// Run backend/scripts/numeric_trace.py inside the PUBLISHED browser runtime (Pyodide under Node), for comparison with
// the desktop trace:  node backend/scripts/web_numeric_trace.mjs <scenario> <out.json> [--steps ...] [--site DIR]
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const arg = (n) => { const i = process.argv.indexOf(n); return i < 0 ? undefined : process.argv[i + 1]; };
const site = resolve(arg('--site') ?? join(root, 'site'));
const rt = join(site, 'runtime');
const manifest = JSON.parse(readFileSync(join(rt, 'manifest.json'), 'utf8'));
const { loadPyodide } = await import(pathToFileURL(join(rt, 'pyodide/pyodide.mjs')).href);
const py = await loadPyodide({ indexURL: join(rt, 'pyodide') + '/' });
await py.loadPackage(['numpy', 'pydantic']);
const zip = readFileSync(join(rt, manifest.engine));
py.unpackArchive(zip.buffer.slice(zip.byteOffset, zip.byteOffset + zip.byteLength), 'zip', { extractDir: '/engine' });
const rest = process.argv.slice(2).filter((a, i, all) => a !== '--site' && all[i - 1] !== '--site');
const hostOut = rest[1];
rest[1] = '/tmp/_trace.json';  // written inside the runtime's virtual filesystem, then copied out
py.globals.set('ARGV', JSON.stringify(['numeric_trace.py', ...rest]));
py.globals.set('SRC', readFileSync(join(root, 'backend/scripts/numeric_trace.py'), 'utf8'));
py.runPython(`
import json, os, sys
os.environ['XZR_SCENARIOS'] = '/engine/scenarios'
sys.path.insert(0, '/engine')
sys.argv = json.loads(ARGV)
g = {'__name__': '__main__'}
exec(compile(SRC, 'numeric_trace.py', 'exec'), g)
`);
writeFileSync(hostOut, py.FS.readFile('/tmp/_trace.json', { encoding: 'utf8' }));
