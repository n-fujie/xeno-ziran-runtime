# Simulator Capability Report

Repository `xeno-ziran-runtime` at git `2634e69` **with uncommitted changes** (package version 0.2.0), measured as-is on
2026-10-06/07. No simulator code was changed for this report. The temporary benchmark harness, every raw
measurement and the generator of the machine-readable summary are in `artifacts/capability-benchmarks/`;
the summary is `artifacts/simulator_capability.json`.

Labels: **VERIFIED** (executed and checked), **MEASURED** (executed benchmark number), **NOT VERIFIED** (not
executed), **NOT IMPLEMENTED** (no code path).

## 1. Executive Verdict

**READY FOR MEDIUM EXPERIMENTS**

On this machine (8 GB Apple M1 laptop), MEASURED: single runs up to 2,048,000 configurations (9.8 M connections);
runs of 50,000 steps without memory growth; a 112-seed-job production experiment in 28.6 min with no failure;
deterministic reruns. NOT IMPLEMENTED: generated-observability and adversarial-differentiation experiment
families. Parallel speed-up is limited to ~2–2.5×, a single job exception aborts a run, and `xzr run` cannot resume —
so matrices of several thousand jobs are feasible only as long unattended runs with LOW-confidence estimates.

## 2. Hardware / Environment

| item | value |
|---|---|
| CPU | Apple M1 — 8 cores (4 performance + 4 efficiency), arm64 |
| RAM | 8 GB; swap 3.5–5 GB of 5–6 GB already in use during the benchmarks (other applications) |
| GPU | Apple M1 7-core GPU — **not used**: no GPU code path exists (no torch/CUDA/numba in the code) |
| VRAM | n/a |
| OS | macOS 26.6.2 (25G83) |
| Python / numpy / scipy | 3.12.13 / 2.5.3 (Accelerate BLAS/LAPACK) / 1.18.1 |
| Storage | APFS SSD 228 GiB, **27 GiB free** |
| Limits | 1,333 processes per user, 1,048,576 file descriptors; not a container/VM |
| Background load | other processes used ~2 CPU cores throughout |

All numbers below are indexed to this environment. `OMP_NUM_THREADS=1` (as the project's runners set it).

## 3. Actual Runtime Architecture

Traced execution paths (VERIFIED by reading the code and executing each path):

| component | path / symbol |
|---|---|
| runtime step | `backend/xzr/runtime/engine.py` `Engine.step` → `runtime/ops.py` (inject, ignite, propagate, transform, retain_and_decay, remember, adapt_weights, cut, disconnect, connect, reconfigure, mutate) |
| state | `runtime/state.py` `State`: numpy arrays per configuration (N) and per connection slot (E capacity) |
| world generation | `runtime/generator.py` `latent_geometric`; experiment topologies `scenario/topologies.py` `topology()` |
| observation | `shapes/detector.py` `ShapeDetector.observe` (cheap descriptors every step; graph descriptors via scipy csgraph every 10 steps); five-resolution frames in `experiments/escalation/harness.py` (`scale_values`) |
| hierarchy (addresses, resolutions) | `lod/hierarchy.py` `build_hierarchy` (recursive Fiedler bisection, scipy `eigsh`) |
| experiment unit | `experiments/escalation/harness.py` `seed_job` (reference C + noise replicate C~ + variants, paired) |
| batch / parallel | `experiments/escalation/runner.py` `run_conditions` — `ProcessPoolExecutor`, per-seed jobs persisted as gzip pickles, resumable; `xzr/results.py` `execute` |
| history ops | `experiments/history.py` `seed_job` (fork/remove/reactivate/migrate on `memory`) |
| CLI / config | `xzr/cli.py` (`run`, `validate`, `presets`, `compare`, `export`, `study`); `xzr/presets/` (JSON, validated) |
| seeds | numpy `default_rng(seed)` per engine (`Engine.__init__`), generator seed per world; no global RNG |
| checkpoints | in-run: `Engine._save_checkpoint` (every `checkpoint_every`, max 24, thinned); experiment-level: persisted seed jobs |
| replay | `Engine.rewind` (checkpoint + deterministic replay incl. logged interventions) |
| logging | progress lines to stdout; per-run `summary.txt`, `result.json` |
| GPU / threads / distributed | NOT IMPLEMENTED |

## 4. Scale Parameters

| parameter | default | minimum | maximum enforced by code | practical limit (MEASURED here) | defined in | scales |
|---|---|---|---|---|---|---|
| configurations `n` | 1,500 (harness), 600–10,000 (scenarios) | 100 (presets validator) | 100,000 (presets validator); 500,000 (`service/limits.py` `XZR_MAX_NODES`, web service); **none** for direct `Engine` use | 2,048,000 OK, 4,096,000 unsafe (runtime only) | `harness.REFERENCE`, `presets/__init__.py`, `service/limits.py` | time and RAM ∝ N + E |
| connections `E` | ≈ 4.8 × N alive (mean degree 6.0 generator); capacity ≈ slots allocated | — | `XZR_MAX_EDGES` 32 M (service only) | 9.8 M alive OK | `generator.latent_geometric(mean_degree=6.0)` | time and RAM ∝ E |
| horizon (steps) | 4,000 (harness reference) | 50 (validator) | 100,000 (validator) | 50,000 (session path), 40,000 (harness) OK | `REFERENCE["horizon"]` | time ∝ steps; memory bounded |
| seeds per condition | 12 (reference), presets 2–12 | 1 | 16 (presets validator); harness unlimited (Monte Carlo test above 14) | 16 per condition × 7 conditions OK | `presets.MAX_SEEDS`, `stats.MAX_EXACT_SEEDS = 14` | jobs ∝ seeds |
| variants per seed job | 9–11 (matrix), 3–10 (presets) | must include C | none | 4 (+C~) measured at scale | `condition["variants"]` | job time ∝ variants + 2 |
| reasoning structure size | 32 items | — | — (matrix used up to 2,048) | not measured here | `REFERENCE["size"]` | reasoning cost |
| workers | 4 (`xzr run`), 7 (`xzr study`) | 1 | none | 8 measured; 4 best per worker | `cli.py --procs` | throughput, RAM |
| checkpoints | every 50 steps, max 24 (sessions); 0 in experiments | 0 | `max_checkpoints` 24 | 21 held, bounded | `Engine.__init__` | RAM ≈ (1+24) × state |
| detector series | — | — | 20,000 points (`MAX_POINTS`) | cap reached at 50,000 steps | `shapes/detector.py` | RAM bounded |
| analysis windows | 40 windows, 8 segments | — | fixed | — | `harness.WINDOWS`, `SEGMENTS` | — |
| node sample (frames) | 4,000 | — | fixed | result size flat above 6,000 configurations | `harness.NODE_SAMPLE` | output size bounded |

**Complexity (code inspection, confirmed by measurement):** one step is vectorised numpy over the N
configuration arrays and the E connection slots (`np.bincount` over connections in `propagate`, masks in `cut`,
`disconnect`) — **O(N + E)**. Python loops exist in `connect`, `reconfigure`, `reconfigure_by_mutation` over
picked configurations (bounded per step by `connect_per_step` / `reconfigure_per_step`) and in `redirect_random` /
`redirect_overloaded` over overloaded connections. MEASURED: runtime throughput stays 2.0–3.4 M
configuration-updates/s from 2,000 to 2,048,000 configurations — linear. Hierarchy build (`eigsh`) MEASURED roughly
linear-to-slightly-superlinear in N (0.3 s at 1,000 → 186 s at 1,024,000). Detector graph pass every 10 steps
(BFS, strong/weak components, sampled shortest paths) adds a constant factor (≈ 2× at all sizes, MEASURED).

## 5. Existing Verified Capabilities

| evidence | class |
|---|---|
| backend test suite (263 tests) — 175 reproducibility/replay/conformance/resume/CLI tests rerun for this report, all passed | **A. CURRENTLY REPRODUCIBLE** |
| preset runs `resolution-escalation`, `boundary-scale-window`, `ablation`, `history-reentry` (2026-10-06; reruns matched 90/90 and 35/35 status cells) | **A** |
| golden conformance fixture (`backend/tests/fixtures/conformance_reference.json`) | **A** (test passed) |
| this report's benchmarks (`artifacts/capability-benchmarks/*.jsonl`, batch of 112 jobs) | **A** |
| resolution matrix `backend/experiments/results/resolution/matrix.json` — 63 conditions incl. n = 100,000 × 4,000 steps, 40,000 steps, 48 seeds; 9.8 h on 7 workers (log); 1,104 persisted job files (1.8 GB) | **B. HISTORICAL, NOT REPRODUCED** |
| studies disconnection / topology_triggers / adaptivity / clusters / compression (logs: 1.2 / 2.1 / 2.6 / 1.4 / 0.5 h), reduction (687 s), reason (273 s) | **B** |
| `bench.json` (2026-10-01: 966.9 steps/s at 1,500, 229.6 at 10,000), `baseline_bench.json` (2026-09-30: benchmark-10k 231 steps/s) | **B** (consistent with but not identical to this report's numbers: different world generator) |
| `docs/BENCHMARK.md` (rendering 60 fps at every scale; WebSocket rates) | **C. DOCUMENTATION CLAIM ONLY** (browser rendering not measured here) |
| iOS simulator benchmarks (`docs/IOS_APP.md`) | **B** |

## 6. OSP Experiment Feature Matrix

Full list with code paths: `artifacts/capability-benchmarks/feature_matrix.json`.

| feature | status | code / evidence |
|---|---|---|
| scale variation | IMPLEMENTED AND TESTED | `harness` n; `b1_harness.jsonl`, preset scale:600/3000 |
| topology variation | IMPLEMENTED AND TESTED | `scenario/topologies.py`; `test_topologies_build`; batch of 7 topologies |
| memory variation | IMPLEMENTED AND TESTED | `MEMORY_REGIMES`; tests `test_memory_*`; preset memory:short/long |
| coupling variation | IMPLEMENTED AND TESTED (executed; no unit test) | `harness.build`; preset coupling:weak/strong |
| horizon variation | IMPLEMENTED AND TESTED | `b2_horizon.jsonl`; preset horizon:1200 |
| observation-level variation | PARTIALLY IMPLEMENTED | five fixed resolutions only (`analysis.py`, `scale_values`) |
| multi-cluster experiments | IMPLEMENTED AND TESTED | `escalation/clusters.py`; `test_multiple_clusters_and_mixed_rules` |
| world-responsive revision | IMPLEMENTED AND TESTED | `reasonlab/triggers.py`; `test_closed_loop_is_deterministic`, open-loop replay test |
| disconnection / cut / reconnection / reconfiguration | IMPLEMENTED AND TESTED | `ops.py`; `test_reconnect_and_disconnect`, `test_cut_reconfiguration_trigger_variants`, `test_reconfiguration_as_mutation_retires_and_creates` |
| compression / reduction | IMPLEMENTED AND TESTED | `escalation/compression.py`, `reduction.py`; compression and reduction tests |
| history fork | IMPLEMENTED AND TESTED | `Engine.fork`; `test_fork_is_independent_and_identical` |
| history removal / reactivation / migration | IMPLEMENTED AND TESTED | `experiments/history.py`; `test_history_operations_are_deterministic_and_fork_is_exact`; preset run |
| configuration-crossing recurrence | PARTIALLY IMPLEMENTED | detector recurrence events; migrate destination counts; no dedicated test |
| sensor addition/removal | **ABSENT** | no code path |
| variable-set changes | **ABSENT** | fixed descriptor sets |
| observation-map changes | **ABSENT** | layouts are visual projections only |
| boundary changes | IMPLEMENTED AND TESTED | `world_schedule` close/open, `Gate`; preset boundary:closed |
| temporal-window changes | PARTIALLY IMPLEMENTED | horizon varies; analysis windows fixed (40 / 8) |
| access blocking | IMPLEMENTED AND TESTED | `Gate` factor 0, `Freeze`; gate tests |
| delayed re-entry | IMPLEMENTED AND TESTED | `history.reactivate_at`; history tests |
| correction latency | **ABSENT** | no code path |
| adversarial configuration search | **ABSENT** | no code path |
| cross-configuration robustness testing | PARTIALLY IMPLEMENTED | `results.configuration_sensitivity` over listed conditions; no search |
| independent re-detection | **ABSENT** | no code path |
| checkpoint/restart | PARTIALLY IMPLEMENTED | in-run rewind; study resume (`test_runner_persists_jobs_and_resumes_only_missing_seeds`); `xzr run` cannot resume |
| experiment provenance | IMPLEMENTED AND TESTED | `results.execute`, `runner.provenance`; `test_complete_experiment_through_the_cli` |

## 7. Benchmark Method

* Each single-run configuration ran in its own process (`bench_one.py`) under a guard (`guard.py`) that sampled
  RSS every 0.5 s and killed the run above **2.5 GB RSS** or a time limit; a sequence stopped at its first
  failure. Peak RSS = `ru_maxrss` (macOS: bytes) and the guard's samples.
* One dimension at a time; geometric progression ×2 from 1,000 configurations.
* Three paths: **runtime** (`Engine.step` on `latent_geometric`), **session path** (+ `ShapeDetector` and
  hierarchy), **experiment harness** (`harness.run`, reference variant with reasoning layer) and seed jobs
  (`harness.seed_job`) in a `ProcessPoolExecutor` (`bench_pool.py`), as the runner uses it.
* Steps/s are reported per third of the run (early / middle / late).
* Calibration of the harness used a private cache; the published cache was only read (its SHA-256 was unchanged
  afterwards, `306d222086271cad`).
* Repetition: the 16,000-configuration runtime path was run three times with seed 1 and the session path twice
  with seed 7 (identical fingerprints within each);
  worker-scaling runs were repeated (two sets with the same results). Run-to-run timing noise was not separately
  quantified beyond these repeats.

## 8. Scaling Results

Runtime only (300 steps, seed 1) — MEASURED:

| configurations | connections | init s | steps/s | early / mid / late | M config-updates/s | peak RSS MB |
|---|---|---|---|---|---|---|
| 1,000 | 4,901 | 0.47 | 1,379 | 1,484 / 1,357 / 1,307 | 1.38 | 65 |
| 4,000 | 19,269 | 0.40 | 675 | 747 / 674 / 615 | 2.70 | 79 |
| 16,000 | 76,534 | 0.70 | 204 | 238 / 202 / 179 | 3.26 | 131 |
| 64,000 | 305,954 | 1.96 | 53.4 | 63.4 / 53.3 / 46.1 | 3.42 | 362 |
| 256,000 | 1,221,438 | 7.42 | 12.8 | 15.2 / 12.9 / 11.0 | 3.28 | 810 |
| 512,000 | 2,443,328 | 16.0 | 6.52 | 7.81 / 6.54 / 5.57 | 3.34 | 1,091 |
| 1,024,000 | 4,886,130 | 35.2 | 3.05 | 3.74 / 3.08 / 2.55 | 3.12 | 1,742 |
| 2,048,000 | 9,772,246 | 105.1 | 1.46 | 1.79 / 1.47 / 1.23 | 2.99 | 2,029 |
| 4,096,000 | — | — | — | — | — | **killed by guard at 3,038 MB during initialisation** |

(2,000 / 8,000 / 32,000 / 128,000 rows: `b1_engine.jsonl`.)

Session path (runtime + shape detection + hierarchy) — MEASURED:

| configurations | init s (hierarchy) | steps/s | M config-updates/s | peak RSS MB |
|---|---|---|---|---|
| 1,000 | 0.81 (0.31) | 602 | 0.60 | 69 |
| 16,000 | 2.43 (1.72) | 92.1 | 1.47 | 146 |
| 128,000 | 17.7 (14.2) | 11.6 | 1.48 | 578 |
| 256,000 | 46.9 (39.6) | 5.55 | 1.42 | 1,097 |
| 512,000 | 100 (84.8) | 2.54 | 1.30 | 1,218 |
| 1,024,000 | 219 (186) | 1.18 | 1.21 | 2,042 |

Experiment harness, one reference run of 400 steps — MEASURED:

| configurations | calibration s (once per topology × size) | run s | steps/s | result size | peak RSS MB |
|---|---|---|---|---|---|
| 1,500 | 0.5 (cached) | 0.86 | 465 | 310 kB | 81 |
| 6,000 | 14.0 | 2.06 | 194 | 631 kB | 101 |
| 24,000 | 23.3 | 7.79 | 51.3 | 630 kB | 186 |
| 96,000 | 90.5 | 30.6 | 13.1 | 630 kB | 458 |

## 9. Single-Run Scaling

* **Largest verified single run (MEASURED): 2,048,000 configurations / 9,772,246 connections**, runtime only, 300
  steps, 1.46 steps/s, 2.03 GB peak, 105 s initialisation.
* Session path (with shape detection): 1,024,000 configurations, 1.18 steps/s, 2.04 GB, 219 s initialisation.
  2,048,000 on this path: NOT VERIFIED (not attempted: the runtime alone already used 2.03 GB at that size).
* Experiment harness: 96,000 configurations × 400 steps (13.1 steps/s, 458 MB) MEASURED; the historical matrix
  ran 100,000 × 4,000 steps (class B).
* Throughput within a run declines 10–30 % from the first to the last third at most sizes (activity builds up
  after the start) — MEASURED; it is not a slowdown that grows with horizon (§10).

## 10. Horizon Scaling

| run | steps | steps/s | early / mid / late | RSS samples MB | notes |
|---|---|---|---|---|---|
| session path, 1,500 | 50,000 | 330 | 395 / 307 / 302 | 71 → 82 → 84 → 55 → 55 | detector series capped at 20,000 points |
| session path, 16,000 | 10,000 | 86.4 | 81 / 88 / 92 | 129 → 131 → 133 → 135 → 135 | +5 MB over 10,000 steps |
| session path, 128,000 | 1,500 | 9.66 | 11.1 / 8.6 / 9.6 | 436 → 494 → 200 → 195 | (OS memory compression) |
| runtime with checkpoints every 50 steps, 16,000 | 10,000 | 173 | 145 / 182 / 204 | 125 → 205 → 266 → 285 → 285 | rises until the 24-checkpoint cap, then flat |
| harness, 1,500 | 40,000 | 1,119 | — | peak 89.5 | result 4.27 MB (vs 0.31 MB at 400 steps) |

MEASURED: memory does **not** grow without bound with horizon (detector series capped by `MAX_POINTS`, checkpoints
capped at 24, harness frames fixed). No slowdown over long runs. Output size of the harness result **does** grow
with horizon (revision and coupling records kept per check): 0.31 MB at 400 steps → 4.27 MB at 40,000 steps.
Numerical instability: none observed (runs completed; fingerprints reproducible); no dedicated stability test.

## 11. Multi-Run / Seed Scaling

Seed jobs on the production path (`harness.seed_job` in `ProcessPoolExecutor`), MEASURED:

| job size | 1 worker | 2 | 3 | 4 | 6 | 8 | peak RSS (8 workers) |
|---|---|---|---|---|---|---|---|
| 1,500 conf. × 400 steps, 16 jobs | 1,392 jobs/h | 2,590 | 2,703 | 3,016 | 3,209 | 3,521 | 746 MB |
| 12,000 conf. × 400 steps, 8 jobs | 288 | 492 | — | 568 | — | 682 | 918 MB |
| 1,500 conf. × 4,000 steps, 4 jobs | 140 | — | — | 302 | — | — | 393 MB (4 workers) |
| 10,000 conf. × 4,000 steps, 2 jobs | — | 64.8 | — | — | — | — | 342 MB |

* **Optimal verified parallelism: 4 workers** (best throughput per worker: 2.0–2.2× serial). 8 workers add
  15–20 % throughput for ~2× RAM (2.4–2.5× serial). Limited by 4 performance cores and ~2 cores of background load.
* Seed isolation / determinism across worker counts: **VERIFIED** — all per-seed results identical with 1, 3, 4
  and 8 workers once three wall-clock timing fields (`build_s`, `ms_per_step`, `loop_ms_per_step`) are excluded
  (`diff_job.py` shows these are the only differing fields).
* Failures in the measured runs: none; no race conditions observed; result writes are per-job files (no
  contention observed).
* **Production batch (MEASURED):** `python -m xzr run` of 7 topologies × 16 seeds (112 seed jobs, 1,500 conf.,
  4,000 steps, variants A C E H + C~), 4 workers: **1,717 s (28.6 min), 235 jobs/h, peak 1.59 GB for the process
  tree** (analysis of a condition holds its 16 seed results and the permutation matrices), 98 MB on disk, 0
  failures, noise replicate detected in no condition.
* Failure propagation (code inspection, NOT VERIFIED by fault injection): an exception in any seed job propagates
  from `f.result()` in `runner.run_conditions` and aborts the run; jobs already saved remain on disk (studies
  resume; `xzr run` does not). A killed worker breaks the whole pool (`BrokenProcessPool`, observed earlier in this
  project for a different cause).

## 12. Reproducibility

**DETERMINISTIC** on this hardware and software stack:
* identical state fingerprints for the same configuration and seed in separate processes, and against a run made
  hours earlier (runtime and session paths, `b4_repro.jsonl`) — VERIFIED;
* identical per-seed experiment results across 1/3/4/8 workers (timing fields excluded) — VERIFIED;
* identical status cells for full preset reruns (90/90, 35/35) — VERIFIED;
* 175 tests covering replay, rewind, fork, conformance (desktop scipy path vs iOS stand-in path against a golden
  fixture), save/load and resume — passed.

Limitations: results embed wall-clock timing fields (byte equality of raw files fails unless they are excluded);
cross-platform bit identity (other OS / CPU / numpy versions) — NOT VERIFIED; no GPU nondeterminism (no GPU path).
RNG: numpy PCG64 per engine seed and per world generator seed; workers receive explicit seeds; no global RNG.

## 13. Memory / VRAM Behavior

* Single runs (runtime only), measured peak RSS: 65 MB (1,000), 131 MB (16,000), 362 MB (64,000), 646 MB
  (128,000), 810 MB (256,000), 1,091 MB (512,000), 1,742 MB (1.02 M), 2,029 MB (2.05 M); growth flattens above
  ~128,000 configurations while the host was under memory pressure (macOS memory compression), so these peaks are
  not a clean linear model. 4.1 M exceeded 3.0 GB during initialisation.
* Worker processes: ≈ 90–115 MB each for 1,500–12,000-configuration jobs; the analysis step of `xzr run` adds up
  to ~1.2 GB for 16 seeds per condition (production batch peak 1.59 GB at 4 workers).
* No unbounded growth with horizon (§10). VRAM: not applicable.

## 14. Storage / Result Growth

* Seed job (gzip pickle, persisted): **0.85 MB/job** in the production batch (4 variants, 4,000 steps); 0.6–1.4
  MB/job in preset runs; up to 2.9 MB/job historically (11 variants). Historical matrix: 1,104 jobs = 1.8 GB.
* `result.json` 12–28 kB; `raw.json` 0.36 MB for 7 conditions; history runs ~50 kB.
* Growth with horizon: harness result 0.31 MB (400 steps) → 4.27 MB (40,000 steps), uncompressed.
* Checkpoints: in memory only (not written); experiment-level persistence is the per-seed jobs.
* Free disk at measurement: 27 GiB.

## 15. Failure Boundary

| path | LAST VERIFIED SAFE | FIRST OBSERVED FAILURE / UNSAFE |
|---|---|---|
| runtime only | 2,048,000 configurations, 9.77 M connections, 300 steps (2.03 GB) | 4,096,000 configurations: killed by the guard at 3,038 MB RSS during initialisation (host swap rose to 9.7 GB) |
| session path (+ detector, hierarchy) | 1,024,000 configurations, 200 steps (2.04 GB) | not attempted — NOT VERIFIED |
| experiment harness | 96,000 configurations × 400 steps (458 MB) | not reached — NOT VERIFIED |
| horizon | 50,000 steps (1,500 conf.), 40,000 steps (harness) | not reached |
| batch | 112 jobs, 4 workers, 28.6 min | not reached |

The exact maximum between the last safe and the first unsafe configuration is not inferred.

## 16. Large Experiment Matrix Estimates

Assumed configuration: one run = one seed job (reference C + noise replicate C~ + variants A, E, H), 1,500
configurations, 4,000 steps, multi-condition `xzr run`. Basis: MEASURED 112-job production batch (235 jobs/h at 4
workers) and MEASURED serial rate (139.6 jobs/h); storage 0.85 MB/job MEASURED.

| runs | serial wall | at 4 workers | peak RAM | storage | confidence |
|---|---|---|---|---|---|
| 100 | 0.7 h | 0.4 h | ~1.6 GB | 0.09 GB | HIGH (smaller than the executed 112-job batch) |
| 1,000 | 7.2 h | 4.3 h | ~1.6 GB | 0.9 GB | MEDIUM (~9× the measured batch) |
| 5,000 | 35.8 h | 21.3 h | ~1.6 GB | 4.4 GB | LOW (> 10× beyond measured) |
| 10,000 | 71.6 h | 42.6 h | ~1.6 GB | 8.8 GB | LOW (> 10× beyond measured; one job exception aborts the run; no resume for `xzr run`) |

At 10,000 configurations per world the measured rate is 64.8 jobs/h (2 workers): 1,000 runs ≈ 15 h, ~3 GB
(MEDIUM-LOW: 2 jobs measured). At 100,000 configurations, 1,000 runs are not feasible on this machine within a week
(derived from 13 steps/s per run; LOW CONFIDENCE).

## 17. Scientific Reproducibility Infrastructure

| item | status | where |
|---|---|---|
| fixed experiment manifests | VERIFIED | `xzr/presets/*.json`; `config.json` per run (effective configuration) |
| configuration hashing | VERIFIED | run id = UTC time + SHA-256 of the effective configuration (same suffix for identical configs) |
| commit / version capture | VERIFIED | `provenance`: version, git HEAD, dirty flag (source checkout), code hash |
| environment capture | PARTIAL | Python and numpy versions only (no OS, CPU, scipy) |
| seed capture | VERIFIED | seed list in `result.json` and per job |
| TII or equivalent run identification | PARTIAL | local run id only; no registration with TII |
| raw result preservation | VERIFIED | `jobs/` (per seed), `jobs.json` (history), `raw.json` |
| aggregate result generation | VERIFIED | `result.json`, `summary.txt`, `xzr export` |
| failure logging | PARTIAL | analysis errors recorded per condition; a seed-job exception aborts the run instead of being recorded |
| resumability | PARTIAL | studies resume from persisted jobs; `xzr run` does not |
| ablation support | VERIFIED | `ablation` preset, reduction study |
| baseline comparison | VERIFIED | paired reference C / intact branch + noise replicate |
| multiple seeds | VERIFIED | ≤ 16 per preset condition; harness supports more (Monte Carlo above 14) |
| confidence intervals / statistics | VERIFIED | sign-flip max-T, equivalence (harness); sign-flip + 95 % t interval (history) |
| artifact provenance | PARTIAL | artifacts listed; no per-file hashes |
| replayability | VERIFIED | seeded reruns identical; `Engine.rewind` |

## 18. Missing Capabilities

NOT IMPLEMENTED: generated observability (sensor addition/removal, variable-set changes, observation-map changes);
adversarial configuration search; independent re-detection; correction latency; configurable observation
resolutions or analysis windows; GPU execution; distributed / multi-machine execution; per-seed failure isolation;
resume for `xzr run`. PARTIAL: configuration-crossing recurrence, cross-configuration robustness (listed conditions
only, no search), environment capture, artifact hashing.

## 19. Blocking Issues

**BLOCKING** (for the named experiment families)
* Generated-observability experiments — NOT IMPLEMENTED (no sensor / variable-set / observation-map changes).
* Adversarial-differentiation experiments — NOT IMPLEMENTED (no adversarial search, no independent re-detection).

**IMPORTANT**
* Hardware: 8 GB RAM, 4 performance cores; parallel speed-up ≤ 2.5×; runs above ~2 M configurations unsafe.
* A seed-job exception aborts the whole run; `xzr run` cannot resume (multi-day matrices at risk).
* Presets cap seeds at 16 per condition; the history statistics enumerate 2^seeds (practical ≤ ~20 seeds).
* Results embed wall-clock timing fields (exclude for byte-level reproducibility checks).
* Environment capture partial; the repository's own `.venv` lacks the `xzr` console script until reinstalled
  (`python -m xzr` works; a fresh install provides it).

**OPTIONAL**
* GPU path, distributed execution, per-artifact hashes, configurable analysis windows.

## 20. Final Answer

**"Can this simulator, in its current state, run a flagship large-scale Operational-Shape / Ziran / Xenoscience
experiment?" — YES WITH LIMITATIONS.**

"Large-scale" under current measured evidence means, on this machine: an experiment built only from the
implemented operations (scale, topology, memory, coupling, horizon, boundary, ablation, multi-cluster,
world-responsive revision, disconnection / cut / reconfiguration, compression, history fork / removal /
reactivation / migration), at up to **~1,000 paired seed jobs of 1,500 configurations × 4,000 steps (≈ 4.3 h at 4
workers, ~1 GB)** with MEDIUM confidence, or single worlds up to **2 M configurations** for a few hundred steps.
Several thousand jobs are an unverified, LOW-confidence extrapolation (≈ 21–43 h unattended, no per-seed failure
isolation, no resume for `xzr run`).

For flagships that require **generated observability** or **adversarial differentiation**: **NO** — those
experiment families are NOT IMPLEMENTED.

This report answers whether experiments can be executed, at what scale, and reproducibly. It does not assess whether
an experiment operationalises its intended variable correctly or whether a result supports a philosophical claim.
