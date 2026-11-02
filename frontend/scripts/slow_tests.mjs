// Observe how long the frontend tests take, and how that depends on the machine's load. Runs the whole suite once, then appends one line to docs/ecosystem/test_timing.jsonl:
// the date, the load average before and after, the total, and the ten slowest tests with their durations. Nothing here changes a limit or a test; the point is to see a test's time
// creep up (alone, with the machine idle) or swing with load, instead of finding out from one failed run. Usage: node scripts/slow_tests.mjs [label]
import { spawnSync } from 'node:child_process';
import { appendFileSync, mkdtempSync, readFileSync } from 'node:fs';
import { cpus, loadavg, tmpdir } from 'node:os';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = join(dirname(fileURLToPath(import.meta.url)), '..');
const log = join(frontend, '..', 'docs', 'ecosystem', 'test_timing.jsonl');
const out = join(mkdtempSync(join(tmpdir(), 'vitest-')), 'result.json');
const load0 = loadavg()[0], t0 = Date.now();
const r = spawnSync('npx', ['vitest', 'run', '--reporter=json', `--outputFile=${out}`], { cwd: frontend, stdio: ['ignore', 'ignore', 'inherit'] });
const wall = Date.now() - t0, load1 = loadavg()[0];
const res = JSON.parse(readFileSync(out, 'utf8'));
const tests = res.testResults.flatMap((f) => f.assertionResults.map((a) => ({ file: relative(frontend, f.name), title: [...a.ancestorTitles, a.title].join(' > ').slice(0, 140), ms: Math.round(a.duration ?? 0), status: a.status })));
const slow = [...tests].sort((a, b) => b.ms - a.ms).slice(0, 10);
const line = { date: new Date().toISOString(), label: process.argv[2] ?? '', cpus: cpus().length, loadBefore: +load0.toFixed(2), loadAfter: +load1.toFixed(2), wallMs: wall, tests: tests.length, passed: tests.filter((t) => t.status === 'passed').length,
  failed: tests.filter((t) => t.status === 'failed').map((t) => t.title), over1s: tests.filter((t) => t.ms > 1000).length, slowest: slow };
appendFileSync(log, `${JSON.stringify(line)}\n`);
console.log(`tests ${line.tests} (passed ${line.passed}, failed ${line.failed.length}), wall ${(wall / 1000).toFixed(1)} s, load ${line.loadBefore} -> ${line.loadAfter}`);
for (const s of slow.slice(0, 5)) console.log(`  ${String(s.ms).padStart(6)} ms  ${s.file}  ${s.title.slice(0, 80)}`);
process.exit(r.status ?? 1);
