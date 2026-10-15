// M8 / M8.1 browser verification: render published laboratory records (and a live run) in a real Chromium (headless,
// GPU), run the in-page self-test against the rendered scene graph, measure frames, save PNG screenshots with full
// metadata, benchmark quality levels and profile the live view.
//
//   node frontend/scripts/m8-capture.mjs --stage <name> [--res 1200x866] [--dpr 1] [--scenes all|01,05] [--bench] [--no-live]
//   (needs the local service: make dev, or .venv/bin/uvicorn xzr.service.app:app --app-dir backend --port 3011)
//
// Browser: $CHROME, else the Chrome for Testing build cached by Playwright (~/Library/Caches/ms-playwright); nothing is
// downloaded. The app shell opens a simulation session per page load and the service limits sessions per client, so
// the script deletes its own sessions between loads (through the normal API; no limit is relaxed).

import { execSync, spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { homedir, tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d; };
const flag = (k) => process.argv.includes(`--${k}`);
const BASE = arg('base', 'http://127.0.0.1:3011');
const STAGE = arg('stage', 'adhoc');
const [W, H] = arg('res', '1200x866').split('x').map(Number);
const DPR = Number(arg('dpr', '1'));
const OUT = join(arg('out', join(ROOT, 'docs', 'm8.1')), STAGE, `${W}x${H}@${DPR}`);
const PORT = 9333 + Math.floor(Math.random() * 400);
const COMMIT = execSync('git rev-parse --short HEAD', { cwd: ROOT }).toString().trim()
  + (execSync('git status --porcelain -- frontend/src', { cwd: ROOT }).toString().trim() ? '+uncommitted' : '');

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

const recPath = (n) => join(ROOT, 'backend', 'experiments', 'results', 'lab', `${n}.json`);
const recHash = (n) => createHash('sha256').update(readFileSync(recPath(n))).digest('hex').slice(0, 16);
const load = (n) => JSON.parse(readFileSync(recPath(n), 'utf8'));
const SEP = load('m9-separated-resources-7000');
const EXT = load('m9-extinction-relocation-7000');
const M7 = load('m7-systems-6000');
const idx = (rec, t) => rec.steps.findIndex((s) => s.t === t);

// viewpoints chosen from the records themselves
const carryI = SEP.steps.findIndex((s, i) => i > 120 && Object.values(s.physics.gantries).some((g) => g.carrying));
const carried = Object.values(SEP.steps[carryI].physics.gantries).find((g) => g.carrying).carrying;
const grasp = SEP.physical_events.find((e) => e.type === 'sample_grasped' && e.t > 200);
const ext = EXT.config.extinction;
const reign = EXT.science_events.filter((e) => e.type === 'material_delivered' && e.system === 'A').map((e) => e.t).find((t) => t >= ext.t + 190);
const memSel = M7.science_events.findIndex((e) => e.type === 'experiment_selected' && e.basis === 'memory');
const memEv = M7.science_events[memSel];
const b1 = SEP.layout.bays['1'], b0 = SEP.layout.bays['0'];
const SCENES = [
  { name: '01-overview', rec: 'm9-separated-resources-7000', step: 480, cam: 'overview', note: 'complete installation' },
  { name: '02-oblique', rec: 'm9-separated-resources-7000', step: 480, cam: 'free', campos: [-6, 7.5, -24], target: [6, 1.2, 4], note: 'elevated oblique view across the installation, below the roof' },
  { name: '03-domain', rec: 'm9-separated-resources-7000', step: 480, cam: 'domain', domain: '1', note: 'one research domain' },
  { name: '04-dense-cluster', rec: 'm9-separated-resources-7000', step: 480, cam: 'free', campos: [b1[0] - 5.8, 3.0, b1[1] + 0.6], target: [b1[0] + 0.6, 0.9, b1[1] - 0.4], note: 'chambers, gantry, sensors and services of one domain, eye level' },
  { name: '05-transport', rec: 'm9-separated-resources-7000', step: carryI, cam: 'transfer', sel: `sample:${carried}`, note: `sample ${carried} carried (recorded) at index ${carryI}` },
  { name: '06-sample-grasp', rec: 'm9-separated-resources-7000', step: idx(SEP, grasp.t), cam: 'apparatus', sel: `sample:${grasp.sample}`, note: `recorded grasp of ${grasp.sample} at ${grasp.at}, t${grasp.t}` },
  { name: '07-sensor-assembly', rec: 'm7-systems-6000', step: 480, cam: 'apparatus', sel: 'sensor:A:head', sys: 'A', note: 'system A sensor head (local system)' },
  { name: '08-observation-restricted', rec: 'm9-extinction-relocation-7000', step: idx(EXT, ext.t + 5), cam: 'sensor', sys: 'A', note: 'A\'s observed chambers closed by the declared harness at t320' },
  { name: '09-shared-resource', rec: 'm7-systems-6000', step: 480, cam: 'apparatus', sel: 'gantry:0', note: 'shared bay-0 gantry in the M7 shared laboratory' },
  { name: '10-extinction', rec: 'm9-extinction-relocation-7000', step: idx(EXT, ext.t + 120), cam: 'domain', domain: '0', note: 'inside the extinct interval (M9-C definition)' },
  { name: '11-reignition', rec: 'm9-extinction-relocation-7000', step: idx(EXT, reign), cam: 'domain', domain: '0', note: `first delivery after the extinct interval, t${reign}` },
  { name: '12-history-provenance', rec: 'm7-systems-6000', step: idx(M7, memEv.t), cam: 'apparatus', sel: `chamber:${memEv.dst}`, sys: memEv.system, ev: `science:${memSel}`, note: `selection with basis = memory (recorded), science:${memSel}, t${memEv.t}` },
  { name: '15-hub', rec: 'm7-systems-6000', step: 480, cam: 'apparatus', sel: 'sensor:B:head', sys: 'B', note: 'system B hub (distributed system)' },
  { name: '16-memory-store', rec: 'm7-systems-6000', step: 480, cam: 'apparatus', sel: 'store:C:store', sys: 'C', note: 'system C memory store; filled slots = recorded memory entries' },
  { name: '13-system-comparison', rec: 'm7-systems-6000', step: 480, cam: 'free', campos: [b0[0] + 9, 9, b0[1] + 13], target: [b0[0] - 3, 0.8, b0[1] + 5], note: 'systems A, B, C with their observed chambers (comparison table in the panel)' },
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function cdp(wsUrl) {
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0;
  const pending = new Map();
  ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } };
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

async function waitFor(page, expr, ms = 45000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { if (await page.evaluate(expr).catch(() => false)) return true; await sleep(250); }
  throw new Error(`timeout waiting for ${expr}`);
}

async function closeSessions(page) {
  await page.evaluate(`(async () => { if (!location.href.startsWith('http')) return 0;
    const l = await fetch('/api/sessions').then((r) => r.json()).catch(() => []);
    for (const x of l) await fetch('/api/sessions/' + x.id, { method: 'DELETE' });
    return l.length; })()`).catch(() => 0);
}

const pct = (a, q) => { const s = [...a].sort((x, y) => x - y); return s.length ? +s[Math.min(s.length - 1, Math.floor(s.length * q))].toFixed(2) : null; };
const stats = (a) => ({ n: a.length, mean: a.length ? +(a.reduce((x, y) => x + y, 0) / a.length).toFixed(2) : null, p50: pct(a, 0.5), p95: pct(a, 0.95), p99: pct(a, 0.99), max: pct(a, 1) });

// displayed frames over a window, with long tasks and the view's own counters
const FRAMES = (ms) => `new Promise((res) => { const t = []; let last = performance.now(); let lt = 0, ltMs = 0;
  let po = null; try { po = new PerformanceObserver((l) => { for (const e of l.getEntries()) { lt++; ltMs += e.duration; } }); po.observe({ type: 'longtask', buffered: false }); } catch (e) {}
  const P = window.__labHiFi && window.__labHiFi.prof; if (P) for (const k of Object.keys(P)) P[k].length = 0;
  if (window.__labWs) window.__labWs.length = 0;
  const end = performance.now() + ${ms};
  const f = (now) => { t.push(now - last); last = now; if (now < end) requestAnimationFrame(f); else { po && po.disconnect();
    res({ frames: t.slice(1), longTasks: lt, longTaskMs: +ltMs.toFixed(1), prof: P ? JSON.parse(JSON.stringify(P)) : null, ws: (window.__labWs || []).slice() }); } };
  requestAnimationFrame(f); })`;

async function main() {
  mkdirSync(OUT, { recursive: true });
  const profile = join(tmpdir(), `m8-chrome-${process.pid}`);
  const chrome = spawn(chromePath(), ['--headless=new', `--remote-debugging-port=${PORT}`, `--window-size=${W},${H}`, `--user-data-dir=${profile}`,
    '--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist', '--no-first-run', '--no-default-browser-check', '--hide-scrollbars'], { stdio: 'ignore' });
  const only = arg('scenes', 'all');
  const scenes = only === 'all' ? SCENES : only === 'none' ? [] : SCENES.filter((s) => only.split(',').some((k) => s.name.startsWith(k)));
  try {
    let ver = null;
    for (let k = 0; k < 80 && !ver; k++) { await sleep(250); ver = await fetch(`http://127.0.0.1:${PORT}/json/version`).then((r) => r.json()).catch(() => null); }
    const tgt = await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: 'PUT' }).then((r) => r.json());
    const page = await cdp(tgt.webSocketDebuggerUrl);
    await page.send('Page.enable');
    await page.send('Runtime.enable');
    await page.send('Performance.enable');
    await page.send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: DPR, mobile: false });
    const report = { stage: STAGE, commit: COMMIT, browser: ver?.Browser, base: BASE, viewport: [W, H], devicePixelRatio: DPR, scenes: [] };
    const shoot = async (name, meta) => {
      const st = await page.evaluate('window.__labHiFi.state()');
      const self = await page.evaluate('window.__labHiFi.selfTest()');
      const fr = await page.evaluate(FRAMES(2500));
      const gpu = await page.evaluate(`(() => { const gl = window.__labHiFi.renderer.getContext(); const e = gl.getExtension('WEBGL_debug_renderer_info'); return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER); })()`);
      const shot = await page.send('Page.captureScreenshot', { format: 'png' });
      writeFileSync(join(OUT, `${name}.png`), Buffer.from(shot.data, 'base64'));
      const entry = { name, ...meta, commit: COMMIT, viewport: [W, H], devicePixelRatio: DPR, browser: ver?.Browser, gpu, state: st,
        selfTest: self, frames: stats(fr.frames), longTasks: fr.longTasks };
      report.scenes.push(entry);
      process.stdout.write(`${name}: t${st.step} ${st.cam} [${st.camera}] · positions ${self.positionsChecked} worst ${self.worstPositionError.toExponential(1)} · ${(1000 / entry.frames.mean).toFixed(1)} fps p95 ${entry.frames.p95} p99 ${entry.frames.p99} ms · ${self.drawCalls} draws\n`);
      return entry;
    };
    for (const sc of scenes) {
      const q = new URLSearchParams({ view: 'laboratory', hifi: '1', rec: sc.rec, step: String(sc.step), cam: sc.cam, quality: sc.quality ?? 'balanced' });
      for (const k of ['sel', 'sys', 'domain', 'layers', 'ev']) if (sc[k]) q.set(k, sc[k]);
      if (sc.campos) { q.set('campos', sc.campos.join(',')); q.set('target', sc.target.join(',')); }
      await closeSessions(page);
      await page.send('Page.navigate', { url: `${BASE}/?${q}` });
      await waitFor(page, `!!window.__labHiFi && (window.__labHiFiFrames ?? 0) > 30 && window.__labHiFi.rec.steps.length > 0`);
      await sleep(sc.cam === 'free' ? 1500 : 3200);  // camera transition
      await shoot(sc.name, { record: sc.rec, recordSha256: recHash(sc.rec), stepIndex: sc.step, note: sc.note, url: `/?${q}` });
    }
    if (flag('bench')) {  // GPU-synchronised render cost per quality level
      report.benchmark = [];
      for (const quality of ['performance', 'balanced', 'high']) {
        await closeSessions(page);
        await page.send('Page.navigate', { url: `${BASE}/?view=laboratory&hifi=1&rec=m9-separated-resources-7000&cam=overview&quality=${quality}` });
        await waitFor(page, `!!window.__labHiFi && (window.__labHiFiFrames ?? 0) > 30`);
        await sleep(3000);
        const t = await page.evaluate(`(() => { const H = window.__labHiFi, gl = H.renderer.getContext(), n = H.rec.steps.length, t = [];
          for (let k = 0; k < 30; k++) { H.lab.apply(k, 0, { coverage: true, conduits: true, events: new Set() }); H.renderer.render(H.scene, H.camera); }
          gl.finish();
          for (let k = 0; k < 480; k++) { const t0 = performance.now(); H.lab.apply((k * 2) % n, 0.5, { coverage: true, conduits: true, events: new Set() });
            H.renderer.render(H.scene, H.camera); gl.finish(); t.push(performance.now() - t0); } return t; })()`);
        const info = await page.evaluate(`({ draws: window.__labHiFi.renderer.info.render.calls, tris: window.__labHiFi.renderer.info.render.triangles, canvas: [window.__labHiFi.renderer.domElement.width, window.__labHiFi.renderer.domElement.height], ratio: window.__labHiFi.renderer.getPixelRatio() })`);
        const fr = await page.evaluate(FRAMES(4000));
        report.benchmark.push({ quality, gpuSyncedFrameMs: stats(t), displayed: stats(fr.frames), ...info });
        process.stdout.write(`bench ${quality}: synced ${stats(t).mean}/${stats(t).p95}/${stats(t).p99} ms · displayed p95 ${stats(fr.frames).p95} p99 ${stats(fr.frames).p99} · ${info.draws} draws · ${info.canvas.join('×')}@${info.ratio}\n`);
      }
    }
    if (!flag('no-live')) {  // live autonomous operation, with a profile of the live view
      await closeSessions(page);
      await page.send('Page.navigate', { url: `${BASE}/?view=laboratory&hifi=1&cam=overview` });
      await waitFor(page, `!!window.__labHiFi && (window.__labHiFiFrames ?? 0) > 30`);
      await page.evaluate(`[...document.querySelectorAll('button')].find((b) => b.textContent === 'Start live run').click(), true`);
      await waitFor(page, `[...document.querySelectorAll('.lab-live')].some((x) => /LIVE running/.test(x.textContent) && Number((x.textContent.match(/t (\\d+)/) || [])[1]) > 60)`, 90000);
      const metric = (m, k) => m.metrics.find((x) => x.name === k)?.value ?? 0;
      const profileWindow = async (label) => {
        const m0 = await page.send('Performance.getMetrics');
        const fr = await page.evaluate(FRAMES(6000));
        const m1 = await page.send('Performance.getMetrics');
        const t = await page.evaluate(`Number((document.querySelector('.lab-live').textContent.match(/t (\\d+)/) || [])[1])`);
        const p = { label, liveStepAtEnd: t, windowMs: 6000, displayed: stats(fr.frames), longTasks: fr.longTasks, longTaskMs: fr.longTaskMs,
          panelMs: stats(fr.prof?.panelMs ?? []), applyMs: stats(fr.prof?.applyMs ?? []), renderMs: stats(fr.prof?.renderMs ?? []),
          wsMessageMs: stats(fr.ws.map((x) => x.ms)), wsMessages: fr.ws.length,
          browserSeconds: Object.fromEntries(['ScriptDuration', 'TaskDuration', 'RecalcStyleDuration', 'LayoutDuration'].map((k) => [k, +(metric(m1, k) - metric(m0, k)).toFixed(3)])),
          jsHeapMB: +(metric(m1, 'JSHeapUsedSize') / 1048576).toFixed(1) };
        process.stdout.write(`live profile ${label} (t${t}): fps ${(1000 / p.displayed.mean).toFixed(1)} p95 ${p.displayed.p95} p99 ${p.displayed.p99} · panel ${p.panelMs.mean}/${p.panelMs.p95} ms ×${p.panelMs.n} · apply ${p.applyMs.mean} · render ${p.renderMs.mean}/${p.renderMs.p95} · ws ${p.wsMessageMs.mean} ms ×${p.wsMessages} · long tasks ${p.longTasks} · script ${p.browserSeconds.ScriptDuration}s · heap ${p.jsHeapMB} MB\n`);
        return p;
      };
      const profiles = [await profileWindow('early')];
      for (const target of (arg('live-windows', '') || '').split(',').filter(Boolean).map(Number)) {
        await waitFor(page, `Number((document.querySelector('.lab-live').textContent.match(/t (\\d+)/) || [])[1]) >= ${target}`, 180000);
        profiles.push(await profileWindow(`t>=${target}`));
      }
      const live = await page.evaluate(`document.querySelector('.lab-live').textContent`);
      const entry = await shoot('14-live-operation', { record: 'live', note: 'live run started from the viewer (preset systems)', liveStatus: live });
      entry.liveProfile = profiles;
      await page.evaluate(`[...document.querySelectorAll('button')].find((b) => b.textContent === 'Stop').click(), true`);
      await sleep(1500);
      await closeSessions(page);
    }
    writeFileSync(join(OUT, 'capture.json'), JSON.stringify(report, null, 1));
    await closeSessions(page);  // never leave a session behind (the service limits sessions per client)
    page.close();
  } finally {
    chrome.kill('SIGTERM');
    await sleep(500);
    for (let k = 0; k < 5; k++) {  // Chrome may still be writing its profile while it exits
      try { rmSync(profile, { recursive: true, force: true }); break; } catch { await sleep(500); }
    }
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
