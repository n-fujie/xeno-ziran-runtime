# Post-Active-Inference benchmark

An experimental layer on top of the existing runtime (`backend/xzr`). It tests one hypothesis: **Active Inference
is a high-resolution description of a restricted operational interval rather than a universal description of
adaptive dynamics.** It asks:

1. where an Active-Inference-compatible description is sufficient;
2. where its descriptive units (agent, boundary, generative model, latent state, prediction error, free energy,
   policy) become unstable;
3. whether operational differentiation, intervention, recovery, history dependence and reconfiguration stay
   trackable before, during and after that point.

It is not built to "defeat" Active Inference, and no conclusion is hard-coded. Every label and status comes from
a measured rule documented in the code and in [REPORT.md](REPORT.md).

**What was reused, and what was added:** see [IMPLEMENTATION_GAP.md](IMPLEMENTATION_GAP.md). The runtime is used
unchanged as the world and perturbation engine; nothing in `backend/` was modified. The Active Inference math is
vendored verbatim from the sibling repository `ziran-xeno-simulator/embodied/active_inference` (commit recorded in
`pai/aif_vendor.py`; a test compares it with the sibling copy).

## Design in one page

* **World.** `topology("modular", n=1500)` driven by `Engine`, with the cached calibrated gain. Control starts after
  the connection pool has saturated (t ≥ 1000), i.e. in the steady state.
* **Interface (Markov-blanket proxy).** The target region T is one module. Six sensor channels read T's ignition
  rate. The actuator applies five actions to T: noop, damp (threshold × 2.5), excite (× 0.4), shield (inbound
  permeability 0.2), pulse (inject difference). Both controllers use exactly these sensors and this actuator.
* **Task.** Keep T at a goal activity level. The goal alternates between levels 1 and 3 (of five calibration
  quantiles) every 100 steps, so no world's resting level satisfies it by itself.
* **Controllers.**
  * `aif_fixed`: discrete Active Inference with A and B from calibration, frozen.
  * `aif_adaptive`: online Dirichlet learning plus a surprise-triggered structural rebuild (structure-learning-lite;
    conditions it handles count as overlap, not novelty).
  * `ost`: model-light measured-effect rule on the raw reading.
  * `none`: always noop.
  * Ablations of the adaptive comparator, for the non-redundancy tests.
* **Tracker.** `pai/tracker.py` describes the field from the runtime's step records alone: local and transition
  differences, coupling change, persistence, recurrence, split and merge events, reachable-state change, re-ignition,
  change detection, localisation and propagation depth. A sensor-only variant sees exactly the comparator's channels,
  which separates descriptive form from information access.
* **Perturbations.** 47 subtypes in 8 families (boundary, topology, sensor, variable, memory, coupling, temporal,
  structural), plus 9 aliases and 3 documented non-implementations (`pai/perturbations.py`). Each subtype has a
  severity in [0, 1], a deterministic seed and three phases:
  * pre: 3000–3200;
  * perturbation: 3200–3500;
  * recovery / reconfiguration: 3500–3800.

  Each run saves a per-decision trace.
* **Paired design.** For every seed, all runs share the world, the engine stream and the warm-up + calibration prefix.
  The prefix is simulated once and deep-copied, which is bit-identical to simulating it per run (tested). Severity 0
  is the control, and a noise replicate (engine seed + 1000) gives the noise floor.
* **Regime classifier.** `regime_classifier.py` computes five stability scores against the paired control and noise
  replicate: sensor map, model validity, latent-variable adequacy, boundary footprint, policy identity.
  `C_AIF` is their minimum:
  * ≥ 0.8 → ACTIVE_INFERENCE_COMPATIBLE;
  * < 0.5 → POST_ACTIVE_INFERENCE;
  * otherwise TRANSITION.

  Whether tracking survives is measured separately and never feeds the label.
* **Non-redundancy.** `nonredundancy.py`: paired ablations per regime with sign-flip tests and Holm correction.
  Each element is labelled NON-REDUNDANT, REDUNDANT, HARMFUL or UNRESOLVED.
* **Statistics.** `pai/stats.py`: bootstrap CIs, paired sign-flip tests (the runtime's `sign_matrix`), effect size
  d_z, Holm correction, threshold crossings with bootstrap uncertainty and per-seed robustness.
* **Failures.** All failures are recorded, never discarded (`results/<stage>/failures.json`). Categories:
  simulator, numerical, benchmark, comparator, model-structure, controller, and genuine regime transition.

## Running

From this directory, with the repository's virtual environment:

```bash
../../.venv/bin/python -m pytest -q tests
```

```bash
../../.venv/bin/python run_benchmark.py plan configs/dev.json
```

```bash
../../.venv/bin/python run_benchmark.py run configs/dev.json
```

```bash
../../.venv/bin/python run_benchmark.py analyse configs/dev.json --publish
```

```bash
../../.venv/bin/python run_benchmark.py refine configs/dev.json
```

* `plan` reports hardware, free RAM, job count and a cost estimate. Worker count is capped by CPU count and free
  memory.
* `run` is resumable: every finished cell is written atomically to `results/<stage>/jobs/<seed>/<cell>.json` and
  never overwritten. A new manifest is written for each invocation.
* `analyse` writes the results files into `results/<stage>/`. `--publish` also writes them to `results/`.
* `refine` writes `configs/<stage>_refined.json`, which adds severities near observed crossings (adaptive
  refinement). Run it, then `run` the refined config into the same stage directory.

| stage | config | seeds | severities | runs | status |
|---|---|---|---|---|---|
| 1 smoke | `configs/smoke.json` | 3 | 0.5, 1.0 | 1,338 | done (pre-revision design; not pooled) |
| 2 development | `configs/dev.json` | 10 | 0.25–1.0 (4) | 9,120 | done (0 aborted) — [REPORT.md](REPORT.md) |
| 3 research (confirmatory) | `configs/research.json` | 30 (seeds 11–40) | 0.125–1.0 (8) + 48 refined points | 55,680 | done, 0 aborted — [REPORT_RESEARCH.md](REPORT_RESEARCH.md), pre-registered in [PREREGISTRATION.md](PREREGISTRATION.md) |

## Outputs

`results/summary.json`, `run_manifest.json`, `failures.json`, `main_results.csv`, `thresholds.csv`,
`cell_scores.csv`, `nonredundancy.json` / `.csv` (published copies of the development stage), and
[REPORT.md](REPORT.md).

## Scope and claim discipline

These are measured differences inside one simulated runtime, with one task and one comparator family. They are
not evidence about brains, organisms or any system outside the simulation. "Post-Active-Inference" names a
measured regime (the comparator's primitives no longer hold stably), not a metaphysical claim.
