"""Exploratory counterfactual trace of history reinsertion in HPO-002 condition D (NOT pre-registered; tests nothing).

    python backend/scripts/hpo_history_trace.py [--seeds 32] [--procs 4]

For each of the first ``--seeds`` confirmatory HPO-002 seeds, condition D runs as in the confirmatory experiment. At
every reinsertion moment the whole field (world, operations, archive, causal history) is deep-copied just before the
step, and the copy takes that one step without that reinsertion (all of it, or only one of its three components:
archived data → memory, archived veils → observation, earlier ignition parameters → ignition conditions). Both
branches then continue, unchanged otherwise, and are compared after 1, 10 and 30 steps on the path the reinsertion
should travel:

    entry        memory and effective thresholds of the configurations that received data; ignition parameters
    ignition     fired evaluations of the operations; operations whose ignition status differs
    acts         runtime records applied (intervention selection)
    world        field ignitions, connections, reachable share; any bit difference at all (fingerprint)
    cessation    cessations / re-ignitions in the window

Same exogenous and endogenous streams in both branches: any difference is caused by the skipped reinsertion and by
how the dynamics carry it. Writes backend/experiments/results/hpo/history_trace.json.
"""

from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from xzr.hpo import experiments as X  # noqa: E402
from xzr.hpo.field import Field  # noqa: E402

WINDOWS = (1, 10, 30)
VARIANTS = {"all": None, "data": "data", "veils": "veils", "params": "params"}


def snap(f: Field, nodes: np.ndarray) -> dict:
    st = f.world.state
    by = f.history.summary()["by_type"]
    return {"memory_nodes": st.memory[nodes].copy() if len(nodes) else np.zeros(0),
            "theta_nodes": st.theta_eff()[nodes].copy() if len(nodes) else np.zeros(0),
            "ign_params": {o.oid: json.dumps(o.ign, sort_keys=True) for o in f.live()},
            "status": {o.oid: o.status for o in f.live()}, "fired": f.stats["evaluations"]["FIRED"],
            "applied": sum(f.stats["applied"].values()), "field_ign": f.world.total_ignitions,
            "alive": int(st.alive.sum()), "reach": float(st.reachable_mask().mean()),
            "cease": by.get("cease", 0), "reignite": by.get("reignite", 0), "transform": by.get("transform", 0),
            "fp": f.world.engine.fingerprint()}


def diff(a: dict, b: dict) -> dict:
    keys = set(a["ign_params"]) | set(b["ign_params"])
    return {"memory_nodes_abs": float(np.abs(a["memory_nodes"] - b["memory_nodes"]).mean()) if len(a["memory_nodes"]) else 0.0,
            "theta_nodes_abs": float(np.abs(a["theta_nodes"] - b["theta_nodes"]).mean()) if len(a["theta_nodes"]) else 0.0,
            "ops_with_other_ign_params": sum(a["ign_params"].get(k) != b["ign_params"].get(k) for k in keys),
            "ops_with_other_status": sum(a["status"].get(k) != b["status"].get(k) for k in keys),
            "fired": a["fired"] - b["fired"], "applied": a["applied"] - b["applied"],
            "field_ign": a["field_ign"] - b["field_ign"], "alive": a["alive"] - b["alive"],
            "reach": a["reach"] - b["reach"], "cease": a["cease"] - b["cease"],
            "reignite": a["reignite"] - b["reignite"], "transform": a["transform"] - b["transform"],
            "bit_different": a["fp"] != b["fp"]}


def job(i: int) -> dict:
    gen0, seed0 = X.RANGES["hpo002"]
    gen, seed = gen0 + i, seed0 + i
    base = X._warm(X.WORLD, gen, seed, X.WARMUP)
    s = X.settings_for("D")
    f = Field(base.fork(), s, seed, keep_states=False)
    h = f.s["history"]
    out: list[dict] = []
    for _ in range(X.HORIZON):
        t_next = f.world.t + 1
        due = (t_next - f.t0 >= h["lag"]) and (t_next - f.t0) % h["every"] == 0
        if due and X.HORIZON - (t_next - f.t0) >= 1:
            pre = len(f.history.events)
            branches = {}
            for name, comp in VARIANTS.items():
                g = copy.deepcopy(f)
                if comp is None:
                    g.s["history"]["reinsert"] = False
                else:
                    g.s["history"][comp] = False
                g.step()
                g.s["history"] = copy.deepcopy(f.s["history"])
                branches[name] = g
            f.step()
            rein = [e for e in f.history.events[pre:] if e["type"] == "reinsert"]
            nodes = np.unique(np.concatenate([a["nodes"] for a in f.archive
                                              if a.get("what") == "datum" and f.world.t - a["t"] >= h["lag"]][-3:]
                                             or [np.zeros(0, np.int32)])).astype(np.int32)
            rec: dict = {"t": f.world.t - f.t0, "reinsertions": [(e.get("detail") or {}).get("what") for e in rein],
                         "windows": {}}
            ref = copy.deepcopy(f)
            sims = {"D": ref, **branches}
            steps_done = 1
            for w in WINDOWS:
                for _ in range(w - steps_done):
                    if sims["D"].world.t - f.t0 >= X.HORIZON:
                        break
                    for g in sims.values():
                        g.step()
                steps_done = w
                a = snap(sims["D"], nodes)
                rec["windows"][str(w)] = {name: diff(a, snap(g, nodes)) for name, g in branches.items()}
            out.append(rec)
        else:
            f.step()
    return {"i": i, "moments": out}


def aggregate(jobs: list[dict]) -> dict:
    res: dict = {}
    for w in map(str, WINDOWS):
        res[w] = {}
        for name in VARIANTS:
            rows = [m["windows"][w][name] for j in jobs for m in j["moments"] if w in m["windows"]]
            if not rows:
                continue
            res[w][name] = {"moments": len(rows), **{k: float(np.mean([r[k] for r in rows]))
                                                     for k in rows[0] if k != "bit_different"},
                            "abs_field_ign": float(np.mean([abs(r["field_ign"]) for r in rows])),
                            "abs_fired": float(np.mean([abs(r["fired"]) for r in rows])),
                            "bit_different_share": float(np.mean([r["bit_different"] for r in rows]))}
    kinds: dict[str, int] = {}
    for j in jobs:
        for m in j["moments"]:
            for k in m["reinsertions"]:
                kinds[str(k)] = kinds.get(str(k), 0) + 1
    return {"by_window": res, "reinsertions_executed": kinds}


def main() -> None:
    seeds = int(sys.argv[sys.argv.index("--seeds") + 1]) if "--seeds" in sys.argv else 32
    procs = int(sys.argv[sys.argv.index("--procs") + 1]) if "--procs" in sys.argv else 4
    t = time.time()
    jobs = X.run_pool(job, list(range(seeds)), procs)
    doc = {"status": "exploratory counterfactual trace (not pre-registered; tests no hypothesis)", "seeds": seeds,
           "seed_ranges": {"generator": X.RANGES["hpo002"][0], "engine": X.RANGES["hpo002"][1]},
           "windows_steps": WINDOWS, "variants": list(VARIANTS), "results": aggregate(jobs),
           "elapsed_s": round(time.time() - t, 1), "protocol_sha256": X.protocol_hash()}
    X.write("history_trace", doc)
    print(json.dumps(X.clean(doc["results"]), indent=1)[:4000])


if __name__ == "__main__":
    main()
