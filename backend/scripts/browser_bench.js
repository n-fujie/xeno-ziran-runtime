// In-page benchmark and behaviour check of the browser runtime. Paste into the console of /app/ (or run through a
// browser-automation "evaluate"); it talks to the app's own worker through the app's own module, so it measures exactly
// what a visitor gets, in the browser it runs in. Returns one JSON-able object (also logged).
//
//   await (await fetch('/runtime/browser_bench.js')).text()  -- or paste the file; then:  await xzrBrowserBench({ sizes: ['demo-3k'] })
//
// It never reads or sends anything outside the page. It uses at most one extra session (the app's own is left alone).
async function xzrBrowserBench(opts = {}) {
  const sample = opts.samples ?? ['small-600', 'demo-3k'];
  const seconds = opts.seconds ?? 4;
  const chunk = performance.getEntriesByType('resource').map((r) => r.name).find((n) => /\/assets\/webRuntime-[^/]+\.js$/.test(n));
  if (!chunk) throw new Error('open /app/ first (the runtime module has not been loaded)');
  const mod = await import(chunk);
  const call = async (method, path, body) => {
    const t0 = performance.now();
    const raw = await mod.webHandler.postMessage({ op: 'request', request: JSON.stringify({ method, path, body: body ?? null }) });
    const r = JSON.parse(raw);
    return { ...r, ms: performance.now() - t0 };
  };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const out = { userAgent: navigator.userAgent, hardwareConcurrency: navigator.hardwareConcurrency, deviceMemory: navigator.deviceMemory ?? null,
    marks: performance.getEntriesByType('mark').filter((m) => m.name.startsWith('xzr-web')).map((m) => [m.name, Math.round(m.startTime)]),
    scenarios: [] };
  for (const name of sample) {
    const rec = { name };
    const created = await call('POST', '/api/sessions', { sample: name });
    rec.createStatus = created.status; rec.createMs = Math.round(created.ms);
    if (created.status !== 200) { rec.error = created.body; out.scenarios.push(rec); continue; }
    const sid = created.body.id; rec.nodes = created.body.n ?? created.body.nodes ?? null;
    const st = async () => (await call('GET', `/api/sessions/${sid}`)).body;
    // unthrottled run: as fast as the worker can go, with no stream attached (the page's own rendering is not involved)
    await call('POST', `/api/sessions/${sid}/control`, { action: 'run', speed: 0 });
    const t0 = (await st()).t; const w0 = performance.now();
    await sleep(seconds * 1000);
    const t1 = (await st()).t; rec.unthrottledStepsPerS = +((t1 - t0) / ((performance.now() - w0) / 1000)).toFixed(1);
    // stop
    await call('POST', `/api/sessions/${sid}/control`, { action: 'pause' });
    const stopped = await st(); await sleep(400); const after = await st();
    rec.stopHolds = stopped.t === after.t; rec.running = after.running;
    // resume at the default pace, then a single step and a batch
    await call('POST', `/api/sessions/${sid}/control`, { action: 'run', speed: 20 });
    const r0 = (await st()).t; await sleep(1500); const r1 = (await st()).t;
    rec.resumeStepsIn1_5s = r1 - r0;
    await call('POST', `/api/sessions/${sid}/control`, { action: 'pause' });
    const s0 = (await st()).t; await call('POST', `/api/sessions/${sid}/control`, { action: 'step', steps: 1 }); await sleep(300);
    rec.singleStep = (await st()).t - s0;
    // change a parameter (a practice command) and run a branch comparison; the live session keeps stepping meanwhile
    const cmd = await call('POST', `/api/sessions/${sid}/practice/command`, { text: (opts.commands ?? {})[name] ?? opts.command ?? 'remove concept human', auto_compare: true, horizon: 60 });
    rec.commandStatus = cmd.status;
    if (cmd.status === 200) {
      await call('POST', `/api/sessions/${sid}/control`, { action: 'run', speed: 20 });
      const c0 = (await st()).t; const w = performance.now();
      let job; const jid = cmd.body.job; rec.jobId = typeof jid === 'string' ? jid.slice(0, 8) : null;
      for (let i = 0; i < 1200 && jid; i++) {
        await sleep(100);
        job = (await call('GET', `/api/jobs/${jid}`)).body;
        if (job && ['done', 'error', 'cancelled'].includes(job.status)) break;
      }
      rec.liveAdvancedDuringJob = (await st()).t > c0;
      rec.compare = { status: job?.status ?? 'unknown', seconds: +((performance.now() - w) / 1000).toFixed(2), liveStepsDuringJob: (await st()).t - c0 };
      await call('POST', `/api/sessions/${sid}/control`, { action: 'pause' });
    }
    if (opts.cancel) {  // a queued comparison is cancellable; a second session's job queues behind the first one's
      const other = await call('POST', '/api/sessions', { sample: 'small-600' });
      await call('POST', `/api/sessions/${sid}/practice/command`, { text: opts.command ?? 'remove concept human', auto_compare: false });
      const a = await call('POST', `/api/sessions/${sid}/compare`, { horizon: 300 });
      await call('POST', `/api/sessions/${other.body.id}/practice/command`, { text: 'remove concept inside', auto_compare: false });
      const b = await call('POST', `/api/sessions/${other.body.id}/compare`, { horizon: 300 });
      const cancelled = await call('POST', `/api/jobs/${b.body.job}/cancel`);
      await sleep(300);
      const bj = (await call('GET', `/api/jobs/${b.body.job}`)).body;
      rec.cancel = { cancelStatus: cancelled.status, queuedJobStatus: bj.status };
      for (let i = 0; i < 600; i++) { const aj = (await call('GET', `/api/jobs/${a.body.job}`)).body; if (['done', 'error', 'cancelled'].includes(aj.status)) { rec.cancel.firstJob = aj.status; break; } await sleep(100); }
      await call('DELETE', `/api/sessions/${other.body.id}`);
    }
    rec.wasmHeapMiBAfter = +(Number(await mod.webHandler.postMessage({ op: 'memory' })) / 1048576).toFixed(0);
    await call('DELETE', `/api/sessions/${sid}`);
    out.scenarios.push(rec);
  }
  console.log(JSON.stringify(out));
  return out;
}
globalThis.xzrBrowserBench = xzrBrowserBench;
