"""Where the cells and the edges of a shape come from, and what a change between two shapes is a change OF.

A shape of the laboratory is built from one recorded surface: a grid of interventions (two axes) and, for each grid point, the share of trials with one outcome. ``explain_shape`` states, for every cell and every edge, the intervention it
stands for, the quantity measured, the number of trials and seeds behind it, the construction rule, and (for the knowledge domain, where the operation is a decision rule with three weights) what the model's own weights predict for it.
It also fits the three weights back from the recorded cells: the surface carries the information of the DECISION RULE at that moment (and sampling noise); it is not a record of the run's history, and it is not an observation of a
knowledge Gaisho. ``change_kinds`` separates the four things in which two shapes can differ: the realized operation, the recorded observation, the reconstructed relation and the display.

Nothing here is part of the digest of a record: these are readings of a record (adding them leaves every saved digest as it was).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

LAYERS = {
    "cell": {"real_operation": "the operation behind it is executed in the model: the agent's decision rule (weights at the snapshot) evaluated with E and S set by intervention", "recorded_observation": "THE VALUE of the cell: the share of its trials with the outcome, through the observation instrument (noise, scale, window, ...)",
             "reconstructed_relation": "none: a cell is not derived from other cells", "display": "only its position (the projection)"},
    "edge": {"real_operation": "none: an edge is not an operation", "recorded_observation": "none: only its two ends are recorded", "reconstructed_relation": "THE DIFFERENCE of the two recorded ends; a cut if it is at least 0.5 (a threshold of the laboratory)", "display": "the line that is drawn"},
    "branch_point": {"real_operation": "none", "recorded_observation": "none", "reconstructed_relation": "THE LINEAR INTERPOLATION of the 0.5 crossing between two recorded ends: not a measured point", "display": "the marker"},
    "unresolved": {"real_operation": "unknown: it may exist and was not recorded", "recorded_observation": "none: nothing was recorded", "reconstructed_relation": "none", "display": "THE MARKER of an absence, with the class of the reason"},
    "surface_between_cells": {"real_operation": "none", "recorded_observation": "none", "reconstructed_relation": "an assumption of continuity between four recorded neighbours", "display": "THE DRAWN FACE and the colour (not drawn across a cut)"},
}
SURFACE_RULES = {
    "cell": "one cell per grid point (i, j) of the two interventions: nx x ny cells. It is RECORDED (a value from trials), or UNRESOLVED (a class of the reason it was not recorded): no cell is dropped.",
    "cell_value": "the share of the trials of the cell that had the outcome, averaged over the seeds (one run per seed is the replication unit; the sd is across seeds).",
    "edge": "one edge between two neighbouring grid points along an axis: (nx-1) x ny along the first axis plus nx x (ny-1) along the second, drawn only where both ends are RECORDED cells.",
    "cut": "an edge whose two ends differ by at least 0.5 is a CUT: the surface is not drawn across it (a threshold of the laboratory, not a finding).",
    "branch_point": "where the segment of an edge crosses the level 0.5 of the outcome (linear interpolation between the two recorded ends): a reconstructed relation, not a measured point.",
    "unresolved": "a cell that was not recorded keeps its position on the base plane and the class of the reason (the six unobserved classes).",
    "projection": "x and y are the intervention values, the height is the value of the cell: a VISUALIZATION_PROJECTION chosen by the laboratory and declared in the record; it is not a physical place.",
}


def _expected_edges(nx: int, ny: int) -> int:
    return (nx - 1) * ny + nx * (ny - 1)


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def fit_logistic_surface(vertices: list[dict], n_per_cell: float) -> dict | None:
    """Fit P = sigmoid(a x + b y + c) to the recorded cells by iteratively reweighted least squares (binomial likelihood, weights = trials x seeds). Returns the parameters and the root-mean-square residual."""
    if len(vertices) < 4:
        return None
    X = np.array([[v["x"], v["y"], 1.0] for v in vertices])
    p = np.clip(np.array([v["z"] for v in vertices]), 1e-4, 1 - 1e-4)
    wgt = np.full(len(vertices), float(n_per_cell))
    beta = np.zeros(3)
    for _ in range(60):
        mu = _sigmoid(X @ beta)
        W = np.maximum(wgt * mu * (1 - mu), 1e-9)
        z = X @ beta + (p - mu) / np.maximum(mu * (1 - mu), 1e-9)
        try:
            new = np.linalg.solve(X.T @ (W[:, None] * X) + 1e-9 * np.eye(3), X.T @ (W * z))
        except np.linalg.LinAlgError:
            return None
        if float(np.max(np.abs(new - beta))) < 1e-9:
            beta = new
            break
        beta = np.clip(new, -40, 40)
    fitted = _sigmoid(X @ beta)
    return {"a": float(beta[0]), "b": float(beta[1]), "c": float(beta[2]), "rms_residual": float(np.sqrt(np.mean((p - fitted) ** 2))), "cells_used": len(vertices)}


def explain_shape(rec: dict, cond: str, snapshot: str, dom: Any = None) -> dict:
    """The construction of one shape of a record, cell by cell and edge by edge."""
    shape = rec["shapes"][cond][snapshot]
    res = rec["result"]
    out: dict[str, Any] = {"domain": res["domain"], "condition": cond, "snapshot": snapshot, "shape_digest": shape["digest"], "rules": SURFACE_RULES, "layers": LAYERS, "axes": shape["projection"]["axes"]}
    if not shape.get("recorded"):
        return {**out, "recorded": False, "reason": shape.get("reason")}
    nx, ny = shape["nx"], shape["ny"]
    seeds = res["seeds"]
    verts, unres = shape["vertices"], shape["unresolved"]
    n_trials = verts[0]["n"] if verts else 0
    weights = shape.get("weights")
    ax, ay = shape["projection"]["axes"]["x"], shape["projection"]["axes"]["y"]
    expected = None
    if weights and {"a", "b", "c"} <= set(weights):
        expected = lambda x, y: float(_sigmoid(weights["a"] * x + weights["b"] * y + weights["c"]))  # noqa: E731
    cells = []
    for v in verts:
        e = expected(v["x"], v["y"]) if expected else None
        se = (v["sd"] / math.sqrt(len(seeds))) if v.get("sd") is not None else None
        cells.append({"id": v["id"], "cell": v["cell"], "intervention": {ax: v["x"], ay: v["y"]}, "value": v["z"], "sd_across_seeds": v.get("sd"), "se_of_mean": se, "trials_per_cell_and_seed": v["n"], "seeds": len(seeds),
                      "expected_from_the_agents_weights": e, "value_minus_expected": None if e is None else v["z"] - e, "operation_digest": v["source"]["operation_digest"], "provenance": v["source"]["provenance"]})
    vid = {v["id"]: v for v in verts}
    edges = []
    for kind, lst in (("edge", shape["edges"]), ("cut", shape["cuts"])):
        for e in lst:
            a, b = vid[e["a"]], vid[e["b"]]
            along = ax if a["cell"][1] == b["cell"][1] else ay
            ex = None if expected is None else abs(expected(b["x"], b["y"]) - expected(a["x"], a["y"]))
            edges.append({"a": e["a"], "b": e["b"], "kind": kind, "along": along, "difference": e["difference"], "expected_difference_from_weights": ex, "provenance": e["source"]["provenance"]})
    out.update({
        "recorded": True,
        "counts": {"grid": [nx, ny], "cells_expected": nx * ny, "cells_recorded": len(verts), "cells_unresolved": len(unres), "cells_total": len(verts) + len(unres),
                   "edges_expected_if_all_recorded": _expected_edges(nx, ny), "edges_drawn": len(shape["edges"]) + len(shape["cuts"]), "cuts": len(shape["cuts"]), "branch_points": len(shape["branch"])},
        "counts_consistent": len(verts) + len(unres) == nx * ny and len(shape["edges"]) + len(shape["cuts"]) <= _expected_edges(nx, ny) and (len(unres) > 0 or len(shape["edges"]) + len(shape["cuts"]) == _expected_edges(nx, ny)),
        "what_a_cell_is": "the share of the trials of this cell with the outcome of the domain, when the two interventions are set to the values of the cell",
        "outcome_of_the_domain": getattr(dom, "outcome_meaning", None),
        "cells": cells, "edges": edges,
        "weights_of_the_operation": weights,
        "unresolved": [{"id": u["id"], "reason": u["reason"]} for u in unres],
    })
    fit = fit_logistic_surface(verts, float(n_trials * len(seeds))) if expected is not None and verts else None
    if fit is not None and weights:
        sampling = float(np.sqrt(np.mean([max(1e-6, c["value"] * (1 - c["value"])) for c in cells]) / (n_trials * len(seeds))))
        out["what_the_surface_carries"] = {
            "fitted_weights": {k: fit[k] for k in ("a", "b", "c")}, "weights_of_the_operation": {k: weights[k] for k in ("a", "b", "c")},
            "rms_residual_of_the_fit": fit["rms_residual"], "expected_sampling_rms": sampling,
            "reading": ("the recorded cells are reproduced by three numbers, the weights of the agent's decision rule at this moment, up to sampling noise: the surface is a reading of that rule under intervention. It is not a record of the run's history "
                        "and nothing in it is a Gaisho; its form (a logistic ridge) is a property of the model's decision rule, so a difference between two shapes of this domain is a difference of those weights (or of sampling noise)."),
        }
    return out


def reading_of_difference(a: dict, b: dict, cmp: dict) -> dict:
    """What a difference between two shapes of the same domain is a difference OF, from what the shapes themselves record: the weights of the operation (a real change of the operation, if recorded), the cells (a change of the record), the
    expected sampling noise of the cells (a difference smaller than it is not a difference)."""
    wa, wb = a.get("weights"), b.get("weights")
    va, vb = {v["id"]: v for v in a["vertices"]}, {v["id"]: v for v in b["vertices"]}
    common = sorted(set(va) & set(vb))
    seeds_a, seeds_b = (a["vertices"][0]["source"]["seeds"] if a["vertices"] else 1), (b["vertices"][0]["source"]["seeds"] if b["vertices"] else 1)
    n_a, n_b = (a["vertices"][0]["n"] if a["vertices"] else 1), (b["vertices"][0]["n"] if b["vertices"] else 1)
    var = [(va[i]["z"] * (1 - va[i]["z"])) / (n_a * seeds_a) + (vb[i]["z"] * (1 - vb[i]["z"])) / (n_b * seeds_b) for i in common]
    noise = float(np.mean([math.sqrt(2 / math.pi) * math.sqrt(v) for v in var])) if var else None
    mean_abs = cmp.get("mean_abs_difference")
    wchg = None
    if wa and wb and set(wa) == set(wb):
        wchg = {k: wb[k] - wa[k] for k in wa}
    if wchg is None:
        operation = "UNDETERMINED (the weights of the operation were not recorded for one of the shapes)"
    elif max(abs(x) for x in wchg.values()) < 1e-9:
        operation = "SAME_OPERATION (the weights are identical)"
    else:
        operation = "OPERATION_CHANGED (the weights differ)"
    record = None
    if mean_abs is not None and noise is not None:
        record = "WITHIN_SAMPLING_NOISE" if mean_abs <= 1.5 * noise else "BEYOND_SAMPLING_NOISE"
    return {
        "real_operation": operation, "weight_change": wchg,
        "recorded_observation": {"mean_abs_difference": mean_abs, "expected_sampling_noise": noise, "reading": record},
        "reconstructed_relation": {"cuts_only_in_first": cmp.get("cuts_only_in_first"), "cuts_only_in_second": cmp.get("cuts_only_in_second"), "branch_points": cmp.get("branch_points"),
                                    "note": "cuts and branch points are reconstructed from the recorded cells with a fixed threshold: a change in them is a change of the reconstruction, which follows the record (including its noise)"},
        "display": "none: the choice of moment, ghost, layers and camera is a display setting; it changes no record and no relation",
        "summary": ("a change of the realized operation is claimed only where the weights differ; with identical weights the difference of the cells is the record's sampling noise" if operation.startswith("SAME") else
                    "the weights of the operation differ: the cells differ because the operation (the decision rule) differs" if operation.startswith("OPERATION") else "the cause of the difference cannot be read: the memory of the operation was not recorded"),
    }


def change_kinds_of_observations(cmp: dict) -> dict:
    """The four kinds for two observation conditions of the SAME condition (the output of ``compare_observations``)."""
    kinds = [r["kind"] for r in cmp["relations"]]
    return {
        "real_operation": "CHANGED (the observation is part of the run: probe, environment or window)" if cmp["observation_changed_the_operation"] else ("SAME" if cmp["same_realized_operation"] else "DIFFERENT"),
        "recorded_observation": "DIFFERS (a relation is recorded differently)" if any(k in ("RECORD_DIFFERENCE", "OPERATION_DIFFERENCE") for k in kinds) else "NO RELATION DIFFERS",
        "reconstructed_relation": {"unobserved_in_one": [r["relation"] for r in cmp["relations"] if r["kind"] == "UNOBSERVED_IN_ONE"], "unobserved_in_both": [r["relation"] for r in cmp["relations"] if r["kind"] == "UNOBSERVED_IN_BOTH"]},
        "display": "none: display settings change no record",
    }
