"""MEOS-0, sixth stage: repairability across the MFS, across the SSS region, across observation, and the three restorations of an Address repair.

  C1  MFS x repairability     the repairs Pipeline A validated (or nearly) on the full arrangement are tried on each distinct validated MFS (the arrangement with every component outside the MFS removed at tick 0, under the condition the MFS was found for): does the
                              repairability profile of a stress depend on the MFS? A repair is judged exactly as in Pipeline A (three horizons, sustained, no secondary collapse, resource not exhausted), on seeds 1-5.
  C2  SSS x repairability     for each MFS, a 3 x 3 grid of the SSS region (scale 0.75 / 1 / 1.25 x speed 0.9 / 1 / 1.1, size 1): where the unstressed MFS persists (its island on the grid), and there, for each stress, whether no action, the stress's recommended repair
                              recovers (repairable), collapses secondarily (overshoot-sensitive), recovers at a cost above the costly limit (costly), or does not recover (unrecoverable). Seeds 1-3.
  C3  observation x repairability   the same repaired and unrepaired runs, observed with limited sampling, spatial resolution, region and Address resolution (``analysis.observe``): operational recovery, observed recovery and the observability status, kept as three fields; and the observation repair (full
                              observation) that restores agreement. An observation repair never changes the run.
  C4  Address, three restorations   operational restoration (the run recovers), Address restoration (A2's address integrity over the last W ticks), observability restoration (the observer, with Address resolution 0.5, agrees with the run).

Nothing here is a claim about unrelated systems: it is how this model behaves under these perturbations.
"""

from __future__ import annotations

import copy
import itertools
from collections import defaultdict
from typing import Any

from . import analysis as A
from . import engine as E
from . import experiments as X
from . import mfs5 as M5
from . import repair6 as R
from . import stage5_experiments as X5
from . import stage6_experiments as S6

SSS_GRID = tuple(itertools.product((0.75, 1.0, 1.25), (0.9, 1.0, 1.1)))  # (scale, speed), size 1


# ---------------------------------------------------------------------------------------------------- repairs to try
def recommended(a: dict, max_tick: int = R.T_ACT) -> dict[str, list[tuple[str, list[tuple[str, float, int]], int]]]:
    """Per stress the repairs Pipeline A found effective (validated) or nearly (near miss) at a tick up to ``max_tick``: (label, parts, tick). The earliest-tick representative of each (stress, parts) is kept."""
    out: dict[str, dict[tuple, tuple]] = defaultdict(dict)
    for r in a["single_settings"]:
        if r["status"] in ("validated", "near miss") and r["t"] <= max_tick:
            parts: tuple[tuple[str, float, int], ...] = ((r["action"], r["magnitude"], r["duration"]),)
            out[r["stress"]].setdefault(parts, (r["action"], [parts[0]], r["t"], r["status"]))
    for r in a["combined_settings"]:
        if r["status"] in ("validated", "near miss") and r["t"] <= max_tick:
            parts = tuple((p[0], p[1], p[2]) for p in r["parts"])
            out[r["stress"]].setdefault(parts, (" + ".join(p[0] for p in parts), list(parts), r["t"], r["status"]))
    return {s: [(lab, parts, t) for lab, parts, t, _ in v.values()] for s, v in out.items()}


# ---------------------------------------------------------------------------------------------------- C1 / C2: a run on an MFS configuration
def _cond(cid: str) -> dict:
    return next(c for c in M5.conditions_f() if c["id"] == cid)


def distinct_mfs(s5: dict) -> list[dict]:
    """The distinct validated retaining sets of stage 5 (each under the first MFS id and condition that has it)."""
    seen: dict[tuple, dict] = {}
    for cid, r in s5["F"]["by_condition"].items():
        for m in r["mfs"]:
            seen.setdefault(tuple(m["retained_components"]), {"id": m["id"], "condition": cid, "retained": m["retained_components"]})
    return list(seen.values())


def _run_on(cond: dict, retained: list[str], stress: R.Stress | None, parts: list[tuple[str, float, int]], t: int, seed: int, sss: tuple[float, float] | None = None) -> dict:
    cfg = M5._config(cond, seed, R.HORIZON)
    base = M5.retained_interventions(cond, frozenset(retained))
    if sss is not None:
        base = [*base, {"tick": 0, "op": "ALTER_SSS", "scale": sss[0], "size": 1.0, "speed": sss[1]}]
    reps: list[dict] = []
    for aid, m, d in parts:
        reps += R.build_action(aid, stress or R.STRESSES["history lost"], m, t, d)
    sched = [*base, *(stress.make(R.STRESS_TICK) if stress else []), *copy.deepcopy(sorted(reps, key=lambda i: i["tick"]))]
    rec = E.run_record(cfg, sched)
    ref = E.run_record(cfg, base)
    return R.evaluate(rec, ref, reps, t) | {"_ref_final": ref["final_status"]["label"]}


def _mfs_job(a: tuple) -> dict:
    mfs, stress_id, label, parts, t, seed, sss = a
    cond = _cond(mfs["condition"])
    row = {"mfs": mfs["id"], "stress": stress_id, "repair": label, "t": t, "seed": seed, "sss": list(sss) if sss else None}
    if any(aid == "internal.m2_tap" for aid, _, _ in parts) and "m2_tap" not in cond["universe"]:
        return row | {"applicable": False, "reason": "this MFS's condition has no M2 tap"}
    try:
        o = _run_on(cond, mfs["retained"], R.STRESSES[stress_id] if stress_id != "no stress" else None, list(parts), t, seed, sss)
    except E.MeosError as e:
        return row | {"applicable": False, "reason": str(e)[:120]}
    h = o["horizons"]
    c = o["costs"]
    return row | {"applicable": True, "ok": [h[k]["success"] for k in ("short", "medium", "long")], "outcome": h["long"]["outcome"], "secondary": h["long"]["secondary_collapse"], "exhausted": h["long"]["resource_exhausted"], "unstressed_persists": o["_ref_final"] == "ACTIVE",
                  "energy_rate_norm": c["normalised"]["persistence_energy_rate"], "collateral": c["raw"]["collateral"]}


def _eff(r: dict) -> bool:
    return bool(r.get("applicable") and all(r["ok"]) and not r["secondary"] and not r["exhausted"])


def mfs_cross(a: dict, s5: dict, seeds: tuple[int, ...] = R.SEARCH_SEEDS, processes: int | None = None) -> dict:
    rec = recommended(a)
    jobs: list[tuple] = []
    for mfs in distinct_mfs(s5):
        for sid in R.STRESS_ORDER:
            for label, parts, t in [("no action", [], R.T_ACT), *rec.get(sid, [])]:
                for sd in seeds:
                    jobs.append((mfs, sid, label, tuple(parts), t, sd, None))
    rows = X5.pmap(_mfs_job, jobs, processes, chunksize=4)
    by: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        by[(r["mfs"], r["stress"], r["repair"], r["t"])].append(r)
    table = []
    for (mfs, sid, label, t), rs in sorted(by.items()):
        app = [r for r in rs if r.get("applicable")]
        table.append({"mfs": mfs, "stress": sid, "repair": label, "t": t, "applicable": bool(app), "effective_seeds": f"{sum(_eff(r) for r in app)}/{len(app)}" if app else None, "reason": rs[0].get("reason"), "klass": "A" if "internal.m2_tap" in label and "+" not in label else "A+B" if "internal.m2_tap" in label else "B" if label != "no action" else None,
                      "outcomes_long": S6._count([r["outcome"] for r in app]) if app else None})
    prof: dict[str, dict[str, str]] = defaultdict(dict)
    for m in distinct_mfs(s5):
        for sid in R.STRESS_ORDER:
            ts = [x for x in table if x["mfs"] == m["id"] and x["stress"] == sid and x["repair"] != "no action" and x["applicable"]]
            eff = [x for x in ts if x["effective_seeds"] and x["effective_seeds"].split("/")[0] == x["effective_seeds"].split("/")[1]]
            singles = {(x["repair"], x["t"]) for x in eff if " + " not in x["repair"]}
            internal = any(x["repair"] == "internal.m2_tap" for x in eff)
            external = any(" + " not in x["repair"] and x["repair"] != "internal.m2_tap" for x in eff)
            combined = any(" + " in x["repair"] and not any((p, x["t"]) in singles for p in x["repair"].split(" + ")) for x in eff)  # a pair counts only if neither part is effective alone at that tick
            near = any(x["effective_seeds"] and 0 < int(x["effective_seeds"].split("/")[0]) < int(x["effective_seeds"].split("/")[1]) for x in ts)
            prof[m["id"]][sid] = S6.classify_repairability(internal, external, combined, near)
    return {"mfs": distinct_mfs(s5), "seeds": list(seeds), "table": table, "profile": prof,
            "note": "the repairs were validated on the full arrangement and are tried unchanged on each MFS; 'external' here counts class B and mixed repairs that are effective; an MFS without an M2 tap has no internal route of this kind"}


def sss_cross(a: dict, s5: dict, seeds: tuple[int, ...] = (1, 2, 3), processes: int | None = None) -> dict:
    rec = recommended(a)
    jobs: list[tuple] = []
    for mfs in distinct_mfs(s5):
        for sss in SSS_GRID:
            for sd in seeds:
                jobs.append((mfs, "no stress", "unstressed", (), R.T_ACT, sd, sss))
            for sid in R.STRESS_ORDER:
                reps = rec.get(sid, [])
                best = sorted(reps, key=lambda x: (x[2], len(x[1])))[:1]
                for label, parts, t in [("no action", [], R.T_ACT), *best]:
                    for sd in seeds:
                        jobs.append((mfs, sid, label, tuple(parts), t, sd, sss))
    rows = X5.pmap(_mfs_job, jobs, processes, chunksize=4)
    by: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        by[(r["mfs"], tuple(r["sss"]), r["stress"], r["repair"])].append(r)
    cells = []
    for m in distinct_mfs(s5):
        for sss in SSS_GRID:
            un = [r for r in by.get((m["id"], sss, "no stress", "unstressed"), []) if r.get("applicable")]
            island = bool(un) and all(_eff(r) for r in un)
            cell: dict[str, Any] = {"mfs": m["id"], "scale": sss[0], "speed": sss[1], "unstressed_persists": island, "stress": {}}
            if island:
                for sid in R.STRESS_ORDER:
                    nm = [r for k, rs in by.items() if k[:3] == (m["id"], sss, sid) and k[3] != "no action" for r in rs if r.get("applicable")]
                    none = [r for r in by.get((m["id"], sss, sid, "no action"), []) if r.get("applicable")]
                    eff = [r for r in nm if _eff(r)]
                    if not nm:
                        cls = "unrecoverable (no tested repair at or before the decision tick)"
                    elif len(eff) == len(nm) and nm:
                        cls = "costly recovery" if any((r["energy_rate_norm"] or 0) > S6.COSTLY_ENERGY_RATE or r["collateral"] > S6.COSTLY_COLLATERAL for r in eff) else "repairable"
                    elif any(r["secondary"] for r in nm):
                        cls = "overshoot-sensitive / unstable recovery"
                    elif eff:
                        cls = "repairable on some seeds only"
                    else:
                        cls = "unrecoverable"
                    cell["stress"][sid] = {"class": cls, "no_action_recovers": f"{sum(_eff(r) for r in none)}/{len(none)}", "repair": nm[0]["repair"] if nm else None, "effective": f"{len(eff)}/{len(nm)}"}
            cells.append(cell)
    return {"grid": [list(g) for g in SSS_GRID], "size": 1.0, "seeds": list(seeds), "cells": cells}


# ---------------------------------------------------------------------------------------------------- C3 / C4: observation and the three restorations
OBS_SETTINGS: tuple[tuple[str, dict], ...] = (("full observation", {}), ("sampling interval 2", {"sampling_interval": 2}), ("sampling interval 4", {"sampling_interval": 4}), ("sampling interval 8", {"sampling_interval": 8}),
                                              ("spatial stride 2", {"spatial_stride": 2}), ("region excluding the bodies", {"region": [0, 0, 2, 2]}), ("Address resolution 0.5", {"address_resolution": 0.5}))
OBS_RUNS: tuple[tuple[str, str, tuple, int, int], ...] = (  # (label, stress, parts, tick, seed)
    ("coupling stress, resource pulse 1.0 at 113 (recovered)", "coupling gain 0.5", (("resource.pulse", 1.0, 0),), 113, 1), ("coupling stress, no repair (collapsed)", "coupling gain 0.5", (), 113, 1),
    ("coupling stress, coupling restore at 104 (prevented)", "coupling gain 0.5", (("coupling.restore", 1.0, 0),), 104, 1), ("coupling stress, pulse 4.0 at 113 (overshoot)", "coupling gain 0.5", (("resource.pulse", 4.0, 0),), 113, 1),
    ("history lost, M2 tap at 113 (recovered)", "history lost", (("internal.m2_tap", 0.0, 0),), 113, 1), ("Address stress, restore + pulse 1.0 at 113, seed 1", "Address partial 0.5", (("address.restore", 0.0, 0), ("resource.pulse", 1.0, 0)), 113, 1),
    ("Address stress, restore + pulse 1.0 at 113, seed 6", "Address partial 0.5", (("address.restore", 0.0, 0), ("resource.pulse", 1.0, 0)), 113, 6),
)


def _record(stress_id: str, parts: tuple, t: int, seed: int) -> tuple[dict, list[dict]]:
    st = R.STRESSES[stress_id]
    reps: list[dict] = []
    for aid, m, d in parts:
        reps += R.build_action(aid, st, m, t, d)
    return R.run(st, sorted(reps, key=lambda i: i["tick"]), seed), reps


def observation_cross() -> dict:
    rows = []
    for label, sid, parts, t, seed in OBS_RUNS:
        rec, reps = _record(sid, parts, t, seed)
        op = R.evaluate(rec, R.reference(seed), reps, t)["horizons"]["long"]
        for oname, obs in OBS_SETTINGS:
            o = A.observe(rec, obs)
            traj = o.get("observed_trajectory") or []
            sustained = bool(traj) and all(s == "ACTIVE" for s in traj[-R.W:])
            rows.append({"run": label, "observation": oname, "operational_recovery": op["success"], "operational_outcome": op["outcome"], "operational_state": o["operational_state"], "observed_state": o["observed_state"], "observed_recovery": o["observed_state"] == "ACTIVE" and sustained,
                         "observability_status": o["observability_status"], "agrees": o["operational_state"] == o["observed_state"]})
    disagree = [r for r in rows if r["operational_recovery"] and not r["observed_recovery"]]
    return {"settings": [{"name": n, "observation": o} for n, o in OBS_SETTINGS], "rows": rows, "operationally_recovered_but_not_observed": len(disagree),
            "observation_repair": "a full observation (sampling interval 1, stride 1, whole arena, Address resolution 1) restores agreement in every case listed; it changes what is observed, never the run"}


def address_three(seeds: tuple[int, ...] = R.SEARCH_SEEDS) -> dict:
    st = R.STRESSES["Address partial 0.5"]
    cases = (("no repair", (), 113), ("Address restore at 104", (("address.restore", 0.0, 0),), 104), ("Address restore at 113", (("address.restore", 0.0, 0),), 113), ("Address reassign at 113", (("address.reassign", 0.0, 0),), 113),
             ("resource pulse 1.0 at 113", (("resource.pulse", 1.0, 0),), 113), ("Address restore + pulse 1.0 at 113", (("address.restore", 0.0, 0), ("resource.pulse", 1.0, 0)), 113))
    rows = []
    for label, parts, t in cases:
        per = []
        for sd in seeds:
            rec, reps = _record(st.id, parts, t, sd)
            o = R.evaluate(rec, R.reference(sd), reps, t)["horizons"]["long"]
            integ = rec["traces"]["address_integrity_a2"][-R.W:]
            obs = A.observe(rec, {"address_resolution": 0.5})
            per.append({"operational": o["success"], "address_integrity_last_window": round(sum(integ) / len(integ), 3), "address_restored": sum(integ) / len(integ) >= 0.9, "observer_agrees_at_address_resolution_0.5": obs["operational_state"] == obs["observed_state"],
                        "observability_status": obs["observability_status"]})
        rows.append({"case": label, "t": t, "seeds": len(per), "operational_restoration": f"{sum(p['operational'] for p in per)}/{len(per)}", "address_restoration": f"{sum(p['address_restored'] for p in per)}/{len(per)}",
                     "observability_restoration": f"{sum(p['observer_agrees_at_address_resolution_0.5'] for p in per)}/{len(per)}", "mean_address_integrity": round(sum(p["address_integrity_last_window"] for p in per) / len(per), 3), "statuses": S6._count([p["observability_status"] for p in per])})
    return {"stress": st.id, "rows": rows, "reading": "operational restoration, Address restoration and observability restoration are three measures; a repair may give one without another"}


__all__ = ["mfs_cross", "sss_cross", "observation_cross", "address_three", "X"]
