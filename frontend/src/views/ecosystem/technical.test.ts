// XENO ECOSYSTEM — the technical inspection drawings are computed from the built geometry: projections, measured dimensions, component identifiers and states. Nothing on a sheet is
// typed in, so these tests build the bodies and check the numbers against the parameters they were built from.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { buildBodies } from './bodies';
import { bodyState } from './bodyState';
import type { MeosRecord } from './meosApi';
import { probeDimensions } from './probes';
import { PLATE_DEPTH } from './ncb';
import { cableRoutes, collectInstances, collectSegments, componentRows, dimensionLines, measure, partStates, project } from './technical';

const rec = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'meos-stage2.json'), 'utf8')) as MeosRecord;
const body = buildBodies('performance', null, () => 0);
const aim = new THREE.Vector3(-66, 0, 16);

describe('projection', () => {
  it('maps a point into the front, side and top views', () => {
    const p = new THREE.Vector3(1, 2, 3);
    expect(project(p, 'front')).toEqual([1, -2]);
    expect(project(p, 'side')).toEqual([3, -2]);
    expect(project(p, 'top')).toEqual([1, 3]);
  });
  it('projects the edges of a box into the extent of the box, in the frame of its root', () => {
    const root = new THREE.Group(); root.position.set(50, 7, -9); root.rotation.y = 0.8;
    const m = new THREE.Mesh(new THREE.BoxGeometry(2, 4, 6), new THREE.MeshBasicMaterial()); root.add(m);
    const f = collectSegments(root, 'front'), s = collectSegments(root, 'side'), t = collectSegments(root, 'top');
    expect(f.maxX - f.minX).toBeCloseTo(2, 5); expect(f.maxY - f.minY).toBeCloseTo(4, 5);  // independent of where the root stands and how it is turned
    expect(s.maxX - s.minX).toBeCloseTo(6, 5); expect(t.maxY - t.minY).toBeCloseTo(6, 5);
    expect(f.data.length / 4).toBe(12);  // the twelve edges
  });
  it('uses the first level of a LOD only', () => {
    const root = new THREE.Group(), lod = new THREE.LOD();
    lod.addLevel(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1)), 0); lod.addLevel(new THREE.Mesh(new THREE.BoxGeometry(9, 9, 9)), 50); root.add(lod);
    const f = collectSegments(root, 'front');
    expect(f.maxX - f.minX).toBeCloseTo(1, 6);
  });
});

describe('measured dimensions', () => {
  body.set(bodyState(rec, 120, null), aim);
  it('reads the height of node A from its geometry: the frame height it was built with, the mast and lamp above it and the probe below it', () => {
    const a = body.parts.find((p) => p.id === 'A')!, probe = Number(body.parts.find((p) => p.id === 'A1')!.params!.length), e = measure(a.object, body.ncb);
    expect(e.size.y).toBeGreaterThan(Number(a.params!.h) + probe);
    expect(e.size.y).toBeLessThan(Number(a.params!.h) + probe + 1.3);
  });
  it('reads probe lengths from the geometry and they equal the specified lengths', () => {
    for (const id of ['A1', 'B1', 'C1', 'O1', 'O4']) {
      const pr = body.nodes.flatMap((n) => n.probes).concat(body.observer.probes).find((p) => p.spec.id === id)!, d = probeDimensions(pr);
      expect(d.length).toBe(pr.spec.length);
      expect(d.measuredLength).toBeGreaterThanOrEqual(pr.spec.length - 0.01);
      expect(d.measuredLength).toBeLessThan(pr.spec.length * 1.2);
    }
  });
  it('reports the plate thickness as the build parameter, and that parameter is the real extrusion depth', () => {
    expect(PLATE_DEPTH).toBe(0.09);
    expect(body.stats.plateDepth).toBe(PLATE_DEPTH);
    const rows = componentRows(body, 'ncb', bodyState(rec, 120, null));
    expect(rows.find((r) => r.id === 'A')!.params).toContain('plateThickness 0.09');
  });
  it('lists the dimension lines of a view: overall width and height equal the measured extent of the body', () => {
    for (const which of ['ncb', 'observer'] as const) {
      const root = which === 'ncb' ? body.ncb : body.obs, ext = measure(root, root), dims = dimensionLines(body, which, 'front');
      expect(dims.find((d) => d.id === 'W')!.value).toBeCloseTo(ext.size.x, 1);
      expect(dims.find((d) => d.id === 'H')!.value).toBeCloseTo(ext.size.y, 1);
    }
  });
});

describe('components, states and routing', () => {
  it('gives every listed component an identifier, built-from parameters, a measured extent and a state with its reason', () => {
    const rows = componentRows(body, 'ncb', bodyState(rec, 120, null));
    expect(rows.length).toBeGreaterThan(12);
    for (const r of rows) { expect(r.id.length).toBeGreaterThan(0); expect(r.because.length).toBeGreaterThan(0); expect(['active', 'idle', 'inactive', 'retracted', 'overloaded', 'cut', 'asleep']).toContain(r.state); }
    expect(new Set(rows.map((r) => r.id)).size).toBe(rows.length);
  });
  it('shows the coupling as cut while the interaction channel is cut and as intact after', () => {
    body.set(bodyState(rec, 120, null), aim); expect(partStates(body.parts, bodyState(rec, 120, null))['cable.BCb'].state).toBe('cut');
    expect(partStates(body.parts, bodyState(rec, 160, null))['cable.BCb'].state).toBe('active');
  });
  it('reads collapse, sampling and the Address Domain fault into the states of the probes', () => {
    const s = (t: number) => partStates(body.parts, bodyState(rec, t, null));
    expect(s(150).A1.state).toBe('retracted'); expect(s(150).O1.state).toBe('retracted');
    expect(s(210).C1.state === 'overloaded' || s(210).C1.state === 'asleep' || s(210).C1.state === 'idle' || s(210).C1.state === 'active').toBe(true);
    expect(s(210).C1.because).toContain('probe state');
  });
  it('routes the cables as polylines of the three kinds in every view, and draws fasteners as dots', () => {
    const r = cableRoutes(body, 'ncb', 'top');
    expect(new Set(r.map((x) => x.kind))).toEqual(new Set(['power', 'resource', 'data']));
    expect(r.every((x) => x.pts.length === 25)).toBe(true);
    expect(collectInstances(body.ncb, 'front').length / 2).toBeGreaterThan(50);
  });
  it('draws every body: the edge lists of the three views are not empty and share the vertical extent between front and side', () => {
    for (const which of ['ncb', 'observer'] as const) {
      const root = which === 'ncb' ? body.ncb : body.obs, f = collectSegments(root, 'front'), sd = collectSegments(root, 'side');
      expect(f.data.length / 4).toBeGreaterThan(1000);
      expect(f.maxY - f.minY).toBeCloseTo(sd.maxY - sd.minY, 4);
    }
  }, 120000);
});
