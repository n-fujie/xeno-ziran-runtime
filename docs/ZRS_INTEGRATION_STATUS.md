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

---

# Level 2 completion record (2026-10-23)

Judged in four stages; a stage is never reported as the one above it.

| stage | meaning | status |
|---|---|---|
| A | Implementation complete | **reached** for the items below |
| B | Operationally verified (runs, recorded, tested, reproduced on the same machine) | **reached** for the items below |
| C | Scientifically evaluated (confirmatory, pre-registered, fresh seeds) | **NOT reached** — only functional studies were run |
| D | Non-redundancy established | **NOT established** — default verdict is "not evaluated / not established" |

## What A and B cover

* **Reachability levels** (`hpo/reachability.py`, `hpo/reconfig.py`): availability, executability, success, reachable / observable / detector-identified sets, used.
  Static (right after a change) and dynamic (after the next epoch) levels; effect classes expanded / contracted / mixed / equivalent. `tests/test_reachability_levels.py` (9):
  expansion, contraction, observability gain and loss, boundary change → branching, scale change → identifiability, resource exhaustion → inoperable, history reinjection → selection change,
  invalid revision, equivalent change. Tracing does not change a run (tested).
* **Shared-environment operations** (`study/shared/ops.py`): evaluation change is a shared harness operation; intervention is arm-internal (HPO arm selection rule vs ARDS fixed / permuted order);
  variable generation and boundary change are **not shared**, with the reasons recorded and the operations evaluated in the HPO world (`study/variables.py`, `study/boundaries.py`).
  Permitted / implemented / succeeded are recorded separately. No arm is forced onto another arm's internal algorithm.
* **Meta-revision follow-up**: before-rule, evidence, after-rule, `rules_in_force` per later change, paired comparison against a no-revision control (improved / worsened / unchanged, 2 % tolerance),
  success / failure / exhaustion, measurement cost and budget. Both improvement and worsening are reported. The first scarcity study's result (meta-revision lowered fired samples by 26) is **kept as UNRESOLVED / negative**.
  Artificially imposed functional conditions are separated from independent evaluation conditions (`provenance`).
* **Multi-system exchange / inheritance** (`lab/multisystem.py`): controls (no exchange), stale (`memory_delay`), wrong (`shuffled` writer), colocated placement, stop / start, per-decision counterfactual.
  The null result is kept and is now **diagnosed** into: empty store / no reads / reads without hits (no overlap) / hits without a changed decision (redundancy) / decisions changed.
  Mechanism bug, redundancy and environment constraint are different outcomes in the record. The writer is chosen on a control run and that is disclosed.
* **Variable and boundary generation**: classified as new name / transformation / compression / new identification ability / new intervention possibility / changed later conditions;
  display range vs observation boundary vs interaction structure kept apart. `activity_trend` stays at novelty 0.85 with no resolved downstream effect.
* **Non-redundancy assessment** (`study/nonredundancy.py`, `docs/NONREDUNDANCY.md`): eight axes; comparable axes (reachability via `capable_gained`, observability via `unseen_coverage`) vs not comparable
  (prediction, intervention, action on reality, temporal continuity, reorganisation); literature overlap named (Steinle, Feest, Rheinberger, Rouse, Chang, Schickore; Active Inference, active learning, adaptive control, automated science).
  **No novelty is claimed.** "Established" requires a detected, declared, comparable-axis contrast in an independent confirmatory study.
* **Level 2 paper protocol** (`docs/level2/PROTOCOL_L2_DRAFT.json`, `LEVEL2_PROTOCOL.md`, template `level2-confirmatory`): hypothesis, falsification, arms, independent seeds, primary / secondary metrics, power with its source,
  analysis plan (Holm / BH, equivalence margin, sensitivity), stopping rules, budget, storage, exploration / confirmation seed separation, condition provenance. `preregistration_issues` refuses incomplete blocks.
  **It is a draft: not frozen, not run.** Its only validation issue is the deliberately closed high-cost approval gate.
* **UI / API / report**: reachability levels, follow-up, exchange diagnoses, non-redundancy and preregistration shown in the study views and the generated Results text (verified live in the browser pane; frontend tests 82/82).

## Regression audit

Backend: see the numbers appended below (full unmodified run; nothing deselected, skipped or disabled). Frontend tsc / eslint / vitest 82/82 (last confirmed). TypeScript simulator 73/73 (re-run 2026-10-23).
Phase 3 freeze manifest: **1,526 files, no problems** (re-run 2026-10-23); the ARDS repository has no modified tracked files (HEAD 26472ca). `m2-run-9100.json` untouched. Hierarchy-split semantics untouched.
The two known failures (`test_compat[desktop-scipy]`, `test_published_records_replay`) remain, root cause recorded in `tests/test_hierarchy_diagnosis.py`, owner decision pending.

## Not done / not claimed

Stage C and D; any confirmatory run (high-cost approval not granted; the draft stays unfrozen); cross-machine or third-party reproduction; PNG / PDF outputs; variable generation and boundary change as shared operations;
action on reality and human-energy / human-readability independence (outside this environment). Level 3 is not claimed.

## Git

Branch `feat/zrs-integration`; last push was 57bc3bf (user-instructed). Everything since, including Level 2, is **local commits only**. Nothing deployed or published.

**Backend full run (2026-10-23, current HEAD, nothing deselected):** 501 collected, **499 pass, 2 fail — only the two known failures** (`test_compat[desktop-scipy]`, `test_published_records_replay`). Before the Level 2 directive: 467 pass.

---

# Final integration: total observation, planetary-scale observation, SSS, autonomous research loop (2026-10-23)

Guide: `docs/TOTAL_OBSERVATION.md`. Code: `backend/xzr/totalobs/` (new layer), `backend/xzr/lineage.py`, `backend/xzr/study/totalobs_templates.py`; UI: Experiments → New protocol (conditions form), Total observation, Research lines.

**Tests (current code).** Backend full run: 547 collected, **545 pass, 2 fail — the two known failures** (`test_compat[desktop-scipy]`, `test_published_records_replay`), neither altered, skipped or deselected.
Before this directive: 499 pass. New: `test_totalobs.py` (31), `test_totalobs_study.py` (15). Two regressions of mine were found by the existing guards in the first full run and fixed, not loosened:
`test_layering` (totalobs became its own layer; its templates moved into `study/`) and `test_security` (the conditions endpoint became a GET: a read-only computation, not a mutating route).
Frontend: tsc, eslint clean, vitest 87/87 (82 + 5 new contract tests on a stored run record). TypeScript simulator 73/73. ARDS Phase 3 manifest: 1,526 files, no problems; the ARDS repository is unchanged (HEAD 26472ca, no modified tracked files). `m2-run-9100.json`, hierarchy-split semantics, Phase 4 records: untouched.

**Scenarios completed as stored functional studies** (reserved seeds; 200 runs; all ok; three stored runs per study replayed identically; whole-study re-execution 100 % identical; package verified; ontology audit clean in every run):
`total-observation` S20261023-a6ce61ef-7ffe (84 runs, reproduced as …-f4ea), `autonomous-loop` S20261023-3112b368-55f4 (36, …-3781), `planetary-observation` S20261023-d64d110e-74f4 (48, …-90a8), `sss-axes` S20261023-1a599fc1-433f (32, …-4ad0). Study outputs are git-ignored; the ids are for this machine.
Mechanism checks (tests): distributed observation; interference (between observers, and observer on object); integration loss; objects made by the configuration (classified `configuration` by the verifier); record loss with persistent marks; order dependence; SSS axis independence, 2- and 3-way interactions, metric incomparability across a definition break; observing-condition self-revision (classification, boundary, derived variable with matched control, scale/period/integration); return to the research question; changed later experiment after a refuted hypothesis; multi-generation loop; stop / failure / expiry; save, replay, re-execution.

**Results of the functional studies — reported as found, none is evidence.** `recall_final` (verifier's recall at the last generation), 6 seeds: fixed 0.33, random-matched 0.37, adaptive 0.49, full 0.58; every contrast UNRESOLVED (e.g. adaptive − fixed 0.17, CI [0.0, 0.5]).
In the default environment history, meta-revision, variable generation, boundary redefinition and evaluation-rule revision gave results IDENTICAL to their controls: those mechanisms did not fire there (not "no effect in general"); only classification revision and the grammar extension changed the outcome (UNRESOLVED).
Under failure / outage / record loss / scarcity (`autonomous-loop`): fixed 0.16, random 0.24, adaptive 0.26, +history 0.29, +meta 0.26, full 0.28, all contrasts UNRESOLVED; meta-revision −0.006 vs adaptive (no gain). In an earlier 8-seed exploration under the same stress meta-revision *lowered* recall (0.19 vs 0.29): worsening is a possible outcome of rule revision here and is not hidden.
Hypothesis tests: many deferred or inconclusive; in 10 seeds × 12 generations 6 supported, 5 refuted, 2 coarse; a "supported" hypothesis can be far from the verifier's value (counted in the Results text). `comm-delay` and `planetary-form` arms had near-zero recall (reports older than the staleness window / sparse coverage under a small pool): failures kept.

**Capability map (`/api/studies/lineage`, computed from the file system).** Native 8 (HPO, Operational-Shape Dynamics, Robotics [laboratory mechanics only], Active Inference [research package, not an arm of the new line], Post-Active-Inference, Total Observation, Planetary-Scale Observation, SSS), Adapter 2 (ARDS, XenoBody via ARDS env1), Replay 1 (XenoSNN fixture; live snnTorch server not exercised), Reference 1 (Xenoscience), Unavailable 1 (**ANESCIRE**: no implementation or record found anywhere on this machine).

**Judgement.**
| | |
|---|---|
| A Implementation complete | **reached**: total observation (A–G), planetary conditions, SSS, autonomous loop run in the existing simulator, Study Engine, API and UI |
| B Operationally verified | **reached**: changes of observing / research conditions and of SSS were run, recorded, replayed and re-executed identically (same machine) |
| C Scientific evaluation | **not reached**: functional studies only, 6 seeds, no power plan for this line, all contrasts unresolved |
| D Non-redundancy | **not established**: assessment defaults to "not evaluated"; no Active Inference / Active Learning arm exists; literature overlap named, none excluded |
| E Ontological scope preserved | **reached for the software**: eight-layer ledger, `scope_audit` in every run, agent module structurally cut from the world and verifier (tested), all four claims false. It is a property of this model and its records, not a proof about reality |

**Open / not done.** Confirmatory evaluation of the new line (needs a protocol, power plan and the owner's approval; none started). Cross-machine and third-party reproduction. Active Inference / Active Learning arms. The agent's `silent` reason conflates an outage with a delay longer than the staleness window; `denied` vs `scale-mismatch` is handled by a cooldown, not resolved; the hypothesis test depends on a steady detector. The model is one scalar-activity family; it is not the Earth. The two known failures remain an owner decision. "Capps" in the brief was not identified to a work.
**Git.** Branch `feat/zrs-integration`, local commits only; last push still 57bc3bf (user-instructed); nothing deployed or published; no high-cost experiment, Phase 4 main experiment or confirmatory run started.

---

# Final reliability repair and research-readiness (2026-10-24)

Details: `docs/RELIABILITY_REPAIR.md`. Latest local commit at the time of writing: see `git log` (branch `feat/zrs-integration`; last push still 57bc3bf; nothing deployed).

**Tests (current code).** Backend full run: 567 collected, **565 pass, 2 fail — the two known failures**, unchanged, not skipped (`test_compat[desktop-scipy]`, `test_published_records_replay`). Before this round: 545 pass. Frontend tsc / eslint clean, vitest 87/87. TypeScript simulator 73/73.
ARDS Phase 3 manifest: 1,526 files, no problems; ARDS repository unchanged; `m2-run-9100.json`, the golden fixture and `test_lab.py` / `test_compat.py` have no diff.

**Repairs.** (1) Near-zero recall in `comm-delay` / `planetary-form`: not a determinism fault. The hub's freshness window counted from observation, so records delayed in transit were discarded on arrival (fixed layout, latency 4 and 8: nothing identified at all). `recall` measures what the research system observed, not reproducibility. Rules v2 counts the window from arrival.
(2) A missing report is no longer read as an extinct sensor: states `ok / partial / delayed / no-arrival / not-due`, a probe, an attribution recorded as such, lost records detected from the hub's own accounting, the true cause audited by the verifier (`no-arrival` ↔ failed or outage only). (3) `denied` vs `scale-mismatch` and `denied` vs `period-too-slow`: arbitrated by a stated priority with an explicit infeasibility declaration; the cooldown is a counted backstop. (4) A hypothesis is `supported` only after two consistent tests, can be withdrawn, and the verifier's agreement is recorded apart and never read by the agent (tested). (5) The two known failures: root cause re-run, nothing changed; an opt-in deterministic hierarchy method 2 exists as a separate function (default untouched; invariant where method 1 is not).
Versioning: `rules_version` v1 (default, pinned; earlier stored studies replay identically under the new code: verified) / v2 (templates). Results of the two are not compared.

**End-to-end from the UI** (protocol → create / registered digest → run → analysis → figures and Methods / Results → package → verify → replay → whole-study re-execution), small functional scale:
| environment | runs | registered digest | package | replay | re-execution |
|---|---|---|---|---|---|
| HPO world (revision-study) | 6/6 | identical | 31 files verified | agrees | 100 % (6) |
| ARDS bridge env2 (ards-comparison) | 3/3 | identical | 26 files | agrees | 100 % (3) |
| ARDS–HPO shared env3 (shared-comparison) | 4/4 | identical | 28 files | agrees | 100 % (4) |
| Total Observation v2 | 16/16 | identical | 40 files | agrees | 100 % (16) |
| Planetary-Scale (incl. drifting arms) | 10/10 | identical | 34 files | agrees | 100 % (10) |
| SSS (2³ design) | 16/16 | identical | 40 files | agrees | 100 % (16) |
| Autonomous loop under failure | 9/9 | identical | 33 files | agrees | 100 % (9) |
Completion 71/71, no failed or timed-out run; all identical on the same machine. Not exercised from the UI this round: ARDS env1, lab-population / multi-system (qualified earlier by API and tests). Cross-machine and third-party reproduction: not exercised; address-based results are not guaranteed cross-platform (the two known failures).

**Operational judgement, per environment** (no environment is assumed usable because another is).
| environment | READY — Functional | READY — Reproducible (same machine) | Confirmatory |
|---|---|---|---|
| HPO world | yes | yes | CONDITIONALLY READY: the `level2-confirmatory` draft exists (not frozen, not run); needs freeze, the cost approval and an execution approval |
| ARDS bridge (env1 / env2) | yes (test mode, replicates 3980–3989) | yes (env2 UI; env1 earlier by API) | **NOT READY by design**: the bridge refuses any non-test replicate; ARDS Phase 4 is a separate pipeline and is not started |
| ARDS–HPO shared (env3) | yes | yes | **NOT READY by design** (same bridge limit) |
| Total Observation (v2) | yes | yes | CONDITIONALLY READY: `total-observation-confirmatory` draft (3 arms, 189 fresh seeds from a 12-seed exploration, Holm, equivalence margin, provenance stating that v2 was introduced after seeing v1 results); needs freeze, cost approval (233,604 step-runs > 200,000) and execution approval — both declared and **not granted**; about 4–5 minutes on this machine |
| Planetary-Scale | yes (synthetic; no claim about the Earth) | yes | not prepared: no confirmatory draft; recall is blind to delay while sources stand still (use the drifting arms) |
| SSS | yes | yes | not prepared: interaction contrasts from 2 seeds are not evidence |
| Autonomous loop under failure | yes | yes | not prepared (the draft covers the default environment, not the stress environment) |
v1 of the total-observation line: replay of earlier studies only; do not start new studies on it.
Nothing is NOT READY for functional or exploratory use. Scientific evaluation (C) and non-redundancy (D) remain **not reached**; no confirmatory study, Phase 4 main experiment, push or deployment was started.

**To start a confirmatory study:** (a) the owner reads and accepts the draft's preregistration (hypothesis, falsification, power source, provenance) and, if wanted, changes it before freezing; (b) records `approval.high_cost` and `approval.confirmatory_run` (who, when); (c) the study is created (this registers its digest), then run; (d) a second machine or person reproduces it if cross-platform claims are wanted; (e) the owner decides on the two known failures if address-based results are to be claimed across platforms.


---

# Final certification (2026-10-24)

Evidence: `docs/certification/certification_record.json` (collected by `backend/scripts/certify_studies.py`, which re-executes every stored run in memory and changes nothing) and `docs/certification/protocol_audit.json`
(`backend/scripts/protocol_audit.py`). Operating procedure: `docs/OPERATING_PROCEDURE.md` (every command in it was executed). Reliability repair: `docs/RELIABILITY_REPAIR.md`. Branch `feat/zrs-integration`; local commits only; last push still `57bc3bf`; nothing deployed.

## Regression (current code)

* **Backend, full run, nothing deselected: 565 passed, 2 failed, 0 skipped-to-pass.** The two failures are the known ones and are unchanged: `test_compat[desktop-scipy]`, `test_published_records_replay` (`m2-run-9100.json`). No new failure.
  The run was made on the code of commit `a95cdbd`; since then only the lint configuration (`pyproject.toml` per-file ignores), two evidence scripts and documents changed (`git diff a95cdbd HEAD`): no behavioural code. Layering and API-security guards pass.
* **Frontend:** `tsc -b` and `eslint .` clean; vitest 87/87 (13 files). **TypeScript simulator:** 73/73. **Ruff:** clean.
* **Protected assets:** ARDS Phase 3 manifest — **1,526 files, no problems** (re-verified at certification); ARDS repository — 0 modified tracked files (HEAD `26472ca`); `m2-run-9100.json`, the golden fixture, `tests/test_lab.py` and `tests/test_compat.py` — no diff.
* **The two known failures** remain failing by design: the golden fixture and the stored m2 record were produced with another solver build; the cause (a degenerate eigenspace in the split of a disconnected sub-graph) is re-run by `tests/test_hierarchy_diagnosis.py`; nothing stored was changed. The opt-in `lod.hierarchy.build_hierarchy_v2` is a separate method (default untouched) and is tested to be invariant where the default is not. Whether to change the default is the owner's decision.

## Reproducibility: 264 runs, two independent checks

Replay (one stored run re-executed from its protocol alone and compared with the stored record, wall time / CPU / memory excluded) and whole-study re-execution (the registered protocol re-run into a new study and compared run by run) are separate checks; each was 100 % on every study.
**Same machine, same software versions (Python 3.12.13, scipy 1.18.1, numpy 2.5.3); no other machine or person has reproduced anything.**

| environment | experiment id | protocol digest | seeds (n, first) | runs ok/failed | run-time sum | stored files | package checksums (sha256, first 12) | figures | replay (all runs) | re-execution (new study) |
|---|---|---|---|---|---|---|---|---|---|---|
| HPO / Ziran | S20261023-455de16c-8195 | 455de16c6857 | 2, (7000,70000) | 6/0 | 6.2 s | 32 | 8a27fc279437 | 8 | 6/6 | 100 % (…-f4ff) |
| Total Observation (v2) | S20261023-2311be9b-b9aa | 2311be9b5d4c | 4, (7000,70000) | 16/0 | 1.5 s | 41 | ff56a113f926 | 7 | 16/16 | 100 % (…-bc66) |
| Planetary-Scale (v2) | S20261023-c39f962b-ff5d | c39f962b0c4b | 2, (7000,70000) | 10/0 | 1.0 s | 35 | d73d0bae5dfe | 7 | 10/10 | 100 % (…-ad61) |
| SSS (v2) | S20261023-5273a397-443d | 5273a397e95b | 2, (7000,70000) | 16/0 | 1.2 s | 41 | eb69848eeb76 | 7 | 16/16 | 100 % (…-8ebb) |
| Autonomous loop (v2) | S20261023-4a489b45-ed13 | 4a489b45f090 | 3, (7000,70000) | 9/0 | 0.6 s | 34 | e685588e45a2 | 7 | 9/9 | 100 % (…-421b) |
| ARDS bridge env2 | S20261023-970d1342-3557 | 970d13427f85 | 1, (3980,3980) | 3/0 | 184.7 s | 27 | 05a2230cc4e3 | 6 | 3/3 | 100 % (…-7c41) |
| ARDS–HPO shared env3 | S20261023-0c30f43b-feef | 0c30f43bc0da | 1, (3980,3980) | 4/0 | 229.5 s | 29 | 515f6282c833 | 7 | 4/4 | 100 % (…-4f1f) |
| **7 environments** | | | | **64/0** | | | | | **64/64** | **64/64** |
| v1 (first release) total-observation | S20261023-a6ce61ef-7ffe | a6ce61efd3ac | 6 | 84/0 | 12.6 s | 109 | 7bfdfcf55c82 | 7 | 84/84 | 100 % (…-f4ea) |
| v1 autonomous-loop | S20261023-3112b368-55f4 | 3112b36826e5 | 6 | 36/0 | 3.3 s | 61 | c8cd9f680dc0 | 7 | 36/36 | 100 % (…-3781) |
| v1 planetary | S20261023-d64d110e-74f4 | d64d110ed430 | 4 | 48/0 | 4.9 s | 73 | db1538e264d2 | 7 | 48/48 | 100 % (…-90a8) |
| v1 SSS | S20261023-1a599fc1-433f | 1a599fc1c39b | 4 | 32/0 | 3.4 s | 57 | f9ffe852ed5a | 7 | 32/32 | 100 % (…-4ad0) |
| **v1 (stored before the repair, replayed under the repaired code)** | | | | **200/0** | | | | | **200/200** | **200/200** |
| **Total** | | | | **264/0** | | | | | **264/264** | **264/264** |

All studies: registered digest identical to the protocol digest; analysis, Methods and Results written; package verified. The seven current-environment studies were created and exercised through the UI (protocol → create → run → analysis → figures → package → verify → replay → re-execution); the four v1 studies were created through the UI/API before the repair and replayed here.
Caveats: every manifest records `git_dirty: true` (the studies were made from a working tree with uncommitted changes — commit `62d26cd` for the current ones, `c8a60f2` for the v1 ones; the later commits added the confirmatory draft, an approval gate that applies only to protocols that declare it, tests and documents, none of which a run uses). The ARDS and shared studies have no `rules_version` (it applies to the total-observation line only). ARDS env1 and lab-population / multi-system were not re-run through the UI in this certification (qualified earlier by API and tests). Run times of the ARDS studies are dominated by the node bridge.

## Operational judgement, three axes per environment

| environment | functional / exploratory use | reproducibility (same machine) | technical readiness for a confirmatory study |
|---|---|---|---|
| HPO / Ziran | READY | READY (6/6 replay, re-execution 100 %) | CONDITIONALLY READY: `docs/level2/PROTOCOL_L2_DRAFT.json` is complete (15 of 16 audit items fully met) and blocked only by the cost approval (512,000 step-runs > 200,000); contrast C3 is a *declared underpowered secondary* (762 pairs needed, 200 planned): it is reported with its interval only and is not claimed as powered; C1 (25) and C2 (174) are within the 200 planned |
| ARDS bridge (env1, env2) | READY (test mode, replicates 3980–3989) | READY (env2 re-verified; env1 earlier) | NOT READY by design: the bridge refuses non-test replicates; ARDS Phase 4 is stopped |
| ARDS–HPO shared (env3) | READY | READY | NOT READY by design (same bridge limit) |
| Total Observation (v2) | READY | READY | CONDITIONALLY READY: `total-observation-confirmatory` (3 arms, 189 fresh seeds sized from a 12-seed exploration with upper-bound SDs, Holm, equivalence margin, provenance stating that v2 was adopted after seeing v1 results); blocked only by `approval.high_cost` (233,604 step-runs) and `approval.confirmatory_run`, both declared and **not granted**; all 16 audit items met |
| Planetary-Scale | READY (synthetic model; no Earth claim) | READY | not prepared: no confirmatory draft |
| SSS | READY | READY | not prepared: no confirmatory draft (2-seed interaction contrasts are not evidence) |
| Autonomous loop | READY | READY | not prepared: the draft covers the default environment, not the failure environment |
No environment is NOT READY for functional or exploratory use. v1 is for replaying earlier studies only.

## Completion axes

| axis | judgement |
|---|---|
| A — Implementation | **reached** |
| B — Operational verification | **reached**: the follow-on operation of changed conditions was run, recorded, replayed and re-executed (264/264) |
| C — Scientific evaluation | **not reached**: functional studies only; all contrasts UNRESOLVED; the improvement of v2 over v1 is a repair of a measurement rule, not evidence of superiority |
| D — Scientific non-redundancy | **not established**: assessment defaults to "not evaluated"; no Active Inference / Active Learning arm exists |
| E — Ontological scope | **reached** (software): eight-layer ledger and scope audit in every run (0 issues), the agent cut from the world and the verifier (tested), all four claims false; a property of this model, not a proof about reality |
| F — Experiment readiness | **reached**: protocols can be created, registered, run, analysed, reported, packaged, replayed and re-executed from the UI and the CLI (`docs/OPERATING_PROCEDURE.md`); confirmatory readiness is conditional as above |

**The integrated working version of XENO ZIRAN SIMULATOR is complete on A, B, E and F.** C and D are independent scientific demonstrations and remain unreached; nothing here claims scientific non-redundancy, a scientific advantage of any method, or the strong Xenoscience conditions.

## To start a confirmatory study

1. The owner accepts (or amends before freezing) a draft's preregistration: hypothesis, falsification, power source, provenance. 2. The owner records `approval.high_cost` and, for the total-observation draft, `approval.confirmatory_run` (who, when). 3. The study is created (this registers its digest) and run (about 4–5 minutes for the total-observation draft on this machine). 4. For any cross-platform claim, another machine or person re-executes it. 5. The owner decides on the two known failures if address-based results are to be claimed across platforms. This certification released no gate and started no confirmatory run, no Phase 4 experiment, no push and no deployment.


---

# Research operations baseline — regression audit (2026-10-24)

Scope: confirm that the completed integrated version is retained, in current execution results and not only in earlier reports. No new research module; the additions are an independent statistics audit, a computed usable-range table, and audit rows. Commit audited: `7216bef` (clean tree).

| check | current result |
|---|---|
| Backend, full run, nothing deselected | **566 passed, 2 failed** (the two known: `test_compat[desktop-scipy]`, `test_published_records_replay`); no new failure (565 + 1 new test) |
| Frontend | `tsc -b` and `eslint .` clean; vitest 87/87 |
| TypeScript simulator | 73/73 |
| Ruff | clean |
| ARDS Phase 3 | 1,526 files, no problems; the ARDS repository has no modified tracked file; its 6 untracked Phase 4 documents date from 2026-10-22, before this work, and were not created by it |
| Existing 11 result views (Runtime Reduction … Heterogeneous Philosophical Operations) | all present, content shown, no error banner, no JS error (browser) |
| Research lines | Native 8 · Adapter 2 · Replay 1 · Reference 1 · Unavailable 1 — unchanged (ANESCIRE Unavailable) |
| Replay of every stored run | **264/264** identical at the clean commit, in two software sets on the same machine (tiers 1 and 2 in `RELIABILITY_REPAIR.md` §9); tiers 3 (another machine) and 4 (third party) **not performed** |
| Independent statistics audit (`scripts/audit_statistics.py`, separate numpy / scipy code) | 10 stored studies, **34,554 recomputed quantities, 0 disagreements** (means, medians, sd, var, paired differences, dz, Welch, Mann-Whitney, Wilcoxon, leave-one-out) |
| Older stored analysis | `S20261022-39b6c421-6365` was analysed (2026-10-22 17:12) before the small-sample fix: its n=1 contrasts carry p=1.0. Recomputed with the current code they are undefined (INSUFFICIENT DATA). The stored file is kept unchanged as a historical artefact; the current code is correct |
| Protocol audit (`scripts/protocol_audit.py`, 19 rows) | `total-observation-confirmatory`: 19/19; `PROTOCOL_L2_DRAFT.json`: 18/19 — it declares no known incomparabilities (kept unaltered; an open condition for its registration); both are blocked from creation only by the approvals they declare |

**Usable range per environment** is now computed by the Study Engine's own validation and shown in the UI (New protocol banner and Research lines tab; also in `/api/studies/lineage` → `environments`): functional / exploratory / confirmatory / reproducibility evidence. Confirmatory is never READY: HPO and Total Observation are CONDITIONALLY READY (blocked by the declared approvals), the ARDS bridge and the ARDS–HPO environment are NOT READY by design (test replicates only), Planetary / SSS / loop have no draft. The HPO contrast C3 is a declared underpowered secondary (762 pairs needed, 200 planned): it is reported with its interval only and is not claimed as powered.
Open conditions kept: the two known failures; no confirmatory study started; the high-cost and execution approval gates closed; no other machine or third party has reproduced anything; scientific evaluation (C) and non-redundancy (D) not reached.
Completion axes unchanged and re-verified on current evidence: **A reached, B reached, E reached, F reached; C not reached, D not established.** The software completion stands; it is not a scientific demonstration.
