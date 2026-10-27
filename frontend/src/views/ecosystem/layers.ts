// XENO ECOSYSTEM — the scientific overlays. Every function here is a pure derivation from a MEOS record (and, where a field is needed, its decoded
// field stream) at a tick: no value is invented for presentation, and a layer that needs an experiment that has not been run says so.
import type { AdStatic, Check, Dependency, Ev, Frame, Label, MeosRecord, MfsOut } from './meosApi';

export type LayerId = 'physical' | 'operational' | 'mfs' | 'meos' | 'address' | 'sss' | 'history' | 'firing' | 'xenobody';
export const LAYERS: Array<{ id: LayerId; label: string; what: string }> = [
  { id: 'physical', label: 'PHYSICAL', what: 'the simulated environment: resource field R, alteration fields M1 (A1) and M2 (A2), the finite power reserve' },
  { id: 'operational', label: 'OPERATIONAL', what: 'recorded operational relations of the last ticks: alters, detects, reconfigures, fires on' },
  { id: 'mfs', label: 'MFS', what: 'the minimal relational configuration found by the reduction search (components retained / removable)' },
  { id: 'meos', label: 'MEOS', what: 'the ecosystem-level recursive loop and its status from the cycle criteria' },
  { id: 'address', label: 'ADDRESS', what: 'Address Domains: position, operational boundary (sensing window), temporal window' },
  { id: 'sss', label: 'SSS', what: 'Scale - Size - Speed: sensing reach, footprint and movement per tick, in grid cells' },
  { id: 'history', label: 'HISTORY', what: 'history re-entry: firings whose threshold was lowered by the history trace' },
  { id: 'firing', label: 'FIRING', what: 'active, expired and potential firing relations with the first unmet precondition' },
  { id: 'xenobody', label: 'XENOBODY', what: 'alternative partitions of the same arrangement into operational bodies' },
];
export const ENTITY_NAMES = ['A1', 'A2'] as const;
export type EntityName = (typeof ENTITY_NAMES)[number];
export const WINDOW = 48; // the status criteria's window (ticks)

const clampT = (rec: MeosRecord, t: number) => Math.max(0, Math.min(rec.frames.length - 1, Math.floor(t)));
export const frameAt = (rec: MeosRecord, t: number): Frame => rec.frames[clampT(rec, t)];

// ---------------------------------------------------------------------------------------------------- operational relations
export interface Relation { id: number; tick: number; kind: 'alters' | 'detects' | 'reconfigures' | 'fires-on' | 'fires'; from: string; to: string; cell?: [number, number] }

/** The recorded relations of the last ``span`` ticks up to t: A1 alters the environment, A2 detects it, A2 reconfigures, A1 fires on the reconfiguration. */
export function relations(rec: MeosRecord, t: number, span = 14): Relation[] {
  const out: Relation[] = [];
  const byId = new Map<number, Ev>(rec.events.map((e) => [e.id, e]));
  for (const e of rec.events) {
    if (e.tick > t || e.tick <= t - span) continue;
    const cell = (e.cell as [number, number] | undefined) ?? undefined;
    if (e.kind === 'act' && e.actor === 'A1') out.push({ id: e.id, tick: e.tick, kind: 'alters', from: 'A1', to: 'M1', cell });
    else if (e.kind === 'act' && e.actor === 'A2' && (e.renewed as number) > 0) out.push({ id: e.id, tick: e.tick, kind: 'reconfigures', from: 'A2', to: 'R', cell });
    else if (e.kind === 'fire' && e.actor === 'A2' && e.source != null) out.push({ id: e.id, tick: e.tick, kind: 'detects', from: 'M1', to: 'A2', cell });
    else if (e.kind === 'fire' && e.actor === 'A1' && e.source != null && byId.get(e.source as number)?.actor === 'A2') out.push({ id: e.id, tick: e.tick, kind: 'fires-on', from: 'R', to: 'A1', cell });
    else if (e.kind === 'fire') out.push({ id: e.id, tick: e.tick, kind: 'fires', from: e.actor ?? '', to: e.actor ?? '', cell });
  }
  return out;
}

// ---------------------------------------------------------------------------------------------------- firing
export interface FiringView {
  entity: EntityName; state: 'firing' | 'refractory' | 'potential' | 'blocked' | 'absent';
  d: number; theta: number; s: number; baseline: number; ratio: number; failed: string[]; checks: Check[] | null;
  lastFire: number | null; lastFireEvent: Ev | null; expiresIn: number; refireIn: number; consequences: Ev[];
}

/** Why an operation fired or did not fire at tick t. ``checks`` is the full precondition record of a firing at t (or the latest firing); ``failed`` are the
 *  preconditions unmet at t. ``consequences`` are the recorded events that cite the latest firing. */
export function firingView(rec: MeosRecord, name: EntityName, t: number): FiringView {
  const f = frameAt(rec, t)[name];
  const fires = rec.events.filter((e) => e.kind === 'fire' && e.actor === name && e.tick <= t);
  const last = fires.length ? fires[fires.length - 1] : null;
  const conseq = last ? rec.events.filter((e) => e.tick <= t && ((e.kind === 'act' && e.fire === last.id) || (e.kind === 'expire' && e.fire === last.id) || (e.kind !== 'act' && e.source === last.id) || (e.kind === 'cycle' && (e.a2_fire === last.id || e.a1_fire === last.id)))) : [];
  const ratio = f.theta > 0 ? f.d / f.theta : 0;
  const state: FiringView['state'] = !f.present ? 'absent' : f.active > 0 ? 'firing' : f.cool > 0 ? 'refractory' : f.failed.length ? 'blocked' : 'potential';
  return {
    entity: name, state, d: f.d, theta: f.theta, s: f.s, baseline: f.baseline, ratio, failed: f.failed, checks: (last?.checks as Check[] | undefined) ?? null,
    lastFire: last?.tick ?? null, lastFireEvent: last, expiresIn: f.active, refireIn: f.cool, consequences: conseq.slice(-8),
  };
}

// ---------------------------------------------------------------------------------------------------- MEOS
export interface MeosView { label: Label; reason: string; cycles: number; reentry: number; age: number | null; dependency: Dependency; criteria: string }
export function meosView(rec: MeosRecord, t: number): MeosView {
  const fr = frameAt(rec, t);
  const cyc = rec.cycles.filter((c) => c.tick <= t && t - c.tick < WINDOW);
  const last = [...rec.cycles].reverse().find((c) => c.tick <= t);
  const log = [...rec.status_log].reverse().find((s) => s.tick <= t) ?? rec.status_log[0];
  return {
    label: fr.status, reason: log?.reason ?? '', cycles: cyc.length, reentry: cyc.filter((c) => c.history_reentry).length,
    age: last ? t - last.tick : null, dependency: fr.status === 'ACTIVE' ? null : (log?.dependency ?? null),
    criteria: 'ACTIVE: >= 2 complete cycles in the last 48 ticks, the latest <= 24 ticks old. COLLAPSED: none in the last 48 ticks after the first 48.',
  };
}

export interface StatusSegment { from: number; to: number; label: Label }
export function statusSegments(rec: MeosRecord): StatusSegment[] {
  const out: StatusSegment[] = [];
  rec.frames.forEach((f, i) => {
    const last = out[out.length - 1];
    if (last && last.label === f.status) last.to = i;
    else out.push({ from: i, to: i, label: f.status });
  });
  return out;
}

/** Entity participation in the recursion: it fired in a counted cycle within the status window. */
export function meosMembership(rec: MeosRecord, name: EntityName, t: number): boolean {
  const ev = new Map(rec.events.map((e) => [e.id, e]));
  return rec.events.some((e) => e.kind === 'cycle' && e.tick <= t && t - e.tick < WINDOW && ev.get(e[name === 'A1' ? 'a1_fire' : 'a2_fire'] as number)?.actor === name);
}

// ---------------------------------------------------------------------------------------------------- history
export interface HistoryPath { tick: number; entity: string; reentry: number; previous: number | null }
export function historyPaths(rec: MeosRecord, t: number, span = 60): HistoryPath[] {
  const byId = new Map(rec.events.map((e) => [e.id, e]));
  return rec.events
    .filter((e) => e.kind === 'fire' && e.tick <= t && e.tick > t - span && (e.history_reentry as number) > 0)
    .map((e) => ({ tick: e.tick, entity: e.actor ?? '', reentry: e.history_reentry as number, previous: e.previous_fire != null ? (byId.get(e.previous_fire as number)?.tick ?? null) : null }));
}

// ---------------------------------------------------------------------------------------------------- Address Domain
export interface AddressView { spatial: { x: number; y: number }; boundary: AdStatic['operational_boundary']; window: AdStatic['temporal_window']; speed: number;
  history: { trace: number; enabled: boolean; fires: number; lastFire: number | null }; connectivity: AdStatic['connectivity']; environment: { M1_local: number; mark_persistence: number };
  resource: { R_local: number; energy: number; power_reserve: number }; sss: AdStatic['sss'] }
export function addressView(rec: MeosRecord, name: EntityName, t: number, ad: { A1: AdStatic; A2: AdStatic } | null): AddressView | null {
  if (!ad) return null;
  const fr = frameAt(rec, t), e = fr[name], a = ad[name];
  const last = rec.events.filter((x) => x.kind === 'fire' && x.actor === name && x.tick <= t).pop();
  return {
    spatial: { x: e.x, y: e.y }, boundary: a.operational_boundary, window: a.temporal_window, speed: a.speed,
    history: { trace: e.h, enabled: a.history_reentry_enabled, fires: e.fires, lastFire: last?.tick ?? null }, connectivity: a.connectivity,
    environment: { M1_local: e.m1_local, mark_persistence: a.mark_persistence }, resource: { R_local: e.r_local, energy: e.energy, power_reserve: fr.power }, sss: a.sss,
  };
}

// ---------------------------------------------------------------------------------------------------- XenoBody partitions
export interface Hull { id: string; label: string; rects: Array<[number, number, number, number]>; points: Array<[number, number]>; includesDepot: boolean }
/** Cell-space footprint of each partition's operational components at tick t: sensing windows, positions, the interaction segment and (for the
 *  resource-transfer loop) the power depot. Components outside the arena (the depot) are flagged, not placed. */
export function xenobodyHulls(rec: MeosRecord, t: number, ad: { A1: AdStatic; A2: AdStatic } | null, partitions: Record<string, { label: string; components: string[] }>): Hull[] {
  const fr = frameAt(rec, t);
  const n = rec.fields.grid;
  const win = (name: EntityName): [number, number, number, number] => {
    const e = fr[name], r = ad?.[name].operational_boundary.sensor_radius ?? 2;
    return [Math.max(0, e.x - r), Math.max(0, e.y - r), Math.min(n - 1, e.x + r), Math.min(n - 1, e.y + r)];
  };
  return Object.entries(partitions).map(([id, p]) => {
    const rects: Hull['rects'] = [], points: Hull['points'] = [];
    const has = (c: string) => p.components.includes(c);
    if (has('A1')) { points.push([fr.A1.x, fr.A1.y]); if (has('sensor_resource')) rects.push(win('A1')); }
    if (has('A2')) { points.push([fr.A2.x, fr.A2.y]); if (has('sensor_alteration')) rects.push(win('A2')); }
    if (has('interaction_channel')) points.push([fr.A1.x, fr.A1.y], [fr.A2.x, fr.A2.y]);
    return { id, label: p.label, rects, points, includesDepot: has('feedback') && has('resource_renewal') };
  });
}

// ---------------------------------------------------------------------------------------------------- SSS
export interface SssView { scale: number; size: number; speed: number; sensorCells: number; footprintCells: number; stepsPerTick: number }
export function sssView(ad: { A1: AdStatic; A2: AdStatic } | null, name: EntityName): SssView | null {
  if (!ad) return null;
  const a = ad[name];
  return { ...a.sss, sensorCells: a.operational_boundary.sensor_radius, footprintCells: a.operational_boundary.footprint, stepsPerTick: a.speed };
}

// ---------------------------------------------------------------------------------------------------- data panel
export interface GraphEdge { from: string; to: string; count: number; label: string }
/** The interaction graph accumulated up to t: counts of recorded events per relation. */
export function interactionGraph(rec: MeosRecord, t: number): GraphEdge[] {
  const c = { alters: 0, detects: 0, reconfigures: 0, fires: 0, reentryA1: 0, reentryA2: 0 };
  for (const e of rec.events) {
    if (e.tick > t) break;
    if (e.kind === 'act' && e.actor === 'A1') c.alters++;
    else if (e.kind === 'fire' && e.actor === 'A2' && e.source != null) c.detects++;
    else if (e.kind === 'act' && e.actor === 'A2' && (e.renewed as number) > 0) c.reconfigures++;
    else if (e.kind === 'fire' && e.actor === 'A1' && e.source != null) c.fires++;
    if (e.kind === 'fire' && (e.history_reentry as number) > 0) { if (e.actor === 'A1') c.reentryA1++; else c.reentryA2++; }
  }
  return [
    { from: 'A1', to: 'M1', count: c.alters, label: 'alters' }, { from: 'M1', to: 'A2', count: c.detects, label: 'detected' },
    { from: 'A2', to: 'R', count: c.reconfigures, label: 'reconfigures' }, { from: 'R', to: 'A1', count: c.fires, label: 'fires on' },
    { from: 'H', to: 'A1', count: c.reentryA1, label: 're-entry' }, { from: 'H', to: 'A2', count: c.reentryA2, label: 're-entry' },
  ];
}

export interface Series { label: string; t: number[]; v: number[] }
export function trajectories(rec: MeosRecord): { resource: Series[]; history: Series[]; energy: Series[]; cycles: Series[] } {
  const t = rec.frames.map((f) => f.t);
  return {
    resource: [{ label: 'R total', t, v: rec.frames.map((f) => f.R) }, { label: 'power', t, v: rec.frames.map((f) => f.power) }],
    history: [{ label: 'h A1', t, v: rec.frames.map((f) => f.A1.h) }, { label: 'h A2', t, v: rec.frames.map((f) => f.A2.h) }],
    energy: [{ label: 'A1 energy', t, v: rec.frames.map((f) => f.A1.energy) }],
    cycles: [{ label: 'cycles in window', t, v: rec.frames.map((f) => f.cycles) }],
  };
}

// ---------------------------------------------------------------------------------------------------- MFS membership
export function mfsMembership(m: MfsOut | null, name: EntityName): string {
  if (!m) return 'not computed (run: find the minimal configuration)';
  if (name === 'A1') return 'the operation\'s own configuration (not a removable reduction)';
  return m.retained.includes('A2') ? 'retained: removing A2 ends the operation' : 'removable: the operation survives without it';
}
