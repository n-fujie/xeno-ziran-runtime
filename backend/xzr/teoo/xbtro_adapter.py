"""XB-TRO connection: an *adapter*, not an import.

XB-TRO (branch ``feat/xb-tro``, ``backend/xzr/xbtro/``, commit 94c2e8e) is a separate research layer with its own claims, conditions and verification. TEOO does not import it,
does not merge its branch and does not change what it claims. This module reads XB-TRO's **plain JSON outputs** (a body configuration dict, a live step) and expresses them in TEOO's
terms:

* a declarative body configuration (links, joints, operation lines, ``observable_by``) -> an Open Body Graph (:func:`body_from_config`); joint i joins link i-1 to link i and joint 0 joins
  the ground to link 0 (the N-link planar chain convention of xbtro/engine.py);
* a live step (``frames[].reference``, ``frames[].estimates``, ``observation[kind]``) -> three kinds of record kept apart: REFERENCE_STATE, ESTIMATE and OBSERVATION (:func:`records_from_live_step`);
  XB-TRO's body is a simulated planar model ("nothing here is measured physiology"), so every such record is SYNTHETIC, whatever its kind.

``XENO14_IDS`` are the fourteen principle names of the reference definition, ziran-xeno-simulator ``src/domains/body.ts`` ``XENO14`` (xbtro/xeno14.py cites it as its SOURCE); a test compares them
with both files. ``RETAINED_RESULTS`` keeps the negative and limited results of the Xeno-14 line exactly as their reports state them.
"""

from __future__ import annotations

from typing import Any

from .body import Body, boundary, component, new_body, relation, target
from .provenance import Kind, Provenance, seal

XENO14_IDS = ("lower-abdominal-continuity", "whole-skin-sensing", "axis-maintenance", "endpoint-removal", "low-noise-movement", "minimal-approach-distance", "zero-run-up-transition",
              "tensegrity", "slow-movement", "narrow-step-balance", "fingertip-tension", "breathing-synchronization", "anti-collapse-posture", "long-duration-sedimentation")
XENO14_SOURCE = {"definition": "ziran-xeno-simulator: src/domains/body.ts (XENO14)", "xbtro": "xeno-ziran-runtime feat/xb-tro: backend/xzr/xbtro/xeno14.py (PRINCIPLES; its SOURCE cites body.ts)"}
RETAINED_RESULTS = (
    {"id": "X14-1", "status": "STOP", "source": "ziran-xeno-simulator embodied/README.md; docs/xeno14-x14-1-report.md", "scope": "simulated planar embodiments (Walker2d-v5, Hopper-v5)"},
    {"id": "X14-1b", "status": "CONDITIONAL GO (predefined rule); no non-redundant control advantage demonstrated; analyst assessment: recommend not expanding to X14-2", "source": "ziran-xeno-simulator docs/xeno14-x14-1b-report.md", "scope": "simulated planar embodiments"},
    {"id": "BS-1", "status": "base stabilizer not accepted (A1-A3 fail on held-out seeds)", "source": "ziran-xeno-simulator docs/base-stabilizer-bs1-report.md (commit e37520f)", "scope": "simulated planar embodiments"},
)
SOURCE_META = {"repo": "xeno-ziran-runtime", "branch": "feat/xb-tro", "commit": "94c2e8e", "module": "backend/xzr/xbtro/", "claims": "unchanged: a limited planar model with nominal parameters; nothing here is measured physiology"}


def body_from_config(cfg: dict, *, preset: str, at: str | None = None) -> Body:
    """An XB-TRO body configuration (a plain dict) as an Open Body Graph."""
    links, joints, lines = cfg.get("links", []), cfg.get("joints", []), cfg.get("lines", [])
    comps = [component("ground", "environment", "ground (support)", from_xbtro=False)]
    comps += [component(f"link:{lk['id']}", "segment", lk.get("label", lk["id"]), region=lk.get("region"), length=lk.get("length"), mass=lk.get("mass"), from_xbtro="links") for lk in links]
    comps += [component(f"line:{ln['id']}", "operation-line", ln.get("label", ln["id"]), line_kind=ln.get("kind"), timescale_s=ln.get("timescale_s"), enabled=ln.get("enabled"), observable_by=ln.get("observable_by", []),
                        from_xbtro="lines") for ln in lines]
    rels, tgts = [], []
    for i, j in enumerate(joints):
        a = "ground" if i == 0 else f"link:{links[i - 1]['id']}"
        rels.append(relation(f"joint:{j['id']}", a, f"link:{links[i]['id']}", "joint", convention="xbtro-chain-order"))
    for ln in lines:
        tgts.append(target(f"tgt.line:{ln['id']}", f"line:{ln['id']}", [], None, observation_kinds=ln.get("observable_by", [])))
    family = "artificial" if "machine" in preset else "human"
    return new_body(f"body.xbtro.{preset}", f"XB-TRO {preset} (a limited planar model)", family, components=comps, relations=rels, targets=tgts, at=at,
                    boundaries=[boundary("bd.chain", [c["id"] for c in comps if c["kind"] == "segment"], "the links of the planar chain")],
                    meta={"preset": preset, "source": SOURCE_META, "xeno14_conditions": cfg.get("xeno14"), "note": "read from XB-TRO's configuration dict; TEOO does not run it"})


def records_from_live_step(step_out: dict, *, creator: dict, created_at: str | None = None) -> list[dict]:
    """The three kinds of XB-TRO output as three sealed records (never merged): REFERENCE_STATE, ESTIMATE, OBSERVATION. All SYNTHETIC: a simulated body."""
    src = {"kind": "generator", "description": "XB-TRO live body session (a simulated planar body; nothing here is measured physiology)", "declared_by": "xbtro.live", "xbtro": SOURCE_META}
    frames = step_out["frames"]
    ref = seal({"xbtro": {"t": [f["t"] for f in frames], "reference": [f["reference"] for f in frames]}}, provenance=Provenance.SYNTHETIC, kind=Kind.REFERENCE_STATE, creator=creator, source=src, created_at=created_at)
    est = seal({"xbtro": {"t": [f["t"] for f in frames], "estimates": [f["estimates"] for f in frames]}}, provenance=Provenance.SYNTHETIC, kind=Kind.ESTIMATE, creator=creator, source=src, created_at=created_at)
    obs_payload: dict[str, Any] = {"body": {"id": None, "version": None}, "time": {"device_clock": "xbtro-model-clock", "unit": "s"}, "channels": []}
    for kind, blk in step_out.get("observation", {}).items():
        rows = blk["x"][0]  # XB-TRO's x is [seed][sample][channel]; the first seed's series is taken (declared in the channel)
        for ci, ch in enumerate(blk["channels"]):
            xs = [row[ci] for row in rows]
            obs_payload["channels"].append({"variable": f"xbtro.{kind}.{ch}", "target": None, "unit": None, "times": blk["t"], "available_at": blk["available_at"], "sample_hz": blk["sample_hz"], "seed_index": 0,
                                            "samples": [{"value": x, "status": "MEASURED_VALID", "causes": [], "cause_known": True, "detection_limit": None, "detail": None} for x in xs],
                                            "counts": {"MEASURED_VALID": len(xs)}})
    obs = seal(obs_payload, provenance=Provenance.SYNTHETIC, kind=Kind.OBSERVATION, creator=creator, source=src, created_at=created_at)
    return [ref, est, obs]
