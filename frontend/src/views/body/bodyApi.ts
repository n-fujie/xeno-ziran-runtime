// BODY / TOTAL OBSERVATION — the client side of the TEOO API (backend/xzr/teoo). Types of the records, the body graph and the coverage, and the requests.
// Nothing here measures or simulates: every class, status and time the view shows is read from a record the backend sealed.

export type Provenance = 'MEASURED' | 'SYNTHETIC' | 'RECONSTRUCTED_ESTIMATE' | 'CONCEPTUAL';
export type RecordKind = 'REFERENCE_STATE' | 'OBSERVATION' | 'ESTIMATE' | 'RECONSTRUCTION';
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
async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`${path}: ${r.status}${r.status === 403 ? ' (these routes are local-runtime only)' : ''}`);
  return r.json() as Promise<T>;
}
async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json() as Promise<T>;
}
export const teooDemo = (seed = 7) => get<DemoResponse>(`/demo?seed=${seed}`);
export const teooBodyPreset = (name: string) => get<{ body: TeooBody; issues: Array<{ code: string }>; concept_only: boolean }>(`/body/${name}`);
export const teooCoverage = (records: TeooRecord[], bodyPreset: string) => post<Coverage>('/coverage', { records, body_preset: bodyPreset });
