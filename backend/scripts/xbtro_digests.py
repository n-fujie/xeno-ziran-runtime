"""Digests of the standard small experiment set on this platform (compare with the browser edition's, recorded the same way).

    python backend/scripts/xbtro_digests.py > digests.json

The digest is taken over the results rounded to 6 significant digits, so a float-level difference between platforms shows as
equal; a real implementation difference shows as a different digest (``records.compare`` then says how large the difference is).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xzr.xbtro import experiments, history, observation, records  # noqa: E402

SET = [
    ("A n4 r1", "A", {"n_seeds": 4, "rounds": 1}),
    ("B n4", "B", {"n_seeds": 4}),
    (
        "C n4 subset",
        "C",
        {"n_seeds": 4, "principles": ["axis-maintenance", "anti-collapse-posture", "tensegrity"], "combos": False},
    ),
    ("D n4 trials3", "D", {"n_seeds": 4, "trials": 3}),
    ("E n4 r1", "E", {"n_seeds": 4, "rounds": 1}),
    ("F n4", "F", {"n_seeds": 4}),
    ("G n4 subset", "G", {"n_seeds": 4, "principles": ["axis-maintenance", "zero-run-up-transition"], "ablate": True}),
    ("M n4 r2", "M", {"n_seeds": 4, "rounds": 2}),
    ("S n4", "S", {"n_seeds": 4}),
    ("R n4 subset", "R", {"n_seeds": 4, "principles": ["axis-maintenance", "zero-run-up-transition"]}),
    ("V n4", "V", {"n_seeds": 4}),
]

if __name__ == "__main__":
    rows, recs = [], {}
    store = records.HistoryStore()
    for label, exp, params in SET:
        t0 = time.time()
        rec, slow = experiments.run_to_end(exp, params)
        store.add(rec, slow)
        recs[label] = rec
        rows.append(
            {
                "label": label,
                "record": rec["id"],
                "digest": rec["digest"][:12],
                "neg": len(rec["negative_results"]),
                "s": round(time.time() - t0, 1),
            }
        )
        if label == "A n4 r1":
            re = history.reanalyse(rec, observation.config("full"))
            rows.append({"label": "reanalyse A full", "record": re["id"], "digest": re["digest"][:12]})
            en, _ = history.reenter(store, rec["id"], "B", {"n_seeds": 4})
            rows.append({"label": "reenter B from A", "record": en["id"], "digest": en["digest"][:12]})
    print(json.dumps(rows, indent=1))
