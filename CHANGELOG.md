# Changelog

## Unreleased — XENO ECOSYSTEM, second stage (MEOS-0, engine meos-0.2)

* Engine: intermediate traces and causal paths (separate block and digest; the status never reads them), operational / observed / observability status with five observation parameters, optional M2 sensing,
  per-entity history access, renewal efficiency, Address Domain interventions, first-stage Philosophical operations (expression, scorekeeping, norm-sensitive revision, inference, correction) as operational couplings.
  Every new feature is absent from the default configuration: the baseline result digest is unchanged.
* Experiments (`docs/ECOSYSTEM_MEOS_STAGE2.md`, `docs/ecosystem/experiments_stage2.json`): history x gradient x power, where history is necessary, all minimal operational configurations (full 2^9 search),
  XenoBody boundaries, collapse / recovery phase, SSS phase regions, Address Domain, M2 connection, Philosophical operations. Null, seed-dependent, context-reversed and non-monotone results are recorded as found.
* Interface: observation controls, connections, a STUDIES tab, trace charts, ADDRESS interventions, a research-device layer in the scene (observation array aim and coverage, boundary posts, pulse ring, recovery halo,
  Philosophical module in an expansion bay), two camera presets, truss arches. Extended image statistics for the captures; visual similarity to the references remains partial.
* Graphics pass (`docs/ECOSYSTEM_MEOS_STAGE2.md` section 9): displaced wet-rock terrain with gravel and reflective puddles, a dark studio reflection environment, bloom / vignette / grain and a high-tier depth of field,
  two experimental bodies modelled on supplied concept renders (perforated plates, bolts, cable bundles, an actuated observation arm) whose lamps, probes, cable lights and arm answer to the record through a tested pure mapping.
  Visual similarity to the new references is improved in tone and large-scale structure and **not** in fine structure; the balanced tier no longer holds 60 fps in the heaviest views (16-60 fps headless GPU across tiers).
* Not integrated: R3 (a separate branch), live engine stepping, any connection to XenoBody / Ziran System / Xenoscience / a language-model Philosophical AI.

## Unreleased — XENO ECOSYSTEM (MEOS-0)

* New view `ecosystem` (local runtime only): a real-time 3D megastructure organised like the XENOSCIENCE drawing around a deterministic simulation of MEOS-0, the first
  Minimal Ecosystem Operational Shape experiment (`docs/ECOSYSTEM_MEOS.md`). New self-contained layer `backend/xzr/meos/` (engine, reduction experiments), stateless API
  `/api/meos/*`, the view `frontend/src/views/ecosystem/`, 34 new backend and 26 new frontend tests, capture and comparison scripts, recorded experiments
  (`docs/ecosystem/`). The only changes to existing files are the view registration, one i18n label, the layering declaration, the security route enumeration and lint settings.
* MEOS status (ACTIVE / DEGRADED / COLLAPSED) is derived from counted cycles of a causal chain, never from animation; ablation, the minimal operational configuration,
  XenoBody boundaries, history re-entry, SSS and Address Domain perturbation and observation-dependent status are run on the real engine and recorded with digests.
* Not implemented: the philosophical-AI connection; live engine stepping (playback is of a deterministic record); a pixel-difference visual gate. See section 9 of the document.

## Unreleased — browser edition

* The interactive simulator runs in a browser tab at `/app/` of the public site: the engine on Pyodide (CPython on
  WebAssembly, numpy + pydantic) in a Web Worker, same in-process interface as the iOS app, no simulation server
  (`docs/WEB_RUNTIME.md`; `backend/scripts/export_web_runtime.py`, `npm run build:web`).
* Cooperative sessions for hosts without threads: `Session.pump`, `run_deferred`, `bridge.tick`; branch comparisons are
  generators (`compare_steps`) advanced in time slices, so the live simulation keeps running during a comparison. The
  threaded path (desktop, iOS) is unchanged; `compare()` drives the same generator straight through.
* `_compat` index arrays use `np.intp` (32-bit on WebAssembly); `resource` is optional; reference hierarchies for the two
  10,000-node benchmarks; `XZR_MAX_NODES_COMPUTED_HIERARCHY` refuses graphs whose hierarchy would need the cubic dense
  eigensolver (browser: 1,500).
* Measured and documented: the browser engine is structurally identical to the desktop and numerically equal to ~1e-13 over
  1,000 steps, not bit-identical (WebAssembly math library, summation order); a browser-specific golden guards replay.

## Unreleased — Heterogeneous Philosophical Operations (HPO)

* New experiment layer `backend/xzr/hpo/` (nothing in the runtime, shape, LOD, compare, scenario, practice, reasonlab
  or service layers changed except the integration points listed in docs/HPO_VERIFICATION.md). It contains:
  * a Philosophical Operational Registry with source status, approximations, and failure / revision conditions;
  * instruments that separate what an operation can observe from the world's true state, with six unobservability
    reasons that are never read as zero;
  * six operational series;
  * a Configuration / Ignition Engine and an Interaction Engine (sharing, transformation rules, observation change,
    competition, coupling / splitting / reclassification, closure filter, history reinsertion);
  * a causal execution history with before / after state;
  * sandboxed recursive reconfiguration (HPO-003).
* `xzr hpo registry | run | verify`; `/api/experiments/hpo-<name>`; viewer section "Heterogeneous Philosophical
  Operations" (`?view=hpo`, also in the static mirror).
* Frozen protocol docs/HPO_PROTOCOL.md (SHA-256 pinned). Results: HPO-001 (re-specified, because the pilot archive
  was unavailable), HPO-002 (360 seeds, 10,440 paired comparisons, plus generalization) and HPO-003. See
  docs/HPO_RESULTS.md; regression and verification in docs/HPO_VERIFICATION.md.

## 0.2.0 — research toolkit release

* `xzr` command (`run`, `validate`, `presets`, `compare`, `export`, `study`, `--version`), installed as a console
  script; `python -m xzr` works from a source checkout.
* Five experiment presets with documented question, manipulated / fixed variables, measured outputs and what they
  do not show: `resolution-escalation`, `history-reentry`, `boundary-scale-window`, `ablation`, `smoke`.
* Result schema `xzr.result/1`: effective configuration, seeds, provenance (version, code hash, git commit and
  dirty flag in a source checkout, Python / numpy), per-condition statuses, warnings, failures; runs never
  overwrite and write only their own directory (the published calibration cache is read, not written).
* History operations on retained memory (`xzr/experiments/history.py`): fork, removal, additive reactivation,
  migration; paired sign-flip statistics against a noise branch; an HRGI-style verdict only when retained prior
  difference, re-addressability, actual re-entry and downstream difference are all measured.
* Comparison of runs labels status cells as same / changed / newly detectable / extinguished / missing, and
  configuration sensitivity across conditions; no "novelty" label.
* Configuration validation refuses unknown or misspelt settings; the expanded configuration printed by
  `xzr validate` can be edited and run.
* `run_conditions` takes the first engine seed; `provenance()` records version and does not attribute an
  enclosing repository's commit to an installed copy.
* Post-Active-Inference benchmark (`research/post_active_inference/`, isolated; nothing in `backend/` changed for it):
  a discrete Active Inference comparator (math vendored from `ziran-xeno-simulator`), a model-light controller, an
  operational-shape tracker, 47 perturbation subtypes in 8 families, an empirical regime classifier, ablation-based
  non-redundancy tests, smoke / development / pre-registered confirmatory stages. Confirmatory result (30 seeds,
  55,680 runs): primitive instability replicates for sensor and action-interface disruptions only; where the
  primitives fail, control fails with them — see `REPORT_RESEARCH.md`. Raw per-cell jobs are excluded from version
  control and re-creatable.
* Repository: LICENSE (MIT), CITATION.cff, CI workflow (lint, types, tests, CLI smoke, two-run reproducibility
  check), docs THEORY / EXPERIMENTS / REPRODUCIBILITY, README rewritten for researchers; per-seed raw jobs of the
  long studies (~1.8 GB), run logs and a machine-specific orchestration script are excluded from version control.

## 0.1.0

Runtime, shape detection, practice layer, comparison, LOD service and web interface; primitive reduction,
reasoning non-redundancy and resolution-escalation studies; iOS app on the same engine.
