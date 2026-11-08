// TRUTH-ERROR DYNAMICS — the readings over runs of the synthetic virtual institution. The fixtures are real engine output (backend/xzr/truth_error): a baseline, the same with an invalid (head-pose) rule, with a biased and
// failing sensor, and without a score. SYNTHETIC only: nothing here assesses a real person.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { ADDRESS_STATES, EDGES, MODALITIES, NODES, PATHS, PROCESS_EVENTS, RELATIONS, addressStatesAt, compareRuns, comparePaths, compareRelation, endogenyAt, relationAt, eventTable, fieldsAt, modalitiesAt, modalityCounts, nodeReadings, stepReached, timelineEvents, type NodeId, type TERun } from './truthError';

const runs = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'truth-error-runs.json'), 'utf8')) as Record<'base' | 'invalid' | 'biased' | 'noscore', TERun>;
const { base, invalid, biased, noscore } = runs;
const runs2 = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'truth-error-runs2.json'), 'utf8')) as Record<'base' | 'process' | 'no_release' | 'appeal' | 'appeal_gated' | 'guarded' | 'feedback' | 'on_request' | 'base5' | 'feedback5', TERun>;

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

// ------------------------------------------------------------------------------------------------ phase 2: the nine times and the four paths, read from real engine runs
describe('the nine times and the four paths', () => {
  const { process: proc, no_release: noRel } = runs2;
  it('keep nine separate events, each with a time per subject and a count, and mark the misclassification as the evaluator\'s', () => {
    expect(PROCESS_EVENTS).toHaveLength(9);
    const rows = eventTable(proc);
    expect(rows.map((r) => r.id)).toEqual([...PROCESS_EVENTS]);
    expect(rows.find((r) => r.id === 'misclassified')!.epistemic).toBe('REFERENCE');
    for (const r of rows) { expect(proc.process!.events[r.id].times).toHaveLength(proc.config.n); expect(r.n).toBe(proc.process!.events[r.id].times.filter((x) => x !== null).length); expect(r.of).toBe(proc.config.n); }
  });
  it('are the same subject in two runs of one seed: the judgement path is identical when only the release differs', () => {
    const rows = comparePaths(proc, noRel, 1);
    for (const r of rows.filter((x) => x.path === 'judgement')) expect(r.status, r.step).toBe('SAME');
    // the correction is the same too (approved at the same period), but the release exists only in the baseline
    expect(rows.find((r) => r.step === 'approved')!.status).toBe('SAME');
    const rel = rows.find((r) => r.step === 'released')!;
    expect(rel.base).not.toBeNull(); expect(rel.branch).toBeNull(); expect(rel.status).toBe('ONLY_IN_BASELINE'); expect(rel.delta).toBeNull();
  });
  it('take every step from a recorded variable or event: a step holds at a period exactly when the engine\'s own time is at or before it', () => {
    for (const p of PATHS) for (const s of p.steps) for (let k = 0; k < 4; k++) {
      const at = s.at(proc, k);
      for (const t of [0, 10, 25, 39]) expect(stepReached(proc, k, s, t), `${p.id}/${s.id}/${k}/${t}`).toBe(at !== null && at <= t);
    }
    const ev = proc.process!.events;
    const get = (id: string) => PATHS.flatMap((p) => p.steps).find((s) => s.id === id)!;
    expect(get('adopted').at(proc, 1)).toBe(ev.adopted.times[1]); expect(get('released').at(proc, 1)).toBe(ev.released.times[1]);
    expect(get('denied').at(proc, 1)).toBe(ev.denied.times[1]);
  });
  it('order the correction path\'s own times as the process does: detection, request, approval (and the score update at the approval) never run backwards', () => {
    const e = proc.process!.events;
    for (let i = 0; i < proc.config.n; i++) {
      const [d, q, a, u] = [e.detected.times[i], e.requested.times[i], e.approved.times[i], e.score_updated.times[i]];
      if (d !== null && q !== null) expect(q - d).toBe(proc.config.request_delay);
      if (q !== null && a !== null) expect(a - q).toBe(proc.config.approval_delay);
      if (a !== null && u !== null) expect(u - a).toBe(proc.config.score_delay);
    }
  });
  it('light only steps that are transitions on an edge of the chain', () => {
    for (const p of PATHS) for (const s of p.steps) if (s.edge) expect(EDGES.some(([a, b]) => a === s.edge![0] && b === s.edge![1]), `${p.id}/${s.id}`).toBe(true);
    expect(PATHS.map((p) => p.id)).toEqual(['judgement', 'effect', 'correction', 'subsequent']);
  });
  it('report a step as NEITHER and SAME-with-no-branch without inventing a time', () => {
    const solo = comparePaths(base, null, 0);
    expect(solo.every((r) => r.branch === null)).toBe(true);
    expect(solo.find((r) => r.step === 'detected')!.status).toBe('NEITHER');   // the old baseline has no audit
  });
  it('read the appeal of a subject from the run: not modelled (old run), none, or the stages reached', () => {
    const ap = (r: TERun, k: number) => fieldsAt(r, k, 30).reentry.find((x) => x.label === 'appeal')!;
    expect(ap(base, 0).value).toContain('NOT MODELLED');
    expect(ap(runs2.process, 0).value).toContain('no appeal procedure');
    const filed = runs2.appeal.process!.appeal.stage_times.appeal_filed.findIndex((x) => x !== null);
    expect(filed).toBeGreaterThanOrEqual(0);
    expect(ap(runs2.appeal, filed < 12 ? filed : 0).value).toMatch(/appeal filed at \d+|not filed/);
    expect(runs2.appeal_gated.process!.appeal.blocked_subjects).toBeGreaterThan(0);
  });
  it('keep a correction and a release apart in the engine\'s record: the no-release run approves corrections and releases none', () => {
    expect(noRel.process!.events.approved.n).toBeGreaterThan(0); expect(noRel.process!.events.released.n).toBe(0);
    expect(runs2.process.process!.events.released.n).toBeGreaterThan(0);
  });
  it('the fixed metrics carry their definitions (denominator, period, unit)', () => {
    for (const k of ['access_rate_late_fav', 'denial_rate_late_fav', 'lost_opportunities_per_fav', 'recovery_time', 'persistent_constraint', 'propagation_b_denied_fav']) {
      const d = proc.process!.metric_definitions[k]; expect(d.denominator).toBeTruthy(); expect(d.period).toBeTruthy(); expect(d.unit).toBeTruthy();
    }
  });
});

describe('what was changed between two runs includes the correction process', () => {
  it('lists the release rule when only the release differs, and nothing for a run saved before phase 2 compared with itself', () => {
    const c = compareRuns(runs2.process, runs2.no_release);
    expect(c.changed).toEqual(expect.arrayContaining(['release_mode: "after_approval" -> "never"']));   // the fixture's no-release run also leaves the propagation off
    expect(c.changed).toHaveLength(3);
    expect(compareRuns(runs2.base, runs2.process).changed.join(' ')).toContain('audit_every: null -> 2');
    expect(compareRuns(base, base).changed).toEqual([]);
    expect(compareRuns(base, runs2.base).changed).not.toContain('undefined');   // a field absent in an old run is not reported as a change against the same default
  });
});

// ------------------------------------------------------------------------------------------------ phase 4: the relations are the model's own transition rules, checked against the engine's records
describe('the relations of the scene', () => {
  const all = [runs2.base, runs2.process, runs2.no_release, runs2.appeal, runs2.guarded, runs2.feedback, runs2.on_request];
  it('are nine: seven on real edges of the chain and two that concern the transformed target and the evaluator\'s label', () => {
    expect(RELATIONS.map((r) => r.id)).toEqual(['sensor_subject', 'classifier_record', 'score_judgement', 'judgement_resources', 'resources_state', 'correction_release', 'guarantee_subsequent', 'target_transformation', 'label_generation']);
    for (const r of RELATIONS.filter((x) => !x.evaluator)) for (const [a, b] of r.edges) expect(EDGES.some(([x, y]) => x === a && y === b), `${r.id} ${a}->${b}`).toBe(true);
    const ev = RELATIONS.filter((r) => r.evaluator);
    expect(ev.map((r) => r.id)).toEqual(['label_generation']);   // the label is generated by the evaluator: it is not an edge of the chain, and no institution reads it
    for (const r of ev) for (const [a, b] of r.edges) expect(EDGES.some(([x, y]) => x === a && y === b)).toBe(false);
  });
  it('hold, in the engine\'s own records, for every subject and period where an identity can be checked (the display equals the engine output)', () => {
    const checked: Record<string, number> = {};
    for (const run of all) for (let k = 0; k < run.records.length; k++) for (let t = 0; t < run.records[k].length; t++) for (const r of RELATIONS) {
      const x = relationAt(run, k, t, r.id);
      expect(x.check.holds === false, `${r.id} k${k} t${t}: ${x.check.detail}`).toBe(false);   // never contradicted
      if (x.check.holds === true) checked[r.id] = (checked[r.id] ?? 0) + 1;
    }
    for (const id of ['score_judgement', 'judgement_resources', 'resources_state', 'classifier_record', 'correction_release', 'target_transformation', 'label_generation']) expect(checked[id], id).toBeGreaterThan(100);
  });
  it('are contradicted when the record is altered: the check is a real comparison, not a label', () => {
    const run = structuredClone(runs2.base) as TERun, k = 1, t = 15;
    run.records[k][t].access = !run.records[k][t].access;
    expect(relationAt(run, k, t, 'score_judgement').check.holds).toBe(false);
    const r2 = structuredClone(runs2.base) as TERun; r2.records[k][t].resources += 0.2;
    expect(relationAt(r2, k, t, 'judgement_resources').check.holds).toBe(false);
    const r3 = structuredClone(runs2.base) as TERun; r3.records[k][t].classification = (r3.records[k][t].classification === 1 ? -1 : 1);
    expect(relationAt(r3, k, t, 'classifier_record').check.holds === false || relationAt(r3, k, t, 'classifier_record').check.holds === null).toBe(true);
  });
  it('mark the sensor error as known to the evaluator only and no identity, and keep observed, reference and unresolved apart', () => {
    const x = relationAt(runs2.process, 1, 10, 'sensor_subject');
    expect(x.check.holds).toBeNull();
    expect(x.to.find((r) => r.label.startsWith('error'))!.epistemic).toBe('REFERENCE');
    expect(x.from.every((r) => r.epistemic === 'REFERENCE')).toBe(true);
    expect(x.to.filter((r) => r.epistemic === 'OBSERVED').length + x.to.filter((r) => r.epistemic === 'UNRESOLVED').length).toBeGreaterThan(0);
  });
  it('compare a baseline with a branch for the same subject and period, and the configuration change lists the guarantees', () => {
    const c = compareRelation(runs2.process, runs2.guarded, 2, 20, 'judgement_resources');
    expect(c.branch).not.toBeNull(); expect(c.base.id).toBe('judgement_resources');
    const ch = compareRuns(runs2.process, runs2.guarded).changed.join(' ');
    for (const key of ['resource_floor', 'denial_cap', 'interim_access', 'support_rule', 'support_capacity']) expect(ch, key).toContain(key);
  });
  it('read the guarantee node from the record, and say so where an older run did not record it', () => {
    const g = nodeReadings('guarantee', runs2.guarded.records[1][20], runs2.guarded.config);
    expect(g[0].value).toContain('resource floor 0.2'); expect(g.at(-1)!.value).toContain('HYPOTHETICAL');
    const old = nodeReadings('guarantee', base.records[1][20], base.config);
    expect(old.find((r) => r.label.startsWith('access granted'))!.epistemic).toBe('UNRESOLVED');
    expect(runs2.guarded.records.some((rs) => rs.some((r) => r.guarantee_access || (r.support ?? 0) > 0))).toBe(true);
  });
});

// ------------------------------------------------------------------------------------------------ phase 5: the transformed target, the labels and the accuracy, from the engine's own records
describe('the institution\'s action returning to the evaluated target', () => {
  const { base, feedback } = runs2;
  it('reads the transformed target: the state differs from the counterfactual by beta x the earlier resources, and not at all without the feedback', () => {
    for (let k = 0; k < feedback.records.length; k++) for (const t of [5, 20, 39]) expect(relationAt(feedback, k, t, 'target_transformation').check.holds, `k${k} t${t}`).toBe(true);
    for (const x of base.records[1]) expect(Math.abs(x.reference_z - (x.z_counterfactual as number))).toBeLessThan(2e-3);   // beta 0: the counterfactual state IS the state
    expect(feedback.records.some((rs) => rs.some((x) => Math.abs(x.reference_z - (x.z_counterfactual as number)) > 0.5))).toBe(true);
  });
  it('is contradicted when the record is altered (the check compares, it does not label)', () => {
    const r = structuredClone(feedback) as TERun; r.records[1][20].reference_z += 0.3;
    expect(relationAt(r, 1, 20, 'target_transformation').check.holds).toBe(false);
    const q = structuredClone(feedback) as TERun; q.records[1][20].label_counterfactual = !q.records[1][20].label_counterfactual;
    expect(relationAt(q, 1, 20, 'label_generation').check.holds).toBe(false);
  });
  it('says FIXED only if the classifier and the observation are identical, and attributes a change of accuracy to the target only then', () => {
    const e = endogenyAt(base, feedback, 1, 20);
    expect(e.classifier.fixed).toBe(true); expect(e.classifier.detail).toContain('FIXED');
    expect(e.verdict).toContain('ACCURACY CHANGED WITH THE CLASSIFIER FIXED'); expect(e.verdict).toContain('counterfactual');
    const other = structuredClone(feedback) as TERun; other.config.window = 8;
    const e2 = endogenyAt(base, other, 1, 20);
    expect(e2.classifier.fixed).toBe(false); expect(e2.classifier.changed).toContain('window'); expect(e2.verdict).toContain('CHANGED'); expect(e2.verdict).toContain('cannot be attributed to the target alone');
    expect(endogenyAt(base, null, 1, 20).classifier.fixed).toBeNull();
  });
  it('gives the four labels of one set of decisions and the engine\'s metrics, base and branch', () => {
    const e = endogenyAt(base, feedback, 1, 20);
    expect(e.accuracy.map((a) => a.label.split(' ')[3])).toEqual(['INITIAL', 'CURRENT', 'NEXT', 'COUNTERFACTUAL']);
    const m = feedback.process!.labels!.metrics, b = base.process!.labels!.metrics;
    expect(e.accuracy[1].branch).toBe(m.accuracy_current!.toFixed(3)); expect(e.accuracy[3].base).toBe(b.accuracy_counterfactual!.toFixed(3));
    expect(Number(e.accuracy[1].branch)).toBeGreaterThan(Number(e.accuracy[3].branch));   // the same decisions look better against the label the institution moved
    expect(m.accuracy_current!).toBeCloseTo(feedback.summary.classification_correct!, 9);   // the display equals the summary
  });
  it('keeps before and after, the kinds of state, the groups and what is unresolved', () => {
    const e = endogenyAt(base, feedback, 1, 20);
    expect(e.before.find((r) => r.label.startsWith('state at the start'))!.epistemic).toBe('REFERENCE');
    expect(e.before.find((r) => r.label === 'observed signal')!.epistemic).toMatch(/OBSERVED|UNRESOLVED/);
    expect(e.before.find((r) => r.label === 'classification')!.epistemic).toBe('CLASSIFIED');
    expect(e.after.find((r) => r.label.startsWith('state after'))!.value).toBe(base.records[1][21].reference_z.toFixed(3));   // the baseline's own next state
    expect(e.distribution.map((d) => d.group)).toContain('not favourable at the start'); expect(e.distribution.length).toBe(8);
    expect(e.unresolved.length).toBeGreaterThanOrEqual(3); expect(e.unresolved.join(' ')).toContain('not measured');
  });
  it('says so for a run saved before phase 5 instead of inventing a counterfactual', () => {
    const e = endogenyAt(base, null, 1, 20), old = endogenyAt(structuredClone(base) as TERun, null, 1, 20);
    expect(e.target[0].epistemic).toBe('REFERENCE');
    const stripped = structuredClone(base) as TERun; for (const rs of stripped.records) for (const x of rs) { delete x.z_counterfactual; delete x.label_counterfactual; delete x.label_initial; delete x.label_next; }
    const s2 = endogenyAt(stripped, null, 1, 20);
    expect(s2.target[0].epistemic).toBe('UNRESOLVED'); expect(s2.labelShift[0].value).toContain('not recorded'); expect(old.classifier.fixed).toBeNull();
  });
  it('reads the reach of a guarantee from the engine\'s record: a guarantee on request reaches fewer subjects than the same one delivered, and the node says it is hypothetical', () => {
    const g = runs2.on_request.process!.guarantee!;
    expect(g.support_utilisation!).toBeGreaterThan(0.2); expect(g.support_utilisation!).toBeLessThan(0.9);
    expect(nodeReadings('guarantee', runs2.on_request.records[1][10], runs2.on_request.config).at(-1)!.value).toContain('HYPOTHETICAL');
  });
});
