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
