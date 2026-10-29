// XENO ECOSYSTEM — the research readings of a run, as pure functions of the record (no scene, no clock): event markers for the replay timeline, the state shown when a tick is
// inspected, snapshots and their differences (baseline / intervention / recovered), the mechanical reading of SSS and the state of the M2 tap.
//
// MODEL RESULT and VISUAL REPRESENTATION are kept apart. Everything in this file that is a number about the run (operational state, observed state, observability, boundary, Address
// Domain, SSS, energy, resource, history, path activity) is read from the record the engine produced. ``sssMechanics`` and ``m2TapState`` are different in kind: they say how the *bodies*
// are posed for a run (a design choice of the view, written down here and tested), and a pose is never evidence about the run.
import type { Label, MeosRecord, Observed, ObservabilityStatus, PathActivity, PathId } from './meosApi';
import type { Outcome, RouteState, Topology } from './routeGraph';
import { PATH_IDS } from './meosApi';
import { RECOVERY_TICKS } from './bodyState';
import type { PartState } from './technical';
export * from './mechanics';

// ---------------------------------------------------------------------------------------------------- event markers
export type MarkerKind = 'intervention' | 'boundary' | 'address' | 'pulse' | 'collapse' | 'recovery' | 'observation-failure' | 'route-switch' | 'mfs-change' | 'route-ok' | 'route-failed' | 'fallback' | 'adaptive-switch' | 'm2-takeover' | 'history-loss' | 'address-recovery' | 'address-reassign' | 'stress-onset' | 'repair-decision' | 'repair-action' | 'repair-failed' | 'full-recovery' | 'partial-recovery' | 'overshoot' | 'secondary-collapse' | 'irreversible';
export interface Marker { tick: number; kind: MarkerKind; label: string; detail: string }
export const MARKER_COLOR: Record<MarkerKind, string> = { intervention: '#e8e8ea', boundary: '#c9a227', address: '#7aa7e0', pulse: '#5fb98a', collapse: '#d04a3a', recovery: '#47c26b', 'observation-failure': '#b07acc', 'route-switch': '#38c9c0', 'mfs-change': '#2f8fd0', 'route-ok': '#7fe08a', 'route-failed': '#e0707a', fallback: '#e0b040', 'm2-takeover': '#d080e0', 'history-loss': '#c07a30', 'address-recovery': '#9ad0f0', 'adaptive-switch': '#8a5fd0', 'address-reassign': '#5f9fd8', 'stress-onset': '#d0603a', 'repair-decision': '#6fa8dc', 'repair-action': '#3fb0a0', 'repair-failed': '#c0392b', 'full-recovery': '#2ecc71', 'partial-recovery': '#9bd07a', overshoot: '#e67e22', 'secondary-collapse': '#a93226', irreversible: '#7f8c8d' };
export const MARKER_LABEL: Record<MarkerKind, string> = { intervention: 'intervention', boundary: 'boundary change', address: 'Address Domain', pulse: 'resource pulse', collapse: 'collapse', recovery: 'recovery', 'observation-failure': 'observation failure', 'route-switch': 'route switch', 'mfs-change': 'MFS change', 'route-ok': 'successful reconfiguration', 'route-failed': 'failed reconfiguration', fallback: 'fallback activation', 'm2-takeover': 'M2 takeover', 'history-loss': 'history loss', 'address-recovery': 'Address recovery', 'adaptive-switch': 'adaptive switch', 'address-reassign': 'Address reassignment', 'stress-onset': 'stress onset', 'repair-decision': 'repair decision', 'repair-action': 'repair action', 'repair-failed': 'failed repair', 'full-recovery': 'full recovery', 'partial-recovery': 'sustained (prevented)', overshoot: 'overshoot', 'secondary-collapse': 'secondary collapse', irreversible: 'irreversible threshold' };
const BOUNDARY_TARGETS = new Set(['interaction_channel', 'feedback', 'resource_renewal', 'history', 'sensor_resource', 'sensor_alteration']);

type LogEntry = MeosRecord['intervention_log'][number];
const describe = (iv: LogEntry): string => {
  const rest = Object.entries(iv).filter(([k]) => !['tick', 'op', 'event', 'target', 'address_mode'].includes(k)).map(([k, v]) => `${k} ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`).join(', ');
  return `${iv.op} ${String(iv.target ?? iv.address_mode ?? '')}${rest ? ` (${rest})` : ''}`.trim();
};

/** Every point of a run worth looking at: interventions (of their kind), collapse, recovery, Address Domain updates and the starts of observation failures. */
export function eventMarkers(rec: MeosRecord, observed?: Observed | null, routes?: { topology?: Topology | null; outcomes?: Outcome[] }): Marker[] {
  const out: Marker[] = [];
  const histLost = (t: number) => rec.intervention_log.some((x) => x.op === 'REMOVE' && x.target === 'history' && x.tick <= t);
  for (const iv of rec.intervention_log) {
    if (iv.op === 'ROUTE') {
      const m2On = iv.m2 && (iv.m2 as { sense?: string }).sense !== 'none', ctl = 'why' in iv;
      out.push({ tick: iv.tick, kind: ctl ? 'route-switch' : 'route-switch', label: `ROUTE${ctl ? ` ${String(iv.from)} → ${String(iv.to)}` : ' (set by hand)'}`, detail: `${describe(iv)}${ctl ? `; sensed ${String(iv.trigger ?? iv.why)}` : ''}` });
      const kindOf = routes?.topology?.controller;
      if (ctl && (kindOf === 'fixed' || iv.to === 'fixed fallback')) out.push({ tick: iv.tick, kind: 'fallback', label: 'FIXED FALLBACK ACTIVATED', detail: `route ${String(iv.to)}, cost ${String(iv.cost)}` });
      else if (ctl && kindOf && kindOf !== 'none') out.push({ tick: iv.tick, kind: 'adaptive-switch', label: 'ADAPTIVE SWITCH', detail: `${String(iv.from)} → ${String(iv.to)}, cost ${String(iv.cost)}; trigger ${String(iv.trigger ?? iv.why)}` });
      if (m2On && histLost(iv.tick)) out.push({ tick: iv.tick, kind: 'm2-takeover', label: 'M2 TAKEOVER', detail: 'M2 sensing switched on after history was removed' });
      continue;
    }
    if (iv.op === 'REMOVE' && iv.target === 'history') out.push({ tick: iv.tick, kind: 'history-loss', label: 'HISTORY LOST', detail: describe(iv) });
    if (iv.op === 'ADDRESS' && (iv.address_mode === 'reassign' || iv.address_mode === 'delayed')) out.push({ tick: iv.tick, kind: 'address-reassign', label: `ADDRESS REASSIGNED ${String(iv.target)}`, detail: describe(iv) });
    if (iv.op === 'ADDRESS' && iv.address_mode === 'restore') out.push({ tick: iv.tick, kind: 'address-recovery', label: `ADDRESS RECOVERY ${String(iv.target)}`, detail: describe(iv) });
    const kind: MarkerKind = iv.op === 'ADDRESS' ? 'address' : iv.op === 'CHANGE_BOUNDARY' || (['REMOVE', 'ISOLATE', 'RECONNECT'].includes(iv.op) && BOUNDARY_TARGETS.has(String(iv.target))) ? 'boundary' : iv.op === 'ALTER_RESOURCE' && 'inject' in iv ? 'pulse' : 'intervention';
    out.push({ tick: iv.tick, kind, label: kind === 'address' ? `ADDRESS ${String(iv.address_mode)} ${String(iv.target)}` : `${iv.op} ${String(iv.target ?? '')}`.trim(), detail: describe(iv) });
  }
  let collapsed = false;  // a recovery is the first ACTIVE after a collapse (the status may pass through DEGRADED on the way)
  for (const s of rec.status_log) {
    if (s.label === 'COLLAPSED' && !collapsed) { collapsed = true; out.push({ tick: s.tick, kind: 'collapse', label: 'COLLAPSE', detail: s.dependency?.detail ?? s.reason }); }
    else if (s.label === 'ACTIVE' && collapsed) { collapsed = false; out.push({ tick: s.tick, kind: 'recovery', label: 'RECOVERY', detail: s.reason }); }
  }
  for (const e of rec.events) if (e.kind === 'address_update') out.push({ tick: e.tick, kind: 'address', label: `ADDRESS update ${e.actor ?? ''}`.trim(), detail: String(e.action ?? '') });
  for (const tr of routes?.topology?.transitions ?? []) if (tr.from !== tr.to) out.push({ tick: tr.tick, kind: 'mfs-change', label: `MFS ${tr.from} → ${tr.to}`, detail: `trigger ${tr.trigger.join(', ')}; cost ${tr.cost} (enabled ${tr.enabled.join(', ') || 'nothing'})` });
  for (const o of routes?.outcomes ?? []) out.push({ tick: o.tick, kind: o.preserved_at_end ? 'route-ok' : 'route-failed', label: o.preserved_at_end ? 'RECONFIGURATION OK' : 'RECONFIGURATION FAILED', detail: `${o.from} → ${o.to}: ${o.preserved_at_end ? 'the operation is preserved at the end' : 'the operation is not preserved at the end'}; ${o.operation_lost_ticks_after} ticks not ACTIVE after the switch; recovery latency ${o.recovery_latency ?? 'none'}` });
  if (observed?.timeline) {
    let start: number | null = null, status: string = '';
    const close = (end: number) => { if (start !== null) out.push({ tick: start, kind: 'observation-failure', label: 'OBSERVATION FAILS', detail: `${status} until tick ${end} (operational state and observed state differ; the run itself is unchanged)` }); start = null; };
    for (const r of observed.timeline) {
      if (r.observability !== 'SUFFICIENT') { if (start === null || r.observability !== status) { close(r.t - 1); start = r.t; status = r.observability; } } else close(r.t - 1);
    }
    close(observed.timeline.length - 1);
  }
  return out.sort((a, b) => a.tick - b.tick || a.kind.localeCompare(b.kind));
}

// ---------------------------------------------------------------------------------------------------- path state at a tick
export type PathState = 'cut' | 'active' | 'quiet';
export function pathStatesAt(paths: PathActivity | null | undefined, tick: number): Record<PathId, PathState> {
  const out = {} as Record<PathId, PathState>;
  for (const id of PATH_IDS) out[id] = paths?.[id]?.state_intervals.find((i) => tick >= i.from && tick <= i.to)?.state ?? 'quiet';
  return out;
}

// ---------------------------------------------------------------------------------------------------- inspection
export interface Inspect {
  tick: number; operational: Label; observed: Label | null; observability: ObservabilityStatus | null; limiting: string[];
  boundary: { open: string[]; arenaRadius: number | null; historyAccess: { A1: boolean; A2: boolean } };
  address: Record<'A1' | 'A2', { mode: string | null; integrity: number; cell: [number, number]; names: [number, number] }>;
  sss: { scale: number; size: number; speed: number }; energy: { a1: number; power: number }; resource: { total: number; flow: number };
  history: { enabled: boolean; trace: { A1: number; A2: number }; contribution: { A1: number; A2: number } };
  paths: Record<PathId, PathState>; m2: { sense: string; sensed: number | null }; markers: Marker[];
  /** the routes at this tick (fifth stage): current MFS, active / dormant / failed paths, the routes still open and the routes closed, the last transition and its trigger */ route: RouteState | null;
}
/** The components cut at a tick, from the intervention log (REMOVE and ISOLATE cut, RECONNECT restores). */
export function openComponents(rec: MeosRecord, tick: number): string[] {
  const open = new Set<string>();
  for (const iv of rec.intervention_log) if (iv.tick <= tick) { const t = String(iv.target); if (iv.op === 'REMOVE' || iv.op === 'ISOLATE') open.add(t); else if (iv.op === 'RECONNECT') open.delete(t); }
  return [...open];
}
const at = (a: number[] | undefined, t: number): number => (a && a.length ? a[Math.min(t, a.length - 1)] : 0);

export function inspectAt(rec: MeosRecord, observed: Observed | null | undefined, tick: number, paths: PathActivity | null | undefined, markers: Marker[] = [], route: RouteState | null = null): Inspect {
  const t = Math.min(Math.max(0, tick), rec.frames.length - 1), f = rec.frames[t], tr = rec.traces ?? {};
  let ad = null as null | { A1: { sss: { scale: number; size: number; speed: number }; history_reentry_enabled: boolean; operational_boundary: { arena_radius: number | null } } };
  for (let i = t; i >= 0; i--) if (rec.frames[i].ad) { ad = rec.frames[i].ad as unknown as typeof ad; break; }
  const row = observed?.timeline?.[t];
  const addr = (n: 'A1' | 'A2') => {
    const a = f.address?.[n];
    return { mode: a?.mode ?? null, integrity: a?.integrity ?? 1, cell: [f[n].x, f[n].y] as [number, number], names: (a?.at ?? [f[n].x, f[n].y]) as [number, number] };
  };
  let arena: number | null = rec.config.environment.arena_radius as number | null;
  for (const iv of rec.intervention_log) if (iv.tick <= t && iv.op === 'CHANGE_BOUNDARY') arena = iv.arena_radius as number;
  const access = (rec.config.history.access ?? {}) as unknown as Record<string, boolean>;
  const sense = rec.config.m2?.sense ?? 'none';
  return {
    tick: t, operational: f.status, observed: row?.observed ?? null, observability: row?.observability ?? null, limiting: row?.limiting ?? [],
    boundary: { open: openComponents(rec, t), arenaRadius: arena, historyAccess: { A1: access.A1 !== false, A2: access.A2 !== false } },
    address: { A1: addr('A1'), A2: addr('A2') },
    sss: ad?.A1.sss ?? rec.config.sss, energy: { a1: f.A1.energy, power: f.power }, resource: { total: at(tr.resource_total, t) || f.R, flow: at(tr.resource_flow, t) },
    history: { enabled: ad ? ad.A1.history_reentry_enabled : true, trace: { A1: f.A1.h, A2: f.A2.h }, contribution: { A1: at(tr.history_contribution_a1, t), A2: at(tr.history_contribution_a2, t) } },
    paths: pathStatesAt(paths, t), m2: { sense, sensed: sense === 'none' ? null : at(tr.m2_sensed, t) }, markers: markers.filter((m) => Math.abs(m.tick - t) <= 1), route,
  };
}

// ---------------------------------------------------------------------------------------------------- snapshots and their difference
export interface Snapshot { label: string; tick: number; inspect: Inspect; parts: Record<string, PartState> }
export interface Delta {
  from: string; to: string;
  status: [Label, Label]; observed: [Label | null, Label | null]; observabilityChange: 'lost' | 'gained' | 'unchanged'; observability: [ObservabilityStatus | null, ObservabilityStatus | null];
  components: Array<{ id: string; from: PartState; to: PartState }>; paths: Array<{ path: PathId; from: PathState; to: PathState }>;
  boundary: { opened: string[]; closed: string[]; arenaRadius: [number | null, number | null] | null };
  address: Array<{ target: 'A1' | 'A2'; from: string; to: string }>; sss: boolean; changedCount: number;
}
const addrText = (a: Inspect['address']['A1']) => `${a.mode ?? 'intact'}${a.names[0] !== a.cell[0] || a.names[1] !== a.cell[1] ? ` (names ${a.names.join(',')}, body at ${a.cell.join(',')})` : ''}${a.integrity < 1 ? ` integrity ${a.integrity.toFixed(2)}` : ''}`;

/** What differs between two snapshots of the same record: components whose state changed, paths whose state changed, observability lost or gained, boundary changes, address changes. */
export function deltaSnapshots(a: Snapshot, b: Snapshot): Delta {
  const A = a.inspect, B = b.inspect;
  const components = Object.keys(b.parts).filter((id) => a.parts[id] && a.parts[id] !== b.parts[id]).map((id) => ({ id, from: a.parts[id], to: b.parts[id] }));
  const paths = PATH_IDS.filter((p) => A.paths[p] !== B.paths[p]).map((p) => ({ path: p, from: A.paths[p], to: B.paths[p] }));
  const ok = (s: ObservabilityStatus | null) => s === null || s === 'SUFFICIENT';
  const opened = B.boundary.open.filter((c) => !A.boundary.open.includes(c)), closed = A.boundary.open.filter((c) => !B.boundary.open.includes(c));
  const address = (['A1', 'A2'] as const).filter((n) => addrText(A.address[n]) !== addrText(B.address[n])).map((n) => ({ target: n, from: addrText(A.address[n]), to: addrText(B.address[n]) }));
  const sss = JSON.stringify(A.sss) !== JSON.stringify(B.sss);
  const arena = A.boundary.arenaRadius !== B.boundary.arenaRadius ? ([A.boundary.arenaRadius, B.boundary.arenaRadius] as [number | null, number | null]) : null;
  return {
    from: a.label, to: b.label, status: [A.operational, B.operational], observed: [A.observed, B.observed], observability: [A.observability, B.observability],
    observabilityChange: ok(A.observability) && !ok(B.observability) ? 'lost' : !ok(A.observability) && ok(B.observability) ? 'gained' : 'unchanged',
    components, paths, boundary: { opened, closed, arenaRadius: arena }, address, sss,
    changedCount: components.length + paths.length + opened.length + closed.length + address.length + (arena ? 1 : 0) + (sss ? 1 : 0) + (A.operational !== B.operational ? 1 : 0),
  };
}

/** The three comparison ticks of a record: baseline (just before the first intervention), intervention (the collapse, or ten ticks after the first intervention), recovered (the end of the recovery sequence). */
export function snapshotTicks(rec: MeosRecord): { baseline: number; intervention: number; recovered: number } {
  const last = rec.frames.length - 1, first = rec.intervention_log[0]?.tick ?? Math.min(60, last);
  const collapse = rec.status_log.find((s) => s.label === 'COLLAPSED')?.tick ?? null;
  const recovery = collapse === null ? null : rec.status_log.find((s) => s.label === 'ACTIVE' && s.tick > collapse)?.tick ?? null;
  return { baseline: Math.max(0, first - 1), intervention: Math.min(last, collapse ?? first + 10), recovered: Math.min(last, recovery !== null ? recovery + RECOVERY_TICKS : last) };
}

