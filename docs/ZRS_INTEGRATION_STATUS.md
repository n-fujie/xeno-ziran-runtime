# XENO ZIRAN SIMULATOR — integration status (branch `feat/zrs-integration`)

Working record of the integration. Updated with each increment. Everything here is a statement about the software and
its stored records; nothing is a claim about Strong Xenoscience.

## 1. Baseline before any change (2026-10-22, base `cce36f6`, py3.12.13 / numpy 2.5.3 / scipy 1.18.1)

| Suite | Result |
|---|---|
| `ziran-xeno-simulator` (TS) `node --test test/*.test.ts` | 73 / 73 pass; `tsc -p tsconfig.json` clean |
| `xeno-ziran-runtime` frontend `tsc -b` + `vitest run` | clean; 12 files / 82 tests pass |
| `xeno-ziran-runtime` backend `pytest` | 347 pass, 1 skipped, **2 fail** |

The two backend failures exist before any change here and are environment-caused, not regressions:

1. `test_compat.py::test_engine_conformance_against_the_golden_fixture[desktop-scipy]` — hierarchy digest differs on this
   platform (tie ordering by rounding noise on disconnected sub-graphs; diagnosis in the XB-TRO worktree, open item S11).
2. `test_lab.py::test_published_records_replay` (`m2-run-9100.json`) — the stored record does not replay here
   (digest differs from step 1). Checked at the commit that produced the record (`390c43f`, throwaway worktree): it fails
   there too, so the later M9 changes are not the cause; `XZR_FORCE_COMPAT=1` does not change it. Fresh records replay
   (see the multi-agent tests). The record's documented condition is "same machine, same software versions".
   Neither was fixed or regenerated: stored records are not edited.

## 2. What already exists in the code (verified by reading it, not by the capability report)

The capability report (`docs/SIMULATOR_CAPABILITY_REPORT.md`) describes the `lab-m8` checkout and understates this base.
On this base (`xzr/hpo`, `xzr/lab`) the following exist and are tested:

| Ziran-core item | Where | State |
|---|---|---|
| Observation / scale / time window / boundary (penetration) revision, with reasons | `hpo/observe.py`, `hpo/reconfig.py` (`SANDBOX`) | implemented; every change recorded in the causal history with before/after settings |
| Observation catalog change, resource allocation, evaluation order, coupling, history reinsertion, stopping rules | `hpo/reconfig.py` | implemented |
| Variable proposal / adoption | `hpo/reconfig.py` `_propose` | partial: one derived variable (`activity_trend`) implemented; `veil_coverage`, `conflict_density` are proposals marked "no implementation" |
| Variable generation by a system, adopted only against a matched control | `lab/science.py` (`generate_variables`, LOO rule) | implemented (lab systems) |
| External memory (store chamber; modes none / ordinary / contextual / shuffled / write_only) | `lab/science.py` | implemented |
| Sensor-head relocation, observation-window revision, parameter adaptation | `lab/science.py` | implemented (lab systems) |
| Layering | `tests/test_layering.py` | enforced |

## 3. Added in this branch

| Addition | Files | What it does | Tests |
|---|---|---|---|
| Reachability record | `xzr/hpo/reachability.py`, `Controller(trace_reachability=True)` | For each configuration change: which operations became runnable / blocked and which channels opened / closed, with the reason (static reasons only; `boundary_invisible` and `unmeasured` depend on the world and are not evaluated) | `tests/test_ziran_core.py` |
| Revision of revision rules | `xzr/hpo/metarevision.py`, `Controller(meta=MetaReviser())` | The controller's own rule parameters (penetration, allocation step, lag step) are revised when the change a rule made did not remove the blindness it targeted twice in a row; a rule at its bound is marked exhausted. Sandboxed bounds, every revision recorded with evidence. A revision is a proposal about the controller, not a validated improvement | `tests/test_ziran_core.py` |
| Populations of scientific systems | `xzr/lab/population.py` | Deterministic heterogeneous populations of 3 / 20 / 50 / 100 / 300 systems for the shared laboratory | `tests/test_ziran_multiagent.py` |

Both Controller options are off by default; with them off the controller's behaviour and trace are identical to before
(checked in `test_tracing_reachability_does_not_change_the_run` and `test_default_controller_uses_the_original_parameters`).

Staged load (60 steps, this machine, one process): 3 / 12 / 24 / 48 / 100 / 200 / 300 systems took 0.9 / 1.0 / 1.1 / 1.5 /
1.9 / 2.4 / 3.1 s with a peak of 124–145 MB. This is a scaling statement about the software. The number of systems is
not a measure of autonomy and is not used as one.

## 4. Not done yet (so not claimed)

- The ARDS arms do not run on this runtime (the proposed "Environment 3" adapter does not exist). ARDS stays in
  `pa-simulation-environment`; its Phase 3 frozen assets and Phase 4 constraints are untouched.
- No new service endpoint and no frontend view for the reachability records, rule revisions or populations; the
  existing 11 result views are unchanged.
- No effect test: whether revised rules or reachability-guided changes do better than fixed rules has not been measured
  (that would be a held-out paired comparison and needs its own protocol).
- Variable generation in the HPO controller is still limited to `activity_trend`.
- Save / reload / replay of a controller trace with the new fields has no record format yet.

## 5. Completion levels (assessed separately, not merged)

- **Level 1 (software):** not complete. New code is tested and the old suites are unchanged, but two baseline backend
  tests fail for environment reasons and the ARDS bridge, UI and API integration are missing.
- **Level 2 (Ziran operational):** not claimed. Observation / scale / window / boundary revision with recorded reasons and
  now reachability and rule-revision records exist; their effect on later research has not been measured.
- **Level 3 (strong xenoscience):** not claimed; the four conditions (human-energy independence, human-readability
  independence, self-reproduction, self-generation of variables / boundaries) are not demonstrated, and no experiment
  here bears on them.
