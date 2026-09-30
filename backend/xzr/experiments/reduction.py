"""Operational primitive reduction study (stage 1: paired trajectory distances; audits).

Stage 2 (systematic effects) and the classification rules live in ``reduction_rules.py``.

For each candidate primitive: ablate it, replace it with a reduced implementation (other primitives), and, where
the ablation diverges, search simple parameter compensations. Every variant is paired with the full runtime
under the same configuration, generator seed, engine seed, intervention battery and run length.

Tolerances are calibrated, not chosen: a variant *exceeds* on a metric in a configuration when

    mean_seeds d(full, variant) > 2 · max_seeds d(full, full with a different engine random stream) + 0.02

The perturbation floor (full vs full with 1e-9 added to one configuration's difference) is reported alongside.

Classification rules are explicit and mechanical (see ``classify``); every status cites the verdicts it used.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path

import numpy as np

from ..compare.trajectory import compare_recordings, response_distance, response_vector
from ..runtime import ops
from ..runtime.engine import Engine
from ..runtime.flags import MINIMAL, Flags
from ..runtime.state import State
from ..shapes.waves import WaveObserver
from .runs import CONFIGS, FULL, HORIZON, N, Variant, build_state, run

SEEDS = (11, 12, 13)
NOISE_SEED_OFFSET = 1000
ABS_TOL = 0.02
EXCEED_FACTOR = 2.0

VARIANTS: tuple[Variant, ...] = (
    # Q1 ignition vs transition
    Variant("fused_transition", {"fused_transition": True}),
    Variant("threshold_off", {"threshold": "off"}),
    Variant("threshold_off_gain0.3", {"threshold": "off"}, {"gain": 0.3}),
    Variant("threshold_off_gain0.6", {"threshold": "off"}, {"gain": 0.6}),
    Variant("threshold_off_gain1.0", {"threshold": "off"}, {"gain": 1.0}),
    # Q2 retention vs memory
    Variant("retention_off", {"retention": "off"}),
    Variant("retention_off_memory_x2", {"retention": "off"}, mem_coupling_scale=2.0),
    Variant("retention_off_memory_x4", {"retention": "off"}, mem_coupling_scale=4.0),
    Variant("memory_off", {"memory": "off"}),
    Variant("memory_off_retention+0.05", {"memory": "off"}, retention_add=0.05),
    Variant("memory_off_retention+0.10", {"memory": "off"}, retention_add=0.10),
    # Q3 transformation
    Variant("transform_off", {"transform": "off"}),
    # Q4 penetration
    Variant("wave_state_off", {"wave_state": "off"}),
    Variant("adapt_all_carriers", {"adapt_source": "all_carriers"}),
    Variant("adapt_off", {"adapt_source": "off"}),
    # Q5 return
    Variant("return_events_off", {"return_events": "off"}),
    # Q6 reconfiguration
    Variant("reconfigure_as_mutation", {"reconfigure": "mutation"}),
    Variant("reconfigure_off", {"reconfigure": "off"}),
    # Q7 difference
    Variant("difference_relational", {"difference": "relational"}),
    # other operations
    Variant("transition_off", {"transition": "off"}),
    Variant("cut_off", {"cut": "off"}),
    Variant("disconnect_off", {"disconnect": "off"}),
    Variant("connect_off", {"connect": "off"}),
    # verification of the minimal preset against the full runtime
    Variant("minimal", MINIMAL.to_dict()),
)

# a variant's "own" outputs: state arrays / event kinds that only it writes; excluded from bit-identity checks
OWN_STATE = {
    "transform_off": {"form"},
    "wave_state_off": {"wave_origin", "wave_depth", "pending_origin", "pending_depth"},
    "minimal": {"form", "wave_origin", "wave_depth", "pending_origin", "pending_depth"},
}
OWN_EVENTS = {
    "transform_off": {"transformations"},
    "wave_state_off": {"returns"},
    "return_events_off": {"returns"},
    "minimal": {"transformations", "returns"},  # reconstructed observer-side (returns) / dropped label (form)
}
METRICS = ("event_sequence", "graph_edit", "difference_w1", "signature", "response")


# ------------------------------------------------------------------------------------------------ runs
def _job(args: tuple) -> tuple[tuple, object]:
    key, cfg, variant, gen_seed, engine_seed, intervene, eps = args
    return key, run(cfg, variant, gen_seed, engine_seed, intervene=intervene, eps=eps)


def run_all(variants=VARIANTS, configs=CONFIGS, seeds=SEEDS, procs: int = 7) -> dict:
    jobs = []
    for cfg in configs:
        for s in seeds:
            jobs += [((cfg.name, s, "full", False), cfg, FULL, s, s, False, 0.0),
                     ((cfg.name, s, "full", True), cfg, FULL, s, s, True, 0.0),
                     ((cfg.name, s, "noise", False), cfg, FULL, s, s + NOISE_SEED_OFFSET, False, 0.0),
                     ((cfg.name, s, "noise", True), cfg, FULL, s, s + NOISE_SEED_OFFSET, True, 0.0),
                     ((cfg.name, s, "perturb", False), cfg, FULL, s, s, False, 1e-9)]
            for v in variants:
                jobs += [((cfg.name, s, v.name, False), cfg, v, s, s, False, 0.0),
                         ((cfg.name, s, v.name, True), cfg, v, s, s, True, 0.0)]
    out = {}
    with ProcessPoolExecutor(procs) as ex:
        for key, rec in ex.map(_job, jobs, chunksize=2):
            out[key] = rec
    return out


# ------------------------------------------------------------------------------------------------ distances
def _pair(a, b, a_int, b_int, own_events: set[str]) -> dict:
    c = compare_recordings(a, b)
    kinds = {k: v for k, v in c["event_per_kind"].items() if k not in own_events
             and (sum(a.counts[k]) + sum(b.counts[k])) > 0}
    flat = {
        "event_sequence": float(np.mean(list(kinds.values()))) if kinds else 0.0,
        "graph_edit": c["graph_edit"], "difference_w1": c["difference_w1"], "memory_w1": c["memory_w1"],
        "signature": c["signature"], "ignition_sets": c["ignition_sets"],
        "response": response_distance(response_vector(a, a_int), response_vector(b, b_int)),
        **{f"criterion:{k}": v for k, v in c["criteria"].items()},
    }
    return {"metrics": flat, "first_divergence": c["first_divergence"]}


def _identical(a, b, own_state: set[str], own_events: set[str]) -> bool:
    same_state = all(a.hashes[k] == b.hashes[k] for k in a.hashes if k not in own_state)
    same_events = all(a.counts[k] == b.counts[k] for k in a.counts if k not in own_events)
    same_ign = all(np.array_equal(x, y) for x, y in zip(a.ignitions, b.ignitions, strict=True))
    same_series = all(a.series[k] == b.series[k] for k in a.series if not k.endswith("returns")
                      and not k.endswith("transformations") and k != "s:recurrence")
    return same_state and same_events and same_ign and same_series


def analyse(recs: dict, variants=VARIANTS, configs=CONFIGS, seeds=SEEDS) -> dict:
    result: dict = {"floors": {}, "variants": {}}
    judged = (*METRICS, *[f"criterion:{k}" for k in
                          ("reachable_structure", "branching", "closure", "recurrent_loops", "fragmentation",
                           "concentration", "persistence", "amplification_regime", "path_dependence")])
    noise: dict[str, dict[str, float]] = {}
    for cfg in configs:
        per_seed = [_pair(recs[(cfg.name, s, "full", False)], recs[(cfg.name, s, "noise", False)],
                          recs[(cfg.name, s, "full", True)], recs[(cfg.name, s, "noise", True)], set())
                    for s in seeds]
        pert = [compare_recordings(recs[(cfg.name, s, "full", False)], recs[(cfg.name, s, "perturb", False)])
                for s in seeds]
        noise[cfg.name] = {m: max(p["metrics"][m] for p in per_seed) for m in per_seed[0]["metrics"]}
        result["floors"][cfg.name] = {
            "noise": noise[cfg.name],
            "perturbation": {"ignition_sets": float(np.mean([p["ignition_sets"] for p in pert])),
                             "event_sequence": float(np.mean([p["event_sequence"] for p in pert])),
                             "first_divergence": [p["first_divergence"] for p in pert]},
            "full_ms_per_step": float(np.mean([recs[(cfg.name, s, "full", False)].ms_per_step for s in seeds])),
            "full_ignitions_per_step": float(np.mean([np.mean(recs[(cfg.name, s, "full", False)].counts["ignitions"])
                                                     for s in seeds])),
            "full_event_totals": {k: int(sum(sum(recs[(cfg.name, s, "full", False)].counts[k]) for s in seeds))
                                  for k in recs[(cfg.name, seeds[0], "full", False)].counts},
        }
    for v in variants:
        own_s, own_e = OWN_STATE.get(v.name, set()), OWN_EVENTS.get(v.name, set())
        vres: dict = {"flags": v.flags, "params": v.params, "mem_coupling_scale": v.mem_coupling_scale,
                      "retention_add": v.retention_add, "configs": {}}
        for cfg in configs:
            pairs, ident, ms, ign = [], [], [], []
            for s in seeds:
                a, b = recs[(cfg.name, s, "full", False)], recs[(cfg.name, s, v.name, False)]
                pairs.append(_pair(a, b, recs[(cfg.name, s, "full", True)], recs[(cfg.name, s, v.name, True)], own_e))
                ident.append(_identical(a, b, own_s, own_e) and _identical(
                    recs[(cfg.name, s, "full", True)], recs[(cfg.name, s, v.name, True)], own_s, own_e))
                ms.append(b.ms_per_step)
                ign.append(float(np.mean(b.counts["ignitions"])))
            dist = {m: float(np.mean([p["metrics"][m] for p in pairs])) for m in pairs[0]["metrics"]}
            tol = {m: EXCEED_FACTOR * noise[cfg.name][m] + ABS_TOL for m in judged}
            exceeded = [m for m in judged if dist[m] > tol[m]]
            verdict = "bit-identical" if all(ident) else ("equivalent" if not exceeded else "divergent")
            vres["configs"][cfg.name] = {
                "verdict": verdict, "exceeded": exceeded, "distance": dist, "tolerance": tol,
                "first_divergence": [p["first_divergence"] for p in pairs],
                "ms_per_step": float(np.mean(ms)), "ignitions_per_step": float(np.mean(ign)),
            }
        vs = [c["verdict"] for c in vres["configs"].values()]
        vres["overall"] = ("bit-identical" if all(x == "bit-identical" for x in vs) else
                           "equivalent" if all(x in ("bit-identical", "equivalent") for x in vs) else
                           "divergent" if all(x == "divergent" for x in vs) else "mixed")
        result["variants"][v.name] = vres
    return result


# ------------------------------------------------------------------------------------------------ dataflow audits
def _warm_state(steps: int = 150) -> tuple[State, Engine]:
    st, _ = build_state(CONFIGS[0], SEEDS[0])
    eng = Engine(st, SEEDS[0], checkpoint_every=0)
    eng.run(steps)
    return eng.state, eng


def write_audit(steps: int = 60) -> dict[str, list[str]]:
    """Which state arrays each operation writes (observed by diffing state around each call)."""
    _, eng = _warm_state()
    s, rng = eng.state, eng.rng
    writes: dict[str, set[str]] = {}

    def call(name, fn, *a):
        before = {k: v.copy() for k, v in s.arrays().items()}
        out = fn(*a)
        now = s.arrays()
        writes.setdefault(name, set()).update(k for k in before if not np.array_equal(before[k], now[k], equal_nan=True))
        return out

    carried = np.zeros(0, np.int32)
    for _ in range(steps):
        s.t += 1
        call("inject (external input)", ops.inject, s, rng)
        ign = call("ignite", ops.ignite, s)
        fl = call("propagate (transition)", ops.propagate, s, ign)
        call("transform", ops.transform, s, fl)
        call("retain_and_decay", ops.retain_and_decay, s, fl)
        call("remember (memory)", ops.remember, s, ign)
        call("adapt_weights", ops.adapt_weights, s, ign.penetrations[:, 0], carried)
        carried = fl.edges
        cuts = call("cut", ops.cut, s)
        rem = call("disconnect", ops.disconnect, s)
        call("connect", ops.connect, s, rng, ign, np.concatenate([cuts, rem]))
        call("reconfigure", ops.reconfigure, s, rng)
    return {k: sorted(v) for k, v in writes.items()}


INFLUENCE_FIELDS = ("diff", "theta", "retention", "memory", "form", "wave_origin", "wave_depth", "pending_origin",
                    "pending_depth", "ignite_count", "last_ignite", "overload", "weight", "load", "capacity",
                    "transform")


def influence_matrix(steps: int = 60) -> dict[str, list[str]]:
    """Perturb one state array at a warm state, run both copies with the same random stream, and list which
    *other* arrays differ afterwards. An array that influences nothing but itself is not read by dynamics."""
    base_state, eng = _warm_state()
    rng_state = dict(eng.rng.bit_generator.state)
    ref = eng.fork()
    ref.run(steps)
    out = {}
    for f in INFLUENCE_FIELDS:
        e = Engine(base_state.copy(), SEEDS[0], checkpoint_every=0)
        e.rng.bit_generator.state = rng_state
        arr = getattr(e.state, f)
        g = np.random.default_rng(7)
        if arr.dtype.kind == "f":
            arr *= 1.0 + 0.05 * g.standard_normal(arr.shape)
        elif f in ("form", "transform"):
            arr[:] = (arr + g.integers(1, 3, arr.shape)) % e.state.params.n_forms
        elif f in ("wave_origin", "pending_origin"):
            arr[:] = g.integers(0, e.state.n, arr.shape)
        else:
            arr[:] = arr + g.integers(0, 3, arr.shape).astype(arr.dtype)
        e._carried_prev = eng._carried_prev.copy()
        e.run(steps)
        changed = sorted(k for k, v in e.state.arrays().items()
                         if k != f and not np.array_equal(v, ref.state.arrays()[k], equal_nan=True))
        out[f] = changed
    return out


def observer_reconstruction(steps: int = HORIZON) -> dict:
    """Wave annotations and returns reconstructed outside the runtime vs computed inside it, per configuration."""
    res = {}
    for cfg in CONFIGS:
        agree_p = agree_r = True
        n_pen = n_ret = 0
        crossing = 0
        for s in SEEDS:
            st_a, h = build_state(cfg, s)
            st_b, _ = build_state(cfg, s)
            a = Engine(st_a, s, checkpoint_every=0)
            b = Engine(st_b, s, checkpoint_every=0, flags=Flags(wave_state="off"))
            obs = WaveObserver(b.state)
            macro = h.labels[0]
            for _ in range(steps):
                da, db = a.step(), b.step()
                p, r = obs.observe(db, b.state)
                agree_p &= bool(np.array_equal(p, da.penetrations))
                agree_r &= bool(np.array_equal(r, da.returns))
                n_pen += len(p)
                n_ret += len(r)
                if len(db.penetrations):
                    srcs = obs.src[db.penetrations[:, 0]]
                    crossing += int((macro[srcs] != macro[db.penetration_receivers]).sum())
        res[cfg.name] = {"penetrations_agree": agree_p, "returns_agree": agree_r, "penetrations": n_pen,
                         "returns": n_ret, "cross_macro_share": round(crossing / max(n_pen, 1), 4)}
    return res


def returns_vs_loops(steps: int = HORIZON) -> dict:
    """How return events relate to detected strongly connected loops (descriptive correspondence)."""
    from ..shapes.detector import ShapeDetector
    res = {}
    for cfg in CONFIGS:
        in_loop = total = 0
        for s in SEEDS:
            st, h = build_state(cfg, s)
            e = Engine(st, s, checkpoint_every=0)
            det = ShapeDetector(h, graph_every=10)
            pending: list[np.ndarray] = []
            for _ in range(steps):
                d = e.step()
                r = det.observe(d, e.state)
                pending.append(d.returns)
                if "graph" in r:
                    for ret in pending:
                        total += len(ret)
                        in_loop += int(det.in_loop[ret].sum())
                    pending = []
        res[cfg.name] = {"returns": total, "share_in_detected_loops": round(in_loop / max(total, 1), 4)}
    return res


def perf_table(steps: int = 300) -> dict:
    """Engine-only cost per variant, measured sequentially (no parallel contention), configuration 'intermittent'."""
    cfg = CONFIGS[0]
    out = {}
    for v in (FULL, *VARIANTS):
        st, _ = build_state(cfg, SEEDS[0], v)
        e = Engine(st, SEEDS[0], checkpoint_every=0, flags=Flags.from_dict(v.flags))
        e.run(30)
        t0 = time.perf_counter()
        e.run(steps)
        out[v.name] = {"ms_per_step": round(1000 * (time.perf_counter() - t0) / steps, 3),
                       "state_bytes": int(sum(a.nbytes for a in e.state.arrays().values()))}
    return out


def main(out: str | None = None, procs: int = 7) -> dict:
    t0 = time.perf_counter()
    recs = run_all(procs=procs)
    an = analyse(recs)
    audits = {"writes": write_audit(), "influence": influence_matrix(), "observer": observer_reconstruction(),
              "returns_vs_loops": returns_vs_loops(), "performance": perf_table()}
    from .reduction_rules import classify, minimal_verification, systematic
    sysres = systematic(procs=procs)
    rows = classify(an, audits, sysres)
    result = {
        "suite": "primitive_reduction", "n": N, "horizon": HORIZON, "seeds": list(SEEDS),
        "configs": [asdict(c) for c in CONFIGS], "tolerance_rule": f"exceed if d > {EXCEED_FACTOR}·noise + {ABS_TOL}",
        "floors": an["floors"], "variants": an["variants"], "audits": audits, "systematic": sysres,
        "classification": rows, "minimal_verification": minimal_verification(an, sysres),
        "elapsed_s": round(time.perf_counter() - t0, 1),
    }
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(result, indent=1, default=str))
    return result


if __name__ == "__main__":
    import sys
    r = main(sys.argv[1] if len(sys.argv) > 1 else None)
    for row in r["classification"]:
        print(f"{row['primitive']:36s} {row['status']}")
