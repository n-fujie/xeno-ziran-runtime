"""Interleaved paired benchmark runner (Stage 6 final series).

    PLAYWRIGHT_DIR=... CHROME=... python3 frontend/scripts/perf_run_paired.py --reps 12 --out docs/ecosystem/perf_stage6/paired_final --a 3034 --b 3031

The two builds are served on --a (Stage 5) and --b (Stage 6). Per repetition both are measured, the order alternating (odd repetitions a then b, even b then a). Before each run the 1-minute load average is read and the run waits until it is below
--max-load (default 3.0; it gives up waiting after --wait seconds and runs anyway, recording the load: nothing is dropped afterwards). The load average at the start of each run is written beside the result (<port>_<rep>.load).
An A/A control (the same build on two ports, --a and --b) measures the noise floor of the method.
The rule of the analysis (perf_paired_analysis.py) is the one fixed for Stages 4 and 5; the number of repetitions is fixed here, before any of the data were seen."""
from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--reps", type=int, default=12)
ap.add_argument("--out", required=True)
ap.add_argument("--a", default="3034")
ap.add_argument("--b", default="3031")
ap.add_argument("--max-load", type=float, default=3.0)
ap.add_argument("--wait", type=int, default=600)
ap.add_argument("--start", type=int, default=1)
ap.add_argument("--cams", default="habitat,overview,habitat+research,habitat+technical,habitat+repair,habitat+repairtech")
args = ap.parse_args()
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
CAMS = args.cams


def load() -> float:
    return os.getloadavg()[0]


for rep in range(args.start, args.reps + 1):
    for port in ((args.a, args.b) if rep % 2 else (args.b, args.a)):
        t0 = time.time()
        while load() > args.max_load and time.time() - t0 < args.wait:
            time.sleep(5)
        ld = os.getloadavg()
        (out / f"{port}_{rep}.load").write_text(f"load {{ {ld[0]:.2f} {ld[1]:.2f} {ld[2]:.2f} }}\n")
        with (out / f"{port}_{rep}.log").open("w") as log:
            subprocess.run(["node", "frontend/scripts/ecosystem_perf.mjs", "--base", f"http://127.0.0.1:{port}", "--out", str(out / f"{port}_{rep}.json"), "--frames", "150", "--tiers", "balanced", "--cams", CAMS], stdout=log, stderr=subprocess.STDOUT, check=False)
        print(f"rep {rep} port {port} load {ld[0]:.2f} {time.time() - t0:.0f}s", flush=True)
