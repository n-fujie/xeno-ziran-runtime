"""TEOO AI legal governance: the provisional fifteen-guarantee catalogue is assessed one by one and never combined, a stage without a legal basis is not a legal stage, the synthetic institution behaves as its experiments assume, and the saved
results are those of the registered protocols."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xzr.service import app as app_mod
from xzr.teoo import legal as L
from xzr.teoo import protocol as PR

EV = Path(__file__).resolve().parents[2] / "docs" / "teoo_evidence" / "legal"
client = TestClient(app_mod.app)


def test_the_catalogue_has_fifteen_guarantees_and_says_that_it_is_provisional():
    assert [g["number"] for g in L.GUARANTEES] == list(range(1, 16)) and len({g["title"] for g in L.GUARANTEES}) == 15
    assert L.CATALOGUE_STATUS["verified_against_original"] is False and "PROVISIONAL" in L.CATALOGUE_STATUS["note"] and "not found" in L.CATALOGUE_STATUS["note"]
    assert len(L.PROVISIONS) == 15 and set(L.GUARANTEE_PROVISION.values()) == set(L.PROVISIONS)
    assert L.GUARANTEES[1]["title"] == "Non-Reduction of Guarantees by Score"


def test_each_guarantee_gets_its_own_state_and_no_score_exists():
    a = L.assess_guarantees(L.Institution(), 1)
    assert [x["number"] for x in a] == list(range(1, 16)) and {x["state"] for x in a} <= set(L.STATES) and len({x["state"] for x in a}) > 1
    assert all({"applicable", "required_evidence", "institutional_function", "reason", "remedy_path", "catalogue_verified"} <= set(x) and x["catalogue_verified"] is False for x in a)
    assert not any(k in x for x in a for k in ("score", "total", "legitimacy"))  # fifteen states, never one figure
    assert all(x["remedy_path"] for x in a if x["state"] in ("ABSENT", "PARTIAL"))


def test_absent_partial_indeterminate_and_inapplicable_each_need_their_own_ground():
    inst = L.Institution()
    gone = inst.with_(provisions={**inst.provisions, "ai_use_notice": False, "score_access": None})
    st = {x["provision"]: x for x in L.assess_guarantees(gone, 1)}
    assert st["ai_use_notice"]["state"] == "ABSENT" and st["score_access"]["state"] == "INDETERMINATE" and "unknown" in st["score_access"]["reason"]
    assert st["contestation"]["state"] == "PARTIAL" and "no effect" in st["contestation"]["reason"] or "partly" in st["contestation"]["reason"]  # a formal appeal that can reverse nothing
    seen = {p for p in L.PROVISIONS if p != "history_access"}
    part = {x["provision"]: x for x in L.assess_guarantees(gone, 1, observed=seen)}
    assert part["history_access"]["state"] == "INDETERMINATE" and "not observed is not absent" in part["history_access"]["reason"]
    safe = {x["provision"]: x for x in L.assess_guarantees(inst.with_(harm_irreversible=False), 1)}
    assert safe["suspension"]["state"] == "INAPPLICABLE" and "checked against the configuration" in safe["suspension"]["reason"] and safe["suspension"]["applicable"] is False
    assert {x["provision"]: x for x in L.assess_guarantees(inst, 1)}["suspension"]["state"] != "INAPPLICABLE"  # no exemption without its ground


def test_repairs_secure_what_they_repair():
    base = L.Institution()
    fixed = base.with_(review_independent=True, review_authority=True, review_capacity=0.3, appeal_burden=0.2, propagate_correction=True, score_expiry=4, reentry_support=True, suspension=True, proxy_gate=False, lam=0.0)
    before = {x["provision"]: x["state"] for x in L.assess_guarantees(base, 1)}
    after = {x["provision"]: x["state"] for x in L.assess_guarantees(fixed, 1)}
    assert before["human_review"] == "PARTIAL" and after["human_review"] == "SECURED" and before["correction"] == "PARTIAL" and after["correction"] == "SECURED"
    assert before["expiry_reassessment"] == "PARTIAL" and after["expiry_reassessment"] == "SECURED"


def test_a_stage_without_a_legal_basis_is_not_a_legal_stage_and_an_ai_output_is_not_a_decision():
    ok = L.assess_chain(L.example_chain(True))
    assert ok["valid_legal_decision"] and ok["first_invalid_stage"] is None and [s["stage"] for s in ok["stages"]] == list(L.STAGES)
    bad = L.assess_chain(L.example_chain(False))
    assert not bad["valid_legal_decision"] and bad["first_invalid_stage"] == "legal_fact" and any("an AI output is not a legal decision" in w for s in bad["stages"] for w in s["why_not"])
    technical = L.assess_chain([L.stage("technical_event", legal_basis=None, scope="s", responsible="r", evidence="e", uncertainty="u", authority=None, contest_path=None)])
    assert technical["stages"][0]["valid"] and not technical["valid_legal_decision"]  # a technical fact needs no legal basis, and is not a decision either
    shuffled = L.example_chain(True)[::-1]
    assert L.assess_chain(shuffled)["issues"]
    with pytest.raises(ValueError):
        L.stage("vibes", legal_basis="x", scope="s", responsible="r", evidence="e", uncertainty="u", authority=None, contest_path=None)
    no_route = L.example_chain(True)
    no_route[-2] = {**no_route[-2], "contest_path": None}
    assert not L.assess_chain(no_route)["stages"][-2]["valid"]


def test_the_institution_is_deterministic_and_fairness_optimisation_narrows_the_gap_but_not_the_exclusion():
    b = L.simulate(L.Institution(), 11)
    assert b == L.simulate(L.Institution(), 11) and b != L.simulate(L.Institution(), 12)
    f = L.simulate(L.Institution().with_(fairness_opt=True), 11)
    assert f["tpr_gap"] < b["tpr_gap"] - 0.2 and abs(f["exclusion_persistence"] - b["exclusion_persistence"]) < 0.1


def test_deleting_the_score_lets_the_proxy_take_its_place_and_deleting_both_leaves_a_lottery():
    base = L.Institution()
    d = L.simulate(base.with_(tau_score=False), 5)
    both = L.simulate(base.with_(tau_score=False, proxy_gate=False), 5)
    assert d["exclusion_qualified"] > L.simulate(base, 5)["exclusion_qualified"] + 0.1  # the proxy replaces the score
    assert both["group_exclusion_gap"] < 0.2 and both["exclusion_qualified"] > 0.4  # no group gap, but qualification no longer counts either


def test_a_formal_appeal_without_authority_reverses_nothing_and_an_independent_reviewer_does():
    formal = L.simulate(L.Institution(), 7)
    eff = L.simulate(L.Institution().with_(review_independent=True, review_authority=True, review_capacity=0.3, appeal_burden=0.2), 7)
    assert formal["formal_appeal_rate"] > 0.1 and formal["overturn_rate_of_wrongful"] == 0.0 and eff["overturn_rate_of_wrongful"] > 0.1


def test_a_correction_reaches_the_second_institution_only_if_it_is_propagated():
    inst = L.Institution().with_(review_authority=True, review_independent=True)
    none = L.simulate(inst, 9, correct_at=8)
    prop = L.simulate(inst.with_(propagate_correction=True), 9, correct_at=8)
    assert prop["downstream_access_qualified"] > none["downstream_access_qualified"] and prop["downstream_mismatch"] <= none["downstream_mismatch"]


def test_the_legal_route_is_local_only_and_returns_a_synthetic_bundle_with_the_provisional_notice(monkeypatch):
    import dataclasses

    from xzr.service import studies
    from xzr.service.limits import LIMITS

    r = client.get("/api/teoo/legal").json()
    assert r["synthetic"] and r["catalogue"]["verified_against_original"] is False and len(r["guarantees"]) == 15 and len(r["assessments"]) == 4
    assert all(len(v) == 15 for v in r["assessments"].values()) and not r["chains"]["decided by the scoring system"]["assessment"]["valid_legal_decision"]
    assert "not observed is not absent" in r["observation"]["note"] and client.get("/api/teoo/legal", params={"seed": -1}).status_code == 422
    monkeypatch.setattr(studies, "LIMITS", dataclasses.replace(LIMITS, public=True))
    assert client.get("/api/teoo/legal").status_code == 403


def test_the_saved_legal_results_are_those_of_the_registered_protocols_and_keep_their_negative_results():
    reg = PR.ProtocolRegistry(EV / "protocol_registry.jsonl")
    assert reg.verify() == []
    for k in ("EXP-01", "EXP-02", "EXP-03", "EXP-04", "EXP-05", "EXP-06", "EXP-07", "EXP-08", "EXP-09", "EXP-10", "CMP-01"):
        d = json.loads((EV / f"{k}.json").read_text())
        p = reg.get(d["protocol"]["experiment_id"], 1)
        assert PR.body_digest(p) == d["protocol_digest"] and d["units"] == 30 and all(d["results"][a["id"]]["registered_class"] == reg.analysis_class(p["experiment_id"], 1, a["id"]) for a in p["analyses"])
    e9 = json.loads((EV / "EXP-09.json").read_text())
    assert e9["evidence_class"] == "Implementation Property" and e9["catalogue"]["verified_against_original"] is False and e9["results"]["L09a"]["criterion_met"] and e9["results"]["L09b"]["criterion_met"]
    c = json.loads((EV / "CMP-01.json").read_text())
    assert c["osr_autonomous_revision_demonstrated"] is False and c["results"]["L11a"]["p"] > 0.05  # the revision rule is NOT shown to add anything over a random extra field
    assert json.loads((EV / "EXP-08.json").read_text())["results"]["L08c"]["mean_rho"] < 0  # how convincing an intervention is does not track what it does here
