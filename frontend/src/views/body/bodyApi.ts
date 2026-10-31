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

// AI legal governance: the fifteen guarantees (a PROVISIONAL catalogue), the legal translation chain, the comparison of interventions on a synthetic institution
export interface GuaranteeAssessment { number: number; title: string; provision: string; applicable: boolean; required_evidence: string; institutional_function: string; state: 'SECURED' | 'PARTIAL' | 'ABSENT' | 'INDETERMINATE' | 'INAPPLICABLE'; reason: string; remedy_path: string; effectiveness_indicator: number | null; catalogue_verified: boolean }
export interface ChainStage { stage: string; legal_basis: string | null; scope: string; responsible: string; evidence: string; uncertainty: string; authority: string | null; contest_path: string | null; by_ai: boolean }
export interface ChainAssessment { stages: Array<{ stage: string; valid: boolean; why_not: string[]; uncertainty: string; responsible: string }>; valid_legal_decision: boolean; first_invalid_stage: string | null; issues: string[]; reading: string }
export interface InterventionRow { exclusion_qualified: number; exclusion_persistence: number; tpr_gap: number; group_exclusion_gap: number; downstream_access_qualified: number; overturn_rate_of_wrongful: number; formal_appeal_rate: number; burden_subject: number; burden_institution: number; series_exclusion: number[] }
export interface LegalBundle { synthetic: boolean; catalogue: { source: string; verified_against_original: boolean; note: string }; states: string[]; guarantees: Array<{ number: number; title: string; description: string }>; assessments: Record<string, GuaranteeAssessment[]>;
  chains: Record<string, { chain: ChainStage[]; assessment: ChainAssessment }>; interventions: Record<string, InterventionRow>; observation: { observed_provisions: string[]; not_observed_provisions: string[]; note: string }; scope: string; seed: number }
export const teooLegal = (seed = 3) => get<LegalBundle>(`/legal?seed=${seed}`);
