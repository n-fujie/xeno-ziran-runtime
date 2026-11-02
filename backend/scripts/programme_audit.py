"""Pre-execution audit of the four research-programme protocols: does each validate, pass the fairness check, run to completion on the reserved functional seeds
(one seed, every arm: a software check, not an experiment), and is every metric a programme asks for actually produced by the runs? A requested metric that no run
produces is reported as MISSING, and a metric that exists only as a ratio of two stored metrics as DERIVED; neither is replaced by a stand-in.
Runs in a temporary directory; no study is kept."""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

from xzr.study import protocol as P
from xzr.study import runner, templates

# programme -> requested metric (as the programme text names it) -> stored metrics that carry it ("derived:" = a ratio of stored metrics, not analysed as such)
REQUESTED = {
    "rp1-ziran-self-revision": {
        "executable operations": ["reachable_share"],
        "reachable states": ["reachable_share"],
        "research completion rate": ["stopped_early", "ceased_share"],
        "identifiability": ["fired_samples", "unobservable_samples"],
        "research resource use": ["measure_cost"],
        "change failure rate": ["derived:controller_rejected / (controller_changes + controller_rejected)"],
        "later research conditions": ["controller_changes", "reinsertions", "meta_revisions"],
    },
    "rp2-total-observation": {
        "identifiability": ["recall_final", "precision_mean", "identification_count_error"],
        "loss of observational information": ["observation_loss_share", "records_lost", "ident_lost_object_still_present"],
        "disturbance by observation": ["interference", "marks_total"],
        "later reachability": ["reachable_regions_final", "reach_expanded", "reach_contracted"],
        "change of observing conditions": ["ops_executed", "eval_changes", "metric_definition_breaks"],
        "state after record loss": ["marks_total", "ident_lost_object_still_present"],
    },
    "rp3-planetary-placement": {
        "observed extent": ["coverage_final", "reachable_regions_final"],
        "identification error": ["identification_count_error", "precision_mean", "spurious_rate"],
        "communication delay": ["info_age_mean"],
        "observer expiry rate": ["expiry_rate"],
        "resource cost": ["obs_cost", "ops_cost_spent"],
        "tracking of wide-area change": ["recall_post_change"],
    },
    "rp4-sss-self-revision": {
        "identification ability": ["recall_final"],
        "tracking": ["recall_post_change"],
        "comparability": ["metric_definition_breaks"],
        "state transitions": ["question_changes", "reach_expanded", "reach_contracted"],
        "resource use": ["obs_cost", "ops_cost_spent"],
        "later research": ["cycles_completed", "ops_executed"],
    },
}


def audit_one(name: str) -> dict:
    d = templates.template(name, n_seeds=1)
    row = {
        "programme": name,
        "arms": len(d["arms"]),
        "contrasts": len(d["contrasts"]),
        "mode": d["mode"],
        "validation_issues": P.validate(d),
        "fairness_issues": P.fairness_issues(d),
        "step_runs_with_6_seeds": P.step_runs(templates.template(name, n_seeds=6)),
    }
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        st = runner.Study.create(d, Path(tmp))
        st.execute(procs=2)
        runs = st.runs()
    row["smoke_runs"] = {
        "ok": sum(r["status"] == "ok" for r in runs),
        "failed": sum(r["status"] != "ok" for r in runs),
        "seconds": round(time.time() - t0, 1),
    }
    metrics = [r["metrics"] for r in runs if r["status"] == "ok"]
    declared = set(d["metrics"]["primary"]) | set(d["metrics"].get("secondary", []))
    row["declared_metrics_never_defined"] = sorted(m for m in declared if not any(x.get(m) is not None for x in metrics))
    cov = {}
    for ask, stored in REQUESTED[name].items():
        parts = []
        for s in stored:
            if s.startswith("derived:"):
                comps = ["controller_rejected", "controller_changes"]
                parts.append(
                    {
                        "metric": s,
                        "status": "DERIVED" if all(any(x.get(c) is not None for x in metrics) for c in comps) else "MISSING",
                    }
                )
            else:
                parts.append(
                    {
                        "metric": s,
                        "status": "measured"
                        if any(x.get(s) is not None for x in metrics)
                        else "MISSING (declared but undefined in the smoke runs)",
                    }
                )
        cov[ask] = parts
    row["requested_metrics"] = cov
    row["ready_to_register"] = (
        not row["validation_issues"]
        and not row["fairness_issues"]
        and row["smoke_runs"]["failed"] == 0
        and not any(p["status"].startswith("MISSING") for v in cov.values() for p in v)
    )
    return row


if __name__ == "__main__":
    res = [audit_one(n) for n in REQUESTED]
    Path(sys.argv[1]).write_text(json.dumps(res, indent=1))
    for r in res:
        gaps = [f"{k}: {p['metric']}" for k, v in r["requested_metrics"].items() for p in v if p["status"] != "measured"]
        print(
            f"{r['programme']:28s} arms {r['arms']:2d} contrasts {r['contrasts']:2d} smoke ok {r['smoke_runs']['ok']}/{r['smoke_runs']['ok'] + r['smoke_runs']['failed']} "
            f"validation {len(r['validation_issues'])} fairness {len(r['fairness_issues'])} ready {r['ready_to_register']}"
        )
        for g in gaps:
            print("     not measured directly:", g)
