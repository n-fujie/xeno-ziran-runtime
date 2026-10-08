# XENO ZIRAN SIMULATOR for iOS — on-device runtime

The iOS app runs the simulator **locally on the device**. It is not a client of a remote runtime: no server, socket,
proxy or account is involved. The public research-results site (ziran-xeno-simulator.vercel.app) stays the
place for published results; heavy experiments stay on the desktop runtime.

```
┌──────────────────────── iOS app (io.platodesign.xenoziransimulator) ─────────────────────────┐
│ SwiftUI shell ── lifecycle (scenePhase), start-up / failure screens, share sheet, memory     │
│      │                                                                                        │
│ WKWebView ── bundled interface (frontend, VITE_NATIVE=1) served from the bundle: xzr://app/   │
│      │  window.webkit.messageHandlers.xzr  (request · share · openResults)                   │
│      ▼                                                                                        │
│ SimulatorRuntime.swift ── serial queue ── XZRPython.c (CPython C API, GIL-aware)              │
│      ▼                                                                                        │
│ embedded CPython 3.14.7 + numpy 2.5.2 ── xzr.native.bridge.handle / poll  (allowlisted)      │
│      ▼                                                                                        │
│ xzr.service.operations ── Session ── engine / detector / compare / practice (same source)    │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Release status (2026-10-06, 20:55 JST)

| item | state |
|---|---|
| App Store Connect app | XENO ZIRAN SIMULATOR, app ID 6819625252, bundle ID `io.platodesign.xenoziransimulator`, SKU `xeno-ziran-simulator-ios`, primary language English (U.K.) |
| Builds | 1.0 (1): VALID, INTERNAL_ONLY (exported with `testFlightInternalTestingOnly`, cannot be submitted). 1.0 (2): VALID, APP_STORE_ELIGIBLE. **1.0 (3)** (owner's Z logo as app icon): VALID, APP_STORE_ELIGIBLE, attached to version 1.0 |
| Version 1.0 metadata (set via API) | description, keywords, promotional text, support/marketing URL, copyright, subtitle, privacy-policy URL, categories Education/Reference, content rights, age rating (all none), review contact + notes, free price, all 175 territories, 8 iPhone 6.9" + 8 iPad 13" screenshots |
| Privacy policy | https://ziran-xeno-simulator.vercel.app/privacy/ (source `ios/AppStore/privacy-policy.html`, kept by `export_static.py`) |
| Still to do in App Store Connect (no API) | App Privacy questionnaire → "No, we do not collect data" → Publish; then "Add for Review" / "Submit to App Review" |
| Review | **not submitted** |
| Signing | Apple Distribution: NAOTO FUJIE (4YPXSK4SM2), App Store profile; get-task-allow = false; all 57 frameworks distribution-signed |
| Device coverage | simulators only; no physical device was available |
| Further uploads | `sh ios/scripts/testflight.sh <next build number>` (4, 5, …) |

Apple validation found two packaging defects, both fixed in `ios/scripts/install_runtime.sh`: the extension
frameworks generated from BeeWare's template declared `CFBundlePackageType = APPL` (now `FMWK`), and numpy's
build-time static libraries (`libnpymath.a`, `libnpyrandom.a`) were bundled (now removed; never used at run time).
Automatic signing of the archive step needs a registered device for a development profile; the archive is
therefore built unsigned and signed for distribution by the export step.

## Strategy

Four strategies were weighed (see the delivery report): A — thin WKWebView client of a remote runtime (rejected:
the spec forbids a permanent backend); B — port the engine to Swift; C — embed the existing Python engine;
D — port to TypeScript/WebAssembly in the page. B and D require re-implementing numpy's PCG64 `Generator`
draws (integers, choice, normal, dirichlet, binomial, beta, permutation, …) bit-exactly, plus the engine; any
divergence changes every trajectory, so they could not keep behaviour identical within this pass.
**C was chosen** because the same engine source runs on both platforms and conformance can be *proved* rather
than approximated.

numpy has iOS builds (BeeWare); scipy and pydantic-core do not. The engine therefore gained
`xzr/_compat`: pure-Python/numpy stand-ins for exactly the scipy/pydantic surface it uses, selected only when the
real libraries are absent (desktop is unchanged). The Fiedler-vector hierarchy (ARPACK) cannot be reproduced by a
dense eigensolver at the engine's tolerance, so the bundled scenarios carry **reference hierarchies** computed
on the desktop with scipy (`backend/scripts/export_hierarchy_cache.py`, keyed by the adjacency's SHA-256). A
scenario without a reference hierarchy (custom or loaded file with a new topology) uses the on-device dense
eigensolver and is labelled `Hierarchy.source = "computed on device (dense eigensolver)"` — its hierarchy, and
therefore address-based effects, may differ from the desktop's.

## Conformance (proved, not assumed)

`backend/tests/fixtures/conformance_reference.json` — the golden snapshot generated by the desktop runtime — is
checked on three paths:

| path | where | result |
|---|---|---|
| desktop, scipy/pydantic | `pytest tests/test_compat.py` | exact |
| desktop, iOS stand-ins forced | `pytest tests/test_compat.py` (XZR_FORCE_COMPAT=1) | exact |
| **inside the app** (iOS 26.3 simulator) | XCTest `testEngineConformanceAgainstTheDesktopGoldenFixture` | **exact** |

Exact = state fingerprints (all state arrays + RNG state) after warm-up, +50, +60 steps, after rewind and replay,
after Save → Load and 50 more steps; hierarchy hash; sizes. Observation metrics agree within 5 %; the only
metric allowed to differ is the sampled bottleneck concentration (BFS vs Dijkstra tie-breaking among equally
short paths), which never feeds back into the dynamics.

A Save file written by the desktop runtime loads in the app and, after 20 steps, gives the **byte-identical**
binary state snapshot the desktop gives (`testDesktopSaveFileLoadsToTheIdenticalState`); app saves load on the
desktop (`backend/tests/test_bridge.py`).

## Bridge and security

* `xzr/native/bridge.py`: one JSON request → one JSON response; **allowlisted routes only** (the REST surface the
  interface uses, the stream routes and two lifecycle routes). Everything else is 404. No route evaluates code,
  runs a subprocess, takes a file path, or exists for experiments/ops.
* The page reaches it only through the `xzr` WKScriptMessageHandlerWithReply, accepted only from the main frame
  of the `xzr:` origin. Navigation is confined to `xzr://app/`; the single outbound link (research results) opens
  in the system browser. `window.open` never creates a web view.
* The interface is built with a Content-Security-Policy (`connect-src 'self'`, no remote scripts/styles/fonts) and
  without the remote web-font import; the built bundle is checked for remote URLs in the tests.
* The bundled interpreter has **no networking modules** (`_socket`, `_ssl`, `_hashlib`/OpenSSL, `http`, `ctypes`
  are removed at build time; the engine was verified to run with them blocked). The app makes no automatic
  network requests (audited: 0 internet sockets in the app and its WebKit processes during a running session);
  the only network access is the user opening the research-results link, which opens in Safari. No analytics,
  tracking or telemetry. Website data store is non-persistent.
* Nothing is downloaded or executed at run time. Python bytecode is compiled at build time and signed with the app.

## Single-device session model

Sessions belong to the device user: no cookies, owners, IP limits, proxies or rate limits. What still matters on
a phone is kept: bounded resources, checkpoints, Save/Load, pause on backgrounding.

## Mobile limits (explicit refusal, never silent reduction)

| limit | iOS | desktop default |
|---|---|---|
| configurations (`XZR_MAX_NODES`) | 3,000 | 500,000 |
| connections (`XZR_MAX_EDGES`) | 48,000 | 32,000,000 |
| warm-up steps | 2,000 | 1,000,000 |
| concurrent sessions | 2 (oldest replaced) | 4 |
| step batch | 2,000 | 100,000 |
| checkpoints | 12 | 24 |
| comparison horizon | 300 | 5,000 |
| active / queued jobs | 1 / 2 | 8 / 64 |
| export size | 25 MB | 2 GB |

A larger scenario is refused with HTTP-like 413 and a message naming the limit and the desktop runtime (e.g.
`scenario has 10,000 configurations; this runtime allows 3,000 — larger workloads run in the desktop runtime`).
The scenario menu marks such scenarios as exceeding the limit. Resolution is never reduced to make a workload fit.
3,000 is the largest bundled scenario with a desktop reference hierarchy (see Conformance).

## Lifecycle

* Background: every running session is paused under a background-task assertion (the process is then suspended
  by iOS — nothing runs in the background, and the app claims no background mode). Until the app is active again
  the runtime is *suspended*: a Run or Step request that was still in flight is not started but recorded as paused.
  Foreground (`/native/lifecycle/foreground`): the stream resumes and the page says which simulation was paused;
  the user presses Run to continue (nothing restarts by itself).
  Lifecycle requests run on their own high-priority queue, not behind interface requests and stream polls
  (measured before this change on an iPad simulator running the 3,000-configuration world: the pause waited
  4.8 s behind queued work).
* Memory warning: running sessions pause and rebuildable tile indexes are dropped (nothing the user made is lost).
* Web content process terminated by the system: the interface reloads and resumes the session still held by the
  runtime.

## Capabilities on iOS

Available: Network, Shape Space, Address Space, World Map, 3D Globe (deck.gl/WebGL in WKWebView), scale
navigation and inspector, Run/Pause/Step/+10/Reset/speed, rewind to checkpoints, Timeline, Compare (branch
comparison jobs), Philosophical Practice (command language, dependencies, commitments, apply/discard), Save/Load
(desktop-compatible files), all exports (CSV/JSON) via the share sheet, bundled scenarios ≤ 3,000 configurations.

Not available in the app (by design or not yet):

* Research-result views (Resolution matrix, Hidden difference, Scale penetration, Reasoning structures,
  Disconnection, Long-run compression, Reduction, Reason non-redundancy, Phase timeline, Primitive inspector):
  published on the research-results site; the app links to it (*Research Results ↗*).
* Experiment runs (`xzr/experiments`, `xzr/reasonlab`): desktop only.
* Scenarios above 3,000 configurations (benchmark-10k, benchmark-10k-reason): desktop runtime.
* Exact desktop hierarchies for *new* topologies (custom scenarios): computed on device with a dense eigensolver
  and labelled as such.
* Physical-device performance has not been measured (no device was connected); all timings below are simulator.

## Performance (iOS 26.3 simulators on an Apple-silicon Mac — **not a device**)

In-app benchmark (`testBenchmark`, XCTest inside the app). Simulator timings vary considerably between runs and
simulators (shared host CPU, first boot); ranges over the final runs on iPhone 17 Pro and 17 Pro Max:

| measure | small-600 | reason-lab (1,500) | demo-3k (3,000) |
|---|---|---|---|
| world build | 0.06–0.12 s | 0.22–0.33 s | 0.68–0.75 s |
| engine steps / s | 497–552 | 350–399 | 260–280 |
| session steps / s (engine + observation) | 5–57 | 21–36 | 22–27 |
| 50-step comparison | 2.2–39 s | 3.6–5.8 s | 5.1–8.7 s |
| save / load | ≤ 0.007 / ≤ 0.12 s | ≤ 0.011 / ≤ 0.29 s | 0.02 / ≤ 0.87 s |

The low ends for small-600 come from a freshly booted simulator under load; typical runs give 42–57 steps/s and
a 2–10 s comparison. Desktop for reference (same engine, scipy path): demo-3k 139–162 session steps/s.

Start-up: runtime 3.4–4.1 s warm (bytecode precompiled at build time — without it ~9 s). Launch to a running
3,000-configuration session: ~11 s warm; 24–48 s on the first launch after installing on a simulator (the
simulator checks the signatures of the 57 extension frameworks on first load). App: 54 MB (Release, device).
## Building

```bash
sh ios/scripts/fetch_vendor.sh             # Python.xcframework + numpy iOS wheels, SHA-256 pinned
(cd frontend && npm ci && npm run build:native)
(cd ios && xcodegen generate)
xcodebuild -project ios/XenoZiranSimulator.xcodeproj -scheme XenoZiranSimulator \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' test
```

Requirements: Xcode 26, xcodegen, a host CPython 3.14 (bytecode precompilation), Node for the interface.
Keep DerivedData outside `~/Desktop` (the default location is fine): the simulator needs Desktop access otherwise.
