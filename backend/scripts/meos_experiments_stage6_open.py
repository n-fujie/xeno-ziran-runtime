"""Stage 6 follow-up: the windows that were still effective at tick 330, measured to tick 1140 with the extended horizon (1200).

    PYTHONPATH=backend python backend/scripts/meos_experiments_stage6_open.py [--check-prefix]   # about 30 minutes on 8 cores

Writes docs/ecosystem/experiments_stage6_open_windows.json. ``--check-prefix`` first runs ticks 300-330 and compares them with the saved Stage 6 windows (a run with a longer horizon must agree with the shorter one on those ticks)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from xzr.meos import engine as E
from xzr.meos import repair6 as R
from xzr.meos import stage6_open as O

DOCS = Path(__file__).resolve().parents[2] / "docs" / "ecosystem"
OUT = DOCS / "experiments_stage6_open_windows.json"


def targets() -> list[dict]:
    b = json.loads((DOCS / "experiments_stage6_refine.json").read_text())
    return [w for w in b["B1_windows"] if w["ticks_tested"][1] == 330 and w["latest_effective_tick"] == 330]


def main() -> None:
    t0 = time.time()
    tg = targets()
    print(len(tg), "windows reach tick 330", flush=True)
    if "--check-prefix" in sys.argv:
        bad = 0
        for w in tg:
            x = O.window(w["stress"], [tuple(p) for p in w["parts"]], range(300, 331))
            old = set(t for t in w["effective_ticks"] if t >= 300)
            new = set(x["effective_ticks"])
            print("prefix", w["stress"][:22], w["parts"], "same" if old == new else f"DIFFERENT old-new={sorted(old - new)} new-old={sorted(new - old)}", flush=True)
            bad += old != new
        print("prefix check:", "agrees" if not bad else f"{bad} differ")
        return
    wins = []
    for w in tg:
        x = O.window(w["stress"], [tuple(p) for p in w["parts"]], range(331, O.LAST_TICK + 1))
        wins.append(x)
        print("open window", w["stress"][:22], w["parts"], x["effective_intervals"][-3:], "latest", x["latest_effective_tick"], round(time.time() - t0), "s", flush=True)
    res = {"engine": E.ENGINE_VERSION, "protocol": O.__doc__, "extended_horizon": O.EXTENDED_HORIZON, "last_tick_tested": O.LAST_TICK, "recovery_window": R.W, "seeds": {"exploration": list(R.SEARCH_SEEDS), "validation": list(R.VALIDATION_SEEDS)}, "windows": wins, "seconds": round(time.time() - t0, 1)}
    OUT.write_text(json.dumps(res, indent=0))
    print("wrote", OUT, res["seconds"], "s")


if __name__ == "__main__":
    main()
