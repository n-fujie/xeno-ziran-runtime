# XB-TRO — Claim / Evidence Ledger

Status: written 2026-10-20 from the stored records in `artifacts/xbtro/final/` (15 records, commit `d809a258e9` per `index.json`) and from the source tree at
`feat/xb-tro`. **Nothing here was estimated.** Where the records do not contain a number (for example the total count of simulated body runs), the
ledger says "not recorded". Interpretation (what a result might mean for a theory) is kept apart from what was measured.

## 0. How to read this ledger

| Term | Meaning here |
|---|---|
| **Implementation property** | a statement about the software (it does X); evidenced by source and tests, not by an experiment |
| **Simulation result** | a measured outcome of the planar XB-TRO model under stated conditions and seeds; says nothing about a real body |
| **Interpretation** | a reading of results in terms of Operational-Shape Realism / Ziran System / Xenoscience; **not evidence** |
| **Independent seeds** | number of distinct random seeds in a paired design; the unit of replication. A *trial* (one simulated body run) is not counted in the records |
| **Smoke / confirmatory** | all XB-TRO records are exploratory-to-final simulation studies with 8–16 seeds; none is a pre-registered confirmatory study at the 10,000-trial target |

### Facts that apply to every row

* **Records**: `artifacts/xbtro/final/records/*.json|csv`, `index.json`, `SUMMARY.md`. Re-run entry point: `xzr.xbtro.experiments.run_to_end(exp_id, params)` (catalogue `EXPERIMENTS`); script `backend/scripts/run_xbtro_final.py`.
* **Environment recorded in every record**: `arm64`, `darwin`, Python `3.12.13`, numpy `2.5.3`, `model_version xb-tro/1.0`, code commit `d809a258e9` (checked today with `git diff --stat d809a258e9 HEAD -- backend/xzr`: only `xbtro/live.py` and `service/xbtro_ops.py` differ — the live-inspection fix of `1c5c155`; `engine.py`, `metrics.py`, `experiments.py`, `fragility.py`, `stats.py` and the other experiment modules are identical, and the records were not regenerated).
* **Integrity**: the stored `digest` of all 15 records equals the digest recomputed from the stored `results` today (`artifacts/xbtro/diagnosis/verify_record_digests.py`, 0 mismatches). This shows the files were not edited after writing; it does not show the experiment is correct.
* **Seeds**: final records use seeds `5000..5011` (12), the first report of G `5000..5007` (8), the independent replication of G `7000..7015` (16). Exploration seeds `1000..1031` were used during development; **their results were not stored** and are not evidence.
* **Total number of simulated runs**: not recorded in any record. The catalogue (`EXPERIMENTS` in `experiments.py`) lists `n_seeds` and `sims` per experiment (e.g. A: 12 and 2) but how `sims` maps to runs per seed is not documented in the records, so no product is stated here.
* **10,000-independent-trial target**: **not reached by any study** (largest paired design: 16 independent seeds). Every row's "supported scope" is therefore limited to what 8–16 seeds can show; the plan documents a minimum detectable paired effect of ≈0.81 (12 seeds) and ≈0.70 (16 seeds) at 80 % power, α = 0.05. "No detectable effect" is never "no effect".
* **Reproducibility of the records**: bit-identical on one platform; across platforms to rounding, so the record digest is taken over values rounded to 6 significant digits (`records.py`). Cross-transport equality (HTTP / native bridge / Pyodide) is evidenced in row XB-03. Re-execution *today* in a different environment is recorded in §3 (added after the Phase 2 runs).
* **Pre-registered tolerance bands**: human-like 9 mm, machine-like 9 mm (rule in `metrics.py`). A 13 mm band is reported only as a sensitivity analysis (records `B_band_13mm`, `D_band_13mm`).

## 1. Claims

Columns of each block: scientific claim · implementation · conditions · controls · seeds / trials · metrics · results · uncertainty · ablation · relation to prior work · supported scope · unverified · falsification condition · withdrawal condition.

### XB-01 — The explicit-RK4 plant is numerically stable only above a sub-step threshold, and the code can tell divergence from a physical fall *(simulation result + implementation property)*

| | |
|---|---|
| Claim | For the human-like planar preset an a-priori spectral-radius check of the step matrix refuses configurations that are unstable (explicit Euler / semi-implicit Euler at co-contraction 0.9, RK4 with 1 sub-step), and run-time divergence is recorded separately from physical falls. |
| Implementation | `xzr/xbtro/engine.py` (RK4, `task.substeps`, `task.integrator`), `verification.py` (stability check, forced-run validation), `metrics.py` (fell vs diverged) |
| Conditions | presets human-like / machine-like; integrators rk4, semi-implicit-euler, explicit-euler; co-contraction 0, 0.3, 0.9; 8 conditions × 2 presets × 2 protocols |
| Controls | the same configurations at nominal co-contraction; forced runs of refused configurations (4 seeds each) |
| Seeds / trials | record `V_standard`, seeds 5000..5011 (12); forced-run checks use 4 seeds. Trials: not recorded |
| Metrics | spectral radius ρ of the step matrix, max |λ|h, condition number of M, diverged / fell counts, COM differences |
| Results | human-like: RK4 stable at cc 0–0.9 (ρ 0.998–0.999); semi-implicit Euler UNSTABLE at cc 0.9 (ρ 1.77); explicit Euler UNSTABLE at cc 0.9 (ρ 1.46); RK4 with 1 sub-step refused (forced: ρ = 12.84, diverged 4/4 at cc 0.9, 0/4 nominal). Machine-like: all stable (ρ 1). Condition number of M 227 (human) / 471 (machine) |
| Uncertainty | deterministic checks; 4 seeds for forced runs, counts only |
| Ablation | integrator and sub-step variants are the ablation |
| Prior work | standard stiffness / stability analysis of explicit integrators; no novelty claimed |
| Supported scope | the two planar presets with the listed parameters, cc ∈ [0, 0.9]; the check is *sufficient, not necessary* for stability |
| Unverified | other parameter ranges; behaviour on a 3-D or contact-rich body; iOS device |
| Falsification | a configuration the check accepts (ρ<1) that diverges in a noiseless run, or one it refuses that is stable under a longer test |
| Withdrawal | such a counterexample inside the stated cc range |
| Evidence files | `final/records/V_standard.json`, `SUMMARY.md` (V tables); tests `tests/test_xbtro_numerics.py` |

### XB-02 — The simulation converges as the time step shrinks *(simulation result)*

| | |
|---|---|
| Claim | Noiseless trajectories converge under sub-step refinement. |
| Results | human-like RK4: 2 sub-steps vs reference RMS COM difference 2.35e-05 m (max 9.32e-05); 4 sub-steps 2.35e-07 (max 6.54e-07); control step halved 5.18e-04 (max 1.32e-03). Machine-like RK4: 1 sub-step 2.83e-08 (max 6.46e-08), 2 → 1.70e-09, 4 → 9.75e-11; semi-implicit Euler 2 sub-steps 4.79e-05; explicit Euler 4.21e-05 |
| Implementation / evidence | as XB-01 (`V_standard`); `tests/test_xbtro_numerics.py` |
| Seeds | noiseless: seed-independent; V uses 5000..5011 for the condition table |
| Supported scope | the two planar presets, the stated task protocol (7.5 s horizon) |
| Unverified | convergence order was not fitted; the RK4 row on the human-like preset with 1 sub-step is refused, not measured |
| Falsification / withdrawal | non-monotone error under refinement; a different protocol where RK4 errors do not shrink |

### XB-03 — The same engine gives identical results through HTTP, the native bridge and the in-browser (Pyodide) runtime *(implementation property, measured)*

| | |
|---|---|
| Implementation | `service/xbtro_ops.py` (one route table), `native/bridge.py`, `scripts/xbtro_paths.py`, `scripts/xbtro_digests.py` |
| Evidence | `artifacts/xbtro/pyodide_s1.json` (S1 body sequence: 210 values identical at 6 decimals across the three transports, per `README.md`); `desktop_digests.json` vs `browser_digests.json`: 13 labelled digests, **equal for every label** (checked again today, 13/13) |
| Conditions | 4-seed small standard set; Pyodide without threads, cooperative job slices, built from the same commit |
| Seeds / trials | 4 seeds per labelled experiment; trials not recorded |
| Supported scope | those 13 experiments at that resolution (6 significant digits), those platforms (macOS arm64 desktop; Pyodide 314.0.7 build) |
| Unverified | **iOS device: not available, no behaviour claimed.** Other platforms (Windows, Linux, Intel). Equality at higher resolution |
| Falsification / withdrawal | any labelled digest that differs between transports on the same commit |
| Note | a related, separate platform sensitivity exists in the *hierarchy* used by the Ziran runtime scenarios (see `diagnosis/test_compat/`); it does not involve XB-TRO |

### XB-04 — Changing the observation configuration changes which differences between body conditions are identified; unobserved differences carry a reason *(simulation result)*

| | |
|---|---|
| Implementation | `observation.py`, `tro.py`, `experiments.py` (A, E, M) |
| Conditions | hidden changes: mixed, delay-only, tone-only, fatigue-only; configurations: motion only; motion + EMG-like + contact; dynamic (after up to 4 reconfiguration rounds) |
| Controls | the motion-only configuration; hand-chosen configuration vs automatically revised one |
| Seeds / trials | `A_standard`, `E_standard`: seeds 5000..5011 (12). Trials not recorded. Negative results stored: A 6, E 18 |
| Results (A) | differences that exist 10; identified: motion-only 2 (identifiability 0.2), motion + EMG-like + contact 6 (0.6), dynamic 5 (0.5). Unobserved reasons: motion-only `device-mismatch` 5, `unmeasured` 1 |
| Results (E) | mixed: 10 exist, 2 identified at start, 5 after revision (set-up time 110 s); delay-only 6 exist, 1 → 5; tone-only 5 exist, 2 → 4; fatigue-only 2 exist, 1 → 1; 4 rounds changed the configuration in each |
| Uncertainty | counts over the 12-seed design; no interval stored in the summary |
| Ablation | configuration with vs without the extra devices |
| Prior work | observability / identifiability in control theory; Active-Inference-style observation selection is not compared here |
| Supported scope | the simulated planar body, the listed alterations, simple signal-model devices |
| Unverified | real sensors; whether "identified" generalises; the automatic revision beating a better hand-chosen configuration (the dynamic configuration identified 5 vs 6 for the hand-chosen one) |
| Falsification | a configuration that identifies more differences than the revision procedure on the same seeds with the same budget; a "device-mismatch" reason that disappears when the device is added without other changes |
| Withdrawal | if a re-run with a different seed block changes the ordering motion-only < dynamic ≤ motion+EMG |

### XB-05 — Couplings can be classified by interventional support rather than correlation alone *(simulation result)*

| | |
|---|---|
| Implementation | `coupling.py`, `experiments.py` (B) |
| Seeds / trials | `B_standard` seeds 5000..5011 (12); negative results stored 20; sensitivity `B_band_13mm` (18 negative) |
| Results | classes: correlational-only 5, interventionally-supported 3, untested 2 |
| Supported scope | the listed couplings under the delay / block / reconnection interventions |
| Unverified | couplings outside the tested interventions ("untested" is not "absent"); statistical power of each classification (stated generically as ≈0.81 MDE) |
| Falsification / withdrawal | a coupling classed interventionally-supported whose effect vanishes under an independent seed block |
| Band sensitivity | control recovery time (restricted mean) 1.58 s at the registered 9 mm band vs 0.89 s at 13 mm |

### XB-06 — The Fragility Transfer matrix has no universal sign: improving one organization improves some others and weakens others, depending on the principle *(simulation result)*

| | |
|---|---|
| Implementation | `fragility.py`, `xeno14.py`, `experiments.py` (C) |
| Conditions | 9 Xeno-14 principles as experimental conditions on the human-like preset (C), combos on/off |
| Controls | matched control (same seeds) |
| Seeds / trials | `C_standard` seeds 5000..5011 (12); 14 negative/null results stored. Trials not recorded |
| Results | e.g. lower-abdominal-continuity improved {posture_stability, turn_speed}, weakened {correction_quality, recovery_time}; low-noise-movement improved {correction_quality}, weakened {turn_speed, precision}; slow-movement improved {correction_quality}, weakened {turn_speed, precision, fatigue_cost}; breathing-synchronization improved {posture_stability, turn_speed, precision, recovery_time}, weakened {correction_quality} (full list in `SUMMARY.md` §C) |
| Uncertainty | paired differences with sign-flip permutation, BH q < 0.05 and |d| ≥ 0.8 (`stats.py`); MDE ≈ 0.81 at 12 seeds |
| Ablation | not reported in the C summary (the rule-line share is reported for G, XB-07) |
| Prior work | multi-objective trade-offs; "no free lunch" in control; no priority claimed |
| Supported scope | planar translations of the principles (see XB-13), 12 seeds, one preset |
| Unverified | the sign of any transfer in a real body; the effect of combos beyond those tested |
| Falsification | a principle whose listed transfer reverses in an independent seed block with adequate power |
| Withdrawal | if the transfer lists are not stable under row XB-09's variants (they are *not* fully stable: see XB-09) |

### XB-07 — Directional Fragility Transfer: for axis-maintenance, push deviation and the recovery region get worse; this weakening replicated on an independent seed block *(simulation result)*

| | |
|---|---|
| Implementation | `fragility.py` (G; state-matched pushes), `experiments.py` |
| Conditions | first report: 8 seeds (5000..5007), four principles with ablation; replication: 16 seeds (7000..7015), all fourteen principles |
| Controls | matched control and ablation of the rule line, same seeds |
| Seeds / trials | `G_original_conditions` (8; 2 negative), `G_standard` (12; 7 negative), `G_independent_replication` (16; 6 negative). Trials not recorded |
| Results (first report) | peak push deviation (forward) 0.036 → 0.049 m, **+0.0131 m (≈ +1.3 cm)**, d = 1.48, q = 0.0375, "worsened"; recovery region **+2.12 rungs** (1 → 3.12), d = 3.32, q = 0.0375, "worsened" |
| Results (replication) | peak deviation +0.0125 m, d = 1.06, q = 0.00432, "worsened"; recovery region +2.38, d = 2.18, q = 0.00124, "worsened" |
| Uncertainty | BH-corrected q and effect size d as above; sign-flip permutation; MDE ≈ 0.70 at 16 seeds |
| Ablation | the change is attributed to the rule line itself ("due to the rule line" equals the difference) |
| Prior work | none claimed |
| Supported scope | the planar model, this push protocol (state-matched pushes) |
| Unverified | other pushes / directions; other presets; reality |
| Falsification | an independent seed block (≥16 seeds, new range) where either difference is not "worsened" at q < 0.05 |
| Withdrawal | on such a block; also if the first-version G (`history/G_v0_push_during_movement.json`, flawed: pushed during movement) were found to be the correct protocol |
| Kept record | the first, flawed version of G is kept in `artifacts/xbtro/history/` with its explanation |

### XB-08 — *Negative result.* The apparent improvement of axis-maintenance in settling after the later direction change did **not** replicate *(simulation result)*

| | |
|---|---|
| Results | first report: turn_settling_after_push 1.5 → 0.734 s, d = −17, q = 0.0375, "improved"; replication: 1.49 → 1.15 s, d = −0.566, q = 0.142, "no detectable effect". Correction latency: "no detectable effect" in both |
| Reading (computed in `SUMMARY.md`) | weakening replicated; improvement NOT replicated |
| Supported scope | none for the improvement; it must not be cited as an effect |
| Unverified | whether a smaller true improvement exists (the replication could not detect |d| < 0.70) |
| Falsification / withdrawal | the claim "improvement" is already withdrawn; it would need a new, larger independent block to be reinstated |

### XB-09 — Individual transfers in the matrix are sensitive to analysis variants; only three principles transfer in every variant *(simulation result)*

| | |
|---|---|
| Evidence | `R_standard` (12 seeds; 39 negative results stored) |
| Results | 98 cells; 59 have the identical label in every variant; transfers present in every variant: breathing-synchronization, endpoint-removal, zero-run-up-transition; present in some variants only: axis-maintenance, low-noise-movement, lower-abdominal-continuity, minimal-approach-distance, narrow-step-balance, slow-movement, tensegrity, whole-skin-sensing |
| Consequence | claims in XB-06 about the eight "some variants" principles are **fragile** and must be cited with that qualifier |
| Unverified | which variant is "right" |

### XB-10 — Operational velocity measures are mostly defined for the baseline, but recovery is defined only for part of the seeds and depends on the tolerance band *(simulation result)*

| | |
|---|---|
| Evidence | `D_standard`, `D_band_13mm` (12 seeds; 13 and 13 negative results) |
| Results | defined for all seeds: sensory_detection 0.12 s, neural_response 0.12 s, muscle_onset 0.124 s, movement_onset 0.766 s, correction 0.263 s, settling 1.49 s, consequence 0.881 s, adaptation 0.0128 per trial; **recovery defined for 58.3 % of seeds** (mean 1.28 s) at the registered 9 mm band, **100 % (0.89 s) at 13 mm**; reconfiguration: fraction defined 0 (not measurable in this baseline). "Estimable from observations": neural_response, muscle_onset, correction, settling yes; the rest no |
| Method point | censored metrics (NaN + status, restricted mean) so the window cap is never recorded as a time |
| Supported scope | the human-like baseline |
| Unverified | the "right" band; the human-like recovery classification is band-sensitive and must be reported with both |
| Falsification / withdrawal | a seed block where the 9 mm / 13 mm discrepancy disappears or reverses |

### XB-11 — In the planar model the machine-like preset recovers from stronger pushes than the human-like preset *(simulation result)*

| | |
|---|---|
| Evidence | `F_standard` (12 seeds; 1 negative) |
| Results | strongest push recovered in ≥ 50 % of seeds: human-like 40 N, machine-like 80 N. Recovered fraction by push (N): human 20→1, 40→0.667, 60→0.25, 80→0, 100→0; machine 20–80→1, 100→0.167, 130→0 |
| Supported scope | these two parameter sets of the planar model only. "Human-like" and "machine-like" are labels of presets, not claims about humans or machines |
| Unverified | any real-body or real-robot threshold |
| Falsification / withdrawal | different preset parameters within their documented ranges reversing the order |

### XB-12 — Operation paths and an MO-style (retract-if-no-gain) policy can be selected under stated constraints *(simulation result)*

| | |
|---|---|
| Evidence | `S_standard` (12 seeds; 5 negative), `M_standard` (12 seeds; 5 negative) |
| Results | S ('reach-target'): selection under constraints = "Xeno-14: zero-run-up transition" (latency 0.492 s vs baseline 0.881 s, energy 0.106 vs 0.102); ('stay-upright') = "Xeno-14: slow movement". "Xeno-14: endpoint removal" was dominated for reach-target (non-dominated = 0). M: stopped by the round limit; rounds: 1 retracted (no measured gain), 2 retracted, 3 kept, 4 retracted (the apparatus changes the body) |
| Supported scope | the simulated body and the stated constraints; it is a demonstration of selection, not evidence that the chosen path is best in general |
| Unverified | whether the policy generalises; MO and MS are *not implemented* in the Ziran specification's own status — this is a limited instance (XB-14) |

### XB-13 — The fourteen Xeno-14 principles are implemented as experimental conditions with explicit fidelity levels *(implementation property)*

| | |
|---|---|
| Implementation | `xzr/xbtro/xeno14.py` (`PRINCIPLES`, `FIDELITY`); canonical names from `ziran-xeno-simulator/src/domains/body.ts` (`XENO14`) — all 14 names match (checked today) |
| Fidelity (from the registry) | translated (8): lower-abdominal-continuity, axis-maintenance, endpoint-removal, zero-run-up-transition, tensegrity, slow-movement, narrow-step-balance, anti-collapse-posture · partial (3): whole-skin-sensing, low-noise-movement, breathing-synchronization · proxy-only (3): minimal-approach-distance, fingertip-tension, long-duration-sedimentation |
| Supported scope | the registry states for each principle its operationalization and its gap (`gap` field), e.g. fingertip-tension "is NOT a fingertip" |
| Evidence | `tests/test_xbtro_xeno14.py` |
| Unverified | fidelity to the original specification beyond the written `source_rule`/`gap` comparison |
| Withdrawal | a principle whose operationalization contradicts its `source_rule` |

### XB-14 — MO / DO / ZCA / MS appear only as limited instances over the body model; nothing here completes them *(implementation property)*

| | |
|---|---|
| Implementation | `xzr/xbtro/ziran.py`, quoted from `pa-philosophy-in-audit/data/ziran.ts` |
| Status per the Ziran specification | MO, MS: NOT IMPLEMENTED; DO, ZCA: PARTIAL (`pa-simulation-environment/docs/ZIRAN_CURRENT_SPECIFICATION.md`) |
| Evidence | `tests/test_xbtro_ziran.py`; `docs/XBTRO.md` |
| Supported scope | the instances run on the body model and are recorded; the quotation of the specification is verbatim in intent |
| Unverified | agreement of the instances with the specification's intended semantics (no independent reviewer) |

### XB-15 — Mutating routes are off by default on a public server *(implementation property)*

| | |
|---|---|
| Implementation | `service/xbtro_ops.py::enabled()` (`XZR_PUBLIC=1` turns the XB-TRO routes off), owner scoping, limits `XZR_XB_*` |
| Evidence | `tests/test_security.py`, `tests/test_xbtro_security.py`: passed in the 2026-10-18 run and in the 2026-10-20 full run in this worktree (358 passed, 1 skipped, 1 failed — the failure is `test_compat`, unrelated) |
| Unverified | the **deployed** site's behaviour (nothing is deployed); real-host routing (the local emulator cannot decide it) |

### XB-16 — Relationship to Operational-Shape Realism, Ziran System, Xenoscience, XenoSNN, XenoBody *(interpretation, not evidence)*

| Framework | What the records bear on | What they do not |
|---|---|---|
| Operational-Shape Realism | Results are about *operational differences in a planar simulator* (which differences ignite, are observed, transfer). They are consistent with treating "which differences matter" as an experimental question | They neither support nor refute OSR as a realism claim. A statistical difference is not a philosophical conclusion |
| Ziran System | A limited, quoted instance of MO/DO/ZCA/MS over a body model (XB-14) | Not an implementation of the Ziran System; MO/MS remain unimplemented |
| Xenoscience | A worked example of treating a design principle (Xeno-14) as a hypothesis with possible non-effect or reversal | No Xenoscience claim is tested |
| XenoBody | The planar body is a simplified Xeno-Body prototype (the same caution is stated in `ziran-xeno-simulator/embodied/README.md`) | Not the full Xeno-Body; no real robot |
| XenoSNN | **No connection.** There is no spiking component in XB-TRO | — |

### XB-17 — Real-world validity *(NOT claimed)*

No record supports a statement about a real human body, a real robot, or any hardware. No iOS device was available; iOS behaviour is excluded from every guarantee.

## 2. Open issues that bear on the ledger

1. **Hierarchy platform dependence (not XB-TRO).** `test_compat…[desktop-scipy]` fails; cause of the *mechanism* established (repeated eigenvalue on disconnected sub-graphs; `diagnosis/test_compat/`). It affects the Ziran runtime scenarios' hierarchies, not the XB-TRO experiment records.
2. **Seed budget.** All studies have 8–16 independent seeds; none approaches 10,000 trials. Any statement stronger than "in this planar simulator, with these seeds" is outside the evidence.
3. **Variant sensitivity.** XB-09 and the band sensitivity in XB-05/XB-10 show that several labels depend on analysis choices.
4. **Exploration results are not stored** (seeds 1000..1031), so the path from exploration to the final design cannot be audited from files.
5. **Records were produced before commit `1c5c155`**; re-execution at the current commit is recorded in §3.

## 3. Re-execution evidence (2026-10-20, ARDS replay workflow)

**Method.** Each stored record was re-executed on the real backend (`xzr.xbtro.experiments.run_to_end` with the record's own `rerun` field, same seeds), in the worktree at commit
`9e1aaf8` (clean), with Python 3.12.13 / numpy 2.5.3 — the environment recorded in the records — and compared value by value with the stored record (relative tolerance 1e-6, the
project's rule; the environment record `/provenance` is not compared). The comparison was recomputed by independently written code and the whole run is stored
(`pa-simulation-environment/artifacts/ards/phase2/`, generated `SUMMARY.md` and machine-readable `claim-evidence-map.json`). **This tests that the stored result can be obtained again
from the same code and seeds. It does not test that the result is correct or general.**

| stored record | seeds | values compared | reproduced | wall | peak memory |
|---|---|---|---|---|---|
| A_standard | 12 | 4,348 | exact (also exact under Python 3.14.7 / numpy 2.5.4, and in a second run) | 1.9 s | 66 MiB |
| B_standard | 12 | 4,822 | within rounding: 4,818 identical, 4 differ by at most 2.0e-10 relative; the project digest is equal | 15.0 s | 170 MiB |
| C_standard | 12 | 6,246 | exact | 16.8 s | 197 MiB |
| D_standard | 12 | 3,927 | exact | 6.7 s | 99 MiB |
| E_standard | 12 | 1,860 | exact | 4.8 s | 75 MiB |
| F_standard | 12 | 1,877 | exact | 15.3 s | 110 MiB |
| G_original_conditions | 8 | 1,910 | exact | 27.4 s | 84 MiB |
| G_standard | 12 | 4,571 | exact | 91.6 s | 100 MiB |
| G_independent_replication | 16 | 4,584 | exact | 93.7 s | 139 MiB |
| M_standard | 12 | 1,215 | exact | 8.4 s | 75 MiB |
| R_standard | 12 | 1,976 | exact | 78.4 s | 184 MiB |
| S_standard | 12 | 829 | exact | 12.6 s | 109 MiB |
| V_standard | 12 | 1,201 | exact | 66.0 s | 149 MiB |

Consequences for the claims: for **XB-01, 02, 04–12** (all rows that rest on these records) the records are *reproducible on the same code and seeds*; the claim-evidence map lists
`all-records-reproduced` for each. The qualifiers of each row stand unchanged (small seed counts, planar model, band sensitivity, variant sensitivity).
`B_band_13mm` and `D_band_13mm` were **not replayed**: the 13 mm band is set outside the record's `rerun` field (the final-run script patches `metrics.TOLERANCE`), so a replay from the record would not
reproduce that setting; those two records are not claimed as reproduced. XB-03, 13, 14, 15 rest on source and tests, not on experiment records.

**Not part of XB-TRO, recorded here because the same machinery found it.** The Ziran runtime was re-executed the same way: its conformance snapshot of `small-600` reproduces every dynamics
fingerprint but not the hierarchy digest (and 2 observation metrics, 3rd–4th digit); its reasoning-layer suite (`reason.json`) is **not reproduced** by default (1,326 of 3,971 values differ) and
is nearly reproduced (52 of 3,909 differ, all in `scenarios` / `phases`) when the stored reference hierarchy is forced. This is the hierarchy sensitivity documented in `diagnosis/test_compat/`; it does not touch any XB-TRO record.
