// Reusable geometry assemblies of the high-fidelity laboratory (Three.js). Every object is tagged with its layer
// (A physical, B scientific, C architecture), its category (1 executable, 2 runtime instrument, 3 faithful
// representation of a recorded dependency, 4 architecture without scientific claim) and, when it can be inspected, a
// selection id. Positions of executable objects come from recorded state through coords.ts only.

import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { LabRecord, LabStep, SystemState } from '../labScene';
import { FLOOR_Y, PHYS, chamberFloor, lerp3, physToView, planeToView, type V3 } from './coords';
import { bayOf, ring, specs, type Category, type Layer, type Selection } from './model';

export type Quality = 'performance' | 'balanced' | 'high';

// ------------------------------------------------------------------------------------------------------ materials
export function palette(q: Quality) {
  const std = (color: number, metalness: number, roughness: number) => new THREE.MeshStandardMaterial({ color, metalness, roughness });
  return {
    floor: std(0x121214, 0.3, 0.8),
    plinth: std(0x26262a, 0.55, 0.55),
    ceramic: std(0xd9d9d4, 0.05, 0.55),  // industrial ceramic: chamber floors and walls (executable geometry)
    graphite: std(0x47474c, 0.6, 0.42),
    steel: std(0x77777c, 0.9, q === 'performance' ? 0.45 : 0.32),  // brushed metal
    darkSteel: std(0x5c5c62, 0.8, 0.36),
    composite: std(0x303035, 0.2, 0.75),  // matte composite (architecture)
    louvre: std(0xb9b9be, 0.85, 0.3),
    sample: new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0.25, roughness: 0.7 }),
    glow: new THREE.MeshStandardMaterial({ color: 0x101012, emissive: 0xffffff, emissiveIntensity: 0, metalness: 0.2, roughness: 0.4 }),
    line: new THREE.LineBasicMaterial({ color: 0x6a6a70, transparent: true, opacity: 0.16 }),
    cable: new THREE.MeshStandardMaterial({ color: 0x4a4a50, metalness: 0.6, roughness: 0.5, emissive: 0xffffff, emissiveIntensity: 0 }),
  };
}
export type Palette = ReturnType<typeof palette>;

export function tag(o: THREE.Object3D, layer: Layer, category: Category, kind: string, sel?: Selection): THREE.Object3D {
  o.userData = { ...o.userData, layer, category, kind, sel };
  o.traverse((c) => {
    c.userData = { ...c.userData, layer, category, kind, sel: c.userData.sel ?? sel };
    if ((c as THREE.Mesh).isMesh) { (c as THREE.Mesh).castShadow = !c.userData.smallParts; (c as THREE.Mesh).receiveShadow = true; }
  });
  return o;
}

function box(w: number, h: number, d: number, m: THREE.Material, x = 0, y = 0, z = 0): THREE.Mesh {
  const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
  b.position.set(x, y, z);
  return b;
}

function cyl(r: number, h: number, m: THREE.Material, x = 0, y = 0, z = 0, seg = 12): THREE.Mesh {
  const c = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, seg), m);
  c.position.set(x, y, z);
  return c;
}

/** One InstancedMesh for many copies of a small part (bolts, blades, slots, members). */
function instanced(geo: THREE.BufferGeometry, m: THREE.Material, mats: THREE.Matrix4[]): THREE.InstancedMesh {
  const im = new THREE.InstancedMesh(geo, m, Math.max(1, mats.length));
  im.userData.smallParts = true;  // receives shadows but does not cast them (cheaper shadow pass)
  mats.forEach((mx, i) => im.setMatrixAt(i, mx));
  im.count = mats.length;
  im.instanceMatrix.needsUpdate = true;
  return im;
}

const M = (x: number, y: number, z: number, ry = 0, sx = 1, sy = 1, sz = 1) =>
  new THREE.Matrix4().compose(new THREE.Vector3(x, y, z), new THREE.Quaternion().setFromEuler(new THREE.Euler(0, ry, 0)), new THREE.Vector3(sx, sy, sz));

/** Merge the static, non-instanced meshes under a group by material (fewer draw calls). The merged meshes keep the
 *  group's tags; positions are baked relative to the group, so the drawn geometry is unchanged. */
export function mergeStatic<T extends THREE.Object3D>(g: T): T {
  g.updateMatrixWorld(true);
  const inv = g.matrixWorld.clone().invert();
  const by = new Map<THREE.Material, THREE.BufferGeometry[]>();
  const drop: THREE.Mesh[] = [];
  g.traverse((o) => {
    const m = o as THREE.Mesh;
    if (!m.isMesh || (m as unknown as THREE.InstancedMesh).isInstancedMesh || Array.isArray(m.material) || o === g) return;
    const geo = m.geometry.index ? m.geometry.toNonIndexed() : m.geometry.clone();
    for (const k of Object.keys(geo.attributes)) if (!['position', 'normal', 'uv'].includes(k)) geo.deleteAttribute(k);
    geo.applyMatrix4(inv.clone().multiply(m.matrixWorld));
    const list = by.get(m.material as THREE.Material) ?? [];
    list.push(geo);
    by.set(m.material as THREE.Material, list);
    drop.push(m);
  });
  if (drop.length < 2) return g;
  for (const m of drop) m.parent?.remove(m);
  for (const [mat, geos] of by) {
    const merged = mergeGeometries(geos, false);
    if (!merged) continue;
    const mesh = new THREE.Mesh(merged, mat);
    mesh.castShadow = mesh.receiveShadow = true;
    mesh.userData = { ...g.userData };
    g.add(mesh);
  }
  return g;
}

// ------------------------------------------------------------------------------------------------------ placement spots
// The spots where physics.py `_free_spot` places a delivered sample (offsets from the container centre, metres).
export const SPOTS_CHAMBER: [number, number][] = [[0, 0], [0.65, 0.65], [-0.65, 0.65], [0.65, -0.65], [-0.65, -0.65]];
export const SPOTS_PORT: [number, number][] = [[0, 0], [0.4, 0.4], [-0.4, -0.4]];

function spotMarkers(spots: [number, number][], y: number, p: Palette, kind: 'chamber' | 'port', id: string, at: [number, number] = [0, 0]): THREE.Object3D {
  const mats = spots.map(([dx, dz]) => new THREE.Matrix4().compose(new THREE.Vector3(at[0] + dx, y + 0.003, at[1] + dz),
    new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2, 0, Math.PI / 4)), new THREE.Vector3(1, 1, 1)));
  const m = instanced(new THREE.RingGeometry(0.2, 0.225, 4), p.darkSteel, mats);
  m.castShadow = false;
  tag(m, 'A', 3, 'sample placement spots (physics.py _free_spot)', { kind, id });
  return m;
}

// ------------------------------------------------------------------------------------------------------ chamber
export type ChamberParts = { group: THREE.Group; louvres: THREE.InstancedMesh; activity: THREE.Mesh; memory: THREE.Mesh;
  ring: THREE.Mesh; base: V3 };
const LOUVRES_PER_SIDE = 7;
const RIM_Y0 = FLOOR_Y + PHYS.WALL_H + 0.04;  // the instrument rim sits on the walls, below the tool's travel height
const RIM_H = 0.22;

/** Experimental chamber: executable floor and walls exactly as in MuJoCo (layer A), containment louvres and
 *  instruments driven by recorded runtime state (layer B), housing details (layer C). */
export function chamberAssembly(cid: string, position: V3, p: Palette, q: Quality): ChamberParts {
  const g = new THREE.Group();
  const [x, y, z] = chamberFloor(position);
  g.position.set(x, 0, z);
  const W = 2 * PHYS.CH;
  // layer A — MuJoCo geoms: floor box (half 1.3 × 1.3 × 0.05 centred at z = 0) and four walls (0.7 m)
  const phys = new THREE.Group();
  phys.add(box(W, 0.1, W, p.ceramic, 0, y - 0.05, 0));
  for (const [dx, dz, sx, sz] of [[PHYS.CH, 0, 2 * PHYS.WALL_T, W], [-PHYS.CH, 0, 2 * PHYS.WALL_T, W], [0, PHYS.CH, W, 2 * PHYS.WALL_T], [0, -PHYS.CH, W, 2 * PHYS.WALL_T]]) {
    phys.add(box(sx, PHYS.WALL_H, sz, p.ceramic, dx, y - 0.05 + PHYS.WALL_H / 2, dz));  // MuJoCo: z from 0 to 0.7
  }
  tag(phys, 'A', 1, 'chamber collision geometry', { kind: 'chamber', id: cid });
  g.add(mergeStatic(phys));
  g.add(spotMarkers(SPOTS_CHAMBER, y, p, 'chamber', cid));
  // layer B — containment louvres in the rim: blade angle = recorded closure (1 − mean gate of entering connections)
  const blade = new THREE.BoxGeometry(W / LOUVRES_PER_SIDE - 0.03, RIM_H - 0.04, 0.025);
  const mats: THREE.Matrix4[] = [];
  for (let side = 0; side < 4; side++) {
    for (let k = 0; k < LOUVRES_PER_SIDE; k++) {
      const u = -PHYS.CH + (k + 0.5) * (W / LOUVRES_PER_SIDE);
      const [bx, bz] = side === 0 ? [u, PHYS.CH] : side === 1 ? [u, -PHYS.CH] : side === 2 ? [PHYS.CH, u] : [-PHYS.CH, u];
      mats.push(M(bx, RIM_Y0 + RIM_H / 2, bz, side < 2 ? 0 : Math.PI / 2));
    }
  }
  const louvres = instanced(blade, p.louvre, mats);
  louvres.userData.base = mats.map((m) => m.clone());
  tag(louvres, 'B', 2, 'containment (runtime gate)', { kind: 'chamber', id: cid });
  g.add(louvres);
  // rim frame carrying the louvres (structure of the instrument; no claim of its own)
  const rim = new THREE.Group();
  for (const [dx, dz, sx, sz] of [[0, PHYS.CH, W + 0.12, 0.06], [0, -PHYS.CH, W + 0.12, 0.06], [PHYS.CH, 0, 0.06, W + 0.12], [-PHYS.CH, 0, 0.06, W + 0.12]]) {
    rim.add(box(sx, 0.035, sz, p.darkSteel, dx, RIM_Y0 + RIM_H + 0.02, dz), box(sx, 0.035, sz, p.darkSteel, dx, RIM_Y0 - 0.005, dz));
  }
  if (q !== 'performance') {  // louvre actuator housings at the middle of each rim side (housing only)
    for (const [dx, dz, sx, sz] of [[0, PHYS.CH + 0.07, 0.3, 0.08], [0, -PHYS.CH - 0.07, 0.3, 0.08], [PHYS.CH + 0.07, 0, 0.08, 0.3], [-PHYS.CH - 0.07, 0, 0.08, 0.3]]) {
      rim.add(box(sx, RIM_H + 0.04, sz, p.graphite, dx, RIM_Y0 + RIM_H / 2, dz));
    }
  }
  tag(rim, 'C', 4, 'instrument rim frame');
  g.add(mergeStatic(rim));
  // layer B — corner instrument column: glow = activity (share ignited), fill height = retained memory
  const col = new THREE.Group();
  col.add(box(0.16, 1.5, 0.16, p.graphite, PHYS.CH + 0.18, FLOOR_Y + 0.75, PHYS.CH + 0.18));
  const activity = box(0.06, 1.2, 0.17, p.glow.clone(), PHYS.CH + 0.18, FLOOR_Y + 0.75, PHYS.CH + 0.18 - 0.005);
  activity.position.x += 0.06;
  const memory = box(0.07, 1, 0.07, p.steel, PHYS.CH + 0.18, FLOOR_Y + 0.15, PHYS.CH + 0.31);
  col.add(activity, memory);
  tag(col, 'B', 2, 'chamber instrument (activity, memory)', { kind: 'chamber', id: cid });
  g.add(col);
  // layer C — housing: base skirt, corner posts, bolt rows, vents
  const housing = new THREE.Group();
  housing.add(box(W + 0.3, 0.16, W + 0.3, p.plinth, 0, FLOOR_Y - 0.18, 0));
  for (const [cx, cz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) {
    if (cx === 1 && cz === 1) continue;  // that corner carries the instrument column
    housing.add(box(0.1, PHYS.WALL_H + RIM_H + 0.1, 0.1, p.darkSteel, cx * (PHYS.CH + 0.08), FLOOR_Y + (PHYS.WALL_H + RIM_H) / 2, cz * (PHYS.CH + 0.08)));
  }
  if (q !== 'performance') {
    const bolts: THREE.Matrix4[] = [];
    for (let side = 0; side < 4; side++) {
      for (let k = 0; k < 9; k++) {
        const u = -PHYS.CH + 0.15 + k * ((W - 0.3) / 8);
        const [bx, bz] = side === 0 ? [u, PHYS.CH + 0.16] : side === 1 ? [u, -PHYS.CH - 0.16] : side === 2 ? [PHYS.CH + 0.16, u] : [-PHYS.CH - 0.16, u];
        bolts.push(M(bx, FLOOR_Y - 0.1, bz));
      }
    }
    housing.add(instanced(new THREE.CylinderGeometry(0.022, 0.022, 0.03, 6), p.steel, bolts));
    const vents: THREE.Matrix4[] = [];
    for (let k = 0; k < 6; k++) vents.push(M(-PHYS.CH + 0.4 + k * 0.36, FLOOR_Y - 0.18, -PHYS.CH - 0.155));
    housing.add(instanced(new THREE.BoxGeometry(0.22, 0.06, 0.012), p.graphite, vents));
  }
  if (q !== 'performance') {  // service manifold on the outer face (housing only; no instrument)
    housing.add(box(0.9, 0.34, 0.16, p.composite, -0.4, FLOOR_Y + 0.2, -PHYS.CH - 0.24), box(0.12, 0.5, 0.12, p.darkSteel, 0.25, FLOOR_Y + 0.25, -PHYS.CH - 0.24));
  }
  tag(housing, 'C', 4, 'chamber housing');
  g.add(mergeStatic(housing));
  // selection / event ring (recorded events only)
  const ringM = new THREE.Mesh(new THREE.TorusGeometry(PHYS.CH * 1.45, 0.025, 6, 64),
    new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthWrite: false }));
  ringM.rotation.x = Math.PI / 2;
  ringM.position.y = FLOOR_Y - 0.08;
  tag(ringM, 'B', 2, 'recorded event marker', { kind: 'chamber', id: cid });
  g.add(ringM);
  return { group: g, louvres, activity, memory, ring: ringM, base: [x, y, z] };
}

export function applyChamber(c: ChamberParts, closure: number, activity: number, memory: number): void {
  const base = c.louvres.userData.base as THREE.Matrix4[];
  const q = new THREE.Quaternion();
  const pos = new THREE.Vector3(), sc = new THREE.Vector3(), rot = new THREE.Quaternion();
  const ang = (1 - Math.min(1, Math.max(0, closure))) * (Math.PI / 2) * 0.92;  // open: blades turned edge-on
  base.forEach((m, i) => {
    m.decompose(pos, rot, sc);
    q.setFromAxisAngle(new THREE.Vector3(1, 0, 0), ang);  // about the blade's own long axis (local x) on every side
    void i;
    c.louvres.setMatrixAt(i, new THREE.Matrix4().compose(pos, rot.clone().multiply(q), sc));
  });
  c.louvres.instanceMatrix.needsUpdate = true;
  (c.activity.material as THREE.MeshStandardMaterial).emissiveIntensity = 0.15 + 2.4 * Math.min(1, Math.max(0, activity));
  const h = Math.max(0.02, Math.min(1.3, memory * 1.3));
  c.memory.scale.y = h;
  c.memory.position.y = FLOOR_Y + h / 2;
}

// ------------------------------------------------------------------------------------------------------ gantry
export type GantryParts = { key: string; group: THREE.Group; bridge: THREE.Group; trolley: THREE.Group; mast: THREE.Mesh; carrier: THREE.Mesh;
  carriage: THREE.Group; lamp: THREE.Mesh; env: { x0: number; x1: number; y0: number; y1: number }; railY: number };
const RAIL_Y = 3.45;

/** The work envelope of a bay: its chambers and the ports it serves, axis-aligned in the physics x-y plane (the slide
 *  joints move along world x and y). The slides' range is ±7.5 m; the frame is drawn over the envelope actually used. */
export function bayEnvelope(r: LabRecord, bay: string): { x0: number; x1: number; y0: number; y1: number } {
  // chamber housings reach CH + 0.6 m from the centre (instrument column, sensor posts); ports PORT + 0.35 m
  const box_: [number, number, number][] = r.chambers.filter((c) => bayOf(c.cid) === bay).map((c) => [c.position[0], c.position[2], PHYS.CH + 0.6]);
  for (const [k, xy] of Object.entries(r.layout?.ports ?? {})) if (k.slice(5).split('-').includes(bay)) box_.push([xy[0], xy[1], PHYS.PORT + 0.35]);
  return { x0: Math.min(...box_.map((p) => p[0] - p[2])), x1: Math.max(...box_.map((p) => p[0] + p[2])),
    y0: Math.min(...box_.map((p) => p[1] - p[2])), y1: Math.max(...box_.map((p) => p[1] + p[2])) };
}

/** Cartesian gantry: the carriage and tool are drawn at the recorded tool tip (layer A, executable); rails, bridge and
 *  mast represent the x, y and z slide joints (layer A, category 3); columns are structure (layer C). With private
 *  carriages each group's rails are drawn at their own height (a visual offset only). */
export function gantryAssembly(key: string, env: { x0: number; x1: number; y0: number; y1: number }, level: number, p: Palette,
  q: Quality): GantryParts {
  const g = new THREE.Group();
  const railY = RAIL_Y + level * 0.5;
  const { x0, x1, y0, y1 } = env;
  const rails = new THREE.Group();
  for (const yy of [y0, y1]) {
    rails.add(box(x1 - x0, 0.12, 0.18, p.steel, (x0 + x1) / 2, railY, yy));
    if (q !== 'performance') rails.add(box(x1 - x0, 0.025, 0.05, p.louvre, (x0 + x1) / 2, railY + 0.072, yy));  // linear guide
  }
  tag(rails, 'A', 3, 'x slide (rails)', { kind: 'gantry', id: key });
  g.add(mergeStatic(rails));
  if (level === 0) {
    const cols = new THREE.Group();
    for (const [xx, yy] of [[x0, y0], [x0, y1], [x1, y0], [x1, y1]]) {
      cols.add(box(0.22, railY + 0.4, 0.22, p.darkSteel, xx, (railY + 0.4) / 2 - 0.05, yy));
      if (q !== 'performance') cols.add(box(0.5, 0.06, 0.5, p.graphite, xx, 0.03, yy));
    }
    if (q !== 'performance') {  // knee braces at the column heads and a header beam between columns (structure)
      for (const [xx, yy] of [[x0, y0], [x0, y1], [x1, y0], [x1, y1]]) {
        const sx = xx === x0 ? 1 : -1;
        const br = box(0.05, 1.1, 0.05, p.darkSteel, xx + sx * 0.38, railY - 0.38, yy);
        br.rotation.z = sx * Math.PI / 4;
        cols.add(br);
      }
      for (const xx of [x0, x1]) cols.add(box(0.14, 0.14, y1 - y0, p.darkSteel, xx, railY + 0.33, (y0 + y1) / 2));
    }
    tag(cols, 'C', 4, 'gantry columns');
    g.add(mergeStatic(cols));
  }
  const bridge = new THREE.Group();  // the bridge rides on both rails on end trucks (it is the x slide's moving part)
  bridge.add(box(0.24, 0.16, y1 - y0, p.graphite, 0, railY + 0.14, (y0 + y1) / 2));
  for (const yy of [y0, y1]) bridge.add(box(0.46, 0.14, 0.32, p.darkSteel, 0, railY + 0.13, yy));
  tag(bridge, 'A', 3, 'y slide (bridge on end trucks)', { kind: 'gantry', id: key });
  const trolley = new THREE.Group();
  trolley.add(box(0.42, 0.22, 0.42, p.darkSteel, 0, railY + 0.02, 0));
  if (q !== 'performance') for (const sx of [-1, 1]) trolley.add(box(0.13, 0.16, 0.13, p.graphite, sx * 0.13, railY + 0.21, 0));  // drive housings
  const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.06, 10, 8), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 1 }));
  lamp.position.set(0.24, railY + 0.02, 0);
  trolley.add(lamp);
  tag(trolley, 'A', 3, 'trolley (health lamp: recorded health)', { kind: 'gantry', id: key });
  const mast = box(0.1, 1, 0.1, p.steel);
  tag(mast, 'A', 3, 'z slide (mast)', { kind: 'gantry', id: key });
  const carriage = new THREE.Group();  // MuJoCo carriage box (0.12 × 0.12 × 0.08 half) and tool (0.05 × 0.05 × 0.1 half)
  // its own material: a failed gantry is drawn dark without touching any other steel part
  carriage.add(box(0.24, 0.16, 0.24, p.steel.clone(), 0, PHYS.TIP_OFFSET, 0), box(0.1, 0.2, 0.1, p.darkSteel, 0, 0.1, 0));
  if (q !== 'performance') {  // gripper fingers (the weld grasp is modelled; the fingers are visual)
    for (const s of [-1, 1]) carriage.add(box(0.025, 0.12, 0.09, p.steel, s * 0.07, -0.02, 0));
  }
  tag(carriage, 'A', 1, 'carriage and tool (recorded tool tip)', { kind: 'gantry', id: key });
  const carrier = box(0.1, 0.07, 1, p.composite, 0.2, railY + 0.27, 0);  // cable carrier along the bridge to the trolley
  tag(carrier, 'C', 4, 'cable carrier (drawn, not modelled)');
  carrier.visible = q !== 'performance';
  g.add(bridge, trolley, mast, carriage, carrier);
  return { key, group: g, bridge, trolley, mast, carrier, carriage, lamp, env, railY };
}

export function applyGantry(gp: GantryParts, tipView: V3, health: number, failed: boolean): void {
  const [x, y, z] = tipView;
  gp.bridge.position.x = x;
  gp.trolley.position.set(x, 0, z);
  const len = Math.max(0.05, z - gp.env.y0);  // from the bridge's y0 end truck to the trolley
  gp.carrier.scale.z = len;
  gp.carrier.position.set(x + 0.2, gp.railY + 0.27, gp.env.y0 + len / 2);
  gp.carriage.position.set(x, y, z);
  const top = gp.railY - 0.1, bottom = y + PHYS.TIP_OFFSET + 0.08;
  gp.mast.scale.y = Math.max(0.01, top - bottom);
  gp.mast.position.set(x, (top + bottom) / 2, z);
  (gp.lamp.material as THREE.MeshBasicMaterial).opacity = failed ? 0.05 : 0.2 + 0.8 * health;
  const m = gp.carriage.children[0] as THREE.Mesh;
  (m.material as THREE.MeshStandardMaterial).color.setHex(failed ? 0x26262a : 0x77777c);
}

// ------------------------------------------------------------------------------------------------------ ports, samples
export function portAssembly(key: string, xy: [number, number], p: Palette, q: Quality): THREE.Group {
  const g = new THREE.Group();
  const [x, y, z] = planeToView(xy);
  const table = box(2 * PHYS.PORT, 0.1, 2 * PHYS.PORT, p.ceramic, x, y - 0.05, z);  // MuJoCo port geom (top at z = 0.05)
  tag(table, 'A', 1, 'handoff port', { kind: 'port', id: key });
  g.add(table, spotMarkers(SPOTS_PORT, y, p, 'port', key, [x, z]));
  const ped = new THREE.Group();
  ped.add(cyl(0.38, y - 0.1, p.darkSteel, x, (y - 0.1) / 2, z, 6));
  if (q !== 'performance') {
    for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) ped.add(box(0.06, 0.12, 0.06, p.steel, x + sx * (PHYS.PORT - 0.05), y + 0.06, z + sz * (PHYS.PORT - 0.05)));
  }
  tag(ped, 'C', 4, 'port pedestal');
  g.add(mergeStatic(ped));
  return g;
}

/** All material samples as one instanced mesh; instance k is sample ids[k] (selection maps the instance id back). */
export function samplesMesh(ids: string[], p: Palette): THREE.InstancedMesh {
  const m = new THREE.InstancedMesh(new THREE.BoxGeometry(2 * PHYS.HALF, 2 * PHYS.HALF, 2 * PHYS.HALF), p.sample, Math.max(1, ids.length));
  m.count = ids.length;
  m.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(Math.max(1, ids.length) * 3).fill(1), 3);
  tag(m, 'A', 1, 'material samples (recorded positions)');
  m.userData.ids = ids;
  m.userData.sel = undefined;
  return m;
}

// ------------------------------------------------------------------------------------------------------ systems
export type SystemParts = { sid: string; group: THREE.Group; head: THREE.Group; coverage: THREE.Group; store: THREE.Group | null;
  slots: THREE.InstancedMesh | null; pending: THREE.Group; rangeRing: THREE.Mesh | null };
const SLOTS = 48;

/** Observation and memory apparatus of a scientific system (layer B): the sensor head / hub sits at the recorded sensor
 *  chamber; coverage is the recorded set of observed chambers; the store shows the recorded number of memory entries. */
export function systemAssembly(sid: string, kind: string, k: number, p: Palette, storeCid: string | null, storePos: V3 | null): SystemParts {
  const group = new THREE.Group();
  const head = new THREE.Group();
  if (kind === 'distributed') {  // hub: receiver tower — base cabinet, mast, stacked receiver rings, cap
    head.add(box(0.34, 0.42, 0.34, p.graphite, 0, 0.21, 0), box(0.36, 0.03, 0.36, p.darkSteel, 0, 0.43, 0));
    head.add(cyl(0.05, 1.5, p.darkSteel, 0, 1.15, 0, 10));
    for (const [y, r] of [[1.05, 0.2], [1.32, 0.17], [1.59, 0.14]] as [number, number][]) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(r, 0.022, 6, 24), p.steel);
      ring.rotation.x = Math.PI / 2;
      ring.position.y = y;
      head.add(ring);
      for (let a = 0; a < 3; a++) {  // ring spokes
        const sp = box(r, 0.012, 0.012, p.darkSteel, Math.cos((a * 2 * Math.PI) / 3) * r / 2, y, Math.sin((a * 2 * Math.PI) / 3) * r / 2);
        sp.rotation.y = -(a * 2 * Math.PI) / 3;
        head.add(sp);
      }
    }
    head.add(cyl(0.07, 0.06, p.steel, 0, 1.93, 0, 12));
  } else {  // sensor post on the chamber corner with a short inward boom; the pod stays outside the sample spots the
    // tool visits (spots at ±0.65 m from the centre), above the walls, so it never stands where the carriage moves
    const post = box(0.08, 1.75, 0.08, p.darkSteel, 0, 0.875, 0);
    const base = box(0.2, 0.08, 0.2, p.graphite, 0, 0.04, 0);
    const boom = new THREE.Group();  // two-segment articulated boom with joints, hooded optical pod at its end
    const j1 = new THREE.Mesh(new THREE.SphereGeometry(0.055, 12, 8), p.steel);
    const seg1 = box(0.34, 0.05, 0.05, p.darkSteel, -0.17, 0, 0);
    const j2 = new THREE.Mesh(new THREE.SphereGeometry(0.045, 12, 8), p.steel);
    j2.position.set(-0.34, 0, 0);
    const seg2 = box(0.24, 0.045, 0.045, p.darkSteel, -0.44, -0.07, 0);
    seg2.rotation.z = 0.55;
    const pod = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.075, 0.22, 16), p.steel);
    pod.position.set(-0.56, -0.19, 0);
    pod.rotation.z = 0.9;
    const hood = new THREE.Mesh(new THREE.CylinderGeometry(0.095, 0.085, 0.06, 16, 1, true), p.graphite);
    hood.position.set(-0.62, -0.26, 0);
    hood.rotation.z = 0.9;
    const lens = new THREE.Mesh(new THREE.CircleGeometry(0.06, 16), p.glow.clone());
    lens.position.set(-0.64, -0.28, 0);
    lens.rotation.set(0, Math.PI / 2, 0.9 - Math.PI / 2);
    (lens.material as THREE.MeshStandardMaterial).emissiveIntensity = 0.9;
    boom.add(j1, seg1, j2, seg2, pod, hood, lens);
    boom.position.y = 1.74;
    boom.rotation.y = -Math.PI / 4;  // pointing into the chamber from its (+x, −z) corner
    head.add(base, post, boom);
  }
  tag(head, 'B', 2, kind === 'distributed' ? `system ${sid} hub` : `system ${sid} sensor head`, { kind: 'sensor', id: `${sid}:head` });
  group.add(head);
  const coverage = new THREE.Group();
  tag(coverage, 'B', 2, `system ${sid} observed chambers`);
  group.add(coverage);
  let store: THREE.Group | null = null, slots: THREE.InstancedMesh | null = null;
  if (storeCid && storePos) {  // memory store: a rack whose filled slots are the recorded memory entries
    store = new THREE.Group();
    const [x, , z] = chamberFloor(storePos);
    store.position.set(x - PHYS.CH - 0.36, 0, z);
    store.add(box(0.32, 1.9, 1.2, p.graphite, 0, FLOOR_Y + 0.95, 0));
    for (const z of [-0.6, 0.6]) store.add(box(0.36, 1.96, 0.04, p.darkSteel, 0, FLOOR_Y + 0.98, z));  // frame
    store.add(box(0.36, 0.05, 1.24, p.darkSteel, 0, FLOOR_Y + 1.93, 0), box(0.36, 0.08, 1.24, p.darkSteel, 0, FLOOR_Y + 0.04, 0));
    const mats: THREE.Matrix4[] = [];
    // outward face; filled from the top row down, so the recorded entries stay visible above the neighbouring walls
    for (let i = 0; i < SLOTS; i++) mats.push(M(-0.17, FLOOR_Y + 1.78 - Math.floor(i / 6) * 0.21, -0.45 + (i % 6) * 0.18, 0, 1, 1, 1));
    slots = instanced(new THREE.BoxGeometry(0.02, 0.15, 0.13), p.glow.clone(), mats);
    (slots.material as THREE.MeshStandardMaterial).emissiveIntensity = 1.2;
    store.add(slots);
    tag(store, 'B', 2, `system ${sid} memory store (filled slots: recorded entries)`, { kind: 'store', id: `${sid}:store` });
    group.add(store);
  }
  const pending = new THREE.Group();
  tag(pending, 'B', 3, `system ${sid} pending experiment (recorded)`);
  group.add(pending);
  let rangeRing: THREE.Mesh | null = null;
  if (kind === 'local') {  // sensing radius of a local system (its configured range; shown as an overlay)
    rangeRing = new THREE.Mesh(new THREE.RingGeometry(3.58, 3.62, 96), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.35, side: THREE.DoubleSide }));
    rangeRing.rotation.x = -Math.PI / 2;
    tag(rangeRing, 'B', 2, `system ${sid} sensing radius (configured)`);
    group.add(rangeRing);
  }
  void k;
  return { sid, group, head, coverage, store, slots, pending, rangeRing };
}

const SYS_DASH = [0, 0.3, 0.07];

function outline(cx: number, cz: number, r: number, k: number, opacity: number): THREE.LineLoop {
  const pts = Array.from({ length: 6 }, (_, i) => new THREE.Vector3(cx + r * Math.cos((i * Math.PI) / 3 + Math.PI / 6), FLOOR_Y - 0.06, cz + r * Math.sin((i * Math.PI) / 3 + Math.PI / 6)));
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = SYS_DASH[k] ? new THREE.LineDashedMaterial({ color: 0xffffff, dashSize: SYS_DASH[k], gapSize: SYS_DASH[k] * 0.7, transparent: true, opacity })
    : new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity });
  const l = new THREE.LineLoop(geo, mat);
  l.computeLineDistances();
  return l;
}

export function applySystem(sp: SystemParts, st: SystemState, k: number, chamberPos: Map<string, V3>, storeReadable: boolean,
  showCoverage: boolean, kind: string): void {
  const s = chamberPos.get(st.sensor);
  if (s) {
    const [x, , z] = chamberFloor(s);
    if (kind === 'distributed') sp.head.position.set(x - PHYS.CH - 0.3, FLOOR_Y, z + PHYS.CH + 0.3);
    else sp.head.position.set(x + PHYS.CH + 0.12, FLOOR_Y - 0.1, z - PHYS.CH - 0.12);
    if (sp.rangeRing) sp.rangeRing.position.set(x, FLOOR_Y - 0.07, z);
  }
  // observed-chamber outlines: one cached outline per chamber, shown when the chamber is in the recorded coverage
  const cache = (sp.coverage.userData.byChamber ??= new Map<string, THREE.LineLoop>()) as Map<string, THREE.LineLoop>;
  const want = new Set(showCoverage ? st.coverage : []);
  for (const c of want) {
    if (cache.has(c)) continue;
    const p = chamberPos.get(c);
    if (!p) continue;
    const [x, , z] = chamberFloor(p);
    const l = outline(x, z, PHYS.CH * 1.62 + 0.14 * k, k, 0.8);
    cache.set(c, l);
    sp.coverage.add(l);
  }
  for (const [c, l] of cache) l.visible = want.has(c);
  if (sp.rangeRing) sp.rangeRing.visible = showCoverage;
  if (sp.slots) {
    sp.slots.count = Math.min(SLOTS, st.memory);
    sp.slots.instanceMatrix.needsUpdate = true;
    (sp.slots.material as THREE.MeshStandardMaterial).emissiveIntensity = storeReadable ? 1.2 : 0.12;
  }
  const key = st.pending ? st.pending.join('>') : '';
  if (sp.pending.userData.key === key) return;
  sp.pending.userData.key = key;
  sp.pending.children.forEach((c) => { (c as THREE.Line).geometry.dispose(); ((c as THREE.Line).material as THREE.Material).dispose(); });
  sp.pending.clear();
  if (st.pending) {
    const a = chamberPos.get(st.pending[0]), b = chamberPos.get(st.pending[1]);
    if (a && b) {
      const pa = new THREE.Vector3(...chamberFloor(a)).setY(FLOOR_Y + 2.1), pb = new THREE.Vector3(...chamberFloor(b)).setY(FLOOR_Y + 2.1);
      const mid = pa.clone().add(pb).multiplyScalar(0.5).setY(FLOOR_Y + 2.9 + 0.25 * k);
      const geo = new THREE.BufferGeometry().setFromPoints(new THREE.QuadraticBezierCurve3(pa, mid, pb).getPoints(32));
      const mat = SYS_DASH[k] ? new THREE.LineDashedMaterial({ color: 0xffffff, dashSize: SYS_DASH[k], gapSize: SYS_DASH[k] * 0.7 }) : new THREE.LineBasicMaterial({ color: 0xffffff });
      const l = new THREE.Line(geo, mat);
      l.computeLineDistances();
      sp.pending.add(l);
    }
  }
}

// ------------------------------------------------------------------------------------------------------ conduits
/** Runtime connections between chambers (layer B, category 3). Each chamber has one connection terminal hung from the
 *  ceiling directly above it, at TERMINAL_Y — clear above every gantry part (rails 3.45 m, bridges up to 3.7 m), so no
 *  representation crosses a moving apparatus. Connections are drawn between terminals as gently sagging lines (one
 *  draw call); brightness encodes the recorded count, and a recorded event brightens its connection. Only the end
 *  points carry meaning: the drawn route is a representation. */
export const TERMINAL_Y = 4.85;
const SEG = 10;

export type ConduitParts = { terminals: THREE.Group; lines: THREE.LineSegments; update: (conduits: Record<string, number>, hot: Set<string>) => void };

export function conduitAssembly(chamberPos: Map<string, V3>, p: Palette): ConduitParts {
  const terminals = new THREE.Group();
  const ids = [...chamberPos.keys()];
  const disc: THREE.Matrix4[] = [], hang: THREE.Matrix4[] = [];
  const top = new Map<string, THREE.Vector3>();
  for (const cid of ids) {
    const [x, , z] = chamberFloor(chamberPos.get(cid)!);
    top.set(cid, new THREE.Vector3(x, TERMINAL_Y, z));
    disc.push(M(x, TERMINAL_Y, z));
    hang.push(M(x, (TERMINAL_Y + 7.85) / 2, z));
  }
  terminals.add(instanced(new THREE.CylinderGeometry(0.2, 0.24, 0.08, 6), p.darkSteel, disc));
  terminals.add(instanced(new THREE.BoxGeometry(0.025, 7.85 - TERMINAL_Y, 0.025), p.darkSteel, hang));
  tag(terminals, 'B', 3, 'connection terminals (one per chamber, above it)');
  const cap = ids.length * ids.length / 2;
  const pos = new Float32Array(cap * SEG * 2 * 3), col = new Float32Array(cap * SEG * 2 * 3);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3).setUsage(THREE.DynamicDrawUsage));
  geo.setDrawRange(0, 0);
  const lines = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9 }));
  lines.frustumCulled = false;
  tag(lines, 'B', 3, 'runtime connections (recorded)');
  let key = '';
  const update = (conduits: Record<string, number>, hot: Set<string>) => {
    const k = JSON.stringify(conduits) + [...hot].sort().join(',');
    if (k === key) return;  // geometry only rebuilt when the recorded connections or highlights change
    key = k;
    let v = 0;
    const a = new THREE.Vector3(), b = new THREE.Vector3(), q = new THREE.Vector3();
    for (const [pair, n] of Object.entries(conduits)) {
      const [ca, cb] = pair.split('|');
      const pa = top.get(ca), pb = top.get(cb);
      if (!pa || !pb || v + SEG * 2 > cap * SEG * 2) continue;
      const sag = Math.min(0.9, 0.035 * pa.distanceTo(pb));
      const c = hot.has(pair) ? 1 : Math.min(0.46, 0.17 + 0.05 * n);
      for (let k2 = 0; k2 < SEG; k2++) {
        for (const [u, out] of [[k2 / SEG, a], [(k2 + 1) / SEG, b]] as [number, THREE.Vector3][]) {
          out.lerpVectors(pa, pb, u);
          out.y -= sag * 4 * u * (1 - u);
        }
        for (const w of [a, b]) {
          q.copy(w);
          pos.set([q.x, q.y, q.z], v * 3);
          col.set([c, c, c], v * 3);
          v++;
        }
      }
    }
    geo.setDrawRange(0, v);
    geo.attributes.position.needsUpdate = true;
    geo.attributes.color.needsUpdate = true;
    lines.userData.pairs = Object.keys(conduits).length;
  };
  return { terminals, lines, update };
}

// ------------------------------------------------------------------------------------------------------ architecture
/** The installation's architecture (layer C, category 4) and the routing ring (category 3: transfers go the short way
 *  round the ring of bays through the handoff ports — physics.py `ring` / `_route`). */
export function architecture(r: LabRecord, p: Palette, q: Quality): THREE.Group {
  const root = new THREE.Group();
  const L = r.layout!;
  const arch = new THREE.Group();
  const floor = new THREE.Mesh(new THREE.CircleGeometry(31, 96), p.floor);
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.02;
  arch.add(floor);
  const seams: THREE.Matrix4[] = [];
  for (let k = 0; k < 64; k++) seams.push(M(Math.cos((k / 64) * 2 * Math.PI) * 21, -0.01, Math.sin((k / 64) * 2 * Math.PI) * 21, -(k / 64) * 2 * Math.PI, 1, 1, 1));
  arch.add(instanced(new THREE.BoxGeometry(0.04, 0.01, 2.4), p.graphite, seams));
  // research domains: one hexagonal platform per bay
  for (const [, [bx, by]] of Object.entries(L.bays)) {
    const hex = new THREE.Mesh(new THREE.CylinderGeometry(4.9, 5.1, 0.2, 6), p.plinth);
    hex.position.set(bx, 0.08, by);
    hex.rotation.y = Math.atan2(by, bx);
    arch.add(hex);
    if (q !== 'performance') {
      const edge = new THREE.Mesh(new THREE.TorusGeometry(5.0, 0.03, 4, 6), p.steel);
      edge.rotation.x = Math.PI / 2;
      edge.rotation.z = Math.atan2(by, bx);
      edge.position.set(bx, 0.19, by);
      arch.add(edge);
    }
  }
  const roofY = 9.4;
  const roof = new THREE.Group();  // hidden while the camera is above it (cutaway; layer C only)
  // per domain: service trench round the platform, closed service housings (no indicators: housing only), linear
  // luminaires and a hexagonal ceiling lattice under the roof
  for (const [, [bx, by]] of Object.entries(L.bays)) {
    const ang = Math.atan2(by, bx);
    const dom = new THREE.Group();
    dom.position.set(bx, 0, by);
    dom.rotation.y = -ang;
    const trench = new THREE.Mesh(new THREE.TorusGeometry(5.35, 0.12, 4, 6), p.graphite);
    trench.rotation.x = Math.PI / 2;
    trench.rotation.z = Math.PI / 6;
    trench.position.y = 0.02;
    dom.add(trench);
    if (q !== 'performance') {
      for (const s of [-1, 1]) {  // two service housings on the outer side of the domain
        const h = new THREE.Group();
        h.add(box(0.7, 2.2, 1.4, p.composite, 0, 1.1, 0), box(0.72, 0.06, 1.42, p.darkSteel, 0, 2.23, 0), box(0.72, 0.12, 1.42, p.darkSteel, 0, 0.06, 0));
        for (let k = 0; k < 5; k++) h.add(box(0.012, 1.8, 0.02, p.graphite, 0.36, 1.1, -0.56 + k * 0.28));
        h.position.set(4.35, 0, s * 1.6);
        dom.add(h);
      }
      for (let k = -1; k <= 1; k++) {  // linear luminaires (they light the scene; no scientific claim)
        const lum = box(0.12, 0.06, 5.2, p.darkSteel, k * 1.7, 7.4, 0);
        const lens = box(0.08, 0.012, 5.0, new THREE.MeshStandardMaterial({ color: 0x111111, emissive: 0xffffff, emissiveIntensity: 0.55 }), k * 1.7, 7.36, 0);
        dom.add(lum, lens);
      }
      const hexes: THREE.Matrix4[] = [];
      for (let ix = -2; ix <= 2; ix++) for (let iz = -2; iz <= 2; iz++) {
        const x = ix * 1.9 + (iz % 2 ? 0.95 : 0), z = iz * 1.65;
        if (Math.hypot(x, z) < 4.8) hexes.push(new THREE.Matrix4().compose(new THREE.Vector3(x, 7.9, z), new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.PI / 2, 0, Math.PI / 6)), new THREE.Vector3(1, 1, 1)));
      }
      const ceil = new THREE.Group();  // ceiling lattice and its hangers belong to the roof (cutaway)
      ceil.position.copy(dom.position);
      ceil.rotation.copy(dom.rotation);
      ceil.add(instanced(new THREE.TorusGeometry(0.95, 0.035, 3, 6), p.darkSteel, hexes));
      for (const [x, z] of [[3.6, 3.6], [3.6, -3.6], [-3.6, 3.6], [-3.6, -3.6]]) ceil.add(box(0.05, 1.5, 0.05, p.darkSteel, x * 0.9, 8.65, z * 0.9));
      roof.add(ceil);
    }
    arch.add(dom);
  }
  if (q !== 'performance') {  // overhead cable tray ring above the gantries (carries no recorded connection)
    const tray = new THREE.Mesh(new THREE.TorusGeometry(14, 0.09, 4, 96), p.graphite);
    tray.rotation.x = Math.PI / 2;
    tray.position.y = 4.55;
    arch.add(tray);
    const hangers: THREE.Matrix4[] = [];
    for (let k = 0; k < 48; k++) { const a = (k / 48) * 2 * Math.PI; hangers.push(M(Math.cos(a) * 14, 7.0, Math.sin(a) * 14)); }
    arch.add(instanced(new THREE.BoxGeometry(0.03, 4.9, 0.03), p.darkSteel, hangers));
  }
  // central structural core and roof structure (no function)
  const core = new THREE.Group();
  core.add(new THREE.Mesh(new THREE.CylinderGeometry(2.2, 2.6, 9.4, 6), p.composite));
  core.children[0].position.y = 4.7;
  for (let k = 0; k < 6; k++) core.add(new THREE.Mesh(new THREE.TorusGeometry(2.45 - k * 0.04, 0.05, 4, 6), p.darkSteel));
  core.children.slice(1).forEach((c, k) => { c.rotation.x = Math.PI / 2; c.position.y = 1 + k * 1.5; });
  arch.add(core);
  if (q !== 'performance') {
    const members: THREE.Matrix4[] = [];
    const n = q === 'high' ? 32 : 16;
    for (let k = 0; k < n; k++) {  // radial roof beams from the core to the outer ring
      const a = (k / n) * 2 * Math.PI;
      const len = 26 - 2.4;
      const mx = new THREE.Matrix4().compose(new THREE.Vector3(Math.cos(a) * (2.4 + len / 2), roofY, Math.sin(a) * (2.4 + len / 2)),
        new THREE.Quaternion().setFromEuler(new THREE.Euler(0, -a, 0)), new THREE.Vector3(len, 1, 1));
      members.push(mx);
    }
    roof.add(instanced(new THREE.BoxGeometry(1, 0.32, 0.16), p.darkSteel, members));
    for (const rad of [8, 14, 20, 26]) {
      const ringB = new THREE.Mesh(new THREE.TorusGeometry(rad, 0.08, 4, n * 2), p.darkSteel);
      ringB.rotation.x = Math.PI / 2;
      ringB.position.y = roofY;
      roof.add(ringB);
    }
    // tension cables (tensegrity-like bracing) from the roof ring down to the outer columns
    const cables = new THREE.BufferGeometry();
    const pts: number[] = [];
    for (let k = 0; k < n; k++) {
      const a = (k / n) * 2 * Math.PI, b2 = ((k + 1) / n) * 2 * Math.PI;
      pts.push(Math.cos(a) * 20, roofY, Math.sin(a) * 20, Math.cos(b2) * 26, 0.2, Math.sin(b2) * 26);
      pts.push(Math.cos(b2) * 20, roofY, Math.sin(b2) * 20, Math.cos(a) * 26, 0.2, Math.sin(a) * 26);
    }
    cables.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    roof.add(new THREE.LineSegments(cables, p.line));
  }
  // outer wall: columns and panels
  const nCol = 24;
  const colM: THREE.Matrix4[] = [], panM: THREE.Matrix4[] = [];
  for (let k = 0; k < nCol; k++) {
    const a = (k / nCol) * 2 * Math.PI;
    colM.push(M(Math.cos(a) * 26, roofY / 2, Math.sin(a) * 26, -a));
    const am = ((k + 0.5) / nCol) * 2 * Math.PI;
    for (let lv = 0; lv < (q === 'performance' ? 1 : 3); lv++) panM.push(M(Math.cos(am) * 26.3, 1.6 + lv * 2.9, Math.sin(am) * 26.3, -am + Math.PI / 2));
  }
  arch.add(instanced(new THREE.BoxGeometry(0.5, roofY, 0.5), p.darkSteel, colM));
  arch.add(instanced(new THREE.BoxGeometry(6.4, 2.6, 0.12), p.composite, panM));
  // maintenance walkway at 4.2 m round the installation with railing posts
  const walk = new THREE.Mesh(new THREE.RingGeometry(22.6, 24.2, 96), p.graphite);
  walk.rotation.x = -Math.PI / 2;
  walk.position.y = 4.2;
  (walk.material as THREE.Material).side = THREE.DoubleSide;
  arch.add(walk);
  if (q !== 'performance') {
    const posts: THREE.Matrix4[] = [];
    for (let k = 0; k < 120; k++) {
      const a = (k / 120) * 2 * Math.PI;
      posts.push(M(Math.cos(a) * 22.65, 4.7, Math.sin(a) * 22.65));
    }
    arch.add(instanced(new THREE.BoxGeometry(0.04, 1, 0.04), p.steel, posts));
    const rail = new THREE.Mesh(new THREE.TorusGeometry(22.65, 0.025, 4, 160), p.steel);
    rail.rotation.x = Math.PI / 2;
    rail.position.y = 5.2;
    arch.add(rail);
  }
  tag(arch, 'C', 4, 'installation architecture');
  root.add(mergeStatic(arch));
  tag(roof, 'C', 4, 'roof structure (cutaway when viewed from above)');
  roof.userData.cutawayAbove = roofY - 0.3;
  root.add(roof);
  // routing ring: a sunken channel joining the ports in ring order (category 3)
  const rg = ring(r);
  const ports = L.ports;
  const pts: THREE.Vector3[] = [];
  rg.forEach((b, i) => {
    const nb = rg[(i + 1) % rg.length];
    const key = `port:${[b, nb].sort().join('-')}`;
    const xy = ports[key];
    if (xy) pts.push(new THREE.Vector3(L.bays[b][0], 0.03, L.bays[b][1]), new THREE.Vector3(xy[0], 0.03, xy[1]));
  });
  const routing = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, true, 'catmullrom', 0.0), 256, 0.06, 4, true), p.steel);
  tag(routing, 'A', 3, 'routing ring (transfers go the short way round the bays through the ports)');
  root.add(routing);
  return root;
}

// ------------------------------------------------------------------------------------------------------ the laboratory
export type Lab = {
  root: THREE.Group;
  layers: Record<Layer, THREE.Object3D[]>;
  pickables: THREE.Object3D[];
  apply: (i: number, frac: number, opts: { coverage: boolean; conduits: boolean; events: Set<string> }) => void;
  focus: (sel: Selection) => THREE.Vector3 | null;
  dispose: () => void;
  signature: (i: number) => Record<string, number[]>;
};

/** Build the whole installation for a record (replay or live) at a quality level. The quality level changes geometric
 *  detail only; every layer-A and layer-B transform is computed from the record the same way at every level. */
export function buildLab(r: LabRecord, q: Quality): Lab {
  const p = palette(q);
  const root = new THREE.Group();
  const layers: Record<Layer, THREE.Object3D[]> = { A: [], B: [], C: [] };
  const pickables: THREE.Object3D[] = [];
  const chamberPos = new Map(r.chambers.map((c) => [c.cid, c.position as V3]));
  const chambers = new Map<string, ChamberParts>();
  for (const c of r.chambers) {
    const parts = chamberAssembly(c.cid, c.position as V3, p, q);
    chambers.set(c.cid, parts);
    root.add(parts.group);
    pickables.push(parts.group);
  }
  if (r.layout) {
    const arch = architecture(r, p, q);
    root.add(arch);
    for (const [k, xy] of Object.entries(r.layout.ports)) {
      const pg = portAssembly(k, xy, p, q);
      root.add(pg);
      pickables.push(pg);
    }
  }
  const gantries = new Map<string, GantryParts>();
  const sampleIds = Object.keys(r.steps[0]?.physics?.samples ?? {});
  const sampleIdx = new Map(sampleIds.map((s, k) => [s, k]));
  const samplesIM = r.layout ? samplesMesh(sampleIds, p) : null;
  if (samplesIM) { root.add(samplesIM); pickables.push(samplesIM); }
  const samplePos = new Map<string, THREE.Vector3>();
  const tmpM = new THREE.Matrix4(), white = new THREE.Color(0x5a5a5e), lit = new THREE.Color(0xf0f0f0);
  const ensureGantry = (key: string, bay: string, group: string | null) => {
    let gp = gantries.get(key);
    if (!gp) {
      const groups = [...new Set(Object.values(((r.config.partition as { groups?: Record<string, string> } | undefined)?.groups) ?? {}))].sort();
      const level = group ? Math.max(0, groups.indexOf(group)) : 0;
      gp = gantryAssembly(key, bayEnvelope(r, bay), level, p, q);
      gantries.set(key, gp);
      root.add(gp.group);
      pickables.push(gp.group);
    }
    return gp;
  };
  const sps = specs(r);
  const systems = new Map<string, SystemParts>();
  sps.forEach((s, k) => {
    const sp = systemAssembly(s.sid, s.kind, k, p, s.store ?? null, s.store ? chamberPos.get(s.store) ?? null : null);
    systems.set(s.sid, sp);
    root.add(sp.group);
    pickables.push(sp.head);
    if (sp.store) pickables.push(sp.store);
  });
  if (sps.some((s) => s.kind === 'distributed')) {  // remote sensor pods of distributed systems at their sensor chambers
    for (const s of sps.filter((x) => x.kind === 'distributed')) {
      for (const c of s.sensors ?? []) {
        const pos = chamberPos.get(c);
        if (!pos) continue;
        const [x, , z] = chamberFloor(pos);
        const pod = new THREE.Group();
        const dome = new THREE.Mesh(new THREE.SphereGeometry(0.11, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2), p.steel);
        dome.position.set(0, FLOOR_Y + 1.2, 0);
        pod.add(box(0.07, 1.1, 0.07, p.darkSteel, 0, FLOOR_Y + 0.55, 0), cyl(0.13, 0.05, p.graphite, 0, FLOOR_Y + 1.17, 0, 16), dome,
          box(0.16, 0.06, 0.16, p.graphite, 0, FLOOR_Y + 0.03, 0));
        pod.position.set(x + 0.5, 0, z + PHYS.CH + 0.4);  // middle of the +z side: clear of corner apparatus and the neighbour's manifold
        tag(pod, 'B', 2, `system ${s.sid} remote sensor at ${c}`, { kind: 'sensor', id: `${s.sid}:sensor:${c}` });
        root.add(pod);
        pickables.push(pod);
      }
    }
  }
  const conduitGroup = new THREE.Group();
  const conduitParts = conduitAssembly(chamberPos, p);
  conduitGroup.add(conduitParts.terminals, conduitParts.lines);
  root.add(conduitGroup);
  const cidIdx = new Map(r.chambers.map((c, k) => [c.cid, k]));
  const stepT = new Map(r.steps.map((s, k) => [s.t, k]));
  void stepT;

  const apply: Lab['apply'] = (i, frac, opts) => {
    const s: LabStep = r.steps[i];
    const nx: LabStep | undefined = frac > 0 ? r.steps[i + 1] : undefined;
    r.chambers.forEach((c, k) => {
      const parts = chambers.get(c.cid)!;
      applyChamber(parts, 1 - s.shutter[k], s.activity[k], s.memory[k]);
      const hit = opts.events.has(c.cid);
      (parts.ring.material as THREE.MeshBasicMaterial).opacity = hit ? 0.9 : 0;
    });
    const ph = s.physics, phn = nx?.physics;
    if (ph) {
      for (const [key, g] of Object.entries(ph.gantries)) {
        const gp = ensureGantry(key, g.bay ?? key, g.group ?? null);
        const tip = phn?.gantries[key] ? lerp3(g.tip as V3, phn.gantries[key].tip as V3, frac) : (g.tip as V3);
        applyGantry(gp, physToView(tip), g.health, g.failed);
      }
      const carried = new Set(Object.values(ph.gantries).map((g) => g.carrying).filter(Boolean));
      if (samplesIM) {
        for (const [sid, pos] of Object.entries(ph.samples)) {
          const k = sampleIdx.get(sid);
          if (k === undefined) continue;
          const pp = phn?.samples[sid] ? lerp3(pos as V3, phn.samples[sid] as V3, frac) : (pos as V3);
          const v = new THREE.Vector3(...physToView(pp));
          samplePos.set(sid, v);
          samplesIM.setMatrixAt(k, tmpM.makeTranslation(v.x, v.y, v.z));
          samplesIM.setColorAt(k, carried.has(sid) ? lit : white);  // a carried sample is drawn light
        }
        samplesIM.instanceMatrix.needsUpdate = true;
        if (samplesIM.instanceColor) samplesIM.instanceColor.needsUpdate = true;
      }
    }
    if (s.science) {
      sps.forEach((spec, k) => {
        const st = s.science![spec.sid];
        const sp = systems.get(spec.sid);
        if (!st || !sp) return;
        const storeOpen = spec.store ? (s.shutter[cidIdx.get(spec.store) ?? -1] ?? 1) >= 0.5 : true;
        applySystem(sp, st, k, chamberPos, storeOpen, opts.coverage, spec.kind);
      });
    }
    conduitGroup.visible = opts.conduits;
    if (opts.conduits) conduitParts.update(s.conduits, new Set(Object.keys(s.conduits).filter((k) => opts.events.has(k))));
  };

  const focus: Lab['focus'] = (sel) => {
    if (sel.kind === 'chamber') { const c = chamberPos.get(sel.id); return c ? new THREE.Vector3(...chamberFloor(c)) : null; }
    if (sel.kind === 'gantry') { const g = gantries.get(sel.id); return g ? g.carriage.position.clone() : null; }
    if (sel.kind === 'sample') { const v = samplePos.get(sel.id); return v ? v.clone() : null; }
    if (sel.kind === 'port') { const xy = r.layout?.ports[sel.id]; return xy ? new THREE.Vector3(...planeToView(xy)) : null; }
    const [sid] = sel.id.split(':');
    const sp = systems.get(sid);
    if (!sp) return null;  // the visual centre of the sensor head / store, not its floor-level origin
    const o = sel.kind === 'store' && sp.store ? sp.store : sp.head;
    o.updateMatrixWorld(true);
    return new THREE.Box3().setFromObject(o).getCenter(new THREE.Vector3());
  };

  root.traverse((o) => { const L = o.userData.layer as Layer | undefined; if (L && o.parent && o.parent.userData.layer !== L) layers[L].push(o); });

  const signature: Lab['signature'] = (i) => {  // layer A/B transforms that must not depend on the quality level
    apply(i, 0, { coverage: true, conduits: true, events: new Set() });
    root.updateMatrixWorld(true);
    const out: Record<string, number[]> = {};
    for (const [k, g] of gantries) out[`gantry:${k}`] = g.carriage.position.toArray();
    for (const [k, v] of samplePos) out[`sample:${k}`] = v.toArray();
    for (const [k, c] of chambers) {
      out[`louvres:${k}`] = Array.from(c.louvres.instanceMatrix.array as Float32Array).slice(0, 16).map((v) => Math.round(v * 1e6) / 1e6);
      out[`activity:${k}`] = [(c.activity.material as THREE.MeshStandardMaterial).emissiveIntensity, c.memory.scale.y];
    }
    for (const [k, sp] of systems) out[`system:${k}`] = [...sp.head.position.toArray(), sp.coverage.children.length, sp.slots?.count ?? -1, sp.pending.children.length];
    out.conduits = [conduitParts.lines.userData.pairs ?? 0, conduitParts.lines.geometry.drawRange.count];
    return out;
  };

  const dispose = () => root.traverse((o) => {
    const m = o as THREE.Mesh;
    m.geometry?.dispose();
    const mat = m.material as THREE.Material | THREE.Material[] | undefined;
    if (Array.isArray(mat)) mat.forEach((x) => x.dispose()); else mat?.dispose();
  });
  return { root, layers, pickables, apply, focus, dispose, signature };
}
