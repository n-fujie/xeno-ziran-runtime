"""Observation Mapping: which observation targets of a body have records, and what those records say about them.

The answer for a target is never 'nothing there': no record refers to it -> UNMEASURED ("not observed", which is not "absent"); records refer to it -> the sample
statuses, the causes, the provenance classes of the records (a MEASURED and a SYNTHETIC record are never merged into one reading), the time range and the record
ids. ``display_class`` is what a view colours by, derived from the provenance of the records and their kind, never from a value."""

from __future__ import annotations

from .body import Body

DISPLAY = ("measured", "synthetic", "estimated", "conceptual", "unmeasured", "limited")


def _channels(records: list[dict]) -> list[tuple[dict, dict]]:
    return [(r, ch) for r in records for ch in r.get("payload", {}).get("channels", [])]


def target_state(body: Body, target_id: str, records: list[dict], version: int | None = None) -> dict:
    v = body.at(version) if version else body.current
    t = next((x for x in v["targets"] if x["id"] == target_id), None)
    if t is None:
        raise KeyError(target_id)
    mine = [(r, ch) for r, ch in _channels(records) if ch.get("target") == target_id and r["payload"].get("body", {}).get("id") in (None, body.id)]
    if not mine:
        return {"target": target_id, "ref": t["ref"], "variables": t["variables"], "display_class": "unmeasured", "state": "UNMEASURED", "records": [], "classes": [], "counts": {}, "causes": [],
                "note": "no record refers to this target: it was not observed, which is not the same as being absent"}
    counts: dict[str, int] = {}
    causes: set[str] = set()
    for _, ch in mine:
        for s in ch["samples"]:
            counts[s["status"]] = counts.get(s["status"], 0) + 1
            causes.update(s.get("causes", []))
    classes = sorted({r["provenance"] for r, _ in mine})
    kinds = sorted({r["kind"] for r, _ in mine})
    valid = counts.get("MEASURED_VALID", 0)
    if valid == 0:
        disp, state = "limited", "NO_VALID_SAMPLE"
    elif "MEASURED" in classes:
        disp, state = "measured", "OBSERVED"
    elif "SYNTHETIC" in classes and not ({"ESTIMATE", "RECONSTRUCTION"} & set(kinds)):
        disp, state = "synthetic", "OBSERVED_SYNTHETIC"
    elif "RECONSTRUCTED_ESTIMATE" in classes or {"ESTIMATE", "RECONSTRUCTION"} & set(kinds):
        disp, state = "estimated", "ESTIMATED"
    else:
        disp, state = "conceptual", "CONCEPTUAL"
    times = [x for _, ch in mine for x in ch["times"]]
    return {"target": target_id, "ref": t["ref"], "variables": t["variables"], "display_class": disp, "state": state, "records": sorted({r["record_id"] for r, _ in mine}), "classes": classes, "kinds": kinds,
            "counts": counts, "causes": sorted(causes), "device_time_range_s": [min(times), max(times)] if times else None, "mixed_classes": len(classes) > 1}


def coverage(body: Body, records: list[dict], version: int | None = None) -> dict:
    v = body.at(version) if version else body.current
    states = {t["id"]: target_state(body, t["id"], records, v["version"]) for t in v["targets"]}
    by_ref: dict[str, str] = {}
    for st in states.values():
        by_ref[st["ref"]] = st["display_class"]
    return {"body": body.id, "version": v["version"], "targets": states, "by_ref": by_ref,
            "unmeasured_refs": sorted(({c["id"] for c in v["components"]} | {r["id"] for r in v["relations"]}) - set(by_ref)), "summary": {d: sum(1 for s in states.values() if s["display_class"] == d) for d in DISPLAY}}
