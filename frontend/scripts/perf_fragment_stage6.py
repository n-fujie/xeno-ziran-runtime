"""Writes docs/ecosystem/stage6_fragments/performance.md from the three analyses of the Stage 5 / Stage 6 paired benchmark (docs/ecosystem/perf_stage6/paired/)."""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "docs/ecosystem/perf_stage6/paired"
ALL, PLAN, LOW = (json.loads((P / n).read_text()) for n in ("analysis.json", "analysis_excluding_7_8_9.json", "analysis_excluding_1_3_4.json"))
KEY = "stage6/stage5"


def tbl(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|", *("| " + " | ".join(str(c) for c in r) + " |" for r in rows)]) + "\n"


def cnt(d):
    c = collections.Counter(r["verdict"] for r in d["pairs"][KEY])
    return f"{c.get('regression', 0)} regression, {c.get('no meaningful regression', 0)} no meaningful regression, {c.get('inconclusive', 0)} inconclusive"


rows = [[r["camera"], r["mode"], r["measure"], r["stage5_median"], r["stage6_median"], r["paired_ratio_median"], f"[{r['ci95'][0]}, {r['ci95'][1]}]", r["verdict"]] for r in ALL["pairs"][KEY] if r["measure"] in ("median", "p95")]
cnt_rows = []
for cam in ("habitat", "overview", "habitat+research", "habitat+technical", "habitat+repair", "habitat+repairtech"):
    for b in ("stage5", "stage6"):
        c = ALL["counters"][b][cam]
        s = c["orbit_series"]
        cnt_rows.append([cam, b, c["draw_calls_static"], int(c["triangles_static"]), s["geometry_uploads"], s["programs_built"], s["lod_switches"], s["visibility_flips"]])
reg = [r for r in PLAN["pairs"][KEY] if r["verdict"] == "regression"]
hi = {k: v.split()[2] for k, v in ALL["load"].items() if float(v.split()[2]) > 8}
text = f"""**Method.** The Stage 5 build (`1d1e331`, port 3034) and the Stage 6 build (this tree, port 3031) were measured **interleaved in time**, the order alternating each repetition, balanced tier, 150 frames, 1672 x 808, headless Chromium on the GPU, the preview browser pane closed, nothing built during a run. Conditions: habitat and overview (static, orbit), and with the UI open:
the RESEARCH tab (`+research`), the technical sheet (`+technical`), the RESEARCH tab with a **repaired run, the repair panel and the recovery map** (`+repair`), the technical sheet with the **repair figure and the repair layers** (`+repairtech`). A build without the repair view ignores the repair parameters, so for Stage 5 the same URLs measure the research tab / technical sheet without a repair; the difference is the cost of what Stage 6 adds.
Same rule as for Stages 4 and 5, fixed before any of this data: paired ratio per repetition, 95 % bootstrap interval (10 000 resamples, fixed seed); *regression* if the lower bound exceeds 1.05, *no meaningful regression* if the upper bound is below 1.05, otherwise *inconclusive*. Mean FPS is not used.

**The machine was not idle.** The load average at the start of each run is in `perf_stage6/paired/*.load`; three of the 18 runs began at a load of 9-16 ({', '.join(f'{k}: {v}' for k, v in sorted(hi.items()))}); the others at 3.4-7.3.

| analysis | repetitions | all 48 measures (6 conditions x static/orbit x median/p95/p99/max) |
|---|---|---|
| **planned** (repetitions 1-6, fixed in advance) | 6 | {cnt(PLAN)} |
| **extended** (three more repetitions, 7-9, added because the planned ones were noisy) | 9 | {cnt(ALL)} |
| sensitivity: without the repetitions that contain a high-load run (1, 3, 4) | 6 | {cnt(LOW)} |

**The one flag of the planned analysis is kept:** {'; '.join(f"{r['camera']} {r['mode']} {r['measure']}: {r['stage5_median']} ms -> {r['stage6_median']} ms, ratio {r['paired_ratio_median']} [{r['ci95'][0]}, {r['ci95'][1]}]" for r in reg)}. It is a 99th-percentile of 150 frames in the plain habitat condition, where the render counters of the two builds are identical (below) and no Stage 6 UI is open; it did **not** reappear with three more repetitions or without the high-load runs. It is reported, not removed, and not explained.

Median and p95, extended analysis (9 repetitions); all measures are in `docs/ecosystem/perf_stage6/paired/analysis_tables.md`:

""" + tbl(["condition", "mode", "measure", "Stage 5 (ms)", "Stage 6 (ms)", "paired ratio S6/S5", "95 % CI", "verdict"], rows) + """
Render counters (median over the repetitions; geometry uploads, programs built, LOD switches and visibility flips are from the orbit's per-frame series):

""" + tbl(["condition", "build", "draw calls", "triangles", "geometry uploads", "programs built", "LOD switches", "visibility flips"], cnt_rows) + """
**Verdict, Stage 6 against Stage 5: no regression is established, and for most measures the data cannot say.** In the extended and the low-load analyses no measure is a regression; in the planned analysis one tail measure was (above). Most intervals are wide (the benchmark was run on a shared machine): the cost of the repair view, the recovery map and the repair figure cannot be separated from noise at this sample size, so a cost of a few percent to
tens of percent is **not excluded** for the repair and technical conditions. The stage itself is unchanged: draw calls, triangles, geometry uploads, programs built (0 during an orbit), LOD switches and visibility flips are the same in the two builds, except 136 more triangles in the two conditions that open a repaired run (the run's state differs from the unrepaired one; the cause is not investigated). The update cost of the repair overlay itself is not measured separately.
"""
(ROOT / "docs/ecosystem/stage6_fragments/performance.md").write_text(text)
Path(P / "analysis_tables.md").write_text("# Paired comparison tables, Stage 6 against Stage 5 (generated by frontend/scripts/perf_fragment_stage6.py)\n\n" + "\n".join(f"## {n}\n\n" + tbl(["condition", "mode", "measure", "Stage 5 (ms)", "Stage 6 (ms)", "ratio", "95 % CI", "verdict"], [[r["camera"], r["mode"], r["measure"], r["stage5_median"], r["stage6_median"], r["paired_ratio_median"], f"[{r['ci95'][0]}, {r['ci95'][1]}]", r["verdict"]] for r in d["pairs"][KEY]]) for n, d in (("planned (repetitions 1-6)", PLAN), ("extended (1-9)", ALL), ("low-load (2, 5, 6, 7, 8, 9)", LOW))))
print("written")
