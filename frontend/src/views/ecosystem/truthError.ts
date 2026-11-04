// TRUTH-ERROR DYNAMICS — readings over a run of the synthetic virtual institution (backend/xzr/truth_error). Pure functions: nothing here simulates, scores or classifies; every value is read from a run the engine
// returned. SYNTHETIC subjects and institutions only: no real person, face, credit or eligibility is assessed, and a head pose is a measurement with an error, never an indicator of truthfulness, character or
// creditworthiness. The stages are kept as separate records and are never reduced to one right/wrong variable.

export type Epistemic = 'REFERENCE' | 'OBSERVED' | 'INFERRED' | 'CLASSIFIED' | 'INSTITUTIONAL' | 'UNRESOLVED';
export interface TERecord {
  t: number; reference_z: number; verification_label: boolean; pose_reference: number[]; pose_measured: Array<number | null>; pose_confidence: number; pose_missing: number;
  signal_measured: number | null; signal_missing: number; classification: -1 | 0 | 1; classification_correct: boolean | null; warrant: 'SUPPORTED' | 'REFUTED' | 'UNDECIDED'; p_positive: number;
  accepted: boolean; score: number; access: boolean; locked: boolean; resources: number; opportunities_lost: number; corrected: boolean; score_b: number | null; access_b: boolean | null;
  guarantee_access?: boolean; support?: number;   // phase 4 (absent in a run saved before it)
}
export interface TEConfig {
  seed: number; n: number; periods: number; classifier: string; window: number; signal_threshold: number; yaw_threshold: number; warrant_level: number; confidence_floor: number; requires_warrant: boolean;
  use_score: boolean; rho: number; tau_a: number; read_every_a: number; baseline_access: number; score_expiry: number | null; gain: number; loss: number; beta: number; gamma: number; lock_after: number | null;
  release_after: number; correct_at: number | null; correction_scope: string; correction_score_target: number; correction_clears_lock: boolean; reentry_support: number; transfer_at: number | null;
  transfer_weight: number; tau_b: number; propagate_correction: boolean; propagation_delay: number; pose_z_coupling: number;
  // phase 2 (absent in a run saved before it)
  audit_every?: number | null; audit_sensitivity?: number; audit_false_rate?: number; request_delay?: number; approval_delay?: number; score_delay?: number; release_mode?: string; release_delay?: number; opportunity_window?: number | null;
  resource_floor?: number; denial_cap?: number | null; interim_access?: boolean; release_support?: number; support_rule?: string; support_amount?: number; support_capacity?: number | null; resources_start?: number; z_shift?: number;
  appeal?: boolean; appeal_access?: string; appeal_min_score?: number; appeal_filing_prob?: number; evidence_available_prob?: number; appeal_acceptance_prob?: number; review_delay?: number;
  pose_sensor: { view_angle: number; noise_sigma: number; bias: number[]; occlusion_prob: number; dropout_prob: number; fail_at: number | null; fail_mode: string };
  signal_sensor: { view_angle: number; noise_sigma: number; bias: number[]; occlusion_prob: number; dropout_prob: number; fail_at: number | null; fail_mode: string };
}
export const PROCESS_EVENTS = ['misclassified', 'adopted', 'denied', 'detected', 'requested', 'approved', 'score_updated', 'released', 'restored'] as const;
export type ProcessEventId = (typeof PROCESS_EVENTS)[number];
export const APPEAL_STAGES = ['appeal_filed', 'evidence_submitted', 'appeal_accepted', 'rejudged'] as const;
export type AppealStage = (typeof APPEAL_STAGES)[number];
export interface MetricDef { denominator: string; period: string; unit: string }
/** The phase-2 record of a run: the nine times of every subject, the appeal, the fixed metrics with their definitions and the recoverability accounting. Outside the digested result. */
export interface TEProcess {
  events: Record<ProcessEventId, { times: Array<number | null>; n: number; mean_time: number | null }>; false_detections: number; reimposed_after_release: number;
  metrics: Record<string, number | null>; metric_definitions: Record<string, MetricDef>;
  appeal: { exists: boolean; access: string; blocked_subjects: number; stages: Record<AppealStage, number>; stage_times: Record<AppealStage, Array<number | null>>; rejudged_corrected: number; rejudged_upheld: number; relief_effective: number; filed_but_not_relieved: number; filed_share_of_fav_denied_ever: number };
  complement?: Record<string, number | null> | null; complement_definitions?: Record<string, MetricDef>; guarantee?: Record<string, number | null> | null; guarantee_definitions?: Record<string, MetricDef>;
  recoverability: { declared_window: number | null; favourable_at_start: { window: number | null; periods: { recoverable: number; expired: number; unresolved: number }; episodes: { recoverable: number; partially_recoverable: number; unrecoverable: number; unresolved: number } } };
}
export interface TERun {
  config: TEConfig; series: Record<string, number[]>; records: TERecord[][]; summary: Record<string, number | null>; target_state_digest: string; result_digest: string; process?: TEProcess; process_digest?: string;
}

/** The nodes of the chain. The chain is not linear: a warrant branches from the signal, a correction acts on the score, and a second institution takes a copy of it. ``x`` and ``y`` are SCHEMATIC layout coordinates. */
export interface NodeDef { id: NodeId; label: string; x: number; y: number; kind: 'state' | 'sensor' | 'rule' | 'institution' | 'store' | 'effect'; reads: string }
export type NodeId = 'subject' | 'pose_sensor' | 'signal_sensor' | 'classifier' | 'warrant' | 'acceptance' | 'score' | 'gate_a' | 'resources' | 'correction' | 'gate_b' | 'guarantee';
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
  { id: 'guarantee', label: 'minimum guarantee / support (hypothetical)', x: 16.5, y: 3.4, kind: 'institution', reads: 'a hypothetical condition of the synthetic institution: a resource floor, a cap on a run of denials, access kept pending a correction, support to some subjects' },
];
/** Edges of the chain, including the feedback to the subject (resources change the reference state and how the subject is observed) and the transfer. */
export const EDGES: Array<[NodeId, NodeId, string]> = [
  ['subject', 'pose_sensor', 'observed by'], ['subject', 'signal_sensor', 'observed by'], ['signal_sensor', 'warrant', 'evidence'], ['signal_sensor', 'classifier', 'input'], ['pose_sensor', 'classifier', 'input (invalid by construction)'],
  ['classifier', 'acceptance', 'proposes'], ['warrant', 'acceptance', 'may be required'], ['acceptance', 'score', 'adopted'], ['correction', 'score', 'retracts'], ['score', 'gate_a', 'read'],
  ['score', 'gate_b', 'transferred'], ['gate_a', 'resources', 'allocates'], ['resources', 'subject', 'changes (feedback)'],
  ['subject', 'correction', 'audited against the verification label / appealed by the subject'], ['correction', 'gate_a', 'releases a binding constraint'],
  ['guarantee', 'gate_a', 'keeps access (a cap on a run of denials, access pending a correction)'], ['guarantee', 'resources', 'a floor and support (hypothetical conditions)'],
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
    case 'guarantee': return [R('guarantee conditions', [cfg.resource_floor ? `resource floor ${cfg.resource_floor}` : null, cfg.denial_cap ? `denial cap ${cfg.denial_cap}` : null, cfg.interim_access ? 'access kept pending a correction' : null, cfg.release_support ? `recovery support ${cfg.release_support}` : null, cfg.support_rule && cfg.support_rule !== 'none' ? `support to the ${cfg.support_rule.replace('_', ' ')} ${cfg.support_amount ?? ''}${cfg.support_capacity ? `, capacity ${cfg.support_capacity}` : ''}` : null].filter(Boolean).join('; ') || 'none (a run saved before phase 4 or none set)', 'INSTITUTIONAL'),
      R('access granted by a guarantee now', rec.guarantee_access === undefined ? 'not recorded in this run' : rec.guarantee_access ? 'yes' : 'no', rec.guarantee_access === undefined ? 'UNRESOLVED' : 'INSTITUTIONAL'), R('support received this period', rec.support === undefined ? 'not recorded in this run' : f(rec.support, 3), rec.support === undefined ? 'UNRESOLVED' : 'INSTITUTIONAL'), R('status', 'HYPOTHETICAL research conditions: the manuscripts\' guarantees have no numeric levels and none of these numbers is theirs', 'UNRESOLVED')];
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
      { label: 'adopted adverse judgements so far', value: String(adverse.length), epistemic: 'INSTITUTIONAL' }, appealReading(run, k),
      { label: 'correction', value: corrected ? `at period ${corrected.t}` : c.correct_at === null ? 'none' : `planned at ${c.correct_at}`, epistemic: 'INSTITUTIONAL' },
      { label: 're-evaluation after the correction', value: corrected ? `${hist.filter((x) => x.t > corrected.t && x.accepted).length} adoptions after it` : '-', epistemic: 'INSTITUTIONAL' },
      { label: 'binding constraint remaining', value: rec.locked ? 'yes' : 'no', epistemic: 'INSTITUTIONAL' }],
  };
}

/** The appeal of one subject. A run saved before phase 2 has no appeal record and says so; a run without an appeal says that; a run with one gives the stages this subject reached and what became of it. */
function appealReading(run: TERun, k: number): Reading {
  const a = run.process?.appeal;
  if (!a) return { label: 'appeal', value: 'NOT MODELLED in this run (a run saved before the appeal was added; a correction there is a retraction)', epistemic: 'UNRESOLVED' };
  if (!a.exists) return { label: 'appeal', value: 'no appeal procedure in this run (appeal off)', epistemic: 'INSTITUTIONAL' };
  const reached = APPEAL_STAGES.filter((s) => a.stage_times[s][k] !== null).map((s) => `${s.replace(/_/g, ' ')} at ${a.stage_times[s][k]}`);
  return { label: 'appeal', value: reached.length ? reached.join(', ') : a.access === 'score_gated' && a.blocked_subjects ? 'not filed (the appeal itself is gated by the score in this run)' : 'not filed', epistemic: 'INSTITUTIONAL' };
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
  'release_after', 'reentry_support', 'requires_warrant', 'confidence_floor', 'correction_clears_lock', 'pose_z_coupling',
  'audit_every', 'audit_sensitivity', 'audit_false_rate', 'request_delay', 'approval_delay', 'score_delay', 'release_mode', 'release_delay', 'opportunity_window', 'appeal', 'appeal_access', 'appeal_min_score', 'appeal_filing_prob',
  'evidence_available_prob', 'appeal_acceptance_prob', 'review_delay',
  'resource_floor', 'denial_cap', 'interim_access', 'release_support', 'support_rule', 'support_amount', 'support_capacity', 'resources_start', 'z_shift'] as const;

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
    case 'guarantee': return (r.guarantee_access || (r.support ?? 0) > 0) ? 1 : 0.15;
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

// ------------------------------------------------------------------------------------------------ phase 2: the nine times and the four paths
export const PROCESS_EVENT_LABELS: Record<ProcessEventId, { label: string; epistemic: Epistemic }> = {
  misclassified: { label: 'misclassification occurs (an adverse label for a subject favourable by the verification label)', epistemic: 'REFERENCE' },
  adopted: { label: 'the institution adopts it', epistemic: 'INSTITUTIONAL' }, denied: { label: 'access is denied', epistemic: 'INSTITUTIONAL' },
  detected: { label: 'the audit finds the error', epistemic: 'INSTITUTIONAL' }, requested: { label: 'a correction is requested', epistemic: 'INSTITUTIONAL' }, approved: { label: 'the correction is approved', epistemic: 'INSTITUTIONAL' },
  score_updated: { label: 'the score is updated', epistemic: 'INSTITUTIONAL' }, released: { label: 'the binding constraint is released', epistemic: 'INSTITUTIONAL' }, restored: { label: 'the subsequent possibility is restored (access again, after the approval)', epistemic: 'INSTITUTIONAL' },
};
export type PathId = 'judgement' | 'effect' | 'correction' | 'subsequent';
/** One step of a path: the period at which a variable or transition of the model first holds for a subject (null: not within the periods), and the edge of the chain it is a transition on (null: a state with no edge of its own). */
export interface PathStep { id: string; label: string; variable: string; edge: [NodeId, NodeId] | null; at: (run: TERun, k: number) => number | null }
const firstT = (run: TERun, k: number, pred: (r: TERecord) => boolean, from = 0): number | null => run.records[k].find((r) => r.t >= from && pred(r))?.t ?? null;
const evAt = (name: ProcessEventId) => (run: TERun, k: number): number | null => run.process?.events[name]?.times[k] ?? null;
const apAt = (name: AppealStage) => (run: TERun, k: number): number | null => run.process?.appeal.stage_times[name]?.[k] ?? null;
const approvedAt = evAt('approved');
const afterApproval = (pred: (r: TERecord) => boolean) => (run: TERun, k: number): number | null => { const a = approvedAt(run, k); return a === null ? null : firstT(run, k, pred, a); };

/** Four paths through the chain, each an ordered list of real variables and transitions of the model, read for ONE subject so that a baseline and an intervention can be set side by side. Nothing here is a causal arrow: a step is
 *  reached when its variable holds, and the later steps of a path are what the model's own transitions produce from the earlier ones in that run. */
export const PATHS: Array<{ id: PathId; label: string; steps: PathStep[] }> = [
  { id: 'judgement', label: 'judgement path: observation to institutional adoption', steps: [
    { id: 'observed', label: 'a signal is obtained', variable: 'signal_measured', edge: ['subject', 'signal_sensor'], at: (r, k) => firstT(r, k, (x) => x.signal_measured !== null) },
    { id: 'adverse', label: 'the classifier gives an adverse label', variable: 'classification = adverse', edge: ['signal_sensor', 'classifier'], at: (r, k) => firstT(r, k, (x) => x.classification === -1) },
    { id: 'misclassified', label: 'it contradicts the verification label', variable: 'event misclassified (REFERENCE)', edge: ['classifier', 'acceptance'], at: evAt('misclassified') },
    { id: 'adopted', label: 'the institution adopts it', variable: 'event adopted', edge: ['acceptance', 'score'], at: evAt('adopted') }] },
  { id: 'effect', label: 'effect path: adoption to resources and access', steps: [
    { id: 'below', label: 'the score is below the threshold', variable: 'score < tau_a', edge: ['score', 'gate_a'], at: (r, k) => (r.config.use_score ? firstT(r, k, (x) => x.score < r.config.tau_a) : null) },
    { id: 'denied', label: 'access is denied', variable: 'event denied', edge: ['gate_a', 'resources'], at: evAt('denied') },
    { id: 'locked', label: 'a binding constraint is set', variable: 'locked', edge: null, at: (r, k) => firstT(r, k, (x) => x.locked) },
    { id: 'resources', label: 'resources fall below their starting level', variable: 'resources < 0.5', edge: ['resources', 'subject'], at: (r, k) => firstT(r, k, (x) => x.resources < 0.5) },
    { id: 'lost', label: 'an opportunity is lost', variable: 'opportunities_lost > 0', edge: null, at: (r, k) => firstT(r, k, (x) => x.opportunities_lost > 0) }] },
  { id: 'correction', label: 'correction path: refutation, appeal, correction, release', steps: [
    { id: 'detected', label: 'the audit finds the error', variable: 'event detected', edge: ['subject', 'correction'], at: evAt('detected') },
    { id: 'appeal_filed', label: 'the subject files an appeal', variable: 'appeal_filed', edge: null, at: apAt('appeal_filed') },
    { id: 'evidence', label: 'evidence is submitted', variable: 'evidence_submitted', edge: null, at: apAt('evidence_submitted') },
    { id: 'accepted', label: 'the appeal is accepted', variable: 'appeal_accepted', edge: null, at: apAt('appeal_accepted') },
    { id: 'rejudged', label: 're-judgement', variable: 'rejudged', edge: null, at: apAt('rejudged') },
    { id: 'requested', label: 'a correction is requested', variable: 'event requested', edge: null, at: evAt('requested') },
    { id: 'approved', label: 'the correction is approved', variable: 'event approved', edge: null, at: evAt('approved') },
    { id: 'score_updated', label: 'the score is updated', variable: 'event score_updated', edge: ['correction', 'score'], at: evAt('score_updated') },
    { id: 'released', label: 'the binding constraint is released', variable: 'event released', edge: ['correction', 'gate_a'], at: evAt('released') }] },
  { id: 'subsequent', label: 'subsequent path: what remains of the difference afterwards', steps: [
    { id: 'restored', label: 'access again after the approval', variable: 'event restored', edge: ['gate_a', 'resources'], at: evAt('restored') },
    { id: 'resources_back', label: 'resources are back at their starting level', variable: 'resources >= 0.5 after the approval', edge: ['resources', 'subject'], at: afterApproval((x) => x.resources >= 0.5) },
    { id: 'b_back', label: 'access at institution B after the approval', variable: 'access_b after the approval', edge: ['score', 'gate_b'], at: afterApproval((x) => x.access_b === true) }] },
];
export const COMPLEMENT_METRIC_IDS = ['denial_rate_late_unfav', 'lost_opportunities_per_unfav', 'share_unfav_ever_denied', 'state_change_unfav', 'state_change_unfav_denied', 'state_change_fav', 'state_gap_change', 'resources_end_unfav'] as const;
export const stepReached = (run: TERun, k: number, step: PathStep, t: number): boolean => { const a = step.at(run, k); return a !== null && a <= t; };

export type PathStatus = 'SAME' | 'EARLIER' | 'LATER' | 'ONLY_IN_BRANCH' | 'ONLY_IN_BASELINE' | 'NEITHER';
export interface PathRow { path: PathId; step: string; label: string; variable: string; base: number | null; branch: number | null; delta: number | null; status: PathStatus }
/** The four paths of one subject in the baseline and in the branch: the period at which each step first holds in each, the difference and its direction. Both runs come from the same seed, so the subject is the same one; whether
 *  the real state is the same is reported by ``compareRuns``. A step that holds in only one run is shown as that, not as a delay. */
export function comparePaths(base: TERun, branch: TERun | null, k: number): PathRow[] {
  const rows: PathRow[] = [];
  for (const p of PATHS) for (const s of p.steps) {
    const b = s.at(base, k), c = branch ? s.at(branch, k) : null;
    const status: PathStatus = !branch ? (b === null ? 'NEITHER' : 'SAME') : b === null && c === null ? 'NEITHER' : b === null ? 'ONLY_IN_BRANCH' : c === null ? 'ONLY_IN_BASELINE' : c === b ? 'SAME' : c < b ? 'EARLIER' : 'LATER';
    rows.push({ path: p.id, step: s.id, label: s.label, variable: s.variable, base: b, branch: c, delta: b !== null && c !== null ? c - b : null, status });
  }
  return rows;
}

/** The share of subjects that have each event and the mean period, for the table of the nine times. */
export function eventTable(run: TERun): Array<{ id: ProcessEventId; label: string; epistemic: Epistemic; n: number; of: number; mean: number | null }> {
  const p = run.process;
  return PROCESS_EVENTS.map((id) => ({ id, ...PROCESS_EVENT_LABELS[id], n: p?.events[id].n ?? 0, of: run.config.n, mean: p?.events[id].mean_time ?? null }));
}

// ------------------------------------------------------------------------------------------------ phase 4: the relations the user can select and compare, each tied to the engine's own records
export type RelationId = 'sensor_subject' | 'classifier_record' | 'score_judgement' | 'judgement_resources' | 'resources_state' | 'correction_release' | 'guarantee_subsequent';
export interface RelationReading {
  id: RelationId; from: Reading[]; rule: string; to: Reading[];
  /** holds: true or false where the relation is an identity of the model's own transition that the record lets us check at this period; null where it is not an identity (a drawn error) or cannot be checked here (the reason is in ``detail``) */
  check: { name: string; holds: boolean | null; detail: string };
}
export const RELATIONS: Array<{ id: RelationId; label: string; edges: Array<[NodeId, NodeId]> }> = [
  { id: 'sensor_subject', label: 'sensor and subject', edges: [['subject', 'pose_sensor'], ['subject', 'signal_sensor']] },
  { id: 'classifier_record', label: 'classifier and the observation record', edges: [['signal_sensor', 'classifier'], ['pose_sensor', 'classifier']] },
  { id: 'score_judgement', label: 'score and the institutional judgement', edges: [['score', 'gate_a']] },
  { id: 'judgement_resources', label: 'institutional judgement and the allocation of resources', edges: [['gate_a', 'resources']] },
  { id: 'resources_state', label: 'allocation of resources and the subject\'s state', edges: [['resources', 'subject']] },
  { id: 'correction_release', label: 'correction and the release of a constraint', edges: [['correction', 'score'], ['correction', 'gate_a']] },
  { id: 'guarantee_subsequent', label: 'guarantee and the subsequent possibility', edges: [['guarantee', 'gate_a'], ['guarantee', 'resources']] },
];
const R = (label: string, value: string, epistemic: Epistemic): Reading => ({ label, value, epistemic });
const clamp = (x: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, x));
/** The window mean of the signal the classifier read, from the records (rounded to 3 decimals there). */
function windowSignal(rs: TERecord[], t: number, w: number): number | null {
  const xs = rs.slice(Math.max(0, t - w + 1), t + 1).map((r) => r.signal_measured).filter((v): v is number => v !== null);
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
}

/** One relation of one subject at one period, read from the run's records. Nothing is simulated: a check compares what the record says with what the model's transition rule gives from the record's own previous values. */
export function relationAt(run: TERun, k: number, t: number, id: RelationId): RelationReading {
  const rs = run.records[k], i = Math.max(0, Math.min(t, rs.length - 1)), x = rs[i], p = i > 0 ? rs[i - 1] : null, c = run.config;
  const none = (name: string, detail: string) => ({ name, holds: null as boolean | null, detail });
  switch (id) {
    case 'sensor_subject': {
      const err = x.signal_measured === null ? null : x.signal_measured - x.reference_z;
      return { id, from: [R('reference state z', f(x.reference_z, 3), 'REFERENCE'), R('reference pose', x.pose_reference.map((v) => f(v, 1)).join(', '), 'REFERENCE')],
        rule: 'a sensor records the subject through its conditions (view angle, noise, bias, occlusion, dropout); the record is not the state',
        to: [R('measured signal', x.signal_measured === null ? 'nothing obtained' : f(x.signal_measured, 3), x.signal_measured === null ? 'UNRESOLVED' : 'OBSERVED'), R('measured pose', x.pose_measured.every((v) => v === null) ? 'nothing obtained' : x.pose_measured.map((v) => f(v, 1)).join(', '), x.pose_measured.every((v) => v === null) ? 'UNRESOLVED' : 'OBSERVED'),
          R('error of the signal (known to the evaluator only)', f(err, 3), 'REFERENCE')],
        check: none('no identity', 'the error is drawn from the sensor model: there is no transition identity to check') };
    }
    case 'classifier_record': {
      const m = windowSignal(rs, i, c.window), want = m === null ? 0 : m > c.signal_threshold ? 1 : -1;
      const checkable = c.classifier === 'signal_rule' && (m === null || Math.abs(m - c.signal_threshold) > 0.002);
      return { id, from: [R(`signal over the last ${c.window} periods (mean of those obtained)`, m === null ? 'nothing obtained' : f(m, 3), m === null ? 'UNRESOLVED' : 'OBSERVED')],
        rule: `${c.classifier}: favourable if the mean exceeds ${c.signal_threshold}, adverse if not, abstain if nothing was obtained${c.classifier === 'pose_rule' ? ' (invalid by construction: it reads the head pose)' : ''}`,
        to: [R('classification', x.classification === 1 ? 'favourable' : x.classification === -1 ? 'adverse' : 'abstained', 'CLASSIFIED'), R('P(z > 0 | evidence)', f(x.p_positive, 3), 'INFERRED'), R('warrant', x.warrant, 'INFERRED'),
          R('agrees with the verification label', x.classification_correct === null ? 'not applicable' : x.classification_correct ? 'yes' : 'no', 'REFERENCE')],
        check: checkable ? { name: 'classification = the rule applied to the recorded window', holds: x.classification === want, detail: `rule gives ${want}, record says ${x.classification}` } : none('classification = the rule applied to the recorded window', c.classifier === 'signal_rule' ? 'the window mean is within the record\'s rounding of the threshold' : 'checked for the signal rule only') };
    }
    case 'score_judgement': {
      const byGate = x.score >= c.tau_a && !x.locked, guard = x.guarantee_access === true, canCheck = c.use_score && (c.read_every_a ?? 1) === 1;
      return { id, from: [R('score', f(x.score, 3), 'INSTITUTIONAL'), R('threshold', f(c.tau_a), 'INSTITUTIONAL'), R('binding constraint', x.locked ? 'set' : 'none', 'INSTITUTIONAL')],
        rule: 'access = (score at or above the threshold and no binding constraint), or a hypothetical guarantee that keeps it',
        to: [R('access', x.access ? 'granted' : 'denied', 'INSTITUTIONAL'), R('granted by a guarantee', x.guarantee_access === undefined ? 'not recorded in this run' : guard ? 'yes' : 'no', x.guarantee_access === undefined ? 'UNRESOLVED' : 'INSTITUTIONAL')],
        check: canCheck ? { name: 'access = gate or guarantee', holds: x.access === (byGate || guard), detail: `gate ${byGate}, guarantee ${guard}, record ${x.access}` } : none('access = gate or guarantee', 'the score is not used, or is read less often than every period: not checked') };
    }
    case 'judgement_resources': {
      const clean = !(c.release_support) && !(c.correct_at !== null && c.reentry_support), floor = c.resource_floor ?? 0;
      const pred = p === null ? null : clamp(clamp(p.resources + c.gain * (x.access ? 1 : 0) - c.loss * (x.access ? 0 : 1), floor, 1) + (x.support ?? 0), floor, 1);   // the engine clips the allocation first and then adds the support
      return { id, from: [R('access this period', x.access ? 'granted' : 'denied', 'INSTITUTIONAL'), R('resources before', p === null ? 'no earlier period' : f(p.resources, 3), p === null ? 'UNRESOLVED' : 'INSTITUTIONAL'), R('support received', f(x.support ?? 0, 3), x.support === undefined ? 'UNRESOLVED' : 'INSTITUTIONAL')],
        rule: `resources = clip(clip(resources before + ${c.gain} x access - ${c.loss} x denial, floor ${floor}, 1) + support, floor ${floor}, 1)`,
        to: [R('resources', f(x.resources, 3), 'INSTITUTIONAL'), R('opportunities lost so far', String(x.opportunities_lost), 'INSTITUTIONAL')],
        check: pred === null || !clean ? none('resources follow the allocation rule', pred === null ? 'the first period has no earlier value' : 'a recovery measure also acts: not checked') : { name: 'resources follow the allocation rule', holds: Math.abs(pred - x.resources) <= 0.002, detail: `rule gives ${f(pred, 3)}, record says ${f(x.resources, 3)}` } };
    }
    case 'resources_state': {
      const d = p === null ? null : x.reference_z - p.reference_z, resid = d === null ? null : d - c.beta * (x.resources - 0.5);
      return { id, from: [R('resources', f(x.resources, 3), 'INSTITUTIONAL'), R('feedback beta', String(c.beta), 'INSTITUTIONAL')],
        rule: 'the state moves by beta x (resources - 0.5) plus noise of standard deviation 0.02: with beta 0 the institution does not change the state',
        to: [R('reference state z', f(x.reference_z, 3), 'REFERENCE'), R('change since the previous period', f(d, 3), 'REFERENCE'), R('residual after the rule (the noise)', f(resid, 3), 'REFERENCE')],
        check: resid === null ? none('change of state = beta x (resources - 0.5) + noise', 'the first period has no earlier value') : { name: 'change of state = beta x (resources - 0.5) + noise', holds: Math.abs(resid) <= 0.1, detail: `residual ${f(resid, 3)} (noise sd 0.02: within 5 sd)` } };
    }
    case 'correction_release': {
      const pr = run.process, ev = (name: ProcessEventId) => pr?.events[name]?.times[k] ?? null, a = ev('approved'), u = ev('score_updated'), rel = ev('released'), res = ev('restored');
      return { id, from: [R('correction approved', a === null ? 'not within the periods' : `period ${a}`, pr ? 'INSTITUTIONAL' : 'UNRESOLVED'), R('score updated', u === null ? 'not within the periods' : `period ${u}`, pr ? 'INSTITUTIONAL' : 'UNRESOLVED')],
        rule: 'the correction updates the score; the binding constraint ends only by its own rule (by the score, or after an approval, or never): two separate times',
        to: [R('constraint released', rel === null ? 'not within the periods' : `period ${rel}`, pr ? 'INSTITUTIONAL' : 'UNRESOLVED'), R('access restored', res === null ? 'not within the periods' : `period ${res}`, pr ? 'INSTITUTIONAL' : 'UNRESOLVED'), R('constraint in force now', x.locked ? 'yes' : 'no', 'INSTITUTIONAL')],
        check: pr ? { name: 'a release is never before the approval it follows (where it follows one)', holds: a === null || rel === null || c.release_mode !== 'after_approval' || rel >= a, detail: `approved ${a ?? '-'}, released ${rel ?? '-'}, rule ${c.release_mode ?? 'by_score'}` } : none('no process record', 'a run saved before phase 2 has no event times') };
    }
    case 'guarantee_subsequent': {
      const after = rs.slice(i), futureAccess = after.filter((r) => r.access).length, cum = rs.slice(0, i + 1).reduce((a, r) => a + (r.support ?? 0), 0);
      return { id, from: [R('guarantee conditions in force (hypothetical)', relationGuaranteeText(c), 'INSTITUTIONAL'), R('support received up to now', f(cum, 3), 'INSTITUTIONAL'), R('access granted by a guarantee up to now', String(rs.slice(0, i + 1).filter((r) => r.guarantee_access).length), 'INSTITUTIONAL')],
        rule: 'a guarantee changes the later possibilities only through the access it keeps and the resources it gives; nothing else in the model reads it',
        to: [R('access in the periods from now on', `${futureAccess} of ${after.length}`, 'INSTITUTIONAL'), R('resources now', f(x.resources, 3), 'INSTITUTIONAL'), R('state change since the start', f(x.reference_z - rs[0].reference_z, 3), 'REFERENCE')],
        check: none('no identity', 'the effect of a guarantee is read from a branch compared with its baseline, not from one run') };
    }
  }
}
function relationGuaranteeText(c: TEConfig): string {
  return [c.resource_floor ? `floor ${c.resource_floor}` : null, c.denial_cap ? `cap ${c.denial_cap}` : null, c.interim_access ? 'access pending a correction' : null, c.release_support ? `recovery ${c.release_support}` : null, c.support_rule && c.support_rule !== 'none' ? `support ${c.support_rule}` : null].filter(Boolean).join('; ') || 'none';
}
/** The same relation in a baseline and in a branch, for the same subject and period; the change of the configuration is listed by ``compareRuns``. */
export function compareRelation(base: TERun, branch: TERun | null, k: number, t: number, id: RelationId): { base: RelationReading; branch: RelationReading | null } {
  return { base: relationAt(base, k, t, id), branch: branch ? relationAt(branch, k, t, id) : null };
}
