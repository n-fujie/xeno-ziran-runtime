# Measured tables — stage `research`

Seeds: 30; severities: [0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0]; perturbation subtypes run: 47.

## Null check (unperturbed noise replicate vs control, leave-one-seed-out tolerance)

Per-seed labels: {'ACTIVE_INFERENCE_COMPATIBLE': 30}; mislabelled share 0.00; cell-level C_AIF 1.00 → ACTIVE_INFERENCE_COMPATIBLE.

Noise tolerance per raw quantity: {"acc": 0.66, "acc_adaptive": 0.46, "sensor": 0.028, "pc1": 0.252, "sep": 0.706, "bshare": 0.236}

## Cell-level regime by perturbation and severity (C_AIF; first unstable primitive)

| perturbation | side | sev 0.083 | sev 0.125 | sev 0.167 | sev 0.25 | sev 0.333 | sev 0.375 | sev 0.417 | sev 0.5 | sev 0.583 | sev 0.625 | sev 0.667 | sev 0.75 | sev 0.833 | sev 0.875 | sev 0.917 | sev 1 | transition kind |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| boundary.delayed_update | boundary |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 | compatible_throughout |
| boundary.disappearance | boundary |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.96 | AIF 0.95 | AIF 0.95 | AIF 0.93 | AIF 0.87 | compatible_throughout |
| boundary.fragmentation | boundary |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.98 |  | AIF 0.95 |  | AIF 0.95 | AIF 0.88 | AIF 0.88 | AIF 0.85 | AIF 0.83 | compatible_throughout |
| boundary.leakage | boundary |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 | AIF 0.99 | AIF 0.99 | AIF 0.99 | AIF 0.99 |  | AIF 0.98 |  | AIF 0.97 | compatible_throughout |
| boundary.merge | boundary | AIF 1.00 | AIF 0.99 | AIF 0.99 | AIF 0.99 |  | AIF 0.98 |  | AIF 0.98 |  | AIF 0.97 |  | AIF 0.98 |  | AIF 0.97 |  | AIF 0.98 | compatible_throughout |
| boundary.noise | boundary |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.98 |  | AIF 0.96 | compatible_throughout |
| boundary.reassignment | boundary | AIF 1.00 | AIF 1.00 | AIF 0.99 | AIF 0.98 |  | AIF 0.96 |  | AIF 0.91 |  | AIF 0.84 |  | AIF 0.81 | TRANS 0.77 (boundary) | TRANS 0.75 (boundary) | TRANS 0.75 (boundary) | POST 0.49 (policy) | graded |
| coupling.asymmetric | coupling |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 | compatible_throughout |
| coupling.cross_cluster | coupling |  | AIF 0.99 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 | compatible_throughout |
| coupling.reversal | coupling |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.97 |  | AIF 0.95 | AIF 0.95 | AIF 0.94 | AIF 0.93 | AIF 0.92 | compatible_throughout |
| coupling.strengthening | coupling |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.98 |  | AIF 0.98 | compatible_throughout |
| coupling.temporary_decoupling | coupling |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.97 |  | AIF 0.96 | compatible_throughout |
| coupling.weakening | coupling |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.96 | AIF 0.93 | AIF 0.89 | AIF 0.84 | AIF 0.81 |  | TRANS 0.79 (boundary) |  | TRANS 0.78 (boundary) | graded |
| memory.access_block | memory |  | AIF 0.99 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 1.00 | compatible_throughout |
| memory.deletion | memory |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 | compatible_throughout |
| memory.history_reactivation | memory |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 | compatible_throughout |
| memory.history_removal | memory |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 | compatible_throughout |
| memory.migration | memory |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 1.00 | compatible_throughout |
| memory.truncation | memory |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 1.00 | compatible_throughout |
| sensor.delay | sensor | TRANS 0.68 (sensor) | TRANS 0.51 (sensor) | TRANS 0.51 (sensor) | TRANS 0.51 (sensor) | POST 0.37 (sensor) | POST 0.37 (sensor) | POST 0.37 (sensor) | POST 0.23 (sensor) |  | POST 0.23 (sensor) |  | POST 0.09 (sensor) |  | POST 0.09 (sensor) |  | POST 0.20 (sensor) | graded |
| sensor.dropout | sensor |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 1.00 |  | AIF 0.98 |  | AIF 0.98 | AIF 0.91 | AIF 0.91 | POST 0.03 (sensor) | POST 0.03 (sensor) | abrupt |
| sensor.noise | sensor |  | AIF 0.99 |  | AIF 0.91 | AIF 0.85 | AIF 0.82 | TRANS 0.80 (sensor) | TRANS 0.73 (sensor) |  | TRANS 0.65 (sensor) |  | TRANS 0.57 (sensor) |  | POST 0.50 (sensor) |  | POST 0.46 (sensor) | graded |
| sensor.partial_observability | sensor |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.98 |  | AIF 0.98 |  | AIF 0.92 | compatible_throughout |
| sensor.permutation | sensor |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 | compatible_throughout |
| sensor.reassignment | sensor |  | AIF 0.99 |  | AIF 0.98 | AIF 0.98 | AIF 0.98 | AIF 0.88 | AIF 0.88 |  | TRANS 0.77 (sensor) |  | TRANS 0.77 (sensor) | TRANS 0.54 (sensor) | TRANS 0.54 (sensor) | POST 0.20 (sensor) | POST 0.20 (sensor) | graded |
| sensor.scale_mismatch | sensor |  | AIF 1.00 |  | AIF 0.99 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 1.00 |  | AIF 0.99 | compatible_throughout |
| sensor.window_mismatch | sensor |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.98 |  | AIF 0.92 |  | AIF 0.84 | AIF 0.84 | TRANS 0.73 (sensor) | TRANS 0.73 (sensor) | TRANS 0.59 (sensor) | graded |
| structural.cut_reconnect | structural |  | AIF 0.99 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.98 |  | AIF 0.98 |  | AIF 0.97 | AIF 0.96 | AIF 0.95 | AIF 0.94 | AIF 0.91 | compatible_throughout |
| structural.disconnection | structural |  | AIF 0.99 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.98 |  | AIF 0.97 |  | AIF 0.97 | AIF 0.96 | AIF 0.93 | AIF 0.95 | AIF 0.92 | compatible_throughout |
| structural.multi_cluster_reorganization | structural |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 | compatible_throughout |
| temporal.asynchronous | temporal |  | AIF 1.00 |  | AIF 0.98 |  | AIF 0.95 |  | AIF 0.89 | AIF 0.84 | AIF 0.80 | TRANS 0.75 (sensor) | TRANS 0.62 (sensor) | POST 0.49 (sensor) | POST 0.35 (sensor) | POST 0.30 (sensor) | POST 0.03 (sensor) | graded |
| temporal.horizon_compression | temporal |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 | compatible_throughout |
| temporal.horizon_expansion | temporal |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 | compatible_throughout |
| temporal.interface_drift | temporal | TRANS 0.65 (policy) | TRANS 0.65 (policy) | POST 0.32 (policy) | POST 0.32 (policy) |  | POST 0.33 (policy) |  | POST 0.00 (policy) |  | POST 0.35 (policy) |  | POST 0.33 (policy) |  | POST 0.32 (policy) |  | TRANS 0.65 (policy) | graded |
| temporal.world_drift | temporal |  | AIF 1.00 |  | AIF 0.99 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 | compatible_throughout |
| topology.cluster_merge | topology |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 | AIF 0.99 | AIF 0.99 | AIF 0.99 | AIF 0.98 |  | AIF 0.98 |  | AIF 0.97 | compatible_throughout |
| topology.cluster_split | topology |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 | compatible_throughout |
| topology.dynamic_mutation | topology |  | AIF 0.99 |  | AIF 0.98 |  | AIF 0.97 |  | AIF 0.97 |  | AIF 0.96 |  | AIF 0.96 |  | AIF 0.96 |  | AIF 0.97 | compatible_throughout |
| topology.edge_addition | topology |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 | compatible_throughout |
| topology.edge_deletion | topology |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.97 |  | AIF 0.97 |  | AIF 0.98 |  | AIF 0.97 | compatible_throughout |
| topology.hub_removal | topology |  | AIF 0.99 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.98 | compatible_throughout |
| topology.rerouting | topology |  | AIF 0.99 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.99 |  | AIF 0.97 | compatible_throughout |
| variable.deletion | variable |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 | AIF 1.00 | AIF 0.87 | TRANS 0.55 (sensor) | POST 0.03 (sensor) | graded |
| variable.duplication | variable |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.98 |  | AIF 0.98 |  | AIF 0.98 |  | AIF 0.97 | compatible_throughout |
| variable.outcome_merge | variable |  | AIF 1.00 |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.98 |  | AIF 0.97 |  | AIF 0.95 |  | AIF 0.94 | compatible_throughout |
| variable.relabel | variable |  | AIF 1.00 |  | AIF 1.00 |  | AIF 0.99 |  | AIF 0.96 |  | AIF 0.90 |  | AIF 0.88 | AIF 0.83 | AIF 0.80 | TRANS 0.79 (sensor) | TRANS 0.74 (sensor) | graded |
| variable.remap | variable |  | AIF 0.99 |  | AIF 1.00 | AIF 0.99 | AIF 1.00 | AIF 0.99 | AIF 0.99 |  | AIF 0.99 |  | AIF 0.98 |  | AIF 0.98 |  | AIF 0.98 | compatible_throughout |

Transition kinds: {'compatible_throughout': 36, 'graded': 10, 'abrupt': 1}

## Regime counts

Cell level: {'ACTIVE_INFERENCE_COMPATIBLE': 369, 'TRANSITION': 28, 'POST_ACTIVE_INFERENCE': 27}

Cell × seed level: {'ACTIVE_INFERENCE_COMPATIBLE': 10911, 'TRANSITION': 893, 'POST_ACTIVE_INFERENCE': 916}; threshold sensitivity (cell × seed): {'0.7/0.4': {'ACTIVE_INFERENCE_COMPATIBLE': 11315, 'POST_ACTIVE_INFERENCE': 766, 'TRANSITION': 639}, '0.9/0.6': {'ACTIVE_INFERENCE_COMPATIBLE': 10153, 'TRANSITION': 1475, 'POST_ACTIVE_INFERENCE': 1092}}

| family | AIF | TRANS | POST |
|---|---|---|---|
| boundary | 1809 | 194 | 37 |
| coupling | 1459 | 101 | 0 |
| memory | 1436 | 4 | 0 |
| sensor | 1518 | 330 | 492 |
| structural | 810 | 30 | 0 |
| temporal | 891 | 175 | 314 |
| topology | 1727 | 13 | 0 |
| variable | 1261 | 46 | 73 |

## First unstable primitive (lowest severity at which most seeds leave the compatible regime)

* **S_boundary**: boundary.reassignment, coupling.weakening
* **S_policy**: temporal.interface_drift
* **S_sensor**: sensor.delay, sensor.dropout, sensor.noise, sensor.reassignment, sensor.window_mismatch, temporal.asynchronous, variable.deletion
* **S_variable**: boundary.fragmentation

## Performance by cell-level regime (mean [95 % CI] (n cell×seed))

| metric | regime | none | aif_fixed | aif_adaptive | ost |
|---|---|---|---|---|---|
| one_step_acc_pert | AIF | — | 0.47 [0.46, 0.47] (n=11070) | 0.62 [0.62, 0.63] (n=11070) | 0.48 [0.48, 0.49] (n=11047) |
| one_step_acc_pert | POST | — | 0.30 [0.29, 0.31] (n=780) | 0.46 [0.44, 0.47] (n=780) | 0.47 [0.45, 0.48] (n=780) |
| one_step_acc_pert | REF | — | 0.52 [0.43, 0.61] (n=30) | 0.66 [0.62, 0.71] (n=30) | 0.48 [0.43, 0.52] (n=30) |
| one_step_acc_pert | TRANS | — | 0.33 [0.32, 0.35] (n=840) | 0.48 [0.47, 0.49] (n=840) | 0.47 [0.45, 0.48] (n=816) |
| success_pert | AIF | 0.38 [0.37, 0.38] (n=11070) | 0.39 [0.39, 0.40] (n=11070) | 0.41 [0.40, 0.41] (n=11070) | 0.37 [0.37, 0.37] (n=11070) |
| success_pert | POST | 0.40 [0.38, 0.41] (n=810) | 0.37 [0.36, 0.38] (n=810) | 0.34 [0.33, 0.35] (n=810) | 0.30 [0.29, 0.31] (n=810) |
| success_pert | REF | 0.40 [0.32, 0.47] (n=30) | 0.43 [0.34, 0.52] (n=30) | 0.47 [0.39, 0.54] (n=30) | 0.39 [0.35, 0.44] (n=30) |
| success_pert | TRANS | 0.38 [0.36, 0.39] (n=840) | 0.37 [0.35, 0.38] (n=840) | 0.35 [0.34, 0.37] (n=840) | 0.32 [0.31, 0.33] (n=840) |
| success_rec | AIF | 0.27 [0.27, 0.28] (n=11070) | 0.35 [0.34, 0.35] (n=11070) | 0.36 [0.36, 0.36] (n=11070) | 0.38 [0.38, 0.38] (n=11070) |
| success_rec | POST | 0.27 [0.27, 0.28] (n=810) | 0.37 [0.36, 0.39] (n=810) | 0.32 [0.31, 0.34] (n=810) | 0.37 [0.37, 0.38] (n=810) |
| success_rec | REF | 0.27 [0.23, 0.32] (n=30) | 0.35 [0.28, 0.41] (n=30) | 0.41 [0.35, 0.48] (n=30) | 0.39 [0.35, 0.43] (n=30) |
| success_rec | TRANS | 0.27 [0.27, 0.28] (n=840) | 0.37 [0.35, 0.38] (n=840) | 0.35 [0.33, 0.36] (n=840) | 0.37 [0.36, 0.38] (n=840) |

Paired contrasts (Holm over all):

| metric | regime | contrast | mean diff [95 % CI] | dz | p (Holm) |
|---|---|---|---|---|---|
| one_step_acc_pert | AIF | aif_adaptive - aif_fixed | 0.16 [0.15, 0.16] | 0.69 | 0.0146 |
| one_step_acc_pert | AIF | aif_adaptive - ost | 0.14 [0.13, 0.14] | 0.62 | 0.0146 |
| one_step_acc_pert | AIF | aif_fixed - ost | -0.02 [-0.02, -0.01] | -0.06 | 0.0146 |
| one_step_acc_pert | POST | aif_adaptive - aif_fixed | 0.16 [0.14, 0.18] | 0.63 | 0.0146 |
| one_step_acc_pert | POST | aif_adaptive - ost | -0.01 [-0.02, 0.00] | -0.05 | 1.0000 |
| one_step_acc_pert | POST | aif_fixed - ost | -0.17 [-0.19, -0.15] | -0.59 | 0.0146 |
| one_step_acc_pert | REF | aif_adaptive - aif_fixed | 0.14 [0.06, 0.23] | 0.62 | 0.0527 |
| one_step_acc_pert | REF | aif_adaptive - ost | 0.19 [0.12, 0.26] | 0.88 | 0.0146 |
| one_step_acc_pert | REF | aif_fixed - ost | 0.05 [-0.06, 0.15] | 0.16 | 1.0000 |
| one_step_acc_pert | TRANS | aif_adaptive - aif_fixed | 0.15 [0.13, 0.16] | 0.67 | 0.0146 |
| one_step_acc_pert | TRANS | aif_adaptive - ost | 0.02 [-0.00, 0.03] | 0.07 | 0.9451 |
| one_step_acc_pert | TRANS | aif_fixed - ost | -0.13 [-0.15, -0.11] | -0.47 | 0.0146 |
| success_pert | AIF | aif_adaptive - aif_fixed | 0.01 [0.01, 0.02] | 0.10 | 0.0146 |
| success_pert | AIF | aif_adaptive - none | 0.03 [0.02, 0.03] | 0.10 | 0.0146 |
| success_pert | AIF | aif_adaptive - ost | 0.03 [0.03, 0.04] | 0.15 | 0.0146 |
| success_pert | AIF | aif_fixed - none | 0.02 [0.01, 0.02] | 0.05 | 0.0146 |
| success_pert | AIF | aif_fixed - ost | 0.02 [0.02, 0.03] | 0.09 | 0.0146 |
| success_pert | AIF | ost - none | -0.01 [-0.01, -0.00] | -0.03 | 0.0618 |
| success_pert | POST | aif_adaptive - aif_fixed | -0.03 [-0.04, -0.02] | -0.19 | 0.0146 |
| success_pert | POST | aif_adaptive - none | -0.06 [-0.08, -0.04] | -0.24 | 0.0146 |
| success_pert | POST | aif_adaptive - ost | 0.04 [0.03, 0.05] | 0.21 | 0.0146 |
| success_pert | POST | aif_fixed - none | -0.03 [-0.05, -0.01] | -0.09 | 0.1538 |
| success_pert | POST | aif_fixed - ost | 0.07 [0.05, 0.08] | 0.29 | 0.0146 |
| success_pert | POST | ost - none | -0.10 [-0.11, -0.08] | -0.42 | 0.0146 |
| success_pert | REF | aif_adaptive - aif_fixed | 0.04 [-0.02, 0.10] | 0.22 | 1.0000 |
| success_pert | REF | aif_adaptive - none | 0.07 [-0.05, 0.19] | 0.20 | 1.0000 |
| success_pert | REF | aif_adaptive - ost | 0.08 [-0.02, 0.17] | 0.28 | 1.0000 |
| success_pert | REF | aif_fixed - none | 0.03 [-0.10, 0.16] | 0.09 | 1.0000 |
| success_pert | REF | aif_fixed - ost | 0.04 [-0.07, 0.15] | 0.13 | 1.0000 |
| success_pert | REF | ost - none | -0.01 [-0.08, 0.06] | -0.04 | 1.0000 |
| success_pert | TRANS | aif_adaptive - aif_fixed | -0.01 [-0.02, -0.00] | -0.09 | 0.1438 |
| success_pert | TRANS | aif_adaptive - none | -0.03 [-0.04, -0.01] | -0.10 | 0.1367 |
| success_pert | TRANS | aif_adaptive - ost | 0.04 [0.02, 0.05] | 0.17 | 0.0146 |
| success_pert | TRANS | aif_fixed - none | -0.01 [-0.03, 0.01] | -0.04 | 1.0000 |
| success_pert | TRANS | aif_fixed - ost | 0.05 [0.03, 0.07] | 0.20 | 0.0146 |
| success_pert | TRANS | ost - none | -0.06 [-0.08, -0.05] | -0.26 | 0.0146 |
| success_rec | AIF | aif_adaptive - aif_fixed | 0.02 [0.01, 0.02] | 0.08 | 0.0146 |
| success_rec | AIF | aif_adaptive - none | 0.09 [0.08, 0.09] | 0.37 | 0.0146 |
| success_rec | AIF | aif_adaptive - ost | -0.02 [-0.02, -0.01] | -0.08 | 0.0146 |
| success_rec | AIF | aif_fixed - none | 0.07 [0.07, 0.08] | 0.30 | 0.0146 |
| success_rec | AIF | aif_fixed - ost | -0.03 [-0.04, -0.03] | -0.15 | 0.0146 |
| success_rec | AIF | ost - none | 0.10 [0.10, 0.11] | 0.60 | 0.0146 |
| success_rec | POST | aif_adaptive - aif_fixed | -0.05 [-0.07, -0.03] | -0.21 | 0.0146 |
| success_rec | POST | aif_adaptive - none | 0.05 [0.03, 0.07] | 0.21 | 0.0146 |
| success_rec | POST | aif_adaptive - ost | -0.05 [-0.06, -0.03] | -0.22 | 0.0146 |
| success_rec | POST | aif_fixed - none | 0.10 [0.08, 0.12] | 0.40 | 0.0146 |
| success_rec | POST | aif_fixed - ost | 0.00 [-0.01, 0.02] | 0.01 | 1.0000 |
| success_rec | POST | ost - none | 0.10 [0.09, 0.11] | 0.59 | 0.0146 |
| success_rec | REF | aif_adaptive - aif_fixed | 0.06 [0.00, 0.13] | 0.37 | 0.9451 |
| success_rec | REF | aif_adaptive - none | 0.14 [0.05, 0.22] | 0.57 | 0.1333 |
| success_rec | REF | aif_adaptive - ost | 0.02 [-0.06, 0.10] | 0.09 | 1.0000 |
| success_rec | REF | aif_fixed - none | 0.07 [-0.01, 0.16] | 0.31 | 1.0000 |
| success_rec | REF | aif_fixed - ost | -0.04 [-0.13, 0.04] | -0.19 | 1.0000 |
| success_rec | REF | ost - none | 0.12 [0.07, 0.17] | 0.86 | 0.0146 |
| success_rec | TRANS | aif_adaptive - aif_fixed | -0.02 [-0.03, -0.00] | -0.08 | 0.3651 |
| success_rec | TRANS | aif_adaptive - none | 0.07 [0.06, 0.09] | 0.32 | 0.0146 |
| success_rec | TRANS | aif_adaptive - ost | -0.02 [-0.03, -0.01] | -0.10 | 0.0644 |
| success_rec | TRANS | aif_fixed - none | 0.09 [0.07, 0.11] | 0.36 | 0.0146 |
| success_rec | TRANS | aif_fixed - ost | -0.00 [-0.02, 0.01] | -0.02 | 1.0000 |
| success_rec | TRANS | ost - none | 0.09 [0.08, 0.11] | 0.57 | 0.0146 |

## Tracking by regime (cell × seed label)

| regime | tracker, world-side (detects onset) | tracker, observation-side (correctly: no world change) | comparator surprise, world-side | sensor-only tracker, world-side | localisation AUC tracker | localisation AUC comparator |
|---|---|---|---|---|---|---|
| AIF | 0.65 (n=5672) | 0.96 (n=2950) | 0.07 (n=5672) | 0.16 (n=5672) | 0.43 [0.43, 0.43] (n=5213) | 0.53 [0.53, 0.53] (n=5213) |
| TRANS | 0.97 (n=148) | 0.97 (n=464) | 0.29 (n=148) | 0.43 (n=148) | 0.47 [0.46, 0.49] (n=67) | 0.54 [0.53, 0.55] (n=67) |
| POST | — (n=0) | 0.98 (n=666) | — (n=0) | — (n=0) | — | — |

## Comparator structurally invalid vs tracking

```
{
 "comparator_structurally_invalid_cell_seeds": 916,
 "of_which_tracking_preserved": 654,
 "of_which_tracking_failed": 12,
 "of_which_tracking_not_applicable": 250,
 "where": {
  "sensor.delay": 278,
  "temporal.asynchronous": 99,
  "sensor.reassignment": 84,
  "sensor.dropout": 58,
  "sensor.noise": 50,
  "variable.deletion": 47,
  "variable.relabel": 23,
  "sensor.window_mismatch": 12,
  "variable.outcome_merge": 2,
  "sensor.partial_observability": 1
 },
 "note": "tracking_preserved uses the full-stream tracker (information advantage); the sensor-only tracker's detection is reported in tracking_by_regime"
}
```

## Structure-learning overlap

```
{
 "cell_seeds": 0,
 "where": {},
 "definition": "fixed-model validity < 0.5 while the adaptive (structure-learning-lite) model keeps \u2265 0.8"
}
```

## Too-slow correction (drift)

### temporal.interface_drift

Staleness period (steps): 226; adaptive lag at slowest drift: 72.33 [45.33, 105.00] (n=30)

| severity | period | success none | aif_fixed | aif_adaptive | ost | aif_adaptive − none (p) | ost − none (p) | acc aif_adaptive |
|---|---|---|---|---|---|---|---|---|
| 0.083 | 226 | 0.40 | 0.28 | 0.32 | 0.30 | -0.11 (0.005) | -0.12 (0.004) | 0.46 |
| 0.125 | 196 | 0.40 | 0.27 | 0.29 | 0.29 | -0.13 (0.007) | -0.14 (0.000) | 0.45 |
| 0.167 | 170 | 0.40 | 0.26 | 0.32 | 0.27 | -0.11 (0.008) | -0.15 (0.001) | 0.47 |
| 0.25 | 128 | 0.40 | 0.28 | 0.29 | 0.29 | -0.14 (0.001) | -0.13 (0.001) | 0.48 |
| 0.375 | 84 | 0.40 | 0.29 | 0.29 | 0.28 | -0.13 (0.001) | -0.14 (0.001) | 0.42 |
| 0.5 | 55 | 0.40 | 0.30 | 0.34 | 0.26 | -0.10 (0.024) | -0.17 (0.000) | 0.42 |
| 0.625 | 36 | 0.40 | 0.32 | 0.32 | 0.31 | -0.10 (0.006) | -0.12 (0.002) | 0.39 |
| 0.75 | 23 | 0.40 | 0.28 | 0.31 | 0.27 | -0.12 (0.001) | -0.15 (0.001) | 0.38 |
| 0.875 | 15 | 0.40 | 0.30 | 0.32 | 0.26 | -0.10 (0.007) | -0.17 (0.000) | 0.37 |
| 1.0 | 10 | 0.40 | 0.31 | 0.32 | 0.30 | -0.09 (0.012) | -0.14 (0.001) | 0.38 |

### temporal.world_drift

Staleness period (steps): 196; adaptive lag at slowest drift: 41.33 [29.99, 55.33] (n=30)

| severity | period | success none | aif_fixed | aif_adaptive | ost | aif_adaptive − none (p) | ost − none (p) | acc aif_adaptive |
|---|---|---|---|---|---|---|---|---|
| 0.125 | 196 | 0.38 | 0.45 | 0.47 | 0.40 | 0.07 (0.218) | 0.00 (0.922) | 0.68 |
| 0.25 | 128 | 0.39 | 0.45 | 0.49 | 0.41 | 0.06 (0.314) | -0.00 (0.913) | 0.68 |
| 0.375 | 84 | 0.39 | 0.44 | 0.45 | 0.41 | 0.04 (0.539) | 0.01 (0.798) | 0.68 |
| 0.5 | 55 | 0.40 | 0.44 | 0.47 | 0.42 | 0.03 (0.579) | -0.01 (0.779) | 0.65 |
| 0.625 | 36 | 0.42 | 0.43 | 0.44 | 0.42 | -0.00 (0.977) | -0.01 (0.812) | 0.64 |
| 0.75 | 23 | 0.39 | 0.45 | 0.47 | 0.43 | 0.04 (0.473) | 0.01 (0.733) | 0.67 |
| 0.875 | 15 | 0.40 | 0.44 | 0.47 | 0.43 | -0.00 (0.965) | -0.00 (0.917) | 0.68 |
| 1.0 | 10 | 0.37 | 0.43 | 0.48 | 0.42 | 0.11 (0.071) | 0.05 (0.194) | 0.68 |

## History re-entry

| severity | n | Δ success_rec aif_adaptive (react − remove) | Δ ost | Δ pattern recurrence | migration destination gain |
|---|---|---|---|---|---|
| 0.125 | 30 | -0.03 [-0.08, 0.01] p=0.188 | -0.00 [-0.03, 0.03] p=0.966 | -0.00 [-0.01, 0.00] p=0.271 | 0.00 [-0.04, 0.05] p=0.962 |
| 0.25 | 30 | 0.04 [-0.03, 0.11] p=0.359 | 0.00 [-0.03, 0.03] p=1.000 | -0.01 [-0.03, 0.01] p=0.424 | -0.01 [-0.02, 0.01] p=0.567 |
| 0.375 | 30 | -0.02 [-0.08, 0.03] p=0.472 | -0.02 [-0.06, 0.03] p=0.443 | 0.01 [-0.00, 0.02] p=0.218 | 0.01 [-0.00, 0.03] p=0.182 |
| 0.5 | 30 | -0.03 [-0.10, 0.03] p=0.347 | -0.01 [-0.05, 0.03] p=0.651 | -0.01 [-0.05, 0.03] p=0.784 | 0.01 [-0.01, 0.03] p=0.243 |
| 0.625 | 30 | -0.01 [-0.07, 0.05] p=0.706 | -0.00 [-0.04, 0.03] p=0.942 | -0.00 [-0.02, 0.02] p=0.861 | 0.00 [-0.01, 0.01] p=0.883 |
| 0.75 | 30 | -0.02 [-0.06, 0.02] p=0.316 | 0.01 [-0.03, 0.06] p=0.643 | -0.01 [-0.03, 0.01] p=0.523 | -0.00 [-0.02, 0.01] p=0.620 |
| 0.875 | 30 | 0.01 [-0.04, 0.06] p=0.720 | -0.02 [-0.05, 0.00] p=0.167 | -0.02 [-0.05, 0.01] p=0.297 | -0.00 [-0.02, 0.01] p=0.695 |
| 1.0 | 30 | -0.04 [-0.09, -0.00] p=0.068 | -0.04 [-0.07, -0.01] p=0.018 | 0.00 [-0.01, 0.01] p=0.560 | -0.01 [-0.02, 0.00] p=0.157 |

## Non-redundancy (element × regime; capabilities where NON-REDUNDANT / HARMFUL)

| element | regime | status | non-redundant for | harmful for |
|---|---|---|---|---|
| agent | AIF | NON-REDUNDANT | prediction | perturbation_localisation |
| agent | POST | NON-REDUNDANT | structural_transition_detection | — |
| agent | REF | NON-REDUNDANT | prediction | — |
| agent | TRANS | NON-REDUNDANT | prediction | — |
| boundary | AIF | NON-REDUNDANT | intervention, recovery, history_reuse | prediction |
| boundary | POST | NON-REDUNDANT | intervention, recovery | prediction |
| boundary | REF | NON-REDUNDANT | intervention, recovery | — |
| boundary | TRANS | NON-REDUNDANT | intervention, recovery | prediction |
| boundary (model-light controller) | AIF | NON-REDUNDANT | intervention, recovery | — |
| boundary (model-light controller) | POST | NON-REDUNDANT | intervention, recovery | — |
| boundary (model-light controller) | REF | NON-REDUNDANT | intervention, recovery | — |
| boundary (model-light controller) | TRANS | NON-REDUNDANT | intervention, recovery | — |
| expected_free_energy | AIF | UNRESOLVED | — | — |
| expected_free_energy | POST | UNRESOLVED | — | — |
| expected_free_energy | REF | UNRESOLVED | — | — |
| expected_free_energy | TRANS | UNRESOLVED | — | — |
| free_energy | AIF | UNRESOLVED | — | recovery |
| free_energy | POST | UNRESOLVED | — | recovery |
| free_energy | REF | UNRESOLVED | — | — |
| free_energy | TRANS | UNRESOLVED | — | — |
| latent_state | AIF | UNRESOLVED | — | — |
| latent_state | POST | UNRESOLVED | — | — |
| latent_state | REF | UNRESOLVED | — | — |
| latent_state | TRANS | UNRESOLVED | — | — |
| model | AIF | NON-REDUNDANT | prediction, recovery, history_reuse | perturbation_localisation, structural_transition_detection |
| model | POST | UNRESOLVED | — | — |
| model | REF | UNRESOLVED | — | — |
| model | TRANS | NON-REDUNDANT | recovery | — |
| policy | AIF | NON-REDUNDANT | intervention, recovery, history_reuse | perturbation_localisation |
| policy | POST | NON-REDUNDANT | recovery | — |
| policy | REF | NON-REDUNDANT | intervention, recovery | — |
| policy | TRANS | NON-REDUNDANT | intervention, recovery | — |
| prediction_error | AIF | NON-REDUNDANT | prediction | — |
| prediction_error | POST | NON-REDUNDANT | prediction | — |
| prediction_error | REF | NON-REDUNDANT | prediction | — |
| prediction_error | TRANS | NON-REDUNDANT | prediction | — |

Tests: 184 (Holm); margin ±0.05.

## Failures

```
{
 "simulator_failure": 0,
 "numerical_failure": 0,
 "benchmark_failure": 0,
 "comparator_failure": 0,
 "model_structure_failure": 0,
 "controller_failure": 9070,
 "genuine_regime_transition": 1809
}
```

## C_AIF crossings (severity; bootstrap 95 % CI; share of seeds crossing)

| perturbation | crosses 0.8 at | CI | seeds | crosses 0.5 at | CI | seeds |
|---|---|---|---|---|---|---|
| boundary.delayed_update | — | None | 0.00 | — | None | 0.00 |
| boundary.disappearance | — | [0.97, 1.0] | 0.30 | — | None | 0.03 |
| boundary.fragmentation | 0.87 | [0.82, 0.9] | 0.77 | — | None | 0.17 |
| boundary.leakage | — | None | 0.00 | — | None | 0.00 |
| boundary.merge | — | None | 0.00 | — | None | 0.00 |
| boundary.noise | — | None | 0.07 | — | None | 0.00 |
| boundary.reassignment | 0.66 | [0.6, 0.72] | 1.00 | 0.98 | [0.95, 1.0] | 0.60 |
| coupling.asymmetric | — | None | 0.00 | — | None | 0.00 |
| coupling.cross_cluster | — | None | 0.00 | — | None | 0.00 |
| coupling.reversal | — | None | 0.47 | — | None | 0.00 |
| coupling.strengthening | — | None | 0.00 | — | None | 0.00 |
| coupling.temporary_decoupling | — | None | 0.07 | — | None | 0.00 |
| coupling.weakening | 0.70 | [0.65, 0.82] | 0.77 | — | None | 0.00 |
| memory.access_block | — | None | 0.03 | — | None | 0.00 |
| memory.deletion | — | None | 0.00 | — | None | 0.00 |
| memory.history_reactivation | — | None | 0.00 | — | None | 0.00 |
| memory.history_removal | — | None | 0.00 | — | None | 0.00 |
| memory.migration | — | None | 0.03 | — | None | 0.00 |
| memory.truncation | — | None | 0.03 | — | None | 0.00 |
| sensor.delay | 0.05 | [0.04, 0.06] | 1.00 | 0.26 | [0.12, 0.28] | 1.00 |
| sensor.dropout | 0.88 | [0.88, 0.88] | 1.00 | 0.89 | [0.89, 0.9] | 1.00 |
| sensor.noise | 0.41 | [0.35, 0.47] | 0.97 | 0.87 | [0.76, 0.99] | 0.63 |
| sensor.partial_observability | — | None | 0.10 | — | None | 0.03 |
| sensor.permutation | — | None | 0.00 | — | None | 0.00 |
| sensor.reassignment | 0.59 | [0.53, 0.76] | 1.00 | 0.88 | [0.82, 0.89] | 1.00 |
| sensor.scale_mismatch | — | None | 0.03 | — | None | 0.00 |
| sensor.window_mismatch | 0.85 | [0.74, 0.87] | 0.93 | — | None | 0.27 |
| structural.cut_reconnect | — | None | 0.37 | — | None | 0.00 |
| structural.disconnection | — | None | 0.33 | — | None | 0.00 |
| structural.multi_cluster_reorganization | — | None | 0.00 | — | None | 0.00 |
| temporal.asynchronous | 0.63 | [0.6, 0.66] | 1.00 | 0.83 | [0.8, 0.85] | 1.00 |
| temporal.horizon_compression | — | None | 0.03 | — | None | 0.00 |
| temporal.horizon_expansion | — | None | 0.03 | — | None | 0.00 |
| temporal.interface_drift | 0.05 | [0.04, 0.05] | 1.00 | 0.14 | [0.14, 0.15] | 1.00 |
| temporal.world_drift | — | None | 0.00 | — | None | 0.00 |
| topology.cluster_merge | — | None | 0.00 | — | None | 0.00 |
| topology.cluster_split | — | None | 0.00 | — | None | 0.00 |
| topology.dynamic_mutation | — | None | 0.13 | — | None | 0.00 |
| topology.edge_addition | — | None | 0.00 | — | None | 0.00 |
| topology.edge_deletion | — | None | 0.10 | — | None | 0.00 |
| topology.hub_removal | — | None | 0.00 | — | None | 0.00 |
| topology.rerouting | — | None | 0.00 | — | None | 0.00 |
| variable.deletion | 0.88 | [0.87, 0.9] | 1.00 | 0.92 | [0.9, 0.94] | 1.00 |
| variable.duplication | — | None | 0.07 | — | None | 0.00 |
| variable.outcome_merge | — | None | 0.10 | — | None | 0.03 |
| variable.relabel | 0.88 | [0.77, 0.98] | 0.57 | — | None | 0.40 |
| variable.remap | — | None | 0.07 | — | None | 0.00 |

