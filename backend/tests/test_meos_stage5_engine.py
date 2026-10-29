"""MEOS-0, fifth stage, engine: the new parameters and the ROUTE operation are opt-in, validated, replayable, and leave the baseline and every earlier trace unchanged."""

from __future__ import annotations

import pytest

from xzr.meos import engine as E
from xzr.meos import stage4 as S4

BASELINE = "b4cf1e522e8bee460eab30ee2a3f86ffd703a3f7969dc21271cf0240aa09adc5"


def run(ivs=None, **cfg):
    return E.run_record(E.default_config(**cfg), ivs or [])


def test_the_baseline_digest_and_the_version():
    r = run()
    assert E.ENGINE_VERSION == "meos-0.4" and r["result_digest"] == BASELINE and "m2_sensed" not in r["traces"]


@pytest.mark.parametrize("path,neutral", [("coupling.gain", 1.0), ("environment.renew_delay", 0), ("history.lag", 0)])
def test_each_new_parameter_at_its_neutral_value_leaves_the_dynamics_unchanged(path, neutral):
    base = run()
    r = run([{"tick": 50, "op": "RECONFIGURE", "path": path, "value": neutral}])
    assert S4.dynamics_digest(r) == S4.dynamics_digest(base)  # the result digest differs (the intervention is logged); the frames do not


@pytest.mark.parametrize("path,value,tick", [("coupling.gain", 0.5, 50), ("environment.renew_delay", 6, 50), ("history.lag", 30, 0)])
def test_each_new_parameter_changes_the_dynamics_when_set_and_replays(path, value, tick):
    # a history lag matters only while the delayed trace is lower than the current one, i.e. while the history is forming: set from tick 0 (a measured property, see the document)
    r = run([{"tick": tick, "op": "RECONFIGURE", "path": path, "value": value}])
    assert S4.dynamics_digest(r) != S4.dynamics_digest(run())
    assert E.replay(r)["identical"]


def test_the_new_parameters_are_range_checked():
    for path, bad in (("coupling.gain", 3.0), ("environment.renew_delay", 99), ("history.lag", -1)):
        with pytest.raises(E.MeosError):
            run([{"tick": 5, "op": "RECONFIGURE", "path": path, "value": bad}])


def test_a_weakened_coupling_weakens_what_a2_receives_and_nothing_else_is_scaled():
    r = run([{"tick": 0, "op": "RECONFIGURE", "path": "coupling.gain", "value": 0.5}])
    b = run()
    assert max(r["traces"]["interaction_strength"]) < max(b["traces"]["interaction_strength"])  # A2's alteration signal
    assert r["traces"]["reconfiguration_signal"][:5] == b["traces"]["reconfiguration_signal"][:5]  # A1's resource signal is untouched in the first ticks


def test_a_delayed_renewal_reaches_the_field_later():
    r = run([{"tick": 0, "op": "RECONFIGURE", "path": "environment.renew_delay", "value": 5}])
    assert r["final_config"]["environment"]["renew_delay"] == 5 and E.replay(r)["identical"]


def test_route_validates_applies_and_logs_its_metadata():
    for bad in ({"op": "ROUTE"}, {"op": "ROUTE", "m2": {"sense": "x"}}, {"op": "ROUTE", "history": "maybe"}):
        with pytest.raises(E.MeosError):
            run([{"tick": 10, **bad}])
    r = run([{"tick": 60, "op": "ROUTE", "m2": {"sense": "direct", "weight": 4.0}, "history": "off", "why": "test", "from": "a", "to": "b", "cost": 2}])
    log = next(i for i in r["intervention_log"] if i["op"] == "ROUTE")
    assert log["m2"]["sense"] == "direct" and log["history"] == "off" and log["why"] == "test" and log["cost"] == 2
    assert r["final_config"]["history"]["enabled"] is False and r["final_config"]["m2"]["sense"] == "direct"
    assert E.replay(r)["identical"]


def test_switching_m2_on_during_a_run_keeps_the_trace_the_length_of_the_run():
    r = run([{"tick": 60, "op": "ROUTE", "m2": {"sense": "direct", "weight": 4.0}}])
    tr = r["traces"]["m2_sensed"]
    assert len(tr) == len(r["frames"]) and all(v == 0.0 for v in tr[:60]) and max(tr) > 0  # nothing was sensed before the tap was switched on


def test_inject_schedules_for_the_next_tick_and_the_recorded_schedule_replays_without_the_controller():
    cfg = E.default_config()
    live = E.Run(cfg, [])
    while True:
        if live.t == 80:
            live.inject({"op": "ROUTE", "m2": {"sense": "direct", "weight": 4.0}})
            live.inject({"op": "RECONFIGURE", "path": "coupling.gain", "value": 0.8})
        if not live.step():
            break
    rec = live.record()
    assert [i["tick"] for i in rec["interventions"]] == [81, 81]
    again = E.run_record(cfg, rec["interventions"])
    assert again["frames"] == rec["frames"] and again["events"] == rec["events"]


def test_inject_validates():
    r = E.Run(E.default_config(), [])
    with pytest.raises(E.MeosError):
        r.inject({"op": "ROUTE"})
