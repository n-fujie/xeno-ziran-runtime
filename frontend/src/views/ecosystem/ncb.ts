// XENO ECOSYSTEM — the non-central experimental body: three nodes (A observation / sensing, B processing / analysis, C resource / exchange) of real geometry, a ring junction
// and a network of cables between them. See bodyState.ts for what the parts do and for the statement that this is a presentation of a run and not an identification.
//
// A node is a truncated triangular pyramid frame. Its static geometry is built twice: ``hi`` (perforated plates with real holes and slots, fasteners, ports, brackets, hinge
// pins, tension brackets, cable passthroughs) and ``lo`` (plain plates, frame and hubs only), and shown through a THREE.LOD, so that the detail is paid for only near the camera.
// What moves or lights is separate from the LOD: the lamp, the lens, the probes, and on node C the reservoir, on node B the archive latch.
import * as THREE from 'three';
import { Frame, Parts, boxAt, collar, cylAt, discAt, plateThrough, sphere, torusAt, tube, v3 } from './geom';
import { Fasteners, aperture, blankingPlate, hingePin, inspection, lBracket, passthrough, probeSocket, recessedPort, turnbuckle } from './hardware';
import { bake, buildProbe, type Probe, type ProbeMats, type ProbeSpec } from './probes';
import type { MatKey } from './geom';

export interface PartInfo {
  id: string; name: string; kind: string; body: 'ncb' | 'observer'; object: THREE.Object3D;
  /** quantities read from the build parameters (exact), in scene units; the technical view adds measured ones */
  params?: Record<string, number | string>;
}
export interface BodyMats extends ProbeMats {
  dark: THREE.Material; glass: THREE.Material; sleeve: THREE.Material; lampA: THREE.MeshStandardMaterial; lampB: THREE.MeshStandardMaterial; lampC: THREE.MeshStandardMaterial;
  spark: THREE.MeshBasicMaterial; pulse: THREE.MeshBasicMaterial; lens: THREE.MeshStandardMaterial;
}
export const asMatKeys = (M: BodyMats): Record<MatKey, THREE.Material> => ({ chrome: M.chrome, gun: M.gun, dark: M.dark, rubber: M.rubber, polished: M.polished, sleeve: M.sleeve, glass: M.glass });

export interface NodeSpec { id: 'A' | 'B' | 'C'; r0: number; r1: number; h: number; window: boolean; legs: boolean; seed: number; probes: ProbeSpec[]; reservoir?: boolean; archive?: boolean; /** how far the feet stand below the frame's base (the legs are longer by this) */ lift?: number }
export interface NodeBuild {
  group: THREE.Group; lod: THREE.LOD; spec: NodeSpec; lamp: THREE.Mesh; lens: THREE.Mesh | null; probes: Probe[]; anchors: Record<string, THREE.Vector3>;
  /** the lens cover: a disc that slides across the lens while the node is asleep and parks beside it while the node works */ cover?: { mesh: THREE.Mesh; open: number };
  reservoir?: { piston: THREE.Mesh; bottom: number; height: number }; latch?: { lever: THREE.Group; lamp: THREE.Mesh }; parts: PartInfo[];
  stats: { vertices: number; fasteners: number; plateDepth: number; plates: number };
  dispose(): void;
}
export const PLATE_DEPTH = 0.09;

export function seeded(seed: number): () => number {
  let a = seed >>> 0;
  return () => { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

export function buildNode(spec: NodeSpec, M: BodyMats, detail: number): NodeBuild {
  const owned: Array<{ dispose(): void }> = [];
  const group = new THREE.Group(); group.name = `node-${spec.id}`;
  const lod = new THREE.LOD(); group.add(lod);
  const B = [0, 1, 2].map((i) => { const a = (i / 3) * Math.PI * 2 + 0.3; return v3(Math.cos(a) * spec.r0, 0, Math.sin(a) * spec.r0); });
  const T = [0, 1, 2].map((i) => { const a = (i / 3) * Math.PI * 2 + 0.3; return v3(Math.cos(a) * spec.r1, spec.h, Math.sin(a) * spec.r1); });
  const mats = asMatKeys(M);
  const info: PartInfo[] = [];
  const anchors: Record<string, THREE.Vector3> = {};
  B.forEach((p, i) => { anchors[`hubBase${i}`] = p.clone(); anchors[`hubTop${i}`] = T[i].clone(); });
  anchors.bottom = v3(0, -0.2, 0); anchors.top = v3(0, spec.h + 0.5, 0);
  const stats = { vertices: 0, fasteners: 0, plateDepth: PLATE_DEPTH, plates: 3 };

  const buildStatic = (lo: boolean): THREE.Group => {
    const g = new THREE.Group(), parts = new Parts(), fast = new Fasteners(), R = seeded(spec.seed * 977 + 13);
    const hole = 0.07 - 0.015 * detail, pitch = hole * (lo ? 40 : 2.9);
    // faces
    for (let i = 0; i < 3; i++) {
      const j = (i + 1) % 3, face = [B[i], B[j], T[j], T[i]], win = spec.window && i === 0;
      const [q0, q1, q2] = face, exV = q1.clone().sub(q0).normalize(), nP = exV.clone().cross(q2.clone().sub(q0)).normalize(), eyV = nP.clone().cross(exV);
      const cc = face.reduce((a, b) => a.add(b), v3(0, 0, 0)).multiplyScalar(0.25);
      const out = nP.dot(v3(cc.x, 0, cc.z)) < 0 ? -1 : 1, f = new Frame(cc, exV, eyV, nP.clone().multiplyScalar(out));
      const sl = face[0].distanceTo(face[3]), rr = Math.min(spec.h * 0.3, spec.r0 * 0.42);
      const big: Array<[number, number, number]> = [], clear: Array<[number, number, number]> = [], slots: Array<[number, number, number, number]> = [];
      type Feat = () => void;
      const feats: Feat[] = [];
      if (win) { big.push([0, 0, rr]); }
      else if (i === 1) {
        big.push([0.2, sl * 0.18, rr * 0.5]); clear.push([-0.75, -sl * 0.18, 0.4], [0.6, -sl * 0.3, 0.3], [-0.5, sl * 0.28, 0.3]);
        for (let k = 0; k < 4; k++) slots.push([0.72, -sl * 0.05 - k * 0.2, 0.62, 0.075]);
        feats.push(() => recessedPort(parts, f, 0.2, sl * 0.18, rr * 0.5, 2), () => probeSocket(parts, f, -0.75, -sl * 0.18, 0.2), () => passthrough(parts, f, 0.6, -sl * 0.3, 0.1, f.n.clone().add(v3(0, -0.4, 0)).normalize()),
          () => aperture(parts, f, -0.5, sl * 0.28, 0.14), () => fast.ring(f, 0.2, sl * 0.18, rr * 0.5 + 0.11, 11, R, ['hex', 'socket', 'captive']));
      } else {
        big.push([-0.35, sl * 0.2, rr * 0.46], [0.55, -sl * 0.12, rr * 0.3]); clear.push([0.1, -sl * 0.34, 0.5], [-0.8, -sl * 0.1, 0.3]);
        for (let k = 0; k < 3; k++) slots.push([-0.7, -sl * 0.2 - k * 0.19, 0.5, 0.07]);
        feats.push(() => recessedPort(parts, f, -0.35, sl * 0.2, rr * 0.46, 1), () => recessedPort(parts, f, 0.55, -sl * 0.12, rr * 0.3, 3), () => blankingPlate(parts, fast, f, 0.1, -sl * 0.34, 0.5, 0.36, R),
          () => inspection(parts, f, -0.8, -sl * 0.1, 0.15), () => fast.ring(f, 0.55, -sl * 0.12, rr * 0.3 + 0.09, 9, R, ['socket', 'hex']), () => passthrough(parts, f, 0.8, sl * 0.3, 0.09, f.n.clone().add(v3(0.3, 0.2, 0)).normalize()));
      }
      if (win) {
        for (let k = 0; k < 3; k++) slots.push([0, -sl * 0.35 - k * 0.14, 1.1 - k * 0.2, 0.065]);
        feats.push(() => fast.ring(f, 0, 0, rr * 1.07 + 0.08, 14, R, ['socket', 'hex']), () => inspection(parts, f, -1.0, sl * 0.33, 0.12), () => blankingPlate(parts, fast, f, 0.85, sl * 0.3, 0.42, 0.3, R));
      }
      const plate = plateThrough(face, { hole, pitch, margin: 0.2, depth: PLATE_DEPTH, big, keepClear: clear, slots: lo ? [] : slots, seg: lo ? 4 : detail > 0.6 ? 10 : 6 }, 0.94);
      parts.add('gun', plate, 0.35);
      if (!lo) {
        feats.forEach((fn) => fn());
        fast.edge(face.map((p) => p.clone().lerp(v3(0, spec.h / 2, 0), 0.03)), f.n, R, { pitch: 0.3 / Math.max(0.5, detail), inset: 0.11, lift: 0.045, kinds: ['hex', 'hex', 'socket', 'exposed', 'captive'] });
        // greebles: small blocks, caps and standoffs scattered over the face (more near the openings)
        for (let k = 0; k < 26 * detail; k++) {
          const u = (R() - 0.5) * 1.8, v = (R() - 0.5) * (sl * 0.8), c = f.at(u, v, 0.07);
          if (clear.some(([cx, cy, cr]) => Math.hypot(u - cx, v - cy) < cr + 0.1) || big.some(([cx, cy, cr]) => Math.hypot(u - cx, v - cy) < cr + 0.15)) continue;
          parts.add(R() < 0.5 ? 'gun' : 'chrome', R() < 0.7 ? boxAt(c, f.ex, f.ey, f.n, 0.07 + R() * 0.16, 0.07 + R() * 0.13, 0.04 + R() * 0.08) : cylAt(c, f.n, 0.04 + R() * 0.06, 0.05 + R() * 0.08, 8), 0.7);
        }
        // L brackets along the base edge and a bracket pair at the top
        lBracket(parts, fast, f.at(-0.9, -sl * 0.45, 0.05), f.ex, f.n, 0.32, R); lBracket(parts, fast, f.at(0.9, sl * 0.42, 0.05), f.ex, f.n, 0.26, R);
      }
    }
    // frame: corner tubes, edge tubes, hubs, collars
    for (let i = 0; i < 3; i++) {
      const j = (i + 1) % 3;
      parts.add('chrome', tube(B[i], B[j], 0.07), 0.45); parts.add('chrome', tube(T[i], T[j], 0.07), 0.45); parts.add('chrome', tube(B[i], T[i], 0.085), 0.5); parts.add('chrome', tube(B[i], T[j], 0.04), 0.5);
      parts.add('chrome', sphere(B[i], 0.17, lo ? 8 : 14), 0.95); parts.add('chrome', sphere(T[i], 0.15, lo ? 8 : 14), 0.9);
      if (!lo) { parts.add('chrome', collar(B[i], T[i], 0.115, 0.3), 0.9); parts.add('chrome', collar(B[i], T[i], 0.115, 0.75), 0.9); }
    }
    if (!lo) {
      const mid = [0, 1, 2].map((i) => B[i].clone().lerp(T[i], 0.5).multiplyScalar(1.07).setY(spec.h * 0.5));
      for (let i = 0; i < 3; i++) {
        const j = (i + 1) % 3;
        parts.add('chrome', tube(mid[i], mid[j], 0.06), 0.5); parts.add('chrome', tube(mid[i], B[i].clone().multiplyScalar(1.02), 0.04), 0.5); parts.add('chrome', tube(mid[i], T[i].clone().multiplyScalar(1.02), 0.04), 0.5);
        parts.add('chrome', sphere(mid[i], 0.13), 0.9); parts.add('chrome', collar(mid[i], mid[j], 0.1, 0.5, 0.2), 0.8);
        const fb = B[i].clone().lerp(B[j], 0.5), ft = T[i].clone().lerp(T[j], 0.5), outV = fb.clone().setY(0).normalize().multiplyScalar(0.1);
        parts.add('chrome', tube(fb.clone().add(outV), ft.clone().add(outV), 0.035), 0.5); parts.add('chrome', tube(B[i].clone().add(outV), ft.clone().add(outV), 0.03), 0.5); parts.add('chrome', tube(B[j].clone().add(outV), ft.clone().add(outV), 0.03), 0.5);
        const a = v3(Math.cos(((i + 0.5) / 3) * Math.PI * 2 + 0.3) * spec.r1 * 0.5, spec.h - 0.2, Math.sin(((i + 0.5) / 3) * Math.PI * 2 + 0.3) * spec.r1 * 0.5), b2 = fb.clone().multiplyScalar(0.72).setY(0.35), m2 = a.clone().lerp(b2, 0.42);
        parts.add('gun', tube(a, m2, 0.085), 0.8); parts.add('chrome', tube(m2, b2, 0.045), 0.7); parts.add('chrome', sphere(a, 0.1), 0.9); parts.add('chrome', sphere(b2, 0.09), 0.9);
        // tension brackets on two of the three bays, hinge pins at the base hubs, bolt circles at the hubs
        if (i !== 1) turnbuckle(parts, mid[i].clone().add(v3(0, -0.15, 0)), B[j].clone().multiplyScalar(0.98).add(v3(0, 0.25, 0)), 0.05);
        hingePin(parts, B[i].clone().add(v3(0, 0.05, 0)), v3(-B[i].z, 0, B[i].x).normalize(), 0.5, 0.045);
        for (let k = 0; k < 9; k++) { const t = (k / 9) * Math.PI * 2; fast.add(k % 3 === 0 ? 'socket' : 'hex', v3(Math.cos(t) * 0.21, 0.12, Math.sin(t) * 0.21).add(B[i]), v3(0, 1, 0), 0.8); }
        // a sensor pod on each top vertex
        const pc = T[i].clone().multiplyScalar(1.28).setY(spec.h - 0.15), dir = T[i].clone().setY(0).normalize();
        parts.add('gun', cylAt(pc, dir, 0.24, 0.3, 20), 0.8); parts.add('glass', discAt(pc.clone().addScaledVector(dir, 0.16), dir, 0.14, 18), 0.2); parts.add('chrome', torusAt(pc.clone().addScaledVector(dir, 0.155), dir, 0.16, 0.025, 14), 0.8);
        parts.add('chrome', tube(T[i], pc, 0.05), 0.5);
      }
    }
    // the top drum, ring and mast; feet
    const topC = v3(0, spec.h, 0);
    parts.add('gun', cylAt(topC, v3(0, 1, 0), spec.r1 * 0.95, 0.34, lo ? 12 : 30, spec.r1 * 0.82), 0.6); parts.add('chrome', torusAt(topC.clone().add(v3(0, 0.18, 0)), v3(0, 1, 0), spec.r1 * 0.9, 0.055, lo ? 14 : 40), 0.7);
    parts.add('chrome', cylAt(topC.clone().add(v3(0, 0.3, 0)), v3(0, 1, 0), 0.07, 0.7, 10, 0.05), 0.6);
    if (spec.legs) for (let i = 0; i < 3; i++) {
      const foot = B[i].clone().multiplyScalar(1.25 + (spec.lift ?? 0) * 0.15).add(v3(0, -0.45 - (spec.lift ?? 0), 0));
      parts.add('chrome', tube(B[i].clone().add(v3(0, 0.05, 0)), foot.clone().add(v3(0, 0.05, 0)), 0.08), 0.6); parts.add('gun', cylAt(foot, v3(0, 1, 0), 0.26, 0.12, 14, 0.2), 0.9);
      if (!lo) for (const o of [[0.2, 0], [-0.1, 0.17], [-0.1, -0.17]]) parts.add('chrome', cylAt(foot.clone().add(v3(o[0], -0.09, o[1])), v3(0, 1, 0), 0.05, 0.1, 6, 0.02), 0.9);  // grip spikes under the pad
    }
    parts.flush(g, mats, owned, `node-${spec.id}${lo ? '-lo' : ''}`);
    if (!lo) { fast.build(g, { chrome: M.chrome, gun: M.gun, dark: M.dark }, owned, detail); stats.fasteners = fast.count; stats.vertices = parts.vertices; }
    return g;
  };
  const hi = buildStatic(false), lo = buildStatic(true);
  lod.addLevel(hi, 0); lod.addLevel(lo, 70);
  info.push({ id: `${spec.id}`, name: `Node ${spec.id}`, kind: 'node', body: 'ncb', object: group, params: { r0: spec.r0, r1: spec.r1, h: spec.h, plateThickness: PLATE_DEPTH } });

  // dynamic parts --------------------------------------------------------------------------------------------------------
  const lampMat = spec.id === 'A' ? M.lampA : spec.id === 'B' ? M.lampB : M.lampC;
  const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.17, 14, 10), lampMat); lamp.position.set(0, spec.h + 0.46, 0); group.add(lamp); owned.push(lamp.geometry);
  let lens: THREE.Mesh | null = null, cover: NodeBuild['cover'];
  if (spec.window) {
    const face = [B[0], B[1], T[1], T[0]], [q0, q1, q2] = face, nP = q1.clone().sub(q0).cross(q2.clone().sub(q0)).normalize(), cc = face.reduce((a, b) => a.add(b), v3(0, 0, 0)).multiplyScalar(0.25);
    const nrm = nP.dot(v3(cc.x, 0, cc.z)) < 0 ? nP.clone().negate() : nP, rad = Math.min(spec.h * 0.3, spec.r0 * 0.42);
    const win = new THREE.Group(); win.position.copy(cc); win.lookAt(cc.clone().add(nrm)); group.add(win);
    const mk = (g: THREE.BufferGeometry, m: THREE.Material, z: number) => { const x = new THREE.Mesh(g, m); x.position.z = z; win.add(x); owned.push(g); return x; };
    mk(new THREE.TorusGeometry(rad * 1.02, 0.07, 10, 48), M.chrome, 0.02); mk(new THREE.TorusGeometry(rad * 0.82, 0.05, 10, 48), M.gun, 0.0); mk(new THREE.TorusGeometry(rad * 0.6, 0.05, 10, 40), M.chrome, -0.04);
    mk(new THREE.TorusGeometry(rad * 0.4, 0.035, 8, 36), M.gun, -0.08); mk(new THREE.CylinderGeometry(rad * 0.58, rad * 0.5, 0.12, 36).rotateX(Math.PI / 2), M.dark, -0.1);
    lens = mk(new THREE.CircleGeometry(rad * 0.5, 40), M.glass, -0.14);
    const cv = mk(new THREE.CylinderGeometry(rad * 0.6, rad * 0.6, 0.05, 36).rotateX(Math.PI / 2), M.gun, 0.07);
    const cvRing = new THREE.Mesh(new THREE.TorusGeometry(rad * 0.6, 0.03, 8, 36), M.chrome); cvRing.position.z = 0.03; cv.add(cvRing); owned.push(cvRing.geometry);
    cv.position.x = rad * 1.12; cover = { mesh: cv, open: rad * 1.12 };
    const lensLamp = mk(new THREE.CircleGeometry(rad * 0.2, 28), M.lens, -0.12);  // the lens lamp
    for (let k = 0; k < 6; k++) { const a = (k / 6) * Math.PI * 2 + 0.4; mk(new THREE.BoxGeometry(0.03, rad * 0.32, 0.02), M.dark, -0.11).position.set(Math.cos(a) * rad * 0.36, Math.sin(a) * rad * 0.36, -0.11); }  // iris blades
    bake(win, [lens, cv, lensLamp], owned);  // the rings, iris blades and bolts are one mesh per material; the lens, its lamp and the sliding cover stay separate
    info.push({ id: `${spec.id}.lens`, name: `Lens ${spec.id}`, kind: 'lens', body: 'ncb', object: win, params: { radius: +rad.toFixed(3) } });
  }
  const probes: Probe[] = [];
  spec.probes.forEach((ps, k) => {
    const pr = buildProbe(ps, M, detail);
    if (k === 0) pr.group.position.set(0, 0.0, 0);
    else { pr.group.position.set(B[1].x * 0.5, spec.h * 0.28, B[1].z * 0.5); pr.group.rotation.z = Math.PI / 2; pr.group.position.add(v3(0.55, 0, 0)); }
    group.add(pr.group); probes.push(pr);
    info.push({ id: ps.id, name: `Probe ${ps.id}`, kind: 'probe', body: 'ncb', object: pr.group, params: { length: ps.length, radius: ps.radius, tip: ps.tip } });
  });
  let reservoir: NodeBuild['reservoir'];
  if (spec.reservoir) {
    const rg = new THREE.Group(), at = B[2].clone().multiplyScalar(1.55).add(v3(0.0, 0, 0)), H = 1.7, Rr = 0.27; rg.position.copy(at); group.add(rg);
    const add = (g: THREE.BufferGeometry, m: THREE.Material, y: number) => { const x = new THREE.Mesh(g, m); x.position.y = y; rg.add(x); owned.push(g); return x; };
    add(new THREE.CylinderGeometry(Rr * 1.3, Rr * 1.4, 0.18, 24), M.gun, 0.09); add(new THREE.CylinderGeometry(Rr * 1.3, Rr * 1.2, 0.16, 24), M.gun, H + 0.2);
    add(new THREE.CylinderGeometry(Rr, Rr, H, 24, 1, true), M.glass, H / 2 + 0.17);
    for (let k = 0; k < 4; k++) { const a = (k / 4) * Math.PI * 2 + 0.4, t = tube(v3(Math.cos(a) * Rr * 1.12, 0.17, Math.sin(a) * Rr * 1.12), v3(Math.cos(a) * Rr * 1.12, H + 0.2, Math.sin(a) * Rr * 1.12), 0.025); const m = new THREE.Mesh(t, M.chrome); rg.add(m); owned.push(t); }
    for (let k = 0; k <= 8; k++) add(new THREE.BoxGeometry(0.09, 0.012, 0.05), M.chrome, 0.2 + (k / 8) * (H - 0.06)).position.set(Rr * 1.3, 0.2 + (k / 8) * (H - 0.06), 0);  // gauge ticks
    const piston = add(new THREE.CylinderGeometry(Rr * 0.94, Rr * 0.94, 0.1, 24), M.lens, 0.3);
    const rod = tube(v3(0, 0.1, 0), v3(0, H + 0.1, 0), 0.03); const rm = new THREE.Mesh(rod, M.chrome); rg.add(rm); owned.push(rod);
    bake(rg, [piston], owned);
    reservoir = { piston, bottom: 0.25, height: H - 0.15 };
    info.push({ id: 'C.reservoir', name: 'Reservoir C', kind: 'reservoir', body: 'ncb', object: rg, params: { height: H, radius: Rr } });
    anchors.reservoirTop = at.clone().add(v3(0, H + 0.3, 0)); anchors.reservoirBottom = at.clone().add(v3(0, 0.2, 0));
  }
  let latch: NodeBuild['latch'];
  if (spec.archive) {
    const ag = new THREE.Group(), at = T[0].clone().multiplyScalar(1.5).add(v3(0, -0.6, 0)); ag.position.copy(at); ag.lookAt(at.clone().add(v3(at.x, 0, at.z))); group.add(ag);
    const box = new THREE.Mesh(new THREE.BoxGeometry(0.72, 0.46, 0.36), M.gun); ag.add(box); owned.push(box.geometry);
    for (const dx of [-0.24, 0, 0.24]) { const s = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.025, 0.02), M.dark); s.position.set(dx, 0.08, 0.185); ag.add(s); owned.push(s.geometry); }
    const hinge = new THREE.Group(); hinge.position.set(-0.3, -0.26, 0.2); ag.add(hinge);
    const lever = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.05, 0.04), M.chrome); lever.position.set(0.3, 0, 0); hinge.add(lever); owned.push(lever.geometry);
    const pin = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.1, 10).rotateX(Math.PI / 2), M.chrome); hinge.add(pin); owned.push(pin.geometry);
    const keeper = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.09, 0.07), M.gun); keeper.position.set(0.3, -0.07, 0.2); ag.add(keeper); owned.push(keeper.geometry);
    const al = new THREE.Mesh(new THREE.SphereGeometry(0.045, 10, 8), M.lampB.clone()); al.position.set(0.28, 0.17, 0.19); ag.add(al); owned.push(al.geometry);
    bake(ag, [hinge, al], owned);
    latch = { lever: hinge, lamp: al };
    info.push({ id: 'B.archive', name: 'Archive unit B', kind: 'archive', body: 'ncb', object: ag, params: { width: 0.72, height: 0.46, depth: 0.36 } });
    anchors.archive = at.clone();
  }
  return { group, lod, spec, lamp, lens, probes, anchors, reservoir, latch, cover, parts: info, stats, dispose: () => { owned.forEach((o) => o.dispose()); probes.forEach((p) => p.dispose()); } };
}
