# M8 browser verification and performance

Produced by `frontend/scripts/m8-capture.mjs` against the local service (`uvicorn xzr.service.app:app --app-dir backend
--port 3011`), in **Chrome/151.0.7922.34** (headless, GPU: `ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)`), viewport 1600×1000 at device scale 1, on
an Apple M1 with 8 GB. Raw results are in `browser-verification.json` and the screenshots are in `screenshots/`. All
scenes are published records or a live run; nothing is mocked.

## Rendered scene against record (in-page self-test)

For every scene the page's own scene graph was read after rendering. Every carriage and tool and every material
sample was compared with the transform of its recorded MuJoCo position at the displayed step (`coords.ts`). The worst
error is float32 rounding of instance matrices.

| scene | what it shows | executable objects checked | worst position error (m) | rAF fps | rAF p95 (ms) | draw calls |
|---|---|---|---|---|---|---|
| 01-overview | full installation, M9-A separated-resources record | 80 | 5.1e-07 | 60 | 18.6 | 828 |
| 02-dense-domain | one research domain: chambers, gantry, ports, sensors | 80 | 5.1e-07 | 60 | 18.7 | 406 |
| 03-physical-transfer | sample 0.2#a carried (recorded) at index 121 | 80 | 5.1e-07 | 60 | 18.6 | 428 |
| 04-shared-resource | shared bay-0 gantry in the M7 shared laboratory (mediation panel) | 40 | 5.1e-07 | 60 | 18.6 | 424 |
| 05-sensor-relocation | recorded sensor relocation 0.0 → 0.3 at t16 | 40 | 5.1e-07 | 60 | 18.6 | 212 |
| 06-observation-restricted | A's observed chambers closed by the declared harness at t320 | 40 | 5.1e-07 | 60 | 18.6 | 353 |
| 07-extinction | inside the extinct interval (M9-C definition) | 40 | 5.1e-07 | 60 | 16.8 | 358 |
| 08-reignition | first delivery after the extinct interval, t690 | 40 | 5.1e-07 | 60 | 16.8 | 373 |
| 09-layer-A-only | physical layer alone (MuJoCo-driven) | 80 | 5.1e-07 | 60 | 16.8 | 226 |
| 10-high-quality | high-fidelity quality mode | 80 | 5.1e-07 | 55.1 | 16.8 | 406 |
| 11-live-run | live run started from the viewer (preset systems), streamed while it runs | 40 | 5.1e-07 | 46.8 | 50 | 756 |

The live scene was started from the viewer (preset `systems`) and streamed while it ran. It was then stopped, and its
record was compared with a headless batch run of the same configuration that had no viewer attached:

* runtime and physics fingerprints are identical at **137 of 137 steps**;
* the science events are identical;
* the live record replays with full agreement.

The high-fidelity viewer does not influence the run.

## Render cost by quality level

GPU-synchronised frame cost for each quality level: apply the recorded state, render, then `gl.finish`. The replay
advanced two steps per frame with interpolation, overview camera, 480 frames after 30 warm-up frames. rAF fps is the
displayed frame rate, which the display's 60 Hz caps. The headless browser runs at device scale 1, so "high" ran at
pixel ratio 1 here; on a Retina display it uses pixel ratio 2.

| quality | canvas @ratio | mean ms | p50 ms | p95 ms | max ms | rAF fps | draw calls | triangles | JS heap MB | geometries before→after |
|---|---|---|---|---|---|---|---|---|---|---|
| performance | 1200×866 @1 | 4.98 | 4.5 | 8.8 | 35.3 | 60 | 686 | 121k | 337.8 | 646→694 |
| balanced | 1200×866 @1 | 10.02 | 9.9 | 15.5 | 26.8 | 59.7 | 857 | 160k | 271.7 | 817→865 |
| high | 1200×866 @1 | 13.5 | 13 | 19.4 | 34.8 | 59.7 | 857 | 160k | 329.6 | 829→877 |

How the numbers were brought down, both changes measured in the in-app browser:

* **A geometry leak.** Observation outlines and pending-experiment curves were rebuilt every frame. Fixing it took the
  balanced frame from 16.1 to 10.4 ms mean and from 25.1 to 14.5 ms p95.
* **Draw calls.** Merging static meshes by material and instancing samples and small parts cut them from 1,382 to
  roughly 400–860 depending on the view.

The runtime itself is not affected by rendering: it steps in its own thread, and a run streamed to the viewer equals
the headless run.

## Visual defects found in screenshots and fixed

1. **Decorative arches.** Runtime connections drawn as bright arches up to 8 m dominated the scene. They are now thin
   dark cables on a level above the gantry rails, bright only when a recorded event touches them.
2. **Roof cables.** Decorative roof cables were too bright; they are dimmed.
3. **Roof occlusion.** The roof structure occluded the overview from above. It is now cut away while the camera is
   above it; it is layer C only, and the legend says so.
4. **Rails through housings.** Gantry rails, columns and full-span braces passed through chamber housings, because the
   work envelope's margin was taken from chamber centres. The envelope now clears housings and ports, braces are short
   knee braces, and a test checks it.
5. **Sensor in the tool's path.** The local system's sensor pod stood where the carriage moves. It is now a corner post
   outside the sample spots.
6. **Wall height.** Chamber walls were drawn 5 cm too high. They now match the MuJoCo geom (physics z from 0 to 0.7),
   with a test.
7. **Louvre axis.** Louvre blades on two sides rotated about the wrong axis.
8. **Rail occlusion.** The apparatus camera sat above the rails and was occluded. It is now below rail height.
9. **Lighting.** The scene was underlit; exposure and hemisphere light were raised.

## Limits

* **Headless rendering.** Screenshots and frame rates come from headless Chromium on this machine. A visible window on
  a Retina display renders more pixels at the balanced and high levels.
* **Representations, not modelled parts.** Rails, bridges, masts, louvres, cables and architecture are representations
  (categories 3 and 4). MuJoCo models slide joints, weld grasps, floors, walls, ports and samples; it does not model
  rails or louvres.
* **Sample orientation.** Samples are drawn axis-aligned, because the records keep positions only.
* **Not a scientific result.** M8 improves inspection. It changes no scientific result and no achievement level:
  Level 1 is reached, Level 2 is not achieved under its frozen criteria, and Level 3 is not addressed by simulation.
