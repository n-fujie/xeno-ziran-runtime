"""Study API: protocols, runs, analysis, reports, packages, replay and reproduction (xzr.study) over HTTP.

Local runtime only: studies cost CPU and write records, so on a public deployment (XZR_PUBLIC=1) every route answers 403, and
a request made from another site's page is refused. Experiment ids and file names are matched against fixed patterns before
any path is built.
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from ..study import analysis, report, runner, templates
from ..study import protocol as P
from .limits import LIMITS

router = APIRouter(prefix="/api/studies")
ID = re.compile(r"S\d{8}-[0-9a-f]{8}-[0-9a-f]{4}")
FILE = re.compile(r"[A-Za-z0-9_\-.]{1,120}")
MAX_ACTIVE = int(os.environ.get("XZR_STUDY_MAX_ACTIVE", "1"))
MAX_PROCS = max(1, min(int(os.environ.get("XZR_STUDY_MAX_PROCS", "4")), os.cpu_count() or 1))
MAX_PROTOCOL_BYTES = 512 * 1024
ACTIVE: dict[str, threading.Thread] = {}
_LOCK = threading.Lock()


def _root() -> Path:
    return Path(os.environ.get("XZR_STUDY_ROOT", runner.DEFAULT_ROOT))


def _same_origin(headers: dict[str, str]) -> bool:
    origin = headers.get("origin")
    if LIMITS.allowed_origins:
        return origin is None or origin.rstrip("/").lower() in LIMITS.allowed_origins
    return origin is None or origin.split("://", 1)[-1] == headers.get("host", "")


def local_only(request: Request) -> None:
    if LIMITS.public:
        raise HTTPException(403, "studies are available on a local runtime only")
    if not _same_origin({k.lower(): v for k, v in request.headers.items()}):
        raise HTTPException(403, "cross-origin request refused")


def _study(sid: str) -> runner.Study:
    if not ID.fullmatch(sid) or not (_root() / sid / "protocol.json").is_file():
        raise HTTPException(404, "no such study")
    return runner.Study(_root() / sid)


def _running(sid: str) -> bool:
    t = ACTIVE.get(sid)
    return bool(t and t.is_alive())


def _start(sid: str, fn, *args) -> None:
    with _LOCK:
        live = [k for k in list(ACTIVE) if _running(k)]
        if sid in live:
            raise HTTPException(409, "this study is already running")
        if len(live) >= MAX_ACTIVE:
            raise HTTPException(429, f"at most {MAX_ACTIVE} study(ies) may run at once (XZR_STUDY_MAX_ACTIVE)")
        t = threading.Thread(target=fn, args=args, daemon=True, name=f"study-{sid}")
        ACTIVE[sid] = t
        t.start()


def _summary(st: runner.Study) -> dict:
    m = st.manifest()
    p = st.protocol()
    return {
        "id": st.id,
        "title": p["title"],
        "mode": p["mode"],
        "created": m["created"],
        "status": st.status(),
        "running": _running(st.id),
        "protocol_digest": m["protocol_digest"],
        "n_runs": m["n_runs"],
        "reproduces": m.get("reproduces"),
        "not_evidence": m.get("not_evidence", False),
        "environment": p["environment"]["kind"],
    }


# ------------------------------------------------------------------------------------------------------ models
class ProtocolIn(BaseModel):
    protocol: dict[str, Any]


class RunIn(BaseModel):
    procs: int = Field(1, ge=1, le=64)
    retry_failed: bool = True


class AmendIn(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    value: Any
    reason: str = Field(min_length=1, max_length=2000)


class ReproIn(BaseModel):
    procs: int = Field(1, ge=1, le=64)


def _check_body(doc: dict) -> None:
    if len(json.dumps(doc)) > MAX_PROTOCOL_BYTES:
        raise HTTPException(413, "protocol too large")


# ------------------------------------------------------------------------------------------------------ routes
@router.get("/templates")
def get_templates(request: Request) -> dict:
    local_only(request)
    return {name: templates.template(name) for name in templates.TEMPLATES}


@router.post("/validate")
def validate(body: ProtocolIn, request: Request) -> dict:
    local_only(request)
    _check_body(body.protocol)
    doc = body.protocol
    issues = P.validate(doc)
    out: dict[str, Any] = {"valid": not issues, "issues": issues, "digest": P.digest(doc)}
    if not issues:
        try:
            out.update(
                fairness=P.fairness(doc),
                fairness_issues=P.fairness_issues(doc),
                runs=P.n_runs(doc),
                step_runs=P.step_runs(doc),
                high_cost=P.step_runs(doc) > P.HIGH_COST_STEP_RUNS,
            )
        except (KeyError, ValueError, TypeError) as e:
            out.update(valid=False, issues=[f"fairness: {e}"])
    return out


@router.post("")
def create(body: ProtocolIn, request: Request) -> dict:
    local_only(request)
    _check_body(body.protocol)
    try:
        st = runner.Study.create(body.protocol, _root())
    except P.ProtocolInvalid as e:
        raise HTTPException(422, {"issues": e.issues}) from e
    return _summary(st)


@router.get("")
def list_studies(request: Request) -> list[dict]:
    local_only(request)
    out = []
    for d in sorted(_root().glob("S*-*-*"), reverse=True) if _root().is_dir() else []:
        if ID.fullmatch(d.name) and (d / "protocol.json").is_file():
            try:
                out.append(_summary(runner.Study(d)))
            except (OSError, ValueError, KeyError):
                continue
    return out


@router.get("/{sid}")
def get_study(sid: str, request: Request) -> dict:
    local_only(request)
    st = _study(sid)
    return {
        **_summary(st),
        "protocol": st.protocol(),
        "registered_digest": P.digest(st.registered()),
        "manifest": st.manifest(),
        "amendments": st.amendments(),
        "fairness": P.fairness(st.protocol()),
        "has_analysis": (st.path / "analysis.json").exists(),
        "has_report": (st.path / "report").is_dir(),
        "has_package": st.path.with_suffix(".zip").exists(),
    }


@router.get("/{sid}/status")
def status(sid: str, request: Request) -> dict:
    local_only(request)
    st = _study(sid)
    return {**st.status(), "running": _running(sid), "runs_on_disk": len(st.run_files())}


@router.get("/{sid}/log")
def log(sid: str, request: Request, limit: int = 200) -> list[dict]:
    local_only(request)
    return _study(sid).log_lines(max(1, min(limit, 2000)))


@router.post("/{sid}/run")
def run(sid: str, body: RunIn, request: Request) -> dict:
    local_only(request)
    st = _study(sid)
    procs = min(body.procs, MAX_PROCS)
    _start(sid, lambda: st.execute(procs=procs, retry_failed=body.retry_failed))
    return {**st.status(), "running": True, "procs": procs}


@router.post("/{sid}/stop")
def stop(sid: str, request: Request) -> dict:
    local_only(request)
    st = _study(sid)
    st.stop()
    return {**st.status(), "running": _running(sid), "stop_requested": True}


@router.post("/{sid}/amend")
def amend(sid: str, body: AmendIn, request: Request) -> dict:
    local_only(request)
    st = _study(sid)
    if _running(sid):
        raise HTTPException(409, "stop the study before amending its protocol")
    try:
        return st.amend(body.path, body.value, body.reason)
    except P.ProtocolInvalid as e:
        raise HTTPException(422, {"issues": e.issues}) from e
    except (KeyError, IndexError, ValueError) as e:
        raise HTTPException(422, {"issues": [f"cannot amend {body.path!r}: {e}"]}) from e


def _run_view(r: dict) -> dict:
    m = r.get("metrics") or {}
    return {
        "arm": r["arm"],
        "index": r.get("index"),
        "gen": r["gen"],
        "seed": r["seed"],
        "status": r["status"],
        "error": r.get("error"),
        "wall_s": r.get("wall_s"),
        "peak_rss_mb": r.get("peak_rss_mb"),
        "metrics": {
            k: m.get(k)
            for k in ("fired_samples", "ignitions", "unobservable_samples", "field_ignitions", "revisions", "reinsertions")
        },
        "controller_changes": len(r.get("controller_changes") or []),
        "protocol_changes": len(r.get("protocol_changes") or []),
    }


@router.get("/{sid}/runs")
def runs(sid: str, request: Request) -> list[dict]:
    local_only(request)
    return [_run_view(r) for r in _study(sid).runs()]


@router.get("/{sid}/runs/{arm}/{k}")
def one_run(sid: str, arm: str, k: int, request: Request) -> dict:
    local_only(request)
    st = _study(sid)
    if arm not in {a["name"] for a in st.protocol()["arms"]}:
        raise HTTPException(404, "no such run")
    p = st._run_path(arm, k)
    if not p.is_file():
        raise HTTPException(404, "no such run")
    return json.loads(p.read_text())


@router.post("/{sid}/runs/{arm}/{k}/replay")
def replay(sid: str, arm: str, k: int, request: Request) -> dict:
    local_only(request)
    st = _study(sid)
    if arm not in {a["name"] for a in st.protocol()["arms"]} or not st._run_path(arm, k).is_file():
        raise HTTPException(404, "no such run")
    return runner.replay_run(st, arm, k)


@router.post("/{sid}/analyse")
def analyse(sid: str, request: Request) -> dict:
    local_only(request)
    st = _study(sid)
    if not st.run_files():
        raise HTTPException(409, "no runs to analyse")
    return analysis.analyse(st)


@router.get("/{sid}/analysis")
def get_analysis(sid: str, request: Request) -> Any:
    local_only(request)
    p = _study(sid).path / "analysis.json"
    if not p.is_file():
        raise HTTPException(404, "not analysed yet")
    return JSONResponse(json.loads(p.read_text()))


@router.post("/{sid}/report")
def build_report(sid: str, request: Request) -> dict:
    local_only(request)
    st = _study(sid)
    if not st.run_files():
        raise HTTPException(409, "no runs to report")
    return report.build(st, analysis.analyse(st))


@router.get("/{sid}/report/{name}")
def report_file(sid: str, name: str, request: Request) -> FileResponse:
    local_only(request)
    st = _study(sid)
    p = st.path / "report" / name
    if not FILE.fullmatch(name) or not p.is_file():
        raise HTTPException(404, "no such report file")
    media = {
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".csv": "text/csv",
        ".md": "text/markdown",
        ".json": "application/json",
    }
    return FileResponse(p, media_type=media.get(p.suffix, "text/plain"))


@router.post("/{sid}/package")
def package(sid: str, request: Request) -> dict:
    local_only(request)
    st = _study(sid)
    if _running(sid):
        raise HTTPException(409, "stop the study before packaging it")
    if not (st.path / "report").is_dir():
        report.build(st, analysis.analyse(st))
    z = report.package(st)
    return {"zip": z.name, "bytes": z.stat().st_size, "verify": report.verify(st.path)}


@router.get("/{sid}/package.zip")
def package_zip(sid: str, request: Request) -> FileResponse:
    local_only(request)
    z = _study(sid).path.with_suffix(".zip")
    if not z.is_file():
        raise HTTPException(404, "no package yet")
    return FileResponse(z, media_type="application/zip", filename=z.name)


@router.get("/{sid}/verify")
def verify(sid: str, request: Request) -> dict:
    local_only(request)
    st = _study(sid)
    if not (st.path / "checksums.json").is_file():
        raise HTTPException(404, "not packaged yet")
    return report.verify(st.path)


@router.post("/{sid}/reproduce")
def reproduce(sid: str, body: ReproIn, request: Request) -> dict:
    local_only(request)
    src = _study(sid)
    procs = min(body.procs, MAX_PROCS)
    doc = (
        {k: v for k, v in src.registered().items() if k != "freeze"}
        if src.registered()["mode"] != "confirmatory"
        else src.registered()
    )
    new = runner.Study.create(doc, _root(), reproduces=src.id)

    def go() -> None:
        new.execute(procs=procs)
        cmp = runner.compare_runs(src, new)
        runner._write(new.path / "reproduction.json", {"of": src.id, **cmp})

    _start(new.id, go)
    return _summary(new)


@router.get("/{sid}/reproduction")
def reproduction(sid: str, request: Request) -> Any:
    local_only(request)
    p = _study(sid).path / "reproduction.json"
    if not p.is_file():
        raise HTTPException(404, "not a finished reproduction")
    return JSONResponse(json.loads(p.read_text()))
