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

* **TO-C1 scene (Stage C): blocked.** The original code, inputs and expected outputs were not found. The figures in the request (729 words, six conditions, nine ticks, 4,374 executions, 490 / 270 / 432 / 162) are not reproduced and no substitute model was written: a model built to hit those numbers would be a different, unverified model. When the original is supplied, the scene belongs in a new `views/ecosystem/` module that reads its output, with the numbers asserted as tests.
* **Stage D (controlled interventions).** The existing console already sends interventions to the engine; this work adds the provenance reading and the equality tests above. A trace of *rejected* requests is not kept (the engine refuses them before a run exists; the console shows the error).
* **Stage E.** Observation regimes can be compared; replay and the MEOS history controls already exist. The four-way distinction retention / addressability / re-entry / effective consequence is not added as a separate interface: MEOS records `history_reentry` cycles only, and no source criterion for the other three was supplied.
* **No new 3D scene, exploded view, or new renderer** was written: the existing three.js scene is the 3D workspace. Rendering performance was not re-measured for this change (the pane is DOM only; the headless overlay reported 43–55 fps, 18–23 ms at the time of the check, which is not a benchmark).
* The interface classes (observed / inferred / reference) are *this implementation's* reading of what the MEOS observer has access to (complete cycles through the observation array). It is a declared rule, not something the engine labels.
* No change to the engine, to experiment schemas or to saved records. Outside this repository, a `xeno-3d` preview entry (port 3051) was added to `/Users/user/Desktop/BIM/.claude/launch.json` to run the checks above.
