"""Measurements on a population of research systems in the shared laboratory: do they behave as *several* research systems?

Running many simulations side by side is a load, not a research capability. This module measures, from what the systems actually did, ten
properties that distinguish a population of research systems from a pile of runs, and reports each as a number with what it is computed from:

 1. independent research histories      overlap (Jaccard) of the experiment pairs different systems have run; per-system history lengths
 2. different observation conditions    distinct (kind, sensor chamber, window, coverage size) tuples
 3. different variables / boundaries    distinct sets of adopted variables; distinct sets of observed chambers (the boundary of what a system sees)
 4. asynchronous activity               spread of first-request times; simultaneity (requests per step relative to the number of active systems)
 5. exchange of results                 memory reads of systems that read another system's store (shared_memory_from)
 6. mutual change of research conditions coverage drops a system suffers while it did not change its own sensor / isolate anything itself
 7. competition for research resources  denied and failed transfers per request
 8. stop of some systems                the others' request rate after the stop relative to before; no system crashed
 9. inheritance of results              reads from a predecessor's store by a system that starts later
10. expansion and shrinking of what can be investigated   per-system coverage changes (increases, decreases) over time

Nothing here asserts that any of these is *autonomy* or *scientific ability*: the numbers say what happened in a simulation.
"""

from __future__ import annotations

import itertools
import time

import numpy as np

from .population import population
from .record import LabRun


# Harness steps are numbered from 1: the first recorded step has t = 1 (a harness entry at 0 never fires).
def build_config(arm: dict, gen: int, seed: int, steps: int) -> dict:
    pop = arm.get("population", {})
    scn = arm.get("scenario", {})
    systems = population(
        int(pop.get("n", 20)), capacities=bool(pop.get("capacities", True)), diverse=bool(pop.get("diverse", True))
    )
    for s in systems:
        s.update(pop.get("system_overrides") or {})
    hist = [s["sid"] for s in systems if s["kind"] == "history"]
    harness: list[dict] = []
    if scn.get("exchange") and len(hist) >= 2:  # a fraction of the history systems read the first history system's store
        k = max(1, int(len(hist) * float(scn["exchange"].get("fraction", 0.5))))
        for s in systems:
            if s["sid"] in hist[1 : 1 + k]:
                s["shared_memory_from"] = hist[0]
    if scn.get("stop"):  # a fraction of the systems stops acting at a step
        k = max(1, int(len(systems) * float(scn["stop"].get("fraction", 0.3))))
        victims = [s["sid"] for s in systems][-k:]
        harness += [{"at": int(scn["stop"].get("at", steps // 2)), "do": "stop_system", "system": v} for v in victims]
    if scn.get("inherit") and len(hist) >= 2:  # a successor starts late and reads its predecessor's store
        pred, succ = hist[0], hist[-1]
        for s in systems:
            if s["sid"] == succ:
                s["shared_memory_from"] = pred
        harness += [
            {"at": 1, "do": "stop_system", "system": succ},
            {"at": int(scn["inherit"].get("start_at", steps // 2)), "do": "start_system", "system": succ},
        ]
    cfg = {
        "gen_seed": gen,
        "seed": seed,
        "settings": None,
        "physics": True,
        "horizon": steps,
        "systems": systems,
        "resources": float(scn.get("resources", 3.0)),
    }
    harness += list(scn.get("harness", []))  # any declared harness intervention (close_view / open_view / fail_gantry / ...)
    if harness:
        cfg["harness"] = harness
    return cfg


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def run(arm: dict, gen: int, seed: int, steps: int) -> dict:
    cfg = build_config(arm, gen, seed, steps)
    t0 = time.time()
    r = LabRun(cfg)
    sci = r.science
    sids = list(sci.systems)
    cov_series: dict[str, list[int]] = {s: [] for s in sids}
    req_prev = {s: 0 for s in sids}
    req_by_step: list[dict[str, int]] = []
    sensor_prev = {s: sci.systems[s].sensor for s in sids}
    self_changed: dict[str, set[int]] = {s: set() for s in sids}
    stopped_at = {h["system"]: h["at"] for h in cfg.get("harness", []) if h["do"] == "stop_system" and h["at"] > 0}
    for t in range(steps):
        r.step()
        step_req = {}
        for s in sids:
            st = sci.systems[s]
            step_req[s] = st.stats["requests"] - req_prev[s]
            req_prev[s] = st.stats["requests"]
            cov_series[s].append(len(sci.coverage(st)))
            if st.sensor != sensor_prev[s] or st.isolated:
                self_changed[s].add(t)
            sensor_prev[s] = st.sensor
        req_by_step.append(step_req)
    summ = sci.summary()
    specs = {s: sci.systems[s].spec for s in sids}
    # 1. independent histories
    pairs = {s: set(sci.systems[s].stats["pairs"]) for s in sids}
    active = [s for s in sids if pairs[s]]
    jac = [_jaccard(pairs[a], pairs[b]) for a, b in itertools.combinations(active, 2)]
    # 2/3. conditions, variables, boundaries
    conds = {(specs[s].kind, sci.systems[s].sensor, sci.systems[s].window, len(sci.coverage(sci.systems[s]))) for s in sids}
    variables = {tuple(sci.systems[s].features[6:]) for s in sids}
    bounds = {tuple(sorted(sci.coverage(sci.systems[s]))) for s in sids}
    # 4. asynchrony
    firsts = [summ[s]["first_request"] for s in sids if summ[s]["first_request"] is not None]
    busy = [
        (sum(1 for v in d.values() if v), sum(1 for s in sids if s not in sci.stopped)) for d in req_by_step if any(d.values())
    ]
    simult = float(np.mean([a / max(1, b) for a, b in busy])) if busy else None
    # 6. mutual change: coverage drops not caused by the system's own changes
    drops_ext = drops_all = 0
    expand = shrink = 0
    for s in sids:
        c = cov_series[s]
        for t in range(1, len(c)):
            if c[t] < c[t - 1]:
                shrink += 1
                drops_all += 1
                if t not in self_changed[s] and (t - 1) not in self_changed[s]:
                    drops_ext += 1
            elif c[t] > c[t - 1]:
                expand += 1
    # 7. competition
    req = sum(summ[s]["requests"] for s in sids)
    den = sum(summ[s]["denied"] for s in sids)
    fail = sum(summ[s]["failed"] for s in sids)
    # 8. stop: the request rate of the systems that keep running, after versus before the split step. Every run reports it, with the same
    # definition (the systems that would be stopped are the last 30%; the split is the stop step, or the middle of the run), so that a run with a
    # stop is compared with a run without one on the same quantity.
    t_split = min(stopped_at.values()) if stopped_at else steps // 2
    victims = set(stopped_at) if stopped_at else {s for s in sids[-max(1, int(len(sids) * 0.3)) :]}
    run_ids = [s for s in sids if s not in victims]
    rate_before = sum(d[s] for d in req_by_step[:t_split] for s in run_ids) / max(1, t_split * len(run_ids))
    rate_after = sum(d[s] for d in req_by_step[t_split:] for s in run_ids) / max(1, (steps - t_split) * len(run_ids))
    # 5 / 9. exchange and inheritance
    ex_reads = sum(summ[s]["memory_reads"] for s in sids if specs[s].shared_memory_from)
    ex_unavail = sum(summ[s]["memory_unavailable"] for s in sids if specs[s].shared_memory_from)
    metrics: dict[str, float | None] = {
        "n_systems": float(len(sids)),
        "systems_with_history": float(len(active)),
        "history_overlap_mean": float(np.mean(jac)) if jac else None,
        "distinct_conditions": float(len(conds)),
        "distinct_variable_sets": float(len(variables)),
        "distinct_boundaries": float(len(bounds)),
        "first_request_spread": float(np.std(firsts)) if len(firsts) > 1 else None,
        "simultaneity": simult,
        "exchange_systems": float(sum(1 for s in sids if specs[s].shared_memory_from)),
        "exchange_reads": float(ex_reads),
        "exchange_unavailable": float(ex_unavail),
        "external_coverage_drops": float(drops_ext),
        "coverage_drops": float(drops_all),
        "isolations": float(sum(summ[s]["isolations"] for s in sids)),
        "requests": float(req),
        "completed": float(sum(summ[s]["completed"] for s in sids)),
        "denied": float(den),
        "failed": float(fail),
        "contention_rate": (den + fail) / req if req else None,
        "stopped_systems": float(len(stopped_at)),
        "rate_before_stop": rate_before,
        "rate_after_stop": rate_after,
        "rate_ratio_after_before": (rate_after / rate_before) if rate_before else None,
        "stop_applied": float(bool(stopped_at)),
        "coverage_expansions": float(expand),
        "coverage_shrinks": float(shrink),
        "coverage_mean": float(np.mean([np.mean(c) for c in cov_series.values()])),
        "variables_adopted": float(sum(len(summ[s]["variables_adopted"]) for s in sids)),
        "window_changes": float(sum(summ[s]["window_changes"] for s in sids)),
        "relocations": float(sum(summ[s]["relocations"] for s in sids)),
    }
    rec = r.record()
    return {
        "metrics": metrics,
        "fingerprint_last": rec["steps"][-1]["fingerprint"],
        "events": len(rec["events"]),
        "wall_s": round(time.time() - t0, 3),
        "harness": cfg.get("harness", []),
        "n_steps": steps,
        "crashed": False,
    }
