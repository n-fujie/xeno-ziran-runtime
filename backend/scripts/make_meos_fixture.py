"""Write the MEOS record the frontend tests read (frontend/src/views/ecosystem/__fixtures__/meos-a2-removed.json): the default MEOS-0 configuration, seed 1, 150 ticks,
with A2 removed at tick 60. It is a real engine record (the digests in it are the engine's); regenerate with
    python backend/scripts/make_meos_fixture.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from xzr.meos import engine as E  # noqa: E402

rec = E.run_record(E.default_config(horizon=150), [{"tick": 60, "op": "REMOVE", "target": "A2"}])
out = ROOT / "frontend/src/views/ecosystem/__fixtures__/meos-a2-removed.json"
out.write_text(json.dumps(rec, separators=(",", ":")))
print(out, out.stat().st_size, rec["final_status"]["label"], rec["result_digest"])
