"""Replication of the SBS experiments on NEW independent worlds with the protocol frozen in xzr/sbs/protocol.py (digest unchanged).

    PYTHONPATH=. python scripts/sbs_replication.py              # worlds 33..96 (train 33..64, test 65..96) -> docs/sbs/sbs_replication.json

The first run (docs/sbs/sbs_records.json) used worlds 1..32. This run changes nothing in the protocol, the features or the verdict rule; it only brings 32 test worlds that no earlier decision looked at. NEW EXECUTION; exploratory in the same sense as the first run (the protocol was frozen in code, not registered externally)."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from xzr.sbs.comparison import run_comparison
from xzr.sbs.protocol import PROTOCOL_DIGEST, run_world

OUT = Path(__file__).resolve().parents[2] / "docs" / "sbs"


def _world(seed: int) -> dict:
    w = run_world(seed)
    return {**{k: v for k, v in w.items() if k != "branches"}, "branches": [{k: v for k, v in b.items() if not k.startswith("_")} for b in w["branches"]], "_branches_full": w["branches"]}


def main() -> None:
    first = int(sys.argv[sys.argv.index("--first") + 1]) if "--first" in sys.argv else 33
    n = int(sys.argv[sys.argv.index("--worlds") + 1]) if "--worlds" in sys.argv else 64
    seeds = list(range(first, first + n))
    with ProcessPoolExecutor(max_workers=6) as ex:
        full = list(ex.map(_world, seeds))
    worlds_for_cmp = [{**w, "branches": w["_branches_full"]} for w in full]
    comparison = run_comparison(worlds_for_cmp, seeds[: n // 2], seeds[n // 2 :])
    rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=Path(__file__).parent).stdout.strip()
    outcomes: dict[str, dict[str, int]] = {}
    shares: dict[str, list[float]] = {}
    for w in full:
        for b in w["branches"]:
            key = f"{b['kind']}:{b['level']}"
            outcomes.setdefault(key, {})
            o = b["reconfiguration"]["outcome"]
            outcomes[key][o] = outcomes[key].get(o, 0) + 1
            shares.setdefault(key, []).append(b["dissolution"]["physical"]["largest_share"])
    rec = {
        "classification": "NEW EXECUTION (replication on new worlds, protocol unchanged)",
        "protocol_digest": PROTOCOL_DIGEST,
        "source_revision": rev,
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
        "seeds": {"worlds": seeds, "train": seeds[: n // 2], "test": seeds[n // 2 :]},
        "formation_end_largest_share_mean": float(np.mean([w["formation"]["end_coupled"]["largest_share"] for w in full])),
        "outcomes_by_branch": outcomes,
        "largest_share_at_end_of_intervention_mean": {k: float(np.mean(v)) for k, v in shares.items()},
        "comparison": comparison,
        "reproduce": f"PYTHONPATH=. python scripts/sbs_replication.py --first {first} --worlds {n}",
    }
    (OUT / "sbs_replication.json").write_text(json.dumps(rec, indent=1, sort_keys=True, default=float))
    print("written", OUT / "sbs_replication.json")
    for c in comparison["comparisons"]:
        print(c["observation"], c["protocol"][:22], c["pair"], c["verdict"], round(c["brier_difference_y_minus_x"]["mean"], 4))


if __name__ == "__main__":
    main()
