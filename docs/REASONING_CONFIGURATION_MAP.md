# Reasoning configuration map

For each structural difference between the reasoning variants and the reference structure C, this map gives:
- the configurations in which it becomes operationally visible;
- where coarse equivalence is established within the stated margin (no difference detected there; not shown absent);
- where the experiment cannot resolve it.

Definitions of the variants and statistics are in docs/RESOLUTION_ESCALATION.md.

## 1. Reasoning structures (neutral support specifications) [choice]

`reasonlab/structures.py::generate(kind, size, seed, coupling)`. Items carry tokens, effects bound to world regions,
a base level and a self-standing flag. Requirements either carry a level or only enable. Conflicts are symmetric.

| kind | construction |
|---|---|
| shallow_acyclic | 40 % self-standing roots; every other item carried by 1–2 roots; few conflicts |
| deep_chain | two chains of size/2, each link carried by the previous one; a rival conflicts with the chain head |
| strongly_cyclic | one ring of carry / enable requirements; some backed-but-not-self-standing items, a few roots |
| multi_cycles | overlapping rings of length 4–8 |
| sparse_conflicts / dense_conflicts | random DAG, 25 % roots; 0.1 × size / 1.5 × size conflicts |
| unsupported_addressable | 30 % roots; 50 % backed items without any requirement (addressable, unsupported); 20 % derived |
| competing_clusters | 2–4 clusters, each a DAG leading to one conclusion; the conclusions conflict across clusters |
| local_external_memory | shallow DAG; the roots lose 70 % of their level while memory in R is persistently below baseline |
| distributed_external_memory | the same, with roots grounded in 8 different regions |
| record_fragmentation | shallow DAG; random requirement drops / additions every third check while reasoning |
| record_loss_reconstruction | shallow DAG; all requirements lost at 40 % of the run and restored at 70 % |
| mixed_fixpoint_regions | clusters alternately cyclic (fixpoint-sensitive) and acyclic |
| multiple_clusters | independent DAG clusters, each bound to its own regions |
| partially_incompatible_rules | clusters with cross-cluster conflicts and some cross-cluster records |

The structural descriptors computed for every kind are:
- dependency depth;
- cycles;
- support branching;
- incompatibility density;
- dependency centralization;
- record locality;
- support redundancy;
- fixpoint sensitivity;
- cluster count;
- inter-cluster coupling;
- unsupported-but-backed items.

## 2. World-responsive revision triggers [choice]

`reasonlab/triggers.py`. Each trigger watches one operational metric of one region. It is calibrated against that
region's pre-reasoning baseline, fires on a persistent deviation (|z| > 2 for 2 checks, then a 5-check refractory
period) and edits only items bound to that region. The ten kinds:
- memory level;
- reachability from R;
- prediction mismatch;
- topology change;
- failed intervention;
- support-path loss;
- new incompatibility;
- delayed consequence;
- repeated instability;
- unexpected closure.

The cluster study adds `overwrite`, in which clusters retract each other's items. Triggers never touch world state.

## 3. Configuration map (generated from the result files)

<!-- GENERATED:BEGIN -->
### A — no reasoning layer (vs reasoning with the reference structure)

Labels: HIDDEN AT COARSE RESOLUTION, NON-REDUNDANT, REGIME-DEPENDENT, TIME-WINDOW-DEPENDENT

| factor | dependent | visible at | equivalent at (coarse equivalence) | unresolved at |
|---|---|---|---|---|
| address | yes | locally_stable_globally_unstable, partially_unstable, stable (reference) | highly_unstable | — |
| coupling | no | medium (reference), strong | — | weak |
| horizon | no | 400, 4000 (reference) | — | 40000 |
| memory | no | delayed_return, external_persistent, long, medium (reference), near_zero, short | — | fragmented |
| mutation | yes | high_state, low (reference), mixed | high_topology, medium_topology | — |
| n | no | 10000, 100000, 100000 (400 steps), 1500 (reference) | — | — |
| power | no | 48 seeds | — | — |
| return | yes | competing, immediate | delayed, multi_step_delayed, none | — |
| size | no | 128, 2048, 32 (reference), 512 | — | 9 |
| strong×topology | no | bottlenecked, dense_random, hierarchical, highly_clustered, modular, nested_multiscale, weakly_connected | — | small_world, sparse_random |
| structure | yes | competing_clusters (reference), record_fragmentation, record_loss_reconstruction, unsupported_addressable | multi_cycles, strongly_cyclic | deep_chain, dense_conflicts, distributed_external_memory, local_external_memory, mixed_fixpoint_regions, multiple_clusters, partially_incompatible_rules, shallow_acyclic, sparse_conflicts |
| topology | no | hierarchical, highly_clustered, modular, multi_region (reference) | — | bottlenecked, dense_random, nested_multiscale, small_world, sparse_random, weakly_connected |

Largest systematic effects where visible: n:100000: global reconfigurations -93.4%; n:10000: global reconfigurations -52.9%; n:100000:h400: global reconfigurations -93.2%; reference: macro activity 10.2%; structure:unsupported_addressable: macro degree -17.3%; size:128: global reconfigurations -52.7%; memory:near_zero: global new_connections 10.9%; memory:short: macro activity 25.7%; memory:long: global reconfigurations -70.1%; memory:external_persistent: macro difference 19.5%; memory:delayed_return: macro activity 37.4%; mutation:high_state: global reconfigurations -42.6%

### B — vocabulary-bearing representation of the same structure

Labels: REDUNDANT

| factor | dependent | visible at | equivalent at (coarse equivalence) | unresolved at |
|---|---|---|---|---|
| horizon | no | — | 400, 4000 (reference) | — |
| size | no | — | 128, 32 (reference), 9 | — |
| structure | no | — | competing_clusters (reference), dense_conflicts, multi_cycles, strongly_cyclic, unsupported_addressable | — |

### D — one-status support graph

Labels: HIDDEN AT COARSE RESOLUTION

| factor | dependent | visible at | equivalent at (coarse equivalence) | unresolved at |
|---|---|---|---|---|
| address | no | — | highly_unstable, locally_stable_globally_unstable, partially_unstable, stable (reference) | — |
| coupling | no | — | medium (reference), strong, weak | — |
| horizon | no | — | 400, 4000 (reference), 40000 | — |
| memory | no | — | delayed_return, external_persistent, fragmented, long, medium (reference), near_zero, short | — |
| mutation | no | — | high_state, high_topology, low (reference), medium_topology, mixed | — |
| n | no | — | 10000, 100000 (400 steps), 1500 (reference) | — |
| power | no | — | 48 seeds | — |
| return | no | — | competing, delayed, immediate, multi_step_delayed, none | — |
| size | no | — | 128, 32 (reference), 9 | — |
| strong×topology | no | — | bottlenecked, dense_random, hierarchical, highly_clustered, modular, nested_multiscale, small_world, sparse_random, weakly_connected | — |
| structure | no | — | competing_clusters (reference), deep_chain, dense_conflicts, distributed_external_memory, local_external_memory, mixed_fixpoint_regions, multi_cycles, multiple_clusters, partially_incompatible_rules, record_fragmentation, record_loss_reconstruction, shallow_acyclic, sparse_conflicts, strongly_cyclic | unsupported_addressable |
| topology | no | — | bottlenecked, dense_random, hierarchical, highly_clustered, modular, multi_region (reference), nested_multiscale, small_world, sparse_random, weakly_connected | — |

### E — eligibility tracking disabled (backed only)

Labels: HIDDEN AT COARSE RESOLUTION, NON-REDUNDANT, REGIME-DEPENDENT, SCALE-DEPENDENT, TIME-WINDOW-DEPENDENT

| factor | dependent | visible at | equivalent at (coarse equivalence) | unresolved at |
|---|---|---|---|---|
| address | no | — | highly_unstable | locally_stable_globally_unstable, partially_unstable, stable (reference) |
| coupling | no | — | — | medium (reference), strong, weak |
| horizon | no | 400 | — | 4000 (reference), 40000 |
| memory | no | — | — | delayed_return, external_persistent, fragmented, long, medium (reference), near_zero, short |
| mutation | yes | high_state, mixed | high_topology, medium_topology | low (reference) |
| n | yes | 100000, 100000 (400 steps) | 10000 | 1500 (reference) |
| power | no | 48 seeds | — | — |
| return | no | — | competing, delayed, immediate, none | multi_step_delayed |
| size | no | 128 | — | 2048, 32 (reference), 512, 9 |
| strong×topology | no | — | modular | bottlenecked, dense_random, hierarchical, highly_clustered, nested_multiscale, small_world, sparse_random, weakly_connected |
| structure | no | — | record_loss_reconstruction | competing_clusters (reference), deep_chain, dense_conflicts, distributed_external_memory, local_external_memory, mixed_fixpoint_regions, multi_cycles, multiple_clusters, partially_incompatible_rules, record_fragmentation, shallow_acyclic, sparse_conflicts, strongly_cyclic, unsupported_addressable |
| topology | no | — | modular | bottlenecked, dense_random, hierarchical, highly_clustered, multi_region (reference), nested_multiscale, small_world, sparse_random, weakly_connected |

Largest systematic effects where visible: n:100000: macro memory 5.3%; n:100000:h400: global memory_dependent_share 6.3%; size:128: macro difference -18.9%; mutation:high_state: macro activity -10.4%; mutation:mixed: meso activity -27.7%; power:48seeds: meso activity -10.3%; horizon:400: macro activity -10.2%

### F — least instead of greatest fixpoint

Labels: HIDDEN AT COARSE RESOLUTION, NON-REDUNDANT, SCALE-DEPENDENT

| factor | dependent | visible at | equivalent at (coarse equivalence) | unresolved at |
|---|---|---|---|---|
| address | no | — | highly_unstable | locally_stable_globally_unstable, partially_unstable, stable (reference) |
| coupling | no | — | — | medium (reference), strong, weak |
| horizon | no | — | — | 400, 4000 (reference), 40000 |
| memory | no | — | — | delayed_return, external_persistent, fragmented, long, medium (reference), near_zero, short |
| mutation | no | — | high_state, high_topology, mixed | low (reference), medium_topology |
| n | yes | 10000 | 100000, 100000 (400 steps) | 1500 (reference) |
| power | no | — | — | 48 seeds |
| return | no | — | competing, delayed, immediate, multi_step_delayed, none | — |
| size | no | — | 128, 512, 9 | 2048, 32 (reference) |
| strong×topology | no | — | bottlenecked, modular, sparse_random, weakly_connected | dense_random, hierarchical, highly_clustered, nested_multiscale, small_world |
| structure | no | — | distributed_external_memory, local_external_memory, multi_cycles, record_fragmentation, record_loss_reconstruction, shallow_acyclic, sparse_conflicts, strongly_cyclic, unsupported_addressable | competing_clusters (reference), deep_chain, dense_conflicts, mixed_fixpoint_regions, multiple_clusters, partially_incompatible_rules |
| topology | no | — | modular | bottlenecked, dense_random, hierarchical, highly_clustered, multi_region (reference), nested_multiscale, small_world, sparse_random, weakly_connected |

Largest systematic effects where visible: n:10000: macro activity 3.4%

### G — conflict defeats persist across evaluations

Labels: HIDDEN AT COARSE RESOLUTION, NON-REDUNDANT, SCALE-DEPENDENT, TRANSIENT

| factor | dependent | visible at | equivalent at (coarse equivalence) | unresolved at |
|---|---|---|---|---|
| address | no | — | highly_unstable | locally_stable_globally_unstable, partially_unstable, stable (reference) |
| coupling | no | — | — | medium (reference), strong, weak |
| horizon | no | — | 400 | 4000 (reference), 40000 |
| memory | no | — | — | delayed_return, external_persistent, fragmented, long, medium (reference), near_zero, short |
| mutation | no | — | high_state, high_topology, mixed | low (reference), medium_topology |
| n | yes | 100000 (400 steps) | 10000 | 1500 (reference) |
| power | no | — | 48 seeds | — |
| return | no | — | competing, delayed, immediate, multi_step_delayed, none | — |
| size | no | — | 9 | 128, 32 (reference) |
| structure | no | — | deep_chain, local_external_memory, mixed_fixpoint_regions, multi_cycles, multiple_clusters, record_fragmentation, record_loss_reconstruction, unsupported_addressable | competing_clusters (reference), dense_conflicts, distributed_external_memory, partially_incompatible_rules, shallow_acyclic, sparse_conflicts, strongly_cyclic |
| topology | no | — | dense_random, modular, small_world, sparse_random, weakly_connected | bottlenecked, hierarchical, highly_clustered, multi_region (reference), nested_multiscale |

Largest systematic effects where visible: n:100000:h400: global memory_dependent_share -4.6%

### H — no dependency records

Labels: HIDDEN AT COARSE RESOLUTION, NON-REDUNDANT, SCALE-DEPENDENT, TIME-WINDOW-DEPENDENT, TOPOLOGY-DEPENDENT

| factor | dependent | visible at | equivalent at (coarse equivalence) | unresolved at |
|---|---|---|---|---|
| address | no | — | highly_unstable | locally_stable_globally_unstable, partially_unstable, stable (reference) |
| coupling | no | — | — | medium (reference), strong, weak |
| horizon | no | — | — | 400, 4000 (reference), 40000 |
| memory | no | delayed_return | — | external_persistent, fragmented, long, medium (reference), near_zero, short |
| mutation | no | — | high_state, high_topology | low (reference), medium_topology, mixed |
| n | yes | 100000, 100000 (400 steps) | 10000 | 1500 (reference) |
| power | no | — | — | 48 seeds |
| return | no | — | competing, delayed, immediate, multi_step_delayed, none | — |
| size | yes | 128, 2048, 512 | 9 | 32 (reference) |
| strong×topology | yes | highly_clustered | modular | bottlenecked, dense_random, hierarchical, nested_multiscale, small_world, sparse_random, weakly_connected |
| structure | no | distributed_external_memory, local_external_memory, shallow_acyclic, unsupported_addressable | — | competing_clusters (reference), deep_chain, dense_conflicts, mixed_fixpoint_regions, multi_cycles, multiple_clusters, partially_incompatible_rules, record_fragmentation, record_loss_reconstruction, sparse_conflicts, strongly_cyclic |
| topology | no | — | modular | bottlenecked, dense_random, hierarchical, highly_clustered, multi_region (reference), nested_multiscale, small_world, sparse_random, weakly_connected |

Largest systematic effects where visible: n:100000: meso memory -3.2%; n:100000:h400: global memory_dependent_share -14.5%; structure:unsupported_addressable: meso degree -2.8%; size:128: global reachable_share 2.1%; memory:delayed_return: global memory 8.6%; structure:local_external_memory: macro activity -38.5%; structure:distributed_external_memory: global reconfigurations -27.1%; structure:shallow_acyclic: macro difference 88.1%; strong×topology:highly_clustered: meso memory -7.4%; size:512: global memory -48.5%; size:2048: global penetrations -71.7%

### I — local-only records (cross-cluster requirements dropped)

Labels: REDUNDANT

| factor | dependent | visible at | equivalent at (coarse equivalence) | unresolved at |
|---|---|---|---|---|
| address | no | — | highly_unstable, locally_stable_globally_unstable, partially_unstable, stable (reference) | — |
| coupling | no | — | medium (reference), strong, weak | — |
| horizon | no | — | 400, 4000 (reference) | — |
| memory | no | — | delayed_return, external_persistent, fragmented, long, medium (reference), near_zero, short | — |
| mutation | no | — | high_state, high_topology, low (reference), medium_topology, mixed | — |
| n | no | — | 10000, 100000 (400 steps), 1500 (reference) | — |
| return | no | — | competing, delayed, immediate, multi_step_delayed, none | — |
| size | no | — | 128, 32 (reference), 9 | — |
| structure | no | — | competing_clusters (reference), deep_chain, dense_conflicts, distributed_external_memory, local_external_memory, mixed_fixpoint_regions, multi_cycles, multiple_clusters, partially_incompatible_rules, record_fragmentation, record_loss_reconstruction, shallow_acyclic, sparse_conflicts, strongly_cyclic, unsupported_addressable | — |
| topology | no | — | bottlenecked, dense_random, hierarchical, highly_clustered, modular, multi_region (reference), nested_multiscale, small_world, sparse_random, weakly_connected | — |

### J — records persistent (immune to decay, fragmentation, loss)

Labels: HIDDEN AT COARSE RESOLUTION, NON-REDUNDANT

| factor | dependent | visible at | equivalent at (coarse equivalence) | unresolved at |
|---|---|---|---|---|
| address | no | — | highly_unstable | locally_stable_globally_unstable, partially_unstable, stable (reference) |
| horizon | no | — | 400 | 4000 (reference) |
| memory | no | — | delayed_return, near_zero, short | external_persistent, fragmented, long, medium (reference) |
| mutation | no | — | high_state, high_topology, medium_topology, mixed | low (reference) |
| size | no | 128 | — | 32 (reference), 9 |
| structure | no | — | multi_cycles, record_loss_reconstruction, strongly_cyclic, unsupported_addressable | competing_clusters (reference), dense_conflicts, distributed_external_memory, local_external_memory, record_fragmentation |

Largest systematic effects where visible: size:128: global reconfigurations 53.0%

### K — mixed rules per cluster

Labels: HIDDEN AT COARSE RESOLUTION

| factor | dependent | visible at | equivalent at (coarse equivalence) | unresolved at |
|---|---|---|---|---|
| address | no | — | highly_unstable, locally_stable_globally_unstable, partially_unstable, stable (reference) | — |
| coupling | no | — | medium (reference), weak | strong |
| horizon | no | — | 400, 4000 (reference) | — |
| memory | no | — | delayed_return, external_persistent, long, medium (reference), near_zero, short | fragmented |
| mutation | no | — | high_state, high_topology, low (reference), medium_topology, mixed | — |
| n | no | — | 10000, 100000 (400 steps), 1500 (reference) | — |
| return | no | — | competing, delayed, immediate, multi_step_delayed, none | — |
| size | no | — | 32 (reference), 9 | 128 |
| structure | no | — | competing_clusters (reference), deep_chain, dense_conflicts, distributed_external_memory, local_external_memory, multi_cycles, record_fragmentation, record_loss_reconstruction, shallow_acyclic, sparse_conflicts, strongly_cyclic, unsupported_addressable | mixed_fixpoint_regions, multiple_clusters, partially_incompatible_rules |
| topology | no | — | bottlenecked, dense_random, hierarchical, highly_clustered, modular, multi_region (reference), nested_multiscale, small_world, sparse_random, weakly_connected | — |

### Interacting reasoning clusters

| condition | n | steps | A | D | E | F | G | I | K | C~ |
|---|---|---|---|---|---|---|---|---|---|---|
| clusters:independent | 1,500 | 4,000 | NR | RED | UNR | UNR | RED | RED | UNR | UNR |
| clusters:weakly_connected | 1,500 | 4,000 | UNR | RED | UNR | UNR | HID | RED | UNR | UNR |
| clusters:strongly_interacting | 1,500 | 4,000 | NR | RED | HID | HID | RED | RED | HID | HID |
| clusters:competing | 1,500 | 4,000 | NR | RED | HID | HID | HID | RED | RED | HID |
| clusters:different_fixpoints | 1,500 | 4,000 | NR | HID | HID | HID | RED | RED | HID | HID |
| clusters:different_memory_persistence | 1,500 | 4,000 | NR | HID | UNR | UNR | HID | RED | UNR | UNR |
| clusters:merging | 1,500 | 4,000 | NR | HID | UNR | UNR | RED | RED | HID | UNR |
| clusters:splitting | 1,500 | 4,000 | NR | RED | HID | HID | RED | RED | HID | HID |
| clusters:losing_shared_addressability | 1,500 | 4,000 | NR | RED | UNR | UNR | RED | RED | UNR | UNR |
| clusters:sharing_records | 1,500 | 4,000 | HID | HID | HID | HID | HID | RED | HID | HID |
| clusters:overwriting_records | 1,500 | 4,000 | NR | RED | HID | HID | RED | RED | HID | HID |

### World-responsive revision (all ten triggers)

| noise | adaptivity C / M / S / R | in-band C / S / M / R / A | C − S (t) | C − R (t) | C − A (t) | responded vs control | firings |
|---|---|---|---|---|---|---|---|
| none | 0.9138 / 0.8516 / 0.6339 / 0.0 | 32.2% / 29.3% / 27.1% / 29.3% / 32.4% | 2.9% (1.24) | 3.0% (1.47) | -0.2% (-0.09) | 47% vs 43% | 345.08 |
| state | 0.9271 / 0.602 / 0.0004 / 0.0 | 76.1% / 57.9% / 72.1% / 66.1% / 62.8% | 18.2% (10.61) | 10.0% (6.29) | 13.3% (7.65) | 9% vs 5% | 109.08 |
| mixed | 0.7931 / 0.4947 / 0.1669 / 0.0 | 67.0% / 58.8% / 68.6% / 66.1% / 63.9% | 8.2% (3.08) | 0.9% (0.28) | 3.0% (1.53) | 17% vs 6% | 46.92 |

| noise | vs C | classification | resolutions (node · local · meso · macro · global) |
|---|---|---|---|
| none | C~ | UNRESOLVED | UNRESOLVED · UNRESOLVED · UNRESOLVED · UNRESOLVED · UNRESOLVED |
| none | S | NON-REDUNDANT | UNRESOLVED · UNRESOLVED · UNRESOLVED · UNRESOLVED · DETECTED |
| none | M | NON-REDUNDANT | UNRESOLVED · DETECTED · DETECTED · DETECTED · DETECTED |
| none | R | UNRESOLVED | UNRESOLVED · UNRESOLVED · UNRESOLVED · UNRESOLVED · UNRESOLVED |
| none | A | UNRESOLVED | UNRESOLVED · UNRESOLVED · UNRESOLVED · UNRESOLVED · UNRESOLVED |
| state | C~ | HIDDEN AT COARSE RESOLUTION | UNRESOLVED · UNRESOLVED · UNRESOLVED · EQUIVALENT · EQUIVALENT |
| state | S | NON-REDUNDANT | DETECTED · DETECTED · DETECTED · DETECTED · DETECTED |
| state | M | NON-REDUNDANT | DETECTED · DETECTED · DETECTED · DETECTED · DETECTED |
| state | R | HIDDEN AT COARSE RESOLUTION | UNRESOLVED · UNRESOLVED · UNRESOLVED · EQUIVALENT · EQUIVALENT |
| state | A | NON-REDUNDANT | DETECTED · DETECTED · DETECTED · DETECTED · EQUIVALENT |
| mixed | C~ | UNRESOLVED | UNRESOLVED · UNRESOLVED · UNRESOLVED · UNRESOLVED · EQUIVALENT |
| mixed | S | NON-REDUNDANT | DETECTED · DETECTED · DETECTED · DETECTED · DETECTED |
| mixed | M | NON-REDUNDANT | DETECTED · DETECTED · DETECTED · DETECTED · DETECTED |
| mixed | R | UNRESOLVED | UNRESOLVED · UNRESOLVED · UNRESOLVED · UNRESOLVED · EQUIVALENT |
| mixed | A | NON-REDUNDANT | DETECTED · DETECTED · DETECTED · UNRESOLVED · EQUIVALENT |

### Reasoning structures: descriptors (size 32)

| structure | depth | cycles | branching | conflict density | centralization | record locality | redundancy | fixpoint sensitivity | clusters | inter-cluster coupling | unsupported backed | active / bindings (reference rule) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| shallow_acyclic | 2 | 0 | 2.909 | 0.00202 | 0.0781 | 1.0 | 1.0 | 0.0 | 1 | 0.0 | 0 | 26 / 27 |
| deep_chain | 16 | 0 | 1.0 | 0.00403 | 0.0333 | 1.0 | 1.0 | 0.09659 | 1 | 0.0 | 0 | 0 / 25 |
| strongly_cyclic | 1 | 1 | 1.0 | 0.00403 | 0.0312 | 1.0 | 1.0 | 0.01136 | 1 | 0.0 | 0 | 0 / 21 |
| multi_cycles | 1 | 1 | 1.438 | 0.00403 | 0.0435 | 1.0 | 1.438 | 0.1875 | 1 | 0.0 | 0 | 0 / 22 |
| sparse_conflicts | 6 | 0 | 2.0 | 0.00605 | 0.0921 | 1.0 | 1.0 | 0.0 | 1 | 0.0 | 0 | 19 / 25 |
| dense_conflicts | 4 | 0 | 2.167 | 0.09677 | 0.0641 | 1.0 | 1.0 | 0.03125 | 1 | 0.0 | 0 | 6 / 25 |
| unsupported_addressable | 2 | 0 | 1.4 | 0.00605 | 0.2143 | 1.0 | 1.0 | 0.0 | 1 | 0.0 | 16 | 10 / 23 |
| competing_clusters | 5 | 0 | 1.944 | 0.02016 | 0.0714 | 1.0 | 1.0 | 0.03125 | 4 | 0.1765 | 0 | 9 / 23 |
| local_external_memory | 2 | 0 | 2.636 | 0.00202 | 0.0862 | 1.0 | 1.0 | 0.0 | 1 | 0.0 | 0 | 23 / 25 |
| distributed_external_memory | 2 | 0 | 2.417 | 0.00202 | 0.069 | 1.0 | 1.0 | 0.0 | 1 | 0.0 | 0 | 25 / 28 |
| record_fragmentation | 2 | 0 | 2.636 | 0.00202 | 0.069 | 1.0 | 1.0 | 0.0 | 1 | 0.0 | 0 | 21 / 23 |
| record_loss_reconstruction | 2 | 0 | 2.5 | 0.00202 | 0.0833 | 1.0 | 1.0 | 0.0 | 1 | 0.0 | 0 | 23 / 23 |
| mixed_fixpoint_regions | 6 | 2 | 1.385 | 0.00806 | 0.0694 | 1.0 | 1.0 | 0.09375 | 4 | 0.0 | 0 | 9 / 23 |
| multiple_clusters | 2 | 0 | 2.333 | 0.00806 | 0.0893 | 1.0 | 1.0 | 0.03125 | 4 | 0.0 | 0 | 17 / 22 |
| partially_incompatible_rules | 8 | 0 | 2.059 | 0.02823 | 0.0714 | 0.9231 | 1.0 | 0.0 | 4 | 0.3 | 0 | 10 / 25 |
<!-- GENERATED:END -->

## 4. World-responsive revision: classification, then interpretation

The numbers are in the generated tables above and in `summary.json` (`adaptivity_verdict`).

**[choice] Schedule variation is separated into three sources:**
- **Gating only.** The static structure (S) is gated by the same calibrated enabling conditions, but has no
  triggers.
- **Scripted.** R replays a schedule recorded in another world. It is zero by construction.
- **World-responsive revision.** This is the closed loop's variation (C) minus gating (S).

Revision counts as *genuinely* world-responsive only when that part is positive **and** firings are followed by the
triggering metric returning toward baseline significantly more often than random checks of the same region are
(paired across seeds).

**[measured]**
- **Without extra noise.** Revision varies across world seeds beyond gating, but its response to the world is not
  established (below the threshold). It brings no precision gain over any control.
- **Under high state noise.** Revision is genuinely world-responsive. It keeps the bound regions' activity inside
  their baseline band more often than the static, open-loop and no-reasoning controls. The long-run coarse shape
  against its own replayed schedule is hidden at coarse resolution (equivalent).
- **Under mixed noise.** Revision is world-responsive, with no precision difference.
- **Memoryless revision** (triggers acting on a fresh structure at every check) differs from persistent revision at
  coarse resolution in every noise condition.

**[interpretation]** Adaptivity is real only where the world is noisy enough to give triggers something to respond to.
There it improves control precision, and it never measurably worsened it. It does not, however, change the long-run
coarse shape relative to replaying the same kind of schedule.

## 5. Interacting reasoning clusters: classification, then interpretation

The cell-by-cell table is in the generated section above, and `summary.json` holds the cluster study under
`clusters`.

**[measured]** Eleven interaction settings were run, at 1,500 configurations and 4,000 steps:
- independent, weakly and strongly coupled clusters;
- competing clusters;
- mixed fixpoints and mixed memory persistence;
- merge, split, loss of shared addressability;
- shared records and record overwrite.

Results:
- **No structural variant became visible at meso, macro or global resolution in any setting.**
  - One status, no eligibility, least fixpoint, sticky conflicts and mixed rules are hidden, unresolved or bit-identical in every
    setting.
  - Local-only records are bit-identical in every setting.
- **Only the reasoning layer as a whole (A) is coarse-visible**, in most settings.
- The noise control made no detection.

**[derived]** The key question was whether reasoning-structure differences that were invisible in the single-cluster
lab become world-visible when several reasoning clusters interact. **They do not, at this scale.** Interaction
changes which interventions act, so exact trajectories diverge, but the coarse world stays equivalent or unresolved.

**[interpretation]** In the matrix, structural differences became coarse-visible mainly with larger worlds, where the
noise floor is lower, and with particular noise regimes. That is not a property of interaction: interaction itself
did not make the distinctions more visible at 1,500 configurations.
