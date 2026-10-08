"""Resolution-escalation experiments.

    python experiments/run_escalation.py matrix        # the resolution matrix (hours)
    python experiments/run_escalation.py <study>       # disconnection | triggers | compression | adaptivity | clusters

Results: backend/experiments/results/resolution/<study>.json (resumable).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xzr.experiments.escalation.harness import RESULTS  # noqa: E402


def main() -> None:
    what = sys.argv[1] if len(sys.argv) > 1 else "matrix"
    procs = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    if what == "matrix":
        from xzr.experiments.escalation.matrix import design
        from xzr.experiments.escalation.runner import run_conditions
        conds, omitted = design()
        run_conditions(conds, RESULTS / "matrix.json", procs, meta={"omitted": omitted, "conditions": len(conds)})
    else:
        import importlib
        mod = importlib.import_module(f"xzr.experiments.escalation.{what}")
        mod.main(procs)


if __name__ == "__main__":
    main()
