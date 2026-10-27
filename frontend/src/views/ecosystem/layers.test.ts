// XENO ECOSYSTEM — the overlay derivations and the record decoding, against a real engine record (A2 removed at tick 60, 150 ticks; see
// backend/scripts/make_meos_fixture.py). Nothing here draws: the layers are pure functions of the record.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
  ENTITY_NAMES, LAYERS, addressView, firingView, historyPaths, interactionGraph, meosMembership, meosView, mfsMembership, relations, sssView,
  statusSegments, trajectories, xenobodyHulls,
} from './layers';
import { adAt, decodeFields, fieldAt, type MeosRecord } from './meosApi';

const here = dirname(fileURLToPath(import.meta.url));
const rec = JSON.parse(readFileSync(join(here, '__fixtures__', 'meos-a2-removed.json'), 'utf8')) as MeosRecord;
const PARTS = {
  B1: { label: 'A1 as one operational body', components: ['A1', 'sensor_resource'] },
  B2: { label: 'A1 + sensor network', components: ['A1', 'sensor_resource', 'sensor_alteration', 'interaction_channel'] },
  B3: { label: 'A1 + A2 + loop', components: ['A1', 'A2', 'sensor_resource', 'sensor_alteration', 'interaction_channel', 'feedback', 'resource_renewal', 'history'] },
};
const last = rec.frames.length - 1;

describe('the record', () => {
  it('is a real engine record of the intended run', () => {
    expect(rec.engine).toBe('meos-0.1');
    expect(rec.interventions).toEqual([{ tick: 60, op: 'REMOVE', target: 'A2' }]);
    expect(rec.result_digest).toMatch(/^[0-9a-f]{64}$/);
    expect(rec.final_status.label).toBe('COLLAPSED');
  });
  it('lists all nine layers of the specification', () => {
    expect(LAYERS.map((l) => l.id)).toEqual(['physical', 'operational', 'mfs', 'meos', 'address', 'sss', 'history', 'firing', 'xenobody']);
  });
});

describe('MEOS status', () => {
  it('follows the explicit criteria: active while cycles are sustained, then degraded, then collapsed with the failed dependency named', () => {
    expect(meosView(rec, 40).label).toBe('ACTIVE');
    expect(meosView(rec, 40).cycles).toBeGreaterThanOrEqual(2);
    expect(meosView(rec, last).label).toBe('COLLAPSED');
    expect(meosView(rec, last).cycles).toBe(0);
    expect(meosView(rec, last).dependency?.entity).toBe('A2');
    expect(meosView(rec, last).dependency?.detail).toContain('absent');
    expect(meosView(rec, 40).dependency).toBeNull();
  });
  it('is a sequence of contiguous status segments covering every tick', () => {
    const segs = statusSegments(rec);
    expect(segs[0].from).toBe(0);
    expect(segs[segs.length - 1].to).toBe(last);
    segs.slice(1).forEach((s, i) => expect(s.from).toBe(segs[i].to + 1));
    expect(segs.map((s) => s.label)).toEqual(['DEGRADED', 'ACTIVE', 'DEGRADED', 'COLLAPSED']);
  });
  it('membership of the recursion is derived from the counted cycles, not from firing alone', () => {
    expect(meosMembership(rec, 'A1', 40)).toBe(true);
    expect(meosMembership(rec, 'A2', 40)).toBe(true);
    expect(meosMembership(rec, 'A2', last)).toBe(false);
    expect(rec.frames[70].A2.present).toBe(false); // A2 is already gone at tick 70, yet the status is still derived from the cycles of the window
    expect(meosView(rec, 70).label).toBe('ACTIVE');
    expect(meosMembership(rec, 'A1', last)).toBe(false);
  });
});

describe('operational relations, firing and history', () => {
  it('exposes the chain: alters, detected, reconfigures, fires on', () => {
    const kinds = new Set(relations(rec, 40, 14).map((r) => r.kind));
    for (const k of ['alters', 'detects', 'reconfigures', 'fires-on']) expect(kinds.has(k as never)).toBe(true);
    expect(relations(rec, last, 14).some((r) => r.kind === 'detects')).toBe(false);
  });
  it('explains a firing by its recorded preconditions and an absent configuration by its state', () => {
    const fire = rec.events.find((e) => e.kind === 'fire' && e.actor === 'A1' && e.tick > 30)!;
    const v = firingView(rec, 'A1', fire.tick);
    expect(v.state).toBe('firing');
    expect(v.checks?.every((c) => c.ok)).toBe(true);
    expect(v.consequences.length).toBeGreaterThan(0);
    const gone = firingView(rec, 'A2', last);
    expect(gone.state).toBe('absent');
  });
  it('shows history re-entry only where a threshold was lowered by the trace', () => {
    const paths = historyPaths(rec, 50, 60);
    expect(paths.length).toBeGreaterThan(0);
    expect(paths.every((p) => p.reentry > 0)).toBe(true);
    expect(historyPaths(rec, last, 20).every((p) => p.tick > last - 20)).toBe(true);
  });
  it('accumulates the interaction graph monotonically', () => {
    const a = interactionGraph(rec, 30), b = interactionGraph(rec, last);
    b.forEach((e, i) => expect(e.count).toBeGreaterThanOrEqual(a[i].count));
    expect(b.find((e) => e.label === 'alters')!.count).toBeGreaterThan(0);
  });
});

describe('Address Domain, SSS and XenoBody partitions', () => {
  it('exposes every part of an Address Domain from the record', () => {
    const ad = adAt(rec.frames, 50);
    expect(ad).not.toBeNull();
    const v = addressView(rec, 'A1', 50, ad)!;
    expect(v.spatial).toEqual({ x: rec.frames[50].A1.x, y: rec.frames[50].A1.y });
    expect(v.boundary.sensor_radius).toBe(2);
    expect(v.window).toEqual({ window: 6, persist: 3, refractory: 2 });
    expect(v.history.trace).toBe(rec.frames[50].A1.h);
    expect(Object.keys(v.connectivity)).toEqual(['sensor_resource', 'sensor_alteration', 'interaction', 'feedback']);
    expect(v.resource.power_reserve).toBe(rec.frames[50].power);
  });
  it('reads SSS in grid cells from the operating conditions', () => {
    const s = sssView(adAt(rec.frames, 50), 'A2')!;
    expect(s).toMatchObject({ scale: 1, size: 1, speed: 1, sensorCells: 2, footprintCells: 0, stepsPerTick: 1 });
  });
  it('partitions the same arrangement into different bodies and reports what lies outside the arena', () => {
    const h = xenobodyHulls(rec, 50, adAt(rec.frames, 50), PARTS);
    const by = Object.fromEntries(h.map((x) => [x.id, x]));
    expect(by.B1.includesDepot).toBe(false);
    expect(by.B3.includesDepot).toBe(true);
    expect(by.B1.points.length).toBe(1);
    expect(by.B3.points.length).toBeGreaterThan(by.B1.points.length);
    for (const r of by.B3.rects) expect(r.every((v) => v >= 0 && v < rec.fields.grid)).toBe(true);
  });
  it('mentions MFS membership only from a computed reduction', () => {
    expect(mfsMembership(null, 'A2')).toContain('not computed');
    expect(mfsMembership({ baseline_persists: true, retained: ['A2'], removed: [], operation: '' }, 'A2')).toContain('retained');
    expect(mfsMembership({ baseline_persists: true, retained: [], removed: ['A2'], operation: '' }, 'A2')).toContain('removable');
    expect(mfsMembership(null, 'A1')).toContain('not computed');
  });
});

describe('fields and trajectories', () => {
  it('decodes the recorded field stream to normalised fields consistent with the frame totals', () => {
    const f = decodeFields(rec.fields, rec.frames.length);
    expect(f.n).toBe(14);
    expect(f.R.length).toBe(rec.frames.length * 196);
    for (const t of [0, 40, last]) {
      const R = fieldAt(f, 'R', t);
      const total = Array.from(R).reduce((a, b) => a + b, 0) * f.rTop;
      expect(Math.abs(total - rec.frames[t].R) / rec.frames[t].R).toBeLessThan(0.03); // 8-bit quantisation
    }
    expect(Math.max(...fieldAt(f, 'M1', 30))).toBeGreaterThan(0);
  });
  it('builds the data-panel series from the record', () => {
    const tr = trajectories(rec);
    expect(tr.resource[0].v.length).toBe(rec.frames.length);
    expect(tr.history.map((s) => s.label)).toEqual(['h A1', 'h A2']);
    expect(ENTITY_NAMES).toEqual(['A1', 'A2']);
  });
});

describe('rendering is separate from simulation', () => {
  it('keeps the derivation modules free of any renderer or camera', () => {
    for (const f of ['layers.ts', 'meosApi.ts']) {
      const src = readFileSync(join(here, f), 'utf8');
      expect(src).not.toMatch(/from 'three'|WebGL|requestAnimationFrame|camera/i);
    }
  });
});
