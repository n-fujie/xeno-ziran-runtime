// How the browser runtime scales with scenario size, measured in the PUBLISHED runtime under Node (V8's WebAssembly):
//   node backend/scripts/web_scaling.mjs [--site DIR] [--sizes 1000,3000,5000,...] [--timeout 240]
// For each size a fresh process builds the demo scenario scaled to n configurations (session creation = world build +
// hierarchy), runs 40 session steps and a 50-step branch comparison, and reports seconds, steps/s and memory. A size that
// does not finish within the timeout is reported as such (never as success). This is CLI Pyodide, not a browser.
// --synthetic-hierarchy replaces the hierarchy by a placeholder (contiguous blocks) so the ENGINE's cost at sizes whose real
// hierarchy cannot be computed here (> 1,500 nodes without an exported reference) can still be timed: step speed, comparison
// time and memory only; the placeholder is not a valid address hierarchy and no scientific result is taken from such a run.
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const arg = (n) => { const i = process.argv.indexOf(n); return i < 0 ? undefined : process.argv[i + 1]; };
const site = resolve(arg('--site') ?? join(root, 'site'));

if (process.argv.includes('--child')) {
  const n = Number(arg('--n'));
  const rt = join(site, 'runtime');
  const manifest = JSON.parse(readFileSync(join(rt, 'manifest.json'), 'utf8'));
  const { loadPyodide } = await import(pathToFileURL(join(rt, 'pyodide/pyodide.mjs')).href);
  const py = await loadPyodide({ indexURL: join(rt, 'pyodide') + '/' });
  await py.loadPackage(['numpy', 'pydantic']);
  const zip = readFileSync(join(rt, manifest.engine));
  py.unpackArchive(zip.buffer.slice(zip.byteOffset, zip.byteOffset + zip.byteLength), 'zip', { extractDir: '/engine' });
  py.globals.set('N', n);
  py.globals.set('SYNTH', process.argv.includes('--synthetic-hierarchy'));
  const out = py.runPython(`
import json, os, sys, time
os.environ['XZR_SCENARIOS'] = '/engine/scenarios'; os.environ['XZR_MAX_NODES'] = '100000'; os.environ['XZR_MAX_EDGES'] = '2000000'
sys.path.insert(0, '/engine')
from xzr.scenario.io import load_sample
from xzr.service.session import Session, JOBS, run_deferred
sc = load_sample('demo-3k')
d = sc.model_dump(mode='json', exclude_none=True); d['generator']['n'] = int(N)
from xzr.scenario.model import Scenario
sc = Scenario.model_validate(d)
if SYNTH:
    import numpy as np
    from xzr.lod import hierarchy as H
    from xzr.scenario import build as B
    def fake(a):
        m = a.shape[0]
        return H.hierarchy_from((np.arange(m) * (1 << H.DEPTH)) // m, np.arange(m), source='placeholder (timing only)')
    B.build_hierarchy = fake
t0 = time.perf_counter(); s = Session(sc); build = time.perf_counter() - t0
t0 = time.perf_counter()
with s.lock:
    for _ in range(40): s._step_locked()
steps = 40 / (time.perf_counter() - t0)
t0 = time.perf_counter()
s.command('remove concept human', auto_compare=False)
jid = s.start_compare(50)
while JOBS[jid]['status'] not in ('done', 'error', 'cancelled'): run_deferred(1.0)
cmp = time.perf_counter() - t0
json.dumps({'n': int(N), 'edges': int(s.engine.state.n_edges) if hasattr(s.engine.state, 'n_edges') else None, 'build_s': round(build, 2), 'session_steps_per_s': round(steps, 1), 'compare_50_s': round(cmp, 2), 'job': JOBS[jid]['status']})
`);
  console.log(out);
  const m = process.memoryUsage();
  console.error(`rss_mb=${(m.rss / 1048576).toFixed(0)}`);
  process.exit(0);
}

const sizes = (arg('--sizes') ?? '1000,3000,4000,5000,6000,8000,10000').split(',').map(Number);
const timeout = Number(arg('--timeout') ?? 240) * 1000;
const rows = [];
for (const n of sizes) {
  const t0 = Date.now();
  const r = spawnSync(process.execPath, [fileURLToPath(import.meta.url), '--child', '--n', String(n), '--site', site, ...(process.argv.includes('--synthetic-hierarchy') ? ['--synthetic-hierarchy'] : [])], { encoding: 'utf8', timeout });
  const wall = ((Date.now() - t0) / 1000).toFixed(1);
  if (r.error || r.status !== 0) { rows.push({ n, finished: false, wall_s: Number(wall), reason: r.error?.code === 'ETIMEDOUT' ? `no result within ${timeout / 1000} s` : `exit ${r.status}: ${(r.stderr || '').slice(-200)}` }); }
  else {
    const line = r.stdout.split('\n').find((l) => l.startsWith('{'));
    rows.push({ ...JSON.parse(line), finished: true, wall_s: Number(wall), rss_mb: Number((r.stderr.match(/rss_mb=(\d+)/) ?? [])[1]) });
  }
  console.log(JSON.stringify(rows.at(-1)));
}
console.log(JSON.stringify({ node: process.version, platform: process.platform, rows }, null, 1));
