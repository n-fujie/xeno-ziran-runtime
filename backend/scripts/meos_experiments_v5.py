"""Run the fifth-stage experiments F–K and save them.

  PYTHONPATH=. python scripts/meos_experiments_v5.py [--only F,G,H,I,J,K] [--out ../docs/ecosystem/experiments_stage5.json]

Every experiment runs the real engine; the file records seeds, fixed conditions, the manipulated variable, the measured variables, the results, the null results, the failures, the
unexpected outcomes and the interpretation limit of each. Nothing is tuned: a null result, a counter-example or a refusal is saved as it came."""

from __future__ import annotations

import argparse
import inspect
import json
import time
from pathlib import Path

from xzr.meos import engine as E
from xzr.meos import stage5_experiments as X5

ap = argparse.ArgumentParser()
ap.add_argument("--only", default="F,G,H,I,J,K")
ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "docs" / "ecosystem" / "experiments_stage5.json"))
args = ap.parse_args()
fns = {k: getattr(X5, f"experiment_{k.lower()}") for k in "FGHIJK" if hasattr(X5, f"experiment_{k.lower()}")}
out_path = Path(args.out)
doc = json.loads(out_path.read_text()) if out_path.exists() else {}
doc.update(engine=E.ENGINE_VERSION, baseline_result_digest=E.run_record(E.default_config(), [])["result_digest"], default_configuration=E.default_config())
for k in args.only.split(","):
    t0 = time.time()
    kw = {"f": doc["experiments"]["F"]} if "f" in inspect.signature(fns[k]).parameters else {}
    doc.setdefault("experiments", {})[k] = fns[k](**kw)
    e = doc["experiments"][k]
    print(k, "done in", round(time.time() - t0, 1), "s;", len(e["rows"]), "rows;", len(e["null_results"]), "null results;", len(e["failures"]), "failures;", len(e["unexpected"]), "unexpected", flush=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1))
