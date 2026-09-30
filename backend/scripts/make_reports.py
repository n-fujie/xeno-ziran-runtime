"""Generate the data sections of docs/REDUCTION.md and docs/EXPERIMENT_RESULTS.md from the result files, and write
the machine-readable summary backend/experiments/results/final_results.json.

    python backend/scripts/make_reports.py

Every number in the generated sections comes from experiments/results/*.json; prose that interprets the numbers is
kept in the docs outside the generated blocks (between the GENERATED markers).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "backend" / "experiments" / "results"
sys.path.insert(0, str(ROOT / "backend"))

from xzr.runtime.flags import MINIMAL  # noqa: E402

BEGIN, END = "<!-- GENERATED:BEGIN -->", "<!-- GENERATED:END -->"
VARIANT_OF = {  # removal / replacement variants behind each primitive row
    "Ignition (as a separate operation)": ("fused_transition", None),
    "Threshold gating (ignition condition)": ("threshold_off", "threshold_off_gain0.3, 0.6, 1.0"),
    "Retention": ("retention_off", "retention_off_memory_x2, _x4"),
    "Memory": ("memory_off", "memory_off_retention+0.05, +0.10"),
    "Transformation": ("transform_off", None),
    "Penetration": ("wave_state_off", "adapt_all_carriers"),
    "Return": ("return_events_off", None),
    "Reconfiguration": ("reconfigure_off", "reconfigure_as_mutation"),
    "Difference": ("difference_relational", None),
    "Reachability": (None, None),
    "Transition": ("transition_off", None),
    "Cut": ("cut_off", None),
    "Disconnection": ("disconnect_off", None),
    "Connection (closure)": ("connect_off", None),
    "Weight adaptation": ("adapt_off", "adapt_all_carriers"),
    "Decay": (None, None),
}


def _replace_block(path: Path, body: str) -> None:
    text = path.read_text() if path.exists() else f"{BEGIN}\n{END}\n"
    a, b = text.index(BEGIN) + len(BEGIN), text.index(END)
    path.write_text(text[:a] + "\n" + body.rstrip() + "\n" + text[b:])


def _top(effects: dict, k: int = 3) -> str:
    items = sorted(effects.items(), key=lambda kv: -abs(kv[1]["relative"]))[:k]
    return ", ".join(f"{n.replace('rate:', '').replace('s:', '').replace('g:', '')} {v['relative']:+.0%} (t={v['t']})"
                     for n, v in items)


def reduction_section(r: dict) -> tuple[str, dict]:
    V, S, floors = r["variants"], r["systematic"]["variants"], r["floors"]
    configs = list(floors)
    lines = [f"Result file: `backend/experiments/results/reduction.json` · stage 1: {len(r['configs'])} regimes × "
             f"{len(r['seeds'])} seeds × {r['horizon']} steps, N = {r['n']} · stage 2: {len(r['systematic']['seeds'])} "
             f"seeds × {r['systematic']['horizon']} steps · rule: {r['tolerance_rule']}; systematic effect ⇔ |t| > "
             f"{r['systematic']['t_threshold']} and |effect| > {100 * r['systematic']['practical']:.0f}% (own outputs "
             "excluded) · noise control (same runtime, other random stream): stage-2 detections = "
             f"{sum(len(x['systematic_effects']) for x in S['noise'].values())}", "",
             "### Classification", "",
             "| primitive | status | removal / replacement | stage 1 per regime | stage 2 downstream effects per regime |",
             "|---|---|---|---|---|"]
    summary = {}
    for row in r["classification"]:
        rem, repl = VARIANT_OF.get(row["primitive"], (None, None))
        s1 = s2 = "—"
        if rem and rem in V:
            s1 = " · ".join(f"{c}: {V[rem]['configs'][c]['verdict']}" for c in configs)
        if rem and rem in S:
            s2 = " · ".join(f"{c}: {len(S[rem][c]['systematic_effects'])}" for c in configs)
        lines.append(f"| {row['primitive']} | **{row['status']}** | {rem or '—'}{' / ' + repl if repl else ''} | {s1} | {s2} |")
        summary[row["primitive"]] = {"status": row["status"], "diverges_in": row.get("diverges_in"),
                                     "reduced_to": row.get("reduced_to"), "why_unresolved": row.get("why_unresolved")}
    lines += ["", "### Largest downstream effects (stage 2)", "", "| variant | regime | effects (relative, paired t) |",
              "|---|---|---|"]
    for vn, v in S.items():
        for c in configs:
            e = v[c]["systematic_effects"]
            if e:
                lines.append(f"| {vn} | {c} | {len(e)}: {_top(e)} |")
    lines += ["", "### Full vs MINIMAL", "", f"MINIMAL = `{MINIMAL.to_dict()}`", "",
              f"Verdict: **{r['minimal_verification']['verdict']}**", "",
              "| regime | stage 1 | criteria exceeded | stage 2 downstream effects | worst criterion distance ÷ tolerance |",
              "|---|---|---|---|---|"]
    for c, p in r["minimal_verification"]["per_regime"].items():
        w = max(p["criteria_distance_over_tolerance"].items(), key=lambda kv: kv[1])
        lines.append(f"| {c} | {p['stage1_verdict']} | {', '.join(p['stage1_exceeded']) or 'none'} | "
                     f"{len(p['stage2_downstream_effects'])} | {w[0]} {w[1]:.2f} |")
    lines += ["", "### Floors", "", "| regime | ignitions/step | noise: event sequence | noise: response | "
              "1e-9 perturbation first divergence |", "|---|---|---|---|---|"]
    for c, f in floors.items():
        pert = ", ".join(str(x) if x else "never" for x in f["perturbation"]["first_divergence"])
        lines.append(f"| {c} | {f['full_ignitions_per_step']:.1f} | {f['noise']['event_sequence']:.3f} | "
                     f"{f['noise']['response']:.3f} | {pert} |")
    lines += ["", "### Engine cost per variant (sequential, regime *intermittent*)", "", "| variant | ms/step |", "|---|---|"]
    for k, v in r["audits"]["performance"].items():
        lines.append(f"| {k} | {v['ms_per_step']:.3f} |")
    lines += ["", "### Dataflow audits", "", "Arrays written per operation (observed):", ""]
    for op, fs in r["audits"]["writes"].items():
        lines.append(f"- `{op}` → {', '.join(fs) or '(nothing in the audited window)'}")
    lines += ["", "Influence (perturb one array; which *other* arrays change within 60 steps):", ""]
    for f, out in r["audits"]["influence"].items():
        lines.append(f"- `{f}` → {', '.join(out) if out else '**nothing else**'}")
    obs = r["audits"]["observer"]
    lines += ["", "Observer reconstruction of penetration annotations and returns: " + "; ".join(
        f"{c}: penetrations agree={o['penetrations_agree']}, returns agree={o['returns_agree']} "
        f"({o['penetrations']} penetrations, {o['returns']} returns, cross-macro share {o['cross_macro_share']})"
        for c, o in obs.items())]
    return "\n".join(lines), summary


def strength(effects: dict) -> str:
    """yes / marginal / no — a single summary just over threshold (|t| < 5) is marginal, not a demonstrated effect."""
    if not effects:
        return "no"
    if len(effects) == 1 and abs(next(iter(effects.values()))["t"]) < 5:
        return "marginal"
    return "yes"


def reason_section(rs: dict) -> str:
    we, em = rs["world_effects"], rs["enabling_matrix"]
    lines = [f"Result file: `backend/experiments/results/reason.json` · world effects: {len(we['seeds'])} paired world "
             f"seeds × {we['horizon']} steps, edit at t = {we['edit_at']} · enabling matrix: {len(em['seeds'])} seeds, "
             f"degradation at t = {em['degradation_at']}, probe edit: {em['probe_edit']} · effect ⇔ |t| > 4 and > 2%; "
             "a single effect with |t| < 5 is *marginal*", "",
             "### Reasoning world effects", "",
             "| comparison | identical runs | interventions differ (share of checks) | world effect "
             "| effects (relative, paired t) |",
             "|---|---|---|---|---|"]
    for k, v in we["pairs"].items():
        lines.append(f"| {k} | {v['identical_runs']}/{v['seeds']} | {v['intervention_checks_differing']:.2f} | "
                     f"{strength(v['world_effects'])} | {_top(v['world_effects']) or '—'} |")
    lines += ["", "Schedule adaptivity (share of checks whose interventions differ between world seeds): "
              + " · ".join(f"{k} {v}" for k, v in we["adaptivity"].items()), "",
              "### Enabling conditions", "",
              "| degraded condition | measured by gate | gated: collapsed share | ungated: vs none | vs memoryless | "
              "counterfactual discrimination |", "|---|---|---|---|---|---|"]
    for k, v in em["conditions"].items():
        u = v["ungated"]
        lines.append(f"| {k} | {'yes' if v['measured_by_gate'] else 'no'} | {v['gated_collapsed_share']} | "
                     f"{strength(u['world_effect_vs_none']['effects'])} | "
                     f"{strength(u['persistence_vs_memoryless']['effects'])} | "
                     f"{strength(u['counterfactual_discrimination']['effects'])} |")
    ph = rs["phases"]
    lines += ["", "### Phases", "", f"Schedule: {ph['schedule']} · enabled at t = {ph['enabled_at']} · collapsed at "
              f"t = {ph['collapsed_at']} · first commitment distinction t = {ph['first_commitment_distinction']} · "
              f"first entitlement distinction t = {ph['first_entitlement_distinction']}", "",
              "| phase | checks | commitment distinction operative | entitlement distinction operative | intervention changes |",
              "|---|---|---|---|---|"]
    for k, v in ph["by_phase"].items():
        lines.append(f"| {k} | {v['checks']} | {v['commitment_distinction']} | {v['entitlement_distinction']} | "
                     f"{v['overlay_changes']} |")
    lines += ["", "Mutation sweep (connection mutation in R from t = 150; collapsed share after): "
              + " · ".join(f"{k}: {v['collapsed_share_after']}" for k, v in rs["mutation_sweep"].items())]
    return "\n".join(lines)


def main() -> None:
    red = json.loads((RES / "reduction.json").read_text())
    body, summary = reduction_section(red)
    _replace_block(ROOT / "docs" / "REDUCTION.md", body)
    final = {"primitive_classification": summary,
             "minimal_runtime": {"flags": MINIMAL.to_dict(), "verification": red["minimal_verification"]["verdict"]}}
    reason_path = RES / "reason.json"
    if reason_path.exists():
        rs = json.loads(reason_path.read_text())
        final["reasoning"] = {
            "scenarios": {k: {x: v[x] for x in ("vocabulary_nonredundant", "two_status_nonredundant",
                                                 "entitlement_nonredundant", "fixpoint_choice_matters",
                                                 "replay_reproduces_scorekeeping_exactly", "statement")}
                          for k, v in rs["scenarios"].items()},
            "representation_equivalence": {k: v["disagreements"] for k, v in
                                           rs["representation_equivalence"]["vs_scorekeeping"].items()},
            "enabling_matrix": {k: {"world_value_on": v["valuable_on"], "gated_collapsed_share": v["gated_collapsed_share"],
                                    "measured_by_gate": v["measured_by_gate"], "adaptivity": v["adaptivity"],
                                    "strength": {c: strength(x["effects"]) for c, x in v["ungated"].items()}}
                                for k, v in rs.get("enabling_matrix", {}).get("conditions", {}).items()},
            "world_effects": {k: {"identical_runs": f"{v['identical_runs']}/{v['seeds']}",
                                  "intervention_checks_differing": v["intervention_checks_differing"],
                                  "systematic_world_effects": v["world_effects"],
                                  "strength": strength(v["world_effects"])}
                              for k, v in rs.get("world_effects", {}).get("pairs", {}).items()},
            "criteria": {
                "transition_prediction": rs["criteria"]["transition_prediction"],
                "intervention_precision": {k: v for k, v in rs["criteria"]["intervention_precision"].items()
                                           if k != "min_side_effects_per_modifier"},
                "dependency_tracing_recall": {k: v["recall"] for k, v in rs["criteria"]["dependency_tracing"]["scores"].items()},
                "error_detection_rates": rs["criteria"]["error_detection"]["rates"],
                "compression": rs["criteria"]["compression"],
                "reconfiguration_control": {k: v["in_band_mean"] for k, v in rs["criteria"]["reconfiguration_control"].items()},
            },
            "phases": {k: rs["phases"][k] for k in ("enabled_at", "collapsed_at", "first_commitment_distinction",
                                                     "first_entitlement_distinction", "by_phase")},
            "mutation_collapse": {k: v["collapsed_share_after"] for k, v in rs["mutation_sweep"].items()},
        }
        _replace_block(ROOT / "docs" / "EXPERIMENT_RESULTS.md", reason_section(rs))
    (RES / "final_results.json").write_text(json.dumps(final, indent=1))
    print("wrote docs/REDUCTION.md and docs/EXPERIMENT_RESULTS.md data blocks and", RES / "final_results.json")


if __name__ == "__main__":
    main()
