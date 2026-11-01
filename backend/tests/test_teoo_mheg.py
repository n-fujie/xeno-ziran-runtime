"""The twelve MHEG duties, their functional crosswalk to the fifteen guarantees, the directive's state vocabulary, the itemised provisions and the legal transformation chain (xzr.teoo.mheg)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xzr.service import app as app_mod
from xzr.teoo import legal as L
from xzr.teoo import mheg as M
from xzr.teoo import mheg_experiments as X
from xzr.teoo import protocol as PR
from xzr.teoo.provenance import digest_of

client = TestClient(app_mod.app)
EV = Path(__file__).resolve().parents[2] / "docs" / "teoo_evidence" / "mheg"

REPORTED = {  # the crosswalk as reported (R16), expanded by hand: the test does not use expand()
    "M1": ["G3"], "M2": ["G6"], "M3": ["G2", "G6", "G7", "G8", "G11", "G12A", "G12B", "G14"], "M4": ["G7", "G8", "G9"], "M5": ["G4", "G5", "G8"], "M6": ["G10", "G14", "G15A", "G15B", "G15C", "G15D"],
    "M7": ["G7", "G8", "G11", "G12A", "G12B", "G14"], "M8": ["G9"], "M9": ["G12B"], "M10": ["G11", "G12A", "G12B", "G13", "G15A", "G15B", "G15C", "G15D"], "M11": ["G15D"], "M12": ["G15B", "G15C"]}


def test_the_twelve_duties_are_a_registry_of_their_own_with_the_reported_crosswalk():
    assert [d["id"] for d in M.DUTIES] == [f"M{i}" for i in range(1, 13)]
    assert [d["name"] for d in M.DUTIES] == ["AI Use Notice", "Source Visibility", "Purpose Legitimacy", "Translation Visibility", "Data Access", "Correction Capacity", "Epistemic and Distributive Validity", "Reason Access", "Human Reconsideration",
                                             "Appeal Access", "Systemic Challenge", "Material Restoration"]
    assert {d["id"]: d["findings"] for d in M.DUTIES} == REPORTED
    for d in M.DUTIES:
        assert d["input"] and d["authority_subject"] and "VIOLATED" in d["violation_condition"] and "INSUFFICIENT_EVIDENCE" in d["indeterminate_condition"] and all(f in d["violation_condition"] for f in d["findings"])
        assert d["definition_status"] == "FUNCTIONAL_SUMMARY" and "R16" in d["source"] and d["label_ja"] and d["function"] and d["cannot_verify"] and d["required_evidence"] and d["evaluation_target"]
        assert "not an identity" in d["identity_with_guarantees"]
    titles = {g["title"] for g in L.GUARANTEES}
    assert not titles & {d["name"] for d in M.DUTIES}, "a duty is not a guarantee: the names are not shared"
    assert len({d["id"] for d in M.DUTIES}) == 12 and len(L.GUARANTEES) == 15, "the duties are not replaced by the guarantees, nor the guarantees by the duties"


def test_the_crosswalk_is_functional_not_one_to_one_and_g1_is_named_by_no_duty():
    cw = M.crosswalk_matrix()
    assert cw["not_named_by_any_duty"] == ["G1"] and sorted(cw["named_by_one_duty"]) == sorted(["G2", "G3", "G4", "G5", "G10", "G13"]) and cw["broad_duties"] == ["M3", "M6", "M7", "M10"]
    assert cw["duties_per_finding"]["G8"] == 4 and cw["duties_per_finding"]["G12B"] == 4
    assert any(len(d["findings"]) > 1 for d in M.DUTIES) and any(cw["duties_per_finding"][f] > 1 for f in cw["findings"])
    assert [d["mapping_kind"] for d in M.DUTIES][:3] == ["direct", "direct", "broad"]


def test_the_governance_principles_are_a_separate_series_with_only_the_fifteenth_known_and_nothing_maps_them():
    g = M.GOVERNANCE_PRINCIPLES
    assert g["status"] == "PARTIALLY_KNOWN" and len(g["items"]) == 15 and [i["id"] for i in g["items"] if i["name_status"] != "UNVERIFIED"] == ["P15"]
    p15 = g["items"][14]
    assert p15["name"] == "Audit of the Auditor and Self-Audit of the Institutional Apparatus" and p15["version"] == "Recursive Double Audit" and p15["definition_status"] == "FUNCTIONAL_SUMMARY"
    assert all(i["name"] is None and i["scope"] is None for i in g["items"][:14]), "the other fourteen are not invented"
    assert g["crosswalk_to_guarantees"] is None and g["crosswalk_to_duties"] is None and "not reused" in g["rule"] and "ordinal position" in g["rule"]
    assert g["proximity"][0]["principle"] == "P15" and g["proximity"][0]["guarantee"] == "G15D" and g["proximity"][0]["verified"] is False and "identity is not assumed" in g["proximity"][0]["relation"]
    assert not {i["name"] for i in g["items"]} & {x["title"] for x in L.GUARANTEES}, "the names of the guarantees are not reused"


def test_directive_states_keep_not_applicable_insufficient_evidence_and_not_evaluated_apart():
    assert M.directive_state("SECURED") == "SATISFIED" and M.directive_state("PARTIAL") == "PARTIALLY_SATISFIED" and M.directive_state("ABSENT") == "VIOLATED"
    assert M.directive_state("INAPPLICABLE") == "NOT_APPLICABLE" and M.directive_state("INDETERMINATE", True) == "INSUFFICIENT_EVIDENCE" and M.directive_state("INDETERMINATE", False) == "NOT_EVALUATED"
    assert {"SATISFIED", "VIOLATED", "INSUFFICIENT_EVIDENCE", "NOT_APPLICABLE", "NOT_EVALUATED"} <= set(M.DSTATES)
    assert M.DRANK["INSUFFICIENT_EVIDENCE"] > M.DRANK["SATISFIED"] and M.DRANK["NOT_EVALUATED"] > M.DRANK["SATISFIED"], "neither is compliance"


def test_a_duty_is_its_worst_mapped_finding_and_one_failure_is_not_offset():
    st = {f: {"state": "SATISFIED"} for f in L.FINDING_IDS}
    assert all(v["state"] == "SATISFIED" for v in M.project(st).values())
    st["G12B"] = {"state": "VIOLATED"}
    p = M.project(st)
    assert {d for d, v in p.items() if v["state"] == "VIOLATED"} == {"M3", "M7", "M9", "M10"} and p["M9"]["drivers"] == ["G12B"] and p["M1"]["state"] == "SATISFIED"
    st["G3"] = {"state": "NOT_APPLICABLE"}
    assert M.project(st)["M1"]["state"] == "NOT_APPLICABLE"
    assert not any(k in json.dumps(p) for k in ("total_score", "average", "rank"))


def test_itemised_provisions_can_only_lower_a_finding():
    base = X.full(4001)
    ev0 = L.evidence_for(base, 4001, min_cases=0)
    assert all(L.decide(ev0[f])["state"] == "SECURED" for f in ("G3", "G5", "G9", "G15A"))
    for fid, names in L.COMPONENTS.items():
        allp = {n: True for n in names}
        assert L.decide(L.evidence_for(base.with_(components={fid: allp}), 4001, min_cases=0)[fid])["state"] == "SECURED"
        one = dict(allp, **{names[0]: False})
        d = L.decide(L.evidence_for(base.with_(components={fid: one}), 4001, min_cases=0)[fid])
        assert d["state"] == "PARTIAL" and names[0] in d["reason"]
        assert L.decide(L.evidence_for(base.with_(components={fid: {n: False for n in names}}), 4001, min_cases=0)[fid])["state"] == "ABSENT"
        unk = L.decide(L.evidence_for(base.with_(components={fid: {n: None for n in names}}), 4001, min_cases=0)[fid])
        assert unk["state"] == "INDETERMINATE" and unk["adverse_inference"], "not observed is never SECURED"
    assert base.components is None and base.with_(appeal=False).components is None


def test_each_finding_sits_in_exactly_one_stage_of_the_chain_and_a_broken_stage_is_found():
    fids = [f for c in M.CHAIN for f in c[4]]
    assert sorted(fids) == sorted(L.FINDING_IDS) and len(set(fids)) == 19
    assert [c[1] for c in M.CHAIN] == ["Legal Source", "Translation", "Data Representation", "Classification", "Institutional Treatment", "Effective Access", "Contestation", "Revision", "Material Restoration"]
    base = X.full(4001)
    ev = L.evidence_for(base, 4001, min_cases=0)
    ok = M.assess_transformation(base, L.audit(base, 4001, evidence=ev, min_cases=0), ev)
    assert ok["effective_to_the_end"] and ok["first_violated_stage"] is None and ok["information_lost_in_translation"] == []
    bad = X._break(base, "contestation")  # noqa: SLF001
    evb = L.evidence_for(bad, 4001, min_cases=0)
    r = M.assess_transformation(bad, L.audit(bad, 4001, evidence=evb, min_cases=0), evb)
    assert not r["effective_to_the_end"] and r["first_violated_stage"] == "contestation" and "predict" in r["rule"].lower()
    for s in r["stages"]:
        assert {"operating_condition", "authority_relation", "observability", "time_span", "resource_condition", "evidence", "failure_condition", "recovery_path"} <= set(s)


def test_the_fidelity_table_names_what_is_checked_and_what_is_not_for_every_finding():
    assert set(M.FIDELITY) == set(L.FINDING_IDS)
    assert all(v["implemented"] and v["not_implemented"] and v["normative_unverifiable"] for v in M.FIDELITY.values())


def test_the_bundle_carries_the_duties_the_projection_and_what_is_unverified():
    lb = L.legal_bundle(3)
    mb = M.mheg_bundle(lb)
    assert len(mb["duties"]) == 12 and set(mb["projections"]) == set(lb["assessments"]) and mb["governance_principles"]["status"] == "PARTIALLY_KNOWN" and len(mb["unverified"]) >= 5
    for p in mb["projections"].values():
        assert set(p["duties"]) == set(M.DUTY_IDS) and all(v["state"] in M.DSTATES for v in p["duties"].values())
        assert len(p["findings"]) == 19
    part = next(k for k in mb["projections"] if "not observed" in k)
    assert any(v["state"] == "NOT_EVALUATED" for v in mb["projections"][part]["findings"].values())
    assert "no total" in mb["limits"]


def test_the_legal_route_serves_the_mheg_bundle_locally_only(monkeypatch):
    r = client.get("/api/teoo/legal?seed=3")
    assert r.status_code == 200 and len(r.json()["mheg"]["duties"]) == 12 and r.json()["text_available"] is bool(os.environ.get("XZR_TEOO_PRIVATE_SOURCE"))
    import dataclasses

    from xzr.service import studies
    from xzr.service.limits import LIMITS

    monkeypatch.setattr(studies, "LIMITS", dataclasses.replace(LIMITS, public=True))
    assert client.get("/api/teoo/legal?seed=3").status_code == 403


@pytest.mark.skipif(not (EV / "MH-EXP-04.json").exists(), reason="results not saved")
def test_the_saved_results_replay_and_their_protocols_were_frozen_before_the_data():
    for key in X.RUN:
        saved = json.loads((EV / f"{key}_unit_first.json").read_text())
        u = X.RUN[key](saved["seed"])
        assert digest_of(json.loads(json.dumps(u, default=str))) == saved["digest"], key
    reg = PR.ProtocolRegistry(EV / "protocol_registry.jsonl")
    assert reg.verify() == []
    d = json.loads((EV / "MH-EXP-01.json").read_text())
    r = d["results"]
    assert r["M101"]["uncovered_singles"] == ["G1"] and r["M101"]["noncompensation_violations"] == 0 and r["M101"]["distinct_duty_signatures_among_190"] < 190
    d4 = json.loads((EV / "MH-EXP-04.json").read_text())["results"]
    assert d4["M402b"]["supported"] is False, "the negative result of the treatment stage is kept"
