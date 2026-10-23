"""Operational non-redundancy: what a comparison can and cannot say about whether a method does something its fairly equipped alternatives do not.

The existence of a revision mechanism is not a finding. For every evaluation axis this module lists the indicators that exist in a study's records, which
arms they are defined for, whether they are *comparable* across the arms, the declared contrasts that bear on it and their classification, and the regions
no arm of this environment can evaluate. The verdict is a rule, written here, and defaults to "not established":

    established   a declared contrast on a comparable indicator is DETECTED in an independent confirmatory study (never in a functional or exploratory one),
                  between a method with the P/A-labelled operation and an alternative given the same information, authority and budget
    equivalent    the interval of such a contrast lies inside the equivalence margin on every comparable axis measured
    not evaluated the study is functional or exploratory, or no comparable indicator was measured

A method that merely has revision, reachability records or meta-revision is not thereby non-redundant: the control arms (history off, revision off, random
matched, ARDS's own arms) exist to find out.
"""

from __future__ import annotations

AXES = {
    "prediction": {
        "indicators": ["E_hypotheses (hypotheses, verifiable, falsifiable, supported, refuted) of ARDS arms"],
        "comparable": False,
        "reason": "only ARDS arms state hypotheses with predicates; the HPO arm and the HPO-world controller make no predictions, so no cross-family comparison exists",
    },
    "intervention": {
        "indicators": ["interventions / experiment selection (alteration chosen), protocol interventions"],
        "comparable": False,
        "reason": "arm-internal: the HPO arm with select chooses alterations, ARDS arms follow a fixed or permuted order; comparable only inside a family",
    },
    "reachability": {
        "indicators": [
            "capable_gained (held-out differences observable over the default configuration)",
            "reach_opened, reach_opened_identified (HPO records)",
        ],
        "comparable": True,
        "reason": "capable_gained is defined for every arm by the same ARDS evaluation; the opened / identified records exist only for the HPO arm",
    },
    "observability": {
        "indicators": ["all_coverage, seen_coverage, unseen_coverage, unseen_fdr (ARDS held-out evaluation)"],
        "comparable": True,
        "reason": "one evaluation (ARDS's own code) on one service for every arm; the primary outcome is unseen_coverage",
    },
    "action on reality": {
        "indicators": [],
        "comparable": False,
        "reason": "every effect is internal to the simulation (no physical or institutional effect): this axis cannot be evaluated here by any arm",
    },
    "temporal continuity": {
        "indicators": [
            "stopped_early, stop_step, ceased_share (HPO world, long horizons)",
            "three cycles per replicate (shared environment)",
        ],
        "comparable": False,
        "reason": "the shared environment runs three cycles: continuation beyond that horizon is not measured; the HPO-world runs have their own horizon",
    },
    "reorganisation of later structure": {
        "indicators": [
            "adopted, changes_applied (ARDS and HPO arms)",
            "controller_changes, meta_revisions, meta_exhausted (HPO world)",
        ],
        "comparable": False,
        "reason": "counts of changes are defined for both families but mean different things (ARDS adoption vs HPO rule changes); reported side by side, not ranked",
    },
}
NOT_EVALUABLE = [
    "differences outside the catalog (the environment defines what exists)",
    "alterations other than the four defined (the generalisation beyond them is untested)",
    "variable generation and boundary change as shared operations (not available in the shared environment; evaluated separately in the HPO world)",
    "human-readability and human-energy independence (nothing here bears on them)",
    "any effect outside the simulation",
]
PRIMARY_METRICS = ("unseen_coverage", "fired_samples")
INDICATORS = {
    "reachability": ("capable_gained",),
    "observability": ("unseen_coverage", "seen_coverage", "all_coverage", "unseen_fdr", "fired_samples"),
    "reorganisation of later structure": ("adopted", "changes_applied", "controller_changes", "meta_revisions", "meta_exhausted"),
    "temporal continuity": ("stopped_early", "ceased_share"),
}


def assess(analysis: dict, margin: float = 0.05) -> dict:
    """Fill the axes from a study analysis. ``margin`` is the equivalence margin as a share of the compared mean."""
    mode = analysis["mode"]
    axes = []
    verdicts = []
    for name, spec in AXES.items():
        present = [m for m in INDICATORS.get(name, ()) if m in analysis["metrics"]]
        rows = []
        for c in analysis["contrasts"]:
            for m in present:
                r = c["metrics"].get(m)
                if not r or not r.get("n"):
                    continue
                lo, hi = r.get("ci95") or [None, None]
                scale = r.get("scale") or 0
                within = lo is not None and hi is not None and scale and -margin * scale <= lo and hi <= margin * scale
                rows.append(
                    {
                        "contrast": c["id"],
                        "a": c["a"],
                        "b": c["b"],
                        "metric": m,
                        "n": r["n"],
                        "mean_diff": r.get("mean"),
                        "ci95": r.get("ci95"),
                        "status": r.get("status"),
                        "inside_equivalence_margin": bool(within),
                        "evidence": c["evidence"],
                    }
                )
        axes.append(
            {
                "axis": name,
                "indicators_defined": spec["indicators"],
                "indicators_in_this_study": present,
                "comparable": spec["comparable"],
                "why": spec["reason"],
                "contrasts": rows,
            }
        )
        if spec["comparable"]:
            verdicts += rows
    detected = [r for r in verdicts if r["status"] == "DETECTED" and r["evidence"] == "confirmatory"]
    inside = [r for r in verdicts if r["inside_equivalence_margin"]]
    if mode != "confirmatory" or not verdicts:
        verdict = (
            "not evaluated: the study is "
            + (mode if mode != "confirmatory" else "without a comparable indicator")
            + " (non-redundancy needs an independent confirmatory comparison)"
        )
    elif detected:
        verdict = "established on at least one comparable axis in this confirmatory study (see the rows); other axes are not comparable or not evaluable"
    elif verdicts and len(inside) == len(verdicts):
        verdict = "equivalent: every comparable contrast lies inside the equivalence margin"
    else:
        verdict = "not established: no declared comparable contrast was detected"
    return {
        "schema": "xzr.nonredundancy/1",
        "experiment_id": analysis["experiment_id"],
        "mode": mode,
        "equivalence_margin": margin,
        "axes": axes,
        "not_evaluable_by_this_environment": NOT_EVALUABLE,
        "verdict": verdict,
        "rule": "non-redundancy is never inferred from the existence of revision, reachability records or meta-revision; see the module docstring",
        "unestablished_by_default": True,
    }
