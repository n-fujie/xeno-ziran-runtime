// XENO ECOSYSTEM, sixth stage — the repair of a run, read from the data the server returns with it (the stress, the actions, the controller's log, the status record, the saved experiments). Pure functions: nothing here is drawn or listed that
// that data does not contain. A repair path is never invented: where the repair site differs from the damage site, the figure shows both.
import type { RepairBlock, RepairEvent, StressRow } from './meosApi';
import type { Marker, MarkerKind } from './research';

const EVENT_MARKER: Record<string, MarkerKind> = {
  'stress-onset': 'stress-onset', 'repair-decision': 'repair-decision', 'repair-action': 'repair-action', 'repair-failed': 'repair-failed', 'full-recovery': 'full-recovery', 'partial-recovery': 'partial-recovery',
  overshoot: 'overshoot', 'secondary-collapse': 'secondary-collapse', irreversible: 'irreversible', collapse: 'collapse',
};

/** The replay markers of a repaired run: one per event the server derived from the schedule, the controller log, the status record and the saved results. */
export function repairMarkers(rb: RepairBlock | null | undefined): Marker[] {
  if (!rb) return [];
  return rb.events.filter((e) => EVENT_MARKER[e.kind] && !(e as { hidden?: boolean }).hidden).map((e) => ({ tick: e.tick, kind: EVENT_MARKER[e.kind], label: e.label, detail: `${e.detail} [${e.source}]` }));
}

export type RepairPathState = 'intact' | 'damaged' | 'repair-active' | 'internal-active' | 'repaired' | 'bypass' | 'failed';
export interface RepairState {
  tick: number; damagedPath: string | null; paths: Record<string, RepairPathState>; worldActions: RepairEvent[]; internalActions: RepairEvent[]; failed: RepairEvent[]; lastAction: RepairEvent | null;
  recovered: boolean; collapsed: boolean; secondary: boolean; irreversible: boolean; repairSiteDiffers: boolean;
}
const TEMPORARY = new Set(['coupling.bridge', 'renewal.pulse', 'resource.redistribute', 'resource.inflow']);

/** The state of the damage and of the repair at a tick: which path is damaged, which repair is acting where (a temporary action is a *bypass* while it lasts), whether the damaged path has been repaired or the repair has failed. */
export function repairStateAt(rb: RepairBlock | null | undefined, tick: number): RepairState | null {
  if (!rb) return null;
  const ev = rb.events.filter((e) => e.tick <= tick);
  const onset = rb.events.find((e) => e.kind === 'stress-onset');
  const damaged = onset && onset.tick <= tick ? (onset.path ?? null) : null;
  const acts = ev.filter((e) => e.kind === 'repair-action');
  const world = acts.filter((e) => e.klass === 'B'), internal = acts.filter((e) => e.klass === 'A');
  const recovered = ev.some((e) => e.kind === 'full-recovery' || e.kind === 'partial-recovery') && !ev.some((e) => e.kind === 'secondary-collapse');
  const secondary = ev.some((e) => e.kind === 'secondary-collapse'), failedEv = ev.filter((e) => e.kind === 'repair-failed');
  const collapsed = ev.some((e) => e.kind === 'collapse') && !recovered;
  const paths: Record<string, RepairPathState> = {};
  if (damaged) paths[damaged] = recovered ? 'repaired' : secondary || failedEv.length || (collapsed && acts.length) ? 'failed' : acts.length ? 'repair-active' : 'damaged';
  for (const a of acts) {
    if (!a.path || a.path === damaged) continue;
    const temp = TEMPORARY.has(a.action ?? '') && a.duration && tick < a.tick + a.duration;
    paths[a.path] = a.klass === 'A' ? 'internal-active' : temp ? 'bypass' : 'repair-active';  // an internal reconfiguration is not a world-state repair
  }
  const last = acts.length ? acts[acts.length - 1] : null;
  return { tick, damagedPath: damaged, paths, worldActions: world, internalActions: internal, failed: failedEv, lastAction: last, recovered, collapsed, secondary, irreversible: ev.some((e) => e.kind === 'irreversible'), repairSiteDiffers: !!damaged && acts.some((a) => a.path && a.path !== damaged) };
}

export type RecoveryClass = 'internal' | 'world' | 'combined' | 'none';
export interface StripCell { tick: number; classes: RecoveryClass[] }
const inside = (w: number[][], t: number) => w.some(([a, b]) => t >= a && t <= b);

/** The reachable-recovery strip of a stress: for every tick of the tested range, which kinds of tested action recover the run (one-tick resolution to tick 170, and to tick 330 for the windows that were still open at 170; a tick no tested action recovers is ``none``). It is a region of the tested action space, not of the world. */
export function recoveryStrip(row: StressRow, from = 101, to = 330): StripCell[] {
  const out: StripCell[] = [];
  for (let t = from; t <= to; t++) {
    const c: RecoveryClass[] = [];
    if (inside(row.internal_reconfiguration.windows, t)) c.push('internal');
    if (inside(row.world_single.windows, t)) c.push('world');
    if (inside(row.combined.windows, t)) c.push('combined');
    out.push({ tick: t, classes: c.length ? c : ['none'] });
  }
  return out;
}

/** The windows as text, fragments in order: "101-109, 131-133" (a gap is a gap). */
export const windowText = (w: number[][]): string => (w.length ? w.map(([a, b]) => (a === b ? `${a}` : `${a}-${b}`)).join(', ') : 'none');

export interface FailureLabel { id: string; text: string }
/** The failure class of a repaired run read from its evaluation at the long horizon (the taxonomy of the experiments; ``OVERSHOOT`` needs the pulse to be large: see the sweep of the stress). */
export function failureOf(rb: RepairBlock): FailureLabel | null {
  const h = rb.evaluation.horizons.long;
  if (h.success) return null;
  if (h.resource_exhausted) return { id: 'INSUFFICIENT_RESOURCE', text: 'the run is ACTIVE or not, but the resource field is exhausted' };
  if (h.secondary_collapse) return rb.actions.some((a) => a.action === 'resource.pulse' && a.magnitude >= 3) ? { id: 'OVERSHOOT', text: 'a large pulse was followed by a secondary collapse' } : { id: 'SECONDARY_COLLAPSE', text: 'a collapse after a sustained ACTIVE stretch that followed the repair' };
  if (rb.evaluation.horizons.short.success) return { id: 'DESTABILIZED_BY_ACTION', text: 'recovered at the short horizon and not at the long one' };
  if (!rb.actions.length && !rb.controller.attempts) return { id: rb.controller.log.length ? 'OUTSIDE_TESTED_ACTION_SPACE' : 'NO_EFFECTIVE_ACTION', text: rb.controller.log.length ? 'something was detected and no action is available for it' : 'no repair was applied' };
  if (rb.family === 'address') return { id: 'ADDRESS_UNRESOLVED', text: 'the Address stress was not resolved by the repairs applied' };
  return { id: 'NO_EFFECTIVE_ACTION', text: 'the repairs applied did not recover the run' };
}
