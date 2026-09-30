# Operational primitive reduction

Question: which of the runtime's operations are operationally necessary, and which are relabellings,
derivations, or reducible to other operations? Principle: if two operations generate the same operational shape
under every tested configuration, merge or eliminate one. A primitive is not kept because it has a name, and it
is not called necessary unless removing it demonstrably changes behaviour.

## 1. Method (implementation choices)

* **Variants.** Every candidate is a runtime flag (`backend/xzr/runtime/flags.py`). With default flags the runtime
  is unchanged: deltas are byte-identical to the protocol fixtures committed before this phase. A *removal* drops the
  operation. A *replacement* re-implements it from other operations (e.g. reconfiguration as remove + create). A
  *compensation* removes it and retunes another operation (e.g. no retention, but stronger memory coupling).
* **Pairing.** A variant and the full runtime share configuration, generator seed (initial graph and local
  state), engine random stream, intervention battery (freeze a region, close a boundary to 20%, raise thresholds
  in a third region, at t = 120) and run length.
* **Regimes.** *intermittent* (defaults), *sparse* (lower gain), *memory_heavy* (memory couplings ×2, slower
  decay), *churn* (fragile connections, frequent closure/reconfiguration). N = 1,500.
* **Stage 1 — trajectory distance vs noise.** 3 seeds × 360 steps. Distances compare temporal and topological
  structure (windowed descriptor series for reachability, branching, closure, loops, fragmentation,
  concentration, persistence, amplification regime, path dependence; event sequences; connection-set edit
  distance; state distributions; regional shape signatures; intervention response). A variant *exceeds* when
  its distance > 2 × the full runtime's distance from itself under another random stream + 0.02.
* **Stage 2 — systematic effects.** Stage 1 cannot see small consistent shifts or slow structural effects.
  8 seeds × 1,200 steps; paired differences of ~40 scalar summaries; an effect counts only if |t| > 4 **and**
  |relative effect| > 2%. **A removal's own outputs are excluded** (its own event rate, and the topology-change
  series that sums them). An earlier version of this analysis counted them, which made, e.g., "no cuts after
  removing cut" look like evidence. Control: the same runtime under another random stream → 0 detections.
* **Audits.** (a) which arrays each operation writes; (b) influence matrix: perturb one array, see which other
  arrays change; (c) observer reconstruction of penetration annotations and returns outside the runtime.

## 2. Classification rules (applied mechanically, `xzr/experiments/reduction_rules.py`)

| status | rule |
|---|---|
| DESCRIPTIVE ONLY | removal bit-identical in every regime apart from the operation's own state/events |
| DERIVED | output reconstructed exactly by an observer, or recomputed equivalently from other state |
| REDUCIBLE | removal demonstrably changes behaviour in ≥ 1 regime **and** a replacement from other operations is equivalent in every regime with no systematic effect |
| NON-REDUNDANT | removal demonstrably changes behaviour in ≥ 1 regime **and** no tested replacement/compensation is equivalent everywhere |
| UNRESOLVED | no demonstrated downstream effect (absence of detected effect is not proof of redundancy), or trigger (almost) never fires |

"Demonstrably changes behaviour" = stage-1 exceedance or a stage-2 downstream systematic effect. Regime dependence
is reported per row and never averaged away.

## 3. Measured results (generated from the result file)

<!-- GENERATED:BEGIN -->
Result file: `backend/experiments/results/reduction.json` · stage 1: 4 regimes × 3 seeds × 360 steps, N = 1500 · stage 2: 8 seeds × 1200 steps · rule: exceed if d > 2.0·noise + 0.02; systematic effect ⇔ |t| > 4.0 and |effect| > 2% (own outputs excluded) · noise control (same runtime, other random stream): stage-2 detections = 0

### Classification

| primitive | status | removal / replacement | stage 1 per regime | stage 2 downstream effects per regime |
|---|---|---|---|---|
| Ignition (as a separate operation) | **REDUCIBLE** | fused_transition | intermittent: bit-identical · sparse: bit-identical · memory_heavy: bit-identical · churn: bit-identical | — |
| Threshold gating (ignition condition) | **NON-REDUNDANT** | threshold_off / threshold_off_gain0.3, 0.6, 1.0 | intermittent: divergent · sparse: divergent · memory_heavy: divergent · churn: divergent | — |
| Retention | **NON-REDUNDANT** | retention_off / retention_off_memory_x2, _x4 | intermittent: divergent · sparse: divergent · memory_heavy: divergent · churn: divergent | intermittent: 30 · sparse: 20 · memory_heavy: 29 · churn: 18 |
| Memory | **NON-REDUNDANT** | memory_off / memory_off_retention+0.05, +0.10 | intermittent: divergent · sparse: equivalent · memory_heavy: divergent · churn: divergent | intermittent: 10 · sparse: 5 · memory_heavy: 27 · churn: 15 |
| Transformation | **DESCRIPTIVE ONLY** | transform_off | intermittent: bit-identical · sparse: bit-identical · memory_heavy: bit-identical · churn: bit-identical | intermittent: 0 · sparse: 0 · memory_heavy: 0 · churn: 0 |
| Penetration | **DERIVED** | wave_state_off / adapt_all_carriers | intermittent: bit-identical · sparse: bit-identical · memory_heavy: bit-identical · churn: bit-identical | — |
| Return | **DESCRIPTIVE ONLY** | return_events_off | intermittent: bit-identical · sparse: bit-identical · memory_heavy: bit-identical · churn: bit-identical | — |
| Reconfiguration | **REDUCIBLE** | reconfigure_off / reconfigure_as_mutation | intermittent: equivalent · sparse: equivalent · memory_heavy: equivalent · churn: equivalent | intermittent: 1 · sparse: 0 · memory_heavy: 1 · churn: 23 |
| Difference | **DERIVED** | difference_relational | intermittent: equivalent · sparse: equivalent · memory_heavy: equivalent · churn: equivalent | intermittent: 0 · sparse: 0 · memory_heavy: 0 · churn: 0 |
| Reachability | **DERIVED** | — | — | — |
| Transition | **NON-REDUNDANT** | transition_off | intermittent: divergent · sparse: divergent · memory_heavy: divergent · churn: divergent | — |
| Cut | **NON-REDUNDANT** | cut_off | intermittent: equivalent · sparse: equivalent · memory_heavy: equivalent · churn: equivalent | intermittent: 6 · sparse: 0 · memory_heavy: 1 · churn: 0 |
| Disconnection | **UNRESOLVED** | disconnect_off | intermittent: bit-identical · sparse: equivalent · memory_heavy: bit-identical · churn: bit-identical | intermittent: 0 · sparse: 0 · memory_heavy: 0 · churn: 0 |
| Connection (closure) | **NON-REDUNDANT** | connect_off | intermittent: equivalent · sparse: divergent · memory_heavy: equivalent · churn: equivalent | intermittent: 14 · sparse: 2 · memory_heavy: 9 · churn: 7 |
| Weight adaptation | **NON-REDUNDANT** | adapt_off / adapt_all_carriers | intermittent: equivalent · sparse: equivalent · memory_heavy: equivalent · churn: equivalent | intermittent: 28 · sparse: 0 · memory_heavy: 20 · churn: 0 |
| Decay | **DESCRIPTIVE ONLY** | — | — | — |

### Largest downstream effects (stage 2)

| variant | regime | effects (relative, paired t) |
|---|---|---|
| cut_off | intermittent | 6: memory_dependence -28% (t=-4.51), difference:mean_final +26% (t=5.18), decays -12% (t=-4.64) |
| cut_off | memory_heavy | 1: removed_connections +154% (t=4.12) |
| connect_off | intermittent | 14: loops +189% (t=8.27), reconfigurations -76% (t=-10.27), largest_loop -55% (t=-6.61) |
| connect_off | sparse | 2: edgefinal -8% (t=-7.86), connections -6% (t=-7.77) |
| connect_off | memory_heavy | 9: loops +89% (t=7.91), reconfigurations -86% (t=-6.04), loop_fraction +29% (t=4.1) |
| connect_off | churn | 7: loops +102% (t=12.71), cuts +59% (t=5.46), reach_dynamic +27% (t=4.8) |
| reconfigure_off | intermittent | 1: one_way_share -9% (t=-4.27) |
| reconfigure_off | memory_heavy | 1: path_dependency +7% (t=4.63) |
| reconfigure_off | churn | 23: removed_connections +2644% (t=11.44), persistence +1055% (t=11.45), largest_loop +695% (t=7.2) |
| adapt_off | intermittent | 28: memory_dependence +179% (t=17.21), removed_connections -100% (t=-17.21), largest_loop -91% (t=-12.19) |
| adapt_off | memory_heavy | 20: removed_connections -100% (t=-4.55), persistence -86% (t=-5.12), reconfigurations -86% (t=-5.31) |
| adapt_all_carriers | intermittent | 18: memory_dependence +82% (t=7.69), removed_connections -43% (t=-6.72), largest_loop -38% (t=-6.11) |
| memory_off | intermittent | 10: loops +154% (t=8.82), new_connections -100% (t=-66.04), reconfigurations -84% (t=-14.68) |
| memory_off | sparse | 5: new_connections -100% (t=-6.06), topology_change -85% (t=-5.5), edgefinal -8% (t=-7.82) |
| memory_off | memory_heavy | 27: removed_connections +1610% (t=11.43), largest_loop +808% (t=9.73), persistence +757% (t=19.98) |
| memory_off | churn | 15: loops +128% (t=19.35), persistence +104% (t=5.88), new_connections -100% (t=-4.94) |
| retention_off | intermittent | 30: persistence -100% (t=-18.42), removed_connections -100% (t=-17.21), reconfigurations -100% (t=-26.81) |
| retention_off | sparse | 20: difference:mean_final -91% (t=-15.63), memory_dependence -90% (t=-7.1), path_dependency -86% (t=-7.31) |
| retention_off | memory_heavy | 29: persistence -100% (t=-6.6), removed_connections -100% (t=-4.55), reconfigurations -100% (t=-6.81) |
| retention_off | churn | 18: difference:mean_final -94% (t=-6.22), memory_dependence -92% (t=-6.71), path_dependency -85% (t=-6.11) |

### Full vs MINIMAL

MINIMAL = `{'threshold': 'on', 'fused_transition': True, 'retention': 'on', 'memory': 'on', 'transform': 'off', 'wave_state': 'off', 'return_events': 'off', 'adapt_source': 'dominant', 'reconfigure': 'mutation', 'cut': 'on', 'disconnect': 'on', 'connect': 'on', 'difference': 'node', 'transition': 'on'}`

Verdict: **EQUIVALENT in every regime**

| regime | stage 1 | criteria exceeded | stage 2 downstream effects | worst criterion distance ÷ tolerance |
|---|---|---|---|---|
| intermittent | equivalent | none | 0 | recurrent_loops 0.42 |
| sparse | equivalent | none | 0 | signature 0.08 |
| memory_heavy | equivalent | none | 0 | recurrent_loops 0.54 |
| churn | equivalent | none | 0 | signature 0.45 |

### Floors

| regime | ignitions/step | noise: event sequence | noise: response | 1e-9 perturbation first divergence |
|---|---|---|---|---|
| intermittent | 60.0 | 0.235 | 0.358 | never, never, never |
| sparse | 8.5 | 0.496 | 0.569 | never, never, never |
| memory_heavy | 20.3 | 0.272 | 0.691 | never, never, never |
| churn | 27.3 | 0.198 | 0.831 | never, never, never |

### Engine cost per variant (sequential, regime *intermittent*)

| variant | ms/step |
|---|---|
| full | 0.736 |
| fused_transition | 0.747 |
| threshold_off | 2.497 |
| threshold_off_gain0.3 | 3.301 |
| threshold_off_gain0.6 | 3.282 |
| threshold_off_gain1.0 | 3.241 |
| retention_off | 0.502 |
| retention_off_memory_x2 | 0.513 |
| retention_off_memory_x4 | 0.505 |
| memory_off | 0.600 |
| memory_off_retention+0.05 | 0.919 |
| memory_off_retention+0.10 | 1.031 |
| transform_off | 0.815 |
| wave_state_off | 0.818 |
| adapt_all_carriers | 0.758 |
| adapt_off | 0.610 |
| return_events_off | 0.749 |
| reconfigure_as_mutation | 0.736 |
| reconfigure_off | 0.737 |
| difference_relational | 0.900 |
| transition_off | 0.318 |
| cut_off | 0.760 |
| disconnect_off | 0.720 |
| connect_off | 0.547 |
| minimal | 0.696 |

### Dataflow audits

Arrays written per operation (observed):

- `inject (external input)` → diff
- `ignite` → ignite_count, last_ignite, refractory, wave_depth, wave_origin
- `propagate (transition)` → cause_edge, load, pending_depth, pending_origin
- `transform` → form
- `retain_and_decay` → diff, overload, refractory
- `remember (memory)` → memory
- `adapt_weights` → weight
- `cut` → alive, load
- `disconnect` → (nothing in the audited window)
- `connect` → alive, base_weight, dst, src, weight
- `reconfigure` → dst, load, overload

Influence (perturb one array; which *other* arrays change within 60 steps):

- `diff` → alive, base_weight, cause_edge, dst, form, ignite_count, last_ignite, load, memory, overload, pending_depth, pending_origin, refractory, src, transform, wave_depth, wave_origin, weight
- `theta` → alive, base_weight, cause_edge, diff, dst, form, ignite_count, last_ignite, load, memory, overload, pending_depth, pending_origin, refractory, src, wave_depth, wave_origin, weight
- `retention` → alive, base_weight, cause_edge, diff, dst, form, ignite_count, last_ignite, load, memory, overload, pending_depth, pending_origin, refractory, src, transform, wave_depth, wave_origin, weight
- `memory` → alive, base_weight, cause_edge, diff, dst, form, ignite_count, last_ignite, load, overload, pending_depth, pending_origin, refractory, src, wave_depth, wave_origin, weight
- `form` → **nothing else**
- `wave_origin` → **nothing else**
- `wave_depth` → **nothing else**
- `pending_origin` → wave_origin
- `pending_depth` → wave_depth
- `ignite_count` → **nothing else**
- `last_ignite` → **nothing else**
- `overload` → alive, base_weight, cause_edge, diff, dst, form, ignite_count, last_ignite, load, memory, pending_depth, pending_origin, refractory, src, wave_depth, wave_origin, weight
- `weight` → alive, base_weight, cause_edge, diff, dst, form, ignite_count, last_ignite, load, memory, overload, pending_depth, pending_origin, refractory, src, transform, wave_depth, wave_origin
- `load` → alive, base_weight, cause_edge, diff, dst, form, ignite_count, last_ignite, memory, overload, pending_depth, pending_origin, refractory, src, wave_depth, wave_origin, weight
- `capacity` → alive, base_weight, cause_edge, diff, dst, form, ignite_count, last_ignite, load, memory, overload, pending_depth, pending_origin, refractory, src, wave_depth, wave_origin, weight
- `transform` → form

Observer reconstruction of penetration annotations and returns: intermittent: penetrations agree=True, returns agree=True (57834 penetrations, 933 returns, cross-macro share 0.0933); sparse: penetrations agree=True, returns agree=True (6194 penetrations, 161 returns, cross-macro share 0.0633); memory_heavy: penetrations agree=True, returns agree=True (17096 penetrations, 310 returns, cross-macro share 0.1168); churn: penetrations agree=True, returns agree=True (24233 penetrations, 333 returns, cross-macro share 0.1071)
<!-- GENERATED:END -->

## 4. Derived classification, per primitive

* **Ignition — REDUCIBLE to thresholded transition.** A single fused operation (gate + emission) is bit-identical in
  every regime. What remains is not "ignition" as an operation but the **threshold gate of transition**.
* **Threshold gating — NON-REDUNDANT in every regime.** Continuous emission without a threshold, with gain
  compensation at 0.3/0.6/1.0, diverges on almost every criterion everywhere.
* **Transition — NON-REDUNDANT** in every regime (trivially: without it nothing couples).
* **Retention — NON-REDUNDANT** in every regime; memory-coupling compensation (×2, ×4) never recovers it (stage-2:
  18–30 downstream effects per regime).
* **Memory — NON-REDUNDANT, regime-dependent in magnitude.** Stage 1 does not separate it from noise in *sparse*; stage 2
  finds downstream effects in all four regimes (5 in sparse, up to 27 in memory_heavy). Retention compensation
  (+0.05, +0.10) never recovers it. Memory has two roles (threshold shift, closure gating); removal tests both.
* **Transformation — DESCRIPTIVE ONLY.** Removing it changes only its own `form` label; the influence audit shows
  perturbing `form` changes no other array. In this runtime, form is read by nothing.
* **Penetration — DERIVED.** The runtime needs only the dominant incoming connection of a configuration that passed its
  threshold (a transition record). Wave origin/depth are reconstructed exactly by an observer in every regime;
  removing them is bit-identical. *Caveat*: the dominant-connection selection rule is not reducible to "all
  successful carriers" — that variant has 18 systematic effects in *intermittent* (none elsewhere).
* **Return — DESCRIPTIVE ONLY.** Removing detection is bit-identical; the observer reconstructs returns exactly. Returns
  do not alter future transition conditions. (They are a subset of cycles; see the returns-vs-loops audit.)
* **Reconfiguration — REDUCIBLE to connection mutation.** Removal changes behaviour (strongly in *churn*: 23 downstream
  effects; marginal single effects in *intermittent* t = −4.3 and *memory_heavy* t = 4.6; none in *sparse*); the
  remove + create replacement is equivalent everywhere with zero systematic effects.
* **Difference — DERIVED.** Holding difference on connections (+ one self-held input term) and recomputing the
  per-configuration value as a sum is equivalent in every regime with zero systematic effects and zero first-step
  divergence at stage-1 horizon. The node-local value is a cache of relational state.
* **Reachability — DERIVED.** No operation writes reachability; it is computed from connection, permeability and
  constraint arrays.
* **Cut — NON-REDUNDANT, regime-dependent.** Downstream effects in *intermittent* (6; e.g. one-way flow share −12%,
  t = −9.5; mean difference +26%) and *memory_heavy* (1, marginal: disconnections +154%, t = 4.1); none in *sparse*,
  *churn*. As an *operation* it is connection removal; what is non-redundant is its load trigger.
* **Connection (closure) — NON-REDUNDANT** in every regime (e.g. loops +102% in churn, t = 12.7).
* **Weight adaptation — NON-REDUNDANT, regime-dependent.** 28 effects in *intermittent*, 20 in *memory_heavy*, none in
  *sparse*, *churn*.
* **Disconnection — UNRESOLVED.** It fires (its own removals drop 100%, t = −17 in intermittent), but no downstream
  effect is detectable in any regime. Absence of a detected effect is not evidence of redundancy; its trigger (weight
  < 0.03) is rare in all tested regimes.
* **Decay — DESCRIPTIVE ONLY.** A threshold-crossing label on retention's output; it writes no state.

## 5. Implementation choices (not results)

* The node-local `diff` array is kept in the minimal runtime as a cached aggregate of relational state: the relational
  representation is equivalent but costs more per step (see the cost table).
* Cut, disconnection, closure and reconfiguration are implemented as separate *triggers* of connection mutation;
  the operation underneath all of them is creation/removal/redirection of connections.
* Tolerance constants (2 × noise + 0.02; |t| > 4 and 2%) are fixed before looking at variant results; the noise
  control yields zero detections at these settings.

## 6. Philosophical interpretation (kept separate)

The named operations reduce to a smaller structure: **thresholded transition along connections, retention,
memory, and connection mutation with its triggers (load, co-ignition, adaptation)**. "Ignition", "penetration",
"return", "transformation" and "decay" are names for observations of that structure, not additional operations. This
is a statement about this runtime at this resolution, not about the world.

## 7. Unresolved questions

* Disconnection's operational role (rare trigger; no detected downstream effect).
* Whether transformation becomes non-redundant if forms were allowed to modulate transitions — a different model,
  not tested here.
* Regimes beyond the four tested (larger N, longer horizons, other generators) could reveal effects below the
  present resolution; the classification is relative to the tested set.
