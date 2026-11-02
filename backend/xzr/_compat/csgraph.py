"""The subset of ``scipy.sparse.csgraph`` used by ``shapes/metrics.py``, on the CSR stand-in.

``breadth_first_order`` and ``connected_components`` are exact (callers use only membership and component sizes).
``shortest_path`` (unweighted) is a breadth-first search: distances are exact; where several shortest paths exist the
predecessor chosen may differ from scipy's Dijkstra tie-breaking, which affects only the sampled bottleneck
observation metric (see test_compat.py)."""

from __future__ import annotations

import numpy as np

from .sparse import csr_matrix


def _expand(g: csr_matrix, frontier: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """All out-neighbours of ``frontier`` in frontier order (each node's neighbours in CSR order), with the node
    each was reached from — the order a queue-based search would visit them in."""
    starts = g.indptr[frontier]
    lens = g.indptr[frontier + 1] - starts
    total = int(lens.sum())
    if total == 0:
        return np.empty(0, dtype=np.intp), np.empty(0, dtype=np.intp)
    offs = np.repeat(starts - (np.cumsum(lens) - lens), lens) + np.arange(total)
    return g.indices[offs].astype(np.intp), np.repeat(frontier, lens)


def _bfs(g: csr_matrix, source: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Level-synchronous breadth-first search, vectorised per level. Returns (visit order, distance, predecessor)
    identical to a FIFO-queue search that takes each node's neighbours in CSR order: a node is reached from the
    first frontier node (in visit order) that has it as a neighbour, and is visited in order of that discovery."""
    n = g.shape[0]
    dist = np.full(n, -1, dtype=np.intp)
    pred = np.full(n, -9999, dtype=np.intp)
    dist[source] = 0
    frontier = np.array([source], dtype=np.intp)
    order = [frontier]
    level = 0
    while frontier.size:
        level += 1
        nbrs, parents = _expand(g, frontier)
        fresh = dist[nbrs] < 0
        nbrs, parents = nbrs[fresh], parents[fresh]
        if not nbrs.size:
            break
        u, first = np.unique(nbrs, return_index=True)
        seq = np.argsort(first, kind="stable")  # discovery order
        frontier = u[seq]
        dist[frontier] = level
        pred[frontier] = parents[first[seq]]
        order.append(frontier)
    return np.concatenate(order), dist, pred


def breadth_first_order(g: csr_matrix, i_start: int, directed: bool = True, return_predecessors: bool = True):
    order, _, _ = _bfs(g, int(i_start))
    out = order.astype(np.int32)
    return out if not return_predecessors else (out, None)


def connected_components(g: csr_matrix, directed: bool = True, connection: str = "weak"):
    n = g.shape[0]
    if connection == "weak" or not directed:
        # minimum-label propagation with pointer jumping: each node ends labelled with the smallest index in its
        # (undirected) component, as a union-find keeping the smaller root would
        r, c, _ = g._coo()
        r, c = r.astype(np.intp), c.astype(np.intp)
        labels = np.arange(n, dtype=np.intp)
        while True:
            new = labels.copy()
            np.minimum.at(new, r, labels[c])
            np.minimum.at(new, c, labels[r])
            while True:
                jumped = new[new]
                if np.array_equal(jumped, new):
                    break
                new = jumped
            if np.array_equal(new, labels):
                break
            labels = new
        _, out = np.unique(labels, return_inverse=True)
        return int(out.max() + 1) if n else 0, out.astype(np.int32)
    # strong: iterative Tarjan
    index = np.full(n, -1)
    low = np.zeros(n, dtype=np.intp)
    on = np.zeros(n, dtype=bool)
    labels = np.full(n, -1, dtype=np.int32)
    stack: list[int] = []
    counter = comp = 0
    for root in range(n):
        if index[root] >= 0:
            continue
        work = [(root, g.indptr[root])]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on[root] = True
        while work:
            u, pos = work[-1]
            end = g.indptr[u + 1]
            if pos < end:
                work[-1] = (u, pos + 1)
                v = int(g.indices[pos])
                if index[v] < 0:
                    index[v] = low[v] = counter
                    counter += 1
                    stack.append(v)
                    on[v] = True
                    work.append((v, g.indptr[v]))
                elif on[v]:
                    low[u] = min(low[u], index[v])
            else:
                work.pop()
                if work:
                    p = work[-1][0]
                    low[p] = min(low[p], low[u])
                if low[u] == index[u]:
                    while True:
                        w = stack.pop()
                        on[w] = False
                        labels[w] = comp
                        if w == u:
                            break
                    comp += 1
    return comp, labels


def shortest_path(g: csr_matrix, method: str = "D", directed: bool = True, unweighted: bool = True,
                  indices=None, return_predecessors: bool = True):
    srcs = np.atleast_1d(np.asarray(indices))
    n = g.shape[0]
    dist = np.full((len(srcs), n), np.inf)
    pred = np.full((len(srcs), n), -9999, dtype=np.int32)
    for row, s in enumerate(srcs.tolist()):
        _, d, p = _bfs(g, int(s))
        reached = d >= 0
        dist[row, reached] = d[reached]
        pred[row] = p
    return (dist, pred) if return_predecessors else dist
