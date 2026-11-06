"""Competing surface models for the executed domains other than knowledge (002 Bias, 003 Freedom, 004 Body, 005 Credit).

Dictionary D5 asks that a P/A-specific claim be withdrawn where a matched, equally resourced rival reproduces the contrast. The knowledge domain has its own comparison (``compare.compare_models``: the candidate construction against M0 / M1 / M4). The other domains have no candidate construction of that kind, so the question asked here is smaller and is stated as such:

    Which of three nested descriptions of the recorded surface (the outcome over the two interventions of the domain) predicts the cells that were NOT given to it?

* M0  the marginal rate of the training cells (one parameter; what a single summary statistic holds)
* M1  an additive logistic response to the two interventions (three parameters)
* M2  M1 with an interaction term x*y (four parameters)

All three see the SAME training cells of the 'end' snapshot, none sees the held-out cells or any other snapshot, and the fit is the same least squares on the clipped logit as in ``compare``. Two splits, because a surface that is interpolated well can still be extrapolated badly: ``interpolation`` (training cells are those with i + j even, the held-out cells the others) and ``extrapolation`` (training cells are the first 60 % of the x axis, the held-out cells the rest). The error is the root-mean-square error on the held-out cells, paired over seeds.

What a verdict says. ``RICHER_NEEDED``: the richer model predicts the held-out cells better than the simpler one by more than the margin (95 % interval). ``SIMPLER_SUFFICES``: the interval lies inside +/- the margin. ``RICHER_WORSE``: the richer model is worse by more than the margin. ``UNRESOLVED``: none of these. These are statements about the shape of the response surface of a SYNTHETIC rule set (002, 003, 005) or of a simulated body (004), at one grid. They are not statements about bias, freedom, credit, the body, knowledge or a Gaisho; M2 being needed means the two interventions interact in the recorded surface, not that anything is attributed. No mechanism-level rival (a POMDP, an adaptive controller, a competing institution model) is built here: that would be a new model with its own specification, and XB-TRO has no pluggable controller. Nothing in this module is registered or changes a record of the laboratory."""

from __future__ import annotations

from typing import Any

import numpy as np

from . import MODEL_VERSION
from .lab import FULL, Domain, Observation, paired
from .model import digest

MODELS = {
    "M0": {"label": "marginal rate of the training cells", "parameters": 1},
    "M1": {"label": "additive logistic response to the two interventions", "parameters": 3},
    "M2": {"label": "M1 with an interaction term", "parameters": 4},
}
PAIRS = (("M0", "M1"), ("M1", "M2"))  # (simpler, richer)
SPLITS = ("interpolation", "extrapolation")
MARGIN = 0.03


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 0.02, 0.98)
    return np.log(p / (1 - p))


def _features(x: np.ndarray, y: np.ndarray, kind: str) -> np.ndarray:
    one = np.ones_like(x)
    return np.stack([x, y, one], axis=1) if kind == "M1" else np.stack([x, y, x * y, one], axis=1)


def _fit_predict(kind: str, train: tuple[np.ndarray, np.ndarray, np.ndarray], test: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    tx, ty, tp = train
    if kind == "M0":
        return np.full(test[0].shape, float(np.mean(tp)))
    w = np.linalg.lstsq(_features(tx, ty, kind), _logit(tp), rcond=None)[0]
    z = _features(test[0], test[1], kind) @ w
    return 1.0 / (1.0 + np.exp(-z))


def _split(cells: list[dict], nx: int, kind: str) -> tuple[list[dict], list[dict]]:
    if kind == "interpolation":
        tr = [c for c in cells if (c["i"] + c["j"]) % 2 == 0]
    else:
        tr = [c for c in cells if c["i"] < int(0.6 * nx)]
    ids = {(c["i"], c["j"]) for c in tr}
    return tr, [c for c in cells if (c["i"], c["j"]) not in ids]


def _arrays(cells: list[dict], x0: float, xs: float, y0: float, ys: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (np.array([(c["x"] - x0) / xs for c in cells]), np.array([(c["y"] - y0) / ys for c in cells]), np.array([c["p"] for c in cells], dtype=float))


def _verdict(diff: dict) -> str:
    if diff["ci95"] is None:
        return "UNRESOLVED"
    lo, hi = diff["ci95"]
    if lo > MARGIN:
        return "RICHER_NEEDED"
    if hi < -MARGIN:
        return "RICHER_WORSE"
    if lo > -MARGIN and hi < MARGIN:
        return "SIMPLER_SUFFICES"
    return "UNRESOLVED"


def compare_surface_models(dom: Domain, seeds: tuple[int, ...], conditions: list[str] | None = None, obs: Observation = FULL) -> dict[str, Any]:
    """The three nested descriptions on the held-out cells of every condition of ``dom``, two splits, paired over ``seeds``."""
    names = conditions or list(dom.conditions)
    nx, ny = len(dom.x_values), len(dom.y_values)
    x0, xs = float(dom.x_values.min()), float(np.ptp(dom.x_values)) or 1.0
    y0, ys = float(dom.y_values.min()), float(np.ptp(dom.y_values)) or 1.0
    rows = []
    for cond in names:
        prepare = getattr(dom, "prepare", None)
        if prepare is not None:
            prepare(cond, seeds, obs)
        errs: dict[str, dict[str, list[float]]] = {s: {m: [] for m in MODELS} for s in SPLITS}
        for seed in seeds:
            end = dom.simulate(cond, seed, obs)["snapshots"].get("end")
            if not end:
                continue
            cells = [c for c in end["surface"]["cells"] if c["p"] is not None]
            for split in SPLITS:
                tr, te = _split(cells, nx, split)
                if len(tr) < 6 or not te:
                    continue
                train = _arrays(tr, x0, xs, y0, ys)
                tex, tey, tep = _arrays(te, x0, xs, y0, ys)
                for m in MODELS:
                    pred = _fit_predict(m, train, (tex, tey))
                    errs[split][m].append(float(np.sqrt(np.mean((pred - tep) ** 2))))
        per_split = {}
        for split in SPLITS:
            e = errs[split]
            if min(len(v) for v in e.values()) < 2:
                per_split[split] = {"verdicts": [{"simpler": a, "richer": b, "verdict": "UNRESOLVED", "why": "fewer than two seeds with held-out cells"} for a, b in PAIRS]}
                continue
            verdicts = []
            for a, b in PAIRS:
                d = paired(list(e[a]), list(e[b]))  # simpler error minus richer error: positive = the richer model predicts better
                verdicts.append({"simpler": a, "richer": b, "verdict": _verdict(d), "error_difference": d, "margin": MARGIN})
            per_split[split] = {"errors": {m: float(np.mean(v)) for m, v in e.items()}, "n_seeds": len(e["M0"]), "verdicts": verdicts}
        rows.append({"condition": cond, **per_split})
    return {"domain": dom.id, "seeds": list(seeds), "grid": {"x": nx, "y": ny}, "rows": rows}


def run_surface_models(seeds_by_domain: dict[str, tuple[int, ...]], domains: dict[str, Domain | None]) -> dict[str, Any]:
    """The comparison for every domain given; a domain that is not linked is listed as not executed and nothing is computed for it."""
    out: dict[str, Any] = {}
    not_run: dict[str, str] = {}
    for dom_id, seeds in seeds_by_domain.items():
        dom = domains.get(dom_id)
        if dom is None:
            not_run[dom_id] = "the domain is not executed here (the XB-TRO link is not configured); nothing was computed or substituted"
            continue
        out[dom_id] = compare_surface_models(dom, seeds, list(getattr(dom, "default_conditions", None) or dom.conditions))
    body = {
        "model_version": MODEL_VERSION,
        "models": MODELS,
        "splits": {"interpolation": "training cells with i + j even, held-out cells the others", "extrapolation": "training cells the first 60 % of the x axis, held-out cells the rest"},
        "margin": MARGIN,
        "rule": "RICHER_NEEDED if the richer model's held-out error is lower than the simpler model's by more than the margin (95 % interval); SIMPLER_SUFFICES if the interval lies inside +/- the margin; RICHER_WORSE if the richer model is worse by more than the margin; otherwise UNRESOLVED",
        "reading": "shape of a recorded response surface at one grid; not bias, freedom, credit, the body, knowledge or a Gaisho; no mechanism-level rival (POMDP, adaptive controller, competing institution model) was built",
        "domains": out,
        "not_executed": not_run,
    }
    return {**body, "digest": digest(body)}
