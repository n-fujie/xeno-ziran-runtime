# Long-run compression

Can recurrent trajectories be compressed into higher-order shapes without losing the distinctions that matter for
interventions? Compressed shapes are **detected summaries**. They are never promoted to primitives and never fed back
into the runtime.

## 1. Method [choice]

`experiments/escalation/compression.py`.

1. Every 10 steps the field is summarised at macro resolution (8 clusters × activity, memory, difference), giving 24
   numbers.
2. The summaries of all runs of one seed are quantized into 32 recurrent shapes by k-means with k-means++
   initialisation. There is one codebook per seed, shared by all of that seed's runs so their symbols are comparable.
3. The symbol sequence is factorised into recurring phrases (LZ78).

This is run for 400, 4,000 and 40,000 steps, on the reference world, with 12 seeds. The pairs are C vs D (one
status), C vs F (least fixpoint), C vs A (no reasoning), plus the noise replicate C~.

## 2. Measures

| measure | definition |
|---|---|
| compression ratio | raw bits (windows × 24 × 32) ÷ (codebook + phrases × (log₂ phrases + log₂ 32)) bits |
| replay fidelity | R² of the trajectory reconstructed from the shapes |
| path dependence | lag-5 autocorrelation of the first principal component: compressed vs raw |
| intervention fidelity | the pair's distance ÷ the noise pair's distance, compressed (symbol mismatch rate) vs raw (Euclidean) |
| counterfactual discrimination | whether a systematic pair difference is detected on raw macro means vs on shape frequencies (sign-flip max-T, 12 seeds) |
| delayed divergence | the first window at which the pair differs: compressed minus raw (windows), and how often the compressed sequence never shows it |
| hidden local differences | correlation between the pair's raw local (512-cluster) activity difference and the difference reconstructable from shapes; the magnitude kept |

## 3. Results (generated from the result files)

<!-- GENERATED:BEGIN -->
### 400 steps (12 seeds, 32 shapes, summary every 10 steps)

| run | compression ratio | phrases | replay R² | path dependence raw | compressed |
|---|---|---|---|---|---|
| C | 1.24 ± 0.00 | 28 ± 1 | 0.947 ± 0.011 | 0.917 ± 0.071 | 0.918 ± 0.064 |
| C~ | 1.24 ± 0.00 | 24 ± 1 | 0.914 ± 0.020 | 0.934 ± 0.037 | 0.916 ± 0.036 |
| D | 1.24 ± 0.00 | 28 ± 1 | 0.947 ± 0.011 | 0.917 ± 0.071 | 0.918 ± 0.064 |
| F | 1.24 ± 0.00 | 26 ± 1 | 0.934 ± 0.022 | 0.933 ± 0.038 | 0.931 ± 0.035 |
| A | 1.24 ± 0.00 | 26 ± 1 | 0.938 ± 0.013 | 0.946 ± 0.026 | 0.944 ± 0.021 |

| pair vs C | distance ÷ noise raw | compressed | systematic raw | compressed | onset delay (windows) | onset lost | local difference corr. | local magnitude kept |
|---|---|---|---|---|---|---|---|---|
| D | 0.000 ± 0.000 | 0.000 ± 0.000 | False | False | — | 0 | 0.000 ± 0.000 | 0.000 ± 0.000 |
| F | 0.268 ± 0.117 | 0.343 ± 0.097 | False | False | 5.6 ± 3.9 | 0 | 0.353 ± 0.141 | 1.097 ± 0.308 |
| A | 0.392 ± 0.113 | 0.460 ± 0.044 | True | False | 1.2 ± 1.8 | 0 | 0.409 ± 0.140 | 0.818 ± 0.173 |

Compression cost per seed: codebook 0.121 ± 0.027 s, encoding 0.003 ± 0.003 s.

### 4,000 steps (12 seeds, 32 shapes, summary every 10 steps)

| run | compression ratio | phrases | replay R² | path dependence raw | compressed |
|---|---|---|---|---|---|
| C | 11.93 ± 0.03 | 101 ± 6 | 0.824 ± 0.037 | 0.956 ± 0.014 | 0.949 ± 0.016 |
| C~ | 12.01 ± 0.06 | 88 ± 10 | 0.767 ± 0.059 | 0.961 ± 0.015 | 0.949 ± 0.015 |
| D | 11.93 ± 0.03 | 101 ± 6 | 0.824 ± 0.037 | 0.956 ± 0.014 | 0.949 ± 0.016 |
| F | 11.99 ± 0.05 | 90 ± 9 | 0.807 ± 0.044 | 0.964 ± 0.012 | 0.956 ± 0.017 |
| A | 12.02 ± 0.04 | 85 ± 7 | 0.768 ± 0.041 | 0.956 ± 0.009 | 0.938 ± 0.018 |

| pair vs C | distance ÷ noise raw | compressed | systematic raw | compressed | onset delay (windows) | onset lost | local difference corr. | local magnitude kept |
|---|---|---|---|---|---|---|---|---|
| D | 0.000 ± 0.000 | 0.000 ± 0.000 | False | False | — | 0 | 0.000 ± 0.000 | 0.000 ± 0.000 |
| F | 0.973 ± 0.157 | 0.944 ± 0.028 | False | False | 10.2 ± 5.0 | 0 | 0.455 ± 0.111 | 0.151 ± 0.062 |
| A | 0.973 ± 0.158 | 0.956 ± 0.025 | False | False | 7.2 ± 5.5 | 0 | 0.492 ± 0.114 | 0.190 ± 0.064 |

Compression cost per seed: codebook 0.769 ± 0.208 s, encoding 0.018 ± 0.008 s.

### 40,000 steps (12 seeds, 32 shapes, summary every 10 steps)

| run | compression ratio | phrases | replay R² | path dependence raw | compressed |
|---|---|---|---|---|---|
| C | 93.70 ± 4.28 | 582 ± 97 | 0.875 ± 0.036 | 0.988 ± 0.005 | 0.984 ± 0.008 |
| C~ | 95.52 ± 6.81 | 547 ± 145 | 0.856 ± 0.043 | 0.990 ± 0.004 | 0.985 ± 0.008 |
| D | 93.70 ± 4.28 | 582 ± 97 | 0.875 ± 0.036 | 0.988 ± 0.005 | 0.984 ± 0.008 |
| F | 95.53 ± 5.62 | 544 ± 122 | 0.863 ± 0.033 | 0.990 ± 0.004 | 0.985 ± 0.006 |
| A | 95.55 ± 5.23 | 543 ± 115 | 0.834 ± 0.048 | 0.987 ± 0.004 | 0.980 ± 0.007 |

| pair vs C | distance ÷ noise raw | compressed | systematic raw | compressed | onset delay (windows) | onset lost | local difference corr. | local magnitude kept |
|---|---|---|---|---|---|---|---|---|
| D | 0.000 ± 0.000 | 0.000 ± 0.000 | False | False | — | 0 | 0.000 ± 0.000 | 0.000 ± 0.000 |
| F | 0.927 ± 0.123 | 0.983 ± 0.104 | False | False | 11.8 ± 7.5 | 0 | 0.397 ± 0.233 | 0.476 ± 0.171 |
| A | 0.977 ± 0.195 | 0.990 ± 0.098 | False | False | 9.1 ± 8.6 | 0 | 0.517 ± 0.159 | 0.497 ± 0.154 |

Compression cost per seed: codebook 8.048 ± 1.882 s, encoding 0.223 ± 0.065 s.
<!-- GENERATED:END -->

## 4. Classification, then interpretation

The verdict rules are in `summary.py::compression_verdict`; `summary.json` holds the verdicts under
`compression_verdict`.

**[measured]**
- **Compression grows with run length.** Recurrent shapes compress the macro trajectory more and more as the run
  grows. At 400 steps there is almost nothing to reuse; at 40,000 steps phrases recur heavily. Replay fidelity stays
  high, and path dependence (lag autocorrelation) is retained.
- **At 400 steps compression erases an intervention-relevant distinction.** The difference between reasoning and no
  reasoning (C vs A) is systematic on the raw macro means but not on the compressed shape frequencies.
- **At 4,000 and 40,000 steps the compressed and raw descriptions agree** on every pair: same systematic verdict, a
  similar pair-to-noise distance, and no lost divergence onset. The compressed onset lags the raw onset by a few
  windows.
- **Hidden local differences are not retained.** The local activity difference of a pair is only partly
  reconstructable from the shapes: low correlation, and much of the magnitude lost. The one exception is reasoning vs
  none at 40,000 steps, which reaches the retention threshold.

**[derived]** Long-run compression preserves the distinctions that are visible at macro resolution, from 4,000 steps
on. It **does not preserve hidden local differences**, and at short horizons it can erase a coarse distinction
outright. Compressed shapes therefore cannot stand in for the runtime state when local, intervention-relevant
differences matter. They remain detected summaries and are not promoted to primitives.
