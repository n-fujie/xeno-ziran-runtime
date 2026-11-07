"""SBS API: read-only access to the recorded SBS experiments (docs/sbs/) for the SBS view.

Nothing is computed or stored here and nothing is interpolated: the answers are the saved records, as measured. Local runtime only, like the other research routes: on a public deployment (XZR_PUBLIC=1) every route answers 403 and a request made from another site's page is refused. The file is not part of the iOS app or the public browser runtime (ios/scripts/stage_engine.py)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from .studies import local_only

router = APIRouter(prefix="/api/sbs", dependencies=[Depends(local_only)])
DOCS = Path(__file__).resolve().parents[3] / "docs" / "sbs"


def _load(name: str) -> dict[str, Any]:
    f = DOCS / name
    if not f.is_file():
        raise HTTPException(404, f"{name} is not present; run scripts/sbs_experiments.py")
    return json.loads(f.read_text())


@router.get("/summary")
def summary() -> dict[str, Any]:
    """Provenance, protocol, per-branch outcomes and records (without positions), the hysteresis sweeps and the model comparison."""
    r = _load("sbs_records.json")
    worlds = [{"seed": w["seed"], "formation": w["formation"], "reference_group_size": w["reference_group_size"], "branches": w["branches"]} for w in r["worlds"]]
    return {**{k: r[k] for k in ("classification", "frozen_protocol_in_code", "protocol", "protocol_digest", "source_revision", "environment", "config", "seeds", "reproduce", "metastability", "comparison")}, "worlds": worlds}


@router.get("/frames")
def frames() -> dict[str, Any]:
    """Measured positions of every particle every 250 steps for the worlds that kept them (not interpolated)."""
    return _load("sbs_frames.json")
