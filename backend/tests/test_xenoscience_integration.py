"""XENOSCIENCE ECOSYSTEM — the boundary between the interface and the MEOS engine.

The view may only ask the engine to run and read what it returns.
An intervention request made through the API must give the record
that the engine gives when called directly.
An observation configuration must not change the run it observes.
A request the engine refuses must leave no record.
These are the properties the interface's provenance panel relies on."""

from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from xzr.meos import analysis as A
from xzr.meos import engine as E
from xzr.service import app as app_mod

INTERVENTION_LISTS = [
    [],
    [
        {"tick": 100, "op": "ISOLATE", "target": "interaction_channel"},
        {"tick": 150, "op": "RECONNECT", "target": "interaction_channel"},
    ],
    [{"tick": 100, "op": "REMOVE", "target": "A2"}],
    [
        {"tick": 100, "op": "ISOLATE", "target": "interaction_channel"},
        {"tick": 150, "op": "RECONNECT", "target": "interaction_channel"},
        {"tick": 151, "op": "ALTER_RESOURCE", "inject": {"x": 3, "y": 6, "amount": 2.0}},
    ],
]


@pytest.fixture
def client():
    return TestClient(app_mod.app, headers={"origin": "http://testserver"})


@pytest.mark.parametrize("ivs", INTERVENTION_LISTS)
def test_an_intervention_request_gives_the_record_the_engine_gives_directly(client, ivs):
    direct = E.run_record(E.default_config(), copy.deepcopy(ivs))
    via = client.post("/api/meos/run", json={"interventions": ivs}).json()["record"]
    for k in (
        "initial_config_digest",
        "result_digest",
        "trace_digest",
        "full_digest",
        "interventions",
        "intervention_log",
        "status_log",
        "final_status",
        "termination",
    ):
        assert via[k] == direct[k], k
    assert via["frames"] == direct["frames"]


@pytest.mark.parametrize(
    "obs", [{"sampling_interval": 12}, {"sampling_interval": 3, "spatial_stride": 2}, {"region": [0, 0, 6, 13], "window": 24}]
)
def test_an_observation_configuration_does_not_change_the_run_it_observes(client, obs):
    ivs = INTERVENTION_LISTS[1]
    plain = client.post("/api/meos/run", json={"interventions": ivs}).json()
    seen = client.post("/api/meos/run", json={"interventions": ivs, "observation": obs}).json()
    assert seen["record"]["result_digest"] == plain["record"]["result_digest"]
    assert seen["record"]["full_digest"] == plain["record"]["full_digest"]
    assert seen["record"]["frames"] == plain["record"]["frames"]
    assert "observed" in seen and "observed" not in plain
    # the observation reports the run's own status apart from the observed one
    assert seen["observed"]["operational_state"] == plain["record"]["final_status"]["label"]


def test_the_observed_cycles_are_a_subset_of_the_cycles_the_run_contains(client):
    rec = client.post("/api/meos/run", json={"interventions": INTERVENTION_LISTS[1]}).json()["record"]
    full = A.observe(rec, {})
    coarse = A.observe(rec, {"sampling_interval": 12})
    assert full["true_cycles"] == coarse["true_cycles"] == len(rec["cycles"])
    assert coarse["observed_cycles"] <= full["observed_cycles"] <= full["true_cycles"]


def test_every_accepted_request_is_a_row_of_the_engine_log_in_order():
    ivs = INTERVENTION_LISTS[3]
    rec = E.run_record(E.default_config(), ivs)
    assert [(lg["tick"], lg["op"]) for lg in rec["intervention_log"]] == [(i["tick"], i["op"]) for i in ivs]
    assert len({lg["event"] for lg in rec["intervention_log"]}) == len(ivs)


def test_a_request_the_engine_refuses_leaves_no_record(client):
    r = client.post("/api/meos/run", json={"interventions": [{"tick": 10, "op": "TELEPORT", "target": "A1"}]})
    assert 400 <= r.status_code < 500
    assert "record" not in r.json()
    r2 = client.post("/api/meos/run", json={"interventions": [{"tick": 10, "op": "REMOVE", "target": "no_such_component"}]})
    assert 400 <= r2.status_code < 500 and "record" not in r2.json()


def test_the_engine_is_deterministic_for_the_interface(client):
    a = client.post("/api/meos/run", json={"interventions": INTERVENTION_LISTS[3]}).json()["record"]
    b = client.post("/api/meos/run", json={"interventions": INTERVENTION_LISTS[3]}).json()["record"]
    assert a["full_digest"] == b["full_digest"] and a["frames"] == b["frames"]


def js(x):
    """What JSON.stringify does to a number: 1.0 is written 1 (a browser cannot keep the difference)."""
    if isinstance(x, float) and x == int(x):
        return int(x)
    if isinstance(x, dict):
        return {k: js(v) for k, v in x.items()}
    if isinstance(x, list):
        return [js(v) for v in x]
    return x


@pytest.mark.parametrize("ivs", INTERVENTION_LISTS)
def test_a_record_replays_after_a_round_trip_through_javascript_numbers(client, ivs):
    rec = client.post("/api/meos/run", json={"config": {"seed": 1, "horizon": 360}, "interventions": ivs}).json()["record"]
    own = client.post(
        "/api/meos/replay",
        json={"config": rec["config"], "interventions": rec["interventions"], "result_digest": rec["result_digest"]},
    ).json()
    via_js = client.post(
        "/api/meos/replay",
        json={"config": js(rec["config"]), "interventions": js(rec["interventions"]), "result_digest": rec["result_digest"]},
    ).json()
    assert own["identical"] is True
    assert via_js["identical"] is True, via_js


def test_a_run_does_not_depend_on_whether_a_whole_number_is_written_as_a_float(client):
    # power.capacity and sss.scale / size / speed are the values whose digest changes with the written type
    # (found by trying every whole-number float of the default configuration)
    as_float = client.post(
        "/api/meos/run", json={"config": {"power": {"capacity": 24.0}, "sss": {"scale": 1.0, "size": 1.0, "speed": 1.0}}}
    ).json()["record"]
    as_int = client.post(
        "/api/meos/run", json={"config": {"power": {"capacity": 24}, "sss": {"scale": 1, "size": 1, "speed": 1}}}
    ).json()["record"]
    assert as_int["result_digest"] == as_float["result_digest"] and as_int["full_digest"] == as_float["full_digest"]
    assert as_int["config"] == as_float["config"]


def test_a_value_the_engine_has_no_default_for_is_left_as_given(client):
    out = client.post("/api/meos/run", json={"config": {"m2": {"sense": "direct", "weight": 1}}}).json()["record"]
    assert out["config"]["m2"]["weight"] == 1 and isinstance(out["config"]["m2"]["weight"], int)


def test_digests_of_runs_made_from_python_typed_configs_are_unchanged():
    # the fix reads numbers at the API boundary only: a run made by the engine itself keeps the digests the stored records pin
    assert E.run_record(E.default_config(horizon=360), [])["result_digest"].startswith("4b08c75a")
    assert E.run_record(E.default_config(horizon=360), [{"tick": 100, "op": "DISABLE_HISTORY"}])["result_digest"].startswith(
        "835cce00"
    )
