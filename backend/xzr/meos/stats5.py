"""Small statistics for the fifth-stage experiments: effect sizes, confidence intervals, paired and unpaired non-parametric comparisons, proportions.

With few seeds a p value alone is not a claim: every comparison here returns the effect size and an interval beside it, and ``describe`` words a result without the word
"significant" (the document's rule: a small number of seeds supports at most a description of what was seen)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats as sps


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """The Wilson score interval of a proportion (well behaved at 0 and n)."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))


def proportion(k: int, n: int) -> dict[str, Any]:
    return {"k": k, "n": n, "p": round(k / n, 4) if n else None, "wilson95": list(wilson(k, n))}


def cohens_h(p1: float, p2: float) -> float:
    """Effect size of a difference between two proportions."""
    return round(2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2)), 4)


def cliffs_delta(a: list[float], b: list[float]) -> float:
    """Probability that a draw from ``a`` exceeds one from ``b`` minus the converse (−1..1); no distributional assumption."""
    if not a or not b:
        return float("nan")
    gt = sum(1 for x in a for y in b if x > y)
    lt = sum(1 for x in a for y in b if x < y)
    return round((gt - lt) / (len(a) * len(b)), 4)


def bootstrap_ci(x: list[float], fn=np.mean, b: int = 4000, seed: int = 7) -> tuple[float, float]:
    if len(x) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    arr = np.asarray(x, dtype=float)
    est = [fn(rng.choice(arr, len(arr))) for _ in range(b)]
    return (round(float(np.percentile(est, 2.5)), 4), round(float(np.percentile(est, 97.5)), 4))


def compare_proportions(k1: int, n1: int, k2: int, n2: int) -> dict[str, Any]:
    """Two proportions: each with its Wilson interval, the effect size h, and Fisher's exact test (exact, so valid for small n)."""
    odds, p = sps.fisher_exact([[k1, n1 - k1], [k2, n2 - k2]])
    return {"a": proportion(k1, n1), "b": proportion(k2, n2), "cohens_h": cohens_h(k1 / n1, k2 / n2) if n1 and n2 else None, "fisher_exact_p": round(float(p), 5)}


def compare_paired(a: list[float], b: list[float]) -> dict[str, Any]:
    """Paired values (same seeds): the median difference with a bootstrap interval, the Wilcoxon signed-rank test (when there is any nonzero difference) and the share of pairs in which b exceeds a."""
    d = np.asarray(b, dtype=float) - np.asarray(a, dtype=float)
    out: dict[str, Any] = {"n": len(d), "median_difference": round(float(np.median(d)), 4) if len(d) else None, "bootstrap95_of_median_difference": list(bootstrap_ci(list(d), np.median))}
    out["share_b_greater"] = round(float(np.mean(d > 0)), 4) if len(d) else None
    nz = d[d != 0]
    if len(nz) >= 5:
        try:
            out["wilcoxon_p"] = round(float(sps.wilcoxon(nz).pvalue), 5)
        except ValueError:
            out["wilcoxon_p"] = None
    else:
        out["wilcoxon_p"] = None
        out["note"] = "fewer than 5 nonzero differences: no test"
    return out


def compare_unpaired(a: list[float], b: list[float]) -> dict[str, Any]:
    """Two samples: Cliff's delta, the Mann-Whitney U test, and the medians."""
    out: dict[str, Any] = {"n": [len(a), len(b)], "median": [round(float(np.median(a)), 4) if a else None, round(float(np.median(b)), 4) if b else None], "cliffs_delta": cliffs_delta(a, b)}
    if len(a) >= 3 and len(b) >= 3 and (len(set(a)) + len(set(b)) > 2):
        try:
            out["mann_whitney_p"] = round(float(sps.mannwhitneyu(a, b).pvalue), 5)
        except ValueError:
            out["mann_whitney_p"] = None
    else:
        out["mann_whitney_p"] = None
    return out


def describe(effect: float | None, n: int) -> str:
    """Words for an effect size without a verdict: how large it looks and how few observations it rests on."""
    if effect is None or (isinstance(effect, float) and math.isnan(effect)):
        return "no effect size"
    mag = abs(effect)
    size = "large" if mag >= 0.8 else "moderate" if mag >= 0.5 else "small" if mag >= 0.2 else "negligible"
    return f"{size} ({effect:+.2f}) on {n} observations" + ("; few observations: a description, not a result" if n < 10 else "")
