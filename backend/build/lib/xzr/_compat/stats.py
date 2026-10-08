"""``scipy.stats.wasserstein_distance`` for unweighted 1-D samples — the same algorithm as scipy's ``_cdf_distance``
with p=1."""

from __future__ import annotations

import numpy as np


def wasserstein_distance(u_values, v_values) -> float:
    u_values = np.asarray(u_values, dtype=float)
    v_values = np.asarray(v_values, dtype=float)
    if u_values.size == 0 or v_values.size == 0:
        raise ValueError("Distribution can't be empty.")
    u_sorter = np.argsort(u_values)
    v_sorter = np.argsort(v_values)
    all_values = np.concatenate((u_values, v_values))
    all_values.sort(kind="mergesort")
    deltas = np.diff(all_values)
    u_cdf = u_values[u_sorter].searchsorted(all_values[:-1], "right") / u_values.size
    v_cdf = v_values[v_sorter].searchsorted(all_values[:-1], "right") / v_values.size
    return float(np.vecdot(np.abs(u_cdf - v_cdf), deltas))
