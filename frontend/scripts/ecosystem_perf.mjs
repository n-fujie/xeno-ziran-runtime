// XENO ECOSYSTEM — uncapped render-cost measurement per quality tier and fixed camera, with feature ablations.
//
//   node frontend/scripts/ecosystem_perf.mjs --base http://127.0.0.1:3031 --out docs/ecosystem/performance_stage3.json [--frames 150] [--ablate]
//
// The page is loaded with ?chrome=0 at a fixed viewport; window.__meos.benchmark(n) renders n frames back to back with a GPU sync after each, so the figure is the cost of a
// frame and not the display's refresh rate. fps = 1000 / median. The machine's GPU is used through ANGLE/Metal (--software selects SwiftShader).
import { createRequire } from 'node:module';
import { writeFileSync } from 'node:fs';

const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d; };
const base = arg('base', 'http://127.0.0.1:3031'), out = arg('out', 'docs/ecosystem/performance_stage3.json'), frames = +arg('frames', 150), width = +arg('width', 1672), height = +arg('height', 808);
const ablate = process.argv.includes('--ablate'), software = process.argv.includes('--software');
const tiers = arg('tiers', 'performance,balanced,high').split(','), cams = arg('cams', 'overview,body,observer,habitat').split(',');
const require = createRequire((process.env.PLAYWRIGHT_DIR ?? process.cwd()) + '/package.json');
const { chromium } = require('playwright');
const browser = await chromium.launch({ executablePath: process.env.CHROME, args: software ? ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--enable-webgl'] : ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu', '--enable-webgl'] });
const stat = (ms) => { const s = [...ms].sort((a, b) => a - b), q = (f) => s[Math.min(s.length - 1, Math.floor(s.length * f))]; return { median: +q(0.5).toFixed(2), p95: +q(0.95).toFixed(2), p99: +q(0.99).toFixed(2), mean: +(ms.reduce((a, b) => a + b, 0) / ms.length).toFixed(2), max: +s[s.length - 1].toFixed(2), fps_from_median: +(1000 / q(0.5)).toFixed(1) }; };
const result = { measured_with: software ? 'headless Chromium, SwiftShader' : 'headless Chromium, ANGLE Metal', viewport: [width, height], frames, rows: [] };
// a camera token may carry a research UI to hold open while the stage is measured: ``habitat+research`` (the RESEARCH tab), ``habitat+technical`` (the technical sheet with the research map and the route topology), ``habitat+repair`` (the RESEARCH tab with a repaired run and the recovery map) or ``habitat+repairtech`` (the technical sheet with the repair figure and the repair layers; a build without the repair view ignores the repair parameters);
// the page then keeps its chrome (the panels are part of the cost). The Stage 3 build has neither, so there the same token measures the stage alone.
for (const tier of tiers) for (const token of cams) {
  const [cam, ui] = token.split('+');
  const page = await browser.newPage({ viewport: { width, height } });
  await page.goto(`${base}/?view=ecosystem&cam=${cam}&layers=physical,meos&tick=120&quality=${tier}${ui === 'research' ? '&tab=research&obs=interval:3' : ui === 'technical' ? '&tech=ncb&layer=route.active,route.dormant,mfs.current,mfs.alternative' : ui === 'repair' ? '&tab=research&stress=coupling%20gain%200.5&ract=resource.pulse/1/0/113' : ui === 'repairtech' ? '&tech=ncb&stress=coupling%20gain%200.5&ract=resource.pulse/1/0/113&layer=repair.damaged,repair.world,repair.repaired' : '&chrome=0'}&capture=1&labels=0`, { waitUntil: 'load' });
  await page.waitForFunction(() => document.querySelector('.eco-stage')?.getAttribute('data-settled') === '1' && window.__meos?.ready?.(), null, { timeout: 120000 });
  await page.waitForTimeout(2500);
  await page.evaluate(() => window.__meos.benchmark(30));  // warm-up: shader compilation, first uploads
  const run = async (label, orbit = false) => {
    const r = await page.evaluate(([n, o]) => window.__meos.benchmark(n, o), [frames, orbit]);
    return { label, ...stat(r.ms), cpu_submit_median: stat(r.js).median, gpu_time: r.gpu.length ? stat(r.gpu) : null, drawCalls: r.drawCalls, triangles: r.triangles, geometries: r.geometries, textures: r.textures };
  };
  // the fifth-stage additions: for the orbit, how many shader programs the renderer built, how many geometries were uploaded and how many LOD levels / visibilities flipped (from the benchmark
  // hook's per-frame series; the Stage 3 build has no such hook, so for it these are null)
  const series = async () => page.evaluate((n) => { const r = window.__meos.benchmark(n, true, true); const s = r.series; return s ? { programs_built: (r.programsBuilt ?? []).length, geometry_uploads: Math.max(0, Math.max(...s.geometries) - Math.min(...s.geometries)), lod_switches: s.lodSwitches.reduce((a, b) => a + b, 0), visibility_flips: s.visibilityFlips.reduce((a, b) => a + b, 0) } : null; }, frames);
  const row = { tier, camera: token, ui: ui ?? null, camera_spec: await page.evaluate(() => window.__meos.camera()), instances: await page.evaluate(() => window.__meos.stats().instances), full: await run('full (static camera)'), orbiting: await run('full (camera orbiting: the reflection refreshes every 2nd frame)', true) };
  row.orbit_series = await series();
  if (ablate) {
    row.ablation = {};
    for (const f of ['reflect', 'post', 'bloom', 'gravel', 'rocks', 'bodies', 'structure', 'terrain', 'arena', 'lines', 'points', 'everything']) {
      await page.evaluate((k) => window.__meos.setFeature(k, false), f);
      row.ablation[f] = await run(`without ${f}`);
      await page.evaluate((k) => window.__meos.setFeature(k, true), f);
    }
  }
  result.rows.push(row);
  console.log(tier, token, 'static', JSON.stringify({ m: row.full.median, p95: row.full.p95, calls: row.full.drawCalls, tris: row.full.triangles }), 'orbit', JSON.stringify({ m: row.orbiting.median, p95: row.orbiting.p95 }));
  await page.close();
}
writeFileSync(out, JSON.stringify(result, null, 1));
await browser.close();
