"""TRUTH-ERROR API: the synthetic institution (xzr.truth_error) over HTTP, for the XENO ECOSYSTEM view.

Stateless and read-only: a request carries a configuration and the answer is the deterministic record of that run. Local runtime only, like the MEOS routes (every route answers 403 under XZR_PUBLIC=1).
SYNTHETIC subjects and institutions only: the endpoints accept numbers, never an image, a video or an identifier of a person, and nothing here assesses a real individual."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, Request

from ..truth_error import experiments as X
from ..truth_error import institution as I  # noqa: E741
from ..truth_error import pose as P
from .studies import local_only

router = APIRouter(prefix="/api/truth-error")
MAX_N, MAX_PERIODS = 300, 80
SAVED = Path(__file__).resolve().parents[3] / "docs" / "truth_error" / "experiments.json"
_CONFIG_FIELDS = {f.name for f in dataclasses.fields(I.Config)}
_SENSOR_FIELDS = {f.name for f in dataclasses.fields(P.SensorConfig)}


def _sensor(d: Any, default: P.SensorConfig) -> P.SensorConfig:
    if d is None:
        return default
    if not isinstance(d, dict) or set(d) - _SENSOR_FIELDS:
        raise HTTPException(422, f"a sensor takes only {sorted(_SENSOR_FIELDS)}")
    num = lambda v: isinstance(v, int | float) and not isinstance(v, bool)  # noqa: E731
    for k, v in d.items():
        ok = (
            (isinstance(v, list | tuple) and len(v) == 3 and all(num(x) for x in v))
            if k in ("bias", "scale_error")
            else (v is None or (isinstance(v, int) and not isinstance(v, bool) and v >= 0))
            if k == "fail_at"
            else (v in ("stuck", "zero", "drift"))
            if k == "fail_mode"
            else (isinstance(v, int) and not isinstance(v, bool) and v >= 1)
            if k in ("occlusion_length", "dropout_length")
            else num(v)
        )
        if not ok:
            raise HTTPException(422, f"sensor field {k} has an invalid value")
    kw = {k: (tuple(float(x) for x in v) if k in ("bias", "scale_error") else v) for k, v in d.items()}
    try:
        return dataclasses.replace(default, **kw)  # type: ignore[arg-type]  # the fields are checked by name above and the dataclass rejects a wrong type on use
    except TypeError as exc:
        raise HTTPException(422, str(exc)) from exc


def config_from(body: dict) -> I.Config:
    over = body.get("config") or {}
    if not isinstance(over, dict) or set(over) - _CONFIG_FIELDS:
        raise HTTPException(
            422, f"unknown configuration fields: {sorted(set(over) - _CONFIG_FIELDS) if isinstance(over, dict) else over}"
        )
    base = I.Config()
    kw = {k: v for k, v in over.items() if k not in ("pose_sensor", "signal_sensor")}
    cfg = dataclasses.replace(
        base,
        **kw,
        pose_sensor=_sensor(over.get("pose_sensor"), base.pose_sensor),
        signal_sensor=_sensor(over.get("signal_sensor"), base.signal_sensor),
    )
    if cfg.n > MAX_N or cfg.periods > MAX_PERIODS or cfg.n < 2 or cfg.periods < 14:
        raise HTTPException(422, f"n is limited to 2..{MAX_N} and periods to 14..{MAX_PERIODS} on this API")
    if cfg.classifier not in I.CLASSIFIERS:
        raise HTTPException(422, f"classifier must be one of {I.CLASSIFIERS}")
    return cfg


@router.get("/spec")
def spec(request: Request) -> dict:
    local_only(request)
    d = I.Config().asdict()
    return {
        "engine": "truth_error/1",
        "defaults": d,
        "classifiers": list(I.CLASSIFIERS),
        "warrant_states": list(I.WARRANT),
        "axes": list(P.AXES),
        "limits": {"n": MAX_N, "periods": MAX_PERIODS},
        "scope": "SYNTHETIC only: no real person, face, credit or eligibility; head pose is a measurement, not an indicator of truthfulness, character or creditworthiness; the head-pose classifier is invalid by construction",
        "experiments": [{"id": k} for k in X.REGISTRY],
    }


@router.post("/run")
def run(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    try:
        return I.run(config_from(body))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/pose")
def pose(request: Request, body: dict[str, Any]) -> dict:
    """A synthetic head pose of one virtual subject and what a sensor with the given conditions measured of it (for the 3D pose viewer). Numbers in, numbers out."""
    local_only(request)
    periods = int(body.get("periods", 40))
    if not 2 <= periods <= 200:
        raise HTTPException(422, "periods must be 2..200")
    seed = int(body.get("seed", 1))
    sensor = _sensor(body.get("sensor"), P.SensorConfig())
    ref = P.reference_pose(np.random.default_rng(seed), 1, periods)[0]
    out = P.measure_series(ref, sensor, seed)
    tol = [P.tolerance(a) for a in range(3)]
    err = np.abs(out["values"] - ref)
    return {
        "axes": list(P.AXES),
        "reference": np.round(ref, 3).tolist(),
        "measured": [[None if np.isnan(x) else round(float(x), 3) for x in row] for row in out["values"]],
        "confidence": np.round(out["confidence"], 4).tolist(),
        "missing_reason": out["reason"].astype(int).tolist(),
        "uncertainty_degrees": round(float(out["sigma"]), 4),
        "tolerance_degrees": tol,
        "sensor": sensor.asdict(),
        "within_tolerance": [None if np.isnan(err[t, 0]) else bool(np.all(err[t] <= np.array(tol))) for t in range(periods)],
        "note": "a synthetic pose and a sensor model; it is not a face, not a landmark model, and says nothing about a person",
    }


@router.get("/experiments")
def experiments(request: Request) -> dict:
    local_only(request)
    if not SAVED.is_file():
        raise HTTPException(
            404, "the experiment results are not saved on this server: run backend/scripts/truth_error_experiments.py"
        )
    return json.loads(SAVED.read_text())
