# GAISHO — Operational Shape Laboratory

A research function of the existing XENO ZIRAN SIMULATOR (tab **GAISHO** of the XENO ECOSYSTEM view; engine `backend/xzr/gaisho`; API `/api/gaisho`). It executes **synthetic computational experiments** in which a candidate operation is
intervened on, observed under chosen observation conditions and compared; its operational shapes are built from what those runs recorded. It is local-only (403 under `XZR_PUBLIC`, excluded from the public build and the iOS engine), stateless
and deterministic.

## What it is not

* It never computes a Gaisho attribution. An operational difference is not evidence of a Gaisho; the attribution level stays `UNRESOLVED` unless a researcher supplies independent evidence, and then it is only recorded as `ASSERTED_BY_RESEARCHER`.
* It shows nothing about human neural activity, the formation of a real Gaisho, or a universal law. Every domain is a declared model with declared constants.
* It does not implement the 150–200 concepts; it implements five domains (below), each judged on its own.

## Source status

The manuscript **GAISHO R37 was not found on this machine** (and no `gaisho_001.py` or definition of 概象 exists in any repository here). The five levels, the twelve questions, the prohibited inferences and the verdict classes are those of the
development brief; nothing is taken from R37, and nothing unconfirmed has been filled in. When R37 is available its definitions must be compared with `xzr/gaisho/model.py` before any claim is made about it.

**R37 correspondence: NOT DONE (2026-11-04).** The file `gaisho_r37(1).docx` named in the verification request did not reach this machine (searched `~/Downloads`, `~/Desktop`, `~/Documents`, the Claude app's upload and scratch folders, and the whole disk for `*gaisho*` and `*r37*`; the only hit is a P/A Institute site page that says "no public source describing it was recovered"). Items that need R37 — its definition of the concept (概象), conditions of
establishment and attribution, ignition, maintenance, transformation, expiry, re-ignition, and its distinction from the conceptual operational shape — were not checked, no implementation was changed on its account, and none of the five levels / twelve questions below has been compared with it.
Claim H3 of the registry states this as UNVERIFIED. When the file is placed on the machine, read it in full and compare it with `model.py`, `knowledge.py` and `claims.py` before any claim of faithfulness.

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
| 001-knowledge | accidental-correct (base rate / coincidental cue), ground-responsive, miscalibrated misjudgement, correction and reconfiguration with and without feedback | `INITIAL_EXPERIMENT_EXECUTED` |
| 002-bias | selectivity, training-history prior, sensor/body offset | `INITIAL_CONDITIONS_EXECUTED` |
| 003-freedom | self-interpretation, effective possibility, institutional classification, constraint | `INITIAL_CONDITIONS_EXECUTED` |
| 004-body | sensor placement, morphology, SNN firing, feedback, memory | `NOT_EXECUTED` — XenoSNN is in the P/A repository, not in this runtime; the domain is specified, no substitute computation is made |
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
* **Philosophical hypotheses not tested** (H1–H4): that non-accidentality is the characteristic core of a knowledge Gaisho; that the ground-responsive agent has a knowledge Gaisho; that the operational criterion corresponds to R37's non-accidental core (**UNVERIFIED**); that ignition, maintenance, transformation, expiry and re-ignition have the operational counterparts used here.
A test re-reads the saved results and fails if a supported or negative claim stops holding.

## The attribution is not derived

`model.attribute` takes only the operational states of the first three levels, a bearer, a historical interval and independent evidence (a test fixes its signature); accuracy, spikes, internal-state changes and classification success are not inputs, and a test shows that any operational state leaves the Gaisho levels at `NOT_ESTABLISHED` / `UNRESOLVED`. For every condition of every executed domain the attribution is `UNRESOLVED`.

## A defect found by checking on the real screen (fixed)

The browser sends `0` where Python writes `0.0`, and the record digest tells them apart, so the UI's run of the saved specification did **not** reproduce its saved digest (`efee2fae…` against `fe9adc86…`), although the experiment was the same. `observation_from` now casts the observation to its declared types; the saved digests are unchanged and the UI run reproduces `fe9adc86a7826f79` (a test covers it).

## Bias, freedom and credit: what exists

* **002 Bias** — five conditions on declared rule sets (evidence only, perception-derived selectivity, training-history prior, sensor/body offset, retrained prior); the cell is the agent's accuracy under a base rate and an evidence noise set by intervention. 4 relations not detected, 3 unobserved. Competing models and ablations: not done. What the conditions exhibit follows from the declared rules.
* **003 Freedom** — five conditions on declared coupling rules (self-interpretation, effective possibility, institutional label, constraint, embodied coupling); the cell is the reach. 9 relations not detected. Real alternatives in an action space, competing explanations and ablations: not done.
* **005 Credit** — four conditions, each cell a run of the existing TRUTH–ERROR institution engine (unchanged; a test checks that its digests do not move). 4 relations not detected. The institution's operation is not an individual's Gaisho; the individual's orientation to their own score is not modelled.

## Body-Gaisho and XenoSNN: what the source gives (domain 004 stays NOT EXECUTED)

Checked against the source, not against descriptions. XenoSNN in `pa-simulation-environment` is `python/ziran_pytorch_server.py` (`POST /run` with `metadata.experimentType = "snn-minimal"`) driven by `src/ziran/experimental/pytorchBackend.ts` / `snnBrowserRun.ts`: **one snnTorch Leaky Integrate-and-Fire neuron** (β = 0.9, threshold 1.0, constants in the code) driven by a numeric
input sequence; it returns, per timestep, `t`, `input`, `membrane` and `spike`. It has **no weights, no plasticity, no memory, no sensor placement or morphology, no bodily output and no environment return.** It requires torch and snnTorch ("snnTorch unavailable = SNN experiment unavailable", with no substitute computation by design), and **neither is installed on this machine** (three Python environments checked).
So: of the six separate records the brief asks for (sensor input and time, spikes and time, internal state, weights, plasticity, memory, bodily output, environment return), XenoSNN can supply the first three (input, spike, membrane) and nothing else. A connection would be an adapter in `xzr.gaisho` that posts to a locally started `ziran_pytorch_server.py` (the HTTP protocol, no code copied), stores the returned trace as its own record kind, and attaches **no** Gaisho meaning to a spike;
the body model around it (sensor placement, morphology, feedback, memory, plasticity) does not exist in either repository and would have to be specified and built — as a declared synthetic model, not as XenoSNN. Domain 004 therefore remains specified and not executed until torch + snnTorch are installed and that body model exists. (The XB-TRO ledger states that XB-TRO has no spiking component and no connection to XenoSNN; XenoBody is not connected either.)

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
So no source combines a body, sensors and a spiking controller. What could actually run: Body-Gaisho experiments on the XB-TRO body (intervene on sensing delay/noise, block/reconnect the feedback, change the observation cut and the apparatus; read the difference in the body's operation against a matched control) as a domain of this laboratory — which needs XB-TRO brought into this branch (a merge or cherry-pick of its 8k lines: a decision for you) — and
a second domain with a declared spiking controller only after torch and snnTorch are installed and that controller is specified. Neither exists yet; domain 004 stays NOT EXECUTED.

## Screens

`docs/gaisho/screens/01_cue_shape_pick_trace.jpg` (the coincidental-cue shape in the 3D scene, a picked cell v6_3 in yellow, the 0.5-crossing branch points in blue, the construction trace: 91 cells, 162 edges, 20 branch points, value 0.507 against 0.500 predicted by the weights) and `02_feedback_before_after_reading.jpg` (the correcting agent at the end against its start as a wire; the reading: operation changed, beyond sampling noise, mean |d| 0.363 against 0.011). Both were taken from the running 3D research view and agree with the engine records quoted in the panels.

## Limits

Synthetic operations with declared constants; a shape is a projection of identified relations, not the complete acquisition of any real operation. The intervals are over 20 seeds of one model; they say nothing about other models. Domains 002, 003 and 005 have no
competing-explanation comparison yet; 004 is not executed. Conditions that need the observation to read what is outside the recorded cells (a `UNMEASURED` region) stay unresolved; a different instrument may identify them, and this laboratory does not say that they are zero.

## Next conditions of the research

1. Place `gaisho_r37(1).docx` on the machine (it did not arrive); read it in full and compare its definitions with `model.py`, `knowledge.py` and `claims.py`; correct what does not match, keeping the saved results.
2. Bring XenoSNN into this runtime (or run it through its own repository's record) and execute domain 004 with the sensor input, spikes, internal state, weights, plasticity, memory, bodily output and environment return recorded **separately**, spikes carrying no Gaisho meaning.
3. Run the remaining competing explanations with equal information and resources; run the comparison for the three other executed domains.
4. Independent evidence for any attribution has to come from outside these computations.
