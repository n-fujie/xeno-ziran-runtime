"""Run the MEOS experiments of the XENO ECOSYSTEM specification on the real engine and record what they found.

    python backend/scripts/meos_experiments.py --out docs/ecosystem/experiments.json

Nothing is estimated: every row is a run of xzr.meos (seeded, deterministic), identified by its result digest. The outcomes are properties of MEOS-0 as parameterised in
engine.DEFAULT_CONFIG; they say nothing about any physical or biological ecosystem."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xzr.meos import analysis as A  # noqa: E402
from xzr.meos import engine as E  # noqa: E402


def row(label: str, cfg: dict, ivs: list[dict]) -> dict:
    t0 = time.time()
    rec = E.run_record(cfg, ivs)
    s = A.summarize(rec)
    return {
        "label": label, "interventions": ivs, "status": s["status"], "cycles": s["cycles"], "history_reentry_cycles": s["history_reentry_cycles"],
        "status_trajectory": s["status_log"], "failed_dependency": (s["failed_dependency"] or {}).get("detail"), "final_power": s["final_power"],
        "result_digest": s["result_digest"], "seconds": round(time.time() - t0, 3),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    out_path = Path(ap.parse_args().out)
    cfg = E.default_config()
    exp: dict = {"engine": E.ENGINE_VERSION, "config": cfg, "experiments": {}}
    base = E.run_record(cfg, [])
    exp["experiments"]["deterministic_replay"] = {"digest": base["result_digest"], "replay": E.replay(base), "second_run_digest": E.run_record(cfg, [])["result_digest"],
                                                  "other_seed_digest": E.run_record(E.default_config(seed=2), [])["result_digest"]}
    exp["experiments"]["baseline"] = row("MEOS-0 unperturbed", cfg, [])
    exp["experiments"]["ablation_single"] = A.ablation_table(cfg, None, (1, 2, 3))
    exp["experiments"]["ablation_combinations"] = A.ablation_table(cfg, [["A2", "history"], ["resource_gradient", "history"], ["resource_gradient", "resource_renewal"]], (1,))
    exp["experiments"]["minimal_configuration"] = A.minimal_configuration(cfg, exhaustive=True, horizon=160)
    exp["experiments"]["xenobody_boundaries"] = A.boundary_analysis(cfg)
    exp["experiments"]["history_H_plus_vs_H_minus"] = A.history_comparison(cfg)
    exp["experiments"]["sss"] = A.sss_sweep(cfg)
    exp["experiments"]["address_domain"] = A.address_sweep(cfg)
    iso = [{"tick": 100, "op": "ISOLATE", "target": "interaction_channel"}, {"tick": 150, "op": "RECONNECT", "target": "interaction_channel"}]
    exp["experiments"]["interventions"] = [
        row("A2 removed at tick 100", cfg, [{"tick": 100, "op": "REMOVE", "target": "A2"}]),
        row("interaction channel isolated at 100", cfg, [iso[0]]),
        row("isolated 100, reconnected 150, no pulse (horizon 360)", E.default_config(horizon=360), iso),
        row("isolated 100, reconnected 150, resource pulse 2.0 at 151 (horizon 360)", E.default_config(horizon=360), [*iso, {"tick": 151, "op": "ALTER_RESOURCE", "inject": {"x": 3, "y": 6, "amount": 2.0}}]),
        row("isolated 100, reconnected 150, resource pulse 4.0 at 151 (horizon 360)", E.default_config(horizon=360), [*iso, {"tick": 151, "op": "ALTER_RESOURCE", "inject": {"x": 3, "y": 6, "amount": 4.0}}]),
        row("arena radius 2 at tick 50", cfg, [{"tick": 50, "op": "CHANGE_BOUNDARY", "arena_radius": 2}]),
        row("arena radius 4 at tick 50", cfg, [{"tick": 50, "op": "CHANGE_BOUNDARY", "arena_radius": 4}]),
        row("scale 2 at tick 100", cfg, [{"tick": 100, "op": "ALTER_SSS", "scale": 2.0}]),
        row("infinite-resource control", E.default_config(power={"infinite": True}), []),
        row("infinite-resource control with history removed", E.default_config(power={"infinite": True}), [{"tick": 0, "op": "DISABLE_HISTORY", "mode": "removed"}]),
    ]
    exp["experiments"]["observation"] = {str(k): {kk: v for kk, v in A.observe(base, {"sampling_interval": k}).items() if kk != "observed_trajectory"} for k in (1, 2, 4, 8)}
    out_path.write_text(json.dumps(exp, indent=1))
    print(out_path, out_path.stat().st_size)
    for k, v in exp["experiments"].items():
        if k == "interventions":
            for r in v:
                print("  ", r["label"], "->", r["status"], r["cycles"])


if __name__ == "__main__":
    main()
