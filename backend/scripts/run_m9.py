"""Run the M9 confirmatory experiments (protocol docs/LAB_PROTOCOL_M9.md, frozen; the runner refuses otherwise).

    cd backend && PYTHONPATH=. ../.venv/bin/python scripts/run_m9.py [procs] [experiment ...]

Results are written to backend/experiments/results/lab9/<name>.json; an existing published result is never
overwritten. Default order: m9ab m9c m9d m9e m9f m9w m9alt.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RANGE = {"m9w": "worlds"}  # every other experiment uses the confirmatory seeds


def main() -> None:
    from xzr.lab import m9
    procs = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    names = sys.argv[2:] or ["m9ab", "m9c", "m9d", "m9e", "m9f", "m9w", "m9alt"]
    m9.check_protocol()
    for name in names:
        if (m9.RESULTS / f"{name}.json").exists():
            print("exists, skipped", name, flush=True)
            continue
        t = time.time()
        print("===", name, time.strftime("%H:%M:%S"), flush=True)
        doc = m9.run_experiment(name, procs, confirmatory=True, range_name=RANGE.get(name, "confirm"))
        print("written", m9.write(name, doc), round(time.time() - t), "s", flush=True)


if __name__ == "__main__":
    main()
