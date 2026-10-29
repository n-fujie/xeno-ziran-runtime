# XENO ECOSYSTEM — MEOS-0, stage 4: from a photoreal scene to a research apparatus

Branch `feat/meos-ecosystem` (worktree `xeno-ziran-runtime-meos`), engine `meos-0.3`. Local only: not pushed, not deployed, not merged.
This stage starts from `93119a0` (parent `de6fcfe`), checked in the repository before work began: branch `feat/meos-ecosystem`, tree clean apart from the untracked `frontend/node_modules` symlink, no upstream.
It continues `docs/ECOSYSTEM_MEOS_STAGE3.md`.

**What this stage is not.** It does not polish the photoreal scene further. Its centre is research state: the separation of what a run did, what an observer concludes and why they differ; interventions that can be made, compared and replayed; boundaries, paths and addresses that
are operations of the engine and not labels; experiments that were run and saved with their nulls. The bodies stay a *presentation*: a machine is never identified with A1, A2, history, the Address Domain, SSS or XenoBody.
A picture of a run is not evidence about the run; where the interface shows both, **MODEL RESULT** (read from the record) and **VISUAL REPRESENTATION** (how a body is posed) are labelled apart.

## 1. Scope

| item | where |
|---|---|
| readable research state | RESEARCH tab (`ResearchPane.tsx`), the state panel of the technical sheet, `research.ts` (`inspectAt`) |
| experiment console (observation interval / resolution / region / occluder / threshold / address resolution, XenoBody boundary, Address Domain, SSS, history, coupling, resource pulse, renewal, power, M2) | RESEARCH tab, groups of controls; each builds an intervention or an observation configuration and re-runs the engine |
| technical view extended | research map on the sheet (`researchMap.ts`, `researchMapDraw.ts`): observation region, interval, resolution, window, observability; interventions; three boundary kinds with three line types; five operational paths with layer toggles; B1 / B2 / B3 |
| operational / observed / observability | `analysis.observe` (three fields, v4 vocabulary + first-stage names), `timeline` per tick |
| operable XenoBody boundary | `stage4.boundary_perturbation`, `/api/meos/boundary-perturbation`, console, B1/B2/B3 relation closure |
| real Address Domain interventions | engine: loss, reassign, fragment, collision, partial, restore, **delayed, stale**; `stage4.address_intervention`, `address_effects` |
| SSS on bodies and in experiments | `mechanics.ts` (`sssMechanics`), `bodyset.ts`, `observer.ts`; regions from `/api/meos/sss-classify` |
| M2 on a downstream path | M2 → A1's sensor signal (engine), the M2 tap on node B (probe B2), trace `m2_sensed`, experiment E |
| minimal observer improvements, cables | the old comparison camera is kept; cables of the five paths with harness conductors and ties |
| comparison baseline / intervention / recovered | snapshots A/B on the technical sheet with a delta table (`research.ts` `deltaSnapshots`) |
| replay | markers on the timeline (intervention, boundary change, Address Domain, resource pulse, collapse, recovery, observation failure), click-to-inspect |
| per-run logs | `/api/meos/run-log` (JSON; CSV per tick), export buttons |
| performance | section 12 |
| experiments A–E | section 10 and `docs/ecosystem/experiments_stage4.json` |

## 2. Protected Stage 3 assets (not deleted, not rewritten)

The photoreal bodies and ground, the Technical Inspection View (its three drawings, probe detail, measured dimensions, component table, state panel), the state mapping of Stage 3 (every row still holds; Stage 4 adds rows), the quality tiers, the old
comparison camera `observer`, the 29 Stage 3 captures and their camera record, `docs/ecosystem/perf_stage3/`, the Stage 3 regression evidence, the stored 264 runs and their replay. Nothing was regenerated to force a match; no digest changed.

## 3. Implementation changes

**Engine (`backend/xzr/meos/engine.py`, `meos-0.2` → `meos-0.3`).** Optional and absent by default: a run that does not use them is bit for bit the run of the earlier stages (the baseline result digest `b4cf1e52…adc5` is asserted by a test).
`ADDRESS` gained `delayed` (x, y, delay: the body moves at once, the address names the old cell until the update arrives; an `address_update` event marks the arrival) and `stale` (optional duration: the address stops following the body). A configuration
senses and acts at the cell its address names (`_cell`), which is its own position unless a fault says otherwise. `m2.sense` gained `threshold` (the tap passes only a signal above `m2.threshold`). A trace `m2_sensed` (what A1's tap added to its sensor
signal) is recorded **only** when M2 sensing is configured, so no other run's trace changed.

**Observation (`analysis.py`).** `observe` returns `operational_state`, `observed_state` and `observability` as separate fields. The new vocabulary is primary in `observability.status`; the first-stage name is kept in `observability_status` (records and tests that read it are unchanged).
New opt-in limits: `threshold` (the observer detects an event only if its signal is at least this), `occluder` (a rectangle hiding what lies inside), `address_resolution` (an event is attributed to a configuration only while its address integrity is at least this).
`timeline` gives the three states at every tick. The observation is a function of a finished record: it cannot change a digest (tested).

**Readings (`stage4.py`).** Operational paths (`path_activity`), boundary perturbation, Address Domain effects, per-run log, SSS region of a point. `dynamics_digest` is a digest of the frames without the fault bookkeeping: the result digest also covers the intervention log, so it differs for any intervention, and "the run changed" is decided on the dynamics digest. **Experiments (`stage4_experiments.py`, `scripts/meos_experiments_v4.py`).**

**Interface.** `research.ts` (markers, inspection, snapshots, deltas; pure), `mechanics.ts` (SSS and M2 as body poses; pure), `researchMap.ts` (the map spec; pure), `researchMapDraw.ts`, `ResearchPane.tsx`, changes to `EcosystemView.tsx`, `TechnicalView.tsx`, `bodyState.ts`, `bodyset.ts`, `observer.ts`, `cables.ts`.

## 4. Operational state, observed state, observability

Three separate quantities. `operational_state` is the status of the run itself (ACTIVE / DEGRADED / COLLAPSED by the engine's criteria). `observed_state` is the status computed with the same criteria from only the cycles an observation resolves. `observability.status` says why they differ,
found by relaxing each observation limit in turn and seeing which restores agreement.

| status | cause |
|---|---|
| SUFFICIENT | the observation agrees with the run |
| INSUFFICIENT_TEMPORAL_RESOLUTION | sampling interval (or aggregation) too coarse |
| INSUFFICIENT_SPATIAL_RESOLUTION | spatial stride too coarse |
| OUTSIDE_OBSERVATION_REGION | the region excludes the activity |
| BOUNDARY_OCCLUDED | an occluder hides it |
| ADDRESS_UNRESOLVED | the observer cannot attribute events to a configuration whose address is faulty |
| WINDOW_TOO_SHORT | the counting window is shorter than the cycle spacing (`WINDOW_MISMATCH` for a longer one) |
| SIGNAL_BELOW_THRESHOLD | the events' signal is below the detection threshold |
| COMBINED_LIMITS, OBSERVATION_OVERESTIMATES | no single limit restores agreement; the observer sees ACTIVE where the run is not |

An observed COLLAPSED against an operational non-collapse is reported as `observed_collapse_is_artifact`: it is a limit of the observation, not a collapse of the run. The UI shows the three states in three places (console, timeline strips, sheet).

## 5. Boundary model

Three different boundaries, three different line types on the research map, never merged: the **XenoBody boundary** (solid, heavy: what is retained as the operational body; B1 = A1 + its resource sensor, B2 = + the sensor network and the interaction channel, B3 = both configurations and the resource-transfer loop;
a cut relation the body retains opens a gap), the **Address Domain boundary** (dash-dot: the addressable arena, and pointers to the cell a faulty address names), the **observation boundary** (dashed: the observed region, with the lattice and an occluder hatched).
Perturbing a boundary is an operation: `boundary_perturbation` runs the unperturbed, perturbed-then-restored, perturbed-open and pulsed runs and reports the state before / at the end of the perturbation / final, the paths cut directly and the paths that changed downstream, collapse,
recovery with and without a pulse (with the pulse's own effect on the unperturbed run as control), the observability effect, and for B1 / B2 / B3 which legs of the recursion close inside the body and which the perturbation breaks. B3-only persistence is a property of the unperturbed arrangement and is reported by experiment B.

## 6. Address Domain

Engine faults: loss, reassign, fragment (mask), collision, partial (an auxiliary random stream), delayed, stale, restore. `address_effects` records, per intervention: tick, affected address, old and new state (mode, integrity, the cell the address names and the cell the body occupies), affected paths, the operational effect
(state before, worst state after, collapse tick), the observed effect, recovery status (and recovery with a pulse). Recovery after reassignment is a reassignment back. The Address Domain is an operation of the engine (the cell a configuration senses and acts at), not a label.

## 7. SSS

`ALTER_SSS` changes scale (sensing reach and diffusion length), size (footprint and rates) and speed (movement and the process clock). Regions of the (scale, size, speed) space: ACTIVE, COLLAPSED, METASTABLE (ACTIVE at tick 239 but not at 479, or seeds disagree), RECOVERY-CAPABLE (collapsed, but a pulse restores it), OBSERVATION-SENSITIVE
(ACTIVE, but an observation at interval 2 concludes otherwise); `/api/meos/sss-classify` classifies one point. **Mechanical reading on the bodies** (`mechanics.ts`, a visual representation rule): scale → the observer boom's reach (preload), size → the probe ring's posture (tilt), speed → the coupling's tension and the reservoir regulation,
the region → how far the archive latch stands ajar (METASTABLE 0.6 rad, RECOVERY-CAPABLE 0.9 rad; ACTIVE, COLLAPSED and OBSERVATION-SENSITIVE leave it shut: observation sensitivity is a property of the observer). Each parameter drives its own quantity (tested). The numbers a pose is read from come from the record; the pose says nothing the record does not.

## 8. M2

M2 is A2's alteration of the environment. With M2 sensing configured (`direct`, `delayed`, `noisy`, `threshold`), A1's resource-sensor signal includes a weighted M2 term, so M2 enters A1's differentiated stimulus and its firing condition: a downstream path. The term is recorded as the trace `m2_sensed`; node B's second probe (B2) is drawn as the M2 tap
(lit while A1 senses a nonzero term, trembling for a noisy tap, retracted in a collapsed run). With M2 not connected the probe follows the node as before. Experiment E compares none / direct / delayed / noisy / thresholded; its nulls are recorded as nulls and nothing was tuned.

## 9. Replay

The timeline carries a marker row (colours in the legend of the RESEARCH tab): intervention, boundary change, Address Domain, resource pulse, collapse, recovery, observation failure (from the start of each stretch in which `observability` is not SUFFICIENT; its detail says the run itself is unchanged). A second strip under the status strip shows the *observed* state. Clicking a marker moves the playhead and opens the inspection
panel: operational / observed / observability, the active boundary (open relations, arena radius), the Address Domain (mode, integrity, the cell named versus the body's cell), SSS and its region, energy, resource, history, path states and M2. Replay is deterministic: the same seed, configuration and intervention schedule give the same result digest (the REPLAY button and `/api/meos/replay`).
**Per-run logs** (`/api/meos/run-log`; export buttons): JSON with the seed, the initial configuration and its digest, the intervention schedule, the observation / boundary / Address Domain / SSS / M2 configuration, the operational, observed and observability timelines, collapse and recovery ticks, path summaries and the digests (plus a `log_digest` over the log); CSV with one row per tick.

## 10. Experiments A–E (`docs/ecosystem/experiments_stage4.json`)

Each experiment ran the real engine, deterministic and seeded; nothing was tuned toward an expectation. Every one is saved with its seeds, fixed conditions, manipulated variable, measured variables, results, null results, failures (runs the engine refused: none) and its interpretation limit. They are properties of this formal model's
operational relations and say nothing about any physical or biological ecosystem. Reproduce: `PYTHONPATH=backend python backend/scripts/meos_experiments_v4.py` (about four minutes).

### Experiment A — observation resolution sweep (5 seeds, three scenarios)

*Question.* How far can an observation be degraded before its conclusion departs from what the run did? *Result.* The operational state of a run does not depend on the observation (replay identical after every one of the observations: true). On the ACTIVE run the observer already disagrees at **sampling interval 2**, **spatial stride 2**, a region that no longer contains
A1's cell, an occluder over A1's cell, a detection threshold of **0.1**, and a window of **6**; the first disagreeing value is the same in the unperturbed and the recovered scenario. *Null results.* No value of `address_resolution` in the sweep made the observer disagree on a run with no Address Domain fault (nothing to resolve); and on the collapsing scenario no value of any limit
changed the observer's conclusion (it concludes COLLAPSED with or without the limit: a degraded observation can lose an operation, it cannot invent one). *Unexpected.* Every observation that resolves no cycle concludes COLLAPSED at the end of its window, at tick 48, about 100 ticks before the real collapse of the collapsing run: an observed collapse that is a limit of the observation (flagged `observed_collapse_is_artifact`).
*Limit.* The first disagreeing value depends on this record's event timing (cycle spacing about 5 ticks).

**Tables (copied from the saved file by `backend/scripts/make_stage4_doc_tables.py`).**

**Seeds** [1, 2, 3, 4, 5] · **fixed** {"configuration": "MEOS-0 default", "horizon": 360, "scenarios": ["unperturbed (ACTIVE)", "interaction cut 100-150 (collapses)", "cut 100-150 + pulse 2.0 at 151 (recovers)"]}
**Manipulated** {"observation parameter": ["sampling_interval", "spatial_stride", "region", "occluder", "threshold", "window", "address_resolution"], "values": {"sampling_interval": [1, 2, 3, 4, 5, 6, 8, 12], "spatial_stride": [1, 2, 3, 4, 6], "region": [[0, 0, 13, 13], [0, 0, 9, 9], [0, 0, 6, 9], [2, 4, 6, 8], [3, 5, 5, 7], [4, 6, 5, 7], [8, 8, 12, 12], [0, 0, 2, 13]], "occluder": [[8, 8, 12, 12], [0, 0, 2, 13], [5, 6, 5, 6], [3, 6, 3, 6], [3, 5, 5, 7]], "threshold": [0.0, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.9],
**Measured** operational_state (final); observed_state (final); observability status; observed cycles / true cycles; operational digest
**Failures (runs the engine refused)** 0 · **null results recorded** 9

| scenario | parameter | first value at which the observer disagrees with the run |
|---|---|---|
| unperturbed (ACTIVE) | sampling_interval | 2 |
| unperturbed (ACTIVE) | spatial_stride | 2 |
| unperturbed (ACTIVE) | region | [4, 6, 5, 7] |
| unperturbed (ACTIVE) | occluder | [3, 6, 3, 6] |
| unperturbed (ACTIVE) | threshold | 0.1 |
| unperturbed (ACTIVE) | window | 6 |
| unperturbed (ACTIVE) | address_resolution | none in the sweep (null) |
| interaction cut 100-150 (collapses) | sampling_interval | none in the sweep (null) |
| interaction cut 100-150 (collapses) | spatial_stride | none in the sweep (null) |
| interaction cut 100-150 (collapses) | region | none in the sweep (null) |
| interaction cut 100-150 (collapses) | occluder | none in the sweep (null) |
| interaction cut 100-150 (collapses) | threshold | none in the sweep (null) |
| interaction cut 100-150 (collapses) | window | none in the sweep (null) |
| interaction cut 100-150 (collapses) | address_resolution | none in the sweep (null) |
| cut 100-150 + pulse 2.0 at 151 (recovers) | sampling_interval | 2 |
| cut 100-150 + pulse 2.0 at 151 (recovers) | spatial_stride | 2 |
| cut 100-150 + pulse 2.0 at 151 (recovers) | region | [4, 6, 5, 7] |
| cut 100-150 + pulse 2.0 at 151 (recovers) | occluder | [3, 6, 3, 6] |
| cut 100-150 + pulse 2.0 at 151 (recovers) | threshold | 0.1 |
| cut 100-150 + pulse 2.0 at 151 (recovers) | window | 6 |
| cut 100-150 + pulse 2.0 at 151 (recovers) | address_resolution | none in the sweep (null) |

Replay identical after every observation: **True**.

Observed-collapse tick minus operational-collapse tick in the collapsing scenario, over every observation of the sweep that disagrees or agrees: [-101.0, -95.0, -42.0, -36.0, -24.0, -12.0, 0.0, 24.0] (negative: an observer that resolves no cycle concludes COLLAPSED at the end of its window, long before the run collapses; that is a limit of the observation, not an early collapse).

### Experiment B — XenoBody boundary perturbation (5 boundary kinds × durations 10, 20, 40, 80 ticks, 5 seeds)

*Result.* The **observation boundary** (the observer's region excludes both configurations) changed nothing in the run: the operation is bit for bit the unperturbed one in every seed and duration, and only the observed state differs (OUTSIDE_OBSERVATION_REGION): the observation boundary is not an operational boundary.
The **coupling**, **resource-exchange (renewal feedback)** and **Address Domain** (A2's address lost) perturbations collapsed the run in 5 of 5 seeds at every duration from 10 ticks up (mean collapse tick 149, 144 and 144): the collapse comes at the end of the 48-tick window whatever the duration, because restoring the relation does not restart a cycle that has stopped.
The **history-access** perturbation did not collapse the run when it lasted 10 ticks (the operation changed in detail only: a null result for collapse) and collapsed it in all seeds from 20 ticks (mean tick 157). *Recovery.* Without a pulse no collapsed run recovered. With a pulse after the restoration the coupling and Address Domain perturbations recovered in 5 of 5 seeds at every duration; the resource-exchange perturbation recovered in 0 of 5 and the history-access perturbation in 3 of 5 at 20 ticks and 0 of 5 beyond:
a resource pulse restores what a cut coupling or a lost address interrupted and does not restore what a cut renewal feedback or lost history removed. *Control.* A pulse alone into the unperturbed run at tick 111 or 121 ends COLLAPSED (and ACTIVE at 141 and 181): the pulse has an effect of its own, which is why `recovers_with_pulse` is counted only for runs that collapsed.
*B3-only persistence.* With only the operational components of B1 or B2 retained the operation persists in 0 of 5 seeds, with B3 in 5 of 5: closure of the recursion first holds in B3, as in the earlier stages. For B1, B2 and B3 the legs a perturbation breaks are recorded per run (`bodies`): B1 holds the two legs that need only A1 and its sensor, which none of these perturbations touches.
*Limit.* A perturbation here is a removal and restoration of one relation at a fixed tick; the duration sweep shows how long the relation may be absent in this model, not how long any real boundary may be.

**Seeds** [1, 2, 3, 4, 5] · **fixed** {"configuration": "MEOS-0 default", "perturbation tick": 100, "restoration": "after the stated duration", "pulse": "2.0 at the cell (3, 6), one tick after the restoration"}
**Manipulated** {"boundary": ["observation", "coupling", "resource_exchange", "history_access", "address_domain"], "duration (ticks)": [10, 20, 40, 80]}
**Measured** state before / at end of perturbation / final; collapse tick; recovery without a pulse; recovery with a pulse; paths cut and paths changed; observability status; B1/B2/B3 legs broken
**Failures (runs the engine refused)** 0 · **null results recorded** 5

| boundary | duration | collapsed (of 5) | recovered w/o pulse | recovered with pulse | operation changed | pulse alone, final states | paths cut directly | observability |
|---|---|---|---|---|---|---|---|---|
| observation | 10 | 0 | 0 | 0 | 0 | COLLAPSED | - | OUTSIDE_OBSERVATION_REGION |
| observation | 20 | 0 | 0 | 0 | 0 | COLLAPSED | - | OUTSIDE_OBSERVATION_REGION |
| observation | 40 | 0 | 0 | 0 | 0 | ACTIVE | - | OUTSIDE_OBSERVATION_REGION |
| observation | 80 | 0 | 0 | 0 | 0 | ACTIVE | - | OUTSIDE_OBSERVATION_REGION |
| coupling | 10 | 5 | 0 | 5 | 5 | COLLAPSED | coupling | SUFFICIENT |
| coupling | 20 | 5 | 0 | 5 | 5 | COLLAPSED | coupling | SUFFICIENT |
| coupling | 40 | 5 | 0 | 5 | 5 | ACTIVE | coupling | SUFFICIENT |
| coupling | 80 | 5 | 0 | 5 | 5 | ACTIVE | coupling | SUFFICIENT |
| resource_exchange | 10 | 5 | 0 | 0 | 5 | COLLAPSED | recovery,resource | SUFFICIENT |
| resource_exchange | 20 | 5 | 0 | 0 | 5 | COLLAPSED | recovery,resource | SUFFICIENT |
| resource_exchange | 40 | 5 | 0 | 0 | 5 | ACTIVE | recovery,resource | SUFFICIENT |
| resource_exchange | 80 | 5 | 0 | 0 | 5 | ACTIVE | recovery,resource | SUFFICIENT |
| history_access | 10 | 0 | 0 | 0 | 5 | COLLAPSED | history_access | SUFFICIENT |
| history_access | 20 | 5 | 0 | 3 | 5 | COLLAPSED | history_access | SUFFICIENT |
| history_access | 40 | 5 | 0 | 0 | 5 | ACTIVE | history_access | SUFFICIENT |
| history_access | 80 | 5 | 0 | 0 | 5 | ACTIVE | history_access | SUFFICIENT |
| address_domain | 10 | 5 | 0 | 5 | 5 | COLLAPSED | - | SUFFICIENT |
| address_domain | 20 | 5 | 0 | 5 | 5 | COLLAPSED | - | SUFFICIENT |
| address_domain | 40 | 5 | 0 | 5 | 5 | ACTIVE | - | SUFFICIENT |
| address_domain | 80 | 5 | 0 | 5 | 5 | ACTIVE | - | SUFFICIENT |

| body | retained components | persists (of 5) |
|---|---|---|
| B1 | A1, sensor_resource | 0/5 |
| B2 | A1, sensor_resource, sensor_alteration, interaction_channel | 0/5 |
| B3 | A1, A2, sensor_resource, sensor_alteration, interaction_channel, feedback, resource_renewal, history | 5/5 |

### Experiment C — Address Domain interventions (7 modes × targets A1, A2, both × durations 10, 40 ticks, 5 seeds)

*Change of measure.* "The run changed" is decided on the **dynamics** (every frame without the fault bookkeeping), not on the result digest, because the digest covers the intervention log and so differs for any intervention. This corrected an earlier reading in which every fault looked like a change.
*Result.* **Loss** and **partial addressability** collapse the run in every seed for every target; a pulse after the restoration recovers loss of A2 or of both (5 of 5) and does not recover loss of A1 (0 of 5): the loss of A1's address is not repaired by restoring it and pulsing. **Reassignment** (the configuration moved away, not back) collapses in every seed and no pulse recovers it.
**Fragmentation** of A2's window (to 25 %) never collapsed the run (0 of 5, the dynamics changed in 4 of 5 seeds: a null result for collapse), while fragmentation of A1, or of both, collapsed 4 of 5. **Delayed** update: A1 or both collapse in every seed; A2 does not (the stale address still names a productive cell, the configuration keeps firing and walks back; the dynamics changed in 5 of 5 seeds).
**Collision** and **stale** are null results in the strict sense: the dynamics were bit for bit the unperturbed run's in every seed, target and duration (a configuration that does not move cannot go stale; and the collision fault moves a configuration onto the other's cell, which at tick 100 it already occupies: in the default arrangement A1 and A2 stand on the same cell by then). They are reported as nulls and are limits of what these two faults can do in this model, not evidence about addressing.
*Limit.* The faults are faults of the attribution of a configuration to a cell in this model; they model no network or naming system.

**Seeds** [1, 2, 3, 4, 5] · **fixed** {"configuration": "MEOS-0 default", "intervention tick": 100, "restoration": "after the stated duration (for reassign: the configuration is not moved back)", "pulse": "2.0 one tick after the restoration"}
**Manipulated** {"mode": ["loss", "reassign", "fragment", "collision", "partial", "delayed", "stale"], "target": ["A1", "A2", "both"], "duration": [10, 40]}
**Measured** operational state at the end; collapse tick; recovery status without / with a pulse; address integrity during the fault; observed state under address_resolution 0.9
**Failures (runs the engine refused)** 0 · **null results recorded** 16

| mode | target | duration | collapsed | ACTIVE at end | ACTIVE with pulse | dynamics changed | min integrity |
|---|---|---|---|---|---|---|---|
| loss | A1 | 10 | 5 | 0 | 0 | 5 | 0.0 |
| loss | A1 | 40 | 5 | 0 | 0 | 5 | 0.0 |
| loss | A2 | 10 | 5 | 0 | 5 | 5 | 0.0 |
| loss | A2 | 40 | 5 | 0 | 5 | 5 | 0.0 |
| loss | both | 10 | 5 | 0 | 5 | 5 | 0.0 |
| loss | both | 40 | 5 | 0 | 5 | 5 | 0.0 |
| reassign | A1 | 10 | 5 | 0 | 0 | 5 | 1.0 |
| reassign | A1 | 40 | 5 | 0 | 0 | 5 | 1.0 |
| reassign | A2 | 10 | 5 | 0 | 0 | 5 | 1.0 |
| reassign | A2 | 40 | 5 | 0 | 0 | 5 | 1.0 |
| reassign | both | 10 | 5 | 0 | 0 | 5 | 1.0 |
| reassign | both | 40 | 5 | 0 | 0 | 5 | 1.0 |
| fragment | A1 | 10 | 4 | 1 | 0 | 4 | 0.4133 |
| fragment | A1 | 40 | 4 | 1 | 1 | 4 | 0.4133 |
| fragment | A2 | 10 | 0 | 5 | 4 | 4 | 0.4133 |
| fragment | A2 | 40 | 0 | 5 | 5 | 4 | 0.4133 |
| fragment | both | 10 | 4 | 1 | 0 | 4 | 0.4133 |
| fragment | both | 40 | 4 | 1 | 1 | 4 | 0.4133 |
| collision | A1 | 10 | 0 | 5 | 0 | 0 | 1.0 |
| collision | A1 | 40 | 0 | 5 | 5 | 0 | 1.0 |
| collision | A2 | 10 | 0 | 5 | 0 | 0 | 1.0 |
| collision | A2 | 40 | 0 | 5 | 5 | 0 | 1.0 |
| collision | both | 10 | 0 | 5 | 0 | 0 | 1.0 |
| collision | both | 40 | 0 | 5 | 5 | 0 | 1.0 |
| partial | A1 | 10 | 5 | 0 | 0 | 5 | 0.5 |
| partial | A1 | 40 | 5 | 0 | 0 | 5 | 0.5 |
| partial | A2 | 10 | 5 | 0 | 5 | 5 | 0.5 |
| partial | A2 | 40 | 5 | 0 | 0 | 5 | 0.5 |
| partial | both | 10 | 5 | 0 | 3 | 5 | 0.5 |
| partial | both | 40 | 5 | 0 | 0 | 5 | 0.5 |
| delayed | A1 | 10 | 5 | 0 | 0 | 5 | 0.0 |
| delayed | A1 | 40 | 5 | 0 | 0 | 5 | 0.0 |
| delayed | A2 | 10 | 0 | 5 | 0 | 5 | 0.0 |
| delayed | A2 | 40 | 0 | 5 | 5 | 5 | 0.0 |
| delayed | both | 10 | 5 | 0 | 0 | 5 | 0.0 |
| delayed | both | 40 | 5 | 0 | 0 | 5 | 0.0 |
| stale | A1 | 10 | 0 | 5 | 0 | 0 | 1.0 |
| stale | A1 | 40 | 0 | 5 | 5 | 0 | 1.0 |
| stale | A2 | 10 | 0 | 5 | 0 | 0 | 1.0 |
| stale | A2 | 40 | 0 | 5 | 5 | 0 | 1.0 |
| stale | both | 10 | 0 | 5 | 0 | 0 | 1.0 |
| stale | both | 40 | 0 | 5 | 5 | 0 | 1.0 |

### Experiment D — SSS boundary sweep (grid of 96 points, 2 seeds; transition points by bisection)

*Result.* Of 96 grid points of (scale 0.5–2.0, size 0.5–2.0, speed 0.5–2.0), 86 are COLLAPSED, 2 RECOVERY-CAPABLE, 8 OBSERVATION-SENSITIVE and none METASTABLE on the grid. **Every ACTIVE point is also observation-sensitive** under the stage-two definition (an observation at interval 2 concludes otherwise), so the region "ACTIVE and robust to interval 2" is empty on this grid.
*Transition points* (others at 1.0, bisected to ≤ 0.008): the ACTIVE island is scale up to 1.219 (at 1.2227 the class is METASTABLE; no lower scale down to 0.5 collapses it: a null result), size between 0.688 and 1.242, speed between 0.805 and 1.195 (just below 0.797 METASTABLE, above 1.203 COLLAPSED).
The island is narrow in size and speed (about ±20 % of the default) and one-sided in scale. *Limit.* Scale, size and speed are model parameters of sensing reach, footprint and the process clock; the region is a region of this parameter space.

**Seeds** [1, 2] · **fixed** {"configuration": "MEOS-0 default", "horizon": 480, "region definitions": "ACTIVE at ticks 239 and 479 in every seed; COLLAPSED at 239 in every seed; otherwise METASTABLE; RECOVERY-CAPABLE = COLLAPSED but ACTIVE after a pulse of 2.0 at 300; OBSERVATION-SENSITIVE = ACTIVE but an observation at interval 2 concludes otherwise"}
**Manipulated** {"scale": [0.5, 0.75, 1.0, 1.25, 1.5, 2.0], "size": [0.5, 1.0, 1.5, 2.0], "speed": [0.5, 1.0, 1.5, 2.0]}
**Measured** region of every grid point; counts per region; transition points along each axis (others at 1.0)
**Failures (runs the engine refused)** 0 · **null results recorded** 1

Regions over 96 grid points: {"OBSERVATION-SENSITIVE": 8, "COLLAPSED": 86, "RECOVERY-CAPABLE": 2}

| axis | side | last ACTIVE | first not ACTIVE | class there | resolution |
|---|---|---|---|---|---|
| scale | above | 1.2188 | 1.2227 | metastable | 0.0039 |
| scale | below | 0.5 | None | - | - |
| size | above | 1.2422 | 1.25 | COLLAPSED | 0.0078 |
| size | below | 0.6875 | 0.6797 | COLLAPSED | 0.0078 |
| speed | above | 1.1953 | 1.2031 | COLLAPSED | 0.0078 |
| speed | below | 0.8047 | 0.7969 | metastable | 0.0078 |

| scale | size | speed | region |
|---|---|---|---|
| 0.5 | 0.5 | 0.5 | OBSERVATION-SENSITIVE |
| 0.5 | 0.5 | 1.0 | OBSERVATION-SENSITIVE |
| 0.5 | 1.0 | 0.5 | OBSERVATION-SENSITIVE |
| 0.5 | 1.0 | 1.0 | OBSERVATION-SENSITIVE |
| 0.5 | 1.0 | 1.5 | OBSERVATION-SENSITIVE |
| 0.5 | 1.0 | 2.0 | OBSERVATION-SENSITIVE |
| 0.75 | 1.0 | 1.0 | OBSERVATION-SENSITIVE |
| 0.75 | 1.0 | 1.5 | RECOVERY-CAPABLE |
| 1.0 | 1.0 | 1.0 | OBSERVATION-SENSITIVE |
| 1.0 | 1.0 | 1.5 | RECOVERY-CAPABLE |

### Experiment E — M2 sensing ablation (none / direct / delayed(3) / noisy(0.05) / threshold; weights 1 and 4; 6 scenarios; 5 seeds)

*Downstream path.* M2 enters A1's resource-sensor signal. *Result.* In the unperturbed scenario no M2 condition changed collapse frequency, energy, cycles or A1→A2 lag except noisy sensing (collapse in 1 of 5 seeds at weight 1: fewer cycles, less energy). **Direct and thresholded (0.05) sensing make history unnecessary**: with history removed the operation stays ACTIVE in 5 of 5 seeds (against 0 of 5 for none).
**Noisy sensing at weight 4 rescues** the scale-1.5 run (collapse 5/5 → 0/5) and the interrupted run without a pulse (recovery 0/5 → 5/5), and partly the renewal-efficiency (collapse 5/5 → 2/5) and 50 %-addressable (collapse 5/5 → 2/5) perturbations; **delayed(3) at weight 4 rescues scale 1.5** (collapse 5/5 → 0/5) and nothing else.
*Null results* (23 recorded): delayed sensing changes nothing in the unperturbed run, the interrupted runs and the Address Domain perturbation; direct sensing changes nothing in the interrupted run without a pulse, the renewal-efficiency run at weight 1 and the partial-address run; a threshold of 0.2 is bit for bit the run without M2 in every scenario (the M2 signal never reaches 0.2 in these runs).
*Unexpected.* The rescue by noisy sensing is a rescue by a random, positively biased term (the sensed value is clipped at zero), not by information about A2; it is reported as an effect of the added term and is not evidence for any mechanism of coordination (the A1→A2 lag is unchanged except in one cell). *Limit.* M2 sensing is one added term in A1's sensor signal; "no difference" means no difference in these measured quantities for these seeds and scenarios.

**Seeds** [1, 2, 3, 4, 5] · **fixed** {"configuration": "MEOS-0 default", "downstream path": "M2 (A2's alteration of the environment) is added to A1's resource-sensor signal, so it enters A1's differentiated stimulus and its firing condition", "observation for the observability column": {"sampling_interval": 2}}
**Manipulated** {"m2 sensing": ["none", "direct w=1", "direct w=4", "delayed(3) w=1", "delayed(3) w=4", "noisy(0.05) w=1", "noisy(0.05) w=4", "threshold 0.05 w=4", "threshold 0.2 w=4"], "scenario": ["unperturbed", "cut 100-150 + pulse 2.0", "cut 100-150, no pulse", "scale 1.5", "renewal efficiency 0.7 at 100", "A2 partially addressable (50 %) from 100"]}
**Measured** collapse frequency (any COLLAPSED tick); recovery rate (collapsed, then ACTIVE at the end); cumulative energy use; A1 to A2 coordination (cycles, mean A1-act to A2-fire lag); history dependence (ACTIVE with history removed); observability effect (observed interval 2 disagrees with the run)
**Failures (runs the engine refused)** 0 · **null results recorded** 23

| scenario | M2 sensing | collapse freq. | recovery rate | mean energy | mean cycles | A1→A2 lag | ACTIVE w/o history | observation disagrees | identical to none | differs from none in |
|---|---|---|---|---|---|---|---|---|---|---|
| unperturbed | none | 0.0 | None | 119.08 | 47.0 | 1.0 | 0.0 | 1.0 | - | - |
| unperturbed | direct w=1 | 0.0 | None | 119.08 | 47.0 | 1.0 | 1.0 | 1.0 | False | active_without_history_frequency |
| unperturbed | direct w=4 | 0.0 | None | 119.08 | 47.0 | 1.0 | 1.0 | 1.0 | False | active_without_history_frequency |
| unperturbed | delayed(3) w=1 | 0.0 | None | 119.08 | 47.0 | 1.0 | 0.0 | 1.0 | False | nothing |
| unperturbed | delayed(3) w=4 | 0.0 | None | 119.08 | 47.0 | 1.0 | 0.0 | 1.0 | False | nothing |
| unperturbed | noisy(0.05) w=1 | 0.2 | 0.0 | 117.4 | 43.6 | 1.0 | 0.0 | 0.8 | False | collapse_frequency, recovery_rate, persist_frequency, mean_energy, mean_cycles, observation_disagrees_frequency |
| unperturbed | noisy(0.05) w=4 | 0.0 | None | 118.72 | 39.8 | 1.0 | 0.6 | 1.0 | False | mean_energy, mean_cycles, active_without_history_frequency |
| unperturbed | threshold 0.05 w=4 | 0.0 | None | 119.08 | 47.0 | 1.0 | 1.0 | 1.0 | False | active_without_history_frequency |
| unperturbed | threshold 0.2 w=4 | 0.0 | None | 119.08 | 47.0 | 1.0 | 0.0 | 1.0 | True | nothing |
| cut 100-150 + pulse 2.0 | none | 1.0 | 1.0 | 167.08 | 61.0 | 1.0 | 0.0 | 1.0 | - | - |
| cut 100-150 + pulse 2.0 | direct w=1 | 1.0 | 1.0 | 167.08 | 61.0 | 1.0 | 1.0 | 1.0 | False | active_without_history_frequency |
| cut 100-150 + pulse 2.0 | direct w=4 | 1.0 | 1.0 | 167.08 | 61.0 | 1.0 | 1.0 | 1.0 | False | active_without_history_frequency |
| cut 100-150 + pulse 2.0 | delayed(3) w=1 | 1.0 | 1.0 | 167.08 | 61.0 | 1.0 | 0.0 | 1.0 | False | nothing |
| cut 100-150 + pulse 2.0 | delayed(3) w=4 | 1.0 | 1.0 | 167.08 | 61.0 | 1.0 | 0.0 | 1.0 | False | nothing |
| cut 100-150 + pulse 2.0 | noisy(0.05) w=1 | 1.0 | 1.0 | 167.08 | 60.2 | 1.0 | 0.0 | 1.0 | False | mean_cycles |
| cut 100-150 + pulse 2.0 | noisy(0.05) w=4 | 1.0 | 1.0 | 166.984 | 51.0 | 1.0 | 0.8 | 1.0 | False | mean_energy, mean_cycles, active_without_history_frequency |
| cut 100-150 + pulse 2.0 | threshold 0.05 w=4 | 1.0 | 1.0 | 167.08 | 61.0 | 1.0 | 1.0 | 1.0 | False | active_without_history_frequency |
| cut 100-150 + pulse 2.0 | threshold 0.2 w=4 | 1.0 | 1.0 | 167.08 | 61.0 | 1.0 | 0.0 | 1.0 | True | nothing |
| cut 100-150, no pulse | none | 1.0 | 0.0 | 135.52 | 20.0 | 1.0 | 0.0 | 0.0 | - | - |
| cut 100-150, no pulse | direct w=1 | 1.0 | 0.0 | 135.52 | 20.0 | 1.0 | 0.0 | 0.0 | False | nothing |
| cut 100-150, no pulse | direct w=4 | 1.0 | 0.0 | 135.52 | 20.0 | 1.0 | 0.0 | 0.0 | False | nothing |
| cut 100-150, no pulse | delayed(3) w=1 | 1.0 | 0.0 | 135.52 | 20.0 | 1.0 | 0.0 | 0.0 | False | nothing |
| cut 100-150, no pulse | delayed(3) w=4 | 1.0 | 0.0 | 135.52 | 20.0 | 1.0 | 0.0 | 0.0 | False | nothing |
| cut 100-150, no pulse | noisy(0.05) w=1 | 1.0 | 0.2 | 141.832 | 23.0 | 1.0 | 0.0 | 0.2 | False | recovery_rate, persist_frequency, mean_energy, mean_cycles, observation_disagrees_frequency |
| cut 100-150, no pulse | noisy(0.05) w=4 | 1.0 | 1.0 | 166.84 | 47.6 | 1.0 | 0.8 | 1.0 | False | recovery_rate, persist_frequency, mean_energy, mean_cycles, active_without_history_frequency, observation_disagrees_frequency |
| cut 100-150, no pulse | threshold 0.05 w=4 | 1.0 | 0.0 | 135.52 | 20.0 | 1.0 | 0.0 | 0.0 | False | nothing |
| cut 100-150, no pulse | threshold 0.2 w=4 | 1.0 | 0.0 | 135.52 | 20.0 | 1.0 | 0.0 | 0.0 | True | nothing |
| scale 1.5 | none | 1.0 | 0.0 | 72.17 | 2.0 | 1.0 | 0.0 | 0.0 | - | - |
| scale 1.5 | direct w=1 | 1.0 | 0.0 | 73.57 | 2.8 | 1.0 | 0.0 | 0.0 | False | mean_energy, mean_cycles |
| scale 1.5 | direct w=4 | 1.0 | 0.0 | 73.92 | 3.0 | 1.0 | 0.0 | 0.0 | False | mean_energy, mean_cycles |
| scale 1.5 | delayed(3) w=1 | 1.0 | 0.0 | 73.92 | 3.0 | 1.0 | 0.0 | 0.0 | False | mean_energy, mean_cycles |
| scale 1.5 | delayed(3) w=4 | 0.0 | None | 119.08 | 40.0 | 1.0 | 0.0 | 1.0 | False | collapse_frequency, recovery_rate, persist_frequency, mean_energy, mean_cycles, observation_disagrees_frequency |
| scale 1.5 | noisy(0.05) w=1 | 1.0 | 0.0 | 75.67 | 2.4 | 1.0 | 0.0 | 0.0 | False | mean_energy, mean_cycles |
| scale 1.5 | noisy(0.05) w=4 | 0.0 | None | 118.092 | 27.0 | 1.0 | 0.8 | 1.0 | False | collapse_frequency, recovery_rate, persist_frequency, mean_energy, mean_cycles, active_without_history_frequency, observation_disagrees_frequency |
| scale 1.5 | threshold 0.05 w=4 | 1.0 | 0.0 | 73.92 | 3.0 | 1.0 | 0.0 | 0.0 | False | mean_energy, mean_cycles |
| scale 1.5 | threshold 0.2 w=4 | 1.0 | 0.0 | 72.17 | 2.0 | 1.0 | 0.0 | 0.0 | True | nothing |
| renewal efficiency 0.7 at 100 | none | 1.0 | 0.0 | 119.8 | 20.0 | 1.0 | 0.0 | 0.0 | - | - |
| renewal efficiency 0.7 at 100 | direct w=1 | 1.0 | 0.0 | 119.8 | 20.0 | 1.0 | 0.0 | 0.0 | False | nothing |
| renewal efficiency 0.7 at 100 | direct w=4 | 1.0 | 0.0 | 120.4 | 21.0 | 1.0 | 0.0 | 0.0 | False | mean_energy, mean_cycles |
| renewal efficiency 0.7 at 100 | delayed(3) w=1 | 1.0 | 0.0 | 119.8 | 20.0 | 1.0 | 0.0 | 0.0 | False | nothing |
| renewal efficiency 0.7 at 100 | delayed(3) w=4 | 1.0 | 0.0 | 119.8 | 20.0 | 1.0 | 0.0 | 0.0 | False | nothing |
| renewal efficiency 0.7 at 100 | noisy(0.05) w=1 | 1.0 | 0.0 | 124.552 | 20.6 | 1.0 | 0.0 | 0.2 | False | mean_energy, mean_cycles, observation_disagrees_frequency |
| renewal efficiency 0.7 at 100 | noisy(0.05) w=4 | 0.4 | 0.5 | 142.032 | 33.6 | 1.0 | 0.4 | 1.0 | False | collapse_frequency, recovery_rate, persist_frequency, mean_energy, mean_cycles, active_without_history_frequency, observation_disagrees_frequency |
| renewal efficiency 0.7 at 100 | threshold 0.05 w=4 | 1.0 | 0.0 | 120.4 | 21.0 | 1.0 | 0.0 | 0.0 | False | mean_energy, mean_cycles |
| renewal efficiency 0.7 at 100 | threshold 0.2 w=4 | 1.0 | 0.0 | 119.8 | 20.0 | 1.0 | 0.0 | 0.0 | True | nothing |
| A2 partially addressable (50 %) from 100 | none | 1.0 | 0.0 | 101.77 | 19.4 | 1.0 | 0.0 | 0.0 | - | - |
| A2 partially addressable (50 %) from 100 | direct w=1 | 1.0 | 0.0 | 101.77 | 19.4 | 1.0 | 0.0 | 0.0 | False | nothing |
| A2 partially addressable (50 %) from 100 | direct w=4 | 1.0 | 0.0 | 101.77 | 19.4 | 1.0 | 0.0 | 0.0 | False | nothing |
| A2 partially addressable (50 %) from 100 | delayed(3) w=1 | 1.0 | 0.0 | 101.77 | 19.4 | 1.0 | 0.0 | 0.0 | False | nothing |
| A2 partially addressable (50 %) from 100 | delayed(3) w=4 | 1.0 | 0.0 | 101.77 | 19.4 | 1.0 | 0.0 | 0.0 | False | nothing |
| A2 partially addressable (50 %) from 100 | noisy(0.05) w=1 | 1.0 | 0.0 | 102.47 | 19.0 | 1.0 | 0.0 | 0.0 | False | mean_energy, mean_cycles |
| A2 partially addressable (50 %) from 100 | noisy(0.05) w=4 | 0.4 | 0.5 | 108.17 | 24.2 | 1.0363 | 0.4 | 0.8 | False | collapse_frequency, recovery_rate, persist_frequency, mean_energy, mean_cycles, mean_a1_a2_lag, active_without_history_frequency, observation_disagrees_frequency |
| A2 partially addressable (50 %) from 100 | threshold 0.05 w=4 | 1.0 | 0.0 | 101.77 | 19.4 | 1.0 | 0.0 | 0.0 | False | nothing |
| A2 partially addressable (50 %) from 100 | threshold 0.2 w=4 | 1.0 | 0.0 | 101.77 | 19.4 | 1.0 | 0.0 | 0.0 | True | nothing |

**Null results (E)**

- unperturbed / delayed(3) w=1: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- unperturbed / delayed(3) w=4: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- unperturbed / threshold 0.2 w=4: no difference from M2 sensing 'none' in any measured quantity (the runs are bit for bit identical)
- cut 100-150 + pulse 2.0 / delayed(3) w=1: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- cut 100-150 + pulse 2.0 / delayed(3) w=4: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- cut 100-150 + pulse 2.0 / threshold 0.2 w=4: no difference from M2 sensing 'none' in any measured quantity (the runs are bit for bit identical)
- cut 100-150, no pulse / direct w=1: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- cut 100-150, no pulse / direct w=4: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- cut 100-150, no pulse / delayed(3) w=1: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- cut 100-150, no pulse / delayed(3) w=4: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- cut 100-150, no pulse / threshold 0.05 w=4: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- cut 100-150, no pulse / threshold 0.2 w=4: no difference from M2 sensing 'none' in any measured quantity (the runs are bit for bit identical)
- scale 1.5 / threshold 0.2 w=4: no difference from M2 sensing 'none' in any measured quantity (the runs are bit for bit identical)
- renewal efficiency 0.7 at 100 / direct w=1: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- renewal efficiency 0.7 at 100 / delayed(3) w=1: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- renewal efficiency 0.7 at 100 / delayed(3) w=4: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- renewal efficiency 0.7 at 100 / threshold 0.2 w=4: no difference from M2 sensing 'none' in any measured quantity (the runs are bit for bit identical)
- A2 partially addressable (50 %) from 100 / direct w=1: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- A2 partially addressable (50 %) from 100 / direct w=4: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- A2 partially addressable (50 %) from 100 / delayed(3) w=1: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- A2 partially addressable (50 %) from 100 / delayed(3) w=4: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- A2 partially addressable (50 %) from 100 / threshold 0.05 w=4: no difference from M2 sensing 'none' in any measured quantity (the runs differ in detail)
- A2 partially addressable (50 %) from 100 / threshold 0.2 w=4: no difference from M2 sensing 'none' in any measured quantity (the runs are bit for bit identical)

## 11. Visual mapping and local metrics

| record or reading | what the body or sheet does |
|---|---|
| (Stage 3 rows) | unchanged, see `docs/ECOSYSTEM_MEOS_STAGE3.md` section 4 |
| SSS scale | observer boom sections extend further (up to 0.35 u of preload) |
| SSS size | probe ring tilts (up to ±0.2 rad) |
| SSS speed | coupling swings slightly off its resting line (tension), reservoir level shifts (±0.1) |
| SSS region METASTABLE / RECOVERY-CAPABLE | archive latch ajar (0.6 / 0.9 rad) while history is enabled |
| M2 sensing configured | node B's probe B2 is the M2 tap: extended while A1's M2 term is zero, `sampling` while nonzero, `overloaded` for a noisy tap, retracted when collapsed |
| path states | cables of a path whose layer is on take the path's state on the sheet (red dashed = cut, heavier = active, faint = quiet) |
| cables | harness conductors (thin wires that bow out between ties), cable ties, strand fan-out at connectors; three further routes: ARCH (history access), OBSV (observation), REC (recovery) |

A mapping is a design choice of the view, written at the head of `bodyState.ts` and in `mechanics.ts` and tested; it is not an identification.

**New screenshots** (`docs/ecosystem/visual/`, camera record `cameras-balanced-stage4.json`; the 29 Stage 3 images and their record are untouched; `stage4_recapture/` holds the six Stage 3 cable and probe shots taken again with this stage's build for the metrics above):
`30-observation-failure` (probes overloaded: the observation cannot resolve the operation, the run is unchanged) · `31-boundary-b1`, `32-boundary-b3` (the research map with the XenoBody boundary of B1 and of B3, three boundary line types) · `33-address-loss`, `34-address-recovery` (A2's address lost at 100, restored at 140 with a pulse at 141; ticks 120 and 185) and their maps `43-address-loss-map`, `44-address-recovery-map` ·
`35-sss-active`, `36-sss-metastable`, `37-sss-collapsed` (SSS 1/1/1, 1.2227/1/1 and 1.5/1/1: boom reach and latch) · `38-m2-sensing` (M2 direct, weight 4: node B's probe B2 is the M2 tap) · `39-technical-paths` (the five path layers with the coupling cut) · `40-technical-observation-region` (region, stride-2 lattice, occluder, COMBINED_LIMITS) ·
`41-replay-markers` (the RESEARCH tab with the marker row and observed-state strip) · `42-compare-baseline-intervention-recovered` (ticks 99, 149 and 185 of one record, with the delta table).

**Cables and the observer: local metrics** (`backend/scripts/visual_crops_local.py`, `docs/ecosystem/visual/metrics_crops_stage4_vs_stage3.json`; the same crops and cameras as Stage 3, captures resampled to 766 px; crude proxies, none a perceptual judgement; the reference images are not stored, their Stage 3 statistics are in `metrics_crops_at_reference_resolution.json`):

| shot / crop | contour complexity Stage 3 → Stage 4 | edge density | occupied area | reference (Stage 3 record) |
|---|---|---|---|---|
| 14 experimental body / cable region | 0.625 → **0.618** | 0.335 → 0.345 | 0.598 → 0.633 | 1.587 |
| 20 close cable / cable region | 0.444 → **0.473** | 0.115 → 0.130 | 0.369 → 0.386 | 1.587 |
| 15 observation node / cable region | 0.322 → 0.323 | 0.212 → 0.211 | 0.548 → 0.549 | 1.403 |
| 29 observer hero / cable region | 0.484 → 0.492 | 0.207 → 0.206 | 0.462 → 0.465 | 1.403 |
| 14 / probe region | 0.940 → 0.888 | 0.173 → 0.208 | 0.302 → 0.349 | — |

**Reading.** The harness conductors, ties and strand fans (and the three cables of the history, observation and recovery paths) raised the contour complexity of the close cable shot by 7 % and left the cable crop of capture 14 where it was (−1 %: the added cable area fills the crop, so the outline per occupied pixel did not rise although the edge density and the occupied area did).
The value of the reference (1.59) is not approached. The observer's cable crops did not change measurably (0.322 → 0.323 and 0.484 → 0.492; the observer's limb and boom cables received the same conductors and ties, tagged as the observation path); no other observer geometry was added in this stage beyond state-linked poses (the old comparison camera `observer` is kept). These are proxies: they say how much outline per occupied pixel the crop has, not that a picture looks like a reference.
**What was done in the cables is tied to the paths:** every cable of the non-central body but one (the ground lead BG) names the operational path it carries (`ARCH` history access, `OBSV` observation, `REC` recovery, the coupling halves and `JB` coupling, `JC`/`AC`/`AB`/`AJ`/`CRES` resource); the technical sheet colours a cable by the state of its path when that path's layer is on (red dashed: cut).
The three new cables end where their path does (the archive unit and the junction; node A and a ground port on the side of the observation node; the reservoir and a pulse port on the ground); no cable was added without a path.

## 12. Performance

**Conditions.** The host was loaded by other applications throughout this stage (load average about 8), so every frame time here is higher than in `perf_stage3/` — for the unchanged Stage 3 build as well. Only builds measured **interleaved in time in the same session** are compared; the files and their order are in `docs/ecosystem/perf_stage4/README.md`.
GPU time is not exposed by this headless browser, so the figures are wall time with a GPU sync per frame (`window.__meos.benchmark`), 1672 × 808, GPU through ANGLE/Metal. Targets: `performance` 60 fps; `balanced` median ≥ 50 fps (≤ 20 ms) and 95th percentile ≤ 24 ms; `high` not much worse than before.

**All three tiers, Stage 3 (`93119a0`) against this stage, 2 interleaved repetitions, median of the repetitions** (ms; static camera, then the orbiting camera; `final_tiers/summary.json`):

| tier | camera | static median / p95: Stage 3 → Stage 4 | orbit median / p95: Stage 3 → Stage 4 | draw calls | triangles |
|---|---|---|---|---|---|
| performance | overview | 7.7 / 12.6 → 8.2 / 10.7 | 10.4 / 17.9 → 9.2 / 13.0 | 437 → 439 | 376,038 → 395,384 |
| performance | habitat | 9.4 / 12.6 → 9.6 / 14.1 | 10.7 / 13.2 → 9.9 / 12.6 | 416 → 417 | 545,234 → 577,006 |
| performance | body | 6.4 / 10.4 → 6.8 / 9.9 | 6.7 / 9.8 → 5.8 / 8.7 | 255 → 255 | 457,964 → 478,400 |
| performance | observer | 7.4 / 10.0 → 7.4 / 10.2 | 6.9 / 9.5 → 7.2 / 10.0 | 307 → 308 | 423,684 → 435,020 |
| balanced | overview | 15.2 / 20.4 → 17.9 / 30.1 | 16.6 / 29.1 → 17.2 / 24.9 | 455 → 457 | 653,420 → 679,592 |
| balanced | habitat | 17.5 / 22.4 → 19.4 / 31.1 | 18.4 / 23.6 → 21.2 / 35.0 | 427 → 428 | 1,033,428 → 1,073,126 |
| balanced | body | 16.4 / 22.3 → 16.5 / 19.9 | 16.1 / 24.6 → 17.2 / 26.4 | 264 → 264 | 999,878 → 1,027,440 |
| balanced | observer | 14.8 / 19.3 → 14.4 / 22.4 | 14.1 / 22.6 → 12.6 / 21.0 | 322 → 323 | 874,586 → 886,722 |
| high | overview | 36.0 / 47.6 → 36.1 / 45.9 | 39.9 / 75.0 → 39.3 / 61.8 | 963 → 967 | 1,997,340 → 2,059,484 |
| high | habitat | 38.8 / 48.8 → 40.1 / 52.8 | 41.2 / 59.8 → 44.0 / 73.9 | 880 → 882 | 3,012,252 → 3,104,168 |
| high | body | 40.5 / 50.2 → 43.0 / 52.5 | 40.8 / 70.1 → 40.5 / 56.3 | 557 → 557 | 3,087,756 → 3,152,860 |
| high | observer | 32.9 / 36.4 → 33.0 / 39.8 | 34.3 / 42.9 → 35.1 / 44.0 | 684 → 686 | 2,736,772 → 2,763,584 |

Draw calls rose by 0–4 per camera and triangles by 1–6 % (the added cable conductors, ties and three cables; these figures are from before the last trimming of the strand tessellation, which removed about 0.7 % of the habitat triangles); no overlay, label or marker adds a draw call (the research map and the comparison are 2-D canvases on the technical sheet, the markers are a few DOM elements).
**Reading.** `performance`: both builds are far inside 60 fps (6–10 ms). `balanced`: medians 14–19 ms (52–69 fps) in this session, so the median target holds, narrowly on habitat (19.4 ms); the **95th percentile target (24 ms) is not met** on overview and habitat in either build in this session — and in these two repetitions Stage 4's static p95 on those two cameras is higher than Stage 3's
(30.1 / 31.1 against 20.4 / 22.4 ms), which I cannot rule out as a real cost. `high`: medians 33–43 ms (23–30 fps) in both builds, within ±7 % of each other. A habitat-only run with five interleaved repetitions of the build after the last trimming of the cable tessellation (`habitat_ab_final/`): static median **19.0 (Stage 3) against 18.8 ms**, static p95 27.0 against 23.6 ms, orbit median 19.4 against 20.9 ms (+8 %),
orbit p95 26.2 against 35.0 ms; the spread between repetitions (23.7–39.6 ms for the same build) is larger than most of these differences. **No regression is established in the median; a cost of up to about 8–10 % in the orbit, and a higher 95th percentile, are not excluded.**

**Decomposition of the slow frames of an orbit** (`ecosystem_orbit_decompose.mjs`, balanced, 300 frames per camera; the slow frames are those above the 90th percentile; `orbit_decomposition_balanced.json`). Per-frame series were recorded and compared with the frame time:

| suspected cause | measurement | finding |
|---|---|---|
| LOD switching | LOD levels changed per frame (0–2 in habitat), correlation with frame time | −0.015 (habitat), 0.02 (overview), none in body: **not a cause** |
| culling churn / visibility | objects whose visibility flipped per frame (0–3 habitat, 0–6 overview), draw-call count and its change | flips −0.04 (habitat), 0.12 (overview); calls 0.21, change 0.10: **weak** |
| geometry upload | geometries and textures held by the renderer per frame (textures constant at 9; geometries 324–386 in habitat) | level correlation 0.42 (a position effect), change-between-frames 0.08: **no upload spikes** |
| label updates | orbit with annotation sprites on against off | habitat p95 37.1 → 40.9 ms, overview 36.0 → 31.9, body 39.9 → 28.5: **inconclusive under this noise** |
| shadows | no light casts shadows (`renderer.shadowMap` is not enabled) | **not a cause** |
| post-processing | orbit with the final pass off | p95 37.1 → 37.8 (habitat): not separable |
| reflection (the puddle reflector), structure, bodies | each switched off under the orbit | habitat p95 37.1 → 32.6 (reflection), 31.4 (structure), 33.3 (bodies): the largest, but within the run-to-run spread |
| **shader programs built in flight** | programs held by the renderer per frame, programs built during the orbit | overview orbit built **22 programs mid-orbit** (131 → 153; correlation of the frame time with the change of the count 0.99; the worst frames 419 / 1003 / 545 ms), habitat 2, body 24 |
| CPU or GPU | CPU submit time against frame time | CPU submit median 4.5 ms (p95 11.2) against a frame median of 21.8 ms: the frames are bound by the GPU / compositor |

**Cause and fix.** The first named program built in flight was the puddle reflector's; the rest were the programs of every material for a render target. A program depends on where it renders (into a render target there is no tone mapping and the output is linear), and the startup compile of Stage 3 ran with the *screen* bound while the balanced and high tiers draw into the composer's target:
those programs were therefore built during the first frames that needed them. The reflection, which renders the scene into a target of its own, built its variants the first time a puddle came within range. **Fix** (`EcosystemView.tsx`, `terrain.ts`): the compile runs with the composer's target bound, for the four light states, and the reflection is rendered once at start (`warmReflection`).
(A first attempt, making every LOD level visible for the compile, had no effect and was removed.) **Effect**, 3 interleaved repetitions against the build before the fix (`orbit_fix_ab/`): programs built during an orbit **22 → 0** (the renderer holds a constant 107 programs, 131 before), the worst orbit frame **419–1003 → 58–148 ms** (overview), **251–278 → 70–120 ms** (body), 60–96 → 47–71 ms (habitat).
**The orbit 95th percentile and median did not change measurably** (habitat 38.5 → 40.5 ms, overview 43.6 → 46.9, body 35.1 → 38.2 ms, all within the spread of the repetitions). The target of 24 ms for the habitat orbit was **not reached**; the steady-state cost of the frame, which these measurements could not decompose further under load, is what sets the 95th percentile.
The one-off cost moved to the load of the page (more programs are compiled at start).

## 13. Regression (this commit, nothing carried over)

| check | result |
|---|---|
| backend full regression (`pytest`, 692 tests) | **690 passed, 2 failed**: exactly the two known failures of the baseline (`test_compat::test_engine_conformance_against_the_golden_fixture[desktop-scipy]`, `test_lab::test_published_records_replay`); compared test by test with the Stage 3 JUnit file: no test missing, 40 new, no new failure (`docs/ecosystem/evidence/meos_stage4.junit.xml`, log `meos_stage4_pytest.log`, 19 min 11 s) |
| frontend full tests | **210 / 210** passed (21 files; 123 ecosystem tests, 35 new in this stage: `research.test.ts` 19, `researchMap.test.ts` 10, six body tests for SSS, the M2 tap and the path cables) (`docs/ecosystem/evidence/frontend_stage4.junit.xml`) |
| typecheck `tsc -b` | clean |
| `eslint src` | clean |
| `ruff check xzr tests bench scripts` | clean (new files added to the existing E501 exemptions of the MEOS files) |
| `mypy xzr` | 0 errors in `xzr/meos` (the 89 older errors elsewhere are untouched) |
| frontend build | passes |
| saved 264-run replay (11 studies, this backend's code) | **264 / 264 agree** (545 s; `docs/ecosystem/evidence/replay_meos_stage4.json`) |
| MEOS deterministic replay | baseline result digest `b4cf1e52…adc5` unchanged and replays identically (asserted in `test_meos_stage2.py`, `test_meos_stage4_engine.py`, `test_meos_stage4_observation.py`); the stored fixtures of engine `meos-0.2` (result digest `a0dfe40f…`) and `meos-0.1` (`ea539682…`) replay identically under `meos-0.3` (checked directly, including the trace digest); every Stage 4 intervention mode replays bit for bit (`test_the_new_modes_replay_bit_for_bit`, `test_every_address_intervention_is_recorded_with_old_and_new_state`) |
| state-mapping tests | pass (`bodies.test.ts`, 39: the Stage 3 rows and the new SSS, M2 and path-cable rows) |
| observation separation | pass (`test_meos_stage4_observation.py`: each limit has its own status, the run is unchanged, the observation never enters the digest) |
| boundary / Address Domain / SSS / M2 | pass (`test_meos_stage4_readings.py`, `test_meos_stage4_engine.py`, `research.test.ts`, `researchMap.test.ts`, `bodies.test.ts`) |
| replay event markers | pass (`research.test.ts`: markers of every kind, inspection, snapshot deltas) |
| technical view | pass (`technical.test.ts` unchanged and passing; `researchMap.test.ts`) |
| quality-tier switching | pass (`ecosystem_tiers_check.mjs`: each tier loads with its pipeline, the bodies keep the same detail, switching rebuilds the pipeline, no page errors) |
| screenshot capture | 13 new shots captured without page errors (`docs/ecosystem/visual/30-…42-*.png`, camera record `cameras-balanced-stage4.json`), the Stage 3 29 shots and their camera record untouched |
| experiments A–E | run to the end with 0 refused runs; saved (`docs/ecosystem/experiments_stage4.json`) |
| known failures | the same two as before; none new |

## 14. Failures and corrections during this stage

* **Two known failures** (unchanged since the baseline): `test_compat::test_engine_conformance_against_the_golden_fixture[desktop-scipy]` (a golden fixture made with another scipy) and `test_lab::test_published_records_replay`.
* **A wrong hypothesis about programs built in flight.** The decomposition of the orbit (section 12) found programs being built mid-orbit; the first fix (making every LOD level visible for the startup compile) changed nothing (the count stayed 131 → 153) and was removed. The cause was different (section 12) and was fixed and measured.
* **An unsound measure, corrected.** The first versions of experiments B and C decided "the run changed" by comparing result digests; the result digest covers the intervention log, so it differs for any intervention, which made every fault look like a change. The measure is now a digest of the dynamics (the frames without the fault bookkeeping), and experiments B and C were re-run. The correction turned "collision" and "stale" into strict null results.
* **Two of the new body tests failed at first** (a retracted probe's rod is drawn *up*, not down; one cable carries no operational path) and were corrected in the tests, not in the bodies.
* **A timeout in an unrelated test** (`lab/hifi/assemblies.test.ts`, 5 s default) in one full run made while other work was running on the machine; it passes in the final run.
* **Not reached:** the habitat orbit 95th percentile of 24 ms (section 12), and a rise of the cable-region contour complexity at the camera of capture 14 (section 11).

## 15. Null results (kept, not removed)

Saved in full in `experiments_stage4.json` (`null_results` of each experiment: A 9, B 5, C 16, D 1, E 23). Among them:
* A: no value of `address_resolution` made the observer disagree on a run without an Address Domain fault; on the collapsing scenario no observation limit changed the observer's (correct) conclusion.
* B: the observation boundary changed nothing in the run; a 10-tick loss of history access changed the dynamics but collapsed nothing.
* C: **collision** and **stale** left the dynamics bit for bit unchanged in every seed, target and duration (the two configurations already share a cell at tick 100; a configuration that does not move cannot go stale); fragmentation of A2 and a delayed update of A2 changed the dynamics and collapsed nothing.
* D: no lower scale down to 0.5 leaves the ACTIVE region.
* E: delayed M2 sensing changes nothing in the unperturbed run, the interrupted runs and the Address Domain perturbation; a threshold of 0.2 is bit for bit the run without M2 sensing in every scenario; direct sensing changes nothing in the interrupted run without a pulse.

## 16. Limitations

**Unimplemented.**
* Live stepping in the browser (the view plays a deterministic server record; the console re-runs the engine on the server).
* Connections to the other systems (XenoBody runtime, Ziran / Xeno simulators, Xenoscience, the language-model Philosophical AI); the M2 → A1 path and the first-stage Philosophical operations are inside MEOS-0 only.
* A GPU timer for the frame cost (the `EXT_disjoint_timer_query_webgl2` extension is not exposed in this headless browser: GPU time is reported as null); the cost of a frame is the wall time with a GPU sync.
* A per-component overlay of the delta in the 3-D scene: the delta is drawn on the technical sheet (component table, path and boundary changes) and listed in the research pane, not as an outline on the stage.
* Observation-sensitivity robust to interval 2 (no ACTIVE grid point of experiment D is robust: the region ACTIVE-and-robust is empty on the grid).

**Partial.**
* Cable contour complexity: the measured gain in the close cable shot is small (section 11) and absent in capture 14's cable crop; the reference value (1.59) is far.
* Replay markers are derived on the client from the record (interventions, status log, address events, the observation timeline); there is no server-side event index.
* The SSS region of the setting in force is classified by the engine with two seeds and the default configuration of the other parameters; it is cached per (scale, size, speed) and does not account for other interventions of the run.
* Stale addresses: a configuration that does not move cannot go stale; the fault matters only for a configuration that moves (in this model: A2 walks toward A1; A1 acts in place).
* The three observation limits added in this stage (threshold, occluder, address resolution) are opt-in features of the observer; the observer of the earlier stages does not use them.

**Unverified.**
* Performance on a quiet machine: the host was loaded during the measurements of this stage (section 12); only same-session interleaved comparisons are reported as comparisons, and the Stage 3 figures of quieter conditions are not compared with this session's.
* The mapping of SSS and M2 to body poses has been tested for what moves and with which parameter; nobody has judged whether the poses are readable to a person.
* Every experimental outcome is a property of this formal model with these seeds (five for A, B, C, E; two for D) and scenarios; none is tested against any physical or biological system.

## 17. Remaining work

* A quiet-machine measurement of all three tiers and of the orbit (a GPU timer would separate GPU time from submission), and a decomposition of the steady-state orbit cost (reflection, structure, bodies are the largest switchable parts in the noisy ablation of `perf_stage4/`).
* The delta of a comparison drawn on the 3-D stage, not only on the technical sheet.
* Live stepping, and the connections to the other systems.
* A user study of whether the poses of SSS and M2 on the bodies are readable.
* A cable design that raises the contour complexity at the distance of the comparison camera (more free-standing thin conductors in the air rather than along the ground), and observer-side geometry beyond state-linked poses (none was added in this stage: its cable crops did not change measurably).
* More seeds for experiment D (two), and a larger grid near the narrow ACTIVE island.
