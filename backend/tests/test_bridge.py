"""The iOS in-process bridge (xzr/native/bridge.py): parity with the HTTP service, the route allowlist, mobile limits,
streaming, lifecycle and save / load."""

from __future__ import annotations

import base64
import dataclasses
import json
import time

import pytest
from fastapi.testclient import TestClient

from xzr.native import bridge
from xzr.service import app as app_mod
from xzr.service import limits as limits_mod
from xzr.service import security as sec_mod
from xzr.service import session as session_mod

SAMPLE = "small-600"


def call(method: str, path: str, body=None) -> tuple[int, object]:
    r = json.loads(bridge.handle(json.dumps({"method": method, "path": path, "body": body})))
    return r["status"], (base64.b64decode(r["body"]) if r["kind"] == "binary" else r["body"])


@pytest.fixture(autouse=True)
def clean():
    yield
    for sid in list(bridge.SESSIONS):
        bridge._close(sid)
    for s in list(app_mod.SESSIONS.values()):
        app_mod.close_session(s, "test")
    bridge.SUSPENDED = False
    bridge._PAUSED.clear()


@pytest.fixture
def limits(monkeypatch):
    def set_(**kw):
        new = dataclasses.replace(limits_mod.LIMITS, cookie_secure=False, **kw)
        for m in (limits_mod, app_mod, sec_mod, session_mod, bridge):
            monkeypatch.setattr(m, "LIMITS", new)
    return set_


def _wait_t(sid_get, t):
    for _ in range(2000):
        if sid_get() >= t:
            return
        time.sleep(0.005)
    raise TimeoutError


def test_parity_with_the_http_service():
    http = TestClient(app_mod.app)
    a = http.post("/api/sessions", json={"sample": SAMPLE}).json()
    st, b = call("POST", "/api/sessions", {"sample": SAMPLE})
    assert st == 200
    sa, sb = a["id"], b["id"]
    for sid, step in ((sa, lambda: http.post(f"/api/sessions/{sa}/control", json={"action": "step", "steps": 25})),
                      (sb, lambda: call("POST", f"/api/sessions/{sb}/control", {"action": "step", "steps": 25}))):
        t0 = (app_mod.SESSIONS.get(sid) or bridge.SESSIONS[sid]).engine.state.t
        step()
        _wait_t(lambda sid=sid: (app_mod.SESSIONS.get(sid) or bridge.SESSIONS[sid]).engine.state.t, t0 + 25)
    time.sleep(0.2)
    strip = {"id", "steps_per_second", "connections"}
    ia = {k: v for k, v in http.get(f"/api/sessions/{sa}").json().items() if k not in strip}
    ib = {k: v for k, v in call("GET", f"/api/sessions/{sb}")[1].items() if k not in strip}
    assert ia == ib
    for path in ("hierarchy", "clusters?level=2", "node/7", "events?since=0&limit=50", "metrics?since=0", "shapes",
                 "practice", "save", "export?what=scenario&format=json", "export?what=metrics&format=json"):
        assert http.get(f"/api/sessions/{sa}/{path}").json() == call("GET", f"/api/sessions/{sb}/{path}")[1], path
    for path in ("export?what=nodes&format=csv", "export?what=edges&format=csv", "export?what=events&format=csv"):
        assert http.get(f"/api/sessions/{sa}/{path}").text == call("GET", f"/api/sessions/{sb}/{path}")[1], path
    for path in ("tile?layout=network&level=4&x0=0&y0=0&x1=1000&y1=1000", "tile?layout=geo&level=5", "snapshot"):
        assert http.get(f"/api/sessions/{sa}/{path}").content == call("GET", f"/api/sessions/{sb}/{path}")[1], path
    bad = http.post(f"/api/sessions/{sa}/practice/command", json={"text": "frobnicate everything"})
    assert bad.status_code == 400
    st, body = call("POST", f"/api/sessions/{sb}/practice/command", {"text": "frobnicate everything"})
    assert (st, body) == (400, bad.json())


def test_only_allowlisted_routes_exist():
    sid = call("POST", "/api/sessions", {"sample": SAMPLE})[1]["id"]
    for method, path in [("GET", "/api/exec"), ("POST", "/api/experiments/run"), ("GET", "/api/experiments"),
                         ("GET", "/api/ops/metrics"), ("GET", "/etc/passwd"), ("PUT", f"/api/sessions/{sid}"),
                         ("GET", f"/api/sessions/{sid}/../../x"), ("POST", "/native/shell"), ("GET", "/native/eval")]:
        assert call(method, path)[0] == 404, (method, path)
    for name in ("../scenarios/demo-3k", "/etc/hosts", "demo-3k/../x", "DEMO"):
        assert call("POST", "/api/sessions", {"sample": name})[0] == 404, name
    r = json.loads(bridge.handle("{not json"))
    assert r["status"] == 400
    st, body = call("POST", f"/api/sessions/{sid}/control", {"action": "explode"})
    assert st == 400 and "unknown control action" in body["detail"]
    assert call("GET", "/api/sessions/" + "0" * 32)[0] == 404


def test_mobile_limits_refuse_explicitly(limits):
    limits(max_nodes=1000, max_sessions=2)
    st, body = call("POST", "/api/sessions", {"sample": "demo-3k"})
    assert st == 413 and body["limit"] == "max_nodes" and "desktop runtime" in body["error"]
    a = call("POST", "/api/sessions", {"sample": SAMPLE})[1]["id"]
    b = call("POST", "/api/sessions", {"sample": SAMPLE})[1]["id"]
    c = call("POST", "/api/sessions", {"sample": SAMPLE})[1]["id"]
    assert a not in bridge.SESSIONS and {b, c} <= set(bridge.SESSIONS)  # one device: the oldest is replaced


def test_stream_delivers_snapshot_deltas_metrics_and_job_notices():
    sid = call("POST", "/api/sessions", {"sample": SAMPLE})[1]["id"]
    st, opened = call("POST", f"/native/stream/{sid}")
    assert st == 200 and opened["items"][0]["json"]["type"] == "hello" and "b64" in opened["items"][1]
    key = opened["stream"]
    call("POST", f"/native/stream/{key}/message", {"type": "view", "level": 2})
    call("POST", f"/api/sessions/{sid}/control", {"action": "step", "steps": 5})
    time.sleep(0.5)
    items = [i for s in json.loads(bridge.poll()) if s["stream"] == key for i in s["items"]]
    assert any("b64" in i for i in items) and any(i.get("json", {}).get("type") == "metrics" for i in items)
    job = call("POST", f"/api/sessions/{sid}/compare", {"horizon": 10})[1]["job"]
    for _ in range(400):
        items = [i for s in json.loads(bridge.poll()) if s["stream"] == key for i in s["items"]]
        if any(i.get("json", {}).get("type") == "job" and i["json"]["status"] == "done" for i in items):
            break
        time.sleep(0.02)
    else:
        raise AssertionError("no job notice")
    assert call("GET", f"/api/jobs/{job}")[1]["status"] == "done"
    assert call("DELETE", f"/native/stream/{key}")[0] == 200 and key not in bridge.STREAMS


def test_backgrounding_pauses_running_sessions():
    sid = call("POST", "/api/sessions", {"sample": SAMPLE})[1]["id"]
    call("POST", f"/api/sessions/{sid}/control", {"action": "run"})
    st, body = call("POST", "/native/lifecycle/background")
    assert st == 200 and body["paused"] == [sid]
    assert call("GET", f"/api/sessions/{sid}")[1]["running"] is False
    # a run that arrives after backgrounding (a request already in flight) does not start
    assert call("POST", f"/api/sessions/{sid}/control", {"action": "run"})[1]["running"] is False
    time.sleep(0.2)
    assert call("GET", f"/api/sessions/{sid}")[1]["running"] is False
    st, body = call("POST", "/native/lifecycle/foreground")
    assert st == 200 and body["paused"] == [sid]
    assert call("POST", "/native/lifecycle/foreground")[1]["paused"] == []  # reported once
    assert call("POST", f"/api/sessions/{sid}/control", {"action": "run"})[1]["running"] is True  # active again
    call("POST", f"/api/sessions/{sid}/control", {"action": "pause"})
    call("POST", f"/api/sessions/{sid}/control", {"action": "run"})
    call("GET", f"/api/sessions/{sid}/tile?layout=network&level=4")
    st, body = call("POST", "/native/lifecycle/memory-warning")
    assert st == 200 and body["paused"] == [sid] and not any(k[0] == sid for k in bridge.ops._GRIDS)
    assert call("GET", f"/api/sessions/{sid}/tile?layout=network&level=4")[0] == 200  # rebuilt on demand


def test_save_load_round_trip_through_the_bridge_and_with_a_desktop_save():
    sid = call("POST", "/api/sessions", {"sample": "reason-lab"})[1]["id"]
    call("POST", f"/api/sessions/{sid}/practice/command", {"text": "remove concept human", "auto_compare": False})
    saved = call("GET", f"/api/sessions/{sid}/save")[1]
    st, loaded = call("POST", "/api/sessions", {"scenario": saved["scenario"], "applied": saved["applied"]})
    assert st == 200
    # the draft command was not applied, so the original is still at its built state: the load must reproduce it
    assert bridge.SESSIONS[loaded["id"]].engine.fingerprint() == bridge.SESSIONS[sid].engine.fingerprint()
    # a file saved by the desktop service loads in the bridge (same format) and builds the same world
    http = TestClient(app_mod.app)
    d = http.post("/api/sessions", json={"sample": "reason-lab"}).json()["id"]
    desktop_save = http.get(f"/api/sessions/{d}/save").json()
    st, from_desktop = call("POST", "/api/sessions", {"scenario": desktop_save["scenario"],
                                                       "applied": desktop_save["applied"]})
    assert st == 200
    assert bridge.SESSIONS[from_desktop["id"]].engine.fingerprint() == app_mod.SESSIONS[d].engine.fingerprint()
    # and a bridge save loads in the desktop service
    r = http.post("/api/sessions", json={"scenario": saved["scenario"], "applied": saved["applied"]})
    assert r.status_code == 200
