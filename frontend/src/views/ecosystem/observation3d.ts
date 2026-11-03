import * as THREE from 'three';
import type { Arena } from './megastructure';
import { FULL_OBSERVATION, type Observation } from './meosApi';

// XENOSCIENCE ECOSYSTEM — the observation array in the 3D scene. The overlay shows which cells of the arena the configured observation can see, by the rule the engine applies when it decides whether an event is
// observed (backend/xzr/meos/analysis.py, ``_observed_cycle_ticks``: a cell is seen if it lies on the sampling lattice, outside the occluder and inside the region). The overlay is a drawing of that rule, not a result:
// the observed state of a run is what the engine returns for the regime, and the tests check that the cells drawn here predict the engine's own count of observed cycles. Picking a cell sets the region or the
// occluder of the observation; changing an observation never changes the run it observes.

export const OBSERVATION_LIMITS = {
  interval: [1, 2, 3, 4, 6, 8, 12], stride: [1, 2, 3, 4], aggregation: [1, 2, 4, 8], window: [12, 24, 48, 96], threshold: [0, 0.05, 0.1, 0.2],
} as const;

/** The cells of an n×n arena that the observation sees (index y·n + x). Only the spatial limits are applied here; the sampling interval, threshold, aggregation and window act on events, not on cells. */
export function seenCells(obs: Partial<Observation>, n: number): boolean[] {
  const o = { ...FULL_OBSERVATION, ...obs }, s = Math.max(1, Math.floor(o.spatial_stride)), [ox, oy] = o.spatial_offset ?? [0, 0];
  const r = o.region, oc = o.occluder;
  const seen: boolean[] = [];
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    const onLattice = (((x - ox) % s) + s) % s === 0 && (((y - oy) % s) + s) % s === 0;
    const occluded = !!oc && oc[0] <= x && x <= oc[2] && oc[1] <= y && y <= oc[3];
    const inRegion = !r || (r[0] <= x && x <= r[2] && r[1] <= y && y <= r[3]);
    seen.push(onLattice && !occluded && inRegion);
  }
  return seen;
}

export const isFullObservation = (obs: Observation): boolean => JSON.stringify(obs) === JSON.stringify(FULL_OBSERVATION);

/** A rectangle from two clicked cells, in the engine's order (x0, y0, x1, y1), inside the grid. */
export function rectFromCells(a: [number, number], b: [number, number], n: number): number[] {
  const c = (v: number) => Math.max(0, Math.min(n - 1, v));
  return [c(Math.min(a[0], b[0])), c(Math.min(a[1], b[1])), c(Math.max(a[0], b[0])), c(Math.max(a[1], b[1]))];
}

/** The nearest cell to a point of the arena's local frame (the cell centres are where ``arena.local`` puts them). */
export function cellFromLocal(arena: Arena, p: THREE.Vector3): [number, number] {
  let best: [number, number] = [0, 0], bd = Infinity;
  for (let y = 0; y < arena.n; y++) for (let x = 0; x < arena.n; x++) {
    const c = arena.local(x, y), d = (c.x - p.x) ** 2 + (c.z - p.z) ** 2;
    if (d < bd) { bd = d; best = [x, y]; }
  }
  return best;
}

export interface ObservationFrame { obs: Observation; overlay: boolean; pending: [number, number] | null }
export interface ObservationLayer {
  group: THREE.Group; floor: THREE.Mesh; tiles: THREE.InstancedMesh; set(f: ObservationFrame): void; cellAt(raycaster: THREE.Raycaster): [number, number] | null; dispose(): void;
}

const outline = (color: number): { line: THREE.LineLoop; geo: THREE.BufferGeometry; mat: THREE.LineBasicMaterial } => {
  const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()]);
  const mat = new THREE.LineBasicMaterial({ color });
  const line = new THREE.LineLoop(geo, mat); line.visible = false; line.frustumCulled = false;
  return { line, geo, mat };
};

export function buildObservationLayer(arena: Arena): ObservationLayer {
  const n = arena.n, group = new THREE.Group(); group.name = 'observation';
  const a = arena.local(0, 0), b = arena.local(n - 1, n - 1), cell = Math.abs(arena.local(1, 0).x - a.x) || Math.abs(arena.local(1, 0).z - a.z) || 1;
  // the picking floor: an invisible plane over the arena (it draws nothing and only answers rays)
  const floorGeo = new THREE.PlaneGeometry(Math.abs(b.x - a.x) + cell, Math.abs(b.z - a.z) + cell);
  const floorMat = new THREE.MeshBasicMaterial({ visible: false });
  const floor = new THREE.Mesh(floorGeo, floorMat); floor.rotation.x = -Math.PI / 2; floor.position.set((a.x + b.x) / 2, 0.14, (a.z + b.z) / 2); floor.userData = { observationFloor: true }; floor.name = 'observation-floor';
  const tileGeo = new THREE.PlaneGeometry(cell * 0.9, cell * 0.9), tileMat = new THREE.MeshBasicMaterial({ color: 0x66b8e0, transparent: true, opacity: 0.3, depthWrite: false, side: THREE.DoubleSide });
  const tiles = new THREE.InstancedMesh(tileGeo, tileMat, n * n); tiles.frustumCulled = false; tiles.name = 'observed-cells';
  const m = new THREE.Matrix4(), q = new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2, 0, 0)), one = new THREE.Vector3(1, 1, 1), zero = new THREE.Vector3(0, 0, 0);
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) { const p = arena.local(x, y); tiles.setMatrixAt(y * n + x, m.compose(new THREE.Vector3(p.x, 0.16, p.z), q, one)); }
  const reg = outline(0x66b8e0), occ = outline(0xd9534f), pend = outline(0xffffff);
  group.add(floor, tiles, reg.line, occ.line, pend.line);
  arena.group.add(group);
  const corners = (r: number[], line: THREE.LineLoop, y: number): void => {
    const h = cell / 2, p0 = arena.local(r[0], r[1]), p1 = arena.local(r[2], r[3]);
    const pts = [[p0.x - h, p0.z - h], [p1.x + h, p0.z - h], [p1.x + h, p1.z + h], [p0.x - h, p1.z + h]];
    const pos = line.geometry.getAttribute('position') as THREE.BufferAttribute;
    pts.forEach((c, i) => pos.setXYZ(i, c[0], y, c[1])); pos.needsUpdate = true; line.visible = true;
  };
  const set = (f: ObservationFrame): void => {
    const o = { ...FULL_OBSERVATION, ...f.obs }, seen = seenCells(o, n);
    tiles.visible = f.overlay;
    for (let i = 0; i < n * n; i++) {
      const x = i % n, y = (i / n) | 0, p = arena.local(x, y);
      tiles.setMatrixAt(i, m.compose(new THREE.Vector3(p.x, 0.16, p.z), q, seen[i] ? one : zero));
    }
    tiles.instanceMatrix.needsUpdate = true;
    if (o.region) corners(o.region, reg.line, 0.2); else reg.line.visible = false;
    if (o.occluder) corners(o.occluder, occ.line, 0.22); else occ.line.visible = false;
    if (f.pending) corners([f.pending[0], f.pending[1], f.pending[0], f.pending[1]], pend.line, 0.24); else pend.line.visible = false;
  };
  const cellAt = (rc: THREE.Raycaster): [number, number] | null => {
    const hit = rc.intersectObject(floor, false)[0];
    return hit ? cellFromLocal(arena, arena.group.worldToLocal(hit.point.clone())) : null;
  };
  const dispose = (): void => { group.removeFromParent(); for (const o of [floorGeo, floorMat, tileGeo, tileMat, tiles, reg.geo, reg.mat, occ.geo, occ.mat, pend.geo, pend.mat]) o.dispose(); };
  return { group, floor, tiles, set, cellAt, dispose };
}
