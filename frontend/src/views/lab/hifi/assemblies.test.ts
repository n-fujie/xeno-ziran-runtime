import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { validate } from '../labScene';
import { buildLab, type Quality } from './assemblies';
import { PHYS, physToView, type V3 } from './coords';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..', '..');
const load = (n: string) => validate(JSON.parse(readFileSync(join(root, `backend/experiments/results/lab/${n}.json`), 'utf8')));
const SEP = load('m9-separated-resources-7000');

describe('the scene graph draws executable objects at the transformed recorded positions', () => {
  it('every carriage tool tip and every sample sits exactly at physToView(recorded position)', () => {
    const lab = buildLab(SEP, 'balanced');
    for (const i of [0, 333, 959]) {
      const sig = lab.signature(i);
      const ph = SEP.steps[i].physics!;
      for (const [k, g] of Object.entries(ph.gantries)) expect(sig[`gantry:${k}`]).toEqual(physToView(g.tip as V3));
      for (const [k, p] of Object.entries(ph.samples)) expect(sig[`sample:${k}`]).toEqual(physToView(p as V3));
    }
  });
  it('chamber floors and walls have the MuJoCo geom sizes and positions', () => {
    const lab = buildLab(SEP, 'balanced');
    lab.root.updateMatrixWorld(true);
    const c = SEP.chambers[0];
    const phys = lab.layers.A.find((o) => o.userData.kind === 'chamber collision geometry' && o.userData.sel?.id === c.cid)!;
    const bb = new THREE.Box3().setFromObject(phys);
    // MuJoCo: floor box half (1.3, 1.3, 0.05) at z = 0; walls half (0.03, 1.3, 0.35) at (±1.3, 0, 0.35) and (0, ±1.3, 0.35)
    expect(bb.max.x - bb.min.x).toBeCloseTo(2 * PHYS.CH + 2 * PHYS.WALL_T, 6);
    expect(bb.max.z - bb.min.z).toBeCloseTo(2 * PHYS.CH + 2 * PHYS.WALL_T, 6);
    expect(bb.min.y).toBeCloseTo(0.25 - 0.05, 6);  // floor bottom: physics z = −0.05
    expect(bb.max.y).toBeCloseTo(0.25 + PHYS.WALL_H, 6);  // wall top: physics z = 0.7
    expect((bb.max.x + bb.min.x) / 2).toBeCloseTo(c.position[0], 6);
    expect((bb.max.z + bb.min.z) / 2).toBeCloseTo(c.position[2], 6);
    const ys = new Set<number>();
    phys.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      const pos = m.geometry.attributes.position;
      for (let k = 0; k < pos.count; k++) ys.add(Math.round(new THREE.Vector3().fromBufferAttribute(pos, k).applyMatrix4(m.matrixWorld).y * 1e6) / 1e6);
    });
    expect(ys.has(0.3)).toBe(true);  // the floor top plane (physics z = 0.05)
  });
  it('every object carries a layer and a category; architecture never carries a selection of an apparatus', () => {
    const lab = buildLab(SEP, 'high');
    let n = 0;
    lab.root.traverse((o) => {
      if (!(o as THREE.Mesh).isMesh) return;
      n++;
      if (o.userData.layer === undefined) return;  // geometry added by the renderer (none expected)
      expect(['A', 'B', 'C']).toContain(o.userData.layer);
      expect([1, 2, 3, 4]).toContain(o.userData.category);
      if (o.userData.layer === 'C') expect(o.userData.category).toBe(4);
      if (o.userData.category === 4) expect(o.userData.sel).toBeUndefined();
    });
    expect(n).toBeGreaterThan(300);
  });
});

describe('quality levels change detail, never the scientific state drawn', () => {
  it('layer A and B transforms are identical at every quality level', () => {
    const sigs = (['performance', 'balanced', 'high'] as Quality[]).map((q) => buildLab(SEP, q).signature(480));
    expect(sigs[1]).toEqual(sigs[0]);
    expect(sigs[2]).toEqual(sigs[0]);
  });
  it('detail differs between levels (instanced parts), so the comparison above is not vacuous', () => {
    const count = (q: Quality) => { let n = 0; buildLab(SEP, q).root.traverse((o) => { if ((o as THREE.Mesh).isMesh) n++; }); return n; };
    expect(count('high')).toBeGreaterThan(count('performance'));
  });
});

describe('mechanical coherence', () => {
  it('no gantry column or rail passes through a chamber housing (found in browser screenshots, fixed)', async () => {
    const { bayEnvelope } = await import('./assemblies');
    const housing = PHYS.CH + 0.3;
    for (const bay of Object.keys(SEP.layout!.bays)) {
      const e = bayEnvelope(SEP, bay);
      for (const c of SEP.chambers) {
        const [cx, cz] = [c.position[0], c.position[2]];
        for (const [x, z] of [[e.x0, e.y0], [e.x0, e.y1], [e.x1, e.y0], [e.x1, e.y1]]) {  // columns
          expect(Math.abs(x - cx) > housing || Math.abs(z - cz) > housing, `bay ${bay} column vs ${c.cid}`).toBe(true);
        }
        if (c.cid.split('.')[0] !== bay) continue;
        for (const z of [e.y0, e.y1]) expect(Math.abs(z - cz)).toBeGreaterThan(housing);  // rails along x at y0, y1
        for (const x of [e.x0, e.x1]) expect(Math.abs(x - cx)).toBeGreaterThan(housing);
      }
    }
  });
});

describe('backward compatibility with earlier record schemas', () => {
  it('a schema-1 record without physics (M2) and one with physics but no systems (M3) build and draw', async () => {
    const { inspect, levels, transfers } = await import('./model');
    for (const [name, physics] of [['m2-run-9100', false], ['m3-physical-9100', true]] as [string, boolean][]) {
      const rec = load(name);
      expect(rec.schema).toBe('xzr.labrun/1');
      const lab = buildLab(rec, 'balanced');
      const sig = lab.signature(rec.steps.length - 1);
      expect(Object.keys(sig).some((k) => k.startsWith('gantry:'))).toBe(physics);
      expect(levels(rec, 0, 'A')).toBeNull();  // no scientific systems in these records: reported as absent, not zero
      const f = inspect(rec, 0, { kind: 'chamber', id: rec.chambers[0].cid });
      if (!physics) expect(f.fields.some((x) => x.status === 'unmeasured')).toBe(true);
      expect(Array.isArray(transfers(rec, rec.steps[rec.steps.length - 1].t))).toBe(true);
    }
  });
});
