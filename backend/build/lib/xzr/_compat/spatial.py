"""``scipy.spatial.cKDTree.query(x, k)`` by exact brute force (chunked), for the world generator on iOS. Neighbours
are sorted by Euclidean distance as cKDTree returns them; the only possible difference is the order of exactly equal
distances, which the generator's continuous random points do not produce (checked in test_compat.py)."""

from __future__ import annotations

import numpy as np


class cKDTree:  # noqa: N801
    def __init__(self, data):
        self.data = np.asarray(data, dtype=np.float64)

    def query(self, x, k: int = 1):
        x = np.asarray(x, dtype=np.float64)
        n = len(self.data)
        k = min(k, n)
        dist = np.empty((len(x), k))
        idx = np.empty((len(x), k), dtype=np.int64)
        for a in range(0, len(x), 256):
            b = min(a + 256, len(x))
            d2 = ((x[a:b, None, :] - self.data[None, :, :]) ** 2).sum(-1)
            part = np.argpartition(d2, k - 1, axis=1)[:, :k] if k < n else np.tile(np.arange(n), (b - a, 1))
            pd = np.take_along_axis(d2, part, 1)
            o = np.lexsort((part, pd), axis=1)
            idx[a:b] = np.take_along_axis(part, o, 1)
            dist[a:b] = np.sqrt(np.take_along_axis(pd, o, 1))
        return dist, idx
