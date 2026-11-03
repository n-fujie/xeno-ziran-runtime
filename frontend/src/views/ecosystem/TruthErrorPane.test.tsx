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
const none = async () => undefined;
const ctx = (over: Partial<TruthCtx> = {}): TruthCtx => ({ base: runs.base, branch: null, k: 0, setK: () => undefined, t: 25, setT: () => undefined, selected: null, select: () => undefined, draft: {}, setDraft: () => undefined, busy: false, err: null,
  runBase: none, runBranch: none, clearBranch: () => undefined, focus3d: () => undefined, experiments: saved.experiments, expId: 'EXP-TE02', setExpId: () => undefined, loadArm: none, ...over });
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
});

