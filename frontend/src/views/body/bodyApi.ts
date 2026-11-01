// BODY / TOTAL OBSERVATION — the client side of the TEOO API (backend/xzr/teoo). Types of the records, the body graph and the coverage, and the requests.
// Nothing here measures or simulates: every class, status and time the view shows is read from a record the backend sealed.

export type Provenance = 'MEASURED' | 'SYNTHETIC' | 'RECONSTRUCTED_ESTIMATE' | 'CONCEPTUAL';
export type RecordKind = 'REFERENCE_STATE' | 'OBSERVATION' | 'ESTIMATE' | 'RECONSTRUCTION' | 'INTERVENTION' | 'COUNTERFACTUAL_MODEL';
export type DisplayClass = 'measured' | 'synthetic' | 'estimated' | 'conceptual' | 'unmeasured' | 'limited';

export interface TeooSample { value: number | null; status: string; causes: string[]; cause_known: boolean; detection_limit: number | null; detail: unknown }
export interface TeooChannel { variable: string; target: string | null; unit: string | null; times: number[]; samples: TeooSample[]; counts: Record<string, number> }
export interface TeooRecord {
  schema: string; record_id: string; record_digest: string; provenance: Provenance; kind: RecordKind; lineage_classes: Provenance[]; created_at: string;
  creator: { name: string }; source: { kind: string; description: string }; derived_from: Array<{ record_id: string; record_digest: string }>;
  raw: { digest: string; bytes: number; origin: string };
  payload: { banner?: string; body?: { id: string | null; version: number | null }; time?: Record<string, unknown>; channels?: TeooChannel[] };
}
export interface TeooComponent { id: string; kind: string; label: string; attrs: { concept_layout?: { x: number; y: number }; concept_only?: boolean; [k: string]: unknown } }
export interface TeooRelation { id: string; source: string; target: string; kind: string; directed: boolean; basis: string; claim: string; state: string }
export interface TeooTarget { id: string; ref: string; variables: string[]; anatomical_ref: string | null }
export interface TeooVersion { version: number; components: TeooComponent[]; relations: TeooRelation[]; targets: TeooTarget[]; boundaries: Array<{ id: string; members: string[]; description: string }>; change: { op: string }; digest: string }
export interface TeooBody { id: string; name: string; family: string; versions: TeooVersion[]; meta: { preset?: string; concept_only?: boolean; note?: string } }
export interface TargetState {
  target: string; ref: string; variables: string[]; display_class: DisplayClass; state: string; records: string[]; classes: Provenance[]; kinds?: RecordKind[]; counts: Record<string, number>;
  causes: string[]; device_time_range_s?: [number, number] | null; mixed_classes?: boolean; note?: string;
}
export interface Coverage { body: string; version: number; targets: Record<string, TargetState>; by_ref: Record<string, DisplayClass>; unmeasured_refs: string[]; summary: Record<DisplayClass, number> }
export interface EvidenceLabel { record_id: string; provenance: Provenance; kind: RecordKind; label: string; note: string; claim_status_hint: string; is_evidence: boolean }
export interface TeooInfo {
  version: string; presets: string[]; protections: { implemented: string[]; not_implemented: string[] }; limits: string[]; stored_on_server: boolean; statuses: string[];
  retained_results: Array<{ id: string; status: string; source: string; scope: string }>; domains: Array<{ id: string; label: string }>;
}
export interface DemoResponse {
  banner: string; synthetic: boolean; body: TeooBody; records: TeooRecord[]; evidence: EvidenceLabel[]; coverage: Coverage;
  ledger: { entries: number; issues: Array<{ code: string }>; checkpoint: { seq: number; head_hash: string } }; info: TeooInfo;
}

const API = '/api/teoo';
// Preview build (VITE_TEOO_PREVIEW=1): a read-only static page. Every call is answered from a fixed SYNTHETIC fixture that the backend wrote (backend/scripts/export_teoo_preview.py); no API exists there and nothing is sent anywhere.
const PREVIEW = import.meta.env.VITE_TEOO_PREVIEW === '1';
const FIXTURE = '/teoo-preview';
function fixtureOf(path: string, body?: { kind?: string; body_preset?: string }): string {
  const p = path.split('?')[0];
  if (p === '/demo') return 'demo.json';
  if (p === '/session') return 'session.json';
  if (p === '/safety') return 'safety.json';
  if (p === '/legal') return 'legal.json';
  if (p.startsWith('/body/')) return `body-${p.slice(6).replace(/[^a-z0-9-]/g, '')}.json`;
  if (p === '/coverage') return `coverage-${String(body?.body_preset ?? '').replace(/[^a-z0-9-]/g, '')}.json`;
  if (p === '/figure') return `figure-${String(body?.kind ?? '').replace(/[^a-z]/g, '')}.json`;
  throw new Error(`${path}: not available in the read-only preview`);
}
async function get<T>(path: string): Promise<T> {
  const r = await fetch(PREVIEW ? `${FIXTURE}/${fixtureOf(path)}` : `${API}${path}`);
  if (!r.ok) throw new Error(`${path}: ${r.status}${r.status === 403 ? ' (these routes are local-runtime only)' : ''}`);
  return r.json() as Promise<T>;
}
async function post<T>(path: string, body: unknown): Promise<T> {
  if (PREVIEW) { const r = await fetch(`${FIXTURE}/${fixtureOf(path, body as { kind?: string; body_preset?: string })}`); if (!r.ok) throw new Error(`${path}: ${r.status}`); return r.json() as Promise<T>; }
  const r = await fetch(`${API}${path}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json() as Promise<T>;
}
export const teooDemo = (seed = 7) => get<DemoResponse>(`/demo?seed=${seed}`);
export const teooBodyPreset = (name: string) => get<{ body: TeooBody; issues: Array<{ code: string }>; concept_only: boolean }>(`/body/${name}`);
export const teooCoverage = (records: TeooRecord[], bodyPreset: string) => post<Coverage>('/coverage', { records, body_preset: bodyPreset });

// Phase 3: the session bundle, the replayed observation state, figures, the safety status
import type { ObsState, Session } from './session';
export const teooSession = (seed = 7) => get<Session>(`/session?seed=${seed}`);
export const teooObservation = (t: number, seed = 7) => get<ObsState>(`/observation?t=${t}&seed=${seed}`);
export interface FigureOut { svg: string; metadata: { figure_id: string; evidence: { classes: string[]; watermarks: string[]; band: string[] } }; metadata_ascii: string; issues: string[] }
export const teooFigure = (kind: string, seed = 7) => post<FigureOut>('/figure', { kind, seed });
export interface SafetyOut { production_ready: boolean; human_measurement_ingestion_allowed: boolean; missing: Array<{ id: string; needed: string }>; note: string; capabilities: Array<{ id: number; name: string; implemented: boolean; limits: string }>;
  threats: Array<{ id: string; threat: string; defence: string }>; stored_on_server: boolean }
export const teooSafety = () => get<SafetyOut>('/safety');

// AI legal governance: the fifteen guarantees by their source titles (V3.0 6.2; the wording is held privately and shown only where the private store is attached), their operational definitions in the synthetic institution, one finding each (never a total), the finding U, the legal translation chain, the register
export type GState = 'SECURED' | 'PARTIAL' | 'ABSENT' | 'INDETERMINATE' | 'INAPPLICABLE';
export interface SubFinding { id: string; state: GState; hard_failure: boolean; reason: string; operational_definition: string; evidence_tier: number | null; evidence_basis: string | null; formal_exists: boolean | null }
export interface GuaranteeFinding { number: number; id: string; title: string; definition: string | null; source_position: number; audit_questions: string[]; audit_question_count: number; operational_definition: string; state: GState; hard_failure: boolean; reason: string; remedy_path: string;
  sub_findings: SubFinding[]; evidence_missing: string[]; adverse_inference_available: boolean; applicable: boolean; catalogue_verified: boolean; formal_exists: boolean }
export interface UFinding { state: GState; hard_failure: boolean; reason: string; failed_in: string[]; untested: string[] }
export interface AuditMeta { sub_findings: SubFinding[]; U: UFinding; outcome_taxonomy: Record<string, string[] | Record<string, string>>; run: Record<string, number | null>; recommendation: { candidate: string; advisory_only: boolean; decided_by: string; rule_source: string; hard_failures: string[] }; no_total: string }
export interface ChainStage { stage: string; layer: string; legal_basis: string | null; jurisdiction: string | null; rule_version: string | null; scope: string; responsible: string; evidence: string; uncertainty: string; authority: string | null; contest_path: string | null; by_ai: boolean }
export interface ChainAssessment { stages: Array<{ stage: string; layer: string; valid: boolean; why_not: string[]; uncertainty: string; responsible: string }>; valid_legal_decision: boolean; first_invalid_stage: string | null; issues: string[]; unresolved_legal_questions: string[]; reading: string }
export interface InterventionRow { exclusion_qualified: number; exclusion_persistence: number; tpr_gap: number; group_exclusion_gap: number; downstream_access_qualified: number; overturn_rate_of_wrongful: number; formal_appeal_rate: number; burden_subject: number; burden_institution: number; series_exclusion: number[] }
export interface RegisterRow { variable: string; legal_source: string | null; purpose: string; proxy_for: string | null; threshold: number | null; translation_loss_disclosed: boolean; recipients: string[]; version: string; responsible: string }
export type DState = 'SATISFIED' | 'PARTIALLY_SATISFIED' | 'VIOLATED' | 'INSUFFICIENT_EVIDENCE' | 'NOT_APPLICABLE' | 'NOT_EVALUATED';
export interface MhegDuty { id: string; name: string; label_ja: string; function: string; crosswalk_as_reported: string; findings: string[]; mapping_kind: 'direct' | 'composite' | 'broad'; evaluation_target: string; required_evidence: string; cannot_verify: string;
  definition_status: string; source: string; identity_with_guarantees: string }
export interface MhegFindingState { state: DState; legacy_state: GState; observed: boolean; hard_failure: boolean }
export interface MhegStage { id: string; label: string; operating_condition: string; authority_relation: string; findings: Record<string, DState>; state: DState; observability: string; time_span: string; resource_condition: string; evidence: Record<string, string | null>;
  failure_condition: string; recovery_path: string[] }
export interface MhegBundle { duties: MhegDuty[]; crosswalk: { findings: string[]; duties: string[]; matrix: Record<string, number[]>; duties_per_finding: Record<string, number>; findings_per_duty: Record<string, number>; not_named_by_any_duty: string[]; named_by_one_duty: string[];
  broad_duties: string[]; note: string };
  projections: Record<string, { findings: Record<string, MhegFindingState>; duties: Record<string, { state: DState; drivers: string[]; findings: Record<string, DState> }> }>;
  chains: Record<string, { stages: MhegStage[]; first_violated_stage: string | null; effective_to_the_end: boolean; information_lost_in_translation: string[]; rule: string; stage_assignment: string }>; chain_definition: Array<{ id: string; label: string; findings: string[] }>;
  fidelity: Record<string, { implemented: string; not_implemented: string; normative_unverifiable: string }>; governance_principles: { status: string; reported_count: number; reported_source: string; items: unknown[]; rule: string; to_check_when_available: string[] };
  states: DState[]; components: Record<string, string[]>; unverified: string[]; limits: string; seed: number }
export interface LegalBundle { synthetic: boolean; catalogue: { source: string; verified_against_original: boolean; sha256: Record<string, string>; editions_identical_for_guarantees: boolean | null; note: string }; states: string[];
  guarantees: Array<{ number: number; title: string; definition: string | null; source_position: number; audit_questions: string[]; audit_question_count: number }>; text_available: boolean; sub_finding_definitions: Record<string, string>; assessments: Record<string, GuaranteeFinding[]>; audits: Record<string, AuditMeta>;
  chains: Record<string, { chain: ChainStage[]; assessment: ChainAssessment }>; register: Record<string, RegisterRow[]>; interventions: Record<string, InterventionRow>; inheritance: Record<string, { finding: string; reason?: string; safeguards?: Record<string, boolean>; endogenous_share?: number }>;
  observation: { observed_findings: string[]; not_observed_findings: string[]; note: string }; software_limit: string; scope: string; seed: number; mheg: MhegBundle; observed_by_assessment: Record<string, string[] | null> }
export const teooLegal = (seed = 3) => get<LegalBundle>(`/legal?seed=${seed}`);
