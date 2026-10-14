# Laboratory protocol M4–M7 (frozen before the confirmatory runs)

This file fixes the M4–M7 laboratory experiments before any confirmatory seed is run: conditions, seeds, endpoints,
hypotheses, success and failure criteria, and stopping conditions. Its SHA-256 is pinned in
`backend/xzr/lab/labexp.py` (`PROTOCOL_SHA256`), and the confirmatory runner refuses to start if the file differs.
Criteria are not changed after results are seen; amendments are appended below with date and reason.

Scope: scientific systems are simulated, and the laboratory is a rigid-body simulation with declared approximations
(docs/LAB.md). No result here is a physical discovery or evidence of physically realised autonomous science.

## 1. Development (before freezing)

These design decisions were taken on development seeds only (generator 8000–8003, engine 80000–80003):

* **Material carries a load.** An intervention pilot showed that a bare connection's effect is indistinguishable
  from noise (sd 0.81 vs 0.76), while delivered material changes target ignitions (sd 4.3). Material therefore
  carries a load.
* **Observable targets only.** Systems choose only targets they can observe.
* **Horizon 960 steps.** About 15 interventions per local system.
* **No privileged inputs.** Sensor relocation uses only material the system itself has seen. Window and parameter
  adaptation use the system's own observed errors, never the harness's true effect.
* The pipeline was exercised on 2 development seeds per experiment.

## 2. World, laboratory, systems

* **World:** n = 800, regime `intermittent`, warm-up 40, horizon 960.
* **Laboratory:** physical (MuJoCo, docs/LAB.md), resources 3 per bay, no HPO field. The scientific systems are the
  only operations.
* **Systems** (`xzr/lab/labexp.py`):
  * A (local): sensor at 0.0, transfers within its bay.
  * B (distributed): hub 1.0, sensors 0.1 / 2.0 / 7.0 / 1.2, readings only along runtime connections (≤ 3 hops),
    transfers anywhere, isolates chambers with observed activity > 0.12.
  * C (history): bay 1, store 1.3, ordinary memory, transfers within its own and adjacent bays.
* **Budgets:** 24 units each; a transfer costs 1, a relocation 0.5, an isolation 0.5.
* **True effect:** a release changes the target's ignitions over 20 steps; it is computed by a counterfactual
  runtime fork in the harness and never read by any system.

## 3. Seeds

* **Confirmatory:** 24 seeds (generator 6000+i, engine 60000+i).
* **M5 held-out configurations:** 16 seeds (generator 6500+i, engine 65000+i).
* **Noise replicates:** another endogenous stream (engine seed + 7919).

## 4. Conditions and endpoints

* **M4:** solo_A / solo_B / solo_C (native specifications), and eq_A / eq_B / eq_C. The eq conditions equalise
  observation (all chambers visible), reach (any), memory (none) and isolation (off).
  Endpoints: paths, coverage, pairs, completed, true_gain (plus observed_outcomes, spent, failed).
* **M5 (system A):**
  * conditions: F fixed, R parameter adaptation, O observation revision (sensor relocation and window), V variable
    generation, OV both, and F~ noise;
  * held-out: F, O, V, OV on held-out worlds;
  * primary endpoints: true_gain (O) and abs_pred_error (V).
* **M6 (system C):**
  * conditions: H0 no memory, H1 ordinary, H2 contextual, H3 shuffled, H4 write-only, H5 random policy, and H2~ noise;
  * configuration change at step 480: containment of 1.0 and 1.2 gated to 0.6;
  * primary endpoint: true_gain_post (gain from releases after the change).
* **M7:**
  * conditions: ALL (A, B, C); noA, noB and noC (one system removed); noIso (B without isolation); noComm (B's
    readings independent of runtime connections); noComm_noA; memShare (A reads C's memory); ALL~ (noise);
  * endpoints: coverage, paths, completed, true_gain, pairs, failed, blocked deliveries, deliveries blocked by
    another system's isolation, experiments on reopened chambers, isolations, observed outcomes.

Statistics (`xzr/hpo/stats.py`, unchanged): paired by seed. The tests are:

* two-sided sign-flip test with 20,000 Monte Carlo patterns;
* bootstrap 95 % interval;
* Holm adjustment within each contrast;
* noise floor from the noise replicate where one exists.

A measure is **DETECTED** when p_holm < 0.01, |mean| ≥ 2 % of scale and |mean| exceeds the noise floor. EQUIVALENT
and UNRESOLVED are kept as in HPO.

## 5. Hypotheses and criteria

* **M4.**
  * Heterogeneity is DEMONSTRATED if, under native specifications, every system pair (A–B, A–C, B–C) differs
    (DETECTED) in at least one of paths, coverage, pairs, completed or true_gain. If only some pairs differ, it is
    PARTIAL; if none, NOT DEMONSTRATED.
  * Under equalisation the remaining differences are reported descriptively. Their disappearing is a valid result.
  * **T1 (independent ignition):** every system makes at least 1 request in every solo seed and completes at least
    1 intervention in at least 90 % of solo seeds.
* **M5.**
  * **M5-A (observation revision):** consequential if O vs F is DETECTED and higher on true_gain or pairs.
  * **M5-B (variable generation):** consequential if V vs F is DETECTED and lower on abs_pred_error, or DETECTED and
    higher on true_gain.
  * **Transfer:** the same contrast is DETECTED in the same direction on the held-out worlds.
  * R and OV are reported.
  * **Rejection conditions:**
    * an improvement disappears under F~ (noise);
    * an adopted variable fails the in-run held-out test (it is then not adopted);
    * a gain depends on harness-only information (excluded by design).
* **M6.**
  * **Primary:** H2 > H1 on true_gain_post (DETECTED, positive).
  * **Secondary:** H2 > H3, H2 > H5, H2 > H4, H1 > H0.
  * A positive result needs effects beyond the H2~ noise floor and beyond H5.
  * The inherited unverified negative record is not overwritten.
* **M7.**
  * **T2 (interference):** at least 1 of the T2 contrasts has a DETECTED measure.
  * **T3 (extinction):** A's deliveries are blocked by B's isolation in at least 6 of 24 seeds.
  * **T4 (substitution):** A's completed is not DETECTED lower in ALL than in noIso. If it is lower, substitution is
    incomplete.
  * **T5 (re-ignition):** A experiments on chambers B had isolated and reopened, in at least 6 of 24 seeds.
  * **T6 (cross-system history):** at least 1 DETECTED measure for A in memShare vs ALL.
  * **T7 (counterfactual removal):**
    * B's dependence on A is DETECTED on coverage or paths in ALL vs noA, and none of those measures is DETECTED in
      noComm vs noComm_noA;
    * no isolation blocking of A occurs in noIso.
  * Communication alone is not counted: an effect counts only through material, connections, gates or memory used
    in a decision.

**Levels:**

* Level 2 is claimed only if M4 is DEMONSTRATED, M5-A or M5-B is consequential, and T2 and T7 hold.
* Level 3 is not addressed by simulation.

## 6. Stopping and validity

* If a noise contrast (F~ vs F, H2~ vs H2, or ALL~ vs ALL) has more than 5 % of its measures DETECTED, that
  experiment's statuses are flagged invalid.
* Each experiment must finish within 2 h on 7 processes. If it doesn't, the seed count drops to 16, recorded as an
  amendment.
* The published M2 and M3 records must replay with full agreement before and after. The full regression suite must
  pass. If either fails, integration stops until it is repaired.

## 7. Amendments

None.
