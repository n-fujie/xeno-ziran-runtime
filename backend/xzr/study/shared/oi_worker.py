"""JSON-lines worker for the ARDS side of the shared environment: one request per line on stdin, one response per line on stdout.

    {"cmd": "catalog"}                                        -> the catalog
    {"cmd": "capability", "configs": [...]}                   -> capability of each difference under each configuration
    {"cmd": "observe", "req": {...}, "truth": true}            -> an observation (+ the ground truth, evaluation only, when asked)
    {"cmd": "describe"}                                        -> definition digest and thresholds

Run as ``python -m xzr.study.shared.oi_worker`` (``--precompute`` fills the ground-truth cache and exits).
"""

from __future__ import annotations

import json
import sys

from . import oi_world as O


def handle(msg: dict) -> dict:
    cmd = msg["cmd"]
    if cmd == "catalog":
        return {"ok": True, "catalog": O.catalog()}
    if cmd == "describe":
        return {
            "ok": True,
            "env": O.ENV_ID,
            "digest": O.definition_digest(),
            "thresholds": O.THRESHOLDS,
            "definition": O.definition(),
        }
    if cmd == "capability":
        return {"ok": True, "capability": {c["name"]: {d.id: O.capability_of(c, d) for d in O.DIFFS} for c in msg["configs"]}}
    if cmd == "observe":
        out = O.observe(msg["req"])
        if msg.get("truth"):
            out["truth"] = O.truth_of(msg["req"]["preset"], msg["req"]["alteration"])
        return {"ok": True, **out}
    raise ValueError(f"unknown command {cmd!r}")


def main() -> int:
    if "--precompute" in sys.argv:
        for p in O.PRESETS:
            for a in O.ALTERATIONS:
                O.truth_of(p, a)
                print(f"truth {p}/{a} ready", flush=True)
        return 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            resp = handle(json.loads(line))
        except Exception as e:  # noqa: BLE001 - every failure is returned to the caller, never swallowed
            resp = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        sys.stdout.write(json.dumps(resp, allow_nan=False, default=lambda x: None if x != x else float(x)) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
