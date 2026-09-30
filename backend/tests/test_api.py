"""Service API: sessions, control, LOD, inspection, practice commands, comparison jobs, exports."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from xzr.service.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def sid(client):
    r = client.post("/api/sessions", json={"sample": "demo-3k"})
    assert r.status_code == 200
    return r.json()["id"]


def _wait_t(client, sid, t, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        if client.get(f"/api/sessions/{sid}").json()["t"] >= t:
            return
        time.sleep(0.05)
    raise AssertionError("simulation did not advance")


def _wait_job(client, jid, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] != "running":
            return j
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_health_and_scenarios(client):
    assert client.get("/api/health").json()["ok"]
    ids = {s["id"] for s in client.get("/api/scenarios").json()}
    assert {"demo-3k", "small-600", "benchmark-10k"} <= ids


def test_step_and_inspect(client, sid):
    client.post(f"/api/sessions/{sid}/control", json={"action": "step", "steps": 60})
    _wait_t(client, sid, 60)
    n = client.get(f"/api/sessions/{sid}/node/10").json()
    assert {"theta_eff", "memory", "reachable_transitions", "recent_transitions", "address"} <= set(n)
    assert client.get(f"/api/sessions/{sid}/node/999999").status_code == 404
    ev = client.get(f"/api/sessions/{sid}/events?since=50").json()
    assert ev and all(e["t"] >= 50 for e in ev)
    m = client.get(f"/api/sessions/{sid}/metrics").json()
    assert len(m["t"]) >= 60 and "ignitions" in m["series"]
    assert client.get(f"/api/sessions/{sid}/shapes").json()["interpretation"]["disclaimer"]


def test_lod_endpoints(client, sid):
    for lv, k in enumerate((8, 32, 128, 512)):
        c = client.get(f"/api/sessions/{sid}/clusters?level={lv}").json()
        assert len(c["addresses"]) <= k and set(c["centroids"]) == {"network", "shape", "address", "geo"}
    r = client.get(f"/api/sessions/{sid}/tile?layout=network&x0=0&y0=0&x1=400&y1=400&level=4")
    assert r.status_code == 200 and len(r.content) > 12
    assert client.get(f"/api/sessions/{sid}/tile?layout=nope").status_code == 400


def test_practice_command_triggers_comparison(client, sid):
    r = client.post(f"/api/sessions/{sid}/practice/command", json={"text": "remove concept human", "horizon": 60})
    body = r.json()
    assert r.status_code == 200
    assert body["dependencies"]["direct"] == ["K2"] and "K3" in body["dependencies"]["consequences"]
    changed = {c["claim"] for c in body["commitment_changes"]}
    assert {"K2", "K3"} <= changed
    job = _wait_job(client, body["job"])
    assert job["status"] == "done", job
    res = client.get(f"/api/sessions/{sid}/compare/{body['job']}").json()
    assert res["summary"]["gates_changed"] > 0
    assert len(res["node_classes"]) == 3000


def test_bad_command_gives_suggestions(client, sid):
    r = client.post(f"/api/sessions/{sid}/practice/command", json={"text": "sever relation c1 -> c2999"})
    assert r.status_code == 400 and "no live connection" in r.json()["error"]
    r = client.post(f"/api/sessions/{sid}/practice/command", json={"text": "withdraw everything now"})
    assert r.status_code == 400 and r.json()["suggestions"]


def test_apply_discard_and_save_load(client, sid):
    client.post(f"/api/sessions/{sid}/practice/command", json={"text": "apply"})
    pv = client.get(f"/api/sessions/{sid}/practice").json()
    assert "human" in pv["applied"]["practice"]["removed_concepts"]
    saved = client.get(f"/api/sessions/{sid}/save").json()
    r = client.post("/api/sessions", json={"scenario": saved["scenario"], "applied": saved["applied"]})
    assert r.status_code == 200
    sid2 = r.json()["id"]
    pv2 = client.get(f"/api/sessions/{sid2}/practice").json()
    assert pv2["applied"]["practice"]["removed_concepts"] == ["human"]
    client.delete(f"/api/sessions/{sid2}")


def test_exports(client, sid):
    for what in ("nodes", "edges", "events", "metrics"):
        r = client.get(f"/api/sessions/{sid}/export?what={what}&format=csv")
        assert r.status_code == 200 and r.text.count("\n") > 2
    assert client.get(f"/api/sessions/{sid}/export?what=events&format=json").json()


def test_rewind(client, sid):
    client.post(f"/api/sessions/{sid}/control", json={"action": "step", "steps": 60})
    _wait_t(client, sid, 120)
    r = client.post(f"/api/sessions/{sid}/rewind", json={"t": 75}).json()
    assert r["t"] == 75


def test_websocket_stream(client, sid):
    with client.websocket_connect(f"/ws/{sid}") as ws:
        assert ws.receive_json()["type"] == "hello"
        assert len(ws.receive_bytes()) > 0  # snapshot
        client.post(f"/api/sessions/{sid}/control", json={"action": "run", "speed": 100})
        got_delta = False
        for _ in range(40):
            m = ws.receive()
            if m.get("bytes") and m["bytes"][:4] == (1).to_bytes(4, "little"):
                got_delta = True
                break
        client.post(f"/api/sessions/{sid}/control", json={"action": "pause"})
        assert got_delta


def test_experiment_endpoints(client):
    names = {e["name"] for e in client.get("/api/experiments").json()}
    prims = client.get("/api/experiments/primitives").json()
    assert {"name", "status", "definition", "implementation", "tests", "evidence"} <= set(prims[0])
    # the name guard itself (HTTP paths with "/" never reach this handler; the SPA fallback answers instead)
    from fastapi import HTTPException

    from xzr.service.app import experiment
    for bad in ("../reduction", "..", "a/b", "reduction.json", "REDUCTION", ""):
        with pytest.raises(HTTPException):
            experiment(bad)
    r = client.get("/api/experiments/..%2F..%2Fscenarios%2Fdemo-3k")
    assert "application/json" not in r.headers.get("content-type", "")
    assert client.get("/api/experiments/nope_not_there").status_code == 404
    for n in names:
        assert client.get(f"/api/experiments/{n}").status_code == 200


def test_minimal_runtime_session_streams_complete_events(client):
    r = client.post("/api/sessions", json={"sample": "small-600", "flags": "minimal"})
    assert r.status_code == 200 and r.json()["runtime_is_full"] is False
    sid = r.json()["id"]
    client.post(f"/api/sessions/{sid}/control", json={"action": "step", "steps": 120})
    _wait_t(client, sid, 120)
    ev = client.get(f"/api/sessions/{sid}/events?since=1&limit=2000").json()
    pens = [p for e in ev for p in e["penetrations"]]
    assert pens and all(p[1] >= 0 and p[2] >= 1 for p in pens)  # origin/depth reconstructed by the observer
    assert client.post("/api/sessions", json={"sample": "small-600", "flags": "bogus"}).status_code == 422
    client.delete(f"/api/sessions/{sid}")
