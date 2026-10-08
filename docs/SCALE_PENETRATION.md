# Scale penetration

How a local reasoning difference reaches the world and whether it comes back. Only existing operational
transitions are used: no propagation semantics was added to the runtime. Every step below is measured by
observers outside the runtime.

## 1. The chain (measured per paired run, median over seeds)

1. **Reasoning levels differ.** This is the first check at which the variant's effective item levels differ from
   C's. It is not defined for A, which has no reasoning levels.
2. **Compiled interventions differ.** This is the first check at which the semantic intervention sets differ
   (operation, target, factor).
3. **World differs (exact).** This is the first step at which the per-step state signature differs.
4. **Targets differ (exact).** This is the first step at which the configurations addressed by reasoning differ.
5. **First macro cluster differs (exact).**
6. **Systematic differences.** For each resolution, the time segment at which a family-wise significant, practically
   non-negligible difference first appears.

## 2. Measures [choice]

- **Penetration depth.** The coarsest resolution with a systematic difference.
- **Resolutions crossed.** The number of resolutions (out of five) with a systematic difference.
- **Attenuation / amplification.** The ratio of end-of-run divergence ratios, coarser ÷ finer. The divergence ratio
  is the pair's window distance ÷ the distance between C and its noise replicate: 0 means identical, and about 1
  means as different as an independent run. Below 1 the difference attenuates when coarse-grained; above 1 it is
  amplified relative to noise.
- **Propagation delay.** Steps between the chain stages, and between systematic onsets at successive resolutions.
- **Return into local conditions.** The local divergence ratio late in the run minus its value when the first macro
  cluster diverged. A positive value means divergence keeps growing locally after it has crossed scales.
- **Persistence after return.** Whether every detected resolution has a persistent time pattern.

## 3. Results (generated from the result files)

<!-- GENERATED:BEGIN -->
Comparisons with a systematic difference at ≥ 1 resolution: 68 of 318 with a trajectory difference.

| vs C | condition | levels | interventions | world | targets | first macro | systematic at | depth | local/node | meso/local | macro/meso | global/macro | return |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | horizon:400 | — | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.014 | 1.089 | 0.894 | 1.227 | 0.4992 |
| A | memory:near_zero | — | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 0.996 | 1.144 | 0.937 | 1.137 | 0.5649 |
| A | mutation:high_state | — | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.011 | 1.132 | 0.914 | 0.713 | 0.407 |
| A | n:10000 | — | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.059 | 1.192 | 1.077 | 0.73 | 0.6573 |
| A | n:100000 | — | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.146 | 1.289 | 1.132 | 1.665 | 0.7185 |
| A | n:100000:h400 | — | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.136 | 1.234 | 1.259 | 0.361 | 0.5363 |
| E | n:100000:h400 | 10 | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 0.988 | 0.938 | 0.834 | 1.083 | 0.5052 |
| G | n:100000:h400 | 220 | 220 | 221 | 221 | 221 | node, local, meso, macro, global | global | 1.024 | 0.89 | 1.002 | 0.864 | 0.5001 |
| H | n:100000:h400 | 10 | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.005 | 0.899 | 1.076 | 0.896 | 0.4927 |
| A | power:48seeds | — | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.003 | 1.049 | 1.076 | 1.084 | 0.5285 |
| A | return:competing | — | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.008 | 1.076 | 1.16 | 1.188 | 0.7248 |
| A | return:immediate | — | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 0.998 | 1.086 | 1.131 | 0.669 | 0.6114 |
| H | size:128 | 10 | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.026 | 1.112 | 0.886 | 1.205 | 0.4583 |
| H | size:2048 | 10 | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.099 | 1.909 | 1.577 | 1.125 | 0.7053 |
| A | size:512 | — | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.096 | 1.414 | 0.992 | 0.807 | 0.7832 |
| H | size:512 | 10 | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.061 | 1.255 | 1.113 | 2.145 | 0.6238 |
| A | strong×topology:bottlenecked | — | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 0.994 | 1.213 | 1.215 | 0.533 | 0.4808 |
| A | strong×topology:hierarchical | — | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.027 | 1.006 | 1.164 | 1.069 | 0.6806 |
| A | strong×topology:highly_clustered | — | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.025 | 1.13 | 0.968 | 0.995 | 0.8851 |
| A | topology:highly_clustered | — | 200 | 201 | 201 | 201 | node, local, meso, macro, global | global | 1.004 | 1.173 | 0.897 | 0.379 | 0.8249 |
| A | coupling:strong | — | 200 | 201 | 201 | 201 | node, local, meso, macro | macro | 1.035 | 1.11 | 1.097 | 1.008 | 0.48 |
| E | horizon:400 | 10 | 200 | 201 | 201 | 201 | node, local, meso, macro | macro | 1.0 | 1.052 | 0.854 | 1.511 | 0.498 |
| A | memory:external_persistent | — | 200 | 201 | 201 | 201 | node, local, meso, macro | macro | 1.005 | 1.122 | 0.886 | 1.165 | 0.552 |
| E | mutation:high_state | 10 | 200 | 201 | 201 | 201 | node, local, meso, macro | macro | 1.035 | 1.13 | 0.901 | 1.099 | 0.4111 |
| A | size:128 | — | 200 | 201 | 201 | 201 | node, local, macro, global | global | 1.025 | 1.048 | 1.031 | 1.563 | 0.5245 |
| A | strong×topology:weakly_connected | — | 200 | 201 | 201 | 201 | node, local, meso, global | global | 1.004 | 0.951 | 0.912 | 0.708 | 0.6094 |
| H | structure:shallow_acyclic | 10 | 200 | 201 | 201 | 201 | node, local, meso, macro | macro | 0.989 | 1.04 | 1.003 | 1.189 | 0.5462 |
| A | topology:hierarchical | — | 200 | 201 | 201 | 201 | node, local, meso, macro | macro | 0.996 | 1.125 | 0.882 | 0.77 | 0.5985 |
| A | topology:modular | — | 200 | 201 | 201 | 201 | node, local, meso, global | global | 1.021 | 1.08 | 1.081 | 1.424 | 0.6785 |
| A | address:locally_stable_globally_unstable | — | 200 | 201 | 201 | 201 | local, meso, global | global | 1.012 | 1.089 | 1.004 | 0.938 | 0.5403 |
| A | memory:delayed_return | — | 200 | 201 | 201 | 201 | local, meso, macro | macro | 1.025 | 1.01 | 1.01 | 1.191 | 0.5458 |
| A | memory:short | — | 200 | 201 | 201 | 201 | local, meso, macro | macro | 0.989 | 1.041 | 1.041 | 0.676 | 0.5963 |
| A | mutation:mixed | — | 200 | 201 | 201 | 201 | node, local, meso | meso | 1.006 | 1.011 | 1.043 | 0.874 | 0.4136 |
| E | mutation:mixed | 10 | 200 | 201 | 201 | 201 | node, local, meso | meso | 1.033 | 1.075 | 0.82 | 1.093 | 0.4492 |
| E | power:48seeds | 10 | 200 | 201 | 201 | 201 | node, local, meso | meso | 1.018 | 1.017 | 1.105 | 0.843 | 0.4859 |
| A | size:2048 | — | 200 | 201 | 201 | 201 | meso, macro, global | global | 0.98 | 1.18 | 1.129 | 1.14 | -0.0662 |
| H | strong×topology:highly_clustered | 10 | 200 | 201 | 201 | 201 | node, local, meso | meso | 1.003 | 1.006 | 0.845 | 1.519 | 0.7125 |
| A | strong×topology:modular | — | 200 | 201 | 201 | 201 | node, meso, global | global | 1.021 | 1.046 | 0.989 | 2.088 | 0.5863 |
| A | structure:record_fragmentation | — | 200 | 201 | 201 | 201 | node, local, meso | meso | 0.993 | 1.12 | 1.165 | 0.401 | 0.5785 |
| E | n:100000 | 10 | 200 | 201 | 201 | 201 | meso, macro | macro | 0.994 | 0.89 | 1.036 | 0.751 | 0.6205 |
| H | n:100000 | 10 | 200 | 201 | 201 | 201 | node, meso | meso | 1.001 | 0.94 | 0.886 | 1.456 | 0.6176 |
| A | reference | — | 200 | 201 | 201 | 201 | meso, macro | macro | 1.03 | 1.075 | 1.032 | 1.065 | 0.5774 |
| A | return:delayed | — | 200 | 201 | 201 | 201 | node, local | local | 1.01 | 1.066 | 0.991 | 1.191 | 0.5954 |
| E | size:128 | 10 | 200 | 201 | 201 | 201 | meso, macro | macro | 1.019 | 1.018 | 1.091 | 1.215 | 0.5445 |
| J | size:128 | 1130 | 1270 | 1271 | 1271 | 1271 | macro, global | global | 1.012 | 1.045 | 1.003 | 1.804 | 0.8061 |
| E | size:512 | 10 | 200 | 201 | 201 | 201 | node, local | local | 0.975 | 0.939 | 1.055 | 0.881 | 0.3471 |
| E | size:9 | 10 | 200 | 202 | 202 | 202 | node, local | local | 1.032 | 1.021 | 0.943 | 0.82 | 0.6198 |
| A | structure:distributed_external_memory | — | 200 | 201 | 201 | 201 | node, local | local | 0.994 | 1.093 | 1.12 | 1.023 | 0.543 |
| H | structure:local_external_memory | 10 | 200 | 201 | 201 | 201 | node, macro | macro | 1.025 | 1.026 | 1.035 | 1.775 | 0.5701 |
| A | structure:multiple_clusters | — | 200 | 201 | 201 | 201 | node, local | local | 1.002 | 1.001 | 0.977 | 2.316 | 0.526 |
| H | structure:multiple_clusters | 10 | 200 | 201 | 201 | 201 | node, local | local | 0.986 | 0.949 | 0.954 | 0.779 | 0.5101 |
| A | structure:record_loss_reconstruction | — | 200 | 201 | 201 | 201 | local, meso | meso | 1.044 | 1.139 | 1.007 | 0.917 | 0.6243 |
| A | structure:unsupported_addressable | — | 200 | 201 | 201 | 201 | meso, macro | macro | 1.053 | 0.993 | 1.028 | 1.093 | 0.5451 |
| H | structure:unsupported_addressable | 10 | 200 | 201 | 201 | 201 | node, meso | meso | 1.048 | 1.008 | 0.868 | 0.724 | 0.5454 |
| E | address:locally_stable_globally_unstable | 10 | 200 | 201 | 201 | 201 | local | local | 1.027 | 1.065 | 1.008 | 1.014 | 0.3293 |
| A | address:partially_unstable | — | 200 | 201 | 201 | 201 | meso | meso | 1.01 | 0.979 | 0.97 | 0.645 | 0.5693 |
| H | coupling:strong | 10 | 200 | 201 | 201 | 201 | node | node | 0.985 | 0.984 | 0.986 | 1.012 | 0.4991 |
| A | horizon:40000 | — | 200 | 201 | 201 | 201 | local | local | 1.027 | 1.213 | 1.152 | 1.599 | 0.1853 |
| H | memory:delayed_return | 10 | 200 | 201 | 201 | 201 | global | global | 1.0 | 0.893 | 1.021 | 1.481 | 0.5226 |
| A | memory:long | — | 200 | 201 | 201 | 201 | global | global | 0.998 | 1.036 | 1.134 | 1.863 | 0.1056 |
| F | n:10000 | 10 | 200 | 201 | 201 | 201 | macro | macro | 0.982 | 1.018 | 0.881 | 1.324 | 0.6225 |
| A | size:9 | — | 200 | 202 | 202 | 202 | node | node | 1.02 | 1.031 | 1.2 | 0.895 | 0.7405 |
| A | strong×topology:dense_random | — | 200 | 201 | 201 | 201 | global | global | 1.016 | 0.902 | 0.91 | 0.61 | 0.4558 |
| E | strong×topology:modular | 10 | 200 | 201 | 201 | 201 | node | node | 1.011 | 1.024 | 0.998 | 1.246 | 0.6656 |
| A | strong×topology:nested_multiscale | — | 200 | 201 | 201 | 201 | global | global | 1.017 | 0.953 | 1.084 | 0.76 | 0.5217 |
| H | structure:distributed_external_memory | 10 | 200 | 201 | 201 | 201 | global | global | 1.001 | 1.06 | 1.124 | 0.664 | 0.5348 |
| H | structure:record_fragmentation | 10 | 200 | 201 | 201 | 201 | node | node | 0.996 | 0.971 | 0.828 | 0.858 | 0.5313 |
| A | structure:sparse_conflicts | — | 200 | 201 | 201 | 201 | node | node | 1.017 | 1.032 | 0.992 | 1.916 | 0.5514 |
<!-- GENERATED:END -->

## 4. Classification, then interpretation

All counts and ratios are in the generated table above and in `summary.json` (`penetration`).

**[measured]**
- **Exact propagation is immediate.** A difference in compiled interventions changes the world state one step later.
  The targeted configurations and the first macro cluster differ from that same step. Exact divergence then spreads
  through ordinary transitions, as it would from any perturbation.
- **The pair decorrelates about as much as independent runs, at every resolution.** Coarse-graining neither
  attenuates nor amplifies the divergence much relative to noise. Where a difference is systematic, the coarse
  resolutions carry it slightly *more* strongly than the noise pair, and that is what makes it detectable.
- **Few systematic differences persist.** Most are transient (early segments) or visible only in the time average.
  Local divergence keeps growing after the macro onset in most pairs. This is the "return into local conditions",
  which is indistinguishable from continued chaotic decorrelation.

**[interpretation]** Penetration depth is not limited by an attenuating path: every difference reaches every scale
exactly. What limits it is whether the difference is *systematic*, meaning it shifts the same summaries the same way
across random streams. That is a property of the structural difference and the world, and not of the propagation
path.
