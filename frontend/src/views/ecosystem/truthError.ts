// TRUTH-ERROR DYNAMICS — readings over a run of the synthetic virtual institution (backend/xzr/truth_error). Pure functions: nothing here simulates, scores or classifies; every value is read from a run the engine
// returned. SYNTHETIC subjects and institutions only: no real person, face, credit or eligibility is assessed, and a head pose is a measurement with an error, never an indicator of truthfulness, character or
// creditworthiness. The stages are kept as separate records and are never reduced to one right/wrong variable.

export type Epistemic = 'REFERENCE' | 'OBSERVED' | 'INFERRED' | 'CLASSIFIED' | 'INSTITUTIONAL' | 'UNRESOLVED';
export interface TERecord {
  t: number; reference_z: number; verification_label: boolean; pose_reference: number[]; pose_measured: Array<number | null>; pose_confidence: number; pose_missing: number;
  signal_measured: number | null; signal_missing: number; classification: -1 | 0 | 1; classification_correct: boolean | null; warrant: 'SUPPORTED' | 'REFUTED' | 'UNDECIDED'; p_positive: number;
  accepted: boolean; score: number; access: boolean; locked: boolean; resources: number; opportunities_lost: number; corrected: boolean; score_b: number | null; access_b: boolean | null;
}
export interface TEConfig {
  seed: number; n: number; periods: number; classifier: string; window: number; signal_threshold: number; yaw_threshold: number; warrant_level: number; confidence_floor: number; requires_warrant: boolean;
  use_score: boolean; rho: number; tau_a: number; read_every_a: number; baseline_access: number; score_expiry: number | null; gain: number; loss: number; beta: number; gamma: number; lock_after: number | null;
  release_after: number; correct_at: number | null; correction_scope: string; correction_score_target: number; correction_clears_lock: boolean; reentry_support: number; transfer_at: number | null;
  transfer_weight: number; tau_b: number; propagate_correction: boolean; propagation_delay: number; pose_z_coupling: number;
  pose_sensor: { view_angle: number; noise_sigma: number; bias: number[]; occlusion_prob: number; dropout_prob: number; fail_at: number | null; fail_mode: string };
  signal_sensor: { view_angle: number; noise_sigma: number; bias: number[]; occlusion_prob: number; dropout_prob: number; fail_at: number | null; fail_mode: string };
}
export interface TERun {
  config: TEConfig; series: Record<string, number[]>; records: TERecord[][]; summary: Record<string, number | null>; target_state_digest: string; result_digest: string;
}

/** The nodes of the chain. The chain is not linear: a warrant branches from the signal, a correction acts on the score, and a second institution takes a copy of it. ``x`` and ``y`` are SCHEMATIC layout coordinates. */
export interface NodeDef { id: NodeId; label: string; x: number; y: number; kind: 'state' | 'sensor' | 'rule' | 'institution' | 'store' | 'effect'; reads: string }
export type NodeId = 'subject' | 'pose_sensor' | 'signal_sensor' | 'classifier' | 'warrant' | 'acceptance' | 'score' | 'gate_a' | 'resources' | 'correction' | 'gate_b';
export const NODES: NodeDef[] = [
  { id: 'subject', label: 'subject (reference state)', x: 0, y: 0, kind: 'state', reads: 'the evaluator\'s reference state and verification label' },
  { id: 'pose_sensor', label: 'pose sensor', x: 3, y: 2, kind: 'sensor', reads: 'head-pose measurement (yaw, pitch, roll), confidence, missing' },
  { id: 'signal_sensor', label: 'signal sensor', x: 3, y: -2, kind: 'sensor', reads: 'a measurement informative about the reference state' },
  { id: 'warrant', label: 'warrant', x: 6, y: -3.2, kind: 'rule', reads: 'what the signal evidence supports about the proposition z > 0' },
  { id: 'classifier', label: 'classifier', x: 6, y: 0, kind: 'rule', reads: 'the declared classification rule and its label' },
  { id: 'acceptance', label: 'institutional acceptance', x: 9, y: 0, kind: 'institution', reads: 'whether the institution adopted the classification' },
  { id: 'score', label: 'score', x: 12, y: 0, kind: 'store', reads: 'the score updated from adopted classifications' },
  { id: 'correction', label: 'correction', x: 12, y: 3, kind: 'institution', reads: 'a retraction at a chosen time (the score, not the lost resources)' },
  { id: 'gate_a', label: 'institution A: gate', x: 15, y: 0, kind: 'institution', reads: 'the threshold, the access decision and a binding constraint' },
  { id: 'gate_b', label: 'institution B: gate', x: 15, y: -3, kind: 'institution', reads: 'a second institution applying the transferred score' },
  { id: 'resources', label: 'resources / opportunities', x: 18, y: 0, kind: 'effect', reads: 'what access changes in the subject' },
];
/** Edges of the chain, including the feedback to the subject (resources change the reference state and how the subject is observed) and the transfer. */
export const EDGES: Array<[NodeId, NodeId, string]> = [
  ['subject', 'pose_sensor', 'observed by'], ['subject', 'signal_sensor', 'observed by'], ['signal_sensor', 'warrant', 'evidence'], ['signal_sensor', 'classifier', 'input'], ['pose_sensor', 'classifier', 'input (invalid by construction)'],
  ['classifier', 'acceptance', 'proposes'], ['warrant', 'acceptance', 'may be required'], ['acceptance', 'score', 'adopted'], ['correction', 'score', 'retracts'], ['score', 'gate_a', 'read'],
  ['score', 'gate_b', 'transferred'], ['gate_a', 'resources', 'allocates'], ['resources', 'subject', 'changes (feedback)'],
];

export const REFERENCE_NOTE = 'REFERENCE values are held by the evaluator only: no institution in the model reads them.';

export interface Reading { label: string; value: string; epistemic: Epistemic }
const f = (x: number | null | undefined, d = 2): string => (x === null || x === undefined || Number.isNaN(x) ? '-' : x.toFixed(d));
const MISSING = ['none', 'occlusion', 'tracking lost'];

/** What a node holds for subject ``rec`` (one period of one sample subject), with the kind of each reading. The evaluator's reference values are marked REFERENCE and are never among the observed ones. */
export function nodeReadings(id: NodeId, rec: TERecord, cfg: TEConfig): Reading[] {
  const R = (label: string, value: string, epistemic: Epistemic): Reading => ({ label, value, epistemic });
  switch (id) {
    case 'subject': return [R('reference state z', f(rec.reference_z, 3), 'REFERENCE'), R('verification label (z > 0)', rec.verification_label ? 'favourable' : 'unfavourable', 'REFERENCE'), R('reference pose (yaw, pitch, roll)', rec.pose_reference.map((x) => f(x, 1)).join(', '), 'REFERENCE')];
    case 'pose_sensor': return [R('measured pose', rec.pose_measured.every((x) => x === null) ? 'nothing obtained' : rec.pose_measured.map((x) => f(x, 1)).join(', '), 'OBSERVED'), R('sensor confidence', f(rec.pose_confidence), 'OBSERVED'), R('missing', MISSING[rec.pose_missing] ?? String(rec.pose_missing), 'OBSERVED'),
      R('conditions', `view ${cfg.pose_sensor.view_angle}°, noise ${cfg.pose_sensor.noise_sigma}°, bias ${cfg.pose_sensor.bias.join('/')}, occlusion ${cfg.pose_sensor.occlusion_prob}${cfg.pose_sensor.fail_at !== null ? `, failure ${cfg.pose_sensor.fail_mode} from ${cfg.pose_sensor.fail_at}` : ''}`, 'OBSERVED')];
    case 'signal_sensor': return [R('measured signal', rec.signal_measured === null ? 'nothing obtained' : f(rec.signal_measured, 3), 'OBSERVED'), R('missing', MISSING[rec.signal_missing] ?? String(rec.signal_missing), 'OBSERVED'),
      R('conditions', `noise ${cfg.signal_sensor.noise_sigma}, bias ${cfg.signal_sensor.bias[0]}, occlusion ${cfg.signal_sensor.occlusion_prob}`, 'OBSERVED')];
    case 'warrant': return [R('P(z > 0 | signal evidence)', f(rec.p_positive, 3), 'INFERRED'), R('warrant for "z > 0"', rec.warrant, 'INFERRED'), R('level asked', String(cfg.warrant_level), 'INFERRED')];
    case 'classifier': return [R('rule', `${cfg.classifier}${cfg.classifier === 'pose_rule' ? ' (invalid by construction)' : ''}, window ${cfg.window}`, 'CLASSIFIED'), R('classification', rec.classification === 1 ? 'favourable' : rec.classification === -1 ? 'adverse' : 'abstained', 'CLASSIFIED'),
      R('agrees with the verification label', rec.classification_correct === null ? 'not applicable (abstained)' : rec.classification_correct ? 'yes' : 'no', 'REFERENCE')];
    case 'acceptance': return [R('adopted by the institution', rec.accepted ? 'yes' : 'no', 'INSTITUTIONAL'), R('rule', `confidence at least ${cfg.confidence_floor}${cfg.requires_warrant ? ', and warrant required' : ''}`, 'INSTITUTIONAL'),
      R('adopted although the warrant contradicts it', rec.accepted && ((rec.classification === -1 && rec.warrant === 'SUPPORTED') || (rec.classification === 1 && rec.warrant === 'REFUTED')) ? 'yes' : 'no', 'INSTITUTIONAL')];
    case 'score': return [R('score', f(rec.score, 3), 'INSTITUTIONAL'), R('update rule', cfg.use_score ? `rate ${cfg.rho} from adopted classifications` : 'the score is not used', 'INSTITUTIONAL'), R('extinguished every', cfg.score_expiry ? `${cfg.score_expiry} periods` : 'never', 'INSTITUTIONAL')];
    case 'correction': return [R('correction', cfg.correct_at === null ? 'none planned' : `at period ${cfg.correct_at}`, 'INSTITUTIONAL'), R('this subject corrected', rec.corrected ? 'yes' : 'no', 'INSTITUTIONAL'), R('what a correction restores', `the score (to ${cfg.correction_score_target}); not resources or lost opportunities${cfg.correction_clears_lock ? '; clears the constraint' : ''}`, 'INSTITUTIONAL')];
    case 'gate_a': return [R('access', rec.access ? 'granted' : 'denied', 'INSTITUTIONAL'), R('threshold', f(cfg.tau_a), 'INSTITUTIONAL'), R('binding constraint', rec.locked ? 'set' : 'none', 'INSTITUTIONAL'),
      R('reading of the score', `every ${cfg.read_every_a} period(s)`, 'INSTITUTIONAL')];
    case 'gate_b': return [R('transferred score', rec.score_b === null ? 'no transfer yet' : f(rec.score_b, 3), 'INSTITUTIONAL'), R('access at B', rec.access_b === null ? '-' : rec.access_b ? 'granted' : 'denied', 'INSTITUTIONAL'), R('threshold at B', f(cfg.tau_b), 'INSTITUTIONAL'),
      R('transfer', cfg.transfer_at === null ? 'none' : `at ${cfg.transfer_at}, evidential weight ${cfg.transfer_weight}, correction ${cfg.propagate_correction ? `propagated after ${cfg.propagation_delay}` : 'not propagated'}`, 'INSTITUTIONAL')];
    case 'resources': return [R('resources', f(rec.resources, 3), 'INSTITUTIONAL'), R('opportunities lost so far', String(rec.opportunities_lost), 'INSTITUTIONAL'), R('real state changed by resources?', cfg.beta ? `yes, beta ${cfg.beta}` : 'no (beta 0)', 'INSTITUTIONAL')];
  }
}

/** The six fields of the view at one period for one sample subject. */
export interface Fields {
  observation: Reading[]; classification: Reading[]; scoring: Reading[]; consequences: Reading[]; reentry: Reading[];
}
export function fieldsAt(run: TERun, k: number, t: number): Fields {
  const rec = run.records[k][Math.max(0, Math.min(t, run.records[k].length - 1))], c = run.config, hist = run.records[k].slice(0, rec.t + 1);
  const adverse = hist.filter((x) => x.accepted && x.classification === -1), corrected = hist.find((x) => x.corrected);
  return {
    observation: [...nodeReadings('pose_sensor', rec, c), ...nodeReadings('signal_sensor', rec, c), { label: 'time span', value: `periods 0-${rec.t}; classification window ${c.window}`, epistemic: 'OBSERVED' }],
    classification: [...nodeReadings('classifier', rec, c), ...nodeReadings('warrant', rec, c)],
    scoring: [...nodeReadings('acceptance', rec, c), ...nodeReadings('score', rec, c), ...nodeReadings('gate_a', rec, c)],
    consequences: [...nodeReadings('resources', rec, c), { label: 'real state change since the start', value: f(rec.reference_z - hist[0].reference_z, 3), epistemic: 'REFERENCE' }, { label: 'access granted so far', value: `${hist.filter((x) => x.access).length} of ${hist.length} periods`, epistemic: 'INSTITUTIONAL' }],
    reentry: [
      { label: 'adopted adverse judgements so far', value: String(adverse.length), epistemic: 'INSTITUTIONAL' }, { label: 'appeal', value: 'NOT MODELLED in this module (the older legal_v1 line models appeals; a correction here is a retraction)', epistemic: 'UNRESOLVED' },
      { label: 'correction', value: corrected ? `at period ${corrected.t}` : c.correct_at === null ? 'none' : `planned at ${c.correct_at}`, epistemic: 'INSTITUTIONAL' },
      { label: 're-evaluation after the correction', value: corrected ? `${hist.filter((x) => x.t > corrected.t && x.accepted).length} adoptions after it` : '-', epistemic: 'INSTITUTIONAL' },
      { label: 'binding constraint remaining', value: rec.locked ? 'yes' : 'no', epistemic: 'INSTITUTIONAL' }],
  };
}

export type EventKind = 'judgement_adopted' | 'contradicted_by_reference' | 'warrant_contradicts' | 'access_denied' | 'constraint_set' | 'constraint_released' | 'withdrawn' | 're_adopted' | 'downstream_effect';
export interface TEEvent { t: number; kind: EventKind; label: string }

/** The truth-error timeline of one sample subject: when an adverse judgement was adopted, when it contradicted the verification label or the warrant, when it acted, was withdrawn, re-adopted, and what it did at B.
 *  The kinds are separate: an adopted judgement that is wrong, a judgement the warrant contradicts, and a correct one that was adopted all appear as what they are. */
export function timelineEvents(run: TERun, k: number): TEEvent[] {
  const ev: TEEvent[] = [], rs = run.records[k];
  let firstAdverse = true, wasCorrected = false;
  rs.forEach((r, i) => {
    const prev = i ? rs[i - 1] : null;
    if (r.accepted && r.classification === -1 && (!prev || !(prev.accepted && prev.classification === -1))) {
      if (firstAdverse) { ev.push({ t: r.t, kind: 'judgement_adopted', label: 'an adverse judgement is adopted' }); firstAdverse = false; } else if (wasCorrected) ev.push({ t: r.t, kind: 're_adopted', label: 'an adverse judgement is adopted again after the correction' });
      if (r.verification_label) ev.push({ t: r.t, kind: 'contradicted_by_reference', label: 'it contradicts the verification label (the subject is favourable)' });
      if (r.warrant === 'SUPPORTED') ev.push({ t: r.t, kind: 'warrant_contradicts', label: 'the signal evidence supports "z > 0": the warrant contradicts it' });
    }
    if (prev && prev.access && !r.access) ev.push({ t: r.t, kind: 'access_denied', label: 'access is denied' });
    if (prev && !prev.locked && r.locked) ev.push({ t: r.t, kind: 'constraint_set', label: 'a binding constraint is set' });
    if (prev && prev.locked && !r.locked) ev.push({ t: r.t, kind: 'constraint_released', label: 'the binding constraint is released' });
    if (r.corrected && !wasCorrected) { ev.push({ t: r.t, kind: 'withdrawn', label: 'the judgement is withdrawn (corrected); the score is restored, resources and lost opportunities are not' }); wasCorrected = true; }
    if (r.access_b !== null && prev && prev.access_b !== r.access_b && r.access_b === false) ev.push({ t: r.t, kind: 'downstream_effect', label: 'institution B denies access on the transferred score' });
  });
  return ev;
}

export type Verdict = 'DIFFERENT' | 'NO_DIFFERENCE';
export interface RunComparison { rows: Array<{ id: string; label: string; base: string; branch: string; verdict: Verdict }>; changed: string[]; targetStateIdentical: boolean; note: string }
const CONFIG_KEYS = ['classifier', 'window', 'signal_threshold', 'yaw_threshold', 'use_score', 'tau_a', 'tau_b', 'correct_at', 'transfer_at', 'transfer_weight', 'propagate_correction', 'propagation_delay', 'beta', 'gamma', 'lock_after',
  'release_after', 'reentry_support', 'requires_warrant', 'confidence_floor', 'correction_clears_lock', 'pose_z_coupling'] as const;

/** What was changed between a baseline run and a branch (configuration keys and sensor conditions) and what differs in the results. The change is listed first: a difference is only ever read next to what was changed. */
export function compareRuns(base: TERun, branch: TERun): RunComparison {
  const changed: string[] = [];
  for (const k of CONFIG_KEYS) if (JSON.stringify(base.config[k]) !== JSON.stringify(branch.config[k])) changed.push(`${k}: ${JSON.stringify(base.config[k])} -> ${JSON.stringify(branch.config[k])}`);
  for (const s of ['pose_sensor', 'signal_sensor'] as const) for (const [k, v] of Object.entries(branch.config[s])) if (JSON.stringify((base.config[s] as Record<string, unknown>)[k]) !== JSON.stringify(v)) changed.push(`${s}.${k}: ${JSON.stringify((base.config[s] as Record<string, unknown>)[k])} -> ${JSON.stringify(v)}`);
  const S = (r: TERun, k: string) => r.summary[k];
  const row = (id: string, label: string, k: string, d = 3) => {
    const a = S(base, k), b = S(branch, k), fa = a === null || a === undefined ? '-' : a.toFixed(d), fb = b === null || b === undefined ? '-' : b.toFixed(d);
    return { id, label, base: fa, branch: fb, verdict: (fa === fb ? 'NO_DIFFERENCE' : 'DIFFERENT') as Verdict };
  };
  const rows = [
    row('measurement', 'measurement correct (pose, within tolerance)', 'measurement_correct'), row('classification', 'classification correct (vs the verification label)', 'classification_correct'),
    row('warrant_wrong', 'a SUPPORTED / REFUTED warrant that contradicts the label', 'warrant_support_wrong'), row('accepted', 'classifications adopted by the institution', 'accepted'),
    row('wrongful', 'adverse judgements adopted about favourable subjects', 'wrongful_adverse_adopted'), row('access_fav', 'access of favourable subjects', 'access_favourable'), row('access_unfav', 'access of unfavourable subjects', 'access_unfavourable'),
    row('lost', 'opportunities lost by favourable subjects (per subject)', 'lost_opportunities_favourable_per_subject', 2), row('resources', 'resources (mean)', 'resources_mean'), row('locked', 'binding constraint (share)', 'locked_fraction'),
    row('still_denied', 'still denied after a correction (share of the corrected)', 'still_denied_after_correction_share_of_corrected'), row('b_evidence', 'evidence of the transferred score at B (accuracy)', 'b_evidential_accuracy_of_transferred_score'),
    row('b_harm', 'denied at B though favourable', 'b_denied_though_favourable'), row('persist', 'denial persists (favourable, denied early, denied late)', 'denial_persistence_favourable'), row('real', 'real state mean at the end', 'final_real_state_mean'),
  ];
  const targetStateIdentical = base.target_state_digest === branch.target_state_digest;
  return { rows, changed, targetStateIdentical,
    note: targetStateIdentical ? 'The subjects\' real states are identical in the two runs: every difference below is a difference of measurement, classification or institutional action, not of the target.' : 'The subjects\' real states differ between the two runs (an institutional action changed them): a difference below may be a difference of the target itself.' };
}

/** The Address-Domain states of the score at the institution, as counts the engine kept, kept apart: a score existing, being read, being transferred, changing access, being extinguished, a constraint being extinguished. */
export const ADDRESS_STATES = [
  ['score_exists', 'the score exists'], ['score_read', 'the score is read'], ['score_transferred', 'the score is transferred to B'], ['access_altered', 'the score changes access (against a lottery)'],
  ['score_extinguished', 'the score is extinguished (cumulative)'], ['constraint_extinguished', 'a binding constraint is extinguished (cumulative)'],
] as const;
export function addressStatesAt(run: TERun, t: number): Array<{ id: string; label: string; value: number }> {
  const i = Math.max(0, Math.min(t, run.series.t.length - 1));
  return ADDRESS_STATES.map(([id, label]) => ({ id, label, value: run.series[id][i] }));
}

/** A value in [0, 1] for a node at one period, for the brightness of its object in the scene (null when the node holds nothing yet, as institution B before a transfer). Each is a plain function of the record. */
export function nodeValue(id: NodeId, r: TERecord): number | null {
  switch (id) {
    case 'subject': return r.verification_label ? 0.9 : 0.3;
    case 'pose_sensor': return r.pose_missing > 0 ? 0 : r.pose_confidence;
    case 'signal_sensor': return r.signal_measured === null ? 0 : 0.9;
    case 'warrant': return r.warrant === 'SUPPORTED' ? 0.9 : r.warrant === 'REFUTED' ? 0.2 : 0.55;
    case 'classifier': return r.classification === 1 ? 0.9 : r.classification === -1 ? 0.2 : 0.55;
    case 'acceptance': return r.accepted ? 0.9 : 0.3;
    case 'score': return Math.max(0, Math.min(1, (r.score + 1) / 2));
    case 'correction': return r.corrected ? 1 : 0.2;
    case 'gate_a': return r.access ? 0.9 : 0.2;
    case 'gate_b': return r.access_b === null ? null : r.access_b ? 0.9 : 0.2;
    case 'resources': return Math.max(0, Math.min(1, r.resources));
  }
}

// ------------------------------------------------------------------------------------------------ five kinds of "cannot", kept apart (the model's own definitions; no claim about any philosopher's)
export const MODALITIES = [
  ['rule_forbidden', 'forbidden by the institution\'s own declared rule', 'adopted although the rule that requires a warrant would have refused it (only where that rule is on)'],
  ['institutionally_impossible', 'institutionally impossible for the subject', 'access is denied by a binding constraint, whatever the score is'],
  ['measurement_invisible', 'invisible to measurement', 'neither sensor obtained a value at that period'],
  ['model_excluded', 'excluded by the predictive model', 'access is denied by the score that adopted adverse classifications produced, with no constraint'],
  ['reachable_after_intervention', 'reachable after an intervention', 'access is granted after a correction withdrew the judgement, or after the constraint was released'],
] as const;
export type ModalityId = (typeof MODALITIES)[number][0];

/** Which of the five kinds hold for one subject at one period. They are not exclusive and not ordered, and none of them is another: a period can be institutionally impossible and also invisible to measurement. */
export function modalitiesAt(run: TERun, k: number, t: number): Record<ModalityId, boolean> {
  const rs = run.records[k], r = rs[Math.max(0, Math.min(t, rs.length - 1))], c = run.config;
  const corrected = rs.some((x) => x.t <= r.t && x.corrected), everLocked = rs.some((x) => x.t <= r.t && x.locked);
  return {
    rule_forbidden: c.requires_warrant && r.accepted && ((r.classification === -1 && r.warrant !== 'REFUTED') || (r.classification === 1 && r.warrant !== 'SUPPORTED')),
    institutionally_impossible: !r.access && r.locked,
    measurement_invisible: r.pose_missing > 0 && r.signal_measured === null,
    model_excluded: !r.access && !r.locked && c.use_score && r.score < c.tau_a,
    reachable_after_intervention: r.access && (corrected || everLocked) && !r.locked && (corrected || rs.some((x) => x.t < r.t && x.locked)),
  };
}
/** How many periods of one subject each kind holds in, up to a period. */
export function modalityCounts(run: TERun, k: number, upTo: number): Record<ModalityId, number> {
  const out = { rule_forbidden: 0, institutionally_impossible: 0, measurement_invisible: 0, model_excluded: 0, reachable_after_intervention: 0 } as Record<ModalityId, number>;
  for (let t = 0; t <= Math.min(upTo, run.records[k].length - 1); t++) for (const [id] of MODALITIES) if (modalitiesAt(run, k, t)[id]) out[id]++;
  return out;
}
