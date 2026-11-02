// XENOSCIENCE ECOSYSTEM — research readings over a MEOS record. Pure functions: nothing here runs the engine, edits a record or draws. Every value is read from the record or from
// the engine's observation result; what each reading IS (observed, inferred, or the evaluator's reference state) is declared once in READING_SOURCES and tested, so that a hidden reference
// state is never shown as a measurement. The module states what the engine cannot establish (UNRESOLVED / UNSUPPORTED) instead of filling it in.

import { FULL_OBSERVATION, adAt, type Intervention, type Label, type MeosRecord, type Observation, type Observed, type PathActivity, type SssClassOut } from './meosApi';

export type Epistemic = 'OBSERVED' | 'INFERRED' | 'REFERENCE';
export type Availability = 'AVAILABLE' | 'UNRESOLVED';

/** Where each kind of reading comes from, and why it has the class it has. The observer of MEOS sees complete firing cycles through the observation array and nothing else: everything
 *  the evaluator reads from the entities' internal state is REFERENCE. */
export const READING_SOURCES: Record<string, { epistemic: Epistemic; why: string }> = {
  'observed.observed_state': { epistemic: 'OBSERVED', why: 'the status computed with the evaluator\'s criteria from the cycles the configured observation array recorded' },
  'observed.observed_cycles': { epistemic: 'OBSERVED', why: 'complete cycles recorded through the configured sampling interval, lattice, region, aggregation and window' },
  'observed.observed_trajectory': { epistemic: 'OBSERVED', why: 'the observed status at each tick, from the recorded cycles only' },
  'observed.timeline.observed': { epistemic: 'OBSERVED', why: 'the observed status per tick' },
  'observed.observability': { epistemic: 'INFERRED', why: 'found by relaxing each observation parameter in turn to full resolution and testing whether agreement returns: a declared analytical procedure, not a recording' },
  'observed.limiting_parameters': { epistemic: 'INFERRED', why: 'the parameters whose relaxation restores agreement (same procedure)' },
  'paths': { epistemic: 'INFERRED', why: 'activity of the five operational paths computed by the analysis from the record\'s reference signals; not an observation' },
  'observed.operational_state': { epistemic: 'REFERENCE', why: 'the status of the run itself, evaluated on the internal state; not available to the observer' },
  'observed.true_cycles': { epistemic: 'REFERENCE', why: 'every cycle the run contains, observed or not' },
  'frames.entity': { epistemic: 'REFERENCE', why: 'stimulus, baseline, threshold, energy, history trace, position: the entity\'s internal state at a tick, read by the evaluator' },
  'frames.power': { epistemic: 'REFERENCE', why: 'the finite reserve from which the environment is renewed' },
  'fields': { epistemic: 'REFERENCE', why: 'the resource and alteration fields of the arena' },
  'traces': { epistemic: 'REFERENCE', why: 'intermediate quantities of the engine, which the status never reads' },
  'status_log.dependency': { epistemic: 'REFERENCE', why: 'the failed precondition, computed by the engine from internal values' },
  'events': { epistemic: 'REFERENCE', why: 'the engine\'s own event log (fire, act, cycle, status, intervention...)' },
};

export interface Reading { id: string; label: string; value: string; epistemic: Epistemic; availability: Availability; source: string; why: string }

const fmt = (x: unknown): string => (typeof x === 'number' ? (Number.isInteger(x) ? String(x) : x.toFixed(3)) : x === null || x === undefined ? '-' : String(x));
const mk = (id: string, label: string, value: unknown, source: keyof typeof READING_SOURCES, availability: Availability = 'AVAILABLE', note?: string): Reading =>
  ({ id, label, value: availability === 'UNRESOLVED' ? `unresolved${note ? `: ${note}` : ''}` : fmt(value), epistemic: READING_SOURCES[source].epistemic, availability, source, why: READING_SOURCES[source].why });

export interface Inventory { observed: Reading[]; inferred: Reading[]; reference: Reading[] }

/** The operational shape inspector's readings for one entity at one tick, grouped by epistemic status. ``observed`` null means that no observation result is available: the observed and
 *  inferred groups are then UNRESOLVED, not empty, and the reference group is still listed (as reference). */
export function inventory(rec: MeosRecord, tick: number, entity: 'A1' | 'A2', observed: Observed | null, paths: PathActivity | null, missing = 'no observation result for this run (run with an observation configuration)'): Inventory {
  const t = Math.max(0, Math.min(tick, rec.frames.length - 1)), f = rec.frames[t], e = f[entity];
  const un = (id: string, label: string, source: keyof typeof READING_SOURCES) => mk(id, label, null, source, 'UNRESOLVED', missing);
  const obs: Reading[] = observed ? [
    mk('observed_state', 'observed status (whole run)', observed.observed_state, 'observed.observed_state'),
    mk('observed_cycles', 'cycles recorded by the observation array', observed.observed_cycles, 'observed.observed_cycles'),
    mk('observed_at_tick', `observed status at tick ${t}`, observed.observed_trajectory[t] ?? null, 'observed.observed_trajectory', observed.observed_trajectory[t] === undefined ? 'UNRESOLVED' : 'AVAILABLE', 'outside the observed trajectory'),
  ] : [un('observed_state', 'observed status (whole run)', 'observed.observed_state'), un('observed_cycles', 'cycles recorded by the observation array', 'observed.observed_cycles')];
  const inf: Reading[] = [
    ...(observed ? [
      mk('observability', 'observability status', observed.observability.status, 'observed.observability'),
      mk('limiting', 'limiting observation parameters', observed.limiting_parameters.join(', ') || 'none', 'observed.limiting_parameters'),
    ] : [un('observability', 'observability status', 'observed.observability')]),
    ...(paths ? Object.entries(paths).map(([id, p]) => mk(`path_${id}`, `path ${id}: active ticks / cut ticks`, `${p.active_ticks} / ${p.cut_ticks}`, 'paths')) : [un('paths', 'operational paths', 'paths')]),
  ];
  const ref: Reading[] = [
    ...(observed ? [mk('operational_state', 'operational status (whole run)', observed.operational_state, 'observed.operational_state'), mk('true_cycles', 'cycles the run contains', observed.true_cycles, 'observed.true_cycles')] : []),
    mk('stimulus', 'stimulus s', e.s, 'frames.entity'), mk('baseline', 'adapted baseline', e.baseline, 'frames.entity'), mk('differentiation', 'differentiated stimulus d', e.d, 'frames.entity'),
    mk('threshold', 'firing threshold', e.theta, 'frames.entity'), mk('history_reentry', 'threshold lowered by history', e.reentry, 'frames.entity'),
    mk('energy', 'energy', e.energy, 'frames.entity'), mk('position', 'position (x, y)', `${e.x}, ${e.y}`, 'frames.entity'), mk('present', 'present', e.present, 'frames.entity'),
    mk('unmet', 'unmet preconditions', e.failed.join('; ') || 'none', 'frames.entity'), mk('power', 'power reserve', f.power, 'frames.power'),
  ];
  return { observed: obs, inferred: inf, reference: ref };
}

// ------------------------------------------------------------------------------------------------ what cannot be settled

export interface UnresolvedItem { id: string; label: string; reason: string }

/** The fourth class of the inspector: what the current observation and experiment cannot settle. A difference the observation does not resolve is listed here, not dropped: the observer cannot tell
 *  whether it happened. Nothing in this list is a finding about the target. */
export function unresolvedItems(rec: MeosRecord, observed: Observed | null): UnresolvedItem[] {
  const out: UnresolvedItem[] = [];
  if (!observed) {
    out.push({ id: 'no_observation', label: 'everything the observer would conclude', reason: 'no observation result exists for this run (full-resolution observation requests none): what a limited observer would have recorded is unresolved' });
  } else {
    const hidden = observed.true_cycles - observed.observed_cycles;
    if (hidden > 0) out.push({ id: 'unobserved_cycles', label: `${hidden} of the ${observed.true_cycles} cycles of the run`, reason: `the observation array recorded ${observed.observed_cycles}; from the observer's side it cannot be told whether the other ${hidden} happened` });
    if (observed.observed_state !== observed.operational_state) out.push({ id: 'status_disagreement', label: `observed ${observed.observed_state} against operational ${observed.operational_state}`, reason: `the observation alone does not settle which holds of the target (limiting: ${observed.limiting_parameters.join(', ') || 'none named'}); the operational status is the evaluator's reference, not an observation` });
    const lost = observed.timeline.filter((r) => r.observability !== 'SUFFICIENT').length;
    if (lost > 0) out.push({ id: 'observability_limit', label: `${lost} ticks at which the observation is limited`, reason: 'at these ticks the observed status may differ from the operation for reasons of the observation, which one record cannot separate from a change of the target' });
  }
  out.push({ id: 'intervention_possibilities', label: 'which interventions a regime makes possible', reason: 'the engine has no operation that tests it' });
  out.push({ id: 'attribution', label: 'whether a difference belongs to the target or to the apparatus', reason: 'one record does not settle it; compare two regimes on one run (the target digest must be identical) or run an intervention branch' });
  out.push({ id: 'addressability', label: 'whether a retained history can be retrieved under a later configuration', reason: 'not modelled: the Address Domain of MEOS addresses cells of the arena, not records' });
  if (rec.termination.collapsed) out.push({ id: 'after_collapse', label: `the run after tick ${rec.termination.tick}`, reason: 'the run stopped at collapse; whether the operation could have been re-ignited later is not in the record' });
  return out;
}

// ------------------------------------------------------------------------------------------------ the track of the operational shape

export interface TrackSegment { from: number; to: number; label: Label }
export type TrackMarkKind = 'intervention' | 'divergence' | 'formation' | 'cessation' | 'reignition';
export interface TrackMark { tick: number; kind: TrackMarkKind; label: string }
export interface ShapeTrack { length: number; operational: TrackSegment[]; observed: TrackSegment[] | null; marks: TrackMark[] }

const runs = (n: number, at: (t: number) => Label): TrackSegment[] => {
  const out: TrackSegment[] = [];
  for (let t = 0; t < n; t++) { const l = at(t), last = out[out.length - 1]; if (last && last.label === l) last.to = t; else out.push({ from: t, to: t, label: l }); }
  return out;
};

/** The operational status per tick (from the status log), the observed status per tick when there is an observation result, and the events that mark formation, interventions, cessation, re-ignition and
 *  (when a baseline exists) the first divergence. Rows that differ are the observation's, not the target's. */
export function shapeTrack(rec: MeosRecord, observed: Observed | null, divergence: number | null = null): ShapeTrack {
  const n = rec.frames.length;
  const op = (t: number): Label => { let l: Label = rec.status_log[0]?.label ?? 'DEGRADED'; for (const e of rec.status_log) { if (e.tick <= t) l = e.label; else break; } return l; };
  const marks: TrackMark[] = [];
  const first = rec.status_log.find((e) => e.label === 'ACTIVE');
  if (first) marks.push({ tick: first.tick, kind: 'formation', label: 'operation forms (first ACTIVE)' });
  let collapsed = false;
  for (const e of rec.status_log) {
    if (e.label === 'COLLAPSED' && !collapsed) { marks.push({ tick: e.tick, kind: 'cessation', label: 'collapse' }); collapsed = true; }
    else if (e.label === 'ACTIVE' && collapsed) { marks.push({ tick: e.tick, kind: 'reignition', label: 're-ignition (ACTIVE after COLLAPSED)' }); collapsed = false; }
  }
  for (const i of rec.interventions) marks.push({ tick: i.tick, kind: 'intervention', label: `${i.op}${i.target ? ` ${i.target}` : ''}` });
  if (divergence !== null) marks.push({ tick: divergence, kind: 'divergence', label: 'records first differ from the baseline' });
  marks.sort((a, b) => a.tick - b.tick);
  return { length: n, operational: runs(n, op), observed: observed ? runs(n, (t) => observed.timeline[t]?.observed ?? op(t)) : null, marks };
}

// ------------------------------------------------------------------------------------------------ history: retention, addressability, re-entry, consequence

export interface HistoryReading {
  /** a decaying history trace is held by each entity (the engine's own quantity); ``enabled`` is whether the re-entry channel is on at the tick */
  retention: { A1: number; A2: number; enabled: boolean | null };
  addressability: { status: 'NOT_MODELLED'; reason: string };
  /** complete cycles up to the tick that contain a history re-entry, and the threshold each entity's firing is lowered by at the tick */
  reentry: { cycles: number; ofCycles: number; A1: number; A2: number };
}

/** The four things that must not be taken for one another, as far as the record carries them. Retention and re-entry are read from the record; addressability is not modelled by MEOS; the effective
 *  consequence of re-entry cannot be read from one record and needs a counterfactual run (``historyConsequence``). */
export function historyReading(rec: MeosRecord, tick: number): HistoryReading {
  const t = Math.max(0, Math.min(tick, rec.frames.length - 1)), f = rec.frames[t], ad = adAt(rec.frames, t);
  const upTo = rec.cycles.filter((c) => c.tick <= t);
  return {
    retention: { A1: f.A1.h, A2: f.A2.h, enabled: ad ? ad.A1.history_reentry_enabled : null },
    addressability: { status: 'NOT_MODELLED', reason: 'the Address Domain of MEOS addresses cells of the arena, not records: there is no retrieval of a retained history under a later configuration to observe' },
    reentry: { cycles: upTo.filter((c) => c.history_reentry).length, ofCycles: upTo.length, A1: f.A1.reentry, A2: f.A2.reentry },
  };
}

export interface HistoryConsequence {
  verdict: 'DIFFERS' | 'NO_DIFFERENCE_IN_THIS_RUN';
  base: { label: Label; cycles: number; reentryCycles: number }; withoutHistory: { label: Label; cycles: number; reentryCycles: number };
  firstStatusDivergence: number | null; note: string;
}

/** The effective consequence of history re-entry, from two engine runs of one configuration: the baseline and the same run with the history disabled (``DISABLE_HISTORY``). It holds for this
 *  configuration and seed only; a record that replays is not thereby a re-entry, and a difference here is a difference of these two runs, not a general law. */
export function historyConsequence(base: MeosRecord, withoutHistory: MeosRecord): HistoryConsequence {
  const side = (r: MeosRecord) => ({ label: r.final_status.label, cycles: r.cycles.length, reentryCycles: r.final_status.history_reentry_cycles });
  const b = side(base), o = side(withoutHistory);
  let first: number | null = null;
  const n = Math.min(base.frames.length, withoutHistory.frames.length);
  for (let t = 0; t < n; t++) if (base.frames[t].status !== withoutHistory.frames[t].status) { first = t; break; }
  const differs = b.label !== o.label || b.cycles !== o.cycles || first !== null;
  return { verdict: differs ? 'DIFFERS' : 'NO_DIFFERENCE_IN_THIS_RUN', base: b, withoutHistory: o, firstStatusDivergence: first,
    note: differs ? 'with the history disabled the engine produced a different run: the re-entry had an effect on what followed in this configuration and seed' : 'disabling the history changed neither the final status, the cycles nor the status log of this run: no effect of re-entry is shown here (this does not show that there is none elsewhere)' };
}

// ------------------------------------------------------------------------------------------------ the five kinds of change under an observation regime

export type Verdict = 'CHANGED' | 'UNCHANGED' | 'UNRESOLVED';
export interface RegimeSide { obs: Observation; observed: Observed; resultDigest: string }
export interface RegimeRow { kind: 'target' | 'apparatus' | 'representation' | 'classification' | 'intervention_possibilities'; label: string; verdict: Verdict; detail: string }
export interface RegimeComparison { rows: RegimeRow[]; note: string }

const normObs = (o: Observation): Observation => ({ ...FULL_OBSERVATION, threshold: null, occluder: null, address_resolution: null, spatial_offset: [0, 0], ...o });
const same = (a: unknown, b: unknown): boolean => JSON.stringify(a) === JSON.stringify(b);

/** Compare two observation regimes applied to the same configuration. The five kinds of change are reported separately and none implies another: a changed record of observation is not
 *  a changed target, and a newly identified difference is not evidence of a new real entity. The effect on the interventions that become possible is not evaluated by the engine: UNRESOLVED. */
export function compareRegimes(a: RegimeSide, b: RegimeSide): RegimeComparison {
  const target = a.resultDigest === b.resultDigest ? 'UNCHANGED' : 'CHANGED';
  const apparatus = same(normObs(a.obs), normObs(b.obs)) ? 'UNCHANGED' : 'CHANGED';
  const representation = a.observed.observed_cycles === b.observed.observed_cycles && same(a.observed.observed_trajectory, b.observed.observed_trajectory) ? 'UNCHANGED' : 'CHANGED';
  const classification = a.observed.observed_state === b.observed.observed_state && a.observed.observability.status === b.observed.observability.status ? 'UNCHANGED' : 'CHANGED';
  const rows: RegimeRow[] = [
    { kind: 'target', label: 'a real change in the target', verdict: target, detail: `result digest ${a.resultDigest.slice(0, 8)} → ${b.resultDigest.slice(0, 8)}` },
    { kind: 'apparatus', label: 'a change in the observation apparatus', verdict: apparatus, detail: apparatus === 'CHANGED' ? 'the observation configuration differs' : 'the same observation configuration' },
    { kind: 'representation', label: 'a change in the recorded representation', verdict: representation, detail: `observed cycles ${a.observed.observed_cycles} → ${b.observed.observed_cycles} (the run contains ${b.observed.true_cycles})` },
    { kind: 'classification', label: 'a change in the inferential classification', verdict: classification, detail: `${a.observed.observed_state}/${a.observed.observability.status} → ${b.observed.observed_state}/${b.observed.observability.status}` },
    { kind: 'intervention_possibilities', label: 'a change in the effective intervention possibilities', verdict: 'UNRESOLVED', detail: 'the engine has no operation that tests which interventions a regime makes possible; the status is kept unresolved' },
  ];
  const note = target === 'UNCHANGED' && (representation === 'CHANGED' || classification === 'CHANGED')
    ? 'the record of observation differs while the target is identical: the difference belongs to the observation, not to a newly generated real entity.'
    : target === 'CHANGED' ? 'the two sides are different runs, not two regimes on one run: the differences cannot be attributed to the observation.' : 'no difference in what was recorded or classified.';
  return { rows, note };
}

// ------------------------------------------------------------------------------------------------ intervention provenance

export interface ProvenanceEntry { index: number; requested: Intervention; engine: 'ACCEPTED' | 'NOT_IN_LOG'; event: number | null; firstStatusChange: { tick: number; label: Label } | null }
export interface Provenance {
  engine: string; schema: string; seed: number; initialConfigDigest: string; resultDigest: string; traceDigest: string | null; fullDigest: string | null;
  termination: string; entries: ProvenanceEntry[];
}

/** What was requested of the engine and what the engine logged. A request is ACCEPTED when the engine's own intervention log carries it (matched by tick and operation, in order);
 *  one the log does not carry is reported as NOT_IN_LOG (for example scheduled after the run ended). The first status change after each accepted request is read from the status log. */
export function provenance(rec: MeosRecord): Provenance {
  const used = new Set<number>();
  const entries = rec.interventions.map((iv, index): ProvenanceEntry => {
    const j = rec.intervention_log.findIndex((l, k) => !used.has(k) && l.tick === iv.tick && l.op === iv.op);
    if (j >= 0) used.add(j);
    const logged = j >= 0 ? rec.intervention_log[j] : null;
    const next = logged ? rec.status_log.find((s) => s.tick > logged.tick) ?? null : null;
    return { index, requested: iv, engine: logged ? 'ACCEPTED' : 'NOT_IN_LOG', event: logged ? logged.event : null, firstStatusChange: next ? { tick: next.tick, label: next.label } : null };
  });
  return { engine: rec.engine, schema: rec.schema, seed: rec.seed, initialConfigDigest: rec.initial_config_digest, resultDigest: rec.result_digest, traceDigest: rec.trace_digest ?? null, fullDigest: rec.full_digest ?? null,
    termination: rec.termination.reason, entries };
}

// ------------------------------------------------------------------------------------------------ critical intervals

export type Span = [number, number];
export interface CriticalInterval { id: string; label: string; status: 'DERIVED' | 'NOT_OCCURRED' | 'UNSUPPORTED'; spans: Span[]; basis: string }

const spansOf = (n: number, pred: (t: number) => boolean): Span[] => {
  const out: Span[] = []; let from = -1;
  for (let t = 0; t < n; t++) { if (pred(t)) { if (from < 0) from = t; } else if (from >= 0) { out.push([from, t - 1]); from = -1; } }
  if (from >= 0) out.push([from, n - 1]);
  return out;
};

/** Intervals of scientific operation read from the record and the observation timeline. They are listed, not sequenced: they may overlap or occur in any order, and none implies another
 *  (a failed observation channel is not a cessation; a preserved classification is not a continuing capability). Intervals the engine does not model are UNSUPPORTED, with the records
 *  that exist near them stated. */
export function criticalIntervals(rec: MeosRecord, observed: Observed | null): CriticalInterval[] {
  const n = rec.frames.length;
  const labelAt = (t: number): Label => { let l: Label = rec.status_log[0]?.label ?? 'DEGRADED'; for (const s of rec.status_log) { if (s.tick <= t) l = s.label; else break; } return l; };
  const firstActive = rec.status_log.find((s) => s.label === 'ACTIVE');
  const collapsed = spansOf(n, (t) => labelAt(t) === 'COLLAPSED');
  const reignite: Span[] = [];
  let seenCollapse = false;
  for (const s of rec.status_log) { if (s.label === 'COLLAPSED') seenCollapse = true; else if (seenCollapse && s.label === 'ACTIVE') { reignite.push([s.tick, s.tick]); seenCollapse = false; } }
  const sufficient = observed ? spansOf(n, (t) => observed.timeline[t]?.observability === 'SUFFICIENT') : [];
  const lost = observed ? spansOf(n, (t) => !!observed.timeline[t] && observed.timeline[t].observability !== 'SUFFICIENT') : [];
  const count = (k: string) => rec.events.filter((e) => e.kind === k).length;
  const unsupported = (id: string, label: string, basis: string): CriticalInterval => ({ id, label, status: 'UNSUPPORTED', spans: [], basis });
  const list: CriticalInterval[] = [
    firstActive ? { id: 'formation', label: 'operational formation', status: 'DERIVED', spans: [[0, firstActive.tick]], basis: `from tick 0 to the first ACTIVE status (tick ${firstActive.tick}) in the status log` }
      : { id: 'formation', label: 'operational formation', status: 'NOT_OCCURRED', spans: [], basis: 'the run never reached ACTIVE' },
    observed ? { id: 'observation', label: 'observation', status: sufficient.length ? 'DERIVED' : 'NOT_OCCURRED', spans: sufficient, basis: 'ticks at which the observation timeline reports SUFFICIENT' }
      : unsupported('observation', 'observation', 'no observation result for this run'),
    observed ? { id: 'loss_of_access', label: 'loss of effective access', status: lost.length ? 'DERIVED' : 'NOT_OCCURRED', spans: lost, basis: 'ticks at which the observation timeline reports a limit of the observation; this is not a cessation of the operation' }
      : unsupported('loss_of_access', 'loss of effective access', 'no observation result for this run'),
    unsupported('warrant', 'evidential warrant', `not modelled; the record has ${count('score')} score and ${count('inference')} inference events, which exist only when phil.mode is set and are the model's operations, not an evidential warrant`),
    unsupported('attribution', 'scientific attribution', 'not modelled by the engine'),
    unsupported('material_continuation', 'material continuation', `not modelled; only the finite power reserve (${fmt(rec.frames[n - 1].power)} at the last tick) is recorded`),
    collapsed.length ? { id: 'cessation', label: 'cessation', status: 'DERIVED', spans: collapsed, basis: 'ticks at which the operational status (the run itself, not the observation) is COLLAPSED' }
      : { id: 'cessation', label: 'cessation', status: 'NOT_OCCURRED', spans: [], basis: 'the operational status never was COLLAPSED' },
    reignite.length ? { id: 're_ignition', label: 'possible re-ignition', status: 'DERIVED', spans: reignite, basis: 'ACTIVE after COLLAPSED in the status log' } : { id: 're_ignition', label: 'possible re-ignition', status: 'NOT_OCCURRED', spans: [], basis: 'no ACTIVE status follows a COLLAPSED one in this run' },
  ];
  return list;
}

// ------------------------------------------------------------------------------------------------ human mediation

export type DependencyState = 'PRESENT_IN_THIS_RUN' | 'NOT_REPRESENTED' | 'ASSUMED_AWAY';
export interface HumanDependency { id: string; label: string; state: DependencyState; detail: string }

/** Six kinds of human mediation, kept apart (there is no single human-dependence score). The engine represents few of them: for each, what the record shows and what it cannot establish.
 *  Removing the operator from the loop of a run does not remove the human infrastructure that built, powered and defined it. */
export function humanDependencies(rec: MeosRecord): HumanDependency[] {
  const power = rec.final_config.power, n = rec.interventions.length;
  return [
    { id: 'decisions', label: 'continuing human decisions', state: n ? 'PRESENT_IN_THIS_RUN' : 'NOT_REPRESENTED',
      detail: n ? `${n} intervention${n === 1 ? '' : 's'} requested by the researcher are in the record` : 'the run has no requested intervention, but it was configured and started by a human; the engine does not represent that decision' },
    { id: 'energy', label: 'human-maintained energy supply', state: power.infinite ? 'ASSUMED_AWAY' : 'NOT_REPRESENTED',
      detail: power.infinite ? 'the power reserve is declared unlimited: a modelling assumption that hides the supply, not evidence of independence from it' : `a finite reserve (${fmt(power.reserve)} of capacity ${fmt(power.capacity)}) is a model parameter; who maintains it is not represented` },
    { id: 'maintenance', label: 'human maintenance and fabrication', state: 'NOT_REPRESENTED', detail: 'the engine has no fabrication, repair labour or replacement of parts by humans' },
    { id: 'readability', label: 'mandatory human-readable interpretation', state: 'PRESENT_IN_THIS_RUN', detail: 'the status labels (ACTIVE, DEGRADED, COLLAPSED) and the criteria are human-defined readings of the run; the engine does not run without them' },
    { id: 'approval', label: 'human institutional approval', state: 'NOT_REPRESENTED', detail: 'no approval, permission or institutional step exists in the model' },
    { id: 'inherited', label: 'historically inherited human-defined variables and objectives', state: 'PRESENT_IN_THIS_RUN', detail: 'the resource, alteration fields, thresholds and the persistence criterion are variables chosen by the designers of the model' },
  ];
}

// ------------------------------------------------------------------------------------------------ Strong Xenoscience: four jointly necessary conditions

export type ConditionStatus = 'SUPPORTED_WITHIN_DECLARED_CONDITIONS' | 'FAILED_WITHIN_DECLARED_CONDITIONS' | 'UNTESTED' | 'INSUFFICIENT_EVIDENCE';
export interface Condition { id: 1 | 2 | 3 | 4; label: string; status: ConditionStatus; basis: string; needed: string }
export interface StrongStatus { conditions: Condition[]; joint: 'ESTABLISHED_WITHIN_DECLARED_CONDITIONS' | 'NOT_ESTABLISHED'; note: string }

/** The four conditions, each with an evidence-based status and never a score. A condition is SUPPORTED or FAILED only where the engine's record can bear on it; this simulator is a model of
 *  operational relations and does not establish that any physical system satisfies a condition, so the unmodelled ones stay UNTESTED or INSUFFICIENT_EVIDENCE. The joint classification needs all
 *  four to be supported. */
export function strongXenoscience(rec: MeosRecord): StrongStatus {
  const power = rec.final_config.power, deps = humanDependencies(rec);
  const conds: Condition[] = [
    { id: 1, label: 'Critical Resource Independence', status: power.infinite ? 'INSUFFICIENT_EVIDENCE' : 'UNTESTED',
      basis: power.infinite ? 'the supply is assumed unlimited in this run; independence from a provider cannot be read from an assumption' : 'the reserve is finite and renewed from a parameter; whether a human provides it is not represented',
      needed: 'a declared inquiry and regeneration cycle in which the provisioning of energy and maintenance is traced to a source that does not require continuing human provision' },
    { id: 2, label: 'Human-Readability Independence', status: deps.find((d) => d.id === 'readability')?.state === 'PRESENT_IN_THIS_RUN' ? 'UNTESTED' : 'INSUFFICIENT_EVIDENCE',
      basis: 'the run is classified through human-defined status labels; operation without them was not tested',
      needed: 'a run whose continued operation is shown not to depend on a human-readable interpretation' },
    { id: 3, label: 'Material and Organizational Reproduction', status: 'UNTESTED', basis: 'the engine has no reproduction of apparatus or of the conditions of later investigation across cycles',
      needed: 'the conditions enabling subsequent investigation reproduced autonomously across the specified cycles' },
    { id: 4, label: 'Autonomous Investigative Reorganization', status: 'UNTESTED', basis: 'the engine\'s controllers reconfigure operational components under stress; they do not reorganise observation boundaries, variable partitions, scales, analytical cuts and intervention architectures as inquiry',
      needed: 'autonomous reorganisation of those five, recorded and evaluated' },
  ];
  const all = conds.every((c) => c.status === 'SUPPORTED_WITHIN_DECLARED_CONDITIONS');
  return { conditions: conds, joint: all ? 'ESTABLISHED_WITHIN_DECLARED_CONDITIONS' : 'NOT_ESTABLISHED',
    note: 'The four conditions are jointly necessary and are not combined into a score. This simulator does not establish that a physical system satisfies them.' };
}

// ------------------------------------------------------------------------------------------------ Five-S

export interface FiveSRow { dimension: 'scale' | 'size' | 'speed' | 'structure' | 'sensitivity'; kind: 'CONTROL' | 'CONFIGURATION' | 'MEASURED'; current: string; note: string }

/** Five-S as a conditional analytical framework. Scale, size and speed are engine controls (``sss``); structure is the arrangement of components (set by reductions, not one number); sensitivity is
 *  measured, never set. ``sssClass`` is the engine's classification of the current (scale, size, speed) point when one has been computed. */
export function fiveS(rec: MeosRecord, sssClass: SssClassOut | null): FiveSRow[] {
  const s = rec.final_config.sss, comps = Object.entries(rec.final_config.channels).filter(([, v]) => !v).map(([k]) => k);
  return [
    { dimension: 'scale', kind: 'CONTROL', current: fmt(s.scale), note: 'engine control (SSS axis)' },
    { dimension: 'size', kind: 'CONTROL', current: fmt(s.size), note: 'engine control (SSS axis)' },
    { dimension: 'speed', kind: 'CONTROL', current: fmt(s.speed), note: 'engine control (SSS axis)' },
    { dimension: 'structure', kind: 'CONFIGURATION', current: comps.length ? `channels off: ${comps.join(', ')}` : 'all channels on', note: 'the arrangement of components; not a single adjustable number' },
    { dimension: 'sensitivity', kind: 'MEASURED', current: sssClass ? `${sssClass.region}${sssClass.observation_sensitive ? ' (observation-sensitive)' : ''}` : 'not measured for this point', note: 'an experimentally determined response (SSS classification), not an input' },
  ];
}
