# Shared ARDS–HPO environment (`env3`, kind `shared-oi`) — design record

**A new environment, defined in this repository.** Earlier notes mentioned an "Environment 3" as a proposal; no specification existed. This one
lives in `backend/xzr/study/shared/` (own namespace), changes no ARDS environment, and writes nothing into the ARDS repository
(`pa-simulation-environment`, whose Phase 3 frozen assets — 1,526 files — and Phase 4 records are not read for results and not written).

## The task (ARDS's question on the runtime world)

Which differences between a baseline system and an altered system can an observer identify under an observation configuration, and how
should the configuration be revised to identify more? The system is this runtime's world, observed through the HPO instruments
(`xzr.hpo.Instruments`): channels `activity, tension, memory, recursion, structure, boundary_flow` at hierarchy levels 0–3 (flow up to 2).

* presets: `intermittent`, `sparse` (two worlds; seeds change the exogenous / endogenous streams); 400 configurations, 40 warm-up steps, 16 recorded steps;
* alterations: `input-shift` (input ×2.5), `coupling-shift` (connection weights ×0.3), `retention-shift` (retention ×0.92), `threshold-shift` (thresholds ×1.15);
* twelve differences (features), each readable through one channel at a minimum scale, a maximum sampling period and a minimum window; the reason a difference
  is not observable is named in ARDS's vocabulary (`device-mismatch`, `unmeasured`, `scale-mismatch`, `time-window-mismatch`, `boundary-invisible`);
* an observation of one configuration for n seeds gives, per difference, the paired effect d_z and p; *identified* iff p < 0.01 and |d_z| ≥ 0.8;
* ground truth (evaluation only): 64 reference seeds, ideal configuration (every channel, finest scale, finest sampling, no noise, whole record); a difference
  *exists* iff |d_z| ≥ 0.5 and p < 0.001. It is cached on disk, a function of the definition alone (`oi_world.definition_digest()`).

Structure that makes the task informative (checked in `tests/test_study_shared.py`): the start configuration (activity, tension, memory at macro scale)
identifies only some existing differences; `coupling-shift` exists only in the structure channel at local scale (invisible to the start configuration, then
*capable but not identified* when the channel is added at noise 1, *identified* when the noise is also lowered): invisibility is not absence, and visibility
can need more than one revision. The instrument's sampling period gates capability only, as in `xzr.hpo.observe`.

## Who can do what (`shared/ops.py`)

Shared by every arm, in one vocabulary: observe, add a channel, lower noise, raise the sampling rate, raise the resolution, change the window, query the
capability model. Arm-internal: external memory, history re-injection, revision of the arm's own rules. **Not available** (named, never assumed): variable
generation, boundary change, intervention, evaluation change. The access matrix per arm is part of the fairness record of a study and is shown in the UI.

## Arms

* ARDS's own arms (EXISTING-blind, V2-PA, V2-PA-no-reinjection, FIXED-noise, V1-A, …) run **unchanged** through `vite-node` against a TypeScript service
  (`ards_bridge/zrs_oi.ts`) that talks to the Python worker (`shared/oi_worker.py`). The frozen Phase 3 arms run through ARDS's own vocabulary adapter.
* The HPO arm (`shared/hpo_arm.py`) is the HPO-003 *policy* — reasons for blindness → instrument changes (a one-epoch bundle plus single rules), a reachability
  record per adopted change, optional meta-revision of the policy's rule parameters (`hpo.metarevision` with its own `RuleSpec`) — with the same budgets (72 body
  runs: 8 selection + 4 validation seeds × 3 cycles; set-up 480 s minus the start configuration), the same five revision operations, the same adoption
  discipline (try against the control on the same data, adopt on a gain without loss, confirm on fresh seeds), the observer's view only (a test checks that
  the module never touches the ground truth) and an independent re-derivation of its record (`hpo_arm.verify`). It is **not** the HPO field of operations.
* Every arm's final configuration is scored by **ARDS's own** held-out code (`evaluateHeldOut2`, `ards_eval.ts`) on the same service.

## What the comparison can and cannot say

The ARDS rules (R1–R4) and the HPO rule table are close in structure — both map blindness reasons to instrument changes — so the shared environment measures
the differences between these policies (and between history on / off, meta-revision on / off), not between "ARDS" and "HPO" as whole systems. Profiles list
the dimensions in which two arms differ (`proposal_policy`, `history_reinsertion`, `meta_revision`, …); a difference a contrast does not declare is flagged.
Only ARDS software-test replicates (3980–3989) are used, so every shared study is a functional check by construction.

## Verification

* bridge vs ARDS building blocks (`ards-equivalence`): identical metrics and verification for EXISTING-blind, V2-PA, V2-PA-no-reinjection, FIXED-noise and
  V1-A on **env1** (records `docs/study/ards_equivalence_env1_3980.json`) and on **env3** (`…env3_3980.json`);
* determinism of the world, the observation and the HPO arm; the worker's strict-JSON protocol; the doctored-record checks of `hpo_arm.verify`.
