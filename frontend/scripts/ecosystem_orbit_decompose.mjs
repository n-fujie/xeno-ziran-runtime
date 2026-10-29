// XENO ECOSYSTEM — decomposition of the slow frames of an orbit (stage four).
//
//   node frontend/scripts/ecosystem_orbit_decompose.mjs --base http://127.0.0.1:3031 --out docs/ecosystem/perf_stage4/orbit_decomposition.json [--tier balanced] [--cams habitat] [--frames 300]
//
// For each camera: the orbit is rendered with per-frame series (draw calls, triangles, geometries and textures held, LOD levels that changed, objects whose visibility flipped). The slow
// frames (above the 90th percentile) are compared with the rest on every series, and the correlation of the frame time with each series (and with its frame-to-frame change) is
// reported. Then each suspected cause is switched off in turn under the same orbit and the change of the median and the 95th percentile is reported:
//   reflection (the puddle Reflector), post-processing, labels (annotation sprites), shadows (none are enabled: reported as such), the line and point layers, gravel, rocks, bodies,
//   structure, terrain, arena. Nothing is changed in the scene by this script; the switches are the measurement hooks of window.__meos.setFeature.
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d; };
const base = arg('base', 'http://127.0.0.1:3031'), out = arg('out', 'docs/ecosystem/perf_stage4/orbit_decomposition.json'), frames = +arg('frames', 300), tier = arg('tier', 'balanced');
const noAblation = process.argv.includes('--no-ablation'), cams = arg('cams', 'habitat').split(','), width = +arg('width', 1672), height = +arg('height', 808);
const require = createRequire((process.env.PLAYWRIGHT_DIR ?? process.cwd()) + '/package.json');
const { chromium } = require('playwright');
const browser = await chromium.launch({ executablePath: process.env.CHROME, args: ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu', '--enable-webgl'] });
const pct = (a, f) => { const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(s.length * f))]; };
const stat = (ms) => ({ median: +pct(ms, 0.5).toFixed(2), p95: +pct(ms, 0.95).toFixed(2), p99: +pct(ms, 0.99).toFixed(2), max: +Math.max(...ms).toFixed(2), mean: +(ms.reduce((a, b) => a + b, 0) / ms.length).toFixed(2) });
const mean = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0);
const corr = (x, y) => { const mx = mean(x), my = mean(y); let sxy = 0, sxx = 0, syy = 0; for (let i = 0; i < x.length; i++) { sxy += (x[i] - mx) * (y[i] - my); sxx += (x[i] - mx) ** 2; syy += (y[i] - my) ** 2; } return sxx && syy ? +(sxy / Math.sqrt(sxx * syy)).toFixed(3) : null; };
const diff = (a) => a.map((v, i) => (i ? Math.abs(v - a[i - 1]) : 0));
const result = { measured_with: 'headless Chromium, ANGLE Metal', viewport: [width, height], tier, frames, cameras: {} };
for (const cam of cams) {
  const open = async (labels) => {
    const page = await browser.newPage({ viewport: { width, height } });
    await page.goto(`${base}/?view=ecosystem&cam=${cam}&layers=physical,meos&tick=120&quality=${tier}&chrome=0&capture=1&labels=${labels}`, { waitUntil: 'load' });
    await page.waitForFunction(() => document.querySelector('.eco-stage')?.getAttribute('data-settled') === '1' && window.__meos?.ready?.(), null, { timeout: 120000 });
    await page.waitForTimeout(2500); await page.evaluate(() => window.__meos.benchmark(40, true));
    return page;
  };
  const orbit = (page) => page.evaluate((n) => window.__meos.benchmark(n, true), frames);
  const page = await open(0), r = await orbit(page), ms = r.ms, thr = pct(ms, 0.9), slow = ms.map((v) => v >= thr);
  const S = r.series, cams_ = { calls: S.calls, triangles: S.triangles, geometries: S.geometries, textures: S.textures, programs: S.programs, lod_switches: S.lodSwitches, visibility_flips: S.visibilityFlips };
  const rows = {};
  for (const [k, a] of Object.entries(cams_)) {
    const sl = a.filter((_, i) => slow[i]), fa = a.filter((_, i) => !slow[i]);
    rows[k] = { mean_in_slow_frames: +mean(sl).toFixed(2), mean_in_other_frames: +mean(fa).toFixed(2), correlation_with_frame_time: corr(ms, a), correlation_with_change_between_frames: corr(ms, diff(a)), range: [Math.min(...a), Math.max(...a)] };
  }
  // GPU time and CPU submit time of the slow frames: which side of the frame is slow
  const gpu = r.gpu, js = r.js;
  const side = { cpu_submit_median: +pct(js, 0.5).toFixed(2), cpu_submit_p95: +pct(js, 0.95).toFixed(2), gpu_median: gpu.length ? +pct(gpu, 0.5).toFixed(2) : null, gpu_p95: gpu.length ? +pct(gpu, 0.95).toFixed(2) : null };
  const base_ = stat(ms), abl = {};
  for (const f of noAblation ? [] : ['reflect', 'post', 'lines', 'points', 'gravel', 'rocks', 'bodies', 'structure', 'terrain', 'arena']) {
    await page.evaluate((k) => window.__meos.setFeature(k, false), f);
    abl[f] = stat((await orbit(page)).ms);
    await page.evaluate((k) => window.__meos.setFeature(k, true), f);
  }
  await page.close();
  let withLabels = null;
  if (!noAblation) { const pl = await open(1); withLabels = stat((await orbit(pl)).ms); await pl.close(); }
  const shadows = await (async () => { const p = await open(0); const v = await p.evaluate(() => window.__meos.pipeline()); await p.close(); return v; })();
  result.cameras[cam] = { orbit: base_, side_of_the_frame: side, slow_frame_threshold_ms: +thr.toFixed(2), series: rows, ablation_orbit: abl, with_labels: withLabels, note_shadows: 'no light casts shadows in this scene (renderer.shadowMap is not enabled)', pipeline: shadows.passes };
  console.log(cam, JSON.stringify({ orbit: base_, side, labels: withLabels?.p95, programs: rows.programs.range }), abl.reflect ? `reflect off ${abl.reflect.p95} post off ${abl.post.p95}` : '');
}
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(result, null, 1));
await browser.close();
