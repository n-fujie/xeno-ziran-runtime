# GAISHO — Operational Shape Laboratory

A research function of the existing XENO ZIRAN SIMULATOR (tab **GAISHO** of the XENO ECOSYSTEM view; engine `backend/xzr/gaisho`; API `/api/gaisho`). It executes **synthetic computational experiments** in which a candidate operation is
intervened on, observed under chosen observation conditions and compared; its operational shapes are built from what those runs recorded. It is local-only (403 under `XZR_PUBLIC`, excluded from the public build and the iOS engine), stateless
and deterministic.

## What it is not

* It never computes a Gaisho attribution. An operational difference is not evidence of a Gaisho; the attribution level stays `UNRESOLVED` unless a researcher supplies independent evidence, and then it is only recorded as `ASSERTED_BY_RESEARCHER`.
* It shows nothing about human neural activity, the formation of a real Gaisho, or a universal law. Every domain is a declared model with declared constants.
* It does not implement the 150–200 concepts; it implements five domains (below), each judged on its own.

## Source status

The manuscript **GAISHO R37** (Fujie, 3 November 2026; `~/Downloads/gaisho_r37(1).docx`, 784k characters) reached the machine on 2026-11-05 and was read **in part**; the correspondence below is exactly as far as that reading goes.
**Read in full or nearly so:** Abstract and Preface; Part II §§4–5 and its individuation, two-evidential-tracks, G–C–N, four-way, six-register, equivalence-and-reduction, action-identical-episodes, intervention-order, proxy, failure-to-individuate, causal-mediator, limited-discrimination and levels-of-claim passages; all of Part III; Part X (programme, seven arms, failure registries, counterexamples, withdrawal); most of Part XII; **Appendix A** (A.1–A.3 including the randomized-questioning and report-indeterminacy results, A.3e, A.5, A.6 opening); **Appendix B.2b**; the Appendix C cross-index (001–044).
**Read in part:** Part I (the two inferential prohibitions), Part V (the Scale–Size–Speed passage), Part VIII (the four sites of credit classification, the Score-Subject Agent, reversible renaming against executed classification).
**Headings only, NOT read:** the rest of Part II, Parts IV, VI, VII, IX and XI, the rest of Parts V and VIII, Appendix B.2c–B.5 (the inherited R13–R18 studies) and the rest of Appendix C. This is therefore **not** a full-text verification of the 784k-character manuscript.
**Not available:** the **P/A Dictionary v40 itself (181 pages)** — only R37's cross-index of its headwords is on this machine (searched every docx under Downloads and Desktop); no entry's own definition (022 *Non-Accidental Success* included) has been checked, so claim U3 cannot be resolved. `gaisho_001.py` and a definition of 概象 outside R37 still do not exist here.

**What R37 says that matters most for this laboratory** (section numbers are R37's; the code is `xzr/gaisho/r37.py`, with each constraint and its status in `r37.CONSTRAINTS`, shown in the pane):

* Gaisho is a *candidate* mode of thought-related operation: an **episode** of orientation of a bearer *b* over an interval *τ* toward a directed relation *ω*. Occurrence `Occ_G(b,τ,ω)`, detectability `Det_D(K,τ)` and attribution `A_G(b,τ,ω;e,K) ∈ {supported, defeated-for-K, unresolved}` have different codomains; absent rivals, provenance, admissible interventions and an individuation rule, "the verdict is unresolved rather than negative" (II §4). A candidate causal mediator `M_G` has a different logical type, so a successful manipulation of it can leave `A_G` unresolved.
* **A failed applicability check precedes, and is not coded as, a defeated-for-K judgment.** The laboratory's synthetic operations have no eligible bearer, interval or directed relation: the attribution is recorded `UNRESOLVED` **with an applicability gate `NOT_PASSED`** (new in this pass), which is not an assertion that no thought-related episode occurs.
* Six registers — `A_G`, `C` (conceptual operational shape), `P` (prereflective orientation), `E` (expressive act), `N` (normative standing), `I` (institutional execution) — are separate, with no inference among them (`registers()` records them per domain; `C`, `E`, `N` are NOT_MODELLED; `P` is executed only in the body domain, `I` only in the credit domain).
* **Knowledge is not Gaisho.** R37 keeps the epistemic family of the P/A Dictionary (013–024: constitution, detection, attribution, entitlement, effective defeater, **non-accidental success (022)**, continuity, withdrawal) apart from Gaisho: "five separate results", and these distinctions "prevent a Gaisho episode from replacing epistemic justification"; "the link remains research-dependent rather than a settled account of knowledge". **R37 has no "knowledge Gaisho".**
  The laboratory's knowledge domain is therefore re-described as an operational report on *non-accidental success of a synthetic judgement* (it was titled "knowledge attribution", which in the Dictionary is entry 019, a third-party attribution the laboratory does not compute). It is not a Gaisho candidate. Claim **U3** (below) is UNVERIFIED.
* Ignition is "a transition from a specified prior configuration to an episode that meets the stated attribution criteria"; persistence, expiry, re-ignition and re-entry are different operations; re-ignition needs a justified relation to the prior episode (III). The laboratory has no episode, so the fields of its research objects called ignition, maintenance, expiry and re-ignition are now labelled **OPERATIONAL ANALOGUE ONLY**.
* R37's own **H1–H3 are three formation histories** of an orientation under a question (retrieved by it, constituted by it, a partial disposition transformed by it). They are unrelated to this laboratory's claims; the laboratory's hypothesis identifiers were renamed **U1–U4** to remove the collision, and R37's H1–H3 are listed as not modelled.
* The comparative protocol distinguishes (a) a local philosophical correction, (b) an observationally supported episode attribution, (c) an identified non-redundant mechanism; the equivalence challenge needs a frozen inquiry **Q**, and only a difference surviving an equal-information, equal-cost adversarial comparator supports (c). The laboratory makes none of the three claims for a Gaisho (R6 NOT_IMPLEMENTED); its comparators now carry an explicit Q block and say that outcome (iii) is **not assessed**.
* X: the **fourth study family** is the one the body domain follows ("sensor morphology, memory, available world intervention and resource conditions determine different future continuation classes, without inferring a thinking subject from a classifier"); the **seven arms A–G** (laboratory: A and G partial, B–F not executed, missing cells marked); **five non-exchangeable failure registries** (every kept negative result is now labelled with its registry); separate estimands, no common score.
* Differences kept on purpose: the laboratory's level "Gaisho operational shape" has **no R37 counterpart** (R37 has `Occ_G` and `M_G`); the unobserved class `IDENTIFICATION_UNRESOLVED` and the state `ASSERTED_BY_RESEARCHER` are the laboratory's own, not R37's (R37's five access failures: unmeasured, instrument-, scale-, window-incompatible, boundary-induced invisibility).

## The five levels (never merged into one state)

`real_operation` · `operational_shape` · `conceptual_operational_shape` · `gaisho_operational_shape` · `gaisho_attribution` (`model.attribute`). The laboratory fills the first two; the third is `NOT_MODELLED`; the Gaisho operational shape is
`NOT_ESTABLISHED` (a synthetic operation has no bearer and no historical interval); the attribution is `UNRESOLVED`. Eight inferences are refused with a reason (`model.refuse`): spike → Gaisho fired, concept classification → Gaisho established,
internal-state change → thinking, complex 3D shape → Gaisho exists, accuracy → knowledge, attribution success → judgement true, institution evaluation → individual Gaisho, operational difference → attribution.

## Engine

* **Operational Difference Engine** (`lab.py`): a domain supplies candidate operations, two intervention axes and an executed `simulate(condition, seed, observation)`. One run is one replication unit; seeds have independent streams, and conditions share
  them (common random numbers); differences are paired over seeds with t-based 95 % intervals (n = 20: 2.093).
* **Total relational observation** (`Observation`, ten axes): sensor (noise, channels), scale, temporal window, speed, coupling (intervened / passive), resources, memory, environment, probe (the observer perturbs the operation), boundary.
  Only the temporal window, the environment and the probe change the **realized operation**; the rest change the **record**. `compare_observations` says which it was (`SAME` / `RECORD_DIFFERENCE` / `OPERATION_DIFFERENCE` / `UNOBSERVED_IN_ONE`).
  A relation or region that an observation cannot identify is kept with its class: `UNMEASURED`, `INSTRUMENT_MISFIT`, `SCALE_MISFIT`, `TEMPORAL_MISFIT`, `BOUNDARY_INVISIBLE`, `IDENTIFICATION_UNRESOLVED`.
* **Shapes** (`shape.py`): built from the *recorded* response surface over the two interventions — vertices (recorded cells), edges, cuts (neighbours differing ≥ 0.5), branch points (the 0.5 crossings), unresolved cells. Every element carries its provenance
  class and the digest of the operation it came from; the mapping to a drawn figure is declared a `VISUALIZATION_PROJECTION`. Different conditions give different shapes; no geometry is fixed in advance.
* **Competing explanations** (`compare.compare_models`): same information, same held-out interventions; verdicts `NON_REDUNDANT / REDUNDANT / HARMFUL / UNRESOLVED / CRITERION_NEGATIVE`, never added into a score.
* **Record, restore, figure** (`export.py`, `figure.py`): a record is the specification + seeds + model version + digests + negative results; `restore` re-runs the specification and compares the digest. The figure (white ground, black/grey lines, one
  blue) is regenerated from the record and carries its kind (`EXECUTED_COMPUTATIONAL_EXPERIMENT`, …).

## Domains and their status

| id | domain | status |
|---|---|---|
| 001-knowledge (non-accidental success as an operational difference; not a Gaisho candidate) | accidental-correct (base rate / coincidental cue), ground-responsive, miscalibrated misjudgement, correction and reconfiguration with and without feedback | `INITIAL_EXPERIMENT_EXECUTED` |
| 002-bias | selectivity, training-history prior, sensor/body offset | `INITIAL_CONDITIONS_EXECUTED` |
| 003-freedom | self-interpretation, effective possibility, institutional classification, constraint | `INITIAL_CONDITIONS_EXECUTED` |
| 004-body | a planar body (XB-TRO) under a sensory delay and a disturbance; the continuation class (falls or not) | `INITIAL_CONDITIONS_EXECUTED` **only where the XB-TRO link is configured** (B1: `XZR_XBTRO_PATH`); otherwise `NOT_EXECUTED`. No spiking component: XenoSNN is not connected |
| 005-credit | institutional score and access, running the existing TRUTH–ERROR engine unchanged | `INITIAL_CONDITIONS_EXECUTED` |

One domain being executed completes no other.

## Results of the saved runs (`docs/gaisho/experiments.json`, 20 seeds, regenerable with `backend/scripts/gaisho_experiments.py`)

* **Knowledge.** Before the shift, the accuracy of the base-rate guess (0.844), the coincidental-cue judge (0.842) and the ground-responsive judge (0.833) is the same. Under intervention they differ: the effect of the evidence (do(E)) is ≈ 0 / −0.02 / 1.00; the
  effect of the cue (do(S)) is ≈ 0 / 0.95 / 0.00; the loss when the cue decouples is ≈ 0.01 / 0.33 / 0.00. With feedback the agent reconfigures (revision of the dependence on E +0.78, on S −0.79); without it the cue dependence is kept.
* **Bias, freedom, credit.** Each condition has its own profile of effects (e.g. freedom: the institutional label moves the belief, 0.9, and reaches the outcome only when the belief is adopted, 0.36; credit: an inert allocation transforms the state by 0.00 against 5.7–8.2 for
  the operating ones).

## Negative results kept (and not hidden)

* The pre-set operational criterion for the "non-accidental core" is **negated** for the base-rate guess, the coincidental-cue judge and the feedback-off agent, and **not negated** for the others — including the **miscalibrated misjudgement**, which the criterion cannot
  separate from the ground-responsive judge (it responds to the evidence; its error is in the reading, which the criterion does not test). Not negated is not an attribution.
* The candidate construction (the response to the evidence alone, a three-parameter fit) is `REDUNDANT` against a static causal model (M1) for the base-rate, ground-responsive, misjudged and feedback-on conditions, and `HARMFUL` for the cue-driven and
  feedback-off ones: it adds nothing the causal model does not hold. Against a reliability-only model (M0) it is `NON_REDUNDANT` for the ground-responsive, misjudged and feedback-on conditions, `REDUNDANT` for the base-rate guess and `HARMFUL` for the cue-driven ones.
* Relations that no difference was detected for (interval includes 0) are recorded as not detected, not as zero. Unobserved relations carry their class. The not-done list names the competing explanations that were **not** run (attention, memory, predictive
  processing, sensorimotor, cognitive appraisal, concept learning, SNN, dynamical systems, operational-shape analysis) and the domain not executed.

## Using it

Open the XENO ECOSYSTEM view, tab GAISHO (`?view=ecosystem&tab=gaisho`). Choose a domain and the candidate operations, set the observation conditions, **Run the experiment**; choose a condition and a moment, **show in the 3D scene**, compare with another moment (before/after),
another condition, or the same operation seen through another observation (presets); select a relation to mark the cells it reads; click a point or a hollow marker for its construction data; regenerate the figure; restore any history entry by re-running its
specification; export a record as JSON and import it back (loaded only if its digest is reproduced).

## Where the cells and edges of a shape come from (`construction.py`, `POST /api/gaisho/construction`, panel "Where the cells and edges come from")

A shape of the knowledge domain has **91 cells** = the 13 × 7 grid of the two interventions (do(E) at 13 values in [−3, 3], do(S) at 7 values in [−1.5, 1.5]) and **162 edges** = 12 × 7 neighbour pairs along E + 13 × 6 along S (an edge is drawn only where both ends are recorded). Other domains have their own grids (bias 9 × 5 = 45 cells / 76 edges, freedom 45 / 76, credit 5 × 5 = 25 / 40).
A cell is the share of its 40 trials in which the agent judges +1, with both inputs set by intervention: P(J = +1 | do(E = x), do(S = y)) = sigmoid(a·x + b·y + c) with the agent's weights (a, b, c) at the moment of the snapshot (start, before the shift, end), averaged over the seeds (one run per seed is the unit; sd across seeds).
**It is the response of the agent's decision rule to the interventions, not the correctness of its judgement** (earlier wording in the interface and in this document said "outcome" without saying so; the construction record states it).
The record of each cell and edge (the intervention pair, value, standard error, trials × seeds, what the weights predict, the operation digest, the provenance class, which edges it joins) is returned by the engine; the rules (cell, edge, cut ≥ 0.5, branch point = the 0.5 crossing, unresolved, projection) are listed with it.

**What the 91 cells carry (found while tracing them).** Refitting a logistic surface to the 91 recorded cells recovers the agent's three weights, and the residual is at the expected sampling-noise level, for every condition and moment. So the shape of this domain is a reading of three numbers under intervention. Consequences, kept as claim N3 and as tests:
(a) the domain cannot show an "operational shape" richer than the weights define — no cut appears in any condition; (b) between two moments at which the weights did not change (every condition except the learning one), the "difference" between the two shapes is sampling noise — an earlier on-screen comparison (mean |d| 0.018, branch points 19 / 20 for the cue condition) was exactly that and was shown as a difference;
(c) a Gaisho cannot be read off such a surface.

### Which layer each element of a shape is

| element | real operation | recorded observation | reconstructed relation | display |
|---|---|---|---|---|
| cell (91) | executed in the model: the decision rule (weights at the snapshot) evaluated with E and S set by intervention | **the value**: the share of the cell's trials with the outcome, through the instrument | none | its position (projection) |
| edge (162) | none | none (only its two ends are recorded) | **the difference of the two ends**; a cut if ≥ 0.5 (a threshold of the laboratory) | the line |
| branch point | none | none | **linear interpolation** of the 0.5 crossing: not a measured point | the marker |
| unresolved cell | unknown (it may exist and was not recorded) | none | none | **the marker of an absence**, with the class of the reason |
| face between cells | none | none | an assumption of continuity between four recorded neighbours | **the drawn face** and the colour (not across a cut) |

*A label corrected in this pass:* the record had given a cell the provenance `INTERVENTION_RELATIVE_DIFFERENCE`, which names a difference between interventions (an effect or a revision, i.e. a relation). A cell is a single recorded value, so it is now `RECORDED_OBSERVATION`.
Digests cover the label, so every saved digest changed; the first run is kept as `docs/gaisho/experiments_first_run.json`, and a test checks that every number, relation, verdict, negative result and sensitivity entry is identical between the two (only digests differ).

## What a change is a change of

A difference between two shapes, or between two observations of the same condition, is separated into four kinds (`construction.reading_of_difference`, `change_kinds_of_observations`; shown in the panel):

| kind | what it is | how it is read |
|---|---|---|
| real operation | the realized run / the decision rule itself changed | the weights of the operation (memory record) differ; for observations: the operation digest differs (probe, environment or window are part of the run) |
| recorded observation | the record of the cells or relations differs | the cell differences against the expected sampling noise (`WITHIN_SAMPLING_NOISE` / `BEYOND_SAMPLING_NOISE`); a relation recorded differently under the same operation is `RECORD_DIFFERENCE` |
| reconstructed relation | cuts, branch points, effects, revisions read from the record | they follow the record (including its noise); an unobservable relation is `UNOBSERVED_IN_ONE`, not zero |
| display | moment, ghost, layers, camera | changes no record and no relation |

Without the memory record the cause of a difference is `UNDETERMINED`, and the reading says so.

## Claims: supported, limited, untested (`claims.py`, `/api/gaisho/spec`, panel "Claims")

* **Supported inside the synthetic model** (K1–K5): equal accuracy before a shift with different intervention profiles; the cue-driven agent loses accuracy when the cue decouples; feedback reconfigures the dependence; an observation can change the record without changing the operation (and can change the operation); a shape carries the three weights.
* **Limits and negative results** (N1–N4): the operational criterion does not separate the misjudgement; the core-only construction is redundant or harmful against a static causal model; the shapes are logistic ridges (no cuts); not detected is not zero, and unobserved is not zero.
* **Philosophical hypotheses not tested** (U1–U4, and R37's own H1–H3 listed as not modelled): that non-accidental success is the characteristic core of a knowledge Gaisho (R37 has no such notion); that the ground-responsive agent has a knowledge Gaisho (the applicability gate fails); that the operational criterion corresponds to Non-Accidental Success (Dictionary 022) and that success is a necessary and sufficient constitutive core (**U3, UNVERIFIED**; the researcher states R37 does not prove this, and in the parts read it does not); that ignition, maintenance, transformation, expiry and re-ignition have the operational counterparts used here (R37 III defines them for episodes).
A test re-reads the saved results and fails if a supported or negative claim stops holding.

## The attribution is not derived

`model.attribute` takes only the operational states of the first three levels, a bearer, a historical interval and independent evidence (a test fixes its signature); accuracy, spikes, internal-state changes and classification success are not inputs, and a test shows that any operational state leaves the Gaisho levels at `NOT_ESTABLISHED` / `UNRESOLVED`. For every condition of every executed domain the attribution is `UNRESOLVED`.

## A defect found by checking on the real screen (fixed)

The browser sends `0` where Python writes `0.0`, and the record digest tells them apart, so the UI's run of the saved specification did **not** reproduce its saved digest (`efee2fae…` against `fe9adc86…`), although the experiment was the same. `observation_from` now casts the observation to its declared types; the saved digests are unchanged and the UI run reproduces `fe9adc86a7826f79` (a test covers it).

## Bias, freedom and credit: what exists

* **002 Bias** — five conditions on declared rule sets (evidence only, perception-derived selectivity, training-history prior, sensor/body offset, retrained prior); the cell is the agent's accuracy under a base rate and an evidence noise set by intervention. 4 relations not detected, 3 unobserved. Competing models and ablations: not done. What the conditions exhibit follows from the declared rules.
* **003 Freedom** — five conditions on declared coupling rules (self-interpretation, effective possibility, institutional label, constraint, embodied coupling); the cell is the reach. 9 relations not detected. Real alternatives in an action space, competing explanations and ablations: not done.
* **005 Credit** — four conditions, each cell a run of the existing TRUTH–ERROR institution engine (unchanged; a test checks that its digests do not move). 4 relations not detected. The institution's operation is not an individual's Gaisho; the individual's orientation to their own score is not modelled.

## Body-Gaisho and XenoSNN: what the source gives (B1 executes where the XB-TRO link is configured; B2, the spiking coupling, is not executed)

Checked against the source, not against descriptions. XenoSNN in `pa-simulation-environment` is `python/ziran_pytorch_server.py` (`POST /run` with `metadata.experimentType = "snn-minimal"`) driven by `src/ziran/experimental/pytorchBackend.ts` / `snnBrowserRun.ts`: **one snnTorch Leaky Integrate-and-Fire neuron** (β = 0.9, threshold 1.0, constants in the code) driven by a numeric
input sequence; it returns, per timestep, `t`, `input`, `membrane` and `spike`. It has **no weights, no plasticity, no memory, no sensor placement or morphology, no bodily output and no environment return.** It requires torch and snnTorch ("snnTorch unavailable = SNN experiment unavailable", with no substitute computation by design), and **neither is installed on this machine** (three Python environments checked).
So: of the six separate records the brief asks for (sensor input and time, spikes and time, internal state, weights, plasticity, memory, bodily output, environment return), XenoSNN can supply the first three (input, spike, membrane) and nothing else. A connection would be an adapter in `xzr.gaisho` that posts to a locally started `ziran_pytorch_server.py` (the HTTP protocol, no code copied), stores the returned trace as its own record kind, and attaches **no** Gaisho meaning to a spike;
the body model around it (sensor placement, morphology, feedback, memory, plasticity) does not exist in either repository and would have to be specified and built — as a declared synthetic model, not as XenoSNN. Domain 004 therefore remains specified and not executed until torch + snnTorch are installed and that body model exists. (The XB-TRO ledger states that XB-TRO has no spiking component and no connection to XenoSNN; XenoBody is not connected either.)

## The 91 cells and 162 edges against R37

R37 gives **no construction rule for shapes** (no grid, no edge, no surface), so there is nothing in it to "match" a cell count against; what it does constrain is what a drawn structure may be taken to be. Its Part XII "places operational shape on the side of real constitution and its conditional reconstruction on the side of fallible inquiry" and "treats observed ignition rates as indexed detector outputs"; II separates the real reachable set `Reach_H` from the inquiry-relative estimate `Reach_est` ("a fallible acquisition and reconstruction that can miss possibilities through instrument, scale, timing or boundary mismatch").
The laboratory's layers agree with that and are not changed: a **cell** is a recorded observation (a detector output under an observation condition `K`, `Det_D`) of an executed operation; an **edge**, a cut and a **branch point** are reconstructed relations (fallible, and following the record including its noise); the **face**, colour and position are display; an **unresolved** marker is a typed access failure, not an occurrence. **None of them is `Occ_G`**, and no drawn feature (a ridge, a cut, a branch) is evidence of an episode — R37's non-implication tests (II, six-register crosswalk, X counterexamples) forbid reading a complex shape, an effect or a rate as occurrence or attribution.
Where R37 and the laboratory differ: R37's `Det_D` is a *frozen detector* with a denominator, censoring and a null control; the laboratory's cells carry trials, seeds, intervals and unobserved classes but not a pre-registered detector freeze — R9 is PARTIAL.

## Body-Gaisho B1 (implemented; independent of the other domains)

`xzr/gaisho/bodylink.py` (the only module that touches the filesystem; its own scan test) links an XB-TRO checkout named by `XZR_XBTRO_PATH` (never by a request; without it the domain is NOT EXECUTED and nothing is substituted); the record carries the package's model version (`xb-tro/1.0`) and the SHA-256 of its 17 source files (`4864c289…` for the checkout used).
`BodyDomain`: a planar N-link body, two XB-TRO interventions as the two axes (sensory feedback delay 0–0.2 s × external disturbance 0–200 N, 5 × 5 cells), the continuation class (falls or not) as the outcome, per replication seed (one body per cell and seed; a cell is the share of seeds that fall), two body configurations (human-like and machine-like). Cost: about 21 s per condition for 6 seeds, capped at 8 seeds, inside the two-computation limit.
Saved: `docs/gaisho/experiments_body.json` (`gaisho_experiments.py body`, 6 seeds). Results: the **human-like** body is delay-sensitive (effect of the delay on the fall share 0.60; of the disturbance 0.40), the **machine-like** body is disturbance-sensitive (0.27 and 0.57); both stand up without delay and disturbance (baseline fall 0.0, "not detected" kept in failure registry F1); unlike the logistic ridge of the knowledge domain the body's shape has real steps (5 cuts, 5 branch points in the human-like shape). Limit: the intervals are over seeds only, and are degenerate (width 0) where every seed agrees — a body that is deterministic at a cell gives no seed variation there.
R37 register: **P** (prereflective bodily orientation) is EXECUTED_IN_MODEL; `A_G` stays UNRESOLVED with the gate NOT_PASSED, `Occ_G` NOT_ASSESSED, `C` NOT_MODELLED: a body that falls less is an operational difference, not a thinker. Tests: `tests/test_gaisho_body.py` (they need the XB-TRO package and are **skipped, not passed**, where it is absent).

## R37's finite countermodels, executed (`countermodels.py`, `POST /api/gaisho/countermodels`, panel "R37's finite countermodels")

R37 Appendix A and B.2b state finite constructions that are logical, not empirical. They are now executable and tested (exact enumeration with rational arithmetic; one re-execution):

* **Randomized questioning** (A.3): U and X_ask fair bits; H_R (E0=U, E1=U) and H_F (E0=0, E1=X_ask·U); the report R is inapplicable without a question. Both give the same joint of (X_ask, R) — (0,⊥) ½, (1,0) ¼, (1,1) ¼ — while P(E0=1) is ½ against 0: the record does not identify whether the orientation preceded the question. **Common endpoint** Y: the same joint of (X_ask, Y), the question's interventional effect is identified (½), P(E0=1) is still ½ against 0.
  These are two of R37's three formation histories (retrieval, formation). R37 gives **no finite model of the third** (a partial disposition transformed by the question) in the passages read, and none is invented.
* **Report indeterminacy** (A.3): no report-only rule decides the prior orientation on all histories — checked over all 2³ rules of the three report values, none decides. **Z-equivalence**: equivalent on the question alone; a pre-question probe would break it, and the probe's validity is stipulated (R37 requires it be established without assuming the attribution).
* **R12 / B.2b re-executed** (128 seeds from 20261029, 4,096 units, 524,288 matched worlds; models A: Y := M xor E, B: Y := U xor E; P(E=1)=0.1): the observational (M, Y) records are identical in every seed, also under the 20 % MCAR mask; the association 0.8002 [0.7987, 0.8017]; do(M) in A 0.8002 [0.7987, 0.8017]; in B exactly 0; the executed sham relabel (R13: a reversible relabel decoded before the equations) changes nothing. **R37 reports 0.800495 [0.798913, 0.802078] and 0.800510 [0.798927, 0.802094]: the intervals overlap**; R37 does not give its random generator, so agreement is of the intervals, not of seed-level numbers. Its own conclusion is kept: no part of this supports A_G=supported.
* **Renaming vs executed update** (A.5): a reversible renaming decoded before the gate changes nothing (0 of 4,096); an executed update changes every outcome where the gate reads the marker and none where it does not.
Constraints R15 (PARTIAL), R17–R19 (IMPLEMENTED) and R20 (B1/B2 outcomes: NOT_IMPLEMENTED — no Gaisho-added model exists to be replaced by a rival) record these.

## Body-Gaisho: more conditions, and B2 (the open-loop replay through the real XenoSNN)

**More body conditions.** Besides the two morphologies, named conditions for a sensor (visual feedback blocked), memory (the body's slow gain adaptation off) and resources (`resource_constraint` 0.4) — separate conditions, not crossed. Saved in `docs/gaisho/experiments_body.json` (6 seeds). Results: the effect of the delay (0.60) and the disturbance (0.40) are the **same** for the resource-constrained and the adaptation-off bodies as for the baseline; blocking vision changes the disturbance effect only slightly (0.43).
**A null result kept, not read as "no effect"**: the edits do change the configuration (energy and fatigue; the adaptation switch), and at a borderline cell (delay 0.1 s, push 100 N, 8 seeds) the body without adaptation fell in 8 of 8 against 6 of 8 — but the 5 × 5 grid has no cell near that threshold for 6 seeds, so the grid does not detect it. The limit is the grid and the number of seeds.

**B2** (`snnlink.py`, `bodysnn.py`, `POST /api/gaisho/body-snn`): the real XenoSNN server was run (torch 2.15.0 and snnTorch 1.0.0 installed in a **separate** environment, `/Users/user/Desktop/BIM/.venv-snn`; the shared environment was not touched). The link contacts only a **loopback** address given by `XZR_XENOSNN_URL`, fixed endpoints, redirects refused; it has its own scan test.
A test checks, on the live server, that the neuron obeys `mem_t = 0.9·mem_{t−1} + input_t − 1.0·spike_{t−1}` and spikes when the membrane exceeds 1.0 (the constants of its source). The body's sensed vestibular tilt estimate at a cell is encoded by a **stipulated** gain (1.0, never tuned) as an unsigned input current and replayed; the records are kept apart — sensor input and times, spikes and times, membrane, weights (NONE), plasticity (NONE), memory (NONE in the neuron), the body's own output (fell, fall time), the environment's return (the disturbance) — and the coupling is **OPEN**: XenoSNN keeps no state between requests and cannot be closed-loop with a body.
Saved: `docs/gaisho/experiments_body_snn.json` (cell delay 0.1 s, push 100 N, 4 seeds, two bodies). In the human-like body the seeds that fell had 43 and 35 spikes, the two that stayed up 8 and 8; in the machine-like body all four seeds fell (212–304 spikes). That is an operational difference of a stipulated encoding. It is not a Gaisho: attribution UNRESOLVED, the gate NOT_PASSED, a spike is a threshold crossing (R37's `Det_D`, not `Occ_G`).
**Still not done:** a closed loop (spikes changing an operation line) — there is no spiking controller with weights and plasticity in either repository and building one is a new model, not XenoSNN; a body that crosses morphology, sensor, memory and resources.

## Security (reviewed route by route; `test_security.py` is unchanged except for registering the routes)

What `test_no_route_runs_experiments_or_touches_the_filesystem` protects: the public API surface lists every mutating route (a new one must be reviewed), the route files that run research code answer 403 under `XZR_PUBLIC` and cross-origin, and the app must not call subprocess/experiment runners. Adding `/api/gaisho/construction` to the list was necessary and **not sufficient**. Reviewed:

* **Experiments run in the request** (CPU-bound, in process). Found: `conditions` could repeat a name and so repeat its runs (cost amplification); there was no bound on concurrent runs; the institution engine of domain 005 costs about 1.8 s per seed and condition (20 seeds ≈ 36 s per request; measured). Fixed: distinct, non-empty condition names; a per-domain seed cap (005: 10; the engine refuses it too, whoever calls it); at most two computations at once, a third gets **429** (not queued).
* **Local only, before computing**: the old test only counts `local_only(request)` occurrences (`>=`), which a duplicate could mask. A new test enumerates every `/api/gaisho` route of the app and checks that each answers 403 (cross-origin and `XZR_PUBLIC`) **before** any computation function is reached (the computation functions are replaced by ones that fail the test if called).
* **File access / external effects**: a test scans the engine and the service for file, network, subprocess, dynamic-code and path APIs and finds none (the saved results are read only by tests and by the script).
* **Authentication**: none beyond the local same-origin model shared with the MEOS, TRUTH-ERROR and study routes (they are local-runtime routes; the 403 under `XZR_PUBLIC` is the boundary). **Input validation**: numbers and names of the laboratory's own conditions only, bounded; an observation is cast to its declared types. The figure SVG is built from escaped text (a test feeds markup as the moment).

## Comparators: what M0, M1 and the candidate are, and what the verdicts do and do not say

From `compare.py`: all models see the **same** recorded cells of the `end` snapshot (training: the natural manifold where the evidence and the cue move together, plus the neutral-cue row; held out: every other cell, evidence and cue set independently), **none** sees the history (other snapshots or the weights), and the test interventions are the same.
M0 = the marginal rate (1 parameter; what an accuracy statistic holds). M1 = logistic response to E and S with an offset (3). CAND = the candidate construction, a response to E alone with an offset (2: M1 with the cue weight fixed to 0). **Because the cells of this domain are exactly a three-weight logistic response, M1 is the generating model class and CAND is nested in it: CAND cannot beat M1 where the cue matters, and
the "REDUNDANT / HARMFUL against M1" verdicts follow from that structure.** They show that the construction "response to the evidence alone" adds nothing here; they do not show anything about a Gaisho or about non-accidentality.
Added (opt-in, the record's own comparison is unchanged, `POST /api/gaisho/comparators`, `compare_models(..., extended=True)`): **M4**, the single-factor cue account (S alone, 2 parameters — the same number as CAND), with each model's information, history and parameter count declared. With equal parameters the right single factor wins (cue-driven agents: CAND `HARMFUL` against M4; evidence-driven agents: `NON_REDUNDANT`; base-rate guess: `REDUNDANT`): the candidate has no advantage of its own.
Not run: attention, history-informed prediction, predictive processing, sensorimotor, cognitive appraisal, concept learning, SNN, dynamical systems, the existing operational-shape analysis. (History-informed prediction would have to see more than the others; to be comparable it needs a stated amount of history for every model.)

## Git: the commit and the phase-5 WIP commit

`d8e16f9` is GAISHO (33 files) on top of `1af5700` (the interrupted TRUTH–ERROR phase 5, 14 files, +210k lines because `docs/truth_error/experiments2.json` grew to 10 MB), both pushed to `origin/feat/xenoscience-ecosystem-3d` (13 commits ahead of main). Dependency: **only domain 005-credit** reads the phase-5 output `process.labels.metrics.target_change_abs` (absent at `f8c7fd6`) and the phase-4 `process.complement`; it now raises an error naming them if they are missing.
Domains 001–003, the GAISHO frontend and its tests import nothing from phase 5. The WIP commit is described as unfinished (docs §14 not written); the backend baseline recorded for that state was 1210 passed / 3 skipped, and the full regression of the state including GAISHO is in the changelog. No history was rewritten and nothing was force-pushed.

### Existing body sources that could carry a Body-Gaisho experiment (checked in code, nothing connected or declared executed)

* **XB-TRO** (`xeno-ziran-runtime-xb-tro`, branch `feat/xb-tro`, local, not in this branch): `xzr/xbtro/engine.py`, a batched deterministic **planar N-link body** (Lagrangian mechanics, RK4, base-of-support and friction checks, pushes, a ledge), with **delayed, noisy sensing channels** (proprioceptive, vestibular, visual, tactile, cue — the controller only sees these copies), operation lines that ignite, hold and cost energy,
  internal coordination (energy, fatigue, slow gain adaptation), observation models ("cuts", an apparatus that can change the body) and interventions; experiments A (observation-cut transformation) and B (**sensorimotor coupling**: feedback delay, block, reconnection, with coupling reconstruction and interventional evidence). Pure numpy: a default configuration for 3 seeds ran in 0.9 s here. **No spiking component** (its own ledger says so).
* **ziran-xeno-simulator/embodied**: MuJoCo planar Walker2d / Hopper bodies with the Xeno-14 controller and active inference; needs torch and MuJoCo (not installed; no environment). No SNN either.
* **XenoSNN** (P/A): one LIF neuron (above); `src/ards/verify/lif.ts` is a TypeScript re-computation used to verify its traces, not a body.
**Connection boundary, verified (2026-11-05), before any merge:** `xzr/xbtro/` is a **leaf package**: its only imports are numpy and the standard library (no import of any other `xzr` module; the service layer `service/xbtro_ops.py` and the routes are outside it). It loads as a top-level package from its directory (`PYTHONPATH=<xb-tro>/backend/xzr`, `import xbtro`; `xzr` is not imported) and ran a 4-seed default body here. Its intervention registry (`config.INTERVENTIONS`) already names seven executable interventions:
sensory feedback delay, visual feedback block, contact condition, posture condition, neural response delay, external disturbance, bodily resource constraint. So a Body-Gaisho domain needs **no merge of the 8k lines or of the service layer**: it can load the package through an explicit, optional path (pinned to the XB-TRO commit, currently `94c2e8e` on `feat/xb-tro`, so that a record names the body it ran on) and stay NOT EXECUTED where the path is absent. Not done: the adapter, a choice of the two intervention axes and of the outcome, and the declared reading of its
results — building them is the next step, and it would still say nothing about spikes or about a Gaisho (XB-TRO has no spiking component).
So no source combines a body, sensors and a spiking controller.

**Body-Gaisho: B1 is implemented (2026-11-05), B2 is only a design.** B1 = steps 1–2 below, built as `xzr/gaisho/bodylink.py` and `BodyDomain`; steps 3–5 (spiking coupling) are NOT implemented and NOT executed.
1. *Boundary.* One adapter module outside the scanned engine files (`xzr/gaisho/bodylink.py`, with its own security review, because it is the only place that needs a path): it imports `xbtro` from a path that the operator sets in the environment (never from a request), read-only, and records the package's model version and a hash of its source files in every record. Without the path the domain is NOT EXECUTED, as now. No merge of XB-TRO into this branch and no import of its service layer.
2. *Executable body experiment (level B1, needs only numpy).* The two intervention axes are two entries of `config.INTERVENTIONS` (for example sensory feedback delay × external disturbance); the cell is the share of seeds that fall; the observation conditions are XB-TRO's own observation cuts. The records are kept **separate**, as the brief requires: the sensed copies (delayed, noisy) with their times; the operation-line activity; the joint drive; the internal state (energy, fatigue, slow gain adaptation); the environment's return (push, support).
   Comparators on equal information: the marginal fall rate (M0) and a logistic response to the two intervention values (M1); the matched control is the same seeds without the intervention (common random numbers, which XB-TRO provides).
3. *Spiking coupling (level B2, needs torch and snnTorch, and a new declared component).* XenoSNN's `POST /run` takes a whole input sequence and returns the trace (t, input, membrane, spike): it has no per-step state, so **it cannot sit in a closed loop with the body**. What it supports is an **open-loop replay**: a sensed signal recorded from a B1 run (for example the delayed trunk angle) is fed to the LIF neuron, and the input, the membrane and the spike train are stored as three separate records next to the body's records, with no effect on the body.
   A closed loop (spikes changing an operation line's gain) needs an in-process spiking controller that does not exist in either repository; it would have to be specified as a synthetic component of its own (declared weights and plasticity rule), run on its own, and could not be called XenoSNN.
4. *What none of this says.* A spike is a threshold crossing of a neuron model, not a firing of a Gaisho; spikes, the fall rate and the body's adaptation are never inputs of the attribution (`model.attribute`); a body that falls less under an intervention is an operational difference, not a Gaisho. The levels, the verdicts and the negative results are kept exactly as for the other domains.
5. *Order of work.* B1 first (it runs now, once the adapter exists); B2 open-loop only after torch and snnTorch are installed; B2 closed-loop only after the controller is specified and approved. What could actually run: Body-Gaisho experiments on the XB-TRO body (intervene on sensing delay/noise, block/reconnect the feedback, change the observation cut and the apparatus; read the difference in the body's operation against a matched control) as a domain of this laboratory — which needs XB-TRO brought into this branch (a merge or cherry-pick of its 8k lines: a decision for you) — and
a second domain with a declared spiking controller only after torch and snnTorch are installed and that controller is specified. The first is now implemented (B1, below); the second does not exist.

## Screens

`docs/gaisho/screens/01_cue_shape_pick_trace.jpg` (the coincidental-cue shape in the 3D scene, a picked cell v6_3 in yellow, the 0.5-crossing branch points in blue, the construction trace: 91 cells, 162 edges, 20 branch points, value 0.507 against 0.500 predicted by the weights) and `02_feedback_before_after_reading.jpg` (the correcting agent at the end against its start as a wire; the reading: operation changed, beyond sampling noise, mean |d| 0.363 against 0.011). `03_body_b1_shape_pick.jpg` (domain 004, the human-like planar body, 8 seeds: 25 cells, 40 edges of which 5 are cuts, 5 branch points, a picked cell v2_2 at 0.75 = 6 of 8 seeds fall; the effect of the delay 0.60 and of the disturbance 0.40, attribution UNRESOLVED). All three were taken from the running 3D research view and agree with the engine records quoted in the panels. `04_body_snn_open_loop_countermodels.jpg` (the human-like body at the cell delay 0.1 s, push 100 N, replayed through the real XenoSNN neuron: the per-seed records — input peak, spikes 43 / 8 / 8 / 35, membrane maximum, fell or not — with the record digest `5eb09bd1ad4d`, equal to the saved one at the time (the record's explanatory strings were reworded afterwards — 'requests' to 'calls', so that the code scan has no false hit — so the saved digests are now `38b9eba7fee2` and `4ae4742ea618`; every number is identical); the weights / plasticity / memory / coupling statements; the attribution UNRESOLVED; and below it the countermodel panel). Limit seen on screen: running the body domain from the pane (8 seeds, two bodies) took about two minutes while the browser was rendering, and the pane waits for it.

## Limits

Synthetic operations with declared constants; a shape is a projection of identified relations, not the complete acquisition of any real operation. The intervals are over 20 seeds of one model; they say nothing about other models. Domains 002, 003 and 005 have no
competing-explanation comparison yet; 004 is B1 only and runs only with the XB-TRO link. Conditions that need the observation to read what is outside the recorded cells (a `UNMEASURED` region) stay unresolved; a different instrument may identify them, and this laboratory does not say that they are zero.

## Next conditions of the research

1. Read the parts of R37 still unread (the rest of Part II, Parts IV, VI, VII, IX and XI, the rest of Parts V and VIII, Appendix B.2c–B.5, the rest of Appendix C) and obtain the P/A Dictionary v40 (entries 013–024 and 022 in particular), then re-check `r37.CONSTRAINTS`, claim U3 and the re-description of the knowledge domain; keep the saved results.
2. Body: cross morphology, sensor, memory and resources with a finer grid near the threshold and more seeds (the memory and resource conditions are not detected on the 5 × 5 grid), and add XB-TRO's observation cuts. B2's closed loop needs a declared spiking controller with weights and plasticity that does not exist yet.
3. Run the remaining competing explanations with equal information and resources; run the comparison for the three other executed domains.
4. Independent evidence for any attribution has to come from outside these computations.
