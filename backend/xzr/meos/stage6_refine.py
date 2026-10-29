"""MEOS-0, sixth stage, Pipeline B: refinement at one-tick and fine-magnitude resolution of what Pipeline A found on a coarse grid.

  B1  timing windows         for the settings Pipeline A found effective (or nearly), every action tick from 101 to 170: earliest effective tick, latest effective tick, the effective interval(s), the region where recovery is still possible after the collapse, and the region where it is not.
  B2  resource overshoot      a resource pulse of 0.1 to 6.0 in steps of 0.1 at the decision tick, on every stress: insufficient / effective / overshoot / delayed secondary collapse.
  B3  minimum intervention    the weakest restoration (coupling gain, renewal efficiency), the smallest pulse (alone, and with a restoration of the damaged Address or renewal) at the ticks where they work.
  B4  stage 5 consistency     the M2 tap on 'history lost' under the stage 5 conditions (horizon 300, ACTIVE at the end) and under the stage 6 conditions (three horizons, sustained, no secondary collapse).

A tick or a magnitude is *effective* only if the setting is effective on all five exploration seeds AND all five validation seeds; both counts are saved (exploration and validation are never merged). The words 'latest successful repair tick' and 'earliest irreversible tick'
are about the tested action space: the settings listed in the output, nothing else.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from . import repair6 as R
from . import stage5_experiments as X5
from . import stage6_experiments as S6

FINE_TICKS = tuple(range(101, 171))
SEEDS_ALL = R.SEARCH_SEEDS + R.VALIDATION_SEEDS


def _job(a: tuple) -> dict:
    """One run of a list of parts at a tick: returns the compact row plus the shape of the post-action status sequence (for overshoot / delayed secondary collapse)."""
    stress_id, parts, t, seed = a
    st = R.STRESSES[stress_id]
    reps: list[dict] = []
    for aid, mag, dur in parts:
        reps += R.build_action(aid, st, mag, t, dur)
    rec = R.run(st, sorted(reps, key=lambda i: i["tick"]), seed)
    o = R.evaluate(rec, R.reference(seed), reps, t)
    s = [f["status"] for f in rec["frames"]]
    stretches = [(a_, b_) for a_, b_ in S6_runs(s, t) if b_ - a_ >= R.W]
    first_collapse = next((i for i in range(t, len(s)) if s[i] == "COLLAPSED"), None)
    h = o["horizons"]
    return {"stress": stress_id, "parts": [list(p) for p in parts], "t": t, "seed": seed, "ok": [h[k]["success"] for k in ("short", "medium", "long")], "outcome": [h[k]["outcome"] for k in ("short", "medium", "long")], "secondary": h["long"]["secondary_collapse"],
            "exhausted": h["long"]["resource_exhausted"], "latency": h["long"]["latency"], "first_collapse_after_action": first_collapse, "active_stretch": (stretches[0][1] - stretches[0][0]) if stretches else 0, "raw": o["costs"]["raw"], "norm": o["costs"]["normalised"]}


def S6_runs(s: list[str], lo: int) -> list[tuple[int, int]]:
    return R._runs(s, lo, len(s), "ACTIVE")


def effective_row(r: dict) -> bool:
    return all(r["ok"]) and not r["secondary"] and not r["exhausted"]


def grid(stress_id: str, parts_of: Any, ticks: tuple[int, ...], magnitudes: tuple[float, ...], seeds: tuple[int, ...] = SEEDS_ALL, processes: int | None = None) -> dict[tuple, list[dict]]:
    """Run ``parts_of(magnitude)`` (a list of (action, magnitude, duration)) at every tick on every seed; returns {(magnitude, tick): rows}."""
    keys = [(m, t) for m in magnitudes for t in ticks for _ in seeds]
    jobs = [(stress_id, tuple(parts_of(m)), t, sd) for m in magnitudes for t in ticks for sd in seeds]
    out: dict[tuple, list[dict]] = defaultdict(list)
    for k, r in zip(keys, X5.pmap(_job, jobs, processes, chunksize=8), strict=True):
        out[k].append(r)
    return dict(out)


def cell_status(rows: list[dict]) -> dict:
    ex = [r for r in rows if r["seed"] in R.SEARCH_SEEDS]
    va = [r for r in rows if r["seed"] in R.VALIDATION_SEEDS]
    k1, k2 = sum(effective_row(r) for r in ex), sum(effective_row(r) for r in va)
    outs = [r["outcome"][2] for r in rows]
    return {"exploration": f"{k1}/{len(ex)}", "validation": f"{k2}/{len(va)}", "effective": k1 == len(ex) and k2 == len(va) and len(ex) > 0, "near_miss": (3 <= k1 < len(ex)) or (k1 == len(ex) and 3 <= k2 < len(va)),
            "outcomes_long": dict(sorted(S6._count(outs).items())), "secondary": sum(r["secondary"] for r in rows)}


def intervals(ticks: list[int]) -> list[list[int]]:
    out: list[list[int]] = []
    for t in sorted(ticks):
        if out and t == out[-1][1] + 1:
            out[-1][1] = t
        else:
            out.append([t, t])
    return out


def window(stress_id: str, parts: list[tuple[str, float, int]], ticks: tuple[int, ...] = FINE_TICKS) -> dict:
    """B1: the timing window of one setting at one-tick resolution."""
    g = grid(stress_id, lambda m: parts, ticks, (0.0,))
    cells = {t: cell_status(g[(0.0, t)]) for t in ticks}
    eff = [t for t, c in cells.items() if c["effective"]]
    nm = [t for t, c in cells.items() if c["near_miss"] and not c["effective"]]
    # the collapse of the unrepaired run is at about tick 145: a repair after it is a recovery of a collapsed run, before it a prevention
    return {"stress": stress_id, "parts": [list(p) for p in parts], "effective_ticks": eff, "effective_intervals": intervals(eff), "near_miss_ticks": nm, "earliest_effective_tick": eff[0] if eff else None, "latest_effective_tick": eff[-1] if eff else None,
            "ticks_tested": [ticks[0], ticks[-1]], "per_tick": {str(t): {"exploration": c["exploration"], "validation": c["validation"], "outcomes_long": c["outcomes_long"]} for t, c in cells.items()}}


PULSE_MAGNITUDES: tuple[float, ...] = tuple(round(0.1 * k, 1) for k in range(1, 61))


def pulse_sweep(stress_id: str, t: int = R.T_ACT, magnitudes: tuple[float, ...] = PULSE_MAGNITUDES) -> dict:
    """B2: classify every pulse magnitude at tick ``t``: insufficient / effective / overshoot / delayed secondary collapse."""
    g = grid(stress_id, lambda m: [("resource.pulse", m, 0)], (t,), magnitudes)
    rows = []
    for m in magnitudes:
        rs = g[(m, t)]
        c = cell_status(rs)
        sec = [r for r in rs if r["secondary"]]
        stretch = sorted(r["active_stretch"] for r in sec)
        rows.append({"magnitude": m, **{k: c[k] for k in ("exploration", "validation", "effective", "outcomes_long")}, "secondary_collapse_runs": len(sec), "median_active_stretch_before_secondary": stretch[len(stretch) // 2] if stretch else None})
    eff_m = [r["magnitude"] for r in rows if r["effective"]]
    lo, hi = (min(eff_m), max(eff_m)) if eff_m else (None, None)
    for r in rows:
        if r["effective"]:
            r["phase"] = "effective recovery"
        elif hi is None:  # no magnitude of the sweep is effective on this stress at this tick
            r["phase"] = "transient recovery, then secondary collapse" if r["secondary_collapse_runs"] else "no effect (no magnitude of the sweep recovers)"
        elif r["secondary_collapse_runs"]:
            r["phase"] = "delayed secondary collapse" if (r["median_active_stretch_before_secondary"] or 0) >= 60 else "overshoot" if r["magnitude"] > hi else "secondary collapse (below the effective band)"
        else:
            r["phase"] = "insufficient intervention" if r["magnitude"] < lo else "overshoot (no recovery)"
    return {"stress": stress_id, "tick": t, "effective_band": [lo, hi], "effective_magnitudes": eff_m, "rows": rows}


def stage5_consistency(seeds: tuple[int, ...] = R.SEARCH_SEEDS + R.VALIDATION_SEEDS + R.EVAL_SEEDS) -> dict:
    """B4: the M2 tap on 'history lost' at tick 113 judged the stage 5 way (horizon 300, ACTIVE at the end) and the stage 6 way."""
    st = R.STRESSES["history lost"]
    rep = R.build_action("internal.m2_tap", st, 0.0, R.T_ACT)
    rows = []
    for sd in seeds:
        rec = R.run(st, rep, sd, 480)
        s = [f["status"] for f in rec["frames"]]
        o = R.evaluate(rec, R.reference(sd), rep, R.T_ACT)
        rows.append({"seed": sd, "stage5_style_active_at_300": s[299] == "ACTIVE", "stage5_style_active_at_end_of_480": s[-1] == "ACTIVE", "stage6_short": o["horizons"]["short"]["success"], "stage6_medium": o["horizons"]["medium"]["success"], "stage6_long": o["horizons"]["long"]["success"]})

    def k(key: str, sel: tuple[int, ...]) -> str:
        sub = [r for r in rows if r["seed"] in sel]
        return f"{sum(r[key] for r in sub)}/{len(sub)}"

    return {"stress": "history lost", "action": "internal.m2_tap", "tick": R.T_ACT, "same_in_both": {"stress_onset": 100, "action_tick": 113, "m2_spec": {"sense": "direct", "weight": 4.0}, "engine": "meos-0.4", "dormant tap installed at tick 0 (ROUTE m2 none)": True},
            "differs": {"horizon": "stage 5: 300; stage 6: 480 (short 180, medium 300, long 480)", "criterion": "stage 5: final status ACTIVE; stage 6: ACTIVE on the last 30 ticks, no secondary collapse, resource field not exhausted"},
            "by_seed_set": {name: {key: k(key, sel) for key in ("stage5_style_active_at_300", "stage5_style_active_at_end_of_480", "stage6_short", "stage6_medium", "stage6_long")} for name, sel in (("exploration 1-5", R.SEARCH_SEEDS), ("validation 6-10", R.VALIDATION_SEEDS), ("evaluation 11-30", R.EVAL_SEEDS))}}


def cycle_period(seed: int = 1) -> dict:
    """The period of the operational cycle of the undamaged run (for reading the timing windows: an effective tick depends on where in the cycle the action lands)."""
    cyc = R.reference(seed)["cycles"]
    ticks = [c["tick"] for c in cyc]
    d = sorted(b - a for a, b in zip(ticks, ticks[1:], strict=False))
    return {"seed": seed, "cycles": len(cyc), "horizon": R.HORIZON, "median_interval": d[len(d) // 2] if d else None, "min_interval": d[0] if d else None, "max_interval": d[-1] if d else None, "first_cycle_ticks": ticks[:6]}
