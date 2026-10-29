"""MEOS-0, fifth stage: world-responsive reconfiguration and the route topology. The controller reads only the run's traces, switches only between library MFS, records everything it
senses and does, and leaves a schedule that replays the run without it."""

from __future__ import annotations

import dataclasses
import json

import pytest
from fastapi.testclient import TestClient

from xzr.meos import engine as E
from xzr.meos import mfs5 as M
from xzr.meos import reconf as RC
from xzr.meos import routes5 as R
from xzr.service import app as app_mod
from xzr.service import meos as svc
from xzr.service import studies as studies_mod
from xzr.service.limits import LIMITS

ARR = {"tap": M.M2_BASE, "tap_feature": "direct", "universe": M.COMPONENTS5}
NORMAL = {"history": "ok", "coupling": "normal", "resource": "normal", "renewal": "normal", "address": "ok", "tap": "direct"}
# a hand-made library (the real one is experiment F's): under 'history lost' the route is the history-free set, under 'coupling weak' it needs the resource gradient
CORE = ["A2", "interaction_channel", "sensor_resource", "sensor_alteration", "environmental_persistence", "feedback", "resource_renewal"]
LIB = [
    {"id": "L-BASE", "condition_id": "B", "features": dict(NORMAL), "retained": CORE, "cardinality": 7},
    {"id": "L-NOHIST", "condition_id": "H", "features": {**NORMAL, "history": "lost"}, "retained": CORE, "cardinality": 7},
    {"id": "L-WEAK", "condition_id": "W", "features": {**NORMAL, "coupling": "weak"}, "retained": [*CORE, "m2_tap"], "cardinality": 8},
]
START = [{"tick": 0, "op": "ROUTE", "m2": {"sense": "none"}}]


def cfg(seed=1, horizon=240):
    return E.default_config(seed=seed, horizon=horizon)


def test_no_controller_is_the_plain_run():
    a = RC.run_controlled(cfg(), START, None)
    b = E.run_record(cfg(), START)
    assert a["result_digest"] == b["result_digest"] if "result_digest" in a else a["frames"] == b["frames"]
    assert a["controller"]["kind"] == "none" and a["controller"]["switches"] == 0


def test_enabled_components_are_read_from_the_configuration():
    run = E.Run(cfg(), [*START, {"tick": 0, "op": "REMOVE", "target": "history"}])
    on = RC.enabled_components(run, M.COMPONENTS5)
    assert "history" not in on and "m2_tap" not in on and "feedback" in on and "A2" in on
    run.inject({"op": "ROUTE", "m2": {"sense": "direct", "weight": 4.0}})
    run.step()
    assert "m2_tap" in RC.enabled_components(run, M.COMPONENTS5)


def test_sensing_comes_from_the_traces_and_sees_a_history_that_lowers_nothing():
    quiet = E.Run(cfg(), START)
    lost = E.Run(cfg(), [*START, {"tick": 90, "op": "REMOVE", "target": "history"}])
    for r in (quiet, lost):
        while r.t < 120:
            r.step()
    assert RC.sense(quiet)["history"] == "ok" and RC.sense(lost)["history"] == "lost"
    weak = E.Run(cfg(), [*START, {"tick": 90, "op": "RECONFIGURE", "path": "coupling.gain", "value": 0.3}])
    while weak.t < 120:
        weak.step()
    assert RC.sense(weak)["coupling"] == "weak"
    faulty = E.Run(cfg(), [*START, {"tick": 90, "op": "ADDRESS", "target": "A2", "mode": "partial", "fraction": 0.5}])
    while faulty.t < 120:
        faulty.step()
    assert RC.sense(faulty)["address"] == "degraded"


def test_an_adaptive_controller_switches_to_a_library_route_and_records_why():
    ivs = [*START, {"tick": 100, "op": "RECONFIGURE", "path": "coupling.gain", "value": 0.3}]
    ctl = RC.Controller("adaptive", LIB, ARR)
    rec = RC.run_controlled(cfg(horizon=300), ivs, ctl)
    sw = [e for e in rec["controller"]["log"] if e["kind"] == "switch"]
    assert sw and sw[0]["to"] == "L-WEAK" and sw[0]["enabled"] == ["m2_tap"] and sw[0]["trigger"] == ["coupling"] and sw[0]["tick"] >= 100
    decide = next(e for e in rec["controller"]["log"] if e["kind"] == "decide")
    assert decide["sensed"]["coupling"] == "weak" and decide["candidates"][0]["mfs"] == "L-WEAK"
    routed = [i for i in rec["intervention_log"] if i["op"] == "ROUTE" and "why" in i]
    assert routed and routed[0]["to"] == "L-WEAK" and routed[0]["cost"] == 1
    assert E.replay(rec)["identical"]  # the recorded schedule replays the run without the controller


def test_nothing_is_switched_when_nothing_is_wrong_or_when_the_chosen_route_is_already_in_place():
    ctl = RC.Controller("adaptive", LIB, ARR)
    rec = RC.run_controlled(cfg(), START, ctl)
    assert rec["controller"]["switches"] == 0
    # history lost: the library route under that condition (L-NOHIST) needs nothing that is not enabled: no switch
    ctl2 = RC.Controller("adaptive", LIB, ARR)
    rec2 = RC.run_controlled(cfg(horizon=260), [*START, {"tick": 90, "op": "REMOVE", "target": "history"}], ctl2)
    first = next(e for e in rec2["controller"]["log"] if e["kind"] == "decide")
    assert first["trigger"] == ["history"] and first["outcome"].startswith("no switch") and first["chosen"] == "L-NOHIST"
    # (what the run does afterwards is another matter: without history the default arrangement may collapse, and the controller then reacts to what it senses of the collapse)


def test_a_controller_never_enables_a_component_it_found_broken():
    lib = [{"id": "NEEDS-H", "condition_id": "H", "features": {**NORMAL, "history": "lost"}, "retained": [*CORE, "history"], "cardinality": 8}]
    rec = RC.run_controlled(cfg(horizon=260), [*START, {"tick": 90, "op": "REMOVE", "target": "history"}], RC.Controller("adaptive", lib, ARR))
    assert rec["controller"]["switches"] == 0
    assert any("no known route" in str(e.get("outcome", "")) for e in rec["controller"]["log"])


def test_the_fixed_controller_does_the_same_whatever_was_sensed_and_the_delayed_one_acts_later():
    ivs = [*START, {"tick": 100, "op": "RECONFIGURE", "path": "coupling.gain", "value": 0.3}]
    fixed = RC.run_controlled(cfg(horizon=300), ivs, RC.Controller("fixed", LIB, ARR))
    adaptive = RC.run_controlled(cfg(horizon=300), ivs, RC.Controller("adaptive", LIB, ARR))
    delayed = RC.run_controlled(cfg(horizon=300), ivs, RC.Controller("delayed", LIB, ARR, delay=15))
    t = lambda r: next(e["tick"] for e in r["controller"]["log"] if e["kind"] == "switch")  # noqa: E731
    assert [e["to"] for e in fixed["controller"]["log"] if e["kind"] == "switch"] == ["fixed fallback"]
    assert t(delayed) == t(adaptive) + 15 and E.replay(delayed)["identical"]


def test_a_noisy_controller_can_switch_for_nothing_and_that_is_recorded():
    n = 0
    for sd in range(1, 6):
        rec = RC.run_controlled(cfg(seed=sd), START, RC.Controller("noisy", LIB, ARR, noise=0.3, seed=sd))
        n += rec["controller"]["switches"]
    assert n > 0  # a sensed environment that is wrong at random produces switches in runs with no stress at all


def test_switch_outcomes_say_what_a_switch_cost_and_whether_it_helped():
    ivs = [*START, {"tick": 100, "op": "RECONFIGURE", "path": "coupling.gain", "value": 0.3}]
    rec = RC.run_controlled(cfg(horizon=300), ivs, RC.Controller("adaptive", LIB, ARR))
    out = RC.switch_outcomes(rec, 100)[0]
    assert out["cost"] == 1 and out["from"] and out["to"] == "L-WEAK" and isinstance(out["preserved_at_end"], bool) and out["operation_lost_ticks_after"] >= 0


def test_topology_is_read_from_the_record():
    ivs = [*START, {"tick": 100, "op": "REMOVE", "target": "history"}, {"tick": 120, "op": "ROUTE", "m2": {"sense": "direct", "weight": 4.0}, "why": "w", "from": "a", "to": "b", "cost": 1, "trigger": "history"}]
    rec = E.run_record(cfg(), ivs)
    topo = R.topology(rec)
    tl = topo["component_timeline"]
    assert tl["history"] == [[0, True], [100, False]] and tl["m2_tap"] == [[0, False], [120, True]]
    assert topo["failed_components"] == {"history": {"op": "REMOVE", "tick": 100}} and topo["installed_m2_tap"]
    assert topo["route_events"][-1]["controlled"] is True and topo["route_events"][-1]["to"] == "b"
    assert topo["paths"]["m2"] == ["m2_tap"] and topo["controller"] == "none"


@pytest.fixture(scope="module")
def client():
    return TestClient(app_mod.app)


def test_the_routes_and_their_guards(client, tmp_path, monkeypatch):
    saved = tmp_path / "s5.json"
    f = {"by_condition": {"B": {"condition": {"label": "base"}, "mfs": [{"id": "L-BASE", "environment_condition": {"features": NORMAL}, "retained_components": CORE, "removed_components": ["history"], "cardinality": 7, "route_kind": "x", "retained_paths": [], "lost_paths": [], "digest": "d"}]}}, "levels": ["L1"]}
    saved.write_text(json.dumps({"experiments": {"F": f}}))
    monkeypatch.setattr(svc, "STAGE5_FILE", saved)
    assert client.get("/api/meos/mfs-library").json()["mfs"][0]["id"] == "L-BASE"
    t = client.post("/api/meos/route-topology", json={"interventions": [{"tick": 50, "op": "REMOVE", "target": "history"}]}).json()
    assert t["topology"]["component_timeline"]["history"][-1] == [50, False] and t["library"][0]["id"] == "L-BASE"
    r = client.post("/api/meos/reconfigure", json={"controller": "adaptive", "scenario": "coupling weakened (gain 0.5)", "seed": 1}).json()
    assert r["replay_identical"] is True and r["controller"]["kind"] == "adaptive" and "topology" in r
    for body in ({"controller": "x"}, {"scenario": "x"}, {"seed": "a"}):
        assert client.post("/api/meos/reconfigure", json=body).status_code == 422
    monkeypatch.setattr(svc, "STAGE5_FILE", tmp_path / "missing.json")
    assert client.get("/api/meos/mfs-library").status_code == 404
    monkeypatch.setattr(studies_mod, "LIMITS", dataclasses.replace(LIMITS, public=True))
    for method, path in (("get", "/api/meos/mfs-library"), ("post", "/api/meos/route-topology"), ("post", "/api/meos/reconfigure")):
        assert getattr(client, method)(path, **({"json": {}} if method == "post" else {})).status_code == 403, path


def test_a_shedding_controller_also_removes_what_the_destination_does_not_retain():
    # the destination MFS (L-NOHIST) retains neither history nor the resource gradient: the enable-only controller has nothing to enable (its first decision is "no switch"), the shedding one removes the gradient
    ivs = [*START, {"tick": 90, "op": "REMOVE", "target": "history"}]
    first = lambda r: next(e for e in r["controller"]["log"] if e["kind"] == "decide")  # noqa: E731
    plain = RC.run_controlled(cfg(horizon=300), ivs, RC.Controller("adaptive", LIB, ARR))
    shed = RC.run_controlled(cfg(horizon=300), ivs, RC.Controller("adaptive_shed", LIB, ARR))
    assert first(plain)["outcome"].startswith("no switch")
    assert first(shed)["chosen"] == "L-NOHIST" and "resource_gradient" in first(shed)["shed"] and first(shed)["cost"] >= 1
    sw = next(e for e in shed["controller"]["log"] if e["kind"] == "switch")
    assert "resource_gradient" in sw["shed"] and sw["enabled"] == []
    assert any(i["op"] == "REMOVE" and i["target"] == "resource_gradient" for i in shed["intervention_log"])
    assert E.replay(shed)["identical"]
