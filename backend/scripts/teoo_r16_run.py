"""EXP-R16-02, 04, 08 and 09: concurrent SQLite cases, the independent verification model built from the stated R16 aggregates, comparators (with the evidence-scoped revision model) on both worlds, and the functional correspondence of the
twelve duties, fifteen guarantees and fifteen R16 governance principles. Pre-register (freeze), run, analyse, save. Run: PYTHONPATH=. python scripts/teoo_r16_run.py OUT_DIR [--workers N] [--check] [--only ID]

New experiment ids. The rest of the R16 list is covered by the LAW series (see xzr.teoo.r16experiments) and is not repeated. The stated-aggregates world is an independent verification model, not the manuscript's world: its match with the stated
numbers holds by construction and is not a reproduction. No pilot beyond reading one unit at seed 9101. EXP-R16-02, 04 and 09 are Implementation Properties (04: with a world built to the stated aggregates), EXP-R16-08 compares designs on synthetic scenarios."""

from __future__ import annotations

import gzip
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path
from typing import Any

from xzr.teoo import legal as L
from xzr.teoo import protocol as PR
from xzr.teoo import r16experiments as X
from xzr.teoo import stats as S
from xzr.teoo.provenance import digest_of

SEEDS = {"EXP-R16-02": list(range(8001, 8031)), "EXP-R16-04": [8101], "EXP-R16-08": list(range(8201, 8231)), "EXP-R16-09": [8301]}
CLASS = {"EXP-R16-02": "Implementation Property", "EXP-R16-04": "Implementation Property", "EXP-R16-08": "Synthetic-world Result", "EXP-R16-09": "Implementation Property"}
H = lambda i, t: {"id": i, "statement": t}  # noqa: E731


def A(i: str, h: str, outcome: str, method: str, conf: bool = True, **kw: Any) -> dict:
    return {"id": i, "hypothesis": h, "outcome": outcome, "method": method, "confirmatory": conf, **kw}


def P(eid: str, hyps: list, conds: list, control: str, outcomes: dict, analyses: list, inst: dict) -> dict:
    seeds = SEEDS[eid]
    return PR.new_protocol(experiment_id=eid, hypotheses=hyps, targets=["a synthetic ledger, its worlds and the registries of duties, guarantees and governance principles"], instrument_conditions=inst, control_condition=control, conditions=conds, seeds=seeds,
                           trials_per_condition=1, stopping_rule={"type": "fixed-n", "units": len(seeds), "no interim analysis": True}, outcomes=outcomes, analyses=analyses, multiplicity="holm", failure_conditions=[f"fewer than {len(seeds)} units"],
                           reproduction={"generator": "xzr.teoo.r16experiments", "steps": ["run unit per seed", "analyse"], "world": "xzr.teoo.lawledger on xzr.teoo.lawworld (own world and a world built to the stated R16 aggregates); registries in xzr.teoo.mheg"})


def sf(d: list[float], seed: int, label: str, sign: int = 1) -> dict:
    return {**S.paired_sign_flip(d, seed=seed), "contrast": label, "predicted_sign": sign}


DES = ("A_boolean_state_machine", "B_event_sourcing", "R_evidence_scoped_revision", "C_causal_model", "D_fixed_policy", "E_adaptive_policy")
Q = ("access", "mismatch", "cause_identified", "current_valid", "history_answerable", "open_proceedings", "closure")
NO_STATE = ("C_causal_model", "D_fixed_policy", "E_adaptive_policy")


def agreement(u: list[dict], world: str) -> dict:
    rows = [r for x in u for r in x["worlds"][world]]
    out: dict[str, Any] = {"scenarios": len(rows)}
    for d in DES:
        out[d] = {}
        for q in Q:
            if d in NO_STATE and q in ("current_valid", "open_proceedings", "closure"):
                out[d][q] = {"agree": 0, "answered": 0, "cannot_answer": len(rows)}
            else:
                out[d][q] = {"agree": sum(r[d][q] == r["F"][q] for r in rows), "answered": len(rows), "cannot_answer": 0}
    return out


def protocols() -> dict[str, tuple[dict, list]]:
    out: dict[str, tuple[dict, list]] = {}
    out["EXP-R16-02"] = (P("EXP-R16-02", [H("H1", "Four cases processed at once on one SQLite file (four connections) end in the same state as the same four cases processed one after another"), H("H2", "Sending every submission again changes nothing after the database is reopened"),
                                          H("H3", "No evidence or measurement of one case refers to another case"), H("H4", "Every closure keeps its flag (UNRESOLVED_CONFLICT or MODEL_MATCH_NOT_LEGALLY_VERIFIED)")],
                           ["concurrent four connections", "sequential"], "sequential", {"primary": ["cases equal to sequential", "changes by a resend"], "secondary": ["contamination", "errors"]},
                           [A("R201", "H1", "state equality", "descriptive"), A("R202", "H2", "resend", "descriptive"), A("R203", "H3", "contamination", "descriptive"), A("R204", "H4", "closure flags", "descriptive")],
                           {"cases_per_world": 4, "lifecycle": "receipt, resend, conflict, malformed, corrupt container, review, plan, approval, execution, observation, revision, observation, closure"}),
                          [("R201", lambda u: {"method": "descriptive", "worlds": len(u), "cases_equal": sum(x["cases_equal_to_sequential"] for x in u), "cases": sum(x["cases"] for x in u), "errors": sum(x["errors"] for x in u),
                                               "criterion": "every case equal to its sequential counterpart and 0 errors", "criterion_met": all(x["cases_equal_to_sequential"] == x["cases"] and x["errors"] == 0 for x in u)}),
                           ("R202", lambda u: {"method": "descriptive", "criterion": "a resend adds no row in any world", "criterion_met": all(all(v == 0 for v in x["resend_changes"].values()) for x in u)}),
                           ("R203", lambda u: {"method": "descriptive", "contamination": sum(x["cross_case_contamination"] for x in u), "criterion": "0", "criterion_met": sum(x["cross_case_contamination"] for x in u) == 0}),
                           ("R204", lambda u: {"method": "descriptive", "closures": sum(x["closures"] for x in u), "criterion": "every closure keeps a flag", "criterion_met": all(x["closures_keep_a_flag"] for x in u)})])
    # ---- 04
    def r04(u):
        x = u[0]
        return {"method": "descriptive", "model_access": x["model_access"], "sensor_access": x["sensor_access"], "disagreements": x["disagreements"], "stated_model_access": X.STATED["model_access"], "stated_sensor_access": X.STATED["sensor_access"],
                "stated_disagreements": X.STATED["disagreements"], "nested": x["nested"], "sensor_access_contained_in_model": x["sensor_access_contained_in_model"], "boolean_model_agrees": x["enumeration"]["boolean_model_agrees"],
                "boolean_sensor_agrees": x["enumeration"]["boolean_sensor_agrees"], "comparisons": x["enumeration"]["comparisons"], "ledger_realisation": x["ledger_realisation"], "unexplained_by_q": x["unexplained_by_q"]}

    out["EXP-R16-04"] = (P("EXP-R16-04", [H("H1", "A world of eight Booleans exists whose enumeration gives the stated aggregates (model access 32, 32, 32, 32, 40, 60; sensor access 32, 32, 32, 32, 32, 42; disagreements 8 and 18; none without execution); this world is constructed to the aggregates and is not the original"),
                                           H("H2", "In that world the sensor's access is contained in the model's, so the disagreements are the model's extra access"), H("H3", "An ordinary Boolean model with the same information agrees on all 1,536 comparisons"),
                                           H("H4", "The ledger realises the world on a 96-pair sample"), H("H5", "The EXPANDED mode leaves some disagreements unexplained by the stipulated hidden condition")],
                           ["stated-aggregates world", "boolean comparator", "ledger"], "boolean comparator", {"primary": ["aggregate match", "agreement of the Boolean comparator"], "secondary": ["ledger realisation", "unexplained disagreements"]},
                           [A("R401", "H1", "aggregates", "descriptive"), A("R402", "H2", "containment", "descriptive"), A("R403", "H3", "agreement", "descriptive"), A("R404", "H4", "realisation", "descriptive"), A("R405", "H5", "unexplained", "descriptive")],
                           {"states": 256, "conditions": 6, "comparisons": 1536, "note": "an independent verification model built to the stated aggregates; not a reproduction of the manuscript"}),
                          [("R401", lambda u: {**r04(u), "criterion": "the enumeration equals the stated aggregates (by construction)", "criterion_met": r04(u)["model_access"] == X.STATED["model_access"] and r04(u)["sensor_access"] == X.STATED["sensor_access"]
                                               and r04(u)["disagreements"]["EXEC_GATE"] == 8 and r04(u)["disagreements"]["EXEC_LINKED"] == 18 and all(r04(u)["disagreements"][c] == 0 for c in ("BASE", "RECEIPT_ONLY", "DECLARATION_ONLY", "PLAN_ONLY")),
                                               "reading": "the match is by construction: it shows that the stated aggregates are jointly realisable by a nested eight-Boolean world, not that this is the manuscript's world"}),
                           ("R402", lambda u: {"method": "descriptive", "criterion": "sensor access contained in model access", "criterion_met": bool(u[0]["sensor_access_contained_in_model"])}),
                           ("R403", lambda u: {"method": "descriptive", "boolean_model_agrees": r04(u)["boolean_model_agrees"], "boolean_sensor_agrees": r04(u)["boolean_sensor_agrees"], "criterion": "1,536 / 1,536 on both", "criterion_met": r04(u)["boolean_model_agrees"] == 1536 and r04(u)["boolean_sensor_agrees"] == 1536,
                                               "reading": "met: no predictive advantage of the ledger or its vocabulary over an ordinary Boolean model with the same information"}),
                           ("R404", lambda u: {"method": "descriptive", **r04(u)["ledger_realisation"], "criterion": "96 / 96", "criterion_met": r04(u)["ledger_realisation"]["agree"] == r04(u)["ledger_realisation"]["checked"]}),
                           ("R405", lambda u: {"method": "descriptive", "unexplained_by_q": r04(u)["unexplained_by_q"], "criterion": "some disagreements stay unexplained", "criterion_met": any(v > 0 for v in r04(u)["unexplained_by_q"].values())})])
    # ---- 08
    out["EXP-R16-08"] = (P("EXP-R16-08", [H("H1", "On both worlds, conventional event sourcing with the same information agrees with the ledger on all seven queries"), H("H2", "An evidence-scoped revision model without an event log agrees with the ledger on every query except the history query"),
                                          H("H3", "A Boolean state machine cannot answer the history query and loses concurrent proceedings"), H("H4", "A fixed ACCESS_ONLY policy identifies fewer causes than the adaptive policy, in each world")],
                          ["Boolean state machine", "event sourcing", "evidence-scoped revision model", "causal model with fixed or adaptive observation", "ledger"], "ledger", {"primary": ["agreement with the ledger on seven queries"], "secondary": ["queries a design cannot answer"]},
                          [A("R801", "H1", "agreement of event sourcing", "descriptive"), A("R802", "H2", "agreement of R", "descriptive"), A("R803", "H3", "A's answers", "descriptive"), A("R804", "H4", "causes identified, own world", "paired-sign-flip", paired=True),
                           A("R805", "H4", "causes identified, stated world", "paired-sign-flip", paired=True)], {"worlds": ["own", "r16_stated_aggregates"], "queries": list(Q), "designs": list(DES), "information": "the same events, scope, policy and world"}),
                         [("R801", lambda u: {"method": "descriptive", **{w: {"B_vs_ledger": agreement(u, w)["B_event_sourcing"]} for w in ("own", "r16_stated_aggregates")}, "criterion": "agreement on every query in every scenario of both worlds",
                                              "criterion_met": all(v["agree"] == v["answered"] for w in ("own", "r16_stated_aggregates") for v in agreement(u, w)["B_event_sourcing"].values())}),
                          ("R802", lambda u: {"method": "descriptive", **{w: {"R_vs_ledger": agreement(u, w)["R_evidence_scoped_revision"]} for w in ("own", "r16_stated_aggregates")}, "criterion": "agreement on every query except history_answerable, where it cannot keep history",
                                              "criterion_met": all(v["agree"] == v["answered"] for w in ("own", "r16_stated_aggregates") for q, v in agreement(u, w)["R_evidence_scoped_revision"].items() if q != "history_answerable") and all(agreement(u, w)["R_evidence_scoped_revision"]["history_answerable"]["agree"] == 0 for w in ("own", "r16_stated_aggregates"))}),
                          ("R803", lambda u: {"method": "descriptive", **{w: {"A_vs_ledger": agreement(u, w)["A_boolean_state_machine"]} for w in ("own", "r16_stated_aggregates")}, "criterion": "no history answer and fewer agreeing proceedings counts than scenarios",
                                              "criterion_met": all(agreement(u, w)["A_boolean_state_machine"]["history_answerable"]["agree"] == 0 and agreement(u, w)["A_boolean_state_machine"]["open_proceedings"]["agree"] < agreement(u, w)["A_boolean_state_machine"]["open_proceedings"]["answered"] for w in ("own", "r16_stated_aggregates"))}),
                          ("R804", lambda u: sf([float(sum((r["E_adaptive_policy"]["cause_identified"] or 0) - (r["D_fixed_policy"]["cause_identified"] or 0) for r in x["worlds"]["own"])) for x in u], 31, "causes identified per world: adaptive minus fixed, own world")),
                          ("R805", lambda u: sf([float(sum((r["E_adaptive_policy"]["cause_identified"] or 0) - (r["D_fixed_policy"]["cause_identified"] or 0) for r in x["worlds"]["r16_stated_aggregates"])) for x in u], 32, "causes identified per world: adaptive minus fixed, stated-aggregates world"))])
    # ---- 09
    out["EXP-R16-09"] = (P("EXP-R16-09", [H("H1", "For each of the fifteen R16 principles, the guarantee that matches it best by protected function is its ordinal counterpart, and no other guarantee is close"), H("H2", "The functional match is exact for twelve principles and differs for P5, P10 and P15"),
                                           H("H3", "Titles alone do not establish correspondence: some coincide and most differ in wording"), H("H4", "P1 corresponds to no duty (G1 is named by no duty) and every duty is covered by at least one principle"),
                                           H("H5", "The August Recursive Double Audit version is kept as a separate historical version")],
                          ["by protected function", "by number", "by title"], "by number", {"primary": ["best functional match", "differences"], "secondary": ["titles", "duty coverage"]},
                          [A("R901", "H1", "best match", "descriptive"), A("R902", "H2", "differences", "descriptive"), A("R903", "H3", "titles", "descriptive"), A("R904", "H4", "duties", "descriptive"), A("R905", "H5", "versions", "descriptive")],
                          {"profiles": "protected functions read from the supplied descriptions (this implementation's analytic reading, not verified against the sources); near pairs count 0.5", "threshold": 0.5}),
                         [("R901", lambda u: {"method": "descriptive", "ordinal_counterpart_is_best_match": u[0]["ordinal_counterpart_is_best_match"], "close_guarantees": u[0]["close_guarantees_per_principle"], "criterion": "the ordinal counterpart is the best and the only close guarantee for all fifteen",
                                              "criterion_met": all(u[0]["ordinal_counterpart_is_best_match"].values()) and u[0]["close_guarantees_are_the_ordinal_only"], "reading": "met on these profiles; the profiles are an analytic reading, so this shows what the supplied descriptions say, not what the sources say"}),
                          ("R902", lambda u: {"method": "descriptive", "functionally_identical": u[0]["functionally_identical"], "differs": u[0]["differs"], "criterion": "exact for twelve; P5, P10, P15 differ", "criterion_met": len(u[0]["functionally_identical"]) == 12 and sorted(u[0]["differs"]) == ["P10", "P15", "P5"]}),
                          ("R903", lambda u: {"method": "descriptive", "identical_titles": u[0]["titles_identical_to_the_ordinal_guarantee"], "n_identical": len(u[0]["titles_identical_to_the_ordinal_guarantee"]), "n_different": 15 - len(u[0]["titles_identical_to_the_ordinal_guarantee"]),
                                              "criterion": "some titles coincide and most differ", "criterion_met": 0 < len(u[0]["titles_identical_to_the_ordinal_guarantee"]) < 8}),
                          ("R904", lambda u: {"method": "descriptive", "principles_without_a_duty": u[0]["principles_without_a_duty"], "duties_covered_by_principles": u[0]["duties_covered_by_principles"], "criterion": "only P1 has no duty; every duty has a principle",
                                              "criterion_met": u[0]["principles_without_a_duty"] == ["P1"] and all(v for v in u[0]["duties_covered_by_principles"].values())}),
                          ("R905", lambda u: {"method": "descriptive", "versions": u[0]["august_version_kept"], "criterion": "both versions are kept", "criterion_met": u[0]["august_version_kept"] == ["r16_section_7", "recursive_double_audit_august"]})])
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
               "catalogue": L.CATALOGUE_STATUS, "note": "results about a SYNTHETIC ledger; the stated-aggregates world is an independent verification model built to the stated numbers, not the manuscript's world, and its match is by construction; the principles' profiles are an analytic reading; "
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
