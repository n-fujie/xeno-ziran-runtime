"""ON-02 persistence criteria on the SBS substrate -> docs/sbs/sbs_on02.json (worlds 1..32 and the five branches of xzr/sbs/on_persistence.py). NEW EXECUTION.

    PYTHONPATH=. python scripts/sbs_on02.py"""

from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from xzr.sbs import on_persistence as op
from xzr.sbs.protocol import PROTOCOL_DIGEST

OUT = Path(__file__).resolve().parents[2] / "docs" / "sbs"


def main() -> None:
    seeds = list(range(1, 33))
    with ProcessPoolExecutor(max_workers=6) as ex:
        worlds = list(ex.map(op.run_world, seeds))
    cells = [c for w in worlds for c in op.read_world(w)]
    by_branch: dict[str, list] = defaultdict(list)
    for c in cells:
        by_branch[f"{c['kind']}:{c['level']}"].append(c)
    summary = {}
    for key, cs in by_branch.items():
        n = len(cs)
        summary[key] = {
            "n_worlds": n,
            "persists_count": {k: sum(bool(c["persists"][k]) for c in cs if c["persists"][k] is not None) for k in cs[0]["persists"]},
            "functional_defined_in": sum(c["persists"]["functional_dependency_at_end"] is not None for c in cs),
            "repair_status": {s: sum(c["repair"]["status"] == s for c in cs) for s in ("never_lost_cohesion", "repaired", "not_repaired_within_recovery")},
            "repair_steps_median_among_repaired": float(np.median([c["repair"]["steps_after_end_of_intervention"] for c in cs if c["repair"]["status"] == "repaired"])) if any(c["repair"]["status"] == "repaired" for c in cs) else None,
            "shape_without_membership_at_end": sum(c["shape_without_membership_at_end"] for c in cs),
        }
    rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=Path(__file__).parent).stdout.strip()
    rec = {"classification": "NEW EXECUTION", "condition": "ON-02 persistence criteria kept apart, on the SBS substrate; not an ON Lab reproduction", "protocol_digest": PROTOCOL_DIGEST, "source_revision": rev, "conventions": op.CONVENTIONS,
           "not_applicable_on_this_substrate": ["task performance (no task)", "resource access (no resources)", "technical lineage (no producers or copies)"],
           "seeds": seeds, "summary_by_branch": summary, "disagreements_all_cells": op.disagreements(cells), "cells": cells, "reproduce": "PYTHONPATH=. python scripts/sbs_on02.py"}
    (OUT / "sbs_on02.json").write_text(json.dumps(rec, indent=1, sort_keys=True, default=float))
    for k, v in summary.items():
        print(k, v["persists_count"], v["repair_status"], "shape-w/o-membership", v["shape_without_membership_at_end"])
    for k, v in rec["disagreements_all_cells"].items():
        print(k, v)


if __name__ == "__main__":
    main()
