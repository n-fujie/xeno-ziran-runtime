"""Summarise interleaved benchmark runs of several builds (ecosystem_perf.mjs outputs named ``<label>_<rep>.json``): per build and camera the median over repetitions of the
per-run median and 95th percentile of a frame, for the static camera and for the orbit.

    python backend/scripts/summarize_perf_ab.py DIR label1=3032 label2=3033 ... > summary.json

The repetitions of the builds are interleaved in time, so a change in the load of the machine between repetitions falls on every build alike; the figures are comparable between
builds of the same session and with nothing else (see docs/ECOSYSTEM_MEOS_STAGE4.md, section 12)."""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

d = Path(sys.argv[1])
labels = dict(a.split("=") for a in sys.argv[2:])
out: dict = {}
for label, tag in labels.items():
    runs: dict = {}
    for f in sorted(d.glob(f"{tag}_*.json")):
        for row in json.loads(f.read_text())["rows"]:
            r = runs.setdefault(row["camera"], {"static_median": [], "static_p95": [], "orbit_median": [], "orbit_p95": [], "drawCalls": row["full"]["drawCalls"], "triangles": row["full"]["triangles"]})
            r["static_median"].append(row["full"]["median"])
            r["static_p95"].append(row["full"]["p95"])
            r["orbit_median"].append(row["orbiting"]["median"])
            r["orbit_p95"].append(row["orbiting"]["p95"])
    out[label] = {
        cam: {**{k: round(statistics.median(v), 2) for k, v in r.items() if isinstance(v, list)}, "repetitions": len(r["static_median"]), "drawCalls": r["drawCalls"], "triangles": r["triangles"], "all": {k: v for k, v in r.items() if isinstance(v, list)}}
        for cam, r in runs.items()
    }
print(json.dumps(out, indent=1))
