# TRUTH-ERROR OPERATIONAL DYNAMICS

A research tab of the XENO ECOSYSTEM view (`?view=ecosystem&tab=truth`), an engine (`backend/xzr/truth_error`), an API (`/api/truth-error`, local runtime only) and six pre-registered experiments
(`docs/truth_error/experiments.json`). Branch `feat/xenoscience-ecosystem-3d`. Local only: not pushed, not deployed, not part of the public site.

## 0. Scope and safety (first, and enforced in code and tests)

* **Everything is synthetic.** Virtual subjects, virtual institutions, generated head poses. No real person, face, video, credit, employment, housing or other eligibility is assessed, and this module must not be used for that.
* **A head pose is a measurement with an error, nothing else.** Yaw, pitch and roll are never an indicator of truthfulness, sincerity, character, ability to repay or creditworthiness. The only classifier built on the pose (`pose_rule`) is **invalid by
  construction** (the pose is independent of the reference state unless a parameter couples them by hand; its default is 0): it exists to study what an institution does with an unwarranted meaning.
* **No face pipeline.** The package imports no face, video or image library (tested); the API takes numbers and refuses an image, a video, an identifier or an unknown field; a real-face tracker, identifier or credit scorer is not an option of this system.
* **The model says nothing about real institutions.** Its constants are this implementation's declared assumptions; a result holds for them only.

## 1. What already existed (read from the repository, 2026-11-03)

| Asset | Where | What it is | Use here |
|---|---|---|---|
| AI-scored synthetic institution | `backend/xzr/teoo/legal_v1.py` (`simulate`), `docs/TEOO.md` (EXP-01..10) | a population aggregate: latent qualification, group, inherited record, resources that feed back into the score, a capacity-ranked access, appeals, a downstream institution, `correct_at`, `score_expiry` | **conventions and ideas reused** (synthetic, seeded, probes). Not reused as the engine: it has no sensor, no classifier, no verification label, no warrant, no acceptance rule, no per-subject records, ranks by capacity (no threshold), and its correction restores access in one step |
| Address Domain | MEOS engine (`ad` block: sensing boundary, connectivity, address integrity); `pa-simulation-environment/docs/ZIRAN_ADDRESS_DOMAIN_*.md` | the address of an operational configuration (what it senses and is connected to) | the six states of a score at an institution are an **analogical** use (section 5); a formal reconciliation with the Address-Analytic Domain Theory is not established |
| xeno-capital | `ziran-xeno-simulator/src/domains/civilization.ts` | a theory layer (stores: archive, technique, institution, language, capital, infrastructure, machine) | not an experiment engine; nothing to reuse as a mechanism |
| Credit-scoring theory (DDAT) | `~/Downloads/_AI Credit-Scoring Society Is Not the End of Freedom…txt` (N. Fujie, 2026-06-16, 28 KB) | a theory text, not code | **read in full in phase 2**; the finite model is compared with its claims in section 10.9 (the several AI-society manuscripts beside it in Downloads were **not** read) |
| Badiou / Brassier | `docs/HPO.md` ("Brandom, Brassier, Sacilotto, Barad, Negarestani, Latour, Varela and Friston. None is implemented."), `hpo/registry.py` (names), `thought.ts` (a regex of names) | **names only in the code** | **correction of phase 1, which said no source text exists on this machine:** `~/Downloads/WRAP_THESIS_Brassier_2001.pdf` is Brassier's Warwick PhD thesis (473 pages, text layer); no Badiou text was found. See section 6 |

Why a new layer rather than `legal_v1`: the questions of this research (a sensor error is not a classification error; a classification is not adopted by itself; adoption is not warrant; a corrected score is not a recovered
opportunity) need the stages as **separate records**, which the aggregate engine does not have. The older engine is untouched.

## 2. The model (`xzr/truth_error`)

Each virtual subject has a reference state `z` (the evaluator's, never read by an institution) and a declared verification label `y = (z > 0)`. Stages, each its own record per subject and period:

| Stage | Record | Kept apart from |
|---|---|---|
| measurement | value, confidence, missing and its reason, for a **pose** channel (independent of `z`) and a **signal** channel (informative about `z`); sensor conditions: viewing angle, noise, per-axis calibration bias and gain, occlusion, tracking loss, an injected failure (stuck / zero / drift; a failed sensor does **not** mark itself missing) | the reference |
| measurement correctness | within a declared tolerance of the reference pose | classification correctness |
| classification | favourable / adverse / abstained, by `signal_rule` (valid), `pose_rule` (invalid by construction), `random_rule`, or none | acceptance |
| classification correctness | agreement with `y`, only where a label was assigned (an abstention is neither right nor wrong) | warrant |
| propositional warrant | what the signal evidence supports about "z > 0": SUPPORTED, REFUTED or UNDECIDED (never forced to two values), computed with the **declared** noise, so a miscalibrated sensor can mislead it | correctness |
| institutional acceptance | whether the institution adopted the classification (a confidence floor; optionally a warrant requirement) | correctness and warrant |
| score | updated from adopted classifications only; a prediction used to allocate access ahead of time, not a capacity, a virtue or a truth | |
| gate / access | threshold, reading times, a binding constraint set by consecutive denials and released by a stated condition | the score |
| resources, opportunities, the real state | what access changes (resources always; the real state `z` when `beta > 0`; how the subject is observed when `gamma > 0`) | |
| correction | a retraction at a chosen time of the adverse judgements about favourable subjects (an **oracle** retraction: it consults the verification label); it restores the score, **not** the lost resources or opportunities, and need not release a constraint | |
| transfer | a snapshot of the score sent to institution B with an evidential weight; B's own gate applies it; the correction may or may not reach B, with a delay | |

Random numbers come from independent streams (population, pose sensor, signal sensor, classifier, dynamics, lottery), so an arm that changes one thing shares every other draw with its control. Output: strict JSON (no NaN), digests of the result and of the
**target states**, full records of 12 sample subjects, rates per period, a summary.

## 3. The 3D tab

`TRUTH-ERROR` (local runtime). Runs are asked of the engine; nothing is computed in the browser. The chain floats above the arena as selectable objects (layout coordinates are schematic): subject → pose sensor / signal sensor → warrant / classifier → acceptance → score
(+ correction) → institution A's gate / institution B's gate → resources → back to the subject. The chain is not a line (acceptance has two sources, the score is acted on by a correction and read by two institutions, resources feed back). Brightness is a function of the
record of one sample subject at one period; each object carries two markers, the baseline's value and the branch's. The pose frames are an abstract axis frame, not a face: the reference pose (solid) and the measured pose (translucent) as rotations (yaw about Y, pitch about X, roll about Z).
Clicking an object selects its node: its readings are listed with their kind (REFERENCE / OBSERVED / INFERRED / CLASSIFIED / INSTITUTIONAL / UNRESOLVED) for the baseline and, beside it, for the branch.

Panels: observation field, classification field, institutional scoring field, operational consequences, historical re-entry (an appeal is **NOT MODELLED**: a correction here is a retraction), the truth-error timeline (judgement adopted, contradicted by the verification label, contradicted by the warrant, access denied,
constraint set / released, withdrawn, re-adopted, effect at B), the six Address-Domain states, five kinds of "cannot", the baseline/branch comparison (what was changed is listed first; whether the real states are identical is stated), and the saved experiments (any arm can be loaded as the baseline or the branch and re-run live).

## 4. The experiments (fixed before the runs; 20 seeds; 120 subjects; 40 periods; two sensors)

Each arm is the control with exactly the declared changes (checked by the code), and shares all random draws with it. An effect is "detected" when the paired mean differs from zero by more than two standard errors over the seeds (descriptive; no correction for the number of comparisons).
Failure conditions are evaluated and none was met. Values below are means over the seeds from `docs/truth_error/experiments.json` (reproducible: `backend/scripts/truth_error_experiments.py`; one experiment is re-run in a test and its digests compared).

**Supported within the model's assumptions**

1. **TE01, a sensor error changes the correctness of measurement, classification and warrant, and not the subjects' real states unless an institutional action changes them.** Score not used: pose measurement correct 1.00 (reference) against 0.98 (viewing angle 40), 0.31 (noise x4), 0.40 (calibration bias); classification correct 0.88 against 0.84, 0.68, 0.75; the real states are identical in all arms in every seed. With the score used and resources changing the real state (beta 0.06), the same observation conditions give different real states (identical in the reference arm only).
2. **TE01, a calibration bias can make a warrant look supported and be wrong, and its institutional effect runs both ways.** Of the SUPPORTED/REFUTED warrants, 0.227 contradict the verification label (0.005 for the reference sensor); the biased signal raises access (0.757 against 0.505) and lowers the opportunities favourable subjects lose (0.07 against 1.95): a false favourable judgement is also adopted.
3. **TE02, an invalid rule is at chance and still acts, and no worse than a lottery.** Classification correct 0.51 (valid 0.88, random 0.50). Access of favourable subjects 0.49 (valid 0.91); opportunities they lose 9.9 (valid 1.9; random 10.2; no score, lottery 10.5). The invalid rule discriminates nothing (favourable 0.49, unfavourable 0.47). **Not supported:** that it is worse than allocation by lottery (9.9 against 10.5).
4. **TE03, for identical classification results the threshold alone changes access and loss.** Classification correct 0.880 in every arm; threshold -0.40 to +0.40: access 0.564 to 0.445, access of favourable subjects 0.960 to 0.841, opportunities they lose 0.88 to 3.79 (every difference from the control detected).
5. **TE04, a correction restores the score and not what the denials took.** After a correction at period 10, the score is restored for 0.72 of the corrected subjects, yet 0.31 are still denied at the end; resources of the corrected are 0.67; with re-entry support 0.80, and still-denied unchanged (0.31). **The release condition of the constraint matters more than the correction time:** still denied after a correction at 10: 0.29 (constraint released after 1 period at or above the threshold), 0.31 (3), 0.41 (8), 0.92 (never released by score alone).
6. **TE05, the evidential capacity of a transferred judgement is separate from its force at the second institution.** Transferred from a valid rule: accuracy 0.90 at B, 0.10 of favourable subjects denied at B. From an invalid rule: accuracy 0.50 (no evidence) and 0.48 of favourable subjects denied at B all the same (threshold at B 0.12: 0.53). With the correction propagated to B the invalid rule's wrongful denials at B fall to 0.18 (the correction is an oracle retraction, so some information enters through it).
7. **TE06, a self-reinforcing denial occurred when resources change the real state, and not from a worse observation alone.** Of favourable subjects denied early, the share still denied late: 0.32 (no feedback); 0.43 (beta 0.03, not detected), 0.61 (0.06), 0.76 (0.12), 0.98 (0.4), with the share that were favourable, were denied and ended unfavourable about equal to it (0.43, 0.61, 0.76, 0.98: the denial came true). A binding constraint alone: 0.41 (detected). Worse observation of denied subjects alone (gamma 1.5): 0.31, not detected.

**Kept as results although unexplained or weak**

* TE04: the correction time changes little: opportunities lost 2.24 (at 10), 2.25 (20), 2.26 (30) against 2.37 (none); the arms were not tested against each other, so the order immediate < delayed < late (still denied 0.31, 0.35, 0.41) is a description, not a test.
* TE06: gamma 4.0 lowered persistence (0.24, detected); gamma 4.0 with beta 0.06 gave 0.35 (not detected), weaker than beta 0.06 alone (0.61). Not understood.
* TE05: propagating the correction 8 periods late equals propagating at once in the end window (0.18 and 0.18); the end window is later than the delayed correction, so this is not informative about the delay.
* 37 negative results (primary outcomes whose paired difference from the control was not detected) are listed in the file, per experiment (for example 13 in TE06, 8 in TE01 without a score, 6 in TE03).

**Not established**

Anything about a real institution, person, law or sensor; that any constant corresponds to a real quantity; that the results hold under other noise models, populations or decision rules; the size of timing effects in TE04 and TE05; the mechanism behind the gamma results; the behaviour of a real landmark model.

## 5. The score in the Address Domain, and five kinds of "cannot"

The engine keeps six states of the score at an institution as counts (`score_exists`, `score_read`, `score_transferred`, `access_altered` against a lottery, `score_extinguished`, `constraint_extinguished`). They are separate: a score can exist unread; it can be read without being
transferred or altering access; extinguishing it does not extinguish a binding constraint; and the opportunities lost by earlier denials return with neither (tested: lost opportunities never decrease). This is an analogical use of "Address Domain" (what an entity can reach through a score);
the reconciliation with `ZIRAN_ADDRESS_DOMAIN_RECONCILIATION.md` (an address is not reality; a domain is not a substance) is **not established**.

Five kinds of "cannot", defined by this model and counted per subject: forbidden by the institution's own declared rule (only where a warrant requirement is on); institutionally impossible (denied by a binding constraint, whatever the score); invisible to measurement (neither sensor obtained a value);
excluded by the predictive model (denied by the score, no constraint); reachable after an intervention (access after a correction or a release). Not exclusive, none is another (tested: the first two are never the reason of the same period).

## 6. Badiou and Brassier: a comparison that cannot be made from what exists here

* **Sources (corrected in phase 2).** Phase 1 said no source text existed on this machine; that was wrong for Brassier. `~/Downloads/WRAP_THESIS_Brassier_2001.pdf` is Brassier's 2001 Warwick thesis (473 pages, about 100,000 words in its text layer). Checked by search only, **not read in full**: it names Badiou 21 times, Laruelle about 400 times, and contains the words *error*, *institution*, *credit* and *score* two, two, one and one times in all: it is a work of metaphysics on matter and non-philosophy, and it says nothing a finite institutional model could be compared against. No Badiou text (his positions on true/false utterance, prohibition and impossibility, contingent intervention, truth procedure) was found, and the earlier research the request refers to is not in the repository. The correspondence below therefore stays **not established**; it was not filled in from memory.
* **What was done instead:** an independent formal reading **inside the synthetic model only** (section 5), with explicit definitions and the bridge conditions below. It is **not a reconstruction of Badiou's model** and nothing from it was transplanted into the institution model.
* **Bridge conditions (each is a condition for reading the formal model as a model of the institution), and their status**

| Condition | Status |
|---|---|
| a logical prohibition is representable as a rule the institution declares (only then does `rule_forbidden` count) | holds by construction (a flag of the model) |
| an institutional impossibility is an operation of a gate that outlasts the score (the binding constraint) | holds by construction; its persistence after a correction is measured (TE04) |
| a measurement invisibility is a property of a sensor channel (missing, with a reason) | holds by construction |
| a predictive exclusion is a denial by the score with no constraint | holds by construction |
| reachability after an intervention is established by an engine run, not by the record of one run | holds for the correction and release arms (TE04); the history-disabled and coupling-cut runs belong to the MEOS tab |
| the five kinds correspond to Badiou's truth positions, prohibition vs impossibility, contingent intervention or truth procedure, or to Brassier's critique | **NOT ESTABLISHED** (no source; no implementation) |
| the utterance order (who says what, when) changes what the institution can do | **NOT MODELLED**: the model has classification and adoption but not an utterance by a subject |
| an appeal is a procedure by which a subject changes what is accepted | **modelled in phase 2** as a procedure of the virtual institution (section 10.7); whether it changes what is accepted is measured, and in the saved configuration it does not move the denial rate |

## 7. MediaPipe Face Landmarker: evaluated, not integrated

The frontend has no MediaPipe dependency. `@mediapipe/tasks-vision` runs in a browser (WASM) and needs a downloaded `face_landmarker.task` model and camera or video frames. It was **not added**: it would add a dependency and an external model download (not authorised);
the first data are limited to synthetic poses and explicitly consented validation data; and a real-face pipeline must not be enabled by default. The boundary is fixed so that a later adapter cannot become a person-scoring feature: `/api/truth-error/pose` and `/run` accept **numbers only**; a consented, local
recording would be converted to yaw/pitch/roll and a confidence on the user's own device, and only those numbers would enter the sensor channel, as a measurement with an error. The classifier that may be built on it stays invalid by construction.

## 8. Files, tests, status

* Engine: `backend/xzr/truth_error/{__init__,pose,institution,experiments}.py`; API `backend/xzr/service/truth_error.py` (mounted in `app.py`); script `backend/scripts/truth_error_experiments.py`; saved results `docs/truth_error/experiments.json`.
* Frontend: `frontend/src/views/ecosystem/{truthError,truthError3d,truthApi}.ts`, `TruthErrorPane.tsx`, tab wiring in `EcosystemView.tsx`, fixtures `__fixtures__/truth-error-runs.json` (real engine runs).
* Tests: `backend/tests/test_truth_error.py` (26: determinism, independent streams, sensor model, separation of records, three-state warrant, the asymmetries above, saved-result reproduction, strict JSON, API refusals, the safety scope); `truthError.test.ts` (27), `truthError3d.test.ts` (9), `TruthErrorPane.test.tsx` (11).
* Phase 2 adds: engine `backend/xzr/truth_error/{process,experiments2}.py` (and fields in `institution.py`); results `docs/truth_error/experiments2.json`; tests `backend/tests/test_truth_error_phase2.py` (23); fixture `__fixtures__/truth-error-runs2.json`; frontend tests in the three existing test files (`truthError.test.ts`, `truthError3d.test.ts`, `TruthErrorPane.test.tsx`). Run: `PYTHONPATH=. python scripts/truth_error_experiments.py phase2` (about 2 minutes).
* Not done: MediaPipe; utterance order; a formal comparison with Badiou or Brassier; the Address-Domain reconciliation; multiple institutions beyond A and B; a 3D pose viewer with a real landmark model. (Appeals were added in phase 2.)

## 9. Regression results (2026-11-03, this Mac)

| Suite | Before this work | After |
|---|---|---|
| Backend, whole suite (20 min, alone) | 1131 passed, 3 skipped | **1157 passed, 3 skipped**, no failure (+26: the truth-error tests) |
| Frontend, whole suite, alone | 474 tests (473 passed, 1 skipped) | **521 tests: 520 passed, 1 skipped**, 0 failed (machine load 6-7) |
| `ruff check xzr tests bench scripts`, `mypy xzr` (219 files) | clean | clean |
| `eslint .`, `tsc -b` | clean | clean |
| `vite build` with `VITE_STATIC=1` and `VITE_WEBRT=1` | no local-only code | none of the truth-error code or text in either build |
| Engine staged for the public runtime and iOS (`ios/scripts/stage_engine.py`) | 59 files | 59 files; `truth_error` and its service are not staged |

Two failures of the first whole run were real findings and were fixed, not worked around: (1) the new package would have been staged into the public engine zip and the iOS engine, which `test_stage_engine.py` caught (`truth_error` and `service/truth_error.py` are now excluded there and in the test's own list); (2) `test_security.py`
lists every mutating route and asks that a new one be reviewed against the security boundary: the two POST routes (`/run`, `/pose`) were reviewed (stateless, local runtime and same origin only, 403 under `XZR_PUBLIC`, nothing stored, numbers only), added to the list with that note, and a test of the refusal under public mode and from another origin was added.

## 10. Phase 2: operational correctness, institutional persistence and effective recovery (2026-11-03)

Question of this phase: **is the correction of a judgement the same thing as the release of an institutional constraint, and under what conditions is it not?** Phase 1 (`cf4b3c1`, `ed9829f`) and its six experiments, 37 negative results, tests and the 3D research view are kept as they were: every one of the 11 saved phase-1 experiments still reproduces its `result_digest_seed1` (re-run arm by arm, a test), and the new fields have defaults that reproduce phase 1 exactly. Everything here is as synthetic as before.

### 10.1 Eight notions, kept apart

None is derived from another and no composite right/wrong index exists (the pane lists them separately; a test fixes the nine event times as separate records).

| Notion | Variable of the model (record) |
|---|---|
| measurement accuracy | `measurement_correct` (pose within tolerance) |
| classification accuracy | `classification_correct` (against the verification label) |
| evidential support of a proposition | `warrant` (SUPPORTED / REFUTED / UNDECIDED) |
| institutional adoption | `accepted`; event `adopted` |
| institutional effect | event `denied`, `locked`, `resources`, `opportunities_lost` |
| correction established | events `detected`, `requested`, `approved`, `score_updated` (and a favourable re-judgement of an appeal) |
| release of an institutional constraint | event `released` (a separate time; may never come) |
| recovery of lost subsequent possibility | event `restored`, and the recoverability accounting (10.6) |

The three conditions the request names are separate arms, not one variable: *correct judgement without effect* (accurate classification, adoption removed: TE10 Q2), *wrong judgement with effect* (the full institution, TE09/TE10 control) and *effect remaining after correction* (TE07, TE08, TE10 Q5).

### 10.2 What was added to the engine

Defaults reproduce phase 1; phase-2 output sits outside the digested `{series, summary}` (it has its own `process_digest`). A seventh random stream (appeal and audit draws) is spawned after the first six, so no earlier draw moves.

* **The correction process, per subject, with each step its own time:** an audit every `audit_every` periods reads the verification label through a declared sensitivity (0.6) and false-detection rate (0.01) (an independent review; a first version that reused the classifier's own evidence detected almost nothing and was replaced, because the same evidence cannot contradict itself); then `request_delay`, `approval_delay`, `score_delay`, and the release (`release_mode`: `by_score` = the phase-1 rule, `after_approval` = `release_delay` periods after the approval, `never`). **Correction time (`approval_delay`) and release time (`release_delay`) are independent variables.**
* **The nine times** (`misclassified, adopted, denied, detected, requested, approved, score_updated, released, restored`) for every subject; a phase-1 `correct_at` correction also records its approval and score update.
* **Recoverability** of a lost opportunity under a declared window `opportunity_window` (access returns within it: *recoverable*; the window closed first: *expired*; the periods ended first: *unresolved*; and for runs of denied periods: recoverable / partially recoverable / unrecoverable / unresolved). **Irreversibility is the setting window = 0 or none, not an assumption**: whether lost opportunities return is read from the windows. The window changes the accounting of the same access history, not the dynamics.
* **An appeal** as a procedure of the virtual institution: filing (a per-period effort probability), evidence (a probability it can be produced), acceptance (the institution's capacity), a re-judgement after `review_delay` that follows the evidence at that time, and then the correction/release of the process. `appeal_access = score_gated` is the hypothetical control in which a low score restricts access to the appeal itself, for studying institutional design danger; it is not a procedure for judging any real person. Existence, filing and relief are separate counts.
* **Fixed primary metrics**, each with its denominator, period, unit and population (`process.METRICS`, shown in the pane): access rate and denial rate of the subjects favourable at the start (z0 > 0) over the last 10 periods; lost opportunities (denied periods) per such subject; recovery time (approval to restoration, over those still denied at the approval) with its censored share beside it; persistent constraint (share under a binding constraint at the end); propagation to institution B (share of those subjects denied at B at the end). The virtual population is the same 120 synthetic subjects (z ~ N(0,1)) in every arm, 40 periods.

### 10.3 The experiments (ranges and primary metrics fixed in the code before the runs)

Each arm is the control with exactly the declared change (checked), shares every random draw with the control, and every difference is a paired difference over seeds 1..20 **and again over seeds 21..40**. A difference is *replicated* only if it is beyond two standard errors on both lists with the same sign; *set-dependent* if on one list only; *not detected* if on neither. Over the nine experiments (517 arm-by-metric differences): 335 replicated, 28 set-dependent, 120 not detected, 34 without data (a metric that is empty in the control, such as recovery time without any approval). 131 not-detected primary results are kept in the files. A failure condition that is also checked: an arm that changes nothing in any seed (its factor inoperative) invalidates the experiment. Saved in `docs/truth_error/experiments2.json`.

| Id | What varies | Why |
|---|---|---|
| TE07-release | `lock_after` (none, 2, 4, 8) x release rule (never / by score / with the approval) | does a corrected judgement end the constraint? |
| TE07-correction | `tau_a` (-5 = the score never binds, -0.2, 0) x score update (at the approval / never) with the release immediate | does a released constraint restore access? |
| TE08 | approval delay (0, 6, 16) x release delay (0, 6, 16) against two no-process references | independent timing and its interaction |
| TE09 | single-factor removal and baselines (no score, no adoption, random classification, invalid rule, no constraint, no feedback, no correction, no transfer, immediate correction/release) | what each element carries |
| TE10 | causal questions Q1-Q6 | intervention readings on the model |
| TE11 | correction timing x recovery windows (0, 2, 6, 12) | when does unrecoverability hold |
| TE12 | appeal existence, gating, evidence, capacity, review time, effort | existence is not relief |
| TE13 | one-factor sensitivity over 12 settings at 3 fixed values each (`PARAMETER_RANGES`) | robustness |
| TE14 | 2x2x2 factorial: signal noise, threshold, constraint strength | interaction |

### 10.4 The completion criterion: where the correction of a judgement and the release of a constraint are not the same, and where they are

Reading of the saved results, with their limits. **The non-identity is partly built in** (the binding constraint is a state variable separate from the score, and the correction acts on the score): what the experiments identify is *when it has consequences*, not that it exists in the world.

| Condition | Result (paired difference, mean ± se on seeds 1-20 | on 21-40) | Class |
|---|---|---|
| A constraint binds (`lock_after` 2) and the release is withheld after the correction is approved | denial rate of favourable subjects +0.121 ± 0.007 | +0.129 ± 0.009: the correction does **not** end the constraint | replicated |
| same, `lock_after` 4 | +0.052 ± 0.006 | +0.046 ± 0.006 | replicated |
| a constraint that rarely forms (`lock_after` 8) | +0.002 ± 0.001 | +0.001 ± 0.001 | not detected: neither identity nor non-identity is shown, because there is almost nothing to release |
| no constraint mechanism (`lock_after` none) | exactly 0 (identical runs) | identity holds, trivially |
| the constraint is released but the score is **not** updated, where the score can bind (`tau_a` 0) | denial rate +0.082 ± 0.006 | +0.076 ± 0.008: the release does **not** restore access (the score still denies it) | replicated |
| same, `tau_a` -0.2 | +0.057 ± 0.006 | +0.054 ± 0.005 | replicated |
| same, the score cannot deny (`tau_a` -5) | exactly 0 | identity holds, trivially |
| release **by the score** (the phase-1 rule) instead of with the approval | denial rate -0.026 ± 0.006 (`lock_after` 4) | -0.030 ± 0.006: the correction implies a release after `release_after` periods, with a lag, and also releases subjects the audit never found | replicated |

About 6 % of subjects have a constraint that is released and then bound again, with the score update as often as without it (0.058 against 0.063 at `tau_a` 0): a release is not a guarantee that the constraint ends. So: correction without release leaves a constraint wherever a constraint mechanism forms; release without correction leaves denial wherever the score can bind; and where either mechanism is absent (or nearly never forms) the two are not distinguishable in the outcomes. Timing (TE08): with the release immediate, a **late correction** (approval delay 16 against 0) raises the denial rate by +0.066 ± 0.008 and lost opportunities per favourable subject by +2.5 ± 0.2 (replicated); with the correction immediate, a **late release** (16 against 0) moves the denial rate by +0.007 ± 0.003 (set-dependent), lost opportunities by +0.28 ± 0.09 (replicated) and the recovery time by +1.04 ± 0.23 (replicated): in this model a late correction costs far more than a late release, while the release time is what sets the time to recovery. The two delays interact super-additively on denial (+0.021 ± 0.006) and lost opportunities (+0.61 ± 0.12), both replicated; on the persistent constraint at the end the interaction is not detected for 0 vs 16 and replicated for 0 vs 6 (+0.017 ± 0.006): that is **sensitive to the delay values chosen**.

A finding that qualifies the process itself (TE09): the correction process with its imperfect audit (sensitivity 0.6) does **not** lower the late denial rate against releasing by the score alone (-0.000 ± 0.006, not detected); the lost opportunities it saves, about 0.3 per favourable subject (+0.302 ± 0.151 without it), are not detected. Immediate correction and release is better than the full process by -0.023 ± 0.005, and a one-period release by the score does about as well (-0.021 ± 0.006). A correction process is not, by being there, a remedy.

### 10.5 Causal questions (TE10), common random numbers, one declared variable each

The variable changed and the variables held are recorded with each question in the file (`questions`). Intervention readings in the model, not a claim of causal necessity in the world.

| Q | Intervention | Reading |
|---|---|---|
| Q1 does classification error alone create a constraint | signal noise 0.8 -> 0.05 | lost opportunities per favourable subject 4.15 -> 0.41 (-3.74 ± 0.34), persistent constraint 0.082 -> 0.010: with the other mechanisms held, almost all of the constraint goes with the error (replicated). Not "alone": adoption, the score and the lock rule are what carry an error into a constraint (Q2) |
| Q2 does removing adoption remove the effect | `confidence_floor` 2 (the classifier classifies, nothing is adopted) | no denial and no constraint at all (-4.15 ± 0.32): the effect needs adoption. **Artefact to read with it:** with nothing adopted the score stays 0, which meets the threshold 0, so everyone has access; this is not the same as "no institution" (the lottery arm of TE09 denies 52 %) |
| Q3 does fixing resource allocation remove self-reinforcement | gain = loss = 0 (and, as a second route, beta = 0 — **identical results by construction**, both make allocation inert for the state) | the share of early-denied favourable subjects who end unfavourable falls 0.646 -> 0.135 (-0.51 ± 0.07, replicated), so the *state-level* self-fulfilment goes; the persistent constraint does not change (-0.015 ± 0.011, not detected) and lost opportunities rise by +0.64 ± 0.24 (replicated): the constraint is carried by the lock rule, not by the resource feedback. Model-dependent: the strength of the feedback (beta 0.06) is a declared assumption |
| Q4 which differences remain when only the observation changes | view angle 40, occlusion 0.25 on the signal sensor | lost opportunities +0.74 ± 0.17 (replicated); the persistent constraint +0.010 ± 0.007 (not detected). **The real states are not held here**: resources feed back (beta 0.06), so a different access moves them (the arm's target-state flag is false). With the feedback off (beta 0) the states are identical (tested by digest) and only the observation differs: lost opportunities +1.05 ± 0.13 (replicated), denial rate +0.027 ± 0.006 (replicated), persistent constraint not detected (+0.010 ± 0.006, +0.001 on the other seeds) |
| Q5 which history dependence remains after correction | audit and correction at the first audit, against no process and against an oracle with no constraint | an early correction removes -1.38 ± 0.16 lost opportunities, but **2.41 ± 0.29 remain** against the oracle (replicated), and a persistent constraint of +0.068 ± 0.008 (replicated): history survives the correction |
| Q6 does an accurate classification make the constraint end | accurate classification with the release `never` against accurate with the release by score | not detected (+0.001 ± 0.001): where classification is accurate almost no constraint forms, so the release rule has nothing to act on. This is the one place where DDAT's "even an accurate system may be unjust" would be tested; the model cannot express it (10.9) |

### 10.6 Recoverability (TE11)

Under a window of 6 periods, for subjects favourable at the start and the control without any process: per subject, 1.52 lost periods recoverable, 2.12 expired and 0.51 unresolved at the end of the periods; 62 % of denial episodes recoverable, 21 % partially, 16 % unresolved and **0 % unrecoverable**. With window 2: 0.74 / 3.24 / 0.18; with window 12: 1.94 / 1.26 / 0.96. So **unrecoverability, as complete loss of an episode, does not hold in this model for any window above 0** (episodes end by access returning, usually quickly); what does hold is *expiry of individual lost periods inside long episodes*, growing as correction is late (approval delay 20: expired +1.71 ± 0.14 per subject against the control at window 6, replicated; delay 8: +0.59 ± 0.09). Early correction (delay 0) lowers the recoverable count (-0.93 ± 0.09, replicated) because it removes denials, i.e. there is less to recover. Window 0 is the irreversible reading by definition and shows every closed episode as unrecoverable. Shares and counts per subject are both given because a share can rise when its denominator falls.

### 10.7 Appeals (TE12)

In the open appeal 72 % of subjects file (evidence is submitted by 58 %, the appeal is accepted for 42 %, 5.7 % of subjects are re-judged in their favour and 36 % upheld against). **The existence of an appeal moves none of the outcomes**: denial rate, lost opportunities and the persistent constraint differ from the no-appeal control by 0.000 to 0.005, not detected on either list. The count of subjects who end with access after a favourable re-judgement is +0.055 ± 0.003 (replicated), but it is an association, not an effect: those subjects regain access without the appeal as well (the control releases by the score). This is the model's reading of "existence of an appeal is not effective relief": filing, acceptance, re-judgement and outcome are different counts, and the counterfactual difference is zero. When the appeal itself is gated by the score, 57 % of subjects are blocked from filing and the filing share falls from 0.72 to 0.30, with no detected change in the outcomes (a design danger visible in access to the procedure, not in the outcomes of this configuration). Less evidence (0.2) or less acceptance capacity (0.2) lowers favourable re-judgements to 1.4-1.7 %; a slow review (10 periods) raises them to 9.3 %, because more subjects reach re-judgement with fresher evidence — an untested explanation. The re-judgement can only be favourable when the evidence at that time supports z > 0, which is rare: an institution that re-judges on the evidence it already holds corrects little.

### 10.8 Sensitivity and interaction (TE13, TE14)

One factor at a time (12 settings, 24 arms and the base): 78 of 144 arm-by-metric differences replicated, 11 set-dependent, 55 not detected. Large and replicated: signal noise 1.6 (+0.118 denial), `lock_after` 8 (-0.044), threshold tau_a ±0.2 (∓0.04), beta 0 (+0.099), noise 0.4 (-0.050). Insensitive within the range: `lock_after` 2 against 4 (+0.005), beta 0.12 (-0.002), audit every 4 (+0.004, set-dependent), audit sensitivity 0.9 (+0.000), release delay 4 (+0.008, not detected; 8: +0.026, detected). **An unexpected sign, recorded not explained:** auditing every period (against every 2) raises the late denial rate by +0.030 (replicated); a plausible mechanism, that an early correction is spent (one correction per subject) before a later wrongful denial, is **not tested**. The 2x2x2 factorial (TE14, all 20 contrasts replicated): main effects on the denial rate of favourable subjects, high minus low: noise +0.138 ± 0.006, threshold +0.090 ± 0.004, `lock_after` -0.084 ± 0.004; interactions noise x threshold +0.053, noise x `lock_after` -0.056, threshold x `lock_after` -0.016, three-way -0.010: the effects do not add; a strong constraint multiplies the harm of a noisy sensor.

### 10.9 Philosophical consistency (what was and was not available)

* **Credit-scoring theory (DDAT, N. Fujie, 2026-06-16).** Read in full. What the finite model can bear, by claim:

| DDAT claim | In the model |
|---|---|
| data -> prediction -> score -> classification -> access -> future possibility is the basic structure | the chain of the model is this chain (sensor, classifier, acceptance, score, gate, resources, subject) |
| low score -> less access -> weaker performance -> confirms the score (self-fulfilling closure) | expressed by the resource feedback beta; removing it removes the state-level self-fulfilment but not the constraint (Q3) |
| the danger is the conversion of a measurement into destiny (a constraint that outlives the score) | expressed by the binding constraint and its release rule; the conditions where it outlives the correction are 10.4 |
| return capacity and temporal revision are conditions of freedom | the release rule, restoration and the recoverability accounting; return depends on the release rule and on the correction time (TE07, TE08, TE11) |
| epistemic injustice: a low-scored subject is not heard | only narrowly: the appeal gated by the score (TE12). Credibility, testimony and interpretation are **not modelled** |
| an accurate system may still be unjust (structural conditions behind the score) | **not expressible**: the model has one latent state and accurate classification removes the harm (Q1, Q6) |
| seven generative rates (information, meaning, relational, capacity, responsibility, temporal, return) | information (new evidence updates the warrant), temporal (expiry and time) and return (restoration) are touched; **meaning, relational, capacity and responsibility generation are not modelled**, and no rate is computed |
| scoring absolutism (a score as a total judgement of the person) | not modelled; the score is a limited variable of the institution |
| the audit target is the institution, not the individual | consistent with the metrics (population-level, per arm) and with the scope: no score of a person's direction or worth is computed |

  The correspondence scope: the propositions of DDAT concern institutions of real societies; the results above are results of a finite synthetic model with declared constants. They show which of DDAT's structural claims *can be expressed and hold in that model* (self-fulfilment through allocation, the persistence of a constraint after correction, the dependence of return on timing and the release rule) and which cannot be expressed (accurate-yet-unjust, hearing, four of the seven rates). They neither confirm nor refute DDAT. The several AI-society manuscripts in the same folder were not read.
* **Operational-shape realism, 概象, Address Domain.** No primary definition of 概象 or of operational-shape realism was found; the words occur in this repository's own documents (`TEOO.md`, `ECOSYSTEM_MEOS*.md`, `CHANGELOG.md`), which are not sources. Nothing was inferred or completed. The Address-Domain use stays analogical (section 5).
* **Badiou and Brassier.** Section 6. The formal model (this section) and the political-philosophical argument are kept apart: nothing in the engine, the experiments or the pane is taken from either. The Brassier thesis found is on Laruelle and matter; a correspondence with the model is not established.
* **Novelty.** That prior work leaves parts unmeasured does not make the truth-error operational shape new, and no novelty is claimed.

### 10.10 The 3D view

The four paths (judgement, effect, correction, subsequent) are lines along the **existing edges of the chain**, one segment for each step that is a transition on an edge (the scene adds two edges that are real transitions of the model: the audit/appeal reading the verification label into the correction, and the correction releasing a gate). A segment is lit in its path's colour when the step holds for the selected subject at the selected period, read from the engine's events and records (`stepReached`); otherwise it is dark. The branch's segments are drawn just below the baseline's, lit by the branch's own record; tests check every segment is a real edge, that lit means the recorded time is at or before the period, and that the branch lines appear only with a branch. A step with no edge of its own (a state, an appeal stage) appears in the pane's table only. The pane lists, for the same subject (same seed) in baseline and branch, the period of each step, the difference and its direction (`earlier`, `later`, `only in the branch`, `only in the baseline`); a step present in one run only is never shown as a delay. The lines are not causal arrows.

### 10.11 Negative results, model dependence, and what was wrong on the way

* Kept: 131 not-detected primary results (files); Q6 and N1 at `lock_after` 8 show a release rule that matters nothing where nothing forms; the appeal's null effect; recovery time and persistent constraint interactions that depend on the delay values.
* Model dependence: every sign above depends on declared constants (noise 0.8, beta 0.06, audit sensitivity 0.6, thresholds, window lengths); TE13 and TE14 show which are influential, none shows a universal.
* Errors found by testing and fixed: (1) the first audit read the classifier's own evidence and found 1 subject in 120; (2) a recovery time of 0.0 was an artefact of counting subjects who had access before the approval; now only subjects still denied at it are counted; (3) the experiments' "no correction process" controls had release `after_approval` with no approvals, i.e. a constraint that could never end, while labelled as ending by the score: relabelled and rebuilt (the controls now release by the score, and a separate arm never releases), which changed TE08-TE12; (4) the first TE08 grid never switched the audit on in its arms, so its first output was a table of identical rows — this led to the check that an arm identical to its control in every seed invalidates the experiment; (5) TE11 first reported episode shares that hid right-censoring (every long episode was "unresolved"), so per-subject counts of all three classes were added; (6) "effective relief" counted an association and was renamed.

### 10.12 Regression and verification (2026-11-03, this Mac)

| Check | Result |
|---|---|
| Backend, whole suite alone (20 min 34 s) | **1181 passed, 3 skipped** (before: 1157 / 3; +24 phase-2 tests), no failure |
| Frontend, whole suite alone | **543 tests: 542 passed, 1 skipped**, 0 failed (before: 520 / 1; the comparison fix below added one test after this run; the ecosystem folder, 23 files, was re-run green) |
| `ruff check xzr tests bench scripts`, `mypy xzr` (221 files), `eslint .`, `tsc -b` | clean |
| `vite build` with `VITE_STATIC=1` and with `VITE_WEBRT=1` | no truth-error code or text in either build |
| Public/iOS engine staging | unchanged (`test_stage_engine.py` passes; `truth_error` is excluded) |
| Phase-1 saved experiments | every arm of all 11 reproduces its `result_digest_seed1` |
| Real screen (preview server restarted, TRUTH-ERROR tab, baseline and a branch with audit every 2, approval delay 2, release never) | the nine times, four paths, metrics, recoverability and appeal tables render; the 3D chain shows the path lines. **A bug found only on screen and fixed:** the baseline/branch comparison said "nothing changed" because `compareRuns` did not list the phase-2 settings; it now lists them (test added). For sample subject 2 the screen shows correction without release: approved at 12 (earlier than the baseline's 18), never released, never restored, against the baseline's release at 15 and access at 18 |

Not pushed, not deployed.
