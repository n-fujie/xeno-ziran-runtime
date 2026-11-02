"""Statistics for single-case and small-sample designs, without the assumption that repeated observations of one subject are independent.

* ``randomization_test``: a randomisation test of a difference between two conditions: the p-value is the share of re-assignments of the condition labels (within blocks when the design randomised within blocks) that give a
  difference at least as large as the observed one. It is valid *because of the randomisation actually done*; it makes no assumption of independent errors. If the assignment was not randomised the result is labelled
  ``descriptive: assignment not randomised`` and no p-value is presented as inferential.
* ``holm``: Holm's step-down correction for the family of confirmatory tests.
* ``lag1_autocorrelation``: a check on the series (a warning, not a correction).
Nothing here compares against or favours any theory; if a conventional explanation fits the same observations, that is reported by the analysis that uses these functions, not decided here."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def lag1_autocorrelation(y: list[float]) -> float | None:
    a = np.asarray(y, float)
    if len(a) < 4 or float(a.std()) == 0.0:
        return None
    a = a - a.mean()
    return float((a[:-1] * a[1:]).sum() / (a * a).sum())


def randomization_test(values: list[float], labels: list[str], *, a: str, b: str, randomized: bool, n_perm: int = 10000, seed: int = 0, blocks: list[int] | None = None) -> dict[str, Any]:
    y = np.asarray(values, float)
    lab = np.asarray(labels)
    ia, ib = lab == a, lab == b
    if ia.sum() < 2 or ib.sum() < 2:
        return {"method": "randomization-test", "n_a": int(ia.sum()), "n_b": int(ib.sum()), "p": None, "effect": None, "inferential": False, "reason": "fewer than two observations in a condition"}
    obs = float(y[ib].mean() - y[ia].mean())
    r1 = lag1_autocorrelation(list(y))
    out: dict[str, Any] = {"method": "randomization-test", "statistic": "mean(b) - mean(a)", "a": a, "b": b, "n_a": int(ia.sum()), "n_b": int(ib.sum()), "effect": obs, "lag1_autocorrelation": r1,
                           "autocorrelation_warning": bool(r1 is not None and abs(r1) > 0.3 and not randomized)}
    if not randomized:
        return {**out, "p": None, "inferential": False, "reason": "descriptive: the assignment was not randomised, so a re-assignment distribution does not describe how the data were produced"}
    rng = np.random.default_rng(seed)
    idx = np.where(ia | ib)[0]
    yy, ll = y[idx], lab[idx]
    bl = np.zeros(len(idx), int) if blocks is None else np.asarray(blocks)[idx]
    count = 0
    for _ in range(n_perm):
        perm = ll.copy()
        for g in np.unique(bl):
            m = np.where(bl == g)[0]
            perm[m] = ll[m][rng.permutation(len(m))]
        d = yy[perm == b].mean() - yy[perm == a].mean()
        if abs(d) >= abs(obs) - 1e-12:
            count += 1
    return {**out, "p": (count + 1) / (n_perm + 1), "n_perm": n_perm, "seed": seed, "inferential": True, "blocks": blocks is not None}


def holm(pvals: dict[str, float | None]) -> dict[str, dict[str, Any]]:
    """Holm-adjusted p-values for the tests that have one; a test without a p-value stays without (it is not given 1.0 or dropped)."""
    items = sorted(((k, v) for k, v in pvals.items() if v is not None), key=lambda kv: kv[1])
    m, adj, run = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        adj[k] = run
    return {k: ({"p": v, "p_holm": adj[k]} if v is not None else {"p": None, "p_holm": None}) for k, v in pvals.items()}


def cohen_d(y_a: list[float], y_b: list[float]) -> float | None:
    a, b = np.asarray(y_a, float), np.asarray(y_b, float)
    if len(a) < 2 or len(b) < 2:
        return None
    sp = math.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    return None if sp == 0 else float((b.mean() - a.mean()) / sp)


# ------------------------------------------------------------------------------------------------ paired designs over independent units (worlds, seeds)
def bootstrap_ci(x: list[float], *, level: float = 0.95, n: int = 5000, seed: int = 0) -> tuple[float, float] | None:
    a = np.asarray(x, float)
    if len(a) < 2:
        return None
    rng = np.random.default_rng(seed)
    m = a[rng.integers(0, len(a), size=(n, len(a)))].mean(axis=1)
    lo, hi = np.quantile(m, [(1 - level) / 2, 1 - (1 - level) / 2])
    return float(lo), float(hi)


def paired_sign_flip(diffs: list[float], *, n_perm: int = 20000, seed: int = 0) -> dict[str, Any]:
    """A paired comparison across independent units (e.g. worlds): the p-value is the share of random sign flips of the within-unit differences whose mean is at least as extreme. Valid when the units are independent and
    the condition order within a unit was exchangeable (it is, by construction, in these experiments). Zero differences are kept (they pull the mean towards 0, they are not dropped)."""
    d = np.asarray(diffs, float)
    if len(d) < 3:
        return {"method": "paired-sign-flip", "n": int(len(d)), "p": None, "mean_diff": None, "ci95": None, "inferential": False, "reason": "fewer than three units"}
    obs = float(d.mean())
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(n_perm, len(d)))
    perm = np.abs((signs * d).mean(axis=1))
    p = float((np.sum(perm >= abs(obs) - 1e-12) + 1) / (n_perm + 1))
    sd = float(d.std(ddof=1))
    return {"method": "paired-sign-flip", "n": int(len(d)), "mean_diff": obs, "sd_diff": sd, "dz": None if sd == 0 else obs / sd, "ci95": bootstrap_ci(list(d), seed=seed), "p": p, "n_perm": n_perm, "seed": seed, "inferential": True}


def equivalence(diffs: list[float], margin: float, *, seed: int = 0) -> dict[str, Any]:
    """Equivalence within +-margin: supported when the 90% bootstrap interval of the mean paired difference lies inside the margin (a TOST-like criterion). Failing it is not evidence of a difference."""
    ci = bootstrap_ci(diffs, level=0.90, seed=seed)
    if ci is None:
        return {"method": "equivalence", "margin": margin, "supported": None, "ci90": None, "mean_diff": None}
    return {"method": "equivalence", "margin": margin, "ci90": ci, "mean_diff": float(np.mean(diffs)), "supported": bool(ci[0] > -margin and ci[1] < margin)}


def upper_bound(k: int, n: int, alpha: float = 0.05) -> float | None:
    """One-sided exact (Clopper-Pearson) upper confidence bound of a proportion k/n at level 1-alpha."""
    if n <= 0:
        return None
    from scipy.stats import beta

    return 1.0 if k >= n else float(beta.ppf(1 - alpha, k + 1, n - k))
