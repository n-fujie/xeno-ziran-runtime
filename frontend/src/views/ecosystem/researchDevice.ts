// XENO ECOSYSTEM — the megastructure as a research device. Each space of the structure is mapped to the experimental function it serves, and the
// objects that move or change here do so only because a quantity of the record changed:
//
//   Habitat / Arena         the MEOS-0 grid and the two operational configurations          (arena.ts of megastructure.ts)
//   Processing Layer        the stockpile and the resource carriers: transport of renewed resource
//   Observation Array       twelve dishes: aimed at the observed region, lit in proportion to the cells the observation covers, flashing on sampled ticks
//   Underground Chambers    twelve trial chambers: the outcome of each reduction trial; the selected one is ringed
//   Research Core           the shaft and its instruments (static architecture, no state)
//   Boundary Layer          a barrier ring at the arena's operational boundary: closed while the coupling channels are intact, opened per cut channel
//   Empty Sockets           the expansion bays; one of them takes the first-stage Philosophical module, which exists only in a run that configures one
//
// Everything below the "pure" line is a function of (record, tick, observation) with no state of its own, so it can be tested without a renderer.
import * as THREE from 'three';
import { adAt, FULL_OBSERVATION, type MeosRecord, type Observation } from './meosApi';
import { WORLD } from './megastructure';

// ---------------------------------------------------------------------------------------------------- pure: what the record says about the device
export interface DeviceState {
  phil: { enabled: boolean; mode: string; expressionAge: number | null; responseAge: number | null; scoreAge: number | null; revisionAge: number | null;
    boost: number; reliability: number; trust: number; measuredEfficiency: number; expressions: number; power: number; channelDelay: number };
  pulse: { active: boolean; age: number; x: number; y: number; amount: number };
  recovery: { phase: 'none' | 'collapsed' | 'recovered'; since: number | null; age: number | null; recoveries: number };
  boundary: { arenaRadius: number | null; open: string[]; closed: boolean };
  array: { sampling: boolean; coverage: number; activeDishes: number; aim: [number, number]; region: number[] | null };
}
const PULSE_TICKS = 14, EVENT_TICKS = 10;
const lastAge = (rec: MeosRecord, kind: string, t: number): number | null => {
  for (let i = rec.events.length - 1; i >= 0; i--) { const e = rec.events[i]; if (e.kind === kind && e.tick <= t) return t - e.tick; }
  return null;
};
const trace = (rec: MeosRecord, key: string, t: number, fallback: number): number => {
  const a = rec.traces?.[key];
  return a && a.length ? a[Math.min(t, a.length - 1)] : fallback;
};

/** Coverage of an observation: the share of arena cells (and ticks) it resolves, the product of its spatial lattice, its region and its sampling interval. */
export function observationCoverage(obs: Observation, grid: number): number {
  const r = obs.region;
  const area = r ? Math.max(0, (Math.min(r[2], grid - 1) - Math.max(r[0], 0) + 1)) * Math.max(0, (Math.min(r[3], grid - 1) - Math.max(r[1], 0) + 1)) / (grid * grid) : 1;
  return Math.max(0, Math.min(1, area / (Math.max(1, obs.spatial_stride) ** 2)));
}

export function deviceState(rec: MeosRecord, tick: number, obsIn: Partial<Observation> | null | undefined): DeviceState {
  const t = Math.min(Math.max(0, tick), rec.frames.length - 1);
  const obs: Observation = { ...FULL_OBSERVATION, ...(obsIn ?? {}) };
  const phil = rec.config.phil, mode = phil?.mode ?? 'none';
  // resource pulse: the latest injection (ALTER_RESOURCE with inject) and how long ago it was
  const inj = [...rec.intervention_log].reverse().find((i) => i.op === 'ALTER_RESOURCE' && (i as { inject?: unknown }).inject && i.tick <= t) as
    | { tick: number; inject: { x: number; y: number; amount: number } } | undefined;
  const pulseAge = inj ? t - inj.tick : Infinity;
  // recovery: a COLLAPSED -> ACTIVE transition in the status log; "collapsed" while the last transition is a collapse
  const log = rec.status_log.filter((s) => s.tick <= t);
  const last = log[log.length - 1];
  let recoveries = 0;
  for (let i = 1; i < log.length; i++) if (log[i].label === 'ACTIVE' && log[i - 1].label !== 'ACTIVE' && log.slice(0, i).some((s) => s.label === 'COLLAPSED')) recoveries++;
  const ad = adAt(rec.frames, t);  // the Address Domain is recorded in a frame only when it changes
  const open: string[] = [];
  if (ad) {
    const c = ad.A1.connectivity;
    for (const [k, v] of Object.entries(c)) if (!v) open.push(k);
    if (!ad.A2.present) open.push('A2 absent');
  }
  const arenaRadius = ad?.A1.operational_boundary.arena_radius ?? null;
  const cov = observationCoverage(obs, rec.config.grid);
  const region = obs.region;
  const aim: [number, number] = region ? [(region[0] + region[2]) / 2, (region[1] + region[3]) / 2] : [(rec.config.grid - 1) / 2, (rec.config.grid - 1) / 2];
  return {
    phil: {
      enabled: mode !== 'none', mode,
      expressionAge: mode === 'none' ? null : lastAge(rec, 'expression', t), responseAge: mode === 'none' ? null : lastAge(rec, 'response', t),
      scoreAge: mode === 'none' ? null : lastAge(rec, 'score', t), revisionAge: mode === 'none' ? null : lastAge(rec, 'revision', t),
      boost: trace(rec, 'phil_boost', t, 1), reliability: trace(rec, 'phil_reliability_scarcity', t, 0.5), trust: trace(rec, 'phil_trust_scarcity', t, 0.5),
      measuredEfficiency: trace(rec, 'phil_measured_efficiency', t, 1), expressions: trace(rec, 'phil_expressions', t, 0), power: trace(rec, 'phil_power_spent', t, 0),
      channelDelay: phil?.delay ?? 1,
    },
    pulse: { active: pulseAge <= PULSE_TICKS, age: pulseAge, x: inj?.inject.x ?? 0, y: inj?.inject.y ?? 0, amount: inj?.inject.amount ?? 0 },
    recovery: {
      phase: !last ? 'none' : last.label === 'COLLAPSED' ? 'collapsed' : recoveries > 0 ? 'recovered' : 'none',
      since: last ? last.tick : null, age: last ? t - last.tick : null, recoveries,
    },
    boundary: { arenaRadius, open, closed: open.length === 0 },
    array: { sampling: t % Math.max(1, obs.sampling_interval) === 0, coverage: cov, activeDishes: Math.max(1, Math.round(12 * cov)), aim, region },
  };
}
export const DEVICE_EVENT_TICKS = EVENT_TICKS;

/** The experimental function each space serves, for the interface and the documentation. */
export const SPACES: Array<{ space: string; function: string; driven_by: string }> = [
  { space: 'Habitat / Arena', function: 'where the two operational configurations act on the resource field', driven_by: 'the frame: R, M1, M2, entity positions and firing' },
  { space: 'Processing Layer', function: 'transport and stock of renewed resource', driven_by: 'A2 renewal events (carriers), total R (stockpile)' },
  { space: 'Observation Array', function: 'the observation: where it looks, how much of the arena it resolves, when it samples', driven_by: 'observation region (aim), coverage (lit dishes), sampling interval (flash)' },
  { space: 'Underground Chambers', function: 'outcomes of reduction trials', driven_by: 'ablation results; the selected chamber is ringed' },
  { space: 'Research Core', function: 'the shaft that carries the layers (no state)', driven_by: 'nothing: static architecture' },
  { space: 'Boundary Layer', function: 'the operational boundary of the arrangement', driven_by: 'arena radius and the connectivity of the coupling channels (opened per cut channel)' },
  { space: 'Empty Sockets', function: 'bays for further modules; the first-stage Philosophical module is one', driven_by: 'the phil configuration and its expression / response / score / revision events' },
];

// ---------------------------------------------------------------------------------------------------- scene objects (no state beyond what was last set)
const v3 = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);
const mono = (c: number, o = 1) => new THREE.MeshBasicMaterial({ color: c, transparent: o < 1, opacity: o, depthWrite: o >= 1, blending: THREE.AdditiveBlending, side: THREE.DoubleSide });

export interface DeviceLayer {
  group: THREE.Group;
  set(d: DeviceState, o: { arenaCell: (x: number, y: number) => THREE.Vector3; selectedTrial: number | null; trialPos: THREE.Vector3[]; n: number }): void;
  dispose(): void;
}

export function buildDeviceLayer(arenaGroup: THREE.Group, n: number): DeviceLayer {
  const group = new THREE.Group();
  group.name = 'research-device';
  const owned: Array<{ dispose(): void }> = [];
  const own = <T extends { dispose(): void }>(x: T): T => { owned.push(x); return x; };

  // --- pulse: an expanding ring at the injected cell, in the arena's frame
  const pulseGeo = own(new THREE.RingGeometry(0.9, 1, 40)), pulseMat = own(mono(0xffffff, 0.9));
  const pulse = new THREE.Mesh(pulseGeo, pulseMat); pulse.rotation.x = -Math.PI / 2; pulse.visible = false; arenaGroup.add(pulse);

  // --- recovery halo around the arena (lit while a recovery is recent, dim ring while collapsed)
  const half = n / 2;
  const haloGeo = own(new THREE.TorusGeometry(half * 1.42, 0.12, 8, 96)), haloMat = own(mono(0xffffff, 0.0));
  const halo = new THREE.Mesh(haloGeo, haloMat); halo.rotation.x = Math.PI / 2; halo.position.y = 0.25; arenaGroup.add(halo);

  // --- boundary layer: a barrier of posts at the operational boundary, raised when closed, lowered per open channel
  const POSTS = 48;
  const postGeo = own(new THREE.BoxGeometry(0.16, 1, 0.16)), postMat = own(new THREE.MeshStandardMaterial({ color: 0xcfd1d6, metalness: 0.8, roughness: 0.3, emissive: 0xffffff, emissiveIntensity: 0.35 }));
  const posts = own(new THREE.InstancedMesh(postGeo, postMat, POSTS)); posts.frustumCulled = false; arenaGroup.add(posts);
  const M = new THREE.Matrix4(), Q = new THREE.Quaternion(), S = new THREE.Vector3(), P = new THREE.Vector3();

  // --- selected chamber ring
  const ringGeo = own(new THREE.TorusGeometry(5.2, 0.14, 8, 40)), ringMat = own(mono(0xffffff, 0.85));
  const chamberRing = new THREE.Mesh(ringGeo, ringMat); chamberRing.visible = false; group.add(chamberRing);

  // --- the first-stage Philosophical module, in the third expansion bay (sockets elsewhere stay empty)
  const bay = ((): THREE.Vector3 => { const a = (3 / 9) * Math.PI * 2; return v3(WORLD.expansion.x + Math.cos(a) * 16, 0, WORLD.expansion.z + Math.sin(a) * 16); })();
  const mod = new THREE.Group(); mod.position.copy(bay); mod.visible = false; group.add(mod);
  const baseGeo = own(new THREE.CylinderGeometry(3.4, 3.7, 0.6, 6)), baseMat = own(new THREE.MeshStandardMaterial({ color: 0x8a8d94, metalness: 0.8, roughness: 0.35 }));
  const base = new THREE.Mesh(baseGeo, baseMat); base.position.y = 0.3; mod.add(base);
  const mastGeo = own(new THREE.CylinderGeometry(0.28, 0.4, 7, 10)), mast = new THREE.Mesh(mastGeo, baseMat); mast.position.y = 4; mod.add(mast);
  const lampGeo = own(new THREE.SphereGeometry(0.62, 14, 10));
  const lamps = [0, 1, 2, 3].map((i) => {
    const m = own(new THREE.MeshBasicMaterial({ color: 0x111111 })); const l = new THREE.Mesh(lampGeo, m);
    const a = (i / 4) * Math.PI * 2; l.position.set(Math.cos(a) * 1.7, 7.4 + (i % 2) * 0.01, Math.sin(a) * 1.7); mod.add(l); return { m, l };
  });  // expression, response, score, revision
  const barGeo = own(new THREE.BoxGeometry(0.7, 1, 0.7)), barMat = own(new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0.6 }));
  const bar = new THREE.Mesh(barGeo, barMat); bar.position.set(0, 0.6, 2.6); mod.add(bar);  // renewal boost
  const relGeo = own(new THREE.TorusGeometry(2.4, 0.12, 8, 48)), relMat = own(mono(0xffffff, 0.5));
  const rel = new THREE.Mesh(relGeo, relMat); rel.rotation.x = Math.PI / 2; rel.position.y = 2.2; mod.add(rel);  // reliability of the scarcity claims
  // the channel between the arena and the module: a line and a travelling spark
  const chGeo = own(new THREE.BufferGeometry()), chMat = own(new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.18 }));
  const channel = new THREE.Line(chGeo, chMat); channel.frustumCulled = false; channel.visible = false; group.add(channel);
  const sparkGeo = own(new THREE.SphereGeometry(0.5, 10, 8)), sparkMat = own(new THREE.MeshBasicMaterial({ color: 0xffffff }));
  const spark = new THREE.Mesh(sparkGeo, sparkMat); spark.visible = false; group.add(spark);

  const set: DeviceLayer['set'] = (d, o) => {
    // pulse
    pulse.visible = d.pulse.active;
    if (d.pulse.active) {
      const c = o.arenaCell(d.pulse.x, d.pulse.y);
      const k = d.pulse.age / PULSE_TICKS;
      pulse.position.set(c.x, 0.3, c.z); pulse.scale.setScalar(0.6 + 5 * k * (0.4 + Math.min(1.5, d.pulse.amount) * 0.4)); pulseMat.opacity = 0.9 * (1 - k);
    }
    // recovery halo: bright just after a recovery, steady while recovered, a dim ring while collapsed
    const r = d.recovery;
    haloMat.opacity = r.phase === 'recovered' ? (r.age !== null && r.age < 30 ? 0.9 - 0.4 * (r.age / 30) : 0.35) : r.phase === 'collapsed' ? 0.07 : 0;
    // boundary posts: all raised when closed; one post sector per open channel is lowered
    const rr = d.boundary.arenaRadius ?? half * 1.05;
    const lowered = d.boundary.open.length;
    for (let i = 0; i < POSTS; i++) {
      const a = (i / POSTS) * Math.PI * 2;
      const down = lowered > 0 && (i % Math.max(2, Math.floor(POSTS / (lowered * 2)))) < Math.max(1, Math.floor(POSTS / (lowered * 4)));
      const h = d.boundary.closed ? 0.8 : down ? 0.1 : 0.5;
      P.set(Math.cos(a) * rr, h / 2 + 0.05, Math.sin(a) * rr); S.set(1, h, 1);
      posts.setMatrixAt(i, M.compose(P, Q.identity(), S));
    }
    posts.instanceMatrix.needsUpdate = true;
    // chamber ring
    chamberRing.visible = o.selectedTrial !== null && !!o.trialPos[o.selectedTrial];
    if (chamberRing.visible && o.selectedTrial !== null) chamberRing.position.copy(o.trialPos[o.selectedTrial]);
    // the Philosophical module
    mod.visible = d.phil.enabled; channel.visible = d.phil.enabled;
    spark.visible = false;
    if (d.phil.enabled) {
      const lit = (age: number | null, k: number) => (age !== null && age <= DEVICE_EVENT_TICKS ? 1 - age / (DEVICE_EVENT_TICKS + 2) : 0.07 + (age !== null ? 0.1 : 0)) * k;
      const st = [lit(d.phil.expressionAge, 1), d.phil.mode === 'expression' ? 0 : lit(d.phil.responseAge, 1), d.phil.mode === 'expression' ? 0 : lit(d.phil.scoreAge, 1), d.phil.mode === 'revision' ? lit(d.phil.revisionAge, 1) : 0];
      lamps.forEach((l, i) => l.m.color.setScalar(Math.min(1, 0.06 + st[i])));
      bar.scale.y = Math.max(0.05, (d.phil.boost - 1) * 4 + 0.15); bar.position.y = 0.6 + bar.scale.y / 2;
      relMat.opacity = 0.15 + 0.7 * d.phil.reliability;
      const from = o.arenaCell(Math.floor(n / 2), Math.floor(n / 2)).clone().add(arenaGroup.position).setY(2.5), to = bay.clone().setY(7.4);
      chGeo.setFromPoints([from, to]);
      // a spark travels A1 -> module for an expression and module -> arena for a response, over the channel's delay
      const travelling = d.phil.expressionAge !== null && d.phil.expressionAge <= d.phil.channelDelay + 1 ? { k: (d.phil.expressionAge + 0.5) / (d.phil.channelDelay + 2), out: true }
        : d.phil.mode !== 'expression' && d.phil.responseAge !== null && d.phil.responseAge <= d.phil.channelDelay + 1 ? { k: (d.phil.responseAge + 0.5) / (d.phil.channelDelay + 2), out: false } : null;
      if (travelling) { spark.visible = true; spark.position.lerpVectors(travelling.out ? from : to, travelling.out ? to : from, travelling.k); }
    }
  };
  return { group, set, dispose: () => { owned.forEach((x) => x.dispose()); arenaGroup.remove(pulse, halo, posts); } };
}
