"""The matched-rival comparison of the XB-TRO body (R20 18D). Local only.

    PYTHONPATH=. python scripts/gaisho_rival.py viability     # exploration seeds: is the rival a working controller? (baseline and rival on the grid)
    PYTHONPATH=. python scripts/gaisho_rival.py final         # the frozen protocol on the final seeds -> docs/gaisho/experiments_rival.json
    PYTHONPATH=. python scripts/gaisho_rival.py final --singles   # also each Xeno-14 principle alone
    PYTHONPATH=. python scripts/gaisho_rival.py labels        # H-L: label invariance of the records

A simulated planar body only. See xzr/gaisho/rival_experiment.py for what is frozen and what the result does and does not say."""

from __future__ import annotations

import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from xzr.gaisho import rival_experiment as rx
from xzr.xbtro import engine

OUT = Path(__file__).resolve().parents[2] / "docs" / "gaisho" / "experiments_rival.json"


def code_digest() -> str:
    h = hashlib.sha256()
    for name in ("rival.py", "rival_experiment.py"):
        h.update((Path(rx.__file__).with_name(name)).read_bytes())
    h.update(Path(engine.__file__).read_bytes())
    return h.hexdigest()[:16]


def run_pool(names: list[str], seeds: list[int], workers: int) -> dict:
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return dict(ex.map(rx._job, [(n, seeds) for n in names]))


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "viability"
    workers = 4
    if mode == "viability":
        names = ["baseline", "rival (ordinary optimal feedback)"]
        res = run_pool(names, rx.EXPLORATION_SEEDS, 2)
        rec = rx.record(res, rx.EXPLORATION_SEEDS, "viability (exploration seeds; not a result)", code_digest())
        cell0 = {n: res[n]["0|0"]["fell"] for n in names}
        ok = sum(1 for f in cell0["rival (ordinary optimal feedback)"] if f < 0.5) == len(rx.EXPLORATION_SEEDS)
        print(json.dumps(rec["analysis"]["fall_share_by_condition"], indent=1))
        print("cell (0, 0) falls per seed:", cell0)
        print("VIABILITY (rival holds the unperturbed undelayed cell on every exploration seed):", ok)
        return 0 if ok else 1
    if mode == "labels":
        print(json.dumps(rx.label_invariance(rx.EXPLORATION_SEEDS[:4]), indent=1))
        return 0
    if mode == "final":
        names = list(rx.MAIN) + (list(rx.SINGLES) if "--singles" in argv else [])
        res = run_pool(names, rx.FINAL_SEEDS, workers)
        rec = rx.record(res, rx.FINAL_SEEDS, "final", code_digest())
        rec["label_invariance"] = rx.label_invariance(rx.FINAL_SEEDS[:4])
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(rx.dumps(rec))
        print("saved", OUT, rec["record_digest"][:12])
        print(json.dumps(rec["reading"], indent=1))
        print(json.dumps(rec["analysis"]["fall_share_by_condition"], indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
