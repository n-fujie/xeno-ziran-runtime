"""AI-law ledger experiments LAW-L1 .. LAW-L7 and the ablation LAW-A1. Pre-register (freeze), run, analyse, save. Run: PYTHONPATH=. python scripts/teoo_law_run.py OUT_DIR [--workers N] [--check] [--only ID]

New experiment ids; nothing earlier is touched or re-labelled, and the historical R5-R16 results of the manuscripts are not registered here as TEOO results (the manuscripts, the historical code and the world of Appendix O were not available:
the numbers of the manuscripts are not reproduced). Same discipline as before: protocols are frozen in a hash-chained registry before the first datum; confirmatory or exploratory is the registry's decision; every result is kept.
There was no pilot beyond reading the shape of one unit at seed 9001. LAW-L1, L2, L5, L6 and A1 are Implementation Properties; LAW-L3, L4 and L7 compare designs on synthetic scenarios (Synthetic-world Results)."""

from __future__ import annotations

import gzip
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import numpy as np

from xzr.teoo import lawexperiments as X
from xzr.teoo import legal as L
from xzr.teoo import protocol as PR
from xzr.teoo import stats as S
from xzr.teoo.provenance import digest_of

N = 30
SEEDS = {"LAW-L1": list(range(7001, 7001 + N)), "LAW-L2": list(range(7101, 7101 + N)), "LAW-L3": list(range(7201, 7201 + N)), "LAW-L4": [7301], "LAW-L5": list(range(7401, 7401 + N)), "LAW-L6": list(range(7501, 7501 + N)),
         "LAW-L7": list(range(7601, 7601 + N)), "LAW-A1": list(range(7701, 7701 + N))}
CLASS = {"LAW-L1": "Implementation Property", "LAW-L2": "Implementation Property", "LAW-L3": "Synthetic-world Result", "LAW-L4": "Synthetic-world Result", "LAW-L5": "Implementation Property", "LAW-L6": "Implementation Property",
         "LAW-L7": "Synthetic-world Result", "LAW-A1": "Implementation Property"}
H = lambda i, t: {"id": i, "statement": t}  # noqa: E731


def A(i: str, h: str, outcome: str, method: str, conf: bool = True, **kw: Any) -> dict:
    return {"id": i, "hypothesis": h, "outcome": outcome, "method": method, "confirmatory": conf, **kw}


def P(eid: str, hyps: list, conds: list, control: str, outcomes: dict, analyses: list, inst: dict) -> dict:
    seeds = SEEDS[eid]
    return PR.new_protocol(experiment_id=eid, hypotheses=hyps, targets=["receipts, evidence, proceedings, plans, measurements and closures of a synthetic ledger"], instrument_conditions=inst, control_condition=control, conditions=conds, seeds=seeds,
                           trials_per_condition=1, stopping_rule={"type": "fixed-n", "units": len(seeds), "no interim analysis": True}, outcomes=outcomes, analyses=analyses, multiplicity="holm", failure_conditions=[f"fewer than {len(seeds)} units"],
                           reproduction={"generator": "xzr.teoo.lawexperiments", "steps": ["run unit per seed", "analyse"], "world": "xzr.teoo.lawledger (SQLite, append-only) on xzr.teoo.lawworld (8 Booleans); this implementation's own world, not Appendix O"})


def tot(u: list[dict], f: Any) -> int:
    return int(sum(f(x) for x in u))


def sf(d: list[float], seed: int, label: str, sign: int = 1) -> dict:
    return {**S.paired_sign_flip(d, seed=seed), "contrast": label, "predicted_sign": sign}


def protocols() -> dict[str, tuple[dict, list]]:
    out: dict[str, tuple[dict, list]] = {}
    # ---------------------------------------------------------------- L1
    def l1_h1(u):
        return {"method": "descriptive", "receipt_first_erased_total": tot(u, lambda x: x["receipt_first_erased"]), "evidence_first_erased_total": tot(u, lambda x: x["evidence_first_erased"]), "worlds": len(u),
                "criterion": "0 valid or corrupt-container claims erased by the receipt-first ledger in every world", "criterion_met": tot(u, lambda x: x["receipt_first_erased"]) == 0}

    def l1_h3(u):
        ok = all(x["kept"][k] == x["expected"][k] for x in u for k in x["expected"])
        return {"method": "descriptive", "totals": {k: tot(u, lambda x, k=k: x["kept"][k]) for k in u[0]["expected"]}, "expected_totals": {k: tot(u, lambda x, k=k: x["expected"][k]) for k in u[0]["expected"]},
                "criterion": "every corrupt container kept as a receipt, every resend collapsed, every conflict and malformed input quarantined, every oversize input refused and not received, in every world", "criterion_met": ok}

    def l1_h4(u):
        r10 = {s: sorted({x["r10_states"][s] for x in u}) for s in ("ACTIVE", "QUEUED", "UNACKNOWLEDGED")}
        p65 = {s: sorted({x["persistent_65"][s] for x in u}) for s in ("ACTIVE", "QUEUED", "UNACKNOWLEDGED", "total")}
        return {"method": "descriptive", "r10_70_valid_submissions": r10, "persistent_65": p65, "criterion": "R10 (70 valid): 12 ACTIVE, 52 QUEUED, 6 UNACKNOWLEDGED; persistent (65): 12 ACTIVE, 53 QUEUED, 0 UNACKNOWLEDGED",
                "criterion_met": r10 == {"ACTIVE": [12], "QUEUED": [52], "UNACKNOWLEDGED": [6]} and p65 == {"ACTIVE": [12], "QUEUED": [53], "UNACKNOWLEDGED": [0], "total": [65]}}

    def l1_h5(u):
        ok = all(x["persisted"] == {"receipts": 24, "distinct_sequences": 24, "errors": 0, "active": 12, "queued": 12} and x["same_claim_other_case"] and x["after_invalid_first"] == "ACTIVE" for x in u)
        return {"method": "descriptive", "criterion": "4 connections x 6 concurrent submissions: 24 receipts, 24 distinct sequences, 0 errors, 12 ACTIVE and 12 QUEUED after reopening; the same claim id in another case is a separate receipt; a malformed submission first does not refuse the valid one after it",
                "criterion_met": ok}

    out["LAW-L1"] = (P("LAW-L1", [H("H1", "The receipt-first ledger erases no valid claim, including those whose evidence container is corrupt"), H("H2", "The evidence-first behaviour erases the claims whose container is corrupt"),
                                  H("H3", "Corrupt containers are kept, resends collapsed, conflicts and malformed input quarantined, oversize input refused and not counted as received"),
                                  H("H4", "The R10 in-memory condition leaves overflow UNACKNOWLEDGED; the persistent ledger keeps every valid submission (12 ACTIVE and the rest QUEUED)"),
                                  H("H5", "Concurrent submissions from four connections, a reopened database, the same claim id in another case and an invalid submission first do not lose or refuse valid submissions")],
                      ["receipt first", "evidence first", "R10 in memory"], "evidence first", {"primary": ["erased claims", "invariants I9-I11"], "secondary": ["receipt states", "durability"]},
                      [A("L101", "H1", "erased", "descriptive"), A("L102", "H2", "erased", "paired-sign-flip", paired=True), A("L103", "H3", "kept", "descriptive"), A("L104", "H4", "states", "descriptive"), A("L105", "H5", "persistence", "descriptive")],
                      {"stream": "80 submissions per world: valid, corrupt container, resend, conflict, malformed, oversize", "active_capacity": 12, "r10_local_limit": 64, "max_payload_bytes": 65536}),
                     [("L101", l1_h1), ("L102", lambda u: sf([float(x["evidence_first_erased"] - x["receipt_first_erased"]) for x in u], 11, "claims erased per world: evidence first minus receipt first")), ("L103", l1_h3), ("L104", l1_h4), ("L105", l1_h5)])
    # ---------------------------------------------------------------- L2
    out["LAW-L2"] = (P("LAW-L2", [H("H1", "An improper exception request for G1 leaves the evidence state SECURED, is recorded as applicability REJECTED with an open exception proceeding, and cannot be accepted"),
                                  H("H2", "The ledger keeps every proceeding opened for a case; the single-state variant keeps one"), H("H3", "Completing one proceeding does not complete or erase another")],
                      ["ledger", "single state"], "single state", {"primary": ["evidence state after the exception", "proceedings kept"], "secondary": ["independent completion"]},
                      [A("L201", "H1", "E, A, W", "descriptive"), A("L202", "H2", "proceedings kept", "paired-sign-flip", paired=True), A("L203", "H3", "independent completion", "descriptive")],
                      {"proceeding_kinds": 5, "opened_per_world": "3 to 5 in random order"}),
                     [("L201", lambda u: {"method": "descriptive", "worlds": len(u), "criterion": "E stays SECURED, A is REJECTED, the exception proceeding is open, the evidence is unchanged and the exception cannot be accepted, in every world",
                                          "criterion_met": all(x["r9"]["E_before"] == x["r9"]["E_after"] == "SECURED" and x["r9"]["A"] == "REJECTED" and x["r9"]["W"] == ["EXCEPTION_REVIEW_REQUIRED"] and x["r9"]["evidence_unchanged"] and not x["r9"]["exception_accepted"] for x in u)}),
                      ("L202", lambda u: {**sf([float(x["open_after"]["ledger"] - x["open_after"]["single_state"]) for x in u], 12, "proceedings kept per world: ledger minus single state"), "ledger_kept_all": all(x["open_after"]["ledger"] == x["opened"] for x in u)}),
                      ("L203", lambda u: {"method": "descriptive", "criterion": "completing one proceeding leaves the other open, in every world", "criterion_met": all(x["independent_completion"] for x in u)})])
    # ---------------------------------------------------------------- L3
    def rows(u):
        return [r for x in u for r in x["rows"]]

    def l3_h1(u):
        r = rows(u)
        by = {s: [q for q in r if q["scope"] == s] for s in LG_SCOPES}
        inv = {s: float(np.mean([q["ledger_invalid"] for q in by[s]])) if by[s] else None for s in by}
        return {"method": "descriptive", "invalidated_share_by_scope": inv, "n_by_scope": {s: len(by[s]) for s in by}, "plan_stale_all_scopes": all(all(x["plan_stale"].values()) for x in u),
                "criterion": "an earlier observation is invalidated in every ACCESS and UNKNOWN case and in no METADATA case, and unexecuted plans become stale for every scope", "criterion_met": inv["ACCESS"] == 1.0 and inv["UNKNOWN"] == 1.0 and inv["METADATA"] == 0.0 and all(all(x["plan_stale"].values()) for x in u)}

    def cost(u, who):
        missed = [sum(q["affects"] and not q[who] for q in x["rows"]) for x in u]
        needless = [sum((not q["affects"]) and q[who] for q in x["rows"]) for x in u]
        return missed, needless

    LG_SCOPES = ("ACCESS", "METADATA", "UNKNOWN")
    out["LAW-L3"] = (P("LAW-L3", [H("H1", "A revision of scope ACCESS or UNKNOWN invalidates an earlier observation, a revision of scope METADATA does not, and every scope makes unexecuted plans stale"),
                                  H("H2", "Scope-aware invalidation misses no invalidation that is needed (access truly affected) and has fewer needless reobservations than invalidating on every revision")],
                      ["scope aware", "always invalidate", "never invalidate"], "never invalidate", {"primary": ["missed invalidations", "needless invalidations"], "secondary": ["share invalidated by scope"]},
                      [A("L301", "H1", "invalidated", "descriptive"), A("L302", "H2", "needless invalidations", "paired-sign-flip", paired=True), A("L303", "H2", "missed invalidations", "paired-sign-flip", paired=True)],
                      {"scopes": list(LG_SCOPES), "ground_truth": "the scenario stipulates whether access is affected (the ledger does not find legal relevance by itself); UNKNOWN affects with probability 0.5"}),
                     [("L301", l3_h1),
                      ("L302", lambda u: sf([float(cost(u, "always_invalid")[1][i] - cost(u, "ledger_invalid")[1][i]) for i in range(len(u))], 13, "needless reobservations per world: always invalidate minus scope aware")),
                      ("L303", lambda u: {**sf([float(cost(u, "never_invalid")[0][i] - cost(u, "ledger_invalid")[0][i]) for i in range(len(u))], 14, "missed invalidations per world: never invalidate minus scope aware"), "scope_aware_missed_total": int(sum(cost(u, "ledger_invalid")[0])),
                                          "scope_aware_needless_total": int(sum(cost(u, "ledger_invalid")[1])), "always_needless_total": int(sum(cost(u, "always_invalid")[1])), "never_missed_total": int(sum(cost(u, "never_invalid")[0]))})])
    # ---------------------------------------------------------------- L4
    def l4(u):
        e = u[0]["enumeration"]
        pc = e["per_condition"]
        unex = ("BASE", "RECEIPT_ONLY", "DECLARATION_ONLY", "PLAN_ONLY")
        return {"method": "descriptive", "comparisons": e["comparisons"], "per_condition": pc, "boolean_model_agrees": e["boolean_model_agrees"], "boolean_sensor_agrees": e["boolean_sensor_agrees"], "ledger_realisation": u[0]["ledger_realisation"],
                "disagreements_without_execution": sum(pc[c]["disagreements"] for c in unex), "disagreements_with_execution": sum(pc[c]["disagreements"] for c in ("EXEC_GATE", "EXEC_LINKED")),
                "disagreements_not_explained_by_q": {c: pc[c]["disagreements"] - pc[c]["cause_identified_expanded"] for c in ("EXEC_GATE", "EXEC_LINKED")}, "historical_counts_reproduced": False}

    out["LAW-L4"] = (P("LAW-L4", [H("H1", "Model and synthetic sensor disagree only under executed conditions"), H("H2", "The EXPANDED mode attributes disagreements to the stipulated hidden condition q; ACCESS_ONLY attributes none; some disagreements are not explained by q even in EXPANDED"),
                                  H("H3", "An ordinary Boolean model with the same information agrees with the world on all 1,536 comparisons (no predictive advantage of the ledger)"), H("H4", "The ledger realises the world: its measurements equal the world's function on a sample of 96 (state, condition) pairs")],
                      ["world", "boolean comparator", "ledger"], "boolean comparator", {"primary": ["disagreements", "cause identified", "agreement of the Boolean comparator"], "secondary": ["ledger realisation"]},
                      [A("L401", "H1", "disagreements", "descriptive"), A("L402", "H2", "cause identified", "descriptive"), A("L403", "H3", "agreement", "descriptive"), A("L404", "H4", "ledger realisation", "descriptive")],
                      {"states": 256, "conditions": 6, "comparisons": 1536, "note": "this implementation's world; the manuscript's Appendix O counts are not reproduced"}),
                     [("L401", lambda u: {**l4(u), "criterion": "no disagreement without execution", "criterion_met": l4(u)["disagreements_without_execution"] == 0}),
                      ("L402", lambda u: {**{k: l4(u)[k] for k in ("per_condition", "disagreements_not_explained_by_q")}, "criterion": "ACCESS_ONLY identifies no cause; EXPANDED identifies some but not all disagreements",
                                          "criterion_met": all(p["cause_identified_access_only"] == 0 for p in l4(u)["per_condition"].values()) and any(v > 0 for v in l4(u)["disagreements_not_explained_by_q"].values())}),
                      ("L403", lambda u: {**{k: l4(u)[k] for k in ("comparisons", "boolean_model_agrees", "boolean_sensor_agrees")}, "criterion": "1,536 / 1,536 on both", "criterion_met": l4(u)["boolean_model_agrees"] == 1536 and l4(u)["boolean_sensor_agrees"] == 1536,
                                          "reading": "met: a Boolean model with the same information gives the same outputs; no predictive advantage of the ledger or of its vocabulary is shown"}),
                      ("L404", lambda u: {**l4(u)["ledger_realisation"], "criterion": "96 / 96", "criterion_met": l4(u)["ledger_realisation"]["agree"] == l4(u)["ledger_realisation"]["checked"]})])
    # ---------------------------------------------------------------- L5
    def l5(u):
        r = rows(u)
        conflict_closed = [q for q in r if q["any_closure"] and q["final_conflict"]]
        match_closed = [q for q in r if q["any_closure"] and not q["final_conflict"]]
        return {"method": "descriptive", "scenarios": len(r), "closed": sum(q["any_closure"] for q in r), "closed_with_conflict": len(conflict_closed), "closed_with_match": len(match_closed),
                "conflict_closures_flagged": sum(q["unresolved_flag"] and "CLOSED_ADMIN_CONFLICT" in q["closure_kinds"] for q in conflict_closed),
                "match_closures_kind": sum("CLOSED_ADMIN_MODEL_MATCH" in q["closure_kinds"] and not q["unresolved_flag"] for q in match_closed),
                "determinations_by_software": sum(q["legal_determination"] is not None for q in r), "restoration_verified": sum(q["restoration_verified"] for q in r), "positive_law_verified": sum(q["positive_law_verified"] for q in r),
                "conflicts_hidden_by_success_variant": sum(q["conflict_hidden_by_success"] for q in r), "refused_without_observation": all(x["refused_without_observation"] for x in u)}

    out["LAW-L5"] = (P("LAW-L5", [H("H1", "A closure after a disagreement is CLOSED_ADMIN_CONFLICT and keeps UNRESOLVED_CONFLICT; a closure after a match is CLOSED_ADMIN_MODEL_MATCH"),
                                  H("H2", "No closure creates a legal determination, a verified restoration or verified positive law"), H("H3", "A closure without a model observation newer than the evidence revision and a current sensor comparison is refused"),
                                  H("H4", "A single SUCCESS state hides conflicts that the ledger's closure keeps")],
                      ["separated closure", "single SUCCESS"], "single SUCCESS", {"primary": ["closure kinds", "conflicts hidden"], "secondary": ["refusals"]},
                      [A("L501", "H1", "closure kinds", "descriptive"), A("L502", "H2", "determinations", "descriptive"), A("L503", "H3", "refusals", "descriptive"), A("L504", "H4", "conflicts hidden", "paired-sign-flip", paired=True)],
                      {"scenarios_per_world": 24, "closure_requires": ["evidence revision", "newer model observation", "current sensor comparison", "officer record", "a recorded review"]}),
                     [("L501", lambda u: {**l5(u), "criterion": "every conflict closure carries UNRESOLVED_CONFLICT and every match closure CLOSED_ADMIN_MODEL_MATCH", "criterion_met": l5(u)["conflict_closures_flagged"] == l5(u)["closed_with_conflict"] and l5(u)["match_closures_kind"] == l5(u)["closed_with_match"]}),
                      ("L502", lambda u: {"method": "descriptive", "determinations_by_software": l5(u)["determinations_by_software"], "restoration_verified": l5(u)["restoration_verified"], "positive_law_verified": l5(u)["positive_law_verified"], "criterion": "0 and 0 and 0",
                                          "criterion_met": l5(u)["determinations_by_software"] == 0 and l5(u)["restoration_verified"] == 0 and l5(u)["positive_law_verified"] == 0}),
                      ("L503", lambda u: {"method": "descriptive", "criterion": "refused in every world", "criterion_met": l5(u)["refused_without_observation"]}),
                      ("L504", lambda u: {**sf([float(sum(q["conflict_hidden_by_success"] for q in x["rows"])) for x in u], 15, "conflicts hidden per world: single SUCCESS minus separated closure (which hides none)"), "hidden_total": l5(u)["conflicts_hidden_by_success_variant"]})])
    # ---------------------------------------------------------------- L6
    def l6(u):
        r = rows(u)
        pats = {tuple(q["present"]) for q in r}
        return {"method": "descriptive", "scenarios": len(r), "restoration_verified": sum(q["restoration_verified"] for q in r), "positive_law_verified": sum(q["positive_law_verified"] for q in r), "determination_by_software": sum(q["determination_by_software"] is not None for q in r),
                "access_changed_in_the_synthetic_world": sum(q["access_changed"] for q in r), "relief_misclassified_by_collapse": sum(q["relief_misclassified_by_collapse"] for q in r), "distinct_presence_patterns": len(pats),
                "stage_present_while_previous_absent": sum(any(q["present"][i] and not q["present"][i - 1] for i in range(1, 5)) for q in r)}

    out["LAW-L6"] = (P("LAW-L6", [H("H1", "Material restoration and positive law are never verified, and the software makes no legal determination, in any scenario"), H("H2", "Access changes in the synthetic world in some scenarios while restoration stays unverified: a change of access is not classified as relief"),
                                  H("H3", "The six records are independent: a later one can be present while an earlier one is absent"), H("H4", "Collapsing the chain into one SUCCESS would classify relief that has not been verified")],
                      ["six records", "collapsed SUCCESS"], "collapsed SUCCESS", {"primary": ["restoration verified", "relief misclassified"], "secondary": ["presence patterns"]},
                      [A("L601", "H1", "verified", "descriptive"), A("L602", "H2", "access changed", "descriptive"), A("L603", "H3", "independence", "descriptive"), A("L604", "H4", "misclassified", "paired-sign-flip", paired=True)], {"scenarios_per_world": 24}),
                     [("L601", lambda u: {**l6(u), "criterion": "restoration, positive law and software determinations: 0", "criterion_met": l6(u)["restoration_verified"] == 0 and l6(u)["positive_law_verified"] == 0 and l6(u)["determination_by_software"] == 0}),
                      ("L602", lambda u: {"method": "descriptive", "access_changed_in_the_synthetic_world": l6(u)["access_changed_in_the_synthetic_world"], "criterion": "access changed in at least one scenario while restoration is 0", "criterion_met": l6(u)["access_changed_in_the_synthetic_world"] > 0 and l6(u)["restoration_verified"] == 0}),
                      ("L603", lambda u: {"method": "descriptive", "distinct_presence_patterns": l6(u)["distinct_presence_patterns"], "stage_present_while_previous_absent": l6(u)["stage_present_while_previous_absent"], "criterion": "at least three presence patterns", "criterion_met": l6(u)["distinct_presence_patterns"] >= 3}),
                      ("L604", lambda u: {**sf([float(sum(q["relief_misclassified_by_collapse"] for q in x["rows"])) for x in u], 16, "unverified relief misclassified per world: collapsed SUCCESS minus six records (0)"), "total": l6(u)["relief_misclassified_by_collapse"]})])
    # ---------------------------------------------------------------- L7
    DES = ("A_boolean_state_machine", "B_event_sourcing", "C_causal_model", "D_fixed_policy", "E_adaptive_policy")
    Q = ("access", "mismatch", "cause_identified", "current_valid", "history_answerable", "open_proceedings", "closure")
    NO_STATE = ("C_causal_model", "D_fixed_policy", "E_adaptive_policy")

    def l7(u):
        r = rows(u)
        agree = {d: {q: {"agree": 0, "answered": 0, "cannot_answer": 0} for q in Q} for d in DES}
        for row in r:
            for d in DES:
                for q in Q:
                    v = row[d][q]
                    if d in NO_STATE and q in ("current_valid", "open_proceedings", "closure"):  # a design with no events and no proceedings cannot answer these; for the others None is an answer ("no closure")
                        agree[d][q]["cannot_answer"] += 1
                    else:
                        agree[d][q]["answered"] += 1
                        agree[d][q]["agree"] += int(v == row["F"][q])
        return {"method": "descriptive", "scenarios": len(r), "agreement_with_the_ledger": agree}

    def l7_b(u):
        a = l7(u)["agreement_with_the_ledger"]["B_event_sourcing"]
        return {"method": "descriptive", "scenarios": len(rows(u)), "B_vs_ledger": a, "criterion": "event sourcing with the same information agrees with the ledger on every query in every scenario (so the ledger shows no non-redundancy against it)",
                "criterion_met": all(v["agree"] == v["answered"] == len(rows(u)) for v in a.values())}

    out["LAW-L7"] = (P("LAW-L7", [H("H1", "Conventional event sourcing given the same information agrees with the ledger on all seven queries (the ledger is not shown to be non-redundant against it)"),
                                  H("H2", "A Boolean state machine without history cannot answer the history query and loses concurrent proceedings"), H("H3", "A fixed ACCESS_ONLY policy identifies fewer causes than the adaptive policy"),
                                  H("H4", "On access, disagreement and cause, the equal-information causal model with the adaptive policy agrees with the ledger: no predictive advantage of the ledger")],
                      ["A boolean state machine", "B event sourcing", "C causal model", "D fixed observation", "E adaptive observation", "F ledger"], "F ledger", {"primary": ["agreement with the ledger on seven queries"], "secondary": ["queries a design cannot answer"]},
                      [A("L701", "H1", "agreement of B", "descriptive"), A("L702", "H2", "A's answers", "descriptive"), A("L703", "H3", "causes identified", "paired-sign-flip", paired=True), A("L704", "H4", "agreement of E", "descriptive")],
                      {"queries": list(Q), "designs": list(DES), "information": "the same events, the same scope, the same world", "scenarios_per_world": "about 12 (the sequence receipt, plan, execute, observe, revision)"}),
                     [("L701", l7_b),
                      ("L702", lambda u: {"method": "descriptive", "A_vs_ledger": l7(u)["agreement_with_the_ledger"]["A_boolean_state_machine"], "criterion": "A cannot answer the history query in any scenario and disagrees with the ledger on open proceedings in some",
                                          "criterion_met": l7(u)["agreement_with_the_ledger"]["A_boolean_state_machine"]["history_answerable"]["agree"] == 0 and (l7(u)["agreement_with_the_ledger"]["A_boolean_state_machine"]["open_proceedings"]["agree"] < l7(u)["agreement_with_the_ledger"]["A_boolean_state_machine"]["open_proceedings"]["answered"])}),
                      ("L703", lambda u: {**sf([float(sum((q["E_adaptive_policy"]["cause_identified"] or 0) - (q["D_fixed_policy"]["cause_identified"] or 0) for q in x["rows"])) for x in u], 17, "causes identified per world: adaptive minus fixed policy")}),
                      ("L704", lambda u: {"method": "descriptive", "E_vs_ledger": {q: l7(u)["agreement_with_the_ledger"]["E_adaptive_policy"][q] for q in ("access", "mismatch", "cause_identified")}, "criterion": "agreement on access, disagreement and cause in every scenario",
                                          "criterion_met": all(v["agree"] == v["answered"] == len(rows(u)) for v in [l7(u)["agreement_with_the_ledger"]["E_adaptive_policy"][q] for q in ("access", "mismatch", "cause_identified")]),
                                          "reading": "met: no predictive advantage of the ledger or its vocabulary; what the ledger adds is the audit trail (validity, history, proceedings, closure), and an event-sourced store with the same fields has it too"})])
    # ---------------------------------------------------------------- A1
    def a1_total(u, arm, key):
        return int(sum(x["arms"][arm][key] for x in u))

    targets = {"no_versions": "executed_on_stale_evidence", "no_immutability": "history_unanswerable", "no_concurrent_proceedings": "proceedings_lost", "no_observation_revision": "stale_kept_current", "no_closure_separation": "conflict_hidden", "no_transaction_link": "unlinked_execution"}
    out["LAW-A1"] = (P("LAW-A1", [H("H1", "Each property taken away produces its own loss on the same scenarios: stale plans executed, history unanswerable, proceedings overwritten, stale observations kept current, conflicts hidden by a closure, executions without an approved plan"),
                                  H("H2", "Triggers make UPDATE on a measurement fail; without them the tampering succeeds")],
                      ["intact"] + list(targets), "intact", {"primary": ["the loss that belongs to each property"], "secondary": ["tampering"]},
                      [A(f"A10{i + 1}", "H1", t, "paired-sign-flip", paired=True) for i, t in enumerate(targets.values())] + [A("A107", "H2", "tampering", "descriptive")], {"ablations": targets, "scenarios_per_world": 24}),
                     [(f"A10{i + 1}", (lambda arm, key, sd: lambda u: {**sf([float(x["arms"][arm][key] - x["arms"]["intact"][key]) for x in u], sd, f"{key} per world: {arm} minus intact"), "total": a1_total(u, arm, key), "intact_total": a1_total(u, "intact", key)})(a, t, 20 + i))
                      for i, (a, t) in enumerate(targets.items())] + [("A107", lambda u: {"method": "descriptive", "tamper_succeeds": {a: a1_total(u, a, "tamper_succeeds") for a in ["intact"] + list(targets)}, "criterion": "intact: 0 tampering; the variant without immutability: all",
                                                                                          "criterion_met": a1_total(u, "intact", "tamper_succeeds") == 0 and a1_total(u, "no_immutability", "tamper_succeeds") == a1_total(u, "no_immutability", "scenarios")})])
    return out


def _job(a: tuple[str, int]) -> dict:
    return X.RUN[a[0]](a[1])


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4
    check = "--check" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    reg_path = out / "protocol_registry.jsonl"
    if reg_path.exists() and not check and only is None:
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
            summary[key] = {"replay_identical": digest_of(json.loads(json.dumps(_clean(u), default=str))) == saved["digest"]}
            continue
        with Pool(workers) as pool:
            units = pool.map(_job, [(key, s) for s in p["seeds"]])
        res: dict[str, Any] = {aid: fn(units) for aid, fn in analyses}
        fam = {a: r["p"] for a, r in res.items() if r.get("p") is not None and next(x for x in p["analyses"] if x["id"] == a).get("confirmatory")}
        for aid, h in S.holm(fam).items():
            res[aid]["p_holm"] = h["p_holm"]
            md, sg = res[aid].get("mean_diff"), res[aid].get("predicted_sign")
            res[aid]["supported"] = bool(h["p_holm"] < 0.05 and md is not None and sg is not None and (md > 0) == (sg > 0))
        for a in p["analyses"]:
            res[a["id"]]["registered_class"] = reg.analysis_class(p["experiment_id"], 1, a["id"])
            res[a["id"]]["evidence_class"] = CLASS[key]
        doc = {"experiment_id": p["experiment_id"], "protocol_version": 1, "protocol_digest": PR.body_digest(p), "protocol": p, "units": len(units), "seeds": p["seeds"], "evidence_class": CLASS[key], "seconds": round(time.time() - t0, 1), "results": res,
               "catalogue": L.CATALOGUE_STATUS, "note": "results about a SYNTHETIC ledger and this implementation's own world; the manuscripts R5-R16, the historical code and the world of Appendix O were not available and their numbers are not reproduced; "
                                                          "a closure, a measurement or a match here is not a legal judgment or a restoration; not an observation of any institution, law or person"}
        (out / f"{key}.json").write_text(json.dumps(doc, indent=1, default=str))
        (out / f"{key}_unit_first.json").write_text(json.dumps({"seed": p["seeds"][0], "digest": digest_of(json.loads(json.dumps(_clean(units[0]), default=str)))}))
        with gzip.open(out / f"{key}_units.json.gz", "wt") as f:
            json.dump(units, f, default=str, separators=(",", ":"))
        summary[key] = {a: {k: res[a].get(k) for k in ("mean_diff", "p", "p_holm", "supported", "criterion_met")} for a in res}
        print(key, round(time.time() - t0, 1), "s", json.dumps(summary[key], default=str)[:600], flush=True)
    print(json.dumps(summary) if check else f"registry verify: {reg.verify()}")


def _clean(u: Any) -> Any:
    return u


if __name__ == "__main__":
    main()
