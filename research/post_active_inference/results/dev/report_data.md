# Measured tables — stage `dev`

Seeds: 10; severities: [0.25, 0.5, 0.75, 1.0]; perturbation subtypes run: 47.

## Null check (unperturbed noise replicate vs control, leave-one-seed-out tolerance)

Per-seed labels: {'ACTIVE_INFERENCE_COMPATIBLE': 10}; mislabelled share 0.00; cell-level C_AIF 1.00 → ACTIVE_INFERENCE_COMPATIBLE.

Noise tolerance per raw quantity: {"acc": 0.42, "acc_adaptive": 0.32, "sensor": 0.03, "pc1": 0.148, "sep": 0.37, "bshare": 0.266}

## Cell-level regime by perturbation and severity (C_AIF; first unstable primitive)

| perturbation | side | sev 0.25 | sev 0.5 | sev 0.75 | sev 1 | transition kind |
|---|---|---|---|---|---|---|
| boundary.delayed_update | boundary | AIF 1.00 | AIF 0.99 | AIF 0.98 | AIF 0.96 | compatible_throughout |
| boundary.disappearance | boundary | AIF 1.00 | AIF 0.97 | AIF 0.97 | TRANS 0.77 (variable) | graded |
| boundary.fragmentation | boundary | AIF 1.00 | AIF 0.94 | AIF 0.83 | AIF 0.80 | compatible_throughout |
| boundary.leakage | boundary | AIF 0.97 | AIF 0.92 | TRANS 0.78 (variable) | TRANS 0.68 (variable) | graded |
| boundary.merge | boundary | TRANS 0.75 (variable) | TRANS 0.65 (variable) | TRANS 0.67 (variable) | TRANS 0.65 (variable) | graded |
| boundary.noise | boundary | AIF 1.00 | AIF 1.00 | AIF 0.98 | AIF 0.94 | compatible_throughout |
| boundary.reassignment | boundary | TRANS 0.74 (variable) | TRANS 0.77 (variable) | TRANS 0.77 (variable) | POST 0.45 (policy) | graded |
| coupling.asymmetric | coupling | AIF 0.99 | AIF 0.99 | AIF 0.99 | AIF 0.98 | compatible_throughout |
| coupling.cross_cluster | coupling | AIF 0.99 | AIF 0.99 | AIF 0.98 | AIF 0.99 | compatible_throughout |
| coupling.reversal | coupling | AIF 0.97 | AIF 0.90 | AIF 0.83 | TRANS 0.76 (model) | graded |
| coupling.strengthening | coupling | AIF 0.99 | AIF 0.98 | AIF 0.97 | AIF 0.97 | compatible_throughout |
| coupling.temporary_decoupling | coupling | AIF 0.97 | AIF 1.00 | AIF 0.94 | AIF 0.85 | compatible_throughout |
| coupling.weakening | coupling | AIF 0.97 | AIF 0.94 | TRANS 0.77 (variable) | TRANS 0.66 (variable) | graded |
| memory.access_block | memory | AIF 1.00 | AIF 1.00 | AIF 1.00 | AIF 0.99 | compatible_throughout |
| memory.deletion | memory | AIF 0.99 | AIF 0.99 | AIF 1.00 | AIF 0.99 | compatible_throughout |
| memory.history_reactivation | memory | AIF 1.00 | AIF 1.00 | AIF 1.00 | AIF 1.00 | compatible_throughout |
| memory.history_removal | memory | AIF 1.00 | AIF 1.00 | AIF 1.00 | AIF 1.00 | compatible_throughout |
| memory.migration | memory | AIF 1.00 | AIF 1.00 | AIF 1.00 | AIF 0.98 | compatible_throughout |
| memory.truncation | memory | AIF 1.00 | AIF 0.98 | AIF 1.00 | AIF 0.99 | compatible_throughout |
| sensor.delay | sensor | TRANS 0.51 (sensor) | POST 0.20 (sensor) | POST 0.07 (sensor) | POST 0.23 (sensor) | graded |
| sensor.dropout | sensor | AIF 0.94 | AIF 0.93 | AIF 0.89 | POST 0.03 (sensor) | abrupt |
| sensor.noise | sensor | AIF 0.93 | TRANS 0.74 (sensor) | TRANS 0.62 (sensor) | TRANS 0.51 (sensor) | graded |
| sensor.partial_observability | sensor | AIF 1.00 | AIF 0.97 | AIF 0.95 | AIF 0.92 | compatible_throughout |
| sensor.permutation | sensor | AIF 1.00 | AIF 1.00 | AIF 1.00 | AIF 1.00 | compatible_throughout |
| sensor.reassignment | sensor | AIF 0.97 | AIF 0.80 | TRANS 0.62 (sensor) | POST 0.23 (sensor) | graded |
| sensor.scale_mismatch | sensor | AIF 1.00 | AIF 1.00 | AIF 0.98 | AIF 0.97 | compatible_throughout |
| sensor.window_mismatch | sensor | AIF 0.97 | AIF 0.97 | AIF 0.86 | TRANS 0.60 (sensor) | graded |
| structural.cut_reconnect | structural | AIF 0.97 | AIF 0.97 | AIF 0.89 | TRANS 0.75 (model) | graded |
| structural.disconnection | structural | AIF 0.98 | AIF 0.96 | AIF 0.92 | TRANS 0.78 (model) | graded |
| structural.multi_cluster_reorganization | structural | AIF 0.99 | AIF 0.98 | AIF 0.98 | AIF 0.95 | compatible_throughout |
| temporal.asynchronous | temporal | AIF 0.99 | AIF 0.93 | TRANS 0.68 (sensor) | POST 0.03 (sensor) | graded |
| temporal.horizon_compression | temporal | AIF 1.00 | AIF 1.00 | AIF 1.00 | AIF 1.00 | compatible_throughout |
| temporal.horizon_expansion | temporal | AIF 0.98 | AIF 0.96 | AIF 0.96 | AIF 0.98 | compatible_throughout |
| temporal.interface_drift | temporal | POST 0.32 (policy) | POST 0.00 (policy) | POST 0.33 (policy) | TRANS 0.62 (policy) | graded |
| temporal.world_drift | temporal | AIF 1.00 | AIF 0.99 | AIF 1.00 | AIF 1.00 | compatible_throughout |
| topology.cluster_merge | topology | AIF 0.98 | AIF 0.89 | TRANS 0.67 (variable) | TRANS 0.65 (variable) | graded |
| topology.cluster_split | topology | AIF 1.00 | AIF 0.99 | AIF 0.97 | AIF 0.96 | compatible_throughout |
| topology.dynamic_mutation | topology | AIF 0.97 | AIF 0.97 | AIF 0.95 | AIF 0.92 | compatible_throughout |
| topology.edge_addition | topology | AIF 1.00 | AIF 0.98 | AIF 0.99 | AIF 0.99 | compatible_throughout |
| topology.edge_deletion | topology | AIF 0.97 | AIF 0.94 | AIF 0.95 | AIF 0.89 | compatible_throughout |
| topology.hub_removal | topology | AIF 0.97 | AIF 0.97 | AIF 0.98 | AIF 0.99 | compatible_throughout |
| topology.rerouting | topology | AIF 0.99 | AIF 0.96 | AIF 0.92 | AIF 0.91 | compatible_throughout |
| variable.deletion | variable | AIF 1.00 | AIF 0.97 | AIF 0.96 | POST 0.03 (sensor) | abrupt |
| variable.duplication | variable | AIF 0.99 | AIF 1.00 | AIF 0.98 | AIF 0.98 | compatible_throughout |
| variable.outcome_merge | variable | AIF 1.00 | AIF 0.95 | AIF 0.91 | AIF 0.85 | compatible_throughout |
| variable.relabel | variable | AIF 1.00 | AIF 0.87 | AIF 0.83 | TRANS 0.69 (sensor) | graded |
| variable.remap | variable | AIF 0.96 | TRANS 0.75 (model) | TRANS 0.77 (model) | TRANS 0.77 (model) | graded |

Transition kinds: {'compatible_throughout': 28, 'graded': 17, 'abrupt': 2}

## Regime counts

Cell level: {'ACTIVE_INFERENCE_COMPATIBLE': 148, 'TRANSITION': 29, 'POST_ACTIVE_INFERENCE': 11}

Cell × seed level: {'ACTIVE_INFERENCE_COMPATIBLE': 1427, 'TRANSITION': 316, 'POST_ACTIVE_INFERENCE': 137}; threshold sensitivity (cell × seed): {'0.7/0.4': {'ACTIVE_INFERENCE_COMPATIBLE': 1540, 'TRANSITION': 220, 'POST_ACTIVE_INFERENCE': 120}, '0.9/0.6': {'ACTIVE_INFERENCE_COMPATIBLE': 1316, 'TRANSITION': 358, 'POST_ACTIVE_INFERENCE': 206}}

| family | AIF | TRANS | POST |
|---|---|---|---|
| boundary | 176 | 91 | 13 |
| coupling | 197 | 43 | 0 |
| memory | 238 | 2 | 0 |
| sensor | 198 | 56 | 66 |
| structural | 94 | 26 | 0 |
| temporal | 139 | 20 | 41 |
| topology | 235 | 44 | 1 |
| variable | 150 | 34 | 16 |

## First unstable primitive (lowest severity at which most seeds leave the compatible regime)

* **S_model**: boundary.disappearance, coupling.reversal, coupling.temporary_decoupling, coupling.weakening, structural.cut_reconnect, structural.disconnection, variable.remap
* **S_policy**: temporal.interface_drift
* **S_sensor**: sensor.delay, sensor.dropout, sensor.noise, sensor.reassignment, sensor.window_mismatch, temporal.asynchronous, variable.deletion, variable.relabel
* **S_variable**: boundary.fragmentation, boundary.leakage, boundary.merge, boundary.reassignment, topology.cluster_merge

## Performance by cell-level regime (mean [95 % CI] (n cell×seed))

| metric | regime | none | aif_fixed | aif_adaptive | ost |
|---|---|---|---|---|---|
| one_step_acc_pert | AIF | — | 0.51 [0.49, 0.52] (n=1480) | 0.59 [0.58, 0.60] (n=1480) | 0.49 [0.49, 0.50] (n=1478) |
| one_step_acc_pert | POST | — | 0.27 [0.24, 0.31] (n=100) | 0.45 [0.41, 0.49] (n=100) | 0.53 [0.48, 0.57] (n=100) |
| one_step_acc_pert | REF | — | 0.60 [0.48, 0.72] (n=10) | 0.67 [0.61, 0.74] (n=10) | 0.49 [0.44, 0.55] (n=10) |
| one_step_acc_pert | TRANS | — | 0.35 [0.31, 0.38] (n=290) | 0.56 [0.54, 0.58] (n=290) | 0.53 [0.51, 0.55] (n=290) |
| success_pert | AIF | 0.36 [0.35, 0.37] (n=1480) | 0.47 [0.46, 0.48] (n=1480) | 0.47 [0.46, 0.48] (n=1480) | 0.39 [0.38, 0.39] (n=1480) |
| success_pert | POST | 0.35 [0.31, 0.39] (n=110) | 0.42 [0.38, 0.45] (n=110) | 0.38 [0.35, 0.41] (n=110) | 0.33 [0.30, 0.36] (n=110) |
| success_pert | REF | 0.35 [0.21, 0.48] (n=10) | 0.54 [0.45, 0.62] (n=10) | 0.55 [0.44, 0.67] (n=10) | 0.41 [0.38, 0.45] (n=10) |
| success_pert | TRANS | 0.30 [0.27, 0.32] (n=290) | 0.40 [0.37, 0.42] (n=290) | 0.38 [0.35, 0.41] (n=290) | 0.32 [0.31, 0.34] (n=290) |
| success_rec | AIF | 0.28 [0.27, 0.29] (n=1480) | 0.40 [0.39, 0.41] (n=1480) | 0.44 [0.43, 0.45] (n=1480) | 0.40 [0.39, 0.41] (n=1480) |
| success_rec | POST | 0.29 [0.27, 0.31] (n=110) | 0.41 [0.38, 0.44] (n=110) | 0.37 [0.34, 0.40] (n=110) | 0.37 [0.35, 0.39] (n=110) |
| success_rec | REF | 0.29 [0.23, 0.34] (n=10) | 0.46 [0.32, 0.60] (n=10) | 0.55 [0.45, 0.65] (n=10) | 0.44 [0.38, 0.49] (n=10) |
| success_rec | TRANS | 0.27 [0.26, 0.29] (n=290) | 0.37 [0.34, 0.39] (n=290) | 0.39 [0.37, 0.42] (n=290) | 0.37 [0.35, 0.38] (n=290) |

Paired contrasts (Holm over all):

| metric | regime | contrast | mean diff [95 % CI] | dz | p (Holm) |
|---|---|---|---|---|---|
| one_step_acc_pert | AIF | aif_adaptive - aif_fixed | 0.09 [0.08, 0.10] | 0.43 | 0.0146 |
| one_step_acc_pert | AIF | aif_adaptive - ost | 0.10 [0.09, 0.11] | 0.49 | 0.0146 |
| one_step_acc_pert | AIF | aif_fixed - ost | 0.01 [-0.00, 0.03] | 0.04 | 1.0000 |
| one_step_acc_pert | POST | aif_adaptive - aif_fixed | 0.17 [0.12, 0.24] | 0.56 | 0.0146 |
| one_step_acc_pert | POST | aif_adaptive - ost | -0.08 [-0.11, -0.04] | -0.46 | 0.0146 |
| one_step_acc_pert | POST | aif_fixed - ost | -0.25 [-0.32, -0.19] | -0.77 | 0.0146 |
| one_step_acc_pert | REF | aif_adaptive - aif_fixed | 0.07 [0.01, 0.14] | 0.61 | 1.0000 |
| one_step_acc_pert | REF | aif_adaptive - ost | 0.18 [0.09, 0.27] | 1.10 | 0.3281 |
| one_step_acc_pert | REF | aif_fixed - ost | 0.11 [-0.05, 0.26] | 0.41 | 1.0000 |
| one_step_acc_pert | TRANS | aif_adaptive - aif_fixed | 0.21 [0.18, 0.24] | 0.79 | 0.0146 |
| one_step_acc_pert | TRANS | aif_adaptive - ost | 0.03 [0.01, 0.05] | 0.14 | 0.4804 |
| one_step_acc_pert | TRANS | aif_fixed - ost | -0.18 [-0.22, -0.14] | -0.51 | 0.0146 |
| success_pert | AIF | aif_adaptive - aif_fixed | 0.00 [-0.00, 0.01] | 0.03 | 1.0000 |
| success_pert | AIF | aif_adaptive - none | 0.11 [0.10, 0.12] | 0.41 | 0.0146 |
| success_pert | AIF | aif_adaptive - ost | 0.08 [0.07, 0.09] | 0.42 | 0.0146 |
| success_pert | AIF | aif_fixed - none | 0.11 [0.09, 0.12] | 0.36 | 0.0146 |
| success_pert | AIF | aif_fixed - ost | 0.08 [0.07, 0.09] | 0.38 | 0.0146 |
| success_pert | AIF | ost - none | 0.03 [0.01, 0.04] | 0.11 | 0.0146 |
| success_pert | POST | aif_adaptive - aif_fixed | -0.04 [-0.07, -0.01] | -0.27 | 0.1589 |
| success_pert | POST | aif_adaptive - none | 0.03 [-0.02, 0.08] | 0.12 | 1.0000 |
| success_pert | POST | aif_adaptive - ost | 0.05 [0.02, 0.08] | 0.26 | 0.2124 |
| success_pert | POST | aif_fixed - none | 0.07 [0.02, 0.12] | 0.24 | 0.4218 |
| success_pert | POST | aif_fixed - ost | 0.09 [0.05, 0.13] | 0.39 | 0.0161 |
| success_pert | POST | ost - none | -0.02 [-0.06, 0.03] | -0.07 | 1.0000 |
| success_pert | REF | aif_adaptive - aif_fixed | 0.02 [-0.06, 0.09] | 0.14 | 1.0000 |
| success_pert | REF | aif_adaptive - none | 0.20 [0.07, 0.38] | 0.76 | 0.5391 |
| success_pert | REF | aif_adaptive - ost | 0.14 [0.02, 0.27] | 0.64 | 1.0000 |
| success_pert | REF | aif_fixed - none | 0.19 [0.03, 0.37] | 0.63 | 1.0000 |
| success_pert | REF | aif_fixed - ost | 0.12 [0.02, 0.23] | 0.70 | 1.0000 |
| success_pert | REF | ost - none | 0.06 [-0.07, 0.21] | 0.25 | 1.0000 |
| success_pert | TRANS | aif_adaptive - aif_fixed | -0.01 [-0.03, 0.00] | -0.10 | 1.0000 |
| success_pert | TRANS | aif_adaptive - none | 0.08 [0.05, 0.11] | 0.33 | 0.0146 |
| success_pert | TRANS | aif_adaptive - ost | 0.06 [0.04, 0.08] | 0.30 | 0.0146 |
| success_pert | TRANS | aif_fixed - none | 0.10 [0.07, 0.13] | 0.36 | 0.0146 |
| success_pert | TRANS | aif_fixed - ost | 0.07 [0.05, 0.10] | 0.34 | 0.0146 |
| success_pert | TRANS | ost - none | 0.02 [-0.00, 0.05] | 0.10 | 1.0000 |
| success_rec | AIF | aif_adaptive - aif_fixed | 0.04 [0.03, 0.05] | 0.18 | 0.0146 |
| success_rec | AIF | aif_adaptive - none | 0.16 [0.15, 0.17] | 0.73 | 0.0146 |
| success_rec | AIF | aif_adaptive - ost | 0.04 [0.03, 0.05] | 0.19 | 0.0146 |
| success_rec | AIF | aif_fixed - none | 0.12 [0.11, 0.13] | 0.58 | 0.0146 |
| success_rec | AIF | aif_fixed - ost | 0.00 [-0.01, 0.01] | 0.00 | 1.0000 |
| success_rec | AIF | ost - none | 0.12 [0.11, 0.13] | 0.72 | 0.0146 |
| success_rec | POST | aif_adaptive - aif_fixed | -0.04 [-0.08, 0.01] | -0.17 | 1.0000 |
| success_rec | POST | aif_adaptive - none | 0.08 [0.05, 0.12] | 0.43 | 0.0146 |
| success_rec | POST | aif_adaptive - ost | -0.00 [-0.04, 0.04] | -0.00 | 1.0000 |
| success_rec | POST | aif_fixed - none | 0.12 [0.08, 0.16] | 0.59 | 0.0146 |
| success_rec | POST | aif_fixed - ost | 0.04 [0.00, 0.07] | 0.18 | 1.0000 |
| success_rec | POST | ost - none | 0.08 [0.06, 0.11] | 0.61 | 0.0146 |
| success_rec | REF | aif_adaptive - aif_fixed | 0.09 [-0.05, 0.23] | 0.36 | 1.0000 |
| success_rec | REF | aif_adaptive - none | 0.26 [0.14, 0.38] | 1.28 | 0.1250 |
| success_rec | REF | aif_adaptive - ost | 0.11 [-0.01, 0.23] | 0.57 | 1.0000 |
| success_rec | REF | aif_fixed - none | 0.17 [0.02, 0.34] | 0.66 | 1.0000 |
| success_rec | REF | aif_fixed - ost | 0.03 [-0.09, 0.13] | 0.14 | 1.0000 |
| success_rec | REF | ost - none | 0.15 [0.08, 0.22] | 1.24 | 0.1758 |
| success_rec | TRANS | aif_adaptive - aif_fixed | 0.03 [0.00, 0.05] | 0.13 | 0.4760 |
| success_rec | TRANS | aif_adaptive - none | 0.12 [0.10, 0.14] | 0.58 | 0.0146 |
| success_rec | TRANS | aif_adaptive - ost | 0.03 [0.01, 0.05] | 0.14 | 0.4569 |
| success_rec | TRANS | aif_fixed - none | 0.09 [0.07, 0.11] | 0.45 | 0.0146 |
| success_rec | TRANS | aif_fixed - ost | 0.00 [-0.02, 0.02] | 0.01 | 1.0000 |
| success_rec | TRANS | ost - none | 0.09 [0.07, 0.11] | 0.59 | 0.0146 |

## Tracking by regime (cell × seed label)

| regime | tracker, world-side (detects onset) | tracker, observation-side (correctly: no world change) | comparator surprise, world-side | sensor-only tracker, world-side | localisation AUC tracker | localisation AUC comparator |
|---|---|---|---|---|---|---|
| AIF | 0.62 (n=804) | 1.00 (n=369) | 0.01 (n=804) | 0.20 (n=804) | 0.44 [0.44, 0.45] (n=744) | 0.55 [0.54, 0.55] (n=744) |
| TRANS | 0.87 (n=115) | 1.00 (n=99) | 0.18 (n=115) | 0.37 (n=115) | 0.46 [0.44, 0.47] (n=95) | 0.52 [0.51, 0.53] (n=95) |
| POST | 1.00 (n=1) | 1.00 (n=92) | 0.00 (n=1) | 1.00 (n=1) | 0.51 (n=1) | 0.50 (n=1) |

## Comparator structurally invalid vs tracking

```
{
 "comparator_structurally_invalid_cell_seeds": 137,
 "of_which_tracking_preserved": 93,
 "of_which_tracking_failed": 0,
 "of_which_tracking_not_applicable": 44,
 "where": {
  "sensor.delay": 34,
  "sensor.reassignment": 13,
  "sensor.dropout": 10,
  "temporal.asynchronous": 10,
  "variable.deletion": 10,
  "variable.relabel": 6,
  "sensor.noise": 4,
  "sensor.window_mismatch": 4,
  "sensor.partial_observability": 1,
  "topology.cluster_merge": 1
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

Staleness period (steps): 128; adaptive lag at slowest drift: 38.00 [21.00, 65.00] (n=10)

| severity | period | success none | aif_fixed | aif_adaptive | ost | aif_adaptive − none (p) | ost − none (p) | acc aif_adaptive |
|---|---|---|---|---|---|---|---|---|
| 0.25 | 128 | 0.35 | 0.32 | 0.33 | 0.32 | -0.06 (0.410) | -0.07 (0.430) | 0.39 |
| 0.5 | 55 | 0.35 | 0.35 | 0.38 | 0.31 | -0.02 (0.789) | -0.06 (0.461) | 0.44 |
| 0.75 | 23 | 0.35 | 0.32 | 0.30 | 0.26 | -0.11 (0.133) | -0.11 (0.141) | 0.35 |
| 1.0 | 10 | 0.35 | 0.38 | 0.34 | 0.33 | -0.03 (0.617) | -0.06 (0.426) | 0.36 |

### temporal.world_drift

Staleness period (steps): 128; adaptive lag at slowest drift: 37.00 [23.00, 57.00] (n=10)

| severity | period | success none | aif_fixed | aif_adaptive | ost | aif_adaptive − none (p) | ost − none (p) | acc aif_adaptive |
|---|---|---|---|---|---|---|---|---|
| 0.25 | 128 | 0.38 | 0.53 | 0.49 | 0.37 | 0.06 (0.414) | -0.04 (0.707) | 0.60 |
| 0.5 | 55 | 0.35 | 0.51 | 0.48 | 0.39 | 0.09 (0.328) | 0.01 (0.977) | 0.60 |
| 0.75 | 23 | 0.37 | 0.53 | 0.50 | 0.41 | 0.09 (0.297) | 0.01 (0.945) | 0.66 |
| 1.0 | 10 | 0.40 | 0.48 | 0.51 | 0.36 | 0.06 (0.254) | -0.07 (0.219) | 0.66 |

## History re-entry

| severity | n | Δ success_rec aif_adaptive (react − remove) | Δ ost | Δ pattern recurrence | migration destination gain |
|---|---|---|---|---|---|
| 0.25 | 10 | -0.04 [-0.14, 0.05] p=0.344 | 0.01 [-0.07, 0.11] p=0.844 | 0.01 [-0.04, 0.04] p=0.938 | -0.00 [-0.02, 0.01] p=0.691 |
| 0.5 | 10 | -0.04 [-0.20, 0.13] p=0.631 | 0.06 [-0.01, 0.13] p=0.195 | 0.02 [-0.03, 0.07] p=0.500 | 0.01 [-0.03, 0.06] p=0.510 |
| 0.75 | 10 | -0.03 [-0.10, 0.04] p=0.496 | 0.03 [-0.04, 0.10] p=0.508 | 0.01 [-0.02, 0.03] p=0.750 | 0.00 [-0.01, 0.02] p=0.609 |
| 1.0 | 10 | -0.03 [-0.10, 0.03] p=0.375 | -0.02 [-0.08, 0.05] p=0.645 | -0.01 [-0.02, 0.00] p=0.125 | -0.01 [-0.02, -0.00] p=0.035 |

## Non-redundancy (element × regime; capabilities where NON-REDUNDANT / HARMFUL)

| element | regime | status | non-redundant for | harmful for |
|---|---|---|---|---|
| agent | AIF | NON-REDUNDANT | prediction | perturbation_localisation |
| agent | POST | UNRESOLVED | — | — |
| agent | REF | UNRESOLVED | — | — |
| agent | TRANS | UNRESOLVED | — | — |
| boundary | AIF | NON-REDUNDANT | intervention, recovery, perturbation_localisation, history_reuse | prediction |
| boundary | POST | UNRESOLVED | — | prediction |
| boundary | REF | UNRESOLVED | — | — |
| boundary | TRANS | NON-REDUNDANT | intervention, recovery | prediction |
| boundary (model-light controller) | AIF | NON-REDUNDANT | intervention, recovery | — |
| boundary (model-light controller) | POST | NON-REDUNDANT | recovery | — |
| boundary (model-light controller) | REF | UNRESOLVED | — | — |
| boundary (model-light controller) | TRANS | NON-REDUNDANT | intervention, recovery | — |
| expected_free_energy | AIF | UNRESOLVED | — | — |
| expected_free_energy | POST | UNRESOLVED | — | — |
| expected_free_energy | REF | UNRESOLVED | — | — |
| expected_free_energy | TRANS | UNRESOLVED | — | — |
| free_energy | AIF | UNRESOLVED | — | — |
| free_energy | POST | UNRESOLVED | — | — |
| free_energy | REF | UNRESOLVED | — | — |
| free_energy | TRANS | UNRESOLVED | — | — |
| latent_state | AIF | UNRESOLVED | — | — |
| latent_state | POST | UNRESOLVED | — | — |
| latent_state | REF | UNRESOLVED | — | — |
| latent_state | TRANS | UNRESOLVED | — | — |
| model | AIF | NON-REDUNDANT | recovery | perturbation_localisation |
| model | POST | UNRESOLVED | — | — |
| model | REF | UNRESOLVED | — | — |
| model | TRANS | NON-REDUNDANT | recovery | — |
| policy | AIF | NON-REDUNDANT | prediction, intervention, recovery, history_reuse | perturbation_localisation |
| policy | POST | UNRESOLVED | — | — |
| policy | REF | UNRESOLVED | — | — |
| policy | TRANS | NON-REDUNDANT | intervention, recovery | structural_transition_detection |
| prediction_error | AIF | UNRESOLVED | — | — |
| prediction_error | POST | NON-REDUNDANT | prediction | — |
| prediction_error | REF | UNRESOLVED | — | — |
| prediction_error | TRANS | NON-REDUNDANT | prediction | — |

Tests: 192 (Holm); margin ±0.05.

## Failures

```
{
 "simulator_failure": 0,
 "numerical_failure": 0,
 "benchmark_failure": 0,
 "comparator_failure": 0,
 "model_structure_failure": 0,
 "controller_failure": 694,
 "genuine_regime_transition": 453
}
```

## C_AIF crossings (severity; bootstrap 95 % CI; share of seeds crossing)

| perturbation | crosses 0.8 at | CI | seeds | crosses 0.5 at | CI | seeds |
|---|---|---|---|---|---|---|
| boundary.delayed_update | — | None | 0.10 | — | None | 0.00 |
| boundary.disappearance | 0.92 | [0.85, 0.99] | 0.70 | — | None | 0.10 |
| boundary.fragmentation | 0.80 | [0.65, 0.97] | 0.80 | — | None | 0.10 |
| boundary.leakage | 0.72 | [0.64, 0.81] | 1.00 | — | None | 0.00 |
| boundary.merge | 0.20 | [0.15, 0.31] | 1.00 | — | None | 0.20 |
| boundary.noise | — | None | 0.20 | — | None | 0.00 |
| boundary.reassignment | 0.18 | [0.14, 0.36] | 1.00 | 0.90 | [0.84, 0.98] | 0.70 |
| coupling.asymmetric | — | None | 0.10 | — | None | 0.00 |
| coupling.cross_cluster | — | None | 0.00 | — | None | 0.00 |
| coupling.reversal | 0.83 | [0.47, 0.98] | 0.70 | — | None | 0.00 |
| coupling.strengthening | — | None | 0.00 | — | None | 0.00 |
| coupling.temporary_decoupling | — | [0.88, 1.0] | 0.50 | — | None | 0.00 |
| coupling.weakening | 0.63 | [0.57, 0.7] | 1.00 | — | None | 0.00 |
| memory.access_block | — | None | 0.00 | — | None | 0.00 |
| memory.deletion | — | None | 0.00 | — | None | 0.00 |
| memory.history_reactivation | — | None | 0.00 | — | None | 0.00 |
| memory.history_removal | — | None | 0.00 | — | None | 0.00 |
| memory.migration | — | None | 0.10 | — | None | 0.00 |
| memory.truncation | — | None | 0.10 | — | None | 0.00 |
| sensor.delay | 0.10 | [0.09, 0.12] | 1.00 | 0.26 | [0.22, 0.31] | 1.00 |
| sensor.dropout | 0.77 | [0.7, 0.8] | 1.00 | 0.86 | [0.84, 0.88] | 1.00 |
| sensor.noise | 0.42 | [0.39, 0.45] | 1.00 | — | [0.89, 1.0] | 0.40 |
| sensor.partial_observability | — | [0.92, 1.0] | 0.30 | — | None | 0.10 |
| sensor.permutation | — | None | 0.00 | — | None | 0.00 |
| sensor.reassignment | 0.49 | [0.36, 0.74] | 1.00 | 0.83 | [0.67, 0.9] | 0.90 |
| sensor.scale_mismatch | — | None | 0.00 | — | None | 0.00 |
| sensor.window_mismatch | 0.79 | [0.69, 0.84] | 1.00 | — | [0.92, 1.0] | 0.30 |
| structural.cut_reconnect | 0.84 | [0.7, 0.98] | 0.70 | — | None | 0.00 |
| structural.disconnection | 0.92 | [0.73, 0.99] | 0.60 | — | None | 0.00 |
| structural.multi_cluster_reorganization | — | None | 0.20 | — | None | 0.00 |
| temporal.asynchronous | 0.63 | [0.61, 0.65] | 1.00 | 0.82 | [0.81, 0.83] | 1.00 |
| temporal.horizon_compression | — | None | 0.00 | — | None | 0.00 |
| temporal.horizon_expansion | — | None | 0.10 | — | None | 0.00 |
| temporal.interface_drift | 0.07 | [0.07, 0.07] | 1.00 | 0.18 | [0.18, 0.19] | 1.00 |
| temporal.world_drift | — | None | 0.00 | — | None | 0.00 |
| topology.cluster_merge | 0.60 | [0.53, 0.64] | 1.00 | — | None | 0.10 |
| topology.cluster_split | — | None | 0.10 | — | None | 0.00 |
| topology.dynamic_mutation | — | [0.91, 1.0] | 0.30 | — | None | 0.00 |
| topology.edge_addition | — | None | 0.00 | — | None | 0.00 |
| topology.edge_deletion | — | [0.85, 1.0] | 0.30 | — | None | 0.00 |
| topology.hub_removal | — | None | 0.10 | — | None | 0.00 |
| topology.rerouting | — | [0.82, 1.0] | 0.40 | — | None | 0.00 |
| variable.deletion | 0.79 | [0.78, 0.8] | 1.00 | 0.87 | [0.86, 0.88] | 1.00 |
| variable.duplication | — | None | 0.00 | — | None | 0.00 |
| variable.outcome_merge | — | [0.7, 1.0] | 0.40 | — | None | 0.00 |
| variable.relabel | 0.80 | [0.42, 0.96] | 0.70 | — | [0.95, 1.0] | 0.60 |
| variable.remap | 0.44 | [0.37, 0.5] | 0.70 | — | None | 0.00 |

