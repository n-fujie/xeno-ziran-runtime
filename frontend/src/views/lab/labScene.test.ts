import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { frameAt, HIGHLIGHT_STEPS, validate } from './labScene';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..');
const rec = validate(JSON.parse(readFileSync(join(root, 'backend/experiments/results/lab/m2-run-9100.json'), 'utf8')));

describe('every drawn quantity is a recorded runtime-derived value', () => {
  it('shutters, cores and conduits equal the recorded apparatus state at every step', () => {
    rec.steps.forEach((s, i) => {
      const f = frameAt(rec, i);
      expect(f.t).toBe(s.t);
      f.chambers.forEach((c, k) => {
        expect(c.shutterClosure).toBeCloseTo(1 - s.shutter[k], 12);
        expect(c.coreGlow).toBeCloseTo(Math.min(1, s.activity[k]), 12);
        expect(c.coreScale).toBeCloseTo(Math.min(1.6, 0.45 + s.memory[k]), 12);
      });
      for (const c of f.conduits) expect(c.count).toBe(s.conduits[`${c.a}|${c.b}`] ?? 0);
    });
  });

  it('a highlight exists only within HIGHLIGHT_STEPS after a recorded event of that chamber or conduit', () => {
    rec.steps.forEach((_, i) => {
      const f = frameAt(rec, i);
      for (const c of f.chambers) {
        if (!c.highlight) continue;
        expect(c.highlight.chamber).toBe(c.cid);
        expect(f.t - c.highlight.t).toBeLessThan(HIGHLIGHT_STEPS);
        expect(rec.events).toContain(c.highlight);
      }
      for (const c of f.conduits) if (c.highlight) expect(c.highlight.pair).toBe(`${c.a}|${c.b}`);
    });
  });

  it('every recorded event carries a runtime cause', () => {
    expect(rec.events.length).toBeGreaterThan(0);
    for (const e of rec.events) expect(e.cause.length).toBeGreaterThan(0);
  });

  it('physical bodies are drawn at their recorded physical positions', () => {
    const phys = validate(JSON.parse(readFileSync(join(root, 'backend/experiments/results/lab/m3-physical-9100.json'), 'utf8')));
    expect(phys.layout).toBeTruthy();
    phys.steps.forEach((s, i) => {
      const f = frameAt(phys, i);
      for (const smp of f.samples) {
        const p = s.physics!.samples[smp.sid];
        expect(smp.position).toEqual([p[0], p[2] + 0.25, p[1]]);
      }
      for (const g of f.gantries) expect(g.tip[1]).toBeCloseTo(s.physics!.gantries[g.bay].tip[2] + 0.25, 12);
    });
  });

  it('rejects anything that is not a laboratory record', () => {
    expect(() => validate({ schema: 'other', steps: [] })).toThrow();
  });
});

describe('scientific systems are drawn from the recorded science state', () => {
  it('coverage, sensor, pending experiment and isolation equal the recorded values', () => {
    const steps = [{ ...rec.steps[0], science: { A: { sensor: '0.0', window: 8, budget: 23, coverage: ['0.0', '0.1'], features: [],
      pending: ['0.0', '0.1'] as [string, string], isolated: [], memory: 0 } } }];
    const r = { ...rec, schema: 'xzr.labrun/2', steps, config: { ...rec.config, systems: [{ sid: 'A', kind: 'local', home: '0.0' }] },
      science_events: [{ t: steps[0].t, type: 'experiment_selected', system: 'A' }] };
    const f = frameAt(validate(r), 0);
    expect(f.systems).toEqual([{ ...steps[0].science.A, sid: 'A', kind: 'local', store: null }]);
    expect(f.scienceEvents.length).toBe(1);
  });

  it('the published schema-2 record (M7 ALL, seed 6000) validates and draws every system from its recorded state', () => {
    const v2 = validate(JSON.parse(readFileSync(join(root, 'backend/experiments/results/lab/m7-systems-6000.json'), 'utf8')));
    expect(v2.schema).toBe('xzr.labrun/2');
    const last = v2.steps.length - 1;
    const f = frameAt(v2, last);
    expect(f.systems.map((x) => x.sid)).toEqual(['A', 'B', 'C']);
    f.systems.forEach((x) => expect(x.coverage).toEqual(v2.steps[last].science![x.sid].coverage));
    expect(f.scienceEvents.length).toBeGreaterThan(0);
  });
});
