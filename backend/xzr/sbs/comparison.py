"""SBS-05, the body-concept comparison: does a body-inclusive description add anything that a body-free or a dynamical description does not already hold?

The task. At the end of an intervention an observer has ONE frame of the particle positions (with the measurement error of the observation condition) and knows which intervention was applied and how strongly (all models are permitted this, equally). The target is, for every particle, whether it belongs to the largest group at the end of the recovery (read from the true positions, which no model sees).

The models, all logistic regressions of the same family, the same ridge, the same training data, 8 parameters each unless stated:

* A  body-inclusive:  features of the particle's GROUP in the observed frame (the observed partition into connected groups): whether it is in the largest group, its group's size, its distance to the group centre in units of the group's radius, the share of the largest group.
* B  body-free component:  features of the particle's NEIGHBOURHOOD only, with no group label: contact counts within one, two and three bond lengths and the nearest-neighbour distance. B is allowed neighbourhoods up to three bond lengths so that it is not starved of the multi-hop information the group label summarises.
* C  dynamical (order-parameter) account:  the global state of the system (largest share, bond density, their product and the number of groups), the same for every particle of a run; no particle-level information and no group label.
* N  null:  the intervention descriptor only (4 parameters). It shows whether any state information matters.

Nothing in the features reads the simulation state: the feature functions take the observed frame and the intervention descriptor and nothing else (a test checks that). Verdicts are on paired Brier scores over independent worlds (initial gases), margin 0.01, Holm correction over all comparisons. 'EQUIVALENT_WITHIN_MARGIN' is a statement about this margin and this design, not that the descriptions are the same; 'UNRESOLVED' is kept as such. If B or C reproduces A's accuracy, the result is: no nonredundant advantage of the body-inclusive description was demonstrated in this task. It is not evidence that no body-level organization exists."""

from __future__ import annotations

from typing import Any

import numpy as np

from . import organisation as org
from .lab_stats import holm, paired_t
from .protocol import PROTOCOL

MARGIN = 0.01
MODELS = {
    "A": {"label": "body-inclusive (group features of the observed partition)", "parameters": 8},
    "B": {"label": "body-free component (neighbourhood features up to three bond lengths)", "parameters": 8},
    "C": {"label": "dynamical order-parameter account (global state only)", "parameters": 8},
    "N": {"label": "null (intervention descriptor only)", "parameters": 4},
}
PAIRS = (("A", "B"), ("A", "C"), ("B", "C"), ("A", "N"), ("B", "N"), ("C", "N"))
OBS = ("fine", "coarse")


def descriptor(kind: str | None, level: float | None) -> list[float]:
    """The intervention as every model is told it: two indicators and a severity in [0, 1]."""
    if kind == "decoupling":
        return [1.0, 0.0, (1.5 - float(level)) / 1.5]
    if kind == "heating":
        return [0.0, 1.0, (float(level) - 0.3) / 1.7]
    return [0.0, 0.0, 0.0]


def features(model: str, frame: np.ndarray, box: float, desc: list[float]) -> np.ndarray:
    """Feature matrix (one row per particle) from the OBSERVED frame and the intervention descriptor only."""
    n = len(frame)
    d = frame[:, None, :] - frame[None, :, :]
    d -= box * np.round(d / box)
    r = np.sqrt((d**2).sum(-1))
    np.fill_diagonal(r, np.inf)
    dd = np.tile(np.array(desc), (n, 1))
    if model == "N":
        return dd
    if model == "B":
        rb = org.R_BOND
        cols = [(r < rb).sum(1), (r < 2 * rb).sum(1), (r < 3 * rb).sum(1), np.minimum(r.min(1), 3.0)]
        return np.column_stack([*cols, dd])
    lab = org.partition(frame, box)
    sizes = {k: int((lab == k).sum()) for k in set(int(v) for v in lab if v >= 0)}
    big = max(sizes, key=sizes.get) if sizes else -1
    if model == "A":
        in_big = (lab == big).astype(float) if big >= 0 else np.zeros(n)
        gsize = np.array([sizes.get(int(v), 0) for v in lab], dtype=float) / n
        rel = np.zeros(n)
        for k in sizes:
            idx = np.flatnonzero(lab == k)
            disp = d[idx, idx[0]] * -1.0  # displacements of the members from the first member (minimum image)
            disp -= disp.mean(axis=0)  # from the group centre
            dist = np.linalg.norm(disp, axis=1)
            rel[idx] = dist / max(float(np.sqrt((dist**2).mean())), 1e-6)  # in units of the group's radius of gyration
        share = np.full(n, sizes.get(big, 0) / n)
        return np.column_stack([in_big, gsize, rel, share, dd])
    # model C: the global state
    adj = r < org.R_BOND
    ph = org.physical(frame, box)
    share, bonds, groups = ph["largest_share"], adj.sum() / 2 / n, ph["groups_tracked"] / n
    g = np.array([share, bonds, share * bonds, groups])
    return np.column_stack([np.tile(g, (n, 1)), dd])


def fit_logistic(X: np.ndarray, y: np.ndarray, ridge: float = 1e-2, iters: int = 50) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ridge-penalised logistic regression by Newton steps on standardised features."""
    mu, sd = X.mean(0), X.std(0)
    sd = np.where(sd < 1e-9, 1.0, sd)
    Z = np.column_stack([(X - mu) / sd, np.ones(len(X))])
    w = np.zeros(Z.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(Z @ w, -30, 30)))
        g = Z.T @ (p - y) + ridge * np.r_[w[:-1], 0.0]
        H = (Z * (p * (1 - p))[:, None]).T @ Z + ridge * np.diag(np.r_[np.ones(Z.shape[1] - 1), 0.0]) + 1e-9 * np.eye(Z.shape[1])
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w, mu, sd


def predict(w: np.ndarray, mu: np.ndarray, sd: np.ndarray, X: np.ndarray) -> np.ndarray:
    Z = np.column_stack([(X - mu) / sd, np.ones(len(X))])
    return 1 / (1 + np.exp(-np.clip(Z @ w, -30, 30)))


def build_dataset(worlds: list[dict[str, Any]], obs_name: str) -> list[dict[str, Any]]:
    """One entry per (world, branch): the observed frame at the end of the intervention is turned into the feature blocks of every model; the target is the final largest-group membership."""
    rows = []
    box = float(np.sqrt(PROTOCOL["model"]["n"] / PROTOCOL["model"]["density"]))
    n = PROTOCOL["model"]["n"]
    for w in worlds:
        for bi, b in enumerate(w["branches"]):
            frame = b["_observed_at_end_of_intervention"][obs_name]
            desc = descriptor(b["kind"] if b["kind"] != "control" else None, b["level"])
            y = np.zeros(n)
            y[b["_final_largest_group"]] = 1.0
            rows.append({"seed": w["seed"], "branch": bi, "kind": b["kind"], "level": b["level"], "y": y, "X": {m: features(m, frame, box, desc) for m in MODELS}})
    return rows


def evaluate(train: list[dict[str, Any]], test: list[dict[str, Any]]) -> dict[str, dict[int, float]]:
    """Brier score per test world and model (the mean over the world's test branches and particles)."""
    out: dict[str, dict[int, float]] = {}
    for m in MODELS:
        w, mu, sd = fit_logistic(np.vstack([r["X"][m] for r in train]), np.concatenate([r["y"] for r in train]))
        per_world: dict[int, list[float]] = {}
        for r in test:
            p = predict(w, mu, sd, r["X"][m])
            per_world.setdefault(r["seed"], []).append(float(np.mean((p - r["y"]) ** 2)))
        out[m] = {s: float(np.mean(v)) for s, v in per_world.items()}
    return out


def run_comparison(worlds: list[dict[str, Any]], train_seeds: list[int], test_seeds: list[int]) -> dict[str, Any]:
    """Two evaluation protocols (held-out worlds; held-out worlds AND harsher interventions) under both observation conditions; all comparisons corrected together."""
    spec = PROTOCOL["interventions"]
    mild = {(k, lv) for k, s in spec.items() for lv in s["levels"][:2]}
    harsh = {(k, lv) for k, s in spec.items() for lv in s["levels"][2:]}
    rows: list[dict[str, Any]] = []
    tests: list[tuple[str, str, str, str, dict[str, Any]]] = []
    for obs in OBS:
        data = build_dataset(worlds, obs)
        tr_all = [r for r in data if r["seed"] in train_seeds]
        te_all = [r for r in data if r["seed"] in test_seeds]
        protocols = {
            "held_out_worlds": (tr_all, te_all),
            "held_out_worlds_and_harsher_interventions": ([r for r in tr_all if r["kind"] == "control" or (r["kind"], r["level"]) in mild], [r for r in te_all if (r["kind"], r["level"]) in harsh]),
        }
        for pname, (tr, te) in protocols.items():
            brier = evaluate(tr, te)
            seeds = sorted(set(brier["A"]) & set(brier["B"]) & set(brier["C"]) & set(brier["N"]))
            rows.append({"observation": obs, "protocol": pname, "n_train_rows": len(tr), "n_test_worlds": len(seeds), "mean_brier": {m: float(np.mean([brier[m][s] for s in seeds])) for m in MODELS}})
            for x, y in PAIRS:
                d = [brier[y][s] - brier[x][s] for s in seeds]  # positive: x predicts better than y
                tests.append((obs, pname, x, y, paired_t(d)))
    adj = holm([t[4]["p"] for t in tests])
    comps = []
    for (obs, pname, x, y, tt), pa in zip(tests, adj, strict=True):
        lo, hi = tt["ci95"]
        if lo > MARGIN and pa < 0.05:
            v = f"{x}_BETTER"
        elif hi < -MARGIN and pa < 0.05:
            v = f"{y}_BETTER"
        elif lo > -MARGIN and hi < MARGIN:
            v = "EQUIVALENT_WITHIN_MARGIN"
        else:
            v = "UNRESOLVED"
        comps.append({"observation": obs, "protocol": pname, "pair": [x, y], "brier_difference_y_minus_x": tt, "p_holm": pa, "verdict": v})
    return {"models": MODELS, "margin": MARGIN, "rule": "x_BETTER if the 95% interval of (Brier_y - Brier_x) lies above the margin and the Holm-adjusted p < 0.05; EQUIVALENT_WITHIN_MARGIN if the interval lies inside +/- the margin; otherwise UNRESOLVED", "evaluations": rows, "comparisons": comps}
