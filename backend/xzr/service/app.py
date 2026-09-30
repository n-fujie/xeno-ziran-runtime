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
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from .. import __version__
from ..lod.layouts import LAYOUTS
from ..lod.tiles import GridIndex, cluster_summary, edges_for, encode_tile
from ..runtime.flags import MINIMAL, Flags
from ..scenario.io import edges_csv, events_csv, list_samples, load_sample, metrics_csv, nodes_csv
from ..scenario.model import Scenario
from .protocol import encode_aggregates, encode_deltas, encode_snapshot
from .session import JOBS, CommandError, Session

FRAME_HZ = float(os.environ.get("XZR_FRAME_HZ", "30"))
MAX_SESSIONS = int(os.environ.get("XZR_MAX_SESSIONS", "4"))
STREAM_FILTER_MIN = int(os.environ.get("XZR_STREAM_FILTER_MIN", "50000"))
STATIC_DIR = Path(os.environ.get("XZR_STATIC", Path(__file__).resolve().parents[3] / "frontend" / "dist"))

SESSIONS: dict[str, Session] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    for s in list(SESSIONS.values()):
        s.close()


app = FastAPI(title="Xeno / Ziran Philosophical Runtime", version=__version__, lifespan=lifespan)


def get(sid: str) -> Session:
    s = SESSIONS.get(sid)
    if s is None:
        raise HTTPException(404, f"no session {sid}")
    s.touched = time.time()
    return s


# ---------------------------------------------------------------------------------------------- basics
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": __version__, "sessions": len(SESSIONS)}


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
async def create_session(req: CreateSession) -> dict:
    try:
        if req.sample:
            sc = load_sample(req.sample)
        elif req.scenario:
            sc = Scenario.model_validate(req.scenario)
        else:
            raise HTTPException(400, "give 'sample' or 'scenario'")
        if req.seed is not None:
            sc = sc.model_copy(update={"seed": req.seed})
    except KeyError as e:
        raise HTTPException(404, f"no scenario {req.sample}") from e
    except ValidationError as e:
        raise HTTPException(422, json.loads(e.json())) from e
    if len(SESSIONS) >= MAX_SESSIONS:
        oldest = min(SESSIONS.values(), key=lambda s: s.touched)
        oldest.close()
        SESSIONS.pop(oldest.id, None)
    try:
        flags = (MINIMAL if req.flags == "minimal" else None if req.flags in (None, "full")
                 else Flags.from_dict(req.flags) if isinstance(req.flags, dict) else None)
    except (TypeError, ValueError) as e:
        raise HTTPException(422, f"invalid runtime flags: {e}") from e
    if isinstance(req.flags, str) and req.flags not in ("full", "minimal"):
        raise HTTPException(422, "flags must be 'full', 'minimal' or an object")
    s = await asyncio.to_thread(Session, sc, req.applied, 10, flags)
    SESSIONS[s.id] = s
    return s.info()


@app.get("/api/sessions")
def sessions() -> list[dict]:
    return [{"id": s.id, "scenario": s.scenario.name, "t": s.engine.state.t, "running": s.running}
            for s in SESSIONS.values()]


@app.get("/api/sessions/{sid}")
def session_info(sid: str) -> dict:
    return get(sid).info()


@app.delete("/api/sessions/{sid}")
def delete_session(sid: str) -> dict:
    s = get(sid)
    s.close()
    SESSIONS.pop(sid, None)
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
    return get(sid).h.to_json()


@app.get("/api/sessions/{sid}/clusters")
def clusters(sid: str, level: int = Query(0, ge=0, le=3)) -> dict:
    s = get(sid)
    with s.lock:
        return cluster_summary(s.h, level, s.world.positions, s.engine.state) | {"layout_version": s.layout_version}


_GRID_CACHE: dict[tuple[str, str, int], GridIndex] = {}


@app.get("/api/sessions/{sid}/tile")
def tile(sid: str, layout: str = "network", x0: float = 0, y0: float = 0, x1: float = 1000, y1: float = 1000,
         level: int = Query(4, ge=4, le=5), max_nodes: int = 20000, max_edges: int = 20000) -> Response:
    if layout not in LAYOUTS:
        raise HTTPException(400, f"layout must be one of {LAYOUTS}")
    s = get(sid)
    with s.lock:
        xy = s.world.positions[layout]
        key = (sid, layout, s.layout_version if layout == "shape" else 0)
        grid = _GRID_CACHE.get(key)
        if grid is None or grid.xy is not xy:
            grid = GridIndex(xy)
            _GRID_CACHE[key] = grid
        nodes = grid.query(x0, y0, x1, y1)
        if len(nodes) > max_nodes:
            nodes = nodes[np.argsort(-s.detector.ign_rate[nodes], kind="stable")[:max_nodes]]
        edges, truncated = edges_for(s.engine.state, nodes, max_edges, both_ends=(level == 4))
        body = encode_tile(s.engine.state, xy, nodes, edges, truncated)
    return Response(body, media_type="application/octet-stream",
                    headers={"X-Layout-Version": str(s.layout_version)})


@app.get("/api/sessions/{sid}/snapshot")
def snapshot(sid: str) -> Response:
    s = get(sid)
    with s.lock:
        return Response(encode_snapshot(s.engine), media_type="application/octet-stream")


# ---------------------------------------------------------------------------------------------- inspection
@app.get("/api/sessions/{sid}/node/{i}")
def node(sid: str, i: int) -> dict:
    try:
        return get(sid).node(i)
    except KeyError as e:
        raise HTTPException(404, f"no configuration {i}") from e


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
def practice_command(sid: str, c: Cmd) -> dict | JSONResponse:
    try:
        return get(sid).command(c.text, c.auto_compare, c.horizon)
    except CommandError as e:
        return JSONResponse({"error": str(e), "suggestions": e.suggestions}, status_code=400)


class CompareReq(BaseModel):
    horizon: int = 150


@app.post("/api/sessions/{sid}/compare")
def start_compare(sid: str, r: CompareReq) -> dict:
    return {"job": get(sid).start_compare(r.horizon)}


@app.get("/api/sessions/{sid}/compare/{cid}")
def get_compare(sid: str, cid: str) -> dict:
    s = get(sid)
    if cid not in s.compares:
        raise HTTPException(404, f"no comparison {cid}")
    return s.compares[cid]


@app.get("/api/jobs/{jid}")
def job(jid: str) -> dict:
    if jid not in JOBS:
        raise HTTPException(404, f"no job {jid}")
    return {k: v for k, v in JOBS[jid].items()}


# ---------------------------------------------------------------------------------------------- persistence
@app.get("/api/sessions/{sid}/save")
def save(sid: str) -> dict:
    return get(sid).save()


@app.get("/api/sessions/{sid}/export")
def export(sid: str, what: str = "nodes", format: str = "csv") -> Response:  # noqa: A002
    s = get(sid)
    with s.lock:
        st = s.engine.state
        if what == "scenario":
            return JSONResponse(s.save())
        if what == "metrics":
            m = s.metrics()
            if format == "json":
                return JSONResponse(m)
            return PlainTextResponse(metrics_csv(m["t"], m["series"]), media_type="text/csv")
        if what == "events":
            ds = list(s.ring)
            if format == "json":
                return JSONResponse([d.to_json() for d in ds])
            return PlainTextResponse(events_csv(ds), media_type="text/csv")
        if what == "nodes":
            addrs = [s.h.node_address(i) for i in range(st.n)]
            return PlainTextResponse(nodes_csv(st, addrs), media_type="text/csv")
        if what == "edges":
            return PlainTextResponse(edges_csv(st), media_type="text/csv")
    raise HTTPException(400, "what ∈ {nodes, edges, events, metrics, scenario}")


# ---------------------------------------------------------------------------------------------- experiments
EXP_DIR = Path(__file__).resolve().parents[2] / "experiments" / "results"


@app.get("/api/experiments")
def experiments() -> list[dict]:
    return [{"name": p.stem, "bytes": p.stat().st_size, "modified": p.stat().st_mtime}
            for p in sorted(EXP_DIR.glob("*.json"))]


@app.get("/api/experiments/primitives")
def experiment_primitives() -> list[dict]:
    from ..experiments.catalog import primitives
    return primitives()


@app.get("/api/experiments/{name}")
def experiment(name: str) -> Response:
    if not re.fullmatch(r"[a-z0-9_\-]+", name) or not (EXP_DIR / f"{name}.json").is_file():
        raise HTTPException(404, f"no experiment result {name}")
    return FileResponse(EXP_DIR / f"{name}.json", media_type="application/json")


# ---------------------------------------------------------------------------------------------- websocket
class Client:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.level = 0
        self.node_filter: np.ndarray | None = None
        self.bytes = 0
        self.frames = 0


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
        if resync:
            snap = await asyncio.to_thread(lambda: encode_snapshot_locked(s))
            for c in clients:
                await _send(s, c, snap, {"type": "resync", **s.status()})
        if steps:
            frames: dict[int, bytes] = {}
            for c in clients:
                key = id(c.node_filter) if c.node_filter is not None else 0
                if key not in frames:
                    frames[key] = await asyncio.to_thread(encode_deltas, steps, c.node_filter)
                with s.lock:
                    agg = encode_aggregates(c.level, s.h.labels[c.level], s.h.n_clusters(c.level), steps,
                                            s.engine.state.diff, s.engine.state.t)
                await _send(s, c, frames[key], None)
                await _send(s, c, agg, None)
        with s.lock:
            meta = {"type": "metrics", "step": s.latest, **s.status()}
            if s.graph_latest is not last_graph:
                meta["graph"] = last_graph = s.graph_latest
            if s.layout_version != last_layout:
                last_layout = s.layout_version
                meta["layout_changed"] = "shape"
        for c in clients:
            meta["stream"] = {"frames": c.frames, "bytes": c.bytes}
            await _send(s, c, None, meta)
    BROADCASTERS.pop(s.id, None)


def encode_snapshot_locked(s: Session) -> bytes:
    with s.lock:
        return encode_snapshot(s.engine)


async def _send(s: Session, c: Client, data: bytes | None, meta: dict | None) -> None:
    try:
        if data is not None:
            await c.ws.send_bytes(data)
            c.bytes += len(data)
            c.frames += 1
        if meta is not None:
            await c.ws.send_text(json.dumps(meta))
    except Exception:  # noqa: BLE001 — a dead socket is removed by its reader
        CLIENTS.get(s.id, set()).discard(c)


@app.websocket("/ws/{sid}")
async def ws_endpoint(ws: WebSocket, sid: str) -> None:
    s = SESSIONS.get(sid)
    await ws.accept()
    if s is None:
        await ws.send_text(json.dumps({"type": "error", "error": f"no session {sid}"}))
        await ws.close()
        return
    c = Client(ws)
    loop = asyncio.get_running_loop()

    def listener(msg: dict) -> None:
        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(_send(s, c, None, msg)))

    s.listeners.append(listener)
    await ws.send_text(json.dumps({"type": "hello", **s.info()}))
    await ws.send_bytes(encode_snapshot_locked(s))
    CLIENTS.setdefault(sid, set()).add(c)
    s.streaming = True
    if sid not in BROADCASTERS:
        BROADCASTERS[sid] = asyncio.create_task(_broadcast(s))
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            if msg.get("type") == "view":
                c.level = int(max(0, min(3, msg.get("level", 0))))
                clusters = msg.get("clusters")
                if clusters is not None and s.engine.state.n >= STREAM_FILTER_MIN:
                    mask = np.isin(s.h.labels[3], np.asarray(clusters, dtype=np.int32))
                    c.node_filter = mask
                else:
                    c.node_filter = None
            elif msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong", "t": msg.get("t")}))
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        CLIENTS.get(sid, set()).discard(c)
        s.streaming = bool(CLIENTS.get(sid))
        if listener in s.listeners:
            s.listeners.remove(listener)


# ---------------------------------------------------------------------------------------------- static frontend
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        f = STATIC_DIR / path
        if path and f.is_file() and STATIC_DIR in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(STATIC_DIR / "index.html")
