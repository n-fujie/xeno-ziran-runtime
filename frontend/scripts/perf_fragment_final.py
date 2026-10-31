"""Writes the head of docs/ecosystem/stage6_fragments/performance.md (the final series and the A/A control) from the two analysis files.

    python3 frontend/scripts/perf_fragment_final.py

The earlier text of the fragment (the first Stage 6 series) is kept below the marker line."""
from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "docs" / "ecosystem" / "perf_stage6"
FRAG = ROOT / "docs" / "ecosystem" / "stage6_fragments" / "performance.md"
MARK = "<!-- first Stage 6 series (kept) -->"


def rows(p: str, key: str) -> list[dict]:
    return json.loads((D / p / "analysis.json").read_text())["pairs"][key]


def count(rs: list[dict]) -> dict[str, int]:
    return dict(collections.Counter(r["verdict"] for r in rs))


F, AA = rows("paired_final", "stage6/stage5"), rows("paired_aa", "stage5b/stage5a")
cf, ca = count(F), count(AA)
loads = [float(v.split()[2]) for v in json.loads((D / "paired_final" / "analysis.json").read_text())["load"].values()]
med = [r for r in F if r["measure"] == "median"]
tbl = "\n".join(f"| {r['camera']} | {r['mode']} | {r['stage5_median']} | {r['stage6_median']} | {r['paired_ratio_median']} | [{r['ci95'][0]}, {r['ci95'][1]}] | {r['verdict']} |" for r in med)
aa_med = [r for r in AA if r["measure"] == "median"]
widths = sorted(round(r["ci95"][1] - r["ci95"][0], 2) for r in AA if r["measure"] in ("p95", "p99", "max"))
widths_f = sorted(round(r["ci95"][1] - r["ci95"][0], 2) for r in F if r["measure"] in ("p95", "p99", "max"))
ex = max(AA, key=lambda r: r["ci95"][1] - r["ci95"][0])
head = f"""### Final series (the verdict of this section)

The first series (below) was noisy. A second series was run on the final tree, with its design fixed before any of its data were seen: **12 interleaved pairs** (Stage 5 build on port 3034, Stage 6 build on port 3031, the order alternating each repetition), balanced tier, 150 frames, 1672 x 808, the six conditions, each run started only when the 1-minute load average was below 3 (it waited at most 10 minutes and then ran anyway; the load at the start of every run is in `perf_stage6/paired_final/*.load`: {min(loads):.2f}-{max(loads):.2f}, one run at {max(loads):.2f}). The rule is the one fixed for Stages 4 and 5 (CI lower bound above 1.05: regression; upper bound below 1.05: no meaningful regression; otherwise inconclusive); no repetition was excluded. (A first attempt at this series produced no data: the server's session limit answered 429 and the page never became ready; the limit was raised as in all earlier series and the series was run again; nothing from the failed attempt exists.)

| all 48 measures | regression | no meaningful regression | inconclusive |
|---|---|---|---|
| Stage 6 against Stage 5, 12 pairs | {cf.get('regression', 0)} | {cf.get('no meaningful regression', 0)} | {cf.get('inconclusive', 0)} |
| **A/A control**: the Stage 5 build on two ports, 12 pairs, three conditions (24 measures) | {ca.get('regression', 0)} | {ca.get('no meaningful regression', 0)} | {ca.get('inconclusive', 0)} |

Medians of the frame time (ms), Stage 5 against Stage 6:

| condition | mode | Stage 5 | Stage 6 | paired ratio | 95 % CI | verdict |
|---|---|---|---|---|---|---|
{tbl}

**Statistic.** For every measure (median, p95, p99, max of the 150 frame times of one run) the ratio Stage 6 / Stage 5 is formed **per repetition** (12 ratios); the estimate is their median and the 95 % interval is a bootstrap of that median over the 12 repetitions (10 000 resamples, fixed seed). The frames of a run are not resampled and are not treated as independent repetitions; the unit is the paired repetition.

**What the A/A control shows.** Two ports serving the *same* build, measured the same way, give {ca.get('inconclusive', 0)} inconclusive and {ca.get('no meaningful regression', 0)} no-meaningful-regression verdicts out of {sum(ca.values())}; the width of the 95 % interval of a tail measure (p95, p99, max) is {widths[0]}-{widths[-1]} (median {widths[len(widths) // 2]}) in the A/A and {widths_f[0]}-{widths_f[-1]} (median {widths_f[len(widths_f) // 2]}) in the Stage 6 against Stage 5 series; the widest A/A interval is {ex['camera']} {ex['mode']} {ex['measure']}: ratio {ex['paired_ratio_median']} [{ex['ci95'][0]}, {ex['ci95'][1]}] between identical builds. This limits what the measurement can decide: with 12 pairs on this machine a tail measure cannot be separated from a 5 % effect even for identical builds, so a 5 % non-regression of the tails **cannot be confirmed here**. It does not show that the differences between Stage 5 and Stage 6 are noise, and it does not show that no regression exists. As a rough scale (the interval narrows with the square root of the number of pairs) bringing a tail interval within 5 % would take several times as many pairs, perhaps ten times; this was not run.

**Verdict, Stage 6 against Stage 5.** No performance regression meeting the pre-set criterion was detected in any of the 48 measures of the final series; for {cf.get('no meaningful regression', 0)} measures a 5 % or larger degradation is excluded by that criterion, and {cf.get('inconclusive', 0)} measures are inconclusive (the A/A control shows a comparable uncertainty for the tail measures under these conditions, so a 5 % non-regression cannot be confirmed for them). The first series flagged habitat static p99 once (ratio 1.284 [1.126, 1.727]); in the final series that measure is {next(r['paired_ratio_median'] for r in F if r['camera'] == 'habitat' and r['mode'] == 'static' and r['measure'] == 'p99')} [{next(r['ci95'][0] for r in F if r['camera'] == 'habitat' and r['mode'] == 'static' and r['measure'] == 'p99')}, {next(r['ci95'][1] for r in F if r['camera'] == 'habitat' and r['mode'] == 'static' and r['measure'] == 'p99')}], inconclusive. The overall verdict is **INCONCLUSIVE**; it is not NO_MEANINGFUL_REGRESSION and is not changed by the above. What the data and the render counters support: {sum(r['verdict'] == 'no meaningful regression' for r in med)} of the 12 frame-time medians are shown not to be a 5 % regression and the others are inconclusive; the counters that decide the render cost (draw calls, triangles, geometry uploads, programs built, LOD switches, visibility flips) are identical or within the table below. A cost of the repair view of the order of 10-20 % at the tail is **not excluded**.

{MARK}

"""
old = FRAG.read_text()
if MARK in old:
    old = old.split(MARK, 1)[1].lstrip("\\n")
else:
    old = "#### The first Stage 6 series\n\n" + old
FRAG.write_text(head + old)
print("wrote", FRAG)
