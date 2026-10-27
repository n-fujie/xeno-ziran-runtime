"""The public-runtime security boundary: session ownership, enumeration, limits, rate limits, ingestion, job lifecycle,
WebSocket safeguards, cleanup and observability."""

from __future__ import annotations

import dataclasses
import json
import logging
import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from xzr.service import app as app_mod
from xzr.service import limits as limits_mod
from xzr.service import security as sec_mod
from xzr.service import session as session_mod

SAMPLE = "small-600"


@pytest.fixture
def limits(monkeypatch):
    """Override limits for one test (every module holds its own reference)."""
    def set_(**kw):
        kw.setdefault("cookie_secure", False)
        new = dataclasses.replace(limits_mod.LIMITS, **kw)
        for m in (limits_mod, app_mod, sec_mod, session_mod):
            monkeypatch.setattr(m, "LIMITS", new)
        return new
    set_()
    return set_


@pytest.fixture(autouse=True)
def clean():
    yield
    for s in list(app_mod.SESSIONS.values()):
        app_mod.close_session(s, "test")
    session_mod.JOBS.clear()
    sec_mod.RATES._b.clear()


def client(peer: str = "testclient") -> TestClient:
    return TestClient(app_mod.app, client=(peer, 50000))


def create(c: TestClient, **body) -> dict:
    r = c.post("/api/sessions", json={"sample": SAMPLE, **body})
    assert r.status_code == 200, r.text
    return r.json()


def test_session_ids_are_128_bit_random_and_not_credentials(limits):
    a = client()
    ids = {create(a)["id"] for _ in range(3)}
    assert len(ids) == 3 and all(re.fullmatch(r"[0-9a-f]{32}", i) for i in ids)
    token = a.cookies.get(sec_mod.OWNER_COOKIE)
    assert token and len(token) >= 43 and token not in ids  # the capability is a separate 256-bit token


def test_another_visitor_cannot_reach_any_session_route(limits):
    a, b = client(), client()
    sid = create(a)["id"]
    a.post(f"/api/sessions/{sid}/compare", json={"horizon": 10})
    routes = [("get", ""), ("post", "/control"), ("post", "/rewind"), ("get", "/hierarchy"), ("get", "/clusters"),
              ("get", "/tile"), ("get", "/snapshot"), ("get", "/node/0"), ("get", "/events"), ("get", "/metrics"),
              ("get", "/shapes"), ("get", "/practice"), ("post", "/practice/command"), ("post", "/compare"),
              ("get", "/compare/x"), ("get", "/save"), ("get", "/export?what=nodes&format=csv"), ("delete", "")]
    body = {"/control": {"action": "step"}, "/rewind": {"t": 0}, "/practice/command": {"text": "help"},
            "/compare": {"horizon": 10}}
    for method, path in routes:
        kw = {"json": body[path]} if path in body else {}
        r = getattr(b, method)(f"/api/sessions/{sid}{path}", **kw)
        assert r.status_code == 404 and r.json() == {"detail": "no such session"}, (method, path, r.status_code)
    assert a.get(f"/api/sessions/{sid}").status_code == 200  # untouched by the attempts
    assert b.get("/api/sessions/" + "0" * 32).json() == {"detail": "no such session"}  # same answer as missing


def test_sessions_cannot_be_enumerated(limits):
    a, b = client(), client()
    sid = create(a)["id"]
    assert b.get("/api/sessions").json() == []
    assert [x["id"] for x in a.get("/api/sessions").json()] == [sid]


def test_jobs_belong_to_the_session_owner(limits):
    a, b = client(), client()
    sid = create(a)["id"]
    jid = a.post(f"/api/sessions/{sid}/compare", json={"horizon": 10}).json()["job"]
    assert re.fullmatch(r"[0-9a-f]{32}", jid)
    assert b.get(f"/api/jobs/{jid}").status_code == 404
    assert b.post(f"/api/jobs/{jid}/cancel").status_code == 404
    assert a.get(f"/api/jobs/{jid}").status_code == 200


def test_websocket_requires_ownership_and_same_origin(limits):
    a, b = client(), client()
    sid = create(a)["id"]
    with pytest.raises(WebSocketDisconnect) as e, b.websocket_connect(f"/ws/{sid}"):
        pass
    assert e.value.code == 4404
    with pytest.raises(WebSocketDisconnect) as e, a.websocket_connect(f"/ws/{sid}",
                                                                       headers={"origin": "https://evil.example"}):
        pass
    assert e.value.code == 4403
    with a.websocket_connect(f"/ws/{sid}") as ws:
        assert json.loads(ws.receive_text())["type"] == "hello"


def test_websocket_limits(limits):
    limits(max_ws_per_session=1, ws_max_message=64)
    a = client()
    sid = create(a)["id"]
    with a.websocket_connect(f"/ws/{sid}") as ws1:
        ws1.receive_text()
        with a.websocket_connect(f"/ws/{sid}") as ws2:
            msg = json.loads(ws2.receive_text())
            assert msg["type"] == "error" and msg["limit"] == "max_ws_per_session"
        ws1.send_text(json.dumps({"type": "ping", "pad": "x" * 200}))
        for _ in range(500):  # frames already queued may arrive first
            m = ws1.receive()
            if m["type"] == "websocket.close":
                break
        assert m["type"] == "websocket.close" and m["code"] == 1009


def test_a_full_runtime_never_evicts_another_visitors_session(limits):
    limits(max_sessions=2, max_sessions_per_ip=10)
    a, b, c = client(), client(), client()
    sa, sb = create(a)["id"], create(b)["id"]
    r = c.post("/api/sessions", json={"sample": SAMPLE})
    assert r.status_code == 503 and r.json()["limit"] == "max_sessions"
    assert set(app_mod.SESSIONS) == {sa, sb}


def test_a_client_at_its_limit_replaces_only_its_own_session(limits):
    limits(max_sessions_per_client=1)
    a, b = client(), client()
    first, other = create(a)["id"], create(b)["id"]
    second = create(a)
    assert second["replaced_session"] == first and first not in app_mod.SESSIONS and other in app_mod.SESSIONS


def test_sessions_per_ip(limits):
    limits(max_sessions_per_ip=1, max_sessions_per_client=5)
    a, b = client(), client()  # same test address
    create(a)
    r = b.post("/api/sessions", json={"sample": SAMPLE})
    assert r.status_code == 429 and r.json()["limit"] == "max_sessions_per_ip"


def test_rate_limits(limits):
    limits(rate_sessions_per_min=2)
    a = client()
    codes = [a.post("/api/sessions", json={"sample": SAMPLE}).status_code for _ in range(4)]
    assert codes[:1] == [200] and 429 in codes
    limits(rate_api_per_s=1)
    sec_mod.RATES._b.clear()
    codes = [a.get("/api/scenarios").status_code for _ in range(8)]
    assert codes[0] == 200 and codes[-1] == 429


def test_oversized_and_malformed_uploads_are_rejected_before_allocation(limits):
    limits(max_body_bytes=4000, max_nodes=1000, max_depth=8, max_string=100, max_warmup=10)
    a = client()
    gen = {"name": "x", "generator": {"n": 100}}
    big = {"scenario": {**gen, "description": "d" * 5000}}
    r = a.post("/api/sessions", json=big)
    assert r.status_code == 413 and r.json()["limit"] == "max_body"
    limits(max_body_bytes=10_000_000, max_nodes=1000, max_depth=8, max_string=100, max_warmup=10)
    cases = {
        "max_nodes": {**gen, "generator": {"n": 400_000}},
        "max_string": {**gen, "description": "d" * 101},
        "max_depth": {**gen, "practice": {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": 1}}}}}}}}},
        "max_warmup": {**gen, "warmup": 1000},
    }
    t0 = time.perf_counter()
    for limit, sc in cases.items():
        r = a.post("/api/sessions", json={"scenario": sc})
        assert r.status_code == 413 and r.json()["limit"] == limit, (limit, r.text)
    assert time.perf_counter() - t0 < 2.0 and not app_mod.SESSIONS  # nothing was built
    for bad in ({"name": 1, "generator": {"n": 100}}, {"name": "x", "unknown": 1}, {"name": "x", "generator": {"n": 5}},
                {"name": "x", "generator": {"n": "many"}}):
        assert a.post("/api/sessions", json={"scenario": bad}).status_code == 422
    assert a.post("/api/sessions", content=b"{not json", headers={"content-type": "application/json"}).status_code == 422


def test_runtime_limits_are_explicit(limits):
    limits(max_step_batch=50, max_speed=30, max_compare_horizon=100)
    a = client()
    sid = create(a)["id"]
    r = a.post(f"/api/sessions/{sid}/control", json={"action": "step", "steps": 51})
    assert r.status_code == 422 and r.json()["limit"] == "max_step_batch"
    st = a.post(f"/api/sessions/{sid}/control", json={"action": "speed", "speed": 0}).json()
    assert st["speed"] == 30 and st["speed_limit"] == 30  # "as fast as possible" is capped, and says so
    r = a.post(f"/api/sessions/{sid}/compare", json={"horizon": 101})
    assert r.status_code == 422 and r.json()["limit"] == "max_compare_horizon"


def test_compare_concurrency_is_bounded(limits):
    limits(max_active_jobs_per_session=1, max_queued_jobs=1)
    a = client()
    sid = create(a)["id"]
    session_mod.JOBS["fake"] = {"id": "fake", "session": sid, "status": "running", "created": time.time()}
    r = a.post(f"/api/sessions/{sid}/compare", json={"horizon": 10})
    assert r.status_code == 429 and r.json()["limit"] == "max_active_jobs_per_session"
    session_mod.JOBS["fake"]["session"] = "someone-else"
    r = a.post(f"/api/sessions/{sid}/compare", json={"horizon": 10})
    assert r.status_code == 503 and r.json()["limit"] == "max_queued_jobs"


def test_finished_jobs_are_pruned_by_ttl_and_count(limits):
    limits(job_ttl_s=60, max_jobs=3)
    now = time.time()
    for i in range(6):
        session_mod.JOBS[f"j{i}"] = {"id": f"j{i}", "session": "s", "status": "done", "created": now,
                                     "finished": now - (120 if i < 2 else 10 - i)}
    session_mod.JOBS["live"] = {"id": "live", "session": "s", "status": "running", "created": now}
    session_mod.prune_jobs(now)
    assert "live" in session_mod.JOBS and "j0" not in session_mod.JOBS and "j1" not in session_mod.JOBS
    assert len(session_mod.JOBS) == 3


def test_real_compare_jobs_finish_and_are_pruned(limits):
    limits(job_ttl_s=0.0)
    a = client()
    sid = create(a)["id"]
    jid = a.post(f"/api/sessions/{sid}/compare", json={"horizon": 10}).json()["job"]
    for _ in range(200):
        if session_mod.JOBS[jid]["status"] in session_mod.FINISHED:
            break
        time.sleep(0.05)
    assert session_mod.JOBS[jid]["status"] == "done"
    time.sleep(0.01)
    session_mod.prune_jobs()
    assert jid not in session_mod.JOBS


def test_idle_and_expired_sessions_are_cleaned_up(limits):
    limits(session_idle_s=100, session_max_age_s=1000)
    a = client()
    s1, s2 = create(a)["id"], create(a)["id"]
    app_mod.SESSIONS[s1].touched -= 200  # idle
    app_mod.reap()
    assert s1 not in app_mod.SESSIONS and s2 in app_mod.SESSIONS
    app_mod.reap(now=time.time() + 2000)  # past the absolute lifetime
    assert not app_mod.SESSIONS
    assert sec_mod.METRICS.counters["sessions_closed_idle"] >= 1


def test_export_size_is_bounded(limits):
    limits(max_export_bytes=1000)
    a = client()
    sid = create(a)["id"]
    r = a.get(f"/api/sessions/{sid}/export?what=nodes&format=csv")
    assert r.status_code == 413 and r.json()["limit"] == "max_export_bytes"


def test_ops_metrics_are_protected_and_contain_no_identifiers(limits, caplog):
    limits(public=True, ops_token="")
    a = client()
    assert a.get("/api/ops/metrics").status_code == 404  # disabled without a token
    limits(public=True, ops_token="t0ken")
    caplog.set_level(logging.INFO, logger="xzr.service")
    sid = create(a)["id"]
    token = a.cookies.get(sec_mod.OWNER_COOKIE)
    assert a.get("/api/ops/metrics", headers={"x-ops-token": "wrong"}).status_code == 404
    m = a.get("/api/ops/metrics", headers={"x-ops-token": "t0ken"})
    assert m.status_code == 200
    body = m.text
    for k in ("sessions_active", "websockets_active", "jobs", "rejected_by_limit", "memory_rss_bytes", "process_cpu_s",
              "step_latency_ms_mean", "counters"):
        assert k in m.json()
    assert sid not in body and token not in body and "t0ken" not in body
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "session_created" in logs and token not in logs and sid not in logs  # only an 8-char prefix is logged


def _all_routes() -> list:
    """App routes including those of included routers (newer FastAPI keeps them behind an ``_IncludedRouter`` wrapper)."""
    out = []
    for r in app_mod.app.routes:
        out += list(r.original_router.routes) if hasattr(r, "original_router") else [r]
    return out


def test_no_route_runs_experiments_or_touches_the_filesystem():
    """The public API surface. A new mutating route must be reviewed against the security boundary."""
    routes = _all_routes()
    mutating = sorted((m, r.path) for r in routes for m in getattr(r, "methods", ()) or ()
                      if m in ("POST", "PUT", "PATCH", "DELETE"))
    assert mutating == sorted([
        ("POST", "/api/sessions"), ("DELETE", "/api/sessions/{sid}"), ("POST", "/api/sessions/{sid}/control"),
        ("POST", "/api/sessions/{sid}/rewind"), ("POST", "/api/sessions/{sid}/practice/command"),
        ("POST", "/api/sessions/{sid}/compare"), ("POST", "/api/jobs/{jid}/cancel"), ("POST", "/api/owner/reset"),
        # live laboratory runs: local runtime and same origin only (test_lab_live.py::test_live_routes_boundary)
        ("POST", "/api/lab/live"), ("POST", "/api/lab/live/{rid}/{action}"),
        # studies (experiment protocols, runs, reports): local runtime and same origin only, 403 under XZR_PUBLIC
        # (test_studies_api.py::test_public_deployment_refuses_every_study_route)
        ("POST", "/api/studies/validate"), ("POST", "/api/studies"), ("POST", "/api/studies/{sid}/run"),
        ("POST", "/api/studies/{sid}/stop"), ("POST", "/api/studies/{sid}/amend"),
        ("POST", "/api/studies/{sid}/runs/{arm}/{k}/replay"), ("POST", "/api/studies/{sid}/analyse"),
        ("POST", "/api/studies/{sid}/report"), ("POST", "/api/studies/{sid}/package"),
        ("POST", "/api/studies/{sid}/reproduce"),
        # MEOS (XENO ECOSYSTEM): stateless, deterministic computations that store nothing; local runtime and same origin only,
        # 403 under XZR_PUBLIC
        # (test_meos.py::test_the_api_is_local_only_and_stateless)
        ("POST", "/api/meos/run"), ("POST", "/api/meos/replay"), ("POST", "/api/meos/ablation"), ("POST", "/api/meos/mfs"),
        ("POST", "/api/meos/boundary"), ("POST", "/api/meos/history"), ("POST", "/api/meos/sss"), ("POST", "/api/meos/address"),
        ("POST", "/api/meos/causal"), ("POST", "/api/meos/factorial"), ("POST", "/api/meos/necessity"),
        ("POST", "/api/meos/minimal-configurations"), ("POST", "/api/meos/boundary-experiments"), ("POST", "/api/meos/recovery"),
        ("POST", "/api/meos/sss-phase"), ("POST", "/api/meos/address-experiments"), ("POST", "/api/meos/m2"), ("POST", "/api/meos/phil"),
        ("POST", "/api/meos/observe")])
    meos_src = Path(app_mod.__file__).with_name("meos.py").read_text()
    assert meos_src.count("local_only(request)") >= len([1 for r in routes if "/api/meos" in getattr(r, "path", "")])
    studies_src = Path(app_mod.__file__).with_name("studies.py").read_text()
    assert studies_src.count("local_only(request)") >= len([1 for r in routes if "/api/studies" in getattr(r, "path", "")])
    src = Path(app_mod.__file__).read_text()
    for forbidden in ("subprocess", "os.system", "run_escalation", "run_reduction", "experiments.run"):
        assert forbidden not in src
    experiment_routes = [r.path for r in app_mod.app.routes if "/api/experiments" in getattr(r, "path", "")]
    assert all(set(getattr(r, "methods", {"GET"})) <= {"GET", "HEAD"} for r in app_mod.app.routes
               if getattr(r, "path", "") in experiment_routes)  # results are read-only files


def test_public_defaults_are_the_measured_safe_values(monkeypatch):
    for k in [k for k in __import__("os").environ if k.startswith("XZR_")]:
        monkeypatch.delenv(k)
    monkeypatch.setenv("XZR_PUBLIC", "1")
    p = limits_mod.load_limits()
    assert (p.public, p.cookie_secure, p.max_sessions, p.max_sessions_per_client, p.max_nodes, p.max_speed,
            p.max_compare_horizon, p.max_body_bytes) == (True, True, 4, 2, 3_000, 30, 300, 2_000_000)
    assert min(p.rate_api_per_s, p.rate_sessions_per_min, p.rate_jobs_per_min, p.rate_ws_per_min) > 0
    assert p.ops_token == "" and "ops_token" not in p.describe()  # metrics disabled until a token is configured
    monkeypatch.setenv("XZR_MAX_NODES", "10000")  # every limit can be raised for a larger instance
    assert limits_mod.load_limits().max_nodes == 10_000
    monkeypatch.delenv("XZR_PUBLIC")
    monkeypatch.delenv("XZR_MAX_NODES")
    local = limits_mod.load_limits()  # the local single-user runtime keeps its behaviour
    assert (local.public, local.max_nodes, local.max_speed, local.rate_api_per_s) == (False, 500_000, 0, 0)



# ------------------------------------------------------------------------------------------------ proxy trust model
def _ip(limits, headers, peer, proxies="", header="x-forwarded-for"):
    limits(trusted_proxies=limits_mod._proxies(proxies), forwarded_header=header)
    return sec_mod.client_ip({k.lower(): v for k, v in headers.items()}, peer)


def test_forwarding_headers_from_an_untrusted_peer_are_ignored(limits):
    forged = {"x-forwarded-for": "6.6.6.6", "forwarded": "for=6.6.6.6", "x-real-ip": "6.6.6.6"}
    assert _ip(limits, forged, "203.0.113.9") == "203.0.113.9"  # no trusted proxies configured
    for header in limits_mod.FORWARDED_HEADERS:  # a trusted proxy list does not make other peers trusted
        assert _ip(limits, forged, "203.0.113.9", "10.0.0.0/8", header) == "203.0.113.9"


def test_one_trusted_proxy_appending_x_forwarded_for(limits):
    # the client forged "6.6.6.6"; the proxy (10.0.0.5) appended the address it saw
    assert _ip(limits, {"X-Forwarded-For": "6.6.6.6, 198.51.100.7"}, "10.0.0.5", "10.0.0.5") == "198.51.100.7"
    assert _ip(limits, {"X-Forwarded-For": "198.51.100.7:51234"}, "10.0.0.5", "10.0.0.5") == "198.51.100.7"
    assert _ip(limits, {}, "10.0.0.5", "10.0.0.5") == "10.0.0.5"  # no header: the proxy itself


def test_trusted_proxy_network_with_several_hops(limits):
    xff = {"X-Forwarded-For": "6.6.6.6, 198.51.100.7, 10.1.2.3"}  # edge proxy 10.1.2.3, then 10.0.0.5
    assert _ip(limits, xff, "10.0.0.5", "10.0.0.0/8") == "198.51.100.7"
    assert _ip(limits, {"X-Forwarded-For": "10.1.2.3, 10.9.9.9"}, "10.0.0.5", "10.0.0.0/8") == "10.0.0.5"


def test_forwarded_and_x_real_ip_only_when_configured(limits):
    fwd = {"Forwarded": 'for="6.6.6.6";proto=https, for="[2001:db8::7]:4711"', "X-Forwarded-For": "6.6.6.6"}
    assert _ip(limits, fwd, "10.0.0.5", "10.0.0.5", "forwarded") == "2001:db8::7"
    assert _ip(limits, {"X-Real-IP": "198.51.100.7", "X-Forwarded-For": "6.6.6.6"}, "10.0.0.5", "10.0.0.5",
               "x-real-ip") == "198.51.100.7"
    assert _ip(limits, {"Forwarded": "for=unknown"}, "10.0.0.5", "10.0.0.5", "forwarded") == "10.0.0.5"
    assert _ip(limits, {"X-Forwarded-For": "not-an-address"}, "10.0.0.5", "10.0.0.5") == "10.0.0.5"


def test_the_former_trust_all_switch_refuses_to_start(monkeypatch):
    monkeypatch.setenv("XZR_TRUST_PROXY", "1")
    with pytest.raises(RuntimeError, match="XZR_TRUSTED_PROXIES"):
        limits_mod.load_limits()
    monkeypatch.delenv("XZR_TRUST_PROXY")
    monkeypatch.setenv("XZR_FORWARDED_HEADER", "x-client-ip")
    with pytest.raises(RuntimeError):
        limits_mod.load_limits()


def test_forged_headers_cannot_bypass_address_limits(limits):
    limits(max_sessions_per_ip=1, max_sessions_per_client=5, max_ws_per_ip=1)
    a, b = client("203.0.113.9"), client("203.0.113.9")  # one real address, two identities
    sid = create(a)["id"]
    for forged in ({"X-Forwarded-For": "6.6.6.6"}, {"Forwarded": "for=7.7.7.7"}, {"X-Real-IP": "8.8.8.8"}):
        r = b.post("/api/sessions", json={"sample": SAMPLE}, headers=forged)
        assert r.status_code == 429 and r.json()["limit"] == "max_sessions_per_ip", forged
    limits(rate_sessions_per_min=1, max_sessions_per_ip=10, max_sessions_per_client=5)
    sec_mod.RATES._b.clear()
    codes = [b.post("/api/sessions", json={"sample": SAMPLE}, headers={"X-Forwarded-For": f"6.6.6.{i}"}).status_code
             for i in range(3)]
    assert codes[0] == 200 and codes[1:] == [429, 429]  # rotating forged addresses does not reset the bucket
    limits(max_ws_per_ip=1)
    with a.websocket_connect(f"/ws/{sid}") as ws1:
        ws1.receive_text()
        with a.websocket_connect(f"/ws/{sid}", headers={"X-Forwarded-For": "9.9.9.9"}) as ws2:
            assert json.loads(ws2.receive_text())["limit"] == "max_ws_per_ip"


# ------------------------------------------------------------------------------------------------ capability lifecycle
def test_owner_capability_has_an_explicit_lifetime(limits):
    limits(owner_max_age_s=1000)
    t = sec_mod.new_owner_token(now=10_000)
    assert sec_mod.owner_of(t, now=10_500) is not None
    assert sec_mod.owner_of(t, now=11_001) is None  # expired
    assert sec_mod.owner_of(t, now=5_000) is None  # issued in the future (beyond skew)
    assert sec_mod.owner_of("deadbeef", now=10_500) is None and sec_mod.owner_of(None) is None
    forged = "ffffffff." + t.split(".", 1)[1]  # editing the issue time makes a different, empty identity
    assert sec_mod.owner_of(forged, now=10_500) != sec_mod.owner_of(t, now=10_500)


def test_cookie_attributes(limits):
    limits(cookie_secure=True)
    r = client().post("/api/sessions", json={"sample": SAMPLE})
    cookie = r.headers["set-cookie"].lower()
    for attr in ("xzr_owner=", "httponly", "samesite=strict", "secure", "path=/", "max-age="):
        assert attr in cookie, attr


def test_capability_rotation_keeps_the_owners_sessions(limits, monkeypatch):
    limits(owner_max_age_s=1000)
    a = client()
    sid = create(a)["id"]
    old = a.cookies.get(sec_mod.OWNER_COOKIE)
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 600)  # past half the lifetime (one shared time module)
    create(a)
    new = a.cookies.get(sec_mod.OWNER_COOKIE)
    assert new != old
    assert a.get(f"/api/sessions/{sid}").status_code == 200  # rebound to the new capability
    stale = client()
    stale.cookies.set(sec_mod.OWNER_COOKIE, old)
    assert stale.get(f"/api/sessions/{sid}").status_code == 404  # the old capability no longer reaches it


def test_owner_reset_closes_sessions_and_clears_the_capability(limits):
    a = client()
    sid = create(a)["id"]
    r = a.post("/api/owner/reset")
    assert r.status_code == 200 and r.json() == {"closed_sessions": 1}
    cookie = r.headers["set-cookie"].lower()
    assert sid not in app_mod.SESSIONS and "xzr_owner=" in cookie and "max-age=0" in cookie


def test_sessions_are_reaped_when_their_owner_capability_expires(limits):
    a = client()
    sid = create(a)["id"]
    app_mod.SESSIONS[sid].owner_expires = time.time() - 1
    app_mod.reap()
    assert sid not in app_mod.SESSIONS


def test_a_stale_cookie_after_restart_reaches_nothing(limits):
    a = client()
    sid = create(a)["id"]
    for s in list(app_mod.SESSIONS.values()):  # what a restart does to in-memory state
        app_mod.close_session(s, "restart")
    assert a.get(f"/api/sessions/{sid}").json() == {"detail": "no such session"}
    assert a.get("/api/sessions").json() == []
    b = client()
    other = create(b)["id"]  # another visitor's new session after the restart
    assert a.get(f"/api/sessions/{other}").status_code == 404
    assert create(a)["id"] not in (sid, other)  # the stale-cookie owner starts cleanly


# ------------------------------------------------------------------------------------------------ readiness, logs
def test_readiness_and_liveness(limits):
    with TestClient(app_mod.app) as c:  # runs the lifespan: the cleanup task is running
        r = c.get("/api/ready")
        assert r.status_code == 200 and r.json()["ready"] and r.json()["accepting_new_sessions"]
        app_mod._STATE["stopping"] = True
        try:
            assert c.get("/api/ready").status_code == 503
        finally:
            app_mod._STATE["stopping"] = False
        assert c.get("/api/health").status_code == 200
    body = json.dumps(client().get("/api/ready").json())
    assert "owner" not in body and "token" not in body


def test_access_log_lines_shorten_ids():
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                            ("1.2.3.4:5", "GET", "/api/sessions/" + "ab" * 16 + "/tile?x0=1", "1.1", 200), None)
    sec_mod._RedactIds().filter(rec)
    assert "/api/sessions/abababab…/tile?x0=1" in rec.getMessage() and "ab" * 16 not in rec.getMessage()



def test_websocket_origin_allowlist_for_reverse_proxies(limits):
    """Behind a proxy that rewrites Host (e.g. drops the port) the Host comparison would reject the real site."""
    limits(allowed_origins=("https://runtime.example:9443",))
    a = client()
    sid = create(a)["id"]
    with a.websocket_connect(f"/ws/{sid}", headers={"origin": "https://runtime.example:9443", "host": "runtime.example"}) as ws:
        assert json.loads(ws.receive_text())["type"] == "hello"
    for bad in ("https://evil.example", "https://runtime.example", "http://runtime.example:9443"):
        with pytest.raises(WebSocketDisconnect) as e, a.websocket_connect(f"/ws/{sid}", headers={"origin": bad}):
            pass
        assert e.value.code == 4403, bad



def test_unknown_api_paths_are_404_not_the_app(limits, tmp_path, monkeypatch):
    if not any(getattr(r, "path", "") == "/{path:path}" for r in app_mod.app.routes):
        pytest.skip("no built frontend: the static fallback is not mounted")
    c = client()
    for p in ("/api/exec?cmd=ls", "/api/run", "/api", "/api/experiments/run/x", "/ws/x/y"):
        r = c.get(p)
        assert r.status_code == 404 and "text/html" not in r.headers.get("content-type", ""), p
