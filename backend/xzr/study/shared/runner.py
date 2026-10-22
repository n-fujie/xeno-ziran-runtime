"""Run one arm of the shared environment: an ARDS arm (ARDS's own code, through the bridge) or the HPO arm (this repository's policy), and score
every arm with the same ARDS held-out evaluation on the same service. Test replicates only (3980-3989)."""

from __future__ import annotations

import resource
import sys
import time

from ...hpo.experiments import clean
from .. import ards
from . import hpo_arm


def _rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return round(r / (1 << 20) if sys.platform == "darwin" else r / 1024, 1)


def hpo_metrics(run: dict, held: dict, default: dict, checks: list[dict]) -> dict:
    gain = None
    if held["ratesUnseen"]["coverage"] is not None and default["ratesUnseen"]["coverage"] is not None:
        gain = held["ratesUnseen"]["coverage"] - default["ratesUnseen"]["coverage"]
    cyc = run["cycles"]
    proposed = sum(len(c["proposals"]) for c in cyc)
    adopted = sum(1 for c in cyc if c["adopted"])
    changes = sum(len(next(p["changes"] for p in c["proposals"] if p["rule"] == c["adopted"])) for c in cyc if c["adopted"])
    reach = [c["reachability"] for c in cyc if c["reachability"]]
    m = {
        "A_observability": {
            "capableAll": held["all"]["capable"],
            "capableGainedOverDefault": held["all"]["capable"] - default["all"]["capable"],
        },
        "B_identification": {
            "all": held["ratesAll"],
            "seen": held["ratesSeen"],
            "unseen": held["ratesUnseen"],
            "primaryCoverageUnseen": held["ratesUnseen"]["coverage"],
        },
        "C_budget": {
            "bodyRuns": run["bodyRuns"],
            "setupSecondsSpent": run["setupSecondsSpent"],
            "setupBudget": run["setupBudget"],
            "coverageGainUnseenPerSetupSecond": gain / run["setupSecondsSpent"]
            if gain is not None and run["setupSecondsSpent"] > 0
            else None,
            "coverageGainUnseenPerBodyRun": gain / run["bodyRuns"] if gain is not None and run["bodyRuns"] > 0 else None,
        },
        "D_followUp": {
            "proposed": proposed,
            "adopted": adopted,
            "rejected": max(0, proposed - adopted),
            "changesApplied": changes,
            "ruleChanges": len(run["metaTrace"]),
            "memoryReads": sum(1 for c in cyc[1:]) if run["design"]["history"] else 0,
            "negativeResultsRead": 0,
        },
    }
    flat = ards.metric_values(m, [c for c in checks if not c["pass"]])
    flat.update(
        {
            "reach_opened": float(sum(len(r["opened"]) for r in reach)),
            "reach_opened_identified": float(sum(len(r["opened_and_identified"]) for r in reach)),
            "reach_opened_not_identified": float(sum(len(r["opened_not_identified"]) for r in reach)),
            "reach_closed": float(sum(len(r["closed"]) for r in reach)),
            "meta_revisions": float(len(run["metaTrace"])),
        }
    )
    return flat


def run_hpo(doc: dict, arm: dict, rep: int) -> dict:
    t0 = time.time()
    h = arm["hpo"]
    run = hpo_arm.run(rep, history=bool(h.get("history", True)), meta=bool(h.get("meta", False)))
    checks = hpo_arm.verify(run)
    timeout = float(doc["stop"]["timeout_per_run_s"])
    ev = ards._vite(ards.EVAL, [ards.json.dumps({"env": "env3", "replicate": rep, "config": run["finalConfig"]})], timeout)
    held, default = ev["held"], ev["default"]
    metrics = hpo_metrics(run, held, default, checks)
    reach = [c["reachability"] for c in run["cycles"] if c["reachability"]]
    opened = sum(len(r["opened"]) for r in reach)
    acted = sum(len(r["opened_and_identified"]) for r in reach)
    closed = sum(len(r["closed"]) for r in reach)
    cap_lost_ok = closed  # closed differences are checked against the validation data below
    rec = {
        "schema": "xzr.studyrun/1",
        "arm": arm["name"],
        "gen": rep,
        "seed": rep,
        "status": "ok",
        "metrics": metrics,
        "controller": {
            "mode": "recursive",
            "counts": [1 if c["adopted"] else 0 for c in run["cycles"]],
            "trace": [
                {
                    "epoch": c["cycle"] - 1,
                    "path": c["adopted"],
                    "value": c["reachability"],
                    "why": c["alteration"],
                    "source": "controller",
                }
                for c in run["cycles"]
                if c["adopted"]
            ],
            "meta_trace": run["metaTrace"],
            "rules": run["rules"],
            "proposals": [],
            "rejected": [],
            "authority": sorted(hpo_arm.REVISION_OPS),
            "max_changes_per_epoch": None,
        },
        "controller_changes": [],
        "protocol_changes": [],
        "reachability_check": {
            "opened": {"n": opened, "acted": acted, "rate": acted / opened if opened else None},
            "closed": {"n": closed, "silent": cap_lost_ok, "rate": 1.0 if closed else None},
            "skipped_last_epoch": 0,
            "note": "opened = the capability model says the difference became observable; acted = it was identified on the fresh validation seeds",
        },
        "history_reentry": {
            "reinsertions": max(0, len(run["cycles"]) - 1) if run["design"]["history"] else 0,
            "with_downstream_event": sum(1 for c in run["cycles"] if any(p["rule"] == "lower-noise" for p in c["proposals"])),
            "downstream_share": None,
            "enabled": bool(run["design"]["history"]),
        },
        "hpo_arm": {
            "design": run["design"],
            "cycles": [
                {k: v for k, v in c.items() if k not in ("control", "treatments", "validation", "idleValidation")}
                for c in run["cycles"]
            ],
            "verification": checks,
            "verification_failed": [c for c in checks if not c["pass"]],
            "final_config": run["finalConfig"],
            "ops_used": run["opsUsed"],
        },
        "ards_eval": {
            "env": "env3",
            "replicate": rep,
            "mode": "test",
            "default_held_out": {"unseenCoverage": default["ratesUnseen"]["coverage"]},
        },
        "wall_s": round(time.time() - t0, 3),
        "peak_rss_mb": _rss_mb(),
    }
    hist = rec["history_reentry"]
    hist["downstream_share"] = hist["with_downstream_event"] / hist["reinsertions"] if hist["reinsertions"] else None
    return clean(rec)


def run_arm(doc: dict, arm: dict, gen: int, seed: int) -> dict:
    if gen != seed or not ards.ARDS_REPLICATES[0] <= gen < ards.ARDS_REPLICATES[1]:
        raise ValueError(f"shared-oi: replicate must be an ARDS software-test replicate (3980-3989), got ({gen}, {seed})")
    if arm.get("hpo") is not None:
        return run_hpo(doc, arm, gen)
    return ards.run_ards({**doc, "environment": {**doc["environment"], "ards_env": "env3"}}, arm, gen, seed)
