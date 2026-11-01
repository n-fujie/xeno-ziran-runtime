"""AI legal governance, source-based evaluator: experiments LG2-EXP-01 .. 06. Pre-register (freeze), run, analyse, save. Run: PYTHONPATH=. python scripts/teoo_legal_run2.py OUT_DIR [--workers N] [--check]

New experiment ids: the results of EXP-01..10 and CMP-01 (run with the first implementation, ``legal_v1``) are not touched and are not re-labelled. Same discipline as before: protocols are frozen in a hash-chained registry before the
first datum; confirmatory or exploratory is the registry's decision; every result is kept. There was no pilot: the code was exercised on seed 1 only. The guarantees evaluated are those of the SOURCE text (V3.0 6.2); their operational
definitions are this implementation's. LG2-EXP-01 and 06 are Implementation Properties on synthetic ground truth, the others Synthetic-world Results."""

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
from xzr.teoo import legal_experiments2 as X
from xzr.teoo import protocol as PR
from xzr.teoo import stats as S
from xzr.teoo.provenance import digest_of

SEEDS = list(range(4001, 4031))
SEEDS_07 = list(range(5001, 5031))  # fresh seeds for LG2-EXP-07, which tests a correction made after LG2-EXP-01
H = lambda i, t: {"id": i, "statement": t}  # noqa: E731


def A(i: str, h: str, outcome: str, method: str, conf: bool = True, **kw: Any) -> dict:
    return {"id": i, "hypothesis": h, "outcome": outcome, "method": method, "confirmatory": conf, **kw}


def P(eid: str, hyps: list, conds: list, control: str, outcomes: dict, analyses: list, inst: dict) -> dict:
    seeds = SEEDS_07 if eid == "LG2-EXP-07" else SEEDS
    return PR.new_protocol(experiment_id=eid, hypotheses=hyps, targets=["findings and outcomes of a synthetic institution"], instrument_conditions=inst, control_condition=control, conditions=conds, seeds=seeds, trials_per_condition=1,
                           stopping_rule={"type": "fixed-n", "units": len(seeds), "no interim analysis": True}, outcomes=outcomes, analyses=analyses, multiplicity="holm", failure_conditions=["fewer than 30 worlds"],
                           reproduction={"generator": "xzr.teoo.legal_experiments2", "steps": ["run unit per seed", "analyse"], "world": "xzr.teoo.legal (SYNTHETIC institution; guarantees from the source text V3.0 6.2)"})


def rows(u: list[dict]) -> list[dict]:
    return [r for x in u for r in x["rows"]]


def arm_mean(u: list[dict], arm: str, key: str) -> float:
    return float(np.nanmean([x["arms"][arm][key] for x in u]))


def sf(u: list[dict], f: Any, label: str, seed: int) -> dict:
    d = [f(x) for x in u]
    d = [v for v in d if v is not None and not np.isnan(v)]
    return {**S.paired_sign_flip(d, seed=seed), "contrast": label}


def eqv(u: list[dict], f: Any, label: str, margin: float, seed: int) -> dict:
    d = [v for v in (f(x) for x in u) if v is not None and not np.isnan(v)]
    return {**S.equivalence(d, margin, seed=seed), "contrast": label}


def group(x: dict, **flt: bool) -> list[dict]:
    return [a for a in x["arms"].values() if all(a[k] == v for k, v in flt.items())]


def protocols() -> dict[str, tuple[dict, list]]:
    out: dict[str, tuple[dict, list]] = {}

    def e01_a(u):
        k = sum(not a for r in rows(u) for a in r["agree"])
        n = sum(len(r["agree"]) for r in rows(u))
        return {"method": "exact-upper-bound", "disagreements": k, "comparisons": n, "disagreement_rate": k / n, "upper95": S.upper_bound(k, n), "criterion": "upper 95% bound of disagreement <= 0.05", "criterion_met": (S.upper_bound(k, n) or 1) <= 0.05}

    def e01_e(u):
        deg = [r for r in rows(u) if r["u_truth_degraded"]]
        ok = [r for r in rows(u) if not r["u_truth_degraded"]]
        tp = sum(r["u_state"] == "ABSENT" for r in deg)
        fp = sum(r["u_state"] == "ABSENT" for r in ok)
        return {"method": "descriptive", "sensitivity": tp / max(1, len(deg)), "false_rate": fp / max(1, len(ok)), "false_upper95": S.upper_bound(fp, len(ok)), "n_degraded": len(deg), "n_not_degraded": len(ok),
                "criterion": "sensitivity >= 0.95 and upper 95% bound of the false rate <= 0.08", "criterion_met": tp / max(1, len(deg)) >= 0.95 and (S.upper_bound(fp, len(ok)) or 1) <= 0.08}
    out["LG2-EXP-01"] = (P("LG2-EXP-01", [H("H1", "The evaluator's states agree with an independent reading of the configuration for the findings that the configuration determines"), H("H2", "It finds the hard failures that exist by construction where a checklist of formal provisions does not"),
                                         H("H3", "A finding that is not observed is reported INDETERMINATE, never as a determinate state"), H("H4", "Changing the evidence of one finding changes no other finding (non-compensation), and no total is produced"),
                                         H("H5", "The Low-Score Subject finding U is detected when review is score-conditioned and is not reported when it is not")],
                           ["formal_checklist", "evaluator"], "formal_checklist", {"primary": ["agreement", "hard failures found", "misreported unobserved findings", "violations of non-compensation"], "secondary": ["U sensitivity and false rate"]},
                           [A("L201a", "H1", "agreement", "exact-upper-bound"), A("L201b", "H2", "hard_failures_found", "paired-sign-flip"), A("L201c", "H3", "unobserved_misreported", "descriptive"), A("L201d", "H4", "non_compensation_violations", "descriptive"),
                            A("L201e", "H5", "U", "descriptive")], {"configurations_per_world": 8, "levers": list(X.LEVERS)}),
                          [("L201a", e01_a),
                           ("L201b", lambda u: {**S.paired_sign_flip([float(np.mean([r["hard_found"] / r["hard_truth"] for r in x["rows"] if r["hard_truth"]]) - np.mean([r["hard_found_checklist"] / r["hard_truth"] for r in x["rows"] if r["hard_truth"]])) for x in u], seed=1),
                                                "contrast": "share of constructed hard failures found: evaluator minus checklist", "mean_evaluator": float(np.mean([r["hard_found"] / r["hard_truth"] for r in rows(u) if r["hard_truth"]])), "mean_checklist": float(np.mean([r["hard_found_checklist"] / r["hard_truth"] for r in rows(u) if r["hard_truth"]]))}),
                           ("L201c", lambda u: {"method": "descriptive", "misreported_total": int(sum(r["unobserved_misreported"] for r in rows(u))), "rows": len(rows(u)), "criterion_met": sum(r["unobserved_misreported"] for r in rows(u)) == 0}),
                           ("L201d", lambda u: {"method": "descriptive", "non_compensation_violations": int(sum(r["non_compensation_violations"] for r in rows(u))), "rows_without_total": int(sum(r["no_total"] for r in rows(u))), "rows_advisory": int(sum(r["advisory"] for r in rows(u))), "rows": len(rows(u)),
                                                "criterion_met": sum(r["non_compensation_violations"] for r in rows(u)) == 0 and all(r["no_total"] and r["advisory"] for r in rows(u))}),
                           ("L201e", e01_e)])
    out["LG2-EXP-02"] = (P("LG2-EXP-02", [H("H1", "The finding U is raised in worlds where low-score subjects are reviewed less often and not in the control (>= 0.95 detection; false-rate bound <= 0.15)"), H("H2", "Score-conditioned review opens a review-rate gap between high- and low-score subjects"),
                                         H("H3", "A conventional group-fairness measure (the true-positive-rate gap) does not register it (equivalence within 0.03)"), H("H4", "It lowers the share of wrongful denials that are overturned")],
                           ["control", "degraded"], "control", {"primary": ["U", "review-rate gap"], "secondary": ["true-positive-rate gap", "overturn rate"]},
                           [A("L202a", "H1", "U", "descriptive"), A("L202b", "H2", "review_gap", "paired-sign-flip"), A("L202c", "H3", "tpr_gap", "equivalence", margin=0.03), A("L202d", "H4", "overturn_rate_of_wrongful", "paired-sign-flip")], {"population": 300, "periods": 24}),
                          [("L202a", lambda u: {"method": "descriptive", "detection": float(np.mean([x["arms"]["degraded"]["U"] == "ABSENT" for x in u])), "false_rate": float(np.mean([x["arms"]["control"]["U"] == "ABSENT" for x in u])),
                                                "false_upper95": S.upper_bound(int(sum(x["arms"]["control"]["U"] == "ABSENT" for x in u)), len(u)), "criterion_met": np.mean([x["arms"]["degraded"]["U"] == "ABSENT" for x in u]) >= 0.95 and (S.upper_bound(int(sum(x["arms"]["control"]["U"] == "ABSENT" for x in u)), len(u)) or 1) <= 0.15}),
                           ("L202b", lambda u: {**sf(u, lambda x: x["arms"]["degraded"]["review_gap"] - x["arms"]["control"]["review_gap"], "review-rate gap, degraded minus control", 2), "mean_degraded": arm_mean(u, "degraded", "review_gap"), "mean_control": arm_mean(u, "control", "review_gap")}),
                           ("L202c", lambda u: {**eqv(u, lambda x: x["arms"]["degraded"]["tpr_gap"] - x["arms"]["control"]["tpr_gap"], "true-positive-rate gap, degraded minus control", 0.03, 3), "mean_degraded": arm_mean(u, "degraded", "tpr_gap"), "mean_control": arm_mean(u, "control", "tpr_gap")}),
                           ("L202d", lambda u: {**sf(u, lambda x: x["arms"]["control"]["overturn_rate_of_wrongful"] - x["arms"]["degraded"]["overturn_rate_of_wrongful"], "overturn rate, control minus degraded", 4), "mean_control": arm_mean(u, "control", "overturn_rate_of_wrongful"), "mean_degraded": arm_mean(u, "degraded", "overturn_rate_of_wrongful")})])
    names3 = ["authority_off", "authority_on"]
    out["LG2-EXP-03"] = (P("LG2-EXP-03", [H("H1", "A route whose reviewer has no authority overturns no wrongful denial however it is staffed, independent or easy to use (authority is necessary)"), H("H2", "Where there is authority, independence raises the share overturned"), H("H3", "... and so does capacity"),
                                         H("H4", "A low burden raises the share of wrongful denials that are appealed"), H("H5", "A formal route without authority is found ABSENT on G11 although appeals are filed")],
                           names3, "authority_off", {"primary": ["overturn rate"], "secondary": ["formal appeal rate", "states of G11, G12A, G12B"]},
                           [A("L203a", "H1", "overturn_rate_of_wrongful", "descriptive"), A("L203b", "H2", "overturn_rate_of_wrongful", "paired-sign-flip"), A("L203c", "H3", "overturn_rate_of_wrongful", "paired-sign-flip"), A("L203d", "H4", "formal_appeal_rate", "paired-sign-flip"),
                            A("L203e", "H5", "G11", "descriptive")], {"factors": ["authority", "independence", "capacity", "burden"], "arms": 16}),
                          [("L203a", lambda u: {"method": "descriptive", "arms_without_authority": int(sum(len(group(x, authority=False)) for x in u)), "arms_with_any_overturn": int(sum(a["overturn_rate_of_wrongful"] > 0 for x in u for a in group(x, authority=False))),
                                                "criterion_met": all(a["overturn_rate_of_wrongful"] == 0 for x in u for a in group(x, authority=False))}),
                           ("L203b", lambda u: sf(u, lambda x: np.mean([a["overturn_rate_of_wrongful"] for a in group(x, authority=True, independent=True)]) - np.mean([a["overturn_rate_of_wrongful"] for a in group(x, authority=True, independent=False)]), "overturn, independent minus not (authority on)", 5)),
                           ("L203c", lambda u: sf(u, lambda x: np.mean([a["overturn_rate_of_wrongful"] for a in group(x, authority=True, capacity=True)]) - np.mean([a["overturn_rate_of_wrongful"] for a in group(x, authority=True, capacity=False)]), "overturn, high capacity minus low (authority on)", 6)),
                           ("L203d", lambda u: sf(u, lambda x: np.mean([a["formal_appeal_rate"] for a in group(x, low_burden=True)]) - np.mean([a["formal_appeal_rate"] for a in group(x, low_burden=False)]), "formal appeal rate, low burden minus high", 7)),
                           ("L203e", lambda u: {"method": "descriptive", "arms_with_filed_appeals_and_no_authority": int(sum(a["formal_appeal_rate"] > 0.05 for x in u for a in group(x, authority=False))),
                                                "of_which_G11_absent": int(sum(a["formal_appeal_rate"] > 0.05 and a["G11"] == "ABSENT" for x in u for a in group(x, authority=False))),
                                                "criterion_met": all(a["G11"] == "ABSENT" for x in u for a in group(x, authority=False) if a["formal_appeal_rate"] > 0.05)})])
    out["LG2-EXP-04"] = (P("LG2-EXP-04", [H("H1", "Propagating a correction raises access at the second institution"), H("H2", "Material relief raises the resources of the qualified (restoration of money, services, time)"), H("H3", "Re-entry support adds people who regain access"),
                                         H("H4", "G15B is SECURED only when correction propagates and relief accompanies it (PARTIAL when relief is missing)")],
                           ["appeal_only", "plus_propagation", "plus_material_relief", "plus_reentry_support", "plus_resources_support", "plus_material_relief_without_relief"], "appeal_only",
                           {"primary": ["downstream access", "resources of the qualified", "persons re-entering"], "secondary": ["time to restoration", "G10, G15A-C states"]},
                           [A("L204a", "H1", "downstream_access_qualified", "paired-sign-flip"), A("L204b", "H2", "mean_resources_qualified", "paired-sign-flip"), A("L204c", "H3", "reentered_qualified", "paired-sign-flip"), A("L204d", "H4", "G15B", "descriptive")], {"population": 300, "periods": 24, "review_delay": 3}),
                          [("L204a", lambda u: {**sf(u, lambda x: x["arms"]["plus_propagation"]["downstream_access_qualified"] - x["arms"]["appeal_only"]["downstream_access_qualified"], "downstream access, propagation minus none", 8), "mean_with": arm_mean(u, "plus_propagation", "downstream_access_qualified"), "mean_without": arm_mean(u, "appeal_only", "downstream_access_qualified")}),
                           ("L204b", lambda u: {**sf(u, lambda x: x["arms"]["plus_material_relief"]["mean_resources_qualified"] - x["arms"]["plus_material_relief_without_relief"]["mean_resources_qualified"], "resources of the qualified, relief minus none", 9), "mean_with": arm_mean(u, "plus_material_relief", "mean_resources_qualified"), "mean_without": arm_mean(u, "plus_material_relief_without_relief", "mean_resources_qualified")}),
                           ("L204c", lambda u: {**sf(u, lambda x: x["arms"]["plus_reentry_support"]["reentered_qualified"] - x["arms"]["plus_material_relief"]["reentered_qualified"], "persons re-entering, re-entry support minus none", 10), "mean_with": arm_mean(u, "plus_reentry_support", "reentered_qualified"), "mean_without": arm_mean(u, "plus_material_relief", "reentered_qualified")}),
                           ("L204d", lambda u: {"method": "descriptive", "G15B_by_arm": {a: sorted({x["arms"][a]["G15B"] for x in u}) for a in u[0]["arms"]}, "criterion_met": all(x["arms"]["plus_material_relief"]["G15B"] == "SECURED" and x["arms"]["plus_material_relief_without_relief"]["G15B"] == "PARTIAL" and x["arms"]["appeal_only"]["G15B"] == "ABSENT" for x in u)})])
    out["LG2-EXP-05"] = (P("LG2-EXP-05", [H("H1", "A longer delay of review lengthens the time from denial to restoration"), H("H2", "A longer retention of a reversed denial at the second institution lowers access there"), H("H3", "Expiry of scores narrows the group gap in exclusion")],
                           ["delay0", "delay3", "delay6"], "delay0", {"primary": ["time to restoration", "downstream access", "group gap"], "secondary": ["exclusion", "persistence"]},
                           [A("L205a", "H1", "time_to_restoration_mean", "paired-sign-flip"), A("L205b", "H2", "downstream_access_qualified", "paired-sign-flip"), A("L205c", "H3", "group_exclusion_gap", "paired-sign-flip")], {"delay": [0, 3, 6], "retention": [3, 8], "expiry": [None, 4]}),
                          [("L205a", lambda u: sf(u, lambda x: np.nanmean([a["time_to_restoration_mean"] for k, a in x["arms"].items() if k.startswith("delay6")]) - np.nanmean([a["time_to_restoration_mean"] for k, a in x["arms"].items() if k.startswith("delay0")]), "time to restoration, delay 6 minus delay 0", 11)),
                           ("L205b", lambda u: sf(u, lambda x: np.mean([a["downstream_access_qualified"] for k, a in x["arms"].items() if "retention3" in k]) - np.mean([a["downstream_access_qualified"] for k, a in x["arms"].items() if "retention8" in k]), "downstream access, retention 3 minus 8", 12)),
                           ("L205c", lambda u: sf(u, lambda x: np.mean([a["group_exclusion_gap"] for k, a in x["arms"].items() if k.endswith("expiryNone")]) - np.mean([a["group_exclusion_gap"] for k, a in x["arms"].items() if k.endswith("expiry4")]), "group gap, no expiry minus expiry", 13))])
    def e07_h1(u):
        deg = [r for r in rows(u) if r["truth_degraded"]]
        fa = {k: sum(r[k] == "SECURED" for r in deg) for k in ("first_version", "min_cases_10", "min_cases_30", "min_cases_60")}
        return {"method": "descriptive", "degraded_configurations": len(deg), "reported_SECURED_while_degraded": fa, "criterion": "with min_cases = 30 no degraded configuration is reported SECURED", "criterion_met": fa["min_cases_30"] == 0}

    def e07_h2(u):
        deg = [r for r in rows(u) if r["truth_degraded"]]
        ok = [r for r in rows(u) if not r["truth_degraded"]]
        det = [r for r in deg if r["min_cases_30"] in ("ABSENT", "SECURED")]
        tp = sum(r["min_cases_30"] == "ABSENT" for r in det)
        fp = sum(r["min_cases_30"] == "ABSENT" for r in ok)
        return {"method": "descriptive", "degraded_with_a_performed_test": len(det), "detected_among_those": tp, "detection_when_performed": tp / max(1, len(det)), "false_rate": fp / max(1, len(ok)), "false_upper95": S.upper_bound(fp, len(ok)),
                "indeterminate_share_of_degraded": sum(r["min_cases_30"] == "INDETERMINATE" for r in deg) / max(1, len(deg)), "criterion": "detection when performed >= 0.95 and the upper 95% bound of the false rate <= 0.08",
                "criterion_met": tp / max(1, len(det)) >= 0.95 and (S.upper_bound(fp, len(ok)) or 1) <= 0.08}
    out["LG2-EXP-07"] = (P("LG2-EXP-07", [H("H1", "Once an unperformed score-degradation test is not counted as a passed one, no score-conditioned configuration is reported SECURED on the finding U"), H("H2", "Where the test was performed it detects the degradation (>= 0.95) with a false-rate bound <= 0.08"),
                                         H("H3", "The first version reported false assurance more often than the version with the rule")],
                           ["first_version", "min_cases_30"], "first_version", {"primary": ["false assurance on U", "detection when performed"], "secondary": ["share left INDETERMINATE", "dose of the minimum"]},
                           [A("L207a", "H1", "reported_SECURED_while_degraded", "descriptive"), A("L207b", "H2", "detection_when_performed", "descriptive"), A("L207c", "H3", "false_assurance", "paired-sign-flip")], {"min_cases": [0, 10, 30, 60], "configurations_per_world": 8}),
                          [("L207a", e07_h1), ("L207b", e07_h2),
                           ("L207c", lambda u: {**S.paired_sign_flip([float(sum(r["first_version"] == "SECURED" and r["truth_degraded"] for r in x["rows"]) - sum(r["min_cases_30"] == "SECURED" and r["truth_degraded"] for r in x["rows"])) for x in u], seed=14),
                                                "contrast": "degraded configurations reported SECURED per world: first version minus min_cases = 30"})])
    out["LG2-EXP-06"] = (P("LG2-EXP-06", [H("H1", "The five required findings of the inheritance test (A.6.1, 100_POINT_EDITION) agree with how each configuration was built, in every world")],
                           ["construction", "reader"], "construction", {"primary": ["agreement with construction"], "secondary": ["treatment-produced share of the score"]},
                           [A("L206a", "H1", "finding", "descriptive")], {"cases": ["no inheritance", "without safeguards", "partial safeguards", "effective safeguards", "lineage not produced"]}),
                          [("L206a", lambda u: {"method": "descriptive", "matches": {a: int(sum(x["arms"][a]["match"] for x in u)) for a in u[0]["arms"]}, "worlds": len(u), "endogenous_share_without_safeguards": float(np.mean([x["arms"]["without_safeguards"]["endogenous_share"] for x in u])),
                                                "endogenous_share_no_inheritance": float(np.mean([x["arms"]["no_inheritance"]["endogenous_share"] for x in u])), "criterion_met": all(x["arms"][a]["match"] for x in u for a in x["arms"])})])
    return out


def _job(a: tuple[str, int]) -> dict:
    return X.RUN[a[0]](a[1])


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 6
    check = "--check" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    reg_path = out / "protocol_registry.jsonl"
    if reg_path.exists() and not check and "--only" not in sys.argv:
        reg_path.unlink()
    reg = PR.ProtocolRegistry(reg_path)
    protos = {k: v for k, v in protocols().items() if only is None or k == only}
    if not check:
        for p, _ in protos.values():
            reg.register(p)
            reg.freeze(p["experiment_id"], 1, time.time())
        for p, _ in protos.values():
            reg.note_first_data(p["experiment_id"], 1, time.time() + 1.0)
    summary: dict[str, Any] = {}
    for key, (p, analyses) in protos.items():
        t0 = time.time()
        if check:
            u = X.RUN[key](p["seeds"][0])
            saved = json.loads((out / f"{key}_unit_first.json").read_text())
            summary[key] = {"replay_identical": digest_of(json.loads(json.dumps(u, default=str))) == saved["digest"]}
            continue
        with Pool(workers) as pool:
            units = pool.map(_job, [(key, s) for s in p["seeds"]])
        res: dict[str, Any] = {}
        for aid, fn in analyses:
            res[aid] = fn(units)
        fam = {a: r["p"] for a, r in res.items() if r.get("p") is not None and next(x for x in p["analyses"] if x["id"] == a).get("confirmatory")}
        for aid, h in S.holm(fam).items():
            res[aid]["p_holm"] = h["p_holm"]
        cls = "Implementation Property" if key in ("LG2-EXP-01", "LG2-EXP-06") else "Synthetic-world Result"
        for a in p["analyses"]:
            res[a["id"]]["registered_class"] = reg.analysis_class(p["experiment_id"], 1, a["id"])
            res[a["id"]]["evidence_class"] = cls
        doc = {"experiment_id": p["experiment_id"], "protocol_version": 1, "protocol_digest": PR.body_digest(p), "protocol": p, "units": len(units), "seeds": p["seeds"], "evidence_class": cls, "seconds": round(time.time() - t0, 1), "results": res,
               "catalogue": L.CATALOGUE_STATUS, "note": "results about a SYNTHETIC institution and this implementation; guarantees from the source text; operational definitions are the implementation's; not an observation of any institution, law or person"}
        (out / f"{key}.json").write_text(json.dumps(doc, indent=1, default=str))
        (out / f"{key}_unit_first.json").write_text(json.dumps({"seed": p["seeds"][0], "digest": digest_of(json.loads(json.dumps(units[0], default=str)))}))
        with gzip.open(out / f"{key}_units.json.gz", "wt") as f:
            json.dump(units, f, default=str, separators=(",", ":"))
        summary[key] = {a: {k: res[a].get(k) for k in ("mean_diff", "p", "p_holm", "supported", "criterion_met")} for a in res}
        print(key, round(time.time() - t0, 1), "s", json.dumps(summary[key], default=str)[:480], flush=True)
    print(json.dumps(summary) if check else f"registry verify: {reg.verify()}")


if __name__ == "__main__":
    main()
