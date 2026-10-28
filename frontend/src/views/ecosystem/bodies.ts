// XENO ECOSYSTEM — two experimental bodies of the habitat's surface, modelled after the supplied concept renders:
//
//   NON-CENTRAL EXPERIMENTAL BODY   three nodes (observation / processing / resource exchange) on rock, joined by flexible cable bundles through a ring junction
//   ADAPTIVE OBSERVATION NODE       a column with an actuated arm that carries an exchangeable probe, a tripod-borne sensor head and a module dock
//
// Both are built from real geometry rather than textures: perforated plates (extruded shapes with holes), bolted edges, tubular frames with hub spheres and collars,
// ring connectors, cable bundles (tubes along sagging curves) with clamps, lens assemblies and needle probes.
//
// What is architecture and what is data. The geometry is static architecture and says nothing about the model. The parts that move or light up are driven only
// by a ``BodyState``, a pure function of a MEOS record at a tick and of the observation configuration (``bodyState`` below): they are a presentation of the run, with the
// mapping stated here and in the interface. The mapping is a design choice of this view; it does not claim that A1, A2 or the observation are these machines.
//
//   node A  (observation / sensing)   lens lit on the ticks the observation samples, brighter the more of the arena it covers
//   node B  (processing / analysis)   lamp flashes for ticks after an A1 firing
//   node C  (resource / exchange)     probe sparks for ticks after an A2 renewal; node dark while A2 is absent
//   B-C bundle                        a light travels B->C after an A1 firing and C->B after a renewal; the bundle dims and its junction ring parts while the coupling is cut
//   observation node                  arm aims at the observed region, probe lowers on sampled ticks, head lamp lit while sampling
import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { MeosRecord, Observation } from './meosApi';
import { deviceState } from './researchDevice';
import { mulberry } from './terrain';

const v3 = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);

// ---------------------------------------------------------------------------------------------------- pure: what the record says about the bodies
export interface BodyState {
  sampling: boolean; coverage: number; aim: [number, number];
  a1FireAge: number | null; renewAge: number | null; interaction: number; couplingCut: boolean; a2Present: boolean; status: string; recovered: boolean;
}
const lastAge = (rec: MeosRecord, t: number, pick: (e: MeosRecord['events'][number]) => boolean): number | null => {
  for (let i = rec.events.length - 1; i >= 0; i--) { const e = rec.events[i]; if (e.tick <= t && pick(e)) return t - e.tick; }
  return null;
};
export function bodyState(rec: MeosRecord, tick: number, obs: Partial<Observation> | null | undefined): BodyState {
  const t = Math.min(Math.max(0, tick), rec.frames.length - 1), d = deviceState(rec, t, obs), f = rec.frames[t];
  const inter = rec.traces?.interaction_strength;
  return {
    sampling: d.array.sampling, coverage: d.array.coverage, aim: d.array.aim,
    a1FireAge: lastAge(rec, t, (e) => e.kind === 'fire' && e.actor === 'A1'),
    renewAge: lastAge(rec, t, (e) => e.kind === 'act' && e.actor === 'A2' && Number(e.renewed) > 0),
    interaction: inter && inter.length ? inter[Math.min(t, inter.length - 1)] : 0,
    couplingCut: d.boundary.open.some((k) => k === 'interaction' || k === 'feedback'), a2Present: f.A2.present, status: f.status, recovered: d.recovery.phase === 'recovered',
  };
}
export const FLASH_TICKS = 5;

// ---------------------------------------------------------------------------------------------------- reflections
/** A dark studio for reflections: a black room with a few long bright strips and panels, so that polished metal and wet rock show crisp white streaks as in the concept renders. */
export function studioEnvironment(renderer: THREE.WebGLRenderer): THREE.Texture {
  const sc = new THREE.Scene();
  const room = new THREE.Mesh(new THREE.BoxGeometry(80, 40, 80), new THREE.MeshBasicMaterial({ color: 0x030304, side: THREE.BackSide })); sc.add(room);
  const panel = (w: number, h: number, pos: [number, number, number], rot: [number, number, number], k: number) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(k, k, k * 1.05), side: THREE.DoubleSide }));
    m.position.set(...pos); m.rotation.set(...rot); sc.add(m);
  };
  panel(60, 2.2, [0, 19.5, -8], [Math.PI / 2, 0, 0.35], 9); panel(40, 1.6, [-37, 8, 0], [0, Math.PI / 2, 0.1], 6); panel(1.8, 26, [30, 4, -37], [0, 0, 0], 7);
  panel(10, 10, [0, 6, 38], [0, Math.PI, 0], 2.5); panel(22, 1.2, [10, -3, 38], [0, Math.PI, 0.3], 5); panel(16, 16, [0, 19.8, 14], [Math.PI / 2, 0, 0], 1.2);
  const pm = new THREE.PMREMGenerator(renderer), t = pm.fromScene(sc, 0.02).texture;
  pm.dispose();
  sc.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) { m.geometry.dispose(); (m.material as THREE.Material).dispose(); } });
  return t;
}

// ---------------------------------------------------------------------------------------------------- materials
export interface BodyMats {
  chrome: THREE.MeshStandardMaterial; gun: THREE.MeshStandardMaterial; dark: THREE.MeshStandardMaterial; rubber: THREE.MeshStandardMaterial; glass: THREE.MeshPhysicalMaterial;
  lampA: THREE.MeshStandardMaterial; lampB: THREE.MeshStandardMaterial; lampC: THREE.MeshStandardMaterial; spark: THREE.MeshBasicMaterial; pulse: THREE.MeshBasicMaterial;
}
function materials(env: THREE.Texture | null, owned: Array<{ dispose(): void }>): BodyMats {
  const std = (o: THREE.MeshStandardMaterialParameters) => { const m = new THREE.MeshStandardMaterial({ envMap: env, ...o }); owned.push(m); return m; };
  const lamp = () => std({ color: 0x0c0c0e, emissive: 0xffffff, emissiveIntensity: 0, roughness: 0.3, metalness: 0.1 });
  const glass = new THREE.MeshPhysicalMaterial({ color: 0x020203, roughness: 0.04, metalness: 0.1, clearcoat: 1, clearcoatRoughness: 0.03, envMap: env, envMapIntensity: 2.4 });
  const spark = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
  const pulse = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
  owned.push(glass, spark, pulse);
  return {
    chrome: std({ color: 0xcfd3da, metalness: 1, roughness: 0.16, envMapIntensity: 1.6 }),
    gun: std({ color: 0x1b1d21, metalness: 0.95, roughness: 0.27, envMapIntensity: 1.7 }),
    dark: std({ color: 0x0a0b0d, metalness: 0.7, roughness: 0.42, envMapIntensity: 1.1 }),
    rubber: std({ color: 0x08080a, metalness: 0.2, roughness: 0.62, envMapIntensity: 0.8 }),
    glass, lampA: lamp(), lampB: lamp(), lampC: lamp(), spark, pulse,
  };
}

// ---------------------------------------------------------------------------------------------------- geometry helpers
/** A plate of a polygon outline (in its own x-y plane) with a regular pattern of round holes and optional large openings, extruded ``depth`` along +z. */
export function perforated(outline: Array<[number, number]>, o: { hole: number; pitch: number; margin: number; depth: number; big?: Array<[number, number, number]>; seg?: number }): THREE.BufferGeometry {
  const shape = new THREE.Shape(outline.map(([x, y]) => new THREE.Vector2(x, y)));
  const inside = (px: number, py: number, m: number) => {
    // inside the (convex) outline with a margin from every edge
    for (let i = 0; i < outline.length; i++) {
      const [x1, y1] = outline[i], [x2, y2] = outline[(i + 1) % outline.length], ex = x2 - x1, ey = y2 - y1, len = Math.hypot(ex, ey);
      if ((ex * (py - y1) - ey * (px - x1)) / len < m) return false;
    }
    return true;
  };
  const xs = outline.map((p) => p[0]), ys = outline.map((p) => p[1]);
  const big = o.big ?? [];
  const seg = o.seg ?? 10, dy = o.pitch * 0.866;
  let row = 0;
  for (let y = Math.min(...ys); y <= Math.max(...ys); y += dy, row++) {
    for (let x = Math.min(...xs) + (row % 2 ? o.pitch / 2 : 0); x <= Math.max(...xs); x += o.pitch) {
      if (!inside(x, y, o.margin + o.hole)) continue;
      if (big.some(([bx, by, br]) => Math.hypot(x - bx, y - by) < br + o.hole * 2.2)) continue;
      const h = new THREE.Path(); h.absarc(x, y, o.hole, 0, Math.PI * 2, true); shape.holes.push(h);
    }
  }
  for (const [bx, by, br] of big) { const h = new THREE.Path(); h.absarc(bx, by, br, 0, Math.PI * 2, true); shape.holes.push(h); }
  return new THREE.ExtrudeGeometry(shape, { depth: o.depth, bevelEnabled: true, bevelThickness: o.depth * 0.18, bevelSize: o.depth * 0.18, bevelSegments: 1, curveSegments: seg });
}

/** A beam between two points as a cylinder (placed and oriented into a geometry so that batches can be merged). */
function tube(a: THREE.Vector3, b: THREE.Vector3, r: number, seg = 8): THREE.BufferGeometry {
  const len = a.distanceTo(b), g = new THREE.CylinderGeometry(r, r, len, seg, 1);
  g.applyMatrix4(new THREE.Matrix4().compose(a.clone().add(b).multiplyScalar(0.5), new THREE.Quaternion().setFromUnitVectors(v3(0, 1, 0), b.clone().sub(a).normalize()), v3(1, 1, 1)));
  return g;
}
const sphere = (p: THREE.Vector3, r: number, seg = 14) => { const g = new THREE.SphereGeometry(r, seg, Math.max(6, seg - 4)); g.translate(p.x, p.y, p.z); return g; };
const collar = (a: THREE.Vector3, b: THREE.Vector3, r: number, t = 0.5, w = 0.22, seg = 14) => {
  const p = a.clone().lerp(b, t), d = b.clone().sub(a).normalize(), g = new THREE.CylinderGeometry(r, r, w, seg);
  g.applyMatrix4(new THREE.Matrix4().compose(p, new THREE.Quaternion().setFromUnitVectors(v3(0, 1, 0), d), v3(1, 1, 1)));
  return g;
};
const merge = (gs: THREE.BufferGeometry[]): THREE.BufferGeometry | null => {
  const clean = gs.map((g) => { const c = g.index ? g.toNonIndexed() : g; for (const k of Object.keys(c.attributes)) if (!['position', 'normal', 'uv'].includes(k)) c.deleteAttribute(k); return c; });
  const m = mergeGeometries(clean);
  gs.forEach((g) => g.dispose());
  return m;
};

/** A plate through three or four 3-D points: the outline is flattened into the plane of the first three and the extrusion pushed along its normal. */
function plateThrough(pts: THREE.Vector3[], o: Parameters<typeof perforated>[1], inset: number): THREE.BufferGeometry {
  const [p0, p1, p2] = pts, ex = p1.clone().sub(p0).normalize(), n = ex.clone().cross(p2.clone().sub(p0)).normalize(), ey = n.clone().cross(ex);
  const outline = pts.map((p) => [p.clone().sub(p0).dot(ex), p.clone().sub(p0).dot(ey)] as [number, number]);
  const cx = outline.reduce((a, b) => a + b[0], 0) / outline.length, cy = outline.reduce((a, b) => a + b[1], 0) / outline.length;
  const shrunk = outline.map(([x, y]) => [cx + (x - cx) * inset, cy + (y - cy) * inset] as [number, number]);
  const g = perforated(shrunk, { ...o, big: o.big?.map(([dx, dy, r]) => [cx + dx, cy + dy, r] as [number, number, number]) });  // openings are given relative to the plate's centroid
  g.translate(0, 0, -o.depth / 2);
  g.applyMatrix4(new THREE.Matrix4().makeBasis(ex, ey, n).setPosition(p0));
  return g;
}

/** Instanced bolt heads at given points, each facing along ``normal``. */
function bolts(points: Array<[THREE.Vector3, THREE.Vector3]>, r: number, mat: THREE.Material, owned: Array<{ dispose(): void }>): THREE.InstancedMesh | null {
  if (!points.length) return null;
  const geo = new THREE.CylinderGeometry(r, r * 1.05, r * 0.9, 8);
  const m = new THREE.InstancedMesh(geo, mat, points.length), M = new THREE.Matrix4(), Q = new THREE.Quaternion();
  points.forEach(([p, n], i) => { Q.setFromUnitVectors(v3(0, 1, 0), n); m.setMatrixAt(i, M.compose(p, Q, v3(1, 1, 1))); });
  m.instanceMatrix.needsUpdate = true; m.frustumCulled = false;
  owned.push(geo);
  return m;
}

/** Bolt positions along the inside of a plate's outline. */
function edgeBolts(pts: THREE.Vector3[], pitch: number, inset: number, lift: number): Array<[THREE.Vector3, THREE.Vector3]> {
  const [p0, p1, p2] = pts, n = p1.clone().sub(p0).cross(p2.clone().sub(p0)).normalize(), c = pts.reduce((a, p) => a.add(p), v3(0, 0, 0)).multiplyScalar(1 / pts.length), out: Array<[THREE.Vector3, THREE.Vector3]> = [];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length], len = a.distanceTo(b), k = Math.max(2, Math.round(len / pitch));
    for (let j = 0; j < k; j++) {
      const p = a.clone().lerp(b, (j + 0.5) / k), toC = c.clone().sub(p).normalize().multiplyScalar(inset);
      for (const side of [1, -1]) out.push([p.clone().add(toC).addScaledVector(n, side * lift), n.clone().multiplyScalar(side)]);
    }
  }
  return out;
}

/** A point toward the opposite edge of a quad face: at fraction u along the top edge (face[3] -> face[2]). */
const q3 = (face: THREE.Vector3[], u: number) => face[3].clone().lerp(face[2], u);

// ---------------------------------------------------------------------------------------------------- one node (a truncated triangular pyramid frame)
interface NodeSpec { r0: number; r1: number; h: number; window: boolean; legs: boolean }
interface NodeParts { group: THREE.Group; lens?: THREE.Mesh; lamp: THREE.Mesh; probe: THREE.Group; probeTip: THREE.Mesh; rim: THREE.Mesh | null }
function buildNode(spec: NodeSpec, M: BodyMats, detail: number, R: () => number, owned: Array<{ dispose(): void }>, lampMat: THREE.MeshStandardMaterial): NodeParts {
  const group = new THREE.Group();
  const B = [0, 1, 2].map((i) => { const a = (i / 3) * Math.PI * 2 + 0.3; return v3(Math.cos(a) * spec.r0, 0, Math.sin(a) * spec.r0); });
  const T = [0, 1, 2].map((i) => { const a = (i / 3) * Math.PI * 2 + 0.3; return v3(Math.cos(a) * spec.r1, spec.h, Math.sin(a) * spec.r1); });
  const ports: THREE.BufferGeometry[] = [], greeb: THREE.BufferGeometry[] = [];
  const plates: THREE.BufferGeometry[] = [], frame: THREE.BufferGeometry[] = [], hubs: THREE.BufferGeometry[] = [], boltPts: Array<[THREE.Vector3, THREE.Vector3]> = [];
  const hole = 0.07 - 0.015 * detail, pitch = hole * 2.9;  // a higher tier has smaller, more numerous holes
  for (let i = 0; i < 3; i++) {
    const j = (i + 1) % 3, face = [B[i], B[j], T[j], T[i]];
    const win = spec.window && i === 0;
    const rr = Math.min(spec.h * 0.3, spec.r0 * 0.42), sl = face[0].distanceTo(face[3]);
    const big: Array<[number, number, number]> = win ? [[0, 0, rr]] : [[0, sl * 0.17, rr * 0.5], [0, -sl * 0.2, rr * 0.38]];
    if (!win) {  // ported openings on the plain faces, each with a chrome collar
      const [q0, q1, q2] = face, ex = q1.clone().sub(q0).normalize(), nn = ex.clone().cross(q2.clone().sub(q0)).normalize(), ey = nn.clone().cross(ex);
      const cc = face.reduce((a, b) => a.add(b), v3(0, 0, 0)).multiplyScalar(0.25), out = nn.dot(v3(cc.x, 0, cc.z)) < 0 ? -1 : 1;
      for (const [, dy, r] of big) { const c = cc.clone().addScaledVector(ey, dy).addScaledVector(nn, 0.05 * out); const t = new THREE.TorusGeometry(r * 1.12, 0.045, 8, 28); t.applyMatrix4(new THREE.Matrix4().makeBasis(ex, ey, nn).setPosition(c)); ports.push(t); }
      // greebles: small blocks and caps scattered over the face
      for (let k = 0; k < 44 * detail; k++) {
        const u = 0.12 + R() * 0.76, w = 0.1 + R() * 0.8, pnt = q0.clone().lerp(q1, u).lerp(q3(face, u), w);
        const bx = new THREE.BoxGeometry(0.06 + R() * 0.16, 0.06 + R() * 0.14, 0.04 + R() * 0.09); bx.applyMatrix4(new THREE.Matrix4().makeBasis(ex, ey, nn).setPosition(pnt.addScaledVector(nn, 0.07 * out)));
        greeb.push(bx);
      }
    }
    plates.push(plateThrough(face, { hole, pitch, margin: 0.2, depth: 0.09, big, seg: detail > 0.6 ? 10 : 6 }, 0.94));
    boltPts.push(...edgeBolts(face.map((p) => p.clone().lerp(v3(0, spec.h / 2, 0), 0.035)), 0.2 / Math.max(0.5, detail), 0.11, 0.05));
  }
  for (let i = 0; i < 3; i++) {
    const j = (i + 1) % 3;
    frame.push(tube(B[i], B[j], 0.07), tube(T[i], T[j], 0.07), tube(B[i], T[i], 0.085), tube(B[i], T[j], 0.04));
    hubs.push(sphere(B[i], 0.17), sphere(T[i], 0.15), collar(B[i], T[i], 0.115, 0.3), collar(B[i], T[i], 0.115, 0.75));
  }
  const mp = merge(plates), mf = merge(frame), mh = merge(hubs);
  const add = (g: THREE.BufferGeometry | null, mat: THREE.Material) => { if (!g) return; const m = new THREE.Mesh(g, mat); group.add(m); owned.push(g); return m; };
  add(mp, M.gun); add(mf, M.chrome); add(mh, M.chrome); add(merge(ports), M.chrome); add(merge(greeb), M.gun);
  const bm = bolts(boltPts, 0.034, M.chrome, owned); if (bm) group.add(bm);
  // the top hub: a short drum, a ring and a lamp
  const topC = v3(0, spec.h, 0);
  const drum = new THREE.Mesh(new THREE.CylinderGeometry(spec.r1 * 0.82, spec.r1 * 0.95, 0.34, 30), M.gun); drum.position.copy(topC); group.add(drum); owned.push(drum.geometry);
  const drumRing = new THREE.Mesh(new THREE.TorusGeometry(spec.r1 * 0.9, 0.055, 8, 40), M.chrome); drumRing.rotation.x = Math.PI / 2; drumRing.position.copy(topC).add(v3(0, 0.18, 0)); group.add(drumRing); owned.push(drumRing.geometry);
  const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.17, 14, 10), lampMat); lamp.position.copy(topC).add(v3(0, 0.46, 0)); group.add(lamp); owned.push(lamp.geometry);
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.07, 0.7, 10), M.chrome); mast.position.copy(topC).add(v3(0, 0.3, 0)); group.add(mast); owned.push(mast.geometry);
  // the lens assembly in the window face: a chrome ring, nested rings and a dark glass disc
  let lens: THREE.Mesh | undefined;
  if (spec.window) {
    const mid = B[0].clone().add(B[1]).add(T[0]).add(T[1]).multiplyScalar(0.25), rad = Math.min(spec.h * 0.3, spec.r0 * 0.42);
    const nrm = B[1].clone().sub(B[0]).cross(T[0].clone().sub(B[0])).normalize();
    if (nrm.dot(v3(mid.x, 0, mid.z)) < 0) nrm.negate();
    const win = new THREE.Group(); win.position.copy(mid); win.lookAt(mid.clone().add(nrm)); group.add(win);
    const mk = (g: THREE.BufferGeometry, m: THREE.Material, z: number) => { const x = new THREE.Mesh(g, m); x.position.z = z; win.add(x); owned.push(g); return x; };
    mk(new THREE.TorusGeometry(rad * 1.02, 0.07, 10, 48), M.chrome, 0.02);
    mk(new THREE.TorusGeometry(rad * 0.82, 0.05, 10, 48), M.gun, 0.0);
    mk(new THREE.TorusGeometry(rad * 0.6, 0.05, 10, 40), M.chrome, -0.04);
    lens = mk(new THREE.CircleGeometry(rad * 0.58, 40), M.glass, -0.07);
    mk(new THREE.CircleGeometry(rad * 0.22, 28), lampMat, -0.06);
    for (let k = 0; k < 10; k++) { const a = (k / 10) * Math.PI * 2, b = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.06, 8), M.chrome); b.rotation.x = Math.PI / 2; b.position.set(Math.cos(a) * rad * 1.02, Math.sin(a) * rad * 1.02, 0.1); win.add(b); owned.push(b.geometry); }
  }
  // the probe under the node: a collar, a tapering needle and a lit tip
  const probe = new THREE.Group(); probe.position.set(0, 0.05, 0); group.add(probe);
  const sleeve = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.24, 0.5, 18), M.chrome); sleeve.position.y = -0.1; probe.add(sleeve); owned.push(sleeve.geometry);
  const needle = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.12, 1.5, 12), M.chrome); needle.position.y = -1.0; probe.add(needle); owned.push(needle.geometry);
  const probeTip = new THREE.Mesh(new THREE.SphereGeometry(0.07, 10, 8), M.spark.clone()); probeTip.position.y = -1.78; probe.add(probeTip); owned.push(probeTip.geometry);
  // mechanical detail: a mid band of tubes, outer standoff ribs, bolt circles at the hubs, actuators from the top drum to the base edges, and sensor pods on the vertices
  const mid = [0, 1, 2].map((i) => B[i].clone().lerp(T[i], 0.5).multiplyScalar(1.07).setY(spec.h * 0.5));
  const detailG: THREE.BufferGeometry[] = [], detailH: THREE.BufferGeometry[] = [], detailD: THREE.BufferGeometry[] = [], hubBolts: Array<[THREE.Vector3, THREE.Vector3]> = [];
  for (let i = 0; i < 3; i++) {
    const j = (i + 1) % 3;
    detailG.push(tube(mid[i], mid[j], 0.06), tube(mid[i], B[i].clone().multiplyScalar(1.02), 0.04), tube(mid[i], T[i].clone().multiplyScalar(1.02), 0.04));
    detailH.push(sphere(mid[i], 0.13), collar(mid[i], mid[j], 0.1, 0.5, 0.2));
    // outer ribs: a chevron standing off each face
    const fb = B[i].clone().lerp(B[j], 0.5), ft = T[i].clone().lerp(T[j], 0.5), out = fb.clone().setY(0).normalize().multiplyScalar(0.1);
    detailG.push(tube(fb.clone().add(out), ft.clone().add(out), 0.035), tube(B[i].clone().add(out), ft.clone().add(out), 0.03), tube(B[j].clone().add(out), ft.clone().add(out), 0.03));
    // actuator: a sleeve and a rod from the top drum to the middle of the base edge
    const a = v3(Math.cos(((i + 0.5) / 3) * Math.PI * 2 + 0.3) * spec.r1 * 0.5, spec.h - 0.2, Math.sin(((i + 0.5) / 3) * Math.PI * 2 + 0.3) * spec.r1 * 0.5);
    const b2 = fb.clone().multiplyScalar(0.72).setY(0.35), m2 = a.clone().lerp(b2, 0.42);
    detailD.push(tube(a, m2, 0.085), tube(m2, b2, 0.045), sphere(a, 0.1), sphere(b2, 0.09));
    // bolt circles at the base hubs and a pod at the top vertex
    for (let k = 0; k < 9; k++) { const t = (k / 9) * Math.PI * 2, o = v3(Math.cos(t) * 0.21, 0, Math.sin(t) * 0.21).add(B[i]); hubBolts.push([o.add(v3(0, 0.12, 0)), v3(0, 1, 0)]); }
    const pod = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.3, 20), M.gun), pc = T[i].clone().multiplyScalar(1.28).setY(spec.h - 0.15);
    pod.position.copy(pc); pod.rotation.z = Math.PI / 2; pod.lookAt(pc.clone().add(T[i].clone().setY(0))); pod.rotateX(Math.PI / 2); group.add(pod); owned.push(pod.geometry);
    const podPort = new THREE.Mesh(new THREE.CircleGeometry(0.14, 18), M.glass); podPort.position.copy(pc).add(T[i].clone().setY(0).normalize().multiplyScalar(0.16)); podPort.lookAt(podPort.position.clone().add(T[i].clone().setY(0))); group.add(podPort); owned.push(podPort.geometry);
    detailG.push(tube(T[i], pc, 0.05));
  }
  add(merge(detailG), M.chrome); add(merge(detailH), M.chrome); add(merge(detailD), M.gun);
  const hb = bolts(hubBolts, 0.028, M.chrome, owned); if (hb) group.add(hb);
  // feet
  if (spec.legs) for (let i = 0; i < 3; i++) {
    const foot = tube(B[i].clone().add(v3(0, 0.05, 0)), B[i].clone().multiplyScalar(1.25).add(v3(0, -0.4, 0)), 0.08), pad = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.26, 0.12, 14), M.gun);
    pad.position.copy(B[i]).multiplyScalar(1.25).add(v3(0, -0.45, 0)); group.add(pad); owned.push(pad.geometry);
    const f = new THREE.Mesh(foot, M.chrome); group.add(f); owned.push(foot);
  }
  void R;
  return { group, lens, lamp, probe, probeTip, rim: null };
}

// ---------------------------------------------------------------------------------------------------- cables
interface Cable { curve: THREE.CatmullRomCurve3; mesh: THREE.Mesh; clamps: THREE.InstancedMesh }
function cableBundle(a: THREE.Vector3, b: THREE.Vector3, via: THREE.Vector3[], sag: number, strands: number, M: BodyMats, detail: number, owned: Array<{ dispose(): void }>): Cable {
  const mid = a.clone().lerp(b, 0.5).add(v3(0, -sag, 0));
  const curve = new THREE.CatmullRomCurve3([a, ...via, mid, b], false, 'catmullrom', 0.5);
  const gs: THREE.BufferGeometry[] = [];
  for (let s = 0; s < strands; s++) {
    const ang = (s / Math.max(1, strands - 1)) * Math.PI * 2, off = s === 0 ? v3(0, 0, 0) : v3(Math.cos(ang) * 0.13, Math.sin(ang) * 0.13, 0);
    const c = new THREE.CatmullRomCurve3(curve.points.map((p) => p.clone().add(off)), false, 'catmullrom', 0.5);
    gs.push(new THREE.TubeGeometry(c, Math.max(14, Math.round(44 * detail)), 0.042, 6, false));
  }
  const g = merge(gs)!;
  const mesh = new THREE.Mesh(g, M.rubber); owned.push(g);
  const clampGeo = new THREE.CylinderGeometry(0.17, 0.17, 0.2, 14), n = 6;
  const clamps = new THREE.InstancedMesh(clampGeo, M.chrome, n), Mx = new THREE.Matrix4(), Q = new THREE.Quaternion();
  for (let i = 0; i < n; i++) {
    const u = (i + 0.7) / (n + 0.4), p = curve.getPoint(u), t = curve.getTangent(u);
    clamps.setMatrixAt(i, Mx.compose(p, Q.setFromUnitVectors(v3(0, 1, 0), t), v3(1, 1, 1)));
  }
  clamps.instanceMatrix.needsUpdate = true; clamps.frustumCulled = false;
  owned.push(clampGeo);
  return { curve, mesh, clamps };
}

// ---------------------------------------------------------------------------------------------------- the non-central experimental body
export interface BodySet {
  group: THREE.Group; ncbCentre: THREE.Vector3; observerCentre: THREE.Vector3; set(s: BodyState, aimWorld: THREE.Vector3): void; dispose(): void;
}
export const NCB_AT = v3(-104, 0, 4), OBSERVER_AT = v3(-86, 0, 36);

export function buildBodies(quality: 'performance' | 'balanced' | 'high', env: THREE.Texture | null, groundAt: (x: number, z: number) => number): BodySet {
  const detail = quality === 'performance' ? 0.4 : quality === 'balanced' ? 0.75 : 1;
  const owned: Array<{ dispose(): void }> = [];
  const M = materials(env, owned), R = mulberry(3);
  const group = new THREE.Group(); group.name = 'experimental-bodies';

  // ---- non-central body
  const ncb = new THREE.Group(); ncb.position.set(NCB_AT.x, groundAt(NCB_AT.x, NCB_AT.z), NCB_AT.z); ncb.rotation.y = 0.35; group.add(ncb);
  const spots: Record<'A' | 'B' | 'C', THREE.Vector3> = { A: v3(0, 5.6, -8.5), B: v3(-10, 1.0, 5.5), C: v3(10, 1.0, 5.5) };
  const nodeA = buildNode({ r0: 2.4, r1: 1.2, h: 3.8, window: true, legs: false }, M, detail, R, owned, M.lampA);
  const nodeB = buildNode({ r0: 2.2, r1: 1.2, h: 3.4, window: true, legs: true }, M, detail, R, owned, M.lampB);
  const nodeC = buildNode({ r0: 2.2, r1: 1.1, h: 3.4, window: false, legs: true }, M, detail, R, owned, M.lampC);
  nodeA.group.position.copy(spots.A); nodeB.group.position.copy(spots.B); nodeC.group.position.copy(spots.C);
  nodeB.group.rotation.y = 2.3; nodeC.group.rotation.y = -0.9; nodeA.group.rotation.y = 0.2;
  ncb.add(nodeA.group, nodeB.group, nodeC.group);
  // node A stands on a splayed tripod of struts
  const legs: THREE.BufferGeometry[] = [], legHubs: THREE.BufferGeometry[] = [];
  for (let i = 0; i < 3; i++) {
    const a = (i / 3) * Math.PI * 2 + 0.9, foot = spots.A.clone().add(v3(Math.cos(a) * 4.4, -spots.A.y, Math.sin(a) * 4.4)), top = spots.A.clone().add(v3(Math.cos(a) * 1.3, -0.1, Math.sin(a) * 1.3)), knee = top.clone().lerp(foot, 0.5).add(v3(Math.cos(a) * 0.7, 0.2, Math.sin(a) * 0.7));
    legs.push(tube(top, knee, 0.15), tube(knee, foot, 0.13), tube(top.clone().lerp(knee, 0.5), foot.clone().lerp(knee, 0.5).add(v3(-Math.sin(a) * 1.5, 0, Math.cos(a) * 1.5)), 0.05));
    legHubs.push(sphere(knee, 0.27), sphere(top, 0.22), collar(top, knee, 0.2, 0.5, 0.34), collar(knee, foot, 0.18, 0.4, 0.3));
    const pad = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.62, 0.2, 18), M.gun); pad.position.copy(foot).add(v3(0, 0.1, 0)); ncb.add(pad); owned.push(pad.geometry);
  }
  const lg = merge(legs), lh = merge(legHubs);
  if (lg) { ncb.add(new THREE.Mesh(lg, M.gun)); owned.push(lg); } if (lh) { ncb.add(new THREE.Mesh(lh, M.chrome)); owned.push(lh); }
  // the ring junction on a post, in the middle
  const junctionAt = v3(0, 3.1, 0.5);
  const post = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.4, junctionAt.y, 14), M.gun); post.position.set(junctionAt.x, junctionAt.y / 2, junctionAt.z); ncb.add(post); owned.push(post.geometry);
  const jr: THREE.Mesh[] = [];
  for (const [R0, r0, z, mat] of [[0.95, 0.12, 0, M.chrome], [0.7, 0.08, 0.14, M.gun], [0.7, 0.08, -0.14, M.gun]] as const) {
    const t = new THREE.Mesh(new THREE.TorusGeometry(R0, r0, 12, 40), mat); t.position.copy(junctionAt).add(v3(0, 0, z)); ncb.add(t); owned.push(t.geometry); jr.push(t);
  }
  const hubDisc = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 0.3, 28), M.dark); hubDisc.rotation.x = Math.PI / 2; hubDisc.position.copy(junctionAt); ncb.add(hubDisc); owned.push(hubDisc.geometry);
  // cable bundles: A -> junction, junction -> B, junction -> C, and the low B -> C bundle (the coupling)
  const cs = (p: THREE.Vector3, dy: number) => p.clone().add(v3(0, dy, 0));
  const cabAJ = cableBundle(cs(spots.A, 1.2), junctionAt.clone().add(v3(0, 0.1, -0.4)), [], 1.2, 7, M, detail, owned);
  const cabJB = cableBundle(junctionAt.clone().add(v3(-0.8, 0.1, 0.2)), cs(spots.B, 3.0), [junctionAt.clone().add(v3(-2.6, -0.6, 0.6))], 0.9, 7, M, detail, owned);
  const cabJC = cableBundle(junctionAt.clone().add(v3(0.8, 0.1, 0.2)), cs(spots.C, 3.0), [junctionAt.clone().add(v3(2.6, -0.6, 0.6))], 0.9, 7, M, detail, owned);
  const cabBC = cableBundle(cs(spots.B, 0.7).add(v3(2.2, 0, 1)), cs(spots.C, 0.7).add(v3(-2.2, 0, 1)), [v3(-4, 0.5, 4.6), v3(4, 0.5, 4.6)], 0.2, 8, M, detail, owned);
  for (const c of [cabAJ, cabJB, cabJC, cabBC]) ncb.add(c.mesh, c.clamps);
  // travelling lights on the bundles
  const spk = new THREE.SphereGeometry(0.2, 10, 8); owned.push(spk);
  const mkPulse = () => { const m = new THREE.Mesh(spk, M.pulse.clone()); m.visible = false; ncb.add(m); owned.push(m.material as THREE.Material); return m; };
  const pBC = mkPulse(), pCB = mkPulse(), pAJ = mkPulse(), pJB = mkPulse();
  const sparkA = new THREE.Mesh(new THREE.SphereGeometry(0.55, 12, 10), M.spark.clone()); sparkA.visible = false; nodeC.group.add(sparkA); owned.push(sparkA.geometry, sparkA.material as THREE.Material);
  sparkA.position.set(0, -1.85, 0);

  // ---- adaptive observation node
  const obs = new THREE.Group(); obs.position.set(OBSERVER_AT.x, groundAt(OBSERVER_AT.x, OBSERVER_AT.z), OBSERVER_AT.z); obs.rotation.y = -0.4; obs.scale.setScalar(1.3); group.add(obs);
  const colH = 9.4;
  // base plinth, column drums with collars, bolted flanges
  const colParts: THREE.BufferGeometry[] = [], colDark: THREE.BufferGeometry[] = [];
  const cyl = (r: number, h: number, y: number, seg = 28, rt = r) => { const g = new THREE.CylinderGeometry(rt, r, h, seg); g.translate(0, y, 0); return g; };
  colParts.push(cyl(1.5, 0.5, 0.25, 36), cyl(1.15, 0.45, 0.72, 32));
  for (let i = 0; i < 4; i++) { const y = 1.5 + i * 1.95; colDark.push(cyl(0.78, 1.55, y, 28)); colParts.push(cyl(0.98, 0.26, y - 0.9, 32), cyl(0.98, 0.26, y + 0.9, 32)); }
  colParts.push(cyl(1.05, 0.4, colH - 0.3, 32), cyl(0.5, 0.9, colH + 0.3, 20));
  const cp = merge(colParts), cd = merge(colDark);
  if (cp) { obs.add(new THREE.Mesh(cp, M.chrome)); owned.push(cp); } if (cd) { obs.add(new THREE.Mesh(cd, M.gun)); owned.push(cd); }
  const flangeBolts: Array<[THREE.Vector3, THREE.Vector3]> = [];
  for (let i = 0; i < 4; i++) for (const y of [1.5 + i * 1.95 - 0.9, 1.5 + i * 1.95 + 0.9]) for (let k = 0; k < 14; k++) { const a = (k / 14) * Math.PI * 2; flangeBolts.push([v3(Math.cos(a) * 0.98, y + 0.14, Math.sin(a) * 0.98), v3(0, 1, 0)]); }
  const fb = bolts(flangeBolts, 0.05, M.gun, owned); if (fb) obs.add(fb);
  // a vertical conduit and clamps beside the column
  const cond = tube(v3(1.15, 0.8, 0.3), v3(1.15, colH - 0.5, 0.3), 0.07); const condM = new THREE.Mesh(cond, M.rubber); obs.add(condM); owned.push(cond);
  // the arm: yaw pivot at the column head, shoulder, upper arm, elbow, forearm, wrist, probe carrier
  const yaw = new THREE.Group(); yaw.position.set(0, colH + 0.9, 0); obs.add(yaw);
  const shoulder = new THREE.Group(); yaw.add(shoulder);
  const hubS = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 1.5, 26), M.gun); hubS.rotation.z = Math.PI / 2; shoulder.add(hubS); owned.push(hubS.geometry);
  const L1 = 6.2, L2 = 5.6;
  const armSeg = (len: number, w: number): THREE.Group => {
    const g = new THREE.Group(), parts: THREE.BufferGeometry[] = [], rails: THREE.BufferGeometry[] = [];
    for (const [x, y] of [[w, w], [-w, w], [w, -w], [-w, -w]]) rails.push(tube(v3(x, y, 0.2), v3(x, y, len), 0.07));
    for (let z = 0.2; z < len - 0.4; z += 0.7) { parts.push(tube(v3(-w, w, z), v3(w, -w, z + 0.7), 0.035), tube(v3(w, w, z), v3(-w, -w, z + 0.7), 0.035), tube(v3(-w, w, z), v3(w, w, z), 0.035), tube(v3(-w, -w, z), v3(w, -w, z), 0.035)); }
    const mr = merge(rails), mpz = merge(parts);
    if (mr) { g.add(new THREE.Mesh(mr, M.chrome)); owned.push(mr); } if (mpz) { g.add(new THREE.Mesh(mpz, M.gun)); owned.push(mpz); }
    const box = new THREE.Mesh(new THREE.BoxGeometry(w * 2.6, w * 2.6, 0.7), M.gun); box.position.z = 0.35; g.add(box); owned.push(box.geometry);
    return g;
  };
  const upper = armSeg(L1, 0.55); shoulder.add(upper);
  const elbow = new THREE.Group(); elbow.position.z = L1; shoulder.add(elbow);
  const hubE = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 1.2, 24), M.chrome); hubE.rotation.z = Math.PI / 2; elbow.add(hubE); owned.push(hubE.geometry);
  const fore = armSeg(L2, 0.45); elbow.add(fore);
  // cable loops along the arm and a hydraulic ram from the column head to the upper arm
  for (const [side, sag] of [[0.62, 0.7], [-0.62, 0.9]] as const) {
    const c1 = new THREE.CatmullRomCurve3([v3(side, 0.3, 0.4), v3(side * 1.4, 0.9 + sag * 0.3, L1 * 0.3), v3(side * 1.3, 0.2 - sag * 0.6, L1 * 0.62), v3(side * 0.9, 0.1, L1 - 0.2)]);
    const tg = new THREE.TubeGeometry(c1, 36, 0.06, 8, false), mc = new THREE.Mesh(tg, M.rubber); shoulder.add(mc); owned.push(tg);
  }
  const ram = tube(v3(0, -1.2, -0.4), v3(0, 0.1, L1 * 0.45), 0.13), ramM = new THREE.Mesh(ram, M.chrome); shoulder.add(ramM); owned.push(ram);
  const ram2 = tube(v3(0, -1.2, -0.4), v3(0, -0.35, L1 * 0.22), 0.2), ramM2 = new THREE.Mesh(ram2, M.gun); shoulder.add(ramM2); owned.push(ram2);
  const wrist = new THREE.Group(); wrist.position.z = L2; elbow.add(wrist);
  const head = new THREE.Mesh(new THREE.BoxGeometry(1.5, 1.5, 1.7), M.gun); head.position.z = 0.7; wrist.add(head); owned.push(head.geometry);
  const headPort = new THREE.Mesh(new THREE.CylinderGeometry(0.46, 0.46, 0.2, 28), M.glass); headPort.rotation.x = Math.PI / 2; headPort.position.set(0, 0, 1.6); wrist.add(headPort); owned.push(headPort.geometry);
  const headRing = new THREE.Mesh(new THREE.TorusGeometry(0.6, 0.07, 10, 36), M.chrome); headRing.position.z = 1.58; wrist.add(headRing); owned.push(headRing.geometry);
  const headLamp = new THREE.Mesh(new THREE.SphereGeometry(0.16, 12, 8), M.lampA); headLamp.position.set(0.55, 0.55, 1.62); wrist.add(headLamp); owned.push(headLamp.geometry);
  const carrier = new THREE.Group(); carrier.position.set(0, -0.95, 0.7); wrist.add(carrier);
  const sleeve2 = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.32, 1.0, 20), M.chrome); sleeve2.position.y = -0.1; carrier.add(sleeve2); owned.push(sleeve2.geometry);
  const probeNeedle = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.17, 2.6, 14), M.chrome); probeNeedle.position.y = -1.5; carrier.add(probeNeedle); owned.push(probeNeedle.geometry);
  const probeTip2 = new THREE.Mesh(new THREE.SphereGeometry(0.09, 10, 8), M.spark.clone()); probeTip2.position.y = -2.85; carrier.add(probeTip2); owned.push(probeTip2.geometry);
  // tripod with a sensor head
  const tri = new THREE.Group(); tri.position.set(5.6, 0, 1.6); obs.add(tri);
  const tripod: THREE.BufferGeometry[] = [], tHubs: THREE.BufferGeometry[] = [];
  const headY = 5.2;
  for (let i = 0; i < 3; i++) {
    const a = (i / 3) * Math.PI * 2 + 0.4, foot = v3(Math.cos(a) * 3.0, 0, Math.sin(a) * 3.0), top = v3(Math.cos(a) * 0.35, headY - 0.3, Math.sin(a) * 0.35), knee = top.clone().lerp(foot, 0.55).add(v3(Math.cos(a) * 0.35, 0, Math.sin(a) * 0.35));
    tripod.push(tube(top, knee, 0.1), tube(knee, foot, 0.085)); tHubs.push(sphere(knee, 0.2), sphere(top, 0.17), collar(top, knee, 0.14, 0.45, 0.26), collar(knee, foot, 0.12, 0.5, 0.22));
    const pad = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.34, 0.14, 14), M.gun); pad.position.copy(foot).add(v3(0, 0.07, 0)); tri.add(pad); owned.push(pad.geometry);
  }
  const tg = merge(tripod), th = merge(tHubs);
  if (tg) { tri.add(new THREE.Mesh(tg, M.gun)); owned.push(tg); } if (th) { tri.add(new THREE.Mesh(th, M.chrome)); owned.push(th); }
  const tHead = new THREE.Mesh(new THREE.BoxGeometry(1.5, 1.3, 1.5), M.gun); tHead.position.y = headY + 0.3; tri.add(tHead); owned.push(tHead.geometry);
  const tLens = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 0.2, 28), M.glass); tLens.rotation.z = Math.PI / 2; tLens.position.set(-0.78, headY + 0.3, 0); tri.add(tLens); owned.push(tLens.geometry);
  const tRing = new THREE.Mesh(new THREE.TorusGeometry(0.58, 0.07, 10, 36), M.chrome); tRing.rotation.y = Math.PI / 2; tRing.position.set(-0.78, headY + 0.3, 0); tri.add(tRing); owned.push(tRing.geometry);
  tri.rotation.y = 0.8;
  // the module dock: sensor modules lying on a rail
  const dock = new THREE.Group(); dock.position.set(-2.4, 0, 5.5); obs.add(dock);
  for (let i = 0; i < 3; i++) {
    const m = new THREE.Group(); m.position.set(i * 2.4 - 2.4, 0.7, 0); dock.add(m);
    const body = new THREE.Mesh(new THREE.BoxGeometry(2.0, 1.2, 1.2), M.gun); m.add(body); owned.push(body.geometry);
    const port = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.4, 0.14, 24), M.glass); port.rotation.z = Math.PI / 2; port.position.x = 1.04; m.add(port); owned.push(port.geometry);
    const ringD = new THREE.Mesh(new THREE.TorusGeometry(0.46, 0.06, 8, 28), M.chrome); ringD.rotation.y = Math.PI / 2; ringD.position.x = 1.05; m.add(ringD); owned.push(ringD.geometry);
  }
  const rail = new THREE.Mesh(new THREE.BoxGeometry(8.4, 0.2, 1.8), M.dark); rail.position.y = 0.1; dock.add(rail); owned.push(rail.geometry);
  dock.rotation.y = -0.3;

  // ---- state-linked update
  const tmp = v3(0, 0, 0), tmp2 = v3(0, 0, 0);
  const flash = (age: number | null) => (age === null || age > FLASH_TICKS ? 0 : 1 - age / (FLASH_TICKS + 1));
  const set = (s: BodyState, aimWorld: THREE.Vector3) => {
    const dead = !s.a2Present, fireF = flash(s.a1FireAge), renF = dead ? 0 : flash(s.renewAge);
    // node lamps: A with the observation (lit on sampled ticks, scaled by coverage), B with A1 firing, C with A2 renewal
    M.lampA.emissiveIntensity = s.sampling ? 0.5 + 2.8 * s.coverage : 0.06;
    M.lampB.emissiveIntensity = 0.06 + 3.4 * fireF;
    M.lampC.emissiveIntensity = dead ? 0 : 0.06 + 3.4 * renF + (s.recovered ? 0.3 : 0);
    (nodeC.probeTip.material as THREE.MeshBasicMaterial).opacity = renF; sparkA.visible = renF > 0.05; (sparkA.material as THREE.MeshBasicMaterial).opacity = renF * 0.8; sparkA.scale.setScalar(0.5 + renF);
    nodeC.probe.position.y = dead ? 0.9 : 0.05 - 0.35 * renF;
    nodeB.probe.position.y = 0.05 - 0.3 * fireF;
    nodeA.probe.position.y = s.sampling ? 0.05 - 0.4 * s.coverage : 0.4;
    // bundles: dim and part when the coupling is cut
    cabBC.mesh.material = s.couplingCut ? M.dark : M.rubber; cabBC.clamps.visible = !s.couplingCut;
    jr.forEach((r, i) => { r.position.z = (i === 0 ? 0 : i === 1 ? 0.14 : -0.14) * (s.couplingCut ? 3.4 : 1) + 0.5; });
    // travelling lights
    const place = (m: THREE.Mesh, cab: Cable, u: number, opacity: number) => { m.visible = opacity > 0.02; if (m.visible) { cab.curve.getPoint(Math.max(0, Math.min(1, u)), tmp); m.position.copy(tmp); (m.material as THREE.MeshBasicMaterial).opacity = opacity; } };
    place(pBC, cabBC, s.a1FireAge === null ? 0 : s.a1FireAge / (FLASH_TICKS + 1), s.couplingCut ? 0 : fireF);
    place(pCB, cabBC, s.renewAge === null ? 1 : 1 - s.renewAge / (FLASH_TICKS + 1), s.couplingCut || dead ? 0 : renF);
    place(pAJ, cabAJ, s.sampling ? 0.5 : 0, s.sampling ? 0.5 * s.coverage : 0);
    place(pJB, cabJB, s.a1FireAge === null ? 0 : s.a1FireAge / (FLASH_TICKS + 1), fireF * 0.8);
    // the observation node: the arm turns toward the target and reaches along the line to it (two-link reach, elbow up); the probe stays vertical and lowers on sampled ticks
    obs.updateMatrixWorld(true);
    yaw.getWorldPosition(tmp2);
    const to = aimWorld.clone().sub(tmp2).divideScalar(obs.scale.x), flat = Math.hypot(to.x, to.z), D = Math.min(Math.hypot(flat, to.y), L1 + L2 - 0.2), theta = Math.atan2(to.y, flat);
    yaw.rotation.y = Math.atan2(to.x, to.z) - obs.rotation.y;
    const cosA1 = (L1 * L1 + D * D - L2 * L2) / (2 * L1 * D), cosE = (L1 * L1 + L2 * L2 - D * D) / (2 * L1 * L2);
    const a1 = Math.acos(Math.max(-1, Math.min(1, cosA1))), bend = Math.PI - Math.acos(Math.max(-1, Math.min(1, cosE)));
    shoulder.rotation.x = -(theta + a1);  // a positive rotation about x tilts the arm down, so an elevation is a negative rotation
    elbow.rotation.x = bend;
    wrist.rotation.x = -(shoulder.rotation.x + elbow.rotation.x);
    carrier.position.y = -0.95 - (s.sampling ? 0.9 * s.coverage : 0);
    (probeTip2.material as THREE.MeshBasicMaterial).opacity = s.sampling ? 0.9 : 0.05;
  };
  return { group, ncbCentre: NCB_AT.clone(), observerCentre: OBSERVER_AT.clone(), set, dispose: () => { owned.forEach((o) => o.dispose()); } };
}
