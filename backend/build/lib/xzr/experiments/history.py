"""History operations: fork, removal, reactivation and migration of retained history, compared downstream.

*History* here means the runtime's retained record of past activity: the per-configuration ``memory`` (raised by
every ignition, decaying each step, lowering the effective threshold of the configuration that holds it). The
operations act on that array only; nothing else in the state is touched.

At step ``operation_at`` one warmed-up world is forked into paired branches that share state and random stream:

    intact       continue unchanged (reference)
    noise        continue unchanged with another random stream (false-positive / variability control)
    fork         a second exact continuation: must be bit-identical to ``intact`` (fork carries the full history)
    remove       memory of the target region set to 0
    reactivate   removed as above; at ``reactivate_at`` the region's saved memory (its value at ``operation_at``)
                 is added back on top of whatever memory the region has rebuilt since (the removed record
                 re-enters; nothing that happened in between is erased)
    migrate      the target region's memory moved onto the same number of configurations of another region;
                 the target region is set to 0

Measured for every branch over the window after the operation (per engine seed):

    reachability           mean share of connections usable as transitions
    generation             ignitions in the whole field
    region_generation      ignitions inside the target region (and, for migrate, inside the destination region)
    discrimination         distinct operational-shape signatures recorded by the shape detector
    intervention_response  change in field ignitions caused by a fixed intervention (threshold scaling of a third
                           region) applied at ``probe_at`` — measured as the branch with the intervention minus the
                           branch without it
    later_configuration    final connection count, and the share of connections whose state differs from intact

Statistics (paired over seeds): mean difference against ``intact`` with a two-sided exact sign-flip test (all 2^S
sign patterns) and a 95 % t interval. A difference is DETECTED when p < ``alpha`` and |mean| ≥ 2 % of the intact
mean and larger than the largest |noise − intact| difference of that metric; EQUIVALENT when the 95 % interval lies
within ±5 % of the intact mean; otherwise UNRESOLVED. With fewer than ``min_seeds_for_test`` seeds the sign-flip
test cannot reach ``alpha`` and every non-identical difference is reported UNRESOLVED.

History re-entry (HRGI-style) is reported only when all four are measured, in this runtime's terms:
    retained prior difference   the target region held memory at ``operation_at`` (every seed)
    re-addressability           right after reactivation the region's effective thresholds differ from ``remove``
                                (the restored record is read by the transition rule again; memory coupling is
                                signed, so a restored record can lower or raise a threshold)
    actual re-entry             region ignitions after ``reactivate_at``: reactivate > remove, DETECTED
    downstream difference       a field metric outside the region differs reactivate vs remove, DETECTED
Otherwise the result is reported as history dependence (a ``remove`` metric DETECTED against ``intact``), as
dependence not distinguished from trajectory noise (removal changes the run, but no measured effect exceeds the
noise branch), or as no effect (bit-identical continuation). These are measured differences in a simulation;
they are not evidence about any system outside it.
"""

from __future__ import annotations

import math
from itertools import product
from typing import Any

import numpy as np

from ..lod.hierarchy import build_hierarchy, symmetric_adjacency
from ..runtime.engine import Engine
from ..runtime.generator import latent_geometric
from ..runtime.intervention import ScaleThreshold
from ..runtime.state import Params
from ..shapes.detector import ShapeDetector
from .runs import CONFIGS

DEFAULTS: dict[str, Any] = {
    "n": 1500, "config": "intermittent", "gen_seed": 3, "seeds": 12, "seed0": 100,
    "operation_at": 150, "reactivate_at": 200, "horizon": 300, "probe_at": 220,
    "region": "1", "migrate_to": "4", "probe_region": "6", "probe_factor": 1.3,
    "operations": ["fork", "remove", "reactivate", "migrate"], "alpha": 0.01, "min_seeds_for_test": 8,
}
NOISE_OFFSET = 1000
METRICS = ("reachability", "generation", "region_generation", "discrimination", "intervention_response",
           "final_connections", "connections_differing")


def _world(p: dict):
    cfg = next(c for c in CONFIGS if c.name == p["config"])
    params = Params.from_dict(cfg.params)
    st = latent_geometric(p["n"], p["gen_seed"], params=params, **cfg.gen).state
    if cfg.mem_coupling_scale != 1.0:
        st.base_mem_coupling *= cfg.mem_coupling_scale
        st.mem_coupling[:] = st.base_mem_coupling
    if cfg.mem_decay is not None:
        st.base_mem_decay[:] = cfg.mem_decay
        st.mem_decay[:] = cfg.mem_decay
    m = st.alive
    h = build_hierarchy(symmetric_adjacency(st.src[m], st.dst[m], st.n))
    return st, h


def _continue(eng: Engine, h, p: dict, region: np.ndarray, extra: np.ndarray | None, restore: np.ndarray | None,
              probe: bool) -> dict:
    """Run a branch from the operation step to the horizon and measure it."""
    det = ShapeDetector(h, graph_every=10)
    sigs: set = set()
    reach: list[float] = []
    gen = reg = ext = 0
    reg_after_re = 0
    for _ in range(p["horizon"] - eng.state.t):
        t = eng.state.t
        if restore is not None and t == p["reactivate_at"]:
            eng.state.memory[region] += restore  # the removed record re-enters on top of what regrew since
        if probe and t == p["probe_at"]:
            eng.set_overlay([ScaleThreshold(tuple(p["_probe_nodes"]), p["probe_factor"])])
        d = eng.step()
        r = det.observe(d, eng.state)
        if "graph" in r:
            sigs.update(det.signatures)
        ign = d.ignitions
        gen += int(ign.size)
        inside = np.isin(ign, region)
        reg += int(inside.sum())
        if eng.state.t > p["reactivate_at"]:
            reg_after_re += int(inside.sum())
        if extra is not None:
            ext += int(np.isin(ign, extra).sum())
        reach.append(float(eng.state.reachable_mask().mean()))
    st = eng.state
    return {"reachability": float(np.mean(reach)), "generation": gen, "region_generation": reg,
            "region_generation_after_reactivation": reg_after_re, "destination_generation": ext,
            "discrimination": len(sigs), "final_connections": int(st.alive.sum()),
            "_alive": st.alive.copy(), "_w": st.weight.copy(), "_fp": eng.fingerprint()}


def seed_job(p: dict, seed: int) -> dict:
    """All branches of one engine seed."""
    st, h = _world(p)
    region = h.resolve(p["region"])
    dest = h.resolve(p["migrate_to"])
    p = {**p, "_probe_nodes": h.resolve(p["probe_region"]).tolist()}
    base = Engine(st, seed, checkpoint_every=0)
    for _ in range(p["operation_at"]):
        base.step()
    saved = base.state.memory[region].copy()
    out: dict[str, Any] = {"seed": seed, "region_memory_at_operation": float(saved.mean()),
                           "region_size": int(region.size), "branches": {}}

    def branch(kind: str) -> tuple[Engine, np.ndarray | None]:
        e = base.fork()
        restore = None
        if kind == "noise":
            e.rng = np.random.default_rng(seed + NOISE_OFFSET)
        elif kind == "remove":
            e.state.memory[region] = 0.0
        elif kind == "reactivate":
            e.state.memory[region] = 0.0
            restore = saved
        elif kind == "migrate":
            k = min(region.size, dest.size)
            e.state.memory[dest[:k]] = saved[:k]
            e.state.memory[region] = 0.0
        return e, restore

    kinds = ["intact", "noise", *[o for o in p["operations"] if o != "intact"]]
    for kind in kinds:
        e, restore = branch(kind)
        probe_e, probe_restore = branch(kind)
        extra = dest if kind == "migrate" else None
        m = _continue(e, h, p, region, extra, restore, probe=False)
        mp = _continue(probe_e, h, p, region, extra, probe_restore, probe=True)
        m["intervention_response"] = mp["generation"] - m["generation"]
        out["branches"][kind] = m
    ref = out["branches"]["intact"]
    for m in out["branches"].values():
        m["connections_differing"] = float(np.mean((m["_alive"] != ref["_alive"]) |
                                                   (np.abs(m["_w"] - ref["_w"]) > 1e-9)))
        m["bit_identical_to_intact"] = m["_fp"] == ref["_fp"]
    # re-addressability: effective threshold of the region right after restoration, reactivate vs remove
    if "reactivate" in out["branches"] and "remove" in out["branches"]:
        ea, _ = branch("reactivate")
        eb, _ = branch("remove")
        for _ in range(p["reactivate_at"] - p["operation_at"]):
            ea.step()
            eb.step()
        ea.state.memory[region] += saved
        ta, tb = ea.state.theta_eff()[region], eb.state.theta_eff()[region]
        out["theta_after_restore"] = {"reactivate_mean": float(ta.mean()), "remove_mean": float(tb.mean()),
                                      "share_changed": float(np.mean(np.abs(ta - tb) > 1e-12))}
    for m in out["branches"].values():
        for k in ("_alive", "_w", "_fp"):
            m.pop(k, None)
    return out


# ------------------------------------------------------------------------------------------------ statistics
def sign_flip_p(d: np.ndarray) -> float:
    """Two-sided exact sign-flip p-value of the mean of paired differences (all 2^S patterns, S ≤ 16)."""
    s = d.size
    if s == 0 or np.allclose(d, 0):
        return 1.0
    obs = abs(d.mean())
    signs = np.array(list(product((1, -1), repeat=s)), dtype=float)
    stats = np.abs((signs * d).mean(axis=1))
    return float((stats >= obs - 1e-12).mean())


def _ci_half(d: np.ndarray) -> float:
    if d.size < 2:
        return math.inf
    t = {2: 12.71, 3: 4.30, 4: 3.18, 5: 2.78, 6: 2.57, 7: 2.45, 8: 2.36, 9: 2.31, 10: 2.26, 11: 2.23, 12: 2.20}
    q = t.get(d.size, 2.0)
    return float(q * d.std(ddof=1) / math.sqrt(d.size))


def assess(diffs: np.ndarray, noise: np.ndarray, base_mean: float, p: dict) -> dict:
    scale = abs(base_mean) or 1.0
    mean = float(diffs.mean())
    half = _ci_half(diffs)
    pval = sign_flip_p(diffs)
    noise_max = float(np.max(np.abs(noise))) if noise.size else 0.0
    if np.allclose(diffs, 0, atol=1e-12):
        status = "IDENTICAL"
    elif (diffs.size >= p["min_seeds_for_test"] and pval < p["alpha"] and abs(mean) >= 0.02 * scale
          and abs(mean) > noise_max):
        status = "DETECTED"
    elif math.isfinite(half) and abs(mean) + half <= 0.05 * scale:
        status = "EQUIVALENT"
    else:
        status = "UNRESOLVED"
    return {"mean_difference": mean, "relative": mean / scale, "ci95_half": half, "p_sign_flip": pval,
            "noise_max_abs": noise_max, "status": status}


def analyse(p: dict, jobs: list[dict]) -> dict:
    kinds = [k for k in jobs[0]["branches"] if k != "intact"]
    res: dict[str, Any] = {"seeds": [j["seed"] for j in jobs], "comparisons": {}}
    noise = {m: np.array([j["branches"]["noise"][m] - j["branches"]["intact"][m] for j in jobs], float)
             for m in METRICS}
    for kind in kinds:
        rows: dict[str, Any] = {}
        for m in METRICS:
            d = np.array([j["branches"][kind][m] - j["branches"]["intact"][m] for j in jobs], float)
            base = float(np.mean([j["branches"]["intact"][m] for j in jobs]))
            rows[m] = assess(d, noise[m] if kind != "noise" else np.zeros(0), base, p)
        rows["bit_identical_share"] = float(np.mean([j["branches"][kind]["bit_identical_to_intact"] for j in jobs]))
        res["comparisons"][kind] = rows
    res["history_reentry"] = reentry(p, jobs, res)
    return res


def reentry(p: dict, jobs: list[dict], res: dict) -> dict:
    """HRGI-style criteria, reactivate vs remove (see module docstring)."""
    if not {"remove", "reactivate"} <= set(jobs[0]["branches"]):
        return {"verdict": "NOT EVALUATED", "reason": "needs both remove and reactivate"}
    noise = {m: np.array([j["branches"]["noise"][m] - j["branches"]["intact"][m] for j in jobs], float)
             for m in ("region_generation_after_reactivation", "generation", "reachability", "discrimination",
                       "final_connections")}

    def vs_remove(metric: str) -> dict:
        d = np.array([j["branches"]["reactivate"][metric] - j["branches"]["remove"][metric] for j in jobs], float)
        base = float(np.mean([j["branches"]["remove"][metric] for j in jobs]))
        return assess(d, noise[metric], base, p)

    retained = all(j["region_memory_at_operation"] > 0 for j in jobs)
    readdress = all(j["theta_after_restore"]["share_changed"] > 0 for j in jobs)
    reentry_ = vs_remove("region_generation_after_reactivation")
    downstream = {m: vs_remove(m) for m in ("generation", "reachability", "discrimination", "final_connections")}
    down_hit = [m for m, r in downstream.items() if r["status"] == "DETECTED"]
    criteria = {"retained_prior_difference": retained, "re_addressability": readdress,
                "actual_re_entry": reentry_["status"] == "DETECTED", "downstream_difference": bool(down_hit)}
    removed = res["comparisons"].get("remove", {})
    dependence = any(isinstance(v, dict) and v.get("status") == "DETECTED" for v in removed.values())
    changes_trajectory = any(not j["branches"]["remove"]["bit_identical_to_intact"] for j in jobs)
    if all(criteria.values()):
        verdict = "HISTORY RE-ENTRY (all four criteria measured)"
    elif dependence:
        verdict = "HISTORY DEPENDENCE (re-entry criteria not all met)"
    elif changes_trajectory:
        verdict = ("HISTORY DEPENDENCE NOT DISTINGUISHED FROM TRAJECTORY NOISE (removal changes the trajectory, but no "
                   "measured effect exceeds the noise branch)")
    else:
        verdict = "NO EFFECT OF REMOVAL (bit-identical continuation)"
    return {"verdict": verdict, "criteria": criteria, "re_entry": reentry_, "downstream_vs_remove": downstream,
            "downstream_detected": down_hit,
            "note": "Measured in the simulated runtime under this configuration; a different region, window, size or "
                    "seed set can change the verdict. Not evidence about any system outside the simulation."}
