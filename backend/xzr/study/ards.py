"""Bridge to ARDS (the autonomous R&D system in pa-simulation-environment) as a research module of the study workflow.

What this is: ARDS's own arms (EXISTING-blind, V1 / V2 PA, history and rule-revision ablations, fixed strategies, the oracle reference)
run on ARDS's own environments, driven from a study protocol so that they share the study's seeds bookkeeping, run store, analysis,
Methods / Results text and reproduction. The arm code is ARDS's, executed unchanged in a separate process (vite-node).

What this is not:
  * ARDS arms do not run on the HPO world of this runtime: that would be a new environment with its own ground truth and its own
    validation, and there is no earlier specification of one ("Environment 3" in earlier notes was a proposal only).
  * Environment ``env1`` is ARDS's XB-TRO backend (a Ziran-runtime variant in the xeno-ziran-runtime-xb-tro worktree); ``env2`` is its
    coupled-oscillator network (TypeScript). Both are ARDS's definitions.
  * Only ARDS's software-test mode is used (replicates 3980-3989): its study gate refuses exploration without the owner's go-ahead file
    and study mode without a frozen protocol, and this bridge passes neither. Results of this environment are therefore functional
    checks, never evidence, and nothing is written into the ARDS repository (frozen Phase 3 assets and Phase 4 records are untouched).
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from ..hpo.experiments import clean

HERE = Path(__file__).resolve().parent / "ards_bridge"
JOB = HERE / "ards_job.ts"
REGISTRY = HERE / "ards_registry.json"
SHUFFLED = ("V1-PA-shuffled", "V2-PA-shuffled")  # need another replicate's run: not available through the bridge


def ards_root() -> Path:
    return Path(os.environ.get("XZR_ARDS_ROOT", Path(__file__).resolve().parents[4] / "pa-simulation-environment"))


def node_dir() -> str | None:
    n = os.environ.get("XZR_NODE") or shutil.which("node")
    if n:
        return str(Path(n).parent)
    found = sorted(glob.glob(str(Path.home() / ".nvm" / "versions" / "node" / "*" / "bin" / "node")))
    return str(Path(found[-1]).parent) if found else None


def available() -> str | None:
    """None if the bridge can run, else the reason it cannot."""
    root = ards_root()
    if not (root / "src" / "ards" / "loop2" / "index.ts").is_file():
        return f"ARDS repository not found at {root} (set XZR_ARDS_ROOT)"
    if not (root / "node_modules" / ".bin" / "vite-node").exists():
        return f"vite-node is not installed in {root}"
    if node_dir() is None:
        return "node is not installed (set XZR_NODE)"
    return None


@lru_cache(maxsize=1)
def registry() -> dict:
    return json.loads(REGISTRY.read_text())


def arm_spec(arm_id: str) -> dict | None:
    return next((a for a in registry()["arms"] if a["id"] == arm_id), None)


def profile(arm: dict, env: dict) -> dict:
    """The fairness profile of an ARDS arm, from ARDS's own registry (what it reads, what it may revise, which factors it has)."""
    spec = arm_spec(arm["ards"]["arm"]) or {}
    f = spec.get("factors", {})
    return {
        "information": {"reads": spec.get("reads"), "environment": env.get("ards_env")},
        "revision_authority": sorted(spec.get("mayRevise", [])) or "none",
        "controller": f.get("observationChange"),  # what the arm does with the observation configuration (the role is a label)
        "meta_revision": f.get("ruleRevision") == "meta",
        "history_reinsertion": f.get("reinjection") in ("own", "shuffled", "uninformative"),
        "max_changes_per_epoch": None,
        "interventions": 0,
        "compute": {"warmup": None, "horizon": None, "epoch": None, "systems": None, "ards_env": env.get("ards_env")},
    }


def validate(doc: dict) -> list[str]:
    issues: list[str] = []
    env = doc["environment"]
    if env.get("ards_env") not in registry()["envs"]:
        issues.append(f"environment.ards_env must be one of {registry()['envs']}")
    if doc.get("mode") != "functional":
        issues.append(
            "ards: only functional studies are available through the bridge (ARDS software-test replicates 3980-3989); "
            "exploration and study runs are gated by the ARDS owner records and are not started from here"
        )
    for a in doc["arms"]:
        ards = a.get("ards") or {}
        if not ards.get("arm"):
            issues.append(f"arm {a['name']}: ards.arm (an ARDS arm id) is required")
        elif arm_spec(ards["arm"]) is None:
            issues.append(f"arm {a['name']}: unknown ARDS arm {ards['arm']!r}")
        elif ards["arm"] in SHUFFLED:
            issues.append(f"arm {a['name']}: {ards['arm']} needs another replicate's run and is not available through the bridge")
    seeds = doc.get("seeds", {})
    if "list" not in seeds:
        issues.append("ards: seeds must be an explicit list of [replicate, replicate] pairs inside 3980-3989")
    return issues


def metric_values(m: dict, verification_failed: list) -> dict:
    """Flat metrics of one ARDS arm run: readable aliases for the primary families, and every numeric leaf under its path."""
    flat: dict[str, float | None] = {}

    def walk(prefix: str, x) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                walk(f"{prefix}_{k}" if prefix else k, v)
        elif isinstance(x, bool) or isinstance(x, int | float):
            flat[prefix] = float(x)
        elif x is None:
            flat[prefix] = None

    walk("", {k: v for k, v in m.items() if k not in ("armId", "envId", "replicate")})
    b, c, d = m["B_identification"], m["C_budget"], m["D_followUp"]
    alias = {
        "unseen_coverage": b["unseen"]["coverage"],
        "seen_coverage": b["seen"]["coverage"],
        "all_coverage": b["all"]["coverage"],
        "unseen_fdr": b["unseen"]["fdr"],
        "unseen_recall": b["unseen"]["recall"],
        "unseen_wrong_sign_rate": b["unseen"]["wrongSignRate"],
        "body_runs": c["bodyRuns"],
        "setup_seconds": c["setupSecondsSpent"],
        "adopted": d["adopted"],
        "changes_applied": d["changesApplied"],
        "capable_gained": m["A_observability"]["capableGainedOverDefault"],
        "verification_failed": len(verification_failed),
    }
    return {**flat, **{k: (None if v is None else float(v)) for k, v in alias.items()}}


def run_ards(doc: dict, arm: dict, gen: int, seed: int) -> dict:
    import resource
    import sys
    import time

    t0 = time.time()
    why = available()
    if why:
        raise RuntimeError(why)
    env = doc["environment"]
    root = ards_root()
    job = {"env": env["ards_env"], "arm": arm["ards"]["arm"], "replicate": gen}
    penv = {**os.environ, "XZR_ARDS_ROOT": str(root), "PATH": f"{node_dir()}:{os.environ.get('PATH', '')}"}
    cmd = [str(root / "node_modules" / ".bin" / "vite-node"), str(JOB), "--", "run", json.dumps(job)]
    timeout = float(doc["stop"]["timeout_per_run_s"])
    try:
        p = subprocess.run(cmd, cwd=root, env=penv, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"ARDS job exceeded {timeout:g} s") from e
    lines = [x for x in p.stdout.splitlines() if x.startswith("{")]
    if p.returncode != 0 or not lines:
        raise RuntimeError(f"ARDS job failed (exit {p.returncode}): {(p.stderr or p.stdout).strip()[-600:]}")
    out = json.loads(lines[-1])
    rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    rec = {
        "schema": "xzr.studyrun/1",
        "arm": arm["name"],
        "gen": gen,
        "seed": seed,
        "status": "ok",
        "metrics": metric_values(out["metrics"], out["verificationFailed"]),
        "controller": None,
        "protocol_changes": [],
        "reachability_check": None,
        "history_reentry": None,
        "ards": {
            "arm": job["arm"],
            "env": job["env"],
            "replicate": gen,
            "mode": "test",
            "spec": out["spec"],
            "verification_checks": len(out["verification"]),
            "verification_failed": out["verificationFailed"],
            "run_summary": out["runSummary"],
            "default_held_out": out["default"],
            "ards_wall_s": out["wallSeconds"],
            "ards_commit": _git(root),
            "note": "software-test replicate; not study data",
        },
        "wall_s": round(time.time() - t0, 4),
        "peak_rss_mb": round(rss / (1 << 20) if sys.platform == "darwin" else rss / 1024, 1),
    }
    return clean(rec)


def _git(root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10, check=False
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
