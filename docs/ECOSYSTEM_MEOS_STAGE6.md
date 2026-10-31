# XENO ECOSYSTEM — Stage 6 (MEOS-0.4, follow-up on MEOS-0.5): endogenous repair, world-state intervention, reachable recovery

> Which damage can internal reconfiguration handle, which needs an intervention on the state of the world, and which cannot be recovered in the action space tested here: by which action, how much of it, at which tick, at which cost, on which seeds, and to which horizon.

Everything below is a statement about a **formal model** (MEOS-0, engine `meos-0.4`, unchanged by this stage): how this engine's specified operation responds to the interventions tested. It is not evidence about any real ecosystem. A repair that works here is *conditional* on the model,
the action space, the tick grid, the horizons and the seeds. Raw data and interpretation are kept apart: the tables are copied from `docs/ecosystem/experiments_stage6*.json` by `backend/scripts/make_stage6_doc.py`; the words under them are interpretation and its limits.

## 1. Scope

Stage 5 searched **component enable/disable** (route reconfiguration) and found an action for one stress of six (history lost: the M2 tap). Stage 6 asks the question that left open: for the stresses internal reconfiguration cannot handle, **does an intervention on the world itself** (coupling, resource, renewal, Address)
recover a sustainable operation, and under what conditions? Recovery is not a flash of ACTIVE (section 6). Not changed: the baseline result digest, the 264 saved runs, every Stage 5 result.

**What the words mean here.** *Endogenous* repair is the internal route reconfiguration of Stage 5 (class A: a component switched on or off, decided by the configuration's own controller from its own traces). The world-state actions of Stage 6 (class B: a parameter restored, a resource inserted, an Address restored) are **interventions on the world from outside the configuration**, chosen by a scripted rule or by the experimenter; this stage does not show a system repairing itself by acting on its world, and the controllers are fixed decision rules, not learning agents. A repair is a recovery of the *modelled* operation under the criterion of section 6; the model is synthetic and no real system is claimed. Observation repair (class C) changes only what is observed.

## 2. Repository state

- Worktree `/Users/user/Desktop/BIM/xeno-ziran-runtime-meos`, branch `feat/meos-ecosystem`, from the zrs baseline `ec9667e`. **Local only: not pushed, not merged, not deployed.**
- Stage 5 final commit: `1d1e331`. Stage 6 commits follow it on the same branch (the repair action space, the three pipelines, the corrected criterion, the controllers, the interface, the evidence, the verification and release, and the follow-up that measured the open windows to tick 1140 and built the three missing actions); the final commit's id is in the final report and in the manifest of the snapshot archive.
- The baseline result digest, the trace digest and the 264 stored runs are unchanged; every Stage 5 result file is unchanged (the Stage 5 experiments were re-run on `meos-0.5` for the regression and agree with them).

## 3. Stage 5 inheritance

Stage 5 (experiment L) found that for `history lost` exactly one action of 512 persists, the M2 tap at tick 113, and none for the other five stresses. Stage 6 repeats that stress on the **same engine, onset, action tick and M2 specification**, and differs in two evaluation conditions only: the horizon (Stage 5: 300; Stage 6: three horizons up to 480) and the criterion
(Stage 5: ACTIVE at the end; Stage 6: ACTIVE on the last 30 ticks, no secondary collapse, resource not exhausted). The result is the same under both:

| seed set | Stage 5 criterion: ACTIVE at tick 300 | ACTIVE at the end of 480 | Stage 6 short | Stage 6 medium | Stage 6 long |
|---|---|---|---|---|---|
| exploration 1-5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| validation 6-10 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| evaluation 11-30 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 |

There is no model change and no disagreement to explain: a Stage 5 result stands under the stricter Stage 6 criterion. The Stage 5 result files are not modified.

## 4. Repair action space

Three kinds of recovery action are kept apart in the code, the experiments and this document and are never counted as one: **A** internal reconfiguration (a component switched on or off, a route switched: Stage 5), **B** world-state repair (new), **C** observation repair (a change of how the run is observed; it changes the observed state, never the run).
Every action is built from operations MEOS-0 already has (`RECONFIGURE`, `ALTER_RESOURCE`, `RECONNECT`, `ADDRESS`, `ROUTE`), so no run without a repair changes. Implemented and proxy actions:

| action | class | family | status | magnitudes | durations | latency | side effect | reversibility | declared cost |
|---|---|---|---|---|---|---|---|---|---|
| internal.m2_tap | A | internal | implemented | - | - | 1 tick | A1 also senses M2 | reversible (ROUTE m2 none) | switching: 1 operation |
| coupling.restore | B | coupling | implemented | 0.6, 0.7, 0.8, 0.9, 1.0 | - | 1 tick | none expected: the parameter returns to a value it had | reversible | switching: 1 RECONFIGURE; persistence: none after the change |
| coupling.gradual | B | coupling | implemented | 1.0 | 10, 20, 40 | duration/2 ticks to complete | intermediate gains pass through the dynamics | reversible | switching: duration/5 RECONFIGURE |
| coupling.bridge | B | coupling | implemented | 1.25, 1.5, 2.0 | 10, 20, 40 | 1 tick | the damage remains after the bridge | reversible by construction | switching: 2 RECONFIGURE; persistence: none after the bridge |
| resource.pulse | B | resource | implemented | 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0 | - | 1 tick | oversupply is a failure mode (stage 3: 2.0 recovers, 4.0 re-collapses) | not reversible (material added) | resource: the amount; switching: 1 ALTER_RESOURCE |
| resource.inflow | B | resource | implemented | 0.02, 0.03, 0.04 | 20, 60, 120 | 1 tick | a higher regrow rate is a different regime | reversible (returns to the stressed values) | resource: extra regrow over the duration; persistence: while it lasts |
| resource.redistribute | B | resource | proxy | 0.06, 0.12, 0.24 | 10, 30 | 1 tick | flattens the gradient the configurations use | reversible | switching: 2 RECONFIGURE |
| resource.reserve | B | resource | proxy | 24.0, 48.0, 96.0 | - | 1 tick | energy, not resource, is added | not reversible | energy: the reserve added |
| renewal.restore | B | renewal | implemented | 0.7, 0.8, 0.9, 1.0 | - | 1 tick | - | reversible | switching: 1 RECONFIGURE |
| renewal.restart | B | renewal | implemented | - | - | 1 tick | the feedback component returns | reversible (REMOVE feedback) | switching: 1 RECONNECT |
| renewal.auxiliary | B | renewal | implemented | 0.75, 1.0, 1.5, 2.0 | - | 1 tick | A2 transfers more per action | reversible | switching: 1 RECONFIGURE; resource: more transferred per step |
| renewal.pulse | B | renewal | implemented | 1.25, 1.5, 2.0 | 10, 20, 40 | 1 tick | the damage remains afterwards | reversible by construction | switching: 2 RECONFIGURE |
| address.restore | B | address | implemented | - | - | 1 tick | - | reversible | switching: 1 ADDRESS |
| address.reassign | B | address | implemented | - | - | 1 tick | A2 is moved to (5, 6) with its state kept | reversible | switching: 1 ADDRESS |
| observation.sampling | C | observation | implemented | - | - | - | - | - | - |
| observation.region | C | observation | implemented | - | - | - | - | - | - |
| observation.resolution | C | observation | implemented | - | - | - | - | - | - |
| observation.address | C | observation | implemented | - | - | - | - | - | - |

Class C actions (sampling interval 1, whole arena, stride 1, Address resolution 1.0) are applied to the *observation of a recorded run* (section 20), not to a run. Actions that were **not** implemented, and actions that are only a proxy; none of them was run or simulated by something else:

- `coupling.bypass` (not implemented; built afterwards, section 30): the coupling of MEOS-0 is one scalar share of A1's alteration reaching A2; there is no spatial coupling path to bypass, so no action is built
- `resource.redistribute` (proxy): MEOS-0 has no operation that moves resource from one cell to another; diffusion is the nearest mechanism and is a proxy for redistribution
- `resource.reserve` (proxy): the power reserve is energy for A2's renewal, not the resource field: a proxy for a local reserve release
- `resource.rerouting` (not implemented; built afterwards, section 30): MEOS-0 has no transport network for the resource; no action is built
- `address.temporary_local` (not implemented; built afterwards, section 30): no engine mode gives a bounded-duration local address (the ``stale`` and ``delayed`` modes are faults, not repairs)

## 5. Cost model

Each repair run records, over the window from the action to the long horizon, **raw costs** measured from the traces: energy use (the sum of the power drawn), resource mass present, switching (the number of interventions), persistence energy rate (the energy drawn per tick once the run is sustained), and collateral disturbance (the mean normalised deviation of the interaction strength, the resource total, the power reserve and the resource flow
from the undamaged run of the same seed). **Normalised costs** divide energy use, resource mass and the persistence rate by the undamaged run's. **No weighted total is used in any result**: where one number is needed to order repairs (the *reference repair* of a stress, the cost-aware controller) it is the mean of switching, collateral and persistence rate, each divided by its maximum over the settings compared
(equal weights: a stated convention, not a finding) and the raw values are printed beside it. A recovery is *costly* if its persistence energy rate exceeds 1.5 times the undamaged run's or its collateral disturbance exceeds 1.0 (fixed before the runs).
The repair cost model is synthetic: it is a measurement of this model's traces, not a cost in any real system.

## 6. Pipeline A: protocol, seeds, criterion

- **Exploration seeds 1-5**: every applicable action x magnitude x duration x action tick (2478 settings, 12390 runs); a setting effective on all five is a *candidate*. **Validation seeds 6-10**: every candidate is run again; it is *validated* only if effective on all five. **Evaluation seeds 11-30**: validated settings and near misses are evaluated and reported, never used to choose. The three seed sets are never mixed.
- **Near miss**: effective on 3 or 4 of 5 exploration seeds, or on all exploration seeds and 3 or 4 of 5 validation seeds. A near miss is kept, makes a stress INCONCLUSIVE if nothing is validated, and is **never** counted as validated.
- **Recovery** is not a flash of ACTIVE. A run recovers at a horizon if it is ACTIVE on every tick of the last 30 ticks before it, has no collapse after a sustained ACTIVE stretch of at least 30 ticks that followed the action (*no secondary collapse*), and its resource field is not exhausted (>= 25 % of the undamaged run's). Outcomes: `prevented` (no collapse after the action), `recovered` (collapse, then sustained recovery), `secondary collapse`, `failed`.
- **Horizons**: short 180, medium 300, long 480. A horizon is *applicable* to an action at tick t only if it leaves at least 2 x 30 ticks after it (time to recover and to show a sustained stretch): short up to tick 120, medium and long always. A setting is *effective* if it succeeds at every applicable horizon.
- **A correction made after reading results, and its effect.** The first version required all three horizons at every tick. A repair after tick 120 cannot satisfy the short horizon by construction, which made every late repair look like a failure and the collapse look irreversible. Inspection of the one-tick results showed this (late repairs recovered on every seed at the medium and long horizons). The criterion was corrected as above; **the results of the first criterion are kept**
  (`experiments_stage6*_all_horizons_criterion.json`) and compared here:

| stress | original criterion (all three horizons at every tick): effective ticks | latest / earliest irreversible | corrected criterion (applicable horizons): effective ticks | latest / earliest irreversible |
|---|---|---|---|---|
| coupling weakened (gain 0.5) | 101-105, 108-117, 124-140 | 140 / 141 | 101-105, 108-117, 124-388 | 388 / 389 (CLOSED) |
| resource reduced (regrow 0.01, charge 0.2) | 101-109 | 109 / 110 | 101-109 | 109 / 110 (CLOSED) |
| renewal efficiency 0.6 | 101-111 | 111 / 112 | 101-111 | 111 / 112 (CLOSED) |
| renewal stopped (feedback removed) | 101-106, 121, 130-140 | 140 / 141 | 101-106, 121, 130-383 | 383 / 384 (CLOSED) |
| Address degraded (A2 partial 50 %) | 101-109, 131-133, 135, 140 | 140 / 141 | 101-109, 131-133, 135, 140-383 | 383 / 384 (CLOSED) |
| history lost | 101-120 | 120 / 121 | 101-120 | 120 / 121 (CLOSED) |

Counts: 27 single candidates, 26 validated, 3 near misses; 270 combined settings (pairs of different actions at ticks [113, 120, 130]), 21 candidates, 14 validated, 6 of them synergistic (neither part effective alone at that tick), 9 near misses.
The unrepaired runs: Address degraded (A2 partial 50 %): {'failed': 5}, coupling weakened (gain 0.5): {'failed': 5}, history lost: {'failed': 5}, renewal efficiency 0.6: {'failed': 5}, renewal stopped (feedback removed): {'failed': 5}, resource reduced (regrow 0.01, charge 0.2): {'failed': 5} (all on exploration seeds; no seed recovers without a repair).

## 7. Stress-by-stress repairability

The stresses arrive at tick 100; the decision tick (the first decision of the stage 5 controllers) is 113. Classes: *internally reconfigurable*, *externally repairable* (world-state, single or combined), *both*, *neither (under the tested actions)*, *inconclusive*. "At the decision tick" asks whether a setting is effective **at tick 113**; "at any tested tick" asks whether one is effective at some tested tick (101-170 at one-tick resolution for every setting, to 330 for the windows still open at 170, and to 1140 with the extended horizon 1200 for the three still open at 330).
A *combined* recovery counts only at ticks where neither part is effective alone. Windows are in action ticks.

| stress | internal reconfiguration: effective ticks | world-state repair (single): effective ticks | combined repair: effective ticks | minimum effective action | all effective ticks | last tick a measured setting recovers | first tick after it (`irreversible_tick`; measured settings only) | reference repair, exploration seeds ok at short / medium / long | cost of the reference repair (equal-weight normalised) and its setting | unrepaired collapse tick | classification: at the decision tick 113 / at any tested tick |
|---|---|---|---|---|---|---|---|---|---|---|---|
| coupling weakened (gain 0.5) | none | 101-105, 108-117, 124-388 | none | coupling.gradual 1.0; coupling.restore 0.7; resource.pulse 0.5 | 101-105, 108-117, 124-388 | 388 | 389 | 5/5, 5/5, 5/5 | 0.5486 (coupling.restore 1.0 @104) | 149 | **externally repairable** / **externally repairable** |
| resource reduced (regrow 0.01, charge 0.2) | 101-109 | none | none | internal.m2_tap 0.0 | 101-109 | 109 | 110 | 5/5, 5/5, 5/5 | 0.9895 (internal.m2_tap @104) | 149 | **neither (under the tested actions)** / **internally reconfigurable** |
| renewal efficiency 0.6 | 101-111 | 101-104 | none | internal.m2_tap 0.0; renewal.restore 1.0 | 101-111 | 111 | 112 | 5/5, 5/5, 5/5 | 0.6668 (renewal.restore 1.0 @104) | 149 | **neither (under the tested actions)** / **both** |
| renewal stopped (feedback removed) | none | none | 101-106, 121, 130-383 | - | 101-106, 121, 130-383 | 383 | 384 | combined: see section 14 | 0.7246 (renewal.restart + resource.pulse 0.5 @130) | 144 | **neither (under the tested actions)** / **externally repairable** |
| Address degraded (A2 partial 50 %) | none | none | 101-109, 131-133, 135, 140-383 | - | 101-109, 131-133, 135, 140-383 | 383 | 384 | - | - | 149 | **inconclusive** / **externally repairable** |
| history lost | 101-113 | none | 114-120 | internal.m2_tap 0.0 | 101-120 | 120 | 121 | 5/5, 5/5, 5/5 | 0.4981 (internal.m2_tap @104) | 159 | **internally reconfigurable** / **both** |

| stress | flags | failure ids over the tested grid (cells not effective) |
|---|---|---|
| coupling weakened (gain 0.5) | recoverable only within a timing window | NO_EFFECTIVE_ACTION 306, ACTION_TOO_LATE 112, SECONDARY_COLLAPSE 12, OVERSHOOT 7 |
| resource reduced (regrow 0.01, charge 0.2) | recoverable only within a timing window | NO_EFFECTIVE_ACTION 280, ACTION_TOO_LATE 97, SECONDARY_COLLAPSE 12, OVERSHOOT 1 |
| renewal efficiency 0.6 | recoverable only within a timing window | NO_EFFECTIVE_ACTION 305, ACTION_TOO_LATE 106, OVERSHOOT 9, SEED_DEPENDENT 1 |
| renewal stopped (feedback removed) | recoverable only within a timing window; recovered only by a combination (neither part alone) | NO_EFFECTIVE_ACTION 300, ACTION_TOO_LATE 100 |
| Address degraded (A2 partial 50 %) | recoverable only within a timing window; near miss at the decision tick (validation 3-4 of 5), nothing effective there; recovered only by a combination (neither part alone) | NO_EFFECTIVE_ACTION 278, ACTION_TOO_LATE 102, OVERSHOOT 16, SECONDARY_COLLAPSE 10, SEED_DEPENDENT 2 |
| history lost | recoverable only within a timing window | NO_EFFECTIVE_ACTION 202, ACTION_TOO_LATE 98, OVERSHOOT 46, SECONDARY_COLLAPSE 43 |

*Reference repair*: the validated setting with the lowest equal-weight normalised cost; its horizons are those of its exploration cell. Every validated setting is effective at all applicable horizons by definition, so a setting that recovers at the short horizon and not at the long one is never in this table: it is listed as *only transiently recoverable* (flags) or in the failure ids.
Interpretation: repairability is not a property of a stress but of a stress, an action, a magnitude, a tick and a horizon. For every stress the settings whose window was measured at one-tick resolution (section 8) stop recovering the run: `irreversible_tick` is the tick after the last tick at which any of them is effective, at tick 389 (coupling weakened (gain 0.5)), 110 (resource reduced (regrow 0.01, charge 0.2)), 112 (renewal efficiency 0.6), 384 (renewal stopped (feedback removed)), 384 (Address degraded (A2 partial 50 %)), 121 (history lost). This is a statement about **those settings in the tick range that was measured** (`irreversibility_scope` in the data: the number of settings and the range per stress are in section 8), not about every repair that could be devised; it is not the first failing tick (the windows are fragmented: a failure is often followed by effective ticks again) and not a universal irreversibility. For the coupling, the renewal-stopped and the Address stresses a pulse-based repair stays effective long after the unrepaired collapse (to tick 388, 383, 383); these windows were still effective at the end of the first tested range (tick 330), and were measured on to tick 1140 with the extended horizon before a closure was claimed (section 29). The classification "neither" at tick 113 and "internally reconfigurable / externally repairable / both" at another tick are both true and both are reported.

## 8. Timing windows

For every setting Pipeline A found effective or nearly, every action tick from 101 to 170 was run on seeds 1-10 (exploration and validation reported separately; a tick is *effective* only if both are all effective). The unrepaired run collapses at about tick 144-159 (section 7). A window that is still effective at the last tick tested (170, 330 after the first extension, 1140 after the second) **has not closed**: its end is the end of the range, and no latest successful or irreversible tick is claimed for it. Three windows were still effective at 330; they were measured on with the longest horizon the engine accepts (1200) and all three closed (below).

| stress | setting | effective ticks (exploration and validation seeds all effective) | earliest | latest | near-miss ticks (3-4 of 5) |
|---|---|---|---|---|---|
| coupling weakened (gain 0.5) | internal.m2_tap | none | - | - | - |
| coupling weakened (gain 0.5) | resource.pulse 1.0 | 108-117, 125-330 | 108 | 330 | 107, 118, 119, 120, 121 |
| resource reduced (regrow 0.01, charge 0.2) | internal.m2_tap | 101-109 | 101 | 109 | - |
| resource reduced (regrow 0.01, charge 0.2) | resource.pulse 1.0 | none | - | - | - |
| renewal efficiency 0.6 | internal.m2_tap | 101-111 | 101 | 111 | - |
| renewal efficiency 0.6 | resource.pulse 1.0 | none | - | - | - |
| renewal stopped (feedback removed) | internal.m2_tap | none | - | - | - |
| renewal stopped (feedback removed) | resource.pulse 1.0 | none | - | - | - |
| Address degraded (A2 partial 50 %) | internal.m2_tap | none | - | - | - |
| Address degraded (A2 partial 50 %) | resource.pulse 1.0 | none | - | - | - |
| history lost | internal.m2_tap | 101-113 | 101 | 113 | 114, 115, 116, 117, 118 |
| history lost | resource.pulse 1.0 | none | - | - | - |
| coupling weakened (gain 0.5) | coupling.gradual 1.0 (for 10) | 101-104 | 101 | 104 | - |
| coupling weakened (gain 0.5) | coupling.restore 0.7 | 102-104 | 102 | 104 | 101 |
| coupling weakened (gain 0.5) | resource.pulse 0.5 | 114-117, 124-146 | 114 | 146 | 113, 118, 119, 120, 121, 147, 149 |
| renewal efficiency 0.6 | renewal.restore 1.0 | 101-104 | 101 | 104 | - |
| Address degraded (A2 partial 50 %) | address.reassign + resource.pulse 0.5 | 101-104 | 101 | 104 | 105, 106, 107, 108, 109, 110, 111, 112, 113, 114 … |
| Address degraded (A2 partial 50 %) | address.reassign + resource.pulse 1.0 | 101-109 | 101 | 109 | 110, 111, 112, 113, 114, 115, 116 |
| Address degraded (A2 partial 50 %) | address.reassign + resource.pulse 2.0 | 105-109 | 105 | 109 | 101, 102, 103, 104, 110, 111, 112, 113, 114, 115 … |
| Address degraded (A2 partial 50 %) | address.restore + resource.pulse 0.5 | 101-104, 131-133, 135, 140-142 | 101 | 142 | 105, 106, 107, 108, 109, 110, 111, 112, 113, 114 … |
| Address degraded (A2 partial 50 %) | address.restore + resource.pulse 1.0 | 101-109, 131-133, 135, 140-330 | 101 | 330 | 110, 111, 112, 113, 114, 115, 116, 121, 122, 123 … |
| Address degraded (A2 partial 50 %) | address.restore + resource.pulse 2.0 | 106-109 | 106 | 109 | 103, 104, 105, 110, 111, 112, 113, 114, 115, 116 |
| history lost | internal.m2_tap + renewal.auxiliary 1.0 | 101-113 | 101 | 113 | 114, 115, 116, 117, 118 |
| history lost | internal.m2_tap + renewal.auxiliary 2.0 | 101-113 | 101 | 113 | 114, 115, 116, 117, 118 |
| history lost | internal.m2_tap + renewal.pulse 1.5 (for 20) | 101-113 | 101 | 113 | 114, 115, 116, 117, 118 |
| history lost | internal.m2_tap + resource.inflow 0.02 (for 120) | 101-113 | 101 | 113 | 114, 115, 116, 117, 118 |
| history lost | internal.m2_tap + resource.pulse 0.5 | 101-120 | 101 | 120 | 121, 122, 123, 124, 125, 134 |
| history lost | internal.m2_tap + resource.pulse 1.0 | 101-120 | 101 | 120 | 121, 122, 123, 124, 125 |
| history lost | internal.m2_tap + resource.pulse 2.0 | 106-120 | 106 | 120 | 103, 104, 105, 121, 122, 123, 124, 125 |
| history lost | internal.m2_tap + resource.reserve 48.0 | 101-113 | 101 | 113 | 114, 115, 116, 117, 118 |
| renewal stopped (feedback removed) | renewal.restart + resource.pulse 0.5 | 101-106, 120-121, 130-142 | 101 | 142 | 107, 122, 123, 124, 125, 126, 127, 128, 129, 143 … |
| renewal stopped (feedback removed) | renewal.restart + resource.pulse 1.0 | 101-106, 121, 130-330 | 101 | 330 | 107, 122, 123, 124, 125, 126, 127, 128, 129 |
| coupling weakened (gain 0.5) | coupling.restore 1.0 | 101-105 | 101 | 105 | - |
| renewal stopped (feedback removed) | renewal.restart | none | - | - | - |
| Address degraded (A2 partial 50 %) | address.restore | none | - | - | - |
| Address degraded (A2 partial 50 %) | address.reassign | none | - | - | - |

**Last tick a measured setting recovers** (`latest_successful_repair_tick`) = the last tick at which some setting whose window was measured is effective. **The tick after it** (`irreversible_tick`, when the window is closed) = the first tick from which none of those settings is effective at any later measured tick. Two different things are meant by a closure and are kept apart: **(A)** the last effective tick of one setting (the per-setting table of section 29), and **(B)** the union over the settings that were measured for a stress (this table). B is the only one that is a statement about more than one action, and even B covers only the settings that were window-measured: settings that were never effective on the coarse grid have no one-tick window, the follow-up actions (engine meos-0.5) are covered only where section 30 lists a window, and no action that restores A1's energy exists. The tick ranges are 101-170 for the stresses whose windows all closed early, 101-330 or 101-1140 (extended horizon 1200) where a window was still effective at the end of the previous range, and 200 on the coarse grid. A window may end and another open later: the effective ticks are often **fragmented** (for example the coupling pulse of 1.0: effective at 108-117 and again from 125; the first failing tick is not the closure), a gap is recorded and not smoothed, and the closure is placed after the **last** effective tick. Fragmentation is not explained here (the gaps inside a window are several ticks long, longer than the operating cycle of 5 ticks; no mechanism is claimed).

Reachable recovery by tick (tested action space, one-tick resolution):

- **coupling weakened (gain 0.5)** (unrepaired collapse at 149): 101-105 world-state; 106-107 none; 108-117 world-state; 118-123 none; 124-388 world-state; 389-420 none
- **resource reduced (regrow 0.01, charge 0.2)** (unrepaired collapse at 149): 101-109 internal; 110-420 none
- **renewal efficiency 0.6** (unrepaired collapse at 149): 101-111 internal; 112-420 none
- **renewal stopped (feedback removed)** (unrepaired collapse at 144): 101-106 combined; 107-120 none; 121-121 combined; 122-129 none; 130-383 combined; 384-420 none
- **Address degraded (A2 partial 50 %)** (unrepaired collapse at 149): 101-109 combined; 110-130 none; 131-133 combined; 134-134 none; 135-135 combined; 136-139 none; 140-383 combined; 384-420 none
- **history lost** (unrepaired collapse at 159): 101-113 internal; 114-120 combined; 121-420 none

**Delayed but recoverable** (effective at or after the unrepaired collapse):

- coupling weakened (gain 0.5): effective ticks at or after the unrepaired collapse (149): 124-388
- resource reduced (regrow 0.01, charge 0.2): no tested setting is effective at any tick from the unrepaired collapse (149) to None
- renewal efficiency 0.6: no tested setting is effective at any tick from the unrepaired collapse (149) to None
- renewal stopped (feedback removed): effective ticks at or after the unrepaired collapse (144): 130-383
- Address degraded (A2 partial 50 %): effective ticks at or after the unrepaired collapse (149): 140-383
- history lost: no tested setting is effective at any tick from the unrepaired collapse (159) to None

## 9. Minimum effective interventions

Pipeline A's coarse minimum, and Pipeline B's one-tick and fine-magnitude sweeps (a magnitude is effective at a tick only if all ten exploration and validation seeds are effective; no threshold rests on one seed):

| stress | action | minimum effective magnitude (coarse grid, validated) | effective ticks |
|---|---|---|---|
| coupling weakened (gain 0.5) | coupling.gradual | 1.0 | 104 |
| coupling weakened (gain 0.5) | coupling.restore | 0.7 | 104 |
| coupling weakened (gain 0.5) | resource.pulse | 0.5 | 108, 113, 130, 140, 160, 200 |
| history lost | internal.m2_tap | 0.0 | 104, 108, 113 |
| renewal efficiency 0.6 | internal.m2_tap | 0.0 | 104, 108 |
| renewal efficiency 0.6 | renewal.restore | 1.0 | 104 |
| resource reduced (regrow 0.01, charge 0.2) | internal.m2_tap | 0.0 | 104, 108 |

| intervention | stress | minimum effective magnitude (any tick) | minimum by action tick | ticks with an effective magnitude |
|---|---|---|---|---|
| coupling restore (gain) | coupling weakened (gain 0.5) | 0.65 | @101: 0.75; @102: 0.7; @103: 0.7; @104: 0.65; @105: 0.9 | 101, 102, 103, 104, 105 |
| renewal restore (efficiency) | renewal efficiency 0.6 | 0.95 | @101: 0.95; @102: 0.95; @103: 0.95; @104: 0.95 | 101, 102, 103, 104 |
| resource pulse on the coupling stress | coupling weakened (gain 0.5) | 0.45 | @110: 0.55; @115: 0.5; @125: 0.5; @130: 0.45; @135: 0.5; @140: 0.5; @145: 0.5 | 110, 115, 125, 130, 135, 140, 145 |
| Address restore + pulse | Address degraded (A2 partial 50 %) | 0.5 | @105: 1.0; @135: 0.5; @140: 0.5; @145: 0.75 | 105, 135, 140, 145 |
| renewal restart + pulse | renewal stopped (feedback removed) | 0.5 | @105: 0.5; @120: 0.5; @130: 0.5; @135: 0.5; @140: 0.5; @145: 0.75; @150: 0.75 | 105, 120, 130, 135, 140, 145, 150 |

The minimum depends on the tick: it is not a constant of the repair. The restoration of the Address alone and the restart of the renewal alone have **no effective tick** at all (section 8), whatever their magnitude.

## 10. Coupling (Experiment M)

Stress: coupling gain 0.5 from tick 100. All coupling settings, then the other families on the same stress:

| action tried | settings tried (magnitude x duration x tick) | effective on all 5 exploration seeds | validation (seeds 6-10) | best any setting did on the exploration seeds | main failure ids of the others |
|---|---|---|---|---|---|
| coupling.bridge | 72 | 0 | none validated | 0/5 (magnitude 1.25, duration 10, tick 104) | NO_EFFECTIVE_ACTION 42, ACTION_TOO_LATE 18, SECONDARY_COLLAPSE 12 |
| coupling.gradual | 24 | 1 | validated | 5/5 (magnitude 1.0, duration 10, tick 104) | NO_EFFECTIVE_ACTION 17, ACTION_TOO_LATE 6 |
| coupling.restore | 40 | 4 | validated | 5/5 (magnitude 0.7, duration -, tick 104) | NO_EFFECTIVE_ACTION 26, ACTION_TOO_LATE 10 |
| internal.m2_tap | 8 | 0 | none validated | 0/5 (magnitude 0.0, duration -, tick 104) | NO_EFFECTIVE_ACTION 6, ACTION_TOO_LATE 2 |
| renewal.auxiliary | 32 | 0 | none validated | 0/5 (magnitude 0.75, duration -, tick 104) | NO_EFFECTIVE_ACTION 24, ACTION_TOO_LATE 8 |
| renewal.pulse | 72 | 0 | none validated | 0/5 (magnitude 1.25, duration 10, tick 104) | NO_EFFECTIVE_ACTION 54, ACTION_TOO_LATE 18 |
| resource.inflow | 72 | 0 | none validated | 0/5 (magnitude 0.02, duration 120, tick 104) | NO_EFFECTIVE_ACTION 54, ACTION_TOO_LATE 18 |
| resource.pulse | 64 | 14 | validated | 5/5 (magnitude 0.5, duration -, tick 113) | NO_EFFECTIVE_ACTION 29, ACTION_TOO_LATE 14, OVERSHOOT 7 |
| resource.redistribute | 48 | 0 | none validated | 0/5 (magnitude 0.06, duration 10, tick 104) | NO_EFFECTIVE_ACTION 36, ACTION_TOO_LATE 12 |
| resource.reserve | 24 | 0 | none validated | 0/5 (magnitude 24.0, duration -, tick 104) | NO_EFFECTIVE_ACTION 18, ACTION_TOO_LATE 6 |

Restoring the coupling gain **alone** is effective only very early (it needs the repair within a few ticks of the damage, and a partial restoration is enough at some ticks); a gradual restoration likewise. A temporary bridge (the gain strengthened for a while, then returned to the damaged value) is not effective: the damage remains after it. **A resource pulse works much later and over a long band**: the repair site
is not the damage site, and the original parameter restored alone does not restore the system once the damage has set in. The local bypass was not implemented in the main experiments (no spatial coupling path in the engine); it was built afterwards as a second sensing path (section 30).

## 11. Resource (Experiment N)

| stress | effective pulse band (tick 113) | phase by pulse size |
|---|---|---|
| coupling weakened (gain 0.5) | 0.6 - 2.5 | insufficient intervention 0.1-0.5; effective recovery 0.6-2.5; overshoot 2.6-6.0 |
| resource reduced (regrow 0.01, charge 0.2) | none | no effect (no magnitude of the sweep recovers) 0.1-6.0 |
| renewal efficiency 0.6 | none | no effect (no magnitude of the sweep recovers) 0.1-6.0 |
| renewal stopped (feedback removed) | none | no effect (no magnitude of the sweep recovers) 0.1-6.0 |
| Address degraded (A2 partial 50 %) | none | no effect (no magnitude of the sweep recovers) 0.1-0.3; transient recovery, then secondary collapse 0.4-6.0 |
| history lost | none | transient recovery, then secondary collapse 0.1-6.0 |

For the coupling stress the pulse has three regimes: **insufficient** below the band, **effective** inside it, **overshoot** above it (a secondary collapse); the boundaries are located to 0.1. The non-monotonicity of Stage 3 (2.0 recovers, 4.0 re-collapses) is reproduced with its boundary. For the other stresses **no pulse size of 0.1-6.0 recovers the run**; where a larger pulse gives a transient recovery followed by a secondary collapse that phase is named (*transient recovery, then secondary collapse*) and is not a recovery.
The other resource actions (sustained inflow, redistribution by diffusion (a proxy), power reserve (a proxy)) and the resource stress itself:

| action tried | settings tried (magnitude x duration x tick) | effective on all 5 exploration seeds | validation (seeds 6-10) | best any setting did on the exploration seeds | main failure ids of the others |
|---|---|---|---|---|---|
| coupling.bridge | 72 | 0 | none validated | 0/5 (magnitude 1.25, duration 10, tick 104) | NO_EFFECTIVE_ACTION 54, ACTION_TOO_LATE 18 |
| internal.m2_tap | 8 | 2 | validated | 5/5 (magnitude 0.0, duration -, tick 104) | NO_EFFECTIVE_ACTION 4, ACTION_TOO_LATE 2 |
| renewal.auxiliary | 32 | 0 | none validated | 0/5 (magnitude 0.75, duration -, tick 104) | NO_EFFECTIVE_ACTION 24, ACTION_TOO_LATE 8 |
| renewal.pulse | 72 | 0 | none validated | 0/5 (magnitude 1.25, duration 10, tick 104) | NO_EFFECTIVE_ACTION 54, ACTION_TOO_LATE 18 |
| resource.inflow | 72 | 0 | none validated | 0/5 (magnitude 0.02, duration 120, tick 104) | NO_EFFECTIVE_ACTION 45, ACTION_TOO_LATE 18, SECONDARY_COLLAPSE 9 |
| resource.pulse | 64 | 0 | none validated | 0/5 (magnitude 0.25, duration -, tick 104) | NO_EFFECTIVE_ACTION 48, ACTION_TOO_LATE 15, OVERSHOOT 1 |
| resource.redistribute | 48 | 0 | none validated | 0/5 (magnitude 0.06, duration 10, tick 104) | NO_EFFECTIVE_ACTION 36, ACTION_TOO_LATE 12 |
| resource.reserve | 24 | 0 | none validated | 0/5 (magnitude 24.0, duration -, tick 104) | NO_EFFECTIVE_ACTION 15, ACTION_TOO_LATE 6, SECONDARY_COLLAPSE 3 |

## 12. Renewal (Experiment O)

Two stresses: efficiency 0.6, and renewal stopped (the feedback component removed).

Renewal efficiency 0.6:

| action tried | settings tried (magnitude x duration x tick) | effective on all 5 exploration seeds | validation (seeds 6-10) | best any setting did on the exploration seeds | main failure ids of the others |
|---|---|---|---|---|---|
| coupling.bridge | 72 | 0 | none validated | 0/5 (magnitude 1.25, duration 10, tick 104) | NO_EFFECTIVE_ACTION 54, ACTION_TOO_LATE 18 |
| internal.m2_tap | 8 | 2 | validated | 5/5 (magnitude 0.0, duration -, tick 104) | NO_EFFECTIVE_ACTION 4, ACTION_TOO_LATE 2 |
| renewal.auxiliary | 32 | 0 | none validated | 0/5 (magnitude 0.75, duration -, tick 104) | NO_EFFECTIVE_ACTION 24, ACTION_TOO_LATE 8 |
| renewal.pulse | 72 | 0 | none validated | 0/5 (magnitude 1.25, duration 10, tick 104) | NO_EFFECTIVE_ACTION 45, ACTION_TOO_LATE 18, OVERSHOOT 9 |
| renewal.restore | 32 | 1 | validated | 5/5 (magnitude 1.0, duration -, tick 104) | NO_EFFECTIVE_ACTION 22, ACTION_TOO_LATE 8, SEED_DEPENDENT 1 |
| resource.inflow | 72 | 0 | none validated | 0/5 (magnitude 0.02, duration 120, tick 104) | NO_EFFECTIVE_ACTION 54, ACTION_TOO_LATE 18 |
| resource.pulse | 64 | 0 | none validated | 0/5 (magnitude 0.25, duration -, tick 104) | NO_EFFECTIVE_ACTION 48, ACTION_TOO_LATE 16 |
| resource.redistribute | 48 | 0 | none validated | 0/5 (magnitude 0.06, duration 10, tick 104) | NO_EFFECTIVE_ACTION 36, ACTION_TOO_LATE 12 |
| resource.reserve | 24 | 0 | none validated | 0/5 (magnitude 24.0, duration -, tick 104) | NO_EFFECTIVE_ACTION 18, ACTION_TOO_LATE 6 |

Renewal stopped:

| action tried | settings tried (magnitude x duration x tick) | effective on all 5 exploration seeds | validation (seeds 6-10) | best any setting did on the exploration seeds | main failure ids of the others |
|---|---|---|---|---|---|
| coupling.bridge | 72 | 0 | none validated | 0/5 (magnitude 1.25, duration 10, tick 104) | NO_EFFECTIVE_ACTION 54, ACTION_TOO_LATE 18 |
| internal.m2_tap | 8 | 0 | none validated | 0/5 (magnitude 0.0, duration -, tick 104) | NO_EFFECTIVE_ACTION 6, ACTION_TOO_LATE 2 |
| renewal.auxiliary | 32 | 0 | none validated | 0/5 (magnitude 0.75, duration -, tick 104) | NO_EFFECTIVE_ACTION 24, ACTION_TOO_LATE 8 |
| renewal.pulse | 72 | 0 | none validated | 0/5 (magnitude 1.25, duration 10, tick 104) | NO_EFFECTIVE_ACTION 54, ACTION_TOO_LATE 18 |
| renewal.restart | 8 | 0 | none validated | 0/5 (magnitude 0.0, duration -, tick 104) | NO_EFFECTIVE_ACTION 6, ACTION_TOO_LATE 2 |
| resource.inflow | 72 | 0 | none validated | 0/5 (magnitude 0.02, duration 120, tick 104) | NO_EFFECTIVE_ACTION 54, ACTION_TOO_LATE 18 |
| resource.pulse | 64 | 0 | none validated | 0/5 (magnitude 0.25, duration -, tick 104) | NO_EFFECTIVE_ACTION 48, ACTION_TOO_LATE 16 |
| resource.redistribute | 48 | 0 | none validated | 0/5 (magnitude 0.06, duration 10, tick 104) | NO_EFFECTIVE_ACTION 36, ACTION_TOO_LATE 12 |
| resource.reserve | 24 | 0 | none validated | 0/5 (magnitude 24.0, duration -, tick 104) | NO_EFFECTIVE_ACTION 18, ACTION_TOO_LATE 6 |

Efficiency: a full restoration is effective only within a few ticks of the damage (the fine sweep finds that a restoration to 0.95 is the minimum at those ticks, so a partial restoration to 0.9 or less is **not** enough); the M2 tap is effective only slightly longer. A restart of a stopped renewal alone is never effective (section 8); a restart **together with** a pulse is (section 14).

## 13. Address (Experiment P)

Stage 4's strict nulls (collision, stale) were results of a *fixed* configuration and are **not** overwritten: this section is about a *dynamic degraded* condition (A2 partial 50 % from tick 100).

| action tried | settings tried (magnitude x duration x tick) | effective on all 5 exploration seeds | validation (seeds 6-10) | best any setting did on the exploration seeds | main failure ids of the others |
|---|---|---|---|---|---|
| address.reassign | 8 | 0 | none validated | 1/5 (magnitude 0.0, duration -, tick 104) | NO_EFFECTIVE_ACTION 5, ACTION_TOO_LATE 2, SEED_DEPENDENT 1 |
| address.restore | 8 | 0 | none validated | 2/5 (magnitude 0.0, duration -, tick 104) | NO_EFFECTIVE_ACTION 5, ACTION_TOO_LATE 2, SEED_DEPENDENT 1 |
| coupling.bridge | 72 | 0 | none validated | 0/5 (magnitude 1.25, duration 10, tick 104) | NO_EFFECTIVE_ACTION 45, ACTION_TOO_LATE 18, SECONDARY_COLLAPSE 9 |
| internal.m2_tap | 8 | 0 | none validated | 0/5 (magnitude 0.0, duration -, tick 104) | NO_EFFECTIVE_ACTION 5, ACTION_TOO_LATE 2, SECONDARY_COLLAPSE 1 |
| renewal.auxiliary | 32 | 0 | none validated | 0/5 (magnitude 0.75, duration -, tick 104) | NO_EFFECTIVE_ACTION 24, ACTION_TOO_LATE 8 |
| renewal.pulse | 72 | 0 | none validated | 0/5 (magnitude 1.25, duration 10, tick 104) | NO_EFFECTIVE_ACTION 54, ACTION_TOO_LATE 18 |
| resource.inflow | 72 | 0 | none validated | 0/5 (magnitude 0.02, duration 120, tick 104) | NO_EFFECTIVE_ACTION 54, ACTION_TOO_LATE 18 |
| resource.pulse | 64 | 0 | none validated | 0/5 (magnitude 0.25, duration -, tick 104) | NO_EFFECTIVE_ACTION 32, ACTION_TOO_LATE 16, OVERSHOOT 16 |
| resource.redistribute | 48 | 0 | none validated | 0/5 (magnitude 0.06, duration 10, tick 104) | NO_EFFECTIVE_ACTION 36, ACTION_TOO_LATE 12 |
| resource.reserve | 24 | 0 | none validated | 0/5 (magnitude 24.0, duration -, tick 104) | NO_EFFECTIVE_ACTION 18, ACTION_TOO_LATE 6 |

Three restorations are three measures (5 seeds each):

| case | operational restoration (5 seeds) | Address restoration | observability restoration (Address resolution 0.5) | mean Address integrity, last 30 ticks |
|---|---|---|---|---|
| no repair | 0/5 | 0/5 | 5/5 | 0.5 |
| Address restore at 104 | 2/5 | 5/5 | 5/5 | 1.0 |
| Address restore at 113 | 0/5 | 5/5 | 5/5 | 1.0 |
| Address reassign at 113 | 0/5 | 5/5 | 5/5 | 1.0 |
| resource pulse 1.0 at 113 | 0/5 | 0/5 | 5/5 | 0.5 |
| Address restore + pulse 1.0 at 113 | 5/5 | 5/5 | 5/5 | 1.0 |

Restoring the Address restores the Address integrity at once on every seed, **and does not restore the operation at tick 113 (0 of 5)**: Address restoration and operational restoration are different things. A restoration **together with** a pulse recovers the run in a time window (section 14), but its strict validation failed at tick 113 (a near miss: 4 of 5 validation seeds, one secondary collapse), so
it is reported as such. This does not show that the Address was the direct cause of the collapse: the Address repair alone is null, and the combination works through the resource.

## 14. Combined repair (Experiment Q)

Pairs of different actions, only for the stresses no single world-state action recovers at tick 113 (a restricted set: a primary restoration of the damaged family or the M2 tap, with a secondary additive action), at ticks [113, 120, 130]:

| stress | pair | tick | exploration | validation | status | synergy (neither part effective alone) | evaluation seeds 11-30 |
|---|---|---|---|---|---|---|---|
| Address degraded (A2 partial 50 %) | address.reassign + resource.pulse 0.5 | 113 | 5/5 | 4/5 | **near miss** | no (a part is effective alone at this tick) | 12/20 |
| Address degraded (A2 partial 50 %) | address.reassign + resource.pulse 1.0 | 113 | 5/5 | 4/5 | **near miss** | no (a part is effective alone at this tick) | 15/20 |
| Address degraded (A2 partial 50 %) | address.reassign + resource.pulse 2.0 | 113 | 5/5 | 4/5 | **near miss** | no (a part is effective alone at this tick) | 15/20 |
| Address degraded (A2 partial 50 %) | address.restore + resource.pulse 0.5 | 113 | 5/5 | 4/5 | **near miss** | no (a part is effective alone at this tick) | 14/20 |
| Address degraded (A2 partial 50 %) | address.restore + resource.pulse 0.5 | 120 | 3/5 | - | **near miss** | no (a part is effective alone at this tick) | 17/20 |
| Address degraded (A2 partial 50 %) | address.restore + resource.pulse 0.5 | 130 | 5/5 | 3/5 | **near miss** | no (a part is effective alone at this tick) | 16/20 |
| Address degraded (A2 partial 50 %) | address.restore + resource.pulse 1.0 | 113 | 5/5 | 4/5 | **near miss** | no (a part is effective alone at this tick) | 15/20 |
| Address degraded (A2 partial 50 %) | address.restore + resource.pulse 1.0 | 130 | 4/5 | - | **near miss** | no (a part is effective alone at this tick) | 13/20 |
| Address degraded (A2 partial 50 %) | address.restore + resource.pulse 2.0 | 113 | 5/5 | 4/5 | **near miss** | no (a part is effective alone at this tick) | 15/20 |
| history lost | internal.m2_tap + renewal.auxiliary 1.0 | 113 | 5/5 | 5/5 | **validated** | no (a part is effective alone at this tick) | 20/20 |
| history lost | internal.m2_tap + renewal.auxiliary 2.0 | 113 | 5/5 | 5/5 | **validated** | no (a part is effective alone at this tick) | 20/20 |
| history lost | internal.m2_tap + renewal.pulse 1.5 (for 20) | 113 | 5/5 | 5/5 | **validated** | no (a part is effective alone at this tick) | 20/20 |
| history lost | internal.m2_tap + resource.inflow 0.02 (for 120) | 113 | 5/5 | 5/5 | **validated** | no (a part is effective alone at this tick) | 20/20 |
| history lost | internal.m2_tap + resource.pulse 0.5 | 113 | 5/5 | 5/5 | **validated** | no (a part is effective alone at this tick) | 20/20 |
| history lost | internal.m2_tap + resource.pulse 0.5 | 120 | 5/5 | 5/5 | **validated** | yes | 20/20 |
| history lost | internal.m2_tap + resource.pulse 1.0 | 113 | 5/5 | 5/5 | **validated** | no (a part is effective alone at this tick) | 20/20 |
| history lost | internal.m2_tap + resource.pulse 1.0 | 120 | 5/5 | 5/5 | **validated** | yes | 20/20 |
| history lost | internal.m2_tap + resource.pulse 2.0 | 113 | 5/5 | 5/5 | **validated** | no (a part is effective alone at this tick) | 20/20 |
| history lost | internal.m2_tap + resource.pulse 2.0 | 120 | 5/5 | 5/5 | **validated** | yes | 20/20 |
| history lost | internal.m2_tap + resource.reserve 48.0 | 113 | 5/5 | 5/5 | **validated** | no (a part is effective alone at this tick) | 20/20 |
| renewal stopped (feedback removed) | renewal.restart + resource.pulse 0.5 | 120 | 5/5 | 5/5 | **validated** | yes | 17/20 |
| renewal stopped (feedback removed) | renewal.restart + resource.pulse 0.5 | 130 | 5/5 | 5/5 | **validated** | yes | 20/20 |
| renewal stopped (feedback removed) | renewal.restart + resource.pulse 1.0 | 130 | 5/5 | 5/5 | **validated** | yes | 20/20 |

A pair is credited as a **combined recovery** only where neither part is effective alone at that tick. Where a pair is effective and one part is effective alone (the M2 tap with a pulse on history lost, at ticks up to 113), the pair adds nothing and is not credited with anything. Where it extends a window (history lost: the pair is effective to tick 120, the M2 tap alone to 113), that extension is the combined result.

## 15. Controllers

Six controllers (`repair_ctl.py`): **none**; **fixed** (one action chosen before any run was looked at: a pulse of 2.0, applied once); **rule_based** (each sensed damaged feature mapped to the action that undoes it: restore the gain, restore regrow and charge, restore the efficiency then reconnect the feedback, restore the Address, the M2 tap for a lost history; no knowledge of what worked);
**cost_aware** (the validated library below, highest expected recovery first, the cheapest among equals); **delayed** (cost_aware acting 15 ticks later); **noisy** (cost_aware on a detection that flips each sensed feature with probability 0.1, without debounce). All sense only the five features of the stage 5 sensor and the run's own status; a revision loop watches each attempt for 25 ticks and moves to the next candidate if the run has not recovered (at most 3).
Every decision is logged: what was detected, which plans were available and rejected (with the reason), the one selected, its estimated cost and expected recovery, and what actually happened. The library is built from seeds 1-10 only; the controllers are evaluated on seeds 11-30. Success is a recovery at the long horizon (not a switch, not an action fired). *Effective*: success rate above that of no repair by at least 0.30 and Fisher's p < 0.05 (fixed before the runs), Holm's correction over all comparisons reported.

Library (4 plans validated at the decision tick):

| plan | class | stresses it was validated for | expected recovery | cost (equal-weight normalised) | cost components |
|---|---|---|---|---|---|
| internal.m2_tap m=0.0 d=0 | A | history lost | 1.0 | 0.7764 | {"switching": 1, "collateral": 0.1073, "energy_rate_norm": 0.9993} |
| resource.pulse m=1.0 d=0 | B | coupling weakened (gain 0.5) | 0.25 | 0.9999 | {"switching": 1, "collateral": 0.316, "energy_rate_norm": 1.0098} |
| resource.pulse m=1.5 d=0 | B | coupling weakened (gain 0.5) | 0.25 | 0.9999 | {"switching": 1, "collateral": 0.316, "energy_rate_norm": 1.0098} |
| resource.pulse m=2.0 d=0 | B | coupling weakened (gain 0.5) | 0.25 | 1.0 | {"switching": 1, "collateral": 0.3161, "energy_rate_norm": 1.0098} |

Success at the long horizon, 20 seeds per cell:

| stress (known, library built for it) | none | fixed | rule_based | cost_aware | delayed | noisy |
|---|---|---|---|---|---|---|
| coupling weakened (gain 0.5) | 0/20 | 20/20 | 0/20 | 20/20 | 9/20 | 0/20 |
| resource reduced (regrow 0.01, charge 0.2) | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 |
| renewal efficiency 0.6 | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 |
| renewal stopped (feedback removed) | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 |
| Address degraded (A2 partial 50 %) | 0/20 | 0/20 | 8/20 | 0/20 | 0/20 | 0/20 |
| history lost | 0/20 | 0/20 | 9/20 | 9/20 | 0/20 | 3/20 |
| no stress | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 |

Effective (unadjusted, with the Holm-adjusted p):

| stress | controller | success | no repair | difference | Fisher p | Holm p | verdict |
|---|---|---|---|---|---|---|---|
| coupling weakened (gain 0.5) | fixed | 20/20 | 0/20 | 1.0 | 0.0 | 0.0 | **effective** |
| coupling weakened (gain 0.5) | cost_aware | 20/20 | 0/20 | 1.0 | 0.0 | 0.0 | **effective** |
| coupling weakened (gain 0.5) | delayed | 9/20 | 0/20 | 0.45 | 0.00123 | 0.03444 | **effective** |
| Address degraded (A2 partial 50 %) | rule_based | 8/20 | 0/20 | 0.4 | 0.00328 | 0.082 | **effective** (not after Holm) |
| history lost | rule_based | 9/20 | 0/20 | 0.45 | 0.00123 | 0.03444 | **effective** |
| history lost | cost_aware | 9/20 | 0/20 | 0.45 | 0.00123 | 0.03444 | **effective** |

Failure ids of the controller runs (taxonomy: NO_EFFECTIVE_ACTION, ACTION_TOO_WEAK, ACTION_TOO_LATE, OVERSHOOT, SECONDARY_COLLAPSE, DETECTION_FAILURE, ADDRESS_UNRESOLVED, INSUFFICIENT_RESOURCE, EXCESSIVE_COST, DESTABILIZED_BY_ACTION, OUTSIDE_TESTED_ACTION_SPACE; SEED_DEPENDENT is an addition for a setting effective on some seeds only):

| stress | controller | failure ids of the 20 runs |
|---|---|---|
| Address partial 0.3 (stronger) | cost_aware | OUTSIDE_TESTED_ACTION_SPACE 20 |
| Address partial 0.3 (stronger) | delayed | OUTSIDE_TESTED_ACTION_SPACE 20 |
| Address partial 0.3 (stronger) | fixed | ADDRESS_UNRESOLVED 20 |
| Address partial 0.3 (stronger) | noisy | ADDRESS_UNRESOLVED 4, OUTSIDE_TESTED_ACTION_SPACE 16 |
| Address partial 0.3 (stronger) | none | DETECTION_FAILURE 20 |
| Address partial 0.3 (stronger) | rule_based | ADDRESS_UNRESOLVED 16 |
| Address partial 0.5 | cost_aware | OUTSIDE_TESTED_ACTION_SPACE 20 |
| Address partial 0.5 | delayed | OUTSIDE_TESTED_ACTION_SPACE 20 |
| Address partial 0.5 | fixed | ADDRESS_UNRESOLVED 20 |
| Address partial 0.5 | noisy | ADDRESS_UNRESOLVED 4, OUTSIDE_TESTED_ACTION_SPACE 16 |
| Address partial 0.5 | none | DETECTION_FAILURE 20 |
| Address partial 0.5 | rule_based | ADDRESS_UNRESOLVED 12 |
| Address partial 0.5 at tick 130 (later) | cost_aware | OUTSIDE_TESTED_ACTION_SPACE 20 |
| Address partial 0.5 at tick 130 (later) | delayed | OUTSIDE_TESTED_ACTION_SPACE 20 |
| Address partial 0.5 at tick 130 (later) | fixed | ADDRESS_UNRESOLVED 20 |
| Address partial 0.5 at tick 130 (later) | noisy | ADDRESS_UNRESOLVED 4, OUTSIDE_TESTED_ACTION_SPACE 16 |
| Address partial 0.5 at tick 130 (later) | none | DETECTION_FAILURE 20 |
| Address partial 0.5 at tick 130 (later) | rule_based | ADDRESS_UNRESOLVED 12 |
| Address partial 0.5 at tick 80 (earlier) | cost_aware | OUTSIDE_TESTED_ACTION_SPACE 20 |
| Address partial 0.5 at tick 80 (earlier) | delayed | OUTSIDE_TESTED_ACTION_SPACE 20 |
| Address partial 0.5 at tick 80 (earlier) | fixed | ADDRESS_UNRESOLVED 20 |
| Address partial 0.5 at tick 80 (earlier) | noisy | ADDRESS_UNRESOLVED 4, OUTSIDE_TESTED_ACTION_SPACE 16 |
| Address partial 0.5 at tick 80 (earlier) | none | DETECTION_FAILURE 20 |
| Address partial 0.5 at tick 80 (earlier) | rule_based | ADDRESS_UNRESOLVED 12 |
| Address partial 0.7 (weaker) | cost_aware | OUTSIDE_TESTED_ACTION_SPACE 20 |
| Address partial 0.7 (weaker) | delayed | OUTSIDE_TESTED_ACTION_SPACE 20 |
| Address partial 0.7 (weaker) | fixed | ADDRESS_UNRESOLVED 20 |
| Address partial 0.7 (weaker) | noisy | ADDRESS_UNRESOLVED 4, OUTSIDE_TESTED_ACTION_SPACE 16 |
| Address partial 0.7 (weaker) | none | DETECTION_FAILURE 20 |
| Address partial 0.7 (weaker) | rule_based | ADDRESS_UNRESOLVED 3 |
| coupling gain 0.3 (stronger drop) | cost_aware | OUTSIDE_TESTED_ACTION_SPACE 20 |
| coupling gain 0.3 (stronger drop) | delayed | OUTSIDE_TESTED_ACTION_SPACE 20 |
| coupling gain 0.3 (stronger drop) | fixed | ACTION_TOO_LATE 20 |
| coupling gain 0.3 (stronger drop) | noisy | ACTION_TOO_LATE 4, OUTSIDE_TESTED_ACTION_SPACE 16 |
| coupling gain 0.3 (stronger drop) | none | DETECTION_FAILURE 20 |
| coupling gain 0.3 (stronger drop) | rule_based | ACTION_TOO_LATE 20 |
| coupling gain 0.5 | delayed | SECONDARY_COLLAPSE 11 |
| coupling gain 0.5 | noisy | NO_EFFECTIVE_ACTION 4, OUTSIDE_TESTED_ACTION_SPACE 16 |
| coupling gain 0.5 | none | DETECTION_FAILURE 20 |
| coupling gain 0.5 | rule_based | NO_EFFECTIVE_ACTION 20 |
| coupling gain 0.5 at tick 130 (later) | delayed | SECONDARY_COLLAPSE 14 |
| coupling gain 0.5 at tick 130 (later) | noisy | ACTION_TOO_LATE 4, OUTSIDE_TESTED_ACTION_SPACE 16 |
| coupling gain 0.5 at tick 130 (later) | none | DETECTION_FAILURE 20 |
| coupling gain 0.5 at tick 130 (later) | rule_based | ACTION_TOO_LATE 20 |
| coupling gain 0.7 (weaker drop) | noisy | ACTION_TOO_LATE 4, OUTSIDE_TESTED_ACTION_SPACE 16 |
| coupling gain 0.7 (weaker drop) | none | DETECTION_FAILURE 20 |
| coupling gain 0.7 (weaker drop) | rule_based | ACTION_TOO_LATE 20 |
| history lost | cost_aware | NO_EFFECTIVE_ACTION 11 |
| history lost | delayed | NO_EFFECTIVE_ACTION 20 |
| history lost | fixed | SECONDARY_COLLAPSE 11, NO_EFFECTIVE_ACTION 9 |
| history lost | noisy | NO_EFFECTIVE_ACTION 1, OUTSIDE_TESTED_ACTION_SPACE 16 |
| history lost | none | DETECTION_FAILURE 20 |
| history lost | rule_based | NO_EFFECTIVE_ACTION 11 |
| renewal efficiency 0.4 (stronger) | cost_aware | OUTSIDE_TESTED_ACTION_SPACE 20 |
| renewal efficiency 0.4 (stronger) | delayed | OUTSIDE_TESTED_ACTION_SPACE 20 |
| renewal efficiency 0.4 (stronger) | fixed | ACTION_TOO_LATE 20 |
| renewal efficiency 0.4 (stronger) | noisy | ACTION_TOO_LATE 4, OUTSIDE_TESTED_ACTION_SPACE 16 |
| renewal efficiency 0.4 (stronger) | none | DETECTION_FAILURE 20 |
| renewal efficiency 0.4 (stronger) | rule_based | ACTION_TOO_LATE 20 |
| renewal efficiency 0.6 | cost_aware | ACTION_TOO_LATE 20 |

**Reading, as far as the data go.** On the coupling stress the *fixed* pulse (chosen beforehand) and the *cost-aware* controller are both 20/20: the adaptive controller did not do better than a known fixed repair, and that equality is **not** adaptive superiority. The *rule-based* controller, which restores the damaged parameter, recovers 0/20: **restoring the original parameter alone does not restore the system.**
On history lost the rule-based (M2) and cost-aware controllers are 9/20, the Stage 5 result (the M2 window closes at tick 113 and the controller acts at 114: it acts on the edge of the window). On the Address stress the **cost-aware controller (0/20) is worse than the simple rule (restore the Address)**: the strictly validated library holds no Address action, so the cost-aware controller finds nothing to apply
(`OUTSIDE_TESTED_ACTION_SPACE`) while the rule acts early and recovers on some seeds. For the renewal and resource stresses no controller recovers anything; the *noisy* controller's few recoveries are the accidental result of a false detection that acted early, inside the M2 window, not a skill.

## 16. False positives

The same controllers on a run with **no stress** (Stage 5's no-stress switch count was 0 and is the baseline):

| controller | runs | success | mean attempts (false interventions) per run | mean interventions | mean energy use |
|---|---|---|---|---|---|
| cost_aware | 20 | 20/20 | 0.0 | 0.0 | 147.04 |
| delayed | 20 | 20/20 | 0.0 | 0.0 | 147.04 |
| fixed | 20 | 20/20 | 0.0 | 0.0 | 147.04 |
| noisy | 20 | 20/20 | 0.2 | 0.2 | 147.04 |
| none | 20 | 20/20 | 0.0 | 0.0 | 147.04 |
| rule_based | 20 | 20/20 | 0.0 | 0.0 | 147.04 |

No controller with a debounced detection acted without a stress; the controller with a noisy detection made false interventions (attempts per run above) and the run still recovered every time: false interventions were not harmful in this model. Unnecessary route switches: none (no controller of this stage switches routes except the M2 tap, which is an action in the library).

## 17. Unknown stress

Variations of the stresses the library was built for (a different severity, profile or onset), which the library never saw; 20 seeds each (11-30):

| held-out variation | what varies | onset | none | fixed | rule_based | cost_aware | delayed | noisy |
|---|---|---|---|---|---|---|---|---|
| coupling gain 0.3 (stronger drop) | severity | 100 | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 |
| coupling gain 0.7 (weaker drop) | severity | 100 | 0/20 | 20/20 | 0/20 | 20/20 | 20/20 | 0/20 |
| resource regrow 0.015 charge 0.3 (different profile) | profile | 100 | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 |
| renewal efficiency 0.4 (stronger) | severity | 100 | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 |
| renewal efficiency 0.8 (weaker) | severity | 100 | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 | 3/20 |
| renewal stopped at tick 130 (delayed failure) | onset | 130 | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 | 0/20 |
| Address partial 0.3 (stronger) | severity | 100 | 0/20 | 0/20 | 4/20 | 0/20 | 0/20 | 0/20 |
| Address partial 0.7 (weaker) | severity | 100 | 0/20 | 0/20 | 17/20 | 0/20 | 0/20 | 0/20 |
| Address partial 0.5 at tick 80 (earlier) | onset | 80 | 0/20 | 0/20 | 8/20 | 0/20 | 0/20 | 0/20 |
| Address partial 0.5 at tick 130 (later) | onset | 130 | 0/20 | 0/20 | 8/20 | 0/20 | 0/20 | 0/20 |
| coupling gain 0.5 at tick 130 (later) | onset | 130 | 0/20 | 20/20 | 0/20 | 20/20 | 6/20 | 0/20 |

| stress | controller | success | no repair | difference | Fisher p | Holm p | verdict |
|---|---|---|---|---|---|---|---|
| coupling gain 0.7 (weaker drop) | fixed | 20/20 | 0/20 | 1.0 | 0.0 | 0.0 | **effective** |
| coupling gain 0.7 (weaker drop) | cost_aware | 20/20 | 0/20 | 1.0 | 0.0 | 0.0 | **effective** |
| coupling gain 0.7 (weaker drop) | delayed | 20/20 | 0/20 | 1.0 | 0.0 | 0.0 | **effective** |
| Address partial 0.7 (weaker) | rule_based | 17/20 | 0/20 | 0.85 | 0.0 | 0.0 | **effective** |
| Address partial 0.5 at tick 80 (earlier) | rule_based | 8/20 | 0/20 | 0.4 | 0.00328 | 0.16072 | **effective** (not after Holm) |
| Address partial 0.5 at tick 130 (later) | rule_based | 8/20 | 0/20 | 0.4 | 0.00328 | 0.16072 | **effective** (not after Holm) |
| coupling gain 0.5 at tick 130 (later) | fixed | 20/20 | 0/20 | 1.0 | 0.0 | 0.0 | **effective** |
| coupling gain 0.5 at tick 130 (later) | cost_aware | 20/20 | 0/20 | 1.0 | 0.0 | 0.0 | **effective** |
| coupling gain 0.5 at tick 130 (later) | delayed | 6/20 | 0/20 | 0.3 | 0.0202 | 0.9494 | **effective** (not after Holm) |

**The controller generalized to the tested held-out variations of the coupling stress (a weaker drop, a later onset) and not to a stronger drop (gain 0.3), where every controller, including the fixed pulse, recovers 0 of 20.** For the Address variations only the rule-based controller acts and its success rises with milder severity (0.7: 17/20; 0.5: 8/20; 0.3: 4/20). For renewal and resource variations nothing recovers. Nothing here shows a general generalization.

## 18. MFS x repairability

The repairs Pipeline A validated (or nearly) on the full arrangement were tried unchanged on each distinct validated MFS (the components outside the MFS removed at tick 0, under the condition it was found for), on seeds 1-5 (not independently validated here):

| MFS | coupling | resource | renewal efficiency | renewal stopped | Address | history lost |
|---|---|---|---|---|---|---|
| MFS-F1-1 | externally repairable | neither (under the tested actions) | externally repairable | neither (under the tested actions) | externally repairable | neither (under the tested actions) |
| MFS-F2-1 | externally repairable | neither (under the tested actions) | externally repairable | neither (under the tested actions) | externally repairable | neither (under the tested actions) |
| MFS-F8-1 | externally repairable | neither (under the tested actions) | both | neither (under the tested actions) | externally repairable | neither (under the tested actions) |
| MFS-F14-2 | inconclusive | neither (under the tested actions) | neither (under the tested actions) | neither (under the tested actions) | inconclusive | both |

The repairability profile **differs between MFS**: a repair validated on the full arrangement does not carry over unchanged (the MFS-F14-2, the M2-mediated set, is the only one with an internal route for history lost and the one where the coupling and Address repairs are inconclusive). An MFS whose condition has no M2 tap has no internal route of that kind.

## 19. SSS x repairability

On a 3 x 3 grid of the SSS region (scale 0.75/1/1.25 x speed 0.9/1/1.1, size 1) the unstressed MFS persists on part of the grid (its island); on the island each stress was tried with no action and with its recommended repair (3 seeds):

| MFS | points of the 3 x 3 SSS grid where the unstressed MFS persists (its island) | classes over (island point x stress), one repair per stress |
|---|---|---|
| MFS-F1-1 | 5/9 | unrecoverable (no tested repair at or before the decision tick) 20; repairable 6; repairable on some seeds only 4 |
| MFS-F14-2 | 9/9 | repairable 22; unrecoverable 18; unrecoverable (no tested repair at or before the decision tick) 9; repairable on some seeds only 5 |
| MFS-F2-1 | 5/9 | unrecoverable (no tested repair at or before the decision tick) 20; repairable 6; repairable on some seeds only 4 |
| MFS-F8-1 | 9/9 | repairable 26; unrecoverable 12; unrecoverable (no tested repair at or before the decision tick) 9; overshoot-sensitive / unstable recovery 6; repairable on some seeds only 1 |

Cells are *repairable* (the recommended repair recovers on every seed), *repairable on some seeds only*, *overshoot-sensitive / unstable recovery* (a secondary collapse), *costly recovery* (above the cost limit) or *unrecoverable*. The per-cell classes are in `experiments_stage6_cross.json` (`C2_sss`).

## 20. Observation x repairability

Operational recovery and observed recovery are separate fields (with the observability status): a run that recovered can be observed as collapsed. Observation repair (full observation) is a change of the observer; it never changes the run.

| run | observation | operational state | observed state | observability status | operational recovery | observed recovery |
|---|---|---|---|---|---|---|
| coupling stress, resource pulse 1.0 at 113 (recovered) | full observation | ACTIVE | ACTIVE | OBSERVABLE | yes | yes |
| coupling stress, resource pulse 1.0 at 113 (recovered) | sampling interval 2 | ACTIVE | COLLAPSED | INSUFFICIENT_TEMPORAL_RESOLUTION | yes | no |
| coupling stress, resource pulse 1.0 at 113 (recovered) | sampling interval 4 | ACTIVE | COLLAPSED | INSUFFICIENT_TEMPORAL_RESOLUTION | yes | no |
| coupling stress, resource pulse 1.0 at 113 (recovered) | sampling interval 8 | ACTIVE | COLLAPSED | INSUFFICIENT_TEMPORAL_RESOLUTION | yes | no |
| coupling stress, resource pulse 1.0 at 113 (recovered) | spatial stride 2 | ACTIVE | COLLAPSED | INSUFFICIENT_SPATIAL_RESOLUTION | yes | no |
| coupling stress, resource pulse 1.0 at 113 (recovered) | region excluding the bodies | ACTIVE | COLLAPSED | REGION_EXCLUDES_ACTIVITY | yes | no |
| coupling stress, resource pulse 1.0 at 113 (recovered) | Address resolution 0.5 | ACTIVE | ACTIVE | OBSERVABLE | yes | yes |
| coupling stress, no repair (collapsed) | full observation | COLLAPSED | COLLAPSED | OBSERVABLE | no | no |
| coupling stress, no repair (collapsed) | sampling interval 2 | COLLAPSED | COLLAPSED | OBSERVABLE | no | no |
| coupling stress, no repair (collapsed) | sampling interval 4 | COLLAPSED | COLLAPSED | OBSERVABLE | no | no |
| coupling stress, no repair (collapsed) | sampling interval 8 | COLLAPSED | COLLAPSED | OBSERVABLE | no | no |
| coupling stress, no repair (collapsed) | spatial stride 2 | COLLAPSED | COLLAPSED | OBSERVABLE | no | no |
| coupling stress, no repair (collapsed) | region excluding the bodies | COLLAPSED | COLLAPSED | OBSERVABLE | no | no |
| coupling stress, no repair (collapsed) | Address resolution 0.5 | COLLAPSED | COLLAPSED | OBSERVABLE | no | no |

Of the runs that recovered operationally, 20 (run, observation) pairs were **not** observed as recovered: coarse sampling (`INSUFFICIENT_TEMPORAL_RESOLUTION`), coarse spatial resolution (`INSUFFICIENT_SPATIAL_RESOLUTION`) and a region that excludes the bodies (`REGION_EXCLUDES_ACTIVITY`) all report COLLAPSED for an ACTIVE run; full observation (or Address resolution 0.5) restores agreement.

## 21. Reachable recovery regions

For each stress the tested action space divides the ticks into: recoverable by internal route change, by world-state repair, by a combined action, *unstable recovery* (a transient recovery followed by a secondary collapse: the overshoot and the near misses), *unrecoverable under the tested actions*. Section 8 gives the strip of every stress at one-tick resolution; the interface draws it. These are regions of the **tested action space**, not of the world.

## 22. Replay and interface

**Service.** `GET /api/meos/repair-library` (the action space with each action's status and declared cost model, the stresses, the controllers, the saved results), `POST /api/meos/repair-run` (a stress, explicit actions and/or a repair controller, a seed: the record, the evaluation at the three horizons with the costs, the events of the repair, and whether the recorded schedule replays identically without the controller).
A route refuses an action that is not implemented, an observation action (class C is not a run action), more than four actions, an unknown stress or controller.

**Research tab: the repair panel** (`RepairPanel.tsx`): stress selector, repair mode (controller or explicit actions: action, magnitude, duration, tick; a second action makes a combined repair), RUN; the three horizons (outcome, latency, secondary collapse, resource exhausted), the raw and normalised costs without a weighted total, the failure class, the controller's decisions (detected, available, rejected, selected, estimated cost, expected recovery, actual result);
the **reachable-recovery strips** (one cell per tick 101-170 and stress, coloured by what recovers it: internal reconfiguration / world-state repair / combined repair / nothing tested), the stress table (classification at the decision tick and at any tested tick, windows, minimum effective action), the resource-pulse phase bands, and the list of actions the engine cannot do or only approximates.

**Replay timeline** (markers, each with its source: the schedule, the controller log, the status record or a saved result): stress onset, repair decision, repair action, collapse prevented / full recovery, failed repair, overshoot, secondary collapse, irreversible threshold (for a window that closed). The collapse and recovery markers are those of the run's status record and are not repeated by the repair (an earlier version showed the collapse twice). A click gives the tick, the detail and the source; the inspection beside it shows the world state (operational, observed, observability), the active route and the MFS of the run.
**Research map** layers: damaged path, repairable path, repaired path, temporary bypass, world-state intervention, internal reconfiguration, failed repair (red dotted and crossed for damage and failure, violet for a world-state repair, blue for an internal one, green for a repaired path or a bypass); an internal reconfiguration is never drawn as a world-state repair.
**Technical view**: a repair figure of seven paths (resource, coupling, history, observation, recovery, Address, M2) with their state at the playhead, the stress with its tick, each repair action that has happened with its tick, magnitude, duration and class, the cost annotation and the operational result at the three horizons; drawn only from the run's events (a repair that did not happen is not drawn; the repair site is where the action acted).
**Deep links**: `stress=<id>&repair=<controller>` or `stress=<id>&ract=<action>/<magnitude>/<duration>/<tick>[,...]`; parsing, formatting and the plan are tested.


**Captures** (`docs/ecosystem/visual/stage6/`, 16 images, all taken in one run on the final build, after the repair panel was constrained to the width of the pane (an earlier layout let the panel overflow the pane and clipped the right third of the recovery strips); camera and viewport records in `cameras-balanced.json`; deep link after `?view=ecosystem&`):

| image | what it shows | deep link |
|---|---|---|
| `60-repair-recovered.png` | the three horizons, raw and normalised costs, failure class of a pulse of 1.0 at tick 113 on the coupling stress | `tab=research&stress=coupling gain 0.5&ract=resource.pulse/1/0/113` |
| `61-repair-overshoot.png` | the same with a pulse of 4.0: secondary collapse at every horizon | `...ract=resource.pulse/4/0/113` |
| `62-reachable-recovery-map.png` | the strip of each stress over ticks 101-420; in the settings and ticks that were measured every window closes (the three late ones at 389 / 384 / 384) | as 60 |
| `63-stress-table.png`, `64-pulse-phase-bands.png` | classification and windows per stress; insufficient / effective / overshoot bands | `...&repair=rule_based` |
| `65-controller-decisions.png`, `66-no-action-available.png` | a cost-aware controller's decisions; a detected Address stress with no available action | `stress=history lost&repair=cost_aware`; `stress=Address partial 0.5&repair=cost_aware` |
| `67-technical-repair-figure.png`, `68-technical-overshoot-figure.png` | the repair figure of the technical sheet: repaired coupling path with a world-state action on the resource path; the failed path after a pulse of 4.0 | `tech=ncb&...&tick=200`, `...&tick=479` |
| `69-research-map-repair-layers.png` | damaged, repairable, world-state and repaired layers of the research map at tick 120 | `tech=ncb&...&layer=repair.damaged,...` |
| `70-replay-repair-markers.png` | the replay markers of an overshooting run: stress, alteration, overshoot, repair, collapse (once) | as 61 |
| `71-mfs-repairability.png` | repairability of each stress on each MFS | as 60 |
| `72-address-three-restorations.png` | the Address repair as three measures: operation, Address, observer | `stress=Address partial 0.5&ract=address.restore/0/0/113` |
| `73-observation-vs-operational.png` | an operationally recovered run observed as collapsed under coarse sampling | as 60 |
| `74-extended-action-space.png` | the classification of each stress in the action space of Stage 6 and with the three actions built afterwards (engine meos-0.5) | `stress=Address partial 0.5&ract=address.restore/0/0/113` |
| `75-windows-measured-on.png` | the three windows that were open at tick 330, measured to tick 1140 with the extended horizon | `stress=coupling gain 0.5&ract=resource.pulse/1/0/113` |

Limits of the images: they are pictures of the model's records and of the saved results, not evidence; a click on a marker (tick, source, inspection) is behaviour covered by tests and cannot be written in a URL.

## 23. Performance

### Final series (the verdict of this section)

The first series (below) was noisy. A second series was run on the final tree, with its design fixed before any of its data were seen: **12 interleaved pairs** (Stage 5 build on port 3034, Stage 6 build on port 3031, the order alternating each repetition), balanced tier, 150 frames, 1672 x 808, the six conditions, each run started only when the 1-minute load average was below 3 (it waited at most 10 minutes and then ran anyway; the load at the start of every run is in `perf_stage6/paired_final/*.load`: 2.49-5.07, one run at 5.07). The rule is the one fixed for Stages 4 and 5 (CI lower bound above 1.05: regression; upper bound below 1.05: no meaningful regression; otherwise inconclusive); no repetition was excluded. (A first attempt at this series produced no data: the server's session limit answered 429 and the page never became ready; the limit was raised as in all earlier series and the series was run again; nothing from the failed attempt exists.)

| all 48 measures | regression | no meaningful regression | inconclusive |
|---|---|---|---|
| Stage 6 against Stage 5, 12 pairs | 0 | 10 | 38 |
| **A/A control**: the Stage 5 build on two ports, 12 pairs, three conditions (24 measures) | 0 | 8 | 16 |

Medians of the frame time (ms), Stage 5 against Stage 6:

| condition | mode | Stage 5 | Stage 6 | paired ratio | 95 % CI | verdict |
|---|---|---|---|---|---|---|
| habitat | static | 16.35 | 16.65 | 1.003 | [0.985, 1.101] | inconclusive |
| habitat | orbit | 17.2 | 17.15 | 1.014 | [0.971, 1.136] | inconclusive |
| habitat+repair | static | 14.25 | 14.05 | 1.004 | [0.959, 1.062] | inconclusive |
| habitat+repair | orbit | 15.45 | 14.75 | 0.977 | [0.883, 1.021] | no meaningful regression |
| habitat+repairtech | static | 14.2 | 13.8 | 0.979 | [0.925, 1.007] | no meaningful regression |
| habitat+repairtech | orbit | 15.1 | 14.7 | 0.997 | [0.948, 1.034] | no meaningful regression |
| habitat+research | static | 14.2 | 13.95 | 0.979 | [0.969, 1.01] | no meaningful regression |
| habitat+research | orbit | 14.6 | 14.5 | 0.98 | [0.97, 1.014] | no meaningful regression |
| habitat+technical | static | 14.35 | 14.5 | 1.004 | [0.99, 1.028] | no meaningful regression |
| habitat+technical | orbit | 14.9 | 15.25 | 1.027 | [0.948, 1.061] | inconclusive |
| overview | static | 12.5 | 12.4 | 1.003 | [0.961, 1.052] | inconclusive |
| overview | orbit | 15.65 | 15.7 | 1.003 | [0.978, 1.142] | inconclusive |

**Statistic.** For every measure (median, p95, p99, max of the 150 frame times of one run) the ratio Stage 6 / Stage 5 is formed **per repetition** (12 ratios); the estimate is their median and the 95 % interval is a bootstrap of that median over the 12 repetitions (10 000 resamples, fixed seed). The frames of a run are not resampled and are not treated as independent repetitions; the unit is the paired repetition.

**What the A/A control shows.** Two ports serving the *same* build, measured the same way, give 16 inconclusive and 8 no-meaningful-regression verdicts out of 24; the width of the 95 % interval of a tail measure (p95, p99, max) is 0.13-0.56 (median 0.34) in the A/A and 0.07-0.73 (median 0.27) in the Stage 6 against Stage 5 series; the widest A/A interval is habitat+research orbit max: ratio 0.919 [0.617, 1.179] between identical builds. This limits what the measurement can decide: with 12 pairs on this machine a tail measure cannot be separated from a 5 % effect even for identical builds, so a 5 % non-regression of the tails **cannot be confirmed here**. It does not show that the differences between Stage 5 and Stage 6 are noise, and it does not show that no regression exists. As a rough scale (the interval narrows with the square root of the number of pairs) bringing a tail interval within 5 % would take several times as many pairs, perhaps ten times; this was not run.

**Verdict, Stage 6 against Stage 5.** No performance regression meeting the pre-set criterion was detected in any of the 48 measures of the final series; for 10 measures a 5 % or larger degradation is excluded by that criterion, and 38 measures are inconclusive (the A/A control shows a comparable uncertainty for the tail measures under these conditions, so a 5 % non-regression cannot be confirmed for them). The first series flagged habitat static p99 once (ratio 1.284 [1.126, 1.727]); in the final series that measure is 1.163 [0.946, 1.526], inconclusive. The overall verdict is **INCONCLUSIVE**; it is not NO_MEANINGFUL_REGRESSION and is not changed by the above. What the data and the render counters support: 6 of the 12 frame-time medians are shown not to be a 5 % regression and the others are inconclusive; the counters that decide the render cost (draw calls, triangles, geometry uploads, programs built, LOD switches, visibility flips) are identical or within the table below. A cost of the repair view of the order of 10-20 % at the tail is **not excluded**.

<!-- first Stage 6 series (kept) -->





#### The first Stage 6 series

**Method.** The Stage 5 build (`1d1e331`, port 3034) and the Stage 6 build (this tree, port 3031) were measured **interleaved in time**, the order alternating each repetition, balanced tier, 150 frames, 1672 x 808, headless Chromium on the GPU, the preview browser pane closed, nothing built during a run. Conditions: habitat and overview (static, orbit), and with the UI open:
the RESEARCH tab (`+research`), the technical sheet (`+technical`), the RESEARCH tab with a **repaired run, the repair panel and the recovery map** (`+repair`), the technical sheet with the **repair figure and the repair layers** (`+repairtech`). A build without the repair view ignores the repair parameters, so for Stage 5 the same URLs measure the research tab / technical sheet without a repair; the difference is the cost of what Stage 6 adds.
Same rule as for Stages 4 and 5, fixed before any of this data: paired ratio per repetition, 95 % bootstrap interval (10 000 resamples, fixed seed); *regression* if the lower bound exceeds 1.05, *no meaningful regression* if the upper bound is below 1.05, otherwise *inconclusive*. Mean FPS is not used.

**The machine was not idle.** The load average at the start of each run is in `perf_stage6/paired/*.load`; three of the 18 runs began at a load of 9-16 (3031_4: 10.86, 3031_7: 9.98, 3034_1: 8.98, 3034_3: 16.42); the others at 3.4-7.3.

| analysis | repetitions | all 48 measures (6 conditions x static/orbit x median/p95/p99/max) |
|---|---|---|
| **planned** (repetitions 1-6, fixed in advance) | 6 | 1 regression, 0 no meaningful regression, 47 inconclusive |
| **extended** (three more repetitions, 7-9, added because the planned ones were noisy) | 9 | 0 regression, 3 no meaningful regression, 45 inconclusive |
| sensitivity: without the repetitions that contain a high-load run (1, 3, 4) | 6 | 0 regression, 8 no meaningful regression, 40 inconclusive |

**The one flag of the planned analysis is kept:** habitat static p99: 27.05 ms -> 41.65 ms, ratio 1.284 [1.126, 1.727]. It is a 99th-percentile of 150 frames in the plain habitat condition, where the render counters of the two builds are identical (below) and no Stage 6 UI is open; it did **not** reappear with three more repetitions or without the high-load runs. It is reported, not removed, and not explained.

Median and p95, extended analysis (9 repetitions); all measures are in `docs/ecosystem/perf_stage6/paired/analysis_tables.md`:

| condition | mode | measure | Stage 5 (ms) | Stage 6 (ms) | paired ratio S6/S5 | 95 % CI | verdict |
|---|---|---|---|---|---|---|---|
| habitat | static | median | 18.5 | 19.1 | 1.038 | [0.935, 1.108] | inconclusive |
| habitat | static | p95 | 23.8 | 25.4 | 1.043 | [0.921, 1.324] | inconclusive |
| habitat | orbit | median | 20 | 20.1 | 0.98 | [0.911, 1.052] | inconclusive |
| habitat | orbit | p95 | 29.8 | 30.4 | 0.973 | [0.884, 1.289] | inconclusive |
| habitat+repair | static | median | 16.6 | 16.3 | 0.975 | [0.791, 1.11] | inconclusive |
| habitat+repair | static | p95 | 24.2 | 20 | 0.952 | [0.723, 1.049] | no meaningful regression |
| habitat+repair | orbit | median | 16.1 | 16.6 | 1.026 | [0.808, 1.16] | inconclusive |
| habitat+repair | orbit | p95 | 22.5 | 25.7 | 1.058 | [0.899, 1.206] | inconclusive |
| habitat+repairtech | static | median | 16.4 | 16.4 | 0.994 | [0.777, 1.031] | no meaningful regression |
| habitat+repairtech | static | p95 | 25.1 | 21.6 | 0.869 | [0.689, 1.296] | inconclusive |
| habitat+repairtech | orbit | median | 15.8 | 16.2 | 1.013 | [0.778, 1.071] | inconclusive |
| habitat+repairtech | orbit | p95 | 23 | 24.3 | 1.046 | [0.652, 1.238] | inconclusive |
| habitat+research | static | median | 16.5 | 16.4 | 0.958 | [0.873, 1.044] | no meaningful regression |
| habitat+research | static | p95 | 22.3 | 18.7 | 0.889 | [0.751, 1.291] | inconclusive |
| habitat+research | orbit | median | 16.3 | 16.4 | 1.0 | [0.871, 1.059] | inconclusive |
| habitat+research | orbit | p95 | 25 | 24.2 | 1.07 | [0.745, 1.114] | inconclusive |
| habitat+technical | static | median | 16.5 | 16.5 | 1.0 | [0.811, 1.531] | inconclusive |
| habitat+technical | static | p95 | 19.7 | 20.4 | 0.995 | [0.638, 1.855] | inconclusive |
| habitat+technical | orbit | median | 16.4 | 16.9 | 0.982 | [0.84, 1.306] | inconclusive |
| habitat+technical | orbit | p95 | 25.6 | 25.5 | 0.926 | [0.789, 1.505] | inconclusive |
| overview | static | median | 15.9 | 15.9 | 0.962 | [0.878, 1.118] | inconclusive |
| overview | static | p95 | 21.5 | 18.2 | 0.805 | [0.558, 1.364] | inconclusive |
| overview | orbit | median | 17.9 | 17.6 | 0.983 | [0.9, 1.067] | inconclusive |
| overview | orbit | p95 | 26.8 | 27 | 1.012 | [0.887, 1.474] | inconclusive |

Render counters (median over the repetitions; geometry uploads, programs built, LOD switches and visibility flips are from the orbit's per-frame series):

| condition | build | draw calls | triangles | geometry uploads | programs built | LOD switches | visibility flips |
|---|---|---|---|---|---|---|---|
| habitat | stage5 | 428 | 1065364 | 35 | 0 | 144 | 28 |
| habitat | stage6 | 428 | 1065364 | 35 | 0 | 142 | 28 |
| overview | stage5 | 457 | 674384 | 21 | 0 | 145 | 64 |
| overview | stage6 | 457 | 674384 | 21 | 0 | 145 | 64 |
| habitat+research | stage5 | 385 | 989152 | 38 | 0 | 144 | 28 |
| habitat+research | stage6 | 385 | 989152 | 38 | 0 | 141 | 28 |
| habitat+technical | stage5 | 385 | 989152 | 38 | 0 | 143 | 28 |
| habitat+technical | stage6 | 385 | 989152 | 38 | 0 | 141 | 28 |
| habitat+repair | stage5 | 385 | 989152 | 38 | 0 | 144 | 28 |
| habitat+repair | stage6 | 385 | 989288 | 38 | 0 | 144 | 28 |
| habitat+repairtech | stage5 | 385 | 989152 | 38 | 0 | 142 | 28 |
| habitat+repairtech | stage6 | 385 | 989288 | 38 | 0 | 143 | 28 |

**Verdict of the first series (the final series above states the verdict of this section): no performance regression meeting the criterion was detected, and for most measures the data cannot decide.** In the extended and the low-load analyses no measure is a regression; in the planned analysis one tail measure was (above). Most intervals are wide (the benchmark was run on a shared machine): the cost of the repair view, the recovery map and the repair figure cannot be separated from the variation of the measurement at this sample size, so a cost of a few percent to
tens of percent is **not excluded** for the repair and technical conditions. The stage itself is unchanged: draw calls, triangles, geometry uploads, programs built (0 during an orbit), LOD switches and visibility flips are the same in the two builds, except 136 more triangles in the two conditions that open a repaired run (the run's state differs from the unrepaired one; the cause is not investigated). The update cost of the repair overlay itself is not measured separately.

## 24. Regression

All of it was run on the final tree of the final commit (the Python code, the tests, the interface and the saved results were last changed before these runs; the document and its fragments are generated from the saved results and are checked by a test).

| check | result |
|---|---|
| backend `pytest` (whole suite, one run on the final source) | 807 tests: 805 passed, 2 failed (the two known failures below; `evidence/meos_stage6.junit.xml`) |
| the two known failures | `tests/test_compat.py::test_engine_conformance_against_the_golden_fixture[desktop-scipy]` and `tests/test_lab.py::test_published_records_replay`: same test names and same failure messages as in the baseline record (`evidence/meos_stage4.junit.xml`, compared by name and message text), at Stage 5 and at the earlier Stage 6 commits. Neither concerns MEOS-0 or Stage 6; they were not changed or skipped |
| frontend `vitest` | 276 tests, 0 failures, 0 errors (`evidence/frontend_stage6.junit.xml`) |
| `tsc -b`, `eslint`, `vite build` | no errors |
| `ruff`, `mypy` on the MEOS code (`xzr/meos`, `xzr/service/meos.py`, the Stage 6 scripts and tests) | no findings. The whole-repository run reports `ruff` and `mypy` findings in older modules (`hpo`, `study`, `totalobs`, `lab`, `experiments/results`) that this work does not touch; they are not caused by Stage 6 and were not fixed here |
| replay of the 264 stored runs | 264 / 264 agree on `meos-0.5` (`evidence/replay_meos_stage6.json`, re-run on the final source: 362 s). The runs were not regenerated |
| baseline result digest | `b4cf1e522e8bee460eab30ee2a3f86ffd703a3f7969dc21271cf0240aa09adc5`, unchanged on `meos-0.5` (`tests/test_meos_stage5_engine.py`) |
| baseline trace digest | `bd3e588608139840831c2749b5051ac31a360d91c6a9a0131b9de3f0152ee1b7`, unchanged |
| Stage 5 reproduction (`reproduce_stage5_subset.py`), run on `meos-0.5` | identical: experiment L (history lost), F14 search and its digests, F8 search, F9 search, the first adaptive decisions, the Stage 4 strict nulls (Address collision, stale), the two digests |
| Stage 6 reproduction (`reproduce_stage6_subset.py`), run on `meos-0.5` | identical: 4250 / 4250 rows of the exploration grid, the per-tick window of the coupling pulse, 36 / 36 controller runs (`all_identical: true`) |
| stored MEOS fixtures | covered by the backend and frontend suites above (the Stage 6 fixture is used by `repair.test.ts` and `RepairPanel.test.tsx`) |
| engine version | `meos-0.5`: the three opt-in mechanisms of the follow-up (section 30); `meos-0.4` for every result file written before it, which `meos-0.5` reproduces bit for bit |

**Tests whose expectations were changed by the follow-up (five), and why.** Each change was made because a fact the test stated changed on purpose; none removes an assertion that guarded something still true, and none uses a looser tolerance, a skip or an expected failure.

| test | old expectation | new expectation | basis (not the value the new code returned) | kind of change |
|---|---|---|---|---|
| `test_meos_stage5_engine.py::test_the_baseline_digest_and_the_version` | `ENGINE_VERSION == "meos-0.4"` | `"meos-0.5"`; the baseline result digest `b4cf1e52...` and the absence of the `m2_sensed` trace are asserted exactly as before | the version string moved when the opt-in mechanisms were added; that a default run is unchanged is shown by the unchanged digest assertion in the same test and by the reproduction runs on `meos-0.5` (Stage 5 and Stage 6 subsets, 264 replay) | version label; protection kept |
| `test_meos_stage6_repair.py::test_the_action_space_names_what_the_main_experiments_could_not_do_and_never_runs_it` | the three actions are "not implemented" in the registry **and** `build_action` raises `ValueError` for them | the frozen registry still says "not implemented" (and they are not in `RUNNABLE`); the follow-up registry builds them; `ValueError` is asserted for an observation action (class C), which is never an action of a run | the three actions were built in `meos-0.5` in their own registry (`repair6.FOLLOWUP_LIST`); the frozen Stage 6 registry was deliberately not edited | scope (action space) change; protection kept and extended |
| `test_meos_stage6_results.py::test_an_open_window_is_open_through_the_tested_limit_and_has_no_irreversible_tick` | three stresses are `OPEN_THROUGH_TESTED_LIMIT` with null `irreversible_tick`; the other three are closed at 110, 112, 121 | the **rule** is still asserted on the saved Pipeline B windows as they were before the extension (three open at tick 330, null `irreversible_tick`); after the extension the same three stresses are closed at `latest + 1` (388 / 383 / 383 + 1); the final table is closed everywhere | the extended-horizon measurement (`experiments_stage6_open_windows.json`, ticks 331-1140); the new test `test_the_closure_ticks_are_recomputed_from_the_per_tick_results_and_the_energy_gate_explains_them` recomputes the last effective tick from the per-tick counts and checks the closure against A1's energy from the traces | evaluation range extended |
| `test_meos_stage6_results.py::test_every_cell_of_the_grid_is_in_the_csv_whatever_its_outcome` | the results CSV has three `OPEN_THROUGH_TESTED_LIMIT` rows with an empty irreversible tick | six `CLOSED` rows with 389, 110, 112, 384, 384, 121; the assertions on the cells CSV (every cell kept, failures outnumber successes) are unchanged | the regenerated final table | evaluation range extended |
| `test_meos_stage6_service.py` (the refusal test) | `coupling.bypass` is refused with 422 | an action nobody built (`coupling.nope`) is refused with 422; `resource.rerouting` is accepted | the follow-up registry; class C and over-long action lists are still refused with the assertions unchanged | scope change; protection kept |

A sixth change was an error and was corrected: the test that the three open windows were measured to tick 330 was dropped by mistake when the open-window test was rewritten; it was restored and extended to check the 331-1140 measurement (it is in the whole-suite run above). The document-consistency test was not edited; it failed until the document was regenerated, as designed.

Tests added by the follow-up: `tests/test_meos_stage6_followup.py` (the three mechanisms, their validation, that the fault modes are not extended), the closure test named above, and the checks that the regenerated validation and evaluation rows give the saved summaries (section 8, below).

**What was re-executed, and what is only a saved summary (reproducibility scope).** Different things were checked and they are not interchangeable:

| evidence | what is stored | what was re-executed, and result |
|---|---|---|
| the 264 stored runs (older study engines, not MEOS runs) | the stored study records | **all 264** replayed on the final tree: 264 / 264 agree |
| Pipeline A exploration (seeds 1-5) | **every run** (`experiments_stage6_raw.jsonl.gz`, `_raw_combined`, `experiments_stage6_followup_raw.jsonl.gz`) | the exploration grid of the main experiments: 4250 of 4250 rows re-executed by `reproduce_stage6_subset.py` are identical (a subset of the grid) |
| Pipeline A and follow-up validation (6-10) and evaluation (11-30) | originally the summaries only (counts, Wilson rates, outcome counts) | **every setting that has such a summary was run again** (265 settings, 6475 runs, fixed settings, seeds and criterion) and every one gives the saved counts (`evidence/run_rows_verification.json`; 0 mismatches); the run-level rows are saved in `experiments_stage6_validation_evaluation_rows.jsonl.gz` and are marked as **regenerated** (date, engine, commit of the tree in the first line), not original records |
| Pipeline B windows, ticks 101-330 | per-tick counts (exploration and validation), not per-run rows | the coupling pulse window re-executed tick by tick (identical); the other windows were **not** re-executed one by one |
| the three windows, ticks 331-1140 | per-tick counts | the ticks around each closure and a sample of later ticks re-executed at run level (`experiments_stage6_open_mechanism.json`: 10 seeds per tick, energy, firing, latency); ticks 300-330 of the extended run agree with the saved windows |
| controllers | raw rows (`experiments_stage6_controllers_raw.jsonl.gz`) | 36 of the 36 runs of the reproduction subset identical |
| MFS / SSS / observation readings (C1-C4), performance | summaries; timing measurements | not re-executed (the timings are not reproducible by construction; the readings were not re-run) |

The seed sets were fixed before the runs (exploration 1-5, validation 6-10, evaluation 11-30), settings were chosen from the exploration rows only, and the validation and evaluation seeds were not used to choose; the follow-up used the same seed sets for the new actions. A seed set that has been looked at is not an independent confirmation of a design changed afterwards, and none of the results above was selected on the validation or evaluation seeds.

What this does not show: the reproduction scripts re-run a subset (they are not a re-run of every Stage 6 row); the full results were produced once, and the saved raw rows are for seeds 1-5 only (the other seeds are saved as the summaries derived from them).

## 25. Failed hypotheses

These hypotheses did **not** hold (or held only in part), and are kept:

1. **Restoring the original parameter alone restores the system.** It does not, once the damage has set in: the coupling restored to 1.0 at tick 113 recovers 0 of the seeds, restoring the efficiency to 0.9 or less is not enough, restarting a stopped renewal alone is never effective, restoring the Address alone is null at every tested tick (the Address integrity returns, the operation does not). The *rule-based* controller, which does exactly this, recovers 0 of 20 on the coupling stress.
2. **The repair site is the damage site.** For the coupling stress the effective late repair is a resource pulse; the coupling itself is not the lever.
3. **A stronger intervention is at least as good.** A resource pulse recovers the coupling stress between 0.6 and 2.5 and **re-collapses above 2.6**; a pulse alone on history lost gives only a transient recovery.
4. **Every stress has an effective action.** At the decision tick (113) none of the tested actions, alone or in the tested pairs, validates for the resource, the renewal-efficiency or the renewal-stopped stress; for the Address stress the best combined repair is a near miss.
5. **A cost-aware (adaptive) controller outperforms a known fixed repair.** On the coupling stress the fixed pulse chosen beforehand equals it (20/20 each); on history lost it equals the rule-based controller; on the Address stress it is **worse** than the simple rule (0 of 20 against 8 of 20), because its strictly validated library holds no Address action.
6. **A delay is harmless.** The same cost-aware controller 15 ticks later recovers 9 of 20 where the prompt one recovers 20 of 20 on the coupling stress (the windows are timing-limited).
7. **Unknown-stress generalization.** It failed for the stronger coupling drop (0 of 20 for every controller) and for the renewal and resource variations; it held for the tested weaker drop and later onset of the coupling stress.
8. **A recovery detected by the controller is a skill.** The few recoveries of the noisy controller on history lost are the accidental result of a false detection that acted early.
9. **The first criterion (all three horizons at every tick) was sound.** It was not: it made every repair after tick 120 impossible by construction and hid the repairs that recover after the collapse. It was corrected after the one-tick results showed it; the first results are kept beside the corrected ones (section 6).
10. **The end of the tested range is a closure.** The first derived table reported the latest successful tick as 330 and the irreversible tick as 331 for three stresses. 330 is the last tick that was tested, not a place where recovery closed; those windows were recorded as `OPEN_THROUGH_TESTED_LIMIT` with `irreversible_tick` null until they were measured on to tick 1140 with the extended horizon. They then closed, at ticks 389 (coupling), 384 (renewal stopped) and 384 (Address), not at 331 and not at the end of the range (section 29).
11. **After the collapse nothing recovers.** It did for three stresses: a pulse-based repair (alone on the coupling stress, with a restart or an Address restoration on the others) recovers at every tested tick after the collapse, to tick 388 / 383 / 383. The earlier reading was an artefact of the first criterion (section 6).
12. **The closure of the late windows is a property of the horizon.** The data do not support it: with the extended horizon the closure is found at a state-determined tick (A1's energy at the start of the intervention tick must reach its firing cost) that is the same on every seed of a window, and with A1's upkeep set to 0 after a common history the same pulse recovers the run at each of the ticks tested (to 1140) (section 29). The closure is a statement about the measured settings, not a proof of irreversibility.
13. **A repair needs A1 to fire a few times first, so the Address and renewal windows close earlier.** Withdrawn: A1 fires at the intervention tick itself on every recovering run; the differences of 5 ticks come from A1's energy at tick 300 (0.10 apart, upkeep 0.02 per tick), whose own cause was not traced.

## 26. Null results (kept)

- No pulse of 0.1-6.0 recovers the resource, the renewal-efficiency or the renewal-stopped stress at tick 113 (section 11); a pulse alone on history lost gives a transient recovery and then a secondary collapse.
- The restoration of the Address alone, the restart of the renewal alone, the temporary bridge of the coupling, the temporary renewal boost: no effective tick (sections 9, 12, 13).
- The controllers on the renewal and resource stresses, and on the stronger coupling drop: 0 of 20 (section 15, 17).
- Stage 4's strict nulls are unchanged.
- The raw rows of every run are kept: `experiments_stage6_raw.jsonl.gz` (12390 rows), `experiments_stage6_raw_combined.jsonl.gz`, `experiments_stage6_controllers_raw.jsonl.gz`; the results of the first criterion are kept beside the corrected ones.

## 27. Limitations

- The action space is limited to what MEOS-0 can do: the local bypass, the transport rerouting and the temporary local Address were not implemented in the main experiments and were built afterwards (section 30), as minimal mechanisms of this study; redistribution and the reserve release are proxies (section 4).
- The tick grid is finite (one-tick resolution only for the settings measured at that resolution; ticks 101-170, a coarse grid to 200); the horizons are finite (180, 300, 480); the seeds are few (5 + 5 for each setting, 20 for evaluation) and the engine's seed-to-seed variation is small, so proportions are near 0 or 1.
- The repair cost model is synthetic (measured from the model's own traces, equal-weight only where an order is needed). The environment model is synthetic. No claim is made about real ecosystems.
- The controllers sense five features; four stresses give the same signature, so the controller cannot tell them apart and tries plans in turn.
- Unknown-stress coverage is limited to the variations listed; generalization is shown, where it is, only for those.
- The MFS and SSS readings use the repairs validated on the full arrangement, on 5 and 3 seeds, and an island of a 3 x 3 grid.
- Repairability is conditional on the tested model, version, action space, ticks and horizons: a stress called unrecoverable here is unrecoverable *under the tested actions*.

## 28. Remaining work

**Unimplemented**
- Real redistribution and reserve release (only proxies). The bypass, the rerouting and the temporary local Address were built afterwards (engine meos-0.5, section 30) as minimal mechanisms of this study; other realisations would be other actions. An action that restores A1's energy does not exist in the engine (section 29).
- A repair controller that learns from its own attempts across runs, or one that uses more than the five sensed features.
- Search over the order of two repair actions and over three or more at once (pairs at the same tick only).
- Combined *stresses* (two stresses at once) and their combined repairs.

**Unverified**
- Whether a window closed by the exhaustion of A1's energy (coupling 389, renewal stopped 384, Address 384) could be reopened: no action of the tested space adds energy to A1 and none exists in the engine; the closure is a statement about the tested actions (section 29).
- Whether the new actions of section 30 have windows of their own beyond tick 330 on the stresses where they act only in combination: the combined repairs were measured at ticks 113, 120 and 130 only.
- Whether more seeds would turn the near misses (the Address restoration with a pulse at the decision tick; M2 and its neighbours at tick 114-118) into validated settings or reject them.
- Windows beyond the one-tick range for settings not measured at one-tick resolution; settings outside the grids of magnitudes and durations.
- The fragmentation of the timing windows (gaps inside a window) is recorded, not explained.
- The repairability of the MFS and the SSS grid on independent validation seeds (they use exploration seeds 1-5 and 1-3).

**Partial**
- Unknown-stress evaluation: the variations listed, not a general family of stresses.
- Observation repair: tested as a change of the observer on recorded runs, not as part of a controller.
- The cost model: raw and normalised measurements of the model's traces; no weighted objective was optimised.

## 29. Windows open at tick 330, measured on (follow-up)

**What is closed, and for what.** The first tested range ended at tick 330 because the long horizon (480) leaves room for 60 ticks only up to tick 420. Three single-setting windows (A in section 8: the last effective tick of one setting) were still effective there. They were run again with the longest horizon the engine accepts (1200), at every action tick from 331 to 1140, on seeds 1-10, with the same criterion plus success at the extended horizon (`experiments_stage6_open_windows.json`; ticks 300-330 of the extended run agree with the saved windows). The stress-level `irreversible_tick` of section 7 (B) is the union over the settings that were window-measured for that stress; for these three stresses the later windows of the other settings had closed earlier, so B equals A for the three settings below.

| stress | setting (the window that was open at 330) | action ticks tested | effective ticks | latest effective tick | first tick not effective | exploration / validation at that tick | near-miss ticks |
|---|---|---|---|---|---|---|---|
| coupling weakened (gain 0.5) | resource.pulse 1.0 | 331-1140 | 331-388 | 388 | 389 | 0/5 / 0/5 | 0 |
| Address degraded (A2 partial 50 %) | address.restore + resource.pulse 1.0 | 331-1140 | 331-383 | 383 | 384 | 2/5 / 3/5 | 0 |
| renewal stopped (feedback removed) | renewal.restart + resource.pulse 1.0 | 331-1140 | 331-383 | 383 | 384 | 0/5 / 0/5 | 0 |

The effective ticks of each window are contiguous from tick 331 to the last effective tick and none is effective after it (the intervals above; in the earlier range the windows are fragmented, e.g. the coupling pulse is effective at 108-117 and again from 125, and the closure is the tick after the **last** effective tick, not the first failure). The post-intervention period differs between ticks (tick 1140 leaves 60 ticks of the run, tick 388 leaves 812); this does not affect the finding, as the next two paragraphs show.

**Why it closes (the energy gate).** The saved runs (seeds 1-10, `experiments_stage6_open_mechanism.json`; the engine's tick convention: an intervention scheduled at tick t is applied at the start of step t, A1's firing check in step t uses the energy at the end of step t-1, the upkeep is taken at the end of a step) give one rule for all three windows: **the repair works when A1's energy at the start of the intervention tick is at least its firing cost (0.3), and not otherwise.**

| window | intervention tick | A1 energy at the start of that tick (over seeds) | recovered at tick 1200 | sustained ACTIVE (30 ticks) within 60 ticks of the intervention | first A1 firing (median) | A1 firings in the next 60 ticks | longest latency of a recovery | ticks tracked after the intervention |
|---|---|---|---|---|---|---|---|---|
| coupling gain 0.5 | 388 | 0.3-0.3 | 10/10 | 10/10 | 388.0 | 12.0 | 10 | 812 |
|  | 389 | 0.28-0.28 | 0/10 | 0/10 | none | 0.0 | - | 811 |
| renewal stopped | 383 | 0.3-0.3 | 10/10 | 10/10 | 383.0 | 12.0 | 10 | 817 |
|  | 384 | 0.28-0.28 | 0/10 | 0/10 | none | 0.0 | - | 816 |
| Address partial 0.5 | 383 | 0.3-0.4 | 10/10 | 10/10 | 383.0 | 12.0 | 10 | 817 |
|  | 384 | 0.28-0.38 | 5/10 | 5/10 | 384 | 6.0 | 10 | 816 |

At the last effective tick A1's energy is 0.3 (the cost) on every seed (the Address windows: 0.3-0.4, because the seeds differ by 0.1) and A1 fires **at the intervention tick itself**; one tick later the energy is 0.28 and no A1 firing follows. On the Address stress the seeds with the higher energy keep recovering: the pair is effective on all seeds up to tick 383, on 5 of 10 seeds from 384 to 388, and on none from 389 (the rule of this study for an *effective* tick requires all seeds; both statements are in the data). The unrepaired coupling run's end-of-step energy falls below the cost at tick 388 on every seed, which is the same event seen from the other side (a pulse at tick 388 is applied at the start of step 388, which still has 0.30).

**Why the ticks differ (389, 384, 384).** Upkeep is 0.02 per tick, so a difference of 0.10 in A1's energy is 5 ticks. With the history identical to the unrepaired run up to tick 300, A1's energy at the start of a late intervention is determined by its energy at tick 300 and the upkeep: it is 2.04 in the coupling run, 1.94 in the renewal-stopped run and 1.94-2.04 in the Address runs (the cost is reached after (E-0.30)/0.02 further ticks: 87, 82 and 82-87), which reproduces 388 / 383 / 383 as the last effective ticks. What this does **not** explain is why A1 has 0.10 less energy at tick 300 in the renewal-stopped and Address runs than in the coupling run: that comes from the history of each stress (how often A1 fired before and during the collapse) and was not traced further. The statement that the repair needs A1 to fire a few times first, made in an earlier version of this section, is not supported by these traces and was withdrawn: A1 fires at the intervention tick on every recovering run.

**Controls that change the model (not repair actions).** (a) *Common history, then upkeep 0*: the run is the same as the unrepaired run up to tick 300 (so the damaged, collapsed state and A1's energy at tick 300 are the same), then A1's upkeep is set to 0 and the same intervention is applied later. (b) *Upkeep 0 from the initial configuration*: the first version of this control; the history differs (A1 never loses energy, it stays at 6.0), so it is not a repair of the same damaged state and is kept only for comparison.

| window | A1 energy at the start of the intervention in (a) | recovered at 1200, (a) common history to tick 300, upkeep 0 after it | recovered at 1200, (b) upkeep 0 from the start (some ticks) |
|---|---|---|---|
| coupling | 2.04-2.04 | 387: 10/10, 388: 10/10, 389: 10/10, 394: 10/10, 500: 10/10, 800: 10/10, 1140: 10/10 | 387: 10/10, 388: 10/10, 389: 10/10, 1140: 10/10 (A1 energy 6.0) |
| renewal stopped | 1.94-1.94 | 382: 10/10, 383: 10/10, 384: 10/10, 389: 10/10, 500: 10/10, 800: 10/10, 1140: 10/10 | 382: 10/10, 383: 10/10, 384: 10/10, 1140: 10/10 (A1 energy 6.0) |
| Address | 1.94-2.04 | 382: 10/10, 383: 10/10, 384: 10/10, 389: 10/10, 500: 10/10, 800: 10/10, 1140: 10/10 | 382: 10/10, 383: 10/10, 384: 10/10, 1140: 10/10 (A1 energy 6.0) |

The controls show that, for these three repairs, the closure depends on the energy of A1 and on nothing that the pulse could change: with the energy kept, the same pulse recovers the run at each of the ticks tested in the table above (seven per window, from just before the closure to tick 1140). They do not show that the closure is the only mechanism of irreversibility in the model, that A1's upkeep is the only way to keep A1's energy, or that the repair would be possible in a system that is not this model.

**Post-intervention tracking.** Every intervention tick tested is at most 1140, so every run is followed for at least 2W = 60 ticks after it, the minimum the criterion requires (a horizon is applicable only if it leaves 2W ticks). No run is classified as *insufficiently tracked*: none is excluded or counted as a failure for lack of time. To make the comparison across ticks independent of the end of the run, the same runs were also judged by one criterion that is the same for every tick: *ACTIVE for W = 30 consecutive ticks within 2W = 60 ticks of the intervention*; it agrees with the recovery at tick 1200 on every sampled tick of the table above (the two columns are equal), and the longest latency of any recovery is 10 ticks, far below the 60 ticks that every late run was followed. The failures after the closure are runs in which A1's energy is below its firing cost (at tick 400 and later it is 0.06 or less): they do not depend on how long the run is followed.

**Limits of the statement.** The windows are closed **for these settings** (a resource pulse of 1.0, alone or after an Address restoration or a renewal restart), in the tested tick range, on seeds 1-10, at the stated criterion. No action that restores A1's energy exists in the engine, so whether the stress is recoverable by such an action is untested and not claimed either way. This is not a proof of irreversibility of the modelled system and not a claim about any real system.

## 30. The three actions that were not built (follow-up, engine meos-0.5)

Engine `meos-0.5` adds three opt-in mechanisms (absent from every earlier configuration, so every earlier run is the same run: section 31). The frozen Stage 6 registry still records the three actions as not implemented; they are in their own registry (`repair6.FOLLOWUP_LIST`) and every Stage 6 result above is the result in the original action space.

| action | what it does in the engine | magnitude | durations | declared cost | note |
|---|---|---|---|---|---|
| coupling.bypass | bypass of the damaged coupling: a second path for A1's alteration to reach A2 | share of the peak of A1's own sensing window that reaches A2 (absent = 0): [0.25, 0.5, 0.75, 1.0] | - | switching: 1 RECONFIGURE | engine meos-0.5: A2's stimulus is max(gain x peak of its window, bypass x peak of A1's window); the coupling itself stays damaged |
| resource.rerouting | transport rerouting: a conduit from the source edge of the resource gradient to A1's cell, for a duration | share of the source cell moved to A1's cell per tick: [0.25, 0.5, 1.0] | [10, 30, 100] | resource: moved, not added; switching: 1 ALTER_RESOURCE | engine meos-0.5: resource is moved from (0, 6) to (3, 6) each tick; the total is conserved by the conduit itself |
| address.temporary_local | temporary local addressing: A2 is fully addressable for a duration, then its address state returns | - | [10, 30, 100] | switching: 1 ADDRESS | engine meos-0.5: ADDRESS mode temporary; a later address intervention ends it at once |

Protocol: that of Pipeline A and B (exploration seeds 1-5, validation 6-10, evaluation 11-30, the same criterion, the same eight action ticks, a combined repair counts only where neither part is effective alone). 3240 single runs; 2235 combined runs.

**Single actions** (55 candidates, 55 validated, 3 near misses):

| stress | action | validated settings | near misses | minimum validated magnitude (ticks) |
|---|---|---|---|---|
| coupling weakened (gain 0.5) | coupling.bypass | 2 | 0 | 0.75 (ticks [104]; durations [0]) |
| coupling weakened (gain 0.5) | resource.rerouting | 53 | 3 | 0.25 (ticks [104, 108, 113, 120, 130, 140, 160, 200]; durations [10, 30, 100]) |

Windows (one tick, 101-170, on to 330 where open at 165 or later):

| stress | setting | ticks tested | effective ticks | near-miss ticks |
|---|---|---|---|---|
| coupling weakened (gain 0.5) | coupling.bypass 0.75 | 101-170 | 101-104 | none |
| coupling weakened (gain 0.5) | coupling.bypass 1.0 | 101-170 | 101-105 | none |
| coupling weakened (gain 0.5) | resource.rerouting 0.25 (for 10) | 101-170 | 104-114 | 115, 116, 117, 118, 124 |
| coupling weakened (gain 0.5) | resource.rerouting 1.0 (for 100) | 101-330 | 102-259 | 260, 261, 262 |

**Combined repairs with a new action** (a primary of Stage 6 with one setting of a new action; 140 candidates, 133 validated, 81 synergistic, 20 near misses):

| stress | validated and synergistic | validated, not synergistic (one part alone is effective) | near miss | failed validation |
|---|---|---|---|---|
| coupling weakened (gain 0.5) | 1 | 39 | 2 | 0 |
| resource reduced (regrow 0.01, charge 0.2) | 0 | 0 | 0 | 0 |
| renewal efficiency 0.6 | 16 | 0 | 7 | 2 |
| renewal stopped (feedback removed) | 18 | 0 | 0 | 0 |
| Address degraded (A2 partial 50 %) | 37 | 0 | 5 | 0 |
| history lost | 9 | 13 | 6 | 0 |

**Repairability, in the action space of Stage 6 and in the extended one** (grid classification of Pipeline A/follow-up at the tick named; the window-based classification of section 7 is unchanged):

| stress | at tick 113: Stage 6 action space | at tick 113: extended | any tested tick: Stage 6 action space | any tested tick: extended |
|---|---|---|---|---|
| coupling weakened (gain 0.5) | externally repairable | externally repairable | externally repairable | externally repairable |
| resource reduced (regrow 0.01, charge 0.2) | neither (under the tested actions) | neither (under the tested actions) | internally reconfigurable | internally reconfigurable |
| renewal efficiency 0.6 | neither (under the tested actions) | externally repairable | both | both |
| renewal stopped (feedback removed) | neither (under the tested actions) | externally repairable | externally repairable | externally repairable |
| Address degraded (A2 partial 50 %) | inconclusive | externally repairable | inconclusive | externally repairable |
| history lost | internally reconfigurable | internally reconfigurable | both | both |

Reading. (1) Alone, only `resource.rerouting` and `coupling.bypass` recover anything, and only the coupling stress; rerouting works over a long range of ticks with a large rate and a long duration, the bypass only early. (2) On the other stresses the new actions recover the run only together with a restoration of the damaged parameter (the Address restoration, the renewal restart or restore, the M2 tap): a combined recovery, credited to the combination. (3) The temporary local Address alone does nothing, as the permanent restoration alone did nothing (section 13): the Address is not the only thing that has to be restored. (4) The extended action space changes the class of the renewal-efficiency, the renewal-stopped and the Address stresses **at tick 113**; it does not change the class of the coupling, the resource or the history-lost stresses, and it opens no window for the resource stress. These changes are consequences of a larger action space (the same stress, the same criterion, more actions), not corrections of the earlier judgments: "neither (under the tested actions)" in sections 7 and 9 remains true of the action space that was tested there, and the earlier Stage 4-6 results (the multiple MFS of F14, the rejected candidate of F8, the absent set of F9, the null results of Address collision and stale, the negative result of the first adaptive controller, the M2 route of experiment L) are conditions of their own model version and action space and are not overwritten. (5) `resource.rerouting` moves resource, it does not add it; its effect on the source cell (0, 6) is a side effect that is not scored beyond the collateral cost in the saved rows. The mechanisms are minimal choices of this study (a peak-tap bypass, a point-to-point conduit, a bounded full addressability), not claims about a real system, and other realisations of the same names would be other actions.

## 31. The earlier results on meos-0.5 (follow-up)

The engine version moved from `meos-0.4` to `meos-0.5` for the follow-up. The new mechanisms are absent from every earlier configuration; this was checked, not assumed, by running the earlier experiments again on `meos-0.5`:

- Stage 5 subset (`reproduce_stage5_subset.py`): all identical = True (experiment L on history lost, the F14, F8 and F9 searches with their digests, the first decisions of the adaptive controller, Stage 4's strict nulls, the two baseline digests).
- Stage 6 subset (`reproduce_stage6_subset.py`): all identical = True (4250 of the 12390 exploration rows of the main experiments, the per-tick window of the coupling pulse, 36 controller runs: a subset, see the reproducibility scope in section 24).
- The baseline result digest and trace digest are unchanged (section 24). The result files written by the engine before the change carry `meos-0.4` in their `engine` field; the runs they record are reproduced bit for bit by `meos-0.5`.
