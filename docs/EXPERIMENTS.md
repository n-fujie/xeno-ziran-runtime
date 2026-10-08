# Experiments

Five bundled presets (`xzr presets`) and the long published studies (`xzr study …`). Every preset file
(`backend/xzr/presets/*.json`) states its question, manipulated and fixed variables, measured outputs and what
it does not show; `xzr validate <preset>` prints exactly what will run.

## How a comparison is judged

Paired design: within a seed, the compared runs share world, generator seed, engine random stream and schedule —
only the manipulated thing differs. A **noise replicate** (same world, another random stream) is run alongside
and analysed identically; whatever it shows is a false positive. Across seeds:

* **conditions presets** (escalation harness, `xzr/experiments/escalation/stats.py`): per observation resolution
  (node, local, meso, macro, global), a family-wise sign-flip max-T test over all units × segments × features
  (α = 0.01 split over the five resolutions), an effect counting only above 2 % of the baseline, and
  equivalence when the 90 % interval lies within ±5 %. Status per resolution: `DETECTED`, `EQUIVALENT`,
  `UNRESOLVED` (neither shown — not "absent"); `REDUNDANT` when bit-identical in every seed. With fewer than 10
  seeds the test cannot reach its level (statuses are then not interpretable; the run says so).
* **history preset** (`xzr/experiments/history.py`): per metric, an exact two-sided sign-flip test on the paired
  differences against the intact branch (α = 0.01, ≥ 8 seeds), 2 % practical threshold, larger than every
  noise-branch difference; equivalence ±5 %. Not corrected across metrics — read it as exploratory.

Comparison between two runs (`xzr compare A B`) labels each status cell as *same*, *changed*, *newly detectable*,
*extinguished* or *missing*; within a run, a comparison detected (at macro or global resolution) in some
conditions and not others is *configuration-sensitive*. None of these labels means "novel": whether a newly
detectable difference matters theoretically is an interpretation made outside the software.

Variants of the reasoning layer used by the conditions presets (reference **C** = reasoning with the reference
structure; the variant is compared with C):

| | variant |
|---|---|
| A | no reasoning layer |
| B | same structure in the vocabulary-bearing representation |
| D | one status (conflicts resolved before propagation) |
| E | no eligibility tracking (every backed item acts) |
| F | least instead of greatest fixpoint |
| G | conflict defeats persist across evaluations |
| H | no dependency records |
| I | local records only (cross-cluster requirements dropped) |
| J | persistent records (immune to decay, fragmentation, loss) |
| K | mixed rules per reasoning cluster |

## `resolution-escalation` (A — operational resolution escalation)

* **Question** — at which observation resolutions is each structural difference (A, E, H vs C) systematic, and does
  that change with scale, topology, memory, coupling or horizon?
* **Manipulated** — n (600 / 1,500 / 3,000), topology (multi-region / small-world / modular), memory regime
  (short / medium / long), coupling (weak / medium / strong), horizon (400 / 1,200); one factor at a time.
* **Fixed** — world generator seed, reasoning structure (competing clusters, size 32), triggers, engine seeds.
* **Measured** — status per resolution per comparison per condition; configuration sensitivity across conditions.
* **Interpretation** — a difference detected at fine resolution only is *hidden at coarse resolution*; one detected
  in some conditions only is configuration-sensitive.
* **Does not show** — necessity or generality: one-factor-at-a-time around one reference, small worlds, short
  horizons. The full matrix (`xzr study matrix`, 63 conditions, up to 100,000 configurations and 40,000 steps) is
  the larger version; its results are in `backend/experiments/results/resolution/` and `docs/RESOLUTION_ESCALATION.md`.

## `history-reentry` (B — history re-entry)

* **Question** — does removing a region's retained history (memory) change what happens next, and does restoring it
  re-enter with a downstream difference? Also: does a fork carry the full history; what happens when history is
  moved to another region (configuration-crossing)?
* **Manipulated** — at step 150, on macro region `1`: none (intact), exact fork, removal, removal then re-adding
  the saved memory at step 200 (reactivation), moving it onto region `4` (migration).
* **Fixed** — world, engine seeds, a probe intervention (thresholds × 1.3 on region `6` at step 220).
* **Measured** — reachability, generation (field and region), discrimination (distinct shape signatures),
  intervention response (effect of the probe), later configuration (connections differing, final count); the four
  re-entry criteria; a verdict that only names history re-entry when all four are met.
* **Interpretation** — `fork` must be bit-identical to `intact` (the fork carries the complete state); every other
  branch is judged against the noise branch. The verdict names history re-entry only when all four criteria are
  measured; otherwise *history dependence*, *dependence not distinguished from trajectory noise*, or *no effect*.
* **Does not show** — that history re-entry is general: one region, one window, one world. The runtime is chaotic:
  a different random stream alone makes the later configuration diverge by about half of all connections, so
  effects of history operations must exceed that to be detected.

## `boundary-scale-window` (C — boundary / scale / temporal window sensitivity)

* **Question** — does the E/C and H/C distinction survive a closed boundary between clusters, a different scale,
  a shorter or longer window?
* **Manipulated** — boundary (closed at 25 % of the run), n (600 / 3,000), horizon (200 / 1,200).
* **Fixed** — topology, memory, coupling, reasoning structure, engine seeds.
* **Measured** — status per resolution per condition; the summary lists where each comparison is detected.
* **Does not show** — survival beyond these settings; failure to detect under a setting is not absence (read
  EQUIVALENT vs UNRESOLVED). Changing the observation apparatus beyond the five fixed resolutions, or the variable
  set, is not supported by this preset.

## `ablation` (D — ablation / removal)

* **Question** — which runtime mechanisms change downstream behaviour when removed?
* **Manipulated** — one runtime flag per variant (no reasoning layer): memory, retention, transform, wave state,
  return events, disconnection, reconfiguration, cut, connection creation.
* **Fixed** — world, engine seeds, all other flags.
* **Measured** — status per resolution for each ablated variant vs the full runtime.
* **Does not show** — theoretical necessity. A detected removal effect in one configuration does not make a
  mechanism irreducible; the primitive reduction study (`xzr study reduction`, `docs/REDUCTION.md`) tests
  reductions and parameter compensations across four dynamic regimes.

## `smoke`

Two seeds, one small condition: checks that installation, execution, result writing and classification work.
It supports no statistical claim (the run says so).

## E — target-coupled validation: not supported

The runtime has no mechanism that constructs new sensors, variables, observation routes or access
configurations, so it cannot separate access construction, target-coupled response, validation and revision.
No preset claims to; the closest existing instrument — the reasoning layer's world-responsive revision with its
open-loop replay control (`xzr study adaptivity`, `docs/RESOLUTION_ESCALATION.md`) — tests whether revisions
respond to the world, not whether a new variable is validated against a target.

## Representative results (v0.2.0, 12 seeds each)

Run with the commands in [REPRODUCIBILITY.md](REPRODUCIBILITY.md) on an Apple-silicon Mac (6 worker processes);
a rerun reproduced every status cell (`xzr compare`: 90 / 90 and 35 / 35 *same*).

* **resolution-escalation** (5.2 min) — the noise replicate C~ is detected in none of the 10 conditions. A (no
  reasoning layer) is detected at macro or global resolution in 7 of 10 conditions; E (no eligibility tracking)
  only in the reference condition — under weak coupling, n = 600 or a 1,200-step horizon it is detected at node
  and local resolution only (hidden at coarse resolution); H (no dependency records) only at n = 3,000 and under
  strong coupling.
* **boundary-scale-window** (2.5 min) — E/C survives none of the changed settings at coarse resolution: closing
  the boundary between clusters leaves it detected at node and local resolution only; H/C is detected only at
  n = 3,000. Both are configuration-sensitive.
* **ablation** (1 min) — removing memory, retention, connection creation or disconnection is detected; removing
  reconfiguration or cut is detected at global resolution only; removing transform or wave state is equivalent
  within ±5 % at every resolution (trajectories differ); removing return events is bit-identical (redundant in
  this configuration).
* **history-reentry** (22 s) — the fork is bit-identical to the intact continuation. Removal, reactivation and
  migration change every trajectory, but no measured effect exceeds the noise branch, whose own divergence
  reaches 48 % of connections: verdict *history dependence not distinguished from trajectory noise*. Of the
  re-entry criteria, retained prior difference and re-addressability hold; actual re-entry and a downstream
  difference were not detected. A larger region, a longer retained history or more seeds may change this.

## Long studies (`xzr study NAME`)

| name | what | wall time of the published run (7 worker processes) |
|---|---|---|
| matrix | resolution matrix, 63 conditions | 9.8 h (resumable) |
| disconnection | 8 disconnection structures × 6 implementations | 1.2 h |
| topology_triggers | cut vs reconfiguration triggers | 2.1 h |
| adaptivity | world-responsive revision vs open-loop replay | 2.6 h |
| clusters | multiple interacting reasoning clusters | 1.4 h |
| compression | long-run compression up to 40,000 steps | 0.5 h |
| reduction | primitive reduction (ablate, reduce, compensate) | 11 min |
| reason | reasoning-layer non-redundancy | 5 min |

They write `backend/experiments/results/` (resumable; the per-seed jobs under `resolution/jobs/` are not
committed). Their published findings and caveats: `docs/EXPERIMENT_RESULTS.md`, `docs/RESOLUTION_ESCALATION.md`,
`docs/REDUCTION.md`, `docs/LIMITATIONS.md`.
