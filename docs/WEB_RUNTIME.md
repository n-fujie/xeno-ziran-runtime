# Browser edition: the simulator running in a browser tab

The interactive simulator can run entirely in a visitor's browser, served as static files at `/app/` of the public site.
The same Python engine (`xzr`) that runs on the desktop and inside the iOS app runs in a Web Worker on **Pyodide**
(CPython compiled to WebAssembly) with numpy and pydantic. There is no simulation server: nothing is sent to the host
while the simulator runs; the host only serves files.

This is an engineering delivery of an existing simulator in a new place. It says nothing new about the science, and none
of the strong-Xenoscience conditions follows from it (section 11).

## 1. How it is built

| piece | where |
|---|---|
| in-process interface (the iOS app's) | `backend/xzr/native/bridge.py`: an allowlist of routes, JSON in / JSON out, stream items by polling |
| cooperative sessions (no threads) | `backend/xzr/service/session.py` (`COOPERATIVE`, `Session.pump`, `run_deferred`), `bridge.tick()` |
| time-sliced comparison jobs | `backend/xzr/compare/compare.py` (`compare_steps`: the comparison as a generator; `compare()` drives it straight through) |
| Web Worker host | `frontend/src/api/webRuntime.worker.ts` |
| main-thread transport | `frontend/src/api/webRuntime.ts`, selected by `VITE_WEBRT=1` in `frontend/src/api/native.ts` |
| the app | the same UI as the iOS app (`npm run build:web`), served under `/app/` |
| export | `backend/scripts/export_web_runtime.py` writes `site/app/` and `site/runtime/`; `export_static.py` writes the headers |

There is no WebSocket and none is assumed: the stream is the bridge's `poll()`, driven by the worker's loop.

**Cooperative mode.** WebAssembly has no threads. Where `sys.platform == "emscripten"` a `Session` starts no thread; the
worker calls `bridge.tick()` about every 16 ms, which gives the live sessions and the queued comparison a 12 ms slice
(shared when both have work, whole when only one does). The stepping rules are those of the simulation thread (pending
batches run unpaced, a running session is paced to its speed, stepping waits while a connected client has too many unsent
steps). A comparison is a generator that yields after every simulation step, so it advances in slices and **the live
simulation keeps running during it** (tested: `test_a_long_comparison_is_time_sliced_while_the_session_keeps_running`). A
queued comparison can be cancelled; a running one runs to completion (as on the desktop). Closing a session cancels its
queued comparison. On the desktop and in the iOS app nothing changes: they keep the simulation thread and the thread pool
(the comparison is the same code, driven straight through).

## 2. What is published

`/app/` (the page) and `/runtime/` (all static, served by the host):

| file | size (raw / gzip) | origin |
|---|---|---|
| `pyodide/pyodide.asm.wasm` | 9.6 / 3.5 MB | npm package `pyodide` 314.0.7 (pinned by `frontend/package-lock.json`) |
| `pyodide/python_stdlib.zip`, `pyodide.asm.mjs`, `pyodide.mjs` | 2.5 + 1.3 / ~2.8 MB | same |
| numpy 2.4.6, pydantic 2.12.5, pydantic-core 2.41.5, annotated-types 0.7.0, typing-extensions 4.15.0, typing-inspection 0.4.2 (wheels) | 4.8 / 4.7 MB | Pyodide release CDN, downloaded once at export time |
| `engine-<hash>.zip` | 0.15 MB | the engine source and scenarios (`ios/scripts/stage_engine.py`, the same files the iOS app embeds) |
| `manifest.json` | 2 KB | versions, hashes, the browser limits |

About **11 MB** are downloaded on the first start (gzip; computed from the files, not measured over a network).

Integrity: each wheel is checked against the sha-256 in Pyodide's own `pyodide-lock.json` (which comes from the pinned npm
package) when exported, and the published, trimmed lock file lists only these six packages, so Pyodide verifies each wheel
again in the visitor's browser. The engine zip is content-addressed (`engine-<sha256[:12]>.zip`, deterministic bytes).
`manifest.json` records every file's sha-256. **Self-hosted: no request goes to a CDN or to any other origin at run time**
(checked: the page's resource list contains only the site's own origin; the CSP forbids anything else).

## 3. Trust boundary and security

* The engine and every scenario run **in the visitor's tab**. Scenarios, session files and exports are read and written
  locally (`Load` reads a file chosen by the visitor into the page; `Save` / exports are downloads). Nothing is uploaded.
* There is **no server-side execution and no authentication**: there is no account, no cookie, no API and nothing to
  authenticate; the public host serves files only. The "capability session" model of the server runtime
  (`PUBLIC_RUNTIME_DEPLOYMENT.md`) does not apply here and is not claimed.
* The in-process interface is an allowlist (`native/bridge.py`): no route evaluates code, spawns a process or takes a
  filesystem path. Inputs are validated by the same checks as the server (`check_payload`, `check_scenario`) and bounded by
  the limits below; an exceeded limit is refused with a message naming it.
* Content-Security-Policy (header on `/app/*`, also a `<meta>` in the page): `default-src 'self'`, `script-src 'self'
  'wasm-unsafe-eval'`, `connect-src 'self'`, `worker-src 'self' blob:`, no `eval`, no inline script, no framing, no
  third-party fonts or scripts. `'wasm-unsafe-eval'` is required to compile WebAssembly. The page also sets
  `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`.
* No secret is embedded; the build contains no key, token or credential.
* The tab's resources (CPU, memory) are the visitor's own. Workloads are bounded (section 6) so a mistaken choice cannot
  freeze the tab for hours.
* Residual risks, stated: the integrity of the Pyodide files rests on the npm package pin plus the lock file hashes
  (supply-chain trust in the Pyodide project); a host that serves different files than were exported is not detected by the
  visitor's browser (no subresource-integrity attributes are used for the worker's dynamic imports).

## 4. Numerical results: not bit-identical to the desktop, and why

The browser engine reproduces the desktop **structurally exactly and numerically to about 1e-13**, but **not bit for bit**.

Measured by `backend/scripts/numeric_trace.py` (the same file runs on both sides) and `numeric_compare.py`:

| scenario | steps | integer / boolean arrays | float arrays | worst relative float difference |
|---|---|---|---|---|
| small-600 | 0 → 1,000 | identical at every checkpoint (0 of 36 arrays differ) | 8 differ at t0, 11 from t+50 | 5.2e-16 (t0), 1.9e-14 (t+50), 8.7e-14 (t+500), 1.6e-13 (t+1000) |
| demo-3k | 0 → 1,000 | identical at every checkpoint | 9 differ at t0, 12 from t+50 | 3.5e-14 (t0), 1.2e-13 (t+1000) |

Raw numbers: `docs/web-runtime/numeric-comparison-*.json`. The state fingerprint therefore differs (it hashes the raw bytes).
No integer or boolean state (ignitions, connections, forms, gates' discrete state) differed in any checkpoint of either
scenario, so no discrete divergence was observed within 1,000 steps. This does **not** bound the difference for longer
runs or other scenarios: the system can amplify rounding differences, and no bound is claimed.

**Cause (measured, not assumed).** All arrays have identical dtypes and shapes on both sides (checked). The differences come
from the arithmetic libraries: a probe of elementary functions on fixed inputs (`numeric_trace.py`) shows WebAssembly's math
library rounds differently from the desktop's: `tanh` differs in 995 of 4,001 inputs (up to 2 ulp), `exp` in 10, `sin` in
151, `arctan` in 253, `expm1` in 344, `log1p` in 334 (up to 1 ulp); `sqrt` is identical (exact). Summation and dot products
differ in blocking / order (up to several hundred ulp on 10,007-term sums). One further factor is not separated: the desktop
ran numpy 2.5.3 and Pyodide ships 2.4.6.

**What is guaranteed and what is not.**

* Within this build the runs are deterministic and replayable bit for bit: `backend/tests/fixtures/conformance_reference_wasm.json`
  is the browser build's own golden (state fingerprints after warm-up, 50 steps, rewind and replay, save and load) and
  `node backend/scripts/web_conformance.mjs` checks the **published** files against it exactly (0 differences).
  WebAssembly's floating-point semantics are fixed by its specification and the math library is compiled into the module, so
  other browsers are expected to give the same bits; **only Chromium was checked** (section 8). The same golden also
  reproduced bit for bit under Node on a Linux x86-64 CI runner (generated on macOS arm64), i.e. across CPU architectures
  for V8; it does not prove the same for other engines.
* Against the desktop golden the observation metrics (detector series, comparison summaries) agree within 5 % (0
  differences) and 18 exact fingerprints differ, as expected.
* The address hierarchy of a scenario is computed on the desktop (scipy ARPACK) and shipped as an exact reference for the
  bundled scenarios (`_compat/hierarchies/`, now including the two 10,000-node benchmarks), so the dynamics of bundled
  scenarios start from the desktop's hierarchy. A graph without a reference gets a hierarchy from the dense on-device
  eigensolver, which can differ from ARPACK's (the app labels the source: "computed on device"); this is the iOS app's
  existing behaviour.
* A result computed here and one computed on the desktop must not be compared bit for bit. Publication-grade runs belong
  to the desktop runtime.

## 5. Limits of the browser build (`manifest.json`, from measurements)

| limit | value | reason |
|---|---|---|
| configurations per scenario | 10,000 | measured below |
| connections | 100,000 | the 10k benchmarks have ~70,000 |
| configurations when the hierarchy must be computed on the device (`XZR_MAX_NODES_COMPUTED_HIERARCHY`) | 1,500 | the dense eigensolver is cubic: 1.0 s at 500, 3.8 s at 1,000, 10 s at 1,500, 23 s at 2,000, > 130 s at 4,000 (Pyodide under Node); 10,000 did not finish in 17 min of CPU time |
| sessions | 2 | memory |
| steps per request / warm-up / comparison horizon | 5,000 / 3,000 / 300 | responsiveness |

A graph above the hierarchy limit and without an exported reference is **refused up front** with the limit's name
(`max_nodes_computed_hierarchy`), instead of freezing the tab. Larger or custom graphs run in the desktop runtime.

## 6. Performance (measured)

Machine: Apple M1, 8 logical CPUs, 8 GB, macOS. **Browser**: Chromium 152 (the desktop app's built-in browser), served
locally with the production headers (`backend/scripts/serve_site.py`), so network transfer time is not included.
**CLI** figures are Pyodide under Node 24 (V8's WebAssembly, no rendering) and are not browser figures.

Browser (Chromium; `backend/scripts/browser_bench.js` against the app's own worker):

| scenario | session create | unthrottled steps/s | 60-step comparison | live steps during it | wasm heap |
|---|---|---|---|---|---|
| small-600 | 73 ms | 156 | 1.4 s | 22 | n/m |
| demo-3k (3,000) | 609 ms | 79 | 3.3 s | 40 | n/m |
| benchmark-10k (10,000) | 5.5 s | 24 | 6.8 s | (not run) | 234-280 MiB |

("unthrottled" = speed 0, no stream attached; with the stream and rendering the UI shows about 15-17 steps/s at the
default 20/s on demo-3k. n/m = not measured.)

* Start-up (warm HTTP cache, localhost): runtime files fetched and Pyodide initialised ~3.0 s, numpy + pydantic + engine
  import ~1.6 s: **ready ≈ 4.6-4.8 s** after navigation. A cold download adds the transfer of ~11 MB. A mobile-size
  viewport on the same machine took ~15 s once (not repeated, not analysed).
* At 10,000 configurations the browser engine runs about 24 steps/s unthrottled, so the default pace of 20 steps/s is
  barely reachable there (13 steps/s measured after Resume, including page load). It works; it is not comfortable.
* CLI (Node): engine-only timing at larger sizes with a **placeholder hierarchy** (the real one cannot be computed there;
  timing only, no scientific use): 5,000 nodes 60 steps/s, 10,000 nodes 33 steps/s, 50-step comparison 4.5 s. The desktop
  engine is about 4× faster than Pyodide on the same machine (demo-3k session: 368 vs 86 steps/s).
* Memory: the browser's per-tab limit was not reached. The Worker's WebAssembly heap (a high-water mark) was 234-280 MiB at
  10,000 configurations. JS-heap and total-tab figures were not measured.
* Not measured: a cold, network-fed first load; Firefox and Safari; low-end phones; thermal throttling.
* No performance claim is made beyond these conditions.

## 7. Offline and caching

There is no service worker. After the first load the browser's HTTP cache decides: the host's default for static files
revalidates on every visit (a 304 per file, no re-download); the engine zip is content-addressed and cached as immutable.
**Offline use is not supported** (a reload without network fails with the page's "runtime could not start" message and a
Retry button).

## 8. Verification status

| item | result |
|---|---|
| Chromium 152 (built-in browser), desktop viewport | verified: start, Run, Pause, Resume, Step, preset switch, practice command, branch comparison (completes while the live session keeps stepping), queued-job cancel, direct URL (`?view=practice`), Back / Forward, reload (new worker), mobile viewport (375×812) layout, no console errors during normal use, failure path (runtime manifest missing → clear message, Retry works after the files return) |
| 10,000-node scenario in the browser | starts, runs, compares (numbers above) |
| Safari (WebKit) | **not verified**: on the development machine Safari is in Lockdown Mode, which disables WebAssembly; the page reports that clearly ("WebAssembly is not available in this browser…") but the engine in WebKit was not exercised |
| Firefox | **not verified** (not installed) |
| Chrome (stable), Edge | not verified separately (Chromium engine verified through the built-in browser) |
| real mobile devices | not verified |
| production host (Vercel, https://ziran-xeno-simulator.vercel.app/app/) | **files, hashes and headers verified on the live URL** with `node backend/scripts/verify_published_runtime.mjs <url>`: all 10 runtime files, the engine zip, and the 6 wheels match their sha-256; the WebAssembly file is served as `application/wasm` (brotli, 3.5 MB); `/app/` sends the CSP and `nosniff`; `/app` redirects to `/app/`; the existing result and lab routes still work. **The live page was not exercised in a real browser** from the development environment: the built-in browser blocks every request to that origin (client-side policy, even the main site's own CSS) and Safari has WebAssembly disabled. The same bytes (hash-equal) pass `web_conformance.mjs` locally, and the identical build ran in the built-in browser from `localhost` |

## 9. Testing

* `backend/tests/test_cooperative.py` (10 tests): no thread started, `pump` equals the threaded engine bit for bit, pacing,
  pause, backpressure, `bridge.tick`, time-sliced comparison with the live session running, sliced = direct result,
  cancellation, close leaves no job, the computed-hierarchy limit.
* `node backend/scripts/web_conformance.mjs` (against the **published** `site/runtime`): desktop-golden observation check,
  browser golden exact check, session / stream / tick / comparison / save / load / limit refusal through the interface.
* `frontend/src/api/webRuntime.test.ts` (6 tests): the Worker transport against a fake Worker (start, id routing, stream
  pushes, missing manifest and retry, failed boot, WebAssembly switched off, share / openResults).
* Existing suites unchanged and all passing: backend 273 tests (263 on `main` + 10 new), frontend 40 (34 + 6 new), ruff and
  mypy clean. The iOS and default frontend builds no longer contain any browser-runtime code (checked: 0 such chunks).
* Not automated in CI: the real-browser checks (section 8); they were run by hand and recorded here.

## 10. Reproduction

```
cd frontend && npm ci
python backend/scripts/export_static.py site          # research-result pages (existing)
python backend/scripts/export_web_runtime.py site     # /app/ and /runtime/
node backend/scripts/web_conformance.mjs --site site
python backend/scripts/serve_site.py site 4173        # then open http://localhost:4173/app/
node backend/scripts/web_scaling.mjs --site site --sizes 500,1000,1500,2000
node backend/scripts/web_scaling.mjs --site site --sizes 3000,5000,10000 --synthetic-hierarchy
# numerics: run numeric_trace.py with CPython and (through web_numeric_trace.mjs) with the published runtime, then
python backend/scripts/numeric_compare.py desktop.json wasm.json
# in the browser console on /app/: import('/bench.js') after copying backend/scripts/browser_bench.js to the site root
```

## 11. What this is not

The browser edition makes the existing simulator available without a server. It is not evidence for any of the four
conditions of strong Xenoscience (independence from human energy; independence from human readability; material and
organisational self-reproduction of the inquiry cycle; autonomous revision of variables, observation boundaries and
scales): all four remain **unestablished**, individually and jointly. The simulator's results remain experimental and
analytical outputs, not real-world forecasts.
