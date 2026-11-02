# XENOSCIENCE ECOSYSTEM — integration into the existing XENO ECOSYSTEM view

Branch `feat/xenoscience-ecosystem-3d`, from `main` `3e874c5`. Local only: not pushed, not deployed, not part of the public static site.
The existing view, engine and records are unchanged; the work adds readings over them.

## 1. Inventory (Stage A, read from the repository)

| Question | What the repository has |
|---|---|
| Scientific engine | `backend/xzr/meos` (MEOS-0, engine `meos-0.5`): deterministic, seeded, record with digests; `analysis.observe` (observation regimes); intervention operations (`E.OPS`); `replay`; stage 4–6 experiments. Served by `backend/xzr/service/meos.py` under `/api/meos` (local only). |
| Other engines | the operational-shape runtime (`xzr` core, lab, hpo, teoo, totalobs, study); kept separate, not connected here. |
| Frontend | React 19, TypeScript, Vite 8, **three 0.169** (already used by the Ecosystem view), deck.gl 9 (network/globe views). No React Three Fiber. |
| 3D already present | `views/ecosystem/` renders the arena, bodies, cables, probes, technical sheets, LOD and quality tiers (`lod.ts`, `layers.ts`) from the engine's record. Camera presets, selection, layers, playhead, replay and an observation editor exist. |
| URL state | deep links `?view=ecosystem&tab=…&preset=…&obs=…&cam=…&tick=…` (`deeplink.ts`). |
| Baseline (before any change) | backend `1092 passed, 3 skipped` (25 min on this Mac, three warnings: published lab records that do not replay bit for bit on this platform, as `tests/envcheck.py` documents); frontend `329 passed, 1 skipped`. |
| **TO-C1** | **not in the repository, in any other project folder on this machine, or in any document searched.** The only description of it is the request itself. |

## 2. What was added

* `frontend/src/views/ecosystem/xenoscience.ts` — pure readings over a record and over the engine's own `observe()` result.
* `XenosciencePane.tsx` — a new tab **XENOSCIENCE** of the Ecosystem view (`?tab=xenoscience`). Pinned regime state lives in `EcosystemView.tsx`, so it survives tab changes.
* `ecosystem.css` — styles for the pane; the tab bar now wraps so that eight tabs are all reachable.
* Tests: `xenoscience.test.ts` (27), `XenosciencePane.test.tsx` (11), `backend/tests/test_xenoscience_integration.py` (11). Fixtures are real engine output (`__fixtures__/meos-stage2-observed.json` is `observe()` of the stage-two record).

### Readings (all read from the record; none computed by the interface)

1. **Operational shape inspector** — for the selected entity at the playhead tick, three groups kept apart:
   *OBSERVED* (what the configured observation array recorded), *INFERRED* (observability status, limiting parameters, path activity: declared analytical procedures),
   *REFERENCE* (the evaluator's internal state: stimulus, baseline, threshold, energy, position, power reserve, operational status, true cycle count). The class of every source is one table, `READING_SOURCES`, and is tested. When no observation result exists the observed and inferred readings say **unresolved** and why (full-resolution observation requests none).
2. **Observation regime comparison** — pin the current observation, change the regime, run again: five kinds of change reported apart (target, apparatus, recorded representation, inferential classification, effective intervention possibilities). The last is always UNRESOLVED: the engine has no operation that tests it. A changed record with an identical target is labelled an observation difference, not a new real entity.
3. **Intervention provenance** — engine and schema, seed, initial-configuration, result, trace and full digests, termination, and every requested intervention matched to the engine's own log row (event id) with the first status change after it.
4. **Critical intervals** — formation, observation, loss of effective access, cessation, re-ignition derived from the status log and the observation timeline; evidential warrant, scientific attribution and material continuation are **UNSUPPORTED** (not modelled). Intervals are listed, not sequenced; a lost observation is not a cessation (tested).
5. **Five-S** — scale, size, speed as engine controls; structure as an arrangement; sensitivity as a measurement (from the SSS classification when one exists).
6. **Human mediation** — six kinds kept apart, no score: continuing decisions, energy supply, maintenance and fabrication, human-readable interpretation, institutional approval, inherited variables. `power.infinite` is reported as *assumed away*, not as independence.
7. **Strong Xenoscience** — the four jointly necessary conditions with evidence statuses. In a simulator run none can be SUPPORTED, so the joint classification is NOT ESTABLISHED; no score.

### What is verified

* The API gives the same record as the engine called directly (4 intervention lists, all digests and frames).
* An observation configuration does not change the run (digests and frames identical, 3 configurations); observed cycles never exceed the cycles the run contains.
* A request the engine refuses (unknown operation, unknown target) leaves no record.
* In the running app (preview `xeno-3d`, port 3051): the tab renders from a live run of the engine with no console errors; pinning a regime of sampling interval 12, changing it to 3 and re-running gives *target UNCHANGED (digest 91b7a9cb both), apparatus CHANGED, record UNCHANGED (0 of 28 cycles in both), classification UNCHANGED, intervention possibilities UNRESOLVED*.

## 3. Not done, and why

* **TO-C1 scene (Stage C): blocked.** The original code, inputs and expected outputs were not found (see section 4: `toc1.zip` was announced twice and has not reached this machine). The figures in the request (729 words, six conditions, nine ticks, 4,374 executions, 490 / 270 / 432 / 162) are not reproduced and no substitute model was written: a model built to hit those numbers would be a different, unverified model. When the original is supplied, the scene belongs in a new `views/ecosystem/` module that reads its output, with the numbers asserted as tests.
* **Stage D (controlled interventions).** The existing console already sends interventions to the engine; this work adds the provenance reading and the equality tests above. A trace of *rejected* requests is not kept (the engine refuses them before a run exists; the console shows the error).
* **Stage E.** Observation regimes can be compared; replay and the MEOS history controls already exist. The four-way distinction retention / addressability / re-entry / effective consequence is not added as a separate interface: MEOS records `history_reentry` cycles only, and no source criterion for the other three was supplied.
* **No new 3D scene, exploded view, or new renderer** was written: the existing three.js scene is the 3D workspace. Rendering performance was not re-measured for this change (the pane is DOM only; the headless overlay reported 43–55 fps, 18–23 ms at the time of the check, which is not a benchmark).
* The interface classes (observed / inferred / reference) are *this implementation's* reading of what the MEOS observer has access to (complete cycles through the observation array). It is a declared rule, not something the engine labels.
* No change to the engine, to experiment schemas or to saved records. Outside this repository, a `xeno-3d` preview entry (port 3051) was added to `/Users/user/Desktop/BIM/.claude/launch.json` to run the checks above.

## 4. Continued implementation (2026-11-02): the 3D coupling scene

### TO-C1 and the other candidate experiments
* `toc1.zip` (SHA-256 `ab3c32c9…cbf6`) was announced twice. `/Users/user/Downloads/toc1.zip` does not exist; no file named `toc1*`, no zip with that digest, no `coupling_study.py`, `xenosnn_supplement.py` or `xenosnn_reference.py` exists on this machine, and no commit in the history contains the source (the history hits for the string are this work's own commit). **No number of TO-C1 is shown or reproduced.** `experiments.ts` lists it as `SOURCE_MISSING` with no capability, and the pane shows it that way; the adapter is added as one more registry entry once the original is verified against its archived summary.
* Checked against the code (not against descriptions): MEOS has a live engine with coupling cut/restore (`ISOLATE`/`RECONNECT`), routes and reconfiguration, observation regimes and the `phil` revision modes; Operational Resolution Escalation exists as stored results (`backend/xzr/experiments/escalation`); the multi-system laboratory has its own engine and scene; XenoSNN exists only as a stored replay fixture (`backend/xzr/lineage.py`), no simulation. The first experiment brought into the 3D scene is the MEOS coupling cut.

### What was added
* `couplings.ts` (pure): the four couplings and the engine component behind each (`sensor_resource`, `interaction_channel`, `sensor_alteration`, `feedback`); their state per tick read from the record (`ad.connectivity`); the cut request (`ISOLATE` + `RECONNECT`); branch comparison (first tick at which the recorded state / the status differs, final status, cycles, added interventions); baseline positions; and what produced the record on screen (new engine run / verified replay / differing replay / stored experiment).
* `couplings3d.ts` (three.js): a pickable mesh per coupling in the existing arena. State → appearance (connected: opaque; cut: thin, translucent, red; unrecorded: grey). Display operations that run nothing: coupling layer on/off, isolate the selected coupling, exploded view (layers separated by a schematic lift), baseline markers (the baseline run's recorded cells at the playhead tick). The heights, sideways offsets and the lift are **schematic layout offsets**, not physical dimensions. In MEOS-0, A2 moves to A1's cell by tick 3 and stays there, so the couplings are drawn along fixed schematic directions at that cell for most of a run.
* `EcosystemView.tsx`: a click on a coupling selects it and opens XENOSCIENCE; `REQUEST CUT AT TICK t` sends the baseline's interventions plus the cut to `/api/meos/run`, keeps the baseline record, and replaces the record on screen with the engine's result; the 3D scene, the status strip, the couplings table, the provenance table and the branch comparison all read that one record. `?coupling=<component>` selects a coupling from a link (nothing is run). `window.__meos.couplingScreen(id)` (read-only) reports a coupling's screen position for checking picking.
* `experiments.ts`: the registry of experiments and their real states. `XenosciencePane.tsx`: the sections above, the origin line (a new run vs a replay vs playing a record back) and the experiment table.
* Tests: `couplings.test.ts` (16), `couplings3d.test.ts` (10), `experiments.test.ts` (5), `XenosciencePane.test.tsx` (16, with the earlier ones). Fixture `meos-coupling-cut.json` is real engine output (baseline, interaction channel cut at 100 and restored at 150, feedback cut at 100; digests `4b08c75a`, `ca6b0a84`, `e395635a`).

### Verified in the running app (local runtime, preview `xeno-3d`, port 3051, no console errors)
* Clicking the horizontal coupling arrow in the 3D scene selected `interaction_channel` and the pane showed its engine component, role and the dependency the engine names when it is cut.
* `REQUEST CUT AT TICK 120` for 50 ticks ran the engine: baseline ACTIVE, result digest `4b08c75a…` (identical to a direct engine run); branch COLLAPSED at tick 169, 24 cycles against 71; records first differ at tick 120, status first differs at tick 146; the coupling reads `cut` at tick 120 and 140 in the table and is drawn translucent and red in the scene.
* The exploded view was checked on screen with the camera focused on the selected coupling (feedback, tick 200): assembled, the coupling arrows overlap the configuration; exploded, the couplings and the configuration are lifted apart in separate layers. Its transforms are also unit-tested (lift, return without drift, picking).

### Rendering performance (measured, not estimated)
The existing uncapped benchmark (`window.__meos.benchmark`, frames rendered back to back with the display rate removed), 120-150 frames per sample, balanced tier, habitat camera, software/driver as the preview provides. Five interleaved pairs with the coupling layer shown and hidden: median frame time shown 9.2-10.9 ms, hidden 10.2-11.1 ms; p95 13.1-16.1 ms and 13.1-16.6 ms. The layer adds 10 draw calls (235 against 225) and about 1,100 triangles (837,024 against 835,888). **No cost is measurable beyond noise** (the pairs run in the layer's favour, which a layer cannot cause; it is order drift). The simulation-update figure in the HUD stayed 2-4.6 ms. This is one machine and one camera; it is not a benchmark of other devices, and rendering was not measured on a low-power GPU. On-screen fps values read while the pane was hidden (one read "0 fps") are not valid and are not used.

### The timeout of the previous report (investigated)
The failing test was `assemblies.test.ts` "no two sensor heads, hubs, remote sensors or stores overlap" (6,153 ms against 5,000 ms) in a full frontend run beside the backend suite. The file is unchanged since M8.2 and does not import the ecosystem code. Measured: 0.5 s alone (3 runs); 1.0-1.1 s with every one of the 8 cores busy; 2.0-2.7 s in four full frontend runs beside the backend suite (all 397 tests passed in those four). The failure did not recur, so it is an intermittent tail of a load-sensitive test, not a regression and not something the last change caused. What was wrong is the limit: four sibling tests that do the same work (load published records, build high-tier labs) carry an explicit 60 s limit; this one alone had the 5 s default. It now has the same 60 s limit with a comment holding these numbers. This is a change to a limit with the evidence stated, not a hidden slowdown; if the test's 0.5 s ever becomes seconds without load, that is a regression to look for, and the comment says what the baseline is.

### Regression results (2026-11-02/03, this Mac, after all changes of this section)
| Suite | Before (baseline) | After |
|---|---|---|
| Backend (`pytest`, whole suite, 26 min) | 1092 passed, 3 skipped | **1103 passed, 3 skipped** (the 11 new tests of `test_xenoscience_integration.py`; no failure, no skip added) |
| Frontend (`vitest run`, whole suite, run twice with the backend suite finished) | 329 passed, 1 skipped (start of the first stage) | **403 passed, 1 skipped**, both runs |
| Frontend beside the backend suite (the condition of the earlier timeout), 4 runs | - | 397 passed, 1 skipped each (before the last tests were added) |
| `eslint .`, `tsc -b` | clean | clean (exit code 0) |
| `vite build` (local), `VITE_STATIC=1`, `VITE_WEBRT=1` | - | all build; the static and browser builds contain no coupling, Strong-Xenoscience or experiment-registry code |
The three warnings of the backend run are the published lab records that do not replay bit for bit on this platform (documented in `tests/envcheck.py`), as in the baseline.

### Not done / unsupported
* TO-C1 (all of it): the three demonstrations, source reproduction and archived-state scene need the original package.
* Interventions other than the coupling cut are not requested from the scene (route, reconfiguration and repair stay in the RESEARCH tab).
* The four-way distinction retention / addressability / re-entry / effective consequence is not drawn: MEOS records re-entry cycles only (`history_reentry`), and no source criterion for the other three was supplied. Replay is shown as what the engine did (re-executing a record's inputs and comparing the digest), never as historical re-entry.
* The scene shows the formation, maintenance, lapse and re-ignition of the operation through the status label and strip, the coupling states, and the critical-intervals table; there is no separate animated object for them, because the engine has no state that such an animation could depict.
* Entities other than A1 and A2 (sensors, the body set, the observer array, technical sheets) are the existing scene's, not rebuilt.
* No production change: nothing was deployed or pushed.
