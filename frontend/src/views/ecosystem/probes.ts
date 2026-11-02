// XENO ECOSYSTEM — needle probes. The probe is the most important visual sign of the bodies, so it carries information: its length and diameter, the kind of tip, what it is
// made of along its length, how it is held and how it retracts. Its state is read from the record by ``probeState`` in bodies.ts and is one of
//
//   extended    the rod is out and the bead is dim: the probe is ready
//   retracted   the rod is withdrawn into its housing: not in use
//   sampling    the rod is out a little further and the bead is lit: this is a sampled tick of the observation
//   inactive    the rod is half withdrawn, the bead is dark: the probe cannot act (the entity it belongs to is absent, or its address is lost)
//   overloaded  the rod is part way out and trembles, the bead flickers: the observation cannot resolve the operation it is pointed at
//
// Geometry is a pure function of a ``ProbeSpec``; the dimensions are read back from it (``probeDimensions``) by the technical view, so what is drawn there is what is built here.
import * as THREE from 'three';
import { localBox, normalise } from './geom';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

export type TipKind = 'needle' | 'hollow' | 'hook' | 'bead';
export type ProbeState = 'extended' | 'retracted' | 'sampling' | 'inactive' | 'overloaded';
export interface ProbeSpec { id: string; length: number; radius: number; tip: TipKind; insulated: number; retractor: boolean; strain: boolean }

export interface Probe {
  group: THREE.Group; rod: THREE.Group; bead: THREE.Mesh; polished: THREE.Mesh; spec: ProbeSpec;
  /** Pose the probe for a state; ``tick`` drives the tremble and flicker of the overloaded state. */
  setState(state: ProbeState, tick: number): void;
  dispose(): void;
}
export interface ProbeMats { chrome: THREE.Material; gun: THREE.Material; rubber: THREE.Material; polished: THREE.Material; lamp: THREE.MeshStandardMaterial }

const v3 = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);
const HOUSING = 0.55;  // the housing's share of the length

/** Merge the meshes directly below ``parent`` (except those in ``keep``) into one mesh per material, with their own transforms baked into the geometry: a probe has dozens of small parts
 * and would otherwise cost dozens of draw calls. */
export function bake(parent: THREE.Object3D, keep: THREE.Object3D[], owned: Array<{ dispose(): void }>): void {
  const by = new Map<THREE.Material, THREE.BufferGeometry[]>();
  for (const c of [...parent.children]) {
    const m = c as THREE.Mesh;
    if (!m.isMesh || keep.includes(c)) continue;
    c.updateMatrix();
    const g = m.geometry.clone().applyMatrix4(c.matrix);
    (by.get(m.material as THREE.Material) ?? (by.set(m.material as THREE.Material, []), by.get(m.material as THREE.Material)!)).push(normalise(g, 0.3));
    parent.remove(c); m.geometry.dispose();
  }
  for (const [mat, gs] of by) { const merged = mergeGeometries(gs); gs.forEach((g) => g.dispose()); if (merged) { parent.add(new THREE.Mesh(merged, mat)); owned.push(merged); } }
}

/** The lathe profile of the polished section as (radius, y) pairs from ``upper`` (the bottom of the insulated section) down to the tip at y = -length. */
export function tipProfile(kind: TipKind, length: number, r: number, upper: number): THREE.Vector2[] {
  const span = length + upper, y = (t: number) => upper - span * t, V = (rr: number, t: number) => new THREE.Vector2(rr, y(t));
  if (kind === 'hollow') return [V(r * 0.72, 0), V(r * 0.7, 0.6), V(r * 0.5, 0.88), V(r * 0.42, 0.97), V(r * 0.42, 1), V(r * 0.22, 1), V(r * 0.26, 0.9), V(r * 0.2, 0.8)];
  return [V(r * 0.72, 0), V(r * 0.7, 0.6), V(r * 0.4, 0.86), V(r * 0.12, 0.97), new THREE.Vector2(0.004, -length)];
}

export function buildProbe(spec: ProbeSpec, M: ProbeMats, detail: number): Probe {
  const { length: L, radius: r } = spec;
  const group = new THREE.Group();
  group.name = `probe-${spec.id}`;
  const owned: Array<{ dispose(): void }> = [];
  const mesh = (g: THREE.BufferGeometry, m: THREE.Material, parent: THREE.Object3D = group) => { const x = new THREE.Mesh(g, m); parent.add(x); owned.push(g); return x; };
  const seg = detail > 0.6 ? 18 : 10;
  // mount: a flange ring with bolt heads, then the housing with bands
  const hr = Math.max(r * 3.2, 0.16);
  mesh(new THREE.CylinderGeometry(hr * 1.5, hr * 1.5, 0.05, seg + 6), M.gun).position.y = 0.025;
  const ring = mesh(new THREE.TorusGeometry(hr * 1.38, 0.025, 6, seg + 8), M.chrome); ring.rotation.x = Math.PI / 2; ring.position.y = 0.055;
  for (let k = 0; k < 6; k++) { const a = (k / 6) * Math.PI * 2, b = mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.025, 6), M.chrome); b.position.set(Math.cos(a) * hr * 1.38, 0.065, Math.sin(a) * hr * 1.38); }
  const hh = L * HOUSING;
  mesh(new THREE.CylinderGeometry(hr, hr * 1.04, hh, seg), M.chrome).position.y = -hh / 2;
  for (const t of [0.2, 0.62, 0.92]) { const b = mesh(new THREE.CylinderGeometry(hr * 1.1, hr * 1.1, 0.045, seg), M.gun); b.position.y = -hh * t; }
  mesh(new THREE.CylinderGeometry(hr * 0.78, hr * 0.78, 0.03, seg), M.rubber).position.y = -hh - 0.005;  // the dark seal at the mouth of the housing
  // the rod: an insulated section (rubber) and the polished section with its tip; it slides in and out of the housing
  const rod = new THREE.Group(); group.add(rod);
  const rodTop = -hh * 0.85, rodLen = L - HOUSING * 0.85 * L, insLen = rodLen * spec.insulated;
  const ins = mesh(new THREE.CylinderGeometry(r * 0.78, r * 0.78, insLen, 12), M.rubber, rod); ins.position.y = rodTop - insLen / 2;
  const cl = mesh(new THREE.CylinderGeometry(r * 0.95, r * 0.95, 0.05, 12), M.chrome, rod); cl.position.y = rodTop - insLen;  // the collar between the sections
  const upper = rodTop - insLen;  // the polished section starts below the insulated one
  const polished = mesh(new THREE.LatheGeometry(tipProfile(spec.tip, L, r, upper), seg), M.polished, rod);
  if (spec.tip === 'hook') {  // a short hook at the end: a bent tube
    const base = v3(0, -L, 0), curve = new THREE.CatmullRomCurve3([base.clone().add(v3(0, 0.0, 0)), base.clone().add(v3(0.03, -r * 1.2, 0)), base.clone().add(v3(r * 1.9, -r * 2.2, 0)), base.clone().add(v3(r * 2.6, -r * 0.9, 0))]);
    const tg = new THREE.TubeGeometry(curve, 10, r * 0.13, 6, false); mesh(tg, M.polished, rod);
  }
  const beadAt = spec.tip === 'bead' ? -L * 0.9 : -L * 0.62;
  const bead = new THREE.Mesh(new THREE.SphereGeometry(Math.max(r * 0.55, 0.045), 12, 9), M.lamp.clone()); bead.position.y = beadAt; rod.add(bead); owned.push(bead.geometry, bead.material as THREE.Material);
  if (spec.tip === 'bead') { const t = mesh(new THREE.ConeGeometry(r * 0.12, L * 0.1, 8), M.polished, rod); t.position.y = -L - L * 0.04; t.rotation.x = Math.PI; }
  // the retract mechanism: an actuator body and rod beside the housing, a spring coil around it
  if (spec.retractor) {
    const ax = hr * 1.7, act = mesh(new THREE.CylinderGeometry(hr * 0.32, hr * 0.32, hh * 0.7, 10), M.gun); act.position.set(ax, -hh * 0.38, 0);
    const arm = mesh(new THREE.CylinderGeometry(hr * 0.12, hr * 0.12, hh * 0.6, 8), M.chrome); arm.position.set(ax, -hh * 0.7, 0);
    const link = mesh(new THREE.CylinderGeometry(hr * 0.1, hr * 0.1, ax - hr * 0.9, 8), M.chrome); link.rotation.z = Math.PI / 2; link.position.set((ax + hr * 0.9) / 2, -hh * 0.98, 0);
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= 40; i++) { const t = i / 40, a = t * Math.PI * 2 * 7; pts.push(v3(ax + Math.cos(a) * hr * 0.46, -hh * (0.1 + 0.55 * t), Math.sin(a) * hr * 0.46)); }
    mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 90, 0.012, 5, false), M.chrome);
  }
  // strain cable: a loop from the side of the housing up to the mount, with a boot and a clamp
  if (spec.strain) {
    const c = new THREE.CatmullRomCurve3([v3(-hr * 0.98, -hh * 0.55, 0.0), v3(-hr * 1.9, -hh * 0.35, 0.1), v3(-hr * 2.0, -hh * 0.05, 0.05), v3(-hr * 1.3, 0.05, 0.0)]);
    mesh(new THREE.TubeGeometry(c, 20, 0.018, 6, false), M.rubber);
    const boot = mesh(new THREE.CylinderGeometry(0.03, 0.05, 0.12, 8), M.rubber); boot.position.set(-hr * 1.02, -hh * 0.55, 0); boot.rotation.z = Math.PI / 2;
    const clamp = mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.04, 8), M.chrome); clamp.position.set(-hr * 1.55, -hh * 0.2, 0.08); clamp.rotation.x = Math.PI / 2;
  }
  bake(group, [rod], owned);
  bake(rod, [bead, polished], owned);
  const setState = (state: ProbeState, tick: number) => {
    const lampMat = bead.material as THREE.MeshStandardMaterial;
    let e = 1, lamp = 0.25, tremble = 0;
    if (state === 'retracted') { e = 0; lamp = 0; }
    else if (state === 'sampling') { e = 1.07; lamp = 3.0; }
    else if (state === 'inactive') { e = 0.18; lamp = 0; }
    else if (state === 'overloaded') { e = 0.58; lamp = tick % 2 === 0 ? 2.4 : 0.1; tremble = (tick % 2 === 0 ? 1 : -1) * 0.012; }
    rod.position.y = (1 - e) * L * HOUSING * 0.9;
    rod.position.x = tremble; rod.rotation.z = tremble * 1.6;
    lampMat.emissiveIntensity = lamp;
  };
  setState('extended', 0);
  return { group, rod, bead, polished, spec, setState, dispose: () => owned.forEach((o) => o.dispose()) };
}

/** The dimensions of a probe as built (units of the scene), measured on its geometry with the rod extended: the length from the mounting plane to the tip, the diameter of the
 * polished section, the housing and the insulated section. The technical view prints these numbers. */
export function probeDimensions(p: Probe): { length: number; measuredLength: number; diameter: number; housing: number; insulated: number; tip: TipKind } {
  const { length, insulated, tip } = p.spec;
  const was = p.rod.position.clone(), wasRot = p.rod.rotation.z;
  p.rod.position.set(0, 0, 0); p.rod.rotation.z = 0; p.group.updateMatrixWorld(true);
  const box = localBox(p.group, p.group), pol = localBox(p.polished, p.group);
  p.rod.position.copy(was); p.rod.rotation.z = wasRot; p.group.updateMatrixWorld(true);
  return {
    length: +length.toFixed(3), measuredLength: +(-box.min.y).toFixed(3), diameter: +(pol.max.x - pol.min.x).toFixed(3), housing: +(length * HOUSING).toFixed(3),
    insulated: +((length - HOUSING * 0.85 * length) * insulated).toFixed(3), tip,
  };
}
