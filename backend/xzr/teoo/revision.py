"""Open Revision: changes of the observation apparatus and the body, recorded, compared and replayed.

A revision is a record of a change of the *settings* through which a body is observed (the same sandbox as the Ziran System's HPO-003: settings only, no code is generated or changed): a sensor changed, a scale,
a time window, a boundary, a body structure, a coupling condition, a measured variable added or removed. Each carries the reason, the observation configuration versions before and after, what was lost and what became
obtainable (computed, not asserted), and a status ladder borrowed from HPO-003: ``proposed`` (no new version exists; the expected difference is computed on a hypothetical configuration), ``recorded`` (the
change was made and a new version exists) and, only by an external test, ``validated`` (never set here). **Nothing in this module shows that an observing system can revise itself**: ``initiated_by`` records who asked,
and ``autonomous_revision_demonstrated`` is false in every event.
"""

from __future__ import annotations

import copy
from collections.abc import Callable

from . import observation as OB
from .provenance import now_iso

TYPES = ("sensor_change", "scale_change", "time_window_change", "boundary_change", "body_structure_change", "coupling_change", "variable_added", "variable_removed")
STATUSES = ("proposed", "recorded", "validated")  # 'validated' is set only by an external test: no function here sets it
INITIATORS = ("researcher", "protocol", "system")


def _apply(cfg: dict, rtype: str, params: dict) -> dict:
    c = copy.deepcopy(cfg)
    byid = {s["id"]: s for s in c["sensors"]}
    if rtype == "sensor_change":
        op = params["op"]
        if op == "add":
            c["sensors"].append(params["sensor"])
        elif op == "remove":
            c["sensors"] = [s for s in c["sensors"] if s["id"] != params["id"]]
        elif op == "replace":
            c["sensors"] = [params["sensor"] if s["id"] == params["id"] else s for s in c["sensors"]]
        else:
            raise ValueError("sensor_change op is add, remove or replace")
    elif rtype == "scale_change":
        byid[params["sensor"]]["resolution"] = params["resolution"]
    elif rtype == "time_window_change":
        for k in ("sampling_period_s", "window_s"):
            if k in params:
                byid[params["sensor"]][k] = params[k]
    elif rtype == "boundary_change":
        byid[params["sensor"]]["reach"] = params["reach"]
        if "penetration" in params:
            byid[params["sensor"]]["penetration"] = params["penetration"]
    elif rtype == "coupling_change":
        c["couplings"][params["key"]] = {**c["couplings"].get(params["key"], {"gain": 1.0, "delay_s": 0.0, "link": True}), **params["coupling"]}
    elif rtype == "body_structure_change":
        c["body_version"] = params["body_version"]
    elif rtype == "variable_added":
        c["variables"] = sorted({*c["variables"], params["variable"]})
    elif rtype == "variable_removed":
        c["variables"] = [v for v in c["variables"] if v != params["variable"]]
    else:
        raise ValueError(f"type must be one of {TYPES}")
    return c


def revise(history: list[dict], specs: list[dict], rtype: str, params: dict, *, reason: str, at: float, initiated_by: str = "researcher", status: str = "recorded", log: list[dict] | None = None,
           sensor_effect: Callable[[dict], dict] | None = None) -> tuple[list[dict], dict]:
    """Make (status ``recorded``) or only evaluate (status ``proposed``) a revision. Returns the history (unchanged for a proposal) and the event."""
    if rtype not in TYPES or status not in ("proposed", "recorded") or initiated_by not in INITIATORS or not reason:
        raise ValueError(f"type in {TYPES}, status proposed or recorded, initiated_by in {INITIATORS}, and a reason are required ('validated' cannot be set here)")
    cur = OB.version_at(history, at)
    new = _apply(cur, rtype, params)
    new.update({"version": history[-1]["version"] + 1, "parent": cur["version"], "at": at, "label": rtype, "change": {"op": rtype, "params": copy.deepcopy(params), "reason": reason}})
    before, after = OB.state_at(history, specs, at), OB.state_at([*history, new], specs, at)
    diff = OB.diff_states(before, after)
    event = {"seq": len(log or []) + 1, "type": rtype, "status": status, "reason": reason, "at": at, "recorded_at": now_iso(), "initiated_by": initiated_by, "autonomous_revision_demonstrated": False,
             "before_version": cur["version"], "after_version": new["version"] if status == "recorded" else None, "body_version_before": cur["body_version"], "body_version_after": new["body_version"],
             "lost": diff["lost"], "gained": diff["gained"], "changed": diff["changed"], "unchanged_count": len(diff["unchanged"]), "params": copy.deepcopy(params),
             "note": "a proposal creates no version and is not a physically executed modification" if status == "proposed" else "the change is recorded as made; its usefulness is not validated here"}
    if log is not None:
        log.append(event)
    return ((list(history) + [new]) if status == "recorded" else list(history)), event


def replay_revisions(history: list[dict], log: list[dict], specs: list[dict]) -> list[dict]:
    """The sequence of recorded revisions with the observation state before and after each, rebuilt from the history (a check that the log and the versions agree)."""
    out = []
    for e in log:
        if e["status"] != "recorded":
            continue
        ver = next((c for c in history if c["version"] == e["after_version"]), None)
        out.append({"event": e["seq"], "type": e["type"], "version_ok": ver is not None and ver["change"]["op"] == e["type"] and ver["parent"] == e["before_version"],
                    "before": OB.state_at(history, specs, e["at"] - 1e-9)["summary"] if e["at"] > history[0]["at"] else None, "after": OB.state_at(history, specs, e["at"])["summary"]})
    return out
