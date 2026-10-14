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
| M4 heterogeneous scientific systems | not started | — |
| M5 observation and variable revision | not started in the lab layer (HPO-003 has a sandboxed version; its proposed variable was not validated) | — |
| M6 historical reinsertion with matched ablations | not started in the lab layer (HPO-002 D vs C: H2 not supported) | — |
| M7 cross-system reconfiguration | not started in the lab layer (HPO-002 C: H1 supported in this proxy, does not generalize) | — |
| M8 high-fidelity environment | not started | — |
| M9 independent verification | partial (M1–M3 tests and replay) | — |

**Completion level: Level 1 in part.** There is an interactive 3D environment driven by recorded runtime events with
verified replay, but no live streaming yet: the viewer replays recorded runs. Level 2 (autonomous scientific
operations research environment) and Level 3 (strong Xenoscience) are not reached and are not claimed.

## Strong Xenoscience conditions (not satisfied)

| condition | status |
|---|---|
| 1. Human-energy independence | not satisfied. The simulation runs on a laptop on mains power. |
| 2. Human-readability independence | not assessed. Runs are executable without human-readable output, but nothing tests independence. |
| 3. Material and organizational self-reproduction | not satisfied. Repair restores a modelled actuator from a finite resource counter; nothing reproduces material or organization. |
| 4. Autonomous revision of scientific conditions | not shown in the lab layer. HPO-003 changes sandboxed settings; its one proposed variable failed validation. |

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
