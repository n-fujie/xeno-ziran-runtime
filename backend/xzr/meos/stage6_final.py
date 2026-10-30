"""MEOS-0, sixth stage: the derived reading of Pipelines A, B and C, in one place, for the results table, the interface and the document. Everything is computed from the saved raw results (``experiments_stage6*.json``); nothing is typed in.

Definitions (fixed before the readings were taken):

  effective tick         a tick at which a tested setting recovers sustained to every horizon on all five exploration seeds AND all five validation seeds (Pipeline B, one-tick resolution; ticks 101-170).
  latest successful repair tick   the last tick at which any tested setting is effective.
  irreversible tick (``irreversibility``)   the first tick after which no tested setting is effective at any later tested tick (ticks up to 170 at one-tick resolution; up to 330 for the windows still open at 170; up to 200 on the coarse grid). It is the next tick after the latest successful one, and it is a statement
                          about the tested action space only. **If a window is still effective at the last tick tested, it has not closed: ``irreversibility`` is ``OPEN_THROUGH_TESTED_LIMIT`` and ``irreversible_tick`` is null** (never the next tick). ``CLOSED``: a window ended inside the tested range; ``NO_EFFECTIVE_TICK``: no tested setting is effective at any tested tick.
  first window           the first contiguous run of effective ticks of any setting; ``fragments`` are all of them (the windows are not always contiguous: a gap is recorded, not smoothed).
  reference repair       the validated setting of a stress with the lowest equal-weight normalised cost (switching, collateral disturbance, persistence energy rate, each divided by its maximum over the validated settings): an equal-weight convention, stated, with the raw costs beside it.
  flags                  window closes before the unrepaired collapse (all repairs are timing-limited); only transiently recoverable (a setting recovers at the short horizon on every exploration seed and not at the long one, and nothing is validated); costly (every validated setting is above the cost limit).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from . import repair6 as R
from . import stage6_experiments as S6
from . import stage6_refine as RF

FAMILY_CLASS = {"internal.m2_tap": "internal reconfiguration"}


def merge_intervals(ints: list[list[int]]) -> list[list[int]]:
    out: list[list[int]] = []
    for a, b in sorted(ints):
        if out and a <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def window_class(parts: list[list]) -> str:
    acts = [p[0] for p in parts]
    if acts == ["internal.m2_tap"]:
        return "internal"
    if len(acts) == 1:
        return "world"
    return "combined"


def _ticks(ints: list[list[int]]) -> set[int]:
    return {t for lo, hi in ints for t in range(lo, hi + 1)}


def _to_intervals(ticks: set[int]) -> list[list[int]]:
    return RF.intervals(sorted(ticks))


def stress_windows(b: dict, stress_id: str) -> dict[str, list[list[int]]]:
    """The effective ticks of a stress by kind of repair, at one-tick resolution (Pipeline B). A pair counts as a *combined* recovery only at the ticks where none of its parts is effective alone (the parts' own windows were measured at the same magnitudes);
    a pair with a part whose own window was not measured is left out (it cannot be shown to be a synergy)."""
    singles: dict[tuple, set[int]] = {}
    for w in b["B1_windows"]:
        if w["stress"] == stress_id and len(w["parts"]) == 1:
            singles[tuple(w["parts"][0])] = _ticks(w["effective_intervals"])
    out: dict[str, set[int]] = {"internal": set(), "world": set(), "combined": set()}
    for w in b["B1_windows"]:
        if w["stress"] != stress_id:
            continue
        cls = window_class(w["parts"])
        ticks = _ticks(w["effective_intervals"])
        if cls != "combined":
            out[cls] |= ticks
            continue
        parts = [tuple(p) for p in w["parts"]]
        if all(p in singles for p in parts):
            out["combined"] |= ticks - set().union(*(singles[p] for p in parts))
    return {k: _to_intervals(v) for k, v in out.items()}


def near_miss_ticks(b: dict, stress_id: str) -> list[int]:
    return sorted({t for w in b["B1_windows"] if w["stress"] == stress_id for t in w["near_miss_ticks"]})


def cost_norm(rows: list[dict]) -> list[tuple[float, dict]]:
    """Equal-weight normalised cost of each setting (a convention, stated): the mean of the three costs, each divided by its maximum over ``rows``."""
    def parts(r: dict) -> tuple[float, float, float]:
        c = r["costs"]
        raw = c.get("raw", c)
        return float(raw.get("switching", 1)), float(raw.get("collateral", 0.0)), float(c.get("energy_rate_norm", 1.0))
    ps = [parts(r) for r in rows]
    mx = [max(p[i] for p in ps) or 1.0 for i in range(3)]
    return [(round(sum(p[i] / mx[i] for i in range(3)) / 3, 4), r) for p, r in zip(ps, rows, strict=True)]


def reference_repair(a: dict, stress_id: str) -> dict | None:
    cand: list[dict] = []
    for r in a["single_settings"]:
        if r["stress"] == stress_id and r["status"] == "validated" and r["costs"]:
            cand.append({**r, "kind": "single", "parts": [[r["action"], r["magnitude"], r["duration"]]]})
    for r in a["combined_settings"]:
        if r["stress"] == stress_id and r["status"] == "validated" and r["synergistic"] and r["costs"]:
            cand.append({**r, "kind": "combined"})
    if not cand:
        return None
    scored = cost_norm(cand)
    scored.sort(key=lambda x: (x[0], len(x[1]["parts"]), x[1]["t"]))
    cost, best = scored[0]
    return {"parts": best["parts"], "t": best["t"], "klass": window_class(best["parts"]), "kind": best["kind"], "normalised_cost_equal_weights": cost, "costs": best["costs"], "evaluation": best["evaluation"], "n_candidates": len(cand)}


def stress_row(a: dict, b: dict, sid: str) -> dict[str, Any]:
    rep = a["repairability"][sid]
    win = stress_windows(b, sid)
    nm = near_miss_ticks(b, sid)
    at = lambda ints: any(lo <= R.T_ACT <= hi for lo, hi in ints)  # noqa: E731
    cls_113 = S6.classify_repairability(at(win["internal"]), at(win["world"]), at(win["combined"]), R.T_ACT in nm)
    cls_any = S6.classify_repairability(bool(win["internal"]), bool(win["world"]), bool(win["combined"]), bool(nm) or rep["near_miss"])
    allw = merge_intervals([i for v in win.values() for i in v])
    eff_ticks = sorted(t for lo, hi in allw for t in range(lo, hi + 1))
    na = next(r for r in a["no_action"] if r["stress"] == sid)
    rows = [r for r in a["table"] if r["stress"] == sid and r["action"] != "no action"]
    transient = [r for r in rows if r["n"] and r["short"] == r["n"] and r["long"] == 0]
    mins = [m for m in a["minimum_effective"] if m["stress"] == sid and m["minimum_effective_magnitude"] is not None]
    ref = reference_repair(a, sid)
    failures = Counter(R.failure_id(r["failure"]) for r in rows if r["failure"] != "effective")
    latest = eff_ticks[-1] if eff_ticks else None
    # a window that is still effective at the last tick that was tested has not closed: its end is the end of the range, not a closure
    ends = [w["ticks_tested"][1] for w in b["B1_windows"] if w["stress"] == sid and w["latest_effective_tick"] is not None and w["latest_effective_tick"] >= w["ticks_tested"][1]]
    open_end = max(ends) if ends else None
    flags = []
    if allw and open_end is None:
        flags.append("recoverable only within a timing window")
    if open_end is not None:
        flags.append(f"a window is still open at the end of the tested range (tick {open_end}): no closure found")
    if not allw and transient:
        flags.append("only transiently recoverable")
    validated = [r for r in a["single_settings"] if r["stress"] == sid and r["status"] == "validated"]
    if validated and all(r["costly"] for r in validated):
        flags.append("recoverable with unacceptable cost")
    if R.T_ACT in nm and not any(at(win[k]) for k in win):
        flags.append("near miss at the decision tick (validation 3-4 of 5), nothing effective there")
    if win["combined"] and not win["world"] and not win["internal"]:
        flags.append("recovered only by a combination (neither part alone)")
    return {
        "stress": sid, "label": a["stresses"][sid]["label"], "family": a["stresses"][sid]["family"], "classification_at_decision_tick_113": cls_113, "classification_at_any_tested_tick": cls_any, "pipeline_a_grid_classification": {"at_113": rep["at_decision_tick_113"], "any": rep["at_any_tested_tick"], "note": "the coarse grid (ticks 104, 108, 113, 120, 130, 140, 160, 200; pairs at 113, 120, 130): superseded by the one-tick windows"}, "near_miss_ticks": nm, "flags": flags,
        "internal_reconfiguration": {"effective": bool(win["internal"]), "windows": win["internal"]}, "world_single": {"effective": bool(win["world"]), "windows": win["world"]}, "combined": {"effective": bool(win["combined"]), "windows": win["combined"]},
        "minimum_effective": [{"action": m["action"], "magnitude": m["minimum_effective_magnitude"], "ticks": m.get("effective_ticks")} for m in mins],
        "timing_window_fragments": allw, "first_window": allw[0] if allw else None, "earliest_effective_tick": eff_ticks[0] if eff_ticks else None, "latest_successful_repair_tick": latest,
        "irreversible_tick": (latest + 1) if latest is not None and open_end is None else None, "irreversibility": "OPEN_THROUGH_TESTED_LIMIT" if open_end is not None else "CLOSED" if latest is not None else "NO_EFFECTIVE_TICK", "window_open_at_end_of_tested_range": open_end is not None, "tested_range_end": open_end,
        "irreversible_from_first_tested_tick": latest is None, "tested_ticks": [101, 170], "unrepaired_run": {"outcomes_long": na["outcomes_long"], "success": na["long"]},
        "reference_repair": ref,
        "failure_reasons_in_the_tested_grid": dict(failures), "cells_tested": len(rows), "cells_effective": sum(1 for r in rows if r["effective_seeds"] == r["n"]),
        "near_miss": rep["near_miss"], "transient_settings": len(transient),
    }


def horizons_of(a: dict, sid: str) -> dict | None:
    """Short / medium / long horizon success of the reference repair on the exploration seeds (every validated setting is effective at all three, by definition): the exploration cell's counts."""
    ref = reference_repair(a, sid)
    if not ref:
        return None
    t = ref["t"]
    cells = [r for r in a["table"] if r["stress"] == sid and r["t"] == t and r["action"] == ref["parts"][0][0] and r["magnitude"] == ref["parts"][0][1]]
    return {"short": cells[0]["short"], "medium": cells[0]["medium"], "long": cells[0]["long"], "n": cells[0]["n"]} if cells and len(ref["parts"]) == 1 else {"note": "a combined repair: its three horizons are in the combined rows", "evaluation_long": ref["evaluation"]}


def collapse_ticks(a: dict) -> dict[str, int | None]:
    """The tick at which the unrepaired run collapses, from a no-action run of each stress (exploration seed 1)."""
    out: dict[str, int | None] = {}
    for sid in a["stresses"]:
        rec = R.run(R.STRESSES[sid], [], 1, R.STRESS_TICK + 100)
        out[sid] = next((i for i, f in enumerate(rec["frames"]) if i >= R.STRESS_TICK and f["status"] == "COLLAPSED"), None)
    return out


def build(a: dict, b: dict, c: dict | None, ctl: dict | None) -> dict[str, Any]:
    col = collapse_ticks(a)
    rows = []
    for sid in a["stresses"]:
        r = stress_row(a, b, sid)
        r["horizons_of_reference_repair"] = horizons_of(a, sid)
        r["unrepaired_collapse_tick"] = col[sid]
        r["window_closes_before_collapse"] = bool(r["latest_successful_repair_tick"] is not None and col[sid] is not None and r["latest_successful_repair_tick"] < col[sid])
        rows.append(r)
    pulse = {s["stress"]: s for s in b["B2_pulse_sweeps"]}
    return {"definitions": __doc__, "stress_table": rows, "unrepaired_collapse_tick": col, "resource_non_monotonicity": {sid: {"effective_band": p["effective_band"], "phases": _bands(p["rows"])} for sid, p in pulse.items()},
            "failure_ids": list(R.FAILURE_ID_LIST), "stage5_consistency": b["B4_stage5_consistency"], "cycle_period": b.get("cycle_period"), "unknown_stress": None if ctl is None else ctl["verdicts_unknown"]}


def _bands(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        if out and out[-1]["phase"] == r["phase"]:
            out[-1]["to"] = r["magnitude"]
        else:
            out.append({"phase": r["phase"], "from": r["magnitude"], "to": r["magnitude"]})
    return out


__all__ = ["build", "stress_windows", "reference_repair", "merge_intervals", "near_miss_ticks"]
