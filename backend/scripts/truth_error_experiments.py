"""Run EXP-TE01 .. TE14 and save the results (the protocol, seeds, observation range, outputs, failure conditions and the negative results are in the files):
phase 1 (TE01-TE06) -> docs/truth_error/experiments.json, phase 2 (TE07-TE14, with the replication on seeds 21..40) -> docs/truth_error/experiments2.json.

    PYTHONPATH=. python scripts/truth_error_experiments.py            # both
    PYTHONPATH=. python scripts/truth_error_experiments.py phase2     # phase 2 only (phase 1 is saved and tested against its digests)

Synthetic subjects and institutions only; see xzr/truth_error/__init__.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from xzr.truth_error import experiments as X
from xzr.truth_error import experiments2 as X2

DOCS = Path(__file__).resolve().parents[2] / "docs" / "truth_error"
OUT, OUT2, OUT3 = DOCS / "experiments.json", DOCS / "experiments2.json", DOCS / "appeal_trace.json"


def slim(res: dict) -> dict:
    """keep per-seed values only for the primary and the contrast outcomes (the rest is in each arm's mean and paired summary)"""
    for e in res["experiments"].values():
        keep = set(e["primary_outcomes"]) | {c["outcome"] for c in e.get("contrasts", [])}
        for arm in e["arms"]:
            arm["values"] = {k: v for k, v in arm["values"].items() if k in keep}
    return res


if __name__ == "__main__":
    only2 = "phase2" in sys.argv[1:]
    DOCS.mkdir(parents=True, exist_ok=True)
    if not only2:
        res = X.run_all()
        OUT.write_text(json.dumps(res, indent=1, sort_keys=True))
        for k, v in res["experiments"].items():
            print(f"{k:32s} arms={len(v['arms'])} invalid={v['invalid_if_any_failure_condition']} negatives={len(v['negative_results'])}")
        print("written", OUT)
    res2 = slim(X2.run_all2())
    OUT2.write_text(json.dumps(res2, indent=1, sort_keys=True))
    for k, v in res2["experiments"].items():
        print(f"{k:24s} arms={len(v['arms'])} invalid={v['invalid_if_any_failure_condition']} replication={v['replication']['counts']}")
    print("written", OUT2)
    OUT3.write_text(json.dumps(X2.appeal_trace(), indent=1, sort_keys=True))
    print("written", OUT3)
