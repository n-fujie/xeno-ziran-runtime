// XENO ECOSYSTEM — hardware: the small parts that make a machine read as assembled and used rather than modelled.
//
//   fasteners    hex bolts with washers, socket-cap screws with a dark recess, exposed screws with a protruding thread, captive screws with a collar and a spring.
//                They are laid out unevenly: clustered round openings and along edges, with gaps where one is missing and doubled ones where a joint was reinforced.
//   brackets     L brackets along edges, tension brackets (a turnbuckle: barrel, two threaded ends, two eyes), hinge pins (a barrel through a joint with end caps and a cotter pin)
//   ports        recessed round ports, layered openings, sensor apertures, cable passthroughs with a grommet, ringed inspection holes, blanking plates with four screws,
//                slotted vents (the slots are cut into the plate itself), ringed probe sockets
// Everything is built into ``Parts`` (merged per material) or ``Fasteners`` (instanced per kind), so a node costs a handful of draw calls however many pieces it has.
import * as THREE from 'three';
import { Frame, Parts, boxAt, cylAt, discAt, merge, torusAt, tube, v3 } from './geom';

export type FastenerKind = 'hex' | 'socket' | 'exposed' | 'captive';
export interface FastenerSpot { p: THREE.Vector3; n: THREE.Vector3; scale: number }

/** Instanced fasteners of four kinds. ``add`` records a place; ``build`` makes one InstancedMesh per kind (and one for the dark recesses of the socket screws). */
export class Fasteners {
  private list: Record<FastenerKind, FastenerSpot[]> = { hex: [], socket: [], exposed: [], captive: [] };
  count = 0;
  add(kind: FastenerKind, p: THREE.Vector3, n: THREE.Vector3, scale = 1): void { this.list[kind].push({ p, n: n.clone().normalize(), scale }); this.count++; }

  /** Bolts along the inside of a polygon's outline, unevenly spaced: random gaps, occasional doubles, and a few of another kind. */
  edge(pts: THREE.Vector3[], n: THREE.Vector3, rnd: () => number, o: { pitch: number; inset: number; lift: number; kinds: FastenerKind[] }): void {
    const c = pts.reduce((a, p) => a.add(p), v3(0, 0, 0)).multiplyScalar(1 / pts.length);
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i], b = pts[(i + 1) % pts.length], len = a.distanceTo(b);
      let t = 0.04 + rnd() * 0.05;
      while (t < 0.96) {
        const p = a.clone().lerp(b, t), toC = c.clone().sub(p).normalize().multiplyScalar(o.inset * (0.85 + rnd() * 0.3));
        if (rnd() > 0.08) {  // about one in twelve is missing
          const k = o.kinds[Math.floor(rnd() * o.kinds.length)];
          this.add(k, p.clone().add(toC).addScaledVector(n, o.lift), n, 0.85 + rnd() * 0.35);
          if (rnd() < 0.12) this.add('hex', p.clone().add(toC.clone().multiplyScalar(1.7)).addScaledVector(n, o.lift), n, 0.8);  // a reinforcing second one
        }
        t += (o.pitch / len) * (0.55 + rnd() * 0.9);
      }
    }
  }
  /** A cluster of bolts round a circular opening. */
  ring(f: Frame, u: number, v: number, R: number, count: number, rnd: () => number, kinds: FastenerKind[], lift = 0.04): void {
    const phase = rnd() * 6.28;
    for (let k = 0; k < count; k++) {
      if (rnd() < 0.06) continue;
      const a = phase + (k / count) * Math.PI * 2 + (rnd() - 0.5) * 0.18;
      this.add(kinds[Math.floor(rnd() * kinds.length)], f.at(u + Math.cos(a) * R, v + Math.sin(a) * R, lift), f.n, 0.8 + rnd() * 0.3);
    }
  }

  build(group: THREE.Object3D, mats: { chrome: THREE.Material; gun: THREE.Material; dark: THREE.Material }, owned: Array<{ dispose(): void }>, detail: number): void {
    const seg = detail > 0.6 ? 6 : 5;
    const geo: Record<FastenerKind | 'recess', THREE.BufferGeometry> = {
      hex: mergeSimple([new THREE.CylinderGeometry(0.034, 0.034, 0.032, seg), at(new THREE.CylinderGeometry(0.056, 0.056, 0.01, 10), 0, -0.02, 0)]),
      socket: new THREE.CylinderGeometry(0.03, 0.03, 0.03, 10),
      exposed: mergeSimple([new THREE.CylinderGeometry(0.03, 0.03, 0.018, 8), at(new THREE.CylinderGeometry(0.013, 0.013, 0.1, 6), 0, 0.058, 0)]),
      captive: mergeSimple([new THREE.CylinderGeometry(0.034, 0.034, 0.03, 10), at(new THREE.CylinderGeometry(0.05, 0.05, 0.012, 12), 0, -0.02, 0), at(new THREE.TorusGeometry(0.03, 0.006, 4, 10).rotateX(Math.PI / 2), 0, 0.03, 0)]),
      recess: new THREE.CylinderGeometry(0.012, 0.012, 0.004, 6),
    };
    const M = new THREE.Matrix4(), Q = new THREE.Quaternion(), S = new THREE.Vector3();
    const make = (g: THREE.BufferGeometry, list: FastenerSpot[], mat: THREE.Material, lift = 0) => {
      if (!list.length) { g.dispose(); return; }
      const m = new THREE.InstancedMesh(g, mat, list.length);
      list.forEach((f, i) => { Q.setFromUnitVectors(v3(0, 1, 0), f.n); m.setMatrixAt(i, M.compose(f.p.clone().addScaledVector(f.n, lift * f.scale), Q, S.setScalar(f.scale))); });
      m.instanceMatrix.needsUpdate = true; m.frustumCulled = false;
      group.add(m); owned.push(g);
    };
    make(geo.hex, this.list.hex, mats.chrome); make(geo.socket, this.list.socket, mats.chrome);
    make(geo.recess, this.list.socket, mats.dark, 0.0165);
    make(geo.exposed, this.list.exposed, mats.gun); make(geo.captive, this.list.captive, mats.chrome);
  }
}
function at(g: THREE.BufferGeometry, x: number, y: number, z: number): THREE.BufferGeometry { g.translate(x, y, z); return g; }
const mergeSimple = (gs: THREE.BufferGeometry[]): THREE.BufferGeometry => merge(gs, 0)!;

// ---------------------------------------------------------------------------------------------------- brackets and pins
/** An L bracket on a face: a flat leg on the face and an upright leg, with two screws; ``along`` is the direction of the edge it stands along. */
export function lBracket(parts: Parts, fast: Fasteners, p: THREE.Vector3, along: THREE.Vector3, n: THREE.Vector3, size: number, rnd: () => number): void {
  const side = n.clone().cross(along).normalize();
  parts.add('gun', boxAt(p.clone().addScaledVector(n, 0.02), along, side, n, size, size * 0.8, 0.04), 0.7);
  parts.add('gun', boxAt(p.clone().addScaledVector(n, size * 0.3).addScaledVector(side, size * 0.38), along, n, side, size, size * 0.6, 0.04), 0.7);
  fast.add(rnd() < 0.5 ? 'socket' : 'hex', p.clone().addScaledVector(n, 0.045).addScaledVector(along, size * 0.28), n, 0.8);
  fast.add(rnd() < 0.5 ? 'socket' : 'hex', p.clone().addScaledVector(n, 0.045).addScaledVector(along, -size * 0.28), n, 0.8);
}
/** A tension bracket (turnbuckle) between two points: a barrel in the middle, threaded ends and an eye at each end. */
export function turnbuckle(parts: Parts, a: THREE.Vector3, b: THREE.Vector3, r: number): void {
  const d = b.clone().sub(a), len = d.length(), u = d.clone().normalize(), mid = a.clone().lerp(b, 0.5);
  parts.add('chrome', tube(a.clone().addScaledVector(u, r * 3), mid.clone().addScaledVector(u, -len * 0.14), r * 0.42, 6), 0.5);
  parts.add('chrome', tube(mid.clone().addScaledVector(u, len * 0.14), b.clone().addScaledVector(u, -r * 3), r * 0.42, 6), 0.5);
  parts.add('gun', cylAt(mid, u, r * 1.25, len * 0.28, 10), 0.8);
  for (const e of [a, b]) {
    const dir = e === a ? u : u.clone().negate();
    parts.add('chrome', torusAt(e.clone().addScaledVector(dir, r * 1.6), u.clone().cross(v3(0, 1, 0)).length() > 0.1 ? u.clone().cross(v3(0, 1, 0)) : v3(1, 0, 0), r * 1.6, r * 0.5, 14), 0.6);
  }
}
/** A hinge pin through a joint: a barrel along ``axis``, end caps, and a cotter pin. */
export function hingePin(parts: Parts, c: THREE.Vector3, axis: THREE.Vector3, len: number, r: number): void {
  parts.add('chrome', cylAt(c, axis, r, len, 10), 0.8);
  for (const s of [-1, 1]) parts.add('gun', cylAt(c.clone().addScaledVector(axis, s * (len / 2 + r * 0.2)), axis, r * 1.45, r * 0.5, 10), 0.9);
  const side = axis.clone().cross(v3(0, 1, 0)).normalize();
  parts.add('chrome', torusAt(c.clone().addScaledVector(axis, len / 2 + r * 0.9).addScaledVector(side, r * 0.8), axis, r * 0.8, r * 0.14, 8), 0.5);
}

// ---------------------------------------------------------------------------------------------------- ports and openings
/** A recessed round port: a collar ring, a dark floor set back, and an inner ring; ``layers`` adds nested rings at increasing depth. */
export function recessedPort(parts: Parts, f: Frame, u: number, v: number, R: number, layers = 1): void {
  const c = f.at(u, v);
  parts.add('chrome', torusAt(f.at(u, v, 0.03), f.n, R * 1.04, R * 0.09, 22), 0.9);
  parts.add('dark', discAt(f.at(u, v, -R * 0.55), f.n, R * 0.96, 20), 0.5);
  for (let k = 1; k <= layers; k++) {
    const rr = R * (1 - k * 0.2);
    parts.add('gun', torusAt(f.at(u, v, -R * 0.12 * k), f.n, rr, R * 0.05, 18), 0.8);
    parts.add('dark', discAt(f.at(u, v, -R * (0.3 + 0.18 * k)), f.n, rr * 0.9, 16), 0.5);
  }
  void c;
}
/** A sensor aperture: a small lens in a hooded ring, with a pinhole beside it. */
export function aperture(parts: Parts, f: Frame, u: number, v: number, R: number): void {
  parts.add('chrome', torusAt(f.at(u, v, 0.035), f.n, R, R * 0.12, 16), 0.9);
  parts.add('glass', discAt(f.at(u, v, 0.012), f.n, R * 0.88, 16), 0.2);
  parts.add('gun', cylAt(f.at(u, v, R * 0.35), f.n, R * 1.18, R * 0.7, 14, R * 1.05), 0.8);
  parts.add('dark', discAt(f.at(u + R * 1.9, v, 0.012), f.n, R * 0.22, 8), 0.3);
}
/** A cable passthrough: a grommet in the plate with the cable running out of it. */
export function passthrough(parts: Parts, f: Frame, u: number, v: number, R: number, dir: THREE.Vector3): void {
  parts.add('rubber', torusAt(f.at(u, v, 0.02), f.n, R, R * 0.28, 14), 0.9);
  parts.add('dark', discAt(f.at(u, v, -0.02), f.n, R * 0.78, 14), 0.5);
  parts.add('rubber', cylAt(f.at(u, v).addScaledVector(dir, R * 1.6), dir, R * 0.62, R * 3.2, 10), 0.7);
}
/** A ringed inspection hole: a chrome ring and a dark floor. */
export function inspection(parts: Parts, f: Frame, u: number, v: number, R: number): void {
  parts.add('chrome', torusAt(f.at(u, v, 0.03), f.n, R, R * 0.14, 18), 0.8);
  parts.add('dark', discAt(f.at(u, v, -0.05), f.n, R * 0.94, 16), 0.6);
  parts.add('gun', cylAt(f.at(u, v, -0.02), f.n, R * 0.98, 0.04, 16), 0.5);
}
/** A blanking plate: a small square plate with four screws. */
export function blankingPlate(parts: Parts, fast: Fasteners, f: Frame, u: number, v: number, w: number, h: number, rnd: () => number): void {
  parts.add('gun', boxAt(f.at(u, v, 0.03), f.ex, f.ey, f.n, w, h, 0.035), 0.8);
  for (const [sx, sy] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) fast.add(rnd() < 0.5 ? 'socket' : 'hex', f.at(u + sx * (w / 2 - 0.05), v + sy * (h / 2 - 0.05), 0.058), f.n, 0.7);
}
/** A ringed probe socket: a collar standing off the face, a ring and a dark bore; a probe is mounted in it by the caller. */
export function probeSocket(parts: Parts, f: Frame, u: number, v: number, R: number): void {
  parts.add('gun', cylAt(f.at(u, v, R * 0.4), f.n, R * 1.3, R * 0.8, 18, R * 1.1), 0.9);
  parts.add('chrome', torusAt(f.at(u, v, R * 0.82), f.n, R * 1.12, R * 0.1, 18), 0.9);
  parts.add('dark', discAt(f.at(u, v, R * 0.84), f.n, R * 0.72, 16), 0.4);
}
