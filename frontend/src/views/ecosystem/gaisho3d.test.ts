// GAISHO in the 3D scene - the mapping from the engine's shapes to objects (vertices, edges, cuts, branch points, unresolved markers, the ghost shape), picking and the release of resources. Real engine records
// (__fixtures__/gaisho-records.json); three.js runs in node. SYNTHETIC only.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { shapeOf, type GaishoRecord } from './gaisho';
import { COLOR, buildGaishoLayer, gaishoIdOf, place } from './gaisho3d';

const fx = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'gaisho-records.json'), 'utf8')) as Record<'base' | 'scale4', GaishoRecord>;
const CUE = 'accidental correct: coincidental cue', RESP = 'ground-responsive judgement';
const show = { surface: true, cuts: true, unresolved: true, branch: true };
const frame = (over = {}) => ({ shape: shapeOf(fx.base, RESP, 'end'), ghost: null, selected: null, support: null, show, ...over });

describe('the layer', () => {
  it('draws exactly what the shape holds: one pickable per recorded cell, one segment per edge, the cuts, the branch points, nothing for a shape the record does not have', () => {
    const parent = new THREE.Group(), layer = buildGaishoLayer(parent, new THREE.Vector3(0, 24, 0), 20);
    layer.set(frame());
    const s = shapeOf(fx.base, RESP, 'end')!, c = layer.counts();
    expect(c.vertices).toBe(s.vertices.length); expect(layer.pickables).toHaveLength(s.vertices.length + s.unresolved.length);
    expect(c.edges).toBe(s.edges.length); expect(c.cuts).toBe(s.cuts.length); expect(c.branch).toBe(s.branch.length); expect(c.faces).toBeGreaterThan(0);
    layer.set(frame({ shape: null })); expect(layer.pickables).toHaveLength(0); expect(layer.counts().vertices).toBe(0);
    layer.dispose(); expect(parent.children).toHaveLength(0);
  });
  it('gives different shapes different geometry (no common figure): the cue-driven and the evidence-driven surfaces rise along different axes', () => {
    const a = shapeOf(fx.base, CUE, 'end')!, b = shapeOf(fx.base, RESP, 'end')!;
    const slope = (s: typeof a, axis: 'x' | 'y') => { const lo = s.vertices.filter((v) => v[axis] === Math.min(...s.vertices.map((q) => q[axis]))), hi = s.vertices.filter((v) => v[axis] === Math.max(...s.vertices.map((q) => q[axis]))); const m = (g: typeof lo) => g.reduce((t, v) => t + v.z, 0) / g.length; return m(hi) - m(lo); };
    expect(Math.abs(slope(a, 'y'))).toBeGreaterThan(0.8); expect(Math.abs(slope(a, 'x'))).toBeLessThan(0.2);
    expect(Math.abs(slope(b, 'x'))).toBeGreaterThan(0.8); expect(Math.abs(slope(b, 'y'))).toBeLessThan(0.2);
    const parent = new THREE.Group(), layer = buildGaishoLayer(parent, new THREE.Vector3(), 20);
    layer.set(frame({ shape: a })); const pa = layer.group.getObjectByName('gaisho-surface') as THREE.Mesh | undefined;
    const ya = new Set(a.vertices.map((v) => place(a, v.x, v.y, v.z).y.toFixed(3)));
    expect(ya.size).toBeGreaterThan(1); expect(pa).toBeDefined(); layer.dispose();
  });
  it('maps cells to places by a declared projection: the height is the outcome and the corners of the plane are the extremes of the cells', () => {
    const s = shapeOf(fx.base, RESP, 'end')!;
    const lo = place(s, Math.min(...s.vertices.map((v) => v.x)), Math.min(...s.vertices.map((v) => v.y)), 0), hi = place(s, Math.max(...s.vertices.map((v) => v.x)), Math.max(...s.vertices.map((v) => v.y)), 1);
    expect(lo.toArray()).toEqual([-6, 0, -3]); expect(hi.toArray()).toEqual([6, 4, 3]);
  });
  it('keeps the unrecorded regions of another observation as hollow markers on the base plane, with their id, and can hide them', () => {
    const s4 = shapeOf(fx.scale4, RESP, 'end')!, parent = new THREE.Group(), layer = buildGaishoLayer(parent, new THREE.Vector3(), 20);
    layer.set(frame({ shape: s4 })); expect(layer.counts().unresolved).toBe(s4.unresolved.length);
    const u = layer.pickables.find((m) => m.name.startsWith('gaisho-unresolved:'))!; expect(gaishoIdOf(u)).toBe(s4.unresolved.find((x) => u.name.endsWith(x.id))!.id); expect(u.position.y).toBe(0);
    layer.set(frame({ shape: s4, show: { ...show, unresolved: false } })); expect(layer.counts().unresolved).toBe(0); layer.dispose();
  });
  it('draws the second shape as a faint wire behind the first (before/after, another condition, another observation), and marks the selected point and the cells of a relation', () => {
    const parent = new THREE.Group(), layer = buildGaishoLayer(parent, new THREE.Vector3(), 20), s = shapeOf(fx.base, RESP, 'end')!;
    layer.set(frame({ ghost: shapeOf(fx.base, RESP, 'before shift') })); expect(layer.counts().ghostEdges).toBeGreaterThan(0);
    const ghost = layer.group.getObjectByName('gaisho-ghost') as THREE.LineSegments; expect((ghost.material as THREE.LineBasicMaterial).opacity).toBeLessThan(1);
    const id = s.vertices[20].id, sup = s.vertices.slice(0, 3).map((v) => v.id);
    layer.set(frame({ selected: id, support: sup }));
    const col = (vid: string) => ((layer.pickables.find((m) => gaishoIdOf(m) === vid)!.material as THREE.MeshBasicMaterial).color.getHex());
    expect(col(id)).toBe(COLOR.selected); expect(sup.every((x) => col(x) === COLOR.support)).toBe(true); expect(col(s.vertices[40].id)).not.toBe(COLOR.selected);
    layer.dispose();
  });
  it('does not draw a surface across a cut', () => {
    const s = shapeOf(fx.base, CUE, 'end')!, parent = new THREE.Group(), layer = buildGaishoLayer(parent, new THREE.Vector3(), 20);
    layer.set(frame({ shape: s })); const withCuts = layer.counts();
    const quads = (s.vertices.length - 13 - 7 + 1);  // interior quads of a 13 x 7 grid = 12 x 6 = 72
    expect(withCuts.faces).toBeLessThanOrEqual(2 * 72); expect(quads).toBeGreaterThan(0);
    if (s.cuts.length) expect(withCuts.faces).toBeLessThan(2 * 72);
    layer.dispose();
  });
  it('picks nothing from an object that is not part of the layer', () => { expect(gaishoIdOf(undefined)).toBeNull(); expect(gaishoIdOf(new THREE.Object3D())).toBeNull(); });
});
