// XENO ECOSYSTEM — the research-device mapping: what the structure shows is a function of (record, tick, observation), against a real engine record of
// the second stage (see backend/scripts/make_meos_fixture.py): collapse at 149, recovery at 161, a pulse at 151, an Address Domain fault 200-225, and
// Philosophical operations in revision mode.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { buildMegastructure } from './megastructure';
import { FULL_OBSERVATION, type MeosRecord } from './meosApi';
import { buildDeviceLayer, deviceState, observationCoverage, SPACES } from './researchDevice';

const dir = join(dirname(fileURLToPath(import.meta.url)), '__fixtures__');
const rec2 = JSON.parse(readFileSync(join(dir, 'meos-stage2.json'), 'utf8')) as MeosRecord;
const rec1 = JSON.parse(readFileSync(join(dir, 'meos-a2-removed.json'), 'utf8')) as MeosRecord;

describe('the stage-two record', () => {
  it('is a real engine record that collapses, recovers and collapses again', () => {
    expect(rec2.engine).toBe('meos-0.2');
    expect(rec2.status_log.filter((s) => s.label === 'COLLAPSED').map((s) => s.tick)).toEqual([149, 234]);
    expect(rec2.status_log.some((s) => s.tick === 161 && s.label === 'ACTIVE')).toBe(true);
    expect(rec2.traces?.phil_boost).toHaveLength(rec2.frames.length);
    expect(rec2.trace_digest).toMatch(/^[0-9a-f]{64}$/);
  });
});

describe('deviceState', () => {
  it('reads the recovery phase from the status log, not from a label', () => {
    expect(deviceState(rec2, 50, null).recovery.phase).toBe('none');
    expect(deviceState(rec2, 150, null).recovery.phase).toBe('collapsed');
    const r = deviceState(rec2, 170, null).recovery;
    expect(r.phase).toBe('recovered');
    expect(r.since).toBe(161);
    expect(r.recoveries).toBe(1);
    expect(deviceState(rec2, 250, null).recovery.phase).toBe('collapsed');
  });
  it('shows a resource pulse only for a few ticks after its injection', () => {
    expect(deviceState(rec2, 150, null).pulse.active).toBe(false);
    const p = deviceState(rec2, 155, null).pulse;
    expect(p).toMatchObject({ active: true, age: 4, x: 3, y: 6, amount: 2 });
    expect(deviceState(rec2, 170, null).pulse.active).toBe(false);
  });
  it('opens the boundary per cut channel and closes it again when the channel returns', () => {
    expect(deviceState(rec2, 90, null).boundary.closed).toBe(true);
    const cut = deviceState(rec2, 120, null).boundary;
    expect(cut.closed).toBe(false);
    expect(cut.open.length).toBeGreaterThan(0);
    expect(deviceState(rec2, 160, null).boundary.closed).toBe(true);
  });
  it('has a philosophical module only where a philosophical mode is configured, and counts what the traces recorded', () => {
    const on = deviceState(rec2, 255, null).phil;
    expect(on.enabled).toBe(true);
    expect(on.mode).toBe('revision');
    expect(on.expressions).toBe(rec2.traces!.phil_expressions[255]);
    expect(on.expressionAge === null || on.expressionAge >= 0).toBe(true);
    const off = deviceState(rec1, 100, null).phil;
    expect(off.enabled).toBe(false);
    expect(off.expressionAge).toBeNull();
    expect(off.boost).toBe(1);
  });
  it('maps an observation to an aim, a coverage and a sampling tick', () => {
    expect(deviceState(rec2, 7, FULL_OBSERVATION).array).toMatchObject({ sampling: true, coverage: 1, activeDishes: 12 });
    const coarse = deviceState(rec2, 7, { ...FULL_OBSERVATION, sampling_interval: 4, spatial_stride: 2, region: [0, 0, 6, 13] });
    expect(coarse.array.sampling).toBe(false);
    expect(coarse.array.aim).toEqual([3, 6.5]);
    expect(coarse.array.coverage).toBeCloseTo(0.5 / 4, 6);
    expect(coarse.array.activeDishes).toBe(Math.max(1, Math.round(12 * coarse.array.coverage)));
    expect(deviceState(rec2, 8, { ...FULL_OBSERVATION, sampling_interval: 4 }).array.sampling).toBe(true);
  });
  it('is pure: the same inputs give the same state, and the record is not changed', () => {
    const before = JSON.stringify(rec2.status_log);
    expect(deviceState(rec2, 170, null)).toEqual(deviceState(rec2, 170, null));
    expect(JSON.stringify(rec2.status_log)).toBe(before);
  });
  it('reads a stage-one record (no traces, no phil block) without error', () => {
    for (const t of [0, 70, rec1.frames.length - 1]) expect(() => deviceState(rec1, t, null)).not.toThrow();
    expect(deviceState(rec1, 140, null).recovery.phase).toBe('collapsed');
  });
});

describe('observationCoverage', () => {
  it('is the product of the region and the spatial lattice, bounded by 0..1', () => {
    expect(observationCoverage(FULL_OBSERVATION, 14)).toBe(1);
    expect(observationCoverage({ ...FULL_OBSERVATION, spatial_stride: 3 }, 14)).toBeCloseTo(1 / 9, 6);
    expect(observationCoverage({ ...FULL_OBSERVATION, region: [20, 20, 30, 30] }, 14)).toBe(0);
    expect(observationCoverage({ ...FULL_OBSERVATION, region: [0, 0, 13, 13] }, 14)).toBe(1);
  });
});

describe('the device layer and the array without a renderer', () => {
  const mega = buildMegastructure('performance');
  const layer = buildDeviceLayer(mega.arena.group, 14);
  const opts = { arenaCell: mega.arena.local, selectedTrial: null as number | null, trialPos: mega.trials.positions, n: 14 };
  it('shows the module only for a run that configures one, and a spark only while a claim is in the channel', () => {
    layer.set(deviceState(rec1, 100, null), opts);
    expect(layer.group.children.some((c) => c.visible && c.type === 'Group')).toBe(false);
    layer.set(deviceState(rec2, 120, null), opts);
    expect(layer.group.children.some((c) => c.visible && c.type === 'Group')).toBe(true);
  });
  it('rings only a selected chamber', () => {
    layer.set(deviceState(rec2, 100, null), opts);
    const ring = (): number => layer.group.children.filter((c) => (c as THREE.Mesh).isMesh && c.visible && (c as THREE.Mesh).geometry.type === 'TorusGeometry').length;
    expect(ring()).toBe(0);
    layer.set(deviceState(rec2, 100, null), { ...opts, selectedTrial: 3 });
    expect(ring()).toBe(1);
  });
  it('turns every dish toward the observed target and darkens the dishes outside the coverage', () => {
    const target = new THREE.Vector3(-66, 1, 16);
    mega.array.aim(target, true, 4, 1);
    const grp = mega.array.group.children as THREE.Mesh[];
    const lit = grp.filter((m) => (m.material as THREE.MeshBasicMaterial).color.r > 0.3).length;
    expect(lit).toBe(4);
    expect(mega.array.count).toBe(12);
  });
  it('names the experimental function of every space of the structure', () => {
    expect(SPACES.map((s) => s.space)).toEqual(['Habitat / Arena', 'Processing Layer', 'Observation Array', 'Underground Chambers', 'Research Core', 'Boundary Layer', 'Empty Sockets']);
    for (const s of SPACES) expect(s.driven_by.length).toBeGreaterThan(3);
  });
});
