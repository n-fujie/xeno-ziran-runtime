// XENO ECOSYSTEM — what the record says about the experimental bodies, as a pure function (no scene, no clock).
//
// The bodies are a presentation of a MEOS-0 run. The mapping below is a design choice of the view, written down so that it can be tested and read in the technical view:
//
//   record quantity                                  what the body does
//   -----------------------------------------------  ------------------------------------------------------------------------------------------------
//   observation samples at this tick                 node A's lens lights, its probe is 'sampling'; the observer's boom extends, its ring turns once per sampling interval
//   share of the arena the observation covers        how many of the observer's six probes are out (the rest are withdrawn)
//   observation cannot resolve the operation         the probes it points with are 'overloaded' (they tremble and their beads flicker)
//   A1 fired within the last 5 ticks                 node B's lamp flashes and its probe is 'sampling'; a light runs B -> C along the coupling
//   A2 renewed within the last 5 ticks               node C's probe is 'sampling' and sparks; a light runs C -> B
//   A2 absent, or its address lost                   node C's probe is 'inactive' and its lamp dark
//   interaction channel or feedback cut              the coupling's C-side half swings down and its connector parts from the B-side one; the junction ring opens
//   history re-entry disabled                        the archive unit's latch opens and its lamp goes dark
//   resource pulse injected                          the reservoir level on node C rises, then settles over the next 14 ticks
//   status COLLAPSED                                 every probe retracts and every lamp is dark: structural inactivity
//   recovery after a collapse                        sequential reactivation: node A at once, node B 8 ticks later, node C 16 ticks later
//   Address Domain fault on A1 / A2                  the probe of node B / node C is 'inactive' (loss) or 'overloaded' (fragment or partial)
//   arena boundary changed                           the observer's probe ring is repositioned toward the observed region (aim) and the boundary posts of the arena move
//
// It is a presentation, not an identification: A1, A2 and the observation are not these machines.
import { adAt, type MeosRecord, type Observation } from './meosApi';
import type { ProbeState } from './probes';
import { deviceState } from './researchDevice';

export interface BodyState {
  sampling: boolean; coverage: number; aim: [number, number]; interval: number;
  a1FireAge: number | null; renewAge: number | null; interaction: number; couplingCut: boolean; a2Present: boolean; status: string; recovered: boolean;
  collapsed: boolean; recoveryAge: number | null; pulseAge: number | null; pulseAmount: number; historyEnabled: boolean;
  address: { A1: string | null; A2: string | null }; arenaRadius: number | null; observability: string; tick: number;
}
export const FLASH_TICKS = 5, PULSE_TICKS = 14, RECOVERY_TICKS = 24;
/** Ticks after a recovery at which each node is reactivated (sequential reactivation). */
export const REACTIVATE_AT = { A: 0, B: 8, C: 16 } as const;

const lastAge = (rec: MeosRecord, t: number, pick: (e: MeosRecord['events'][number]) => boolean): number | null => {
  for (let i = rec.events.length - 1; i >= 0; i--) { const e = rec.events[i]; if (e.tick <= t && pick(e)) return t - e.tick; }
  return null;
};

export function bodyState(rec: MeosRecord, tick: number, obs: Partial<Observation> | null | undefined, observability = 'OBSERVABLE'): BodyState {
  const t = Math.min(Math.max(0, tick), rec.frames.length - 1), d = deviceState(rec, t, obs), f = rec.frames[t];
  const inter = rec.traces?.interaction_strength, ad = adAt(rec.frames, t);
  return {
    sampling: d.array.sampling, coverage: d.array.coverage, aim: d.array.aim, interval: Math.max(1, obs?.sampling_interval ?? 1),
    a1FireAge: lastAge(rec, t, (e) => e.kind === 'fire' && e.actor === 'A1'),
    renewAge: lastAge(rec, t, (e) => e.kind === 'act' && e.actor === 'A2' && Number(e.renewed) > 0),
    interaction: inter && inter.length ? inter[Math.min(t, inter.length - 1)] : 0,
    couplingCut: d.boundary.open.some((k) => k === 'interaction' || k === 'feedback'), a2Present: f.A2.present, status: f.status, recovered: d.recovery.phase === 'recovered',
    collapsed: f.status === 'COLLAPSED', recoveryAge: d.recovery.phase === 'recovered' ? d.recovery.age : null,
    pulseAge: d.pulse.active ? d.pulse.age : null, pulseAmount: d.pulse.amount,
    historyEnabled: ad ? ad.A1.history_reentry_enabled : true,
    address: { A1: f.address?.A1.mode ?? null, A2: f.address?.A2.mode ?? null }, arenaRadius: d.boundary.arenaRadius, observability, tick: t,
  };
}

/** A node is awake unless the run is collapsed or the node has not yet been reactivated after a recovery. */
export function nodeAwake(s: BodyState, node: 'A' | 'B' | 'C'): boolean {
  if (s.collapsed) return false;
  if (s.recoveryAge !== null && s.recoveryAge < RECOVERY_TICKS) return s.recoveryAge >= REACTIVATE_AT[node];
  return true;
}
const flash = (age: number | null) => (age === null || age > FLASH_TICKS ? 0 : 1 - age / (FLASH_TICKS + 1));
export const flashOf = flash;

/** The state of the probe of a node (A: observation, B: A1-linked, C: A2-linked). */
export function nodeProbeState(s: BodyState, node: 'A' | 'B' | 'C'): ProbeState {
  if (!nodeAwake(s, node)) return s.collapsed ? 'retracted' : 'inactive';
  if (node === 'A') return s.sampling ? (s.observability !== 'OBSERVABLE' ? 'overloaded' : 'sampling') : 'extended';
  if (node === 'B') {
    const m = s.address.A1;
    if (m === 'loss') return 'inactive';
    if (m === 'fragment' || m === 'partial') return 'overloaded';
    return flash(s.a1FireAge) > 0 ? 'sampling' : 'extended';
  }
  const m = s.address.A2;
  if (!s.a2Present || m === 'loss') return 'inactive';
  if (m === 'fragment' || m === 'partial') return 'overloaded';
  return flash(s.renewAge) > 0 ? 'sampling' : 'extended';
}

/** The state of the i-th of ``n`` probes of the observer's ring: probes beyond the observation's coverage are withdrawn. */
export function ringProbeState(s: BodyState, i: number, n: number): ProbeState {
  if (s.collapsed) return 'retracted';
  if (s.recoveryAge !== null && s.recoveryAge < REACTIVATE_AT.A) return 'inactive';
  const active = Math.max(1, Math.round(s.coverage * n));
  if (i >= active) return 'retracted';
  if (s.observability !== 'OBSERVABLE') return 'overloaded';
  return s.sampling ? 'sampling' : 'extended';
}

/** The level (0..1) of the reservoir on node C: it rises with a resource pulse and settles over ``PULSE_TICKS``. */
export function reservoirLevel(s: BodyState): number {
  const base = s.collapsed ? 0.12 : 0.38;
  if (s.pulseAge === null) return base;
  const k = 1 - s.pulseAge / PULSE_TICKS;
  return Math.min(1, base + Math.min(0.5, 0.18 * s.pulseAmount) * k);
}
