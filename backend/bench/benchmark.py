"""Performance benchmark: 10,000 configurations, >50,000 connections, continuous transitions.

    python backend/bench/benchmark.py [--steps 1000] [--ws-seconds 10] [--out backend/bench/results/latest.json]

Reports
  * simulation steps/s — runtime only, and runtime + shape detection (as the live service runs it)
  * per-step latency (p50 / p95), events per step, encoded delta bytes per step
  * WebSocket update rate and bandwidth — an in-process server streaming to a real websocket client,
    at maximum simulation speed and at 30 steps/s
  * memory — peak RSS of this process, and runtime array bytes

Rendering FPS cannot be measured headless: open the UI with ``?scenario=benchmark-10k`` and read the fps
counter in the control bar (also exposed as ``window.__xzr.get().fps``); docs/BENCHMARK.md records a run.
No semantic events are dropped anywhere in this path; counts below include every event.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import resource
import socket
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xzr.runtime.delta import encode_step  # noqa: E402
from xzr.scenario.build import build_world  # noqa: E402
from xzr.scenario.io import load_sample  # noqa: E402
from xzr.shapes.detector import ShapeDetector  # noqa: E402


def rss_mib() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / (1024 * 1024) if sys.platform == "darwin" else r / 1024


def bench_runtime(steps: int, flags=None) -> dict:
    t0 = time.perf_counter()
    world = build_world(load_sample("benchmark-10k"), flags)
    build_s = time.perf_counter() - t0
    s = world.state
    out: dict = {"configurations": s.n, "connections": int(s.alive.sum()), "connection_capacity": s.e_cap,
                 "build_seconds": round(build_s, 2)}
    e = world.engine
    e.run(100)  # warm-up into the sustained regime
    lat, events, nbytes = [], [], []
    t0 = time.perf_counter()
    for _ in range(steps):
        a = time.perf_counter()
        d = e.step()
        lat.append(time.perf_counter() - a)
        events.append(sum(d.counts().values()))
        nbytes.append(len(encode_step(d)))
    wall = time.perf_counter() - t0
    out["runtime_only"] = {
        "steps": steps, "steps_per_second": round(steps / wall, 1),
        "step_ms_p50": round(1000 * float(np.percentile(lat, 50)), 2),
        "step_ms_p95": round(1000 * float(np.percentile(lat, 95)), 2),
        "events_per_step_mean": round(float(np.mean(events)), 1),
        "delta_bytes_per_step_mean": round(float(np.mean(nbytes))),
        "delta_bytes_per_step_p95": round(float(np.percentile(nbytes, 95))),
        "full_state_bytes_equivalent": int(sum(a.nbytes for a in s.arrays().values())),
    }
    det = ShapeDetector(world.hierarchy, graph_every=10)
    t0 = time.perf_counter()
    lat = []
    for _ in range(steps):
        a = time.perf_counter()
        det.observe(e.step(), e.state)
        lat.append(time.perf_counter() - a)
    wall = time.perf_counter() - t0
    out["runtime_plus_shape_detection"] = {
        "steps": steps, "steps_per_second": round(steps / wall, 1),
        "step_ms_p50": round(1000 * float(np.percentile(lat, 50)), 2),
        "step_ms_p95": round(1000 * float(np.percentile(lat, 95)), 2),
        "graph_pass_every": 10,
    }
    out["connections_after"] = int(e.state.alive.sum())
    out["runtime_array_mib"] = round(sum(a.nbytes for a in e.state.arrays().values()) / 2**20, 1)
    return out


def _free_port() -> int:
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        return sk.getsockname()[1]


def _rss_of(pid: int) -> float:
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return round(int(out) / 1024, 1) if out else float("nan")


def bench_websocket(seconds: float, flags: str = "full") -> dict:
    """Server in a separate process (as deployed); a websocket client in this process consumes the stream."""
    import httpx
    import websockets

    port = _free_port()
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "xzr.service.app:app", "--app-dir", str(root),
                             "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"])
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(200):
            try:
                httpx.get(f"{base}/api/health", timeout=1)
                break
            except httpx.HTTPError:
                time.sleep(0.1)
        sid = httpx.post(f"{base}/api/sessions", json={"sample": "benchmark-10k", "flags": flags}, timeout=60).json()["id"]

        async def measure(speed: float) -> dict:
            async with websockets.connect(f"ws://127.0.0.1:{port}/ws/{sid}", max_size=None) as ws:
                await ws.recv()  # hello
                await ws.recv()  # snapshot
                httpx.post(f"{base}/api/sessions/{sid}/control", json={"action": "run", "speed": speed})
                frames = nbytes = steps = 0
                t_first = None
                t0 = time.perf_counter()
                while time.perf_counter() - t0 < seconds:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    if isinstance(msg, bytes) and msg[:4] == (1).to_bytes(4, "little"):
                        t_first = t_first or time.perf_counter()
                        frames += 1
                        nbytes += len(msg)
                        steps += int.from_bytes(msg[4:8], "little")
                wall = time.perf_counter() - (t_first or t0)
                httpx.post(f"{base}/api/sessions/{sid}/control", json={"action": "pause"})
                return {"requested_steps_per_second": speed or "max",
                        "delta_frames_per_second": round(frames / wall, 1),
                        "steps_streamed_per_second": round(steps / wall, 1),
                        "kib_per_second": round(nbytes / wall / 1024, 1),
                        "mean_frame_kib": round(nbytes / max(frames, 1) / 1024, 1),
                        "server_rss_mib": _rss_of(proc.pid)}

        return {"max_speed": asyncio.run(measure(0)), "speed_30": asyncio.run(measure(30)),
                "speed_60": asyncio.run(measure(60))}
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def bench_reasoning(steps: int) -> dict:
    """Reasoning overhead on the 10k field: the closed loop with no reasoning layer vs with scorekeeping (enabling
    conditions as in the reasoning experiments), each with and without live shape detection."""
    from xzr.experiments.reason import GROUNDINGS
    from xzr.reasonlab.loop import LoopConfig, ReasonLoop
    from xzr.shapes.detector import ShapeDetector
    sc = load_sample("benchmark-10k-reason")
    out = {}
    for rep, track in (("none", False), ("scorekeeping", False), ("scorekeeping", True)):
        for detect in (False, True):
            w = build_world(sc)
            # enabling conditions off: reasoning is active throughout, so this is its full (upper-bound) cost; the
            # lab's enabling thresholds were calibrated on 1,500 configurations and do not transfer to this field.
            # track=True adds the experiments' instrumentation (two counterfactual compilations per check).
            loop = ReasonLoop(w, sc.practice, LoopConfig(representation=rep, enabling=[], groundings=GROUNDINGS,
                                                         track_distinctions=track))
            det = ShapeDetector(w.hierarchy, graph_every=10) if detect else None
            for _ in range(150):  # reach the reasoning phase before timing
                d = loop.step()
                if det:
                    det.observe(d, w.state)
            t0 = time.perf_counter()
            for _ in range(steps):
                d = loop.step()
                if det:
                    det.observe(d, w.state)
            dt = time.perf_counter() - t0
            phases = [r["phase"] for r in loop.timeline[-steps // 10:]]
            out[f"{rep}{'+instrumentation' if track else ''}{'+detection' if detect else ''}"] = {
                "steps_per_second": round(steps / dt, 1), "ms_per_step": round(1000 * dt / steps, 2),
                "reasoning_active_share": round(phases.count("reasoning") / max(len(phases), 1), 2)}
    base, withr = out["none"]["ms_per_step"], out["scorekeeping"]["ms_per_step"]
    instr = out["scorekeeping+instrumentation"]["ms_per_step"]
    out["reasoning_overhead_ms_per_step"] = round(withr - base, 2)
    out["reasoning_overhead_relative"] = round((withr - base) / base, 4)
    out["instrumentation_overhead_ms_per_step"] = round(instr - withr, 2)
    return out


def bench_comparison(horizon: int = 150) -> dict:
    """Cost of one baseline-vs-intervention comparison job (three branches incl. the noise floor) on the 10k field."""
    from xzr.compare.compare import compare
    from xzr.runtime.intervention import Freeze
    world = build_world(load_sample("benchmark-10k"))
    world.engine.run(100)
    region = tuple(world.hierarchy.resolve("1").tolist())
    t0 = time.perf_counter()
    r = compare(world.engine, [], [], [Freeze(region)], [], world.hierarchy, horizon=horizon)
    dt = time.perf_counter() - t0
    return {"horizon": horizon, "branches": 3, "seconds": round(dt, 2), "steps_simulated": 3 * horizon,
            "ms_per_branch_step": round(1000 * dt / (3 * horizon), 2),
            "first_divergence_step": r["summary"]["first_divergence_step"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=1000)
    ap.add_argument("--ws-seconds", type=float, default=10)
    ap.add_argument("--out", default=str(Path(__file__).parent / "results" / "latest.json"))
    args = ap.parse_args()
    result = {
        "scenario": "benchmark-10k",
        "machine": {"platform": platform.platform(), "processor": platform.processor() or platform.machine(),
                    "python": platform.python_version(), "numpy": np.__version__},
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "simulation": bench_runtime(args.steps),
    }
    from xzr.runtime.flags import MINIMAL
    result["simulation_minimal"] = bench_runtime(args.steps, MINIMAL)
    result["reasoning"] = bench_reasoning(args.steps // 2)
    result["comparison"] = bench_comparison()
    result["websocket"] = bench_websocket(args.ws_seconds)
    result["websocket_minimal"] = bench_websocket(args.ws_seconds, "minimal")
    result["peak_rss_mib"] = round(rss_mib(), 1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
