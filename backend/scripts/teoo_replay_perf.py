"""Replay of the observation state: before / after. Run: PYTHONPATH=. python scripts/teoo_replay_perf.py out.json

"Before" is the first implementation (kept unchanged as ``reference_state_at`` in tests/test_teoo_observation.py), "after" is ``xzr.teoo.observation.replay``. Each repetition runs both on the same world, in alternating
order, so that the comparison is paired. Every repetition also checks that the two reconstruct exactly the same states. SYNTHETIC worlds, this machine, wall clock, one process; no MEOS or Stage 6 result is involved.
Percentiles over a few repetitions are order statistics of those repetitions (the largest condition has 3), and are reported as such.
"""

from __future__ import annotations

import json
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from test_teoo_observation import reference_state_at  # noqa: E402

from xzr.teoo import observation as OB  # noqa: E402

CONDITIONS = [  # targets, sensors, time points, repetitions, whether every version changes a sensor of the (single) channel (the worst case for reuse between versions)
    (7, 4, 21, 15, False), (50, 5, 21, 15, False), (200, 20, 21, 7, False), (1000, 100, 21, 3, False), (200, 20, 201, 5, False),
    (200, 20, 21, 7, True), (1000, 100, 21, 3, True),
]


def world(n_targets: int, n_sensors: int, vary: bool = False):
    sensors = [OB.sensor(f"s{k}", ["angle"], resolution=1.0, sampling_period_s=0.02, window_s=20.0, detection_limit=0.1, penetration=0.5, health=1.0 if k % 7 else 0.5, cost_per_s=0.1) for k in range(n_sensors)]
    specs = [OB.target_spec(f"tg{k}", "angle", scale=2.0, phenomenon_period_s=2.0 if k % 5 else 0.01, amplitude=10.0, opacity=(k % 10) / 10) for k in range(n_targets)]
    hist = []
    for k in range(4):
        sv = [{**x, "detection_limit": 0.1 + 0.01 * k} if (vary and i == 0) else x for i, x in enumerate(sensors)]
        hist.append(OB.new_configuration(sv, resources={"energy_budget": 400.0}, at=float(k * 6), body_version=1))
    return hist, specs


def pct(xs: list[float], q: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, max(0, round(q * (len(s) - 1))))]


def main() -> None:
    out = {"machine": {"platform": platform.platform(), "python": platform.python_version()}, "conditions": []}
    for n_t, n_s, n_times, reps, vary in CONDITIONS:
        hist, specs = world(n_t, n_s, vary)
        times = [float(x) * (24.0 / max(1, n_times - 1)) for x in range(n_times)]
        ref_s, fast_s, same = [], [], True
        cache = OB._Cache()
        for r in range(reps):
            order = ("ref", "fast") if r % 2 == 0 else ("fast", "ref")
            res = {}
            for which in order:
                t0 = time.perf_counter()
                if which == "ref":
                    res[which] = [reference_state_at(hist, specs, t) for t in times]
                    ref_s.append(time.perf_counter() - t0)
                else:
                    cache = OB._Cache()
                    res[which] = OB.replay(hist, specs, times, _cache=cache)
                    fast_s.append(time.perf_counter() - t0)
            same = same and res["ref"] == res["fast"]
        tracemalloc.start()
        OB.replay(hist, specs, times)
        peak_fast = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        tracemalloc.start()
        [reference_state_at(hist, specs, t) for t in times]
        peak_ref = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        ratios = [a / b for a, b in zip(ref_s, fast_s, strict=True)]
        row = {"targets": n_t, "sensors": n_s, "time_points": n_times, "time_span_s": times[-1], "versions": len(hist), "repetitions": reps, "every_version_changes_a_sensor": vary, "dataset_size_target_sensor_time": n_t * n_s * n_times,
               "identical_states": same, "cache": {"served_again_same_version": cache.hits, "reused_from_earlier_version": cache.reused, "computed": cache.misses, "computed_fraction": round(cache.misses / max(1, cache.hits + cache.reused + cache.misses), 4)},
               "before_s": {"p50": round(statistics.median(ref_s), 4), "p95": round(pct(ref_s, .95), 4), "p99": round(pct(ref_s, .99), 4), "min": round(min(ref_s), 4), "max": round(max(ref_s), 4)},
               "after_s": {"p50": round(statistics.median(fast_s), 4), "p95": round(pct(fast_s, .95), 4), "p99": round(pct(fast_s, .99), 4), "min": round(min(fast_s), 4), "max": round(max(fast_s), 4)},
               "speedup_paired": {"median": round(statistics.median(ratios), 2), "min": round(min(ratios), 2), "max": round(max(ratios), 2)},
               "peak_python_memory_mb": {"before": round(peak_ref / 2**20, 1), "after": round(peak_fast / 2**20, 1)}}
        out["conditions"].append(row)
        print(json.dumps(row), flush=True)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
