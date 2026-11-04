"""GAISHO - Operational Shape Laboratory over HTTP, for the XENO ECOSYSTEM view.

Stateless and deterministic: a request carries a specification (a domain, an observation condition, seeds) and the answer is the record of that executed computational experiment; nothing is stored, and a history is recovered
by running the record's specification again (``/restore``). Local runtime only, like the MEOS and TRUTH-ERROR routes (403 under XZR_PUBLIC). The endpoints take numbers and names of the laboratory's own conditions: no
image, no video, no identifier of a person. SYNTHETIC computational experiments only.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ..gaisho import MODEL_VERSION
from ..gaisho.claims import CLAIMS
from ..gaisho.compare import compare_models, compare_observations
from ..gaisho.construction import change_kinds_of_observations, explain_shape, reading_of_difference
from ..gaisho.domains import STATUS, domain_registry
from ..gaisho.export import MAX_SEEDS, observation_from, restore, run_experiment
from ..gaisho.figure import figure_svg
from ..gaisho.knowledge import ENVIRONMENTS
from ..gaisho.lab import FULL
from ..gaisho.model import (
    FIGURE_KINDS,
    LEVEL_LABELS,
    LEVEL_STATES,
    LIMITS,
    OBSERVATION_AXES,
    PROHIBITED_INFERENCES,
    PROVENANCE,
    UNOBSERVED,
    VERDICTS,
)
from ..gaisho.shape import compare_shapes
from .studies import local_only

router = APIRouter(prefix="/api/gaisho")
# An experiment is CPU-bound and runs in the request: at most two at a time (a third is refused with 429, not queued), each request bounded by its seeds, its distinct conditions and the domain's own seed cap.
_BUSY = threading.BoundedSemaphore(2)


@contextmanager
def _compute() -> Iterator[None]:
    if not _BUSY.acquire(blocking=False):
        raise HTTPException(429, "the laboratory is running its maximum number of experiments: try again when one has finished")
    try:
        yield
    finally:
        _BUSY.release()


_OBS_LIMITS = {"sensor_noise": (0.0, 0.45), "scale": (1, 4), "temporal_window": (5, 200), "speed": (1, 3), "resources": (1, 10_000), "probe": (0.0, 2.0)}


def _obs(d: Any):
    d = d or {}
    if not isinstance(d, dict) or set(d) - set(FULL.asdict()):
        raise HTTPException(422, f"an observation takes only {sorted(FULL.asdict())}")
    for k, (lo, hi) in _OBS_LIMITS.items():
        if k in d and not (isinstance(d[k], int | float) and not isinstance(d[k], bool) and lo <= d[k] <= hi):
            raise HTTPException(422, f"{k} must be a number {lo}..{hi}")
    if "coupling" in d and d["coupling"] not in ("intervened", "passive"):
        raise HTTPException(422, "coupling must be intervened or passive")
    if "environment" in d and d["environment"] not in ENVIRONMENTS:
        raise HTTPException(422, f"environment must be one of {sorted(ENVIRONMENTS)}")
    if "memory" in d and not isinstance(d["memory"], bool):
        raise HTTPException(422, "memory must be true or false")
    for k, allowed in (("boundary", ("x", "y")), ("sensor_channels", ("x", "y", "memory"))):
        if k in d and (not isinstance(d[k], list | tuple) or set(d[k]) - set(allowed)):
            raise HTTPException(422, f"{k} takes only {allowed}")
    return observation_from(d)


def _spec(body: dict) -> dict:
    dom = body.get("domain")
    reg = domain_registry()
    if dom not in reg:
        raise HTTPException(422, f"domain must be one of {sorted(reg)}")
    d = reg[dom]
    cap = min(MAX_SEEDS, getattr(d, "max_seeds", MAX_SEEDS))
    seeds = body.get("seeds")
    if seeds is not None and (not isinstance(seeds, list) or not seeds or len(seeds) > cap or not all(isinstance(s, int) and not isinstance(s, bool) and 1 <= s <= 1000 for s in seeds)):
        raise HTTPException(422, f"seeds must be a list of 1..{cap} integers 1..1000")
    conds = body.get("conditions")
    if conds is not None and (d is None or not isinstance(conds, list) or not conds or len(conds) != len(set(map(str, conds))) or not all(isinstance(c, str) for c in conds) or set(conds) - set(d.conditions)):
        raise HTTPException(422, "conditions must be distinct names of the domain's conditions")
    return {"domain": dom, "observation": _obs(body.get("observation")).asdict(), "seeds": seeds, "conditions": conds}


@router.get("/spec")
def spec(request: Request) -> dict:
    local_only(request)
    reg = domain_registry()
    return {
        "model_version": MODEL_VERSION,
        "scope": "SYNTHETIC computational experiments only: no human neural activity, no real institution, no real person. The laboratory executes operations and records differences; it never computes a Gaisho attribution.",
        "source_status": "the manuscript GAISHO R37 was not found on this machine; the five levels, the twelve questions and the verdicts are those of the development brief, and nothing is taken from R37",
        "domains": {k: {"title": d.title if d else None, "conditions": list(d.conditions) if d else [], "x": d.x_name if d else None, "y": d.y_name if d else None, "snapshots": list(d.snapshots) if d else [], "relations": list(d.relation_names) if d else [], "max_seeds": getattr(d, "max_seeds", 0) if d else 0, "status": STATUS[k]} for k, d in reg.items()},
        "observation_axes": list(OBSERVATION_AXES),
        "observation_defaults": FULL.asdict(),
        "environments": list(ENVIRONMENTS),
        "levels": LEVEL_LABELS,
        "level_states": list(LEVEL_STATES),
        "provenance_classes": list(PROVENANCE),
        "unobserved_classes": list(UNOBSERVED),
        "verdicts": list(VERDICTS),
        "figure_kinds": list(FIGURE_KINDS),
        "prohibited_inferences": [{"premise": p, "conclusion": c, "reason": w} for p, c, w in PROHIBITED_INFERENCES],
        "limits": LIMITS,
        "claims": list(CLAIMS),
    }


@router.post("/run")
def run(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    sp = _spec(body)
    with _compute():
        return run_experiment(sp)


@router.post("/compare-observations")
def compare_obs(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    s = _spec(body)
    dom = domain_registry()[s["domain"]]
    cond = body.get("condition")
    if dom is None or cond not in dom.conditions:
        raise HTTPException(422, "condition must be a condition of an executed domain")
    a, b = _obs(body.get("first")), _obs(body.get("second"))
    seeds = tuple(s["seeds"] or range(1, min(11, getattr(dom, "seed_count", 20) + 1)))
    with _compute():
        cmp = compare_observations(dom, cond, a, b, seeds)
    return {**cmp, "change_kinds": change_kinds_of_observations(cmp)}


@router.post("/compare-shapes")
def compare_shape(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    s = _spec(body)
    with _compute():
        rec = run_experiment(s)
    if not rec.get("executed"):
        raise HTTPException(422, "this domain is not executed")
    a, b = body.get("first") or {}, body.get("second") or {}
    try:
        sa, sb = rec["shapes"][a["condition"]][a["snapshot"]], rec["shapes"][b["condition"]][b["snapshot"]]
    except (KeyError, TypeError) as exc:
        raise HTTPException(422, "first and second are {condition, snapshot} of the record") from exc
    cmp = compare_shapes(sa, sb)
    return {"comparison": cmp, "reading": reading_of_difference(sa, sb, cmp) if cmp.get("comparable") else None, "digest": rec["digest"]}


@router.post("/construction")
def construction(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    s = _spec(body)
    with _compute():
        rec = run_experiment(s)
    if not rec.get("executed"):
        raise HTTPException(422, "this domain is not executed")
    cond, snap = str(body.get("condition")), str(body.get("snapshot"))
    try:
        rec["shapes"][cond][snap]
    except (KeyError, TypeError) as exc:
        raise HTTPException(422, "condition and snapshot must be those of the record") from exc
    return {**explain_shape(rec, cond, snap, domain_registry()[s["domain"]]), "digest": rec["digest"]}


@router.post("/figure")
def figure(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    sp = _spec(body)
    with _compute():
        rec = run_experiment(sp)
    if not rec.get("executed"):
        raise HTTPException(422, "this domain is not executed: no figure of an experiment is drawn for it")
    snap = body.get("snapshot", "end")
    return {"svg": figure_svg(rec, snap if isinstance(snap, str) else "end"), "digest": rec["digest"], "figure_kind": rec["figure_kind"]}


@router.post("/restore")
def restore_route(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    s = body.get("spec")
    if not isinstance(s, dict) or "digest" not in body:
        raise HTTPException(422, "a record with its spec and digest is needed")
    sp = _spec(s)
    with _compute():
        return restore({"spec": sp, "digest": body["digest"]})


@router.post("/comparators")
def comparators(request: Request, body: dict[str, Any]) -> dict:
    """The comparison with competing explanations, extended with the equal-parameter cue account and with each model's declared information, history and parameters (the record's own comparison is unchanged)."""
    local_only(request)
    s = _spec(body)
    dom = domain_registry()[s["domain"]]
    if s["domain"] != "001-knowledge" or dom is None or s["conditions"] is not None:
        raise HTTPException(422, "the comparison with competing explanations exists for the knowledge domain, over all its conditions")
    seeds = tuple(s["seeds"] or range(1, 11))
    with _compute():
        return compare_models(dom, seeds, observation_from(s["observation"]), extended=True)
