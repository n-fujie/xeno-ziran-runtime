// Pure model of the high-fidelity laboratory view (no Three.js): everything the M8 viewer shows is computed here from
// a recorded or streamed run (schemas xzr.labrun/1–3). Nothing here can change a run.
//
// Three layers, each object carrying one of four categories:
//   layer A  physical apparatus   — driven by recorded MuJoCo state                       (category 1: executable)
//   layer B  scientific operations — driven by recorded runtime / system state           (category 2: runtime instrument,
//                                                                                          category 3: faithful
//                                                                                          representation of a dependency)
//   layer C  architectural context — no scientific claim                                  (category 4)
//
// Recorded vs derived. Every recorded event keeps its id `<stream>:<index>` (index into the record's event list).
// Quantities the record does not contain are either derived by a stated rule from recorded state (flagged `derived`,
// with the rule) or reported with an availability status — never filled with zeros.

import type { LabRecord, LabStep, PhysEvent, SystemState } from '../labScene';

export type Layer = 'A' | 'B' | 'C';
export type Category = 1 | 2 | 3 | 4;
export const CATEGORY_TEXT: Record<Category, string> = {
  1: 'executable physical apparatus (recorded MuJoCo state)',
  2: 'runtime-authoritative scientific instrument (recorded runtime / system state)',
  3: 'faithful representation of a recorded runtime or physical dependency',
  4: 'architectural context — no scientific claim',
};

export type Availability = 'recorded' | 'derived' | 'unmeasured' | 'measurement unavailable' | 'sensor incompatible'
  | 'outside observation range' | 'unknown' | 'operationally absent';
export type Field = { label: string; status: Availability; value?: string; note?: string };
const rec_ = (label: string, value: unknown, note?: string): Field => ({ label, status: 'recorded', value: fmt(value), note });
const st_ = (label: string, status: Availability, note?: string): Field => ({ label, status, note });

function fmt(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(3);
  if (Array.isArray(v)) return v.length ? v.map(fmt).join(', ') : 'none';
  return String(v);
}

// ------------------------------------------------------------------------------------------------------ events
export type Stream = 'apparatus' | 'physical' | 'science';
export type EventRef = { id: string; stream: Stream; idx: number; t: number; type: string; raw: Record<string, unknown> };

export function allEvents(r: LabRecord): EventRef[] {
  const out: EventRef[] = [];
  r.events.forEach((e, idx) => out.push({ id: `apparatus:${idx}`, stream: 'apparatus', idx, t: e.t, type: e.type, raw: e as never }));
  (r.physical_events ?? []).forEach((e, idx) => out.push({ id: `physical:${idx}`, stream: 'physical', idx, t: e.t, type: e.type, raw: e }));
  (r.science_events ?? []).forEach((e, idx) => out.push({ id: `science:${idx}`, stream: 'science', idx, t: e.t, type: e.type, raw: e }));
  return out.sort((a, b) => a.t - b.t || a.stream.localeCompare(b.stream) || a.idx - b.idx);
}

// ------------------------------------------------------------------------------------------------------ geometry facts
export type SpecLite = { sid: string; kind: string; home: string; sensors?: string[]; store?: string | null; reach?: string | null;
  comm?: string; comm_free?: boolean; inert?: boolean; budget?: number; cost_transfer?: number; memory?: string };

export function specs(r: LabRecord): SpecLite[] {
  return ((r.config.systems ?? []) as SpecLite[]).map((s) => ({ ...s }));
}

export function bayOf(cid: string): string {
  return cid.split('.')[0];
}

/** Bays ordered by angle round the laboratory centre (physics.py `ring`). */
export function ring(r: LabRecord): string[] {
  const bays = r.layout?.bays ?? {};
  return Object.keys(bays).sort((a, b) => Math.atan2(bays[a][1], bays[a][0]) - Math.atan2(bays[b][1], bays[b][0]));
}

/** Bays from a to b the short way round the ring (physics.py `_route`). */
export function route(rg: string[], a: string, b: string): string[] {
  const i = rg.indexOf(a), j = rg.indexOf(b), n = rg.length;
  const fwd = (((j - i) % n) + n) % n, back = (((i - j) % n) + n) % n;
  const step = fwd <= back ? 1 : -1;
  return Array.from({ length: Math.min(fwd, back) + 1 }, (_, k) => rg[(((i + step * k) % n) + n) % n]);
}

function reachRule(s: SpecLite): string {
  return s.reach ?? ({ local: 'bay', distributed: 'any', history: 'adjacent' } as Record<string, string>)[s.kind] ?? 'bay';
}

function reachOk(rg: string[], s: SpecLite, a: string, b: string): boolean {
  const rule = reachRule(s);
  if (rule === 'any') return true;
  const ia = rg.indexOf(bayOf(a)), ib = rg.indexOf(bayOf(b)), n = rg.length;
  const hops = Math.min((((ia - ib) % n) + n) % n, (((ib - ia) % n) + n) % n);
  return rule === 'bay' ? hops === 0 : hops <= 1;
}

/** Material in a chamber usable by a system: every sample in the shared laboratory, the group's own with private
 *  material (physics.py `material`). */
function material(r: LabRecord, s: LabStep, cid: string, sid: string): string[] {
  const items = s.physics?.contents[cid] ?? [];
  const part = r.config.partition as { groups?: Record<string, string>; material?: string } | undefined;
  if (!part || part.material !== 'private') return items;
  const g = part.groups?.[sid];
  return items.filter((x) => x.split('#')[1] === g);
}

// ------------------------------------------------------------------------------------------------------ five levels
export type Levels = {
  sid: string;
  exists: string[];  // experiments physically executable now (material, open target, working gantries on the route)
  observed: string[];  // chambers the system observes (recorded coverage)
  accessible: string[];  // experiments the system can select now (derived by science.py `candidates` from recorded state)
  selected: string[];  // experiments the system selected up to this step (recorded experiment_selected events)
  executed: string[];  // experiments delivered up to this step (recorded material_delivered events)
  pending: [string, string] | null;
};

/** What exists, what a system observes, can access, selects and executes — the M9 distinction, at step index i. */
export function levels(r: LabRecord, i: number, sid: string): Levels | null {
  const s = r.steps[i];
  const st: SystemState | undefined = s.science?.[sid];
  const spec = specs(r).find((x) => x.sid === sid);
  if (!st || !spec) return null;
  const rg = ring(r);
  const cidIdx = new Map(r.chambers.map((c, k) => [c.cid, k]));
  const open = (c: string) => (s.shutter[cidIdx.get(c) ?? -1] ?? 1) >= 0.5;
  const cov = [...st.coverage].sort();
  const accessible: string[] = [];
  for (const a of cov) {
    if (!material(r, s, a, sid).length) continue;
    for (const b of cov) {
      if (b !== a && reachOk(rg, spec, a, b) && open(b) && !st.isolated.includes(b)) accessible.push(`${a}>${b}`);
    }
  }
  const gantries = s.physics?.gantries ?? {};
  const part = r.config.partition as { groups?: Record<string, string>; gantries?: string } | undefined;
  const gkey = (bay: string) => (part?.gantries === 'private' ? `${bay}#${part.groups?.[sid]}` : bay);
  const works = (a: string, b: string) => route(rg, bayOf(a), bayOf(b)).every((bay) => !gantries[gkey(bay)]?.failed);
  const exists: string[] = [];
  if (s.physics) {
    for (const ca of r.chambers) {
      if (!material(r, s, ca.cid, sid).length) continue;
      for (const cb of r.chambers) {
        if (cb.cid !== ca.cid && reachOk(rg, spec, ca.cid, cb.cid) && open(cb.cid) && works(ca.cid, cb.cid)) exists.push(`${ca.cid}>${cb.cid}`);
      }
    }
  }
  const evs = (r.science_events ?? []).filter((e) => e.system === sid && e.t <= s.t);
  return {
    sid, exists, observed: cov, accessible,
    selected: evs.filter((e) => e.type === 'experiment_selected').map((e) => `${String(e.src)}>${String(e.dst)}`),
    executed: evs.filter((e) => e.type === 'material_delivered').map((e) => `${String(e.src)}>${String(e.dst)}`),
    pending: st.pending,
  };
}

// ------------------------------------------------------------------------------------------------------ transfers
export type TransferState = 'queued' | 'carrying' | 'transport complete' | 'delivered' | 'delivery blocked' | 'failed';
export type Transfer = { tid: number; system: string | null; src: string; dst: string; state: TransferState;
  requested: number | null; completed: number | null; events: string[]; note: string };

/** Transfers and their states, up to step t. "Delivered" only on a recorded material_delivered event (the runtime
 *  accepted the material); a transfer whose sample reached the chamber but whose delivery was refused is
 *  "delivery blocked" — physical transport completion is not delivery (M9 measurement-definition defect). */
export function transfers(r: LabRecord, t: number): Transfer[] {
  const ph = (r.physical_events ?? []).map((e, idx) => ({ e, id: `physical:${idx}` })).filter((x) => x.e.t <= t);
  const sc = (r.science_events ?? []).map((e, idx) => ({ e, id: `science:${idx}` })).filter((x) => x.e.t <= t);
  const by = new Map<number, Transfer>();
  for (const { e, id } of ph) {
    const tid = e.transfer as number | undefined;
    if (tid === undefined) continue;
    let tr = by.get(tid);
    if (!tr) {
      tr = { tid, system: null, src: String(e.src ?? e.at ?? ''), dst: String(e.dst ?? ''), state: 'queued', requested: null,
        completed: null, events: [], note: '' };
      by.set(tid, tr);
    }
    tr.events.push(id);
    if (e.type === 'sample_grasped' && tr.state === 'queued') tr.state = 'carrying';
    if (e.type === 'transfer_failed') { tr.state = 'failed'; tr.note = String(e.reason ?? ''); tr.src = String(e.src); tr.dst = String(e.dst); }
    if (e.type === 'transfer_complete') {
      tr.state = 'transport complete';
      tr.src = String(e.src); tr.dst = String(e.dst);
      tr.requested = e.requested_at as number;
      tr.completed = e.t;
      const d = sc.find((x) => (x.e.type === 'material_delivered' || x.e.type === 'delivery_blocked') && x.e.t === e.t && x.e.dst === e.dst);
      if (d) {
        tr.system = String(d.e.system);
        tr.state = d.e.type === 'material_delivered' ? 'delivered' : 'delivery blocked';
        tr.events.push(d.id);
        tr.note = d.e.type === 'material_delivered' ? 'the runtime accepted the material (connection made, load injected)'
          : 'transport completed, delivery refused: the target containment was closed';
      } else {
        tr.note = 'transport complete; no delivery event recorded for it (run without scientific systems, or an operation\'s connection)';
      }
    }
  }
  for (const tr of by.values()) {
    if (tr.system === null) {
      const f = sc.find((x) => x.e.type === 'experiment_failed' && x.e.src === tr.src && x.e.dst === tr.dst && tr.events.length
        && x.e.t === (ph.find((p) => p.id === tr.events[tr.events.length - 1])?.e.t));
      if (f) tr.system = String(f.e.system);
    }
  }
  return [...by.values()].sort((a, b) => a.tid - b.tid);
}

// ------------------------------------------------------------------------------------------------------ mediation
export type GantryMediation = { key: string; bay: string; group: string | null; health: number; failed: boolean; queue: number;
  resources: number; carrying: string | null; legsBySystem: Record<string, number>; shared: boolean; failures: number };

/** Physical-resource mediation at step index i: which systems' legs each gantry has served so far (from recorded leg
 *  events and their transfers), wear (recorded health), queue, failures. */
export function mediation(r: LabRecord, i: number, known?: Transfer[]): GantryMediation[] {
  const s = r.steps[i];
  const g = s.physics?.gantries;
  if (!g) return [];
  const owner = new Map((known ?? transfers(r, s.t)).map((tr) => [tr.tid, tr.system]));
  const legs: Record<string, Record<string, number>> = {};
  const fails: Record<string, number> = {};
  for (const e of r.physical_events ?? []) {
    if (e.t > s.t) break;
    if (e.type === 'leg_complete') {
      const key = String(e.bay);
      const sys = owner.get(e.transfer as number) ?? 'unattributed';
      legs[key] = legs[key] ?? {};
      legs[key][sys] = (legs[key][sys] ?? 0) + 1;
    }
    if (e.type === 'gantry_failed') fails[String(e.bay)] = (fails[String(e.bay)] ?? 0) + 1;
  }
  return Object.entries(g).map(([key, x]) => {
    const bay = x.bay ?? key;
    const byS = x.group ? {} : (legs[bay] ?? {});  // leg events name the bay; with private carriages they are not split per carriage
    return { key, bay, group: x.group ?? null, health: x.health, failed: x.failed, queue: x.queue, resources: x.resources,
      carrying: x.carrying, legsBySystem: byS, shared: Object.keys(byS).filter((k) => k !== 'unattributed').length > 1,
      failures: fails[bay] ?? 0 };
  });
}

// ------------------------------------------------------------------------------------------------------ transitions
export type TransitionKind = 'ignition' | 'intervention' | 'observation revision' | 'variable adoption' | 'historical reinsertion'
  | 'interference' | 'extinction' | 're-ignition' | 'harness intervention';
export type Transition = { kind: TransitionKind; t: number; system: string | null; where: string[]; eventId: string | null;
  derived: boolean; rule: string };

/** Scientific operational transitions up to step t. Recorded ones point to their event id; derived ones state their rule. */
export function transitions(r: LabRecord, t: number): Transition[] {
  const out: Transition[] = [];
  const sc = r.science_events ?? [];
  const iso = sc.filter((e) => e.type === 'isolation').map((e) => ({ t0: e.t, t1: e.until as number, sys: String(e.system), c: String(e.chamber) }));
  sc.forEach((e, idx) => {
    if (e.t > t) return;
    const id = `science:${idx}`;
    const sys = e.system === undefined ? null : String(e.system);
    if (e.type === 'material_delivered') out.push({ kind: 'intervention', t: e.t, system: sys, where: [String(e.src), String(e.dst)], eventId: id, derived: false, rule: 'recorded delivery' });
    if (e.type === 'sensor_relocated') out.push({ kind: 'observation revision', t: e.t, system: sys, where: [String(e.from), String(e.to)], eventId: id, derived: false, rule: 'recorded sensor relocation' });
    if (e.type === 'window_changed') out.push({ kind: 'observation revision', t: e.t, system: sys, where: [], eventId: id, derived: false, rule: `recorded window change ${String(e.from)} → ${String(e.to)}` });
    if (e.type === 'variable_candidate' && e.adopted) out.push({ kind: 'variable adoption', t: e.t, system: sys, where: [], eventId: id, derived: false, rule: `recorded adoption of ${String(e.variable)}` });
    if (e.type === 'experiment_selected' && e.basis === 'memory') out.push({ kind: 'historical reinsertion', t: e.t, system: sys, where: [String(e.src), String(e.dst)], eventId: id, derived: false, rule: 'recorded selection whose prediction used retained memory (basis = memory)' });
    if (e.type === 'harness') out.push({ kind: 'harness intervention', t: e.t, system: null, where: (e.chambers as string[] | undefined) ?? [], eventId: id, derived: false, rule: `declared harness intervention: ${String(e.do)}` });
    if (e.type === 'delivery_blocked') {
      const by = iso.filter((x) => x.c === e.dst && x.t0 <= e.t && e.t < x.t1 && x.sys !== sys).map((x) => x.sys);
      if (by.length) out.push({ kind: 'interference', t: e.t, system: sys, where: [String(e.dst)], eventId: id, derived: true, rule: `delivery blocked during the recorded isolation of ${String(e.dst)} by system ${by.join(', ')}` });
    }
  });
  const ext = r.config.extinction as { system: string; t: number } | undefined;
  if (ext) {  // M9-C operational definitions (docs/LAB_PROTOCOL_M9.md §6, xzr/lab/causal.py) applied to recorded deliveries
    const T = ext.t;
    const ts = sc.filter((e) => e.type === 'material_delivered' && e.system === ext.system).map((e) => e.t);
    const active = ts.some((x) => x >= T - 160 && x < T);
    const extinct = active && !ts.some((x) => x >= T + 30 && x < T + 190);
    if (extinct && t >= T + 190) out.push({ kind: 'extinction', t: T + 30, system: ext.system, where: [], eventId: null, derived: true, rule: 'M9-C definition: active in [T−160, T), no delivery in [T+30, T+190)' });
    const later = ts.filter((x) => x >= T + 190);
    if (extinct && later.length && t >= later[0]) {
      const idx = sc.findIndex((e) => e.type === 'material_delivered' && e.system === ext.system && e.t === later[0]);
      out.push({ kind: 're-ignition', t: later[0], system: ext.system, where: [], eventId: `science:${idx}`, derived: true, rule: 'M9-C definition: first delivery after the extinct interval' });
    }
  }
  return out.sort((a, b) => a.t - b.t);
}

/** Ignition (derived): experiments that became accessible to a system at decision step i that were not accessible at
 *  its previous decision step (accessibility derived from recorded state, verified against the backend). */
export function ignitions(r: LabRecord, i: number, sid: string, period = 4): string[] {
  const now = levels(r, i, sid);
  const j = r.steps.findIndex((s) => s.t === r.steps[i].t - period);
  const before = j >= 0 ? levels(r, j, sid) : null;
  if (!now || !before) return [];
  return now.accessible.filter((x) => !before.accessible.includes(x));
}

// ------------------------------------------------------------------------------------------------------ provenance
export type Provenance = { event: EventRef; initiating: EventRef[]; consequences: EventRef[]; attribution: string;
  preceding: Field[]; affected: string[] };

/** Recorded provenance of one event: recorded causes and linked events only (transfer id, system and experiment). No
 *  attribution is inferred from temporal proximity; if none is recorded it says so. */
export function provenance(r: LabRecord, id: string): Provenance | null {
  const evs = allEvents(r);
  const ev = evs.find((e) => e.id === id);
  if (!ev) return null;
  const x = ev.raw;
  const affected = [x.chamber, x.src, x.dst, x.at].filter((v) => typeof v === 'string') as string[];
  const pair = typeof x.pair === 'string' ? (x.pair as string).split('|') : [];
  affected.push(...pair);
  let initiating: EventRef[] = [];
  let consequences: EventRef[] = [];
  let attribution = 'unresolved: no causal link is recorded for this event';
  if (ev.stream === 'apparatus') {
    const cause = (x.cause as string[] | undefined) ?? [];
    attribution = cause.length ? `recorded cause: ${cause.join(', ')}` : attribution;
  } else if (ev.stream === 'physical' && typeof x.transfer === 'number') {
    const tr = transfers(r, Infinity).find((t) => t.tid === x.transfer);
    if (tr) {
      const linked = tr.events.map((i) => evs.find((e) => e.id === i)!).filter(Boolean);
      initiating = linked.filter((e) => e.t < ev.t || (e.t === ev.t && e.idx < ev.idx && e.stream === ev.stream));
      consequences = linked.filter((e) => !initiating.includes(e) && e.id !== ev.id);
      attribution = `recorded transfer ${tr.tid}${tr.system ? ` of system ${tr.system}` : ''}: ${tr.state} — ${tr.note}`;
    }
    if (x.reason) attribution += ` · recorded reason: ${String(x.reason)}`;
  } else if (ev.stream === 'science' && typeof x.system === 'string') {
    const same = evs.filter((e) => e.stream === 'science' && e.raw.system === x.system);
    if (x.src !== undefined && x.dst !== undefined) {
      const exp = same.filter((e) => e.raw.src === x.src && e.raw.dst === x.dst);
      const sel = exp.filter((e) => e.type === 'experiment_selected' && e.t <= ev.t).pop();
      if (sel && sel.id !== ev.id) initiating = [sel];
      consequences = exp.filter((e) => e.t > ev.t && e.type !== 'experiment_selected').slice(0, 4);
      const obs = same.filter((e) => (e.type === 'outcome_observed' || e.type === 'outcome_unobservable') && e.raw.dst === x.dst && e.t > ev.t).slice(0, 1);
      if (ev.type === 'material_delivered') consequences = [...consequences, ...obs];
      attribution = sel ? `recorded experiment of system ${String(x.system)} (${String(x.src)} → ${String(x.dst)}) selected at t${sel.t}`
        : `recorded event of system ${String(x.system)}`;
    } else if (ev.type === 'isolation') {
      consequences = evs.filter((e) => e.t >= ev.t && e.t <= (x.until as number) && ((e.type === 'delivery_blocked' && e.raw.dst === x.chamber)
        || (e.type === 'reopened' && e.raw.chamber === x.chamber && e.raw.system === x.system)));
      attribution = `recorded isolation by system ${String(x.system)}: observed activity ${fmt(x.observed_activity)} above its threshold`;
    } else {
      attribution = `recorded event of system ${String(x.system)}`;
    }
  } else if (ev.type === 'harness') {
    consequences = evs.filter((e) => e.t === ev.t && e.stream === 'physical');
    attribution = `declared harness intervention (part of the run's configuration): ${String(x.do)}`;
  }
  const i = Math.max(0, r.steps.findIndex((s) => s.t === ev.t) - 1);
  const prev = r.steps[i];
  const preceding: Field[] = [];
  const cidIdx = new Map(r.chambers.map((c, k) => [c.cid, k]));
  for (const c of [...new Set(affected)].filter((c) => cidIdx.has(c))) {
    const k = cidIdx.get(c)!;
    preceding.push(rec_(`${c} containment (t${prev.t})`, prev.shutter[k]), rec_(`${c} activity (t${prev.t})`, prev.activity[k]));
    if (prev.physics) preceding.push(rec_(`${c} material (t${prev.t})`, prev.physics.contents[c] ?? []));
  }
  if (typeof x.system === 'string' && prev.science?.[x.system as string]) {
    const sy = prev.science[x.system as string];
    preceding.push(rec_(`system ${String(x.system)} observes (t${prev.t})`, sy.coverage), rec_(`budget (t${prev.t})`, sy.budget));
  }
  return { event: ev, initiating, consequences, attribution, preceding, affected: [...new Set(affected)] };
}

// ------------------------------------------------------------------------------------------------------ inspection
export type Selection = { kind: 'chamber' | 'gantry' | 'sample' | 'port' | 'sensor' | 'store'; id: string };

/** Recorded operational state of a selected apparatus at step index i, with availability statuses. */
export function inspect(r: LabRecord, i: number, sel: Selection): { title: string; layer: Layer; category: Category; fields: Field[] } {
  const s = r.steps[i];
  const ph = s.physics;
  const cidIdx = new Map(r.chambers.map((c, k) => [c.cid, k]));
  const sys = s.science ?? {};
  const noPhys = st_('physical state', 'unmeasured', 'record without the physical laboratory');
  if (sel.kind === 'chamber') {
    const k = cidIdx.get(sel.id)!;
    const observers = Object.entries(sys).filter(([, x]) => x.coverage.includes(sel.id)).map(([sid]) => sid);
    const unobserved = Object.keys(sys).filter((sid) => !observers.includes(sid));
    const last = allEvents(r).filter((e) => e.t <= s.t && (e.raw.chamber === sel.id || e.raw.dst === sel.id
      || (typeof e.raw.pair === 'string' && (e.raw.pair as string).split('|').includes(sel.id)))).pop();
    return { title: `Chamber ${sel.id} (domain ${bayOf(sel.id)})`, layer: 'B', category: 2, fields: [
      rec_('configurations', r.chambers[k].size),
      rec_('containment (mean gate of entering connections)', s.shutter[k]),
      rec_('activity (share ignited this step)', s.activity[k]),
      rec_('retained memory (mean)', s.memory[k]),
      ph ? rec_('material', ph.contents[sel.id] ?? []) : noPhys,
      rec_('observed by', observers.length ? observers : 'no system'),
      ...unobserved.map((sid) => st_(`system ${sid}`, 'outside observation range', 'not in its recorded coverage at this step')),
      rec_('connections to other chambers', Object.entries(s.conduits).filter(([p]) => p.split('|').includes(sel.id)).map(([p, n]) => `${p.replace(sel.id, '').replace('|', '')}×${n}`)),
      last ? rec_('last recorded event', `${last.id} ${last.type} (t${last.t})`) : st_('last recorded event', 'operationally absent', 'no event recorded for this chamber yet'),
    ] };
  }
  if (sel.kind === 'gantry') {
    const g = ph?.gantries[sel.id];
    if (!g) return { title: `Gantry ${sel.id}`, layer: 'A', category: 1, fields: [noPhys] };
    const med = mediation(r, i).find((m) => m.key === sel.id);
    return { title: `Gantry ${sel.id}${g.group ? ` (private carriage of group ${g.group})` : ' (shared)'}`, layer: 'A', category: 1, fields: [
      rec_('domain (bay)', g.bay ?? sel.id), rec_('tool tip (MuJoCo, m)', g.tip),
      rec_('actuator health', g.health), rec_('failed', g.failed), rec_('repair resources', g.resources),
      rec_('queued legs', g.queue), rec_('carrying', g.carrying ?? 'nothing'),
      med && !g.group ? rec_('completed legs by system (so far)', Object.entries(med.legsBySystem).map(([k, n]) => `${k}: ${n}`))
        : st_('completed legs by system', 'measurement unavailable', 'leg events name the bay, not the private carriage'),
      med ? rec_('shared by more than one system', med.shared) : st_('sharing', 'unknown'),
      med ? rec_('gantry failures in this bay (so far)', med.failures) : st_('failures', 'unknown'),
    ] };
  }
  if (sel.kind === 'sample') {
    const p = ph?.samples[sel.id];
    if (!p) return { title: `Sample ${sel.id}`, layer: 'A', category: 1, fields: [noPhys] };
    const where = Object.entries(ph!.contents).find(([, v]) => v.includes(sel.id))?.[0];
    const by = Object.entries(ph!.gantries).find(([, g]) => g.carrying === sel.id)?.[0];
    return { title: `Material sample ${sel.id}`, layer: 'A', category: 1, fields: [
      rec_('position (MuJoCo, m)', p), by ? rec_('carried by gantry', by) : rec_('in container', where ?? 'outside every container'),
      st_('orientation', 'unmeasured', 'the record keeps positions only'),
    ] };
  }
  if (sel.kind === 'port') {
    return { title: `Handoff port ${sel.id}`, layer: 'A', category: 1, fields: [
      ph ? rec_('samples on the port', ph.contents[sel.id] ?? []) : noPhys,
      rec_('role', 'relay between the two bays it joins (routing: the short way round the ring)'),
    ] };
  }
  const [sid] = sel.id.split(':');
  const x = sys[sid];
  const spec = specs(r).find((y) => y.sid === sid);
  if (!x || !spec) return { title: `System ${sid}`, layer: 'B', category: 2, fields: [st_('state', 'operationally absent')] };
  const lv = levels(r, i, sid);
  const evs = (r.science_events ?? []).map((e, idx) => ({ e, idx })).filter(({ e }) => e.system === sid && e.t <= s.t);
  const lastC = evs.filter(({ e }) => e.type === 'material_delivered').pop();
  const fail = evs.filter(({ e }) => e.type === 'experiment_failed' || e.type === 'delivery_blocked').pop();
  const fields: Field[] = [
    rec_('kind', `${spec.kind} (decision rule shared by every system; heterogeneity is configuration-dependent)`),
    rec_(sel.kind === 'store' ? 'memory store chamber' : spec.kind === 'distributed' ? 'hub' : 'sensor head', sel.kind === 'store' ? spec.store : x.sensor),
    spec.kind === 'distributed' ? rec_('sensors', spec.sensors ?? []) : st_('remote sensors', 'operationally absent', 'only distributed systems have them'),
    spec.kind === 'distributed' ? rec_('readings travel', spec.comm_free ? 'free' : spec.comm ?? 'along live runtime connections (≤ 3 hops)') : st_('communication', 'operationally absent'),
    rec_('observation window (steps)', x.window), rec_('observed chambers', x.coverage),
    rec_('reach', reachRule(spec)),
    rec_('budget left', x.budget),
    rec_('memory entries', x.memory), rec_('adopted variables', x.features.length ? x.features : 'none'),
    rec_('isolating', x.isolated), x.pending ? rec_('pending experiment', `${x.pending[0]} → ${x.pending[1]}`) : rec_('pending experiment', 'none'),
    lastC ? rec_('last delivery (consequential event)', `science:${lastC.idx} ${String(lastC.e.src)} → ${String(lastC.e.dst)} (t${lastC.e.t}); harness true effect ${fmt(lastC.e.true_effect)} (never seen by the system)`)
      : st_('last delivery', 'operationally absent', 'no delivery yet'),
    fail ? rec_('last failure', `science:${fail.idx} ${fail.e.type} ${String(fail.e.reason ?? fail.e.dst ?? '')} (t${fail.e.t})`) : st_('last failure', 'operationally absent'),
  ];
  if (lv) fields.push({ label: 'experimentally accessible now', status: 'derived', value: `${lv.accessible.length}`, note: 'science.py candidates() applied to recorded state' });
  if (spec.inert) fields.push(rec_('inert', 'physical work only; no runtime effect'));
  return { title: `System ${sid} — ${sel.kind === 'store' ? 'memory store' : 'observation'}`, layer: 'B', category: 2, fields };
}

export function sharedSystems(r: LabRecord): string[] {
  return specs(r).map((s) => s.sid);
}

export type { PhysEvent };
