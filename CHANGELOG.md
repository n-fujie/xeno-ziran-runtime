# Changelog

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
