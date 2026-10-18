// Pure logic of the XenoBody view (no DOM, no three.js): frame buffering, what an observation shows of the body, kinematics,
// record comparison and formatting. Everything drawn is computed here from runtime values — nothing is a stored picture.
import type { BodyInfo, Frame, ObsDelta, Table, XbRecord } from '../../api/xbtro';

export const SEED = 0;   // the live view follows the first seed of a body

/** The last `seconds` of reference frames of the followed seed, newest last. */
export class FrameBuffer {
  frames: Frame[] = [];
  constructor(public seconds = 12) {}
  push(fs: Frame[]): void {
    this.frames.push(...fs);
    const last = this.frames[this.frames.length - 1];
    if (!last) return;
    const cut = last.t - this.seconds;
    let i = 0;
    while (i < this.frames.length && this.frames[i].t < cut) i++;
    if (i > 0) this.frames.splice(0, i);
  }
  clear(): void { this.frames = []; }
  latest(): Frame | null { return this.frames.length ? this.frames[this.frames.length - 1] : null; }
  /** one reference quantity of the followed seed as a time series */
  series(pick: (f: Frame) => number | undefined): { t: number[]; v: number[] } {
    const t: number[] = []; const v: number[] = [];
    for (const f of this.frames) { const x = pick(f); if (x !== undefined && Number.isFinite(x)) { t.push(f.t); v.push(x); } }
    return { t, v };
  }
}

export interface Sample { t: number; at: number; x: (number | null)[] }

/** What each observation model has delivered so far (followed seed). Missing samples are null: never filled in. */
export class ObservationStore {
  models = new Map<string, { kind: string; channels: string[]; samples: Sample[]; retired: number | null; hz: number }>();
  push(delta: Record<string, ObsDelta>, keep = 12): void {
    for (const [id, d] of Object.entries(delta)) {
      let m = this.models.get(id);
      if (!m) { m = { kind: d.kind, channels: d.channels, samples: [], retired: d.retired_from_t, hz: d.sample_hz }; this.models.set(id, m); }
      m.retired = d.retired_from_t;
      const rows = d.x[SEED] ?? [];
      for (let i = 0; i < d.t.length; i++) m.samples.push({ t: d.t[i], at: d.available_at[i], x: rows[i] ?? [] });
      const last = m.samples[m.samples.length - 1];
      if (last) { const cut = last.t - keep; let k = 0; while (k < m.samples.length && m.samples[k].t < cut) k++; if (k > 0) m.samples.splice(0, k); }
    }
  }
  clear(): void { this.models.clear(); }
  /** the newest sample that is available at time `t` (its delay has passed) and holds at least one value; samples that were dropped or
   *  blind are skipped (the last real value is held, and its age is reported — the display must show that it is stale) */
  holding(id: string, t: number): (Sample & { age: number }) | null {
    const m = this.models.get(id);
    if (!m) return null;
    for (let i = m.samples.length - 1; i >= 0; i--) {
      const s = m.samples[i];
      if (s.at <= t && s.x.some((v) => v !== null)) return { ...s, age: t - s.at };
    }
    return null;
  }
  series(id: string, channel: number, t0: number): { t: number[]; v: number[] } {
    const m = this.models.get(id);
    const t: number[] = []; const v: number[] = [];
    if (!m) return { t, v };
    for (const s of m.samples) { const x = s.x[channel]; if (s.at >= t0 && x !== null && x !== undefined && Number.isFinite(x)) { t.push(s.at); v.push(x); } }
    return { t, v };
  }
}

export interface Pose {
  /** absolute segment angles (rad), null where nothing observes that segment */
  angles: (number | null)[];
  source: 'joint' | 'segment' | 'pooled' | 'none';
  model: string | null;
  /** seconds since the value shown was delivered (large = the device has been silent: dropout, blind window or retired) */
  age: number;
}

/** The body as the observation shows it: joint angles accumulate along the chain, so one missing joint hides everything above it. */
export function observedPose(info: BodyInfo, obs: ObservationStore, t: number): Pose {
  const n = info.links.length;
  const none: Pose = { angles: new Array<number | null>(n).fill(null), source: 'none', model: null, age: Infinity };
  for (const [id, m] of obs.models) {
    if (m.kind !== 'posture' || (m.retired !== null && m.retired <= t)) continue;
    const s = obs.holding(id, t);
    if (!s) continue;
    const joint = m.channels.every((c) => c.startsWith('q:'));
    const segment = m.channels.every((c) => c.startsWith('theta:'));
    if (joint) {
      const q = new Array<number | null>(n).fill(null);
      m.channels.forEach((c, k) => { const j = info.joints.findIndex((jj) => `q:${jj.id}` === c); if (j >= 0) q[j] = s.x[k]; });
      const angles: (number | null)[] = [];
      let acc: number | null = 0;
      for (let i = 0; i < n; i++) { acc = acc !== null && q[i] !== null ? acc + (q[i] as number) : null; angles.push(acc); }
      return { angles, source: 'joint', model: id, age: s.age };
    }
    if (segment) {
      const a = new Array<number | null>(n).fill(null);
      m.channels.forEach((c, k) => { const i = info.links.findIndex((l) => `theta:${l.id}` === c); if (i >= 0) a[i] = s.x[k]; });
      return { angles: a, source: 'segment', model: id, age: s.age };
    }
    if (m.channels[0] === 'lean:pooled') {
      const lean = s.x[0];
      return { angles: new Array<number | null>(n).fill(lean), source: 'pooled', model: id, age: s.age };
    }
  }
  return none;
}

export interface Point { x: number; y: number }

/** Joint positions of the planar chain for absolute segment angles (the ankle at the origin). */
export function chain(info: BodyInfo, angles: (number | null)[]): { points: Point[]; known: boolean[] } {
  const pts: Point[] = [{ x: 0, y: 0 }];
  const known: boolean[] = [];
  let ok = true;
  for (let i = 0; i < info.links.length; i++) {
    const a = angles[i];
    ok = ok && a !== null && a !== undefined;
    const th = ok ? (a as number) : 0;
    const p = pts[i];
    pts.push({ x: p.x + info.links[i].length * Math.sin(th), y: p.y + info.links[i].length * Math.cos(th) });
    known.push(ok);
  }
  return { points: pts, known };
}

/** Whole-body COM from absolute segment angles (the same kinematics the simulator uses); null if any segment is unobserved. */
export function comFromAngles(info: BodyInfo, angles: (number | null)[]): number | null {
  if (angles.some((a) => a === null || a === undefined)) return null;
  let m = 0; let s = 0; let base = 0;
  info.links.forEach((l, i) => {
    const th = angles[i] as number;
    s += l.mass * (base + l.com_frac * l.length * Math.sin(th));
    m += l.mass;
    base += l.length * Math.sin(th);
  });
  return m > 0 ? s / m : null;
}

/** Position of a part of the reference body (for markers): link midpoint or joint. */
export function partPosition(info: BodyInfo, angles: (number | null)[], part: string): Point | null {
  const { points } = chain(info, angles.map((a) => a ?? 0));
  const [kind, id] = part.split(':');
  if (kind === 'link') { const i = info.links.findIndex((l) => l.id === id); return i < 0 ? null : { x: (points[i].x + points[i + 1].x) / 2, y: (points[i].y + points[i + 1].y) / 2 }; }
  if (kind === 'joint') { const i = info.joints.findIndex((j) => j.id === id); return i < 0 ? null : points[i]; }
  return null;
}

/** Regions of the body that no deployed model reaches, as the coverage of the current observation configuration states them. */
export const unobservedRegions = (info: BodyInfo): string[] => info.coverage.unobserved_regions;

// -------------------------------------------------------------------------------- records
const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

export interface DiffRow { key: string; cells: { column: string; a: number | null; b: number | null; delta: number | null }[] }
export interface TableDiff { name: string; title: string; labelColumns: string[]; rows: DiffRow[]; onlyInA: number; onlyInB: number }

/** Before / after: tables with the same name in two records are matched row by row on their text columns; numeric columns are differenced. */
export function compareRecords(a: XbRecord, b: XbRecord): TableDiff[] {
  const out: TableDiff[] = [];
  for (const ta of a.results.tables) {
    const tb = b.results.tables.find((t) => t.name === ta.name);
    if (!tb || ta.columns.join('|') !== tb.columns.join('|')) continue;
    const labelIdx = ta.columns.map((_, i) => i).filter((i) => ta.rows.every((r) => !isNum(r[i])) );
    const numIdx = ta.columns.map((_, i) => i).filter((i) => !labelIdx.includes(i));
    const keyOf = (r: Table['rows'][number]) => labelIdx.map((i) => String(r[i])).join(' · ');
    const mb = new Map(tb.rows.map((r) => [keyOf(r), r]));
    const rows: DiffRow[] = [];
    let onlyA = 0;
    for (const r of ta.rows) {
      const o = mb.get(keyOf(r));
      if (!o) { onlyA++; continue; }
      mb.delete(keyOf(r));
      rows.push({ key: keyOf(r), cells: numIdx.map((i) => {
        const x = isNum(r[i]) ? (r[i] as number) : null; const y = isNum(o[i]) ? (o[i] as number) : null;
        return { column: ta.columns[i], a: x, b: y, delta: x !== null && y !== null ? y - x : null };
      }) });
    }
    out.push({ name: ta.name, title: ta.title, labelColumns: labelIdx.map((i) => ta.columns[i]), rows, onlyInA: onlyA, onlyInB: mb.size });
  }
  return out;
}

export function fmt(x: unknown, digits = 3): string {
  if (x === null || x === undefined) return '—';
  if (typeof x === 'boolean') return x ? 'yes' : 'no';
  if (typeof x === 'string') return x;
  if (!Number.isFinite(x as number)) return '—';
  const v = x as number;
  if (v === 0) return '0';
  const a = Math.abs(v);
  return a >= 1000 || a < 0.001 ? v.toExponential(2) : Number(v.toPrecision(digits + (a >= 10 ? 0 : 0))).toString();
}

/** Colour of a status word used by the observability and fragility views (never the only carrier of meaning: the word is always shown). */
export const STATUS_COLOR: Record<string, string> = {
  identified: '#7fe0a0', 'identified-by-proxy': '#b6e07f', 'noise-limited': '#e0c07f', unobserved: '#e08a7f', 'no-difference-in-model': '#6e6e78',
  improved: '#7fe0a0', worsened: '#e08a7f', 'no detectable effect': '#6e6e78', undefined: '#4a4a52',
  established: '#7fe0a0', varied: '#e0c07f', lapsed: '#e08a7f', 'interventionally-supported': '#7fe0a0', 'correlational-only': '#e0c07f', untested: '#6e6e78',
};
export const CLASS_LABEL: Record<string, string> = {
  reference: 'reference (model state)', observation: 'observation (device output)', estimate: 'estimate (model-based)',
};
export const LAYER_COLOR = { reference: '#d8d8dc', observation: '#5fd0e8', estimate: '#f0b45a' } as const;

/** The COM computed from the observation alone, as a time series: every delivered posture sample that observes the whole chain gives
 *  one point, placed at the time it became available. Samples that do not observe every segment give no point (nothing is filled in). */
export function obsComSeries(info: BodyInfo, obs: ObservationStore, t0: number): { t: number[]; v: number[] } {
  const t: number[] = []; const v: number[] = [];
  for (const [, m] of obs.models) {
    if (m.kind !== 'posture') continue;
    const joint = m.channels.every((c) => c.startsWith('q:'));
    const segment = m.channels.every((c) => c.startsWith('theta:'));
    for (const s of m.samples) {
      if (s.at < t0) continue;
      let angles: (number | null)[] | null = null;
      if (joint) {
        const q = new Array<number | null>(info.links.length).fill(null);
        m.channels.forEach((c, k) => { const j = info.joints.findIndex((jj) => `q:${jj.id}` === c); if (j >= 0) q[j] = s.x[k]; });
        let acc: number | null = 0;
        angles = q.map((x) => (acc = acc !== null && x !== null ? acc + x : null));
      } else if (segment) {
        const a = new Array<number | null>(info.links.length).fill(null);
        m.channels.forEach((c, k) => { const i = info.links.findIndex((l) => `theta:${l.id}` === c); if (i >= 0) a[i] = s.x[k]; });
        angles = a;
      }
      const c = angles ? comFromAngles(info, angles) : null;
      if (c !== null) { t.push(s.at); v.push(c); }
    }
  }
  const order = t.map((_, i) => i).sort((a, b) => t[a] - t[b]);
  return { t: order.map((i) => t[i]), v: order.map((i) => v[i]) };
}
