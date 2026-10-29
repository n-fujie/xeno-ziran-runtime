**Method.** Stage 3 (`93119a0`, port 3032), Stage 4 (`f61243a`, port 3033) and Stage 5 (this tree, port 3031) were measured **interleaved in time**: 6 repetitions, each repetition running the three builds once, the order rotating over a Latin square so that no build is always first or last.
Balanced tier, 150 frames, 1672 x 808 viewport, headless Chromium on the GPU (ANGLE/Metal). Conditions: habitat (static, orbit), overview (static, orbit), body close-up (static, orbit), and, for Stage 4 and Stage 5 only (Stage 3 has no research UI), the habitat stage with **the Research tab open** (`habitat+research`, with an observation setting on) and with **the Technical View open** (`habitat+technical`, research map, route layers and route topology on the sheet).
The benchmark page was the only browser; the preview browser pane was closed; nothing was built during the measurement (a first attempt in which a type-check ran during the first run was discarded and restarted).
Per condition: median, p95, p99, max of the frame time, and draw calls, triangles, geometry uploads, shader programs built, LOD switches and visibility flips (the last four from the orbit's per-frame series, which Stage 3 does not have).

**Machine state, not hidden.** The machine was not idle (other applications were running). Load average at the start of each run is in `docs/ecosystem/perf_stage5/paired/*.load`: 16 of 18 runs began at a 1-minute load of 3.1-6.8; **2 runs (3031_1, 3033_1, two of the three runs of repetition 1) began at a load of 16-18**. All six repetitions are in the primary analysis; the same analysis without repetition 1 is given as a **sensitivity analysis**, never as a replacement.

**Rule (the one fixed for the Stage 4 acceptance, before any of this data existed).** Per repetition the ratio of the two builds is formed (paired); its 95 % bootstrap interval (10 000 resamples over the repetitions, fixed seed) is computed. *Regression* if the lower bound exceeds 1.05; *no meaningful regression* if the upper bound is below 1.05; otherwise *inconclusive*. Mean FPS is not used.

### Stage 5 against Stage 4 (the Stage 5 changes: route/MFS layers, panels, deep links)

All 40 measures (5 conditions x static/orbit x median/p95/p99/max): primary analysis **0 regression, 12 no meaningful regression, 28 inconclusive**; without repetition 1: 0 regression, 11 no meaningful regression, 29 inconclusive.
Median and p95 (all measures in `docs/ecosystem/perf_stage5/paired/analysis_tables.md`):

| camera | mode | measure | Stage 4 (ms) | Stage 5 (ms) | paired ratio S5/S4 | 95 % CI | verdict |
|---|---|---|---|---|---|---|---|
| body | static | median | 16.65 | 16.5 | 0.988 | [0.914, 1.009] | no meaningful regression |
| body | static | p95 | 25.7 | 20.6 | 0.851 | [0.688, 1.047] | no meaningful regression |
| body | orbit | median | 17.1 | 17.35 | 0.988 | [0.882, 1.113] | inconclusive |
| body | orbit | p95 | 24.4 | 27.0 | 0.987 | [0.812, 1.296] | inconclusive |
| habitat | static | median | 17.95 | 17.8 | 0.961 | [0.878, 1.023] | no meaningful regression |
| habitat | static | p95 | 22.75 | 22.2 | 1.002 | [0.751, 1.028] | no meaningful regression |
| habitat | orbit | median | 19.85 | 20.15 | 1.026 | [0.893, 1.158] | inconclusive |
| habitat | orbit | p95 | 26.35 | 36.3 | 1.136 | [0.906, 1.562] | inconclusive |
| habitat+research | static | median | 16.65 | 16.35 | 0.985 | [0.93, 0.994] | no meaningful regression |
| habitat+research | static | p95 | 19.85 | 18.9 | 0.978 | [0.727, 1.069] | inconclusive |
| habitat+research | orbit | median | 16.3 | 16.3 | 0.985 | [0.887, 1.028] | no meaningful regression |
| habitat+research | orbit | p95 | 21.45 | 23.2 | 1.069 | [0.895, 1.121] | inconclusive |
| habitat+technical | static | median | 16.45 | 16.3 | 0.985 | [0.904, 1.0] | no meaningful regression |
| habitat+technical | static | p95 | 23.95 | 19.05 | 0.857 | [0.652, 1.116] | inconclusive |
| habitat+technical | orbit | median | 16.4 | 16.2 | 0.994 | [0.928, 1.037] | no meaningful regression |
| habitat+technical | orbit | p95 | 24.5 | 22.3 | 0.915 | [0.736, 1.193] | inconclusive |
| overview | static | median | 15.85 | 15.5 | 0.975 | [0.909, 1.026] | no meaningful regression |
| overview | static | p95 | 20.55 | 17.95 | 0.869 | [0.82, 0.993] | no meaningful regression |
| overview | orbit | median | 18.25 | 17.65 | 0.959 | [0.921, 1.174] | inconclusive |
| overview | orbit | p95 | 27.4 | 26.3 | 0.937 | [0.818, 1.328] | inconclusive |

**Verdict, Stage 5 against Stage 4: no regression is established.** No interval lies wholly above 1.05, with or without repetition 1. With the **Research tab open** and with the **Technical View open** the static median is *no meaningful regression* (0.985 [0.930, 0.994] and 0.985 [0.904, 1.000]); the orbit tails (p95, p99, max) of habitat stay *inconclusive* (e.g. habitat orbit p95 1.136 [0.906, 1.562]):
the data cannot exclude a worse orbit tail, and the repetition-1 load makes that tail the least reliable number here. Mean FPS is not a basis for any of this.

### Stage 5 against Stage 3 (the stage alone; no research UI in Stage 3), median and p95

| camera | mode | measure | Stage 3 (ms) | Stage 5 (ms) | paired ratio S5/S3 | 95 % CI | verdict |
|---|---|---|---|---|---|---|---|
| body | static | median | 15.85 | 16.5 | 1.039 | [1.003, 1.051] | inconclusive |
| body | static | p95 | 18.95 | 20.6 | 1.061 | [0.82, 1.445] | inconclusive |
| body | orbit | median | 15.95 | 17.35 | 1.094 | [1.032, 1.119] | inconclusive |
| body | orbit | p95 | 22.1 | 27.0 | 1.125 | [0.963, 1.405] | inconclusive |
| habitat | static | median | 18.2 | 17.8 | 0.995 | [0.943, 1.024] | no meaningful regression |
| habitat | static | p95 | 22.7 | 22.2 | 0.997 | [0.798, 1.086] | inconclusive |
| habitat | orbit | median | 19.5 | 20.15 | 1.02 | [0.894, 1.149] | inconclusive |
| habitat | orbit | p95 | 27.1 | 36.3 | 1.061 | [0.869, 1.489] | inconclusive |
| overview | static | median | 15.65 | 15.5 | 1.0 | [0.892, 1.036] | no meaningful regression |
| overview | static | p95 | 19.8 | 17.95 | 0.924 | [0.714, 1.017] | no meaningful regression |
| overview | orbit | median | 17.95 | 17.65 | 0.984 | [0.763, 1.282] | inconclusive |
| overview | orbit | p95 | 30.9 | 26.3 | 0.858 | [0.523, 1.282] | inconclusive |

Primary analysis, all 24 measures: **0 regression, 6 no meaningful regression, 18 inconclusive**; without repetition 1: **1 regression, 6 no meaningful regression, 17 inconclusive**. The one measure that changes class is the **body close-up orbit median** (primary 1.094 [1.032, 1.119], inconclusive; without repetition 1 the same measure is 1.106 [1.052, 1.125], which the rule calls a *regression*).
It is reported as it is: **a cost of roughly 5-12 % in the median frame time of the body close-up orbit against Stage 3 is probable**, it is not shown against Stage 4 (0.988 [0.882, 1.113]), and the other conditions show no regression against Stage 3.
The rendering counters agree with a small increase in geometry (body static triangles 999 878 in Stage 3, 1 021 422 in Stage 4 and Stage 5; draw calls 264 in all three).

### Counters (median over the repetitions; static camera unless noted)

| condition | build | draw calls | triangles | geometry uploads (orbit) | programs built (orbit) | LOD switches (orbit) | visibility flips (orbit) |
|---|---|---|---|---|---|---|---|
| habitat | stage3 | 427.0 | 1033428 | n/a | n/a | n/a | n/a |
| habitat | stage4 | 428.0 | 1065364 | 35 | 0 | 141 | 28 |
| habitat | stage5 | 428.0 | 1065364 | 35 | 0 | 142 | 28 |
| overview | stage3 | 455.0 | 653420 | n/a | n/a | n/a | n/a |
| overview | stage4 | 457.0 | 674384 | 21 | 0 | 145 | 64 |
| overview | stage5 | 457.0 | 674384 | 21 | 0 | 145 | 64 |
| body | stage3 | 264.0 | 999878 | n/a | n/a | n/a | n/a |
| body | stage4 | 264.0 | 1021422 | 38 | 1 | 0 | 40 |
| body | stage5 | 264.0 | 1021422 | 38 | 1 | 0 | 40 |
| habitat+research | stage3 | 384.0 | 960564 | n/a | n/a | n/a | n/a |
| habitat+research | stage4 | 385.0 | 989152 | 38 | 0 | 142 | 28 |
| habitat+research | stage5 | 385.0 | 989152 | 38 | 0 | 143 | 28 |
| habitat+technical | stage3 | 384.0 | 960564 | n/a | n/a | n/a | n/a |
| habitat+technical | stage4 | 385.0 | 989152 | 38 | 0 | 144 | 28 |
| habitat+technical | stage5 | 385.0 | 989152 | 38 | 0 | 142 | 28 |

Stage 5 and Stage 4 have identical counters (the Stage 5 changes are interface and data, not scene geometry): no program is built during an orbit except one in the body close-up, which both builds show.

**Not claimed:** no absolute frame rate is claimed for any machine other than this one under this load; software-rendered captures and the headless GPU figures are not comparable with each other.
