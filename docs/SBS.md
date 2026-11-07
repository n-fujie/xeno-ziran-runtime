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

## What is not done (stated precisely)

* **Stage 2 (historical ON Lab reproduction) and Stage 5 (Operational Nihilism integration): not done.** `on_lab_r2.zip` is not on this machine, and no ON Lab or RODENIAN-X1–X4 source was found in the repositories or in the archives `xeno-ziran-eaeca92.zip`, `xeno-ziran-63cc4b9.zip` or `BIM_share_lean_2026-10-21.zip`. Nothing was reproduced and no ON module was written.
* **The XenoBody body-category ablation framework was not found** in the XB-TRO branch (only a per-principle ablation in `fragility.py`). The A/B/C comparison above follows the specification of the directive and was written new; it is not a reuse of an existing framework.
* **Gate F (visualization): not done.** `sbs_frames.json` holds measured positions, but no view in the frontend reads them yet.
* No other engine was compared (no cross-engine comparison); no conventional morphology–controller, MPC or RL competitor applies to this substrate and none was built.
* Not tested: dependence of the results on the number of particles, the box density, the contact cut-off, the hold times or the integration step; the contact cut-off already changes the fine-observation partition for 35 of 288 readings.
* Not claimed: validation against any physical material or body; Simondonian individuation; metastability in Simondon's sense; posthuman anything.

## Regression verification (backend)

| run | result |
|---|---|
| baseline: `main` (3e874c5) + the P/A SYSTEM rename, whole suite | 1089 passed, 1 failed, 5 skipped (1 h 40 min; other heavy jobs were running at the same time) |
| this branch (adds `xzr/sbs`, 8 tests, one entry in `stage_engine.py`), whole suite | 1098 passed, 0 failed, 5 skipped (1 h 08 min) |
| `tests/test_cooperative.py` alone, on an untouched `origin/main` | 1 failed (`test_bridge_tick_runs_sessions_streams_and_comparisons`), 9 passed |
| the same file alone, on this branch | the same 1 failed, 9 passed |

The one failing test is a timing/order-dependent test of the cooperative bridge ('running' != 'done'); it fails alone on an untouched `origin/main`, so it is **pre-existing and not caused by this work**; it failed in the baseline full run and passed in this branch's full run, which also shows it is not deterministic in a full run. 1089 + 1 + 8 = 1098: no previously passing test failed. The two environment warnings (another scipy hierarchy; three published records that do not replay bit for bit here) are the known ones. Frontend tests were not re-run for this branch (no frontend file changed). Historical result files were not touched.
