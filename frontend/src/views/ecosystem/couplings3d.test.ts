// XENOSCIENCE ECOSYSTEM — the coupling layer of the 3D scene, built on the real arena (three.js runs in node: geometry, materials, transforms and raycasting need no GL context). What is checked is
// the mapping from the record to the scene (state → colour, thickness and opacity; position → the recorded cells), picking, the display operations (isolate, explode, baseline markers) and that
// the layer releases what it created.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { COUPLING_IDS, couplingStates, type CouplingId } from './couplings';
import { buildCouplingLayer, couplingOfObject, type CouplingFrame } from './couplings3d';
import { buildMegastructure } from './megastructure';
import { decodeFields, fieldAt, type MeosRecord } from './meosApi';

const dir = join(dirname(fileURLToPath(import.meta.url)), '__fixtures__');
const cutFx = JSON.parse(readFileSync(join(dir, 'meos-coupling-cut.json'), 'utf8')) as Record<'base' | 'cut', MeosRecord>;
const a2Gone = JSON.parse(readFileSync(join(dir, 'meos-a2-removed.json'), 'utf8')) as MeosRecord;
const fields = decodeFields(a2Gone.fields, a2Gone.frames.length);
const mega = buildMegastructure('performance'), arena = mega.arena;
const place = (t: number) => arena.setFrame(a2Gone.frames[t], fieldAt(fields, 'R', t), fieldAt(fields, 'M1', t), fieldAt(fields, 'M2', t));
const state = (rec: MeosRecord, t: number, over: Partial<CouplingFrame> = {}): CouplingFrame => ({ frame: rec.frames[t], states: couplingStates(rec, t), selected: null, isolated: null, exploded: 0, baseline: null, ...over });
const mat = (m: THREE.Mesh) => m.material as THREE.MeshStandardMaterial;

describe('the coupling layer', () => {
  const layer = buildCouplingLayer(arena);
  it('has one pickable body and one head per coupling, each naming its engine component', () => {
    expect(layer.pickables).toHaveLength(8);
    for (const id of COUPLING_IDS) { expect(couplingOfObject(layer.meshOf(id))).toBe(id); expect(layer.meshOf(id).userData).toEqual({ coupling: id }); }
    expect(couplingOfObject(undefined)).toBeNull();
    expect(couplingOfObject(new THREE.Object3D())).toBeNull();
  });
  it('draws a connected coupling thick and opaque, and a cut one thin, red and translucent', () => {
    place(120);
    layer.set(state(cutFx.cut, 120));
    expect(layer.meshOf('interaction_channel').scale.x).toBeLessThan(layer.meshOf('feedback').scale.x);
    expect(mat(layer.meshOf('interaction_channel')).opacity).toBe(0.4);
    expect(mat(layer.meshOf('feedback')).opacity).toBe(1);
    expect(mat(layer.meshOf('interaction_channel')).color.r).toBeGreaterThan(mat(layer.meshOf('interaction_channel')).color.b);
    expect(mat(layer.meshOf('feedback')).color.b).toBeGreaterThan(mat(layer.meshOf('feedback')).color.r);
    layer.set(state(cutFx.cut, 160));  // restored at 150
    expect(mat(layer.meshOf('interaction_channel')).opacity).toBe(1);
  });
  it('places the channel between the recorded cells of the two configurations while they are apart (ticks 0-2 of the default run)', () => {
    place(1);
    layer.set(state(cutFx.base, 1));
    const f = cutFx.base.frames[1], m = layer.meshOf('interaction_channel');
    expect([f.A1.x, f.A1.y, f.A2.x, f.A2.y]).toEqual([3, 6, 5, 6]);
    const a = arena.local(f.A1.x, f.A1.y), b = arena.local(f.A2.x, f.A2.y);
    // the body's axis points from A1's cell to A2's (the schematic sideways offset moves it parallel to that line, not off it)
    const axis = new THREE.Vector3(0, 1, 0).applyQuaternion(m.quaternion), want = b.clone().sub(a).setY(0).normalize();
    expect(axis.setY(0).normalize().distanceTo(want)).toBeLessThan(1e-3);
    // it starts at A1's cell and ends no further than A2's
    const along = (m.position.x - a.x) * want.x + (m.position.z - a.z) * want.z;
    expect(along).toBeGreaterThan(0); expect(along).toBeLessThan(a.distanceTo(b) + 1e-3);
  });
  it('still draws four distinct, pickable couplings when the two configurations share a cell (most of the run: A2 moves to A1\'s cell by tick 3)', () => {
    place(120);
    const f = cutFx.base.frames[120];
    expect([f.A1.x, f.A1.y]).toEqual([f.A2.x, f.A2.y]);
    layer.set(state(cutFx.base, 120));
    const pos = COUPLING_IDS.map((id) => layer.meshOf(id).position.clone());
    for (let i = 0; i < pos.length; i++) for (let j = i + 1; j < pos.length; j++) expect(pos[i].distanceTo(pos[j])).toBeGreaterThan(0.2);
    for (const id of COUPLING_IDS) { const m = layer.meshOf(id); expect(m.visible).toBe(true); expect(m.scale.y).toBeGreaterThan(0.05); expect(Number.isFinite(m.quaternion.x + m.quaternion.y + m.quaternion.z + m.quaternion.w)).toBe(true); }
  });
  it('hides the couplings of a configuration that is absent', () => {
    const gone = a2Gone.frames.findIndex((f) => !f.A2.present);
    expect(gone).toBeGreaterThan(0);
    place(gone);
    layer.set(state(a2Gone, gone));
    expect(layer.meshOf('interaction_channel').visible).toBe(false);
    expect(layer.meshOf('feedback').visible).toBe(false);
    expect(layer.meshOf('sensor_alteration').visible).toBe(false);
    expect(layer.meshOf('sensor_resource').visible).toBe(true);  // A1 is still there
  });
  it('highlights the selected coupling and isolates one on request (a display operation)', () => {
    place(40);
    layer.set(state(cutFx.base, 40, { selected: 'feedback' }));
    expect(layer.meshOf('feedback').scale.x).toBeGreaterThan(layer.meshOf('interaction_channel').scale.x);
    expect(mat(layer.meshOf('feedback')).emissiveIntensity).toBeGreaterThan(0);
    layer.set(state(cutFx.base, 40, { isolated: 'feedback' }));
    const shown = COUPLING_IDS.filter((id) => layer.meshOf(id).visible);
    expect(shown).toEqual(['feedback']);
    layer.set(state(cutFx.base, 40));
    expect(COUPLING_IDS.every((id) => layer.meshOf(id).visible)).toBe(true);
  });
  it('explodes the layers by a schematic lift and returns to the assembled position without drift', () => {
    place(40);
    layer.set(state(cutFx.base, 40));
    const y0 = { c: layer.meshOf('feedback').position.y, e: arena.entities.A1.position.y };
    layer.set(state(cutFx.base, 40, { exploded: 1 })); layer.set(state(cutFx.base, 40, { exploded: 1 }));  // twice: no accumulation
    expect(layer.meshOf('feedback').position.y).toBeGreaterThan(y0.c + 2);
    expect(arena.entities.A1.position.y).toBeGreaterThan(y0.e + 1);
    layer.set(state(cutFx.base, 40, { exploded: 0 }));
    expect(layer.meshOf('feedback').position.y).toBeCloseTo(y0.c, 6);
    expect(arena.entities.A1.position.y).toBeCloseTo(y0.e, 6);
  });
  it('marks the baseline branch at its recorded cells and hides the marker of an absent configuration', () => {
    place(120);
    const base = { A1: { x: 3, y: 6, present: true }, A2: { x: 9, y: 6, present: false } };
    layer.set(state(cutFx.cut, 120, { baseline: base }));
    const p = arena.local(3, 6);
    expect(layer.baselineMarkers.A1.visible).toBe(true);
    expect(layer.baselineMarkers.A1.position.x).toBeCloseTo(p.x, 6); expect(layer.baselineMarkers.A1.position.z).toBeCloseTo(p.z, 6);
    expect(layer.baselineMarkers.A2.visible).toBe(false);
    layer.set(state(cutFx.cut, 120));
    expect(layer.baselineMarkers.A1.visible).toBe(false);
  });
  it('is picked by a ray: a ray aimed at a coupling returns that coupling', () => {
    place(40);
    layer.set(state(cutFx.base, 40));
    arena.group.updateMatrixWorld(true);
    const rc = new THREE.Raycaster();
    for (const id of ['interaction_channel', 'feedback'] as CouplingId[]) {
      const m = layer.meshOf(id), target = m.getWorldPosition(new THREE.Vector3());
      rc.set(target.clone().add(new THREE.Vector3(0, 6, 0.0)), new THREE.Vector3(0, -1, 0));
      const hit = rc.intersectObjects(layer.pickables, false)[0];
      expect(hit).toBeDefined();
      // two couplings stand over the same line at different heights: the ray from above meets the higher one first, and every hit names a coupling
      expect(couplingOfObject(hit.object)).not.toBeNull();
    }
    rc.set(new THREE.Vector3(500, 6, 500), new THREE.Vector3(0, -1, 0));
    expect(rc.intersectObjects(layer.pickables, false)).toHaveLength(0);
  });
});

describe('mounting and unmounting the layer', () => {
  it('leaves the arena as it found it and disposes every geometry and material it created', () => {
    const before = arena.group.children.length;
    const disposed: string[] = [];
    for (let i = 0; i < 25; i++) {
      const layer = buildCouplingLayer(arena);
      expect(arena.group.children.length).toBe(before + 1);
      const g = layer.meshOf('feedback').geometry, m = layer.meshOf('feedback').material as THREE.Material;
      g.addEventListener('dispose', () => disposed.push('g')); m.addEventListener('dispose', () => disposed.push('m'));
      layer.set(state(cutFx.base, 10));
      layer.dispose();
      expect(arena.group.children.length).toBe(before);
    }
    expect(disposed.filter((x) => x === 'g')).toHaveLength(25);
    expect(disposed.filter((x) => x === 'm')).toHaveLength(25);
  });
});
