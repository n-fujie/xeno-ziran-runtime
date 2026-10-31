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

**What the A/A control shows.** Two ports serving the *same* build, measured the same way, give {ca.get('inconclusive', 0)} inconclusive and {ca.get('no meaningful regression', 0)} no-meaningful-regression verdicts out of {sum(ca.values())}; the width of the 95 % interval of a tail measure (p95, p99, max) is {widths[0]}-{widths[-1]} (median {widths[len(widths) // 2]}) in the A/A and {widths_f[0]}-{widths_f[-1]} (median {widths_f[len(widths_f) // 2]}) in the Stage 6 against Stage 5 series; the widest A/A interval is {ex['camera']} {ex['mode']} {ex['measure']}: ratio {ex['paired_ratio_median']} [{ex['ci95'][0]}, {ex['ci95'][1]}] between identical builds. So on this machine, with 12 pairs, a tail measure cannot be separated from a 5 % effect whatever the build; the inconclusive verdicts of the tails are the method's resolution and not a finding about Stage 6. The number of pairs that would be needed to bring a tail interval within 5 % is roughly an order of magnitude larger (the interval narrows with the square root of the number of pairs); it was not run.

**Verdict, Stage 6 against Stage 5.** *No regression* in any of the 48 measures of the final series (and none in the extended and the low-load analyses of the first series; the one flag of the first series' planned analysis, habitat static p99, did not reappear: ratio {next(r['paired_ratio_median'] for r in F if r['camera'] == 'habitat' and r['mode'] == 'static' and r['measure'] == 'p99')} [{next(r['ci95'][0] for r in F if r['camera'] == 'habitat' and r['mode'] == 'static' and r['measure'] == 'p99')}, {next(r['ci95'][1] for r in F if r['camera'] == 'habitat' and r['mode'] == 'static' and r['measure'] == 'p99')}] in the final series). By the rule, the overall verdict is **INCONCLUSIVE** (no measure is a regression, {cf.get('no meaningful regression', 0)} are shown not to be one, {cf.get('inconclusive', 0)} cannot be decided); it is not NO_MEANINGFUL_REGRESSION, and it is not changed by the arguments that follow. What the data and the render counters support: the frame-time **medians** are within a few percent in every condition ({sum(r['verdict'] == 'no meaningful regression' for r in med)} of 12 medians are shown not to be a regression, the others are inconclusive), and the counters that decide the render cost (draw calls, triangles, geometry uploads, programs built, LOD switches, visibility flips) are identical or within the table below. A cost of the repair view of the order of 10-20 % at the tail is **not excluded**; a cost of several percent at the median is unlikely.

{MARK}

"""
old = FRAG.read_text()
if MARK in old:
    old = old.split(MARK, 1)[1].lstrip("\\n")
else:
    old = "#### The first Stage 6 series\n\n" + old
FRAG.write_text(head + old)
print("wrote", FRAG)
