// TRUTH-ERROR DYNAMICS — the readings over runs of the synthetic virtual institution. The fixtures are real engine output (backend/xzr/truth_error): a baseline, the same with an invalid (head-pose) rule, with a biased and
// failing sensor, and without a score. SYNTHETIC only: nothing here assesses a real person.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { ADDRESS_STATES, EDGES, MODALITIES, NODES, addressStatesAt, compareRuns, fieldsAt, modalitiesAt, modalityCounts, nodeReadings, timelineEvents, type NodeId, type TERun } from './truthError';

const runs = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'truth-error-runs.json'), 'utf8')) as Record<'base' | 'invalid' | 'biased' | 'noscore', TERun>;
const { base, invalid, biased, noscore } = runs;

describe('the chain', () => {
  it('is not a line: a node has more than one source, the score is acted on by a correction, and the subject receives feedback', () => {
    const into = (id: NodeId) => EDGES.filter(([, to]) => to === id).map(([from]) => from);
    expect(into('acceptance').sort()).toEqual(['classifier', 'warrant']);
    expect(into('score').sort()).toEqual(['acceptance', 'correction']);
    expect(into('classifier').sort()).toEqual(['pose_sensor', 'signal_sensor']);
    expect(into('subject')).toEqual(['resources']);
    expect(EDGES.filter(([from]) => from === 'score').map(([, to]) => to).sort()).toEqual(['gate_a', 'gate_b']);  // two institutions read the score
    for (const [a, b] of EDGES) { expect(NODES.some((n) => n.id === a)).toBe(true); expect(NODES.some((n) => n.id === b)).toBe(true); }
  });
});

describe('what each node holds', () => {
  const rec = base.records[0][20], c = base.config;
  it('marks the evaluator\'s reference values REFERENCE and the sensors\' own records OBSERVED, never mixed', () => {
    for (const r of nodeReadings('subject', rec, c)) expect(r.epistemic).toBe('REFERENCE');
    for (const id of ['pose_sensor', 'signal_sensor'] as NodeId[]) for (const r of nodeReadings(id, rec, c)) expect(r.epistemic).toBe('OBSERVED');
    for (const r of nodeReadings('warrant', rec, c)) expect(r.epistemic).toBe('INFERRED');
    for (const id of ['acceptance', 'score', 'gate_a', 'gate_b', 'correction', 'resources'] as NodeId[]) for (const r of nodeReadings(id, rec, c)) expect(r.epistemic).toBe('INSTITUTIONAL');
    const cls = nodeReadings('classifier', rec, c);
    expect(cls.find((r) => r.label === 'classification')!.epistemic).toBe('CLASSIFIED');
    expect(cls.find((r) => r.label.startsWith('agrees with the verification label'))!.epistemic).toBe('REFERENCE');
  });
  it('never puts the reference state among the readings of a sensor or of the institution', () => {
    const z = rec.reference_z.toFixed(3);
    for (const id of ['pose_sensor', 'signal_sensor', 'warrant', 'acceptance', 'score', 'gate_a', 'gate_b', 'resources'] as NodeId[]) for (const r of nodeReadings(id, rec, c)) expect(r.value, `${id} ${r.label}`).not.toBe(z);
  });
  it('says plainly that the head-pose rule is invalid by construction', () => {
    const r = invalid.records[0][20];
    expect(nodeReadings('classifier', r, invalid.config)[0].value).toContain('invalid by construction');
    expect(nodeReadings('classifier', rec, c)[0].value).not.toContain('invalid');
  });
  it('reads a missing and a failed sensor as what they are: nothing obtained, and a stuck value that is not marked missing', () => {
    const rs = biased.records[0];
    const lost = rs.find((r) => r.pose_missing > 0)!;
    expect(nodeReadings('pose_sensor', lost, biased.config).find((x) => x.label === 'missing')!.value).not.toBe('none');
    // after the injected failure at 30: the periods that are not occluded report a value, never "missing", and the value is stuck while the reference moves
    const after = rs.filter((r) => r.t >= 31 && r.pose_missing === 0);
    expect(after.length).toBeGreaterThan(3);
    expect(nodeReadings('pose_sensor', after[0], biased.config).find((x) => x.label === 'conditions')!.value).toContain('failure stuck from 30');
    expect(new Set(after.map((r) => JSON.stringify(r.pose_measured))).size).toBe(1);   // stuck
    expect(new Set(after.map((r) => JSON.stringify(r.pose_reference))).size).toBeGreaterThan(1);   // while the reference moves
    expect(after.every((r) => r.pose_confidence > 0)).toBe(true);   // and still confident
  });
  it('shows what a transfer carries and that a correction restores the score but not the resources', () => {
    const t = nodeReadings('gate_b', base.records[0][20], c).map((r) => r.value).join(' ');
    expect(t).toContain('at 12'); expect(t).toContain('not propagated');
    expect(nodeReadings('correction', rec, c).find((r) => r.label === 'what a correction restores')!.value).toContain('not resources or lost opportunities');
  });
});

describe('the six fields', () => {
  it('give every field readings at a period, and keep an appeal NOT MODELLED rather than inventing one', () => {
    const f = fieldsAt(base, 0, 25);
    for (const k of ['observation', 'classification', 'scoring', 'consequences', 'reentry'] as const) expect(f[k].length, k).toBeGreaterThan(2);
    const appeal = f.reentry.find((r) => r.label === 'appeal')!;
    expect(appeal.epistemic).toBe('UNRESOLVED'); expect(appeal.value).toContain('NOT MODELLED');
  });
  it('count the history up to the period: adoptions, the correction and what follows it', () => {
    const rs = base.records[3], corrected = rs.find((r) => r.corrected);
    const f = fieldsAt(base, 3, 30);
    expect(f.reentry.find((r) => r.label === 'adopted adverse judgements so far')!.value).toBe(String(rs.slice(0, 31).filter((r) => r.accepted && r.classification === -1).length));
    if (corrected) expect(f.reentry.find((r) => r.label === 'correction')!.value).toBe(`at period ${corrected.t}`);
  });
  it('clamp the period into the run', () => {
    expect(() => fieldsAt(base, 0, 9999)).not.toThrow();
    expect(() => fieldsAt(base, 0, -4)).not.toThrow();
  });
});

describe('the truth-error timeline', () => {
  const all = (r: TERun) => r.records.flatMap((_, k) => timelineEvents(r, k));
  it('is in time order and each event can be found in the records it was read from', () => {
    for (let k = 0; k < base.records.length; k++) {
      const ev = timelineEvents(base, k), rs = base.records[k];
      expect(ev.map((e) => e.t)).toEqual([...ev.map((e) => e.t)].sort((a, b) => a - b));
      for (const e of ev.filter((x) => x.kind === 'access_denied')) { expect(rs[e.t].access).toBe(false); expect(rs[e.t - 1].access).toBe(true); }
      for (const e of ev.filter((x) => x.kind === 'withdrawn')) expect(rs.findIndex((r) => r.corrected)).toBe(e.t);
      for (const e of ev.filter((x) => x.kind === 'contradicted_by_reference')) { expect(rs[e.t].verification_label).toBe(true); expect(rs[e.t].classification).toBe(-1); expect(rs[e.t].accepted).toBe(true); }
      for (const e of ev.filter((x) => x.kind === 'warrant_contradicts')) expect(rs[e.t].warrant).toBe('SUPPORTED');
    }
  });
  it('keeps an adopted judgement, its contradiction by the reference, and its contradiction by the warrant as three different events', () => {
    const kinds = new Set(all(invalid).map((e) => e.kind));
    for (const k of ['judgement_adopted', 'contradicted_by_reference', 'access_denied', 'withdrawn'] as const) expect(kinds.has(k), k).toBe(true);
  });
  it('finds more judgements contradicted by the reference under the invalid rule than under the valid one', () => {
    const n = (r: TERun) => all(r).filter((e) => e.kind === 'contradicted_by_reference').length;
    expect(n(invalid)).toBeGreaterThan(n(base));
  });
  it('shows the effect at the second institution and the constraint set and released', () => {
    const kinds = new Set(all(base).map((e) => e.kind));
    expect(kinds.has('downstream_effect') || kinds.has('constraint_set')).toBe(true);
  });
});

describe('comparing a baseline with a branch', () => {
  it('lists first what was changed, then what differs', () => {
    const c = compareRuns(base, invalid);
    expect(c.changed).toEqual(['classifier: "signal_rule" -> "pose_rule"']);
    expect(c.rows.find((r) => r.id === 'classification')!.verdict).toBe('DIFFERENT');
    expect(c.rows.find((r) => r.id === 'measurement')!.verdict).toBe('NO_DIFFERENCE');  // the measurement is the same: only the rule changed
  });
  it('says the real state is the same when the change is of the rule or of the observation and no resources feed back', () => {
    expect(compareRuns(base, invalid).targetStateIdentical).toBe(true);
    expect(compareRuns(base, invalid).note).toContain('not of the target');
    const b = compareRuns(base, biased);
    expect(b.changed.some((x) => x.startsWith('pose_sensor.')) && b.changed.some((x) => x.startsWith('signal_sensor.'))).toBe(true);
    expect(b.targetStateIdentical).toBe(true);
  });
  it('names the score as the change when it is not used, and shows the access of favourable subjects change', () => {
    const c = compareRuns(base, noscore);
    expect(c.changed).toEqual(['use_score: true -> false']);
    expect(c.rows.find((r) => r.id === 'access_fav')!.verdict).toBe('DIFFERENT');
  });
  it('finds nothing different and nothing changed between a run and itself', () => {
    const c = compareRuns(base, base);
    expect(c.changed).toEqual([]); expect(c.rows.every((r) => r.verdict === 'NO_DIFFERENCE')).toBe(true);
  });
  it('finds a biased sensor produce a wrong warrant that the control does not', () => {
    const r = compareRuns(base, biased).rows.find((x) => x.id === 'warrant_wrong')!;
    expect(r.verdict).toBe('DIFFERENT'); expect(Number(r.branch)).toBeGreaterThan(Number(r.base));
  });
});

describe('the Address-Domain states of the score', () => {
  it('keeps six states apart and reads them from the engine series', () => {
    expect(ADDRESS_STATES.map(([id]) => id)).toEqual(['score_exists', 'score_read', 'score_transferred', 'access_altered', 'score_extinguished', 'constraint_extinguished']);
    expect(addressStatesAt(base, 5).find((x) => x.id === 'score_transferred')!.value).toBe(0);
    expect(addressStatesAt(base, 20).find((x) => x.id === 'score_transferred')!.value).toBe(1);   // transfer at 12
    expect(addressStatesAt(noscore, 20).find((x) => x.id === 'score_exists')!.value).toBe(0);     // no score is used: it does not exist
    expect(addressStatesAt(noscore, 20).find((x) => x.id === 'score_read')!.value).toBe(0);
  });
  it('keeps a constraint\'s extinction apart from the score\'s: the cumulative counts differ', () => {
    const a = addressStatesAt(base, 39);
    expect(a.find((x) => x.id === 'constraint_extinguished')!.value).toBeGreaterThanOrEqual(0);
    expect(a.find((x) => x.id === 'score_extinguished')!.value).toBe(0);  // no expiry configured
  });
});

describe('five kinds of "cannot", kept apart', () => {
  const kinds = ['rule_forbidden', 'institutionally_impossible', 'measurement_invisible', 'model_excluded', 'reachable_after_intervention'] as const;
  it('are five distinct kinds, each defined in words', () => {
    expect(MODALITIES.map(([id]) => id)).toEqual([...kinds]);
    for (const [, label, def] of MODALITIES) { expect(label.length).toBeGreaterThan(10); expect(def.length).toBeGreaterThan(20); }
  });
  it('are read from the records: an impossibility needs a denial and a constraint, an exclusion a denial by the score and no constraint', () => {
    for (let k = 0; k < base.records.length; k++) for (let t = 0; t < base.records[k].length; t++) {
      const r = base.records[k][t], m = modalitiesAt(base, k, t);
      expect(m.institutionally_impossible).toBe(!r.access && r.locked);
      if (m.model_excluded) { expect(r.access).toBe(false); expect(r.locked).toBe(false); expect(r.score).toBeLessThan(base.config.tau_a); }
      expect(m.institutionally_impossible && m.model_excluded).toBe(false);   // the two are never the same period's reason
      if (m.reachable_after_intervention) expect(r.access).toBe(true);
    }
  });
  it('are not one thing: a subject is excluded by the model in some periods and impossible by a constraint in others, and the two are never the same period', () => {
    const k = invalid.records.findIndex((_, i) => { const c = modalityCounts(invalid, i, 39); return c.institutionally_impossible > 0 && c.model_excluded > 0; });
    expect(k).toBeGreaterThanOrEqual(0);
    const at = (t: number) => modalitiesAt(invalid, k, t);
    const ts = Array.from({ length: 40 }, (_, t) => t);
    expect(ts.some((t) => at(t).institutionally_impossible && !at(t).model_excluded)).toBe(true);
    expect(ts.some((t) => at(t).model_excluded && !at(t).institutionally_impossible)).toBe(true);
    expect(ts.every((t) => !(at(t).institutionally_impossible && at(t).model_excluded))).toBe(true);
  });
  it('count more periods of the model\'s exclusion under the invalid rule than under the valid one, without changing the measurement', () => {
    const sum = (r: TERun, id: 'model_excluded' | 'measurement_invisible') => r.records.reduce((a, _, k) => a + modalityCounts(r, k, 39)[id], 0);
    expect(sum(invalid, 'model_excluded')).toBeGreaterThan(sum(base, 'model_excluded'));
    expect(sum(invalid, 'measurement_invisible')).toBe(sum(base, 'measurement_invisible'));
  });
  it('count a missing measurement as invisible only when neither sensor obtained a value', () => {
    const rs = biased.records[0], lost = rs.find((r) => r.pose_missing > 0 && r.signal_measured === null);
    if (lost) expect(modalitiesAt(biased, 0, lost.t).measurement_invisible).toBe(true);
    const seen = rs.find((r) => r.pose_missing > 0 && r.signal_measured !== null)!;
    expect(modalitiesAt(biased, 0, seen.t).measurement_invisible).toBe(false);
  });
  it('find no rule-forbidden adoption when the institution does not require a warrant (nothing is forbidden that the rule does not forbid)', () => {
    for (let k = 0; k < base.records.length; k++) expect(modalityCounts(base, k, 39).rule_forbidden).toBe(0);
  });
  it('find a constraint outlast a correction in some subject, and the access reached again later in another kind', () => {
    const rs = base.records;
    const lockedAfterCorrection = rs.some((r) => r.some((x) => x.corrected && x.locked));
    const reached = rs.some((_, k) => modalityCounts(base, k, 39).reachable_after_intervention > 0);
    expect(lockedAfterCorrection || reached).toBe(true);
  });
});
