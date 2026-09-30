"""Primitive ablation, reduced implementations, observer reconstruction, trajectory distances, minimal runtime."""

from __future__ import annotations

import numpy as np
import pytest

from xzr.compare.trajectory import Recording, compare_recordings, response_distance, response_vector
from xzr.runtime.engine import Engine
from xzr.runtime.flags import FULL, MINIMAL, Flags
from xzr.runtime.generator import latent_geometric
from xzr.runtime.intervention import Gate, ScaleThreshold, Sever
from xzr.shapes.waves import WaveObserver

T = 200


def eng(flags: Flags = FULL, seed: int = 5, n: int = 800) -> Engine:
    return Engine(latent_geometric(n, seed).state, seed, flags=flags)


def differing_arrays(a: Engine, b: Engine) -> set[str]:
    return {k for k, v in a.state.arrays().items() if not np.array_equal(v, b.state.arrays()[k], equal_nan=True)}


def test_flags_validate_and_default_is_full():
    assert Flags() == FULL and FULL.is_full()
    with pytest.raises(ValueError):
        Flags(threshold="sometimes")


def test_fused_transition_is_bit_identical():
    a, b = eng(), eng(Flags(fused_transition=True))
    a.run(T)
    b.run(T)
    assert a.fingerprint() == b.fingerprint()


def test_transformation_has_no_downstream_effect():
    a, b = eng(), eng(Flags(transform="off"))
    da, db = a.run(T, collect=True), b.run(T, collect=True)
    assert differing_arrays(a, b) == {"form"}
    assert all(np.array_equal(x.ignitions, y.ignitions) for x, y in zip(da, db, strict=True))
    assert sum(len(x.transformations) for x in da) > 0 and sum(len(y.transformations) for y in db) == 0


def test_return_detection_has_no_downstream_effect():
    a, b = eng(), eng(Flags(return_events="off"))
    da, db = a.run(T, collect=True), b.run(T, collect=True)
    assert a.fingerprint() == b.fingerprint()
    assert sum(len(x.returns) for x in da) > 0 and sum(len(y.returns) for y in db) == 0


def test_wave_state_is_reconstructed_exactly_outside_the_runtime():
    a, b = eng(), eng(Flags(wave_state="off"))
    obs = WaveObserver(b.state)
    for _ in range(T):
        da, db = a.step(), b.step()
        pens, rets = obs.observe(db, b.state)
        assert np.array_equal(pens, da.penetrations)
        assert np.array_equal(rets, da.returns)
    assert differing_arrays(a, b) <= {"wave_origin", "wave_depth", "pending_origin", "pending_depth"}


def test_relational_difference_tracks_node_difference():
    a, b = eng(), eng(Flags(difference="relational"))
    for _ in range(T):
        da, db = a.step(), b.step()
        assert np.array_equal(da.ignitions, db.ignitions)
    assert np.allclose(a.state.diff, b.state.diff, rtol=1e-9, atol=1e-9)


def test_reconfiguration_as_mutation_retires_and_creates():
    e = eng(Flags(reconfigure="mutation"), seed=6, n=1500)
    rec = 0
    for _ in range(400):
        d = e.step()
        rec += len(d.reconfigurations)
        assert len(d.retired) == len(d.reconfigurations)
        # right after the step: the retired connections are gone, their replacements exist, in different slots
        assert not e.state.alive[d.retired].any()
        assert e.state.alive[d.reconfigurations[:, 0]].all()
        assert set(d.retired.tolist()).isdisjoint(d.reconfigurations[:, 0].tolist())
    assert rec > 0


@pytest.mark.parametrize("flags", [Flags(threshold="off"), Flags(retention="off"), Flags(memory="off"),
                                   Flags(reconfigure="off"), Flags(adapt_source="all_carriers"), MINIMAL])
def test_deterministic_replay_under_ablation(flags):
    a, b = eng(flags), eng(flags)
    a.run(120)
    b.run(120)
    assert a.fingerprint() == b.fingerprint()


def test_rewind_under_ablation_replays_interventions():
    e = eng(MINIMAL)
    e.checkpoint_every = 25
    e.run(60)
    e.set_overlay([ScaleThreshold(tuple(range(40)), 1.4), Gate((1, 2, 3), 0.1)])
    e.run(20)
    e.apply([Sever(tuple(np.flatnonzero(e.state.alive)[:10].tolist()))])
    e.run(40)
    target = e.fingerprint()
    e.rewind(90)
    e.run(30)
    assert e.fingerprint() == target


def test_minimal_exact_reductions_are_bit_identical():
    """All reductions in MINIMAL except reconfiguration-as-mutation are exact: they only drop state nothing reads."""
    a, b = eng(), eng(MINIMAL.with_(reconfigure="redirect"))
    da, db = a.run(T, collect=True), b.run(T, collect=True)
    assert differing_arrays(a, b) <= {"form", "wave_origin", "wave_depth", "pending_origin", "pending_depth"}
    assert all(np.array_equal(x.ignitions, y.ignitions) for x, y in zip(da, db, strict=True))


def test_minimal_runtime_events_are_complete_with_the_observer():
    """With the observer, the minimal runtime reports the same penetration annotations and returns it would compute."""
    b = eng(MINIMAL.with_(reconfigure="redirect"))
    a = eng()
    obs = WaveObserver(b.state)
    for _ in range(T):
        da, db = a.step(), b.step()
        p, r = obs.observe(db, b.state)
        assert np.array_equal(p, da.penetrations) and np.array_equal(r, da.returns)


def test_minimal_runtime_stays_within_the_noise_floor():
    """Reconfiguration-as-mutation makes the minimal runtime statistically (not bitwise) equivalent: its distance from
    the full runtime must not exceed twice the full runtime's distance from itself under another random stream."""
    full, mini, noise = _rec(steps=400, n=1500), _rec(MINIMAL, steps=400, n=1500), _rec(rng_seed=1005, steps=400, n=1500)
    d_mini, d_noise = compare_recordings(full, mini), compare_recordings(full, noise)
    for k, v in d_mini["criteria"].items():
        assert v <= 2 * d_noise["criteria"][k] + 0.02, k


def test_ablations_that_matter_do_change_the_trajectory():
    base = eng()
    base.run(T)
    for flags in (Flags(threshold="off"), Flags(retention="off"), Flags(memory="off"), Flags(transition="off")):
        e = eng(flags)
        e.run(T)
        assert e.fingerprint() != base.fingerprint()


# ------------------------------------------------------------------------------------------------ trajectory
def _rec(flags: Flags = FULL, seed: int = 5, rng_seed: int | None = None, steps: int = 120, n: int = 600) -> Recording:
    from xzr.lod.hierarchy import build_hierarchy, symmetric_adjacency
    from xzr.shapes.detector import ShapeDetector
    st = latent_geometric(n, seed).state
    h = build_hierarchy(symmetric_adjacency(st.src[st.alive], st.dst[st.alive], st.n))
    e = Engine(st, seed if rng_seed is None else rng_seed, flags=flags)
    det = ShapeDetector(h, graph_every=10)
    r = Recording(n=st.n, snapshot_every=30)
    for _ in range(steps):
        d = e.step()
        out = det.observe(d, e.state)
        r.record(d, e.state)
        if "graph" in out:
            r.signatures.append(list(det.signatures))
    r.attach_detector(det)
    return r


def test_trajectory_distances_zero_for_identical_runs():
    a, b = _rec(), _rec()
    c = compare_recordings(a, b)
    assert c["first_divergence"] is None
    assert c["event_sequence"] == c["graph_edit"] == c["difference_w1"] == c["signature"] == 0.0
    assert all(v == 0.0 for v in c["criteria"].values())


def test_trajectory_distances_detect_structural_change():
    a, b = _rec(), _rec(Flags(retention="off"))
    c = compare_recordings(a, b)
    assert c["first_divergence"] is not None and c["event_sequence"] > 0.3
    assert c["criteria"]["amplification_regime"] > 0.2


def test_response_distance():
    a, b = _rec(), _rec(rng_seed=99)
    ra = response_vector(a, b)
    assert response_distance(ra, ra) == 0.0
    assert 0.0 < response_distance(ra, -ra) <= 1.0
