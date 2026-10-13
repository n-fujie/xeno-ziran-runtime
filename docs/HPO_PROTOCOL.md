# HPO protocol — Heterogeneous Philosophical Operations (frozen before the confirmatory runs)

This file fixes the experiment plan, the seed ranges, the measures, the hypotheses with their success criteria, and
the stopping conditions **before** any confirmatory seed is run. Its SHA-256 is pinned in
`backend/xzr/hpo/experiments.py` (`PROTOCOL_SHA256`). The confirmatory runners refuse to start if this file differs
from the pinned hash, and every result records both hashes. Criteria are not changed after results are seen. If an
error is found later, it is recorded as an amendment with its date and reason, and the affected results are re-run
under a new hash. Superseded results are kept.

Scope: an engineering experiment on proxies named after philosophical operations, inside one simulated runtime.
Nothing here tests a philosophical doctrine, and no result is evidence for or against one
(`docs/HPO.md`, `xzr/hpo/registry.py`).

## 1. Development (before freezing)

Thresholds and rule parameters (`operations.DEFAULT_IGN`, `DEFAULT_RULE`) were calibrated on the development
seeds only: generator seeds 0–7 with engine seeds 1000–1007 (regime `intermittent`), and generator seed 3 with engine
seeds 101–103. The analysis pipeline was exercised on the smoke range (generator 9000+, engine 90000+; validation 9500+/95000+).
No confirmatory or held-out seed (below) was run before freezing.

## 2. World and run

* World: `latent_geometric`, n = 800, regime `intermittent` (the runtime's default dynamic regime), the engine's own
  input switched off and replaced by an exogenous stream with the same rate (0.004) and amplitude (0.9).
* Warm-up 40 steps shared by every branch of a seed; then 240 steps per branch.
* Paired branches of one seed share the initial world, the warm-up, the exogenous stream and the endogenous stream.
  The noise branch C~ differs only in the endogenous stream (seed + 7919).
* Operations: the six registry kinds, placed with `placement = shared` (overlapping regions in the two largest macro
  clusters; `field.place`).

## 3. Conditions

HPO-002 (per seed, 28 branches):

| id | settings |
|---|---|
| R0 | no HPO (world only) |
| A | independent operations: every interaction switch off |
| B | coupled: `share_info`, `share_resources`, `share_history` on |
| C | mutual transformation: every interaction switch on |
| C~ | C with another endogenous stream (false-positive control) |
| D | C + history reinsertion (`history.reinsert`, lag 60, every 40: archived data, archived veils, earlier ignition parameters) |
| E:k | C; at step 80 the essential channel of kind k is removed from that kind's instruments |
| F:k | E:k; at step 160 the kind is relocated to the next macro-cluster pair and the channel is restored |
| G:-x | D with one switch x off: transform, observation_change, competition_adapt, partition, reclassify, action_filter, share_info, share_resources, share_history, feedback |

Contrasts (29 per seed): B–A, C–B, C–A, C~–C, D–C, A–R0, C–R0, E:k–C (6), F:k–E:k (6), G:-x–D (10).

Seeds: HPO-002 confirmatory, 360 seeds (generator 100+i, engine 20000+i), giving 360 × 29 = 10,440 paired
comparisons. Generalization: 64 seeds per setting (generator 5000+i, engine 50000+i), with conditions R0, A, B, C, C~ and D
and contrasts B–A, C–B, C~–C, D–C and C–R0, in six settings not used in development: regimes `sparse`, `churn` and
`memory_heavy`; n = 1200; `placement = separate`; and the boundary change `veil_scale 0.5, gate_scale 1.5`.

HPO-001 (re-specified, because the pilot archive was not available): 64 seeds (generator 3000+i, engine 30000+i). Each
kind runs alone, with interaction off, once with its instrument and once with oracle (truth) access. The comparisons
are the R0 branch and a noise R0 branch.

HPO-003: 96 seeds (generator 4000+i, engine 40000+i), base condition D, four epochs of 60 steps, and three
controllers: static, recursive and random. The random controller makes the same number of changes per epoch as the
recursive one on the same seed. Proposal validation uses 64 held-out seeds (generator 4500+i, engine 45000+i). It is
run only for a proposed variable that has an implementation (currently `activity_trend`).

## 4. Measures and statistics

Measures are listed in `xzr/hpo/metrics.py` (ignition, transformation, reachability, cessation, re-ignition, history,
latency, real effects, unobservability, causal structure, per-kind ignition, re-ignition and cessation counts).

Statistics are computed per metric and per contrast, paired by seed (`xzr/hpo/stats.py`):

* the mean difference, d_z and a bootstrap 95 % interval (2,000 seeded resamples);
* a two-sided sign-flip test: exact up to 16 seeds, otherwise 20,000 seeded Monte Carlo patterns;
* Holm adjustment across the metrics of the contrast.

The noise floor of a metric is |mean(C~ − C)| + 1.96·se. Statuses:

* **DETECTED**: p_holm < 0.01, |mean| ≥ 2 % of scale, and |mean| > noise floor.
* **EQUIVALENT**: the 95 % interval lies within ±5 % of scale.
* **UNRESOLVED**: neither of the above.
* **IDENTICAL**: every pairwise difference is 0.
* **NOT MEASURED**: the metric is undefined in every pair.

Scale is the larger of the two absolute condition means. Contrasts against R0 use world measures only.

## 5. Hypotheses and success criteria (evaluated by `experiments.verdicts`)

* **H1 mutual transformation (C vs B).** SUPPORTED IN THIS PROXY requires all three of: `transformations` DETECTED
  with a positive mean; at least one world measure DETECTED; and at least one operation-level downstream measure
  DETECTED (ignitions, fired samples, cessations, re-ignitions, unobservable samples, final operation count, first
  ignition, ceased share, reach from regions, states visited). If only one of the last two holds, the verdict is
  PARTIAL; otherwise NOT SUPPORTED.
* **H2 historical reinsertion (D vs C).** SUPPORTED IN THIS PROXY requires a positive mean number of reinsertions
  in D and at least one world, operation-level, transformation, conflict or coupling measure DETECTED.
* **H3 cessation (E:k vs C).** For each kind: CONSEQUENCES DETECTED if any world, operation-level, transformation,
  filter or conflict measure is DETECTED.
* **H4 re-ignition (F:k vs E:k).** For each kind: DETECTED if `reignitions:k` is DETECTED and higher in F.
* **H5 ablation (G:-x vs D).** For each switch: CONTRIBUTES if any listed downstream measure is DETECTED.
* **H6 real effects (A, C vs R0).** The world measures that are DETECTED.
* **Generalization.** H1 and H2 are reported per setting. A result "generalizes" only if it is DETECTED in the same
  direction in at least half of the six settings.
* **HPO-003.** Recursive reconfiguration is "result-driven beyond change as such" for the measures DETECTED in both
  recursive vs static and recursive vs random. A proposal is "validated" only by its held-out criterion: lower
  `picturing_error`, DETECTED.

Negative and partial outcomes are reported with the same prominence as positive ones.

## 6. Stopping and validity conditions

* **False-positive control.** If more than 5 % of the measures of C~ vs C are DETECTED, the HPO-002 statuses are
  flagged invalid (`verdicts.control_noise.valid = false`) and are not interpreted.
* **Reproducibility.** Re-running seeds in one process must give identical measures (`experiments.reproducibility`)
  and identical HPO-003 reconfiguration traces. If either fails, the results are not published.
* **Sandbox.** Any reconfiguration outside `reconfig.SANDBOX` is rejected and counted. Any applied change outside it
  is a failure.
* **Regression.** The legacy test suites (backend, frontend, research) must pass unchanged, and published result
  files of earlier studies must be byte-identical to the pre-HPO baseline. If either check fails, publication of
  the viewer update is stopped (`docs/HPO_VERIFICATION.md`).
* **Compute.** Each confirmatory runner must finish in under 2 hours on 7 processes. If one does not, the seed count
  is reduced to the largest multiple of 8 that fits, and the reduction is recorded here as an amendment before that
  runner is run again.

## 7. Amendments

* **2026-10-13, amendment 1 (defect, no change to criteria).** The first confirmatory HPO-002 run under protocol
  hash `37c8b0a3ee7f…` stopped with an `IndexError` in `field._read_archive`. A composite's region had grown after
  its picture was formed, and an archived datum was written into a picture of a different size. The fix: a datum
  becomes a picture's prior only when the picture covers exactly the current categories and region. Nothing else
  changed. That run wrote no result, and the runs queued after it were stopped before writing any. Before the
  re-run, the fix was checked on the smoke range only: 200 jobs covering every HPO-002 condition, all
  generalization settings, HPO-001 and HPO-003, with no errors. All confirmatory runs are repeated under this
  file's new hash.
