// TRUTH-ERROR pane — rendered to a string from real engine runs (truth-error-runs.json); what is checked is what a researcher is shown: the scope statement, the separate fields, the kind of every reading, the
// changes listed before the differences, and that an appeal and a missing experiment are not invented. SYNTHETIC only.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { TEExperiment } from './truthApi';
import TruthErrorPane, { type TruthCtx } from './TruthErrorPane';
import type { NodeId, TERun } from './truthError';

const dir = join(dirname(fileURLToPath(import.meta.url)), '__fixtures__');
const runs = JSON.parse(readFileSync(join(dir, 'truth-error-runs.json'), 'utf8')) as Record<'base' | 'invalid' | 'biased' | 'noscore', TERun>;
const saved = JSON.parse(readFileSync(join(dir, '..', '..', '..', '..', '..', 'docs', 'truth_error', 'experiments.json'), 'utf8')) as { experiments: Record<string, TEExperiment> };
const saved2 = JSON.parse(readFileSync(join(dir, '..', '..', '..', '..', '..', 'docs', 'truth_error', 'experiments2.json'), 'utf8')) as { experiments: Record<string, TEExperiment> };
const runs2 = JSON.parse(readFileSync(join(dir, 'truth-error-runs2.json'), 'utf8')) as Record<'base' | 'process' | 'no_release' | 'appeal' | 'appeal_gated', TERun>;
const none = async () => undefined;
const ctx = (over: Partial<TruthCtx> = {}): TruthCtx => ({ base: runs.base, branch: null, k: 0, setK: () => undefined, t: 25, setT: () => undefined, selected: null, select: () => undefined, draft: {}, setDraft: () => undefined, busy: false, err: null,
  runBase: none, runBranch: none, clearBranch: () => undefined, focus3d: () => undefined, experiments: saved.experiments, expId: 'EXP-TE02', setExpId: () => undefined, experiments2: saved2.experiments, exp2Id: 'EXP-TE07-release', setExp2Id: () => undefined, loadArm: none, ...over });
const html = (over: Partial<TruthCtx> = {}) => renderToString(<TruthErrorPane {...ctx(over)} />);
const text = (h: string) => h.replace(/<!-- -->/g, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').replace(/\s+([,.;:)])/g, '$1').replace(/\(\s+/g, '(').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&gt;/g, '>').replace(/&lt;/g, '<').replace(/&amp;/g, '&');
const section = (h: string, id: string) => { const i = h.indexOf(`data-testid="${id}"`); const next = h.indexOf('data-testid=', i + 10); return h.slice(i, next < 0 ? undefined : next); };

describe('the truth-error pane', () => {
  it('states first that everything is synthetic, that a head pose is a measurement only, and that the pose rule is invalid by construction', () => {
    const t = text(section(html(), 'te-scope'));
    for (const s of ['SYNTHETIC', 'No real person', 'must not be used for that', 'not an indicator of truthfulness', 'invalid by construction', 'REFERENCE']) expect(t).toContain(s);
  });
  it('asks for a baseline when there is none, and shows no field', () => {
    const t = text(html({ base: null }));
    expect(t).toContain('Run a baseline first'); expect(html({ base: null })).not.toContain('te-f-observation');
  });
  it('shows the five fields, the chain, the timeline and the Address-Domain states for a run', () => {
    const h = html();
    for (const id of ['te-f-observation', 'te-f-classification', 'te-f-scoring', 'te-f-consequences', 'te-f-reentry', 'te-chain', 'te-timeline', 'te-address', 'te-pose-trace']) expect(h, id).toContain(`data-testid="${id}"`);
    expect(text(section(h, 'te-chain'))).toContain('institution A: gate');
    expect(text(section(h, 'te-address'))).toContain('the score is extinguished'); expect(text(section(h, 'te-address'))).toContain('a binding constraint is extinguished');
  });
  it('marks every reading with its kind and never calls a reference value observed', () => {
    const o = text(section(html(), 'te-f-observation'));
    expect(o).toContain('OBSERVED'); expect(o).not.toContain('REFERENCE');
    const c = text(section(html(), 'te-f-classification'));
    expect(c).toContain('CLASSIFIED'); expect(c).toContain('INFERRED'); expect(c).toContain('REFERENCE');   // the agreement with the verification label is the evaluator's
    expect(text(section(html(), 'te-f-scoring'))).toContain('INSTITUTIONAL');
  });
  it('keeps an appeal NOT MODELLED rather than inventing one', () => {
    const t = text(section(html(), 'te-f-reentry'));
    expect(t).toContain('appeal'); expect(t).toContain('NOT MODELLED'); expect(t).toContain('UNRESOLVED');
  });
  it('shows the selected node of the baseline, and the same node of the branch beside it', () => {
    const one = text(section(html({ selected: 'classifier' as NodeId }), 'te-node'));
    expect(one).toContain('classifier: baseline'); expect(one).toContain('signal_rule'); expect(one).not.toContain('the same node in the branch');
    const two = text(section(html({ selected: 'classifier' as NodeId, branch: runs.invalid }), 'te-node'));
    expect(two).toContain('the same node in the branch'); expect(two).toContain('pose_rule (invalid by construction)');
  });
  it('lists what was changed before the differences, and says whether the real state is the same', () => {
    const h = html({ branch: runs.invalid });
    expect(text(section(h, 'te-changed'))).toContain('classifier: "signal_rule" -> "pose_rule"');
    expect(h.indexOf('data-testid="te-changed"')).toBeLessThan(h.indexOf('data-testid="te-compare"'));
    expect(text(h)).toContain('real states are identical');
    expect(text(section(html({ branch: runs.base }), 'te-changed'))).toContain('nothing (the same configuration)');
  });
  it('lists the saved experiment with its question, control, seeds, protocol, negative results and failure conditions', () => {
    const t = text(section(html(), 'te-experiment'));
    for (const s of ['Question:', 'Control:', 'Seeds: 20', 'observation range', 'Protocol:']) expect(t).toContain(s);
    expect(t).toContain('invalid rule (head pose)'); expect(text(section(html(), 'te-negatives'))).toContain('Not detected (kept)');
    const f = text(section(html(), 'te-failures'));
    expect(f).toContain('Failure conditions'); expect(f).toContain('not met'); expect(f).toContain('Synthetic subjects and institutions');
  });
  it('says so when the saved results are not on the server', () => {
    expect(text(html({ experiments: null }))).toContain('The saved results are not available on this server');
  });
  it('offers the settings of the engine and no way to give it an image, a video or a person', () => {
    const h = html(), t = text(section(h, 'te-controls')) + text(section(h, 'te-sensor-controls'));
    for (const s of ['classifier', 'threshold', 'score', 'correction at', 'transfer at', 'view angle', 'noise', 'occlusion', 'calibration bias', 'inject a failure at']) expect(t).toContain(s);
    expect(h).not.toMatch(/type="file"|<video|<img|getUserMedia|capture=/);
  });
  it('lists the five kinds of "cannot" apart, with the model\'s definition of each and no claim of a philosophical correspondence', () => {
    const t = text(section(html({ branch: runs.invalid }), 'te-modalities'));
    for (const s of ['forbidden by the institution', 'institutionally impossible', 'invisible to measurement', 'excluded by the predictive model', 'reachable after an intervention', 'branch']) expect(t).toContain(s);
    expect(text(html())).toContain('a correspondence with any philosophical account');
  });

  // ------------------------------------------------------------------------------------------------ phase 2
  it('shows the nine times, the four paths, the fixed metrics with their denominators, the recoverability and the appeal for a run that has a process', () => {
    const h = html({ base: runs2.process, k: 1, t: 30 });
    for (const id of ['te-process', 'te-paths', 'te-metrics', 'te-recover', 'te-appeal']) expect(h, id).toContain(`data-testid="${id}"`);
    const proc = text(section(h, 'te-process'));
    for (const e of ['misclassified', 'adopted', 'denied', 'detected', 'requested', 'approved', 'score updated', 'released', 'restored']) expect(proc, e).toContain(e);
    expect(proc).toContain('REFERENCE');   // a misclassification is known to the evaluator only
    const paths = text(section(h, 'te-paths'));
    for (const p of ['judgement path', 'effect path', 'correction path', 'subsequent path']) expect(paths).toContain(p);
    const m = text(section(h, 'te-metrics'));
    for (const s of ['access rate late fav', 'lost opportunities per fav', 'recovery time', 'persistent constraint', 'propagation b denied fav', 'subjects favourable at the start', 'last 10 periods']) expect(m, s).toContain(s);
  });
  it('lists the four paths of the same subject in the baseline and in the branch with the difference and its direction', () => {
    const h = html({ base: runs2.process, branch: runs2.no_release, k: 1, t: 30 });
    const paths = text(section(h, 'te-paths'));
    expect(paths).toContain('branch (period)'); expect(paths).toContain('branch − baseline');
    expect(paths).toContain('the binding constraint is released'); expect(paths).toContain('only in the baseline');   // the release happens in the process run, never in the no-release branch
    expect(paths).toContain('same');
  });
  it('keeps the release a separate time: a branch that never releases still shows the approval', () => {
    const t = text(section(html({ base: runs2.process, branch: runs2.no_release, k: 1, t: 30 }), 'te-process'));
    expect(t).toContain('the correction is approved'); expect(t).toContain('not within the periods');
  });
  it('says that an appeal that exists is not relief, and shows a gated appeal blocking the filing', () => {
    const t = text(section(html({ base: runs2.appeal, branch: runs2.appeal_gated }), 'te-appeal'));
    expect(t).toContain('exists (open)'); expect(t).toContain('exists (gated by the score)'); expect(t).toContain('blocked from filing by the score'); expect(t).toContain('after a favourable re-judgement');
    expect(t).toContain('three different counts'); expect(text(section(html({ base: runs2.appeal }), 'te-appeal'))).toContain('an association, not an effect of the appeal');
  });
  it('does not invent a process for a run saved before phase 2: no process sections, and the appeal stays NOT MODELLED', () => {
    const h = html();
    expect(h).not.toContain('data-testid="te-process"'); expect(h).not.toContain('data-testid="te-paths"');
    expect(text(section(h, 'te-f-reentry'))).toContain('NOT MODELLED');
  });
  it('says no appeal procedure exists when the run has none, instead of NOT MODELLED', () => {
    const t = text(section(html({ base: runs2.process }), 'te-f-reentry'));
    expect(t).toContain('no appeal procedure in this run'); expect(t).not.toContain('NOT MODELLED');
  });
  it('shows a phase-2 experiment with its contrasts, the replication on the other seeds and the not-detected results', () => {
    const h = html({ exp2Id: 'EXP-TE07-release' });
    const t = text(section(h, 'te2-experiment'));
    expect(t).toContain('replicated on 21-40');
    const c = text(section(h, 'te2-contrasts'));
    expect(c).toContain('withholding the release'); expect(c).toContain('replicated'); expect(c).toContain('not detected');
    expect(text(section(h, 'te2-replication'))).toContain('set-dependent means in one only');
    expect(text(section(h, 'te2-negatives'))).toContain('Not detected (kept)');
    expect(text(section(html({ exp2Id: 'EXP-TE10' }), 'te2-questions'))).toContain('Does classification error alone create a constraint');
  });
  it('says the phase-2 results are unavailable rather than showing none when the server has not saved them', () => {
    expect(text(html({ experiments2: null }))).toContain('The phase-2 results are not available on this server');
  });
  it('offers the correction time and the release time as separate controls, and states that the gated appeal is a hypothetical control', () => {
    const h = html();
    const t = text(section(h, 'te-process-controls'));
    expect(t).toContain('approval delay'); expect(t).toContain('release delay'); expect(t).toContain('audit every'); expect(t).toContain('appeal');
    expect(text(h)).toContain('hypothetical control for studying institutional design danger');
    expect(text(h)).toContain('not a procedure for judging any real person');
  });
});
