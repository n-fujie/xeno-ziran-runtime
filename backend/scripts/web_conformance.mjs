// Check the PUBLISHED browser runtime (site/runtime: Pyodide, wheels, engine zip) under Node, with the same files a
// visitor's browser loads. Run after backend/scripts/export_web_runtime.py:
//
//   node backend/scripts/web_conformance.mjs [--site DIR] [--write-golden]
//
// 1. the engine's conformance snapshot against the desktop golden fixture (tests/fixtures/conformance_reference.json),
//    observation numbers within 5 %. The browser build is NOT bit-identical to the desktop (WebAssembly's math library
//    rounds the last bit differently, ~1e-14 relative after 50 steps); the report states how many exact fingerprints differ.
// 2. the snapshot against this build's own golden (tests/fixtures/conformance_reference_wasm.json): exact. This is
//    the replay guarantee of the browser build and the regression guard for it (--write-golden regenerates it).
// 3. the in-process interface end to end: create a session, run and stream it with tick() (no threads), run a
//    branch comparison through the deferred job queue, save the session and load it again.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const arg = (n) => { const i = process.argv.indexOf(n); return i < 0 ? undefined : process.argv[i + 1]; };
const site = resolve(arg('--site') ?? join(root, 'site'));
const rt = join(site, 'runtime');
const manifest = JSON.parse(readFileSync(join(rt, 'manifest.json'), 'utf8'));
const desktopRef = readFileSync(join(root, 'backend/tests/fixtures/conformance_reference.json'), 'utf8');
const wasmGoldenPath = join(root, 'backend/tests/fixtures/conformance_reference_wasm.json');

const { loadPyodide } = await import(pathToFileURL(join(rt, 'pyodide/pyodide.mjs')).href);
const t0 = Date.now();
const py = await loadPyodide({ indexURL: join(rt, 'pyodide') + '/' });
await py.loadPackage(['numpy', 'pydantic']);
const zip = readFileSync(join(rt, manifest.engine));
py.unpackArchive(zip.buffer.slice(zip.byteOffset, zip.byteOffset + zip.byteLength), 'zip', { extractDir: '/engine' });
py.globals.set('XZR_LIMITS', JSON.stringify(manifest.limits));
py.runPython(`
import json, os, sys
os.environ.update(json.loads(XZR_LIMITS))
os.environ['XZR_SCENARIOS'] = '/engine/scenarios'
sys.path.insert(0, '/engine')
`);
console.log(`runtime loaded in ${Date.now() - t0} ms: Pyodide ${manifest.pyodide}, Python ${manifest.python}, numpy ${manifest.numpy}`);

let failed = 0;
const check = (ok, what) => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${what}`); if (!ok) failed++; };

// ---- 1 + 2: conformance ------------------------------------------------------------------------------------
py.globals.set('DESKTOP_REF', desktopRef);
const desk = JSON.parse(py.runPython("from xzr.native import conformance\nconformance.run_json(DESKTOP_REF, 0.05)"));
check(desk.comparison.observation_differences.length === 0,
  `observation metrics agree with the desktop golden within 5 % (${desk.comparison.observation_differences.length} differences)`);
const exact = desk.comparison.exact_differences.length;
console.log(`INFO  exact fingerprints differing from the desktop golden: ${exact} (expected: floating-point library differences, not a defect)`);
console.log(`INFO  seconds per scenario: ${JSON.stringify(desk.seconds)}`);

if (process.argv.includes('--write-golden') || !existsSync(wasmGoldenPath)) {
  writeFileSync(wasmGoldenPath, JSON.stringify(desk.snapshot, null, 1) + '\n');
  console.log(`wrote ${wasmGoldenPath}`);
} else {
  py.globals.set('WASM_REF', readFileSync(wasmGoldenPath, 'utf8'));
  const own = JSON.parse(py.runPython("conformance.run_json(WASM_REF, 0.0)"));
  check(own.comparison.exact_differences.length === 0 && own.comparison.observation_differences.length === 0,
    `identical to this build's own golden, bit for bit (${own.comparison.exact_differences.length} exact, ${own.comparison.observation_differences.length} observation differences)`);
}

// ---- 3: the in-process interface, end to end ------------------------------------------------------------------
py.runPython(`
import json
from xzr.native import bridge
def call(method, path, body=None):
    r = json.loads(bridge.handle(json.dumps({"method": method, "path": path, "body": body})))
    return r["status"], r["body"]
`);
const call = (m, p, b) => JSON.parse(py.runPython(`json.dumps(call(${JSON.stringify(m)}, ${JSON.stringify(p)}, ${JSON.stringify(b ?? null).replace(/\bnull\b/g, 'None').replace(/\btrue\b/g, 'True').replace(/\bfalse\b/g, 'False')}))`));
const [st, info] = call('POST', '/api/sessions', { sample: 'small-600' });
check(st === 200 && /^[0-9a-f]{32}$/.test(info.id), 'a session is created (no thread is started)');
const sid = info.id;
const [sst, stream] = call('POST', `/native/stream/${sid}`);
check(sst === 200, 'a stream is opened');
call('POST', `/api/sessions/${sid}/control`, { action: 'step', steps: 30 });
let items = 0;
for (let i = 0; i < 400; i++) {
  const batch = JSON.parse(py.runPython('bridge.tick(20)'));
  items += batch.reduce((n, b) => n + b.items.length, 0);
  const [, status] = call('GET', `/api/sessions/${sid}`);
  if (items > 0 && status.t >= 30) break;
}
check(items > 0, `tick() steps the session and returns stream items (${items})`);
const [cst] = call('POST', `/api/sessions/${sid}/practice/command`, { text: 'remove concept inside', auto_compare: true });
check(cst === 200, 'a practice command is accepted and queues a branch comparison');
let done = false;
for (let i = 0; i < 200 && !done; i++) {
  py.runPython('bridge.tick(20)');
  done = py.runPython("all(j['status'] in ('done','error','cancelled') for j in __import__('xzr.service.session', fromlist=['JOBS']).JOBS.values())");
}
const jobs = JSON.parse(py.runPython("json.dumps([j['status'] for j in __import__('xzr.service.session', fromlist=['JOBS']).JOBS.values()])"));
check(done && jobs.length > 0 && jobs.every((s) => s === 'done'), `the comparison runs through the deferred queue and completes (${jobs.join(',')})`);
const [vst, saved] = call('GET', `/api/sessions/${sid}/save`);
check(vst === 200 && saved.format === 'xzr-session/1', 'the session saves');
const [lst, loaded] = call('POST', '/api/sessions', { scenario: saved.scenario, applied: saved.applied });
check(lst === 200 && !!loaded.id, 'the saved scenario loads again');
// a graph without an exported hierarchy above the computed-hierarchy limit is refused up front (not a hang)
{
  py.globals.set('SC_JSON', JSON.stringify({ n: 2000 }));
  const sc = JSON.parse(py.runPython(`
from xzr.scenario.io import load_sample
d = load_sample('demo-3k').model_dump(mode='json', exclude_none=True); d['generator']['n'] = json.loads(SC_JSON)['n']
json.dumps(d)`));
  const [bst, bbody] = call('POST', '/api/sessions', { scenario: sc });
  check(bst === 422 && bbody.limit === 'max_nodes_computed_hierarchy', `an uncached 2,000-node graph is refused with the named limit (HTTP ${bst}, ${bbody.limit})`);
}

console.log(failed ? `\n${failed} check(s) FAILED` : '\nall checks passed');
process.exit(failed ? 1 : 0);
