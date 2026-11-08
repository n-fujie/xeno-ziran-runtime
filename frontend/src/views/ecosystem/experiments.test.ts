// XENOSCIENCE ECOSYSTEM — the registry of experiments says only what the repository has. These tests keep it from claiming more.
import { describe, expect, it } from 'vitest';
import { EXPERIMENTS, MODE_TEXT, SCENE_TEXT, experimentById, seriesEvidence } from './experiments';

describe('the experiment registry', () => {
  it('has unique ids and a text for every mode and scene', () => {
    expect(new Set(EXPERIMENTS.map((e) => e.id)).size).toBe(EXPERIMENTS.length);
    for (const e of EXPERIMENTS) { expect(MODE_TEXT[e.mode]).toBeTruthy(); expect(SCENE_TEXT[e.scene]).toBeTruthy(); }
  });
  it('uses the four modes, each at least once, and no other', () => {
    expect([...new Set(EXPERIMENTS.map((e) => e.mode))].sort()).toEqual(['FIXTURE', 'LIVE_ENGINE', 'UNSUPPORTED', 'VERIFIED_REPLAY']);
  });
  it('draws only MEOS experiments in this scene, and the coupling cut has every capability', () => {
    const inScene = EXPERIMENTS.filter((e) => e.scene === 'IN_SCENE').map((e) => e.id);
    expect(inScene).toEqual(['meos-coupling', 'meos-observation', 'meos-history', 'meos-series', 'meos-replay']);
    expect(Object.values(experimentById('meos-coupling')!.capabilities).every(Boolean)).toBe(true);
    expect(experimentById('meos-observation')!.capabilities.intervene).toBe(false);  // a regime is applied to a run, it is not an intervention
  });
  it('shows at least two experiment series of different kinds in the scene, each run by an engine', () => {
    const live = EXPERIMENTS.filter((e) => e.scene === 'IN_SCENE' && e.mode === 'LIVE_ENGINE');
    expect(live.length).toBeGreaterThanOrEqual(2);
    expect(new Set(live.map((e) => e.own.interventions)).size).toBe(live.length);  // each keeps its own intervention rules
  });
  it('never passes a stored result off as a live experiment: fixtures and unsupported entries run nothing', () => {
    for (const e of EXPERIMENTS.filter((x) => x.mode === 'FIXTURE' || x.mode === 'UNSUPPORTED')) expect(Object.values(e.capabilities).some(Boolean), e.id).toBe(false);
    for (const e of EXPERIMENTS) if (e.capabilities.intervene) expect(e.mode).toBe('LIVE_ENGINE');
    expect(experimentById('meos-replay')!.mode).toBe('VERIFIED_REPLAY'); expect(experimentById('meos-replay')!.capabilities.intervene).toBe(false);
  });
  it('keeps each experiment\'s own state, intervention, observation and span definitions', () => {
    for (const e of EXPERIMENTS) for (const k of ['state', 'interventions', 'observation', 'span'] as const) expect(e.own[k].length, `${e.id}.${k}`).toBeGreaterThan(3);
    expect(experimentById('xenosnn')!.own.state).toContain('membrane');
    expect(experimentById('multicluster')!.own.span).toContain('thousands of steps');
  });
  it('lists TO-C1 as unsupported with no capability, and quotes none of its results', () => {
    const t = experimentById('to-c1')!;
    expect(t.mode).toBe('UNSUPPORTED'); expect(t.scene).toBe('NONE');
    expect(Object.values(t.capabilities).some(Boolean)).toBe(false);
    expect(JSON.stringify(t)).not.toMatch(/\b(490|270|432|162|4,?374|118,?098)\b/);
    expect(t.source).toContain('ab3c32c97c7fec06b55e266e19db2515f900c503858aba3b586fe66fa93fcbf6'); expect(t.note).toContain('SOURCE MISSING');
  });
  it('does not call the XenoSNN fixture a simulation', () => {
    const x = experimentById('xenosnn')!;
    expect(x.mode).toBe('FIXTURE'); expect(x.capabilities.observe).toBe(false); expect(x.capabilities.intervene).toBe(false);
  });
  it('lists the disconnection and escalation studies as stored results drawn by another view', () => {
    for (const id of ['disconnection', 'escalation']) { const e = experimentById(id)!; expect(e.mode).toBe('FIXTURE'); expect(e.scene).toBe('ELSEWHERE'); }
  });
});

describe('what a loaded series really is', () => {
  it('is a live engine run in every case, and never a verified replay of a stored experiment', () => {
    for (const k of ['preset', 'mfs', 'controlled'] as const) { const v = seriesEvidence(k, null); expect(v.mode).toBe('LIVE_ENGINE'); expect(v.storedResultCompared).toBe(false); }
  });
  it('says that a saved MFS stores the digest of its definition, not of a run, so nothing is compared', () => {
    const t = seriesEvidence('mfs', null).text;
    expect(t).toContain('digest of its definition, not of a run'); expect(t).toContain('not a verified replay');
  });
  it('reports the engine\'s own replay check of a controlled run\'s schedule, as a replay of the schedule only', () => {
    expect(seriesEvidence('controlled', 'controlled run: the recorded schedule replays identically without the controller').text).toContain('replays identically without the controller (a replay of the schedule, not of a stored experiment)');
    expect(seriesEvidence('controlled', 'REPLAY OF THE CONTROLLED RUN DIFFERS').text).toContain('does NOT replay identically');
    expect(seriesEvidence('controlled', null).text).toContain('not reported');
  });
  it('does not call the scene a reason for a mode: the preset is not a replay although it is drawn here', () => {
    expect(seriesEvidence('preset', null).text).toContain('not a replay');
  });
});

