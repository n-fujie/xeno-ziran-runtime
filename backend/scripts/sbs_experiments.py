"""Run the SBS experiments (Simondonian Body Simulation) and write the records to docs/sbs/.

    PYTHONPATH=. python scripts/sbs_experiments.py              # worlds 1..32 (train 1..16, test 17..32) + hysteresis sweeps 1..12
    PYTHONPATH=. python scripts/sbs_experiments.py --worlds 2   # a short smoke run, written to a separate file, not to the records

The records are NEW EXECUTION (see docs/SBS.md): the protocol is frozen in xzr/sbs/protocol.py and hashed into every record."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import scipy

from xzr.sbs.comparison import run_comparison
from xzr.sbs.engine import Config
from xzr.sbs.protocol import PROTOCOL, PROTOCOL_DIGEST, run_metastability, run_world

OUT = Path(__file__).resolve().parents[2] / "docs" / "sbs"
FRAME_SEEDS = (1, 17)


def _world(seed: int) -> dict:
    return run_world(seed, keep_frames=seed in FRAME_SEEDS)


def _meta(seed: int) -> dict:
    return run_metastability(seed)


def _public(w: dict) -> dict:
    return {**{k: v for k, v in w.items() if k != "branches"}, "branches": [{k: v for k, v in b.items() if not k.startswith("_")} for b in w["branches"]]}


def main() -> None:
    n_worlds = 32
    if "--worlds" in sys.argv:
        n_worlds = int(sys.argv[sys.argv.index("--worlds") + 1])
    smoke = n_worlds != 32
    half = n_worlds // 2
    seeds = list(range(1, n_worlds + 1))
    with ProcessPoolExecutor(max_workers=4) as ex:
        worlds = list(ex.map(_world, seeds))
        metas = list(ex.map(_meta, range(1, (3 if smoke else 12) + 1)))
    comparison = run_comparison(worlds, seeds[:half], seeds[half:])
    try:
        rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=Path(__file__).parent).stdout.strip()
    except OSError:
        rev = "unknown"
    meta_area = [m["hysteresis_area"] for m in metas]
    record = {
        "classification": "NEW EXECUTION",
        "frozen_protocol_in_code": "written before the first run, thresholds not changed after seeing results; not an external registration",
        "protocol": PROTOCOL,
        "protocol_digest": PROTOCOL_DIGEST,
        "source_revision": rev,
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "config": Config().asdict(),
        "seeds": {"worlds": seeds, "train": seeds[:half], "test": seeds[half:], "metastability": [m["seed"] for m in metas]},
        "reproduce": "PYTHONPATH=. python scripts/sbs_experiments.py" + (f" --worlds {n_worlds}" if smoke else ""),
        "worlds": [_public(w) for w in worlds],
        "metastability": {"sweeps": metas, "hysteresis_area_mean": float(np.mean(meta_area)), "hysteresis_area_sd": float(np.std(meta_area, ddof=1)) if len(meta_area) > 1 else None},
        "comparison": comparison,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / ("sbs_smoke.json" if smoke else "sbs_records.json")).write_text(json.dumps(record, indent=1, sort_keys=True, default=float))
    frames = {str(w["seed"]): [{k: v for k, v in b.items() if k in ("kind", "level", "frames")} for b in w["branches"]] for w in worlds if w["seed"] in FRAME_SEEDS}
    if not smoke:
        (OUT / "sbs_frames.json").write_text(json.dumps({"classification": "NEW EXECUTION", "protocol_digest": PROTOCOL_DIGEST, "box": Config().box(), "note": "positions of every particle every 250 steps (positions rounded to 3 decimals); measured states, not interpolated", "worlds": frames}, default=float))
    print("written", OUT, "protocol", PROTOCOL_DIGEST[:12])
    for c in comparison["comparisons"]:
        print(c["observation"], c["protocol"][:22], c["pair"], c["verdict"], round(c["brier_difference_y_minus_x"]["mean"], 4))


if __name__ == "__main__":
    main()
