"""Live laboratory runs: the runtime is independent of viewers, events are complete and ordered under backpressure,
controls work, the recorded live run equals a batch run, and the WebSocket endpoint streams it."""

from __future__ import annotations

import dataclasses
import json
import time

import pytest
from fastapi.testclient import TestClient

from xzr.lab import live
from xzr.lab.record import run
from xzr.lab.replay import replay

CFG = {**live.PRESETS["apparatus"], "gen_seed": 9200, "seed": 92000, "horizon": 60}


def _wait(r: live.LiveRun, states=("finished", "stopped", "failed"), timeout=120.0) -> None:
    end = time.time() + timeout
    while r.state not in states and time.time() < end:
        time.sleep(0.02)
    assert r.state in states, r.status()


def test_live_run_equals_a_batch_run_and_replays(tmp_path):
    r = live.LiveRun(CFG, rate=200, out_dir=tmp_path)
    _wait(r)
    rec = json.loads(r.record_path.read_text())
    batch = run(CFG)
    assert [s["fingerprint"] for s in rec["steps"]] == [s["fingerprint"] for s in batch["steps"]]
    assert rec["events"] == batch["events"]
    assert replay(rec)["agreement"]


def test_slow_viewer_gets_every_event_in_order(tmp_path):
    woken = []
    r = live.LiveRun(CFG, rate=200, out_dir=tmp_path)
    sub, hello = r.subscribe(lambda: woken.append(1))
    got, seqs = [], []
    while r.state not in ("finished", "stopped", "failed") or sub.latest is not None:
        time.sleep(0.05)  # slower than the run: frames are coalesced
        m = sub.take()
        if m:
            got += m["events"]
            seqs.append((m["seq_from"], m["seq_to"]))
    full = hello["history"]["events"] + got
    assert full == r.history["events"]  # nothing dropped, nothing reordered
    flat = [s for a, b in seqs for s in range(a, b + 1)]
    assert flat == list(range(flat[0], flat[0] + len(flat)))  # contiguous sequence numbers
    assert any(b > a for a, b in seqs), "expected coalesced frames for a slow viewer"


def test_pause_resume_stop_and_stopped_record_replays(tmp_path):
    r = live.LiveRun({**CFG, "horizon": 400}, rate=40, out_dir=tmp_path)
    _wait(r, ("running",), 60)
    time.sleep(0.3)
    r.control("pause")
    time.sleep(0.2)
    t1 = r.status()["t"]
    time.sleep(0.4)
    assert r.status()["t"] == t1 and r.state == "paused"
    r.control("resume")
    time.sleep(0.3)
    assert r.status()["t"] > t1
    r.control("stop")
    _wait(r)
    assert r.state == "stopped"
    rec = json.loads(r.record_path.read_text())
    assert 0 < len(rec["steps"]) < 400 and replay(rec)["agreement"]
    with pytest.raises(ValueError):
        r.control("explode")


def test_websocket_streams_a_live_run(monkeypatch, tmp_path):
    from xzr.service.app import app
    monkeypatch.setattr(live, "PRESETS", {**live.PRESETS, "apparatus": {**CFG}})
    c = TestClient(app)
    st = c.post("/api/lab/live", json={"preset": "apparatus", "seed": 9200, "rate": 200}).json()
    live.RUNS[st["id"]].out_dir = tmp_path
    with c.websocket_connect(f"/ws/lab/{st['id']}") as ws:
        hello = json.loads(ws.receive_text())
        assert hello["type"] == "hello" and hello["id"] == st["id"]
        assert len(hello["chambers"]) == 32  # the hello carries the built laboratory, never an empty one
        frames, end = [], None
        while end is None:
            m = json.loads(ws.receive_text())
            if m["type"] == "frame":
                frames.append(m)
            elif m["type"] == "end":
                end = m
    assert frames and end["state"] == "finished"
    assert c.post(f"/api/lab/live/{st['id']}/explode").status_code == 400
    assert c.get("/api/lab/live/nope").status_code == 404


def test_live_routes_boundary(monkeypatch, tmp_path):
    """Live runs cost CPU and write records: refused on a public runtime and for another site's page; inputs bounded."""
    from xzr.service import app as app_mod
    monkeypatch.setattr(live, "PRESETS", {**live.PRESETS, "apparatus": {**CFG}})
    c = TestClient(app_mod.app)
    body = {"preset": "apparatus", "seed": 9200, "rate": 200}
    assert c.post("/api/lab/live", json=body, headers={"origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/lab/live", json={**body, "seed": -1}).status_code == 422
    assert c.post("/api/lab/live", json={**body, "rate": 1e9}).status_code == 422
    st = c.post("/api/lab/live", json=body).json()
    r = live.RUNS[st["id"]]
    r.out_dir = tmp_path
    assert c.post(f"/api/lab/live/{st['id']}/stop", headers={"origin": "https://evil.example"}).status_code == 403
    _wait(r)
    with c.websocket_connect(f"/ws/lab/{st['id']}") as ws:  # a viewer arriving after the end is answered, not hung
        assert json.loads(ws.receive_text())["type"] == "hello"
        assert json.loads(ws.receive_text())["type"] == "end"
    monkeypatch.setattr(app_mod, "LIMITS", dataclasses.replace(app_mod.LIMITS, public=True))
    assert c.post("/api/lab/live", json=body).status_code == 403
    assert c.post(f"/api/lab/live/{st['id']}/pause").status_code == 403
