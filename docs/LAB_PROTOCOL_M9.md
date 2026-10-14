# Laboratory protocol M9 (causal pathways, extinction, revision, history, cross-world)

This file fixes the M9 experiments before any confirmatory seed is run: conditions, seeds, endpoints, hypotheses,
criteria and stopping conditions. Its SHA-256 is pinned in `backend/xzr/lab/m9.py` (`PROTOCOL_SHA256`); the runner
refuses to start if the file differs. Criteria are not changed after results are seen; amendments are appended in §11
with date and reason.

The M4–M7 protocol (`docs/LAB_PROTOCOL.md`, frozen at `ce00c75f…`) and its results are unchanged. In particular, the
original T7 failure stays binding for the M4–M7 Level 2 criterion; nothing here re-scores it.

Scope: scientific systems are simulated programs, and the laboratory is a rigid-body simulation (MuJoCo 3.14) with
declared approximations (`docs/LAB.md`). No result here is a physical discovery, a validated real-world physical
phenomenon or evidence of physically realised autonomous science.

## 1. Development before freezing

**Verified baseline.**

* Commit `dd2ec81`, tag `m7-verified`.
* All 736 M4–M7 runs were re-executed from that tag; fingerprints, contrasts, verdicts and means are identical
  (`results/labx/verification/level_a_reproduction.json`).

**Instrumentation**, with defaults bit-identical to M4–M7 (tested):

* **Resource partition by system group:**
  * private carriages (own queue, wear, failure, repair);
  * private material and chamber occupancy;
  * private queue capacity;
  * scheduling priority;
  * wear exemption.
* **Communication modes:** `conduit` (live runtime connections), `frozen` (the connection graph as it was when the
  systems started) and `free`.
* **Inert systems:** physical work only, with no runtime effect.
* **Declared harness interventions.**
* **Read-only measures and decision diagnostics.**

**Findings that shaped the design** (development and pilot seeds only):

* **No hidden coupling.** An idle A changes nothing (bit-identical). With every pathway cut (inert A, private
  resources, frozen communication) the run is bit-identical to the run without A. There is no hidden coupling through
  the shared MuJoCo model, the caches or the decision scheduling.
* **Private material is not perfectly matched.** It changes the baseline trajectory even without A: the extra idle
  bodies change the physics numerics (first divergence at step 33 on pilot seed 8000). Private carriages do not.
  Resource effects are therefore estimated from A's effect within each resource mode, never from B's raw outcomes
  across modes.
* **Separated gantries over shared material can race.** Two private carriages in one bay can race for one shared
  sample. The second grasp now fails as a recorded transfer failure; before the fix it crashed the run. This cannot
  happen in the shared laboratory.
* **Refused transfers still cost budget.** A system pays for a transfer request even when the transfer is impossible
  (M4–M7 semantics, unchanged). After a gantry failure, a system keeps requesting and spends its budget. This bears
  on re-ignition after repair (M9-C).
* **Pilot results** (seeds 8100–8103, design only, not evidence): §8.

## 2. World, laboratory, systems, seeds

* **World, laboratory and systems A, B, C:** exactly as in M4–M7 (n = 800, intermittent, warm-up 40, horizon 960,
  MuJoCo laboratory, resources 3 per bay, no HPO field).
* **Grouping:** A forms one group; B and C form the other.
* **Confirmatory seeds** (never used before: not in M4–M7, the T7 diagnostic or any pilot):
  * generator 7000+i, engine 70000+i;
  * 24 seeds for M9-A/B, C, D, E and F.
* **Held-out seeds (M9-D):** generator 7500+i, engine 75000+i, 16 seeds.
* **Cross-world seeds:** generator 7700+i, engine 77000+i, 16 seeds per laboratory.
* **Alternative physics arrangement:** confirmatory seeds 0–11.
* **Noise replicates:** another endogenous stream (engine seed + 7919).

## 3. Statistics (unchanged from M4–M7: `xzr/hpo/stats.py`)

The tests are paired by seed:

* two-sided sign-flip test;
* bootstrap 95 % interval;
* Holm adjustment, applied separately within the primary family and within the secondary family of each contrast.

**Status rules:**

* **DETECTED:** p_holm < 0.01, |mean| ≥ 2 % of scale and |mean| > noise floor.
* **EQUIVALENT:** the 95 % interval lies within ±5 % of scale.
* **UNRESOLVED:** neither of the above.
* **IDENTICAL:** every paired difference is 0.

**Dependence** of B on A in a cell = per-seed difference B(with A) − B(without A). Contrasts of dependences use the
noise floor of (dependence on the noise stream) − (dependence).

## 4. M9-A: communication × resources factorial (primary experiment)

**Cells** (systems A, B, C; A present + or absent 0):

| | communication live (L) | communication frozen (F) |
|---|---|---|
| resources shared (S) | LS+ / LS0 (= M7 ALL / noA) | FS+ / FS0 |
| resources separated (P: private gantries and private material) | LP+ / LP0 | FP+ / FP0 |

**Controls:**

* noise LS+~ / LS0~;
* identity checks: LSz (idle A) must equal LS0, and FPi (inert A in the fully cut cell) must equal FP0;
* LSi: inert A with shared resources (A's physical pathway alone).

**Matching** (§1): separation gives each group what it has alone. The laboratory's total capacity is then larger
than in the shared laboratory, and that is the contention being removed. Private material shifts the baseline
numerically; that is why effects are estimated within cells.

**Endpoints (B):**

* **Primary:** completed transfers, distinct experiments (pairs), mean request-to-delivery latency.
* **Secondary:** failed, coverage, paths, true gain, queue wait, contended legs, waits behind other systems' legs,
  failures by cause (gantry, material, free spot), gantry failures hit, recovery steps, completions in the last third,
  isolations after another system's delivery, observed outcomes.

**Hypotheses** (all evaluated on the primary family):

* **H-A1, resource mediation:** the resource effect on dependence ((LS + FS)/2 vs (LP + FP)/2) is DETECTED on at
  least one primary endpoint.
* **H-A2, communication mediation:** the communication effect on dependence ((LS + LP)/2 vs (FS + FP)/2) is DETECTED
  on at least one primary endpoint. T7 predicts it is not.
* **H-A3, residual (environmental) dependence:** dependence in FP (both pathways cut) is DETECTED on at least one
  primary endpoint. If it is, A's runtime effects alone (environment) carry the dependence. The runtime-only contrast
  FP+ vs FPi and the secondary marker "isolations after another system's delivery" characterise it.
* **Interaction:** reported.

**Validity:**

* The experiment is valid only if both identity checks hold on every seed.
* It is flagged invalid if a noise contrast has more than 5 % of its measures DETECTED.

## 5. M9-B: physical mediation (one resource separated at a time; live communication, real A)

**Conditions:**

* **G+:** private gantries (access, queue, wear, failure, repair);
* **Q+:** private queue capacity on shared gantries;
* **W+:** A's legs cause no wear;
* **P+:** B and C's legs are served before A's waiting legs;
* **M+ / M0:** private material and occupancy.

**References:** G, Q, W and P without A are identical to LS0 (no A legs; an idle private carriage changes nothing,
tested). M+ is referenced to M0.

**Mediation by resource r:** dependence in LS vs dependence with r separated, on the primary family. Resource r
**mediates** if that contrast is DETECTED on at least one primary endpoint.

**Classification:**

* **Direct physical mediation:**
  * the physical-only pathway (LSi vs LS0) is DETECTED on a primary endpoint; and
  * at least one resource mediates.
* **Indirect environmental mediation:** H-A3 holds.
* **Spurious dependence:** an identity check fails, a noise contrast is flagged, or dependence in LS is not DETECTED
  at all.

**Not testable:**

* **Shared transport ports:** in this configuration A never relays (it reaches its own bay only), so A and B share no
  port. This is checked in the leg trace and reported.
* **Chamber occupancy:** it is one resource with material in this model, because a sample is both.

## 6. M9-C: operational extinction and re-ignition (definitions in `xzr/lab/causal.py`)

**Intervention:** at T = 320; closures are reopened at 640. "Extinct" means:

* the system completed a transfer in [T − 160, T); and
* it completes none in [T + 30, T + 190).

**Re-ignition, restored versus new dependency, extinction point and outage paths:** as declared in
`xzr/lab/causal.py`. The M7 thresholds are not changed: M7's T3 stays as recorded (5/24 seeds; not met).

**Conditions:**

* **X0:** none.
* **X1:** bay-0 gantry fails with no repair resources.
* **X2:** the same failure with 1 repair resource.
* **X3:** X1, then 1 resource moved to bay 0 at 480.
* **X4:** X1 with A reaching adjacent bays.
* **X5:** A's observed chambers closed 320–640.
* **X6:** X5 with sensor relocation.
* **X7:** B's hub and sensor chambers have every connection severed at 320.
* **X7f:** X7 with B's communication frozen.
* **X8:** C's memory store closed 320–640.
* **X10 / X10n:** C's whole bay closed 320–640, with ordinary memory or no memory.

**Criteria** (counts are among seeds where the condition applies):

* **C1, failure without substitutes extinguishes:** X1 extinct in ≥ 80 % of active seeds.
* **C2, a repaired failure is not extinction:** X2 extinct in ≤ 20 %.
* **C3, redistribution re-ignites the same dependency:** X3 re-ignites in ≥ 80 % of its extinct seeds, and ≥ 80 % of
  those re-ignitions restore the same dependency.
* **C4, redundant paths prevent extinction:** X4 vs X1 on "extinct" is DETECTED and lower.
* **C5, observation loss extinguishes:** X5 extinct in ≥ 80 % of active seeds.
* **C6, sensor relocation prevents or shortens extinction:** X6 vs X5 on "extinct" is DETECTED and lower.
* **C7, communication loss extinguishes B:** X7 vs X7f on "extinct" is DETECTED and higher.
* **C8, loss of evidence is not operational extinction:** X8 extinct in ≤ 20 %, and evidence unavailable in every
  seed.
* **C9, history restores the same dependency:** X10 restores the same dependency in at least 6 more seeds than X10n.

## 7. M9-D, M9-E, M9-F, cross-world, alternative arrangement

**M9-D: observation revision** (A alone).

* **Conditions:**
  * F, fixed observation;
  * R, parameter adaptation;
  * O, the M5 revision (novelty relocation plus window);
  * Oloc, relocation only;
  * Owin, window only;
  * Oout, outcome-guided relocation plus window;
  * OoutR, Oout with parameter adaptation;
  * F~, noise.
* **Held-out worlds:** F, O and Oout.
* **D1:** Oout vs F on true gain is DETECTED and higher, on the main and on the held-out worlds. A main-only result is
  reported separately and does not satisfy D1.
* **D2, replication of the M5 direction:** O vs F on gain per completed transfer is DETECTED and lower.
* **Decomposition:** reported.

**M9-E: variable generation** (A alone; decision diagnostics on).

* **Conditions:**
  * F, fixed;
  * V, the M5 criterion;
  * Vr, random adoption at the same times;
  * Flo / Vlo / Vrlo: the same three at exploration 0.3, where the model rather than the exploration bonus decides;
  * Vlo~, noise.
* **E0:** the M5 negative result replicates if V vs F is not DETECTED on any primary endpoint (mean |prediction − true
  effect|, mean |prediction − observed|, true gain).
* **E1, variables are consequential when the model decides:** Vlo vs Flo is DETECTED with lower error on a primary
  error endpoint, or with higher true gain.
* **E2, the criterion beats random adoption:** Vlo vs Vrlo on observed error is DETECTED and lower.
* **Diagnostics, reported:** share of decisions changed without variables or without predictions; correlation between
  observed outcome and true effect.

**M9-F: historical reinsertion** (C alone; configuration change at 480 as in M6; diagnostics on).

* **Conditions:**
  * H0, no memory;
  * H1, ordinary;
  * H2, contextual;
  * H3, shuffled;
  * H4, write-only (reinsertion disabled);
  * H6, delayed by 120 steps;
  * H7, contextual with a wrong context;
  * H1lo / H2lo, at exploration 0.3;
  * H2~, noise.
* **Primary endpoint:** true gain after the change. Each of the following is satisfied if the contrast is DETECTED and
  positive:
  * **F1:** H2 > H1 (a replication of the M6 primary, on new seeds);
  * **F2:** H2lo > H1lo;
  * **F3:** H1 > H0;
  * **F4:** H2 > H3;
  * **F5:** H2 > H7;
  * **F6:** H1 > H6.
* The M6 result stays as recorded whatever F1 shows.

**Cross-world** (16 seeds per laboratory):

* **Laboratories:**
  * **transport:** budget 48, decisions every 2 steps;
  * **sensor:** local radius 2.0, distributed readings 1 hop;
  * **fractured:** B's connections severed every 120 steps;
  * **scarce:** no repair resources, budgets 12;
  * **dynamic:** pairs of chambers closed and reopened every 160 steps.
* **Contrasts in each laboratory:**
  * dependence (LS+ vs LS0);
  * residual dependence (FP+ vs FP0);
  * physical-only pathway (LSi vs LS0);
  * A's outcome-guided revision vs fixed (Oout vs F).
* **Reporting:** per effect and laboratory, whether it persists (DETECTED in the same direction as in the base
  laboratory), disappears (not DETECTED), reverses (DETECTED in the opposite direction) or appears (DETECTED here and
  not in the base). No overall criterion: validity is reported per configuration.

**Alternative physics arrangement** (dt 2 ms × 100 sub-steps, 12 seeds):

* **Cells:** LS+, LS0, LSi, FP+ and FP0.
* **Agreement:** a primary-endpoint verdict of M9-A agrees if the effect is DETECTED in the same direction, or not
  DETECTED in both arrangements.

**Independent checks** (`backend/scripts/m9_independent.py`):

* recount from raw records;
* independently written statistics;
* a queue model.

They are reported as they come out; a disagreement is reported, not repaired by changing the original analysis.

## 8. Pilot (design only; seeds 8100–8103, cross-world 8100–8101)

To be filled in before freezing: what the pilot showed, and which design choices it changed.

## 9. Level 2 candidate claim (separate from the M4–M7 Level 2 criterion)

Level 2 (heterogeneous autonomous scientific operations that consequentially change later experimental possibilities)
is claimed under this protocol only if **all** of the following hold:

1. **Without a human:** the systems select and execute every experiment without per-action human selection (true by
   construction, checked in the event logs).
2. **Consequential results:** M4 is DEMONSTRATED (stands), and true gain is non-zero for each system (M4 stands).
3. **Later observation or conditions change:** M5-A stands. In addition, D1 holds, or a revision is DETECTED to change
   later reachability (paths or coverage) on the held-out worlds.
4. **Identifiable changes in future accessibility:** at least two of C1, C3, C5 and C7 hold. Each shows an identified
   operation whose loss or restoration changes what can later be done.
5. **A cross-system pathway survives matched controls:**
   * H-A1 or H-A3 holds (a pathway is identified);
   * the identity checks hold;
   * the noise is not flagged; and
   * the pathway's dependence is DETECTED in the same direction under the alternative physics arrangement.
6. **Reproducible:** the Level A reproduction holds, and independent check B1 agrees on every re-run seed.
7. **Configuration dependence:** the cross-world results report, for the identified pathway, at least one laboratory
   where it persists and the configurations where it does not.

If any condition fails, Level 2 is not claimed. Level 3 (strong Xenoscience) is not addressed by simulation.

## 10. Stopping and validity

* Each experiment must finish within 3 h on 7 processes. If it doesn't, its seed count drops to 16, recorded as an
  amendment before the result is analysed.
* No further confirmatory experiments are added after these results to pursue a positive outcome. Follow-ups are
  labelled exploratory.
* The full regression suite must pass, and the M2, M3 and M7 demonstration records must replay with full agreement,
  before and after.

## 11. Amendments

None.
