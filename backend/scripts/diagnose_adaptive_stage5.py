"""Why the adaptive controller did not act (Stage 5, experiment I, a diagnosis of its own log).

    PYTHONPATH=backend python backend/scripts/diagnose_adaptive_stage5.py

For every scenario of experiment I and seeds 1-10 the adaptive controller is run exactly as ``POST /api/meos/reconfigure`` runs it and the outcome of each of its decisions is tallied from its own log.
Writes docs/ecosystem/experiments_stage5_adaptive_diagnosis.json. Nothing in experiments_stage5.json is changed."""

from __future__ import annotations

import collections
import copy
import json
from pathlib import Path

from xzr.meos import mfs5 as M5
from xzr.meos import reconf as RC
from xzr.meos import stage5_experiments as X5
from xzr.service import meos as SVC

OUT = Path(__file__).resolve().parents[2] / "docs" / "ecosystem" / "experiments_stage5_adaptive_diagnosis.json"
SEEDS = tuple(range(1, 11))


def kind(e: dict) -> str:
    o = e.get("outcome", "")
    return "already wholly enabled (cost 0, no action)" if o.startswith("no switch") else "no known route" if o.startswith("no known") else "switch"


def main() -> None:
    ex = SVC._stage5()
    library = RC.library_from(ex["F"]["by_condition"])
    arrangement = {"tap": M5.M2_BASE, "tap_feature": "direct", "universe": M5.COMPONENTS5}
    rows = []
    for scen in X5.SCENARIOS:
        if scen.startswith("no stress"):
            continue
        decisions: collections.Counter = collections.Counter()
        first: collections.Counter = collections.Counter()
        switches = 0
        for seed in SEEDS:
            cfg = SVC._config({"config": {"seed": seed, "horizon": 300}})
            ivs = [{"tick": 0, "op": "ROUTE", "m2": {"sense": "none"}}, *copy.deepcopy(X5.SCENARIOS[scen][0])]
            rec = RC.run_controlled(cfg, ivs, RC.Controller("adaptive", library, arrangement, noise=0.05, seed=seed))
            log = rec["controller"]["log"]
            dec = [e for e in log if e["kind"] == "decide"]
            for e in dec:
                decisions[kind(e)] += 1
            first[kind(dec[0]) if dec else "no decision"] += 1
            switches += sum(1 for e in log if e["kind"] == "switch")
        rows.append({"scenario": scen, "seeds": list(SEEDS), "decisions": dict(decisions), "first_decision": dict(first), "switches": switches})
    OUT.write_text(json.dumps({
        "what": "outcome of every decision of the adaptive controller, from its own log, 10 seeds per scenario",
        "rows": rows,
        "reading": "In every scenario but 'renewal disabled' the controller's first decision, in all 10 seeds, was that the matched MFS is already wholly enabled (cost 0): the library holds sets that suffice when everything else is removed at tick 0, and the full arrangement already contains them, so the controller has nothing to enable and does not act while the run collapses. "
                   "Only the fixed fallback adds a component that is in no MFS of the condition (the M2 tap). The library certifies configurations sustained from the start of a condition, not the passage through a stress in mid-run.",
        "limit": "A statement about this controller and this library. It is not a finding that reconfiguration cannot help.",
    }, indent=1))
    print(json.dumps(rows, indent=1)[:1500])


if __name__ == "__main__":
    main()
