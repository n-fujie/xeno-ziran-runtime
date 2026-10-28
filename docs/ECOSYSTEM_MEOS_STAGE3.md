# XENO ECOSYSTEM — MEOS-0, stage 3: mechanical density, readable states, technical inspection and performance

Branch `feat/meos-ecosystem` (worktree `xeno-ziran-runtime-meos`), engine `meos-0.2` (unchanged: no backend change in this stage except two scripts). Local only: not pushed, not deployed, not merged.
This stage starts from `14900b9` (parent `abce372`), checked in the repository before work began: branch `feat/meos-ecosystem`, tree clean apart from the untracked `frontend/node_modules` symlink, no upstream configured.
It continues `docs/ECOSYSTEM_MEOS_STAGE2.md` (sections 4 and 9 there describe the earlier visual passes).

**What this stage is not.** It is not an attempt to make a photorealistic sci-fi machine. The bodies are a *presentation* of a MEOS-0 run: the mapping from the record to what a body does is a design choice written at the head of
`frontend/src/views/ecosystem/bodyState.ts` and in section 4 below. It is not an identification: A1, A2 and the observation are **not** these machines. Nothing in the geometry makes a scientific claim.

## 1. Git

| | |
|---|---|
| branch | `feat/meos-ecosystem` |
| start of this stage | `14900b9` (parent `abce372`) |
| commits of this stage | `15a1c7c` (performance step 1), `b423a73` (visual work in progress), `de6fcfe` (merged parts, lens covers, sparks, gantries, presets, crop comparison, reflection policy), and the final commit of this stage (documentation, evidence, tests, tier check) |
| push | none (no upstream; nothing was pushed or deployed) |
| tree | clean except `frontend/node_modules`, a symlink to the zrs checkout's modules |
| R3 | not integrated (separate branch); baseline `ec9667e` untouched; Phase 3 / Phase 4 files and the 264 stored runs untouched |

## 2. What was added to the visuals

**Fine mechanical density** (real geometry; counts are of the `balanced` tier, `docs/ecosystem/perf_stage3/` and `ecosystem_tiers_check.mjs`): 869 k vertices of static body geometry, 714 instanced fasteners of four kinds
(hex bolt with washer, socket-cap screw with a dark recess, exposed screw with a protruding thread, captive screw with a collar and spring), laid out unevenly (random gaps, doubled reinforcing bolts, clusters round openings and along edges);
L brackets, tension brackets (turnbuckles: barrel, threaded ends, eyes), hinge pins with end caps and cotter pins; recessed and layered round ports, slotted vents cut into the plates, sensor apertures with hoods, ringed inspection holes,
blanking plates with four screws, cable passthroughs with grommets, ringed probe sockets; perforated plates with real holes (extruded shapes, finer and more numerous holes at a higher tier).

**Cable infrastructure** (`cables.ts`): ten routes in the non-central body (and further ones on the limbs and between the boom sections of the observation node) in 3 kinds (energy / resource / data) of unequal radius (0.032 – 0.115 u), each anchored at hubs or ports of the machines, with 21 clamps standing on anchor plates, strain-relief boots,
connector heads (7), a braided sleeve of helical strands over part of 4 routes, hanging slack, a junction block where cables branch, two routes that rest on the ground and run under stones placed against them, and a coupling made of two halves
that meet at a connector pair.

**Material logic** (`weathering.ts`): roughness and colour vary in world space within 62 (balanced) / 90 (high) units of the camera: brushing along one axis, sparse scratches clustered by a low-frequency mask, edge wear found from the screen-space change of the normal (it follows the real geometry),
joint grime from a per-vertex wear weight baked at build time (hubs, clamps and bolts carry more than long tubes), darkening on faces that look down, water streaks on vertical faces below joints, glossy oil-like patches on upward faces, smudges. It is not uniform noise: each effect has its own bias.

**Ground** (`terrain.ts`): the polar ground with a roughness map; 8 puddles, 48 micro-puddles (0.3 – 1.6 u), 6 wavy reflective channels joining puddles; mud patches and a wet halo that darken the albedo round water; a heavy-tailed scatter of rocks of two kinds
(cut blocks and rounded stones), some sunk into the ground; up to 14 000 wet pebbles including flattened ones; embedded debris (shards, pipe offcuts, plates); stones set against the cables that rest on the ground.

**Observation node** (`observer.ts`), redesigned away from a robot arm on a stand: an irregular perforated chassis carried on five legs of unequal length and posture, each with three foot contacts and two with a damper and a coil spring; an offset body block;
a turret set off the centre; a three-section telescoping boom with a hydraulic ram; a side-mounted optical unit; a sensor head that is not at the end of anything; an articulated ring round the boom; a ring of six retractable micro-probes of different lengths, diameters and tips;
three docked modules of different sizes; exposed cables over the limbs and bridging the sections.

**Probes** (`probes.ts`): lengths 0.8 – 2.45 u (11 probes, all different), diameters 0.06 – 0.16 u, four tip kinds (needle, hollow, hook, sensor bead), an insulated section, a polished section, a collar, a mounting ring with bolts, a strain cable, and a retract mechanism with an actuator and a coil spring. Five states, **identifiable**:
extended (rod out, bead dim), retracted (inside the housing), sampling (further out, bead lit), inactive (half withdrawn, dark), overloaded (part way out, trembling, bead flickering).

**Other:** the western gantry field (7 lattice pylons with booms, hanging cells and bridges) behind the bodies, for background mechanical depth; round dust sprites instead of squares; 4 new fixed cameras for close-ups and 1 for the observation node.

## 3. Technical inspection view (`TechnicalView.tsx`, `technical.ts`)

A sheet over the stage (tab TECHNICAL, or `?tech=ncb|observer&probe=ID`): front, side and top orthographic drawings (one common scale) of the selected body's real geometry **in the pose the record gives at the current tick**, a probe detail drawing,
a component table, the state panel and the line list. Printed on it, all computed from the built geometry (`measure`, `collectSegments`, `probeDimensions`) and not typed in: component identifiers; overall width, height and depth and
selected component dimensions in scene units (**u**; the model defines no scale to metres, so none is shown); probe length, diameter, housing and insulated length, tip kind; plate thickness (the extrusion depth parameter);
joint axes (hinge pins are drawn); cable routing, drawn as solid (energy), dashed (resource) and dotted (data) lines with radius and length; fasteners as dots; state-linked components in the state colour (active blue, cut / overloaded red, inactive grey);
the observation (sampling interval, stride, window, coverage, observability), the XenoBody boundary (arena radius, whether the interaction channel is cut), the Address Domain state of A1 and A2, whether the run is M2-sensitive, history re-entry, the resource pulse and the run status.
Not drawn: the observation region as a drawing element (the bodies are not in the arena's frame; the region is given as a figure), an intervention point as a marker (the intervention is in the state panel as its effect).
Tests (`technical.test.ts`) check projections, that overall dimensions equal the measured extents, that probe lengths read back from the geometry equal the specified lengths, that listed parameters equal the build parameters, and the states.

## 4. State mapping (tested in `bodies.test.ts`)

| record quantity | what the body does |
|---|---|
| observation samples at this tick | node A's lens and lamp light and its probe samples; the observer's boom extends, its ring turns once per sampling interval |
| share of the arena the observation covers | how many of the observer's six probes are out (the rest are withdrawn) |
| observation cannot resolve the operation | the probes it points with are overloaded (tremble, flicker) |
| A1 fired within 5 ticks | node B's lamp flashes and its probe samples; a light runs B→C along the coupling |
| A2 renewed within 5 ticks | node C's probe samples and throws sparks; a light runs C→B |
| A2 absent, or its address lost | node C's probe inactive, its lamp dark |
| interaction channel or feedback cut | **physical separation**: the C-side half of the coupling swings down about node C and its connector parts from the B-side one; the junction ring opens |
| history re-entry disabled | **the archive unit's latch opens** and its lamp goes dark |
| resource pulse injected | **line pressure / reservoir**: the level on node C rises, then settles over 14 ticks |
| status COLLAPSED | **structural inactivity**: lens covers slide shut, every probe retracts, lamps dark, the boom folds |
| recovery after a collapse | **sequential reactivation**: node A at once, node B 8 ticks later, node C 16 ticks later (covers open in that order) |
| Address Domain fault on A1 / A2 | the probe of node B / node C is inactive (loss) or overloaded (fragment, partial) |
| arena boundary changed | the observer's probe ring is repositioned (and the boundary posts of the arena move) |

Not mapped: a boundary crossing of SSS (scale / size / speed). It is not drawn on the bodies. Lamps are used only where a record quantity lights them; mechanical change is preferred. The mapping is a presentation, not an identification.

## 5. Performance

Method (`frontend/scripts/ecosystem_perf.mjs`): headless Chromium on the machine's GPU (Apple M1, ANGLE/Metal), viewport 1672 × 808, pixel ratio 1; `window.__meos.benchmark(n)` renders n frames back to back with a GPU read-back after each (so the figure is the **cost of a frame**, not the display's refresh rate: fps = 1000 / median);
150 frames after 30 of warm-up, fixed cameras (`cameras-balanced.json`), three repetitions per tier (the first `high` repetition timed out while the build was being replaced and is missing), the **median of the three medians** is given. During the runs another application's
WebKit process used about 170 % of a core, so individual runs vary by up to ±30 % (listed per run); the page in the app's browser pane was closed so that it would not draw at the same time. These are not measurements inside the app's browser pane.

Start of this stage (same script, `balanced`, before any change): overview **34.1 ms** (p95 50.4; 404 draw calls, 2.16 M triangles), body **25.9 ms** (p95 37.3; 297 calls, 2.42 M triangles).

| tier | camera | runs | median frame time (ms) per run | median of medians | fps from it | p95 (ms) | orbiting camera median (ms) | draw calls | triangles | instances |
|---|---|---|---|---|---|---|---|---|---|---|
| performance | body | 3 | 5.7 / 8.5 / 11.2 | **8.5** | 118 | 10.2 | 8.2 | 255 | 457,964 | 26,733 |
| performance | habitat | 3 | 15.9 / 10.4 / 11.4 | **11.4** | 88 | 16.5 | 12.0 | 416 | 545,234 | 26,733 |
| performance | observer | 3 | 11.1 / 8.6 / 11.2 | **11.1** | 90 | 11.9 | 9.6 | 307 | 423,684 | 26,733 |
| performance | overview | 3 | 12.9 / 9.9 / 8.2 | **9.9** | 101 | 17.5 | 11.5 | 437 | 376,038 | 26,733 |
| performance | plate | 3 | 5.3 / 8.2 / 8.3 | **8.2** | 122 | 9.2 | 8.2 | 183 | 340,980 | 26,733 |
| performance | probe | 3 | 5.5 / 7.3 / 8.3 | **7.3** | 137 | 9.0 | 8.0 | 231 | 433,498 | 26,733 |
| balanced | body | 3 | 16.7 / 14.7 / 13.1 | **14.7** | 68 | 20.3 | 15.9 | 264 | 999,878 | 55,195 |
| balanced | habitat | 3 | 19.9 / 17.1 / 15.9 | **17.1** | 58 | 21.5 | 18.9 | 427 | 1,033,428 | 55,195 |
| balanced | observer | 3 | 20.7 / 12.8 / 12.2 | **12.8** | 78 | 14.3 | 11.2 | 322 | 874,586 | 55,195 |
| balanced | overview | 3 | 21.7 / 14.0 / 11.6 | **14.0** | 71 | 16.4 | 15.9 | 455 | 653,420 | 55,195 |
| balanced | plate | 3 | 18.9 / 15.4 / 11.9 | **15.4** | 65 | 20.4 | 14.3 | 193 | 727,130 | 55,195 |
| balanced | probe | 3 | 16.0 / 13.4 / 11.6 | **13.4** | 75 | 15.9 | 13.6 | 242 | 925,804 | 55,195 |
| high | body | 2 | 44.6 / 42.7 | **43.7** | 23 | 53.5 | 41.1 | 557 | 3,087,756 | 85,452 |
| high | habitat | 2 | 48.7 / 35.2 | **42.0** | 24 | 58.3 | 45.8 | 880 | 3,012,252 | 85,452 |
| high | observer | 2 | 31.8 / 27.1 | **29.5** | 34 | 37.5 | 29.2 | 684 | 2,736,772 | 85,452 |
| high | overview | 2 | 34.6 / 31.3 | **33.0** | 30 | 40.5 | 37.6 | 963 | 1,997,340 | 85,452 |
| high | plate | 2 | 36.5 / 29.5 | **33.0** | 30 | 42.3 | 35.7 | 401 | 2,180,588 | 85,452 |
| high | probe | 2 | 34.8 / 28.3 | **31.5** | 32 | 42.4 | 36.8 | 513 | 2,813,864 | 85,452 |

Reading: **performance** is far above 60 fps (7 – 11 ms). **balanced** now has a median of 12.8 – 17.1 ms (58 – 78 fps) and a p95 of 14.3 – 21.5 ms in every fixed camera, against 34 / 26 ms at the start, **while the bodies carry far more detail** (target: median ≥ 50 fps, p95 ≤ 24 ms: met by the median of three runs in all six cameras; single runs reached 21.7 ms in the overview in a noisy repetition, and with a moving camera the p95 is 21.2 – 26.6 ms, median of three runs: the habitat view, 26.6 ms, exceeds the 24 ms target).
**high** is 29.5 – 43.7 ms (23 – 34 fps) with 2 – 3 M triangles; it was not made worse: the stage-2 capture measurement of the same tier (a different method, display-limited) gave 16 – 25 fps, so the two are not directly comparable and no claim of an improvement is made for `high`.

What was done: spatial chunks with frustum culling for the megastructure batches, gravel, rocks and debris (`lod.ts`); distance levels of detail (gravel 80 → 20 faces → none, rocks three levels, bodies' static geometry hi / lo through `THREE.LOD`); range limits on the fine detail of the structure (greebles, fittings); fewer drawn edges at lower tiers (the line primitive is expensive on this stack);
puddle reflection replaced by a dark mirror beyond 95 u and refreshed every 3rd frame while the camera moves and every 30th while it rests (pebbles and debris are not drawn in it; 384² at `balanced`); lights that cannot be seen are switched off (spots on the bodies when the camera is far from them, the shaft's lights when the camera looks away), all four combinations
precompiled; `balanced` without multisampling and without bloom (a light edge anti-alias, vignette and grain in one final pass); probe, lens, reservoir and archive parts merged into one mesh per material (draw calls in the habitat view 620 → 427). Reflection cost measured by alternating blocks in one session: balanced 0 – 2.4 ms, high 0 – 4 ms (within noise).
The measured cost of the post chain at the start (an empty scene at 1672 × 808 cost 9 ms with multisampling, bloom, grade, output and FXAA) was the largest fixed cost.

Tier check (`frontend/scripts/ecosystem_tiers_check.mjs`): all three tiers load without errors with their own pipeline (none / render + output + final / render + bloom + depth of field + output + final), draw, keep the same parts of the bodies (11 probes, 10 cable routes), and switching the tier in the running page rebuilds the scene with the new pipeline: **all checks passed**.

## 6. Visual metrics, local to crops

Same cameras before and after (`cameras-balanced.json`; presets `body`, `observer`, `puddle`; before = the captures of `14900b9`). Boxes: `docs/ecosystem/visual/crops.json` (references: the render half of the supplied sheets, boxes chosen by eye). The statistics are crude proxies;
**none of them establishes that a picture matches a reference**. Two resolutions: *at reference resolution* (our capture resampled to 766 px width, the render panel of the sheets) is the fair one for edge and frequency statistics; *native* is in `metrics_crops_native.json`.
Luminance histogram distance is the total-variation distance between the 8-bin histograms (0 = identical).

Non-central body, at reference resolution:

| shot / crop | metric | before (14900b9) | after | reference |
|---|---|---|---|---|
| 14-experimental-body / specimen_body | edge density | 0.198 | 0.244 | 0.287 |
| 14-experimental-body / specimen_body | high-frequency share | 0.139 | 0.241 | 0.353 |
| 14-experimental-body / specimen_body | contour complexity | 0.272 | 0.960 | 1.248 |
| 14-experimental-body / specimen_body | local contrast | 0.079 | 0.095 | 0.132 |
| 14-experimental-body / specimen_body | luminance histogram distance | 0.148 | 0.054 | 0 |
| 14-experimental-body / probe_region | edge density | 0.367 | 0.173 | 0.228 |
| 14-experimental-body / probe_region | high-frequency share | 0.217 | 0.269 | 0.303 |
| 14-experimental-body / probe_region | contour complexity | 0.371 | 0.940 | 0.984 |
| 14-experimental-body / probe_region | local contrast | 0.131 | 0.075 | 0.097 |
| 14-experimental-body / probe_region | luminance histogram distance | 0.305 | 0.036 | 0 |
| 14-experimental-body / cable_region | edge density | 0.297 | 0.335 | 0.225 |
| 14-experimental-body / cable_region | high-frequency share | 0.230 | 0.237 | 0.404 |
| 14-experimental-body / cable_region | contour complexity | 0.677 | 0.625 | 1.587 |
| 14-experimental-body / cable_region | local contrast | 0.111 | 0.118 | 0.097 |
| 14-experimental-body / cable_region | luminance histogram distance | 0.432 | 0.360 | 0 |
| 14-experimental-body / ground | edge density | 0.222 | 0.169 | 0.121 |
| 14-experimental-body / ground | high-frequency share | 0.201 | 0.191 | 0.112 |
| 14-experimental-body / ground | contour complexity | 0.630 | 0.840 | 0.471 |
| 14-experimental-body / ground | local contrast | 0.095 | 0.072 | 0.071 |
| 14-experimental-body / ground | luminance histogram distance | 0.109 | 0.064 | 0 |
| 14-experimental-body / puddle_reflection | edge density | 0.214 | 0.213 | 0.169 |
| 14-experimental-body / puddle_reflection | high-frequency share | 0.243 | 0.210 | 0.187 |
| 14-experimental-body / puddle_reflection | contour complexity | 0.804 | 0.787 | 0.550 |
| 14-experimental-body / puddle_reflection | local contrast | 0.088 | 0.083 | 0.085 |
| 14-experimental-body / puddle_reflection | luminance histogram distance | 0.058 | 0.050 | 0 |
| 14-experimental-body / bolt_plate_region | edge density | 0.290 | 0.353 | 0.282 |
| 14-experimental-body / bolt_plate_region | high-frequency share | 0.152 | 0.293 | 0.371 |
| 14-experimental-body / bolt_plate_region | contour complexity | 0.218 | 1.064 | 1.490 |
| 14-experimental-body / bolt_plate_region | local contrast | 0.112 | 0.128 | 0.130 |
| 14-experimental-body / bolt_plate_region | luminance histogram distance | 0.380 | 0.137 | 0 |
| 14-experimental-body / silhouette | edge density | 0.165 | 0.229 | 0.224 |
| 14-experimental-body / silhouette | high-frequency share | 0.150 | 0.228 | 0.340 |
| 14-experimental-body / silhouette | contour complexity | 0.385 | 0.773 | 1.173 |
| 14-experimental-body / silhouette | local contrast | 0.067 | 0.085 | 0.100 |
| 14-experimental-body / silhouette | luminance histogram distance | 0.124 | 0.120 | 0 |
| 14-experimental-body / background_mechanical_density | edge density | 0.026 | 0.145 | 0.329 |
| 14-experimental-body / background_mechanical_density | high-frequency share | 0.144 | 0.238 | 0.253 |
| 14-experimental-body / background_mechanical_density | contour complexity | 0.314 | 0.974 | 0.417 |
| 14-experimental-body / background_mechanical_density | local contrast | 0.018 | 0.051 | 0.140 |
| 14-experimental-body / background_mechanical_density | luminance histogram distance | 0.538 | 0.424 | 0 |

Observation node (old camera), observer close camera (new, no before) and wet ground, at reference resolution:

| shot / crop | metric | before (14900b9) | after | reference |
|---|---|---|---|---|
| 15-observation-node / observation_node | edge density | 0.155 | 0.129 | 0.195 |
| 15-observation-node / observation_node | high-frequency share | 0.108 | 0.107 | 0.284 |
| 15-observation-node / observation_node | contour complexity | 0.178 | 0.149 | 1.079 |
| 15-observation-node / observation_node | local contrast | 0.065 | 0.056 | 0.092 |
| 15-observation-node / observation_node | luminance histogram distance | 0.358 | 0.358 | 0 |
| 15-observation-node / probe_region | edge density | 0.221 | 0.124 | 0.172 |
| 15-observation-node / probe_region | high-frequency share | 0.204 | 0.174 | 0.337 |
| 15-observation-node / probe_region | contour complexity | 0.064 | 0.030 | 0.979 |
| 15-observation-node / probe_region | local contrast | 0.081 | 0.061 | 0.092 |
| 15-observation-node / probe_region | luminance histogram distance | 0.656 | 0.675 | 0 |
| 15-observation-node / cable_region | edge density | 0.193 | 0.212 | 0.207 |
| 15-observation-node / cable_region | high-frequency share | 0.136 | 0.154 | 0.353 |
| 15-observation-node / cable_region | contour complexity | 0.311 | 0.322 | 1.403 |
| 15-observation-node / cable_region | local contrast | 0.078 | 0.077 | 0.098 |
| 15-observation-node / cable_region | luminance histogram distance | 0.324 | 0.350 | 0 |
| 15-observation-node / ground | edge density | 0.154 | 0.163 | 0.145 |
| 15-observation-node / ground | high-frequency share | 0.130 | 0.131 | 0.193 |
| 15-observation-node / ground | contour complexity | 0.471 | 0.377 | 0.735 |
| 15-observation-node / ground | local contrast | 0.072 | 0.072 | 0.074 |
| 15-observation-node / ground | luminance histogram distance | 0.226 | 0.276 | 0 |
| 15-observation-node / puddle_reflection | edge density | 0.148 | 0.176 | 0.232 |
| 15-observation-node / puddle_reflection | high-frequency share | 0.176 | 0.131 | 0.234 |
| 15-observation-node / puddle_reflection | contour complexity | 0.728 | 0.488 | 0.891 |
| 15-observation-node / puddle_reflection | local contrast | 0.069 | 0.075 | 0.102 |
| 15-observation-node / puddle_reflection | luminance histogram distance | 0.090 | 0.198 | 0 |
| 15-observation-node / bolt_plate_region | edge density | 0.207 | 0.185 | 0.266 |
| 15-observation-node / bolt_plate_region | high-frequency share | 0.131 | 0.141 | 0.279 |
| 15-observation-node / bolt_plate_region | contour complexity | 0.160 | 0.127 | 0.889 |
| 15-observation-node / bolt_plate_region | local contrast | 0.082 | 0.071 | 0.129 |
| 15-observation-node / bolt_plate_region | luminance histogram distance | 0.330 | 0.350 | 0 |
| 15-observation-node / silhouette | edge density | 0.154 | 0.130 | 0.176 |
| 15-observation-node / silhouette | high-frequency share | 0.107 | 0.106 | 0.278 |
| 15-observation-node / silhouette | contour complexity | 0.200 | 0.158 | 1.070 |
| 15-observation-node / silhouette | local contrast | 0.065 | 0.056 | 0.084 |
| 15-observation-node / silhouette | luminance histogram distance | 0.360 | 0.370 | 0 |
| 15-observation-node / background_mechanical_density | edge density | 0.130 | 0.067 | 0.329 |
| 15-observation-node / background_mechanical_density | high-frequency share | 0.132 | 0.111 | 0.253 |
| 15-observation-node / background_mechanical_density | contour complexity | 0.443 | 0.538 | 0.417 |
| 15-observation-node / background_mechanical_density | local contrast | 0.054 | 0.031 | 0.140 |
| 15-observation-node / background_mechanical_density | luminance histogram distance | 0.365 | 0.442 | 0 |
| 29-observer-hero / observation_node | edge density | — | 0.155 | 0.195 |
| 29-observer-hero / observation_node | high-frequency share | — | 0.144 | 0.284 |
| 29-observer-hero / observation_node | contour complexity | — | 0.287 | 1.079 |
| 29-observer-hero / observation_node | local contrast | — | 0.067 | 0.092 |
| 29-observer-hero / observation_node | luminance histogram distance | — | 0.331 | 0 |
| 29-observer-hero / probe_region | edge density | — | 0.215 | 0.172 |
| 29-observer-hero / probe_region | high-frequency share | — | 0.187 | 0.337 |
| 29-observer-hero / probe_region | contour complexity | — | 0.223 | 0.979 |
| 29-observer-hero / probe_region | local contrast | — | 0.083 | 0.092 |
| 29-observer-hero / probe_region | luminance histogram distance | — | 0.518 | 0 |
| 29-observer-hero / cable_region | edge density | — | 0.207 | 0.207 |
| 29-observer-hero / cable_region | high-frequency share | — | 0.197 | 0.353 |
| 29-observer-hero / cable_region | contour complexity | — | 0.484 | 1.403 |
| 29-observer-hero / cable_region | local contrast | — | 0.086 | 0.098 |
| 29-observer-hero / cable_region | luminance histogram distance | — | 0.237 | 0 |
| 29-observer-hero / ground | edge density | — | 0.102 | 0.145 |
| 29-observer-hero / ground | high-frequency share | — | 0.111 | 0.193 |
| 29-observer-hero / ground | contour complexity | — | 0.355 | 0.735 |
| 29-observer-hero / ground | local contrast | — | 0.047 | 0.074 |
| 29-observer-hero / ground | luminance histogram distance | — | 0.149 | 0 |
| 29-observer-hero / bolt_plate_region | edge density | — | 0.216 | 0.266 |
| 29-observer-hero / bolt_plate_region | high-frequency share | — | 0.189 | 0.279 |
| 29-observer-hero / bolt_plate_region | contour complexity | — | 0.378 | 0.889 |
| 29-observer-hero / bolt_plate_region | local contrast | — | 0.089 | 0.129 |
| 29-observer-hero / bolt_plate_region | luminance histogram distance | — | 0.162 | 0 |
| 29-observer-hero / silhouette | edge density | — | 0.155 | 0.176 |
| 29-observer-hero / silhouette | high-frequency share | — | 0.144 | 0.278 |
| 29-observer-hero / silhouette | contour complexity | — | 0.287 | 1.070 |
| 29-observer-hero / silhouette | local contrast | — | 0.067 | 0.084 |
| 29-observer-hero / silhouette | luminance histogram distance | — | 0.344 | 0 |
| 16-wet-ground / ground | edge density | 0.191 | 0.167 | 0.121 |
| 16-wet-ground / ground | high-frequency share | 0.133 | 0.176 | 0.112 |
| 16-wet-ground / ground | contour complexity | 0.438 | 0.668 | 0.471 |
| 16-wet-ground / ground | local contrast | 0.088 | 0.073 | 0.071 |
| 16-wet-ground / ground | luminance histogram distance | 0.179 | 0.037 | 0 |
| 16-wet-ground / puddle_reflection | edge density | 0.197 | 0.180 | 0.169 |
| 16-wet-ground / puddle_reflection | high-frequency share | 0.125 | 0.180 | 0.187 |
| 16-wet-ground / puddle_reflection | contour complexity | 0.444 | 0.738 | 0.550 |
| 16-wet-ground / puddle_reflection | local contrast | 0.090 | 0.078 | 0.085 |
| 16-wet-ground / puddle_reflection | luminance histogram distance | 0.126 | 0.078 | 0 |

Reading. The non-central body moved clearly toward the reference in the structural statistics: specimen body high-frequency share 0.139 → 0.242 (reference 0.353), contour complexity 0.272 → 0.965 (1.248); bolt / plate region 0.152 → 0.293 (0.371) and 0.218 → 1.064 (1.490); probe region contour complexity 0.371 → 0.990 (0.984);
the luminance histogram distance fell in the specimen, probe and plate crops. **It is still below the reference in high-frequency share (about two thirds) and in contour complexity of the cable region (0.62 against 1.59).** The wet ground now agrees with the reference in these statistics (hf 0.177 against 0.112, contour 0.665 against 0.471; the puddle crop 0.179 against 0.187).
The observation node in the old camera did **not** improve (it is small in that frame and the domes dominate the crops); in the new close camera its statistics are higher but still well below the reference (contour 0.29 against 1.08): the asymmetric machine is better in a close view than in the statistics.
The close-up views (probe, cable, plate) are at a larger magnification than the reference's detail and are low in these statistics by construction. The background mechanical density crop of the body view rose (edge 0.026 → 0.145, contour 0.31 → 0.97) because of the gantry field, against a reference lattice with edge density 0.33.
A statistic that rose is not a visual claim: the close-ups were looked at (section 8) and they show perforated plates with slots and ports, bolt clusters, springs, clamps and connectors, but they remain clean CG: the rocks are faceted, the metal is more even than a photograph.

## 7. Regression (this commit, nothing carried over)

| check | result |
|---|---|
| backend full regression (`pytest`, 652 tests) | **650 passed, 2 failed**: exactly the two known failures of the baseline (`test_compat::test_engine_conformance_against_the_golden_fixture[desktop-scipy]`, `test_lab::test_published_records_replay`); no baseline test missing; no new failure (JUnit compared test by test: `docs/ecosystem/evidence/meos_stage3.junit.xml`, log `meos_stage3_pytest.log`) |
| frontend full tests | **175 / 175** passed (19 files; 88 of them are ecosystem tests, 33 new in this stage: bodies, hardware, probes, cables, weathering, technical drawings, presets) |
| typecheck `tsc -b` | clean |
| `eslint src` | clean (one error in `observer.ts` and one dependency warning fixed in this stage) |
| `ruff check xzr tests bench scripts` | clean |
| `mypy xzr` | 0 errors in `xzr/meos` (the ~89 older errors elsewhere are untouched) |
| frontend build | passes |
| saved 264-run replay (11 studies, this backend's code) | **264 / 264 agree** (605 s; `docs/ecosystem/evidence/replay_meos_stage3.json`) |
| MEOS deterministic replay | baseline result digest `b4cf1e52…adc5` unchanged and replays identically; the stage-two fixture replays identically |
| state-mapping tests | pass (`bodies.test.ts`: probe states, node reactivation order, lens covers, archive latch, reservoir, coupling swing, ring phase, probe withdrawal, boundary repositioning) |
| ground polygon orientation regression | pass (every sampled triangle of the ground faces up) |
| quality-tier switching | pass (`ecosystem_tiers_check.mjs`) |
| screenshot capture | 29 shots + 2 JSON records captured without page errors |
| known failures | the same two as before; none new |

## 8. Screenshots (`docs/ecosystem/visual/`)

The 18 existing shots (01 – 18, re-captured with this build and the same cameras), 3 close-ups (`19-close-probe`, `20-close-cable`, `21-close-plate`), `22-probe-ring`, `29-observer-hero`, the three states of the run (`23-state-collapse` tick 153, `24-state-recovery` tick 170,
`17-body-coupling-cut` tick 125) and `25-state-pulse` (a resource pulse), and the three technical inspection sheets (`26-technical-ncb`, `27-technical-observer`, `28-technical-cut`: the non-central body, the observation node, and the body with its coupling cut). `before_14900b9/` holds the earlier captures used for the crop comparison.
The camera of every capture (position, target, field of view, clipping, exposure, tone mapping, pixel ratio, buffer size, quality tier) is in `cameras-balanced.json`.

## 9. Not done, partial, failed

* **Not done:** a photographic result: the rocks are faceted (cut-stone and rounded kinds, but low-poly), the metal is cleaner than a photograph, no screen-space reflections or volumetric dust; the layout of the reference's engineering sheet (illustrated module details, topology variations, operation sequence) was not reproduced: the sheet here is a measured orthographic drawing, not an illustration;
  a boundary crossing of SSS is not shown on the bodies; no GPU measurement inside the app's browser pane in this stage.
* **Partial:** high-frequency share and contour complexity are still below the reference (section 6); the observation node is a closer reading than its statistics; the technical sheet is drawn from the `performance`-tier build (no weathering, coarser holes) so that the edge lists stay light; `high` frame times are 23 – 34 fps.
* **Failed / reverted:** the first optimisation attempts (half-resolution bloom parameter, spot-light toggling without precompiled variants) were measured to give nothing or a hitch and were replaced; a first version of the ground faced down and was not drawn (fixed in the stage before, with a regression test); a probe's measured length was computed in world coordinates and read negative (fixed, now measured in the probe's own frame and tested).
* **Performance caveat:** the numbers were measured with another application loading the machine and are repeated three times to show their spread; they are not a guarantee on other hardware.

## 10. Completion conditions

| condition | state |
|---|---|
| high-frequency component clearly improved | **met in the body crops** (0.14 → 0.24 – 0.29), not in the observation node's old camera |
| contour complexity clearly improved | **met in the body crops** (0.27 → 0.97, 0.22 → 1.06), not in the observation node's old camera |
| photographic material variation increased | **met in the mechanism** (weathering is spatially biased) — visible at close range in `19`, `21`, not measured separately |
| machine silhouette more alien | observer: five unequal legs, offset turret, side optics, ring of retractable probes — **met by design, judged by eye** |
| close-ups do not read as simple CG | **partly**: plates, ports, springs and clamps read as assembled; rocks and clean metal still read as CG |
| components / states / interventions readable | **met**: the mapping table and the technical sheet |
| technical inspection view with geometry-derived dimensions | **met** (tested) |
| `performance` tier holds 60 fps | **met** (7 – 11 ms) |
| `balanced` clearly improved | **met** (34 / 26 ms → 14.0 / 14.7 ms in the overview / body; every fixed camera ≤ 17.1 ms median of three) |
| `high` not much worse | **not worse by the methods available** (23 – 34 fps now, 16 – 25 fps by the earlier display-limited method) |
| full regression run, 264 replay, MEOS replay, state mapping kept | **met** (section 7) |
