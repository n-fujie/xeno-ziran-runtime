"""Shape descriptors on constructed structures, and detector integration."""

from __future__ import annotations

import numpy as np
from conftest import make_state

from xzr.interpret.labels import DEFAULT_RULES, interpret
from xzr.lod.hierarchy import build_hierarchy, symmetric_adjacency
from xzr.runtime.engine import Engine
from xzr.runtime.generator import latent_geometric
from xzr.shapes import metrics as M
from xzr.shapes.detector import GRAPH_SERIES, STEP_SERIES, ShapeDetector


def test_gini_and_top_share():
    assert M.gini(np.ones(10)) == 0.0
    one = np.zeros(10)
    one[3] = 5
    assert np.isclose(M.gini(one), 0.9)
    assert M.top_share(one, 0.1) == 1.0


def test_loops_found_on_ring_not_on_chain():
    ring = make_state(4, [(0, 1), (1, 2), (2, 3), (3, 0)])
    ring.load[:4] = 1.0
    chain = make_state(4, [(0, 1), (1, 2), (2, 3)])
    chain.load[:3] = 1.0
    assert M.loops(ring)["n_loops"] == 1 and M.loops(ring)["largest_loop"] == 4
    assert M.loops(chain)["n_loops"] == 0


def test_fragmentation_counts_components():
    st = make_state(6, [(0, 1), (1, 2), (3, 4)])
    f = M.fragmentation(st)
    assert f["components"] == 3 and np.isclose(f["largest_component"], 0.5)


def test_reachability_horizon_and_closure_respect_gates():
    st = make_state(5, [(0, 1), (1, 2), (2, 3), (3, 4)])
    g = M.transition_graph(st)
    assert M.horizon_reach(g, np.array([0]), 2).tolist() == [True, True, True, False, False]
    assert M.closure_reach(g, np.array([0])).all()
    st.gate[2] = 0.0  # a closed boundary
    g = M.transition_graph(st)
    assert M.closure_reach(g, np.array([0])).tolist() == [True, True, True, False, False]


def test_bottleneck_is_the_bridge():
    # two fans joined through node 4
    edges = [(0, 4), (1, 4), (2, 4), (3, 4), (4, 5), (5, 6), (5, 7), (5, 8)]
    st = make_state(9, edges)
    visits = M.bottlenecks(M.transition_graph(st), np.array([0, 1, 2, 3]), np.random.default_rng(0))
    assert np.argmax(visits) in (4, 5) and visits[4] > 0 and visits[5] > 0


def test_asymmetry_on_reciprocal_pair():
    st = make_state(3, [(0, 1), (1, 0), (1, 2)])
    st.load[:3] = [3.0, 1.0, 2.0]
    a = M.asymmetry(st)
    assert np.isclose(a["asymmetry"], 0.5) and np.isclose(a["one_way_share"], 2 / 6)


def _world(seed=3, n=600):
    g = latent_geometric(n, seed)
    s = g.state
    h = build_hierarchy(symmetric_adjacency(s.src[s.alive], s.dst[s.alive], s.n))
    return Engine(s, seed), h


def test_detector_series_signatures_embedding():
    e, h = _world()
    det = ShapeDetector(h, graph_every=10)
    for _ in range(120):
        det.observe(e.step(), e.state)
    assert all(len(det.series[k]) == 120 for k in STEP_SERIES)
    assert all(len(det.graph_series[k]) == 12 for k in GRAPH_SERIES)
    assert len(det.signatures) == h.n_clusters(2)
    assert det.embedding is not None and det.embedding.shape == (e.state.n, 2)
    shapes = det.recurrent_shapes()
    assert shapes and all(set(s["axes"]) == {"I", "L", "R", "M", "K", "B"} for s in shapes)
    out = interpret(shapes, DEFAULT_RULES)
    assert out["disclaimer"] and len(out["interpretations"]) == len(shapes)


def test_detection_and_interpretation_do_not_change_the_runtime():
    e1, h = _world()
    e2, _ = _world()
    det = ShapeDetector(h, graph_every=5)
    for _ in range(100):
        d = e1.step()
        det.observe(d, e1.state)
        if d.t % 20 == 0:
            interpret(det.recurrent_shapes())
    e2.run(100)
    assert e1.fingerprint() == e2.fingerprint()


def test_truncate_after_rewind():
    e, h = _world()
    det = ShapeDetector(h, graph_every=10)
    for _ in range(80):
        det.observe(e.step(), e.state)
    det.truncate(40)
    assert det.t[-1] == 40 and det.t_graph[-1] == 40
