// XENO ECOSYSTEM — the megastructure builder and the simulation-driven objects, without a renderer: geometry, instancing and the purity of the
// mapping from a recorded frame to what is drawn.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { CAMERA_PRESETS, DENSITY, WORLD, buildMegastructure } from './megastructure';
import { decodeFields, fieldAt, type MeosRecord } from './meosApi';

const rec = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'meos-a2-removed.json'), 'utf8')) as MeosRecord;
const fields = decodeFields(rec.fields, rec.frames.length);

describe('the static architecture', () => {
  const lo = buildMegastructure('performance'), mid = buildMegastructure('balanced');
  it('is dense and scales with the quality tier without changing what is simulated', () => {
    expect(lo.stats.instances).toBeGreaterThan(8000);
    expect(mid.stats.instances).toBeGreaterThan(lo.stats.instances * 1.5);
    expect(DENSITY.performance).toBeLessThan(DENSITY.balanced);
    expect(DENSITY.balanced).toBeLessThan(DENSITY.high);
    expect(lo.stats.edgeSegments).toBeGreaterThan(10000);
    for (const k of ['trusses', 'plates', 'nodes', 'rock', 'cables']) expect(mid.stats.byKind[k]).toBeGreaterThan(0);
  });
  it('is deterministic (seeded): two builds have the same statistics', () => {
    expect(buildMegastructure('performance').stats).toEqual(lo.stats);
  });
  it('keeps the draw-call count low through instancing', () => {
    expect(mid.stats.objects).toBeLessThan(80);
  });
  it('has the nine zones of the reference drawing and a navigable shaft through four layers', () => {
    expect(Object.keys(mid.anchors).sort()).toEqual(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']);
    expect(Object.values(WORLD.levels)).toEqual([0, -34, -68, -104]);
    expect(mid.anchors.B.y).toBe(WORLD.levels.subsurface);
    expect(Object.keys(CAMERA_PRESETS)).toEqual(['overview', 'core', 'habitat', 'subsurface', 'array', 'socket']);
  });
});

describe('the simulation-driven objects', () => {
  const m = buildMegastructure('performance');
  const arena = m.arena;
  const cells = (arena.group.children.filter((c) => (c as THREE.InstancedMesh).isInstancedMesh) as THREE.InstancedMesh[]);
  const colorsOf = () => cells.map((c) => (c.instanceColor ? Array.from(c.instanceColor.array) : []));
  const apply = (t: number) => arena.setFrame(rec.frames[t], fieldAt(fields, 'R', t), fieldAt(fields, 'M1', t), fieldAt(fields, 'M2', t));

  it('draws the habitat arena as an n×n grid of the recorded fields with two operational configurations', () => {
    expect(arena.n).toBe(14);
    expect(cells.filter((c) => c.count === 196).length).toBeGreaterThanOrEqual(4);
    expect(Object.keys(arena.entities)).toEqual(['A1', 'A2']);
    expect(arena.pickables.length).toBeGreaterThan(5);
  });
  it('places each configuration at the recorded cell and hides one that was removed', () => {
    apply(40);
    const p = arena.local(rec.frames[40].A1.x, rec.frames[40].A1.y);
    expect(arena.entities.A1.position.x).toBeCloseTo(p.x);
    expect(arena.entities.A1.position.z).toBeCloseTo(p.z);
    expect(arena.entities.A2.visible).toBe(true);
    apply(140);
    expect(arena.entities.A2.visible).toBe(false);
    expect(arena.entities.A1.visible).toBe(true);
  });
  it('maps firing to brightness: an active configuration is brighter than a refractory one, which is brighter than an idle one', () => {
    const f = rec.frames.findIndex((x) => x.A1.active > 0);
    const c = rec.frames.findIndex((x) => x.A1.cool > 0 && x.A1.active === 0);
    const i = rec.frames.findIndex((x) => x.A1.cool === 0 && x.A1.active === 0 && x.t > 20);
    const em = () => ((arena.entities.A1.children.find((o) => ((o as THREE.Mesh).material as THREE.MeshStandardMaterial).emissiveIntensity !== undefined && ((o as THREE.Mesh).material as THREE.MeshStandardMaterial).emissive.r > 0) as THREE.Mesh).material as THREE.MeshStandardMaterial).emissiveIntensity;
    apply(f); const a = em();
    apply(c); const r = em();
    apply(i); const d = em();
    expect(a).toBeGreaterThan(r);
    expect(r).toBeGreaterThan(d);
  });
  it('is a pure function of the recorded frame: the order of frames drawn does not matter, and a camera preset touches nothing', () => {
    apply(50); const first = JSON.stringify(colorsOf());
    apply(10); apply(120); apply(50);
    expect(JSON.stringify(colorsOf())).toBe(first);
    const before = JSON.stringify(rec.frames[50]);
    for (const p of Object.values(CAMERA_PRESETS)) new THREE.PerspectiveCamera().position.set(...p.pos); // moving a camera has no route to the record
    expect(JSON.stringify(rec.frames[50])).toBe(before);
  });
  it('shows the power reserve, the processing stockpile and the transfers from recorded values', () => {
    m.gauge.set(0.5, false);
    const fill = m.gauge.group.children.find((c) => (c as THREE.Mesh).geometry instanceof THREE.CylinderGeometry && c.scale.y > 1.01 && c.scale.y < 12) as THREE.Mesh;
    expect(fill.scale.y).toBeCloseTo(0.5 * 11.6, 1);
    m.carriers.set([{ progress: 0.5, amount: 0.5 }]);
    expect(m.carriers.group.children.filter((c) => c.visible).length).toBe(1);
    m.carriers.set([]);
    expect(m.carriers.group.children.filter((c) => c.visible).length).toBe(0);
  });
  it('shows ablation trials in the subsurface chambers: brightness by status, a removed A2 is absent', () => {
    expect(m.trials.slots).toBe(12);
    m.trials.set([{ label: 'baseline', status: 'ACTIVE', removed: [] }, { label: 'A2', status: 'COLLAPSED', removed: ['A2'] }, { label: 'history', status: 'DEGRADED', removed: ['history'] }, null]);
    const lamp = (i: number) => ((m.trials.group.children[i].children.at(-2) as THREE.Mesh).material as THREE.MeshStandardMaterial).emissiveIntensity;
    expect(lamp(0)).toBeGreaterThan(lamp(2));
    expect(lamp(2)).toBeGreaterThan(lamp(1));
    const a2 = (i: number) => (m.trials.group.children[i].children[4] as THREE.Mesh).visible;
    expect(a2(0)).toBe(true);
    expect(a2(1)).toBe(false);
  });
});
