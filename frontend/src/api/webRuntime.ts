// Main-thread side of the browser build's in-tab runtime (see webRuntime.worker.ts). It starts the worker on first use,
// waits until the engine is loaded, and turns the app's native-style requests into worker messages. The runtime files
// (Pyodide, wheels, the engine zip) are fetched from this site's own /runtime/ directory; nothing is sent anywhere.

export interface WebStatus { phase: 'idle' | 'manifest' | 'runtime' | 'packages' | 'engine' | 'ready' | 'failed'; message?: string }

interface Manifest {
  engine: string;
  limits: Record<string, string>;
  pyodide: string;
  python: string;
  numpy: string;
  sizeBytes: number;
}

const BASE = (import.meta.env.VITE_RUNTIME_BASE as string | undefined) ?? '/runtime/';

let status: WebStatus = { phase: 'idle' };
export const webStatus = (): WebStatus => status;
function setStatus(s: WebStatus): void {
  status = s;
  performance.mark(`xzr-web-${s.phase}`);  // start-up phases are readable from the Performance API (nothing is reported anywhere)
  window.dispatchEvent(new CustomEvent('xzr-web-status', { detail: s }));
}

let worker: Worker | null = null;
let ready: Promise<void> | null = null;
let seq = 0;
const pending = new Map<number, (reply: string) => void>();

/** After a failed start the worker is discarded, so the next request starts a fresh one (a retry needs no page reload). */
function fail(message: string): void {
  worker?.terminate();
  worker = null;
  ready = null;
  pending.forEach((resolve) => resolve(JSON.stringify({ status: 503, kind: 'json', body: { detail: 'the runtime is not available' } })));
  pending.clear();
  setStatus({ phase: 'failed', message });
}

function start(): Promise<void> {
  if (ready) return ready;
  if (typeof WebAssembly === 'undefined') {
    // some privacy modes switch WebAssembly off (for example Safari's Lockdown Mode); the engine cannot run without it
    fail('WebAssembly is not available in this browser. It is switched off in some privacy modes (for example Safari\'s '
      + 'Lockdown Mode) and in a few very old browsers. Allow it for this site, use another browser, or run the desktop runtime.');
    return Promise.reject(new Error('WebAssembly is not available'));
  }
  ready = new Promise<void>((resolve, reject) => {
    setStatus({ phase: 'manifest' });
    fetch(`${BASE}manifest.json`, { cache: 'no-cache' })
      .then((r) => { if (!r.ok) throw new Error(`runtime manifest: HTTP ${r.status}`); return r.json() as Promise<Manifest>; })
      .then((m) => {
        worker = new Worker(new URL('./webRuntime.worker.ts', import.meta.url), { type: 'module' });
        worker.onerror = (e) => { fail(e.message || 'the runtime worker stopped'); reject(new Error(e.message)); };
        worker.onmessage = (e: MessageEvent<{ op: string; phase?: string; message?: string; id?: number; reply?: string; batch?: string }>) => {
          const d = e.data;
          if (d.op === 'status') {
            if (d.phase === 'ready') { setStatus({ phase: 'ready' }); resolve(); }
            else if (d.phase === 'failed') { fail(d.message ?? 'the runtime failed to start'); reject(new Error(d.message ?? 'the runtime failed to start')); }
            else setStatus({ phase: d.phase as WebStatus['phase'] });
          } else if (d.op === 'reply' && d.id !== undefined) {
            pending.get(d.id)?.(d.reply ?? '');
            pending.delete(d.id);
          } else if (d.op === 'push' && d.batch) {
            (window as unknown as { __xzrNative?: { push(b: unknown): void } }).__xzrNative?.push(JSON.parse(d.batch));
          }
        };
        worker.postMessage({ op: 'init', base: BASE, engine: `${BASE}${m.engine}`, limits: m.limits });
      })
      .catch((err: unknown) => { fail(String((err as Error)?.message ?? err)); reject(err as Error); });
  });
  return ready;
}

function probeMemory(): Promise<string> {
  return start().then(() => new Promise<string>((resolve) => {
    const id = ++seq;
    pending.set(id, resolve);
    worker!.postMessage({ op: 'memory', id });
  }));
}

function rpc(request: string): Promise<string> {
  return start().then(() => new Promise<string>((resolve) => {
    const id = ++seq;
    pending.set(id, resolve);
    worker!.postMessage({ op: 'request', id, request });
  }));
}

// The tab hidden counts as the app leaving the foreground: running sessions pause (nothing keeps computing in a
// background tab), and the page is told which ones when it returns.
if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (!worker || status.phase !== 'ready') return;
    const hidden = document.hidden;
    void rpc(JSON.stringify({ method: 'POST', path: `/native/lifecycle/${hidden ? 'background' : 'foreground'}`, body: null })).then((raw) => {
      if (hidden) return;
      const body = (JSON.parse(raw) as { body?: { paused?: string[] } }).body;
      (window as unknown as { __xzrNative?: { lifecycle(s: string, d?: unknown): void } }).__xzrNative?.lifecycle('foreground', body);
    });
  });
}

function download(filename: string, mime: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.rel = 'noopener';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** The reply-capable handler the native transport expects (same shape as the iOS message handler). */
export const webHandler = {
  async postMessage(msg: unknown): Promise<unknown> {
    const m = msg as { op: string; request?: string; filename?: string; mime?: string; text?: string };
    if (m.op === 'request') return rpc(m.request ?? '{}');
    if (m.op === 'memory') return probeMemory();
    if (m.op === 'share') { download(m.filename ?? 'download.txt', m.mime ?? 'text/plain', m.text ?? ''); return ''; }
    if (m.op === 'openResults') { window.open('/', '_blank', 'noopener'); return ''; }
    return '';
  },
};
