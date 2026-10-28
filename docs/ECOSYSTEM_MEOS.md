# XENO ECOSYSTEM — MEOS-0 and the XENOSCIENCE megastructure

> Second stage (engine `meos-0.2`: traces, observation separation, M2, Philosophical operations, Address Domain interventions, new experiments, research-device layer): see `docs/ECOSYSTEM_MEOS_STAGE2.md`. The statement in section 9 below that the philosophical-AI connection is not implemented is superseded there only in the narrow sense that first-stage Philosophical operations exist inside MEOS-0; the Philosophical AI itself is not connected.

A new view of XENO ZIRAN SIMULATOR (`?view=ecosystem`, local runtime only) that draws a deterministic simulation of **MEOS — Minimal Ecosystem Operational Shape**
in a navigable megastructure organised like the XENOSCIENCE drawing. It was added on a separate branch; no existing view, test or stored result was changed
(the only edits to existing files are the view registration, one i18n label, the layering declaration of the new layer, the enumeration of the new API routes in
the security test and lint settings for the new files).

What it is not: an animation, a background image or a mock-up. Every experimental object in the habitat is drawn from a record the engine produced; the
structure around it is **static architecture** and is labelled as such.

## 1. Architecture of the model (what the drawing became)

| Zone of the drawing | In the simulation |
|---|---|
| A Research Core | the shaft's four layers (surface 0, intermediate −34, core −68, subsurface −104) and the status/analysis surfaces; the MEOS status is read here and in the HUD |
| B Subsurface Laboratory | twelve trial chambers on the deepest ring; each holds one reduction experiment (baseline, each single removal, three combinations): brightness = the trial's MEOS status, a removed A2 is absent from its chamber |
| C Material Processing | the stockpile follows the total resource R of the recorded field |
| D Autonomous Power | the finite power reserve (a gauge at the solar field); the reserve pays A2's firing and the renewal of R and recharges at a stated rate. An infinite reserve exists only as an explicit control condition |
| E Non-Human Habitat | the arena of MEOS-0 under a dome: the field F, A1, A2 |
| F Transportation Network | resource carriers move from the depot to the arena for every recorded renewal by A2 |
| G Observation Array | dishes pulse on the ticks the configured observation samples; the observed status can differ from the true status |
| H Data & Model Generation | the DATA tab: status, cycles, resource, history and energy trajectories, the firing raster, the accumulated interaction graph, the resource distribution |
| I Expansion Zone | empty module sockets (nothing is installed): new experimental modules attach to `xzr/meos` and to the view's `Megastructure` without redesigning either |

## 2. MEOS-0

`backend/xzr/meos/engine.py`. Environment field F (a 14×14 grid with a resource field R and two alteration fields M1, M2), operational entity A1, operational
entity A2, a resource gradient, an interaction relation and history H.

* **A1** senses the peak of R in its window, differentiates it from an adapted baseline, fires when the difference exceeds its threshold, consumes R and deposits M1.
* **A2** senses the peak of M1 in its window, differentiates it, fires, moves toward the alteration and reconfigures R from the finite power reserve.
* **History** is a decaying trace of each configuration's firing and detected difference. When history re-enters, it lowers the next firing threshold (never below 40 %
  of it). `removed` and `prevented` are different conditions: in `prevented` the trace is still recorded but lowers nothing.
* **A cycle** is the chain *A1 acts → A2 detects that alteration and fires → A2 reconfigures R → A1 detects the change and fires*. Each link is a causal attribution to a
  recorded event of the other configuration within 6 ticks, and only if the sensed signal itself (before sensor noise) rose above the noise.
* **Status** is derived from cycles only. ACTIVE: at least 2 cycles in the last 48 ticks and the latest no older than 24. COLLAPSED: no cycle in the last 48 ticks
  after the first 48. Otherwise DEGRADED (including "forming" before the first cycle). Animation activity plays no part: with A2 removed, A1 still fires and the status
  is COLLAPSED.
* **Failed dependency**: the first unmet dependency of the loop — structure first (a part absent, disconnected, disabled), then the latest precondition evaluation in the
  order of the loop, then the power reserve. It is derived from state, never from the picture.
* A1 and A2 are *operational configurations* (a sensing window, a threshold, a firing persistence, an action rule). They are not organisms, subjects, agents or
  minds; their operational boundary is a specification you can change (sections 4 and 5). A test checks that the engine's source does not call them otherwise.
* **Parameters were chosen** so that the unperturbed run sustains the recursion (a random search over thresholds, ranges, renewal amounts and persistence found regimes
  sustained across seeds; one was adopted). What every perturbation then does is *measured*. These are properties of this model, not of any real ecosystem.

## 3. Reduction experiments (what was executed)

All runs are the real engine, seeded and deterministic; `docs/ecosystem/experiments.json` holds every row with its result digest
(`python backend/scripts/meos_experiments.py --out ...`). Default configuration, seed 1, 240 ticks (three seeds for single removals).

| Experiment | Outcome |
|---|---|
| unperturbed MEOS-0 | ACTIVE from tick 11, 47 cycles; replay bit-identical (`b4cf1e52…`); seed 2 gives a different digest |
| remove A2 | COLLAPSED (0 cycles); dependency "A2 is absent: nothing reconfigures the environment for A1"; A1 still fires |
| remove history (removed, or prevented) | COLLAPSED after 22 cycles; first divergence from H+ at tick 17; mean threshold reduction 0.073 → 0 |
| remove the resource gradient (flatten) | **ACTIVE** (47): in this model A2's reconfiguration, not the gradient, supplies what A1 detects |
| remove resource renewal | COLLAPSED after 13 cycles: the finite reserve runs out |
| interrupt interaction / sensor channels / feedback / alteration persistence | COLLAPSED (0 cycles), each naming its own dependency |
| interaction cut at 100, reconnect at 150 | stays COLLAPSED (nothing re-triggers A1) |
| … plus a resource pulse of 2.0 at 151 | collapse, refiring and **recovery to ACTIVE** (61 cycles); a pulse of 4.0 collapses again |
| remove A2 and history together; gradient and renewal together | COLLAPSED; gradient and history together: ACTIVE (non-monotone) |
| infinite-resource control, with and without history | ACTIVE in both: the history dependence of the default run is tied to the finite power reserve |
| spatial boundary radius 2 / 4 at tick 50 | COLLAPSED / ACTIVE |
| SSS (one axis at a time, from tick 0) | ACTIVE only at scale ≤ 1 (0.5 and 1), size 1, speed 1: a narrow operating band |
| Address Domain (one parameter at a time) | collapses when A2 is moved to x ≥ 7, its sensing radius is 0, A1's radius is 3, A1's window is 2, A2's persistence is 1 or 6, A2's speed is 0.5 or 2 |
| observation sampling interval 1 / 2 / 4 / 8 | observed status ACTIVE / COLLAPSED / COLLAPSED / COLLAPSED (all four events of a cycle must be sampled): observation is a parameter of what is found |

**Minimal operational configuration (the MFS relation).** MFS is *not* redefined: it is the minimal relational operational configuration relative to a specified
operation (the cycle is sustained, status ACTIVE at the end), the physical conditions and scale of the run, and the admissible reductions (the nine removals in
`engine.COMPONENTS`). The search (greedy backward elimination, verified by leave-one-out; exhaustive over all 512 removal sets on request) found one minimal retained
set: A2, the interaction channel, the resource and alteration sensors, alteration persistence, feedback and resource renewal; the gradient and history are removable in
that combination although history is not removable alone. MEOS is the ecosystem-level application — two operational sequences recursively modify one another's subsequent
conditions; minimality is operational and relational, never a number of graphical objects.

**XenoBody boundaries (same arrangement).** B1 (A1 alone): closure 33 %, the operation does not persist when only B1 is retained; B2 (A1 + sensor network): 50 %, does
not persist; B3 (A1 + A2 + the resource-transfer loop + history): 100 %, persists. Closure = share of the six legs of the recursion whose components all lie inside the body.

## 4. The interface

* **Time**: RUN, PAUSE, STEP ±, RESET, REPLAY (re-runs the recorded seed, configuration and interventions and compares the result digests), a scrub bar, a speed control.
  The simulation tick (the record's frames) and the render frame rate are separate clocks.
* **Camera**: orbit, pan, zoom (OrbitControls), presets Overview / Research Core / Habitat / Subsurface Laboratory, follow A1 or A2, focus the selection. The camera has no
  route to the record (tested).
* **Interventions**: REMOVE, ISOLATE, RECONNECT, RECONFIGURE (any Address Domain or environment parameter in the settable list), CHANGE BOUNDARY, DISABLE HISTORY,
  ALTER SSS, ALTER RESOURCE (including a resource pulse). Each is validated, logged with its tick, applied by re-running the record from its seed with the new list (the past
  before the tick is identical) and shown in the intervention log with undo.
* **Layers** (each derived from the record): PHYSICAL, OPERATIONAL, MFS, MEOS, ADDRESS, SSS, HISTORY, FIRING, XENOBODY.
* **Inspector** (click A1, A2 or a chamber): object id, operational configuration, Address Domain (position, boundary, temporal window, speed, history, connectivity,
  environment, resource), SSS, MFS membership (only after the reduction search was run), MEOS membership (from counted cycles), firing state and the unmet preconditions,
  the preconditions of the last firing and its recorded consequences, resource state, interaction partner, operational boundary, recent transitions.
* URL parameters (also used by the captures): `preset=baseline|a2-removed|no-history|interaction-cut`, `tick`, `cam`, `layers`, `quality`, `reductions=1`, `chrome=0` (stage alone).

## 5. API (`/api/meos`, stateless, local runtime and same origin only — 403 under `XZR_PUBLIC`)

`GET /spec` · `POST /run` (record + summary + optional observed status) · `/replay` · `/ablation` · `/mfs` · `/boundary` · `/history` · `/sss` · `/address`.
Sizes are bounded (horizon ≤ 600, ≤ 64 interventions, ≤ 5 seeds). Nothing is stored on the server; the new routes are enumerated in the security test and the new layer
(`xzr.meos`, which imports nothing of the rest of the package) is declared in the layering test.

## 6. Reproducibility

A record carries the initial configuration, the seed, the interventions, the Address Domain parts that change by intervention, SSS, boundary configuration, every firing
event with its preconditions, the resource history (every field of every tick, 8-bit), interactions, the MEOS status trajectory and the termination reason, and two digests:
the input digest and the result digest. The only randomness is a small sensor noise and the initial jitter of R, drawn from `numpy.random.default_rng(seed)` in a fixed order.

## 7. Visual layer and its regression evidence

Static architecture is generated procedurally (seeded) with Three.js instancing: lattice trusses with drawn edges, the space frame of black glossy nodes in the shaft,
greeble plating, rails with carriages, manipulators, hanging cells, domes, a solar field, conveyors, an observation array, module bays, catenary cables, the strata of the
shaft wall and suspended material. Monochrome materials, no bloom, no colour. Three quality tiers change only the density of the decoration, never the simulation.

Captures of the specified states are in `docs/ecosystem/visual/` (`node frontend/scripts/ecosystem_capture.mjs`, headless Chromium, 1672×808 stage): overview, habitat,
Research Core, MEOS-0 active, MEOS collapse, XenoBody boundary overlay, history overlay and the subsurface laboratory. `backend/scripts/visual_compare.py` compares them with
the supplied reference images on crude statistics (the references are not stored in the repository); `metrics.json` has the numbers.

Honest reading of those numbers: the **Research Core** view is the closest to the reference imagery (monochrome: chroma 0.016 against 0.002; detail uniformity 0.80 against
0.85–0.93; detail density 0.19 against 0.35–0.44; mean luminance 0.38 against 0.26–0.29). The wide and habitat views are much sparser (detail density 0.14, large black areas
in the overview) and brighter than the references. The result approaches the references in the interior views; it does not match them, and no pixel-difference gate exists.

## 8. Performance

Measured on one machine (Apple M1, Metal via ANGLE, in the desktop app's browser pane), `docs/ecosystem/performance.json`: 60 fps sustained (vsync-limited, 240-frame windows,
p95 17.6–17.7 ms) in the three tiers, up to 975 k triangles, 65 k instances, 136 k drawn edge segments and 49–94 draw calls in the high tier; one 51 ms frame in a playing run;
simulation update 0.35–1.13 ms per tick; JS heap 20–30 MB. The headless captures use a software rasteriser (seconds per frame) and say nothing about GPU performance.
The simulation is computed by the server and drawn from the record, so rendering cannot change a result (tested).

## 9. Not implemented, and limits

* The future philosophical-AI connection (expressivist operations, normative sensitivity, scorekeeping, inferential operations, reason-responsive revision) is **not**
  implemented and not faked; only the extension points exist (the expansion sockets, the independent `xzr.meos` layer).
* Playback is of a deterministic record computed by the server, not live stepping of the engine; an intervention re-runs the whole record. The dynamic objects are the arena, the
  carriers, the power gauge, the stockpile, the array lamps and the trial chambers; **manipulators, rails, carriages and the rest of the structure are static**.
* Trial chambers show the results of the reduction runs (status and what was removed), not replays inside the chamber; "material insertion" exists as the resource pulse.
* The Observation Array exposes the sampling interval in the interface; spatial resolution and region exist in the API (`observe`) but have no controls. Transport of samples
  and information-bearing objects is not drawn; only resource transfers are.
* M2 (A2's alteration) is recorded and drawn but no configuration senses it.
* Visual similarity to the reference imagery is partial (section 7); there is no automated visual-difference test, only captures and statistics.
* The model is brittle in a narrow SSS band by construction of its tuning; the outcomes are not claims about real systems.
* Only the normal (host) build has the view: the static mirror, the iOS app and the in-browser runtime do not, because the engine runs on the server.
* Tested rendering: headless Chromium (software) and the desktop app's browser pane (Apple M1). Other browsers and GPUs were not tried.
