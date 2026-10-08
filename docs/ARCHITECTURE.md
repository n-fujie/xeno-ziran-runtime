# Architecture — XENO ZIRAN SIMULATOR runtime (`xeno-ziran-runtime`)

*Operational Shape Simulation Platform.* Explore possible transitions under intervention. The Philosophical Runtime
(practice layer, reason lab) is one operational region of the simulator, beside the experimental runtime and the
research results; see the README for the layering.

## 0. Relation to the existing repository (Phase 1 inspection)

`../ziran-xeno-simulator` (v0.4.0, published) is an event-scheduled symbolic engine: opaque values,
rule bundles, full causal traces, description-space lineage. It is correct for its research purpose,
but it is single-threaded TS with per-event objects and cannot run 10 000 configurations × 50 000
connections at interactive rates, and its `src/` tree is pinned to a release tag by its own tests.

This project is therefore a **new sibling service**. The published repository is not modified.
What was carried forward, and where:

| From `ziran-xeno-simulator` | Reused as | Here |
|---|---|---|
| Seeded, cloneable RNG streams (`core/rng.ts`) | Explicit stochasticity: one seeded `numpy` PCG64 generator per run, state captured in checkpoints | `xzr/runtime/engine.py` |
| Canonical JSON + SHA-256 run identity (`core/hash.ts`) | Deterministic-replay fingerprint of runtime arrays | `xzr/runtime/state.py::fingerprint` |
| Layer-0 anti-regression vocabulary scan (`bench/layers.ts`) | Test that the runtime and shape layers contain no domain vocabulary | `backend/tests/test_vocabulary.py` |
| Counterfactual twin-run + diff (`core/counterfactual.ts`) | Baseline vs intervention from the same checkpoint and RNG state | `xzr/compare/compare.py` |
| Penetration as causal hop tracking (`core/penetration.ts`) | Per-ignition cause edge, wave origin and depth | `xzr/runtime/ops.py::penetrate` |
| Non-redundancy framing (a distinction matters iff removing it changes outcomes) | Every intervention is evaluated only by operational differences | `xzr/compare/` |

Nothing from `src/domains/*` (market, institution, body…) is carried over: domain bundles are exactly
what this runtime must not contain.

## 1. Layers (strict, one-directional)

```
                 ┌───────────────────────────── Visualization (frontend/) ─────────────────────────────┐
                 │  Network · Shape Space · Address Space · World Map · Globe · Timeline · Compare ·   │
                 │  Practice console.   deck.gl WebGL, LOD by zoom, delta mirror, binary decoder       │
                 └───────────────▲───────────────────────────────▲─────────────────────────────────────┘
                                 │ WebSocket (binary deltas)     │ REST (JSON / binary LOD tiles)
┌────────────────────────────────┴───────────────────────────────┴──────────────────────────────────────┐
│ Service (xzr/service): FastAPI control API, one worker thread per session, job pool for comparisons   │
└──────▲─────────────────────▲──────────────────────▲─────────────────────────▲─────────────────────────┘
       │                     │                      │                         │
┌──────┴────────┐  ┌─────────┴────────┐  ┌──────────┴──────────┐  ┌───────────┴──────────────────┐
│ Simulation    │→ │ Shape Detection  │→ │ Interpretation      │  │ Philosophical Practice       │
│ Runtime       │  │ (operational     │  │ (optional labels on │  │ claims/commitments/…         │
│ xzr/runtime   │  │ descriptors)     │  │ recurrent shapes)   │  │ compiles to runtime          │
│ numbers only  │  │ xzr/shapes       │  │ xzr/interpret       │  │ Interventions (xzr/practice) │
└───────────────┘  └──────────────────┘  └─────────────────────┘  └──────────────────────────────┘
```

Dependency rules (enforced by `tests/test_layering.py`):

* `runtime` imports nothing from the other layers and contains no human-readable domain labels.
* `shapes` reads runtime arrays; never writes them.
* `interpret` reads shape signatures; never touches runtime. A test runs the same seed with and
  without interpretation and checks bit-identical runtime fingerprints.
* `practice` never mutates runtime directly: it compiles commitments into a list of
  `Intervention` records (threshold modifiers, gates, severances, memory conditions) addressed by
  *opaque ids* (configuration index, cluster address, named node/edge set). The runtime applies those
  records without knowing what concept produced them.

## 2. Simulation Runtime (`xzr/runtime`)

Structure-of-arrays, `numpy`, fixed capacity with free-slot reuse for connections.

Per configuration *i*: `diff` (current difference), `form` (opaque small integer: what a difference
is *like*; transformations change it), `theta` (ignition threshold), `retention` (fraction kept per
step), `memory` (decaying ignition trace), `mem_coupling` (how memory shifts the effective
threshold), `cap` (local constraint: saturation), `frozen` (local constraint: cannot ignite),
`refractory`, wave bookkeeping (`wave_origin`, `wave_depth`), optional `geo` (lon, lat; NaN if absent).

Per connection *e*: `src`, `dst`, `weight`, `alive`, `transform` (form-rewrite code), `gate`
(permeability, 0..1 — boundaries are gates), `load` (recent flow, drives cuts).

**Reachable transitions** of *i* = alive out-connections with gate > 0 whose target is not frozen.
They are derived, not stored.

Step order (each is a named operation in `ops.py`, also callable directly as an intervention):

1. **ignite** — `diff ≥ θ_eff` with `θ_eff = θ·threshold_mod − mem_coupling·memory`, not refractory, not frozen.
2. **propagate / penetrate** — ignited configurations emit a fraction of their difference along reachable
   transitions (∝ weight·gate). The dominant incoming connection of each receiver is its *cause edge*;
   when the receiver ignites next step the hop is a **penetration** carrying wave origin and depth + 1.
3. **transform** — a dominant incoming flow through a connection with `transform ≠ 0` rewrites the
   receiver's `form`.
4. **retain / decay** — non-ignited configurations keep `retention·diff`; configurations falling below ε
   emit a **decay** event.
5. **return** — an ignition whose wave origin is itself at depth > 0 (a difference came back).
6. **memory** — `memory ← λ·memory + ignited`.
7. **cut / disconnect** — connections whose load exceeds capacity break (**cut**); connections whose
   weight falls below `w_min` are **disconnected**.
8. **connect** — co-igniting, memory-bearing, unconnected configurations within the same local
   neighbourhood may form new connections (seeded, rate-limited).
9. **reconfigure** — overloaded configurations redirect their strongest outgoing connection to a
   second-order neighbour (topology change without net edge loss).

Every step emits a `StepDelta`: quantized changed differences (only indices whose quantized value
changed), changed forms, ignitions, penetrations, transformations, returns, decays, cuts, new
connections, removed connections, reconfigurations. **No semantic event is ever dropped**; streaming
aggregates, it never filters the event log.

Determinism: one PCG64 generator per run. `fingerprint()` hashes all arrays + RNG state. Checkpoints
every *k* steps capture full arrays + RNG state; rewind = restore nearest checkpoint + deterministic
replay.

## 3. Shape Detection (`xzr/shapes`)

Cheap descriptors every step (ignition count, amplification ratio, branching ratio, re-ignition,
returns, decay, topology-change z-score, memory dependence) and graph descriptors every *n* steps
using `scipy.sparse.csgraph` (reachability from active set, strongly connected loops in the recent-flow
graph, weak components / fragmentation, sampled-BFS bottlenecks, Gini concentration, persistence,
path dependency via lagged overlap vs. chance, attractor-like recurrence via coarse pattern hashes,
transition asymmetry over reciprocal pairs). Per-cluster descriptor vectors are quantized into
**shape signatures**; signatures recurring across clusters/windows are the "recurrent operational
shapes". Also computes the **Abstract Shape Space** embedding (PCA of per-configuration descriptor
vectors).

## 4. Interpretation (`xzr/interpret`)

A declarative rule table mapping signature feature ranges to optional labels ("commitment-cluster-like",
"credit-like", …). Labels are attached to *already detected* shapes and displayed with the rule that
produced them. They cannot change any runtime quantity.

## 5. Philosophical Practice (`xzr/practice`)

Concepts (opaque tokens), claims (use concepts), commitments (strength 0..1 per claim), entitlements
(derived), incompatibilities, inferential dependencies (committive / permissive), withdrawal,
revision, consequence. Scorekeeping is a deterministic fixpoint: commitments close under committive
dependencies; entitlement requires commitment, entitled premises (or default entitlement) and no
stronger incompatible commitment. Each claim may carry **bindings** — structured operational effects
(threshold modifier on a target set, gate on a boundary, severance, memory condition). Active
bindings = bindings of entitled commitments weighted by strength; they compile to runtime
`Intervention`s. Commands are parsed by a small deterministic grammar (`parser.py`). No LLM is involved;
an LLM could later only translate prose into this grammar.

## 6. Multi-scale / LOD (`xzr/lod`)

Hierarchy is intrinsic (topology), not geographic: spectral embedding of the connection graph →
recursive principal-axis bisection → addresses such as `3.1.0.2`. Scale levels:

| Level | Shows |
|---|---|
| Macro | ~8 clusters + aggregated flows |
| Global | ~32 clusters + aggregated flows |
| Regional | ~128 clusters |
| Local | ~512 clusters |
| Configuration | configurations in viewport + strongest connections in viewport |
| Relation | configurations + all connections in viewport, thresholds, memory rings, recent transitions |

Each projection (network, shape space, address space, geo) positions clusters at the centroid of
their members. The client requests `lod` tiles for (layout, level, viewport); the server answers from a
grid index with compact binary arrays. Configurations without geo still appear in every non-geo view.

## 7. Transport

* REST (`/api/...`): sessions, scenarios, run/pause/step/reset/rewind, interventions, comparison
  jobs, event log, exports (JSON/CSV), LOD tiles.
* WebSocket (`/ws/{session}`): binary frames. Frame = header + concatenated step deltas since the last
  frame (steps merged only at transport level; every event keeps its step index) + cluster-level
  aggregates + a JSON metrics record. Frame rate capped (default 30 Hz); simulation speed is
  independent (steps/s setting or "max").

## 8. Deployment

Single container: multi-stage Dockerfile (Node builds `frontend/`, Python serves API + static build),
listens on `$PORT` (Cloud Run convention). Sessions are in-memory per instance — documented limit;
for multi-instance deployment, pin sessions (Cloud Run session affinity) or split the worker later.

## 9. Modules

```
backend/xzr/runtime/{state,ops,engine,delta,generator,intervention,flags,relational}.py
backend/xzr/shapes/{metrics,detector,waves}.py
backend/xzr/interpret/labels.py
backend/xzr/practice/{graph,parser,compile,support}.py
backend/xzr/compare/{compare,trajectory}.py
backend/xzr/reasonlab/{representations,conditions,loop}.py
backend/xzr/experiments/{runs,reduction,reduction_rules,reason,catalog}.py
backend/experiments/run_reduction.py  backend/experiments/results/*.json  backend/scripts/make_reports.py
backend/xzr/lod/{hierarchy,layouts,tiles}.py
backend/xzr/scenario/{model,build,io}.py  + scenarios/*.json
backend/xzr/service/{app,session,protocol}.py
backend/tests/*  backend/bench/benchmark.py
frontend/src/{api,store,proto,views,components,lod}/…
Dockerfile, docker-compose.yml, README.md, docs/*.md
```

## 10. Implementation notes (as built)

* **Dynamics constants that matter.** Emission is normalized over reachable transitions and multiplied by a
  transmission `gain` (difference is not conserved); an ignition keeps only a `discharge` fraction of its
  residue; loaded connections conduct less (`fatigue`); memory can lower a threshold to at most `theta_floor`
  of its base; `cap` is ~1.8× threshold. Without these the field was either sub-critical (waves die) or
  saturated (refractory-limited oscillation everywhere); defaults give a sustained, intermittent regime.
* **Generator.** Latent-space proximity connections plus *distance-biased* longer connections (rank⁻¹ among
  the 160 nearest) and 20% uniform shortcuts. With uniform long-range links only, coarse topology ignored
  latent geometry, so topological macro-clusters were scattered across the network projection.
* **Transport.** State sections use hysteresis (3 quantization levels), switch to dense `u8[N]` when >1/5 of
  configurations changed, and memory is streamed every 5 steps. Backpressure: with clients attached the
  simulation waits once 45 steps are unsent. Events are never dropped. Protocol fixtures generated by the
  backend encoder (`backend/scripts/make_fixtures.py`) are decoded by the frontend tests; a backend test fails
  if they are stale.
* **Rendering.** One imperative deck.gl `Deck` per spatial view (Orthographic, Map, Globe); layers are rebuilt
  each animation frame from the client mirror using binary attributes. deck.gl is used for the network view
  too (instead of Sigma.js) so that all projections share one renderer, one LOD scheme and one animation path.
  Camera moves (breadcrumb / cluster drill-down) are animated in the frame loop with a controlled view state.
* **Comparison.** Baseline, intervention and a noise-floor replicate run in a worker pool on forks of the
  live engine; the live session is untouched until `apply`.

## 11. Research phase additions (as built)

Only what the reduction and non-redundancy experiments required; the layering above is unchanged.

* **Runtime flags** (`runtime/flags.py`). `Flags` selects removal / replacement variants of each operation; the
  default `FULL` is byte-identical to the pre-research runtime (protocol fixtures unchanged). `MINIMAL` =
  `fused_transition`, `transform="off"`, `wave_state="off"`, `return_events="off"`, `reconfigure="mutation"` —
  only reductions supported by evidence (docs/MINIMAL_RUNTIME.md). Sessions accept `"flags": "full" | "minimal" |
  {…}`; the UI accepts `?runtime=minimal`. With `wave_state`/`return_events` off, the session reconstructs
  penetration origin/depth and returns with `shapes/waves.py::WaveObserver` (outside the runtime) before
  streaming.
* **Trajectory comparison** (`compare/trajectory.py`): recordings, distance criteria and the noise floor used by
  the reduction study.
* **Terminology-free support graph** (`practice/support.py`): the alternative representation used to test the
  vocabulary; it compiles through the same `active_bindings()` interface as scorekeeping (`practice/compile.py`
  is generic over it).
* **Reason lab** (`reasonlab/`): the closed loop world → probes (`conditions.py::WorldProbe`) → grounded revisions
  → compile → `InterventionGate` → world. The gate accepts only operational overlay records (threshold, gate,
  memory condition, freeze, mutation); the loop has no reference that could write runtime arrays. Enabling
  conditions are operational measurements; failure collapses the layer (decay / drop / freeze policy).
  `representations.py` holds the compared representations, the memoryless policy and schedule replay.
* **Experiments** (`experiments/`): the reduction study (stage 1 distance vs noise, stage 2 paired systematic
  effects, audits, mechanical classification) and the reasoning suite (`philosophical_nonredundancy` scenarios,
  representation equivalence, seven criteria, multi-seed world effects, phases, enabling matrix, mutation sweep,
  closed-loop trace). They import runtime, practice and reasonlab; nothing imports them except the service's
  read-only `/api/experiments*` endpoints, which serve the result files to the Research views.
* **Layering tests** cover `reasonlab` (never imported by runtime/shapes) and the vocabulary scan now also covers
  `practice/support.py`, `reasonlab/conditions.py` and the runtime docstrings.

## 12. Resolution escalation additions (as built)

All additions are additive. The default runtime is still byte-identical to the protocol fixtures. The reasoning
layer still reaches the world only through `InterventionGate`, and no propagation semantics were added to the runtime.

* **Runtime flag values** (`runtime/flags.py`, `runtime/ops.py`):
  * `disconnect` = `weight_zero | as_cut | as_mutation | redirect`, the disconnection replacements;
  * `topology_trigger` = `unified | generic_conditions | merged`, the cut / reconfiguration trigger merges.

  These are experiment variants; the defaults (`on`, `separate`) are unchanged.
* **World families** (`scenario/topologies.py`):
  * 10 topology families;
  * memory regimes;
  * return / delay structures;
  * 8 targeted disconnection structures;
  * transmission-gain calibration to a common sustained activity.

  Node parameters are drawn as in the default generator.
* **Multi-resolution observer** (`shapes/multiscale.py`). Read-only. It records:
  * exact per-step signatures;
  * window fingerprints;
  * node features;
  * cluster aggregates at local, meso and macro resolution (hierarchy depths 9, 5 and 3);
  * global aggregates.
* **Reasoning structures**:
  * `reasonlab/structures.py` holds the 15 neutral structure generators, their descriptors, variants A–K and
    `revert_to_reference`;
  * `reasonlab/mixed.py` holds mixed rules per cluster;
  * `practice/support.py` gains an optional `sticky` conflict-persistence mode and a version-keyed evaluation memo,
    which gives identical results;
  * `reasonlab/representations.py` gains `untranslate` and the edits `add_conflict`, `lose_records` and
    `restore_records`.
* **World-responsive revision** (`reasonlab/triggers.py`). 10 trigger kinds, plus `overwrite`, each calibrated on
  its region's pre-reasoning baseline. `ReasonLoop` gains optional hooks, all off by default:
  * `triggers`;
  * a prebuilt `rep`;
  * a `light` (compact) timeline;
  * enabling conditions relative to a calibrated baseline (`rel`);
  * persistent records (`rep.persistent`);
  * a memo in target resolution per compile.

  `WorldProbe` gains the `closure` and `churn` metrics.
* **Experiments** (`experiments/escalation/`):

  | module | role |
  |---|---|
  | `harness` | world assembly per condition; paired runs per seed |
  | `stats` | sign-flip max-T, equivalence, classification rules |
  | `analysis` | per-condition tests at five resolutions × two time families |
  | `runner` | resumable process pool |
  | `matrix` | the design and its recorded omissions |
  | `disconnection`, `topology_triggers`, `adaptivity`, `clusters`, `compression` | the studies |
  | `summary` | aggregation into `results/resolution/summary.json` |

  `experiments/run_escalation.py` is the entry point, and `scripts/escalation_reports.py` generates the doc tables.
* **Service**. Results in `experiments/results/resolution/*.json` are served as `resolution-<name>` by
  `/api/experiments/{name}`, with the name guard extended.
* **UI** (`frontend/src/views/resolution/`), six read-only views backed by `summary.json`:
  * Resolution Matrix;
  * Hidden Difference;
  * Scale Penetration;
  * Reasoning Structure Inspector;
  * Disconnection Study;
  * Long-Run Compression.
