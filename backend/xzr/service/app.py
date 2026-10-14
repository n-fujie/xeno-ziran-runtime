"""HTTP + WebSocket service.

REST controls sessions, scenarios, interventions, comparisons, exports and LOD queries. A WebSocket per
client streams binary delta frames at a capped frame rate; simulation speed is independent of it.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import __version__
from ..scenario.io import list_samples, load_sample
from . import operations as ops
from .limits import LIMITS, LimitError
from .protocol import encode_aggregates, encode_deltas, encode_snapshot
from .security import (
    METRICS,
    OWNER_COOKIE,
    RATES,
    check_payload,
    check_rate,
    check_scenario,
    client_ip,
    event,
    new_owner_token,
    owner_of,
    rss_bytes,
    short,
    token_issued,
)
from .session import JOBS, CommandError, Session, active_jobs, cancel_job, prune_jobs

FRAME_HZ = float(os.environ.get("XZR_FRAME_HZ", "30"))
STREAM_FILTER_MIN = int(os.environ.get("XZR_STREAM_FILTER_MIN", "50000"))
STATIC_DIR = Path(os.environ.get("XZR_STATIC", Path(__file__).resolve().parents[3] / "frontend" / "dist"))

SESSIONS: dict[str, Session] = {}


_CREATE_LOCK = asyncio.Lock()


def close_session(s: Session, reason: str) -> None:
    s.close()
    SESSIONS.pop(s.id, None)
    ops.drop_caches(s.id)
    METRICS.inc(f"sessions_closed_{reason}")


def reap(now: float | None = None) -> int:
    """Close sessions idle beyond the TTL (no API call or socket message; an open socket pings) or older than the
    absolute lifetime; prune finished jobs and stale rate buckets."""
    now = time.time() if now is None else now
    n = 0
    for s in list(SESSIONS.values()):
        idle = now - s.touched > LIMITS.session_idle_s
        if now > s.owner_expires:
            close_session(s, "owner_expired")  # its capability can no longer reach it
        elif now - s.created > LIMITS.session_max_age_s:
            close_session(s, "expired")
        elif idle:
            close_session(s, "idle")
        else:
            continue
        n += 1
    prune_jobs(now)
    RATES.prune()
    return n


async def _reaper() -> None:
    while True:
        await asyncio.sleep(15)
        try:
            reap()
        except Exception as e:  # noqa: BLE001 — the reaper must keep running
            event("reaper_error", error=type(e).__name__)


_STATE: dict = {"reaper": None, "stopping": False}


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_reaper())
    _STATE["reaper"], _STATE["stopping"] = task, False
    event("start", public=LIMITS.public, limits=LIMITS.describe())
    yield
    _STATE["stopping"] = True
    task.cancel()
    for s in list(SESSIONS.values()):
        s.close()


app = FastAPI(title="XENO ZIRAN SIMULATOR runtime", version=__version__, lifespan=lifespan)


def get(sid: str) -> Session:
    s = SESSIONS.get(sid)
    if s is None:
        raise HTTPException(404, "no such session")
    s.touched = time.time()
    return s


@app.exception_handler(ops.OpError)
async def _op_error(_: Request, e: ops.OpError) -> JSONResponse:
    # practice-command errors keep their own shape ({"error", "suggestions"}); others are HTTPException-shaped
    body = e.body if isinstance(e.body, dict) and "error" in e.body else {"detail": e.body}
    return JSONResponse(body, status_code=e.status)


@app.exception_handler(LimitError)
async def _limit_error(_: Request, e: LimitError) -> JSONResponse:
    METRICS.reject(e.limit)
    return JSONResponse(e.body(), status_code=e.status)


_SESSION_PATH = re.compile(r"^/api/sessions/([^/]+)")
_JOB_PATH = re.compile(r"^/api/jobs/([^/]+)")
_JOB_ROUTES = re.compile(r"^/api/sessions/[^/]+/(compare|practice/command)$")


def _owns(request_owner: str | None, s: Session | None) -> bool:
    return s is not None and s.owner is not None and s.owner == request_owner


@app.middleware("http")
async def guard(request: Request, call_next):
    """The access boundary and abuse controls, applied before any route: request rates per client IP, request body
    size, and ownership of every session (and of its jobs). A session or job the caller does not own is answered
    exactly like one that does not exist."""
    path = request.url.path
    if not path.startswith("/api/") or path in ("/api/health", "/api/ready"):
        return await call_next(request)
    ip = client_ip({k.lower(): v for k, v in request.headers.items()}, request.client.host if request.client else None)
    try:
        check_rate("api", ip)
        if request.method in ("POST", "PUT", "PATCH"):
            length = request.headers.get("content-length")
            if length is None and LIMITS.public:
                raise LimitError("content_length", "a request body needs a Content-Length", 411)
            if length is not None and int(length) > LIMITS.max_body_bytes:
                raise LimitError("max_body", f"request body exceeds {LIMITS.max_body_bytes:,} bytes", 413)
            if path == "/api/sessions":
                check_rate("sessions", ip)
            elif _JOB_ROUTES.match(path):
                check_rate("jobs", ip)
    except LimitError as e:
        METRICS.reject(e.limit)
        return JSONResponse(e.body(), status_code=e.status, headers={"Retry-After": "5"} if e.status == 429 else None)
    owner = owner_of(request.cookies.get(OWNER_COOKIE))
    m = _SESSION_PATH.match(path)
    if m and not _owns(owner, SESSIONS.get(m.group(1))):
        METRICS.inc("denied_session")
        return JSONResponse({"detail": "no such session"}, status_code=404)
    m = _JOB_PATH.match(path)
    if m:
        job = JOBS.get(m.group(1))
        if job is None or not _owns(owner, SESSIONS.get(job["session"])):
            METRICS.inc("denied_job")
            return JSONResponse({"detail": "no such job"}, status_code=404)
    request.state.ip = ip
    request.state.owner = owner
    response = await call_next(request)
    METRICS.inc(f"http_{response.status_code // 100}xx")
    return response


# ---------------------------------------------------------------------------------------------- basics
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": __version__, "sessions": len(SESSIONS), "public": LIMITS.public,
            "max_nodes": LIMITS.max_nodes}


MEMORY_READY_FRACTION = float(os.environ.get("XZR_READY_MEMORY_FRACTION", "0.9"))


def _memory_limit() -> int | None:
    """The container's memory limit (cgroup v2 / v1), if any."""
    for f in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            v = Path(f).read_text().strip()
            if v.isdigit() and int(v) < 1 << 60:
                return int(v)
        except OSError:
            continue
    return None


@app.get("/api/ready")
def ready() -> JSONResponse:
    """Readiness: whether this process can safely serve its sessions (cleanup running, not shutting down, memory
    below the container limit's headroom). Being full is not unreadiness — a single instance taken out of rotation
    would cut off its existing sessions — and is reported as `accepting_new_sessions`."""
    reaper = _STATE["reaper"]
    limit = _memory_limit()
    rss = rss_bytes()
    checks = {"cleanup_running": reaper is not None and not reaper.done(), "not_stopping": not _STATE["stopping"],
              "memory_headroom": limit is None or rss < MEMORY_READY_FRACTION * limit}
    ok = all(checks.values())
    return JSONResponse({"ready": ok, "checks": checks, "accepting_new_sessions": len(SESSIONS) < LIMITS.max_sessions},
                        status_code=200 if ok else 503)


@app.get("/api/scenarios")
def scenarios() -> list[dict]:
    return list_samples()


@app.get("/api/scenarios/{sid}")
def scenario(sid: str) -> dict:
    try:
        return load_sample(sid).model_dump(mode="json", exclude_none=True)
    except KeyError as e:
        raise HTTPException(404, f"no scenario {sid}") from e


class CreateSession(BaseModel):
    sample: str | None = None
    scenario: dict | None = None
    applied: dict | None = None
    seed: int | None = None
    flags: str | dict | None = None  # "full" | "minimal" | explicit runtime flags


@app.post("/api/sessions")
async def create_session(req: CreateSession, request: Request, response: Response) -> dict:
    # ownership: the browser's anonymous capability (created with its first session, rotated past half its lifetime;
    # the caller's live sessions move to the new capability)
    token = request.cookies.get(OWNER_COOKIE)
    owner = owner_of(token)
    issued = token_issued(token) if owner else None
    if owner is None or issued is None or time.time() - issued > LIMITS.owner_max_age_s / 2:
        previous = owner
        token = new_owner_token()
        owner = owner_of(token)
        _set_owner_cookie(response, token)
        if previous is not None:
            for x in SESSIONS.values():
                if x.owner == previous:
                    x.owner, x.owner_expires = owner, time.time() + LIMITS.owner_max_age_s
            METRICS.inc("owner_rotated")
    owner_expires = (token_issued(token) or time.time()) + LIMITS.owner_max_age_s
    ip = getattr(request.state, "ip", "unknown")
    # bounds on the payload and on the world it would build, before anything is allocated
    if req.scenario is not None:
        check_payload(req.scenario)
    if req.applied is not None:
        check_payload(req.applied)
    sc = ops.scenario_from(req.sample, req.scenario, req.seed)
    check_scenario(sc)
    flags = ops.runtime_flags(req.flags)
    async with _CREATE_LOCK:
        reap()
        # a client at its own limit replaces its own least recently used session — never anyone else's
        mine = sorted((x for x in SESSIONS.values() if x.owner == owner), key=lambda x: x.touched)
        replaced = None
        if len(mine) >= LIMITS.max_sessions_per_client:
            replaced = mine[0].id
            close_session(mine[0], "replaced_by_owner")
        if sum(1 for x in SESSIONS.values() if x.ip == ip and x.owner != owner) + \
                sum(1 for x in SESSIONS.values() if x.owner == owner) >= LIMITS.max_sessions_per_ip:
            raise LimitError("max_sessions_per_ip", f"at most {LIMITS.max_sessions_per_ip} live sessions per "
                             "client address; close one or wait for idle sessions to expire")
        if len(SESSIONS) >= LIMITS.max_sessions:
            raise LimitError("max_sessions", f"the runtime is at capacity ({LIMITS.max_sessions} live sessions); "
                             "retry later", 503)
        s = await asyncio.to_thread(Session, sc, req.applied, 10, flags)
        s.owner, s.ip, s.owner_expires = owner, ip, owner_expires
        SESSIONS[s.id] = s
    METRICS.inc("sessions_created")
    event("session_created", session=s.id[:8], client=short(ip), n=s.engine.state.n, replaced=replaced is not None)
    return s.info() | ({"replaced_session": replaced} if replaced else {})


def _set_owner_cookie(response: Response, token: str) -> None:
    response.set_cookie(OWNER_COOKIE, token, httponly=True, samesite="strict", secure=LIMITS.cookie_secure,
                        max_age=int(LIMITS.owner_max_age_s), path="/")


@app.post("/api/owner/reset")
def owner_reset(request: Request, response: Response) -> dict:
    """Forget this browser's anonymous identity: close its sessions and clear the capability cookie."""
    owner = owner_of(request.cookies.get(OWNER_COOKIE))
    closed = [x for x in list(SESSIONS.values()) if owner is not None and x.owner == owner]
    for x in closed:
        close_session(x, "owner_reset")
    response.delete_cookie(OWNER_COOKIE, path="/", secure=LIMITS.cookie_secure, httponly=True, samesite="strict")
    return {"closed_sessions": len(closed)}


@app.get("/api/sessions")
def sessions(request: Request) -> list[dict]:
    """The caller's own sessions only."""
    owner = owner_of(request.cookies.get(OWNER_COOKIE))
    return [{"id": s.id, "scenario": s.scenario.name, "t": s.engine.state.t, "running": s.running}
            for s in SESSIONS.values() if _owns(owner, s)]


@app.get("/api/sessions/{sid}")
def session_info(sid: str) -> dict:
    return get(sid).info()


@app.delete("/api/sessions/{sid}")
def delete_session(sid: str) -> dict:
    close_session(get(sid), "deleted")
    return {"deleted": sid}


class Control(BaseModel):
    action: str
    steps: int = 1
    speed: float | None = None


@app.post("/api/sessions/{sid}/control")
async def control(sid: str, c: Control) -> dict:
    s = get(sid)
    try:
        if c.action == "reset":
            return await asyncio.to_thread(s.control, "reset")
        return s.control(c.action, c.steps, c.speed)
    except CommandError as e:
        raise HTTPException(400, str(e)) from e


class Rewind(BaseModel):
    t: int


@app.post("/api/sessions/{sid}/rewind")
async def rewind(sid: str, r: Rewind) -> dict:
    s = get(sid)
    try:
        return await asyncio.to_thread(s.rewind, r.t)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# ---------------------------------------------------------------------------------------------- LOD
@app.get("/api/sessions/{sid}/hierarchy")
def hierarchy(sid: str) -> dict:
    return ops.hierarchy(get(sid))


@app.get("/api/sessions/{sid}/clusters")
def clusters(sid: str, level: int = Query(0, ge=0, le=3)) -> dict:
    return ops.clusters(get(sid), level)


@app.get("/api/sessions/{sid}/tile")
def tile(sid: str, layout: str = "network", x0: float = 0, y0: float = 0, x1: float = 1000, y1: float = 1000,
         level: int = Query(4, ge=4, le=5), max_nodes: int = 20000, max_edges: int = 20000) -> Response:
    body, layout_version = ops.tile(get(sid), layout, x0, y0, x1, y1, level, max_nodes, max_edges)
    return Response(body, media_type="application/octet-stream", headers={"X-Layout-Version": str(layout_version)})


@app.get("/api/sessions/{sid}/snapshot")
def snapshot(sid: str) -> Response:
    return Response(ops.snapshot(get(sid)), media_type="application/octet-stream")


# ---------------------------------------------------------------------------------------------- inspection
@app.get("/api/sessions/{sid}/node/{i}")
def node(sid: str, i: int) -> dict:
    return ops.node(get(sid), i)


@app.get("/api/sessions/{sid}/events")
def events(sid: str, since: int = 0, until: int | None = None, limit: int = Query(200, le=2000)) -> list[dict]:
    return get(sid).events(since, until, limit)


@app.get("/api/sessions/{sid}/metrics")
def metrics(sid: str, since: int = 0) -> dict:
    return get(sid).metrics(since)


@app.get("/api/sessions/{sid}/shapes")
def shapes(sid: str) -> dict:
    return get(sid).shapes()


# ---------------------------------------------------------------------------------------------- practice / compare
@app.get("/api/sessions/{sid}/practice")
def practice(sid: str) -> dict:
    return get(sid).practice_view()


class Cmd(BaseModel):
    text: str
    auto_compare: bool = True
    horizon: int = 150


@app.post("/api/sessions/{sid}/practice/command", response_model=None)
def practice_command(sid: str, c: Cmd) -> dict:
    return ops.command(get(sid), c.text, c.auto_compare, c.horizon)


class CompareReq(BaseModel):
    horizon: int = 150


@app.post("/api/sessions/{sid}/compare")
def start_compare(sid: str, r: CompareReq) -> dict:
    return {"job": get(sid).start_compare(r.horizon)}


@app.get("/api/sessions/{sid}/compare/{cid}")
def get_compare(sid: str, cid: str) -> dict:
    return ops.compare_result(get(sid), cid)


@app.get("/api/jobs/{jid}")
def job(jid: str) -> dict:
    j = JOBS.get(jid)
    if j is None:
        raise HTTPException(404, "no such job")
    return dict(j)


@app.post("/api/jobs/{jid}/cancel")
def cancel(jid: str) -> dict:
    """Cancel a queued comparison; a running one completes within its horizon cap."""
    return {"cancelled": cancel_job(jid), "status": JOBS[jid]["status"] if jid in JOBS else "gone"}


# ---------------------------------------------------------------------------------------------- operations
@app.get("/api/ops/metrics")
def ops_metrics(request: Request) -> dict:
    """Counts for operating the service (no ids, addresses, tokens or research payloads). In public mode it needs
    the X-Ops-Token header matching XZR_OPS_TOKEN and is disabled when that is unset."""
    if LIMITS.public and (not LIMITS.ops_token or request.headers.get("x-ops-token") != LIMITS.ops_token):
        raise HTTPException(404, "Not Found")
    live = list(SESSIONS.values())
    lat = [x.step_latency for x in live if x.step_latency > 0]
    return {
        "uptime_s": round(time.time() - METRICS.started), "public": LIMITS.public,
        "sessions_active": len(live), "websockets_active": sum(len(c) for c in CLIENTS.values()),
        "jobs": {"active": active_jobs(), "retained": len(JOBS)},
        "counters": dict(METRICS.counters), "rejected_by_limit": dict(METRICS.rejected),
        "memory_rss_bytes": rss_bytes(), "process_cpu_s": round(time.process_time(), 2),
        "step_latency_ms_mean": round(1000 * sum(lat) / len(lat), 3) if lat else None,
        "steps_per_second_total": round(sum(x.steps_per_second() for x in live), 1),
        "limits": LIMITS.describe(),
    }


# ---------------------------------------------------------------------------------------------- persistence
@app.get("/api/sessions/{sid}/save")
def save(sid: str) -> dict:
    return get(sid).save()


@app.get("/api/sessions/{sid}/export")
def export(sid: str, what: str = "nodes", format: str = "csv") -> Response:  # noqa: A002
    body, media = ops.export(get(sid), what, format)
    r = JSONResponse(body) if media == "application/json" else PlainTextResponse(body, media_type=media)
    if len(r.body) > LIMITS.max_export_bytes:
        raise LimitError("max_export_bytes", f"export of {len(r.body):,} bytes exceeds {LIMITS.max_export_bytes:,}", 413)
    return r


# ---------------------------------------------------------------------------------------------- experiments
EXP_DIR = Path(__file__).resolve().parents[2] / "experiments" / "results"


@app.get("/api/experiments")
def experiments() -> list[dict]:
    """Result files: experiments/results/*.json, resolution-escalation results (results/resolution/*.json) under the
    name ``resolution-<stem>``, and HPO results (results/hpo/*.json) under ``hpo-<stem>``."""
    out = [{"name": p.stem, "bytes": p.stat().st_size, "modified": p.stat().st_mtime}
           for p in sorted(EXP_DIR.glob("*.json"))]
    out += [{"name": f"resolution-{p.stem}", "bytes": p.stat().st_size, "modified": p.stat().st_mtime}
            for p in sorted((EXP_DIR / "resolution").glob("*.json"))]
    out += [{"name": f"hpo-{p.stem}", "bytes": p.stat().st_size, "modified": p.stat().st_mtime}
            for p in sorted((EXP_DIR / "hpo").glob("*.json"))]
    out += [{"name": f"lab-{p.stem}", "bytes": p.stat().st_size, "modified": p.stat().st_mtime}
            for p in sorted((EXP_DIR / "lab").glob("*.json"))]
    return [e for e in out if _NAME.fullmatch(str(e["name"]))]  # only names the endpoint below serves


_NAME = re.compile(r"[a-z0-9_\-]+")


def _experiment_path(name: str) -> Path | None:
    if not re.fullmatch(r"[a-z0-9_\-]+", name):
        return None
    if name.startswith("resolution-"):
        p = EXP_DIR / "resolution" / f"{name[len('resolution-'):]}.json"
    elif name.startswith("hpo-"):
        p = EXP_DIR / "hpo" / f"{name[len('hpo-'):]}.json"
    elif name.startswith("lab-"):
        p = EXP_DIR / "lab" / f"{name[len('lab-'):]}.json"
    else:
        p = EXP_DIR / f"{name}.json"
    return p if p.is_file() else None


@app.get("/api/experiments/primitives")
def experiment_primitives() -> list[dict]:
    from ..experiments.catalog import primitives
    return primitives()


@app.get("/api/experiments/{name}")
def experiment(name: str) -> Response:
    p = _experiment_path(name)
    if p is None:
        raise HTTPException(404, f"no experiment result {name}")
    return FileResponse(p, media_type="application/json")


# ---------------------------------------------------------------------------------------------- websocket
class Client:
    """One socket. Outbound frames go through a bounded queue drained by a writer task, so a slow client never
    stalls the broadcaster or other clients. On overflow its pending delta frames are dropped and it is resynchronised
    with a full snapshot (no state is lost) and told so explicitly."""

    def __init__(self, ws: WebSocket, ip: str):
        self.ws = ws
        self.ip = ip
        self.level = 0
        self.node_filter: np.ndarray | None = None
        self.bytes = 0
        self.frames = 0
        self.queue: asyncio.Queue[tuple[bytes | None, dict | None]] = asyncio.Queue(maxsize=LIMITS.ws_queue)
        self.need_resync = False
        self.resyncs = 0
        self.writer: asyncio.Task | None = None


BROADCASTERS: dict[str, asyncio.Task] = {}
CLIENTS: dict[str, set[Client]] = {}


async def _broadcast(s: Session) -> None:
    period = 1.0 / FRAME_HZ
    last_layout = s.layout_version
    last_graph = None
    while CLIENTS.get(s.id):
        await asyncio.sleep(period)
        steps, resync = s.take_outbox()
        clients = list(CLIENTS.get(s.id, ()))
        lagging = [c for c in clients if c.need_resync]
        if resync or lagging:
            snap = await asyncio.to_thread(lambda: encode_snapshot_locked(s))
            for c in (clients if resync else lagging):
                c.need_resync = False
                _send(s, c, snap, {"type": "resync", **s.status()})
        if steps:
            frames: dict[int, bytes] = {}
            for c in clients:
                key = id(c.node_filter) if c.node_filter is not None else 0
                if key not in frames:
                    frames[key] = await asyncio.to_thread(encode_deltas, steps, c.node_filter)
                with s.lock:
                    agg = encode_aggregates(c.level, s.h.labels[c.level], s.h.n_clusters(c.level), steps,
                                            s.engine.state.diff, s.engine.state.t)
                _send(s, c, frames[key], None)
                _send(s, c, agg, None)
        with s.lock:
            meta = {"type": "metrics", "step": s.latest, **s.status()}
            if s.graph_latest is not last_graph:
                meta["graph"] = last_graph = s.graph_latest
            if s.layout_version != last_layout:
                last_layout = s.layout_version
                meta["layout_changed"] = "shape"
        for c in clients:
            _send(s, c, None, {**meta, "stream": {"frames": c.frames, "bytes": c.bytes, "resyncs": c.resyncs}})
    BROADCASTERS.pop(s.id, None)


def encode_snapshot_locked(s: Session) -> bytes:
    with s.lock:
        return encode_snapshot(s.engine)


def _send(s: Session, c: Client, data: bytes | None, meta: dict | None) -> None:
    """Queue a frame for the client's writer (never blocks)."""
    try:
        c.queue.put_nowait((data, meta))
    except asyncio.QueueFull:
        # too slow: keep the JSON messages (job notices, metrics), drop the queued binary deltas, resynchronise
        kept = []
        while not c.queue.empty():
            d, m = c.queue.get_nowait()
            if m is not None:
                kept.append((None, m))
        notice = {"type": "notice", "notice": "stream resynchronised: this connection could not keep up with the "
                  "update rate; the full state is resent"}
        for item in kept[-(LIMITS.ws_queue - 2):] + [(None, notice)] + ([(None, meta)] if meta and not data else []):
            c.queue.put_nowait(item)
        c.need_resync = True
        c.resyncs += 1
        METRICS.inc("ws_resyncs")


async def _writer(s: Session, c: Client) -> None:
    while True:
        data, meta = await c.queue.get()
        try:
            if data is not None:
                await c.ws.send_bytes(data)
                c.bytes += len(data)
                c.frames += 1
                METRICS.inc("ws_frames")
            if meta is not None:
                await c.ws.send_text(json.dumps(meta))
        except Exception:  # noqa: BLE001 — a dead socket is removed by its reader
            CLIENTS.get(s.id, set()).discard(c)
            return


def _ws_reject(limit: str) -> None:
    METRICS.reject(limit)


@app.websocket("/ws/{sid}")
async def ws_endpoint(ws: WebSocket, sid: str) -> None:
    s = SESSIONS.get(sid)
    headers = {k.lower(): v for k, v in ws.headers.items()}
    origin = headers.get("origin")
    # same-origin only (with SameSite=Strict on the capability cookie this blocks cross-site socket hijacking):
    # the configured origins, or else the request's own Host
    allowed = (origin is None or origin.rstrip("/").lower() in LIMITS.allowed_origins if LIMITS.allowed_origins
               else origin is None or origin.split("://", 1)[-1] == headers.get("host", ""))
    if not allowed:
        _ws_reject("ws_origin")
        await ws.close(code=4403)
        return
    if not _owns(owner_of(ws.cookies.get(OWNER_COOKIE)), s):
        METRICS.inc("denied_ws")
        await ws.close(code=4404)  # an unowned session is indistinguishable from a missing one
        return
    assert s is not None
    ip = client_ip(headers, ws.client.host if ws.client else None)
    try:
        check_rate("ws", ip)
        total = sum(len(v) for v in CLIENTS.values())
        if total >= LIMITS.max_ws:
            raise LimitError("max_ws", "the runtime has no free stream connections; retry later", 503)
        if len(CLIENTS.get(sid, ())) >= LIMITS.max_ws_per_session:
            raise LimitError("max_ws_per_session", f"at most {LIMITS.max_ws_per_session} streams per session")
        if sum(1 for v in CLIENTS.values() for c in v if c.ip == ip) >= LIMITS.max_ws_per_ip:
            raise LimitError("max_ws_per_ip", f"at most {LIMITS.max_ws_per_ip} streams per client address")
    except LimitError as e:
        METRICS.reject(e.limit)
        await ws.accept()
        await ws.send_text(json.dumps({"type": "error", **e.body()}))
        await ws.close(code=1013)
        return
    await ws.accept()
    c = Client(ws, ip)
    loop = asyncio.get_running_loop()

    def listener(msg: dict) -> None:
        loop.call_soon_threadsafe(lambda: _send(s, c, None, msg))

    s.listeners.append(listener)
    await ws.send_text(json.dumps({"type": "hello", **s.info()}))
    await ws.send_bytes(encode_snapshot_locked(s))
    c.writer = asyncio.create_task(_writer(s, c))
    CLIENTS.setdefault(sid, set()).add(c)
    METRICS.inc("ws_opened")
    s.streaming = True
    if sid not in BROADCASTERS:
        BROADCASTERS[sid] = asyncio.create_task(_broadcast(s))
    window, count = time.monotonic(), 0
    try:
        while True:
            try:
                text = await asyncio.wait_for(ws.receive_text(), timeout=LIMITS.ws_idle_s)
            except TimeoutError:
                await ws.close(code=1001, reason="idle")
                METRICS.inc("ws_idle_closed")
                break
            if len(text) > LIMITS.ws_max_message:
                _ws_reject("ws_max_message")
                await ws.close(code=1009, reason="message too large")
                break
            if LIMITS.ws_message_rate > 0:
                now = time.monotonic()
                if now - window >= 1.0:
                    window, count = now, 0
                count += 1
                if count > LIMITS.ws_message_rate:
                    _ws_reject("ws_message_rate")
                    await ws.close(code=1008, reason="message rate exceeded")
                    break
            s.touched = time.time()
            msg = json.loads(text)
            if msg.get("type") == "view":
                c.level = int(max(0, min(3, msg.get("level", 0))))
                clusters = msg.get("clusters")
                if clusters is not None and s.engine.state.n >= STREAM_FILTER_MIN:
                    mask = np.isin(s.h.labels[3], np.asarray(clusters, dtype=np.int32))
                    c.node_filter = mask
                else:
                    c.node_filter = None
            elif msg.get("type") == "ping":
                _send(s, c, None, {"type": "pong", "t": msg.get("t")})
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        CLIENTS.get(sid, set()).discard(c)
        if c.writer is not None:
            c.writer.cancel()
        s.streaming = bool(CLIENTS.get(sid))
        if listener in s.listeners:
            s.listeners.remove(listener)
        METRICS.inc("ws_closed")


# ---------------------------------------------------------------------------------------------- static frontend
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> Response:
        if path == "api" or path.startswith(("api/", "ws/")):  # unknown API routes are not the app
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        f = STATIC_DIR / path
        if path and f.is_file() and STATIC_DIR in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(STATIC_DIR / "index.html")
