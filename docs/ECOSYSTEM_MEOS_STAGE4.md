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

**Readings (`stage4.py`).** Operational paths (`path_activity`), boundary perturbation, Address Domain effects, per-run log, SSS region of a point. **Experiments (`stage4_experiments.py`, `scripts/meos_experiments_v4.py`).**

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

@@EXPERIMENTS@@

## 11. Visual mapping

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

@@PERFORMANCE@@

@@REGRESSION@@

@@FAILURES@@

@@LIMITATIONS@@
