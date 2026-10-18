"""Run the same XB-TRO request sequence over the transports that run on a desktop and compare with a recording from another.

    python backend/scripts/xbtro_paths.py [pyodide_s1.json]

Sequence S1: create a human-like body (2 seeds, seed 11, horizon 6 s, full observation), step 50 x 12, apply a 60 N push after the
4th chunk, and record per chunk the last frame (reference COM, COP, energy, controller estimate, joint angles) and the last
observation sample of every model. Run over (a) HTTP (the FastAPI app through its test client) and (b) the native bridge
(``bridge.handle``: the same code the iOS app embeds). With a file argument recorded in the browser (Pyodide) it compares that
too. The recording stores values rounded to 6 decimals, so the comparison is at that resolution.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def s1(call) -> dict:
    ws = call("POST", "/api/xbtro/workspaces", {})["id"]
    b = call(
        "POST",
        f"/api/xbtro/workspaces/{ws}/bodies",
        {"preset": "human-like-planar", "n_seeds": 2, "seed": 11, "horizon_s": 6, "observation": {"name": "full"}},
    )
    out: dict = {"stability": b["numeric_stability"]["margin"], "frames": [], "obs": {}}
    last = None
    for i in range(12):
        if i == 4:
            call(
                "POST",
                f"/api/xbtro/workspaces/{ws}/bodies/{b['id']}/command",
                {"type": "intervention", "id": "perturbation", "magnitude": 60},
            )
        last = call("POST", f"/api/xbtro/workspaces/{ws}/bodies/{b['id']}/step", {"n": 50})
        f = last["frames"][-1]
        out["frames"].append(
            {
                "t": f["t"],
                "com": f["reference"]["com"],
                "cop": f["reference"]["cop"],
                "energy": f["reference"]["energy"],
                "est": f["estimates"]["controller"]["com"],
                "push": max(x["reference"]["push_force"][0] for x in last["frames"]),
                "theta0": f["reference"]["theta"][0],
            }
        )
        for k, v in last["observation"].items():
            idx = len(v["x"][0]) - 1
            out["obs"][k] = {"n": out["obs"].get(k, {}).get("n", 0) + len(v["t"]), "lastT": v["t"][idx], "last": v["x"][0][idx]}
    out["status"] = last["status"]
    return out


def http_call():
    from fastapi.testclient import TestClient

    from xzr.service.app import app

    c = TestClient(app)

    def call(method, path, body=None):
        r = c.request(method, path, json=body) if body is not None else c.request(method, path)
        assert r.status_code == 200, (path, r.status_code, r.text[:200])
        return r.json()

    return call


def bridge_call():
    from xzr.native import bridge

    def call(method, path, body=None):
        r = json.loads(bridge.handle(json.dumps({"method": method, "path": path, "body": body})))
        assert r["status"] == 200, (path, r)
        return r["body"]

    return call


def flat(d: dict) -> dict[str, float]:
    out: dict[str, float] = {}

    def walk(x, p):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, f"{p}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{p}[{i}]")
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            out[p] = float(x)
        elif x is None:
            out[p] = float("nan")
        elif isinstance(x, bool):
            out[p] = float(x)

    walk(d, "")
    return out


def compare(name_a: str, a: dict, name_b: str, b: dict) -> dict:
    fa, fb = flat(a), flat(b)
    keys = sorted(set(fa) & set(fb))
    missing = sorted(set(fa) ^ set(fb))
    diffs = np.array([abs(fa[k] - fb[k]) if not (np.isnan(fa[k]) and np.isnan(fb[k])) else 0.0 for k in keys])
    worst = int(diffs.argmax()) if len(diffs) else 0
    return {
        "pair": f"{name_a} vs {name_b}",
        "values_compared": len(keys),
        "structural_differences": missing[:5],
        "max_abs_difference": float(diffs.max()) if len(diffs) else 0.0,
        "worst": keys[worst] if keys else None,
        "identical": bool((diffs == 0).all() and not missing),
    }


if __name__ == "__main__":
    runs = {"http": s1(http_call()), "bridge": s1(bridge_call())}
    if len(sys.argv) > 1:
        runs["pyodide"] = json.loads(Path(sys.argv[1]).read_text())

    def rnd(x):
        return (
            round(x, 6)
            if isinstance(x, float)
            else [rnd(v) for v in x]
            if isinstance(x, list)
            else {k: rnd(v) for k, v in x.items()}
            if isinstance(x, dict)
            else x
        )

    names = list(runs)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            print(json.dumps(compare(names[i], rnd(runs[names[i]]), names[j], rnd(runs[names[j]]))))
