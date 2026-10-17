// Verify a PUBLISHED browser runtime over HTTP: every file listed in /runtime/manifest.json is downloaded from the host and
// its sha-256 compared with the manifest; the engine zip against engineSha256; the response headers of /app/ against the
// policy. This checks what the host actually serves (compression, CDN, caching) rather than what was exported.
//
//   node backend/scripts/verify_published_runtime.mjs https://ziran-xeno-simulator.vercel.app
import { createHash } from 'node:crypto';

const base = (process.argv[2] ?? '').replace(/\/$/, '');
if (!/^https?:\/\//.test(base)) throw new Error('usage: node verify_published_runtime.mjs <site url>');
let failed = 0;
const check = (ok, what) => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${what}`); if (!ok) failed++; };
const sha = (buf) => createHash('sha256').update(Buffer.from(buf)).digest('hex');
const get = async (path) => {
  const r = await fetch(`${base}${path}`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return { r, bytes: await r.arrayBuffer() };
};

const { bytes: mb } = await get('/runtime/manifest.json');
const manifest = JSON.parse(Buffer.from(mb).toString('utf8'));
console.log(`manifest: Pyodide ${manifest.pyodide}, Python ${manifest.python}, numpy ${manifest.numpy}, ${manifest.sizeBytes} bytes, engine ${manifest.engine}`);
for (const [name, expected] of Object.entries(manifest.files)) {
  const { bytes } = await get(`/runtime/pyodide/${name}`);
  check(sha(bytes) === expected, `${name} (${bytes.byteLength} bytes) matches the manifest sha-256`);
}
const { bytes: eb, r: er } = await get(`/runtime/${manifest.engine}`);
check(sha(eb) === manifest.engineSha256, `${manifest.engine} matches engineSha256`);
check(/immutable/.test(er.headers.get('cache-control') ?? ''), `the content-addressed engine zip is cached as immutable (${er.headers.get('cache-control')})`);
const lock = JSON.parse(Buffer.from((await get('/runtime/pyodide/pyodide-lock.json')).bytes).toString('utf8'));
for (const [pkg, meta] of Object.entries(lock.packages)) {
  const { bytes } = await get(`/runtime/pyodide/${meta.file_name}`);
  check(sha(bytes) === meta.sha256, `lock entry ${pkg}: served wheel matches the sha-256 in the lock file`);
}
const app = await fetch(`${base}/app/`, { cache: 'no-store' });
const csp = app.headers.get('content-security-policy') ?? '';
check(app.ok, '/app/ is served (HTTP 200)');
check(/default-src 'self'/.test(csp) && /connect-src 'self'/.test(csp) && /'wasm-unsafe-eval'/.test(csp) && !/unsafe-eval'(?!\s*)/.test(csp.replace(/'wasm-unsafe-eval'/g, '')), '/app/ sends the Content-Security-Policy (same-origin only; wasm-unsafe-eval, no eval)');
check(app.headers.get('x-content-type-options') === 'nosniff', '/app/ sends X-Content-Type-Options: nosniff');
const wasm = await fetch(`${base}/runtime/pyodide/pyodide.asm.wasm`, { method: 'HEAD' });
check((wasm.headers.get('content-type') ?? '').startsWith('application/wasm'), `the WebAssembly file is served as application/wasm (${wasm.headers.get('content-type')})`);
const redirect = await fetch(`${base}/app`, { redirect: 'manual' });
check(redirect.status === 308 && /\/app\/$/.test(redirect.headers.get('location') ?? ''), '/app redirects to /app/');
console.log(failed ? `\n${failed} check(s) FAILED` : '\nall checks passed');
process.exit(failed ? 1 : 0);
