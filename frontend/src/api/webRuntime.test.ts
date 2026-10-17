// The browser build's transport (webRuntime.ts) against a fake Worker: request / reply routing, stream pushes, start-up
// failure (missing manifest, missing WebAssembly), retry after a failure, and that nothing is left pending after one.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

class FakeWorker {
  static last: FakeWorker | null = null;
  sent: { op: string; id?: number; request?: string; base?: string; engine?: string; limits?: unknown }[] = [];
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onerror: ((e: { message: string }) => void) | null = null;
  terminated = false;
  constructor() { FakeWorker.last = this; }
  postMessage(m: { op: string }) { this.sent.push(m as never); }
  terminate() { this.terminated = true; }
  emit(data: unknown) { this.onmessage?.({ data }); }
}

const manifest = { engine: 'engine-abc.zip', limits: { XZR_MAX_NODES: '10000' }, pyodide: '314.0.7', python: '3.14.2', numpy: '2.4.6', sizeBytes: 1 };

function install(fetchImpl: (url: string) => Promise<unknown>) {
  const listeners = new Map<string, ((e: Event) => void)[]>();
  const win = {
    dispatchEvent: (e: Event) => { listeners.get(e.type)?.forEach((f) => f(e)); return true; },
    addEventListener: (t: string, f: (e: Event) => void) => listeners.set(t, [...(listeners.get(t) ?? []), f]),
    __xzrNative: { push: vi.fn(), lifecycle: vi.fn() },
  };
  vi.stubGlobal('window', win);
  vi.stubGlobal('document', { hidden: false, addEventListener: vi.fn() });
  vi.stubGlobal('Worker', FakeWorker);
  vi.stubGlobal('fetch', vi.fn(fetchImpl));
  return win;
}
const ok = (body: unknown) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
const tick = () => new Promise((r) => setTimeout(r, 0));

describe('web runtime transport', () => {
  beforeEach(() => { vi.resetModules(); FakeWorker.last = null; });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('starts the worker with the manifest, waits for ready, and routes replies by id', async () => {
    install(() => ok(manifest));
    const m = await import('./webRuntime');
    const reply = m.webHandler.postMessage({ op: 'request', request: '{"method":"GET","path":"/api/health"}' });
    await tick(); await tick();
    const w = FakeWorker.last!;
    expect(w.sent[0]).toMatchObject({ op: 'init', base: '/runtime/', engine: '/runtime/engine-abc.zip', limits: manifest.limits });
    expect(m.webStatus().phase).toBe('manifest');
    w.emit({ op: 'status', phase: 'packages' });
    expect(m.webStatus().phase).toBe('packages');
    w.emit({ op: 'status', phase: 'ready' });
    await tick();
    const req = w.sent.find((x) => x.op === 'request')!;
    expect(req.request).toContain('/api/health');
    w.emit({ op: 'reply', id: req.id, reply: '{"status":200}' });
    await expect(reply).resolves.toBe('{"status":200}');
    expect(m.webStatus().phase).toBe('ready');
  });

  it('forwards stream pushes to the app and keeps replies of different requests apart', async () => {
    const win = install(() => ok(manifest));
    const m = await import('./webRuntime');
    const a = m.webHandler.postMessage({ op: 'request', request: 'A' });
    const b = m.webHandler.postMessage({ op: 'request', request: 'B' });
    await tick(); await tick();
    const w = FakeWorker.last!;
    w.emit({ op: 'status', phase: 'ready' });
    await tick();
    const [ra, rb] = w.sent.filter((x) => x.op === 'request');
    w.emit({ op: 'push', batch: '[{"stream":"st1","items":[]}]' });
    expect(win.__xzrNative.push).toHaveBeenCalledWith([{ stream: 'st1', items: [] }]);
    w.emit({ op: 'reply', id: rb.id, reply: 'for-B' });
    w.emit({ op: 'reply', id: ra.id, reply: 'for-A' });
    await expect(a).resolves.toBe('for-A');
    await expect(b).resolves.toBe('for-B');
  });

  it('reports a missing manifest, resolves nothing as success, and starts afresh on the next request', async () => {
    let up = false;
    install(() => (up ? ok(manifest) : Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) })));
    const m = await import('./webRuntime');
    await expect(m.webHandler.postMessage({ op: 'request', request: '{}' })).rejects.toThrow(/manifest/);
    expect(m.webStatus()).toMatchObject({ phase: 'failed' });
    expect(m.webStatus().message).toMatch(/HTTP 404/);
    up = true;  // the files are back: a retry needs no page reload
    const again = m.webHandler.postMessage({ op: 'request', request: '{}' });
    await tick(); await tick();
    FakeWorker.last!.emit({ op: 'status', phase: 'ready' });
    await tick();
    const req = FakeWorker.last!.sent.find((x) => x.op === 'request')!;
    FakeWorker.last!.emit({ op: 'reply', id: req.id, reply: 'second' });
    await expect(again).resolves.toBe('second');
    expect(m.webStatus().phase).toBe('ready');
  });

  it('a worker that fails to boot is terminated, reported, and its pending requests do not hang', async () => {
    install(() => ok(manifest));
    const m = await import('./webRuntime');
    const first = m.webHandler.postMessage({ op: 'request', request: '{}' });
    const settled = first.then(() => 'resolved', (e: Error) => `rejected: ${e.message}`);
    await tick(); await tick();
    const w = FakeWorker.last!;
    w.emit({ op: 'status', phase: 'failed', message: 'could not load numpy' });
    await expect(settled).resolves.toMatch(/rejected: could not load numpy/);
    expect(w.terminated).toBe(true);
    expect(m.webStatus()).toEqual({ phase: 'failed', message: 'could not load numpy' });
  });

  it('says so clearly when WebAssembly is switched off (for example Safari Lockdown Mode)', async () => {
    install(() => ok(manifest));
    vi.stubGlobal('WebAssembly', undefined);
    const m = await import('./webRuntime');
    await expect(m.webHandler.postMessage({ op: 'request', request: '{}' })).rejects.toThrow(/WebAssembly is not available/);
    expect(m.webStatus().message).toMatch(/Lockdown Mode/);
    expect(FakeWorker.last).toBeNull();  // no worker was started
  });

  it('share downloads through a Blob link and openResults opens the results site without an opener', async () => {
    install(() => ok(manifest));
    const clicks: string[] = [];
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: () => 'blob:x', revokeObjectURL: () => undefined }));
    vi.stubGlobal('document', { hidden: false, addEventListener: vi.fn(), body: { appendChild: vi.fn() },
      createElement: () => ({ click: () => clicks.push('click'), remove: vi.fn(), set href(_v: string) { /* */ }, set download(v: string) { clicks.push(v); } }) });
    const open = vi.fn();
    vi.stubGlobal('window', { ...(globalThis as { window: object }).window, open });
    const m = await import('./webRuntime');
    await m.webHandler.postMessage({ op: 'share', filename: 'session.json', mime: 'application/json', text: '{}' });
    expect(clicks).toEqual(['session.json', 'click']);
    await m.webHandler.postMessage({ op: 'openResults' });
    expect(open).toHaveBeenCalledWith('/', '_blank', 'noopener');
  });
});
