// Pure mapping from a recorded laboratory run (schema xzr.labrun/1, written by backend/xzr/lab/record.py) to what the
// 3D view draws. The renderer draws these values and nothing else: every visual quantity is a recorded runtime-derived
// apparatus value, and every highlight is a recorded apparatus event. Nothing here can change the run.

export type LabEvent = {
  t: number; type: 'containment_close' | 'containment_open' | 'conduit_established' | 'conduit_severed';
  chamber?: string; pair?: string; before: number; after: number; cause: string[];
};
export type LabStep = {
  t: number; fingerprint: string; digest: string; shutter: number[]; activity: number[]; memory: number[];
  conduits: Record<string, number>;
};
export type LabRecord = {
  schema: string; config: Record<string, unknown>; chambers: { cid: string; position: [number, number, number]; size: number }[];
  steps: LabStep[]; events: LabEvent[]; operations: string[]; note: string;
};

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
export type Frame = { t: number; index: number; chambers: ChamberVisual[]; conduits: ConduitVisual[]; events: LabEvent[] };

export function validate(r: unknown): LabRecord {
  const x = r as LabRecord;
  if (!x || x.schema !== 'xzr.labrun/1' || !Array.isArray(x.steps) || !x.steps.length) throw new Error('not an xzr.labrun/1 record');
  return x;
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
  return { t: s.t, index: i, chambers, conduits, events: r.events.filter((e) => e.t <= s.t) };
}
