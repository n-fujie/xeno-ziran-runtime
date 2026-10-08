"""One benchmark measurement in its own process (temporary harness; not part of the repository).

    python bench_one.py MODE N STEPS SEED [CHECKPOINT_EVERY]

MODE:
  engine     Engine.step only (runtime), world from xzr.runtime.generator.latent_geometric
  detector   Engine.step + ShapeDetector.observe every step (graph descriptors every 10 steps) — the path used by
             interactive sessions (xzr/service/session.py) and xzr/experiments/runs.py
  harness    xzr.experiments.escalation.harness.run(condition, "C", seed, gains) — one reference run of the
             experiment harness (reasoning layer, 5-resolution frames), as used by `xzr run` / `xzr study`

Prints one JSON line: init/step/final timings, steps/s per segment (early/middle/late), RSS samples, peak RSS
(ru_maxrss), edge counts, fingerprint.
"""
import json
import os
import resource
import sys
import time

sys.path.insert(0, "/Users/user/Desktop/BIM/xeno-ziran-runtime/backend")


def rss_mb() -> float:
    import subprocess
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())], capture_output=True, text=True).stdout
    return int(out.strip() or 0) / 1024


def main() -> None:
    mode, n, steps, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    ckpt = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    import numpy as np
    out: dict = {"mode": mode, "n": n, "steps": steps, "seed": seed, "checkpoint_every": ckpt}
    t0 = time.perf_counter()
    if mode in ("engine", "detector"):
        from xzr.lod.hierarchy import build_hierarchy, symmetric_adjacency
        from xzr.runtime.engine import Engine
        from xzr.runtime.generator import latent_geometric
        g = latent_geometric(n, 3)
        st = g.state
        t1 = time.perf_counter()
        out["init_generate_s"] = round(t1 - t0, 3)
        h = None
        if mode == "detector":
            m = st.alive
            h = build_hierarchy(symmetric_adjacency(st.src[m], st.dst[m], st.n))
        out["init_hierarchy_s"] = round(time.perf_counter() - t1, 3)
        out["edges_alive_initial"] = int(st.alive.sum())
        out["edge_capacity"] = int(st.src.shape[0])
        eng = Engine(st, seed, checkpoint_every=ckpt)
        det = None
        if mode == "detector":
            from xzr.shapes.detector import ShapeDetector
            det = ShapeDetector(h, graph_every=10)
        out["init_total_s"] = round(time.perf_counter() - t0, 3)
        seg = max(1, steps // 3)
        seg_times, rss = [], [rss_mb()]
        ts = time.perf_counter()
        ignitions = 0
        for i in range(steps):
            d = eng.step()
            ignitions += int(d.ignitions.size)
            if det is not None:
                det.observe(d, eng.state)
            if (i + 1) % seg == 0 or i + 1 == steps:
                now = time.perf_counter()
                seg_times.append(now - ts)
                ts = now
                rss.append(rss_mb())
        out["run_s"] = round(sum(seg_times), 3)
        out["steps_per_s"] = round(steps / sum(seg_times), 2)
        out["segment_steps_per_s"] = [round(seg / x, 2) for x in seg_times[:3]]
        out["rss_mb_samples"] = [round(x, 1) for x in rss]
        out["ignitions_total"] = ignitions
        out["edges_alive_final"] = int(eng.state.alive.sum())
        out["checkpoints_held"] = len(eng.checkpoints)
        tf = time.perf_counter()
        out["fingerprint"] = eng.fingerprint()
        out["state_bytes"] = int(sum(v.nbytes for v in eng.state.arrays().values()))
        out["finalize_s"] = round(time.perf_counter() - tf, 3)
        if det is not None:
            out["detector_series_len"] = len(det.t)
    elif mode == "harness":
        from xzr.experiments.escalation.harness import RESULTS, _family, calibrations, condition, run
        c = condition(id="bench", n=n, horizon=steps, seeds=1, variants=("C",))
        cache_path = os.environ.get("BENCH_CALIB")  # private cache; the published one is only read
        from pathlib import Path
        gains = calibrations([c], 1, Path(cache_path), RESULTS / "calibration.json")
        out["init_calibration_s"] = round(time.perf_counter() - t0, 3)
        out["calibration_family"] = list(_family(c))
        tr = time.perf_counter()
        r = run(c, "C", seed, gains)
        out["run_s"] = round(time.perf_counter() - tr, 3)
        out["steps_per_s"] = round(steps / out["run_s"], 2)
        out["result_keys"] = len(r)
        import pickle
        out["result_pickle_bytes"] = len(pickle.dumps(r))
        out["rss_mb_samples"] = [round(rss_mb(), 1)]
    out["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024, 1)  # macOS: bytes
    out["wall_s"] = round(time.perf_counter() - t0, 3)
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
