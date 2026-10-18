"""Run the XB-TRO experiments at their final settings and store the records (JSON and CSV) with the code commit.

    python backend/scripts/run_xbtro_final.py <out_dir> [name ...]

Sets
  standard      A-G, M, R, S, V at 12 final seeds (5000..5011), the settings the interface offers.
  g-original    G with the settings of the first report of the axis-maintenance result (8 seeds, 4 principles,
                ablation).
  g-replicate   G over all fourteen principles at 16 seeds from another block (7000..7015): an independent
                re-verification.
  band13        B and D at 12 seeds with the human-like tolerance band at 13 mm instead of the registered 9 mm
                (a sensitivity analysis; the registered value is not changed anywhere).
Nothing is tuned here: parameters are fixed in this file. The index records the git commit, platform and the time each took.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xzr.xbtro import experiments, metrics, records  # noqa: E402

STANDARD = [(f"{e}_standard", e, {"n_seeds": 12}) for e in "ABCDEFGMRSV"]
SETS = {
    "standard": STANDARD,
    "g-original": [
        (
            "G_original_conditions",
            "G",
            {
                "n_seeds": 8,
                "principles": ["axis-maintenance", "zero-run-up-transition", "slow-movement", "tensegrity"],
                "ablate": True,
            },
        )
    ],
    "g-replicate": [("G_independent_replication", "G", {"n_seeds": 16, "seed": 7000})],
    "band13": [("B_band_13mm", "B", {"n_seeds": 12}), ("D_band_13mm", "D", {"n_seeds": 12})],
}


def commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


if __name__ == "__main__":
    out = Path(sys.argv[1])
    (out / "records").mkdir(parents=True, exist_ok=True)
    want = set(sys.argv[2:]) or set(SETS)
    index_path = out / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {"runs": []}
    for set_name, items in SETS.items():
        if set_name not in want:
            continue
        for name, exp, params in items:
            old = dict(metrics.TOLERANCE["human-like"])
            if set_name == "band13":
                metrics.TOLERANCE["human-like"] = {**old, "band": 0.013}
            t0 = time.time()
            rec, _ = experiments.run_to_end(exp, params)
            metrics.TOLERANCE["human-like"] = old
            (out / "records" / f"{name}.json").write_text(records.to_json(rec))
            (out / "records" / f"{name}.csv").write_text(records.to_csv(rec))
            index["runs"] = [r for r in index["runs"] if r["name"] != name] + [
                {
                    "name": name,
                    "set": set_name,
                    "experiment": exp,
                    "params": params,
                    "record": rec["id"],
                    "digest": rec["digest"],
                    "seeds": [rec["seeds"][0], rec["seeds"][-1]],
                    "negative_results": len(rec["negative_results"]),
                    "seconds": round(time.time() - t0, 1),
                    "commit": commit(),
                    "python": platform.python_version(),
                    "tolerance_override": {"human-like": 0.013} if set_name == "band13" else None,
                }
            ]
            index_path.write_text(json.dumps(index, indent=1))
            print(name, rec["id"], round(time.time() - t0, 1), flush=True)
