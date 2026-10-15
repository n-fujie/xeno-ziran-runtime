# XENO–ZIRAN 3D laboratory: status, design and limits

This is the 3D laboratory layer (`backend/xzr/lab/`, viewer `?view=laboratory`). The scientific runtime stays the only
source of scientific state transitions. The lab layer derives apparatus states from it, couples a rigid-body physical
model to it, records runs and replays them independently. The renderer draws recorded values only.

## Milestone status (2026-10-15, branch `lab-m9`)

| milestone | status | evidence |
|---|---|---|
| M1 verified baseline | done | Commit `f0d945b`. Backend 294, frontend 34, research 59 tests passing. Python 3.12.13, numpy 2.5.3, scipy 1.18.1, Node 24.14.1, Apple M1 (8 cores, 8 GB). |
| M2 runtime-driven 3D operation | done | `results/lab/m2-run-9100.json`: 240 steps, 26 apparatus events, each with runtime provenance. Independent replay agrees at every step and event. Viewer values equal recorded values (vitest). |
| M3 executable 3D environment | done, for the scope below | MuJoCo gantries, samples, walls and ports. Material transfer gates runtime connections; wear, failure, repair and resources are modelled. Validation tests pass. `results/lab/m3-physical-9100.json` replays with full agreement. |
| M4 heterogeneous scientific systems | **DEMONSTRATED** (frozen criterion) | `results/labx/m4.json`, 24 paired seeds |
| M5 observation and variable revision | **M5-A consequential, M5-B not demonstrated** | `results/labx/m5.json`, 24 seeds + 16 held-out |
| M6 historical reinsertion with matched ablations | **primary hypothesis NOT SUPPORTED** | `results/labx/m6.json`, 24 paired seeds |
| M7 cross-system reconfiguration | **T2, T4, T5 hold; T3, T6, T7 not met** | `results/labx/m7.json`, 24 paired seeds |
| live runtime→3D streaming | done | `xzr/lab/live.py`, `/ws/lab/{id}`; tested and checked in the browser |
| M8 high-fidelity environment | **done** (branch `lab-m8-high-fidelity`) | Real-time high-fidelity view of recorded and live runs; rendered positions equal recorded MuJoCo positions (browser self-test, 11 scenes); a run streamed to the view equals the headless run (137/137 steps). See `docs/m8/`. |
| M9 causal pathways, extinction, revision, history, cross-world, verification | **done** (frozen protocol; results below) | `results/lab9/`, 2,036 confirmatory runs; Level A re-execution of all 736 M4–M7 runs |

## Completion level

* **Level 1 (interactive 3D environment driven by the runtime): reached.** Recorded runs replay with full agreement,
  and live runs stream to the viewer while the runtime steps independently of it. The renderer draws recorded or
  streamed values only.
* **Level 2 under the M9 protocol (§9 of `docs/LAB_PROTOCOL_M9.md`): not achieved — partially demonstrated.** Six of
  its seven frozen conditions hold. Condition 6 (the independent recount agrees on every re-run seed) does not: the
  recount disagrees with the frozen latency endpoint (a measurement-definition defect, below). The condition is not
  reinterpreted.
* **Level 2 under the M4–M7 protocol: not claimed (unchanged).** The frozen protocol
  (`docs/LAB_PROTOCOL.md` §5) requires M4 DEMONSTRATED, M5-A or M5-B consequential, and T2 and T7. M4, M5-A and T2
  hold; **T7 fails**. B's dependence on A persists when B's readings no longer travel along runtime connections, so
  the protocol's mediator (communication through the runtime) is not shown. The criterion was not changed after the
  result. Existence of the M4–M7 code is not a basis for Level 2.
* **Level 3 (strong Xenoscience): not addressed.** Software simulation cannot satisfy it (conditions below).

## Strong Xenoscience conditions (not satisfied)

| condition | status |
|---|---|
| 1. Human-energy independence | not satisfied. The simulation runs on a laptop on mains power. |
| 2. Human-readability independence | not assessed. Runs are executable without human-readable output, but nothing tests independence. |
| 3. Material and organizational self-reproduction | not satisfied. Repair restores a modelled actuator from a finite resource counter; nothing reproduces material or organization. |
| 4. Autonomous revision of scientific conditions | not shown. In M5, simulated systems revise their own observation (sensor position, window) inside a fixed program; variable generation (M5-B) had no measurable effect. This is a designed revision rule, not autonomy over scientific conditions. |

## Scientific systems (M4–M7)

Code: `backend/xzr/lab/science.py` (systems), `backend/xzr/lab/labexp.py` (experiments). Protocol:
`docs/LAB_PROTOCOL.md`, frozen before any confirmatory seed (SHA-256 `ce00c75f…`, pinned in code; the runner refuses
a changed protocol). Schema `xzr.labrun/2` adds per-step system state and science events. `xzr.labrun/1` records
(M2, M3) are unchanged and still replay.

**What a system is.** A system is a program that:

* sees chambers through sensors;
* selects a source and a target;
* requests a physical transfer of material, which takes extraction, MuJoCo transport and delivery;
* observes the target's ignitions afterwards;
* updates a ridge model with UCB-style exploration.

The runtime is the only source of scientific state transitions:

* a delivery is a runtime `Connect` plus an injected load;
* an isolation gates the runtime connections entering a chamber;
* a closed containment hides the chamber from every sensor.

The **true effect** of a release (the change in the target's ignitions over 20 steps) comes from a counterfactual fork
of the runtime in the harness. No system reads it, and a test inspects the decision code for this.

| system | observation | reach | memory | isolation |
|---|---|---|---|---|
| A local | sensor at 0.0, range 3.6 | own bay | none | no |
| B distributed | hub 1.0 plus sensors 0.1 / 2.0 / 7.0 / 1.2; readings travel along runtime connections (≤ 3 hops, delay = hops) | anywhere | none | closes chambers with observed activity > 0.12 for 40 steps |
| C history | own bay | own and adjacent bays | ordinary memory in store chamber 1.3 (unreadable while it is closed) | no |

### Results (confirmatory: 24 paired seeds per condition, 960 steps, MuJoCo physics; 736 runs, 706,560 simulated steps)

All four experiments were produced at commit `4ae0840` (code_sha1 `a94f2bc0c413ea6f`). The statistics are:

* paired sign-flip test;
* bootstrap CI;
* Holm adjustment;
* DETECTED = p_holm < 0.01, |mean| ≥ 2 % of scale, and beyond the noise floor.

**M4 — heterogeneity: DEMONSTRATED.** Every system pair differs.

| per run (mean) | A | B | C |
|---|---|---|---|
| connection paths observed | 3.25 | 10.91 | 6.53 |
| coverage (fraction of chambers) | 0.094 | 0.147 | 0.125 |
| distinct experiments (pairs) | 5.92 | 7.75 | 9.38 |
| completed transfers | 21.9 | 8.7 | 21.3 |
| true gain | 22.2 | 7.7 | 15.6 |

DETECTED differences:

* A–B: paths, coverage, pairs, completed.
* A–C: paths, coverage, pairs.
* B–C: paths, coverage, pairs, completed, true gain.

**Equalised controls** (all chambers visible, reach anywhere, no memory, no isolation): the three systems are
bit-identical. The differences therefore come from observation, reach, memory and isolation, not from the decision
rule. That rule is shared, which is itself a limit of the heterogeneity shown.

**T1 (independent ignition):** every system requested and completed transfers in 24/24 solo seeds.

**M5 — revision (system A).**

* **M5-A, observation revision (O vs F): consequential by the frozen criterion.**
  * Distinct experiments rose (pairs +46 %, DETECTED; held-out worlds +4.5 pairs, DETECTED).
  * It also lowered completed transfers (−5 %) and observed outcomes (−21 %).
  * True gain did not improve: O 16.0 vs F 22.2 (−28 %), UNRESOLVED (main and held-out).
  * The revision changes what the system explores, not how well it intervenes.
* **M5-B, variable generation (V vs F): NOT DEMONSTRATED.**
  * 11,097 candidate variables were tested in-run against permuted controls, and 30 were adopted (product terms).
  * Neither prediction error nor gain changed, on the main or the held-out worlds.
* **R (parameter adaptation):** nothing DETECTED.
* **Noise control (F~ vs F):** nothing DETECTED.

**M6 — historical reinsertion (system C; configuration change at step 480): primary NOT SUPPORTED.**

* **H2 vs H1** (contextual vs ordinary memory, on post-change true gain): 6.4 vs 6.8, UNRESOLVED.
* **H2 beyond the shuffled (H3), stochastic (H5) and disabled (H4) controls:** not shown.
* **Memory vs none (H1 vs H0):** only fewer distinct experiments (−13 %, DETECTED).
* **H2 vs H5:** prediction error is higher with memory (+60 %, DETECTED), since the random policy predicts trivially.
* **Inherited record:** this is an independent negative result. It does not verify or overwrite the inherited record
  (below).

**M7 — cross-system effects (A, B, C together; one removed; variants).**

| test | criterion | result |
|---|---|---|
| T2 interference | ≥ 1 DETECTED measure | **holds**: with A present, B completes 4.8 vs 6.5 and runs fewer pairs; with B present, A completes 15.5 vs 21.8 with more failures; with A present, C completes 14.8 vs 12.9 |
| T3 extinction | A blocked by B's isolation in ≥ 6/24 seeds | **not met**: 5/24 seeds (5 blocked deliveries) |
| T4 substitution | A's completed not lower than without isolation | **holds**: EQUIVALENT (15.5 vs 15.3) |
| T5 re-ignition | A experiments on reopened chambers in ≥ 6/24 seeds | **holds**: 7/24 seeds, 17 experiments |
| T6 cross-system history | ≥ 1 DETECTED for A reading C's memory | **not met**: identical runs (A and C never share a pair, so A never uses C's memory) |
| T7 counterfactual removal | B's dependence on A disappears without connection-borne readings | **fails**: with readings independent of connections, A's presence still lowers B's completed (−28 %) and pairs (−31 %), DETECTED. Without isolation A is never blocked (holds). |
| noise (ALL~ vs ALL) | — | nothing DETECTED |

**Exploratory (development seeds 8000–8007, after the confirmatory result; not a confirmatory finding).** A
diagnostic of the T7 failure points to shared physical resources as the route of B's dependence on A:

* the bay-0 gantry;
* material in chamber 0.1.

B's transfer latency is 141 vs 119 steps with A present. Script and output:
`results/labx/history/exploratory_t7_mediator.*`.

### Execution record

* **Protocol not amended.** No criterion, endpoint or seed range was changed after results.
* **Superseded launch.** One confirmatory launch imported the wrong code tree. It was set aside unpublished and all
  four experiments were re-run (`results/labx/history/execution-notes.txt`, `confirmatory-run.log`).
* **Defect fixed after the runs.** A threshold of `isolate_above = 0.0` disabled isolation (commit `eb1a048`). The
  protocol configuration uses 0.12 and is unaffected. On this machine, five sampled confirmatory runs re-executed at
  the current HEAD reproduce their published fingerprints bit-for-bit (m4 solo_B/3, m5 OV/11, m6 H2/7, m7 ALL/0,
  m7 noIso/5).
* **Demo record.** `results/lab/m7-systems-6000.json` is the M7 ALL condition on confirmatory seed 6000. Its final
  fingerprint equals the published `ALL/confirm/0`, and it replays with full agreement.

### Limits of these results

* **Shared decision rule.** All systems use one decision rule. Heterogeneity is in observation, reach, memory and
  isolation only.
* **Noisy true-gain endpoint.** The counterfactual true-gain endpoint can vary strongly between endogenous streams
  (M6 post-change: H2~ 11.4 vs H2 6.4, same systems and worlds), even though no noise contrast is DETECTED. Power on true gain
  is therefore low, and UNRESOLVED there means "not shown", not "no effect".
* **One world class.** One world class was used (n = 800, intermittent) with one laboratory layout. Held-out worlds
  were used only for M5.
* **Simulation only.** Systems, materials and physics are simulated. Nothing here is a physical discovery.

## M9 — causal pathways, extinction, revision and history (2026-10-14/15)

Protocol `docs/LAB_PROTOCOL_M9.md`, frozen before any confirmatory seed (SHA-256 `4757ee7d…`, pinned in
`xzr/lab/m9.py`). Code `xzr/lab/m9.py`, `xzr/lab/causal.py`; pathway switches in `physics.py` (resource partition),
`science.py` (communication modes, inert systems, revision/memory/variable variants, read-only diagnostics) and
`record.py` (declared harness interventions, schema `xzr.labrun/3`). Defaults reproduce M4–M7 bit for bit.

**Baseline (verification A).** All 736 M4–M7 runs were re-executed from tag `m7-verified` (`dd2ec81`). Fingerprints,
contrasts, verdicts and means are identical (`results/labx/verification/level_a_reproduction.json`).

**Execution.** The confirmatory runs used commit `419aafe`, from a separate worktree, on 7 processes:

| experiment | runs |
|---|---|
| M9-A/B | 456 |
| M9-C | 312 |
| M9-D | 240 |
| M9-E | 168 |
| M9-F | 240 |
| cross-world | 560 |
| alternative physics | 60 |
| **total** | **2,036** |

Seeds are confirmatory 7000+i, held-out 7500+i and cross-world 7700+i, none used before. Hashes, log and notes are in
`results/lab9/history/`. No run was repeated or set aside, and the protocol was not amended.

| | result |
|---|---|
| **M9-A** communication × resources | Instrument valid: idle A == no A and inert A with every pathway cut == no A, bit for bit on 24/24 seeds; no noise flagged. B depends on A with shared resources (completed −21 %, distinct experiments −27 %, latency +19 %), equally with communication frozen. **Resource mediation holds; communication mediation does not; no residual dependence.** An inert A (physical work only) reproduces the whole dependence. |
| **M9-B** physical mediators | Private carriages remove the dependence (pairs, latency). A's wear exemption halves the latency effect (definition-sensitive, below). Private material removes the loss of distinct experiments but raises B's latency dependence. Queue capacity and priority are IDENTICAL (one pending transfer per system; stated before confirmation). Ports are not a pathway (A never relays). |
| **M9-C** extinction / re-ignition | **Hold:** C1 (failure without substitute: 24/24 extinct), C2 (repaired failure: 2/24; natural failures in 24/24 X0 seeds, no extinction), C5 (observation loss: 24/24 extinct, 24/24 re-ignite). **Not met:** C3 (budget spent on refused requests before the resource arrives), C4, C4b (no substitute detectable as executable, below), C6 (relocation does not prevent extinction but makes re-ignition a new dependency: reuse 0.49 vs 0.92; new in 23/24 vs 9/24), C7 (severed conduits: B's paths 10.3 → 0.04, later completions −76 %, but one in-flight transfer lands in the window), C8 (evidence loss not exercised in 1/24 seeds), C9. |
| **M9-D** observation revision | D1 not met. D2 not replicated (the M5 revision is +23 % on true gain here, UNRESOLVED; M5 had −28 %). Relocation is the whole effect and window revision is EQUIVALENT to fixed: distinct observed pairs +40 %, redundant observations −51 %, reachable experiments +13 % (held-out +15 %), completed −5 %. **What can be observed and reached changes; effectiveness is not shown to change.** |
| **M9-E** variable generation | E0: the M5 negative replicates. E1 and E2 not met: variables adopted by the criterion are no better than random adoption. Adopted variables change 10–13 % of decisions. The systems' observed outcome correlates with the true effect at r ≈ 0.09–0.19. |
| **M9-F** historical reinsertion | F1–F6 not supported: contextual memory is no better than ordinary, shuffled, disabled, delayed or wrong-context memory, nor at low exploration. The M6 negative replicates. Memory changes 30–54 % of decisions. |
| **Cross-world** (16 seeds each) | The physical-resource dependence persists (transport, dynamic), is amplified (scarce: completed −45 %), persists in part (fractured: pairs, latency) and is not detected (sensor-restricted: inconclusive). No residual dependence anywhere. Revision's gain in distinct experiments: sensor, fractured, dynamic. |
| **Alternative physics** (dt 2 ms × 100, 12 seeds) | The dependence persists in direction and detection. The physical-only pathway is detected on latency only. |

**Verification** (`results/lab9/verification/`):

* **Independent statistics (B2):** all five primary M9-A verdicts agree.
* **Event recount (B1):** attempted, physically completed and delivered transfers, blocked deliveries, failures,
  repairs and budget all agree. M9-C extinction and re-ignition, recounted from the protocol text, agree. All recorded
  gantry health values fit the declared wear rules. A causes 70–80 % of the wear on the bay-0 gantry B uses (6 re-run seeds).
* **Queue model (C1):** removing A's legs from the recorded bay-0 queue predicts B's wait 0.0, against 0.48 observed
  without A.
* **Replay (D):** two schema-3 records equal their confirmatory runs and replay with full agreement:
  `results/lab/m9-separated-resources-7000.json` and `m9-extinction-relocation-7000.json`.

**Measurement-definition defect (latency).** The protocol states the endpoint as request-to-**delivery** latency. The
harness measured request-to-**physical-completion** latency, which includes transfers whose delivery was then blocked
at a closed containment. The independent recount disagreed on 5 of 12 runs. The frozen results are unchanged; the
original endpoint is to be read as physical-completion latency.

An exploratory sensitivity analysis (`results/lab9/exploratory/latency_sensitivity.json`) re-executed 360 runs:

* **Cause:** every one of the 85 blocked deliveries was blocked by B's own isolation.
* **Verdicts:** under the delivery definition every latency verdict keeps its status and direction, except the
  wear-mediation latency effect, which becomes UNRESOLVED.

**Correction: substitute paths.** The frozen protocol's pilot section (§8) and the M9-C commit message say that A
"saw" substitute experiments during the outage and did not use them. That is wrong. The route-aware exploratory
analysis (`results/lab9/exploratory/substitutes.json`) shows:

* **Available:** executable substitutes existed in the laboratory, about 273 per decision.
* **Detectable:** A detected about 10 experiments per decision in X4b.
* **Executable among the detectable:** none. Every one needed the failed bay-0 gantry.
* **Selected and executed:** none.

The failure was inaccessibility of the alternatives to the system, compounded by budget exhaustion. A first version of
that analysis, which checked only the source's gantry, is kept as `…_SUPERSEDED.json`.

**Heterogeneity.** As in M4, heterogeneity here is configuration-dependent (observation, reach, memory, isolation,
resources). The systems share one decision rule. No diversity of scientific decision procedures is claimed;
investigating one would be a separate project.

**Manuscript.** `docs/publication/XENO-ZIRAN-3D-research-record.docx` is one cumulative English document. It contains
the argument, methods, results, verification, negative-results register, figures, protocols, complete source
listings, configurations and every result file. Rebuild it with `backend/scripts/m9_figures.py` and
`backend/scripts/build_m9_manuscript.py`, which need python-docx and matplotlib (not runtime dependencies).

## M8 — high-fidelity real-time laboratory (2026-10-15)

A second view of the same runs: the **High fidelity (M8)** toggle in the 3D Laboratory, or `?view=laboratory&hifi=1`.
The standard view is unchanged. Code is in `frontend/src/views/lab/hifi/` (see its README); verification and
performance are in `docs/m8/`.

* **Three layers, four categories.** Every drawn object is classified:
  * layer A, physical: MuJoCo floors, walls, ports and samples, carriages and tools at recorded positions; rails, bridge
    and mast represent the slide joints;
  * layer B, scientific: containment louvres, activity and memory instruments, sensors, memory stores, runtime
    connections, pending experiments, observed chambers;
  * layer C, architecture with no scientific claim.

  Each layer can be shown alone.
* **Physics-to-render mapping** (`coords.ts`): `view = (x, z + 0.25, y)`, with no scaling. Tests and the in-browser
  self-test show the rendered positions of every carriage and sample equal the transformed recorded positions (worst
  error 5×10⁻⁷ m, float32). Chamber floors and walls equal the MuJoCo geoms.
* **What a system can do.** The view separates what exists, what a system observes, what it can experimentally access,
  what it selects and what it executes. "Accessible" applies `science.py candidates()` to recorded state; it equals the
  backend at every decision step of both M9 records.
* **Delivery.** It is shown only from a recorded `material_delivered` event. A refused transfer is "delivery blocked",
  matching the M9 measurement-definition finding.
* **Mediation and provenance.** Physical-resource mediation shows gantry wear, queues and legs by system. Recorded and
  derived transitions are listed; derived ones state their rule. Provenance uses recorded links only, with
  "unresolved" otherwise. Unrecorded quantities show an availability status, not zero.
* **Camera modes:** overview, domain, apparatus, operation, transfer, sensor and free.
* **Quality levels:** performance, balanced and high. They give identical layer-A/B state (tested).
* **Rendering cannot change a run.** The runtime steps in its own thread. A run streamed to the high-fidelity view equals
  a headless batch run of the same configuration at 137 of 137 steps, and its record replays.
* **Performance** (Apple M1, headless Chromium with GPU, 1200×866): mean / p95 frame cost of 5.0 / 8.8 ms
  (performance), 10.0 / 15.5 ms (balanced) and 13.5 / 19.4 ms (high), at about 60 displayed fps.
* **Not a scientific result.** M8 changes no scientific result or achievement level. The research manuscript
  (`docs/publication/`) is unchanged.

## Live streaming

`backend/xzr/lab/live.py`, endpoints in `backend/xzr/service/app.py`, and the viewer's "Start live run":

* **The runtime is independent of viewers.** It steps in its own thread at its own rate (0.5–200 steps/s) and never
  waits for one. Viewers can only pause, resume, stop or change the rate.
* **Backpressure without losing events.** Each viewer has a mailbox. When the socket is slower than the run, visual
  frames are coalesced (the message carries `seq_from`–`seq_to`), and every event is still delivered in order. A
  viewer more than 20,000 events behind is disconnected with an explicit message; the run and its record are
  unaffected.
* **A new viewer joins mid-run.** It gets all events so far, the built laboratory and then the live frames.
* **Recording.** A finished or stopped run is written to `xzr-results/lab-live/<id>.json` as an ordinary
  `xzr.labrun` record (a stopped run is a prefix of the horizon) before its end state is published. It replays with
  full agreement. Tests show that a live run equals a batch run step by step.
* **Access.** Live runs are available only on a local runtime: they are refused on a public deployment and for
  cross-origin requests. At most 2 can run at a time.

## What is physical and what is approximated (M3)

| | modelled with rigid-body physics (MuJoCo 3.14, dt 4 ms, 50 sub-steps per runtime step) | computational approximation |
|---|---|---|
| motion | 3-axis gantries with position servos, force limits, damping; gravity on carried samples | gantry self-weight gravity-compensated |
| contact | samples on floors, ports and each other; collisions with chamber walls (0.7 m) | — |
| manipulation | — | grasping is a weld constraint activated within 8 cm (no friction grasp) |
| degradation | lower health lowers servo gain and force: a transfer takes 30 steps at h = 1.0, 39 at 0.7, 51 at 0.5, 61 at 0.4 (measured) | the wear rate per leg and failure below h = 0.35 are rules, not a fracture model |
| repair | — | restores h = 1 after 30 steps at the cost of 1 resource unit; with no resources the gantry stays failed |
| transport | relay through handoff ports between adjacent bays | routing takes the shortest way round the ring |

Validation tests (`backend/tests/test_lab_physics.py`):
* free-fall time within 2 % of √(2h/g);
* resting penetration under 2 mm;
* a wall stops a sample pushed against it;
* wear slows transfers;
* failure and repair follow the declared rules;
* bit-identical physics in repeated runs;
* the physical run couples to the runtime and replays.

The physical model is not validated against any real apparatus.

### How physics couples to the runtime

When an operation requests a connection (a runtime `Connect`), the connection exists only after a material sample has
been moved physically, by one or more relay legs, into the target chamber. Duplicate requests can fail for lack of
material, queues can be full, and a failed gantry without resources ends the transfers of its bay. All of these are
recorded as physical events with their causes. In `m3-physical-9100`, the assemblage operation requested 4 transfers
from 0.3 to 1.0:

* 1 was completed after 66 steps through port 0-1;
* 3 failed with "no material in 0.3";
* 2 further requests were rejected because the queue was full.

The runtime state differs from the run without physics (tested).

## Rendering

* **Runtime-derived quantities:**
  * containment shutters: 1 − the mean gate of the connections entering the chamber;
  * state lamp: glow = ignition share, size = memory;
  * conduits: live connections between chambers.
* **Physical bodies:** drawn at their recorded MuJoCo positions.
* **Scientific systems (schema 2):** rings around observed chambers (solid A, dashed B, dotted C), sensor markers, the
  memory store, and an arc for the pending transfer. All are drawn from the recorded per-step system state, which a
  test checks against the published demo record.
* **Highlights:** only for recorded events.
* **Static scenery** (floor, grid, overhead frames) carries no runtime meaning.

Measured on the M1:

* 60 fps in the in-app browser;
* headless recording at about 160–220 runtime steps/s without physics and about 50 steps/s with physics;
* peak Python allocation 13 MB;
* records of 0.7 MB (without physics) and 1.2 MB (with physics) for 240 steps.

Rendering has no access to the run: the lab layer imports no rendering code (tested), and records are produced
headless.

## Reproduction

```bash
.venv/bin/pip install -e "backend[dev,physics]"
.venv/bin/xzr lab run --out xzr-results/lab/my-run.json
.venv/bin/xzr lab replay xzr-results/lab/my-run.json
.venv/bin/xzr lab replay backend/experiments/results/lab/m7-systems-6000.json
```

To re-run a confirmatory experiment, use any directory other than the published one (`write` refuses to overwrite
published results). M7 took 25 minutes on 7 processes on the M1:

```bash
cd backend && ../.venv/bin/python -c "from pathlib import Path; from xzr.lab import labexp as L; \
  print(L.write('m7', L.run_experiment('m7', 7), Path('../xzr-results/labx-rerun')))"
```

`xzr lab run` records a run without physics. For a physical run, pass `--config` with a JSON file containing
`{"physics": true}`. Replay agreement is defined for the same machine and software versions
(`docs/REPRODUCIBILITY.md`). Elsewhere the ARPACK hierarchy can differ.

## Inherited records not verified here

The exploratory history-dependence record handed over with the request could not be traced to any source code, log or
result file on this machine:

* 8 paired seeds, 160 configurations, 232 steps;
* intervention at step 95, reactivation at step 145, observation at step 180;
* four history-dependence criteria not satisfied;
* a 21.9 % connectivity difference in a separate noise condition.

The runtime's own `history-reentry` preset uses different conditions. The record is kept as an inherited, unverified
negative finding: it was not reconstructed and not reinterpreted.

The request also names architectural components (MO, DO, ZCA, MS, ΩⅨ, R-A, HDA) and "v4 experimental components". None
of them is implemented on this machine (MO … HDA are named as possible future rule bundles in
ziran-xeno-simulator/DESIGN.md), so none is claimed as preserved.
