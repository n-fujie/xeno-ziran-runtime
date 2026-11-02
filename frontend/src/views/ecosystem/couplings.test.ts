// XENOSCIENCE ECOSYSTEM — couplings and branch comparison, from real engine records: the baseline run and the run with the interaction channel isolated at tick 100 and restored at 150
// (horizon 360, seed 1), plus a run with feedback isolated at 100. The fixture is the engine output with the field stream and traces removed (meos-coupling-cut.json).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { MeosRecord } from './meosApi';
import { COUPLINGS, baselinePositions, compareBranches, couplingDef, couplingStates, cutRequest, originOf } from './couplings';

const fx = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'meos-coupling-cut.json'), 'utf8')) as Record<'base' | 'cut' | 'feedback', MeosRecord>;

describe('the couplings', () => {
  it('are four engine components, each with the dependency the engine names when it is cut', () => {
    expect(COUPLINGS.map((c) => c.id)).toEqual(['sensor_resource', 'interaction_channel', 'sensor_alteration', 'feedback']);
    // the engine's own words for the cut interaction channel and feedback are the ones in the recorded status log
    const dep = (r: MeosRecord) => r.status_log.find((s) => s.dependency)?.dependency?.detail;
    expect(dep(fx.cut)).toBe(couplingDef('interaction_channel').whenCut);
    expect(dep(fx.feedback)).toBe(couplingDef('feedback').whenCut);
  });
  it('are all connected in the baseline run at every tick', () => {
    for (const t of [0, 100, 200, 359]) expect(Object.values(couplingStates(fx.base, t)).every((s) => s === 'connected')).toBe(true);
  });
  it('read the cut and the restoration from the record, at the ticks the engine applied them', () => {
    expect(couplingStates(fx.cut, 99).interaction_channel).toBe('connected');
    expect(couplingStates(fx.cut, 100).interaction_channel).toBe('cut');
    expect(couplingStates(fx.cut, 149).interaction_channel).toBe('cut');
    expect(couplingStates(fx.cut, 150).interaction_channel).toBe('connected');
    // only the named coupling changes
    expect(couplingStates(fx.cut, 120).feedback).toBe('connected');
    expect(couplingStates(fx.feedback, 120).feedback).toBe('cut');
    expect(couplingStates(fx.feedback, 359).feedback).toBe('cut');
  });
  it('are reported unrecorded when the record carries no Address Domain frame', () => {
    const bare = { ...fx.base, frames: fx.base.frames.map((f) => ({ ...f, ad: undefined })) } as MeosRecord;
    expect(Object.values(couplingStates(bare, 10)).every((s) => s === 'unrecorded')).toBe(true);
  });
});

describe('a cut request', () => {
  it('is an ISOLATE of the coupling and a RECONNECT after the duration', () => {
    expect(cutRequest('interaction_channel', 100, 50, 359)).toEqual([{ tick: 100, op: 'ISOLATE', target: 'interaction_channel' }, { tick: 150, op: 'RECONNECT', target: 'interaction_channel' }]);
  });
  it('has no restoration when the duration is open or runs past the end', () => {
    expect(cutRequest('feedback', 100, null, 359)).toEqual([{ tick: 100, op: 'ISOLATE', target: 'feedback' }]);
    expect(cutRequest('feedback', 340, 80, 359)).toHaveLength(1);
  });
  it('is the interventions the engine ran for the fixture (the recorded intervention log carries exactly them)', () => {
    const req = cutRequest('interaction_channel', 100, 50, 359);
    expect(fx.cut.interventions).toEqual(req);
    expect(fx.cut.intervention_log.map((l) => [l.tick, l.op])).toEqual(req.map((i) => [i.tick, i.op]));
  });
  it('clamps the tick into the run', () => {
    expect(cutRequest('feedback', -5, null, 359)[0].tick).toBe(0);
    expect(cutRequest('feedback', 9999, null, 359)[0].tick).toBe(359);
  });
});

describe('branch comparison', () => {
  const c = compareBranches(fx.base, fx.cut);
  it('locates where the two records first differ, and says what each ended as', () => {
    expect(c.sameConfiguration).toBe(true);
    expect(fx.base.initial_config_digest).not.toBe(fx.cut.initial_config_digest);  // the input digest covers the interventions as well
    expect(c.base.label).toBe('ACTIVE'); expect(c.base.firstCollapse).toBeNull(); expect(c.base.terminatedAt).toBeNull();
    expect(c.branch.label).toBe('COLLAPSED'); expect(c.branch.firstCollapse).toBe(149);
    expect(c.base.resultDigest).not.toBe(c.branch.resultDigest);
    expect(c.firstStatusDivergence).toBe(126);
    expect(c.firstStateDivergence).not.toBeNull();
    expect(c.firstStateDivergence!).toBeLessThanOrEqual(c.firstStatusDivergence!);
    expect(c.firstStateDivergence!).toBeGreaterThanOrEqual(100);  // nothing differs before the intervention
  });
  it('lists exactly the interventions the branch added', () => {
    expect(c.added).toEqual(fx.cut.interventions);
  });
  it('does not call two runs of different configurations the same', () => {
    const other = { ...fx.cut, config: { ...fx.cut.config, seed: 99 } } as MeosRecord;
    expect(compareBranches(fx.base, other).sameConfiguration).toBe(false);
  });
  it('finds no divergence between a record and itself, and no added intervention', () => {
    const s = compareBranches(fx.base, fx.base);
    expect(s.firstStateDivergence).toBeNull(); expect(s.firstStatusDivergence).toBeNull(); expect(s.added).toEqual([]);
  });
  it('compares only the ticks both records cover', () => {
    expect(c.comparedTicks).toBe(Math.min(fx.base.frames.length, fx.cut.frames.length));
  });
  it('shows that an earlier cut diverges no later than a later one (feedback cut at 100 vs interaction cut at 100 both diverge from 100 on)', () => {
    const f = compareBranches(fx.base, fx.feedback);
    expect(f.firstStateDivergence!).toBeGreaterThanOrEqual(100);
    expect(f.branch.firstCollapse).toBe(144);
  });
});

describe('baseline positions for the 3D marker', () => {
  it('are the recorded positions of the baseline at that tick, and null outside it', () => {
    const p = baselinePositions(fx.base, 120)!;
    expect(p.A1.x).toBe(fx.base.frames[120].A1.x); expect(p.A2.y).toBe(fx.base.frames[120].A2.y);
    expect(baselinePositions(fx.base, 99999)).toBeNull();
  });
});

describe('where the displayed record comes from', () => {
  it('keeps a new run, a verified replay, a failed replay and a stored experiment apart', () => {
    expect(originOf(null)).toBe('NEW_ENGINE_RUN');
    expect(originOf('replay identical: 4b08c75a...')).toBe('REPLAY_VERIFIED');
    expect(originOf('REPLAY DIFFERS: aaa vs bbb')).toBe('REPLAY_DIFFERS');
    expect(originOf('MFS MFS-F14-1: 8 components retained')).toBe('SAVED_EXPERIMENT');
  });
});
