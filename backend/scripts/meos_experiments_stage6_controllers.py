"""Stage 6, repair controllers: the library, six controllers on the stresses of the library, on unknown variations of them, and on a run with no stress (false positives).

    PYTHONPATH=backend python backend/scripts/meos_experiments_stage6_controllers.py     # needs experiments_stage6.json

Writes docs/ecosystem/experiments_stage6_controllers.json and experiments_stage6_controllers_raw.jsonl.gz. Library: seeds 1-10 only; evaluation: seeds 11-30."""

from __future__ import annotations

import gzip
import json
import time
from pathlib import Path

from xzr.meos import repair6 as R
from xzr.meos import stage6_controllers as C

DOCS = Path(__file__).resolve().parents[2] / "docs" / "ecosystem"


def main() -> None:
    t0 = time.time()
    res = json.loads((DOCS / "experiments_stage6.json").read_text())
    lib, sigs = C.build_library(res)
    latest: dict[str, int] = {}
    for v in res["single_settings"]:
        if v["status"] == "validated":
            latest[v["stress"]] = max(latest.get(v["stress"], 0), v["t"])
    for v in res["combined_settings"]:
        if v["status"] == "validated" and v.get("synergistic"):
            latest[v["stress"]] = max(latest.get(v["stress"], 0), v["t"])
    known = [(sid, R.STRESS_TICK) for sid in R.STRESS_ORDER]
    unknown = [(i, o) for i, s, o, _ in C.unknown_stresses()]
    rows = C.run_controllers(lib, [*known, ("no stress", R.STRESS_TICK), *unknown], latest=latest)
    with gzip.open(DOCS / "experiments_stage6_controllers_raw.jsonl.gz", "wt") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    summary = C.summarise(rows)
    out = {
        "seeds": {"library": "exploration 1-5 and validation 6-10", "evaluation": [R.EVAL_SEEDS[0], R.EVAL_SEEDS[-1]]}, "controllers": list(C.KINDS), "signatures": {k: v for k, v in sigs.items()}, "library": lib, "failure_classes": list(C.FAILURE_CLASSES),
        "summary": summary, "verdicts_known": C.verdicts(summary, [s for s, _ in known]), "verdicts_unknown": C.verdicts(summary, [s for s, _ in unknown]),
        "unknown_stresses": [{"id": i, "varies": w, "onset": o} for i, s, o, w in C.unknown_stresses()],
        "false_positives": [s for s in summary if s["stress"] == "no stress"], "criteria": C.__doc__, "seconds": round(time.time() - t0, 1),
        "limit": "The library holds the settings validated at the default action tick for the six stresses; the unknown stresses are variations of them. A formal model; a result here is about these controllers and this library.",
    }
    (DOCS / "experiments_stage6_controllers.json").write_text(json.dumps(out, indent=0))
    print(f"wrote in {out['seconds']} s; library {len(lib)} plans")
    for v in out["verdicts_known"]:
        print(v["stress"][:24], v["controller"], v["success"], "vs", v["none"], v["verdict"])


if __name__ == "__main__":
    main()
