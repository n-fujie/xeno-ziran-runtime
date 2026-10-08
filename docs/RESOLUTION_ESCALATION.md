# Operational resolution escalation

The question: are the reasoning-layer differences that the previous phase found to have no world-level effect
operationally redundant at the represented world level, or were they hidden by insufficient scale, topology, horizon, memory structure,
coupling or observation resolution?

The rule this phase follows: never conclude "no operational difference" when the actual result is "no difference
detected at this resolution". Invisibility is not redundancy.

Statement kinds are marked as in docs/EXPERIMENT_RESULTS.md: **[measured]**, **[derived]** (a fixed rule applied to
measured results), **[choice]** (an implementation choice the result depends on), **[interpretation]**,
**[unresolved]**.

## 1. What is compared

The reference structure is **C**: a two-level support graph with a greatest fixpoint. It is the terminology-free
structure that the previous phase found bit-identical to scorekeeping. Every other variant is compared with C in
the same world, on the same engine random stream and with the same schedule. The variant definitions are in
`reasonlab/structures.py`.

| | variant | exact structural difference from C |
|---|---|---|
| A | no reasoning layer | no reasoning-derived interventions |
| B | vocabulary | same structure expressed in the vocabulary-bearing representation (`practice/graph.py`) |
| D | one status | conflicts resolved before propagation; levels flow only out of eligible items |
| E | no eligibility | eligibility not tracked: every backed item acts at its level |
| F | least fixpoint | eligibility grown from the self-standing base instead of shrunk from all backed items |
| G | sticky conflicts | a defeat persists across evaluations while the defeater stays usable |
| H | no dependency records | requirements dropped; every item stands on its own level |
| I | local records | requirements that cross reasoning clusters are dropped |
| J | persistent records | records immune to decay on collapse, fragmentation and record loss |
| K | mixed rules | each reasoning cluster is evaluated with its own rule (greatest, single, least, backed) |
| C~ | noise control | C under another random stream (false-positive control) |

No effect is attributed to vocabulary. B is the only variant that uses the vocabulary, and it serves as the
control.

## 2. Factors and operational definitions [choice]

| factor | levels | operational definition |
|---|---|---|
| configurations | 1,500 · 10,000 · 100,000 | world size |
| horizon | 400 · 4,000 · 40,000 steps | run length (reasoning allowed from step 200) |
| topology | sparse random, dense random, modular, hierarchical, small world, highly clustered, weakly connected, bottlenecked, multi-region, nested multi-scale | `scenario/topologies.py` |
| memory | near-zero (decay 0.3), short (0.7), medium (0.8–0.95), long (0.99), external persistent (record region R held at decay 0.995, coupling 0.3), fragmented (fine clusters at 0.3 or 0.99), delayed return (R reaches the rest only through a 15-step relay) | memory decay / world-side memory condition |
| coupling | weak · medium · strong | effect of one binding at full level: threshold ×(1 ± 0.05 / 0.2 / 0.5); permeability × 0.9 / 0.6 / 0.2; memory condition decay 0.92 / 0.96 / 0.99 with coupling 0.05 / 0.15 / 0.35; eligibility freezes 1/512, 1/128 or 1/32 of the field; connection mutation 0.0002 / 0.001 / 0.005. The *realized* coupling (mean threshold shift, gated share, frozen share, memory-modified share, mutation rate) is measured in every run |
| mutation | low · medium topology (0.0005) · high topology (0.005) · high state (external input × 8) · mixed (0.002 and input × 4) | world-side connection mutation / exogenous difference input |
| return / delay | immediate (60 % reciprocation) · delayed (5-step relay replaces direct B → A) · multi-step (25) · none (a DAG: no return path anywhere) · competing (relays of 5 and 17) | between two modules A and B of a modular world |
| addressability | stable · partially unstable (mutation 0.002 on half the targeted regions) · highly unstable (0.01 on all) · locally stable / globally unstable (0.01 everywhere else) | connection stability of the regions that reasoning addresses |
| reasoning structure | 15 kinds (docs/REASONING_CONFIGURATION_MAP.md) | neutral support specifications |
| structure size | 9 · 32 · 128 · 512 · 2,048 items | |

Topologies were calibrated before any comparison was run [choice]. Each family's transmission gain was set so the
field sustains about 0.04 ignitions per configuration per step, so that topology rather than criticality varies.
Families with a discontinuous transition end above that target. Sparse random never reaches it (maximum 0.0099 at
gain 9); this is recorded as a property of that topology, not corrected. The calibration table is generated below.

The regions that reasoning addresses are hierarchy clusters. `Z0`–`Z31` are the 32 meso clusters, and `R` (= Z0)
is the record region. Reasoning cluster k binds to regions r with r mod k_clusters = k.

Reasoning is enabled by operational conditions calibrated on the run's own pre-reasoning checks:
- memory in R at least 0.5 × its baseline;
- activity in R at least 0.25 × its baseline;
- connection stability of R at least 0.9.

When a condition fails, reasoning collapses and its records decay. Three world-responsive triggers are active in
the matrix: memory level, prediction mismatch and failed intervention. All ten triggers are active in the
adaptivity study.

## 3. Observation resolutions

| resolution | units |
|---|---|
| exact | per-step state signature, per-window fingerprints |
| node | configurations (a 4,000-configuration sample at 10,000 and 100,000) |
| local | the 512 finest hierarchy clusters |
| meso | 32 clusters |
| macro | 8 clusters |
| global | whole-field aggregates (activity, memory, difference, out-degree, closure, cuts, removals, reconfigurations, memory-dependent share, penetrations, reachable share, connections) |

Each unit is described by four features: activity, memory, difference and out-degree.

## 4. Statistics [choice]

**Pairing.** For every engine seed, all variants share the world and the random stream. The noise replicate
changes only the stream.

**Tests.** Each resolution has two families of paired differences:
1. segment means: 8 time segments × features × units;
2. the time average over the post-reasoning segments.

Each family gets a sign-flip max-|t| permutation test, which controls the family-wise error over every unit,
segment and feature. With ≤ 14 seeds all 2^S patterns are enumerated; the 48-seed arm uses 4,096 random patterns
plus the identity. The level is 0.01 per comparison, split over 5 resolutions × 2 families (0.001 each), and 12
seeds give a minimum attainable p of 0.00049.

**Effect.** An effect counts when it is family-wise significant **and** at least 2 % of that unit's baseline. A
difference that is identical in every seed has no random component; it is reported as deterministic and counted
when it is at least 2 %.

**Equivalence.** A resolution is EQUIVALENT only when nothing is detected **and** the median 90 % confidence
half-width of its time-aggregated differences is ≤ 5 % (two-one-sided-tests logic). Otherwise it is UNRESOLVED.

**Resolution floor.** The confidence half-width reached by the noise control, per resolution. This floor is the
smallest difference the design could exclude.

## 5. Classification rules [derived]

Per comparison and condition:

| label | rule |
|---|---|
| REDUNDANT | bit-identical represented output in every seed (no difference detected; not a claim of absence) |
| NON-REDUNDANT | systematic difference at meso, macro or global resolution |
| TRANSIENT | … and every coarse detection has a transient time pattern |
| TIME-WINDOW-DEPENDENT | … and the coarse onset is in segment ≥ 2 of a ≥ 4,000-step run |
| HIDDEN AT COARSE RESOLUTION | trajectories differ (and possibly node / local are systematic), while macro **and** global are EQUIVALENT |
| UNRESOLVED | trajectories differ and macro / global equivalence is not established |

Across conditions, per structural difference:
- **TOPOLOGY-, MEMORY-, SCALE-, TIME-WINDOW- or REGIME-DEPENDENT** (for coupling, mutation, return, addressability
  or structure kind): visible at some levels of that factor and equivalent, with coarse equivalence established within the stated
  margin, at others. An unresolved level does not count as equivalent.
- **Globally non-redundant**: visible at macro or global resolution in at least one condition.
- **Locally non-redundant only**: systematic at node, local or meso resolution but never at macro or global.
- **REDUNDANT**: bit-identical in every condition where it was run. This is an operational label: no difference was
  detected within the represented and measured state under the stated comparison procedure. It is not a claim of
  genuine absence, which would need independent justification.

## 6. Results (generated from the result files)

<!-- GENERATED:BEGIN -->
Result files: `backend/experiments/results/resolution/*.json` → `summary.json`. Rules: family-wise α = 0.01 per comparison, split over 5 resolutions × 2 time families (α = 0.0010 each); practical threshold 2%; equivalence bound (smallest effect of interest) 5%.

Noise control (reference C vs C under another random stream, analysed identically): detections in 0 of 63 conditions (none).

### Classification per condition (vs reference structure C)

NR = systematic difference at meso, macro or global resolution · HID = trajectories differ, macro and global equivalent · UNR = coarse equivalence not established · RED = bit-identical

| condition | n | steps | A | B | D | E | F | G | H | I | J | K | C~ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| n:100000 | 100,000 | 4,000 | NR | · | · | NR | HID | · | NR | · | · | · | HID |
| horizon:40000 | 1,500 | 40,000 | UNR | · | RED | UNR | UNR | UNR | UNR | · | · | · | UNR |
| n:10000 | 10,000 | 4,000 | NR | · | RED | HID | NR | HID | HID | RED | · | RED | HID |
| n:100000:h400 | 100,000 | 400 | NR | · | RED | NR | HID | NR | NR | RED | · | RED | HID |
| reference | 1,500 | 4,000 | NR | RED | RED | UNR | UNR | UNR | UNR | RED | UNR | RED | UNR |
| structure:strongly_cyclic | 1,500 | 4,000 | RED | RED | RED | UNR | RED | UNR | UNR | RED | RED | RED | UNR |
| structure:multi_cycles | 1,500 | 4,000 | RED | RED | RED | UNR | RED | RED | UNR | RED | RED | RED | UNR |
| structure:dense_conflicts | 1,500 | 4,000 | UNR | RED | RED | UNR | UNR | UNR | UNR | RED | UNR | RED | UNR |
| structure:unsupported_addressable | 1,500 | 4,000 | NR | RED | UNR | UNR | RED | RED | NR | RED | HID | RED | UNR |
| size:9 | 1,500 | 4,000 | UNR | RED | RED | UNR | RED | RED | RED | RED | UNR | RED | UNR |
| size:128 | 1,500 | 4,000 | NR | RED | RED | NR | HID | UNR | NR | RED | NR | UNR | UNR |
| memory:near_zero | 1,500 | 4,000 | NR | · | RED | UNR | UNR | UNR | UNR | RED | HID | RED | UNR |
| memory:short | 1,500 | 4,000 | NR | · | RED | UNR | UNR | UNR | UNR | RED | HID | RED | UNR |
| memory:long | 1,500 | 4,000 | NR | · | RED | UNR | UNR | UNR | UNR | RED | UNR | HID | UNR |
| memory:external_persistent | 1,500 | 4,000 | NR | · | RED | UNR | UNR | UNR | UNR | RED | UNR | HID | UNR |
| memory:fragmented | 1,500 | 4,000 | UNR | · | RED | UNR | UNR | UNR | UNR | RED | UNR | UNR | UNR |
| memory:delayed_return | 1,500 | 4,000 | NR | · | RED | UNR | UNR | UNR | NR | RED | HID | HID | UNR |
| mutation:medium_topology | 1,500 | 4,000 | HID | · | RED | HID | UNR | UNR | UNR | RED | HID | RED | UNR |
| mutation:high_topology | 1,500 | 4,000 | HID | · | RED | HID | HID | HID | HID | RED | HID | RED | HID |
| mutation:high_state | 1,500 | 4,000 | NR | · | RED | NR | HID | HID | HID | RED | HID | RED | HID |
| mutation:mixed | 1,500 | 4,000 | NR | · | RED | NR | HID | HID | UNR | RED | HID | RED | UNR |
| address:partially_unstable | 1,500 | 4,000 | NR | · | RED | UNR | UNR | UNR | UNR | RED | UNR | HID | UNR |
| address:highly_unstable | 1,500 | 4,000 | RED | · | RED | RED | RED | RED | RED | RED | RED | RED | UNR |
| address:locally_stable_globally_unstable | 1,500 | 4,000 | NR | · | RED | UNR | UNR | UNR | UNR | RED | UNR | RED | UNR |
| structure:local_external_memory | 1,500 | 4,000 | UNR | · | RED | UNR | RED | RED | NR | RED | UNR | RED | UNR |
| structure:distributed_external_memory | 1,500 | 4,000 | UNR | · | RED | UNR | RED | UNR | NR | RED | UNR | RED | UNR |
| structure:record_fragmentation | 1,500 | 4,000 | NR | · | RED | UNR | RED | RED | UNR | RED | UNR | RED | UNR |
| structure:record_loss_reconstruction | 1,500 | 4,000 | NR | · | RED | HID | RED | RED | UNR | RED | HID | RED | UNR |
| topology:sparse_random | 1,500 | 4,000 | UNR | · | RED | UNR | UNR | HID | UNR | RED | · | RED | UNR |
| topology:dense_random | 1,500 | 4,000 | UNR | · | RED | UNR | UNR | HID | UNR | RED | · | RED | UNR |
| topology:modular | 1,500 | 4,000 | NR | · | RED | HID | HID | HID | HID | RED | · | RED | HID |
| topology:hierarchical | 1,500 | 4,000 | NR | · | RED | UNR | UNR | UNR | UNR | RED | · | RED | UNR |
| topology:small_world | 1,500 | 4,000 | UNR | · | RED | UNR | UNR | HID | UNR | RED | · | HID | UNR |
| topology:highly_clustered | 1,500 | 4,000 | NR | · | RED | UNR | UNR | UNR | UNR | RED | · | RED | UNR |
| topology:weakly_connected | 1,500 | 4,000 | UNR | · | RED | UNR | UNR | RED | UNR | RED | · | RED | UNR |
| topology:bottlenecked | 1,500 | 4,000 | UNR | · | RED | UNR | UNR | UNR | UNR | RED | · | HID | UNR |
| topology:nested_multiscale | 1,500 | 4,000 | UNR | · | RED | UNR | UNR | UNR | UNR | RED | · | HID | UNR |
| coupling:weak | 1,500 | 4,000 | UNR | · | RED | UNR | UNR | UNR | UNR | RED | · | HID | UNR |
| coupling:strong | 1,500 | 4,000 | NR | · | HID | UNR | UNR | UNR | UNR | RED | · | UNR | UNR |
| return:immediate | 1,500 | 4,000 | NR | · | RED | HID | HID | HID | HID | RED | · | RED | HID |
| return:delayed | 1,500 | 4,000 | HID | · | RED | HID | HID | HID | HID | RED | · | RED | HID |
| return:multi_step_delayed | 1,500 | 4,000 | HID | · | RED | UNR | HID | HID | HID | RED | · | RED | UNR |
| return:none | 1,500 | 4,000 | HID | · | RED | HID | HID | HID | HID | RED | · | HID | HID |
| return:competing | 1,500 | 4,000 | NR | · | RED | HID | HID | HID | HID | RED | · | RED | UNR |
| structure:shallow_acyclic | 1,500 | 4,000 | UNR | · | RED | UNR | RED | UNR | NR | RED | · | RED | UNR |
| structure:deep_chain | 1,500 | 4,000 | UNR | · | RED | UNR | UNR | RED | UNR | RED | · | RED | UNR |
| structure:sparse_conflicts | 1,500 | 4,000 | UNR | · | HID | UNR | RED | UNR | UNR | RED | · | RED | UNR |
| structure:mixed_fixpoint_regions | 1,500 | 4,000 | UNR | · | HID | UNR | UNR | RED | UNR | RED | · | UNR | UNR |
| structure:multiple_clusters | 1,500 | 4,000 | UNR | · | HID | UNR | UNR | HID | UNR | RED | · | UNR | UNR |
| structure:partially_incompatible_rules | 1,500 | 4,000 | UNR | · | RED | UNR | UNR | UNR | UNR | RED | · | UNR | UNR |
| power:48seeds | 1,500 | 4,000 | NR | · | RED | NR | UNR | HID | UNR | · | · | · | UNR |
| strong×topology:sparse_random | 1,500 | 4,000 | UNR | · | RED | UNR | HID | · | UNR | · | · | · | UNR |
| strong×topology:dense_random | 1,500 | 4,000 | NR | · | RED | UNR | UNR | · | UNR | · | · | · | UNR |
| strong×topology:modular | 1,500 | 4,000 | NR | · | RED | HID | HID | · | HID | · | · | · | HID |
| strong×topology:hierarchical | 1,500 | 4,000 | NR | · | RED | UNR | UNR | · | UNR | · | · | · | UNR |
| strong×topology:small_world | 1,500 | 4,000 | UNR | · | RED | UNR | UNR | · | UNR | · | · | · | UNR |
| strong×topology:highly_clustered | 1,500 | 4,000 | NR | · | RED | UNR | UNR | · | NR | · | · | · | UNR |
| strong×topology:weakly_connected | 1,500 | 4,000 | NR | · | RED | UNR | HID | · | UNR | · | · | · | UNR |
| strong×topology:bottlenecked | 1,500 | 4,000 | NR | · | RED | UNR | HID | · | UNR | · | · | · | UNR |
| strong×topology:nested_multiscale | 1,500 | 4,000 | NR | · | RED | UNR | UNR | · | UNR | · | · | · | UNR |
| size:512 | 1,500 | 4,000 | NR | · | · | UNR | HID | · | NR | · | · | · | UNR |
| horizon:400 | 1,500 | 400 | NR | RED | RED | NR | UNR | HID | UNR | RED | HID | RED | UNR |
| size:2048 | 1,500 | 4,000 | NR | · | · | UNR | UNR | · | NR | · | · | · | UNR |

### Per structural difference

| vs C | difference | conditions | visible (meso+) | visible at macro/global | local only | hidden | unresolved | bit-identical | labels |
|---|---|---|---|---|---|---|---|---|---|
| A | no reasoning layer (vs reasoning with the reference structure) | 63 | 34 | 30 | 10 | 10 | 21 | 3 | HIDDEN AT COARSE RESOLUTION, NON-REDUNDANT, REGIME-DEPENDENT, TIME-WINDOW-DEPENDENT |
| B | vocabulary-bearing representation of the same structure | 8 | 0 | 0 | 0 | 0 | 0 | 8 | REDUNDANT |
| C~ | noise control: the reference under another random stream | 63 | 0 | 0 | 0 | 10 | 53 | 0 | HIDDEN AT COARSE RESOLUTION |
| D | one-status support graph | 60 | 0 | 0 | 0 | 4 | 1 | 55 | HIDDEN AT COARSE RESOLUTION |
| E | eligibility tracking disabled (backed only) | 63 | 7 | 5 | 6 | 13 | 45 | 1 | HIDDEN AT COARSE RESOLUTION, NON-REDUNDANT, REGIME-DEPENDENT, SCALE-DEPENDENT, TIME-WINDOW-DEPENDENT |
| F | least instead of greatest fixpoint | 63 | 1 | 1 | 0 | 17 | 34 | 11 | HIDDEN AT COARSE RESOLUTION, NON-REDUNDANT, SCALE-DEPENDENT |
| G | conflict defeats persist across evaluations | 51 | 1 | 1 | 0 | 16 | 24 | 10 | HIDDEN AT COARSE RESOLUTION, NON-REDUNDANT, SCALE-DEPENDENT, TRANSIENT |
| H | no dependency records | 63 | 11 | 8 | 6 | 13 | 40 | 2 | HIDDEN AT COARSE RESOLUTION, NON-REDUNDANT, SCALE-DEPENDENT, TIME-WINDOW-DEPENDENT, TOPOLOGY-DEPENDENT |
| I | local-only records (cross-cluster requirements dropped) | 49 | 0 | 0 | 0 | 0 | 0 | 49 | REDUNDANT |
| J | records persistent (immune to decay, fragmentation, loss) | 25 | 1 | 1 | 0 | 10 | 11 | 3 | HIDDEN AT COARSE RESOLUTION, NON-REDUNDANT |
| K | mixed rules per cluster | 49 | 0 | 0 | 0 | 9 | 6 | 34 | HIDDEN AT COARSE RESOLUTION |

### Resolution floor (noise control: median 90 % CI half-width of time-aggregated summaries)

| design | node | local | meso | macro | global | conditions |
|---|---|---|---|---|---|---|
| n=100000 horizon=4000 seeds=12 | 40.1% | 7.4% | 2.2% | 1.6% | 0.7% | 1 |
| n=1500 horizon=40000 seeds=12 | 51.0% | 45.0% | 33.0% | 25.5% | 13.5% | 1 |
| n=10000 horizon=4000 seeds=12 | 39.8% | 17.9% | 6.7% | 4.7% | 2.6% | 1 |
| n=100000 horizon=400 seeds=12 | 58.4% | 12.6% | 4.4% | 2.5% | 1.9% | 1 |
| n=1500 horizon=4000 seeds=12 | 42.0% | 32.2% | 17.4% | 10.6% | 6.6% | 57 |
| n=1500 horizon=4000 seeds=48 | 26.1% | 19.9% | 9.3% | 5.4% | 3.6% | 1 |
| n=1500 horizon=400 seeds=12 | 69.8% | 55.2% | 28.4% | 19.1% | 11.5% | 1 |

### Regime calibration (transmission gain for a common sustained activity of 0.04)

| family | n | gain | activity reached | reached |
|---|---|---|---|---|
| D:bottleneck | 1,500 | 3.172 | 0.0435 | True |
| D:single_bridge | 1,500 | 3.2223 | 0.04345 | True |
| bottlenecked | 1,500 | 3.098 | 0.05996 | True |
| dense_random | 1,500 | 4.8329 | 0.19366 | True |
| hierarchical | 1,500 | 2.8299 | 0.04379 | True |
| highly_clustered | 1,500 | 2.753 | 0.04013 | True |
| modular | 1,500 | 3.235 | 0.10279 | True |
| multi_region | 10,000 | 2.7314 | 0.0445 | True |
| multi_region | 100,000 | 2.8077 | 0.04745 | True |
| multi_region | 1,500 | 2.753 | 0.04067 | True |
| nested_multiscale | 1,500 | 3.0858 | 0.04057 | True |
| small_world | 1,500 | 2.6363 | 0.04179 | True |
| sparse_random | 1,500 | 9.0 | 0.00994 | False |
| weakly_connected | 1,500 | 3.1347 | 0.052 | True |

### Reversibility (variant reverted to the reference rule at mid-run)

| condition | variant | unreverted | reverted | systematic difference after the revert (node · local · meso · macro · global) | irreversible |
|---|---|---|---|---|---|
| horizon:40000 | E | UNRESOLVED | UNRESOLVED | no · no · no · no · no | not established: exact divergence persists; coarse equivalence after the revert not resolved |
| reference | D | REDUNDANT | REDUNDANT | no · no · no · no · no | no divergence (bit-identical) |
| reference | E | UNRESOLVED | UNRESOLVED | no · no · no · no · no | not established: exact divergence persists; coarse equivalence after the revert not resolved |
| reference | F | UNRESOLVED | UNRESOLVED | no · no · no · no · no | not established: exact divergence persists; coarse equivalence after the revert not resolved |
| reference | G | UNRESOLVED | UNRESOLVED | no · no · no · no · no | not established: exact divergence persists; coarse equivalence after the revert not resolved |
| reference | H | UNRESOLVED | UNRESOLVED | no · no · no · no · no | not established: exact divergence persists; coarse equivalence after the revert not resolved |
| horizon:400 | D | REDUNDANT | REDUNDANT | no · no · no · no · no | no divergence (bit-identical) |
| horizon:400 | E | NON-REDUNDANT | NON-REDUNDANT | yes · yes · yes · no · no | irreversible: systematic difference persists after the revert |
| horizon:400 | F | UNRESOLVED | HIDDEN AT COARSE RESOLUTION | no · no · no · no · no | exact divergence persists (never re-converges); no systematic difference after the revert |
| horizon:400 | G | HIDDEN AT COARSE RESOLUTION | REDUNDANT | no · no · no · no · no | no divergence (bit-identical) |
| horizon:400 | H | UNRESOLVED | UNRESOLVED | no · no · no · no · no | not established: exact divergence persists; coarse equivalence after the revert not resolved |

### Omitted from the design

- **full_factorial**: not run; one-factor-at-a-time around the reference plus the listed crossings
- **n=10000**: only at the reference condition (4,000 steps); no factor sweeps at 10,000
- **n=100000**: reference condition only, at 400 steps (9 variants) and 4,000 steps (variants A, C, E, F, H); no 40,000-step run
- **horizon=40000**: reference condition only, n = 1,500, variants A, C, D, E, F, G, H
- **variant J**: run only where records can behave differently (record dynamics, collapse regimes, reference)
- **variant B**: vocabulary control run in the reference and in 8 structural conditions
- **crossings**: only strong coupling × topology
- **graph sizes 512 / 2048**: variants A, C, E, F, H only (compiling 512–2048 bindings per check makes the other variants ~2 h each)
<!-- GENERATED:END -->

## 7. Classification, then interpretation

Every statement below refers to the generated tables above or to the answer records in docs/EXPERIMENT_RESULTS.md,
where each effect is given with its experiment ID, confidence half-width, noise comparison and seed count. No number
is typed here.

**[measured] The noise floor sets what "no difference" can mean.** At 1,500 configurations and 4,000 steps, the
time-aggregated macro and global summaries of an *independent replicate* (C~) cannot be pinned down within the 5 %
equivalence bound. Most comparisons there are therefore UNRESOLVED, and the correct reading is "not resolvable at
this design", not "no effect".

The floor falls with:
- more seeds (the 48-seed arm);
- larger worlds (10,000 and 100,000).

At 100,000 configurations, macro and global equivalence is decidable. There, differences that were UNRESOLVED at
1,500 separate into two kinds:
- **HIDDEN AT COARSE RESOLUTION**: trajectories differ and the coarse aggregates are equivalent;
- **NON-REDUNDANT** at meso or macro scale.

The noise control never produced a detection.

**[measured] Trajectories diverge whenever compiled interventions differ.** This holds for every structural variant.
A single intervention difference makes the chaotic field decorrelate at node level within a few hundred steps: the
divergence ratio approaches the noise replicate's. Exact divergence alone therefore marks a difference as real and
caused, but not as specific. That is why "hidden" is sub-labelled *exact-only* when nothing is systematic at any
resolution.

**[derived] Structure by structure** (details: docs/REASONING_CONFIGURATION_MAP.md):

| structure | result |
|---|---|
| vocabulary (B), local-only records (I) | bit-identical in every condition where they were run |
| one status (D), mixed rules (K) | never systematic at any resolution: bit-identical or hidden in most conditions, unresolved in a few |
| no eligibility (E), no dependency records (H) | systematic at meso, macro or global in a minority of conditions: larger worlds, some noise regimes, some structures and sizes; hidden elsewhere, unresolved in most 1,500-configuration conditions. Dependence is labelled per factor; see the map |
| least fixpoint (F), sticky conflicts (G), persistent records (J) | systematic in single conditions only; otherwise hidden, redundant or unresolved |
| no reasoning layer (A) | visible at coarse resolution in many conditions (counts in the per-structure table); bit-identical where the reference structure has no active binding (see below) or where reasoning is never enabled |

**[measured] Self-defeating reference structures.** Under the reference rule (two-level, greatest fixpoint, a tied
conflict defeats both items), the deep chain and both cyclic structures have **no active binding at all**. Bottleneck propagation gives every item on a support path the same level. A conflict on that path is
therefore a tie, the roots are removed, and the rest loses its justification.

In those worlds the reference applies no reasoning interventions, so "no reasoning" equals it. The descriptors table
lists the active bindings of every structure. This is a property of the generated structures under this rule, not of
the harness. It limits what the cyclic and deep structures can show about the reference.

**[measured] Topology calibration.** Sparse random topology cannot sustain the common activity regime at any gain.
This is recorded as a property of that topology–parameter combination, and in that world reasoning collapses for most
of the run. Families with a discontinuous transition run above the target activity.

**[interpretation]** What the phase adds to the previous one:
- The earlier null results for the structural distinctions were largely a resolution limit.
- With enough configurations some distinctions become coarse-visible, but only as small effects in specific
  configurations.
- Most remain hidden: they change which interventions act, and therefore the exact trajectory, while leaving the
  macro and global shape equivalent.
- The vocabulary itself remains without any operational trace.
