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

  it('rejects anything that is not a laboratory record', () => {
    expect(() => validate({ schema: 'other', steps: [] })).toThrow();
  });
});
