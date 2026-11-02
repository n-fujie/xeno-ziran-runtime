// XENOSCIENCE ECOSYSTEM — the registry of experiments says only what the repository has. These tests keep it from claiming more.
import { describe, expect, it } from 'vitest';
import { EXPERIMENTS, STATUS_TEXT, experimentById } from './experiments';

describe('the experiment registry', () => {
  it('has unique ids and a status text for every status', () => {
    expect(new Set(EXPERIMENTS.map((e) => e.id)).size).toBe(EXPERIMENTS.length);
    for (const e of EXPERIMENTS) expect(STATUS_TEXT[e.status]).toBeTruthy();
  });
  it('makes only the MEOS experiments active in the scene, and the coupling cut has every capability', () => {
    const active = EXPERIMENTS.filter((e) => e.status === 'SCENE_ACTIVE');
    expect(active.map((e) => e.id)).toEqual(['meos-coupling', 'meos-observation', 'meos-history']);
    expect(Object.values(experimentById('meos-coupling')!.capabilities).every(Boolean)).toBe(true);
    // a regime is applied to a run, it is not an intervention on the engine
    expect(experimentById('meos-observation')!.capabilities.intervene).toBe(false);
  });
  it('lists the disconnection and escalation studies as stored results, from which nothing can be run', () => {
    for (const id of ['disconnection', 'escalation']) { const e = experimentById(id)!; expect(e.status).toBe('RESULTS_ONLY'); expect(Object.values(e.capabilities).some(Boolean)).toBe(false); }
  });
  it('lets only an experiment with a live engine be intervened on', () => {
    for (const e of EXPERIMENTS) if (e.capabilities.intervene) expect(['SCENE_ACTIVE']).toContain(e.status);
    for (const e of EXPERIMENTS.filter((x) => x.status === 'RESULTS_ONLY' || x.status === 'FIXTURE_ONLY' || x.status === 'SOURCE_MISSING')) expect(e.capabilities.intervene).toBe(false);
  });
  it('lists TO-C1 as a missing source with no capability, and quotes none of its results', () => {
    const t = experimentById('to-c1')!;
    expect(t.status).toBe('SOURCE_MISSING');
    expect(Object.values(t.capabilities).some(Boolean)).toBe(false);
    expect(JSON.stringify(t)).not.toMatch(/\b(490|270|432|162|4,?374|118,?098)\b/);
    expect(t.source).toContain('ab3c32c97c7fec06b55e266e19db2515f900c503858aba3b586fe66fa93fcbf6');
  });
  it('does not call the XenoSNN fixture a simulation', () => {
    const x = experimentById('xenosnn')!;
    expect(x.status).toBe('FIXTURE_ONLY'); expect(x.capabilities.observe).toBe(false); expect(x.capabilities.intervene).toBe(false);
  });
});
