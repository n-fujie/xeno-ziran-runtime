"""Write results/research/preregistration.json: everything frozen before the confirmatory run.

    python -m pai.preregister
"""
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np
import scipy
from xzr.experiments.escalation.runner import provenance

import nonredundancy as NR
import regime_classifier as RC
import run_benchmark as RB
from pai import controllers as C
from pai import episode as E
from pai import perturbations as P
from pai import tracker as T
from pai import world as W

DEV_TOLERANCE = {"acc": 0.42, "acc_adaptive": 0.32, "sensor": 0.03, "pc1": 0.148, "sep": 0.37, "bshare": 0.266}


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main() -> None:
    cfg = RB.load("configs/research.json")
    files = sorted(p for p in Path(".").rglob("*.py") if "results" not in p.parts and "__pycache__" not in p.parts)
    files += [Path(p) for p in ("configs/research.json", "configs/dev.json", "configs/dev_refined.json", "ruff.toml", "PREREGISTRATION.md")
              if Path(p).exists()]
    rt = sorted(Path("../../backend/xzr").rglob("*.py"))
    dev_cells = json.loads(Path("results/dev/summary.json").read_text())["cell_classification"]
    prov = provenance()
    rec = {
        "preregistration_time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "stage": "research (confirmatory)",
        "git": {"head": prov["git_head"], "working_tree_dirty": prov["dirty"],
                "note": "benchmark layer and part of backend/xzr are uncommitted; the exact code is pinned by the per-file "
                        "SHA-256 below and the frozen source archives"},
        "config": {"path": "configs/research.json", "sha256_file": sha("configs/research.json"), "config_hash": RB.config_hash(cfg),
                   "seeds": cfg["seeds"], "severities": cfg["severities"], "extra_severities_from_dev": cfg["extra_severities"],
                   "n_refinement_points": sum(len(v) for v in cfg["extra_severities"].values()),
                   "controllers": cfg["controllers"], "ablations": cfg["ablations"], "ablation_cells": cfg["ablation_cells"]},
        "plan": {k: v for k, v in RB.plan(cfg).items() if k in ("cells", "runs", "procs", "estimated_wall_min")},
        "negative_controls": {"included": True,
                              "per_seed": ["control: severity 0, engine seed s; controllers none/aif_fixed/aif_adaptive/ost + all ablations",
                                           f"noise replicate: severity 0, engine seed s+{cfg['noise_offset']}; "
                                           "controllers none/aif_fixed/aif_adaptive"],
                              "check": "null classification with leave-one-seed-out tolerance (regime_classifier.null_scores)"},
        "classifier": {"HI": RC.HI, "LO": RC.LO, "sensitivity": RC.SENSITIVITY, "scores": RC.SCORES, "raw_quantities": RC.RAW,
                       "phase_probes": RC.PHASE_PROBES, "min_reference": RC.MIN_REF,
                       "rule": "C_AIF = min(scores); >= HI compatible; < LO post; else transition; primary label per cell "
                               "(scores averaged over seeds); noise tolerance = max |control - noise| per raw quantity over all seeds",
                       "development_tolerance_for_sensitivity_analysis": DEV_TOLERANCE},
        "nonredundancy": {"margin": NR.MARGIN, "elements": NR.ELEMENTS, "capabilities": NR.CAPABILITIES, "correction": "Holm"},
        "tracker": {"Z_DETECT": T.Z_DETECT, "window": 20},
        "aif_frozen_parameters": {"GAMMA": C.GAMMA, "DIRICHLET": C.DIRICHLET, "FORGET": C.FORGET, "SURPRISE_WINDOW": C.SURPRISE_WINDOW,
                                  "BASELINE_DECISIONS": C.BASELINE_DECISIONS, "REBUILD_Z": C.REBUILD_Z, "COOLDOWN": C.COOLDOWN,
                                  "N_LEVELS": W.N_LEVELS, "preferences": "C = -2|level - goal|, normalised",
                                  "ost": {"alpha": 0.25, "eps": 0.05}},
        "world": W.WorldConfig().__dict__, "phases": E.PHASES, "actions": W.ACTIONS, "setpoints": W.SETPOINTS,
        "setpoint_period": W.SETPOINT_PERIOD,
        "perturbations": {"registered": list(P.REGISTRY), "aliases": P.ALIASES, "not_implemented": P.NOT_IMPLEMENTED},
        "development_reference_labels": {k: {"label": v["label"], "C_AIF": v["C_AIF"]} for k, v in dev_cells.items()},
        "hardware": RB.hardware(),
        "dependencies": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "runtime_provenance": prov,
        "aif_source": "ziran-xeno-simulator embodied/active_inference @ d4ad6a7544bbb515027e1a97fa914423f01bf8e6 (vendored, test-checked)",
        "file_sha256": {"benchmark": {str(p): sha(p) for p in files},
                        "runtime": {str(p.relative_to("../../backend")): sha(p) for p in rt}},
        "frozen_archives": {p: sha(f"results/research/{p}") for p in ("frozen_source_benchmark.tar.gz", "frozen_source_runtime_xzr.tar.gz")},
    }
    Path("results/research/preregistration.json").write_text(json.dumps(rec, indent=1, default=str))
    print("config_hash", rec["config"]["config_hash"], "| seeds", cfg["seeds"][0], "-", cfg["seeds"][-1], "| refinement points",
          rec["config"]["n_refinement_points"], "| runs", rec["plan"]["runs"])


if __name__ == "__main__":
    main()
