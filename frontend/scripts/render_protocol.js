// Reproducible rendering protocol for the XENO ECOSYSTEM view (paste into the page's console while the view is open with ?view=ecosystem&tab=xenoscience&horizon=360&tick=100&cam=habitat;
// the camera is set once by window.__meos.setCamera and then left alone). Frames are rendered back to back with a GPU sync by the view's own benchmark hook, so the display rate does not limit them
// and a hidden browser pane does not matter. Engine time is the HTTP time of the /api/meos run calls, measured apart from drawing; the per-tick state projection is the view's simUpdate mean.
//   1. paste this file;  2. await __pp.round(k) three times (conditions normal / layer off / exploded);  3. __pp.runs holds the results;  4. __pp.fetchLog holds the engine call times.
// Each condition: 20 warm-up frames, then 150 timed frames. A frame with the reflection pass (every 30th at rest) is reported separately. Report medians and p95, and the spread over rounds.
(async () => {
  const m = window.__meos, wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const q = (a, p) => { const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(p * s.length))]; };
  const P = window.__pp = { m, wait, q, runs: [], fetchLog: [] };
  P.btn = (re) => [...document.querySelectorAll('button')].find((b) => re.test(b.textContent.trim()));
  P.setPressed = async (re, on) => { const b = P.btn(re); if ((b.getAttribute('aria-pressed') === 'true') !== on) { b.click(); await wait(500); } };
  P.bench = (n = 150) => {
    m.benchmark(20); const r = m.benchmark(n, false, true), calls = r.series.calls, lo = [], hi = [];
    calls.forEach((c, i) => (c > Math.min(...calls) * 1.4 ? hi : lo).push(r.ms[i]));
    return { n: r.ms.length, med: +q(r.ms, 0.5).toFixed(2), p95: +q(r.ms, 0.95).toFixed(2), medNoReflection: +q(lo, 0.5).toFixed(2), reflectionFrames: hi.length, callsLow: Math.min(...calls), callsHigh: Math.max(...calls) };
  };
  P.round = async (k) => {
    const row = { round: k };
    await P.setPressed(/^coupling layer$/, true); await P.setPressed(/^exploded view$/, false); row.normal = P.bench();
    await P.setPressed(/^coupling layer$/, false); row.layerOff = P.bench(); await P.setPressed(/^coupling layer$/, true);
    await P.setPressed(/^exploded view$/, true); row.exploded = P.bench(); await P.setPressed(/^exploded view$/, false);
    return row;
  };
  // The reflection pass: at rest the puddle reflection is refreshed every 30th frame (terrain.ts), a frame of about twice the draw calls. This measures those frames apart from the others, over several samples,
  // and the period between them. Append the returned object, with the date and the load average, to docs/ecosystem/perf_log.jsonl.
  P.reflection = (samples = 5, frames = 240) => {
    const out = [];
    for (let k = 0; k < samples; k++) {
      m.benchmark(20); const r = m.benchmark(frames, false, true), calls = r.series.calls, lo = Math.min(...calls), hi = [], normal = [], pos = [];
      calls.forEach((c, i) => { if (c > lo * 1.4) { hi.push(r.ms[i]); pos.push(i); } else normal.push(r.ms[i]); });
      const gaps = pos.slice(1).map((p, i) => p - pos[i]);
      out.push({ frames: r.ms.length, reflectionFrames: hi.length, callsNormal: lo, callsReflection: Math.max(...calls), medNormal: +q(normal, 0.5).toFixed(2), p95Normal: +q(normal, 0.95).toFixed(2),
        medReflection: hi.length ? +q(hi, 0.5).toFixed(2) : null, extraMsPerReflectionFrame: hi.length ? +(q(hi, 0.5) - q(normal, 0.5)).toFixed(2) : null, period: [...new Set(gaps)] });
    }
    return out;
  };
  const of = window.fetch;
  window.fetch = async (u, i) => {
    const t0 = performance.now(), r = await of(u, i);
    if (/\/api\/meos\/(run|mfs-run|reconfigure|replay)/.test(String(u))) { const txt = await r.clone().text(); P.fetchLog.push({ url: String(u).replace(/^.*\/api\/meos/, ''), ms: Math.round(performance.now() - t0), bytes: txt.length }); }
    return r;
  };
  // playback: the state projection per tick, apart from drawing:  m.resetPerf(); for (t = 100; t < 190; t++) { m.goto(t); await wait(25); }  then  m.perf().simUpdateMsMean
})();
