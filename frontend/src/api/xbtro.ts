// Client of the XenoBody / Total Observation research environment (backend/xzr/service/xbtro_ops.py). The same routes are served over
// HTTP, by the iOS bridge and by the in-tab runtime, so this client does not depend on the transport.
import { j, post, rawText } from './client';

const B = '/api/xbtro';

export interface Experiment { id: string; title: string; question: string; default_n_seeds: number; params: Record<string, unknown> }
export interface Preset { id: string; name: string; family: string; links: number; joints: number; lines: number; dt: number; tolerance_band_m: number }
export interface InterventionSpec { label: string; unit: string; default: number; range: [number, number]; edits: string }
export interface ObsKind {
  label: string; family: string; defaults: Record<string, number | string | number[]>; spatial_choices: string[]; noise_unit: string; signals: string[];
  effects: Record<string, number>;
}
export interface Principle {
  id: string; alias: string; definition: string; operationalization: string; ignition: string; acts_on: string[]; fidelity: string; gap: string;
  source_rule: string; status: string;
}
export interface Catalog {
  model_version: string; record_schema: string; presets: Preset[]; interventions: Record<string, InterventionSpec>; experiments: Experiment[];
  xeno14: Principle[]; xeno14_source: string;
  observation: { kinds: Record<string, ObsKind>; presets: Record<string, string[]>; regions: string[] };
  differences: { id: string; label: string; family: string; timescale_s: number }[];
  velocity_measures: { id: string; label: string; unit: string; definition: string }[];
  organizations: Record<string, string>; tolerance: Record<string, { band: number; rule: string }>;
  seeds: { exploration: [number, number]; final_base: number };
  ziran: ZiranStatus; limits: Record<string, number | string[]>; labels: Record<string, string>; scope: string;
}
export interface ZiranStatus {
  sources: Record<string, string>; statement: string;
  spec: Record<string, { name: string; definition: string; not_this: string }>;
  status: Record<string, { repository_status: string; xbtro_instance: string; not_covered: string }>;
}

export interface Line { id: string; label: string; kind: string; enabled: boolean; timescale_s: number; ignition: { signal: string; threshold: number; hold_s: number }; observable_by: string[] }
export interface ObsModel {
  id: string; kind: string; sample_hz: number; noise: number; delay_s: number; dropout: number; spatial?: string;
  blind_windows: [number, number][]; blind_regions: string[]; joints?: string | number[]; segments?: number[];
  [k: string]: unknown;
}
export interface ObsConfig { name: string; models: ObsModel[]; window: [number, number] | null }
export interface BodyInfo {
  id: string; preset: string; family: string; name: string; seeds: number[]; dt: number; horizon_s: number;
  links: { id: string; label: string; region: string; length: number; mass: number; com_frac: number }[];
  joints: { id: string; label: string; tau_max: number; q_range: number }[];
  foot: { toe: number; heel: number }; base_of_support_m: [number, number]; lines: Line[]; task: { x_target: number; x_turn: number; t_cue: number; t_turn: number };
  xeno14: string[]; observation: ObsConfig;
  coverage: { models: Record<string, string[]>; regions: Record<string, string[]>; unobserved_regions: string[] };
  numeric_stability: { margin: number; stable: boolean; integrator: string; scope: string };
  tolerance_band_m: number; labels: Record<string, string>;
}
export interface Frame {
  t: number;
  reference: {
    theta: number[][]; omega: number[][]; q: number[][]; tau: number[][]; drive: number[][]; cocontraction: number[][]; com: number[]; vcom: number[]; cop: number[];
    normal_force: number[]; energy: number[]; fatigue: number[]; capacity: number[]; xref: number[]; adaptation_gain: number[]; push_force: number[]; slip: number[];
    alive: number[]; lines_active: number[][]; line_command: number[][];
  };
  estimates: { controller: { com: number[]; com_velocity: number[]; reference_it_works_towards: number[] } };
}
export interface ObsDelta {
  kind: string; channels: string[]; t: number[]; available_at: number[]; x: (number | null)[][][]; sample_hz: number; spatial: string;
  retired_from_t: number | null; label: 'observation';
}
export interface StepResult {
  t0: number; t1: number; steps: number; frames: Frame[]; observation: Record<string, ObsDelta>; finished: boolean;
  status: { t: number; alive: boolean[]; fell: boolean[]; diverged: boolean[]; fall_time: (number | null)[]; energy: number[]; fatigue: number[] };
}
export interface Inspect {
  part: string; region: string; kind: string; now: Record<string, number>; t: number[]; series: Record<string, (number | null)[]>;
  lines: { id: string; label: string; enabled: boolean; active_fraction: number; mean_command_here: number; timescale_s: number }[];
  observation: { covered: boolean; unobserved: boolean; models: { id: string; kind: string; sample_hz: number; noise: number; delay_s: number; dropout: number; spatial?: string; blind_windows: number[][] }[] };
  note: string;
}

export interface Job {
  id: string; kind: string; status: 'queued' | 'running' | 'done' | 'error' | 'cancelled'; progress: number; stage: string; label: string; experiment?: string;
  record_id: string | null; error?: string; summary?: { id: string; experiment: string; digest: string; negative_results: number; unobserved_differences: number; tables: string[] };
}
export interface RecordListing { id: string; experiment: string; digest: string; sequence: number; parent: string | null; negative_results: number; unobserved: number; seeds: number }
export interface HistoryView { records: RecordListing[]; unobserved_registry: { id: string; first_record: string; identified_later: boolean; identified_in?: string; history: { record: string; status: string; reason: string | null; configuration: string }[] }[]; limit: number; note: string }

export interface Table { name: string; title: string; columns: string[]; rows: (string | number | boolean | null)[][] }
export interface Series { t: number[]; mean: (number | null)[]; sd: (number | null)[] }
export interface XbRecord {
  schema: string; id: string; experiment: string; model_version: string; seeds: number[]; initial_configuration: Record<string, unknown>;
  observation_configurations: ObsConfig[]; interventions: unknown[]; time_step_s: number; numerical_method: string; parameters: Record<string, unknown>;
  results: Record<string, unknown> & { tables: Table[]; series?: Record<string, Series>; reading?: string };
  negative_results: { statement: string; evidence: unknown }[]; unobserved_differences: { id: string; status: string; reason: string | null; configuration: string }[];
  history: Record<string, unknown>; rerun: { experiment: string; parameters: Record<string, unknown> }; digest: string; provenance: Record<string, string>;
  labels: Record<string, string>;
}

const W = (wid: string) => `${B}/workspaces/${wid}`;

export const xb = {
  catalog: () => j<Catalog>(`${B}/catalog`),
  createWorkspace: () => post<{ id: string }>(`${B}/workspaces`, {}),
  diagnose: (preset: string, overrides: Record<string, unknown> = {}) => post<Record<string, unknown>>(`${B}/diagnose`, { preset, overrides }),
  history: (wid: string) => j<HistoryView>(`${W(wid)}/history`),
  createBody: (wid: string, body: Record<string, unknown>) => post<BodyInfo>(`${W(wid)}/bodies`, body),
  bodyInfo: (wid: string, bid: string) => j<{ id: string; info: BodyInfo; log: Record<string, unknown>[] }>(`${W(wid)}/bodies/${bid}`),
  step: (wid: string, bid: string, n: number) => post<StepResult>(`${W(wid)}/bodies/${bid}/step`, { n }),
  command: (wid: string, bid: string, cmd: Record<string, unknown>) => post<Record<string, unknown>>(`${W(wid)}/bodies/${bid}/command`, cmd),
  inspect: (wid: string, bid: string, part: string, seconds = 5) => j<Inspect>(`${W(wid)}/bodies/${bid}/inspect?part=${encodeURIComponent(part)}&seconds=${seconds}`),
  closeBody: (wid: string, bid: string) => j<{ closed: string }>(`${W(wid)}/bodies/${bid}`, { method: 'DELETE' }),
  saveBody: (wid: string, bid: string) => post<{ record: Job['summary'] }>(`${W(wid)}/bodies/${bid}/save`, {}),
  startExperiment: (wid: string, experiment: string, params: Record<string, unknown>) =>
    post<{ job: Job }>(`${W(wid)}/experiments`, { experiment, params }),
  job: (wid: string, jid: string) => j<Job>(`${W(wid)}/jobs/${jid}`),
  cancel: (wid: string, jid: string) => post<{ cancelled: boolean; status: string }>(`${W(wid)}/jobs/${jid}/cancel`, {}),
  record: (wid: string, rid: string) => j<XbRecord>(`${W(wid)}/records/${rid}`),
  exportRecord: (wid: string, rid: string, fmt: 'json' | 'csv') => rawText(`${W(wid)}/records/${rid}?format=${fmt}`),
  rerun: (wid: string, rid: string) => post<{ job: Job }>(`${W(wid)}/records/${rid}/rerun`, {}),
  reanalyse: (wid: string, rid: string, observation: unknown) => post<{ job: Job }>(`${W(wid)}/records/${rid}/reanalyse`, { observation }),
  reenter: (wid: string, rid: string, experiment: string, params: Record<string, unknown>) =>
    post<{ job: Job }>(`${W(wid)}/records/${rid}/reenter`, { experiment, params }),
  deleteRecord: (wid: string, rid: string) => j<{ deleted: string }>(`${W(wid)}/records/${rid}`, { method: 'DELETE' }),
  importRecord: (wid: string, rec: unknown) => post<Record<string, unknown>>(`${W(wid)}/records`, rec),
  exportHistory: (wid: string) => rawText(`${W(wid)}/history/export`),
  importHistory: (wid: string, data: unknown) => post<{ imported: number }>(`${W(wid)}/history/import`, data),
};
