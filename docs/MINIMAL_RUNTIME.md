# Minimal runtime

`MINIMAL` in `backend/xzr/runtime/flags.py`; select it with `POST /api/sessions {"sample": …, "flags": "minimal"}` or
`/?runtime=minimal` in the UI.

## 1. What it contains (derived classification → implementation)

| reduction | flag | evidence (docs/REDUCTION.md) | exactness |
|---|---|---|---|
| ignition merged into thresholded transition | `fused_transition=True` | bit-identical in all 4 regimes | exact |
| transformation removed | `transform="off"` | removal bit-identical apart from its own `form` label; `form` influences no other array | exact (label dropped) |
| wave origin/depth moved out of the runtime | `wave_state="off"` | observer (`shapes/waves.py`) reconstructs them exactly in all regimes | exact (reconstructed) |
| return detection moved out of the runtime | `return_events="off"` | removal bit-identical; observer reconstructs returns exactly | exact (reconstructed) |
| reconfiguration as connection mutation (remove + create) | `reconfigure="mutation"` | equivalent in all regimes, 0 stage-2 effects | statistical (edge ids differ) |

**Not included** (deliberately):

* relational difference (DERIVED, but costlier; the node-local value is kept as a cache — implementation choice);
* disconnection removal (UNRESOLVED — no demonstrated effect is not evidence of redundancy);
* anything classified NON-REDUNDANT.

## 2. Primitive set of the minimal runtime

1. **Thresholded transition** along reachable connections (gate = effective threshold; emission with gain and
   load-dependent conduction; refractory period).
2. **Retention** of non-emitted difference (with discharge on transition).
3. **Memory** (decaying transition trace; shifts effective thresholds; gates closure).
4. **Connection mutation** — creation, removal, redirection — triggered by load (cut), weakness (disconnection;
   unresolved), co-ignition memory (closure) and overload (reconfiguration, now remove + create).
5. **Weight adaptation** of connections that caused a transition (dominant incoming connection).

Derived, not primitive: difference (sum of relational state), reachability (computed), penetration (transition
record + observer). Descriptive only: return, transformation, decay.

## 3. Verification (measured)

Full vs MINIMAL, same framework as single reductions (stage 1: 4 regimes × 3 seeds × 360 steps with the intervention
battery; stage 2: 8 seeds × 1,200 steps): **equivalent in every regime; zero downstream systematic effects; worst
criterion distance 0.54 of tolerance (recurrent loops, memory_heavy)**. Details: generated tables in
docs/REDUCTION.md. Tests: `test_minimal_exact_reductions_are_bit_identical`,
`test_minimal_runtime_events_are_complete_with_the_observer`, `test_minimal_runtime_stays_within_the_noise_floor`,
`test_deterministic_replay_under_ablation[MINIMAL]`, `test_rewind_under_ablation_replays_interventions`.

Event fidelity: sessions running MINIMAL reconstruct penetration origin/depth and returns with the observer before
streaming, so clients receive the same event kinds; only the `form` label (transformations) is absent.

## 4. Performance

See docs/BENCHMARK.md (full vs minimal section).

## 5. Unresolved

Whether disconnection can be removed; whether the reconfiguration trigger could be merged with the cut trigger (not
tested).
