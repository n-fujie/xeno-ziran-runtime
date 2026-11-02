"""Write the MEOS records the frontend tests read (frontend/src/views/ecosystem/__fixtures__/):

  meos-a2-removed.json   the stage-one record (engine meos-0.1, no traces): the default configuration, seed 1, 150 ticks, A2 removed at tick 60. It is kept as it was
                         written so that the view keeps reading records that predate the stage-two fields.
  meos-stage2.json       a stage-two record (this engine): seed 1, 260 ticks, Philosophical operations in ``revision`` mode, the interaction channel cut at 100 and
                         restored at 150, a resource pulse at 151, the renewal efficiency lowered at 190, A2's addressable window fragmented at 200 and restored at 225.
                         It collapses, recovers and collapses again.

Both are real engine records (the digests in them are the engine's); regenerate the second with
    python backend/scripts/make_meos_fixture.py
(the first is only rewritten with --stage1, and only an engine that still produces meos-0.1 records would reproduce it)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from xzr.meos import engine as E  # noqa: E402

FIX = ROOT / "frontend/src/views/ecosystem/__fixtures__"
if "--stage1" in sys.argv:
    rec = E.run_record(E.default_config(horizon=150), [{"tick": 60, "op": "REMOVE", "target": "A2"}])
    (FIX / "meos-a2-removed.json").write_text(json.dumps(rec, separators=(",", ":")))
    print("stage 1", rec["engine"], rec["final_status"]["label"], rec["result_digest"])

cfg = E.default_config(horizon=260)
cfg["phil"] = {"mode": "revision"}
ivs = [
    {"tick": 100, "op": "ISOLATE", "target": "interaction_channel"},
    {"tick": 150, "op": "RECONNECT", "target": "interaction_channel"},
    {"tick": 151, "op": "ALTER_RESOURCE", "inject": {"x": 3, "y": 6, "amount": 2.0}},
    {"tick": 190, "op": "RECONFIGURE", "path": "environment.renew_efficiency", "value": 0.85},
    {"tick": 200, "op": "ADDRESS", "target": "A2", "mode": "fragment", "fraction": 0.5},
    {"tick": 225, "op": "ADDRESS", "target": "both", "mode": "restore"},
]
rec = E.run_record(cfg, ivs)
out = FIX / "meos-stage2.json"
out.write_text(json.dumps(rec, separators=(",", ":")))
print(out, out.stat().st_size, rec["engine"], rec["final_status"]["label"], rec["result_digest"])
