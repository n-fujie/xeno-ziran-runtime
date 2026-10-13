# HPO results (generated from backend/experiments/results/hpo/*.json by backend/scripts/hpo_report.py)

Proxies of philosophical operations inside one simulated runtime; every statement below is about this simulation under the stated configuration and is not evidence about a philosophical doctrine.

Protocol SHA-256 `71e589c7d88cdb1119810579121e65a89c4557b98856c66fd047d6c031f67685` (pinned `71e589c7d88cdb1119810579121e65a89c4557b98856c66fd047d6c031f67685`), commit `6804327a49569e3eeea6adb65abacd58ea8280c0` (uncommitted changes).

## HPO-002 — Cross-Operational Transformation

360 seeds × 29 contrasts = **10,440 paired comparisons**; world n = 800 (intermittent), 240 steps; elapsed 1943 s.

False-positive control (C~ vs C): 0 of 61 measures DETECTED (0.0 %) — valid (≤ 5 %).

| hypothesis | verdict | detail |
|---|---|---|
| H1 mutual transformation (C vs B) | **SUPPORTED IN THIS PROXY** | world: field_ignitions, memory_mean; operations: ignitions, fired_samples, reignitions, unobservable_samples, first_ignition_mean, ceased_share, op_states_visited |
| H2 historical reinsertion (D vs C) | **NOT SUPPORTED** | 27.3 reinsertions per run; downstream: none |
| H3 cessation of withdrawal (E vs C) | CONSEQUENCES DETECTED | ignitions, reignitions, unobservable_samples, first_ignition_mean, op_states_visited |
| H3 cessation of transduction (E vs C) | CONSEQUENCES DETECTED | ignitions, fired_samples, cessations, reignitions, unobservable_samples, ops_final, first_ignition_mean, op_states_visited, transformations, conflicts |
| H3 cessation of concrescence (E vs C) | CONSEQUENCES DETECTED | fired_samples |
| H3 cessation of picturing (E vs C) | CONSEQUENCES DETECTED | fired_samples, transformations |
| H3 cessation of assemblage (E vs C) | CONSEQUENCES DETECTED | ignitions, cessations, reignitions, first_ignition_mean, op_states_visited |
| H3 cessation of closure (E vs C) | CONSEQUENCES DETECTED | field_ignitions, memory_mean, ceased_share, filtered |
| H4 re-ignition of withdrawal (F vs E) | RE-IGNITION UNDER CHANGED CONFIGURATION DETECTED | re-ignitions F 0.436 vs E 0.169 (DETECTED) |
| H4 re-ignition of transduction (F vs E) | RE-IGNITION UNDER CHANGED CONFIGURATION DETECTED | re-ignitions F 0.883 vs E 0.289 (DETECTED) |
| H4 re-ignition of concrescence (F vs E) | RE-IGNITION UNDER CHANGED CONFIGURATION DETECTED | re-ignitions F 0.417 vs E 0.214 (DETECTED) |
| H4 re-ignition of picturing (F vs E) | RE-IGNITION UNDER CHANGED CONFIGURATION DETECTED | re-ignitions F 0.275 vs E 0.0917 (DETECTED) |
| H4 re-ignition of assemblage (F vs E) | RE-IGNITION UNDER CHANGED CONFIGURATION DETECTED | re-ignitions F 0.431 vs E 0.189 (DETECTED) |
| H4 re-ignition of closure (F vs E) | RE-IGNITION UNDER CHANGED CONFIGURATION DETECTED | re-ignitions F 0.664 vs E 0.192 (DETECTED) |
| H5 ablation −transform (G vs D) | CONTRIBUTES | field_ignitions, memory_mean, ignitions, fired_samples, unobservable_samples, first_ignition_mean, ceased_share, op_states_visited, transformations, conflicts, couplings, reinsertions, revisions, param_drift |
| H5 ablation −observation_change (G vs D) | CONTRIBUTES | field_ignitions, memory_mean, fired_samples, unobservable_samples, ops_final, first_ignition_mean, op_states_visited, transformations, filtered, conflicts, couplings, splits, reinsertions, revisions |
| H5 ablation −competition_adapt (G vs D) | CONTRIBUTES | transformations |
| H5 ablation −partition (G vs D) | CONTRIBUTES | field_ignitions, reignitions, unobservable_samples, ops_final, ceased_share, op_states_visited, transformations, filtered, couplings, splits, reinsertions |
| H5 ablation −reclassify (G vs D) | NO DETECTED CONTRIBUTION | — |
| H5 ablation −action_filter (G vs D) | CONTRIBUTES | field_ignitions, memory_mean, filtered, conflicts |
| H5 ablation −share_info (G vs D) | CONTRIBUTES | fired_samples, reignitions, unobservable_samples, ops_final, first_ignition_mean, op_states_visited, transformations, filtered, conflicts, couplings, splits, reinsertions, revisions, param_drift |
| H5 ablation −share_resources (G vs D) | NO DETECTED CONTRIBUTION | — |
| H5 ablation −share_history (G vs D) | CONTRIBUTES | revisions |
| H5 ablation −feedback (G vs D) | CONTRIBUTES | fired_samples, reinsertions |
| H6 real effects A vs R0 | DETECTED | field_ignitions |
| H6 real effects C vs R0 | none detected | — |

### Means per run (A independent · B coupled · C mutual transformation · D + reinsertion)

| measure | A | B | C | D |
|---|---|---|---|---|
| transformations | 0 | 0 | 310 | 315 |
| ignitions | 10.3 | 10.2 | 8.75 | 8.67 |
| fired_samples | 139 | 170 | 202 | 194 |
| cessations | 7.22 | 8.07 | 7.44 | 7.32 |
| reignitions | 5.43 | 5.47 | 3.54 | 3.53 |
| unobservable_samples | 9.91 | 2.37 | 223 | 217 |
| couplings | 0 | 0 | 3.06 | 2.96 |
| splits | 0 | 1.9 | 4.87 | 4.54 |
| filtered | 0 | 0 | 104 | 96.7 |
| conflicts | 0.925 | 5.41 | 28.9 | 26.5 |
| reinsertions | 0 | 0 | 0 | 27.3 |
| field_ignitions | 5956 | 6299 | 6096 | 6078 |
| memory_mean | 0.396 | 0.433 | 0.393 | 0.403 |
| alive_connections | 4376 | 4386 | 4375 | 4376 |
| gate_mean | 0.999 | 0.998 | 0.995 | 0.998 |
| reachable_share | 1 | 1 | 1 | 1 |
| reach_from_regions | 0.635 | 0.634 | 0.632 | 0.63 |
| ops_final | 6 | 7.9 | 7.81 | 7.58 |

### C vs B (DETECTED measures)

| measure | status | Δ mean | relative | d_z | p (Holm) | n |
|---|---|---|---|---|---|---|
| ignitions | DETECTED | -1.47 | -14.4% | -0.35 | 0.003 | 360 |
| fired_samples | DETECTED | 32.3 | +16.0% | 0.27 | 0.003 | 360 |
| first_ignition_mean | DETECTED | -9.77 | -11.8% | -0.36 | 0.003 | 360 |
| never_ignited | DETECTED | -0.464 | -36.9% | -0.52 | 0.003 | 360 |
| transformations | DETECTED | 310 | +100.0% | 1.4 | 0.003 | 360 |
| filtered | DETECTED | 104 | +100.0% | 0.35 | 0.003 | 360 |
| conflicts | DETECTED | 23.5 | +81.3% | 0.39 | 0.003 | 360 |
| couplings | DETECTED | 3.06 | +100.0% | 2.4 | 0.003 | 360 |
| splits | DETECTED | 2.97 | +60.9% | 0.59 | 0.003 | 360 |
| revisions | DETECTED | 1.26 | +75.7% | 1.4 | 0.003 | 360 |
| feedback | DETECTED | -9.89 | -16.7% | -0.22 | 0.003 | 360 |
| param_drift | DETECTED | 0.0647 | +47.4% | 0.95 | 0.003 | 360 |
| op_states_visited | DETECTED | 7.8 | +35.9% | 1.9 | 0.003 | 360 |
| kinds_seen | DETECTED | 3.17 | +34.6% | 1.9 | 0.003 | 360 |
| ceased_share | DETECTED | 0.0759 | +28.9% | 0.57 | 0.003 | 360 |
| reignitions | DETECTED | -1.93 | -35.3% | -0.49 | 0.003 | 360 |
| reignite_latency | DETECTED | 7.14 | +18.9% | 0.24 | 0.003 | 299 |
| applied_records | DETECTED | -4099 | -30.7% | -0.34 | 0.003 | 360 |
| suppressed | DETECTED | 16.9 | +56.8% | 0.19 | 0.0031 | 360 |
| unobservable_samples | DETECTED | 221 | +98.9% | 1 | 0.003 | 360 |
| shared_fills | DETECTED | 21397 | +84.1% | 0.41 | 0.003 | 360 |
| cross_links | DETECTED | 542 | +96.5% | 0.66 | 0.003 | 360 |
| causal_depth | DETECTED | 35.9 | +93.3% | 0.67 | 0.003 | 360 |
| sources_on_path | DETECTED | 20.9 | +94.2% | 0.7 | 0.003 | 360 |
| field_ignitions | DETECTED | -203 | -3.2% | -0.23 | 0.0031 | 360 |
| memory_mean | DETECTED | -0.04 | -9.3% | -0.42 | 0.003 | 360 |
| unobs:scale_mismatch | DETECTED | 38.7 | +100.0% | 0.65 | 0.003 | 360 |
| unobs:boundary_invisible | DETECTED | 223 | +100.0% | 1.6 | 0.003 | 360 |
| unobs:unmeasured | DETECTED | 51.2 | +40.1% | 0.19 | 0.0038 | 360 |
| ignitions:withdrawal | DETECTED | -0.214 | -23.8% | -0.48 | 0.003 | 360 |
| reignitions:withdrawal | DETECTED | -1.26 | -61.2% | -0.56 | 0.003 | 360 |
| cessations:withdrawal | DETECTED | -1.14 | -47.6% | -0.49 | 0.003 | 360 |
| ignitions:transduction | DETECTED | 0.139 | +17.1% | 0.34 | 0.003 | 360 |
| ignitions:concrescence | DETECTED | 0.0583 | +6.6% | 0.2 | 0.0063 | 360 |
| reignitions:concrescence | DETECTED | -0.436 | -62.3% | -0.38 | 0.003 | 360 |
| cessations:concrescence | DETECTED | -0.492 | -56.7% | -0.42 | 0.003 | 360 |
| ignitions:picturing | DETECTED | 0.508 | +51.1% | 1 | 0.003 | 360 |
| reignitions:picturing | DETECTED | 0.164 | +100.0% | 0.44 | 0.003 | 360 |
| cessations:picturing | DETECTED | 0.328 | +100.0% | 0.65 | 0.003 | 360 |
| reignitions:assemblage | DETECTED | -0.294 | -31.6% | -0.24 | 0.003 | 360 |
| cessations:assemblage | DETECTED | 0.731 | +37.0% | 0.3 | 0.003 | 360 |
| picturing_error | DETECTED | -0.104 | -14.2% | -0.46 | 0.003 | 360 |

### D vs C (DETECTED measures)

| measure | status | Δ mean | relative | d_z | p (Holm) | n |
|---|---|---|---|---|---|---|
| revisions | DETECTED | -0.175 | -10.6% | -0.29 | 0.003 | 360 |
| param_drift | DETECTED | -0.0372 | -27.3% | -0.69 | 0.003 | 360 |
| reinsertions | DETECTED | 27.3 | +100.0% | 4.2 | 0.003 | 360 |
| retransform_latency | DETECTED | -1.02 | -24.4% | -0.19 | 0.003 | 360 |
| ignitions:transduction | DETECTED | -0.0667 | -8.2% | -0.26 | 0.003 | 360 |
| picturing_error | DETECTED | 0.0212 | +3.2% | 0.26 | 0.003 | 360 |

### B vs A (DETECTED measures)

| measure | status | Δ mean | relative | d_z | p (Holm) | n |
|---|---|---|---|---|---|---|
| fired_samples | DETECTED | 30.2 | +17.8% | 0.53 | 0.003 | 360 |
| first_ignition_mean | DETECTED | 2.2 | +2.7% | 0.21 | 0.0037 | 360 |
| never_ignited | DETECTED | 0.0917 | +7.3% | 0.21 | 0.003 | 360 |
| splits | DETECTED | 1.9 | +100.0% | 0.53 | 0.003 | 360 |
| feedback | DETECTED | 12.4 | +20.9% | 0.57 | 0.003 | 360 |
| ops_final | DETECTED | 1.9 | +24.1% | 0.53 | 0.003 | 360 |
| cessations | DETECTED | 0.85 | +10.5% | 0.24 | 0.003 | 360 |
| ceased_share | DETECTED | -0.0156 | -7.7% | -0.21 | 0.0037 | 360 |
| applied_records | DETECTED | 3052 | +22.8% | 0.51 | 0.003 | 360 |
| field_ignitions | DETECTED | 343 | +5.4% | 0.47 | 0.003 | 360 |
| memory_mean | DETECTED | 0.0366 | +8.5% | 0.47 | 0.003 | 360 |
| unobs:unmeasured | DETECTED | 66.5 | +87.0% | 0.31 | 0.003 | 360 |
| cessations:transduction | DETECTED | 1.32 | +54.4% | 0.4 | 0.003 | 360 |
| ignitions:concrescence | DETECTED | -0.05 | -5.7% | -0.22 | 0.003 | 360 |
| cessations:concrescence | DETECTED | 0.0889 | +10.3% | 0.21 | 0.0052 | 360 |
| ignitions:picturing | DETECTED | -0.0528 | -9.8% | -0.21 | 0.003 | 360 |
| cessations:picturing | DETECTED | -0.119 | -100.0% | -0.37 | 0.003 | 360 |

### C vs R0 (DETECTED measures)

| measure | status | Δ mean | relative | d_z | p (Holm) | n |
|---|---|---|---|---|---|---|

Divergence from the matched no-HPO branch R0 (same exogenous input): share of connections differing at the end, and first step at which the endogenous stream diverged (intervention-branched continuation):

| condition | connections differing | memory |Δ| | bit-identical share | endogenous divergence step |
|---|---|---|---|---|
| A | 0.292 | 0.217 | 0 | 42.4 |
| B | 0.3 | 0.229 | 0 | 41.8 |
| C | 0.298 | 0.21 | 0 | 41.1 |
| C~ | 0.315 | 0.228 | 0 | 1 |
| D | 0.297 | 0.216 | 0 | 41.1 |

## Generalization (settings not used in development)

64 seeds per setting; 1,920 paired comparisons.

| setting | H1 world | H1 operations | H2 downstream | noise detected |
|---|---|---|---|---|
| sparse | memory_mean | ignitions, fired_samples, cessations, reignitions, unobservable_samples, ops_final, op_states_visited | none | 0.0 % |
| churn | none | fired_samples, reignitions, unobservable_samples, op_states_visited | none | 0.0 % |
| memory_heavy | none | ignitions, fired_samples, cessations, reignitions, unobservable_samples, op_states_visited | none | 0.0 % |
| n1200 | memory_mean | unobservable_samples, ops_final, ceased_share, op_states_visited | none | 0.0 % |
| separate | none | unobservable_samples, first_ignition_mean, op_states_visited | none | 0.0 % |
| boundary | none | ignitions, fired_samples, cessations, reignitions, unobservable_samples, first_ignition_mean, op_states_visited | none | 0.0 % |

H1 (world and operation downstream) in 2 of 6 settings; H2 in 0 of 6 (protocol: 'generalizes' needs ≥ half).

## HPO-001 (re-specified)

Pilot: not available in the implementation environment (searched the machine); no pilot code or result was inherited, reconstructed or estimated.

* operations receive instrument observations only; the world's true state is read by the harness (oracle access exists only as the explicit truth-leak control)
* exogenous input comes from its own stream, identical in every paired branch; the endogenous stream is tracked and its first divergence from the no-HPO branch is reported (intervention-branched continuation) separately from the exogenously matched comparison
* prediction error (picturing) is reported as a property of the proxy under this configuration, never as a ranking of philosophical theories

No metric here ranks the philosophical series against one another; the series do different things and their proxies are not commensurable as theories.

| kind | truth leak: DETECTED measures (oracle vs instrument) | endogenous divergence step | connections differing vs R0 (noise R0~: …) |
|---|---|---|---|
| withdrawal | none | 103 | 0.224 (noise 0.306) |
| transduction | fired_samples, applied_records | 134 | 0.175 (noise 0.306) |
| concrescence | none | 98.9 | 0.214 (noise 0.306) |
| picturing | none | 191 | 0.0723 (noise 0.306) |
| assemblage | none | 81.5 | 0.243 (noise 0.306) |
| closure | none | 121 | 0.185 (noise 0.306) |

## HPO-003 — Recursive Reconfiguration of Ziran System

96 seeds, epochs of 60 steps, base condition D. Reproducible trace: **True**. Rejected changes: 0. Sandbox paths: allocation.*, catalog, couplable, history.every, history.lag, history.reinsert, instruments.*.channels, instruments.*.level, instruments.*.penetration, instruments.*.period, instruments.*.window, order, resources.pool_per_step, stop.all_ceased, variables.

Changed settings (all seeds): instruments.*.period ×274, allocation.* ×203, instruments.*.penetration ×201, order ×174, couplable ×152, variables ×60, instruments.*.level ×54, history.lag ×29.

| proposed variable | status | seeds | rationale |
|---|---|---|---|
| veil_coverage | proposed (no implementation; untestable here) | 88 | operations repeatedly blinded by veils: a variable for how much of the field is veiled could anticipate blindness |
| activity_trend | not validated (held-out seeds) | 60 | picturing error stays above tolerance after revising categories: the error may come from change over time that a level picture cannot carry |
| conflict_density | proposed (no implementation; untestable here) | 38 | frequent opposite threshold factors on shared configurations |

Validation of activity_trend on 64 held-out seeds (picturing_error DETECTED and lower with the variable than without, on held-out seeds):

| measure | status | Δ mean | relative | d_z | p (Holm) | n |
|---|---|---|---|---|---|---|
| picturing_error | DETECTED | 0.263 | +30.1% | 0.8 | 0.00025 | 64 |
| revisions | DETECTED | 0.359 | +20.7% | 0.41 | 0.0096 | 64 |
| fired_samples | UNRESOLVED | 35.2 | +15.3% | 0.29 | 0.04 | 64 |
| ignitions | UNRESOLVED | -0.0938 | -1.0% | -0.029 | 0.85 | 64 |
| field_ignitions | EQUIVALENT | -90.4 | -1.4% | -0.12 | 0.71 | 64 |

Result-driven beyond change as such (DETECTED in both recursive vs static and recursive vs random): ignitions, fired_samples, transformations, filtered, feedback, reignitions, retransform_latency, applied_records, suppressed, shared_fills, cross_links, unobs:boundary_invisible, unobs:unmeasured, reignitions:withdrawal, reignitions:assemblage, cessations:assemblage.

### recursive vs static (DETECTED measures)

| measure | status | Δ mean | relative | d_z | p (Holm) | n |
|---|---|---|---|---|---|---|
| ignitions | DETECTED | 1.89 | +17.3% | 0.59 | 0.0031 | 96 |
| fired_samples | DETECTED | 147 | +42.3% | 1.1 | 0.0031 | 96 |
| first_ignition_mean | DETECTED | -5.52 | -7.8% | -0.45 | 0.0031 | 96 |
| transformations | DETECTED | 123 | +28.7% | 0.44 | 0.0031 | 96 |
| filtered | DETECTED | 375 | +79.4% | 0.38 | 0.0031 | 96 |
| couplings | DETECTED | 0.75 | +20.2% | 0.56 | 0.0031 | 96 |
| feedback | DETECTED | 55.2 | +52.2% | 0.94 | 0.0031 | 96 |
| op_states_visited | DETECTED | 2.36 | +9.9% | 0.65 | 0.0031 | 96 |
| kinds_seen | DETECTED | 1.14 | +11.4% | 0.68 | 0.0031 | 96 |
| reignitions | DETECTED | 1.64 | +29.6% | 0.53 | 0.0031 | 96 |
| reinsertions | DETECTED | -4.14 | -15.1% | -0.67 | 0.0031 | 96 |
| retransform_latency | DETECTED | -0.979 | -32.9% | -0.95 | 0.0031 | 96 |
| applied_records | DETECTED | 22475 | +71.3% | 0.62 | 0.0031 | 96 |
| suppressed | DETECTED | 158 | +87.6% | 0.43 | 0.0031 | 96 |
| shared_fills | DETECTED | 83402 | +75.8% | 0.97 | 0.0031 | 96 |
| cross_links | DETECTED | 556 | +49.7% | 0.51 | 0.0031 | 96 |
| field_ignitions | DETECTED | 285 | +4.6% | 0.38 | 0.0076 | 96 |
| memory_mean | DETECTED | 0.0386 | +8.9% | 0.42 | 0.0031 | 96 |
| unobs:boundary_invisible | DETECTED | -96.1 | -40.0% | -0.73 | 0.0031 | 96 |
| unobs:unmeasured | DETECTED | 220 | +57.5% | 0.49 | 0.0031 | 96 |
| reignitions:withdrawal | DETECTED | 0.615 | +37.8% | 0.38 | 0.0076 | 96 |
| reignitions:assemblage | DETECTED | 1.11 | +59.8% | 0.56 | 0.0031 | 96 |
| cessations:assemblage | DETECTED | 1.18 | +38.4% | 0.44 | 0.0031 | 96 |
| picturing_error | DETECTED | 0.1 | +13.4% | 0.5 | 0.0031 | 96 |
| reconfigurations | DETECTED | 11.9 | +100.0% | 2.6 | 0.0031 | 96 |

### random vs static (DETECTED measures)

| measure | status | Δ mean | relative | d_z | p (Holm) | n |
|---|---|---|---|---|---|---|
| kinds_seen | DETECTED | 0.552 | +5.9% | 0.41 | 0.0088 | 96 |
| reinsertions | DETECTED | -6.69 | -24.4% | -0.84 | 0.0031 | 96 |
| unobs:scale_mismatch | DETECTED | 131 | +80.0% | 0.34 | 0.0031 | 96 |
| reconfigurations | DETECTED | 11.9 | +100.0% | 2.6 | 0.0031 | 96 |

### recursive vs random (DETECTED measures)

| measure | status | Δ mean | relative | d_z | p (Holm) | n |
|---|---|---|---|---|---|---|
| ignitions | DETECTED | 2.09 | +19.2% | 0.63 | 0.0031 | 96 |
| fired_samples | DETECTED | 143 | +41.2% | 1 | 0.0031 | 96 |
| transformations | DETECTED | 122 | +28.4% | 0.48 | 0.0031 | 96 |
| filtered | DETECTED | 341 | +72.3% | 0.34 | 0.0031 | 96 |
| feedback | DETECTED | 49.1 | +46.5% | 0.76 | 0.0031 | 96 |
| param_drift | DETECTED | -0.0274 | -23.4% | -0.39 | 0.0084 | 96 |
| cessations | DETECTED | 2.07 | +22.5% | 0.41 | 0.0031 | 96 |
| reignitions | DETECTED | 1.8 | +32.6% | 0.55 | 0.0031 | 96 |
| retransform_latency | DETECTED | -1.07 | -34.9% | -0.81 | 0.0031 | 96 |
| applied_records | DETECTED | 19384 | +61.5% | 0.52 | 0.0031 | 96 |
| suppressed | DETECTED | 170 | +94.2% | 0.46 | 0.0031 | 96 |
| shared_fills | DETECTED | 80003 | +72.7% | 0.77 | 0.0031 | 96 |
| cross_links | DETECTED | 503 | +45.0% | 0.42 | 0.0031 | 96 |
| unobs:scale_mismatch | DETECTED | -127 | -77.8% | -0.33 | 0.0031 | 96 |
| unobs:boundary_invisible | DETECTED | -59.7 | -29.3% | -0.43 | 0.0031 | 96 |
| unobs:unmeasured | DETECTED | 310 | +80.9% | 0.47 | 0.0031 | 96 |
| ignitions:withdrawal | DETECTED | 0.167 | +18.6% | 0.44 | 0.0066 | 96 |
| reignitions:withdrawal | DETECTED | 0.719 | +44.2% | 0.41 | 0.0045 | 96 |
| reignitions:assemblage | DETECTED | 1.02 | +54.7% | 0.53 | 0.0031 | 96 |
| cessations:assemblage | DETECTED | 1.06 | +34.7% | 0.43 | 0.0031 | 96 |

## Result classes

| class | what | where |
|---|---|---|
| development | threshold calibration on development seeds (gen 0–7 / engine 1000–1007; gen 3 / 101–103) | `results/hpo/history/calibration-development-seeds.txt` |
| smoke / pilot | pipeline checks and the 200-job robustness sweep on the smoke ranges | `results/hpo/history/robustness_sweep.txt` |
| confirmatory | HPO-001, HPO-002, HPO-003 under the frozen protocol | `hpo001.json`, `hpo002.json`, `hpo003.json` |
| generalization | six settings not used in development (pre-registered) | `general.json` |
| post-hoc descriptive | substantive questions Q1–Q9 on 48 confirmatory seeds re-run deterministically; not pre-registered, tests nothing | `substantive.json` |

## Protocol history

* Frozen at `37c8b0a3ee7f…` (text kept as `results/hpo/history/HPO_PROTOCOL.37c8b0a3ee7f.md`). The first confirmatory HPO-002 run failed with `IndexError` in `field._read_archive` (log with traceback: `results/hpo/history/confirmatory-run-1-failed.log`). No result was written.
* Amendment 1 (defect fix only; hypotheses, thresholds, measures and conditions unchanged), robustness sweep, re-frozen at `71e589c7d88c…`. Every confirmatory run was repeated (`confirmatory-run-2.log`).

## HPO-003: proposed, accepted, executed, validated

* configuration changes proposed by the controller: 1147 (all 96 seeds)
* accepted by the sandbox: 1147 (rejected 0)
* executed in the running experiment: 1147
* consequences validated: the measures DETECTED in both recursive vs static and recursive vs random (above); new variables validated: none (activity_trend failed its held-out criterion; veil_coverage and conflict_density have no implementation and were not testable)
* all of this is reconfiguration of simulated experiment settings: no physical or institutional effect was produced or verified

## Substantive operational differences (post-hoc, descriptive)

48 confirmatory HPO-002 seeds re-run deterministically with full state recording; the re-run reproduces the stored confirmatory causal trace: **True**. Counts are per run. Nothing here is a hypothesis test.

**Q1 Which ignition conditions changed (C)?**

| parameter | runs | changes per run | mean relative change |
|---|---|---|---|
| picturing.ign.tolerance | 48/48 | 16 | -8.4% |
| withdrawal.ign.threshold | 48/48 | 28.7 | +2.9% |
| transduction.rule.factor | 48/48 | 118 | +0.4% |
| closure.ign.threshold | 47/48 | 23 | -8.0% |
| assemblage.ign.threshold | 44/48 | 14 | -9.5% |
| transduction.ign.threshold | 43/48 | 17.2 | -7.7% |
| withdrawal.instrument.level | 42/48 | 0.875 | +100.0% |
| assemblage.rule.links | 35/48 | 4.06 | -24.3% |
| picturing.rule.damp | 34/48 | 8.96 | -0.5% |
| assemblage.instrument.level | 31/48 | 0.646 | +100.0% |
| closure.instrument.level | 31/48 | 0.646 | +100.0% |
| concrescence.instrument.level | 21/48 | 0.438 | +100.0% |
| closure.rule.adapt | 20/48 | 1.96 | +0.0% |
| concrescence∘assemblage.instrument.level | 4/48 | 0.0833 | +100.0% |

**Q2 Which series caused them (source → target, per run, C)?** picturing → transduction 60.3; competition → transduction 43.8; concrescence → transduction 15.5; concrescence → withdrawal 15.5; assemblage → transduction 14.6; closure → withdrawal 13.2; concrescence → closure 10.9; assemblage → withdrawal 9.71; assemblage → closure 8.67; assemblage → picturing 8.58; concrescence → assemblage 8.58; assemblage → concrescence 5.77.

**Q3 Which operations became possible or impossible (C vs B, share of seeds)?** withdrawal: enabled +2.1%, disabled +27.1%; transduction: enabled +8.3%, disabled +4.2%; concrescence: enabled +10.4%, disabled +0.0%; picturing: enabled +47.9%, disabled +0.0%; assemblage: enabled +6.2%, disabled +6.2%; closure: enabled +2.1%, disabled +4.2%. Reachability measures (C vs B): reach_from_regions EQUIVALENT, reachable_share IDENTICAL, op_states_visited DETECTED.

**Q4 Which changes persisted?** Share of operation parameters still ≠ initial at the end of the run: C +22.4%, B +16.4% (B has no cross-operational transformation; its changes come from each operation's own feedback).

**Q5 What disappeared after removing the initiating series (E:k vs C)?** Transformations sourced by k after the removal step (per run), share of E runs in which k still ignited, mean parameter drift of the remaining operations:

| k | by k after step 80: C → E | k ignited in E | drift C → E |
|---|---|---|---|
| withdrawal | 2.85 → 0.25 | +35.4% | 0.141 → 0.138 |
| transduction | 12.7 → 5.04 | +75.0% | 0.141 → 0.144 |
| concrescence | 36.9 → 33.1 | +91.7% | 0.141 → 0.142 |
| picturing | 58.7 → 45 | +100.0% | 0.141 → 0.136 |
| assemblage | 23.2 → 4.75 | +75.0% | 0.141 → 0.15 |
| closure | 9.4 → 0.833 | +83.3% | 0.141 → 0.114 |

Removing withdrawal, closure or assemblage removes most of their downstream transformations. Removing the activity channel of picturing or concrescence barely does: other operations' observations fill the missing channel (`share_info`), so these series keep igniting — the removal is compensated by information sharing.

**Q6 Which historical differences were reintroduced (D)?** ignition parameters of an earlier configuration: 16.4 per run, +33.1% caused a later event; archived veil: 1.46 per run, +72.9% caused a later event; archived datum: 9.56 per run, +77.1% caused a later event; archived datum re-seeds the milieu: 1.12 per run, +0.0% caused a later event. They re-enter and are acted on, but no downstream difference D vs C was detected (H2).

**Q7 Did the operational configuration change?** C: 3.1 couplings and 4.56 splits per run, 19 distinct composite kinds across runs (most frequent: concrescence∘picturing 36, concrescence∘assemblage 21, transduction∘closure 19, concrescence∘picturing∘assemblage 19); B: no couplings, 1.88 splits (transduction's own). Reclassification never occurred (0 per run).

**Q8 Did the system modify its own subsequent execution conditions?** Yes, in HPO-003, within the sandbox (see above).

**Q9 What remained unobserved?** Unobservable channel-samples per run, C: withdrawal boundary_invisible 54.6; transduction boundary_invisible 95.8, unmeasured 59.5, scale_mismatch 3.85; assemblage boundary_invisible 54.6, unmeasured 30.8, scale_mismatch 29.4; closure boundary_invisible 41.6, unmeasured 60.7, scale_mismatch 6.08; concrescence boundary_invisible 17.2, scale_mismatch 6.6, unmeasured 0.438; picturing boundary_invisible 17.9, scale_mismatch 11, unmeasured 2.48. In B only `unmeasured` occurs. UNRESOLVED statuses in the confirmatory contrasts: 616 of 1657 measure-contrast cells.

**Q10 Which findings contradict the initial hypotheses?**

* H2 (history reinsertion has downstream effects): not supported at 360 seeds and in all six generalization settings.
* H1 does not generalize by the protocol's rule (world and operation effects together in 2 of 6 settings); the operation-level part alone appears in all 6.
* C vs R0 shows no detected world effect while A vs R0 does (field ignitions): mutual transformation attenuates the operations' net world effect rather than adding to it.
* `reclassify` and `share_resources` show no detected contribution; reclassification never fired.
* The proposed variable `activity_trend` made picturing error worse on held-out seeds (+30 %).
* Removing a series' essential channel is compensated for picturing and concrescence by information sharing (they keep igniting).

## Future research questions

1. Does history reinsertion become effective with other lags, selections (what re-enters) or larger deposits — and is H2's null result a property of the proxy or of the reinsertion rule?
2. Why does the world-level effect of H1 depend on regime and size (2 of 6 settings) while the operation-level effect is stable?
3. Is the attenuation of net world effects under mutual transformation (C vs R0 none, A vs R0 detected) robust, and which rules produce it?
4. A reclassification criterion that can fire, or evidence that partition change through coupling suffices.
5. Implementations for the proposed variables veil_coverage and conflict_density, then held-out tests.
6. Consulting the primary texts and revising each proxy's registry entry (and possibly its rule) against them; adding extension candidates only with consulted sources.
