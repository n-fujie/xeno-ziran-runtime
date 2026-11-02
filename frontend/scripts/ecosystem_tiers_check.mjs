// XENO ECOSYSTEM — quality-tier check: each tier loads without errors with its own pipeline, and switching the tier in the running page rebuilds the scene with the new pipeline.
//
//   node frontend/scripts/ecosystem_tiers_check.mjs --base http://127.0.0.1:3031
import { createRequire } from 'node:module';
const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d; };
const base = arg('base', 'http://127.0.0.1:3031');
const require = createRequire((process.env.PLAYWRIGHT_DIR ?? process.cwd()) + '/package.json');
const { chromium } = require('playwright');
const browser = await chromium.launch({ executablePath: process.env.CHROME, args: ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu', '--enable-webgl'] });
const EXPECT = { performance: (p) => p.passes.length === 0, balanced: (p) => p.passes.join() === 'RenderPass,OutputPass,ShaderPass', high: (p) => p.passes.includes('UnrealBloomPass') && p.passes.includes('BokehPass') };
const results = []; let failed = 0;
const check = (name, ok, detail) => { results.push({ name, ok, detail }); if (!ok) failed++; console.log(ok ? 'ok  ' : 'FAIL', name, JSON.stringify(detail)); };
const errors = [];
for (const tier of ['performance', 'balanced', 'high']) {
  const page = await browser.newPage({ viewport: { width: 1400, height: 800 } });
  page.on('pageerror', (e) => errors.push(`${tier}: ${String(e).slice(0, 200)}`));
  await page.goto(`${base}/?view=ecosystem&cam=body&layers=physical,meos&tick=120&quality=${tier}&chrome=0&capture=1&labels=0`, { waitUntil: 'load' });
  await page.waitForFunction(() => document.querySelector('.eco-stage')?.getAttribute('data-settled') === '1' && window.__meos?.ready?.(), null, { timeout: 120000 });
  const p = await page.evaluate(() => window.__meos.pipeline());
  const r = await page.evaluate(() => window.__meos.benchmark(5));
  check(`tier ${tier} loads with its pipeline`, EXPECT[tier](p) && p.quality === tier, p.passes);
  check(`tier ${tier} draws`, r.drawCalls > 20 && r.triangles > 1000, { calls: r.drawCalls, triangles: r.triangles });
  check(`tier ${tier} keeps the same mechanical detail of the bodies (the tier changes the detail, never the parts)`, p.bodies.probes === 11 && p.bodies.cableRoutes >= 10, p.bodies);
  await page.close();
}
// switch in the running page
const page = await browser.newPage({ viewport: { width: 1672, height: 900 } });
page.on('pageerror', (e) => errors.push(`switch: ${String(e).slice(0, 200)}`));
await page.goto(`${base}/?view=ecosystem&cam=body&layers=physical,meos&tick=120&quality=balanced`, { waitUntil: 'load' });
await page.waitForFunction(() => window.__meos?.ready?.(), null, { timeout: 120000 });
for (const tier of ['high', 'performance', 'balanced']) {
  await page.evaluate((t) => { const sel = [...document.querySelectorAll('select')].find((s) => [...s.options].some((o) => o.value === 'performance') && [...s.options].some((o) => o.value === 'high')); const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; set.call(sel, t); sel.dispatchEvent(new Event('change', { bubbles: true })); }, tier);
  await page.waitForFunction((t) => window.__meos?.ready?.() && window.__meos.pipeline().quality === t, tier, { timeout: 60000 });
  const p = await page.evaluate(() => window.__meos.pipeline());
  check(`switching to ${tier} rebuilds the scene with that tier's pipeline`, EXPECT[tier](p), p.passes);
}
check('no page errors in any tier or switch', errors.length === 0, errors);
await browser.close();
console.log(failed ? `${failed} FAILED` : 'all tier checks passed');
process.exit(failed ? 1 : 0);
