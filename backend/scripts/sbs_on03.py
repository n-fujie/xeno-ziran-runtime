"""ON-03 fragility transfer on the SBS substrate -> docs/sbs/sbs_on03.json. NEW EXECUTION.

    PYTHONPATH=. python scripts/sbs_on03.py [--worlds 24]      # worlds 301.., four formation couplings (xzr/sbs/on_fragility.py)"""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from xzr.sbs import on_fragility as of
from xzr.sbs.protocol import PROTOCOL_DIGEST

OUT = Path(__file__).resolve().parents[2] / "docs" / "sbs"


def _t(a: tuple[int, float]) -> dict:
    return of.run_design_world(*a)


def main() -> None:
    nw = int(sys.argv[sys.argv.index("--worlds") + 1]) if "--worlds" in sys.argv else 24
    seeds = list(range(301, 301 + nw))
    tasks = list(itertools.product(seeds, of.DESIGNS))
    with ProcessPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(_t, tasks, chunksize=1))
    rows: dict[float, dict[int, dict]] = {e: {} for e in of.DESIGNS}
    for r in res:
        rows[r["eps"]][r["seed"]] = r
    per_design = {}
    for e in of.DESIGNS:
        rs = list(rows[e].values())
        per_design[str(e)] = {
            "formation_largest_share_mean": float(np.mean([r["formation_largest_share"] for r in rs])),
            "energy_per_particle_mean": float(np.mean([r["energy_per_particle"] for r in rs])),
            "performance_overlap_mean": float(np.mean([r["performance_overlap"] for r in rs])),
            "single_group_after_decoupling": int(sum(r["repair"]["single_group"] for r in rs)),
            "steps_to_half_median_all_worlds_unrepaired_as_inf": float(np.median([r["repair"]["steps_to_half"] if r["repair"]["steps_to_half"] is not None else np.inf for r in rs])),
            "load_retention_mean": float(np.mean([r["load_retention"] for r in rs if r["load_retention"] is not None])),
            "mobility_msd_500_mean": float(np.mean([r["mobility_msd_500"] for r in rs])),
        }
    rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=Path(__file__).parent).stdout.strip()
    rec = {"classification": "NEW EXECUTION", "condition": "ON-03 fragility transfer on the SBS substrate; not an ON Lab reproduction", "sbs_protocol_digest": PROTOCOL_DIGEST, "source_revision": rev, "designs_eps": of.DESIGNS, "baseline": of.BASELINE, "seeds": seeds,
           "not_applicable_on_this_substrate": ["communication", "maintenance", "resource dependence", "dependence on external systems", "latency of an external signal"],
           "per_design": per_design, "verdicts_against_baseline": of.verdicts(rows), "pareto": of.pareto(rows), "rows": [rows[e][s] for e in of.DESIGNS for s in seeds], "reproduce": f"PYTHONPATH=. python scripts/sbs_on03.py --worlds {nw}"}
    (OUT / "sbs_on03.json").write_text(json.dumps(rec, indent=1, sort_keys=True, default=float))
    for e, v in per_design.items():
        print(e, {k: round(x, 3) if isinstance(x, float) else x for k, x in v.items()})
    for e, v in rec["verdicts_against_baseline"].items():
        print(e, v["verdict"], "perf", round(v["performance_diff"]["mean"], 3), "| single", round(v["single_group_share_diff"]["mean"], 3), "| load", v["load_retention_diff"]["mean"], "| mech", v["mechanism_a_present"], v["mechanism_b_present"], v["mechanism_anneal_b"])
    print("pareto", rec["pareto"]["retained_non_dominated"], rec["pareto"]["dominated_by"])


if __name__ == "__main__":
    main()
