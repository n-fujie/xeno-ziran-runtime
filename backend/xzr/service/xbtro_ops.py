"""Transport-independent XenoBody / Total Observation operations, shared by the HTTP service (app.py), the native bridge (iOS app)
and the browser edition (Pyodide, via the same bridge). No HTTP types: inputs are plain values, results are dicts or text, failures
are ``OpError(status, body)``.

A *workspace* holds one researcher's history of experiment records (JSON/CSV exportable, re-runnable, re-enterable), their live
bodies, and nothing else. Experiments run as jobs in the shared job table (``session.JOBS``), so the same limits, pruning and — in
the browser — the same time-sliced cooperative loop apply as for comparison jobs. Long experiments are generators: one slice every
100 simulation steps.

Limits come from the environment (``XZR_XB_*``); an exceeded limit is refused with its name, never silently truncated.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..xbtro import (
    MODEL_VERSION,
    RELEASE,
    experiments,
    history,
    live,
    metrics,
    observation,
    records,
    tro,
    velocity,
    verification,
    xeno14,
    ziran,
)
from ..xbtro import config as xcfg
from . import session as S
from .limits import LIMITS, LimitError
from .operations import OpError


def _n(name: str, local: float, public: float) -> int:
    v = os.environ.get(name)
    return int(v) if v not in (None, "") else int(public if LIMITS.public else local)


@dataclass(frozen=True)
class XbLimits:
    max_seeds: int  # XZR_XB_MAX_SEEDS: seeds per experiment
    max_records: int  # XZR_XB_MAX_RECORDS: records per workspace
    max_bodies: int  # XZR_XB_MAX_BODIES: live bodies per workspace
    max_body_seeds: int  # XZR_XB_MAX_BODY_SEEDS: seeds per live body
    max_step: int  # XZR_XB_MAX_STEP: simulation steps per step request
    max_horizon_s: int  # XZR_XB_MAX_HORIZON_S: horizon of a live body
    max_workspaces: int  # XZR_XB_MAX_WORKSPACES: per process
    max_trials: int  # XZR_XB_MAX_TRIALS: adaptation trials (Experiment D)
    max_body_cells: int  # XZR_XB_MAX_BODY_CELLS: seeds x simulation steps of one live body (memory is proportional to it)
    max_obs_models: int  # XZR_XB_MAX_OBS_MODELS: observation models in one configuration
    experiments: tuple[str, ...]  # XZR_XB_EXPERIMENTS: comma-separated ids that may be started


def load_xb_limits() -> XbLimits:
    allowed = os.environ.get("XZR_XB_EXPERIMENTS")
    ids = tuple(x.strip() for x in allowed.split(",") if x.strip()) if allowed else tuple(experiments.EXPERIMENTS)
    return XbLimits(
        _n("XZR_XB_MAX_SEEDS", 32, 16),
        _n("XZR_XB_MAX_RECORDS", 80, 20),
        _n("XZR_XB_MAX_BODIES", 6, 2),
        _n("XZR_XB_MAX_BODY_SEEDS", 8, 3),
        _n("XZR_XB_MAX_STEP", 60, 30),
        _n("XZR_XB_MAX_HORIZON_S", 60, 30),
        _n("XZR_XB_MAX_WORKSPACES", 16, 64),
        _n("XZR_XB_MAX_TRIALS", 8, 6),
        _n("XZR_XB_MAX_BODY_CELLS", 600_000, 90_000),
        _n("XZR_XB_MAX_OBS_MODELS", 16, 12),
        ids,
    )


XB = load_xb_limits()


def enabled() -> bool:
    """The research environment's routes. On by default for the local runtime, the iOS app and the browser edition (which run it on the
    user's own machine); OFF by default on a public server (XZR_PUBLIC=1), whose compute budget is not for running experiments —
    the public site offers the browser edition instead. ``XZR_XBTRO=1`` / ``0`` overrides either default."""
    v = os.environ.get("XZR_XBTRO")
    return (v == "1") if v not in (None, "") else (not LIMITS.public)


SLOW_FIELDS = ("fatigue", "energy", "kc", "sediment", "core", "hand")
# parameters each experiment accepts (anything else is refused)
PARAMS: dict[str, set[str]] = {
    "A": {"n_seeds", "seed", "preset", "rounds", "alteration", "carry_over"},
    "E": {"n_seeds", "seed", "preset", "rounds", "alteration", "carry_over"},
    "B": {"n_seeds", "seed", "preset", "carry_over"},
    "C": {"n_seeds", "seed", "preset", "principles", "combos", "carry_over"},
    "D": {"n_seeds", "seed", "preset", "trials", "carry_over"},
    "F": {"n_seeds", "seed", "t_goal", "t_recover", "carry_over"},
    "G": {"n_seeds", "seed", "preset", "principles", "ablate", "carry_over"},
    "M": {"n_seeds", "seed", "preset", "rounds", "alteration", "carry_over"},
    "R": {"n_seeds", "preset", "principles"},
    "S": {"n_seeds", "seed", "preset", "push_force"},
    "V": {"n_seeds"},
}


@dataclass
class Workspace:
    id: str
    owner: str | None
    created: float = field(default_factory=time.time)
    touched: float = field(default_factory=time.time)
    history: records.HistoryStore = field(default_factory=records.HistoryStore)
    bodies: dict[str, tuple[live.BodySession, threading.RLock]] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)


WORKSPACES: dict[str, Workspace] = {}
_LOCK = threading.RLock()


# ------------------------------------------------------------------------------------------------ catalog
def catalog() -> dict[str, Any]:
    presets = []
    for pid, fn in xcfg.PRESETS.items():
        c = fn()
        presets.append(
            {
                "id": pid,
                "name": c["name"],
                "family": c["family"],
                "links": len(c["links"]),
                "joints": len(c["joints"]),
                "lines": len(c["lines"]),
                "dt": c["task"]["dt"],
                "tolerance_band_m": metrics.band(c),
            }
        )
    return {
        "release": {
            "name": RELEASE["name"],
            "channel": RELEASE["channel"],
            "platforms": RELEASE["platforms"],
            "statements": [{"topic": t, "text": x} for t, x in RELEASE["statements"]],
            "xeno14_fidelity": {
                f: sum(1 for p in xeno14.PRINCIPLES if p["fidelity"] == f) for f in ("translated", "partial", "proxy-only")
            },
        },
        "model_version": MODEL_VERSION,
        "record_schema": records.SCHEMA,
        "presets": presets,
        "interventions": xcfg.INTERVENTIONS,
        "experiments": [e for e in experiments.catalog() if e["id"] in XB.experiments],
        "xeno14": xeno14.catalog(),
        "xeno14_source": xeno14.SOURCE,
        "observation": {"kinds": observation.KINDS, "presets": observation.PRESET_CONFIGS, "regions": list(observation.REGIONS)},
        "differences": [{k: d[k] for k in ("id", "label", "family", "timescale_s")} for d in tro.catalog()],
        "velocity_measures": velocity.MEASURES,
        "ranges": xcfg.RANGES,
        "organizations": {k: v[1] for k, v in metrics.ORGANIZATION.items()},
        "tolerance": metrics.TOLERANCE,
        "seeds": {
            "exploration": [metrics.EXPLORATION_SEEDS[0], metrics.EXPLORATION_SEEDS[-1]],
            "final_base": metrics.FINAL_SEED_BASE,
        },
        "ziran": ziran.status(),
        "limits": {k: (list(v) if isinstance(v, tuple) else v) for k, v in XB.__dict__.items()},
        "labels": {
            "reference": "model reference state (simulator-internal; not an observation of a real body)",
            "observation": "output of a simulated observation model, stored apart from the reference",
            "estimate": "a model-based estimate computed from observation outputs, or the controller's own belief",
        },
        "scope": "A simplified planar body model with nominal parameters. Not a measurement of, or a claim about, any real human or machine.",
    }


# ------------------------------------------------------------------------------------------------ workspaces
def create_workspace(owner: str | None) -> dict[str, Any]:
    with _LOCK:
        mine = sorted((w for w in WORKSPACES.values() if w.owner == owner), key=lambda w: w.touched)
        if len(WORKSPACES) >= XB.max_workspaces:
            if not mine:
                raise LimitError("max_workspaces", "the runtime's workspaces are all in use; retry later", 503)
            WORKSPACES.pop(mine[0].id, None)
        elif mine and LIMITS.public and len(mine) >= 2:
            WORKSPACES.pop(mine[0].id, None)
        ws = Workspace(uuid.uuid4().hex[:12], owner)
        WORKSPACES[ws.id] = ws
    return {"id": ws.id, "created": ws.created}


def workspace(wid: str, owner: str | None) -> Workspace:
    ws = WORKSPACES.get(wid)
    if ws is None or ws.owner != owner:
        raise OpError(404, "no such workspace")
    ws.touched = time.time()
    return ws


def close_workspace(wid: str, owner: str | None) -> dict[str, Any]:
    ws = workspace(wid, owner)
    with _LOCK:
        WORKSPACES.pop(ws.id, None)
    return {"closed": wid}


# ------------------------------------------------------------------------------------------------ validation
def _int(params: dict, key: str, lo: int, hi: int) -> int:
    v = params[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != int(v) or not lo <= int(v) <= hi:
        raise OpError(422, f"{key} must be an integer within {lo}..{hi}")
    return int(v)


def _num(params: dict, key: str, lo: float, hi: float) -> float:
    v = params[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise OpError(422, f"{key} must be a number within {lo}..{hi}")
    return float(v)


def validate_params(exp: str, params: dict[str, Any] | None) -> dict[str, Any]:
    if exp not in experiments.EXPERIMENTS or exp not in XB.experiments:
        raise OpError(
            404, f"experiment {exp!r} is not available; available: {[e for e in experiments.EXPERIMENTS if e in XB.experiments]}"
        )
    params = dict(params or {})
    unknown = set(params) - PARAMS[exp]
    if unknown:
        raise OpError(422, f"unknown parameter(s) for experiment {exp}: {sorted(unknown)}; accepted: {sorted(PARAMS[exp])}")
    if "n_seeds" in params:
        _int(params, "n_seeds", 4, XB.max_seeds)
    if "seed" in params:
        _int(params, "seed", 0, 10_000_000)
    if "preset" in params and params["preset"] not in xcfg.PRESETS:
        raise OpError(422, f"preset must be one of {sorted(xcfg.PRESETS)}")
    if "rounds" in params:
        _int(params, "rounds", 1, 6)
    if "trials" in params:
        _int(params, "trials", 3, XB.max_trials)
    if "alteration" in params and params["alteration"] not in ("mixed", "delay-only", "tone-only", "fatigue-only"):
        raise OpError(422, "alteration must be one of mixed, delay-only, tone-only, fatigue-only")
    if "principles" in params:
        pr = params["principles"]
        if not isinstance(pr, list) or not pr or len(pr) > 14 or any(p not in xeno14.BY_ID for p in pr):
            raise OpError(422, "principles must be a non-empty list of Xeno-14 principle ids")
    for k in ("combos", "ablate"):
        if k in params and not isinstance(params[k], bool):
            raise OpError(422, f"{k} must be true or false")
    for k, lo, hi in (("t_goal", 0.3, 5.0), ("t_recover", 0.3, 5.0), ("push_force", 5.0, 200.0)):
        if k in params:
            _num(params, k, lo, hi)
    if "carry_over" in params:
        co = params["carry_over"]
        if not isinstance(co, dict) or not set(co) <= set(SLOW_FIELDS):
            raise OpError(422, f"carry_over must be an object with fields from {SLOW_FIELDS}")
        for k, v in co.items():
            if (
                not isinstance(v, list)
                or not 1 <= len(v) <= 64
                or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in v)
            ):
                raise OpError(422, f"carry_over.{k} must be a list of 1..64 finite numbers")
    return params


# ------------------------------------------------------------------------------------------------ jobs (experiments, repeats, re-analysis)
def _public_job(j: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in j.items() if k not in ("created", "cancel", "_producer")}


def _start(
    ws: Workspace,
    label: str,
    producer,
    extra: dict[str, Any],
    parent: str | None = None,
    operation: str | None = None,
    reentry: list[dict] | None = None,
) -> dict[str, Any]:
    if len(ws.history.order) >= XB.max_records:
        raise LimitError("max_records", f"this workspace holds {XB.max_records} records; delete one first", 422)
    if sum(1 for j in S.JOBS.values() if j.get("workspace") == ws.id and j["status"] in ("queued", "running")) >= (
        1 if LIMITS.public else 2
    ):
        raise LimitError(
            "max_active_jobs_per_workspace", "this workspace already has its experiments running; wait for one to finish"
        )
    job = S.register_job("xbtro", ws.id, workspace=ws.id, label=label, progress=0.0, stage="queued", record_id=None, **extra)

    def steps():
        job["status"] = "running"
        try:
            gen = producer()
            while True:
                try:
                    fr = next(gen)
                except StopIteration as st:
                    rec, slow = st.value
                    break
                job["progress"], job["stage"] = round(float(fr["progress"]), 4), fr["stage"]
                if job.get("cancel"):
                    job["status"] = "cancelled"
                    job["finished"] = time.time()
                    S.METRICS.inc("jobs_cancelled")
                    return
                yield
            if parent or operation:
                rec["history"] = {
                    **rec.get("history", {}),
                    "parent": parent,
                    "operation": operation,
                    **({"reentry": reentry} if reentry else {}),
                }
            with ws.lock:
                stored = ws.history.add(rec, slow, parent=parent)
            job.update(status="done", progress=1.0, stage="done", record_id=stored["id"], summary=_summary(stored))
            S.METRICS.inc("jobs_done")
        except (
            experiments.ExperimentError,
            xcfg.ConfigError,
            observation.ObservationError,
            history.HistoryError,
            ValueError,
        ) as e:
            job.update(status="error", error=f"{type(e).__name__}: {e}")
            S.METRICS.inc("jobs_failed")
        except Exception as e:  # noqa: BLE001 — reported to the client
            job.update(status="error", error=f"internal: {type(e).__name__}: {e}")
            S.METRICS.inc("jobs_failed")
        job["finished"] = time.time()
        with S._JOBS_LOCK:
            S.FUTURES.pop(job["id"], None)

    S.schedule_job(job["id"], steps)
    return _public_job(job)


def _summary(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": rec["id"],
        "experiment": rec["experiment"],
        "digest": rec["digest"][:12],
        "negative_results": len(rec.get("negative_results", [])),
        "unobserved_differences": len(rec.get("unobserved_differences", [])),
        "tables": [t["name"] for t in rec["results"].get("tables", [])],
    }


def start_experiment(ws: Workspace, exp: str, params: dict[str, Any] | None) -> dict[str, Any]:
    p = validate_params(exp, params)
    return _start(ws, f"experiment {exp}", lambda: experiments.run(exp, p), {"experiment": exp, "params": p})


def job_view(ws: Workspace, jid: str) -> dict[str, Any]:
    j = S.JOBS.get(jid)
    if j is None or j.get("workspace") != ws.id:
        raise OpError(404, "no such job")
    return _public_job(j)


def cancel(ws: Workspace, jid: str) -> dict[str, Any]:
    j = S.JOBS.get(jid)
    if j is None or j.get("workspace") != ws.id:
        raise OpError(404, "no such job")
    if j["status"] in S.FINISHED:
        return {"cancelled": False, "status": j["status"]}
    j["cancel"] = True
    S.cancel_job(jid)  # a queued job is dropped at once; a running one stops at its next slice
    return {"cancelled": True, "status": j["status"]}


def jobs(ws: Workspace) -> list[dict[str, Any]]:
    return [_public_job(j) for j in list(S.JOBS.values()) if j.get("workspace") == ws.id]


# ------------------------------------------------------------------------------------------------ history
def history_view(ws: Workspace) -> dict[str, Any]:
    with ws.lock:
        return {
            "records": ws.history.listing(),
            "unobserved_registry": ws.history.registry(),
            "limit": XB.max_records,
            "note": "re-observation of a simulation is not re-measurement of a body",
        }


def get_record(ws: Workspace, rid: str) -> dict[str, Any]:
    try:
        return ws.history.get(rid)
    except KeyError as e:
        raise OpError(404, "no such record") from e


def delete_record(ws: Workspace, rid: str) -> dict[str, Any]:
    with ws.lock:
        if rid not in ws.history.records:
            raise OpError(404, "no such record")
        ws.history.records.pop(rid)
        ws.history.order.remove(rid)
        ws.history.slow.pop(rid, None)
        ws.history.log.append({"event": "deleted", "id": rid})
    return {"deleted": rid}


def export_record(ws: Workspace, rid: str, fmt: str) -> tuple[str, str, str]:
    rec = get_record(ws, rid)
    if fmt == "json":
        text, mime = records.to_json(rec), "application/json"
    elif fmt == "csv":
        text, mime = records.to_csv(rec), "text/csv"
    else:
        raise OpError(422, "format must be json or csv")
    if len(text) > LIMITS.max_export_bytes:
        raise LimitError("max_export_bytes", f"the export exceeds {LIMITS.max_export_bytes:,} bytes", 413)
    return text, mime, f"{rec['id']}.{fmt}"


def export_history(ws: Workspace) -> dict[str, Any]:
    with ws.lock:
        return ws.history.export()


def import_record(ws: Workspace, rec: Any) -> dict[str, Any]:
    if not isinstance(rec, dict):
        raise OpError(422, "a record must be an object")
    if len(ws.history.order) >= XB.max_records:
        raise LimitError("max_records", f"this workspace holds {XB.max_records} records; delete one first", 422)
    try:
        with ws.lock:
            return _summary(ws.history.import_record(rec))
    except (ValueError, KeyError) as e:
        raise OpError(422, f"not an XB-TRO record: {e}") from e


def import_history(ws: Workspace, data: Any) -> dict[str, Any]:
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("records"), list)
        or len(data["records"]) + len(ws.history.order) > XB.max_records
    ):
        raise OpError(422, f"a history export with at most {XB.max_records} records in total is expected")
    try:
        with ws.lock:
            return {"imported": ws.history.load(data)}
    except (ValueError, KeyError) as e:
        raise OpError(422, f"not an XB-TRO history: {e}") from e


def rerun(ws: Workspace, rid: str) -> dict[str, Any]:
    rec = get_record(ws, rid)
    exp = rec["rerun"]["experiment"]
    if exp not in experiments.EXPERIMENTS or exp not in XB.experiments:
        raise OpError(
            422, f"record {rid} ({exp}) is a derived record or its experiment is not available here; repeat its parent instead"
        )
    p = validate_params(exp, rec["rerun"]["parameters"])
    return _start(
        ws,
        f"rerun of {rid}",
        lambda: experiments.run(exp, p),
        {"experiment": exp, "params": p, "parent": rid},
        parent=rid,
        operation="rerun",
    )


def reenter(ws: Workspace, rid: str, exp: str, params: dict[str, Any] | None) -> dict[str, Any]:
    with ws.lock:
        try:
            state = history.carried_state(ws.history, rid)
        except history.HistoryError as e:
            raise OpError(404, str(e)) from e
    p = validate_params(exp, {**(params or {}), "carry_over": state}) if "carry_over" in PARAMS.get(exp, set()) else None
    if p is None:
        raise OpError(422, f"experiment {exp} does not take a carried state")
    return _start(
        ws,
        f"{exp} re-entered from {rid}",
        lambda: experiments.run(exp, p),
        {"experiment": exp, "params": {k: v for k, v in p.items() if k != "carry_over"}, "parent": rid},
        parent=rid,
        operation="reenter",
        reentry=[{"from": rid, "kind": "slow-state", "fields": sorted(state)}],
    )


def observation_from(spec: Any, n_links: int = 4) -> dict[str, Any]:
    """An observation configuration from a request: {"name": preset}, {"kinds": [...]}, or {"config": {...}}."""
    if spec is None:
        return observation.validate(observation.config("motion+emg+contact"), n_links)
    if isinstance(spec, str):
        spec = {"name": spec}
    if not isinstance(spec, dict):
        raise OpError(422, "observation must be a preset name or an object")
    try:
        if "config" in spec:
            cfg = spec["config"]
            models = cfg.get("models") if isinstance(cfg, dict) else None
            if isinstance(models, list):
                if len(models) > XB.max_obs_models:
                    raise OpError(422, f"an observation configuration has at most {XB.max_obs_models} models")
                for m in models:
                    if (
                        isinstance(m, dict)
                        and isinstance(m.get("blind_windows", []), list)
                        and len(m.get("blind_windows", [])) > 16
                    ):
                        raise OpError(422, "a model has at most 16 blind windows")
            return observation.validate(cfg, n_links)
        if "kinds" in spec:
            kinds = spec["kinds"]
            if not isinstance(kinds, list) or len(kinds) > XB.max_obs_models or not all(isinstance(k, str) for k in kinds):
                raise OpError(422, f"kinds must be a list of at most {XB.max_obs_models} observation kinds")
            return observation.validate(observation.config(spec.get("name", "custom"), kinds=kinds), n_links)
        name = spec.get("name", "motion+emg+contact")
        if name not in observation.PRESET_CONFIGS:
            raise OpError(422, f"unknown observation preset {name!r}; known: {sorted(observation.PRESET_CONFIGS)}")
        return observation.validate(observation.config(name), n_links)
    except observation.ObservationError as e:
        raise OpError(422, str(e)) from e


def reanalyse(ws: Workspace, rid: str, obs_spec: Any) -> dict[str, Any]:
    rec = get_record(ws, rid)
    obs = observation_from(obs_spec)
    if not (rec.get("results") or {}).get("pair"):
        raise OpError(422, f"record {rid} does not store a pair of body conditions; only A, E and M records can be re-analysed")
    return _start(
        ws,
        f"re-observation of {rid}",
        lambda: history.reanalyse_steps(rec, obs),
        {"experiment": "RE", "params": {"observation": obs["name"]}, "parent": rid},
        parent=rid,
        operation="reanalyse",
    )


# ------------------------------------------------------------------------------------------------ diagnosis
def diagnose(body: dict[str, Any] | None) -> dict[str, Any]:
    body = body or {}
    try:
        preset = body.get("preset", "human-like-planar")
        if preset not in xcfg.PRESETS:
            raise OpError(422, f"preset must be one of {sorted(xcfg.PRESETS)}")
        over = body.get("overrides") or {}
        if not isinstance(over, dict):
            raise OpError(422, "overrides must be an object")
        cfg = xcfg.build(preset, over)
        return verification.diagnose(cfg)
    except xcfg.ConfigError as e:
        raise OpError(422, f"invalid configuration: {e}") from e


# ------------------------------------------------------------------------------------------------ live bodies
def create_body(ws: Workspace, body: dict[str, Any] | None) -> dict[str, Any]:
    body = body or {}
    with ws.lock:
        if len(ws.bodies) >= XB.max_bodies:
            raise LimitError("max_bodies", f"this workspace already has {XB.max_bodies} live bodies; close one first", 422)
    n = int(body.get("n_seeds", 1))
    if not 1 <= n <= XB.max_body_seeds:
        raise OpError(422, f"n_seeds must be within 1..{XB.max_body_seeds}")
    horizon = float(body.get("horizon_s", 30.0))
    if not 1.0 <= horizon <= XB.max_horizon_s:
        raise OpError(422, f"horizon_s must be within 1..{XB.max_horizon_s}")
    preset = body.get("preset", "human-like-planar")
    if preset not in xcfg.PRESETS:
        raise OpError(422, f"preset must be one of {sorted(xcfg.PRESETS)}")
    over = body.get("overrides") or {}
    if not isinstance(over, dict):
        raise OpError(422, "overrides must be an object")
    task = over.get("task") if isinstance(over.get("task"), dict) else {}
    dt = task.get("dt", xcfg.PRESETS[preset]()["task"]["dt"])
    if isinstance(dt, bool) or not isinstance(dt, (int, float)) or not 0.002 <= dt <= 0.02:
        raise OpError(422, "task.dt must be a number within 0.002..0.02")
    cells = n * math.ceil(horizon / dt)
    if cells > XB.max_body_cells:
        raise LimitError(
            "max_body_cells",
            f"seeds x steps = {cells:,} exceeds this runtime's {XB.max_body_cells:,}; use fewer seeds, a shorter horizon or a larger time step",
            422,
        )
    try:
        obs = observation_from(body.get("observation"), len(xcfg.PRESETS[preset]()["links"]))
        ids = body.get("xeno14") or []
        if not isinstance(ids, list) or any(i not in xeno14.BY_ID for i in ids):
            raise OpError(422, "xeno14 must be a list of Xeno-14 principle ids")
        b = live.BodySession(
            preset, body.get("overrides") or {}, [int(body.get("seed", 1)) + i for i in range(n)], obs, horizon, ids
        )
    except (xcfg.ConfigError, observation.ObservationError) as e:
        raise OpError(422, str(e)) from e
    bid = uuid.uuid4().hex[:10]
    with ws.lock:
        ws.bodies[bid] = (b, threading.RLock())
    return {"id": bid, **b.info()}


def _body(ws: Workspace, bid: str) -> tuple[live.BodySession, threading.RLock]:
    x = ws.bodies.get(bid)
    if x is None:
        raise OpError(404, "no such body")
    return x


def body_info(ws: Workspace, bid: str) -> dict[str, Any]:
    b, lk = _body(ws, bid)
    with lk:
        return {"id": bid, **b.snapshot()}


def body_step(ws: Workspace, bid: str, n: int) -> dict[str, Any]:
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= XB.max_step:
        raise OpError(422, f"n must be an integer within 1..{XB.max_step}")
    b, lk = _body(ws, bid)
    with lk:
        try:
            return b.step(n)
        except xcfg.ConfigError as e:
            raise OpError(422, str(e)) from e


def body_apply(ws: Workspace, bid: str, cmd: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(cmd, dict) or "type" not in cmd:
        raise OpError(422, "a command is an object with a 'type': intervention, line, xeno14 or observation")
    b, lk = _body(ws, bid)
    with lk:
        try:
            t = cmd["type"]
            if t == "intervention":
                m = cmd.get("magnitude")
                if m is not None and (isinstance(m, bool) or not isinstance(m, (int, float)) or not math.isfinite(m)):
                    raise OpError(422, "magnitude must be a finite number")
                return b.apply(str(cmd.get("id")), m)
            if t == "line":
                return b.set_line(str(cmd.get("id")), bool(cmd.get("enabled")))
            if t == "xeno14":
                ids = cmd.get("ids")
                if not isinstance(ids, list) or any(i not in xeno14.BY_ID for i in ids):
                    raise OpError(422, "ids must be a list of Xeno-14 principle ids")
                return b.set_xeno14(ids)
            if t == "observation":
                return b.set_observation(observation_from(cmd.get("observation"), len(b.cfg["links"])))
            raise OpError(422, f"unknown command type {t!r}")
        except (xcfg.ConfigError, observation.ObservationError, KeyError) as e:
            raise OpError(422, str(e)) from e


def body_inspect(ws: Workspace, bid: str, part: str, seconds: float = 5.0) -> dict[str, Any]:
    b, lk = _body(ws, bid)
    if not 0.5 <= seconds <= 30.0:
        raise OpError(422, "seconds must be within 0.5..30")
    with lk:
        try:
            return b.inspect(part, seconds)
        except xcfg.ConfigError as e:
            raise OpError(422, str(e)) from e


def body_close(ws: Workspace, bid: str) -> dict[str, Any]:
    with ws.lock:
        if ws.bodies.pop(bid, None) is None:
            raise OpError(404, "no such body")
    return {"closed": bid}


def body_to_record(ws: Workspace, bid: str) -> dict[str, Any]:
    """Save the run of a live body as a record: the configuration, the interventions in order, the observation configuration at the
    end, and the reference trajectory summary. (The live run is repeatable from its log and seeds.)"""
    b, lk = _body(ws, bid)
    if len(ws.history.order) >= XB.max_records:
        raise LimitError("max_records", f"this workspace holds {XB.max_records} records; delete one first", 422)
    with lk:
        run = b.record()
        m = metrics.summary(run)
        nm = metrics.numeric_only(m)
        res = {
            "tables": [
                experiments.table(
                    "live_run_summary",
                    "Reference summary of the live run (per seed)",
                    ["measure", *[f"seed {s}" for s in b.seeds]],
                    [[k, *[None if not np.isfinite(x) else float(x) for x in np.atleast_1d(v)]] for k, v in nm.items()],
                ),
                experiments.table(
                    "live_run_log",
                    "What was done to the body, in order",
                    ["t (s)", "event", "detail"],
                    [[e.get("t"), e.get("event"), str({k: v for k, v in e.items() if k not in ("t", "event")})] for e in b.log],
                ),
            ],
            "log": b.log,
            "duration_s": b.t,
        }
        rec = records.make_record(
            "L",
            {"preset": b.preset, "seeds": b.seeds, "duration_s": round(b.t, 3)},
            b.seeds,
            b.cfg,
            [b.obs],
            [e for e in b.log if e.get("event") == "intervention"],
            res,
            [],
            [],
            {"reentry": []},
            run.dt,
        )
        slow = run.slow_end
    with ws.lock:
        stored = ws.history.add(rec, slow)
    return _summary(stored)


# ------------------------------------------------------------------------------------------------ the route table (shared by every transport)
import re  # noqa: E402


@dataclass
class Raw:
    """A text download (JSON / CSV export)."""

    text: str
    mime: str
    filename: str


def _json_body(body: Any) -> dict[str, Any]:
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise OpError(422, "the request body must be a JSON object")
    return body


def _h_create_ws(owner, p, q, b):
    return create_workspace(owner)


def _h_export_record(owner, p, q, b):
    ws = workspace(p["wid"], owner)
    fmt = q.get("format")
    if fmt is None:
        return get_record(ws, p["rid"])
    text, mime, name = export_record(ws, p["rid"], fmt)
    return Raw(text, mime, name)


def _h_experiment(owner, p, q, b):
    b = _json_body(b)
    if "experiment" not in b:
        raise OpError(422, "give 'experiment' (and optionally 'params')")
    return {"job": start_experiment(workspace(p["wid"], owner), str(b["experiment"]), b.get("params"))}


def _h_reenter(owner, p, q, b):
    b = _json_body(b)
    if "experiment" not in b:
        raise OpError(422, "give 'experiment' (and optionally 'params')")
    return {"job": reenter(workspace(p["wid"], owner), p["rid"], str(b["experiment"]), b.get("params"))}


def _h_inspect(owner, p, q, b):
    return body_inspect(workspace(p["wid"], owner), p["bid"], q.get("part", ""), float(q.get("seconds", 5.0)))


def _h_step(owner, p, q, b):
    b = _json_body(b)
    return body_step(workspace(p["wid"], owner), p["bid"], b.get("n", 5))


ROUTES: list[tuple[str, re.Pattern, Any]] = [
    (m, re.compile(pat), fn)
    for m, pat, fn in [
        ("GET", r"/catalog", lambda o, p, q, b: catalog()),
        ("POST", r"/diagnose", lambda o, p, q, b: diagnose(_json_body(b))),
        ("POST", r"/workspaces", _h_create_ws),
        ("DELETE", r"/workspaces/(?P<wid>[a-f0-9]+)", lambda o, p, q, b: close_workspace(p["wid"], o)),
        ("GET", r"/workspaces/(?P<wid>[a-f0-9]+)/history", lambda o, p, q, b: history_view(workspace(p["wid"], o))),
        (
            "GET",
            r"/workspaces/(?P<wid>[a-f0-9]+)/history/export",
            lambda o, p, q, b: Raw(
                json.dumps(export_history(workspace(p["wid"], o)), sort_keys=True), "application/json", "xbtro-history.json"
            ),
        ),
        ("POST", r"/workspaces/(?P<wid>[a-f0-9]+)/history/import", lambda o, p, q, b: import_history(workspace(p["wid"], o), b)),
        ("POST", r"/workspaces/(?P<wid>[a-f0-9]+)/records", lambda o, p, q, b: import_record(workspace(p["wid"], o), b)),
        ("GET", r"/workspaces/(?P<wid>[a-f0-9]+)/records/(?P<rid>[A-Za-z0-9_.\-]+)", _h_export_record),
        (
            "DELETE",
            r"/workspaces/(?P<wid>[a-f0-9]+)/records/(?P<rid>[A-Za-z0-9_.\-]+)",
            lambda o, p, q, b: delete_record(workspace(p["wid"], o), p["rid"]),
        ),
        (
            "POST",
            r"/workspaces/(?P<wid>[a-f0-9]+)/records/(?P<rid>[A-Za-z0-9_.\-]+)/rerun",
            lambda o, p, q, b: {"job": rerun(workspace(p["wid"], o), p["rid"])},
        ),
        (
            "POST",
            r"/workspaces/(?P<wid>[a-f0-9]+)/records/(?P<rid>[A-Za-z0-9_.\-]+)/reanalyse",
            lambda o, p, q, b: {"job": reanalyse(workspace(p["wid"], o), p["rid"], _json_body(b).get("observation"))},
        ),
        ("POST", r"/workspaces/(?P<wid>[a-f0-9]+)/records/(?P<rid>[A-Za-z0-9_.\-]+)/reenter", _h_reenter),
        ("POST", r"/workspaces/(?P<wid>[a-f0-9]+)/experiments", _h_experiment),
        ("GET", r"/workspaces/(?P<wid>[a-f0-9]+)/jobs", lambda o, p, q, b: jobs(workspace(p["wid"], o))),
        (
            "GET",
            r"/workspaces/(?P<wid>[a-f0-9]+)/jobs/(?P<jid>[a-f0-9]+)",
            lambda o, p, q, b: job_view(workspace(p["wid"], o), p["jid"]),
        ),
        (
            "POST",
            r"/workspaces/(?P<wid>[a-f0-9]+)/jobs/(?P<jid>[a-f0-9]+)/cancel",
            lambda o, p, q, b: cancel(workspace(p["wid"], o), p["jid"]),
        ),
        ("POST", r"/workspaces/(?P<wid>[a-f0-9]+)/bodies", lambda o, p, q, b: create_body(workspace(p["wid"], o), _json_body(b))),
        (
            "GET",
            r"/workspaces/(?P<wid>[a-f0-9]+)/bodies/(?P<bid>[a-f0-9]+)",
            lambda o, p, q, b: body_info(workspace(p["wid"], o), p["bid"]),
        ),
        ("POST", r"/workspaces/(?P<wid>[a-f0-9]+)/bodies/(?P<bid>[a-f0-9]+)/step", _h_step),
        (
            "POST",
            r"/workspaces/(?P<wid>[a-f0-9]+)/bodies/(?P<bid>[a-f0-9]+)/command",
            lambda o, p, q, b: body_apply(workspace(p["wid"], o), p["bid"], _json_body(b)),
        ),
        ("GET", r"/workspaces/(?P<wid>[a-f0-9]+)/bodies/(?P<bid>[a-f0-9]+)/inspect", _h_inspect),
        (
            "POST",
            r"/workspaces/(?P<wid>[a-f0-9]+)/bodies/(?P<bid>[a-f0-9]+)/save",
            lambda o, p, q, b: {"record": body_to_record(workspace(p["wid"], o), p["bid"])},
        ),
        (
            "DELETE",
            r"/workspaces/(?P<wid>[a-f0-9]+)/bodies/(?P<bid>[a-f0-9]+)",
            lambda o, p, q, b: body_close(workspace(p["wid"], o), p["bid"]),
        ),
    ]
]
JOB_START = re.compile(r"^/workspaces/[^/]+/(experiments|records/[^/]+/(rerun|reanalyse|reenter))$")


def dispatch(method: str, path: str, query: dict[str, str], body: Any, owner: str | None) -> Any:
    """Serve one request. ``path`` is relative to /api/xbtro. Raises OpError / LimitError."""
    if not enabled():
        raise OpError(
            404, "the XenoBody research environment is not enabled on this runtime (use the browser edition or a local runtime)"
        )
    for m, pat, fn in ROUTES:
        if m == method:
            mm = pat.fullmatch(path)
            if mm:
                return fn(owner, mm.groupdict(), query, body)
    raise OpError(404, "no such route")
