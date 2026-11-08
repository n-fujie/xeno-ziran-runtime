"""The matched-rival comparison (xzr.gaisho.rival, rival_experiment): the engine hook is inert, the rival is a working controller, and the verdict logic is the one that was frozen."""

from __future__ import annotations

import numpy as np

from xzr.gaisho import rival
from xzr.gaisho import rival_experiment as rx
from xzr.xbtro import config, engine

SEEDS = [1000, 1001]


def test_the_hook_is_inert_when_unused():
    cfg = config.apply_intervention(config.build("human-like-planar"), "perturbation", 100.0)
    a = engine.simulate(cfg, SEEDS)
    b = engine.simulate(cfg, SEEDS, ext_ctrl=None)
    for k in ("theta", "omega", "tau", "energy", "line_u"):
        assert np.array_equal(np.asarray(a[k]), np.asarray(b[k]))


def test_expm_and_dare():
    m = np.array([[0.0, 1.0], [-1.0, 0.0]])
    e = rival.expm(m * 0.5)
    assert np.allclose(e, [[np.cos(0.5), np.sin(0.5)], [-np.sin(0.5), np.cos(0.5)]], atol=1e-12)
    a = np.array([[1.01, 0.01], [0.0, 1.0]])
    b = np.array([[0.0], [0.01]])
    _, k = rival.dare(a, b, np.eye(2), np.eye(1))
    assert np.max(np.abs(np.linalg.eigvals(a - b @ k))) < 1.0


def test_linearised_plant_matches_the_engine():
    cfg = config.apply_intervention(config.build("human-like-planar"), "perturbation", 0.0)
    sim = engine.Sim(cfg, [1], record=False)
    lin = rival.linearise(sim)
    assert np.max(np.abs(np.linalg.eigvals(lin["A"]))) > 1.0  # an inverted pendulum: open-loop unstable
    rv = rival.OrdinaryFeedback()
    rv._build(sim)
    assert np.max(np.abs(np.linalg.eigvals(rv.A - rv.B @ rv.K))) < 1.0  # stable without delay


def test_the_rival_is_a_working_controller():
    """The viability criterion of the frozen protocol: it holds the unperturbed, undelayed cell."""
    cfg = rx.build_config({"rival": {}}, 0.0, 0.0)
    run = engine.simulate(cfg, SEEDS, ext_ctrl=rx.rival_for({"rival": {}}))
    assert not np.asarray(run.fell).any()


def test_the_rival_sees_only_what_the_preset_law_sees():
    """It is called with delayed, noisy estimates and the perceived reference; changing the TRUE task cue time leaves its inputs' structure unchanged (no true state is passed)."""
    seen: dict[str, set[str]] = {}

    def spy(sim, i, sig):
        seen.setdefault("keys", set()).update(sig)
        return np.zeros(sim.S), np.zeros(sim.S)

    cfg = rx.build_config({}, 0.0, 0.0)
    engine.simulate(cfg, SEEDS[:1], ext_ctrl=spy)
    assert seen["keys"] == {"xref", "th_hat", "w_hat", "x_p", "v_p", "x_v", "x_vis", "vis_ok", "kc"}


def test_paired_verdicts():
    a = np.array([0.10, 0.12, 0.11, 0.10, 0.09, 0.12, 0.11, 0.10])
    assert rx.paired(a, a + 0.2)["verdict"] == "A_BETTER"
    assert rx.paired(a + 0.2, a)["verdict"] == "B_BETTER"
    assert rx.paired(a, a + 0.001 * np.arange(8))["verdict"] == "EQUIVALENT"
    noisy = np.array([0.0, 0.4, 0.0, 0.4, 0.0, 0.4, 0.0, 0.4])
    assert rx.paired(noisy, np.zeros(8))["verdict"] == "UNRESOLVED"


def test_protocol_is_frozen_and_hashed():
    assert rx.digest(rx.PROTOCOL) == rx.PROTOCOL_DIGEST
    assert set(rx.FINAL_SEEDS).isdisjoint(rx.EXPLORATION_SEEDS)
    assert len(rx.CONDITIONS) == 22


def test_label_scrambling_changes_labels_but_not_records():
    res = rx.label_invariance([1000])
    for row in res["rows"]:
        assert row["labels_changed"] and row["records_bit_identical"]
