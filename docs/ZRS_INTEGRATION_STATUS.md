# XENO ZIRAN SIMULATOR — integration status (branch `feat/zrs-integration`)

Working record of the integration. Everything here is a statement about the software and its stored records; nothing is a claim about
Strong Xenoscience or about any theory. Workflow guide: `docs/STUDY.md`. Perf record: `docs/study/perf_2026-10-22.json`.

## 1. Baseline before any change (2026-10-22, base `cce36f6`, py3.12.13 / numpy 2.5.3 / scipy 1.18.1)

| Suite | Result |
|---|---|
| `ziran-xeno-simulator` (TS) `node --test test/*.test.ts` | 73 / 73; `tsc` clean |
| runtime frontend `tsc -b` + `vitest` | clean; 12 files / 82 tests |
| runtime backend `pytest` | 347 pass, 1 skipped, **2 fail** |

The two backend failures predate every change here and are environment-caused, not regressions (kept visible, not fixed, stored records not
regenerated): `test_compat[desktop-scipy]` (hierarchy tie ordering on this platform; open item S11) and `test_published_records_replay`
(`m2-run-9100.json` does not replay here; it fails identically at the commit that produced it, `390c43f`; `XZR_FORCE_COMPAT=1` does not change it).

## 2. What already existed (verified by reading the code, not the older capability report)

HPO-003 recursive reconfiguration with sandbox and causal history (observation channels, scale, time window, penetration, catalog,
allocation, order, coupling, history, stopping; one derived variable `activity_trend`), instruments with reasons for blindness, lab
scientific systems (external memory, observation revision, variable generation against a matched control, parameter adaptation), shape
detector, hierarchy, the 11 result views. None of this was re-implemented.

## 3. Added (all on top of unchanged defaults)

| Addition | Where | Tests |
|---|---|---|
| Reachability record of every configuration change, checked against what the operations then did | `hpo/reachability.py`, `Controller(trace_reachability)`, `study/envs.py` | `test_ziran_core.py`, `test_study.py` |
| Revision of revision rules (bounded, recorded, exhaustible) | `hpo/metarevision.py`, `Controller(meta)` | `test_ziran_core.py` |
| Revision authority and per-epoch change budget | `Controller(authority, max_changes_per_epoch)` | `test_study.py` |
| Populations of 3 / 20 / 50 / 100 / 300 scientific systems | `lab/population.py` | `test_ziran_multiagent.py` |
| **Study layer**: protocol (modes, seed discipline, fairness, registration, amendments), runner (worker pool, timeouts, safe stop, resume, provenance), analysis, report, package / verify / reproduce, CLI, performance measurements | `xzr/study/` | `test_study.py` (41) |
| Study API (local runtime only; 403 under `XZR_PUBLIC`; cross-origin refused; ids and file names matched before any path is built) | `service/studies.py` | `test_studies_api.py`, `test_security.py` |
| **Experiments view** (protocol form / JSON, validation + fairness, run control, Ziran records, statistics, paper outputs, replay, reproduce) | `frontend/src/views/study/` | typecheck, eslint, vitest (82), live run in the browser |
| ARDS bridge (ARDS's own arms on its own environments, test mode only) | `study/ards.py`, `ards_bridge/` | `test_study_ards.py` |

The security-surface test did not see routes of included routers (newer FastAPI hides them behind `_IncludedRouter`); it now flattens them
and lists the new POST routes explicitly.

## 4. Verification evidence

* Backend after all changes: **426 pass, 2 fail (the two known), 0 skipped**; ruff clean. Frontend: tsc, eslint, vitest 82/82. TS simulator untouched.
* **End to end through the UI** (browser, local server): created the nine-arm revision study from the form (4 seeds), ran it (36/36 runs ok, 33 s,
  3 workers), analysed it, built the paper outputs (17 files, 8 figures rendered), packaged it (61 files checksummed, verification passed),
  replayed a stored run (agrees), reproduced the whole study (36/36 run records identical).
* End to end through the API in `test_end_to_end_paper_experiment_every_stage_through_the_api`: fixed run, narrowed observation, veiled boundary,
  added variable, shifted scale / window, reachability recorded and checked, meta-revision arm, history re-entry vs none, matched-random control,
  save / reload, statistics, figures, Methods / Results, package, replay, reproduction.
* ARDS: `EXISTING-blind`, `V2-PA`, `V2-PA-no-reinjection`, `FIXED-noise`, `V1-A` on env2, replicates 3980–3981: 10/10 runs, 0 verification
  failures. After the runs the frozen Phase 3 manifest verifies (1,526 files, no problems) and the ARDS git status is unchanged.
  Only env2 was exercised here; env1 (XB-TRO backend, worktree `xeno-ziran-runtime-xb-tro`) was not run through the bridge.
* Performance (one machine, 8 CPUs; `perf_2026-10-22.json`): run 0.64 s, CPU utilisation 0.98, peak 105 MB; speed-up 1.56× with 2 workers and 1.54× with 4
  for only 8 short runs (start-up dominates; efficiency 0.78 and 0.38); failure rate 0; analysis 0.03 s, report 0.01 s, package 0.06 s, verify 0.003 s;
  replay agreement 8/8; history re-entry cost ratio 1.01 (with / without); lab 3 → 300 systems for 40 steps: 1.0 → 2.6 s, 123 → 156 MB. The laboratory's
  completed transfers saturate (6 of 2,730 requests at 300 systems): the number of systems is a load, not a measure of autonomy.

## 5. What the functional runs showed (not evidence; 4–6 seeds in a reserved range)

`recursive-meta` is identical to `recursive` in the revision study (no rule failed twice in a row, so no revision occurred): a null result,
kept. `observation-narrowed` shows opened-but-not-used operations (reachability is not success). Contrasts are mostly UNRESOLVED at these sample sizes.
In the ARDS functional check `EXISTING-blind` scored higher unseen coverage than `V2-PA` (0.69 vs 0.50, 2 replicates), the same direction as the
Phase 4 exploration; it is reported as a functional check only.

## 6. Acceptance criteria (section X of the directive)

| # | Criterion | State |
|---|---|---|
| 1 | starts locally | met (`uvicorn`, built frontend) |
| 2 | API, UI and runtime connected | met (UI → API → runtime, live run) |
| 3 | researcher sets conditions | met (form / JSON / CLI) |
| 4 | independent-seed repetitions | met |
| 5 | comparison conditions explicit | met (fairness profiles per arm, undeclared differences flagged) |
| 6 | observation / boundary / scale / variable changes | met (protocol changes and controller changes; HPO world) |
| 7 | reachability recorded verifiably | met (record + next-epoch check) |
| 8 | meta-revision reflected in later operation | **partly**: shown in a unit / integration test with an imposed thick veil (revisions at epochs 2 and 4 reach the controller's next changes); in the nine-arm functional study no revision occurred |
| 9 | history re-entry works | met |
| 10 | raw data and logs stored | met |
| 11 | stored results reload | met (list, open, replay) |
| 12 | statistics | met |
| 13 | paper figures / tables | met as SVG / CSV; PNG only with an SVG converter; **no PDF** |
| 14 | Methods / Results data | met |
| 15 | git / environment / seed / protocol correspondence | met (manifest; the git dirty flag is recorded) |
| 16 | reproducibility test | met on the same machine (36/36); not exercised across machines |
| 17 | no serious regression | met apart from the two known baseline failures |
| 18 | negative results kept | met (every contrast and metric listed; failed runs kept; null results reported) |
| 19 | unproven propositions not treated as proven | met (labels, interpretation boundary, no theory statements generated) |
| 20 | third-party procedure exists | exists (`REPRODUCE.md`, CLI); never run by a third party |

## 7. Not done (so not claimed)

* ARDS arms do not run on the HPO world; "Environment 3" had no earlier specification (it was only a proposal) and was not built. The ARDS bridge
  is test-mode only, so no ARDS exploratory / confirmatory study can be produced from here.
* Active Inference and other comparison methods are not arms of the HPO world; they live in their own environments (`research/`, ARDS). The
  HPO-world comparators are fixed, recursive, recursive+meta, matched random, no-history and protocol-imposed observation / boundary / variable / scale conditions.
* The interactive Shape Space view is session-based and is not linked to study runs; a study can run the shape detector (`detect_shapes`) and
  stores its output separately from interpretation.
* The agent display is per arm (profile, changes, records), not a live view of agents inside a run.
* A confirmatory study has been exercised with small functional-size runs in tests only; no confirmatory scientific experiment was run.
* Variable generation in the HPO controller is still limited to `activity_trend`.
* No CPU-time or memory limit is enforced per run beyond the timeout (peak memory is recorded).

## 8. Completion levels (separate)

* **Level 1 (software): reached for the study workflow**, subject to the two baseline failures that are environment-related and unchanged,
  and to the gaps in section 7.
* **Level 2 (Ziran operational): not claimed.** The operating sequence (conditions → observation / intervention → difference → revision →
  change of later possibilities → history re-entry → re-revision) can be configured, run and recorded, and reachability and rule-revision records
  exist; whether such revision *improves* later research is not shown (the functional studies are not evidence).
* **Level 3 (strong xenoscience): not claimed.** Human-energy independence, human-readability independence, self-reproduction and self-generation
  of variables / boundaries are not demonstrated; nothing here bears on them.

---

# Second directive (ARDS env1, shared ARDS–HPO environment, Ziran validation, multi-system) — status

Design record of the new environment: `docs/SHARED_ENVIRONMENT.md`. Everything below is functional-check level (reserved seed ranges / ARDS
software-test replicates 3980–3989): **no scientific claim, no confirmatory or Phase 4 study was run.**

## Stage 2 — ARDS env1 (XB-TRO) through the bridge

* Specification read from the ARDS code (`envSpec.ts`, `loop/types.ts`, `heldOut2.ts`, `arms2.ts`, `driver.ts`, `studyGuard.ts`): env1 = XB-TRO planar body on the
  Ziran-runtime variant (worktree `xeno-ziran-runtime-xb-tro`, interpreter `xeno-ziran-runtime/.venv`), held-out cases human/machine × four alterations, 72 body runs,
  set-up budget from the catalog. The bridge calls ARDS's own `runReplicate`; no method is re-implemented.
* **Equivalence check** (`python -m xzr.study ards-equivalence`): the bridge path against ARDS's own building blocks (`runArm` + held-out evaluation, as
  `scripts/ardsV2RealSmoke.ts` uses them), same environment / replicate 3980 / arm / test parameters: **EXISTING-blind, V2-PA, V2-PA-no-reinjection, FIXED-noise,
  V1-A — metrics identical, 0 verification failures, on env1 and on env3** (`docs/study/ards_equivalence_env{1,3}_3980.json`).
* A five-arm env1 study ran through the study workflow (10/10 runs, analysis, report). On that single replicate pair EXISTING-blind scored higher unseen coverage
  than V2-PA (0.74 vs 0.70) — the same direction as the Phase 4 exploration; a functional check only.

## Stage 3 — shared ARDS–HPO environment (`env3`, kind `shared-oi`)

* New environment, own namespace; ARDS arms run unchanged against a Python worker through a TypeScript service; the HPO arm is the HPO-003 *policy* on the
  same task with the same budgets, permissions, adoption discipline and evaluation (ARDS's held-out code). Operations table: shared / arm-internal / **not
  available** (variable generation, boundary change, intervention, evaluation change are named as unavailable here, not assumed).
* A UI-created study (8 arms, 1 replicate) ran to completion (8/8), was analysed, reported (16 files, 7 figures), packaged (32 files verified), and a stored HPO-arm
  run replayed with agreement. A real defect surfaced and was fixed (figures with undefined intervals at a single seed), with a regression test.
* A two-replicate study: unseen coverage — existing-blind 0.64, ards-pa 0.35, hpo-rules 0.56, hpo-rules-no-history 0.52, fixed-noise 0.29, control 0.27; `hpo-rules-meta`
  identical to `hpo-rules` (no rule failed twice, no revision); capability openings predicted by the HPO arm were mostly not identified on fresh data (13 opened, 1
  identified): the reachability estimate over-predicts usefulness. Two replicates: not evidence.

## Stage 4 — Ziran operational validation

* Observation revision with invisibility ≠ absence: tested (`test_a_hidden_difference_becomes_identifiable…`): a difference that exists in the truth is device-blind, then
  capable-but-not-identified (noise), then identified after a second revision.
* Generated variable (`xzr/study/variables.py`): `activity_trend` is **not a relabelling** (novelty 0.85: only 15% of its variance is explained by the existing channels), but with 8
  paired seeds **no downstream effect is resolved** (picturing_error +0.13, CI [−0.03, 0.28]; revisions, fired samples, ignitions unresolved). New, and not shown to matter.
* Meta-revision: mechanism verified (imposed veil; the policy's own rule spec in the shared environment); in the functional studies no rule failed twice, so no revision occurred.
  Null kept; a revision is never evidence of improvement.
* History re-entry: on/off arms in both worlds; effect not presumed (shared environment: hpo-rules 0.56 vs no-history 0.52 over two replicates, unresolved).
* Reachability: predicted-vs-realised recorded in both environments (opened ≠ success).
* Shape detection output stays separated from interpretation (`detect_shapes`); the detector's limits are stored with it.

## Stage 5 — multi-research-system measurements (`lab/multisystem.py`, template `multi-system`)

Ten properties measured per run and contrasted with controls (tests: `test_multisystem.py`). In the functional study (20 systems, 4 seeds × 6 arms, 24/24 runs): histories are
independent (pair overlap 0.0); 20 distinct observation conditions; activity is asynchronous (first-request spread 1.1 steps, simultaneity 0.1; the non-diverse control is 0);
exchange and inheritance produce reads of another system's store (61 / 25) but **no change in requests or completions** (null); stopping 30% lowers the others' request rate ratio
(0.42 vs 0.57 without a stop; confounded by time); scaling to 100 systems raises contention (denied + failed share 0.97 vs 0.53) while completed transfers stay at ~8;
closing and reopening one system's view raises coverage shrink / expansion counts (20 / 12 vs 18 / 8). These are properties of a simulation, **not evidence of autonomous science**.

## Stage 9 — the two baseline failures (investigated, not "fixed")

* `m2-run-9100.json`: fails identically at the commit that produced it. At steps 1–3 the activity and shutter vectors are identical and **two of 32 chambers' memory differ with
  their sum preserved**, and the conduit count differs by one (177 vs 176): a few nodes sit in the neighbouring chamber — the dynamics agree, the *hierarchy partition* differs.
  Same root cause as `test_compat[desktop-scipy]` (tie ordering of the bisection on disconnected sub-graphs; `docs/DISCONNECTION.md`, open item S11).
* No code change: a deterministic tie-break would change cluster membership, hence every address-based stored result, on every platform, and could not reproduce records made under
  another tie order. It is an owner decision (options: canonical tie-break + regenerate with a compatibility note; or keep the reference-hierarchy mechanism). Stored records untouched.

---

# Final completion record (2026-10-22)

**Tests (current code, current logs).** Backend full run: 469 collected, **467 pass, 2 fail — the two known environment-caused failures** (`test_compat[desktop-scipy]`,
`test_published_records_replay` / `m2-run-9100.json`), neither skipped nor altered; the run showed two further failures that were test-isolation defects of my own
(a test that tampered with a module-wide fixture); fixed, and `tests/test_study.py` re-run in order: 50/50. Frontend: tsc, eslint, vitest 82/82. TypeScript simulator 73/73 + tsc.
ARDS frozen Phase 3 manifest: 1,526 files, no problems; the ARDS repository's git status is unchanged by every bridge run (tested).
Before → after: backend 365 → 467 passing; the same two failures throughout.

**Both known failures now have a code-level diagnosis (`tests/test_hierarchy_diagnosis.py`), not a fix.** The first divergence from the exported reference hierarchy is a bisection
of a sub-graph with two connected components (degenerate eigenspace: the second eigenvector is only defined up to the solver); every connected split before it agrees. The `m2` record's
first steps agree with a fresh run in all per-chamber activity and shutter values; two chambers' memory differ with their sum preserved: a few configurations sit in the neighbouring chamber.
Unresolved by design: a deterministic tie-break would change cluster membership, hence the addresses of every stored result, and could not reproduce records made under another
tie order. Impact on the completion judgement: cross-platform bit-reproducibility of address-based results is not guaranteed; same-machine reproduction is (36/36, 8/8 verified).

**Small samples.** `analysis.paired_safe`: fewer than two complete pairs → mean (n=1) only, sd / effect size / interval / p / Holm / BH are `null`, status `INSUFFICIENT DATA`; n=0 → `NOT MEASURED`;
descriptives for n=1 have no sd/var/interval; criteria become `not evaluable`; nothing is replaced by 0, 1 or ∞. Regression tests for n = 0, 1, 2, 3 (analysis, strict JSON, report, figures),
and for missing-versus-zero effect.

**Scenarios (software verification, not confirmatory science).**
A standard experiment (9 arms × seeds → stats → outputs → package): UI-driven earlier, API test `test_end_to_end_paper_experiment…`. B observation / boundary / variable / scale / window changes with reachability:
revision-study arms. C meta-revision reflected in later decisions: imposed-veil integration test (penetration 0.7 → 0.85 → 1.0 reaches the controller's next changes) and the scarcity study (alloc_step 1.5 → 2.0 → 2.5 in 6/6 severe runs).
D ARDS: env1, env2, env3 bridge studies run; five arms identical to ARDS-direct on env1 and env3. E reproducibility: stored-run replay (ARDS and HPO arms) and full re-execution of the shared study, 8/8 identical;
36/36 for the revision study. F failure and negative results (`scarcity-study`, 42 runs): research stop (all operations ceased for an epoch) in 50% of fixed-moderate runs, meta-revisions 3 per run and rule exhaustion
in 6/6 severe and no-resource runs, complete blindness (0 fired samples) without resources, plus opened-but-unused reachability. G multi-system: ten measured properties (above).

**Output checks.** Tests verify that the generated Methods / Results contain none of a list of unsupported-claim words, carry the functional banner and the interpretation boundary, and that the numbers in
runs.csv / descriptives.csv / contrasts.csv / results.md equal the stored run records.

**Completion levels.** Level 1 (experimental infrastructure): reached for the study workflow (HPO world, laboratory populations, ARDS env1/env2/env3, shared environment), with the limits below.
Level 2 (Ziran operational research): the sequence conditions → observation / intervention → revision → change of later possibilities → history re-entry → re-revision runs and is recorded; revisions reach later decisions
(tests above); whether revision *improves* later research is **not shown** (functional studies: unresolved or negative contrasts, e.g. meta-revision lowered fired samples by 26 in the first scarcity study, UNRESOLVED).
Level 3 (strong xenoscience): **not claimed**; human-energy independence, human-readability independence, self-reproduction and self-generation of variables / boundaries are not demonstrated, and variable generation
exists only as `activity_trend` (novel, 0.85, but no downstream effect resolved at 8 seeds).

**Not done / limits.** No third-party or cross-machine reproduction; no PNG without an SVG converter, no PDF; variable generation / boundary change / intervention are *not available* operations in the shared environment (named, not assumed);
env1 was run through the bridge on replicates 3980–3981 only; ARDS rule family and HPO rule table are structurally close, so the shared-environment comparison is a policy-level comparison; no exploratory/confirmatory ARDS study can be started
from here by design; the interactive Shape Space view is not linked to study runs.

**Git.** Branch `feat/zrs-integration`; the branch was pushed once (user-instructed, up to commit 57bc3bf); every later commit is local only; nothing deployed. Untracked: `frontend/node_modules` (symlink), study outputs are git-ignored.
