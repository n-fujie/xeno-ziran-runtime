"""Run the second-stage MEOS experiments at full size and record what they found (docs/ecosystem/experiments_stage2.json).

    python backend/scripts/meos_experiments_v2.py --out docs/ecosystem/experiments_stage2.json [--quick]

Every row is a run of xzr.meos (seeded, deterministic) identified by its result and trace digests. Seeds per experiment are stated in the output. Nothing is selected,
smoothed or re-run until it agrees with an expectation; a null result, a reversed effect, a conditional necessity, several minimal sets and a non-monotone response are
kept as found. The outcomes are properties of the formal model MEOS-0, not claims about any physical or biological ecosystem."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xzr.meos import analysis as A  # noqa: E402
from xzr.meos import engine as E  # noqa: E402
from xzr.meos import experiments as X  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--quick", action="store_true", help="few seeds and a coarse grid (a smoke run, not the recorded evidence)")
    a = ap.parse_args()
    q = a.quick
    cfg = E.default_config()
    out: dict = {"engine": E.ENGINE_VERSION, "quick": q, "baseline_config": cfg, "experiments": {}, "timing_seconds": {}}
    seeds10, seeds5, seeds3 = tuple(range(1, 4 if q else 11)), tuple(range(1, 3 if q else 6)), tuple(range(1, 3 if q else 4))

    def step(name: str, fn):
        t = time.time()
        out["experiments"][name] = fn()
        out["timing_seconds"][name] = round(time.time() - t, 1)
        print(f"{name}: {out['timing_seconds'][name]} s", flush=True)

    base = E.run_record(cfg, [])
    out["experiments"]["baseline"] = {"result_digest": base["result_digest"], "trace_digest": base["trace_digest"], "state": base["final_status"]["label"], "cycles": len(base["cycles"]), "replay": E.replay(base)}
    step("causal_paths", lambda: {
        "A2 removed at 100": X.causal_path(cfg, [{"tick": 100, "op": "REMOVE", "target": "A2"}]),
        "history removed at 0 (finite power)": X.causal_path(cfg, [{"tick": 0, "op": "REMOVE", "target": "history"}]),
        "interaction channel cut at 100": X.causal_path(cfg, [{"tick": 100, "op": "ISOLATE", "target": "interaction_channel"}]),
        "resource renewal removed at 0": X.causal_path(cfg, [{"tick": 0, "op": "REMOVE", "target": "resource_renewal"}]),
        "address loss of A2 at 100": X.causal_path(cfg, [{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "loss"}]),
        "scale 1.5 at 100": X.causal_path(cfg, [{"tick": 100, "op": "ALTER_SSS", "scale": 1.5}]),
    })
    step("factorial_history_gradient_power", lambda: X.factorial_history_gradient_power(cfg, seeds10))
    step("history_necessity_map", lambda: X.history_necessity_map(cfg, seeds=seeds3 if not q else (1,)))
    step("minimal_configurations_finite_power", lambda: X.minimal_configurations(cfg, seeds=(1,) if q else (1, 2, 3), horizon=160 if q else 200))
    if not q:
        step("minimal_configurations_unlimited_power", lambda: X.minimal_configurations(X.cfg_with(cfg, power=X.POWER_UNLIMITED), seeds=(1, 2, 3), horizon=200))
        step("minimal_configurations_observed_interval_1", lambda: X.minimal_configurations(cfg, seeds=(1,), horizon=160, observation={"sampling_interval": 1}))
        step("minimal_configurations_observed_interval_2", lambda: X.minimal_configurations(cfg, seeds=(1,), horizon=160, observation={"sampling_interval": 2}))
    step("observation", lambda: {
        name: A.observe(base, obs) | {"observed_trajectory": None}
        for name, obs in {
            "full": {}, "interval 2": {"sampling_interval": 2}, "interval 4": {"sampling_interval": 4}, "spatial stride 2": {"spatial_stride": 2}, "region excluding the habitat": {"region": [0, 0, 1, 1]},
            "aggregation 6": {"aggregation": 6}, "aggregation 24": {"aggregation": 24}, "window 6": {"window": 6}, "window 12": {"window": 12}, "interval 2 + stride 2": {"sampling_interval": 2, "spatial_stride": 2},
        }.items()
    })
    step("boundary_experiments", lambda: {"kinds": X.boundary_experiments(cfg, seeds3), "closure": X.body_closure(cfg)})
    amounts = tuple(round(0.25 * i, 2) for i in range(0, 25 if not q else 9, 1 if not q else 3))
    step("recovery_interaction_cut", lambda: X.recovery_phase(cfg, amounts, seeds5, "interaction cut 100-150"))
    step("recovery_a2_removed", lambda: X.recovery_phase(cfg, amounts, seeds5, "A2 removed 100-150"))
    step("sss_phase", lambda: X.sss_phase(cfg, (0.5, 1.0, 1.5) if q else (0.5, 1.0, 1.5), (1.0, 2.0) if q else (0.5, 1.0, 1.5, 2.0), (0.5, 1.0, 2.0) if q else (0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0), (1,) if q else (1, 2, 3)))
    step("address_domain", lambda: X.address_experiments(cfg, seeds5))
    step("m2_connection", lambda: X.m2_experiment(cfg, seeds5))
    step("philosophical_operations", lambda: X.phil_experiment(cfg, seeds5))
    Path(a.out).write_text(json.dumps(out, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print(a.out, Path(a.out).stat().st_size)


if __name__ == "__main__":
    main()
