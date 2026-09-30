"""Graph-level operational shape descriptors (pure functions over runtime arrays).

These are descriptors of operational shape — reachability, closure, fragmentation, bottlenecks,
asymmetry — not interpretations of what the shapes are.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.sparse import csgraph

from ..runtime.state import State


def gini(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, dtype=np.float64))
    n = len(x)
    s = x.sum()
    if n == 0 or s <= 0:
        return 0.0
    cum = np.cumsum(x)
    return float((n + 1 - 2 * (cum / s).sum()) / n)


def top_share(x: np.ndarray, frac: float = 0.01) -> float:
    s = float(np.sum(x))
    if s <= 0:
        return 0.0
    k = max(1, int(len(x) * frac))
    return float(np.sort(x)[-k:].sum() / s)


def transition_graph(state: State) -> sp.csr_matrix:
    """Directed graph of currently reachable transitions."""
    m = state.reachable_mask()
    n = state.n
    return sp.csr_matrix((np.ones(int(m.sum())), (state.src[m], state.dst[m])), shape=(n, n))


def horizon_reach(g: sp.csr_matrix, sources: np.ndarray, hops: int) -> np.ndarray:
    """Configurations reachable from ``sources`` within ``hops`` transitions (bool mask)."""
    n = g.shape[0]
    reached = np.zeros(n, dtype=bool)
    reached[sources] = True
    frontier = reached.copy()
    gt = g.T.tocsr()
    for _ in range(hops):
        nxt = (gt @ frontier.astype(np.float64)) > 0
        nxt &= ~reached
        if not nxt.any():
            break
        reached |= nxt
        frontier = nxt
    return reached


def closure_reach(g: sp.csr_matrix, sources: np.ndarray) -> np.ndarray:
    """Transitive reachability from a set (bool mask) via a virtual super-source."""
    n = g.shape[0]
    reached = np.zeros(n, dtype=bool)
    if len(sources) == 0:
        return reached
    row = sp.csr_matrix((np.ones(len(sources)), (np.zeros(len(sources), dtype=np.int64), sources)), shape=(1, n))
    aug = sp.vstack([sp.hstack([g, sp.csr_matrix((n, 1))]), sp.hstack([row, sp.csr_matrix((1, 1))])]).tocsr()
    order = csgraph.breadth_first_order(aug, n, directed=True, return_predecessors=False)
    order = order[order < n]
    reached[order] = True
    return reached


def loops(state: State, load_min: float = 0.05) -> dict:
    """Strongly connected structure of the recent-flow graph: loops that retain themselves."""
    n = state.n
    m = state.alive & (state.load > load_min)
    g = sp.csr_matrix((np.ones(int(m.sum())), (state.src[m], state.dst[m])), shape=(n, n))
    k, lab = csgraph.connected_components(g, directed=True, connection="strong")
    size = np.bincount(lab, minlength=k)
    in_loop = size[lab] >= 2
    nontrivial = size[size >= 2]
    return {"in_loop": in_loop, "n_loops": int(len(nontrivial)),
            "largest_loop": int(nontrivial.max()) if len(nontrivial) else 0,
            "loop_fraction": float(in_loop.mean())}


def fragmentation(state: State) -> dict:
    n = state.n
    m = state.alive
    g = sp.csr_matrix((np.ones(int(m.sum())), (state.src[m], state.dst[m])), shape=(n, n))
    k, lab = csgraph.connected_components(g, directed=True, connection="weak")
    size = np.bincount(lab, minlength=k)
    return {"components": int(k), "components_ge5": int((size >= 5).sum()),
            "largest_component": float(size.max() / n), "fragmentation": float(1 - size.max() / n)}


def bottlenecks(g: sp.csr_matrix, sources: np.ndarray, rng: np.random.Generator, targets_per_source: int = 64
                ) -> np.ndarray:
    """Sampled shortest-path visit counts (approximate betweenness). Returns visits per configuration."""
    n = g.shape[0]
    visits = np.zeros(n)
    if len(sources) == 0:
        return visits
    _, pred = csgraph.shortest_path(g, method="D", directed=True, unweighted=True, indices=sources,
                                    return_predecessors=True)
    for row, s in enumerate(sources):
        p = pred[row]
        reach = np.flatnonzero(p >= 0)
        if len(reach) == 0:
            continue
        for tgt in rng.choice(reach, size=min(targets_per_source, len(reach)), replace=False):
            v = p[tgt]
            while v >= 0 and v != s:
                visits[v] += 1
                v = p[v]
    return visits


def asymmetry(state: State) -> dict:
    """Transition asymmetry: how unevenly flow runs along reciprocal pairs, and how much flow is one-way."""
    m = np.flatnonzero(state.alive)
    n = np.int64(state.n)
    key = state.src[m].astype(np.int64) * n + state.dst[m]
    rev = state.dst[m].astype(np.int64) * n + state.src[m]
    o = np.argsort(key)
    ks = key[o]
    pos = np.clip(np.searchsorted(ks, rev), 0, len(ks) - 1)
    has = ks[pos] == rev if len(ks) else np.zeros(0, dtype=bool)
    load = state.load[m]
    total = float(load.sum())
    if total <= 0:
        return {"asymmetry": 0.0, "one_way_share": 0.0, "reciprocal_pairs": int(has.sum() // 2)}
    lr = np.zeros_like(load)
    lr[has] = load[o[pos[has]]]
    first = has & (key < rev)
    num = np.abs(load[first] - lr[first]).sum()
    den = (load[first] + lr[first]).sum()
    return {"asymmetry": float(num / den) if den > 0 else 0.0,
            "one_way_share": float(load[~has].sum() / total), "reciprocal_pairs": int(first.sum())}
