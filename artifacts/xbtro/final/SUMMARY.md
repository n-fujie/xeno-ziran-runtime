# XB-TRO final records — summary

Generated from the stored records by `summarize_xbtro_final.py`. Every number below is read from a record.

## Index

| name | record | digest (12) | seeds | negative results | seconds | commit |
|---|---|---|---|---|---|---|
| A_standard | xb-a-bcea40306ec6 | bcea40306ec6 | 5000..5011 | 6 | 2.3 | f10a53fd67 |
| B_standard | xb-b-c53f1e3b769f | c53f1e3b769f | 5000..5011 | 20 | 29.7 | f10a53fd67 |
| C_standard | xb-c-06072890cfd9 | 06072890cfd9 | 5000..5011 | 14 | 18.4 | f10a53fd67 |
| D_standard | xb-d-f96899506f2d | f96899506f2d | 5000..5011 | 13 | 6.7 | f10a53fd67 |
| E_standard | xb-e-4a0fd16addbe | 4a0fd16addbe | 5000..5011 | 18 | 4.8 | f10a53fd67 |
| F_standard | xb-f-9208dab23942 | 9208dab23942 | 5000..5011 | 1 | 20.9 | f10a53fd67 |
| G_standard | xb-g-1da4c7f8e5e2 | 1da4c7f8e5e2 | 5000..5011 | 7 | 126 | f10a53fd67 |
| M_standard | xb-m-bea03229da51 | bea03229da51 | 5000..5011 | 5 | 11.8 | f10a53fd67 |
| R_standard | xb-r-c21ef3036b78 | c21ef3036b78 | 5000..5011 | 39 | 88.5 | f10a53fd67 |
| S_standard | xb-s-eb2910e1593f | eb2910e1593f | 5000..5011 | 5 | 13.9 | f10a53fd67 |
| V_standard | xb-v-d8bf067d22e3 | d8bf067d22e3 | 5000..5011 | 0 | 71.7 | f10a53fd67 |
| G_original_conditions | xb-g-23f06737f018 | 23f06737f018 | 5000..5007 | 2 | 28.1 | f10a53fd67 |
| G_independent_replication | xb-g-43505057a32a | 43505057a32a | 7000..7015 | 6 | 98.8 | f10a53fd67 |
| B_band_13mm | xb-b-68a347c760c2 | 68a347c760c2 | 5000..5011 | 18 | 16.3 | f10a53fd67 |
| D_band_13mm | xb-d-320ccb2795e3 | 320ccb2795e3 | 5000..5011 | 13 | 6.7 | f10a53fd67 |

## Numerical verification (record V)

### A-priori stability of the passive plant (human-like-planar)

| preset | integrator | co-contraction | control dt s | plant substeps | spectral radius of the step matrix | passive plant | max |lambda| h | condition number of M |
|---|---|---|---|---|---|---|---|---|
| human-like-planar | rk4 | 0 | 0.01 | 2 | 0.999 | stable | 1.28 | 227 |
| human-like-planar | rk4 | 0.3 | 0.01 | 2 | 0.999 | stable | 1.67 | 227 |
| human-like-planar | rk4 | 0.9 | 0.01 | 2 | 0.998 | stable | 2.46 | 227 |
| human-like-planar | semi-implicit-euler | 0 | 0.01 | 2 | 0.999 | stable | 1.28 | 227 |
| human-like-planar | semi-implicit-euler | 0.3 | 0.01 | 2 | 0.999 | stable | 1.67 | 227 |
| human-like-planar | semi-implicit-euler | 0.9 | 0.01 | 2 | 1.77 | UNSTABLE | 2.46 | 227 |
| human-like-planar | explicit-euler | 0 | 0.01 | 2 | 0.999 | stable | 1.28 | 227 |
| human-like-planar | explicit-euler | 0.3 | 0.01 | 2 | 0.999 | stable | 1.67 | 227 |
| human-like-planar | explicit-euler | 0.9 | 0.01 | 2 | 1.46 | UNSTABLE | 2.46 | 227 |

### Time-step and integrator convergence, noiseless (human-like-planar)

| variant | plant step s | RMS COM diff m | max COM diff m | state |
|---|---|---|---|---|
| RK4, 1 plant sub-step(s) | 0.01 | — | — | refused: the explicit RK4 step is numerically unstable for the passive joint dynamics (pl |
| RK4, 2 plant sub-step(s) | 0.005 | 2.35e-05 | 9.32e-05 | ok |
| RK4, 4 plant sub-step(s) | 0.0025 | 2.35e-07 | 6.54e-07 | ok |
| semi-implicit-euler, 2 plant sub-step(s) | 0.005 | — | — | refused by the stability check: the explicit RK4 step is numerically unstable for the passiv |
| explicit-euler, 2 plant sub-step(s) | 0.005 | — | — | refused by the stability check: the explicit RK4 step is numerically unstable for the passiv |
| RK4, control step halved | 0.0025 | 0.000518 | 0.00132 | ok |
| RK4, 1 plant sub-step (refused by the check; forced to run, 4 seeds) | 0.01 | — | — | check (cc up to 0.9): unstable, rho=12.84; nominal co-contraction run: diverged 0/4, fell 0/4; co-contraction 0.9 run: diverged 4/4, fell 0/4 |
| semi-implicit Euler (refused by the check; forced to run, 4 seeds) | 0.005 | — | — | check (cc up to 0.9): unstable, rho=1.77; nominal co-contraction run: diverged 0/4, fell 0/4; co-contraction 0.9 run: diverged 4/4, fell 0/4 |
| explicit Euler (refused by the check; forced to run, 4 seeds) | 0.005 | — | — | check (cc up to 0.9): unstable, rho=1.46; nominal co-contraction run: diverged 0/4, fell 0/4; co-contraction 0.9 run: diverged 0/4, fell 4/4 |

### A-priori stability of the passive plant (machine-like-planar)

| preset | integrator | co-contraction | control dt s | plant substeps | spectral radius of the step matrix | passive plant | max |lambda| h | condition number of M |
|---|---|---|---|---|---|---|---|---|
| machine-like-planar | rk4 | 0 | 0.005 | 2 | 1 | stable | 0.221 | 471 |
| machine-like-planar | rk4 | 0.3 | 0.005 | 2 | 1 | stable | 0.279 | 471 |
| machine-like-planar | rk4 | 0.9 | 0.005 | 2 | 1 | stable | 0.367 | 471 |
| machine-like-planar | semi-implicit-euler | 0 | 0.005 | 2 | 1 | stable | 0.221 | 471 |
| machine-like-planar | semi-implicit-euler | 0.3 | 0.005 | 2 | 1 | stable | 0.279 | 471 |
| machine-like-planar | semi-implicit-euler | 0.9 | 0.005 | 2 | 1 | stable | 0.367 | 471 |
| machine-like-planar | explicit-euler | 0 | 0.005 | 2 | 1 | stable | 0.221 | 471 |
| machine-like-planar | explicit-euler | 0.3 | 0.005 | 2 | 1 | stable | 0.279 | 471 |
| machine-like-planar | explicit-euler | 0.9 | 0.005 | 2 | 1 | stable | 0.367 | 471 |

### Time-step and integrator convergence, noiseless (machine-like-planar)

| variant | plant step s | RMS COM diff m | max COM diff m | state |
|---|---|---|---|---|
| RK4, 1 plant sub-step(s) | 0.005 | 2.83e-08 | 6.46e-08 | ok |
| RK4, 2 plant sub-step(s) | 0.0025 | 1.7e-09 | 3.88e-09 | ok |
| RK4, 4 plant sub-step(s) | 0.00125 | 9.75e-11 | 2.23e-10 | ok |
| semi-implicit-euler, 2 plant sub-step(s) | 0.0025 | 4.79e-05 | 0.000114 | ok |
| explicit-euler, 2 plant sub-step(s) | 0.0025 | 4.21e-05 | 0.000162 | ok |
| RK4, control step halved | 0.00125 | 3.87e-05 | 0.000144 | ok |

### Eight conditions x two presets x two protocols

| preset | protocol | condition | fell (physical) | diverged (numerical) | max COM m | recovered in window | settled after turn | state |
|---|---|---|---|---|---|---|---|---|
| human | default | no disturbance | 0 | 0 | 0.0488 | 0 | 1 | ok |
| human | default | small disturbance (25 N, extra push) | 0 | 0 | 0.0574 | 0 | 1 | ok |
| human | default | large disturbance (120 N, extra push) | 1 | 0 | 0.414 | 0 | 0 | ok |
| human | default | control delay +0.06 s | 1 | 0 | 0.416 | 0 | 0 | ok |
| human | default | resource constraint 0.7 | 0 | 0 | 0.0489 | 0 | 1 | ok |
| human | default | sensor noise x4 | 0 | 0 | 0.0488 | 0 | 1 | ok |
| human | default | contact condition 0.5 | 0 | 0 | 0.0459 | 0 | 1 | ok |
| human | default | control time step halved | 0 | 0 | 0.0523 | 0 | 1 | ok |
| human | short | no disturbance | 0 | 0 | 0.0619 | 0.583 | 1 | ok |
| human | short | small disturbance (25 N, extra push) | 0 | 0 | 0.0662 | 0.333 | 1 | ok |
| human | short | large disturbance (120 N, extra push) | 1 | 0 | 0.415 | 0 | 0 | ok |
| human | short | control delay +0.06 s | 0 | 0 | 0.337 | 0 | 0 | ok |
| human | short | resource constraint 0.7 | 0 | 0 | 0.0619 | 0.583 | 1 | ok |
| human | short | sensor noise x4 | 0 | 0 | 0.0727 | 0.0833 | 1 | ok |
| human | short | contact condition 0.5 | 0 | 0 | 0.0619 | 0.75 | 1 | ok |
| human | short | control time step halved | 0 | 0 | 0.0597 | 0.583 | 1 | ok |
| machi | default | no disturbance | 0 | 0 | 0.0393 | 0 | 1 | ok |
| machi | default | small disturbance (25 N, extra push) | 0 | 0 | 0.0439 | 0 | 1 | ok |
| machi | default | large disturbance (120 N, extra push) | 1 | 0 | 0.339 | 0 | 0 | ok |
| machi | default | control delay +0.06 s | 1 | 0 | 0.339 | 0 | 0 | ok |
| machi | default | resource constraint 0.7 | 0 | 0 | 0.0393 | 0 | 1 | ok |
| machi | default | sensor noise x4 | 0 | 0 | 0.039 | 0 | 1 | ok |
| machi | default | contact condition 0.5 | 0 | 0 | 0.0393 | 0 | 1 | ok |
| machi | default | control time step halved | 0 | 0 | 0.039 | 0 | 1 | ok |
| machi | short | no disturbance | 0 | 0 | 0.0471 | 1 | 1 | ok |
| machi | short | small disturbance (25 N, extra push) | 0 | 0 | 0.0525 | 1 | 1 | ok |
| machi | short | large disturbance (120 N, extra push) | 1 | 0 | 0.339 | 0 | 0 | ok |
| machi | short | control delay +0.06 s | 1 | 0 | 0.338 | 0 | 0 | ok |
| machi | short | resource constraint 0.7 | 0 | 0 | 0.0471 | 1 | 1 | ok |
| machi | short | sensor noise x4 | 0 | 0 | 0.0467 | 1 | 1 | ok |
| machi | short | contact condition 0.5 | 0 | 0 | 0.0471 | 1 | 1 | ok |
| machi | short | control time step halved | 0 | 0 | 0.0472 | 1 | 1 | ok |

## B — couplings

classes: {'correlational-only': 5, 'interventionally-supported': 3, 'untested': 2}


## C — Fragility Transfer matrix

seeds 12; design: with 12 paired seeds an effect of about 0.81 (standardised, paired) is detectable with 80% power at the 0.05 level; smaller true effects are expected to be missed, so 'no detectable effect' is not 'no effect'

transfers:

- **lower-abdominal-continuity**: improved ['posture_stability', 'turn_speed']; weakened ['correction_quality', 'recovery_time']
- **whole-skin-sensing**: improved ['turn_speed', 'precision', 'recovery_time']; weakened ['correction_quality']
- **axis-maintenance**: improved ['turn_speed']; weakened ['correction_quality', 'recovery_time']
- **endpoint-removal**: improved ['turn_speed', 'precision']; weakened ['correction_quality', 'fatigue_cost']
- **low-noise-movement**: improved ['correction_quality']; weakened ['turn_speed', 'precision']
- **minimal-approach-distance**: improved ['turn_speed', 'precision']; weakened ['correction_quality', 'recovery_time']
- **zero-run-up-transition**: improved ['turn_speed', 'precision']; weakened ['correction_quality', 'fatigue_cost']
- **slow-movement**: improved ['correction_quality']; weakened ['turn_speed', 'precision', 'fatigue_cost']
- **breathing-synchronization**: improved ['posture_stability', 'turn_speed', 'precision', 'recovery_time']; weakened ['correction_quality']

negative / null results: 14

## G — directional Fragility Transfer

seeds 12; design: with 12 paired seeds an effect of about 0.81 (standardised, paired) is detectable with 80% power at the 0.05 level; smaller true effects are expected to be missed, so 'no detectable effect' is not 'no effect'

transfers:

- **lower-abdominal-continuity**: improved ['correction_latency', 'peak_dev_forward', 'posture_sway', 'turn_settling_after_push']; weakened ['energy_beyond_declared']
- **whole-skin-sensing**: improved ['turn_settling_after_push']; weakened ['peak_dev_forward']
- **axis-maintenance**: improved ['correction_latency', 'turn_settling_after_push']; weakened ['energy_beyond_declared', 'line_conflicts', 'peak_dev_forward', 'recovery_region']
- **endpoint-removal**: improved ['line_conflicts', 'turn_settling_after_push']; weakened ['energy_beyond_declared']
- **low-noise-movement**: improved ['energy_beyond_declared', 'peak_dev_forward']; weakened ['turn_settling_after_push']
- **minimal-approach-distance**: improved ['correction_latency', 'peak_dev_forward', 'turn_settling_after_push']; weakened ['energy_beyond_declared', 'line_conflicts']
- **zero-run-up-transition**: improved ['line_conflicts', 'turn_settling_after_push']; weakened ['energy_beyond_declared']

negative / null results: 7

## G — independent replication (16 seeds, seeds 7000..)

seeds 16; design: with 16 paired seeds an effect of about 0.70 (standardised, paired) is detectable with 80% power at the 0.05 level; smaller true effects are expected to be missed, so 'no detectable effect' is not 'no effect'

transfers:

- **lower-abdominal-continuity**: improved ['correction_latency', 'line_conflicts', 'peak_dev_forward', 'posture_sway', 'turn_settling_after_push']; weakened ['energy_beyond_declared']
- **whole-skin-sensing**: improved ['turn_settling_after_push']; weakened ['peak_dev_forward']
- **endpoint-removal**: improved ['line_conflicts', 'turn_settling_after_push']; weakened ['energy_beyond_declared']
- **low-noise-movement**: improved ['energy_beyond_declared', 'peak_dev_forward']; weakened ['turn_settling_after_push']
- **minimal-approach-distance**: improved ['correction_latency', 'peak_dev_forward', 'turn_settling_after_push']; weakened ['energy_beyond_declared', 'line_conflicts']
- **zero-run-up-transition**: improved ['line_conflicts', 'turn_settling_after_push']; weakened ['energy_beyond_declared']
- **narrow-step-balance**: improved ['turn_settling_after_push']; weakened ['recovery_region']
- **fingertip-tension**: improved ['peak_dev_forward', 'posture_sway', 'turn_settling_after_push']; weakened ['energy_beyond_declared']

negative / null results: 6

## Axis-maintenance: the first report and its independent re-verification

First report (8 seeds, seeds 5000.., four principles, ablation) and replication (16 seeds, seeds 7000.., all fourteen principles). Mean effects (condition minus control; lower is better) and the share due to the rule line (against the ablation).

| run | measure | control mean | condition mean | difference | d | q (BH) | label | due to the rule line |
|---|---|---|---|---|---|---|---|---|
| first report | peak_dev_forward | 0.036 | 0.049 | 0.0131 | 1.48 | 0.0375 | worsened | 0.0131 |
| first report | recovery_region | 1 | 3.12 | 2.12 | 3.32 | 0.0375 | worsened | 2.12 |
| first report | tolerance_forward | 0 | 0 | 0 | 0 | 1 | no detectable effect | 0 |
| first report | tolerance_backward | 1 | 1 | 0 | 0 | 1 | no detectable effect | 0 |
| first report | correction_latency | 0.159 | 0.136 | -0.0225 | -1.42 | 0.0625 | no detectable effect | -0.0225 |
| first report | turn_settling_after_push | 1.5 | 0.734 | -0.764 | -17 | 0.0375 | improved | -0.764 |
| replication | peak_dev_forward | 0.0356 | 0.0481 | 0.0125 | 1.06 | 0.00432 | worsened | 0.0125 |
| replication | recovery_region | 1.06 | 3.44 | 2.38 | 2.18 | 0.00124 | worsened | 2.38 |
| replication | tolerance_forward | 0 | 0 | 0 | 0 | 1 | no detectable effect | 0 |
| replication | tolerance_backward | 1 | 1 | 0 | 0 | 1 | no detectable effect | 0 |
| replication | correction_latency | 0.129 | 0.109 | -0.0206 | -0.772 | 0.021 | no detectable effect | -0.0206 |
| replication | turn_settling_after_push | 1.49 | 1.15 | -0.336 | -0.566 | 0.142 | no detectable effect | -0.336 |

Reading (computed from the labels above):

- peak push deviation (weakening): first report 'worsened', replication 'worsened' — replicated
- recovery region (weakening): first report 'worsened', replication 'worsened' — replicated
- settling after the later direction change (improvement): first report 'improved', replication 'no detectable effect' — NOT replicated
- correction latency (improvement): first report 'no detectable effect', replication 'no detectable effect' — replicated

## R — sensitivity of the Fragility Transfer matrix

cells: 98; identical label in every variant: 59; transfers in every variant: ['breathing-synchronization', 'endpoint-removal', 'zero-run-up-transition']; in some variants only: ['axis-maintenance', 'low-noise-movement', 'lower-abdominal-continuity', 'minimal-approach-distance', 'narrow-step-balance', 'slow-movement', 'tensegrity', 'whole-skin-sensing']

## D — operational velocity (baseline)

| measure | unit | fraction defined | mean | estimable from observations |
|---|---|---|---|---|
| sensory_detection | s | 1 | 0.12 | no |
| neural_response | s | 1 | 0.12 | yes |
| muscle_onset | s | 1 | 0.124 | yes |
| movement_onset | s | 1 | 0.766 | no |
| correction | s | 1 | 0.263 | yes |
| settling | s | 1 | 1.49 | yes |
| adaptation | 1/trial | 1 | 0.0128 | no |
| recovery | s | 0.583 | 1.28 | no |
| reconfiguration | rounds / s | 0 | — | no |
| consequence | s | 1 | 0.881 | no |

## F — human-like vs machine-like

strongest push recovered (50 % of seeds): {'human-like-planar': 40.0, 'machine-like-planar': 80.0}

| push N | human-like | machine-like |
|---|---|---|
| 20 | 1 | 1 |
| 40 | 0.667 | 1 |
| 60 | 0.25 | 1 |
| 80 | 0 | 1 |
| 100 | 0 | 0.167 |
| 130 | 0 | 0 |
| 160 | 0 | 0 |

## S — paths for 'reach-target'

| path | latency s | energy | info gain | reach s | lines changed | recovery s | fall | non-dominated |
|---|---|---|---|---|---|---|---|---|
| all lines (baseline) | 0.881 | 0.102 | 0 | 0.124 | 0 | 1.9 | 0 | 1 |
| without the hip balance line | 0.871 | 0.0882 | 5 | 0.124 | 1 | 2 | 0 | 1 |
| without the reflex line | 0.863 | 0.101 | 6 | 0.124 | 1 | 2 | 0 | 1 |
| Xeno-14: zero-run-up transition | 0.492 | 0.106 | 6 | 0.127 | 2 | 1.82 | 0 | 1 |
| Xeno-14: endpoint removal | 0.51 | 0.107 | 3 | 0.128 | 2 | 1.86 | 0 | 0 |
| Xeno-14: slow movement | 0.91 | 0.104 | 5 | 0.124 | 2 | 1.85 | 0 | 1 |
| stop: the response to the cue is switched off | — | 0.0708 | 5 | 0.188 | 2 | 2 | 0 | 1 |

## S — paths for 'stay-upright'

| path | latency s | energy | info gain | reach s | lines changed | recovery s | fall | non-dominated |
|---|---|---|---|---|---|---|---|---|
| all lines (baseline) | 1.59 | 0.102 | 0 | 0.223 | 0 | 1.9 | 0 | 1 |
| without the hip balance line | — | 0.0882 | 5 | 0.269 | 1 | 2 | 0 | 1 |
| without the reflex line | — | 0.101 | 6 | 0.257 | 1 | 2 | 0 | 1 |
| Xeno-14: zero-run-up transition | 1.58 | 0.106 | 6 | 0.108 | 2 | 1.82 | 0 | 1 |
| Xeno-14: endpoint removal | 1.57 | 0.107 | 3 | 0.126 | 2 | 1.86 | 0 | 1 |
| Xeno-14: slow movement | 1.56 | 0.104 | 5 | 0.232 | 2 | 1.85 | 0 | 1 |
| stop: the response to the cue is switched off | — | 0.0708 | 5 | 0.146 | 2 | 2 | 0 | 1 |

selection under stated constraints: {'reach-target': 'Xeno-14: zero-run-up transition', 'stay-upright': 'Xeno-14: slow movement'}

## E — adaptive observation

| hidden change | differences that exist | identified at the start (motion only) | identified after revision | rounds that changed the configuration | set-up time s | still unobserved, by reason |
|---|---|---|---|---|---|---|
| mixed | 10 | 2 | 5 | 4 | 110 | unobserved:device-mismatch=3 |
| delay-only | 6 | 1 | 5 | 4 | 160 |  |
| tone-only | 5 | 2 | 4 | 4 | 120 |  |
| fatigue-only | 2 | 1 | 1 | 4 | 120 |  |

## M — MO-style policy

stopped because: round limit; rounds: [(1, 'retracted: no measured gain, so the set-'), (2, 'retracted: no measured gain, so the set-'), (3, 'kept'), (4, 'retracted: the apparatus changes the bod')]

## A — identifiability by observation configuration

| configuration | existing differences | identified | identifiability | unobserved reasons |
|---|---|---|---|---|
| motion only | 10 | 2 | 0.2 | unobserved:device-mismatch=5; unobserved:unmeasured=1 |
| motion + EMG-like + contact | 10 | 6 | 0.6 | unobserved:device-mismatch=1 |
| dynamic (after reconfiguration) | 10 | 5 | 0.5 | unobserved:device-mismatch=3 |

## Tolerance band sensitivity (human-like 9 mm registered vs 13 mm)

| experiment | band | measure | value |
|---|---|---|---|
| B | 9 mm (registered) | control recovery time (restricted mean, s) | 1.58 |
| B | 13 mm | control recovery time (restricted mean, s) | 0.89 |
| D | 9 mm (registered) | recovery: fraction of seeds defined / mean s | 0.583 / 1.28 |
| D | 13 mm | recovery: fraction of seeds defined / mean s | 1 / 0.89 |
