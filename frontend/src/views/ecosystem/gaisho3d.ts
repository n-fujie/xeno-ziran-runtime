import * as THREE from 'three';
import type { GaishoShape } from './gaisho';

// GAISHO in the 3D scene: the OPERATIONAL SHAPE of one condition at one moment, built from the engine's record and nothing else. A vertex is a recorded cell (x and y are the two interventions, the height is the share of
// trials with the outcome); an edge joins neighbouring recorded cells; a CUT is an edge whose two ends differ by at least 0.5 (the surface is not drawn across it); a blue point is where the response crosses 0.5 along an edge
// (a branch of the reconstructed relation); a hollow marker on the base plane is a region the observation did not record (it keeps its class). The mapping from cells to positions is a VISUALIZATION PROJECTION chosen here
// and declared in the record; it is not a physical place. A second shape (the same condition before the shift, another condition, or the same operation seen through another observation) is drawn behind as a faint wire so
// that the two can be compared. Every vertex and every unresolved region can be picked and its construction data read. No shape is drawn that the record does not contain, and none is fixed in advance.

export interface GaishoFrame {
  shape: GaishoShape | null; ghost: GaishoShape | null; selected: string | null; support: string[] | null;
  show: { surface: boolean; cuts: boolean; unresolved: boolean; branch: boolean };
}
export interface GaishoLayer {
  group: THREE.Group; pickables: THREE.Mesh[]; set(f: GaishoFrame): void; dispose(): void;
  counts(): { vertices: number; edges: number; cuts: number; branch: number; unresolved: number; faces: number; ghostEdges: number };
  centre(): THREE.Vector3;
}
const W = 12, D = 6, H = 4;  // local extent of the projection: width (x), depth (y), height (outcome 0..1)
export const COLOR = { surface: 0x8aa4c8, edge: 0x9aa3ad, cut: 0xf2f2f2, branch: 0x2f6df0, unresolved: 0x7a828c, ghost: 0x5b6670, selected: 0xffd24a, support: 0x2f6df0, plate: 0x6b7683 } as const;

/** The local position of a cell of a shape: x and y normalised over the cells the shape holds (recorded or not), z the outcome. */
export function place(shape: GaishoShape, x: number, y: number, z: number): THREE.Vector3 {
  const xs = [...shape.vertices, ...shape.unresolved].map((v) => v.x), ys = [...shape.vertices, ...shape.unresolved].map((v) => v.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  return new THREE.Vector3(((x - x0) / Math.max(1e-9, x1 - x0) - 0.5) * W, z * H, ((y - y0) / Math.max(1e-9, y1 - y0) - 0.5) * D);
}

export function buildGaishoLayer(parent: THREE.Object3D, centre: THREE.Vector3, span: number): GaishoLayer {
  const group = new THREE.Group(); group.name = 'gaisho';
  group.position.copy(centre); group.scale.setScalar(span / 20);
  const dyn = new THREE.Group(); group.add(dyn);
  const owned: Array<THREE.BufferGeometry | THREE.Material> = [];
  let pickables: THREE.Mesh[] = [];
  let counts = { vertices: 0, edges: 0, cuts: 0, branch: 0, unresolved: 0, faces: 0, ghostEdges: 0 };
  // the base plate with the two intervention axes and the 0.5 level
  const plate = (() => {
    const g = new THREE.BufferGeometry(), m = new THREE.LineBasicMaterial({ color: COLOR.plate }); owned.push(g, m);
    const pts: number[] = [], rect = (y: number): void => { const c: Array<[number, number]> = [[-W / 2, -D / 2], [W / 2, -D / 2], [W / 2, D / 2], [-W / 2, D / 2]]; c.forEach(([x, z], i) => { const [x2, z2] = c[(i + 1) % 4]; pts.push(x, y, z, x2, y, z2); }); };
    rect(0); rect(H / 2);  // the base plane (outcome 0) and the level 0.5 of the outcome
    g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    const l = new THREE.LineSegments(g, m); l.name = 'gaisho-plate'; group.add(l); return l;
  })();
  void plate;
  const clear = (): void => { for (const c of [...dyn.children]) { dyn.remove(c); (c as THREE.Mesh).geometry?.dispose(); const m = (c as THREE.Mesh).material; if (Array.isArray(m)) m.forEach((x) => x.dispose()); else m?.dispose(); } pickables = []; };
  const lines = (pts: number[], color: number, opacity = 1, name = ''): THREE.LineSegments => {
    const g = new THREE.BufferGeometry(), m = new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity });
    g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3)); const l = new THREE.LineSegments(g, m); l.name = name; dyn.add(l); return l;
  };
  const set = (f: GaishoFrame): void => {
    clear();
    counts = { vertices: 0, edges: 0, cuts: 0, branch: 0, unresolved: 0, faces: 0, ghostEdges: 0 };
    const s = f.shape;
    if (f.ghost?.recorded && s?.recorded) {
      const pos = new Map(f.ghost.vertices.map((v) => [v.id, place(s, v.x, v.y, v.z)] as const)), pts: number[] = [];
      for (const e of [...f.ghost.edges, ...f.ghost.cuts]) { const a = pos.get(e.a), b = pos.get(e.b); if (a && b) pts.push(a.x, a.y, a.z, b.x, b.y, b.z); }
      counts.ghostEdges = pts.length / 6; if (pts.length) lines(pts, COLOR.ghost, 0.55, 'gaisho-ghost');
    }
    if (!s || !s.recorded) return;
    const P = new Map(s.vertices.map((v) => [v.id, place(s, v.x, v.y, v.z)] as const));
    const cutKey = new Set(s.cuts.map((e) => `${e.a}|${e.b}`));
    // the surface: a quad of four recorded neighbours, not drawn across a cut
    if (f.show.surface) {
      const byCell = new Map(s.vertices.map((v) => [`${v.cell[0]},${v.cell[1]}`, v] as const)), pos: number[] = [], col: number[] = [];
      const tri = (a: typeof s.vertices[number], b: typeof s.vertices[number], c: typeof s.vertices[number]): void => { for (const v of [a, b, c]) { const p = P.get(v.id)!; pos.push(p.x, p.y, p.z); const k = new THREE.Color(COLOR.surface).lerp(new THREE.Color(0x1a3d8f), v.z); col.push(k.r, k.g, k.b); } };
      for (const v of s.vertices) {
        const [i, j] = v.cell, r = byCell.get(`${i + 1},${j}`), u = byCell.get(`${i},${j + 1}`), d = byCell.get(`${i + 1},${j + 1}`);
        if (!r || !u || !d) continue;
        if ([[v, r], [v, u], [r, d], [u, d]].some(([p, q]) => cutKey.has(`${p.id}|${q.id}`))) continue;
        tri(v, r, d); tri(v, d, u); counts.faces += 2;
      }
      if (pos.length) {
        const g = new THREE.BufferGeometry(), m = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.38, side: THREE.DoubleSide, depthWrite: false });
        g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
        const mesh = new THREE.Mesh(g, m); mesh.name = 'gaisho-surface'; dyn.add(mesh);
      }
    }
    const ep: number[] = [], cp: number[] = [];
    for (const e of s.edges) { const a = P.get(e.a), b = P.get(e.b); if (a && b) ep.push(a.x, a.y, a.z, b.x, b.y, b.z); }
    for (const e of s.cuts) { const a = P.get(e.a), b = P.get(e.b); if (a && b) cp.push(a.x, a.y, a.z, b.x, b.y, b.z); }
    counts.edges = ep.length / 6; counts.cuts = f.show.cuts ? cp.length / 6 : 0;
    if (ep.length) lines(ep, COLOR.edge, 0.85, 'gaisho-edges');
    if (f.show.cuts && cp.length) lines(cp, COLOR.cut, 1, 'gaisho-cuts');
    // the vertices: small pickable spheres; the selected one and the cells a selected relation reads are marked
    const sg = new THREE.SphereGeometry(0.11, 10, 8); owned.push(sg);
    const sup = new Set(f.support ?? []);
    for (const v of s.vertices) {
      const sel = f.selected === v.id, on = sup.has(v.id);
      const m = new THREE.Mesh(sg, new THREE.MeshBasicMaterial({ color: sel ? COLOR.selected : on ? COLOR.support : 0xdfe6ee }));
      m.position.copy(P.get(v.id)!); m.scale.setScalar(sel ? 2 : on ? 1.5 : 1); m.userData = { gaishoId: v.id }; m.name = `gaisho-vertex:${v.id}`; dyn.add(m); pickables.push(m);
    }
    counts.vertices = s.vertices.length;
    if (f.show.branch) {
      const bg = new THREE.SphereGeometry(0.17, 12, 10); owned.push(bg);
      for (const b of s.branch) { const m = new THREE.Mesh(bg, new THREE.MeshBasicMaterial({ color: COLOR.branch })); m.position.copy(place(s, b.x, b.y, b.z)); m.name = 'gaisho-branch'; dyn.add(m); }
      counts.branch = s.branch.length;
    }
    // unrecorded regions stay on the base plane as hollow markers, with their class (nothing is dropped)
    if (f.show.unresolved) {
      const ug = new THREE.OctahedronGeometry(0.15); owned.push(ug);
      for (const u of s.unresolved) {
        const m = new THREE.Mesh(ug, new THREE.MeshBasicMaterial({ color: f.selected === u.id ? COLOR.selected : COLOR.unresolved, wireframe: true })); m.position.copy(place(s, u.x, u.y, 0)); m.userData = { gaishoId: u.id }; m.name = `gaisho-unresolved:${u.id}`;
        dyn.add(m); pickables.push(m);
      }
      counts.unresolved = s.unresolved.length;
    }
  };
  parent.add(group);
  const dispose = (): void => { clear(); group.removeFromParent(); for (const o of owned) o.dispose(); };
  return { group, get pickables() { return pickables; }, set, dispose, counts: () => ({ ...counts }), centre: () => group.getWorldPosition(new THREE.Vector3()) };
}

export const gaishoIdOf = (o: THREE.Object3D | undefined): string | null => ((o?.userData as { gaishoId?: string } | undefined)?.gaishoId) ?? null;
