"""What a study of the total-observation line reports about its runs: reasons, operations, reachability effects, questions, hypotheses, metric breaks, ontology audit.

Counts only; no interpretation. Differences between arms are the study's contrasts, not this summary.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from . import sss


def _mean(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(float(np.mean(xs)), 6) if xs else None


def arm_summary(rs: list[dict]) -> dict:
    gens = [g for r in rs for g in r["totalobs"]["generations"]]
    reasons = Counter(x for g in gens for x in g["trigger"]["reasons"])
    ops = Counter(f"{o['op']} [{o['status']}]" for g in gens for o in g["ops"])
    by_reason = Counter(o["reason"] for g in gens for o in g["ops"] if o["status"] == "executed")
    dyn = Counter(g["levels"]["dynamic_effect"] for g in gens)
    sta = Counter(g["levels"]["static_effect"] for g in gens)
    hyp = Counter((g["hypothesis_test"] or {}).get("outcome") for g in gens if g.get("hypothesis_test"))
    q = Counter(g["before"]["question"] for g in gens)
    rc = Counter(c["what"] for g in gens for c in g["changes"])
    integ = Counter(g["integration"]["effect"] for g in gens)
    audit = [r["totalobs"]["scope_audit"] for r in rs]
    breaks = [len(s) - 1 for r in rs for s in r["totalobs"]["metric_log"]["segments"].values() if len(s) > 1]
    disagree = []
    for r in rs:
        for g in r["totalobs"]["generations"]:
            h = g.get("hypothesis_test")
            if h and h.get("outcome") in ("supported", "refuted") and h.get("true_speed"):
                est = h["D"] / max(h["lag"], 1)
                disagree.append(abs(est - h["true_speed"]) / h["true_speed"])
    sup = [h for g in gens if (h := g.get("hypothesis_test")) and h.get("outcome") == "supported" and h.get("true_speed")]
    v2 = {}
    if all(r["totalobs"].get("rules_version") == "v2" for r in rs):
        cross: Counter = Counter()
        for g in gens:
            h = g.get("hypothesis_test")
            if h and h.get("observational_support"):
                cross[f"{h['observational_support']} / model {h['model_agreement']}"] += 1
        conf = Counter(f"{a['agent_state']} | true cause {a['true_cause']}" for r in rs for a in r["totalobs"]["silence_audit"])
        confl = [c for r in rs for c in r["totalobs"]["conflicts"]]
        attrib = Counter(
            f"{e['attribution']} | true causes seen {','.join(e['true_causes_seen_for_this_sensor']) or '-'}" for r in rs for e in r["totalobs"]["silence_log"]
        )
        v2 = {
            "rules_version": "v2",
            "freshness": rs[0]["totalobs"]["freshness"],
            "hypothesis_support_vs_model": dict(sorted(cross.items())),
            "hypothesis_status_after_test": dict(Counter(g["hypothesis_test"].get("status_after") for g in gens if g.get("hypothesis_test") and g["hypothesis_test"].get("status_after"))),
            "silence_states_vs_true_causes": dict(sorted(conf.items())),
            "probe_attributions": dict(sorted(attrib.items())),
            "rule_conflicts": {
                "events": len(confl),
                "resolutions": dict(Counter(c["resolution"].split(" ")[0] for c in confl)),
                "infeasible_or_not_retried": sum(1 for c in confl if c["resolution"] == "infeasible" or c.get("note")),
                "scale_reversals": sum(r["metrics"].get("scale_reversals", 0) or 0 for r in rs),
                "cooldown_suppressions": sum(r["metrics"].get("cooldown_suppressions", 0) or 0 for r in rs),
            },
            "identification_lost": {
                "object_still_present_in_the_world": sum(r["metrics"].get("ident_lost_object_still_present", 0) or 0 for r in rs),
                "object_absent": sum(r["metrics"].get("ident_lost_object_absent", 0) or 0 for r in rs),
                "note": "a lost identification is not a vanished object: the verifier says which",
            },
        }
    return {
        **v2,
        "runs": len(rs),
        "generations": len(gens),
        "reasons": dict(sorted(reasons.items())),
        "operations": dict(sorted(ops.items())),
        "executed_by_reason": dict(sorted(by_reason.items())),
        "reachability": {
            "static": dict(sta),
            "dynamic": dict(dyn),
            "note": "static = right after the change against the state before it; dynamic = after the generation (includes the world's own change)",
        },
        "questions": dict(q),
        "condition_changes": dict(rc),
        "hypothesis_tests": {k or "none": v for k, v in hyp.items()},
        "supported_but_off_by_more_than_50pct_from_the_verifier": sum(
            1 for h in sup if abs(h["D"] / max(h["lag"], 1) - h["true_speed"]) / h["true_speed"] > 0.5
        ),
        "estimate_vs_verifier_relative_error_mean": _mean(disagree),
        "integration": dict(integ),
        "meta_trace_entries": sum(len(r["totalobs"]["meta_trace"]) for r in rs),
        "final_rules": [r["totalobs"]["rules"] for r in rs][:3],
        "suppressed_decisions": sum(len(r["totalobs"]["suppressed"]) for r in rs),
        "stopped": dict(
            Counter((r["totalobs"]["stopped"] or {}).get("reason", "").split(":")[0] or "ran to the end" for r in rs)
        ),
        "metric_definition_breaks": {
            "series_with_a_break": len(breaks),
            "total_breaks": sum(breaks),
            "note": "numbers on the two sides of a break were measured under different definitions and are not compared",
        },
        "ontology_audit": {"runs_with_issues": sum(1 for a in audit if a), "issues": sorted({i for a in audit for i in a})},
        "memory": {
            "reads": sum(r["totalobs"]["memory"]["reads"] for r in rs),
            "hits": sum(r["totalobs"]["memory"]["hits"] for r in rs),
        },
    }


def sss_effects(doc: dict, by_arm: dict[str, float | None]) -> dict | None:
    """Main effects and interaction contrasts of the SSS axes, from the arms' means, when the arms are a full 2^k design tagged ``sss``."""
    tagged = {a["name"]: a["sss"] for a in doc["arms"] if a.get("sss")}
    if not tagged:
        return None
    axes = tuple(a for a in sss.AXES if any(a in t for t in tagged.values()))
    cells: dict[tuple, float | None] = {}
    for name, t in tagged.items():
        cells[tuple(t.get(a, "low") for a in axes)] = by_arm.get(name)
    full = 2 ** len(axes)
    if len(cells) != full:
        return {"axes": list(axes), "complete": False, "note": f"{len(cells)} of {full} cells present: no effects computed"}
    out = sss.effects(axes, cells)
    out["complete"] = True
    out["note"] = (
        "effects of the primary metric on arm means (high - low); the three axes are changed through the declared parameters only; a metric whose "
        "definition depends on the changed axis is compared only if sss.comparable() allows it"
    )
    return out


def study_summary(doc: dict, runs: list[dict], arms: list[str], means: dict[str, float | None]) -> dict[str, Any]:
    out: dict[str, Any] = {"arms": {}}
    for a in arms:
        rs = [r for r in runs if r["arm"] == a and r["status"] == "ok" and r.get("totalobs")]
        if rs:
            out["arms"][a] = arm_summary(rs)
    first = next((r for r in runs if r["status"] == "ok" and r.get("totalobs")), None)
    if first:
        out["planetary"] = {
            a: next(
                (r["totalobs"]["planetary"] for r in runs if r["arm"] == a and r["status"] == "ok" and r.get("totalobs")), None
            )
            for a in arms
        }
        out["planetary_note"] = first["totalobs"]["planetary"]["note"]
        out["metric_registry"] = first["totalobs"]["metric_log"]["registry"]
    out["sss"] = sss_effects(doc, means)
    out["scope"] = (
        "A synthetic world, a finite model: its state is not reality as a whole, what the agent identifies is a construction of its observing "
        "configuration, and nothing here is a statement about the Earth or about any theory."
    )
    return out
