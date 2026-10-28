// XENO ECOSYSTEM — the experimental bodies and the wet ground, without a renderer: what the record says about the bodies (a pure mapping), that the geometry builds,
// that the ground faces up, and that the lamps and the arm answer to the state and to nothing else.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { bodyState, buildBodies, FLASH_TICKS, perforated } from './bodies';
import { FULL_OBSERVATION, type MeosRecord } from './meosApi';
import { PUDDLES, buildTerrain, makeNoise } from './terrain';

const dir = join(dirname(fileURLToPath(import.meta.url)), '__fixtures__');
const rec = JSON.parse(readFileSync(join(dir, 'meos-stage2.json'), 'utf8')) as MeosRecord;
const rec1 = JSON.parse(readFileSync(join(dir, 'meos-a2-removed.json'), 'utf8')) as MeosRecord;

describe('bodyState', () => {
  it('reads the last A1 firing from the events, as an age in ticks', () => {
    const fires = rec.events.filter((e) => e.kind === 'fire' && e.actor === 'A1').map((e) => e.tick);
    const t = fires[10] + 2;
    expect(bodyState(rec, t, null).a1FireAge).toBe(t - Math.max(...fires.filter((f) => f <= t)));
    const first = bodyState(rec, 0, null).a1FireAge;
    expect(first === null || first >= 0).toBe(true);
  });
  it('marks the coupling as cut while the interaction channel is cut, and not before or after', () => {
    expect(bodyState(rec, 90, null).couplingCut).toBe(false);
    expect(bodyState(rec, 120, null).couplingCut).toBe(true);
    expect(bodyState(rec, 160, null).couplingCut).toBe(false);
  });
  it('follows the observation: a sampled tick and its coverage', () => {
    expect(bodyState(rec, 8, { ...FULL_OBSERVATION, sampling_interval: 4 }).sampling).toBe(true);
    expect(bodyState(rec, 9, { ...FULL_OBSERVATION, sampling_interval: 4 }).sampling).toBe(false);
    expect(bodyState(rec, 9, { ...FULL_OBSERVATION, spatial_stride: 2 }).coverage).toBeCloseTo(0.25, 6);
  });
  it('marks recovery only after a collapse was left, and reads a record without traces', () => {
    expect(bodyState(rec, 100, null).recovered).toBe(false);
    expect(bodyState(rec, 170, null).recovered).toBe(true);
    expect(() => bodyState(rec1, 100, null)).not.toThrow();
    expect(bodyState(rec1, 100, null).interaction).toBe(0);
  });
  it('is pure', () => {
    expect(bodyState(rec, 130, null)).toEqual(bodyState(rec, 130, null));
  });
});

describe('geometry', () => {
  it('makes a perforated plate with real holes: more geometry than the plain outline, and more of it for a finer pitch', () => {
    const tri: Array<[number, number]> = [[0, 0], [3, 0], [1.5, 2.6]];
    const plain = perforated(tri, { hole: 0.01, pitch: 100, margin: 5, depth: 0.1 });
    const dense = perforated(tri, { hole: 0.06, pitch: 0.25, margin: 0.2, depth: 0.1 });
    const sparse = perforated(tri, { hole: 0.06, pitch: 0.5, margin: 0.2, depth: 0.1 });
    expect(dense.getAttribute('position').count).toBeGreaterThan(sparse.getAttribute('position').count);
    expect(sparse.getAttribute('position').count).toBeGreaterThan(plain.getAttribute('position').count);
  });
  it('builds the two bodies at every quality tier, with more detail at a higher tier', () => {
    const counts = (['performance', 'balanced', 'high'] as const).map((q) => {
      const b = buildBodies(q, null, () => 0);
      let n = 0;
      b.group.traverse((o) => { const g = (o as THREE.Mesh).geometry; if (g) n += g.getAttribute('position').count; });
      b.dispose();
      return n;
    });
    expect(counts[0]).toBeGreaterThan(20000);
    expect(counts[1]).toBeGreaterThan(counts[0]);
    expect(counts[2]).toBeGreaterThan(counts[1]);
  });
});

describe('the ground', () => {
  const terrain = buildTerrain('performance', 34, [], null);
  it('faces up: every sampled triangle of the ground has an upward normal', () => {
    const ground = terrain.group.children.find((c) => (c as THREE.Mesh).isMesh) as THREE.Mesh;
    const pos = ground.geometry.getAttribute('position'), idx = ground.geometry.index!;
    let up = 0, n = 0;
    for (let i = 0; i < idx.count; i += 3 * 97) {
      const a = new THREE.Vector3().fromBufferAttribute(pos, idx.getX(i)), b = new THREE.Vector3().fromBufferAttribute(pos, idx.getX(i + 1)), c = new THREE.Vector3().fromBufferAttribute(pos, idx.getX(i + 2));
      n++;
      if (b.sub(a).cross(c.sub(a)).y > 0) up++;
    }
    expect(n).toBeGreaterThan(20);
    expect(up).toBe(n);
  });
  it('is deterministic and level where the work areas stand', () => {
    expect(makeNoise(3).fbm(1.3, 2.1)).toBe(makeNoise(3).fbm(1.3, 2.1));
    expect(Math.abs(terrain.heightAt(-104, 4))).toBeLessThan(0.5);
    expect(Math.abs(terrain.heightAt(-66, 16))).toBeLessThan(0.5);
    expect(PUDDLES.length).toBeGreaterThan(3);
  });
});

describe('the bodies answer to the state', () => {
  const b = buildBodies('performance', null, () => 0);
  const lit = (): number[] => {
    const out: number[] = [];
    b.group.traverse((o) => {
      const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
      if (m && m.emissive && m.emissive.r > 0.5) out.push(m.emissiveIntensity);
    });
    return out;
  };
  const idle = { sampling: false, coverage: 1, aim: [6.5, 6.5] as [number, number], a1FireAge: null, renewAge: null, interaction: 0, couplingCut: false, a2Present: true, status: 'ACTIVE', recovered: false };
  const target = new THREE.Vector3(-66, 0, 16);
  it('lights a lamp for a few ticks after an event and not otherwise', () => {
    b.set(idle, target);
    const quiet = Math.max(...lit());
    b.set({ ...idle, a1FireAge: 0, renewAge: 1 }, target);
    const fired = Math.max(...lit());
    b.set({ ...idle, a1FireAge: FLASH_TICKS + 3, renewAge: FLASH_TICKS + 3 }, target);
    expect(fired).toBeGreaterThan(quiet * 5);
    expect(Math.max(...lit())).toBeLessThanOrEqual(quiet + 1e-9);
  });
  it('keeps node C dark while A2 is absent', () => {
    b.set({ ...idle, renewAge: 0, a2Present: false }, target);
    expect(lit().filter((v) => v === 0).length).toBeGreaterThan(0);
  });
  it('turns the observation arm toward a different target when the target moves', () => {
    const yaws = (): string => {
      const r: number[] = [];
      b.group.traverse((o) => { if (o.type === 'Group' && o.parent?.type === 'Group' && o.rotation.y !== 0) r.push(o.rotation.y); });
      return JSON.stringify(r);
    };
    b.set(idle, new THREE.Vector3(-66, 0, 16));
    const a = yaws();
    b.set(idle, new THREE.Vector3(-120, 0, 60));
    expect(yaws()).not.toBe(a);
  });
});
