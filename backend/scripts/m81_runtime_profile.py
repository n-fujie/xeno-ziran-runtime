"""Server-side cost of one live laboratory step (preset `systems`), split by part. Read-only timing wrappers.

Usage: cd backend && PYTHONPATH=. python scripts/m81_runtime_profile.py [steps]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    from xzr.lab import live, physics, science
    from xzr.lab.record import LabRun
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    acc: dict[str, list[float]] = {}

    def timed(obj, name, key):
        f = getattr(obj, name)

        def w(*a, **k):
            t0 = time.perf_counter()
            try:
                return f(*a, **k)
            finally:
                acc.setdefault(key, [0.0])[-1] += time.perf_counter() - t0
        setattr(obj, name, w)

    timed(physics.PhysicalLab, "step", "mujoco + transfers (physics.step)")
    timed(science.Science, "decide", "system decisions (science.decide)")
    timed(science.Science, "_true_effect", "harness true effect (counterfactual fork)")
    timed(science.Science, "observe_outcomes", "outcome observation")
    cfg = {**live.PRESETS["systems"], "gen_seed": 8000, "seed": 80000}
    r = LabRun(cfg)
    timed(r.w, "step", "runtime step (world.step)")
    per_step = []
    for _ in range(steps):
        for v in acc.values():
            v.append(0.0)
        t0 = time.perf_counter()
        out = r.step()
        json.dumps(out, separators=(",", ":"))  # what the stream serialises per step
        per_step.append(time.perf_counter() - t0)
    ms = lambda a: {"mean": round(1000 * float(np.mean(a)), 3), "p95": round(1000 * float(np.percentile(a, 95)), 3),  # noqa: E731
                    "p99": round(1000 * float(np.percentile(a, 99)), 3)}
    res = {"steps": steps, "step_total_incl_serialisation_ms": ms(per_step),
           "parts_ms": {k: ms(v[1:]) for k, v in acc.items()}}
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
