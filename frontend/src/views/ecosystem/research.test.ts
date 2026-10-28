// XENO ECOSYSTEM, fourth stage — the research readings are pure functions of the record: event markers, the state shown on inspection, snapshots and their differences, the mechanical
// reading of SSS and the M2 tap. The fixture is the stage-two record (collapse 149, recovery 161, pulse 151, Address fragmentation 200-225).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { MeosRecord, Observed, PathActivity } from './meosApi';
import { deltaSnapshots, eventMarkers, inspectAt, m2TapState, openComponents, pathStatesAt, snapshotTicks, sssMechanics, type Snapshot } from './research';

const rec = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'meos-stage2.json'), 'utf8')) as MeosRecord;
const observed = (failFrom: number, failTo: number): Observed => ({
  observation: {}, observed_cycles: 0, true_cycles: 0, observed_status: 'ACTIVE', true_status: 'ACTIVE', agrees: false, observed_trajectory: [], operational_state: 'ACTIVE', observed_state: 'COLLAPSED',
  observability_status: 'x', limiting_parameters: [], observability: { status: 'INSUFFICIENT_TEMPORAL_RESOLUTION', limiting_parameters: ['sampling_interval'], legacy_status: 'x', observed_collapse_is_operational: false, observed_collapse_is_artifact: true },
  timeline: rec.frames.map((f, t) => ({ t, operational: f.status, observed: t >= failFrom && t <= failTo ? 'COLLAPSED' : f.status, observability: t >= failFrom && t <= failTo ? 'INSUFFICIENT_TEMPORAL_RESOLUTION' : 'SUFFICIENT', limiting: t >= failFrom && t <= failTo ? ['sampling_interval'] : [] })),
});
const paths = { coupling: { label: '', components: [], means: '', signal_name: '', peak: 1, mean: 1, active_ticks: 0, cut_ticks: 0, series: [], state_intervals: [{ from: 0, to: 99, state: 'active' }, { from: 100, to: 149, state: 'cut' }, { from: 150, to: 359, state: 'active' }] } } as unknown as PathActivity;

describe('event markers', () => {
  const obs = observed(30, 40), m = eventMarkers(rec, obs);
  it('has a marker for every intervention, of its kind', () => {
    expect(m.filter((x) => ['intervention', 'boundary', 'address', 'pulse'].includes(x.kind)).length).toBeGreaterThanOrEqual(rec.intervention_log.length);
    expect(m.find((x) => x.tick === 100)!.kind).toBe('boundary');  // ISOLATE interaction_channel
    expect(m.find((x) => x.tick === 151)!.kind).toBe('pulse');
    expect(m.find((x) => x.tick === 200)!.kind).toBe('address');
  });
  it('marks the collapse and the recovery at the ticks the status log gives', () => {
    expect(m.find((x) => x.kind === 'collapse')!.tick).toBe(149);
    expect(m.find((x) => x.kind === 'recovery')!.tick).toBe(161);
  });
  it('marks the start of an observation failure and says the run itself is unchanged', () => {
    const f = m.find((x) => x.kind === 'observation-failure')!;
    expect(f.tick).toBe(30); expect(f.detail).toContain('until tick 40'); expect(f.detail).toContain('run itself is unchanged');
  });
  it('is sorted by tick and has no observation marker without an observation', () => {
    expect(m.map((x) => x.tick)).toEqual([...m.map((x) => x.tick)].sort((a, b) => a - b));
    expect(eventMarkers(rec, null).some((x) => x.kind === 'observation-failure')).toBe(false);
  });
});

describe('inspection', () => {
  const mk = eventMarkers(rec, observed(30, 40));
  it('separates operational, observed and observability state', () => {
    const a = inspectAt(rec, observed(30, 40), 35, paths, mk), b = inspectAt(rec, observed(30, 40), 60, paths, mk);
    expect(a.operational).toBe('ACTIVE'); expect(a.observed).toBe('COLLAPSED'); expect(a.observability).toBe('INSUFFICIENT_TEMPORAL_RESOLUTION'); expect(a.limiting).toEqual(['sampling_interval']);
    expect(b.observed).toBe('ACTIVE'); expect(b.observability).toBe('SUFFICIENT');
  });
  it('reads the cut coupling, the Address Domain fault and the pulse from the record', () => {
    expect(inspectAt(rec, null, 120, paths).boundary.open).toEqual(['interaction_channel']);
    expect(inspectAt(rec, null, 160, paths).boundary.open).toEqual([]);
    expect(inspectAt(rec, null, 210, paths).address.A2.mode).toBe('fragment');
    expect(inspectAt(rec, null, 230, paths).address.A2.mode).toBeNull();
    expect(inspectAt(rec, null, 120, paths).paths.coupling).toBe('cut');
    expect(inspectAt(rec, null, 160, paths).paths.coupling).toBe('active');
  });
  it('lists the markers at the inspected tick and gives energy, resource and history', () => {
    const i = inspectAt(rec, null, 100, paths, mk);
    expect(i.markers.some((x) => x.kind === 'boundary')).toBe(true);
    expect(i.energy.power).toBeGreaterThan(0); expect(i.resource.total).toBeGreaterThan(0); expect(i.history.trace.A1).toBeGreaterThanOrEqual(0);
  });
  it('finds a stale or delayed address by the cell it still names', () => {
    const fake = { ...rec, frames: rec.frames.map((f, t) => (t === 50 ? { ...f, address: { A1: { mode: 'delayed', integrity: 0, at: [3, 6] as [number, number] }, A2: { mode: null, integrity: 1 } } } : f)) } as MeosRecord;
    expect(inspectAt(fake, null, 50, null).address.A1.names).toEqual([3, 6]);
  });
  it('knows which components are open at a tick', () => {
    expect(openComponents(rec, 99)).toEqual([]); expect(openComponents(rec, 100)).toEqual(['interaction_channel']); expect(openComponents(rec, 150)).toEqual([]);
  });
});

describe('snapshots', () => {
  it('chooses the baseline, intervention and recovered ticks from the record', () => {
    const t = snapshotTicks(rec);
    expect(t.baseline).toBe(99); expect(t.intervention).toBe(149); expect(t.recovered).toBeGreaterThan(161);
  });
  const snap = (label: string, tick: number, parts: Record<string, 'active' | 'cut' | 'idle'>): Snapshot => ({ label, tick, inspect: inspectAt(rec, observed(140, 160), tick, paths), parts });
  it('reports the components, paths, boundary, address and observability that changed', () => {
    const a = snap('baseline', 99, { 'cable.BCb': 'active', A1: 'idle' }), b = snap('intervention', 149, { 'cable.BCb': 'cut', A1: 'idle' });
    const d = deltaSnapshots(a, b);
    expect(d.components).toEqual([{ id: 'cable.BCb', from: 'active', to: 'cut' }]);
    expect(d.paths).toEqual([{ path: 'coupling', from: 'active', to: 'cut' }]);
    expect(d.boundary.opened).toEqual(['interaction_channel']); expect(d.boundary.closed).toEqual([]);
    expect(d.observabilityChange).toBe('lost'); expect(d.status).toEqual(['ACTIVE', 'COLLAPSED']);
    const back = deltaSnapshots(b, snap('recovered', 185, { 'cable.BCb': 'active', A1: 'idle' }));
    expect(back.boundary.closed).toEqual(['interaction_channel']); expect(back.observabilityChange).toBe('gained');
  });
  it('is empty between a snapshot and itself', () => {
    const a = snap('a', 99, { A1: 'idle' });
    expect(deltaSnapshots(a, a).changedCount).toBe(0);
  });
  it('reports an Address Domain change', () => {
    const d = deltaSnapshots(snap('a', 199, {}), snap('b', 210, {}));
    expect(d.address).toHaveLength(1); expect(d.address[0].target).toBe('A2'); expect(d.address[0].to).toContain('fragment');
  });
});

describe('path states', () => {
  it('reads the state of each path at a tick from its intervals', () => {
    expect(pathStatesAt(paths, 120).coupling).toBe('cut'); expect(pathStatesAt(paths, 5).coupling).toBe('active'); expect(pathStatesAt(null, 5).resource).toBe('quiet');
  });
});

describe('SSS as mechanics (a visual representation rule)', () => {
  it('is neutral at the default setting and moves each mechanical quantity with its own parameter', () => {
    const d = sssMechanics({ scale: 1, size: 1, speed: 1 });
    expect(d).toEqual({ boomPreload: 0, ringTilt: 0, couplingTension: 0.5, archiveAjar: 0, regulation: 0 });
    expect(sssMechanics({ scale: 2, size: 1, speed: 1 }).boomPreload).toBeGreaterThan(0);
    expect(sssMechanics({ scale: 1, size: 0.5, speed: 1 }).ringTilt).toBeLessThan(0);
    expect(sssMechanics({ scale: 1, size: 1, speed: 2 }).couplingTension).toBeGreaterThan(0.5);
    expect(sssMechanics({ scale: 2, size: 1, speed: 1 }).couplingTension).toBe(0.5);  // each parameter drives its own quantity
  });
  it('leaves the archive latch ajar in regions that are not stably active, and shut in the others', () => {
    const s = { scale: 1, size: 1, speed: 1 };
    expect(sssMechanics(s, 'METASTABLE').archiveAjar).toBeGreaterThan(0); expect(sssMechanics(s, 'RECOVERY-CAPABLE').archiveAjar).toBeGreaterThan(sssMechanics(s, 'METASTABLE').archiveAjar);
    expect(sssMechanics(s, 'ACTIVE').archiveAjar).toBe(0); expect(sssMechanics(s, 'OBSERVATION-SENSITIVE').archiveAjar).toBe(0);
  });
  it('bounds every quantity', () => {
    const m = sssMechanics({ scale: 4, size: 4, speed: 4 }, 'METASTABLE');
    expect(Math.abs(m.boomPreload)).toBeLessThanOrEqual(1); expect(Math.abs(m.ringTilt)).toBeLessThanOrEqual(0.2); expect(m.couplingTension).toBeLessThanOrEqual(1);
  });
});

describe('the M2 tap', () => {
  it('is absent when M2 is not connected', () => { expect(m2TapState(rec, 100)).toEqual({ configured: false, sense: 'none', sensed: 0, state: null }); });
  it('follows the recorded M2 term: lit while A1 senses it, extended when it does not, retracted when the run is collapsed, trembling for a noisy tap', () => {
    const base = { ...rec, config: { ...rec.config, m2: { sense: 'direct' as const, weight: 1 } }, traces: { ...rec.traces, m2_sensed: rec.frames.map((_, t) => (t % 2 ? 0.3 : 0)) } } as MeosRecord;
    expect(m2TapState(base, 11).state).toBe('sampling'); expect(m2TapState(base, 10).state).toBe('extended'); expect(m2TapState(base, 150).state).toBe('retracted');
    expect(m2TapState({ ...base, config: { ...base.config, m2: { sense: 'noisy' as const } } } as MeosRecord, 11).state).toBe('overloaded');
  });
});
