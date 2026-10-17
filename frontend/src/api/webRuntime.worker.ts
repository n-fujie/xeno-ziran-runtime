/// <reference lib="webworker" />
// The browser build's engine host: the simulator package (xzr) runs here, in a Web Worker, on Pyodide (CPython compiled
// to WebAssembly) with numpy and pydantic. It is the same Python source as the desktop runtime and the iOS app, reached
// through the same in-process interface (backend/xzr/native/bridge.py). WebAssembly has no threads, so this loop
// plays the part of the simulation thread: it calls bridge.tick() repeatedly, which steps every session for a share of
// the time slice and returns the stream items to forward to the page.
//
// Nothing here talks to a server except fetching this site's own runtime files (Pyodide, the wheels, the engine zip).

interface Init { op: 'init'; base: string; engine: string; limits: Record<string, string> }
interface Request { op: 'request'; id: number; request: string }
interface MemoryProbe { op: 'memory'; id: number }
type Inbound = Init | Request | MemoryProbe;

interface PyFn { (...args: unknown[]): unknown }
interface Pyodide {
  loadPackage(names: string[]): Promise<unknown>;
  unpackArchive(data: ArrayBuffer, format: string, options?: { extractDir?: string }): void;
  runPython(code: string, options?: { globals?: unknown }): unknown;
  globals: { set(name: string, value: unknown): void; get(name: string): unknown };
  _module?: { HEAPU8?: { byteLength: number } };
}

const ctx = self as unknown as DedicatedWorkerGlobalScope;
let pyodide: Pyodide | null = null;
let handle: PyFn | null = null;
let tick: PyFn | null = null;
const queue: Request[] = [];

const report = (phase: string, detail?: Record<string, unknown>) => ctx.postMessage({ op: 'status', phase, ...detail });

async function boot(m: Init): Promise<void> {
  report('runtime');
  const { loadPyodide } = (await import(/* @vite-ignore */ `${m.base}pyodide/pyodide.mjs`)) as {
    loadPyodide(o: { indexURL: string }): Promise<Pyodide>;
  };
  const py = await loadPyodide({ indexURL: `${m.base}pyodide/` });
  pyodide = py;
  report('packages');
  await py.loadPackage(['numpy', 'pydantic']);  // sha-256 checked by Pyodide against the lock file shipped with the runtime
  report('engine');
  const zip = await (await fetch(m.engine)).arrayBuffer();
  py.unpackArchive(zip, 'zip', { extractDir: '/engine' });
  py.globals.set('XZR_LIMITS', JSON.stringify(m.limits));
  py.runPython(`
import json, os, sys
os.environ.update(json.loads(XZR_LIMITS))
os.environ['XZR_SCENARIOS'] = '/engine/scenarios'
sys.path.insert(0, '/engine')
from xzr.native import bridge
`);
  handle = py.runPython('bridge.handle') as PyFn;
  tick = py.runPython('bridge.tick') as PyFn;
  report('ready');
}

function answer(r: Request): void {
  let reply: string;
  try {
    reply = String(handle!(r.request));
  } catch (e) {
    // an unexpected engine error: reported as a server error without internals
    reply = JSON.stringify({ status: 500, kind: 'json', body: { detail: 'internal runtime error' } });
    console.error('runtime error', e);
  }
  ctx.postMessage({ op: 'reply', id: r.id, reply });
}

function loop(): void {
  const t0 = performance.now();
  while (queue.length) answer(queue.shift()!);
  try {
    const out = String(tick!(12));
    if (out !== '[]') ctx.postMessage({ op: 'push', batch: out });
  } catch (e) {
    console.error('runtime tick error', e);
  }
  setTimeout(loop, Math.max(2, 16 - (performance.now() - t0)));
}

ctx.onmessage = (e: MessageEvent<Inbound>) => {
  const m = e.data;
  if (m.op === 'init') {
    boot(m).then(loop, (err: unknown) => report('failed', { message: String((err as Error)?.message ?? err) }));
  } else if (m.op === 'memory') {
    // size of the engine's WebAssembly memory: it only grows, so this is the high-water mark of the tab's engine heap
    ctx.postMessage({ op: 'reply', id: m.id, reply: String(pyodide?._module?.HEAPU8?.byteLength ?? 0) });
  } else if (m.op === 'request') {
    if (handle) queue.push(m);
    else ctx.postMessage({ op: 'reply', id: m.id, reply: JSON.stringify({ status: 503, kind: 'json', body: { detail: 'the runtime is not ready' } }) });
  }
};

export {};
