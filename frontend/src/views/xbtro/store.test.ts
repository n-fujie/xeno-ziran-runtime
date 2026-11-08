import { beforeEach, describe, expect, it, vi } from 'vitest';

const inspect = vi.fn(async (_w: string, _b: string, part: string) => ({
  part, region: 'x', kind: 'reference', now: { v: 1 }, t: [0.5], series: {}, lines: [], observation: { covered: false, unobserved: true, models: [] }, note: '',
}));
vi.mock('../../api/xbtro', () => ({
  xb: {
    inspect: (...a: [string, string, string]) => inspect(...a),
    closeBody: vi.fn(async () => ({ closed: 'b' })),
  },
}));

const { useXb, frames } = await import('./store');

describe('the part panel shows the paused state', () => {
  beforeEach(() => {
    inspect.mockClear();
    frames.clear();
    useXb.setState({ wid: 'w', bid: 'b', selected: 'joint:knee', inspect: null, running: true });
  });
  it('refreshes the inspector when the body is paused', async () => {
    useXb.getState().pause();
    await Promise.resolve();
    expect(inspect).toHaveBeenCalledWith('w', 'b', 'joint:knee', 5);
    expect(useXb.getState().running).toBe(false);
  });
  it('does not ask for a part when none is selected', () => {
    useXb.setState({ selected: null });
    useXb.getState().pause();
    expect(inspect).not.toHaveBeenCalled();
  });
});
