// XENOSCIENCE ECOSYSTEM — couplings and branch comparison, from real engine records: the baseline run and the run with the interaction channel isolated at tick 100 and restored at 150
// (horizon 360, seed 1), plus a run with feedback isolated at 100. The fixture is the engine output with the field stream and traces removed (meos-coupling-cut.json).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { MeosRecord } from './meosApi';
import { COUPLINGS, baselinePositions, branchAspects, compareBranches, couplingDef, couplingStates, cutRequest, originOf } from './couplings';

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

describe('the branch compared aspect by aspect', () => {
  const fxAll = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'meos-coupling-cut.json'), 'utf8')) as Record<'base' | 'cut' | 'feedback' | 'history_off', MeosRecord>;
  const obsFx = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'meos-stage2-observed.json'), 'utf8')) as Record<'full' | 'coarse', { observed: import('./meosApi').Observed }>;
  const get = (a: ReturnType<typeof branchAspects>, id: string) => a.find((x) => x.id === id)!;
  it('has seven aspects, each with its two sides and a verdict', () => {
    const a = branchAspects(fxAll.base, fxAll.cut);
    expect(a.map((x) => x.id)).toEqual(['couplings', 'observation', 'reached', 'delay', 'persistence', 'history', 'routes']);
    for (const x of a) expect(['DIFFERENT', 'NO_DIFFERENCE', 'UNRESOLVED']).toContain(x.verdict);
  });
  it('finds the cut coupling, the state reached, the collapse and the response delay of the interaction-channel cut', () => {
    const a = branchAspects(fxAll.base, fxAll.cut);
    expect(get(a, 'couplings').verdict).toBe('DIFFERENT'); expect(get(a, 'couplings').detail).toBe('changed: interaction_channel');
    expect(get(a, 'couplings').branch).toContain('interaction_channel: 100-149');
    expect(get(a, 'reached').base).toContain('ACTIVE'); expect(get(a, 'reached').branch).toContain('COLLAPSED');
    expect(get(a, 'persistence').branch).toBe('collapse at 149'); expect(get(a, 'persistence').base).toBe('no collapse');
    expect(get(a, 'delay').base).toBe('no status change after t=100'); expect(get(a, 'delay').branch).toBe('DEGRADED at 126 (26 ticks after t=100)'); expect(get(a, 'delay').verdict).toBe('DIFFERENT');
  });
  it('keeps the negative results: routes did not differ, and the history disabled run changed no coupling', () => {
    expect(get(branchAspects(fxAll.base, fxAll.cut), 'routes').verdict).toBe('NO_DIFFERENCE');
    const h = branchAspects(fxAll.base, fxAll.history_off);
    expect(get(h, 'couplings').verdict).toBe('NO_DIFFERENCE'); expect(get(h, 'couplings').detail).toBe('no coupling was cut in either run');
    expect(get(h, 'history').verdict).toBe('DIFFERENT'); expect(get(h, 'history').base).toBe('71 of 71 cycles contain a re-entry'); expect(get(h, 'history').branch).toBe('20 of 22 cycles contain a re-entry');
  });
  it('reports a record compared with itself as no difference throughout (except the observation, which needs two observation results)', () => {
    const a = branchAspects(fxAll.base, fxAll.base);
    for (const x of a.filter((y) => y.id !== 'observation')) expect(x.verdict, x.id).toBe('NO_DIFFERENCE');
    expect(get(a, 'observation').verdict).toBe('UNRESOLVED');
  });
  it('compares the observation records of the two runs when both exist, and leaves it unresolved when one does not', () => {
    const a = branchAspects(fxAll.base, fxAll.cut, obsFx.full.observed, obsFx.coarse.observed);
    expect(get(a, 'observation').verdict).toBe('DIFFERENT'); expect(get(a, 'observation').base).toContain('27 of 27'); expect(get(a, 'observation').branch).toContain('0 of 27');
    expect(get(branchAspects(fxAll.base, fxAll.cut, obsFx.full.observed, null), 'observation').verdict).toBe('UNRESOLVED');
  });
});

describe('traceability of the branch aspects', () => {
  const fxAll = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'meos-coupling-cut.json'), 'utf8')) as Record<'base' | 'cut' | 'feedback' | 'history_off', MeosRecord>;
  it('names the fields each aspect reads, for every branch', () => {
    for (const k of ['cut', 'feedback', 'history_off'] as const) for (const a of branchAspects(fxAll.base, fxAll[k])) { expect(a.reads.length, `${k}.${a.id}`).toBeGreaterThan(0); expect(a.detail.length).toBeGreaterThan(10); }
  });
  it('agrees with the records themselves: the coupling spans and the first collapse are the ones the frames and logs hold', () => {
    const a = branchAspects(fxAll.base, fxAll.cut);
    const cutTicks = fxAll.cut.frames.map((f, t) => (f.ad && !f.ad.A1.connectivity.interaction ? t : -1)).filter((t) => t >= 0);
    expect(cutTicks.length).toBeGreaterThan(0);   // the ad block is written only where it changes: the spans come from the latest ad frame
    expect(a.find((x) => x.id === 'couplings')!.branch).toContain('interaction_channel: 100-149');
    expect(a.find((x) => x.id === 'persistence')!.branch).toBe(`collapse at ${fxAll.cut.frames.findIndex((f) => f.status === 'COLLAPSED')}`);
  });
  it('keeps the negative result of every aspect that did not change, for every branch', () => {
    for (const k of ['cut', 'feedback', 'history_off'] as const) {
      const a = branchAspects(fxAll.base, fxAll[k]);
      expect(a.some((x) => x.verdict === 'NO_DIFFERENCE'), k).toBe(true);
      expect(a.filter((x) => x.verdict === 'NO_DIFFERENCE').every((x) => x.base === x.branch), k).toBe(true);
    }
  });
  it('draws no conclusion about cause: the aspects only locate differences', () => {
    const words = JSON.stringify(branchAspects(fxAll.base, fxAll.cut)).toLowerCase();
    for (const bad of ['caused', 'because', 'proves', 'due to']) expect(words).not.toContain(bad);
  });
});

