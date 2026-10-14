// Pure mapping from a recorded laboratory run (schema xzr.labrun/1–3, written by backend/xzr/lab/record.py) to what the
// 3D view draws. The renderer draws these values and nothing else: every visual quantity is a recorded runtime-derived
// apparatus value, and every highlight is a recorded apparatus event. Nothing here can change the run.

export type LabEvent = {
  t: number; type: 'containment_close' | 'containment_open' | 'conduit_established' | 'conduit_severed';
  chamber?: string; pair?: string; before: number; after: number; cause: string[];
};
export type PhysState = {
  fingerprint: string;
  gantries: Record<string, { tip: [number, number, number]; health: number; failed: boolean; carrying: string | null;
    resources: number; queue: number; bay?: string; group?: string | null }>;
  samples: Record<string, [number, number, number]>;
  contents: Record<string, string[]>;
};
export type SystemState = { sensor: string; window: number; budget: number; coverage: string[]; features: string[];
  pending: [string, string] | null; isolated: string[]; memory: number };
export type LabStep = {
  t: number; fingerprint: string; digest: string; shutter: number[]; activity: number[]; memory: number[];
  conduits: Record<string, number>; physics?: PhysState; science?: Record<string, SystemState>;
};
export type PhysEvent = { t: number; type: string; [k: string]: unknown };
export type Layout = { bays: Record<string, [number, number]>; ports: Record<string, [number, number]>; chamber_half: number;
  wall_height: number; sample_half: number; port_half: number; safe_z: number };
export type LabRecord = {
  schema: string; config: Record<string, unknown>; chambers: { cid: string; position: [number, number, number]; size: number }[];
  steps: LabStep[]; events: LabEvent[]; operations: string[]; note: string;
  layout?: Layout | null; physical_events?: PhysEvent[]; science_events?: PhysEvent[];
};
export type SystemSpecLite = { sid: string; kind: string; home: string; store?: string | null; sensors?: string[] };
export type SystemVisual = SystemState & { sid: string; kind: string; store: string | null };

/** Physics plane (x, y, z-up; chamber floor top at z = 0.05) → 3D view (x, height, z; chamber floor top at 0.3). */
export const PHYS_Y0 = 0.25;
export function physToView(p: [number, number, number]): [number, number, number] {
  return [p[0], p[2] + PHYS_Y0, p[1]];
}
/** key = bay (shared laboratory) or bay#group (a group's private carriage, schema 3 resource partition). */
export type GantryVisual = { key: string; bay: string; group: string | null; tip: [number, number, number]; health: number;
  failed: boolean; carrying: string | null };
export type SampleVisual = { sid: string; position: [number, number, number]; carried: boolean };

/** How long (in steps) a recorded event stays highlighted after it occurred. */
export const HIGHLIGHT_STEPS = 12;

export type ChamberVisual = {
  cid: string; position: [number, number, number];
  shutterClosure: number;  // 1 − shutter permeability: the drawn closure of the containment panels
  coreGlow: number;  // activity (share of configurations that ignited this step), clamped to [0, 1]
  coreScale: number;  // 0.45 + memory, clamped: retained history drawn as the size of the material core
  highlight: LabEvent | null;  // most recent containment event within HIGHLIGHT_STEPS, if any
};
export type ConduitVisual = { a: string; b: string; count: number; highlight: LabEvent | null };
export type Frame = {
  t: number; index: number; chambers: ChamberVisual[]; conduits: ConduitVisual[]; events: LabEvent[];
  gantries: GantryVisual[]; samples: SampleVisual[]; physicalEvents: PhysEvent[];
  systems: SystemVisual[]; scienceEvents: PhysEvent[];
};

export function validate(r: unknown): LabRecord {
  const x = r as LabRecord;
  if (!x || !SCHEMAS.includes(x.schema) || !Array.isArray(x.steps) || !x.steps.length) {
    throw new Error('not an xzr.labrun/1, /2 or /3 record');
  }
  return x;
}
export const SCHEMAS = ['xzr.labrun/1', 'xzr.labrun/2', 'xzr.labrun/3'];

/** The recorded causal-pathway configuration of a run (schema 3), as text; empty for earlier records. */
export function pathways(r: LabRecord): string[] {
  const c = r.config as { partition?: Record<string, unknown>; systems?: Record<string, unknown>[]; harness?: Record<string, unknown>[] };
  const out: string[] = [];
  if (c.partition) {
    const p = c.partition;
    const priv = ['gantries', 'material', 'queues'].filter((k) => p[k] === 'private');
    out.push(`resources: ${priv.length ? priv.join(', ') + ' private per group' : 'shared'}`
      + (p.priority ? `; priority ${String(p.priority)}` : '') + ((p.wear_exempt as string[] | undefined)?.length ? `; wear exempt ${String(p.wear_exempt)}` : ''));
  }
  for (const s of c.systems ?? []) {
    const bits = [s.comm && s.comm !== 'conduit' ? `communication ${String(s.comm)}` : '', s.comm_free ? 'communication free' : '',
      s.inert ? 'inert (no runtime effect)' : ''].filter(Boolean);
    if (bits.length) out.push(`${String(s.sid)}: ${bits.join(', ')}`);
  }
  if (c.harness?.length) out.push(`harness: ${c.harness.map((h) => `${String(h.do)}@${String(h.at)}`).join(' ')}`);
  return out;
}

export function frameAt(r: LabRecord, index: number): Frame {
  const i = Math.max(0, Math.min(r.steps.length - 1, Math.floor(index)));
  const s = r.steps[i];
  const recent = r.events.filter((e) => e.t <= s.t && e.t > s.t - HIGHLIGHT_STEPS);
  const lastFor = (pred: (e: LabEvent) => boolean) => [...recent].reverse().find(pred) ?? null;
  const chambers = r.chambers.map((c, k) => ({
    cid: c.cid, position: c.position,
    shutterClosure: 1 - s.shutter[k],
    coreGlow: Math.min(1, Math.max(0, s.activity[k])),
    coreScale: Math.min(1.6, 0.45 + Math.max(0, s.memory[k])),
    highlight: lastFor((e) => e.chamber === c.cid),
  }));
  const pairs = new Set([...Object.keys(s.conduits), ...recent.filter((e) => e.pair).map((e) => e.pair as string)]);
  const conduits = [...pairs].sort().map((p) => {
    const [a, b] = p.split('|');
    return { a, b, count: s.conduits[p] ?? 0, highlight: lastFor((e) => e.pair === p) };
  });
  const ph = s.physics;
  const carried = new Set(ph ? Object.values(ph.gantries).map((g) => g.carrying).filter(Boolean) : []);
  return {
    t: s.t, index: i, chambers, conduits, events: r.events.filter((e) => e.t <= s.t),
    gantries: ph ? Object.entries(ph.gantries).map(([key, g]) => ({ key, bay: g.bay ?? key, group: g.group ?? null,
      tip: physToView(g.tip), health: g.health, failed: g.failed, carrying: g.carrying })) : [],
    samples: ph ? Object.entries(ph.samples).map(([sid, p]) => ({ sid, position: physToView(p), carried: carried.has(sid) })) : [],
    physicalEvents: (r.physical_events ?? []).filter((e) => e.t <= s.t),
    systems: s.science ? Object.entries(s.science).map(([sid, st]) => {
      const spec = ((r.config.systems ?? []) as SystemSpecLite[]).find((x) => x.sid === sid);
      return { ...st, sid, kind: spec?.kind ?? '?', store: spec?.store ?? null };
    }) : [],
    scienceEvents: (r.science_events ?? []).filter((e) => e.t <= s.t),
  };
}
