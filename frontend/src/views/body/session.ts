// BODY / TOTAL OBSERVATION, Phase 3 — the session bundle every view reads (GET /api/teoo/session) and the pure selectors the views use.
// One bundle: the same record ids, the same time base (device time, seconds), the same body configuration versions. Nothing here measures or simulates.
import type { Coverage, EvidenceLabel, TeooBody, TeooChannel, TeooRecord } from './bodyApi';

export interface ObsSensor { id: string; channels: string[]; resolution: number | null; sampling_period_s: number | null; window_s: number | null; detection_limit: number | null; penetration: number | null; health: number; reach: string[] | null }
export interface ObsConfig { version: number; parent: number | null; at: number; label: string; sensors: ObsSensor[]; body_version: number | null; change: { op: string; reason?: string; params?: unknown } }
export interface TargetSpec { id: string; channel: string; scale: number | null; phenomenon_period_s: number | null; amplitude: number | null; opacity: number | null }
export interface Assessment { status: string; causes: string[]; cause_known: boolean; undetermined: string[]; sensor: string | null; detail: string[] }
export interface ObsState { t: number; version: number; config_digest: string; body_version: number | null; targets: Record<string, Assessment>; summary: Record<string, number>; claim_note: string; declared_targets: number; observed: number; note: string }
export interface RevisionEvent { seq: number; type: string; status: 'proposed' | 'recorded' | 'validated'; reason: string; at: number; initiated_by: string; autonomous_revision_demonstrated: boolean; before_version: number; after_version: number | null;
  lost: Array<{ target: string; to: string }>; gained: Array<{ target: string; from: string }>; changed: Array<{ target: string; from: string; to: string }>; note: string }
export interface ObservedDifference { variable: string; pre_record: string; post_record: string; intervention_record: string | null; mean_pre: number | null; mean_post: number | null; observed_difference: number | null; n_pre: number; n_post: number;
  observation_configuration_changed: boolean; causal_claim: null; reading: string; pre_counts: Record<string, number>; post_counts: Record<string, number> }
export interface Protocol { experiment_id: string; version: number; hypotheses: Array<{ id: string; statement: string }>; conditions: string[]; control_condition: string; seeds: number[]; trials_per_condition: number; stopping_rule: Record<string, unknown>;
  analyses: Array<{ id: string; hypothesis: string; method: string; confirmatory?: boolean }>; multiplicity: string; failure_conditions: string[]; reproduction: { generator: string; steps: string[] }; targets: string[] }
export interface Relation { id: string; dimension: string; observed: boolean; accessible: boolean | null; judgment_changing: boolean | null; note: string }
export interface Session {
  banner: string; synthetic: boolean; seed: number; time_base: string; records: TeooRecord[]; record_index: Record<string, { provenance: string; kind: string; label: string }>; evidence: EvidenceLabel[];
  bodies: Record<string, TeooBody>; body_versions: { before: number; after: number }; coverage: Coverage;
  observation: { history: ObsConfig[]; specs: TargetSpec[]; revisions: RevisionEvent[]; times: number[]; states: ObsState[]; replay_check: Array<{ event: number; version_ok: boolean }> };
  reconstruction: { record_id: string; input_record_id: string; lost: { interval_s: [number, number]; n_samples: number; statement: string }; variable: string };
  intervention: { record_id: string; pre: string; post: string; counterfactual: string; observed_difference: ObservedDifference; identification: { status: string; why_not_causal: string[]; assumptions: string[]; statement: string };
    model: { assumptions: string[]; identification: string[]; scope: string } };
  protocol: { protocol: Protocol; amended: { version: number; parent_version: number; change_reason: string }; run: { experiment_id: string; version: number; n_trials: number; results: Record<string, { effect: number; p: number; inferential: boolean; lag1_autocorrelation: number | null; n_a: number; n_b: number }>;
    adjusted: Record<string, { p: number; p_holm: number }>; generator_note: string }; n_trials: number; trials_head: Array<{ seed: number; trial: number; condition: string; value: number }>; analysis_classes: Record<string, string>;
    reproduction: { identical: boolean; trials_digest: string }; registry_ok: boolean };
  relation_field: { task: string; relations: Relation[]; observed: string[]; accessible_but_unobserved: string[]; inaccessible: string[]; access_unknown: string[]; judgment_open: string[]; epistemically_open: boolean; generalisation_allowed: boolean; reading: string; note: string };
  ledger: { entries: number; issues: unknown[] };
}

export const STATUS_COLOR: Record<string, string> = { MEASURED_VALID: '#cfd6e4', MISSING: '#ff8a70', INVALID: '#ff5a4a', BOUNDARY_INVISIBLE: '#c9a227', TIME_WINDOW_MISMATCH: '#9bb0d0', INSTRUMENT_MISMATCH: '#b07acc',
  SIGNAL_BELOW_THRESHOLD: '#78e696', SCALE_MISMATCH: '#7ad0d0', UNMEASURED: '#555555', UNMEASURABLE: '#777777', UNKNOWN_CAUSE: '#ffffff' };

export const recordOf = (s: Session, id: string): TeooRecord | undefined => s.records.find((r) => r.record_id === id);
export const channelOf = (r: TeooRecord, variable: string): TeooChannel | undefined => r.payload.channels?.find((c) => c.variable === variable);

export interface Run { from: number; to: number; status: string }
/** Runs of equal status along a channel (a gap is a run with its own status: it is shown, not skipped). Indices are sample indices. */
export function statusRuns(ch: TeooChannel): Run[] {
  const out: Run[] = [];
  ch.samples.forEach((s, i) => { const last = out[out.length - 1]; if (last && last.status === s.status) last.to = i; else out.push({ from: i, to: i, status: s.status }); });
  return out;
}

/** The polyline point lists of a channel, broken at every sample that is not MEASURED_VALID: no line is drawn across a gap. */
export function segments(ch: TeooChannel, x: (t: number) => number, y: (v: number) => number): string[] {
  const out: string[] = []; let cur: string[] = [];
  ch.samples.forEach((s, i) => { if (s.status === 'MEASURED_VALID' && s.value !== null) cur.push(`${x(ch.times[i]).toFixed(1)},${y(s.value).toFixed(1)}`); else if (cur.length) { out.push(cur.join(' ')); cur = []; } });
  if (cur.length) out.push(cur.join(' '));
  return out;
}

export const validRange = (ch: TeooChannel): [number, number] => {
  const v = ch.samples.filter((s) => s.status === 'MEASURED_VALID' && s.value !== null).map((s) => s.value as number);
  return v.length ? [Math.min(...v), Math.max(...v)] : [0, 1];
};

export type Level = { id: number; name: string; note: string };
export const LEVELS: Level[] = [
  { id: 1, name: 'recorded observation', note: 'what an apparatus acquired and a record holds' },
  { id: 2, name: 'estimate / reconstruction', note: 'computed from records by a method; not observed' },
  { id: 3, name: 'intervention', note: 'what was done; not what followed' },
  { id: 4, name: 'counterfactual model', note: 'what a declared model says would have happened; not an observation' },
  { id: 5, name: 'experiment (protocol)', note: 'pre-registered conditions, seeds, trials and analyses' },
  { id: 6, name: 'hypothesised or unobserved relation', note: 'declared relations that are not observed; unknown is not absent' },
  { id: 7, name: 'unobserved difference', note: 'targets whose observation is limited; not observed is not absent' },
];

export interface Row { level: number; item: string; cls: string; record: string; note: string }
/** The integrated table of View H: every row keeps its level, its provenance class and its record id; nothing is merged across levels. */
export function integratedRows(s: Session, t: number): Row[] {
  const rows: Row[] = [];
  for (const r of s.records) {
    const lv = r.kind === 'OBSERVATION' ? 1 : r.kind === 'ESTIMATE' || r.kind === 'RECONSTRUCTION' ? 2 : r.kind === 'INTERVENTION' ? 3 : r.kind === 'COUNTERFACTUAL_MODEL' ? 4 : 1;
    rows.push({ level: lv, item: `${r.kind} ${r.payload.channels?.map((c) => c.variable).join(', ') ?? ''}`.trim(), cls: r.provenance, record: r.record_id, note: s.record_index[r.record_id]?.label ?? '' });
  }
  for (const a of s.protocol.protocol.analyses) rows.push({ level: 5, item: `${s.protocol.protocol.experiment_id} v${s.protocol.run.version} ${a.id}`, cls: 'SYNTHETIC', record: s.protocol.protocol.experiment_id, note: s.protocol.analysis_classes[a.id] ?? '' });
  for (const id of s.relation_field.judgment_open) rows.push({ level: 6, item: `relation ${id}`, cls: 'declared', record: '-', note: 'not observed; could change the judgment (or unknown)' });
  const st = s.observation.states.reduce((a, b) => (Math.abs(b.t - t) < Math.abs(a.t - t) ? b : a));
  for (const [tid, a] of Object.entries(st.targets)) if (a.status !== 'MEASURED_VALID') rows.push({ level: 7, item: tid, cls: 'unobserved', record: '-', note: `${a.status}${a.causes.length ? ` (${a.causes.join(' + ')})` : ''} at t = ${st.t} s, configuration v${st.version}` });
  return rows.sort((p, q) => p.level - q.level);
}
