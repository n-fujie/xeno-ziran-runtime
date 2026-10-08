# Disconnection, and the cut / reconfiguration trigger distinction

The previous phase left disconnection UNRESOLVED: it fires, but removing it had no detected downstream effect in
the default regimes. This study builds worlds in which disconnection should matter if it is operationally
non-redundant, and tests it on downstream effects only.

## 1. Targeted structures [choice]

`scenario/topologies.py::disconnection_structure`. The world consists of eight closed modules. The connections
between modules are weak, with a base weight of 1.6 × w_min, so they dissolve when they carry flow without
penetrating. The structures differ in how the modules are joined:

| structure | how the modules are joined |
|---|---|
| single_bridge | modules 1–7 richly joined; module 0 attached by one connection each way |
| bottleneck | two groups of four joined by two connections each way |
| sparse_tree | a binary tree of modules (one connection each way per edge) |
| fragile_loop | a one-way ring of modules |
| one_way_path | a one-way chain of modules |
| delayed_return_route | a chain forward (two connections per hop) and a single connection back from the last module to the first |
| high_path_dependence | two competing routes from module 0 to module 5, and one back |
| isolated_regions_bridge | two groups of four with dense intra-group links and a single bridge between the groups |

Every structure's transmission gain is calibrated to the common sustained activity, as for the topologies.

## 2. Variants (runtime flags; no reasoning layer)

| variant | disconnection trigger (weight < w_min) executes |
|---|---|
| C (reference) | removal |
| off | nothing (disconnection removed) |
| weight_zero | the connection stays, with weight and base weight 0 |
| as_cut | the cut operation (removal + load reset; reported as a cut) |
| as_mutation | removal through the generic mutation path (retired slot) |
| redirect | generic connection mutation: redirected to a uniformly random configuration, weight reset |

Own outputs are excluded because they differ by construction:
- disconnection, removal, cut and reconfiguration counts;
- connection counts;
- out-degree;
- reachable-connection share.

Everything else counts as downstream, at all six resolutions.

## 3. Status rules [derived]

| status | rule |
|---|---|
| REDUCIBLE | removal demonstrably detectable (a systematic downstream difference somewhere) and a replacement equivalent in every structure |
| NON-REDUNDANT | removal detectable in every structure and no replacement equivalent everywhere |
| REGIME-DEPENDENT | removal detectable in some structures, equivalent within the stated margin in others, and no replacement equivalent everywhere |
| UNRESOLVED | removal not demonstrably detectable in any structure |

Cut / reconfiguration trigger study variants (`runtime/flags.py::topology_trigger`):

| variant | definition |
|---|---|
| cut only | reconfiguration removed |
| reconfiguration only | cut removed |
| unified | one connection-level trigger (load > capacity) and one operation (redirect past the target) |
| generic conditions | both conditions kept; both executed as generic connection mutation |
| merged | one configuration-level condition (an overloaded outgoing connection, or an overload streak) and one operation (remove the most loaded connection and create one to a second-order neighbour) |

The regimes are the default field, long memory, high topology mutation, and the bottlenecked, modular,
small-world and dense-random topologies. Status rules: descriptive only / reducible / structurally necessary /
conditionally necessary / unresolved, as defined in `experiments/escalation/summary.py::trigger_verdict`.

## 4. Results (generated from the result files)

<!-- GENERATED:BEGIN -->
**Status: REDUCIBLE**

- removal detectable (downstream, systematic) in: disconnection:bottleneck, disconnection:fragile_loop, disconnection:one_way_path, disconnection:delayed_return_route, disconnection:high_path_dependence, disconnection:isolated_regions_bridge
- removal equivalent (macro and global within 5 %, no systematic difference) in: none
- removal unresolved in: disconnection:single_bridge, disconnection:sparse_tree
- replacements equivalent in every structure: as_cut, as_mutation
- replacements bit-identical in every structure: as_mutation
- noise control detections: 0 of 8

Own outputs excluded: alive_connections, cuts, degree, reachable_share, reconfigurations, removed

| structure | off | weight_zero | as_cut | as_mutation | redirect | C~ |
|---|---|---|---|---|---|---|
| single_bridge | UNR | UNR | HID | RED | NR (global difference 59%) | UNR |
| bottleneck | NR (global new_connections -14%) | UNR | RED | RED | NR (global difference 74%) | UNR |
| sparse_tree | UNR | UNR | RED | RED | NR (global penetrations 95%) | UNR |
| fragile_loop | NR (global new_connections -42%) | UNR | RED | RED | NR (global difference 58%) | UNR |
| one_way_path | NR (global new_connections -8%) | UNR | RED | RED | NR (global difference 61%) | UNR |
| delayed_return_route | NR (global new_connections -5%) | UNR | RED | RED | NR (global difference 72%) | UNR |
| high_path_dependence | NR (global new_connections -6%) | UNR | HID | RED | NR (global difference 79%) | UNR |
| isolated_regions_bridge | NR (global new_connections -5%) | UNR | RED | RED | NR (global memory_dependent_share 57%) | UNR |

### Cut / reconfiguration triggers

**Status: conditionally necessary**

- removing the reconfiguration trigger (cut only) detectable in: topology_trigger:default, topology_trigger:small_world, topology_trigger:dense_random
- removing the cut trigger (reconfiguration only) detectable in: topology_trigger:default, topology_trigger:long_memory, topology_trigger:high_mutation, topology_trigger:bottlenecked, topology_trigger:modular, topology_trigger:small_world, topology_trigger:dense_random
- unified trigger detectable in: topology_trigger:default, topology_trigger:long_memory, topology_trigger:high_mutation, topology_trigger:bottlenecked, topology_trigger:modular, topology_trigger:small_world, topology_trigger:dense_random
- merged condition detectable in: topology_trigger:default, topology_trigger:long_memory, topology_trigger:high_mutation, topology_trigger:bottlenecked, topology_trigger:modular, topology_trigger:small_world, topology_trigger:dense_random
- shared generic operation with separate conditions bit-identical everywhere: False
- **A. is the connection-mutation operation shared?** shared (equivalent in every regime; not bit-identical)
- **B. are the trigger conditions operationally distinct?** distinct: merging the conditions changes behaviour in unified: topology_trigger:default, topology_trigger:long_memory, topology_trigger:high_mutation, topology_trigger:bottlenecked, topology_trigger:modular, topology_trigger:small_world, topology_trigger:dense_random; merged: topology_trigger:default, topology_trigger:long_memory, topology_trigger:high_mutation, topology_trigger:bottlenecked, topology_trigger:modular, topology_trigger:small_world, topology_trigger:dense_random

| structure | cut_only | reconfigure_only | unified | generic_conditions | merged | C~ |
|---|---|---|---|---|---|---|
| default | NR (meso memory 17%) | NR (global penetrations 94%) | NR (global new_connections -18%) | HID | UNR (local degree -72%) | UNR |
| long_memory | UNR | NR (global new_connections -9%) | NR (global new_connections -8%) | RED | UNR (node degree -68%) | UNR |
| high_mutation | HID | NR (global alive_connections 2%) | NR (global alive_connections 3%) | HID | NR (global alive_connections 3%) | HID |
| bottlenecked | UNR | NR (global penetrations 88%) | NR (global new_connections -24%) | HID | NR (global memory_dependent_share 35%) | UNR |
| modular | UNR | NR (global penetrations 49%) | NR (global new_connections -30%) | HID | NR (global memory_dependent_share 86%) | HID |
| small_world | NR (global memory_dependent_share -32%) | NR (global new_connections -6%) | NR (global new_connections -10%) | HID | NR (global new_connections 89%) | UNR |
| dense_random | NR (global memory_dependent_share -34%) | NR (global new_connections -23%) | NR (global new_connections -22%) | HID | NR (global memory_dependent_share 118%) | UNR |
<!-- GENERATED:END -->

## 5. Classification, then interpretation

**[derived] Disconnection: REDUCIBLE.** The verdict and every cell are generated above.
- **Removal is detectable.** Removing disconnection produces a systematic downstream difference in most targeted
  structures. It shows as reduced closure: dissolved-but-alive connections block triadic closure from recreating
  those links. In the remaining structures it is unresolved, never shown equivalent.
- **Its operation is shared.** Executing the same trigger through the generic mutation removal path is bit-identical
  in every structure. Executing it as a cut is equivalent everywhere, with exact divergence in a small share of seeds.
- **Other replacements.** Redirecting the dissolved connection instead (generic *redirect* mutation) is
  non-redundant everywhere. A weight-zero replacement is unresolved.
- **Conclusion.** What is operationally needed is the **weakness condition**, not a separate operation. Disconnection
  = generic connection removal, triggered by weight < w_min.

**[derived] Cut / reconfiguration triggers:**
- **A. The connection-mutation operation is shared.** Executing both triggers through one generic mutation operation,
  with the conditions kept separate, is equivalent in every regime tested. It is not bit-identical: new connections
  land in other slots, which changes float summation order.
- **B. The trigger conditions are operationally distinct.** Merging them into one connection-level trigger, or into
  one configuration-level condition, changes behaviour in every regime. Removing the cut trigger is detectable
  everywhere; removing the reconfiguration trigger only in some regimes.
- **Status: conditionally necessary.** The conditions cannot be merged, and the operation can be shared.

**[interpretation]** Both studies point the same way. The runtime's topology operations reduce to one generic
connection mutation, but the conditions that trigger it (overload, overload streak, weakness) are distinct
operational distinctions and are not reducible.
