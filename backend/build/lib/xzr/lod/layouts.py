"""Projections of configurations into 2-D view spaces. Every projection is optional and replaceable;
none is ontologically primary. Coordinates are normalized to a [0, 1000] box (geo stays lon/lat)."""

from __future__ import annotations

import numpy as np

from .hierarchy import Hierarchy

BOX = 1000.0
LAYOUTS = ("network", "shape", "address", "geo")


def normalize(xy: np.ndarray, margin: float = 0.03) -> np.ndarray:
    xy = np.asarray(xy, dtype=np.float64)
    ok = np.isfinite(xy).all(1)
    out = np.full_like(xy, np.nan)
    if not ok.any():
        return out.astype(np.float32)
    lo, hi = xy[ok].min(0), xy[ok].max(0)
    span = max(float((hi - lo).max()), 1e-9)
    center = (lo + hi) / 2
    out[ok] = (xy[ok] - center) / span * (BOX * (1 - 2 * margin)) + BOX / 2
    return out.astype(np.float32)


def hilbert_d2xy(side: int, d: np.ndarray) -> np.ndarray:
    """Vectorized Hilbert curve index → (x, y) on a side×side grid (side a power of two)."""
    d = d.astype(np.int64).copy()
    x = np.zeros_like(d)
    y = np.zeros_like(d)
    s = 1
    while s < side:
        rx = 1 & (d // 2)
        ry = 1 & (d ^ rx)
        swap = ry == 0
        flip = swap & (rx == 1)
        x[flip] = s - 1 - x[flip]
        y[flip] = s - 1 - y[flip]
        x[swap], y[swap] = y[swap].copy(), x[swap].copy()
        x += s * rx
        y += s * ry
        d //= 4
        s *= 2
    return np.stack([x, y], 1)


def address_layout(h: Hierarchy) -> np.ndarray:
    """Configurations ordered by hierarchical address along a Hilbert curve: clusters become blocks."""
    n = h.n
    side = 1 << int(np.ceil(np.log2(max(2.0, np.sqrt(n)))))
    rank = np.empty(n, dtype=np.int64)
    rank[h.order] = np.arange(n)
    d = (rank * (side * side) // max(n, 1)).astype(np.int64)
    return normalize(hilbert_d2xy(side, d) + 0.5, margin=0.02)


def network_layout(h: Hierarchy, latent: np.ndarray | None, seed: int) -> np.ndarray:
    """Topology layout: generator latent coordinates if available, otherwise a recursive-bisection layout."""
    if latent is not None:
        return normalize(latent)
    rng = np.random.default_rng(seed)
    n = h.n
    xy = np.zeros((n, 2))
    # place each leaf-path cell as a rectangle split alternately along x / y
    for i in range(n):
        p = int(h.path[i])
        x0, y0, w, hgt = 0.0, 0.0, 1.0, 1.0
        for b in range(8, -1, -1):
            bit = (p >> b) & 1
            if w >= hgt:
                w /= 2
                x0 += bit * w
            else:
                hgt /= 2
                y0 += bit * hgt
        xy[i] = (x0 + rng.uniform(0.1, 0.9) * w, y0 + rng.uniform(0.1, 0.9) * hgt)
    return normalize(xy)


def geo_layout(geo: np.ndarray) -> np.ndarray:
    return geo.astype(np.float32)
