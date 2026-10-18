"""Numerical soundness of the XB-TRO body simulator: a-priori stability, divergence vs fall, convergence, determinism."""

from __future__ import annotations

import copy

import numpy as np
import pytest

from xzr.xbtro import config, engine, metrics
from xzr.xbtro.experiments import base_config

PRESETS = ("human-like-planar", "machine-like-planar")
SEEDS = [11, 12, 13, 14]


@pytest.mark.parametrize("preset", PRESETS)
def test_presets_are_stable_for_the_covered_range(preset):
    P = engine.Params(base_config(preset))
    for cc in (0.0, 0.3, engine.CC_MAX):
        ns = P.numeric_stability(cc)
        assert ns["stable"], (preset, cc, ns["margin"])
        assert ns["mass_matrix_min_eig"] > 0                      # positive definite mass matrix
    assert P.numeric_stability()["mass_matrix_condition"] < 1e4


def test_the_criterion_matches_the_step_polynomial_of_a_single_mode():
    """For one decaying mode the spectral radius of the RK4 step matrix is |R(lambda h)|: stable up to lambda h = -2.78."""
    def R(z):
        return abs(1 + z + z * z / 2 + z ** 3 / 6 + z ** 4 / 24)
    assert R(-2.7) < 1 < R(-2.9)


def test_refuses_a_numerically_unstable_configuration_instead_of_running_it():
    cfg = base_config("human-like-planar")
    cfg["task"]["substeps"] = 1                       # the human-like damping needs a finer plant step
    with pytest.raises(config.ConfigError, match="numerically unstable"):
        engine.simulate(cfg, SEEDS)


def test_other_integrators_are_judged_by_their_own_step_matrix():
    P = engine.Params(base_config("human-like-planar"))
    assert P.numeric_stability(engine.CC_MAX, "rk4")["stable"]
    assert not P.numeric_stability(engine.CC_MAX, "semi-implicit-euler")["stable"]
    assert not P.numeric_stability(engine.CC_MAX, "explicit-euler")["stable"]


def test_numerical_divergence_is_not_a_fall():
    """Forced past the check with the worst-case co-contraction, the criterion's prediction is borne out as divergence, and the
    run is flagged as diverged — not as a fallen body."""
    cfg = base_config("human-like-planar")
    cfg["task"]["substeps"] = 1
    cfg["neural"]["cocontraction_base"] = 0.9
    r = engine.simulate(cfg, SEEDS, enforce_stability=False)
    assert r.diverged.all()
    assert not r.fell.any()
    m = metrics.summary(r)
    assert np.isnan(m["track_rms"]).all()             # a diverged run is not scored
    assert (m["recovery_status"] == "diverged").all()


def test_a_physical_fall_is_not_a_divergence():
    cfg = base_config("human-like-planar", extra={"environment": {"pushes": [{"t": 3.2, "dur": 0.12, "force": 400.0, "link": 2, "point_frac": 0.8}]}})
    r = engine.simulate(cfg, SEEDS)
    assert r.fell.all() and not r.diverged.any()
    assert (metrics.summary(r)["recovery_status"] == "fell").all()


@pytest.mark.parametrize("preset", PRESETS)
def test_both_presets_stand_without_disturbance_and_respond_gradedly(preset):
    cfg = base_config(preset, push=False)
    r = engine.simulate(cfg, SEEDS)
    assert not r.fell.any() and not r.diverged.any()
    peaks = []
    for f in (15.0, 40.0, 80.0):
        c = base_config(preset, extra={"environment": {"pushes": [{"t": 3.2, "dur": 0.12, "force": f, "link": 2, "point_frac": 0.8}]}})
        rr = engine.simulate(c, SEEDS)
        assert not rr.diverged.any()
        peaks.append(float(np.nanmedian(metrics.summary(rr)["peak_dev"])))
    assert peaks[0] < peaks[1] < peaks[2]


def test_plant_substeps_converge():
    """Noiseless runs: refining the plant step changes the COM trajectory by less than 0.1 mm (RMS)."""
    from xzr.xbtro.verification import noiseless
    base = noiseless(base_config("human-like-planar"))
    a = copy.deepcopy(base); a["task"]["substeps"] = 2
    b = copy.deepcopy(base); b["task"]["substeps"] = 4
    xa = engine.simulate(a, [1])["com"][0]
    xb = engine.simulate(b, [1])["com"][0]
    assert np.sqrt(np.mean((xa - xb) ** 2)) < 1e-4


def test_deterministic_and_common_random_numbers():
    cfg = base_config("human-like-planar")
    r1, r2 = engine.simulate(cfg, SEEDS), engine.simulate(cfg, SEEDS)
    assert np.array_equal(r1["com"], r2["com"])
    other = config.apply_intervention(cfg, "perturbation", 50.0)     # same noise: identical until the intervention acts
    r3 = engine.simulate(other, SEEDS)
    t_push = int(round(1.0 / cfg["task"]["dt"]))
    assert np.array_equal(r1["com"][:, :t_push], r3["com"][:, :t_push])
    assert not np.array_equal(r1["com"], r3["com"])


def test_diagnosis_reports_instead_of_raising():
    from xzr.xbtro.verification import diagnose
    bad = base_config("human-like-planar")
    bad["task"]["substeps"] = 1
    out = diagnose(bad)
    assert out["integrator_stable"] is False and out["probe"] is None and "unstable" in out["verdict"]
    good = diagnose(base_config("machine-like-planar"))
    assert good["integrator_stable"] and good["probe"]["diverged_fraction"] == 0
    assert "does not cover" in good["guarantee"]
