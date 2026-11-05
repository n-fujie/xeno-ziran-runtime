// GAISHO - the readings of the engine's record (gaisho.ts), on REAL records produced by the engine (__fixtures__/gaisho-records.json: knowledge domain, 4 seeds). What is checked is what the tab shows: relations with
// intervals or the class of the reason they are not identified, the five levels kept apart, the attribution never above UNRESOLVED, the support cells of a relation, construction data traceable to its source, the
// figure <-> condition table, the frame handed to the 3D scene, and the record export/import. SYNTHETIC only.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { FULL_OBSERVATION, LEVELS, OBS_PRESETS, cellTrace, claimGroups, constraintGroups, constructionOf, domainStatusRows, exportRecord, figureTable, frameOf, registerRows, initialGaishoUi, levelRows, negativeCounts, observationDiff, operationPart, parseRecord, relationRows, relationSupport, shapeOf, snapshotsOf, type ComparatorsOut, type ConstructionOut, type GaishoRecord, type GaishoSpecInfo, type ShapeReading } from './gaisho';

const fx = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'gaisho-records.json'), 'utf8')) as Record<'base' | 'passive' | 'scale4' | 'body', GaishoRecord> & { info: GaishoSpecInfo; construction: ConstructionOut; construction_scale: ConstructionOut; reading_same: ShapeReading; reading_changed: ShapeReading; obs_cmp: { change_kinds: { real_operation: string; recorded_observation: string; display: string } }; comparators: ComparatorsOut };
const { base, passive, scale4, body, info } = fx;
const CUE = 'accidental correct: coincidental cue', RESP = 'ground-responsive judgement', FB = 'correction and reconfiguration (feedback on)';

describe('relations', () => {
  it('give the value with its interval, and the class of the reason when a relation was not identified', () => {
    const e = relationRows(base, RESP).find((r) => r.name === 'effect_E')!;
    expect(e.status).toBe('IDENTIFIED'); expect(e.value!).toBeGreaterThan(0.9); expect(e.text).toMatch(/\[\d\.\d+, \d\.\d+\] n=4/);
    const p = relationRows(passive, RESP).filter((r) => ['effect_E', 'effect_S', 'revision_E'].includes(r.name));
    expect(p.every((r) => r.status === 'IDENTIFICATION_UNRESOLVED' && r.value === null && r.ci === null)).toBe(true);
    expect(relationRows(scale4, RESP).find((r) => r.name === 'effect_E')!.status).toBe('SCALE_MISFIT');
    expect(relationRows(base, 'no such condition')).toEqual([]);
  });
  it('tell candidates with a similar accuracy apart by their profile under intervention', () => {
    const v = (c: string, n: string) => relationRows(base, c).find((r) => r.name === n)!.value!;
    expect(v(CUE, 'effect_S')).toBeGreaterThan(0.8); expect(v(CUE, 'effect_E')).toBeLessThan(0.2);
    expect(v(RESP, 'effect_E')).toBeGreaterThan(0.8); expect(v(RESP, 'effect_S')).toBeLessThan(0.2);
    expect(v(FB, 'revision_E')).toBeGreaterThan(0.3);
  });
});

describe('the five levels', () => {
  it('are five separate records in order, and the Gaisho levels are never established or attributed by the laboratory', () => {
    for (const c of Object.keys(base.levels!)) {
      const rows = levelRows(base, c);
      expect(rows.map((r) => r.level)).toEqual([...LEVELS]);
      expect(rows.find((r) => r.level === 'gaisho_operational_shape')!.state).toBe('NOT_ESTABLISHED');
      expect(rows.find((r) => r.level === 'gaisho_attribution')!.state).toBe('UNRESOLVED');
      expect(rows.find((r) => r.level === 'conceptual_operational_shape')!.state).toBe('NOT_MODELLED');
    }
    expect(base.attribution_tests!.every((t) => t.attribution === 'UNRESOLVED')).toBe(true);
  });
  it('keep the negative results and the 8 forbidden inferences in the record', () => {
    const k = Object.fromEntries(negativeCounts(base));
    expect(k.NOT_DONE).toBe(1); expect(k.CRITERION_NEGATIVE).toBeGreaterThanOrEqual(1);
    expect(base.prohibited_inferences).toHaveLength(8); expect(base.limits).toContain('human neural activity');
  });
});

describe('shapes', () => {
  it('are the engine\'s, per condition and moment, each with a declared projection', () => {
    expect(snapshotsOf(base)).toEqual(['start', 'before shift', 'end']);
    const s = shapeOf(base, CUE, 'end')!;
    expect(s.recorded).toBe(true); expect(s.projection.kind).toBe('VISUALIZATION_PROJECTION'); expect(s.vertices.length + s.unresolved.length).toBe(91);
    expect(shapeOf(base, CUE, 'nowhere')).toBeNull();
  });
  it('keep the unrecorded regions of another observation with their class', () => {
    const s = shapeOf(scale4, RESP, 'end')!;
    expect(s.unresolved.length).toBeGreaterThan(0); expect(new Set(s.unresolved.map((u) => u.reason))).toEqual(new Set(['SCALE_MISFIT']));
    expect(operationPart(scale4.spec.observation)).toEqual(operationPart(base.spec.observation));  // an instrument change is no change of the operation
    expect(scale4.result!.conditions[RESP].operation_digest).toBe(base.result!.conditions[RESP].operation_digest);
  });
  it('give the cells an axis relation reads, and say so when a relation has no cells', () => {
    const s = shapeOf(base, RESP, 'end')!;
    const e = relationSupport('effect_E', s), sc = relationSupport('effect_S', s);
    expect(e.cells!.length).toBe(2 * 7); expect(sc.cells!.length).toBe(2 * 13);
    expect(e.cells!.every((id) => { const v = s.vertices.find((x) => x.id === id)!; return v.cell[0] === 0 || v.cell[0] === 12; })).toBe(true);
    expect(relationSupport('stability_do_W', s).cells).toBeNull(); expect(relationSupport('revision_E', s).note).toContain('two moments');
  });
  it('make every point traceable: a vertex names its cell, its trials, its provenance and its operation digest, an unresolved region its class', () => {
    const s = shapeOf(base, CUE, 'end')!, v = constructionOf(s, s.vertices[10].id)!;
    const t = Object.fromEntries(v.rows);
    expect(t.provenance).toBe('RECORDED_OBSERVATION'); expect(t['operation digest']).toBe(base.result!.conditions[CUE].operation_digest); expect(t['trials per cell and seed']).toBe('40');
    const s4 = shapeOf(scale4, RESP, 'end')!, u = constructionOf(s4, s4.unresolved[0].id)!;
    expect(Object.fromEntries(u.rows).class).toBe('SCALE_MISFIT'); expect(constructionOf(s, 'v99_99')).toBeNull();
  });
});

describe('the figure and the frame', () => {
  it('correspond: every drawn condition names its operation digest, its seeds and its shapes', () => {
    const t = figureTable(base);
    expect(t.map((r) => r.condition).sort()).toEqual([CUE, FB, RESP].sort());
    for (const r of t) { expect(r.seeds).toBe(4); expect(r.shapes.map((s) => s.snapshot)).toEqual(['start', 'before shift', 'end']); expect(r.shapes.every((s) => s.recorded)).toBe(true); }
    expect(figureTable({ ...base, result: undefined })).toEqual([]);
  });
  it('hands the 3D scene the shape, the ghost the researcher chose and the support of the relation', () => {
    const ui = { ...initialGaishoUi(), rec: base, cond: RESP, snap: 'end' };
    expect(frameOf(ui).shape!.condition).toBe(RESP); expect(frameOf(ui).ghost).toBeNull();
    expect(frameOf({ ...ui, ghost: { kind: 'moment', cond: RESP, snap: 'before shift' } }).ghost!.snapshot).toBe('before shift');
    expect(frameOf({ ...ui, ghost: { kind: 'condition', cond: CUE, snap: '' } }).ghost!.condition).toBe(CUE);
    expect(frameOf({ ...ui, recB: scale4, ghost: { kind: 'observation', cond: RESP, snap: 'end' } }).ghost!.unresolved.length).toBeGreaterThan(0);
    expect(frameOf({ ...ui, relation: 'effect_E' }).support).toHaveLength(14); expect(frameOf({ ...ui, relation: 'shift_drop' }).support).toBeNull();
    expect(frameOf(initialGaishoUi())).toEqual({ shape: null, ghost: null, selected: null, support: null, show: initialGaishoUi().show });
  });
});

describe('domains, observations and records', () => {
  it('keep the completion of every domain apart; the body domain is specified and not executed, with no figure and no result', () => {
    const rows = domainStatusRows(info);
    expect(rows.map((r) => r.id)).toEqual(['001-knowledge', '002-bias', '003-freedom', '004-body', '005-credit']);
    expect(rows.find((r) => r.id === '004-body')!.executed).toBe(false); expect(rows.filter((r) => r.executed)).toHaveLength(4);
    expect(new Set(rows.map((r) => r.completion)).size).toBeGreaterThan(1);
    expect(body.executed).toBe(false); expect(body.result).toBeUndefined(); expect(body.shapes).toBeUndefined(); expect(body.figure_kind).toBe('CONCEPTUAL_RECONSTRUCTION');
    expect(info.source_status).toContain('R37');
  });
  it('state the observation differences and the presets (each differs from the fullest observation)', () => {
    expect(observationDiff(FULL_OBSERVATION)).toEqual([]);
    expect(observationDiff({ ...FULL_OBSERVATION, scale: 4, boundary: ['y'] })).toEqual(['scale=4', 'boundary=[y]']);
    for (const p of OBS_PRESETS) expect(observationDiff({ ...FULL_OBSERVATION, ...p.patch }).length, p.name).toBeGreaterThan(0);
  });
  it('export a record as its specification and digest, import it back, and refuse anything else', () => {
    const t = parseRecord(exportRecord(base));
    expect(t.digest).toBe(base.digest); expect(t.spec.seeds).toEqual([1, 2, 3, 4]);
    expect(() => parseRecord('{"kind":"other"}')).toThrow('not a GAISHO record'); expect(() => parseRecord('nope')).toThrow();
    expect(exportRecord(base)).not.toContain('"vertices"');  // the shapes are regenerated by running the specification, not stored
  });
});

describe('where the cells and edges come from (the engine\'s construction record)', () => {
  it('accounts for the 91 cells and the 162 edges: the 13 x 7 grid of the interventions, 12 x 7 + 13 x 6 neighbour pairs, each cell one intervention pair', () => {
    const t = fx.construction, c = t.counts!;
    expect(c.grid).toEqual([13, 7]); expect(c.cells_total).toBe(91); expect(c.edges_drawn).toBe(162); expect(c.edges_expected_if_all_recorded).toBe(12 * 7 + 13 * 6); expect(t.counts_consistent).toBe(true);
    expect(t.cells).toHaveLength(91); expect(t.edges).toHaveLength(162); expect(t.cells![0].trials_per_cell_and_seed).toBe(40); expect(t.cells![0].seeds).toBe(4);
    expect(t.outcome_of_the_domain).toContain('P(J = +1'); expect(t.outcome_of_the_domain).toContain('not the correctness');
    for (const k of ['cell', 'cell_value', 'edge', 'cut', 'branch_point', 'unresolved', 'projection']) expect(t.rules[k]).toBeTruthy();
  });
  it('shows that the surface carries the three weights of the decision rule and nothing more', () => {
    const w = fx.construction.what_the_surface_carries!;
    expect(w.fitted_weights.a).toBeCloseTo(w.weights_of_the_operation.a, 0); expect(w.rms_residual_of_the_fit).toBeLessThan(1.6 * w.expected_sampling_rms); expect(w.reading).toContain('not a record of the run');
  });
  it('traces one cell or one unresolved region', () => {
    const t = fx.construction, id = t.cells![40].id, r = cellTrace(t, id);
    expect(r.cell!.id).toBe(id); expect(r.edges.length).toBeGreaterThanOrEqual(2); expect(r.edges.every((e) => e.a === id || e.b === id)).toBe(true); expect(r.cell!.expected_from_the_agents_weights).not.toBeNull();
    const s = fx.construction_scale, u = s.unresolved![0];
    expect(s.counts!.cells_unresolved).toBeGreaterThan(0); expect(s.counts!.cells_total).toBe(91); expect(cellTrace(s, u.id)).toEqual({ cell: null, edges: [], unresolved: 'SCALE_MISFIT' });
  });
});

describe('what a difference is a difference of', () => {
  it('reads two moments of an agent whose weights did not change as the same operation and the record\'s sampling noise', () => {
    const r = fx.reading_same;
    expect(r.real_operation).toContain('SAME_OPERATION'); expect(r.recorded_observation.reading).toBe('WITHIN_SAMPLING_NOISE'); expect(r.display).toMatch(/^none/);
  });
  it('reads a change of the weights as a real change of the operation, far beyond the noise', () => {
    const r = fx.reading_changed;
    expect(r.real_operation).toContain('OPERATION_CHANGED'); expect(r.recorded_observation.reading).toBe('BEYOND_SAMPLING_NOISE'); expect(Math.max(...Object.values(r.weight_change!).map(Math.abs))).toBeGreaterThan(1);
  });
  it('names the four kinds for another observation of the same operation', () => {
    expect(fx.obs_cmp.change_kinds.real_operation).toBe('SAME'); expect(fx.obs_cmp.change_kinds.display).toMatch(/^none/);
  });
});

describe('claims', () => {
  it('are grouped as supported, limited and untested, and the hypotheses are never listed as supported', () => {
    const g = claimGroups(fx.info.claims);
    expect(g.map((x) => x.status)).toEqual(['SUPPORTED_IN_MODEL', 'LIMITED_OR_NEGATIVE', 'UNTESTED_PHILOSOPHICAL_HYPOTHESIS']);
    expect(g.every((x) => x.items.length > 0)).toBe(true);
    const h = g[2].items.map((c) => c.id); expect(h).toContain('U1'); expect(h).toContain('R37-H1..H3'); expect(g[0].items.some((c) => h.includes(c.id))).toBe(false);
    expect(g[2].items.find((c) => c.id === 'U3')!.rests_on).toContain('UNVERIFIED');
  });
});

describe('which layer each element is, and the comparators', () => {
  it('classifies the cell as the recorded observation, the edge and the branch point as reconstructed relations, the unresolved marker and the face as display', () => {
    const L = fx.construction.layers;
    expect(Object.keys(L).sort()).toEqual(['branch_point', 'cell', 'edge', 'surface_between_cells', 'unresolved']);
    expect(L.cell.recorded_observation).toContain('THE VALUE'); expect(L.cell.reconstructed_relation).toContain('none'); expect(L.cell.real_operation).toContain('decision rule');
    expect(L.edge.reconstructed_relation).toContain('THE DIFFERENCE'); expect(L.edge.recorded_observation).toContain('none'); expect(L.branch_point.reconstructed_relation).toContain('INTERPOLATION');
    expect(L.unresolved.display).toContain('MARKER'); expect(L.surface_between_cells.display).toContain('DRAWN FACE');
    expect(fx.construction.cells!.every((c) => c.provenance === 'RECORDED_OBSERVATION')).toBe(true); expect(fx.construction.edges!.every((e) => e.provenance === 'RECONSTRUCTED_RELATION')).toBe(true);
  });
  it('declares what each comparator is given: the same cells, no history, the number of parameters, and what was not run', () => {
    const c = fx.comparators;
    expect(Object.keys(c.comparators)).toEqual(['M0', 'M1', 'CAND', 'M4']); expect(c.comparators.CAND.parameters).toBe(c.comparators.M4.parameters);
    expect(Object.values(c.comparators).every((m) => !m.history && m.information === 'end-snapshot training cells')).toBe(true);
    expect(c.not_run).toContain('attention'); expect(c.reading).toContain('nested model cannot beat');
    const by = Object.fromEntries(c.rows.map((r) => [r.condition, Object.fromEntries(r.verdicts.map((v) => [v.competitor.split(' ')[0], v.verdict]))]));
    expect(by['accidental correct: coincidental cue'].M4).toBe('HARMFUL'); expect(by['ground-responsive judgement'].M4).toBe('NON_REDUNDANT'); expect(by['ground-responsive judgement'].M1).toBe('REDUNDANT');
  });
});

describe('the correspondence with GAISHO R37', () => {
  it('shows the applicability gate with the unresolved attribution, and the R37 term of every level (one level has none)', () => {
    for (const c of Object.keys(base.levels!)) {
      const rows = levelRows(base, c), a = rows.find((r) => r.level === 'gaisho_attribution')!;
      expect(a.state).toBe('UNRESOLVED'); expect(a.applicability_gate).toMatch(/^NOT_PASSED/); expect(a.r37_term).toContain('defeated-for-K');
      expect(rows.find((r) => r.level === 'gaisho_operational_shape')!.r37_term).toContain('NO R37 TERM');
    }
  });
  it('lists the registers apart: occurrence is not assessed, the attribution is unresolved, C, E and N are not modelled', () => {
    const r = Object.fromEntries(registerRows(base).map((x) => [x.id, x]));
    expect(Object.keys(r)).toEqual(['S', 'Occ_G', 'Det_D', 'A_G', 'C', 'P', 'E', 'N', 'I']);
    expect(r.Occ_G.lab).toBe('NOT_ASSESSED'); expect(r.A_G.lab).toBe('UNRESOLVED'); expect(r.A_G.gate).toBe('NOT_PASSED'); expect(r.C.lab).toBe('NOT_MODELLED'); expect(r.N.lab).toBe('NOT_MODELLED');
  });
  it('groups the R37 constraints by how far they are implemented, and does not count the comparative claims or the ignition constraint as implemented', () => {
    const g = constraintGroups(info.r37.constraints), ids = (s: string) => g.find((x) => x.status === s)!.items.map((c) => c.id);
    expect(g.map((x) => x.status)).toEqual(['IMPLEMENTED', 'PARTIAL', 'NOT_IMPLEMENTED']);
    expect(ids('NOT_IMPLEMENTED')).toEqual(expect.arrayContaining(['R6', 'R8', 'R15'])); expect(ids('IMPLEMENTED')).toEqual(expect.arrayContaining(['R2', 'R5', 'R14']));
    expect(info.source_status).toContain('read on 2026-11-05'); expect(info.source_status).toContain('not read in full');
  });
  it('keeps every negative result in one failure registry', () => {
    expect(base.negative_results!.every((n) => typeof n.registry === 'string' && n.registry !== '')).toBe(true);
    expect(base.r37!.arms.B.lab).toBe('NOT_EXECUTED'); expect(Object.keys(base.r37!.failure_registries)).toEqual(['F1', 'F2', 'F3', 'F4', 'F5']);
  });
});
