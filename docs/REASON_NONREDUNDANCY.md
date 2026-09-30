# Reasoning-layer non-redundancy

Question: when, if ever, does the reasoning / scorekeeping layer produce an operational difference the base runtime
cannot reproduce at the same descriptive resolution — and is anything operationally non-redundant attributable to
the commitment/entitlement **vocabulary**, as opposed to the **transition structure** underneath it?

Result files: `backend/experiments/results/reason.json` (full), `final_results.json` (summary). Suite:
`python -m xzr.experiments.reason experiments/results/reason.json` (≈ 5 min on 8 cores). Scenario `reason-lab`
(1,500 configurations; record region R, regions A and B with boundaries BA/BB; 9 illustrative claims — sample
material, not asserted by the platform).

## 1. Method (implementation choices)

* **Representations** (same world, seed, edits, run length):
  A. `none` — operational runtime only;
  B. `scorekeeping` — commitment + entitlement (practice/graph.py);
  C. reduced reasoning — `scorekeeping_no_entitlement` (every commitment counts as entitled) and `support_single`
     (one status);
  D. terminology-free support graph (practice/support.py: items, levels, requirements, conflicts, eligibility) —
     `support_greatest` (greatest fixpoint), `support` (least fixpoint), `support_backed_only` (no eligibility
     check; the terminology-free counterpart of C/no-entitlement). support.py contains none of the words commitment,
     entitlement, Brandom, Wolfendale, responsibility, human (enforced by a test) and uses different algorithms
     (priority-queue bottleneck propagation; eligibility grown or shrunk explicitly).
  plus `memoryless` (a reactive policy that re-applies groundings to the initial specification each check — no
  persistent reasoning state) and `replay` (the base runtime applying a recorded intervention schedule).
* **Closed loop** (`reasonlab/loop.py`): world → probes → grounded revisions (only while enabled) → compile →
  operational interventions through `InterventionGate` (threshold, permeability, memory, eligibility/freeze,
  mutation/addressability) → world. The reasoning layer cannot write world state (tests:
  `test_intervention_gate_accepts_only_operational_overlay_records`,
  `test_reasoning_layer_never_writes_world_state_directly`).
* **Two levels of difference, never conflated.** *Intervention level*: which operational interventions are in force,
  compared exactly per check as the set of (operation, target set, factor). *World level*: a systematic effect on the
  world trajectory — 8 paired world seeds × 400 steps, paired t on ~40 scalar summaries, |t| > 4 and > 2% (same rule
  as the reduction study). A single summary just over threshold (|t| < 5) is reported as *marginal*, not as a
  demonstrated effect.
* **Enabling conditions** are measured operational properties (memory in R; stability of R's connections; activity
  in R; reach R→A; mutation rate), each configurable. The word “human” is never an enabling condition.

## 2. Measured results

### 2.1 Vocabulary vs structure (random claim graphs; 3,000 graphs × 4 random edits = 12,000 states)

| representation | compared with | states that disagree | located in structural cause |
|---|---|---|---|
| support graph, greatest fixpoint (no scorekeeping terms) | scorekeeping | **0** | — |
| support graph, backed-only (no eligibility check) | scorekeeping without entitlement | **0** | — |
| support graph, least fixpoint | scorekeeping | 295 | 295 (cycle 163 · unentitled support 225 · conflict scope 212) |
| single-status support graph | scorekeeping | 941 | 941 (cycle 344 · unentitled support 542 · conflict scope 834) |
| scorekeeping without entitlement tracking | scorekeeping | 8,574 | 8,574 (unentitled support 8,574 · …) |

Causes (not exclusive): *cycle* = on/downstream of a dependency cycle (fixpoint choice); *unentitled support* =
downstream of a committed-but-not-entitled claim (support flows through commitment in two-status scorekeeping, only
through eligibility with one status); *conflict scope* = in/downstream of an incompatibility whose other member is
committed but not finally entitled (which items conflicts are resolved among, and whether a defeat is undone when the
defeater later loses entitlement — a persistence rule inside the fixpoint). Every disagreement lies within these;
zero residuals.

### 2.2 In the world (8 paired seeds, 400 steps)

| comparison | identical runs | interventions differ (share of checks) | systematic world effects |
|---|---|---|---|
| reasoning layer vs none | 0/8 | 0.75 | memory dependence +157% (t = 9.1); closure rate +9% (t = 6.5) |
| vocabulary: scorekeeping vs support graph (greatest fixpoint) | **8/8** | 0.00 | none (bit-identical) |
| vocabulary under an edit (remove concept “human”) | **8/8** | 0.00 | none (bit-identical) |
| fixpoint choice: greatest vs least | 8/8 | 0.00 | none (the lab graph has no cycles) |
| two-status vs single-status | 0/8 | 0.72 | none detected |
| entitlement tracking on vs off | 0/8 | 0.72 | none detected |
| persistent reasoning state vs memoryless policy | 0/8 | 0.35 | none detected |
| edit: remove concept “human” | 0/8 | 0.58 | marginal (memory dependence −10%, t = −4.7) |
| edit: remove concept “responsibility” | 0/8 | 0.62 | none detected |
| counterfactual discrimination (same interventions, different dependency structure, same edit) | 0/8 | 0.72 | none detected |

The ten `philosophical_nonredundancy` scenarios (single world seed, every representation) agree: the
terminology-free support graph (greatest fixpoint; backed-only in scenario 5) gives a **bit-identical world
trajectory and intervention schedule in 10/10 scenarios**, and the base runtime **replaying the recorded
intervention schedule reproduces the scorekeeping run exactly in 10/10**.

### 2.3 The seven criteria

| criterion | kind | result | counts as non-redundant? |
|---|---|---|---|
| transition prediction | operational | intervention-change accuracy 0.854 with every feature set (base rate 0.75); activity R² 0.9675 (ops) → 0.9679 (+reasoning) vs 0.9686 (+history) | **no** — reasoning features add nothing beyond operational history |
| intervention precision | operational | best single reasoning edit changes 0.67 other modifiers per targeted modifier; direct operational edit 0 | **no** — worse |
| compression of recurrent structure | description length | semantic intervention changes 6–13 vs reasoning 26–29 tokens (25 static + 1–4 dynamic) over 400 steps | **no** at this horizon (dynamic part alone would compress; unresolved for long horizons) |
| error detection | bookkeeping | recompiling from dependency records detects orphan/lost/tampered modifiers 100%, 0% false alarms; operational-only checks 0% | **yes, by construction of dependency records** — identical for the terminology-free graph |
| counterfactual discrimination | operational | intervention level: identical before the edit, differ at 72% of checks after it; world level: not detected (8 seeds; 3/9 matrix rows marginal) | **intervention level only** |
| dependency tracing | bookkeeping | recall 1.00 (scorekeeping), 1.00 (support graph), 0.00 (operational only) | **yes, by construction** — vocabulary-independent |
| reconfiguration control | operational | share of checks inside the grounding bands: scorekeeping 0.028, memoryless 0.069, replay 0.056, none 0 | **no** |

### 2.4 Phases (pre → reasoning → degraded)

Single world, reasoning allowed from t = 150, external memory of R degraded at t = 450:
enabling conditions met from t ≈ 90 (not yet allowed); reasoning active t = 150–460; collapse at **t = 470**.
Commitment and entitlement distinctions (would a one-status or no-entitlement representation compile different
interventions *now*?) are **operative in 31 of 32 reasoning checks, from t = 160**, and in 0 checks in the pre and
collapsed phases. They become operative when a grounded revision asserts K9 (region B quiet), K9 defeats K4 through
their incompatibility, and K8 — self-standing and derived from K4 — keeps its support only in the two-status
representation.

### 2.5 Enabling conditions (each degraded at t = 150; 6 paired world seeds)

| candidate condition | gated: collapsed share | ungated: world effect vs none | ungated: vs memoryless | ungated: counterfactual |
|---|---|---|---|---|
| (none degraded — reference) | 0.00 | yes | no | marginal |
| external memory | 0.83 | **no** | no | no |
| stable addressability | 0.83 | yes | no | no |
| repeated interaction | 0.33 | marginal | no | marginal |
| traceable dependency structure | 0.83 | yes | no | no |
| incompatibility tracking (reasoning-internal) | 0.00 | yes | no | no |
| inferential interface stability (reasoning-internal) | 0.00 | yes | no | no |
| low mutation rate | 0.83 | yes | no | marginal |
| shared record persistence (reasoning-internal) | 0.13 (indirect) | **no** | **yes** (4 effects) | no |

Gated collapse is *by construction* for conditions measured by a gate (external memory, stable addressability,
repeated interaction, traceable dependency, mutation) — an implementation choice. Shared record persistence is not
gated; its 0.13 collapse is an indirect closed-loop effect (decaying records weaken the memory condition that keeps
R's memory above the enabling threshold). Mutation sweep (connection mutation in R): no collapse up to rate 0.001;
collapse (96% of checks, from t = 170) from rate 0.002, where R's per-check stability falls below 0.95.

## 3. Derived classification

* **The commitment/entitlement vocabulary: DESCRIPTIVE / INTERPRETIVE.** A representation with none of its terms
  and different algorithms is operationally identical — 0 disagreements in 12,000 random states, bit-identical
  world runs 8/8 (with and without an edit) and in all 10 scenarios.
* **The structure under the vocabulary** — two statuses (support flows through commitment, eligibility is separate),
  the scope of incompatibility resolution with its persistence rule, and the fixpoint choice — **changes which
  operational interventions are applied** (72% of checks in the lab; 941/295/8,574 random states), with every
  difference located in exactly these operations. At the world level its consequences were **not detected** in
  this lab.
* **The reasoning layer as a whole vs no reasoning layer: non-redundant at the world level** (replicated; mechanism:
  its memory condition on the record region). But every reasoning trajectory is **reproduced exactly by an
  operational intervention schedule** — at the resolution of operational interventions, the layer is a *generator*
  of schedules, not a source of operational difference the runtime could not express.
* Of the seven criteria, the reasoning layer improves only **error detection and dependency tracing**, both
  **by construction of dependency records** and equally in the terminology-free representation; counterfactual
  discrimination holds at the intervention level only.

## 4. Conditions (measured)

* **Reasoning adds a world-level difference only while** (i) its interventions are in force (enabling conditions
  met, if gated), (ii) the record region's memory is not overridden by the world (*external memory*), (iii) its
  own records persist (*shared record persistence*), and (iv) the record region stays active (*repeated
  interaction*; marginal when degraded). Stable addressability, traceable dependency structure, low mutation,
  incompatibility tracking and interface stability were **not** required for the world-level effect when
  reasoning was forced on — they matter only as configured collapse conditions.
* **The commitment/entitlement split becomes operative** (changes interventions) only when reasoning is active and an
  incompatibility defeats a committed claim that supports a self-standing consequence.
* **It collapses / becomes redundant** when an enabling condition fails (by construction), when records decay
  (indirectly, through the loop), under connection mutation ≥ 0.002 in the record region, and whenever its compiled
  schedule is replayed without it (exact reproduction).

## 5. Philosophical interpretation (separate from the results)

What is operationally non-redundant here is the **transition structure** (two-status support propagation,
incompatibility-resolution scope and its persistence, fixpoint choice, and dependency records), not the
**vocabulary**. Brandom- or Wolfendale-style terms name that structure; renaming it changes nothing. Nothing here
bears on whether scorekeeping *is* what people do; the lab shows only what this implementation's structure does to
this runtime.

## 6. Unresolved

* World-level consequences of the two-status structure and of counterfactual dependency structure: not detected at
  N = 1,500, 400 steps, 8 seeds; could exist below this resolution or in other worlds/claim graphs.
* Compression over long horizons with recurring coordinated revisions.
* Whether grounded revision produces world-dependent schedules in richer worlds: in this lab, ungated schedules
  were identical across world seeds (adaptivity 0.00); observed adaptivity (0.21 gated) came from enabling timing.
* Enabling thresholds were calibrated on this lab and do not transfer to the 10k field unchanged.
