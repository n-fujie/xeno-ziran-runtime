"""R16 verification: twenty-five direct and adversarial checks of the ledger (written by this implementation from the operational description; they are not the manuscript's twenty-five), the world built to the stated aggregates,
and the saved results of EXP-R16-02, 04, 08 and 09."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xzr.teoo import lawexperiments as X
from xzr.teoo import lawledger as LG
from xzr.teoo import lawworld as W
from xzr.teoo import protocol as PR
from xzr.teoo import r16experiments as R
from xzr.teoo.provenance import digest_of

EV = Path(__file__).resolve().parents[2] / "docs" / "teoo_evidence" / "r16"
OK = X.EV_OK


def L(features=None, world="own"):
    return X.ledger(features, world=world)


def _case(features=None):
    lg = L(features)
    lg.create_case("c", "G3", W.pack(a=1, b=1, c=0, h=1))
    lg.receive("c", X.claim(1))
    return lg


def _run(lg):
    p = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    lg.approve(p, "approver1")
    lg.execute(p, "executor1")
    return p


def c01():
    lg = L()
    assert lg.receive("c", b"{" + b" " * (LG.MAX_PAYLOAD_BYTES - 1))["state"] == "QUARANTINED", "exactly at the contract it is received (and quarantined as malformed)"
    assert lg.receive("c", b"x" * (LG.MAX_PAYLOAD_BYTES + 1))["received"] is False


def c02():
    assert L().receive("c", {"claim_id": "", "guarantee": "G3"})["state"] == "QUARANTINED"


def c03():
    assert L().receive("c", {"claim_id": "k", "guarantee": "G99"})["state"] == "QUARANTINED"


def c04():
    assert LG.evidence_container_valid({"tier": True, "exists": True, "usable": True, "score_conditioned": False})[0] is False


def c05():
    assert LG.evidence_container_valid({"tier": 1, "exists": "yes", "usable": True, "score_conditioned": False})[0] is False and LG.evidence_container_valid(None)[0] is False


def c06():
    lg = L()
    lg.receive("c", X.claim(1))
    a = lg.receive("c", {**X.claim(1), "x": 1})
    b = lg.receive("c", {**X.claim(1), "x": 1})
    assert a["state"] == "QUARANTINED" and b["duplicate"] is True and a["receipt_seq"] == b["receipt_seq"]


def c07():
    lg = L()
    lg.receive("c", X.claim(1))
    lg.receive("c", {**X.claim(1), "x": 1})
    assert [r["state"] for r in lg.receipts("c")] == ["ACTIVE", "QUARANTINED"]


def c08():
    lg = L()
    assert lg.receive("A", X.claim(1))["state"] == lg.receive("B", X.claim(1))["state"] == "ACTIVE"


def c09():
    with pytest.raises(Exception, match="append-only"):
        _case().db.execute("UPDATE receipts SET reason = 'x'")


def c10():
    lg = _case()
    _run(lg)
    lg.observe("c", "ACCESS_ONLY", "m")
    with pytest.raises(Exception, match="append-only"):
        lg.db.execute("DELETE FROM measurement_status_events")


def c11():
    with pytest.raises(KeyError):
        L().observe("nope", "ACCESS_ONLY")


def c12():
    assert _case().plan("c", "NOT_A_MEASURE", "planner1")["ok"] is False


def c13():
    lg = _case()
    p = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    assert lg.approve(p, "approver1")["ok"] and lg.approve(p, "approver1")["ok"] is False


def c14():
    lg = _case()
    p = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    assert lg.execute(p, "executor1")["ok"] is False and lg.world("c")["condition"] == "PLAN_ONLY"


def c15():
    lg = _case()
    lg.set_role("approver1", "executor")
    p = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    lg.approve(p, "approver1")
    assert lg.execute(p, "approver1")["ok"] is False and lg.execute(p, "executor1")["ok"] is True


def c16():
    lg = _case()
    p = lg.plan("c", "EXEC_LINKED", "planner1")["plan_id"]
    lg.approve(p, "approver1")
    lg.register_evidence("c", "G3", OK, scope="METADATA")
    assert lg.execute(p, "executor1")["ok"] is False and lg.plan_status(p) == "STALE_EVIDENCE"


def c17():
    got = {}
    for scope in LG.SCOPES:
        lg = _case()
        _run(lg)
        mid = lg.observe("c", "ACCESS_ONLY", "m")["measurement_id"]
        lg.register_evidence("c", "G3", OK, scope=scope)
        got[scope] = next(m["status"] for m in lg.measurements("c") if m["id"] == mid)
    assert got == {"ACCESS": "STALE_EVIDENCE", "METADATA": "CURRENT", "UNKNOWN": "STALE_EVIDENCE"}


def c18():
    lg = _case()
    _run(lg)
    assert lg.observe("c", "ACCESS_ONLY", "m")["ok"] and lg.observe("c", "ACCESS_ONLY", "m")["ok"] is False and lg.observe("c", "EXPANDED", "m")["ok"]


def c19():
    lg = _case()
    _run(lg)
    m = lg.observe("c", "ACCESS_ONLY", "m")
    for p in m["proceedings"]:
        lg.complete_review(p["id"], "reviewer1", "ok")
    assert lg.close_review("c", m["proceedings"][0]["id"], "executor1")["ok"] is False


def c20():
    lg = _case()
    _run(lg)
    m = lg.observe("c", "ACCESS_ONLY", "m")
    for p in m["proceedings"]:
        lg.complete_review(p["id"], "reviewer1", "ok")
    lg.register_evidence("c", "G3", OK, scope="METADATA")
    lg.observe("c", "EXPANDED", "m2")
    pid = m["proceedings"][0]["id"]
    assert lg.close_review("c", pid, "officer1")["ok"] and lg.close_review("c", pid, "officer1")["ok"] is False


def c21():
    lg = _case()
    lg.create_case("d", "G3", 7)
    pr = lg.open_proceeding("d", "G3", "HUMAN_REVIEW")
    lg.complete_review(pr["id"], "reviewer1", "ok")
    assert lg.close_review("c", pr["id"], "officer1")["ok"] is False


def c22():
    lg = L()
    lg.create_case("c", "G2", 7)
    lg.receive("c", X.claim(1, "G2"))
    lg.receive("c", {**X.claim(2, "G2"), "exception": {"reason": "x"}})
    assert lg.decide_exception("c", "G2", True, "reviewer1")["ok"] is False and lg.effective_state("c", "G2")["effective"] == "SECURED"


def c23():
    lg = _case()
    before = (lg.effective_state("c", "G3"), lg.closures("c"), lg.restoration_sequence("c")["stages"])
    lg.record_determination("c", None, "a court (reported)", "a decision")
    after = (lg.effective_state("c", "G3"), lg.closures("c"), lg.restoration_sequence("c")["stages"])
    assert before == after


def c24():
    lg = _case()
    r = lg.record_restoration_claim("c", "the person", "the benefit was restored")
    s = lg.restoration_sequence("c")
    assert r["material_restoration_verified"] is False and s["restoration_claims_recorded"] == 1 and s["stages"][-1]["present"] is False


def c25():
    lg = _case()
    _run(lg)
    mid = lg.observe("c", "ACCESS_ONLY", "m")["measurement_id"]
    t = lg.now()
    lg.register_evidence("c", "G3", OK, scope="ACCESS")
    assert lg.status_at(mid, t) == "CURRENT"
    free = _case({"immutable": False})
    _run(free)
    m2 = free.observe("c", "ACCESS_ONLY", "m")["measurement_id"]
    t2 = free.now()
    free.register_evidence("c", "G3", OK, scope="ACCESS")
    assert free.status_at(m2, t2) is None, "an overwriting store cannot say what the status was"


CHECKS = [c01, c02, c03, c04, c05, c06, c07, c08, c09, c10, c11, c12, c13, c14, c15, c16, c17, c18, c19, c20, c21, c22, c23, c24, c25]


@pytest.mark.parametrize("check", CHECKS, ids=[f.__name__ for f in CHECKS])
def test_direct_and_adversarial_check(check):
    check()


def test_there_are_exactly_twenty_five_checks():
    assert len(CHECKS) == 25 and len({f.__name__ for f in CHECKS}) == 25


# ------------------------------------------------------------------------------------------------ the world built to the stated aggregates
def test_the_verification_model_gives_the_stated_aggregates_and_is_not_the_original():
    e = W.enumerate_world("r16_stated_aggregates")
    pc = e["per_condition"]
    assert [pc[c]["model_access"] for c in W.CONDITIONS] == R.STATED["model_access"] and [pc[c]["sensor_access"] for c in W.CONDITIONS] == R.STATED["sensor_access"]
    assert [pc[c]["disagreements"] for c in W.CONDITIONS] == [0, 0, 0, 0, 8, 18] and e["comparisons"] == 1536 and e["boolean_model_agrees"] == e["boolean_sensor_agrees"] == 1536
    assert e["historical_counts_reproduced"] is False and "by construction" in e["note"] and "not" in e["note"]
    assert all(W.model_access(s, c, "r16_stated_aggregates") for s in range(256) for c in W.CONDITIONS if W.sensor_access(s, c, "r16_stated_aggregates")), "the sensor's access is contained in the model's"
    with pytest.raises(ValueError):
        W.observe(0, "BASE", "ACCESS_ONLY", "nope")
    with pytest.raises(ValueError):
        LG.Ledger(world="nope")


def test_the_first_world_is_unchanged_by_the_second():
    e = W.enumerate_world()
    assert "world" not in e and e["per_condition"]["EXEC_GATE"]["model_access"] == 88 and W.enumerate_world("own") == e


def test_the_ledger_realises_the_stated_world():
    for cond in W.CONDITIONS:
        lg = L(world="r16_stated_aggregates")
        lg.create_case("c", "G3", W.pack(a=1, b=1, c=0, h=0))
        X._drive(lg, cond)  # noqa: SLF001
        w = lg.world("c")
        o = lg.observe("c", "EXPANDED", "m")
        d = W.observe(w["bits"], w["condition"], "EXPANDED", "r16_stated_aggregates")
        assert (o["model"], o["sensor"]) == (d["model"], d["sensor"]) and w["condition"] == cond


# ------------------------------------------------------------------------------------------------ saved results
@pytest.mark.skipif(not (EV / "EXP-R16-09.json").exists(), reason="results not saved")
def test_the_saved_r16_results_replay_were_frozen_first_and_keep_their_readings():
    for key in R.RUN:
        saved = json.loads((EV / f"{key}_unit_first.json").read_text())
        u = R.RUN[key](saved["seed"])
        assert digest_of(json.loads(json.dumps(u, default=str))) == saved["digest"], key
    assert PR.ProtocolRegistry(EV / "protocol_registry.jsonl").verify() == []
    d = {k: json.loads((EV / f"{k}.json").read_text()) for k in R.RUN}
    r = {k: v["results"] for k, v in d.items()}
    assert r["EXP-R16-02"]["R201"]["criterion_met"] and r["EXP-R16-02"]["R201"]["cases"] == 120 and r["EXP-R16-02"]["R201"]["cases_equal"] == 120
    assert r["EXP-R16-04"]["R401"]["criterion_met"] and "by construction" in r["EXP-R16-04"]["R401"]["reading"] and r["EXP-R16-04"]["R403"]["boolean_model_agrees"] == 1536
    assert all(r["EXP-R16-08"][a]["criterion_met"] for a in ("R801", "R802", "R803")) and r["EXP-R16-08"]["R804"]["supported"] and r["EXP-R16-08"]["R805"]["supported"]
    assert r["EXP-R16-09"]["R902"]["differs"].keys() == {"P5", "P10", "P15"} and r["EXP-R16-09"]["R904"]["principles_without_a_duty"] == ["P1"]
    assert all(v["evidence_class"] in ("Implementation Property", "Synthetic-world Result") for v in d.values())
