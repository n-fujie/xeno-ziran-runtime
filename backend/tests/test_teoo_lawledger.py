"""The AI-law ledger (xzr.teoo.lawledger, lawworld, lawbundle): receipt first, persistence, evidence/applicability/proceedings kept apart, plans linked to evidence versions, immutable measurements with status events, administrative
closure kept apart from legal determination and restoration; and the saved results of LAW-L1..L7, A1."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from xzr.teoo import lawbundle as LB
from xzr.teoo import lawexperiments as X
from xzr.teoo import lawledger as LG
from xzr.teoo import lawworld as W
from xzr.teoo import protocol as PR
from xzr.teoo.provenance import digest_of

EV = Path(__file__).resolve().parents[2] / "docs" / "teoo_evidence" / "law"
OK = X.EV_OK


def L(features=None, path=":memory:"):
    return X.ledger(features, path)


# ------------------------------------------------------------------------------------------------ receipt first, persistence
def test_a_valid_submission_is_received_and_a_resend_returns_the_same_record():
    lg = L()
    a = lg.receive("c", X.claim(1))
    b = lg.receive("c", X.claim(1))
    assert a["state"] == "ACTIVE" and b["duplicate"] is True and a["receipt_seq"] == b["receipt_seq"] and len(lg.receipts("c")) == 1


def test_a_corrupt_evidence_container_does_not_remove_the_receipt_I9():
    lg = L()
    r = lg.receive("c", {**X.claim(1), "evidence": {"tier": 9, "exists": "maybe"}})
    assert r["received"] and r["state"] == "ACTIVE" and r["evidence"]["valid"] is False and r["evidence"]["e_state"] == "INDETERMINATE"
    assert [p["kind"] for p in r["proceedings"]] == ["EVIDENCE_REVIEW"] and lg.evidence_state("c", "G3") is None, "no valid evidence, but the claim exists"


def test_same_id_with_another_body_is_quarantined_and_an_invalid_first_does_not_block_a_valid_one():
    lg = L()
    lg.receive("c", X.claim(1))
    r = lg.receive("c", {**X.claim(1), "note": "different"})
    assert r["state"] == "QUARANTINED" and "conflict" in r["reason"] and r["conflict_with"] == 1
    assert lg.receive("c", {**X.claim(1), "note": "different"})["duplicate"] is True, "the conflicting body is itself deduplicated"
    lg2 = L()
    assert lg2.receive("d", b"{broken")["state"] == "QUARANTINED" and lg2.receive("d", b"{broken")["duplicate"] is True
    assert lg2.receive("d", X.claim(7))["state"] == "ACTIVE", "a bad submission first refuses nothing after it"
    assert lg2.receive("d", {"claim_id": "k", "guarantee": "G99"})["state"] == "QUARANTINED"


def test_input_above_the_contract_is_refused_and_is_not_a_receipt():
    lg = L()
    r = lg.receive("c", b"x" * (LG.MAX_PAYLOAD_BYTES + 1))
    assert r["received"] is False and r["state"] == "NOT_RECEIVED" and "durability" in r["reason"] and lg.receipts("c") == [] and lg.counts("c")["refused"] == 1
    assert lg.receive("c", {**X.claim(1), "pad": "x" * 60_000})["received"] is True, "just inside the contract"


def test_the_same_claim_id_in_another_case_is_a_separate_receipt_with_its_own_sequence():
    lg = L()
    a, b = lg.receive("A", X.claim(1)), lg.receive("B", X.claim(1))
    assert a["receipt_seq"] != b["receipt_seq"] and a["state"] == b["state"] == "ACTIVE"


def test_active_capacity_is_twelve_and_the_rest_are_queued_without_loss_and_a_review_promotes_the_oldest():
    lg = L()
    for i in range(65):
        lg.receive("c", X.claim(i))
    c = lg.counts("c")
    assert (c["ACTIVE"], c["QUEUED"]) == (12, 53)
    first = lg.receipts("c")[0]["receipt_seq"]
    out = lg.mark_reviewed(first, "reviewer1")
    c = lg.counts("c")
    assert out["ok"] and out["promoted"] is not None and (c["ACTIVE"], c["QUEUED"], c["REVIEWED"]) == (12, 52, 1)
    assert lg.mark_reviewed(first, "reviewer1")["ok"] is False


def test_the_r10_historical_condition_leaves_overflow_unacknowledged_and_says_so():
    out = LG.r10_batch([X.claim(i) for i in range(70)] + [b"junk"])  # type: ignore[list-item]
    st = [o["state"] for o in out]
    assert (st.count("ACTIVE"), st.count("QUEUED"), st.count("UNACKNOWLEDGED"), st.count("QUARANTINED")) == (12, 52, 6, 1)


def test_receipts_persist_across_reopening_and_four_connections_can_submit_at_once(tmp_path):
    path = str(tmp_path / "intake.sqlite")
    conns = [L(path=path) for _ in range(4)]
    errs = []

    def work(k):
        try:
            for i in range(6):
                conns[k].receive("cc", X.claim(k * 100 + i))
        except Exception as e:  # noqa: BLE001
            errs.append(e)

    ts = [threading.Thread(target=work, args=(k,)) for k in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    [c.close() for c in conns]
    again = L(path=path)
    rc = again.receipts("cc")
    assert not errs and len(rc) == 24 and len({r["receipt_seq"] for r in rc}) == 24 and again.counts("cc")["ACTIVE"] == 12 and again.counts("cc")["QUEUED"] == 12


def test_stored_rows_cannot_be_changed_or_deleted_and_the_variant_without_triggers_can():
    lg = L()
    lg.receive("c", X.claim(1))
    for sql in ("UPDATE receipts SET state = 'x'", "UPDATE receipts SET reason = 'x'", "DELETE FROM receipts", "DELETE FROM evidence_events"):
        with pytest.raises(Exception, match="append-only|no such column"):
            lg.db.execute(sql)
    free = L({"immutable": False})
    free.receive("c", X.claim(1))
    free.db.execute("UPDATE receipts SET reason = 'x'")


# ------------------------------------------------------------------------------------------------ R9: evidence, applicability, proceedings
def test_an_improper_exception_for_g1_keeps_the_evidence_records_applicability_and_cannot_be_accepted():
    lg = L()
    lg.create_case("c", "G1", 7)
    lg.receive("c", X.claim(1, "G1"))
    before = lg.effective_state("c", "G1")
    r = lg.receive("c", {**X.claim(2, "G1"), "exception": {"reason": "improper"}})
    after = lg.effective_state("c", "G1")
    assert before["E"] == after["E"] == "SECURED" and after["A"] == "REJECTED" and after["W"] == ["EXCEPTION_REVIEW_REQUIRED"] and after["effective"] == "SECURED" and r["exception"]["evidence_unchanged"]["e_state"] == "SECURED"
    assert lg.decide_exception("c", "G1", True, "reviewer1")["ok"] is False and lg.decide_exception("c", "G2", True, "reviewer1")["ok"] is False


def test_an_exception_for_another_guarantee_is_requested_then_decided_and_the_evidence_is_never_rewritten():
    lg = L()
    lg.create_case("c", "G13", 7)
    lg.receive("c", X.claim(1, "G13"))
    lg.receive("c", {**X.claim(2, "G13"), "exception": {"reason": "no irreversible harm is possible"}})
    e = lg.effective_state("c", "G13")
    assert e["E"] == "SECURED" and e["A"] == "EXCEPTION_REQUESTED" and e["effective"] == "SECURED"
    assert lg.decide_exception("c", "G13", True, "nobody")["ok"] is False
    assert lg.decide_exception("c", "G13", True, "reviewer1")["ok"] is True
    e = lg.effective_state("c", "G13")
    assert e["A"] == "ACCEPTED" and e["effective"] == "INAPPLICABLE" and e["E"] == "SECURED", "applicability changed the state read, not the evidence"


def test_proceedings_are_kept_side_by_side_and_completing_one_does_not_touch_another():
    lg = L()
    lg.create_case("c", "G3", 7)
    ids = [lg.open_proceeding("c", "G3", k)["id"] for k in ("EVIDENCE_REVIEW", "HUMAN_REVIEW", "REASSESS_OUTCOME")]
    lg.complete_review(ids[0], "reviewer1", "done")
    assert [p["state"] for p in lg.proceedings("c")] == ["REVIEWED", "OPEN", "OPEN"] and lg.complete_review(ids[1], "nobody", "x")["ok"] is False
    one = L({"concurrent": False})
    one.create_case("c", "G3", 7)
    for k in ("EVIDENCE_REVIEW", "HUMAN_REVIEW", "REASSESS_OUTCOME"):
        one.open_proceeding("c", "G3", k)
    assert len(one.proceedings("c", open_only=True)) == 1


# ------------------------------------------------------------------------------------------------ R13: plans, approval, execution
def _case(features=None):
    lg = L(features)
    lg.create_case("c", "G3", W.pack(a=1, b=1, c=0, h=1))
    lg.receive("c", X.claim(1))
    return lg


def test_approval_needs_roles_current_evidence_and_completed_reviews_and_execution_a_different_actor():
    lg = _case()
    p = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    assert lg.plan("c", "EXEC_LINKED", "nobody")["ok"] is False and lg.approve(p, "nobody")["ok"] is False
    pr = lg.open_proceeding("c", "G3", "HUMAN_REVIEW")
    assert "required review not completed" in " ".join(lg.approve(p, "approver1")["missing"])
    lg.complete_review(pr["id"], "reviewer1", "ok")
    assert lg.approve(p, "approver1")["ok"] is True
    lg.set_role("approver1", "executor")
    assert "executor is the approver" in " ".join(lg.execute(p, "approver1")["missing"])
    assert lg.execute(p, "executor1")["ok"] is True and lg.plan_status(p) == "EXECUTED" and lg.execute(p, "executor1")["ok"] is False


def test_a_revision_of_any_scope_makes_an_unexecuted_plan_stale_and_an_executed_one_is_kept():
    for scope in LG.SCOPES:
        lg = _case()
        p = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
        lg.approve(p, "approver1")
        e = lg.register_evidence("c", "G3", OK, scope=scope)
        assert lg.plan_status(p) == "STALE_EVIDENCE" and e["stale_plans"] == [p]
        assert lg.approve(p, "approver1")["ok"] is False and lg.execute(p, "executor1")["ok"] is False
    lg = _case()
    p = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    lg.approve(p, "approver1")
    lg.execute(p, "executor1")
    lg.register_evidence("c", "G3", OK, scope="ACCESS")
    assert lg.plan_status(p) == "EXECUTED", "an executed event is never rewritten"


def test_indeterminate_evidence_blocks_approval_and_an_invalid_container_is_not_a_revision():
    lg = L()
    lg.create_case("c", "G3", 7)
    lg.receive("c", {**X.claim(1), "evidence": {"tier": 3, "exists": True, "usable": True, "score_conditioned": False}})  # tier 3 alone cannot establish compliance
    p = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    assert "INDETERMINATE" in " ".join(lg.approve(p, "approver1")["missing"])
    lg2 = _case()
    m = lg2.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    lg2.approve(m, "approver1")
    lg2.register_evidence("c", "G3", {"tier": 9}, scope="ACCESS")
    assert lg2.plan_status(m) == "APPROVED" and lg2.evidence_state("c", "G3")["version"] == 1, "a container that is not evidence revises nothing"


def test_without_transaction_link_the_gate_path_executes_what_the_linked_one_refuses():
    lg = _case({"transaction_linked": False})
    p = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    assert lg.execute(p, "executor1")["ok"] is True and lg.world("c")["condition"] == "EXEC_GATE"
    assert _case().execute(_case().plan("c", "EXEC_LINKED", "planner1")["plan_id"], "executor1")["ok"] is False


# ------------------------------------------------------------------------------------------------ R14-R16: measurements and their status events
def _executed():
    lg = _case()
    p = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    lg.approve(p, "approver1")
    lg.execute(p, "executor1")
    return lg


def test_a_measurement_is_never_edited_and_the_same_comparison_is_refused_twice():
    lg = _executed()
    m = lg.observe("c", "ACCESS_ONLY", "mo1")
    assert m["ok"] and m["mismatch"] and m["cause_identified"] is False and [p["kind"] for p in m["proceedings"]] == ["EVIDENCE_REVIEW", "REASSESS_OUTCOME"]
    assert lg.observe("c", "ACCESS_ONLY", "mo1")["ok"] is False and lg.observe("c", "EXPANDED", "mo1")["ok"] is True
    with pytest.raises(Exception, match="append-only"):
        lg.db.execute("UPDATE measurements SET mismatch = 0")
    with pytest.raises(Exception, match="append-only"):
        lg.db.execute("UPDATE measurement_status_events SET status = 'CURRENT'")
    assert lg.observe("c", "EXPANDED", "mo9")["q"] is True


def test_the_scope_of_a_revision_decides_what_happens_to_an_observation():
    out = {}
    for scope in LG.SCOPES:
        lg = _executed()
        mid = lg.observe("c", "ACCESS_ONLY", "mo1")["measurement_id"]
        t = lg.now()
        e = lg.register_evidence("c", "G3", OK, scope=scope)
        m = next(x for x in lg.measurements("c") if x["id"] == mid)
        out[scope] = (m["status"], e["invalidated_measurements"], lg.status_at(mid, t), len(m["status_history"]))
    assert out["ACCESS"][0] == out["UNKNOWN"][0] == "STALE_EVIDENCE" and out["METADATA"][0] == "CURRENT" and out["METADATA"][1] == []
    assert all(v[2] == "CURRENT" for v in out.values()), "the earlier status is still answerable: events are kept"
    assert out["ACCESS"][3] == 2 and out["METADATA"][3] == 1


def test_a_changed_world_makes_the_observation_stale_and_a_newer_one_makes_the_old_historical():
    lg = _case()
    p1 = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    lg.approve(p1, "approver1")
    m0 = lg.observe("c", "ACCESS_ONLY", "before")["measurement_id"]
    lg.execute(p1, "executor1")
    assert next(x for x in lg.measurements("c") if x["id"] == m0)["status"] == "STALE_WORLD"
    m1 = lg.observe("c", "ACCESS_ONLY", "after")["measurement_id"]
    m2 = lg.observe("c", "EXPANDED", "after-x")["measurement_id"]
    st = {x["id"]: x["status"] for x in lg.measurements("c")}
    assert st[m1] == "HISTORICAL" and st[m2] == "CURRENT"


def test_without_the_observation_revision_a_stale_observation_stays_current():
    lg = L({"observation_revision": False})
    lg.create_case("c", "G3", 7)
    lg.receive("c", X.claim(1))
    mid = lg.observe("c", "ACCESS_ONLY", "x")["measurement_id"]
    lg.register_evidence("c", "G3", OK, scope="ACCESS")
    assert next(m for m in lg.measurements("c") if m["id"] == mid)["status"] == "CURRENT"


# ------------------------------------------------------------------------------------------------ administrative closure
def test_closure_needs_a_current_observation_after_the_revision_a_review_and_an_officer_and_keeps_its_flag():
    lg = _executed()
    lg.observe("c", "ACCESS_ONLY", "mo1")
    pr = lg.proceedings("c", True)
    assert "no review has been recorded" in " ".join(lg.close_review("c", pr[0]["id"], "officer1")["missing"]) and lg.close_review("c", pr[0]["id"], "nobody")["ok"] is False
    for p in pr:
        lg.complete_review(p["id"], "reviewer1", "ok")
    lg.register_evidence("c", "G3", OK, scope="ACCESS")
    assert "no current sensor comparison" in " ".join(lg.close_review("c", pr[0]["id"], "officer1")["missing"])
    lg.observe("c", "EXPANDED", "mo2")
    r = lg.close_review("c", pr[0]["id"], "officer1")
    assert r["ok"] and r["kind"] == "CLOSED_ADMIN_CONFLICT" and r["flag"] == "UNRESOLVED_CONFLICT" and r["legal_determination"] is None and r["material_restoration_verified"] is False and r["positive_law_verified"] is False and r["evidential_resolution"] is False
    assert lg.close_review("c", pr[0]["id"], "officer1")["ok"] is False, "a closed proceeding is not closed twice"


def test_a_match_closes_as_a_model_match_that_is_not_legally_verified():
    lg = L()
    lg.create_case("c", "G3", W.pack(a=1, b=1, c=1))
    lg.receive("c", X.claim(1))
    pr = lg.open_proceeding("c", "G3", "HUMAN_REVIEW")
    lg.complete_review(pr["id"], "reviewer1", "ok")
    m = lg.observe("c", "ACCESS_ONLY", "mo")
    assert m["mismatch"] is False
    r = lg.close_review("c", pr["id"], "officer1")
    assert r["kind"] == "CLOSED_ADMIN_MODEL_MATCH" and r["flag"] == "MODEL_MATCH_NOT_LEGALLY_VERIFIED"


def test_a_closure_without_separation_hides_the_conflict_and_a_determination_record_verifies_nothing():
    lg = _executed()
    lg2 = L({"closure_separation": False})
    lg2.create_case("c", "G3", W.pack(a=1, b=1, c=0, h=1))
    lg2.receive("c", X.claim(1))
    p = lg2.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    lg2.approve(p, "approver1")
    lg2.execute(p, "executor1")
    lg2.observe("c", "ACCESS_ONLY", "m")
    pr = lg2.proceedings("c", True)
    for x in pr:
        lg2.complete_review(x["id"], "reviewer1", "ok")
    assert lg2.close_review("c", pr[0]["id"], "officer1")["kind"] == "CLOSED_SUCCESS"
    out = lg.record_determination("c", None, "a court (reported)", "a decision reported to this ledger")
    assert out["positive_law_verified"] is False and out["material_restoration_verified"] is False
    seq = lg.restoration_sequence("c")
    assert seq["legal_determination_by_this_software"] is None and seq["determinations_recorded"] == 1 and seq["material_restoration_verified"] is False and seq["stages"][-1] == {"stage": "material_restoration", "present": False, "n": 0}


# ------------------------------------------------------------------------------------------------ the finite world
def test_the_world_has_256_states_6_conditions_and_disagrees_only_under_execution_and_does_not_reproduce_the_manuscript():
    e = W.enumerate_world()
    pc = e["per_condition"]
    assert e["states"] == 256 and e["comparisons"] == 1536 and all(pc[c]["disagreements"] == 0 for c in ("BASE", "RECEIPT_ONLY", "DECLARATION_ONLY", "PLAN_ONLY"))
    assert pc["EXEC_GATE"]["disagreements"] > 0 and pc["EXEC_LINKED"]["disagreements"] > 0 and e["historical_counts_reproduced"] is False
    assert e["boolean_model_agrees"] == e["boolean_sensor_agrees"] == 1536, "an ordinary Boolean model with the same information gives the same outputs"
    assert all(p["cause_identified_access_only"] == 0 for p in pc.values()) and pc["EXEC_GATE"]["cause_identified_expanded"] < pc["EXEC_GATE"]["disagreements"], "q does not explain every disagreement"
    assert (pc["EXEC_GATE"]["model_access"], pc["EXEC_LINKED"]["sensor_access"]) != (40, 42), "not calibrated to the manuscript"


def test_the_ledger_realises_the_world():
    for cond in W.CONDITIONS:
        lg = L()
        lg.create_case("c", "G3", W.pack(a=1, b=1, c=0, h=1))
        X._drive(lg, cond)  # noqa: SLF001
        w = lg.world("c")
        o = lg.observe("c", "EXPANDED", "m")
        d = W.observe(w["bits"], w["condition"], "EXPANDED")
        assert w["condition"] == cond and (o["model"], o["sensor"]) == (d["model"], d["sensor"])


# ------------------------------------------------------------------------------------------------ bundle and saved results
def test_the_bundle_is_deterministic_and_says_what_it_is_not():
    a, b = LB.law_bundle(3), LB.law_bundle(3)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["synthetic"] and a["world"]["historical_counts_reproduced"] is False and set(a["invariants"]) == {"I9", "I10", "I11", "I12"}
    assert [r["r"] for r in a["r_table"]] == ["R5-R7", "R8", "R9", "R10", "R11", "R12", "R13", "R14", "R15", "R16"]
    assert {r["r"]: r["status"] for r in a["r_table"]}["R14"] == "STRUCTURE_ONLY" and {r["r"]: r["status"] for r in a["r_table"]}["R5-R7"] == "NOT_AVAILABLE"
    assert a["demo"]["case"]["restoration"]["material_restoration_verified"] is False and a["demo"]["counts_65"]["ACTIVE"] == 12 and a["demo"]["counts_65"]["QUEUED"] == 53
    assert "no predictive advantage" in a["limits"]


@pytest.mark.skipif(not (EV / "LAW-A1.json").exists(), reason="results not saved")
def test_the_saved_results_replay_were_frozen_first_and_keep_their_negative_and_unmet_outcomes():
    for key in X.RUN:
        saved = json.loads((EV / f"{key}_unit_first.json").read_text())
        u = X.RUN[key](saved["seed"])
        assert digest_of(json.loads(json.dumps(u, default=str))) == saved["digest"], key
    assert PR.ProtocolRegistry(EV / "protocol_registry.jsonl").verify() == []
    d = {k: json.loads((EV / f"{k}.json").read_text())["results"] for k in X.RUN}
    assert d["LAW-L1"]["L101"]["receipt_first_erased_total"] == 0 and d["LAW-L1"]["L102"]["supported"] is True and d["LAW-L4"]["L403"]["boolean_model_agrees"] == 1536
    assert d["LAW-L6"]["L603"]["criterion_met"] is False, "the unmet pre-registered criterion is kept"
    assert d["LAW-L7"]["L701"]["criterion_met"] is True and d["LAW-L7"]["L702"]["criterion_met"] is True and d["LAW-L7"]["L704"]["criterion_met"] is True
    assert all(d["LAW-A1"][f"A10{i}"]["supported"] for i in range(1, 7)) and d["LAW-A1"]["A107"]["criterion_met"] is True
