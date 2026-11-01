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
from ..teoo import export as EX
from ..teoo import ingest as IN
from ..teoo import lawbundle as LB
from ..teoo import legal as LG
from ..teoo import mapping as MP
from ..teoo import mheg as MH
from ..teoo import observation as OB
from ..teoo import provenance as P
from ..teoo import safety as SF
from ..teoo import schema as SC
from ..teoo import session as SE
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


# ------------------------------------------------------------------------------------------------ Phase 3: the session bundle (Views B-H), observation replay, figures, safety
_SESSIONS: dict[int, dict] = {}


def _session(seed: int) -> dict:
    if not 0 <= seed <= 10_000:
        raise HTTPException(422, "seed must be 0..10000")
    if seed not in _SESSIONS:
        if len(_SESSIONS) > 8:
            _SESSIONS.clear()
        _SESSIONS[seed] = SE.build_session(seed)
    return _SESSIONS[seed]


@router.get("/session")
def session(request: Request, seed: int = 7) -> dict:
    """The research session bundle: SYNTHETIC records, the body versions, the observation configuration history with its revisions, the reconstruction, the intervention, the protocol and its replay, the relation field.
    All views read this one bundle: the same record ids, the same time base, the same body versions."""
    local_only(request)
    return _session(seed)


@router.get("/observation")
def observation(request: Request, t: float = 0.0, seed: int = 7) -> dict:
    """The observation state at time t, replayed from the configuration history (what each declared target's observability was)."""
    local_only(request)
    s = _session(seed)
    if not 0.0 <= t <= 1_000_000.0:
        raise HTTPException(422, "t must be a number of seconds >= 0")
    return OB.state_at(s["observation"]["history"], s["observation"]["specs"], t)


@router.post("/figure")
def figure(request: Request, body: dict[str, Any]) -> dict:
    """A figure of the session as SVG with its metadata (JSON): the evidence band and the watermarks are part of the rendering and cannot be turned off."""
    local_only(request)
    kind = body.get("kind")
    if kind not in ("timeseries", "body", "limits", "evidence"):
        raise HTTPException(422, "kind must be timeseries, body, limits or evidence")
    out = SE.figure_for(_session(int(body.get("seed", 7))), kind, generated_at=str(body.get("generated_at") or P.now_iso()))
    return {"svg": out["svg"], "metadata": out["metadata"], "metadata_ascii": EX.metadata_ascii(out["metadata"]), "issues": EX.verify_svg(out["svg"])}


@router.post("/figure/verify")
def figure_verify(request: Request, body: dict[str, Any]) -> dict:
    local_only(request)
    svg, png = body.get("svg"), body.get("png_base64")
    if isinstance(svg, str) and len(svg) <= 2_000_000:
        return {"kind": "svg", "issues": EX.verify_svg(svg)}
    if isinstance(png, str) and len(png) <= 6_000_000:
        import base64
        return {"kind": "png", **EX.inspect_png(base64.b64decode(png))}
    raise HTTPException(422, "svg (a string) or png_base64 is required")


@router.get("/safety")
def safety(request: Request) -> dict:
    """The capabilities, the threat model and the production gate. No human measurement may be ingested for real while the gate is closed; the service stores nothing."""
    local_only(request)
    return {**SF.production_gate(), "stored_on_server": False}


_LEGAL: dict[int, dict] = {}


@router.get("/legal")
def legal(request: Request, seed: int = 3) -> dict:
    """The AI legal governance bundle: the fifteen guarantees (public specification; the wording is held privately) assessed for five synthetic institutions, the twelve MHEG duties and their functional crosswalk (``mheg``), the legal translation chains, the intervention comparison and the observation conditions. Computed from small
    simulations on demand; nothing is stored; a synthetic institution, not any real one."""
    local_only(request)
    if not 0 <= seed <= 10_000:
        raise HTTPException(422, "seed must be between 0 and 10000")
    if seed not in _LEGAL:
        if len(_LEGAL) > 8:
            _LEGAL.clear()
        lb = LG.legal_bundle(seed)
        _LEGAL[seed] = {**lb, "mheg": MH.mheg_bundle(lb), "ledger": LB.law_bundle(seed)}
    return _LEGAL[seed]
