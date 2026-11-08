"""Observation vs reference, boundary transformation, reconfiguration (Experiments A and E)."""

from __future__ import annotations

import numpy as np
import pytest

from xzr.xbtro import engine, experiments, observation, tro
from xzr.xbtro.experiments import base_config

SEEDS = [5000 + i for i in range(12)]


@pytest.fixture(scope="module")
def pair():
    a = base_config("human-like-planar")
    b = experiments.alteration(a, "mixed")
    return a, b, engine.simulate(a, SEEDS), engine.simulate(b, SEEDS)


def _noise_rows(rows):
    return [(r["model"], r["field"], r["value"]) for r in rows]


def test_noise_halving_is_applied_to_the_current_value_in_every_round():
    """Experiment A / E: each 'better instrument' step halves the model's CURRENT noise, not a fixed 0.5."""
    a = base_config("human-like-planar")
    obs = observation.validate(observation.config("motion+emg+contact"))
    emg = next(m for m in obs["models"] if m["kind"] == "emg")
    current = []
    for _ in range(4):
        rows = [{"id": "cocontraction", "status": "noise-limited", "reason": None, "reference": {"exists": True, "d": 5.0}}]
        cands = tro.candidates(rows, obs, a)
        emg_c = [c for c in cands if c["changes"] and c["changes"][0].get("model") == emg["id"]]
        if not emg_c:
            break
        new = emg_c[0]["changes"][0]["value"]
        current.append((emg["noise"], new))
        assert new == pytest.approx(emg["noise"] * 0.5, rel=1e-3)
        obs = tro.boundary_transformation(obs, emg_c[0]["changes"])["observation"]
        emg = next(m for m in obs["models"] if m["id"] == emg["id"])
    assert len(current) >= 3
    assert [round(n, 4) for _, n in current] == [round(1.0 * 0.5**k, 4) for k in range(1, len(current) + 1)]


def test_candidates_stop_halving_at_the_floor():
    a = base_config("human-like-planar")
    obs = observation.validate(observation.config("motion+emg+contact"))
    for m in obs["models"]:
        m["noise"] = 0.05
    rows = [{"id": "cocontraction", "status": "noise-limited", "reason": None, "reference": {"exists": True, "d": 5.0}}]
    assert not [c for c in tro.candidates(rows, obs, a) if c["changes"] and c["changes"][0].get("field") == "noise"]


def test_experiment_a_log_shows_cumulative_halving():
    rec, _ = experiments.run_to_end("A", {"n_seeds": 12, "seed": 5000, "rounds": 5})
    seen: dict[str, list[float]] = {}
    for g in rec["results"]["reconfiguration"]:
        for ch in g.get("changes", []):
            if ch.get("op") == "set" and ch.get("field") == "noise":
                seen.setdefault(ch["model"], []).append(ch["value"])
    assert seen, "expected at least one noise reduction to be logged"
    for vals in seen.values():
        for prev, nxt in zip(vals, vals[1:], strict=False):
            assert nxt == pytest.approx(prev / 2, rel=1e-3)


def test_observation_never_changes_the_reference(pair):
    a, _, ra, _ = pair
    before = ra["com"].copy()
    for kind in ("motion-only", "motion+emg+contact", "full"):
        observation.observe(ra, observation.validate(observation.config(kind)))
    assert np.array_equal(before, ra["com"])


def test_changing_the_observation_changes_the_measurement_not_the_body(pair):
    _, _, ra, _ = pair
    o1 = observation.observe(ra, observation.validate(observation.config("motion-only")))
    o2 = observation.observe(ra, observation.validate(observation.config("motion+emg+contact")))
    assert set(o2) - set(o1)  # new streams appear only when the devices exist


def test_identifiability_depends_on_the_observation_configuration(pair):
    _, _, ra, rb = pair
    ref = tro.reference_effects(ra, rb)
    s1 = tro.summarize(tro.assess(ra, rb, observation.validate(observation.config("motion-only")), ref))
    s2 = tro.summarize(tro.assess(ra, rb, observation.validate(observation.config("motion+emg+contact")), ref))
    assert s2["identified"] > s1["identified"]
    assert s1["existing"] == s2["existing"]  # what exists in the model reference does not depend on the instruments


def test_unobserved_reasons_are_kept_apart(pair):
    _, _, ra, rb = pair
    rows = tro.assess(ra, rb, observation.validate(observation.config("motion-only")))
    reasons = {r["reason"] for r in rows if r["status"] == "unobserved"}
    assert reasons <= {
        "unmeasured",
        "device-mismatch",
        "scale-mismatch",
        "time-window-mismatch",
        "boundary-invisible",
        "measurement-impossible",
    }
    assert len(reasons) >= 2
    absent = [r for r in rows if r["status"] == "no-difference-in-model"]
    assert absent and all(not r["reference"]["exists"] for r in absent)  # absence in the model is not the same as not measured


def test_reconfiguration_records_reason_information_expectation_and_result():
    rec, _ = experiments.run_to_end("A", {"n_seeds": 12, "seed": 5000, "rounds": 2})
    g = rec["results"]["reconfiguration"][0]
    for key in ("reason", "information_used", "expected", "actual", "changes", "setup_time_s"):
        assert key in g
    assert "identified_before" in g["actual"] and "identified_after" in g["actual"]
