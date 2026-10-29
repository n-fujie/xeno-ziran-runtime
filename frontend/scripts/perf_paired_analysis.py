"""Paired analysis of the interleaved Stage 3 / 4 / 5 benchmark (docs/ecosystem/perf_stage5/paired/).

    python3 frontend/scripts/perf_paired_analysis.py                 # all repetitions: the primary analysis (analysis.json)
    python3 frontend/scripts/perf_paired_analysis.py --exclude 1     # sensitivity analysis without the named repetition(s) (analysis_excluding_1.json); never replaces the primary one
    python3 frontend/scripts/perf_paired_analysis.py --pool          # Stage 3 vs Stage 4 only, with the 8 earlier repetitions of stage4_acceptance/ added (analysis_pooled_stage4_acceptance.json)

The rule is the one fixed for the Stage 4 acceptance, before the data were looked at: per repetition the ratio of the two builds is formed (paired); its 95 % bootstrap confidence
interval (10 000 resamples over the repetitions, fixed seed) is computed; *regression* if the lower bound exceeds 1.05, *no meaningful regression* if the upper bound is below 1.05,
*inconclusive* otherwise. Medians are over repetitions. Ports: 3032 = Stage 3, 3033 = Stage 4, 3031 = Stage 5.
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "docs/ecosystem/perf_stage5/paired"
BUILD = {"3032": "stage3", "3033": "stage4", "3031": "stage5"}
RULE = 1.05
MEASURES = [("median", "median"), ("p95", "p95"), ("p99", "p99"), ("max", "max")]


def load(d: Path, offset: int = 0) -> dict[tuple[str, int], dict]:
    out = {}
    for f in sorted(d.glob("*.json")):
        if f.stem == "analysis" or not f.stem[:4].isdigit():
            continue
        port, rep = f.stem.split("_")
        out[(BUILD[port], int(rep) + offset)] = {r["camera"]: r for r in json.loads(f.read_text())["rows"]}
    return out


def boot(xs: list[float], n: int = 10000, seed: int = 20261029) -> tuple[float, float]:
    rng = random.Random(seed)
    meds = sorted(statistics.median(rng.choices(xs, k=len(xs))) for _ in range(n))
    return meds[int(0.025 * n)], meds[int(0.975 * n) - 1]


def verdict(lo: float, hi: float) -> str:
    return "regression" if lo > RULE else "no meaningful regression" if hi < RULE else "inconclusive"


def ratios(data, a: str, b: str, cam: str, mode: str, m: str) -> list[float]:
    reps = sorted({r for (bld, r) in data if bld == a} & {r for (bld, r) in data if bld == b})
    out = []
    for r in reps:
        ra, rb = data[(a, r)].get(cam), data[(b, r)].get(cam)
        if ra and rb and ra[mode].get(m) and rb[mode].get(m):
            out.append(rb[mode][m] / ra[mode][m])
    return out


def main() -> None:
    data = load(D)
    pool = "--pool" in sys.argv
    excl = {int(sys.argv[i + 1]) for i, a in enumerate(sys.argv) if a == "--exclude"}
    if pool:
        data.update(load(D.parent / "stage4_acceptance", 100))
    data = {k: v for k, v in data.items() if k[1] not in excl}
    reps = sorted({r for (_, r) in data})
    cams = sorted({c for v in data.values() for c in v})
    res: dict = {"rule": f"ratio CI lower > {RULE}: regression; upper < {RULE}: no meaningful regression; otherwise inconclusive", "repetitions": len(reps), "pairs": {}, "counters": {}, "load": {}}
    for f in sorted(D.glob("*.load")):
        res["load"][f.stem] = f.read_text().strip()
    for a, b in [("stage3", "stage4")] if pool else [("stage3", "stage4"), ("stage4", "stage5"), ("stage3", "stage5")]:
        rows = []
        for cam in cams:
            ui = "+" in cam
            if ui and a == "stage3":
                continue  # the Stage 3 build has no research UI: nothing to compare against
            for mode, label in [("full", "static"), ("orbiting", "orbit")]:
                for m, ml in [x for x in MEASURES if x[0] in ("median", "p95")] if pool else MEASURES:
                    rs = ratios(data, a, b, cam, mode, m)
                    if len(rs) < 5:
                        continue
                    lo, hi = boot(rs)
                    ma = statistics.median(data[(a, r)][cam][mode][m] for r in reps if (a, r) in data and cam in data[(a, r)])
                    mb = statistics.median(data[(b, r)][cam][mode][m] for r in reps if (b, r) in data and cam in data[(b, r)])
                    rows.append({"camera": cam, "mode": label, "measure": ml, f"{a}_median": round(ma, 2), f"{b}_median": round(mb, 2), "paired_ratio_median": round(statistics.median(rs), 3), "ci95": [round(lo, 3), round(hi, 3)], "n": len(rs), "verdict": verdict(lo, hi)})
        res["pairs"][f"{b}/{a}"] = rows
    for bld in ("stage3", "stage4", "stage5"):
        res["counters"][bld] = {}
        for cam in cams:
            rows = [data[(bld, r)][cam] for r in reps if (bld, r) in data and cam in data[(bld, r)]]
            if not rows:
                continue
            ser = [r.get("orbit_series") for r in rows if r.get("orbit_series")]
            res["counters"][bld][cam] = {"draw_calls_static": statistics.median(r["full"]["drawCalls"] for r in rows), "triangles_static": statistics.median(r["full"]["triangles"] for r in rows),
                                         "draw_calls_orbit": statistics.median(r["orbiting"]["drawCalls"] for r in rows), "orbit_series": ser[0] if ser else None, "orbit_series_runs": len(ser)}
    res["excluded_repetitions"] = sorted(excl)
    (D / ("analysis_pooled_stage4_acceptance.json" if pool else f"analysis_excluding_{'_'.join(map(str, sorted(excl)))}.json" if excl else "analysis.json")).write_text(json.dumps(res, indent=1))
    for pair, rows in res["pairs"].items():
        print(f"\n## {pair}  ({res['repetitions']} repetitions)")
        print("| camera | mode | measure | " + pair.split("/")[1] + " | " + pair.split("/")[0] + " | ratio | 95 % CI | verdict |\n|---|---|---|---|---|---|---|---|")
        a, b = pair.split("/")[1], pair.split("/")[0]
        for r in rows:
            print(f"| {r['camera']} | {r['mode']} | {r['measure']} | {r[a + '_median']} | {r[b + '_median']} | {r['paired_ratio_median']} | [{r['ci95'][0]}, {r['ci95'][1]}] | {r['verdict']} |")


if __name__ == "__main__":
    main()
