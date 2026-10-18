"""Write SUMMARY.md from the stored final records (so that every number in the report comes from a record, not from memory).

python backend/scripts/summarize_xbtro_final.py <final_dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load(d: Path, name: str) -> dict:
    return json.loads((d / "records" / f"{name}.json").read_text())


def f(x, n=3):
    return "—" if x is None else (f"{x:.{n}g}" if isinstance(x, (int, float)) else str(x))


def table(cols, rows):
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    out += ["| " + " | ".join(f(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def tbl(rec: dict, name: str) -> dict:
    return next(t for t in rec["results"]["tables"] if t["name"] == name)


def main(d: Path) -> str:
    idx = json.loads((d / "index.json").read_text())["runs"]
    L = [
        "# XB-TRO final records — summary",
        "",
        "Generated from the stored records by `summarize_xbtro_final.py`. Every number below is read from a record.",
        "",
        "## Index",
        "",
        table(
            ["name", "record", "digest (12)", "seeds", "negative results", "seconds", "commit"],
            [
                [
                    r["name"],
                    r["record"],
                    r["digest"][:12],
                    f"{r['seeds'][0]}..{r['seeds'][1]}",
                    r["negative_results"],
                    r["seconds"],
                    r["commit"][:10],
                ]
                for r in idx
            ],
        ),
    ]
    # numerics
    v = load(d, "V_standard")
    L += ["", "## Numerical verification (record V)", ""]
    for t in v["results"]["tables"]:
        if t["name"].startswith("stability"):
            L += [f"### {t['title']}", "", table(t["columns"], t["rows"]), ""]
        if t["name"].startswith("convergence"):
            L += [
                f"### {t['title']}",
                "",
                table(
                    ["variant", "plant step s", "RMS COM diff m", "max COM diff m", "state"],
                    [[r[1], r[2], r[3], r[4], r[5]] for r in t["rows"]],
                ),
                "",
            ]
    pm = tbl(v, "preset_matrix")
    L += [
        "### Eight conditions x two presets x two protocols",
        "",
        table(
            [
                "preset",
                "protocol",
                "condition",
                "fell (physical)",
                "diverged (numerical)",
                "max COM m",
                "recovered in window",
                "settled after turn",
                "state",
            ],
            [[r[0][:5], r[1], r[2], r[4], r[5], r[6], r[12], r[13], r[15]] for r in pm["rows"]],
        ),
    ]
    # B
    b = load(d, "B_standard")
    c = b["results"]["coupling"]
    L += ["", "## B — couplings", "", f"classes: {c['classes']}", ""]
    # C / G / R
    for name, title in (
        ("C_standard", "C — Fragility Transfer matrix"),
        ("G_standard", "G — directional Fragility Transfer"),
        ("G_independent_replication", "G — independent replication (16 seeds, seeds 7000..)"),
    ):
        rec = load(d, name)
        L += [
            "",
            f"## {title}",
            "",
            f"seeds {len(rec['seeds'])}; design: {rec['results']['design']['reading']}",
            "",
            "transfers:",
            "",
        ]
        for t in rec["results"]["transfers"]:
            L.append(
                f"- **{t['principle']}**: improved {t['improved']}; weakened {t['worsened']}"
                + (" (directional)" if t.get("directional") else "")
            )
        if not rec["results"]["transfers"]:
            L.append("- none")
        L += ["", f"negative / null results: {len(rec['negative_results'])}"]
    og, rp = load(d, "G_original_conditions"), load(d, "G_independent_replication")
    L += [
        "",
        "## Axis-maintenance: the first report and its independent re-verification",
        "",
        "First report (8 seeds, seeds 5000.., four principles, ablation) and replication (16 seeds, seeds 7000.., "
        "all fourteen principles). Mean effects (condition minus control; lower is better) and the share due to "
        "the rule line (against the ablation).",
        "",
    ]
    rows = []
    for lab, rec in (("first report", og), ("replication", rp)):
        m = rec["results"]["matrix"].get("axis-maintenance", {})
        for k in (
            "peak_dev_forward",
            "recovery_region",
            "tolerance_forward",
            "tolerance_backward",
            "correction_latency",
            "turn_settling_after_push",
        ):
            x = m.get(k)
            if x:
                mean_d = None if x["mean"] is None or x["mean_control"] is None else x["mean"] - x["mean_control"]
                rows.append(
                    [lab, k, x["mean_control"], x["mean"], mean_d, x["d"], x["q"], x["label"], x.get("effect_of_the_rule_line")]
                )
    L += [
        table(
            ["run", "measure", "control mean", "condition mean", "difference", "d", "q (BH)", "label", "due to the rule line"],
            rows,
        )
    ]

    def label(rec: dict, k: str) -> str:
        return rec["results"]["matrix"]["axis-maintenance"][k]["label"]

    L += ["", "Reading (computed from the labels above):", ""]
    for k, what in (
        ("peak_dev_forward", "peak push deviation (weakening)"),
        ("recovery_region", "recovery region (weakening)"),
        ("turn_settling_after_push", "settling after the later direction change (improvement)"),
        ("correction_latency", "correction latency (improvement)"),
    ):
        a_, b_ = label(og, k), label(rp, k)
        L.append(f"- {what}: first report '{a_}', replication '{b_}' — {'replicated' if a_ == b_ else 'NOT replicated'}")
    r = load(d, "R_standard")["results"]
    L += [
        "",
        "## R — sensitivity of the Fragility Transfer matrix",
        "",
        f"cells: {r['cells']}; identical label in every variant: {r['cells_with_identical_label_in_all_variants']}; "
        f"transfers in every variant: {r['transfers_in_every_variant']}; "
        f"in some variants only: {r['transfers_in_some_variants']}",
    ]
    # D
    dd = load(d, "D_standard")
    L += [
        "",
        "## D — operational velocity (baseline)",
        "",
        table(
            ["measure", "unit", "fraction defined", "mean", "estimable from observations"],
            [[x[0], x[2], x[4], x[5], x[8]] for x in tbl(dd, "baseline_measures")["rows"]],
        ),
    ]
    # F S M E A
    fr = load(d, "F_standard")["results"]
    L += [
        "",
        "## F — human-like vs machine-like",
        "",
        f"strongest push recovered (50 % of seeds): {fr['critical_push']}",
        "",
        table(
            ["push N", "human-like", "machine-like"],
            [[x[0], x[1], x[2]] for x in tbl(load(d, "F_standard"), "reachability")["rows"]],
        ),
    ]
    s = load(d, "S_standard")["results"]
    for cons, o in s["consequences"].items():
        L += [
            "",
            f"## S — paths for '{cons}'",
            "",
            table(
                ["path", "latency s", "energy", "info gain", "reach s", "lines changed", "recovery s", "fall", "non-dominated"],
                [
                    [
                        p["path"],
                        p["latency_s"],
                        p["energy"],
                        p["information_gain"],
                        p["intervention_reach_s"],
                        p["lines_changed"],
                        p["recovery_rmst_s"],
                        p["fall_rate"],
                        p["non_dominated"],
                    ]
                    for p in o["paths"]
                ],
            ),
        ]
    L += ["", f"selection under stated constraints: {s['selection_under_stated_constraints']}"]
    e = load(d, "E_standard")
    L += ["", "## E — adaptive observation", "", table(tbl(e, "adaptive_summary")["columns"], tbl(e, "adaptive_summary")["rows"])]
    m = load(d, "M_standard")["results"]
    L += [
        "",
        "## M — MO-style policy",
        "",
        f"stopped because: {m['policy']['stopped_because']}; "
        f"rounds: {[(g['round'], g['decision'][:40]) for g in m['policy']['rounds']]}",
    ]
    a = load(d, "A_standard")
    L += [
        "",
        "## A — identifiability by observation configuration",
        "",
        table(tbl(a, "summary")["columns"], tbl(a, "summary")["rows"]),
    ]
    # band sensitivity
    L += ["", "## Tolerance band sensitivity (human-like 9 mm registered vs 13 mm)", ""]
    rows = []
    for nm in ("B", "D"):
        for lab, name in (("9 mm (registered)", f"{nm}_standard"), ("13 mm", f"{nm}_band_13mm")):
            rec = load(d, name)
            if nm == "B":
                ctrl = [r for r in tbl(rec, "condition_effects")["rows"] if "recovery" in r[1]][0]
                rows.append([nm, lab, "control recovery time (restricted mean, s)", ctrl[2]])
            else:
                row = next(r for r in tbl(rec, "baseline_measures")["rows"] if r[0] == "recovery")
                rows.append([nm, lab, "recovery: fraction of seeds defined / mean s", f"{f(row[4])} / {f(row[5])}"])
    L += [table(["experiment", "band", "measure", "value"], rows)]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    d = Path(sys.argv[1])
    (d / "SUMMARY.md").write_text(main(d))
    print(f"wrote {d / 'SUMMARY.md'}")
