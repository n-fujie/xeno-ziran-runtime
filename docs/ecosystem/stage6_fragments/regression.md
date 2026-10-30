All of it was run on the final tree of this commit (the interface and the document were last changed before the frontend run; the Python code was not changed after the full backend run except the document generator, which only reads saved data).

| check | result |
|---|---|
| backend `pytest` (whole suite, 796 tests) | 793 passed, 3 failed. Two are the known failures (below). The third was the document-consistency test, which failed only because the document had not yet been regenerated; after regeneration the three Stage 6 test files (33 tests, including that one) pass. So: 794 passed, 2 known failures |
| the two known failures | `tests/test_compat.py::test_engine_conformance_against_the_golden_fixture[desktop-scipy]` and `tests/test_lab.py::test_published_records_replay`: same names and same messages as at the baseline (`ec9667e`) and at Stage 5. Neither concerns MEOS-0 or Stage 6; they were not changed or skipped |
| frontend `vitest` | 275 tests, 0 failures, 0 errors (`evidence/frontend_stage6.junit.xml`) |
| `tsc -b`, `eslint`, `vite build` | no errors |
| `ruff`, `mypy` on the MEOS code (`xzr/meos`, `xzr/service/meos.py`, the Stage 6 scripts and tests) | no findings. The whole-repository run reports 39 `ruff` and 89 `mypy` findings in older modules (`hpo`, `study`, `totalobs`, `lab`, `experiments/results`) that this work does not touch; they are not caused by Stage 6 and were not fixed here |
| replay of the 264 stored runs | 264 / 264 agree (388 s; `evidence/replay_meos_stage6.json`). The runs were not regenerated |
| baseline result digest | `b4cf1e522e8bee460eab30ee2a3f86ffd703a3f7969dc21271cf0240aa09adc5`, unchanged |
| baseline trace digest | `bd3e588608139840831c2749b5051ac31a360d91c6a9a0131b9de3f0152ee1b7`, unchanged |
| Stage 5 reproduction (`reproduce_stage5_subset.py`) | identical: experiment L (history lost), F14 search and its digests, F8 search, F9 search, the first adaptive decisions, the Stage 4 strict nulls (Address collision, stale), the two digests |
| Stage 6 reproduction (`reproduce_stage6_subset.py`) | identical: 4250 / 4250 rows of the exploration grid, the per-tick window of the coupling pulse, 36 / 36 controller runs (`all_identical: true`) |
| stored MEOS fixtures | covered by the backend and frontend suites above (the Stage 6 fixture is used by `repair.test.ts` and `RepairPanel.test.tsx`) |
| engine version | `meos-0.4`, unchanged by Stage 6 |

What this does not show: the reproduction scripts re-run a subset (they are not a re-run of every Stage 6 row); the full results were produced once, and the saved raw rows are for seeds 1-5 only (the other seeds are saved as the summaries derived from them).
