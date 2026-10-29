"""Derive the final reading of experiments F-K from the saved raw results and write it into the same file under ``final`` (the raw rows are not touched).

  PYTHONPATH=. python scripts/finalize_stage5.py [--file ../docs/ecosystem/experiments_stage5.json]

New runs are made only where a question needs them: the validation of candidate sets on seeds 6-10, the stability of the two F14 sets, a confirmation of the fixed fallback on seeds 11-30."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from xzr.meos import stage5_final as FN

ap = argparse.ArgumentParser()
root = Path(__file__).resolve().parents[2] / "docs" / "ecosystem"
ap.add_argument("--file", default=str(root / "experiments_stage5.json"))
ap.add_argument("--preliminary", default=str(root / "experiments_stage5_F_preliminary_3seeds.json"))
a = ap.parse_args()
path = Path(a.file)
doc = json.loads(path.read_text())
pre = json.loads(Path(a.preliminary).read_text())["experiments"]["F"] if Path(a.preliminary).exists() else None
final = FN.finalize(doc, pre)
for k, e in doc["experiments"].items():
    e["validation_seeds"] = list(FN.VALIDATION_SEEDS) if k == "F" else "not used: the experiment compares conditions, it does not search for sets"
doc["final"] = final
path.write_text(json.dumps(doc, indent=1))
print("classes", final["class_counts"])
print("F8", [(c["retained"][-3:], c["status"]) for c in final["F8_candidate_rejection"]["candidates_and_status"]])
print("F14 claim:", final["F14_comparison"]["claim"][:200])
print("reconf by controller:", final["reconfiguration"]["by_controller"])
print("fixed confirmation:", {k: (v["k"], v["n"]) for k, v in final["fixed_fallback_confirmation"]["persisted"].items()}, final["fixed_fallback_confirmation"]["fixed_vs_none"]["fisher_exact_p"])
