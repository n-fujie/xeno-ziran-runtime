"""Stage 6, Pipeline B: timing windows at one-tick resolution, the resource overshoot sweep, minimum intervention sweeps, and the stage 5 consistency check.

    PYTHONPATH=backend python backend/scripts/meos_experiments_stage6_refine.py     # needs experiments_stage6.json; about 25 minutes on 8 cores

Writes docs/ecosystem/experiments_stage6_refine.json. See xzr/meos/stage6_refine.py for the protocol (exploration and validation seeds are both required and kept apart)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from xzr.meos import engine as E
from xzr.meos import repair6 as R
from xzr.meos import stage6_refine as RF

DOCS = Path(__file__).resolve().parents[2] / "docs" / "ecosystem"
OUT = DOCS / "experiments_stage6_refine.json"
COUPLING, RESOURCE, RENEW_EFF, RENEW_STOP, ADDRESS, HISTORY = (R.STRESSES[k].id for k in R.STRESSES)


def settings_for_windows(a: dict) -> list[tuple[str, list[tuple[str, float, int]]]]:
    """The settings whose timing window is measured: for every stress the settings Pipeline A found effective or nearly (the minimum effective one of each action, every validated pair), the M2 tap and a pulse of 1.0 for the cross view."""
    out: dict[tuple, tuple[str, list]] = {}

    def add(stress: str, parts: list[tuple[str, float, int]]) -> None:
        out[(stress, tuple(parts))] = (stress, parts)

    for sid in R.STRESS_ORDER:
        add(sid, [("internal.m2_tap", 0.0, 0)])
        add(sid, [("resource.pulse", 1.0, 0)])
    rows = a["single_settings"]
    for m in a["minimum_effective"]:
        if m["minimum_effective_magnitude"] is not None:
            r = next(x for x in rows if x["stress"] == m["stress"] and x["action"] == m["action"] and x["magnitude"] == m["minimum_effective_magnitude"] and x["status"] == "validated")
            add(m["stress"], [(m["action"], m["minimum_effective_magnitude"], r["duration"])])
    for r in rows:
        if r["status"] != "failed validation" and r["status"] == "near miss":
            add(r["stress"], [(r["action"], r["magnitude"], r["duration"])])
    for r in a["combined_settings"]:
        if r["status"] in ("validated", "near miss"):
            add(r["stress"], [tuple(p) for p in r["parts"]])
    for aid in ("coupling.restore", "renewal.restore", "renewal.restart", "address.restore", "address.reassign"):
        for sid in R.STRESS_ORDER:
            from xzr.meos import stage6_experiments as S6
            if S6.applicable(aid, sid):
                add(sid, [(aid, max(R.ACTIONS[aid].magnitudes or (0.0,)), 0)])
    return list(out.values())


def main() -> None:
    t0 = time.time()
    if "--extend" in sys.argv:  # the windows that reach the end of the one-tick range (tick 165 or later) are measured on to tick 330, where the horizons still leave room (long: action tick <= 420)
        res = json.loads(OUT.read_text())
        ticks = tuple(range(171, 331))
        ext = []
        for w in res["B1_windows"]:
            if w["latest_effective_tick"] is not None and w["latest_effective_tick"] >= 165:
                x = RF.window(w["stress"], [tuple(p) for p in w["parts"]], ticks)
                ext.append(x)
                w["per_tick"].update(x["per_tick"])
                eff = sorted({*w["effective_ticks"], *x["effective_ticks"]})
                w.update(effective_ticks=eff, effective_intervals=RF.intervals(eff), earliest_effective_tick=eff[0], latest_effective_tick=eff[-1], near_miss_ticks=sorted({*w["near_miss_ticks"], *x["near_miss_ticks"]}), ticks_tested=[w["ticks_tested"][0], 330])
                print("extended", w["stress"][:22], w["parts"], w["effective_intervals"], flush=True)
        res["B1_extension"] = {"ticks": [171, 330], "windows_extended": len(ext), "note": "windows whose latest effective tick was 165 or later at the end of the first range"}
        OUT.write_text(json.dumps(res, indent=0))
        print("extended", len(ext), "windows in", round(time.time() - t0), "s")
        return
    if "--b2-only" in sys.argv:  # recompute the pulse sweeps (and the cycle period) only, keeping the rest of the saved result
        res = json.loads(OUT.read_text())
        res["B2_pulse_sweeps"] = [RF.pulse_sweep(sid) for sid in R.STRESS_ORDER]
        res["cycle_period"] = RF.cycle_period()
        OUT.write_text(json.dumps(res, indent=0))
        print("B2 recomputed in", round(time.time() - t0), "s")
        return
    a = json.loads((DOCS / "experiments_stage6.json").read_text())
    res: dict = {"engine": E.ENGINE_VERSION, "protocol": RF.__doc__, "seeds": {"exploration": list(R.SEARCH_SEEDS), "validation": list(R.VALIDATION_SEEDS)}, "decision_tick": R.T_ACT, "stress_tick": R.STRESS_TICK}
    wins = []
    for sid, parts in settings_for_windows(a):
        wins.append(RF.window(sid, parts))
        print("window", sid[:22], parts, wins[-1]["effective_intervals"], flush=True)
    res["B1_windows"] = wins
    res["B2_pulse_sweeps"] = [RF.pulse_sweep(sid) for sid in R.STRESS_ORDER]
    print("B2 done", round(time.time() - t0), flush=True)
    seeds = RF.SEEDS_ALL
    b3: dict = {}

    def sweep(name: str, stress: str, parts_of, ticks: tuple[int, ...], mags: tuple[float, ...]) -> None:
        g = RF.grid(stress, parts_of, ticks, mags, seeds)
        cells = {f"{m}@{t}": {k: v for k, v in RF.cell_status(rs).items() if k != "near_miss"} | {"near_miss": RF.cell_status(rs)["near_miss"]} for (m, t), rs in g.items()}
        eff = [(m, t) for (m, t), rs in g.items() if RF.cell_status(rs)["effective"]]
        b3[name] = {"stress": stress, "magnitudes": list(mags), "ticks": list(ticks), "cells": cells, "minimum_effective_magnitude_by_tick": {str(t): min((m for m, tt in eff if tt == t), default=None) for t in ticks},
                    "minimum_effective_magnitude_overall": min((m for m, _ in eff), default=None), "effective_ticks": sorted({t for _, t in eff})}
        print("B3", name, b3[name]["minimum_effective_magnitude_overall"], flush=True)

    sweep("coupling restore (gain)", COUPLING, lambda m: [("coupling.restore", m, 0)], tuple(range(101, 113)), tuple(round(0.5 + 0.05 * i, 2) for i in range(11)))
    sweep("renewal restore (efficiency)", RENEW_EFF, lambda m: [("renewal.restore", m, 0)], tuple(range(101, 113)), tuple(round(0.6 + 0.05 * i, 2) for i in range(9)))
    sweep("resource pulse on the coupling stress", COUPLING, lambda m: [("resource.pulse", m, 0)], tuple(range(105, 150, 5)), tuple(round(0.05 * i, 2) for i in range(1, 21)))
    sweep("Address restore + pulse", ADDRESS, lambda m: [("address.restore", 0.0, 0), ("resource.pulse", m, 0)], tuple(range(105, 150, 5)), tuple(round(0.25 * i, 2) for i in range(1, 13)))
    sweep("renewal restart + pulse", RENEW_STOP, lambda m: [("renewal.restart", 0.0, 0), ("resource.pulse", m, 0)], tuple(range(105, 155, 5)), tuple(round(0.25 * i, 2) for i in range(1, 13)))
    res["B3_minimum_intervention"] = b3
    res["B4_stage5_consistency"] = RF.stage5_consistency()
    res["cycle_period"] = RF.cycle_period()
    res["seconds"] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(res, indent=0))
    print(f"wrote {OUT} in {res['seconds']} s")


if __name__ == "__main__":
    main()
