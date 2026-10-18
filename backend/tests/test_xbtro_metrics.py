"""Recovery / settling metrics: censoring, windows, pre-registered bands."""

from __future__ import annotations

import numpy as np

from xzr.xbtro import config, engine, metrics
from xzr.xbtro.experiments import base_config


def _fake_run(inside: np.ndarray, fell=None, diverged=None, fall_time=None, dt=0.01):
    s, T = inside.shape
    cfg = base_config("human-like-planar")
    arrays = {"com": np.zeros((s, T))}
    fell = np.zeros(s, dtype=bool) if fell is None else fell
    return engine.Run(cfg, list(range(s)), np.arange(T) * dt, dt, arrays, [], fell, np.full(s, np.inf) if fall_time is None else fall_time,
                      np.zeros(s, dtype=bool) if diverged is None else diverged, np.full(s, np.inf), {}, {})


def test_not_achieved_is_censored_not_the_window_length():
    inside = np.zeros((2, 400), dtype=bool)
    inside[0, 150:250] = True                         # holds for 1.0 s from 1.5 s on
    run = _fake_run(inside)
    res = metrics.time_to_hold(run, inside, 1.0, 3.0)
    assert res["time"][0] == 0.5 and res["status"][0] == "achieved"
    assert np.isnan(res["time"][1]) and res["status"][1] == "not-achieved-in-window"
    assert res["rmst"][1] == 2.0 and res["window"][1] == 2.0      # the restricted mean uses the window; the time stays NaN


def test_the_hold_must_complete_inside_the_window():
    inside = np.zeros((1, 400), dtype=bool)
    inside[0, 290:400] = True                         # enters at 2.9 s but the window ends at 3.0 s: hold (0.4 s) cannot finish
    res = metrics.time_to_hold(_fake_run(inside), inside, 1.0, 3.0)
    assert res["status"][0] == "not-achieved-in-window"


def test_fall_and_divergence_are_separate_statuses():
    inside = np.zeros((3, 400), dtype=bool)
    fell = np.array([True, False, False])
    div = np.array([False, True, False])
    run = _fake_run(inside, fell=fell, diverged=div, fall_time=np.array([1.5, np.inf, np.inf]))
    res = metrics.time_to_hold(run, inside, 1.0, 3.0)
    assert list(res["status"]) == ["fell", "diverged", "not-achieved-in-window"]
    assert np.isnan(res["rmst"][1]) and res["rmst"][0] == res["rmst"][2] == 2.0


def test_search_starts_at_the_peak_not_at_the_push():
    """Regression: a body still inside the band just after the push (before it has moved) used to count as recovered."""
    inside = np.zeros((1, 700), dtype=bool)
    inside[0, 320:380] = True                         # inside right after the push at 3.2 s ...
    inside[0, 480:560] = True                         # ... and genuinely recovered from 4.8 s on
    run = _fake_run(inside)
    early = metrics.time_to_hold(run, inside, 3.2, 6.0)                       # naive start: finds the early stay
    assert early["time"][0] < 0.5
    from_peak = metrics.time_to_hold(run, inside, 3.2, 6.0, start_idx=np.array([400]))
    assert abs(from_peak["time"][0] - 1.6) < 1e-9


def test_summary_has_status_columns_and_windows_are_bounded_by_protocol_events():
    cfg = base_config("machine-like-planar")
    ev = metrics.events(cfg)
    assert metrics.window_end(ev, ev["cue"]) == ev["pushes"][0]
    assert metrics.window_end(ev, ev["pushes"][0]) == ev["turn"]
    assert metrics.window_end(ev, ev["turn"]) == ev["horizon"]
    m = metrics.summary(engine.simulate(cfg, [1, 2, 3]))
    for k in ("recovery", "settle_cue", "settle_turn"):
        assert k in m and f"{k}_status" in m and f"{k}_window" in m and f"{k}_rmst" in m


def test_intervention_pushes_do_not_cut_the_protocol_windows():
    cfg = config.apply_intervention(base_config("human-like-planar"), "perturbation", 40.0)
    ev = metrics.events(cfg)
    assert len(ev["pushes"]) == 1                     # only the protocol's own push defines windows
    assert any(p.get("role") == "intervention" for p in cfg["environment"]["pushes"])


def test_tolerance_bands_are_the_pre_registered_rule_and_not_tuned_to_results():
    for preset, family in (("human-like-planar", "human-like"), ("machine-like-planar", "machine-like")):
        assert metrics.calibrate_band(preset) == metrics.TOLERANCE[family]["band"]
    assert not set(metrics.EXPLORATION_SEEDS) & set(range(metrics.FINAL_SEED_BASE, metrics.FINAL_SEED_BASE + 1000))
