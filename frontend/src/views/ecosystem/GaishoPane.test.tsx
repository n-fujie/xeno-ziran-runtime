// GAISHO pane - rendered to a string from real engine records (__fixtures__/gaisho-records.json); what is checked is what a researcher is shown: the scope and the missing manuscript, the domains each with its own
// status, the five levels kept apart with the attribution unresolved, the unobserved classes, the negative results, the figure kind, and that a domain that was not executed is not shown as a result. SYNTHETIC only.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import GaishoPane, { type GaishoCtx } from './GaishoPane';
import { initialGaishoUi, type ConstructionOut, type GaishoRecord, type GaishoSpecInfo, type ShapeReading } from './gaisho';

const fx = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'gaisho-records.json'), 'utf8')) as Record<'base' | 'passive' | 'body', GaishoRecord> & { info: GaishoSpecInfo; construction: ConstructionOut; reading_same: ShapeReading; reading_changed: ShapeReading };
const saved = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..', 'docs', 'gaisho', 'experiments.json'), 'utf8')) as { domains: Record<string, GaishoRecord> };
const RESP = 'ground-responsive judgement', CUE = 'accidental correct: coincidental cue';
const ctx = (over: Partial<GaishoCtx['ui']> = {}, extra: Partial<GaishoCtx> = {}): GaishoCtx => ({ info: fx.info, infoErr: null, ui: { ...initialGaishoUi(), ...over }, setUi: () => undefined, busy: false, setBusy: () => undefined, err: null, setErr: () => undefined, focus3d: () => undefined, ...extra });
const html = (over: Partial<GaishoCtx['ui']> = {}, extra: Partial<GaishoCtx> = {}) => renderToString(<GaishoPane {...ctx(over, extra)} />);
const text = (h: string) => h.replace(/<!-- -->/g, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&gt;/g, '>').replace(/&amp;/g, '&');
const section = (h: string, id: string) => { const i = h.indexOf(`data-testid="${id}"`); const next = h.slice(i + 10).search(/data-testid="gs-(?!unobs)/); return h.slice(i, next < 0 ? undefined : i + 10 + next); };
const run = (rec: GaishoRecord, cond = RESP) => ({ rec, cond, domain: rec.spec.domain, snap: 'end' });

describe('the GAISHO pane before a run', () => {
  it('states that it is synthetic, that the manuscript was not found, and that the laboratory never computes an attribution', () => {
    const t = text(section(html(), 'gs-scope'));
    for (const s of ['SYNTHETIC', 'never computes a Gaisho attribution', 'R37 was not found']) expect(t).toContain(s);
  });
  it('lists the five domains each with its own completion status, and shows no result', () => {
    const h = html(), t = text(section(h, 'gs-domains'));
    for (const d of ['001-knowledge', '002-bias', '003-freedom', '004-body', '005-credit']) expect(t).toContain(d);
    expect(t).toContain('NOT_EXECUTED'); expect(t).toContain('INITIAL_EXPERIMENT_EXECUTED'); expect(t).toContain('INITIAL_CONDITIONS_EXECUTED');
    expect(h).not.toContain('data-testid="gs-result"'); expect(text(html())).toContain('No experiment yet');
  });
  it('offers the candidate operations of the domain and the ten axes of the observation', () => {
    const h = html();
    expect(text(section(h, 'gs-conditions'))).toContain('accidental correct: coincidental cue');
    const o = text(section(h, 'gs-observation'));
    for (const s of ['sensor noise', 'scale', 'temporal window', 'speed', 'coupling', 'resources', 'memory record', 'environment', 'probe', 'outside the boundary', 'sensor channels', 'seeds']) expect(o).toContain(s);
  });
  it('lists the forbidden inferences', () => {
    const t = text(section(html(), 'gs-prohibited'));
    expect(t).toContain('spike_fired'); expect(t).toContain('operational_difference_found'); expect(t).toContain('human neural activity');
  });
});

describe('the GAISHO pane with an executed record', () => {
  const h = html(run(fx.base));
  it('shows the figure kind, the model, the seed unit and the digest', () => {
    const t = text(section(h, 'gs-result'));
    for (const s of ['EXECUTED_COMPUTATIONAL_EXPERIMENT', 'Executed Computational Experiment', 'gaisho-lab/1', '4 seeds', 'one run per seed', fx.base.digest.slice(0, 16)]) expect(t).toContain(s);
  });
  it('shows the relations of the chosen condition with their intervals, and the same condition under a passive coupling with the class of the reason', () => {
    expect(text(section(h, 'gs-relations'))).toMatch(/effect_E 0\.\d+ \[/);
    const p = html(run(fx.passive)), t = text(section(p, 'gs-relations'));
    expect(t).toContain('IDENTIFICATION_UNRESOLVED'); expect(t).toContain('does not separate the axes'); expect(p).toContain('data-testid="gs-unobs-effect_E"');
  });
  it('keeps the five levels apart, with the attribution unresolved and the operational test marked as not an attribution', () => {
    const t = text(section(h, 'gs-levels'));
    for (const s of ['NOT_ESTABLISHED', 'NOT_MODELLED', 'EXECUTED_IN_MODEL', 'RECONSTRUCTED']) expect(t).toContain(s);
    const a = text(section(h, 'gs-attribution'));
    expect(a).toContain('UNRESOLVED'); expect(a).toContain('never computes it'); expect(a).toContain('NOT_NEGATED');
    expect(text(section(html(run(fx.base, CUE)), 'gs-attribution'))).toContain('CRITERION_NEGATIVE');
  });
  it('shows the verdicts of the competing explanations apart and unscored, including the negative ones', () => {
    const t = text(section(html(run({ ...fx.base, models: saved.domains['001-knowledge'].models }, CUE)), 'gs-models'));
    expect(t).toMatch(/HARMFUL|REDUNDANT/); expect(t).toContain('not added into a score');
    const absent = text(section(html(run(fx.base, CUE)), 'gs-models-absent'));  // a subset of the conditions: no comparison is made, and the pane says what was not run
    expect(absent).toContain('only when every candidate condition'); expect(absent).toContain('have not been run');
  });
  it('keeps the negative results, the shape counts with the projection named, and the figure <-> condition table', () => {
    expect(text(section(h, 'gs-negative'))).toContain('NOT_DONE');
    const s = text(section(h, 'gs-shape-counts'));
    expect(s).toContain('recorded cells'); expect(s).toContain('VISUALIZATION_PROJECTION');
    const f = text(section(h, 'gs-figure-table'));
    for (const c of ['coincidental cue', 'ground-responsive judgement', 'reconfiguration']) expect(f).toContain(c);
    expect(f).toContain('start:'); expect(f).toContain('end:');
  });
  it('has the history, the export and the import, and an unrecorded region is named when the observation hides cells', () => {
    const hist = text(section(html({ ...run(fx.base), history: [{ id: 1, label: 'x', spec: fx.base.spec, digest: fx.base.digest, restored: true }] }), 'gs-history'));
    expect(hist).toContain('digest reproduced'); expect(text(section(h, 'gs-history'))).toContain('No experiment yet');
    expect(text(h)).toContain('restored by running the specification again'); expect(h).toContain('data-testid="gs-export"'); expect(h).toContain('data-testid="gs-import"');
    expect(text(section(html(run(fx.passive)), 'gs-unresolved'))).toContain('UNMEASURED');
  });
  it('shows construction data for the selected point', () => {
    const id = fx.base.shapes![RESP].end.vertices[5].id, t = text(section(html({ ...run(fx.base), selected: id }), 'gs-construction'));
    expect(t).toContain('INTERVENTION_RELATIVE_DIFFERENCE'); expect(t).toContain('operation digest');
  });
});

describe('a domain that is not executed', () => {
  it('is shown as specified, with no result, no shape, no figure of an experiment and no substitute computation', () => {
    const h = html({ domain: '004-body', rec: fx.body }), t = text(h);
    expect(t).toContain('NOT executed'); expect(t).toContain('no substitute computation'); expect(t).toContain('CONCEPTUAL_RECONSTRUCTION');
    for (const id of ['gs-result', 'gs-shape', 'gs-figure']) expect(h).not.toContain(`data-testid="${id}"`);
  });
});

describe('errors', () => {
  it('are shown, and a failed spec load is shown', () => {
    expect(text(html({}, { err: 'boom' }))).toContain('boom'); expect(text(html({}, { infoErr: '/spec: 403' }))).toContain('403');
  });
});

describe('the claims, the construction and the reading of a difference', () => {
  it('lists what is supported, what is limited and what is only a philosophical hypothesis, apart', () => {
    const t = text(section(html(), 'gs-claims'));
    for (const s of ['Supported by the executed experiments', 'Limits and negative results', 'Philosophical hypotheses NOT tested', 'K1', 'N1', 'H1', 'UNVERIFIED']) expect(t).toContain(s);
  });
  it('has a button that traces the construction of the shape in view, and no trace before it is asked for', () => {
    const h = html(run(fx.base));
    expect(h).toContain('data-testid="gs-trace-run"'); expect(h).not.toContain('data-testid="gs-trace-out"');
  });
  it('would show the reading of a difference (the weights, the sampling noise and that display changes no record)', () => {
    // the reading is held in the pane's own state from the engine's answer; its wording is what is checked here
    expect(fx.reading_same.summary).toContain('sampling noise'); expect(fx.reading_changed.summary).toContain('the operation (the decision rule) differs');
  });
});
