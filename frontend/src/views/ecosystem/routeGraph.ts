// XENO ECOSYSTEM, fifth stage — the route topology of a run, read from its record: when each component was enabled or cut, the route changes (ROUTE operations, with whatever a
// controller recorded in them), the transitions between MFS, and the graph drawn from them. Pure functions: nothing here is drawn that the record (or the saved MFS library) does not
// contain. ``topologyOf`` is the same reading as ``backend/xzr/meos/routes5.py::topology`` (a parity test compares them on a stored controlled run).
import type { MeosRecord } from './meosApi';

export const COMPONENTS5 = ['A2', 'resource_gradient', 'history', 'interaction_channel', 'sensor_resource', 'sensor_alteration', 'environmental_persistence', 'feedback', 'resource_renewal', 'm2_tap'] as const;
export type Component = (typeof COMPONENTS5)[number];
/** The operational paths and the components each is made of (the M2 path and the address path exist from the fifth stage). */
export const PATHS5: Record<string, string[]> = {
  resource: ['resource_gradient', 'feedback', 'resource_renewal'], coupling: ['interaction_channel'], history_access: ['history'], observation: ['sensor_resource', 'sensor_alteration'],
  recovery: ['resource_renewal', 'feedback'], m2: ['m2_tap'], address: ['A1', 'A2'],
};
export interface McCard {
  preserved_operation: string | null; energy_use: number | null; resource_throughput: number | null; recovery_latency: number | null; perturbation_collapse_share: number | null; history_dependence: number | null; address_dependence: number | null;
  observational_robustness: number | null; sss_region: string | null; ranges_along_axes: Record<string, unknown> | null; operational_robustness: number | null; addressability: number | null; recoverability: number | null;
}
export interface SssPoint { scale: number; size: number; speed: number; region: string }
export interface LibraryMfs {
  id: string; condition_id: string; condition: string; features: Record<string, string>; retained: string[]; removed: string[]; cardinality: number; route_kind: string; retained_paths: string[]; lost_paths: string[]; digest: string;
  /** the profile of the saved results (absent in a minimal library) */ card?: McCard; sss_points?: SssPoint[]; seeds_discovered?: number[]; seeds_validated?: number[];
}
/** A candidate retaining set that was searched and did not become an MFS: it failed the search criterion, failed validation on the independent seeds, or was a near miss. Never drawn as an MFS. */
export interface RejectedCandidate {
  condition_id: string; retained: string[]; cardinality: number; status: string; found_by: string[]; search_seeds: number[]; persists_in_search_seeds: number; validation_seeds: number[]; persists_in_validation_seeds: number;
  per_validation_seed: boolean[]; discovered_in_search: boolean; survived_validation: boolean;
}
export interface RouteEvent { tick: number; m2: { sense?: string; weight?: number; delay?: number; noise?: number; threshold?: number } | null; history: string | null; why: string | null; from: string | null; to: string | null; cost: number | null; trigger: string | null; controlled: boolean }
export interface Transition { tick: number; from: string; to: string; cost: number; trigger: string[]; enabled: string[] }
export interface Topology {
  universe: string[]; component_timeline: Record<string, Array<[number, boolean]>>; installed_m2_tap: boolean; failed_components: Record<string, { op: string; tick: number }>; failure_intervals: Array<{ component: string; op: string; from: number; to: number | null }>; route_events: RouteEvent[];
  transitions: Transition[]; decisions: Array<Record<string, unknown>>; initial_mfs: string | null; paths: Record<string, string[]>; controller: string; last_tick: number;
}
export interface Outcome { tick: number; from: string; to: string; trigger: string[]; cost: number; enabled: string[]; state_at_switch: string; operation_lost_ticks_after: number; recovery_latency: number | null; preserved_at_end: boolean; stress_tick: number | null; changes_of_state_after: number }

type RecWithController = MeosRecord & { controller?: { kind: string; log: Array<Record<string, unknown>>; switches: number } };

/** The topology of a record (the reading of the backend, from the record alone). */
export function topologyOf(rec: RecWithController, universe: readonly string[] = COMPONENTS5): Topology {
  const cfg = rec.config as unknown as { m2?: { sense?: string }; history: { enabled: boolean }; environment: { gradient: boolean } };
  const on = new Set<string>(universe);
  if ((cfg.m2?.sense ?? 'none') === 'none') on.delete('m2_tap');
  if (!cfg.history.enabled) on.delete('history');
  if (!cfg.environment.gradient) on.delete('resource_gradient');
  const timeline: Record<string, Array<[number, boolean]>> = {};
  for (const c of universe) timeline[c] = [[0, on.has(c)]];
  const failed: Topology['failed_components'] = {}, events: RouteEvent[] = [], intervals: Topology['failure_intervals'] = [];
  let installed = on.has('m2_tap');
  for (const iv of rec.intervention_log as Array<Record<string, unknown> & { tick: number; op: string }>) {
    const t = iv.tick, op = iv.op, change: Array<[string, boolean]> = [];
    const target = iv.target as string | undefined;
    if ((op === 'REMOVE' || op === 'ISOLATE') && target && universe.includes(target)) { change.push([target, false]); failed[target] = { op, tick: t }; intervals.push({ component: target, op, from: t, to: null }); }
    else if (op === 'RECONNECT' && target && universe.includes(target)) { change.push([target, true]); delete failed[target]; for (const f of intervals) if (f.component === target && f.to === null) f.to = t; }
    else if (op === 'ROUTE') {
      const m2 = iv.m2 as RouteEvent['m2'] | undefined, hist = iv.history as string | undefined;
      if (m2) { installed = true; change.push(['m2_tap', (m2.sense ?? 'none') !== 'none']); }
      if (hist !== undefined) change.push(['history', hist === 'on']);
      events.push({ tick: t, m2: m2 ?? null, history: hist ?? null, why: (iv.why as string) ?? null, from: (iv.from as string) ?? null, to: (iv.to as string) ?? null, cost: (iv.cost as number) ?? null, trigger: (iv.trigger as string) ?? null, controlled: 'why' in iv });
    }
    for (const [c, state] of change) { const tl = timeline[c], last = tl[tl.length - 1]; if (last[1] !== state || last[0] !== t) tl.push([t, state]); }
  }
  const log = rec.controller?.log ?? [];
  const transitions = log.filter((e) => e.kind === 'switch').map((e) => ({ tick: e.tick as number, from: e.from as string, to: e.to as string, cost: e.cost as number, trigger: e.trigger as string[], enabled: e.enabled as string[] }));
  const decisions = log.filter((e) => e.kind === 'decide').map((e) => Object.fromEntries(['tick', 'trigger', 'current_mfs', 'candidates', 'chosen', 'outcome'].filter((k) => k in e).map((k) => [k, e[k]])));
  return { universe: [...universe], component_timeline: timeline, installed_m2_tap: installed, failed_components: failed, failure_intervals: intervals, route_events: events, transitions, decisions, initial_mfs: (decisions[0]?.current_mfs as string) ?? null,
    paths: Object.fromEntries(Object.entries(PATHS5).map(([k, v]) => [k, [...v]])), controller: rec.controller?.kind ?? 'none', last_tick: rec.frames.length - 1 };
}

export type PathRouteState = 'active' | 'dormant' | 'failed' | 'fallback' | 'adaptive' | 'absent';
export interface RouteState {
  tick: number; enabled: string[]; dormant: string[]; failed: string[]; paths: Record<string, PathRouteState>; currentMfs: string; alternative: LibraryMfs[]; available: LibraryMfs[]; disabled: Array<{ mfs: LibraryMfs; because: string[] }>; /** the ids this run is concerned with: the current MFS, those a controller considered or moved between, and the validated MFS of the current MFS's condition */ named: string[];
  lastTransition: Transition | null; lastEvent: RouteEvent | null; triggers: string[];
}
const enabledAt = (tl: Array<[number, boolean]>, t: number): boolean => { let v = tl[0][1]; for (const [k, s] of tl) if (k <= t) v = s; return v; };

/** The state of the routes at a tick: which components are enabled, dormant (the M2 tap that is installed and not in use) or failed (removed or isolated and not restored), the state of each path
 * (a path made of enabled components is active; one that needs the dormant tap is dormant; one with a failed component is failed; one that a controller switched on is a fallback), the current
 * MFS, and, against a library, the routes still open and the routes a failure has closed. */
export function topologyAt(topo: Topology, tick: number, library: LibraryMfs[] = []): RouteState {
  const t = Math.min(Math.max(0, tick), topo.last_tick);
  const enabled = topo.universe.filter((c) => enabledAt(topo.component_timeline[c], t));
  const failed = [...new Set(topo.failure_intervals.filter((f) => f.from <= t && (f.to === null || t < f.to)).map((f) => f.component))].filter((c) => !enabled.includes(c));
  const dormant = topo.installed_m2_tap && !enabled.includes('m2_tap') && !failed.includes('m2_tap') ? ['m2_tap'] : [];
  const switched = new Set<string>();
  for (const e of topo.route_events) if (e.tick <= t && e.controlled) { if (e.m2 && (e.m2.sense ?? 'none') !== 'none') switched.add('m2'); if (e.history === 'on') switched.add('history_access'); }
  const paths: Record<string, PathRouteState> = {};
  for (const [p, comps] of Object.entries(topo.paths)) {
    const known = comps.filter((c) => topo.universe.includes(c));
    if (!known.length) { paths[p] = 'active'; continue; }  // the address path: both configurations present
    paths[p] = known.some((c) => failed.includes(c)) ? 'failed' : known.every((c) => enabled.includes(c)) ? (switched.has(p) ? (topo.controller === 'fixed' ? 'fallback' : 'adaptive') : 'active') : known.every((c) => enabled.includes(c) || dormant.includes(c)) ? 'dormant' : 'absent';
  }
  let lastTransition: Transition | null = null;
  for (const tr of topo.transitions) if (tr.tick <= t) lastTransition = tr;
  let lastEvent: RouteEvent | null = null;
  for (const e of topo.route_events) if (e.tick <= t) lastEvent = e;
  const sameSet = (x: string[], y: string[]) => x.length === y.length && x.every((c) => y.includes(c));
  const known = topo.initial_mfs && topo.initial_mfs !== 'none' ? topo.initial_mfs : null;
  // the current MFS: the one the last transition moved to, else the one the run is known to be (a controller's first decision, or the MFS a deep link ran), else the library MFS whose retained
  // components are exactly the enabled ones; a run that is none of these is not an MFS (the full arrangement contains every MFS, so containment says nothing)
  const currentMfs = lastTransition ? lastTransition.to : (known ?? library.find((m) => sameSet(m.retained, enabled))?.id ?? 'none');
  const cur = library.find((m) => m.id === currentMfs);
  const ids = new Set<string>([currentMfs, ...topo.transitions.flatMap((x) => [x.from, x.to]), ...(cur ? library.filter((m) => m.condition_id === cur.condition_id).map((m) => m.id) : [])]);
  for (const d of topo.decisions) { for (const k of ['chosen', 'current_mfs'] as const) if (typeof d[k] === 'string') ids.add(d[k] as string); for (const c of (d.candidates as Array<{ mfs: string }> | undefined) ?? []) ids.add(c.mfs); }
  const named = [...ids].filter((id) => library.some((m) => m.id === id));
  const open = library.filter((m) => !m.retained.some((c) => failed.includes(c)));
  const closed = library.filter((m) => m.retained.some((c) => failed.includes(c))).map((m) => ({ mfs: m, because: m.retained.filter((c) => failed.includes(c)) }));
  return { tick: t, enabled, dormant, failed, paths, currentMfs, alternative: open.filter((m) => named.includes(m.id) && m.id !== currentMfs), available: open, disabled: closed, named, lastTransition, lastEvent, triggers: lastTransition?.trigger ?? [] };
}

export type EdgeKind = 'path' | 'reconfiguration' | 'membership' | 'candidate';
export interface GraphNode { id: string; label: string; kind: 'component' | 'mfs' | 'candidate'; state: 'enabled' | 'dormant' | 'failed' | 'disabled' | 'rejected'; x: number; y: number }
export interface GraphEdge { from: string; to: string; kind: EdgeKind; path?: string; state: PathRouteState | 'transition' | 'rejected'; label?: string }
export interface RouteGraph { nodes: GraphNode[]; edges: GraphEdge[] }

/** The graph drawn on the technical sheet: components as nodes (state from the record), an edge between the consecutive components of each path (state of the path), MFS nodes for the current MFS,
 * the alternatives and every MFS a recorded transition names, edges for the transitions (with their cost) and faint membership edges from the current and the alternative MFS to their
 * components. Every edge is derived from ``topo``, the library and PATHS5. */
export function routeGraph(topo: Topology, library: LibraryMfs[], tick: number, rejected: RejectedCandidate[] = []): RouteGraph {
  const st = topologyAt(topo, tick, library);
  const comp = topo.universe, nodes: GraphNode[] = [], edges: GraphEdge[] = [];
  comp.forEach((c, i) => nodes.push({ id: c, label: c, kind: 'component', state: st.failed.includes(c) ? 'failed' : st.enabled.includes(c) ? 'enabled' : st.dormant.includes(c) ? 'dormant' : 'disabled', x: i / Math.max(1, comp.length - 1), y: 0.78 }));
  for (const [p, comps] of Object.entries(topo.paths)) {
    const known = comps.filter((c) => comp.includes(c));
    for (let i = 0; i + 1 < known.length; i++) edges.push({ from: known[i], to: known[i + 1], kind: 'path', path: p, state: st.paths[p] });
    if (known.length === 1) edges.push({ from: known[0], to: known[0], kind: 'path', path: p, state: st.paths[p] });
  }
  const named = new Set<string>([st.currentMfs, ...st.alternative.map((m) => m.id), ...st.disabled.map((d) => d.mfs.id).filter((id) => st.named.includes(id)), ...topo.transitions.flatMap((t) => [t.from, t.to])]);
  const mfsList = [...named].filter((id) => id !== 'none' && id !== 'fixed fallback');
  mfsList.forEach((id, i) => { const m = library.find((x) => x.id === id); nodes.push({ id, label: id, kind: 'mfs', state: id === st.currentMfs ? 'enabled' : m && m.retained.some((c) => st.failed.includes(c)) ? 'failed' : 'dormant', x: (i + 0.5) / mfsList.length, y: 0.16 }); });
  for (const tr of topo.transitions) if (tr.tick <= tick) edges.push({ from: tr.from, to: tr.to, kind: 'reconfiguration', state: 'transition', label: `t${tr.tick} cost ${tr.cost}` });
  for (const id of mfsList) { const m = library.find((x) => x.id === id); if (m) for (const c of m.retained) if (comp.includes(c)) edges.push({ from: id, to: c, kind: 'membership', state: id === st.currentMfs ? 'active' : 'dormant' }); }
  // the candidate sets that were searched and rejected, for the conditions of the MFS shown: dotted nodes and dotted membership edges, labelled as candidates (never drawn as MFS)
  const conds = new Set(mfsList.map((id) => library.find((x) => x.id === id)?.condition_id).filter(Boolean));
  const shown = rejected.filter((c) => conds.has(c.condition_id));
  shown.forEach((c, i) => {
    const id = `candidate ${c.condition_id}-${i + 1}`;
    nodes.push({ id, label: `${id} (not MFS)`, kind: 'candidate', state: 'rejected', x: (i + 0.5) / Math.max(1, shown.length), y: 0.46 });
    for (const k of c.retained) if (comp.includes(k)) edges.push({ from: id, to: k, kind: 'candidate', state: 'rejected' });
  });
  return { nodes, edges };
}
