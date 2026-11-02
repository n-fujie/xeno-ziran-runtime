"""MEOS-0, fifth stage: Experiments F–K. Every function runs the real engine; no outcome is adjusted toward an expectation, and a counter-example or a null result is kept.

  F  multiple MFS: exhaustive search of every inclusion-minimal retaining set under eleven conditions, the classification of the components, route equivalence between the sets found
  G  history <-> M2 substitution: where M2 sensing replaces history and where it does not
  H  dynamic Address dependence: separated, moving, crossing and ambiguous configurations
  I  adaptive reconfiguration: controllers against stresses, the transitions between known MFS
  J  MFS x SSS region: where each MFS persists in (scale, size, speed)
  K  observation robustness across MFS

Each returns the frame of the earlier stages: seeds, fixed conditions, manipulated variable, measured variables, rows, null results, failures, unexpected outcomes and the interpretation limit.
"""

from __future__ import annotations

import itertools
import multiprocessing as mp
from collections import defaultdict
from typing import Any

from . import analysis as A
from . import engine as E
from . import experiments as X
from . import mfs5 as M
from . import reconf as RC
from . import routes5 as R
from . import stage4 as S4
from . import stats5 as ST

HONESTY = (
    "A formal model: these numbers describe how this engine's specified operation (a recursive cycle of two configurations, status ACTIVE) responds to the manipulation. They are not "
    "evidence about any physical, biological or ecological system, and a visual representation of a run is never evidence of the run."
)


def frame(name: str, seeds: tuple[int, ...], fixed: dict, manipulated: dict, measured: list[str], limit: str) -> dict:
    return {
        "experiment": name,
        "seeds": list(seeds),
        "fixed_conditions": fixed,
        "manipulated_variable": manipulated,
        "measured_variables": measured,
        "rows": [],
        "null_results": [],
        "failures": [],
        "unexpected": [],
        "interpretation_limit": f"{limit} {HONESTY}",
    }


def experiment_f(processes: int | None = None) -> dict:
    conds = M.conditions_f()
    out = frame(
        "F: multiple MFS, exhaustive search",
        M.SEARCH_SEEDS,
        {"horizon": M.HORIZON, "operation": "status ACTIVE at the horizon", "search": "every subset of the universe is the retained set once; a set persists only if it persists in every search seed", "confirmation_seeds": list(M.CONFIRM_SEEDS)},
        {"condition": [c["label"] for c in conds], "retained set": "all 2^n subsets of the universe of each condition"},
        ["inclusion-minimal retaining sets", "their paths, recovery capability, observability, digest", "necessary / sufficient / substitutable / null / redundant / destabilizing / jointly necessary per component", "route equivalence between the sets found"],
        "A set is minimal relative to the universe of components of the condition (the nine components of the earlier stages, plus the M2 tap where the condition has one); a component outside the universe cannot be found necessary.",
    )
    results: dict[str, dict] = {}
    for c in conds:
        r = M.search(c, processes=processes)
        results[c["id"]] = r
        out["rows"].append({"condition": c["id"], "label": c["label"], "universe_size": len(r["universe"]), "persisting_subsets": r["persisting_subsets"], "minimal_sets": r["minimal_count"], "seed_disagreeing_subsets": r["seed_disagreeing_subsets"],
                            "mfs": [{"id": m["id"], "cardinality": m["cardinality"], "route_kind": m["route_kind"], "retained": m["retained_components"], "paths_kept": m["retained_paths"], "persists_in_5_seeds": m["persists_in_confirmation_seeds"]} for m in r["mfs"]]})
        if r["minimal_count"] == 0:
            out["null_results"].append(f"{c['id']} ({c['label']}): no subset of the universe persists in every search seed: there is no retaining set under this condition")
        elif r["minimal_count"] == 1:
            out["null_results"].append(f"{c['id']} ({c['label']}): a single inclusion-minimal set exists (no second route under this condition)")
    out["by_condition"] = results
    out["across_conditions"] = M.classify_across(results)
    # distinct MFS across conditions: the same retained set under different conditions is one set seen under several conditions; sets of equal size with different components are different
    sets: dict[tuple, list[str]] = {}
    for r in results.values():
        for m in r["mfs"]:
            sets.setdefault(tuple(m["retained_components"]), []).append(m["id"])
    out["distinct_retained_sets"] = [{"retained": list(k), "cardinality": len(k), "found_as": v} for k, v in sorted(sets.items(), key=lambda kv: (len(kv[0]), kv[0]))]
    out["same_cardinality_different_components"] = [
        [list(a), list(b)] for a in sets for b in sets if len(a) == len(b) and a < b
    ]
    # equivalence: the first minimal set of each condition against every other set found (profiles of each distinct (condition, set) are computed once)
    profiles: dict[str, dict] = {}
    eq = []
    seen_sets: dict[tuple, str] = {}
    chosen: list[tuple[str, dict, tuple]] = []
    for cid, r in results.items():
        cond = next(c for c in conds if c["id"] == cid)
        for m in r["mfs"]:
            chosen.append((m["id"], cond, tuple(m["retained_components"])))
    # profile every MFS under its own condition; compare all pairs found under the same condition, and each set across the conditions it was found under
    for mid, cond, key in chosen:
        profiles[mid] = R.profile(cond, frozenset(key))
    by_cond: dict[str, list[str]] = {}
    for mid, cond, _ in chosen:
        by_cond.setdefault(cond["id"], []).append(mid)
    for cid, ids in by_cond.items():
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                eq.append({"condition": cid, "a": ids[i], "b": ids[j], **R.compare(profiles[ids[i]], profiles[ids[j]])})
    first_of: dict[tuple, str] = {}
    for mid, _cond, key in chosen:
        first_of.setdefault(key, mid)
    distinct_ids = list(first_of.values())
    already = {(e["a"], e["b"]) for e in eq}
    for i in range(len(distinct_ids)):  # distinct retained sets against each other (each set under the first condition it was found in)
        for j in range(i + 1, len(distinct_ids)):
            a_, b_ = distinct_ids[i], distinct_ids[j]
            if (a_, b_) not in already:
                eq.append({"condition": "between distinct retained sets", "a": a_, "b": b_, **R.compare(profiles[a_], profiles[b_])})
    del seen_sets
    out["profiles"] = profiles
    out["route_equivalence"] = eq
    out["levels"] = list(R.LEVELS)
    multi = [cid for cid, r in results.items() if r["minimal_count"] > 1]
    out["conditions_with_more_than_one_mfs"] = multi
    if not multi:
        out["unexpected"].append("no condition has more than one inclusion-minimal retaining set: one dominant MFS only, in this universe")
    return out


# ---------------------------------------------------------------------------------------------------- helpers
def pmap(fn: Any, items: list, processes: int | None = None, chunksize: int = 4) -> list:
    """Map ``fn`` over ``items`` in worker processes (the runs are independent and deterministic, so the order of completion does not matter)."""
    if processes == 1 or len(items) < 8:
        return [fn(i) for i in items]
    with mp.get_context("fork").Pool(processes or max(1, (mp.cpu_count() or 2) - 2)) as pool:
        return pool.map(fn, items, chunksize=chunksize)


def _active(rec: dict) -> bool:
    return rec["final_status"]["label"] == "ACTIVE"


# ---------------------------------------------------------------------------------------------------- G: history <-> M2 and the other alternatives
M2_VARIANTS: dict[str, dict | None] = {
    "none": None,
    "direct": {"sense": "direct", "weight": 4.0},
    "delayed(3)": {"sense": "delayed", "weight": 4.0, "delay": 3},
    "noisy(0.05)": {"sense": "noisy", "weight": 4.0, "noise": 0.05},
    "threshold(0.05)": {"sense": "threshold", "weight": 4.0, "threshold": 0.05},
}
RESOURCE_LEVELS: dict[str, dict] = {
    "reduced": {"environment": {"regrow": 0.01}, "power": {"charge": 0.2}},
    "normal": {},
    "oversupplied": {"environment": {"regrow": 0.06}, "power": {"charge": 1.0}},
}


def _g1_job(a: tuple) -> tuple:
    hist, m2, scale, speed, res, gain, seed = a
    over: dict[str, Any] = {"sss": {"scale": scale, "size": 1.0, "speed": speed}, **{k: dict(v) for k, v in RESOURCE_LEVELS[res].items()}}
    if gain != 1.0:
        over["coupling"] = {"gain": gain}
    if M2_VARIANTS[m2]:
        over["m2"] = dict(M2_VARIANTS[m2] or {})
    cfg = X.cfg_with(E.default_config(), seed=seed, horizon=240, **over)
    ivs = [{"tick": 0, "op": "REMOVE", "target": "history"}] if hist == "OFF" else []
    r = E.run_record(cfg, ivs)
    return (hist, m2, scale, speed, res, gain, seed, _active(r), len(r["cycles"]))


def experiment_g() -> dict:
    seeds = tuple(range(1, 11))
    out = frame(
        "G: history <-> M2 substitution, and the other alternatives",
        seeds,
        {"horizon": 240, "operation": "status ACTIVE at the horizon", "M2 weight": 4.0},
        {"G1 (scope of the substitution)": {"history": ["ON", "OFF (removed from tick 0)"], "M2 sensing": list(M2_VARIANTS), "SSS scale": [0.85, 1.0, 1.15], "SSS speed": [0.85, 1.0, 1.15], "resource": list(RESOURCE_LEVELS), "coupling gain": [0.6, 1.0, 1.4]},
         "G2 (alternatives among coupling, resource, renewal, history, M2: full factorial)": {"coupling": ["normal", "weakened", "interrupted", "restored"], "resource": ["normal", "reduced", "pulsed", "oversupplied"], "renewal": ["normal", "reduced", "disabled", "delayed"], "history": ["ON", "OFF"], "M2": ["none", "direct"]},
         "G3 (partial and delayed history)": ["history lag 8", "kappa x 0.5", "access of A1 only", "history OFF", "history ON"]},
        ["proportion of seeds ACTIVE at the horizon, with Wilson intervals", "per cell: is history needed, does M2 substitute", "alternatives that rescue a failing cell"],
        "A substitution is a property of cells of this grid of conditions and of the five M2 variants; a cell with ten seeds gives a proportion, not a certainty.",
    )
    # --- G1
    scales, speeds, gains = (0.85, 1.0, 1.15), (0.85, 1.0, 1.15), (0.6, 1.0, 1.4)
    jobs = [(h, m, sc, sp, rs, g, sd) for h in ("ON", "OFF") for m in M2_VARIANTS for sc in scales for sp in speeds for rs in RESOURCE_LEVELS for g in gains for sd in seeds]
    res = pmap(_g1_job, jobs)
    cell: dict[tuple, int] = defaultdict(int)
    cyc: dict[tuple, list[int]] = defaultdict(list)
    for h, m, sc, sp, rs, g, _sd, ok, nc in res:
        cell[(h, m, sc, sp, rs, g)] += ok
        cyc[(h, m, sc, sp, rs, g)].append(nc)
    n = len(seeds)
    classes: dict[str, dict[str, int]] = {m: defaultdict(int) for m in M2_VARIANTS if m != "none"}
    cell_rows: list[dict[str, Any]] = []
    for sc, sp, rs, g in itertools.product(scales, speeds, RESOURCE_LEVELS, gains):
        base_on, off_none = cell[("ON", "none", sc, sp, rs, g)], cell[("OFF", "none", sc, sp, rs, g)]
        row: dict[str, Any] = {"scale": sc, "speed": sp, "resource": rs, "coupling_gain": g, "ON_none": base_on, "OFF_none": off_none, "n": n}
        for m in M2_VARIANTS:
            if m == "none":
                continue
            off_m, on_m = cell[("OFF", m, sc, sp, rs, g)], cell[("ON", m, sc, sp, rs, g)]
            row[f"OFF_{m}"], row[f"ON_{m}"] = off_m, on_m
            if base_on <= 0.2 * n and off_none <= 0.2 * n:
                k = "no operation to substitute in (history ON and OFF both fail without M2)" + ("; M2 supplies one" if off_m >= 0.8 * n else "")
            elif off_none >= 0.8 * n:
                k = "history not needed here"
            elif base_on >= 0.8 * n and off_none <= 0.2 * n:
                k = "history needed; M2 substitutes" if off_m >= 0.8 * n else "history needed; M2 partly substitutes" if off_m > 0.2 * n else "history needed; M2 does not substitute"
            else:
                k = "mixed (intermediate proportions)"
            classes[m][k] += 1
            row[f"class_{m}"] = k
        cell_rows.append(row)
    out["rows"] = cell_rows
    out["G1_summary_by_m2_variant"] = {m: dict(v) for m, v in classes.items()}
    # --- scope: among the cells where history is needed, how often does each variant substitute, and by factor level
    scope: dict[str, Any] = {}
    for m in M2_VARIANTS:
        if m == "none":
            continue
        needed = [r for r in cell_rows if r["ON_none"] >= 0.8 * n and r["OFF_none"] <= 0.2 * n]
        subst = [r for r in needed if r[f"OFF_{m}"] >= 0.8 * n]
        entry: dict[str, Any] = {"cells_where_history_is_needed": len(needed), "cells_where_M2_substitutes": len(subst), "proportion": ST.proportion(len(subst), len(needed)) if needed else None, "by_factor": {}}
        for fac in ("scale", "speed", "resource", "coupling_gain"):
            levels: dict[str, Any] = {}
            for lv in sorted({r[fac] for r in needed}, key=str):
                nn = [r for r in needed if r[fac] == lv]
                levels[str(lv)] = ST.proportion(sum(1 for r in nn if r[f"OFF_{m}"] >= 0.8 * n), len(nn))
            entry["by_factor"][fac] = levels
        scope[m] = entry
    out["G1_scope_of_substitution"] = scope
    # seeds: the substitution at the default cell across the ten seeds, paired against history OFF without M2
    dflt = (1.0, 1.0, "normal", 1.0)
    paired = {}
    for m in M2_VARIANTS:
        if m == "none":
            continue
        a = [1.0 if any(r[:7] == ("OFF", "none", *dflt, sd) and r[7] for r in res) else 0.0 for sd in seeds]
        b = [1.0 if any(r[:7] == ("OFF", m, *dflt, sd) and r[7] for r in res) else 0.0 for sd in seeds]
        paired[m] = ST.compare_proportions(int(sum(b)), n, int(sum(a)), n)
    out["G1_default_cell_OFF_with_M2_vs_OFF_without"] = paired
    for m, e in scope.items():
        if e["cells_where_M2_substitutes"] == 0:
            out["null_results"].append(f"M2 {m}: in none of the {e['cells_where_history_is_needed']} cells where history is needed does it substitute")
        elif e["cells_where_M2_substitutes"] < e["cells_where_history_is_needed"]:
            out["unexpected"].append(f"M2 {m} substitutes for history in {e['cells_where_M2_substitutes']} of {e['cells_where_history_is_needed']} cells where history is needed: a conditional, not a general, substitute")
        else:
            out["unexpected"].append(f"M2 {m} substitutes for history in every one of the {e['cells_where_history_is_needed']} cells where it is needed on this grid (not generalised beyond the grid)")
    out.update(_g2(seeds=(1, 2, 3, 4, 5)))
    out.update(_g3(seeds))
    return out


RESTORING_LEVELS = {"coupling": "normal", "resource": "normal", "renewal": "normal", "history": "ON", "m2": "none"}


def compensations(rescues: list[dict]) -> dict:
    """Of the single changes that rescue a failing cell, those that merely put a factor back to its normal level (restoring) and those that change a factor to something other than normal
    (compensating: an oversupplied resource, a delayed renewal, a direct M2 tap, a restored coupling after an interruption, ...): the second kind is an alternative route."""
    comp = [r for r in rescues if next(iter(r["change"].values()))[1] != RESTORING_LEVELS[next(iter(r["change"]))]]
    by: dict[str, dict[str, int]] = {}
    for r in comp:
        (f, (a, b)), = r["change"].items()
        by.setdefault(f, {}).setdefault(f"{a} -> {b}", 0)
        by[f][f"{a} -> {b}"] += 1
    return {"restoring": len(rescues) - len(comp), "compensating": len(comp), "compensating_by_factor_and_change": by, "examples": comp[:12]}


COUPLING_LEVELS = ("normal", "weakened", "interrupted", "restored")
RESOURCE_G2 = ("normal", "reduced", "pulsed", "oversupplied")
RENEWAL_LEVELS = ("normal", "reduced", "disabled", "delayed")


def _g2_ivs(coupling: str, resource: str, renewal: str, history: str) -> list[dict]:
    ivs: list[dict] = []
    if coupling == "weakened":
        ivs.append({"tick": 100, "op": "RECONFIGURE", "path": "coupling.gain", "value": 0.6})
    elif coupling == "interrupted":
        ivs.append({"tick": 100, "op": "ISOLATE", "target": "interaction_channel"})
    elif coupling == "restored":
        ivs += [{"tick": 100, "op": "ISOLATE", "target": "interaction_channel"}, {"tick": 140, "op": "RECONNECT", "target": "interaction_channel"}]
    if resource == "reduced":
        ivs += [{"tick": 100, "op": "RECONFIGURE", "path": "environment.regrow", "value": 0.01}, {"tick": 100, "op": "RECONFIGURE", "path": "power.charge", "value": 0.2}]
    elif resource == "pulsed":
        ivs.append(X.pulse(100, 2.0))
    elif resource == "oversupplied":
        ivs += [{"tick": 100, "op": "RECONFIGURE", "path": "environment.regrow", "value": 0.06}, {"tick": 100, "op": "RECONFIGURE", "path": "power.charge", "value": 1.0}]
    if renewal == "reduced":
        ivs.append({"tick": 100, "op": "RECONFIGURE", "path": "environment.renew_efficiency", "value": 0.5})
    elif renewal == "disabled":
        ivs.append({"tick": 100, "op": "REMOVE", "target": "feedback"})
    elif renewal == "delayed":
        ivs.append({"tick": 100, "op": "RECONFIGURE", "path": "environment.renew_delay", "value": 6})
    if history == "OFF":
        ivs.append({"tick": 100, "op": "REMOVE", "target": "history"})
    return ivs


def _g2_job(a: tuple) -> tuple:
    coupling, resource, renewal, history, m2, seed = a
    over = {"m2": dict(M2_VARIANTS["direct"] or {})} if m2 == "direct" else {}
    r = E.run_record(X.cfg_with(E.default_config(), seed=seed, horizon=300, **over), _g2_ivs(coupling, resource, renewal, history))
    return (coupling, resource, renewal, history, m2, seed, _active(r))


def _g2(seeds: tuple[int, ...]) -> dict:
    """The full factorial of the five alternatives (4 x 4 x 4 x 2 x 2 = 256 cells) at a stress applied from tick 100; which single change rescues a failing cell."""
    jobs = [(c, r, n, h, m, sd) for c in COUPLING_LEVELS for r in RESOURCE_G2 for n in RENEWAL_LEVELS for h in ("ON", "OFF") for m in ("none", "direct") for sd in seeds]
    res = pmap(_g2_job, jobs)
    agg: dict[tuple, int] = defaultdict(int)
    for c, r, n, h, m, _sd, ok in res:
        agg[(c, r, n, h, m)] += ok
    ns = len(seeds)
    cells: list[dict[str, Any]] = [{"coupling": c, "resource": r, "renewal": n, "history": h, "m2": m, "active": agg[(c, r, n, h, m)], "n": ns} for c, r, n, h, m in itertools.product(COUPLING_LEVELS, RESOURCE_G2, RENEWAL_LEVELS, ("ON", "OFF"), ("none", "direct"))]
    factors = {"coupling": COUPLING_LEVELS, "resource": RESOURCE_G2, "renewal": RENEWAL_LEVELS, "history": ("ON", "OFF"), "m2": ("none", "direct")}
    marg: dict[str, Any] = {}
    for f, levels in factors.items():
        marg[f] = {lv: ST.proportion(sum(c["active"] for c in cells if c[f] == lv), ns * sum(1 for c in cells if c[f] == lv)) for lv in levels}
    rescues = []
    key = lambda c: (c["coupling"], c["resource"], c["renewal"], c["history"], c["m2"])  # noqa: E731
    by = {key(c): c for c in cells}
    for c in cells:
        if c["active"] > 0.2 * ns:
            continue
        for f, levels in factors.items():
            for lv in levels:
                if lv == c[f]:
                    continue
                k2 = dict(zip(("coupling", "resource", "renewal", "history", "m2"), key(c), strict=True))
                k2[f] = lv
                d = by[(k2["coupling"], k2["resource"], k2["renewal"], k2["history"], k2["m2"])]
                if d["active"] >= 0.8 * ns:
                    rescues.append({"failing_cell": {k: c[k] for k in factors}, "change": {f: [c[f], lv]}, "after": d["active"], "n": ns})
    nulls = [f for f, lv in marg.items() if max(v["p"] for v in lv.values()) - min(v["p"] for v in lv.values()) < 0.05]
    comp = compensations(rescues)
    return {"G2_cells": cells, "G2_marginal_proportions": marg, "G2_rescues_by_one_change": rescues, "G2_compensating_changes": comp, "G2_summary": {"cells": len(cells), "cells_failing": sum(1 for c in cells if c["active"] <= 0.2 * ns), "cells_persisting": sum(1 for c in cells if c["active"] >= 0.8 * ns), "rescuing_single_changes": len(rescues), "factors_with_no_marginal_effect": nulls}}


def _g3_job(a: tuple) -> tuple:
    name, m2, scale, seed = a
    over: dict[str, Any] = {"sss": {"scale": scale}}
    if m2 == "direct":
        over["m2"] = dict(M2_VARIANTS["direct"] or {})
    ivs: list[dict] = []
    if name == "history lag 8":
        over["history"] = {"lag": 8}
    elif name == "kappa x 0.5":
        over["history"] = {"kappa": E.default_config()["history"]["kappa"] * 0.5}
    elif name == "access of A1 only":
        over["history"] = {"access": {"A1": True, "A2": False}}
    elif name == "history OFF":
        ivs = [{"tick": 0, "op": "REMOVE", "target": "history"}]
    r = E.run_record(X.cfg_with(E.default_config(), seed=seed, horizon=240, **over), ivs)
    return (name, m2, scale, seed, _active(r), len(r["cycles"]))


def _g3(seeds: tuple[int, ...]) -> dict:
    names = ("history ON", "history lag 8", "kappa x 0.5", "access of A1 only", "history OFF")
    res = pmap(_g3_job, [(nm, m, sc, sd) for nm in names for m in ("none", "direct") for sc in (1.0, 1.15) for sd in seeds])
    rows = []
    for nm in names:
        for m in ("none", "direct"):
            for sc in (1.0, 1.15):
                rr = [r for r in res if r[:3] == (nm, m, sc)]
                rows.append({"history": nm, "m2": m, "scale": sc, "proportion_active": ST.proportion(sum(r[4] for r in rr), len(rr)), "mean_cycles": round(sum(r[5] for r in rr) / len(rr), 2)})
    return {"G3_partial_delayed_history": rows}


# ---------------------------------------------------------------------------------------------------- H: dynamic Address dependence
def _dyn(rec: dict) -> str:
    return S4.dynamics_digest(rec)


def _arr_cfg(a2x: int, a2y: int, a2speed: float, a1speed: float, seed: int, horizon: int = 300, a2r: int = 2, a1r: int = 2) -> dict:
    cfg = X.cfg_with(E.default_config(), seed=seed, horizon=horizon)
    cfg["entities"]["A2"]["pos"] = [a2x, a2y]
    cfg["entities"]["A2"]["speed"] = a2speed
    cfg["entities"]["A1"]["speed"] = a1speed
    cfg["entities"]["A2"]["sensor_radius"] = a2r
    cfg["entities"]["A1"]["sensor_radius"] = a1r
    return cfg


def _sep(rec: dict, a: int, b: int) -> list[float]:
    return [abs(f["A1"]["x"] - f["A2"]["x"]) + abs(f["A1"]["y"] - f["A2"]["y"]) for f in rec["frames"][a:b]]


def _h_screen_job(a: tuple) -> dict:
    a2x, a2y, sp, a2r, a1r, seed = a
    rec = E.run_record(_arr_cfg(a2x, a2y, sp, 1.0, seed, 300, a2r, a1r), [])
    sep = _sep(rec, 60, 300)
    a2 = [(f["A2"]["x"], f["A2"]["y"]) for f in rec["frames"]]
    moved_late = sum(1 for p, q in zip(a2[60:], a2[61:], strict=False) if p != q)
    return {"a2x": a2x, "a2y": a2y, "speed": sp, "a2r": a2r, "a1r": a1r, "seed": seed, "active": _active(rec), "separation_after_60": round(sum(sep) / len(sep), 2), "a2_moves_after_60": moved_late}


FAULTS: dict[str, dict] = {
    "loss": {"mode": "loss"},
    "reassign (to 11,6; not restored)": {"mode": "reassign", "x": 11, "y": 6},
    "fragment (50 %)": {"mode": "fragment", "fraction": 0.5},
    "collision": {"mode": "collision"},
    "partial (50 %)": {"mode": "partial", "fraction": 0.5},
    "delayed update (to 11,6; 20 ticks)": {"mode": "delayed", "x": 11, "y": 6, "delay": 20},
    "stale (30 ticks)": {"mode": "stale", "duration": 30},
}


def _h_job(a: tuple) -> dict:
    arr, fault, target, tick, seed = a
    cfg = _arr_cfg(arr["a2x"], arr["a2y"], arr["speed"], 1.0, seed, 300, arr["a2r"], arr["a1r"])
    ctl = E.run_record(cfg, [])
    spec = {"tick": tick, "op": "ADDRESS", "target": target, **FAULTS[fault]}
    ivs = [spec]
    if spec["mode"] not in ("reassign", "delayed", "stale"):
        ivs.append({"tick": tick + 40, "op": "ADDRESS", "target": target, "mode": "restore"})
    rec = E.run_record(cfg, ivs)
    return {"arr": arr["id"], "fault": fault, "target": target, "tick": tick, "seed": seed, "collapsed": not _active(rec), "dynamics_changed": _dyn(rec) != _dyn(ctl), "control_active": _active(ctl)}


def _h_swap_job(a: tuple) -> dict:
    arr, tick, seed = a
    cfg = _arr_cfg(arr["a2x"], arr["a2y"], arr["speed"], 1.0, seed, 300, arr["a2r"], arr["a1r"])
    ctl = E.run_record(cfg, [])
    f = ctl["frames"][tick]
    a1, a2 = (f["A1"]["x"], f["A1"]["y"]), (f["A2"]["x"], f["A2"]["y"])
    ivs = [{"tick": tick, "op": "RECONFIGURE", "path": f"entities.A1.{ax}", "value": v} for ax, v in (("x", a2[0]), ("y", a2[1]))] + [{"tick": tick, "op": "RECONFIGURE", "path": f"entities.A2.{ax}", "value": v} for ax, v in (("x", a1[0]), ("y", a1[1]))]
    rec = E.run_record(cfg, ivs)
    return {"arr": arr["id"], "fault": "swap of the two positions (crossing)", "target": "both", "tick": tick, "seed": seed, "collapsed": not _active(rec), "dynamics_changed": _dyn(rec) != _dyn(ctl), "control_active": _active(ctl), "positions_differ": a1 != a2}


def experiment_h() -> dict:
    seeds = (1, 2, 3, 4, 5)
    out = frame(
        "H: dynamic Address dependence",
        seeds,
        {"horizon": 300, "fault": "applied at the stated tick; restored 40 ticks later except reassignment, delayed update and stale", "control": "the same arrangement and seed without the fault (paired)"},
        {"arrangement": "A2's start cell and speed (screened first: which arrangements keep the operation and keep the configurations apart or moving)", "fault": list(FAULTS) + ["swap of the two positions (crossing)"], "target": ["A1", "A2"], "timing": ["tick 12 (A2 may still be moving)", "tick 100 (settled)"]},
        ["collapse against the matched control", "whether the dynamics changed at all (frames, not the intervention log)", "arrangements in which the two configurations are apart"],
        "The arrangements are those a 14 x 14 grid with these two configurations allows to persist; 'moving' and 'apart' are measured on the controls, not assumed. Address matters or does not matter here only for the arrangements and faults listed.",
    )
    grid = [(x, sp, a2r, a1r) for x in (5, 7, 9, 11) for sp in (0.25, 1.0) for a2r in (2, 4, 6) for a1r in (2, 4)]
    screen = pmap(_h_screen_job, [(x, 6, sp, a2r, a1r, sd) for x, sp, a2r, a1r in grid for sd in seeds])
    arrs = []
    for x, sp, a2r, a1r in grid:
        rr = [r for r in screen if r["a2x"] == x and r["speed"] == sp and r["a2r"] == a2r and r["a1r"] == a1r]
        act = sum(r["active"] for r in rr)
        sepm = sum(r["separation_after_60"] for r in rr) / len(rr)
        mv = sum(r["a2_moves_after_60"] for r in rr) / len(rr)
        arrs.append({"id": f"A2@{x},6 speed {sp} radii A2 {a2r} A1 {a1r}", "a2x": x, "a2y": 6, "speed": sp, "a2r": a2r, "a1r": a1r, "active_seeds": act, "mean_separation_after_60": round(sepm, 2), "a2_moves_after_60": round(mv, 1), "separated": sepm >= 2.0, "moving_late": mv >= 3.0})
    out["arrangements_screened"] = arrs
    usable = [a for a in arrs if a["active_seeds"] == len(seeds)]
    out["arrangements_used"] = [a["id"] for a in usable]
    if not any(a["separated"] for a in usable):
        out["unexpected"].append("no screened arrangement keeps the two configurations apart (mean separation >= 2 cells after tick 60) and the operation active: A2 walks to A1 in every arrangement that persists")
    if not any(a["moving_late"] for a in usable):
        out["unexpected"].append("in no persisting arrangement does A2 still move after tick 60: the configurations are static once settled")
    jobs = [(a, f, tg, tk, sd) for a in usable for f in FAULTS for tg in ("A1", "A2") for tk in (12, 100) for sd in seeds]
    res = pmap(_h_job, jobs)
    swaps = pmap(_h_swap_job, [(a, tk, sd) for a in usable for tk in (12, 100) for sd in seeds])
    rows = []
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in [*res, *swaps]:
        groups[(r["arr"], r["fault"], r["target"], r["tick"])].append(r)
    for (arr, fault, target, tick), rr in groups.items():
        k_c, k_d = sum(r["collapsed"] for r in rr), sum(r["dynamics_changed"] for r in rr)
        row = {"arrangement": arr, "fault": fault, "target": target, "tick": tick, "n": len(rr), "collapsed": ST.proportion(k_c, len(rr)), "dynamics_changed": ST.proportion(k_d, len(rr))}
        row["class"] = "null (dynamics identical to the control)" if k_d == 0 else "dynamics changed, no collapse" if k_c == 0 else "collapse"
        rows.append(row)
    out["rows"] = rows
    out["summary_by_class"] = {c: sum(1 for r in rows if r["class"].startswith(c)) for c in ("null", "dynamics changed", "collapse")}
    # where Address becomes operationally important: collapses, by arrangement kind, fault and timing
    by_kind: dict[str, dict[str, int]] = {}
    for r in rows:
        a = next(x for x in arrs if x["id"] == r["arrangement"])
        kind = ("apart" if a["separated"] else "together") + (", moving late" if a["moving_late"] else "")
        e = by_kind.setdefault(kind, {"cells": 0, "collapse": 0, "dynamics_changed_only": 0, "null": 0})
        e["cells"] += 1
        e["collapse"] += r["class"] == "collapse"
        e["dynamics_changed_only"] += r["class"].startswith("dynamics changed")
        e["null"] += r["class"].startswith("null")
    out["summary_by_arrangement_kind"] = by_kind
    by_fault: dict[str, dict[str, int]] = {}
    for r in rows:
        e = by_fault.setdefault(r["fault"], {"cells": 0, "collapse": 0, "null": 0})
        e["cells"] += 1
        e["collapse"] += r["class"] == "collapse"
        e["null"] += r["class"].startswith("null")
    out["summary_by_fault"] = by_fault
    for r in rows:
        if r["class"].startswith("null"):
            out["null_results"].append(f"{r['fault']} on {r['target']} at tick {r['tick']} in {r['arrangement']}: dynamics identical to the control in all {r['n']} seeds")
    # the Stage 4 strict nulls: collision and stale at tick 100 in the default (together) arrangement, kept as they were
    d = [r for r in rows if r["arrangement"] == "A2@5,6 speed 1.0 radii A2 2 A1 2" and r["tick"] == 100 and r["fault"] in ("collision", "stale (30 ticks)")]
    out["stage4_strict_nulls_reproduced"] = [{"fault": r["fault"], "target": r["target"], "class": r["class"]} for r in d]
    return out


# ---------------------------------------------------------------------------------------------------- I: adaptive reconfiguration
STRESS_TICK = 100
SCENARIOS: dict[str, tuple[list[dict], set[str]]] = {
    "no stress (control for false switches)": ([], set()),
    "history lost": ([{"tick": STRESS_TICK, "op": "REMOVE", "target": "history"}], {"history"}),
    "coupling weakened (gain 0.5)": ([{"tick": STRESS_TICK, "op": "RECONFIGURE", "path": "coupling.gain", "value": 0.5}], {"coupling"}),
    "resource reduced": ([{"tick": STRESS_TICK, "op": "RECONFIGURE", "path": "environment.regrow", "value": 0.01}, {"tick": STRESS_TICK, "op": "RECONFIGURE", "path": "power.charge", "value": 0.2}], {"resource"}),
    "renewal efficiency 0.6": ([{"tick": STRESS_TICK, "op": "RECONFIGURE", "path": "environment.renew_efficiency", "value": 0.6}], {"renewal", "resource"}),
    "renewal disabled": ([{"tick": STRESS_TICK, "op": "REMOVE", "target": "feedback"}], {"renewal", "resource"}),
    "Address degraded (A2 partial 50 %)": ([{"tick": STRESS_TICK, "op": "ADDRESS", "target": "A2", "mode": "partial", "fraction": 0.5}], {"address"}),
}
CONTROLLERS = ("none", "fixed", "adaptive", "adaptive_shed", "delayed", "noisy")


def _i_job(a: tuple) -> dict:
    scen, kind, seed, library, arrangement = a
    stress, expected = SCENARIOS[scen]
    cfg = X.cfg_with(E.default_config(), seed=seed, horizon=300)
    ivs = [{"tick": 0, "op": "ROUTE", "m2": {"sense": "none"}}, *stress] if arrangement["tap"] else list(stress)  # the tap is installed and dormant
    ctl = None if kind == "none" else RC.Controller(kind, library, arrangement, noise=0.05, seed=seed)
    rec = RC.run_controlled(cfg, ivs, ctl)
    frames = rec["frames"]
    after = [f["status"] for f in frames[STRESS_TICK:]]
    collapsed_at = next((i + STRESS_TICK for i, s in enumerate(after) if s == "COLLAPSED"), None)
    recovered_at = next((i + collapsed_at for i, s in enumerate(frames[collapsed_at:] and [f["status"] for f in frames[collapsed_at:]] or []) if s == "ACTIVE"), None) if collapsed_at is not None else None
    sw = RC.switch_outcomes(rec, STRESS_TICK)
    return {
        "scenario": scen, "controller": kind, "seed": seed, "active_at_end": _active(rec), "collapsed_after_stress": collapsed_at is not None, "collapse_tick": collapsed_at,
        "recovered": recovered_at is not None and _active(rec), "time_to_recovery": None if recovered_at is None or collapsed_at is None else recovered_at - collapsed_at,
        "energy": X.trace_metrics(rec)["cumulative_energy_use"], "resource_throughput": X.trace_metrics(rec)["resource_throughput"],
        "switches": sw, "switch_count": len(sw), "switching_cost": sum(s["cost"] for s in sw),
        "false_switches": sum(1 for e in rec["controller"]["log"] if e["kind"] == "switch" and not (set(e["trigger"]) & expected)),
        "decisions_without_route": sum(1 for e in rec["controller"]["log"] if e["kind"] == "decide" and str(e.get("outcome", "")).startswith("no known route")),
        "state_changes_after_stress": sum(1 for a, b in zip(after, after[1:], strict=False) if a != b),
        "replay_identical": E.replay(rec)["identical"], "result_digest": rec["result_digest"], "log": rec["controller"]["log"],
    }


def experiment_i(f: dict | None = None) -> dict:
    seeds = tuple(range(1, 11))
    if f is None:
        raise ValueError("experiment I needs the library of experiment F")
    library = RC.library_from(f["by_condition"])
    arrangement = {"tap": M.M2_BASE, "tap_feature": "direct", "universe": M.COMPONENTS5}
    out = frame(
        "I: adaptive reconfiguration between known MFS",
        seeds,
        {"horizon": 300, "stress tick": STRESS_TICK, "arrangement": "the full arrangement with the M2 tap installed and dormant (sense none) from tick 0; history, coupling, resource and renewal in place", "library": f"{len(library)} MFS of experiment F", "sensing window": RC.WINDOW, "controller start": 60},
        {"scenario": list(SCENARIOS), "controller": list(CONTROLLERS)},
        ["persistence at the end, collapse, recovery, time to recovery", "resource / energy cost", "switching cost (components enabled)", "false switches (trigger not belonging to the stress)", "unnecessary switches (the no-reconfiguration control stayed ACTIVE throughout)", "instability after the stress (changes of state)", "replay of the recorded schedule without the controller"],
        "The controller can only enable components of an MFS in its library and only senses five features; the library is that of experiment F. A reconfiguration can only help where a route exists in the library.",
    )
    jobs = [(sc, k, sd, library, arrangement) for sc in SCENARIOS for k in CONTROLLERS for sd in seeds]
    res = pmap(_i_job, jobs, chunksize=2)
    by: dict[tuple, list[dict]] = defaultdict(list)
    for r in res:
        by[(r["scenario"], r["controller"])].append(r)
    rows = []
    for sc in SCENARIOS:
        ctl_none = {r["seed"]: r for r in by[(sc, "none")]}
        for k in CONTROLLERS:
            rr = by[(sc, k)]
            n = len(rr)
            unnecessary = sum(r["switch_count"] for r in rr if ctl_none[r["seed"]]["active_at_end"] and not ctl_none[r["seed"]]["collapsed_after_stress"])
            ttr = [r["time_to_recovery"] for r in rr if r["time_to_recovery"] is not None]
            row = {
                "scenario": sc, "controller": k, "n": n, "persisted": ST.proportion(sum(r["active_at_end"] for r in rr), n), "collapsed": ST.proportion(sum(r["collapsed_after_stress"] for r in rr), n),
                "recovered": ST.proportion(sum(r["recovered"] for r in rr), sum(r["collapsed_after_stress"] for r in rr) or 1) if any(r["collapsed_after_stress"] for r in rr) else None,
                "median_time_to_recovery": float(sorted(ttr)[len(ttr) // 2]) if ttr else None, "mean_energy": round(sum(r["energy"] for r in rr) / n, 2),
                "mean_switches": round(sum(r["switch_count"] for r in rr) / n, 2), "mean_switching_cost": round(sum(r["switching_cost"] for r in rr) / n, 2),
                "false_switches": sum(r["false_switches"] for r in rr), "unnecessary_switches": unnecessary, "decisions_without_route": sum(r["decisions_without_route"] for r in rr),
                "mean_state_changes_after_stress": round(sum(r["state_changes_after_stress"] for r in rr) / n, 2),
            }
            if k != "none":
                a_, b_ = ctl_none, {r["seed"]: r for r in rr}
                row["vs_none_persistence"] = ST.compare_proportions(sum(r["active_at_end"] for r in rr), n, sum(r["active_at_end"] for r in ctl_none.values()), len(ctl_none))
                row["vs_none_energy_paired"] = ST.compare_paired([a_[s]["energy"] for s in sorted(a_)], [b_[s]["energy"] for s in sorted(a_)])
            rows.append(row)
    out["rows"] = rows
    out["all_replays_identical"] = all(r["replay_identical"] for r in res)
    out["runs"] = len(res)
    trans: dict[tuple, list[dict]] = defaultdict(list)
    for r in res:
        for s in r["switches"]:
            trans[(r["controller"], s["from"], s["to"], ",".join(s["trigger"]))].append(s)
    out["transitions"] = [
        {"controller": c, "from_mfs": fr, "to_mfs": to, "trigger": tr, "count": len(v), "success_preserved_at_end": ST.proportion(sum(x["preserved_at_end"] for x in v), len(v)), "mean_cost": round(sum(x["cost"] for x in v) / len(v), 2),
         "mean_operation_lost_ticks_after": round(sum(x["operation_lost_ticks_after"] for x in v) / len(v), 1), "mean_recovery_latency": (round(sum(x["recovery_latency"] for x in v if x["recovery_latency"] is not None) / max(1, sum(1 for x in v if x["recovery_latency"] is not None)), 1) if any(x["recovery_latency"] is not None for x in v) else None)}
        for (c, fr, to, tr), v in sorted(trans.items())
    ]
    # the verdicts, both ways
    for sc in SCENARIOS:
        none_p = next(r for r in rows if r["scenario"] == sc and r["controller"] == "none")["persisted"]["p"]
        for k in ("adaptive", "adaptive_shed", "fixed", "delayed", "noisy"):
            row = next(r for r in rows if r["scenario"] == sc and r["controller"] == k)
            if row["persisted"]["p"] < none_p:
                out["unexpected"].append(f"{k} reconfiguration under '{sc}' persisted LESS than no reconfiguration ({row['persisted']['p']} against {none_p}): harmful here")
            elif row["persisted"]["p"] == none_p:
                out["null_results"].append(f"{k} reconfiguration under '{sc}': persistence equal to no reconfiguration ({none_p})")
    out["observation_strategy_revision"] = _observer_revision(seeds)
    return out


def _observer_revision(seeds: tuple[int, ...]) -> dict:
    """An observer that starts at sampling interval 4 and halves its interval whenever, over the last 48 ticks, it has resolved no cycle (checked every 12 ticks from tick 60). Success: at
    the end its conclusion equals the run's. A revision that does not help (the run really is collapsed) is a false switch."""
    scen = {"operation persists": [], "operation collapses (cut 100-150)": X.INTERRUPTION, "collapses and recovers": [*X.INTERRUPTION, X.pulse(151, 2.0)]}
    rows = []
    for name, ivs in scen.items():
        per = []
        for sd in seeds:
            rec = E.run_record(X.cfg_with(E.default_config(), seed=sd, horizon=360), ivs)
            interval, revisions = 4, []
            for t in range(60, 360, 12):
                part = {"events": [e for e in rec["events"] if e["tick"] <= t], "frames": rec["frames"][: t + 1]}
                cyc = A._observed_cycle_ticks(part, {**A.FULL_OBSERVATION, "sampling_interval": interval, "threshold": None, "occluder": None, "address_resolution": None})
                if not [c for c in cyc if t - 48 < c <= t] and interval > 1:
                    revisions.append({"tick": t, "from": interval, "to": max(1, interval // 2)})
                    interval = max(1, interval // 2)
            o = A.observe(rec, {"sampling_interval": interval})
            per.append({"revisions": revisions, "final_interval": interval, "operational": o["operational_state"], "observed": o["observed_state"], "agrees": o["observed_state"] == o["operational_state"],
                        "no_revision_would_agree": A.observe(rec, {"sampling_interval": 4})["observed_state"] == o["operational_state"]})
        rows.append({"scenario": name, "n": len(per), "agree_after_revision": ST.proportion(sum(p["agrees"] for p in per), len(per)), "agree_without_revision": ST.proportion(sum(p["no_revision_would_agree"] for p in per), len(per)),
                     "mean_revisions": round(sum(len(p["revisions"]) for p in per) / len(per), 2), "revisions_in_collapsed_runs_that_could_not_help": sum(len(p["revisions"]) for p in per if p["operational"] == "COLLAPSED")})
    return {"rule": "interval 4; halve when no cycle was resolved over the last 48 ticks (checked every 12 ticks from tick 60)", "rows": rows}


# ---------------------------------------------------------------------------------------------------- J: MFS x SSS region
SSS_GRID = [(sc, sz, sp) for sc in (0.75, 1.0, 1.25) for sz in (0.75, 1.0, 1.25) for sp in (0.75, 1.0, 1.25)]
SSS_AXES = {"scale": [0.5, 0.75, 1.0, 1.1, 1.25, 1.5, 2.0], "size": [0.5, 0.75, 1.0, 1.1, 1.25, 1.5, 2.0], "speed": [0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0]}


def _distinct_mfs(f: dict) -> list[dict]:
    seen, out = set(), []
    for cid, r in f["by_condition"].items():
        for m in r["mfs"]:
            key = (cid, tuple(m["retained_components"]))
            if key not in seen:
                seen.add(key)
                out.append({"id": m["id"], "cid": cid, "retained": m["retained_components"]})
    return out


def _j_job(a: tuple) -> dict:
    mid, cid, retained, sc, sz, sp = a
    cond = next(c for c in M.conditions_f() if c["id"] == cid)
    p = R.sss_point(cond, frozenset(retained), sc, sz, sp)
    return {"mfs": mid, "scale": sc, "size": sz, "speed": sp, "region": p["region"], "class": p["class"]}


def experiment_j(f: dict | None = None) -> dict:
    assert f is not None
    mfs = _distinct_mfs(f)
    out = frame(
        "J: MFS x SSS region",
        (1, 2),
        {"definitions": "ACTIVE at ticks 239 and 479 in every seed; COLLAPSED at 239 in every seed; otherwise METASTABLE; RECOVERY-CAPABLE = collapsed but active after a pulse of 2.0 at 300; OBSERVATION-SENSITIVE = active but an observation at interval 2 concludes otherwise", "horizon": 480},
        {"MFS": [m["id"] for m in mfs], "grid": "scale, size, speed in {0.75, 1.0, 1.25}^3", "axes": SSS_AXES},
        ["region of every grid point and axis value for every MFS", "per MFS: active, metastable, collapse, observation-sensitive and recovery-capable ranges along each axis"],
        "Two seeds per point; a range is a statement about the scanned values, not between them. The default setting (1, 1, 1) is the point for which the MFS was found.",
    )
    jobs = [(m["id"], m["cid"], m["retained"], *pt) for m in mfs for pt in SSS_GRID]
    for m in mfs:
        for ax, vals in SSS_AXES.items():
            for v in vals:
                pt = {"scale": 1.0, "size": 1.0, "speed": 1.0}
                pt[ax] = v
                jobs.append((m["id"], m["cid"], m["retained"], pt["scale"], pt["size"], pt["speed"]))
    res = pmap(_j_job, jobs, chunksize=2)
    seen_keys: set[tuple] = set()
    uniq = []
    for r in res:
        k = (r["mfs"], r["scale"], r["size"], r["speed"])
        if k not in seen_keys:
            seen_keys.add(k)
            uniq.append(r)
    out["points"] = uniq
    summaries = []
    for m in mfs:
        mine = [r for r in uniq if r["mfs"] == m["id"]]
        entry: dict[str, Any] = {"mfs": m["id"], "condition": m["cid"], "retained": m["retained"], "default_setting_region": next((r["region"] for r in mine if (r["scale"], r["size"], r["speed"]) == (1.0, 1.0, 1.0)), None), "regions_on_grid": {}, "ranges_along_axes": {}}
        for reg in ("ACTIVE", "OBSERVATION-SENSITIVE", "METASTABLE", "RECOVERY-CAPABLE", "COLLAPSED"):
            entry["regions_on_grid"][reg] = sum(1 for r in mine if r["region"] == reg and (r["scale"], r["size"], r["speed"]) in SSS_GRID)
        entry["regions_on_grid"]["operationally active (ACTIVE or OBSERVATION-SENSITIVE)"] = entry["regions_on_grid"]["ACTIVE"] + entry["regions_on_grid"]["OBSERVATION-SENSITIVE"]
        for ax, vals in SSS_AXES.items():
            rng: dict[str, list[float]] = {}
            groups = {"operationally active": ("ACTIVE", "OBSERVATION-SENSITIVE"), "OBSERVATION-SENSITIVE": ("OBSERVATION-SENSITIVE",), "METASTABLE": ("METASTABLE",), "RECOVERY-CAPABLE": ("RECOVERY-CAPABLE",), "COLLAPSED": ("COLLAPSED",)}
            for name, regs in groups.items():
                hit = [v for v in vals if any(r["region"] in regs and r[ax] == v and all(r[o] == 1.0 for o in ("scale", "size", "speed") if o != ax) for r in mine)]
                if hit:
                    rng[name] = [min(hit), max(hit)]
            entry["ranges_along_axes"][ax] = rng
        summaries.append(entry)
    out["rows"] = summaries
    # do different MFS have different SSS islands?
    islands: dict[Any, list[str]] = {}
    for e in summaries:
        act = ()
        sig = tuple((ax, tuple(e["ranges_along_axes"][ax].get("operationally active", []))) for ax in SSS_AXES)
        islands.setdefault((act, sig), []).append(e["mfs"])
    out["distinct_islands"] = [{"mfs": v, "operationally_active_ranges_along_the_axes": {ax: list(rr) for ax, rr in sig}} for (_, sig), v in islands.items()]
    if len(islands) == 1:
        out["unexpected"].append("every MFS scanned has the same SSS island: no MFS-specific region on these scans")
    for e in summaries:
        if not e["regions_on_grid"]["operationally active (ACTIVE or OBSERVATION-SENSITIVE)"]:
            out["null_results"].append(f"{e['mfs']}: no ACTIVE point on the grid (its operation does not persist anywhere on it)")
    return out


# ---------------------------------------------------------------------------------------------------- K: observation robustness across MFS
OBS_SWEEPS: dict[str, list[float]] = {"sampling_interval": [1, 2, 3, 4, 6, 8], "spatial_stride": [1, 2, 3, 4], "threshold": [0.0, 0.05, 0.1, 0.2, 0.3, 0.5]}


def experiment_k(f: dict | None = None) -> dict:
    assert f is not None
    mfs = _distinct_mfs(f)
    out = frame(
        "K: observation robustness across MFS",
        M.CONFIRM_SEEDS,
        {"horizon": 240, "operation": "unperturbed run of the retained set", "observation sweeps": OBS_SWEEPS},
        {"MFS": [m["id"] for m in mfs]},
        ["operational robustness (survival of the perturbation battery)", "observational robustness (agreement of the observer's conclusion with the run over the observation settings)", "addressability (survival of the Address fault battery)", "recoverability (recovery after an interruption and a pulse)", "per sweep: the first value at which the observer disagrees"],
        "The four robustness scores are kept apart on purpose: a set that is unobservable is not thereby a set that failed. Scores are proportions over the confirmation seeds and the settings of each battery.",
    )
    rows = []
    profiles = f["profiles"]
    for m in mfs:
        pr = profiles.get(m["id"])
        cond = next(c for c in M.conditions_f() if c["id"] == m["cid"])
        base_ivs = M.retained_interventions(cond, frozenset(m["retained"]))
        recs = [E.run_record(M._config(cond, sd, 240), base_ivs) for sd in M.CONFIRM_SEEDS]
        first: dict[str, Any] = {}
        for param, vals in OBS_SWEEPS.items():
            hit = next((v for v in vals if any(A.observe(r, {param: v})["observed_state"] != A.observe(r, {param: v})["operational_state"] for r in recs)), None)
            first[param] = hit
        sens = pr["perturbation_sensitivity"]
        rc = pr["recovery"]
        rows.append({
            "mfs": m["id"], "condition": m["cid"], "retained": m["retained"],
            "operational_robustness": round(1 - sum(sens.values()) / len(sens), 3), "observational_robustness": pr["observational_robustness"], "addressability": round(1 - pr["address_dependence"], 3),
            "recoverability": (round(rc["with_pulse"] / rc["seeds"], 3) if rc.get("testable") else None), "operation_preserved": pr["preserved_operation"],
            "first_observation_value_that_disagrees": first, "observed_vs_operational_at_interval_2": A.observe(recs[0], {"sampling_interval": 2})["observability"]["status"],
        })
        if pr["preserved_operation"] == 1.0 and pr["observational_robustness"] < 0.5:
            out["unexpected"].append(f"{m['id']} keeps the operation in every seed but the observer agrees with it in only {pr['observational_robustness']:.2f} of the settings: unobservable, not failed")
    out["rows"] = rows
    obs = [r["observational_robustness"] for r in rows]
    out["spread"] = {"observational_robustness_min": min(obs), "max": max(obs)}
    if rows and max(obs) - min(obs) < 0.05:
        out["null_results"].append("observational robustness is the same (within 0.05) for every MFS: the observer's view does not separate them")
    return out
