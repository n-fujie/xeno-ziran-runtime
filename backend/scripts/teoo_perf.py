"""TEOO performance measurement under predefined conditions (small / medium / large). Run: PYTHONPATH=. python scripts/teoo_perf.py [out.json]

Each condition runs in its own process so that the resident-memory peak belongs to that condition. Everything measured here is TEOO's own code on SYNTHETIC data on this machine; nothing here is a result of MEOS or of
Stage 6, and a claim made from these numbers holds for the measured range only. The browser side (render update frequency) is measured by frontend/scripts/teoo-render-perf.mjs.
"""

from __future__ import annotations

import json
import math
import platform
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CONDITIONS = {
    # variables per record, records, samples per series, body components (graph size), observation targets
    "small": {"variables": 5, "records": 10, "series_length": 1_000, "components": 15, "targets": 7},
    "medium": {"variables": 10, "records": 40, "series_length": 5_000, "components": 200, "targets": 50},
    "large": {"variables": 10, "records": 100, "series_length": 10_000, "components": 1_000, "targets": 200},
}


def _t(f, *a, **k):
    t0 = time.perf_counter()
    out = f(*a, **k)
    return out, round(time.perf_counter() - t0, 4)


def run(name: str) -> dict:
    from xzr.teoo import body as B
    from xzr.teoo import export as EX
    from xzr.teoo import observation as OB
    from xzr.teoo import status as ST
    from xzr.teoo.mapping import coverage
    from xzr.teoo.provenance import Kind, Ledger, Provenance, seal, verify_record

    c = CONDITIONS[name]
    creator = {"name": "teoo.perf/1", "role": "generator"}
    source = {"kind": "generator", "description": "performance benchmark generator (SYNTHETIC)", "declared_by": "teoo.perf"}
    at = "2026-01-01T00:00:00.000000Z"
    n_ok = ST.ObsStatus.MEASURED_VALID

    def make_record(i: int) -> dict:
        chans = []
        for v in range(c["variables"]):
            times = [round(k / 50.0, 6) for k in range(c["series_length"])]
            samples = [ST.sample(20.0 * math.sin(2 * math.pi * 0.5 * t + i + v), n_ok) for t in times]
            chans.append({"variable": f"v{v}", "target": f"t{v}", "unit": "deg", "times": times, "samples": samples, "counts": {"MEASURED_VALID": len(samples)}})
        return seal({"channels": chans}, provenance=Provenance.SYNTHETIC, kind=Kind.OBSERVATION, creator=creator, source=source, created_at=at)

    out: dict = {"condition": name, **c, "samples_total": c["variables"] * c["records"] * c["series_length"]}
    base_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    records, out["build_records_s"] = _t(lambda: [make_record(i) for i in range(c["records"])])
    ledger = Ledger()
    _, out["ledger_append_s"] = _t(lambda: [ledger.append(r) for r in records])
    issues, out["ledger_verify_s"] = _t(ledger.verify)
    out["ledger_issues"] = len(issues)
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "records.json"
        _, out["save_s"] = _t(lambda: path.write_text(json.dumps(records, separators=(",", ":"))))
        out["saved_mb"] = round(path.stat().st_size / 2**20, 1)
        loaded, out["load_s"] = _t(lambda: json.loads(path.read_text()))
    bad, out["verify_loaded_records_s"] = _t(lambda: sum(len(verify_record(r)) for r in loaded))
    out["verify_loaded_issues"] = bad
    comps = [B.component(f"c{i}", "segment", f"c{i}") for i in range(c["components"])]
    rels = [B.relation(f"r{i}", f"c{i}", f"c{i + 1}", "joint") for i in range(c["components"] - 1)]
    tg = [B.target(f"t{v}", f"c{v % c['components']}", [f"v{v}"]) for v in range(c["variables"])]
    body, out["body_build_s"] = _t(lambda: B.new_body("perf", "perf", "artificial", components=comps, relations=rels, targets=tg, at=at))
    iss, out["body_validate_s"] = _t(B.validate_body, body)
    out["body_issues"] = len(iss)
    _, out["coverage_s"] = _t(coverage, body, records)
    sensors = [OB.sensor(f"s{k}", ["angle"], resolution=1.0, sampling_period_s=0.02, window_s=20.0, detection_limit=0.1, penetration=0.5) for k in range(max(4, c["targets"] // 10))]
    specs = [OB.target_spec(f"tg{k}", "angle", scale=2.0, phenomenon_period_s=2.0, amplitude=10.0, opacity=(k % 10) / 10) for k in range(c["targets"])]
    hist = [OB.new_configuration(sensors, at=float(k * 6), body_version=1) for k in range(4)]
    _, out["replay_21_times_s"] = _t(OB.replay, hist, specs, [float(x) for x in range(21)])
    ch = records[0]["payload"]["channels"][0]
    half = min(c["series_length"], 2_000)
    ch_small = {**ch, "times": ch["times"][:half], "samples": ch["samples"][:half]}
    fig, out["figure_svg_s"] = _t(EX.build_figure, "timeseries", "perf", {"channel": ch_small, "label": "v0"}, [records[0]], generated_at=at)
    out["figure_svg_kb"] = round(len(fig["svg"]) / 1024, 1)
    out["figure_points_drawn"] = half
    out["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (2**20 if sys.platform == "darwin" else 2**10), 1)
    out["rss_before_mb"] = round(base_rss / (2**20 if sys.platform == "darwin" else 2**10), 1)
    return out


def main() -> None:
    if len(sys.argv) > 2 and sys.argv[1] == "--one":
        print(json.dumps(run(sys.argv[2])))
        return
    results = []
    for name in CONDITIONS:
        p = subprocess.run([sys.executable, __file__, "--one", name], capture_output=True, text=True, env={**__import__("os").environ, "PYTHONPATH": "."})
        if p.returncode != 0:
            results.append({"condition": name, "error": p.stderr[-400:]})
            print(name, "FAILED", p.stderr[-300:])
            continue
        r = json.loads(p.stdout.strip().splitlines()[-1])
        results.append(r)
        print(json.dumps(r))
    doc = {"machine": {"platform": platform.platform(), "python": platform.python_version(), "processor": platform.processor()}, "conditions": CONDITIONS, "results": results,
           "note": "TEOO code on SYNTHETIC data, single run per condition, wall-clock; no MEOS or Stage 6 result is involved or changed. Claims hold for the measured range only."}
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(doc, indent=1))


if __name__ == "__main__":
    main()
