"""Multi-run capacity on the production experiment path (temporary harness).

    python bench_pool.py OUT.jsonl N HORIZON SEEDS WORKERS...

Runs the same seed jobs (xzr.experiments.escalation.harness.seed_job: reference C, noise replicate C~ and
variants A, E, H) with each worker count, in a ProcessPoolExecutor exactly as runner.run_conditions does. Records
wall time, jobs/s, summed RSS of the pool's workers (sampled), and a SHA-256 of every job's pickled result, so
determinism across worker counts can be checked.
"""
import hashlib
import json
import pickle
import subprocess
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, "/Users/user/Desktop/BIM/xeno-ziran-runtime/backend")

from xzr.experiments.escalation.harness import RESULTS, calibrations, condition, seed_job  # noqa: E402

HERE = Path(__file__).parent


TIMING = {"build_s", "loop_ms_per_step", "ms_per_step"}  # wall-clock self-measurements, not simulation content


def _strip_timing(x):
    if isinstance(x, dict):
        return {k: _strip_timing(v) for k, v in x.items() if k not in TIMING}
    if isinstance(x, list):
        return [_strip_timing(v) for v in x]
    return x


def tree_rss_mb(pid: int) -> float:
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss="], capture_output=True, text=True).stdout
    rows = [tuple(int(x) for x in line.split()) for line in out.splitlines() if line.strip()]
    kids = {p for p, pp, _ in rows if pp == pid}
    return sum(r for p, _, r in rows if p in kids or p == pid) / 1024


def main() -> None:
    out, n, h, seeds = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    workers = [int(x) for x in sys.argv[5:]]
    c = condition(id="pool", n=n, horizon=h, seeds=seeds, variants=("A", "C", "E", "H"))
    gains = calibrations([c], 1, HERE / "calibration-private.json", RESULTS / "calibration.json")
    import os
    for w in workers:
        peak = [0.0]
        stop = threading.Event()

        def sampler() -> None:
            while not stop.is_set():
                peak[0] = max(peak[0], tree_rss_mb(os.getpid()))
                time.sleep(0.5)

        th = threading.Thread(target=sampler, daemon=True)
        th.start()
        t0 = time.time()
        hashes: dict[int, str] = {}
        sizes: dict[int, int] = {}
        failures = []
        with ProcessPoolExecutor(w) as ex:
            futs = {ex.submit(seed_job, (c, 100 + k, gains)): 100 + k for k in range(seeds)}
            for f in as_completed(futs):
                s = futs[f]
                try:
                    r = f.result()
                    b = pickle.dumps(_strip_timing(r), protocol=5)
                    hashes[s] = hashlib.sha256(b).hexdigest()[:16]
                    sizes[s] = len(b)
                except Exception as e:  # noqa: BLE001
                    failures.append({"seed": s, "error": repr(e)[:300]})
        wall = time.time() - t0
        stop.set()
        th.join()
        rec = {"n": n, "horizon": h, "seeds": seeds, "workers": w, "wall_s": round(wall, 2),
               "jobs_per_hour": round(3600 * seeds / wall, 1), "peak_tree_rss_mb": round(peak[0], 1),
               "result_hashes": dict(sorted(hashes.items())), "result_bytes_mean": int(sum(sizes.values()) / max(1, len(sizes))),
               "failures": failures}
        with open(out, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(json.dumps({k: rec[k] for k in ("workers", "wall_s", "jobs_per_hour", "peak_tree_rss_mb", "result_bytes_mean",
                                              "failures")}), flush=True)


if __name__ == "__main__":
    main()
