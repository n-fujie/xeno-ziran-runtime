// XENO ECOSYSTEM, fifth stage — the route topology read from a record. The fixture is a controlled run made by the backend (adaptive reconfiguration against a weakened coupling, a hand-made
// two-route library whose second route needs the M2 tap, history removed at tick 100): the TypeScript reading must agree with the Python one on the same record, and everything drawn must
// come from the record, the library and the path definitions.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { MeosRecord } from './meosApi';
import { eventMarkers, inspectAt, MARKER_COLOR } from './research';
import { buildResearchMap, DEFAULT_MAP_LAYERS, MAP_LAYERS, type MapLayer, type Prim } from './researchMap';
import { COMPONENTS5, PATHS5, routeGraph, topologyAt, topologyOf, type LibraryMfs, type Outcome, type Topology } from './routeGraph';
import { visibleEdge, type RouteToggle } from './routeGraphDraw';

const fx = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'meos-stage5-controlled.json'), 'utf8')) as { record: MeosRecord; topology: Topology; library: LibraryMfs[]; outcomes: Outcome[] };
const topo = topologyOf(fx.record as never);

describe('the topology of a record', () => {
  it('agrees with the backend reading of the same record', () => {
    for (const k of ['universe', 'component_timeline', 'installed_m2_tap', 'failed_components', 'failure_intervals', 'route_events', 'transitions', 'decisions', 'initial_mfs', 'paths', 'controller', 'last_tick'] as const) expect(topo[k], k).toEqual(fx.topology[k]);
  });
  it('knows when each component was enabled, cut or switched on', () => {
    expect(topo.component_timeline.history).toEqual([[0, true], [100, false]]);
    expect(topo.component_timeline.m2_tap[0]).toEqual([0, false]); expect(topo.component_timeline.m2_tap[1][1]).toBe(true);
    expect(topo.failure_intervals).toEqual([{ component: 'history', op: 'REMOVE', from: 100, to: null }]);
    expect(topo.route_events.filter((e) => e.controlled)).toHaveLength(1);
  });
});

describe('the routes at a tick', () => {
  const sw = topo.transitions[0].tick;
  it('before the stress: history enabled, the M2 tap installed and dormant, the M2 path dormant, the current MFS the base one', () => {
    const s = topologyAt(topo, 80, fx.library);
    expect(s.enabled).toContain('history'); expect(s.dormant).toEqual(['m2_tap']); expect(s.paths.m2).toBe('dormant'); expect(s.paths.history_access).toBe('active'); expect(s.failed).toEqual([]);
    expect(s.currentMfs).toBe('L-BASE');
  });
  it('after the stress and before the switch: the history path has failed and the history-needing routes are closed', () => {
    const s = topologyAt(topo, sw - 1, fx.library);
    expect(s.failed).toEqual(['history']); expect(s.paths.history_access).toBe('failed');
  });
  it('after the switch: the M2 path is a fallback, the current MFS is the destination, the transition and its trigger are known', () => {
    const s = topologyAt(topo, sw + 5, fx.library);
    expect(s.paths.m2).toBe('fallback'); expect(s.currentMfs).toBe('L-WEAK'); expect(s.dormant).toEqual([]);
    expect(s.lastTransition).toMatchObject({ tick: sw, to: 'L-WEAK', cost: 1 }); expect(s.lastTransition!.trigger).toContain('coupling');
    expect(s.alternative.map((m) => m.id)).toEqual(['L-BASE']);
  });
  it('closes a library route when a component it needs has failed', () => {
    const lib: LibraryMfs[] = [...fx.library, { id: 'NEEDS-HISTORY', condition_id: 'X', condition: 'x', features: {}, retained: ['A2', 'history'], removed: [], cardinality: 2, route_kind: '', retained_paths: [], lost_paths: [], digest: '' }];
    const s = topologyAt(topo, sw - 1, lib);
    expect(s.disabled.map((d) => d.mfs.id)).toEqual(['NEEDS-HISTORY']); expect(s.disabled[0].because).toEqual(['history']); expect(s.available.map((m) => m.id)).not.toContain('NEEDS-HISTORY');
  });
});

describe('the route graph', () => {
  const g = routeGraph(topo, fx.library, 200);
  it('has a node for every component and an edge only where a path, a transition or a library membership says so', () => {
    expect(g.nodes.filter((n) => n.kind === 'component').map((n) => n.id)).toEqual([...COMPONENTS5]);
    for (const e of g.edges.filter((x) => x.kind === 'path')) { expect(PATHS5[e.path!]).toContain(e.from); expect(PATHS5[e.path!]).toContain(e.to); }
    for (const e of g.edges.filter((x) => x.kind === 'membership')) expect(fx.library.find((m) => m.id === e.from)!.retained).toContain(e.to);
    const rc = g.edges.filter((x) => x.kind === 'reconfiguration'); expect(rc).toHaveLength(topo.transitions.length); expect(rc[0].label).toContain('cost 1');
  });
  it('shows no transition before it happened', () => {
    expect(routeGraph(topo, fx.library, topo.transitions[0].tick - 1).edges.filter((x) => x.kind === 'reconfiguration')).toHaveLength(0);
  });
  it('is switched by the nine toggles', () => {
    const all = new Set<RouteToggle>(['active', 'dormant', 'failed', 'fallback', 'reconfiguration', 'mfs', 'address', 'history', 'm2', 'resource']);
    const shown = (on: Set<RouteToggle>) => g.edges.filter((e) => visibleEdge(e, on)).length;
    expect(shown(all)).toBeGreaterThan(shown(new Set<RouteToggle>(['active'])));
    const noM2 = new Set(all); noM2.delete('m2'); expect(g.edges.filter((e) => visibleEdge(e, noM2) && e.path === 'm2')).toHaveLength(0);
    const noRecon = new Set(all); noRecon.delete('reconfiguration'); expect(g.edges.filter((e) => visibleEdge(e, noRecon) && e.kind === 'reconfiguration')).toHaveLength(0);
    expect(g.edges.filter((e) => visibleEdge(e, new Set<RouteToggle>()))).toHaveLength(0);
  });
});

describe('replay markers of the routes', () => {
  const m = eventMarkers(fx.record, null, { topology: topo, outcomes: fx.outcomes });
  it('marks history loss, the route switch, the M2 takeover, the MFS change and the failed reconfiguration', () => {
    const kinds = new Set(m.map((x) => x.kind));
    for (const k of ['history-loss', 'route-switch', 'm2-takeover', 'mfs-change', 'route-failed'] as const) expect(kinds.has(k), k).toBe(true);
    expect(fx.outcomes[0].preserved_at_end).toBe(false);  // the run ended COLLAPSED: the reconfiguration failed, and is marked as failed, not as a success
    expect(m.find((x) => x.kind === 'mfs-change')!.detail).toContain('cost 1');
    expect(m.find((x) => x.kind === 'm2-takeover')!.tick).toBe(topo.transitions[0].tick + 1);  // the controller acted at tick t; the engine applies the injected intervention at t + 1
    for (const k of kinds) expect(MARKER_COLOR[k]).toBeTruthy();
  });
  it('marks a successful reconfiguration as such and an Address recovery', () => {
    const ok = eventMarkers(fx.record, null, { topology: topo, outcomes: [{ ...fx.outcomes[0], preserved_at_end: true }] });
    expect(ok.some((x) => x.kind === 'route-ok')).toBe(true);
    const rec2 = { ...fx.record, intervention_log: [...fx.record.intervention_log, { tick: 150, op: 'ADDRESS', event: 0, target: 'A2', address_mode: 'restore' }] } as MeosRecord;
    expect(eventMarkers(rec2).some((x) => x.kind === 'address-recovery' && x.tick === 150)).toBe(true);
  });
  it('carries the route state into the inspection', () => {
    const s = topologyAt(topo, 200, fx.library);
    const ins = inspectAt(fx.record, null, 200, null, m, s);
    expect(ins.route!.currentMfs).toBe('L-WEAK'); expect(ins.route!.lastTransition!.trigger).toContain('coupling');
    expect(inspectAt(fx.record, null, 200, null).route).toBeNull();
  });
});

describe('the research map routes', () => {
  const t = topo.transitions[0].tick + 5, route = topologyAt(topo, t, fx.library), ins = inspectAt(fx.record, null, t, null, [], route);
  const map = (layers: Set<MapLayer>) => buildResearchMap({ rec: fx.record, tick: t, obs: {}, inspect: ins, paths: null, markers: [], layers, route }).prims;
  const ids = (p: Prim[], id: string) => p.filter((x) => x.id === id);
  it('keeps the route layers off by default (they are not all shown at once)', () => {
    expect(DEFAULT_MAP_LAYERS.has('route.fallback')).toBe(false); expect(DEFAULT_MAP_LAYERS.has('mfs.current')).toBe(false); expect(MAP_LAYERS.some((l) => l.id === 'route.fallback')).toBe(true);
    expect(buildResearchMap({ rec: fx.record, tick: t, obs: {}, inspect: ins, paths: null, markers: [], route }).prims.some((p) => p.id.startsWith('route.') || p.id.startsWith('mfs.'))).toBe(false);
  });
  it('draws the fallback and the failed route when their layers are on, and the current and alternative MFS in words', () => {
    const on = new Set<MapLayer>(['route.fallback', 'route.failed', 'route.dormant', 'route.active', 'mfs.current', 'mfs.alternative']);
    const p = map(on);
    expect(ids(p, 'route.fallback').some((x) => x.t === 'text' && x.text.includes('m2 route fallback'))).toBe(true);
    expect(ids(p, 'route.failed').some((x) => x.t === 'text' && x.text.includes('history_access route failed'))).toBe(true);
    expect(ids(p, 'route.failed').some((x) => x.t === 'cross')).toBe(true);
    expect((ids(p, 'mfs.current')[0] as Extract<Prim, { t: 'text' }>).text).toContain('current MFS L-WEAK');
    expect((ids(p, 'mfs.alternative')[0] as Extract<Prim, { t: 'text' }>).text).toContain('L-BASE');
  });
  it('removes a route layer when it is switched off', () => {
    const p = map(new Set<MapLayer>(['route.fallback']));
    expect(ids(p, 'route.failed')).toHaveLength(0); expect(ids(p, 'route.fallback').length).toBeGreaterThan(0);
  });
});
