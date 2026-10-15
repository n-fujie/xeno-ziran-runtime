# High-fidelity laboratory view (M8)

The view draws a recorded or streamed laboratory run (schemas `xzr.labrun/1–3`) and nothing else. Open it with the
**High fidelity (M8)** toggle in the 3D Laboratory view, or with `?view=laboratory&hifi=1`.

## Files

| file | role |
|---|---|
| `coords.ts` | The MuJoCo → Three.js transform: `view = (x, z + 0.25, y)`, no scaling. It also has the inverse, rendering-only interpolation, model constants, and the limits of the mapping. |
| `model.ts` | Pure, no Three.js. Defines layers and categories, event ids, transfer states, the five levels (exists / observed / accessible / selected / executed), physical-resource mediation, recorded and derived transitions, provenance, and inspection fields with availability statuses. |
| `assemblies.ts` | Geometry library: chamber, gantry, port, samples, system sensors and stores, runtime connections, and the installation. Its `buildLab` makes the whole laboratory for one record and quality level. |
| `HiFiLab.tsx` | The React view: renderer, camera modes, panels, quality modes, self-test, frame-time reporting. |
| `fixtures/access-*.json` | The backend's own `science.candidates()` at every decision step of the published M9 records, written by `backend/scripts/m8_access_fixture.py`. |

## Layers and categories

Every object carries a layer and a category in `userData`:

| layer | content | categories |
|---|---|---|
| A physical | MuJoCo chamber floors and walls, ports and samples, all at recorded positions; carriages and tools at the recorded tool tip; rails, bridge and mast representing the x / y / z slide joints; the routing ring | 1 executable; 3 representation of a joint or of the routing |
| B scientific | containment louvres (closure = 1 − mean gate of entering connections), activity and memory instruments, sensors / hub / remote sensors / memory store, runtime connections, pending experiments, observed chambers | 2 runtime instrument; 3 representation of a recorded dependency |
| C architecture | platforms, trenches, housings, columns, roof (cut away while the camera is above it), walls, walkway, luminaires | 4, no scientific claim |

## Rules the view keeps

- **Positions.** A rendered position is the transform of the recorded MuJoCo position. Interpolation between recorded
  frames happens only while a replay plays, and affects rendering only.
- **Delivery.** "Delivered" requires a recorded `material_delivered` event. A transfer whose sample reached the chamber
  but was refused is shown as "delivery blocked": physical transport completion is not delivery.
- **No invented values.** Unrecorded quantities show an availability status (unmeasured, measurement unavailable,
  outside observation range, operationally absent, unknown, derived), never a zero.
- **Derived quantities state their rule.** "Experimentally accessible" is `science.py candidates()` applied to recorded
  state; a test checks it against the backend at every decision step. Ignition is "became accessible since the
  previous decision step". Extinction and re-ignition use the M9-C definitions.
- **Provenance uses recorded links only.** These are recorded causes, transfer ids, and system and experiment matches.
  When no link is recorded the view says "unresolved", and never infers attribution from proximity in time.
- **Heterogeneity.** The three systems share one decision rule, so their heterogeneity is configuration-dependent (M4).
  The view says so and draws no difference in method.

## Camera modes

| mode | what it shows |
|---|---|
| Overview | the whole installation |
| Domain | one bay |
| Apparatus | the selected object |
| Operation | follows the system's carried sample, or else its pending target |
| Transfer | follows the selected or carried sample |
| Sensor | from the system's sensor head toward its observed chambers |
| Free | orbit, pan and zoom |

## URL parameters (reproducible scenes)

| parameter | value |
|---|---|
| `rec` | record name |
| `step` | step index |
| `cam` | camera mode |
| `domain` | bay |
| `sel` | `kind:id`, e.g. `gantry:0` or `sample:0.1#a` |
| `sys` | system |
| `layers` | e.g. `AB` |
| `quality` | `performance`, `balanced` or `high` |
| `ev` | selected event id |
| `campos`, `target` | free-camera position and target, `x,y,z` |

## Tests

- `model.test.ts`: coordinates; accessibility equals the backend; blocked deliveries are never shown as delivered;
  event ids and transitions; agreement with the published M9-C run; provenance; availability statuses; live-grown
  versus replayed records.
- `assemblies.test.ts`: rendered positions; MuJoCo geom sizes; layer and category tags; quality-level independence; no
  gantry column or rail passes through a chamber housing; connection terminals clear every gantry part; system apparatus
  never interpenetrate; a failed gantry darkens only its own carriage; recorded tool tips lie inside the drawn
  envelope; recorded carriage and mast positions miss every static instrument; a synthetic sweep of each bay's
  reachable envelope (`reachHull`) at travel height hits nothing, and no static part inside it rises above
  `TRAVEL_TOP`.
- **Browser test** (`frontend/scripts/m8-capture.mjs`): runs in a real Chromium against the running service. For each
  scene it runs the in-page self-test of the rendered scene graph (`window.__labHiFi.selfTest()`), measures frame times
  and saves a screenshot with full metadata, benchmarks every quality level (`--bench`) and profiles the live view over a
  run's lifetime (`--live-windows 400,800`). Options: `--stage`, `--res WxH` (browser viewport; the canvas is smaller),
  `--dpr`, `--scenes all|01,05`, `--no-live`. Results are in `docs/m8/` (M8) and `docs/m8.1/<stage>/` (M8.1).
- `window.__labHiFi.prof` holds panel / apply / render / frame timings for profiling.
