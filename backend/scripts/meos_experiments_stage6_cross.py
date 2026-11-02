"""Stage 6, repairability across the MFS, the SSS region, observation, and the three restorations of an Address repair.

    PYTHONPATH=backend python backend/scripts/meos_experiments_stage6_cross.py      # needs experiments_stage6.json and experiments_stage5.json; about 10 minutes

Writes docs/ecosystem/experiments_stage6_cross.json. See xzr/meos/stage6_cross.py for the definitions."""

from __future__ import annotations

import json
import time
from pathlib import Path

from xzr.meos import engine as E
from xzr.meos import stage6_cross as C

DOCS = Path(__file__).resolve().parents[2] / "docs" / "ecosystem"


def main() -> None:
    t0 = time.time()
    a = json.loads((DOCS / "experiments_stage6.json").read_text())
    s5 = json.loads((DOCS / "experiments_stage5.json").read_text())["experiments"]
    out = {"engine": E.ENGINE_VERSION, "protocol": C.__doc__}
    out["C4_address_three_restorations"] = C.address_three()
    print("C4", round(time.time() - t0), flush=True)
    out["C3_observation"] = C.observation_cross()
    print("C3", round(time.time() - t0), flush=True)
    out["C1_mfs"] = C.mfs_cross(a, s5)
    print("C1", round(time.time() - t0), flush=True)
    out["C2_sss"] = C.sss_cross(a, s5)
    out["seconds"] = round(time.time() - t0, 1)
    (DOCS / "experiments_stage6_cross.json").write_text(json.dumps(out, indent=0))
    print("wrote in", out["seconds"], "s")
    for m, p in out["C1_mfs"]["profile"].items():
        print(m, p)


if __name__ == "__main__":
    main()
