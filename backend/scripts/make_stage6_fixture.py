"""Frontend fixtures of the sixth stage: real repair blocks produced by the engine (a pulse that recovers, one that overshoots, a temporary bridge, a controller's decision, a stress with no available action, a repair after the collapse).

    PYTHONPATH=backend python backend/scripts/make_stage6_fixture.py"""

from __future__ import annotations

import json
from pathlib import Path

from xzr.meos import repair6 as R
from xzr.meos import repair_ctl as RCTL
from xzr.meos import repair_events as RE

OUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "views" / "ecosystem" / "__fixtures__" / "meos-stage6-repair.json"


def block(stress_id: str, parts: list[tuple[str, float, int]], t: int, seed: int = 1, ctl: RCTL.RepairController | None = None, irr: int | None = None) -> dict:
    st = R.STRESSES[stress_id]
    reps: list[dict] = []
    for a, m, d in parts:
        reps += R.build_action(a, st, m, t, d)
    base = R.schedule(st, sorted(reps, key=lambda i: i["tick"]))
    rec = RCTL.run_repaired(R.config(seed), base, ctl)
    inj = [i for i in rec["interventions"] if i not in base]
    ev = R.evaluate(rec, R.reference(seed), [*reps, *inj], min([t] if parts else [113]))
    acts = [{"action": a, "magnitude": m, "duration": d, "t": t} for a, m, d in parts]
    return RE.build(st, 100, acts, rec, ev, rec["controller"]["log"] if ctl else None, irr)


def main() -> None:
    out = {
        "recovered": block("coupling gain 0.5", [("resource.pulse", 1.0, 0)], 113), "overshoot": block("coupling gain 0.5", [("resource.pulse", 4.0, 0)], 113, irr=141), "bridge": block("coupling gain 0.5", [("coupling.bridge", 1.5, 20)], 104),
        "controller": block("history lost", [], 113, ctl=RCTL.RepairController("rule_based", [], seed=1)), "no_action_available": block("Address partial 0.5", [], 113, ctl=RCTL.RepairController("cost_aware", [], seed=1)),
        "late_recovery": block("coupling gain 0.5", [("resource.pulse", 1.0, 0)], 160),
    }
    OUT.write_text(json.dumps(out))
    for k, v in out.items():
        print(k, [(e["kind"], e["tick"]) for e in v["events"]], v["evaluation"]["horizons"]["long"]["outcome"], "attempts", v["controller"]["attempts"])


if __name__ == "__main__":
    main()
