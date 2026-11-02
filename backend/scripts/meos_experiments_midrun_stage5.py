"""Stage 5, experiment L (mid-run actions): runs L1-L3 of xzr/meos/midrun.py and writes docs/ecosystem/experiments_stage5_midrun.json.

    PYTHONPATH=backend python backend/scripts/meos_experiments_midrun_stage5.py        # about 12 minutes on 8 cores

experiments_stage5.json is not touched."""

from __future__ import annotations

import json
import time
from pathlib import Path

from xzr.meos import engine as E
from xzr.meos import midrun as ML

OUT = Path(__file__).resolve().parents[2] / "docs" / "ecosystem" / "experiments_stage5_midrun.json"


def main() -> None:
    t0 = time.time()
    res = ML.run_all()
    res.update({
        "engine": E.ENGINE_VERSION, "experiment": "L: configurations that survive a stress arriving in mid-run, and a controller that uses them",
        "seeds": {"search": list(ML.SEARCH_SEEDS), "validation": list(ML.VALIDATION_SEEDS), "evaluation": [ML.EVAL_SEEDS[0], ML.EVAL_SEEDS[-1]]}, "action_tick": ML.T_ACT, "stress_tick": 100, "horizon": ML.HORIZON,
        "criteria": ML.verdicts.__doc__, "seconds": round(time.time() - t0, 1),
        "limit": "The stresses of the evaluation are the stresses the library was built for (on other seeds): this tests whether an action exists and a controller can find it by sensing, not generalisation to an unseen stress. A formal model.",
    })
    OUT.write_text(json.dumps(res, indent=1))
    print(f"wrote {OUT} in {res['seconds']} s")


if __name__ == "__main__":
    main()
