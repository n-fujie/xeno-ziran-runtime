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
  address?: Record<'A1' | 'A2', { mode: string | null; integrity: number; at?: [number, number] }>;  // present only while an Address Domain fault is active; ``at`` is the cell a stale or delayed address still names
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
  initial_config_digest: string; result_digest: string; trace_digest?: string; full_digest?: string;
  traces?: Record<string, number[]>;  // intermediate quantities, one value per tick (the status never reads them)
}
export interface MeosConfig {
  seed: number; horizon: number; grid: number; noise: number;
  m2?: { sense: 'none' | 'direct' | 'delayed' | 'noisy' | 'threshold'; weight?: number; delay?: number; noise?: number; threshold?: number };
  phil?: { mode: 'none' | 'expression' | 'scorekeeping' | 'revision'; margin?: number; window?: number; verify_margin?: number; noise?: number; delay?: number; cost?: number };
  environment: Record<string, number | boolean | null>; power: { reserve: number; capacity: number; charge: number; infinite: boolean };
  channels: Record<string, boolean>; history: Record<string, number | boolean | string>; sss: { scale: number; size: number; speed: number };
  entities: Record<'A1' | 'A2', Record<string, number | boolean | number[]>>;
}
export interface Intervention { tick: number; op: string; m2?: { sense: string; weight?: number; delay?: number; noise?: number; threshold?: number }; history?: 'on' | 'off'; why?: string; from?: string; to?: string; cost?: number; trigger?: string; target?: string; path?: string; value?: number; arena_radius?: number; mode?: string; x?: number; y?: number; fraction?: number; delay?: number; duration?: number;
  scale?: number; size?: number; speed?: number; inject?: { x: number; y: number; amount: number } }
export interface Spec {
  engine: string; defaults: MeosConfig; components: string[]; entities: string[]; operations: string[]; settable: Record<string, [number, number]>;
  partitions: Record<string, { label: string; components: string[] }>; body_components: string[]; legs: Record<string, string[]>;
  status_criteria: Record<string, string>; limits: { max_horizon: number; max_interventions: number; max_seeds: number };
}
export interface Summary { status: Label; persists: boolean; cycles: number; first_collapse_tick: number | null; failed_dependency: Dependency;
  result_digest: string; status_log: Array<[number, Label]>; final_power: number; history_reentry_cycles: number; reason: string }
export interface RunOut { record: MeosRecord; summary: Summary; observed?: Observed; paths?: PathActivity }
/** The observation configuration. ``threshold``, ``occluder`` and ``address_resolution`` are the fourth stage's optional limits: absent, the observation is the earlier one. */
export interface Observation { sampling_interval: number; spatial_stride: number; region: number[] | null; aggregation: number; window: number;
  threshold?: number | null; occluder?: number[] | null; address_resolution?: number | null; spatial_offset?: number[] }
export const FULL_OBSERVATION: Observation = { sampling_interval: 1, spatial_stride: 1, region: null, aggregation: 1, window: 48 };
/** The fourth stage's observability vocabulary (``observability.status``); the first-stage name stays in ``observability_status``. */
export const OBSERVABILITY_STATUSES = ['SUFFICIENT', 'INSUFFICIENT_TEMPORAL_RESOLUTION', 'INSUFFICIENT_SPATIAL_RESOLUTION', 'OUTSIDE_OBSERVATION_REGION', 'BOUNDARY_OCCLUDED', 'ADDRESS_UNRESOLVED', 'WINDOW_TOO_SHORT', 'SIGNAL_BELOW_THRESHOLD', 'COMBINED_LIMITS', 'OBSERVATION_OVERESTIMATES'] as const;
export type ObservabilityStatus = (typeof OBSERVABILITY_STATUSES)[number] | 'WINDOW_MISMATCH';
export interface TimelineRow { t: number; operational: Label; observed: Label; observability: ObservabilityStatus; limiting: string[] }
export interface Observed { observation: Record<string, unknown>; observed_cycles: number; true_cycles: number; observed_status: Label; true_status: Label;
  agrees: boolean; observed_trajectory: Label[];
  // operational state and observed state are kept apart; the status says why they differ
  operational_state: Label; observed_state: Label; observability_status: string; limiting_parameters: string[];
  observability: { status: ObservabilityStatus; limiting_parameters: string[]; legacy_status: string; observed_collapse_is_operational: boolean; observed_collapse_is_artifact: boolean };
  timeline: TimelineRow[] }
export type PathId = 'resource' | 'coupling' | 'history_access' | 'observation' | 'recovery';
export const PATH_IDS: PathId[] = ['resource', 'coupling', 'history_access', 'observation', 'recovery'];
export interface PathActivity { [id: string]: { label: string; components: string[]; means: string; signal_name: string; peak: number; mean: number; active_ticks: number; cut_ticks: number;
  series: number[]; state_intervals: Array<{ from: number; to: number; state: 'cut' | 'active' | 'quiet' }> } }
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
export const runMeos = (config: Record<string, unknown> | undefined, interventions: Intervention[], observation?: Record<string, unknown>, paths = true) =>
  post<RunOut>('/run', { config, interventions, observation, paths });
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

// ------------------------------------------------------------------------------------------------ second-stage experiments (tables are shown as the engine returned them)
export type Json = Record<string, unknown>;
export const causalPath = (config: unknown, interventions: Intervention[]) => post<Json>('/causal', { config, interventions });
export const factorial = (config: unknown, seeds?: number[]) => post<Json>('/factorial', { config, seeds });
export const necessity = (config: unknown, seeds?: number[]) => post<Json>('/necessity', { config, seeds });
export const minimalConfigurations = (config: unknown, body: Json = {}) => post<Json>('/minimal-configurations', { config, ...body });
export const boundaryExperiments = (config: unknown, seeds?: number[]) => post<Json>('/boundary-experiments', { config, seeds });
export const recoveryPhase = (config: unknown, body: Json = {}) => post<Json>('/recovery', { config, ...body });
export const sssPhase = (config: unknown, body: Json = {}) => post<Json>('/sss-phase', { config, ...body });
export const addressExperiments = (config: unknown, seeds?: number[]) => post<Json>('/address-experiments', { config, seeds });
export const m2Experiment = (config: unknown, seeds?: number[]) => post<Json>('/m2', { config, seeds });
export const philExperiment = (config: unknown, seeds?: number[]) => post<Json>('/phil', { config, seeds });
export const observeRun = (config: unknown, interventions: Intervention[], observation: Json) => post<Observed>('/observe', { config, interventions, observation });

// ------------------------------------------------------------------------------------------------ fourth stage: research readings
export type BoundaryKind = 'observation' | 'coupling' | 'resource_exchange' | 'history_access' | 'address_domain';
export const BOUNDARY_KINDS: BoundaryKind[] = ['observation', 'coupling', 'resource_exchange', 'history_access', 'address_domain'];
export interface BoundaryPerturbationOut { boundary: BoundaryKind; label: string; tick: number; duration: number; interventions: Intervention[]; affected_components: string[];
  bodies: Record<string, { label: string; components: string[]; affected_inside: string[]; affected_outside: string[]; legs_closed: string[]; legs_closed_count: number; legs_broken_by_perturbation: string[]; legs_total: number }>;
  rows: Array<{ seed: number; state_before: Label; state_end_of_perturbation: Label; state_final_perturbed_open: Label; state_final_restored: Label; state_final_restored_and_pulse: Label; state_final_unperturbed: Label;
    state_final_unperturbed_and_pulse: Label; collapse_tick: number | null; collapsed: boolean; recovers_without_pulse: boolean; recovers_with_pulse: boolean; operation_changed: boolean;
    paths: Record<string, { mean_unperturbed: number; mean_perturbed: number; changed: boolean; cut_directly: boolean }>;
    observability: { operational_state: Label; observed_state: Label; status: ObservabilityStatus; observation: Record<string, unknown> } }>;
  affected_paths: string[]; paths_cut_directly: string[]; note: string }
export interface AddressEffect { tick: number; mode: string; affected_address: string[]; old_state: Record<string, Json>; new_state: Record<string, Json>; affected_path: string[];
  operational_effect: { state_before: Label; worst_state_after: Label; collapse_tick: number | null }; observed_effect: { observed_state_final: Label; observability: ObservabilityStatus };
  recovery_status: string; recovery_with_pulse?: string; params: Record<string, number> }
export interface AddressInterventionOut { mode: string; target: string; effects: AddressEffect[]; operational_state: Label; unperturbed_state: Label; restored_and_pulse_state: Label; record: MeosRecord; observed: Observed;
  digests: Record<string, string> }
export interface SssClassOut { scale: number; size: number; speed: number; class: string; region: 'ACTIVE' | 'COLLAPSED' | 'METASTABLE' | 'RECOVERY-CAPABLE' | 'OBSERVATION-SENSITIVE'; recovery_capable: boolean | null; observation_sensitive: boolean; seeds: number[] }
export const boundaryPerturbation = (config: unknown, body: { kind: BoundaryKind; tick?: number; duration?: number; seeds?: number[]; params?: Json }) => post<BoundaryPerturbationOut>('/boundary-perturbation', { config, ...body });
export const addressIntervention = (config: unknown, body: { mode: string; target?: string; tick?: number; duration?: number; seed?: number; params?: Json; observation?: Json }) => post<AddressInterventionOut>('/address-intervention', { config, ...body });
export const sssClassify = (config: unknown, body: { scale: number; size: number; speed: number; seeds?: number[] }) => post<SssClassOut>('/sss-classify', { config, ...body });
export const runLog = (config: unknown, interventions: Intervention[], observation?: Json) => post<Json>('/run-log', { config, interventions, observation, format: 'json' });
export async function runLogCsv(config: unknown, interventions: Intervention[], observation?: Json): Promise<string> {
  const r = await fetch(`${API}/run-log`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ config, interventions, observation, format: 'csv' }) });
  if (!r.ok) throw new Error(`/run-log: ${r.status}`);
  return r.text();
}

// ------------------------------------------------------------------------------------------------ fifth stage: routes, the MFS library, a controlled run
import type { LibraryMfs, Outcome, Topology } from './routeGraph';
import type { LibraryOut } from './mfsPanels';
export interface ReconfigureOut { record: MeosRecord & { controller?: { kind: string; log: Array<Record<string, unknown>>; switches: number } }; summary: Summary; paths: PathActivity; controller: { kind: string; log: Array<Record<string, unknown>>; switches: number }; outcomes: Outcome[]; topology: Topology; replay_identical: boolean }
export const mfsLibrary = async () => { const r = await fetch(`${API}/mfs-library`); if (!r.ok) throw new Error(`mfs-library: ${r.status}`); return r.json() as Promise<LibraryOut>; };
/** Run the configuration of one saved MFS (its condition with only its retained components in place) on a seed. */
export const mfsRun = (mfsId: string, seed: number) => post<{ record: MeosRecord; summary: Summary; paths: PathActivity; topology: Topology; mfs: { id: string; condition_id: string; retained: string[]; removed: string[] } }>('/mfs-run', { mfs: mfsId, seed });
export const routeTopology = (config: unknown, interventions: Intervention[]) => post<{ topology: Topology; summary: Summary; library?: LibraryMfs[] }>('/route-topology', { config, interventions });
export const reconfigure = (body: { controller: string; scenario: string; seed?: number }) => post<ReconfigureOut>('/reconfigure', body);

// ------------------------------------------------------------------------------------------------ sixth stage: world-state repair
export interface RepairActionSpec { id: string; class: 'A' | 'B' | 'C'; family: string; label: string; status: 'implemented' | 'proxy' | 'not implemented'; magnitudes: number[]; magnitude_meaning: string; durations: number[]; latency: string; side_effect: string; reversibility: string; declared_cost: Record<string, string>; note: string }
export interface RepairEvent { tick: number; kind: string; label: string; detail: string; source: string; family?: string; klass?: 'A' | 'B' | 'C'; action?: string; magnitude?: number; duration?: number; path?: string | null; expected_recovery?: number | null; estimated_cost?: number | null; attempt?: number; actual?: { tick: number; recovered_so_far: boolean; status_now: string } | null }
export interface RepairHorizon { outcome: string; success: boolean; collapsed_after_action: boolean; secondary_collapse: boolean; stable_from: number | null; latency: number | null; resource_exhausted: boolean }
export interface RepairBlock {
  stress: string; label: string; family: string; onset: number; actions: Array<{ action: string; magnitude: number; duration: number; t: number }>; events: RepairEvent[];
  evaluation: { horizons: Record<'short' | 'medium' | 'long', RepairHorizon>; costs: { raw: Record<string, number>; normalised: Record<string, number> }; final_status: string }; controller: { attempts: number; log: Array<Record<string, unknown>> };
}
export interface RepairRunOut { record: MeosRecord; summary: Summary; paths: PathActivity; topology: Topology; repair: RepairBlock; replay_identical: boolean }
export interface StressRow {
  stress: string; label: string; family: string; classification_at_decision_tick_113: string; classification_at_any_tested_tick: string; flags: string[];
  internal_reconfiguration: { effective: boolean; windows: number[][] }; world_single: { effective: boolean; windows: number[][] }; combined: { effective: boolean; windows: number[][] };
  minimum_effective: Array<{ action: string; magnitude: number; ticks: number[] | null }>; timing_window_fragments: number[][]; first_window: number[] | null; earliest_effective_tick: number | null; latest_successful_repair_tick: number | null; earliest_irreversible_tick: number | null;
  irreversible_from_first_tested_tick: boolean; window_open_at_end_of_tested_range: boolean; tested_range_end: number | null; unrepaired_collapse_tick: number | null; window_closes_before_collapse: boolean; reference_repair: { parts: Array<[string, number, number]>; t: number; klass: string; normalised_cost_equal_weights: number; costs: Record<string, unknown>; evaluation: { k: number; n: number } | null } | null;
  failure_reasons_in_the_tested_grid: Record<string, number>; near_miss: boolean;
}
export interface RepairLibraryOut {
  actions: RepairActionSpec[]; stresses: Record<string, { family: string; label: string; onset: number }>; controllers: string[]; failure_classes: string[]; horizons: Record<'short' | 'medium' | 'long', number>; recovery_window: number; decision_tick: number; stress_tick: number;
  has_results: boolean; results: Record<string, unknown> | null; refine: Record<string, unknown> | null; controller_results: Record<string, unknown> | null; final: { stress_table: StressRow[]; resource_non_monotonicity: Record<string, { effective_band: [number | null, number | null]; phases: Array<{ phase: string; from: number; to: number }> }> } | null;
}
export const repairLibrary = async () => { const r = await fetch(`${API}/repair-library`); if (!r.ok) throw new Error(`repair-library: ${r.status}`); return r.json() as Promise<RepairLibraryOut>; };
export const repairRun = (body: { stress: string; seed?: number; controller?: string | null; actions?: Array<{ action: string; magnitude: number; duration: number; t: number }> }) => post<RepairRunOut>('/repair-run', body);

