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
