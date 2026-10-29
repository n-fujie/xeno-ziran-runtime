Run on the final tree (`docs/ecosystem/evidence/`):

| check | result |
|---|---|
| backend, full `pytest` (`meos_stage5.junit.xml`, 1187 s; run again after experiment L and the `adaptive_mid` controller were added) | **763 tests: 761 passed, 2 failed** — the two known failures only: `tests/test_compat.py::test_engine_conformance_against_the_golden_fixture[desktop-scipy]` and `tests/test_lab.py::test_published_records_replay` (both failed in the baseline before this work; Stage 4 had 692 tests with the same two) |
| new Stage 5 backend tests (engine, mfs, reconf, experiments, final, mid-run), service routes, security (mutating-route list incl. `route-topology`, `reconfigure`, `mfs-run`), layering | all passed (inside the full run) |
| `ruff check xzr tests bench scripts` | all checks passed |
| `mypy xzr/meos` | no issues (13 source files) |
| frontend `tsc -b`, `eslint src scripts` | clean |
| frontend `vitest` (`frontend_stage5.junit.xml`) | **253 tests, 0 failures** (Stage 4: 210) |
| 264-run replay of stored studies | **264 / 264 identical** |
| baseline result digest and trace digest | unchanged (section 19) |
| experiment F-K tests with the saved results | passed (saved minimality, baseline digest in the saved file, `final` block) |

The 2 known failures were already failing in the baseline and are not touched by Stage 5; they are listed, not hidden.
