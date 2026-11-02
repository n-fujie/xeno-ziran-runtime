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
    if scn.get(
        "diagnose", bool(scn.get("exchange") or scn.get("inherit"))
    ):  # would each decision have differed without the memory?
        for s in systems:
            s["diagnose"] = True
    if scn.get("exchange") and len(hist) >= 2:  # some history systems read another system's store
        ex = scn["exchange"]
        k = max(1, int(len(hist) * float(ex.get("fraction", 0.5))))
        writer = ex.get("writer_sid") or hist[0]
        if ex.get("placement") == "colocated":  # readers nearest to the writer's bay first (a natural topology, not a tuned one)
            ring = sorted({s["home"].split(".")[0] for s in systems}, key=int)
            bay = {s["sid"]: s["home"].split(".")[0] for s in systems}
            dist = lambda sid: min((int(bay[sid]) - int(bay[writer])) % len(ring), (int(bay[writer]) - int(bay[sid])) % len(ring))  # noqa: E731
            readers = sorted(hist[1:], key=lambda sid: (dist(sid), sid))[:k]
        else:
            readers = hist[1 : 1 + k]
        quality = ex.get("quality", "fresh")
        for s in systems:
            if s["sid"] in readers:
                s["shared_memory_from"] = writer
                if quality == "stale":
                    s["memory_delay"] = int(ex.get("delay", 30))  # entries readable only this long after they were written
            if quality == "wrong" and s["sid"] == writer:
                s["memory"] = "shuffled"  # the store's outcomes are permuted across entries: information that is wrong
    if scn.get("stop"):  # a fraction of the systems stops acting at a step
        k = max(1, int(len(systems) * float(scn["stop"].get("fraction", 0.3))))
        victims = [s["sid"] for s in systems][-k:]
        harness += [{"at": int(scn["stop"].get("at", steps // 2)), "do": "stop_system", "system": v} for v in victims]
    if scn.get("inherit") and len(hist) >= 2:  # a successor starts late and reads its predecessor's store
        pred, succ = scn["inherit"].get("writer_sid") or hist[0], hist[-1]
        if pred == succ:
            succ = next(h for h in hist if h != pred)
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


def _exchange_diagnosis(m: dict) -> str | None:
    """Why an exchange of results did or did not reach the decisions: separates a mechanism that was never reached, information that does not overlap
    with what the reader considers (an environment constraint), information the reader already has (redundancy), and information that changed decisions."""
    if not m["exchange_systems"]:
        return None
    if not m["reader_memory_reads"]:
        return "no reads: the mechanism was not reached (the reader never consulted the store)"
    if not m["store_entries_read"]:
        return "reads of an empty store: the system whose results were to be shared had produced none (nothing to exchange yet)"
    if not m["reader_memory_hits"]:
        return "reads without hits: the store holds nothing about the experiments the reader considers (no overlap; an environment constraint)"
    if not m["reader_decisions_changed_by_memory"]:
        return "hits without a changed decision: the information was redundant with what the reader already used"
    return "the stored results changed some of the reader's decisions"


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def productive_writer(arm: dict, gen: int, seed: int, steps: int) -> tuple[str | None, int]:
    """The history system with the most stored results in a control run (same seed, no exchange): who has something to share. Chosen on the
    control, disclosed in the record; it is the only use of the control's outcomes, and it keeps the exchange from being a read of an empty store."""
    ctl = {**arm, "scenario": {"diagnose": False}}
    r = LabRun(build_config(ctl, gen, seed, steps))
    for _ in range(steps):
        r.step()
    hist = [(len(s.memory), s.spec.sid) for s in r.science.systems.values() if s.spec.kind == "history"]
    if not hist or max(hist)[0] == 0:
        return None, 0
    n, sid = max(hist, key=lambda x: (x[0], -ord(x[1][-1])))
    return sid, n


def run(arm: dict, gen: int, seed: int, steps: int) -> dict:
    scn = arm.get("scenario", {})
    writer_info = None
    for key in ("exchange", "inherit"):
        if scn.get(key) and scn[key].get("writer", "productive") == "productive" and not scn[key].get("writer_sid"):
            sid, n = productive_writer(arm, gen, seed, steps)
            writer_info = {
                "rule": "history system with the most stored results in a control run",
                "writer": sid,
                "entries_in_control": n,
            }
            arm = {**arm, "scenario": {**scn, key: {**scn[key], **({"writer_sid": sid} if sid else {})}}}
            break
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
    rec_events = list(sci.events)
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
    readers = [s for s in sids if specs[s].shared_memory_from]
    rd = [sci.systems[s].diag for s in readers]
    r_reads = sum(summ[s]["memory_reads"] for s in readers)
    r_hits = sum(summ[s]["memory_hits"] for s in readers)
    r_dec = sum(d.get("decisions", 0) for d in rd)
    r_changed = sum(d.get("changed_without_memory", 0) for d in rd)
    store_entries = sum(len(sci.systems[w].memory) for w in {specs[s].shared_memory_from for s in readers})
    basis_memory = sum(
        1 for e in rec_events if e["type"] == "experiment_selected" and e["system"] in readers and e["basis"] == "memory"
    )
    selected = sum(1 for e in rec_events if e["type"] == "experiment_selected" and e["system"] in readers)
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
        "reader_decisions": float(r_dec),
        "reader_decisions_changed_by_memory": float(r_changed),
        "reader_memory_hits": float(r_hits),
        "reader_memory_reads": float(r_reads),
        "reader_hit_rate": (r_hits / r_reads) if r_reads else None,
        "reader_changed_share": (r_changed / r_dec) if r_dec else None,
        "reader_memory_basis_share": (basis_memory / selected) if selected else None,
        "store_entries_read": float(store_entries),
        "messages": float(r_reads),
        "variables_adopted": float(sum(len(summ[s]["variables_adopted"]) for s in sids)),
        "window_changes": float(sum(summ[s]["window_changes"] for s in sids)),
        "relocations": float(sum(summ[s]["relocations"] for s in sids)),
    }
    rec = r.record()
    return {
        "metrics": metrics,
        "exchange_diagnosis": _exchange_diagnosis(metrics),
        "writer": writer_info,
        "fingerprint_last": rec["steps"][-1]["fingerprint"],
        "events": len(rec["events"]),
        "wall_s": round(time.time() - t0, 3),
        "harness": cfg.get("harness", []),
        "n_steps": steps,
        "crashed": False,
    }
