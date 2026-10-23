"""Intrinsic multi-scale hierarchy: recursive spectral (Fiedler) bisection of the connection graph.

The hierarchy is derived from topology, never from geography. Each configuration receives a leaf path
of ``DEPTH`` bits; cluster levels are prefixes of that path. Addresses read ``m.g.r.l`` with the macro
component 0–7 (3 bits) and each finer component 0–3 (2 bits).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

import numpy as np

from .._compat import FORCE as _COMPAT

try:  # the iOS app has no scipy: a dense symmetric eigensolve stands in for ARPACK (see _compat/linalg.py)
    if _COMPAT:
        raise ImportError
    import scipy.sparse as sp
    from scipy.sparse.linalg import ArpackNoConvergence, eigsh
    _COMPAT_PATH = False
except ImportError:
    from .._compat import sparse as sp  # type: ignore[no-redef]
    from .._compat.linalg import ArpackNoConvergence, eigsh  # type: ignore[assignment]
    _COMPAT_PATH = True
from .._compat import hierarchy_cache as _reference_cache

SCALES = ("macro", "global", "regional", "local", "configuration", "relation")
CLUSTER_DEPTHS = (3, 5, 7, 9)  # bits of the leaf path used by the four cluster scales
DEPTH = CLUSTER_DEPTHS[-1]


def symmetric_adjacency(src: np.ndarray, dst: np.ndarray, n: int) -> sp.csr_matrix:
    a = sp.csr_matrix((np.ones(len(src)), (src, dst)), shape=(n, n))
    a = a + a.T
    a.data[:] = 1.0
    return a.tocsr()


def _fiedler(a: sp.csr_matrix) -> np.ndarray:
    """Second eigenvector of the (self-loop regularized) normalized adjacency."""
    m = a.shape[0]
    deg = np.asarray(a.sum(1)).ravel() + 1.0
    dinv = 1.0 / np.sqrt(deg)
    norm = sp.diags(dinv) @ (a + sp.identity(m)) @ sp.diags(dinv)
    if m <= 400:
        _, vecs = np.linalg.eigh(norm.toarray())
        v = vecs[:, -2]
    else:
        v0 = np.linspace(1.0, 2.0, m)
        try:
            _, vecs = eigsh(norm, k=2, which="LA", tol=1e-4, v0=v0, maxiter=3000)
            v = vecs[:, 0]
        except ArpackNoConvergence as err:
            v = err.eigenvectors[:, 0] if err.eigenvectors.shape[1] else v0
    v = v * dinv
    # deterministic sign
    if np.dot(v, np.arange(m) - m / 2) < 0:
        v = -v
    return v


@dataclass
class Hierarchy:
    path: np.ndarray  # (n,) leaf path, DEPTH bits
    order: np.ndarray  # nodes sorted by (path, fiedler position) — a topological linear order
    labels: list[np.ndarray]  # per cluster scale: compact cluster index for each configuration
    codes: list[np.ndarray]  # per cluster scale: path prefix of each compact cluster
    parents: list[np.ndarray]  # per cluster scale: compact index of the parent cluster (scale-1), -1 for macro
    source: str = "computed"  # how the leaf paths were obtained (see build_hierarchy)

    @property
    def n(self) -> int:
        return int(self.path.shape[0])

    def n_clusters(self, level: int) -> int:
        return int(len(self.codes[level]))

    @staticmethod
    def code_to_address(code: int, level: int) -> str:
        bits = CLUSTER_DEPTHS[level]
        parts = [str(code >> (bits - 3))]
        for k in range(1, level + 1):
            shift = bits - CLUSTER_DEPTHS[k]
            parts.append(str((code >> shift) & 0b11))
        return ".".join(parts)

    def address(self, level: int, k: int) -> str:
        return self.code_to_address(int(self.codes[level][k]), level)

    def node_address(self, i: int) -> str:
        return self.code_to_address(int(self.path[i]), len(CLUSTER_DEPTHS) - 1)

    def resolve(self, address: str) -> np.ndarray:
        """Configurations under an address prefix such as ``3`` or ``3.1.0``."""
        parts = [int(x) for x in address.strip().split(".") if x != ""]
        if not parts or len(parts) > len(CLUSTER_DEPTHS) or not 0 <= parts[0] < 8 or any(
                not 0 <= x < 4 for x in parts[1:]):
            raise ValueError(f"invalid address: {address}")
        level = len(parts) - 1
        code = parts[0]
        for x in parts[1:]:
            code = (code << 2) | x
        prefix = self.path >> (DEPTH - CLUSTER_DEPTHS[level])
        return np.flatnonzero(prefix == code).astype(np.int32)

    def to_json(self) -> dict:
        return {
            "scales": list(SCALES),
            "levels": [
                {"scale": SCALES[lv], "clusters": [self.address(lv, k) for k in range(self.n_clusters(lv))],
                 "parents": self.parents[lv].tolist()}
                for lv in range(len(CLUSTER_DEPTHS))
            ],
        }


def adjacency_key(a) -> str:
    """Identity of a symmetric adjacency (its node count and sorted edge set), for the reference-hierarchy cache."""
    coo = a.tocoo() if hasattr(a, "tocoo") else None
    r, c = (coo.row, coo.col) if coo is not None else a._coo()[:2]
    o = np.lexsort((c, r))
    h = hashlib.sha256(np.int64(a.shape[0]).tobytes())
    h.update(np.asarray(r, dtype=np.int64)[o].tobytes())
    h.update(np.asarray(c, dtype=np.int64)[o].tobytes())
    return h.hexdigest()


class HierarchyTooLarge(ValueError):
    """A graph with no exported reference hierarchy is above the host's limit for computing one (see build_hierarchy)."""

    limit = "max_nodes_computed_hierarchy"

    def __init__(self, n: int, cap: int):
        super().__init__(f"this graph has {n:,} configurations and no precomputed address hierarchy; this runtime can "
                         f"compute one for at most {cap:,} (its eigensolver is much slower than the desktop's). The bundled "
                         "scenarios, and graphs up to that size, run here; larger ones run in the desktop runtime")


def build_hierarchy(a: sp.csr_matrix) -> Hierarchy:
    if _COMPAT_PATH:  # no scipy (iOS): exact desktop reference where available, else the dense eigensolver
        cached = _reference_cache.load(adjacency_key(a))
        if cached is not None:
            return hierarchy_from(*cached, source="reference")
    if _COMPAT_PATH:
        # Without scipy the hierarchy of a graph that has no exported desktop reference is computed by a dense eigensolve,
        # whose cost grows with n^3 (browser runtime, Pyodide: 1.5k nodes ~10 s, 2k ~23 s, 4k > 130 s). A host sets
        # XZR_MAX_NODES_COMPUTED_HIERARCHY to refuse such graphs up front instead of letting the page hang (0 = no limit).
        cap = int(os.environ.get("XZR_MAX_NODES_COMPUTED_HIERARCHY", "0") or 0)
        if cap and a.shape[0] > cap:
            raise HierarchyTooLarge(a.shape[0], cap)
    h = _build_hierarchy(a)
    if _COMPAT_PATH:
        h.source = "on-device eigensolver (may differ from the desktop's ARPACK hierarchy)"
    return h


def _build_hierarchy(a: sp.csr_matrix) -> Hierarchy:
    n = a.shape[0]
    path = np.zeros(n, dtype=np.int64)
    pos = np.zeros(n)  # continuous position within the final leaf (used for ordering)
    stack: list[tuple[np.ndarray, int]] = [(np.arange(n), 0)]
    while stack:
        idx, depth = stack.pop()
        if depth == DEPTH:
            continue
        if len(idx) < 2:
            path[idx] <<= DEPTH - depth
            continue
        f = _fiedler(a[idx][:, idx]) if len(idx) > 2 else np.array([0.0, 1.0])
        o = np.argsort(f, kind="stable")
        pos[idx] = np.argsort(o) / max(1, len(idx) - 1)
        half = len(idx) // 2
        lo, hi = idx[o[:half]], idx[o[half:]]
        path[lo] <<= 1
        path[hi] = (path[hi] << 1) | 1
        stack.append((lo, depth + 1))
        stack.append((hi, depth + 1))
    order = np.lexsort((pos, path)).astype(np.int32)
    return hierarchy_from(path, order)


# ----------------------------------------------------------------------------------------------- hierarchy method 2 (opt-in, versioned)
# Method 1 (``build_hierarchy`` above: the default, and the one every stored address and the golden fixture were made
# with) splits a sub-graph by the second eigenvector of its normalized adjacency. For a sub-graph with several connected
# components that eigenvalue is degenerate: every vector of the eigenspace is a valid answer and the one a solver returns
# depends on its LAPACK / ARPACK build (open item S11; tests/test_hierarchy_diagnosis.py). Method 2 removes that freedom:
# components are ordered by a canonical rule (size, then lowest node index) and a split orders nodes by (component,
# position within the component). It gives DIFFERENT partitions from method 1 wherever method 1 hit a degenerate
# eigenspace, so it is a new method with its own name, never a replacement: nothing selects it by default, results made
# with method 1 keep their meaning, no reference is rewritten.
HIERARCHY_METHODS = {
    1: "spectral bisection (default; platform-dependent on disconnected sub-graphs)",
    2: "component-canonical spectral bisection (opt-in; solver-independent on disconnected sub-graphs)",
}


def _fiedler_v2(a: sp.csr_matrix) -> np.ndarray:
    from scipy.sparse import csgraph as _csg  # desktop only: the iOS path never selects method 2

    m = a.shape[0]
    ncc, lab = _csg.connected_components(a, directed=False)
    if ncc == 1:
        return _fiedler(a)
    # canonical component order: larger first, ties by the lowest node index
    comps = sorted(range(ncc), key=lambda c: (-int((lab == c).sum()), int(np.flatnonzero(lab == c)[0])))
    f = np.zeros(m)
    for rank, c in enumerate(comps):
        idx = np.flatnonzero(lab == c)
        if len(idx) > 2:
            inner = _fiedler(a[idx][:, idx])
            pos = np.argsort(np.argsort(inner, kind="stable"), kind="stable") / max(1, len(idx) - 1)
        else:
            pos = np.linspace(0.0, 1.0, len(idx)) if len(idx) > 1 else np.zeros(1)
        f[idx] = rank + 0.5 * pos  # strictly inside the component's slot
    return f


def build_hierarchy_v2(a: sp.csr_matrix) -> Hierarchy:
    """Method 2 (see above). Same structure and addresses format as method 1; ``source`` says which method made it."""
    n = a.shape[0]
    path = np.zeros(n, dtype=np.int64)
    pos = np.zeros(n)
    stack: list[tuple[np.ndarray, int]] = [(np.arange(n), 0)]
    while stack:
        idx, depth = stack.pop()
        if depth == DEPTH:
            continue
        if len(idx) < 2:
            path[idx] <<= DEPTH - depth
            continue
        f = _fiedler_v2(a[idx][:, idx]) if len(idx) > 2 else np.array([0.0, 1.0])
        o = np.argsort(f, kind="stable")
        pos[idx] = np.argsort(o) / max(1, len(idx) - 1)
        half = len(idx) // 2
        lo, hi = idx[o[:half]], idx[o[half:]]
        path[lo] <<= 1
        path[hi] = (path[hi] << 1) | 1
        stack.append((lo, depth + 1))
        stack.append((hi, depth + 1))
    order = np.lexsort((pos, path)).astype(np.int32)
    return hierarchy_from(path, order, source="method 2 (component-canonical)")


def hierarchy_from(path: np.ndarray, order: np.ndarray, source: str = "computed") -> Hierarchy:
    """The cluster scales of a hierarchy, derived from its leaf paths and linear order."""
    path = np.asarray(path, dtype=np.int64)
    labels, codes, parents = [], [], []
    for lv, bits in enumerate(CLUSTER_DEPTHS):
        prefix = path >> (DEPTH - bits)
        c, lab = np.unique(prefix, return_inverse=True)
        labels.append(lab.astype(np.int32))
        codes.append(c)
        if lv == 0:
            parents.append(np.full(len(c), -1, dtype=np.int32))
        else:
            pc = c >> (bits - CLUSTER_DEPTHS[lv - 1])
            parents.append(np.searchsorted(codes[lv - 1], pc).astype(np.int32))
    return Hierarchy(path.astype(np.int32), np.asarray(order, dtype=np.int32), labels, codes, parents, source)
