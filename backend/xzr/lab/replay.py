"""Independent replay: re-execute a recorded laboratory run from its configuration alone and compare.

Agreement is required, step by step, on the runtime fingerprint, the apparatus-state digest and the full apparatus
state, and on the event list (type, place, step, values, provenance). The reproducibility condition is the one
documented for the runtime: same machine, same software versions (docs/REPRODUCIBILITY.md); across platforms the
address hierarchy can differ and agreement is not expected.
"""

from __future__ import annotations

import json
from pathlib import Path

from .record import SCHEMA, SCHEMA_V2, LabRun


def replay(record: dict) -> dict:
    if record.get("schema") not in (SCHEMA, SCHEMA_V2):
        raise ValueError(f"not an {SCHEMA} / {SCHEMA_V2} record")
    # re-execute exactly as many steps as were recorded (a stopped live run is a prefix of its horizon)
    r = LabRun(record["config"])
    for _ in range(len(record["steps"])):
        r.step()
    again = r.record()
    mism = []
    for a, b in zip(record["steps"], again["steps"], strict=False):
        for k in ("fingerprint", "digest", "shutter", "activity", "memory", "conduits", "physics", "science"):
            if a.get(k) != b.get(k):
                mism.append({"t": a["t"], "field": k})
                break
    if len(record["steps"]) != len(again["steps"]):
        mism.append({"t": None, "field": "length"})
    # records written before a field existed (e.g. physical_events, added with the physical laboratory) lack it: an
    # absent optional list means "none recorded"
    ev_same = all(json.dumps(record.get(k) or [], sort_keys=True) == json.dumps(again.get(k) or [], sort_keys=True)
                  for k in ("events", "physical_events", "science_events"))
    return {"steps": len(record["steps"]), "mismatched_steps": len(mism), "first_mismatches": mism[:5],
            "events_identical": ev_same, "agreement": not mism and ev_same,
            "condition": "same machine and software versions"}


def replay_file(path: str | Path) -> dict:
    return replay(json.loads(Path(path).read_text()))
