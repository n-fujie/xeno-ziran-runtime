// XENOSCIENCE ECOSYSTEM — the observation array in the 3D scene. The cells the overlay draws are checked against the engine: for twelve regimes whose results the engine returned (meos-stage2-regimes.json,
// observe() of the stage-two record), the number of cycles that the overlay's rule would observe equals the engine's own count. The layer is built on the real arena (three.js runs in node).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { buildMegastructure } from './megastructure';
import { FULL_OBSERVATION, type MeosRecord, type Observation } from './meosApi';
import { buildObservationLayer, cellFromLocal, isFullObservation, rectFromCells, seenCells } from './observation3d';

const dir = join(dirname(fileURLToPath(import.meta.url)), '__fixtures__');
const rec = JSON.parse(readFileSync(join(dir, 'meos-stage2.json'), 'utf8')) as MeosRecord;
const regimes = JSON.parse(readFileSync(join(dir, 'meos-stage2-regimes.json'), 'utf8')) as Array<{ name: string; obs: Partial<Observation>; observed_cycles: number; true_cycles: number }>;
const n = rec.config.grid;

/** The cycles an observation would resolve by the overlay's rule: an event is seen at a sampled tick, on a cell the overlay draws. (Threshold and aggregation act on events, not on cells, and are not part of this check.) */
function predictedCycles(obs: Partial<Observation>): number {
  const o = { ...FULL_OBSERVATION, ...obs }, seen = seenCells(o, n), k = Math.max(1, o.sampling_interval);
  const byId = new Map(rec.events.map((e) => [e.id, e]));
  const sees = (id: unknown): boolean => {
    const e = byId.get(id as number);
    if (!e || e.tick % k !== 0) return false;
    const c = e.cell as [number, number] | undefined;
    return !c || seen[c[1] * n + c[0]];
  };
  return rec.events.filter((e) => e.kind === 'cycle' && ['a1_act', 'a2_fire', 'reconfigure', 'a1_fire'].every((key) => sees(e[key]))).length;
}

describe('the cells the observation sees', () => {
  it('are all of them for the full observation', () => {
    expect(seenCells(FULL_OBSERVATION, 14).every(Boolean)).toBe(true);
    expect(isFullObservation(FULL_OBSERVATION)).toBe(true);
    expect(isFullObservation({ ...FULL_OBSERVATION, spatial_stride: 2 })).toBe(false);
  });
  it('follow the lattice, the region and the occluder', () => {
    const s = (o: Partial<Observation>) => seenCells(o, 14);
    expect(s({ spatial_stride: 2 }).filter(Boolean)).toHaveLength(49);
    expect(s({ spatial_stride: 2, spatial_offset: [1, 0] })[6 * 14 + 3]).toBe(true);
    expect(s({ spatial_stride: 2 })[6 * 14 + 3]).toBe(false);
    expect(s({ region: [2, 4, 6, 8] }).filter(Boolean)).toHaveLength(5 * 5);
    expect(s({ occluder: [3, 6, 3, 6] })[6 * 14 + 3]).toBe(false);
    expect(s({ occluder: [3, 6, 3, 6] }).filter(Boolean)).toHaveLength(195);
    expect(s({ region: [0, 0, 6, 13], occluder: [4, 5, 5, 7] }).filter(Boolean)).toHaveLength(7 * 14 - 6);
  });
  it('predict the number of cycles the engine observed, for every regime that limits events by tick, lattice, region or occluder', () => {
    const checked = regimes.filter((r) => !('threshold' in r.obs) && !('aggregation' in r.obs));
    expect(checked.length).toBeGreaterThanOrEqual(12);
    for (const r of checked) expect(predictedCycles(r.obs), `${r.name}: engine observed ${r.observed_cycles} of ${r.true_cycles}`).toBe(r.observed_cycles);
    // the regimes are not all alike: the check is not vacuous
    expect(new Set(checked.map((r) => r.observed_cycles)).size).toBeGreaterThanOrEqual(3);
  });
});

describe('a rectangle from two clicked cells', () => {
  it('is ordered as the engine reads it and kept inside the grid', () => {
    expect(rectFromCells([6, 8], [2, 4], 14)).toEqual([2, 4, 6, 8]);
    expect(rectFromCells([-3, 5], [40, 2], 14)).toEqual([0, 2, 13, 5]);
    expect(rectFromCells([3, 6], [3, 6], 14)).toEqual([3, 6, 3, 6]);
  });
});

describe('the observation layer', () => {
  const mega = buildMegastructure('performance'), arena = mega.arena;
  const layer = buildObservationLayer(arena);
  const shown = () => { const m = new THREE.Matrix4(), v = new THREE.Vector3(); let c = 0; for (let i = 0; i < arena.n * arena.n; i++) { layer.tiles.getMatrixAt(i, m); v.setFromMatrixScale(m); if (v.x > 0) c++; } return c; };

  it('has an invisible picking floor and one tile per cell', () => {
    expect(layer.floor.userData).toEqual({ observationFloor: true });
    expect((layer.floor.material as THREE.Material).visible).toBe(false);
    expect(layer.tiles.count).toBe(arena.n * arena.n);
  });
  it('shows exactly the cells the regime sees, and hides the overlay when asked', () => {
    for (const r of regimes.filter((x) => !('threshold' in x.obs) && !('aggregation' in x.obs))) {
      layer.set({ obs: { ...FULL_OBSERVATION, ...r.obs } as Observation, overlay: true, pending: null });
      expect(shown(), r.name).toBe(seenCells(r.obs, arena.n).filter(Boolean).length);
    }
    layer.set({ obs: FULL_OBSERVATION, overlay: false, pending: null });
    expect(layer.tiles.visible).toBe(false);
  });
  it('outlines the region and the occluder only when they are set, and marks a pending corner', () => {
    const lines = () => layer.group.children.filter((c) => (c as THREE.LineLoop).isLineLoop).map((c) => c.visible);
    layer.set({ obs: FULL_OBSERVATION, overlay: true, pending: null });
    expect(lines()).toEqual([false, false, false]);
    layer.set({ obs: { ...FULL_OBSERVATION, region: [2, 4, 6, 8], occluder: [3, 6, 3, 6] }, overlay: true, pending: [5, 5] });
    expect(lines()).toEqual([true, true, true]);
  });
  it('answers a ray from above with the cell under it', () => {
    arena.group.updateMatrixWorld(true);
    const rc = new THREE.Raycaster();
    for (const [x, y] of [[0, 0], [3, 6], [13, 13], [7, 2]] as Array<[number, number]>) {
      const w = arena.group.localToWorld(arena.local(x, y).clone());
      rc.set(w.clone().add(new THREE.Vector3(0, 10, 0)), new THREE.Vector3(0, -1, 0));
      expect(layer.cellAt(rc), `cell ${x},${y}`).toEqual([x, y]);
    }
    rc.set(new THREE.Vector3(900, 10, 900), new THREE.Vector3(0, -1, 0));
    expect(layer.cellAt(rc)).toBeNull();
    expect(cellFromLocal(arena, arena.local(5, 9).clone().add(new THREE.Vector3(0.01, 0, 0.01)))).toEqual([5, 9]);
  });
  it('can be mounted and unmounted repeatedly without leaving anything in the arena or undisposed', () => {
    const before = arena.group.children.length, disposed: string[] = [];
    for (let i = 0; i < 20; i++) {
      const l = buildObservationLayer(arena);
      expect(arena.group.children.length).toBe(before + 1);
      l.floor.geometry.addEventListener('dispose', () => disposed.push('g')); l.tiles.addEventListener('dispose', () => disposed.push('t'));
      l.set({ obs: { ...FULL_OBSERVATION, spatial_stride: 2 }, overlay: true, pending: null });
      l.dispose();
      expect(arena.group.children.length).toBe(before);
    }
    expect(disposed.filter((x) => x === 'g')).toHaveLength(20); expect(disposed.filter((x) => x === 't')).toHaveLength(20);
  });
});
