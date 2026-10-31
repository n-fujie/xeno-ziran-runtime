"""TEOO API: the BODY / TOTAL OBSERVATION view's endpoints (xzr.teoo) over HTTP.

Local runtime only (like the study and MEOS routes: 403 under XZR_PUBLIC, and a request from another site's page is refused): what can pass through these routes is body observation data.
Nothing is stored on the server: an ingestion is validated and the sealed record is returned to the caller; ``stored`` is false and the response says which protections are implemented and which
are not (``protections``). Bounded sizes. SYNTHETIC records carry a banner that the response always includes.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ..teoo import TEOO_VERSION
from ..teoo import body as B
from ..teoo import evidence as EV
from ..teoo import ingest as IN
from ..teoo import mapping as MP
from ..teoo import provenance as P
from ..teoo import schema as SC
from ..teoo import synthetic as SY
from ..teoo import xbtro_adapter as XA
from .studies import local_only

router = APIRouter(prefix="/api/teoo")
MAX_BYTES = 1_000_000
MAX_RECORDS = 50


def _info() -> dict:
    return {"version": TEOO_VERSION, "schemas": list(SC.SCHEMA_IDS), "domains": [{"id": d, "label": lab} for d, lab in SC.DOMAINS], "provenance": [p.value for p in P.Provenance], "kinds": [k.value for k in P.Kind],
            "statuses": list(__import__("xzr.teoo.status", fromlist=["STATUS_IDS"]).STATUS_IDS), "presets": sorted(B.PRESETS), "protections": P.PROTECTIONS, "retained_results": list(XA.RETAINED_RESULTS),
            "xeno14": {"ids": list(XA.XENO14_IDS), "source": XA.XENO14_SOURCE}, "stored_on_server": False,
            "limits": ["a conceptual drawing is not a photograph; SYNTHETIC data are functional-test data and not a body model", "a record is not evidence; digests detect change, they do not authenticate",
                       "no medical conclusion is drawn from anything here"]}


@router.get("/info")
def info(request: Request) -> dict:
    local_only(request)
    return _info()


@router.get("/demo")
def demo(request: Request, seed: int = 7) -> dict:
    """The SYNTHETIC example: a human simplified-skeleton preset, one sealed SYNTHETIC record with every observation limit, the coverage of the body's targets, and the ledger's verification."""
    local_only(request)
    if not 0 <= seed <= 10_000:
        raise HTTPException(422, "seed must be 0..10000")
    d = SY.make_demo(seed)
    return {"banner": d["banner"], "synthetic": True, "body": d["body"].to_dict(), "records": d["records"], "evidence": [EV.classify(r) for r in d["records"]], "coverage": d["coverage"],
            "ledger": {"entries": len(d["ledger"].entries), "issues": [i.to_dict() for i in d["ledger"].verify()], "checkpoint": d["ledger"].checkpoint()}, "info": _info()}


@router.get("/body/{preset}")
def body_preset(request: Request, preset: str) -> dict:
    local_only(request)
    if preset not in B.PRESETS:
        raise HTTPException(404, f"no such preset; one of {sorted(B.PRESETS)}")
    b = B.PRESETS[preset]()
    return {"body": b.to_dict(), "issues": [i.to_dict() for i in B.validate_body(b)], "concept_only": True}


@router.post("/ingest")
def ingest(request: Request, body: dict[str, Any]) -> dict:
    """Validate a CSV or JSON document and, if it has no blocking error, return the sealed record. Nothing is stored. A document without a declared provenance is refused (quarantined in memory only)."""
    local_only(request)
    text, mt, manifest, preset = body.get("text"), body.get("media_type"), body.get("manifest"), body.get("body_preset", "human-simplified-skeleton")
    if not isinstance(text, str) or len(text.encode()) > MAX_BYTES or not isinstance(mt, str):
        raise HTTPException(422, f"text (a string of at most {MAX_BYTES} bytes) and media_type are required")
    if preset not in B.PRESETS:
        raise HTTPException(422, f"body_preset must be one of {sorted(B.PRESETS)}")
    if manifest is not None and not isinstance(manifest, dict):
        raise HTTPException(422, "manifest must be an object")
    res = IN.ingest(text.encode(), media_type=mt, registry=SC.default_registry(), body=B.PRESETS[preset](), quarantine=P.Quarantine(), manifest=manifest)
    out = res.to_dict()
    out.update({"stored": False, "record": res.record, "protections": P.PROTECTIONS,
                "evidence": EV.classify(res.record) if res.record else None, "note": "nothing was stored; keep the record and its raw original, and export the ledger checkpoint elsewhere if you need to prove they were not changed"})
    return out


@router.post("/verify")
def verify(request: Request, body: dict[str, Any]) -> dict:
    """Verify records as a ledger (each parent before its children): digests, class rules, lineage."""
    local_only(request)
    recs = body.get("records")
    if not isinstance(recs, list) or len(recs) > MAX_RECORDS or len(json.dumps(recs)) > MAX_BYTES * 2:
        raise HTTPException(422, f"records: a list of at most {MAX_RECORDS} records")
    seen: dict[str, dict] = {}
    out = []
    for i, r in enumerate(recs):
        issues = P.verify_record(r, seen)
        out.append({"index": i, "record_id": r.get("record_id") if isinstance(r, dict) else None, "ok": not issues, "issues": [x.to_dict() for x in issues]})
        if isinstance(r, dict) and "record_id" in r:
            seen[r["record_id"]] = r
    return {"ok": all(o["ok"] for o in out), "results": out}


@router.post("/coverage")
def coverage(request: Request, body: dict[str, Any]) -> dict:
    """Coverage of a body preset's observation targets by the supplied (already verified) records."""
    local_only(request)
    recs, preset = body.get("records") or [], body.get("body_preset", "human-simplified-skeleton")
    if preset not in B.PRESETS or not isinstance(recs, list) or len(recs) > MAX_RECORDS:
        raise HTTPException(422, "body_preset and a list of at most 50 records are required")
    return MP.coverage(B.PRESETS[preset](), recs)
