"""Paired statistics for HPO contrasts (fixed seeds; every random draw here is seeded).

For one metric and one contrast (condition X against reference Y, paired by seed):

    mean, sd, dz          mean paired difference, its standard deviation, standardised effect size mean/sd
    ci95                  percentile bootstrap interval of the mean (2,000 resamples, seeded)
    p                     two-sided sign-flip test: exact for ≤ 16 seeds, else Monte Carlo with 20,000 sign patterns
    p_holm                Holm-adjusted across the metrics of the contrast
    noise_floor           |mean| + 1.96·se of the noise comparison (C~ − C: same exogenous input, another endogenous
                          stream) for that metric — the size of difference ordinary trajectory divergence produces

Status: IDENTICAL (every difference 0) · DETECTED (p_holm < α, |mean| ≥ 2 % of scale, |mean| > noise floor) ·
EQUIVALENT (the 95 % interval lies within ±5 % of scale) · UNRESOLVED (neither shown). Scale = the larger of the two
condition means in absolute value (so a mechanism that is absent in the reference still has a scale). Runs whose
metric is undefined (NaN, e.g. no re-ignition happened) are dropped pairwise and the number used is reported.
"""

from __future__ import annotations

import math
from itertools import product

import numpy as np

ALPHA = 0.01
PRACTICAL = 0.02
EQUIV = 0.05


def sign_flip_p(d: np.ndarray, rng: np.random.Generator, n_perm: int = 20000) -> float:
    s = d.size
    if s == 0 or np.allclose(d, 0):
        return 1.0
    obs = abs(d.mean())
    if s <= 16:
        signs = np.array(list(product((1, -1), repeat=s)), dtype=float)
    else:
        signs = rng.choice((-1.0, 1.0), size=(n_perm, s))
    stats = np.abs((signs * d).mean(axis=1))
    return float(((stats >= obs - 1e-12).sum() + (0 if s <= 16 else 1)) / (len(signs) + (0 if s <= 16 else 1)))


def bootstrap_ci(d: np.ndarray, rng: np.random.Generator, n: int = 2000) -> tuple[float, float]:
    if d.size < 2:
        return (-math.inf, math.inf)
    idx = rng.integers(0, d.size, size=(n, d.size))
    means = d[idx].mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def holm(ps: dict[str, float]) -> dict[str, float]:
    items = sorted(ps.items(), key=lambda kv: kv[1])
    m = len(items)
    out, running = {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def paired(x: np.ndarray, y: np.ndarray, noise: np.ndarray | None, rng: np.random.Generator) -> dict:
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    d = x - y
    if d.size == 0:
        return {"n": 0, "status": "NOT MEASURED", "note": "metric undefined in every pair"}
    mean = float(d.mean())
    sd = float(d.std(ddof=1)) if d.size > 1 else 0.0
    lo, hi = bootstrap_ci(d, rng)
    floor = 0.0
    if noise is not None:
        nz = noise[~np.isnan(noise)]
        if nz.size > 1:
            floor = abs(float(nz.mean())) + 1.96 * float(nz.std(ddof=1)) / math.sqrt(nz.size)
    scale = max(abs(float(x.mean())), abs(float(y.mean())), 1e-12)
    return {"n": int(d.size), "mean_x": float(x.mean()), "mean_y": float(y.mean()), "mean": mean, "sd": sd,
            "dz": mean / sd if sd > 0 else (math.inf if mean else 0.0), "relative": mean / scale, "ci95": [lo, hi],
            "p": sign_flip_p(d, rng), "noise_floor": floor, "scale": scale, "identical": bool(np.allclose(d, 0))}


def classify(r: dict) -> str:
    if r.get("n", 0) == 0:
        return "NOT MEASURED"
    if r["identical"]:
        return "IDENTICAL"
    if r["p_holm"] < ALPHA and abs(r["mean"]) >= PRACTICAL * r["scale"] and abs(r["mean"]) > r["noise_floor"]:
        return "DETECTED"
    lo, hi = r["ci95"]
    if math.isfinite(lo) and -EQUIV * r["scale"] <= lo and hi <= EQUIV * r["scale"]:
        return "EQUIVALENT"
    return "UNRESOLVED"


def contrast(rows_x: list[dict], rows_y: list[dict], metrics: list[str], noise: dict[str, np.ndarray] | None,
             seed: int) -> dict:
    rng = np.random.default_rng([seed, 0x5354])
    out = {}
    for m in metrics:
        x = np.array([r.get(m, math.nan) for r in rows_x], float)
        y = np.array([r.get(m, math.nan) for r in rows_y], float)
        out[m] = paired(x, y, None if noise is None else noise.get(m), rng)
    ps = {m: v["p"] for m, v in out.items() if v.get("n", 0)}
    for m, p in holm(ps).items():
        out[m]["p_holm"] = p
    for v in out.values():
        v["status"] = classify(v)
    return out
