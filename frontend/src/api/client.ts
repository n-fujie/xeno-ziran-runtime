// REST + WebSocket access to the backend. All paths are same-origin (Vite proxies in development).

import { decodeFrame, decodeTile, type Frame, type Tile } from '../proto/decode';

export interface SessionInfo {
  id: string;
  scenario: { name: string; description: string };
  n: number; e_cap: number; t: number; running: boolean; speed: number; steps_per_second: number;
  connections: number; checkpoints: number[]; layout_version: number; draft_differs: boolean;
  params: Record<string, number>; quant_max: number; mem_qmax: number; n_forms: number;
  scales: string[]; layouts: string[]; clusters_per_level: number[]; geo_count: number; sets: string[];
  boundaries: Record<string, number>;
  runtime_flags?: Record<string, string | boolean>; runtime_is_full?: boolean;
}

export interface Status {
  t: number; running: boolean; speed: number; pending_steps: number; steps_per_second: number;
  connections: number; checkpoints: number[]; layout_version: number; draft_differs: boolean;
}

export interface ClusterSummary {
  level: number; addresses: string[]; parents: number[]; count: number[];
  centroids: Record<string, ([number | null, number | null])[]>;
  spread: Record<string, (number | null)[]>;
  flows: [number, number, number, number, number][];
  layout_version: number;
}

export class ApiError extends Error {
  constructor(msg: string, public status: number, public body: unknown) {
    super(msg);
  }
}

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...init });
  const body = r.headers.get('content-type')?.includes('json') ? await r.json() : await r.text();
  if (!r.ok) {
    const msg = typeof body === 'object' && body ? (body as { error?: string; detail?: unknown }).error ??
      JSON.stringify((body as { detail?: unknown }).detail) : String(body);
    throw new ApiError(msg, r.status, body);
  }
  return body as T;
}

const post = <T>(path: string, body: unknown) => j<T>(path, { method: 'POST', body: JSON.stringify(body) });

export const api = {
  scenarios: () => j<{ id: string; name: string; description: string; configurations: number }[]>('/api/scenarios'),
  createSession: (sample: string, flags?: string) => post<SessionInfo>('/api/sessions', { sample, flags }),
  loadSession: (saved: { scenario: unknown; applied?: unknown }) =>
    post<SessionInfo>('/api/sessions', { scenario: saved.scenario, applied: saved.applied }),
  sessions: () => j<{ id: string; scenario: string; t: number }[]>('/api/sessions'),
  info: (sid: string) => j<SessionInfo>(`/api/sessions/${sid}`),
  control: (sid: string, action: string, extra: { steps?: number; speed?: number } = {}) =>
    post<Status>(`/api/sessions/${sid}/control`, { action, ...extra }),
  rewind: (sid: string, t: number) => post<Status>(`/api/sessions/${sid}/rewind`, { t }),
  clusters: (sid: string, level: number) => j<ClusterSummary>(`/api/sessions/${sid}/clusters?level=${level}`),
  tile: async (sid: string, layout: string, level: number, b: [number, number, number, number], maxEdges = 20000): Promise<Tile> => {
    const q = `layout=${layout}&level=${level}&x0=${b[0]}&y0=${b[1]}&x1=${b[2]}&y1=${b[3]}&max_edges=${maxEdges}`;
    const r = await fetch(`/api/sessions/${sid}/tile?${q}`);
    if (!r.ok) throw new ApiError(await r.text(), r.status, null);
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
  experiments: () => j<{ name: string; bytes: number; modified: number }[]>('/api/experiments'),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  experiment: <T = any>(name: string) => j<T>(`/api/experiments/${name}`),
  primitives: () => j<PrimitiveEntry[]>('/api/experiments/primitives'),
};

export interface PrimitiveEntry {
  primitive: string; name: string; definition: string; implementation: string[]; flags: string[]; tests: string[];
  status: string; question: string | null; rule: string | null; reduced_to: string | null;
  diverges_in: string[] | null; why_unresolved: string | null; evidence: string[];
}

export type WsMessage =
  | { kind: 'frame'; frame: Frame }
  | { kind: 'json'; msg: Record<string, unknown> & { type: string } };

export function connect(sid: string, onMessage: (m: WsMessage) => void, onClose: () => void): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws/${sid}`);
  ws.binaryType = 'arraybuffer';
  ws.onmessage = (ev) => {
    if (typeof ev.data === 'string') onMessage({ kind: 'json', msg: JSON.parse(ev.data) });
    else onMessage({ kind: 'frame', frame: decodeFrame(ev.data as ArrayBuffer) });
  };
  ws.onclose = onClose;
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
