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
