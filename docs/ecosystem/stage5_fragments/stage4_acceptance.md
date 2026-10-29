**Final acceptance of the Stage 4 performance question** (appended to `ECOSYSTEM_MEOS_STAGE4.md` section 19). The pre-fixed rule (lower CI bound above 1.05 = regression; upper bound below 1.05 = no meaningful regression; otherwise inconclusive) was applied to the **14 paired repetitions** of Stage 4 against Stage 3 that now exist: the 8 of the first acceptance (`perf_stage5/stage4_acceptance/`) and the 6 of this stage (`perf_stage5/paired/`).
Balanced tier, 150 frames; median and p95 over repetitions.

| camera | mode | measure | Stage 3 (ms) | Stage 4 (ms) | paired ratio S4/S3 | 95 % CI | verdict |
|---|---|---|---|---|---|---|---|
| body | static | median | 15.95 | 16.45 | 1.038 | [1.012, 1.085] | inconclusive |
| body | static | p95 | 19.6 | 20.4 | 1.123 | [0.835, 1.343] | inconclusive |
| body | orbit | median | 16.85 | 16.65 | 1.013 | [0.944, 1.058] | inconclusive |
| body | orbit | p95 | 26.6 | 24.4 | 0.954 | [0.789, 1.146] | inconclusive |
| habitat | static | median | 17.9 | 18.25 | 1.03 | [0.989, 1.077] | inconclusive |
| habitat | static | p95 | 23.05 | 29.6 | 1.043 | [0.896, 1.465] | inconclusive |
| habitat | orbit | median | 19.45 | 19.4 | 1.003 | [0.959, 1.022] | no meaningful regression |
| habitat | orbit | p95 | 29.1 | 25.85 | 0.932 | [0.862, 0.996] | no meaningful regression |
| overview | static | median | 15.35 | 15.75 | 1.007 | [0.986, 1.044] | no meaningful regression |
| overview | static | p95 | 19.95 | 21.1 | 0.975 | [0.925, 1.14] | inconclusive |
| overview | orbit | median | 16.75 | 17.7 | 1.018 | [0.982, 1.043] | no meaningful regression |
| overview | orbit | p95 | 29.05 | 26.35 | 0.994 | [0.75, 1.107] | inconclusive |

**Result: 0 regression, 4 no meaningful regression, 8 inconclusive.** No regression is established. The static median of body (1.038 [1.012, 1.085]) and habitat (1.030 [0.989, 1.077]) is *inconclusive*: a cost of up to about 8 % is not excluded, and for body the whole interval is above 1.0 (a small cost is probable). The orbit median of habitat and overview, and the orbit p95 of habitat, are *no meaningful regression* (the habitat orbit tail is better than Stage 3's: 0.932 [0.862, 0.996]).
Acceptance status of Stage 4 performance: **no regression established; inconclusive (a small cost not excluded) for the static median of body and habitat; no meaningful regression for the orbit median and the habitat orbit tail.** The first 8 repetitions were measured at a load of 3.0-5.3, the last 6 as stated in section 20 of the Stage 5 document.
