// Transport of the iOS app (VITE_NATIVE=1): the simulator runs in-process (embedded Python engine, see
// backend/xzr/native/bridge.py); the page reaches it through a WKWebView message handler instead of HTTP and a
// WebSocket. No network request is made for the simulator: requests go to `window.webkit.messageHandlers.xzr`
// (reply-capable handler), stream items arrive from Swift through `window.__xzrNative.push(...)`.
//
// Only the API surface changes; requests, response bodies and the stream's messages are those of the HTTP service.

export const NATIVE = import.meta.env.VITE_NATIVE === '1';

interface ReplyHandler { postMessage(msg: unknown): Promise<unknown> }

interface NativeReply { status: number; kind: 'json' | 'text' | 'binary'; body: unknown }

function handler(): ReplyHandler {
  const h = (window as unknown as { webkit?: { messageHandlers?: { xzr?: ReplyHandler } } }).webkit?.messageHandlers?.xzr;
  if (!h) throw new Error('The in-app runtime is not available (native bridge missing).');
  return h;
}

export function base64ToBytes(b64: string): Uint8Array<ArrayBuffer> {
  const s = atob(b64);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

/** One request to the in-process runtime. */
export async function nativeCall(method: string, path: string, body?: unknown): Promise<NativeReply> {
  const raw = await handler().postMessage({ op: 'request', request: JSON.stringify({ method, path, body: body ?? null }) });
  return JSON.parse(String(raw)) as NativeReply;
}

/** The reply as a fetch Response, so callers handle both transports the same way. */
export function toResponse(r: NativeReply): Response {
  const headers = { 'content-type': r.kind === 'json' ? 'application/json' : r.kind === 'text' ? 'text/plain' : 'application/octet-stream' };
  const payload = r.kind === 'json' ? JSON.stringify(r.body) : r.kind === 'text' ? String(r.body) : base64ToBytes(String(r.body));
  return new Response(payload, { status: r.status, headers });
}

export async function nativeFetch(path: string, init?: RequestInit): Promise<Response> {
  const body = typeof init?.body === 'string' && init.body ? JSON.parse(init.body) : undefined;
  return toResponse(await nativeCall(init?.method ?? 'GET', path, body));
}

/** Hand a file to the system (share sheet: save to Files, AirDrop, …). */
export async function nativeShare(filename: string, mime: string, text: string): Promise<void> {
  await handler().postMessage({ op: 'share', filename, mime, text });
}

/** Open the research-results site (system browser; the app itself never loads remote pages). */
export function nativeOpenResults(): void {
  void handler().postMessage({ op: 'openResults' });
}

// ------------------------------------------------------------------ stream

type Item = { b64: string } | { json: Record<string, unknown> };

const streams = new Map<string, NativeSocket>();

// Swift calls push() with the JSON of bridge.poll(): [{stream, items}], and notice() on lifecycle changes.
if (NATIVE) (window as unknown as { __xzrNative: unknown }).__xzrNative = {
  push(batch: { stream: string; items: Item[] }[]) {
    for (const { stream, items } of batch) streams.get(stream)?.deliver(items);
  },
  lifecycle(state: string, detail?: unknown) {
    window.dispatchEvent(new CustomEvent('xzr-lifecycle', { detail: { state, detail } }));
  },
};

/** The subset of WebSocket the store uses, over the native stream routes. */
export class NativeSocket {
  static readonly OPEN = 1;
  readyState = 0;
  binaryType = 'arraybuffer';
  onmessage: ((ev: { data: string | ArrayBuffer }) => void) | null = null;
  onclose: ((ev: { code: number }) => void) | null = null;
  private key: string | null = null;

  constructor(private sid: string) {
    void this.open();
  }

  private async open() {
    try {
      const r = await nativeCall('POST', `/native/stream/${this.sid}`);
      if (this.readyState === 3) {  // closed while opening
        if (r.status === 200) void nativeCall('DELETE', `/native/stream/${(r.body as { stream: string }).stream}`);
        return;
      }
      if (r.status !== 200) return this.finish(r.status === 404 ? 4404 : 1011);
      const { stream, items } = r.body as { stream: string; items: Item[] };
      this.key = stream;
      streams.set(stream, this);
      this.readyState = 1;
      this.deliver(items);
    } catch {
      this.finish(1011);
    }
  }

  deliver(items: Item[]) {
    for (const it of items) {
      if ('b64' in it) this.onmessage?.({ data: base64ToBytes(it.b64).buffer });
      else this.onmessage?.({ data: JSON.stringify(it.json) });
    }
  }

  send(data: string) {
    if (this.key) void nativeCall('POST', `/native/stream/${this.key}/message`, JSON.parse(data));
  }

  close(code = 1000) {
    if (this.key) {
      streams.delete(this.key);
      void nativeCall('DELETE', `/native/stream/${this.key}`);
      this.key = null;
    }
    this.finish(code);
  }

  private finish(code: number) {
    if (this.readyState === 3) return;
    this.readyState = 3;
    this.onclose?.({ code });
  }
}
