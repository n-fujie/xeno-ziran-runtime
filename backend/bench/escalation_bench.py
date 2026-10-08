"""Benchmark for the resolution-escalation phase: core runtime, reasoning runtime and diagnostic instrumentation
are measured separately (instrumentation is never folded into product runtime cost).

    python backend/bench/escalation_bench.py [--out backend/experiments/results/resolution/bench.json]

CORE RUNTIME          engine steps/s (full and MINIMAL) at 1,500 / 10,000 / 100,000 configurations; shape detection
                      at 10,000; delta size; runtime array memory; WebSocket throughput (from bench/benchmark.py)
REASONING RUNTIME     closed loop (reference structure + triggers) vs no reasoning layer, per step, at 1,500 and
                      10,000; graph sizes 32 / 128 / 512 / 2,048 at 1,500
DIAGNOSTIC            multi-scale observer per step; realized-coupling probe; per-condition statistics (max-T)
INSTRUMENTATION
COMPRESSION           codebook + encoding + phrase factorisation per run (400 / 4,000 / 40,000-step sequences)
"""

from __future__ import annotations

import argparse
import json
import platform
import resource
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xzr.experiments.escalation import compression as comp  # noqa: E402
from xzr.experiments.escalation.harness import build, calibrations, condition, realized_coupling  # noqa: E402
from xzr.experiments.escalation.stats import maxt_test  # noqa: E402
from xzr.lod.hierarchy import build_hierarchy, symmetric_adjacency  # noqa: E402
from xzr.runtime.engine import Engine  # noqa: E402
from xzr.runtime.flags import MINIMAL, Flags  # noqa: E402
from xzr.runtime.generator import latent_geometric  # noqa: E402
from xzr.shapes.multiscale import MultiScaleObserver  # noqa: E402


def rss_mib() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)


def core(n: int, steps: int, flags: Flags) -> dict:
    st = latent_geometric(n, 3, geo_fraction=0.0).state
    e = Engine(st, 3, checkpoint_every=0, flags=flags)
    for _ in range(30):
        e.step()
    ts = []
    for _ in range(steps):
        a = time.perf_counter()
        e.step()
        ts.append(time.perf_counter() - a)
    ts = np.array(ts) * 1000
    return {"n": n, "steps": steps, "steps_per_second": round(1000 / ts.mean(), 1), "ms_p50": round(float(np.median(ts)), 3),
            "ms_p95": round(float(np.quantile(ts, 0.95)), 3),
            "array_mib": round(sum(v.nbytes for v in st.arrays().values()) / 2**20, 2)}


def observer(n: int, steps: int) -> dict:
    st = latent_geometric(n, 3, geo_fraction=0.0).state
    h = build_hierarchy(symmetric_adjacency(st.src[st.alive], st.dst[st.alive], n))
    e = Engine(st, 3, checkpoint_every=0)
    obs = MultiScaleObserver(n, 100, macro_labels=h.labels[0], target=np.arange(0, n, 7))
    t_obs = t_cpl = 0.0
    for k in range(steps):
        d = e.step()
        a = time.perf_counter()
        obs.observe(d, st)
        b = time.perf_counter()
        if k % 10 == 0:
            realized_coupling(st)
        t_obs += b - a
        t_cpl += time.perf_counter() - b
    return {"n": n, "observer_ms_per_step": round(1000 * t_obs / steps, 3),
            "coupling_probe_ms_per_step": round(1000 * t_cpl / steps, 3)}


def reasoning(n: int, steps: int, size: int, gains: dict) -> dict:
    out = {}
    for letter in ("A", "C"):
        c = condition(n=n, size=size, horizon=steps + 200, reasoning_from=100)
        loop, world, *_ = build(c, 5, gains, letter)
        for _ in range(150):
            loop.step()
        a = time.perf_counter()
        for _ in range(steps):
            loop.step()
        out[letter] = 1000 * (time.perf_counter() - a) / steps
    return {"n": n, "size": size, "none_ms_per_step": round(out["A"], 3), "closed_loop_ms_per_step": round(out["C"], 3),
            "reasoning_overhead_ms_per_step": round(out["C"] - out["A"], 3),
            "reasoning_overhead_relative": round(out["C"] / out["A"] - 1, 3)}


def statistics_cost() -> dict:
    rng = np.random.default_rng(0)
    out = {}
    for label, m in (("1500 node-level family (8×4×4000)", 128000), ("meso family (8×4×32)", 1024)):
        d = rng.normal(0, 1, (12, m))
        a = time.perf_counter()
        maxt_test(d, np.ones(m))
        out[label] = round(time.perf_counter() - a, 3)
    return out


def compression_cost() -> dict:
    rng = np.random.default_rng(1)
    out = {}
    for steps in (400, 4000, 40000):
        x = rng.normal(0, 1, (steps // 10, 24))
        a = time.perf_counter()
        cb = comp.kmeans(x, comp.K, 0)
        sym = comp.encode(x, cb)
        comp.lz78_phrases(sym)
        out[str(steps)] = round(time.perf_counter() - a, 3)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "experiments" / "results" / "resolution" / "bench.json"))
    ap.add_argument("--ws-seconds", type=float, default=8)
    a = ap.parse_args()
    res: dict = {"machine": {"platform": platform.platform(), "python": platform.python_version(),
                             "numpy": np.__version__}, "date": time.strftime("%Y-%m-%d %H:%M:%S")}
    res["core"] = {f"{n}:{name}": core(n, steps, fl) for n, steps in ((1500, 2000), (10000, 800), (100000, 120))
                   for name, fl in (("full", Flags()), ("minimal", MINIMAL))}
    from benchmark import bench_runtime, bench_websocket  # bench/benchmark.py
    res["core"]["10000:with_shape_detection"] = bench_runtime(600)["runtime_plus_shape_detection"]
    res["core"]["10000:delta_and_memory"] = {k: v for k, v in bench_runtime(300).items()
                                             if k in ("runtime_only", "runtime_array_mib", "connections")}
    res["core"]["websocket_full"] = bench_websocket(a.ws_seconds, "full")
    gains = calibrations([condition(), condition(n=10000), condition(n=100000)])
    res["reasoning"] = [reasoning(1500, 1000, 32, gains), reasoning(10000, 300, 32, gains),
                        reasoning(100000, 60, 32, gains)] + [
        reasoning(1500, 400, z, gains) for z in (128, 512, 2048)]
    res["instrumentation"] = {"observer": [observer(n, s) for n, s in ((1500, 1000), (10000, 400), (100000, 60))],
                              "statistics_s": statistics_cost()}
    res["compression_s"] = compression_cost()
    res["peak_rss_mib"] = round(rss_mib(), 1)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
