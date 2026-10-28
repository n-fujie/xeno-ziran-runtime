// XENO ECOSYSTEM — cable infrastructure. A cable here is a route, not a tube between two floating points: it starts and ends at fixed points on the machine, is held by clamps
// that stand on small anchor plates, ends in a strain-relief boot or a connector head, hangs with slack, differs in thickness from its neighbours, may be sheathed in a braided
// sleeve (helical strands) over part of its length, and may branch at a junction block. Routes cross at different heights and are asymmetrical.
//
// Each route has a kind that the technical view prints and colours by: ``power`` (an energy line), ``resource`` (a resource line) or ``data``.
import * as THREE from 'three';
import { Parts, boxAt, cylAt, merge, torusAt, v3 } from './geom';

export type EndKind = 'plain' | 'strain' | 'connector' | 'anchor';
export interface CableRoute {
  id: string; kind: 'power' | 'resource' | 'data'; points: THREE.Vector3[]; radius: number;
  /** extra hang between consecutive points, as a share of their distance */ sag?: number;
  /** a braided sleeve over this part of the length: [from, to] in 0..1 */ sleeve?: [number, number];
  ends?: [EndKind, EndKind];
  /** positions along the route (0..1) that carry a clamp on an anchor plate */ clamps?: number[];
  /** the route is lowered so that its lowest point lies at this height (a cable resting on the ground, partly under gravel) */ rest?: number;
}
export interface CableSet {
  group: THREE.Group; curves: Record<string, THREE.CatmullRomCurve3>; routes: CableRoute[];
  /** the parts of one route kept in their own group so that a state can move them (the connector halves of a coupling) */ named: Record<string, THREE.Group>;
  stats: { routes: number; clamps: number; connectors: number; sleeved: number; lengthTotal: number };
  dispose(): void;
}
export interface CableMats { rubber: THREE.Material; sleeve: THREE.Material; chrome: THREE.Material; gun: THREE.Material; dark: THREE.Material }

const UP = v3(0, 1, 0);

/** The curve of a route: the points with a lowered midpoint inserted between each pair (the hang), smoothed. */
export function routeCurve(r: CableRoute): THREE.CatmullRomCurve3 {
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i < r.points.length; i++) {
    pts.push(r.points[i].clone());
    if (i < r.points.length - 1) {
      const a = r.points[i], b = r.points[i + 1], d = a.distanceTo(b), sag = (r.sag ?? 0.08) * d;
      pts.push(a.clone().lerp(b, 0.5).add(v3(0, -sag, 0)));
    }
  }
  if (r.rest !== undefined) {
    const lowest = Math.min(...pts.map((p) => p.y));
    if (lowest > r.rest) { const k = (lowest - r.rest); pts.forEach((p, i) => { const t = i / (pts.length - 1), w = Math.sin(Math.PI * t); p.y -= k * Math.pow(w, 0.7); }); }
  }
  return new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.5);
}

export function buildCables(routes: CableRoute[], M: CableMats, detail: number, rnd: () => number): CableSet {
  const group = new THREE.Group();
  group.name = 'cables';
  const owned: Array<{ dispose(): void }> = [];
  const curves: Record<string, THREE.CatmullRomCurve3> = {}, named: Record<string, THREE.Group> = {};
  const rubber: THREE.BufferGeometry[] = [], sleeve: THREE.BufferGeometry[] = [];
  const hw = new Parts();
  let clampsN = 0, connectors = 0, sleeved = 0, length = 0;
  for (const r of routes) {
    const curve = routeCurve(r);
    curves[r.id] = curve; length += curve.getLength();
    const segs = Math.max(14, Math.round(curve.getLength() * 3 * detail)), rad = r.radius;
    const sl = r.sleeve;
    if (sl) sleeved++;
    // the tube: split where the sleeve begins and ends so that the braided part is a different surface
    const cut = (a: number, b: number) => {
      const n = Math.max(4, Math.round(segs * (b - a))), pts: THREE.Vector3[] = [];
      for (let i = 0; i <= n; i++) pts.push(curve.getPointAt(a + (b - a) * (i / n)));
      return new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.5);
    };
    const spans: Array<[number, number, boolean]> = sl ? [[0, sl[0], false], [sl[0], sl[1], true], [sl[1], 1, false]] : [[0, 1, false]];
    for (const [a, b, braid] of spans) {
      if (b - a < 0.01) continue;
      const c = cut(a, b), n = Math.max(6, Math.round(segs * (b - a)));
      if (!braid) { rubber.push(new THREE.TubeGeometry(c, n, rad, detail > 0.6 ? 8 : 6, false)); continue; }
      // braided sleeve: a thin core and three helical strands, so that the surface shows a weave under the light
      rubber.push(new THREE.TubeGeometry(c, n, rad * 0.78, 6, false));
      const frames = c.computeFrenetFrames(n * 2, false), turns = Math.max(3, c.getLength() * 1.4);
      for (let s = 0; s < 3; s++) {
        const pts: THREE.Vector3[] = [];
        for (let i = 0; i <= n * 2; i++) { const t = i / (n * 2), ang = t * turns * Math.PI * 2 + (s / 3) * Math.PI * 2; pts.push(c.getPoint(t).addScaledVector(frames.normals[i], Math.cos(ang) * rad * 0.62).addScaledVector(frames.binormals[i], Math.sin(ang) * rad * 0.62)); }
        sleeve.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.5), n * 2, rad * 0.3, 5, false));
      }
    }
    // ends: strain-relief boot, connector head or an anchor block
    (r.ends ?? ['strain', 'strain']).forEach((kind, k) => {
      const t = k === 0 ? 0 : 1, p = curve.getPointAt(t), tan = curve.getTangentAt(t).multiplyScalar(k === 0 ? -1 : 1);  // pointing out of the cable
      if (kind === 'strain') {
        hw.add('rubber', cylAt(p.clone().addScaledVector(tan, -rad * 3.2), tan, rad * 1.1, rad * 7, 10, rad * 2.1), 0.9);
        hw.add('gun', cylAt(p.clone().addScaledVector(tan, -rad * 6.6), tan, rad * 2.3, rad * 0.8, 12), 0.9);
      } else if (kind === 'connector') {
        connectors++;
        hw.add('gun', cylAt(p.clone().addScaledVector(tan, -rad * 1.8), tan, rad * 2.4, rad * 5, 12), 0.9);
        hw.add('chrome', torusAt(p.clone().addScaledVector(tan, rad * 0.3), tan, rad * 2.4, rad * 0.35, 14), 0.9);
        hw.add('chrome', cylAt(p.clone().addScaledVector(tan, rad * 1.1), tan, rad * 1.6, rad * 2.2, 12), 0.8);
        hw.add('dark', cylAt(p.clone().addScaledVector(tan, rad * 2.25), tan, rad * 1.1, rad * 0.2, 10), 0.6);
        for (let q = 0; q < 3; q++) { const a = (q / 3) * 6.28, side = tan.clone().cross(UP).normalize(), up = tan.clone().cross(side).normalize(); hw.add('chrome', cylAt(p.clone().addScaledVector(tan, rad * 2.5).addScaledVector(side, Math.cos(a) * rad * 0.6).addScaledVector(up, Math.sin(a) * rad * 0.6), tan, rad * 0.14, rad * 0.9, 6), 0.4); }
      } else if (kind === 'anchor') {
        const side = tan.clone().cross(UP).normalize(), up = tan.clone().cross(side).normalize();
        hw.add('gun', boxAt(p.clone().addScaledVector(tan, -rad * 1.2), side, up, tan, rad * 4.4, rad * 3.6, rad * 2.4), 0.9);
        hw.add('chrome', cylAt(p.clone().addScaledVector(tan, -rad * 2.5).addScaledVector(up, rad * 2.2), tan, rad * 0.5, rad * 0.6, 8), 0.8);
      }
    });
    // clamps: a ring round the cable on a small anchor plate with a bolt, standing off toward whatever lies beneath
    for (const t of r.clamps ?? []) {
      clampsN++;
      const p = curve.getPointAt(t), tan = curve.getTangentAt(t), side = tan.clone().cross(UP).normalize(), up = tan.clone().cross(side).normalize(), down = up.y > 0 ? up.clone().negate() : up.clone();
      hw.add('chrome', cylAt(p, tan, rad * 2.0, rad * 1.7, 12), 0.95);
      hw.add('gun', boxAt(p.clone().addScaledVector(down, rad * 2.6), side, tan, down, rad * 3.6, rad * 3.2, rad * 0.7), 0.95);
      hw.add('chrome', cylAt(p.clone().addScaledVector(down, rad * 1.5), down, rad * 0.5, rad * 2.2, 8), 0.8);
      hw.add('chrome', cylAt(p.clone().addScaledVector(down, rad * 3.1), down, rad * 0.7, rad * 0.5, 6), 0.8);
    }
    void rnd;
  }
  const add = (g: THREE.BufferGeometry | null, mat: THREE.Material) => { if (!g) return; const m = new THREE.Mesh(g, mat); group.add(m); owned.push(g); };
  add(merge(rubber, 0.35), M.rubber); add(merge(sleeve, 0.25), M.sleeve);
  hw.flush(group, { chrome: M.chrome, gun: M.gun, dark: M.dark, rubber: M.rubber, polished: M.chrome, sleeve: M.sleeve, glass: M.dark }, owned);
  return { group, curves, routes, named, stats: { routes: routes.length, clamps: clampsN, connectors, sleeved, lengthTotal: +length.toFixed(2) }, dispose: () => owned.forEach((o) => o.dispose()) };
}

/** A junction block where a cable branches: a block with the incoming route's end and the outgoing routes' starts. */
export function junctionBlock(parts: Parts, c: THREE.Vector3, ex: THREE.Vector3, ey: THREE.Vector3, n: THREE.Vector3, size: number): void {
  parts.add('gun', boxAt(c, ex, ey, n, size * 1.4, size, size * 0.9), 0.95);
  parts.add('chrome', torusAt(c.clone().addScaledVector(n, size * 0.46), n, size * 0.28, size * 0.05, 12), 0.9);
  for (const s of [-1, 1]) parts.add('chrome', cylAt(c.clone().addScaledVector(ex, s * size * 0.72), ex, size * 0.22, size * 0.2, 10), 0.9);
}
