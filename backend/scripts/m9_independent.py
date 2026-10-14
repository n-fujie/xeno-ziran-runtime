"""Independent checks of the M9 findings (verification Levels B and C). Shares no measurement or statistics code with
the experiment harness: it does not import xzr.lab.causal, xzr.lab.m9's analyses or xzr.hpo.stats.

    B1  recount   re-execute sampled confirmatory runs, keep only the run *record* (the raw event log) and recount B's
                  completed and failed transfers and its request-to-delivery latency from those events with code written
                  here; compare with the harness's measures (published per-run values)
    B2  statistics recompute the primary M9-A/B verdicts from the published per-run values with an independently written
                  paired sign-flip test (exact enumeration for small n, otherwise Monte Carlo), percentile bootstrap,
                  Holm adjustment and the declared DETECTED rule; compare statuses
    C1  queue     an independent first-in-first-out single-server model of the bay-0 gantry, fed with the recorded legs
                  (arrival, service duration, owner) of runs with A present: B's predicted waiting with and without A's
                  legs, against the waiting B shows in the runs without A

Usage: python scripts/m9_independent.py <published m9ab.json> <out.json> [seeds]
"""

from __future__ import annotations

import json
import math
import sys
from itertools import product
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xzr.lab import m9 as M  # noqa: E402  (configurations and seed ranges only)
from xzr.lab.record import LabRun  # noqa: E402  (the system under test)

ALPHA, PRACTICAL = 0.01, 0.02


# ------------------------------------------------------------------ B1: recount from the raw record
def recount(rec: dict, sid: str) -> dict[str, float]:
    sci = rec.get("science_events", [])
    phys = rec.get("physical_events", [])
    delivered = [e for e in sci if e["type"] == "material_delivered" and e["system"] == sid]
    failed = [e for e in sci if e["type"] in ("experiment_failed", "delivery_blocked") and e["system"] == sid]
    complete = {(e["src"], e["dst"], e["t"]): e for e in phys if e["type"] == "transfer_complete"}
    lat = [complete[(e["src"], e["dst"], e["t"])]["t"] - complete[(e["src"], e["dst"], e["t"])]["requested_at"]
           for e in delivered if (e["src"], e["dst"], e["t"]) in complete]
    return {"completed": float(len(delivered)), "failed": float(len(failed)),
            "latency_mean": float(np.mean(lat)) if lat else math.nan}


def run_cond(cond: str, i: int) -> tuple[dict, list[dict]]:
    gen0, seed0 = M.RANGES["confirm"]
    r = LabRun(M.config(M.EXPERIMENTS["m9ab"][cond], gen0 + i, seed0 + i))
    while not r.done:
        r.step()
    rec = json.loads(json.dumps(r.record()))  # only what a record file would hold
    assert r.lab is not None
    return rec, [dict(x) for x in r.lab.trace["legs"]]


# ------------------------------------------------------------------ B2: statistics written independently
def p_signflip(d: np.ndarray, seed: int) -> float:
    if d.size == 0 or np.all(d == 0):
        return 1.0
    obs = abs(d.mean())
    if d.size <= 16:
        s = np.array(list(product((1.0, -1.0), repeat=d.size)))
        return float((np.abs((s * d).mean(1)) >= obs - 1e-12).mean())
    s = np.random.default_rng(seed).choice((-1.0, 1.0), size=(50000, d.size))
    return float(((np.abs((s * d).mean(1)) >= obs - 1e-12).sum() + 1) / (50000 + 1))


def holm(ps: list[float]) -> list[float]:
    order = np.argsort(ps)
    out, run = [0.0] * len(ps), 0.0
    for rank, k in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[k]))
        out[k] = run
    return out


def statuses(x: list[dict], y: list[dict], metrics, noise: dict | None, seed: int) -> dict[str, str]:
    res = {}
    for m in metrics:
        a = np.array([r.get(m, math.nan) for r in x], float)
        b = np.array([r.get(m, math.nan) for r in y], float)
        ok = ~(np.isnan(a) | np.isnan(b))
        d = a[ok] - b[ok]
        floor = 0.0
        if noise is not None:
            nz = noise[m][~np.isnan(noise[m])]
            floor = abs(nz.mean()) + 1.96 * nz.std(ddof=1) / math.sqrt(nz.size) if nz.size > 1 else 0.0
        res[m] = {"d": d, "p": p_signflip(d, seed), "scale": max(abs(a[ok].mean()), abs(b[ok].mean()), 1e-12) if ok.any() else 1,
                  "floor": floor}
    ms = [m for m in metrics if res[m]["d"].size]
    for m, ph in zip(ms, holm([res[m]["p"] for m in ms]), strict=True):
        res[m]["ph"] = ph
    out = {}
    for m in metrics:
        r = res[m]
        if not r["d"].size:
            out[m] = "NOT MEASURED"
        elif np.allclose(r["d"], 0):
            out[m] = "IDENTICAL"
        elif r["ph"] < ALPHA and abs(r["d"].mean()) >= PRACTICAL * r["scale"] and abs(r["d"].mean()) > r["floor"]:
            out[m] = "DETECTED"
        else:
            out[m] = "not detected"
    return out


def per_run(doc: dict, cond: str, sid: str = "B") -> list[dict]:
    rs = sorted((r for r in doc["per_run"] if r["cond"] == cond), key=lambda r: r["i"])
    return [{k: (math.nan if v is None else v) for k, v in r["systems"][sid].items()} for r in rs]  # JSON null = NaN


def b2(doc: dict) -> dict:
    P = list(M.PRIMARY_B)
    R = {c: per_run(doc, c) for c in {r["cond"] for r in doc["per_run"]}}
    sub = lambda a, b: [{m: x[m] - y[m] for m in P} for x, y in zip(a, b, strict=True)]  # noqa: E731
    D = {c: sub(R[c + "+"], R[c + "0"]) for c in ("LS", "FS", "LP", "FP")}
    Dn = sub(R["LS+~"], R["LS0~"])
    noise = {m: np.array([a[m] - b[m] for a, b in zip(Dn, D["LS"], strict=True)], float) for m in P}
    mean2 = lambda a, b: [{m: (x[m] + y[m]) / 2 for m in P} for x, y in zip(a, b, strict=True)]  # noqa: E731
    zero = [{m: 0.0 for m in P} for _ in D["LS"]]
    mine = {
        "dependence LS: B with A vs without A": statuses(R["LS+"], R["LS0"], P, None, 1),
        "communication effect on dependence (L vs F, averaged over resources)":
            statuses(mean2(D["LS"], D["LP"]), mean2(D["FS"], D["FP"]), P, noise, 2),
        "resource effect on dependence (S vs P, averaged over communication)":
            statuses(mean2(D["LS"], D["FS"]), mean2(D["LP"], D["FP"]), P, noise, 3),
        "residual dependence (F, P) vs zero": statuses(D["FP"], zero, P, noise, 4),
        "physical-only pathway: inert A (shared) vs no A": statuses(R["LSi"], R["LS0"], P, None, 5),
    }
    agree = {}
    for k, st in mine.items():
        pub = {m: doc["contrasts"][k][m]["status"] for m in P}
        pub2 = {m: ("DETECTED" if v == "DETECTED" else v if v in ("IDENTICAL", "NOT MEASURED") else "not detected")
                for m, v in pub.items()}
        agree[k] = {"independent": st, "published": pub, "agree": st == pub2}
    return agree


# ------------------------------------------------------------------ C1: queueing model of the shared gantry
def fifo_waits(legs: list[dict]) -> dict[int, int]:
    """legs: arrival, service, id; served in arrival order by one server; returns waiting time per leg id."""
    t_free, out = -1, {}
    for lg in sorted(legs, key=lambda x: (x["arrival"], x["id"])):
        start = max(lg["arrival"], t_free)
        out[lg["id"]] = start - lg["arrival"]
        t_free = start + lg["service"]
    return out


def c1(traces_with_a: list[list[dict]], waits_without_a: list[float]) -> dict:
    pred_with, pred_without = [], []
    for legs in traces_with_a:
        g0 = [{"arrival": lg["queued"], "service": lg["end"] - lg["start"], "id": k, "owner": lg["owner"]}
              for k, lg in enumerate(legs) if lg["gantry"] == "0" and lg["start"] is not None and lg["end"] is not None]
        w_all = fifo_waits(g0)
        w_b = fifo_waits([x for x in g0 if x["owner"] != "A"])
        b = [x["id"] for x in g0 if x["owner"] == "B"]
        if b:
            pred_with.append(float(np.mean([w_all[i] for i in b])))
            pred_without.append(float(np.mean([w_b[i] for i in b])))
    return {"model": "FIFO single server, recorded arrivals and service durations of bay-0 gantry legs",
            "B_wait_predicted_with_A": float(np.mean(pred_with)) if pred_with else None,
            "B_wait_predicted_A_legs_removed": float(np.mean(pred_without)) if pred_without else None,
            "B_wait_observed_without_A_runs": float(np.nanmean(waits_without_a)) if waits_without_a else None,
            "seeds_with_B_legs_on_bay0": len(pred_with)}


def main() -> None:
    pub_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    seeds = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    doc = json.loads(pub_path.read_text())
    out: dict = {"published": str(pub_path), "seeds_rerun": seeds, "B1_recount": [], "B2_statistics": b2(doc)}
    traces, waits0 = [], []
    for i in range(seeds):
        for cond in ("LS+", "LS0"):
            rec, legs = run_cond(cond, i)
            mine = recount(rec, "B")
            pubrow = next(r["systems"]["B"] for r in doc["per_run"] if r["cond"] == cond and r["i"] == i)
            same = all((math.isnan(mine[k]) and pubrow[k] is None) or (pubrow[k] is not None and abs(mine[k] - pubrow[k]) < 1e-9)
                       for k in mine)
            out["B1_recount"].append({"cond": cond, "i": i, "independent": mine,
                                      "published": {k: pubrow[k] for k in mine}, "agree": same})
            if cond == "LS+":
                traces.append(legs)
            else:
                w = [lg["start"] - lg["queued"] for lg in legs
                     if lg["owner"] == "B" and lg["gantry"] == "0" and lg["start"] is not None]
                waits0.append(float(np.mean(w)) if w else math.nan)
    out["C1_queue_model"] = c1(traces, waits0)
    out["summary"] = {"B1_all_agree": all(x["agree"] for x in out["B1_recount"]),
                      "B2_all_agree": all(v["agree"] for v in out["B2_statistics"].values())}
    out_path.write_text(json.dumps(out, indent=1, default=lambda o: None if isinstance(o, float) and math.isnan(o) else str(o)))
    print(json.dumps(out["summary"]), json.dumps(out["C1_queue_model"]))


if __name__ == "__main__":
    main()
