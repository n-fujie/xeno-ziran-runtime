"""Run the executed experiments of the GAISHO laboratory and save them to docs/gaisho/experiments.json: for every executed domain the record at the full observation (without the bulky shapes and cell lists, which are regenerated
by running the specification), and for the knowledge domain the sensitivity of what can be identified to each axis of the observation, with the classes of what could not be.

    PYTHONPATH=. python scripts/gaisho_experiments.py

    XZR_XBTRO_PATH=<...>/backend/xzr/xbtro PYTHONPATH=. python scripts/gaisho_experiments.py body     # domain 004, all five body conditions (needs the XB-TRO package): docs/gaisho/experiments_body.json
    XZR_XBTRO_PATH=... XZR_XENOSNN_URL=http://127.0.0.1:<port> PYTHONPATH=. python scripts/gaisho_experiments.py body-snn   # B2, the open-loop replay through a running XenoSNN server: docs/gaisho/experiments_body_snn.json

    XZR_XBTRO_PATH=... PYTHONPATH=. python scripts/gaisho_experiments.py body-matched   # the two XB-TRO presets compared one block of the configuration at a time (Dictionary 060): docs/gaisho/experiments_body_matched.json

SYNTHETIC computational experiments; the domain 004 (body) runs only where the XB-TRO link is configured, and is otherwise specified and not executed."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from xzr.gaisho.domains import STATUS
from xzr.gaisho.export import run_experiment
from xzr.gaisho.knowledge import KnowledgeDomain
from xzr.gaisho.lab import FULL, Observation, run_domain

OUT = Path(__file__).resolve().parents[2] / "docs" / "gaisho" / "experiments.json"
SEEDS = list(range(1, 21))
BODY_OUT = OUT.with_name("experiments_body.json")

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


SNN_OUT = OUT.with_name("experiments_body_snn.json")
MATCHED_OUT = OUT.with_name("experiments_body_matched.json")

if __name__ == "__main__" and sys.argv[1:] == ["body-matched"]:
    from xzr.gaisho.bodymatched import run_matched
    from xzr.gaisho.domains import domain_registry

    if domain_registry()["004-body"] is None:
        raise SystemExit("the body domain is not executed: set XZR_XBTRO_PATH to the xbtro package")
    _m = run_matched(SEEDS[:6])
    MATCHED_OUT.write_text(json.dumps(_m, indent=1, sort_keys=True))
    print("body-matched", _m["digest"][:12], "uncovered:", _m["uncovered_differences"], "written", MATCHED_OUT)
    raise SystemExit(0)


if __name__ == "__main__" and sys.argv[1:] == ["body-snn"]:
    from xzr.gaisho.bodysnn import replay_cell
    from xzr.gaisho.domains import BodyDomain, domain_registry

    dom = domain_registry()["004-body"]
    if not isinstance(dom, BodyDomain):
        raise SystemExit("the body domain is not executed: set XZR_XBTRO_PATH to the xbtro package")
    recs = [replay_cell(dom, c, 2, 2, [1, 2, 3, 4]) for c in ("human-like planar body", "machine-like planar body")]
    SNN_OUT.write_text(json.dumps({"model_version": "gaisho-lab/1", "records": recs}, indent=1, sort_keys=True))
    print("body-snn", [r["digest"][:12] for r in recs], "written", SNN_OUT)
elif __name__ == "__main__" and sys.argv[1:] == ["body"]:
    from xzr.gaisho.domains import BodyDomain, domain_registry

    _b = domain_registry()["004-body"]
    rec = run_experiment({"domain": "004-body", "seeds": SEEDS[:6], "conditions": list(_b.conditions) if isinstance(_b, BodyDomain) else None})
    if not rec.get("executed"):
        raise SystemExit("the body domain is not executed: set XZR_XBTRO_PATH to the xbtro package")
    BODY_OUT.write_text(json.dumps({"model_version": "gaisho-lab/1", "seeds": SEEDS[:6], "domain": slim(rec)}, indent=1, sort_keys=True))
    print("body", rec["digest"][:12], "negative results:", len(rec["negative_results"]), "written", BODY_OUT)
elif __name__ == "__main__":
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
