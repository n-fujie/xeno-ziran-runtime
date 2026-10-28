"""Run the fourth-stage experiments A–E and save them.

  python scripts/meos_experiments_v4.py [--only A,B,C,D,E] [--out ../docs/ecosystem/experiments_stage4.json]

Every experiment runs the real engine; the file records seeds, fixed conditions, the manipulated variable, the measured variables, the results, the null results, the
failures and the interpretation limit of each. Nothing is tuned: if an experiment gives a null result the file says so."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from xzr.meos import engine as E
from xzr.meos import stage4_experiments as X4

ap = argparse.ArgumentParser()
ap.add_argument("--only", default="A,B,C,D,E")
ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "docs" / "ecosystem" / "experiments_stage4.json"))
args = ap.parse_args()
cfg = E.default_config()
fns = {"A": X4.experiment_a, "B": X4.experiment_b, "C": X4.experiment_c, "D": X4.experiment_d, "E": X4.experiment_e}
out_path = Path(args.out)
doc = json.loads(out_path.read_text()) if out_path.exists() else {}
doc.update(engine=E.ENGINE_VERSION, baseline_result_digest=E.run_record(cfg, [])["result_digest"], default_configuration=cfg)
for k in args.only.split(","):
    t0 = time.time()
    doc.setdefault("experiments", {})[k] = fns[k](cfg)
    print(k, "done in", round(time.time() - t0, 1), "s;", len(doc["experiments"][k]["rows"]), "rows;", len(doc["experiments"][k]["null_results"]), "null results;", len(doc["experiments"][k]["failures"]), "failures", flush=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=False))
