"""MEOS-0, fifth stage: what a retained set *does*, beyond whether the operation persists — the profile on which two routes are compared, and the levels of equivalence.

Two routes that both end ACTIVE are not thereby equivalent. A profile measures, for one retained set under one condition (every number from real runs over the confirmation seeds):
the preserved operation, energy use, resource throughput, recovery latency, stability, sensitivity to a battery of perturbations, history dependence, Address dependence, observation
robustness, the SSS region and the collapse modes. ``compare`` says at which level two profiles stop being the same.
"""

from __future__ import annotations

import statistics
from typing import Any

import numpy as np

from . import analysis as A
from . import engine as E
from . import experiments as X
from . import mfs5 as M
from . import stage4 as S4

SEEDS = M.CONFIRM_SEEDS
HORIZON = 240

PERTURBATIONS: dict[str, list[dict]] = {
    "address loss of A2 (40 ticks)": [{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "loss"}, {"tick": 140, "op": "ADDRESS", "target": "A2", "mode": "restore"}],
    "resource pulse 4.0 (oversupply)": [X.pulse(100, 4.0)],
    "renewal efficiency 0.7": [{"tick": 100, "op": "RECONFIGURE", "path": "environment.renew_efficiency", "value": 0.7}],
    "coupling weakened (gain 0.5)": [{"tick": 100, "op": "RECONFIGURE", "path": "coupling.gain", "value": 0.5}],
    "SSS scale 1.15": [{"tick": 100, "op": "ALTER_SSS", "scale": 1.15}],
    "sensing noise 0.05": [{"tick": 100, "op": "RECONFIGURE", "path": "noise", "value": 0.05}],
}
ADDRESS_FAULTS: dict[str, list[dict]] = {
    "loss of A1": [{"tick": 100, "op": "ADDRESS", "target": "A1", "mode": "loss"}],
    "loss of A2": [{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "loss"}],
    "partial A2 (50 %)": [{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "partial", "fraction": 0.5}],
    "fragment of A2 (50 %)": [{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "fragment", "fraction": 0.5}],
    "delayed update of A2 (to 9,6; 20 ticks)": [{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "delayed", "x": 9, "y": 6, "delay": 20}],
}
OBSERVATIONS: dict[str, dict] = {
    "interval 2": {"sampling_interval": 2},
    "interval 3": {"sampling_interval": 3},
    "stride 2": {"spatial_stride": 2},
    "region away from both": {"region": [8, 8, 12, 12]},
    "occluder over A1": {"occluder": [3, 6, 3, 6]},
    "detection threshold 0.1": {"threshold": 0.1},
}


def _label(rec: dict) -> str:
    return rec["final_status"]["label"]


def _mode(rec: dict) -> str | None:
    dep = rec["final_status"].get("dependency") or {}
    return dep.get("precondition")


def _cv(rec: dict) -> float | None:
    ticks = [c["tick"] for c in rec["cycles"] if c["tick"] >= len(rec["frames"]) - 100]
    iv = np.diff(ticks)
    return round(float(iv.std() / iv.mean()), 4) if len(iv) > 2 and iv.mean() > 0 else None


def profile(cond: dict, retained: frozenset | set, seeds: tuple[int, ...] = SEEDS) -> dict:
    """The profile of one retained set under one condition."""
    base_ivs = M.retained_interventions(cond, retained)
    base_runs = [E.run_record(M._config(cond, sd, HORIZON), base_ivs) for sd in seeds]
    tm = [X.trace_metrics(r) for r in base_runs]
    prof: dict[str, Any] = {
        "preserved_operation": sum(_label(r) == "ACTIVE" for r in base_runs) / len(seeds),
        "energy_use": round(statistics.fmean(t["cumulative_energy_use"] for t in tm), 3),
        "resource_throughput": round(statistics.fmean(t["resource_throughput"] for t in tm), 3),
        "stability_cycle_cv": [c for c in (_cv(r) for r in base_runs) if c is not None],
    }
    cvs = prof["stability_cycle_cv"]
    prof["stability_cycle_cv"] = round(statistics.fmean(cvs), 4) if cvs else None
    rp = M.recovery_probe(cond, frozenset(retained), seeds)
    lat = [x for x in rp.get("latency_with_pulse", []) if x is not None]
    prof["recovery"] = rp
    prof["recovery_latency"] = round(statistics.fmean(lat), 2) if lat else None
    # sensitivity to a battery of perturbations, and how the collapses end
    sens: dict[str, float] = {}
    modes: dict[str, str | None] = {}
    for name, ivs in PERTURBATIONS.items():
        runs = [E.run_record(M._config(cond, sd, HORIZON), [*base_ivs, *ivs]) for sd in seeds]
        sens[name] = sum(_label(r) != "ACTIVE" for r in runs) / len(seeds)
        ms = [m for m in (_mode(r) for r in runs if _label(r) != "ACTIVE") if m]
        modes[name] = max(set(ms), key=ms.count) if ms else None
    prof["perturbation_sensitivity"] = sens
    prof["collapse_modes"] = modes
    # history dependence: the set without its history (only when it retains it)
    if "history" in retained:
        nh = [E.run_record(M._config(cond, sd, HORIZON), M.retained_interventions(cond, set(retained) - {"history"})) for sd in seeds]
        prof["history_dependence"] = round(1 - sum(_label(r) == "ACTIVE" for r in nh) / len(seeds), 3)
    else:
        prof["history_dependence"] = None  # not retained: nothing to depend on
    af: dict[str, float] = {}
    for name, ivs in ADDRESS_FAULTS.items():
        runs = [E.run_record(M._config(cond, sd, HORIZON), [*base_ivs, *ivs]) for sd in seeds]
        af[name] = sum(_label(r) != "ACTIVE" for r in runs) / len(seeds)
    prof["address_fault_collapse"] = af
    prof["address_dependence"] = round(statistics.fmean(af.values()), 3)
    # observation robustness: how often the observer's conclusion equals the run's (operation and observation kept apart)
    agree = {}
    for name, ob in OBSERVATIONS.items():
        agree[name] = sum(A.observe(r, ob)["observed_state"] == A.observe(r, ob)["operational_state"] for r in base_runs) / len(seeds)
    prof["observation_agreement"] = agree
    prof["observational_robustness"] = round(statistics.fmean(agree.values()), 3)
    prof["sss_region"] = sss_point(cond, retained, 1.0, 1.0, 1.0)["region"]
    return prof


def sss_point(cond: dict, retained: frozenset | set, scale: float, size: float, speed: float, seeds: tuple[int, ...] = (1, 2)) -> dict:
    """The region of one SSS setting for a retained set (the definitions of ``experiments.sss_phase``): ACTIVE at tick 239 and 479 in every seed, COLLAPSED at 239 in every seed, otherwise
    METASTABLE; a collapsed point is RECOVERY-CAPABLE if a pulse at 300 restores it; an ACTIVE point is OBSERVATION-SENSITIVE if an observation at interval 2 concludes otherwise."""
    base_ivs = M.retained_interventions(cond, retained)
    per = []
    for sd in seeds:
        cfg = X.cfg_with(M._config(cond, sd, 480), sss={"scale": scale, "size": size, "speed": speed})
        rec = E.run_record(cfg, base_ivs)
        s239, s479 = rec["frames"][239]["status"], rec["frames"][-1]["status"]
        obs = A.observe(rec, {"sampling_interval": 2})["observed_state"]
        cap = None
        if s239 != "ACTIVE":
            r2 = E.run_record(cfg, [*base_ivs, X.pulse(300, 2.0)])
            cap = _label(r2) == "ACTIVE" and _label(rec) != "ACTIVE"
        per.append({"at_239": s239, "at_479": s479, "observed_interval_2": obs, "recovery_capable": cap})
    p = {
        "class": "ACTIVE" if all(x["at_239"] == "ACTIVE" and x["at_479"] == "ACTIVE" for x in per) else "COLLAPSED" if all(x["at_239"] != "ACTIVE" for x in per) else "metastable",
        "recovery_capable": any(x["recovery_capable"] for x in per),
        "observation_sensitive": all(x["observed_interval_2"] != "ACTIVE" for x in per),
    }
    return {"scale": scale, "size": size, "speed": speed, "class": p["class"], "region": S4.sss_region(p), "per_seed": per}


# ---------------------------------------------------------------------------------------------------- equivalence
LEVELS = (
    "L1: the same preserved operation",
    "L2: and the same energy use, resource throughput and stability (within 15 %, 15 %, 0.10)",
    "L3: and the same sensitivity to perturbation, history dependence and Address dependence (Jaccard of the collapsing perturbations >= 0.8, differences <= 0.2)",
    "L4: and the same collapse modes, observational robustness (within 0.2) and SSS region",
)


def _close(a: float | None, b: float | None, rel: float | None = None, absol: float | None = None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if rel is not None:
        return abs(a - b) <= rel * max(abs(a), abs(b), 1e-9)
    return abs(a - b) <= (absol or 0.0)


def _jaccard(a: dict[str, float], b: dict[str, float]) -> float:
    sa, sb = {k for k, v in a.items() if v > 0}, {k for k, v in b.items() if v > 0}
    return 1.0 if not (sa | sb) else len(sa & sb) / len(sa | sb)


def compare(pa: dict, pb: dict) -> dict:
    """Equivalence level of two profiles: the highest level whose conditions hold together with every lower level; at the first level that fails, what differs is listed."""
    checks: list[tuple[str, bool, list[str]]] = []
    l1 = pa["preserved_operation"] == 1.0 and pb["preserved_operation"] == 1.0
    checks.append(("L1", l1, [] if l1 else ["preserved operation"]))
    diff2 = [n for n, ok in (("energy use", _close(pa["energy_use"], pb["energy_use"], rel=0.15)), ("resource throughput", _close(pa["resource_throughput"], pb["resource_throughput"], rel=0.15)), ("stability", _close(pa["stability_cycle_cv"], pb["stability_cycle_cv"], absol=0.10))) if not ok]
    checks.append(("L2", not diff2, diff2))
    jac = _jaccard(pa["perturbation_sensitivity"], pb["perturbation_sensitivity"])
    diff3 = [n for n, ok in ((f"perturbation sensitivity (Jaccard {jac:.2f})", jac >= 0.8), ("history dependence", _close(pa["history_dependence"], pb["history_dependence"], absol=0.2)), ("Address dependence", _close(pa["address_dependence"], pb["address_dependence"], absol=0.2))) if not ok]
    checks.append(("L3", not diff3, diff3))
    diff4 = [n for n, ok in (("collapse modes", pa["collapse_modes"] == pb["collapse_modes"]), ("observational robustness", _close(pa["observational_robustness"], pb["observational_robustness"], absol=0.2)), ("SSS region", pa["sss_region"] == pb["sss_region"])) if not ok]
    checks.append(("L4", not diff4, diff4))
    level = 0
    for i, (_, ok, _) in enumerate(checks, 1):
        if not ok:
            break
        level = i
    first_fail = next(((n, d) for n, ok, d in checks if not ok), None)
    verdict = f"operationally equivalent at level L{level}" if level else "not equivalent even at L1"
    if first_fail:
        verdict += f"; non-equivalent at level {first_fail[0]} (differs in: {', '.join(first_fail[1])})"
    return {"equivalent_through_level": level, "verdict": verdict, "differences_at_first_failed_level": first_fail[1] if first_fail else []}


# ---------------------------------------------------------------------------------------------------- route topology of a run
def _initial_enabled(rec: dict, universe: tuple[str, ...]) -> set[str]:
    cfg = rec["config"]
    on = set(universe)
    if (cfg.get("m2") or {}).get("sense", "none") == "none":
        on.discard("m2_tap")
    if not cfg["history"]["enabled"]:
        on.discard("history")
    if not cfg["environment"]["gradient"]:
        on.discard("resource_gradient")
    return on


def topology(rec: dict, universe: tuple[str, ...] = M.COMPONENTS5) -> dict:
    """The route topology of a run, from its record alone: when each component was enabled or cut, the route changes (``ROUTE`` operations with whatever a controller recorded in them), the
    transitions between MFS and the paths each component belongs to. A client reconstructs the state at any tick from this; nothing is drawn that the record does not contain."""
    on = _initial_enabled(rec, universe)
    timeline: dict[str, list[list[Any]]] = {c: [[0, c in on]] for c in universe}
    failed_by: dict[str, dict[str, Any]] = {}
    intervals: list[dict[str, Any]] = []  # each time a component was removed or isolated: from when to when (None: not restored)
    events: list[dict] = []
    installed_tap = "m2_tap" in on
    for iv in rec["intervention_log"]:
        t, op = iv["tick"], iv["op"]
        change: list[tuple[str, bool]] = []
        if op in ("REMOVE", "ISOLATE") and iv.get("target") in universe:
            change.append((iv["target"], False))
            failed_by[iv["target"]] = {"op": op, "tick": t}
            intervals.append({"component": iv["target"], "op": op, "from": t, "to": None})
        elif op == "RECONNECT" and iv.get("target") in universe:
            change.append((iv["target"], True))
            failed_by.pop(iv["target"], None)
            for iv2 in intervals:
                if iv2["component"] == iv["target"] and iv2["to"] is None:
                    iv2["to"] = t
        elif op == "ROUTE":
            if "m2" in iv:
                installed_tap = True
                change.append(("m2_tap", iv["m2"].get("sense", "none") != "none"))
            if "history" in iv:
                change.append(("history", iv["history"] == "on"))
            events.append({"tick": t, "m2": iv.get("m2"), "history": iv.get("history"), "why": iv.get("why"), "from": iv.get("from"), "to": iv.get("to"), "cost": iv.get("cost"), "trigger": iv.get("trigger"), "controlled": "why" in iv})
        for c, state in change:
            if timeline[c][-1][1] != state or timeline[c][-1][0] != t:
                timeline[c].append([t, state])
    ctl = rec.get("controller") or {}
    transitions = [{"tick": e["tick"], "from": e["from"], "to": e["to"], "cost": e["cost"], "trigger": e["trigger"], "enabled": e["enabled"]} for e in ctl.get("log", []) if e.get("kind") == "switch"]
    decisions = [e for e in ctl.get("log", []) if e.get("kind") == "decide"]
    return {
        "universe": list(universe), "component_timeline": timeline, "installed_m2_tap": installed_tap, "failed_components": failed_by, "failure_intervals": intervals, "route_events": events, "transitions": transitions,
        "decisions": [{k: e[k] for k in ("tick", "trigger", "current_mfs", "candidates", "chosen", "outcome") if k in e} for e in decisions],
        "initial_mfs": decisions[0]["current_mfs"] if decisions else None, "paths": {k: list(v) for k, v in M.PATH_COMPONENTS.items()},
        "controller": ctl.get("kind", "none"), "last_tick": len(rec["frames"]) - 1,
    }
