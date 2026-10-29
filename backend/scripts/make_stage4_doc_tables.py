"""Markdown tables of the fourth-stage experiments (A-E), read from docs/ecosystem/experiments_stage4.json, for docs/ECOSYSTEM_MEOS_STAGE4.md.

    python backend/scripts/make_stage4_doc_tables.py > /tmp/stage4_tables.md

Every number in the tables is copied from the saved experiment file; nothing is typed in."""

from __future__ import annotations

import json
from pathlib import Path

D = json.loads((Path(__file__).resolve().parents[2] / "docs" / "ecosystem" / "experiments_stage4.json").read_text())["experiments"]
out: list[str] = []


def table(head: list[str], rows: list[list]) -> None:
    out.append("| " + " | ".join(head) + " |")
    out.append("|" + "|".join("---" for _ in head) + "|")
    out.extend("| " + " | ".join(str(c) for c in r) + " |" for r in rows)
    out.append("")


def meta(k: str) -> None:
    e = D[k]
    out.append(f"**Seeds** {e['seeds']} · **fixed** {json.dumps(e['fixed_conditions'], ensure_ascii=False)[:600]}")
    out.append(f"**Manipulated** {json.dumps(e['manipulated_variable'], ensure_ascii=False)[:500]}")
    out.append(f"**Measured** {'; '.join(e['measured_variables'])}")
    out.append(f"**Failures (runs the engine refused)** {len(e['failures'])} · **null results recorded** {len(e['null_results'])}")
    out.append("")


# A
out.append("@@A@@")
meta("A")
A = D["A"]
table(["scenario", "parameter", "first value at which the observer disagrees with the run"], [[t["scenario"], t["parameter"], t["first_disagreeing_value"] if t["first_disagreeing_value"] is not None else "none in the sweep (null)"] for t in A["transition_values"]])
out.append(f"Replay identical after every observation: **{A['replay_identical_after_all_observations']}**.\n")
lat = sorted({r["mean_observation_latency_ticks"] for r in A["rows"] if r["scenario"].startswith("interaction cut 100-150 (collapses)") and r.get("mean_observation_latency_ticks") is not None})
out.append(f"Observed-collapse tick minus operational-collapse tick in the collapsing scenario, over every observation of the sweep that disagrees or agrees: {lat} (negative: an observer that resolves no cycle concludes COLLAPSED at the end of its window, long before the run collapses; that is a limit of the observation, not an early collapse).\n")
# B
out.append("@@B@@")
meta("B")
B = D["B"]
table(["boundary", "duration", "collapsed (of 5)", "recovered w/o pulse", "recovered with pulse", "operation changed", "pulse alone, final states", "paths cut directly", "observability"],
      [[r["boundary"], r["duration"], r["collapsed_seeds"], r["recovered_without_pulse_seeds"], r["recovered_with_pulse_seeds"], r["operation_changed_seeds"], "/".join(r["pulse_alone_final_states"]), ",".join(r["paths_cut_directly"]) or "-", ",".join(r["observability"])] for r in B["rows"]])
table(["body", "retained components", "persists (of 5)"], [[k, ", ".join(v["components_retained"]), f"{v['persists_seeds']}/{v['seeds']}"] for k, v in B["body_persistence"].items()])
# C
out.append("@@C@@")
meta("C")
C = D["C"]
table(["mode", "target", "duration", "collapsed", "ACTIVE at end", "ACTIVE with pulse", "dynamics changed", "min integrity"], [[r["mode"], r["target"], r["duration"], r["collapsed_seeds"], r["final_active_seeds"], r["final_active_with_pulse_seeds"], r["dynamics_changed_seeds"], r["min_integrity"]] for r in C["rows"]])
# D
out.append("@@D@@")
meta("D")
Dd = D["D"]
out.append(f"Regions over {len(Dd['rows'])} grid points: {json.dumps(Dd['counts'])}\n")
table(["axis", "side", "last ACTIVE", "first not ACTIVE", "class there", "resolution"], [[t["axis"], t["side"], t["last_active"], t.get("first_not_active"), t.get("class_there", "-"), t.get("resolution", "-")] for t in Dd["transition_points"]])
table(["scale", "size", "speed", "region"], [[r["scale"], r["size"], r["speed"], r["region"]] for r in Dd["rows"] if r["region"] != "COLLAPSED"])
# E
out.append("@@E@@")
meta("E")
E = D["E"]
table(["scenario", "M2 sensing", "collapse freq.", "recovery rate", "mean energy", "mean cycles", "A1→A2 lag", "ACTIVE w/o history", "observation disagrees", "identical to none", "differs from none in"],
      [[r["scenario"], r["m2"], r["collapse_frequency"], r["recovery_rate"], r["mean_energy"], r["mean_cycles"], r["mean_a1_a2_lag"], r["active_without_history_frequency"], r["observation_disagrees_frequency"], r.get("identical_runs_to_none", "-"), ", ".join(r.get("measured_differences_vs_none", [])) or ("-" if r["m2"] == "none" else "nothing")] for r in E["rows"]])
out.append("**Null results (E)**\n")
out.extend(f"- {n}" for n in E["null_results"])
print("\n".join(out))
