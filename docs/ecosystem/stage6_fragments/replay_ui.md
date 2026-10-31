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
| `62-reachable-recovery-map.png` | the strip of each stress over ticks 101-420; every window closes (the three late ones at 389 / 384 / 384) | as 60 |
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
