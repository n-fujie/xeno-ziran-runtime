"""Post-Active-Inference benchmark driver.

    python run_benchmark.py plan    configs/<stage>.json            hardware, job count, cost estimate
    python run_benchmark.py run     configs/<stage>.json [--procs N] run (resumable: finished cells are skipped)
    python run_benchmark.py analyse configs/<stage>.json [--publish] statistics → results/<stage>/ (and results/)
    python run_benchmark.py refine  configs/<stage>.json            add severities near observed crossings →
                                                                     configs/<stage>_refined.json

Run from this directory with the repository's virtual environment (../../.venv/bin/python). One cell = one seed ×
one perturbation subtype × one severity, with all its controller runs. Every finished cell is written once to
results/<stage>/jobs/<seed>/<cell>.json and never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pai  # noqa: E402,F401  (sets up import paths)
from pai.perturbations import ALIASES, NOT_IMPLEMENTED, REGISTRY  # noqa: E402

CONTROL = "control"
SEC_PER_RUN = 2.3     # measured (check stage, Apple M1): one 1,200-step continuation incl. tracker and probes
SEC_PREFIX = 6.0      # warm-up + calibration, once per seed and process
MB_PER_PROC = 200     # conservative resident size of one worker (measured peak ≈ 81 MB on M1)


# ------------------------------------------------------------------------------------------------ config / plan
def load(path: str) -> dict:
    cfg = json.loads(Path(path).read_text())
    cfg.setdefault("world", {})
    cfg.setdefault("phases", {})
    cfg.setdefault("controllers", ["none", "aif_fixed", "aif_adaptive", "ost"])
    cfg.setdefault("noise_offset", 1000)
    cfg.setdefault("ablations", [])
    cfg.setdefault("ablation_cells", [])
    if cfg.get("perturbations") in (None, "all"):
        cfg["perturbations"] = list(REGISTRY)
    cfg["_path"] = str(path)
    return cfg


def config_hash(cfg: dict) -> str:
    c = {k: v for k, v in cfg.items() if not k.startswith("_")}
    return hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()[:16]


def out_dir(cfg: dict) -> Path:
    return HERE / "results" / cfg["stage"]


def cell_name(key: str, sev: float) -> str:
    return f"{key}@{sev:g}"


def cells_for(cfg: dict) -> list[tuple[int, str, float]]:
    out = []
    for seed in cfg["seeds"]:
        out.append((seed, CONTROL, 0.0))
        for k in cfg["perturbations"]:
            for s in cfg["severities"] + cfg.get("extra_severities", {}).get(k, []):
                if s > 0:
                    out.append((seed, k, float(s)))
    return out


def runs_for(cfg: dict, key: str, sev: float) -> list[tuple[str, int, bool]]:
    """(controller spec, engine-seed offset, probes) for one cell."""
    r = [(c, 0, c == "none") for c in cfg["controllers"]]
    abl_cell = key == CONTROL or [key, sev] in [[a, float(b)] for a, b in cfg["ablation_cells"]]
    if abl_cell and cfg["ablations"]:
        r += [(f"aif_adaptive-{a}", 0, False) for a in cfg["ablations"]]
        if "no_boundary" in cfg["ablations"]:
            r.append(("ost-no_boundary", 0, False))
    if key == CONTROL:  # noise replicate (other engine stream, unperturbed)
        r += [(c, cfg["noise_offset"], c == "none") for c in ("none", "aif_fixed", "aif_adaptive")]
    return r


def hardware() -> dict:
    hw = {"machine": platform.machine(), "platform": platform.platform(), "processor": platform.processor(),
          "cpu_count": os.cpu_count(), "python": platform.python_version()}
    try:
        hw["ram_gb"] = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) / 2**30
        hw["cpu_brand"] = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
        vm = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
        page = 16384 if "16384" in vm.splitlines()[0] else 4096
        free = sum(int(ln.split(":")[1].strip().rstrip(".")) for ln in vm.splitlines()
                   if ln.startswith(("Pages free", "Pages inactive", "Pages speculative")))
        hw["available_gb"] = free * page / 2**30
    except (OSError, ValueError, IndexError):
        pass
    hw["gpu"] = "not used (the runtime has no GPU code path)"
    return hw


def safe_procs(cfg: dict, hw: dict, requested: int | None) -> int:
    want = requested or cfg.get("procs", 4)
    cap = max(1, (hw.get("cpu_count") or 2) // 2)
    if hw.get("available_gb"):
        cap = min(cap, max(1, int(hw["available_gb"] * 1024 * 0.6 // MB_PER_PROC)))
    return max(1, min(want, cap))


def plan(cfg: dict, procs: int | None = None) -> dict:
    hw = hardware()
    cells = cells_for(cfg)
    runs = sum(len(runs_for(cfg, k, s)) for _, k, s in cells)
    p = safe_procs(cfg, hw, procs)
    done = sum(1 for seed, k, s in cells if (out_dir(cfg) / "jobs" / str(seed) / f"{cell_name(k, s)}.json").exists())
    est = (runs * SEC_PER_RUN + len(cfg["seeds"]) * p * SEC_PREFIX * 2) / p
    return {"stage": cfg["stage"], "cells": len(cells), "cells_done": done, "runs": runs, "procs": p,
            "estimated_wall_min": round(est / 60, 1), "estimated_peak_mb": p * MB_PER_PROC, "hardware": hw,
            "config_hash": config_hash(cfg), "perturbations": len(cfg["perturbations"]),
            "aliases": ALIASES, "not_implemented": NOT_IMPLEMENTED}


# ------------------------------------------------------------------------------------------------ run
def _work(args) -> list[tuple[str, str]]:
    cfg, seed, cells = args
    from pai.episode import run_episode
    out = []
    for key, sev in cells:
        path = out_dir(cfg) / "jobs" / str(seed) / f"{cell_name(key, sev)}.json"
        if path.exists():
            out.append((path.name, "skipped"))
            continue
        res = {"seed": seed, "key": key, "severity": sev, "runs": {}}
        for spec, off, probes in runs_for(cfg, key, sev):
            name = spec if off == 0 else f"{spec}@noise"
            res["runs"][name] = run_episode(cfg["world"], seed + off, None if key == CONTROL else key, sev, spec,
                                            phases=cfg["phases"], probes=probes, trace=cfg.get("trace", True))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(res, default=_default))
        tmp.rename(path)  # atomic: a cell file is either complete or absent
        bad = [n for n, r in res["runs"].items() if r["status"] != "ok"]
        out.append((path.name, "failed:" + ",".join(bad) if bad else "ok"))
    return out


def _default(x):
    import numpy as np
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating):
        return float(x) if np.isfinite(x) else None
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.bool_):
        return bool(x)
    return str(x)


def manifest(cfg: dict, extra: dict | None = None) -> dict:
    import numpy as np
    import scipy
    from xzr.experiments.escalation.runner import provenance
    h = hashlib.sha1()
    for p in sorted(HERE.rglob("*.py")):
        if "results" not in p.parts:
            h.update(p.read_bytes())
    return {"stage": cfg["stage"], "config": {k: v for k, v in cfg.items() if not k.startswith("_")},
            "config_hash": config_hash(cfg), "runtime_provenance": provenance(), "benchmark_code_sha1": h.hexdigest()[:16],
            "dependencies": {"numpy": np.__version__, "scipy": scipy.__version__, "python": platform.python_version()},
            "aif_source": "ziran-xeno-simulator embodied/active_inference @ d4ad6a7544bbb515027e1a97fa914423f01bf8e6 (vendored)",
            "hardware": hardware(), "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **(extra or {})}


def run(cfg: dict, procs: int | None = None, chunk: int = 6) -> None:
    pl = plan(cfg, procs)
    print(json.dumps({k: pl[k] for k in ("stage", "cells", "cells_done", "runs", "procs", "estimated_wall_min",
                                         "estimated_peak_mb")}), flush=True)
    od = out_dir(cfg)
    od.mkdir(parents=True, exist_ok=True)
    (od / f"run_manifest_{time.strftime('%Y%m%d-%H%M%S')}.json").write_text(json.dumps(manifest(cfg, {"plan": pl}), indent=1, default=_default))
    by_seed: dict[int, list] = {}
    for seed, k, s in cells_for(cfg):
        if not (od / "jobs" / str(seed) / f"{cell_name(k, s)}.json").exists():
            by_seed.setdefault(seed, []).append((k, s))
    tasks = [(cfg, seed, cs[i:i + chunk]) for seed, cs in by_seed.items() for i in range(0, len(cs), chunk)]
    t0 = time.time()
    n = 0
    total = sum(len(t[2]) for t in tasks)
    with ProcessPoolExecutor(pl["procs"]) as ex:
        futs = [ex.submit(_work, t) for t in tasks]
        for f in as_completed(futs):
            for name, st in f.result():
                n += 1
                if st != "ok":
                    print(f"  {name}: {st}", flush=True)
            el = time.time() - t0
            print(f"[{n}/{total}] {el / 60:.1f} min elapsed, ~{el / max(n, 1) * (total - n) / 60:.1f} min left", flush=True)


# ------------------------------------------------------------------------------------------------ main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("plan", "run", "analyse", "refine"))
    ap.add_argument("config")
    ap.add_argument("--procs", type=int)
    ap.add_argument("--publish", action="store_true", help="also write the top-level results/ files")
    a = ap.parse_args()
    cfg = load(a.config)
    if a.cmd == "plan":
        print(json.dumps(plan(cfg, a.procs), indent=1, default=_default))
    elif a.cmd == "run":
        run(cfg, a.procs)
    elif a.cmd == "analyse":
        from pai.analysis import analyse
        analyse(cfg, out_dir(cfg), publish_to=HERE / "results" if a.publish else None, manifest_fn=manifest)
    else:
        from pai.analysis import refine
        p = refine(cfg, out_dir(cfg))
        print("wrote", p)


if __name__ == "__main__":
    main()
