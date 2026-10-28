// XENO ECOSYSTEM — spatial chunking with distance levels of detail for large fields of repeated objects (gravel, rocks, the batches of the megastructure).
//
// A field is split into cells of a ground grid; each cell is one InstancedMesh per level of detail with its own bounding sphere, so that
//   * three.js culls the cells outside the view (a single instanced mesh over the whole field cannot be culled), and
//   * a cell that is far from the camera is drawn with a cheaper geometry, or not at all.
// The levels are chosen from the distance between the camera and the nearest point of the cell, so the objects near the camera, which carry the picture, are never reduced.
import * as THREE from 'three';

export interface FieldItem { matrix: THREE.Matrix4; shade: number }
export interface FieldLevel { geometry: THREE.BufferGeometry; /** drawn while the nearest point of the cell is closer than this */ range: number }

export interface ChunkedField {
  group: THREE.Group;
  /** Choose the level of every cell for a camera position. Returns the number of instances that will be drawn (for the statistics). */
  update(camera: THREE.Vector3): number;
  chunks: number; instances: number;
  dispose(): void;
}

export function buildChunkedField(items: FieldItem[], levels: FieldLevel[], material: THREE.Material, cell: number, name: string): ChunkedField {
  const group = new THREE.Group();
  group.name = name;
  const cells = new Map<string, FieldItem[]>();
  const p = new THREE.Vector3();
  for (const it of items) {
    p.setFromMatrixPosition(it.matrix);
    const key = `${Math.floor(p.x / cell)}:${Math.floor(p.z / cell)}`;
    let c = cells.get(key);
    if (!c) cells.set(key, (c = []));
    c.push(it);
  }
  const chunks: Array<{ meshes: THREE.InstancedMesh[]; centre: THREE.Vector3; radius: number; count: number }> = [];
  const color = new THREE.Color();
  for (const list of cells.values()) {
    const meshes = levels.map((lv) => {
      const m = new THREE.InstancedMesh(lv.geometry, material, list.length);
      list.forEach((it, i) => { m.setMatrixAt(i, it.matrix); m.setColorAt(i, color.setScalar(it.shade)); });
      m.instanceMatrix.needsUpdate = true; if (m.instanceColor) m.instanceColor.needsUpdate = true;
      m.computeBoundingSphere();  // the cell's own sphere: this is what lets three.js cull it
      m.frustumCulled = true; m.visible = false;
      group.add(m);
      return m;
    });
    const s = meshes[0].boundingSphere!;
    chunks.push({ meshes, centre: s.center.clone(), radius: s.radius, count: list.length });
  }
  const update = (cam: THREE.Vector3): number => {
    let drawn = 0;
    for (const c of chunks) {
      const d = Math.max(0, c.centre.distanceTo(cam) - c.radius);
      let pick = -1;
      for (let i = 0; i < levels.length; i++) if (d < levels[i].range) { pick = i; break; }
      c.meshes.forEach((m, i) => { m.visible = i === pick; });
      if (pick >= 0) drawn += c.count;
    }
    return drawn;
  };
  return {
    group, update, chunks: chunks.length, instances: items.length,
    dispose: () => { levels.forEach((l) => l.geometry.dispose()); group.children.forEach((m) => (m as THREE.InstancedMesh).dispose()); material.dispose(); },
  };
}

/** Split one instanced batch (matrices and shades) into spatial chunks that three.js can cull, without levels of detail (used for the megastructure's batches). */
export function chunkBatch(geometry: THREE.BufferGeometry, material: THREE.Material, matrices: Float32Array, shades: number[] | null, count: number, cell: number, tinted: boolean, maxRange = Infinity): THREE.Group {
  const group = new THREE.Group();
  group.userData.maxRange = maxRange;
  const cells = new Map<string, number[]>();
  for (let i = 0; i < count; i++) {
    const o = i * 16, key = `${Math.floor(matrices[o + 12] / cell)}:${Math.floor(matrices[o + 13] / (cell * 0.85))}:${Math.floor(matrices[o + 14] / cell)}`;
    let c = cells.get(key);
    if (!c) cells.set(key, (c = []));
    c.push(i);
  }
  const c = new THREE.Color();
  for (const list of cells.values()) {
    const m = new THREE.InstancedMesh(geometry, material, list.length);
    list.forEach((src, i) => { m.instanceMatrix.array.set(matrices.subarray(src * 16, src * 16 + 16), i * 16); if (tinted) m.setColorAt(i, c.setScalar(shades![src])); });
    m.instanceMatrix.needsUpdate = true; if (m.instanceColor) m.instanceColor.needsUpdate = true;
    m.computeBoundingSphere(); m.frustumCulled = true;
    group.add(m);
  }
  return group;
}

/** Split a list of line segments (pairs of points, 6 numbers per segment) into spatial chunks with their own bounding spheres. */
export function chunkLines(edges: number[], material: THREE.LineBasicMaterial, cell: number, maxRange = Infinity): THREE.Group {
  const group = new THREE.Group();
  group.userData.maxRange = maxRange;
  const cells = new Map<string, number[]>();
  for (let i = 0; i + 5 < edges.length; i += 6) {
    const mx = (edges[i] + edges[i + 3]) / 2, my = (edges[i + 1] + edges[i + 4]) / 2, mz = (edges[i + 2] + edges[i + 5]) / 2, key = `${Math.floor(mx / cell)}:${Math.floor(my / (cell * 0.85))}:${Math.floor(mz / cell)}`;
    let c = cells.get(key);
    if (!c) cells.set(key, (c = []));
    c.push(edges[i], edges[i + 1], edges[i + 2], edges[i + 3], edges[i + 4], edges[i + 5]);
  }
  for (const arr of cells.values()) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(arr, 3));
    g.computeBoundingSphere();
    const l = new THREE.LineSegments(g, material);
    l.frustumCulled = true;
    group.add(l);
  }
  return group;
}

/** Hide the chunks of range-limited groups (fine detail: greebles, fittings, linework) that are farther from the camera than their range. Returns the chunks hidden. */
export function applyRanges(groups: THREE.Object3D[], camera: THREE.Vector3): number {
  let hidden = 0;
  for (const g of groups) {
    const r = g.userData.maxRange as number;
    for (const c of g.children) {
      const m = c as THREE.Mesh, sph = m.geometry?.boundingSphere ?? (c as THREE.InstancedMesh).boundingSphere;
      if (!sph) continue;
      const centre = (c as THREE.InstancedMesh).isInstancedMesh ? sph.center : sph.center;  // chunk geometries are built in world space
      const off = centre.distanceTo(camera) - sph.radius > r;
      c.visible = !off;
      if (off) hidden++;
    }
  }
  return hidden;
}
