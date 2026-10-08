"""Re-derive every condition of a result file from its persisted seed jobs with the current analysis code (no
simulation is rerun). Used so that all conditions of the matrix are classified by one analysis version.

    python -m xzr.experiments.escalation.reanalyse matrix [disconnection ...]
"""

from __future__ import annotations

import json
import sys
import time

from .harness import RESULTS
from .runner import SEED0, analyse_condition, load_jobs, provenance


def _one(args: tuple) -> tuple[str, dict | None]:
    name, cid, cond, run_prov, prov, exclude_name = args
    path = RESULTS / f"{name}.json"
    c = dict(cond)
    for k in ("variants", "revert", "triggers", "world_schedule"):
        if isinstance(c.get(k), list):
            c[k] = tuple(c[k])
    jobs = load_jobs(path, cid)
    if len(jobs) < c["seeds"]:
        return cid, None
    res = [jobs[SEED0 + k] for k in range(c["seeds"])]
    return cid, analyse_condition(c, res, _exclude(exclude_name), path, {**prov, "run": run_prov}, time.time())


def _exclude(name: str | None):
    if name == "disconnection":
        from .disconnection import OWN
        return lambda c, own=OWN: own
    if name == "topology_triggers":
        from .topology_triggers import OWN as OWN2
        return lambda c, own=OWN2: own
    return None


def reanalyse(name: str, procs: int = 4) -> dict:
    from concurrent.futures import ProcessPoolExecutor
    path = RESULTS / f"{name}.json"
    doc = json.loads(path.read_text())
    prov = {**provenance(), "reanalysed": True}
    args = [(name, cid, a["condition"], a.get("provenance", {}), prov,
             name if name in ("disconnection", "topology_triggers") else None)
            for cid, a in doc["conditions"].items()]
    # heaviest first (seed count × world size)
    args.sort(key=lambda x: -x[2]["seeds"] * x[2]["n"])
    missing = []
    with ProcessPoolExecutor(procs) as ex:
        for cid, new in ex.map(_one, args):
            if new is None:
                missing.append(cid)
            else:
                doc["conditions"][cid] = new
            print(f"reanalysed {cid}", flush=True)
    doc.setdefault("meta", {})["reanalysis"] = {**prov, "missing_jobs": missing}
    path.write_text(json.dumps(doc))
    return {"conditions": len(doc["conditions"]), "missing_jobs": missing}


def main() -> None:
    for name in sys.argv[1:] or ["matrix"]:
        print(name, reanalyse(name))


if __name__ == "__main__":
    main()
