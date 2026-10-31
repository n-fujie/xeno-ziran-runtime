"""MEOS-0, sixth stage, follow-up: do the three windows that were still effective at tick 330 close at a later tick?

The first range ended at tick 330 because the long horizon (480) leaves room for 60 ticks only up to tick 420. Here every setting whose one-tick window reached tick 330 is run once more with the longest horizon the engine accepts
(``EXTENDED_HORIZON`` = 1200) at every action tick from 331 to ``EXTENDED_HORIZON - 2W``. A tick is *effective* when the setting is effective on all five exploration seeds AND all five validation seeds (kept apart, as in Pipeline B), where a
row is effective if it succeeds at every horizon applicable to the tick (180, 300, 480, as before) and at the extended horizon, with no secondary collapse and a resource field not exhausted. A window that is effective at the last tick tested
(1140) is still ``OPEN_THROUGH_TESTED_LIMIT``; otherwise the first tick after the last effective tick at which nothing is effective afterwards is the irreversible tick, **of the tested action space**.
"""

from __future__ import annotations

from typing import Any

from . import repair6 as R
from . import stage5_experiments as X5
from . import stage6_experiments as S6
from . import stage6_refine as RF

EXTENDED_HORIZON = 1200
LAST_TICK = EXTENDED_HORIZON - 2 * R.W  # 1140


def _job(a: tuple) -> dict:
    stress_id, parts, t, seed = a
    st = R.STRESSES[stress_id]
    reps: list[dict] = []
    for aid, mag, dur in parts:
        reps += R.build_action(aid, st, mag, t, dur)
    rec = R.run(st, sorted(reps, key=lambda i: i["tick"]), seed, EXTENDED_HORIZON)
    ref = R.reference(seed, EXTENDED_HORIZON)
    s = [f["status"] for f in rec["frames"]]
    ok: list[bool] = []
    out: list[str] = []
    for H in (*R.HORIZONS.values(), EXTENDED_HORIZON):
        o = R.outcome_at(s, H, t)
        exhausted = rec["traces"]["resource_total"][H - 1] < 0.25 * (ref["traces"]["resource_total"][H - 1] or 1.0)
        ok.append(bool(o["success"]) and not exhausted)
        out.append("failed (resource exhausted)" if exhausted else o["outcome"])
    secondary = R.outcome_at(s, EXTENDED_HORIZON, t)["secondary_collapse"]
    app = R.horizons_applicable(t)
    names = ("short", "medium", "long")
    good = all(o for o, n in zip(ok[:3], names, strict=True) if app[n]) and ok[3] and not secondary
    return {"stress": stress_id, "parts": [list(p) for p in parts], "t": t, "seed": seed, "ok": ok, "outcome": out, "secondary": secondary, "effective": good}


def window(stress_id: str, parts: list[tuple[str, float, int]], ticks: range) -> dict:
    jobs = [(stress_id, tuple(parts), t, sd) for t in ticks for sd in RF.SEEDS_ALL]
    rows = X5.pmap(_job, jobs, None, chunksize=8)
    by: dict[int, list[dict]] = {t: [] for t in ticks}
    for r in rows:
        by[r["t"]].append(r)
    per_tick: dict[str, Any] = {}
    eff: list[int] = []
    nm: list[int] = []
    for t in ticks:
        ex = [r for r in by[t] if r["seed"] in R.SEARCH_SEEDS]
        va = [r for r in by[t] if r["seed"] in R.VALIDATION_SEEDS]
        k1, k2 = sum(r["effective"] for r in ex), sum(r["effective"] for r in va)
        per_tick[str(t)] = {"exploration": f"{k1}/{len(ex)}", "validation": f"{k2}/{len(va)}", "outcomes_extended": dict(sorted(S6._count([r["outcome"][3] for r in by[t]]).items()))}
        if k1 == len(ex) and k2 == len(va):
            eff.append(t)
        elif (3 <= k1 < len(ex)) or (k1 == len(ex) and 3 <= k2 < len(va)):
            nm.append(t)
    return {"stress": stress_id, "parts": [list(p) for p in parts], "ticks_tested": [ticks[0], ticks[-1]], "effective_ticks": eff, "effective_intervals": RF.intervals(eff), "near_miss_ticks": nm,
            "latest_effective_tick": eff[-1] if eff else None, "per_tick": per_tick}
