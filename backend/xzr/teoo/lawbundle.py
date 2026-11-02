"""The data View I reads for the AI-law ledger: a deterministic demonstration of the ledger on a SYNTHETIC case, the finite world, the table of what was implemented for each of R5-R16, and the saved results of LAW-L1..L7, A1.

The demonstration is run in memory with fixed inputs, so the bundle is the same on every call. It shows what the ledger keeps (receipts, evidence versions and their scope, concurrent proceedings, plans, immutable measurements with their
status events, administrative closure) and what it never does (a legal determination, a verified restoration). The R5-R16 table says, for each, what exists in this repository and that the manuscripts and historical code were not available.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import lawexperiments as X
from . import lawledger as LG
from . import lawworld as W
from .r16experiments import STATED as X_STATED

EVIDENCE_DIR = Path(__file__).resolve().parents[3] / "docs" / "teoo_evidence" / "law"
R16_DIR = Path(__file__).resolve().parents[3] / "docs" / "teoo_evidence" / "r16"
ORIGINAL_NOTE = "implemented from the operational description in the request; the manuscript, the historical code and (for R14) the world of Appendix O were not available, so names of states and events are this implementation's and no historical number is reproduced"

R_TABLE: list[dict[str, Any]] = [
    {"r": "R5-R7", "what": "earlier arguments and experiments of the AI-law line (no description was given)", "implemented": "not separately implemented", "where": "-", "experiment": "-", "status": "NOT_AVAILABLE", "note": "kept as history; nothing is claimed"},
    {"r": "R8", "what": "G1 judged SECURED, then an improper exception request turned it INDETERMINATE", "implemented": "kept as the problem that R9 corrects; the overwriting variant is the comparator", "where": "lawledger.Ledger (features: concurrent) and LAW-L2", "experiment": "LAW-L2", "status": "SPECIFIED_AND_TESTED"},
    {"r": "R9", "what": "evidence E, applicability A and proceedings W kept apart; G1 and G2 cannot be nullified by a general exception; contradiction in evidence is not a person's objection", "implemented": "yes", "where": "Ledger._request_exception, effective_state, decide_exception", "experiment": "LAW-L2", "status": "IMPLEMENTED"},
    {"r": "R10", "what": "receipt first: the claim is recorded before its evidence is validated; invariants I9-I12; historical limits 12 ACTIVE / 64 QUEUED", "implemented": "yes (the 64 limit only as the historical in-memory condition r10_batch)", "where": "Ledger.receive, r10_batch", "experiment": "LAW-L1", "status": "IMPLEMENTED"},
    {"r": "R11", "what": "persistent SQLite intake: global receipt sequence, resend returns the same record, an id conflict is quarantined, an invalid submission does not block a later valid one, 65,536-byte contract", "implemented": "yes", "where": "Ledger.receive (SQLite, append-only)", "experiment": "LAW-L1, EXP-R16-02", "status": "IMPLEMENTED"},
    {"r": "R12", "what": "receipt, evidence finding, review, proposed measure, downstream observation and material restoration are separate records; restoration and positive law never verified", "implemented": "yes", "where": "Ledger.restoration_sequence", "experiment": "LAW-L6", "status": "IMPLEMENTED"},
    {"r": "R13", "what": "evidence registration, revision, review, plan, approval, execution and observation in one history; STALE_EVIDENCE; the executor is not the approver", "implemented": "yes", "where": "Ledger.plan / approve / execute", "experiment": "LAW-L3, LAW-A1", "status": "IMPLEMENTED"},
    {"r": "R14", "what": "model against a synthetic sensor; ACCESS_ONLY and EXPANDED; a hidden stipulated condition; 256 states x 6 conditions = 1,536 comparisons; an ordinary Boolean model matched them all", "implemented": "two worlds: this implementation's own, and an independent verification model built to the stated aggregates",
     "where": "lawworld (worlds own and r16_stated_aggregates)", "experiment": "LAW-L4, EXP-R16-04", "status": "STRUCTURE_AND_STATED_AGGREGATES",
     "note": "the stated counts (model 32/32/32/32/40/60, sensor 32/32/32/32/32/42, disagreements 8 and 18) hold in the verification model by construction; the manuscript's own world was not available, so this is not a reproduction"},
    {"r": "R15", "what": "measurements anchored to evidence event, execution and world revision; STALE_EVIDENCE and STALE_WORLD; a duplicate comparison is refused", "implemented": "yes", "where": "Ledger.observe, register_evidence, execute", "experiment": "LAW-L3, LAW-L4", "status": "IMPLEMENTED"},
    {"r": "R16", "what": "immutable measurement payload and separate status events; evidence scope ACCESS / METADATA / UNKNOWN; administrative closure kept apart from legal determination and restoration (CLOSED_ADMIN_CONFLICT, CLOSED_ADMIN_MODEL_MATCH, UNRESOLVED_CONFLICT, MODEL_MATCH_NOT_LEGALLY_VERIFIED)",
     "implemented": "yes", "where": "Ledger (triggers, measurement_status_events, close_review)", "experiment": "LAW-L3, LAW-L5, LAW-A1", "status": "IMPLEMENTED"},
]


def demo(seed: int = 3) -> dict[str, Any]:
    """One synthetic case through the whole path, plus a second case that receives 65 submissions."""
    lg = X.ledger()
    lg.create_case("case-1", "G3", W.pack(a=1, b=1, c=0, h=1))
    steps: list[dict[str, Any]] = []

    def log(what: str, out: Any) -> None:
        steps.append({"step": len(steps) + 1, "what": what, "result": out})

    ok = X.claim(1)
    r = lg.receive("case-1", {**ok, "scope": "ACCESS"})
    log("a valid claim with an evidence container is received", {"state": r["state"], "receipt": r["receipt_seq"]})
    r = lg.receive("case-1", {**ok, "scope": "ACCESS"})
    log("the same submission is sent again", {"duplicate": r["duplicate"], "same receipt": r["receipt_seq"]})
    r = lg.receive("case-1", X.claim(2) | {"evidence": {"tier": 9}})
    log("a claim whose evidence container is corrupt: the claim is kept, the evidence is not usable", {"state": r["state"], "evidence_valid": r["evidence"]["valid"], "proceedings": [p["kind"] for p in r["proceedings"]]})
    r = lg.receive("case-1", {**ok, "note": "another body under the same claim id"})
    log("another body under an used claim id", {"state": r["state"], "reason": r["reason"]})
    r = lg.receive("case-1", b"{broken")
    log("malformed input", {"state": r["state"]})
    r = lg.receive("case-1", b"x" * (LG.MAX_PAYLOAD_BYTES + 1))
    log("input above 65,536 bytes", {"received": r["received"], "state": r["state"]})
    lg.create_case("case-g1", "G1", 7)
    lg.receive("case-g1", X.claim(10, "G1"))
    r = lg.receive("case-g1", {**X.claim(11, "G1"), "exception": {"reason": "an improper request that G1 does not apply"}})
    e = lg.effective_state("case-g1", "G1")
    log("G1 is SECURED; an improper exception for G1 is requested (R8's problem)", {"E": e["E"], "A": e["A"], "W": e["W"], "effective": e["effective"], "accepted": lg.decide_exception("case-g1", "G1", True, "reviewer1")["ok"]})
    lg.declare("case-1", "executor1", "a correction is declared")
    pl = lg.plan("case-1", "EXEC_LINKED", "planner1")["plan_id"]
    log("a plan is made on evidence version 1", {"plan": pl, "status": lg.plan_status(pl)})
    ap = lg.approve(pl, "approver1")
    log("approval is refused while a required review is open", {"ok": ap["ok"], "missing": ap.get("missing")})
    for p in lg.proceedings("case-1", open_only=True):
        lg.complete_review(p["id"], "reviewer1", "reviewed")
    lg.register_evidence("case-1", "G3", X.EV_OK, scope="METADATA", source="a corrected address")
    log("a METADATA revision arrives: the unexecuted plan is made stale at once", {"plan_status": lg.plan_status(pl)})
    pl = lg.plan("case-1", "EXEC_LINKED", "planner1")["plan_id"]
    log("a new plan on the current evidence", {"plan": pl, "approved": lg.approve(pl, "approver1")["ok"], "executed_by_the_approver": lg.execute(pl, "approver1")["ok"], "executed_by_another": lg.execute(pl, "executor1")["ok"]})
    m1 = lg.observe("case-1", "ACCESS_ONLY", "model-obs-1")
    log("model and synthetic sensor are compared (ACCESS_ONLY)", {"model": m1["model"], "sensor": m1["sensor"], "mismatch": m1["mismatch"], "cause_identified": m1["cause_identified"], "proceedings": [p["kind"] for p in m1["proceedings"]]})
    log("the same comparison again is refused", {"ok": lg.observe("case-1", "ACCESS_ONLY", "model-obs-1")["ok"]})
    m2 = lg.observe("case-1", "EXPANDED", "model-obs-2")
    log("the EXPANDED mode adds the stipulated hidden condition", {"q": m2["q"], "cause_identified": m2["cause_identified"]})
    ev = lg.register_evidence("case-1", "G3", X.EV_OK, scope="ACCESS", source="access-relevant new evidence")
    log("an ACCESS revision arrives: the current observation is invalidated, not edited", {"invalidated": ev["invalidated_measurements"]})
    pr = lg.proceedings("case-1", open_only=True)
    log("closure is refused until the observation is repeated", {"ok": lg.close_review("case-1", pr[0]["id"], "officer1")["ok"]})
    m3 = lg.observe("case-1", "EXPANDED", "model-obs-3")
    for p in lg.proceedings("case-1", open_only=True):
        if p["state"] == "OPEN":
            lg.complete_review(p["id"], "reviewer1", "reviewed")
    cl = lg.close_review("case-1", pr[0]["id"], "officer1")
    log("administrative closure", {"ok": cl["ok"], "kind": cl.get("kind"), "flag": cl.get("flag"), "legal_determination": cl.get("legal_determination"), "material_restoration_verified": cl.get("material_restoration_verified")})
    try:
        lg.db.execute("UPDATE measurements SET mismatch = 0")
        tamper = "succeeded"
    except Exception as ex:  # noqa: BLE001
        tamper = f"refused ({ex})"
    log("an attempt to change a stored measurement", {"result": tamper})
    big = X.ledger()
    for i in range(65):
        big.receive("case-65", X.claim(i))
    snap = lg.snapshot("case-1")
    return {"steps": steps, "case": {k: snap[k] for k in ("case_id", "guarantee", "world", "receipts", "evidence", "proceedings", "measurements", "closures", "restoration")}, "case_g1": lg.snapshot("case-g1")["effective"],
            "counts_case_1": lg.counts("case-1"), "counts_65": big.counts("case-65"), "events_kept": {t: lg.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("receipts", "evidence_events", "proceedings", "plan_events", "measurements", "measurement_status_events", "closures")},
            "seed": seed, "m3_current": m3["measurement_id"]}


def saved_results() -> list[dict[str, Any]]:
    out = []
    for k, base in [(k, EVIDENCE_DIR) for k in ("LAW-L1", "LAW-L2", "LAW-L3", "LAW-L4", "LAW-L5", "LAW-L6", "LAW-L7", "LAW-A1")] + [(k, R16_DIR) for k in ("EXP-R16-02", "EXP-R16-04", "EXP-R16-08", "EXP-R16-09")]:
        f = base / f"{k}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        out.append({"id": k, "class": d["evidence_class"], "units": d["units"], "analyses": {a: {"hypothesis": next(x["hypothesis"] for x in d["protocol"]["analyses"] if x["id"] == a), "criterion_met": r.get("criterion_met"), "supported": r.get("supported"), "mean_diff": r.get("mean_diff"),
                                                                                              "p_holm": r.get("p_holm"), "confirmatory": next(x["confirmatory"] for x in d["protocol"]["analyses"] if x["id"] == a)} for a, r in d["results"].items()}})
    return out


REGISTRIES: list[dict[str, str]] = [
    {"name": "MHEG Twelve-Duty Registry", "kept_in": "xzr.teoo.mheg.DUTIES", "theory_requires": "for each duty: input, evidence, responsible subject, failure and indeterminate conditions", "software_verifies": "that the mapped findings are evaluated and projected (never summed)",
     "authority": "whether a duty is met in a legal order is not decided here"},
    {"name": "Fifteen Guarantees Registry", "kept_in": "xzr.teoo.legal (GUARANTEES, audit, itemised provisions)", "theory_requires": "an independent finding per guarantee; G12A/B and G15A-D separately; no total", "software_verifies": "the states from the evidence of a synthetic institution; hard failures; INDETERMINATE is not compliance",
     "authority": "legal legitimacy is not decided here"},
    {"name": "Fifteen Governance Principles Registry", "kept_in": "xzr.teoo.mheg.GOVERNANCE_PRINCIPLES", "theory_requires": "the R16 principles and the August version kept apart, with their sources", "software_verifies": "titles as supplied, the functional comparison with guarantees and duties, a projection of findings",
     "authority": "the content of the sources is not verified (R16 and the book were not available)"},
    {"name": "Legal Source Registry", "kept_in": "xzr.teoo.legal.RegisterEntry (the Translation Register)", "theory_requires": "an identified authority, purpose, proxy, threshold and disclosed loss for each variable", "software_verifies": "that each variable names an authority and discloses its proxy, threshold and loss",
     "authority": "the validity of the named authority in a real legal order"},
    {"name": "Receipt Registry", "kept_in": "lawledger: receipts, receipt_status_events, refusals", "theory_requires": "a claim is recorded before its evidence is validated and is not erased", "software_verifies": "idempotent resend, quarantine, per-case isolation, persistence, the input contract; I9-I11",
     "authority": "a local row is not a receipt by a public body (I12)"},
    {"name": "Evidence Registry", "kept_in": "lawledger: evidence_events, applicability_events", "theory_requires": "evidence, applicability and proceedings are separate; revisions have a scope", "software_verifies": "versions, container validity, E/A/W independence, scope effects",
     "authority": "whether a revision is legally relevant is stipulated, not judged"},
    {"name": "Proceedings Registry", "kept_in": "lawledger: proceedings, proceeding_events, reviews", "theory_requires": "several independent proceedings at once", "software_verifies": "concurrent proceedings, their states, reviews by an authorised actor of the TEST roles", "authority": "no review here has legal effect"},
    {"name": "Intervention Registry", "kept_in": "lawledger: plans, plan_events, executions, declarations, roles", "theory_requires": "plans bound to evidence versions; approval, execution and observation separate", "software_verifies": "STALE_EVIDENCE, approval conditions, a different executor",
     "authority": "approval and execution here are TEST roles, not an authority"},
    {"name": "Immutable Measurement Registry", "kept_in": "lawledger: measurements", "theory_requires": "a measurement is never changed after it is stored", "software_verifies": "append-only triggers; duplicate comparisons refused", "authority": "the synthetic sensor is an experimenter's stipulation, not an observation of a real world"},
    {"name": "Status Event Registry", "kept_in": "lawledger: measurement_status_events", "theory_requires": "validity changes by new events, never by editing", "software_verifies": "CURRENT, STALE_EVIDENCE, STALE_WORLD, HISTORICAL as appended events and the status at a past tick", "authority": "the names are this implementation's"},
    {"name": "Administrative Closure Registry", "kept_in": "lawledger: closures, determinations", "theory_requires": "administrative closure, evidential resolution, legal determination and restoration are four things", "software_verifies": "the order of conditions for a closure; the flags UNRESOLVED_CONFLICT and MODEL_MATCH_NOT_LEGALLY_VERIFIED",
     "authority": "a determination reported from outside is an input and verifies nothing"},
    {"name": "Material Restoration Records", "kept_in": "lawledger: restoration_claims and restoration_sequence", "theory_requires": "restoration is a separate record that nothing earlier implies", "software_verifies": "that claims are recorded and that no claim is verified here", "authority": "real restoration is outside this environment"},
]
LINEAGE: list[dict[str, str]] = [
    {"date": "2026-07", "stage": "MHEG: twelve operational duties", "kept_as": "mheg.DUTIES (functional summaries; the initial source was not available)"},
    {"date": "2026", "stage": "The Minimum Guarantees of Human Legal Subjecthood V3.0 / 100_POINT_EDITION: fifteen guarantees", "kept_as": "legal.GUARANTEES (titles verified; wording held privately)"},
    {"date": "2026-08", "stage": "The End of Human Philosophy 12.3, Recursive Double Audit version: a different fifteenth principle (audit of the auditor)", "kept_as": "a separate historical version in mheg.GOVERNANCE_PRINCIPLES"},
    {"date": "2026-11-01", "stage": "AI law R16, section 7: fifteen governance principles P1-P15", "kept_as": "mheg.GOVERNANCE_PRINCIPLES.items (titles as supplied; R16 not available)"},
    {"date": "2026-11-01", "stage": "R10-R16: receipt first, persistent intake, receipt-to-outcome, transaction-linked intervention, model-sensor comparison, evidence-anchored observation, immutable evidence-scoped observation", "kept_as": "lawledger, lawworld, LAW-L1..L7, LAW-A1, EXP-R16-02/04/08/09"},
]


def law_bundle(seed: int = 3) -> dict[str, Any]:
    en = W.enumerate_world()
    st = W.enumerate_world("r16_stated_aggregates")
    res = saved_results()
    unmet = [{"experiment": e["id"], "analysis": a, "hypothesis": v["hypothesis"]} for e in res for a, v in e["analyses"].items() if v["criterion_met"] is False or v["supported"] is False]
    return {"synthetic": True, "note": ORIGINAL_NOTE, "demo": demo(seed), "world": {k: en[k] for k in ("states", "conditions", "comparisons", "per_condition", "boolean_model_agrees", "boolean_sensor_agrees", "historical_counts_reproduced", "note")},
            "world_stated": {k: st[k] for k in ("world", "states", "conditions", "comparisons", "per_condition", "boolean_model_agrees", "boolean_sensor_agrees", "historical_counts_reproduced", "note")}, "stated_aggregates": X_STATED,
            "registries": REGISTRIES, "lineage": LINEAGE, "r_table": R_TABLE,
            "results": res, "negative_and_unmet": unmet + [
                {"experiment": "LAW-L4", "analysis": "L403", "hypothesis": "an ordinary Boolean model with the same information agrees on 1,536 / 1,536: no predictive advantage of the ledger or its vocabulary (kept as a negative result)"},
                {"experiment": "LAW-L7", "analysis": "L701", "hypothesis": "event sourcing with the same information agrees with the ledger on every query: non-redundancy of the ledger against it is not shown"},
                {"experiment": "EXP-R16-04", "analysis": "R403", "hypothesis": "in the world built to the stated aggregates too, an ordinary Boolean model agrees on 1,536 / 1,536: no predictive advantage"},
                {"experiment": "EXP-R16-08", "analysis": "R801", "hypothesis": "on both worlds, event sourcing agrees with the ledger on every query; the evidence-scoped revision model agrees on all but the history query: what the ledger adds is history and the audit trail, which event sourcing has too"}],
            "invariants": {"I9": "a corrupt evidence container does not remove the receipt of a valid submission", "I10": "a submission beyond a limit is stated as not acknowledged, never as if it did not exist", "I11": "several independent proceedings are not overwritten by one state string",
                           "I12": "a receipt, a hash, a closure or a model match in a synthetic environment creates no judicial or administrative authority"},
            "limits": "a SYNTHETIC ledger and a world of this implementation's own: nothing here is a legal judgment, a restoration or an observation of any institution; no predictive advantage of operational-shape realism is shown", "seed": seed}
