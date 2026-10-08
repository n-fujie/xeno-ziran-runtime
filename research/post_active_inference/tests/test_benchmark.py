"""Tests for the Post-Active-Inference benchmark layer. Run: ../../.venv/bin/python -m pytest -q tests"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import nonredundancy as NR  # noqa: E402
import pai  # noqa: E402,F401
import regime_classifier as RC  # noqa: E402
from pai import aif_vendor as V  # noqa: E402
from pai import episode as E  # noqa: E402
from pai.perturbations import ALIASES, REGISTRY  # noqa: E402
from pai.stats import crossing, holm, sign_flip_p, threshold  # noqa: E402

SMALL = {"n": 400, "sensor_size": 3}
PH = {"warmup": 60, "calib_end": 260, "t_p": 320, "t_r": 360, "horizon": 400}
SIBLING = HERE.parents[2] / "ziran-xeno-simulator" / "embodied" / "active_inference"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"sib_{name}", SIBLING / f"{name}.py",
                                                  submodule_search_locations=[str(SIBLING)])
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


@pytest.mark.skipif(not SIBLING.exists(), reason="sibling repository not present")
def test_vendored_aif_math_matches_sibling():
    si = _load("state_inference")
    ef = _load("expected_free_energy")
    rng = np.random.default_rng(0)
    for _ in range(20):
        A = rng.random((5, 5)); A /= A.sum(0)
        B = rng.random((5, 5)); B /= B.sum(0)
        prior = rng.random(5); prior /= prior.sum()
        logC = np.log(rng.random(5)); o = int(rng.integers(5))
        assert np.array_equal(V.posterior(A, prior, o), si.posterior(A, prior, o))
        q = V.posterior(A, prior, o)
        assert V.vfe(A, prior, q, o) == si.vfe(A, prior, q, o)
        a, b = V.efe(A, B, q, logC), ef.efe(A, B, q, logC)
        assert a["G"] == b["G"] and a["epistemic"] == b["epistemic"] and a["pragmatic"] == b["pragmatic"]


def test_vfe_equals_surprise_at_exact_posterior():
    A = np.full((5, 5), 0.05) + np.eye(5) * 0.75
    A /= A.sum(0)
    prior = np.full(5, 0.2)
    q = V.posterior(A, prior, 2)
    assert np.isclose(V.vfe(A, prior, q, 2), -np.log((A[2] * prior).sum()))


def _run(pert=None, sev=0.0, ctl="aif_adaptive", probes=False):
    return E.run_episode(SMALL, 5, pert, sev, ctl, phases=PH, probes=probes)


def test_episode_is_deterministic_and_prefix_cache_is_exact():
    E._PREFIX.clear()
    a = _run()
    b = _run()  # from the cached prefix
    E._PREFIX.clear()
    c = _run()  # fresh prefix
    assert a["status"] == "ok"
    assert a["metrics"] == b["metrics"] == c["metrics"]
    assert a["trace"] == c["trace"]


def test_severity_zero_is_the_unperturbed_control():
    a = _run()
    b = _run("topology.cluster_split", 0.0)
    assert a["metrics"] == b["metrics"]


@pytest.mark.parametrize("key", sorted(REGISTRY))
def test_every_perturbation_runs(key):
    r = _run(key, 1.0, "aif_fixed")
    assert r["status"] == "ok", r.get("failure")
    assert r["side"] in ("world", "interface", "observation")
    if r["side"] == "observation":
        assert r["perturbation_info"]["footprint_size"] == 0


def test_aliases_resolve():
    for a, k in ALIASES.items():
        assert k in REGISTRY and a not in REGISTRY


def test_observation_perturbation_leaves_world_untouched():
    a = E.run_episode(SMALL, 5, None, 0.0, "none", phases=PH)
    b = E.run_episode(SMALL, 5, "sensor.noise", 1.0, "none", phases=PH)
    # noop controller: the world trajectory cannot depend on readings
    assert a["trace"]["true"] == b["trace"]["true"]
    assert a["trace"]["agg"] != b["trace"]["agg"]


def test_probes_and_tracker_fields():
    r = _run(None, 0.0, "none", probes=True)
    assert set(r["probes"]) == {"pre", "p1", "mid", "p3", "post"}
    assert len(r["probes"]["mid"]["effect"]) == 5 and r["probes"]["mid"]["effect"][0] == 0.0
    for k in ("detect_onset", "z_max_pre", "splits_pert", "reachable_pre"):
        assert k in r["tracker"]


def _rec(acc, corr, pc1, tn, fp=None, eff=None, side="world", hit=True):
    m = {"one_step_acc_pert": acc, "sensor_corr_pert": corr, "pc1_share_pert": pc1, "T_N_corr_pert": tn}
    r = {"status": "ok", "metrics": m, "side": side,
         "tracker": {"detect_onset": {"hit": hit}, "localisation_auc": 0.7},
         "tracker_sensor_only": {"detect_onset": {"hit": False}}}
    if fp is not None:
        r["probes"] = {k: {"footprint": fp, "effect": eff, "response_share_T": 0.5} for k in ("p1", "mid", "p3")}
    return r


def test_classifier_rule():
    ctrl = {"aif_fixed": _rec(0.8, 0.9, 0.6, 0.2), "none": _rec(0, 0, 0, 0, list(range(10)), [0, -1, 1, -0.5, 0.5])}
    noise = {"aif_fixed": _rec(0.8, 0.9, 0.6, 0.2), "none": _rec(0, 0, 0, 0, list(range(10)), [0, -1, 1, -0.5, 0.5])}
    same = {"aif_fixed": _rec(0.8, 0.9, 0.6, 0.2), "none": _rec(0, 0, 0, 0, list(range(10)), [0, -1, 1, -0.5, 0.5])}
    assert RC.scores(same, ctrl, noise)["label"] == RC.LABELS[0]
    mid = {"aif_fixed": _rec(0.52, 0.9, 0.6, 0.2), "none": same["none"]}
    assert RC.scores(mid, ctrl, noise)["label"] == RC.LABELS[1]
    bad = {"aif_fixed": _rec(0.1, 0.9, 0.6, 0.2), "none": same["none"]}
    s = RC.scores(bad, ctrl, noise)
    assert s["label"] == RC.LABELS[2] and s["first_unstable"] == "S_model"
    flipped = {"aif_fixed": _rec(0.8, 0.9, 0.6, 0.2), "none": _rec(0, 0, 0, 0, list(range(10)), [0, 1, -1, 0.5, -0.5])}
    s = RC.scores(flipped, ctrl, noise)
    assert s["S_policy"] == 0.0 and s["label"] == RC.LABELS[2]


def test_tracking_rule_depends_on_side_not_on_label():
    obs = {"none": _rec(0, 0, 0, 0, side="observation", hit=False), "aif_fixed": _rec(0.1, 0.1, 0.6, 0.2)}
    assert RC.tracking(obs)["tracking_preserved"] is True
    obs["none"]["tracker"]["detect_onset"]["hit"] = True
    assert RC.tracking(obs)["tracking_preserved"] is False


def test_nonredundancy_statuses():
    rng = np.random.default_rng(1)
    cells = []
    for i in range(12):
        runs = {"aif_adaptive": {"status": "ok", "metrics": {"success_pert": 0.8 + 0.01 * rng.standard_normal(),
                                                             "one_step_acc_pert": 0.7}},
                "aif_adaptive-no_policy": {"status": "ok", "metrics": {"success_pert": 0.3, "one_step_acc_pert": 0.7}}}
        cells.append({"key": "x", "severity": 1.0, "seed": i, "regime": "R", "runs": runs})
    res = NR.analyse(cells)
    t = res["table"]["policy"]["R"]
    assert t["intervention"] == "NON-REDUNDANT" and t["prediction"] == "REDUNDANT"


def test_stats():
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert sign_flip_p(np.ones(10)) < 0.01 and sign_flip_p(np.zeros(5)) == 1.0
    assert crossing(np.array([0, 0.5, 1.0]), np.array([1.0, 0.9, 0.5]), 0.8) == pytest.approx(0.625)
    t = threshold([0, 0.5, 1.0], np.array([[1, 0.9, 0.5], [1, 0.85, 0.6]]), 0.8)
    assert 0.5 < t["estimate"] < 1.0 and t["seeds_crossing_share"] == 1.0


def test_dead_sensor_scores_zero():
    from metrics import _sensor_corr
    assert _sensor_corr([0.0] * 10, list(range(10))) == 0.0
    assert _sensor_corr([float("nan")] * 10, list(range(10))) == 0.0
    assert _sensor_corr(list(range(10)), [1.0] * 10) is None
    assert _sensor_corr(list(range(10)), list(range(10))) == pytest.approx(1.0)
