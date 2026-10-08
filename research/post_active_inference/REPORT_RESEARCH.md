# REPORT — research-scale (confirmatory) stage

**Stage:** RESEARCH, confirmatory under frozen rules ([PREREGISTRATION.md](PREREGISTRATION.md); record
`results/research/preregistration.json`).

* 30 fresh seeds (11–40, disjoint from development).
* Severities: 8 principal + 48 refined points.
* 12,750 cells, 55,680 runs, 0 aborted.
* Run time 842 min on Apple M1 / 8 GB, 2026-10-07 14:39 → 2026-10-08 04:42 JST.

**Analysis.** Primary: `python -m pai.confirmatory results/research`. Secondary: `run_benchmark.py analyse
configs/research.json`. The analysis-code hashes match Addenda A and B.

**Separation.** This report uses `results/research/` only. Nothing is pooled with smoke or development data. It is
written before any integration with the development report ([REPORT.md](REPORT.md)).

**Scope.** Measured differences in one simulated runtime, with:

* one world graph;
* one control task;
* one discrete Active Inference comparator family (fixed and adaptive);
* one model-light controller;
* one tracker.

All conclusions hold "under the tested task, world, controller and outcome measures". They are not about Active
Inference in general.

Data: [`results/research/confirmatory_tables.md`](results/research/confirmatory_tables.md) (primary, including
per-severity statistics and seed-level label distributions for every principal crossing),
[`results/research/report_data.md`](results/research/report_data.md) (secondary),
`results/research/confirmatory.json` and `cell_scores.csv` (continuous scores per cell × seed).

## 1. Result in one paragraph

The development-stage regions **replicate for sensor and action-interface disruptions only**:

* 10 of 19 development crossings replicate under the pre-registered criterion.
* All 8 perturbations that reach POST_ACTIVE_INFERENCE are observation- or interface-side.
* All 15 stable threshold estimates belong to those perturbations.

World-structure perturbations (topology, coupling, memory, structural) never reach POST. One reaches TRANSITION:
coupling weakening. The variable- and model-driven transitions seen in development under boundary merge or leakage,
cluster merge, coupling reversal, cut, disconnection and variable remap **did not replicate**. Part of this is the
predicted effect of the noise-tolerance rule growing with 30 seeds (§ 3, Q2).

The pre-registered dissociation test **failed in the opposite direction**. Where the representational primitives
failed (cell-level POST), both AIF variants controlled the task **worse than no control**: fixed −0.028 [−0.049,
−0.008], Holm p = 0.0085; adaptive −0.058 [−0.075, −0.041], Holm p = 0.0005. Across cells, validity and control are
positively coupled (Spearman ρ = 0.44 [0.37, 0.51]).

Inside the compatible regime, the AIF's control advantage is real but small in fresh seeds: +0.03 [0.02, 0.03]
over no control, d_z = 0.10. In development it was +0.11.

## 2. Verdict on the central hypothesis

> "Active Inference remains an effective controller inside and sometimes beyond the interval in which its tested
> representational primitives remain stable; those stability conditions can nevertheless exhibit reproducible,
> severity-dependent transitions."

| part | verdict |
|---|---|
| effective controller **inside** the interval | **weakly supported:** significant but small advantage over no control in the compatible regime (+0.02 fixed, +0.03 adaptive; Holm p = 0.015); not significant on the unperturbed reference alone (+0.07, n = 30, Holm p = 1.0) |
| **sometimes beyond** the interval | **not supported:** in POST cells the AIF is worse than no control; the development result (fixed AIF +0.07 over no control in POST) did not replicate |
| reproducible, severity-dependent transitions of the stability conditions | **supported for sensor and action-interface disruptions** (10 of 19 development crossings; 8 subtypes reach POST; 15 stable thresholds); **not supported for world-structure perturbations** |

**Strongest defensible formulation.** Under the tested task, world, controller and outcome measures:

* the representational primitives of this discrete Active Inference comparator lose stability reproducibly,
  mostly gradually and severity-dependently, when its **observation map or action interface** is disrupted;
* disruptions of the **world's structure** (topology, coupling, memory, structural reconfiguration) do not push it
  out of the compatible regime in the tested range;
* where the primitives fail, **control fails with them**;
* inside the compatible regime its control advantage is small.

Not claimed:

* that Active Inference is falsified;
* that operational-shape tracking is a superior controller (it is not, except under coupling weakening, § 4);
* that other Active Inference implementations share these limits;
* that a general Post-Active-Inference theory has been demonstrated.

## 3. Confirmatory questions (pre-registered rules)

**Q1. Do unperturbed controls remain compatible?** **Confirmed.** Per-seed null labels (leave-one-seed-out
tolerance): 30/30 ACTIVE_INFERENCE_COMPATIBLE. Cell-level null: compatible.

**Q2. Do development crossings replicate?** **10 of 19.**

* **Replicated:**
  * sensor delay, sensor dropout, sensor noise, sensor reassignment, sensor window mismatch;
  * temporal asynchronous, temporal interface drift;
  * variable deletion;
  * boundary reassignment;
  * coupling weakening.
* **Not replicated:** boundary disappearance, leakage and merge; coupling reversal; cut + reconnect; disconnection;
  cluster merge; variable relabel; variable remap. Their seed-crossing shares were 0.00–0.57, below the 0.5
  criterion or with an unstable bootstrap. Variable relabel crossed in 57 % of seeds, but 7.75 % of bootstrap
  means never cross (the rule requires < 5 %), so it fails the frozen rule.
* **Reverse check:** no perturbation that was compatible throughout development crossed in research.
* **Tolerance effect, predicted in PREREGISTRATION § 3.** With 30 seeds the tolerances grew:
  * accuracy 0.42 → 0.66;
  * separability 0.37 → 0.71;
  * PC1 0.15 → 0.25.

  The model and variable scores, which drove most non-replicated crossings, therefore became much harder to
  trigger. With the frozen development tolerance (secondary), cell labels are 345 compatible / 52 transition / 27
  post, against 369 / 28 / 27 under the primary rule. The extra transitions are where the non-replications sit.
* **Conclusion:** the observation and interface crossings replicate under either tolerance. Whether the
  variable- and model-driven transitions are real but small, or development noise, **is not resolved** by this design.

**Q3. Do sweeps run COMPATIBLE → TRANSITION → POST where development suggested it?** **Yes for 6 of 7 development
POST perturbations.**

| perturbation | development | research sequence | research labels |
|---|---|---|---|
| sensor reassignment | C→T→P | **C→T→P** | C to 0.5; T 0.625–0.875; P from 0.917 |
| temporal asynchronous | C→T→P | **C→T→P** | C to 0.625; T 0.667–0.75; P from 0.833 |
| variable deletion | C→P | **C→T→P** | C to 0.875; T at 0.917; P at 1.0 |
| boundary reassignment | T→P | **C→T→P** | C to 0.75; T 0.833–0.917; P at 1.0 |
| sensor delay | T→P | **T→P** (C only at severity 0) | T 0.083–0.25; P from 0.333 |
| sensor dropout | C→P | **C→P** | C to 0.875; P from 0.917 |
| temporal interface drift | P→T (non-monotone) | **non-monotone** | T at 0.083–0.125; P 0.167–0.875; T at 1.0 |

Interface drift is non-monotone again, consistent with probe aliasing at the shortest periods, a design
limitation registered in advance. Sensor noise is new: it reaches POST at severity ≥ 0.917 (development stopped at
TRANSITION).

**Q4. Are the thresholds stable across seeds?** **15 of 38 principal crossings are stable** (CI width ≤ 0.25 and ≥ 80 %
of seeds crossing). All 15 are observation- or interface-side.

| crossing | estimate [95 % CI] | seeds crossing | per-seed IQR |
|---|---|---|---|
| sensor delay → 0.8 | 0.05 [0.04, 0.06] | 1.00 | 0.04–0.09 |
| sensor delay → 0.5 | 0.26 [0.12, 0.28] | 1.00 | 0.10–0.31 |
| interface drift → 0.8 | 0.05 [0.04, 0.05] | 1.00 | 0.04–0.05 |
| interface drift → 0.5 | 0.14 [0.14, 0.15] | 1.00 | 0.14–0.15 |
| sensor noise → 0.8 | 0.41 [0.35, 0.47] | 0.97 | 0.33–0.49 |
| sensor reassignment → 0.8 / 0.5 | 0.59 [0.53, 0.76] / 0.88 [0.82, 0.89] | 1.00 / 1.00 | 0.54–0.79 / 0.79–0.89 |
| temporal asynchronous → 0.8 / 0.5 | 0.63 [0.60, 0.66] / 0.83 [0.80, 0.85] | 1.00 / 1.00 | 0.56–0.68 / 0.77–0.85 |
| boundary reassignment → 0.8 | 0.66 [0.60, 0.72] | 1.00 | 0.53–0.76 |
| sensor window mismatch → 0.8 | 0.85 [0.74, 0.87] | 0.93 | 0.81–0.95 |
| sensor dropout → 0.8 / 0.5 | 0.88 [0.88, 0.88] / 0.89 [0.89, 0.90] | 1.00 / 1.00 | — |
| variable deletion → 0.8 / 0.5 | 0.88 [0.87, 0.90] / 0.92 [0.90, 0.94] | 1.00 / 1.00 | 0.88–0.93 / 0.90–0.96 |

**Unstable:**

* coupling weakening → 0.8: 0.70 [0.65, 0.82], 77 % of seeds;
* boundary reassignment → 0.5: 60 % of seeds;
* sensor noise → 0.5: 0.87 [0.76, 0.99], 63 % of seeds.

**Seed disagreement near the boundary** is preserved in the tables, for example:

* sensor noise at severity 1.0: 19/30 POST, 10/30 TRANSITION, 1/30 compatible;
* boundary reassignment at 0.833: 18 TRANSITION, 8 compatible, 4 POST;
* coupling weakening at 1.0: 18 TRANSITION, 12 compatible;
* variable relabel at 1.0: 17 compatible, 8 TRANSITION, 5 POST.

**Q5. Gradual, abrupt, hysteretic or inconsistent?** Over the 19 development crossings:

* 8 gradual (sensor noise, reassignment and window mismatch; temporal asynchronous; boundary reassignment; variable
  deletion and relabel; coupling weakening);
* 1 abrupt (sensor dropout: the aggregate reading stays informative until the last channel dies);
* 2 inconsistent (sensor delay, whose mean C_AIF dips at 0.75 and rises at 1.0; interface drift);
* 8 compatible throughout (the non-replications).

Hysteresis is not testable with this design. On the task-level proxy, only coupling weakening at 0.625 leaves
recovery-phase success persistently below control after reversal (−0.18, Holm p < 0.05).

**Q6. Are observation and interface perturbations disproportionately responsible for POST?** **Yes, entirely.**

* POST cells: observation 19, interface 8, world 0.
* POST cell × seeds: 13.3 % of observation + interface against 0 % of world (Fisher exact p ≈ 10⁻²⁵⁷).

**Q7. Do topology, coupling, memory and structural perturbations stay compatible or transition?** **Confirmed.**

* Topology: 58/58 cells compatible.
* Memory: 48/48 compatible.
* Structural: 28/28 compatible.
* Coupling: 50 compatible, 2 TRANSITION (weakening).
* Zero per-seed POST labels in all four families.

**Q8. Does task performance dissociate from representational validity?** **No: they are coupled.**

| scope | contrast | mean [95 % CI] | d_z | Holm p |
|---|---|---|---|---|
| cell-level POST (810 cell × seeds) | aif_fixed − none | −0.028 [−0.049, −0.008] | −0.09 | 0.0085 |
| | aif_adaptive − none | −0.058 [−0.075, −0.041] | −0.24 | 0.0005 |
| per-seed POST (916 cell × seeds) | aif_fixed − none | −0.034 [−0.055, −0.015] | −0.11 | 0.0007 |
| | aif_adaptive − none | −0.063 [−0.079, −0.047] | −0.25 | 0.0005 |

* Spearman correlation of cell C_AIF with the adaptive AIF's advantage over no control: ρ = 0.44 [0.37, 0.51], 423 cells.
* With one-step predictive accuracy: ρ = 0.54 [0.45, 0.62].
* The pre-registered dissociation criterion is **not met**.

Task success, predictive accuracy and the five primitive scores remain separate quantities in
`confirmatory_tables.md`. The data do not show control surviving representational failure.

## 4. Development findings re-tested

| development finding | research outcome |
|---|---|
| 1. OST is not generally a superior controller | **Confirmed**, with one exception |
| 2. OST's detection advantage shrinks when sensor information is equalised | **Confirmed** |
| 3. Localisation is near chance | **Confirmed** |
| 4. History re-entry has no detectable effect under the tested memory dynamics | **Confirmed** |
| 5. Frequent action remapping degrades all controllers | **Confirmed and strengthened** |
| 6. Free-energy rebuild, EFE epistemic term and latent-state inference are operationally redundant for prediction and intervention in the compatible regime | **Confirmed**, with one addition |

1. **OST as a controller.** AIF beats OST in every regime: compatible +0.02 / +0.03, transition +0.05 / +0.04, POST
   +0.07 / +0.04 (fixed / adaptive; Holm p = 0.015). The exception is coupling weakening at severity ≥ 0.667, where
   OST is far better than both AIF variants and than no control (0.28–0.37 against 0.09–0.15 and 0.11–0.27).
   Under reduced transmission gain, the measured-effect rule adapts and the frozen model does not. Recorded as a
   condition where the model-light controller performs better.
2. **Detection with equalised sensors.** World-side onset detection is 0.65 / 0.97 for the full-stream tracker (compatible /
   transition), 0.16 / 0.43 for the sensor-only tracker and 0.07 / 0.29 for the comparator's surprise. The
   information-access explanation stands.
3. **Localisation.** ROC-AUC is 0.43–0.47 for the tracker and 0.53–0.54 for the comparator.
4. **History re-entry.** Reactivation against removal shows no significant effect at any of 8 severities on
   recovery, pattern recurrence or migration gain. The two smallest uncorrected p-values (0.068, 0.018) are
   negative in direction and do not survive correction.
5. **Interface drift.** Every controller is significantly **below** no control at every drift period from 10 to 226
   steps: adaptive AIF −0.09 to −0.14, OST −0.12 to −0.17. Development found only non-significant decreases.
   Staleness begins at or beyond the slowest tested period (226 steps); the adaptive comparator's lag there is 72
   [45, 105] steps. World drift does not produce staleness (adaptive AIF +0.00 to +0.11 over no control, n.s.).
6. **Redundancy of free-energy machinery.** In the compatible regime, with 300 paired cell × seeds:
   * surprise-triggered rebuild: REDUNDANT for prediction and intervention, and **HARMFUL for recovery** (removing
     it improves recovery by +0.055 [0.039, 0.072]; also harmful in POST);
   * epistemic EFE term: REDUNDANT for prediction, intervention and recovery;
   * latent-state inference: REDUNDANT for prediction, intervention and recovery.

   These elements are **non-redundant** in all regimes:
   * boundary (intervention, recovery; also for the model-light controller);
   * policy (intervention and/or recovery);
   * prediction-error learning (prediction);
   * agent persistence (prediction in compatible and transition; structural-transition detection in POST);
   * transition model (recovery and prediction in compatible).

## 5. Integrity notes

* **Aborted runs:** none (no simulator, numerical, benchmark or comparator failure). Model-structure failures: 0,
  because the conservative tolerance prevents any fixed-model score from falling below 0.5.
* **Controller-failure flags: 9,070.** This is a single-run criterion (success more than 0.2 below no control) and
  reflects run-to-run variance; the regime-level paired contrasts above are the reliable comparison.
  Genuine regime transitions: 1,809 cell × seeds.
* **Pre-launch correction (documented):** research seeds changed from 1–30 to 11–40 to avoid duplicating development runs.
  No post-launch change to code, configuration or analysis. The frozen hashes were verified after completion.
* **Effect-size shrinkage from development to research.** In the compatible regime the AIF's advantage fell from
  +0.11 to +0.03, and in POST it reversed from +0.07 to −0.03. This is consistent with development estimates being
  optimistic: the task was designed while looking at seeds 1–3. The research figures are the ones to quote.

## 6. What would sharpen this (not done)

* Mean-based (not maximum-based) cell-level tolerance, to settle whether the variable- and model-driven transitions
  are real (Q2).
* More world graphs (generator seeds).
* An AIF variant given the tracker's information.
* A reverse severity sweep for hysteresis.
* Policy identity integrated over time.
* A long-memory world for history re-entry.
