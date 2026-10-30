**Method.** The Stage 5 build (`1d1e331`, port 3034) and the Stage 6 build (this tree, port 3031) were measured **interleaved in time**, the order alternating each repetition, balanced tier, 150 frames, 1672 x 808, headless Chromium on the GPU, the preview browser pane closed, nothing built during a run. Conditions: habitat and overview (static, orbit), and with the UI open:
the RESEARCH tab (`+research`), the technical sheet (`+technical`), the RESEARCH tab with a **repaired run, the repair panel and the recovery map** (`+repair`), the technical sheet with the **repair figure and the repair layers** (`+repairtech`). A build without the repair view ignores the repair parameters, so for Stage 5 the same URLs measure the research tab / technical sheet without a repair; the difference is the cost of what Stage 6 adds.
Same rule as for Stages 4 and 5, fixed before any of this data: paired ratio per repetition, 95 % bootstrap interval (10 000 resamples, fixed seed); *regression* if the lower bound exceeds 1.05, *no meaningful regression* if the upper bound is below 1.05, otherwise *inconclusive*. Mean FPS is not used.

**The machine was not idle.** The load average at the start of each run is in `perf_stage6/paired/*.load`; three of the 18 runs began at a load of 9-16 (3031_4: 10.86, 3031_7: 9.98, 3034_1: 8.98, 3034_3: 16.42); the others at 3.4-7.3.

| analysis | repetitions | all 48 measures (6 conditions x static/orbit x median/p95/p99/max) |
|---|---|---|
| **planned** (repetitions 1-6, fixed in advance) | 6 | 1 regression, 0 no meaningful regression, 47 inconclusive |
| **extended** (three more repetitions, 7-9, added because the planned ones were noisy) | 9 | 0 regression, 3 no meaningful regression, 45 inconclusive |
| sensitivity: without the repetitions that contain a high-load run (1, 3, 4) | 6 | 0 regression, 8 no meaningful regression, 40 inconclusive |

**The one flag of the planned analysis is kept:** habitat static p99: 27.05 ms -> 41.65 ms, ratio 1.284 [1.126, 1.727]. It is a 99th-percentile of 150 frames in the plain habitat condition, where the render counters of the two builds are identical (below) and no Stage 6 UI is open; it did **not** reappear with three more repetitions or without the high-load runs. It is reported, not removed, and not explained.

Median and p95, extended analysis (9 repetitions); all measures are in `docs/ecosystem/perf_stage6/paired/analysis_tables.md`:

| condition | mode | measure | Stage 5 (ms) | Stage 6 (ms) | paired ratio S6/S5 | 95 % CI | verdict |
|---|---|---|---|---|---|---|---|
| habitat | static | median | 18.5 | 19.1 | 1.038 | [0.935, 1.108] | inconclusive |
| habitat | static | p95 | 23.8 | 25.4 | 1.043 | [0.921, 1.324] | inconclusive |
| habitat | orbit | median | 20 | 20.1 | 0.98 | [0.911, 1.052] | inconclusive |
| habitat | orbit | p95 | 29.8 | 30.4 | 0.973 | [0.884, 1.289] | inconclusive |
| habitat+repair | static | median | 16.6 | 16.3 | 0.975 | [0.791, 1.11] | inconclusive |
| habitat+repair | static | p95 | 24.2 | 20 | 0.952 | [0.723, 1.049] | no meaningful regression |
| habitat+repair | orbit | median | 16.1 | 16.6 | 1.026 | [0.808, 1.16] | inconclusive |
| habitat+repair | orbit | p95 | 22.5 | 25.7 | 1.058 | [0.899, 1.206] | inconclusive |
| habitat+repairtech | static | median | 16.4 | 16.4 | 0.994 | [0.777, 1.031] | no meaningful regression |
| habitat+repairtech | static | p95 | 25.1 | 21.6 | 0.869 | [0.689, 1.296] | inconclusive |
| habitat+repairtech | orbit | median | 15.8 | 16.2 | 1.013 | [0.778, 1.071] | inconclusive |
| habitat+repairtech | orbit | p95 | 23 | 24.3 | 1.046 | [0.652, 1.238] | inconclusive |
| habitat+research | static | median | 16.5 | 16.4 | 0.958 | [0.873, 1.044] | no meaningful regression |
| habitat+research | static | p95 | 22.3 | 18.7 | 0.889 | [0.751, 1.291] | inconclusive |
| habitat+research | orbit | median | 16.3 | 16.4 | 1.0 | [0.871, 1.059] | inconclusive |
| habitat+research | orbit | p95 | 25 | 24.2 | 1.07 | [0.745, 1.114] | inconclusive |
| habitat+technical | static | median | 16.5 | 16.5 | 1.0 | [0.811, 1.531] | inconclusive |
| habitat+technical | static | p95 | 19.7 | 20.4 | 0.995 | [0.638, 1.855] | inconclusive |
| habitat+technical | orbit | median | 16.4 | 16.9 | 0.982 | [0.84, 1.306] | inconclusive |
| habitat+technical | orbit | p95 | 25.6 | 25.5 | 0.926 | [0.789, 1.505] | inconclusive |
| overview | static | median | 15.9 | 15.9 | 0.962 | [0.878, 1.118] | inconclusive |
| overview | static | p95 | 21.5 | 18.2 | 0.805 | [0.558, 1.364] | inconclusive |
| overview | orbit | median | 17.9 | 17.6 | 0.983 | [0.9, 1.067] | inconclusive |
| overview | orbit | p95 | 26.8 | 27 | 1.012 | [0.887, 1.474] | inconclusive |

Render counters (median over the repetitions; geometry uploads, programs built, LOD switches and visibility flips are from the orbit's per-frame series):

| condition | build | draw calls | triangles | geometry uploads | programs built | LOD switches | visibility flips |
|---|---|---|---|---|---|---|---|
| habitat | stage5 | 428 | 1065364 | 35 | 0 | 144 | 28 |
| habitat | stage6 | 428 | 1065364 | 35 | 0 | 142 | 28 |
| overview | stage5 | 457 | 674384 | 21 | 0 | 145 | 64 |
| overview | stage6 | 457 | 674384 | 21 | 0 | 145 | 64 |
| habitat+research | stage5 | 385 | 989152 | 38 | 0 | 144 | 28 |
| habitat+research | stage6 | 385 | 989152 | 38 | 0 | 141 | 28 |
| habitat+technical | stage5 | 385 | 989152 | 38 | 0 | 143 | 28 |
| habitat+technical | stage6 | 385 | 989152 | 38 | 0 | 141 | 28 |
| habitat+repair | stage5 | 385 | 989152 | 38 | 0 | 144 | 28 |
| habitat+repair | stage6 | 385 | 989288 | 38 | 0 | 144 | 28 |
| habitat+repairtech | stage5 | 385 | 989152 | 38 | 0 | 142 | 28 |
| habitat+repairtech | stage6 | 385 | 989288 | 38 | 0 | 143 | 28 |

**Verdict, Stage 6 against Stage 5: no regression is established, and for most measures the data cannot say.** In the extended and the low-load analyses no measure is a regression; in the planned analysis one tail measure was (above). Most intervals are wide (the benchmark was run on a shared machine): the cost of the repair view, the recovery map and the repair figure cannot be separated from noise at this sample size, so a cost of a few percent to
tens of percent is **not excluded** for the repair and technical conditions. The stage itself is unchanged: draw calls, triangles, geometry uploads, programs built (0 during an orbit), LOD switches and visibility flips are the same in the two builds, except 136 more triangles in the two conditions that open a repaired run (the run's state differs from the unrepaired one; the cause is not investigated). The update cost of the repair overlay itself is not measured separately.
