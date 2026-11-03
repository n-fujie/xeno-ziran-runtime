"""Run EXP-TE01 .. TE06 and save the results to docs/truth_error/experiments.json (the protocol, seeds, observation range, outputs, failure conditions and the negative results are in the file).

    PYTHONPATH=. python scripts/truth_error_experiments.py

Synthetic subjects and institutions only; see xzr/truth_error/__init__.py."""

from __future__ import annotations

import json
from pathlib import Path

from xzr.truth_error import experiments as X

OUT = Path(__file__).resolve().parents[2] / "docs" / "truth_error" / "experiments.json"

if __name__ == "__main__":
    res = X.run_all()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, sort_keys=True))
    for k, v in res["experiments"].items():
        print(
            f"{k:32s} arms={len(v['arms'])} invalid={v['invalid_if_any_failure_condition']} negatives={len(v['negative_results'])}"
        )
    print("written", OUT)
