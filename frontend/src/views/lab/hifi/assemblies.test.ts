import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { validate, type LabRecord } from '../labScene';
import { JAW_CLOSED, JAW_H, JAW_OPEN, JAW_T, RIM_TOP, RIM_Y0, buildLab, type Quality } from './assemblies';
import { FLOOR_Y, PHYS, chamberFloor, physToView, type V3 } from './coords';

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

describe('connection terminals stay clear of every gantry part over the whole record', () => {
  it('the highest point any rail, bridge, trolley, mast or carriage reaches is below the terminals', async () => {
    const { TERMINAL_Y } = await import('./assemblies');
    const lab = buildLab(SEP, 'high');
    let top = -Infinity;
    for (let i = 0; i < SEP.steps.length; i += 7) {
      lab.apply(i, 0, { coverage: false, conduits: false, events: new Set() });
      lab.root.updateMatrixWorld(true);
      for (const o of lab.layers.A) {
        if (o.userData.sel?.kind !== 'gantry') continue;
        top = Math.max(top, new THREE.Box3().setFromObject(o).max.y);
      }
    }
    expect(top).toBeLessThan(TERMINAL_Y - 0.1);
  });
});

describe('system apparatus never interpenetrate (found in screenshots: a remote sensor inside the hub)', () => {
  it('no two sensor heads, hubs, remote sensors or stores overlap, at sampled steps of every published record', () => {
    for (const name of ['m7-systems-6000', 'm9-separated-resources-7000', 'm9-extinction-relocation-7000']) {
      const rec = load(name);
      const lab = buildLab(rec, 'high');
      for (let i = 0; i < rec.steps.length; i += 60) {
        lab.apply(i, 0, { coverage: false, conduits: false, events: new Set() });
        lab.root.updateMatrixWorld(true);
        const parts: { id: string; box: THREE.Box3 }[] = [];
        lab.root.traverse((o) => {
          const s = o.userData.sel as { kind: string; id: string } | undefined;
          if (s && (s.kind === 'sensor' || s.kind === 'store') && o.parent?.userData.sel?.id !== s.id) parts.push({ id: s.id, box: new THREE.Box3().setFromObject(o) });
        });
        expect(parts.length).toBeGreaterThan(0);
        for (let a = 0; a < parts.length; a++) for (let b = a + 1; b < parts.length; b++) {
          expect(parts[a].box.intersectsBox(parts[b].box), `${name} step ${i}: ${parts[a].id} vs ${parts[b].id}`).toBe(false);
        }
      }
    }
  });
});

describe('a failed gantry is drawn dark without changing any other part (shared-material bug found in review)', () => {
  it('at a recorded failure, only that carriage darkens; every rail keeps the steel colour', () => {
    const rec = load('m7-systems-6000');
    const i = rec.steps.findIndex((s) => Object.values(s.physics!.gantries).some((g) => g.failed));
    expect(i).toBeGreaterThan(0);
    const lab = buildLab(rec, 'balanced');
    lab.apply(i, 0, { coverage: false, conduits: false, events: new Set() });
    const failed = Object.entries(rec.steps[i].physics!.gantries).filter(([, g]) => g.failed).map(([k]) => k);
    const colours = (kind: string) => {
      const out: { id: string; hex: number }[] = [];
      lab.root.traverse((o) => {
        if (o.userData.kind === kind && (o as THREE.Mesh).isMesh) out.push({ id: o.userData.sel?.id, hex: ((o as THREE.Mesh).material as THREE.MeshStandardMaterial).color.getHex() });
      });
      return out;
    };
    for (const r of colours('x slide (rails)')) expect([0x77777c, 0xb9b9be]).toContain(r.hex);  // steel rail, light linear guide
    const carriages = colours('carriage and tool (recorded tool tip)').filter((c) => c.hex !== 0x5c5c62);
    expect(carriages.filter((c) => c.hex === 0x26262a).map((c) => c.id).sort()).toEqual(failed.sort());
  });
});

describe('full reachable envelope of every gantry', () => {
  const statics = (lab: ReturnType<typeof buildLab>) => {  // apparatus that never moves with a gantry
    const out: { what: string; box: THREE.Box3 }[] = [];
    lab.root.updateMatrixWorld(true);
    lab.root.traverse((o) => {
      const s = o.userData.sel as { kind: string; id: string } | undefined;
      if (s && (s.kind === 'sensor' || s.kind === 'store') && o.parent?.userData.sel?.id !== s.id) out.push({ what: s.id, box: new THREE.Box3().setFromObject(o) });
      if (o.userData.kind === 'chamber instrument (activity, memory)' && o.parent?.userData.kind !== o.userData.kind) out.push({ what: `instrument ${o.userData.sel?.id}`, box: new THREE.Box3().setFromObject(o) });
    });
    return out;
  };
  it('every recorded tool tip of every published record lies within its gantry\'s drawn rail envelope', async () => {
    const { bayEnvelope } = await import('./assemblies');
    for (const name of ['m3-physical-9100', 'm7-systems-6000', 'm9-separated-resources-7000', 'm9-extinction-relocation-7000']) {
      const rec = load(name);
      const env = new Map(Object.keys(rec.layout!.bays).map((b) => [b, bayEnvelope(rec, b)]));
      for (const s of rec.steps) {
        for (const [key, g] of Object.entries(s.physics!.gantries)) {
          const e = env.get(g.bay ?? key)!;
          const [x, , z] = physToView(g.tip as V3);
          expect(x >= e.x0 && x <= e.x1 && z >= e.y0 && z <= e.y1, `${name} t${s.t} ${key} at (${x}, ${z})`).toBe(true);
        }
      }
    }
  });
  it('no recorded carriage, tool or mast position intersects a sensor, hub, store or chamber instrument', () => {
    for (const name of ['m7-systems-6000', 'm9-separated-resources-7000', 'm9-extinction-relocation-7000']) {
      const rec = load(name);
      const lab = buildLab(rec, 'high');
      for (let i = 0; i < rec.steps.length; i += 3) {
        lab.apply(i, 0, { coverage: false, conduits: false, events: new Set() });
        const fixed = statics(lab);
        lab.root.traverse((o) => {
          if (o.userData.sel?.kind !== 'gantry' || !(String(o.userData.kind).startsWith('carriage and tool') || o.userData.kind === 'z slide (mast)')) return;
          if (o.parent?.userData.kind === o.userData.kind) return;
          const b = new THREE.Box3().setFromObject(o);
          for (const f of fixed) expect(b.intersectsBox(f.box), `${name} t${rec.steps[i].t} ${o.userData.sel.id} ${o.userData.kind} vs ${f.what}`).toBe(false);
        });
      }
    }
  });
});

describe('synthetic sweep of every gantry over its whole reachable envelope at travel height', () => {
  // A carriage moves in straight lines between its targets (assemblies.ts reachHull).
  it('a carriage and its mast anywhere in the reachable envelope meet no static apparatus, service housing or other gantry\'s column', async () => {
    const { bayEnvelope, reachHull, hullDistance, TRAVEL_TOP } = await import('./assemblies');
    const rec = load('m7-systems-6000');
    const lab = buildLab(rec, 'high');
    lab.apply(0, 0, { coverage: false, conduits: false, events: new Set() });
    lab.root.updateMatrixWorld(true);
    const fixed: { what: string; box: THREE.Box3 }[] = [];
    lab.root.traverse((o) => {
      const s = o.userData.sel as { kind: string; id: string } | undefined;
      const k = o.userData.kind as string | undefined;
      const top = o.parent?.userData.kind !== k;
      if (s && (s.kind === 'sensor' || s.kind === 'store') && o.parent?.userData.sel?.id !== s.id) fixed.push({ what: s.id, box: new THREE.Box3().setFromObject(o) });
      if (k === 'chamber instrument (activity, memory)' && top) fixed.push({ what: `instrument ${s?.id}`, box: new THREE.Box3().setFromObject(o) });
      if (k === 'domain service housing' && top) fixed.push({ what: 'service housing', box: new THREE.Box3().setFromObject(o) });
    });
    for (const f of fixed.filter((x) => x.what.startsWith('instrument'))) expect(f.box.max.y, f.what).toBeLessThanOrEqual(TRAVEL_TOP + 1e-6);
    const rimBoxes = rec.chambers.map((c) => {
      const [cx, , cz] = chamberFloor(c.position as V3);
      return { what: `rim ${c.cid}`, box: new THREE.Box3(new THREE.Vector3(cx - PHYS.CH - 0.12, RIM_Y0 - 0.03, cz - PHYS.CH - 0.12), new THREE.Vector3(cx + PHYS.CH + 0.12, RIM_TOP, cz + PHYS.CH + 0.12)) };
    });
    expect(RIM_TOP).toBeLessThan(TRAVEL_TOP);
    const bays = Object.keys(rec.layout!.bays);
    const envs = new Map(bays.map((b) => [b, bayEnvelope(rec, b)]));
    let checked = 0;
    for (const bay of bays) {
      const h = reachHull(rec, bay);
      const cols: { what: string; box: THREE.Box3 }[] = [];
      for (const [ob, e] of envs) {
        if (ob === bay) continue;  // other gantries' columns and knee braces
        const others = bays.filter((b2) => b2 !== ob).map((b2) => reachHull(rec, b2));
        for (const [cx, cz] of [[e.x0, e.y0], [e.x0, e.y1], [e.x1, e.y0], [e.x1, e.y1]]) {
          if (others.some((h2) => hullDistance(h2, cx, cz) < 1.1)) {  // drawn as a ceiling hanger above the rail
            cols.push({ what: `bay ${ob} rail hanger`, box: new THREE.Box3(new THREE.Vector3(cx - 0.18, 3.45, cz - 0.18), new THREE.Vector3(cx + 0.18, 7.85, cz + 0.18)) });
            continue;
          }
          cols.push({ what: `bay ${ob} column`, box: new THREE.Box3(new THREE.Vector3(cx - 0.25, 0, cz - 0.25), new THREE.Vector3(cx + 0.25, 3.9, cz + 0.25)) });
          const sx = cx === e.x0 ? 1 : -1;
          cols.push({ what: `bay ${ob} knee brace`, box: new THREE.Box3(new THREE.Vector3(Math.min(cx, cx + sx * 0.8), 2.9, cz - 0.04), new THREE.Vector3(Math.max(cx, cx + sx * 0.8), 3.5, cz + 0.04)) });
        }
      }
      const e = envs.get(bay)!;
      for (let x = e.x0; x <= e.x1; x += 0.2) for (let z = e.y0; z <= e.y1; z += 0.2) {
        if (hullDistance(h, x, z) > 0) continue;
        const carriage = new THREE.Box3(new THREE.Vector3(x - 0.12, 1.65, z - 0.12), new THREE.Vector3(x + 0.12, 2.03, z + 0.12));
        const mast = new THREE.Box3(new THREE.Vector3(x - 0.05, 2.03, z - 0.05), new THREE.Vector3(x + 0.05, 3.35, z + 0.05));
        // a carried sample (centre 0.255 m below the tip) and the jaws, open or closed
        // a carried sample anywhere from just above the walls (worn-gantry sag) to its nominal height
        const load = new THREE.Box3(new THREE.Vector3(x - 0.15, TRAVEL_TOP + 1e-3, z - 0.15), new THREE.Vector3(x + 0.15, 1.65 - 0.255 + 0.15, z + 0.15));
        const jaws = new THREE.Box3(new THREE.Vector3(x - JAW_OPEN - JAW_T / 2, 1.65 - JAW_H + 0.02, z - 0.06), new THREE.Vector3(x + JAW_OPEN + JAW_T / 2, 1.65 + 0.025, z + 0.06));
        for (const f of [...fixed, ...cols, ...rimBoxes]) {
          for (const [what, b] of [['carriage', carriage], ['mast', mast], ['carried sample', load], ['jaws', jaws]] as const) {
            expect(b.intersectsBox(f.box), `bay ${bay} ${what} at (${x.toFixed(2)}, ${z.toFixed(2)}) vs ${f.what}`).toBe(false);
          }
        }
        checked++;
      }
    }
    expect(checked).toBeGreaterThan(3000);
  }, 60_000);
});

describe('a carried sample and the gripper jaws clear every static part (found in M8.2: the travel plane ignored the load)', () => {
  // The rim (louvre band and frame) of every chamber, as boxes along its four walls.
  const rims = (rec: LabRecord) => {
    const out: { what: string; box: THREE.Box3 }[] = [];
    for (const c of rec.chambers) {
      const [x, , z] = chamberFloor(c.position as V3);
      const e = PHYS.CH + 0.12;
      for (const [x0, x1, z0, z1] of [[-e, e, PHYS.CH - 0.06, e], [-e, e, -e, -PHYS.CH + 0.06], [PHYS.CH - 0.06, e, -e, e], [-e, -PHYS.CH + 0.06, -e, e]]) {
        out.push({ what: `rim ${c.cid}`, box: new THREE.Box3(new THREE.Vector3(x + x0, RIM_Y0 - 0.03, z + z0), new THREE.Vector3(x + x1, RIM_TOP, z + z1)) });
      }
    }
    return out;
  };
  it('at every recorded step, a carried sample and closed jaws meet no rim, instrument, sensor or store', () => {
    for (const name of ['m7-systems-6000', 'm9-separated-resources-7000', 'm9-extinction-relocation-7000']) {
      const rec = load(name);
      const lab = buildLab(rec, 'high');
      lab.apply(0, 0, { coverage: false, conduits: false, events: new Set() });
      lab.root.updateMatrixWorld(true);
      const fixed = [...rims(rec)];
      lab.root.traverse((o) => {
        const s = o.userData.sel as { kind: string; id: string } | undefined;
        if (s && (s.kind === 'sensor' || s.kind === 'store') && o.parent?.userData.sel?.id !== s.id) fixed.push({ what: s.id, box: new THREE.Box3().setFromObject(o) });
        if (o.userData.kind === 'chamber instrument (activity, memory)' && o.parent?.userData.kind !== o.userData.kind) fixed.push({ what: `instrument ${s?.id}`, box: new THREE.Box3().setFromObject(o) });
      });
      let carried = 0;
      for (const st of rec.steps) {
        for (const g of Object.values(st.physics!.gantries)) {
          if (!g.carrying) continue;
          const [sx, sy, sz] = physToView(st.physics!.samples[g.carrying] as V3);
          const [tx, ty, tz] = physToView(g.tip as V3);
          const sample = new THREE.Box3(new THREE.Vector3(sx - PHYS.HALF, sy - PHYS.HALF, sz - PHYS.HALF), new THREE.Vector3(sx + PHYS.HALF, sy + PHYS.HALF, sz + PHYS.HALF));
          const jaws = new THREE.Box3(new THREE.Vector3(tx - JAW_CLOSED - JAW_T / 2, ty - JAW_H + 0.02, tz - 0.06), new THREE.Vector3(tx + JAW_CLOSED + JAW_T / 2, ty + 0.025, tz + 0.06));
          // the sample is still inside its own chamber while it is lifted: only travel above the walls is checked
          if (sy - PHYS.HALF < FLOOR_Y + PHYS.WALL_H + 0.05) continue;
          carried++;
          for (const f of fixed) {
            expect(sample.intersectsBox(f.box), `${name} t${st.t} sample ${g.carrying} vs ${f.what}`).toBe(false);
            expect(jaws.intersectsBox(f.box), `${name} t${st.t} jaws vs ${f.what}`).toBe(false);
          }
        }
      }
      expect(carried, name).toBeGreaterThan(20);
    }
  }, 60_000);
  it('closed jaws meet the recorded sample faces at every carrying step; open jaws clear every resting sample', () => {
    for (const name of ['m7-systems-6000', 'm9-separated-resources-7000']) {
      const rec = load(name);
      for (const st of rec.steps) {
        for (const g of Object.values(st.physics!.gantries)) {
          const [tx, ty, tz] = physToView(g.tip as V3);
          if (g.carrying) {
            const [sx, , sz] = physToView(st.physics!.samples[g.carrying] as V3);
            expect(Math.abs(tx - sx) + Math.abs(tz - sz), `${name} t${st.t}`).toBeLessThan(0.02);  // carried centred under the tool
            expect(JAW_CLOSED - JAW_T / 2 - PHYS.HALF).toBeGreaterThan(0);
            expect(JAW_CLOSED - JAW_T / 2 - PHYS.HALF).toBeLessThan(0.01);
            continue;
          }
          const jaws = [-1, 1].map((sd) => new THREE.Box3(new THREE.Vector3(tx + sd * JAW_OPEN - JAW_T / 2, ty - JAW_H + 0.02, tz - 0.06), new THREE.Vector3(tx + sd * JAW_OPEN + JAW_T / 2, ty + 0.025, tz + 0.06)));
          const held = new Set(Object.values(st.physics!.gantries).map((x) => x.carrying).filter(Boolean));
          for (const [sid, pos] of Object.entries(st.physics!.samples)) {
            if (held.has(sid)) continue;  // carriages never collide in the model: a relay hand-over co-locates two carriages
            const [sx, sy, sz] = physToView(pos as V3);
            const b = new THREE.Box3(new THREE.Vector3(sx - PHYS.HALF, sy - PHYS.HALF, sz - PHYS.HALF), new THREE.Vector3(sx + PHYS.HALF, sy + PHYS.HALF, sz + PHYS.HALF));
            for (const j of jaws) expect(j.intersectsBox(b), `${name} t${st.t} open jaw vs ${sid}`).toBe(false);
          }
        }
      }
    }
  }, 60_000);
});

describe('relocated system apparatus stand clear of the static installation (M8.2: moved outside the reach envelopes)', () => {
  it('no sensor head, hub, remote sensor or store meets a chamber vessel, a gantry column or a service housing', async () => {
    const { bayEnvelope, reachHull, hullDistance } = await import('./assemblies');
    for (const name of ['m7-systems-6000', 'm9-separated-resources-7000', 'm9-extinction-relocation-7000']) {
      const rec = load(name);
      const lab = buildLab(rec, 'high');
      const bays = Object.keys(rec.layout!.bays);
      const fixed: { what: string; box: THREE.Box3 }[] = rec.chambers.map((c) => {
        const [x, , z] = chamberFloor(c.position as V3);
        const e = PHYS.CH + 0.36;  // vessel, shutter band, actuator housings and corner instrument
        return { what: `chamber ${c.cid}`, box: new THREE.Box3(new THREE.Vector3(x - e, 0, z - e), new THREE.Vector3(x + e, 1.2, z + e)) };
      });
      for (const b of bays) {
        const e = bayEnvelope(rec, b);
        const others = bays.filter((b2) => b2 !== b).map((b2) => reachHull(rec, b2));
        for (const [cx, cz] of [[e.x0, e.y0], [e.x0, e.y1], [e.x1, e.y0], [e.x1, e.y1]]) {
          if (others.some((h2) => hullDistance(h2, cx, cz) < 1.1)) continue;  // hung from the ceiling: nothing at floor level
          fixed.push({ what: `bay ${b} column`, box: new THREE.Box3(new THREE.Vector3(cx - 0.25, 0, cz - 0.25), new THREE.Vector3(cx + 0.25, 3.9, cz + 0.25)) });
        }
      }
      for (let i = 0; i < rec.steps.length; i += 60) {
        lab.apply(i, 0, { coverage: false, conduits: false, events: new Set() });
        lab.root.updateMatrixWorld(true);
        const parts: { id: string; box: THREE.Box3 }[] = [], housings: THREE.Box3[] = [];
        lab.root.traverse((o) => {
          const sel = o.userData.sel as { kind: string; id: string } | undefined;
          if (sel && (sel.kind === 'sensor' || sel.kind === 'store') && o.parent?.userData.sel?.id !== sel.id) parts.push({ id: sel.id, box: new THREE.Box3().setFromObject(o) });
          if (o.userData.kind === 'domain service housing' && o.parent?.userData.kind !== o.userData.kind) housings.push(new THREE.Box3().setFromObject(o));
        });
        for (const a of parts) {
          for (const f of fixed) expect(a.box.intersectsBox(f.box), `${name} step ${i}: ${a.id} vs ${f.what}`).toBe(false);
          for (const h of housings) expect(a.box.intersectsBox(h), `${name} step ${i}: ${a.id} vs service housing`).toBe(false);
        }
      }
    }
  });
});

describe('connection contrast (M8.2: idle lines dimmed so the apparatus dominates; no line removed)', () => {
  it('a pair in a recorded event is drawn at full brightness, idle pairs below it and ordered by recorded count', async () => {
    const { connectionShade } = await import('./assemblies');
    const rec = load('m7-systems-6000');
    const lab = buildLab(rec, 'high');
    const i = 480;
    const pairs = Object.keys(rec.steps[i].conduits);
    expect(pairs.length).toBeGreaterThan(3);
    lab.apply(i, 0, { coverage: false, conduits: true, events: new Set([pairs[0]]) });
    let lines: THREE.LineSegments | null = null;
    lab.root.traverse((o) => { if (o.userData.kind === 'runtime connections (recorded)' && (o as THREE.LineSegments).isLineSegments) lines = o as THREE.LineSegments; });
    const geo = lines!.geometry;
    const col = geo.attributes.color.array as Float32Array;
    const n = geo.drawRange.count;
    let bright = 0;
    for (let v = 0; v < n; v++) if (col[v * 3] === 1) bright++;
    expect(bright).toBeGreaterThan(0);
    expect(bright).toBeLessThan(n);  // only the event's pair
    expect(lines!.userData.pairs).toBe(pairs.length);  // every recorded connection is still drawn
    for (let k = 1; k < 30; k++) expect(connectionShade(k)).toBeGreaterThanOrEqual(connectionShade(k - 1));
    expect(connectionShade(1000)).toBeLessThan(1);
  });
});

describe('system B receiver points at its recorded remote sensors (M8.2)', () => {
  it('one pickup arm per configured remote sensor, each aimed at that sensor within 1°', () => {
    const rec = load('m7-systems-6000');
    const spec = (rec.config as { systems: { sid: string; sensors?: string[] }[] }).systems.find((x) => x.sid === 'B')!;
    const lab = buildLab(rec, 'high');
    lab.apply(480, 0, { coverage: false, conduits: false, events: new Set() });
    lab.root.updateMatrixWorld(true);
    let hub: THREE.Object3D | null = null;
    const pods: THREE.Vector3[] = [];
    lab.root.traverse((o) => {
      const sel = o.userData.sel as { kind: string; id: string } | undefined;
      if (!sel || o.parent?.userData.sel?.id === sel.id) return;
      if (sel.id === 'B:head') hub = o;
      if (sel.id.startsWith('B:sensor:')) pods.push(o.getWorldPosition(new THREE.Vector3()));
    });
    const arms = (hub!.children.find((c) => c.userData.pickups) as THREE.Group).children;
    expect(arms.length).toBe(spec.sensors!.length);
    expect(pods.length).toBe(spec.sensors!.length);
    const h = (hub as unknown as THREE.Object3D).position;
    for (const pod of pods) {
      const want = Math.atan2(pod.z - h.z, pod.x - h.x);
      const best = Math.min(...arms.map((a) => { const d = Math.abs(((-a.rotation.y - want + 3 * Math.PI) % (2 * Math.PI)) - Math.PI); return d; }));
      expect(best).toBeLessThan(Math.PI / 180);
    }
  });
});
