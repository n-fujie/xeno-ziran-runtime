# Reliability repair of the total-observation line (rules v2)

Scope: only what bears on the reliability of experimental results. No new research module. Everything below is a *synthetic model*; nothing is a statement about the Earth or any theory.
Versioning: `environment.rules_version` — `v1` (default when absent: the first release, behaviour pinned by digests in `tests/test_totalobs_v2.py`, earlier stored studies replay identically under the repaired code,
verified) and `v2` (the repair; the four templates now name it). A v1 record gains no key. v1 and v2 numbers are not compared: the metric registry of v2 carries the freshness rule in its basis.

## 1. What "recall" measures — and what it does not

`recall_final` / `recall_region` is the share of the world's objects (connected sets of regions above the verifier's truth threshold, full resolution) that overlap an object *identified from the records the
hub's freshness rule lets the agent use*. It measures **what the research system observed**. It is not the software's reproducibility: re-execution agreement (replay, whole-study reproduction) is a separate quantity
(`reproduction.json`, `identical_share`), and the stored results are never edited to make anything agree. The v2 record states this in `recall_definition` and in the metric registry.

## 2. Why `comm-delay` and `planetary-form` recall was near zero

Found by controlled variation, not by assumption:

| fixed layout, 3 sensors | v1 (window counted from observation) | v2 (window counted from arrival) |
|---|---|---|
| latency 1 | recall 0.53 | 0.53 |
| latency 2 | 0.39 | 0.48 |
| latency 4 | **0.00, nothing identified at all** | 0.49 |
| latency 8 | **0.00, nothing identified at all** | 0.57 |

Cause: the hub kept a record only while `now − t_observed ≤ 12`. A record delayed in transit (`hops × latency`, up to 46 steps in `planetary-form`) was already older than the window when it arrived, so the agent's view was empty:
recall 0 with precision undefined. It is a measurement rule interacting with a declared latency, not a fault of determinism. Ruled out: the resource pool (raising it 24 → 1000 changed nothing), seeds (generator and engine seeds are separate; runs are identical on
re-execution), event order (events are applied in their listed order at the start of a generation, before the operations; recorded), update order, record loss and replay restoration (stored v1 studies replay identically under the new code; whole-study
reproduction 100 %).

v2 counts the window from arrival. A second finding follows and is kept: with stationary sources recall hardly depends on delay (information is old but the objects have not moved: 0.53 / 0.48 / 0.49 / 0.57), while `info_age_mean`
grows from 13 to 53 steps; with moving sources delay does cost recall (0.42 → 0.20 → 0.16 for latency 1 → 4 → 8). `recall` therefore cannot show the harm of delay in a stationary world; the planetary template now includes drifting-source arms.

## 3. A missing report is not an extinct sensor

v1 called a sensor "silent" when no record *observed* in the generation was in view, and answered by moving it next to the hub. Under delay this labelled every sensor silent. v2:

* classifies each sensor's reports from the hub's own bookkeeping and the agent's own layout: `ok`, `partial` (fewer blocks than the footprint: cost denied), `delayed` (reports arrive later than one period), `no-arrival` (reports were due and none arrived), `not-due`;
* never decides the cause of a missing report (outage, stopped sensor, lost records are not distinguishable from the hub); a `no-arrival` sensor is **probed once** (moved next to the hub): records resuming → "place-dependent (outage or delay)"; still none → "stopped-or-unreachable" and the sensor is abandoned. Attributions are recorded as attributions with their evidence;
* detects lost records from the hub's own accounting (`received − evicted − held`);
* the verifier records the true cause of every non-`ok` state (`silence_audit`). Over 8 seeds × 8 generations (failed sensor, regional outage, latency 3): `no-arrival` ↔ failed 40, outage 48 (never a plain delay); `delayed` ↔ delay 141, outage 24 (reports from before an outage began).
* a lost *identification* is split by the verifier into "the world's object is still there" and "the object is absent" (`ident_lost_object_still_present` / `_absent`).
* the stop reason reads "no-arrival: records arrive from no sensor (cause undetermined)", not "no observer".

## 4. `denied` against `scale-mismatch`

Both rules draw on the same budget and want opposite things of one sensor's scale. v1 flip-flopped; only a cooldown stopped it (43 suppressed moves in 10 runs of a conflict scenario). v2 states the conflict and its resolution (`conflicts` in every generation and run):

* `denied + scale-mismatch` → keep the resolution; relieve cost by doubling the period of the costliest sensor that is not the test's detector;
* `denied + period-too-slow` → keep the detector's period; relieve cost by coarsening the costliest non-detector sensor (by period if that sensor is the one whose resolution is wanted);
* no relief left, or the estimated demand (Σ blocks / period) would still exceed the pool → the conflict is **infeasible**: resolution and timing win, denial is tolerated for that sensor and it is not served again; each entry carries the demand and the pool.

Result in the same scenario: 0 cooldown suppressions, 2 scale reversals in 10 runs (a later, not simultaneous, change). The cooldown remains as a backstop and is counted separately (`cooldown_suppressions`). Resolved here: conflicts within one generation. Not resolved: sequential conflicts across generations beyond the cooldown (reported as `scale_reversals`).

## 5. "Supported" is observational support, not agreement with the model

Each test records: the detector, the baseline, the detection threshold (4 × its own report-to-report variation), `observational_support` (supported / refuted / coarse / no-arrival), `status_after`, and — verifier side only — `model_agreement` (`agree` within 50 % of the true propagation speed, `disagree`, or `unobservable` when the world itself shows no arrival).
v2 status: one supporting test → `provisional`; a second consistent one (within 35 %) → `supported`; an inconsistent one restarts the count; a refuting test after `supported` **withdraws** the support (`withdrawn`). Only `supported` returns the loop to the first question.
Test (`test_support_for_a_hypothesis_is_recorded_apart…`): when the verifier's answer is replaced by a wrong constant, the agent's operations and statuses are identical and only the recorded agreement changes — the agent never reads the verifier.

## 6. The two known failures (unchanged, now with a versioned alternative)

`test_compat[desktop-scipy]` and `test_published_records_replay` (`m2-run-9100.json`) fail on this machine (scipy 1.18.1, numpy 2.5.3, Python 3.12) because the golden fixture and the stored m2 record were produced with another solver build.
Root cause, already established and re-run (`tests/test_hierarchy_diagnosis.py`): the first divergence is the split of a sub-graph with several connected components; the second eigenvalue is degenerate, any vector of the eigenspace is a valid answer, and the one returned depends on the LAPACK/ARPACK build.
Nothing stored was changed or regenerated; the tests still fail and are not skipped. A deterministic **method 2** exists as a separate, opt-in function (`lod.hierarchy.build_hierarchy_v2`; components ordered by size then lowest index): it is invariant where method 1 is not (tested by emulating another solver build) and gives different partitions where method 1 hit the degenerate case — so it is a new method with its own name, selected by nothing by default, and does not overwrite any result made with method 1.

## 7. Limits that remain

The hypothesis test still needs a steady detector (many tests are deferred). Sequential rule conflicts are limited by a cooldown. Recall is blind to delay while sources stand still. The model is one scalar-activity family. Cross-machine and third-party reproduction have not been exercised.


## 8. Final verification (2026-10-24)

* **v1 compatibility.** The behaviour of v1 is pinned by digests of metrics and operation sequences (`tests/test_totalobs_v2.py::test_v1_behaviour_is_pinned`, three cases) and a v1 record gains no key. The four studies stored before the repair (200 runs: total-observation 84, autonomous-loop 36, planetary 48, SSS 32) were
  replayed **run by run under the repaired code: 200/200 identical**; their whole-study re-executions were 100 % identical. The repair did not rewrite any stored result and no v1 number is compared with a v2 number.
* **v2 on the seven environments** (64 runs): replay 64/64 and re-execution 64/64, same machine and software versions only (table in `ZRS_INTEGRATION_STATUS.md`, evidence in `docs/certification/certification_record.json`). Replay and re-execution are independent checks.
* **What the repair does not show.** The higher recall under delay in v2 is the removal of a measurement artefact (records discarded on arrival), not evidence that any method is better. With stationary sources recall does not show the cost of delay at all (information age does); v2 contrasts between arms remain UNRESOLVED in the functional studies.
* **Open limits, unchanged:** the hypothesis test needs a steady detector; sequential rule conflicts across generations are limited by the cooldown (reported as `scale_reversals`); no other machine or person has reproduced a result; the two known failures remain (owner decision).


## 9. Reproducibility in four tiers, and the environment dependence of the two known failures (2026-10-24)

| tier | what | performed | result |
|---|---|---|---|
| 1 | same machine, same software (Python 3.12.13, numpy 2.5.3, scipy 1.18.1, Accelerate BLAS/LAPACK), clean committed code `7216bef` | yes | replay of **264/264** stored runs identical (`docs/certification/certification_record.json`); whole-study re-execution identical for all 11 studies (stored `reproduction.json`, made earlier with the same code) |
| 2 | same machine, changed dependencies (Python 3.14.7, numpy 2.5.4, scipy 1.18.1, same Accelerate) | yes | replay of **264/264** identical, including the 7 ARDS-bridge runs (`certification_record_alt_env.json`) |
| 3 | another machine | **not performed** | — |
| 4 | independent third party | **not performed** | — |

Each record carries the environment in which it was produced (`replay_environment`: interpreter, numpy, scipy, BLAS/LAPACK, platform, git commit, dirty flag — clean for both). The studies themselves record the commit that made them and `git_dirty: true`
(working trees with uncommitted changes: `62d26cd` for the current-rules studies, `c8a60f2` for the v1 ones). Their traceability is therefore: the creating commit and its dirty flag, the registered protocol digest and seeds in the manifest, and the fact that **the clean committed code reproduces every stored run**
(tier 1 and 2). The uncommitted content of those working trees is not recoverable and is not claimed.

**The two known failures are an environment dependence, not a Python or numpy dependence.** In both software sets the computed hierarchy of the golden fixture's graph differs from the exported reference in the **same 501 of its nodes** (`docs/certification/environment.json`): on this machine the result is stable across these versions, so the reference was produced by
a solver build that the fixture does not record. The repository's `requirements-lock.txt` (2026-08-04) pins numpy 2.5.1 and no scipy or BLAS/LAPACK, which is not enough to rebuild it. To rebuild the old environment the owner needs: (1) the machine and build that produced the reference
(`numpy.show_config()`, scipy version, platform), (2) a virtualenv with those versions installed, (3) `pytest tests/test_compat.py tests/test_lab.py::test_published_records_replay` there. That would confirm the dependency; it was **not executed here** (it needs package downloads, and step 1 is unknown). From now on the build of any new reference should be recorded next to it.
Nothing stored was changed, and results of the default hierarchy method are never mixed with those of the opt-in method 2.
