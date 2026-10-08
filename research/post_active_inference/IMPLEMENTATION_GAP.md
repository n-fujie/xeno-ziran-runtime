# Implementation gap — Post-Active-Inference benchmark vs the existing runtime

Inspection date: 2026-10-07. Repository `xeno-ziran-runtime` at HEAD `2634e69` plus uncommitted v0.2.0 work (measured
as-is, nothing in `backend/` was modified for this layer). Paths below are relative to `backend/xzr/` unless they
start with `research/` or name the sibling repository.

**Main finding.** The runtime is a strong *world and perturbation engine*: topology, memory, coupling, gating,
cut, reconnect, mutation, history operations, fork and checkpoints all exist, along with paired-seed statistics. The
runtime has **no agent, sensor, actuator, generative-model or policy concept**. It is agent-free by design
(`runtime/state.py` docstring: "It carries no human-readable category of what a configuration 'is'"). The only
Active Inference code in the project family lives in the sibling repository `ziran-xeno-simulator`:

* `embodied/active_inference/` (Python): a discrete A/B/C/D/E model, posterior inference, VFE, EFE (pragmatic +
  epistemic) and softmax policy selection, bound to a MuJoCo Walker2d body;
* `comparison/worlds/w1…w5` (TypeScript): synthetic worlds that include W2 *too-late correction*.

Neither is wired to this runtime. The benchmark layer therefore has to add exactly these pieces:

* an observation/actuation interface (Markov-blanket proxy) over the runtime;
* a comparator that reuses the sibling's AIF math;
* a model-light controller and tracker;
* the perturbation scheduler;
* metrics, the regime classifier, ablations and the run/analysis driver.

## A. ALREADY SUPPORTED

| spec item | where (file → function/class) | how the benchmark uses it |
|---|---|---|
| main simulator entry point | `runtime/engine.py` → `Engine.step`, `Engine.run`; `__main__.py`/`cli.py` (`xzr run`) | world dynamics; one `Engine` per run |
| world/state representation | `runtime/state.py` → `State`, `Params`, `allocate`, `fingerprint` | read-only for tracking; perturbations write only through the paths below |
| topology representation + generators | `runtime/state.py` (`src`, `dst`, `alive`, `weight`, `gate`); `scenario/topologies.py` → `topology()` (`modular`, `multi_region`, `bottlenecked`, …), `TOPOLOGIES` | world = `topology("modular", …)`; its 16 module sets give the target region and its neighbours |
| gain calibration | `scenario/topologies.py` → `calibrate_gain`; cache `experiments/results/resolution/calibration.json` (`modular\|1500`) | reused read-only (gain 3.235) |
| memory representation | `State.memory`, `mem_decay`, `mem_coupling`, `theta_eff()`; `runtime/ops.py` → `remember` | memory perturbations write `state.memory` (same convention as `experiments/history.py`) |
| memory regimes | `scenario/topologies.py` → `MEMORY_REGIMES`, `apply_memory_regime` | available; the first comparison keeps the default regime |
| coupling controls | `Params.gain`; `runtime/intervention.py` → `Gate` (permeability), `ScaleThreshold` | coupling and boundary perturbations; controller actions |
| perturbation interface | `runtime/intervention.py` → overlay items (`ScaleThreshold`, `Gate`, `MemoryCondition`, `Freeze`, `Mutation`) and actions (`Sever`, `Connect`, `SetThreshold`, `Inject`); `Engine.set_overlay`, `Engine.apply`, `Engine.base_overlay` | world perturbations go into `base_overlay` or actions; controller actions go into `overlay`, so neither overwrites the other |
| cut / reconnect / disconnection / reconfiguration | `runtime/ops.py` → `cut`, `sever`, `add_connection`, `disconnect`, `reconfigure`, `reconfigure_by_mutation`, `mutate`, `redirect_random` | topology and structural families (edge deletion, addition, rerouting, reconnect) |
| dynamic topology mutation | `intervention.Mutation` + `ops.mutate` | `topology.dynamic_mutation` |
| history fork | `Engine.fork` (exact continuation), `Engine.snapshot/restore/rewind` | counterfactual action probes (ground-truth policy→effect map, boundary footprint) |
| history removal / reactivation / migration | `experiments/history.py` → `seed_job` (`remove`, `reactivate`, `migrate`) | the same operations are applied inside the benchmark schedule (re-implemented on the run's own engine; semantics copied, cited) |
| delayed re-entry | `experiments/history.py` (`reactivate_at`); `scenario/topologies.py` `RETURN_STRUCTURES` | `memory.history_reactivation` with a delay set by severity |
| boundary changes between clusters | `experiments/escalation/harness.py` → `_apply_world_event` (`open`/`close`/`unstable`) | the pattern (gating cross-cluster connections) is reused for `coupling.temporary_decoupling` and `temporal.world_drift` |
| multi-cluster structure | `scenario/topologies.py` module sets; `lod/hierarchy.py` → `build_hierarchy`, `Hierarchy.resolve` | target region = one module; neighbour module for merge/leakage |
| world-responsive revision (closed loop) | `reasonlab/loop.py` → `ReasonLoop`; `reasonlab/triggers.py` → `TriggerSet` | not used as a controller (it revises a support graph, not a predictive model); cited as prior art for closed-loop revision |
| current benchmark harness | `experiments/escalation/harness.py` (`run`, `seed_job`, paired reference / noise replicate `C~`), `escalation/runner.py` (`run_conditions`, persisted jobs, resume) | design copied: paired control + noise replicate per seed, persisted per-job results, resume by skipping finished jobs |
| seed handling | `harness.NOISE_OFFSET = 1000`; generator seed vs engine seed separation (`REFERENCE["gen_seed"]`) | same convention: world fixed by `gen_seed`; engine seed per run; noise replicate = seed + 1000 |
| result serialisation + provenance | `escalation/runner.py` → `provenance()` (version, git HEAD, dirty flag, code hash, Python, numpy); `results.py` → `execute` | `provenance()` is called and extended with machine, dependency versions and the configuration hash |
| paired statistics | `experiments/escalation/stats.py` → `sign_matrix` (exact ≤ 14 seeds, Monte Carlo above), `maxt_test`; `experiments/history.py` → `sign_flip_p`, `assess` (DETECTED / EQUIVALENT / UNRESOLVED) | `sign_matrix` is reused for the paired sign-flip tests; the three-way status logic is copied |
| reachability metrics | `shapes/metrics.py` → `transition_graph`, `horizon_reach`, `closure_reach`, `fragmentation` | tracker: reachable-state change from the target region |
| re-ignition, recurrence | `shapes/detector.py` → `ShapeDetector` (`QUIET_GAP = 20`, `reignitions`, `_recurrence`) | tracker uses the same re-ignition definition (`QUIET_GAP`) |
| intervention response | `experiments/history.py` (`intervention_response`); `compare/trajectory.py` → `response_vector` | ground-truth policy→effect map by forked probes (same "with minus without" definition) |
| compression of long runs | `experiments/escalation/compression.py` (`kmeans`, `lz78_phrases`) | not needed for the first comparison |
| determinism | `Engine` docstring; `fingerprint`; test `test_fork_is_independent_and_identical` | every run is seeded; the benchmark adds its own determinism test |

## B. PARTIALLY SUPPORTED

| spec item | what exists | what is missing → minimum addition |
|---|---|---|
| Active Inference comparator | sibling `ziran-xeno-simulator/embodied/active_inference/`: `state_inference.posterior`, `state_inference.vfe`, `expected_free_energy.efe` (pragmatic + epistemic), `policy_selection.select`, `generative_model.GenerativeModel` (Walker2d-specific A, Dirichlet-learned B) | Not importable here: it lives in another repository and its model is tied to a body. **Addition:** `pai/aif_vendor.py` vendors the four math functions verbatim, records the source commit, and a test checks them against the sibling copy when it is present. `pai/controllers.py → AIFController` builds a world-specific A/B/C/D/E (Dirichlet A and B from a calibration phase) and adds what the spec requires but the sibling lacks: online learning, a surprise-triggered structural rebuild (adaptive variant), prediction logging, failure counters |
| observation level variation | `shapes/multiscale.py` → `MultiScaleObserver` (five fixed resolutions) | No experimental observation map. **Addition:** `pai/world.py → SensorArray` (configurable channels over node sets, with dropout, reassignment, delay, noise, window and scale controls) |
| sensor / observation perturbation | none in the runtime (capability report: "sensor addition/removal: ABSENT") | **Addition:** sensor family in `pai/perturbations.py`, acting on `SensorArray` only; world dynamics untouched |
| variable-set changes | feature sets fixed (`harness.GLOBAL_KEYS`, detector `FEATURES`) | **Addition:** variable family (reading remap, fold relabel, coarsening, duplication) on the observation map; latent split/merge realised in the world (split or merge of the target region) |
| temporal-window changes | horizon varies; analysis windows fixed (`harness.WINDOWS = 40`) | **Addition:** decision-interval compression/expansion, sensor window mismatch, observation delay, asynchronous channels, actuation delay |
| correction latency / too-slow correction | sibling TS world `comparison/worlds/w2-too-late.ts` (synthetic, not this runtime) | **Addition:** `temporal.interface_drift` and `temporal.world_drift` with change period set by severity; metric `staleness` |
| configuration-crossing recurrence | `experiments/history.py` `migrate` (destination ignitions); detector recurrence events | No measure of recurrence of a *pattern* across configurations. **Addition:** tracker `pattern_recurrence` (correlation of the pre-perturbation activity profile with the post-reactivation/migration profile) |
| checkpoint / restart | `Engine` checkpoints; `escalation/runner.py` persisted jobs + resume | Copied pattern: one JSON per finished job under `results/jobs/`, skipped on resume, never overwritten |
| cross-configuration robustness | `results.py → configuration_sensitivity` over listed conditions | Severity sweeps per perturbation subtype, plus adaptive refinement near crossings (`run_benchmark.py refine`) |
| split / merge events | detector `fragmentation`, `components` (graph series) | Counts only, no event matching. **Addition:** tracker matches active components between windows (Jaccard) to emit split and merge events |
| statistics | sign-flip / max-T, t intervals | No bootstrap CIs, effect sizes, Holm correction or threshold estimation. **Addition:** `pai/stats.py` |

## C. MISSING

| spec item | minimum addition (file → symbol) |
|---|---|
| agent / environment partition, boundary (Markov-blanket proxy) | `pai/world.py → BenchWorld` (target region T = one module; sensory channels on T; actuator set U = T; environment = the rest). Boundary perturbations act on the actuator mapping (`Actuator`) |
| latent-state ground truth | `pai/world.py → BenchWorld.true_level` (the target region's mean ignition rate over the decision interval, binned with edges calibrated in the pre-phase) |
| policies / action interface | `pai/world.py → ACTIONS` (noop, damp, excite, shield, pulse), compiled to runtime overlay items / actions on U |
| operational-shape tracker (model-light) | `pai/tracker.py → OperationalTracker` (local differences, transition differences, coupling change, persistence, recurrence, split/merge, reachable-state change, propagation depth, re-ignition, change detection, localisation, reconfiguration magnitude) |
| model-light controller | `pai/controllers.py → MeasuredEffectController` (raw reading; recency-weighted measured effect per action; no bins, latent states or transition model) |
| perturbation scheduler with severity, phases, seeds, traces | `pai/perturbations.py → REGISTRY`, `Perturbation`; phases pre / perturbation / recovery fixed in the config |
| ground-truth probes (policy identity, boundary footprint) | `pai/world.py → probe_effects` (forks the engine; per action, the effect on T against noop) |
| adversarial differentiation, independent re-detection | out of scope for the first comparison; still MISSING |
| compression / expansion as perturbations | `structural.compression` is not applicable to a fixed-N engine: MISSING. "Expansion" is realised only as a region merge (alias, flagged) |
| metrics (predictive, intervention, recovery, structural, historical, operational, speed) | `metrics.py` |
| regime classifier with continuous scores | `regime_classifier.py` |
| non-redundancy (ablation) tests | `nonredundancy.py` + ablation flags in `pai/controllers.py` |
| failure taxonomy | `pai/episode.py → classify_failure`; `results/failures.json` |
| run driver, manifest, resumability, adaptive refinement | `run_benchmark.py` (`plan`, `run`, `analyse`, `refine`) |

## Information-access note (fairness, decided before any result)

* Both controllers (AIF and model-light) receive **the same sensor channels** and act through **the same actuator
  interface**. Sensor, variable, boundary and temporal perturbations therefore hit both equally.
* The descriptive tracker reads the full delta stream and the current graph; the AIF comparator reads only its
  sensors. Any tracker-vs-AIF difference in *detection* or *localisation* is therefore confounded with information
  access. The benchmark reports a `tracker_sensor_only` variant that sees exactly the AIF's channels, so the
  descriptive form can be separated from the information advantage.
