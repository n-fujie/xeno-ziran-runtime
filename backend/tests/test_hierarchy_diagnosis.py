"""Diagnosis of the known platform dependence of the address hierarchy (open item S11; test_compat[desktop-scipy]).

The hierarchy is built by recursive spectral bisection. For a sub-graph with more than one connected component the eigenvalue of the
second eigenvector is degenerate: any vector in the eigenspace is a valid answer, and which one an eigensolver returns depends on the LAPACK /
ARPACK build. This test does not hide the divergence: it compares the computed hierarchy of the golden fixture's graph with its exported
reference and, where they differ, asserts that the FIRST differing split is at a sub-graph with more than one connected component (the cause), and
that every sub-graph split before it that is connected agrees with the reference. On a platform whose solver reproduces the reference the paths are
equal and the test passes without a divergence to explain.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse.csgraph as csg

from xzr._compat import hierarchy_cache as reference_cache
from xzr.lod import hierarchy as H
from xzr.scenario.io import load_sample
from xzr.service.session import Session


def test_first_divergence_from_the_reference_hierarchy_is_at_a_disconnected_subgraph():
    s = Session(load_sample("demo-3k"))
    st = s.engine.state
    m = st.alive
    a = H.symmetric_adjacency(st.src[m], st.dst[m], st.n)
    ref = reference_cache.load(H.adjacency_key(a))
    assert ref is not None, "the reference hierarchy of the fixture graph is part of the repository"
    rpath = np.asarray(ref[0])
    if np.array_equal(rpath, s.h.path):
        return  # this platform reproduces the reference
    stack = [(np.arange(a.shape[0]), 0)]
    first = None
    connected_mismatches = 0
    while stack:
        idx, depth = stack.pop()
        if depth == H.DEPTH or len(idx) < 2:
            continue
        sub = a[idx][:, idx]
        ncc, _ = csg.connected_components(sub, directed=False)
        f = H._fiedler(sub) if len(idx) > 2 else np.array([0.0, 1.0])
        o = np.argsort(f, kind="stable")
        half = len(idx) // 2
        rbit = (rpath[idx] >> (H.DEPTH - depth - 1)) & 1
        mism = int((rbit[o[:half]] != 0).sum() + (rbit[o[half:]] != 1).sum())
        if mism:
            first = first or (depth, len(idx), int(ncc))
            # splits whose parents agreed with the reference and which are connected must agree too
            if first == (depth, len(idx), int(ncc)) and ncc == 1:
                connected_mismatches += 1
        stack += [(idx[o[:half]], depth + 1), (idx[o[half:]], depth + 1)]
    assert first is not None
    assert first[2] > 1, f"first divergence at a connected sub-graph {first}: the degenerate-eigenspace explanation does not hold"
    assert connected_mismatches == 0
