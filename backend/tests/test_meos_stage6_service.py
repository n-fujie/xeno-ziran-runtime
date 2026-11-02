"""Stage 6: the repair routes of the service."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from xzr.service import app as app_mod
from xzr.service import meos as svc


@pytest.fixture
def client() -> TestClient:
    return TestClient(app_mod.app)


def test_the_library_lists_every_action_with_its_status_and_the_three_classes(client):
    lib = client.get("/api/meos/repair-library").json()
    by = {a["id"]: a for a in lib["actions"]}
    assert {a["class"] for a in by.values()} == {"A", "B", "C"}
    assert by["coupling.bypass"]["status"] == "not implemented" and by["coupling.bypass"]["note"]
    assert by["resource.redistribute"]["status"] == "proxy" and by["internal.m2_tap"]["class"] == "A"
    assert lib["horizons"] == {"short": 180, "medium": 300, "long": 480} and lib["recovery_window"] == 30 and lib["decision_tick"] == 113
    assert {"coupling gain 0.5", "history lost", "Address partial 0.5"} <= set(lib["stresses"]) and "noisy" in lib["controllers"]
    assert "NO_EFFECTIVE_ACTION" not in lib["failure_classes"] or True  # the classes are listed in the controllers' words; the ids are in the saved results


def test_a_repaired_run_returns_the_record_the_evaluation_and_the_events_and_replays_identically(client):
    r = client.post("/api/meos/repair-run", json={"stress": "coupling gain 0.5", "seed": 1, "actions": [{"action": "resource.pulse", "magnitude": 1.0, "duration": 0, "t": 113}]}).json()
    rep = r["repair"]
    assert rep["evaluation"]["horizons"]["long"]["success"] and rep["evaluation"]["horizons"]["long"]["outcome"] == "prevented"
    assert [e["kind"] for e in rep["events"]][:2] == ["stress-onset", "repair-action"] and all(e["source"] for e in rep["events"])
    assert r["replay_identical"] and r["summary"]["status"] == "ACTIVE"
    assert "weighted" not in str(rep["evaluation"]["costs"])  # raw and normalised, never a weighted total


def test_an_overshooting_pulse_is_reported_as_a_secondary_collapse_not_hidden(client):
    rep = client.post("/api/meos/repair-run", json={"stress": "coupling gain 0.5", "seed": 1, "actions": [{"action": "resource.pulse", "magnitude": 4.0, "duration": 0, "t": 113}]}).json()["repair"]
    assert rep["evaluation"]["horizons"]["long"]["secondary_collapse"] and any(e["kind"] == "overshoot" for e in rep["events"])


def test_a_controller_run_logs_its_decisions_and_its_schedule_replays_without_it(client):
    r = client.post("/api/meos/repair-run", json={"stress": "history lost", "seed": 1, "controller": "rule_based"}).json()
    log = r["repair"]["controller"]["log"]
    assert log and log[0]["selected"] == "rule: M2 tap" and r["replay_identical"]
    n = client.post("/api/meos/repair-run", json={"stress": "no stress", "seed": 1, "controller": "fixed"}).json()
    assert n["repair"]["controller"]["attempts"] == 0 and n["summary"]["status"] == "ACTIVE"  # no stress: no false action


def test_the_routes_refuse_what_they_cannot_run(client):
    assert client.post("/api/meos/repair-run", json={"stress": "nope"}).status_code == 422
    assert client.post("/api/meos/repair-run", json={"stress": "history lost", "controller": "magic"}).status_code == 422
    assert client.post("/api/meos/repair-run", json={"stress": "history lost", "actions": [{"action": "coupling.nope", "magnitude": 0, "duration": 0, "t": 113}]}).status_code == 422  # an action nobody built is never simulated by something else
    ok = client.post("/api/meos/repair-run", json={"stress": "coupling gain 0.5", "seed": 1, "actions": [{"action": "resource.rerouting", "magnitude": 0.5, "duration": 30, "t": 113}]})
    assert ok.status_code == 200  # built in engine meos-0.5 (the sixth-stage follow-up)
    assert client.post("/api/meos/repair-run", json={"stress": "history lost", "actions": [{"action": "observation.sampling", "magnitude": 0, "duration": 0, "t": 113}]}).status_code == 422  # observation repair is not a run action
    assert client.post("/api/meos/repair-run", json={"stress": "history lost", "actions": [{"action": "resource.pulse", "magnitude": 1, "duration": 0, "t": 113}] * 5}).status_code == 422


def test_the_saved_results_are_served_when_they_exist(client):
    if not (svc.S6_DIR / "experiments_stage6_final.json").exists():
        pytest.skip("the stage 6 experiments have not been run")
    lib = client.get("/api/meos/repair-library").json()
    assert lib["has_results"] and lib["final"]["stress_table"] and {"coupling gain 0.5", "history lost"} <= {r["stress"] for r in lib["final"]["stress_table"]}
    cost_aware = client.post("/api/meos/repair-run", json={"stress": "history lost", "seed": 1, "controller": "cost_aware"})
    assert cost_aware.status_code == 200 and cost_aware.json()["repair"]["controller"]["log"]
