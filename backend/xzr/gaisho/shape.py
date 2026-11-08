"""Shape generation. A shape is built ONLY from the relations the experiments identified, never drawn first and named after: for a condition and a moment the recorded response of the operation to the interventions
on the two axes (the response surface) gives the vertices; their neighbours give the edges; the places where the response crosses the decision level give the branch; the neighbours whose responses differ by at least half
give the cuts; the cells that were not recorded are kept as UNRESOLVED regions with the reason. Every vertex, edge and region carries what it came from (the cell, the number of trials, the seeds, the digest of the run it
was read from) and a provenance class. The coordinate system is a researcher-chosen PROJECTION (the default is the intervention plane and the outcome): the figure drawn is a projection of identified relations, not the
complete acquisition of an operation, and no fixed solid is used for every candidate.
"""

from __future__ import annotations

import numpy as np

from .model import digest


def build_shape(result: dict, cond: str, snapshot: str, dom_axes: dict, projection: str = "response-surface") -> dict:
    c = result["conditions"][cond]
    snap = c["snapshots"].get(snapshot)
    base = {"domain": result["domain"], "condition": cond, "snapshot": snapshot, "model_version": result["model_version"], "projection": {"kind": "VISUALIZATION_PROJECTION", "name": projection, "axes": {"x": dom_axes["x"], "y": dom_axes["y"], "z": "outcome (share of trials)"}, "chosen_by": "researcher (default)"}}
    if not snap or not snap.get("recorded"):
        return {**base, "recorded": False, "reason": (snap or {}).get("reason", "UNMEASURED"), "vertices": [], "edges": [], "branch": [], "cuts": [], "unresolved": [], "digest": digest(base)}
    nx, ny = snap["nx"], snap["ny"]
    by = {(k["i"], k["j"]): k for k in snap["cells"]}
    src = {"operation_digest": c["operation_digest"], "seeds": c["seeds"], "provenance": "RECORDED_OBSERVATION"}  # a cell is a recorded observation of the operation under an intervention (a difference between interventions is read from cells, as a relation)
    verts, unres = [], []
    for k in snap["cells"]:
        vid = f"v{k['i']}_{k['j']}"
        if k["p"] is None:
            unres.append({"id": vid, "x": k["x"], "y": k["y"], "reason": k["status"], "provenance": "VISUALIZATION_PROJECTION"})
        else:
            verts.append({"id": vid, "x": k["x"], "y": k["y"], "z": k["p"], "sd": k.get("sd"), "n": k["n"], "cell": [k["i"], k["j"]], "source": src})
    edges: list[dict] = []
    cuts: list[dict] = []
    branch: list[dict] = []
    for (i, j), k in by.items():
        for di, dj in ((1, 0), (0, 1)):
            q = by.get((i + di, j + dj))
            if not q or k["p"] is None or q["p"] is None:
                continue
            d = abs(q["p"] - k["p"])
            e = {"a": f"v{i}_{j}", "b": f"v{i + di}_{j + dj}", "difference": d, "source": {**src, "provenance": "RECONSTRUCTED_RELATION"}}
            (cuts if d >= 0.5 else edges).append(e)
            lo, hi = (k["p"], q["p"])
            if (lo - 0.5) * (hi - 0.5) < 0 and (nx > 1 and ny > 1):
                t = (0.5 - lo) / (hi - lo)
                branch.append({"x": k["x"] + t * (q["x"] - k["x"]), "y": k["y"] + t * (q["y"] - k["y"]), "z": 0.5, "from": [e["a"], e["b"]], "source": {**src, "provenance": "RECONSTRUCTED_RELATION"}})
    out = {**base, "recorded": True, "nx": nx, "ny": ny, "vertices": verts, "edges": edges, "cuts": cuts, "branch": branch, "unresolved": unres, "weights": snap.get("weights")}
    out["digest"] = digest(out)
    return out


def compare_shapes(a: dict, b: dict) -> dict:
    """The difference of two shapes of the same domain (two conditions, two moments, two observation conditions): the cell-wise difference of the outcome, the cuts in one and not the other (a cut or a reconnection),
    the branch points that moved, and what stayed unresolved in either. Nothing is scored: these are differences."""
    if not (a.get("recorded") and b.get("recorded")):
        return {"comparable": False, "reason": "one of the shapes was not recorded"}
    va, vb = {v["id"]: v for v in a["vertices"]}, {v["id"]: v for v in b["vertices"]}
    common = sorted(set(va) & set(vb))
    d = np.array([vb[i]["z"] - va[i]["z"] for i in common])
    ca, cb = {(e["a"], e["b"]) for e in a["cuts"]}, {(e["a"], e["b"]) for e in b["cuts"]}
    ra, rb = {u["id"]: u["reason"] for u in a["unresolved"]}, {u["id"]: u["reason"] for u in b["unresolved"]}
    return {
        "comparable": True,
        "cells_compared": len(common),
        "mean_abs_difference": float(np.abs(d).mean()) if d.size else None,
        "max_abs_difference": float(np.abs(d).max()) if d.size else None,
        "mean_signed_difference": float(d.mean()) if d.size else None,
        "cuts_only_in_first": sorted(f"{x}-{y}" for x, y in ca - cb),
        "cuts_only_in_second": sorted(f"{x}-{y}" for x, y in cb - ca),
        "unresolved_in_first_only": sorted(set(ra) - set(rb)),
        "unresolved_in_second_only": sorted(set(rb) - set(ra)),
        "branch_points": [len(a["branch"]), len(b["branch"])],
        "cell_differences": {i: float(x) for i, x in zip(common, d, strict=True)},
    }


def relation_vector(cond_result: dict, names: list[str]) -> list[float | None]:
    return [cond_result["relations"][n]["value"] if cond_result["relations"][n]["status"] == "IDENTIFIED" else None for n in names]


def structural_similarity(result: dict) -> list[dict]:
    """The similarity of the relation profiles of every pair of conditions, over the relations identified in both: 1 minus the mean absolute difference (the relations are in [-1, 1] or are accuracies). A similarity between two
    conditions, or between two domains, is a structural similarity of identified relations: it is reported whether it is shared and it is not assumed to identify a common core."""
    names = list(next(iter(result["conditions"].values()))["relations"])
    conds = list(result["conditions"])
    out = []
    for i in range(len(conds)):
        for j in range(i + 1, len(conds)):
            va, vb = relation_vector(result["conditions"][conds[i]], names), relation_vector(result["conditions"][conds[j]], names)
            pairs = [(x, y) for x, y in zip(va, vb, strict=True) if x is not None and y is not None]
            out.append({"a": conds[i], "b": conds[j], "relations_compared": len(pairs), "similarity": (1.0 - float(np.mean([abs(x - y) for x, y in pairs]))) if pairs else None})
    return out
