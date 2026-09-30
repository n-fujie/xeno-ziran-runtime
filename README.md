# Xeno / Ziran Philosophical Runtime

**Operational Shape Simulation Platform** — *Not a prediction. Explore possible transitions.*

A counterfactual transition-exploration runtime. It does not start from domains (people, markets, institutions,
states…). It simulates domain-neutral operations — difference, connection, ignition, transition, retention,
transformation, cut, penetration, return, reconfiguration, memory, reachability — detects the operational shapes
that recur, and only then (optionally) attaches interpretive labels. Philosophical claims and commitments can be
entered as structured interventions; the runtime is rerun and baseline vs intervention are compared.

## Quick start

Requirements: Python ≥ 3.11, Node ≥ 20.

```bash
make setup
```

```bash
make dev
```

Open http://127.0.0.1:3011 — the demo scenario (3,000 configurations) loads automatically; press **Run**.
Other scenarios: the scenario selector, or `/?scenario=benchmark-10k`, `/?scenario=small-600`. Optional
Japanese UI strings: `?lang=ja`.

Frontend development with hot reload: `make backend` in one terminal and `make frontend` in another
(Vite on :5173 proxies `/api` and `/ws` to :3011).

Container (Cloud Run compatible, listens on `$PORT`, default 8080):

```bash
make docker
```

```bash
make docker-run
```

## Using it

* **Views** — Network, Shape Space, Address Space, World Map, 3D Globe (spatial projections of the *same*
  configurations; the map is one optional projection, configurations without geo coordinates remain in all
  other views), Timeline, Compare, Philosophical Practice, and **Research** (Reduction · Minimal primitives ·
  Reason layer · Phases — read-only views of the experiment result files).
* **Runtime** — full (default) or the evidence-based MINIMAL runtime: `/?runtime=minimal`, or
  `"flags": "minimal"` when creating a session via the API.
* **Scales** — Macro → Global → Regional → Local → Configuration → Relation. Zoom with the wheel, click a
  cluster to drill down, or use the breadcrumb. Coarse scales show aggregated clusters and flows; fine scales
  load only the configurations and connections in the viewport.
* **Inspect** — click a configuration at Configuration/Relation scale: state, effective threshold, memory,
  wave origin/depth, reachable transitions, recent transitions.
* **Control** — run / pause / step / reset, speed, rewind to checkpoints (deterministic replay, including
  interventions), save / load a session, export CSV/JSON (configurations, connections, event log, metrics).
* **Practice console** — e.g.

  ```text
  remove concept human
  weaken commitment K2 by 0.5
  withdraw claim K4
  remove boundary B0
  change ignition threshold of configuration c42 to 0.6
  sever relation c12 -> c40
  introduce new memory condition on @2.1 decay 0.98 coupling 0.3
  compare baseline against intervention horizon 200
  apply
  ```

  Each command: traces dependencies → rescoring of commitments/entitlements → compiled changes to ignition
  conditions and gates → rerun of baseline and intervention from the same state and random stream (+ a
  noise-floor replicate) → comparison of reachability, ignition patterns, cuts, loops, concentration,
  branching, persistence, reconfiguration and commitment dependencies, highlighted directly in the graph.
  Parsing is a fixed grammar (`help` lists it); no language model is involved.

Visual encoding: ignition = brief white pulse · retention = brightness (difference / threshold) · memory =
decaying ring · penetration = particle travelling along a connection · return = amber expanding ring ·
branching = white ring at the source · cut = red connection breaking from the middle · new connection = green ·
reconfiguration = violet · boundary = blue-grey (reduced permeability). Hue is used only for these distinctions.

## Repository

```
backend/
  xzr/runtime     simulation runtime: state arrays, 11 operations, seeded engine, deltas, interventions
  xzr/shapes      shape detection: reachability, loops, fragmentation, bottlenecks, asymmetry, recurrence, …
  xzr/interpret   optional labels on recurrent shapes (never touches the runtime)
  xzr/practice    claims / commitments / entitlements, grammar parser, compilation to interventions;
                  terminology-free support graph (support.py)
  xzr/compare     baseline vs intervention (+ noise floor); trajectory distances for ablations
  xzr/reasonlab   closed loop world ↔ reasoning through an operational intervention gate; enabling conditions
  xzr/experiments primitive reduction study and reasoning non-redundancy suite
  experiments/    run_reduction.py; results/{reduction,reason,final_results}.json
  xzr/lod         intrinsic hierarchy (recursive Fiedler bisection), projections, viewport tiles
  xzr/scenario    scenario schema, world builder, import/export
  xzr/service     FastAPI + WebSocket, session worker threads, comparison job pool
  scenarios/      demo-3k (with practice layer), small-600 (no geo), benchmark-10k, reason-lab, benchmark-10k-reason
  tests/          125 tests · bench/benchmark.py · scripts/{make_fixtures,make_reports}.py
frontend/         React + TypeScript + deck.gl + Zustand; binary protocol decoder; 5 tests
docs/             ARCHITECTURE.md · BENCHMARK.md · LIMITATIONS.md · REDUCTION.md · MINIMAL_RUNTIME.md ·
                  REASON_NONREDUNDANCY.md · EXPERIMENT_RESULTS.md
Dockerfile · docker-compose.yml · Makefile
```

Checks: `make test` (pytest + vitest), `make lint` (ruff, mypy, eslint, tsc), `make bench`.
Experiments: `make experiments` (= `experiments-reduction` + `experiments-reason`), then
`python backend/scripts/make_reports.py` to regenerate the data tables in the docs.

Tests cover ignition, retention, penetration, return, transformation, cut, disconnection, reconnection,
reconfiguration, deterministic replay and rewind across interventions, overlay reversibility, intervention
comparison, shape metrics on constructed graphs, serialization (binary deltas, tiles, scenarios, practice),
the command grammar, the API/WebSocket, strict layering, and a scan that keeps domain vocabulary out of the
runtime, shape, LOD and comparison layers.

## Benchmark (10,000 configurations, 59,329 connections)

230.2 steps/s runtime-only (MINIMAL 228.4), 110.4 steps/s with continuous shape detection (MINIMAL 106.7);
~24 KB per step delta (vs 7.3 MB full state); scorekeeping loop +0.92 ms/step (+23%); WebSocket ~21 frames/s at
30 steps/s; 60 fps rendering at every scale including all 10,000 configurations in Shape Space (measured
2026-09-29; not re-measured this phase). Details and method: [docs/BENCHMARK.md](docs/BENCHMARK.md).

## Design commitments

Interpretation never changes simulation semantics; the runtime never sees human-readable categories; geography
is one projection among several; no semantic event is dropped for performance. Research results — which
primitives are necessary, and that the commitment/entitlement vocabulary is descriptive while the transition structure under it is what changes interventions:
[docs/EXPERIMENT_RESULTS.md](docs/EXPERIMENT_RESULTS.md). What the tool does not claim:
[docs/LIMITATIONS.md](docs/LIMITATIONS.md). Architecture and what was reused from `ziran-xeno-simulator`:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
