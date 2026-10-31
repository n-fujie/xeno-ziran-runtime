"""Stage 6 follow-up: why the windows that were open at tick 330 close at tick 383-388.

    PYTHONPATH=backend python backend/scripts/meos_experiments_stage6_open_mechanism.py     # about 2 minutes

Reads the A1 energy of the unrepaired coupling run (seeds 1-10): the tick at which it falls below A1's firing cost. Then, as a counterfactual (a change of the *model*, not a repair action), the same pulse at later ticks with A1's upkeep set to 0 in the
initial configuration: if the closure is the exhaustion of A1's energy, the pulse stays effective. Writes docs/ecosystem/experiments_stage6_open_mechanism.json."""

from __future__ import annotations

import json
from pathlib import Path

from xzr.meos import engine as E
from xzr.meos import repair6 as R

DOCS = Path(__file__).resolve().parents[2] / "docs" / "ecosystem"
H = 1200
SIDS = ("coupling gain 0.5",)
SEEDS = tuple(range(1, 11))


def main() -> None:
    cfg0 = E.default_config()["entities"]["A1"]
    cost, upkeep = cfg0["cost"], cfg0["upkeep"]
    st = R.STRESSES[SIDS[0]]
    below, e300 = [], []
    for sd in SEEDS:
        rec = R.run(st, [], sd, 500)
        en = [f["A1"]["energy"] for f in rec["frames"]]
        e300.append(en[300])
        below.append(next((t for t in range(150, len(en)) if en[t] < cost), None))
    cf = []
    for t in (383, 388, 389, 400, 500, 800, 1140):
        rows = []
        for upk in (upkeep, 0.0):
            ok = 0
            for sd in SEEDS:
                cfg = R.config(sd, H)
                cfg["entities"]["A1"]["upkeep"] = upk
                rec = E.run_record(cfg, R.schedule(st, R.build_action("resource.pulse", st, 1.0, t, 0)))
                s = [f["status"] for f in rec["frames"]]
                ref_cfg = R.config(sd, H)
                ref_cfg["entities"]["A1"]["upkeep"] = upk
                ref = E.run_record(ref_cfg, R.schedule(None, []))
                o = R.outcome_at(s, H, t)
                exhausted = rec["traces"]["resource_total"][H - 1] < 0.25 * (ref["traces"]["resource_total"][H - 1] or 1.0)
                ok += bool(o["success"]) and not exhausted
            rows.append({"a1_upkeep": upk, "recovered_of_10": ok})
        cf.append({"pulse_tick": t, "by_upkeep": rows})
        print(t, rows, flush=True)
    out = {"stress": SIDS[0], "a1_firing_cost": cost, "a1_upkeep_per_tick": upkeep, "a1_energy_at_tick_300_unrepaired": {"min": round(min(e300), 3), "max": round(max(e300), 3)}, "tick_a1_energy_below_firing_cost_unrepaired": {"min": min(below), "max": max(below)},
           "counterfactual_resource_pulse_1.0_horizon_1200": cf, "note": "the counterfactual changes the model (A1's upkeep), it is not a repair action; it shows what the closure depends on"}
    (DOCS / "experiments_stage6_open_mechanism.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in out if k != "counterfactual_resource_pulse_1.0_horizon_1200"}))


if __name__ == "__main__":
    main()
