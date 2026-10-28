// XENO ECOSYSTEM — the XENOSCIENCE megastructure as a navigable space, built procedurally with Three.js instancing.
//
// Two kinds of object, kept apart on purpose:
//   * STATIC ARCHITECTURE (layer C of the lab views): trusses, rings, rails, towers, manipulators, chambers, domes, arrays, rock. It is seeded and
//     deterministic, it makes no scientific claim, and the interface labels it as architecture.
//   * SIMULATION-DRIVEN OBJECTS: the habitat arena (resource field, alteration fields, the two operational configurations, firing), the power
//     reserve gauge, the resource carriers, the processing stockpile, the observation-array pulses and the subsurface trial chambers. Their
//     appearance is a pure function of a MEOS record at a tick (``Arena.setFrame``, ``Trials.set``); nothing here advances any state.
//
// The functional organisation follows the supplied drawing: surface layer (observation / power / habitat), intermediate layer (processing /
// transport), core layer (experiment / analysis) and a deep subsurface layer, around one vertical shaft.
import * as THREE from 'three';
import type { EntityFrame, Frame, Label } from './meosApi';
import { buildBodies, type BodySet } from './bodies';
import { applyRanges, chunkBatch, chunkLines } from './lod';
import { buildPebbles, buildRocks, buildTerrain, type Terrain } from './terrain';
import type { ChunkedField } from './lod';

export type Quality = 'performance' | 'balanced' | 'high';
let _dust: THREE.DataTexture | null = null;
/** A soft round sprite for the suspended dust (so that a particle near the camera is a speck of light and not a square). */
function dustSprite(): THREE.Texture {
  if (_dust) return _dust;
  const N = 32, d = new Uint8Array(N * N * 4);
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const r = Math.hypot(x - N / 2 + 0.5, y - N / 2 + 0.5) / (N / 2), a = Math.max(0, 1 - r), o = (y * N + x) * 4;
    d[o] = d[o + 1] = d[o + 2] = 255; d[o + 3] = Math.round(255 * Math.min(1, a * 1.6));
  }
  _dust = new THREE.DataTexture(d, N, N, THREE.RGBAFormat); _dust.needsUpdate = true;
  return _dust;
}
export const DENSITY: Record<Quality, number> = { performance: 0.3, balanced: 0.65, high: 1 };

export const WORLD = {
  pit: 34, depth: 128,
  levels: { surface: 0, intermediate: -34, core: -68, subsurface: -104 },
  habitat: new THREE.Vector3(-66, 0, 16), habitatR: 17, cell: 1.0,
  depot: new THREE.Vector3(-62, 0, -46), processing: new THREE.Vector3(64, 0, -22), array: new THREE.Vector3(54, 0, 52), expansion: new THREE.Vector3(20, 0, -78),
} as const;

export const ANNOTATIONS: Array<{ id: string; text: string; at: THREE.Vector3 }> = [
  { id: 'A', text: 'A  Research Core', at: new THREE.Vector3(0, 52, 0) },
  { id: 'B', text: 'B  Subsurface Laboratory', at: new THREE.Vector3(0, -88, 0) },
  { id: 'C', text: 'C  Material Processing', at: new THREE.Vector3(64, 20, -22) },
  { id: 'D', text: 'D  Autonomous Power', at: new THREE.Vector3(-62, 14, -46) },
  { id: 'E', text: 'E  Habitat (non-human)', at: new THREE.Vector3(-66, 24, 16) },
  { id: 'F', text: 'F  Transportation Network', at: new THREE.Vector3(-14, 8, 56) },
  { id: 'G', text: 'G  Observation Array', at: new THREE.Vector3(54, 24, 52) },
  { id: 'H', text: 'H  Data & Model Generation', at: new THREE.Vector3(32, 8, 22) },
  { id: 'I', text: 'I  Expansion Zone', at: new THREE.Vector3(20, 12, -78) },
];

export const CAMERA_PRESETS: Record<string, { pos: [number, number, number]; target: [number, number, number]; label: string }> = {
  overview: { pos: [-26, 36, 98], target: [-4, -26, -6], label: 'Overview' },
  core: { pos: [20, -22, 24], target: [-4, -44, -4], label: 'Research Core' },
  habitat: { pos: [-48, 11, 33], target: [-66, 1.2, 16], label: 'Habitat' },
  body: { pos: [-89, 3.2, 15], target: [-104, 3.0, 3], label: 'Experimental Body' },
  observer: { pos: [-104, 4.2, 22], target: [-85, 7.5, 37], label: 'Observation Node' },
  puddle: { pos: [-90, 0.9, 13], target: [-103, 2.6, 2], label: 'Wet Ground' },
  subsurface: { pos: [4, -86, 50], target: [0, -102, 12], label: 'Subsurface Laboratory' },
  array: { pos: [22, 20, 30], target: [54, 9, 52], label: 'Observation Array' },
  socket: { pos: [30, 15, -46], target: [12, 5, -64], label: 'Expansion Socket' },
};

// ---------------------------------------------------------------------------------------------------- helpers
function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const UNIT_CORNERS: Array<[number, number, number]> = [];
for (const x of [-0.5, 0.5]) for (const y of [-0.5, 0.5]) for (const z of [-0.5, 0.5]) UNIT_CORNERS.push([x, y, z]);
const CUBE_EDGES: Array<[number, number]> = [];
for (let i = 0; i < 8; i++) for (let j = i + 1; j < 8; j++) {
  const d = UNIT_CORNERS[i].map((v, k) => (v === UNIT_CORNERS[j][k] ? 0 : 1)).reduce((a: number, b) => a + b, 0);
  if (d === 1) CUBE_EDGES.push([i, j]);
}

const _p = new THREE.Vector3(), _s = new THREE.Vector3(), _q = new THREE.Quaternion(), _m = new THREE.Matrix4(), _c = new THREE.Vector3();
const _up = new THREE.Vector3(0, 1, 0), _d = new THREE.Vector3();

/** A batch of unit-cube instances (position, rotation, scale) with optional drawn edges: one InstancedMesh and one LineSegments per batch. */
export class Boxes {
  count = 0;
  private buf = new Float32Array(16 * 1024);
  private col: number[] = [];
  edges: number[] = [];
  /** the share of boxes that keep their drawn edges: the lines are an expensive primitive, so a lower tier draws fewer of them */
  edgeKeep = 1;
  private tint = false;

  private grow() {
    if ((this.count + 1) * 16 > this.buf.length) { const n = new Float32Array(this.buf.length * 2); n.set(this.buf); this.buf = n; }
  }

  box(cx: number, cy: number, cz: number, sx: number, sy: number, sz: number, q?: THREE.Quaternion, edge = false, shade?: number) {
    this.grow();
    _p.set(cx, cy, cz); _s.set(sx, sy, sz); _q.copy(q ?? _q.identity());
    _m.compose(_p, _q, _s);
    _m.toArray(this.buf, this.count * 16);
    if (shade !== undefined) { this.tint = true; }
    this.col.push(shade ?? 1);
    this.count++;
    if (edge && (this.count * 0.6180339) % 1 < this.edgeKeep) {
      for (const [i, j] of CUBE_EDGES) {
        for (const k of [i, j]) {
          const c = UNIT_CORNERS[k];
          _c.set(c[0] * sx, c[1] * sy, c[2] * sz).applyQuaternion(_q).add(_p);
          this.edges.push(_c.x, _c.y, _c.z);
        }
      }
    }
  }

  /** A beam of square section ``t`` between two points. */
  beam(a: THREE.Vector3, b: THREE.Vector3, t: number, edge = false, shade?: number) {
    _d.subVectors(b, a);
    const len = _d.length();
    if (len < 1e-6) return;
    _q.setFromUnitVectors(_up, _d.multiplyScalar(1 / len));
    const q = _q.clone();
    this.box((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2, t, len, t, q, edge, shade);
  }

  mesh(mat: THREE.Material, geo: THREE.BufferGeometry = new THREE.BoxGeometry(1, 1, 1)): THREE.InstancedMesh | null {
    if (!this.count) return null;
    const m = new THREE.InstancedMesh(geo, mat, this.count);
    m.instanceMatrix.array.set(this.buf.subarray(0, this.count * 16));
    m.instanceMatrix.needsUpdate = true;
    if (this.tint) {
      const c = new THREE.Color();
      for (let i = 0; i < this.count; i++) m.setColorAt(i, c.setScalar(this.col[i]));
      m.instanceColor!.needsUpdate = true;
    }
    m.frustumCulled = false;
    return m;
  }

  /** Like ``mesh`` but, for a large batch, split into spatial chunks that three.js can cull (a single mesh over the whole structure is always drawn in full). */
  chunked(mat: THREE.Material, geo: THREE.BufferGeometry = new THREE.BoxGeometry(1, 1, 1), cell = 56, maxRange = Infinity): THREE.Object3D | null {
    if (this.count <= 600) return this.mesh(mat, geo);
    const g = chunkBatch(geo, mat, this.buf, this.col, this.count, cell, this.tint, maxRange);
    g.userData.heavy = true;
    return g;
  }

  chunkedLines(mat: THREE.LineBasicMaterial, cell = 56, maxRange = Infinity): THREE.Object3D | null {
    if (this.edges.length < 6000) return this.lines(mat);
    const g = chunkLines(this.edges, mat, cell, maxRange);
    g.userData.heavy = true;
    return g;
  }

  lines(mat: THREE.LineBasicMaterial): THREE.LineSegments | null {
    if (!this.edges.length) return null;
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.edges, 3));
    const l = new THREE.LineSegments(g, mat);
    l.frustumCulled = false;
    return l;
  }
}

const v3 = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);

export interface Stats { instances: number; edgeSegments: number; objects: number; byKind: Record<string, number> }

// ---------------------------------------------------------------------------------------------------- materials
function materials() {
  return {
    metal: new THREE.MeshStandardMaterial({ color: 0x9a9da4, metalness: 0.85, roughness: 0.34 }),
    dark: new THREE.MeshStandardMaterial({ color: 0x2b2d31, metalness: 0.7, roughness: 0.46 }),
    plate: new THREE.MeshStandardMaterial({ color: 0xc8cacf, metalness: 0.75, roughness: 0.28 }),
    rock: new THREE.MeshStandardMaterial({ color: 0x6a6c72, metalness: 0.2, roughness: 0.8, flatShading: true }),
    glass: new THREE.MeshStandardMaterial({ color: 0xe6e6e6, metalness: 0, roughness: 0.05, transparent: true, opacity: 0.12, depthWrite: false, side: THREE.DoubleSide }),
    edge: new THREE.LineBasicMaterial({ color: 0xf0f0f2, transparent: true, opacity: 0.5 }),
    edgeDim: new THREE.LineBasicMaterial({ color: 0xb9bcc3, transparent: true, opacity: 0.28 }),
    cable: new THREE.LineBasicMaterial({ color: 0xd4d6db, transparent: true, opacity: 0.4 }),
  };
}
export type Mats = ReturnType<typeof materials>;

// ---------------------------------------------------------------------------------------------------- architecture
export interface Megastructure {
  root: THREE.Group; arena: Arena; trials: Trials; stats: Stats; carriers: Carriers; gauge: Gauge; stockpile: Stockpile; array: ArrayPulse;
  anchors: Record<string, THREE.Vector3>; terrain: Terrain; bodies: BodySet; heavy: THREE.Object3D[];
  /** Per-frame level-of-detail selection for the chunked fields; returns the instances drawn. */
  update(camera: THREE.Vector3): number; dispose(): void;
}

export function buildMegastructure(quality: Quality, seed = 7, env: THREE.Texture | null = null): Megastructure {
  const R = rng(seed);
  const dens = DENSITY[quality];
  const M = materials();
  const root = new THREE.Group();
  root.name = 'xenoscience';
  const owned: Array<{ dispose(): void }> = [...Object.values(M)];
  const stats: Stats = { instances: 0, edgeSegments: 0, objects: 0, byKind: {} };
  const seen = new Set<THREE.BufferGeometry>();
  const add = (kind: string, o: THREE.Object3D | null) => {
    if (!o) return;
    root.add(o);
    stats.objects++;
    let n = 0, seg = 0;
    o.traverse((c) => {
      const im = c as THREE.InstancedMesh, ls = c as THREE.LineSegments;
      if (im.isInstancedMesh) n += im.count;
      if (ls.isLineSegments) seg += ls.geometry.getAttribute('position').count / 2;
      const g = (c as THREE.Mesh).geometry;
      if (g && !seen.has(g)) { seen.add(g); owned.push(g); }
    });
    stats.instances += n; stats.edgeSegments += seg; stats.byKind[kind] = (stats.byKind[kind] ?? 0) + n + seg;
  };
  const metal = new Boxes(), dark = new Boxes(), plate = new Boxes(), rock = new Boxes(), glass = new Boxes(), bolts = new Boxes();
  for (const b of [metal, dark, plate, rock, glass, bolts]) b.edgeKeep = quality === 'high' ? 1 : quality === 'balanced' ? 0.72 : 0.5;
  const joint = (p: THREE.Vector3) => { if (R() < 0.55 * dens) bolts.box(p.x, p.y, p.z, 0.22, 0.22, 0.22); };
  const beam = (b: Boxes, a: THREE.Vector3, c: THREE.Vector3, t: number, edge = false, shade?: number) => { b.beam(a, c, t, edge, shade); joint(a); };
  const lat = (n: number) => Math.max(4, Math.round(n * dens));

  // --- terrain with the central shaft: wet broken rock with puddles (terrain.ts)
  const terrain = buildTerrain(quality, WORLD.pit, owned, env);
  root.add(terrain.group); stats.objects++;
  const wall = new THREE.Mesh(new THREE.CylinderGeometry(WORLD.pit, WORLD.pit - 2, WORLD.depth, 96, 1, true), new THREE.MeshStandardMaterial({ color: 0x27292d, roughness: 1, side: THREE.BackSide }));
  wall.position.y = -WORLD.depth / 2; owned.push(wall.geometry, wall.material as THREE.Material);
  add('terrain', wall);
  const floor = new THREE.Mesh(new THREE.CircleGeometry(WORLD.pit - 2, 64), new THREE.MeshStandardMaterial({ color: 0x141518, roughness: 0.9, metalness: 0.2 }));
  floor.rotation.x = -Math.PI / 2; floor.position.y = -WORLD.depth; owned.push(floor.geometry, floor.material as THREE.Material);
  add('terrain', floor);

  // --- strata of the shaft wall and surface rock
  const nWall = lat(7000);
  for (let i = 0; i < nWall; i++) {
    const a = R() * Math.PI * 2, y = -R() * WORLD.depth, r = WORLD.pit - 1 + (R() - 0.5) * 2.6;
    const sx = 0.8 + R() * 3, sy = 0.3 + R() * 1.4, sz = 0.8 + R() * 3;
    _q.setFromEuler(new THREE.Euler(R() * 0.3, -a + (R() - 0.5) * 0.4, R() * 0.3));
    rock.box(Math.cos(a) * r, y, Math.sin(a) * r, sx, sy, sz, _q.clone(), false, 0.45 + R() * 0.7);
  }
  const nSurf = lat(5200);
  const zones: Array<[THREE.Vector3, number]> = [[v3(-104, 0, 4), 26], [v3(-86, 0, 36), 16], [WORLD.habitat, 24], [WORLD.habitat.clone().add(v3(-8, 0, 40)), 18], [WORLD.depot, 34], [WORLD.processing, 34], [WORLD.array, 28], [WORLD.expansion, 24]];
  for (let i = 0; i < nSurf; i++) {
    const a = R() * Math.PI * 2, r = WORLD.pit + 3 + Math.pow(R(), 1.1) * 150;
    if (zones.some(([c, rad]) => Math.hypot(Math.cos(a) * r - c.x, Math.sin(a) * r - c.z) < rad)) continue;  // building sites stay clear of gravel
    const s = 0.25 + R() * R() * R() * 3.2;
    _q.setFromEuler(new THREE.Euler(R() * 3, R() * 3, R() * 3));
    rock.box(Math.cos(a) * r, s * 0.18, Math.sin(a) * r, s * (0.8 + R()), s * 0.6, s * (0.8 + R()), _q.clone(), false, 0.18 + R() * 0.34);
  }

  // --- the four layers: ring platforms with chords, verticals, diagonals and radial spokes
  const ring = (y: number, r: number, h: number, segs: number, edge: boolean) => {
    const pts = (yy: number) => Array.from({ length: segs }, (_, i) => { const a = (i / segs) * Math.PI * 2; return v3(Math.cos(a) * r, yy, Math.sin(a) * r); });
    const top = pts(y + h / 2), bot = pts(y - h / 2);
    for (let i = 0; i < segs; i++) {
      const j = (i + 1) % segs;
      beam(metal, top[i], top[j], 0.5, edge); beam(metal, bot[i], bot[j], 0.5, edge);
      beam(dark, top[i], bot[i], 0.28);
      beam(dark, i % 2 ? top[i] : bot[i], i % 2 ? bot[j] : top[j], 0.22);
    }
  };
  const levelYs = [WORLD.levels.surface, WORLD.levels.intermediate, WORLD.levels.core, WORLD.levels.subsurface];
  levelYs.forEach((y, k) => {
    ring(y, WORLD.pit + 2, 3.2, 120, true);
    ring(y, WORLD.pit - 6, 2.4, 96, k === 0);
    ring(y, WORLD.pit - 14, 2, 72, false);
    // deck plates
    const plates = lat(160);
    for (let i = 0; i < plates; i++) {
      const a = (i / plates) * Math.PI * 2, r = WORLD.pit - 3.5;
      _q.setFromEuler(new THREE.Euler(0, -a, 0));
      plate.box(Math.cos(a) * r, y - 1.4, Math.sin(a) * r, 5, 0.25, 12, _q.clone(), true);
    }
    // radial spokes and a central hub that leaves the shaft open
    const spokes = lat(24);
    for (let i = 0; i < spokes; i++) {
      const a = (i / spokes) * Math.PI * 2;
      beam(metal, v3(Math.cos(a) * (WORLD.pit - 14), y, Math.sin(a) * (WORLD.pit - 14)), v3(Math.cos(a) * (WORLD.pit + 2), y, Math.sin(a) * (WORLD.pit + 2)), 0.4, true);
    }
  });

  // --- the space frame: nodes (black glossy spheres) and beams filling the shaft between the four layers, the dense lattice of the reference imagery
  const nodes = new Boxes();
  const node = (p: THREE.Vector3) => nodes.box(p.x, p.y, p.z, 1, 1, 1);
  const radii = [12, 17.5, 23, 28.5];
  for (const [k, y0] of [WORLD.levels.surface, WORLD.levels.intermediate, WORLD.levels.core].entries()) {
    const ys = Array.from({ length: 6 }, (_, j) => y0 - 3 - j * 5.4);
    const rings = radii.map((r) => { const n = Math.max(8, Math.round((2 * Math.PI * r) / 5.4)); return Array.from({ length: n }, (_, i) => { const a = (i / n) * Math.PI * 2 + k * 0.1; return { a, r, n }; }); });
    ys.forEach((y, yi) => rings.forEach((ring, ri) => ring.forEach((c, ci) => {
      if (R() > 0.2 + 0.8 * dens) return;
      const p = v3(Math.cos(c.a) * c.r, y, Math.sin(c.a) * c.r);
      node(p);
      const nxt = ring[(ci + 1) % ring.length];
      if (R() < 0.85) beam(R() < 0.5 ? metal : dark, p, v3(Math.cos(nxt.a) * nxt.r, y, Math.sin(nxt.a) * nxt.r), 0.2, R() < 0.2);
      if (yi < ys.length - 1 && R() < 0.8) beam(R() < 0.5 ? metal : dark, p, v3(p.x, y - 5.4, p.z), 0.22, R() < 0.25);
      if (ri < rings.length - 1 && R() < 0.75) {
        const o = rings[ri + 1][Math.round((ci / ring.length) * rings[ri + 1].length) % rings[ri + 1].length];
        beam(dark, p, v3(Math.cos(o.a) * o.r, y, Math.sin(o.a) * o.r), 0.18, R() < 0.15);
      }
      if (yi < ys.length - 1 && R() < 0.3) beam(dark, p, v3(Math.cos(nxt.a) * nxt.r, y - 5.4, Math.sin(nxt.a) * nxt.r), 0.14);
    })));
  }
  const nodeGeo = new THREE.SphereGeometry(0.62, 8, 6);
  const nodeMat = new THREE.MeshStandardMaterial({ color: 0x0b0b0d, metalness: 0.95, roughness: 0.14 });
  const nodeMesh = nodes.chunked(nodeMat, nodeGeo);
  if (nodeMesh) { add('nodes', nodeMesh); owned.push(nodeGeo, nodeMat); }

  // --- the shaft columns: a lattice from the surface to the subsurface layer
  const columns = lat(28);
  for (let i = 0; i < columns; i++) {
    const a = (i / columns) * Math.PI * 2 + 0.05;
    const cx = Math.cos(a), cz = Math.sin(a), r0 = WORLD.pit - 1.2;
    const tx = -cz, tz = cx;
    const seg = 3.2;
    for (let y = 0; y > -WORLD.depth + 6; y -= seg) {
      const legs = [[0.9, 0.9], [-0.9, 0.9], [0.9, -0.9], [-0.9, -0.9]].map(([u, w]) => (yy: number) => v3((r0 + w) * cx + u * tx, yy, (r0 + w) * cz + u * tz));
      legs.forEach((L, k) => beam(metal, L(y), L(y - seg), 0.3, k < 2));
      beam(dark, legs[0](y), legs[3](y - seg), 0.18); beam(dark, legs[1](y), legs[2](y - seg), 0.18);
      beam(dark, legs[0](y), legs[1](y), 0.2); beam(dark, legs[2](y), legs[3](y), 0.2);
    }
  }

  // --- surface lattice towers (the Research Core's gantry) with booms, platforms and hoists
  const towers = lat(10);
  const towerTops: THREE.Vector3[] = [];
  for (let i = 0; i < towers; i++) {
    const a = (i / towers) * Math.PI * 2 + 0.2, r = WORLD.pit + 10 + (i % 2) * 6;
    const cx = Math.cos(a) * r, cz = Math.sin(a) * r, h = 34 + (i % 3) * 8, w = 2.6;
    const seg = 2.8;
    for (let y = 0; y < h; y += seg) {
      const c = [[w, w], [-w, w], [w, -w], [-w, -w]].map(([u, k]) => (yy: number) => v3(cx + u, yy, cz + k));
      c.forEach((L) => beam(metal, L(y), L(y + seg), 0.4, true));
      beam(dark, c[0](y), c[3](y + seg), 0.22); beam(dark, c[1](y), c[2](y + seg), 0.22);
      beam(dark, c[0](y + seg), c[1](y + seg), 0.24); beam(dark, c[2](y + seg), c[3](y + seg), 0.24);
    }
    plate.box(cx, h + 0.4, cz, 7, 0.5, 7, undefined, true);
    const boom = 14 + R() * 12, ba = a + Math.PI / 2 + (R() - 0.5);
    beam(metal, v3(cx, h + 2, cz), v3(cx + Math.cos(ba) * boom, h + 3 + R() * 3, cz + Math.sin(ba) * boom), 0.5, true);
    beam(dark, v3(cx, h + 8, cz), v3(cx + Math.cos(ba) * boom, h + 3, cz + Math.sin(ba) * boom), 0.16);
    towerTops.push(v3(cx, h + 1, cz));
  }
  // gantry bridges between neighbouring towers and across the shaft
  for (let i = 0; i < towerTops.length; i++) {
    const a = towerTops[i], b = towerTops[(i + 1) % towerTops.length];
    beam(metal, a.clone().setY(a.y - 4), b.clone().setY(b.y - 4), 0.7, true);
    beam(dark, a.clone().setY(a.y - 7), b.clone().setY(b.y - 4), 0.2);
  }
  for (let i = 0; i < towerTops.length; i += 2) {
    const o = towerTops[(i + Math.floor(towerTops.length / 2)) % towerTops.length];
    beam(metal, towerTops[i].clone().setY(towerTops[i].y - 10), o.clone().setY(o.y - 10), 0.6, true);
  }

  // --- gantry arches: truss arches spanning over the shaft (static architecture): vertical scale, depth layering and overlapping silhouettes
  const arches = lat(14);
  for (let i = 0; i < arches; i++) {
    const a = (i / arches) * Math.PI + 0.1, r = WORLD.pit + 6, rise = 48 + (i % 3) * 7, segs = 26;
    const at = (f: number, off: number) => {
      const th = f * Math.PI, ca = Math.cos(a), sa = Math.sin(a);
      const u = Math.cos(th) * r, y = Math.sin(th) * rise + off * 0.9, w = off * 0.0;
      return v3(u * ca - w * sa, y, u * sa + w * ca);
    };
    for (let k = 0; k < segs; k++) {
      const f0 = k / segs, f1 = (k + 1) / segs;
      beam(metal, at(f0, 0), at(f1, 0), 0.55, true); beam(metal, at(f0, -3.4), at(f1, -3.4), 0.4, true);
      beam(dark, at(f0, 0), at(f1, -3.4), 0.2); beam(dark, at(f0, -3.4), at(f1, 0), 0.2);
      if (k % 2 === 0) beam(dark, at(f0, 0), at(f0, -3.4), 0.24);
    }
  }

  // --- rails: surface loops and the lines that join the zones, with sleepers and carriages
  const railLine = (pts: THREE.Vector3[], gauge: number, sleepers = true) => {
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1];
      _d.subVectors(b, a);
      const len = _d.length(), n = _d.clone().normalize(), side = v3(-n.z, 0, n.x).multiplyScalar(gauge);
      beam(metal, a.clone().add(side), b.clone().add(side), 0.28, true); beam(metal, a.clone().sub(side), b.clone().sub(side), 0.28, true);
      if (sleepers) for (let s = 0; s < len; s += 1.8) {
        const p = a.clone().addScaledVector(n, s);
        _q.setFromUnitVectors(v3(1, 0, 0), v3(-n.z, 0, n.x).normalize());
        dark.box(p.x, p.y - 0.15, p.z, 0.3, 0.2, gauge * 2.6, _q.clone());
      }
    }
  };
  const circle = (r: number, y: number, n: number) => Array.from({ length: n + 1 }, (_, i) => v3(Math.cos((i / n) * Math.PI * 2) * r, y, Math.sin((i / n) * Math.PI * 2) * r));
  railLine(circle(WORLD.pit + 22, 0.4, lat(72)), 1.2); railLine(circle(WORLD.pit + 30, 0.4, lat(90)), 1.2);
  const hab = WORLD.habitat, dep = WORLD.depot, pro = WORLD.processing, arr = WORLD.array, exp = WORLD.expansion;
  const link = (a: THREE.Vector3, b: THREE.Vector3) => railLine([a.clone().setY(0.4), b.clone().setY(0.4)], 1.1);
  [[dep, hab], [hab, v3(-40, 0, 40)], [pro, v3(40, 0, -10)], [arr, v3(40, 0, 36)], [exp, v3(14, 0, -60)], [v3(40, 0, 36), v3(10, 0, 56)], [v3(14, 0, -60), v3(-10, 0, -56)],
    [v3(-40, 0, 40), v3(-10, 0, 56)], [v3(-10, 0, -56), dep], [v3(40, 0, -10), v3(34, 0, 20)]].forEach(([a, b]) => link(a, b));
  // carriages on the loop rails (static architecture)
  const carriages = lat(46);
  for (let i = 0; i < carriages; i++) {
    const a = R() * Math.PI * 2, r = WORLD.pit + (R() < 0.5 ? 22 : 30);
    _q.setFromEuler(new THREE.Euler(0, -a + Math.PI / 2, 0));
    dark.box(Math.cos(a) * r, 1.2, Math.sin(a) * r, 5 + R() * 3, 1.8, 2.4, _q.clone(), true);
    plate.box(Math.cos(a) * r, 2.4, Math.sin(a) * r, 3, 0.5, 2, _q.clone(), true);
  }

  // --- manipulators hanging into the shaft (three segments with joints)
  const jointGeo = new THREE.SphereGeometry(0.5, 10, 8);
  const joints = new Boxes();
  const arms = lat(120);
  for (let i = 0; i < arms; i++) {
    const a = R() * Math.PI * 2, y = levelYs[i % 4] - 1.6, r = WORLD.pit - 4 - R() * 8;
    let p = v3(Math.cos(a) * r, y, Math.sin(a) * r);
    const dir = v3(-Math.cos(a), 0, -Math.sin(a));
    dark.box(p.x, p.y + 0.5, p.z, 2, 1, 2, undefined, true);
    for (let s = 0; s < 3; s++) {
      const len = 4 + R() * 3.5;
      const q = p.clone().addScaledVector(dir, len * (0.4 + R() * 0.5)).add(v3(0, -len * (s === 0 ? 0.9 : R() * 0.6 - 0.1), 0));
      beam(metal, p, q, 0.5 - s * 0.08, true);
      joints.box(q.x, q.y, q.z, 1, 1, 1);
      p = q;
    }
    dark.box(p.x, p.y - 0.4, p.z, 0.9, 0.8, 0.5, undefined, true);
  }
  const jm = joints.mesh(M.plate, jointGeo);
  if (jm) { add('manipulators', jm); owned.push(jointGeo); }

  // --- hanging experiment chambers (decorative cells with a suspended sample) and their hoists
  const chamberGeo = new THREE.IcosahedronGeometry(1, 1);
  const samples = new Boxes();
  const cables: number[] = [];
  const nCh = lat(70);
  for (let i = 0; i < nCh; i++) {
    const a = R() * Math.PI * 2, r = 5 + R() * (WORLD.pit - 14), y = -8 - R() * (WORLD.depth - 20), s = 2.4 + R() * 3;
    const cx = Math.cos(a) * r, cz = Math.sin(a) * r;
    glass.box(cx, y, cz, s, s, s);
    // the twelve edges of the cell frame
    const corner = (i: number) => v3(cx + (i & 1 ? s / 2 : -s / 2), y + (i & 2 ? s / 2 : -s / 2), cz + (i & 4 ? s / 2 : -s / 2));
    for (let i = 0; i < 8; i++) for (const bit of [1, 2, 4]) if (!(i & bit)) beam(metal, corner(i), corner(i | bit), 0.14, true);
    _q.setFromEuler(new THREE.Euler(R() * 3, R() * 3, R() * 3));
    samples.box(cx, y, cz, s * 0.36, s * 0.3, s * 0.34, _q.clone(), false, 0.4 + R() * 0.5);
    cables.push(cx, y + s / 2, cz, cx + (R() - 0.5) * 2, 0.5, cz + (R() - 0.5) * 2);
  }
  const sm = samples.mesh(M.rock, chamberGeo);
  if (sm) { add('chambers', sm); owned.push(chamberGeo); }

  // --- cables: catenaries between the rings, the towers and the hoists
  const catenary = (a: THREE.Vector3, b: THREE.Vector3, sag: number, n = 14) => {
    for (let i = 0; i < n; i++) {
      const f0 = i / n, f1 = (i + 1) / n;
      const P = (f: number) => v3(a.x + (b.x - a.x) * f, a.y + (b.y - a.y) * f - Math.sin(f * Math.PI) * sag, a.z + (b.z - a.z) * f);
      const p0 = P(f0), p1 = P(f1);
      cables.push(p0.x, p0.y, p0.z, p1.x, p1.y, p1.z);
    }
  };
  const nCab = lat(260);
  for (let i = 0; i < nCab; i++) {
    const a1 = R() * Math.PI * 2, a2 = a1 + (R() - 0.5) * 1.2, k = i % 3, y1 = levelYs[k], y2 = levelYs[k + 1] ?? levelYs[k];
    catenary(v3(Math.cos(a1) * (WORLD.pit - 3), y1, Math.sin(a1) * (WORLD.pit - 3)), v3(Math.cos(a2) * (WORLD.pit - 3), y2 + 2, Math.sin(a2) * (WORLD.pit - 3)), 1 + R() * 3);
  }
  for (let i = 0; i < towerTops.length; i++) catenary(towerTops[i], v3(Math.cos(i) * (WORLD.pit - 2), -2, Math.sin(i) * (WORLD.pit - 2)), 2 + R() * 3, 18);

  // --- habitat domes (ribs, glazing, racks) — E
  const dome = (c: THREE.Vector3, r: number, ribsN: number) => {
    const g = new THREE.Mesh(new THREE.SphereGeometry(r, 48, 20, 0, Math.PI * 2, 0, Math.PI / 2), M.glass);
    g.position.copy(c); owned.push(g.geometry); add('habitat', g);
    const mer = lat(ribsN), par = 7;
    for (let i = 0; i < mer; i++) {
      const a = (i / mer) * Math.PI * 2;
      for (let j = 0; j < 12; j++) {
        const t0 = (j / 12) * (Math.PI / 2), t1 = ((j + 1) / 12) * (Math.PI / 2);
        const P = (t: number) => v3(c.x + Math.cos(a) * Math.sin(t) * r, c.y + Math.cos(t) * r, c.z + Math.sin(a) * Math.sin(t) * r);
        beam(metal, P(t0), P(t1), 0.24, true);
      }
    }
    for (let k = 1; k <= par; k++) {
      const t = (k / (par + 0.6)) * (Math.PI / 2), rr = Math.sin(t) * r, yy = c.y + Math.cos(t) * r, n = lat(56);
      for (let i = 0; i < n; i++) {
        const a0 = (i / n) * Math.PI * 2, a1 = ((i + 1) / n) * Math.PI * 2;
        beam(metal, v3(c.x + Math.cos(a0) * rr, yy, c.z + Math.sin(a0) * rr), v3(c.x + Math.cos(a1) * rr, yy, c.z + Math.sin(a1) * rr), 0.2, k % 2 === 0);
      }
    }
    // a base ring of plant-like and rack-like fittings (the habitat's non-human fittings; architecture)
    const nf = lat(70);
    for (let i = 0; i < nf; i++) {
      const a = R() * Math.PI * 2, rr = 9 + R() * (r - 11);
      if (c === WORLD.habitat && rr < 10.5) continue;  // the arena's own footprint is kept clear
      const h = 0.8 + R() * 2.4;
      dark.box(c.x + Math.cos(a) * rr, h / 2, c.z + Math.sin(a) * rr, 0.5 + R(), h, 0.5 + R(), undefined, R() < 0.3);
    }
  };
  dome(WORLD.habitat, WORLD.habitatR, 20);
  dome(WORLD.habitat.clone().add(v3(-8, 0, 40)), 13, 14);
  // habitat apron plates
  for (let i = 0; i < lat(40); i++) {
    const a = (i / lat(40)) * Math.PI * 2;
    _q.setFromEuler(new THREE.Euler(0, -a, 0));
    plate.box(WORLD.habitat.x + Math.cos(a) * (WORLD.habitatR + 1.2), 0.2, WORLD.habitat.z + Math.sin(a) * (WORLD.habitatR + 1.2), 3, 0.4, 5, _q.clone(), true);
  }

  // --- autonomous power — D (solar arrays, batteries, regolith heat store)
  const nPan = 10 * 14;
  for (let i = 0; i < lat(nPan); i++) {
    const row = Math.floor(i / 14), col = i % 14;
    const px = dep.x - 24 + col * 4.4, pz = dep.z - 14 + row * 5.6;
    _q.setFromEuler(new THREE.Euler(-0.55, 0, 0));
    plate.box(px, 2.2, pz, 4, 0.12, 4.8, _q.clone(), true, 0.55);
    dark.box(px, 1, pz + 1.2, 0.2, 2, 0.2);
  }
  const bat = new Boxes(); const batGeo = new THREE.CylinderGeometry(1, 1, 1, 16);
  for (let i = 0; i < lat(26); i++) bat.box(dep.x + 12 + (i % 6) * 3.2, 2.2, dep.z + 16 + Math.floor(i / 6) * 3.2, 1.3, 4.4, 1.3, undefined, false, 0.7);
  const bm = bat.mesh(M.plate, batGeo); if (bm) { add('power', bm); owned.push(batGeo); }

  // --- material processing — C (conveyors, hoppers, containers, cranes)
  for (let l = 0; l < 3; l++) {
    const z0 = pro.z - 10 + l * 9;
    for (let i = 0; i < lat(60); i++) {
      const x = pro.x - 18 + (i / lat(60)) * 36;
      dark.box(x, 1.4 + l * 0.2, z0, 0.7, 0.3, 2.6, undefined, true);
      if (i % 4 === 0) beam(metal, v3(x, 0, z0 + 1.6), v3(x, 1.4 + l * 0.2, z0 + 1.6), 0.25);
    }
    beam(metal, v3(pro.x - 18, 1.5 + l * 0.2, z0 - 1.4), v3(pro.x + 18, 1.5 + l * 0.2, z0 - 1.4), 0.3, true);
    beam(metal, v3(pro.x - 18, 1.5 + l * 0.2, z0 + 1.4), v3(pro.x + 18, 1.5 + l * 0.2, z0 + 1.4), 0.3, true);
  }
  for (let i = 0; i < lat(40); i++) {
    _q.setFromEuler(new THREE.Euler(0, R() * 0.2, 0));
    dark.box(pro.x - 24 + (i % 10) * 4.5, 1.2, pro.z + 14 + Math.floor(i / 10) * 3.4, 3.2, 2.4, 2.6, _q.clone(), true, 0.8);
  }
  for (let i = 0; i < 4; i++) {
    const bx = pro.x - 12 + i * 11;
    for (let y = 0; y < 16; y += 3.2) { beam(metal, v3(bx - 1.5, y, pro.z - 22), v3(bx - 1.5, y + 3.2, pro.z - 22), 0.35, true); beam(metal, v3(bx + 1.5, y, pro.z - 22), v3(bx + 1.5, y + 3.2, pro.z - 22), 0.35, true); beam(dark, v3(bx - 1.5, y, pro.z - 22), v3(bx + 1.5, y + 3.2, pro.z - 22), 0.2); }
    beam(metal, v3(bx, 16, pro.z - 22), v3(bx + 6, 12, pro.z - 12), 0.5, true);
  }

  // --- observation array — G (dishes on lattice masts)
  const dishGeo = new THREE.SphereGeometry(1, 20, 10, 0, Math.PI * 2, 0, 0.95);
  const dishes = new Boxes();
  const dishPos: THREE.Vector3[] = [], dishSize: number[] = [];
  for (let i = 0; i < 12; i++) {
    const x = arr.x - 20 + (i % 4) * 11, z = arr.z - 12 + Math.floor(i / 4) * 12, h = 7 + (i % 3) * 3;
    dishPos.push(v3(x, h + 2, z));
    for (let y = 0; y < h; y += 2.2) for (const [u, w] of [[0.6, 0.6], [-0.6, 0.6], [0.6, -0.6], [-0.6, -0.6]]) beam(metal, v3(x + u, y, z + w), v3(x + u, y + 2.2, z + w), 0.16, y === 0);
    const s = 2.4 + (i % 3) * 0.6;
    dishSize.push(s);
    _q.setFromEuler(new THREE.Euler(-0.9, (i * 0.7) % 6.28, 0));
    dishes.box(x, h + 2, z, s, s, s, _q.clone());
    beam(dark, v3(x, h + 2, z), v3(x, h + 4.4, z), 0.12);
  }
  const dm = dishes.mesh(new THREE.MeshStandardMaterial({ color: 0xd9dbe0, metalness: 0.8, roughness: 0.25, side: THREE.DoubleSide }), dishGeo);
  if (dm) { add('array', dm); owned.push(dishGeo, dm.material as THREE.Material); }

  // --- expansion zone — I (module bays; sockets are empty: nothing is installed)
  const hexGeo = new THREE.CylinderGeometry(1, 1, 1, 6);
  const hexes = new Boxes(); const hexEdges: number[] = [];
  for (let i = 0; i < 9; i++) {
    const a = (i / 9) * Math.PI * 2, c = v3(exp.x + Math.cos(a) * 16, 0, exp.z + Math.sin(a) * 16);
    if (i < 3) hexes.box(c.x, 1.4, c.z, 6, 2.8, 6, undefined, false, 0.7);
    else for (let k = 0; k < 6; k++) { const a0 = (k / 6) * Math.PI * 2, a1 = ((k + 1) / 6) * Math.PI * 2; hexEdges.push(c.x + Math.cos(a0) * 3.2, 0.1, c.z + Math.sin(a0) * 3.2, c.x + Math.cos(a1) * 3.2, 0.1, c.z + Math.sin(a1) * 3.2); }
    link(c, exp);
  }
  const hm = hexes.mesh(M.plate, hexGeo); if (hm) { add('expansion', hm); owned.push(hexGeo); }
  if (hexEdges.length) { const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(hexEdges, 3)); add('expansion', new THREE.LineSegments(g, M.edge)); }

  // --- micro-structure: greeble plating on the rings and columns, and fine grids on the shaft wall and the deck plates (the density of the reference imagery)
  const greeb = new Boxes();
  const nG = lat(16000);
  for (let i = 0; i < nG; i++) {
    const a = R() * Math.PI * 2, y = -R() * (WORLD.depth - 6), r = WORLD.pit - 3 - R() * 22;
    const s2 = 0.18 + R() * R() * 1.3;
    _q.setFromEuler(new THREE.Euler(0, -a + (R() - 0.5), 0));
    greeb.box(Math.cos(a) * r, y, Math.sin(a) * r, s2 * (0.6 + R()), s2 * (0.4 + R()), s2 * (0.6 + R()), _q.clone(), R() < 0.12, 0.25 + R() * 0.75);
  }
  add('greebles', greeb.chunked(M.plate, undefined, 40, 105)); add('greebles edges', greeb.chunkedLines(M.edgeDim, 40, 105));
  const grid: number[] = [];
  const step = 2.2;
  for (let y = 0; y > -WORLD.depth; y -= step) for (let i = 0; i < 96; i++) {
    const a0 = (i / 96) * Math.PI * 2, a1 = ((i + 1) / 96) * Math.PI * 2, rr = WORLD.pit - 2.4;
    grid.push(Math.cos(a0) * rr, y, Math.sin(a0) * rr, Math.cos(a1) * rr, y, Math.sin(a1) * rr);
  }
  for (let i = 0; i < 128; i++) { const a = (i / 128) * Math.PI * 2, rr = WORLD.pit - 2.4; grid.push(Math.cos(a) * rr, 0, Math.sin(a) * rr, Math.cos(a) * rr, -WORLD.depth, Math.sin(a) * rr); }
  { const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(grid, 3)); add('wall grid', new THREE.LineSegments(g, M.edgeDim)); }

  // --- flush the batches into instanced meshes and edge lines
  const flush = (kind: string, b: Boxes, mat: THREE.Material, edgeMat: THREE.LineBasicMaterial | null) => { add(kind, b.chunked(mat)); if (edgeMat) add(kind + ' edges', b.chunkedLines(edgeMat)); };
  flush('trusses', metal, M.metal, M.edge); flush('panels', dark, M.dark, M.edgeDim); flush('plates', plate, M.plate, M.edge);
  flush('rock', rock, M.rock, null); flush('glazing', glass, M.glass, null);
  // bolts and joints: the micro-structure that gives the density of the reference imagery
  add('fittings', bolts.chunked(M.plate, undefined, 40, 95));
  if (cables.length) { const cg = chunkLines(cables, M.cable, 56); cg.userData.heavy = true; add('cables', cg); }

  // --- suspended material in the shaft and stars
  const pt = (n: number, spread: () => THREE.Vector3, size: number, op: number) => {
    const a: number[] = [];
    for (let i = 0; i < n; i++) { const p = spread(); a.push(p.x, p.y, p.z); }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(a, 3));
    const mt = new THREE.PointsMaterial({ color: 0xffffff, size, sizeAttenuation: true, transparent: true, opacity: op, depthWrite: false, map: dustSprite(), alphaTest: 0.05 }); owned.push(mt);
    return new THREE.Points(g, mt);
  };
  add('suspended material', pt(lat(19000), () => { const a = R() * 6.283, r = Math.sqrt(R()) * (WORLD.pit - 3); return v3(Math.cos(a) * r, -R() * WORLD.depth, Math.sin(a) * r); }, 0.28, 0.75));
  add('suspended material', pt(lat(9000), () => { const a = R() * 6.283, r = WORLD.pit + R() * 70; return v3(Math.cos(a) * r, R() * 40, Math.sin(a) * r); }, 0.3, 0.55));
  add('sky', pt(900, () => { const a = R() * 6.283, e = R() * 1.2 + 0.1, r = 700; return v3(Math.cos(a) * Math.cos(e) * r, Math.sin(e) * r, Math.sin(a) * Math.cos(e) * r); }, 1.6, 0.8));
  const moon = new THREE.Mesh(new THREE.SphereGeometry(26, 32, 16), new THREE.MeshStandardMaterial({ color: 0xb9bbc0, roughness: 1, emissive: 0x2a2b2e }));
  moon.position.set(-300, 210, -460); owned.push(moon.geometry, moon.material as THREE.Material); add('sky', moon);

  // --- the simulation-driven parts
  // wet rocks around the experimental bodies and bodies themselves
  const rocks = buildRocks([{ x: -104, z: 4, r: 26, n: lat(260) }, { x: -86, z: 36, r: 16, n: lat(110) }, { x: -92, z: 14, r: 7, n: lat(80) }, { x: -80, z: -6, r: 14, n: lat(70) }], terrain.heightAt, env, owned, quality === 'high' ? 4 : quality === 'balanced' ? 3 : 2, [{ x: -104, z: 4, r: 16 }, { x: -92, z: 12, r: 9 }, { x: -86, z: 36, r: 7 }]);
  const addField = (kind: string, f: ChunkedField) => { root.add(f.group); stats.objects++; stats.instances += f.instances; stats.byKind[kind] = f.instances; };  // a field is counted once, not once per level of detail
  addField('rocks (wet)', rocks);
  const peb = quality === 'performance' ? 0.15 : quality === 'balanced' ? 0.6 : 1;
  const gravel = buildPebbles([{ x: -104, z: 4, r: 30, n: Math.round(9000 * peb) }, { x: -86, z: 36, r: 18, n: Math.round(3500 * peb) }, { x: -92, z: 14, r: 10, n: Math.round(2500 * peb) }], terrain.heightAt, env, owned);
  addField('gravel (wet)', gravel);
  const bodies = buildBodies(quality, env, terrain.heightAt);
  root.add(bodies.group); stats.objects++;
  const arena = buildArena(14, M, owned);
  arena.group.position.copy(WORLD.habitat).add(v3(0, 0.15, 0));
  root.add(arena.group);
  const trials = buildTrials(M, owned);
  trials.group.position.set(0, WORLD.levels.subsurface - 0.5, 0);
  root.add(trials.group);
  const gauge = buildGauge(M, owned); gauge.group.position.copy(dep).add(v3(-18, 0, 12)); root.add(gauge.group);
  const stock = buildStockpile(M, owned); stock.group.position.copy(pro).add(v3(22, 0, 0)); root.add(stock.group);
  const carriers = buildCarriers(M, owned, arena); root.add(carriers.group);
  const arrayPulse = buildArrayPulse(dishPos, dishSize, dm, owned); root.add(arrayPulse.group);
  // light structure: static annotations of the nine zones are drawn by the view (sprites), not here.
  const anchors: Record<string, THREE.Vector3> = {
    A: v3(0, 0, 0), B: v3(0, WORLD.levels.subsurface, 0), C: pro.clone(), D: dep.clone(), E: WORLD.habitat.clone(), F: v3(-20, 0, 62), G: arr.clone(), H: v3(36, 0, 24), I: exp.clone(),
  };
  // what a planar reflection does not need to draw: the distant space frame, cables and points (hidden during the puddles' reflection render)
  const heavy = root.children.filter((o) => o.userData.heavy === true || ((o as THREE.InstancedMesh).isInstancedMesh && (o as THREE.InstancedMesh).count > 600) || (o as THREE.LineSegments).isLineSegments || (o as THREE.Points).isPoints);
  terrain.setReflectionHidden(heavy);
  const rangeGroups = root.children.filter((o) => Number.isFinite(o.userData.maxRange));
  return { root, arena, trials, stats, carriers, gauge, stockpile: stock, array: arrayPulse, anchors, terrain, bodies, heavy, update: (cam) => { terrain.update(cam); applyRanges(rangeGroups, cam); return rocks.update(cam) + gravel.update(cam); }, dispose: () => { owned.forEach((o) => o.dispose()); } };
}

// ---------------------------------------------------------------------------------------------------- the habitat arena
export interface Arena {
  group: THREE.Group; n: number; entities: Record<'A1' | 'A2', THREE.Group>; sensors: Record<'A1' | 'A2', THREE.Mesh>;
  cellCenter(x: number, y: number, target?: THREE.Vector3): THREE.Vector3; local(x: number, y: number): THREE.Vector3;
  setFrame(f: Frame, R: Float32Array, M1: Float32Array, M2: Float32Array): void; pickables: THREE.Object3D[];
}

function machine(kind: 'A1' | 'A2', owned: Array<{ dispose(): void }>) {
  const g = new THREE.Group();
  g.userData = { entity: kind };
  const em = new THREE.MeshStandardMaterial({ color: 0xcfd1d6, metalness: 0.8, roughness: 0.3, emissive: 0xffffff, emissiveIntensity: 0 });
  const dk = new THREE.MeshStandardMaterial({ color: 0x2c2e33, metalness: 0.7, roughness: 0.45 });
  owned.push(em, dk);
  const geos: THREE.BufferGeometry[] = [];
  const mesh = (geo: THREE.BufferGeometry, mat: THREE.Material, x: number, y: number, z: number) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.userData = { entity: kind }; g.add(m); geos.push(geo); return m; };
  if (kind === 'A1') {
    mesh(new THREE.CylinderGeometry(0.46, 0.5, 0.18, 24), dk, 0, 0.09, 0);
    mesh(new THREE.BoxGeometry(0.7, 0.5, 0.7), dk, 0, 0.43, 0);
    mesh(new THREE.CylinderGeometry(0.16, 0.2, 0.9, 12), em, 0, 1.1, 0);
    mesh(new THREE.SphereGeometry(0.34, 20, 12, 0, Math.PI * 2, 0, 1.4), em, 0, 1.6, 0);
    mesh(new THREE.TorusGeometry(0.42, 0.04, 8, 28), em, 0, 0.14, 0).rotation.x = Math.PI / 2;
  } else {
    mesh(new THREE.BoxGeometry(0.62, 0.16, 0.9), dk, 0, 0.08, 0);
    mesh(new THREE.CylinderGeometry(0.1, 0.14, 0.7, 10), dk, 0, 0.5, 0);
    mesh(new THREE.BoxGeometry(0.15, 0.15, 0.9), em, 0, 0.92, 0.2).rotation.x = -0.4;
    mesh(new THREE.ConeGeometry(0.1, 0.34, 10), em, 0, 0.95, 0.62).rotation.x = Math.PI / 2 - 0.4;
    mesh(new THREE.SphereGeometry(0.18, 14, 10), em, 0, 0.9, 0);
  }
  geos.forEach((x) => owned.push(x));
  return { g, em };
}

function buildArena(n: number, M: Mats, owned: Array<{ dispose(): void }>): Arena {
  const group = new THREE.Group();
  group.name = 'meos-arena';
  const cs = WORLD.cell, half = (n * cs) / 2;
  const local = (x: number, y: number) => new THREE.Vector3(x * cs - half + cs / 2, 0, y * cs - half + cs / 2);
  // platform: a plinth and a grid of floor plates
  const plinth = new THREE.Mesh(new THREE.CylinderGeometry(half * 1.55, half * 1.62, 0.5, 64), new THREE.MeshStandardMaterial({ color: 0x2a2c30, metalness: 0.8, roughness: 0.4 }));
  plinth.position.y = -0.3; owned.push(plinth.geometry, plinth.material as THREE.Material); group.add(plinth);
  const ringEdge = new THREE.Mesh(new THREE.TorusGeometry(half * 1.55, 0.07, 8, 96), M.plate); ringEdge.rotation.x = Math.PI / 2; ringEdge.position.y = -0.04; owned.push(ringEdge.geometry); group.add(ringEdge);
  const floorGeo = new THREE.BoxGeometry(cs * 0.94, 0.06, cs * 0.94);
  const floor = new THREE.InstancedMesh(floorGeo, new THREE.MeshStandardMaterial({ color: 0x3a3c41, metalness: 0.6, roughness: 0.5 }), n * n);
  const resGeo = new THREE.BoxGeometry(cs * 0.62, 1, cs * 0.62);
  const resMat = new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0.5, roughness: 0.35 });
  const res = new THREE.InstancedMesh(resGeo, resMat, n * n);
  const m1Geo = new THREE.PlaneGeometry(cs * 0.86, cs * 0.86), m2Geo = new THREE.RingGeometry(cs * 0.22, cs * 0.4, 16);
  const addMat = (c: number) => new THREE.MeshBasicMaterial({ color: c, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
  const m1 = new THREE.InstancedMesh(m1Geo, addMat(0xffffff), n * n), m2 = new THREE.InstancedMesh(m2Geo, addMat(0xffffff), n * n);
  const rot = new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2, 0, 0));
  const ident = new THREE.Matrix4();
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    const i = y * n + x, p = local(x, y);
    floor.setMatrixAt(i, ident.compose(new THREE.Vector3(p.x, 0.03, p.z), new THREE.Quaternion(), new THREE.Vector3(1, 1, 1)));
    m1.setMatrixAt(i, ident.compose(new THREE.Vector3(p.x, 1.9, p.z), rot, new THREE.Vector3(1, 1, 1)));
    m2.setMatrixAt(i, ident.compose(new THREE.Vector3(p.x, 2.3, p.z), rot, new THREE.Vector3(1, 1, 1)));
    res.setMatrixAt(i, ident.compose(new THREE.Vector3(p.x, 0.07, p.z), new THREE.Quaternion(), new THREE.Vector3(1, 0.001, 1)));
    for (const mm of [m1, m2, res]) mm.setColorAt(i, new THREE.Color(0, 0, 0));
  }
  for (const mm of [floor, res, m1, m2]) { mm.instanceMatrix.needsUpdate = true; mm.frustumCulled = false; group.add(mm); owned.push(mm.geometry, mm.material as THREE.Material); }
  const ents: Record<'A1' | 'A2', THREE.Group> = { A1: null as never, A2: null as never };
  const sensors = {} as Record<'A1' | 'A2', THREE.Mesh>;
  const mats: Record<'A1' | 'A2', THREE.MeshStandardMaterial> = {} as never;
  const pickables: THREE.Object3D[] = [];
  for (const k of ['A1', 'A2'] as const) {
    const { g, em } = machine(k, owned);
    g.scale.setScalar(1.7);
    ents[k] = g; mats[k] = em; group.add(g); g.traverse((o) => { if ((o as THREE.Mesh).isMesh) pickables.push(o); });
    const s = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.0, depthWrite: false, side: THREE.DoubleSide }));
    s.rotation.x = -Math.PI / 2; s.position.y = 0.08; s.userData = { sensor: k }; owned.push(s.geometry, s.material as THREE.Material); sensors[k] = s; group.add(s);
  }
  // a thin dome of lamps over the arena (architecture of the habitat chamber)
  const lamps = new THREE.PointLight(0xffffff, 26, 40, 1.6); lamps.position.set(0, 9, 0); group.add(lamps);
  const tmp = new THREE.Matrix4(), col = new THREE.Color(), pos = new THREE.Vector3(), sc = new THREE.Vector3(), q0 = new THREE.Quaternion();
  const shade = (a: number) => col.setScalar(Math.max(0, Math.min(1, a)));
  const place = (e: EntityFrame, g: THREE.Group, em: THREE.MeshStandardMaterial, dir: number) => {
    g.visible = e.present;
    const p = local(e.x, e.y);
    g.position.set(p.x, 0.06, p.z);
    g.rotation.y = dir;
    em.emissiveIntensity = e.active > 0 ? 0.95 : e.cool > 0 ? 0.22 : 0.05;
    em.color.setScalar(e.active > 0 ? 1 : 0.74);
  };
  const setFrame = (f: Frame, R: Float32Array, M1: Float32Array, M2: Float32Array) => {
    for (let i = 0; i < n * n; i++) {
      const x = i % n, y = (i / n) | 0, p = local(x, y);
      const r = R[i];
      pos.set(p.x, 0.07 + r * 0.55, p.z); sc.set(1, Math.max(0.001, r * 1.1), 1);
      tmp.compose(pos, q0, sc); res.setMatrixAt(i, tmp); res.setColorAt(i, shade(0.1 + r * 0.62));
      m1.setColorAt(i, shade(Math.min(1, M1[i] * 5)));
      m2.setColorAt(i, shade(Math.min(1, M2[i] * 5)));
    }
    for (const mm of [res, m1, m2]) { mm.instanceColor!.needsUpdate = true; }
    res.instanceMatrix.needsUpdate = true;
    place(f.A1, ents.A1, mats.A1, 0);
    place(f.A2, ents.A2, mats.A2, Math.atan2(f.A1.x - f.A2.x, f.A1.y - f.A2.y));
  };
  return { group, n, entities: ents, sensors, cellCenter: (x, y, t = new THREE.Vector3()) => t.copy(local(x, y)).applyMatrix4(group.matrixWorld), local, setFrame, pickables };
}

// ---------------------------------------------------------------------------------------------------- power gauge, stockpile, carriers, array pulses
export interface Gauge { group: THREE.Group; set(level: number, infinite: boolean): void }
function buildGauge(M: Mats, owned: Array<{ dispose(): void }>): Gauge {
  const g = new THREE.Group();
  const shell = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.5, 12, 24, 1, true), M.glass); shell.position.y = 6; g.add(shell);
  const fillGeo = new THREE.CylinderGeometry(1.2, 1.2, 1, 24);
  const fillMat = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0.5, metalness: 0.2, roughness: 0.4 });
  const fill = new THREE.Mesh(fillGeo, fillMat); g.add(fill);
  const cap = new THREE.Mesh(new THREE.CylinderGeometry(1.7, 1.7, 0.3, 24), M.plate); cap.position.y = 12.1; g.add(cap);
  const base = cap.clone(); base.position.y = -0.1; g.add(base);
  owned.push(shell.geometry, fillGeo, fillMat, cap.geometry);
  return { group: g, set(level, infinite) { const h = Math.max(0.02, Math.min(1, level)) * 11.6; fill.scale.y = h; fill.position.y = h / 2; fillMat.emissiveIntensity = 0.15 + 0.6 * level; fillMat.opacity = infinite ? 0.5 : 1; fillMat.transparent = infinite; } };
}
export interface Stockpile { group: THREE.Group; set(level: number): void }
function buildStockpile(M: Mats, owned: Array<{ dispose(): void }>): Stockpile {
  const g = new THREE.Group();
  const geo = new THREE.ConeGeometry(1, 1, 7); const mat = new THREE.MeshStandardMaterial({ color: 0x6c6e73, roughness: 1, flatShading: true });
  owned.push(geo, mat);
  const cones: THREE.Mesh[] = [];
  for (let i = 0; i < 6; i++) { const c = new THREE.Mesh(geo, mat); c.position.set((i % 3) * 5 - 5, 0, Math.floor(i / 3) * 6 - 3); g.add(c); cones.push(c); }
  void M;
  return { group: g, set(level) { cones.forEach((c, i) => { const s = Math.max(0.05, level) * (3 + (i % 3)); c.scale.set(s * 1.4, s * 2, s * 1.4); c.position.y = s; }); } };
}
export interface Carriers { group: THREE.Group; set(items: Array<{ progress: number; amount: number }>): void; path: THREE.Vector3[] }
function buildCarriers(M: Mats, owned: Array<{ dispose(): void }>, arena: Arena): Carriers {
  const g = new THREE.Group();
  const geo = new THREE.BoxGeometry(1, 1, 1); const mat = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0.4, metalness: 0.4, roughness: 0.4 });
  owned.push(geo, mat);
  const pool: THREE.Mesh[] = [];
  for (let i = 0; i < 24; i++) { const m = new THREE.Mesh(geo, mat); m.visible = false; g.add(m); pool.push(m); }
  // the transfer path: the power depot, along the rail to the habitat, to the arena
  const path = [WORLD.depot.clone().setY(1.6), v3(-58, 1.6, -22), WORLD.habitat.clone().add(v3(0, 1.6, -14)), WORLD.habitat.clone().add(v3(0, 1.6, -7))];
  void M; void arena;
  const seg = path.slice(1).map((p, i) => p.distanceTo(path[i])), total = seg.reduce((a, b) => a + b, 0);
  return {
    group: g, path,
    set(items) {
      pool.forEach((m, i) => {
        const it = items[i];
        m.visible = !!it;
        if (!it) return;
        let d = Math.max(0, Math.min(1, it.progress)) * total, k = 0;
        while (k < seg.length - 1 && d > seg[k]) { d -= seg[k]; k++; }
        m.position.lerpVectors(path[k], path[k + 1], d / seg[k]);
        const s = 0.7 + Math.min(1.4, it.amount * 1.2);
        m.scale.set(s, s * 0.7, s);
      });
    },
  };
}
export interface ArrayPulse {
  group: THREE.Group; count: number; set(on: boolean, intensity: number): void;
  /** Observation Array: every dish is turned toward ``target``; the first ``active`` lamps are lit (flashing on a sampled tick), the rest are dark. */
  aim(target: THREE.Vector3, sampling: boolean, active: number, intensity: number): void;
}
function buildArrayPulse(dishes: THREE.Vector3[], sizes: number[], mesh: THREE.InstancedMesh | null, owned: Array<{ dispose(): void }>): ArrayPulse {
  const g = new THREE.Group();
  const geo = new THREE.SphereGeometry(0.34, 12, 8), mat = new THREE.MeshBasicMaterial({ color: 0xffffff }); owned.push(geo, mat);
  const lamps = dishes.map((p) => { const m = new THREE.Mesh(geo, mat.clone()); m.position.copy(p).add(v3(0, 2.6, 0)); g.add(m); return m; });
  const M = new THREE.Matrix4(), Q = new THREE.Quaternion(), S = new THREE.Vector3(), dir = new THREE.Vector3();
  return {
    group: g, count: dishes.length,
    set(on, intensity) { lamps.forEach((m) => { (m.material as THREE.MeshBasicMaterial).color.setScalar(on ? 0.35 + 0.65 * intensity : 0.12); }); },
    aim(target, sampling, active, intensity) {
      dishes.forEach((p, i) => {
        if (mesh) { dir.subVectors(target, p).normalize(); Q.setFromUnitVectors(_up, dir); mesh.setMatrixAt(i, M.compose(p, Q, S.setScalar(sizes[i]))); }
        (lamps[i].material as THREE.MeshBasicMaterial).color.setScalar(i < active ? (sampling ? 0.35 + 0.65 * intensity : 0.2) : 0.05);
      });
      if (mesh) mesh.instanceMatrix.needsUpdate = true;
    },
  };
}

// ---------------------------------------------------------------------------------------------------- the subsurface trial chambers (B)
export interface Trial { label: string; status: Label | null; removed: string[]; note?: string }
export interface Trials { group: THREE.Group; slots: number; set(t: Array<Trial | null>): void; positions: THREE.Vector3[]; pickables: THREE.Object3D[] }
function buildTrials(M: Mats, owned: Array<{ dispose(): void }>): Trials {
  const g = new THREE.Group();
  const slots = 12, rr = WORLD.pit - 9;
  const positions: THREE.Vector3[] = [];
  const cells: Array<{ body: THREE.Mesh; a1: THREE.Mesh; a2: THREE.Mesh; link: THREE.Mesh; mats: THREE.MeshStandardMaterial[]; lamp: THREE.Mesh }> = [];
  const frameGeo = new THREE.BoxGeometry(5, 5, 5), edges = new THREE.EdgesGeometry(frameGeo), tile = new THREE.BoxGeometry(3.6, 0.2, 3.6);
  const blk = new THREE.BoxGeometry(0.8, 1.2, 0.8), bar = new THREE.BoxGeometry(0.12, 0.12, 1), lampG = new THREE.SphereGeometry(0.25, 10, 8);
  owned.push(frameGeo, edges, tile, blk, bar, lampG);
  const pickables: THREE.Object3D[] = [];
  for (let i = 0; i < slots; i++) {
    const a = (i / slots) * Math.PI * 2;
    const c = new THREE.Group(); c.position.set(Math.cos(a) * rr, 4.2, Math.sin(a) * rr); c.rotation.y = -a; c.scale.setScalar(1.7); g.add(c);
    positions.push(c.position.clone().add(v3(0, WORLD.levels.subsurface, 0)));
    const body = new THREE.Mesh(frameGeo, M.glass); c.add(body); body.userData = { trial: i }; pickables.push(body);
    c.add(new THREE.LineSegments(edges, M.edge));
    const mk = () => { const m = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0.1, metalness: 0.7, roughness: 0.35 }); owned.push(m); return m; };
    const floor = new THREE.Mesh(tile, M.plate); floor.position.y = -2.3; c.add(floor);
    const m1 = mk(), m2 = mk(), m3 = mk(), m4 = mk();
    const a1 = new THREE.Mesh(blk, m1); a1.position.set(-1.1, -1.5, 0); c.add(a1);
    const a2 = new THREE.Mesh(blk, m2); a2.position.set(1.1, -1.5, 0); c.add(a2);
    const link = new THREE.Mesh(bar, m3); link.rotation.y = Math.PI / 2; link.scale.z = 1.9; link.position.set(0, -1.2, 0); c.add(link);
    const lamp = new THREE.Mesh(lampG, m4); lamp.position.set(0, 1.9, 0); c.add(lamp);
    for (const m of [a1, a2, link, lamp]) m.userData = { trial: i };
    // hoist cable
    const cab = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute([0, 2.5, 0, 0, 14, 0], 3)), M.cable); owned.push(cab.geometry); c.add(cab);
    cells.push({ body, a1, a2, link, mats: [m1, m2, m3, m4], lamp });
  }
  return {
    group: g, slots, positions, pickables,
    set(t) {
      cells.forEach((c, i) => {
        const tr = t[i] ?? null;
        const lvl = !tr || tr.status === null ? 0.06 : tr.status === 'ACTIVE' ? 1 : tr.status === 'DEGRADED' ? 0.42 : 0.08;
        c.mats.forEach((m) => { m.emissiveIntensity = lvl; m.color.setScalar(0.35 + lvl * 0.65); });
        c.a2.visible = !tr || !tr.removed.includes('A2');
        c.link.visible = !tr || !(tr.removed.includes('interaction_channel') || tr.removed.includes('feedback'));
        c.lamp.visible = !!tr;
        c.a1.scale.y = tr?.removed.includes('sensor_resource') ? 0.5 : 1;
      });
    },
  };
}
