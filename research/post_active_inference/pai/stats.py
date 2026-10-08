"""Statistics: descriptive summaries with bootstrap CIs, paired sign-flip tests (reusing the runtime's
``sign_matrix``: exact for ≤ 14 pairs, seeded Monte Carlo above), effect sizes, Holm correction, three-way status
(the DETECTED / EQUIVALENT / UNRESOLVED logic of ``xzr.experiments.history.assess``) and threshold estimation with
bootstrap uncertainty."""
from __future__ import annotations

import numpy as np
from xzr.experiments.escalation.stats import sign_matrix

BOOT = 2000


def _clean(x) -> np.ndarray:
    a = np.asarray([v for v in x if v is not None], float)
    return a[np.isfinite(a)]


def bootstrap_ci(x, stat=np.mean, n: int = BOOT, seed: int = 0, level: float = 0.95) -> tuple[float, float] | None:
    a = _clean(x)
    if len(a) < 2:
        return None
    rng = np.random.default_rng(seed)
    b = np.array([stat(a[rng.integers(0, len(a), len(a))]) for _ in range(n)])
    lo, hi = np.quantile(b, [(1 - level) / 2, 1 - (1 - level) / 2])
    return float(lo), float(hi)


def describe(x) -> dict:
    a = _clean(x)
    if len(a) == 0:
        return {"n": 0, "mean": None, "median": None, "sd": None, "ci95": None}
    return {"n": int(len(a)), "mean": float(a.mean()), "median": float(np.median(a)),
            "sd": float(a.std(ddof=1)) if len(a) > 1 else None, "ci95": bootstrap_ci(a)}


def sign_flip_p(d) -> float:
    """Two-sided paired sign-flip p-value of the mean difference."""
    a = _clean(d)
    if len(a) == 0 or np.allclose(a, 0):
        return 1.0
    S = sign_matrix(len(a)).astype(float)
    stats = np.abs(S @ a) / len(a)
    return float((stats >= abs(a.mean()) - 1e-12).mean())


def cohen_dz(d) -> float | None:
    a = _clean(d)
    if len(a) < 2:
        return None
    sd = a.std(ddof=1)
    if sd == 0:
        return None if a.mean() == 0 else float(np.sign(a.mean()) * np.inf)
    return float(a.mean() / sd)


def holm(p: list[float]) -> list[float]:
    p = np.asarray(p, float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * p[i]))
        adj[i] = run
    return adj.tolist()


def paired(d, margin: float) -> dict:
    """Paired difference summary: mean, CI, p, dz, and the equivalence check (95 % bootstrap CI within ±margin)."""
    a = _clean(d)
    ci = bootstrap_ci(a)
    return {"n": int(len(a)), "mean": float(a.mean()) if len(a) else None, "ci95": ci, "p": sign_flip_p(a),
            "dz": cohen_dz(a), "within_margin": bool(ci is not None and -margin <= ci[0] and ci[1] <= margin)}


def crossing(levels: np.ndarray, curve: np.ndarray, threshold: float) -> float | None:
    """First severity at which a curve (mean score per severity, decreasing in the usual case) falls below the
    threshold, by linear interpolation between grid points. None = never below; levels[0] if already below."""
    for i in range(len(levels)):
        if np.isfinite(curve[i]) and curve[i] < threshold:
            if i == 0:
                return float(levels[0])
            j = i - 1
            while j >= 0 and not np.isfinite(curve[j]):
                j -= 1
            if j < 0:
                return float(levels[i])
            c0, c1 = curve[j], curve[i]
            return float(levels[j] + (c0 - threshold) / (c0 - c1) * (levels[i] - levels[j])) if c0 != c1 else float(levels[i])
    return None


def threshold(levels, per_seed: np.ndarray, thr: float, n: int = BOOT, seed: int = 0) -> dict:
    """Severity at which the across-seed mean score crosses ``thr``; bootstrap over seeds for its uncertainty; the
    share of seeds whose own curve crosses (robustness) and the spread of per-seed crossings."""
    levels = np.asarray(levels, float)
    M = np.asarray(per_seed, float)  # seeds × levels (NaN = missing)
    if M.size == 0:
        return {"estimate": None}
    with np.errstate(invalid="ignore"):
        mean = np.nanmean(M, 0)
    est = crossing(levels, mean, thr)
    rng = np.random.default_rng(seed)
    boots = []
    never = 0
    for _ in range(n):
        with np.errstate(invalid="ignore"):
            c = crossing(levels, np.nanmean(M[rng.integers(0, len(M), len(M))], 0), thr)
        if c is None:
            never += 1
        else:
            boots.append(c)
    per = [crossing(levels, row, thr) for row in M]
    crossed = [c for c in per if c is not None]
    return {"estimate": est,
            "ci95": [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))] if len(boots) >= 20 else None,
            "boot_never_share": never / n,
            "seeds_crossing_share": len(crossed) / len(per) if per else None,
            "per_seed_iqr": [float(np.quantile(crossed, 0.25)), float(np.quantile(crossed, 0.75))] if len(crossed) >= 2 else None,
            "curve": [None if not np.isfinite(v) else float(v) for v in mean]}
