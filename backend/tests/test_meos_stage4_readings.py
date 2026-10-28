"""MEOS-0, fourth stage: operational paths, boundary perturbation, Address Domain effects, the per-run log, the SSS region of one point and the routes that serve them.

Outcomes are measured by running the engine; a null result is pinned as a null result. The readings never feed back into a run: the digest of a run is the same
whether or not they were computed."""

from __future__ import annotations

import csv
import dataclasses
import io

import pytest
from fastapi.testclient import TestClient

from xzr.meos import analysis as A
from xzr.meos import engine as E
from xzr.meos import stage4 as S
from xzr.service import app as app_mod
from xzr.service import studies as studies_mod
from xzr.service.limits import LIMITS


@pytest.fixture(scope="module")
def client():
    return TestClient(app_mod.app)


@pytest.fixture(scope="module")
def base():
    return E.run_record(E.default_config(), [])


def test_the_five_paths_have_components_a_signal_and_intervals(base):
    pa = S.path_activity(base)
    assert list(pa) == ["resource", "coupling", "history_access", "observation", "recovery"]
    for p in pa.values():
        assert len(p["series"]) == len(base["frames"]) and p["components"] and p["means"]
        assert p["state_intervals"][0]["from"] == 0 and p["state_intervals"][-1]["to"] == len(base["frames"]) - 1
    assert pa["coupling"]["active_ticks"] > 0 and pa["coupling"]["cut_ticks"] == 0


def test_a_cut_component_shows_as_a_cut_interval_of_its_path_only():
    rec = E.run_record(
        E.default_config(),
        [
            {"tick": 60, "op": "ISOLATE", "target": "interaction_channel"},
            {"tick": 90, "op": "RECONNECT", "target": "interaction_channel"},
        ],
    )
    pa = S.path_activity(rec)
    assert pa["coupling"]["cut_ticks"] == 30
    assert {"from": 60, "to": 89, "state": "cut"} in pa["coupling"]["state_intervals"]
    assert pa["history_access"]["cut_ticks"] == 0 and pa["observation"]["cut_ticks"] == 0


def test_path_activity_does_not_change_the_digest(base):
    S.path_activity(base)
    S.run_log(base)
    assert E.replay(base)["identical"]


def test_an_observation_boundary_changes_what_is_seen_and_not_what_the_run_did():
    r = S.boundary_perturbation(E.default_config(), "observation")
    row = r["rows"][0]
    assert row["operation_changed"] is False and row["state_final_restored"] == "ACTIVE"  # the run is the unperturbed run
    assert row["observability"]["operational_state"] == "ACTIVE" and row["observability"]["observed_state"] != "ACTIVE"
    assert row["observability"]["status"] == "OUTSIDE_OBSERVATION_REGION" and row["collapsed"] is False


@pytest.mark.parametrize("kind", ["coupling", "resource_exchange", "history_access", "address_domain"])
def test_an_operational_boundary_perturbation_collapses_the_run_and_names_what_it_broke(kind):
    r = S.boundary_perturbation(E.default_config(), kind)
    row = r["rows"][0]
    assert row["operation_changed"] and row["collapsed"] and row["state_before"] == "ACTIVE"
    if (
        kind != "address_domain"
    ):  # an Address Domain fault cuts no component: it breaks the attribution of events to a configuration
        assert r["paths_cut_directly"] and set(r["paths_cut_directly"]) <= set(r["affected_paths"])
    assert r["bodies"]["B3"]["legs_broken_by_perturbation"]  # B3 contains every relation the perturbation touches
    assert r["bodies"]["B1"]["legs_broken_by_perturbation"] == []  # B1 holds no leg that depends on these components
    assert (
        row["observability"]["status"] == "SUFFICIENT"
    )  # with full observation, the collapse is seen as a collapse of the operation


def test_boundary_perturbation_is_deterministic():
    a = S.boundary_perturbation(E.default_config(), "coupling")
    b = S.boundary_perturbation(E.default_config(), "coupling")
    assert a == b


@pytest.mark.parametrize("mode", ["loss", "reassign", "fragment", "collision", "partial", "delayed", "stale"])
def test_every_address_intervention_is_recorded_with_old_and_new_state(mode):
    r = S.address_intervention(E.default_config(), mode)
    e = r["effects"][0]
    assert e["tick"] == 100 and e["mode"] == mode and e["affected_address"] == ["A2"]
    assert {
        "old_state",
        "new_state",
        "affected_path",
        "operational_effect",
        "observed_effect",
        "recovery_status",
        "recovery_with_pulse",
    } <= set(e)
    assert len(r["effects"]) == 2 and r["effects"][1]["mode"] == "restore"
    assert E.replay(r["record"])["identical"]


def test_address_loss_collapses_and_a_pulse_after_restoration_recovers_it():
    r = S.address_intervention(E.default_config(), "loss")
    assert r["operational_state"] == "COLLAPSED" and r["restored_and_pulse_state"] == "ACTIVE"
    assert r["effects"][0]["operational_effect"]["collapse_tick"] is not None


def test_the_run_log_carries_the_seed_the_schedule_the_three_timelines_and_the_digests(base):
    rec = E.run_record(E.default_config(), [{"tick": 60, "op": "ISOLATE", "target": "interaction_channel"}])
    log = S.run_log(rec, {"sampling_interval": 3})
    for k in (
        "seed",
        "initial_configuration",
        "intervention_schedule",
        "configuration",
        "timelines",
        "collapse_tick",
        "recovery_tick",
        "digests",
        "log_digest",
    ):
        assert k in log
    assert set(log["timelines"]) == {"operational", "observed", "observability"}
    assert all(len(v) == len(rec["frames"]) for v in log["timelines"].values())
    assert log["digests"]["result"] == rec["result_digest"] and log["collapse_tick"] == 109
    assert S.run_log(rec, {"sampling_interval": 3})["log_digest"] == log["log_digest"]
    assert S.run_log(rec, {"sampling_interval": 5})["log_digest"] != log["log_digest"]


def test_the_csv_log_has_one_row_per_tick(base):
    rows = list(csv.DictReader(io.StringIO(S.run_log_csv(base, {"sampling_interval": 3}))))
    assert (
        len(rows) == len(base["frames"])
        and rows[200]["operational"] == "ACTIVE"
        and rows[200]["observability"] == "INSUFFICIENT_TEMPORAL_RESOLUTION"
    )


def test_sss_classify_matches_the_phase_map_definition():
    c = S.sss_classify(E.default_config(), 1.5, 1.0, 1.0)
    assert c["region"] == "COLLAPSED" and c["class"] == "COLLAPSED"
    assert S.sss_classify(E.default_config(), 1.0, 1.0, 1.0)["class"] == "ACTIVE"


def test_the_routes(client):
    r = client.post("/api/meos/run-log", json={"interventions": [{"tick": 60, "op": "ISOLATE", "target": "interaction_channel"}]})
    assert r.status_code == 200 and r.json()["collapse_tick"] == 109
    assert client.post("/api/meos/run-log", json={"format": "csv"}).text.startswith("tick,operational")
    assert client.post("/api/meos/paths", json={}).json()["coupling"]["components"] == ["interaction_channel"]
    assert client.post("/api/meos/sss-classify", json={"scale": 1.5}).json()["region"] == "COLLAPSED"
    assert client.post("/api/meos/boundary-perturbation", json={"kind": "coupling"}).json()["rows"][0]["collapsed"]
    assert client.post("/api/meos/address-intervention", json={"mode": "loss"}).json()["operational_state"] == "COLLAPSED"
    run = client.post("/api/meos/run", json={"paths": True, "observation": {"threshold": 0.9}}).json()
    assert "paths" in run and run["observed"]["observability"]["status"] == "SIGNAL_BELOW_THRESHOLD"
    for path, body in (
        ("/api/meos/boundary-perturbation", {"kind": "nope"}),
        ("/api/meos/address-intervention", {"mode": "restore"}),
        ("/api/meos/sss-classify", {"scale": 9}),
        ("/api/meos/run-log", {"format": "xml"}),
    ):
        assert client.post(path, json=body).status_code == 422, path


def test_the_new_routes_are_local_only(client, monkeypatch):
    monkeypatch.setattr(studies_mod, "LIMITS", dataclasses.replace(LIMITS, public=True))
    for path in ("paths", "boundary-perturbation", "address-intervention", "run-log", "sss-classify"):
        assert client.post(f"/api/meos/{path}", json={}).status_code == 403, path


def test_the_first_stage_vocabulary_is_kept_beside_the_new_one(base):
    x = A.observe(base, {"region": [8, 8, 12, 12]})
    assert (
        x["observability_status"] == "REGION_EXCLUDES_ACTIVITY" and x["observability"]["status"] == "OUTSIDE_OBSERVATION_REGION"
    )
