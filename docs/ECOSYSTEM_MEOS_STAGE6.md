# XENO ECOSYSTEM — Stage 6 (MEOS-0.4): endogenous repair, world-state intervention, reachable recovery

> Which damage can internal reconfiguration handle, which needs an intervention on the state of the world, and which cannot be recovered in the action space tested here: by which action, how much of it, at which tick, at which cost, on which seeds, and to which horizon.

Everything below is a statement about a **formal model** (MEOS-0, engine `meos-0.4`, unchanged by this stage): how this engine's specified operation responds to the interventions tested. It is not evidence about any real ecosystem. A repair that works here is *conditional* on the model,
the action space, the tick grid, the horizons and the seeds. Raw data and interpretation are kept apart: the tables are copied from `docs/ecosystem/experiments_stage6*.json` by `backend/scripts/make_stage6_doc.py`; the words under them are interpretation and its limits.

## 1. Scope

Stage 5 searched **component enable/disable** (route reconfiguration) and found an action for one stress of six (history lost: the M2 tap). Stage 6 asks the question that left open: for the stresses internal reconfiguration cannot handle, **does an intervention on the world itself** (coupling, resource, renewal, Address)
recover a sustainable operation, and under what conditions? Recovery is not a flash of ACTIVE (section 6). Not changed: the baseline result digest, the 264 saved runs, every Stage 5 result.

## 2. Repository state

(pending)

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

- `coupling.bypass` (not implemented): the coupling of MEOS-0 is one scalar share of A1's alteration reaching A2; there is no spatial coupling path to bypass, so no action is built
- `resource.redistribute` (proxy): MEOS-0 has no operation that moves resource from one cell to another; diffusion is the nearest mechanism and is a proxy for redistribution
- `resource.reserve` (proxy): the power reserve is energy for A2's renewal, not the resource field: a proxy for a local reserve release
- `resource.rerouting` (not implemented): MEOS-0 has no transport network for the resource; no action is built
- `address.temporary_local` (not implemented): no engine mode gives a bounded-duration local address (the ``stale`` and ``delayed`` modes are faults, not repairs)

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
| coupling weakened (gain 0.5) | 101-105, 108-117, 124-140 | 140 / 141 | 101-105, 108-117, 124-330 | 330 / None |
| resource reduced (regrow 0.01, charge 0.2) | 101-109 | 109 / 110 | 101-109 | 109 / 110 |
| renewal efficiency 0.6 | 101-111 | 111 / 112 | 101-111 | 111 / 112 |
| renewal stopped (feedback removed) | 101-106, 121, 130-140 | 140 / 141 | 101-106, 121, 130-330 | 330 / None |
| Address degraded (A2 partial 50 %) | 101-109, 131-133, 135, 140 | 140 / 141 | 101-109, 131-133, 135, 140-330 | 330 / None |
| history lost | 101-120 | 120 / 121 | 101-120 | 120 / 121 |

Counts: 27 single candidates, 26 validated, 3 near misses; 270 combined settings (pairs of different actions at ticks [113, 120, 130]), 21 candidates, 14 validated, 6 of them synergistic (neither part effective alone at that tick), 9 near misses.
The unrepaired runs: Address degraded (A2 partial 50 %): {'failed': 5}, coupling weakened (gain 0.5): {'failed': 5}, history lost: {'failed': 5}, renewal efficiency 0.6: {'failed': 5}, renewal stopped (feedback removed): {'failed': 5}, resource reduced (regrow 0.01, charge 0.2): {'failed': 5} (all on exploration seeds; no seed recovers without a repair).

## 7. Stress-by-stress repairability

The stresses arrive at tick 100; the decision tick (the first decision of the stage 5 controllers) is 113. Classes: *internally reconfigurable*, *externally repairable* (world-state, single or combined), *both*, *neither (under the tested actions)*, *inconclusive*. "At the decision tick" asks whether a setting is effective **at tick 113**; "at any tested tick" asks whether one is effective at some tested tick (101-170 at one-tick resolution for every setting, to 330 for the windows still open at 170).
A *combined* recovery counts only at ticks where neither part is effective alone. Windows are in action ticks.

| stress | internal reconfiguration: effective ticks | world-state repair (single): effective ticks | combined repair: effective ticks | minimum effective action | all effective ticks | latest successful repair tick | earliest irreversible tick | reference repair, exploration seeds ok at short / medium / long | cost of the reference repair (equal-weight normalised) and its setting | unrepaired collapse tick | classification: at the decision tick 113 / at any tested tick |
|---|---|---|---|---|---|---|---|---|---|---|---|
| coupling weakened (gain 0.5) | none | 101-105, 108-117, 124-330 | none | coupling.gradual 1.0; coupling.restore 0.7; resource.pulse 0.5 | 101-105, 108-117, 124-330 | >= 330 (window still open at the end of the tested range) | not reached: no closure found up to tick 330 | 5/5, 5/5, 5/5 | 0.5486 (coupling.restore 1.0 @104) | 149 | **externally repairable** / **externally repairable** |
| resource reduced (regrow 0.01, charge 0.2) | 101-109 | none | none | internal.m2_tap 0.0 | 101-109 | 109 | 110 | 5/5, 5/5, 5/5 | 0.9895 (internal.m2_tap @104) | 149 | **neither (under the tested actions)** / **internally reconfigurable** |
| renewal efficiency 0.6 | 101-111 | 101-104 | none | internal.m2_tap 0.0; renewal.restore 1.0 | 101-111 | 111 | 112 | 5/5, 5/5, 5/5 | 0.6668 (renewal.restore 1.0 @104) | 149 | **neither (under the tested actions)** / **both** |
| renewal stopped (feedback removed) | none | none | 101-106, 121, 130-330 | - | 101-106, 121, 130-330 | >= 330 (window still open at the end of the tested range) | not reached: no closure found up to tick 330 | combined: see section 14 | 0.7246 (renewal.restart + resource.pulse 0.5 @130) | 144 | **neither (under the tested actions)** / **externally repairable** |
| Address degraded (A2 partial 50 %) | none | none | 101-109, 131-133, 135, 140-330 | - | 101-109, 131-133, 135, 140-330 | >= 330 (window still open at the end of the tested range) | not reached: no closure found up to tick 330 | - | - | 149 | **inconclusive** / **externally repairable** |
| history lost | 101-113 | none | 114-120 | internal.m2_tap 0.0 | 101-120 | 120 | 121 | 5/5, 5/5, 5/5 | 0.4981 (internal.m2_tap @104) | 159 | **internally reconfigurable** / **both** |

| stress | flags | failure ids over the tested grid (cells not effective) |
|---|---|---|
| coupling weakened (gain 0.5) | a window is still open at the end of the tested range (tick 330): no closure found | NO_EFFECTIVE_ACTION 306, ACTION_TOO_LATE 112, SECONDARY_COLLAPSE 12, OVERSHOOT 7 |
| resource reduced (regrow 0.01, charge 0.2) | recoverable only within a timing window | NO_EFFECTIVE_ACTION 280, ACTION_TOO_LATE 97, SECONDARY_COLLAPSE 12, OVERSHOOT 1 |
| renewal efficiency 0.6 | recoverable only within a timing window | NO_EFFECTIVE_ACTION 305, ACTION_TOO_LATE 106, OVERSHOOT 9, SEED_DEPENDENT 1 |
| renewal stopped (feedback removed) | a window is still open at the end of the tested range (tick 330): no closure found; recovered only by a combination (neither part alone) | NO_EFFECTIVE_ACTION 300, ACTION_TOO_LATE 100 |
| Address degraded (A2 partial 50 %) | a window is still open at the end of the tested range (tick 330): no closure found; near miss at the decision tick (validation 3-4 of 5), nothing effective there; recovered only by a combination (neither part alone) | NO_EFFECTIVE_ACTION 278, ACTION_TOO_LATE 102, OVERSHOOT 16, SECONDARY_COLLAPSE 10, SEED_DEPENDENT 2 |
| history lost | recoverable only within a timing window | NO_EFFECTIVE_ACTION 202, ACTION_TOO_LATE 98, OVERSHOOT 46, SECONDARY_COLLAPSE 43 |

*Reference repair*: the validated setting with the lowest equal-weight normalised cost; its horizons are those of its exploration cell. Every validated setting is effective at all applicable horizons by definition, so a setting that recovers at the short horizon and not at the long one is never in this table: it is listed as *only transiently recoverable* (flags) or in the failure ids.
Interpretation: repairability is not a property of a stress but of a stress, an action, a magnitude, a tick and a horizon. For the resource, the renewal-efficiency and the history-lost stresses the tested action space has a **window that closes** (at ticks 110, 112 and 121); for the coupling, the renewal-stopped and the Address stresses a pulse-based repair
stays effective **at every tested tick after the collapse, to tick 330, where the tested range ends**: no closure was found, and no irreversible tick is claimed. The classification "neither" at tick 113 and "internally reconfigurable / externally repairable / both" at another tick are both true and both are reported.

## 8. Timing windows

For every setting Pipeline A found effective or nearly, every action tick from 101 to 170 was run on seeds 1-10 (exploration and validation reported separately; a tick is *effective* only if both are all effective). The unrepaired run collapses at about tick 144-159 (section 7). A window that is still effective at the last tick tested (170, or 330 after the extension) **has not closed**: its end is the end of the range, and no latest successful or irreversible tick is claimed for it.

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

**Latest successful repair tick** = the last tick at which some tested setting is effective. **Earliest irreversible tick** = the next tick, after which no tested setting is effective at any later tested tick (ticks 101-170 at one-tick resolution for every setting, 171-330 for the three whose window was still open at 170, 200 on the coarse grid). They are not the same notion (a window may end and another open later: the effective ticks are often **fragmented**, a gap is recorded and not smoothed), and **both depend on the tested action space**:
a tick that is irreversible here may be recoverable by an action that was not tested. Fragmentation is not explained here (the gaps inside a window are several ticks long, longer than the operating cycle of 5 ticks; no mechanism is claimed).

Reachable recovery by tick (tested action space, one-tick resolution):

- **coupling weakened (gain 0.5)** (unrepaired collapse at 149): 101-105 world-state; 106-107 none; 108-117 world-state; 118-123 none; 124-330 world-state
- **resource reduced (regrow 0.01, charge 0.2)** (unrepaired collapse at 149): 101-109 internal; 110-330 none
- **renewal efficiency 0.6** (unrepaired collapse at 149): 101-111 internal; 112-330 none
- **renewal stopped (feedback removed)** (unrepaired collapse at 144): 101-106 combined; 107-120 none; 121-121 combined; 122-129 none; 130-330 combined
- **Address degraded (A2 partial 50 %)** (unrepaired collapse at 149): 101-109 combined; 110-130 none; 131-133 combined; 134-134 none; 135-135 combined; 136-139 none; 140-330 combined
- **history lost** (unrepaired collapse at 159): 101-113 internal; 114-120 combined; 121-330 none

**Delayed but recoverable** (effective at or after the unrepaired collapse):

- coupling weakened (gain 0.5): effective ticks at or after the unrepaired collapse (149): 124-330
- resource reduced (regrow 0.01, charge 0.2): no tested setting is effective at any tick from the unrepaired collapse (149) to 170
- renewal efficiency 0.6: no tested setting is effective at any tick from the unrepaired collapse (149) to 170
- renewal stopped (feedback removed): effective ticks at or after the unrepaired collapse (144): 130-330
- Address degraded (A2 partial 50 %): effective ticks at or after the unrepaired collapse (149): 140-330
- history lost: no tested setting is effective at any tick from the unrepaired collapse (159) to 170

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
is not the damage site, and the original parameter restored alone does not restore the system once the damage has set in. The local bypass is not implemented (no spatial coupling path in the engine).

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

**Replay timeline** (markers, each with its source: the schedule, the controller log, the status record or a saved result): stress onset, repair decision, repair action, collapse, collapse prevented / full recovery, failed repair, overshoot, secondary collapse, irreversible threshold. A click gives the tick, the detail and the source; the inspection beside it shows the world state (operational, observed, observability), the active route and the MFS of the run.
**Research map** layers: damaged path, repairable path, repaired path, temporary bypass, world-state intervention, internal reconfiguration, failed repair (red dotted and crossed for damage and failure, violet for a world-state repair, blue for an internal one, green for a repaired path or a bypass); an internal reconfiguration is never drawn as a world-state repair.
**Technical view**: a repair figure of seven paths (resource, coupling, history, observation, recovery, Address, M2) with their state at the playhead, the stress with its tick, each repair action that has happened with its tick, magnitude, duration and class, the cost annotation and the operational result at the three horizons; drawn only from the run's events (a repair that did not happen is not drawn; the repair site is where the action acted).
**Deep links**: `stress=<id>&repair=<controller>` or `stress=<id>&ract=<action>/<magnitude>/<duration>/<tick>[,...]`; parsing, formatting and the plan are tested.

## 23. Performance

(pending)

## 24. Regression

(pending)

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

## 26. Null results (kept)

- No pulse of 0.1-6.0 recovers the resource, the renewal-efficiency or the renewal-stopped stress at tick 113 (section 11); a pulse alone on history lost gives a transient recovery and then a secondary collapse.
- The restoration of the Address alone, the restart of the renewal alone, the temporary bridge of the coupling, the temporary renewal boost: no effective tick (sections 9, 12, 13).
- The controllers on the renewal and resource stresses, and on the stronger coupling drop: 0 of 20 (section 15, 17).
- Stage 4's strict nulls are unchanged.
- The raw rows of every run are kept: `experiments_stage6_raw.jsonl.gz` (12390 rows), `experiments_stage6_raw_combined.jsonl.gz`, `experiments_stage6_controllers_raw.jsonl.gz`; the results of the first criterion are kept beside the corrected ones.

## 27. Limitations

- The action space is limited to what MEOS-0 can do: the local bypass, the transport rerouting and the temporary local Address are not implemented, redistribution and the reserve release are proxies (section 4).
- The tick grid is finite (one-tick resolution only for the settings measured at that resolution; ticks 101-170, a coarse grid to 200); the horizons are finite (180, 300, 480); the seeds are few (5 + 5 for each setting, 20 for evaluation) and the engine's seed-to-seed variation is small, so proportions are near 0 or 1.
- The repair cost model is synthetic (measured from the model's own traces, equal-weight only where an order is needed). The environment model is synthetic. No claim is made about real ecosystems.
- The controllers sense five features; four stresses give the same signature, so the controller cannot tell them apart and tries plans in turn.
- Unknown-stress coverage is limited to the variations listed; generalization is shown, where it is, only for those.
- The MFS and SSS readings use the repairs validated on the full arrangement, on 5 and 3 seeds, and an island of a 3 x 3 grid.
- Repairability is conditional on the tested model, version, action space, ticks and horizons: a stress called unrecoverable here is unrecoverable *under the tested actions*.

## 28. Remaining work

**Unimplemented**
- The local bypass of the coupling, transport rerouting of the resource and temporary local addressing (the engine has no mechanism; none was simulated by something else); real redistribution and reserve release (only proxies).
- A repair controller that learns from its own attempts across runs, or one that uses more than the five sensed features.
- Search over the order of two repair actions and over three or more at once (pairs at the same tick only).
- Combined *stresses* (two stresses at once) and their combined repairs.

**Unverified**
- Whether more seeds would turn the near misses (the Address restoration with a pulse at the decision tick; M2 and its neighbours at tick 114-118) into validated settings or reject them.
- Windows beyond the one-tick range for settings not measured at one-tick resolution; settings outside the grids of magnitudes and durations.
- The fragmentation of the timing windows (gaps inside a window) is recorded, not explained.
- The repairability of the MFS and the SSS grid on independent validation seeds (they use exploration seeds 1-5 and 1-3).

**Partial**
- Unknown-stress evaluation: the variations listed, not a general family of stresses.
- Observation repair: tested as a change of the observer on recorded runs, not as part of a controller.
- The cost model: raw and normalised measurements of the model's traces; no weighted objective was optimised.
