"""Small paired statistics (numpy only, deterministic): effect size, sign-flip permutation test, bootstrap interval.

All comparisons in this package are paired by seed (common random numbers), so the sample is a vector of per-seed
differences. NaN pairs (a quantity undefined in one of the two runs, e.g. a latency of a body that fell first) are dropped
and counted, never imputed.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

_RNG_SEED = 20261018


def clean_pairs(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, int]:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    return (b[ok] - a[ok]), int((~ok).sum())


def paired_effect(a: np.ndarray, b: np.ndarray, n_perm: int = 4096, n_boot: int = 1000) -> dict[str, Any]:
    """b − a over seeds. Returns mean difference, standardised effect (d_z), a two-sided sign-flip permutation p-value
    (exact up to 12 pairs, Monte-Carlo above), a bootstrap 95 % interval, n used and n dropped."""
    d, dropped = clean_pairs(a, b)
    n = len(d)
    out: dict[str, Any] = {"n": n, "dropped": dropped, "mean_diff": float("nan"), "d": float("nan"), "p": float("nan"),
                           "ci": [float("nan"), float("nan")], "mean_a": float("nan"), "mean_b": float("nan")}
    aa = np.asarray(a, dtype=float)
    bb = np.asarray(b, dtype=float)
    if np.isfinite(aa).any():
        out["mean_a"] = float(np.nanmean(aa))
    if np.isfinite(bb).any():
        out["mean_b"] = float(np.nanmean(bb))
    if n < 3:
        return out
    m = float(d.mean())
    sd = float(d.std(ddof=1))
    out["mean_diff"] = m
    out["d"] = m / sd if sd > 1e-15 else (0.0 if abs(m) < 1e-15 else math.copysign(float("inf"), m))
    rng = np.random.default_rng(_RNG_SEED)
    if n <= 12:
        signs = ((np.arange(2 ** n)[:, None] >> np.arange(n)[None]) & 1) * 2 - 1
    else:
        signs = rng.integers(0, 2, size=(n_perm, n)) * 2 - 1
    stat = np.abs((signs * d[None]).mean(axis=1))
    out["p"] = float(((stat >= abs(m) - 1e-15).sum() + (0 if n <= 12 else 1)) / (len(stat) + (0 if n <= 12 else 1)))
    idx = rng.integers(0, n, size=(n_boot, n))
    bm = d[idx].mean(axis=1)
    out["ci"] = [float(np.percentile(bm, 2.5)), float(np.percentile(bm, 97.5))]
    return out


def unpaired_effect(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) < 2 or len(b) < 2:
        return {"d": float("nan"), "n_a": len(a), "n_b": len(b)}
    sp = math.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    return {"d": float((b.mean() - a.mean()) / sp) if sp > 1e-15 else 0.0, "n_a": len(a), "n_b": len(b)}


def cross_correlation(x: np.ndarray, y: np.ndarray, max_lag: int) -> tuple[float, int]:
    """Peak normalised cross-correlation of two series over lags −max_lag..max_lag (positive lag: y follows x). Series are
    detrended; returns (peak value, lag in samples)."""
    x = np.asarray(x, dtype=float) - np.mean(x)
    y = np.asarray(y, dtype=float) - np.mean(y)
    nx, ny = float(np.linalg.norm(x)), float(np.linalg.norm(y))
    if nx < 1e-12 or ny < 1e-12 or len(x) <= max_lag + 2:
        return 0.0, 0
    best, lag_best = 0.0, 0
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            c = float(np.dot(x[: len(x) - lag], y[lag:]))
        else:
            c = float(np.dot(x[-lag:], y[: len(y) + lag]))
        c /= nx * ny
        if abs(c) > abs(best):
            best, lag_best = c, lag
    return best, lag_best


def predictive_gain(x: np.ndarray, y: np.ndarray, lag: int, order: int = 3) -> float:
    """Granger-style improvement: fraction of the variance of y(t) left unexplained by y's own past that is explained when the
    past of x (lagged by ``lag`` samples) is added (linear least squares). 0 = no improvement, 1 = all explained."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(y)
    start = order + max(lag, 1)
    if n < start + 10:
        return 0.0
    rows_y = np.stack([y[start - k - 1: n - k - 1] for k in range(order)], axis=1)
    rows_x = np.stack([x[start - lag - k: n - lag - k] for k in range(order)], axis=1)
    target = y[start:n]
    base = np.hstack([rows_y, np.ones((len(target), 1))])
    full = np.hstack([base, rows_x])
    rb = target - base @ np.linalg.lstsq(base, target, rcond=None)[0]
    rf = target - full @ np.linalg.lstsq(full, target, rcond=None)[0]
    vb = float((rb ** 2).sum())
    return float(max(0.0, (vb - float((rf ** 2).sum())) / vb)) if vb > 1e-18 else 0.0


def bh_adjust(p: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values (q-values) of a family of tests; NaN p-values stay NaN and are not counted."""
    p = np.asarray(p, dtype=float)
    q = np.full(p.shape, np.nan)
    ok = np.isfinite(p)
    if not ok.any():
        return q
    idx = np.where(ok)[0]
    order = idx[np.argsort(p[idx])]
    m = len(order)
    adj = p[order] * m / (np.arange(m) + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    q[order] = np.clip(adj, 0.0, 1.0)
    return q


def design_note(n_pairs: int, alpha: float = 0.05, power: float = 0.8) -> dict[str, Any]:
    """What a paired design with ``n_pairs`` seeds can resolve: the smallest p-value the sign-flip permutation test can give, and
    the smallest standardised paired effect (d_z) detectable with the given power at the given (two-sided) level, by the normal
    approximation (d = (z_{1-alpha/2} + z_power) / sqrt(n)). Used to state why a number of seeds was chosen."""
    from statistics import NormalDist
    nd = NormalDist()
    d_min = (nd.inv_cdf(1 - alpha / 2) + nd.inv_cdf(power)) / math.sqrt(max(n_pairs, 1))
    min_p = 2.0 / (2 ** n_pairs) if n_pairs <= 12 else 1.0 / 4097.0
    return {"n_pairs": n_pairs, "min_attainable_p": min_p, "min_detectable_dz": d_min, "alpha": alpha, "power": power,
            "reading": f"with {n_pairs} paired seeds an effect of about {d_min:.2f} (standardised, paired) is detectable with {power:.0%} power at the {alpha:g} level; "
                       "smaller true effects are expected to be missed, so 'no detectable effect' is not 'no effect'"}
