// XENO ECOSYSTEM — the ground of the surface layer: dark broken rock with wet sheen and shallow puddles that reflect what stands near them.
// Static architecture and landscape: nothing here reads a record. Deterministic (seeded) so that captures are comparable between builds.
//
//   * a polar mesh around the central pit (fine near the work areas, coarse far away), displaced by fractal noise, with vertex shading and a roughness map in which
//     wet patches are glossy and dry rock is rough;
//   * puddles: flat irregular blobs set into the ground; at the 'balanced' and 'high' tiers they are planar reflectors (one extra render of the near scene, with the
//     heavy distant structure hidden during that render);
//   * rocks: instanced displaced icosahedra of several sizes, with a wet clear-coat sheen, clustered where the camera presets look.
import * as THREE from 'three';
import { Reflector } from 'three/examples/jsm/objects/Reflector.js';
import { mergeGeometries, mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { Quality } from './megastructure';

export function mulberry(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Seeded 2-D value noise and fractal sum, in [0, 1]. */
export function makeNoise(seed: number) {
  const P = new Float32Array(256 * 256);
  const R = mulberry(seed);
  for (let i = 0; i < P.length; i++) P[i] = R();
  const at = (ix: number, iy: number) => P[((iy & 255) << 8) | (ix & 255)];
  const smooth = (t: number) => t * t * (3 - 2 * t);
  const noise = (x: number, y: number) => {
    const ix = Math.floor(x), iy = Math.floor(y), fx = smooth(x - ix), fy = smooth(y - iy);
    const a = at(ix, iy), b = at(ix + 1, iy), c = at(ix, iy + 1), d = at(ix + 1, iy + 1);
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
  };
  const fbm = (x: number, y: number, oct = 5) => {
    let s = 0, amp = 0.5, f = 1, norm = 0;
    for (let o = 0; o < oct; o++) { s += amp * noise(x * f, y * f); norm += amp; amp *= 0.5; f *= 2.03; }
    return s / norm;
  };
  return { noise, fbm };
}

export interface Puddle { x: number; z: number; r: number }
/** Where the puddles are: around the experimental bodies (so that the camera presets that look at them have reflections in the foreground). */
export const PUDDLES: Puddle[] = [
  { x: -96, z: 0, r: 9 }, { x: -112, z: 8, r: 7 }, { x: -104, z: -12, r: 6 }, { x: -90, z: 12, r: 5 }, { x: -100, z: 14, r: 4 },
  { x: -84, z: 28, r: 6 }, { x: -92, z: 44, r: 6 }, { x: -78, z: 36, r: 4 },
];

export interface Terrain {
  group: THREE.Group; puddleMesh: THREE.Mesh | null; heightAt(x: number, z: number): number; setReflectionHidden(hidden: THREE.Object3D[]): void; dispose(): void;
}

const blob = (p: Puddle, R: () => number): THREE.Shape => {
  const s = new THREE.Shape(), n = 28, ph = R() * 6;
  for (let i = 0; i <= n; i++) {
    const a = (i / n) * Math.PI * 2, k = 1 + 0.32 * Math.sin(a * 3 + ph) + 0.18 * Math.sin(a * 5 + ph * 2) + (R() - 0.5) * 0.08;
    const x = p.x + Math.cos(a) * p.r * k, y = -(p.z + Math.sin(a) * p.r * k * 0.8);  // the shape's y is -z: rotating it flat about x by -90 degrees puts it at +z with an upward normal
    if (i === 0) s.moveTo(x, y); else s.lineTo(x, y);
  }
  return s;
};

export function buildTerrain(quality: Quality, pit: number, owned: Array<{ dispose(): void }>, env: THREE.Texture | null): Terrain {
  const group = new THREE.Group();
  group.name = 'terrain';
  const { fbm } = makeNoise(31);
  const puddleAt = (x: number, z: number) => {
    let m = 0;
    for (const p of PUDDLES) { const d = Math.hypot(x - p.x, (z - p.z) / 0.8) / (p.r * 1.7); m = Math.max(m, 1 - d); }
    return Math.max(0, Math.min(1, m * 3));
  };
  const height = (x: number, z: number): number => {
    const r = Math.hypot(x, z);
    const big = fbm(x * 0.018, z * 0.018, 4), mid = fbm(x * 0.09 + 11, z * 0.09, 4), fine = fbm(x * 0.5, z * 0.5, 3);
    // rock relief grows away from the pit; puddles flatten it to a basin
    let h = (big - 0.5) * 5 + (mid - 0.5) * 1.6 + (fine - 0.5) * 0.28 + Math.max(0, big - 0.62) * 9;
    h *= Math.min(1, (r - pit) / 18);
    const pm = puddleAt(x, z);
    return h * (1 - pm) + -0.18 * pm;
  };
  // the work area stays level (the habitat, the arena and the bodies are placed at y = 0); relief is blended out around them
  const flat = (x: number, z: number): number => {
    const keep = [[-66, 16, 24], [-62, -46, 34], [64, -22, 34], [54, 52, 28], [20, -78, 26], [-74, 56, 17], [-104, 4, 20], [-86, 36, 12]] as const;
    let k = 0;
    for (const [cx, cz, cr] of keep) k = Math.max(k, 1 - Math.max(0, Math.hypot(x - cx, z - cz) - cr) / 10);
    return Math.max(0, Math.min(1, k));
  };
  const groundHeight = (x: number, z: number) => height(x, z) * (1 - flat(x, z) * 0.92) - 0.06;

  // polar mesh: radial spacing grows with distance
  const RAD = quality === 'performance' ? 70 : quality === 'balanced' ? 120 : 170, ANG = quality === 'performance' ? 180 : quality === 'balanced' ? 320 : 460;
  const r0 = pit + 0.5, r1 = 280;
  const pos = new Float32Array((RAD + 1) * (ANG + 1) * 3), col = new Float32Array((RAD + 1) * (ANG + 1) * 3), uv = new Float32Array((RAD + 1) * (ANG + 1) * 2);
  const idx: number[] = [];
  for (let i = 0; i <= RAD; i++) {
    const r = r0 + (r1 - r0) * Math.pow(i / RAD, 1.9);
    for (let j = 0; j <= ANG; j++) {
      const a = (j / ANG) * Math.PI * 2, x = Math.cos(a) * r, z = Math.sin(a) * r, k = i * (ANG + 1) + j;
      const y = groundHeight(x, z);
      pos.set([x, y, z], k * 3);
      const wet = puddleAt(x, z), tone = 0.022 + 0.04 * fbm(x * 0.25 + 3, z * 0.25, 4) + 0.03 * fbm(x * 1.4, z * 1.4, 2);
      const v = tone * (1 - 0.5 * wet);
      col.set([v, v * 1.01, v * 1.04], k * 3);
      uv.set([x / 48, z / 48], k * 2);
      if (i < RAD && j < ANG) { const n = (i + 1) * (ANG + 1) + j; idx.push(k, k + 1, n, k + 1, n + 1, n); }  // counter-clockwise seen from above: the normals point up
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3)); geo.setAttribute('color', new THREE.BufferAttribute(col, 3)); geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  geo.setIndex(idx); geo.computeVertexNormals();

  // roughness map: dry rock is rough, wet patches are glossy (the red channel is read as roughness, the green one as metalness for three's standard material)
  const S = quality === 'performance' ? 256 : 1024;
  const data = new Uint8Array(S * S * 4), { fbm: f2 } = makeNoise(77);
  for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
    const wet = f2(x / S * 6, y / S * 6, 4), grit = f2(x / S * 40, y / S * 40, 3);
    const rough = Math.max(0.14, Math.min(1, 1.0 - 2.4 * Math.max(0, wet - 0.5) - 0.22 * (1 - grit)));
    const o = (y * S + x) * 4;
    data[o] = 255; data[o + 1] = Math.round(rough * 255); data[o + 2] = Math.round((0.15 + 0.25 * (1 - rough)) * 255); data[o + 3] = 255;
  }
  const tex = new THREE.DataTexture(data, S, S, THREE.RGBAFormat);  // no canvas: this also builds in a test environment without a DOM
  tex.needsUpdate = true; tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.anisotropy = 8; tex.generateMipmaps = true; tex.minFilter = THREE.LinearMipmapLinearFilter;
  const mat = new THREE.MeshStandardMaterial({ vertexColors: true, roughnessMap: tex, roughness: 1, metalness: 0.08, envMap: env, envMapIntensity: 0.16, bumpMap: tex, bumpScale: 1.5 });
  const ground = new THREE.Mesh(geo, mat);
  group.add(ground);
  owned.push(geo, mat, tex);

  // puddles
  const R = mulberry(5);
  let puddleMesh: THREE.Mesh | null = null;
  let reflector: Reflector | null = null;
  const shapes = PUDDLES.map((p) => new THREE.ShapeGeometry(blob(p, R), 6));
  const merged = mergeGeometries(shapes);
  shapes.forEach((s) => s.dispose());
  if (merged) {
    merged.rotateX(-Math.PI / 2);
    merged.translate(0, 0.04, 0);
    owned.push(merged);
    if (quality === 'performance') {
      puddleMesh = new THREE.Mesh(merged, new THREE.MeshStandardMaterial({ color: 0x050506, roughness: 0.05, metalness: 0.9, envMap: env, envMapIntensity: 1.6 }));
      owned.push(puddleMesh.material as THREE.Material);
      group.add(puddleMesh);
    } else {
      const size = quality === 'high' ? 1024 : 512;
      reflector = new Reflector(merged, { textureWidth: size, textureHeight: size, color: 0x44464a, clipBias: 0.003 });
      puddleMesh = reflector;
      group.add(reflector);
      owned.push((reflector as unknown as { getRenderTarget(): THREE.WebGLRenderTarget }).getRenderTarget());
    }
  }
  const setReflectionHidden = (hidden: THREE.Object3D[]) => {
    if (!reflector) return;
    const orig = reflector.onBeforeRender;
    reflector.onBeforeRender = function (this: THREE.Object3D, ...a: Parameters<typeof orig>) {
      const was = hidden.map((o) => o.visible);
      hidden.forEach((o) => { o.visible = false; });
      orig.apply(this, a);
      hidden.forEach((o, i) => { o.visible = was[i]; });
    } as typeof orig;
  };
  return { group, puddleMesh, heightAt: groundHeight, setReflectionHidden, dispose: () => { owned.forEach((o) => o.dispose()); } };
}

/** Wet rocks: instanced, displaced icosahedra of several sizes placed with a seeded scatter around given centres; returns the mesh and the instance count. */
export function buildRocks(centres: Array<{ x: number; z: number; r: number; n: number }>, heightAt: (x: number, z: number) => number, env: THREE.Texture | null,
  owned: Array<{ dispose(): void }>, detail: number, calm: Array<{ x: number; z: number; r: number }> = []): THREE.InstancedMesh {
  const base = mergeVertices(new THREE.IcosahedronGeometry(1, detail).deleteAttribute('uv').deleteAttribute('normal'));  // shared vertices: smooth normals after the displacement
  const { fbm } = makeNoise(9);
  const p = base.getAttribute('position');
  for (let i = 0; i < p.count; i++) {
    // angular, ridged relief: cut-stone forms rather than pebbles
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i), n1 = fbm(x * 1.7 + 5, y * 1.7 + z * 1.4, 3), ridge = 1 - Math.abs(2 * fbm(x * 2.6 + 9, z * 2.6 + y, 2) - 1);
    const d = 0.62 + 0.55 * n1 + 0.34 * ridge * ridge;
    p.setXYZ(i, x * d, Math.max(y * d * 0.7, -0.25), z * d);
  }
  base.computeVertexNormals();
  const total = centres.reduce((a, c) => a + c.n, 0);
  const mat = new THREE.MeshPhysicalMaterial({ color: 0x0a0b0d, roughness: 0.5, metalness: 0.3, clearcoat: 0.3, clearcoatRoughness: 0.4, flatShading: true, envMap: env, envMapIntensity: 0.45 });
  const mesh = new THREE.InstancedMesh(base, mat, total);
  const R = mulberry(21), M = new THREE.Matrix4(), Q = new THREE.Quaternion(), S = new THREE.Vector3(), P = new THREE.Vector3(), E = new THREE.Euler();
  let k = 0;
  for (const c of centres) for (let i = 0; i < c.n; i++) {
    const a = R() * Math.PI * 2, d = Math.sqrt(R()) * c.r, x = c.x + Math.cos(a) * d, z = c.z + Math.sin(a) * d, s = (0.25 + Math.pow(R(), 2.6) * 1.7) * (calm.some((q) => Math.hypot(x - q.x, z - q.z) < q.r) ? 0.3 : 1);
    P.set(x, heightAt(x, z) + s * 0.18, z); S.set(s * (0.8 + R() * 0.6), s * (0.7 + R() * 0.7), s * (0.8 + R() * 0.6));
    E.set(R() * 0.5, R() * 6.28, R() * 0.5); Q.setFromEuler(E);
    mesh.setMatrixAt(k, M.compose(P, Q, S));
    mesh.setColorAt(k++, new THREE.Color().setScalar(0.5 + R() * 0.9));
  }
  mesh.instanceMatrix.needsUpdate = true; mesh.instanceColor!.needsUpdate = true; mesh.frustumCulled = false;
  owned.push(base, mat);
  return mesh;
}

/** Wet gravel: thousands of small glossy pebbles scattered over the ground, which give the foreground its fine speckled highlights. */
export function buildPebbles(centres: Array<{ x: number; z: number; r: number; n: number }>, heightAt: (x: number, z: number) => number, env: THREE.Texture | null,
  owned: Array<{ dispose(): void }>): THREE.InstancedMesh {
  const base = mergeVertices(new THREE.IcosahedronGeometry(1, 1).deleteAttribute('uv').deleteAttribute('normal'));
  const { fbm } = makeNoise(13), p = base.getAttribute('position');
  for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i), z = p.getZ(i), d = 0.7 + 0.5 * fbm(x * 2 + 1, y * 2 + z, 2); p.setXYZ(i, x * d, y * d * 0.6, z * d); }
  base.computeVertexNormals();
  const total = centres.reduce((a, c) => a + c.n, 0);
  const mat = new THREE.MeshPhysicalMaterial({ color: 0x151619, roughness: 0.32, metalness: 0.2, clearcoat: 0.9, clearcoatRoughness: 0.12, flatShading: true, envMap: env, envMapIntensity: 0.9 });
  const mesh = new THREE.InstancedMesh(base, mat, total);
  const R = mulberry(55), M = new THREE.Matrix4(), Q = new THREE.Quaternion(), S = new THREE.Vector3(), P = new THREE.Vector3(), E = new THREE.Euler();
  let k = 0;
  for (const c of centres) for (let i = 0; i < c.n; i++) {
    const a = R() * Math.PI * 2, d = Math.sqrt(R()) * c.r, x = c.x + Math.cos(a) * d, z = c.z + Math.sin(a) * d, s = 0.05 + Math.pow(R(), 3) * 0.3;
    P.set(x, heightAt(x, z) + s * 0.3, z); S.set(s * (0.8 + R() * 0.7), s * (0.6 + R() * 0.6), s * (0.8 + R() * 0.7));
    E.set(R() * 3, R() * 6.28, R() * 3); Q.setFromEuler(E);
    mesh.setMatrixAt(k, M.compose(P, Q, S));
    mesh.setColorAt(k++, new THREE.Color().setScalar(0.5 + R() * 1.4));
  }
  mesh.instanceMatrix.needsUpdate = true; mesh.instanceColor!.needsUpdate = true; mesh.frustumCulled = false;
  owned.push(base, mat);
  return mesh;
}
