All of it was run on the final tree of the final commit (the Python code, the tests, the interface and the saved results were last changed before these runs; the document and its fragments are generated from the saved results and are checked by a test).

| check | result |
|---|---|
| backend `pytest` | whole suite, final run (`evidence/meos_stage6.junit.xml`): 804 tests, 802 passed, 2 failed (the two known failures below). One test (that the window file of the extension covers every tick to 1140) was put back after that run and was run with the five test files it touches (56 tests): it passes, so 805 tests, 803 passed, the same 2 failed |
| the two known failures | `tests/test_compat.py::test_engine_conformance_against_the_golden_fixture[desktop-scipy]` and `tests/test_lab.py::test_published_records_replay`: same names and same messages as at the baseline (`ec9667e`), at Stage 5 and at the first Stage 6 commit. Neither concerns MEOS-0 or Stage 6; they were not changed or skipped |
| frontend `vitest` | 276 tests, 0 failures, 0 errors (`evidence/frontend_stage6.junit.xml`) |
| `tsc -b`, `eslint`, `vite build` | no errors |
| `ruff`, `mypy` on the MEOS code (`xzr/meos`, `xzr/service/meos.py`, the Stage 6 scripts and tests) | no findings. The whole-repository run reports `ruff` and `mypy` findings in older modules (`hpo`, `study`, `totalobs`, `lab`, `experiments/results`) that this work does not touch; they are not caused by Stage 6 and were not fixed here |
| replay of the 264 stored runs | 264 / 264 agree on `meos-0.5` (`evidence/replay_meos_stage6.json`). The runs were not regenerated |
| baseline result digest | `b4cf1e522e8bee460eab30ee2a3f86ffd703a3f7969dc21271cf0240aa09adc5`, unchanged on `meos-0.5` (`tests/test_meos_stage5_engine.py`) |
| baseline trace digest | `bd3e588608139840831c2749b5051ac31a360d91c6a9a0131b9de3f0152ee1b7`, unchanged |
| Stage 5 reproduction (`reproduce_stage5_subset.py`), run on `meos-0.5` | identical: experiment L (history lost), F14 search and its digests, F8 search, F9 search, the first adaptive decisions, the Stage 4 strict nulls (Address collision, stale), the two digests |
| Stage 6 reproduction (`reproduce_stage6_subset.py`), run on `meos-0.5` | identical: 4250 / 4250 rows of the exploration grid, the per-tick window of the coupling pulse, 36 / 36 controller runs (`all_identical: true`) |
| stored MEOS fixtures | covered by the backend and frontend suites above (the Stage 6 fixture is used by `repair.test.ts` and `RepairPanel.test.tsx`) |
| engine version | `meos-0.5`: the three opt-in mechanisms of the follow-up (section 30); `meos-0.4` for every result file written before it, which `meos-0.5` reproduces bit for bit |

Tests added by the follow-up: `tests/test_meos_stage6_followup.py` (the three mechanisms, their validation, that the fault modes are not extended), and the expectations of five older tests that stated facts the follow-up changed (the engine version, the registry's not-implemented actions, the open windows and their CSV) were updated to the new facts; each of them still states the rule it protected (a window effective at the last tick tested is open; the fault modes are unchanged; the baseline digest is the same).

What this does not show: the reproduction scripts re-run a subset (they are not a re-run of every Stage 6 row); the full results were produced once, and the saved raw rows are for seeds 1-5 only (the other seeds are saved as the summaries derived from them).
