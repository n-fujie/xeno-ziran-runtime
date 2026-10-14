"""EXPLORATORY sensitivity analysis (not part of the frozen M9 protocol): B's transfer latency under two definitions.

    physical completion latency   request -> the last leg's release of the sample in the target chamber
                                  (what the frozen harness measured: every `transfer_complete` of the system)
    delivered latency             request -> successful delivery (the runtime accepted the material: a
                                  `material_delivered` event; deliveries blocked at a closed containment are excluded)

The frozen primary analysis (results/lab9/m9ab.json) is not changed. This script re-executes the M9-A/B conditions on
the confirmatory seeds (each re-run is checked against the published run fingerprint), records both latencies and
every blocked delivery with its cause, and recomputes the M9-A/B latency contrasts with the delivered definition
using the same statistics as the frozen analysis.

Usage: cd backend && PYTHONPATH=. python scripts/m9_latency_sensitivity.py <published m9ab.json> <out.json> [procs]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CONDS = ("LS+", "LS0", "FS+", "FS0", "LP+", "LP0", "FP+", "FP0", "LS+~", "LS0~", "LSi", "G+", "W+", "M+", "M0")


def one(args: tuple) -> dict:
    from xzr.lab import m9
    from xzr.lab.record import LabRun
    cond, i = args
    gen0, seed0 = m9.RANGES["confirm"]
    r = LabRun(m9.config(m9.EXPERIMENTS["m9ab"][cond], gen0 + i, seed0 + i))
    while not r.done:
        r.step()
    sci = r.science
    assert sci is not None
    owner = {tid: exp["system"] for tid, exp in sci.transfers.items()}
    complete = {e["transfer"]: e for e in r.physical if e["type"] == "transfer_complete"}
    phys, deliv, blocked = [], [], []
    iso = [(e["t"], e["until"], e["system"], e["chamber"]) for e in sci.events if e["type"] == "isolation"]
    harness = [e for e in sci.events if e["type"] == "harness"]
    for tid, e in complete.items():
        if owner.get(tid) != "B":
            continue
        lat = e["t"] - e["requested_at"]
        phys.append(lat)
        ok = any(d["type"] == "material_delivered" and d["system"] == "B" and d["t"] == e["t"] and d["dst"] == e["dst"]
                 for d in sci.events)
        if ok:
            deliv.append(lat)
        else:
            by = sorted({s for t0, t1, s, c in iso if c == e["dst"] and t0 <= e["t"] < t1})
            blocked.append({"transfer": tid, "t": e["t"], "src": e["src"], "dst": e["dst"], "latency": lat,
                            "closed_by_isolation_of": by, "harness": bool(harness)})
    return {"cond": cond, "i": i, "fingerprint": r.w.engine.fingerprint(),
            "physical_latency_mean": float(np.mean(phys)) if phys else math.nan,
            "delivered_latency_mean": float(np.mean(deliv)) if deliv else math.nan,
            "physical_n": len(phys), "delivered_n": len(deliv), "blocked": blocked}


def main() -> None:
    from xzr.hpo.experiments import run_pool
    from xzr.lab import m9
    pub = json.loads(Path(sys.argv[1]).read_text())
    out_path = Path(sys.argv[2])
    procs = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    runs = run_pool(one, [(c, i) for c in CONDS for i in range(pub["seeds"])], procs)
    for x in runs:  # the re-run is the published run
        x["fingerprint_matches_published"] = x["fingerprint"] == pub["fingerprints"][f"{x['cond']}/confirm/{x['i']}"]
        prow = next(p for p in pub["per_run"] if p["cond"] == x["cond"] and p["i"] == x["i"])["systems"]["B"]
        pl = prow.get("latency_mean")
        x["published_latency_mean"] = pl
        x["harness_equals_physical_definition"] = (pl is None and math.isnan(x["physical_latency_mean"])) or (
            pl is not None and abs(pl - x["physical_latency_mean"]) < 1e-9)
    R = {c: sorted((x for x in runs if x["cond"] == c), key=lambda x: x["i"]) for c in CONDS}

    def rows(c: str, key: str) -> list[dict]:
        return [{"latency": x[key]} for x in R[c]]

    def diff(a, b):
        return [{"latency": x["latency"] - y["latency"]} for x, y in zip(a, b, strict=True)]

    def avg(a, b):
        return [{"latency": (x["latency"] + y["latency"]) / 2} for x, y in zip(a, b, strict=True)]

    out: dict = {"exploratory": True, "definitions": __doc__.split("Usage")[0].strip(), "runs": len(runs),
                 "all_fingerprints_match_published": all(x["fingerprint_matches_published"] for x in runs),
                 "harness_metric_is_physical_completion_latency": all(x["harness_equals_physical_definition"] for x in runs),
                 "contrasts": {}}
    for key, label in (("physical_latency_mean", "physical"), ("delivered_latency_mean", "delivered")):
        D = {cell: diff(rows(f"{cell}+", key), rows(f"{cell}0", key)) for cell in ("LS", "FS", "LP", "FP")}
        Dn = diff(rows("LS+~", key), rows("LS0~", key))
        nf = {"latency": np.array([a["latency"] - b["latency"] for a, b in zip(Dn, D["LS"], strict=True)], float)}
        zero = [{"latency": 0.0} for _ in D["LS"]]
        cs = {"dependence LS": m9.contrast(rows("LS+", key), rows("LS0", key), ["latency"], None, 9000),
              "dependence FP": m9.contrast(rows("FP+", key), rows("FP0", key), ["latency"], None, 9003),
              "communication effect on dependence": m9.contrast(avg(D["LS"], D["LP"]), avg(D["FS"], D["FP"]),
                                                                ["latency"], nf, 9004),
              "resource effect on dependence": m9.contrast(avg(D["LS"], D["FS"]), avg(D["LP"], D["FP"]), ["latency"], nf,
                                                           9005),
              "residual dependence (F, P) vs zero": m9.contrast(D["FP"], zero, ["latency"], nf, 9007),
              "physical-only pathway": m9.contrast(rows("LSi", key), rows("LS0", key), ["latency"], None, 9008)}
        for r, ref in (("G+", "LS0"), ("W+", "LS0"), ("M+", "M0")):
            cs[f"mediation {r[0]}"] = m9.contrast(D["LS"], diff(rows(r, key), rows(ref, key)), ["latency"], nf, 9100)
        out["contrasts"][label] = {k: {f: v["latency"].get(f) for f in ("status", "mean", "relative", "ci95", "p_holm", "n",
                                                                         "mean_x", "mean_y")} for k, v in cs.items()}
    out["discrepant_runs"] = [{k: x[k] for k in ("cond", "i", "physical_latency_mean", "delivered_latency_mean",
                                                  "physical_n", "delivered_n", "blocked")}
                              for x in runs if x["physical_n"] != x["delivered_n"]]
    out["blocked_by_cause"] = {}
    for x in runs:
        for b in x["blocked"]:
            k = "B's own isolation" if b["closed_by_isolation_of"] == ["B"] else (
                "another system's isolation" if b["closed_by_isolation_of"] else "other closure (harness or turnover)")
            out["blocked_by_cause"][k] = out["blocked_by_cause"].get(k, 0) + 1
    out["runs_detail"] = runs
    from xzr.hpo.experiments import clean
    out_path.write_text(json.dumps(clean(out), indent=1, allow_nan=False))
    print(json.dumps({k: out[k] for k in ("runs", "all_fingerprints_match_published",
                                          "harness_metric_is_physical_completion_latency", "blocked_by_cause")}))
    for label, cs in out["contrasts"].items():
        print(label, {k: (v["status"], round(v["mean"], 2) if v["mean"] is not None else None) for k, v in cs.items()})


if __name__ == "__main__":
    main()
