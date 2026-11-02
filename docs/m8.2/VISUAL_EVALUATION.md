# M8.2 — Independent visual evaluation and refinement

Branch `lab-m8-visual-refinement`, from `lab-m8-visual-verification` at `705288c` (checkpoint tag
`m8.2-checkpoint-start`). The scientific runtime, records, protocols and level statuses are untouched:

- **Level 1:** achieved.
- **Level 2:** partially demonstrated, not achieved under the frozen criteria.
- **Level 3:** not achieved.

The laboratory visualises recorded simulation-internal runs. It is not evidence of autonomous science.

## 1. Baseline verified

These facts were checked directly before any change:

- **Git.** `HEAD` is `705288c`, and `origin/lab-m8-visual-verification` has the same hash. The tree was clean.
- **Service.** The local service answered on 127.0.0.1:3011.
- **Test suites.** These were rerun on the baseline; the results are listed in §8.
- **Baseline capture.** `docs/m8.2/00-baseline/1200x866@1/` holds every scene rendered from the unmodified M8.1 code.
  Two required viewpoints were missing from the capture script and were added: `17-distributed-sensor` (one of system
  B's remote sensors) and `18-gantry-closeup` (a carriage during a recorded carry).
- **Images inspected.** All M8.1 final images (`docs/m8.1/08-final/1920x1080@1/*.png`) were opened at full resolution,
  and the gantry tool and an overhead terminal were cropped and enlarged.

## 2. Initial evaluation (M8.1 final, before any M8.2 change)

The scores are conservative, from 0 to 100. Engineering correctness (dimension I) is scored separately from artistic
completion. Passing tests did not raise any other score.

| scene (M8.1 image) | A mech. sophistication | B arch. originality | C sci. legibility | D struct. coherence | E density | F distinctiveness | G material / light | H composition | I sci. fidelity | J overall |
|---|---|---|---|---|---|---|---|---|---|---|
| 01 overview | 40 | 50 | 45 | 65 | 55 | 35 | 50 | 60 | 85 | 48 |
| 02 oblique | 45 | 45 | 30 | 60 | 60 | 30 | 45 | 40 | 85 | 40 |
| 03 domain | 50 | 45 | 55 | 70 | 55 | 40 | 50 | 60 | 85 | 50 |
| 05 transport | 35 | 30 | 50 | 60 | 40 | 30 | 45 | 55 | 75 | 40 |
| 06 grasp / gantry close-up | 35 | 30 | 45 | 55 | 40 | 35 | 45 | 45 | 75 | 38 |
| 07 system A sensor | 55 | 40 | 50 | 65 | 50 | 55 | 50 | 55 | 85 | 50 |
| 15 system B receiver | 45 | 40 | 40 | 60 | 40 | 50 | 45 | 40 | 85 | 42 |
| 17 system B remote sensor | — | — | — | — | — | — | — | — | — | — (defect: the camera showed the hub, see P6) |
| 16 system C store | 35 | 30 | 55 | 60 | 35 | 50 | 45 | 50 | 85 | 40 |
| 08 observation restricted | 45 | 40 | 55 | 65 | 55 | 35 | 50 | 60 | 85 | 50 |
| 09 shared resource | 35 | 30 | 35 | 60 | 40 | 30 | 45 | 50 | 80 | 38 |
| 10 extinction | 45 | 45 | 50 | 70 | 55 | 35 | 50 | 60 | 85 | 50 |
| 11 re-ignition | 45 | 45 | 45 | 70 | 55 | 35 | 50 | 60 | 85 | 48 |
| 14 live operation | 40 | 50 | 40 | 65 | 55 | 35 | 45 | 55 | 85 | 45 |

### Evidence behind the scores

**I, scientific fidelity (75–85).** The in-page self-test matches every carriage and sample to its recorded MuJoCo
position, with a worst error of 5.4×10⁻⁷ m. Fidelity is still not 100, because the drawn gripper does not touch the
sample it is recorded as holding (see P1). In the shared-resource scene, the sharing is visible only in the panel.

**A, mechanical sophistication (35–55).**
- The gantry tool is a bare box with two small square tabs, sitting *above* the carried cube (crop:
  `docs/m8.1/08-final/1920x1080@1/05-transport.png`, region 600–960 × 330–700). No jaw, wrist or guide is visible.
- The chamber walls are flat white slabs with no stiffeners, seams or flanges.
- The articulated system-A boom is the most convincing mechanism.

**B, architectural originality (30–50).**
- The plan is identifiable: a circular hall, eight radial bays and a central core.
- At eye level the scene reads as rows of identical white bins in a dark warehouse (05, 06, 09).
- The central core is an undifferentiated six-sided prism (01, 02, 14).

**C, scientific legibility (30–55).**
- Extinction is legible from the 0-chamber observation and the closed louvres.
- In the oblique view, the overhead connection lines (hundreds of thin bright strokes fanning from the ceiling
  terminals) dominate the upper half of the frame and hide the apparatus behind them.
- Shared-resource interference is not visible in 3D.

**D, structural coherence (55–70).** M8.1 verified the supports, hangers and envelopes. The remaining incoherence is the
tool–sample relationship (P1).

**E, density (35–60).** The domain and dense views are reasonably full. Close views are dominated by large blank wall
planes (05, 06, 09, 16).

**F, distinctiveness (30–55).**
- The A boom, the B rings and the C slot rack are distinct.
- The C store reads as a lit window panel rather than a retained-record apparatus (16).
- The B receiver's three rings read as a coil spring (15).

**G, material and lighting (45–50).** Legible since M8.1, but the ceramic walls clip to near-white under the exposure and
lose form (05, 09, 16). There is no atmospheric depth: far bays are as contrasty as near ones (02).

**H, composition (40–60).** The fixed cameras are sound. The oblique view has no depth separation, and the hub view
(15) is dominated by a foreground wall.

**J, overall (38–50).** A legible, honest instrument view, not yet a sophisticated installation.

## 3. Highest-impact remaining problems (ranked)

The ranking weighs visual impact, scientific importance, mechanical plausibility, complexity and regression risk.

### P1. The gantry tool does not grasp the sample

- **Screenshots:** 05, 06, 18 (crop above).
- **Defect:** The recorded weld grasp is drawn as two 2 cm tabs over the cube's top face. The transfer mechanism, the
  laboratory's central executable operation, is not readable.
- **Correction:**
  - Keep the MuJoCo carriage and tool boxes exactly.
  - Add a wrist flange, a jaw guide, and two parallel jaws that reach down both sides of the cube.
  - The jaws are closed only while a grasp is recorded (`carrying`), and open otherwise.
- **Expected improvement:** A transfer reads as grasp, carry and release.
- **Verification:**
  - closed-jaw faces meet the recorded sample faces at every carrying step;
  - open jaws never intersect another sample or a chamber wall at any recorded tip position;
  - envelope sweep.
- **Risk:** jaw geometry entering neighbouring samples in a port, which is tested.

### P2. Chamber housings are blank, identical white slabs

- **Screenshots:** 03, 05, 06, 09, 16.
- **Defect:** The largest surfaces in every close view carry no structure, and they blow out to white.
- **Correction:**
  - Keep the MuJoCo walls exactly.
  - Add exterior wall stiffeners, a coping flange and a base flange (category 4, outside the walls and below the
    rim).
  - Reduce the ceramic albedo slightly so that form shading survives.
- **Expected improvement:** Engineered vessels instead of bins.
- **Verification:**
  - stiffeners stay outside the wall's outer face and below `TRAVEL_TOP`;
  - envelope sweep;
  - draw calls are unchanged (merged into the global chamber statics).
- **Risk:** extra triangles.

### P3. The overhead connection network dominates the far field

- **Screenshots:** 02, 03, 11, 14.
- **Defect:** Every connection is a full-contrast line at any distance. The fans of strokes read as decorative cables,
  which the design direction says to avoid.
- **Correction:**
  - Add atmospheric depth: exponential fog matched to the background, which affects every material including the lines.
  - Lower the contrast of idle connections. Connections active in a recorded event stay bright.
  - No connection is removed.
- **Expected improvement:** Depth layering, and the apparatus stays dominant.
- **Verification:**
  - the connection signature is unchanged (the same pairs and counts);
  - event-hot connections are still drawn at full brightness;
  - screenshots.
- **Risk:** over-darkening the far bays in the overview.

### P4. The central core is an undifferentiated prism

- **Screenshots:** 01, 02, 14.
- **Defect:** The largest single object in the overview has no structure. It reads as a placeholder.
- **Correction:** Articulate it as structure (category 4): ring girders, vertical ribs, service galleries and roof-beam
  seats. It makes no functional claim.
- **Expected improvement:** A credible centre for the installation.
- **Verification:** Screenshots; it stays outside every reach hull; draw calls (merged).
- **Risk:** low.

### P5. The System C store reads as a lit window and the System B receiver as a coil

- **Screenshots:** 15, 16.
- **Defect:** The forms do not communicate their roles: retained records and their retrieval for C; relational
  measurement across distributed sensors for B.
- **Correction:**
  - **C:** a cartridge rack. Each recorded entry is a cartridge drawn in its slot; empty slots stay recessed.
  - **B:** horizontal receiver rings with radial struts and a pickup on each ring at the bearing of each remote sensor
    (from the recorded configuration).
- **Verification:**
  - the filled count still equals the recorded memory entries;
  - the pickup bearings equal the bearings of the recorded remote sensors;
  - the interpenetration test.
- **Risk:** implying an independent decision mechanism. Labels keep "shared decision rule".

### P6 (defect found while capturing, not a visual-quality ranking)

Selecting a remote B sensor focused the hub, because `focus()` ignored pod ids: scene 17 shows the hub. This is fixed
along with P5.

## 4. Implementation log

(Each change follows the cycle: before screenshot, one bounded change, tests, build, render, capture, direct
inspection, fidelity and performance check, accept or revert, commit.)

### Change 1: gripper, carried-load clearance, instruments outside the reach (P1, plus a defect found while doing it)

- **Before:** `00-baseline/1200x866@1/05-transport.png`, `06-sample-grasp.png`, `18-gantry-closeup.png`,
  `07-sensor-assembly.png`, `15-hub.png`, `16-memory-store.png`, `17-distributed-sensor.png`.
- **After:** the same files under `01-transport-envelope/1200x866@1/`.

**Gripper.** The MuJoCo carriage and tool boxes are unchanged. Additions:

- a wrist flange and a jaw guide, merged with the tool;
- two parallel jaws (layer A, category 3). They are closed exactly while `carrying` is recorded, with their inner
  faces 4 mm from the sample faces, and open by 8 cm otherwise.

The enlarged crops show a parallel clamp on the cube: the near jaw lies on the face toward the camera, and the far jaw
shows above the cube.

**Defect found by the new tests: carried samples passed through the apparatus.** M8.1's travel plane
(`TRAVEL_TOP` = 1.55 m) considered only the tool. The recorded weld puts a carried sample 0.255 m below the tip.
Worn gantries sag (lower servo gain), and the lowest recorded carried-sample bottom is 1.026 m, only 7.6 cm above the
chamber walls (0.95 m). The recorded runs therefore carried samples through:

- the louvre crown on the walls (m7 step 19, chamber 0.0);
- B's remote sensor at 0.1 (m7 step 258);
- other apparatus, as the tests showed.

None of these is in the physics model: they were drawn additions in M8.

**Correction (redesigned visual structure; no physics change).**

- **Travel limit.** `TRAVEL_TOP` = 0.98 m: inside a reach envelope, nothing static rises above the walls.
- **Containment louvres.** These are still driven by recorded closure. They moved from a crown on the wall tops to a
  shutter band on the outer upper wall face (0.70–0.94 m), with the actuator housings outside it.
- **Chamber instrument column.** It is now 0.65 m tall (top 0.95 m). The memory bar's full scale is 0.6 m (the same
  rule: height ∝ retained memory).
- **System apparatus.** A's sensor head, B's hub and remote sensors, and C's store now stand at *instrument mounts*
  (`instrumentMount`). A mount is on the bay's outer side, aligned with the instrument's chamber, at the first distance
  that clears every reach hull (by the footprint plus a carried load) and every chamber vessel. A's boom turns to face
  its recorded sensor chamber. The sensing radius stays centred on the chamber.
- **Close-up camera.** It now looks at outboard instruments from the hall side. It no longer stops inside the
  service-housing ring or beyond the walkway: before this fix, the first capture showed only dark walls in 07 and 16.
- **Remote-sensor camera.** Selecting a remote sensor now frames that sensor instead of the hub (P6).

**Tests added or strengthened (all pass).**

- At every recorded carrying step of three records, the carried sample and the closed jaws meet no rim, instrument,
  sensor or store. This test failed before the correction.
- At every recorded step, the closed jaws are centred on the sample within 2 cm and clear its faces by less than 1 cm,
  and the open jaws clear every resting sample.
- The synthetic sweep now carries a load box (from the wall plane up to the nominal height) and the jaws, against the
  rims as well.
- Relocated apparatus meet no chamber vessel, floor column or service housing at sampled steps of three records.
- `focus()` of a remote sensor is that sensor (exercised by scene 17).

**Fidelity.** The self-test checks 80 positions per m9 scene, with a worst error of 5.4×10⁻⁷ m. One defect appeared on
the way: the new merged tool group inherited the carriage label, and the self-test counted it twice (96 checks). It was
relabelled, and the count is back to 80.

**Performance** (1200×866, balanced):

- every scene renders at 59.6–60 fps;
- overview draw calls went from 681 to 713, for two jaw meshes on each of 16 carriages.

**Fidelity limit disclosed, not changed.** In `m9-separated-resources-7000`, the two private carriages of each bay
share tool positions at all 960 steps (4 799 same-bay pair-steps within 0.3 m). In `m7` there are 6 relay hand-overs
where two bays' carriages meet at a port. The model declares that "carriages never collide with anything". The view
draws the recorded positions, so such carriages coincide on screen.

### Change 2: engineered vessel exteriors (P2)

- **Before:** `01-transport-envelope/1200x866@1/09-shared-resource.png`, `03-domain.png`.
- **After:** `02-vessels/1200x866@1/` (scenes 01, 03, 05, 09, 16, 17, 18).

**Correction.** The MuJoCo floor and walls are unchanged in geometry. Additions:

- seven vertical stiffener ribs per side on the outer faces, between the base and the shutter band;
- a base flange (category 4, merged into the global chamber statics);
- the ceramic albedo lowered from 0xd9d9d4 to 0xc6c6c1 (roughness 0.6).

**Inspection.** In 09, the distant vessels now show ribbed exteriors under the shutter band, where the baseline showed
blank white boxes. The near interior walls keep their shading instead of clipping to white. No new intersections:
the ribs are 2–6 cm from the wall face, below the band; the vessel-clearance and envelope tests pass.

**Performance.** Draw calls are unchanged (229 in the domain view, 713 in the overview). Triangles in the domain view
rose from 51k to 63k. Every captured scene renders at 60 fps.

### Change 3: connection contrast and atmospheric depth (P3)

- **Before:** `01-transport-envelope/1200x866@1/02-oblique.png`, `01-overview.png`, `03-domain.png`.
- **After:** `03-connections-depth/1200x866@1/` (scenes 01, 02, 03, 10, 11, 13).

**Correction.**

- **Idle connections.** Drawn at `min(0.30, 0.10 + 0.035 n)`, still ordered by recorded count, instead of
  `min(0.46, 0.17 + 0.05 n)`.
- **Event highlight.** A pair in a recorded event is still drawn at 1.0.
- **No connection removed.** The `pairs` count is unchanged.
- **Fog.** The linear fog (45–95 m), which never reached the hall, was replaced by exponential fog of density 0.012:
  about 3 % at 15 m and 30 % at 50 m. It is a rendering choice with no claim.

**Inspection.** In a side-by-side crop of the oblique view (upper half), the bright-line coverage (grey > 140) fell from
7.0 % to 2.7 % of pixels, and the mean luminance went from 49 to 43. The rails, columns and terminals now carry the
image, and the far bay recedes.

**Trade-off accepted.** Distant chambers are slightly dimmer as well.

**Test added.** A pair in a recorded event is drawn at full brightness and only it; every recorded pair is still drawn;
the idle shade is monotone in the recorded count and below 1.

**Performance.** Draw calls are unchanged, and every captured scene renders at 60 fps.

### Change 4: structural core (P4)

- **Before:** `03-connections-depth/1200x866@1/01-overview.png`, `02-oblique.png`.
- **After:** `04-core/1200x866@1/01-overview.png`, `02-oblique.png`, `13-system-comparison.png`.

**Correction.** The central core is architecture (category 4, no function). It was rebuilt from a featureless prism with
thin rings as structure, merged into one static mesh per material:

- a recessed hexagonal shaft;
- six corner columns;
- three box-section ring girders;
- diagonal bracing on alternate faces, and service panels with vents on the others;
- a service gallery at the walkway level (deck, railing, knee brackets).

**Inspection.** In the overview, the core reads as a braced structure with a gallery instead of a placeholder volume.
Up close (oblique crop), the columns, a brace, the deck and the brackets are legible. The first capture's deck had no
visible support, so knee brackets were added before acceptance.

**Fidelity.** The core is outside every reach hull (radius ≤ 3.3 m, hulls ≥ 11.6 m) and draws no claim.

**Performance.** Overview draw calls are unchanged (713), and the scene renders at 60 fps.

### Change 5: system roles in the apparatus (P5, and the close-up camera)

- **Before:** `01-transport-envelope/1200x866@1/15-hub.png` and `16-memory-store.png`.
- **After:** `05-systems/1200x866@1/15-hub.png` and `16-memory-store.png`, plus 04, 07, 09, 13, 17 and 18.

**System B receiver.** The three stacked rings read as a coil spring. They were replaced with one receiver ring. Its
pickup arms are built by `aimReceiver`, one per *configured* remote sensor, each aimed at that sensor's drawn position.
The arms are rebuilt only when the hub moves with the recorded sensor chamber. They draw no signal or activity.

**System C store.** Every one of the 48 slots is now a recessed bay, which shows capacity. Each recorded memory entry is
a cartridge seated in its bay. The cartridges are lit while the store is readable (recorded shutter) and grey
otherwise. The filled count is still `st.memory`.

**Close-up camera.** In the first capture, 15 showed the hub hidden behind a gantry column and the neighbouring store.
`closeView` now rejects candidate positions whose line of sight to the target crosses solid geometry; the test is a
raycast that ignores lines and transparent overlays. The chosen offset is cached per selection, so the cost is paid
once and not on every frame. After the fix, 15 shows the mast, the ring and three of the four aimed pickups.

**Mount footprint.** The hub's footprint grew, and a test caught it meeting a bay-1 floor column. Instrument mounts now
also clear the floor-standing gantry columns.

**Tests.**
- New: the pickup-arm count equals the configured remote sensors, and each arm points at its sensor within 1°.
- Kept: the relocation, envelope and interpenetration tests pass.

**Inspection.** The store reads as an archive rack in which 7 of the 48 bays are occupied, the recorded count at m7 step
481. The hub reads as a directional receiver.

**Performance.** Every captured scene renders at 60 fps.

### Change 6: scientific event legibility (section IX)

Two event scenes were added to the capture script: `19-delivery-blocked` (the first recorded `delivery_blocked` of m7)
and `20-observation-revision` (the first recorded `sensor_relocated` of the extinction record). Evidence is in
`06-events/1200x866@1/`.

**Correction.** In the first capture, 19 showed only a wall and the shutter band from 1.4 m, and the refused sample in
the vessel was invisible. A selected chamber is now viewed from 2.9 m above its floor. The vessel's contents, the closed
shutter band, the gantry with its jaws open after the release, and the event ring are visible together.

| event | recorded cause | apparatus | shown in 3D | legible from the 3D view alone? |
|---|---|---|---|---|
| material transfer | `sample_grasped`, `leg_complete`, `material_delivered` | gantry, jaws, sample, target chamber | carried sample in closed jaws (05, 18) | **yes** |
| delivery refusal | `delivery_blocked` (containment closed) | target chamber, shutter band | sample inside, shutters closed, event ring (19) | **partly**: refusal versus acceptance needs the panel's transfer state |
| shared-resource interference | `interference` transition (derived from a recorded isolation) | the shared gantry | gantry queue only in the panel (09) | **no**: the 3D view does not show contention |
| observation revision | `sensor_relocated`, `window_changed` | A's sensor head | the head stands at the new chamber's mount; the sensor camera looks from it (20) | **partly**: the move is visible over time, and the panel names it |
| experiment selection | `experiment_selected` | pending-experiment arc between chambers | dashed or solid arc above the chambers | **yes**, in domain views |
| operational extinction | M9-C definition | the system's observed chambers | 0 observed outlines, closed shutters (10) | **yes**, with the panel count |
| re-ignition | first delivery after the extinct interval | as above | delivery and outlines return (11) | **yes** |
| historical reinsertion | `experiment_selected` with basis = memory | C store, selection arc | store cartridges; the arc lies outside the close-up (12) | **partly**: the basis is shown only in the panel |
| variable adoption | `variable_candidate` with `adopted` | — | none: there is no such event in any published record (M9 negative result) | not applicable; nothing is drawn, which is correct |

No decorative animation was added. Indicators remain the recorded event ring, the shutter angle, the jaw state, the
cartridges and the arcs.

### Change 7: live rendering defect, a hidden second renderer (section X)

**Found by the live profile, not by screenshots.** The first final capture showed the live view at 44 fps early and
16 fps late (p99 583 ms). Two steps located the cause:

1. **Bisecting** the M8.2 commits (early window) suggested change 1. Because of the noisy machine, this pointed in the
   wrong direction.
2. **A sampled CPU profile** of an unminified build (`07-live/cpu-profile-before-fix.txt`) showed `TubeGeometry`,
   `generateSegment` and `computeFrenetFrames` in the hot list. The high-fidelity view creates no tubes per frame.

**Cause (present since M8).** Starting a live run in hi-fi mode briefly mounted the *standard* view, because hi-fi
waits for the first frame. The standard view's effect created its own WebGL renderer and render loop. Its
dependencies (`base`, `hifi`) did not change when hi-fi took over, so the loop kept rendering a detached canvas. It
also rebuilt its connection tubes at every step without disposing them, so the cost and the heap grew through the run.

**Fix.**
- The standard view's renderer is never created while hi-fi is on.
- Its per-frame tubes are disposed before rebuilding, which fixes the leak in standard mode too.

**Second finding.** The capture machine had 28 orphaned Chrome for Testing processes, left by interrupted capture runs
(load average 18–22). They were stopped before every measurement below. The load average from other applications
stayed at about 6–7 during the A/B runs.

A/B under the same conditions, run back to back. The values are displayed fps with p99 in ms; heap is JS heap in MB:

| window | M8.1 build (`705288c`) | M8.2 with the fix |
|---|---|---|
| early (t≈122) | 48.2 fps, p99 51, heap 120 | 59.5 fps, p99 17.7, heap 40 |
| t ≥ 400 | 28.8 fps, p99 233, heap 196 | 60.0 fps, p99 17.7, heap 70 |
| t ≥ 800 | 17.9 fps, p99 150, heap 318 | 57.0 fps, p99 34.2, heap 77 |
| apparatus selected during execution | 8.4 fps, p99 1800 | 60.0 fps, p99 17.7 |
| domain view, all overlays | 55.2 fps, p99 34.3 | 60.0 fps, p99 17.7 |

Raw data: `07-live/ab-m8.1-build.json` and `07-live/ab-m8.2-fixed.json`.

**Correction to M8.1.** M8.1 reported 60 fps through step ≈861. That was measured on a lightly loaded machine, which
hid the growing cost of the hidden renderer. It does not hold under moderate load.

**Capture script.** Two windows were added to the live profile:
- a carriage picked through the real pointer path (CDP mouse events), followed in Apparatus mode;
- a domain view with every overlay on.

The script also gained an optional `--cpu-profile` flag.

### Change 8: high-DPI rendering (section XI)

**Measurement before the change** (`08-final/1920x1080@2/`; load average about 7 from other applications):

- At 1920×1080 with DPR 2, *balanced* drew a 2280×1371 buffer (ratio 1.5). The bench showed a displayed p95 of 50 ms
  and a p99 of 783 ms, and the scenes ran at 40–47 fps.
- *High* drew 3040×1828 (ratio 2), with a p99 above 1 s.
- At 1200×866 with DPR 2, balanced (1200×1084 at ratio 1.5) held 60 fps, and high (1600×1446) did not (p99 567 ms).

**Correction.** *Balanced* keeps its 1.5 ratio cap and also gets a drawing-buffer budget of 1.4 Mpx. That is about the
size of the 1920×1080 DPR-1 canvas, which the final DPR-1 capture measured at 54–60 fps. The ratio never goes below 1,
so DPR-1 displays and small canvases are unchanged; `quality.test.ts` checks this. *High* is unchanged: the full ratio
up to 2.

**After** (`09-dpr-budget/`). Balanced at 1920×1080 with DPR 2 now draws 1525×917. The load average reached 13–14
because of Spotlight indexing and other applications; this was not controllable, and the numbers were repeated twice.

| scene | before | after |
|---|---|---|
| overview | 39.7 fps | 50.9–55.6 fps |
| transport | 42.1 fps | 57.2–58.8 fps |
| memory store | 47.4 fps | 59.5–60 fps |

**Limits kept and documented.**
- High at DPR 2 does not sustain 60 fps on this Apple M1 at either size.
- Under heavy background load, the full-hall overview at 1920×1080 runs at 51–56 fps.

## 5. Final evaluation (after M8.2)

Images: `08-final/1200x866@1/`, `08-final/1920x1080@1/` and `08-final/1200x866@2/`. The 1920×1080 DPR-2 values are
superseded by `09-dpr-budget/`. Every final image listed here was opened and inspected. The scores stay conservative
and use the same scale as §2.

| scene | A | B | C | D | E | F | G | H | I | J | before J |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 overview | 48 | 56 | 50 | 75 | 58 | 42 | 55 | 62 | 88 | 55 | 48 |
| 02 oblique | 50 | 52 | 40 | 72 | 60 | 35 | 52 | 48 | 88 | 48 | 40 |
| 03 domain | 58 | 52 | 58 | 78 | 60 | 45 | 56 | 60 | 88 | 57 | 50 |
| 05 transport | 55 | 35 | 62 | 78 | 45 | 32 | 52 | 58 | 88 | 55 | 40 |
| 06 / 18 grasp, gantry close-up | 55 | 35 | 60 | 78 | 45 | 38 | 52 | 55 | 88 | 53 | 38 |
| 07 system A sensor | 55 | 40 | 52 | 78 | 42 | 58 | 52 | 52 | 88 | 52 | 50 |
| 15 system B receiver | 55 | 45 | 55 | 75 | 40 | 65 | 50 | 55 | 88 | 55 | 42 |
| 17 system B remote sensor | 45 | 40 | 50 | 75 | 45 | 55 | 52 | 55 | 88 | 50 | — |
| 16 system C store | 50 | 40 | 65 | 75 | 45 | 65 | 50 | 52 | 88 | 55 | 40 |
| 08 observation restricted | 48 | 45 | 55 | 75 | 55 | 40 | 55 | 58 | 88 | 53 | 50 |
| 09 shared resource | 50 | 38 | 35 | 75 | 48 | 32 | 55 | 52 | 85 | 48 | 38 |
| 10 extinction | 50 | 50 | 52 | 78 | 58 | 40 | 55 | 60 | 88 | 55 | 50 |
| 11 re-ignition | 50 | 50 | 50 | 78 | 58 | 40 | 55 | 60 | 88 | 54 | 48 |
| 19 delivery refusal | 50 | 40 | 55 | 78 | 50 | 35 | 55 | 60 | 88 | 52 | — |
| 20 observation revision | 50 | 42 | 50 | 75 | 55 | 45 | 55 | 55 | 88 | 50 | — |
| 14 live operation | 48 | 56 | 45 | 75 | 58 | 42 | 55 | 58 | 88 | 53 | 45 |

### Evidence for the changes

**D, structural coherence (+10 to +23).**
- The largest gains are in transport and the gantry, and they rest on tests, not on appearance.
- No drawn part stands where a recorded carried sample passes, at any recorded step.
- The jaws close on the recorded sample.
- Instruments stand outside every reach envelope, chamber vessel and floor column.

**I, scientific fidelity (85–88).**
- The jaws now agree with the recorded grasp, and the remote-sensor camera frames the right object.
- It is not higher because two carriages that the model lets overlap are drawn as one, and some event consequences
  (refusal versus acceptance, the basis of a selection) still need the panel.

**A and E, mechanism and density (+5 to +20).** The gripper, vessel stiffeners and the structural core add visible
mechanism with a stated role. The sensor close-up (07) lost some density because the instruments now stand on the
bays' outer sides, against a dark hall.

**F, distinctiveness (+5 to +15).** B's pickups point at its own remote sensors, and C's rack shows capacity against
recorded entries. A, B and C remain differences of apparatus only; they share one decision rule.

**B, originality (modest).** The installation remains function-led and austere. Nothing was added for silhouette.

**C, legibility.**
- Shared-resource interference (09) is still not visible in 3D: the score did not move.
- The oblique view is less dominated by lines, but it is still busy.

**J, overall (+2 to +17).** The laboratory reads more as a coherent unmanned installation. It is not yet "sophisticated"
in the sense of the design brief: surfaces are untextured, and several views are sparse or dark.

## 6. Changes accepted, rejected or revised

**Accepted:** changes 1–8 above. Every one of them was revised at least once on the evidence of a screenshot or a test
before acceptance:
- the label that made the self-test count carriages twice;
- the close-up camera inside the housing ring;
- the occluded hub;
- the floating gallery deck;
- the low chamber camera;
- the balanced pixel budget, first 1.8 Mpx and then 1.4 Mpx.

**Rejected:**
- *Lowering the louvre crown to clear the nominal travel height.* Recorded worn-gantry sag put loads 7.6 cm above the
  walls, so any crown on the walls is crossed. The crown was redesigned into a band below the wall top.
- *Separating co-located private carriages on screen.* That would draw positions that were not recorded.
- *Added texture or emissive accents.* They were not justified by any defect.

## 7. Remaining limitations

- **Machine.** Measurements come from one machine (Apple M1, 8 GB, headless Chrome for Testing with GPU) under a
  background load average of 4–15 (Spotlight, other applications). They vary from run to run; the variation is
  reported with each measurement.
- **High at DPR 2.** It misses 60 fps.
- **1920×1080 at DPR 1.** The full-hall overview runs at 51–56 fps under heavy load.
- **Memory in long live runs.** In the final live capture the JS heap rose from 339 MB to 458 MB over steps 122–960. In
  the A/B run on a fresh page it rose from 40 MB to 77 MB. The live record retains every step by design. This
  measurement does not separate record growth from any remaining leak.
- **Carriage overlaps.** Two carriages that the physics model lets overlap (private carriages, relay hand-overs) are
  drawn as one.
- **Shared-resource interference.** It is not visible in the 3D view.
- **Instrument close-ups.** These are composed against the dark outer hall.
- **Surfaces.** They are untextured.
- **Envelope sweep.** It covers the commandable placement envelope, not the slide joints' travel to their limits.
- **Browser pane.** The visible in-app browser pane was not used; all rendering was headless with the GPU.

## 8. Regression

These checks were run on the final code:

* **Backend.** pytest: 340 passed. ruff: clean. mypy: no issues in 105 files.
* **Research.** `research/post_active_inference` tests: 59 passed.
* **Frontend.** vitest: 76 passed, up from 68 in M8.1. ESLint, tsc and the production build all exit 0.
* **Replays.** `xzr.lab.replay` gives full agreement, with 0 mismatched steps and identical events, for:
  * `m2-run-9100` (240 steps);
  * `m3-physical-9100` (240 steps);
  * `m7-systems-6000` (960 steps);
  * `m9-extinction-relocation-7000` (960 steps);
  * `m9-separated-resources-7000` (960 steps).
* **Frozen files.** `git diff 705288c HEAD` outside `frontend/` and `docs/` is empty. Since the M8 commit `77c9a38`,
  no file has changed under `backend/experiments`, the research configs, `docs/publication` or
  `docs/LAB_PROTOCOL_M9.md`.
* **Research DOCX.** sha256 `f00dc9db01f51310…`, unchanged.
* **Rendering cannot change outcomes.** The runtime runs headless in its own thread, and the replays above agree. Every
  M8.2 change is in `frontend/`; the rest are capture scripts and documents.

The level statuses are unchanged:

- **Level 1:** achieved.
- **Level 2:** partially demonstrated, not achieved under the frozen criteria (the transfer-latency verification
  discrepancy).
- **Level 3:** not achieved.

The negative M9 results stand: physical-resource mediation, observation revision, variable generation, and historical
reinsertion. No claim of strong Xenoscience is made.

## 9. Reproduction

Start the local service:

```bash
.venv/bin/uvicorn xzr.service.app:app --app-dir backend --host 127.0.0.1 --port 3011
```

Build the frontend:

```bash
npm --prefix frontend run build
```

Run the final captures:

```bash
node frontend/scripts/m8-capture.mjs --out docs/m8.2 --stage 08-final --res 1200x866 --bench --live-windows 400,800
```

```bash
node frontend/scripts/m8-capture.mjs --out docs/m8.2 --stage 08-final --res 1920x1080 --bench --no-live
```

```bash
node frontend/scripts/m8-capture.mjs --out docs/m8.2 --stage 08-final --res 1200x866 --dpr 2 --scenes 01,02,05,07,15,16 --bench --no-live
```

```bash
node frontend/scripts/m8-capture.mjs --out docs/m8.2 --stage 09-dpr-budget --res 1920x1080 --dpr 2 --scenes 01,05,16 --bench --no-live
```

Record a sampled CPU profile of the live view:

```bash
node frontend/scripts/m8-capture.mjs --out docs/m8.2 --stage live-profile --scenes none --cpu-profile
```

**Before measuring:**

- Make sure no orphaned Chrome for Testing processes remain from interrupted runs:
  `pkill -f "Google Chrome for Testing"`.
- Record the load average.
- In zsh, a loop variable holding several flags must be split with `${=args}`.
