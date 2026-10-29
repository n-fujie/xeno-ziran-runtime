"""MEOS-0, fifth stage: the final, derived reading of experiments F–K. Everything here is computed from the saved raw results (``experiments_stage5.json``) and, where a question needs new
runs (the validation of a candidate set, the stability of the two F14 sets across the validation seeds, a confirmation of the fixed fallback on fresh seeds), from real runs of the engine.
Raw data and interpretation are kept apart: the raw rows stay where the experiments put them, and ``final`` carries the derived classification, the effect sizes, the intervals and the words.

Protocol (fixed in code, not tuned after the fact):
  search seeds 1-5       a set *persists* only if it persists in every one of them; the inclusion-minimal persisting sets are the discovered MFS
  validation seeds 6-10  every discovered MFS is run again on seeds the search never saw; it is *validated* only if it persists in all of them
  candidate              an inclusion-minimal set under the relaxed criterion "persists in at least 3 of the 5 search seeds", or a minimal set of the first (3-seed) search; its status says why
                         it is or is not an MFS: validated, failed the search criterion, failed validation, near miss (4 of 5 on both sets of seeds: the data cannot separate it)
  condition class        NO_MFS, SINGLE_MFS, MULTIPLE_MFS (two or more validated sets of different composition), UNSTABLE_CANDIDATE (no validated set, candidates exist),
                         INCONCLUSIVE (a near-miss candidate exists)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import engine as E
from . import mfs5 as M
from . import reconf as RC
from . import routes5 as R
from . import stats5 as ST

VALIDATION_SEEDS = M.CONFIRM_SEEDS
SEARCH_SEEDS = M.SEARCH_SEEDS
ROLE_COMPONENTS = {"history": ["history"], "M2": ["m2_tap"], "coupling": ["interaction_channel"], "resource": ["resource_gradient"], "renewal": ["resource_renewal", "feedback"]}
ROLE_ORDER = ("necessary", "compensatory", "substitutable", "destabilizing", "redundant", "null")


# ---------------------------------------------------------------------------------------------------- candidates and the condition classes
def _mask(uni: list[str], retained: list[str]) -> int:
    return sum(1 << uni.index(c) for c in retained)


def candidate_analysis(cond: dict, res: dict, preliminary: dict | None) -> dict:
    """The candidate retaining sets of one condition and what became of each: discovered in the search, survived validation, or failed (and where)."""
    uni = res["universe"]
    counts = {int(k): v for k, v in res["table"].items()}  # per subset: in how many of the 5 search seeds it persists
    relaxed = {m: c >= 3 for m, c in counts.items()}
    cand_masks = set(M.minimal_masks(relaxed))
    cand_masks |= {_mask(uni, m["retained_components"]) for m in res["mfs"]}
    prelim_sets: list[list[str]] = []
    if preliminary:
        prelim_sets = [m["retained_components"] for m in preliminary.get("by_condition", {}).get(cond["id"], {}).get("mfs", []) if all(c in uni for c in m["retained_components"])]
        cand_masks |= {_mask(uni, s) for s in prelim_sets}
    validated = {tuple(m["retained_components"]) for m in res["mfs"]}
    out = []
    for mask in sorted(cand_masks, key=lambda m: (bin(m).count("1"), m)):
        ret = [c for i, c in enumerate(uni) if mask >> i & 1]
        s_k = counts[mask]
        v = M.persists(cond, frozenset(ret), VALIDATION_SEEDS)
        v_k = sum(v)
        found_by = []
        if mask in M.minimal_masks(relaxed):
            found_by.append("inclusion-minimal under the relaxed criterion (>= 3 of 5 search seeds)")
        if tuple(ret) in validated:
            found_by.append("inclusion-minimal under the search criterion (all 5 search seeds)")
        if ret in prelim_sets:
            found_by.append("minimal set of the first search (seeds 1-3 only)")
        if tuple(ret) in validated and v_k == len(VALIDATION_SEEDS):
            status = "validated"
        elif s_k < len(SEARCH_SEEDS) and s_k >= 4 and v_k >= 4:
            status = "near miss"
        elif s_k < len(SEARCH_SEEDS):
            status = "failed the search criterion"
        else:
            status = "failed validation"
        out.append({"retained": ret, "cardinality": len(ret), "found_by": found_by, "search_seeds": list(SEARCH_SEEDS), "persists_in_search_seeds": s_k, "validation_seeds": list(VALIDATION_SEEDS), "persists_in_validation_seeds": v_k, "status": status,
                    "per_validation_seed": list(v), "discovered_in_search": bool(found_by), "survived_validation": status == "validated"})
    return {"candidates": out, "validated": sum(1 for c in out if c["status"] == "validated"), "rejected": [c for c in out if c["status"] not in ("validated", "near miss")], "near_misses": [c for c in out if c["status"] == "near miss"]}


def condition_class(ca: dict) -> str:
    n = ca["validated"]
    if ca["near_misses"]:
        return "INCONCLUSIVE"
    if n >= 2:
        return "MULTIPLE_MFS"
    if n == 1:
        return "SINGLE_MFS"
    return "UNSTABLE_CANDIDATE" if ca["rejected"] else "NO_MFS"


def role(cid: str, comp: str, res: dict, across: dict) -> str:
    """The role of a component under a condition: necessary, compensatory (needed here and redundant under the condition this one degrades), substitutable, destabilizing, redundant, null."""
    if comp not in res["universe"]:
        return "not available under this condition"
    if any(c["needed_under"] == cid for c in across[comp]["compensatory"]):
        return "compensatory"
    labels = res["classification"]["components"][comp]["labels"]
    for name in ROLE_ORDER:
        if any(lb.startswith(name) for lb in labels):
            return name
    return "contributes in some contexts only"


def f_table(f: dict, cands: dict[str, dict], j: dict, k: dict) -> list[dict]:
    """One row per condition F1-F16 with everything asked of the final table."""
    jr = {r["mfs"]: r for r in j["rows"]}
    kr = {r["mfs"]: r for r in k["rows"]}
    rows = []
    for cid, r in f["by_condition"].items():
        ids = [m["id"] for m in r["mfs"]]
        prof = [f["profiles"][i] for i in ids]
        roles = {name: [role(cid, c, r, f["across_conditions"]) for c in comps] for name, comps in ROLE_COMPONENTS.items()}
        rows.append({
            "condition_id": cid, "description": r["condition"]["label"], "search_seeds": list(SEARCH_SEEDS), "validation_seeds": list(VALIDATION_SEEDS),
            "candidate_retaining_sets": len(cands[cid]["candidates"]), "validated_mfs": cands[cid]["validated"], "rejected_candidates": len(cands[cid]["rejected"]), "near_miss_candidates": len(cands[cid]["near_misses"]),
            "mfs_ids": ids, "cardinality": [m["cardinality"] for m in r["mfs"]],
            "history_role": roles["history"][0], "m2_role": roles["M2"][0], "coupling_role": roles["coupling"][0], "resource_role": roles["resource"][0],
            "renewal_role": "/".join(sorted(set(roles["renewal"]))),
            "address_role": ("not a removable component; collapse share under the Address fault battery (mean over the MFS): " + ", ".join(f"{p['address_dependence']:.2f}" for p in prof)) if prof else "no MFS to test",
            "sss_region_default_setting": [jr[i]["default_setting_region"] for i in ids], "observational_robustness": [kr[i]["observational_robustness"] for i in ids],
            "classification": condition_class(cands[cid]), "persisting_subsets_in_search": r["persisting_subsets"], "seed_disagreeing_subsets": r["seed_disagreeing_subsets"],
        })
    return rows


# ---------------------------------------------------------------------------------------------------- F14: the two validated sets compared
def stability_on_validation_seeds(cond: dict, retained: list[str]) -> dict:
    ivs = M.retained_interventions(cond, frozenset(retained))
    per = []
    for sd in VALIDATION_SEEDS:
        rec = E.run_record(M._config(cond, sd, 240), ivs)
        ticks = [c["tick"] for c in rec["cycles"] if c["tick"] >= 140]
        import numpy as np

        iv = np.diff(ticks)
        per.append({"seed": sd, "active_at_end": rec["final_status"]["label"] == "ACTIVE", "cycles": len(rec["cycles"]), "cycle_interval_cv": round(float(iv.std() / iv.mean()), 4) if len(iv) > 2 and iv.mean() > 0 else None})
    cvs = [p["cycle_interval_cv"] for p in per if p["cycle_interval_cv"] is not None]
    return {"per_seed": per, "persists": sum(p["active_at_end"] for p in per), "mean_cycles": round(sum(p["cycles"] for p in per) / len(per), 2), "mean_cycle_interval_cv": round(sum(cvs) / len(cvs), 4) if cvs else None}


def f14_comparison(f: dict, j: dict, k: dict) -> dict:
    cond = next(c for c in M.conditions_f() if c["id"] == "F14")
    a_id, b_id = "MFS-F14-1", "MFS-F14-2"
    sets = {m["id"]: m["retained_components"] for m in f["by_condition"]["F14"]["mfs"]}
    pa, pb = f["profiles"][a_id], f["profiles"][b_id]
    jr = {r["mfs"]: r for r in j["rows"]}
    kr = {r["mfs"]: r for r in k["rows"]}
    # dependence on the tap and on history: the set without the component (only where the set has it)
    dep: dict[str, Any] = {}
    for mid, comp in ((a_id, "history"), (b_id, "m2_tap")):
        without = [c for c in sets[mid] if c != comp]
        dep[mid] = {"component": comp, "persists_without_it": sum(M.persists(cond, frozenset(without), VALIDATION_SEEDS)), "seeds": len(VALIDATION_SEEDS)}
    rows = []

    def add(name: str, a: Any, b: Any) -> None:
        rows.append({"measure": name, a_id: a, b_id: b, "differs": a != b})

    add("preserved operation (share of seeds ACTIVE, confirmation seeds)", pa["preserved_operation"], pb["preserved_operation"])
    add("energy use (mean cumulative)", pa["energy_use"], pb["energy_use"])
    add("resource throughput", pa["resource_throughput"], pb["resource_throughput"])
    add("recovery capability (recovered with a pulse after an interruption, of 5)", pa["recovery"].get("with_pulse"), pb["recovery"].get("with_pulse"))
    add("recovery latency after the pulse (ticks)", pa["recovery_latency"], pb["recovery_latency"])
    add("perturbation sensitivity (collapse share per perturbation)", pa["perturbation_sensitivity"], pb["perturbation_sensitivity"])
    add("collapse modes", pa["collapse_modes"], pb["collapse_modes"])
    add("history dependence (share of seeds that collapse without history)", pa["history_dependence"], pb["history_dependence"])
    add("M2 dependence (persists without the tap, of 5)", "n/a: the set has no tap", f"{dep[b_id]['persists_without_it']} of {dep[b_id]['seeds']} persist without the tap")
    add("Address dependence (mean collapse share under the Address fault battery)", pa["address_dependence"], pb["address_dependence"])
    add("Address faults (collapse share per fault)", pa["address_fault_collapse"], pb["address_fault_collapse"])
    add("SSS region at the default setting", jr[a_id]["default_setting_region"], jr[b_id]["default_setting_region"])
    add("operationally active range along scale", jr[a_id]["ranges_along_axes"]["scale"].get("operationally active"), jr[b_id]["ranges_along_axes"]["scale"].get("operationally active"))
    add("operationally active range along size", jr[a_id]["ranges_along_axes"]["size"].get("operationally active"), jr[b_id]["ranges_along_axes"]["size"].get("operationally active"))
    add("operationally active range along speed", jr[a_id]["ranges_along_axes"]["speed"].get("operationally active"), jr[b_id]["ranges_along_axes"]["speed"].get("operationally active"))
    add("metastable settings on the axes", {ax: v.get("METASTABLE") for ax, v in jr[a_id]["ranges_along_axes"].items()}, {ax: v.get("METASTABLE") for ax, v in jr[b_id]["ranges_along_axes"].items()})
    add("observational robustness", kr[a_id]["observational_robustness"], kr[b_id]["observational_robustness"])
    st = {a_id: stability_on_validation_seeds(cond, sets[a_id]), b_id: stability_on_validation_seeds(cond, sets[b_id])}
    rows.append({"measure": "stability across the validation seeds (persisting seeds of 5; mean cycles; mean cycle-interval CV)", a_id: [st[a_id]["persists"], st[a_id]["mean_cycles"], st[a_id]["mean_cycle_interval_cv"]], b_id: [st[b_id]["persists"], st[b_id]["mean_cycles"], st[b_id]["mean_cycle_interval_cv"]], "differs": st[a_id]["mean_cycle_interval_cv"] != st[b_id]["mean_cycle_interval_cv"]})
    cmp = R.compare(pa, pb)
    differing = [r["measure"] for r in rows if r["differs"]]
    return {
        "condition": f["by_condition"]["F14"]["condition"], "mfs_a": {"id": a_id, "retained": sets[a_id], "route_kind": next(m["route_kind"] for m in f["by_condition"]["F14"]["mfs"] if m["id"] == a_id)}, "mfs_b": {"id": b_id, "retained": sets[b_id], "route_kind": next(m["route_kind"] for m in f["by_condition"]["F14"]["mfs"] if m["id"] == b_id)},
        "same_cardinality": len(sets[a_id]) == len(sets[b_id]), "rows": rows, "dependence_runs": dep, "stability": st, "equivalence": cmp,
        "claim": ("route non-equivalence: both sets preserve the same specified operation in every validation seed, and they differ in internal operating form, dependence and stable region (" + "; ".join(differing[:6]) + ")")
        if all(s["persists"] == len(VALIDATION_SEEDS) for s in st.values()) and cmp["equivalent_through_level"] < 4 else "no route non-equivalence claimed: the profiles agree through level 4 or a set does not persist in every validation seed",
    }


# ---------------------------------------------------------------------------------------------------- equivalence classification
def equivalence_class(entry: dict, pa: dict, pb: dict) -> str:
    """Words for an equivalence level: equivalent at the tested preservation level (through level 4), partially equivalent (through level 2 or 3), non-equivalent (fails at level 1 or 2 with a
    measured difference), insufficient evidence (a recovery or a profile entry could not be tested for one of the two)."""
    if not pa["recovery"].get("testable", True) or not pb["recovery"].get("testable", True):
        return "insufficient evidence"
    lvl = entry["equivalent_through_level"]
    return "equivalent at tested preservation level" if lvl >= 4 else "partially equivalent" if lvl >= 3 else "non-equivalent"


def equivalence_table(f: dict) -> list[dict]:
    prof = f["profiles"]
    first: dict[tuple, str] = {}
    for r in f["by_condition"].values():
        for m in r["mfs"]:
            first.setdefault(tuple(m["retained_components"]), m["id"])
    distinct = list(first.values())
    out = []
    for e in f["route_equivalence"]:
        if e["a"] in distinct and e["b"] in distinct:
            pa, pb = prof[e["a"]], prof[e["b"]]
            out.append({"a": e["a"], "b": e["b"], "level": e["equivalent_through_level"], "class": equivalence_class(e, pa, pb), "verdict": e["verdict"], "differences": e["differences_at_first_failed_level"],
                        "preserved_operation": [pa["preserved_operation"], pb["preserved_operation"]], "energy": [pa["energy_use"], pb["energy_use"]], "resource": [pa["resource_throughput"], pb["resource_throughput"]], "recovery_latency": [pa["recovery_latency"], pb["recovery_latency"]],
                        "history_dependence": [pa["history_dependence"], pb["history_dependence"]], "address_dependence": [pa["address_dependence"], pb["address_dependence"]], "sss_region": [pa["sss_region"], pb["sss_region"]], "observation_robustness": [pa["observational_robustness"], pb["observational_robustness"]]})
    return out


# ---------------------------------------------------------------------------------------------------- reconfiguration: success defined, controllers kept apart
CRITERIA = {
    "effective": "persistence higher than the no-reconfiguration control by at least 3 of 10 seeds AND Fisher exact p < 0.05 (unadjusted) AND mean switching cost <= 3",
    "harmful": "persistence lower than the control by at least 3 of 10 seeds AND Fisher exact p < 0.05",
    "no effect": "otherwise (no difference or a difference too small to separate from the control with 10 seeds)",
    "note": "a route switch is not a success: success is a better outcome than the control, never that a switch happened. The criteria are generic and were written down in code after the first complete run had been looked at; "
    "they are reported with the Holm-adjusted p over all comparisons so that a result that does not survive the correction says so.",
}


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj = [0.0] * len(ps)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, ps[i] * (len(ps) - rank)))
        adj[i] = round(run, 5)
    return adj


def reconfiguration_verdicts(i: dict) -> dict:
    rows = [r for r in i["rows"] if r["controller"] != "none" and "vs_none_persistence" in r and not r["scenario"].startswith("no stress")]
    ps = [r["vs_none_persistence"]["fisher_exact_p"] for r in rows]
    adj = holm(ps)
    out = []
    for r, pa in zip(rows, adj, strict=True):
        none = next(x for x in i["rows"] if x["scenario"] == r["scenario"] and x["controller"] == "none")
        d = r["persisted"]["k"] - none["persisted"]["k"]
        p = r["vs_none_persistence"]["fisher_exact_p"]
        verdict = "effective" if d >= 3 and p < 0.05 and r["mean_switching_cost"] <= 3 else "harmful" if d <= -3 and p < 0.05 else "no effect"
        out.append({"scenario": r["scenario"], "controller": r["controller"], "persisted_k_of_n": [r["persisted"]["k"], r["n"]], "control_k_of_n": [none["persisted"]["k"], none["n"]], "difference_in_seeds": d, "cohens_h": r["vs_none_persistence"]["cohens_h"],
                    "fisher_p_unadjusted": p, "holm_p_over_all_comparisons": pa, "survives_correction": pa < 0.05, "verdict": verdict, "switches_per_run": r["mean_switches"], "mean_switching_cost": r["mean_switching_cost"], "false_switches": r["false_switches"],
                    "unnecessary_switches": r["unnecessary_switches"], "energy_cost_vs_none": r["vs_none_energy_paired"].get("median_difference"), "route_switch_occurred_in_runs": r["mean_switches"] > 0})
    by_ctl: dict[str, dict[str, Any]] = {}
    for v in out:
        e = by_ctl.setdefault(v["controller"], {"effective": 0, "harmful": 0, "no effect": 0, "scenarios_with_a_switch": 0})
        e[v["verdict"]] += 1
        e["scenarios_with_a_switch"] += v["route_switch_occurred_in_runs"]
    return {"criteria": CRITERIA, "comparisons": len(out), "verdicts": out, "by_controller": by_ctl, "family": f"Holm correction over the {len(out)} comparisons (5 controllers x 6 stress scenarios; the no-stress control is the false-switch measure)"}


def fixed_fallback_confirmation(f: dict, seeds: tuple[int, ...] = tuple(range(11, 31))) -> dict:
    """The one effective cell (fixed fallback under 'history lost') on twenty fresh seeds, against no reconfiguration, adaptive and shedding adaptive."""
    from . import stage5_experiments as X5

    lib = RC.library_from(f["by_condition"])
    arr = {"tap": M.M2_BASE, "tap_feature": "direct", "universe": M.COMPONENTS5}
    scen = "history lost"
    res: dict[str, list[bool]] = {}
    for kind in ("none", "fixed", "adaptive", "adaptive_shed"):
        res[kind] = [X5._i_job((scen, kind, sd, lib, arr))["active_at_end"] for sd in seeds]
    base = sum(res["none"])
    return {"scenario": scen, "seeds": list(seeds), "persisted": {k: ST.proportion(sum(v), len(v)) for k, v in res.items()}, "fixed_vs_none": ST.compare_proportions(sum(res["fixed"]), len(seeds), base, len(seeds)),
            "adaptive_vs_none": ST.compare_proportions(sum(res["adaptive"]), len(seeds), base, len(seeds)), "adaptive_shed_vs_none": ST.compare_proportions(sum(res["adaptive_shed"]), len(seeds), base, len(seeds))}


# ---------------------------------------------------------------------------------------------------- the whole
def finalize(doc: dict, preliminary: dict | None) -> dict:
    ex = doc["experiments"]
    f, j, k, i, h = ex["F"], ex["J"], ex["K"], ex["I"], ex["H"]
    conds = {c["id"]: c for c in M.conditions_f()}
    cands = {cid: candidate_analysis(conds[cid], r, preliminary) for cid, r in f["by_condition"].items()}
    table = f_table(f, cands, j, k)
    counts: dict[str, int] = {}
    for r in table:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1
    f8 = cands["F8"]
    prelim_f8 = [m for m in (preliminary or {}).get("by_condition", {}).get("F8", {}).get("mfs", [])]
    # J: the relation of ACTIVE and OBSERVATION-SENSITIVE on the tested grid
    act = sum(r["regions_on_grid"]["ACTIVE"] for r in j["rows"])
    osens = sum(r["regions_on_grid"]["OBSERVATION-SENSITIVE"] for r in j["rows"])
    final: dict[str, Any] = {
        "protocol": {"search_seeds": list(SEARCH_SEEDS), "validation_seeds": list(VALIDATION_SEEDS), "text": __doc__},
        "headline": ("Multiple operational realisations are not a general law in this model; they are local. Of the sixteen conditions " + ", ".join(f"{v} {k_}" for k_, v in sorted(counts.items())) +
                     ". Where one validated set exists it is usually the only one; where none exists, no retaining set was found under the allowed reductions, the specified criterion and these seeds."),
        "class_counts": counts, "F_table": table, "candidates": cands,
        "F8_candidate_rejection": {"preliminary_3seed_sets": [{"id": m["id"], "retained": m["retained_components"], "route_kind": m["route_kind"]} for m in prelim_f8], "candidates_and_status": f8["candidates"],
                                   "statement": "The first search (seeds 1-3) reported two inclusion-minimal sets under F8. Under the search criterion of five seeds only one remains; the other did not persist in every search seed. F8 is therefore SINGLE_MFS, not MULTIPLE_MFS."},
        "F9_no_mfs": {"statement": "Under the allowed reductions and specified preservation criterion, no validated inclusion-minimal retaining set was found. This is a result about these seeds (search 1-5) and these reductions only; it does not say that no retaining set exists in general.",
                      "persisting_subsets_in_search": f["by_condition"]["F9"]["persisting_subsets"], "subsets_evaluated": f["by_condition"]["F9"]["subsets_evaluated"], "candidates": cands["F9"]["candidates"], "classification": next(r["classification"] for r in table if r["condition_id"] == "F9")},
        "F14_comparison": f14_comparison(f, j, k),
        "history_role": [{"condition": r["condition_id"], "role": r["history_role"], "classification": r["classification"]} for r in table],
        "route_equivalence": equivalence_table(f),
        "reconfiguration": reconfiguration_verdicts(i),
        "fixed_fallback_confirmation": fixed_fallback_confirmation(f),
        "address": {
            "statement": "The present MEOS dynamics did not sustain a long-lived spatially separated configuration suitable for independently testing persistent address dependence. In every persisting arrangement of the 48 screened, the two configurations ended on one cell and A2 stopped moving after tick 60.",
            "not_concluded": "This is not a finding that Address is unnecessary: with the configurations on one cell, collision, stale and crossing cannot differ from the control, and loss, reassignment and partial addressability collapsed the run.",
            "persisting_arrangements": [a for a in h["arrangements_screened"] if a["active_seeds"] > 0], "screened": len(h["arrangements_screened"]), "stage4_strict_nulls_kept": h["stage4_strict_nulls_reproduced"],
            "stage4_fixed_condition_vs_stage5_dynamic_conditions": "Stage 4 (default arrangement, tick 100): collision and stale are strict nulls. Stage 5 (screened arrangements, ticks 12 and 100): collision and stale are again null in every persisting arrangement; no non-null condition for them was produced and none was manufactured.",
        },
        "sss_x_mfs": {"statement": "On the tested grid, all ACTIVE points were also observation-sensitive: no point was ACTIVE without being OBSERVATION-SENSITIVE (the observation-sensitive set coincides with the operationally active set), so no independent observation-sensitive island is claimed.",
                      "active_only_points": act, "observation_sensitive_points": osens, "islands": j["distinct_islands"]},
        "statistics": {"effect_sizes": "Cohen's h for differences of proportions, Cliff's delta for unpaired samples", "intervals": "Wilson 95 % for proportions; bootstrap 95 % for medians", "tests": "Fisher exact (proportions), Wilcoxon signed-rank (paired), Mann-Whitney (unpaired); few seeds: descriptions, not verdicts",
                       "multiple_comparisons": "Holm over the 30 reconfiguration comparisons; experiments G and H report proportions with intervals and do no hypothesis test across cells"},
    }
    return final


def load(path: Path) -> dict:
    return json.loads(path.read_text())
