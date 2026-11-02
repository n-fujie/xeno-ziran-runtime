"""Behavioural conformance snapshot of the simulator core, for comparing runtimes.

The same code runs on the desktop (with scipy / pydantic, or with the iOS stand-ins forced by XZR_FORCE_COMPAT=1)
and inside the iOS app (embedded CPython + numpy). ``snapshot()`` returns, per bundled scenario:

* dynamics — exact state fingerprints (state arrays + RNG state) after warmup, after 50 steps, after +10, after a
  rewind to t+50 and 10 replayed steps, and after save → load (a fresh world from the saved scenario + applied
  interventions) stepped the same 50 steps; plus the hierarchy's leaf paths (it resolves address-based sets);
* observation — the detector's metric series and a branch comparison summary (numbers, compared with a tolerance:
  the sampled bottleneck metric may differ where shortest paths tie, see _compat/csgraph.py).

``compare(a, b)`` reports any difference: exact fields must be equal, observation numbers within ``tol``.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from typing import Any

from ..scenario.io import load_sample
from ..scenario.model import Scenario
from ..service.session import COOPERATIVE, JOBS, Session, run_deferred

STEPS = 50
EXACT = ("fp_t0", "fp_50", "fp_60", "fp_rewind_60", "fp_load_t0", "fp_load_50", "hierarchy", "t0", "n", "edges")


def _wait(s: Session, t: int, timeout: float = 600) -> None:
    end = time.time() + timeout
    while time.time() < end:
        with s.lock:
            if s.engine.state.t >= t and s.pending_steps == 0:
                return
        if COOPERATIVE:  # no simulation thread here: step it from this loop
            s.pump(0.05)
        else:
            time.sleep(0.005)
    raise TimeoutError(f"session did not reach t={t}")


def _steps(s: Session, k: int) -> str:
    with s.lock:
        target = s.engine.state.t + k
    s.control("step", steps=k)
    _wait(s, target)
    with s.lock:
        return s.engine.fingerprint()


def _numbers(x: Any) -> Any:
    """JSON-safe copy keeping numbers (NaN / inf as strings)."""
    if isinstance(x, dict):
        return {str(k): _numbers(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_numbers(v) for v in x]
    if hasattr(x, "tolist"):
        return _numbers(x.tolist())
    if isinstance(x, float) and not math.isfinite(x):
        return str(x)
    return x


def scenario_snapshot(name: str, compare_horizon: int = 30) -> dict:
    sc = load_sample(name)
    s = Session(sc)
    try:
        with s.lock:
            st = s.engine.state
            out: dict[str, Any] = {"n": int(st.n), "edges": int(st.alive.sum()), "t0": int(st.t),
                                   "fp_t0": s.engine.fingerprint(),
                                   "hierarchy": hashlib.sha256(s.h.path.tobytes()).hexdigest()}
            t0 = st.t
        out["fp_50"] = _steps(s, STEPS)
        out["fp_60"] = _steps(s, 10)
        s.rewind(t0 + STEPS)
        out["fp_rewind_60"] = _steps(s, 10)
        metrics = s.metrics(0)
        out["observation"] = {"series_last": {k: v[-1] for k, v in metrics["series"].items() if len(v)},
                              "graph_last": {k: v[-1] for k, v in metrics["graph_series"].items() if len(v)}}
        jid = s.start_compare(compare_horizon)
        end = time.time() + 600
        while JOBS[jid]["status"] in ("queued", "running") and time.time() < end:
            if COOPERATIVE:
                run_deferred(1)
            time.sleep(0.02)
        out["observation"]["compare"] = JOBS[jid].get("summary")
        saved = json.loads(json.dumps(s.save()))  # what a Save file holds
    finally:
        s.close()
    s2 = Session(Scenario.model_validate(saved["scenario"]), saved["applied"])
    try:
        with s2.lock:
            out["fp_load_t0"] = s2.engine.fingerprint()
        out["fp_load_50"] = _steps(s2, STEPS)
    finally:
        s2.close()
    return _numbers(out)


def snapshot(names: list[str]) -> dict:
    return {name: scenario_snapshot(name) for name in names}


def _close(a: Any, b: Any, tol: float, path: str, diffs: list[str]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                diffs.append(f"{path}.{k}: missing on one side")
            else:
                _close(a[k], b[k], tol, f"{path}.{k}", diffs)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append(f"{path}: length {len(a)} != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b, strict=False)):
            _close(x, y, tol, f"{path}[{i}]", diffs)
    elif isinstance(a, int | float) and isinstance(b, int | float) and not isinstance(a, bool):
        if not math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol):
            diffs.append(f"{path}: {a} != {b}")
    elif a != b:
        diffs.append(f"{path}: {a!r} != {b!r}")


def compare(reference: dict, candidate: dict, tol: float = 0.0) -> dict:
    """Exact fields must match; observation numbers within ``tol`` (relative or absolute)."""
    exact: list[str] = []
    observation: list[str] = []
    for name in sorted(set(reference) | set(candidate)):
        if name not in reference or name not in candidate:
            exact.append(f"{name}: present on one side only")
            continue
        r, c = reference[name], candidate[name]
        for k in EXACT:
            if r.get(k) != c.get(k):
                exact.append(f"{name}.{k}: {r.get(k)} != {c.get(k)}")
        _close(r.get("observation"), c.get("observation"), tol, f"{name}.observation", observation)
    return {"exact_differences": exact, "observation_differences": observation}


def run_json(reference_json: str, tol: float = 0.05) -> str:
    """Snapshot the scenarios named in a reference (the golden fixture) on this runtime and compare (used by the
    iOS app's tests to check the embedded engine against the desktop reference). Returns JSON: the comparison,
    the snapshot and the wall time per scenario."""
    reference = json.loads(reference_json)
    snap, seconds = {}, {}
    for name in sorted(reference):
        t0 = time.time()
        snap[name] = scenario_snapshot(name)
        seconds[name] = round(time.time() - t0, 3)
    return json.dumps({"comparison": compare(reference, snap, tol), "snapshot": snap, "seconds": seconds})


def benchmark_json(name: str = "demo-3k", steps: int = 40) -> str:
    """Timings of the runtime on this machine (used by the iOS app's tests): world build, engine-only steps, session
    steps (engine + observation), a branch comparison, save and load. JSON, seconds."""
    import numpy as np

    from ..service.session import JOBS as jobs

    out: dict[str, Any] = {"scenario": name, "numpy": np.__version__}
    t0 = time.perf_counter()
    s = Session(load_sample(name))
    out["build_s"] = time.perf_counter() - t0
    try:
        with s.lock:
            t0 = time.perf_counter()
            for _ in range(10):
                s.engine.step()
            out["engine_steps_per_s"] = 10 / (time.perf_counter() - t0)
        t0 = time.perf_counter()
        _steps(s, steps)
        out["session_steps_per_s"] = steps / (time.perf_counter() - t0)
        t0 = time.perf_counter()
        jid = s.start_compare(50)
        while jobs[jid]["status"] in ("queued", "running"):
            if COOPERATIVE:
                run_deferred(1)
            time.sleep(0.01)
        out["compare_50_s"] = time.perf_counter() - t0
        t0 = time.perf_counter()
        saved = json.loads(json.dumps(s.save()))
        out["save_s"] = time.perf_counter() - t0
    finally:
        s.close()
    t0 = time.perf_counter()
    Session(Scenario.model_validate(saved["scenario"]), saved["applied"]).close()
    out["load_s"] = time.perf_counter() - t0
    return json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in out.items()})
