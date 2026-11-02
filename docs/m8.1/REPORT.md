# M8.1 — Continuous visual verification, screenshot-driven improvement, real-time performance

> **M8.2 corrections (2026-10-15).** Two findings change how parts of this report should be read; the report itself is
> left as written.
>
> * The live result of 60 fps through step ≈860 was measured on a lightly loaded machine. A hidden standard-view
>   renderer, present since M8, kept running under the hi-fi live view and grew in cost through the run. Under moderate
>   load, the M8.1 build falls to 18 fps late in a run.
> * `TRAVEL_TOP` = 1.55 m considered the tool but not a carried sample. Recorded carried samples passed through drawn
>   instruments.
>
> Both are fixed in M8.2; see `docs/m8.2/VISUAL_EVALUATION.md`.

Branch `lab-m8-visual-verification`, from `lab-m8-high-fidelity` at `77c9a38`. The M8 branch is preserved. No frozen
M1–M9 scientific result, record or protocol was modified. The level statuses are unchanged:

- **Level 1:** achieved.
- **Level 2:** partially demonstrated, not achieved under the frozen criteria (the transfer-latency verification
  discrepancy).
- **Level 3:** not achieved.

The laboratory is a visualisation of recorded simulation-internal runs. It is not evidence of autonomous science or of
strong Xenoscience.

Every change below went through the same loop:

1. implement one subsystem;
2. run tsc, ESLint and the lab tests;
3. build;
4. render in a real Chromium;
5. capture screenshots;
6. inspect them directly;
7. fix what the screenshots showed;
8. commit, with that stage's evidence in `docs/m8.1/<stage>/`.

Each stage directory holds `capture.json` with per-shot metadata:

- commit;
- record name and sha256;
- step;
- camera mode, position and target;
- selection and layers;
- quality;
- viewport, canvas and DPR;
- browser and GPU;
- in-page self-test and frame statistics.

`00-before` is the untouched M8 baseline (commit `77c9a38`) and was never overwritten.

## Environment

- Headless Chrome for Testing 151.0.7922.34, from the Playwright cache, driven over CDP.
- GPU: ANGLE Metal on an Apple M1 with 8 GB.
- Local service: `uvicorn xzr.service.app:app --app-dir backend --port 3011`.

The in-app browser pane was hidden during this work, so no visible-window rendering was checked; all rendering below is
headless Chromium with a real GPU.

**Viewport versus canvas.** The required "1200×866" is the *browser viewport*. The 3D canvas inside it is **800×723**,
because the side panel takes the rest. M8's report called a 1600×1000 viewport's canvas "1200×866". This report names
both values everywhere.

## Commits

| # | commit | subsystem | evidence |
|---|---|---|---|
| 1 | `8e9ff3b` | capture v2 (metadata, 14+2 viewpoints, live profile); runtime connections redrawn as a ceiling terminal grid | `01-connections` |
| 2–3 | `fab4d63` | monochrome materials and lighting; camera composition (`closeView`) | `02-lighting`, `03-camera` |
| 4 | `3654322` | live view profiled over a run's lifetime; side panel throttled (250 ms) and memoised | `04-live-before`, `04-live-after` |
| 5 | `2e14a76` | distinct observation and memory apparatus; interpenetration test | `05-apparatus` |
| 6 | `155bb4a` | mechanical detail (guides, drives, end trucks, cable carrier, louvre actuators); a failed gantry was not shown as failed | `06-mechanics` |
| 7 | `c8e4a89` | full reachable-envelope verification; instruments below the travel plane; ceiling hangers; draw calls 972 → 681 | `07-envelope` |
| — | (this commit) | final captures at 1200×866, 1920×1080 and DPR 2; report and docs | `08-final` |

## Before and after, by subsystem

Paths are relative to `docs/m8.1/`. Each row has a "before" (the M8 baseline) and an "after" (final) at the same URL,
record, step and camera.

| subsystem | before | intermediate | after | what changed and why (from the screenshots) |
|---|---|---|---|---|
| Whole installation | `00-before/1200x866@1/01-overview.png` | `02-lighting/…/01-overview.png` | `08-final/1200x866@1/01-overview.png`, `08-final/1920x1080@1/01-overview.png` | **Before:** apparatus were near-black silhouettes on a black floor, and connection risers rose from every chamber like stalactites. **After:** a graded monochrome palette (floor, plinth, graphite, dark steel), environment light and a counter-light. Connections end at a ceiling terminal grid, so no moving bridge crosses a riser. |
| Runtime connections | `00-before/…/04-dense-cluster.png` | `01-connections/…/04-dense-cluster.png` | `08-final/…/04-dense-cluster.png` | Vertical risers became ceiling-hung terminals. A test checks that the terminals clear every gantry part over the whole record. |
| Camera, apparatus | `00-before/…/07-sensor-assembly.png`, `…/09-shared-resource.png` | `03-camera/…` | `08-final/…/07-sensor-assembly.png`, `…/09-shared-resource.png` | **Before:** the apparatus camera could sit inside a chamber housing (a white wall filled the frame). **After:** `closeView` searches outward directions and rejects positions inside housings. |
| Camera, sensor | `00-before/…/08-observation-restricted.png` | `03-camera/…/08-…` | `08-final/…/08-observation-restricted.png` | **Before:** with empty recorded coverage (during extinction) the sensor camera fell back to the overview. **After:** it looks from the head across its own domain, so the restriction itself is visible. |
| System B hub | (fan-like rotor) `00-before/…/04-dense-cluster.png` | `05-apparatus/…/15-hub.png` | `08-final/…/15-hub.png` | A receiver tower: cabinet, mast and three rings. The remote pods were inside the hub; they were moved, and a new interpenetration test fails on the old placement ("B:head vs B:sensor"). |
| System C memory store | slots hidden on the inner face | `05-apparatus/…/16-memory-store.png` | `08-final/…/16-memory-store.png` | 48 slots on the outward face, filled top-down. At m7 step 481, 7 lit slots = 7 recorded entries. |
| System A local sensor | `00-before/…/07-sensor-assembly.png` | `05-apparatus/…/07-…` | `08-final/1200x866@2/07-sensor-assembly.png` | A post, a two-segment boom with joints, and a hooded pod and lens, so it reads as an articulated instrument rather than a box. |
| Gantry mechanics | `00-before/…/05-transport.png`, `…/06-sample-grasp.png` | `06-mechanics/…` | `08-final/…/05-transport.png`, `…/06-sample-grasp.png` | Linear guides on the rails, end trucks on the bridge, trolley drive housings, a cable carrier that follows the trolley, and louvre actuators. Fix: the carriages shared one material, so a failed gantry darkened nothing, or everything. A per-carriage material and a test fix this. |
| Envelope and frames | `06-mechanics/…/03-domain.png` | `07-envelope/…` | `08-final/…/03-domain.png`, `…/02-oblique.png` | The instrument column and some service housings stood inside reachable envelopes (one recorded case: m7 step 4, column versus carriage). Instruments are now below `TRAVEL_TOP`, and housings are at `SERVICE_X`. Frame corners inside another bay's reach hang from the ceiling instead of standing on columns. |
| Domain / extinction / re-ignition | `00-before/…/10-extinction.png`, `…/11-reignition.png` | — | `08-final/…/10-extinction.png`, `…/11-reignition.png` | The same camera at t440 (0 chambers observed, apparatus physically intact) and at t690 (re-ignition). These views are now legible because of lighting; nothing scene-specific was added. |
| System comparison | `00-before/…/13-system-comparison.png` | `05-apparatus/…/13-…` | `08-final/…/13-system-comparison.png` | Three apparatus families are distinguishable in one frame. A comparison table is in the panel. |
| Live operation | `00-before/…/14-live-operation.png` | `04-live-before`, `04-live-after` | `08-final/1200x866@1/14-live-operation.png` | See the performance section. |

## Defects found by looking at screenshots or by the new tests

| defect | found by | fix | guarded by |
|---|---|---|---|
| Connection risers would be crossed by moving bridges | screenshot (stage 01) | ceiling terminal grid | `assemblies.test.ts`: terminals clear every gantry part over the record |
| Dark silhouettes; apparatus unreadable | screenshot | palette and lighting | screenshots only (subjective) |
| Apparatus camera inside a chamber housing | screenshot | `closeView` | — |
| Sensor camera stuck at the overview when coverage is empty | screenshot | look across own domain | — |
| Remote sensor pods inside the hub | screenshot | pods moved | interpenetration test (3 records, sampled steps) |
| Store slots facing inward (invisible) | screenshot | outward face, top-down fill | — |
| A failed gantry was not displayed as failed (shared material) | screenshot, then test | per-carriage material | test: failure darkens only its carriage, rails unchanged |
| Instrument column hit by a carriage at m7 step 4 | recorded-motion test | instruments below `TRAVEL_TOP` | recorded carriage and mast versus statics, 4 records |
| A knee brace of bay 7 inside bay 0's reach | synthetic envelope sweep | hull-based reach; ceiling hangers at blocked corners | sweep over `reachHull` at travel height (0.2 m grid) |
| Late-run live frame tail (p99 32.7 ms at t≈856) | live profile | panel throttled and memoised | live profile windows |
| Draw calls rose to 972 after the detail work | metadata | merged housings, bridges and chamber statics; instanced spots | per-scene draw counts in `capture.json` |

## Mechanical envelope verification

`assemblies.test.ts` now checks the following:

1. **Recorded tips inside the envelope.** Every recorded tool tip, at every step of four records, lies within the drawn
   envelope.
2. **No collisions along recorded motion.** No recorded carriage or mast position intersects a sensor, store or
   instrument.
3. **Synthetic sweep of the reachable envelope.** Each bay's reach hull (its chamber and port placement spots, plus the
   bay centre) is swept on a 0.2 m grid at travel height. The carriage box is y 1.65–2.03 and the mast 2.03–3.35. They
   are tested against all static apparatus, and against other bays' columns, knee braces and hangers.
4. **Static heights.** No static part inside an envelope rises above `TRAVEL_TOP` = 1.55.
5. **Connection terminals.** The terminals clear the gantry parts.

The first sweep was vacuous: merged-column bounding boxes covered the whole bay. The corrected sweep found a real
conflict, which is now fixed. The sweep covers the *placement* envelope, which is what the physics can command
(`physics.py _free_spot`). It does not cover the full mechanical travel of the slide joints to their limits, which no
recorded or commandable operation reaches.

## Scientific operations match the records

In every scene, the in-page `selfTest()` compares rendered carriage groups and instanced sample matrices with
`physToView` of the recorded MuJoCo positions:

- worst error: **5.4×10⁻⁷ m**;
- positions checked: 80 or 40 per scene, at every resolution.

Other checks:

- **Store fill.** The store's lit slot count equals the recorded memory entries (7 at m7 step 481).
- **Extinction and re-ignition.** These are shown at the recorded steps of `m9-extinction-relocation-7000`. The
  observed-chamber count is 0 at t440.
- **Shared resource.** The shared-resource view selects `gantry:0`, the recorded shared carriage.
- **Provenance.** The provenance view selects the recorded `experiment_selected` event whose basis is `memory`.

Model tests, including accessibility against the backend's own `candidates()`, are unchanged and pass.

## Performance

### Scenes, 1200×866 viewport (800×723 canvas), balanced

The table compares draw calls and triangles per scene, then the displayed frame-interval p95/p99 (in ms) for the final
build at 1200×866 and at 1920×1080. The last column is the self-test's worst position error.

| scene | before draws / tris | after draws / tris | after p95 / p99 (1200×866) | after p95 / p99 (1920×1080) | self-test worst |
|---|---|---|---|---|---|
| 01-overview | 828 / 152k | 681 / 101k | 18.6 / 18.7 | 18.3 / 18.7 | 5.1e-7 |
| 02-oblique | 621 / 124k | 487 / 83k | 18.7 / 18.7 | 18.6 / **35.3** | 5.1e-7 |
| 03-domain | 341 / 86k | 232 / 50k | 18.2 / 18.7 | 18.6 / 18.7 | 5.1e-7 |
| 04-dense-cluster | 187 / 47k | 150 / 37k | 18.1 / 18.7 | 18.4 / 18.7 | 5.1e-7 |
| 05-transport | 398 / 90k | 244 / 57k | 18.1 / 18.6 | 18.0 / 18.8 | 5.1e-7 |
| 06-sample-grasp | 377 / 88k | 255 / 59k | 18.0 / 18.7 | 18.6 / 18.8 | 5.4e-7 |
| 07-sensor-assembly | 301 / 76k | 230 / 63k | 18.6 / 18.7 | 18.6 / 18.7 | 5.1e-7 |
| 08-observation-restricted | 721 / 148k | 244 / 61k | 16.7 / 16.8 | 16.7 / 16.8 | 5.1e-7 |
| 09-shared-resource | 398 / 100k | 211 / 56k | 16.7 / 16.8 | 16.7 / 16.8 | 5.1e-7 |
| 10-extinction | 308 / 86k | 164 / 49k | 16.7 / 16.8 | 16.8 / 16.8 | 5.1e-7 |
| 11-reignition | 323 / 90k | 167 / 49k | 16.7 / 16.8 | 16.8 / 16.8 | 5.1e-7 |
| 12-history-provenance | 404 / 102k | 228 / 60k | 16.7 / 16.8 | 16.7 / 16.8 | 5.1e-7 |
| 13-system-comparison | 607 / 141k | 386 / 85k | 16.7 / 16.8 | 16.7 / 16.8 | 5.1e-7 |
| 15-hub | — | 217 / 54k | 16.7 / 16.8 | 16.8 / 16.8 | 5.1e-7 |
| 16-memory-store | — | 74 / 29k | 16.7 / 16.8 | 16.8 / 16.8 | 5.1e-7 |
| 14-live-operation | 758 / 149k | 574 / 98k | 16.7 / 16.8 | — | 5.1e-7 |

The displayed frame interval is quantised to the 60 Hz vsync, so 16.7 ms means no missed frame. The 18.x ms p95 values
in the first scenes of each run are the warm-up of a fresh page, not dropped frames: all of those scenes report 60.0
fps. The single 35.3 ms p99 at 1920×1080 (02-oblique, 57.6 fps) is one dropped frame per ~30 in the densest view at
the largest canvas.

### GPU-synchronised frame cost (benchmark, overview scene)

All values are in ms, with `gl.finish` per frame.

| quality | canvas | before mean / p95 / p99 | after mean / p95 / p99 |
|---|---|---|---|
| performance | 800×723 | 4.05 / 7.3 / 15.0 | 4.05 / 7.2 / 13.6 |
| balanced | 800×723 | 8.81 / 14.5 / 18.7 | 10.05 / 15.7 / 19.8 |
| high | 800×723 | 10.53 / 16.6 / 21.4 | 9.80 / 14.7 / 19.6 |
| performance | 1520×914 (1920×1080 viewport) | — | 4.0 / 6.8 / 14.4 |
| balanced | 1520×914 | — | 12.0 / 20.8 / 75.5 |
| high | 1520×914 | — | 11.6 / 15.7 / 61.1 |
| balanced | 1200×1084 (DPR 2, capped at 1.5) | — | 11.7 / 17.4 / 81.6 |
| high | 1600×1446 (DPR 2) | — | 17.3 / 28.4 / 111.3; displayed p99 **433 ms** |

**Balanced.** The synchronised cost went up about 1.2 ms. That comes from the environment map and the counter-light
added for legibility, against fewer draw calls. It stays within budget: displayed frames hold 60 fps.

**High at DPR 2.** At DPR 2, `high` (full pixel ratio) **does not meet 60 fps** on this M1. That is a limit, not a
target: `balanced` caps the pixel ratio at 1.5 and holds 60 fps at DPR 2. The large synchronised p99 values at the big
canvases come from forcing `gl.finish` on every frame (GPU pipeline stalls). The displayed frames at the same settings
are 16.8 ms, except for `high` at DPR 2.

### Live execution (target: 60 fps balanced at 1200×866)

The live view ran preset `systems` at 8000 configurations, 8 steps/s, with 6 s profile windows.

| window | before p95 / p99 / max | panel ms (mean × count) | after p95 / p99 / max | panel ms (mean × count) | render ms after |
|---|---|---|---|---|---|
| early (t≈122) | 18.6 / 18.7 / 18.8 | 1.58 × 65 | 16.8 / 16.8 / 16.9 | 1.40 × 24 | 3.57 |
| t ≥ 400 (t≈461) | 18.6 / 18.7 / 18.7 | 1.79 × 67 | 16.8 / 16.8 / 16.9 | 1.42 × 24 | 3.53 |
| t ≥ 800 (t≈860) | 18.7 / **32.7** / **50.4** | 3.09 × 61 | 16.8 / 16.8 / 16.9 | 1.50 × 24 | 3.57 |

The "before" columns are `04-live-before`, which is the M8 code with the profiler. The "after" columns are `08-final`.

The tail growth was the side panel rebuilding every transfer's mediation on every step, with a cost that grew with the
number of transfers. The fix has two parts:

- the panel is throttled to 250 ms;
- the per-system levels and transfers are computed once, and mediation reuses them.

Per-part cost after the fix:

- record apply: 0.35 ms;
- render submit: 3.5 ms;
- WebSocket handling: 0.15 ms;
- long tasks: 0.

**Server step** (`backend/scripts/m81_runtime_profile.py`, preset `systems`):

- mean 16.6 ms per step, of which MuJoCo is 11.6 ms;
- the true-effect fork reaches a p99 of 32 ms on deliveries;
- this is within the 125 ms budget of 8 steps/s.

M8's claim of "live p95 50 ms" was not reproduced at t≈120. The real degradation was the late-run tail shown above.

## A–J evaluation (from direct inspection of the screenshots)

| dimension | before | after | assessment |
|---|---|---|---|
| A. Mechanical density | sparse frames, black | guides, end trucks, drives, cable carriers, actuators, hangers | Improved. Every added part represents a recorded joint or support (category 3) or is architecture (category 4). |
| B. Spatial coherence | risers through bridges; instruments inside reach | verified by recorded-motion and synthetic sweeps | Improved and now tested, not just seen. |
| C. Scientific legibility | the restriction was invisible | extinction, sensor restriction and store fill are visible | Improved. The oblique overview is still cluttered by connection lines at distance. |
| D. Material and lighting | near-black silhouettes | graded monochrome, environment light | Clearly improved. Still deliberately austere, with no textures. |
| E. Apparatus distinctiveness | A, B and C similar | articulated sensor; receiver tower with remote pods; slotted store | Improved. The differences are of apparatus, not of method: the systems share one rule (M4). |
| F. Camera composition | cameras inside housings; fallback to overview | `closeView`; sensor across its own domain | Improved. Free-camera scenes depend on the hand-chosen poses in the capture script. |
| G. Mechanical plausibility | failure not shown; collisions | per-carriage state; envelope tests | Improved within the placement envelope. Full slide-joint limits are not swept. |
| H. Runtime fidelity | self-test 5×10⁻⁷ m | unchanged, 5.4×10⁻⁷ m worst | Maintained. No rendering change moves recorded objects. |
| I. Visual originality | generic | a circular hall, a ceiling terminal grid, a central core | Modest. Function-led, not stylised. |
| J. Performance | live tail p99 32.7 ms late; 828 draws | live p99 16.8 ms throughout; 681 draws | Target met at 1200×866 balanced. `high` at DPR 2 misses. |

## Acceptance

Acceptance status, against the requirements:

- **Viewpoints.** All 14 required viewpoints, plus the hub and the store, were captured at 1200×866 and 1920×1080;
  5 were captured at DPR 2.
- **Self-test.** Passes in every scene.
- **Live performance.** 60 fps balanced at 1200×866 during live execution, with p95/p99 16.8/16.8 ms at t≈860.
- **Envelope tests.** Pass.
- **Visual defects.** Every defect found in screenshots is fixed or listed as a limit.

Cosmetic work stopped here.

## Regression (final commit)

* **Backend.** pytest: 340 passed. ruff: clean. mypy: no issues (105 files).
* **Research.** `research/post_active_inference` tests: 59 passed.
* **Frontend.** vitest: 68 passed (10 files). ESLint: clean. tsc: clean. Production build: succeeds.
* **Replays.** `xzr.lab.replay` gives full agreement, with 0 mismatched steps and identical events, for:
  * `m2-run-9100` (240 steps);
  * `m3-physical-9100` (240 steps);
  * `m7-systems-6000` (960 steps);
  * `m9-extinction-relocation-7000` (960 steps);
  * `m9-separated-resources-7000` (960 steps).
* **Frozen files.** `git diff 77c9a38 HEAD` outside `frontend/` and `docs/m8.1/` lists only the new
  `backend/scripts/m81_runtime_profile.py`. Every record, protocol, result and hash file is byte-identical to M8.
* **Research DOCX.** sha256 `f00dc9db01f51310…`, unchanged.

## Known limits

- Headless rendering only; the visible app pane was not available.
- One machine (Apple M1, 8 GB); no other GPU was tested.
- At DPR 2, `high` misses 60 fps.
- The 1920×1080 oblique view drops roughly 1 frame in 30.
- The oblique and overview views are visually busy, because of the overhead connection lines. Turning the
  *connections* overlay off removes them.
- The envelope sweep covers the commandable placement envelope, not joint-limit travel.
- Free-camera poses are hand-chosen in the capture script.

## Reproduction

```bash
.venv/bin/uvicorn xzr.service.app:app --app-dir backend --host 127.0.0.1 --port 3011
```

```bash
npm --prefix frontend run build
```

```bash
node frontend/scripts/m8-capture.mjs --stage 08-final --res 1200x866 --bench --live-windows 400,800
```

```bash
node frontend/scripts/m8-capture.mjs --stage 08-final --res 1920x1080 --bench --no-live
```

```bash
node frontend/scripts/m8-capture.mjs --stage 08-final --res 1200x866 --dpr 2 --scenes 01,02,04,07,13 --bench --no-live
```

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python scripts/m81_runtime_profile.py
```

Captures use a temporary Chrome profile, and close their own sessions through `/api/sessions` between page loads. The
service's per-client session limit is unchanged.
