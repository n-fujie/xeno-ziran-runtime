// REST + WebSocket access to the backend. All paths are same-origin (Vite proxies in development).

import type { Listing } from './results';
import { isGone, markGone, provesGone, SessionGoneError, sessionOf } from './sessionGone';
import { decodeFrame, decodeTile, type Frame, type Tile } from '../proto/decode';
import { NATIVE, NativeSocket, nativeFetch } from './native';

// The iOS app reaches its in-process runtime through the native bridge; every other build uses HTTP.
const send: (path: string, init?: RequestInit) => Promise<Response> = NATIVE ? nativeFetch : (p, i) => fetch(p, i);

export interface SessionInfo {
  id: string;
  scenario: { name: string; description: string };
  n: number; e_cap: number; t: number; running: boolean; speed: number; steps_per_second: number;
  connections: number; checkpoints: number[]; layout_version: number; draft_differs: boolean;
  params: Record<string, number>; quant_max: number; mem_qmax: number; n_forms: number;
  scales: string[]; layouts: string[]; clusters_per_level: number[]; geo_count: number; sets: string[];
  boundaries: Record<string, number>;
  runtime_flags?: Record<string, string | boolean>; runtime_is_full?: boolean;
  /** how the address hierarchy was obtained: 'computed', 'reference', or computed on device (may differ) */
  hierarchy_source?: string;
}

export interface Status {
  t: number; running: boolean; speed: number; speed_limit?: number | null; pending_steps: number; steps_per_second: number;
  connections: number; checkpoints: number[]; layout_version: number; draft_differs: boolean;
}

export interface ClusterSummary {
  level: number; addresses: string[]; parents: number[]; count: number[];
  centroids: Record<string, ([number | null, number | null])[]>;
  spread: Record<string, (number | null)[]>;
  flows: [number, number, number, number, number][];
  layout_version: number;
}

/** Sessions are ephemeral: they end on expiry, when closed, or when the runtime restarts. Nothing is persisted. */
export const SESSION_GONE = NATIVE
  ? 'This session no longer exists in the on-device runtime (the app was closed or ended by the system, or the '
    + 'session was closed; sessions are not persisted). Start a new session; use Save to keep a copy of your work.'
  : 'This session no longer exists on the runtime (it expired, was closed, or the runtime '
    + 'restarted; sessions are not persisted). Reload to start a new session; use Save to keep a copy of your work.';

export class ApiError extends Error {
  constructor(msg: string, public status: number, public body: unknown) {
    super(msg);
  }
}

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const bound = sessionOf(path);
  if (bound && isGone(bound)) throw new SessionGoneError(bound);  // never re-request a session known to be gone
  const r = await send(path, { headers: { 'Content-Type': 'application/json' }, ...init });
  const body = r.headers.get('content-type')?.includes('json') ? await r.json() : await r.text();
  if (!r.ok) {
    // a refused limit names itself: {"error": "...", "limit": "max_nodes"}
    const b = (typeof body === 'object' && body ? body : {}) as { error?: string; limit?: string; detail?: unknown };
    const detail = typeof b.detail === 'string' ? b.detail : b.detail !== undefined ? JSON.stringify(b.detail) : undefined;
    const msg = b.error ? (b.limit ? `${b.error} [limit: ${b.limit}]` : b.error)
      : r.status === 404 && detail === 'no such session' ? SESSION_GONE : detail ?? String(body);
    if (bound && provesGone(path, r.status, detail)) markGone(bound);
    throw new ApiError(msg, r.status, body);
  }
  return body as T;
}

const post = <T>(path: string, body: unknown) => j<T>(path, { method: 'POST', body: JSON.stringify(body) });

export const api = {
  health: () => j<{ ok: boolean; public?: boolean; max_nodes?: number }>('/api/health'),
  scenarios: () => j<{ id: string; name: string; description: string; configurations: number }[]>('/api/scenarios'),
  createSession: (sample: string, flags?: string) => post<SessionInfo>('/api/sessions', { sample, flags }),
  loadSession: (saved: { scenario: unknown; applied?: unknown }) =>
    post<SessionInfo>('/api/sessions', { scenario: saved.scenario, applied: saved.applied }),
  sessions: () => j<{ id: string; scenario: string; t: number }[]>('/api/sessions'),
  deleteSession: (sid: string) => j<{ deleted: string }>(`/api/sessions/${sid}`, { method: 'DELETE' }),
  info: (sid: string) => j<SessionInfo>(`/api/sessions/${sid}`),
  control: (sid: string, action: string, extra: { steps?: number; speed?: number } = {}) =>
    post<Status>(`/api/sessions/${sid}/control`, { action, ...extra }),
  rewind: (sid: string, t: number) => post<Status>(`/api/sessions/${sid}/rewind`, { t }),
  clusters: (sid: string, level: number) => j<ClusterSummary>(`/api/sessions/${sid}/clusters?level=${level}`),
  tile: async (sid: string, layout: string, level: number, b: [number, number, number, number], maxEdges = 20000): Promise<Tile> => {
    const q = `layout=${layout}&level=${level}&x0=${b[0]}&y0=${b[1]}&x1=${b[2]}&y1=${b[3]}&max_edges=${maxEdges}`;
    if (isGone(sid)) throw new SessionGoneError(sid);
    const path = `/api/sessions/${sid}/tile?${q}`;
    const r = await send(path);
    if (!r.ok) {
      const text = await r.text();
      let detail: unknown;
      try { detail = (JSON.parse(text) as { detail?: unknown }).detail; } catch { detail = undefined; }
      if (provesGone(path, r.status, detail)) markGone(sid);
      throw new ApiError(text, r.status, null);
    }
    return decodeTile(await r.arrayBuffer());
  },
  node: (sid: string, i: number) => j<NodeDetail>(`/api/sessions/${sid}/node/${i}`),
  metrics: (sid: string, since = 0) => j<Metrics>(`/api/sessions/${sid}/metrics?since=${since}`),
  shapes: (sid: string) => j<Shapes>(`/api/sessions/${sid}/shapes`),
  practice: (sid: string) => j<PracticeView>(`/api/sessions/${sid}/practice`),
  command: (sid: string, text: string, horizon = 150) =>
    post<CommandReport>(`/api/sessions/${sid}/practice/command`, { text, horizon }),
  compare: (sid: string, horizon: number) => post<{ job: string }>(`/api/sessions/${sid}/compare`, { horizon }),
  compareResult: (sid: string, cid: string) => j<CompareResult>(`/api/sessions/${sid}/compare/${cid}`),
  job: (jid: string) => j<Job>(`/api/jobs/${jid}`),
  save: (sid: string) => j<{ scenario: unknown; applied: unknown }>(`/api/sessions/${sid}/save`),
  exportUrl: (sid: string, what: string, format: string) => `/api/sessions/${sid}/export?what=${what}&format=${format}`,
  experiments: () => j<Listing>('/api/experiments'),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  experiment: <T = any>(name: string) => j<T>(`/api/experiments/${name}`),
  primitives: () => j<PrimitiveEntry[]>('/api/experiments/primitives'),
  // Studies (local runtime only): protocols, runs, analysis, reports, packages, replay and reproduction.
  studyLineage: () => j<StudyAnalysis>('/api/studies/lineage'),
  studyConditions: (environment: StudyProtocol) => j<{ issues: string[]; conditions: StudyAnalysis | null }>(`/api/studies/totalobs/conditions?env=${encodeURIComponent(JSON.stringify(environment))}`),
  studyTemplates: () => j<Record<string, StudyProtocol>>('/api/studies/templates'),
  studyValidate: (protocol: StudyProtocol) => post<StudyValidation>('/api/studies/validate', { protocol }),
  studyCreate: (protocol: StudyProtocol) => post<StudySummary>('/api/studies', { protocol }),
  studies: () => j<StudySummary[]>('/api/studies'),
  study: (id: string) => j<StudyDetail>(`/api/studies/${id}`),
  studyStatus: (id: string) => j<StudyStatus>(`/api/studies/${id}/status`),
  studyLog: (id: string, limit = 200) => j<{ at: string; event: string; [k: string]: unknown }[]>(`/api/studies/${id}/log?limit=${limit}`),
  studyRun: (id: string, procs: number) => post<StudyStatus>(`/api/studies/${id}/run`, { procs }),
  studyStop: (id: string) => post<StudyStatus>(`/api/studies/${id}/stop`, {}),
  studyAmend: (id: string, path: string, value: unknown, reason: string) =>
    post<Record<string, unknown>>(`/api/studies/${id}/amend`, { path, value, reason }),
  studyRuns: (id: string) => j<StudyRunRow[]>(`/api/studies/${id}/runs`),
  studyRunRecord: (id: string, arm: string, k: number) =>
    j<StudyRunRecord>(`/api/studies/${id}/runs/${encodeURIComponent(arm)}/${k}`),
  studyReplay: (id: string, arm: string, k: number) =>
    post<{ agreement: boolean; metrics_differing: string[]; condition: string }>(`/api/studies/${id}/runs/${encodeURIComponent(arm)}/${k}/replay`, {}),
  studyAnalyse: (id: string) => post<StudyAnalysis>(`/api/studies/${id}/analyse`, {}),
  studyAnalysis: (id: string) => j<StudyAnalysis>(`/api/studies/${id}/analysis`),
  studyReport: (id: string) => post<{ files: string[]; figures: { file: string; caption: string; png: string | null }[] }>(`/api/studies/${id}/report`, {}),
  studyReportUrl: (id: string, name: string) => `/api/studies/${id}/report/${name}`,
  studyReportText: async (id: string, name: string) => (await fetch(`/api/studies/${id}/report/${name}`)).text(),
  studyPackage: (id: string) => post<{ zip: string; bytes: number; verify: { ok: boolean; files: number } }>(`/api/studies/${id}/package`, {}),
  studyPackageUrl: (id: string) => `/api/studies/${id}/package.zip`,
  studyVerify: (id: string) => j<{ ok: boolean; files: number; mismatched: string[]; missing: string[] }>(`/api/studies/${id}/verify`),
  studyReproduce: (id: string, procs: number) => post<StudySummary>(`/api/studies/${id}/reproduce`, { procs }),
  studyReproduction: (id: string) => j<{ of: string; identical_share: number; runs_compared: number; differing: unknown[]; condition: string }>(`/api/studies/${id}/reproduction`),
};

/* eslint-disable @typescript-eslint/no-explicit-any */
export type StudyProtocol = Record<string, any>;
export interface StudyValidation {
  valid: boolean; issues: string[]; digest: string; runs?: number; step_runs?: number; high_cost?: boolean;
  fairness?: { profiles: Record<string, any>; contrasts: { contrast: string; a: string; b: string; differences: Record<string, any>; declared: string[]; undeclared: string[]; equal_on: string[] }[]; controls: Record<string, string>;
    operations?: { operations: Record<string, { description: string; status: string; via: string }>; access: Record<string, Record<string, boolean>> } };
  fairness_issues?: string[];
}
export interface StudyStatus {
  state: string; n_total: number; n_ok: number; n_failed: number; elapsed_s?: number; stop_reason?: string | null; remaining?: number;
  running?: boolean; runs_on_disk?: number; updated: string;
}
export interface StudySummary {
  id: string; title: string; mode: string; created: string; status: StudyStatus; running: boolean; protocol_digest: string;
  n_runs: number; reproduces: string | null; not_evidence: boolean; environment: string;
}
export interface StudyDetail extends StudySummary {
  protocol: StudyProtocol; registered_digest: string; manifest: Record<string, any>; amendments: Record<string, any>[];
  fairness: NonNullable<StudyValidation['fairness']>; has_analysis: boolean; has_report: boolean; has_package: boolean;
}
export interface StudyRunRow {
  arm: string; index: number; gen: number; seed: number; status: string; error?: string | null; wall_s?: number | null;
  peak_rss_mb?: number | null; metrics: Record<string, number | null>; controller_changes: number; protocol_changes: number;
}
export type StudyRunRecord = Record<string, any>;
export type StudyAnalysis = Record<string, any>;
/* eslint-enable @typescript-eslint/no-explicit-any */

export interface PrimitiveEntry {
  primitive: string; name: string; definition: string; implementation: string[]; flags: string[]; tests: string[];
  status: string; question: string | null; rule: string | null; reduced_to: string | null;
  diverges_in: string[] | null; why_unresolved: string | null; evidence: string[];
}

export type WsMessage =
  | { kind: 'frame'; frame: Frame }
  | { kind: 'json'; msg: Record<string, unknown> & { type: string } };

export type Stream = WebSocket | NativeSocket;

export function connect(sid: string, onMessage: (m: WsMessage) => void, onClose: (code: number) => void): Stream {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws: Stream = NATIVE ? new NativeSocket(sid) : new WebSocket(`${proto}://${location.host}/ws/${sid}`);
  // both transports deliver the same events: text messages (JSON) and binary frames (ArrayBuffer)
  const sock = ws as unknown as { binaryType: string; onmessage: (ev: { data: unknown }) => void;
    onclose: (ev: { code: number }) => void };
  sock.binaryType = 'arraybuffer';
  sock.onmessage = (ev) => {
    if (typeof ev.data === 'string') onMessage({ kind: 'json', msg: JSON.parse(ev.data) });
    else onMessage({ kind: 'frame', frame: decodeFrame(ev.data as ArrayBuffer) });
  };
  // keep-alive: the server closes sockets that stay silent beyond its idle limit
  const ping = setInterval(() => { if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'ping', t: Date.now() })); }, 30_000);
  sock.onclose = (ev) => { clearInterval(ping); onClose(ev.code); };
  return ws;
}

// ------------------------------------------------------------------ response types

export interface NodeDetail {
  id: number; address: string; cluster_path: string[]; difference: number; form: number; theta: number;
  theta_mod: number; theta_eff: number; retention: number; memory: number; mem_decay: number; mem_coupling: number;
  cap: number; frozen: boolean; refractory: number; overload: number; wave_origin: number; wave_depth: number;
  ignite_count: number; last_ignite: number; geo: [number, number] | null; in_loop: boolean;
  regional_signature: string | null;
  reachable_transitions: { edge: number; to: number; weight: number; gate: number; load: number; transform: number;
    reachable: boolean }[];
  incoming: { edge: number; from: number; weight: number; gate: number }[];
  out_degree: number; in_degree: number;
  recent_transitions: { t: number; kind: string; [k: string]: unknown }[];
}

export interface Metrics {
  t: number[]; series: Record<string, number[]>; t_graph: number[]; graph_series: Record<string, number[]>;
  events: { t: number; kind: string; [k: string]: unknown }[];
}

export interface RecurrentShape {
  signature: string; first_seen: number; last_seen: number; passes: number; clusters_now: number;
  max_clusters: number; clusters: string[]; axes: Record<string, number>;
}

export interface Shapes {
  t: number; step: Record<string, number>; graph: Record<string, number>;
  events: { t: number; kind: string }[]; recurrent_shapes: RecurrentShape[];
  axes: { key: string; descriptor: string }[];
  embedding_loadings: Record<string, [number, number]>;
  interpretation: { disclaimer: string; interpretations: { signature: string; labels: { label: string; rule: string;
    gloss: string }[] }[]; rules: { label: string; rule: string; gloss: string }[] };
}

export interface ClaimJson {
  id: string; text: string; uses: string[]; bindings: { op: string; target: string; factor?: number }[];
  default_entitled: boolean; commitment: number;
}

export interface Provenance { source: string; effect: string; targets?: number; why?: string }

export interface ConfigView {
  practice: { concepts: string[]; claims: ClaimJson[]; dependencies: { premises: string[]; conclusion: string;
    kind: string }[]; incompatibilities: [string, string][]; withdrawn: string[]; removed_concepts: string[] };
  boundaries: Record<string, number>; removed_boundaries: string[]; boundary_override: Record<string, number>;
  direct: { kind: string; text?: string }[]; actions: { kind: string; text?: string }[]; log: string[];
  score: { commitment: Record<string, number>; entitled: Record<string, boolean>; status: Record<string, string> };
  provenance: Provenance[];
}

export interface PracticeView { applied: ConfigView; draft: ConfigView; grammar: string[]; sets: string[] }

export interface CommitmentChange {
  claim: string; text: string;
  before: { commitment: number; entitled: boolean; status: string };
  after: { commitment: number; entitled: boolean; status: string };
}

export interface CommandReport {
  command: { op: string; args: Record<string, unknown>; text: string };
  dependencies?: { token: string; direct: string[]; consequences: string[];
    dependencies: { premises: string[]; conclusion: string; kind: string }[]; incompatibilities: string[][] };
  commitment_changes?: CommitmentChange[];
  operational_changes?: { before: Provenance[]; after: Provenance[] };
  job?: string; grammar?: string[]; applied?: unknown; discarded?: boolean; severed_connections?: number;
  score?: ConfigView['score'];
}

export interface Job { id: string; kind: string; status: 'running' | 'done' | 'error'; error?: string; horizon: number;
  summary?: CompareResult['summary'] }

export interface MetricRow { baseline: number; intervention: number; delta: number; noise_floor?: number;
  exceeds_noise?: boolean }

export interface CompareResult {
  id: string; start_t: number; horizon: number; elapsed_s: number;
  summary: {
    reachable: { baseline: number; intervention: number; newly_reached: number; no_longer_reached: number;
      noise_floor_flips: number | null; exceeds_noise: boolean | null };
    ignition_pattern: { ignites_more: number; ignites_less: number; total_baseline: number; total_intervention: number };
    cuts: { only_baseline: number; only_intervention: number; shared: number };
    loops: { gained: number; lost: number; baseline_fraction: number; intervention_fraction: number };
    reconfiguration: { baseline: number; intervention: number; only_intervention: number };
    new_connections: { baseline: number; intervention: number };
    gates_changed: number; first_divergence_step: number | null;
  };
  metrics: Record<string, MetricRow>;
  series: { t: number[]; baseline: number[]; intervention: number[] };
  node_classes: number[]; node_class_names: Record<string, string>; cluster_changes: number[][];
  edges: [number, number, number][]; edge_class_names: Record<string, string>;
  commitment_changes: CommitmentChange[];
  operational_changes: { baseline: Provenance[]; intervention: Provenance[] };
  intervention_log: string[];
}
