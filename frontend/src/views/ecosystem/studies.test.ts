import { describe, expect, it } from 'vitest';
import { fmt, groupBy, necessityGrid, regionRuns, stat } from './studies';

describe('study table helpers', () => {
  it('formats statistics and missing values without inventing numbers', () => {
    expect(stat({ mean: 47, std: 0 })).toBe('47.00±0.00');
    expect(stat({ mean: null, std: null })).toBe('-');
    expect(stat(undefined)).toBe('-');
    expect(fmt(null)).toBe('-');
    expect(fmt(0.123456, 3)).toBe('0.123');
  });
  it('groups in first-seen order', () => {
    const g = groupBy([{ k: 'b', v: 1 }, { k: 'a', v: 2 }, { k: 'b', v: 3 }], (x) => x.k);
    expect(Object.keys(g)).toEqual(['b', 'a']);
    expect(g.b.map((x) => x.v)).toEqual([1, 3]);
  });
  it('lays out the history-necessity map and counts every class, including a reversed one', () => {
    const g = necessityGrid({
      axes: { charge: [0.4, 0.5], capacity: [12, 24] },
      cells: [
        { charge: 0.4, capacity: 12, class: 'history necessary' }, { charge: 0.4, capacity: 24, class: 'history reversed (persists only without)' },
        { charge: 0.5, capacity: 12, class: 'persists without history' }, { charge: 0.5, capacity: 24, class: 'collapses either way' },
      ],
    });
    expect(g.rows.map((r) => r.cells.map((c) => c.code))).toEqual([['H', 'R'], ['P', 'X']]);
    expect(Object.values(g.counts).reduce((a, b) => a + b, 0)).toBe(4);
  });
  it('shows a non-monotone recovery response as separate runs of the same region', () => {
    const runs = regionRuns({ rows: [{ amount: 0, region: 'no' }, { amount: 1, region: 'rec' }, { amount: 2, region: 'no' }, { amount: 3, region: 'rec' }] });
    expect(runs).toHaveLength(4);
    expect(regionRuns({ rows: [{ amount: 0, region: 'a' }, { amount: 1, region: 'a' }] })).toEqual([{ region: 'a', amounts: [0, 1] }]);
  });
});
