// XENO ECOSYSTEM, sixth stage — the repair of a run, read from the data the backend returns: the fixtures are real repair blocks produced by the engine (a pulse that recovers, a pulse that overshoots, a temporary bridge, a controller's decision, a stress with no available action, a repair after the collapse).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { RepairBlock, StressRow } from './meosApi';
import { failureOf, recoveryStrip, repairMarkers, repairStateAt, windowText } from './repair';
import { MARKER_COLOR, MARKER_LABEL } from './research';
import { buildResearchMap, MAP_LAYERS, type MapLayer, type Prim } from './researchMap';
import { inspectAt } from './research';
import { repairFigureItems } from './repairFigureDraw';
import type { MeosRecord } from './meosApi';

const ctl = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'meos-stage5-controlled.json'), 'utf8')) as { record: MeosRecord };
const fx = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'meos-stage6-repair.json'), 'utf8')) as Record<'recovered' | 'overshoot' | 'bridge' | 'controller' | 'no_action_available' | 'late_recovery', RepairBlock>;

describe('markers', () => {
  it('has one marker per event, with a kind, a colour and a label, and says where each event comes from', () => {
    for (const rb of Object.values(fx)) for (const m of repairMarkers(rb)) { expect(MARKER_COLOR[m.kind]).toBeTruthy(); expect(MARKER_LABEL[m.kind]).toBeTruthy(); expect(m.detail).toMatch(/\[[^\]]+\]$/); }
    expect(repairMarkers(fx.recovered).map((m) => m.kind)).toEqual(['stress-onset', 'repair-action', 'partial-recovery']);
    expect(repairMarkers(null)).toEqual([]);
  });
  it('shows the overshoot, the secondary collapse and the irreversible threshold of a pulse that was too large', () => {
    const k = repairMarkers(fx.overshoot).map((m) => m.kind);
    expect(k).toEqual(expect.arrayContaining(['overshoot', 'secondary-collapse', 'irreversible', 'collapse']));
  });
  it('shows a controller decision before its action, and a detected stress with no available action as a failed repair, not as nothing', () => {
    const c = repairMarkers(fx.controller); expect(c.findIndex((m) => m.kind === 'repair-decision')).toBeLessThan(c.findIndex((m) => m.kind === 'repair-action'));
    const n = repairMarkers(fx.no_action_available); expect(n.find((m) => m.kind === 'repair-failed')?.label).toBe('NO ACTION AVAILABLE');
  });
  it('shows a repair after the collapse as a full recovery', () => {
    const k = repairMarkers(fx.late_recovery).map((m) => m.kind); expect(k.indexOf('collapse')).toBeLessThan(k.indexOf('repair-action')); expect(k).toContain('full-recovery');
  });
});

describe('the state of the repair at a tick', () => {
  it('is intact before the stress, damaged after it, and repaired after a sustained recovery', () => {
    expect(repairStateAt(fx.recovered, 99)!.damagedPath).toBeNull();
    expect(repairStateAt(fx.recovered, 105)!.paths.coupling).toBe('damaged');
    const mid = repairStateAt(fx.recovered, 120)!; expect(mid.paths.resource).toBe('repair-active'); expect(mid.repairSiteDiffers).toBe(true);  // the repair site (the resource) is not the damage site (the coupling)
    const end = repairStateAt(fx.recovered, 400)!; expect(end.paths.coupling).toBe('repaired'); expect(end.recovered).toBe(true);
  });
  it('shows a failed path after a secondary collapse and keeps the overshoot', () => {
    const end = repairStateAt(fx.overshoot, 479)!; expect(end.paths.coupling).toBe('failed'); expect(end.secondary).toBe(true); expect(end.recovered).toBe(false); expect(end.irreversible).toBe(true);
  });
  it('shows a temporary action as a bypass only while it lasts', () => {
    const during = repairStateAt(fx.bridge, 110)!, after = repairStateAt(fx.bridge, 140)!;
    expect(during.paths.coupling).not.toBe('bypass');  // the bridge acts on the damaged path itself: the damaged path's own state wins
    expect(during.worldActions).toHaveLength(1); expect(after.lastAction?.action).toBe('coupling.bridge');
  });
  it('separates a world-state repair from an internal reconfiguration', () => {
    const s = repairStateAt(fx.controller, 130)!; expect(s.internalActions.map((a) => a.action)).toEqual(['internal.m2_tap']); expect(s.worldActions).toEqual([]);
    expect(repairStateAt(fx.recovered, 130)!.internalActions).toEqual([]);
  });
});

describe('failure class', () => {
  it('names why a run did not recover, in the taxonomy of the experiments', () => {
    expect(failureOf(fx.recovered)).toBeNull();
    expect(failureOf(fx.overshoot)!.id).toBe('OVERSHOOT');  // a pulse of 4.0 (3.0 or more) followed by a secondary collapse
    expect(failureOf(fx.bridge)!.id).toBe('SECONDARY_COLLAPSE');  // a temporary bridge followed by a secondary collapse is not an overshoot
    expect(failureOf(fx.no_action_available)!.id).toBe('OUTSIDE_TESTED_ACTION_SPACE');
  });
});

describe('the reachable-recovery strip', () => {
  const row = { internal_reconfiguration: { effective: true, windows: [[101, 113]] }, world_single: { effective: false, windows: [] }, combined: { effective: true, windows: [[114, 120], [130, 131]] } } as unknown as StressRow;
  it('has one cell per tick and labels each tick by what recovers it, a gap as none', () => {
    const s = recoveryStrip(row); expect(s).toHaveLength(230); expect(s[0]).toEqual({ tick: 101, classes: ['internal'] });
    expect(s.find((c) => c.tick === 115)!.classes).toEqual(['combined']); expect(s.find((c) => c.tick === 125)!.classes).toEqual(['none']); expect(s.find((c) => c.tick === 130)!.classes).toEqual(['combined']);
  });
  it('writes the fragments of a window as they are, a gap being a gap', () => { expect(windowText([[101, 109], [131, 133], [135, 135]])).toBe('101-109, 131-133, 135'); expect(windowText([])).toBe('none'); });
});

describe('the research map and the technical figure', () => {
  it('has the repair layers, off by default', () => {
    for (const id of ['repair.damaged', 'repair.repairable', 'repair.repaired', 'repair.bypass', 'repair.world', 'repair.internal', 'repair.failed']) expect(MAP_LAYERS.some((l) => l.id === id)).toBe(true);
  });
  it('draws the damaged path and the repair site only from the run\'s repair state, each in its own layer, and nothing when the layers are off', () => {
    const rec = ctl.record, t = 120, ins = inspectAt(rec, null, t, null, [], null), state = repairStateAt(fx.recovered, t)!;
    const prims = (layers: Set<MapLayer>) => buildResearchMap({ rec, tick: t, obs: {}, inspect: ins, paths: null, markers: [], layers, repair: { state, repairable: true } }).prims;
    const ids = (p: Prim[], id: string) => p.filter((x) => x.id === id);
    const on = prims(new Set<MapLayer>(['repair.damaged', 'repair.world', 'repair.repairable']));
    expect(ids(on, 'repair.world').some((x) => x.t === 'text' && x.text.includes('resource.pulse'))).toBe(true);  // the world-state action, with its action id
    expect(ids(on, 'repair.world').some((x) => x.t === 'text' && x.text.includes('the repair site is not the damage site'))).toBe(true);
    expect(prims(new Set<MapLayer>(['repair.repaired'])).filter((x) => x.id.startsWith('repair.'))).toHaveLength(0);  // at tick 120 nothing is repaired yet
    expect(prims(new Set<MapLayer>()).filter((x) => x.id.startsWith('repair.'))).toHaveLength(0);
    const end = repairStateAt(fx.recovered, 400)!;
    const done = buildResearchMap({ rec, tick: t, obs: {}, inspect: ins, paths: null, markers: [], layers: new Set<MapLayer>(['repair.repaired', 'repair.failed']), repair: { state: end } }).prims;
    expect(ids(done, 'repair.repaired').some((x) => x.t === 'text' && x.text.includes('coupling repaired'))).toBe(true);
    const failed = buildResearchMap({ rec, tick: t, obs: {}, inspect: ins, paths: null, markers: [], layers: new Set<MapLayer>(['repair.failed']), repair: { state: repairStateAt(fx.overshoot, 479)! } }).prims;
    expect(ids(failed, 'repair.failed').some((x) => x.t === 'text' && x.text.includes('SECONDARY COLLAPSE'))).toBe(true);
    const inter = buildResearchMap({ rec, tick: t, obs: {}, inspect: ins, paths: null, markers: [], layers: new Set<MapLayer>(['repair.internal', 'repair.world']), repair: { state: repairStateAt(fx.controller, 130)! } }).prims;
    expect(ids(inter, 'repair.internal').some((x) => x.t === 'text' && x.text.includes('internal.m2_tap'))).toBe(true); expect(ids(inter, 'repair.world').filter((x) => x.t === 'text')).toHaveLength(0);  // an internal reconfiguration is not a world-state repair
  });
  it('lists, in the technical figure, the nodes, the stress, each action that has happened with its tick, magnitude and class, and the result', () => {
    const it = repairFigureItems(fx.controller, repairStateAt(fx.controller, 130)!);
    expect(it.filter((i) => i.kind === 'node')).toHaveLength(7);
    expect(it.find((i) => i.kind === 'action')!.label).toContain('internal.m2_tap'); expect(it.find((i) => i.kind === 'action')!.label).toContain('[internal]');
    expect(it.find((i) => i.kind === 'stress')!.label).toContain('history lost'); expect(it.find((i) => i.id === 'result')!.label).toContain('long prevented');
    expect(repairFigureItems(fx.recovered, repairStateAt(fx.recovered, 50)!).some((i) => i.kind === 'action')).toBe(false);  // no repair has happened at tick 50: none is drawn
  });
});
