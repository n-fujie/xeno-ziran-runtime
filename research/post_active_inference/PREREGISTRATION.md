# Pre-registration — research-scale (confirmatory) stage

Written and frozen **before launch**, 2026-10-07, before any research-stage result existed. The machine-readable
record is `results/research/preregistration.json`. It holds:

* git HEAD and dirty flag;
* the configuration hash;
* per-file SHA-256 of every benchmark and runtime source file;
* the frozen source archives;
* classifier thresholds and frozen AIF parameters;
* the development-derived refinement points;
* hardware and dependency versions.

This document is the binding analysis protocol.

## 0. Stage separation

| stage | role | data |
|---|---|---|
| SMOKE | implementation validation | `results/smoke/` (pre-revision design) |
| DEVELOPMENT | exploratory threshold discovery and benchmark correction; **frozen** | `results/dev/` |
| RESEARCH | confirmatory evaluation with frozen rules | `results/research/` |

Research statistics are computed from `results/research/` only and are never pooled with smoke or development data.
The research report (`REPORT_RESEARCH.md`) is written separately, before any integration with `REPORT.md`.

## 1. Frozen design

Run exactly `configs/research.json` (config hash in the JSON record):

* 30 seeds;
* principal severities 0.125, 0.25, …, 1.0 (eight levels);
* 48 refinement points from `refine` on the development crossings;
* controllers `none`, `aif_fixed`, `aif_adaptive`, `ost`;
* the eight ablations on the 16 development ablation cells;
* 12,750 cells, 55,680 runs.

**Pre-launch correction.** The prepared seeds 1–30 overlapped the development seeds 1–10. At the four shared
severities those runs would have been bit-identical copies of development data, so they could not count as
confirmation. The seeds are therefore **11–40**, disjoint from development. No other part of the design was
changed.

**Negative controls (included).** Every seed has a control cell (severity 0, all controllers and ablations) and a
noise replicate (engine seed + 1000; `none`, `aif_fixed`, `aif_adaptive`).

**Frozen until the report is written:** world, task, setpoint schedule, phases, controllers and their parameters,
perturbation implementations, tracker, classifier (`HI` = 0.8, `LO` = 0.5, scores, noise-tolerance rule,
cell-level primary label), non-redundancy rule (margin ±0.05, Holm) and analysis code.

**Defect rule.** If a genuine code defect is found during the run:

1. stop the affected conditions;
2. document the defect here (dated addendum);
3. identify the invalid cells and invalidate only those;
4. fix the defect;
5. re-run the affected conditions from scratch.

There is no silent mid-run patching.

**Analysis code.** The confirmatory analysis (`pai/confirmatory.py`) implements this protocol. It is completed
while the run is in progress, without reading any research job file. Its SHA-256 is added to this document
(addendum A) before the first research result is opened.

## 2. Quantities kept separate

For every cell × seed, these are reported as separate quantities, never merged into one label:

* **task success:** `success_pert`, `success_rec` per controller;
* **predictive success:** one-step accuracy and multi-step accuracy;
* **representational validity:** `C_AIF`, the compatibility score;
* **observation-map stability:** `S_sensor`;
* **interface / policy stability:** `S_policy`;
* **boundary-proxy stability:** `S_boundary`;
* **model-structure stability:** `S_model`;
* **variable-system stability:** `S_variable`.

Derived continuous scores, defined here before results:

* **compatibility score** = `C_AIF`;
* **structural-instability score** = 1 − min(`S_model`, `S_variable`) (missing scores are skipped);
* **operational-persistence score** = clip(`persistence_pert` of the uncontrolled run / the mean `persistence_pert` of
  the control and noise-replicate uncontrolled runs, 0, 1). `persistence_pert` is the tracker's Jaccard of active
  sets between consecutive windows. It is reported together with `tracking_preserved`.

Seed-level label distributions are always reported (for example "18/30 TRANSITION, 12/30 POST"), never only the
cell-level word.

## 3. Confirmatory questions and decision rules

**D** is the set of 19 perturbations whose development cell-level label left the compatible regime at some severity.
**D_post** is the subset that reached POST in development: sensor delay, sensor dropout, sensor reassignment,
temporal asynchronous, variable deletion, boundary reassignment, temporal interface drift. **K** is the set of 28
perturbations that stayed compatible throughout development.

* **Q1 — unperturbed controls.** Report the per-seed null labels (leave-one-seed-out tolerance) and the cell-level
  null label.
  * *Confirmed* if the cell-level label is compatible and at least 27 of 30 per-seed labels are compatible.
* **Q2 — replication of crossings.** For each k ∈ D, with crossings estimated over all research severities (principal
  and refined):
  * *Replicated* if the research cell-level label is non-compatible at ≥ 1 severity, the 0.8 crossing has
    `boot_never_share` < 0.05, and `seeds_crossing_share` ≥ 0.5.
  * Report the development crossing severity next to the research estimate and CI, and whether it falls inside.
  * Also report, as a reverse check, any k ∈ K that crosses in research.
  * Report the count of replicated perturbations out of 19.
* **Q3 — sequence.** For each k ∈ D, the cell-level label sequence over increasing severity is classified as:
  * `C→T→P` (monotone through TRANSITION to POST);
  * `C→T` (reaches TRANSITION only);
  * `C→P` (no TRANSITION cell between);
  * `non-monotone`.

  For each k ∈ D_post: *sequence replicated* if POST is reached at ≥ 1 severity and the sequence is `C→T→P` or `C→P`
  as in development.
* **Q4 — threshold stability.** For every principal crossing (k ∈ D, thresholds 0.8 and 0.5) report:
  * number of seeds;
  * mean and median `C_AIF` per severity, with 95 % bootstrap CI;
  * effect size d_z of per-seed `C_AIF`(severity) − per-seed null `C_AIF`;
  * seed-level direction consistency: the share of seeds with `C_AIF`(severity) < their own null `C_AIF`;
  * the cell-level and per-seed regime distribution;
  * the threshold estimate, its bootstrap 95 % CI, `seeds_crossing_share` and the per-seed crossing IQR.

  *Stable* if the CI width is ≤ 0.25 severity units and `seeds_crossing_share` ≥ 0.8.
* **Q5 — kind of transition.** Each k ∈ D is labelled:
  * *gradual:* passes through a TRANSITION cell and the mean `C_AIF` is monotone within its CIs;
  * *abrupt:* compatible → POST between adjacent tested severities;
  * *inconsistent:* the mean `C_AIF` rises between consecutive severities by more than the larger CI half-width.

  **Hysteresis cannot be tested with this design** (no reverse sweep). As a pre-specified proxy, for reversible
  perturbations (those with a revert step), report whether `aif_adaptive` recovery-phase success stays below the
  control's after reversal (paired sign-flip, Holm). This is reported as *task-level persistence after reversal*,
  not as regime hysteresis.
* **Q6 — observation and interface share of POST.** Report POST counts at cell and cell × seed level by side (world,
  interface, observation). Test the POST proportion among observation + interface cell × seeds against world cell ×
  seeds (two-sided Fisher exact test).
* **Q7 — world-side families.** Report the maximum cell-level label and the per-seed POST counts for topology,
  coupling, memory and structural perturbations.
  * *Confirmed* (they remain compatible or transition) if no world-side cell is POST at cell level.
* **Q8 — task performance vs representational validity (dissociation).**
  * (a) In cell-level POST cells, test `aif_fixed − none` and `aif_adaptive − none` on `success_pert`, paired over
    cell × seed (sign-flip, Holm over the two). Do the same restricted to per-seed POST cell × seeds.
  * (b) Across all perturbation cells, compute the Spearman correlation between cell `C_AIF` and the cell mean
    advantage over no control (`aif_adaptive − none`), with bootstrap CI.
  * (c) The same with one-step predictive accuracy instead of task success.
  * *Dissociation supported* if (a) is positive with Holm p < 0.05 for at least one AIF variant, i.e. control is
    retained where representational validity has failed.
  * Report (b) and (c) as the strength of coupling between validity and performance.

**Secondary analyses (pre-specified):**

* the full development-style analysis (`run_benchmark.py analyse configs/research.json`);
* threshold sensitivity (0.7/0.4, 0.9/0.6);
* a tolerance sensitivity analysis using the frozen development tolerance values instead of the 30-seed maximum.
  **Predictable effect, stated before results:** with more seeds the maximum noise difference can only grow, so
  the primary rule is *more* conservative than in development. Fewer non-compatible labels in research may partly
  reflect this, which is why the sensitivity analysis exists.

## 4. Development findings to re-test (not to be removed unless research evidence changes them)

1. OST is not generally a superior controller.
2. OST's detection advantage shrinks substantially when sensor information is equalised (sensor-only tracker).
3. Localisation is near chance for both systems.
4. History re-entry shows no detectable effect under the tested memory dynamics.
5. Frequent action remapping (interface drift) degrades all controllers to the level of no control.
6. Free-energy rebuilding, the EFE epistemic term and latent-state inference are operationally redundant for the
   measured prediction and intervention outcomes in the tested compatible regime.

All redundancy statements are scoped to "under the tested task, world, controller and outcome measures" and are
not generalised to Active Inference as a whole.

## 5. Central hypothesis and permitted conclusions

**Hypothesis.** Active Inference remains an effective controller inside, and sometimes beyond, the interval in which
its tested representational primitives remain stable; those stability conditions can nevertheless show
reproducible, severity-dependent transitions.

**Permitted outcomes:**

* If POST regions disappear at 30 seeds: say that the development-stage evidence did not replicate.
* If they replicate only for sensor and action-interface disruptions: restrict the claim to those conditions.
* If they replicate broadly: quantify how broadly.

**Not claimed under any outcome:**

* that Active Inference is falsified;
* that operational-shape tracking is a universally superior controller;
* that all Active Inference implementations share these limits;
* that a general Post-Active-Inference theory is experimentally proven.

## 6. Known limitations, fixed in advance

* One world graph (generator seed 3); seeds vary the engine stream, not the world structure.
* One task and one comparator family.
* Conservative noise tolerance (small shifts are not registered).
* Policy identity is probed at three instants (aliasing with drift periods).
* The memory regime is short.
* Cross-platform determinism is not verified, so the whole stage runs on one machine.

## Addenda

*(dated; appended only — nothing above is edited after launch)*

### Addendum A — confirmatory analysis code frozen (2026-10-07 14:47 +0900)

`pai/confirmatory.py` implements §§ 2–4. It was tested only on development data (output written to a scratch
directory; `results/dev/` untouched). No research job file had been opened. 82 research cells had been written by
the running job at this time; none was read.

| file | SHA-256 |
|---|---|
| pai/confirmatory.py | b1a22382cd358148ccbcf78eccb5d1aa6d2bea7ae69f94cb08ee556a546cf786 |
| pai/analysis.py | b8c49df26e41161d0475bd4eaf56ca252e789381c2ece94a3a690829913d06e6 |
| pai/stats.py | 7871812acfbe90771a387dc64d0ea8c0438f89ce36de814dfeead4ee7d8c06c4 |
| regime_classifier.py | af7c974bac6aaf1cc438058418eb090e3e39a970294d3c3318d1bc48553e55e2 |

Order of analysis after completion: (1) `run_benchmark.py analyse configs/research.json` (secondary, development-style),
(2) `python -m pai.confirmatory results/research` (primary), (3) `REPORT_RESEARCH.md`.

### Addendum B — cosmetic lint change (2026-10-07 14:47 +0900)

One unused loop variable renamed (`s` → `_s`) in `pai/confirmatory.py`; no behavioural change (diff: one line).
Long table-template lines exempted in `ruff.toml`. New SHA-256 of `pai/confirmatory.py`: 95323ac17f4b7e333f9f7079d4dea25d06f7731846ceaf87958d52fb45f72af8. Still no research job
file opened.

Runtime note: measured development throughput (≈ 4.3 s per run per worker under this machine's load) puts the research
stage at ≈ 16–17 h, not the ≈ 9 h estimated by `plan`; the design is unchanged.
