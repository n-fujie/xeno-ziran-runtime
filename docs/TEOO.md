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

---

# Phase 4: final verification of Phase 3, preview, cryptography, replay performance, and experiments A–E

Branch `feat/teoo-phase4` (from `9dcca49`). Evidence: `docs/teoo_evidence/phase4/` (`pilot_seeds_1_30/`, `confirmatory_v2/`, `figures/`, `replay_perf.json`). **Everything below that is an experimental result is a result about a SYNTHETIC world and about this implementation. No measurement of any body exists in this repository; nothing here supports a claim about a real body.**

## 24. Phase 3 final verification (commit `9dcca49`)

Run on the committed Phase 3 source, clean tree: backend **949 tests, 947 passed, 2 failed**; the two failures are the known ones, identical in name and message to the Stage 6 baseline (compared programmatically from the two JUnit files). The 264 stored runs replay 264 / 264; the 6,475 regenerated runs (265 settings) match their saved summaries with 0 mismatches. The first full frontend run happened while other heavy jobs were running and 6 tests in unrelated modules (`ecosystem/megastructure`, `lab/hifi/*`) hit vitest's 5 s timeout; they are load timeouts (the same files pass on an idle machine, see section 33), not behaviour changes. `ruff` over the whole backend found 40 findings against 39 at Stage 6: the extra one was mine (a 167-character line in `tests/test_security.py` from Phase 3); fixed in Phase 4. Two defects of Phase 3 found during Phase 4 and fixed: (1) the export bar of the workspace could export a figure under the metadata of a tab that had been left (a late response replaced the current one; found because three exports of one tab had different figure ids); (2) the ruff finding above. Not changed: Stage 4–6 results and everything under them — the git tree digests of `docs/ecosystem`, `backend/experiments`, `backend/xzr/{meos,hpo,totalobs,study,lab,runtime,shapes}` and `research` are identical at `63cc4b9`, `87e1fa3` and the Phase 4 head.

## 25. Preview environment

`https://teoo-preview.vercel.app` — a **separate** Vercel project (`teoo-preview`, team `platoststems-projects`); the production project of `ziran-xeno-simulator.vercel.app` and its branch `deploy/site-lab-m8-browser-edition` are untouched. (The first deployment of a new project is that project's "production" target; it is not the existing site.) The page is a static build (`npm run build:teoo-preview`; `frontend/vite.teoo-preview.config.ts`, entry `src/teooPreview.tsx`) of the same components as the local app, fed by 15 fixed JSON fixtures written by `backend/scripts/export_teoo_preview.py` from the local API. The exporter **refuses to write** if any record is MEASURED or has a MEASURED ancestor, if any record is not SYNTHETIC / reconstruction / concept, if a figure does not verify, or if the production gate is open. **Access control and scope:** public, read-only, no API (`/api/*` answers 404), no upload, no cookies, no stored data, no authentication or session limits to bypass because none of the local runtime is part of the page; response headers: `X-Robots-Tag: noindex`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a CSP with `connect-src 'self'`, `frame-ancestors 'none'`. The unique deployment URLs sit behind Vercel's deployment protection (302), the alias is public. A page banner says that it is a read-only SYNTHETIC preview.

Browser verification on the real URL (headless Chrome, desktop 1400×900 and mobile 390×844; script `verify_preview.cjs`, screenshots with their environment in the report JSON): all eight tabs render; no console error other than the deliberate probes of `/api/*` (404); every request is to the page's own origin; the slider drives the shared state (configuration v1 at t = 0, v3 at t = 12); SYNTHETIC banner and preview notice present on every tab; no horizontal overflow on mobile in any tab; SVG, PNG and JSON exports of tab B were downloaded and checked with `verify_svg` / `inspect_png`: no issues, the three carry the same figure id and the PNG metadata equals the JSON. (The check for the last item found the race of section 24.)

## 26. Cryptography

`xzr.teoo.crypto` now seals with a **vetted AEAD** from the `cryptography` package (OpenSSL): AES-256-GCM (default) or ChaCha20-Poly1305. Format 2: `0x02 | algorithm | key id (4 B) | 96-bit random nonce | ciphertext‖tag`; the entire header is authenticated with the caller's associated data (a swapped algorithm byte or key id fails authentication; tested for every byte of a blob). Nonces are random and a per-key counter refuses the 2³²-th message (NIST SP 800-38D); the counter lives in the process (a restart begins again — stated limit). **Without the library nothing is sealed** (`CryptoUnavailable` → `VaultError("CRYPTO_UNAVAILABLE")`, nothing written, tested); the old stdlib construction is never written again, but format 1 blobs can still be **opened** so that data made before can be migrated. `Vault.migrate` converts the passphrase check, the identity store, the wrapped subject keys and every record blob, appends a `reseal` entry to the ledger for each blob (the ledger stays append-only; `verify_integrity` follows the newest digest), stops on the first authentication failure without touching the damaged blob, is idempotent, and reports what is left by reading what is stored (`crypto_status`: object counts by format, algorithm and key id). `rotate_subject_key` (new data key, blobs re-encrypted, key id = generation) and `rotate_master` (new salt and master key, id + 1; check, identity store and every wrapped key re-sealed) need the new `key.rotate` permission (steward only). A failed decryption stops the operation with a code (`INTEGRITY`), discloses nothing about the content and is audited by code. Tests: `tests/test_teoo_crypto_v2.py` (15) and the 22 of Phase 3 unchanged. The dependency is declared (`teoo-vault` and `dev` extras in `pyproject.toml`; the HTTP service does not import it) and was installed in the shared virtual environment (`cryptography 50.0.2`).

**Unchanged and still blocking human data:** no external identity provider, no key-management service or hardware module (keys come from a passphrase held in process memory), no ethics approval, no independent security review or review of this integration by a cryptographer, no tested backup-deletion procedure, no published trust anchor. The production gate is closed and the preview shows it; human measurement ingestion stays forbidden.

## 27. Replay of the observation state: profile, change, before / after

Profile (cProfile, 400 targets × 40 sensors × 21 times): 87 % of the time was `assess_target`, of which a third was `channels_of(cfg)` recomputed for every (target, sensor) — O(targets × sensors²) — and the rest per-time recomputation of assessments that do not depend on time. The change (no speculative optimisations): a per-configuration context (channels and sensors by channel, built once); the **time-independent assessment** (everything except the energy budget) shared across all times; reuse **across versions** when everything an assessment was computed from is equal (the target's spec, the carried channels, the parameters of every sensor carrying the channel — reach included — and the target's couplings), so that a change to one channel recomputes the targets of that channel only. `state_at` / `replay` return the same states: the first implementation is kept in `tests/test_teoo_observation.py` as the reference and **60 random worlds × 9 times are compared field by field for equality**; no status, cause, detail or undetermined list is dropped. Measurement (`backend/scripts/teoo_replay_perf.py`; paired, alternating order; 3–15 repetitions per condition; wall clock, one process, this machine; percentiles of so few repetitions are order statistics of them):

| condition (targets × sensors × time points) | before p50 | after p50 (p95) | paired speed-up (min–max) | states identical |
|---|---|---|---|---|
| 7 × 4 × 21 | 4.5 ms | 0.8 ms (1.3) | 5.6× | yes |
| 50 × 5 × 21 | 35–138 ms (one noisy run) | 14.5 ms (45) | 8.9× | yes |
| 200 × 20 × 21 | 0.70 s | 0.038 s (0.085) | 17.9× | yes |
| **1000 × 100 × 21** | **40.3 s** | **0.76 s** (0.77) | **52.6×** | yes |
| 200 × 20 × 201 | 6.5 s | 0.21 s (0.22) | 30.5× | yes |
| 200 × 20 × 21, **every version changes a sensor** (worst case for reuse) | 0.68 s | 0.10 s (0.12) | 6.6× | yes |
| 1000 × 100 × 21, every version changes a sensor | 36.8 s | **2.3 s** (2.6) | 15.9× | yes |

The first condition is favourable (the versions carry identical sensors, so 95 % of the assessments are reused); the worst case (a changed sensor on the only channel recomputes every target) still gains from the context and the time sharing. Peak Python memory is unchanged within 3 MB (11–15 MB at 1000 × 100). **Claim:** replay of 1,000 targets × 100 sensors × 21 times falls from about 40 s to between 0.8 and 2.3 s depending on how much changes between versions, with identical states; nothing is claimed beyond the measured range (≤ 1,000 targets, ≤ 100 sensors, ≤ 201 time points, 4 versions) and nothing about other hardware. Cache hit rate is reported in `replay_perf.json`. The Stage 6 MEOS performance verdict (INCONCLUSIVE) is not touched.

## 28. Phase 4 experiments: design, pre-registration, what was run

**Central question.** Which operational features of a body become identifiable, and which differences become unidentifiable, when the sensor (scale, time resolution, detection threshold, window), the body configuration (couplings cut, rejoined, rewired) or the way the sensor is revised changes? It is turned into manipulations of a SYNTHETIC world (`xzr/teoo/world.py`, `experiments.py`) whose truth is its generator: components with an oscillation, optional bursts and feed-forward couplings; the sensor acts through mechanisms (spatial mixing for a resolution coarser than the structure's scale, un-filtered sampling, a dead zone below the detection limit that yields **no value, never 0**, attenuation behind a boundary the sensor cannot penetrate), so the TEOO status of a target is a **prediction** that the detectors can be compared with. Nothing is physically simulated: when a coupling is cut here the generated signal changes because the generator says so.

**Pre-registration and what the registry can and cannot show.** Five protocols (`TEOO4-EXP-A…E`) with hypotheses, null (the paired-difference tests are against zero, the equivalence tests against a margin), conditions, control, seeds, trials, primary/secondary endpoints, stopping rule (fixed n), tests, multiplicity (Holm over the confirmatory superiority tests of one experiment), failure criteria and reproduction steps were registered and frozen in the hash-chained registry before any datum of the pilot existed. **Honest sequence:** the generator and the hypotheses were designed after smoke-testing the code on seeds 1 and 2; a **pilot** (version 1, 30 worlds, seeds 1–30) was then run and its outcomes were seen (kept whole in `pilot_seeds_1_30/`, labelled exploratory evidence). Version 2 (`amend`, reason recorded) repeats **the same hypotheses, analyses, margins and criteria on fresh seeds** (1001–1030; D: 1101–1130), was frozen, and the first datum of version 2 was noted afterwards: the registry classifies the registered analyses of version 2 as confirmatory. One change beyond the seeds, made because of a defect found in the pilot (not to improve an outcome): the graph method of version 1 ignored a component's own samples when parents were available; version 2 uses own samples when there are any and the parents otherwise, and E2 is restricted to components without own samples. No success criterion was changed after the pilot, and the failed ones (A3, E3) stayed. Because the pilot was seen, the confirmatory label means "registered and frozen before the data of this run on seeds not seen before", not "no information about the outcome existed".

**Variables, and whether they were manipulated** (the directive asked to check that each can actually be operated in the existing simulator): sensor configuration, spatial resolution, temporal resolution, detection threshold, observation window — manipulated (A; C revises them); connection topology, disconnection, reconnection, reconfiguration — manipulated (B, D); coupling — manipulated only as presence/absence and a fixed strength (A coupling cases, B, D), not as a graded variable; boundary — penetration manipulated, the boundary's definition (opacity) is a fixed property of each component, **not manipulated**; component count — **not an independent variable** (n = 10 in A, B, D, E; 12 in C); resource (energy budget exists in TEOO), memory, environmental responsiveness and intervention timing — **not manipulated in Phase 4** (the revisions of C are offline, before the final measurement). These are not claimed.

## 29. Results (confirmatory run, 30 synthetic worlds per experiment, effect sizes and 95 % intervals in `confirmatory_v2/EXP-*.json`)

**A — observation resolution** (24 sensor conditions × 24 cases per world; α = 0.01 per case; identification of the true difference, undetermined counted as not identified).
* A5 (calibration, failure criterion): null cases identified at ≤ 1.4 % under every one of the 24 conditions, worst exact upper bound 2.9 % (< 5 %): met, the simulation is calibrated.
* **A2 burst differences: supported** (finest vs coarsest sampling: 0.64 vs 0.07 identified; Δ = 0.58, p_Holm = 0.0001).
* **A1 frequency differences: NOT supported** (0.74 vs 0.67; Δ = 0.08, 95 % CI −0.02…0.19, p = 0.26). The pilot had found an effect (Δ = 0.19, p = 0.013); on fresh seeds it is not there. Reason found in the data (exploratory A7): at coarse sampling a *difference* between two frequencies still shows (both alias, to different frequencies) but it is not the true difference: of the identified frequency differences, **98 % were identified as the true difference at 0.02 s, 65 % at 0.2 s, 26 % at 1.0 s**. The TEOO status predicts the loss of the value, not of the difference.
* **A3 amplitude differences: equivalence NOT supported** (Δ = 0.27; the expected null of the negative control failed: coarser sampling leaves fewer valid samples and the amplitude estimate becomes undetermined).
* **A4 status predicts identification: supported** (valid 0.65 vs not valid 0.24; Δ = 0.42). Exploratory A6: accuracy of the status model 0.74 against 0.32 for the one-parameter rule "amplitude ≥ detection limit" — a **weak comparator** (no fitted model on the same parameters was tried), so no claim of non-redundancy over a proper statistical predictor is made. 35.5 % of all cases were undetermined; only 20.5 % of the true-difference rows had a MEASURED_VALID status — most of the grid is deliberately poor.
* Secondary: finer resolution, lower detection limit and longer window each raise identification (tables in the JSON).

**B — body reconfiguration** (couplings of a set of three components to the rest cut; read by cross-correlation against a trial-shuffled null).
* B1 **supported**: share of the cut pairs read as coupled 0.67 (connected) → 0.15 (disconnected); B2 **supported**: back to 0.68 on reconnection. Reconfigured (the same number of couplings elsewhere): 0.30 of the old pairs read as coupled and 55 % of the new couplings recovered.
* **B3 NOT supported:** reading with TEOO status (leaving a pair undecided when an endpoint is not MEASURED_VALID) did not raise precision (Δ = +0.06, 95 % CI −0.10…0.24, p = 0.50; 19 of 30 worlds defined; on average 40 of 45 pairs left undecided with the medium sensor, so the aware reader decides very little).
* Descriptive: even the fine sensor reads the structure poorly (F1 0.48, precision 0.38, recall 0.69; 4.1 of 13 true couplings not read) because influence propagates, so correlation along indirect paths is read as coupling; the medium and limited sensors read 9.0 and 11.8 of the 13 couplings not at all. The relations not read are **unobserved, not absent**.

**C — open revision** (identification of 12 amplitude differences; revision budget 6.0 cost units; offline revisions).
* C1 adaptive − fixed: **supported** (9.5 vs 0.0 of 12). C2 adaptive − pre-specified schedule at equal budget: **supported** (+4.8; the fixed order spends its budget badly); random order is as bad as the schedule (4.5 vs 4.6).
* **C3 adaptive − cost-matched static sensor: NOT supported** (9.47 vs 9.83; Δ = −0.37, 95 % CI −1.0…0.27, p = 0.35); the equivalence (margin 0.5) is not supported either (90 % CI −0.87…0.17), so the data neither show that revision helps beyond a good static sensor nor that it is equivalent. **Non-redundancy of the adaptive revision rule is not established**: its advantage over the weak arms is the advantage of choosing a good sensor, which a static search with the same information also does, at a slightly higher cost for the static one (4.4 vs 4.1 cost units). The static arm is an oracle over the grid using the same status information; the adaptive arm needs 8 revisions on average.
* Every event names its initiator and says `autonomous_revision_demonstrated: false`; the adaptive rule's decider and information (statuses only, no ground truth) are recorded; no capability was lost in any revision (0 in all arms); **no autonomous self-revision is claimed.**

**D — disconnection** (30 other worlds). Source→sink dependency read by the fine sensor: connected 0.40, disconnected 0.04, reconnected 0.40, reconfigured 0.09; the world's operability (variance share): 0.27, 0.00, 0.27, 0.02. D1 and D2 **supported**; D3 **supported**: Spearman ρ = 0.93 (95 % CI 0.90…0.94) between observed dependency and operability over world × condition points; the sign of the change for the reconfigured condition agreed in 30 of 30 worlds. The observed dependency exceeds the operability level (indirect paths). The correspondence of these structures with the Rodenian Disconnection thesis is **not judged** (no source of the thesis was found); the existing graph-cut studies (`docs/DISCONNECTION.md`) and XB-TRO were not re-run and are not re-claimed.

**E — reconstruction limits** (one fine sensor degraded six ways). E1 **supported** (interpolation in gaps: normalised error 0.24 against 1.00 for the zero predictor); E2 **supported** (components without samples of their own: the coupled part from observed parents reduces the error by 0.18 against zero, though the reconstruction of those components remains poor: normalised error about 0.82 against 1.00 for zero). **E3 NOT supported**: the 90 % intervals are conservative (coverage 0.98, not 0.90 ± 0.05). Unidentifiable cells are kept as gaps: 50 % (partial reach), 38 % (opaque boundary), **93 % (1 s sampling)** for the interpolation; no value is filled for them and no error is computed. Under 3× noise error rises to 0.57, under 0.12 s desynchronisation it is unchanged (0.22).

**Statistics:** paired sign-flip tests across worlds (20,000 sign flips; valid for independent units with exchangeable condition order, which holds by construction), bootstrap intervals, exact bounds; Holm within each experiment's confirmatory superiority tests. Confirmatory tests: 17; supported after correction: 11 (A2, A4, B1, B2, C1, C2, D1, D2, D3, E1, E2); not supported: A1, A3, B3, C3, E3; A5 criterion met. **Negative or unexpected results kept:** A1, A3, B3, C3/C4, E3 (above), the weak indirect-path structure recovery, the near-total undecidedness of the status-aware reader, and that the pilot's A1 effect did not replicate.

**Evidence classes** (separate axes): Implementation Property — the 15 tests of `test_teoo_phase4.py` (determinism, mechanisms, calibration, refusal to fill, registry); Synthetic-world Result — all of section 29, confirmatory or exploratory as the registry says; Replayed Empirical Result and Empirical Observation — none; Unverified Claim — none made. A registered, frozen, SYNTHETIC experiment is not an empirical demonstration.

**Non-redundancy.** Comparators were set where one exists: static cost-matched sensor (C), naive reader (B), one-parameter rule (A6), zero predictor and interpolation without couplings (E; ablation of the graph information: E2's gain is only for components without own samples). Where the new component helps it is over weak comparators (C2, C5, A6); against the strongest available comparator (C3) it does not. Not done: ablations of every feature of the world, a fitted statistical predictor for A6, other reconstruction methods than the three.

## 30. Total observation records and figures

`confirmatory_v2/total_observation_records.json` (unit 1001): the body as a declared graph with versions (declare, sever ×k, rejoin ×k), two sealed SYNTHETIC intervention records with body and observation-configuration versions before and after (ledger verified), the observation configuration history (v1 fine sensor, v2 coarser sensor from t = 10 s), the replayed states at 0, 5, 9.9, 10, 15 s (replay identical), and the revision events of one unit. Not recorded: operational states of the simulated components beyond the digests of unit data (`*_units.json.gz` holds every unit's rows), resource and memory states (not manipulated). The unobserved are listed by status, not recorded as 0.

Figures (SVG, PNG 1600×840, JSON metadata, from the saved results; the PNGs were rasterised in headless Chrome and carry the metadata in a text chunk, checked): `figures/fig1…fig8` — total relational observation (true couplings not read, by sensor and body configuration), observation resolution, open body reconfiguration, open revision, disconnection, reconstruction limits, non-redundancy (standardised paired differences with intervals), the evidence summary (all 17 analyses). Each carries its evidence band, the SYNTHETIC watermark, experiment id and version, seeds, observation conditions and limits, record ids and digests. They are plots of synthetic-world results: no photograph and no screenshot of the application. Screenshots of the preview (the application) are in the verification report of section 25 and are separate files.

## 31. Existing research compatibility

Tree digests of the Stage 4–6 results and code are identical (section 24). Backend, frontend, replay and regenerated-run results of the Phase 4 head are in section 33. One existing module changed for Phase 4: `protocol.py` accepts further registered methods (`paired-sign-flip`, `equivalence`, `exact-upper-bound`, `descriptive`); the old validity tests are unchanged and pass.

## 32. The AI Legal Governance request: what could and could not be recovered

**Found:** `~/Downloads/The_Non_Scalability_of_Legal.docx` ("The Non-Scalability of Legal Subjecthood: Low-Score Subjects, Ontological Score Inheritance, and Procedural Equality in AI-Scored Institutions"), `ontological_score_inheritance_ai_society_revised_anonymous_manuscript.docx`, `score_inheritance_manuscript_anonymous_revised.docx` (+ title page), `AI_Society_Limit_Managed_Subject_Manuscript.docx`; Study E (192 settings / 1,920 trajectories / 61,440 series) in `docs/research/EVIDENCE_MANAGEMENT.md` and `RESEARCH_PROGRAMS.md`; and, in `~/plato-audit-suite/prisma/seed.ts`, a **catalogue of fifteen guarantees** that an earlier implementation of the user's carries (titles and definitions). **Not found** anywhere searched (Desktop, Downloads, the repositories, the two archives): *The Minimum Guarantees of Human Legal Subjecthood* (V3.0, 100_POINT_EDITION: so no comparison and no fixed base version), the MHEG text and its twelve guarantees, the fifteen principles of AI legal-logic governance, *Operational-Shape Realism for AI Law* (R1), XenoCapital, Operation Without Politics. The found manuscripts contain none of the strings "Minimum Guarantee", "MHEG", "Fifteen principles", "Operational-Shape". **Consequences, stated once:** (1) the fifteen guarantees are implemented from the plato-audit-suite catalogue copied verbatim by script (`backend/xzr/teoo/legal_guarantees.json`) and are marked everywhere (data, API, view, results) **PROVISIONAL — not verified against the original**; their names, definitions and independence may differ from the original's; replacing that file is a data change; (2) the three lists (twelve MHEG guarantees, fifteen guarantees of legal subjecthood, fifteen principles of governance) are not conflated: only a fifteen-item list is present, and which of the three it is cannot be said; (3) the comparison of V3.0 with the 100_POINT_EDITION was **not done**; (4) paper R1 was not available, so the **paper integration was not done** and no experimental figures were written into any paper.

## 33. Final verification of the Phase 4 head

Source: commit `8ab04cd` and its parents (later commits change documentation only), clean tree, idle machine.

| check | result |
|---|---|
| backend, whole suite | **981 tests (949 + 32 new), 979 passed, 2 failed**: the two known failures, identical in name and message to the Stage 6 baseline (programmatic comparison); new tests: `test_teoo_phase4.py` 15, `test_teoo_crypto_v2.py` 15, replay equivalence 2. JUnit: `docs/teoo_evidence/phase4/backend.junit.xml` |
| frontend, whole suite | 306 passed, 1 skipped (the render measurement); the same 306 at `9dcca49` on an idle machine (the 6 load timeouts of section 24 do not recur) |
| `tsc -b`, `eslint`, `vite build`, `build:teoo-preview` | clean |
| `ruff` (whole backend) | 39 findings = the Stage 6 baseline (all in archived experiment scripts); none in TEOO code; `mypy` on `xzr/teoo` and `service/teoo.py`: no finding in TEOO files |
| 264 stored runs | 264 / 264 agree |
| 6,475 regenerated runs | 265 / 265 settings match their saved summaries, 0 mismatches |
| Stage 4–6 | git tree digests identical (section 24) |
| experiments | `--check` re-runs the first unit of each experiment: digests identical for A–E; units are identical under different `PYTHONHASHSEED`; every confirmatory result file matches its registered protocol (test) |
| preview | `https://teoo-preview.vercel.app`, redeployed from the Phase 4 head; re-verified in a real browser (report, screenshots and the three exports in `docs/teoo_evidence/phase4/preview_verification/`); no external request, `/api/*` 404, SVG/PNG/JSON consistent |

**Mistake made and undone during the redeploy:** the first redeploy attempt, run from a folder without its project link, created a stray Vercel project `site-teoo-preview` connected to the GitHub repository; it was removed within a minute (it had been deployed once, to its own URL), and the deployment was repeated into `teoo-preview`. No other project was touched.

**Completion against the Phase 4 criteria.** (1) Phase 3 verified at its final commit: yes. (2) Preview works: yes. (3) Views A–H in a real browser: yes (the preview; the local app was verified in Phase 3). (4) SYNTHETIC / measured separation kept: yes, enforced by the exporter. (5) Replay performance measured: yes, with its limits. (6) Experiments A–E: all five run, on a synthetic world only; the variables that were not manipulated are listed in section 28. (7) Protocols and results saved: yes. (8) Negative results reported: yes (section 29). (9) Limits and uncertainty kept: yes. (10) No regression of earlier research: yes (digests). (11) Figures from real data: yes. (12) No unrun experiment claimed: yes. **Phase 4 is complete for what it set out to do on a synthetic world; it is not a validation of anything about a real body, the AI Legal Governance request (section 32) is open, and production use with human data remains closed.**


---

# AI Legal Governance on the synthetic institution

## 34. Implementation

`backend/xzr/teoo/legal.py` (imports nothing else from `xzr`), `legal_experiments.py`, `legal_guarantees.json`; route `GET /api/teoo/legal` (local-only); View I in the workspace (`ViewI`), also in the preview. 11 backend tests (`test_teoo_legal.py`), 6 frontend tests. **Reuse, not reinvention:** the registry, statistics, evidence classes, figure/PNG machinery, TEOO observation (statuses, configurations, revision) and the experiment runner pattern of Phase 4 are reused; the only new engine is a small synthetic institution (not an extension of the MEOS or the operational-shape runtime: those were not touched, and it was not checked whether an existing runtime scenario could express this institution — it is a research model for comparing configurations, not a legal or social model).

* **Institution:** people with a latent qualification, a group, an inherited record and resources that feed back into the score; a capacity-limited decision on the score or, when the score is deleted, on a proxy of the inherited record; a gate on the proxy; a second institution that inherits the first one's records and holds a denial for three periods unless corrections propagate; appeals (formal route, reviewer capacity, independence, authority, burden); expiry, re-entry support, suspension.
* **Fifteen guarantees:** `assess_guarantees` gives each its own state — SECURED, PARTIAL, ABSENT, INDETERMINATE, INAPPLICABLE — from the institution's formal provision and, where one applies, a measured effectiveness indicator; never one score. INAPPLICABLE needs a reason that is checked against the configuration (suspension when `harm_irreversible` is false); a provision that is not observed is INDETERMINATE, never ABSENT; every ABSENT or PARTIAL names a remedy path. The mapping guarantee → provision → indicator is this implementation's operationalisation, not the paper's (the catalogue gives titles and definitions only).
* **Legal translation:** the ten-stage path (technical event … remedy); each stage records basis, scope, responsible party, evidence, uncertainty, authority, route to contest; a stage without a legal basis is not a valid legal step; an AI output is not a legal decision (an authorised human with a route to review is required); a chain invalid at any legal stage is not treated as a valid decision.
* **Interventions** (reusing the TEOO notion of intervention: what is done, separate from what follows): score threshold, score deletion, gate removal, data correction (inheritance to zero), appeal, independent review, suspension, re-entry, correction propagation, expiry, governance reconfiguration; their inferential plausibility, executability, realised effect — measured in EXP-08 separately.
* **Observation:** the observer's fields (inherited record, score log, downstream log, review log) are observation conditions, each mechanism's detector is calibrated on worlds where it is switched off, and an unobserved mechanism is "not observed", not "inactive" (EXP-07, CMP-01).

## 35. Experiments EXP-01 … EXP-10 and CMP-01 (30 synthetic worlds each; protocols frozen before the first datum; no pilot — the code was smoke-tested on seed 1 only)

Registered analyses: 11 protocols, 28 confirmatory; **23 supported** (Holm-corrected p < 0.05, equivalence supported, or criterion met), **5 not supported**; all 28 results and all exploratory ones are in `docs/teoo_evidence/legal/`. Study E (192 settings, 1,920 trajectories, 61,440 series) is **not re-counted** as a result here; it stays where it is recorded.

| id | question | result (mean over worlds; synthetic institution) |
|---|---|---|
| EXP-01 fairness and exclusion | does fairness optimisation end exclusion? | true-positive gap 0.513 → 0.136 (supported); persistence of exclusion 0.908 vs 0.915 (**equivalence within 0.05 supported**: fairness improved, exclusion persisted); removing the gate on top: exclusion 0.297 → 0.250 |
| EXP-02 score and gate | score change, score deletion, gate removal | qualified people excluded: baseline 0.302; **score deleted 0.595** (the proxy takes its place); gate removed 0.285; both deleted 0.590 (a lottery that ignores qualification: the group gap closes, the exclusion of the qualified does not) |
| EXP-03 regeneration | after gate removal, does exclusion regenerate? | group gap before 0.513; after gate removal with residual dependencies **0.426 (83 % regenerated)**; with the dependencies cut 0.160 |
| EXP-04 contestability | formal appeal vs effective review | formal-only route: 40 % of wrongful denials appealed, **overturned in none of the 30 worlds**; independent reviewer with authority: 43 % overturned |
| EXP-05 material restoration | correction vs actual access | correction without propagation changed exclusion by 0.001 (p_Holm 0.022: statistically supported, **practically nil**); propagating the correction raises downstream access 0.696 → 0.754; re-entry support adds 6 persons (159 → 165) |
| EXP-06 score inheritance | weight of the inherited record | group gap 0.364 (λ = 0) → 0.564 (λ = 1.2); expiry of the inherited part 0.519 → 0.503 |
| EXP-07 observation revision | fixed vs revised observation | one more observed field identifies +0.53 active mechanisms of 4 (supported); choosing it from the outcome vs without looking: +0.03 (**p = 1.0**); vs a field order fixed in advance: 0.00 (**p = 1.0**) — **no advantage of the outcome-responsive revision rule** |
| EXP-08 inferential vs operational | convincing vs effective | the three most convincing interventions realise 0.014 reduction of exclusion, the three operationally best executable ones 0.067; only 57 % of the most convincing three are executable by the actor; **correlation between how convincing an intervention is and what it does: ρ = −0.12** (negative) |
| EXP-09 fifteen guarantees (class: **Implementation Property**) | detection, evidence insufficiency, remedy | every removed provision is reported ABSENT when observed and none that is present (criterion met); a provision that is not observed is never reported SECURED or ABSENT (criterion met); a formal appeal that can reverse nothing is found PARTIAL in 30 of 30 worlds, a checklist of formal provisions passes it in 21 of 30; every non-SECURED state names a remedy (met) |
| EXP-10 governance reconfiguration | moving review to an independent body | exclusion 0.301 → 0.270; a consent step and formal procedure shifts burden onto the subject: 0.707 → 0.753 |
| CMP-01 six planners, same observation and authority | exclusion of the qualified after at most two executable interventions (baseline 0.260; oracle 0.199) | rule-based compliance 0.241, fairness optimisation 0.267 (**worse than doing nothing**), structural causal model 0.234, constrained planning 0.227, model-based greedy 0.207, **observation-revision planner 0.216**, constrained planning with a random extra field 0.216 |

**CMP-01 reading.** The observation-revision planner beats rule-based compliance (Δ 0.026, p_Holm 0.014), fairness optimisation (0.052, 0.0003) and the structural causal model (0.018, 0.014). It does **not** beat constrained planning on the initial observation (Δ 0.011, p_Holm 0.19), nor — the non-redundancy question — the same planner given a **randomly chosen** extra field (Δ 0.0003, p = 0.96), and greedy model-based planning is nominally better still (−0.009, n.s.). **Non-redundancy of the revision rule is not established; the operational-shape reading is not shown to beat ordinary planning with the same information.** The planners share the intervention menu, the executability constraints, the budget and the observation (the revision planner's extra field is its only extra information and its cost is matched by the random-field arm); the model-based planners differ in how they obtain their model (stated in `run_cmp`), so the comparison is of those implementations, not of the families in general. No revision event shows autonomous self-revision (`autonomous_revision_demonstrated: false`; the initiator is the system by a fixed rule).

**Not shown, and not claimed:** that the guarantees are the ones of the original; that any result describes a real institution, law, algorithm or person; that the effect sizes hold outside this model; any claim about the thesis of the paper. Negative or weak results kept: fairness optimisation alone is worse than nothing in CMP-01; correction without propagation does nothing; the outcome-responsive revision rule adds nothing over a random field; how convincing an intervention is correlates negatively with what it does; the structure of EXP-05 is mostly a small effect in a 3-period holding model.

**Not done from the request:** the original catalogue and V3.0 / 100_POINT_EDITION comparison (originals missing), the integration into the paper R1 (paper missing), a dedicated research-figure set for these experiments and screenshots taken from the local application (the preview carries View I and its screenshots are saved with the preview verification), re-checks of the existing runtimes for features that could replace the synthetic institution (the existing Shape Detection / Interpretation / Philosophical Practice views were not exercised by this module), and the audit of the earlier plato-audit-suite catalogue against its own source. **The request is therefore not complete**: what is implemented and run is what could be implemented without the originals.


## 36. Final verification of the head with the legal-governance work

Run on the committed source (clean tree, regression run on `04c38e0`; afterwards only two corrections were made — the safety text that still called the cipher "not vetted", and a duplicated banner in View I — and the affected tests, the frontend build and the preview were re-run).

| check | result |
|---|---|
| backend, whole suite | **992 tests (981 + 11 new), 990 passed, 2 failed**: the two known failures, identical in name and message to the Stage 6 baseline (programmatic comparison). JUnit: `docs/teoo_evidence/phase4/backend.junit.xml` |
| frontend, whole suite | 312 passed, 1 skipped on an idle machine (the first run, started while other jobs were running, had one 5 s timeout in `lab/hifi/assemblies.test.ts`, a heavy existing test; it passes when run alone and on the idle rerun) |
| `tsc -b`, `eslint`, `vite build`, `build:teoo-preview` | clean |
| `ruff` (whole backend) | 39 findings = Stage 6 baseline, none in TEOO code; `mypy` on `xzr/teoo`: no finding in TEOO files |
| 264 stored runs / 6,475 regenerated runs | 264 / 264; 265 / 265 settings match, 0 mismatches |
| Stage 4–6 | git tree digests identical (section 24) |
| experiments | `--check` re-runs the first unit of each of the 16 experiments (Phase 4 A–E, legal EXP-01…10, CMP-01): digests identical |
| preview `https://teoo-preview.vercel.app` | nine tabs A–I verified in a real browser (desktop and mobile, no overflow, no external request, no console error besides the deliberate `/api/*` probes, exports consistent); View I interaction checked (assessment and chain selectors, counts, verdict); screenshots in `docs/teoo_evidence/phase4/preview_verification/` |

Corrections found by looking at the live page: (1) `safety.py` still described the vault cipher as "not a vetted AEAD" after Phase 4 replaced it (the page showed it) — corrected; the Phase 3 text of section 13 stays as it was written then and section 26 supersedes it; (2) View I showed the SYNTHETIC banner twice — corrected.

**Completion statement.** The Phase 4 and the implemented part of the AI Legal Governance request are done and verified as above. **Not complete, and not claimed:** the original catalogue and its V3.0 / 100_POINT_EDITION comparison, the paper R1 integration, a dedicated research-figure set for the legal experiments, screenshots from the local application for View I (the preview's are saved), a check of the existing runtimes' views for reuse (section 35), real-world validity of any result, and production use with human data. The request is open until the originals are supplied.
