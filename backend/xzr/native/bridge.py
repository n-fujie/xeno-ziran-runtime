"""The iOS app's in-process API: the simulator's REST + stream interface without sockets, HTTP or FastAPI.

The bundled web UI sends ``{"method", "path", "body"}`` requests through a WKWebView message handler; Swift passes
them to ``handle()`` (one JSON string in, one JSON string out). Only the routes in ``ROUTES`` exist — an explicit
allowlist mirroring the REST routes the UI uses; anything else is 404. No route evaluates code, runs a subprocess or
takes a filesystem path. The WebSocket stream becomes ``/native/stream/...`` routes plus ``poll()``, which Swift calls
on a timer and forwards to the page.

Single device, single user: there is no ownership, cookie, rate limit or proxy logic here. What remains relevant on
a phone is kept: bounded resources (``XZR_MAX_*`` from the app's environment; larger inputs are refused with an
explicit message, never truncated), checkpointing, save / load, and pausing on backgrounding.
"""

from __future__ import annotations

import base64
import json
import re
import threading
import time
from collections import deque
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .. import __version__
from ..scenario.io import list_samples
from ..service import operations as ops
from ..service.limits import LIMITS, LimitError
from ..service.security import check_payload, check_scenario
from ..service.session import JOBS, CommandError, Session, cancel_job, prune_jobs

SESSIONS: dict[str, Session] = {}
_LOCK = threading.RLock()
STREAM_FILTER_MIN = 50_000
DESKTOP_HINT = " — larger workloads run in the desktop runtime"


class _Stream:
    def __init__(self, sid: str, s: Session):
        self.sid = sid
        self.cursor = ops.StreamCursor(s)
        self.pending: deque[tuple[bytes | None, dict | None]] = deque(maxlen=256)  # job notices etc.
        self.listener = lambda msg: self.pending.append((None, msg))
        s.listeners.append(self.listener)
        s.streaming = True


STREAMS: dict[str, _Stream] = {}
SUSPENDED = False  # the app is in the background (between the lifecycle routes)
_PAUSED: set[str] = set()  # sessions paused (or not started) because of the background period
_stream_seq = 0


def _session(sid: str) -> Session:
    s = SESSIONS.get(sid)
    if s is None:
        raise ops.OpError(404, "no such session")
    s.touched = time.time()
    return s


def _close(sid: str) -> None:
    with _LOCK:  # lifecycle requests iterate the sessions from another thread
        s = SESSIONS.pop(sid, None)
    for k in [k for k, st in STREAMS.items() if st.sid == sid]:
        _stream_close(k)
    if s is not None:
        s.close()
        ops.drop_caches(sid)


def _q(query: dict, key: str, default: Any, cast: type = str) -> Any:
    v = query.get(key)
    return cast(v[0]) if v else default


# ------------------------------------------------------------------------------------------------ handlers
def _health(_q: dict, _b: Any) -> dict:
    return {"ok": True, "version": __version__, "sessions": len(SESSIONS), "public": False, "native": True,
            "max_nodes": LIMITS.max_nodes}


def _scenarios(_q: dict, _b: Any) -> list[dict]:
    return list_samples()


_SAMPLE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _create(_q: dict, body: dict) -> dict:
    body = body or {}
    sample = body.get("sample")
    if sample is not None and (not isinstance(sample, str) or not _SAMPLE.fullmatch(sample)):
        raise ops.OpError(404, f"no scenario {sample}")
    if body.get("scenario") is not None:
        check_payload(body["scenario"])
    if body.get("applied") is not None:
        check_payload(body["applied"])
    sc = ops.scenario_from(sample, body.get("scenario"), body.get("seed"))
    try:
        check_scenario(sc)
    except LimitError as e:
        raise LimitError(e.limit, e.message + DESKTOP_HINT, e.status) from e
    flags = ops.runtime_flags(body.get("flags"))
    with _LOCK:
        if len(SESSIONS) >= LIMITS.max_sessions:  # on a single device the oldest session is replaced
            oldest = min(SESSIONS.values(), key=lambda x: x.touched)
            _close(oldest.id)
        s = Session(sc, body.get("applied"), 10, flags)
        SESSIONS[s.id] = s
    return s.info()


def _list(_q: dict, _b: Any) -> list[dict]:
    return [{"id": s.id, "scenario": s.scenario.name, "t": s.engine.state.t, "running": s.running}
            for s in list(SESSIONS.values())]


def _control(s: Session, body: dict) -> dict:
    body = body or {}
    action = str(body.get("action", ""))
    with _LOCK:
        if SUSPENDED and action in ("run", "step"):
            # arrived after the app left the foreground: nothing may start now; reported as paused on return
            _PAUSED.add(s.id)
            return s.status()
    try:
        return s.control(action, int(body.get("steps", 1)), body.get("speed"))
    except CommandError as e:
        raise ops.OpError(400, str(e)) from e


def _delete(sid: str) -> dict:
    _session(sid)
    _close(sid)
    return {"deleted": sid}


def _stream_delete(key: str) -> dict:
    _stream_close(key)
    return {"ok": True}


def _cancel(jid: str) -> dict:
    _job(jid)
    return {"cancelled": cancel_job(jid)}


def _rewind(s: Session, body: dict) -> dict:
    try:
        return s.rewind(int((body or {}).get("t", 0)))
    except ValueError as e:
        raise ops.OpError(400, str(e)) from e


def _tile(s: Session, q: dict) -> tuple[bytes, int]:
    return ops.tile(s, _q(q, "layout", "network"), _q(q, "x0", 0, float), _q(q, "y0", 0, float),
                    _q(q, "x1", 1000, float), _q(q, "y1", 1000, float), _q(q, "level", 4, int),
                    _q(q, "max_nodes", 20000, int), _q(q, "max_edges", 20000, int))


def _export(s: Session, q: dict) -> tuple[Any, str]:
    body, media = ops.export(s, _q(q, "what", "nodes"), _q(q, "format", "csv"))
    size = len(json.dumps(body)) if media == "application/json" else len(body)
    if size > LIMITS.max_export_bytes:
        raise LimitError("max_export_bytes", f"export of {size:,} bytes exceeds {LIMITS.max_export_bytes:,}", 413)
    return body, media


def _job(jid: str) -> dict:
    j = JOBS.get(jid)
    if j is None or j["session"] not in SESSIONS:
        raise ops.OpError(404, "no such job")
    return dict(j)


def _stream_open(sid: str) -> dict:
    global _stream_seq
    s = _session(sid)
    with _LOCK:
        _stream_seq += 1
        key = f"st{_stream_seq}"
        st = _Stream(sid, s)
        STREAMS[key] = st
    return {"stream": key, "items": _encode(st.cursor.hello())}


def _stream_close(key: str) -> None:
    st = STREAMS.pop(key, None)
    if st is None:
        return
    s = SESSIONS.get(st.sid)
    if s is not None:
        if st.listener in s.listeners:
            s.listeners.remove(st.listener)
        s.streaming = any(x.sid == st.sid for x in STREAMS.values())


def _stream_message(key: str, body: dict) -> dict:
    st = STREAMS.get(key)
    if st is None:
        raise ops.OpError(404, "no such stream")
    body = body or {}
    if body.get("type") == "view":
        st.cursor.view(int(body.get("level", 0)), body.get("clusters"), STREAM_FILTER_MIN)
    elif body.get("type") == "ping":
        st.pending.append((None, {"type": "pong", "t": body.get("t")}))
    return {"ok": True}


def _background(_q: dict, _b: Any) -> dict:
    """The app is leaving the foreground: pause every running session (iOS suspends the process; nothing runs).
    Until ``_foreground``, run / step requests that still arrive are not started (see ``_control``)."""
    global SUSPENDED
    paused = []
    with _LOCK:
        SUSPENDED = True
        for s in SESSIONS.values():
            if s.running or s.pending_steps:
                s.control("pause")
                paused.append(s.id)
        _PAUSED.update(paused)
    return {"paused": paused}


def _foreground(_q: dict, _b: Any) -> dict:
    """The app is active again: runs may start; reports every session paused because of the background period."""
    global SUSPENDED
    with _LOCK:
        SUSPENDED = False
        paused = sorted(sid for sid in _PAUSED if sid in SESSIONS)
        _PAUSED.clear()
    return {"paused": paused}


def _memory_warning(_q: dict, _b: Any) -> dict:
    """The system reported memory pressure: pause running sessions and drop the rebuildable tile indexes (nothing the
    user made is discarded; sessions, checkpoints and comparisons stay)."""
    paused = []
    with _LOCK:
        for s in SESSIONS.values():
            if s.running or s.pending_steps:
                s.control("pause")
                paused.append(s.id)
    for sid in list(SESSIONS):
        ops.drop_caches(sid)
    return {"paused": paused}


# (method, path pattern, handler(match, query, body) -> (status, kind, value))
def _json(v: Any) -> tuple[int, str, Any]:
    return 200, "json", v


ROUTES: list[tuple[str, re.Pattern, Any]] = [(m, re.compile(p), h) for m, p, h in [
    ("GET", r"/api/health", lambda m, q, b: _json(_health(q, b))),
    ("GET", r"/api/scenarios", lambda m, q, b: _json(_scenarios(q, b))),
    ("POST", r"/api/sessions", lambda m, q, b: _json(_create(q, b))),
    ("GET", r"/api/sessions", lambda m, q, b: _json(_list(q, b))),
    ("GET", r"/api/sessions/(?P<sid>[0-9a-f]{32})", lambda m, q, b: _json(_session(m["sid"]).info())),
    ("DELETE", r"/api/sessions/(?P<sid>[0-9a-f]{32})", lambda m, q, b: _json(_delete(m["sid"]))),
    ("POST", r"/api/sessions/(?P<sid>[0-9a-f]{32})/control", lambda m, q, b: _json(_control(_session(m["sid"]), b))),
    ("POST", r"/api/sessions/(?P<sid>[0-9a-f]{32})/rewind", lambda m, q, b: _json(_rewind(_session(m["sid"]), b))),
    ("GET", r"/api/sessions/(?P<sid>[0-9a-f]{32})/hierarchy", lambda m, q, b: _json(ops.hierarchy(_session(m["sid"])))),
    ("GET", r"/api/sessions/(?P<sid>[0-9a-f]{32})/clusters",
     lambda m, q, b: _json(ops.clusters(_session(m["sid"]), _q(q, "level", 0, int)))),
    ("GET", r"/api/sessions/(?P<sid>[0-9a-f]{32})/tile", lambda m, q, b: (200, "binary", _tile(_session(m["sid"]), q)[0])),
    ("GET", r"/api/sessions/(?P<sid>[0-9a-f]{32})/snapshot", lambda m, q, b: (200, "binary", ops.snapshot(_session(m["sid"])))),
    ("GET", r"/api/sessions/(?P<sid>[0-9a-f]{32})/node/(?P<i>\d{1,9})",
     lambda m, q, b: _json(ops.node(_session(m["sid"]), int(m["i"])))),
    ("GET", r"/api/sessions/(?P<sid>[0-9a-f]{32})/events",
     lambda m, q, b: _json(_session(m["sid"]).events(_q(q, "since", 0, int), _q(q, "until", None, int),
                                                     min(2000, _q(q, "limit", 200, int))))),
    ("GET", r"/api/sessions/(?P<sid>[0-9a-f]{32})/metrics",
     lambda m, q, b: _json(_session(m["sid"]).metrics(_q(q, "since", 0, int)))),
    ("GET", r"/api/sessions/(?P<sid>[0-9a-f]{32})/shapes", lambda m, q, b: _json(_session(m["sid"]).shapes())),
    ("GET", r"/api/sessions/(?P<sid>[0-9a-f]{32})/practice", lambda m, q, b: _json(_session(m["sid"]).practice_view())),
    ("POST", r"/api/sessions/(?P<sid>[0-9a-f]{32})/practice/command",
     lambda m, q, b: _json(ops.command(_session(m["sid"]), str((b or {}).get("text", "")),
                                       bool((b or {}).get("auto_compare", True)), int((b or {}).get("horizon", 150))))),
    ("POST", r"/api/sessions/(?P<sid>[0-9a-f]{32})/compare",
     lambda m, q, b: _json({"job": _session(m["sid"]).start_compare(int((b or {}).get("horizon", 150)))})),
    ("GET", r"/api/sessions/(?P<sid>[0-9a-f]{32})/compare/(?P<cid>[0-9a-f]{32})",
     lambda m, q, b: _json(ops.compare_result(_session(m["sid"]), m["cid"]))),
    ("GET", r"/api/jobs/(?P<jid>[0-9a-f]{32})", lambda m, q, b: _json(_job(m["jid"]))),
    ("POST", r"/api/jobs/(?P<jid>[0-9a-f]{32})/cancel",
     lambda m, q, b: _json(_cancel(m["jid"]))),
    ("GET", r"/api/sessions/(?P<sid>[0-9a-f]{32})/save", lambda m, q, b: _json(_session(m["sid"]).save())),
    ("GET", r"/api/sessions/(?P<sid>[0-9a-f]{32})/export",
     lambda m, q, b: (lambda r: (200, "json" if r[1] == "application/json" else "text", r[0]))(
         _export(_session(m["sid"]), q))),
    ("POST", r"/native/stream/(?P<sid>[0-9a-f]{32})", lambda m, q, b: _json(_stream_open(m["sid"]))),
    ("POST", r"/native/stream/(?P<key>st\d{1,9})/message", lambda m, q, b: _json(_stream_message(m["key"], b))),
    ("DELETE", r"/native/stream/(?P<key>st\d{1,9})", lambda m, q, b: _json(_stream_delete(m["key"]))),
    ("POST", r"/native/lifecycle/background", lambda m, q, b: _json(_background(q, b))),
    ("POST", r"/native/lifecycle/foreground", lambda m, q, b: _json(_foreground(q, b))),
    ("POST", r"/native/lifecycle/memory-warning", lambda m, q, b: _json(_memory_warning(q, b))),
]]


def _encode(items: list[tuple[bytes | None, dict | None]]) -> list[dict]:
    out: list[dict[str, Any]] = []
    for data, meta in items:
        if data is not None:
            out.append({"b64": base64.b64encode(data).decode("ascii")})
        if meta is not None:
            out.append({"json": meta})
    return out


def handle(request: str) -> str:
    """One request (JSON: method, path incl. query, optional body) → one response (JSON: status, kind, body)."""
    try:
        req = json.loads(request)
        method = str(req.get("method", "GET")).upper()
        url = urlsplit(str(req.get("path", "")))
        body = req.get("body")
        if isinstance(body, str):
            body = json.loads(body) if body else None
        query = parse_qs(url.query)
        for m, pattern, handler in ROUTES:
            match = pattern.fullmatch(url.path)
            if match and m == method:
                status, kind, value = handler(match, query, body)
                break
        else:
            raise ops.OpError(404, "Not Found")
    except ops.OpError as e:
        status, kind, value = e.status, "json", (e.body if isinstance(e.body, dict) and "error" in e.body
                                                 else {"detail": e.body})
    except LimitError as e:
        status, kind, value = e.status, "json", e.body()
    except (ValueError, TypeError, KeyError) as e:
        status, kind, value = 400, "json", {"detail": f"malformed request: {e}"}
    if kind == "binary":
        value = base64.b64encode(value).decode("ascii")
    return json.dumps({"status": status, "kind": kind, "body": value})


def poll() -> str:
    """Pending stream items for every open stream: ``[{"stream": key, "items": [...]}, ...]`` (JSON)."""
    out = []
    for key, st in list(STREAMS.items()):
        if st.sid not in SESSIONS:
            continue
        items = list(st.pending)
        st.pending.clear()
        items += st.cursor.poll()
        out.append({"stream": key, "items": _encode(items)})
    prune_jobs()
    return json.dumps(out)
