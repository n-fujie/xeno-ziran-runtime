# XENO–ZIRAN 3D laboratory: status, design and limits

This is the 3D laboratory layer (`backend/xzr/lab/`, viewer `?view=laboratory`). The scientific runtime stays the only
source of scientific state transitions. The lab layer derives apparatus states from it, couples a rigid-body physical
model to it, records runs and replays them independently. The renderer draws recorded values only.

## Milestone status (2026-10-14, branch `lab-3d`)

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
| M8 high-fidelity environment | not started | — |
| M9 independent verification | partial (tests, replay, re-execution of sampled confirmatory runs on this machine) | — |

## Completion level

* **Level 1 (interactive 3D environment driven by the runtime): reached.** Recorded runs replay with full agreement,
  and live runs stream to the viewer while the runtime steps independently of it. The renderer draws recorded or
  streamed values only.
* **Level 2 (autonomous scientific operations research environment): not claimed.** The frozen protocol
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
