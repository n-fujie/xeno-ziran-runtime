"""MEOS-0, sixth stage: Experiments M-Q (world-state repair) and the derived readings.

  explore    every applicable repair action of ``repair6`` on every stress, over its magnitudes x durations x action ticks, on the exploration seeds (1-5). This is the raw material of M, N, O, P and of the cross-family matrix.
  validate   a setting that was effective on every exploration seed is run again on the validation seeds (6-10) and is *validated* only if it is effective on all of them. The two seed sets are never mixed.
  evaluate   the validated settings are evaluated on fresh seeds (11-30).
  M N O P    the coupling, resource, renewal and Address stresses with the actions of their own family (the cross-family matrix shows what the other families do to the same stress).
  Q          combined repairs on the stresses no single action recovers.

*Effective* (fixed here, before the runs were read): recovered or prevented at all three horizons (short, medium, long), with no secondary collapse and no exhausted resource field, on every seed of the set.
*Costly*: effective, but the energy rate needed to keep the run going exceeds 1.5 x the undamaged run's, or its collateral disturbance exceeds 1.0 (the scale of the undamaged run). *Unstable*: recovered at the short horizon and not at the medium or long one.
Every row of every run is saved; a null result is a result.
"""

from __future__ import annotations

import gzip
import itertools
import json
from collections import defaultdict
from pathlib import Path

from . import repair6 as R
from . import stage5_experiments as X5
from . import stats5 as ST

TIMINGS = (104, 108, 113, 120, 130, 140, 160, 200)  # the stress arrives at 100; the unrepaired run collapses at ~145; 160 and 200 are after the collapse
COSTLY_ENERGY_RATE = 1.5
COSTLY_COLLATERAL = 1.0
RAW = Path(__file__).resolve().parents[3] / "docs" / "ecosystem" / "experiments_stage6_raw.jsonl.gz"
OWN_FAMILY_ONLY = {"coupling.restore", "coupling.gradual", "renewal.restore", "renewal.restart", "address.restore", "address.reassign"}  # restoring a parameter the stress did not damage would damage it


def applicable(action_id: str, stress_id: str) -> bool:
    a, s = R.ACTIONS[action_id], R.STRESSES[stress_id]
    if a.status == "not implemented" or a.klass != "B" and a.id != "internal.m2_tap":
        return False
    if action_id == "renewal.restart":
        return stress_id == "renewal stopped"
    if action_id == "renewal.restore":
        return s.family == "renewal" and stress_id != "renewal stopped"
    if action_id in OWN_FAMILY_ONLY:
        return a.family == s.family
    return True


def settings(action_id: str) -> list[tuple[float, int]]:
    a = R.ACTIONS[action_id]
    return list(itertools.product(a.magnitudes or (0.0,), a.durations))


# ---------------------------------------------------------------------------------------------------- one run -> one compact row
def _job(a: tuple) -> dict:
    stress_id, action_id, mag, dur, t, seed = a
    st = R.STRESSES[stress_id]
    reps = R.build_action(action_id, st, mag, t, dur) if action_id else []
    o = R.run_eval(st, reps, seed, t)
    h = o["horizons"]
    c = o["costs"]
    return {"stress": stress_id, "action": action_id, "magnitude": mag, "duration": dur, "t": t, "seed": seed, "ok": [h[k]["success"] for k in ("short", "medium", "long")], "outcome": [h[k]["outcome"] for k in ("short", "medium", "long")],
            "latency": h["long"]["latency"], "secondary": h["long"]["secondary_collapse"], "exhausted": h["long"]["resource_exhausted"], "raw": c["raw"], "norm": c["normalised"]}


def explore(stress_ids: tuple[str, ...] = R.STRESS_ORDER, seeds: tuple[int, ...] = R.SEARCH_SEEDS, processes: int | None = None) -> list[dict]:
    jobs = [(sid, "", 0.0, 0, R.T_ACT, sd) for sid in stress_ids for sd in seeds]  # the no-action control, once per seed (judged from the default action tick)
    for sid in stress_ids:
        for aid in R.RUNNABLE:
            if not applicable(aid, sid):
                continue
            for (m, d), t, sd in itertools.product(settings(aid), TIMINGS, seeds):
                jobs.append((sid, aid, m, d, t, sd))
    return X5.pmap(_job, jobs, processes, chunksize=8)


def save_raw(rows: list[dict], path: Path = RAW) -> None:
    with gzip.open(path, "wt") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def load_raw(path: Path = RAW) -> list[dict]:
    with gzip.open(path, "rt") as f:
        return [json.loads(line) for line in f]


# ---------------------------------------------------------------------------------------------------- cells, effectiveness, costs
def cell_key(r: dict) -> tuple:
    return (r["stress"], r["action"], r["magnitude"], r["duration"], r["t"])


def cells(rows: list[dict]) -> dict[tuple, list[dict]]:
    out: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        out[cell_key(r)].append(r)
    return out


def effective(rs: list[dict]) -> bool:
    return bool(rs) and all(all(r["ok"]) and not r["secondary"] and not r["exhausted"] for r in rs)


def summarise(rs: list[dict]) -> dict:
    n = len(rs)
    return {"n": n, "effective_seeds": sum(1 for r in rs if all(r["ok"]) and not r["secondary"] and not r["exhausted"]), "short": sum(r["ok"][0] for r in rs), "medium": sum(r["ok"][1] for r in rs), "long": sum(r["ok"][2] for r in rs),
            "secondary_collapse": sum(1 for r in rs if r["secondary"]), "outcomes_long": dict(sorted(_count([r["outcome"][2] for r in rs]).items())), "latency_median": _median([r["latency"] for r in rs if r["latency"] is not None]),
            "energy_rate_norm": _mean([r["norm"]["persistence_energy_rate"] for r in rs]), "collateral": _mean([r["raw"]["collateral"] for r in rs]), "energy_use_raw": _mean([r["raw"]["energy_use"] for r in rs]), "switching": rs[0]["raw"]["switching"]}


def _count(xs: list) -> dict:
    d: dict = {}
    for x in xs:
        d[x] = d.get(x, 0) + 1
    return d


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 4) if xs else None


def _median(xs: list[float]) -> float | None:
    s = sorted(xs)
    return s[len(s) // 2] if s else None


def costly(s: dict) -> bool:
    return bool(s["energy_rate_norm"] is not None and s["energy_rate_norm"] > COSTLY_ENERGY_RATE or s["collateral"] is not None and s["collateral"] > COSTLY_COLLATERAL)


def failure_reason(s: dict, rs: list[dict], action_id: str, t: int) -> str:
    """Why a setting did not recover, from the runs themselves (one of the stage 6 failure classes)."""
    if s["effective_seeds"] == s["n"]:
        return "effective"
    outs = {o for r in rs for o in r["outcome"]}
    if any("exhausted" in o for o in outs):
        return "insufficient resource (resource field exhausted)"
    if s["secondary_collapse"]:
        return "secondary collapse (overshoot)" if action_id.startswith("resource.pulse") or action_id.endswith("pulse") else "secondary collapse"
    if s["short"] and not s["long"]:
        return "action destabilized the system (recovered short, not long)"
    if t >= 160:
        return "action too late (after the collapse)"
    if s["long"] == 0 and s["medium"] == 0:
        return "no effective action at this setting (action too weak or the wrong target)"
    return "partial: effective on some seeds only"


# ---------------------------------------------------------------------------------------------------- validation and evaluation
def validate(stress_id: str, action_id: str, mag: float, dur: int, t: int, seeds: tuple[int, ...] = R.VALIDATION_SEEDS) -> list[dict]:
    return [_job((stress_id, action_id, mag, dur, t, sd)) for sd in seeds]


def _vjob(a: tuple) -> tuple[tuple, list[dict]]:
    key = a
    return key, validate(*key)


def validate_all(candidates: list[tuple], processes: int | None = None) -> dict[tuple, list[dict]]:
    return dict(X5.pmap(_vjob, candidates, processes, chunksize=2))


def evaluate_all(candidates: list[tuple], processes: int | None = None) -> dict[tuple, list[dict]]:
    def_jobs = [(*k, sd) for k in candidates for sd in R.EVAL_SEEDS]
    res = X5.pmap(_job, def_jobs, processes, chunksize=4)
    out: dict[tuple, list[dict]] = defaultdict(list)
    for r in res:
        out[cell_key(r)].append(r)
    return dict(out)


def wilson_rate(rs: list[dict]) -> dict:
    k = sum(1 for r in rs if all(r["ok"]) and not r["secondary"] and not r["exhausted"])
    return ST.proportion(k, len(rs))


# ---------------------------------------------------------------------------------------------------- the readings
def stress_action_table(rows: list[dict]) -> list[dict]:
    """One row per (stress, action, magnitude, duration, tick): the exploration summary, with the failure reason."""
    out = []
    for key, rs in sorted(cells(rows).items(), key=lambda kv: str(kv[0])):
        s = summarise(rs)
        out.append({"stress": key[0], "action": key[1] or "no action", "magnitude": key[2], "duration": key[3], "t": key[4], **s, "costly": costly(s) if s["effective_seeds"] == s["n"] else None, "failure": failure_reason(s, rs, key[1], key[4])})
    return out


def minimum_effective(table: list[dict], validated: set[tuple]) -> list[dict]:
    """Per (stress, action): the smallest magnitude that is effective (on all exploration seeds and validated), over the tested ticks and durations, and the ticks at which each effective magnitude works."""
    by: dict[tuple, list[dict]] = defaultdict(list)
    for r in table:
        if r["action"] != "no action":
            by[(r["stress"], r["action"])].append(r)
    out = []
    for (stress, action), rs in sorted(by.items()):
        eff = [r for r in rs if r["effective_seeds"] == r["n"] and (stress, action, r["magnitude"], r["duration"], r["t"]) in validated]
        if not eff:
            near = [r for r in rs if r["effective_seeds"] > 0]
            out.append({"stress": stress, "action": action, "minimum_effective_magnitude": None, "validated_settings": 0, "any_seed_effective": bool(near), "note": "no setting is effective on all exploration seeds and validated" if not near else "some seeds only: not a validated minimum"})
            continue
        m = min(r["magnitude"] for r in eff)  # every magnitude list is ordered from the weakest to the strongest repair (a lower target gain or efficiency is a weaker restoration)
        at = sorted({r["t"] for r in eff if r["magnitude"] == m})
        out.append({"stress": stress, "action": action, "minimum_effective_magnitude": m, "ticks_at_that_magnitude": at, "validated_settings": len(eff), "effective_magnitudes": sorted({r["magnitude"] for r in eff}), "effective_ticks": sorted({r["t"] for r in eff}), "any_seed_effective": True})
    return out


def phase_map(table: list[dict], stress: str, action: str, duration: int | None = None) -> dict:
    """The (magnitude, action tick) plane of one action on one stress: for each cell the outcome class (effective / unstable / secondary collapse / failed), for the reachable-recovery picture."""
    rs = [r for r in table if r["stress"] == stress and r["action"] == action and (duration is None or r["duration"] == duration)]
    mags, ts = sorted({r["magnitude"] for r in rs}), sorted({r["t"] for r in rs})
    grid = {}
    for r in rs:
        cls = "effective" if r["effective_seeds"] == r["n"] else "secondary collapse" if r["secondary_collapse"] else "unstable" if r["short"] and not r["long"] else "partial" if r["effective_seeds"] else "failed"
        grid[f"{r['magnitude']}@{r['t']}" + (f"/d{r['duration']}" if duration is None else "")] = cls
    return {"stress": stress, "action": action, "magnitudes": mags, "ticks": ts, "cells": grid}


# ---------------------------------------------------------------------------------------------------- Q: combined repairs
COMBO_TICKS = (113, 120, 130)
SECONDARY: tuple[tuple[str, float, int], ...] = (("resource.pulse", 0.5, 0), ("resource.pulse", 1.0, 0), ("resource.pulse", 2.0, 0), ("resource.inflow", 0.02, 120), ("renewal.auxiliary", 1.0, 0), ("renewal.auxiliary", 2.0, 0),
                                                 ("coupling.bridge", 1.5, 20), ("renewal.pulse", 1.5, 20), ("resource.reserve", 48.0, 0), ("resource.redistribute", 0.12, 10))


def primaries(stress_id: str) -> list[tuple[str, float, int]]:
    """The first part of a combined repair: the full restoration of the family the stress damaged (where there is one) and the internal M2 tap."""
    out: list[tuple[str, float, int]] = []
    for aid in ("coupling.restore", "renewal.restore", "renewal.restart", "address.restore", "address.reassign"):
        if applicable(aid, stress_id):
            out.append((aid, max(R.ACTIONS[aid].magnitudes or (0.0,)), 0))
    out.append(("internal.m2_tap", 0.0, 0))
    return out


def combos(stress_id: str) -> list[tuple[tuple[str, float, int], ...]]:
    """Pairs of different actions, restricted: (a primary, a secondary of another action). No exhaustive search of all combinations."""
    return [(p, s) for p in primaries(stress_id) for s in SECONDARY if s[0] != p[0]]


def _cjob(a: tuple) -> dict:
    stress_id, parts, t, seed = a
    st = R.STRESSES[stress_id]
    reps: list[dict] = []
    for aid, mag, dur in parts:
        reps += R.build_action(aid, st, mag, t, dur)
    o = R.run_eval(st, sorted(reps, key=lambda i: i["tick"]), seed, t)
    h, c = o["horizons"], o["costs"]
    return {"stress": stress_id, "parts": [list(p) for p in parts], "t": t, "seed": seed, "ok": [h[k]["success"] for k in ("short", "medium", "long")], "outcome": [h[k]["outcome"] for k in ("short", "medium", "long")], "latency": h["long"]["latency"],
            "secondary": h["long"]["secondary_collapse"], "exhausted": h["long"]["resource_exhausted"], "raw": c["raw"], "norm": c["normalised"]}


def explore_combined(stress_ids: tuple[str, ...], seeds: tuple[int, ...] = R.SEARCH_SEEDS, processes: int | None = None) -> list[dict]:
    jobs = [(sid, parts, t, sd) for sid in stress_ids for parts in combos(sid) for t in COMBO_TICKS for sd in seeds]
    return X5.pmap(_cjob, jobs, processes, chunksize=8)


def combined_cells(rows: list[dict]) -> dict[tuple, list[dict]]:
    out: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        out[(r["stress"], tuple(map(tuple, r["parts"])), r["t"])].append(r)
    return out


# ---------------------------------------------------------------------------------------------------- repairability
def classify_repairability(internal: bool, single: bool, combined: bool, near_miss: bool) -> str:
    """internal reconfiguration (class A), world-state repair (class B, single or combined), both, neither, inconclusive (only a near miss: effective on some seeds but not validated)."""
    external = single or combined
    if internal and external:
        return "both"
    if internal:
        return "internally reconfigurable"
    if external:
        return "externally repairable"
    return "inconclusive" if near_miss else "neither (under the tested actions)"
