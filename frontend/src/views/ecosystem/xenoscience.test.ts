// XENOSCIENCE ECOSYSTEM — the research readings are pure functions of a MEOS record and of the engine's own observation result. The fixtures are real engine output: the stage-two record
// (collapse 149, recovery 161, interventions at 100, 150, 151) and observe() of it under full observation and under a sampling interval of 12 (meos-stage2-observed.json).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { MeosRecord, Observed } from './meosApi';
import { FULL_OBSERVATION } from './meosApi';
import { READING_SOURCES, compareRegimes, criticalIntervals, fiveS, entityObservations, historyConsequence, historyReading, humanDependencies, inventory, operationalStates, provenance, shapeTrack, strongXenoscience, unresolvedItems } from './xenoscience';

const dir = join(dirname(fileURLToPath(import.meta.url)), '__fixtures__');
const rec = JSON.parse(readFileSync(join(dir, 'meos-stage2.json'), 'utf8')) as MeosRecord;
const obsFx = JSON.parse(readFileSync(join(dir, 'meos-stage2-observed.json'), 'utf8')) as Record<'full' | 'coarse', { obs: Record<string, unknown>; observed: Observed }>;
const full = { obs: { ...FULL_OBSERVATION }, observed: obsFx.full.observed, resultDigest: rec.result_digest };
const coarse = { obs: { ...FULL_OBSERVATION, sampling_interval: 12 }, observed: obsFx.coarse.observed, resultDigest: rec.result_digest };

describe('epistemic inventory', () => {
  const inv = inventory(rec, 100, 'A1', full.observed, null);
  it('keeps the evaluator\'s internal state out of the observed group', () => {
    expect(inv.reference.map((r) => r.id)).toEqual(expect.arrayContaining(['stimulus', 'threshold', 'baseline', 'energy', 'position', 'power', 'operational_state', 'true_cycles']));
    for (const r of inv.observed) expect(r.epistemic).toBe('OBSERVED');
    for (const r of inv.reference) expect(r.epistemic).toBe('REFERENCE');
    for (const r of inv.inferred) expect(r.epistemic).toBe('INFERRED');
    const observedIds = inv.observed.map((r) => r.id);
    for (const hidden of ['stimulus', 'threshold', 'energy', 'position', 'operational_state', 'true_cycles']) expect(observedIds).not.toContain(hidden);
  });
  it('reads every value from the record', () => {
    const f = rec.frames[100].A1;
    expect(inv.reference.find((r) => r.id === 'threshold')!.value).toBe(f.theta.toFixed(3));
    expect(inv.reference.find((r) => r.id === 'power')!.value).toBe(rec.frames[100].power.toFixed(3));
    expect(inv.observed.find((r) => r.id === 'observed_cycles')!.value).toBe(String(full.observed.observed_cycles));
  });
  it('declares the class of every reading source, and every internal frame/field source is REFERENCE', () => {
    for (const [k, v] of Object.entries(READING_SOURCES)) {
      expect(v.why.length).toBeGreaterThan(10);
      if (k.startsWith('frames') || k === 'fields' || k === 'traces' || k === 'events' || k.startsWith('status_log')) expect(v.epistemic).toBe('REFERENCE');
    }
    for (const r of [...inv.observed, ...inv.inferred, ...inv.reference]) expect(READING_SOURCES[r.source]).toBeDefined();
  });
  it('marks observed and inferred readings UNRESOLVED when there is no observation result, instead of leaving them empty or inventing them', () => {
    const none = inventory(rec, 100, 'A2', null, null);
    expect(none.observed.length).toBeGreaterThan(0);
    for (const r of [...none.observed, ...none.inferred]) { expect(r.availability).toBe('UNRESOLVED'); expect(r.value.startsWith('unresolved')).toBe(true); }
    expect(none.reference.every((r) => r.availability === 'AVAILABLE')).toBe(true);
  });
  it('clamps the tick into the run', () => {
    expect(() => inventory(rec, 99999, 'A1', full.observed, null)).not.toThrow();
    expect(() => inventory(rec, -5, 'A2', null, null)).not.toThrow();
  });
});

describe('observation regimes', () => {
  it('separates the five kinds of change: a coarser regime changes the apparatus and the record of observation, not the target', () => {
    const c = compareRegimes(full, coarse), row = (k: string) => c.rows.find((r) => r.kind === k)!;
    expect(row('target').verdict).toBe('UNCHANGED');
    expect(row('apparatus').verdict).toBe('CHANGED');
    expect(row('representation').verdict).toBe('CHANGED');
    expect(row('intervention_possibilities').verdict).toBe('UNRESOLVED');
    expect(c.note).toMatch(/not to a newly generated real entity/);
  });
  it('does not call a changed record a changed whole-run classification (here both runs are classed COLLAPSED)', () => {
    const c = compareRegimes(full, coarse);
    expect(full.observed.observed_state).toBe(coarse.observed.observed_state);
    expect(c.rows.find((r) => r.kind === 'classification')!.verdict).toBe('UNCHANGED');
  });
  it('reports nothing changed for the same regime twice', () => {
    const c = compareRegimes(full, full);
    for (const k of ['target', 'apparatus', 'representation', 'classification']) expect(c.rows.find((r) => r.kind === k)!.verdict).toBe('UNCHANGED');
  });
  it('refuses to attribute differences to the observation when the targets differ', () => {
    const c = compareRegimes(full, { ...coarse, resultDigest: 'deadbeef00000000' });
    expect(c.rows.find((r) => r.kind === 'target')!.verdict).toBe('CHANGED');
    expect(c.note).toMatch(/different runs/);
  });
  it('treats an absent optional limit and its explicit default as the same apparatus', () => {
    const c = compareRegimes(full, { ...full, obs: { ...FULL_OBSERVATION, threshold: null, occluder: null } });
    expect(c.rows.find((r) => r.kind === 'apparatus')!.verdict).toBe('UNCHANGED');
  });
});

describe('intervention provenance', () => {
  const p = provenance(rec);
  it('carries the engine, digests and seed of the record', () => {
    expect(p.engine).toBe(rec.engine); expect(p.seed).toBe(rec.seed); expect(p.resultDigest).toBe(rec.result_digest); expect(p.initialConfigDigest).toBe(rec.initial_config_digest);
  });
  it('matches every requested intervention to the engine\'s own log entry (event id included)', () => {
    expect(p.entries).toHaveLength(rec.interventions.length);
    for (const e of p.entries) {
      expect(e.engine).toBe('ACCEPTED');
      const l = rec.intervention_log.find((x) => x.event === e.event)!;
      expect(l.tick).toBe(e.requested.tick); expect(l.op).toBe(e.requested.op);
    }
  });
  it('reports a request the log does not carry as NOT_IN_LOG', () => {
    const extra = { ...rec, interventions: [...rec.interventions, { tick: 5000, op: 'ISOLATE', target: 'history' }] } as MeosRecord;
    const e = provenance(extra).entries.at(-1)!;
    expect(e.engine).toBe('NOT_IN_LOG'); expect(e.event).toBeNull();
  });
  it('reads the first status change after an accepted request from the status log', () => {
    const first = p.entries.find((e) => e.requested.tick === 100)!;
    expect(first.firstStatusChange).toEqual({ tick: 126, label: 'DEGRADED' });
  });
});

describe('critical intervals', () => {
  const iv = (id: string, o: Observed | null = full.observed) => criticalIntervals(rec, o).find((x) => x.id === id)!;
  it('derives formation, cessation and re-ignition from the status log', () => {
    expect(iv('formation').spans).toEqual([[0, 11]]);
    const ces = iv('cessation');
    expect(ces.status).toBe('DERIVED'); expect(ces.spans[0][0]).toBe(149); expect(ces.spans[0][1]).toBe(155);
    expect(iv('re_ignition').spans).toContainEqual([161, 161]);
  });
  it('does not take a failed observation for a cessation', () => {
    const lost = iv('loss_of_access', coarse.observed);
    expect(lost.status).toBe('DERIVED'); expect(lost.spans.length).toBeGreaterThan(0);
    // the observation is lost at ticks where the operation is ACTIVE: the intervals overlap and neither implies the other
    expect(lost.spans.some(([a]) => rec.frames[a].status === 'ACTIVE')).toBe(true);
    // the observation timeline reports COLLAPSED at those ticks, yet the cessation intervals come from the operational status log only
    const cess = (o: Observed) => criticalIntervals(rec, o).find((x) => x.id === 'cessation')!.spans;
    expect(cess(coarse.observed)).toEqual(cess(full.observed));
    expect(cess(full.observed)[0]).toEqual([149, 155]);
  });
  it('lists intervals without imposing an order and marks the unmodelled ones UNSUPPORTED', () => {
    const all = criticalIntervals(rec, full.observed);
    expect(all.map((x) => x.id)).toEqual(['formation', 'observation', 'loss_of_access', 'warrant', 'attribution', 'material_continuation', 'cessation', 're_ignition']);
    for (const id of ['warrant', 'attribution', 'material_continuation']) { expect(all.find((x) => x.id === id)!.status).toBe('UNSUPPORTED'); expect(all.find((x) => x.id === id)!.spans).toEqual([]); }
  });
  it('without an observation result, observation intervals are UNSUPPORTED rather than empty-and-fine', () => {
    expect(iv('observation', null).status).toBe('UNSUPPORTED'); expect(iv('loss_of_access', null).status).toBe('UNSUPPORTED');
  });
  it('reports a run that never collapsed as NOT_OCCURRED', () => {
    const calm = { ...rec, status_log: [{ tick: 0, label: 'DEGRADED', reason: '', dependency: null }, { tick: 11, label: 'ACTIVE', reason: '', dependency: null }] } as MeosRecord;
    expect(criticalIntervals(calm, null).find((x) => x.id === 'cessation')!.status).toBe('NOT_OCCURRED');
    expect(criticalIntervals(calm, null).find((x) => x.id === 're_ignition')!.status).toBe('NOT_OCCURRED');
  });
});

describe('human mediation', () => {
  it('keeps six kinds apart, with no combined score', () => {
    const d = humanDependencies(rec);
    expect(d.map((x) => x.id)).toEqual(['decisions', 'energy', 'maintenance', 'readability', 'approval', 'inherited']);
    expect(JSON.stringify(d)).not.toMatch(/score|total|percent/i);
  });
  it('does not read an unlimited power setting as independence from human supply', () => {
    const inf = { ...rec, final_config: { ...rec.final_config, power: { ...rec.final_config.power, infinite: true } } } as MeosRecord;
    expect(humanDependencies(inf).find((x) => x.id === 'energy')!.state).toBe('ASSUMED_AWAY');
    expect(humanDependencies(rec).find((x) => x.id === 'energy')!.state).toBe('NOT_REPRESENTED');
  });
  it('counts the researcher\'s requested interventions as continuing human decisions, and states what the engine cannot represent', () => {
    const d = humanDependencies(rec);
    expect(d.find((x) => x.id === 'decisions')!.state).toBe('PRESENT_IN_THIS_RUN');
    for (const id of ['maintenance', 'approval']) expect(d.find((x) => x.id === id)!.state).toBe('NOT_REPRESENTED');
  });
});

describe('Strong Xenoscience', () => {
  const s = strongXenoscience(rec);
  it('has the four conditions with evidence statuses and never a score', () => {
    expect(s.conditions.map((c) => c.id)).toEqual([1, 2, 3, 4]);
    const allowed = ['SUPPORTED_WITHIN_DECLARED_CONDITIONS', 'FAILED_WITHIN_DECLARED_CONDITIONS', 'UNTESTED', 'INSUFFICIENT_EVIDENCE'];
    for (const c of s.conditions) { expect(allowed).toContain(c.status); expect(c.needed.length).toBeGreaterThan(20); }
    expect(JSON.stringify(s)).not.toMatch(/"score"|percent|"total"/i);
  });
  it('does not establish the joint classification from a simulator run', () => {
    expect(s.joint).toBe('NOT_ESTABLISHED');
    expect(s.conditions.some((c) => c.status === 'SUPPORTED_WITHIN_DECLARED_CONDITIONS')).toBe(false);
  });
  it('treats an assumed-unlimited supply as insufficient evidence for resource independence', () => {
    const inf = { ...rec, final_config: { ...rec.final_config, power: { ...rec.final_config.power, infinite: true } } } as MeosRecord;
    expect(strongXenoscience(inf).conditions[0].status).toBe('INSUFFICIENT_EVIDENCE');
    expect(s.conditions[0].status).toBe('UNTESTED');
  });
});

describe('Five-S', () => {
  it('treats scale, size and speed as controls, structure as a configuration and sensitivity as a measurement', () => {
    const r = fiveS(rec, null);
    expect(r.map((x) => [x.dimension, x.kind])).toEqual([['scale', 'CONTROL'], ['size', 'CONTROL'], ['speed', 'CONTROL'], ['structure', 'CONFIGURATION'], ['sensitivity', 'MEASURED']]);
    expect(r[4].current).toBe('not measured for this point');
  });
  it('reads sensitivity from the engine\'s SSS classification when there is one', () => {
    const r = fiveS(rec, { scale: 1, size: 1, speed: 1, class: 'x', region: 'OBSERVATION-SENSITIVE', recovery_capable: null, observation_sensitive: true, seeds: [1] });
    expect(r[4].current).toBe('OBSERVATION-SENSITIVE (observation-sensitive)');
  });
});

// ------------------------------------------------------------------------------------------------ the continued stage: unresolved, track, history
const cf = JSON.parse(readFileSync(join(dir, 'meos-coupling-cut.json'), 'utf8')) as Record<'base' | 'cut' | 'history_off', MeosRecord>;

describe('what cannot be settled', () => {
  it('lists the cycles the observation did not record, instead of dropping them', () => {
    const u = unresolvedItems(rec, coarse.observed), hid = coarse.observed.true_cycles - coarse.observed.observed_cycles;
    expect(hid).toBeGreaterThan(0);
    expect(u.find((x) => x.id === 'unobserved_cycles')!.label).toContain(`${hid} of the ${coarse.observed.true_cycles} cycles`);
    expect(u.find((x) => x.id === 'observability_limit')).toBeDefined();
  });
  it('lists nothing about cycles when the observation recorded all of them', () => {
    expect(unresolvedItems(rec, full.observed).find((x) => x.id === 'unobserved_cycles')).toBeUndefined();
  });
  it('says everything is unresolved when there is no observation result', () => {
    expect(unresolvedItems(rec, null)[0].id).toBe('no_observation');
  });
  it('always names what the engine cannot test, and that addressability is not modelled', () => {
    for (const o of [null, full.observed, coarse.observed]) {
      const ids = unresolvedItems(rec, o).map((x) => x.id);
      expect(ids).toEqual(expect.arrayContaining(['intervention_possibilities', 'attribution', 'addressability']));
    }
  });
  it('notes that a collapsed run stops, so later re-ignition is not in the record', () => {
    expect(unresolvedItems(cf.cut, null).some((x) => x.id === 'after_collapse')).toBe(true);
    expect(unresolvedItems(cf.base, null).some((x) => x.id === 'after_collapse')).toBe(false);
  });
});

describe('the track of the operational shape', () => {
  it('covers every tick exactly once, in order, for the operational row', () => {
    const tr = shapeTrack(cf.cut, null);
    expect(tr.length).toBe(cf.cut.frames.length);
    expect(tr.operational[0].from).toBe(0); expect(tr.operational.at(-1)!.to).toBe(tr.length - 1);
    for (let i = 1; i < tr.operational.length; i++) { expect(tr.operational[i].from).toBe(tr.operational[i - 1].to + 1); expect(tr.operational[i].label).not.toBe(tr.operational[i - 1].label); }
    expect(tr.observed).toBeNull();
  });
  it('places formation, the interventions and the collapse at the ticks of the engine\'s own logs', () => {
    const m = shapeTrack(cf.cut, null).marks, at = (k: string) => m.filter((x) => x.kind === k).map((x) => x.tick);
    expect(at('formation')).toEqual([11]); expect(at('intervention')).toEqual([100, 150]); expect(at('cessation')).toEqual([149]);
    expect(m.map((x) => x.tick)).toEqual([...m.map((x) => x.tick)].sort((a, b) => a - b));
  });
  it('marks the re-ignition of the stage-two run and the divergence from a baseline when one is given', () => {
    expect(shapeTrack(rec, null).marks.find((x) => x.kind === 'reignition')!.tick).toBe(161);
    expect(shapeTrack(cf.cut, null, 126).marks.find((x) => x.kind === 'divergence')!.tick).toBe(126);
    expect(shapeTrack(cf.cut, null).marks.some((x) => x.kind === 'divergence')).toBe(false);
  });
  it('keeps the observed row apart: under the coarse observation it reads COLLAPSED at ticks where the operation is ACTIVE', () => {
    const tr = shapeTrack(rec, coarse.observed);
    expect(tr.observed).not.toBeNull();
    const at = (rows: NonNullable<typeof tr.observed>, t: number) => rows.find((s) => s.from <= t && t <= s.to)!.label;
    expect(at(tr.operational, 60)).toBe('ACTIVE'); expect(at(tr.observed!, 60)).toBe('COLLAPSED');
    expect(shapeTrack(rec, full.observed).observed!.map((s) => s.label)).toEqual(tr.operational.map((s) => s.label));
  });
});

describe('history: retention, addressability, re-entry, consequence', () => {
  it('reads retention and re-entry from the record, tick by tick', () => {
    const h = historyReading(cf.base, 200), f = cf.base.frames[200];
    expect(h.retention.A1).toBe(f.A1.h); expect(h.retention.A2).toBe(f.A2.h); expect(h.retention.enabled).toBe(true);
    expect(h.reentry.A1).toBe(f.A1.reentry);
    const upTo = cf.base.cycles.filter((c) => c.tick <= 200);
    expect(h.reentry.ofCycles).toBe(upTo.length); expect(h.reentry.cycles).toBe(upTo.filter((c) => c.history_reentry).length);
    expect(h.reentry.cycles).toBeGreaterThan(0);
  });
  it('counts re-entry cycles that grow with the tick and never exceed the cycles', () => {
    let prev = 0;
    for (const t of [20, 100, 200, 359]) { const r = historyReading(cf.base, t).reentry; expect(r.cycles).toBeGreaterThanOrEqual(prev); expect(r.cycles).toBeLessThanOrEqual(r.ofCycles); prev = r.cycles; }
  });
  it('says addressability is not modelled instead of inventing it', () => {
    expect(historyReading(cf.base, 50).addressability.status).toBe('NOT_MODELLED');
  });
  it('shows the history as disabled after the intervention (the re-entry channel is read from the record)', () => {
    expect(historyReading(cf.history_off, 99).retention.enabled).toBe(true);
    expect(historyReading(cf.history_off, 120).retention.enabled).toBe(false);
  });
  it('finds an effective consequence of re-entry in this run: the history-disabled run differs (engine output)', () => {
    const c = historyConsequence(cf.base, cf.history_off);
    expect(c.verdict).toBe('DIFFERS');
    expect(c.base).toEqual({ label: 'ACTIVE', cycles: 71, reentryCyclesInFinalWindow: 9 });
    expect(c.withoutHistory).toEqual({ label: 'COLLAPSED', cycles: 22, reentryCyclesInFinalWindow: 0 });
    expect(c.firstStatusDivergence).toBe(136);
  });
  it('reports no effect when the two runs are the same run, and limits the claim to this run', () => {
    const c = historyConsequence(cf.base, cf.base);
    expect(c.verdict).toBe('NO_DIFFERENCE_IN_THIS_RUN'); expect(c.firstStatusDivergence).toBeNull();
    expect(c.note).toMatch(/does not show that there is none elsewhere/);
    expect(historyConsequence(cf.base, cf.history_off).note).toMatch(/this configuration and seed/);
  });
});

describe('the six states of the operation, each with its basis', () => {
  const st = (r: MeosRecord, o: Observed | null, t: number) => operationalStates(r, o, t);
  const by = (r: MeosRecord, o: Observed | null, t: number, id: string) => st(r, o, t).states.find((x) => x.id === id)!;
  it('reads each state from the engine\'s logs, with the rule and the values it used', () => {
    const s = st(rec, full.observed, 100);
    expect(s.states.map((x) => x.id)).toEqual(['formation', 'maintenance', 'transformation', 'cessation', 're_ignition', 'reconfiguration']);
    for (const x of s.states) { expect(x.rule.length).toBeGreaterThan(20); expect(x.observationCondition.length).toBeGreaterThan(10); }
    expect(by(rec, full.observed, 100, 'formation').spans).toEqual([[0, 11]]);
    expect(by(rec, full.observed, 100, 'cessation').spans[0]).toEqual([149, 155]);
    expect(by(rec, full.observed, 100, 're_ignition').spans).toContainEqual([161, 161]);
    expect(by(rec, full.observed, 100, 'cessation').engineValues.join(' ')).toContain('no complete cycle in the last 48 ticks');
  });
  it('says at the playhead tick which rules hold, and they need not be in order', () => {
    const at = (t: number) => st(rec, full.observed, t).states.filter((x) => x.holdsAt).map((x) => x.id);
    expect(at(5)).toContain('formation'); expect(at(5)).not.toContain('maintenance');
    expect(at(60)).toEqual(['maintenance']);
    expect(at(150)).toContain('cessation');
    expect(at(161)).toEqual(expect.arrayContaining(['re_ignition', 'maintenance']));  // two rules hold at once
  });
  it('maps interventions to transformation or reconfiguration by the engine\'s operation names, and leaves other operations out of both', () => {
    const r = by(rec, null, 100, 'reconfiguration'), tf = by(rec, null, 100, 'transformation');
    expect(r.spans).toEqual([[100, 100], [150, 150], [190, 190]].filter(([t]) => rec.interventions.some((i) => i.tick === t && ['ISOLATE', 'RECONNECT', 'REMOVE', 'ROUTE', 'DISABLE_HISTORY'].includes(i.op))));
    expect(tf.engineValues.join(' ')).not.toContain('ISOLATE');
    expect(rec.interventions.some((i) => i.op === 'ALTER_RESOURCE')).toBe(true);
    expect(`${r.engineValues} ${tf.engineValues}`).not.toContain('ALTER_RESOURCE');
  });
  it('states what the observation could see: equal statuses at all ticks under full observation, limited ticks under the coarse one', () => {
    expect(by(rec, full.observed, 60, 'maintenance').observationCondition).toMatch(/equals the operational status at (\d+) of \1 ticks/);
    expect(by(rec, coarse.observed, 60, 'maintenance').observationCondition).toContain('the observation is limited');
    expect(by(rec, null, 60, 'maintenance').observationCondition).toContain('no observation result');
  });
  it('says nothing to observe when a rule never holds, and does not judge the shape ontologically', () => {
    const calm = st(cf.base, null, 100);
    expect(calm.states.find((x) => x.id === 'cessation')!.spans).toEqual([]);
    expect(calm.states.find((x) => x.id === 'cessation')!.engineValues).toEqual([]);
    expect(calm.note).toMatch(/not a judgement that an operational shape was in fact formed/);
    expect(st(cf.base, full.observed, 100).states.find((x) => x.id === 'cessation')!.observationCondition).toContain('does not hold anywhere');
  });
});

describe('the reference and the observation of one entity', () => {
  it('keeps the reference cell and activity apart from what the observation can see of it', () => {
    const e = entityObservations(rec, { ...FULL_OBSERVATION, region: [8, 8, 12, 12] }, 60, null)[0];
    expect(e.reference.cell).toEqual([rec.frames[60].A1.x, rec.frames[60].A1.y]);
    expect(e.observation.cellSeen).toBe(false);
    expect(e.reading).toContain('in a cell the observation does not see: its state is not observed');
    expect(e.observation.observedStatus).toBeNull();
  });
  it('sees an entity in a seen cell only at a sampled tick', () => {
    const at = (t: number) => entityObservations(rec, { ...FULL_OBSERVATION, sampling_interval: 3 }, t, full.observed)[0];
    expect(at(60).observation.tickSampled).toBe(true); expect(at(61).observation.tickSampled).toBe(false);
    expect(at(61).reading).toContain('not a sampled tick');
    expect(at(60).reading).toContain('events there can be observed');
  });
  it('agrees with the lattice rule used for the overlay and with the engine\'s regimes (an entity on the lattice cell is seen)', () => {
    const a1 = rec.frames[100].A1;
    expect(entityObservations(rec, { ...FULL_OBSERVATION, spatial_stride: 2, spatial_offset: [1, 0] }, 100, null)[0].observation.cellSeen).toBe(a1.x % 2 === 1 && a1.y % 2 === 0);
    expect(entityObservations(rec, { ...FULL_OBSERVATION, occluder: [a1.x, a1.y, a1.x, a1.y] }, 100, null)[0].observation.cellSeen).toBe(false);
  });
  it('reports an absent entity as absent', () => {
    const gone = JSON.parse(readFileSync(join(dir, 'meos-a2-removed.json'), 'utf8')) as MeosRecord;
    const t = gone.frames.findIndex((f) => !f.A2.present);
    expect(entityObservations(gone, FULL_OBSERVATION, t, null)[1].reading).toContain('absent in the record');
  });
});

describe('traceability of the six states: every span can be checked against a source the rule did not read', () => {
  const records: Array<[string, MeosRecord]> = [['stage2', rec], ['base', cf.base], ['cut', cf.cut], ['history_off', cf.history_off]];
  const inSpans = (spans: Array<[number, number]>, t: number) => spans.some(([a, b]) => a <= t && t <= b);
  it('derives maintenance and cessation from the status log, and the frames\' own status field (an independent source) agrees at every tick', () => {
    for (const [name, r] of records) {
      const st = operationalStates(r, null, 0).states, m = st.find((x) => x.id === 'maintenance')!, c = st.find((x) => x.id === 'cessation')!;
      for (let t = 0; t < r.frames.length; t++) {
        expect(inSpans(m.spans, t), `${name} maintenance t=${t}`).toBe(r.frames[t].status === 'ACTIVE');
        expect(inSpans(c.spans, t), `${name} cessation t=${t}`).toBe(r.frames[t].status === 'COLLAPSED');
      }
    }
  });
  it('places formation, re-ignition and the intervention states at ticks the logs carry', () => {
    for (const [name, r] of records) {
      const st = operationalStates(r, null, 0).states;
      const first = r.status_log.find((e) => e.label === 'ACTIVE');
      expect(st.find((x) => x.id === 'formation')!.spans, name).toEqual(first ? [[0, first.tick]] : []);
      for (const [a] of st.find((x) => x.id === 're_ignition')!.spans) {
        const i = r.status_log.findIndex((e) => e.tick === a && e.label === 'ACTIVE');
        expect(i, `${name} re-ignition t=${a}`).toBeGreaterThan(0);
        expect(r.status_log.slice(0, i).some((e) => e.label === 'COLLAPSED')).toBe(true);
      }
      for (const id of ['transformation', 'reconfiguration'] as const) for (const [a] of st.find((x) => x.id === id)!.spans) expect(r.interventions.some((iv) => iv.tick === a), `${name} ${id} t=${a}`).toBe(true);
    }
  });
  it('names the record fields each rule reads, the rule, and the observation condition, for every state', () => {
    for (const x of operationalStates(rec, full.observed, 100).states) {
      expect(x.reads.length, x.id).toBeGreaterThan(0);
      for (const f of x.reads) expect(['status_log', 'cycles', 'interventions', 'final_status.dependency']).toContain(f);
      expect(x.rule.length).toBeGreaterThan(20); expect(x.observationCondition.length).toBeGreaterThan(10);
    }
  });
  it('makes no ontological judgement, as data and in words, whatever the record', () => {
    for (const [name, r] of records) {
      const o = operationalStates(r, full.observed, 100);
      expect(o.ontologicalJudgement, name).toBe('NOT_MADE');
      const words = JSON.stringify(o).toLowerCase();
      for (const bad of ['was formed', 'is formed', 'proves', 'proved', 'established that', 'genuine', 'truly', 'real operational shape']) expect(words, `${name}: ${bad}`).not.toContain(bad);
    }
  });
  it('lets the observation change only what it could see of a state, never the span the engine\'s logs give', () => {
    const spans = (o: Observed | null) => operationalStates(rec, o, 100).states.map((x) => JSON.stringify(x.spans));
    expect(spans(coarse.observed)).toEqual(spans(full.observed)); expect(spans(null)).toEqual(spans(full.observed));
    const obsc = (o: Observed | null) => operationalStates(rec, o, 100).states.map((x) => x.observationCondition);
    expect(obsc(coarse.observed)).not.toEqual(obsc(full.observed));
  });
});

