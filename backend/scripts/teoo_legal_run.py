"""AI legal governance experiments (EXP-01 .. EXP-10, CMP-01) on the synthetic institution: pre-register (freeze), run, analyse, save. Run: PYTHONPATH=. python scripts/teoo_legal_run.py OUT_DIR [--workers N] [--check]

Same discipline as the Phase 4 runner: the protocols are frozen in a hash-chained registry before the first datum; confirmatory or exploratory is the registry's decision; every result is kept, supported or not. There was no pilot:
the code was smoke-tested on seed 1 only. The guarantee catalogue behind EXP-09 is PROVISIONAL (see xzr/teoo/legal.py). Everything is a result about a SYNTHETIC institution and about this implementation."""

from __future__ import annotations

import gzip
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import numpy as np

from xzr.teoo import legal as L
from xzr.teoo import legal_experiments as LX
from xzr.teoo import protocol as PR
from xzr.teoo import stats as S
from xzr.teoo.provenance import digest_of

SEEDS = list(range(2001, 2031))
SEEDS_CMP = list(range(3001, 3031))


def mean_arm(units: list[dict], arm: str, key: str) -> float:
    return float(np.mean([u["arms"][arm][key] for u in units]))


def sf(units: list[dict], arm_a: str, arm_b: str, key: str, seed: int) -> dict:
    """paired difference arm_a - arm_b of `key` over worlds"""
    d = [u["arms"][arm_a][key] - u["arms"][arm_b][key] for u in units]
    return {**S.paired_sign_flip(d, seed=seed), "contrast": f"{arm_a} minus {arm_b} on {key}", f"mean_{arm_a}": mean_arm(units, arm_a, key), f"mean_{arm_b}": mean_arm(units, arm_b, key)}


def eq(units: list[dict], arm_a: str, arm_b: str, key: str, margin: float, seed: int) -> dict:
    d = [u["arms"][arm_a][key] - u["arms"][arm_b][key] for u in units]
    return {**S.equivalence(d, margin, seed=seed), "contrast": f"{arm_a} minus {arm_b} on {key}", f"mean_{arm_a}": mean_arm(units, arm_a, key), f"mean_{arm_b}": mean_arm(units, arm_b, key)}


def spearman_per_world(units: list[dict]) -> dict:
    from scipy.stats import spearmanr

    rhos = [float(spearmanr(u["inferential_scores"], u["operational_effects"])[0]) for u in units]
    rhos = [r for r in rhos if not np.isnan(r)]
    return {**S.paired_sign_flip(rhos, seed=44), "contrast": "per-world Spearman between how convincing an intervention is and what it does", "mean_rho": float(np.mean(rhos))}


def A(i: str, h: str, outcome: str, method: str, conf: bool = True, **kw: Any) -> dict:
    return {"id": i, "hypothesis": h, "outcome": outcome, "method": method, "confirmatory": conf, **kw}


def protocols() -> dict[str, tuple[dict, list]]:
    def P(eid: str, hyps: list, conds: list, control: str, seeds: list, outcomes: dict, analyses: list, fails: list, inst: dict) -> dict:
        return PR.new_protocol(experiment_id=eid, hypotheses=hyps, targets=["exclusion and access of a synthetic institution"], instrument_conditions=inst, control_condition=control, conditions=conds, seeds=seeds, trials_per_condition=1,
                               stopping_rule={"type": "fixed-n", "units": len(seeds), "no interim analysis": True}, outcomes=outcomes, analyses=analyses, multiplicity="holm", failure_conditions=fails,
                               reproduction={"generator": "xzr.teoo.legal_experiments", "steps": ["run unit per seed", "analyse"], "world": "xzr.teoo.legal (SYNTHETIC institution)"})
    H = lambda i, t: {"id": i, "statement": t}  # noqa: E731
    out: dict[str, tuple[dict, list]] = {}
    out["EXP-01"] = (P("LEG-EXP-01", [H("H1", "Fairness optimisation of the score narrows the true-positive-rate gap"), H("H2", "...but leaves the persistence of exclusion unchanged (equivalence within 0.05)"), H("H3", "Removing the proxy gate in addition lowers exclusion of the qualified")],
                       ["baseline", "fairness_opt", "fairness_opt_gate_removed"], "baseline", SEEDS, {"primary": ["tpr_gap", "exclusion_persistence"], "secondary": ["exclusion_qualified"]},
                       [A("L01a", "H1", "tpr_gap", "paired-sign-flip"), A("L01b", "H2", "exclusion_persistence", "equivalence", margin=0.05), A("L01c", "H3", "exclusion_qualified", "paired-sign-flip")], ["fewer than 30 worlds"], {"population": 300, "periods": 24}),
                      [("L01a", lambda u: sf(u, "baseline", "fairness_opt", "tpr_gap", 1)), ("L01b", lambda u: eq(u, "fairness_opt", "baseline", "exclusion_persistence", 0.05, 2)), ("L01c", lambda u: sf(u, "fairness_opt", "fairness_opt_gate_removed", "exclusion_qualified", 3))])
    out["EXP-02"] = (P("LEG-EXP-02", [H("H1", "Deleting the score without removing the proxy gate raises exclusion of the qualified (the proxy takes its place)"), H("H2", "Removing the gate lowers it"), H("H3", "Deleting both leaves a lottery that ignores qualification and raises exclusion of the qualified")],
                       ["baseline", "lower_threshold", "delete_score", "remove_gate", "delete_score_and_gate"], "baseline", SEEDS, {"primary": ["exclusion_qualified"], "secondary": ["group_exclusion_gap", "access_rate"]},
                       [A("L02a", "H1", "exclusion_qualified", "paired-sign-flip"), A("L02b", "H2", "exclusion_qualified", "paired-sign-flip"), A("L02c", "H3", "exclusion_qualified", "paired-sign-flip")], ["fewer than 30 worlds"], {"population": 300, "periods": 24}),
                      [("L02a", lambda u: sf(u, "delete_score", "baseline", "exclusion_qualified", 4)), ("L02b", lambda u: sf(u, "baseline", "remove_gate", "exclusion_qualified", 5)), ("L02c", lambda u: sf(u, "delete_score_and_gate", "baseline", "exclusion_qualified", 6))])
    out["EXP-03"] = (P("LEG-EXP-03", [H("H1", "After the gate is removed, the group gap in exclusion is larger when the score still carries the inherited record and the second institution still inherits, than when those dependencies are cut"), H("H2", "(descriptive) how much of the gap is regenerated")],
                       ["before_removal", "gate_removed_with_residual_dependencies", "gate_removed_dependencies_cut"], "before_removal", SEEDS, {"primary": ["group_exclusion_gap"], "secondary": ["excl_g1"]},
                       [A("L03a", "H1", "group_exclusion_gap", "paired-sign-flip"), A("L03b", "H2", "group_exclusion_gap", "descriptive", False)], ["fewer than 30 worlds"], {"population": 300, "periods": 24}),
                      [("L03a", lambda u: sf(u, "gate_removed_with_residual_dependencies", "gate_removed_dependencies_cut", "group_exclusion_gap", 7)),
                       ("L03b", lambda u: {"method": "descriptive", "regenerated_share_of_gap": float(np.mean([u_["arms"]["gate_removed_with_residual_dependencies"]["group_exclusion_gap"] / max(1e-9, u_["arms"]["before_removal"]["group_exclusion_gap"]) for u_ in u])),
                                           "gap_before": mean_arm(u, "before_removal", "group_exclusion_gap"), "gap_residual": mean_arm(u, "gate_removed_with_residual_dependencies", "group_exclusion_gap"), "gap_cut": mean_arm(u, "gate_removed_dependencies_cut", "group_exclusion_gap")})])
    out["EXP-04"] = (P("LEG-EXP-04", [H("H1", "An appeal route that can reverse nothing files appeals but overturns no wrongful denial"), H("H2", "An independent reviewer with authority overturns more wrongful denials than a formal-only route")],
                       ["formal_only", "effective"], "formal_only", SEEDS, {"primary": ["overturn_rate_of_wrongful"], "secondary": ["formal_appeal_rate", "exclusion_qualified", "burden_subject"]},
                       [A("L04a", "H1", "overturn_rate_of_wrongful", "descriptive", False), A("L04b", "H2", "overturn_rate_of_wrongful", "paired-sign-flip")], ["fewer than 30 worlds"], {"population": 300, "periods": 24}),
                      [("L04a", lambda u: {"method": "descriptive", "formal_only_appeal_rate": mean_arm(u, "formal_only", "formal_appeal_rate"), "formal_only_overturn_rate": mean_arm(u, "formal_only", "overturn_rate_of_wrongful"), "worlds_with_any_overturn_in_formal_only": int(sum(x["arms"]["formal_only"]["overturn_rate_of_wrongful"] > 0 for x in u))}),
                       ("L04b", lambda u: sf(u, "effective", "formal_only", "overturn_rate_of_wrongful", 8))])
    out["EXP-05"] = (P("LEG-EXP-05", [H("H1", "Correcting the decisions lowers exclusion even when the correction does not reach the second institution"), H("H2", "Propagating the correction raises access at the second institution"), H("H3", "Re-entry support adds persons who regain access")],
                       ["no_correction", "correction_no_propagation", "correction_propagated", "correction_propagated_with_reentry_support"], "no_correction", SEEDS, {"primary": ["exclusion_qualified", "downstream_access_qualified"], "secondary": ["reentered_qualified"]},
                       [A("L05a", "H1", "exclusion_qualified", "paired-sign-flip"), A("L05b", "H2", "downstream_access_qualified", "paired-sign-flip"), A("L05c", "H3", "reentered_qualified", "paired-sign-flip")], ["fewer than 30 worlds"], {"population": 300, "periods": 24, "correction_period": 8}),
                      [("L05a", lambda u: sf(u, "no_correction", "correction_no_propagation", "exclusion_qualified", 9)), ("L05b", lambda u: sf(u, "correction_propagated", "correction_no_propagation", "downstream_access_qualified", 10)),
                       ("L05c", lambda u: sf(u, "correction_propagated_with_reentry_support", "correction_propagated", "reentered_qualified", 11))])
    out["EXP-06"] = (P("LEG-EXP-06", [H("H1", "A larger weight of the inherited record in the score widens the group gap in exclusion"), H("H2", "Expiry of the inherited part narrows it")],
                       ["lambda_0.0", "lambda_0.4", "lambda_0.8", "lambda_1.2", "lambda_0.8_with_expiry"], "lambda_0.0", SEEDS, {"primary": ["group_exclusion_gap"], "secondary": ["excl_g1"]},
                       [A("L06a", "H1", "group_exclusion_gap", "paired-sign-flip"), A("L06b", "H2", "group_exclusion_gap", "paired-sign-flip")], ["fewer than 30 worlds"], {"population": 300, "periods": 24}),
                      [("L06a", lambda u: sf(u, "lambda_1.2", "lambda_0.0", "group_exclusion_gap", 12)), ("L06b", lambda u: sf(u, "lambda_0.8", "lambda_0.8_with_expiry", "group_exclusion_gap", 13))])
    out["EXP-07"] = (P("LEG-EXP-07", [H("H1", "One more observed field lets the observer identify more of the active mechanisms than the initial two"), H("H2", "Choosing the field from the outcome identifies more than choosing it without looking, at equal cost"), H("H3", "... and more than a field order fixed in advance")],
                       ["fixed", "prespecified_revision", "outcome_responsive_revision", "cost_matched_static"], "fixed", SEEDS, {"primary": ["active mechanisms identified"], "secondary": ["false identifications", "active but not observed"]},
                       [A("L07a", "H1", "true_identified", "paired-sign-flip"), A("L07b", "H2", "true_identified", "paired-sign-flip"), A("L07c", "H3", "true_identified", "paired-sign-flip")], ["fewer than 30 worlds"], {"fields_initial": 2, "mechanisms": list(LX.MECHS)}),
                      [("L07a", lambda u: sf(u, "cost_matched_static", "fixed", "true_identified", 14)), ("L07b", lambda u: sf(u, "outcome_responsive_revision", "cost_matched_static", "true_identified", 15)), ("L07c", lambda u: sf(u, "outcome_responsive_revision", "prespecified_revision", "true_identified", 16))])
    out["EXP-08"] = (P("LEG-EXP-08", [H("H1", "The three interventions that are most convincing as arguments achieve less than the three operationally best ones the actor can execute"), H("H2", "Some of the most convincing interventions cannot be executed by the actor"), H("H3", "How convincing an intervention is correlates with what it does")],
                       ["inferential_top3", "operational_best3"], "inferential_top3", SEEDS, {"primary": ["realised effect on exclusion"], "secondary": ["share executable", "rank correlation"]},
                       [A("L08a", "H1", "effect", "paired-sign-flip"), A("L08b", "H2", "top3_executable_share", "paired-sign-flip"), A("L08c", "H3", "spearman", "paired-sign-flip")], ["fewer than 30 worlds"], {"menu": list(LX.MENU), "actor can execute": 5}),
                      [("L08a", lambda u: {**S.paired_sign_flip([x["effect_of_operationally_best_executable3"] - x["realised_effect_of_inferential_top3"] for x in u], seed=17), "contrast": "operationally best executable three minus the most convincing three (realised)",
                                           "mean_operational": float(np.mean([x["effect_of_operationally_best_executable3"] for x in u])), "mean_inferential": float(np.mean([x["realised_effect_of_inferential_top3"] for x in u]))}),
                       ("L08b", lambda u: {**S.paired_sign_flip([1 - x["top3_executable_share"] for x in u], seed=18), "contrast": "share of the most convincing three that the actor cannot execute", "mean_share_executable": float(np.mean([x["top3_executable_share"] for x in u]))}),
                       ("L08c", spearman_per_world)])
    out["EXP-09"] = (P("LEG-EXP-09", [H("H1", "Every removed provision is reported ABSENT when observed, and no provision that is present is"), H("H2", "A provision that is not observed is reported INDETERMINATE, never SECURED or ABSENT"), H("H3", "A formal route that cannot change anything is found PARTIAL by the assessment and passed by a checklist of formal provisions"),
                                     H("H4", "Every state that is not SECURED or INAPPLICABLE names a remedy path")],
                       ["formal_checklist", "assessment"], "formal_checklist", SEEDS, {"primary": ["detection, false detection, indeterminate handling"], "secondary": ["remedy"]},
                       [A("L09a", "H1", "violation_detection", "descriptive", False), A("L09b", "H2", "unseen_misreported", "descriptive", False), A("L09c", "H3", "formal_but_ineffective", "paired-sign-flip"), A("L09d", "H4", "remedy_share", "descriptive", False)], ["fewer than 30 worlds"],
                       {"guarantee catalogue": "PROVISIONAL (not verified against the originals)", "provisions": len(L.PROVISIONS)}),
                      [("L09a", lambda u: {"method": "descriptive", "violation_detection_full": float(np.mean([x["violation_detection_full"] for x in u])), "false_detection_full": float(np.mean([x["false_detection_full"] for x in u])), "criterion_met": all(x["violation_detection_full"] == 1.0 and x["false_detection_full"] == 0.0 for x in u)}),
                       ("L09b", lambda u: {"method": "descriptive", "unseen_removed_total": int(sum(x["unseen_removed"] for x in u)), "reported_indeterminate": int(sum(x["unseen_removed_reported_indeterminate"] for x in u)), "misreported_secured_or_absent": int(sum(x["unseen_removed_reported_secured_or_absent"] for x in u)),
                                           "false_absent_partial_mean": float(np.mean([x["false_absent_partial"] for x in u])), "criterion_met": all(x["unseen_removed_reported_secured_or_absent"] == 0 for x in u) and all(x["false_absent_partial"] == 0 for x in u)}),
                       ("L09c", lambda u: {**S.paired_sign_flip([x["formal_but_ineffective_found"] - x["rule_based_finds_ineffective"] for x in u], seed=19), "contrast": "assessment finds the ineffective route minus the checklist finds it", "mean_assessment": float(np.mean([x["formal_but_ineffective_found"] for x in u])),
                                           "mean_checklist": float(np.mean([x["rule_based_finds_ineffective"] for x in u]))}),
                       ("L09d", lambda u: {"method": "descriptive", "remedy_share_mean": float(np.mean([x["remedy_given_when_not_secured"] for x in u])), "inapplicable_reason_checked_in_all": all(x["inapplicable_has_checked_reason"] for x in u), "criterion_met": all(x["remedy_given_when_not_secured"] == 1.0 for x in u)})])
    out["EXP-10"] = (P("LEG-EXP-10", [H("H1", "Moving review to an independent body with authority lowers exclusion compared with review by the institution itself"), H("H2", "A consent step and formal procedure in front of that body shifts burden onto the subject compared with the plain independent route")],
                       ["institution_self_review", "independent_body_with_authority", "independent_body_with_consent_and_formal_procedure", "subject_initiated_correction_no_consent_step"], "institution_self_review", SEEDS, {"primary": ["exclusion_qualified", "burden_subject"], "secondary": ["overturn_rate_of_wrongful", "burden_institution"]},
                       [A("L10a", "H1", "exclusion_qualified", "paired-sign-flip"), A("L10b", "H2", "burden_subject", "paired-sign-flip")], ["fewer than 30 worlds"], {"population": 300, "periods": 24}),
                      [("L10a", lambda u: sf(u, "institution_self_review", "independent_body_with_authority", "exclusion_qualified", 20)), ("L10b", lambda u: sf(u, "independent_body_with_consent_and_formal_procedure", "independent_body_with_authority", "burden_subject", 21))])
    arms = ["rule_based_compliance", "fairness_optimisation", "structural_causal_model", "constrained_planning", "model_based_greedy", "osr_with_observation_revision", "constrained_planning_with_random_extra_field", "oracle_best_executable"]
    def vs_osr(a: str) -> Any:
        return lambda u: sf(u, a, "osr_with_observation_revision", "exclusion", 23)
    cmp_an = [("L11a", vs_osr("constrained_planning_with_random_extra_field"))] + [(f"L11{c}", vs_osr(a)) for c, a in zip("bcdef", arms[:5], strict=True)]
    out["CMP-01"] = (P("LEG-CMP-01", [H("H1", "Choosing the extra observed field from the outcome (the observation-revision planner) leaves less exclusion than the same planner with a randomly chosen extra field (non-redundancy of the revision rule)"),
                                     H("H2", "It leaves less exclusion than rule-based compliance, fairness optimisation, a structural causal model, constrained planning on the initial observation, and greedy model-based planning")],
                       arms, "rule_based_compliance", SEEDS_CMP, {"primary": ["exclusion of the qualified after the plan (lower is better)"], "secondary": ["rollouts used", "gap to the oracle"]},
                       [A("L11a", "H1", "exclusion", "paired-sign-flip")] + [A(f"L11{c}", "H2", "exclusion", "paired-sign-flip") for c in "bcdef"], ["fewer than 30 worlds"], {"fields_initial": 2, "budget": LX.BUDGET, "actor can execute": 6}),
                      cmp_an)
    return out


def _run(key: str, seed: int) -> dict:
    fn = {"EXP-01": LX.run_e01, "EXP-02": LX.run_e02, "EXP-03": LX.run_e03, "EXP-04": LX.run_e04, "EXP-05": LX.run_e05, "EXP-06": LX.run_e06, "EXP-07": LX.run_e07, "EXP-08": LX.run_e08, "EXP-09": LX.run_e09, "EXP-10": LX.run_e10, "CMP-01": LX.run_cmp}[key]
    return fn(seed)


def _job(a: tuple[str, int]) -> dict:
    return _run(*a)


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 6
    check = "--check" in sys.argv
    reg_path = out / "protocol_registry.jsonl"
    if reg_path.exists() and not check:
        reg_path.unlink()
    reg = PR.ProtocolRegistry(reg_path)
    protos = protocols()
    if not check:
        for p, _ in protos.values():
            reg.register(p)
            reg.freeze(p["experiment_id"], 1, time.time())
        for p, _ in protos.values():
            reg.note_first_data(p["experiment_id"], 1, time.time() + 1.0)
    summary: dict[str, Any] = {}
    for key, (p, analyses) in protos.items():
        t0 = time.time()
        seeds = p["seeds"]
        if check:
            u = _run(key, seeds[0])
            saved = json.loads((out / f"{key}_unit_first.json").read_text())
            summary[key] = {"replay_identical": digest_of(json.loads(json.dumps(u, default=str))) == saved["digest"]}
            continue
        with Pool(workers) as pool:
            units = pool.map(_job, [(key, s) for s in seeds])
        res: dict[str, Any] = {}
        for aid, fn in analyses:
            res[aid] = fn(units)
        fam = {a: r["p"] for a, r in res.items() if r.get("p") is not None and next(x for x in p["analyses"] if x["id"] == a).get("confirmatory")}
        for aid, h in S.holm(fam).items():
            res[aid]["p_holm"] = h["p_holm"]
        cls = "Implementation Property" if key == "EXP-09" else "Synthetic-world Result"
        for a in p["analyses"]:
            res[a["id"]]["registered_class"] = reg.analysis_class(p["experiment_id"], 1, a["id"])
            res[a["id"]]["evidence_class"] = cls
        doc = {"experiment_id": p["experiment_id"], "protocol_version": 1, "protocol_digest": PR.body_digest(p), "protocol": p, "units": len(units), "seeds": seeds, "evidence_class": cls, "seconds": round(time.time() - t0, 1), "results": res,
               "catalogue": L.CATALOGUE_STATUS if key == "EXP-09" else None, "note": "results about a SYNTHETIC institution and this implementation; not an observation of any institution, law or person"}
        if key == "CMP-01":
            doc["arms"] = {a: {"exclusion_mean": float(np.mean([x["arms"][a]["exclusion"] for x in units])), "exclusion_sd": float(np.std([x["arms"][a]["exclusion"] for x in units], ddof=1)), "rollouts_mean": float(np.mean([x["arms"][a]["rollouts"] for x in units]))} for a in units[0]["arms"]}
            doc["base_exclusion_mean"] = float(np.mean([x["base"] for x in units]))
            doc["osr_autonomous_revision_demonstrated"] = any(x["arms"]["osr_with_observation_revision"]["autonomous_revision_demonstrated"] for x in units)
        (out / f"{key}.json").write_text(json.dumps(doc, indent=1, default=str))
        (out / f"{key}_unit_first.json").write_text(json.dumps({"seed": seeds[0], "digest": digest_of(json.loads(json.dumps(units[0], default=str)))}))
        with gzip.open(out / f"{key}_units.json.gz", "wt") as f:
            json.dump(units, f, default=str, separators=(",", ":"))
        summary[key] = {a: {k: res[a].get(k) for k in ("mean_diff", "p", "p_holm", "supported", "criterion_met")} for a in res}
        print(key, round(time.time() - t0, 1), "s", json.dumps(summary[key], default=str)[:420], flush=True)
    print(json.dumps(summary) if check else f"registry verify: {reg.verify()}")


if __name__ == "__main__":
    main()
