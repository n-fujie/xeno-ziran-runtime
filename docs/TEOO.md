# TEOO — BODY / TOTAL OBSERVATION (Phase 2: the open body-observation architecture)

Code: `backend/xzr/teoo/` (the layer), `backend/xzr/service/teoo.py` (routes under `/api/teoo`), `frontend/src/views/body/` (View A). View: `?view=body` (local server only).
TEOO (Total Embodied Operational Observation) is an **implementation label**, not a theory. "Total" means that consequential relations are not excluded in advance; it does not mean the whole of a body is observed.

**What this is.** A way to hold records *about bodies* (human, artificial, non-human, distributed) so that what was measured, generated, estimated and drawn are never confused; so that what was not observed is told apart from what does not exist; and so that a body is a declared, versioned graph and not a fixed skeleton.

**What this is not.** A physiological model, a medical device, a claim about any real body, a confirmation of any philosophical theory, or evidence. No real measurement exists in this repository: every example is SYNTHETIC or a test fixture and says so. Nothing here shows posthuman disconnection or total knowledge of a body; no medical conclusion is drawn from anything.

## 1. Layers and what is kept apart

| axis | values | where it is held |
|---|---|---|
| provenance (where the data come from) | `MEASURED`, `SYNTHETIC`, `RECONSTRUCTED_ESTIMATE`, `CONCEPTUAL` | inside every sealed record and its digest (`provenance.py`) |
| kind (what the record is) | `REFERENCE_STATE`, `OBSERVATION`, `ESTIMATE`, `RECONSTRUCTION` | a separate axis; an observation taken from a synthetic world is SYNTHETIC, never MEASURED |
| sample status (why a value is or is not there) | 11 states (section 3) | per sample in the payload (`status.py`) |
| time | Device, Acquisition, Ingestion, Reconstruction | `timebase.py`, with the synchronisation uncertainty |
| relation basis / claim | declared / observed / estimated / hypothesized; structural / association / causal | per relation in the body graph (`body.py`) |

## 2. Modules

| module | what it does |
|---|---|
| `schema.py` | Schema Registry (versioned schema ids, structure validation that never repairs); the 16 variable domains; the extensible, versioned variable registry (declared set of 26 example variables; declaring a variable implies no measurement) |
| `provenance.py` | Provenance Registry: `seal`, `derive`, `verify_record`, the append-only hash-chained `Ledger`, the write-once content-addressed `RawStore`, `Quarantine`, `PROTECTIONS` |
| `status.py` | Observation Status: the unified model, `assess()` for the causes of an observation limit (several can apply at once; undetermined metadata gives UNKNOWN_CAUSE, never a guessed reason), tables mapping the `hpo` and `meos` vocabularies |
| `timebase.py` | Temporal Reference: four kinds of time, clock synchronisation with known/unknown uncertainty, `align` (pairs only what can be paired), `resolvable`, interpolation records |
| `ingest.py` | Data Ingestion: CSV and JSON; ten checks; errors returned with field, code, fixability, never repaired; raw bytes kept; undeclared provenance quarantined |
| `body.py` | Open Body Graph: Body, Component, Relation, Constraint, Boundary, ObservationTarget, ConfigurationVersion; every change is a new version; four presets |
| `mapping.py` | Observation Mapping: coverage of a body's targets by records (a target with no record is UNMEASURED, "not observed", which is not "absent") |
| `reconstruction.py` | Reconstruction Records: derived, always RECONSTRUCTED_ESTIMATE, with inputs, method, time, uncertainty, interpolation |
| `evidence.py` | Evidence Classification: a label from provenance and kind (never from values); a record is never evidence by itself; mixing classes needs a declaration |
| `synthetic.py` | The SYNTHETIC example: artificial series that exercise every observation limit |
| `xbtro_adapter.py` | XB-TRO adapter (section 6) |

**Dependency direction.** `teoo` imports nothing else from `xzr` (checked by `tests/test_layering.py` and by `tests/test_teoo_layering.py`, which also runs it in a fresh interpreter and checks that no other `xzr` module is loaded); only the service imports it. TEOO runs without MEOS. The mapping from the observation vocabularies of `hpo/observe.py` and `meos/analysis.py` is plain data in `status.py`; a test imports both modules and checks that the tables are complete.

## 3. Observation status

`MEASURED_VALID`, `UNMEASURED` (could have been measured, was not), `UNMEASURABLE` (no instrument of the configuration can), `INSTRUMENT_MISMATCH`, `SCALE_MISMATCH`, `TIME_WINDOW_MISMATCH`, `BOUNDARY_INVISIBLE`, `SIGNAL_BELOW_THRESHOLD` (measured, under the detection limit: a bound, not an absence), `MISSING` (an expected sample is absent), `INVALID` (a value failed validation; its raw text is kept), `UNKNOWN_CAUSE`.

State, cause and validity are separate fields. A value is present only for `MEASURED_VALID`; elsewhere it is `None`, never 0. Several limits can apply at once: the status is the highest-precedence cause and the `causes` list carries all of them. A gap whose cause is unknown stays unknown (`cause_known: false`, no cause attached). No status says that something does not exist.

## 4. Provenance integrity: what is implemented, and what is not

Implemented: a content digest of every record (it covers the provenance class, kind, payload, parents and history); the digest of the raw original; an append-only ledger with a hash chain; an exportable checkpoint; class rules for derivation (a record derived from SYNTHETIC data can never be MEASURED; a derived MEASURED record needs an allowed processing step; `lineage_classes` carries every upstream class); quarantine of data without a declared provenance. A conversion is a **new** record with `derived_from`; there is no function that changes the class of an existing record, and verification fails when a stored class or content differs from its digest.

**Not implemented** (stated in every service response): digital signatures; access control and authentication; consent records, deletion on request, separation of personal identifiers; encryption at rest; a trusted external timestamp or transparency log; verification that a MEASURED record was really measured by the declared device. A digest detects a change; it does not stop someone who can rewrite the whole ledger and recompute every hash, and it says nothing about whether a MEASURED record was measured: that is a declaration of its source. The checkpoint must be stored outside the ledger to be of any use.

## 5. The body graph: represented, and validated

Represented (by the schema and the presets): human (a simplified skeleton, one preset among four; its coordinates are a drawing, `concept_only`), artificial (an articulated arm), non-human (a radial body with any number of limbs, no spine, no symmetry), distributed (a mesh of nodes with an observer-dependent boundary), severing, rejoining, adding and removing a component, reconfiguring, changing a boundary. A correlation is an `association`; a `causal` relation needs supporting record ids and a design (an intervention comparison, a randomised N-of-1 or a natural experiment), and the only route is `promote_to_causal`, which makes a new version.

Validated (by tests): that these structures can be declared, changed with their history kept, and checked for dangling references, duplicate ids, altered history and unsupported causal claims. **Not validated:** any physical behaviour. Nothing in `body.py` simulates a body; no claim is made that a preset is a faithful model of anything.

## 6. XB-TRO connection and Xeno-14

XB-TRO (branch `feat/xb-tro`, `backend/xzr/xbtro/`, commit `94c2e8e`) is **not merged and not imported**: the adapter reads its plain JSON outputs. (1) A declarative body configuration (links, joints, operation lines with `observable_by`) becomes an Open Body Graph; joint i joins link i-1 to link i and joint 0 joins the ground to link 0 (the N-link chain convention of `xbtro/engine.py`, recorded as a convention). (2) A live step becomes three records kept apart: `REFERENCE_STATE` (`frames[].reference`), `ESTIMATE` (`frames[].estimates`) and `OBSERVATION` (`observation[kind]`, with both the model time and the time it became available); all are SYNTHETIC, because XB-TRO's body is a simulated planar model ("nothing here is measured physiology"). Verified on fixtures dumped from the branch (`backend/tests/fixtures/teoo/`), not on a live import. The branch-wide merge was not attempted (48 files overlap with this branch).

The fourteen Xeno-14 names (`xbtro_adapter.XENO14_IDS`) are those of the reference definition, `ziran-xeno-simulator/src/domains/body.ts` (`XENO14`); a test compares them with the fixture extracted from that file and from `xbtro/xeno14.py` (equal, in the same order) and, when the sibling repositories are on the machine, with the live files. The results of the Xeno-14 line are kept as their reports state them (`xbtro_adapter.RETAINED_RESULTS`): **X14-1 STOP**; **X14-1b CONDITIONAL GO** under its predefined rule, no non-redundant control advantage demonstrated, the analyst assessment recommending not expanding to X14-2; **BS-1: base stabilizer not accepted** (A1-A3 fail on held-out seeds). All are results on simulated planar embodiments.

## 7. Ingestion

A document is a manifest plus data. CSV: pass the manifest beside it; JSON: `{"manifest": {...}, "rows": [{...}]}`. The manifest declares the schema version, the **provenance** (required), the creator and source, the body and its version, the time column and clock, and each channel (column, registered variable, unit, observation target, optional status column). Checks: schema version, units (a unit that differs from the registered one is an error; there is no conversion), time (finite, monotonic, no duplicates), provenance, observation target, missing values (a blank or NA is `MISSING`, never 0), invalid values (a non-number or a value outside the registered valid interval is `INVALID` with its raw text), duplicates, the body configuration, the digest of the original. A blocking error registers nothing and sends the raw bytes to quarantine with the issues.

## 8. View A — Body Observation

`?view=body`. A simplified drawing of a declared body; each part is coloured by the provenance class of the records that refer to it and by nothing else (and by pattern and outline as well as colour). Unmeasured parts are neutral and say so; limited parts (records exist, no valid sample) are marked apart; a selected part lists its target, variables, records, provenance, sample counts, observation limits and device time range. The drawing is labelled a **conceptual illustration** (not a photograph, not an anatomical measurement). When any record is SYNTHETIC (or has a SYNTHETIC ancestor) the page shows a banner and a watermark; both are derived from the data and no control can remove them. The body preset selector draws the other presets with the same code (a body without a concept layout is drawn on a circle).

Not in this phase: Views B–H; export of figures; experimental photographs; the protocol and statistics layer; the safety and consent controls; the large variable registry; hardware connections.

## 9. Running and testing

```bash
cd backend && python -m pytest tests/test_teoo_*.py -q          # the TEOO tests
cd frontend && npx vitest run src/views/body                    # View A
cd backend && uvicorn xzr.service.app:app --port 3011           # then open /?view=body (after `npm run build` in frontend/)
```

## 10. Tests: the 24 required checks, each its own test

| # | check | test |
|---|---|---|
| 1 | schema validity | `test_teoo_schema.py::test_a_valid_record_and_a_valid_body_pass_their_schemas` (+ missing / mistyped fields) |
| 2 | schema version identification | `test_teoo_schema.py::test_the_schema_version_is_identified_from_the_id_and_a_version_less_id_is_not_a_schema_id` |
| 3 | MEASURED and SYNTHETIC kept apart | `test_teoo_provenance.py::test_measured_and_synthetic_are_separate_classes_with_separate_digests` |
| 4 | an unrecorded change of class is detected | `test_teoo_provenance.py::test_changing_a_synthetic_record_to_measured_fails_verification` (and a changed content: `…changing_the_content_of_a_stored_record…`) |
| 5 | digest of the original | `test_teoo_provenance.py::test_the_raw_original_is_verified_by_its_digest` |
| 6 | derivation history | `test_teoo_provenance.py::test_a_derived_record_keeps_its_parents_and_the_upstream_classes` |
| 7 | unknown provenance rejected or quarantined | `test_teoo_provenance.py::test_an_unknown_provenance_is_never_registered_as_measured` |
| 8 | missing is not zero | `test_teoo_status.py::test_a_missing_value_is_none_and_never_zero` |
| 9 | unmeasured is not absent | `test_teoo_status.py::test_unmeasured_and_absent_are_not_the_same_state` |
| 10 | several observation limits at once | `test_teoo_status.py::test_several_observation_limits_can_apply_at_once_and_none_is_dropped` |
| 11 | synchronisation uncertainty | `test_teoo_status.py::test_clock_synchronisation_uncertainty_is_kept_and_unsynchronised_data_are_not_paired` |
| 12 | CSV ingestion | `test_teoo_ingest.py::test_a_csv_with_a_declared_provenance_becomes_a_sealed_measured_record` |
| 13 | JSON ingestion | `test_teoo_ingest.py::test_a_json_document_is_ingested_by_the_same_rules` |
| 14 | declaring a body graph | `test_teoo_body.py::test_a_body_is_declared_as_a_graph_and_validates` |
| 15 | history of changes | `test_teoo_body.py::test_every_change_of_the_structure_is_a_new_version_and_the_history_is_kept` |
| 16 | non-human bodies | `test_teoo_body.py::test_non_human_bodies_are_registered_by_the_same_schema` |
| 17 | severing and rejoining | `test_teoo_body.py::test_severing_and_rejoining_are_recorded_and_the_history_cannot_be_rewritten_silently` |
| 18 | observation and estimate kept apart | `test_teoo_reconstruction.py::test_observation_estimate_and_reference_state_are_kept_apart` |
| 19 | association edges and causal edges | `test_teoo_body.py::test_a_correlation_is_never_recorded_as_a_cause` |
| 20 | SYNTHETIC display enforced | `BodyView.test.tsx` "View A: the SYNTHETIC display is enforced" (3 tests) and `test_teoo_service.py::test_the_demo_is_synthetic_with_a_banner_and_a_verified_ledger` |
| 21 | data and drawing reference each other | `test_teoo_service.py::test_the_views_data_and_the_records_it_cites_are_the_same_data` and `BodyView.test.tsx` "cites only records that exist" |
| 22 | layering | `test_teoo_layering.py` (imports; a fresh interpreter loads no other `xzr` module; only the service imports `teoo`) and `test_layering.py` |
| 23 | XB-TRO connection | `test_teoo_xbtro.py` (presets to graphs; a live step to three records; Xeno-14 names; retained results) |
| 24 | no interference with Stage 4-6 | `test_teoo_layering.py` (the MEOS baseline digest, the Stage 6 result values, nothing of TEOO writes into the results) |

Existing tests were changed in two places only, to register what is new: `test_layering.py` (the `teoo` layer's allowed imports) and `test_security.py` (the three mutating `/api/teoo` routes, and that every route calls `local_only`). No expectation of an existing test was loosened.

## 11. Verification (Phase 2)

| check | result |
|---|---|
| new TEOO backend tests | 75 (`test_teoo_*.py`), all pass; `ruff` and `mypy` clean on `xzr/teoo`, `xzr/service/teoo.py` and the tests |
| View A tests | 12 (`BodyView.test.tsx`), all pass |
| backend, whole suite | one run on the final source: **882 tests (807 existing + 75 new), 880 passed, 2 failed**: the two known failures, `tests/test_compat.py::test_engine_conformance_against_the_golden_fixture[desktop-scipy]` and `tests/test_lab.py::test_published_records_replay`, with the same test names and the same failure messages as in the baseline record (`docs/ecosystem/evidence/meos_stage6.junit.xml`); no new failure |
| frontend, whole suite | 288 tests (276 before + 12 new), 0 failures; `tsc -b`, `eslint`, `vite build` clean |
| the 264 stored runs | replayed on this branch: 264 / 264 agree |
| the 6,475 regenerated validation and evaluation runs | re-executed on this branch (read-only; 265 settings): all equal the saved summaries, 0 mismatches |
| Stage 4-6 results | `git diff 63cc4b9` of `docs/` and of `xzr/meos`, `hpo`, `totalobs`, `study`, `lab`, `runtime`, `shapes` is empty; the MEOS baseline digest `b4cf1e52…` is unchanged (`meos-0.5`) |
| performance | **not measured and not claimed.** Nothing here has been benchmarked: no claim about the number of variables, channels or samples TEOO handles. The Stage 6 performance verdict (INCONCLUSIVE) is untouched |
| View A in a real browser | the page loads `/?view=body` against the running backend, draws 27 marks (3 synthetic, 3 limited, 21 unmeasured), shows the banner and the watermark, opens the detail of a selected part with its record id, and draws the radial non-human preset on a circle; no console error |

## 12. What exists, what does not, what was not checked

**Implemented and tested:** everything in sections 2-8 except the items below. **Implemented, tested only on fixtures:** the XB-TRO adapter (fixtures dumped from `feat/xb-tro` at `94c2e8e`; no live import and no merge), the live comparison of the Xeno-14 names (it runs only when the sibling repositories are on the machine).

**Not implemented:** signatures; access control; consent records and deletion; separation of personal identifiers; encryption at rest; an external timestamp or transparency log; Views B-H; figure export (PNG/SVG with metadata) and experimental photographs; the protocol, statistics and conventional-model comparison layer; the safety checklist and adverse-event records; a registry of hundreds of variables (26 are declared); hardware adapters (no device was connected, none is claimed); time-series synchronisation beyond pairing; hypothesis and causal-graph reconstruction beyond the records.

**Not checked:** that any MEASURED record was measured (nothing in this repository is measured); that the presets describe any real body; the connection to Operational Nihilism / NLEAAO, Rodenian Disconnection, Wide Human, Ontology Generation Interval and DGAR (no source for them was found in the searched text files; absence of a manuscript is **not** concluded: it was not found, and nothing here implements them); the relation of "Operational-Shape Realism" materials in `pa-simulation-environment` (not read for implementation). Name similarity (for instance this repository's graph-cut `disconnection` experiments) was not taken as a technical connection.

**Negative and limited results kept:** the MEOS Stage 4-6 results (including the performance verdict INCONCLUSIVE, the closed windows with their limits, the proxies) are unchanged; X14-1 STOP, X14-1b CONDITIONAL GO (no non-redundant control advantage demonstrated), BS-1 not accepted are carried in `RETAINED_RESULTS`; the protections that are not implemented are listed with every ingestion response.

**Novelty is not claimed.** What exists is a working arrangement of records, status, time and a body graph with tests; its difference from the existing layers is that provenance class and kind are part of a sealed record, that a derivation cannot drop its ancestry, that the observation status separates state, cause and validity for external data, and that the body is declared. Whether this is useful for real experiments is not shown here.
