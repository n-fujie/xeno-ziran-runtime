// XENO ECOSYSTEM — the technical inspection drawings: orthographic projections of the bodies' real geometry, with component identifiers, dimensions measured on that geometry, the
// state of each state-linked component, and the cable routing. Everything here is computed from the built bodies; no dimension is typed in. Units are scene units (``u``): the
// model does not define a scale to metres, so none is shown.
import * as THREE from 'three';
import type { BodySet } from './bodyset';
import { localBox } from './geom';
import { nodeAwake, nodeProbeState, reservoirLevel, ringProbeState, type BodyState } from './bodyState';
import { probeDimensions } from './probes';
import type { PartInfo } from './ncb';

export type ViewName = 'front' | 'side' | 'top';
export interface Segments { data: Float32Array; minX: number; maxX: number; minY: number; maxY: number }
export const EMPTY: Segments = { data: new Float32Array(0), minX: 0, maxX: 1, minY: 0, maxY: 1 };

/** The 2-D coordinates of a body-local point in a view: front looks along -z (x right, y up), side along -x (z right, y up), top from above (x right, z down). Screen y grows downward. */
export function project(p: THREE.Vector3, view: ViewName): [number, number] {
  return view === 'front' ? [p.x, -p.y] : view === 'side' ? [p.z, -p.y] : [p.x, p.z];
}

const edgeCache = new WeakMap<THREE.BufferGeometry, Float32Array>();
function edgesOf(g: THREE.BufferGeometry, angle: number): Float32Array {
  let e = edgeCache.get(g);
  if (!e) {
    const pos = g.getAttribute('position');
    e = pos && pos.count < 400000 ? (new THREE.EdgesGeometry(g, angle).getAttribute('position').array as Float32Array) : new Float32Array(0);
    edgeCache.set(g, e);
  }
  return e;
}
const isLodRest = (o: THREE.Object3D): boolean => {
  const par = o.parent as THREE.LOD | null;
  return !!par && (par as THREE.LOD).isLOD === true && par.levels.length > 0 && par.levels[0].object !== o;
};

/** The edges of every visible mesh below ``root`` (the first level of any LOD only), projected into a view, in the frame of ``root``. */
export function collectSegments(root: THREE.Object3D, view: ViewName, o: { angle?: number; filter?: (m: THREE.Mesh) => boolean } = {}): Segments {
  root.updateMatrixWorld(true);
  const inv = root.matrixWorld.clone().invert(), M = new THREE.Matrix4(), a = new THREE.Vector3(), b = new THREE.Vector3();
  const out: number[] = [];
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  const visit = (obj: THREE.Object3D): void => {
    if (!obj.visible || isLodRest(obj)) return;
    const m = obj as THREE.Mesh;
    if (m.isMesh && !(m as THREE.InstancedMesh).isInstancedMesh && m.geometry && (!o.filter || o.filter(m))) {
      const e = edgesOf(m.geometry, o.angle ?? 30);
      M.multiplyMatrices(inv, m.matrixWorld);
      for (let i = 0; i + 5 < e.length; i += 6) {
        a.set(e[i], e[i + 1], e[i + 2]).applyMatrix4(M); b.set(e[i + 3], e[i + 4], e[i + 5]).applyMatrix4(M);
        const [x1, y1] = project(a, view), [x2, y2] = project(b, view);
        out.push(x1, y1, x2, y2);
        minX = Math.min(minX, x1, x2); maxX = Math.max(maxX, x1, x2); minY = Math.min(minY, y1, y2); maxY = Math.max(maxY, y1, y2);
      }
    }
    obj.children.forEach(visit);
  };
  visit(root);
  return out.length ? { data: new Float32Array(out), minX, maxX, minY, maxY } : EMPTY;
}

/** The positions of every instanced fastener below ``root``, projected (drawn as dots). */
export function collectInstances(root: THREE.Object3D, view: ViewName): Float32Array {
  root.updateMatrixWorld(true);
  const inv = root.matrixWorld.clone().invert(), M = new THREE.Matrix4(), I = new THREE.Matrix4(), p = new THREE.Vector3(), out: number[] = [];
  root.traverse((obj) => {
    const im = obj as THREE.InstancedMesh;
    if (!im.isInstancedMesh || !obj.visible) return;
    let par: THREE.Object3D | null = obj.parent, hidden = false;
    while (par) { if (!par.visible || isLodRest(par)) { hidden = true; break; } par = par.parent; }
    if (hidden) return;
    M.multiplyMatrices(inv, im.matrixWorld);
    for (let i = 0; i < im.count; i++) { im.getMatrixAt(i, I); p.setFromMatrixPosition(I).applyMatrix4(M); const [x, y] = project(p, view); out.push(x, y); }
  });
  return new Float32Array(out);
}

export interface Extent { size: THREE.Vector3; min: THREE.Vector3; max: THREE.Vector3 }
/** The extent of an object in the frame of ``root``: measured on the geometry as built. */
export function measure(obj: THREE.Object3D, root: THREE.Object3D): Extent {
  const box = localBox(obj, root), size = new THREE.Vector3();
  if (!box.isEmpty()) box.getSize(size);
  return { size, min: box.min.clone(), max: box.max.clone() };
}

export type PartState = 'active' | 'idle' | 'inactive' | 'retracted' | 'overloaded' | 'cut' | 'asleep';
/** The state of each component for a BodyState, by part id (the same mapping that drives the 3-D bodies). */
export function partStates(parts: PartInfo[], s: BodyState): Record<string, { state: PartState; because: string }> {
  const out: Record<string, { state: PartState; because: string }> = {};
  const put = (id: string, state: PartState, because: string) => { out[id] = { state, because }; };
  const probeState = (st: string): PartState => (st === 'sampling' ? 'active' : st === 'extended' ? 'idle' : (st as PartState));
  for (const n of ['A', 'B', 'C'] as const) {
    const awake = nodeAwake(s, n), ps = nodeProbeState(s, n);
    const why = n === 'A' ? `observation: sampled tick ${s.sampling ? 'yes' : 'no'}, coverage ${(s.coverage * 100).toFixed(0)}%` : n === 'B' ? `A1 last fired ${s.a1FireAge === null ? 'never' : s.a1FireAge + ' ticks ago'}` : `A2 last renewed ${s.renewAge === null ? 'never' : s.renewAge + ' ticks ago'}; A2 ${s.a2Present ? 'present' : 'absent'}`;
    put(n, !awake ? 'asleep' : (n === 'A' ? s.sampling : n === 'B' ? s.a1FireAge !== null && s.a1FireAge <= 5 : s.renewAge !== null && s.renewAge <= 5) ? 'active' : 'idle', why);
    put(`${n}1`, probeState(ps), `probe state ${ps}`);
    if (parts.some((p) => p.id === `${n}2`)) put(`${n}2`, probeState(ps === 'sampling' ? 'sampling' : ps === 'extended' ? 'retracted' : ps), 'follows the first probe of its node');
  }
  put('A.lens', s.sampling && nodeAwake(s, 'A') ? 'active' : 'idle', 'lit on sampled ticks');
  put('B.archive', s.historyEnabled ? 'active' : 'inactive', `history re-entry ${s.historyEnabled ? 'enabled: latch closed' : 'disabled: latch open'}`);
  put('C.reservoir', s.pulseAge !== null ? 'active' : 'idle', `level ${(reservoirLevel(s) * 100).toFixed(0)}%${s.pulseAge !== null ? `; pulse ${s.pulseAmount} injected ${s.pulseAge} ticks ago` : ''}`);
  for (const id of ['J', 'cable.BCb', 'cable.BCc']) put(id, s.couplingCut ? 'cut' : 'active', `interaction channel ${s.couplingCut ? 'cut' : 'intact'}`);
  put('RING', 'active', `turns once per sampling interval (k = ${s.interval})`);
  put('CLUSTER', s.collapsed ? 'retracted' : 'active', `${Math.max(1, Math.round(s.coverage * 6))} of 6 probes out; boundary radius ${s.arenaRadius ?? 'whole grid'}`);
  for (let i = 0; i < 6; i++) { const st = ringProbeState(s, i, 6); put(`O${i + 1}`, probeState(st), `probe state ${st}`); }
  put('OPT', s.sampling ? 'active' : 'idle', 'lamp lit while sampling'); put('BM2', s.collapsed ? 'retracted' : 'active', s.collapsed ? 'boom folded' : s.sampling ? 'boom extended to sample' : 'boom at rest extension');
  return out;
}

export interface Dimension { id: string; label: string; a: [number, number]; b: [number, number]; value: number; offset: number }
/** The dimension lines of a view: overall width and height of the body and of selected components, measured on the built geometry (``u``). */
export function dimensionLines(body: BodySet, which: 'ncb' | 'observer', view: ViewName): Dimension[] {
  const root = which === 'ncb' ? body.ncb : body.obs, out: Dimension[] = [];
  const ext = measure(root, root);
  const span = (e: Extent, axis: 'x' | 'y' | 'z') => [e.min[axis], e.max[axis]] as [number, number];
  const h = view === 'top' ? 'x' : view === 'front' ? 'x' : 'z', v = view === 'top' ? 'z' : 'y';
  const [h0, h1] = span(ext, h as 'x' | 'z'), [v0, v1] = span(ext, v as 'y' | 'z');
  const sv = (y: number) => (v === 'y' ? -y : y);
  out.push({ id: 'W', label: 'overall', a: [h0, sv(v1)], b: [h1, sv(v1)], value: +(h1 - h0).toFixed(2), offset: -1.4 });
  out.push({ id: 'H', label: view === 'top' ? 'overall depth' : 'overall height', a: [h1, sv(v0)], b: [h1, sv(v1)], value: +(v1 - v0).toFixed(2), offset: 1.6 });
  const pick = (id: string) => body.parts.find((p) => p.id === id);
  const add = (id: string, label: string, axis: 'x' | 'y' | 'z') => {
    const p = pick(id); if (!p) return;
    const e = measure(p.object, root), [a0, a1] = span(e, axis);
    if (view === 'top' && axis === 'y') return;
    if (axis === 'y' && v === 'y') out.push({ id, label, a: [(e.min.x + e.max.x) / 2 + (h === 'z' ? 0 : 0), sv(a0)], b: [(e.min.x + e.max.x) / 2, sv(a1)], value: +(a1 - a0).toFixed(2), offset: 0 });
    else if (axis === h) out.push({ id, label, a: [a0, sv((e.min[v as 'y'] + e.max[v as 'y']) / 2)], b: [a1, sv((e.min[v as 'y'] + e.max[v as 'y']) / 2)], value: +(a1 - a0).toFixed(2), offset: 0 });
  };
  if (which === 'ncb') { add('A', 'node A height', 'y'); add('B', 'node B height', 'y'); add('C', 'node C height', 'y'); add('C.reservoir', 'reservoir', 'y'); }
  else { add('BM1', 'boom 1', 'z'); add('CLUSTER', 'probe ring', 'x'); add('OBS', 'overall', 'x'); }
  return out;
}

export interface Row { id: string; name: string; kind: string; params: string; extent: string; state: PartState; because: string }
const fmt = (n: number) => (Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(2));
/** The component table: every listed part with the parameters it was built from, its measured extent and its state. */
export function componentRows(body: BodySet, which: 'ncb' | 'observer', s: BodyState): Row[] {
  const root = which === 'ncb' ? body.ncb : body.obs, st = partStates(body.parts, s);
  return body.parts.filter((p) => p.body === which && !['cable'].includes(p.kind)).map((p) => {
    const e = measure(p.object, root), pr = p.params ?? {};
    const params = Object.entries(pr).map(([k, v]) => `${k} ${typeof v === 'number' ? fmt(v) : v}`).join(', ');
    let extent = e.size.length() > 0 ? `${fmt(e.size.x)} × ${fmt(e.size.y)} × ${fmt(e.size.z)}` : '—';
    if (p.kind === 'probe') { const pr2 = (body.nodes.flatMap((n) => n.probes).concat(body.observer.probes)).find((q) => q.spec.id === p.id); if (pr2) { const d = probeDimensions(pr2); extent = `length ${fmt(d.measuredLength)}, ⌀ ${fmt(d.diameter)}`; } }
    const stt = st[p.id] ?? { state: 'idle' as PartState, because: 'static' };
    return { id: p.id, name: p.name, kind: p.kind, params, extent, state: stt.state, because: stt.because };
  });
}

/** The cable routes of a body as polylines in the view's coordinates, for drawing (dashed by kind). */
export function cableRoutes(body: BodySet, which: 'ncb' | 'observer', view: ViewName): Array<{ id: string; kind: string; radius: number; pts: Array<[number, number]> }> {
  const root = which === 'ncb' ? body.ncb : body.obs, sets = which === 'ncb' ? body.cables : body.observer.cables;
  root.updateMatrixWorld(true);
  return sets.flatMap((cs) => cs.routes.map((r) => {
    const curve = cs.curves[r.id], pts: Array<[number, number]> = [], v = new THREE.Vector3();
    cs.group.updateMatrixWorld(true);
    const m = new THREE.Matrix4().multiplyMatrices(root.matrixWorld.clone().invert(), cs.group.matrixWorld);
    for (let i = 0; i <= 24; i++) { curve.getPoint(i / 24, v); pts.push(project(v.clone().applyMatrix4(m), view)); }
    return { id: r.id, kind: r.kind, radius: r.radius, pts };
  }));
}
