"""Baseline vs intervention comparison."""

from __future__ import annotations

import numpy as np

from xzr.compare.compare import compare
from xzr.lod.hierarchy import build_hierarchy, symmetric_adjacency
from xzr.runtime.engine import Engine
from xzr.runtime.generator import latent_geometric
from xzr.runtime.intervention import Freeze, Gate


def _setup(n=600, seed=4):
    g = latent_geometric(n, seed)
    s = g.state
    h = build_hierarchy(symmetric_adjacency(s.src[s.alive], s.dst[s.alive], s.n))
    e = Engine(s, seed)
    e.run(40)
    return e, h


def test_identical_branches_do_not_differ():
    e, h = _setup()
    r = compare(e, [], [], [], [], h, horizon=60, noise_floor=False)
    assert r["fingerprints"]["baseline"] == r["fingerprints"]["intervention"]
    assert set(r["node_classes"]) == {0}
    assert r["edges"] == [] and r["summary"]["first_divergence_step"] is None


def test_intervention_differs_and_source_is_untouched():
    e, h = _setup()
    before = e.fingerprint()
    region = h.resolve("0")
    inside = np.zeros(e.state.n, bool)
    inside[region] = True
    boundary = np.flatnonzero(e.state.alive & (inside[e.state.src] != inside[e.state.dst]))
    r = compare(e, [], [], [Freeze(tuple(region.tolist())), Gate(tuple(boundary.tolist()), 0.0)], [], h, horizon=80)
    assert e.fingerprint() == before
    assert r["fingerprints"]["baseline"] != r["fingerprints"]["intervention"]
    # note: total ignitions may *rise* — closed boundaries concentrate emission onto the remaining transitions
    assert r["summary"]["gates_changed"] == len(boundary)
    assert any(c != 0 for c in r["node_classes"])
    frozen_reached = [r["node_classes"][i] for i in region]
    assert all(c in (0, 2, 4, 6) for c in frozen_reached)  # a frozen region can only lose
    assert any(c in (2, 6) for c in frozen_reached)
    m = r["metrics"]["ignitions"]
    assert {"baseline", "intervention", "delta", "noise_floor", "exceeds_noise"} <= set(m)
