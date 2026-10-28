// XENO ECOSYSTEM — how the bodies are posed for a run's SSS and M2 connection. These are VISUAL REPRESENTATION rules (a design choice of the view, written down and tested), not model
// results: a pose is never evidence about a run. The numbers they read (the SSS triple, the region, the M2 term A1 senses) come from the record or from the engine's classification.
import type { MeosRecord } from './meosApi';
import type { ProbeState } from './probes';

export type SssRegion = 'ACTIVE' | 'COLLAPSED' | 'METASTABLE' | 'RECOVERY-CAPABLE' | 'OBSERVATION-SENSITIVE';
export interface SssMechanics {
  /** the observer's boom: extension bias, -1 (short) .. +1 (long); scale is the reach of sensing, so the boom that carries the probes reaches further */ boomPreload: number;
  /** the probe ring's posture: tilt in radians; size is the footprint of an operation, so the ring takes a larger or smaller stance */ ringTilt: number;
  /** the coupling's tension, 0 (slack) .. 1 (taut); speed is the process clock, so the line between the nodes is drawn taut when the process runs fast */ couplingTension: number;
  /** the archive latch opening (radians): 0 closed; a region that is not stably active leaves the latch ajar */ archiveAjar: number;
  /** the reservoir's level shift from regulation, -0.1 .. +0.1 (speed regulates how fast the exchange draws the reservoir) */ regulation: number;
}
const dev = (x: number) => Math.max(-1, Math.min(1, Math.log2(Math.max(0.25, x)) / 1.5));
// observation sensitivity is a property of the observer (every ACTIVE point of the experiment-D grid has it), not of history access, so it leaves the latch shut
const AJAR: Record<SssRegion, number> = { ACTIVE: 0, 'OBSERVATION-SENSITIVE': 0, METASTABLE: 0.6, 'RECOVERY-CAPABLE': 0.9, COLLAPSED: 0 };
export function sssMechanics(sss: { scale: number; size: number; speed: number }, region: SssRegion = 'ACTIVE'): SssMechanics {
  return { boomPreload: dev(sss.scale), ringTilt: 0.2 * dev(sss.size), couplingTension: 0.5 + 0.5 * dev(sss.speed), archiveAjar: AJAR[region], regulation: 0.1 * dev(sss.speed) };
}

// ---------------------------------------------------------------------------------------------------- the M2 tap
export interface M2Tap { configured: boolean; sense: string; sensed: number; state: ProbeState | null }
/** The state of the M2 tap on node B (its second probe): M2 is A2's alteration of the environment, added to A1's resource-sensor signal. Absent when M2 is not connected. */
const at = (a: number[] | undefined, t: number): number => (a && a.length ? a[Math.min(t, a.length - 1)] : 0);
export function m2TapState(rec: MeosRecord, tick: number): M2Tap {
  const sense = rec.config.m2?.sense ?? 'none', t = Math.min(Math.max(0, tick), rec.frames.length - 1);
  if (sense === 'none') return { configured: false, sense, sensed: 0, state: null };
  const sensed = at(rec.traces?.m2_sensed, t), collapsed = rec.frames[t].status === 'COLLAPSED';
  const state: ProbeState = collapsed ? 'retracted' : sensed > 1e-6 ? (sense === 'noisy' ? 'overloaded' : 'sampling') : 'extended';
  return { configured: true, sense, sensed, state };
}
