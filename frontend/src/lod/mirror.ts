// Client-side mirror of runtime state, kept current from delta frames.
// Node arrays are dense (N entries). Edges and positions are sparse: only what viewport tiles have loaded.
// Semantic events are kept (with wall-clock time) long enough to animate them; nothing is dropped from
// counts — the per-kind totals include every event received.

import type { Aggregates, Snapshot, StepDelta, Tile } from '../proto/decode';

export type Layout = 'network' | 'shape' | 'address' | 'geo';
export const LAYOUT_NAMES: Layout[] = ['network', 'shape', 'address', 'geo'];

export interface Transient { a: number; b: number; wall: number; kind: number; depth?: number }

export const TK = { PENETRATE: 1, CUT: 2, NEW: 3, RECONF_OLD: 4, RECONF_NEW: 5, RETURN: 6, BRANCH: 7 } as const;

export const EVENT_KEYS = ['ignitions', 'penetrations', 'transformations', 'returns', 'decays', 'cuts',
  'newConnections', 'removed', 'reconfigurations'] as const;
export type EventKey = (typeof EVENT_KEYS)[number];

export class Mirror {
  n: number;
  t = 0;
  diffQ: Uint8Array;
  memQ: Uint8Array;
  form: Uint8Array;
  frozen: Uint8Array;
  thetaEff: Float32Array;
  igniteWall: Float64Array; // wall-clock ms of last ignition (for pulses)
  igniteStep: Int32Array;
  returnWall: Float64Array;
  transformWall: Float64Array;
  positions: Record<Layout, Float32Array>;
  // sparse edge store (only edges some tile has shown)
  edgeSrc = new Map<number, number>();
  edgeDst = new Map<number, number>();
  edgeW = new Map<number, number>();
  edgeGate = new Map<number, number>();
  edgeTransform = new Map<number, number>();
  edgesVersion = 0;
  positionsVersion = 0;
  transients: Transient[] = [];
  totals: Record<EventKey, number> = Object.fromEntries(EVENT_KEYS.map((k) => [k, 0])) as Record<EventKey, number>;
  lastStepCounts: Record<EventKey, number> = { ...this.totals };
  aggregates: Aggregates | null = null;
  aggregatePrev: Float32Array | null = null;
  aggregateWall = 0;
  bytes = 0;
  frames = 0;
  firstFrameWall = 0;

  constructor(n: number) {
    this.n = n;
    this.diffQ = new Uint8Array(n);
    this.memQ = new Uint8Array(n);
    this.form = new Uint8Array(n);
    this.frozen = new Uint8Array(n);
    this.thetaEff = new Float32Array(n);
    this.igniteWall = new Float64Array(n).fill(-1e12);
    this.igniteStep = new Int32Array(n).fill(-1e9);
    this.returnWall = new Float64Array(n).fill(-1e12);
    this.transformWall = new Float64Array(n).fill(-1e12);
    const nanArr = () => new Float32Array(n * 2).fill(NaN);
    this.positions = { network: nanArr(), shape: nanArr(), address: nanArr(), geo: nanArr() };
  }

  applySnapshot(s: Snapshot) {
    if (s.n !== this.n) throw new Error('snapshot size mismatch');
    this.t = s.t;
    this.diffQ.set(s.diffQ);
    this.memQ.set(s.memQ);
    this.form.set(s.form);
    this.frozen.set(s.frozen);
    this.thetaEff.set(s.thetaEff);
    this.transients = [];
    for (let i = 0; i < this.n; i++) this.igniteStep[i] = s.t - s.age[i];
  }

  applyTile(layout: Layout, tile: Tile) {
    const p = this.positions[layout];
    for (let i = 0; i < tile.nodes.length; i++) {
      const k = tile.nodes[i] * 2;
      p[k] = tile.x[i];
      p[k + 1] = tile.y[i];
    }
    for (let j = 0; j < tile.edges.length; j++) {
      const e = tile.edges[j];
      if (!tile.alive[j]) continue;
      this.edgeSrc.set(e, tile.src[j]);
      this.edgeDst.set(e, tile.dst[j]);
      this.edgeW.set(e, tile.weight[j]);
      this.edgeGate.set(e, tile.gate[j]);
      this.edgeTransform.set(e, tile.transform[j]);
    }
    this.positionsVersion++;
    this.edgesVersion++;
  }

  clearEdges() {
    this.edgeSrc.clear();
    this.edgeDst.clear();
    this.edgeW.clear();
    this.edgeGate.clear();
    this.edgeTransform.clear();
    this.edgesVersion++;
  }

  setLayoutPositions(layout: Layout, xy: Float32Array) {
    this.positions[layout] = xy;
    this.positionsVersion++;
  }

  applySteps(steps: StepDelta[], now: number, bytes: number) {
    if (!this.firstFrameWall) this.firstFrameWall = now;
    this.frames++;
    this.bytes += bytes;
    let topo = false;
    // spread the steps of one frame over the frame interval so animations stay legible
    const spread = steps.length > 1 ? 30 / steps.length : 0;
    steps.forEach((d, si) => {
      const wall = now + si * spread;
      this.t = d.t;
      const counts = Object.fromEntries(EVENT_KEYS.map((k) => [k, 0])) as Record<EventKey, number>;
      if (d.diffDense) this.diffQ.set(d.diffDense);
      if (d.memDense) this.memQ.set(d.memDense);
      if (d.diffIdx && d.diffQ) for (let i = 0; i < d.diffIdx.length; i++) this.diffQ[d.diffIdx[i]] = d.diffQ[i];
      if (d.memIdx && d.memQ) for (let i = 0; i < d.memIdx.length; i++) this.memQ[d.memIdx[i]] = d.memQ[i];
      if (d.ignitions) {
        counts.ignitions = d.ignitions.length;
        for (const i of d.ignitions) {
          this.igniteWall[i] = wall;
          this.igniteStep[i] = d.t;
        }
      }
      if (d.penetrations) {
        const pe = d.penetrations;
        counts.penetrations = pe.edge.length;
        const perSrc = new Map<number, number>();
        for (let i = 0; i < pe.edge.length; i++) {
          const e = pe.edge[i];
          const a = this.edgeSrc.get(e);
          const b = this.edgeDst.get(e);
          if (a === undefined || b === undefined) continue;
          this.transients.push({ a, b, wall, kind: TK.PENETRATE, depth: pe.depth[i] });
          perSrc.set(a, (perSrc.get(a) ?? 0) + 1);
        }
        for (const [a, c] of perSrc) if (c >= 2) this.transients.push({ a, b: a, wall, kind: TK.BRANCH, depth: c });
      }
      if (d.transformations) {
        counts.transformations = d.transformations.node.length;
        const tr = d.transformations;
        for (let i = 0; i < tr.node.length; i++) {
          this.form[tr.node[i]] = tr.form[i];
          this.transformWall[tr.node[i]] = wall;
        }
      }
      if (d.returns) {
        counts.returns = d.returns.length;
        for (const i of d.returns) {
          this.returnWall[i] = wall;
          this.transients.push({ a: i, b: i, wall, kind: TK.RETURN });
        }
      }
      if (d.decays) counts.decays = d.decays.length;
      if (d.cuts) {
        counts.cuts = d.cuts.length;
        for (const e of d.cuts) {
          const a = this.edgeSrc.get(e);
          const b = this.edgeDst.get(e);
          if (a !== undefined && b !== undefined) this.transients.push({ a, b, wall, kind: TK.CUT });
          this.dropEdge(e);
          topo = true;
        }
      }
      if (d.removed) {
        counts.removed = d.removed.length;
        for (const e of d.removed) {
          this.dropEdge(e);
          topo = true;
        }
      }
      if (d.newConnections) {
        const nc = d.newConnections;
        counts.newConnections = nc.edge.length;
        for (let i = 0; i < nc.edge.length; i++) {
          const e = nc.edge[i];
          this.edgeSrc.set(e, nc.src[i]);
          this.edgeDst.set(e, nc.dst[i]);
          this.edgeW.set(e, nc.weight[i]);
          this.edgeGate.set(e, 1);
          this.edgeTransform.set(e, 0);
          this.transients.push({ a: nc.src[i], b: nc.dst[i], wall, kind: TK.NEW });
          topo = true;
        }
      }
      if (d.reconfigurations) {
        const rc = d.reconfigurations;
        counts.reconfigurations = rc.edge.length;
        for (let i = 0; i < rc.edge.length; i++) {
          const e = rc.edge[i];
          const a = this.edgeSrc.get(e);
          if (a !== undefined) {
            this.transients.push({ a, b: rc.from[i], wall, kind: TK.RECONF_OLD });
            this.transients.push({ a, b: rc.to[i], wall, kind: TK.RECONF_NEW });
            this.edgeDst.set(e, rc.to[i]);
          }
          topo = true;
        }
      }
      if (d.weightEdge && d.weightVal) {
        for (let i = 0; i < d.weightEdge.length; i++) {
          if (this.edgeW.has(d.weightEdge[i])) this.edgeW.set(d.weightEdge[i], d.weightVal[i]);
        }
      }
      if (d.gateEdge && d.gateVal) {
        for (let i = 0; i < d.gateEdge.length; i++) {
          if (this.edgeGate.has(d.gateEdge[i])) this.edgeGate.set(d.gateEdge[i], d.gateVal[i]);
        }
        if (d.gateEdge.length) topo = true;
      }
      for (const k of EVENT_KEYS) this.totals[k] += counts[k];
      this.lastStepCounts = counts;
    });
    if (topo) this.edgesVersion++;
    // bound the animation queue; totals above already counted every event
    const horizon = now - 1500;
    if (this.transients.length > 60000 || (this.transients.length && this.transients[0].wall < horizon)) {
      this.transients = this.transients.filter((x) => x.wall >= horizon).slice(-40000);
    }
  }

  applyAggregates(a: Aggregates, now: number) {
    this.aggregatePrev = this.aggregates?.level === a.level ? this.aggregates.ignitions : null;
    this.aggregates = a;
    this.aggregateWall = now;
  }

  private dropEdge(e: number) {
    this.edgeSrc.delete(e);
    this.edgeDst.delete(e);
    this.edgeW.delete(e);
    this.edgeGate.delete(e);
    this.edgeTransform.delete(e);
  }
}
