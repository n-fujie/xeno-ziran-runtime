import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, SESSION_GONE } from './client';
import { _reset, isGone, markGone, onGone, provesGone, SessionGoneError, sessionOf } from './sessionGone';

const SID = 'ab'.repeat(16);
const OTHER = 'cd'.repeat(16);

function respond(status: number, body: unknown) {
  return Promise.resolve(new Response(typeof body === 'string' ? body : JSON.stringify(body),
    { status, headers: { 'content-type': typeof body === 'string' ? 'text/plain' : 'application/json' } }));
}

describe('definitive loss vs transient failure', () => {
  it('only a 404 "no such session" on a session route proves the session is gone', () => {
    expect(sessionOf(`/api/sessions/${SID}/tile?x0=1`)).toBe(SID);
    expect(sessionOf('/api/sessions')).toBeNull();
    expect(provesGone(`/api/sessions/${SID}/metrics`, 404, 'no such session')).toBe(true);
    expect(provesGone(`/api/sessions/${SID}/node/9`, 404, 'no configuration 9')).toBe(false);  // another 404
    for (const status of [0, 500, 502, 503, 504]) expect(provesGone(`/api/sessions/${SID}`, status, 'no such session')).toBe(false);
    expect(provesGone('/api/jobs/x', 404, 'no such session')).toBe(false);
  });
});

describe('API client', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  beforeEach(() => { _reset(); fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock); });
  afterEach(() => { vi.unstubAllGlobals(); _reset(); });

  it('marks a session gone once, then never requests it again (REST and tiles)', async () => {
    const seen: string[] = [];
    onGone((s) => seen.push(s));
    fetchMock.mockImplementation(() => respond(404, { detail: 'no such session' }));
    await expect(api.metrics(SID)).rejects.toMatchObject({ status: 404, message: SESSION_GONE });
    expect(isGone(SID)).toBe(true);
    expect(seen).toEqual([SID]);
    const calls = fetchMock.mock.calls.length;
    await expect(api.metrics(SID)).rejects.toBeInstanceOf(SessionGoneError);
    await expect(api.tile(SID, 'network', 4, [0, 0, 1, 1])).rejects.toBeInstanceOf(SessionGoneError);
    await expect(api.clusters(SID, 1)).rejects.toBeInstanceOf(SessionGoneError);
    expect(fetchMock.mock.calls.length).toBe(calls);  // no network request for the gone session
    fetchMock.mockImplementation(() => respond(200, { level: 1 }));
    await expect(api.clusters(OTHER, 1)).resolves.toEqual({ level: 1 });  // other sessions are unaffected
    markGone(SID);
    expect(seen).toEqual([SID]);  // told once
  });

  it('a tile 404 for a missing session is definitive too', async () => {
    fetchMock.mockImplementation(() => respond(404, { detail: 'no such session' }));
    await expect(api.tile(SID, 'network', 4, [0, 0, 1, 1])).rejects.toBeInstanceOf(ApiError);
    expect(isGone(SID)).toBe(true);
  });

  it('transient failures do not mark a session gone', async () => {
    fetchMock.mockImplementationOnce(() => respond(502, '<html>Bad Gateway</html>'))
      .mockImplementationOnce(() => Promise.reject(new TypeError('Failed to fetch')))
      .mockImplementationOnce(() => respond(503, { detail: 'busy' }));
    await expect(api.info(SID)).rejects.toMatchObject({ status: 502 });
    await expect(api.info(SID)).rejects.toThrow('Failed to fetch');
    await expect(api.info(SID)).rejects.toMatchObject({ status: 503 });
    expect(isGone(SID)).toBe(false);
  });
});
