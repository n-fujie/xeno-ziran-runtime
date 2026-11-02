"""Audit of confirmatory protocol drafts against the sixteen items a confirmatory study must fix before its first run. Reads the drafts; changes nothing,
creates no study, starts no run, and does not touch any approval gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from xzr.study import protocol as P
from xzr.study import runner, templates

ROOT = Path(__file__).resolve().parents[2]


def audit(name: str, d: dict) -> dict:
    pr = d.get("preregistration") or {}
    pw = pr.get("power") or {}
    ap = pr.get("analysis_plan") or {}
    seeds = P.seed_list(d)
    expl = {tuple(x) for x in (pr.get("separation") or {}).get("exploratory_seeds", [])}
    issues = P.validate(d)
    plan = d.get("planning") or {}
    need = plan.get("pairs_needed_for_80pct_power") or plan.get("pairs_needed_for_80pct_power_at_alpha_0.025") or {}
    rows = {
        "1 main hypothesis": bool(pr.get("central_hypothesis")),
        "2 falsification conditions": bool(pr.get("falsification")),
        "3 arms (described)": all(a.get("description") for a in d["arms"]) and len(d["arms"]) >= 2,
        "4 fairness (no undeclared difference)": P.fairness_issues(d) == [],
        "5 independent seeds (fresh, validated)": not any("seed" in i for i in issues),
        "6 number of trials": f"{len(seeds)} seeds per arm",
        "7 power (assumptions and source; every contrast powered or declared underpowered)": bool(
            pw.get("source") and pw.get("assumed_sd") and pw.get("min_effect")
        )
        and all(v <= len(seeds) or k in plan.get("underpowered", []) for k, v in need.items()),
        "7b contrasts declared underpowered (reported with intervals only)": plan.get("underpowered", []),
        "8 metrics (primary / secondary)": bool(d["metrics"].get("primary")),
        "9 analysis plan": bool(ap.get("primary") and ap.get("estimation") and ap.get("sensitivity")),
        "10 multiplicity correction": ap.get("multiplicity") in ("Holm", "Benjamini-Hochberg"),
        "11 stopping rules": bool(pr.get("stopping_rules")) and bool(d.get("stop")),
        "12 computational budget": f"{P.step_runs(d)} step-runs; gate {P.HIGH_COST_STEP_RUNS}; budget {d.get('budget')}",
        "13 storage format": bool(pr.get("data_storage")),
        "14 reproduction procedure": hasattr(runner, "reproduce") and hasattr(runner, "replay_run"),
        "15 exploration / confirmation separated": bool(expl) and not (expl & {tuple(s) for s in seeds}),
        "16 change management after registration": callable(P.amend),
        "17 minimum effect sizes declared": bool(pw.get("min_effect")),
        "18 known incomparabilities declared in the protocol": bool(pr.get("known_incomparabilities")),
        "19 design changes after exploration recorded (provenance 'exploration')": any(
            p_.get("derived_from") == "exploration" for p_ in pr.get("condition_provenance", [])
        ),
    }
    return {
        "draft": name,
        "mode": d["mode"],
        "status": d.get("status"),
        "frozen": bool(d.get("freeze")),
        "items": rows,
        "open_issues_that_block_creation": issues,
        "approvals_granted": {k: bool(v) for k, v in (d.get("approval") or {}).items() if k != "note"},
    }


if __name__ == "__main__":
    l2 = json.loads((ROOT / "docs/level2/PROTOCOL_L2_DRAFT.json").read_text())
    out = [
        audit("docs/level2/PROTOCOL_L2_DRAFT.json (HPO)", l2),
        audit("template total-observation-confirmatory", templates.template("total-observation-confirmatory")),
    ]
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
    for a in out:
        print(a["draft"], "| frozen:", a["frozen"], "| approvals:", a["approvals_granted"])
        for k, v in a["items"].items():
            print("  ", "OK  " if v is True else ("--  " if v is False else "    "), k, "" if v is True or v is False else v)
        print("   blocking:", a["open_issues_that_block_creation"])
