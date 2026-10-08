# Benchmark

Scenario `benchmark-10k`: **10,000 configurations, 59,329 connections** (capacity 79,105), continuous
transitions (~1,210 semantic events per step in the sustained regime). Reproduce with `make bench`
(`backend/bench/benchmark.py`; raw output in `backend/bench/results/latest.json`).

Machine: Apple Silicon Mac (macOS 26.6, arm64), Python 3.12.13, NumPy 2.5.3. Measured 2026-09-30 08:56 with no
other simulation server running (`OMP_NUM_THREADS=1`, `caffeinate -i`). Numbers are for this machine only; the
2026-09-29 run of the same code path gave 221.6 / 93.9 steps/s, which is the run-to-run spread to expect.

## Simulation — full vs MINIMAL runtime

| | full: steps/s | p50 | p95 | MINIMAL: steps/s | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|
| Runtime only | **230.2** | 4.36 ms | 5.10 ms | **228.4** | 4.38 ms | 5.06 ms |
| Runtime + shape detection (as the live service runs it; graph pass every 10 steps) | **110.4** | 5.21 ms | 43.86 ms | **106.7** | 5.54 ms | 44.22 ms |

Events per step: full 1,210.3, MINIMAL 1,117.7 (no `transformation` events; penetrations and returns are
reconstructed by the observer in sessions, not in this runtime-only loop). The difference in steps/s is within
run-to-run spread: the reductions remove bookkeeping, not work on the critical path (dataflow audit in
docs/REDUCTION.md). MINIMAL is chosen for its evidence, not for speed.

The p95 of the second row is the periodic graph pass (reachability, strongly connected loops, components,
sampled bottlenecks, asymmetry, signatures, shape-space PCA): ~40 ms every 10 steps.

## Delta transport

| | bytes / step |
|---|---:|
| Encoded step delta, mean — full | **24,136** |
| Encoded step delta, p95 — full | 32,430 |
| Encoded step delta, mean — MINIMAL | **23,351** |
| Encoded step delta, p95 — MINIMAL | 31,235 |
| Full runtime state (for comparison) | 7,313,770 |

A delta is ~0.3% of the full state. Every event is included; the size is dominated by the state section
(quantized differences, sent as a dense `u8[N]` when more than 1/5 of configurations changed) and by the
~1,200 events per step.

## WebSocket (server in its own process, one client)

| runtime | requested speed | steps streamed/s | delta frames/s | KiB/s | server RSS |
|---|---|---:|---:|---:|---:|
| full | 30 steps/s | 24.0 | 20.7 | 633 | 154 MiB |
| full | 60 steps/s | 42.4 | 21.2 | 1,105 | 180 MiB |
| full | max | 99.9 | 13.9 | 2,215 | 169 MiB |
| MINIMAL | 30 steps/s | 23.6 | 19.6 | 607 | 179 MiB |
| MINIMAL | 60 steps/s | 41.5 | 20.7 | 1,044 | 214 MiB |
| MINIMAL | max | 91.1 | 12.2 | 2,066 | 154 MiB |

Every streamed step carries all of its events. At "max", simulation speed is bounded by the transport through
backpressure (the simulation waits when 45 steps are unsent), not by dropping. Requested speeds are not fully
reached at 30/60 steps/s because the live loop includes shape detection and yields to the transport; the
steps/s shown in the UI is the achieved rate.

MINIMAL sessions run the wave observer before streaming, so clients receive the same event kinds (except
`transformation`).

## Reasoning layer (scenario `benchmark-10k-reason`, 10k configurations)

Closed loop active for the whole run (`enabling=[]`, so scorekeeping is never gated off; `reasoning_active_share`
= 1.0). *Instrumentation* = the research probes that record, per check, whether one-status / no-entitlement
representations would compile different interventions; it is measurement, not part of the layer.

| | ms/step | steps/s |
|---|---:|---:|
| no reasoning layer | 3.93 | 254.4 |
| scorekeeping loop | 4.85 | 206.1 |
| scorekeeping loop + instrumentation | 6.13 | 163.2 |
| no reasoning layer + shape detection | 8.10 | 123.4 |
| scorekeeping loop + shape detection | 9.02 | 110.9 |

Reasoning overhead **+0.92 ms/step (+23%)**; instrumentation a further +1.28 ms/step.

## Comparison jobs

Baseline + intervention + noise replicate, horizon 150 (3 branches, worker pool): **3.37 s**, 7.48 ms per
branch-step; first divergence at step 101.

## Memory

Peak RSS of the benchmark process 293.9 MiB (it builds several 10k worlds in sequence); runtime arrays 7.0 MiB;
server process 154–214 MiB depending on buffered frames and checkpoints (24 kept, thinned).

## Rendering FPS

**Not re-measured on 2026-09-30.** The in-app browser pane throttled `requestAnimationFrame` to ~1.5 callbacks/s
while unfocused (a raw rAF probe independent of the app confirmed it), so any number would measure the host, not
the renderer. The rendering path did not change in this phase (MINIMAL only changes which events the server
computes itself). Last valid measurement (full runtime, 2026-09-29):

Measured in the Claude desktop in-app browser (Chromium, WebGL, 1440×900 viewport) with the simulation running
at 30 steps/s on `benchmark-10k`, reading the app's fps counter (`window.__xzr.get().fps`):

| view · scale | visible | fps |
|---|---|---:|
| Network · Macro | 8 clusters, 56 aggregated flows | 60 |
| Network · Regional / Local | 128 / 512 clusters, 600 flows | 60 |
| Network · Configuration | 2,523 configurations, 14,752 connections, ~250 moving particles | 60 |
| Network · Relation | 954 configurations, 14,812 connections, ~790 particles | 60 |
| Shape Space · Configuration | **all 10,000 configurations**, ~1,280 particles | 60 |

60 is the display refresh cap, so these show the budget was not exceeded, not the headroom. Rendering FPS cannot
be measured headless; repeat by opening `/?scenario=benchmark-10k`.

## What is *not* optimized away

No semantic event is dropped or sampled at any point: the event log (last 1,500 steps in memory, exportable)
and the stream contain every ignition, penetration, transformation, return, decay, cut, new/removed connection
and reconfiguration. Reductions come only from: level of detail (clusters at coarse scales, viewport tiles at
fine scales), quantization of continuous state with hysteresis, dense/sparse state encoding, memory afterimages
streamed every 5 steps, and backpressure.

## Resolution escalation phase (generated)

Measured on a quiet machine: no other simulation, experiment or benchmark running. The costs are split into core
runtime, reasoning runtime, diagnostic instrumentation, experiment-harness overhead and compression overhead;
research instrumentation is never counted as product runtime cost.

<!-- GENERATED:ESCALATION:BEGIN -->
Measured 2026-10-01 09:46:24 (macOS-26.6.2-arm64-arm-64bit, Python 3.12.13, NumPy 2.5.3); `make bench-escalation`; raw: `backend/experiments/results/resolution/bench.json`.

### 1. Core runtime (engine step only)

| configurations | runtime | steps/s | ms/step p50 | p95 | runtime arrays (MiB) |
|---|---|---|---|---|---|
| 1,500 | full | 966.9 | 1.043 | 1.242 | 0.89 |
| 1,500 | minimal | 943.2 | 1.074 | 1.26 | 0.89 |
| 10,000 | full | 229.6 | 4.397 | 5.484 | 5.92 |
| 10,000 | minimal | 217.5 | 4.634 | 5.451 | 5.92 |
| 100,000 | full | 29.3 | 35.033 | 41.867 | 58.84 |
| 100,000 | minimal | 25.7 | 36.253 | 56.043 | 58.84 |

Shape detection at 10,000: 96.5 steps/s (p95 49.85 ms). Delta: 20480 bytes/step mean. WebSocket (full runtime): max_speed: 90.0 steps/s, 10.8 frames/s, 1861.4 KiB/s; speed_30: 26.7 steps/s, 23.5 frames/s, 690.0 KiB/s; speed_60: 46.1 steps/s, 23.0 frames/s, 1214.8 KiB/s

### 2. Reasoning runtime (closed loop with the reference structure and triggers vs no reasoning layer)

| configurations | structure size | no reasoning (ms/step) | closed loop (ms/step) | overhead (ms/step) | relative |
|---|---|---|---|---|---|
| 1,500 | 32 | 1.021 | 1.235 | 0.215 | 21.0% |
| 10,000 | 32 | 3.33 | 4.219 | 0.889 | 26.7% |
| 100,000 | 32 | 41.677 | 52.828 | 11.15 | 26.8% |
| 1,500 | 128 | 1.28 | 2.234 | 0.955 | 74.6% |
| 1,500 | 512 | 1.182 | 4.549 | 3.367 | 284.7% |
| 1,500 | 2048 | 1.09 | 22.502 | 21.412 | 1964.7% |

### 3. Diagnostic instrumentation (research only; never part of product runtime cost)

| configurations | multi-scale observer (ms/step) | realized-coupling probe (ms/step) |
|---|---|---|
| 1,500 | 0.036 | 0.008 |
| 10,000 | 0.168 | 0.029 |
| 100,000 | 1.477 | 0.256 |

Per-condition statistics (sign-flip max-T, 12 seeds): 1500 node-level family (8×4×4000): 6.068 s; meso family (8×4×32): 0.101 s

### 4. Experiment harness overhead (measured inside the matrix runs, 7 parallel workers)

| configurations | harness run (ms/step, median) | loop only (ms/step) | observer + probes + bookkeeping |
|---|---|---|---|
| 1,500 | 4.33 | 4.18 | 0.15 |
| 10,000 | 11.35 | 10.93 | 0.42 |
| 100,000 | 124.71 | 117.74 | 6.98 |

### 5. Compression overhead (codebook + encoding + phrase factorisation, one run)

| steps | seconds |
|---|---|
| 400 | 0.039 |
| 4,000 | 0.142 |
| 40,000 | 0.858 |

Peak RSS of the benchmark process: 1076.2 MiB.
<!-- GENERATED:ESCALATION:END -->

**Rendering FPS: not re-measured in this phase.** Only a measurement taken with the browser pane actually visible and
focused is valid. The last valid figure is the 60 fps at every scale measured on 2026-09-29 (section *Rendering FPS*
above). It is historical: this phase did not change the rendering path, and it has not been re-measured.
