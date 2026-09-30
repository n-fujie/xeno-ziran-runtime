// Binary frame decoding. Keep in sync with backend/xzr/runtime/delta.py and backend/xzr/service/protocol.py.

export const FRAME_DELTAS = 1;
export const FRAME_SNAPSHOT = 2;
export const FRAME_AGGREGATES = 3;

export const K = {
  DIFF: 1, FORM: 2, IGNITE: 3, PENETRATE: 4, TRANSFORM: 5, RETURN: 6, DECAY: 7,
  CUT: 8, NEW: 9, REMOVED: 10, RECONF: 11, WEIGHT: 12, MEMORY: 13, GATE: 14, DIFF_DENSE: 15, MEMORY_DENSE: 16,
} as const;

export interface StepDelta {
  t: number;
  diffIdx?: Uint32Array; diffQ?: Uint8Array;
  memIdx?: Uint32Array; memQ?: Uint8Array;
  diffDense?: Uint8Array; memDense?: Uint8Array;
  weightEdge?: Uint32Array; weightVal?: Float32Array;
  gateEdge?: Uint32Array; gateVal?: Float32Array;
  ignitions?: Uint32Array;
  penetrations?: { edge: Uint32Array; origin: Uint32Array; depth: Uint32Array };
  transformations?: { node: Uint32Array; form: Uint32Array };
  returns?: Uint32Array;
  decays?: Uint32Array;
  cuts?: Uint32Array;
  newConnections?: { edge: Uint32Array; src: Uint32Array; dst: Uint32Array; weight: Float32Array };
  removed?: Uint32Array;
  reconfigurations?: { edge: Uint32Array; from: Uint32Array; to: Uint32Array };
}

export interface Snapshot {
  t: number; n: number;
  diffQ: Uint8Array; memQ: Uint8Array; form: Uint8Array; frozen: Uint8Array;
  thetaEff: Float32Array; age: Float32Array;
}

export interface Aggregates { level: number; k: number; t: number; ignitions: Float32Array; meanDiff: Float32Array }

export type Frame =
  | { type: 'deltas'; steps: StepDelta[]; bytes: number }
  | { type: 'snapshot'; snapshot: Snapshot }
  | { type: 'aggregates'; aggregates: Aggregates };

const pad4 = (n: number) => (n + 3) & ~3;

/** A cursor over a little-endian ArrayBuffer that yields aligned typed-array views (copies when unaligned). */
class Reader {
  private dv: DataView;
  constructor(private buf: ArrayBuffer, public off = 0) {
    this.dv = new DataView(buf);
  }
  u32(): number {
    const v = this.dv.getUint32(this.off, true);
    this.off += 4;
    return v;
  }
  u32s(n: number): Uint32Array {
    const a = new Uint32Array(this.buf.slice(this.off, this.off + 4 * n));
    this.off += 4 * n;
    return a;
  }
  f32s(n: number): Float32Array {
    const a = new Float32Array(this.buf.slice(this.off, this.off + 4 * n));
    this.off += 4 * n;
    return a;
  }
  u8s(n: number): Uint8Array {
    const a = new Uint8Array(this.buf.slice(this.off, this.off + n));
    this.off += pad4(n);
    return a;
  }
}

export function decodeStep(r: Reader): StepDelta {
  const t = r.u32();
  const ns = r.u32();
  const d: StepDelta = { t };
  for (let s = 0; s < ns; s++) {
    const kind = r.u32();
    const c = r.u32();
    switch (kind) {
      case K.DIFF: d.diffIdx = r.u32s(c); d.diffQ = r.u8s(c); break;
      case K.MEMORY: d.memIdx = r.u32s(c); d.memQ = r.u8s(c); break;
      case K.DIFF_DENSE: d.diffDense = r.u8s(c); break;
      case K.MEMORY_DENSE: d.memDense = r.u8s(c); break;
      case K.WEIGHT: d.weightEdge = r.u32s(c); d.weightVal = r.f32s(c); break;
      case K.GATE: d.gateEdge = r.u32s(c); d.gateVal = r.f32s(c); break;
      case K.IGNITE: d.ignitions = r.u32s(c); break;
      case K.PENETRATE: d.penetrations = { edge: r.u32s(c), origin: r.u32s(c), depth: r.u32s(c) }; break;
      case K.TRANSFORM: d.transformations = { node: r.u32s(c), form: r.u32s(c) }; break;
      case K.RETURN: d.returns = r.u32s(c); break;
      case K.DECAY: d.decays = r.u32s(c); break;
      case K.CUT: d.cuts = r.u32s(c); break;
      case K.NEW: d.newConnections = { edge: r.u32s(c), src: r.u32s(c), dst: r.u32s(c), weight: r.f32s(c) }; break;
      case K.REMOVED: d.removed = r.u32s(c); break;
      case K.RECONF: d.reconfigurations = { edge: r.u32s(c), from: r.u32s(c), to: r.u32s(c) }; break;
      default: throw new Error(`unknown section kind ${kind}`);
    }
  }
  return d;
}

export function decodeFrame(buf: ArrayBuffer): Frame {
  const r = new Reader(buf);
  const type = r.u32();
  if (type === FRAME_DELTAS) {
    const n = r.u32();
    const steps: StepDelta[] = [];
    for (let i = 0; i < n; i++) steps.push(decodeStep(r));
    return { type: 'deltas', steps, bytes: buf.byteLength };
  }
  if (type === FRAME_SNAPSHOT) {
    const t = r.u32();
    const n = r.u32();
    const snapshot: Snapshot = {
      t, n, diffQ: r.u8s(n), memQ: r.u8s(n), form: r.u8s(n), frozen: r.u8s(n), thetaEff: r.f32s(n), age: r.f32s(n),
    };
    return { type: 'snapshot', snapshot };
  }
  if (type === FRAME_AGGREGATES) {
    const level = r.u32();
    const k = r.u32();
    const t = r.u32();
    return { type: 'aggregates', aggregates: { level, k, t, ignitions: r.f32s(k), meanDiff: r.f32s(k) } };
  }
  throw new Error(`unknown frame type ${type}`);
}

export interface Tile {
  nodes: Uint32Array; x: Float32Array; y: Float32Array;
  edges: Uint32Array; src: Uint32Array; dst: Uint32Array; weight: Float32Array; gate: Float32Array;
  alive: Uint8Array; transform: Uint8Array; truncated: boolean;
}

export function decodeTile(buf: ArrayBuffer): Tile {
  const r = new Reader(buf);
  const nn = r.u32();
  const ne = r.u32();
  const truncated = r.u32() === 1;
  return {
    nodes: r.u32s(nn), x: r.f32s(nn), y: r.f32s(nn),
    edges: r.u32s(ne), src: r.u32s(ne), dst: r.u32s(ne), weight: r.f32s(ne), gate: r.f32s(ne),
    alive: r.u8s(ne), transform: r.u8s(ne), truncated,
  };
}

/** Inverse of the backend's log quantization (0..255 → magnitude). */
export function dequantize(q: number, vmax: number): number {
  return Math.expm1((q * Math.log1p(vmax)) / 255);
}
