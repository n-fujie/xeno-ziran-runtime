"""Performance and load measurements of the study workflow itself (not of any scientific claim).

Measured, each as a plain number with the conditions it was taken under:
  * run time, CPU time (utilisation = CPU / wall) and peak memory per run, from the run records;
  * parallel efficiency: the same protocol executed with 1, 2, … workers (speed-up and speed-up per worker);
  * failure rate (runs not ok / runs planned) in every execution;
  * storage: time to write the run records, to analyse, to build the paper outputs, to package and to verify;
  * replay agreement: every stored run re-executed from the protocol alone and compared with its record;
  * history re-entry load: wall time of arms that re-insert history versus the same arm without it, per seed pair;
  * laboratory load: staged populations of scientific systems (steps/s, events, memory), where the systems' messages are the runtime
    connections their readings travel along (communication) — a load figure, never an autonomy measure.
All numbers are from the machine and software versions recorded alongside them.
"""

from __future__ import annotations

import json
import os
import platform
import resource
import sys
import time
from pathlib import Path

from . import analysis, report, runner, templates
from . import protocol as P


def _rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(r / (1 << 20) if sys.platform == "darwin" else r / 1024, 1)


def _mean(x: list[float]) -> float | None:
    return sum(x) / len(x) if x else None


def parallel(root: Path, procs: tuple[int, ...] = (1, 2, 4), n_seeds: int = 4, horizon: int = 120) -> dict:
    rows = []
    base = None
    for p in procs:
        st = runner.Study.create(templates.template("quick", n_seeds=n_seeds, horizon=horizon), root)
        t0 = time.time()
        st.execute(procs=p)
        wall = time.time() - t0
        runs = st.runs()
        ok = [r for r in runs if r["status"] == "ok"]
        base = base or wall
        rows.append(
            {
                "procs": p,
                "wall_s": round(wall, 2),
                "speedup": round(base / wall, 2),
                "efficiency": round(base / wall / p, 2),
                "runs": len(runs),
                "ok": len(ok),
                "failure_rate": 1 - len(ok) / max(1, len(runs)),
                "mean_run_wall_s": round(_mean([r["wall_s"] for r in ok]) or 0, 3),
                "mean_cpu_utilisation": round(
                    _mean([r["cpu_s"] / r["wall_s"] for r in ok if r.get("cpu_s") and r["wall_s"]]) or 0, 2
                ),
                "peak_run_rss_mb": max((r["peak_rss_mb"] for r in ok), default=None),
                "study": st.id,
            }
        )
    return {
        "protocol": "quick",
        "n_seeds": n_seeds,
        "horizon": horizon,
        "runs_per_execution": rows[0]["runs"],
        "rows": rows,
        "note": "speed-up is relative to one worker; process start-up and the shared first import are included in the wall time",
    }


def storage_and_replay(root: Path, n_seeds: int = 4, horizon: int = 120) -> dict:
    st = runner.Study.create(templates.template("quick", n_seeds=n_seeds, horizon=horizon), root)
    st.execute(procs=2)
    out: dict = {"study": st.id, "runs": len(st.run_files())}
    t = time.time()
    runs = st.runs()
    out["read_runs_s"] = round(time.time() - t, 4)
    out["bytes_per_run"] = round(sum(p.stat().st_size for p in st.run_files()) / max(1, len(st.run_files())))
    t = time.time()
    an = analysis.analyse(st)
    out["analyse_s"] = round(time.time() - t, 3)
    t = time.time()
    report.build(st, an)
    out["report_s"] = round(time.time() - t, 3)
    t = time.time()
    z = report.package(st)
    out["package_s"], out["package_bytes"] = round(time.time() - t, 3), z.stat().st_size
    t = time.time()
    v = report.verify(st.path)
    out["verify_s"], out["verify_ok"] = round(time.time() - t, 3), v["ok"]
    agree, n = 0, 0
    t = time.time()
    for r in runs:
        res = runner.replay_run(st, r["arm"], r["index"])
        agree += res["agreement"]
        n += 1
    out["replay"] = {
        "runs": n,
        "agree": agree,
        "agreement_rate": agree / max(1, n),
        "wall_s": round(time.time() - t, 2),
        "condition": "same machine and software versions",
    }
    return out


def history_load(root: Path, n_seeds: int = 4, horizon: int = 240) -> dict:
    """Wall time with and without history re-entry (arms recursive vs no-history of the revision study, same seeds)."""
    d = templates.template("revision-study", n_seeds=n_seeds, horizon=horizon)
    d["arms"] = [a for a in d["arms"] if a["name"] in ("recursive", "no-history")]
    d["contrasts"] = [c for c in d["contrasts"] if {c["a"], c["b"]} <= {"recursive", "no-history"}]
    d["hypotheses"], d["criteria"] = [], {"success": [], "failure": []}
    st = runner.Study.create(d, root)
    st.execute(procs=1)
    by = {a: [r for r in st.runs() if r["arm"] == a and r["status"] == "ok"] for a in ("recursive", "no-history")}
    w = {a: _mean([r["wall_s"] for r in rs]) for a, rs in by.items()}
    reins = {a: _mean([r["history_reentry"]["reinsertions"] for r in rs]) for a, rs in by.items()}
    return {
        "study": st.id,
        "n_seeds": n_seeds,
        "mean_wall_s": w,
        "mean_reinsertions": reins,
        "wall_ratio_with_over_without": (w["recursive"] / w["no-history"]) if w["no-history"] else None,
        "note": "the two arms also differ in what the controller does with the extra events; one process, sequential, so wall times are comparable",
    }


def lab_stages(stages: tuple[int, ...] = (3, 20, 50, 100, 300), steps: int = 40) -> dict:
    from ..lab.population import population
    from ..lab.record import LabRun

    rows = []
    for n in stages:
        t0 = time.time()
        c0 = time.process_time()
        r = LabRun(
            {"gen_seed": 8000, "seed": 80000, "settings": None, "physics": True, "horizon": steps, "systems": population(n)}
        )
        for _ in range(steps):
            r.step()
        rec = r.record()
        wall = time.time() - t0
        st = r.science.systems
        rows.append(
            {
                "systems": n,
                "steps": steps,
                "wall_s": round(wall, 2),
                "steps_per_s": round(steps / wall, 1),
                "cpu_utilisation": round((time.process_time() - c0) / wall, 2),
                "events": len(rec["events"]),
                "requests": sum(s.stats["requests"] for s in st.values()),
                "completed": sum(s.stats["completed"] for s in st.values()),
                "peak_rss_mb": _rss_mb(),
            }
        )
    return {
        "stages": rows,
        "note": "peak_rss is the process high-water mark and only grows; the number of systems is a load, not a measure of autonomy",
    }


def run(out: Path, quick: bool = False) -> dict:
    """Run every measurement into scratch study roots under ``out`` and write ``perf.json``."""
    out.mkdir(parents=True, exist_ok=True)
    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "xzr_force_compat": os.environ.get("XZR_FORCE_COMPAT", ""),
    }
    res: dict = {"schema": "xzr.perf/1", "environment": env, "protocol_digest_example": P.digest(templates.template("quick"))}
    n = 2 if quick else 4
    res["parallel"] = parallel(out / "parallel", (1, 2) if quick else (1, 2, 4), n_seeds=n)
    res["storage_replay"] = storage_and_replay(out / "storage", n_seeds=n)
    res["history_load"] = history_load(out / "history", n_seeds=2 if quick else 4, horizon=120 if quick else 240)
    try:
        res["lab"] = lab_stages((3, 20) if quick else (3, 20, 50, 100, 300))
    except ImportError as e:
        res["lab"] = {"skipped": f"mujoco is not installed ({e})"}
    (out / "perf.json").write_text(json.dumps(res, indent=1))
    return res
