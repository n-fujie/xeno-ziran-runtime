"""Fairness profiles and the operation access matrix of the shared environment (both arm families, same keys)."""

from __future__ import annotations

from .. import ards
from . import ops


def profile(arm: dict, env: dict) -> dict:
    if arm.get("hpo") is not None:
        h = arm["hpo"]
        return {
            "information": {"reads": "observer-view", "environment": "env3"},
            "revision_authority": sorted(ops.REVISION_OPS),
            "controller": "revised-from-data",
            "proposal_policy": "HPO-003 rule table (reason -> instrument change, bundle)",
            "meta_revision": bool(h.get("meta", False)),
            "history_reinsertion": bool(h.get("history", True)),
            "max_changes_per_epoch": None,
            "interventions": 0,
            "compute": {"warmup": None, "horizon": None, "epoch": None, "systems": None, "ards_env": "env3"},
        }
    return ards.profile(arm, {**env, "ards_env": "env3"})


def access_matrix(doc: dict) -> dict:
    out = {}
    for a in doc["arms"]:
        if a.get("hpo") is not None:
            out[a["name"]] = ops.access("hpo", a["hpo"])
        else:
            out[a["name"]] = ops.access("ards", ards.arm_spec(a["ards"]["arm"]) or {})
    return {"operations": ops.OPERATIONS, "access": out}
