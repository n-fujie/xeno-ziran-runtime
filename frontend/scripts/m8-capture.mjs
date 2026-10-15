// M8 browser verification: render published laboratory records in a real Chromium (headless, GPU), run the in-page
// self-test against the rendered scene graph, measure frame times with requestAnimationFrame, and save screenshots.
//
//   node frontend/scripts/m8-capture.mjs [base-url] [out-dir]
//   (needs the local service: make dev, or uvicorn xzr.service.app:app --app-dir backend --port 3011)
//
// Browser: $CHROME, else the Chrome for Testing build cached by Playwright (~/Library/Caches/ms-playwright). Nothing is
// downloaded. Talks to the browser over the DevTools protocol with Node's built-in WebSocket.

import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { homedir, tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const BASE = process.argv[2] ?? 'http://127.0.0.1:3011';
const OUT = process.argv[3] ?? join(ROOT, 'docs', 'm8');
const W = 1600, H = 1000, PORT = 9333;

function chromePath() {
  if (process.env.CHROME) return process.env.CHROME;
  const cache = join(homedir(), 'Library', 'Caches', 'ms-playwright');
  const dirs = existsSync(cache) ? readdirSync(cache).filter((d) => /^chromium-\d+$/.test(d)).sort().reverse() : [];
  for (const d of dirs) {
    const p = join(cache, d, 'chrome-mac-arm64', 'Google Chrome for Testing.app', 'Contents', 'MacOS', 'Google Chrome for Testing');
    if (existsSync(p)) return p;
  }
  throw new Error('no Chromium found: set CHROME');
}

const load = (n) => JSON.parse(readFileSync(join(ROOT, 'backend', 'experiments', 'results', 'lab', `${n}.json`), 'utf8'));
const SEP = load('m9-separated-resources-7000');
const EXT = load('m9-extinction-relocation-7000');
const idx = (rec, t) => rec.steps.findIndex((s) => s.t === t);

// scenes chosen from the records themselves (not by eye)
const carryI = SEP.steps.findIndex((s, i) => i > 120 && Object.values(s.physics.gantries).some((g) => g.carrying));
const carried = Object.values(SEP.steps[carryI].physics.gantries).find((g) => g.carrying).carrying;
const reloc = EXT.science_events.find((e) => e.type === 'sensor_relocated');
const ext = EXT.config.extinction;
const deliveredA = EXT.science_events.filter((e) => e.type === 'material_delivered' && e.system === 'A').map((e) => e.t);
const reign = deliveredA.find((t) => t >= ext.t + 190);
const SCENES = [
  { name: '01-overview', rec: 'm9-separated-resources-7000', step: 480, cam: 'overview', note: 'full installation, M9-A separated-resources record' },
  { name: '02-dense-domain', rec: 'm9-separated-resources-7000', step: 480, cam: 'domain', domain: '1', note: 'one research domain: chambers, gantry, ports, sensors' },
  { name: '03-physical-transfer', rec: 'm9-separated-resources-7000', step: carryI, cam: 'transfer', sel: `sample:${carried}`, note: `sample ${carried} carried (recorded) at index ${carryI}` },
  { name: '04-shared-resource', rec: 'm7-systems-6000', step: 480, cam: 'apparatus', sel: 'gantry:0', note: 'shared bay-0 gantry in the M7 shared laboratory (mediation panel)' },
  { name: '05-sensor-relocation', rec: 'm9-extinction-relocation-7000', step: idx(EXT, reloc.t), cam: 'sensor', sys: 'A', note: `recorded sensor relocation ${reloc.from} → ${reloc.to} at t${reloc.t}` },
  { name: '06-observation-restricted', rec: 'm9-extinction-relocation-7000', step: idx(EXT, ext.t + 5), cam: 'domain', domain: '0', note: 'A\'s observed chambers closed by the declared harness at t320' },
  { name: '07-extinction', rec: 'm9-extinction-relocation-7000', step: idx(EXT, ext.t + 120), cam: 'domain', domain: '0', note: 'inside the extinct interval (M9-C definition)' },
  { name: '08-reignition', rec: 'm9-extinction-relocation-7000', step: idx(EXT, reign), cam: 'domain', domain: '0', note: `first delivery after the extinct interval, t${reign}` },
  { name: '09-layer-A-only', rec: 'm9-separated-resources-7000', step: 480, cam: 'domain', domain: '1', layers: 'A', note: 'physical layer alone (MuJoCo-driven)' },
  { name: '10-high-quality', rec: 'm9-separated-resources-7000', step: 480, cam: 'domain', domain: '1', quality: 'high', note: 'high-fidelity quality mode' },
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function cdp(wsUrl) {
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0;
  const pending = new Map();
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); }
  };
  const send = (method, params = {}) => new Promise((res, rej) => {
    const k = ++id;
    pending.set(k, (d) => (d.error ? rej(new Error(`${method}: ${d.error.message}`)) : res(d.result)));
    ws.send(JSON.stringify({ id: k, method, params }));
  });
  const evaluate = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? 'evaluation failed');
    return r.result.value;
  };
  return { send, evaluate, close: () => ws.close() };
}

async function waitFor(page, expr, ms = 40000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (await page.evaluate(expr).catch(() => false)) return true;
    await sleep(250);
  }
  throw new Error(`timeout waiting for ${expr}`);
}

async function closeSessions(page) {
  await page.evaluate(`(async () => { if (!location.href.startsWith('http')) return 0;
    const l = await fetch('/api/sessions').then((r) => r.json()).catch(() => []);
    for (const x of l) await fetch('/api/sessions/' + x.id, { method: 'DELETE' });
    return l.length; })()`).catch(() => 0);
}

const FRAMES = `new Promise((res) => { const t = []; let last = performance.now();
  const f = (now) => { t.push(now - last); last = now; if (t.length < 181) requestAnimationFrame(f); else {
    const s = t.slice(1).sort((a, b) => a - b); const mean = s.reduce((a, b) => a + b, 0) / s.length;
    res({ frames: s.length, meanMs: +mean.toFixed(2), p95Ms: +s[Math.floor(s.length * 0.95)].toFixed(2), maxMs: +s[s.length - 1].toFixed(2), fps: +(1000 / mean).toFixed(1) }); } };
  requestAnimationFrame(f); })`;

async function main() {
  mkdirSync(join(OUT, 'screenshots'), { recursive: true });
  const profile = join(tmpdir(), `m8-chrome-${process.pid}`);
  const chrome = spawn(chromePath(), ['--headless=new', `--remote-debugging-port=${PORT}`, `--window-size=${W},${H}`, `--user-data-dir=${profile}`,
    '--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist', '--no-first-run', '--no-default-browser-check', '--hide-scrollbars'], { stdio: 'ignore' });
  try {
    let ver = null;
    for (let k = 0; k < 60 && !ver; k++) { await sleep(250); ver = await fetch(`http://127.0.0.1:${PORT}/json/version`).then((r) => r.json()).catch(() => null); }
    const tgt = await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: 'PUT' }).then((r) => r.json());
    const page = await cdp(tgt.webSocketDebuggerUrl);
    await page.send('Page.enable');
    await page.send('Runtime.enable');
    await page.send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
    const report = { browser: ver?.Browser, base: BASE, viewport: [W, H], scenes: [] };
    for (const sc of SCENES) {
      const q = new URLSearchParams({ view: 'laboratory', hifi: '1', rec: sc.rec, step: String(sc.step), cam: sc.cam, quality: sc.quality ?? 'balanced' });
      for (const k of ['sel', 'sys', 'domain', 'layers']) if (sc[k]) q.set(k, sc[k]);
      await closeSessions(page);  // the app shell opens a simulation session per load; the service limits them per client
      await page.send('Page.navigate', { url: `${BASE}/?${q}` });
      await waitFor(page, `!!window.__labHiFi && (window.__labHiFiFrames ?? 0) > 30 && window.__labHiFi.rec.config.gen_seed !== undefined`);
      await sleep(3200);  // camera transition
      const gpu = await page.evaluate(`(() => { const gl = window.__labHiFi.renderer.getContext(); const e = gl.getExtension('WEBGL_debug_renderer_info'); return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER); })()`);
      const self = await page.evaluate('window.__labHiFi.selfTest()');
      const frames = await page.evaluate(FRAMES);
      const shot = await page.send('Page.captureScreenshot', { format: 'png' });
      writeFileSync(join(OUT, 'screenshots', `${sc.name}.png`), Buffer.from(shot.data, 'base64'));
      report.scenes.push({ ...sc, gpu, selfTest: self, frames });
      process.stdout.write(`${sc.name}: positions ${self.positionsChecked} worst ${self.worstPositionError.toExponential(1)} · ${frames.fps} fps p95 ${frames.p95Ms} ms · ${self.drawCalls} draws\n`);
    }
    // render cost per quality level (GPU-synchronised: apply recorded state, render, gl.finish), replay advancing
    report.benchmark = [];
    for (const quality of ['performance', 'balanced', 'high']) {
      await closeSessions(page);
      await page.send('Page.navigate', { url: `${BASE}/?view=laboratory&hifi=1&rec=m9-separated-resources-7000&cam=overview&quality=${quality}` });
      await waitFor(page, `!!window.__labHiFi && (window.__labHiFiFrames ?? 0) > 30`);
      await sleep(3000);
      const b = await page.evaluate(`(() => { const H = window.__labHiFi, gl = H.renderer.getContext(), n = H.rec.steps.length, t = [];
        for (let k = 0; k < 30; k++) { H.lab.apply(k, 0, { coverage: true, conduits: true, events: new Set() }); H.renderer.render(H.scene, H.camera); }
        gl.finish(); const g0 = H.renderer.info.memory.geometries;
        for (let k = 0; k < 480; k++) { const t0 = performance.now(); H.lab.apply((k * 2) % n, 0.5, { coverage: true, conduits: true, events: new Set() });
          H.renderer.render(H.scene, H.camera); gl.finish(); t.push(performance.now() - t0); }
        t.sort((a, b) => a - b); const mean = t.reduce((a, b) => a + b, 0) / t.length;
        return { quality: '${quality}', frames: t.length, meanMs: +mean.toFixed(2), p50Ms: +t[240].toFixed(2), p95Ms: +t[Math.floor(t.length * 0.95)].toFixed(2),
          maxMs: +t[t.length - 1].toFixed(2), equivalentFps: +(1000 / mean).toFixed(1), drawCalls: H.renderer.info.render.calls,
          triangles: H.renderer.info.render.triangles, geometriesBefore: g0, geometriesAfter: H.renderer.info.memory.geometries,
          canvas: [H.renderer.domElement.width, H.renderer.domElement.height], pixelRatio: H.renderer.getPixelRatio(),
          heapMB: performance.memory ? +(performance.memory.usedJSHeapSize / 1048576).toFixed(1) : null }; })()`);
      const frames = await page.evaluate(FRAMES);
      report.benchmark.push({ ...b, rafFrames: frames });
      process.stdout.write(`bench ${quality}: ${b.meanMs} ms mean, p95 ${b.p95Ms} ms (≈${b.equivalentFps} fps unsynced) · rAF ${frames.fps} fps · ${b.drawCalls} draws · ${b.canvas.join('×')}\n`);
    }
    // live autonomous experiment: start a live run from the viewer, let it stream, capture, stop it
    await closeSessions(page);
    await page.send('Page.navigate', { url: `${BASE}/?view=laboratory&hifi=1&cam=overview` });
    await waitFor(page, `!!window.__labHiFi && (window.__labHiFiFrames ?? 0) > 30`);
    await page.evaluate(`[...document.querySelectorAll('button')].find((b) => b.textContent === 'Start live run').click(), true`);
    await waitFor(page, `[...document.querySelectorAll('.lab-live')].some((x) => /LIVE running/.test(x.textContent) && Number((x.textContent.match(/t (\\d+)/) || [])[1]) > 60)`, 90000);
    await sleep(2500);
    const liveSelf = await page.evaluate('window.__labHiFi.selfTest()');
    const liveStatus = await page.evaluate(`document.querySelector('.lab-live').textContent`);
    const liveFrames = await page.evaluate(FRAMES);
    const shot = await page.send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(join(OUT, 'screenshots', '11-live-run.png'), Buffer.from(shot.data, 'base64'));
    await page.evaluate(`[...document.querySelectorAll('button')].find((b) => b.textContent === 'Stop').click(), true`);
    await sleep(1500);
    await closeSessions(page);
    report.scenes.push({ name: '11-live-run', note: 'live run started from the viewer (preset systems), streamed while it runs', liveStatus, selfTest: liveSelf, frames: liveFrames });
    process.stdout.write(`11-live-run: ${liveStatus} · positions ${liveSelf.positionsChecked} worst ${liveSelf.worstPositionError.toExponential(1)} · ${liveFrames.fps} fps\n`);
    writeFileSync(join(OUT, 'browser-verification.json'), JSON.stringify(report, null, 1));
    page.close();
  } finally {
    chrome.kill('SIGTERM');
    await sleep(500);
    rmSync(profile, { recursive: true, force: true });
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
