"""Sample-size arithmetic for the pre-registration (paired designs, two-sided alpha). Pure functions; nothing here reads a result."""

from __future__ import annotations

import math

from scipy import stats as sps


def sd_upper(sd: float, df: int, conf: float = 0.95) -> float:
    """One-sided upper confidence bound of a standard deviation estimated with ``df`` degrees of freedom (chi-square). A planning value that does not
    trust a small exploratory sample's spread."""
    if df < 1 or sd < 0:
        raise ValueError("df >= 1 and sd >= 0 required")
    return sd * math.sqrt(df / sps.chi2.ppf(1 - conf, df))


def sample_size_paired(sd: float, delta: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """Pairs needed to detect a mean paired difference ``delta`` with spread ``sd`` (t-based, iterated from the normal approximation)."""
    if sd <= 0 or delta <= 0:
        raise ValueError("sd > 0 and delta > 0 required")
    n = max(2, math.ceil(((sps.norm.ppf(1 - alpha / 2) + sps.norm.ppf(power)) * sd / delta) ** 2))
    for _ in range(50):
        df = n - 1
        need = math.ceil(((sps.t.ppf(1 - alpha / 2, df) + sps.t.ppf(power, df)) * sd / delta) ** 2)
        need = max(2, need)
        if need == n:
            break
        n = need
    return n


def minimal_detectable_difference(sd: float, n: int, alpha: float = 0.05, power: float = 0.8) -> float:
    df = n - 1
    return float((sps.t.ppf(1 - alpha / 2, df) + sps.t.ppf(power, df)) * sd / math.sqrt(n))
