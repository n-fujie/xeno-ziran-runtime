// XENO ECOSYSTEM — the adaptive observation node. It is deliberately not a robot arm on a stand and not a humanoid: an irregular low chassis carried on five unequal legs with
// several contacts each (two of them with local suspension), a turret set off the centre, a telescoping boom, a side-mounted optical unit, a sensor head that is not at the end of
// anything, an articulated ring round the boom, a cluster of six retractable micro-probes of different lengths, diameters and tips, and three docked modules of different
// sizes, with their cables running over the limbs in the open.
//
// What it does (bodyState.ts): the turret turns and the boom pitches toward the observed region; the boom extends on a sampled tick and folds back when the run collapses;
// the ring turns once per sampling interval; the probes in the cluster are out in proportion to the share of the arena the observation covers and tremble when it cannot resolve the
// operation; the probe ring is repositioned when the arena boundary changes; the optical unit's lamp is lit while sampling.
import * as THREE from 'three';
import { Frame, Parts, boxAt, cylAt, discAt, perforated, plateThrough, sphere, torusAt, tube, v3 } from './geom';
import { Fasteners, aperture, blankingPlate, hingePin, inspection, lBracket, probeSocket, recessedPort, turnbuckle } from './hardware';
import { buildCables, type CableRoute, type CableSet } from './cables';
import { buildProbe, type Probe, type ProbeSpec } from './probes';
import { asMatKeys, seeded, type BodyMats, type PartInfo } from './ncb';
import { nodeAwake, ringProbeState, type BodyState } from './bodyState';

export const RING_PROBES: ProbeSpec[] = [
  { id: 'O1', length: 2.45, radius: 0.1, tip: 'hollow', insulated: 0.3, retractor: true, strain: true },
  { id: 'O2', length: 1.35, radius: 0.06, tip: 'needle', insulated: 0.2, retractor: true, strain: false },
  { id: 'O3', length: 1.75, radius: 0.075, tip: 'hook', insulated: 0.35, retractor: false, strain: true },
  { id: 'O4', length: 0.8, radius: 0.045, tip: 'bead', insulated: 0.0, retractor: true, strain: false },
  { id: 'O5', length: 2.05, radius: 0.055, tip: 'needle', insulated: 0.4, retractor: false, strain: false },
  { id: 'O6', length: 1.2, radius: 0.085, tip: 'hollow', insulated: 0.15, retractor: true, strain: true },
];
export const BOOM = { sec1: 3.4, sec2: 3.0, sec3: 2.6 };
export const CHASSIS_OUTLINE: Array<[number, number]> = [[-3.2, -1.6], [0.5, -2.6], [3.4, -1.2], [3.0, 1.8], [-0.8, 2.7], [-3.6, 0.9]];
export const CHASSIS_THICKNESS = 0.35;

export interface ObserverBuild {
  group: THREE.Group; yaw: THREE.Group; pitch: THREE.Group; probes: Probe[]; parts: PartInfo[]; cables: CableSet[];
  set(s: BodyState, aimWorld: THREE.Vector3): void; stats: { vertices: number; fasteners: number }; dispose(): void;
}

export function buildObserver(M: BodyMats, detail: number, groundAt: (x: number, z: number) => number): ObserverBuild {
  const owned: Array<{ dispose(): void }> = [];
  const mats = asMatKeys(M), group = new THREE.Group(); group.name = 'observer';
  const info: PartInfo[] = [];
  const cableSets: CableSet[] = [];
  const lod = new THREE.LOD(); group.add(lod);
  let fastCount = 0, vertexCount = 0;
  const H = 1.5;  // chassis height above the ground

  // ---- static part (chassis, legs, modules, cables on limbs), in two levels of detail
  const buildStatic = (lo: boolean): THREE.Group => {
    const g = new THREE.Group(), parts = new Parts(), fast = new Fasteners(), r = seeded(77);
    // chassis plate: perforated, thick, irregular
    const plate = perforated(CHASSIS_OUTLINE, { hole: 0.075, pitch: lo ? 60 : 0.3, margin: 0.35, depth: CHASSIS_THICKNESS, slots: lo ? [] : [[-1.4, 0.2, 0.9, 0.09], [-1.4, 0.45, 0.9, 0.09], [-1.4, 0.7, 0.9, 0.09], [1.6, -0.6, 0.08, 0.8]], seg: lo ? 4 : 8, keepClear: [[0.6, -0.6, 1.0], [-1.2, 2.0, 1.2]] });
    plate.rotateX(-Math.PI / 2); plate.translate(0, H, 0);
    parts.add('gun', plate, 0.4);
    // rim tubes along the outline, with hubs at the corners
    CHASSIS_OUTLINE.forEach(([x, z], i) => {
      const [x2, z2] = CHASSIS_OUTLINE[(i + 1) % CHASSIS_OUTLINE.length];
      parts.add('chrome', tube(v3(x, H + 0.2, z), v3(x2, H + 0.2, z2), 0.09), 0.5); parts.add('chrome', sphere(v3(x, H + 0.2, z), 0.2, lo ? 8 : 14), 0.9);
      if (!lo) fast.edge([v3(x, H + 0.4, z), v3(x2, H + 0.4, z2), v3(x2 * 0.9, H + 0.4, z2 * 0.9), v3(x * 0.9, H + 0.4, z * 0.9)], v3(0, 1, 0), r, { pitch: 0.42, inset: 0.0, lift: 0.0, kinds: ['hex', 'socket', 'exposed'] });
    });
    // the offset body block with hatches and an inspection port
    const bc = v3(-1.2, H + 0.2 + 0.7, 0.6);
    parts.add('gun', boxAt(bc, v3(1, 0, 0), v3(0, 1, 0), v3(0, 0, 1), 2.6, 1.3, 1.8), 0.6);
    if (!lo) {
      const top = new Frame(bc.clone().add(v3(0, 0.66, 0)), v3(1, 0, 0), v3(0, 0, -1), v3(0, 1, 0));
      blankingPlate(parts, fast, top, -0.7, 0.3, 0.7, 0.5, r); inspection(parts, top, 0.5, -0.2, 0.2); recessedPort(parts, top, 0.7, 0.45, 0.22, 2);
      const side = new Frame(bc.clone().add(v3(0, 0, 0.92)), v3(1, 0, 0), v3(0, 1, 0), v3(0, 0, 1));
      for (let k = 0; k < 5; k++) parts.add('dark', boxAt(side.at(-0.7 + k * 0.0, -0.4 + k * 0.17, 0.005), side.ex, side.ey, side.n, 1.0, 0.07, 0.02), 0.4);
      aperture(parts, side, 0.8, 0.3, 0.16); fast.ring(side, 0.8, 0.3, 0.3, 8, r, ['socket', 'hex']);
      for (let k = 0; k < 14; k++) fast.add(k % 4 === 0 ? 'socket' : 'hex', side.at(-1.2 + (k / 13) * 2.4 + (r() - 0.5) * 0.08, 0.6, 0.02), side.n, 0.9);
    }
    // five legs of unequal length and posture: hip, upper segment, knee with a hinge pin, lower segment, a foot of three contacts; two have suspension
    const legs: Array<{ hip: [number, number]; yaw: number; up: number; low: number; knee: number; susp: boolean }> = [
      { hip: [-3.2, -1.6], yaw: 3.9, up: 2.6, low: 3.3, knee: 1.3, susp: true }, { hip: [0.5, -2.6], yaw: 4.9, up: 2.2, low: 3.0, knee: 1.0, susp: false },
      { hip: [3.4, -1.2], yaw: 0.3, up: 3.0, low: 3.7, knee: 1.6, susp: true }, { hip: [3.0, 1.8], yaw: 0.9, up: 2.0, low: 2.7, knee: 0.8, susp: false }, { hip: [-3.6, 0.9], yaw: 2.9, up: 2.4, low: 3.1, knee: 1.1, susp: false },
    ];
    const legRoutes: CableRoute[] = [];
    legs.forEach((L, i) => {
      const hip = v3(L.hip[0], H + 0.05, L.hip[1]), dir = v3(Math.cos(L.yaw), 0, Math.sin(L.yaw));
      const knee = hip.clone().addScaledVector(dir, L.up * 0.8).add(v3(0, L.knee, 0)), footXZ = knee.clone().addScaledVector(dir, L.low * 0.65);
      const gy = groundAt(footXZ.x, footXZ.z), foot = v3(footXZ.x, gy + 0.22, footXZ.z);
      parts.add('chrome', sphere(hip, 0.3, lo ? 8 : 14), 0.95); parts.add('chrome', tube(hip, knee, 0.15, lo ? 6 : 10, 0.17), 0.5);
      parts.add('chrome', sphere(knee, 0.24, lo ? 8 : 14), 0.95); parts.add('chrome', tube(knee, foot, 0.075, lo ? 6 : 10, 0.12), 0.5);
      parts.add('gun', cylAt(foot.clone().add(v3(0, -0.12, 0)), v3(0, 1, 0), 0.3, 0.16, lo ? 8 : 14, 0.22), 0.9);
      if (!lo) {
        hingePin(parts, knee, dir.clone().cross(v3(0, 1, 0)).normalize(), 0.6, 0.06);
        for (const o of [[0.42, 0], [-0.25, 0.36], [-0.25, -0.36]]) { const q = foot.clone().add(v3(o[0], -0.18, o[1])); parts.add('chrome', cylAt(q, v3(0, 1, 0), 0.13, 0.12, 10, 0.07), 0.9); parts.add('chrome', cylAt(q.clone().add(v3(0, -0.1, 0)), v3(0, 1, 0), 0.02, 0.14, 6, 0.01), 0.9); }
        if (L.susp) {  // a damper beside the lower segment and a coil spring round it
          const a = knee.clone().lerp(foot, 0.18).add(v3(0, 0, 0.32)), b = knee.clone().lerp(foot, 0.7).add(v3(0, 0, 0.32));
          parts.add('gun', tube(a, a.clone().lerp(b, 0.55), 0.07), 0.8); parts.add('chrome', tube(a.clone().lerp(b, 0.5), b, 0.035), 0.7);
          const pts: THREE.Vector3[] = [], axis = b.clone().sub(a), len = axis.length(), u = axis.clone().normalize(), s = u.clone().cross(v3(0, 1, 0)).normalize(), w = u.clone().cross(s).normalize();
          for (let k = 0; k <= 46; k++) { const t = k / 46, ang = t * Math.PI * 2 * 9; pts.push(a.clone().addScaledVector(u, len * t).addScaledVector(s, Math.cos(ang) * 0.13).addScaledVector(w, Math.sin(ang) * 0.13)); }
          parts.add('chrome', new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 110, 0.016, 5, false), 0.5);
          turnbuckle(parts, hip.clone().add(v3(0, 0.1, 0.25)), knee.clone().add(v3(0, 0.15, 0.25)), 0.04);
        }
        // exposed cables along the limb
        legRoutes.push({ id: `L${i}`, kind: i % 2 ? 'data' : 'power', points: [hip.clone().add(v3(0.1, 0.2, 0.18)), hip.clone().lerp(knee, 0.5).add(v3(0, 0.3, 0.25)), knee.clone().add(v3(0, 0.2, 0.2)), knee.clone().lerp(foot, 0.5).add(v3(0, 0, 0.22))], radius: 0.035 + (i % 3) * 0.012, sag: 0.1, ends: ['strain', 'anchor'], clamps: [0.3, 0.62, 0.9] });
      }
    });
    // docked modules of different sizes, each on a latch and rail, with a ringed port
    const modules: Array<{ at: THREE.Vector3; size: [number, number, number]; yaw: number }> = [{ at: v3(-3.9, 0.9, -2.4), size: [1.9, 1.15, 1.25], yaw: 0.6 }, { at: v3(1.4, H - 0.75, 0.2), size: [1.1, 0.8, 0.9], yaw: -0.2 }, { at: v3(2.5, H + 0.95, 1.2), size: [1.5, 0.9, 1.0], yaw: 1.1 }];
    modules.forEach((m, i) => {
      const ex = v3(Math.cos(m.yaw), 0, Math.sin(m.yaw)), nz = v3(-Math.sin(m.yaw), 0, Math.cos(m.yaw)), up = v3(0, 1, 0);
      parts.add('gun', boxAt(m.at, ex, up, nz, ...m.size), 0.7); parts.add('dark', boxAt(m.at.clone().add(v3(0, -m.size[1] / 2 - 0.08, 0)), ex, up, nz, m.size[0] * 1.1, 0.12, m.size[2] * 1.15), 0.9);
      if (!lo) {
        const f = new Frame(m.at.clone().addScaledVector(ex, m.size[0] / 2 + 0.01), nz, up, ex);
        probeSocket(parts, f, 0, 0, 0.26); fast.ring(f, 0, 0, 0.42, 8, r, ['socket', 'hex']); lBracket(parts, fast, f.at(0.3, -0.45, 0.04), nz, ex, 0.3, r);
        for (let k = 0; k < 4; k++) fast.add(k % 2 ? 'hex' : 'socket', m.at.clone().addScaledVector(up, m.size[1] / 2 + 0.02).addScaledVector(ex, -m.size[0] * 0.3 + k * m.size[0] * 0.2).addScaledVector(nz, (k % 2 ? 1 : -1) * m.size[2] * 0.3), up, 0.9);
      }
      info.push({ id: `M${i + 1}`, name: `Module M${i + 1}`, kind: 'module', body: 'observer', object: g, params: { width: m.size[0], height: m.size[1], depth: m.size[2] } });
      if (!lo) legRoutes.push({ id: `M${i}`, kind: 'resource', points: [m.at.clone().add(v3(0, m.size[1] / 2, 0)), m.at.clone().lerp(v3(-0.5, H + 0.4, 0.2), 0.5).add(v3(0, 0.5, 0)), v3(-0.5, H + 0.4, 0.2)], radius: 0.05 + i * 0.015, sag: 0.14, ends: ['connector', 'strain'], clamps: [0.45] });
    });
    // the turret base, off the centre
    parts.add('gun', cylAt(v3(0.6, H + 0.55, -0.6), v3(0, 1, 0), 0.95, 0.5, lo ? 12 : 30, 0.85), 0.6); parts.add('chrome', torusAt(v3(0.6, H + 0.82, -0.6), v3(0, 1, 0), 0.9, 0.07, lo ? 14 : 36), 0.7);
    if (!lo) for (let k = 0; k < 16; k++) { const a = (k / 16) * Math.PI * 2 + 0.1; fast.add(k % 3 ? 'hex' : 'captive', v3(0.6 + Math.cos(a) * 0.9, H + 0.84, -0.6 + Math.sin(a) * 0.9), v3(0, 1, 0), 0.9); }
    if (legRoutes.length) {
      const cs = buildCables(legRoutes, { rubber: M.rubber, sleeve: M.sleeve, chrome: M.chrome, gun: M.gun, dark: M.dark }, detail, r);
      g.add(cs.group); owned.push({ dispose: () => cs.dispose() }); if (!lo) cableSets.push(cs);
    }
    parts.flush(g, mats, owned, `observer${lo ? '-lo' : ''}`);
    if (!lo) { fast.build(g, { chrome: M.chrome, gun: M.gun, dark: M.dark }, owned, detail); fastCount = fast.count; vertexCount = parts.vertices; }
    return g;
  };
  lod.addLevel(buildStatic(false), 0); lod.addLevel(buildStatic(true), 75);
  info.push({ id: 'OBS', name: 'Observation node chassis', kind: 'chassis', body: 'observer', object: group, params: { thickness: CHASSIS_THICKNESS, legs: 5, height: H } });

  // ---- turret, boom, sections, ring, optical unit, sensor head, probe cluster
  const yaw = new THREE.Group(); yaw.position.set(0.6, H + 0.85, -0.6); group.add(yaw);
  const pitch = new THREE.Group(); pitch.position.set(0, 0.55, 0); yaw.add(pitch);
  const boomParts = new Parts(), rb = seeded(91);
  const sq = (len: number, w: number, z0: number, parts: Parts, wear = 0.5) => {  // a square section: four rails, cross bracing, collars and perforated side plates
    for (const [x, y] of [[w, w], [-w, w], [w, -w], [-w, -w]]) parts.add('chrome', tube(v3(x, y, z0), v3(x, y, z0 + len), 0.06), wear);
    for (let z = z0; z < z0 + len - 0.2; z += 0.5) {
      parts.add('gun', tube(v3(-w, w, z), v3(w, -w, z + 0.5), 0.028), 0.6);
      parts.add('gun', tube(v3(w, w, z), v3(-w, -w, z + 0.5), 0.028), 0.6);
    }
    for (const z of [z0 + 0.1, z0 + len * 0.5, z0 + len - 0.1]) parts.add('chrome', boxAt(v3(0, 0, z), v3(1, 0, 0), v3(0, 1, 0), v3(0, 0, 1), w * 2.5, w * 2.5, 0.08), 0.9);
    const sidePlate = plateThrough([v3(w * 1.05, -w, z0 + 0.1), v3(w * 1.05, -w, z0 + len - 0.1), v3(w * 1.05, w, z0 + len - 0.1), v3(w * 1.05, w, z0 + 0.1)], { hole: 0.04, pitch: 0.16, margin: 0.1, depth: 0.03, seg: 6 }, 0.95);
    parts.add('gun', sidePlate, 0.4);
  };
  hingePin(boomParts, v3(0, 0, 0), v3(1, 0, 0), 1.2, 0.1);
  sq(BOOM.sec1, 0.36, 0, boomParts);
  // hydraulic ram under the boom, a bracket at each end
  boomParts.add('chrome', tube(v3(0, -0.9, -0.6), v3(0, -0.4, 1.5), 0.1), 0.8); boomParts.add('gun', tube(v3(0, -0.9, -0.6), v3(0, -0.62, 0.5), 0.16), 0.8);
  boomParts.add('chrome', sphere(v3(0, -0.9, -0.6), 0.14), 0.95); boomParts.add('chrome', sphere(v3(0, -0.4, 1.5), 0.12), 0.95);
  turnbuckle(boomParts, v3(0.4, 0.4, 0.2), v3(0.4, 0.4, 2.9), 0.04);
  boomParts.flush(pitch, mats, owned, 'boom1');
  // the sensor head, off the centre line of section 1, and the side-mounted optical unit
  const head = new Parts(), headFast = new Fasteners(), hf = new Frame(v3(-0.78, 0.15, 1.6), v3(0, 0, 1), v3(0, 1, 0), v3(-1, 0, 0));
  head.add('gun', boxAt(v3(-0.78, 0.15, 1.6), v3(1, 0, 0), v3(0, 1, 0), v3(0, 0, 1), 0.7, 0.7, 1.3), 0.7);
  recessedPort(head, hf, 0, 0.1, 0.22, 2); aperture(head, hf, 0.4, -0.18, 0.1); blankingPlate(head, headFast, hf, -0.38, 0.05, 0.3, 0.26, rb); headFast.ring(hf, 0, 0.1, 0.34, 9, rb, ['socket', 'hex']);
  head.add('chrome', tube(v3(-0.4, 0.15, 1.2), v3(-0.78, 0.15, 1.2), 0.07), 0.6);
  head.flush(pitch, mats, owned, 'head'); headFast.build(pitch, { chrome: M.chrome, gun: M.gun, dark: M.dark }, owned, detail);
  const opt = new THREE.Group(); opt.position.set(0.95, -0.15, 0.6); pitch.add(opt);
  const op = new Parts(), of = new Fasteners();
  op.add('gun', cylAt(v3(0, 0, 0.5), v3(0, 0, 1), 0.38, 1.5, 24), 0.7); op.add('gun', cylAt(v3(0, 0, 1.45), v3(0, 0, 1), 0.38, 0.5, 24, 0.62), 0.8);
  op.add('chrome', torusAt(v3(0, 0, 1.7), v3(0, 0, 1), 0.6, 0.06, 28), 0.9); op.add('glass', discAt(v3(0, 0, 1.2), v3(0, 0, 1), 0.34, 24), 0.2);
  op.add('chrome', torusAt(v3(0, 0, 0.95), v3(0, 0, 1), 0.4, 0.04, 22), 0.8); op.add('chrome', torusAt(v3(0, 0, 0.2), v3(0, 0, 1), 0.4, 0.04, 22), 0.8);
  op.add('gun', boxAt(v3(-0.5, 0.1, 0.4), v3(1, 0, 0), v3(0, 1, 0), v3(0, 0, 1), 0.25, 0.7, 0.9), 0.9); hingePin(op, v3(-0.5, 0.1, 0.1), v3(0, 1, 0), 0.9, 0.05);
  op.add('chrome', tube(v3(-0.4, 0.35, 0.35), v3(-0.1, 0.5, 0.9), 0.05), 0.7);
  for (let k = 0; k < 10; k++) { const a = (k / 10) * 6.28; of.add(k % 2 ? 'hex' : 'socket', v3(Math.cos(a) * 0.6, Math.sin(a) * 0.6, 1.73), v3(0, 0, 1), 0.8); }
  op.flush(opt, mats, owned, 'optic'); of.build(opt, { chrome: M.chrome, gun: M.gun, dark: M.dark }, owned, detail);
  const optLamp = new THREE.Mesh(new THREE.SphereGeometry(0.07, 10, 8), M.lampA); optLamp.position.set(0.3, 0.3, 1.0); opt.add(optLamp); owned.push(optLamp.geometry);
  info.push({ id: 'OPT', name: 'Optical unit (side-mounted)', kind: 'optic', body: 'observer', object: opt, params: { length: 1.7, radius: 0.38 } });
  info.push({ id: 'HEAD', name: 'Sensor head (non-central)', kind: 'sensor', body: 'observer', object: pitch, params: { width: 0.7, height: 0.7, depth: 1.3 } });
  // telescoping sections
  const sec2 = new THREE.Group(), sec3 = new THREE.Group(); pitch.add(sec2); sec2.add(sec3);
  const p2 = new Parts(); sq(BOOM.sec2, 0.27, 0, p2, 0.4); p2.flush(sec2, mats, owned, 'boom2');
  const p3 = new Parts(); sq(BOOM.sec3, 0.2, 0, p3, 0.4); p3.add('chrome', cylAt(v3(0, 0, BOOM.sec3), v3(0, 0, 1), 0.32, 0.12, 24), 0.9); p3.flush(sec3, mats, owned, 'boom3');
  info.push({ id: 'BM1', name: 'Boom section 1', kind: 'boom', body: 'observer', object: pitch, params: { length: BOOM.sec1 } }, { id: 'BM2', name: 'Boom section 2', kind: 'boom', body: 'observer', object: sec2, params: { length: BOOM.sec2 } }, { id: 'BM3', name: 'Boom section 3', kind: 'boom', body: 'observer', object: sec3, params: { length: BOOM.sec3 } });
  // the articulated ring round section 2
  const ring = new THREE.Group(); ring.position.set(0, 0, 1.2); sec2.add(ring);
  const rp = new Parts(), rf = new Fasteners();
  rp.add('chrome', torusAt(v3(0, 0, 0), v3(0, 0, 1), 0.62, 0.07, 36), 0.8);
  for (const a of [0.3, 3.5]) { const c = v3(Math.cos(a) * 0.62, Math.sin(a) * 0.62, 0); rp.add('gun', boxAt(c, v3(1, 0, 0), v3(0, 1, 0), v3(0, 0, 1), 0.2, 0.2, 0.26), 0.9); hingePin(rp, c, v3(Math.sin(a), -Math.cos(a), 0), 0.34, 0.035); }
  rp.add('gun', tube(v3(0.62, 0.1, 0), v3(0.35, 0.3, 0.0), 0.04), 0.7); for (let k = 0; k < 18; k++) { const a = (k / 18) * 6.28; rf.add(k % 3 ? 'hex' : 'exposed', v3(Math.cos(a) * 0.62, Math.sin(a) * 0.62, 0.07), v3(0, 0, 1), 0.7); }
  rp.flush(ring, mats, owned, 'ring'); rf.build(ring, { chrome: M.chrome, gun: M.gun, dark: M.dark }, owned, detail);
  info.push({ id: 'RING', name: 'Articulated ring', kind: 'ring', body: 'observer', object: ring, params: { radius: 0.62 } });
  // the probe cluster at the end of section 3, unevenly arranged
  const cluster = new THREE.Group(); cluster.position.set(0, 0, BOOM.sec3 + 0.14); sec3.add(cluster);
  const cp = new Parts(), cf = new Fasteners();
  cp.add('gun', cylAt(v3(0, 0, 0.03), v3(0, 0, 1), 0.75, 0.1, 30), 0.9); cp.add('chrome', torusAt(v3(0, 0, 0.1), v3(0, 0, 1), 0.7, 0.05, 32), 0.9);
  const angles = [0.1, 1.2, 2.2, 3.4, 4.3, 5.4], radii = [0.45, 0.5, 0.38, 0.5, 0.42, 0.34];
  const ringProbes: Probe[] = [];
  RING_PROBES.forEach((ps, i) => {
    const pr = buildProbe(ps, M, detail * 0.8), a = angles[i], rr = radii[i];
    pr.group.position.set(Math.cos(a) * rr, Math.sin(a) * rr, 0.12); pr.group.rotation.x = -Math.PI / 2;  // its axis (-y) points forward along the boom
    pr.group.rotateOnWorldAxis(v3(0, 0, 1), 0); cluster.add(pr.group); ringProbes.push(pr);
    cf.add('hex', v3(Math.cos(a) * (rr + 0.12), Math.sin(a) * (rr + 0.12), 0.1), v3(0, 0, 1), 0.8);
    info.push({ id: ps.id, name: `Probe ${ps.id}`, kind: 'probe', body: 'observer', object: pr.group, params: { length: ps.length, radius: ps.radius, tip: ps.tip } });
  });
  cp.flush(cluster, mats, owned, 'cluster'); cf.build(cluster, { chrome: M.chrome, gun: M.gun, dark: M.dark }, owned, detail);
  info.push({ id: 'CLUSTER', name: 'Probe ring (retractable array)', kind: 'cluster', body: 'observer', object: cluster, params: { probes: RING_PROBES.length } });
  // slack loops bridging the sections: authored for the full extension and stretched along z with the sections
  const loops = buildCables([
    { id: 'W1', kind: 'power', points: [v3(0.3, 0.3, 0.6), v3(0.34, 0.1, BOOM.sec1 * 0.6), v3(0.3, 0.28, BOOM.sec1)], radius: 0.05, sag: 0.2, sleeve: [0.2, 0.8], ends: ['anchor', 'connector'], clamps: [0.2] },
    { id: 'W2', kind: 'data', points: [v3(-0.3, 0.3, 0.6), v3(-0.34, 0.05, BOOM.sec1 * 0.55), v3(-0.3, 0.26, BOOM.sec1 * 0.95)], radius: 0.032, sag: 0.25, ends: ['strain', 'strain'], clamps: [0.15, 0.85] },
  ], { rubber: M.rubber, sleeve: M.sleeve, chrome: M.chrome, gun: M.gun, dark: M.dark }, detail, rb);
  pitch.add(loops.group); owned.push({ dispose: () => loops.dispose() }); cableSets.push(loops);
  info.push(...loops.routes.map((r) => ({ id: `cable.${r.id}`, name: `Cable ${r.id} (${r.kind})`, kind: 'cable', body: 'observer' as const, object: loops.group, params: { radius: r.radius, kind: r.kind } })));

  group.position.y = 0;
  const tmpV = v3(0, 0, 0);
  const set = (s: BodyState, aimWorld: THREE.Vector3) => {
    const awake = nodeAwake(s, 'A');
    group.updateMatrixWorld(true);
    yaw.getWorldPosition(tmpV);
    const to = aimWorld.clone().sub(tmpV), flat = Math.hypot(to.x, to.z), sc = group.scale.x;
    // the turret turns toward the observed region; the boom pitches toward it (a collapsed run folds the boom down)
    yaw.rotation.y = Math.atan2(to.x, to.z) - group.rotation.y;
    const want = Math.atan2(-to.y, Math.max(1, flat)) * 0.9, boundary = s.arenaRadius === null ? 0 : Math.max(-0.5, Math.min(0.5, (s.arenaRadius - 7) * 0.08));
    pitch.rotation.x = s.collapsed ? 0.62 : Math.max(-0.25, Math.min(0.5, want + 0.08));
    const e = s.collapsed ? 0 : !awake ? 0.1 : s.sampling ? 1 : 0.4 + 0.3 * s.coverage;
    // SSS scale preloads the boom: a longer reach extends its sections further (a visual representation rule, see mechanics.ts)
    sec2.position.z = 2.2 + e * 1.3 + 0.35 * s.mech.boomPreload; sec3.position.z = 1.9 + e * 1.0 + 0.25 * s.mech.boomPreload;
    ring.rotation.z = (2 * Math.PI * (s.tick % s.interval)) / s.interval;
    cluster.rotation.z = boundary;  // the probe ring is repositioned when the arena boundary changes
    cluster.rotation.x = s.mech.ringTilt;  // SSS size sets the posture of the probe ring
    const stretch = 0.55 + 0.35 * e; loops.group.scale.z = stretch;
    ringProbes.forEach((p, i) => p.setState(ringProbeState(s, i, ringProbes.length), s.tick));
    M.lampA.emissiveIntensity = awake && s.sampling ? 0.6 + 2.8 * s.coverage : 0.06;
    void sc;
  };
  return { group, yaw, pitch, probes: ringProbes, parts: info, cables: cableSets, set, stats: { vertices: vertexCount, fasteners: fastCount }, dispose: () => { owned.forEach((o) => o.dispose()); ringProbes.forEach((p) => p.dispose()); } };
}
