// XENO ECOSYSTEM — geometry helpers shared by the experimental bodies, their hardware, cables and probes.
import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { setWear } from './weathering';

export const v3 = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);

/** A plate of a polygon outline (in its own x-y plane) with a regular pattern of round holes, optional large round openings and optional rectangular slots, extruded along +z. */
export interface PlateOpts {
  hole: number; pitch: number; margin: number; depth: number; seg?: number;
  /** round openings (x, y, radius) */ big?: Array<[number, number, number]>;
  /** slots (x, y, width, height), rounded at the ends */ slots?: Array<[number, number, number, number]>;
  /** where the regular pattern is not drawn (x, y, radius): around features, so the holes do not run into them */ keepClear?: Array<[number, number, number]>;
}
export function perforated(outline: Array<[number, number]>, o: PlateOpts): THREE.BufferGeometry {
  const shape = new THREE.Shape(outline.map(([x, y]) => new THREE.Vector2(x, y)));
  const inside = (px: number, py: number, m: number) => {
    for (let i = 0; i < outline.length; i++) {  // inside the (convex) outline with a margin from every edge
      const [x1, y1] = outline[i], [x2, y2] = outline[(i + 1) % outline.length], ex = x2 - x1, ey = y2 - y1, len = Math.hypot(ex, ey);
      if ((ex * (py - y1) - ey * (px - x1)) / len < m) return false;
    }
    return true;
  };
  const xs = outline.map((p) => p[0]), ys = outline.map((p) => p[1]);
  const big = o.big ?? [], slots = o.slots ?? [], clear = o.keepClear ?? [];
  const seg = o.seg ?? 10, dy = o.pitch * 0.866;
  let row = 0;
  for (let y = Math.min(...ys); y <= Math.max(...ys); y += dy, row++) {
    for (let x = Math.min(...xs) + (row % 2 ? o.pitch / 2 : 0); x <= Math.max(...xs); x += o.pitch) {
      if (!inside(x, y, o.margin + o.hole)) continue;
      if (big.some(([bx, by, br]) => Math.hypot(x - bx, y - by) < br + o.hole * 2.2)) continue;
      if (clear.some(([bx, by, br]) => Math.hypot(x - bx, y - by) < br + o.hole * 1.5)) continue;
      if (slots.some(([sx, sy, sw, sh]) => Math.abs(x - sx) < sw / 2 + o.hole * 2 && Math.abs(y - sy) < sh / 2 + o.hole * 2)) continue;
      const h = new THREE.Path(); h.absarc(x, y, o.hole, 0, Math.PI * 2, true); shape.holes.push(h);
    }
  }
  for (const [bx, by, br] of big) { const h = new THREE.Path(); h.absarc(bx, by, br, 0, Math.PI * 2, true); shape.holes.push(h); }
  for (const [sx, sy, sw, sh] of slots) {  // a slot is a rectangle with half-round ends, wound clockwise like the other holes
    const r = Math.min(sw, sh) / 2, h = new THREE.Path(), x0 = sx - sw / 2, x1 = sx + sw / 2, y0 = sy - sh / 2, y1 = sy + sh / 2;
    h.moveTo(x0 + r, y1); h.lineTo(x1 - r, y1); h.absarc(x1 - r, y1 - r, r, Math.PI / 2, 0, true);
    h.lineTo(x1, y0 + r); h.absarc(x1 - r, y0 + r, r, 0, -Math.PI / 2, true);
    h.lineTo(x0 + r, y0); h.absarc(x0 + r, y0 + r, r, -Math.PI / 2, -Math.PI, true);
    h.lineTo(x0, y1 - r); h.absarc(x0 + r, y1 - r, r, Math.PI, Math.PI / 2, true);
    shape.holes.push(h);
  }
  return new THREE.ExtrudeGeometry(shape, { depth: o.depth, bevelEnabled: true, bevelThickness: o.depth * 0.18, bevelSize: o.depth * 0.18, bevelSegments: 1, curveSegments: seg });
}

/** A beam between two points as a cylinder (placed and oriented into a geometry so that batches can be merged). */
export function tube(a: THREE.Vector3, b: THREE.Vector3, r: number, seg = 8, rb = r): THREE.BufferGeometry {
  const len = a.distanceTo(b), g = new THREE.CylinderGeometry(rb, r, len, seg, 1);  // radius rb at the top (b), r at the bottom (a)
  g.applyMatrix4(new THREE.Matrix4().compose(a.clone().add(b).multiplyScalar(0.5), new THREE.Quaternion().setFromUnitVectors(v3(0, 1, 0), b.clone().sub(a).normalize()), v3(1, 1, 1)));
  return g;
}
export const sphere = (p: THREE.Vector3, r: number, seg = 14) => { const g = new THREE.SphereGeometry(r, seg, Math.max(6, seg - 4)); g.translate(p.x, p.y, p.z); return g; };
export const collar = (a: THREE.Vector3, b: THREE.Vector3, r: number, t = 0.5, w = 0.22, seg = 14) => {
  const p = a.clone().lerp(b, t), d = b.clone().sub(a).normalize(), g = new THREE.CylinderGeometry(r, r, w, seg);
  g.applyMatrix4(new THREE.Matrix4().compose(p, new THREE.Quaternion().setFromUnitVectors(v3(0, 1, 0), d), v3(1, 1, 1)));
  return g;
};
export const torusAt = (c: THREE.Vector3, n: THREE.Vector3, R: number, r: number, seg = 28) => {
  const g = new THREE.TorusGeometry(R, r, 8, seg);
  g.applyMatrix4(new THREE.Matrix4().compose(c, new THREE.Quaternion().setFromUnitVectors(v3(0, 0, 1), n.clone().normalize()), v3(1, 1, 1)));
  return g;
};
export const discAt = (c: THREE.Vector3, n: THREE.Vector3, R: number, seg = 24) => {
  const g = new THREE.CircleGeometry(R, seg);
  g.applyMatrix4(new THREE.Matrix4().compose(c, new THREE.Quaternion().setFromUnitVectors(v3(0, 0, 1), n.clone().normalize()), v3(1, 1, 1)));
  return g;
};
export const boxAt = (c: THREE.Vector3, ex: THREE.Vector3, ey: THREE.Vector3, n: THREE.Vector3, sx: number, sy: number, sz: number) => {
  const g = new THREE.BoxGeometry(sx, sy, sz);
  g.applyMatrix4(new THREE.Matrix4().makeBasis(ex, ey, n).setPosition(c));
  return g;
};
export const cylAt = (c: THREE.Vector3, axis: THREE.Vector3, r: number, len: number, seg = 14, rTop = r) => {
  const g = new THREE.CylinderGeometry(rTop, r, len, seg);
  g.applyMatrix4(new THREE.Matrix4().compose(c, new THREE.Quaternion().setFromUnitVectors(v3(0, 1, 0), axis.clone().normalize()), v3(1, 1, 1)));
  return g;
};

/** Normalise a geometry for merging: non-indexed, with position, normal, uv and aWear only. */
export function normalise(g: THREE.BufferGeometry, wear = 0): THREE.BufferGeometry {
  const c = g.index ? g.toNonIndexed() : g;
  for (const k of Object.keys(c.attributes)) if (!['position', 'normal', 'uv', 'aWear'].includes(k)) c.deleteAttribute(k);
  if (!c.getAttribute('uv')) c.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(c.getAttribute('position').count * 2), 2));
  if (!c.getAttribute('aWear')) setWear(c, wear);
  return c;
}
export const merge = (gs: THREE.BufferGeometry[], wear = 0): THREE.BufferGeometry | null => {
  if (!gs.length) return null;
  const m = mergeGeometries(gs.map((g) => normalise(g, wear)));
  gs.forEach((g) => g.dispose());
  return m;
};

export type MatKey = 'chrome' | 'gun' | 'dark' | 'rubber' | 'polished' | 'sleeve' | 'glass';
/** Accumulates small geometries per material, with a wear weight each, and merges them into one mesh per material. */
export class Parts {
  private by = new Map<MatKey, THREE.BufferGeometry[]>();
  vertices = 0;
  add(key: MatKey, g: THREE.BufferGeometry, wear = 0.3): void {
    const n = normalise(g, wear);
    if (n !== g) g.dispose();
    if (!n.getAttribute('aWear') || wear !== 0) setWear(n, wear);
    this.vertices += n.getAttribute('position').count;
    (this.by.get(key) ?? (this.by.set(key, []), this.by.get(key)!)).push(n);
  }
  flush(group: THREE.Object3D, mats: Record<MatKey, THREE.Material>, owned: Array<{ dispose(): void }>, tag?: string): THREE.Mesh[] {
    const out: THREE.Mesh[] = [];
    for (const [key, gs] of this.by) {
      const m = mergeGeometries(gs);
      gs.forEach((g) => g.dispose());
      if (!m) continue;
      const mesh = new THREE.Mesh(m, mats[key]);
      if (tag) mesh.name = `${tag}:${key}`;
      group.add(mesh); owned.push(m); out.push(mesh);
    }
    this.by.clear();
    return out;
  }
}

/** A local frame on a surface: a centre, two in-plane axes and the outward normal; ``at(u, v, lift)`` gives the point u along ex, v along ey and lift along n. */
export class Frame {
  constructor(public c: THREE.Vector3, public ex: THREE.Vector3, public ey: THREE.Vector3, public n: THREE.Vector3) {}
  at(u: number, v: number, lift = 0): THREE.Vector3 { return this.c.clone().addScaledVector(this.ex, u).addScaledVector(this.ey, v).addScaledVector(this.n, lift); }
  static ofFace(face: THREE.Vector3[], outwardFrom: THREE.Vector3 = v3(0, 0, 0)): Frame {
    const [q0, q1, q2] = face, ex = q1.clone().sub(q0).normalize();
    let n = ex.clone().cross(q2.clone().sub(q0)).normalize();
    const c = face.reduce((a, b) => a.add(b), v3(0, 0, 0)).multiplyScalar(1 / face.length);
    if (n.dot(c.clone().sub(outwardFrom).setY(0)) < 0) n = n.negate();
    const ey = n.clone().cross(ex).normalize();
    return new Frame(c, ex, ey, n);
  }
}

/** A plate through three or four 3-D points: the outline is flattened into the plane of the first three and the extrusion pushed along its normal. Openings are given relative
 * to the plate's centroid, in the face's own axes (x along the first edge). */
export function plateThrough(pts: THREE.Vector3[], o: PlateOpts, inset: number): THREE.BufferGeometry {
  const [p0, p1, p2] = pts, ex = p1.clone().sub(p0).normalize(), n = ex.clone().cross(p2.clone().sub(p0)).normalize(), ey = n.clone().cross(ex);
  const outline = pts.map((p) => [p.clone().sub(p0).dot(ex), p.clone().sub(p0).dot(ey)] as [number, number]);
  const cx = outline.reduce((a, b) => a + b[0], 0) / outline.length, cy = outline.reduce((a, b) => a + b[1], 0) / outline.length;
  const shrunk = outline.map(([x, y]) => [cx + (x - cx) * inset, cy + (y - cy) * inset] as [number, number]);
  const rel = (a?: Array<[number, number, number]>) => a?.map(([dx, dy, r]) => [cx + dx, cy + dy, r] as [number, number, number]);
  const g = perforated(shrunk, { ...o, big: rel(o.big), keepClear: rel(o.keepClear), slots: o.slots?.map(([dx, dy, w, h]) => [cx + dx, cy + dy, w, h] as [number, number, number, number]) });
  g.translate(0, 0, -o.depth / 2);
  g.applyMatrix4(new THREE.Matrix4().makeBasis(ex, ey, n).setPosition(p0));
  return g;
}

/** The bounding box of the meshes below ``obj`` (first level of any LOD, not instanced), expressed in the local frame of ``frame`` (so that it does not depend on where the body stands). */
export function localBox(obj: THREE.Object3D, frame: THREE.Object3D): THREE.Box3 {
  frame.updateMatrixWorld(true);
  const box = new THREE.Box3(), inv = frame.matrixWorld.clone().invert(), tmp = new THREE.Box3(), M = new THREE.Matrix4();
  const visit = (o: THREE.Object3D): void => {
    const par = o.parent as THREE.LOD | null;
    if (!o.visible || (par && par.isLOD && par.levels.length > 0 && par.levels[0].object !== o)) return;
    const m = o as THREE.Mesh;
    if (m.isMesh && m.geometry && !(m as THREE.InstancedMesh).isInstancedMesh) {
      if (!m.geometry.boundingBox) m.geometry.computeBoundingBox();
      tmp.copy(m.geometry.boundingBox!); M.multiplyMatrices(inv, m.matrixWorld); tmp.applyMatrix4(M); box.union(tmp);
    }
    o.children.forEach(visit);
  };
  visit(obj);
  return box;
}
