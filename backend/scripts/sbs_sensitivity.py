"""Run the SBS sensitivity variants (see xzr/sbs/sensitivity.py) -> docs/sbs/sbs_sensitivity.json.

    PYTHONPATH=. python scripts/sbs_sensitivity.py [--worlds 8] [--hysteresis 3]

Worlds 201..(200+worlds), none of which belongs to the first run (1..32) or the replication (33..96). NEW EXECUTION."""

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from xzr.sbs.protocol import PROTOCOL_DIGEST
from xzr.sbs.sensitivity import VARIANTS, run_one, summarise

OUT = Path(__file__).resolve().parents[2] / "docs" / "sbs"


def _task(a: tuple[str, int, bool]) -> dict:
    return run_one(*a)


def main() -> None:
    nw = int(sys.argv[sys.argv.index("--worlds") + 1]) if "--worlds" in sys.argv else 8
    nh = int(sys.argv[sys.argv.index("--hysteresis") + 1]) if "--hysteresis" in sys.argv else 3
    tasks = []
    for name, (kind, _) in VARIANTS.items():
        seeds = range(201, 201 + (nw if kind == "world" else nh))
        tasks += [(name, s, (s - 201) < nh) for s in seeds]
    with ProcessPoolExecutor(max_workers=6) as ex:
        rows = list(ex.map(_task, tasks, chunksize=1))
    result = {}
    for name, (kind, change) in VARIANTS.items():
        result[name] = {"kind": kind, "change": change, **summarise([r for r in rows if r["variant"] == name])}
    rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=Path(__file__).parent).stdout.strip()
    rec = {"classification": "NEW EXECUTION", "baseline_protocol_digest": PROTOCOL_DIGEST, "source_revision": rev, "worlds": f"201..{200 + nw}", "hysteresis_sweeps_per_variant": nh, "variants": result, "rows": rows,
           "reproduce": f"PYTHONPATH=. python scripts/sbs_sensitivity.py --worlds {nw} --hysteresis {nh}"}
    (OUT / "sbs_sensitivity.json").write_text(json.dumps(rec, indent=1, sort_keys=True, default=float))
    for name, r in result.items():
        print(name, {k: (v["holds"] if isinstance(v, dict) and "holds" in v else None) for k, v in r.items() if k.startswith("F")})


if __name__ == "__main__":
    main()
