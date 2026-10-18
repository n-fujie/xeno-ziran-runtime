"""Historical re-entry: records feed later experiments; re-observation of a simulation is labelled as such."""

from __future__ import annotations

import pytest

from xzr.xbtro import experiments, history, observation, records

N = 4


def _state(fatigue, energy, kc=1.0):
    return {
        "fatigue": [fatigue] * N,
        "energy": [energy] * N,
        "kc": [kc] * N,
        "sediment": [0.0] * N,
        "core": [0.2] * N,
        "hand": [0.0] * N,
    }


def test_rerun_reproduces_the_parent_and_records_the_link():
    a, slow = experiments.run_to_end("B", {"n_seeds": N})
    h = records.HistoryStore()
    h.add(a, slow)
    b, _ = history.rerun(a)
    assert b["history"]["parent"] == a["id"] and b["history"]["same_digest_as_parent"] is True


def test_reanalysis_is_labelled_as_re_observation_of_a_simulation_and_changes_what_is_identified():
    a, _ = experiments.run_to_end("A", {"n_seeds": 8, "rounds": 1})
    poor = history.reanalyse(a, observation.config("motion-only"))
    rich = history.reanalyse(a, observation.config("full"))
    assert poor["results"]["re_observation_of_a_simulation"] and "not a new measurement" in poor["results"]["reading"]
    assert rich["results"]["summary"]["identified"] > poor["results"]["summary"]["identified"]
    assert poor["history"]["parent"] == a["id"] and poor["history"]["reentry"][0]["kind"] == "re-observation"
    # the unobserved differences of the poorer configuration are carried into the registry and found again by the richer one
    h = records.HistoryStore()
    h.add(a)
    h.add(poor)
    h.add(rich)
    reg = {e["id"]: e for e in h.registry()}
    assert any(e["identified_later"] for e in reg.values())


def test_a_derived_record_cannot_be_repeated_and_other_records_cannot_be_reanalysed():
    a, _ = experiments.run_to_end("A", {"n_seeds": 4, "rounds": 1})
    re = history.reanalyse(a, observation.config("full"))
    with pytest.raises(history.HistoryError):
        history.rerun(re)
    b, _ = experiments.run_to_end("B", {"n_seeds": N})
    with pytest.raises(history.HistoryError):
        history.reanalyse(b, observation.config("full"))


def test_slow_state_reentry_changes_what_later_operations_do():
    """What happened before (fatigue, spent energy) changes the later experiment: the same protocol, same seeds, different start."""
    fresh, _ = experiments.run_to_end("B", {"n_seeds": N})
    tired, _ = experiments.run_to_end("B", {"n_seeds": N, "carry_over": _state(0.8, 0.35)})
    f = {r[1]: r[2] for r in fresh["results"]["tables"][0]["rows"][:6]}  # control means appear in column 2 of the first rows
    t = {r[1]: r[2] for r in tired["results"]["tables"][0]["rows"][:6]}
    assert fresh["digest"] != tired["digest"]
    assert any(abs((f[k] or 0) - (t[k] or 0)) > 1e-6 for k in f)
    assert tired["parameters"]["carry_over"]["fatigue"] == [0.8] * N  # stored: the re-entry can be repeated


def test_reenter_uses_the_stored_slow_state_of_a_record():
    a, slow = experiments.run_to_end("B", {"n_seeds": N})
    h = records.HistoryStore()
    h.add(a, slow)
    b, _ = history.reenter(h, a["id"], "B", {"n_seeds": N})
    assert b["history"]["operation"] == "reenter" and b["history"]["reentry"][0]["from"] == a["id"]
    assert set(b["parameters"]["carry_over"]) == {"fatigue", "energy", "kc", "sediment", "core", "hand"}
    with pytest.raises(history.HistoryError):
        history.carried_state(records.HistoryStore(), "nope")
