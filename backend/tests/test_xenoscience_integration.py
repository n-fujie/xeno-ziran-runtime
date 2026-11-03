"""XENOSCIENCE ECOSYSTEM — the boundary between the interface and the MEOS engine.

The view may only ask the engine to run and read what it returns.
An intervention request made through the API must give the record
that the engine gives when called directly.
An observation configuration must not change the run it observes.
A request the engine refuses must leave no record.
These are the properties the interface's provenance panel relies on."""

from __future__ import annotations

import copy
import json
from pathlib import Path

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


# numeric types over the stored records

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src" / "views" / "ecosystem"
FIXTURES = FRONTEND / "__fixtures__"


def stored_records() -> dict[str, dict]:
    out = {}
    for name in ("meos-stage2", "meos-a2-removed"):
        out[name] = json.loads((FIXTURES / f"{name}.json").read_text())
    for k, v in json.loads((FIXTURES / "meos-coupling-cut.json").read_text()).items():
        out[f"coupling-{k}"] = v
    out["stage5-controlled"] = json.loads((FIXTURES / "meos-stage5-controlled.json").read_text())["record"]
    return out


@pytest.mark.parametrize("name", list(stored_records()))
def test_every_stored_record_replays_both_as_python_wrote_it_and_through_javascript_numbers(client, name):
    rec = stored_records()[name]
    py = client.post(
        "/api/meos/replay",
        json={"config": rec["config"], "interventions": rec["interventions"], "result_digest": rec["result_digest"]},
    ).json()
    via_js = client.post(
        "/api/meos/replay",
        json={"config": js(rec["config"]), "interventions": js(rec["interventions"]), "result_digest": rec["result_digest"]},
    ).json()
    assert py["identical"] is True and py["interpretation"] == "as_received" and py["verification"] == "VERIFIED_AS_RECEIVED"
    assert via_js["identical"] is True, via_js


def test_a_record_a_server_made_with_a_whole_number_float_needs_the_reading_and_says_so(client):
    # the stage-5 controlled run: a ROUTE intervention carries m2.weight 4.0, which a browser writes 4
    rec = stored_records()["stage5-controlled"]
    via_js = client.post(
        "/api/meos/replay",
        json={"config": js(rec["config"]), "interventions": js(rec["interventions"]), "result_digest": rec["result_digest"]},
    ).json()
    assert via_js["identical"] is True and via_js["verification"] == "VERIFIED_BY_READING"
    assert (
        via_js["interpretation"] == "interventions_as_floats"
    )  # the configuration was already right: only the interventions needed the reading


def test_the_two_readings_run_the_same_computation_only_the_digest_differs():
    rec = stored_records()["stage5-controlled"]
    a = E.run_record(rec["config"], rec["interventions"])
    b = E.run_record(rec["config"], js(rec["interventions"]))
    assert a["result_digest"] != b["result_digest"]
    for k in ("frames", "events", "cycles", "status_log", "final_status", "termination"):
        assert a[k] == b[k], k


def test_a_digest_that_nothing_reproduces_is_never_called_identical(client):
    rec = stored_records()["stage5-controlled"]
    out = client.post(
        "/api/meos/replay",
        json={"config": js(rec["config"]), "interventions": js(rec["interventions"]), "result_digest": "0" * 64},
    ).json()
    assert (
        out["identical"] is False
        and out["interpretation"] == "none_reproduces_the_digest"
        and out["verification"] == "NOT_REPRODUCED"
    )


def test_the_reading_keeps_whole_numbers_where_the_engine_requires_them():
    from xzr.service.meos import _as_float_where_the_engine_reads_one as read

    ivs = [
        {
            "tick": 3,
            "op": "ADDRESS",
            "mode": "delayed",
            "delay": 5,
            "x": 4,
            "y": 2,
            "fraction": 1,
            "duration": 20,
            "inject": {"x": 3, "y": 6, "amount": 2},
            "cost": 1,
        }
    ]
    got = read(ivs)[0]
    assert (got["tick"], got["delay"], got["x"], got["y"], got["duration"], got["cost"]) == (3, 5, 4, 2, 20, 1)
    assert all(isinstance(got[k], int) for k in ("tick", "delay", "x", "y", "duration", "cost"))
    assert (
        isinstance(got["fraction"], float) and isinstance(got["inject"]["amount"], float) and isinstance(got["inject"]["x"], int)
    )
    assert read({"horizon": 360, "entities": {"A1": {"pos": [3, 6], "window": 6, "speed": 1}}}) == {
        "horizon": 360,
        "entities": {"A1": {"pos": [3, 6], "window": 6, "speed": 1.0}},
    }
    assert read({"flag": True}) == {"flag": True}


def test_a_reconfigure_value_takes_the_type_of_the_parameter_it_sets():
    from xzr.service.meos import _reconfigure_values_like_their_parameter as like

    cfg = E.default_config()
    out = like(
        [
            {"tick": 1, "op": "RECONFIGURE", "path": "environment.diffusion", "value": 1},
            {"tick": 1, "op": "RECONFIGURE", "path": "entities.A1.window", "value": 6},
        ],
        cfg,
    )
    assert isinstance(out[0]["value"], float) and isinstance(out[1]["value"], int)


# ---------------------------------------------------------------- the reading must not hide a real mismatch
def replay_js(client, rec, mutate=None):
    cfg, ivs = js(rec["config"]), js(rec["interventions"])
    if mutate:
        cfg, ivs = mutate(copy.deepcopy(cfg), copy.deepcopy(ivs))
    return client.post(
        "/api/meos/replay", json={"config": cfg, "interventions": ivs, "result_digest": rec["result_digest"]}
    ).json()


def test_the_answer_names_the_input_rule_the_candidates_and_the_leaves_each_changed(client):
    out = replay_js(client, stored_records()["stage5-controlled"])
    assert out["rule"].startswith("a whole number is read as a float unless") and out["input_record_digest"]
    names = {c["reading"]: c for c in out["candidates"]}
    assert names["as_received"]["matches"] is False
    assert (
        names["interventions_as_floats"]["matches"] is True
        and "interventions.[3].m2.weight" in names["interventions_as_floats"]["changed_example"]
    )
    assert (
        names["config_and_interventions_as_floats"]["matches"] is True
    )  # a larger reading that also matches only repeats the minimal one
    assert names["config_and_interventions_as_floats"]["changed_leaves"] >= names["interventions_as_floats"]["changed_leaves"]


@pytest.mark.parametrize(
    "what,mutate",
    [
        ("a changed parameter value", lambda c, i: (c, [{**x, "value": 0.4} if x["op"] == "RECONFIGURE" else x for x in i])),
        ("a moved intervention tick", lambda c, i: (c, [{**x, "tick": x["tick"] + 1} if x["op"] == "REMOVE" else x for x in i])),
        ("a different seed", lambda c, i: ({**c, "seed": 2}, i)),
        ("a dropped intervention", lambda c, i: (c, i[:-1])),
    ],
)
def test_a_genuine_difference_in_the_inputs_is_never_verified_by_a_reading(client, what, mutate):
    out = replay_js(client, stored_records()["stage5-controlled"], mutate)
    assert out["identical"] is False, what
    assert out["verification"] == "NOT_REPRODUCED" and out["interpretation"] == "none_reproduces_the_digest"
    assert all(c["matches"] is False for c in out["candidates"])


def test_reading_numbers_as_floats_does_not_change_the_computation_of_any_stored_record():
    from xzr.service.meos import _as_float_where_the_engine_reads_one as read
    from xzr.service.meos import _reconfigure_values_like_their_parameter as like

    for name, rec in stored_records().items():
        cfg2 = read(js(rec["config"]))
        a = E.run_record(js(rec["config"]), js(rec["interventions"]))
        b = E.run_record(cfg2, like(read(js(rec["interventions"])), cfg2))
        for k in ("frames", "events", "cycles", "status_log", "final_status", "termination"):
            assert a[k] == b[k], f"{name}: {k}"


def test_the_choice_among_matching_readings():
    from xzr.service.meos import pick_reading

    assert pick_reading({}) == ("NOT_REPRODUCED", None)
    assert pick_reading({"a": {"x"}}) == ("VERIFIED_BY_READING", "a")
    # nested: the larger reading only repeats the smaller one
    assert pick_reading({"a": {"x"}, "both": {"x", "y"}}) == ("VERIFIED_BY_READING", "a")
    # not nested: two different minimal readings reproduce the digest, so none is chosen
    assert pick_reading({"a": {"x"}, "same": {"x"}}) == ("VERIFIED_BY_READING", "a")  # the same leaves changed: one reading
    assert pick_reading({"a": {"x"}, "b": {"y"}}) == ("AMBIGUOUS", None)
    assert pick_reading({"a": {"x"}, "b": {"y"}, "both": {"x", "y"}}) == ("AMBIGUOUS", None)


def test_a_reading_that_would_change_the_computation_is_refused(client, monkeypatch):
    rec = stored_records()["stage5-controlled"]
    real = E.run_record
    calls = {"n": 0}

    def fake(config, interventions=None):
        out = real(config, interventions)
        calls["n"] += 1
        if calls["n"] == 2:  # the first reading: claims the expected digest but with a different computation
            out = {
                **out,
                "result_digest": rec["result_digest"],
                "status_log": [*out["status_log"], {"tick": 999, "label": "ACTIVE", "reason": "tampered", "dependency": None}],
            }
        return out

    monkeypatch.setattr(E, "run_record", fake)
    out = replay_js(client, rec)
    assert out["identical"] is False and out["verification"] == "COMPUTATION_DIFFERS"


def test_the_observation_never_enters_the_digest_of_the_run(client):
    # result_digest covers frames, events, cycles, status log, final status, termination and the fields:
    # the outputs of the run, never an observation
    ivs = INTERVENTION_LISTS[1]
    plain = client.post("/api/meos/run", json={"config": {"horizon": 360}, "interventions": ivs}).json()["record"]
    regimes = json.loads((FIXTURES / "meos-stage2-regimes.json").read_text())
    assert len(regimes) >= 14
    for r in regimes:
        seen = client.post(
            "/api/meos/run", json={"config": {"horizon": 360}, "interventions": ivs, "observation": r["obs"]}
        ).json()
        assert seen["record"]["result_digest"] == plain["result_digest"], r["name"]
        assert seen["record"]["full_digest"] == plain["full_digest"], r["name"]
        assert seen["record"]["frames"] == plain["frames"] and seen["record"]["status_log"] == plain["status_log"], r["name"]
    # while the observation result itself does change with the regime
    assert len({r["observed_cycles"] for r in regimes}) >= 3
