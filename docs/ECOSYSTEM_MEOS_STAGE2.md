# XENO ECOSYSTEM — MEOS-0, second stage

Branch `feat/meos-ecosystem` (worktree `xeno-ziran-runtime-meos`), engine `meos-0.2`, on baseline `ec9667e`. Local only: not pushed, not deployed, not merged.
The first stage (`docs/ECOSYSTEM_MEOS.md`) is unchanged in what it claims; this document records what the second stage added, what it measured, and what it did not do.
Every number below comes from `docs/ecosystem/experiments_stage2.json` (written by `backend/scripts/meos_experiments_v2.py`; each row is a seeded, deterministic run identified by
its result and trace digests). Outcomes are properties of the formal model MEOS-0. They are not claims about any physical or biological ecosystem.

## 0. Which function exists in which branch

| function | baseline `ec9667e` | R3 (`feat/r3-confirmatory-reproduction`) | MEOS (`feat/meos-ecosystem`) |
|---|---|---|---|
| XENO ZIRAN SIMULATOR runtime, 264 stored runs, Phase 3 / Phase 4 files | yes | yes (unchanged) | yes (unchanged; 264/264 replay checked, section 8) |
| R3 confirmatory reproduction | no | yes | **no — not integrated** (this branch does not contain it) |
| MEOS-0 engine, `/api/meos`, ecosystem view | no | no | yes |
| MEOS stage-two additions (traces, M2, Philosophical operations, Address Domain interventions, observation separation, new experiments, research-device layer) | no | no | yes |

Nothing from R3 is claimed as retained here. The MEOS baseline result digest `b4cf1e522e8bee460eab30ee2a3f86ffd703a3f7969dc21271cf0240aa09adc5` is unchanged by stage two (every new feature is absent from a default configuration; frames only gain `address` while a fault is active; traces are a separate block with their own digest).

## 1. What was added to the engine (`backend/xzr/meos`, `meos-0.2`)

* **Operational traces** (separate block `traces`, `trace_digest`, `full_digest`; the status never reads them): resource consumed / renewed / flow / total, power reserve / intake / draw / balance, renewal requests and events, A1 energy, A1/A2 activity and firings, interaction strength, reconfiguration signal, differentiated stimuli, history contribution and trace per entity, sensor radius and speed, Address Domain integrity, cycles in window, target margin (`target_margin >= 0` iff ACTIVE). `causal_path` reports, for an intervention, the first departure of each quantity from the counterfactual run, the persistence-failure tick, the collapse tick, the trigger and the chain.
* **Observation separated from operation** (`analysis.observe`): `operational_state`, `observed_state`, `observability_status` (`OBSERVABLE`, `INSUFFICIENT_TEMPORAL_RESOLUTION`, `INSUFFICIENT_SPATIAL_RESOLUTION`, `REGION_EXCLUDES_ACTIVITY`, `AGGREGATION_SCALE_MISMATCH`, `OBSERVATION_WINDOW_MISMATCH`, `COMBINED_LIMITS`, `OBSERVATION_OVERESTIMATES`) and the limiting parameters (found by relaxing each parameter to full resolution). Five parameters: sampling interval, spatial lattice stride / offset, region, aggregation scale, window.
* **M2 sensing** (`m2`: none / direct / delayed / noisy, weight): A1 also senses the alteration M2 that A2's reconfiguration leaves. Absent by default.
* **History access per entity** (`history.access`), **renewal efficiency** (`environment.renew_efficiency`, `entities.A2.renew` settable), **Address Domain interventions** (`ADDRESS`: loss, reassign, fragment, collision, partial, restore).
* **First-stage Philosophical operations** (`phil.py`, optional block `phil`): expression, scorekeeping, norm-sensitive revision, inferential transition, correction after mismatch, realised as couplings of A1 and A2 (no language model). The closed path: environmental event → body detection (A1 compares a firing attributed to A2's renewal with its adapting expectation) → expression (a claim sent through a channel with its own delay and noise, paid for from the finite power reserve) → other-system response (A2 checks the claim against its own measurement of how much of a renewal reached the field) → score update (both ledgers) → subsequent operational change (A2 raises its renewal amount by the inferred shortfall if the claimant's reliability meets the norm; A1 withholds an unreliable kind of claim). Modes: `none`, `expression` (claims made and paid for, nobody answers), `scorekeeping`, `revision`.

## 2. Experiments, seeds, conditions and results

Seeds are stated per experiment; the same seeds and period are used for every condition inside one experiment. "Persist" = status ACTIVE at the end of the run.

### 2.1 Resource flow, energy balance and causal path (seed 1, default configuration, 240 ticks)

| intervention | first departing quantity (tick) | persistence failure | collapse | recovery |
|---|---|---|---|---|
| A2 removed at 100 | interaction strength (100) | 121 | 144 | none |
| history removed at 0 (finite power) | history contribution of A1 (2) | 0 | 159 | none |
| interaction channel cut at 100 | interaction strength (100) | 126 | 149 | none |
| resource renewal removed at 0 | power balance (2) | 0 | 114 | none |
| A2 address lost at 100 | interaction strength (100) | 121 | 144 | none |
| scale 1.5 at 100 | A1 differentiated stimulus (100) | 126 | 149 | none |

The status is derived from counted cycles; the dependency label is an explanation after the fact and is not what decides it.

### 2.2 History × gradient × power, eight conditions, seeds 1–10

| history | gradient | power | operational state | seeds persisting | cycles | cumulative energy use | renewals |
|---|---|---|---|---|---|---|---|
| on | on | finite | ACTIVE | 10/10 | 47.0 ± 0.0 | 119.08 | 143.0 |
| off | on | finite | **COLLAPSED** | 0/10 | 19.6 ± 5.9 | 100.76 | 61.8 |
| on | off | finite | ACTIVE | 10/10 | 47.0 | 119.08 | 143.0 |
| off | off | finite | ACTIVE | 10/10 | 47.0 | 119.08 | 143.0 |
| on | on | unlimited | ACTIVE | 10/10 | 47.0 | 71.50 | 143.0 |
| off | on | unlimited | **MIXED** | 9/10 | 42.5 ± 13.5 (first collapse at tick 59 in the failing seed) | 64.80 | 129.6 |
| on | off | unlimited | ACTIVE | 10/10 | 47.0 | 71.50 | 143.0 |
| off | off | unlimited | ACTIVE | 10/10 | 47.0 | 71.50 | 143.0 |

(Throughput, A1/A2 activity, target-held share, recovery possibility and the preserved target are in the JSON.) Result: history is **necessary only where there is a resource gradient and the power reserve is finite**; with unlimited power it is not necessary but one seed in ten still fails without it (a seed-dependent, non-deterministic-looking dependence that is deterministic per seed); without a gradient history is never necessary. Nothing in this table is reversed. With 5 seeds (Studies tab, default) the unlimited / history-off / gradient-on row shows 5/5, which is the seed variance the 10-seed run exposes — the 10-seed table is the recorded one.

**Where history is necessary** (power charge rate × reserve capacity, 3 seeds, 30 cells): history necessary in 3 cells (charge 0.4 at every capacity), persists without history in 15, collapses either way in 12. Necessity is confined to a narrow band of the recharge rate and does not depend on capacity in the range tested.

### 2.3 Minimal operational configurations (full 2^9 search; seeds 1–3, 200 ticks)

Operation: "recursive cycle sustained (status ACTIVE at the end of the run)". Admissible reductions: A2, resource gradient, history, interaction channel, resource sensor, alteration sensor, environmental persistence, feedback, resource renewal. Scale 1, no observation (operational state). All 512 subsets were run; inclusion-minimality was checked against all of them.

| power | subsets preserving | minimal sets | cardinality | retained |
|---|---|---|---|---|
| finite | 3 | 1 | 7 | A2, environmental persistence, feedback, interaction channel, resource renewal, alteration sensor, resource sensor |
| unlimited | 8 | 1 | 6 | the same without resource renewal |

* Every proper subset of each minimal set fails; each set was checked against its single removals.
* **History + gradient simultaneous removal preserves the status** (it is inside the minimal set's complement), but **not the same operation**: against the unreduced run, the share of cycles with history re-entry falls from 1.0 to 0.0 (period median 5 and the four-link chain unchanged). Under finite power, history alone removed does not preserve (non-monotone: history removed with the gradient preserves, history removed alone does not). So "preserves the status" and "preserves the same operation" differ, and the table reports both.
* Seen through an observation: with sampling interval 1 the observed minimal set is the same; with interval 2 **no configuration appears to preserve the operation** (the observation cannot resolve it).

### 2.4 Observation (seed 1, baseline run, 47 true cycles)

full resolution — OBSERVABLE; interval 2 and 4 — observed COLLAPSED, INSUFFICIENT_TEMPORAL_RESOLUTION; spatial stride 2 — COLLAPSED, INSUFFICIENT_SPATIAL_RESOLUTION; region excluding the habitat — COLLAPSED, REGION_EXCLUDES_ACTIVITY; aggregation 6 and 24 — ACTIVE (39 and 10 cycles resolved); window 6 — DEGRADED, OBSERVATION_WINDOW_MISMATCH; window 12 — ACTIVE; interval 2 + stride 2 — COLLAPSED, COMBINED_LIMITS (no single relaxation restores agreement). An observation that cannot resolve the operation is a limit of the observation, not evidence that the operation is gone.

### 2.5 XenoBody boundary experiments (seeds 1–3)

| boundary change | operation persists (all seeds) | note (seed 1) |
|---|---|---|
| none | yes | coupling 0.248, renewed 63.1 |
| observation region excludes A2's habitat | yes | observed state ACTIVE, `REGION_EXCLUDES_ACTIVITY` flag |
| coupling cut (interaction channel) | no | coupling 0, collapse |
| resource-exchange boundary: renewal feedback | no | renewed 0 |
| resource-exchange boundary: power recharge and source renewal | no | renewed 20.5 |
| history-access boundary: A1 only | yes | mean threshold reduction 0.119 |
| history-access boundary: A2 only | no | |
| history-access boundary: neither | no | threshold reduction 0 |
| Address Domain: arena radius 2 | yes (operationally) | observed COLLAPSED |
| Address Domain: A2 reassigned to (9, 6) | no | coupling 0.0003 |

**What first closes in B3:** of 64 candidate bodies exactly one persists: B1 plus {A2, feedback, history, interaction channel, resource renewal, alteration sensor} — six relations, closing six legs; nothing smaller than B3's complete set of those relations persists. B1 (A1 with its resource sensor) alone does not.

### 2.6 Collapse / recovery phase (resource pulse, 25 amounts 0–6 at step 0.25, seeds 1–5)

| scenario | no recovery (below) | recovery | no recovery / re-collapse (above) | monotone |
|---|---|---|---|---|
| interaction cut 100–150 | 0, 0.25 | 0.75–3.5 (0.5 is seed-dependent) | 3.75–6 (no recovery) | **no** (a seed-dependent amount at 0.5) |
| A2 removed 100–150 | 0 | 0.25–3.5 | 3.75–6 (overshoot / re-collapse) | yes |

Seed 1 at pulse 0.75 (cut): latency 11 ticks, 199 ticks sustained, no re-collapse, period cv 0. The recovery band is bounded above: **too much resource also prevents recovery** (an excess pulse), so the dependence of recovery on the pulse is a band, not a threshold. Latency, sustained duration, post-recovery stability, history reconstruction and energy reserve at recovery are recorded per seed in the JSON.

### 2.7 SSS phase regions (3 scales × 4 sizes × 8 speeds = 96 points, seeds 1–3)

ACTIVE 16, COLLAPSED 78, metastable 2; recovery-capable points 1; observation-sensitive points 16. Scale 0.5 is ACTIVE at sizes 0.5 and 1 (speeds 0.5–1.1 and 0.5–2 respectively) and collapses at sizes 1.5 and 2; scale 1 is ACTIVE only at size 1 and speeds 0.9–1.1 (metastable at speed 0.75 and 1.5, the latter recovery-capable); scale 1.5 collapses everywhere tested. The active region is narrow in the model's own units; it is not a claim about any physical scale.

### 2.8 Address Domain interventions (17 cases, seeds 1–5; fault at 100, restored at 150, optional pulse after; the cases without a qualification gave the same outcome in all five seeds)

* **Loss** of A1: collapses and does not recover, even with restoration and a pulse. Loss of A2 (or both): collapses, restoration alone does not recover it, restoration **plus a pulse** does.
* **Collision** of A1 with A2's address: the operation continues (ACTIVE throughout). Collision of A2 (or both): ACTIVE under the fault, **collapses after restoration**, recovers with a pulse (a reversal worth noting: restoring the address harmed the run).
* **Fragmentation** of A2's addressable window: 50 % and 75 % — ACTIVE throughout (null) in all five seeds; 25 % — **seed-dependent** (some seeds stay ACTIVE, the others collapse and do not recover).
* **Partial addressability** (A1 or A2): at 25 % and 50 % of steps it collapses in every seed and does not recover with restoration or a pulse; at 75 % it collapses in every seed but is **seed-dependent in recovery** (A2: one seed in five recovers with restoration plus a pulse; A1: two seeds in five recover with restoration alone).
* **Reassignment** of A2 to (9, 6): collapses; **returning** it to (5, 6) does not recover.

### 2.9 M2 connected to a follow-on operation (16 connection conditions × 7 scenarios, seeds 1–5)

* Unperturbed, finite power: direct and delayed connections at every weight make **no difference in outcome**; a noisy connection (σ 0.05) at weight ≥ 1 **harms** (4/5 seeds persist, cycles 47 → 39.6–43.6).
* Interaction cut 100–150 with a pulse: direct and delayed — no difference; noisy at weight 2 reduces cycles 61 → 48.
* Interaction cut, no pulse: none/direct/delayed — collapse, no difference; **noisy at weights 2 and 4 rescues** all five seeds (cycles 20 → 41 / 47.6). Noise supplies what the signal lacks.
* Scale 1.5: direct raises cycles from 2 to 3 but never rescues; **delayed (3 ticks) at weight 2 rescues 2/5 and at weight 4 rescues 5/5**; noisy at 2 rescues 3/5, at 4 5/5. The connection is neither uniformly helpful nor uniformly harmful: its effect depends on the perturbation and on the form of the connection.
* Renewal efficiency 0.7 at 100 and A2 50 % addressable from 100: direct and delayed — no rescue; noisy at weights 2 and 4 — 4/5 seeds persist. Unlimited power, unperturbed: no difference except a small harm from noise.

### 2.10 Philosophical operations, first stage (4 modes × 6 environments × 3 channels, finite and unlimited power, seeds 1–5)

Environment events are changes of the renewal efficiency (stable, step to 0.85, step to 0.7, drift to 0.7, drift to 0.5, shift–restore–shift). Seeds keeping the operation, out of 5:

* **Finite power:** every mode (none, expression, scorekeeping, revision) fails in every perturbed environment (0/5) and persists in the stable one (5/5). The operation costs power from a reserve that the perturbation is already draining, so **revision does not rescue under finite power**, and no mode is harmed in the stable environment either.
* **Unlimited power, clean channel:** step 0.85 — all modes persist (5/5; the operation is unnecessary); step 0.7, drift 0.5 — none, expression, scorekeeping 0/5, **revision 5/5**; drift 0.7 — 1/5 without revision, **5/5 with it**; shift–restore–shift — 0/5 without, 4/5 with revision. Noisy and slow channels leave revision at 5/5 (4/5 for the noisy shift–restore–shift).
* Expression alone and scorekeeping alone never help (the operation changes nothing until it is acted upon). In a stable environment the module fires on false alarms (about 4 expressions by tick 170 at seed 1) and spends power on them. It becomes needed only under unlimited power and a sufficiently strong environmental event, is unnecessary for a mild one (0.85), and re-fires after restoration (shift–restore–shift).

These results say that, in MEOS-0, a norm-sensitive revision coupling can be needed, unnecessary or inert depending on the power regime and the environment. They do not show that philosophy "works": the mechanism is a small operational coupling and the result is conditional.

## 3. The interface (`frontend/src/views/ecosystem`)

* **EXPERIMENT tab:** observation controls (interval, spatial stride, aggregation, window, region, full-resolution reset) with operational / observed / observability display; connections (M2 → A1 mode and weight, philosophical mode and channel); intervention list extended with `ADDRESS` (loss, reassign, fragment, collision, partial, restore); a live "Research device" readout; the space-to-function table.
* **STUDIES tab (new):** nine experiment buttons (history × gradient × power, where history is necessary, all minimal configurations with finite / unlimited power, XenoBody boundaries, recovery phase for two scenarios, SSS phase regions, Address Domain, M2 connection, Philosophical operations) that run the real engine on the current configuration and print the tables the engine returned (`studies.ts` only reformats them).
* **DATA tab:** trace charts (resource flow, energy / power balance, A1/A2 activity, interaction strength, history contribution, target margin, Philosophical boost and reliability).
* **Research device in the scene** (`researchDevice.ts`; each is a pure function of record, tick and observation, tested without a renderer): Observation Array dishes turn toward the observed region and light in proportion to the cells it covers, flashing on sampled ticks; Boundary Layer posts at the operational boundary (raised while closed, lowered per open channel); resource-pulse ring at the injected cell; recovery halo (bright after a recovery, dim while collapsed); a selected-chamber ring; the Philosophical module in the third expansion bay (lamps for expression / response / score / revision, a renewal-boost bar, a reliability ring and a travelling spark during the channel delay) — present only in a run that configures one. Camera presets added: `array`, `socket`. Deep links: `?preset=recovery-demo&horizon=360&phil=revision&cam=socket&tick=165`.
* Not state-linked and therefore not animated: the Research Core, gantry arches, rails and towers (static architecture). "Active chamber indication" is the selected-chamber ring over the outcome of a recorded reduction trial; it is **not** a live indicator of which trial is executing (the server computes the trials in one request).

## 4. Visual comparison with the references (second pass; see section 9 for a later graphics pass)

Fixed camera presets (`overview`, `core`, `habitat`, `subsurface`, `array`, `socket`) and fixed deep-link states are used so that captures are comparable between stages. Statistics (`backend/scripts/visual_compare.py`; luminance histogram, edge density, spatial frequency, occupied-area ratio, depth proxy, silhouette density, with the first-stage statistics kept) are crude proxies. **They never establish that a picture matches a reference.** Stage-one values for the same views are in `docs/ecosystem/visual/stage1/`. Results of this stage are in `docs/ecosystem/visual/metrics.json`; the references are the four supplied images (their statistics are stored, the images are not).

| view | first-stage distance to nearest reference (stage 1 → 2) | lum | edge | sf-hi | occ | depth | sil |
|---|---|---|---|---|---|---|---|
| 01-overview | 0.619 → 0.609 (ref 2) | 0.130 | 0.180 | 0.140 | 0.396 | 0.616 | 0.366 |
| 02-habitat | 0.473 → 0.491 (ref 2) | 0.287 | 0.108 | 0.064 | 0.938 | 0.841 | 0.011 |
| 03-research-core | 0.238 → 0.236 (ref 2) | 0.357 | 0.159 | 0.074 | 0.873 | 0.891 | 0.074 |
| 04-meos0-active | 0.449 → 0.468 (ref 2) | 0.288 | 0.106 | 0.062 | 0.938 | 0.843 | 0.010 |
| 05-meos-collapse | 0.412 → 0.426 (ref 2) | 0.280 | 0.108 | 0.068 | 0.925 | 0.829 | 0.018 |
| 06-xenobody-boundary | 0.489 → 0.507 (ref 2) | 0.289 | 0.109 | 0.065 | 0.937 | 0.845 | 0.013 |
| 07-history-overlay | 0.473 → 0.493 (ref 2) | 0.288 | 0.106 | 0.062 | 0.938 | 0.843 | 0.010 |
| 08-subsurface-laboratory | 0.353 → 0.348 (ref 2) | 0.319 | 0.107 | 0.083 | 0.867 | 0.779 | 0.060 |
| 09-observation-array | new → 0.694 (ref 2) | 0.101 | 0.056 | 0.043 | 0.264 | 0.502 | 0.249 |
| 10-philosophical-socket | new → 0.656 (ref 2) | 0.130 | 0.067 | 0.047 | 0.342 | 0.560 | 0.242 |
| 11-resource-pulse | new → 0.419 (ref 2) | 0.281 | 0.108 | 0.066 | 0.924 | 0.837 | 0.018 |
| 12-boundary-open | new → 0.429 (ref 2) | 0.283 | 0.101 | 0.062 | 0.938 | 0.832 | 0.010 |
| 13-recovered | new → 0.454 (ref 2) | 0.293 | 0.107 | 0.060 | 0.938 | 0.852 | 0.010 |
| reference 1 | — | 0.795 | 0.418 | 0.322 | 0.924 | 0.772 | 0.207 |
| reference 2 | — | 0.273 | 0.301 | 0.208 | 0.736 | 0.828 | 0.343 |
| reference 3 | — | 0.260 | 0.329 | 0.253 | 0.707 | 0.819 | 0.417 |
| reference 4 | — | 0.286 | 0.312 | 0.197 | 0.744 | 0.824 | 0.329 |

Reading: the first-stage distance moved by at most 0.02 in either direction; it **improved slightly for the overview (the arches), the research core and the subsurface views and got slightly worse for the habitat views** (the barrier posts add large uniform shapes). The structural statistics still differ from the references by a wide margin: edge density 0.06–0.18 against 0.30–0.42, high-frequency power 0.04–0.14 against 0.20–0.32, silhouette density of the habitat views 0.01 against 0.21–0.42 (the habitat frame is almost fully occupied, so it has almost no outline). The Research Core view remains the closest (0.236). **The visual-similarity goal is therefore PARTIAL and the change of this stage is not a measured improvement**; the statistics do not say that any view matches a reference, and no pixel-difference gate was added. The captures were taken on a software rasteriser (headless Chromium, SwiftShader).

Structural change made for this stage: 14 truss arches over the shaft (vertical scale, overlapping silhouettes and depth layering).

## 5. Not implemented, partial, failed

* **Not implemented:** live stepping of the engine from the browser (playback of a deterministic server record, as in stage one); a connection of XenoBody, the Ziran System, Xenoscience or a language-model Philosophical AI (the Philosophical operations here are couplings inside MEOS-0 only); a pixel-difference visual gate; any claim about a real ecosystem; R3 integration.
* **Partial:** recovery phase diagram covers two scenarios and one pulse site/time (25 amounts, 5 seeds); SSS regions cover 96 points at 3 seeds with no sweep finer than 0.1 in speed; the Philosophical experiment covers one claim kind that matters (scarcity of renewal efficiency) and one environment variable; the visual similarity to the references is partial and measured only by the proxies above; performance is measured on one machine.
* **Failed / negative results kept:** history reversal never occurred in the tested ranges (reported as absent, not hunted); revision under finite power fails; restoring an address after a collision collapses the run; partial addressability collapses and does not recover; fragmentation is a null result; direct M2 is a null result; the first captures with the heavier scene timed out under software rendering until the screenshot timeout was raised (a tooling failure, not a model result).

## 6. Performance

Measured in the desktop app's browser pane (WebGL2 on ANGLE Metal, Apple M1), balanced tier, overview camera, 240 frames: **59.998 fps, 16.67 ms mean, p95 17.7 ms, max 17.8 ms** — vsync-limited at 60 fps, so headroom is not measured. 95 draw calls, 671 k triangles, 44 130 instances, 102 k edge segments, simulation-state update 0.45 ms per tick, JS heap 25 MB. Against the first-stage scene: 86 → 95 draw calls, 42 684 → 44 130 instances (arches and the device layer). The `high` tier was **not** measured (the pane was hidden, so no frames were drawn); only its static counts are known (67 785 instances). `docs/ecosystem/performance_stage2.json`. The headless captures' 0.1–1.3 fps is software rendering and is not a performance figure.

## 7. Verification (this commit)

| check | result |
|---|---|
| backend full regression (`pytest`, 652 tests) | **650 passed, 2 failed**: the same two known failures as the baseline (`test_compat::test_engine_conformance_against_the_golden_fixture[desktop-scipy]`, `test_lab::test_published_records_replay`); no baseline test is missing; 71 tests added to the baseline's 581 (34 from stage one, 37 from this stage); JUnit compared test by test |
| frontend full tests | **130 / 130** passed (17 files; 17 new in this stage: 13 research-device and 4 study-helper tests; the camera-preset test was updated) |
| typecheck (`tsc -b`) | clean |
| lint | `ruff check xzr tests bench scripts` clean (E501 ignored for the MEOS scripts and modules, as for the other MEOS files); `eslint src` clean; `mypy xzr`: **0 errors in `xzr/meos`** (38 introduced earlier by this branch were fixed in this stage; ~89 errors elsewhere in `xzr` pre-date the branch and are untouched) |
| frontend build | passes |
| saved 264-run replay (11 studies, run with this backend's code) | **264 / 264 agree** (362 s; `docs/ecosystem/evidence/replay_meos_stage2.json`; script `backend/scripts/replay_stored_studies.py`) |
| MEOS deterministic replay | baseline result digest `b4cf1e52…adc5` unchanged and replays identically; the stage-two fixture replays identically (`a0dfe40f…ad21`); the stage-one fixture's (engine `meos-0.1`) result digest is reproduced by `meos-0.2` |
| existing known failures | unchanged (the two above) |
| undocumented dependencies | none added (`pyproject.toml` and `package.json`: only lint-ignore lines changed) |
| hidden baseline-parameter changes | none: `default_config()` is identical to the one at the end of stage one (field-by-field comparison) |

The replay script was rebuilt in this stage (the earlier one was not kept) and is now in the repository: `replay_run` of every stored run of the 11 stored studies, compared with the stored record.

## 8. Scores (separate; each is an assessment of this branch, not a measurement)

* **Software implementation completeness: 72 / 100.** Done and tested: engine `meos-0.2`, traces, causal paths, observation separation, M2, Philosophical operations, Address Domain interventions, nine experiment endpoints, the interface for all of them, a state-linked research-device layer, fixtures, 54 new tests (37 backend, 17 frontend), determinism checks. Missing: live engine stepping in the browser, an honest "which trial is executing" indicator, GPU measurement of the high tier, a visual regression gate, the connections to the other systems.
* **Experimental validation completeness: 52 / 100.** Eleven experiments were run on a fixed default configuration with 3–10 seeds each, deterministic and reproducible, with null, reversed-by-context, seed-dependent and non-monotone results kept. Not done: confirmatory or pre-registered runs, more than one base configuration, sensitivity analysis of the engine's own constants, independent replication, any link to a real system. Several findings (the narrow history-necessity band, the SSS active region, the recovery band) are properties of constants chosen so that the baseline sustains.
* **XENO ECOSYSTEM project completeness (as the first experimental foundation for XenoBody, Ziran System, Xenoscience and Philosophical AI in one space): 45 / 100.** MEOS-0 is a reproducible space in which two operational sequences generate each other's conditions and persistence, collapse and recovery are measured, and a first Philosophical coupling can be switched on and its necessity tested. The other systems are **not connected**: XenoBody appears only as boundary partitions of MEOS-0, the Ziran System and Xenoscience not at all, and the Philosophical coupling is a small operational module, not the Philosophical AI.

## 9. Graphics pass (third pass on visual similarity)

A new reference pair was supplied: dark concept renders of a *non-central experimental body* (three nodes joined by cable bundles) and an *adaptive observation node* (a column with an actuated arm and an exchangeable probe), each beside a white engineering sheet. This pass tried to reach that level of graphics in the real-time view. **It did not reach it**; it moved the look a measurable way toward it and the gap is stated below.

**What was built** (`terrain.ts`, `bodies.ts`, `researchDevice.ts`, the view):

* *Ground:* a displaced polar mesh of dark broken rock (before this pass the ground was a flat black disc); wet gravel (up to 14 000 glossy instanced pebbles) and wet rocks around the work areas; eight irregular puddles that are planar reflectors at the `balanced` and `high` tiers (the distant space frame is hidden during the reflection render) and polished dark mirrors at `performance`.
* *Light and reflection:* a dark studio environment map (a black room with long bright strips) for polished metal and wet rock, three narrow cool spot lights on the bodies, bloom on highlights and lamps, a vignette with fine grain, and at `high` a depth-of-field pass focused on the orbit target. The grain is part of the look and was kept small (0.035) so that it does not inflate the edge statistics.
* *Two experimental bodies,* of real geometry and not textures: perforated plates (extruded shapes with up to several hundred real holes), ported openings with collars, lens assemblies, bolted edges and bolt circles, tubular frames with hub spheres and collars, actuators, sensor pods, greebles, cable bundles (tubes along sagging curves, up to eight strands) with clamps, a ring junction on a post; for the observation node a column with flanges, a lattice arm with a hydraulic ram and cable loops, an elbow, a probe carrier and needle, a tripod-borne sensor head and a module dock.
* *What moves, and why* (`bodyState` is a pure function of the record, the tick and the observation; tested): node A's lens and lamp light on the ticks the observation samples (scaled by its coverage); node B's lamp flashes for five ticks after an A1 firing; node C's probe sparks for five ticks after an A2 renewal and the node is dark while A2 is absent; a light travels along the B–C bundle after a firing (B→C) and after a renewal (C→B); when the interaction channel is cut the bundle goes dark and the junction ring parts; the observation node's arm turns and reaches toward the observed region (two-link reach) and its probe lowers on sampled ticks. **This mapping is a presentation choice of the view. It does not claim that A1, A2 or the observation are these machines.** The geometry itself is static architecture.
* New camera presets `body`, `observer`, `puddle`; dust is now round sprites (square points were visible as boxes at close range); `window.__meos.setCamera` for captures; `?labels=0`.
* Captures now run on the machine's GPU in headless Chromium (ANGLE/Metal) instead of the software rasteriser (seconds instead of minutes per shot; `--software` keeps the old mode).

**Measured similarity.** Statistics are the proxies of section 4 and **do not establish a match**. Two comparisons are given because the supplied renders are 760 px wide and ours 1672 px: *native* (our capture as taken) and *at their resolution* (our capture resampled to 760 px width), the fairer one for edge and frequency statistics. References are the left halves of the two sheets with the title block removed.

| view | distance to the two body renders: native / at their resolution | lum | edge | sf-hi | occ | depth | sil | dark |
|---|---|---|---|---|---|---|---|---|
| 01-overview | 0.630 / 0.799 | 0.223 | 0.178 | 0.266 | 0.714 | 0.645 | 0.665 | 0.105 |
| 09-observation-array | 0.410 / 0.464 | 0.185 | 0.044 | 0.092 | 0.717 | 0.684 | 0.077 | 0.283 |
| 10-philosophical-socket | 0.516 / 0.598 | 0.219 | 0.082 | 0.131 | 0.819 | 0.743 | 0.155 | 0.181 |
| 14-experimental-body | 0.205 / 0.337 | 0.134 | 0.116 | 0.129 | 0.435 | 0.631 | 0.561 | 0.565 |
| 15-observation-node | 0.216 / 0.410 | 0.162 | 0.121 | 0.124 | 0.486 | 0.673 | 0.257 | 0.514 |
| 16-wet-ground | 0.236 / 0.248 | 0.157 | 0.107 | 0.106 | 0.498 | 0.690 | 0.543 | 0.502 |
| 17-body-coupling-cut | 0.205 / 0.330 | 0.128 | 0.117 | 0.135 | 0.415 | 0.615 | 0.584 | 0.585 |
| 18-body-renewal | 0.205 / 0.337 | 0.134 | 0.116 | 0.129 | 0.436 | 0.631 | 0.560 | 0.564 |
| reference ref21 (render half) | — | 0.111 | 0.203 | 0.284 | 0.322 | 0.580 | 0.956 | 0.678 |
| reference ref20 (render half) | — | 0.096 | 0.166 | 0.257 | 0.278 | 0.531 | 0.956 | 0.723 |

* Tone is close for the body views: the luminance-histogram total-variation distance to the nearest reference is 0.06–0.08 for views 14, 17 and 18, 0.11 for the wet-ground view and 0.18–0.19 for the observation-node view (whose frame contains lit domes). The proportion of near-black pixels is lower than in the references (0.50–0.59 against 0.68–0.72), the tonal-layer proxy and the occupied area are higher (0.61–0.70 against 0.53–0.58; 0.39–0.50 against 0.28–0.32): the new views are brighter and fuller than the renders.
* **Fine structure is not matched.** At the references' resolution the edge density is 0.14–0.16 against 0.17–0.20 (fairly close), but the high-frequency power is 0.11–0.15 against 0.26–0.28 and the silhouette density 0.26–0.47 against 0.96 (the references' outlines are far more broken). The distance to the references at their resolution is 0.25–0.41.
* The existing views (habitat, overview, research core, subsurface) share the same new ground, lighting and post-processing, so their look changed. Their distance to the **four earlier lattice references** fell, but this mainly reflects the darker, textured ground and not a closer match of the lattice itself:

| existing view | distance to the four lattice references: second-stage capture → this pass |
|---|---|
| 01-overview | 0.609 → 0.192 |
| 02-habitat | 0.491 → 0.315 |
| 03-research-core | 0.236 → 0.194 |
| 04-meos0-active | 0.468 → 0.317 |
| 05-meos-collapse | 0.426 → 0.309 |
| 06-xenobody-boundary | 0.507 → 0.314 |
| 07-history-overlay | 0.493 → 0.316 |
| 08-subsurface-laboratory | 0.348 → 0.225 |
| 09-observation-array | 0.694 → 0.247 |
| 10-philosophical-socket | 0.656 → 0.220 |
| 11-resource-pulse | 0.419 → 0.311 |
| 12-boundary-open | 0.429 → 0.318 |
| 13-recovered | 0.454 → 0.324 |

**Cost.** The balanced tier no longer holds 60 fps in the heavy views. Headless GPU (Apple M1, 1672 × 808): `performance` 60 fps (display limit) on the overview and the body; `balanced` 23 fps (overview), 27–32 (habitat views), 36–45 (body views), up to 58 (array and socket views); `high` 16–25 fps (`docs/ecosystem/performance_gpu_headless_*.json`). These are headless numbers and are not comparable with the 60 fps measured in the app's browser pane in section 6 (which was vsync-limited and measured the earlier scene); the pane was not available for a re-measurement. Per-frame work rose because of the reflection render, the post-processing chain and ~1 M vertices of body geometry per tier at `balanced`.

**Not done.** The engineering-sheet layout of the right-hand panels (dimensioned drawings, callouts, module detail views) was not reproduced; the images are not photographic (the bodies read as clean CG against the grit of the references, rocks are faceted); no screen-space reflections or volumetric dust; the depth-of-field pass exists only at `high`; no GPU measurement inside the app's browser pane for this pass.
