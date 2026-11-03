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
| Credit-scoring theory | `~/Downloads/_AI Credit-Scoring Society Is Not the End of Freedom…txt` and related | theory texts, not code | not parsed or implemented |
| Badiou / Brassier | `docs/HPO.md` ("Brandom, Brassier, Sacilotto, Barad, Negarestani, Latour, Varela and Friston. None is implemented."), `hpo/registry.py` (names), `thought.ts` (a regex of names) | **names only** | **no implementation and no source text exists on this machine** (the Downloads folder was searched, including .docx) |

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

* **Sources:** none. The repository holds the names only (`HPO.md`: "None is implemented"), and no text of or on Badiou, his true/false utterance positions (left, right, centre), prohibition and impossibility, contingent intervention or truth procedure, or on Brassier's critique, was found on this machine. The earlier research the request refers to is not in the repository.
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
| an appeal is a procedure by which a subject changes what is accepted | **NOT MODELLED** here (`legal_v1` models appeals separately; a correction here is a retraction by the institution) |

## 7. MediaPipe Face Landmarker: evaluated, not integrated

The frontend has no MediaPipe dependency. `@mediapipe/tasks-vision` runs in a browser (WASM) and needs a downloaded `face_landmarker.task` model and camera or video frames. It was **not added**: it would add a dependency and an external model download (not authorised);
the first data are limited to synthetic poses and explicitly consented validation data; and a real-face pipeline must not be enabled by default. The boundary is fixed so that a later adapter cannot become a person-scoring feature: `/api/truth-error/pose` and `/run` accept **numbers only**; a consented, local
recording would be converted to yaw/pitch/roll and a confidence on the user's own device, and only those numbers would enter the sensor channel, as a measurement with an error. The classifier that may be built on it stays invalid by construction.

## 8. Files, tests, status

* Engine: `backend/xzr/truth_error/{__init__,pose,institution,experiments}.py`; API `backend/xzr/service/truth_error.py` (mounted in `app.py`); script `backend/scripts/truth_error_experiments.py`; saved results `docs/truth_error/experiments.json`.
* Frontend: `frontend/src/views/ecosystem/{truthError,truthError3d,truthApi}.ts`, `TruthErrorPane.tsx`, tab wiring in `EcosystemView.tsx`, fixtures `__fixtures__/truth-error-runs.json` (real engine runs).
* Tests: `backend/tests/test_truth_error.py` (26: determinism, independent streams, sensor model, separation of records, three-state warrant, the asymmetries above, saved-result reproduction, strict JSON, API refusals, the safety scope); `truthError.test.ts` (27), `truthError3d.test.ts` (9), `TruthErrorPane.test.tsx` (11).
* Not done: MediaPipe; appeals; utterance order; a formal comparison with Badiou or Brassier; the Address-Domain reconciliation; multiple institutions beyond A and B; a 3D pose viewer with a real landmark model.

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
