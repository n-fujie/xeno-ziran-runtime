"""Level-of-detail queries: aggregated clusters and flows at coarse scales, viewport tiles at fine scales.

Binary tile layout (little-endian, 4-byte aligned columns):

    u32 n_nodes, u32 n_edges, u32 truncated
    nodes: u32 idx[n], f32 x[n], f32 y[n]
    edges: u32 id[m], u32 src[m], u32 dst[m], f32 weight[m], f32 gate[m], u8 alive[m] (padded), u8 transform[m] (padded)
"""

from __future__ import annotations

import struct

import numpy as np

from ..runtime.state import State
from .hierarchy import Hierarchy


def _pad(b: bytes) -> bytes:
    return b + b"\0" * ((4 - len(b) % 4) % 4)


class GridIndex:
    """Uniform grid over one projection for viewport queries. NaN positions (no projection) are skipped."""

    def __init__(self, xy: np.ndarray, cells: int = 64):
        self.xy = xy
        ok = np.isfinite(xy).all(1)
        self.valid = np.flatnonzero(ok)
        if len(self.valid) == 0:
            self.lo = np.zeros(2)
            self.size = np.ones(2)
            self.cells = 1
            self.start = np.zeros(2, dtype=np.int64)
            self.items = np.zeros(0, dtype=np.int64)
            return
        p = xy[self.valid]
        self.lo = p.min(0)
        self.size = np.maximum((p.max(0) - self.lo) / cells, 1e-9)
        self.cells = cells
        c = self._cell(p)
        key = c[:, 1] * cells + c[:, 0]
        o = np.argsort(key, kind="stable")
        self.items = self.valid[o]
        self.start = np.searchsorted(key[o], np.arange(cells * cells + 1))

    def _cell(self, p: np.ndarray) -> np.ndarray:
        return np.clip(((p - self.lo) / self.size).astype(np.int64), 0, self.cells - 1)

    def query(self, x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
        if len(self.items) == 0:
            return np.zeros(0, dtype=np.int32)
        (cx0, cy0), (cx1, cy1) = self._cell(np.array([[x0, y0], [x1, y1]]))
        parts = [self.items[self.start[cy * self.cells + cx0]: self.start[cy * self.cells + cx1 + 1]]
                 for cy in range(cy0, cy1 + 1)]
        idx = np.concatenate(parts) if parts else np.zeros(0, dtype=np.int64)
        p = self.xy[idx]
        m = (p[:, 0] >= x0) & (p[:, 0] <= x1) & (p[:, 1] >= y0) & (p[:, 1] <= y1)
        return idx[m].astype(np.int32)


def cluster_summary(h: Hierarchy, level: int, positions: dict[str, np.ndarray], state: State,
                    max_flows: int = 600) -> dict:
    """Clusters of one scale with per-projection centroids, and aggregated inter-cluster flows."""
    lab = h.labels[level]
    k = h.n_clusters(level)
    count = np.bincount(lab, minlength=k)
    cent = {}
    spread = {}
    for name, xy in positions.items():
        ok = np.isfinite(xy).all(1)
        c = np.bincount(lab[ok], minlength=k).astype(np.float64)
        sx = np.bincount(lab[ok], xy[ok, 0], minlength=k)
        sy = np.bincount(lab[ok], xy[ok, 1], minlength=k)
        with np.errstate(invalid="ignore", divide="ignore"):
            cx, cy = sx / c, sy / c
        cent[name] = [[None if not np.isfinite(a) else round(float(a), 2),
                       None if not np.isfinite(b) else round(float(b), 2)] for a, b in zip(cx, cy, strict=True)]
        dx = xy[ok, 0] - cx[lab[ok]]
        dy = xy[ok, 1] - cy[lab[ok]]
        with np.errstate(invalid="ignore", divide="ignore"):
            rms = np.sqrt(np.bincount(lab[ok], dx * dx + dy * dy, minlength=k) / c)
        spread[name] = [None if not np.isfinite(r) else round(float(r), 2) for r in rms]
    m = state.alive
    a, b = lab[state.src[m]], lab[state.dst[m]]
    cross = a != b
    key = a[cross].astype(np.int64) * k + b[cross]
    w = state.weight[m][cross] * state.gate[m][cross]
    ld = state.load[m][cross]
    uk, inv = np.unique(key, return_inverse=True)
    ws = np.bincount(inv, w)
    ls = np.bincount(inv, ld)
    cn = np.bincount(inv)
    top = np.argsort(-(ws + 2 * ls), kind="stable")[:max_flows]
    flows = [[int(uk[i] // k), int(uk[i] % k), int(cn[i]), round(float(ws[i]), 3), round(float(ls[i]), 3)]
             for i in top]
    return {
        "level": level,
        "addresses": [h.address(level, i) for i in range(k)],
        "parents": h.parents[level].tolist(),
        "count": count.tolist(),
        "centroids": cent,
        "spread": spread,  # RMS distance of members from the centroid, per projection
        "flows": flows,  # [from, to, n_connections, weight·gate sum, recent load sum]
    }


def edges_for(state: State, nodes: np.ndarray, max_edges: int, both_ends: bool) -> tuple[np.ndarray, bool]:
    inset = np.zeros(state.n, dtype=bool)
    inset[nodes] = True
    s_in, d_in = inset[state.src], inset[state.dst]
    m = state.alive & ((s_in & d_in) if both_ends else (s_in | d_in))
    e = np.flatnonzero(m)
    truncated = False
    if len(e) > max_edges:
        score = state.weight[e] * state.gate[e] + state.load[e]
        e = e[np.argsort(-score, kind="stable")[:max_edges]]
        truncated = True
    return e.astype(np.int32), truncated


def encode_tile(state: State, xy: np.ndarray, nodes: np.ndarray, edges: np.ndarray, truncated: bool) -> bytes:
    ends = np.concatenate([state.src[edges], state.dst[edges]]) if len(edges) else np.zeros(0, np.int32)
    allnodes = np.union1d(nodes, ends).astype(np.int32)
    p = xy[allnodes]
    out = [struct.pack("<III", len(allnodes), len(edges), int(truncated)),
           allnodes.astype("<u4").tobytes(), p[:, 0].astype("<f4").tobytes(), p[:, 1].astype("<f4").tobytes(),
           edges.astype("<u4").tobytes(), state.src[edges].astype("<u4").tobytes(),
           state.dst[edges].astype("<u4").tobytes(), state.weight[edges].astype("<f4").tobytes(),
           state.gate[edges].astype("<f4").tobytes(), _pad(state.alive[edges].astype(np.uint8).tobytes()),
           _pad(state.transform[edges].astype(np.uint8).tobytes())]
    return b"".join(out)
