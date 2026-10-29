"""MEOS-0, sixth stage: the repair library, the comparison of repair controllers, unknown stresses and false positives.

The library is built from the exploration and validation results only (seeds 1-10); the controllers are evaluated on seeds 11-30. Unknown stresses are variations of the stresses the library was built for (a different severity, profile or onset): they test whether a repair found for one
stress carries over to a nearby one, and nothing is assumed about it.

A controller *succeeds* in a run if the run recovers at the long horizon (``repair6.outcome_at``, ACTIVE on the last 30 ticks, no secondary collapse, resource not exhausted). It is *effective* against a stress if its success rate exceeds that of no repair by at least 0.30 and Fisher's exact p is below 0.05
(fixed before the runs). Holm's correction over all comparisons is reported beside the unadjusted p. A failure is classified into one of ten classes (``failure_class``) from the run and its controller log.
"""

from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from . import engine as E
from . import reconf as RC
from . import repair6 as R
from . import repair_ctl as RCTL
from . import stage5_experiments as X5
from . import stats5 as ST

DOCS = Path(__file__).resolve().parents[3] / "docs" / "ecosystem"
KINDS = RCTL.KINDS


# ---------------------------------------------------------------------------------------------------- unknown stresses (variations of the stresses the library was built for)
def unknown_stresses() -> list[tuple[str, R.Stress, int, str]]:
    """(id, stress, onset, what varies). None of these settings was used to build the library."""
    return [
        ("coupling gain 0.3 (stronger drop)", R.stress_coupling(0.3), 100, "severity"), ("coupling gain 0.7 (weaker drop)", R.stress_coupling(0.7), 100, "severity"),
        ("resource regrow 0.015 charge 0.3 (different profile)", R.stress_resource(0.015, 0.3), 100, "profile"), ("renewal efficiency 0.4 (stronger)", R.stress_renewal_efficiency(0.4), 100, "severity"),
        ("renewal efficiency 0.8 (weaker)", R.stress_renewal_efficiency(0.8), 100, "severity"), ("renewal stopped at tick 130 (delayed failure)", R.stress_renewal_stopped(), 130, "onset"),
        ("Address partial 0.3 (stronger)", R.stress_address(0.3), 100, "severity"), ("Address partial 0.7 (weaker)", R.stress_address(0.7), 100, "severity"),
        ("Address partial 0.5 at tick 80 (earlier)", R.stress_address(0.5), 80, "onset"), ("Address partial 0.5 at tick 130 (later)", R.stress_address(0.5), 130, "onset"),
        ("coupling gain 0.5 at tick 130 (later)", R.stress_coupling(0.5), 130, "onset"),
    ]


class _Probe:
    """Records the signature (the five sensed features) at the first firm detection; never acts."""

    kind = "probe"

    def __init__(self, debounce: int = 3, start: int = 60):
        self.sig: dict[str, str] | None = None
        self.streak: dict[str, int] = {}
        self.debounce, self.start = debounce, start

    def step(self, run: E.Run) -> None:
        if self.sig is not None or run.t < self.start:
            return
        f = RC.sense(run)
        for k in RC.FEATURES:
            self.streak[k] = self.streak.get(k, 0) + 1 if f[k] != RC.NORMAL[k] else 0
        if any(self.streak[k] >= self.debounce for k in RC.FEATURES):
            self.sig = f


def signature(stress: R.Stress, onset: int = R.STRESS_TICK, seeds: tuple[int, ...] = R.SEARCH_SEEDS) -> dict[str, str]:
    c: Counter = Counter()
    for sd in seeds:
        run = E.Run(R.config(sd, 300), R.schedule(stress, [], onset))
        p = _Probe()
        while True:
            p.step(run)
            if not run.step():
                break
        if p.sig:
            c[tuple(sorted(p.sig.items()))] += 1
    return dict(c.most_common(1)[0][0]) if c else {}


# ---------------------------------------------------------------------------------------------------- the library
def build_library(results: dict) -> tuple[list[dict], dict[str, dict]]:
    """One plan per setting that was validated (alone, or as a synergistic pair) at the default action tick, with the signature(s) of the stresses it was validated for, the expected recovery (the share of the stresses that share that signature
    for which it was validated) and the cost (the mean of the normalised switching, persistence energy rate and collateral over the library, equal weights: a stated convention, the raw values are kept beside it)."""
    sigs = {sid: signature(R.STRESSES[sid]) for sid in R.STRESS_ORDER}
    groups: dict[tuple, list[str]] = defaultdict(list)
    for sid, g in sigs.items():
        groups[tuple(sorted(g.items()))].append(sid)
    plans: dict[str, dict] = {}

    def add(pid: str, actions: list[dict], klass: str, stress: str, comps: dict) -> None:
        p = plans.setdefault(pid, {"id": pid, "actions": actions, "klass": klass, "stresses": [], "cost_components": comps})
        p["stresses"].append(stress)

    for v in results["single_settings"]:
        if v["status"] == "validated" and v["t"] == R.T_ACT:
            add(f"{v['action']} m={v['magnitude']} d={v['duration']}", [{"action": v["action"], "magnitude": v["magnitude"], "duration": v["duration"]}], R.ACTIONS[v["action"]].klass, v["stress"],
                {"switching": v["costs"]["raw"]["switching"], "collateral": v["costs"]["raw"]["collateral"], "energy_rate_norm": v["costs"]["energy_rate_norm"]})
    for v in results["combined_settings"]:
        if v["status"] == "validated" and v["t"] == R.T_ACT and v.get("synergistic"):
            parts = v["parts"]
            add(" + ".join(f"{a} m={m} d={d}" for a, m, d in parts), [{"action": a, "magnitude": m, "duration": d} for a, m, d in parts], "A+B" if any(R.ACTIONS[a].klass == "A" for a, _, _ in parts) else "B", v["stress"], v["costs"])
    for p in plans.values():
        p["signatures"] = [dict(sigs[s]) for s in sorted(set(p["stresses"]))]
        share = []
        for s in set(p["stresses"]):
            grp = groups[tuple(sorted(sigs[s].items()))]
            share.append(len(set(p["stresses"]) & set(grp)) / len(grp))
        p["expected"] = round(sum(share) / len(share), 3)
    lib = sorted(plans.values(), key=lambda p: p["id"])
    mx = {k: (max(p["cost_components"][k] for p in lib) or 1.0) for k in ("switching", "collateral", "energy_rate_norm")} if lib else {}
    for p in lib:
        p["cost"] = round(sum(p["cost_components"][k] / mx[k] for k in mx) / len(mx), 4)
    return lib, sigs


# ---------------------------------------------------------------------------------------------------- failure classes
FAILURE_CLASSES = ("no effective action", "action too weak", "action too late", "overshoot", "action destabilized system", "insufficient resource", "Address unresolved", "detection failure", "action cost too high", "secondary collapse")


def failure_class(o: dict, ctx: dict) -> str | None:
    """The reason a controller run did not succeed (None if it did and was not costly)."""
    long = o["horizons"]["long"]
    if long["success"]:
        c = o["costs"]
        return "action cost too high" if c["normalised"]["persistence_energy_rate"] > 1.5 or c["raw"]["collateral"] > 1.0 else None
    if ctx["attempts"] == 0:
        return "detection failure"
    if long["resource_exhausted"]:
        return "insufficient resource"
    if long["secondary_collapse"]:
        return "overshoot" if any(a["action"].endswith("pulse") and a["magnitude"] >= 3.0 for e in ctx["log"] for a in e["actions"]) else "secondary collapse"
    if o["horizons"]["short"]["success"] and not long["success"]:
        return "action destabilized system"
    if ctx["family"] == "address":
        return "Address unresolved"
    if ctx["first_action_tick"] is not None and ctx["first_action_tick"] > ctx["latest_effective_tick"]:
        return "action too late"
    return "no effective action"


# ---------------------------------------------------------------------------------------------------- running controllers
def _job(a: tuple) -> dict:
    sid, onset, kind, seed, library, latest = a
    st = R.STRESSES.get(sid) or next(s for i, s, o, _ in unknown_stresses() if i == sid)
    stress = None if sid == "no stress" else st
    ctl = RCTL.RepairController(kind, library, seed=seed, noise=0.1)
    cfg = R.config(seed)
    base = R.schedule(stress, [], onset)
    rec = RCTL.run_repaired(cfg, base, ctl)
    injected = [i for i in rec["interventions"] if i not in base] if "interventions" in rec else []
    t_act = onset + 13
    o = R.evaluate(rec, R.reference(seed), injected, t_act)
    log = rec["controller"]["log"]
    first = next((e["tick"] for e in log), None)
    ctx = {"attempts": rec["controller"]["attempts"], "log": log, "family": st.family if stress else "none", "first_action_tick": first, "latest_effective_tick": latest.get(sid, 0)}
    h = o["horizons"]
    return {"stress": sid, "onset": onset, "controller": kind, "seed": seed, "ok": [h[k]["success"] for k in ("short", "medium", "long")], "outcome": [h[k]["outcome"] for k in ("short", "medium", "long")], "latency": h["long"]["latency"], "attempts": ctx["attempts"],
            "injected": len(injected), "first_decision": first, "raw": o["costs"]["raw"], "norm": o["costs"]["normalised"], "failure": failure_class(o, ctx), "selected": [e["selected"] for e in log], "actual": [e["actual"]["recovered_so_far"] if e["actual"] else None for e in log]}


def run_controllers(library: list[dict], stresses: list[tuple[str, int]], kinds: tuple[str, ...] = KINDS, seeds: tuple[int, ...] = R.EVAL_SEEDS, latest: dict | None = None, processes: int | None = None) -> list[dict]:
    jobs = [(sid, onset, kind, sd, library, latest or {}) for sid, onset in stresses for kind in kinds for sd in seeds]
    return X5.pmap(_job, jobs, processes, chunksize=2)


def summarise(rows: list[dict]) -> list[dict]:
    by: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        by[(r["stress"], r["controller"])].append(r)
    out = []
    for (sid, kind), rs in sorted(by.items()):
        n = len(rs)
        ks = [sum(1 for r in rs if r["ok"][i]) for i in range(3)]
        out.append({"stress": sid, "controller": kind, "n": n, "success_short": ST.proportion(ks[0], n), "success_medium": ST.proportion(ks[1], n), "success_long": ST.proportion(ks[2], n), "mean_attempts": round(sum(r["attempts"] for r in rs) / n, 2),
                    "mean_interventions": round(sum(r["injected"] for r in rs) / n, 2), "mean_energy_use": round(sum(r["raw"]["energy_use"] for r in rs) / n, 2), "mean_collateral": round(sum(r["raw"]["collateral"] for r in rs) / n, 3),
                    "median_latency": sorted(r["latency"] for r in rs if r["latency"] is not None)[len([1 for r in rs if r["latency"] is not None]) // 2] if any(r["latency"] is not None for r in rs) else None,
                    "failures": dict(Counter(r["failure"] for r in rs if r["failure"]))})
    return out


def verdicts(summary: list[dict], stresses: list[str]) -> list[dict]:
    idx = {(s["stress"], s["controller"]): s for s in summary}
    out = []
    for sid in stresses:
        base = idx[(sid, "none")]["success_long"]
        for kind in KINDS:
            if kind == "none":
                continue
            r = idx[(sid, kind)]["success_long"]
            c = ST.compare_proportions(r["k"], r["n"], base["k"], base["n"])
            d = r["p"] - base["p"]
            out.append({"stress": sid, "controller": kind, "success": f"{r['k']}/{r['n']}", "none": f"{base['k']}/{base['n']}", "difference": round(d, 3), "cohens_h": c["cohens_h"], "fisher_p": c["fisher_exact_p"], "_d": d})
    from .stage5_final import holm
    adj = holm([o["fisher_p"] for o in out])
    for o, a in zip(out, adj, strict=True):
        d = o.pop("_d")
        o["holm_p"] = a
        o["survives_holm"] = a < 0.05
        o["verdict"] = "effective" if d >= 0.30 and o["fisher_p"] < 0.05 else "harmful" if d <= -0.30 and o["fisher_p"] < 0.05 else "no effect"
    return out


def example_record(library: list[dict], stress_id: str, kind: str, seed: int = 1) -> dict:
    """One controller run in full (record with the controller log), for the replay and the interface."""
    st = R.STRESSES[stress_id]
    ctl = RCTL.RepairController(kind, library, seed=seed)
    rec = RCTL.run_repaired(R.config(seed), R.schedule(st, []), ctl)
    return rec


def dumps(x: Any) -> str:
    return json.dumps(x, indent=0, default=str)


__all__ = ["build_library", "run_controllers", "summarise", "verdicts", "signature", "unknown_stresses", "FAILURE_CLASSES", "example_record", "copy"]
