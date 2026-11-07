"""The small statistics of the SBS comparison: a paired t interval over independent worlds and the Holm correction."""

from __future__ import annotations

import numpy as np
from scipy import stats


def paired_t(d: list[float]) -> dict:
    a = np.asarray(d, dtype=float)
    n = len(a)
    m = float(a.mean())
    if n < 2:
        return {"n": n, "mean": m, "sd": None, "ci95": [-np.inf, np.inf], "p": 1.0}
    sd = float(a.std(ddof=1))
    se = sd / np.sqrt(n)
    t = float(stats.t.ppf(0.975, n - 1))
    p = 1.0 if se == 0 and m == 0 else (0.0 if se == 0 else float(2 * stats.t.sf(abs(m / se), n - 1)))
    return {"n": n, "mean": m, "sd": sd, "ci95": [m - t * se, m + t * se], "p": p}


def holm(p: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (monotone, capped at 1)."""
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    run = 0.0
    for rank, idx in enumerate(order):
        run = max(run, (m - rank) * p[idx])
        adj[idx] = min(1.0, run)
    return adj.tolist()
