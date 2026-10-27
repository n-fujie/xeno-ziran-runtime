// XENO ECOSYSTEM — the client side of the MEOS API (backend/xzr/meos). Types of the record, requests, and the pure decoding of the
// recorded field stream. Nothing here simulates: every number the view shows is read from a record the engine produced.

export type Label = 'ACTIVE' | 'DEGRADED' | 'COLLAPSED';
export type Dependency = { entity: string | null; precondition: string; detail: string; value: unknown; need: unknown } | null;

export interface EntityFrame {
  present: boolean; x: number; y: number; energy: number; h: number; active: number; cool: number; fired: boolean; s: number; d: number;
  theta: number; baseline: number; reentry: number; r_local: number; m1_local: number; fires: number; failed: string[];
}
export interface AdStatic {
  operational_boundary: { sensor_radius: number; footprint: number; arena_radius: number | null };
  temporal_window: { window: number; persist: number; refractory: number };
  speed: number;
  connectivity: { sensor_resource: boolean; sensor_alteration: boolean; interaction: boolean; feedback: boolean };
  history_reentry_enabled: boolean; mark_persistence: number; sss: { scale: number; size: number; speed: number }; present: boolean; threshold: number;
}
export interface Frame {
  t: number; status: Label; cycles: number; power: number; R: number; M1: number; M2: number; A1: EntityFrame; A2: EntityFrame;
  ad?: { A1: AdStatic; A2: AdStatic };
}
export interface Ev {
  id: number; tick: number; kind: string; actor: string | null; [k: string]: unknown;
}
export interface Check { precondition: string; ok: boolean; value: unknown; need: unknown }
export interface MeosRecord {
  schema: string; engine: string; config: MeosConfig; final_config: MeosConfig; seed: number; interventions: Intervention[];
  intervention_log: Array<{ tick: number; op: string; event: number; [k: string]: unknown }>; frames: Frame[]; events: Ev[];
  cycles: Array<{ tick: number; id: number; history_reentry: boolean }>;
  status_log: Array<{ tick: number; label: Label; reason: string; dependency: Dependency }>;
  final_status: { label: Label; reason: string; dependency: Dependency; cycles_in_window: number; history_reentry_cycles: number; age: number | null };
  termination: { reason: string; tick: number; collapsed: boolean; failed_dependency: Dependency };
  fields: { grid: number; channels: string[]; encoding: string; r_top: number; b64: string };
  initial_config_digest: string; result_digest: string;
}
export interface MeosConfig {
  seed: number; horizon: number; grid: number; noise: number;
  environment: Record<string, number | boolean | null>; power: { reserve: number; capacity: number; charge: number; infinite: boolean };
  channels: Record<string, boolean>; history: Record<string, number | boolean | string>; sss: { scale: number; size: number; speed: number };
  entities: Record<'A1' | 'A2', Record<string, number | boolean | number[]>>;
}
export interface Intervention { tick: number; op: string; target?: string; path?: string; value?: number; arena_radius?: number; mode?: string;
  scale?: number; size?: number; speed?: number; inject?: { x: number; y: number; amount: number } }
export interface Spec {
  engine: string; defaults: MeosConfig; components: string[]; entities: string[]; operations: string[]; settable: Record<string, [number, number]>;
  partitions: Record<string, { label: string; components: string[] }>; body_components: string[]; legs: Record<string, string[]>;
  status_criteria: Record<string, string>; limits: { max_horizon: number; max_interventions: number; max_seeds: number };
}
export interface Summary { status: Label; persists: boolean; cycles: number; first_collapse_tick: number | null; failed_dependency: Dependency;
  result_digest: string; status_log: Array<[number, Label]>; final_power: number; history_reentry_cycles: number; reason: string }
export interface RunOut { record: MeosRecord; summary: Summary; observed?: Observed }
export interface Observed { observation: Record<string, unknown>; observed_cycles: number; true_cycles: number; observed_status: Label; true_status: Label;
  agrees: boolean; observed_trajectory: Label[] }
export interface AblationRow { removed: string[]; persists_in_all_seeds: boolean;
  outcomes: Array<{ seed: number; status: Label; persists: boolean; cycles: number; first_collapse_tick: number | null; failed_dependency: Dependency }> }
export interface MfsOut { baseline_persists: boolean; retained: string[]; removed: string[]; retained_is_one_minimal?: boolean;
  single_removal_persists?: Record<string, boolean>; leave_one_out_persists?: Record<string, boolean>; note?: string;
  exhaustive?: { subsets_evaluated: number; minimal_retained_sets: string[][] }; operation: string }
export interface BoundaryOut { partitions: Array<{ id: string; label: string; components: string[]; legs_inside: Record<string, boolean>; closure: number;
  persists_when_only_the_body_is_retained: boolean; status_when_only_the_body_is_retained: Label; failed_dependency: Dependency; cycles: number }> }
export type HistoryOut = Record<string, Summary & { 'first_divergence_from_H+': number | null; mean_threshold_reduction: number }>;

export const API = '/api/meos';

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${path}: ${r.status} ${(await r.text()).slice(0, 200)}`);
  return r.json() as Promise<T>;
}

export const getSpec = async (): Promise<Spec> => {
  const r = await fetch(`${API}/spec`);
  if (!r.ok) throw new Error(`spec: ${r.status}`);
  return r.json();
};
export const runMeos = (config: Partial<MeosConfig> | undefined, interventions: Intervention[], observation?: Record<string, unknown>) =>
  post<RunOut>('/run', { config, interventions, observation });
export const replayMeos = (config: unknown, interventions: Intervention[], result_digest: string) =>
  post<{ identical: boolean; expected: string; got: string }>('/replay', { config, interventions, result_digest });
export const ablation = (config: unknown, subsets?: string[][], seeds?: number[]) => post<{ rows: AblationRow[]; seeds: number[] }>('/ablation', { config, subsets, seeds });
export const mfs = (config: unknown, exhaustive = false, horizon?: number) => post<MfsOut>('/mfs', { config, exhaustive, horizon });
export const boundary = (config: unknown, partitions?: unknown) => post<BoundaryOut>('/boundary', { config, partitions });
export const historyCompare = (config: unknown) => post<HistoryOut>('/history', { config });
export const sssSweep = (config: unknown) => post<{ rows: Array<{ axis: string; value: number; status: Label; persists: boolean; cycles: number; first_collapse_tick: number | null }> }>('/sss', { config });
export const addressSweep = (config: unknown) => post<{ rows: Array<{ path: string; value: number; status: Label; persists: boolean; cycles: number; first_collapse_tick: number | null }> }>('/address', { config });

// ------------------------------------------------------------------------------------------------ fields
export interface Fields { n: number; frames: number; R: Float32Array; M1: Float32Array; M2: Float32Array; rTop: number }

/** Decode the recorded uint8 stream (frame-major, channel-major, x-major) into normalised 0..1 arrays (R relative to its recorded top). */
export function decodeFields(f: MeosRecord['fields'], nFrames: number): Fields {
  const bin = atob(f.b64);
  const n = f.grid, cells = n * n;
  const R = new Float32Array(nFrames * cells), M1 = new Float32Array(nFrames * cells), M2 = new Float32Array(nFrames * cells);
  for (let t = 0; t < nFrames; t++) {
    const base = t * 3 * cells;
    for (let i = 0; i < cells; i++) {
      R[t * cells + i] = bin.charCodeAt(base + i) / 255;
      M1[t * cells + i] = bin.charCodeAt(base + cells + i) / 255;
      M2[t * cells + i] = bin.charCodeAt(base + 2 * cells + i) / 255;
    }
  }
  return { n, frames: nFrames, R, M1, M2, rTop: f.r_top };
}

export const fieldAt = (f: Fields, ch: 'R' | 'M1' | 'M2', t: number): Float32Array => {
  const cells = f.n * f.n;
  return f[ch].subarray(t * cells, (t + 1) * cells);
};

/** The Address Domain parts that only an intervention changes, as of tick t (the latest frame at or before t that carries them). */
export function adAt(frames: Frame[], t: number): { A1: AdStatic; A2: AdStatic } | null {
  for (let i = Math.min(t, frames.length - 1); i >= 0; i--) if (frames[i].ad) return frames[i].ad!;
  return null;
}

export const STATUS_VALUE: Record<Label, number> = { COLLAPSED: 0, DEGRADED: 1, ACTIVE: 2 };
