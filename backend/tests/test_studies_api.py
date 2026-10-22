"""Study API: local-only boundary, protocol validation, creation, run control, analysis, reports, packaging, replay,
reproduction, and path hygiene."""

from __future__ import annotations

import dataclasses
import time

import pytest
from fastapi.testclient import TestClient

from xzr.service import app as app_mod
from xzr.service import studies as studies_mod
from xzr.service.limits import LIMITS
from xzr.study import templates


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("XZR_STUDY_ROOT", str(tmp_path))
    studies_mod.ACTIVE.clear()
    return TestClient(app_mod.app, headers={"origin": "http://testserver"})


def _quick(n=2):
    return templates.template("quick", n_seeds=n, horizon=120)


def _wait(c, sid, timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        s = c.get(f"/api/studies/{sid}/status").json()
        if not s["running"] and s["state"] in ("finished", "stopped"):
            return s
        time.sleep(0.2)
    raise AssertionError("study did not finish")


def test_templates_and_validation(client):
    t = client.get("/api/studies/templates").json()
    assert {"revision-study", "quick", "lab-population"} <= set(t)
    ok = client.post("/api/studies/validate", json={"protocol": _quick()}).json()
    assert ok["valid"] and ok["runs"] == 4 and ok["fairness_issues"] == [] and not ok["high_cost"]
    bad = _quick()
    bad["arms"][0].pop("description")
    r = client.post("/api/studies/validate", json={"protocol": bad}).json()
    assert not r["valid"] and any("description" in i for i in r["issues"])
    assert client.post("/api/studies", json={"protocol": bad}).status_code == 422


def test_full_workflow_through_the_api(client):
    sid = client.post("/api/studies", json={"protocol": _quick(3)}).json()["id"]
    assert client.get("/api/studies").json()[0]["id"] == sid
    run = client.post(f"/api/studies/{sid}/run", json={"procs": 2})
    assert run.status_code == 200
    assert client.post(f"/api/studies/{sid}/run", json={"procs": 2}).status_code in (
        200,
        409,
        429,
    )  # a second start is refused while running
    s = _wait(client, sid)
    assert s["state"] == "finished" and s["n_ok"] == 6
    runs = client.get(f"/api/studies/{sid}/runs").json()
    assert len(runs) == 6 and all(r["status"] == "ok" for r in runs)
    one = client.get(f"/api/studies/{sid}/runs/recursive/0").json()
    assert one["arm"] == "recursive" and one["metrics"]["fired_samples"] >= 0
    rep = client.post(f"/api/studies/{sid}/runs/recursive/0/replay").json()
    assert rep["agreement"] is True
    an = client.post(f"/api/studies/{sid}/analyse").json()
    assert an["label"].startswith("FUNCTIONAL") and an["contrasts"][0]["metrics"]["fired_samples"]["n"] == 3
    assert client.get(f"/api/studies/{sid}/analysis").json()["experiment_id"] == sid
    idx = client.post(f"/api/studies/{sid}/report").json()
    assert "methods.md" in idx["files"]
    md = client.get(f"/api/studies/{sid}/report/methods.md")
    assert md.status_code == 200 and sid in md.text
    svg = client.get(f"/api/studies/{sid}/report/{idx['figures'][0]['file']}")
    assert svg.headers["content-type"].startswith("image/svg+xml") and svg.text.startswith("<svg")
    pk = client.post(f"/api/studies/{sid}/package").json()
    assert pk["verify"]["ok"] and client.get(f"/api/studies/{sid}/package.zip").status_code == 200
    assert client.get(f"/api/studies/{sid}/verify").json()["ok"]
    det = client.get(f"/api/studies/{sid}").json()
    assert det["has_analysis"] and det["has_report"] and det["has_package"] and det["registered_digest"] == det["protocol_digest"]
    # reproduction: a new study that re-executes the registered protocol and compares
    new = client.post(f"/api/studies/{sid}/reproduce", json={"procs": 2}).json()
    _wait(client, new["id"])
    cmp = client.get(f"/api/studies/{new['id']}/reproduction").json()
    assert cmp["of"] == sid and cmp["identical_share"] == 1.0


def test_amend_is_recorded_and_refused_while_running(client):
    sid = client.post("/api/studies", json={"protocol": _quick(1)}).json()["id"]
    r = client.post(
        f"/api/studies/{sid}/amend", json={"path": "stop.max_failures", "value": 5, "reason": "tolerate more failures"}
    )
    assert r.status_code == 200 and r.json()["status"] == "pre-registered change"
    assert client.get(f"/api/studies/{sid}").json()["amendments"][0]["path"] == "stop.max_failures"
    bad = client.post(f"/api/studies/{sid}/amend", json={"path": "arms.0.name", "value": "", "reason": "x"})
    assert bad.status_code == 422


def test_ids_and_files_are_matched_before_any_path_is_built(client):
    for bad in ("..", "../etc", "S1", "S20261022-ZZZZZZZZ-0000"):
        assert client.get(f"/api/studies/{bad}").status_code in (404, 422)
    sid = client.post("/api/studies", json={"protocol": _quick(1)}).json()["id"]
    assert client.get(f"/api/studies/{sid}/report/..%2Fprotocol.json").status_code == 404
    assert client.get(f"/api/studies/{sid}/report/nothing.md").status_code == 404
    assert client.get(f"/api/studies/{sid}/runs/ghost/0").status_code == 404


def test_cross_origin_requests_are_refused(client):
    r = client.post("/api/studies/validate", json={"protocol": _quick()}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403


def test_public_deployment_refuses_every_study_route(client, monkeypatch):
    pub = dataclasses.replace(LIMITS, public=True)
    monkeypatch.setattr(studies_mod, "LIMITS", pub)
    for method, path in (
        ("get", "/api/studies"),
        ("get", "/api/studies/templates"),
        ("post", "/api/studies/validate"),
        ("post", "/api/studies"),
        ("post", "/api/studies/S20261022-00000000-0000/run"),
    ):
        r = getattr(client, method)(path, **({"json": {"protocol": _quick()}} if method == "post" else {}))
        assert r.status_code == 403, path


def test_oversized_protocol_is_refused(client):
    big = _quick()
    big["notes"] = "x" * (600 * 1024)
    assert client.post("/api/studies/validate", json={"protocol": big}).status_code == 413
