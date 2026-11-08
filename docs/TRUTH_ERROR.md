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
transferred or altering access; extinguishing it does not extinguish a binding constraint; and the opportunities lost by earlier denials return with neither (tested: lost opportunities never decrease; and, added in section 12, extinguishing the score leaves a binding constraint in force). This is an analogical use of "Address Domain" (what an entity can reach through a score);
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

Each arm is the control with exactly the declared change (checked), shares every random draw with the control, and every difference is a paired difference over seeds 1..20 **and again over seeds 21..40**. A difference is *replicated* only if it is beyond two standard errors on both lists with the same sign; *set-dependent* if on one list only; *not detected* if on neither. Over the nine experiments at the time of writing (the totals of all eleven, with EXP-TE12-release and EXP-TE15 added in the final verification, are in section 11.3) (517 arm-by-metric differences): 335 replicated, 28 set-dependent, 120 not detected, 34 without data (a metric that is empty in the control, such as recovery time without any approval). 131 not-detected primary results are kept in the files. A failure condition that is also checked: an arm that changes nothing in any seed (its factor inoperative) invalidates the experiment. Saved in `docs/truth_error/experiments2.json`.

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
| Q6 does an accurate classification make the constraint end | accurate classification with the release `never` against accurate with the release by score | not detected (+0.001 ± 0.001): where classification is accurate almost no constraint forms, so the release rule has nothing to act on. Q6 does not test DDAT's "even an accurate system may be unjust": the constraint is the wrong place to look for it (see section 12.3, where the harm to the correctly denied is measured) |

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
| an accurate system may still be unjust | **corrected in section 12.3:** partly expressible. The primary metrics (lost opportunities of the subjects favourable at the start) are blind to it, but an accurate classifier still lowers the real state of the subjects it correctly denies (through the resource feedback). *Structural conditions behind the score* are not modelled |
| seven generative rates (information, meaning, relational, capacity, responsibility, temporal, return) | information (new evidence updates the warrant), temporal (expiry and time) and return (restoration) are touched; **meaning, relational, capacity and responsibility generation are not modelled**, and no rate is computed |
| scoring absolutism (a score as a total judgement of the person) | not modelled; the score is a limited variable of the institution |
| the audit target is the institution, not the individual | consistent with the metrics (population-level, per arm) and with the scope: no score of a person's direction or worth is computed |

  The correspondence scope: the propositions of DDAT concern institutions of real societies; the results above are results of a finite synthetic model with declared constants. They show which of DDAT's structural claims *can be expressed and hold in that model* (self-fulfilment through allocation, the persistence of a constraint after correction, the dependence of return on timing and the release rule) and which cannot be expressed (accurate-yet-unjust, hearing, four of the seven rates). They neither confirm nor refute DDAT. The several AI-society manuscripts in the same folder were not read.
* **Operational-shape realism, 概象, Address Domain.** **Corrected in the final verification (section 11.4):** the earlier statement that no primary source was found was wrong for operational-shape realism and the Address Domain; manuscripts exist in `~/Downloads` and were retrieved. 概象 (Gaisho) has no definition in anything found.
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


## 11. Final verification of phase 2 (2026-11-03): what the results support, what the model guarantees, what remains unestablished

This section changes no model rule. Where an experiment was added it was added to answer a stated question, is labelled, and leaves the earlier experiments' content unchanged.

### 11.1 Separating the correction, the score update, the release and the restoration (EXP-TE15, with the records of TE07-TE14)

Every experiment now stores, for each arm, an `intervention_record`: the variables changed (with the values), the variables held (every other configuration field, listed), the observation period (40 periods, the late window the last 10, 120 subjects, seeds 1-20 and 21-40) and that the random draws are shared with the control. EXP-TE15 delays three things independently, 2x2x2 (approval 0 or 8, score update +0 or +8, release +0 or +8), against a control with no process, and reads the restoration of access as an outcome (the period of the first access after the approval, and its share). Mean periods (seeds 1-20): approval 11.2 or 17.5; score update at the approval or 6 periods after it (17.5 against 11.2); release at 18.7 to 24.5: **the declared delays act on exactly their own event, and the other times are not moved** (the time of the approval is identical in arms that differ only in the score update or the release).

| Contrast (main effect = mean of the four arms with the later setting minus the four with the earlier) | denial rate of favourable subjects | lost opportunities | time to restoration | Class |
|---|---|---|---|---|
| later correction (approval 8 against 0) | +0.027 ± 0.004 | +1.08 ± 0.11 | +10.4 ± 0.4 | replicated |
| later score update (+8 against +0) | +0.030 ± 0.003 | +1.12 ± 0.10 | +0.85 ± 0.28 | replicated |
| later release (+8 against +0) | +0.002 ± 0.002 (**not detected**) | +0.13 ± 0.05 | +4.4 ± 0.2 | denial not detected, others replicated |
| correction time x score update | -0.030 ± 0.003 | -1.09 ± 0.10 | -1.7 ± 0.2 | replicated |
| correction time x release | +0.013 ± 0.003 | +0.59 ± 0.08 | +2.3 ± 0.2 | replicated |
| score update x release | -0.009 ± 0.002 | -0.44 ± 0.05 | +4.0 ± 0.4 | replicated |
| three-way | +0.006 ± 0.001 | +0.17 ± 0.03 | -2.4 ± 0.2 | replicated |

(Seeds 21-40 agree in sign and detection in every row.) Reading, within the model: delaying the correction and delaying the score update each raise the late denial rate and the lost opportunities; delaying the release alone barely moves the late denial rate but delays the restoration of access; and the dependences do not add (a late score update matters less if the correction is late too: the negative interaction, the two delays being substitutes for the same lateness). The correction and the score update are two separate effects here only because the model lets the score be updated later than the approval.

**Built in, and what was found.** Some differences cannot be found because they follow from one period of the rules (`BY_CONSTRUCTION`, each checked by a test of the rule): the release never occurs under `release_mode` never; no constraint exists with `lock_after` none, so the arms are identical runs; a score that cannot deny makes its update irrelevant; each delay shifts its own event by exactly that amount; nothing is denied if nothing is adopted; the appeal is the same run when it is off. What the experiments found, and the rules do not state, are the sizes and signs of the downstream outcomes and the interactions above, and **that a correction process with an imperfect audit does not beat release by the score** (section 10.4). The non-identity of correction and release is therefore partly guaranteed (the two are separate mechanisms) and partly confirmed (when it has consequences).

### 11.2 Why the appeal changed no outcome: the transitions, read, not altered

`appeal_trace` (saved in `docs/truth_error/appeal_trace.json`, reproduced by a test) reads the TE12 open-appeal runs over seeds 1-20 against the same runs without the appeal (2400 subject-runs):

* **The appeal is connected to evidence, re-judgement, correction and the score update.** 1725 filed; 1382 submitted evidence; 998 were accepted; all 998 accepted were re-judged. 137 re-judgements followed the evidence: every one of them became a correction request in the same period, an approval exactly `approval_delay` later and a score update at the approval (137 and 137 of 137); 861 were upheld. 132 of the corrected were favourable at the start and 5 were not (the appeal follows the evidence, not the label, so it can relieve a denial that was right).
* **It is not connected to the release when the constraint ends by the score** (the TE12 setting): only 6 of the 137 corrections were followed by a release at or after the approval.
* **Why the outcomes do not move:** of 1214 subjects favourable at the start, 1 had any difference in their access history with and without the appeal. Of the 111 favourable subjects still denied at the end, none had failed to file; 70 were upheld, 22 had no evidence, 18 were not accepted, 1 were corrected and still denied. The rules explain it: a subject has **one** appeal, filed at the first denial (median period 1, when the classification window has not yet turned and the evidence does not support "z > 0"), so it is upheld; a constraint that forms later (after four denied periods) can no longer be appealed; and a favourable re-judgement only duplicates what the score is already doing.
* **The release is an event, not a state.** A release at an approval acts only on a constraint in force at that period. In the exploratory arms of EXP-TE12-release (added after the null result, labelled exploratory) the appeal made the only route to a release and was fully resourced (always filed, evidence always available, always accepted): approvals were made for 16 % of subjects (mean period about 4), **no release occurred in any seed** (all the approvals preceded the constraint), and the outcomes did not move (the matched comparison, appeal minus no appeal with the constraint released only at an approval: denial rate -0.001 ± 0.001, not detected on either list). The comparison that does move (denial +0.072 ± 0.007, replicated) switches the release rule from the score to the approval and so removes the release by the score for everyone the appeal does not reach: it is **confounded** and is shown labelled as such. A rule that releases by the score *or* at an approval would test the connection without that loss; **the model has none, and adding one after the null result would be a post-hoc change of the model, so it was not added.** It is recorded as a limit of the model, possibly a design deficiency of the one-shot appeal and of the event-type release, not as a finding about appeals in general.

### 11.3 How far the present claims are supported

| Claim | Status |
|---|---|
| Correcting a judgement does not by itself end a binding constraint, and releasing a constraint does not by itself restore access | **Confirmed in the model where a constraint forms and the score can bind** (TE07, TE15; replicated on a second seed list). **Built in as a possibility** (separate mechanisms); not shown for any real institution |
| The two are not distinguishable where the mechanism is absent | **By construction** (identical runs) and where the mechanism rarely forms (`lock_after` 8: not detected, which is not evidence of identity) |
| A late correction costs more than a late release | Confirmed in the model (TE08, TE15); depends on declared constants (TE13) |
| A correction process with imperfect audit does not beat release by the score | Confirmed in the model for audit sensitivity 0.6; not tested for other audit designs beyond TE13's 0.3 and 0.9 |
| An appeal that exists gives no relief | **Not a general claim.** In this model, with a one-shot appeal filed at the first denial, an evidence-only re-judgement and an event-type release, it changed nothing; the transitions explain why (11.2). It does not show that appeals are ineffective |
| A score-gated appeal is harmless to the outcomes | **Not claimed.** The gating blocked 57 % of subjects from filing; the outcomes are unchanged only because the appeal itself had no effect. The Low-Score Subject Guarantee Principle (11.4) is violated in that arm by design, and the model has no outcome that could register the harm |
| Self-fulfilment through allocation | Confirmed for the state-level share (Q3), not for the constraint; depends on beta |
| Anything about real credit, institutions, persons or law | **None** |

Totals over the nine experiment files plus the two added (EXP-TE12-release, EXP-TE15): 11 experiments, 645 arm-by-metric differences: 409 replicated, 35 set-dependent, 130 not detected, 71 without data; 141 not-detected primary results kept.

### 11.4 The related manuscripts: search and what they say (2026-11-03)

Searched: every .txt, .md, .tex, .docx, .pdf, .html, .rtf, .json, .py and .odt file under `~/Downloads`, `~/Desktop` and `~/Documents` (31,117 files; text layer of the PDFs, `word/document.xml` of the .docx files). Found, not found, and how much was read:

| Term | Found | Read |
|---|---|---|
| Operational-Shape Realism | `~/Downloads/ai_law_osr_r2.docx` (N. Fujie, "Operational-Shape Realism for AI Law", 31 Oct 2026, R2); `XENOSCIENCE_Representative_FINAL_Validated_2026-10-22.docx` (section 3A, Non-Closure Realism, Operational-Shape Realism and Retrospective Identification); `~/Desktop/Phase3_audit_files/99_ERRATA_AND_CORRECTIONS/THEORY_SCOPE.md` (which says the primary manuscripts were not consulted) | the AI-law manuscript **in full**; section 3A in context only; the Xenoscience book (330,000 characters) not read |
| AIスコア社会論 / AI score society | many manuscripts in `~/Downloads` (`AI_Score_Society*.docx`, `ontological_instability_ai_scored_society_*`, `score_inheritance_*`, `scored_cartesianism_*`, `New_Score_Pragmatism*`, `ddat.txt`, `ddat2.txt`, `ddat3.txt`) | only the DDAT text (section 10.9); the rest are listed, **not read** |
| Address Domain | `Planetary_Precision_State_Space_Construction.docx` ("Address-Analytic Domain Physics"); the Xenoscience book; `pa-simulation-environment/docs/ZIRAN_ADDRESS_DOMAIN_*.md` | the abstract passage only |
| Low-Score Subject Guarantee | `The_Minimum_Guarantees_Human_Legal_Subjecthood_PUBLICATION_FINAL_V3_0*.docx` (the 100-point edition adds it as "the constitutional premise") | the principle's statement; not the book (297,000 characters) |
| Data Metabolism | `~/Desktop/BIM/world-market-audit/theory/source/vol123.txt` (Volume III, chapter 5, "Data Metabolism: From Collection to Reinsertion") and the world-market-audit docs | the table of contents and abstract passages only |
| Gaisho (概象) | one occurrence, in `pa-simulation-environment/docs/ZIRAN_CURRENT_SPECIFICATION.md`, as the name of a layer that ZCA addresses ("configuration/physical state/observation/intervention/model/gaisho/concept/theory/system layers") | **no definition anywhere found** |
| 正誤的作動形状 | **no file and no text** | |
| 信用スコア作動形状浸透循環論 | **no file and no text** (the score-society manuscripts above are the nearest) | |

Not filled in: the content of the unread files, the meaning of 概象, and any manuscript named 正誤的作動形状 or 信用スコア作動形状浸透循環論. A search can have missed a file in another folder, a differently spelled title, an image-only PDF or a file inside an archive.

**The operational-shape-realism AI-law manuscript against this model.** It states the same research problem (a correction that leaves the score or the adverse status unchanged is not effective; correction must propagate through the network that propagated the error; reconstruction of the chain X to T to S to D to A with the contestation C and the restoration R kept as separate interventions; paired initial states and common exogenous inputs, otherwise only a scenario comparison; a negative result where an ordinary causal account reproduces the predictions). What the model does and does not do against it:

| Statement of the manuscript | In the model |
|---|---|
| Interventions on S, D, C and R are distinct (section 2) | the score (S), the gate and constraint (D, A), the appeal and correction process (C) and the release/restoration (R) are separate variables and were intervened on separately (TE07, TE08, TE15) |
| A corrected input that leaves the operative score or adverse status unchanged is not an effective correction (guarantee 10) | the model shows the other direction as well: a correction that updates the score but leaves a constraint (TE07); and a release that leaves the score denial (TE07-correction) |
| Correction must propagate through the network that propagated the error (guarantee 10) | institution B with `propagate_correction` and `propagation_delay` (TE05, TE09, TE13): the propagation delay moves the harm at B at the end of the periods and nothing at A |
| No score may reduce the availability of the other guarantees; interim protection may not depend on a favourable score (guarantees 2, 13; the Low-Score Subject Guarantee Principle) | the score-gated appeal is the model of a violation; see 11.3 for what its null effect does and does not mean |
| An appeal whose reviewer lacks authority (benchmark E); independent reconsideration with authority (guarantee 12) | **not modelled**: the re-judgement is an evidence-following rule with no reviewer and no authority |
| Effective re-entry and material restoration (guarantee 15) | restoration of access and the recoverability accounting (TE11); money, services, status and time are not modelled |
| Counterfactual comparisons need paired initial states and common random inputs (section 17) | satisfied by the independent random streams; **not satisfied where the real state feeds back** (beta above 0: the arm's target-state flag is false), which is stated where it applies (Q4) |
| Non-redundancy: ordinary causal accounts may reproduce the predictions (sections 7, 22) | **no non-redundancy of the operational-shape vocabulary is shown here.** The non-identity found is a property of two state variables and their update rules; an ordinary state-machine description reproduces it. The manuscript itself retains this as a live objection |
| The fifteen guarantees return separate states, never a score | the model computes no composite index of them; it has none of the fifteen guarantee evaluators |

The model variables are not identified with the manuscript's concepts: "release", "correction" and "appeal" here are the model's own transitions and carry none of the manuscript's legal content (jurisdiction, authority, remedy). Data Metabolism (collection to reinsertion) corresponds, at most, to the loop signal to classification to score to resources to the subject's state (beta); that was not compared with the text.

### 11.5 Badiou and Brassier

* **Primary sources:** no Badiou text is on this machine. The Brassier thesis (WRAP, 2001, on Laruelle and matter) is **not** used as a basis here, as asked. `rp121_article2_axiomaticheresy_brassier.pdf` (Brassier on Laruelle) mentions Badiou twice, in passing. `the-revenge-of-reason-0.docx` is by another author and mentions Badiou in passing. None bears on this model.
* **Location of the primary source (from a web search, not from a copy):** Badiou, *Peut-on penser la politique ?*, Seuil, 1985; English: *Can Politics Be Thought?*, Duke University Press, January 2019 (the publisher's page; an earlier version of this section said 2018, taken from a search summary and wrong), trans. Bruno Bosteels ([PhilArchive record](https://dc2.philarchive.org/rec/BADCPB), [Cambridge chapter on Badiou's politics](https://www.cambridge.org/core/books/alain-badiou/politics/0A679BFFFA5AC2A10F1085390B06109B)). The same search found Brassier only as translator and editor of Badiou's *Theoretical Writings* and **found no source for a Brassier critique of this book, nor for a prohibition/impossibility distinction in it.** The text was not obtained.
* **What can be said:** nothing about the argument of the book. Its concept of representation, of political intervention, the distinction of prohibition and impossibility and Brassier's critique of them are **unverified here and not supplied from memory**. The only connection available is the one already stated: this model's own definitions of "forbidden by a declared rule", "institutionally impossible" and "excluded by the score" (section 5) are formal categories of the model and are **not** a reading of Badiou. Whether they can be connected to his distinction is open until the text is read.

### 11.6 PR #3 (feat/browser-edition)

OPEN, `mergeable: CONFLICTING` (`DIRTY`): 41 files, +3,280 / -58, base `6804327`; main is now at `3e874c5`, 176 commits and 300 files later (read through the GitHub API, because `git merge-base` and `git merge-tree` are refused in this session). Of the 41 files, 25 were also changed on main; **17 of those 25 are byte-identical on main and on the PR branch** (the browser-edition scripts, `_compat`, `native`, `service/security.py`, `service/session.py`, `compare.py`; they apparently reached main through the deployment work, which was not verified), so they are not real conflicts. The files that differ are `.github/workflows/ci.yml`, `.gitignore`, `CHANGELOG.md`, `README.md`, `backend/scripts/export_static.py`, `backend/xzr/lod/hierarchy.py` and two test fixtures (`conformance_reference_wasm.json`, `test_cooperative.py`; the file API could not return them for the PR branch, so their difference is not established). 16 of the PR's files were not touched on main. Nothing was merged, forced or rewritten; the resolution (taking main's side of the shared files and keeping the PR's 16, with a hand merge of CI, README, CHANGELOG and `export_static.py`) is a decision for the owner of the PR.

### 11.7 Regression at the final commit (2026-11-03, this Mac)

| Check | Result |
|---|---|
| Backend, whole suite alone (19 min 26 s) | **1187 passed, 3 skipped** (1181 before this verification; +6 tests) |
| Frontend, whole suite alone (includes the baseline/branch comparison fix) | **544 tests: 543 passed, 1 skipped**, 0 failed |
| `ruff check xzr tests bench scripts`, `mypy xzr`, `eslint .`, `tsc -b` | clean |
| `vite build` with `VITE_STATIC=1` and with `VITE_WEBRT=1` | no truth-error code or text |
| Saved results | `experiments.json` unchanged; `experiments2.json` regenerated (11 experiments, intervention records added); `appeal_trace.json` added; all reproduced by tests |

Not pushed, not deployed. TO-C1 remains SOURCE_MISSING.


## 12. Correspondence with the existing philosophical corpus (2026-11-04)

No feature was added. The verification below compares the model's variables, transition rules, interventions and results with propositions of the author's manuscripts, retrieved and read as stated in 12.1. It corrected two statements of this document (12.3). Three levels are kept apart, as `THEORY_SCOPE.md` of the earlier phases does: what the manuscript says (theory), what the code implements (mechanism), what an experiment supports (proposition). A result at the third level is not evidence about the first.

### 12.1 What was retrieved, which version is latest, how much was read

Searched (names and text; .docx and .pdf text layers; inside .zip archives): `~/Downloads`, `~/Desktop`, `~/Documents`, the P/A and world-market-audit repositories on the Desktop, and the sibling worktrees. File dates are modification dates; dates inside a manuscript are its own.

| Asset (group) | File / version / date | Position | Read |
|---|---|---|---|
| 1. Operational-Shape Realism, AI-law line | `ai_law_osr_r2.docx`, R2 cumulative, **31 Oct 2026**: the latest *of the AI-law line* found; it is **not** the latest version of the research system as a whole (the system's latest, if it exists, was not retrieved: see the not-retrieved list below). R1 is retained inside it; no separate R1 file was found | applies OSR to AI law: X to T to S to D to A, with contestation C and restoration R as separate interventions; fifteen guarantees; falsification by matched baselines | **in full** |
| 1. OSR, foundations | `XENOSCIENCE_Representative_FINAL_Validated_2026-10-22.docx` ("Cumulative Representative Revision", 22 Oct 2026; 330,000 characters), section 3A | non-closure realism and OSR; unmeasured / unmeasurable / absent kept apart; operational establishment is not lexical adoption; vocabulary must yield | 3A, 5 and 10A **in full**; the rest not read |
| 1. earlier / related | `Minimal_Operational_Conditions_of_Science.docx` (1 Sep), `Do_the_Histories_of_Philosophy_and_Thought_Exist_FINAL_LOCKED_V16.docx` (Sep; V9 is the older), `Before_One_and_Two_PUBLIC_FINAL_V14_2026-09-20.docx`, `operational-shape-reduction/` (repository) | earlier statements of the same minimal operational vocabulary | located; V16 read at the passages on the operational vocabulary only |
| 2. Gaisho (概象) | **one occurrence**, in `pa-simulation-environment/docs/ZIRAN_CURRENT_SPECIFICATION.md`, as the name of a layer ZCA addresses | no definition anywhere | not definable from what exists; **not redefined here** |
| 2. 正誤的作動形状 | **no file and no text** (also searched inside archives and for 正誤 alone) | | none |
| 3. AI-score society, DDAT | credit-scoring paper (**16 Jun 2026**, seven generative rates); `ddat3.txt` (22 Jun, nine generative rates, capability evaluation); `ddat.txt` (23 Jun, dialectical natural efficacy); `ddat2.txt` (**26 Jun**, the self-critique, correctness-rate; 1.1 MB, the latest); many AI-score-society manuscripts of June to July (`AI_Score_Society`, `ontological_instability_*`, `score_inheritance_*`, `scored_cartesianism_*`, `New_Score_Pragmatism`, ...) | DDAT audits the institutional *direction* of scoring, not persons | the 16 Jun paper in full; `ddat2` chapter 21 and 6.3 in full; the rest **not read** |
| 3. 信用スコア作動形状浸透循環論 | **no file and no text under that or a translated name** | | none |
| 4. Address Domain | `Planetary_Precision_State_Space_Construction.docx` (10 Sep; Address-Analytic Domain Physics); Xenoscience 10A; `ZIRAN_ADDRESS_DOMAIN_RECONCILIATION.md` (6 Sep, an earlier audit of this repository) | an address says where a distinction is reached, retained or acted upon; it is not guaranteed by a name | 10A and the abstract passage |
| 4. Low-Score Subject Guarantee | `The_Minimum_Guarantees_Human_Legal_Subjecthood_PUBLICATION_FINAL_V3_0_100_POINT_EDITION.docx` (adds the principle as the constitutional premise) and V3.0 (both file dated 1 Nov) | a score may be part of the disputed decision and never decides whether the person may dispute it | the principle, the taxonomy of failures (8.6); not the book |
| 4. Data Metabolism | `world-market-audit/theory/source/vol123.txt`, Volume III chapter 5 | collection is not use; reinsertion is where an output becomes consequential | chapter 5 **in full** |
| 5. XENOSCIENCE "R78" | **no file or text carries "R78"**; the latest Xenoscience file is the 22 Oct 2026 revision above (the revision number is not in its text) | | see above |
| 6. Operational Nihilism, non-precedence of the human operational vocabulary | **"Operational Nihilism" appears in no manuscript** (only in this repository's own `TEOO.md`, as not found). The non-precedence is stated in the Xenoscience monograph (the vocabulary "must yield rather than claim metaphysical priority"; "rejects ... an unargued promotion of operational vocabulary into final ontology") and in V16 ("the operational vocabulary itself is not exempt") | | those passages |

Not read, therefore not used: the unread parts of the files above, and any file the search could not reach (another folder, a differently spelled title, an image-only PDF, an archive of another format).

### 12.2 The seven distinctions: what corresponds, what partly, what does not

| Distinction | Proposition (source) | Model variable or rule | Verdict |
|---|---|---|---|
| **Real occurrence and observability** | unmeasured, unmeasurable under the setup and absent must be distinguished; absence in the data is not absence in the system (Xenoscience 3A, 5; "indeterminacy does not count as compliance", Minimum Guarantees 8.6) | the reference state and the verification label are held by the evaluator only (REFERENCE) and no institution reads them; the sensors have separate failure kinds (occlusion, tracking lost, a silent stuck/zero/drift); `measurement_invisible` is a modality of its own; experiments separate *identical runs* (exactly 0, by construction) from *not detected* (a test with power) and from *no data* | **Corresponds in structure; partly in content.** The model has no failure kinds for scale, window or boundary mismatch, and "not detected" still mixes an absent effect with an under-powered test; it is reported as not detected, never as absent |
| **Correctness of the judgement and institutional effect** | predictive correctness (correspondence to a target) is a lower-level criterion; audit correctness is the direction of the consequence; three layers: technical accuracy, contextual validity, institutional direction (`ddat2` 21.1-21.5). Also: operational establishment is two axes, a change of vocabulary and a change of capacity (Xenoscience 3A) | `classification_correct` (layer 1); the invalid pose rule and the biased sensors (a form of layer 2); adoption, denial, lost opportunities and the real state (layer 3); adoption is a separate record from classification | **Corresponds**, with a limit: the institution's only response to a classification is denial (what DDAT calls *destiny use*). *Diagnostic use* (support instead of denial) is not modelled, so the direction cannot be varied, only the amount of destiny use |
| **Correction and release of a constraint** | a corrected input that leaves the operative score or adverse status unchanged is not an effective correction (OSR AI-law, guarantee 10); *remedial failure*: a wrongful classification identified but its consequences not stopped (Minimum Guarantees 8.6) | the correction updates the score; the constraint is a separate state with its own release rule | **Corresponds.** Section 10.4 and 11.1 give the conditions; the separation of the two is partly built into the model |
| **Extinction of the score and extinction of the institutional effect** | expiry and temporal limitation (guarantees 5, 14); a measured loss may be defective observation, inaccessible records or a genuine disappearance and must not be identified before testing (Xenoscience 10A) | `score_expiry` resets the score; `constraint_extinguished` counts releases of a constraint; the six Address-Domain states are kept apart | **Corresponds, and is now tested** (it was stated in section 5 without a test): at every expiry a subject under a constraint stays denied, and the constraint at the end is as common with the expiry as without it (0.512 against 0.510) |
| **Effective reachability and formal right of access** | a formal right is not a pathway (G2, G11, G12: reviewer without authority, effort required of the subject); an address is not guaranteed by a name (10A); the Low-Score Principle: the score may never decide who may dispute | the appeal exists, is filed, is accepted, is re-judged, corrected and followed by an outcome: five separate counts; the gated appeal violates the principle by design; **no reviewer, authority, burden of proof or cost** | **Partly.** Existence against filing against relief is separated (TE12); the gate's `access` is the effective state, with no formal-but-ineffective variant |
| **Retention of history and re-entry into what follows** | retention and re-entry are what make an operational shape (Xenoscience 3A); data metabolism: collection is not use, *reinsertion* is where an output becomes consequential (vol. III, 5); feedback loops (G14, DDAT 21.4) | measurements are not adopted unless accepted (collection is not use: tested by the arm with nothing adopted); adoption updates the score, the gate allocates, resources feed the state (reinsertion); the counters of lost opportunities and the lock keep history; `reentry_support` | **Partly.** History is retained as state (lock, counters) and re-enters only through the score and the resources; there is no retention policy, no archive and no deletion, and the one-shot appeal keeps no case history |
| **概象, concept, classification label, formal model** | 概象 is undefined in everything found; classification is a "cut", the operational vocabulary must yield (Xenoscience) | the model has a *classification label* (`classification`) and a *formal model* (the code); it has no concept variable and no 概象 | **Not confirmed.** A label and a formal model exist; 概象 and a concept layer do not, and the model's variables are **not** identified with any of them |

### 12.3 Two corrections found by the verification

1. **An accurate classification is not harmless in the model, and the primary metrics could not show it.** The primary metrics of section 10 count the lost opportunities of the subjects *favourable at the start*, so they are blind to what DDAT 21.3-21.4 calls correct predictions producing wrong futures. Measured directly (the 12 sample subjects of each of seeds 1-20, paired with a lottery run of the same seed; change of the real state z over the periods): with an accurate classifier (signal noise 0.05, classification correct above 0.97) the subjects **unfavourable at the start (n = 125) fall by 1.09 under the score against a rise of 0.08 under the lottery** (paired difference -1.165 ± 0.104), and those favourable at the start (n = 115) gain +1.307 ± 0.104 more than under the lottery. The same holds with the noisy sensor (-0.984 ± 0.106 and +1.102 ± 0.121). The score widens the gap between the two groups although it classifies both correctly. This is **built in through the declared resource feedback** (beta 0.06: a denial lowers resources, resources lower the state): it shows that the model can express DDAT's accurate-yet-harmful case, not that such a harm exists in a real institution. It is reproduced by a test (10 seeds, thresholds). Section 10.9's statement that the model could not express it, and the reading of Q6 as the test of it, are corrected above. *Structural conditions behind the score* (the other half of DDAT's claim) remain unmodelled.
2. **Score extinction:** the claim of section 5 is now tested (12.2).

### 12.4 Badiou and Brassier: what was read, the argument as far as it can be reconstructed, and the connection

* **Badiou, *Peut-on penser la politique ?* (Seuil, 1985; English: *Can Politics Be Thought?*, Duke, January 2019, trans. Bruno Bosteels): the text was not obtained.** No copy is on the machine, the archive.org search found none, and the PhilArchive record returned 403. What was reached: the publisher's page (table of contents: Threshold; 1. Destruction; 2. Recomposition; "Of an Obscure Disaster") and a review in *Marx & Philosophy Review of Books* (Sergio Valverde), which is a **secondary** account: it reports that Badiou separates *politics* (an active mode of thinking, tied to an event that opens a hole in the State's fiction) from *the political* (the domain of State power, "non-thought" with no intrinsic relation to truth), treats political philosophy as asking who is represented and counted, and follows late Althusser on history as chance and encounter. **The review says nothing about a distinction between prohibition and impossibility and none of the sources read contains one**, so that distinction is **unverified** and is not reconstructed.
* **Brassier, "Stellar Void or Cosmic Animal? Badiou and Deleuze on the Dice-Throw", *Pli* 10 (2000), pp. 200-216 (the journal's public PDF, read in full; it is not the doctoral thesis).** It is not about the 1985 book: it quotes *Abrégé de métapolitique* (1998) for Badiou's politics. The argument as it can be read: (a) Badiou's presentation/re-presentation: a situation counts its elements as one; the *state of the situation* re-presents (counts) its subsets; there are always more subsets than elements and that excess cannot be measured, so it is undecidable; (b) a subjective intervention decides the undecidable as an event and so puts it into effect; Badiou names this the dice-throw; political intervention is a generic truth-procedure whose subject is necessarily collective, and, as Brassier quotes Badiou, the political event "assigns a measure to the State's ultra-power"; (c) against Deleuze's single throw, which Badiou reads as affirming chance as fate, politically debilitating and complicit with the machinic enslavement by Capital; (d) **Brassier's own critical point**: Badiou's political translation of the excess in terms of presentation and the State leaves Capital unlocalised; defining Capital's global excess as a power-set or universal metastructure would reinstate the One, and treating it as a radically inconsistent Ober-Event would make the subjection worse than the one Badiou charges Deleuze with. "Impossible" occurs there as Deleuze's "representational im-possibility" and as what "representation considers as impossible or intolerable", not as a distinction between prohibition and impossibility.
* **Connection to the model.** Only analogies are available, each marked: the **re-presentation** (the institution's classification and score counting subjects) corresponds structurally to the model's classification, acceptance and score, as *records*, not as Badiou's state of the situation; the model has **no counterpart of the unmeasurable excess** (its representation is a function of the measurement), **of the event, of a truth-procedure or of a collective subject** (the appeal is individual); a correction here is an administrative act of the institution, not a political intervention; Brassier's critique of the unlocalised Capital has no counterpart. The distinctions the model does draw (forbidden by a declared rule, institutionally impossible, excluded by the score, section 5) are **its own definitions** and are not a reading of Badiou's prohibition and impossibility. The connection is therefore **not established, and weak at the level of the variables**; it stays a question about the 1985 text, which has to be read first. Brassier's thesis was not used.

### 12.5 What remains unestablished

The 1985 text and any account of prohibition and impossibility in it; Brassier's critique of that book (none was found; his essays reached are on ontology and on Capital); the definition of 概象; the two titles 正誤的作動形状 and 信用スコア作動形状浸透循環論; "Operational Nihilism"; any "R78"; the unread parts of the manuscripts of 12.1; and every claim about a real institution. No variable of the model is identified with a philosophical concept.

Checks for this section (2026-11-04): the two new tests and the truth-error, staging and security test files pass (the whole backend and frontend suites of section 11.7 are unchanged: no code changed, two tests were added); ruff clean. Not pushed, not deployed.

### 12.6 Verification of the evaluation metrics: the −1.17 ± 0.10 and what the primary metrics left out (2026-11-04)

**The figure checked.** The −1.17 ± 0.10 of section 12.3 was an ad hoc analysis, not a saved experiment: aggregation unit = **one subject** (the 12 sample subjects kept in full in each of seeds 1-20, 240 in all); denominator = the subjects with z0 < 0 (n = 125; the favourable n = 115); quantity = the change of the real state z from the first to the last *record* (39 updates), paired with the lottery run of the same seed and subject; dispersion = **standard error across subjects**, s / sqrt(n) (the subject-level standard deviation was about 1.16); beta = 0.06 (the default: z moves by beta x (resources - 0.5) per period, plus noise 0.02, and the resources fall by 0.12 per denied period to a floor of 0, so a denied subject falls by about 0.03 x 36 = 1.1 over 40 periods). Two things were wrong with it as a basis for a statement. A subject-level standard error treats subjects as independent units, which the design does not need (one run is the natural unit); and the reference was a lottery, which is not "no institution".

**Re-measured in the framework** (EXP-TE16, saved; one run = one unit, the mean over all of its subjects, ~60 not favourable at the start; paired difference and standard error over seeds 1-20, replicated on 21-40; z after the last update minus z0, 40 updates; beta 0.06 unless varied):

| Contrast (seeds 1-20; for the first row also seeds 21-40) | not favourable at the start: change of z | favourable at the start: change of z | gap between the two |
|---|---|---|---|
| accurate score (noise 0.05) minus lottery | **-1.134 ± 0.031** (seeds 21-40: -1.104 ± 0.028) | +1.172 ± 0.028 | +2.305 ± 0.042 |
| accurate score minus full access | -2.290 ± 0.005 | -0.024 ± 0.006 | +2.266 ± 0.008 |
| base-sensor score (noise 0.8) minus lottery | -1.002 ± 0.037 | +0.952 ± 0.033 | +1.954 ± 0.049 |
| accurate score, **no feedback (beta 0)**, minus lottery | +0.004 ± 0.030 (not detected) | +0.044 ± 0.027 (not detected) | +0.040 ± 0.040 (not detected) |

All replicated except where marked. The ad hoc figure (-1.165) agrees with the seed-level one (-1.134 ± 0.031); the larger interval of the first came from the small, subject-level sample.

**What the number is.** (1) It is **proportional to beta**: with the accurate score the change is -0.569 at beta 0.03, -1.137 at 0.06 and -2.267 at 0.12; at beta 0 it is zero. It is therefore the declared feedback times the time spent denied, an arithmetic consequence of the constants, **not a discovered magnitude.** (2) It is measured against a lottery that denies half of everyone: under it the subjects who happen to be denied fall by 1.14 as well (the lottery's mean change near 0 is the average of +1.15 and -1.14). **The correctly denied are not worse off than the randomly denied** (accurate score minus lottery, among the subjects denied at least once: -0.008 ± 0.004, not detected on both lists). What an accurate score adds is **concentration**: the whole harm falls on one group and the whole gain on the other (gap +2.3 against about 0 for the lottery), and relative to full access the not-favourable fall by 2.29. The statement "an accurate classification still lowers the real state of the correctly denied" holds against both references, but only the second is the harm of denial itself; the first measures the change of who bears it. (3) Units are those of z (standard normal at the start): the fall is about 1.1 initial standard deviations.

**What the primary metrics excluded.** The primary metrics (section 10.2) take the subjects *favourable at the start* as the denominator, so they leave out: the harm to the subjects who are not favourable at the start, including those correctly denied (change of state, resources, denial rate, denied periods); the effect on the gap between the groups; and any harm through the real state at all (the primary metrics read access and constraint, which do not move with beta). They include the favourable subjects whom the institution's own feedback pushes below zero (the denominator is fixed at the start, by design).

**Decision.** A complement was needed and was added; **no primary metric was changed or removed.** `process.COMPLEMENT_METRICS` (each with denominator, period and unit): denial rate in the late periods, denied periods per subject, share ever denied, change of z (not favourable at the start; those denied at least once; favourable at the start; the gap), resources at the end, all for the subjects not favourable at the start (z0 <= 0). They are in every run's `process.complement`, in every experiment of the saved file as extra outcomes (the primary lists are unchanged and the earlier primary values reproduce, as the existing reproduction tests check), in the pane beside the fixed metrics, and are the outcomes of EXP-TE16. The correctly-denied subset is defined by the start label and by having been denied, not by the institution's own adverse classification (the engine does not record which adopted classifications were correct). Still unmodelled: any harm not carried by the state (the institution can only deny, section 12.2).

### 12.7 Sources: what the publisher materials say, and the protocol for the transcript

* **Badiou, *Peut-on penser la politique ?*.** French edition: Paris, Éditions du Seuil, 1985 (catalogue records: Penn Libraries gives 119 pages; the Kingston and Monoskop bibliographies agree on publisher and year). **The Seuil catalogue page itself was not reached**, so the publisher's own description of the French edition is unverified; the collection name is unverified. English edition, from the publisher's page ([Duke University Press](https://www.dukeupress.edu/can-politics-be-thought)): *Can Politics Be Thought?*, trans. Bruno Bosteels, a John Hope Franklin Center Book, **published January 2019** (release date given as 7 January 2019), 152 pages, ISBN 978-1-4780-0166-9 (paper), 978-1-4780-0132-4 (cloth), 978-1-4780-0275-8 (e-book); it includes "Of an Obscure Disaster"; contents: Translator's Introduction; Can Politics Be Thought? (Threshold; 1. Destruction; 2. Recomposition); Of an Obscure Disaster. The publisher's text describes the book as distinguishing politics, an active mode of thinking, from the political, a domain of the State, and as arguing for continuing Marxist politics; it says nothing of prohibition or impossibility. **The body text of neither edition has been obtained or read.**
* **Not yet retrieved in the searchable range** (searched 2026-11-03 and 2026-11-04 over the Downloads, Desktop and Documents folders, the sibling worktrees and the zip archives there): Xenoscience "R78" (no file or text carries it; the latest Xenoscience file found is the 22 Oct 2026 revision); the manuscript on 概象 / Gaisho operational shapes; the manuscript on 正誤的作動形状. They are recorded as **not retrieved**, which is not a finding that they do not exist.
* **Brassier's critique of Badiou's political philosophy.** The lecture transcript that is to be provided separately has **not** been provided and is not on the machine (checked 2026-11-04). Until it is, nothing about it is asserted. Protocol for when it arrives, fixed now: (1) the transcript is a *record of speech* (possible transcription errors, no pagination, unknown revision by the speaker) and is kept apart from the *confirmed source text* (a published, paginated text) and from *secondary accounts* (the Valverde review); (2) a quotation is recorded with its status, *transcript-only*, *matched to the published text at page N*, or *unmatched*, and **no quotation is treated as settled while it is transcript-only**; (3) the argument is reconstructed from the transcript as the speaker's claim, then checked against Brassier's published essays (the 2000 *Pli* essay on the dice-throw, read in full; the 2006 *Continental Philosophy Review* article on presentation, abstract only) and against the text of Badiou he cites; (4) a philosophical concept is **not** assigned to a model variable mechanically: a candidate correspondence is stated with the rule it would have to satisfy and is marked *analogy*, *structural homology* or *not established*, as in 12.2 and 12.4.

Checks for sections 12.6-12.7 (2026-11-04): backend whole suite alone **1192 passed, 3 skipped** (1187 before: +5 tests); frontend whole suite alone **546 tests: 545 passed, 1 skipped**, 0 failed; ruff, mypy (221 files), eslint, `tsc -b` clean; the static and Web-runtime builds contain no truth-error code. Not pushed, not deployed.

## 13. Phase 4: operational correctness, institutional consequences and minimum guarantees (2026-11-04)

Everything earlier (TE01-TE16, the 3D research environment, the results, the negative results, the tests) is kept; the new settings default to the earlier behaviour (a test re-runs every saved arm of phases 1 and 2 and compares its digest). Everything is synthetic. The guarantee and support conditions below are **hypothetical research conditions of a synthetic institution**, not procedures for judging any real person.

### 13.1 The existing research assets, rechecked

Searched again (new files since 3 Nov, names and text of the unretrieved works): no new file, no transcript, no manuscript carrying the names below. Recorded as **not retrieved in the searchable range** (not as non-existent): Xenoscience "R78" (the latest Xenoscience file found is the 22 Oct 2026 revision), Gaisho / 概象 operational shapes (one mention as a ZCA layer name, no definition), 正誤的作動形状, 信用スコア作動形状浸透循環論, Operational Nihilism. The AI-law operational-shape-realism R2 (31 Oct 2026) is the latest **of the AI-law line only**, not of operational-shape realism as a whole. Read for this phase, in addition to section 12: the definitions of guarantees 2, 13, 14 and 15 in the Minimum Guarantees V3.0 (100-point edition) itself. They are **functions without numeric levels**: G2 no score may reduce the availability of the other guarantees (so an appeal may not be gated by the score: the existing `appeal_access` open/gated); G13 timely suspension pending review without a favourable score as a condition (modelled here as `interim_access`); G14 expiry, reassessment and an audit of the feedback loops (`score_expiry`, the complementary metrics); G15 effective re-entry and restoration, with **G15A "minimum resources" meaning the resources needed to use the procedure** (time, information, language, representation: the model's appeal effort and evidence, `appeal_filing_prob`, `evidence_available_prob`), **not a material allocation that keeps the subject's state.** So a resource floor, a cap on a run of denials, support and recovery support are **new hypothetical control conditions**, not implementations of the theory; no number is theirs.

### 13.2 EXP-TE16 reproduced, with the statistical unit stated

One run is one unit (the mean over the ~60 subjects not favourable at the start); paired over seeds 1-20 (n = 20), the same seed in both arms; subjects are never counted as units (the ad hoc figure of section 12.6 counted 125 of them). Standard error = SD / sqrt(20); 95 % interval from the t distribution with 19 degrees of freedom. `experiments2.paired_summary` computes it from the per-seed values saved in `experiments2.json`; a test recomputes every row.

| Contrast (change of the real state z, not favourable at the start unless stated) | mean | SD | SE | 95 % CI | seeds 21-40 |
|---|---|---|---|---|---|
| accurate score minus lottery | -1.134 | 0.141 | 0.031 | [-1.200, -1.068] | -1.104 ± 0.028 |
| accurate score minus full access | -2.290 | 0.023 | 0.005 | [-2.300, -2.279] | -2.271 ± 0.009 |
| gap between the groups (accurate score minus lottery) | +2.305 | 0.188 | 0.042 | [+2.217, +2.393] | +2.268 ± 0.045 |
| denied subjects only (accurate score minus lottery) | -0.008 | 0.020 | 0.004 | [-0.017, +0.001] | +0.017 ± 0.009 (not detected) |
| beta 0 (no feedback) minus lottery | +0.004 | 0.134 | 0.030 | [-0.059, +0.067] | +0.015 ± 0.029 |
| beta 0.03 / 0.06 / 0.12 minus lottery | -0.566 / -1.134 / -2.264 | | 0.030 / 0.031 / 0.035 | | |

(The levels at beta 0.03 / 0.06 / 0.12 are -0.57 / -1.14 / -2.27.) **By construction and identified.** By construction: the change of state of a subject denied in every period is beta x the sum of (resources - 0.5) = -0.06 x 19.2 = **-1.152**, and +1.152 if granted in every period (`resource_path_change`; the lottery arm's denied subjects give -1.143, full access +1.153; the noise has mean zero). Hence beta 0 gives 0, the effect is proportional to beta, and "the correctly denied are not worse off than the randomly denied" is the same number on both sides. What the experiment identified is **who is denied** under each rule (the shares of denial), which the constants do not fix: the accurate score denies 99 % of the not favourable against 50 % under the lottery, so the mean difference is about -2.3 x 0.49 = -1.13.

### 13.3 The fourteen operations, kept distinct

| Operation | Model variable or rule | Where recorded |
|---|---|---|
| 1 real state of the subject | the reference state z and the verification label (z > 0) | `reference_z`, `verification_label` (REFERENCE) |
| 2 record of the instrument | the signal and pose measurements with conditions and failure kinds | `signal_measured`, `pose_measured` (OBSERVED) |
| 3 estimation, classification | the rule on the window of the record | `classification` (CLASSIFIED) |
| 4 accuracy of the classification | agreement with the label | `classification_correct` (REFERENCE) |
| 5 evidential support of the proposition | the posterior with the declared noise | `p_positive`, `warrant` (INFERRED) |
| 6 adoption by the institution | acceptance rule (confidence, optionally the warrant) | `accepted`, event `adopted` |
| 7 generation of the score | update from adopted classifications | `score` |
| 8 institutional constraint | binding after consecutive denials | `locked` |
| 9 effect on resources and access | gate, then allocation | `access`, `resources`, `opportunities_lost` |
| 10 later change of the subject's state | beta x (resources - 0.5) plus noise | the next `reference_z` |
| 11 correction | retraction or approval, score update | events `approved`, `score_updated` |
| 12 release of the constraint | its own rule and time | event `released` |
| 13 effective recovery | access again after the approval, the recoverability accounting | event `restored`, `process.recoverability` |
| 14 re-entry of the history | the score and the resources carry it; nothing else does | `score`, `resources`, the lock |

None is assumed identical to another: each has its own record, and the experiments intervene on them separately. **The causal structure the transition rules implement** (reconstructed from the code of one period): reference state -> sensors (noise, bias, occlusion) -> window -> classification -> adoption -> score -> gate (threshold, lock, hypothetical guarantees) -> access -> resources (gain, loss, floor, support) -> the next reference state (only through beta) -> the next observation. It follows that **with beta 0 no setting of the observation, the classifier, the threshold or a guarantee can change a subject's state** (tested: the target-state digest is identical across eight such interventions and differs at beta 0.06). Interventions are the researcher's changes of one declared setting with shared initial conditions and random draws; an observed correlation in one run is not read as an effect, and every effect below is a paired difference of such interventions. No extrapolation to any real institution is made.

### 13.4 P1, P2, P3 (EXP-TE17; 26 arms; the factors and metrics were fixed in the code before the run)

* **P1: the accuracy of a classification does not guarantee the legitimacy of its institutional effect.** What the model measures is the *consequence*; it does **not** measure legitimacy, and no normative judgement is made. With the classifier correct (noise 0.05, `classification_correct` 1.000) the consequences are large (not favourable group: -2.290 against full access, gap +2.27, denial 99 %), and **they are set by other settings at the same accuracy**: the change of state of the not favourable runs from 0.00 (beta 0) to -1.14 (0.06) to -2.27 (0.12). Accuracy underdetermines the consequence in the model (a statement about the model's mechanisms, partly by construction).
* **P2: an institutional disadvantage without classification error.** With the classifier correct (99.0 % at beta 0), the not favourable are denied 97 % of the late periods and their resources end at 0.03, without any feedback (against 0 % and 1.0 under full access): the denial and the loss of resources follow from the gate's rule applied to correct classifications (by construction). The change of **state** needs the feedback (accurate, beta 0 minus lottery: +0.004 ± 0.030, not detected; with beta 0.06: -1.134). So both conditions are compared and the dependence is the one the rules fix.
* **P3: improving the accuracy changes the distribution of the disadvantage** (noise 0.8 to 0.05; every contrast replicated on seeds 21-40): denial of the favourable -0.081 ± 0.009, denial of the not favourable +0.039 ± 0.006, change of state of the not favourable -0.132 ± 0.012, of the favourable +0.219, the gap +0.351 ± 0.024: **the harm moves from the favourable subjects who were wrongly denied to the not favourable who are rightly denied.** The factors separated: the classifier (above); the allocation (gain = loss 0.06 / 0.24: the state change of the not favourable -0.95 / -1.04 against -1.005, a small change); the denial rule (threshold -0.2 / +0.2: -0.93 / -1.05; no binding constraint -0.975); the initial state (z_shift -0.5 / +0.5: -1.016 / -0.905; initial resources 0.8: -0.877); the feedback (beta 0 / 0.12: 0.00 / -1.96). The interaction accuracy x feedback equals the whole effect of the accuracy on the state (-0.132 ± 0.012: at beta 0 accuracy changes no state); accuracy x threshold, x constraint and x allocation are small (|interaction| below 0.05 on the not favourable's state; the allocation one not detected).
* **Manufactured accuracy.** The same classifier is measured as more accurate when the institution acts: `classification_correct` is 0.984 under the score at beta 0.06 against 0.880 at beta 0 (0.918 under the lottery), because the denials and grants push the subjects away from the boundary and the verification label is read at the end. Protecting the states lowers it again (support to the denied 0.12: 0.954). The accuracy reported after an institutional action is partly produced by that action (DDAT's 21.4 in the model's terms).

### 13.5 The hypothetical minimum guarantees and support (EXP-TE18; 28 arms, on a noisy and an accurate classifier)

The six conditions of the directive and what implements each (all new, default off): **minimum resource allocation** = `resource_floor`; **minimum access guarantee / conditional access** = `denial_cap` (access after a run of consecutive denials); **cap on the accumulation of a denial** = `denial_cap` (the same mechanism, read as a cap); **access kept until the correction** = `interim_access` (from an audit finding to its approval, or while an accepted appeal awaits re-judgement); **recovery support after a release** = `release_support`; **no refusal of an appeal because of the score** = the existing `appeal_access` (TE12). Support to the denied or to the low-score subjects (`support_rule`, `support_amount`, `support_capacity`) is the additional measure. Results (change of the real state of the not favourable group, paired difference from the arm's own control; seeds 1-20, replicated on 21-40 unless marked):

| Condition | noisy classifier | accurate classifier | cost (resources per subject) | note |
|---|---|---|---|---|
| resource floor 0.3 | +0.648 ± 0.005 | +0.673 ± 0.002 | 0 | the state improves; the gap narrows (-0.55 / -0.67); for the accurate classifier **the denial of the not favourable does not change** (-0.001, not detected) |
| denial cap 3 / 6 | +0.159 / +0.042 | +0.090 / +0.037 | 0 | little: the access is intermittent; denial of the not favourable falls 0.955 to 0.662 (cap 3) |
| support to the denied 0.06 / 0.12 | +0.234 / +1.296 | +0.180 / +1.174 | 1.2 / 2.1-2.3 | support equal to the loss (0.12) removes the fall; half of it removes about a fifth |
| support to the low score 0.12 (no limit / capacity 25 % / 10 %) | +1.195 / +0.188 / +0.069 | +1.158 / +0.185 / +0.069 | 2.1-2.3 / 1.2 / 0.48 | **the capacity makes it nearly useless at 10 %**: the cost falls and the improvement with it |
| floor 0.3 + cap 6 + support 0.06 (a combination: to read the interaction) | +0.930 | +0.927 | 1.1-1.2 | |
| access kept pending the correction (with the process) | +0.107 | +0.084 | 0 | the favourable gain more (+0.19) in the noisy case |
| recovery support 0.3 after the release (with the process) | +0.104 (gap not detected) | +0.100 | 0 | |
| the two process guarantees together | +0.159 | +0.144 | 0 | **sub-additive**: the interaction is -0.052 / -0.040 (they substitute) |

**Where it does not improve, what it costs, what it does to others.** Not improving or not identified: the gap under recovery support for the noisy classifier (not detected); a cap of 6 (+0.04); the denial under a floor for the accurate classifier (not detected); a capacity of 10 % (+0.07); the denial rate of the not favourable for the accurate classifier is unchanged by a floor (-0.001), by support to the denied 0.06 (-0.001), by a capacity-limited support (0.000) and by recovery support (0.000), and falls only a little under support 0.12 (-0.048 / -0.031) and access pending a correction (-0.030); the cap is the one condition that changes it (cap 3: -0.298, cap 6: -0.100), because it grants access by rule. **Costs and constraints:** the support is paid in resources, and a capacity bounds both the cost and the effect (`capacity_binding_periods` is reported). **Side effects:** protecting the states lowers the measured accuracy of the same classifier (noisy: 0.984 to 0.954 under support to the denied 0.12; to 0.967 under a floor), which is the manufactured accuracy of 13.4, not a worse classifier; the guarantees helped the favourable group too in the noisy case (their state change +0.10 to +0.20), because fewer of them are wrongly denied. **Accurate classification and the identification of recipients, measured separately:** the share of the support that reaches the not favourable (precision) is 0.995 with the accurate classifier against 0.942 with the noisy one; the support cost is the same; yet the state change of the not favourable under the same support is **lower** with the accurate classifier (+0.021 against +0.190 at support 0.12 to the low score), because the accurate classifier also denies nearly all of them in the first place (denial 0.994 against 0.955), so what it gains in identification it takes back in denial. Classification accuracy, the allocation of the support and the improvement of the real state are three different measures and they do not move together.

### 13.6 The responses of the institution

| Response | In the engine | Status |
|---|---|---|
| denial | the gate | existing |
| access kept; conditional access | `interim_access`; `denial_cap` | **added**, default off |
| resource guarantee | `resource_floor` | **added** |
| additional support | `support_rule` / `support_amount` / `support_capacity` | **added** |
| suspension of the judgement | `requires_warrant` (adopt only what the evidence supports) | existing; **not re-tested here** |
| correction; release; recovery measure | the process; the release rules; `release_support` | existing; `release_support` added |

The existing transition rules were not changed; each addition is an intervention that can be switched off, applied after the gate (access) or after the allocation (resources), and recorded apart (`guarantee_access`, `support` in the records; `process.guarantee` and the complement for the metrics).

### 13.7 The 3D research environment

The chain has a node for the hypothetical guarantee (edges to the gate and to the resources) and the pane offers **seven relations to select and compare**: sensor and subject; classifier and the observation record; score and the institutional judgement; judgement and the allocation of resources; allocation and the subject's state; correction and the release of a constraint; guarantee and the subsequent possibility. The selected relation is drawn in front of the chain and **coloured by the engine's own record at that subject and period**: green where the record satisfies the model's transition rule (access = gate or guarantee; resources = the allocation rule; change of state = beta x (resources - 0.5) + noise; classification = the rule on the recorded window; no release before its approval), red where it does not, white where there is no identity (a drawn sensor error) or it cannot be checked. A baseline and a branch (same subject, same seed) are shown side by side with the change of configuration listed first. The states are kept apart by their kind: REFERENCE (the state and the label, held by the evaluator), OBSERVED (the instrument's record), INFERRED (the posterior), CLASSIFIED, INSTITUTIONAL, and UNRESOLVED (not recorded in an older run, or nothing obtained). **The display equals the engine output:** the checks hold at every subject and period of the five saved runs (hundreds of periods per relation) and are contradicted when a record is altered (tests). The check found a real discrepancy during the work: the display computed the allocation with the support added before the clipping while the engine clips first and adds the support afterwards; the display was corrected. A line is a relation of the model's variables and **does not show that one thing causes another**: that is read from the interventions of EXP-TE07 to TE18.

### 13.8 Badiou and Brassier against the model (sources as in 12.4 and 12.7; the 1985 text and any transcript still not obtained)

| Term | What the sources read say | The model | Status |
|---|---|---|---|
| logical prohibition | not in the review (Valverde) nor in Brassier's essay | `rule_forbidden`: a rule the institution declares (its own definition) | **not established** |
| historical impossibility | the review reports an "unrepresentable point" that the dialectic reaches; no source read states a prohibition/impossibility distinction | `institutionally_impossible` (a constraint), its own definition | **not established** |
| representation | Brassier (2000): the state of the situation re-presents (counts) the subsets, an excess that cannot be measured; the review: political philosophy asks who is represented and counted | the classification and score are the institution's record of subjects: a *structural analogy*; the model has **no unmeasurable excess** (the record is a function of the measurement) | analogy only |
| intervention | Brassier (2000): a subjective, collective decision on the undecidable; the review: politics intervenes in a contingent history | correction, appeal and guarantees are administrative acts; the researcher's *intervention* on a setting is the third, interventionist sense: **three different senses** | not corresponding |
| truth-procedure | Brassier (2000): politics as a generic truth-procedure | none: the model's "truth" is the verification label, a proposition about the reference state, and the warrant is evidential support | not corresponding |
| social determination | not found in the sources read | the feedback of resources on the state | no source: **not assessed** |
| institutional classification and exclusion | the State's counting (Brassier, review) | direct: classification, denial, lock | the model's own object; correspondence **not established** |

The formal, ontological argument of Badiou (as reported) does not predict anything about a finite model, and the model's results are about its declared constants: neither confirms nor refutes the other. Brassier's critique of the unlocalised Capital has no counterpart. **Not read: the 1985 text, the 2019 translation's body, and Brassier's critique of Badiou's political philosophy in any text beyond the 2000 essay; no transcript has been provided.** Nothing is asserted about them, and no concept was assigned to a variable.

### 13.9 Limits and unresolved

The institution can only deny, support or keep access: no diagnostic use, no reviewer with authority, no cost to anyone but the support budget, no multiple institutions beyond A and B; the guarantee numbers are arbitrary research values; every state effect is proportional to the declared beta; the classifications are checked against the label read at the end (13.4); the P1 legitimacy question is not measurable here; the retrieval of the manuscripts named in 13.1 is incomplete.

### 13.10 Regression and verification (2026-11-04, this Mac)

| Check | Result |
|---|---|
| Backend, whole suite alone (25 min 44 s) | **1201 passed, 3 skipped** (1192 before; +9 tests) |
| Frontend, whole suite alone | **558 tests: 557 passed, 1 skipped**, 0 failed (546 before; +12) |
| `ruff`, `mypy` (221 files), `eslint`, `tsc -b` | clean |
| `vite build` with `VITE_STATIC=1` and `VITE_WEBRT=1` | no truth-error code or text |
| Earlier results | every saved arm of phases 1 and 2 reproduces its digest with the new settings at their defaults (tests) |
| Real screen (preview server restarted; TRUTH-ERROR tab; baseline, then a branch with a floor 0.3, a cap of 3 and support to the low score with capacity 25 %; relation "judgement and the allocation of resources") | the changes are listed first; for sample subject 3 the relation shows resources 0.000 in the baseline and 0.680 in the branch with the support 0.100 received, and the allocation rule holds in both against the record |

Not pushed, not deployed. TO-C1 remains SOURCE_MISSING; PR #3 remains conflicting (unchanged).
