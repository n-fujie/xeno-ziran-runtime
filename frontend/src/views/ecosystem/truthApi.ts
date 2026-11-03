// TRUTH-ERROR — the client side of /api/truth-error. Numbers in, numbers out: a run takes a configuration and returns the deterministic record of a synthetic institution; nothing here sends an image, a video or
// an identifier of a person.
import type { TEConfig, TERun } from './truthError';

async function call<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`/api/truth-error${path}`, body === undefined ? undefined : { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${path}: ${r.status} ${(await r.text()).slice(0, 200)}`);
  return r.json() as Promise<T>;
}
export type TEOverrides = Partial<Omit<TEConfig, 'pose_sensor' | 'signal_sensor'>> & { pose_sensor?: Partial<TEConfig['pose_sensor']>; signal_sensor?: Partial<TEConfig['signal_sensor']> };
export const teRun = (config: TEOverrides): Promise<TERun> => call<TERun>('/run', { config });
export interface TEPose { axes: string[]; reference: number[][]; measured: Array<Array<number | null>>; confidence: number[]; missing_reason: number[]; uncertainty_degrees: number; tolerance_degrees: number[]; within_tolerance: Array<boolean | null>; sensor: Record<string, unknown>; note: string }
export const tePose = (body: { seed?: number; periods?: number; sensor?: TEOverrides['pose_sensor'] }): Promise<TEPose> => call<TEPose>('/pose', body);
export interface TEExperimentArm { arm: string; changed_vs_control: Record<string, unknown>; mean: Record<string, { mean: number | null; sd: number | null; se: number | null; n: number }>; paired_vs_control?: Record<string, { mean: number | null; se: number | null; up: number; down: number; same: number; detected: boolean | null }>; result_digest_seed1: string; target_state_identical_to_control_in_every_seed: boolean }
export interface TEExperiment { id: string; title: string; question: string; control: string; arms: TEExperimentArm[]; seeds: number[]; periods: number; n_subjects: number; outcomes: string[]; primary_outcomes: string[]; negative_results: string[]; failure_conditions: Record<string, boolean>; invalid_if_any_failure_condition: boolean; limits: string; protocol: Record<string, unknown>; protocol_digest: string }
export const teExperiments = (): Promise<{ engine: string; experiments: Record<string, TEExperiment> }> => call('/experiments');
