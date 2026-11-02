// XENOSCIENCE ECOSYSTEM — the couplings of MEOS-0 as objects of the 3D scene, and the comparison of two branches of one experiment. Pure functions over records: nothing here runs the engine
// or edits a record. A coupling is not a drawing choice: each one is a component of the engine (``spec.components``) that an ISOLATE / RECONNECT intervention switches, and its state at a tick is read
// from the record's Address Domain (``ad.connectivity``), which the engine writes whenever an intervention changes it.

import { adAt, type Frame, type Intervention, type Label, type MeosRecord } from './meosApi';

export type CouplingId = 'sensor_resource' | 'interaction_channel' | 'sensor_alteration' | 'feedback';
export interface CouplingDef {
  id: CouplingId; label: string; from: string; to: string;
  /** the key of ``ad.connectivity`` that records it */
  flag: 'sensor_resource' | 'interaction' | 'sensor_alteration' | 'feedback';
  /** what the engine does with the coupling (read from backend/xzr/meos/engine.py, not from the picture) */
  role: string;
  /** the dependency the engine names when the coupling is cut */
  whenCut: string;
}

export const COUPLINGS: CouplingDef[] = [
  { id: 'sensor_resource', label: 'resource sensing', from: 'resource field R', to: 'A1', flag: 'sensor_resource',
    role: 'A1 senses the resource field R through this channel; without it the sensor channel of A1 is not connected and A1 cannot fire.', whenCut: "A1's resource sensor is disconnected" },
  { id: 'interaction_channel', label: 'interaction channel (alteration M1)', from: 'A1 alteration M1', to: 'A2', flag: 'interaction',
    role: "the alteration of the environment is the only way A2 detects A1; with the channel cut A2's sensor channel is not connected.", whenCut: "the interaction channel between A1's alteration and A2 is interrupted" },
  { id: 'sensor_alteration', label: 'alteration sensing', from: 'alteration M1', to: 'A2', flag: 'sensor_alteration',
    role: 'A2 senses the alteration M1 through this channel (together with the interaction channel).', whenCut: "A2's alteration sensor is disconnected" },
  { id: 'feedback', label: 'feedback (reconfigured resource R)', from: 'A2 reconfiguration', to: 'A1 via R', flag: 'feedback',
    role: "the reconfigured resource is the only way A1 detects A2; with feedback cut A2 renews nothing for A1.", whenCut: "A2's reconfiguration of the resource is disabled (no feedback to A1)" },
];
export const COUPLING_IDS = COUPLINGS.map((c) => c.id);
export const couplingDef = (id: CouplingId): CouplingDef => COUPLINGS.find((c) => c.id === id)!;

export type CouplingState = 'connected' | 'cut' | 'unrecorded';

/** The state of every coupling at tick t, read from the record. A coupling is ``unrecorded`` when the record carries no Address Domain frame at or before t. */
export function couplingStates(rec: MeosRecord, t: number): Record<CouplingId, CouplingState> {
  const ad = adAt(rec.frames, t);
  const out = {} as Record<CouplingId, CouplingState>;
  for (const c of COUPLINGS) out[c.id] = !ad ? 'unrecorded' : ad.A1.connectivity[c.flag] ? 'connected' : 'cut';
  return out;
}

/** The interventions that cut a coupling at tick ``at`` and restore it ``duration`` ticks later (never later than the last tick of the run). ``duration`` null cuts it for the rest of the run. */
export function cutRequest(id: CouplingId, at: number, duration: number | null, last: number): Intervention[] {
  const cut: Intervention = { tick: Math.max(0, Math.min(at, last)), op: 'ISOLATE', target: id };
  if (duration === null || cut.tick + duration > last) return [cut];
  return [cut, { tick: cut.tick + Math.max(1, duration), op: 'RECONNECT', target: id }];
}

// ------------------------------------------------------------------------------------------------ branch comparison

export interface BranchSide { label: Label; cycles: number; firstCollapse: number | null; terminatedAt: number | null; resultDigest: string }
export interface BranchComparison {
  base: BranchSide; branch: BranchSide;
  /** interventions present in the branch and not in the baseline */
  added: Intervention[];
  /** first tick at which the recorded state of the two runs differs (status, either entity, resource, power); null if they never differ */
  firstStateDivergence: number | null;
  /** first tick at which the operational status differs */
  firstStatusDivergence: number | null;
  /** the two runs were configured identically (``config``; the record's input digest also covers the interventions, so it differs between a baseline and a branch by construction) */
  sameConfiguration: boolean;
  /** the last tick both records cover */
  comparedTicks: number;
}

const side = (r: MeosRecord): BranchSide => ({
  label: r.final_status.label, cycles: r.cycles.length, firstCollapse: r.status_log.find((s) => s.label === 'COLLAPSED')?.tick ?? null,
  terminatedAt: r.termination.collapsed ? r.termination.tick : null, resultDigest: r.result_digest,
});
const key = (f: Frame): string => JSON.stringify([f.status, f.A1, f.A2, f.R, f.M1, f.M2, f.power]);
const ivKey = (i: Intervention): string => JSON.stringify(i);

/** Compare a baseline run with an intervened run of the same configuration: where the recorded states first differ, and what each branch ended as. The comparison is of two records the engine produced;
 *  a difference after the divergence tick is not attributed to the intervention by this function (that needs the engine's own causal operations), only located. */
export function compareBranches(base: MeosRecord, branch: MeosRecord): BranchComparison {
  const n = Math.min(base.frames.length, branch.frames.length);
  let state: number | null = null, status: number | null = null;
  for (let t = 0; t < n && (state === null || status === null); t++) {
    if (state === null && key(base.frames[t]) !== key(branch.frames[t])) state = t;
    if (status === null && base.frames[t].status !== branch.frames[t].status) status = t;
  }
  const baseSet = new Set(base.interventions.map(ivKey));
  return { base: side(base), branch: side(branch), added: branch.interventions.filter((i) => !baseSet.has(ivKey(i))), firstStateDivergence: state, firstStatusDivergence: status,
    sameConfiguration: JSON.stringify(base.config) === JSON.stringify(branch.config), comparedTicks: n };
}

/** Where the entities of the baseline run were at tick t (for the baseline marker of the 3D scene). Null outside the baseline's record. */
export function baselinePositions(base: MeosRecord, t: number): Record<'A1' | 'A2', { x: number; y: number; present: boolean }> | null {
  const f = base.frames[t];
  return f ? { A1: { x: f.A1.x, y: f.A1.y, present: f.A1.present }, A2: { x: f.A2.x, y: f.A2.y, present: f.A2.present } } : null;
}

// ------------------------------------------------------------------------------------------------ where a displayed record comes from

export type Origin = 'NEW_ENGINE_RUN' | 'REPLAY_VERIFIED' | 'REPLAY_DIFFERS' | 'SAVED_EXPERIMENT';

/** What produced the record on screen, kept apart from playing it. Moving the playhead plays a record back and runs nothing; a new run is the engine executing the configuration and interventions; a
 *  replay is the engine re-executing a record's inputs and comparing the result digest (``replay`` is the view's own status line for it). */
export function originOf(replay: string | null): Origin {
  if (!replay) return 'NEW_ENGINE_RUN';
  if (replay.startsWith('replay identical')) return 'REPLAY_VERIFIED';
  if (replay.startsWith('REPLAY DIFFERS') || replay.startsWith('REPLAY OF THE CONTROLLED RUN DIFFERS')) return 'REPLAY_DIFFERS';
  return 'SAVED_EXPERIMENT';
}
export const ORIGIN_TEXT: Record<Origin, string> = {
  NEW_ENGINE_RUN: 'the engine executed this configuration and these interventions for this view',
  REPLAY_VERIFIED: 'the engine re-executed the record\'s inputs and reproduced its result digest',
  REPLAY_DIFFERS: 'the engine re-executed the record\'s inputs and did NOT reproduce its result digest',
  SAVED_EXPERIMENT: 'a stored experiment configuration, executed by the engine on request',
};
