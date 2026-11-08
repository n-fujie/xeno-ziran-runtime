import { describe, expect, it } from 'vitest';
import type { BodyInfo, Frame, ObsDelta, XbRecord } from '../../api/xbtro';
import { FrameBuffer, ObservationStore, chain, compareRecords, comFromAngles, fmt, obsComSeries, observedPose } from './logic';

const info = {
  links: [
    { id: 'shank', label: 's', region: 'shank', length: 0.5, mass: 10, com_frac: 0.5 },
    { id: 'thigh', label: 't', region: 'thigh', length: 0.5, mass: 10, com_frac: 0.5 },
  ],
  joints: [{ id: 'ankle', label: 'a', tau_max: 1, q_range: 1 }, { id: 'knee', label: 'k', tau_max: 1, q_range: 1 }],
} as unknown as BodyInfo;

const frame = (t: number): Frame => ({ t, reference: { com: [t] } as unknown as Frame['reference'], estimates: { controller: { com: [0], com_velocity: [0], reference_it_works_towards: [0] } } });
const delta = (kind: string, channels: string[], t: number[], at: number[], x: (number | null)[][]): ObsDelta =>
  ({ kind, channels, t, available_at: at, x: [x], sample_hz: 50, spatial: 'joint', retired_from_t: null, label: 'observation' });

describe('FrameBuffer', () => {
  it('keeps the last seconds only', () => {
    const b = new FrameBuffer(1);
    b.push([0, 0.5, 1, 1.5, 2].map(frame));
    expect(b.frames.map((f) => f.t)).toEqual([1, 1.5, 2]);
    expect(b.series((f) => f.reference.com[0]).v).toEqual([1, 1.5, 2]);
  });
});

describe('what an observation shows of the body', () => {
  it('draws nothing when no posture model has delivered a value', () => {
    expect(observedPose(info, new ObservationStore(), 1).source).toBe('none');
  });
  it('respects the delay: a sample is shown only once it is available', () => {
    const o = new ObservationStore();
    o.push({ posture: delta('posture', ['q:ankle', 'q:knee'], [1.0], [1.04], [[0.1, 0.2]]) });
    expect(observedPose(info, o, 1.02).source).toBe('none');
    const p = observedPose(info, o, 1.05);
    expect(p.source).toBe('joint');
    expect(p.angles[0]).toBeCloseTo(0.1);
    expect(p.angles[1]).toBeCloseTo(0.3);       // joint angles accumulate along the chain
  });
  it('a missing joint hides every segment above it', () => {
    const o = new ObservationStore();
    o.push({ posture: delta('posture', ['q:ankle', 'q:knee'], [1], [1], [[0.1, null]]) });
    const p = observedPose(info, o, 2);
    expect(p.angles[0]).toBeCloseTo(0.1);
    expect(p.angles[1]).toBeNull();
    expect(chain(info, p.angles).known).toEqual([true, false]);
    expect(comFromAngles(info, p.angles)).toBeNull();      // no estimate is made from partial information
  });
  it('a dropped sample is never filled in from the reference', () => {
    const o = new ObservationStore();
    o.push({ posture: delta('posture', ['q:ankle', 'q:knee'], [1, 1.02], [1, 1.02], [[0.1, 0.1], [null, null]]) });
    const p = observedPose(info, o, 1.03);
    expect(p.angles[0]).toBeCloseTo(0.1);        // the last value that exists is held ...
    expect(p.age).toBeCloseTo(0.03);             // ... and its age is reported, so the display can show that it is stale
  });
  it('a retired model stops contributing', () => {
    const o = new ObservationStore();
    o.push({ posture: { ...delta('posture', ['q:ankle', 'q:knee'], [1], [1], [[0.1, 0.1]]), retired_from_t: 1.5 } });
    expect(observedPose(info, o, 1.2).source).toBe('joint');
    expect(observedPose(info, o, 2).source).toBe('none');
  });
});

describe('kinematics', () => {
  it('upright chain and COM', () => {
    const c = chain(info, [0, 0]);
    expect(c.points[2].y).toBeCloseTo(1);
    expect(comFromAngles(info, [0, 0])).toBeCloseTo(0);
    // leaning both segments by 0.1 rad moves the COM forward by sin(0.1) times the mass-weighted lever
    expect(comFromAngles(info, [0.1, 0.1])!).toBeCloseTo((10 * 0.25 * Math.sin(0.1) + 10 * (0.5 + 0.25) * Math.sin(0.1)) / 20, 6);
  });
});

describe('before / after comparison of two records', () => {
  const rec = (v: number): XbRecord => ({ results: { tables: [{ name: 't', title: 'T', columns: ['condition', 'mean', 'p'], rows: [['a', v, 0.1], ['b', 2, 0.2]] }] } } as unknown as XbRecord);
  it('matches rows on their text columns and differences the numbers', () => {
    const d = compareRecords(rec(1), rec(3));
    expect(d).toHaveLength(1);
    expect(d[0].rows[0].cells[0]).toEqual({ column: 'mean', a: 1, b: 3, delta: 2 });
    expect(d[0].rows[1].cells[0].delta).toBe(0);
  });
  it('skips tables whose columns differ', () => {
    const b = rec(3);
    b.results.tables[0].columns = ['condition', 'other', 'p'];
    expect(compareRecords(rec(1), b)).toEqual([]);
  });
});

describe('fmt', () => {
  it('formats without hiding that a value is missing', () => {
    expect(fmt(null)).toBe('—');
    expect(fmt(NaN)).toBe('—');
    expect(fmt(0)).toBe('0');
    expect(fmt(true)).toBe('yes');
    expect(fmt(0.123456)).toBe('0.123');
  });
});

describe('COM computed from observations only', () => {
  it('gives a point only where the whole chain is observed, at the time the sample arrived', () => {
    const o = new ObservationStore();
    o.push({ posture: delta('posture', ['q:ankle', 'q:knee'], [1, 2, 3], [1.1, 2.1, 3.1], [[0.1, 0.0], [0.1, null], [0.2, 0.0]]) });
    const s = obsComSeries(info, o, 0);
    expect(s.t).toEqual([1.1, 3.1]);              // the middle sample misses the knee: no estimate is made from it
    expect(s.v[1]).toBeGreaterThan(s.v[0]);
  });
});
