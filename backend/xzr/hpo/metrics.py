"""Measures of one HPO run (computed by the harness from the field's records and the world's true state).

Grouped as in the HPO protocol (docs/HPO_PROTOCOL.md):

    ignition          ignitions (ignite + re-ignite events), fired samples, mean first-ignition step (censored at the
                      horizon for kinds that never ignite) and the number of kinds that never ignited
    transformation    cross-operation transformations, filtered acts, conflicts, couplings, splits, reclassifications,
                      revisions, feedback adaptations, parameter drift
    reachability      final share of usable connections; configurations reachable within ``reach_hops`` from the
                      operations' regions; distinct operation states visited
    cessation         cessations; share of operation-samples spent ceased
    re-ignition       re-ignitions and their latency
    history           re-insertions
    latency           correction latency (error onset → revision); re-transformation latency (being transformed →
                      next act)
    real effects      runtime records applied, and the world's divergence from the matched no-HPO branch (R0)
    unobservability   unobservable evaluations, per reason
    causal            cross-operation causal links, maximum causal depth, maximum number of sources on one path

Every effect here is a simulation-internal causal effect. The run has no physical or institutional effect outside
the simulation (``external_effects`` is reported as such).
"""

from __future__ import annotations

import math

import numpy as np

from .field import Field
from .observe import REASONS
from .registry import KINDS
from .world import World

EXTERNAL_EFFECTS = "none: the run changes simulated state only (no physical, institutional or networked effect)"


def _mean(x: list) -> float:
    return float(np.mean(x)) if x else math.nan


def reach_from(world: World, nodes: np.ndarray, hops: int) -> int:
    st = world.state
    m = st.reachable_mask()
    src, dst = st.src[m], st.dst[m]
    seen = np.zeros(st.n, bool)
    seen[nodes] = True
    frontier = seen.copy()
    for _ in range(hops):
        nxt = np.zeros(st.n, bool)
        nxt[dst[frontier[src]]] = True
        frontier = nxt & ~seen
        if not frontier.any():
            break
        seen |= frontier
    return int(seen.sum())


def world_measure(w: World) -> dict[str, float]:
    """The world-level measures alone (for the no-HPO reference branch R0)."""
    st = w.state
    return {"field_ignitions": float(w.total_ignitions), "memory_mean": float(st.memory.mean()),
            "alive_connections": float(st.alive.sum()),
            "gate_mean": float(st.gate[st.alive].mean()) if st.alive.any() else 0.0,
            "reachable_share": float(st.reachable_mask().sum() / max(1, st.alive.sum()))}


def measure(f: Field, ref: World | None = None) -> dict[str, float]:
    st = f.stats
    hs = f.history.summary()
    bt = hs["by_type"]
    w = f.world
    horizon = w.t - f.t0
    kinds = f.s["kinds"]
    first = [st["first_ignition"].get(k, horizon) for k in kinds]
    never = sum(1 for k in kinds if k not in st["first_ignition"])
    live = f.live()
    regions = np.unique(np.concatenate([o.region for o in live])) if live else np.zeros(0, np.int32)
    ser = st["series"]
    ceased_share = float(np.sum(ser["ceased"]) / max(1, np.sum(ser["ops"])))
    drift = f.drift()
    m: dict[str, float] = {
        "ignitions": bt.get("ignite", 0) + bt.get("reignite", 0),
        "fired_samples": st["evaluations"]["FIRED"],
        "first_ignition_mean": float(np.mean(first)),
        "never_ignited": never,
        "transformations": bt.get("transform", 0),
        "filtered": bt.get("filter", 0),
        "conflicts": bt.get("conflict", 0),
        "couplings": bt.get("couple", 0),
        "splits": bt.get("split", 0),
        "reclassifications": bt.get("reclassify", 0),
        "revisions": bt.get("revise", 0),
        "feedback": bt.get("feedback", 0),
        "param_drift": float(np.mean(list(drift.values()))) if drift else 0.0,
        "reachable_share": float(w.state.reachable_mask().sum() / max(1, w.state.alive.sum())),
        "reach_from_regions": reach_from(w, regions, f.s["reach_hops"]) / w.state.n if len(regions) else 0.0,
        "op_states_visited": len(st["states_visited"]),
        "kinds_seen": len({lab for lab, _, _ in st["states_visited"]}),
        "ops_final": len(live),
        "cessations": bt.get("cease", 0),
        "ceased_share": ceased_share,
        "reignitions": bt.get("reignite", 0),
        "reignite_latency": _mean(st["reignite_latency"]),
        "reinsertions": st["reinsertions"],
        "correction_latency": _mean(st["correction_latency"]),
        "retransform_latency": _mean(st["retransform_latency"]),
        "applied_records": float(sum(st["applied"].values())),
        "suppressed": st["suppressed"],
        "unobservable_samples": st["evaluations"]["UNOBSERVABLE"],
        "shared_fills": st["shared_fills"],
        "cross_links": hs["cross_operation_links"],
        "causal_depth": hs["max_depth"],
        "sources_on_path": hs["max_sources_on_a_path"],
        "field_ignitions": float(w.total_ignitions),
        "memory_mean": float(w.state.memory.mean()),
        "alive_connections": float(w.state.alive.sum()),
        "gate_mean": float(w.state.gate[w.state.alive].mean()) if w.state.alive.any() else 0.0,
    }
    for r in REASONS:
        m[f"unobs:{r}"] = st["unobservable"].get(r, 0)
    for kind in KINDS:  # per kind (an operation counts for every kind it carries at the end of the run)
        for typ, name in (("ignite", "ignitions"), ("reignite", "reignitions"), ("cease", "cessations")):
            m[f"{name}:{kind}"] = sum(1 for e in f.history.events if e["type"] == typ and e["source"] in f.ops
                                      and kind in f.ops[e["source"]].kinds)
    pic = [o.mem.get("picturing", {}) for o in f.ops.values() if "picturing" in o.kinds]
    errs = [p["error_sum"] / p["errors"] for p in pic if p.get("errors")]
    m["picturing_error"] = _mean(errs)
    if ref is not None:
        a, b = w.state, ref.state
        m["div_connections"] = float(np.mean((a.alive != b.alive) | (np.abs(a.weight - b.weight) > 1e-9)))
        m["div_ignitions"] = float(w.total_ignitions - ref.total_ignitions)
        m["div_memory"] = float(np.abs(a.memory - b.memory).mean())
        m["div_identical"] = float(w.engine.fingerprint() == ref.engine.fingerprint())
        if w.rng_trace is not None and ref.rng_trace is not None:
            k = next((i for i, (x, y) in enumerate(zip(w.rng_trace, ref.rng_trace, strict=False)) if x != y), None)
            m["endogenous_divergence_step"] = float(k + 1) if k is not None else float(horizon)
    return m
