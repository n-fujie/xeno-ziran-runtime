# XenoBody / XB-TRO — Operational-Shape Robotics Simulator (Research Beta)

XenoBody is a research environment inside XENO ZIRAN SIMULATOR. It runs a **simplified planar body** (a human-like and a machine-like
preset), lets local **observation devices** cut that body in different ways, lets you **intervene**, and runs **experiments** whose
records can be stored, exported, repeated, re-observed and re-entered. This page states what it is, how it works, what was checked,
and — as importantly — what it is not.

## Scope, stated once

* The body is a limited planar N-link model (four links) with **nominal parameters**. Nothing is measured physiology and nothing is
  the property of a particular robot. **No physical robot and no human participant was used; nothing has been validated against a
  real body.**
* The simulator's own state is the **model reference state**. It is not an observation of anything. Observation models produce
  separate outputs (sampled, delayed, noisy, with dropouts and blind windows). A third kind of value, an **estimate**, is either the
  controller's own belief or a quantity computed from observation outputs only. The interface draws the three apart and never blends them.
* Xeno-14 principles are **experimental conditions**. No sign of effect is assumed. A statistical difference is not a philosophical
  conclusion, and "not detected" is not "absent".
* MO / DO / ZCA / MS are **limited instances** over this body model. In the Ziran System specification's own status MO and MS are
  NOT IMPLEMENTED and DO and ZCA are PARTIAL. Nothing here completes them.

## Architecture

| layer | where | notes |
|---|---|---|
| computation | `backend/xzr/xbtro/` | pure numpy, deterministic, imports nothing else from `xzr` (checked by `tests/test_layering.py`) |
| operations | `backend/xzr/service/xbtro_ops.py` | transport-independent: validation, limits, workspaces, jobs, history, live bodies; one route table |
| transports | `service/app.py` (HTTP), `native/bridge.py` (iOS and the in-tab Pyodide runtime) | both serve the same table; jobs use the shared job table and the cooperative loop |
| interface | `frontend/src/views/xbtro/` | React + three.js 0.169.0 (lazy chunk), SVG charts; data comes from the runtime |

Modules of `xzr/xbtro/`: `config` (presets, interventions, validation), `engine` (body simulator), `observation` (devices),
`tro` (identifiability, boundary transformation, reconfiguration), `coupling`, `velocity`, `metrics`, `stats`, `xeno14`, `experiments`,
`fragility` (experiment G), `ziran` (ZCA / DO / MO / MS instances), `records` (JSON/CSV, digests, history), `history` (repeat, re-observe,
re-enter), `live` (a body advanced in small steps), `verification` (numerical studies).

## The body

N-link planar Lagrangian chain (exact mass matrix) with joint viscoelasticity, a muscle drive (first-order activation), an ankle torque
limited by the base of support, friction, pushes. **Operation lines** (passive mechanics, proprioceptive / vestibular / visual /
tactile / cue sensing, reflex, central ankle / hip / cue commands, tonic core, breathing, metabolic supply, slow gain adaptation) each
have a time scale, an ignition condition on delayed noisy sensed signals, a hold time, a resource cost and an observability. Lines
fire, hold, lapse and re-fire; commands from different lines add per joint, so conflicts and couplings can be read from the record.
Slow states (fatigue, energy, adaptation gain, tension, sediment) are retained and can be handed to a later experiment.

## Numerics

The plant is integrated by explicit RK4 with the muscle drive held over each control step; `task.substeps` refines the plant step
without changing the controller. `task.integrator` also offers semi-implicit and explicit Euler for comparison.

**A-priori check (sufficient, not necessary).** At the upright pose the passive plant is linear, `x' = A x`. One sub-step maps `x` to
`Φ x` with `Φ = I + Ah + (Ah)²/2 + (Ah)³/6 + (Ah)⁴/24` (RK4), `I + Ah` (explicit Euler) or the semi-implicit map. The step is stable
for the passive plant iff the spectral radius of `Φ` is at most 1 (for RK4 this is the classical `|R(λh)| ≤ 1`, about `λh ∈ [−2.78, 0]`
on the real axis), checked for every co-contraction value in `[0, 0.9]` (the engine clips it there). A configuration that passes
cannot blow up through its passive dynamics. It is **not necessary**: a refused configuration may run stably at the co-contraction it
actually uses (`verification.convergence_study` runs refused configurations anyway: at the nominal co-contraction they stay bounded, at
0.9 they diverge, as predicted). And it does **not** cover feedback delays, gains or contact switching: a passed configuration can still
have an unstable closed loop. Those are caught by run-time criteria.

**Run-time diagnosis keeps three outcomes apart.** *Numerical divergence* (non-finite values, joint rate above 60 rad/s, torque above 40×
the largest `tau_max`): the run is flagged `diverged`, scored on nothing, and never reported as a fall. *Physical fall* (a segment angle
or the COM beyond the recoverable range): a result. *Unstable closed loop*: reported as growth of late over early sway (defined only for
bodies still standing). A numerically unstable run can end as a fall before the divergence criteria trip (observed for explicit Euler at
co-contraction 0.9); the a-priori check is therefore the primary guard, the run-time criteria the second.

The human-like preset uses 2 plant sub-steps at dt = 0.01 s; the machine-like preset uses dt = 0.005 s (its loop latencies are 4–15 ms)
with 2 sub-steps. Time-step convergence (noiseless runs): refining the human plant step changes the COM trajectory by 2·10⁻⁵ m RMS
(2 → 8 sub-steps), halving the control step by 5·10⁻⁴ m; the machine-like numbers are in `artifacts/xbtro/final/SUMMARY.md`.

## Metrics and tolerances

* **Recovery / settling are time-to-event with censoring.** The time is `NaN` where the event did not happen inside its window
  (the window ends at the next protocol event), with a status: *achieved*, *not-achieved-in-window*, *fell*, *diverged*. The window
  length is never recorded as a time. For statistics a **restricted mean** (`*_rmst`: the time where achieved, the window length
  otherwise; `NaN` for diverged runs) is used and named as such, next to the fraction achieved.
* Recovery is searched from the time of the largest deviation, so a body that the push has not yet moved is not "recovered".
* **Tolerance bands are fixed in advance** from the nominal body's steady fluctuation on tuning seeds (1000–1031):
  `band = max(3 × detrended steady COM SD, 0.25 × smallest commanded step)`, rounded up to the next millimetre
  (`metrics.calibrate_band` reproduces it; a test checks it). Registered: **human-like 9 mm, machine-like 9 mm.** Experiments use
  other seeds (5000…; the replication 7000…). **Note on 13 mm:** an intermediate controller tuning gave 13 mm for the human-like body;
  the controller was then retuned on the tuning seeds and the same rule gave 9 mm. No band was ever set from final-seed results. The
  effect of using 13 mm is reported as a sensitivity analysis (`SUMMARY.md`), the registered value is unchanged. **The human-like recovery
  classification is sensitive to the band**: with 9 mm the human-like body recovers inside the window in 7 of 12 seeds (restricted mean
  1.58 s in B's control), with 13 mm in all 12 (0.89 s). Conclusions about human-like recovery time are therefore conclusions under the
  registered band. (The sensitivity run varied the human-like band only; the machine-like band was not varied.)
* Comparisons are paired by seed (common random numbers; interventions never touch the random streams). Effects are paired `d`, a
  sign-flip permutation test (exact up to 12 pairs) and a bootstrap interval; label thresholds (Benjamini–Hochberg `q < 0.05` over the
  whole table, `|d| ≥ 0.8`) are fixed in advance. `stats.design_note(n)` states what `n` seeds can resolve (12 seeds: about 0.81).

## Experiments

A–F keep their defined purposes; G, M, R, S, V were added independently.

| id | question |
|---|---|
| A | Observation-Cut Transformation: motion only / + muscle activity and contact / dynamic revision — what is identified, what stays unobserved and why |
| B | Sensorimotor Coupling: feedback delay, block, reconnection; couplings classed by interventional evidence, not correlation |
| C | Fragility Transfer: the fourteen Xeno-14 conditions and pairs against a matched control; BH-controlled labels; ignition tracked |
| D | Operational Velocity: ten separate measures; established / varied / lapsed, with line-stopped, observation-lost, description-inapplicable and censored kept apart |
| E | Adaptive Observation: automatic revision of the observation configuration for each kind of hidden body change |
| F | Human–machine comparison against one stated consequence |
| G | Directional Fragility Transfer (independent check): push met at rest, both directions, recovery region, saturation, lines that stop igniting, later reachability, ablation of the rule line, declared cost separated |
| M | MO-style reach policy (limited instance) with distributed observation |
| R | Sensitivity of the Fragility Transfer matrix to seeds, mass, loop latency, sensor noise, push strength |
| S | MS-style path comparison for one consequence (vector of measures; no single speed score; the stopped response is one path) |
| V | Numerical verification (stability radii, convergence, eight conditions × two presets × two protocols) |

Final records (JSON and CSV, with the code commit) are in `artifacts/xbtro/final/`; `SUMMARY.md` is generated from them by
`backend/scripts/summarize_xbtro_final.py`. `backend/scripts/run_xbtro_final.py` regenerates them.

## Xeno-14 fidelity

Names and definitions come from `ziran-xeno-simulator` (`src/domains/body.ts`, `embodied/xeno14/principles.py`); tests compare them with the
source files when present. For this planar body: **8 translated, 3 partly translated, 3 proxy-only** (minimal-approach-distance,
fingertip-tension, long-duration-sedimentation: the body has nothing the rule acts on; their effects say nothing about the principle).
Each principle's source rule, its planar translation and the gap are in `xeno14.FIDELITY` and shown in the Scope tab. A principle whose
ignition condition is never reached (anti-collapse-posture in these protocols) is reported as *never ignited*, not as *no effect*.

## Ziran System

`xzr/xbtro/ziran.py` quotes the MO / DO / ZCA / MS definitions verbatim from `pa-philosophy-in-audit/data/ziran.ts` (a test compares the text)
and implements limited instances: **ZCA** addresses with the specification's fields `⟨N, ID, t, s, b, v, p⟩`, four field states and no equivalence
function; **DO** per-source verdicts kept side by side, conflicts preserved, nothing fused; **MO** a cost-aware revision policy that keeps reach as a
vector, measures its own perturbation and retracts what does not pay; **MS** a Pareto comparison of executable paths under measured constraints.
`STATUS` in that module says per responsibility what the instance covers and what it does not. The connection to the TypeScript Ziran code
(`ziran-xeno-simulator/src/ziran/system.ts`) is by analogy of mechanism only (conditional start/stop ≈ line ignition and lapse; historical
reinsertion ≈ slow-state re-entry); no code is shared.

## Interfaces and safety

* HTTP routes `/api/xbtro/…` and the native bridge serve one table (`xbtro_ops.ROUTES`). Records can be exported as JSON or CSV; an import
  is checked against the record's own digest.
* **Public servers:** the routes are **off by default** under `XZR_PUBLIC=1` (the public site offers the in-browser edition instead);
  `XZR_XBTRO=1` turns them on with smaller limits. Ownership (a workspace belongs to the capability that created it, others get "no such …"),
  rate limiting of job-starting routes, body size / depth / string bounds, per-workspace job limits, record and body limits, `n_seeds`,
  `horizon`, `seeds × steps` and observation-model bounds are enforced and named (`XZR_XB_*`). Parameters are allowlisted per experiment.
  `tests/test_xbtro_security.py` covers cross-owner access to every resource type, limits, oversized and nested input, tampered imports.
* No route evaluates code, runs a subprocess or touches the filesystem (a test reads the module source for such calls).

## What was checked, and where

| item | local server (HTTP) | in-tab Pyodide | iOS device |
|---|---|---|---|
| body, stepping, observation, interventions | checked | checked | **not checked** |
| experiments A–G, M, R, S, V as jobs | checked | checked (cooperative, no threads) | not checked |
| repeat / re-observe / re-enter | checked | checked | not checked |
| same-condition equality | S1 sequence and the experiment digests equal across HTTP, bridge and Pyodide | | |

The in-tab and desktop runs use different Python and numpy builds (3.14 / 2.4.6 wasm and 3.12 / 2.5.3); values agree at the recorded resolution
(6 significant digits) and digests agree. A digest taken over 6 significant digits does not claim bit identity. The iOS app embeds the same
bridge module, but no device was available: **no behaviour is guaranteed on iOS.**

## Limitations

Planar, four links, nominal parameters; proportional controllers without integral action (a steady offset of up to a quarter of a commanded
shift is accepted by the registered band); the 14 Xeno-14 translations are planar approximations; observation models are simple signal models;
`EXPERIMENTS` G, R and V are long (minutes on a desktop, longer in the browser: run them with fewer seeds there); live runs saved as record `L`
cannot be repeated by the repeat operation (their log is stored); the coupling reconstruction and the velocity measures have the power stated
in each record's `design`.

## Defects found and fixed during development (kept, not hidden)

Explicit-integration instability of light links with large joint damping (machine-like preset fell without any disturbance) — fixed by an a-priori
check, sub-stepping, and retuning; recovery/settling metrics saturated at the window cap — replaced by censored time-to-event with statuses; a
recovery search that started at the push and counted a not-yet-moved body as recovered; the noise-halving of the observation reconfiguration reset
to a constant instead of halving the current value; the Xeno-14 rule lines ignored `enabled = false` (ablation had no effect); an
initial Fragility Transfer analysis that pushed the body during movement, so that differences in body state at push time appeared as weakening
(first version of G, kept in `artifacts/xbtro/` history; state-matched pushes replaced it); Experiment E duplicated A; two candidates adding the
same observation model crashed a revision round; a stability ratio of two floating-point residues made one verification digest platform-dependent.
