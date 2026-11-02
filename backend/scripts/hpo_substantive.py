"""Post-hoc descriptive analysis of substantive operational differences in HPO-002 (NOT pre-registered).

    python backend/scripts/hpo_substantive.py [--seeds 48] [--procs 7]

Re-runs, deterministically, the first ``--seeds`` confirmatory HPO-002 seeds (same seeds, settings and code as the
confirmatory run) with full state recording, and answers descriptively, from the causal history rather than from
event counts alone:

    Q1 which ignition conditions changed           transformations by (target kind, parameter), relative change
    Q2 which series caused them                    transformations by source kind (rule) → target kind
    Q3 which operations became possible/impossible per kind: ignited in X but not in B (enabled), in B but not in X
    Q4 which changes persisted                     transformed parameters still ≠ initial at the end of the run
    Q5 which disappeared after removing the source E:k vs C: transformations sourced by k after the removal step,
                                                   and other operations' parameter drift at the end
    Q6 which historical differences re-entered     reinsertions by kind and the share that caused a later event
    Q7 did the operational configuration change    couplings, splits, composite kinds, reclassifications
    Q9 what stayed unobserved                      unobservable channel-samples by reason and kind

(Q8 is HPO-003; Q10 is assembled from the verdicts in hpo_report.py.) Writes
backend/experiments/results/hpo/substantive.json. Reproducibility: the re-run of seed 0, condition D, must reproduce the
causal-history summary stored in hpo002.json (``trace.summary``).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from xzr.hpo import experiments as X  # noqa: E402
from xzr.hpo.registry import KINDS  # noqa: E402

CONDS = ["B", "C", "D", *[f"E:{k}" for k in KINDS], *[f"F:{k}" for k in KINDS]]


def kinds_of(f, oid: str) -> tuple[str, ...]:
    o = f.ops.get(oid)
    return o.kinds if o is not None else ()


def describe(f) -> dict:
    evs = f.history.events
    t0 = f.t0
    q1: dict[str, list[float]] = {}
    q2: dict[str, int] = {}
    src_after: dict[str, int] = dict.fromkeys(KINDS, 0)
    for e in evs:
        if e["type"] != "transform":
            continue
        rule = e.get("detail", {}).get("rule", "")
        sk = rule.split(":")[0] if ":" in rule else rule
        q2[f"{sk} → {'∘'.join(kinds_of(f, e['target']))}"] = q2.get(f"{sk} → {'∘'.join(kinds_of(f, e['target']))}", 0) + 1
        if sk in src_after and e["t"] - t0 > X.CEASE_AT:
            src_after[sk] += 1
        b, a = e.get("before") or {}, e.get("after") or {}
        for sect in ("ign", "rule"):
            for k, d in (a.get(sect) or {}).items():
                for p, v in d.items():
                    v0 = (b.get(sect) or {}).get(k, {}).get(p)
                    if v0 not in (None, 0) and v != v0:
                        q1.setdefault(f"{k}.{sect}.{p}", []).append((v - v0) / abs(v0))
        if (a.get("instrument") or {}).get("level") != (b.get("instrument") or {}).get("level"):
            q1.setdefault(f"{'∘'.join(kinds_of(f, e['target']))}.instrument.level", []).append(1.0)
    persisted = total = 0
    for o in f.live():
        init = o.mem.get("_init") or {}
        for sect in ("ign", "rule"):
            for k, d in getattr(o, sect).items():
                for p, v in d.items():
                    v0 = init.get(sect, {}).get(k, {}).get(p)
                    if v0 is None:
                        continue
                    total += 1
                    persisted += int(abs(v - v0) > 1e-12)
    fired = {k: k in f.stats["first_ignition"] for k in KINDS}
    rein = [e for e in evs if e["type"] == "reinsert"]
    caused = {c for e in evs for c in e["causes"]}
    rein_kinds: dict[str, list[int]] = {}
    for e in rein:
        what = (e.get("detail") or {}).get("what", "?")
        rein_kinds.setdefault(what, []).append(int(e["id"] in caused))
    comps = sorted({o.label for o in f.ops.values() if len(o.kinds) > 1})
    unobs = {}
    for lab, per in f.stats["unobservable_by_kind"].items():
        for k in lab.split("∘"):
            for r, n in per.items():
                unobs.setdefault(k, {}).setdefault(r, 0)
                unobs[k][r] += n
    drift = f.drift()
    return {"q1": {k: [len(v), float(np.mean(v))] for k, v in q1.items()}, "q2": q2,
            "transforms_by_source_after_removal_step": src_after, "persisted": [persisted, total], "fired": fired,
            "reinsert": {k: [len(v), sum(v)] for k, v in rein_kinds.items()},
            "composites": comps, "couplings": sum(e["type"] == "couple" for e in evs),
            "splits": sum(e["type"] == "split" for e in evs), "reclass": sum(e["type"] == "reclassify" for e in evs),
            "unobs": unobs, "drift": drift, "drift_mean": float(np.mean(list(drift.values()))) if drift else 0.0,
            "summary": f.history.summary()}


def job(i: int) -> dict:
    gen0, seed0 = X.RANGES["hpo002"]
    gen, seed = gen0 + i, seed0 + i
    base = X._warm(X.WORLD, gen, seed, X.WARMUP)
    _, r0w, _ = X.run_one(base, None, seed, None)
    out = {}
    for c in CONDS:
        _, _, f = X.run_one(base, X.settings_for(c), seed, r0w, keep_states=True)
        out[c] = describe(f)
    return out


def aggregate(jobs: list[dict]) -> dict:
    res: dict = {}
    n = len(jobs)
    for c in CONDS:
        rows = [j[c] for j in jobs]
        q1: dict[str, list] = {}
        for r in rows:
            for k, (cnt, mean) in r["q1"].items():
                q1.setdefault(k, []).append((cnt, mean))
        q2: dict[str, int] = {}
        for r in rows:
            for k, v in r["q2"].items():
                q2[k] = q2.get(k, 0) + v
        rein: dict[str, list[int]] = {}
        for r in rows:
            for k, (a, b) in r["reinsert"].items():
                x = rein.setdefault(k, [0, 0])
                x[0] += a
                x[1] += b
        unobs: dict[str, dict[str, float]] = {}
        for r in rows:
            for k, per in r["unobs"].items():
                for reason, v in per.items():
                    unobs.setdefault(k, {}).setdefault(reason, 0.0)
                    unobs[k][reason] += v / n
        comp: dict[str, int] = {}
        for r in rows:
            for lab in r["composites"]:
                comp[lab] = comp.get(lab, 0) + 1
        res[c] = {
            "Q1_changed_ignition_conditions": {k: {"runs": len(v), "per_run": sum(a for a, _ in v) / n,
                                                   "mean_relative_change": float(np.mean([m for _, m in v]))}
                                               for k, v in sorted(q1.items(), key=lambda kv: -len(kv[1]))},
            "Q2_causing_series": {k: v / n for k, v in sorted(q2.items(), key=lambda kv: -kv[1])},
            "Q3_ignited_share": {k: float(np.mean([r["fired"][k] for r in rows])) for k in KINDS},
            "Q4_parameters_persisting_changed": float(sum(r["persisted"][0] for r in rows)
                                                      / max(1, sum(r["persisted"][1] for r in rows))),
            "Q5_transforms_by_source_after_step_80": {k: float(np.mean([r["transforms_by_source_after_removal_step"][k]
                                                                         for r in rows])) for k in KINDS},
            "Q5_parameter_drift_mean": float(np.mean([r["drift_mean"] for r in rows])),
            "Q6_reinsertions": {k: {"per_run": a / n, "share_causing_a_later_event": b / a if a else None}
                                for k, (a, b) in rein.items()},
            "Q7_configuration": {"couplings_per_run": float(np.mean([r["couplings"] for r in rows])),
                                 "splits_per_run": float(np.mean([r["splits"] for r in rows])),
                                 "reclassifications_per_run": float(np.mean([r["reclass"] for r in rows])),
                                 "composite_kinds_seen_in_runs": comp},
            "Q9_unobservable_channel_samples_per_run": unobs,
        }
    # Q3 relative to B: per kind, share of seeds where the kind ignited in C but not in B (enabled) and vice versa
    res["Q3_C_vs_B"] = {k: {"enabled_share": float(np.mean([j["C"]["fired"][k] and not j["B"]["fired"][k] for j in jobs])),
                            "disabled_share": float(np.mean([j["B"]["fired"][k] and not j["C"]["fired"][k] for j in jobs]))}
                        for k in KINDS}
    res["Q5_removal"] = {k: {"transforms_by_k_after_step_80_C": res["C"]["Q5_transforms_by_source_after_step_80"][k],
                             "transforms_by_k_after_step_80_E": res[f"E:{k}"]["Q5_transforms_by_source_after_step_80"][k],
                             "drift_C": res["C"]["Q5_parameter_drift_mean"],
                             "drift_E": res[f"E:{k}"]["Q5_parameter_drift_mean"],
                             "ignited_share_E": res[f"E:{k}"]["Q3_ignited_share"][k]} for k in KINDS}
    return res


def main() -> None:
    seeds = int(sys.argv[sys.argv.index("--seeds") + 1]) if "--seeds" in sys.argv else 48
    procs = int(sys.argv[sys.argv.index("--procs") + 1]) if "--procs" in sys.argv else 7
    t = time.time()
    jobs = X.run_pool(job, list(range(seeds)), procs)
    stored = json.loads((X.RESULTS / "hpo002.json").read_text())["trace"]["summary"]
    rerun = jobs[0]["D"]["summary"]
    doc = {"status": "post-hoc descriptive analysis (not pre-registered; no hypothesis is tested here)",
           "seeds": seeds, "seed_ranges": {"generator": X.RANGES["hpo002"][0], "engine": X.RANGES["hpo002"][1]},
           "conditions": CONDS, "results": aggregate(jobs),
           "reproduces_confirmatory_trace": json.loads(json.dumps(rerun)) == stored,
           "elapsed_s": round(time.time() - t, 1), "protocol_sha256": X.protocol_hash()}
    X.write("substantive", doc)
    print("reproduces confirmatory seed-0 trace:", doc["reproduces_confirmatory_trace"], f"({doc['elapsed_s']} s)")


if __name__ == "__main__":
    main()
