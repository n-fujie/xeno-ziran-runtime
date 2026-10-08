import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SESSION_GONE, type SessionInfo } from '../api/client';
import { _reset, markGone } from '../api/sessionGone';
import { probe, useSim } from './sim';

const SID = 'ef'.repeat(16);
const info = { id: SID } as unknown as SessionInfo;
const respond = (status: number, body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } }));

describe('store: session loss', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal('fetch', vi.fn()); });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

  it('a definitive loss closes the stream and reports it once, with the new-session state', () => {
    const close = vi.fn();
    useSim.setState({ info, ws: { close } as unknown as WebSocket, connected: true, error: null, sessionGone: false });
    markGone(SID);
    const s = useSim.getState();
    expect(close).toHaveBeenCalledWith(1000);
    expect(s.sessionGone).toBe(true);
    expect(s.connected).toBe(false);
    expect(s.error).toBe(SESSION_GONE);
  });

  it('transient failures keep it a disconnect (reconnecting notice); a 404 ends it as a loss', async () => {
    const other = 'aa'.repeat(16);
    const inf = { id: other } as unknown as SessionInfo;
    useSim.setState({ info: inf, ws: { close: vi.fn() } as unknown as WebSocket, error: null, notice: null, sessionGone: false });
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementationOnce(() => Promise.reject(new TypeError('Failed to fetch')))
      .mockImplementationOnce(() => respond(502, { detail: 'bad gateway' }))
      .mockImplementationOnce(() => respond(404, { detail: 'no such session' }));
    const done = probe(inf);
    await vi.advanceTimersByTimeAsync(1100);
    expect(useSim.getState().notice).toMatch(/reconnecting/);
    expect(useSim.getState().sessionGone).toBe(false);
    await vi.advanceTimersByTimeAsync(2100);
    expect(useSim.getState().sessionGone).toBe(false);  // still transient after a 502
    await vi.advanceTimersByTimeAsync(4100);
    await done;
    expect(useSim.getState().sessionGone).toBe(true);
    expect(useSim.getState().error).toBe(SESSION_GONE);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    _reset();
  });
});
