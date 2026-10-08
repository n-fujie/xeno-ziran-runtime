"""Transport-independent session operations, shared by the HTTP service (app.py, desktop / server) and the native
bridge (xzr/native/bridge.py, the iOS app). No HTTP, cookies, FastAPI or WebSocket types: inputs are plain values,
results are dicts / bytes / text, failures are ``OpError(status, body)`` that each transport renders its own way.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from ..lod.layouts import LAYOUTS
from ..lod.tiles import GridIndex, cluster_summary, edges_for, encode_tile
from ..runtime.flags import MINIMAL, Flags
from ..scenario.io import edges_csv, events_csv, load_sample, metrics_csv, nodes_csv
from ..scenario.model import Scenario
from .protocol import encode_aggregates, encode_deltas, encode_snapshot
from .session import CommandError, Session


class OpError(Exception):
    """A request that cannot be served: ``status`` follows HTTP semantics, ``body`` is the JSON-able detail."""

    def __init__(self, status: int, body: Any):
        super().__init__(str(body))
        self.status = status
        self.body = body


def scenario_from(sample: str | None, scenario: dict | None, seed: int | None) -> Scenario:
    try:
        if sample:
            sc = load_sample(sample)
        elif scenario:
            sc = Scenario.model_validate(scenario)
        else:
            raise OpError(400, "give 'sample' or 'scenario'")
        if seed is not None:
            sc = sc.model_copy(update={"seed": seed})
        return sc
    except KeyError as e:
        raise OpError(404, f"no scenario {sample}") from e
    except ValueError as e:  # pydantic.ValidationError and the stand-in's ValidationError are ValueErrors
        raise OpError(422, json.loads(e.json()) if hasattr(e, "json") else str(e)) from e


def runtime_flags(flags: str | dict | None) -> Flags | None:
    if isinstance(flags, str) and flags not in ("full", "minimal"):
        raise OpError(422, "flags must be 'full', 'minimal' or an object")
    try:
        return (MINIMAL if flags == "minimal" else None if flags in (None, "full")
                else Flags.from_dict(flags) if isinstance(flags, dict) else None)
    except (TypeError, ValueError) as e:
        raise OpError(422, f"invalid runtime flags: {e}") from e


def hierarchy(s: Session) -> dict:
    return s.h.to_json()


def clusters(s: Session, level: int) -> dict:
    if not 0 <= level <= 3:
        raise OpError(422, "level must be between 0 and 3")
    with s.lock:
        return cluster_summary(s.h, level, s.world.positions, s.engine.state) | {"layout_version": s.layout_version}


_GRIDS: dict[tuple[str, str, int], GridIndex] = {}


def drop_caches(sid: str) -> None:
    for k in [k for k in _GRIDS if k[0] == sid]:
        _GRIDS.pop(k, None)


def tile(s: Session, layout: str = "network", x0: float = 0, y0: float = 0, x1: float = 1000, y1: float = 1000,
         level: int = 4, max_nodes: int = 20000, max_edges: int = 20000) -> tuple[bytes, int]:
    """Binary LOD tile and the layout version it was cut from."""
    if layout not in LAYOUTS:
        raise OpError(400, f"layout must be one of {LAYOUTS}")
    if level not in (4, 5):
        raise OpError(422, "level must be 4 or 5")
    with s.lock:
        xy = s.world.positions[layout]
        key = (s.id, layout, s.layout_version if layout == "shape" else 0)
        grid = _GRIDS.get(key)
        if grid is None or grid.xy is not xy:
            grid = GridIndex(xy)
            _GRIDS[key] = grid
        nodes = grid.query(x0, y0, x1, y1)
        if len(nodes) > max_nodes:
            nodes = nodes[np.argsort(-s.detector.ign_rate[nodes], kind="stable")[:max_nodes]]
        edges, truncated = edges_for(s.engine.state, nodes, max_edges, both_ends=(level == 4))
        return encode_tile(s.engine.state, xy, nodes, edges, truncated), s.layout_version


def snapshot(s: Session) -> bytes:
    with s.lock:
        return encode_snapshot(s.engine)


def node(s: Session, i: int) -> dict:
    try:
        return s.node(i)
    except KeyError as e:
        raise OpError(404, f"no configuration {i}") from e


def command(s: Session, text: str, auto_compare: bool = True, horizon: int = 150) -> dict:
    try:
        return s.command(text, auto_compare, horizon)
    except CommandError as e:
        raise OpError(400, {"error": str(e), "suggestions": e.suggestions}) from e


def compare_result(s: Session, cid: str) -> dict:
    if cid not in s.compares:
        raise OpError(404, f"no comparison {cid}")
    return s.compares[cid]


EXPORTS = {"nodes", "edges", "events", "metrics", "scenario"}


def export(s: Session, what: str, format: str) -> tuple[Any, str]:  # noqa: A002
    """(body, media type): a JSON-able value for application/json, text for text/csv."""
    with s.lock:
        st = s.engine.state
        if what == "scenario":
            return s.save(), "application/json"
        if what == "metrics":
            m = s.metrics()
            return (m, "application/json") if format == "json" else (metrics_csv(m["t"], m["series"]), "text/csv")
        if what == "events":
            ds = list(s.ring)
            return ([d.to_json() for d in ds], "application/json") if format == "json" else (events_csv(ds), "text/csv")
        if what == "nodes":
            return nodes_csv(st, [s.h.node_address(i) for i in range(st.n)]), "text/csv"
        if what == "edges":
            return edges_csv(st), "text/csv"
    raise OpError(400, "what ∈ {nodes, edges, events, metrics, scenario}")


class StreamCursor:
    """The stream a WebSocket client receives (see app.py ``_broadcast``), produced on demand for one reader:
    a snapshot on (re)synchronisation, binary delta and aggregate frames for new steps, and a metrics message."""

    def __init__(self, s: Session):
        self.s = s
        self.level = 0
        self.node_filter: np.ndarray | None = None
        self.last_layout = s.layout_version
        self.last_graph: Any = None
        self.frames = 0
        self.bytes = 0

    def hello(self) -> list[tuple[bytes | None, dict | None]]:
        return [(None, {"type": "hello", **self.s.info()}), (snapshot(self.s), None)]

    def view(self, level: int, clusters: list[int] | None, filter_min: int) -> None:
        self.level = int(max(0, min(3, level)))
        if clusters is not None and self.s.engine.state.n >= filter_min:
            self.node_filter = np.isin(self.s.h.labels[3], np.asarray(clusters, dtype=np.int32))
        else:
            self.node_filter = None

    def poll(self) -> list[tuple[bytes | None, dict | None]]:
        s = self.s
        out: list[tuple[bytes | None, dict | None]] = []
        steps, resync = s.take_outbox()
        if resync:
            out.append((snapshot(s), {"type": "resync", **s.status()}))
        if steps:
            out.append((encode_deltas(steps, self.node_filter), None))
            with s.lock:
                out.append((encode_aggregates(self.level, s.h.labels[self.level], s.h.n_clusters(self.level), steps,
                                              s.engine.state.diff, s.engine.state.t), None))
        with s.lock:
            meta = {"type": "metrics", "step": s.latest, **s.status()}
            if s.graph_latest is not self.last_graph:
                meta["graph"] = self.last_graph = s.graph_latest
            if s.layout_version != self.last_layout:
                self.last_layout = s.layout_version
                meta["layout_changed"] = "shape"
        for data, _ in out:
            if data is not None:
                self.frames += 1
                self.bytes += len(data)
        meta["stream"] = {"frames": self.frames, "bytes": self.bytes, "resyncs": 0}
        out.append((None, meta))
        return out


def _jsonable(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_jsonable(v) for v in x]
    if isinstance(x, str | int | float | bool) or x is None:
        return x
    return str(x)
