// XENO ECOSYSTEM — visual-regression captures and performance measurements.
//
//   node frontend/scripts/ecosystem_capture.mjs --base http://127.0.0.1:3031 --out docs/ecosystem/visual [--width 1672 --height 941] [--quality balanced]
//
// Needs Playwright (resolved from PLAYWRIGHT_DIR, a directory whose node_modules contains it) and a Chromium/headless-shell binary (CHROME). It loads the view with
// ?chrome=0 (the stage alone), waits until the record is loaded and the scene settled, takes the picture of the stage and reads window.__meos.perf().
// In a headless browser WebGL runs on a software rasteriser (SwiftShader): the frame rates it reports are those of software rendering, not of a GPU.
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d; };
const base = arg('base', 'http://127.0.0.1:3031'), out = arg('out', 'docs/ecosystem/visual'), width = +arg('width', 1672), height = +arg('height', 941), quality = arg('quality', 'balanced');
const only = arg('only', null);
const wait = +arg('wait', 9000);
const require = createRequire((process.env.PLAYWRIGHT_DIR ?? process.cwd()) + '/package.json');
const { chromium } = require('playwright');
const exe = process.env.CHROME;
mkdirSync(out, { recursive: true });

export const SHOTS = {
  '01-overview': 'cam=overview&layers=physical,meos&tick=120',
  '02-habitat': 'cam=habitat&layers=physical,operational,firing&tick=120',
  '03-research-core': 'cam=core&layers=physical&tick=120',
  '04-meos0-active': 'cam=habitat&layers=physical,meos,operational&tick=120',
  '05-meos-collapse': 'preset=a2-removed&cam=habitat&layers=physical,meos,firing&tick=150',
  '06-xenobody-boundary': 'cam=habitat&layers=physical,xenobody,address&tick=120',
  '07-history-overlay': 'cam=habitat&layers=physical,history&tick=120',
  '08-subsurface-laboratory': 'reductions=1&cam=subsurface&layers=physical&tick=120',
  // second stage: the research device (fixed camera presets, so that a capture is comparable with the earlier ones)
  '09-observation-array': 'cam=array&layers=physical,meos&tick=120',
  '10-philosophical-socket': 'preset=recovery-demo&horizon=360&phil=revision&cam=socket&layers=physical,meos&tick=165',
  '11-resource-pulse': 'preset=recovery-demo&horizon=360&phil=revision&cam=habitat&layers=physical,meos&tick=154',
  '12-boundary-open': 'preset=recovery-demo&horizon=360&phil=revision&cam=habitat&layers=physical,meos&tick=125',
  '13-recovered': 'preset=recovery-demo&horizon=360&phil=revision&cam=habitat&layers=physical,meos&tick=175',
  // the experimental bodies and the wet ground (third stage)
  '14-experimental-body': 'cam=body&layers=physical,meos&tick=120&labels=0',
  '15-observation-node': 'cam=observer&layers=physical,meos&tick=120&labels=0',
  '16-wet-ground': 'cam=puddle&layers=physical&tick=120&labels=0',
  '17-body-coupling-cut': 'preset=recovery-demo&horizon=360&phil=revision&cam=body&layers=physical,meos&tick=125&labels=0',
  '18-body-renewal': 'preset=recovery-demo&horizon=360&phil=revision&cam=body&layers=physical,meos&tick=175&labels=0',
};

// default: the machine's GPU through ANGLE/Metal (frame rates are then those of the GPU); --software forces SwiftShader (slow, a rasteriser on the CPU)
const software = process.argv.includes('--software');
const browser = await chromium.launch({ executablePath: exe, args: software ? ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-webgl'] : ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu', '--enable-webgl'] });
const perf = {};
for (const [name, q] of Object.entries(SHOTS)) {
  if (only && !only.split(',').some((o) => name.includes(o))) continue;
  const page = await browser.newPage({ viewport: { width, height } });
  page.on('pageerror', (e) => console.error('pageerror', String(e).slice(0, 300)));
  await page.goto(`${base}/?view=ecosystem&${q}&quality=${quality}&chrome=0&capture=1`, { waitUntil: 'load' });
  await page.waitForFunction(() => document.querySelector('.eco-stage')?.getAttribute('data-settled') === '1' && window.__meos?.ready?.(), null, { timeout: 120000 });
  await page.waitForTimeout(wait);
  await page.evaluate(() => window.__meos.resetPerf());  // measure after warm-up: the scene build and shader compilation are not steady state
  await page.waitForTimeout(+arg('measure', 5000));
  perf[name] = await page.evaluate(() => ({ ...window.__meos.perf(), camera: window.__meos.camera(), stats: window.__meos.stats() }));
  await (await page.$('.eco-stage')).screenshot({ path: join(out, `${name}.png`), timeout: 300000 });
  await page.close();
  console.log(name, 'ok', perf[name].fps.toFixed(1), software ? 'fps (software rendering)' : 'fps (GPU, headless)');
}
writeFileSync(join(out, `perf-${quality}.json`), JSON.stringify({ browser: software ? 'headless Chromium, WebGL on SwiftShader (software)' : 'headless Chromium, WebGL on ANGLE Metal (GPU)', viewport: [width, height], quality, perf }, null, 1));
await browser.close();
