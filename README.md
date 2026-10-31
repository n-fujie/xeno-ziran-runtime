# XENO ZIRAN SIMULATOR — runtime repository (`xeno-ziran-runtime`)

> **Operational-Shape tools are not an implementation of a final ontology. They are experimental instruments for
> varying configurations, testing operational distinctions, comparing transformations, and measuring changes in
> subsequent possibilities.**

## What is this?

A simulation runtime in which differences ignite, propagate, are retained as memory, cut and reconfigure
connections across a field of configurations — plus the instruments to experiment on it: vary scale, topology,
memory, coupling, horizon, boundary and observation resolution; switch runtime mechanisms off; fork, remove,
reactivate or migrate retained history; and compare paired runs against a noise replicate, with the effective
configuration and provenance recorded for every result. It also contains the interactive simulator (web and iOS)
built on the same runtime.

## What can I run, and what does it test?

| command | tests |
|---|---|
| `xzr run resolution-escalation` | at which observation resolution (node → global) structural differences are systematic, as scale, topology, memory, coupling and horizon change |
| `xzr run history-reentry` | whether removing, restoring or moving a region's retained history changes reachability, generation, discrimination, intervention response and later configuration — and whether restored history re-enters |
| `xzr run boundary-scale-window` | whether a candidate distinction survives a closed boundary, another scale or another time window |
| `xzr run ablation` | which runtime mechanisms change downstream behaviour when removed |
| `xzr compare A B` · `xzr export R` | cell-by-cell change of detection status between runs · CSV export |
| `xzr study …` | the long published studies (resolution matrix, disconnection, triggers, adaptivity, clusters, compression, reduction, reasoning layer) |

Details per experiment — question, manipulated and fixed variables, measured outputs, what it does **not**
show: [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md). The few concepts the software uses:
[docs/THEORY.md](docs/THEORY.md).

## What it is NOT

* Not a validator of Operational-Shape Philosophy, Ziran, Xenoscience or any vocabulary — a detected difference
  is a difference in this simulation under the stated configuration, nothing more.
* Its results are experimental and analytical outputs under stated configurations — not real-world forecasts or
  predictive claims.
* Not a source of proof by absence: *not detected* is not *absent*; `EQUIVALENT` (shown within ±5 %) and
  `UNRESOLVED` (neither shown) are reported separately; *bit-identical* means no difference in the represented
  and measured state.
* Not a novelty detector: a residual or newly detectable difference is labelled as such; whether it is
  theoretically novel is an interpretation outside the software.
* Target-coupled validation of newly constructed variables or sensors is not supported (no such mechanism exists
  in the runtime).

## Quick start (experiments)

Python ≥ 3.11. No network, account or credential is needed.

```bash
git clone <repository-url> xeno-ziran-runtime && cd xeno-ziran-runtime
python3 -m venv .venv && .venv/bin/pip install -e "backend[dev]"
.venv/bin/xzr presets
.venv/bin/xzr run history-reentry          # ~30 s on 4 cores
```

Results go to `xzr-results/<experiment>/<run-id>/`: `config.json` (the effective configuration — what actually
ran), `result.json` (schema `xzr.result/1`: seeds, provenance, per-condition statuses, warnings, failures),
`summary.txt`, and the raw per-seed outputs. Runs never overwrite earlier runs. Exit code 0 = success,
1 = the run recorded failures, 2 = invalid configuration or usage.

## Representative experiment

`xzr run resolution-escalation` (12 paired seeds, 10 conditions, 5.2 min on 6 processes) — status of each
structural variant against the reference reasoning layer C at node · local · meso · macro · global resolution
(DETE detected, EQUI equivalent within ±5 %, UNRE unresolved):

```text
  reference
       C~  UNRE UNRE UNRE UNRE UNRE   noise replicate: never detected (in any of the 10 conditions)
        A  DETE DETE DETE DETE DETE   no reasoning layer
        E  DETE DETE DETE DETE EQUI   no eligibility tracking
        H  UNRE UNRE UNRE UNRE EQUI   no dependency records
across conditions (macro/global):
        A  configuration-sensitive — detected in 7 of 10 conditions
        E  configuration-sensitive — detected only in the reference
        H  configuration-sensitive — detected only at n = 3,000 and under strong coupling
```

Read it as: these distinctions exist in this runtime under some configurations and not others; which ones, and at
which resolution, is the result. It does not show that any of them is necessary in general.

## Research benchmark: where does an Active-Inference description hold?

[`research/post_active_inference/`](research/post_active_inference/) uses this runtime as a world and perturbation
engine to test when the descriptive units of a discrete Active Inference comparator (agent, boundary, generative
model, latent state, prediction error, free energy, policy) stay stable, and what happens to control when they do
not. It was run in three stages; the last one was pre-registered
([PREREGISTRATION.md](research/post_active_inference/PREREGISTRATION.md)) and run on 30 fresh seeds (55,680 runs).
Result ([REPORT_RESEARCH.md](research/post_active_inference/REPORT_RESEARCH.md)): the comparator's primitives lose
stability reproducibly and mostly gradually under **sensor and action-interface** disruptions, not under the tested
changes of world structure; where they fail, its **control fails with them** (no dissociation); inside the stable
regime its control advantage is small. Scope: one simulated world, one task, one comparator family — not a claim
about Active Inference in general.

## Heterogeneous Philosophical Operations (HPO)

[`backend/xzr/hpo/`](backend/xzr/hpo/) runs six operational series together in one world. They are engineering
proxies named after operations of Harman (withdrawal), Simondon (transduction), Whitehead (concrescence), Sellars
(picturing), Deleuze & Guattari (assemblage) and Luhmann (operational closure). They:

* ignite under configuration-dependent conditions (unobservable is never read as absent);
* act only through runtime intervention records;
* change one another's ignition conditions, rules, instruments, resources, history and partition;
* reconfigure the experiment's own settings inside a sandbox.

Every change is recorded as a causal event with before/after state. Experiments HPO-001/002/003 follow a frozen
protocol ([docs/HPO_PROTOCOL.md](docs/HPO_PROTOCOL.md)); results are in [docs/HPO_RESULTS.md](docs/HPO_RESULTS.md) and
in the viewer (`?view=hpo`). No result is evidence for or against a philosophical doctrine
([docs/HPO.md](docs/HPO.md)).

Body observation records (the open body-observation architecture of `?view=body`: provenance that cannot be rewritten silently,
observation status, a declared body graph) are described in [docs/TEOO.md](docs/TEOO.md). Its example data are SYNTHETIC test data.

```bash
.venv/bin/xzr hpo run hpo-002 --pilot --seeds 8
```

## Reproducibility, citation, license

Exact commands, determinism and its limits: [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md). Every run records
version, code hash, git commit (with a flag for uncommitted changes), Python/numpy versions, seeds and the
effective configuration. Cite with [CITATION.cff](CITATION.cff). License: MIT ([LICENSE](LICENSE)).

## The interactive simulator

Operational-Shape Dynamics (theory) › Xenoscience (scientific regime) › Ziran System (architecture family) ›
XENO ZIRAN SIMULATOR (this application). The simulator's operations fall into distinct regions: the **experimental
runtime** (configuration, intervention, execution, comparison, replay), the **research results** produced on it
(`backend/experiments/`), and the **Philosophical Runtime** (philosophical analysis: claims and commitments as
structured interventions). The Philosophical Runtime is one region of the simulator, not its enclosing category.

The public deployment (https://ziran-xeno-simulator.vercel.app, built by `backend/scripts/export_static.py`) exposes
the read-only research-result layer at `/`, and the interactive simulator at `/app/`, which runs entirely in the
visitor's browser tab (Pyodide in a Web Worker, no simulation server — [docs/WEB_RUNTIME.md](docs/WEB_RUNTIME.md); smaller
workloads, results not bit-identical to the desktop). Full-size runs use the local server, or the device itself in the
iOS app — [docs/IOS_APP.md](docs/IOS_APP.md)). The published result views are experimental and analytical
outputs and should not be interpreted as real-world forecasts or predictive claims.

It does not start from domains (people, markets, institutions, states…). It simulates domain-neutral operations —
difference, connection, ignition, transition, retention, transformation, cut, penetration, return,
reconfiguration, memory, reachability — detects the operational shapes that recur, and only then (optionally)
attaches interpretive labels. Philosophical claims and commitments can be entered as structured interventions;
the runtime is rerun and baseline vs intervention are compared.

### Running the interactive simulator

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

### Using it

* **Views** — Network, Shape Space, Address Space, World Map, 3D Globe (spatial projections of the *same*
  configurations; the map is one optional projection, configurations without geo coordinates remain in all
  other views), Timeline, Compare, Philosophical Practice, and **Research** (Reduction · Minimal primitives ·
  Reason layer · Phases — read-only views of the experiment result files). Resolution escalation adds six more
  views: Resolution Matrix · Hidden Difference · Scale Penetration · Reasoning Structure Inspector · Disconnection
  Study · Long-Run Compression.
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
  xzr/experiments primitive reduction study, reasoning non-redundancy suite, resolution escalation
                  (escalation/), history operations (history.py: fork, removal, reactivation, migration)
  xzr/hpo         Heterogeneous Philosophical Operations: registry, instruments, operations, interaction engine,
                  causal history, sandboxed reconfiguration, HPO-001/002/003 (docs/HPO.md)
  xzr/teoo        BODY / TOTAL OBSERVATION: sealed records of body observations (MEASURED / SYNTHETIC / RECONSTRUCTED_ESTIMATE /
                  CONCEPTUAL), observation status, an open body graph, CSV/JSON ingestion, an XB-TRO adapter (docs/TEOO.md)
  xzr/cli.py      the `xzr` command; xzr/results.py: result schema, provenance, compare, export
  xzr/presets     experiment presets (JSON) and configuration validation
  experiments/    run_reduction.py; results/{reduction,reason,final_results}.json
  xzr/lod         intrinsic hierarchy (recursive Fiedler bisection), projections, viewport tiles
  xzr/scenario    scenario schema, world builder, import/export
  xzr/service     FastAPI + WebSocket, session worker threads, comparison job pool
                  + operations.py: transport-independent session operations (HTTP and the iOS bridge)
  xzr/native      iOS in-process bridge (allowlisted routes, stream polling) and behavioural conformance
  xzr/_compat     numpy stand-ins for the scipy/pydantic surface the engine uses (iOS has neither) +
                  desktop reference hierarchies for the bundled scenarios
  scenarios/      demo-3k (with practice layer), small-600 (no geo), benchmark-10k, reason-lab, benchmark-10k-reason
  tests/          245 tests · bench/{benchmark,escalation_bench}.py · scripts/{make_fixtures,make_reports,escalation_reports,export_static}.py
frontend/         React + TypeScript + deck.gl + Zustand; binary protocol decoder; `npm run build:native` for iOS
docs/             THEORY.md · EXPERIMENTS.md · REPRODUCIBILITY.md · ARCHITECTURE.md · BENCHMARK.md · LIMITATIONS.md · REDUCTION.md · MINIMAL_RUNTIME.md ·
                  REASON_NONREDUNDANCY.md · EXPERIMENT_RESULTS.md · RESOLUTION_ESCALATION.md ·
                  REASONING_CONFIGURATION_MAP.md · DISCONNECTION.md · SCALE_PENETRATION.md · LONG_RUN_COMPRESSION.md
ios/              iOS app (SwiftUI + WKWebView + embedded CPython running this engine on the device);
                  see docs/IOS_APP.md
Dockerfile · docker-compose.yml · Makefile
```

Checks: `make test` (pytest + vitest), `make lint` (ruff, mypy, eslint, tsc), `make bench`; CI runs the same
plus a CLI smoke run and a two-run reproducibility check (`.github/workflows/ci.yml`).
Experiments: `make experiments` (= `experiments-reduction` + `experiments-reason`), then
`python backend/scripts/make_reports.py` to regenerate the data tables in the docs. Resolution escalation:
`make experiments-escalation` (several hours; resumable), `make reports-escalation`, `make bench-escalation`.

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
