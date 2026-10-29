# XENO ECOSYSTEM — Stage 5 (MEOS-0.4): multiple MFS, alternative routes, reconfiguration

> 複数の作動的実現可能性は一般則ではなく、特定条件に局在する。多くの条件では単一MFSまたはMFS不成立へ収束する。
> (Multiple operational realisations are not a general rule: they are local to particular conditions. In most conditions the result is a single MFS or no MFS.)

Everything below is a statement about a **formal model** (MEOS-0): how this engine's specified operation responds to the manipulations listed. It is not evidence about any physical, biological or ecological system. The visual representation (bodies, map, graph) presents the
model's records; it is never used as evidence. Raw data and interpretation are kept apart: tables are copied from `docs/ecosystem/experiments_stage5.json` by `backend/scripts/make_stage5_doc.py`; the words under them are interpretation and its limits.

## 1. Scope

Stage 5 asks **where** a single MFS, several non-isomorphic MFS, or no MFS holds, and how far alternative routes and reconfiguration help. It does not try to confirm an expected theory. In the finalisation no theory feature was added; the work was to finalise results, the frontend
integration, reproducible captures, performance, regression and this document. Not changed: the baseline result digest, the 264 saved runs, the Stage 4 results and strict nulls.

## 2. Repository state

- Worktree `/Users/user/Desktop/BIM/xeno-ziran-runtime-meos`, branch `feat/meos-ecosystem`, from the zrs baseline `ec9667e`. **Local only: not pushed, not merged, not deployed.**
- Stage 5 commits: `4a4e4bf` (checkpoint: engine meos-0.4, MFS search, reconfiguration, experiments F-K), `b2f9917` (backend finalisation: candidate/validation analysis, classes, service routes, deep-link module), `946d654` (frontend: saved-results panel, route states, rejected-candidate layer, replay markers), followed by the final commit of this stage (documents, captures, paired performance evidence, UI corrections). `git log` gives its id.
- The baseline result digest and the 264 stored runs are unchanged; the Stage 3 comparison worktree (`/tmp/s5/s3wt`) was removed after the benchmark.

## 3. Stage 4 acceptance

**Final acceptance of the Stage 4 performance question** (appended to `ECOSYSTEM_MEOS_STAGE4.md` section 19). The pre-fixed rule (lower CI bound above 1.05 = regression; upper bound below 1.05 = no meaningful regression; otherwise inconclusive) was applied to the **14 paired repetitions** of Stage 4 against Stage 3 that now exist: the 8 of the first acceptance (`perf_stage5/stage4_acceptance/`) and the 6 of this stage (`perf_stage5/paired/`).
Balanced tier, 150 frames; median and p95 over repetitions.

| camera | mode | measure | Stage 3 (ms) | Stage 4 (ms) | paired ratio S4/S3 | 95 % CI | verdict |
|---|---|---|---|---|---|---|---|
| body | static | median | 15.95 | 16.45 | 1.038 | [1.012, 1.085] | inconclusive |
| body | static | p95 | 19.6 | 20.4 | 1.123 | [0.835, 1.343] | inconclusive |
| body | orbit | median | 16.85 | 16.65 | 1.013 | [0.944, 1.058] | inconclusive |
| body | orbit | p95 | 26.6 | 24.4 | 0.954 | [0.789, 1.146] | inconclusive |
| habitat | static | median | 17.9 | 18.25 | 1.03 | [0.989, 1.077] | inconclusive |
| habitat | static | p95 | 23.05 | 29.6 | 1.043 | [0.896, 1.465] | inconclusive |
| habitat | orbit | median | 19.45 | 19.4 | 1.003 | [0.959, 1.022] | no meaningful regression |
| habitat | orbit | p95 | 29.1 | 25.85 | 0.932 | [0.862, 0.996] | no meaningful regression |
| overview | static | median | 15.35 | 15.75 | 1.007 | [0.986, 1.044] | no meaningful regression |
| overview | static | p95 | 19.95 | 21.1 | 0.975 | [0.925, 1.14] | inconclusive |
| overview | orbit | median | 16.75 | 17.7 | 1.018 | [0.982, 1.043] | no meaningful regression |
| overview | orbit | p95 | 29.05 | 26.35 | 0.994 | [0.75, 1.107] | inconclusive |

**Result: 0 regression, 4 no meaningful regression, 8 inconclusive.** No regression is established. The static median of body (1.038 [1.012, 1.085]) and habitat (1.030 [0.989, 1.077]) is *inconclusive*: a cost of up to about 8 % is not excluded, and for body the whole interval is above 1.0 (a small cost is probable). The orbit median of habitat and overview, and the orbit p95 of habitat, are *no meaningful regression* (the habitat orbit tail is better than Stage 3's: 0.932 [0.862, 0.996]).
Acceptance status of Stage 4 performance: **no regression established; inconclusive (a small cost not excluded) for the static median of body and habitat; no meaningful regression for the orbit median and the habitat orbit tail.** The first 8 repetitions were measured at a load of 3.0-5.3, the last 6 as stated in section 20 of the Stage 5 document.

## 4. MEOS-0.4 changes (all opt-in; absent by default, so the baseline digest is unchanged)

- Settable `coupling.gain` (0-2), `environment.renew_delay` (0-40 ticks), `history.lag` (0-40; it matters only while the delayed trace is lower than the current one, i.e. when set from tick 0).
- New operation `ROUTE` (an `m2` block and/or `history` on/off); a controller records `why`, `from`, `to`, `cost`, `trigger` in it. `Run.inject` schedules an intervention for the next tick and keeps the canonical order, so the recorded schedule replays the same run **without** the controller.
- `engine.finalize` adds the digests; the `m2_sensed` trace is back-filled with zeros when M2 is switched on mid-run.
- Backend modules: `mfs5` (exhaustive search and validation), `routes5` (profiles, equivalence levels, topology), `reconf` (controllers), `stats5`, `stage5_experiments` (F-K), `stage5_final` (derived classification). Service routes: `/api/meos/mfs-library`, `/route-topology`, `/reconfigure`, `/mfs-run`.

## 5. What "multiple MFS" means here

An **MFS** is an inclusion-minimal set of components that, with everything else removed at tick 0, still preserves the specified operation (status ACTIVE at horizon 160) under a given condition. **Multiple MFS** means at least two validated inclusion-minimal sets of *different composition* under the same condition
(equal cardinality is not required and not sufficient). The universe is nine components plus, where the condition has one, the M2 tap; all 2^n retained subsets are enumerated. Component roles: necessary, sufficient (completes the core), substitutable (by X in a context), redundant, null, compensatory
(needed only because another condition degrades something), destabilizing.

## 6. Search and validation protocol (fixed in code before the final reading)

- **Search seeds 1-5.** A set *persists* only if it persists in every one of them; the inclusion-minimal persisting sets are the discovered MFS.
- **Validation seeds 6-10.** Every discovered MFS is run again on seeds the search never saw; it is *validated* only if it persists in all five.
- **Candidate** = an inclusion-minimal set under the relaxed criterion (>= 3 of 5 search seeds) or a minimal set of the first 3-seed search; its status says why it is or is not an MFS: validated / failed the search criterion / failed validation / near miss (4 of 5 on both seed sets).
- **Classes:** NO_MFS, SINGLE_MFS, MULTIPLE_MFS (>= 2 validated sets of different composition), UNSTABLE_CANDIDATE (no validated set, candidates exist), INCONCLUSIVE (a near-miss candidate exists).
- Search seeds and validation seeds are **never mixed**: the tables show them in separate columns.

## 7. F1-F16

Result: **1 NO_MFS, 13 SINGLE_MFS, 1 MULTIPLE_MFS, 0 UNSTABLE_CANDIDATE, 1 INCONCLUSIVE** of 16 conditions. Multiple operational realisations are not a general law in this model; they are local. Of the sixteen conditions 1 INCONCLUSIVE, 1 MULTIPLE_MFS, 1 NO_MFS, 13 SINGLE_MFS. Where one validated set exists it is usually the only one; where none exists, no retaining set was found under the allowed reductions, the specified criterion and these seeds.

| condition | description | search seeds | validation seeds | candidate sets | validated MFS | MFS ids | cardinality | history | M2 | Address | coupling | resource | renewal | SSS region (default setting) | observational robustness | class |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 | finite power, no M2 tap | 1-5 | 6-10 | 1 | 1 | MFS-F1-1 | 7 | contributes in some contexts only | not available under this condition | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.72 | necessary | destabilizing | necessary | OBSERVATION-SENSITIVE | 0.00 | **SINGLE_MFS** |
| F2 | unlimited power, no M2 tap | 1-5 | 6-10 | 1 | 1 | MFS-F2-1 | 6 | redundant | not available under this condition | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.72 | necessary | redundant | necessary/redundant | OBSERVATION-SENSITIVE | 0.00 | **SINGLE_MFS** |
| F3 | finite power, direct M2 tap (weight 4) | 1-5 | 6-10 | 1 | 1 | MFS-F3-1 | 7 | substitutable | substitutable | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.72 | necessary | destabilizing | necessary | OBSERVATION-SENSITIVE | 0.00 | **SINGLE_MFS** |
| F4 | unlimited power, direct M2 tap | 1-5 | 6-10 | 1 | 1 | MFS-F4-1 | 6 | redundant | redundant | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.72 | necessary | redundant | necessary/redundant | OBSERVATION-SENSITIVE | 0.00 | **SINGLE_MFS** |
| F5 | finite power, noisy M2 tap (0.05, weight 4) | 1-5 | 6-10 | 1 | 1 | MFS-F5-1 | 7 | contributes in some contexts only | redundant | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.72 | necessary | destabilizing | necessary | OBSERVATION-SENSITIVE | 0.00 | **SINGLE_MFS** |
| F6 | finite power, delayed M2 tap (3 ticks, weight 4) | 1-5 | 6-10 | 1 | 1 | MFS-F6-1 | 7 | contributes in some contexts only | redundant | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.72 | necessary | destabilizing | necessary | OBSERVATION-SENSITIVE | 0.00 | **SINGLE_MFS** |
| F7 | direct tap, history unavailable | 1-5 | 6-10 | 1 | 1 | MFS-F7-1 | 7 | not available under this condition | contributes in some contexts only | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.72 | necessary | destabilizing | necessary | OBSERVATION-SENSITIVE | 0.00 | **SINGLE_MFS** |
| F8 | direct tap, coupling weakened (gain 0.6) | 1-5 | 6-10 | 2 | 1 | MFS-F8-1 | 8 | compensatory | redundant | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.72 | necessary | redundant | necessary | OBSERVATION-SENSITIVE | 0.00 | **SINGLE_MFS** |
| F9 | direct tap, resource reduced (regrow 0.01, charge 0.2) | 1-5 | 6-10 | 0 | 0 | — | — | null | null | no MFS to test | null | null | null | — | — | **NO_MFS** |
| F10 | direct tap, renewal efficiency 0.7 | 1-5 | 6-10 | 1 | 1 | MFS-F10-1 | 8 | compensatory | null | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.64 | necessary | destabilizing | necessary | OBSERVATION-SENSITIVE | 0.00 | **SINGLE_MFS** |
| F11 | direct tap, history delayed (lag 8) | 1-5 | 6-10 | 1 | 1 | MFS-F11-1 | 7 | substitutable | substitutable | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.72 | necessary | destabilizing | necessary | OBSERVATION-SENSITIVE | 0.00 | **SINGLE_MFS** |
| F12 | SSS scale 1.5, no M2 tap | 1-5 | 6-10 | 1 | 1 | MFS-F12-1 | 8 | necessary | not available under this condition | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.72 | necessary | destabilizing | necessary | OBSERVATION-SENSITIVE | 0.00 | **SINGLE_MFS** |
| F13 | SSS scale 1.5, direct M2 tap | 1-5 | 6-10 | 1 | 1 | MFS-F13-1 | 8 | necessary | null | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.72 | necessary | destabilizing | necessary | OBSERVATION-SENSITIVE | 0.00 | **SINGLE_MFS** |
| F14 | SSS scale 1.5, delayed M2 tap (3 ticks) | 1-5 | 6-10 | 2 | 2 | MFS-F14-1, MFS-F14-2 | 8, 8 | substitutable | substitutable | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.72, 0.72 | necessary | destabilizing | necessary | OBSERVATION-SENSITIVE, OBSERVATION-SENSITIVE | 0.00, 0.00 | **MULTIPLE_MFS** |
| F15 | SSS scale 1.5, noisy M2 tap (0.05) | 1-5 | 6-10 | 2 | 1 | MFS-F15-1 | 8 | necessary | contributes in some contexts only | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.72 | necessary | destabilizing | necessary | OBSERVATION-SENSITIVE | 0.00 | **SINGLE_MFS** |
| F16 | renewal efficiency 0.7, noisy M2 tap | 1-5 | 6-10 | 2 | 1 | MFS-F16-1 | 8 | compensatory | contributes in some contexts only | not a removable component; collapse share under the Address fault battery (mean over the MFS): 0.64 | necessary | destabilizing | necessary | OBSERVATION-SENSITIVE | 0.00 | **INCONCLUSIVE** |

Search seeds 1-5, validation seeds 6-10 in every row. Roles: *history* is the role of the history component in the condition's MFS (necessary / compensatory / substitutable / redundant / null / contributes in some contexts only); *Address* is not a removable component, the entry gives the collapse
share under the Address fault battery. SSS region and observational robustness are those of the default setting.

### 7.1 Candidate sets, with search and validation seeds apart

Every candidate retaining set that was searched is listed with how it fared on the two seed sets. A candidate is **not** an MFS unless its status says *validated*.

| condition | set | retained components | persists on search seeds 1-5 | persists on validation seeds 6-10 | discovery | validation | status |
|---|---|---|---|---|---|---|---|
| F1 | F1-set1 | 7: A2, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal | 5/5 | 5/5 | discovered | survived | **validated** |
| F2 | F2-set1 | 6: A2, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback | 5/5 | 5/5 | discovered | survived | **validated** |
| F3 | F3-set1 | 7: A2, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal | 5/5 | 5/5 | discovered | survived | **validated** |
| F4 | F4-set1 | 6: A2, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback | 5/5 | 5/5 | discovered | survived | **validated** |
| F5 | F5-set1 | 7: A2, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal | 5/5 | 5/5 | discovered | survived | **validated** |
| F6 | F6-set1 | 7: A2, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal | 5/5 | 5/5 | discovered | survived | **validated** |
| F7 | F7-set1 | 7: A2, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal | 5/5 | 5/5 | discovered | survived | **validated** |
| F8 | F8-set1 | 8: A2, resource_gradient, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal | 4/5 | 1/5 | discovered | did not survive | **failed the search criterion** |
| F8 | F8-set2 | 8: A2, history, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal | 5/5 | 5/5 | discovered | survived | **validated** |
| F10 | F10-set1 | 8: A2, history, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal | 5/5 | 5/5 | discovered | survived | **validated** |
| F11 | F11-set1 | 7: A2, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal | 5/5 | 5/5 | discovered | survived | **validated** |
| F12 | F12-set1 | 8: A2, history, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal | 5/5 | 5/5 | discovered | survived | **validated** |
| F13 | F13-set1 | 8: A2, history, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal | 5/5 | 5/5 | discovered | survived | **validated** |
| F14 | F14-set1 | 8: A2, history, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal | 5/5 | 5/5 | discovered | survived | **validated** |
| F14 | F14-set2 | 8: A2, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal, m2_tap | 5/5 | 5/5 | discovered | survived | **validated** |
| F15 | F15-set1 | 8: A2, history, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal | 5/5 | 5/5 | discovered | survived | **validated** |
| F15 | F15-set2 | 8: A2, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal, m2_tap | 3/5 | 2/5 | discovered | did not survive | **failed the search criterion** |
| F16 | F16-set1 | 8: A2, history, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal | 5/5 | 5/5 | discovered | survived | **validated** |
| F16 | F16-set2 | 8: A2, interaction_channel, sensor_resource, sensor_alteration, environmental_persistence, feedback, resource_renewal, m2_tap | 4/5 | 5/5 | discovered | did not survive | **near miss** |

**F8:** the first search (3 seeds) found two inclusion-minimal sets. Under the five-seed search and the independent validation the history-free set persisted on 4 of 5 search seeds and on 1 of 5 validation seeds; it did not survive, and **F8 is not counted as a condition with multiple MFS** (class SINGLE_MFS).
The first, 3-seed result files are kept (`experiments_stage5_F_preliminary_3seeds.json`, `experiments_stage5_first_full_run.json`). **F16:** a near-miss candidate (4 of 5 on both seed sets): the data cannot separate it, the class is INCONCLUSIVE and it is not counted as a second MFS.

## 8. F14: two validated MFS (a local result, not a general one)

F14 (SSS scale 1.5 with a delayed M2 tap) has two validated inclusion-minimal sets of equal cardinality and different composition: a **history-mediated** set and an **M2-mediated** set. Both preserve the operation in all five validation seeds.

| measure | MFS-F14-1 | MFS-F14-2 |  |
|---|---|---|---|
| preserved operation (share of seeds ACTIVE, confirmation seeds) | 1.0 | 1.0 | same |
| energy use (mean cumulative) | 119.08 | 119.08 | same |
| resource throughput | 107.561 | 107.49 | differs |
| recovery capability (recovered with a pulse after an interruption, of 5) | 5 | 5 | same |
| recovery latency after the pulse (ticks) | 11.0 | 12.0 | differs |
| perturbation sensitivity (collapse share per perturbation) | {"address loss of A2 (40 ticks)": 1.0, "resource pulse 4.0 (oversupply)": 1.0, "renewal efficiency 0.7": 0.0, "coupling weakened (gain 0.5)": 1.0, "SSS scale 1.15": 0.0, "sensing noise 0.05": 0.0} | {"address loss of A2 (40 ticks)": 1.0, "resource pulse 4.0 (oversupply)": 1.0, "renewal efficiency 0.7": 1.0, "coupling weakened (gain 0.5)": 1.0, "SSS scale 1.15": 0.0, "sensing noise 0.05": 0.2} | differs |
| collapse modes | {"address loss of A2 (40 ticks)": "differentiated stimulus >= threshold", "resource pulse 4.0 (oversupply)": "differentiated stimulus >= threshold", "renewal efficiency 0.7": null, "coupling weakened (gain 0.5)": "differentiated stimulus >= threshold", "SSS scale 1.15": null, "sensing noise 0.05": null} | {"address loss of A2 (40 ticks)": "differentiated stimulus >= threshold", "resource pulse 4.0 (oversupply)": "differentiated stimulus >= threshold", "renewal efficiency 0.7": "differentiated stimulus >= threshold", "coupling weakened (gain 0.5)": "differentiated stimulus >= threshold", "SSS scale 1.15": null, "sensing noise 0.05": "differentiated stimulus >= threshold"} | differs |
| history dependence (share of seeds that collapse without history) | 1.0 | None | differs |
| M2 dependence (persists without the tap, of 5) | n/a: the set has no tap | 0 of 5 persist without the tap | differs |
| Address dependence (mean collapse share under the Address fault battery) | 0.72 | 0.72 | same |
| Address faults (collapse share per fault) | {"loss of A1": 1.0, "loss of A2": 1.0, "partial A2 (50 %)": 1.0, "fragment of A2 (50 %)": 0.6, "delayed update of A2 (to 9,6; 20 ticks)": 0.0} | {"loss of A1": 1.0, "loss of A2": 1.0, "partial A2 (50 %)": 1.0, "fragment of A2 (50 %)": 0.6, "delayed update of A2 (to 9,6; 20 ticks)": 0.0} | same |
| SSS region at the default setting | OBSERVATION-SENSITIVE | OBSERVATION-SENSITIVE | same |
| operationally active range along scale | [0.5, 1.5] | [0.5, 1.5] | same |
| operationally active range along size | [0.5, 1.25] | [0.75, 1.25] | differs |
| operationally active range along speed | [0.75, 2.0] | [0.5, 1.1] | differs |
| metastable settings on the axes | {"scale": null, "size": null, "speed": null} | {"scale": null, "size": null, "speed": null} | same |
| observational robustness | 0.0 | 0.0 | same |
| stability across the validation seeds (persisting seeds of 5; mean cycles; mean cycle-interval CV) | [5, 47.0, 0.0] | [5, 47.0, 0.0] | same |

Equivalence reached: through level 2; operationally equivalent at level L2; non-equivalent at level L3 (differs in: perturbation sensitivity (Jaccard 0.60), history dependence).

**Claim, limited to what is justified:** route non-equivalence: both sets preserve the same specified operation in every validation seed, and they differ in internal operating form, dependence and stable region (resource throughput; recovery latency after the pulse (ticks); perturbation sensitivity (collapse share per perturbation); collapse modes; history dependence (share of seeds that collapse without history); M2 dependence (persists without the tap, of 5)). Both sets preserve the same specified operation with the same energy use and the same stability across the validation seeds; they differ in resource throughput, recovery latency, perturbation sensitivity, collapse modes, history/M2 dependence and the active range along size and speed.
This is shown for F14 only; it is **not generalised** to other conditions (13 of 16 conditions have a single MFS). The M2 substitution for history here is conditional on this combination of conditions (see section 11).

## 9. F9: a negative result, kept

Under the allowed reductions and specified preservation criterion, no validated inclusion-minimal retaining set was found. This is a result about these seeds (search 1-5) and these reductions only; it does not say that no retaining set exists in general.

The search evaluated 1024 subsets; 0 persisted on every search seed, so there is no candidate and no near miss. Class NO_MFS. This is a result about this condition (regrow 0.01, charge 0.2), these reductions and these seeds; it is not universalised, and F9 is not hidden or merged into another class.

## 10. Role of history

| condition | history role | class |
|---|---|---|
| F1 | contributes in some contexts only | SINGLE_MFS |
| F2 | redundant | SINGLE_MFS |
| F3 | substitutable | SINGLE_MFS |
| F4 | redundant | SINGLE_MFS |
| F5 | contributes in some contexts only | SINGLE_MFS |
| F6 | contributes in some contexts only | SINGLE_MFS |
| F7 | not available under this condition | SINGLE_MFS |
| F8 | compensatory | SINGLE_MFS |
| F9 | null | NO_MFS |
| F10 | compensatory | SINGLE_MFS |
| F11 | substitutable | SINGLE_MFS |
| F12 | necessary | SINGLE_MFS |
| F13 | necessary | SINGLE_MFS |
| F14 | substitutable | MULTIPLE_MFS |
| F15 | necessary | SINGLE_MFS |
| F16 | compensatory | INCONCLUSIVE |

History is necessary in F12, F13 and F15 (scale 1.5), compensatory in F8, F10 and F16 (needed only because the condition degrades coupling or renewal), substitutable by the M2 tap in F3, F11 and F14, redundant in F2 and F4 (unlimited power), null in F9 (no retaining set), and not available in F7. No single role holds across conditions.

## 11. M2 as a substitute for history (experiment G)

| M2 variant | cells where history is needed and M2 substitutes | proportion (Wilson 95 %) |
|---|---|---|
| direct | 6/25 | 0.24 [0.12, 0.43] |
| delayed(3) | 10/25 | 0.40 [0.23, 0.59] |
| noisy(0.05) | 2/25 | 0.08 [0.02, 0.25] |
| threshold(0.05) | 6/25 | 0.24 [0.12, 0.43] |

M2 substitutes for history in a minority of the cells where history is needed, and the proportion depends on the M2 variant and on scale, speed, resource and coupling (per-factor proportions are in `experiments_stage5.json`, `G.G1_scope_of_substitution`). The result is a **conditional** substitution, not a general one.

## 12. Dynamic Address (experiment H)

The present MEOS dynamics did not sustain a long-lived spatially separated configuration suitable for independently testing persistent address dependence. In every persisting arrangement of the 48 screened, the two configurations ended on one cell and A2 stopped moving after tick 60.

This is not a finding that Address is unnecessary: with the configurations on one cell, collision, stale and crossing cannot differ from the control, and loss, reassignment and partial addressability collapsed the run.

48 arrangements were screened (A2 start cell, A2 speed, sensing radii); **6 persisted in all 5 seeds**; none of them kept the two configurations apart.

| persisting arrangement | separation after tick 60 (cells) | A2 moves after tick 60 | separated | moving late |
|---|---|---|---|---|
| A2@5,6 speed 1.0 radii A2 2 A1 2 | 0.0 | 0.0 | False | False |
| A2@5,6 speed 1.0 radii A2 4 A1 2 | 0.0 | 0.0 | False | False |
| A2@5,6 speed 1.0 radii A2 6 A1 2 | 0.0 | 0.0 | False | False |
| A2@7,6 speed 1.0 radii A2 4 A1 2 | 0.0 | 0.0 | False | False |
| A2@7,6 speed 1.0 radii A2 6 A1 2 | 0.0 | 0.0 | False | False |
| A2@9,6 speed 1.0 radii A2 6 A1 2 | 0.0 | 0.0 | False | False |

Outcome of the 180 fault cells on those arrangements: collapse 95, dynamics changed without collapse 25, null (dynamics identical to the control) 60.

Stage 4 strict nulls (collision, stale) are kept and are **fixed-configuration** results; Stage 5 H is the dynamic attempt. In the dynamic screen the collision, stale and crossing faults are again null on the persisting arrangements (listed in section 22), and loss, reassignment and partial addressability collapsed the run.

## 13. Reconfiguration (experiment I)

Success is defined by **pre-defined metrics, not by a switch occurring**: persistence better than the no-reconfiguration control by >= 3 of 10 seeds, Fisher exact p < 0.05 (unadjusted), mean switching cost <= 3. Holm correction over the 30 comparisons is reported next to the unadjusted p.

| scenario | controller | persisted | no reconfiguration | difference (seeds) | Cohen's h | Fisher p | Holm p (30) | switches / run | false switches | unnecessary | switching cost | energy vs none | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| history lost | fixed | 5/10 | 0/10 | 5 | 1.5708 | 0.03251 | 0.9753 | 1.0 | 0 | 0 | 1.0 | 11.04 | **effective** |
| history lost | adaptive | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.0 | 0 | 0 | 0.0 | 0.0 | **no effect** |
| history lost | adaptive_shed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 1.0 | 0.0 | **no effect** |
| history lost | delayed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.0 | 0 | 0 | 0.0 | 0.0 | **no effect** |
| history lost | noisy | 1/10 | 0/10 | 1 | 0.6435 | 1.0 | 1.0 | 0.1 | 1 | 0 | 0.1 | 0.0 | **no effect** |
| coupling weakened (gain 0.5) | fixed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 1.0 | 0.0 | **no effect** |
| coupling weakened (gain 0.5) | adaptive | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.0 | 0 | 0 | 0.0 | 0.0 | **no effect** |
| coupling weakened (gain 0.5) | adaptive_shed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 1.0 | 0.0 | **no effect** |
| coupling weakened (gain 0.5) | delayed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.0 | 0 | 0 | 0.0 | 0.0 | **no effect** |
| coupling weakened (gain 0.5) | noisy | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.0 | 0 | 0 | 0.0 | 0.0 | **no effect** |
| resource reduced | fixed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 1.0 | 0.0 | **no effect** |
| resource reduced | adaptive | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.0 | 0 | 0 | 0.0 | 0.0 | **no effect** |
| resource reduced | adaptive_shed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 1.0 | 0.0 | **no effect** |
| resource reduced | delayed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.0 | 0 | 0 | 0.0 | 0.0 | **no effect** |
| resource reduced | noisy | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.0 | 0 | 0 | 0.0 | 0.0 | **no effect** |
| renewal efficiency 0.6 | fixed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 1.0 | 0.0 | **no effect** |
| renewal efficiency 0.6 | adaptive | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.0 | 0 | 0 | 0.0 | 0.0 | **no effect** |
| renewal efficiency 0.6 | adaptive_shed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 1.0 | 0.0 | **no effect** |
| renewal efficiency 0.6 | delayed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.0 | 0 | 0 | 0.0 | 0.0 | **no effect** |
| renewal efficiency 0.6 | noisy | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.0 | 0 | 0 | 0.0 | 0.0 | **no effect** |
| renewal disabled | fixed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 1.0 | 0.0 | **no effect** |
| renewal disabled | adaptive | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 1.0 | 0.0 | **no effect** |
| renewal disabled | adaptive_shed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 2.0 | 0.0 | **no effect** |
| renewal disabled | delayed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 1.0 | 0.0 | **no effect** |
| renewal disabled | noisy | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.7 | 0 | 0 | 0.7 | 0.0 | **no effect** |
| Address degraded (A2 partial 50 %) | fixed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 1.0 | 0.0 | **no effect** |
| Address degraded (A2 partial 50 %) | adaptive | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.0 | 0 | 0 | 0.0 | 0.0 | **no effect** |
| Address degraded (A2 partial 50 %) | adaptive_shed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 1.0 | 0.0 | **no effect** |
| Address degraded (A2 partial 50 %) | delayed | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.0 | 0 | 0 | 0.0 | 0.0 | **no effect** |
| Address degraded (A2 partial 50 %) | noisy | 0/10 | 0/10 | 0 | 0.0 | 1.0 | 1.0 | 0.0 | 0 | 0 | 0.0 | 0.0 | **no effect** |

**Adaptive reconfiguration did not beat the controls.** Its persistence equalled that of no reconfiguration in 6 of 6 scenarios and was never better. It never switched in 5 of them (no library MFS matched what it sensed); where it switched (renewal disabled) the run still collapsed. This is a formal negative result and is kept as such.

**Fixed M2 fallback (kept separate):** the fixed fallback was 'effective' only for 'history lost' (5/10 against 0/10); this does not survive Holm correction over the original 10-seed family. It was therefore re-tested on fresh seeds:

| controller | persisted on fresh seeds 11-30 ('history lost') | Wilson 95 % |
|---|---|---|
| none | 0/20 | [0.00, 0.16] |
| fixed | 9/20 | [0.26, 0.66] |
| adaptive | 0/20 | [0.00, 0.16] |
| adaptive_shed | 0/20 | [0.00, 0.16] |

fixed against none: Cohen's h 1.4706, Fisher exact p 0.00123; adaptive against none: p 1.0; adaptive_shed against none: p 1.0.

The fixed fallback helped in one scenario ('history lost') and in no other; that success is kept separate, does not overwrite the adaptive failure, and is not evidence that adaptive reconfiguration works.

### 13.1 Why the adaptive controller did not act (diagnosis from its own log)

`backend/scripts/diagnose_adaptive_stage5.py` tallies the outcome of every decision of the adaptive controller (`docs/ecosystem/experiments_stage5_adaptive_diagnosis.json`; the main results file is unchanged):

| scenario | first decision (10 seeds) | all decisions (10 seeds, several per run) | switches |
|---|---|---|---|
| history lost | already wholly enabled (cost 0, no action): 10 | already wholly enabled (cost 0, no action): 25, no known route: 45 | 0 |
| coupling weakened (gain 0.5) | already wholly enabled (cost 0, no action): 10 | already wholly enabled (cost 0, no action): 70 | 0 |
| resource reduced | already wholly enabled (cost 0, no action): 10 | already wholly enabled (cost 0, no action): 70 | 0 |
| renewal efficiency 0.6 | already wholly enabled (cost 0, no action): 10 | already wholly enabled (cost 0, no action): 70 | 0 |
| renewal disabled | switch: 10 | switch: 10, already wholly enabled (cost 0, no action): 60 | 10 |
| Address degraded (A2 partial 50 %) | already wholly enabled (cost 0, no action): 10 | already wholly enabled (cost 0, no action): 70 | 0 |

In every scenario but 'renewal disabled' the controller's first decision, in all 10 seeds, was that the matched MFS is already wholly enabled (cost 0): the library holds sets that suffice when everything else is removed at tick 0, and the full arrangement already contains them, so the controller has nothing to enable and does not act while the run collapses. Only the fixed fallback adds a component that is in no MFS of the condition (the M2 tap). The library certifies configurations sustained from the start of a condition, not the passage through a stress in mid-run.

*Limit:* A statement about this controller and this library. It is not a finding that reconfiguration cannot help.

So the negative result of section 13 is mostly **structural**: the library lists sets that suffice when everything else is removed at tick 0; in the full arrangement they are already enabled, the cost of "switching" is 0, and the controller does nothing while the run collapses. This separates two questions the F-K experiments had run together: *which configurations can be sustained from the start of a condition* (answered by F: mostly one, sometimes none)
and *whether a run can pass through a stress that arrives in mid-run* (not answered: the library does not prescribe an action for it). It also explains why only the fixed fallback ever helped: it adds a component that is in no MFS of the condition (the M2 tap). This is a statement about this controller and this library, not about reconfiguration in general.

## 14. Shedding controller

`adaptive_shed` (the adaptive controller that may also shed components) is reported separately from the original adaptive controller, the fixed fallback and no reconfiguration (survival, collapse, time to recovery, switches, false and unnecessary switches, switching cost, energy cost):

| scenario | controller | persisted | collapsed | median recovery (ticks) | switches / run | false switches | switching cost | mean energy |
|---|---|---|---|---|---|---|---|---|
| history lost | none | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 120.7 |
| history lost | fixed | 5/10 | 5/10 | — | 1.0 | 0 | 1.0 | 131.74 |
| history lost | adaptive | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 120.7 |
| history lost | adaptive_shed | 0/10 | 10/10 | — | 1.0 | 0 | 1.0 | 120.7 |
| history lost | delayed | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 120.7 |
| history lost | noisy | 1/10 | 9/10 | — | 0.1 | 1 | 0.1 | 122.97 |
| coupling weakened (gain 0.5) | none | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 118.72 |
| coupling weakened (gain 0.5) | fixed | 0/10 | 10/10 | — | 1.0 | 0 | 1.0 | 118.72 |
| coupling weakened (gain 0.5) | adaptive | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 118.72 |
| coupling weakened (gain 0.5) | adaptive_shed | 0/10 | 10/10 | — | 1.0 | 0 | 1.0 | 118.72 |
| coupling weakened (gain 0.5) | delayed | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 118.72 |
| coupling weakened (gain 0.5) | noisy | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 118.72 |
| resource reduced | none | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 91.64 |
| resource reduced | fixed | 0/10 | 10/10 | — | 1.0 | 0 | 1.0 | 91.64 |
| resource reduced | adaptive | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 91.64 |
| resource reduced | adaptive_shed | 0/10 | 10/10 | — | 1.0 | 0 | 1.0 | 91.64 |
| resource reduced | delayed | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 91.64 |
| resource reduced | noisy | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 91.64 |
| renewal efficiency 0.6 | none | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 119.8 |
| renewal efficiency 0.6 | fixed | 0/10 | 10/10 | — | 1.0 | 0 | 1.0 | 119.8 |
| renewal efficiency 0.6 | adaptive | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 119.8 |
| renewal efficiency 0.6 | adaptive_shed | 0/10 | 10/10 | — | 1.0 | 0 | 1.0 | 119.8 |
| renewal efficiency 0.6 | delayed | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 119.8 |
| renewal efficiency 0.6 | noisy | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 119.8 |
| renewal disabled | none | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 118.22 |
| renewal disabled | fixed | 0/10 | 10/10 | — | 1.0 | 0 | 1.0 | 118.22 |
| renewal disabled | adaptive | 0/10 | 10/10 | — | 1.0 | 0 | 1.0 | 118.22 |
| renewal disabled | adaptive_shed | 0/10 | 10/10 | — | 1.0 | 0 | 2.0 | 118.22 |
| renewal disabled | delayed | 0/10 | 10/10 | — | 1.0 | 0 | 1.0 | 118.22 |
| renewal disabled | noisy | 0/10 | 10/10 | — | 0.7 | 0 | 0.7 | 118.22 |
| Address degraded (A2 partial 50 %) | none | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 118.77 |
| Address degraded (A2 partial 50 %) | fixed | 0/10 | 10/10 | — | 1.0 | 0 | 1.0 | 118.93 |
| Address degraded (A2 partial 50 %) | adaptive | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 118.77 |
| Address degraded (A2 partial 50 %) | adaptive_shed | 0/10 | 10/10 | — | 1.0 | 0 | 1.0 | 118.77 |
| Address degraded (A2 partial 50 %) | delayed | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 118.77 |
| Address degraded (A2 partial 50 %) | noisy | 0/10 | 10/10 | — | 0.0 | 0 | 0.0 | 118.77 |

Shedding switched more often than the original adaptive controller in 5 of 6 scenarios, but its persistence equalled the control in 6 of 6 and it was never better; on fresh seeds in 'history lost' it persisted 0/20. It is a **null result**.

## 15. SSS x MFS (experiment J)

On the tested grid, all ACTIVE points were also observation-sensitive: no point was ACTIVE without being OBSERVATION-SENSITIVE (the observation-sensitive set coincides with the operationally active set), so no independent observation-sensitive island is claimed.

Operationally active ranges along the axes (two seeds per point; a range is a statement about the scanned values, not between them), grouped by MFS that share the same region:

| MFS (same operationally active region) | scale | size | speed |
|---|---|---|---|
| MFS-F1-1, MFS-F2-1, MFS-F3-1, MFS-F4-1, MFS-F5-1, MFS-F6-1, MFS-F7-1, MFS-F11-1 | 0.5-1.1 | 1.0-1.25 | 0.9-2.0 |
| MFS-F8-1 | 0.5-1.5 | 0.75-1.25 | 0.75-2.0 |
| MFS-F10-1, MFS-F16-1 | 0.5-1.25 | 1.0-1.25 | 0.9-1.1 |
| MFS-F12-1, MFS-F13-1, MFS-F14-1, MFS-F15-1 | 0.5-1.5 | 0.5-1.25 | 0.75-2.0 |
| MFS-F14-2 | 0.5-1.5 | 0.75-1.25 | 0.5-1.1 |

The ranges differ between some MFS (the M2-mediated set of F14 is operationally active for speed 0.5-1.1 against 0.75-2.0 for the history-mediated set), so the SSS region is MFS-dependent on this grid. The observation-sensitive set coincided with the operationally active set (219 points); **no independent observation-sensitive island is claimed.**
Per-MFS maps are in the research pane (`sssmap=<MFS>`).

## 16. Observation robustness (experiment K)

Four measures are kept independent: operational (does the operation persist under perturbations), observational (does the observer agree with it across observation settings), recoverability and addressability. A set that is unobservable is not thereby a set that failed.

| MFS | operational robustness | observational robustness | addressability | recoverability | first observation setting that disagrees |
|---|---|---|---|---|---|
| MFS-F1-1 | 0.267 | 0.0 | 0.28 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |
| MFS-F2-1 | 0.433 | 0.0 | 0.28 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |
| MFS-F3-1 | 0.267 | 0.0 | 0.28 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |
| MFS-F4-1 | 0.433 | 0.0 | 0.28 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |
| MFS-F5-1 | 0.267 | 0.0 | 0.28 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |
| MFS-F6-1 | 0.267 | 0.0 | 0.28 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |
| MFS-F7-1 | 0.267 | 0.0 | 0.28 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |
| MFS-F8-1 | 0.633 | 0.0 | 0.28 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.05} |
| MFS-F10-1 | 0.5 | 0.0 | 0.36 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |
| MFS-F11-1 | 0.267 | 0.0 | 0.28 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |
| MFS-F12-1 | 0.5 | 0.0 | 0.28 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |
| MFS-F13-1 | 0.5 | 0.0 | 0.28 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |
| MFS-F14-1 | 0.5 | 0.0 | 0.28 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |
| MFS-F14-2 | 0.3 | 0.0 | 0.28 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |
| MFS-F15-1 | 0.5 | 0.0 | 0.28 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |
| MFS-F16-1 | 0.5 | 0.0 | 0.36 | 1.0 | {"sampling_interval": 2, "spatial_stride": 2, "threshold": 0.1} |

Observational robustness was 0.00 for **every** MFS: in every one the operation persisted in all confirmation seeds while the observer agreed with it in none of the observation settings of the battery (the first disagreement is listed per MFS). Hence the observer's view does not separate the MFS from each other (a null result), and 'unobservable, not failed' applies to all of them.

## 17. Route equivalence among validated MFS

Levels L1 (preserved operation) - L4 (collapse modes, observational robustness, SSS region); classes: equivalent at the tested preservation level / partially equivalent / non-equivalent / insufficient evidence. ACTIVE alone is never taken as equivalence.

| MFS a | MFS b | level reached | class | differences / verdict |
|---|---|---|---|---|
| MFS-F1-1 | MFS-F2-1 | 1 | **non-equivalent** | operationally equivalent at level L1; non-equivalent at level L2 (differs in: energy use) |
| MFS-F1-1 | MFS-F8-1 | 2 | **non-equivalent** | operationally equivalent at level L2; non-equivalent at level L3 (differs in: perturbation sensitivity (Jaccard 0.60), history dependence) |
| MFS-F1-1 | MFS-F14-2 | 4 | **equivalent at tested preservation level** | operationally equivalent at level L4 |
| MFS-F2-1 | MFS-F8-1 | 1 | **non-equivalent** | operationally equivalent at level L1; non-equivalent at level L2 (differs in: energy use) |
| MFS-F2-1 | MFS-F14-2 | 1 | **non-equivalent** | operationally equivalent at level L1; non-equivalent at level L2 (differs in: energy use) |
| MFS-F8-1 | MFS-F14-2 | 2 | **non-equivalent** | operationally equivalent at level L2; non-equivalent at level L3 (differs in: perturbation sensitivity (Jaccard 0.60), history dependence) |

Only distinct retaining sets are compared (each under the id of its first MFS; the F14 history-mediated set has the same components as MFS-F8-1). 'Equivalent' means: at the levels tested, not that the routes are identical.

## 18. Frontend integration

- **Research pane** (`MfsResults`): the F1-F16 table (compact; all columns behind a fold), the candidate list (validated MFS and rejected candidates, search and validation seeds apart), the comparison of two MFS with the saved equivalence verdict (or the statement that the pair was not compared), the SSS map of an MFS, the reconfiguration group (controller, scenario, outcome table).
- **Research map** layers: active / dormant / failed route, fixed fallback route, adaptive route, current MFS, alternative (validated) MFS, rejected candidate. Validated and candidate are distinguished by line type and mark (solid rule for the current MFS, dashed for validated alternatives, dotted for rejected candidates), not by colour alone.
- **Technical view**: route topology generated from the run record and the saved library only (components with state, path edges, MFS nodes, transitions with tick and cost, dotted candidate nodes); toggles for each route kind; no figure is drawn from anything but run data.
- **Replay markers**: route switch, MFS change, fixed fallback activation, adaptive switch, successful / failed reconfiguration, M2 takeover, history loss, Address reassignment, Address recovery; clicking one shows tick, source/target MFS, trigger, cost and the operational / observed / observability state. (Candidate discovery and validation are properties of the *search*, not of a run, so they are shown in the candidate table and not as timeline events.)
- **Deep links** (`deeplink.ts`): `seed, tick, mfs, route (controller:scenario), experiment, sssmap, sss, address, obs, layer, routelayers, cam, quality`; parse/format round-trips are tested and the same link always gives the same plan.

### Stage 5 captures (`docs/ecosystem/visual/stage5/`; the Stage 3 and Stage 4 images are kept where they are)

Each capture is a URL (see `frontend/scripts/ecosystem_capture.mjs`, entries 45-59); the exact camera, viewport and tier are in `visual/stage5/cameras-balanced.json`. They are all pictures of model records, not evidence.

| image | what it shows | deep link (after `?view=ecosystem&`) |
|---|---|---|
| `45-f14-history-mfs.png` | F14, history-mediated MFS: research map with current MFS and the validated alternative | `mfs=MFS-F14-1` |
| `46-f14-m2-mfs.png` | F14, M2-mediated MFS | `mfs=MFS-F14-2` |
| `47-f9-no-mfs.png` | F9 (NO_MFS) in the F1-F16 table, with the row marked | `experiment=F9` |
| `48-adaptive-failure.png` | adaptive controller, 'renewal disabled': the switch and the failed outcome (preserved: no) | `route=adaptive:renewal disabled` |
| `49-fixed-fallback-success.png` | fixed M2 fallback, 'history lost' (seed 1): preserved: yes (5 of 10 seeds in the experiment) | `route=fixed:history lost` |
| `50-sss-map-mfs-a.png`, `51-sss-map-mfs-b.png` | SSS map of the two F14 MFS | `sssmap=MFS-F14-1`, `sssmap=MFS-F14-2` |
| `52-observation-sensitive-active.png` | observation boundary and lattice over an operationally active run | `obs=interval:3,stride:2` |
| `53-dynamic-address-attempt.png` | an Address reassignment (A2 to 11,6 at tick 100) on the research map | `address=reassign@100:A2:11,6` |
| `54-route-topology.png` | route topology of the M2-mediated MFS run | `mfs=MFS-F14-2&tech=ncb` |
| `55-mfs-comparison.png` | the two F14 MFS side by side | `mfs=MFS-F14-1` (research tab) |
| `56-replay-transition-inspection.png` | the research tab at a controlled run: markers and the inspection at the transition | `route=adaptive:renewal disabled` |
| `57-technical-view-alternate-route.png` | technical view with the fixed fallback route, the failed history path and the MFS lines | `route=fixed:history lost&tech=ncb` |
| `58-rejected-candidate-route.png` | route topology of MFS-F8-1 with the **rejected candidate** (dotted, "not MFS") | `mfs=MFS-F8-1&tech=ncb` |
| `59-current-alternative-mfs-map.png` | the research map with current MFS, validated alternative and the rejected-candidate row | `mfs=MFS-F14-1&layer=mfs.current,...` |

Limits of these images: (a) the replay-marker click inspection (tick, source/target MFS, trigger, cost, states) is a click and cannot be written in a URL; the capture shows the research pane at that tick, and the click behaviour is covered by tests; (b) the route graph reads enable/disable operations,
so a parameter stress such as 'renewal disabled' shows as an intervention marker, not as a failed component.

## 19. Replay

- **Stored studies (264 runs):** replayed with this tree's backend (`backend/scripts/replay_stored_studies.py`, ids from `/tmp/replay264/ids.json`, stored runs from the zrs checkout): **264 of 264 identical** (`docs/ecosystem/evidence/replay_meos_stage5.json`, 535.9 s). No run was regenerated.
- **Baseline digests (meos-0.4):** result digest `b4cf1e522e8bee460eab30ee2a3f86ffd703a3f7969dc21271cf0240aa09adc5` and trace digest `bd3e588608139840831c2749b5051ac31a360d91c6a9a0131b9de3f0152ee1b7` are unchanged (`docs/ecosystem/evidence/meos_stage5_digests.txt`).
- **Recorded schedules:** a controlled run's recorded schedule replays identically **without** the controller (`POST /api/meos/reconfigure` returns `replay_identical`, and tests assert it); `POST /api/meos/replay` replays any record from its configuration and intervention schedule.
- **Replay in the UI:** the research tab shows the replay markers of section 18 and inspects tick, source/target MFS, trigger, cost and the operational / observed / observability state at each.

## 20. Performance

**Method.** Stage 3 (`93119a0`, port 3032), Stage 4 (`f61243a`, port 3033) and Stage 5 (this tree, port 3031) were measured **interleaved in time**: 6 repetitions, each repetition running the three builds once, the order rotating over a Latin square so that no build is always first or last.
Balanced tier, 150 frames, 1672 x 808 viewport, headless Chromium on the GPU (ANGLE/Metal). Conditions: habitat (static, orbit), overview (static, orbit), body close-up (static, orbit), and, for Stage 4 and Stage 5 only (Stage 3 has no research UI), the habitat stage with **the Research tab open** (`habitat+research`, with an observation setting on) and with **the Technical View open** (`habitat+technical`, research map, route layers and route topology on the sheet).
The benchmark page was the only browser; the preview browser pane was closed; nothing was built during the measurement (a first attempt in which a type-check ran during the first run was discarded and restarted).
Per condition: median, p95, p99, max of the frame time, and draw calls, triangles, geometry uploads, shader programs built, LOD switches and visibility flips (the last four from the orbit's per-frame series, which Stage 3 does not have).

**Machine state, not hidden.** The machine was not idle (other applications were running). Load average at the start of each run is in `docs/ecosystem/perf_stage5/paired/*.load`: 16 of 18 runs began at a 1-minute load of 3.1-6.8; **2 runs (3031_1, 3033_1, two of the three runs of repetition 1) began at a load of 16-18**. All six repetitions are in the primary analysis; the same analysis without repetition 1 is given as a **sensitivity analysis**, never as a replacement.

**Rule (the one fixed for the Stage 4 acceptance, before any of this data existed).** Per repetition the ratio of the two builds is formed (paired); its 95 % bootstrap interval (10 000 resamples over the repetitions, fixed seed) is computed. *Regression* if the lower bound exceeds 1.05; *no meaningful regression* if the upper bound is below 1.05; otherwise *inconclusive*. Mean FPS is not used.

### Stage 5 against Stage 4 (the Stage 5 changes: route/MFS layers, panels, deep links)

All 40 measures (5 conditions x static/orbit x median/p95/p99/max): primary analysis **0 regression, 12 no meaningful regression, 28 inconclusive**; without repetition 1: 0 regression, 11 no meaningful regression, 29 inconclusive.
Median and p95 (all measures in `docs/ecosystem/perf_stage5/paired/analysis_tables.md`):

| camera | mode | measure | Stage 4 (ms) | Stage 5 (ms) | paired ratio S5/S4 | 95 % CI | verdict |
|---|---|---|---|---|---|---|---|
| body | static | median | 16.65 | 16.5 | 0.988 | [0.914, 1.009] | no meaningful regression |
| body | static | p95 | 25.7 | 20.6 | 0.851 | [0.688, 1.047] | no meaningful regression |
| body | orbit | median | 17.1 | 17.35 | 0.988 | [0.882, 1.113] | inconclusive |
| body | orbit | p95 | 24.4 | 27.0 | 0.987 | [0.812, 1.296] | inconclusive |
| habitat | static | median | 17.95 | 17.8 | 0.961 | [0.878, 1.023] | no meaningful regression |
| habitat | static | p95 | 22.75 | 22.2 | 1.002 | [0.751, 1.028] | no meaningful regression |
| habitat | orbit | median | 19.85 | 20.15 | 1.026 | [0.893, 1.158] | inconclusive |
| habitat | orbit | p95 | 26.35 | 36.3 | 1.136 | [0.906, 1.562] | inconclusive |
| habitat+research | static | median | 16.65 | 16.35 | 0.985 | [0.93, 0.994] | no meaningful regression |
| habitat+research | static | p95 | 19.85 | 18.9 | 0.978 | [0.727, 1.069] | inconclusive |
| habitat+research | orbit | median | 16.3 | 16.3 | 0.985 | [0.887, 1.028] | no meaningful regression |
| habitat+research | orbit | p95 | 21.45 | 23.2 | 1.069 | [0.895, 1.121] | inconclusive |
| habitat+technical | static | median | 16.45 | 16.3 | 0.985 | [0.904, 1.0] | no meaningful regression |
| habitat+technical | static | p95 | 23.95 | 19.05 | 0.857 | [0.652, 1.116] | inconclusive |
| habitat+technical | orbit | median | 16.4 | 16.2 | 0.994 | [0.928, 1.037] | no meaningful regression |
| habitat+technical | orbit | p95 | 24.5 | 22.3 | 0.915 | [0.736, 1.193] | inconclusive |
| overview | static | median | 15.85 | 15.5 | 0.975 | [0.909, 1.026] | no meaningful regression |
| overview | static | p95 | 20.55 | 17.95 | 0.869 | [0.82, 0.993] | no meaningful regression |
| overview | orbit | median | 18.25 | 17.65 | 0.959 | [0.921, 1.174] | inconclusive |
| overview | orbit | p95 | 27.4 | 26.3 | 0.937 | [0.818, 1.328] | inconclusive |

**Verdict, Stage 5 against Stage 4: no regression is established.** No interval lies wholly above 1.05, with or without repetition 1. With the **Research tab open** and with the **Technical View open** the static median is *no meaningful regression* (0.985 [0.930, 0.994] and 0.985 [0.904, 1.000]); the orbit tails (p95, p99, max) of habitat stay *inconclusive* (e.g. habitat orbit p95 1.136 [0.906, 1.562]):
the data cannot exclude a worse orbit tail, and the repetition-1 load makes that tail the least reliable number here. Mean FPS is not a basis for any of this.

### Stage 5 against Stage 3 (the stage alone; no research UI in Stage 3), median and p95

| camera | mode | measure | Stage 3 (ms) | Stage 5 (ms) | paired ratio S5/S3 | 95 % CI | verdict |
|---|---|---|---|---|---|---|---|
| body | static | median | 15.85 | 16.5 | 1.039 | [1.003, 1.051] | inconclusive |
| body | static | p95 | 18.95 | 20.6 | 1.061 | [0.82, 1.445] | inconclusive |
| body | orbit | median | 15.95 | 17.35 | 1.094 | [1.032, 1.119] | inconclusive |
| body | orbit | p95 | 22.1 | 27.0 | 1.125 | [0.963, 1.405] | inconclusive |
| habitat | static | median | 18.2 | 17.8 | 0.995 | [0.943, 1.024] | no meaningful regression |
| habitat | static | p95 | 22.7 | 22.2 | 0.997 | [0.798, 1.086] | inconclusive |
| habitat | orbit | median | 19.5 | 20.15 | 1.02 | [0.894, 1.149] | inconclusive |
| habitat | orbit | p95 | 27.1 | 36.3 | 1.061 | [0.869, 1.489] | inconclusive |
| overview | static | median | 15.65 | 15.5 | 1.0 | [0.892, 1.036] | no meaningful regression |
| overview | static | p95 | 19.8 | 17.95 | 0.924 | [0.714, 1.017] | no meaningful regression |
| overview | orbit | median | 17.95 | 17.65 | 0.984 | [0.763, 1.282] | inconclusive |
| overview | orbit | p95 | 30.9 | 26.3 | 0.858 | [0.523, 1.282] | inconclusive |

Primary analysis, all 24 measures: **0 regression, 6 no meaningful regression, 18 inconclusive**; without repetition 1: **1 regression, 6 no meaningful regression, 17 inconclusive**. The one measure that changes class is the **body close-up orbit median** (primary 1.094 [1.032, 1.119], inconclusive; without repetition 1 the same measure is 1.106 [1.052, 1.125], which the rule calls a *regression*).
It is reported as it is: **a cost of roughly 5-12 % in the median frame time of the body close-up orbit against Stage 3 is probable**, it is not shown against Stage 4 (0.988 [0.882, 1.113]), and the other conditions show no regression against Stage 3.
The rendering counters agree with a small increase in geometry (body static triangles 999 878 in Stage 3, 1 021 422 in Stage 4 and Stage 5; draw calls 264 in all three).

### Counters (median over the repetitions; static camera unless noted)

| condition | build | draw calls | triangles | geometry uploads (orbit) | programs built (orbit) | LOD switches (orbit) | visibility flips (orbit) |
|---|---|---|---|---|---|---|---|
| habitat | stage3 | 427.0 | 1033428 | n/a | n/a | n/a | n/a |
| habitat | stage4 | 428.0 | 1065364 | 35 | 0 | 141 | 28 |
| habitat | stage5 | 428.0 | 1065364 | 35 | 0 | 142 | 28 |
| overview | stage3 | 455.0 | 653420 | n/a | n/a | n/a | n/a |
| overview | stage4 | 457.0 | 674384 | 21 | 0 | 145 | 64 |
| overview | stage5 | 457.0 | 674384 | 21 | 0 | 145 | 64 |
| body | stage3 | 264.0 | 999878 | n/a | n/a | n/a | n/a |
| body | stage4 | 264.0 | 1021422 | 38 | 1 | 0 | 40 |
| body | stage5 | 264.0 | 1021422 | 38 | 1 | 0 | 40 |
| habitat+research | stage3 | 384.0 | 960564 | n/a | n/a | n/a | n/a |
| habitat+research | stage4 | 385.0 | 989152 | 38 | 0 | 142 | 28 |
| habitat+research | stage5 | 385.0 | 989152 | 38 | 0 | 143 | 28 |
| habitat+technical | stage3 | 384.0 | 960564 | n/a | n/a | n/a | n/a |
| habitat+technical | stage4 | 385.0 | 989152 | 38 | 0 | 144 | 28 |
| habitat+technical | stage5 | 385.0 | 989152 | 38 | 0 | 142 | 28 |

Stage 5 and Stage 4 have identical counters (the Stage 5 changes are interface and data, not scene geometry): no program is built during an orbit except one in the body close-up, which both builds show.

**Not claimed:** no absolute frame rate is claimed for any machine other than this one under this load; software-rendered captures and the headless GPU figures are not comparable with each other.

## 21. Regression

Run on the final tree (`docs/ecosystem/evidence/`):

| check | result |
|---|---|
| backend, full `pytest` (`meos_stage5.junit.xml`, 977 s) | **756 tests: 754 passed, 2 failed** — the two known failures only: `tests/test_compat.py::test_engine_conformance_against_the_golden_fixture[desktop-scipy]` and `tests/test_lab.py::test_published_records_replay` (both failed in the baseline before this work; Stage 4 had 692 tests with the same two) |
| new Stage 5 backend tests (engine, mfs, reconf, experiments, final), service routes, security (mutating-route list incl. `route-topology`, `reconfigure`, `mfs-run`), layering | all passed (inside the full run) |
| `ruff check xzr tests bench scripts` | all checks passed |
| `mypy xzr/meos` | no issues (13 source files) |
| frontend `tsc -b`, `eslint src scripts` | clean |
| frontend `vitest` (`frontend_stage5.junit.xml`) | **253 tests, 0 failures** (Stage 4: 210) |
| 264-run replay of stored studies | **264 / 264 identical** |
| baseline result digest and trace digest | unchanged (section 19) |
| experiment F-K tests with the saved results | passed (saved minimality, baseline digest in the saved file, `final` block) |

The 2 known failures were already failing in the baseline and are not touched by Stage 5; they are listed, not hidden.

## 22. Null results (kept)

- F: 15 entries — no second route under 13 conditions, and F9 has no retaining set (section 9).
- G: M2 does not substitute for history in most cells (section 11).
- H: collision, stale and crossing faults are null on persisting arrangements (60 entries, all identical to the control):
- collision on A1 at tick 12 in A2@5,6 speed 1.0 radii A2 2 A1 2: dynamics identical to the control in all 5 seeds
- collision on A1 at tick 100 in A2@5,6 speed 1.0 radii A2 2 A1 2: dynamics identical to the control in all 5 seeds
- collision on A2 at tick 12 in A2@5,6 speed 1.0 radii A2 2 A1 2: dynamics identical to the control in all 5 seeds
- collision on A2 at tick 100 in A2@5,6 speed 1.0 radii A2 2 A1 2: dynamics identical to the control in all 5 seeds
- … and 56 more of the same kind (all are in `experiments_stage5.json`, `H.null_results`)
- I: persistence equal to no reconfiguration in 33 controller x scenario cells.
- K: observational robustness equal for every MFS.
- Stage 4 strict nulls (collision on A1/A2, stale address) are unchanged in `experiments_stage4.json`; they are not overwritten by Stage 5.
- Adaptive reconfiguration and the shedding variant: no effect against no reconfiguration (section 13/14).
- The first complete run of F (3 search seeds) is kept as `experiments_stage5_first_full_run.json` with its F8 second set; it is superseded, not deleted.

## 23. Failed hypotheses

1. **Multiple MFS is not widespread.** One condition of 16 (F14) has two validated MFS; 13 have one, one has none, one is inconclusive.
2. **The F8 second candidate failed validation** (persisted on 4/5 search and 1/5 validation seeds) and is not counted.
3. **Adaptive reconfiguration did not beat the controls**, nor did the shedding variant; only the fixed M2 fallback helped, in one scenario. The diagnosis (section 13.1) shows the adaptive controller mostly never acted (its matched MFS was already wholly enabled), so the result is about this controller and library, not about reconfiguration in general.
4. **Persistent spatial separation was not sustained:** A2 walked to A1 in every persisting arrangement, so persistent Address dependence could not be tested independently.
5. **The observation-sensitive region did not separate from ACTIVE** on the tested grid.
6. **Cable visual complexity is far below the reference** (measured in Stage 4: close-cable contour complexity 0.47 against 1.59 for the reference; not re-measured in Stage 5, whose changes did not touch the cable geometry): the visual representation does not reach the reference and says nothing about the model.

## 24. Limitations

- The model is a formal one; MFS are relative to the specified operation, the allowed reductions, the preservation criterion, the seeds and the 14 x 14 grid. "No MFS" or "single MFS" means this, not that no other realisation exists.
- Five search and five validation seeds: proportions with wide intervals; near-misses are reported as INCONCLUSIVE, not resolved.
- Experiments G and H do no hypothesis test across cells; the reconfiguration verdicts use Holm over 30 comparisons and several effective results do not survive it.
- The controller senses five features and can only enable components of library MFS; the library holds from-start sufficiency sets, so in mid-run stress the matched MFS is usually already enabled and the controller does not act (section 13.1). A negative result is about this controller.
- Only the removal of components at tick 0 is explored for MFS search; mid-run removal and re-entry are covered in other experiments only.
- The route topology reads enable/disable operations; a parameter stress (e.g. renewal disabled by efficiency) does not appear as a failed component.
- Performance measurements are in a headless browser on one machine that was not idle (see section 20).

## 25. Remaining work

**Unimplemented**
- Search over mid-run removal and re-entry (MFS are searched for removal at tick 0 only). The adaptive-controller diagnosis (section 13.1) shows this is the missing experiment: a library of sets that survive a stress arriving in mid-run, from which a controller could actually prescribe an action.
- Controllers that sense more than five features or enable components outside the library; any learning controller.
- A clickable replay-marker inspection that can be written in a URL.

**Unverified**
- Whether more seeds would separate the F16 near miss and the F14 tail measures (near-miss candidates are reported INCONCLUSIVE).
- The cable-complexity gap to the reference (not re-measured in Stage 5).
- Stage 5 performance on other machines or under an idle machine: the headless GPU benchmark here ran under a shared load.

**Partial**
- Dynamic Address: only the arrangements the 14 x 14 grid lets persist were screened; the result is limited as stated in section 12 and is not a finding that Address is unnecessary.
- SSS x MFS: two seeds per point on the scanned grid; ranges are statements about scanned values.
- The route topology shows enable/disable operations only.
- The Research UI measures: median and static tails are no worse than Stage 4; the habitat orbit tail is inconclusive (section 20).
