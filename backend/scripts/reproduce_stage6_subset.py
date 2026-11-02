"""Stage 6 regression: a re-run of parts of the Stage 6 experiments, compared with the saved results (nothing is overwritten). The engine is deterministic: the rows must be identical.

    PYTHONPATH=backend python backend/scripts/reproduce_stage6_subset.py         # about 6 minutes

  - the exploration grid of two stresses (coupling; history lost) against experiments_stage6_raw.jsonl.gz, row by row;
  - the one-tick window of the coupling resource pulse (ticks 101-170) against experiments_stage6_refine.json;
  - the six repair controllers on two stresses, seeds 11-13, against experiments_stage6_controllers_raw.jsonl.gz.
Writes docs/ecosystem/evidence/stage6_reproduction.json."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from xzr.meos import repair6 as R
from xzr.meos import stage6_controllers as C
from xzr.meos import stage6_experiments as S6
from xzr.meos import stage6_refine as RF

DOCS = Path(__file__).resolve().parents[2] / "docs" / "ecosystem"


def main() -> None:
    out: dict = {}
    raw = S6.load_raw()
    key = lambda r: (r["stress"], r["action"], r["magnitude"], r["duration"], r["t"], r["seed"])  # noqa: E731
    saved = {key(r): r for r in raw}
    stresses = ("coupling gain 0.5", "history lost")
    rows = S6.explore(stresses)
    same = sum(1 for r in rows if saved.get(key(r)) == r)
    out["exploration_grid"] = {"stresses": list(stresses), "rows": len(rows), "identical_to_saved": same, "identical": same == len(rows)}
    b = json.loads((DOCS / "experiments_stage6_refine.json").read_text())
    w = RF.window("coupling gain 0.5", [("resource.pulse", 1.0, 0)])
    sw = next(x for x in b["B1_windows"] if x["stress"] == "coupling gain 0.5" and x["parts"] == [["resource.pulse", 1.0, 0]])
    out["window_coupling_pulse_1.0"] = {"effective_intervals_101_170": w["effective_intervals"], "saved_intervals_up_to_330": sw["effective_intervals"], "per_tick_identical": all(sw["per_tick"][t] == v for t, v in w["per_tick"].items()), "identical": all(sw["per_tick"][t] == v for t, v in w["per_tick"].items())}
    ct = json.loads((DOCS / "experiments_stage6_controllers.json").read_text())
    with gzip.open(DOCS / "experiments_stage6_controllers_raw.jsonl.gz", "rt") as f:
        craw = {(r["stress"], r["controller"], r["seed"]): r for r in map(json.loads, f)}
    latest: dict[str, int] = {}
    for v in json.loads((DOCS / "experiments_stage6.json").read_text())["single_settings"]:
        if v["status"] == "validated":
            latest[v["stress"]] = max(latest.get(v["stress"], 0), v["t"])
    lib = ct["library"]
    got = C.run_controllers(lib, [("coupling gain 0.5", R.STRESS_TICK), ("history lost", R.STRESS_TICK)], seeds=(11, 12, 13), latest=latest)
    same_c = sum(1 for r in got if all(craw[(r["stress"], r["controller"], r["seed"])][k] == r[k] for k in ("ok", "outcome", "attempts", "latency", "failure", "selected")))
    out["controllers"] = {"runs": len(got), "identical_to_saved": same_c, "identical": same_c == len(got)}
    out["all_identical"] = all(v["identical"] for v in out.values() if isinstance(v, dict))
    (DOCS / "evidence" / "stage6_reproduction.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: (v if not isinstance(v, dict) else {a: b for a, b in v.items() if a in ("rows", "runs", "identical_to_saved", "identical", "per_tick_identical")}) for k, v in out.items()}, indent=1))


if __name__ == "__main__":
    main()
