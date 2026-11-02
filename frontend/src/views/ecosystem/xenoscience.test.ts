// XENOSCIENCE ECOSYSTEM — the research readings are pure functions of a MEOS record and of the engine's own observation result. The fixtures are real engine output: the stage-two record
// (collapse 149, recovery 161, interventions at 100, 150, 151) and observe() of it under full observation and under a sampling interval of 12 (meos-stage2-observed.json).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { MeosRecord, Observed } from './meosApi';
import { FULL_OBSERVATION } from './meosApi';
import { READING_SOURCES, compareRegimes, criticalIntervals, fiveS, humanDependencies, inventory, provenance, strongXenoscience } from './xenoscience';

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
