"""Render the measured tables behind REPORT.md from results/<stage>/summary.json (+ nonredundancy.json).

    python -m pai.report_data results/dev > results/dev/report_data.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SHORT = {"ACTIVE_INFERENCE_COMPATIBLE": "AIF", "TRANSITION": "TRANS", "POST_ACTIVE_INFERENCE": "POST", None: "—",
         "REFERENCE (unperturbed)": "REF"}


def f(x, d=2):
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float):
        return f"{x:.{d}f}"
    return str(x)


def ci(desc):
    if not desc or desc.get("mean") is None:
        return "—"
    c = desc.get("ci95")
    return f"{desc['mean']:.2f}" + (f" [{c[0]:.2f}, {c[1]:.2f}]" if c else "") + f" (n={desc['n']})"


def main(stage_dir: str) -> str:
    d = Path(stage_dir)
    s = json.loads((d / "summary.json").read_text())
    nr = json.loads((d / "nonredundancy.json").read_text())
    out = [f"# Measured tables — stage `{s['stage']}`", "",
           f"Seeds: {len(s['seeds'])}; severities: {s['severities']}; perturbation subtypes run: {s['perturbations_run']}.", ""]
    nc = s["null_classification"]
    out += ["## Null check (unperturbed noise replicate vs control, leave-one-seed-out tolerance)", "",
            f"Per-seed labels: {nc['labels']}; mislabelled share {f(nc['mislabelled_share'])}; cell-level "
            f"C_AIF {f(nc['cell_level']['C_AIF'])} → {nc['cell_level']['label']}.", "",
            f"Noise tolerance per raw quantity: {json.dumps({k: round(v, 3) for k, v in s['noise_tolerance'].items()})}", ""]
    # regime by perturbation and severity
    sevs = sorted({k.split("@")[1] for k in s["cell_classification"]}, key=float)
    out += ["## Cell-level regime by perturbation and severity (C_AIF; first unstable primitive)", "",
            "| perturbation | side | " + " | ".join(f"sev {x}" for x in sevs) + " | transition kind |",
            "|---|---|" + "---|" * len(sevs) + "---|"]
    keys = sorted({k.split("@")[0] for k in s["cell_classification"]})
    tr = s["transition_region"]["per_perturbation"]
    for k in keys:
        cells = []
        side = ""
        for x in sevs:
            v = s["cell_classification"].get(f"{k}@{x}")
            if v is None:
                cells.append("")
                continue
            fu = (v["first_unstable"] or "").replace("S_", "")
            cells.append(f"{SHORT[v['label']]} {f(v['C_AIF'])}" + (f" ({fu})" if fu else ""))
        side = k.split(".")[0]
        out.append(f"| {k} | {side} | " + " | ".join(cells) + f" | {tr.get(k, {}).get('kind', '—')} |")
    out += ["", f"Transition kinds: {s['transition_region']['counts']}", ""]
    reg = s["regimes"]
    out += ["## Regime counts", "", f"Cell level: {reg['cells_majority']}", "",
            f"Cell × seed level: {reg['overall']}; threshold sensitivity (cell × seed): {reg['threshold_sensitivity']}", "",
            "| family | AIF | TRANS | POST |", "|---|---|---|---|"]
    for fam, c in sorted(reg["by_family"].items()):
        out.append(f"| {fam} | {c.get('ACTIVE_INFERENCE_COMPATIBLE', 0)} | {c.get('TRANSITION', 0)} | {c.get('POST_ACTIVE_INFERENCE', 0)} |")
    out += ["", "## First unstable primitive (lowest severity at which most seeds leave the compatible regime)", ""]
    for prim, ks in sorted(s["first_unstable"]["by_primitive"].items()):
        out.append(f"* **{prim}**: {', '.join(sorted(ks))}")
    # performance
    out += ["", "## Performance by cell-level regime (mean [95 % CI] (n cell×seed))", "",
            "| metric | regime | none | aif_fixed | aif_adaptive | ost |", "|---|---|---|---|---|---|"]
    for key, m in sorted(s["performance_by_regime"]["means"].items()):
        metric, regime = key.split("|")
        out.append(f"| {metric} | {SHORT.get(regime, regime)} | " + " | ".join(ci(m.get(c)) for c in ("none", "aif_fixed", "aif_adaptive", "ost")) + " |")
    out += ["", "Paired contrasts (Holm over all):", "", "| metric | regime | contrast | mean diff [95 % CI] | dz | p (Holm) |",
            "|---|---|---|---|---|---|"]
    for t in sorted(s["performance_by_regime"]["contrasts"], key=lambda t: (t["metric"], t["regime"], t["contrast"])):
        c = t["ci95"]
        out.append(f"| {t['metric']} | {SHORT.get(t['regime'], t['regime'])} | {t['contrast']} | {f(t['mean'])}"
                   + (f" [{c[0]:.2f}, {c[1]:.2f}]" if c else "") + f" | {f(t['dz'])} | {f(t['p_holm'], 4)} |")
    # tracking
    out += ["", "## Tracking by regime (cell × seed label)", "",
            "| regime | tracker, world-side (detects onset) | tracker, observation-side (correctly: no world change) | "
            "comparator surprise, world-side | sensor-only tracker, world-side | localisation AUC tracker | localisation AUC comparator |",
            "|---|---|---|---|---|---|---|"]
    for lab, v in s["tracking_by_regime"].items():
        def sh(x):
            return f"{f(x['share_true'])} (n={x['n']})"
        out.append(f"| {SHORT[lab]} | {sh(v['tracking_preserved_world'])} | {sh(v['tracking_preserved_observation'])} | "
                   f"{sh(v['comparator_detection_world'])} | {sh(v['sensor_only_tracker_world'])} | {ci(v['localisation_auc_tracker'])} | "
                   f"{ci(v['localisation_auc_comparator_channels'])} |")
    q7 = s["tracker_informative_while_comparator_invalid"]
    out += ["", "## Comparator structurally invalid vs tracking", "", "```", json.dumps(q7, indent=1), "```", "",
            "## Structure-learning overlap", "", "```", json.dumps(s["structure_learning_overlap"], indent=1), "```", ""]
    # too slow
    out += ["## Too-slow correction (drift)", ""]
    for k, v in s["too_slow_correction"].items():
        out += [f"### {k}", "", f"Staleness period (steps): {v['staleness_period_steps']}; adaptive lag at slowest drift: {ci(v['adaptive_lag_steps_slowest'])}", "",
                "| severity | period | success none | aif_fixed | aif_adaptive | ost | aif_adaptive − none (p) | ost − none (p) | acc aif_adaptive |",
                "|---|---|---|---|---|---|---|---|---|"]
        for r in v["by_severity"]:
            out.append(f"| {r['severity']} | {r['change_period_steps']} | {f(r['success_none'])} | {f(r['success_aif_fixed'])} | "
                       f"{f(r['success_aif_adaptive'])} | {f(r['success_ost'])} | {f(r['aif_adaptive_minus_none'])} ({f(r['aif_adaptive_minus_none_p'], 3)}) | "
                       f"{f(r['ost_minus_none'])} ({f(r['ost_minus_none_p'], 3)}) | {f(r['acc_aif_adaptive'])} |")
        out.append("")
    # history
    out += ["## History re-entry", "", "| severity | n | Δ success_rec aif_adaptive (react − remove) | Δ ost | Δ pattern recurrence | migration destination gain |",
            "|---|---|---|---|---|---|"]
    for r in s["history_reentry"]["by_severity"]:
        def pr(x):
            return "—" if not x else f"{f(x['mean'])} [{f(x['ci95'][0]) if x['ci95'] else '—'}, {f(x['ci95'][1]) if x['ci95'] else '—'}] p={f(x['p'], 3)}"
        out.append(f"| {r['severity']} | {r['n']} | {pr(r['success_rec_reactivate_minus_remove_aif_adaptive'])} | "
                   f"{pr(r['success_rec_reactivate_minus_remove_ost'])} | {pr(r['pattern_recurrence_reactivate_minus_remove'])} | "
                   f"{pr(r['migration_destination_recurrence_gain'])} |")
    # non-redundancy
    out += ["", "## Non-redundancy (element × regime; capabilities where NON-REDUNDANT / HARMFUL)", "",
            "| element | regime | status | non-redundant for | harmful for |", "|---|---|---|---|---|"]
    for el, regs in sorted(nr["summary"].items()):
        for regm, v in sorted(regs.items()):
            out.append(f"| {el} | {SHORT.get(regm, regm)} | {v['status']} | {', '.join(v['non_redundant_for']) or '—'} | {', '.join(v['harmful_for']) or '—'} |")
    out += ["", f"Tests: {nr['n_tests']} (Holm); margin ±{nr['margin']}.", "", "## Failures", "", "```",
            json.dumps(s["failures"], indent=1), "```", ""]
    # thresholds
    out += ["## C_AIF crossings (severity; bootstrap 95 % CI; share of seeds crossing)", "",
            "| perturbation | crosses 0.8 at | CI | seeds | crosses 0.5 at | CI | seeds |", "|---|---|---|---|---|---|---|"]
    for k, v in sorted(s["thresholds"].items()):
        a, b = v.get("0.8", {}), v.get("0.5", {})
        out.append(f"| {k} | {f(a.get('crossing_severity'))} | {a.get('ci95') and [round(x, 2) for x in a['ci95']]} | {f(a.get('seeds_crossing_share'))} | "
                   f"{f(b.get('crossing_severity'))} | {b.get('ci95') and [round(x, 2) for x in b['ci95']]} | {f(b.get('seeds_crossing_share'))} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    print(main(sys.argv[1]))
