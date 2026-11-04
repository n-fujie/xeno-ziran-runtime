"""Run the executed experiments of the GAISHO laboratory and save them to docs/gaisho/experiments.json: for every executed domain the record at the full observation (without the bulky shapes and cell lists, which are regenerated
by running the specification), and for the knowledge domain the sensitivity of what can be identified to each axis of the observation, with the classes of what could not be.

    PYTHONPATH=. python scripts/gaisho_experiments.py

SYNTHETIC computational experiments; the domain 004 (body) is specified and not executed."""

from __future__ import annotations

import json
from pathlib import Path

from xzr.gaisho.domains import STATUS
from xzr.gaisho.export import run_experiment
from xzr.gaisho.knowledge import KnowledgeDomain
from xzr.gaisho.lab import FULL, Observation, run_domain

OUT = Path(__file__).resolve().parents[2] / "docs" / "gaisho" / "experiments.json"
SEEDS = list(range(1, 21))

SENSITIVITY = {
    "full observation": {},
    "temporal window 10 trials per cell": {"temporal_window": 10},
    "temporal window 100 trials per cell": {"temporal_window": 100},
    "scale 2 (every second grid point)": {"scale": 2},
    "scale 4 (every fourth grid point)": {"scale": 4},
    "instrument noise 0.3 (a recorded outcome flips with probability 0.3)": {"sensor_noise": 0.3},
    "passive coupling (the operation is only watched along its natural coupling)": {"coupling": "passive"},
    "the cue axis outside the boundary": {"boundary": ["y"]},
    "no memory record": {"memory": False},
    "speed 3 (one snapshot in three)": {"speed": 3},
    "resources: 30 cells": {"resources": 30},
    "observer probe 1.0 (the observation perturbs the operation)": {"probe": 1.0},
    "environment: cue decoupled from the start": {"environment": "cue decoupled from the start"},
    "environment: harder evidence": {"environment": "harder evidence (sigma 1.2)"},
}


def slim(rec: dict) -> dict:
    if not rec.get("executed"):
        return rec
    out = {k: v for k, v in rec.items() if k not in ("shapes", "result")}
    res = rec["result"]
    out["result"] = {"domain": res["domain"], "title": res["title"], "digest": res["digest"], "observation": res["observation"], "seeds": res["seeds"], "conditions": {c: {"accuracy": v["accuracy"], "accuracy_pre_shift": v["accuracy_pre_shift"], "relations": {n: {k: x for k, x in r.items() if k != "per_seed"} for n, r in v["relations"].items()}, "operation_digest": v["operation_digest"]} for c, v in res["conditions"].items()}}
    return out


def sensitivity() -> dict:
    dom = KnowledgeDomain()
    rows = {}
    for name, over in SENSITIVITY.items():
        obs = Observation(**{**FULL.asdict(), **{k: (tuple(v) if isinstance(v, list) else v) for k, v in over.items()}})
        res = run_domain(dom, obs, tuple(SEEDS))
        rows[name] = {"observation": obs.asdict(), "digest": res["digest"], "conditions": {c: {"accuracy": v["accuracy"]["mean"], "relations": {n: (round(r["value"], 3) if r["status"] == "IDENTIFIED" else r["status"]) for n, r in v["relations"].items()}, "operation_digest": v["operation_digest"][:16]} for c, v in res["conditions"].items()}}
    return rows


if __name__ == "__main__":
    out: dict = {"model_version": "gaisho-lab/1", "seeds": SEEDS, "domains": {}, "status": STATUS}
    for dom in ("001-knowledge", "002-bias", "003-freedom", "005-credit", "004-body"):
        seeds = SEEDS[:6] if dom == "005-credit" else SEEDS
        rec = run_experiment({"domain": dom, "seeds": seeds})
        out["domains"][dom] = slim(rec)
        print(dom, "executed" if rec.get("executed") else "NOT EXECUTED", (rec.get("digest") or "")[:12], "negative results:", len(rec.get("negative_results", [])))
    out["knowledge_observation_sensitivity"] = sensitivity()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True))
    print("written", OUT)
