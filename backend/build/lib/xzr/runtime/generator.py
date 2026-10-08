"""Seeded generators of initial operational structure.

``latent_geometric``: configurations are placed in an abstract 2-D latent space with multi-scale
clustering; connections follow latent proximity (k nearest), with partial reciprocity and a fraction
of long-range connections. Parameters are heterogeneous so that different operational shapes can
emerge. Nothing here names what a configuration is.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .._compat import FORCE as _COMPAT

try:  # the iOS app has no scipy: an exact brute-force neighbour query stands in (see _compat/spatial.py)
    if _COMPAT:
        raise ImportError
    from scipy.spatial import cKDTree
except ImportError:
    from .._compat.spatial import cKDTree

from .state import Params, State, allocate


@dataclass
class Generated:
    state: State
    latent: np.ndarray  # (N, 2) in [0, 1] — used only as a layout hint


def _latent_points(rng: np.random.Generator, n: int, groups: int) -> np.ndarray:
    top = rng.uniform(0.12, 0.88, size=(groups, 2))
    subs = []
    for c in top:
        k = int(rng.integers(3, 7))
        subs.append(c + rng.normal(0, 0.07, size=(k, 2)))
    sub = np.concatenate(subs)
    weights = rng.dirichlet(np.full(len(sub), 1.5))
    n_bg = n // 12
    which = rng.choice(len(sub), size=n - n_bg, p=weights)
    spread = rng.uniform(0.012, 0.035, size=len(sub))[which]
    pts = sub[which] + rng.normal(0, 1, size=(n - n_bg, 2)) * spread[:, None]
    bg = rng.uniform(0, 1, size=(n_bg, 2))
    pts = np.concatenate([pts, bg])
    pts = pts[rng.permutation(n)]
    return np.clip(pts, 0.0, 1.0)


def latent_geometric(n: int, seed: int, mean_degree: float = 6.0, long_range: float = 0.08,
                     reciprocity: float = 0.35, groups: int = 6, geo_fraction: float = 0.7,
                     transform_fraction: float = 0.08, capacity: float = 3.0, heterogeneity: float = 0.35,
                     cap_ratio: float = 1.8,
                     params: Params | None = None) -> Generated:
    rng = np.random.default_rng(seed)
    params = params or Params()
    pts = _latent_points(rng, n, groups)

    # proximity connections
    k_near = max(1, int(round(mean_degree * (1 - long_range) / (1 + reciprocity))))
    k_far = min(n - 1, max(k_near + 1, 160))
    _, nb = cKDTree(pts).query(pts, k=k_far + 1)
    src = np.repeat(np.arange(n), k_near)
    dst = nb[:, 1:k_near + 1].reshape(-1)
    back = rng.random(len(src)) < reciprocity
    src, dst = np.concatenate([src, dst[back]]), np.concatenate([dst, src[back]])
    # longer-range connections, distance-biased (rank^-1 among the k_far nearest), plus a few uniform shortcuts,
    # so that coarse topology and latent geometry agree across scales
    m = int(n * mean_degree * long_range)
    m_uniform = m // 5
    ranks = np.arange(k_near + 1, k_far + 1)
    p_rank = 1.0 / ranks
    p_rank /= p_rank.sum()
    a = rng.integers(0, n, m - m_uniform)
    b = nb[a, rng.choice(ranks, size=len(a), p=p_rank)]
    src = np.concatenate([src, a, rng.integers(0, n, m_uniform)])
    dst = np.concatenate([dst, b, rng.integers(0, n, m_uniform)])
    keep = src != dst
    key = np.unique(src[keep].astype(np.int64) * n + dst[keep])
    src, dst = (key // n).astype(np.int32), (key % n).astype(np.int32)
    order = rng.permutation(len(src))
    src, dst = src[order], dst[order]
    e = len(src)

    st = allocate(n, e + max(2048, e // 3), params)
    # smooth random field over latent space: some regions are more excitable than others
    bumps = rng.uniform(0, 1, size=(12, 2))
    amp = rng.normal(0, 1, size=12)
    d2 = ((pts[:, None, :] - bumps[None]) ** 2).sum(-1)
    field_ = (np.exp(-d2 / (2 * 0.12**2)) * amp).sum(1)
    field_ = (field_ - field_.mean()) / (field_.std() + 1e-9)
    st.theta[:] = np.clip(rng.normal(1.0, 0.15, n) * np.exp(heterogeneity * field_), 0.3, 4.0)
    st.cap[:] = np.exp(rng.normal(np.log(cap_ratio), 0.25, n)) * st.theta
    st.retention[:] = np.clip(rng.beta(9, 1.8, n), 0.4, 0.98)
    st.base_mem_decay[:] = st.mem_decay[:] = rng.uniform(0.8, 0.95, n)
    st.base_mem_coupling[:] = st.mem_coupling[:] = rng.choice([-0.25, -0.1, 0.0, 0.1, 0.25], n, p=[0.25, 0.2, 0.2, 0.2, 0.15])
    st.form[:] = rng.integers(0, params.n_forms, n)
    st.diff[:] = rng.exponential(0.3, n)
    has_geo = rng.random(n) < geo_fraction
    st.geo[has_geo, 0] = -170 + 340 * pts[has_geo, 0]
    st.geo[has_geo, 1] = -55 + 125 * (1 - pts[has_geo, 1])

    st.src[:e], st.dst[:e] = src, dst
    w = np.clip(np.exp(rng.normal(np.log(0.5), 0.5, e)), 0.08, 2.5)
    st.weight[:e] = st.base_weight[:e] = w
    st.alive[:e] = True
    tr = rng.random(e) < transform_fraction
    st.transform[:e] = np.where(tr, rng.integers(1, params.n_forms, e), 0)
    st.capacity[:e] = np.exp(rng.normal(np.log(capacity), 0.4, e))
    return Generated(st, pts)
