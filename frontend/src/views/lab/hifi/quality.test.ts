import { describe, expect, it } from 'vitest';
import { BALANCED_PIXELS, pixelRatioFor } from './HiFiLab';

describe('drawing-buffer pixel ratio per quality level (M8.2 high-DPI investigation)', () => {
  it('DPR-1 displays are unchanged at every level', () => {
    for (const [w, h] of [[800, 723], [1520, 914]]) {
      expect(pixelRatioFor('performance', w, h, 1)).toBe(1);
      expect(pixelRatioFor('balanced', w, h, 1)).toBe(1);
      expect(pixelRatioFor('high', w, h, 1)).toBe(1);
    }
  });
  it('balanced keeps 1.5 on small canvases and stays within its pixel budget on large DPR-2 canvases, never below 1', () => {
    expect(pixelRatioFor('balanced', 800, 723, 2)).toBe(1.5);
    const r = pixelRatioFor('balanced', 1520, 914, 2);
    expect(r).toBeGreaterThanOrEqual(1);
    expect(r).toBeLessThan(1.5);
    expect(1520 * 914 * r * r).toBeLessThanOrEqual(BALANCED_PIXELS + 1);
    expect(pixelRatioFor('balanced', 4000, 3000, 2)).toBe(1);
  });
  it('high keeps the full ratio up to 2 (its DPR-2 cost is a documented limit)', () => {
    expect(pixelRatioFor('high', 1520, 914, 2)).toBe(2);
    expect(pixelRatioFor('high', 800, 723, 3)).toBe(2);
  });
});
