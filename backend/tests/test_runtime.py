"""Operational primitives: ignition, retention, penetration, return, transform, cut, reconfiguration,
connection, determinism, replay."""

from __future__ import annotations

import numpy as np
from conftest import make_state

from xzr.runtime import ops
from xzr.runtime.engine import Engine
from xzr.runtime.intervention import Freeze, Gate, ScaleThreshold, Sever
from xzr.runtime.state import fingerprint


def test_ignition_threshold_and_refractory():
    st = make_state(3, [])
    st.diff[:] = [1.2, 0.9, 1.5]
    st.frozen[2] = True
    ign = ops.ignite(st)
    assert ign.fired.tolist() == [0]  # 1 below threshold, 2 frozen
    assert st.refractory[0] == st.params.refractory_steps + 1
    ign2 = ops.ignite(st)
    assert 0 not in ign2.fired  # refractory


def test_memory_lowers_effective_threshold_and_is_counted():
    st = make_state(2, [])
    st.mem_coupling[:] = 0.3
    st.memory[:] = [1.0, 0.0]
    st.diff[:] = [0.8, 0.8]
    ign = ops.ignite(st)
    assert ign.fired.tolist() == [0]
    assert ign.memory_dependent == 1


def test_retention_and_decay_event():
    e = Engine(make_state(2, []), seed=1)
    e.state.diff[:] = [0.5, 0.021]
    d = e.step()
    assert np.isclose(e.state.diff[0], 0.4)
    assert d.decays.tolist() == [1]  # crossed below decay_eps


def test_penetration_carries_wave_origin_and_depth():
    e = Engine(make_state(3, [(0, 1), (1, 2)]), seed=1)
    e.state.diff[0] = 1.5
    d1 = e.step()
    assert d1.ignitions.tolist() == [0] and len(d1.penetrations) == 0
    d2 = e.step()
    assert d2.ignitions.tolist() == [1]
    assert d2.penetrations.tolist() == [[0, 0, 1]]  # edge 0, origin 0, depth 1
    d3 = e.step()
    assert d3.penetrations.tolist() == [[1, 0, 2]]


def test_return_on_a_loop():
    e = Engine(make_state(3, [(0, 1), (1, 2), (2, 0)], refractory_steps=1), seed=1)
    e.state.diff[0] = 1.5
    returns = []
    for _ in range(6):
        d = e.step()
        returns += [(d.t, int(i)) for i in d.returns]
    assert (4, 0) in returns  # the wave came back to its origin


def test_transformation_rewrites_form():
    st = make_state(2, [(0, 1)])
    st.transform[0] = 1
    st.form[:] = [2, 0]
    e = Engine(st, seed=1)
    e.state.diff[0] = 1.5
    d = e.step()
    assert d.transformations.tolist() == [[1, 3]]
    assert e.state.form[1] == 3


def test_overload_cuts_connection():
    st = make_state(2, [(0, 1)])
    st.capacity[0] = 0.1
    e = Engine(st, seed=1)
    e.state.diff[0] = 1.5
    d = e.step()
    assert d.cuts.tolist() == [0]
    assert not e.state.alive[0]


def test_weak_connection_disconnects():
    st = make_state(2, [(0, 1)])
    st.weight[0] = 0.01
    st.base_weight[0] = 0.01
    d = Engine(st, seed=1).step()
    assert d.removed_connections.tolist() == [0]


def test_reconfiguration_redirects_strongest_connection():
    st = make_state(3, [(0, 1), (1, 2)], reconfigure_per_step=1)
    st.overload[0] = st.params.overload_steps
    out = ops.reconfigure(st, np.random.default_rng(0))
    assert out.tolist() == [[0, 1, 2]]
    assert st.dst[0] == 2 and st.overload[0] == 0


def test_triadic_connect_creates_new_connection():
    st = make_state(3, [(0, 1), (1, 2)], connect_per_step=1)
    st.memory[:] = 1.0
    st.diff[0] = 1.5
    ign = ops.ignite(st)
    new = ops.connect(st, np.random.default_rng(0), ign, np.zeros(0, np.int32))
    assert new.tolist() == [[2, 0, 2]]
    assert st.alive[2] and st.src[2] == 0 and st.dst[2] == 2


def test_deterministic_replay_same_seed(small_world):
    a, b = small_world(), small_world()
    a.run(150)
    b.run(150)
    assert a.fingerprint() == b.fingerprint()
    c = small_world(seed=6)
    c.run(150)
    assert c.fingerprint() != a.fingerprint()


def test_rewind_replays_interventions_exactly(small_world):
    """Rewinding across logged interventions re-applies them at the same steps: bit-identical trajectory."""
    e = small_world()
    e.checkpoint_every = 25
    e.run(70)
    e.set_overlay([ScaleThreshold(tuple(range(50)), 1.5)])
    e.run(10)
    e.apply([Sever(tuple(np.flatnonzero(e.state.alive)[:20].tolist()))])  # at t=80, after checkpoint 75
    e.run(40)
    target = e.fingerprint()
    e.rewind(90)  # restore t=75, replay the sever at 80
    assert e.state.t == 90
    e.run(30)
    assert e.fingerprint() == target


def test_fork_is_independent_and_identical(small_world):
    e = small_world()
    e.run(30)
    before = e.fingerprint()
    f = e.fork()
    assert f.fingerprint() == before
    f.run(20)
    assert e.fingerprint() == before
    e.run(20)
    assert e.fingerprint() == f.fingerprint()


def test_overlay_is_idempotent_and_reversible(small_world):
    e = small_world()
    s = e.state
    base_gate = s.gate.copy()
    e.set_overlay([ScaleThreshold((1, 2, 3), 2.0), Gate((0, 1), 0.0), Freeze((7,))])
    assert s.theta_mod[1] == 2.0 and s.gate[0] == 0.0 and s.frozen[7]
    e.set_overlay([ScaleThreshold((1, 2, 3), 2.0), Gate((0, 1), 0.0), Freeze((7,))])
    assert s.theta_mod[1] == 2.0  # not compounded
    e.set_overlay([])
    assert np.all(s.theta_mod == 1.0) and np.array_equal(s.gate, base_gate) and not s.frozen.any()


def test_fingerprint_covers_rng_state(small_world):
    e = small_world()
    a = fingerprint(e.state, e.rng)
    e.rng.random()
    assert fingerprint(e.state, e.rng) != a
