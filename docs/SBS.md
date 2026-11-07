# SBS — Simondonian Body Simulation (experimental core, first vertical slice)

Code: `backend/xzr/sbs/` (`engine.py`, `organisation.py`, `protocol.py`, `comparison.py`, `lab_stats.py`). Run: `PYTHONPATH=. python scripts/sbs_experiments.py` from `backend/`. Records: `docs/sbs/sbs_records.json` (all numbers below), `docs/sbs/sbs_frames.json` (measured particle positions of two worlds, every 250 steps). Tests: `backend/tests/test_sbs.py`. The package is local-only: `ios/scripts/stage_engine.py` excludes it from the iOS and browser bundles.

**Source classification: NEW EXECUTION.** Nothing here is a historical archive, an independent reproduction or a validated physical result. The protocol (`xzr/sbs/protocol.py`, digest `144ee2531333…`) was written before the first run and its thresholds were not changed after seeing results; that is a freeze inside the code, not an external registration, so the comparison is **exploratory with a frozen protocol**, not confirmatory. One change was made to the comparison after a 4-world smoke run and before the full run, and is disclosed here: model C's squared terms were replaced by a product and a group count, because squares extrapolated wildly to harsher interventions and would have made C look worse for a reason unrelated to its claim.

## What the substrate is, and is not

60 identical particles in a periodic 2-D box, overdamped Langevin dynamics, a repulsive core and a tunable attractive tail (well depth `eps`), thermal energy `kT`. It is an ordinary condensation model. **No body is in it**: the particles are not grouped, labelled or bounded. A group that stays together is a phenomenon of the dynamics that an observer detects with a declared convention (contact graph, cut-off 1.35 diameters). It was chosen over the XB-TRO planar body for formation experiments because XB-TRO's body is a body by construction; it cannot be used to ask whether a body forms.

## SBS-01 formation

From a gas (`eps = 0`, `kT = 1`), `eps = 1.5` at `kT = 0.3` for 6000 steps. The largest connected group holds a mean **0.77** of the particles after formation, against **0.10** in a control that shares the noise but is never coupled (32 worlds). The reference group at the end of formation has a mean 46.7 of 60 particles. This shows condensation under these parameters, which is what the physics predicts; it is not an observation of individuation in Simondon's sense.

## SBS-02 metastability (the indicator appropriate to this model)

A sweep of `eps` from 0.2 to 1.8 and back, each level held 1500 steps, at fixed `kT`; the order parameter is the share of the largest group. Mean over 12 independent sweeps: the up and down sweeps differ over `eps` 0.4 to 1.2 (for example at `eps` 0.6, 0.23 up against 0.76 down; at 1.0, 0.52 against 0.91), a hysteresis loop of area **0.51 ± 0.18 (sd)**. So the substrate is **path dependent at these hold times**. This is **finite-time hysteresis**: it does not distinguish a true coexistence/metastable basin from slow nucleation in a 60-particle system, and no basin of attraction, transition path or persistence interval was computed. It does not establish Simondon's metastability, which is a philosophical notion that no number here tests.

## SBS-03 dissolution: six records, kept apart

For every world, a control branch and eight intervention branches (decoupling: `eps` 1.0, 0.6, 0.3, 0.0; heating: `kT` 0.5, 0.8, 1.2, 2.0; 1500 steps), all from the same formed state with the same noise. At the end of the intervention (means over 32 worlds):

| branch | largest-group share | reference membership overlap (Jaccard) | force transmission (trailing/leading displacement) |
|---|---|---|---|
| control | 0.82 | 0.94 | 0.46 |
| decoupling 1.0 / 0.6 / 0.3 / 0.0 | 0.82 / 0.57 / 0.29 / 0.14 | 0.90 / 0.70 / 0.35 / 0.17 | 0.44 / 0.36 / 0.25 / 0.18 |
| heating 0.5 / 0.8 / 1.2 / 2.0 | 0.79 / 0.48 / 0.22 / 0.13 | 0.86 / 0.54 / 0.23 / 0.15 | 0.39 / 0.35 / 0.22 / 0.26 |

* **physical** (contact connectivity), **organizational** (membership overlap with the reference group) and **functional** (a probe that pulls the leading fifth of the reference group and reads the trailing fifth against a no-pull branch with the same noise) are separate records and move together here, but they are different measures: for example heating 2.0 and decoupling 0.0 leave nearly the same physical share (0.13 and 0.14) while their transmission differs (0.26 and 0.18), and the transmission is not monotonic in the severity of heating (0.22 at 1.2, 0.26 at 2.0): the probe is one pull per branch and noisy, and the group is a liquid droplet, not a rigid body (an intact group transmits 0.46, not 1).
* **attributional** is decided by the comparison below, not by any threshold in the dynamics.
* **agentic** is recorded as `NOT_APPLICABLE`: the substrate has no agent, policy or goal and nothing was computed for it.
* **observational**: an observer with measurement error 0.05 (fine) reads the true partition with a mean adjusted Rand index of 0.87 at the end of recovery (35 of 288 readings below 0.5, caused by the sensitivity of the contact cut-off); with error 0.3 (coarse) the mean is 0.29 (209 of 288 below 0.5). Those readings are classed `UNRESOLVED_OBSERVATION`, not as a loss of the group: the system did not change, the observer cannot say.

## SBS-04 reconfiguration without a guaranteed outcome

After the intervention the system evolves for 3000 steps under the formation conditions. Outcomes, read from the true positions (32 worlds per row):

| branch | persistence | partial recovery | different organization | multiple organizations |
|---|---|---|---|---|
| control | 26 | 6 | 0 | 0 |
| decoupling 1.0 / 0.6 / 0.3 / 0.0 | 25 / 23 / 21 / 14 | 6 / 8 / 10 / 17 | 1 / 1 / 0 / 1 | 0 / 0 / 1 / 0 |
| heating 0.5 / 0.8 / 1.2 / 2.0 | 22 / 20 / 11 / 2 | 9 / 11 / 17 / 16 | 1 / 1 / 4 / 7 | 0 / 0 / 0 / 7 |

* **The control is not at 100% persistence**: 6 of 32 untouched worlds are `PARTIAL_RECOVERY` because the reference group coarsens or merges with others by itself (the overlap is a Jaccard index, which falls when a group grows). Interventions must be read against this baseline, not against a perfect one.
* Strong heating (2.0) produces `MULTIPLE_ORGANIZATIONS` in 7 of 32 worlds (the only other occurrence is 1 of 32 under decoupling 0.3) and nearly removes persistence (2 of 32). Full decoupling mostly returns a group of the same particles or a larger one. No outcome was imposed as the objective; "no relevant reconstitution" occurred in no world.
* The classes are conventions of this model (overlap ≥ 0.8, ≥ 0.5). A group that grows by absorbing other particles is called a partial recovery by the overlap measure although all of the reference members are retained; the record also keeps `reference_retained_in_best_group`.

## SBS-05 body-concept comparison

Task: from ONE observed frame at the end of an intervention, and the intervention descriptor (given equally to every model), predict for each particle whether it is in the largest group at the end of recovery (true positions, seen by no model). Models: **A** body-inclusive (features of the particle's group in the observed partition), **B** body-free (neighbourhood counts up to three bond lengths and the nearest-neighbour distance, no group label), **C** dynamical order-parameter account (global state only), **N** null (descriptor only). Logistic regression, the same ridge and data; A, B, C have 8 parameters, N has 4. Training worlds 1–16, test worlds 17–32 (independent initial gases); the second protocol also trains on mild and tests on harsher interventions. Paired Brier scores over test worlds; margin 0.01; Holm correction over all 24 comparisons. The feature functions take only the observed frame and the descriptor (a test checks the signature and purity), so no model reads the simulation.

Mean Brier (lower is better):

| observation | protocol | A | B | C | N |
|---|---|---|---|---|---|
| fine | held-out worlds | 0.1199 | **0.1139** | 0.1253 | 0.1264 |
| fine | harsher interventions | 0.2019 | **0.1823** | 0.1838 | 0.1884 |
| coarse | held-out worlds | 0.1222 | **0.1153** | 0.1269 | 0.1264 |
| coarse | harsher interventions | 0.1970 | **0.1842** | 0.1977 | 0.1884 |

Verdicts (rule in the record): **no comparison detected an advantage of the body-inclusive description A.** B was better than A in one of four conditions (fine observation, harsher interventions: Brier difference 0.020, Holm-significant); in the others A against B is unresolved. A against C is equivalent within the margin in two conditions and unresolved in two. B against C: B better in one (coarse, harsher), unresolved otherwise. A against the null is unresolved or equivalent in all four conditions, and B and C were not shown better than the null either (B against the null: equivalent within the margin in two conditions, unresolved in two): in this task the observed frame added no demonstrated predictive value over knowing only which intervention was applied, for any description.

**Reading.** In this task and with these models, the body-inclusive description did not show a nonredundant predictive advantage over a body-free neighbourhood description with the same information; in one condition it was worse. This is a statement about this prediction task, this feature construction and 16 test worlds, **not** evidence that no body-level organization exists, and not a defeat of Simondon's philosophy, which these models do not instantiate. "Equivalent within the margin" means the 95% interval lies inside ±0.01 Brier, not that the models are the same. Many comparisons are `UNRESOLVED`: 16 worlds do not resolve differences of this size.

## Follow-ups (all NEW EXECUTION; the frozen protocol and its digest `144ee2531333…` are unchanged)

Code: `xzr/sbs/sensitivity.py`, `on_persistence.py`, `on_fragility.py`; runners `scripts/sbs_replication.py`, `sbs_sensitivity.py`, `sbs_on02.py`, `sbs_on03.py`; records `docs/sbs/sbs_replication.json`, `sbs_sensitivity.json`, `sbs_on02.json`, `sbs_on03.json`; tests `tests/test_sbs_followups.py`. The only edit to code that the first run used: `organisation.contact_graph` / `partition` now read the contact cut-off `R_BOND` at call time (so that a sensitivity run can change it); with the default it is bit-identical (a test checks this, and the 9 original tests pass).

### Replication on new worlds (answers "16 test worlds are too few")

The same protocol, features and verdict rule on worlds 33–96 (train 33–64, test 65–96; none of them used before): 32 test worlds instead of 16 and 32 training worlds instead of 16. Formation: mean largest-group share 0.74 (first run 0.77). Outcomes over 64 worlds: control persistence 43, partial recovery 21; heating 2.0: persistence 8, partial 33, different organization 12, multiple organizations 11; decoupling 0.0: persistence 24, partial 32, different 5, multiple 3. The direction agrees with the first run; the proportions differ (control persistence 67% against 81%), which is the size of the world-to-world noise here.

Mean Brier (lower is better), 32 test worlds:

| observation | protocol | A | B | C | N |
|---|---|---|---|---|---|
| fine | held-out worlds | 0.1128 | **0.1066** | 0.1222 | 0.1259 |
| fine | harsher interventions | 0.1913 | **0.1614** | 0.1945 | 0.1781 |
| coarse | held-out worlds | 0.1204 | **0.1079** | 0.1249 | 0.1259 |
| coarse | harsher interventions | 0.1845 | **0.1659** | 0.1855 | 0.1781 |

* **A (body-inclusive) was again not shown better than anything**: no comparison has A better. B (body-free) is better than A in the two harsher-intervention conditions (Brier difference 0.030 fine, 0.019 coarse; Holm-significant) and unresolved against A in the held-out conditions. A against C is equivalent within the margin in three conditions and unresolved in one.
* **This changes one statement of the first run.** The first run found B and C not demonstrably better than the null. In the replication **B is better than the null in three of four conditions** (fine held-out, fine harsher, coarse held-out; differences 0.017–0.019, Holm-significant) and unresolved in the fourth; C is equivalent to the null or worse. So a body-free neighbourhood description does carry predictive information about which particles stay in the largest group beyond the intervention descriptor alone. Because the replication also doubled the training worlds, the gain may come from more training data rather than from different worlds; the two runs were not separated on that point.
* The reading stays what it was: in this task, with these features and 32 test worlds, a body-inclusive description showed no nonredundant advantage over a body-free one. It is not evidence about body-level organization in general.

### Dependence on the model's conventions (answers "not tested")

Eleven variants (nine run the whole protocol, two only the hysteresis sweep) and the baseline, each changing one convention of the frozen protocol (eight worlds per world-variant, seeds 201–208; three hysteresis sweeps per variant; the model comparison was NOT repeated per variant, it needs dozens of worlds each). Four findings, fixed before the run in `sensitivity.py`: F1 the coupled run holds a larger largest-group share than the never-coupled control; F2 the share at the end of the intervention falls monotonically with the severity of decoupling and of heating; F3 persistence is less frequent after the harshest heating than in the control; F4 finite-time hysteresis area is positive.

| variant | worlds | formation share (coupled / uncoupled) | share at decoupling 1.0 → 0.0 · heating 0.5 → 2.0 | persistence: control · heating 2.0 | hysteresis area | F1 F2 F3 F4 |
|---|---|---|---|---|---|---|
| baseline | 8 | 0.83 / 0.08 | 0.80 → 0.12 · 0.80 → 0.17 | 8/8 · 2/8 | 0.48 | yes yes yes yes |
| n = 40 | 8 | 0.96 / 0.10 | 0.95 → 0.18 · 0.95 → 0.21 | 8/8 · 5/8 | 0.26 | yes yes yes yes |
| n = 100 | 8 | 0.50 / 0.06 | 0.47 → 0.08 · 0.44 → 0.08 | 4/8 · 0/8 | 0.29 | yes yes yes yes |
| density 0.15 | 8 | 0.30 / 0.05 | 0.32 → 0.08 · 0.30 → 0.09 | 7/8 · 0/8 | 0.23 | yes yes yes yes |
| density 0.35 | 8 | 0.99 / 0.24 | 0.96 → 0.22 · 0.93 → 0.21 | 8/8 · 7/8 | 0.15 | yes yes yes yes |
| cut-off 1.2 | 8 | 0.68 / 0.05 | 0.40 → 0.07 · 0.38 → 0.07 | 3/8 · 0/8 | 0.21 | yes yes yes yes |
| cut-off 1.5 | 8 | 0.83 / 0.15 | 0.83 → 0.28 · 0.85 → 0.31 | 8/8 · 3/8 | 0.46 | yes **NO** yes yes |
| recovery 1500 steps | 8 | 0.83 / 0.08 | as baseline | 8/8 · 1/8 | 0.48 | yes yes yes yes |
| recovery 6000 steps | 8 | 0.83 / 0.08 | as baseline | 8/8 · 3/8 | 0.48 | yes yes yes yes |
| dt 0.001, same physical time | 8 | 0.77 / 0.09 | 0.76 → 0.17 · 0.75 → 0.12 | 6/8 · 3/8 | 0.44 | yes yes yes yes |
| sweep hold 750 / 3000 steps | — | — | — | — | 0.57 / 0.33 | hysteresis yes / yes |

* **The qualitative findings held in every variant except one cell**: F2 at cut-off 1.5, where the mean share at heating 0.5 (0.848) is below that at heating 0.8 (0.854), a 0.006 plateau that the strict monotone rule counts as a failure; with eight worlds that is within noise, but the rule was fixed in advance and the failure stays in the record.
* **The numbers are not robust, only the direction is.** The formation share runs from 0.30 to 0.99, the control's persistence from 3/8 to 8/8 and the persistence after the harshest heating from 0/8 to 7/8 across the variants. At density 0.35 even heating 2.0 leaves the reference group intact in 7 of 8 worlds, so F3 holds there only trivially. The hysteresis area is positive everywhere and shrinks with longer holds (0.57 at 750 steps, 0.33 at 3000), as finite-time hysteresis should; it was not shown to vanish or to persist in the long-hold limit, so nothing here separates a true metastable region from slow nucleation. The outcome tables in SBS-04 are therefore statements about this parameter point, not about condensation in general.
* Eight worlds per variant detect only large changes.

### ON-02 non-guaranteed persistence, on this substrate (NEW condition; not an ON Lab reproduction)

The same 32 worlds and five branches (control, decoupling 0.3 and 0.0, heating 1.2 and 2.0), same noise seeds as SBS-04 (a test checks that the end values agree with `sbs_records.json`). One run is read by several persistence criteria, kept apart; conventions fixed in the code: membership overlap ≥ 0.8, retention of the reference's initial contact pairs ≥ 0.8, cohesion (largest share ≥ 0.5), function (transmission ratio after recovery ≥ half the same world's control ratio). Task performance, resource access and technical lineage are **not applicable** and not computed; "historically identified continuity" is represented only by the tracked particle membership, which is thin (particles have no other history).

At the end of the recovery (cells = 32 worlds × branch; control · decoupling 0.3 · 0.0 · heating 1.2 · 2.0):

| criterion | persists |
|---|---|
| physical cohesion | 32 · 31 · 30 · 31 · 25 |
| membership (Jaccard ≥ 0.8) | 26 · 21 · 14 · 11 · 2 |
| function (transmission ≥ half of control) | 32 · 26 · 26 · 24 · 22 |
| local configuration (≥ 0.8 of reference contact pairs) | 0 · 0 · 0 · 0 · 0 |
| cohesion never lost during the run | 28 · 0 · 0 · 0 · 0 |

* **The criteria disagree, and not in one direction.** Cohesion is present while membership is lost in 75 of 160 cells; function is present while membership is lost in 61 of 160 (the reverse in 5); in 51 cells membership persists although cohesion was lost during the run (an intervention took it below 0.5 and it came back), and in 5 cohesion was never lost yet membership fell below the convention. A finite survival summary ("cohesion never lost") is 28/32 in the control and, by construction, 0/32 in every intervention branch (each intervention takes cohesion below 0.5), so it cannot say what persisted afterwards: that is the specification's point that finite survival time is not a complete measure, shown on data.
* **Repair capacity** (steps from the end of the intervention until the largest group again holds half of the particles): median 250 (control cases that lost cohesion, 3), 250 (decoupling 0.3), 500 (decoupling 0.0), 500 (heating 1.2), 1000 (heating 2.0); not repaired within the 3000-step recovery in 1 world after decoupling 0.0 and 5 after heating 2.0.
* **Shape without membership**: after heating 2.0, in 2 of 32 worlds no group continues the reference membership (overlap < 0.5) although a group of about its size exists; none in the other branches. A description that reads shape only would call that group the continuation.
* **The local-configuration criterion is never met, in any branch, even in the control**: the median retention of the reference's contact pairs at the end is 0.48 in the control (0.35, 0.29, 0.17, 0.10 in the interventions, falling with severity). The group is a liquid droplet; individual contacts turn over. The 0.8 convention was fixed before the run and is not informative as a yes/no here; the continuous values grade with severity and are in the record. Counts that involve this criterion (for example "149 of 160 cells where cohesion is present and the configuration is not") are consequences of that convention, not independent findings.
* No quantity here is a probability of failure and none is offered as a measure of existential non-guarantee.

### ON-03 fragility transfer, on this substrate (NEW condition; not an ON Lab reproduction)

Designs: the formation coupling `eps` ∈ {1.0, 1.5 (baseline), 2.0, 2.5}; 24 worlds each (seeds 301–324), compared with the baseline world by world. Fixed in `on_fragility.py` before the run: the improvement under test (membership persistence after heating 1.2: paired 95% interval of the difference above 0.05), the measures kept apart (performance; repair: single-group share and steps to half after complete decoupling; load failure: group integrity under a 400-step pull; stored cohesive energy, recorded and not ranked), the transfer mechanism (kinetic arrest: stronger coupling lowers mobility and traps poorly merged arrangements), the two required forms of mechanism evidence (lower mobility; an anneal merges more failed repairs than a same-noise control) and the verdict rule. Communication, maintenance, resource dependence, dependence on external systems and external latency are **not applicable** and not computed.

| design eps | formation share | performance (overlap after heating 1.2) | single group after decoupling 0.0 (of 24) | median steps to half (unrepaired = ∞) | load retention | mobility (MSD over 500 steps) | energy per particle |
|---|---|---|---|---|---|---|---|
| 1.0 | 0.68 | 0.505 | 10 | 1250 | 0.89 | 0.41 | −1.93 |
| 1.5 (baseline) | 0.73 | 0.692 | 18 | 500 | 0.99 | 0.28 | −3.24 |
| 2.0 | 0.73 | 0.749 | 16 | 250 | 1.00 | 0.22 | −4.59 |
| 2.5 | 0.70 | 0.741 | 19 | 375 | 1.00 | 0.22 | −5.79 |

* **Verdict against the baseline: `NOT_AN_IMPROVEMENT` for all three designs.** Eps 2.0 and 2.5 raise performance by 0.057 and 0.049, but the 95% intervals ([−0.025, 0.139] and [−0.028, 0.127]) include zero and do not exceed the 0.05 margin, so no improvement was established and the question of transfer does not arise by the rule. Eps 1.0 is worse than the baseline on every measure (performance −0.186, interval [−0.283, −0.089]; load −0.10).
* **No transfer of vulnerability was found.** Repair is not worse in the stronger designs (single-group share difference −0.083 [−0.386, 0.22] at 2.0 and +0.042 at 2.5; steps to half −83 and +31, intervals include zero). **The proposed mechanism's first marker is present** (mobility is lower than at the baseline: baseline minus design 0.017 to 0.098 at 2.0, 0.019 to 0.109 at 2.5), **but its predicted consequence is not**: lower mobility did not produce measurably worse repair. The anneal test is small and inconclusive (merged after anneal / after control: 5 / 3 of 8 failed repairs at 2.0; 2 / 1 of 5 at 2.5; 5 / 4 of 14 at 1.0).
* **Pareto**: on means, 1.0 is dominated; 1.5 is dominated by 2.5; **2.0 and 2.5 are incomparable** (2.0 has the higher performance mean, 2.5 the higher single-group share) and both are retained. Dominance on means ignores the uncertainty above, under which none of 1.5, 2.0, 2.5 is separated from the others on performance.
* **Unplanned observation, not a result**: going from 1.0 to 1.5 improves performance, repair and load together; so over this range stronger coupling improved everything measured, which is the opposite of a transfer. This comparison was not the pre-specified one.
* Not tested: other perturbation types than heating, decoupling and a pull; other kinds of improvement than coupling strength; other transfer mechanisms than kinetic arrest. Absence of a detected transfer here does not show that Fragility Transfer cannot occur.

## What is not done (stated precisely)

* **Stage 2 (historical ON Lab reproduction) and Stage 5 (integration with the historical Operational Nihilism programme): not done and cannot be done here.** `on_lab_r2.zip` is not on this machine, and no ON Lab or RODENIAN-X1–X4 source was found in the repositories or in the archives `xeno-ziran-eaeca92.zip`, `xeno-ziran-63cc4b9.zip` or `BIM_share_lean_2026-10-21.zip`. Nothing was reproduced. The ON-02 and ON-03 sections above are new conditions on the SBS substrate, written from the specification text, and make no claim to reproduce or extend ON Lab results.
* ON-01, ON-04, ON-05, ON-06 and ON-07 are not built (ON-01 needs the ON Lab / XenoBody instruction-withdrawal structures; the others need agents, norms or lineage that this substrate does not have).
* **The XenoBody body-category ablation framework was not found** in the XB-TRO branch (only a per-principle ablation in `fragility.py`). The A/B/C comparison follows the specification of the directive and was written new; it is not a reuse of an existing framework.
* **Gate F (visualization)**: shows recorded states of two worlds only; the replication, sensitivity, ON-02 and ON-03 records have no view.
* No other engine was compared (no cross-engine comparison); no conventional morphology–controller, MPC or RL competitor applies to this substrate (it has no controller) and none was built.
* The model comparison was not repeated across the sensitivity variants.
* Not claimed: validation against any physical material or body; Simondonian individuation; metastability in Simondon's sense; posthuman anything.

## Regression verification (backend)

| run | result |
|---|---|
| baseline: `main` (3e874c5) + the P/A SYSTEM rename, whole suite | 1089 passed, 1 failed, 5 skipped (1 h 40 min; other heavy jobs were running at the same time) |
| this branch (adds `xzr/sbs`, 8 tests, one entry in `stage_engine.py`), whole suite | 1098 passed, 0 failed, 5 skipped (1 h 08 min) |
| `tests/test_cooperative.py` alone, on an untouched `origin/main` | 1 failed (`test_bridge_tick_runs_sessions_streams_and_comparisons`), 9 passed |
| the same file alone, on this branch | the same 1 failed, 9 passed |

The one failing test is a timing/order-dependent test of the cooperative bridge ('running' != 'done'); it fails alone on an untouched `origin/main`, so it is **pre-existing and not caused by this work**; it failed in the baseline full run and passed in this branch's full run, which also shows it is not deterministic in a full run. 1089 + 1 + 8 = 1098: no previously passing test failed. The two environment warnings (another scipy hierarchy; three published records that do not replay bit for bit here) are the known ones. Historical result files were not touched.

Follow-up verification: `tests/test_sbs.py`, `tests/test_sbs_followups.py`, `tests/test_stage_engine.py` and `tests/test_cooperative.py` together: 31 passed. The **whole backend suite was not rerun** after the follow-ups; the only change to code the earlier whole-suite run exercised is `organisation.contact_graph`/`partition` reading the default cut-off at call time (bit-identical, tested) and a test-only timing fix in `test_cooperative.py` (the earlier failing test now waits against a wall-clock deadline and passed; `test_running_session_is_paced_and_pausable` is a wall-clock pacing test that failed once under a machine load average of about 25 and passed in the later run, so it is load dependent and was not changed).

Frontend (whole suite after the follow-ups): 336 passed, 1 skipped, 0 failed (earlier: 331 passed, 5 failed). The earlier failures were `Test timed out` in three heavy 3D-laboratory geometry files; the tests take 5–12 s on a loaded machine against vitest's default 5 s, so `vite.config.ts` now sets `testTimeout: 60_000` (the limit `assemblies.test.ts` already used for its heaviest cases). That makes them pass; it does not make them faster. `tsc --noEmit` was clean for the SBS work.

## The SBS view (Gate F)

`?view=sbs` in the local app (not in the public site, the browser edition or the iOS app): `frontend/src/views/sbs/`, fed by the read-only local routes `/api/sbs/summary` and `/api/sbs/frames` (`backend/xzr/service/sbs.py`, excluded from the engine bundle). It plays, pauses and steps through the measured particle positions (18 frames per branch, every 250 steps, never interpolated), shows the six dissolution records of the selected world and branch, the outcome table over the 32 worlds, the hysteresis curves, the model comparison and the evidence boundary. The largest-group share and the number of groups computed in the viewer from the measured positions equal the saved records in all 18 recorded branches (a test checks this); the contact count can differ by one pair because the saved positions are rounded to three decimals. Checked in a real browser against the running local backend (playback, stepping, console without errors); the phone layout was later checked at a true 375 px width (emulated Android phone, built frontend served by the local backend): no horizontal overflow of the page and no element outside a scrolling box; the page was looked at on its first screen only (selectors, the particle canvas, playback controls), not scrolled through in full. Measured frame rates were not taken and none is claimed.
