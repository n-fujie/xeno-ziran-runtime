### Final series (the verdict of this section)

The first series (below) was noisy. A second series was run on the final tree, with its design fixed before any of its data were seen: **12 interleaved pairs** (Stage 5 build on port 3034, Stage 6 build on port 3031, the order alternating each repetition), balanced tier, 150 frames, 1672 x 808, the six conditions, each run started only when the 1-minute load average was below 3 (it waited at most 10 minutes and then ran anyway; the load at the start of every run is in `perf_stage6/paired_final/*.load`: 2.49-5.07, one run at 5.07). The rule is the one fixed for Stages 4 and 5 (CI lower bound above 1.05: regression; upper bound below 1.05: no meaningful regression; otherwise inconclusive); no repetition was excluded. (A first attempt at this series produced no data: the server's session limit answered 429 and the page never became ready; the limit was raised as in all earlier series and the series was run again; nothing from the failed attempt exists.)

| all 48 measures | regression | no meaningful regression | inconclusive |
|---|---|---|---|
| Stage 6 against Stage 5, 12 pairs | 0 | 10 | 38 |
| **A/A control**: the Stage 5 build on two ports, 12 pairs, three conditions (24 measures) | 0 | 8 | 16 |

Medians of the frame time (ms), Stage 5 against Stage 6:

| condition | mode | Stage 5 | Stage 6 | paired ratio | 95 % CI | verdict |
|---|---|---|---|---|---|---|
| habitat | static | 16.35 | 16.65 | 1.003 | [0.985, 1.101] | inconclusive |
| habitat | orbit | 17.2 | 17.15 | 1.014 | [0.971, 1.136] | inconclusive |
| habitat+repair | static | 14.25 | 14.05 | 1.004 | [0.959, 1.062] | inconclusive |
| habitat+repair | orbit | 15.45 | 14.75 | 0.977 | [0.883, 1.021] | no meaningful regression |
| habitat+repairtech | static | 14.2 | 13.8 | 0.979 | [0.925, 1.007] | no meaningful regression |
| habitat+repairtech | orbit | 15.1 | 14.7 | 0.997 | [0.948, 1.034] | no meaningful regression |
| habitat+research | static | 14.2 | 13.95 | 0.979 | [0.969, 1.01] | no meaningful regression |
| habitat+research | orbit | 14.6 | 14.5 | 0.98 | [0.97, 1.014] | no meaningful regression |
| habitat+technical | static | 14.35 | 14.5 | 1.004 | [0.99, 1.028] | no meaningful regression |
| habitat+technical | orbit | 14.9 | 15.25 | 1.027 | [0.948, 1.061] | inconclusive |
| overview | static | 12.5 | 12.4 | 1.003 | [0.961, 1.052] | inconclusive |
| overview | orbit | 15.65 | 15.7 | 1.003 | [0.978, 1.142] | inconclusive |

**Statistic.** For every measure (median, p95, p99, max of the 150 frame times of one run) the ratio Stage 6 / Stage 5 is formed **per repetition** (12 ratios); the estimate is their median and the 95 % interval is a bootstrap of that median over the 12 repetitions (10 000 resamples, fixed seed). The frames of a run are not resampled and are not treated as independent repetitions; the unit is the paired repetition.

**What the A/A control shows.** Two ports serving the *same* build, measured the same way, give 16 inconclusive and 8 no-meaningful-regression verdicts out of 24; the width of the 95 % interval of a tail measure (p95, p99, max) is 0.13-0.56 (median 0.34) in the A/A and 0.07-0.73 (median 0.27) in the Stage 6 against Stage 5 series; the widest A/A interval is habitat+research orbit max: ratio 0.919 [0.617, 1.179] between identical builds. This limits what the measurement can decide: with 12 pairs on this machine a tail measure cannot be separated from a 5 % effect even for identical builds, so a 5 % non-regression of the tails **cannot be confirmed here**. It does not show that the differences between Stage 5 and Stage 6 are noise, and it does not show that no regression exists. As a rough scale (the interval narrows with the square root of the number of pairs) bringing a tail interval within 5 % would take several times as many pairs, perhaps ten times; this was not run.

**Verdict, Stage 6 against Stage 5.** No performance regression meeting the pre-set criterion was detected in any of the 48 measures of the final series; for 10 measures a 5 % or larger degradation is excluded by that criterion, and 38 measures are inconclusive (the A/A control shows a comparable uncertainty for the tail measures under these conditions, so a 5 % non-regression cannot be confirmed for them). The first series flagged habitat static p99 once (ratio 1.284 [1.126, 1.727]); in the final series that measure is 1.163 [0.946, 1.526], inconclusive. The overall verdict is **INCONCLUSIVE**; it is not NO_MEANINGFUL_REGRESSION and is not changed by the above. What the data and the render counters support: 6 of the 12 frame-time medians are shown not to be a 5 % regression and the others are inconclusive; the counters that decide the render cost (draw calls, triangles, geometry uploads, programs built, LOD switches, visibility flips) are identical or within the table below. A cost of the repair view of the order of 10-20 % at the tail is **not excluded**.

<!-- first Stage 6 series (kept) -->





#### The first Stage 6 series

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

**Verdict of the first series (the final series above states the verdict of this section): no performance regression meeting the criterion was detected, and for most measures the data cannot decide.** In the extended and the low-load analyses no measure is a regression; in the planned analysis one tail measure was (above). Most intervals are wide (the benchmark was run on a shared machine): the cost of the repair view, the recovery map and the repair figure cannot be separated from the variation of the measurement at this sample size, so a cost of a few percent to
tens of percent is **not excluded** for the repair and technical conditions. The stage itself is unchanged: draw calls, triangles, geometry uploads, programs built (0 during an orbit), LOD switches and visibility flips are the same in the two builds, except 136 more triangles in the two conditions that open a repaired run (the run's state differs from the unrepaired one; the cause is not investigated). The update cost of the repair overlay itself is not measured separately.
