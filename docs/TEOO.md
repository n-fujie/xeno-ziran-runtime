# TEOO — BODY / TOTAL OBSERVATION (Phase 2: the open body-observation architecture; Phase 3 from section 13)

Code: `backend/xzr/teoo/` (the layer), `backend/xzr/service/teoo.py` (routes under `/api/teoo`), `frontend/src/views/body/` (View A). View: `?view=body` (local server only). Sections 1–12 describe Phase 2 as it was verified then; **Phase 3 (safety, total observation, Views B–H, protocols, causal inference, Open Revision, export, performance) starts at section 13**, and where the two differ (what is "not implemented") section 22 is current.
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

Not in Phase 2 (Views B–H, figure export, the protocol layer and the safety controls are Phase 3, sections 13–19): Views B–H; export of figures; experimental photographs; the protocol and statistics layer; the safety and consent controls; the large variable registry; hardware connections.

## 9. Running and testing

```bash
cd backend && python -m pytest tests/test_teoo_*.py -q          # the TEOO tests
cd frontend && npx vitest run src/views/body                    # Views A-H
cd backend && PYTHONPATH=. python scripts/teoo_perf.py out.json # the performance conditions (section 20)
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

**Not implemented in Phase 2 (superseded: sections 13–22 say what Phase 3 added):** signatures; access control; consent records and deletion; separation of personal identifiers; encryption at rest; an external timestamp or transparency log; Views B-H; figure export (PNG/SVG with metadata) and experimental photographs; the protocol, statistics and conventional-model comparison layer; the safety checklist and adverse-event records; a registry of hundreds of variables (26 are declared); hardware adapters (no device was connected, none is claimed); time-series synchronisation beyond pairing; hypothesis and causal-graph reconstruction beyond the records.

**Not checked:** that any MEASURED record was measured (nothing in this repository is measured); that the presets describe any real body; the connection to Operational Nihilism / NLEAAO, Rodenian Disconnection, Wide Human, Ontology Generation Interval and DGAR (no source for them was found in the searched text files; absence of a manuscript is **not** concluded: it was not found, and nothing here implements them); the relation of "Operational-Shape Realism" materials in `pa-simulation-environment` (not read for implementation). Name similarity (for instance this repository's graph-cut `disconnection` experiments) was not taken as a technical connection.

**Negative and limited results kept:** the MEOS Stage 4-6 results (including the performance verdict INCONCLUSIVE, the closed windows with their limits, the proxies) are unchanged; X14-1 STOP, X14-1b CONDITIONAL GO (no non-redundant control advantage demonstrated), BS-1 not accepted are carried in `RETAINED_RESULTS`; the protections that are not implemented are listed with every ingestion response.

**Novelty is not claimed.** What exists is a working arrangement of records, status, time and a body graph with tests; its difference from the existing layers is that provenance class and kind are part of a sealed record, that a derivation cannot drop its ancestry, that the observation status separates state, cause and validity for external data, and that the body is declared. Whether this is useful for real experiments is not shown here.

---

# Phase 3: total observation, experimental protocols, evidence integrity and open body research

Code added in this phase: `backend/xzr/teoo/{crypto,chainlog,redact,access,consent,vault,safety}.py` (data protection), `observation.py`, `revision.py` (total observation, Open Revision), `stats.py`, `protocol.py`, `causal.py` (experiments and causal inference), `media.py`, `export.py`, `session.py` (figures and the session bundle); routes `GET /api/teoo/{session,observation,safety}` and `POST /api/teoo/{figure,figure/verify}`; `frontend/src/views/body/{views.tsx,Workspace.tsx,session.ts,png.ts}` (Views B–H). The layering rule is unchanged: `teoo` imports nothing else from `xzr`; only the service imports it. The new routes are local-only like the others (403 under `XZR_PUBLIC`; the static mirror excludes `body`). **No real measurement exists anywhere in this repository and none was made in this phase: every figure, record and result below is SYNTHETIC or a test fixture, and says so.**

## 13. Safety and data management (before any human data)

**Judgement kept in two parts.** *Local verification*: what the tests in this repository exercise. *Production readiness*: whether human measurements may be ingested for real. The second is **no**: `GET /api/teoo/safety` returns `production_ready: false`, `human_measurement_ingestion_allowed: false` and the six missing requirements; the service stores nothing (`stored_on_server: false`). An attestation that is present in `production_gate(...)` opens nothing by itself being present: the code cannot check that it is true (`test_the_production_gate_is_closed_until_every_requirement_is_attested_and_an_attestation_is_not_verification`).

| # | capability | module | what is implemented (and its stated limit) |
|---|---|---|---|
| 1 | access control and authentication | `access.py` | scrypt password hashes, a minimum length, lockout after repeated failures, HMAC-signed expiring revocable tokens, a permission per operation and three roles (steward, researcher, reviewer). Limit: local accounts only; no external identity provider, no multi-factor authentication |
| 2 | consent and purposes | `consent.py` | append-only hash-chained consent log; purposes and data classes; external transmission is its own explicit class; revocation and expiry end use. Limit: a record of what was agreed, not a legal instrument; legal validity is not assessed |
| 3 | deletion with verification | `vault.py` | crypto-shredding (the subject's wrapped key is destroyed), overwrite and removal of blobs, removal of the identity, a tombstone, and `verify_deletion` that looks at what actually remains. A backup of the key store taken before deletion **defeats** deletion and the check says so (demonstrated in a test). Limit: copies outside the vault are not known unless listed |
| 4 | encryption at rest | `crypto.py` | scrypt + HKDF (RFC 5869 vector verified) + an HMAC-SHA256-CTR encrypt-then-MAC construction built from the standard library. **Not a vetted AEAD**; no `cryptography` package is installed here. The master key lives in process memory |
| 5 | integrity of the originals | `vault.py`, `provenance.py` | authenticated encryption (a changed blob does not decrypt), record digests, hash-chained ledger and audit log. A digest says the bytes are unchanged, not that they were measured |
| 6 | signatures / trusted checkpoints | `crypto.py`, `vault.py` | Lamport one-time signatures, each key committing to the next, chained from a trust anchor; a forgery, a rewrite, a shortened history and a reused key are caught. Limit: the anchor must be published where the vault's holder cannot change it (not done); key custody is not solved |
| 7 | identity / observation separation | `vault.py` | pseudonyms; identity only in one encrypted store; the ledger carries non-identifying skeletons. Limit: a pseudonym plus outside knowledge can still identify; the raw-data digest and the record digest stay in the ledger after a deletion, so a guessable original could be confirmed against them; re-identification risk is not assessed |
| 8 | no sensitive data in logs | `redact.py`, `access.py`, `vault.py` | the audit log and error messages carry identifiers and codes only; a redacting filter is a safety net; tested with planted canaries. Logs of other components (web server, proxies) are outside this layer |

**Append-only ledger and deletion.** The ledger keeps *what is retained*: non-identifying skeletons (record id, class, kind, digest of the encrypted blob, the pseudonym), never the data or the identity. A deletion therefore removes the originals, the key and the identity, and leaves a verification record that proves the chain is intact without containing anything about the person. What was deleted is verified by looking (`verify_deletion`), not by recording an intention.

**Threat → tests** (`tests/test_teoo_safety.py`, 22 tests): T1 unauthorised read → `test_t1_*`; T2 write without consent → `test_t2_*`; T3 tampering → `test_t3_*` (two); T4 token forgery/replay → `test_t4_*`; T5 password guessing → `test_t5_*`; T6 linkage through stores → `test_t6_*`; T7 leaks through logs/errors → `test_t7_*` (two); T8 data left after deletion → `test_t8_*` (four, including the backup that defeats it); T9 use beyond the purpose → `test_t9_*`; T10 rewriting history → `test_t10_*`; T11 opening without the passphrase → `test_t11_*`; the primitives (RFC vector, authenticated encryption, Lamport, checkpoints), consent appends, and the production gate have their own tests.

**Production requirements still missing (all six):** external identity provider; key-management service or hardware module with a vetted AEAD; an ethics approval for the specific protocol; an independent security review; a tested procedure removing data and keys from every backup and snapshot; a trust anchor published outside the vault holder's control. Until each has a verified reference, no human measurement may be ingested for real.

## 14. Total observation (inside TEOO)

`observation.py`. "Total" is **not** complete acquisition. A configuration says, for declared targets, what could be observed; its history is replayable.

* **Parts of a configuration:** sensors (channels, resolution, sampling period, window, detection limit, penetration, health, reach), couplings (gain, delay, link up/down), resources (an energy budget with a cost per second), memory (a buffer and a retrieval delay), and boundary opacity of each target. Each configuration is a numbered version with its parent and the change that made it.
* **Targets** are declared with a scale, a phenomenon period, an amplitude and an opacity. `assess_target` returns one of the 11 statuses with *all* applicable causes (scale, time window, boundary, signal below threshold, instrument, a failed sensor, a spent budget, an overwritten sample, a dead link); metadata that is missing gives `UNKNOWN_CAUSE`, never a guessed reason. A target that **could** be measured but is not is `UNMEASURED`/`MISSING`, which is different from `UNMEASURABLE` (no instrument carries it) and from absent.
* **Replay:** `state_at(history, specs, t)` gives the configuration in force at any time and the status of every declared target; `diff_states` and `observability_changes` say where a target's observability changed and which change did it. The session shows four configurations (t = 0, 6, 10, 14 s): the ankle moves from `TIME_WINDOW_MISMATCH` to `MEASURED_VALID` at 10 s because a sampling period was changed; the thigh from `UNMEASURABLE` to `MEASURED_VALID` at 6 s because an EMG sensor was added; the elbow at 14 s because the penetration of the sensor was raised; the head stays `SIGNAL_BELOW_THRESHOLD` throughout (the proposed coupling change was only proposed, and creates no version).
* **Reported completeness is relative to the declared targets** (`observed` of `declared_targets`), and the state carries the note that it is "not an acquisition of the world". There is no field named completeness or coverage of the world.
* **Relation field** (`relation_field`): relations of a task are listed with their dimension (spatial, temporal, material, hierarchical, infrastructural, causal), whether each was observed, whether it is accessible, and whether it could change the judgment. Unknown is counted as possible; the field is `epistemically_open` while any judgment-changing relation is unobserved, `generalisation_allowed` is false then, and `completeness_claim` is always `None`. This is the TRO reading of the task (section 21).

Tests: `tests/test_teoo_observation.py` (every limit from its declared conditions; the sensor failure, spent budget, overwritten sample, dead link and weak coupling; the reach rule; unknown cause; replay at any time; completeness relative to the declared targets; the relation field).

## 15. Views A–H

View A is unchanged (`BodyView.tsx`, `bodyDraw.ts`, its 12 tests). `Workspace.tsx` holds the eight tabs and reads **one** session bundle (`GET /api/teoo/session`): the same record ids, the same time base ("device time, seconds; unsynchronised"), the same body versions in every view. The SYNTHETIC banner is rendered by the workspace itself, above every tab, with no control that could hide it.

| view | shows | does not do |
|---|---|---|
| B Temporal Operational Shape | the observed samples as a line **broken at every non-valid sample**, the gap shaded, the status ribbon, the reconstruction as a dashed line with a band (RECONSTRUCTED_ESTIMATE) | draw a line across a gap; treat a missing value as zero |
| C Relational Observation | declared body relations, the sensors and their observation relations at time t, the relation field with what is unobserved | show an unobserved relation as absent |
| D Observation Limits | the time slider; the configuration in force; every declared target with its status and causes; the sensors; the revisions (who initiated each; autonomous revision is not demonstrated) | report completeness of anything but the declared targets |
| E Intervention | OBSERVATION before / INTERVENTION / OBSERVATION after / COUNTERFACTUAL_MODEL as four separate records, body versions before and after, the observed difference, the causal status | call the difference an effect |
| F Reconstruction | input record, result record, method, assumptions, interpolation, uncertainty, and the information lost | present an interpolation as an observation |
| G Experimental Evidence | the registered protocol, its class, the analyses with p and p (Holm), the replay check | present a synthetic generator as a real-world experiment |
| H Total Observation | one table of levels 1–7 (observation; estimate/reconstruction; intervention; counterfactual model; experiment; hypothesised or unobserved relation; unobserved difference); each row keeps its level, class and record id | add or average across levels |

Tests: `Workspace.test.tsx` (selectors, the gap in B, the configuration at t in D, the three kinds in E, the lost information in F, the protocol in G, the levels in H, that all views cite only records of the one session, the PNG helpers against a PNG made by the backend, the banner). Real-browser check: all eight tabs were driven in headless Chrome against the running backend with no console error; View D at t = 12 s showed configuration v3 and 5 of 7 declared targets observed; the exports of tab B were checked by the backend verifiers (section 19).

## 16. Experiment protocols

`protocol.py`, `stats.py`. A protocol is pre-registered data: hypotheses, targets, instrument conditions (the observation configuration version), control, conditions, seeds, trials per condition, a stopping rule, outcomes, analyses, a multiplicity rule, failure conditions and the reproduction steps. `validate` names every missing or inconsistent element (a control that is not a condition, repeated seeds, an analysis that names no hypothesis, two confirmatory analyses without a multiplicity rule).

* **Versions:** a registered protocol can be frozen; a frozen protocol cannot change; a change is `amend(...)`, which makes a **new version** with its parent and a stated reason. The registry is a hash chain; editing a stored protocol is detected (`verify`).
* **Confirmatory vs exploratory** is decided by three questions asked of the registry, not by the author: was the analysis declared in this version, marked confirmatory, was the version frozen, and was it frozen before the first data? Anything else is "exploratory (…)" with the reason. It agrees with the study layer's own rule on the same cases (a test compares them without making `teoo` import it).
* **Statistics:** a randomisation test that is **valid only if the assignment was randomised** (otherwise the p-value is withheld and the comparison is descriptive); Holm correction (a missing p stays missing); Cohen's d; a lag-1 autocorrelation warning for series that are not independent.
* **Replay:** `run_protocol` with a declared synthetic generator and `reproduce` give an identical trials digest for the same protocol, seeds and parameters, and a different one for any change. A null effect stays a null result and is kept.

Tests: `tests/test_teoo_protocol.py` (8).

## 17. Observation, intervention and counterfactual model; causal claims

`causal.py`. Three record kinds that are never merged: `OBSERVATION`; `INTERVENTION` (what was done, with body and observation-configuration versions before and after, and how it was assigned); `COUNTERFACTUAL_MODEL` (what a **declared** model says would have happened). The kind axis in `provenance.py` was extended and the class rules still hold: a counterfactual can never be MEASURED (it is SYNTHETIC from synthetic inputs, otherwise RECONSTRUCTED_ESTIMATE).

* A before/after difference is reported as an **observed difference** with `causal_claim: None`; when the observation configuration also changed, the comparison says the two records are "not even the same observation".
* `identify(design)` returns `association` unless the assignment was randomised, the analysis was confirmatory and no confounder is unaddressed; even then the answer is "supported under the stated assumptions … not established, not general".
* `StructuralModel` is a linear structural causal model that must name its assumptions, its identification conditions and its scope; it separates conditioning from `do`, and a counterfactual is abduction–action–prediction on a unit. The session's brace example is **researcher-chosen, exploratory and has an unaddressed confounder**, so its status is `association`.

Tests: `tests/test_teoo_causal_export.py` (the kinds, the observed difference, identification, `do` against confounded regression, counterfactual provenance).

## 18. Open Revision

`revision.py`. Types: sensor, scale, time window, boundary, body structure, coupling change; variable added/removed. Every revision is an event with its reason, who initiated it, the versions before and after, the body version before and after, and **what was gained and what was lost**, computed by replaying the target states before and after (a coarser sensor shows up as a loss). A *proposal* creates no version and says it "is not a physically executed modification"; `validated` cannot be set here; `autonomous_revision_demonstrated` is always `False` (a system that initiated a change did not thereby show autonomous revision). `replay_revisions` re-derives each event from the history; a changed history is noticed. **Nothing here claims that the apparatus revised itself.**

## 19. Figure export

`export.py`. SVG with embedded metadata (`<metadata id="teoo-metadata">`), PNG with the same metadata in a `tEXt` chunk (the browser rasterises the SVG on a canvas; the chunk is added in the page and the PNG helpers check every chunk CRC), and JSON metadata. Metadata: the figure id, kind, title, generation time, TEOO version, the evidence classes and watermarks, whether any real-world experiment is recorded, the records (id, class, kind, lineage, digest), the experiment (protocol, seeds, conditions), the observation limits, the body and version, units, a claim ("an illustration … no claim beyond them") and a digest of all of it.

* The **evidence band** and a **watermark for every SYNTHETIC / RECONSTRUCTED_ESTIMATE / CONCEPTUAL class** are part of the rendering; no parameter turns them off. `verify_svg` checks that the metadata matches its digest and that the band and watermarks are **drawn** (not merely quoted in the metadata); removing the band, a watermark or the metadata, or editing a field, is detected. (Writing this test found that the check had accepted a figure whose band text had been deleted, because the same text also sits in the metadata; fixed.)
* `inspect_png` reads the chunk and the digest; **the pixels are not examined**, and the check cannot tell a re-rendered PNG from the original.
* `media.py`: a photograph (MEASURED media) needs a declared capture device and time and a declarer; a generated image is SYNTHETIC, a reconstruction RECONSTRUCTED_ESTIMATE, a drawing CONCEPTUAL, and `presentation_label` is the only text a figure may use for an image ("… NOT a photograph"). The registry cannot see pixels: a declaration is not a proof. (This too was fixed while testing: a reconstructed image had been given a kind the class rules refuse.) No photograph exists in this repository.

## 20. Performance (measured, small range)

`backend/scripts/teoo_perf.py`, `frontend/src/views/body/perf.test.tsx` (`TEOO_PERF=<file>`), and a Playwright slider run; results in `docs/teoo_evidence/perf_phase3.json`. One run per condition, SYNTHETIC data, TEOO code only, this machine (Apple silicon, Python 3.12, headless Chrome 151). **These are not MEOS or Stage 6 results; the Stage 6 performance verdict stays INCONCLUSIVE and is untouched.**

| condition | variables × records × series length | samples | body graph / targets | build + seal | ledger append + verify | save / load | verify loaded | coverage | peak RSS |
|---|---|---|---|---|---|---|---|---|---|
| small | 5 × 10 × 1,000 | 5·10⁴ | 15 / 7 | 0.31 s | 0.14 + 0.12 s | 0.09 / 0.08 s (6 MB) | 0.10 s | 0.01 s | 81 MB |
| medium | 10 × 40 × 5,000 | 2·10⁶ | 200 / 50 | 13.7 s | 4.3 + 4.4 s | 3.7 / 4.9 s (246 MB) | 7.1 s | 0.74 s | 1.47 GB |
| large | 10 × 100 × 10,000 | 10⁷ | 1,000 / 200 | 86.6 s | 22.9 + 22.7 s | 52.9 / 40.9 s (1.2 GB) | 23.1 s | 13.1 s | 2.24 GB |

* **Cost is dominated by sealing and digesting the sample dictionaries** (about 9 µs per sample to build and seal), and memory is about 200 B per sample as Python objects. A 10⁷-sample session needs 2.2 GB and 1.2 GB on disk as JSON. Nothing beyond 10⁷ samples was run; no claim is made beyond it.
* **Body graph:** validation of 1,000 components took 0.08 s. **Figure SVG** of a 2,000-point series: 13–15 ms, 25 KB.
* **Replay of the observation state** at 21 times: 4 ms (7 targets, 4 sensors); 33 ms (50 × 5); 0.64 s (200 × 20); **36 s (1,000 targets × 100 sensors)**: the cost grows with targets × sensors × times, and 1,000 targets with 100 sensors is not interactive. Inside the loaded medium and large runs the same replay took 5.2 s and 0.64 s because of garbage-collection pressure from millions of live objects (isolated: 0.03 s for the medium case). The in-process figures are noisy; they are reported because they are what happened.
* **Render cost** (React `renderToString` of the plot in Node, a proxy for one render pass, **not** a frame rate): median 1.5 ms for 1,000 samples, 4.7 ms for 5,000, 8.1 ms for 10,000 (p95 2.9 / 6.6 / 10.3 ms; HTML 12 / 57 / 112 KB).
* **Render update frequency in a real browser:** dragging the time slider through 168 updates on tabs B, C, D and H (the session's 500-sample series) completed each update within one 60 Hz frame (median 16.7 ms, p95 ≤ 17.8 ms, max 22.9 ms on B). The measurement is limited by the frame period, so it shows "within one frame", not how much faster it is; series of 10⁴ samples were **not** run in the browser.
* **Claim:** TEOO handles the measured range above; the 1,000-target replay is a known slow case; whether anything faster, larger or on other hardware holds is not measured.

## 21. Theory connections: what is found, what is not

The sources were searched in the sibling repositories, `Phase3_audit_files/` and `Phase4_preparation_2026-10-21/`. A term that was not found is reported as not found; it is **not** concluded that no manuscript exists, and nothing was inferred about an unseen theory.

| term | found where | status in TEOO |
|---|---|---|
| Operational-Shape Realism | `Phase3_audit_files/99_ERRATA_AND_CORRECTIONS/THEORY_SCOPE.md` (and the Phase 4 `PROPOSITIONS.md`); the primary manuscript is **not** among the files searched, and that document itself says it did not consult it | TEOO stores records about operational shapes (the temporal shape in View B is a time series of status and values); no claim that it tests or supports the theory |
| XenoBody14 / Xeno-14 | the XB-TRO branch (`feat/xb-tro`), `docs/ECOSYSTEM_MEOS*.md`, `docs/HPO_VERIFICATION.md`, `frontend/src/views/ecosystem/body.ts` | the adapter checks the Xeno-14 names against `body.ts`; fixtures only, no merge |
| Ziran System | `THEORY_SCOPE.md`, `PROPOSITIONS.md` (the M4 meta-configuration proposition) | nothing in TEOO tests it; Open Revision is not "partially revisable meta-configuration" and demonstrates no autonomous revision |
| Xenoscience | the Phase 3 audit status files, `THEORY_SCOPE.md` | no implementation or claim |
| Disconnection | `docs/DISCONNECTION.md` (a disconnection study of the simulator: cut versus reconfiguration), and the **Rodenian Disconnection** name itself was **not found** | TEOO has `sever`/`rejoin` of body relations; it has no test of disconnection as a theory |
| Operational Nihilism, NLEAAO, Wide Human, Ontology Generation Interval | **no source found** (the only hits are this document) | not implemented, not claimed |
| DGAR | no source found (the hits in `world-market-audit` are unrelated text) | not implemented, not claimed |

**TRO (total relational observation), where it is implemented:** `relation_field` — relations of a task, observed or not, accessible or not, judgment-changing or unknown; the field stays open and forbids generalisation while a judgment-changing relation is unobserved; no completeness is ever claimed.

**Concrete operations for correspondences that are not implemented** (so that a future claim has something to check). *Rodenian/Wide-Human style disconnection of a body from its conditions:* the operation would be a dependency analysis over a declared body graph plus its environment — for each relation, record whether it was observed, severed, or unobservable along four dimensions (spatial, temporal, material, hierarchical) and whether severing it changed a declared outcome; the data would be paired records with and without the relation (an intervention record each); the verification would be a pre-registered protocol (section 16) whose confirmatory analysis compares outcomes with the relation intact and severed under randomised assignment. None of this exists in code, and no result is claimed. *Ontology Generation Interval:* no definition was found, so no operation can be stated.

## 22. What exists, what does not, what was not checked (Phase 3)

**Newly implemented and tested here:** sections 13–19 (all on SYNTHETIC data and fixtures).

**Still not implemented:** hardware adapters; an external timestamp or transparency log; a vetted AEAD and key management; an external identity provider; a registry of hundreds of variables (26 are declared); adverse-event records; conventional-model comparison beyond the synthetic two-condition generator; the dependency analysis of section 21; any physical sensor or body revision.

**Not checked:** that any record is measured (none is); that the presets describe any real body; the security of the crypto beyond the tests (the construction is not vetted and no independent review was done); legal validity of consent; behaviour above the measured performance range; the connections to the unfound theories.

**Judgement for a Phase 4.** Production feasibility is **no** (section 13). A Phase 4 that stays on SYNTHETIC and pre-registered synthetic or simulated-instrument experiments is feasible with what exists; a Phase 4 that ingests human measurement is not, until the six missing requirements have verified references.

## 23. Verification (Phase 3)

| check | result |
|---|---|
| new TEOO backend tests | 67 (`test_teoo_safety` 22, `test_teoo_observation` 19, `test_teoo_protocol` 8, `test_teoo_causal_export` 18); `ruff` and `mypy` clean on `xzr/teoo`, `xzr/service/teoo.py`, the tests and `scripts/teoo_perf.py` |
| new frontend tests | 18 (`Workspace.test.tsx`), plus `perf.test.tsx` (skipped unless `TEOO_PERF` is set); `tsc -b`, `eslint`, `vite build` clean |
| backend, whole suite | **949 tests (882 before + 67 new), 947 passed, 2 failed**: `tests/test_compat.py::test_engine_conformance_against_the_golden_fixture[desktop-scipy]` and `tests/test_lab.py::test_published_records_replay`, identical in name and failure message to the baseline record (`docs/ecosystem/evidence/meos_stage6.junit.xml` on the Stage 6 branch; compared programmatically). Run record: `docs/teoo_evidence/teoo_phase3_backend.junit.xml`. The run began before a lint-only clean-up (unused imports and variables, type annotations, one `noqa`); afterwards the touched modules' tests and `test_security.py` were re-run (95 passed) |
| frontend, whole suite | 306 passed, 1 skipped (288 before + 18 new), 0 failures |
| the 264 stored runs | replayed on this branch: 264 / 264 agree |
| the 6,475 regenerated validation and evaluation runs | re-executed on this branch (read-only; 265 settings): 265 / 265 settings match the saved summaries, 0 mismatches |
| Stage 4–6 results | `git diff 63cc4b9` of `docs/ecosystem` and `xzr/meos`, `hpo`, `totalobs`, `study`, `lab`, `runtime`, `shapes` is empty |
| existing tests changed | one: `test_security.py` lists the two new mutating routes (`/figure`, `/figure/verify`). No expectation was loosened |
| real browser | all eight tabs driven in headless Chrome against the running backend; no console error; exports (SVG, PNG, JSON) downloaded from tab B and checked with `verify_svg`, `inspect_png` and the digest: no issues, PNG metadata equal to the JSON |

**Completion criteria.** Met on SYNTHETIC data: data-protection capabilities 1–8 implemented with tests and stated limits; observation states replayable at any time; Views B–H over one session; protocols versioned and replayable; observation / intervention / counterfactual kept apart with no causal claim from a before/after difference; Open Revision recorded and replayable without any claim of autonomous revision; figure export that cannot drop its evidence band or class watermarks; performance measured for three predefined conditions, with the range stated; regression unchanged. **Not met, and not claimed:** production readiness for human data (six requirements missing), any real measurement, any vetted cryptography, any support for a theory.
