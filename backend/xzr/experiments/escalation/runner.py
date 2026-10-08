"""Run a list of conditions (conditions × engine seeds in a process pool), analyse each condition when all its
seeds are in, and write results incrementally (resumable: conditions already in the output file are skipped)."""

from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from .analysis import analyse
from .harness import calibrations, seed_job

SEED0 = 100


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return _jsonable(x.tolist())
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating):
        v = float(x)
        return v if np.isfinite(v) else str(v)
    if isinstance(x, float) and not np.isfinite(x):
        return str(x)
    return x


def provenance() -> dict:
    """Code state that produced a result: git HEAD, whether the tree is dirty, and a hash of backend/xzr/**/*.py."""
    import hashlib
    import subprocess
    root = Path(__file__).resolve().parents[3]
    h = hashlib.sha1()
    for p in sorted((root / "xzr").rglob("*.py")):
        h.update(p.read_bytes())
    head: str | None = None
    dirty: bool | None = None
    if (root / "pyproject.toml").exists():  # a source checkout (an installed copy has no git state of its own)
        try:
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                                  text=True).stdout.strip() or None
            dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True,
                                        text=True).stdout.strip()) if head else None
        except OSError:
            head = dirty = None
    import platform

    from ... import __version__
    return {"version": __version__, "git_head": head, "dirty": dirty, "code_sha1": h.hexdigest()[:16],
            "time": time.strftime("%Y-%m-%d %H:%M:%S"), "python": platform.python_version(),
            "numpy": np.__version__}


def _job_dir(out: Path, cid: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in cid)
    return out.parent / "jobs" / out.stem / safe


def _save_job(out: Path, cid: str, res: dict) -> None:
    import gzip
    import pickle
    d = _job_dir(out, cid)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{res['seed']}.pkl.gz.tmp"
    with gzip.open(tmp, "wb", compresslevel=3) as f:
        pickle.dump(res, f, protocol=5)
    tmp.rename(d / f"{res['seed']}.pkl.gz")


def load_jobs(out: Path, cid: str) -> dict[int, dict]:
    """Per-seed job results already on disk for a condition (completed jobs only)."""
    import gzip
    import pickle
    d = _job_dir(out, cid)
    got = {}
    for p in sorted(d.glob("*.pkl.gz")) if d.exists() else []:
        try:
            with gzip.open(p, "rb") as f:
                r = pickle.load(f)
            got[int(r["seed"])] = r
        except (OSError, EOFError, pickle.UnpicklingError):
            p.rename(p.with_suffix(".corrupt"))  # quarantine a truncated file; the seed is rerun
    return got


def analyse_condition(c: dict, res: list[dict], exclude, out: Path, prov: dict, t0: float) -> dict:
    import traceback
    ex_ = exclude(c) if callable(exclude) else set()
    try:
        a = analyse(c, res, ex_)
    except Exception:  # noqa: BLE001 — an analysis failure must not stop the run; the jobs are on disk
        return {"condition": {k: (list(v) if isinstance(v, tuple) else v) for k, v in c.items()},
                "analysis_error": traceback.format_exc()[-3000:]}
    a["elapsed_s"] = round(time.time() - t0, 1)
    a["provenance"] = {**prov, "experiment": out.stem, "condition": c["id"], "engine_seeds": [r["seed"] for r in res]}
    return _jsonable(a)


def run_conditions(conds: list[dict], out: Path, procs: int = 7, meta: dict | None = None, exclude=None,
                   keep_jobs: bool = False, seed0: int = SEED0, calibration: Path | None = None,
                   calibration_base: Path | None = None) -> dict:
    """Every seed job is written to results/resolution/jobs/<experiment>/<condition>/<seed>.pkl.gz as soon as it
    completes; a restart reruns only missing seeds, and a condition is analysed once all its seeds are on disk."""
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = json.loads(out.read_text()) if out.exists() else {"meta": meta or {}, "conditions": {}}
    prov = provenance()
    doc.setdefault("meta", {}).setdefault("provenance", []).append(prov)
    todo = [c for c in conds if c["id"] not in doc["conditions"] or "analysis_error" in doc["conditions"][c["id"]]]
    if not todo:
        return doc
    gains = calibrations(todo, procs, calibration, calibration_base)
    doc["calibration"] = {k: v for k, v in gains.items()}
    t0 = time.time()
    by_id = {c["id"]: c for c in todo}
    have = {c["id"]: load_jobs(out, c["id"]) for c in todo}
    jobs = [(c, seed0 + k, gains) for c in todo for k in range(c["seeds"]) if seed0 + k not in have[c["id"]]]
    jobs.sort(key=lambda j: -j[0]["n"] * j[0]["horizon"] * (len(j[0]["variants"]) + len(j[0].get("revert", ()))))

    def finish(cid: str) -> None:
        c = by_id[cid]
        res = [have[cid][seed0 + k] for k in range(c["seeds"])]
        doc["conditions"][cid] = analyse_condition(c, res, exclude, out, prov, t0)
        out.write_text(json.dumps(doc))
        status = "ANALYSIS ERROR" if "analysis_error" in doc["conditions"][cid] else "done"
        print(f"[{time.time() - t0:7.0f}s] {cid} {status} ({len(doc['conditions'])}/{len(conds)})", flush=True)

    for c in todo:  # conditions whose seeds were all on disk already
        if len(have[c["id"]]) >= c["seeds"]:
            finish(c["id"])
    if jobs:
        with ProcessPoolExecutor(procs) as ex:
            futs = {ex.submit(seed_job, j): j[0]["id"] for j in jobs}
            for f in as_completed(futs):
                cid = futs[f]
                r = f.result()
                _save_job(out, cid, r)
                print(f"[{time.time() - t0:7.0f}s]   job {cid} seed {r['seed']} saved", flush=True)
                have[cid][int(r["seed"])] = r
                if len(have[cid]) == by_id[cid]["seeds"]:
                    finish(cid)
                    have[cid] = {}  # free memory; the jobs stay on disk
    return doc
