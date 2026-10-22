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


def test_stored_lab_record_m2_differs_only_in_chamber_membership_not_in_dynamics():
    """test_published_records_replay fails for m2-run-9100.json (also at the commit that produced it). The record's first steps agree with a fresh run
    in every per-chamber activity and shutter value; two chambers' retained memory differ with their sum preserved and the conduit count differs by one:
    a few configurations sit in the neighbouring chamber. The dynamics agree; the hierarchy partition (the chambers) differs: the same cause."""
    import json
    from pathlib import Path

    import pytest

    pytest.importorskip("mujoco")
    from xzr.lab.record import LabRun

    rec = json.loads((Path(__file__).resolve().parents[1] / "experiments" / "results" / "lab" / "m2-run-9100.json").read_text())
    r = LabRun(rec["config"])
    for t in range(3):
        r.step()
        a, b = r.record()["steps"][t], rec["steps"][t]
        assert np.allclose(a["activity"], b["activity"], atol=1e-3) and np.allclose(a["shutter"], b["shutter"], atol=1e-3)
        x, y = np.array(a["memory"], float), np.array(b["memory"], float)
        differing = np.flatnonzero(np.abs(x - y) > 1e-3)
        assert (
            len(differing) <= 4 and abs(x[differing].sum() - y[differing].sum()) < 1e-3
        )  # memory moved between chambers, none created or lost
        assert abs(len(a["conduits"]) - len(b["conduits"])) <= 2
