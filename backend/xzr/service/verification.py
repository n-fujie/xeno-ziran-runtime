"""Verification API: the Brassier Machine's demonstration ledger (``xzr.verification``), computed on request from synthetic worlds.

Nothing is stored. Local runtime only, like the other research routes (403 when ``XZR_PUBLIC=1``); excluded from the iOS and browser bundles by ``ios/scripts/stage_engine.py``."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..verification.brassier import verify_record
from ..verification.demo import demo_ledger
from .studies import local_only

router = APIRouter(prefix="/api/verification", dependencies=[Depends(local_only)])


@router.get("/brassier/demo")
def brassier_demo() -> dict[str, Any]:
    """The ledger of the synthetic demonstration (three claims, three pairs of mechanisms) beside the standard AIC/BIC comparison, with the result of the seal check."""
    out = demo_ledger()
    out["seal_intact"] = verify_record(out["brassier"])
    return out
