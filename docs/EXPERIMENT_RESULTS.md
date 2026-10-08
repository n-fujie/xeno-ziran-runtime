# Experiment results — research phase

This file collects the results of the research phase and says, for each statement, what *kind* of statement it
is:

* **[measured]** comes straight from a result file;
* **[derived]** is a classification made by a fixed rule applied to measured results;
* **[choice]** is an implementation choice that the result depends on;
* **[interpretation]** is a philosophical reading, which the experiments do not establish;
* **[unresolved]** is an open question.

Details are in docs/REDUCTION.md (primitives), docs/MINIMAL_RUNTIME.md (the reduced runtime) and
docs/REASON_NONREDUNDANCY.md (reasoning layer). Performance is in docs/BENCHMARK.md.

## Reproduce

Results are machine-readable: `backend/experiments/results/{reduction,reason,final_results}.json`.

```bash
make experiments
```

This runs `experiments-reduction` (stage 1 + stage 2 + audits, about 25 minutes on 8 cores) and
`experiments-reason` (about 5 minutes). Afterwards, `python backend/scripts/make_reports.py` regenerates the data
blocks in this file and in REDUCTION.md, as well as `final_results.json`. The UI shows the same files under
**Research** (Reduction, Minimal primitives, Reason layer, Phases).

## 1. Primitive reduction

* **[measured]** Stage 2 ran 8 seeds × 1,200 steps in each of 4 regimes, with the variant's own outputs excluded.
  The noise control produced 0 detections. Per-primitive evidence is in the REDUCTION.md generated tables.
* **[derived]** Classification:

| | primitives |
|---|---|
| NON-REDUNDANT | threshold gating, retention, memory, transition, connection (closure) |
| NON-REDUNDANT (regime-dependent) | cut (intermittent; memory_heavy marginal), weight adaptation (intermittent, memory_heavy) |
| REDUCIBLE | ignition (into thresholded transition; bit-identical), reconfiguration (into connection mutation: remove + create; 0 stage-2 effects) |
| DERIVED | penetration (observer reconstructs it exactly), difference (relational: 0 effects), reachability (computed) |
| DESCRIPTIVE ONLY | transformation, return, decay |
| UNRESOLVED | disconnection (it fires, but has no downstream effect; the absence of a detected effect is not treated as redundancy) |

* **[choice]** The detection rule has several fixed parameters:
  * stage 1 counts a variant as exceeding when d > 2·noise + 0.02;
  * stage 2 counts an effect when |t| > 4 and the effect exceeds 2%;
  * the tests use N = 1,500 and the 4 regimes listed.

  A different rule or other regimes could move the regime-dependent rows. Cut and weight adaptation show no
  effect in *sparse* or *churn*.

## 2. MINIMAL runtime

* **[measured]** Full and MINIMAL runtimes are equivalent in every regime, with 0 stage-2 downstream effects. The
  worst criterion is at 0.54 of tolerance. The exact reductions are bit-identical (tests).
* **[derived]** MINIMAL has 5 primitives:
  1. thresholded transition;
  2. retention;
  3. memory;
  4. connection mutation (triggered by cut, disconnection, closure or reconfiguration);
  5. weight adaptation.
* **[choice]** Some reductions were not adopted:
  * relational difference was not adopted because it costs more;
  * disconnection was kept because its status is unresolved.

## 3. Reasoning layer

* **[measured]** Across 12,000 random states, the terminology-free support graph (greatest fixpoint) and
  scorekeeping never disagree.
* **[measured]** In the world, the two runs are bit-identical in 8/8 paired seeds, both with and without an edit,
  and in all 10 scenarios.
* **[measured]** Replaying the recorded intervention schedule reproduces the scorekeeping runs exactly in 10/10
  scenarios.
* **[measured]** The structural variants change which interventions are applied, in 72% of checks:
  * two-status vs single-status;
  * entitlement tracking on vs off;
  * fixpoint choice (on random graphs with cycles).

  Every disagreement is located in one of three causes: cycle, unentitled support, or conflict scope.
* **[measured]** No systematic world-level effect was detected for these structural variants.
* **[measured]** Reasoning vs no reasoning shows a world-level effect: memory dependence +157% (t = 9.1).
* **[measured]** On the 7 criteria, reasoning improves only two: error detection and dependency tracing.
* **[derived]** The commitment/entitlement vocabulary is **DESCRIPTIVE / INTERPRETIVE**.
* **[derived]** What is non-redundant at the intervention level is the **transition structure**:
  * two-status support propagation;
  * the scope of incompatibility resolution, with its persistence rule;
  * the fixpoint choice;
  * dependency records.
* **[derived]** At the world level, the only demonstrated difference is reasoning vs none. That difference is
  expressible as an operational schedule (replay).
* **[derived]** Error detection and dependency tracing are true by construction of the dependency records.
* **[choice]** The results depend on several choices:
  * the lab world and claim graph (`reason-lab`, 9 claims);
  * the groundings and the enabling thresholds (memory ≥ 0.7, calibrated on this world);
  * the check interval of 10 steps;
  * the world-level effect rule.
* **[interpretation]** Renaming the structure does not change anything operational. Brandom- or Wolfendale-style
  terms name structure, and the lab says nothing about whether that structure is what people do.

## 4. Phases and enabling conditions

* **[measured]** The phase timeline:
  * reasoning becomes active at t = 150;
  * it collapses at t = 470, after external memory is degraded at t = 450;
  * the commitment and entitlement distinctions are operative in 31/32 reasoning checks, and in 0 checks in the
    pre and collapsed phases.
* **[measured]** In the enabling matrix, forcing reasoning on removes its world-level effect when **external
  memory** is degraded.
* **[measured]** The effect is marginal when **repeated interaction** is degraded.
* **[measured]** Degrading **shared record persistence** removes the effect relative to no reasoning, and it is
  the only condition that makes persistent reasoning differ from the memoryless policy.
* **[measured]** Collapse from mutation starts at a connection-mutation rate of 0.002 in R.
* **[derived]** The minimum configuration for reasoning to be useful at the world level in this lab has three
  requirements:
  * an active record region whose memory the world does not override;
  * persistent records;
  * the interventions actually being in force.

  The other candidate conditions trigger collapse only when a gate is configured on them.
* **[choice]** Gated collapse is by construction: the gates are defined on those conditions.
* **[choice]** "Human" is not an enabling condition. Every condition is an operational measurement.

## 5. Closed loop

* **[measured]** The loop runs world → probes → grounded revision → compile → gate → world. Every change of
  intervention in the chain is attributed:
  * t = 90: enabled, 6 interventions added;
  * t = 100: grounded revision removes 2 interventions;
  * t = 310: external degradation;
  * t = 320: enabling fails, all interventions are removed, collapse.
* **[measured]** The reasoning layer never writes world state. Tests check this: the gate accepts only overlay
  records, and the world fingerprints are unchanged by reasoning-side calls.

## 6. Unresolved

* Disconnection has no demonstrated downstream effect, and it cannot be classified from that absence.
* Whether the reconfiguration trigger could be merged with the cut trigger has not been tested.
* Any world-level consequences of the two-status structure, or of counterfactual dependency structure, fall
  below this resolution: N = 1,500, 400 steps, 8 seeds.
* Compression over long horizons is untested.
* It is open whether grounded revision yields world-dependent schedules in richer worlds.
* The enabling thresholds may not transfer to other worlds.
* Rendering FPS was not re-measured in this phase because the host throttles `requestAnimationFrame`.

## 7. Generated tables

<!-- GENERATED:BEGIN -->
Result file: `backend/experiments/results/reason.json` · world effects: 8 paired world seeds × 400 steps, edit at t = 150 · enabling matrix: 6 seeds, degradation at t = 150, probe edit: remove concept human at t=250 · effect ⇔ |t| > 4 and > 2%; a single effect with |t| < 5 is *marginal*

### Reasoning world effects

| comparison | identical runs | interventions differ (share of checks) | world effect | effects (relative, paired t) |
|---|---|---|---|---|
| reasoning layer vs none | 0/8 | 0.75 | yes | memory_dependence +157% (t=9.1), new_connections +9% (t=6.5) |
| vocabulary: scorekeeping vs terminology-free support graph (greatest fixpoint) | 8/8 | 0.00 | no | — |
| vocabulary under an edit: same, after removing concept human | 8/8 | 0.00 | no | — |
| fixpoint choice: greatest vs least | 8/8 | 0.00 | no | — |
| two-status vs single-status | 0/8 | 0.72 | no | — |
| entitlement tracking on vs off | 0/8 | 0.72 | no | — |
| persistent reasoning state vs memoryless reactive policy | 0/8 | 0.35 | no | — |
| edit: remove concept human | 0/8 | 0.58 | marginal | memory_dependence -10% (t=-4.73) |
| edit: remove concept responsibility | 0/8 | 0.62 | no | — |
| counterfactual discrimination: same interventions, different dependency structure, same edit | 0/8 | 0.72 | no | — |

Schedule adaptivity (share of checks whose interventions differ between world seeds): scorekeeping 0.208 · memoryless 0.508 · none 0.0

### Enabling conditions

| degraded condition | measured by gate | gated: collapsed share | ungated: vs none | vs memoryless | counterfactual discrimination |
|---|---|---|---|---|---|
| none degraded (reference) | no | 0.0 | yes | no | marginal |
| external memory | yes | 0.833 | no | no | no |
| stable addressability | yes | 0.833 | yes | no | no |
| repeated interaction | yes | 0.333 | marginal | no | marginal |
| traceable dependency structure | yes | 0.833 | yes | no | no |
| incompatibility tracking | no | 0.0 | yes | no | no |
| inferential interface stability | no | 0.0 | yes | no | no |
| low mutation rate | yes | 0.833 | yes | no | marginal |
| shared record persistence | no | 0.13 | no | yes | no |

### Phases

Schedule: {'reasoning_from': 150, 'degrade_at': 450, 'degradation': 'memory condition on R (decay 0.3)', 'end': 700} · enabled at t = 150 · collapsed at t = 470 · first commitment distinction t = 160 · first entitlement distinction t = 160

| phase | checks | commitment distinction operative | entitlement distinction operative | intervention changes |
|---|---|---|---|---|
| pre | 14 | 0 | 0 | 0 |
| reasoning | 32 | 31 | 31 | 32 |
| collapsed | 24 | 0 | 0 | 1 |

Mutation sweep (connection mutation in R from t = 150; collapsed share after): 0.0: 0.0 · 0.0005: 0.0 · 0.001: 0.0 · 0.002: 0.96 · 0.004: 0.96 · 0.008: 0.96 · 0.016: 0.96
<!-- GENERATED:END -->

## 8. Operational resolution escalation (phase 3)

This phase asks whether the reasoning-structure differences found invisible in phase 2 are operationally redundant at
the world level, or were hidden by scale, topology, horizon, memory, coupling or observation resolution. It covers:
- 63 matrix conditions, plus the targeted disconnection, trigger-merge, world-responsive-revision, cluster and
  compression studies;
- 12 paired engine seeds per condition, and 48 in the power arm;
- worlds of 1,500 / 10,000 / 100,000 configurations, run for 400 / 4,000 / 40,000 steps.

Method, operational definitions and the result tables:
- docs/RESOLUTION_ESCALATION.md;
- docs/REASONING_CONFIGURATION_MAP.md;
- docs/DISCONNECTION.md;
- docs/SCALE_PENETRATION.md;
- docs/LONG_RUN_COMPRESSION.md.

Result files are in `backend/experiments/results/resolution/`:
- `matrix.json`, `disconnection.json`, `topology_triggers.json`, `adaptivity.json`, `clusters.json` and
  `compression.json`;
- `summary.json`, which is built from them;
- `jobs/`, holding every seed's raw run summaries for re-analysis.

Statement kinds, as above:
- **[measured]** the classification records below;
- **[derived]** the rules in `experiments/escalation/stats.py` and `summary.py`;
- **[choice]** the design and its omissions (listed in docs/RESOLUTION_ESCALATION.md);
- **[interpretation]** only in the docs' interpretation sections.

Provenance:
- **Runs.** The matrix ran from HEAD 2634e69 plus the uncommitted phase code. Later edits were verified
  behaviour-neutral with fixed fingerprints.
- **Analysis.** Every matrix condition was re-analysed from its persisted seed jobs with the final analysis code, and
  no classification changed.
- **Validation.** Every result row carries experiment, code state, condition, topology, configuration count,
  horizon, engine seeds, reasoning structure, variant, memory, coupling, mutation, addressability and a status per
  observation resolution. Rows missing any of these are quarantined, and none were.

### Answers to the seventeen questions (generated evidence records)

<!-- GENERATED:ESCALATION:BEGIN -->
### 1. Which reasoning structures are globally non-redundant?

Structures: **E, F, G, H, J, A**

| experiment | vs C | effect | noise CI (macro / global) | topology | n | steps | seeds | CI half (macro / global) | classification |
|---|---|---|---|---|---|---|---|---|---|
| matrix:n:100000 | A | global reconfigurations -93.4% | 1.6% / 0.7% | multi_region | 100,000 | 4,000 | 12 | 1.3% / 0.5% | NON-REDUNDANT |
| matrix:n:100000 | E | macro memory 5.3% | 1.6% / 0.7% | multi_region | 100,000 | 4,000 | 12 | 1.1% / 0.6% | NON-REDUNDANT |
| matrix:n:10000 | A | global reconfigurations -52.9% | 4.7% / 2.6% | multi_region | 10,000 | 4,000 | 12 | 3.8% / 2.5% | NON-REDUNDANT |
| matrix:n:10000 | F | macro activity 3.4% | 4.7% / 2.6% | multi_region | 10,000 | 4,000 | 12 | 3.1% / 2.1% | NON-REDUNDANT |
| matrix:n:100000:h400 | A | global reconfigurations -93.2% | 2.5% / 1.9% | multi_region | 100,000 | 400 | 12 | 1.2% / 1.1% | NON-REDUNDANT |
| matrix:n:100000:h400 | E | global memory_dependent_share 6.3% | 2.5% / 1.9% | multi_region | 100,000 | 400 | 12 | 1.0% / 0.4% | NON-REDUNDANT, TRANSIENT |
| matrix:n:100000:h400 | G | global memory_dependent_share -4.6% | 2.5% / 1.9% | multi_region | 100,000 | 400 | 12 | 0.9% / 0.6% | NON-REDUNDANT, TRANSIENT |
| matrix:n:100000:h400 | H | global memory_dependent_share -14.5% | 2.5% / 1.9% | multi_region | 100,000 | 400 | 12 | 1.3% / 1.2% | NON-REDUNDANT, TRANSIENT |
| matrix:reference | A | macro activity 10.2% | 12.1% / 8.2% | multi_region | 1,500 | 4,000 | 12 | 13.2% / 8.1% | NON-REDUNDANT, TRANSIENT |
| matrix:structure:unsupported_addressable | A | macro degree -17.3% | 9.9% / 5.9% | multi_region | 1,500 | 4,000 | 12 | 11.4% / 6.0% | NON-REDUNDANT |
| matrix:size:128 | A | global reconfigurations -52.7% | 10.6% / 4.7% | multi_region | 1,500 | 4,000 | 12 | 11.4% / 7.0% | NON-REDUNDANT, TRANSIENT |
| matrix:size:128 | E | macro difference -18.9% | 10.6% / 4.7% | multi_region | 1,500 | 4,000 | 12 | 11.5% / 7.5% | NON-REDUNDANT, TIME-WINDOW-DEPENDENT |
| … 34 more rows in summary.json | | | | | | | | | |

### 2. Which are only locally non-redundant?

Structures: **none**

### 3. Which are hidden at coarse resolution?

Structures: **A, D, E, F, G, H, J, K**

| experiment | vs C | effect | noise CI (macro / global) | topology | n | steps | seeds | CI half (macro / global) | classification |
|---|---|---|---|---|---|---|---|---|---|
| matrix:n:100000 | F | median |Δ| global 0.5%; divergence ratio 0.69 | 1.6% / 0.7% | multi_region | 100,000 | 4,000 | 12 | 1.5% / 0.7% | HIDDEN AT COARSE RESOLUTION |
| matrix:horizon:40000 | A | local degree 49.2% | 25.5% / 13.5% | multi_region | 1,500 | 40,000 | 12 | 19.5% / 11.0% | UNRESOLVED, HIDDEN AT COARSE RESOLUTION |
| matrix:n:10000 | E | median |Δ| global 0.7%; divergence ratio 1.67 | 4.7% / 2.6% | multi_region | 10,000 | 4,000 | 12 | 4.2% / 2.0% | HIDDEN AT COARSE RESOLUTION |
| matrix:n:10000 | G | median |Δ| global 0.7%; divergence ratio 1.02 | 4.7% / 2.6% | multi_region | 10,000 | 4,000 | 12 | 3.5% / 2.1% | HIDDEN AT COARSE RESOLUTION |
| matrix:n:10000 | H | median |Δ| global 0.4%; divergence ratio 0.83 | 4.7% / 2.6% | multi_region | 10,000 | 4,000 | 12 | 3.7% / 2.2% | HIDDEN AT COARSE RESOLUTION |
| matrix:n:100000:h400 | F | median |Δ| global 0.1%; divergence ratio 0.69 | 2.5% / 1.9% | multi_region | 100,000 | 400 | 12 | 1.1% / 0.7% | HIDDEN AT COARSE RESOLUTION |
| matrix:structure:unsupported_addressable | J | median |Δ| global 1.6%; divergence ratio 0.62 | 9.9% / 5.9% | multi_region | 1,500 | 4,000 | 12 | 3.9% / 2.7% | HIDDEN AT COARSE RESOLUTION |
| matrix:size:9 | A | node activity -9.8% | 10.6% / 7.9% | multi_region | 1,500 | 4,000 | 12 | 13.5% / 9.6% | UNRESOLVED, HIDDEN AT COARSE RESOLUTION |
| matrix:size:9 | E | local difference -73.6% | 10.6% / 7.9% | multi_region | 1,500 | 4,000 | 12 | 11.6% / 7.4% | UNRESOLVED, HIDDEN AT COARSE RESOLUTION |
| matrix:size:128 | F | median |Δ| global 0.3%; divergence ratio 0.00 | 10.6% / 4.7% | multi_region | 1,500 | 4,000 | 12 | 1.3% / 0.6% | HIDDEN AT COARSE RESOLUTION |
| matrix:memory:near_zero | J | median |Δ| global 2.7%; divergence ratio 0.58 | 9.7% / 5.8% | multi_region | 1,500 | 4,000 | 12 | 4.5% / 1.9% | HIDDEN AT COARSE RESOLUTION |
| matrix:memory:short | J | median |Δ| global 0.4%; divergence ratio 0.71 | 11.2% / 6.2% | multi_region | 1,500 | 4,000 | 12 | 4.1% / 2.5% | HIDDEN AT COARSE RESOLUTION |
| … 80 more rows in summary.json | | | | | | | | | |

### 4. Which are topology-dependent?

Structures: **H**

| experiment | vs C | effect | noise CI (macro / global) | topology | n | steps | seeds | CI half (macro / global) | classification |
|---|---|---|---|---|---|---|---|---|---|
| matrix:reference | H | median |Δ| global 2.7%; divergence ratio 0.76 | 12.1% / 8.2% | multi_region | 1,500 | 4,000 | 12 | 11.1% / 5.9% | UNRESOLVED |
| matrix:topology:sparse_random | H | median |Δ| global 2.6%; divergence ratio 1.09 | 8.3% / 4.6% | sparse_random | 1,500 | 4,000 | 12 | 7.6% / 5.6% | UNRESOLVED |
| matrix:topology:dense_random | H | median |Δ| global 6.3%; divergence ratio 0.37 | 21.3% / 14.9% | dense_random | 1,500 | 4,000 | 12 | 8.6% / 6.9% | UNRESOLVED |
| matrix:topology:modular | H | median |Δ| global 0.4%; divergence ratio 1.29 | 3.9% / 2.4% | modular | 1,500 | 4,000 | 12 | 3.2% / 1.7% | HIDDEN AT COARSE RESOLUTION |
| matrix:topology:hierarchical | H | median |Δ| global 0.7%; divergence ratio 0.90 | 10.7% / 5.2% | hierarchical | 1,500 | 4,000 | 12 | 6.9% / 5.8% | UNRESOLVED |
| matrix:topology:small_world | H | median |Δ| global 1.0%; divergence ratio 1.48 | 6.8% / 5.7% | small_world | 1,500 | 4,000 | 12 | 7.8% / 5.2% | UNRESOLVED |
| matrix:topology:highly_clustered | H | median |Δ| global 1.6%; divergence ratio 1.08 | 9.9% / 6.8% | highly_clustered | 1,500 | 4,000 | 12 | 13.1% / 6.4% | UNRESOLVED |
| matrix:topology:weakly_connected | H | median |Δ| global 3.2%; divergence ratio 0.64 | 13.0% / 5.7% | weakly_connected | 1,500 | 4,000 | 12 | 9.8% / 5.7% | UNRESOLVED |
| matrix:topology:bottlenecked | H | median |Δ| global 0.8%; divergence ratio 0.63 | 10.8% / 6.6% | bottlenecked | 1,500 | 4,000 | 12 | 7.5% / 6.6% | UNRESOLVED |
| matrix:topology:nested_multiscale | H | median |Δ| global 5.0%; divergence ratio 0.66 | 19.2% / 12.8% | nested_multiscale | 1,500 | 4,000 | 12 | 11.9% / 8.9% | UNRESOLVED |
| matrix:strong×topology:sparse_random | H | median |Δ| global 5.5%; divergence ratio 1.70 | 10.0% / 6.3% | sparse_random | 1,500 | 4,000 | 12 | 9.3% / 8.1% | UNRESOLVED |
| matrix:strong×topology:dense_random | H | median |Δ| global 1.5%; divergence ratio 0.40 | 18.6% / 13.0% | dense_random | 1,500 | 4,000 | 12 | 13.4% / 9.0% | UNRESOLVED |
| … 7 more rows in summary.json | | | | | | | | | |

### 5. Which are time-window-dependent?

Structures: **A, E, H**

| experiment | vs C | effect | noise CI (macro / global) | topology | n | steps | seeds | CI half (macro / global) | classification |
|---|---|---|---|---|---|---|---|---|---|
| matrix:horizon:40000 | A | local degree 49.2% | 25.5% / 13.5% | multi_region | 1,500 | 40,000 | 12 | 19.5% / 11.0% | UNRESOLVED, HIDDEN AT COARSE RESOLUTION |
| matrix:horizon:40000 | E | median |Δ| global 3.0%; divergence ratio 3.02 | 25.5% / 13.5% | multi_region | 1,500 | 40,000 | 12 | 22.0% / 15.6% | UNRESOLVED |
| matrix:horizon:40000 | H | median |Δ| global 1.1%; divergence ratio 2.41 | 25.5% / 13.5% | multi_region | 1,500 | 40,000 | 12 | 18.5% / 11.6% | UNRESOLVED |
| matrix:reference | A | macro activity 10.2% | 12.1% / 8.2% | multi_region | 1,500 | 4,000 | 12 | 13.2% / 8.1% | NON-REDUNDANT, TRANSIENT |
| matrix:reference | E | median |Δ| global 2.5%; divergence ratio 0.70 | 12.1% / 8.2% | multi_region | 1,500 | 4,000 | 12 | 11.8% / 5.6% | UNRESOLVED |
| matrix:reference | H | median |Δ| global 2.7%; divergence ratio 0.76 | 12.1% / 8.2% | multi_region | 1,500 | 4,000 | 12 | 11.1% / 5.9% | UNRESOLVED |
| matrix:horizon:400 | A | global reconfigurations -47.7% | 19.1% / 11.5% | multi_region | 1,500 | 400 | 12 | 9.4% / 4.2% | NON-REDUNDANT |
| matrix:horizon:400 | E | macro activity -10.2% | 19.1% / 11.5% | multi_region | 1,500 | 400 | 12 | 6.9% / 4.1% | NON-REDUNDANT, TRANSIENT |
| matrix:horizon:400 | H | median |Δ| global 1.9%; divergence ratio 0.55 | 19.1% / 11.5% | multi_region | 1,500 | 400 | 12 | 8.6% / 4.7% | UNRESOLVED |

### 6. Which are memory-dependent?

Structures: **none**

### 7. Which remain redundant across all tested configurations?

Structures: **B, I**

| experiment | vs C | effect | noise CI (macro / global) | topology | n | steps | seeds | CI half (macro / global) | classification |
|---|---|---|---|---|---|---|---|---|---|
| matrix:n:10000 | I | median |Δ| global 0.0%; divergence ratio 0.00 | 4.7% / 2.6% | multi_region | 10,000 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:n:100000:h400 | I | median |Δ| global 0.0%; divergence ratio 0.00 | 2.5% / 1.9% | multi_region | 100,000 | 400 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:reference | I | median |Δ| global 0.0%; divergence ratio 0.00 | 12.1% / 8.2% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:reference | B | median |Δ| global 0.0%; divergence ratio 0.00 | 12.1% / 8.2% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:structure:strongly_cyclic | I | median |Δ| global 0.0%; divergence ratio 0.00 | 12.9% / 6.9% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:structure:strongly_cyclic | B | median |Δ| global 0.0%; divergence ratio 0.00 | 12.9% / 6.9% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:structure:multi_cycles | I | median |Δ| global 0.0%; divergence ratio 0.00 | 12.9% / 6.9% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:structure:multi_cycles | B | median |Δ| global 0.0%; divergence ratio 0.00 | 12.9% / 6.9% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:structure:dense_conflicts | I | median |Δ| global 0.0%; divergence ratio 0.00 | 10.0% / 4.1% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:structure:dense_conflicts | B | median |Δ| global 0.0%; divergence ratio 0.00 | 10.0% / 4.1% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:structure:unsupported_addressable | I | median |Δ| global 0.0%; divergence ratio 0.00 | 9.9% / 5.9% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:structure:unsupported_addressable | B | median |Δ| global 0.0%; divergence ratio 0.00 | 9.9% / 5.9% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| … 45 more rows in summary.json | | | | | | | | | |

### 8. Which remain unresolved?

Structures: **D, K**
- per structure (unresolved / hidden / conditions): D 1/4/60; E 45/13/63; F 34/17/63; G 24/16/51; H 40/13/63; I 0/0/49; J 11/10/25; K 6/9/49

| experiment | vs C | effect | noise CI (macro / global) | topology | n | steps | seeds | CI half (macro / global) | classification |
|---|---|---|---|---|---|---|---|---|---|
| matrix:structure:unsupported_addressable | D | median |Δ| global 0.8%; divergence ratio 0.65 | 9.9% / 5.9% | multi_region | 1,500 | 4,000 | 12 | 9.0% / 3.2% | UNRESOLVED |
| matrix:size:128 | K | median |Δ| global 1.6%; divergence ratio 1.41 | 10.6% / 4.7% | multi_region | 1,500 | 4,000 | 12 | 13.4% / 7.4% | UNRESOLVED |
| matrix:memory:fragmented | K | median |Δ| global 5.0%; divergence ratio 0.00 | 14.3% / 7.5% | multi_region | 1,500 | 4,000 | 12 | 9.1% / 8.0% | UNRESOLVED |
| matrix:coupling:strong | K | median |Δ| global 1.2%; divergence ratio 1.13 | 11.7% / 7.7% | multi_region | 1,500 | 4,000 | 12 | 9.2% / 4.7% | UNRESOLVED |
| matrix:structure:mixed_fixpoint_regions | K | median |Δ| global 3.8%; divergence ratio 0.05 | 11.9% / 7.7% | multi_region | 1,500 | 4,000 | 12 | 6.8% / 4.3% | UNRESOLVED |
| matrix:structure:multiple_clusters | K | median |Δ| global 5.7%; divergence ratio 0.74 | 10.6% / 5.6% | multi_region | 1,500 | 4,000 | 12 | 9.9% / 5.7% | UNRESOLVED |
| matrix:structure:partially_incompatible_rules | K | median |Δ| global 2.3%; divergence ratio 0.61 | 8.9% / 4.8% | multi_region | 1,500 | 4,000 | 12 | 8.8% / 4.2% | UNRESOLVED |

### 9. Under what exact configuration does reasoning become operationally non-redundant?


reasoning vs none:

| experiment | vs C | effect | noise CI (macro / global) | topology | n | steps | seeds | CI half (macro / global) | classification |
|---|---|---|---|---|---|---|---|---|---|
| matrix:n:100000 | A | global reconfigurations -93.4% | 1.6% / 0.7% | multi_region | 100,000 | 4,000 | 12 | 1.3% / 0.5% | NON-REDUNDANT |
| matrix:n:10000 | A | global reconfigurations -52.9% | 4.7% / 2.6% | multi_region | 10,000 | 4,000 | 12 | 3.8% / 2.5% | NON-REDUNDANT |
| matrix:n:100000:h400 | A | global reconfigurations -93.2% | 2.5% / 1.9% | multi_region | 100,000 | 400 | 12 | 1.2% / 1.1% | NON-REDUNDANT |
| matrix:reference | A | macro activity 10.2% | 12.1% / 8.2% | multi_region | 1,500 | 4,000 | 12 | 13.2% / 8.1% | NON-REDUNDANT, TRANSIENT |
| matrix:structure:unsupported_addressable | A | macro degree -17.3% | 9.9% / 5.9% | multi_region | 1,500 | 4,000 | 12 | 11.4% / 6.0% | NON-REDUNDANT |
| matrix:size:128 | A | global reconfigurations -52.7% | 10.6% / 4.7% | multi_region | 1,500 | 4,000 | 12 | 11.4% / 7.0% | NON-REDUNDANT, TRANSIENT |
| matrix:memory:near_zero | A | global new_connections 10.9% | 9.7% / 5.8% | multi_region | 1,500 | 4,000 | 12 | 8.8% / 7.1% | NON-REDUNDANT |
| matrix:memory:short | A | macro activity 25.7% | 11.2% / 6.2% | multi_region | 1,500 | 4,000 | 12 | 11.0% / 5.5% | NON-REDUNDANT, TIME-WINDOW-DEPENDENT |
| matrix:memory:long | A | global reconfigurations -70.1% | 12.3% / 5.1% | multi_region | 1,500 | 4,000 | 12 | 11.7% / 6.0% | NON-REDUNDANT, TRANSIENT |
| matrix:memory:external_persistent | A | macro difference 19.5% | 11.0% / 7.3% | multi_region | 1,500 | 4,000 | 12 | 6.7% / 5.6% | NON-REDUNDANT, TIME-WINDOW-DEPENDENT |
| matrix:memory:delayed_return | A | macro activity 37.4% | 16.4% / 8.7% | multi_region | 1,500 | 4,000 | 12 | 14.4% / 8.5% | NON-REDUNDANT, TIME-WINDOW-DEPENDENT |
| matrix:mutation:high_state | A | global reconfigurations -42.6% | 4.2% / 2.0% | multi_region | 1,500 | 4,000 | 12 | 3.3% / 1.6% | NON-REDUNDANT |
| … 22 more rows in summary.json | | | | | | | | | |

structure differences:

| experiment | vs C | effect | noise CI (macro / global) | topology | n | steps | seeds | CI half (macro / global) | classification |
|---|---|---|---|---|---|---|---|---|---|
| matrix:n:100000 | E | macro memory 5.3% | 1.6% / 0.7% | multi_region | 100,000 | 4,000 | 12 | 1.1% / 0.6% | NON-REDUNDANT |
| matrix:n:100000 | H | meso memory -3.2% | 1.6% / 0.7% | multi_region | 100,000 | 4,000 | 12 | 1.3% / 0.6% | NON-REDUNDANT, TRANSIENT |
| matrix:n:10000 | F | macro activity 3.4% | 4.7% / 2.6% | multi_region | 10,000 | 4,000 | 12 | 3.1% / 2.1% | NON-REDUNDANT |
| matrix:n:100000:h400 | E | global memory_dependent_share 6.3% | 2.5% / 1.9% | multi_region | 100,000 | 400 | 12 | 1.0% / 0.4% | NON-REDUNDANT, TRANSIENT |
| matrix:n:100000:h400 | G | global memory_dependent_share -4.6% | 2.5% / 1.9% | multi_region | 100,000 | 400 | 12 | 0.9% / 0.6% | NON-REDUNDANT, TRANSIENT |
| matrix:n:100000:h400 | H | global memory_dependent_share -14.5% | 2.5% / 1.9% | multi_region | 100,000 | 400 | 12 | 1.3% / 1.2% | NON-REDUNDANT, TRANSIENT |
| matrix:structure:unsupported_addressable | H | meso degree -2.8% | 9.9% / 5.9% | multi_region | 1,500 | 4,000 | 12 | 10.3% / 5.6% | NON-REDUNDANT, TRANSIENT |
| matrix:size:128 | E | macro difference -18.9% | 10.6% / 4.7% | multi_region | 1,500 | 4,000 | 12 | 11.5% / 7.5% | NON-REDUNDANT, TIME-WINDOW-DEPENDENT |
| matrix:size:128 | H | global reachable_share 2.1% | 10.6% / 4.7% | multi_region | 1,500 | 4,000 | 12 | 11.5% / 6.5% | NON-REDUNDANT, TRANSIENT |
| matrix:size:128 | J | global reconfigurations 53.0% | 10.6% / 4.7% | multi_region | 1,500 | 4,000 | 12 | 6.2% / 4.1% | NON-REDUNDANT |
| matrix:memory:delayed_return | H | global memory 8.6% | 16.4% / 8.7% | multi_region | 1,500 | 4,000 | 12 | 13.8% / 4.5% | NON-REDUNDANT, TRANSIENT, TIME-WINDOW-DEPENDENT |
| matrix:mutation:high_state | E | macro activity -10.4% | 4.2% / 2.0% | multi_region | 1,500 | 4,000 | 12 | 3.5% / 2.1% | NON-REDUNDANT |
| … 9 more rows in summary.json | | | | | | | | | |

### 10. Under what exact configuration does reasoning collapse?


Rule: reasoning inactive for most of the run: collapsed (enabled, then failed) or never enabled

| experiment | reasoning active | collapsed | never enabled | topology | memory | mutation | address | n | steps |
|---|---|---|---|---|---|---|---|---|---|
| matrix:address:highly_unstable | 0.0% | 0.0% | 95.2% | multi_region | medium | low | highly_unstable | 1500 | 4000 |
| matrix:topology:sparse_random | 1.7% | 93.6% | 0.0% | sparse_random | medium | low | stable | 1500 | 4000 |
| matrix:strong×topology:sparse_random | 2.3% | 92.9% | 0.0% | sparse_random | medium | low | stable | 1500 | 4000 |
| matrix:mutation:medium_topology | 7.0% | 88.3% | 0.0% | multi_region | medium | medium_topology | stable | 1500 | 4000 |
| matrix:mutation:high_topology | 8.1% | 69.2% | 17.9% | multi_region | medium | high_topology | stable | 1500 | 4000 |
| matrix:horizon:40000 | 29.0% | 70.5% | 0.0% | multi_region | medium | low | stable | 1500 | 40000 |
| matrix:address:locally_stable_globally_unstable | 34.8% | 60.5% | 0.0% | multi_region | medium | low | locally_stable_globally_unstable | 1500 | 4000 |
| matrix:memory:long | 35.6% | 59.6% | 0.0% | multi_region | long | low | stable | 1500 | 4000 |

### 11. Does world-responsive revision create genuine adaptivity?

- adaptivity:none: gating only adaptivity 0.6339; scripted adaptivity 0.0; closed loop adaptivity 0.9138; world responsive part 0.2799; firings followed by return 0.4747; random checks followed by return 0.4345; response paired t 3.05; genuinely world responsive False
  - control precision vs: {'C-S': 'no significant difference', 'C-M': 'no significant difference', 'C-R': 'no significant difference', 'C-A': 'no significant difference'}
  - world effect vs: {'C~': 'UNRESOLVED', 'S': 'NON-REDUNDANT', 'M': 'NON-REDUNDANT', 'R': 'UNRESOLVED', 'A': 'UNRESOLVED'}
- adaptivity:state: gating only adaptivity 0.0004; scripted adaptivity 0.0; closed loop adaptivity 0.9271; world responsive part 0.9267; firings followed by return 0.0917; random checks followed by return 0.0462; response paired t 3.62; genuinely world responsive True
  - control precision vs: {'C-S': 'better', 'C-M': 'no significant difference', 'C-R': 'better', 'C-A': 'better'}
  - world effect vs: {'C~': 'HIDDEN AT COARSE RESOLUTION', 'S': 'NON-REDUNDANT', 'M': 'NON-REDUNDANT', 'R': 'HIDDEN AT COARSE RESOLUTION', 'A': 'NON-REDUNDANT'}
- adaptivity:mixed: gating only adaptivity 0.1669; scripted adaptivity 0.0; closed loop adaptivity 0.7931; world responsive part 0.6262; firings followed by return 0.1685; random checks followed by return 0.0594; response paired t 4.11; genuinely world responsive True
  - control precision vs: {'C-S': 'no significant difference', 'C-M': 'no significant difference', 'C-R': 'no significant difference', 'C-A': 'no significant difference'}
  - world effect vs: {'C~': 'UNRESOLVED', 'S': 'NON-REDUNDANT', 'M': 'NON-REDUNDANT', 'R': 'UNRESOLVED', 'A': 'NON-REDUNDANT'}

### 12. Does the vocabulary-bearing representation (variant B) remain purely interpretive?

- bit identical in all conditions: True
- conditions: 8

| experiment | vs C | effect | noise CI (macro / global) | topology | n | steps | seeds | CI half (macro / global) | classification |
|---|---|---|---|---|---|---|---|---|---|
| matrix:reference | B | median |Δ| global 0.0%; divergence ratio 0.00 | 12.1% / 8.2% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:structure:strongly_cyclic | B | median |Δ| global 0.0%; divergence ratio 0.00 | 12.9% / 6.9% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:structure:multi_cycles | B | median |Δ| global 0.0%; divergence ratio 0.00 | 12.9% / 6.9% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:structure:dense_conflicts | B | median |Δ| global 0.0%; divergence ratio 0.00 | 10.0% / 4.1% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:structure:unsupported_addressable | B | median |Δ| global 0.0%; divergence ratio 0.00 | 9.9% / 5.9% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:size:9 | B | median |Δ| global 0.0%; divergence ratio 0.00 | 10.6% / 7.9% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:size:128 | B | median |Δ| global 0.0%; divergence ratio 0.00 | 10.6% / 4.7% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| matrix:horizon:400 | B | median |Δ| global 0.0%; divergence ratio 0.00 | 19.1% / 11.5% | multi_region | 1,500 | 400 | 12 | 0.0% / 0.0% | REDUNDANT |

### 13. Is disconnection reducible?

- verdict: **REDUCIBLE**
- removal detected in: ['disconnection:bottleneck', 'disconnection:fragile_loop', 'disconnection:one_way_path', 'disconnection:delayed_return_route', 'disconnection:high_path_dependence', 'disconnection:isolated_regions_bridge']
- equivalent replacements: ['as_cut', 'as_mutation']

| experiment | vs C | effect | noise CI (macro / global) | topology | n | steps | seeds | CI half (macro / global) | classification |
|---|---|---|---|---|---|---|---|---|---|
| disconnection:disconnection:single_bridge | off | median |Δ| global 13.9%; divergence ratio 1.25 | 23.4% / 11.6% | multi_region | 1,500 | 4,000 | 12 | 35.8% / 10.7% | UNRESOLVED |
| disconnection:disconnection:single_bridge | weight_zero | median |Δ| global 11.1%; divergence ratio 0.88 | 23.4% / 11.6% | multi_region | 1,500 | 4,000 | 12 | 23.4% / 8.2% | UNRESOLVED |
| disconnection:disconnection:single_bridge | as_cut | median |Δ| global 0.0%; divergence ratio 0.00 | 23.4% / 11.6% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | HIDDEN AT COARSE RESOLUTION |
| disconnection:disconnection:single_bridge | as_mutation | median |Δ| global 0.0%; divergence ratio 0.00 | 23.4% / 11.6% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| disconnection:disconnection:single_bridge | redirect | global difference 58.7% | 23.4% / 11.6% | multi_region | 1,500 | 4,000 | 12 | 49.9% / 14.1% | NON-REDUNDANT, TIME-WINDOW-DEPENDENT |
| disconnection:disconnection:bottleneck | off | global new_connections -13.8% | 17.2% / 10.5% | multi_region | 1,500 | 4,000 | 12 | 49.2% / 7.8% | NON-REDUNDANT, TRANSIENT |
| disconnection:disconnection:bottleneck | weight_zero | median |Δ| global 8.4%; divergence ratio 1.14 | 17.2% / 10.5% | multi_region | 1,500 | 4,000 | 12 | 46.6% / 7.8% | UNRESOLVED |
| disconnection:disconnection:bottleneck | as_cut | median |Δ| global 0.0%; divergence ratio 0.00 | 17.2% / 10.5% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| disconnection:disconnection:bottleneck | as_mutation | median |Δ| global 0.0%; divergence ratio 0.00 | 17.2% / 10.5% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| disconnection:disconnection:bottleneck | redirect | global difference 74.1% | 17.2% / 10.5% | multi_region | 1,500 | 4,000 | 12 | 61.5% / 8.2% | NON-REDUNDANT |
| disconnection:disconnection:sparse_tree | off | median |Δ| global 4.6%; divergence ratio 3.65 | 29.5% / 19.1% | multi_region | 1,500 | 4,000 | 12 | 18.4% / 15.8% | UNRESOLVED |
| disconnection:disconnection:sparse_tree | weight_zero | median |Δ| global 6.2%; divergence ratio 1.00 | 29.5% / 19.1% | multi_region | 1,500 | 4,000 | 12 | 6.7% / 14.1% | UNRESOLVED |
| … 28 more rows in summary.json | | | | | | | | | |

### 14. Can cut and reconfiguration triggers be merged?

- verdict: **conditionally necessary**
- operation shared: shared (equivalent in every regime; not bit-identical)
- conditions distinct: distinct: merging the conditions changes behaviour in unified: topology_trigger:default, topology_trigger:long_memory, topology_trigger:high_mutation, topology_trigger:bottlenecked, topology_trigger:modular, topology_trigger:small_world, topology_trigger:dense_random; merged: topology_trigger:default, topology_trigger:long_memory, topology_trigger:high_mutation, topology_trigger:bottlenecked, topology_trigger:modular, topology_trigger:small_world, topology_trigger:dense_random
- removal detected in: {'cut_only': ['topology_trigger:default', 'topology_trigger:small_world', 'topology_trigger:dense_random'], 'reconfigure_only': ['topology_trigger:default', 'topology_trigger:long_memory', 'topology_trigger:high_mutation', 'topology_trigger:bottlenecked', 'topology_trigger:modular', 'topology_trigger:small_world', 'topology_trigger:dense_random']}

| experiment | vs C | effect | noise CI (macro / global) | topology | n | steps | seeds | CI half (macro / global) | classification |
|---|---|---|---|---|---|---|---|---|---|
| topology_triggers:topology_trigger:default | cut_only | meso memory 17.2% | 12.1% / 6.1% | multi_region | 1,500 | 4,000 | 12 | 12.0% / 5.9% | NON-REDUNDANT, TRANSIENT, TIME-WINDOW-DEPENDENT |
| topology_triggers:topology_trigger:default | reconfigure_only | global penetrations 94.1% | 12.1% / 6.1% | multi_region | 1,500 | 4,000 | 12 | 12.8% / 7.7% | NON-REDUNDANT, TIME-WINDOW-DEPENDENT |
| topology_triggers:topology_trigger:default | unified | global new_connections -17.9% | 12.1% / 6.1% | multi_region | 1,500 | 4,000 | 12 | 9.0% / 7.7% | NON-REDUNDANT, TIME-WINDOW-DEPENDENT |
| topology_triggers:topology_trigger:default | generic_conditions | median |Δ| global 0.0%; divergence ratio 0.00 | 12.1% / 6.1% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | HIDDEN AT COARSE RESOLUTION |
| topology_triggers:topology_trigger:default | merged | local degree -71.8% | 12.1% / 6.1% | multi_region | 1,500 | 4,000 | 12 | 11.3% / 9.1% | UNRESOLVED, HIDDEN AT COARSE RESOLUTION |
| topology_triggers:topology_trigger:long_memory | cut_only | median |Δ| global 4.2%; divergence ratio 0.81 | 13.5% / 5.9% | multi_region | 1,500 | 4,000 | 12 | 11.5% / 4.1% | UNRESOLVED |
| topology_triggers:topology_trigger:long_memory | reconfigure_only | global new_connections -8.8% | 13.5% / 5.9% | multi_region | 1,500 | 4,000 | 12 | 12.3% / 4.9% | NON-REDUNDANT, TIME-WINDOW-DEPENDENT |
| topology_triggers:topology_trigger:long_memory | unified | global new_connections -7.8% | 13.5% / 5.9% | multi_region | 1,500 | 4,000 | 12 | 13.3% / 5.2% | NON-REDUNDANT, TIME-WINDOW-DEPENDENT |
| topology_triggers:topology_trigger:long_memory | generic_conditions | median |Δ| global 0.0%; divergence ratio 0.00 | 13.5% / 5.9% | multi_region | 1,500 | 4,000 | 12 | 0.0% / 0.0% | REDUNDANT |
| topology_triggers:topology_trigger:long_memory | merged | node degree -67.7% | 13.5% / 5.9% | multi_region | 1,500 | 4,000 | 12 | 12.6% / 6.6% | UNRESOLVED, HIDDEN AT COARSE RESOLUTION |
| topology_triggers:topology_trigger:high_mutation | cut_only | median |Δ| global 0.3%; divergence ratio 0.68 | 1.6% / 1.0% | multi_region | 1,500 | 4,000 | 12 | 1.6% / 1.3% | HIDDEN AT COARSE RESOLUTION |
| topology_triggers:topology_trigger:high_mutation | reconfigure_only | global alive_connections 2.0% | 1.6% / 1.0% | multi_region | 1,500 | 4,000 | 12 | 1.6% / 1.4% | NON-REDUNDANT, TIME-WINDOW-DEPENDENT |
| … 23 more rows in summary.json | | | | | | | | | |

### 15. Does long-run compression preserve intervention-relevant distinctions?

- 400: compression ratio C 1.2363; replay r2 C 0.947
  - pairs: {'D': {'distinction_preserved': True, 'systematic_agree': True, 'distance_ratio_close': True, 'onset_lost_seeds': 0, 'hidden_local_retained': False}, 'F': {'distinction_preserved': False, 'systematic_agree': True, 'distance_ratio_close': False, 'onset_lost_seeds': 0, 'hidden_local_retained': False}, 'A': {'distinction_preserved': False, 'systematic_agree': False, 'distance_ratio_close': True, 'onset_lost_seeds': 0, 'hidden_local_retained': False}}
- 4000: compression ratio C 11.9295; replay r2 C 0.8238
  - pairs: {'D': {'distinction_preserved': True, 'systematic_agree': True, 'distance_ratio_close': True, 'onset_lost_seeds': 0, 'hidden_local_retained': False}, 'F': {'distinction_preserved': True, 'systematic_agree': True, 'distance_ratio_close': True, 'onset_lost_seeds': 0, 'hidden_local_retained': False}, 'A': {'distinction_preserved': True, 'systematic_agree': True, 'distance_ratio_close': True, 'onset_lost_seeds': 0, 'hidden_local_retained': False}}
- 40000: compression ratio C 93.6971; replay r2 C 0.8752
  - pairs: {'D': {'distinction_preserved': True, 'systematic_agree': True, 'distance_ratio_close': True, 'onset_lost_seeds': 0, 'hidden_local_retained': False}, 'F': {'distinction_preserved': True, 'systematic_agree': True, 'distance_ratio_close': True, 'onset_lost_seeds': 0, 'hidden_local_retained': False}, 'A': {'distinction_preserved': True, 'systematic_agree': True, 'distance_ratio_close': True, 'onset_lost_seeds': 0, 'hidden_local_retained': True}}

### 16. What is the smallest world / scale / time window where reasoning structure changes world behavior?

- smallest n: 1500
- smallest horizon: 400
- smallest structure size: 32

| experiment | vs C | effect | noise CI (macro / global) | topology | n | steps | seeds | CI half (macro / global) | classification |
|---|---|---|---|---|---|---|---|---|---|
| matrix:horizon:400 | E | macro activity -10.2% | 19.1% / 11.5% | multi_region | 1,500 | 400 | 12 | 6.9% / 4.1% | NON-REDUNDANT, TRANSIENT |
| matrix:structure:unsupported_addressable | H | meso degree -2.8% | 9.9% / 5.9% | multi_region | 1,500 | 4,000 | 12 | 10.3% / 5.6% | NON-REDUNDANT, TRANSIENT |
| matrix:memory:delayed_return | H | global memory 8.6% | 16.4% / 8.7% | multi_region | 1,500 | 4,000 | 12 | 13.8% / 4.5% | NON-REDUNDANT, TRANSIENT, TIME-WINDOW-DEPENDENT |
| matrix:mutation:high_state | E | macro activity -10.4% | 4.2% / 2.0% | multi_region | 1,500 | 4,000 | 12 | 3.5% / 2.1% | NON-REDUNDANT |
| matrix:mutation:mixed | E | meso activity -27.7% | 5.9% / 4.5% | multi_region | 1,500 | 4,000 | 12 | 5.4% / 3.7% | NON-REDUNDANT, TRANSIENT |
| matrix:structure:local_external_memory | H | macro activity -38.5% | 14.8% / 6.0% | multi_region | 1,500 | 4,000 | 12 | 10.1% / 7.4% | NON-REDUNDANT |
| matrix:structure:distributed_external_memory | H | global reconfigurations -27.1% | 14.5% / 8.0% | multi_region | 1,500 | 4,000 | 12 | 10.3% / 5.4% | NON-REDUNDANT, TRANSIENT |
| matrix:structure:shallow_acyclic | H | macro difference 88.1% | 10.8% / 10.1% | multi_region | 1,500 | 4,000 | 12 | 11.7% / 8.6% | NON-REDUNDANT, TIME-WINDOW-DEPENDENT |
| matrix:power:48seeds | E | meso activity -10.3% | 5.4% / 3.6% | multi_region | 1,500 | 4,000 | 48 | 5.4% / 3.3% | NON-REDUNDANT, TRANSIENT |
| matrix:strong×topology:highly_clustered | H | meso memory -7.4% | 9.5% / 4.2% | highly_clustered | 1,500 | 4,000 | 12 | 6.3% / 2.2% | NON-REDUNDANT, TRANSIENT |
| matrix:size:128 | E | macro difference -18.9% | 10.6% / 4.7% | multi_region | 1,500 | 4,000 | 12 | 11.5% / 7.5% | NON-REDUNDANT, TIME-WINDOW-DEPENDENT |
| matrix:size:128 | H | global reachable_share 2.1% | 10.6% / 4.7% | multi_region | 1,500 | 4,000 | 12 | 11.5% / 6.5% | NON-REDUNDANT, TRANSIENT |
| … 8 more rows in summary.json | | | | | | | | | |

### 17. At what observation scale do hidden differences first become visible?

- comparisons with trajectory difference: 258
- finest systematic resolution: {'meso': 2, 'exact': 230, 'node': 21, 'macro': 2, 'global': 2, 'local': 1}
- coarsest systematic resolution: {'macro': 7, 'exact': 230, 'meso': 5, 'global': 9, 'local': 4, 'node': 3}
- exact divergence share: 0.7132
<!-- GENERATED:ESCALATION:END -->
