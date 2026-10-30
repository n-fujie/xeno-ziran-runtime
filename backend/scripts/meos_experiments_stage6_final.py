"""Stage 6, the derived reading: the stress-by-stress table, timing windows, latest successful and earliest irreversible ticks, the resource non-monotonicity bands, the controllers' failure ids.

    PYTHONPATH=backend python backend/scripts/meos_experiments_stage6_final.py

Reads experiments_stage6.json, _refine.json, _cross.json, _controllers.json; writes experiments_stage6_final.json. Nothing is typed in: see xzr/meos/stage6_final.py."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from xzr.meos import repair6 as R
from xzr.meos import stage6_final as F

DOCS = Path(__file__).resolve().parents[2] / "docs" / "ecosystem"


def main() -> None:
    a, b = (json.loads((DOCS / f"experiments_stage6{n}.json").read_text()) for n in ("", "_refine"))
    c = json.loads((DOCS / "experiments_stage6_cross.json").read_text())
    ctl = json.loads((DOCS / "experiments_stage6_controllers.json").read_text())
    out = F.build(a, b, c, ctl)
    # the controllers' failures under the stage 6 taxonomy ids
    for s in ctl["summary"]:
        s["failure_ids"] = {R.failure_id(k): v for k, v in s["failures"].items()}
    out["controller_failure_ids"] = {f"{s['stress']} | {s['controller']}": s["failure_ids"] for s in ctl["summary"] if s["failure_ids"]}
    out["counts"] = {"stresses": len(out["stress_table"]), "windows": len(b["B1_windows"])}
    (DOCS / "experiments_stage6_final.json").write_text(json.dumps(out, indent=0))
    # the same results as CSV: one row per stress (the table) and one row per cell of the exploration grid, whatever its outcome (effective, near miss, failed, undetermined): nothing is listed only if it worked
    with (DOCS / "experiments_stage6_results_table.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["stress", "classification_at_decision_tick_113", "classification_at_any_tested_tick", "internal_windows", "world_single_windows", "combined_windows", "latest_successful_repair_tick", "irreversible_tick", "irreversibility", "tested_range_end", "unrepaired_collapse_tick", "flags"])
        for r in out["stress_table"]:
            w.writerow([r["stress"], r["classification_at_decision_tick_113"], r["classification_at_any_tested_tick"], json.dumps(r["internal_reconfiguration"]["windows"]), json.dumps(r["world_single"]["windows"]), json.dumps(r["combined"]["windows"]),
                        r["latest_successful_repair_tick"] if r["latest_successful_repair_tick"] is not None else "", r["irreversible_tick"] if r["irreversible_tick"] is not None else "", r["irreversibility"], r["tested_range_end"] or "", r["unrepaired_collapse_tick"], "; ".join(r["flags"])])
    with (DOCS / "experiments_stage6_cells.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["stress", "action", "magnitude", "duration", "tick", "seeds", "effective_seeds", "short_ok", "medium_ok", "long_ok", "secondary_collapse", "failure_id", "status"])
        for r in a["table"]:
            w.writerow([r["stress"], r["action"], r["magnitude"], r["duration"], r["t"], r["n"], r["effective_seeds"], r["short"], r["medium"], r["long"], r["secondary_collapse"], R.failure_id(r["failure"]) or "", "effective" if r["effective_seeds"] == r["n"] else "partial" if r["effective_seeds"] else "not effective"])
    print("wrote experiments_stage6_final.json")
    for r in out["stress_table"]:
        print(f"{r['stress'][:26]:26} | {r['classification_at_decision_tick_113'][:26]:26} | any: {r['classification_at_any_tested_tick'][:26]:26} | fragments {r['timing_window_fragments']} | latest {r['latest_successful_repair_tick']} | irreversible {r['irreversible_tick']} | collapse {r['unrepaired_collapse_tick']} | flags {r['flags']}")


if __name__ == "__main__":
    main()
