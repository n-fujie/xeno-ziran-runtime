"""The stage-five fixture of the frontend: a controlled MEOS run (adaptive reconfiguration, coupling weakened at tick 100, a hand-made two-route library whose second route needs the M2 tap),
with the backend's route topology of it, so that the TypeScript reading (``routeGraph.ts``) is tested against the Python one on the same record.

    PYTHONPATH=. python scripts/make_stage5_fixture.py"""

from __future__ import annotations

import json
from pathlib import Path

from xzr.meos import engine as E
from xzr.meos import mfs5 as M
from xzr.meos import reconf as RC
from xzr.meos import routes5 as R

CORE = ["A2", "interaction_channel", "sensor_resource", "sensor_alteration", "environmental_persistence", "feedback", "resource_renewal"]
N = {"history": "ok", "coupling": "normal", "resource": "normal", "renewal": "normal", "address": "ok", "tap": "direct"}
LIB = [
    {"id": "L-BASE", "condition_id": "B", "features": dict(N), "retained": CORE, "cardinality": 7},
    {"id": "L-WEAK", "condition_id": "W", "features": {**N, "coupling": "weak"}, "retained": [*CORE, "m2_tap"], "cardinality": 8},
]
arr = {"tap": M.M2_BASE, "tap_feature": "direct", "universe": M.COMPONENTS5}
ivs = [{"tick": 0, "op": "ROUTE", "m2": {"sense": "none"}}, {"tick": 100, "op": "REMOVE", "target": "history"}, {"tick": 100, "op": "RECONFIGURE", "path": "coupling.gain", "value": 0.3}]
rec = RC.run_controlled(E.default_config(seed=1, horizon=300), ivs, RC.Controller("adaptive", LIB, arr))
out = {"record": {k: v for k, v in rec.items() if k != "fields"}, "topology": R.topology(rec), "library": [{**m, "condition": m["condition_id"], "removed": [], "route_kind": "", "retained_paths": [], "lost_paths": [], "digest": ""} for m in LIB], "outcomes": RC.switch_outcomes(rec, 100)}
out["record"]["fields"] = {"grid": 14, "channels": ["R", "M1", "M2"], "encoding": "", "r_top": 1.5, "b64": ""}
(Path(__file__).resolve().parents[2] / "frontend" / "src" / "views" / "ecosystem" / "__fixtures__" / "meos-stage5-controlled.json").write_text(json.dumps(out, separators=(",", ":")))
print("switches", rec["controller"]["switches"], [e["to"] for e in rec["controller"]["log"] if e["kind"] == "switch"], "final", rec["final_status"]["label"])
