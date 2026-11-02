"""TEOO legal governance on the source text: the canonical catalogue is the source (verified against the files when they are present), the evaluator follows the rules of the source (R2 section 16; V3.0 8, Appendix A and B), and nothing
is aggregated. The provisional catalogue of the first implementation is shown to be a paraphrase."""

from __future__ import annotations

import hashlib
import json
import os
import random
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xzr.service import app as app_mod
from xzr.teoo import legal as L
from xzr.teoo import legal_source as LS

TEOO = Path(__file__).resolve().parents[1] / "xzr" / "teoo"
DL = Path.home() / "Downloads"
V3 = DL / "The_Minimum_Guarantees_Human_Legal_Subjecthood_PUBLICATION_FINAL_V3_0.docx"
client = TestClient(app_mod.app)


PRIVATE = os.environ.get(LS.ENV)


def test_the_public_specification_has_the_source_titles_checksums_and_question_counts_but_no_wording():
    c = L.CANON
    assert c["verified_against_original"] is True and c["editions_identical_for_guarantees"] is True and set(c["sources"]) == {"v3_0", "v3_0_100_point_edition", "ai_law_osr_r2"}
    assert [g["number"] for g in L.GUARANTEES] == list(range(1, 16)) and sum(g["audit_question_count"] for g in L.GUARANTEES) == 45 and set(c["sub_findings"]) == {"G12A", "G12B", "G15A", "G15B", "G15C", "G15D"}
    assert L.GUARANTEES[1]["title"] == "Non-Degradation of Minimum Guarantees by Score" and L.GUARANTEES[14]["title"] == "Effective Re-entry, Minimum Resources, Material Restoration, and Mutual Audit"
    if PRIVATE:
        assert "Generic statements that analytics may be used are insufficient." in L.GUARANTEES[2]["definition"] and sum(len(g["audit_questions"]) for g in L.GUARANTEES) == 45 and c["text_available"]
    else:
        assert not c["text_available"] and all(g["definition"] is None and g["audit_questions"] == [] for g in L.GUARANTEES)
    assert "not a sixteenth guarantee" in c["principle_status"] and "software" in c["software_limit"].lower() and "does not decide legal legitimacy" in c["software_limit"]


@pytest.mark.skipif(not V3.exists(), reason="the primary source is not on this machine")
def test_the_canonical_file_is_exactly_what_the_sources_say_when_the_sources_are_present():
    import importlib.util

    spec = importlib.util.spec_from_file_location("intake", Path(__file__).resolve().parents[1] / "scripts" / "teoo_legal_source_intake.py")
    m = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(m)  # type: ignore[union-attr]
    g = m.extract_guarantees(m.paragraphs(V3))
    assert hashlib.sha256(V3.read_bytes()).hexdigest() == L.CANON["sources"]["v3_0"]["sha256"]
    for x in L.GUARANTEES:
        assert (x["title"], x["source_position"]) == (g[x["number"]]["title"], g[x["number"]]["position"])
        assert x["audit_question_count"] == 3
        if x["definition"] is not None:  # the private store is attached
            assert x["definition"] == g[x["number"]]["definition"]


def test_the_provisional_catalogue_of_the_first_implementation_is_a_paraphrase_of_the_source():
    prov = json.loads((TEOO / "legal_guarantees_provisional.json").read_text())
    same = [p["number"] for p, c in zip(prov["guarantees"], L.GUARANTEES, strict=True) if p["title"] == c["title"]]
    assert same == [1, 4, 13, 14] and prov["verified_against_original"] is False and all(p["description"] != c["definition"] for p, c in zip(prov["guarantees"], L.GUARANTEES, strict=True))  # a withheld (None) definition differs by construction


def test_the_public_file_is_exactly_the_projection_of_the_private_store_when_it_is_attached():
    if not PRIVATE:
        pytest.skip("no private store attached (XZR_TEOO_PRIVATE_SOURCE)")
    assert LS.public_spec(json.loads(Path(PRIVATE).expanduser().read_text())) == json.loads(LS.PUBLIC_FILE.read_text())


def test_a_private_store_that_does_not_match_the_public_specification_is_refused(tmp_path):
    full = {"schema": LS.PRIVATE_SCHEMA, "sources": {}, "guarantees": []}
    bad = tmp_path / "store.json"
    bad.write_text(json.dumps(full))
    with pytest.raises(LS.PrivateSourceError):
        LS.load(bad)
    with pytest.raises(LS.PrivateSourceError):
        LS.load(tmp_path / "missing.json")


def test_the_state_rule_follows_the_source():
    # missing evidence is Indeterminate and is never compliance (B.10); policy alone cannot establish implementation (A.8); Tier 3 alone cannot establish compliance (B.2)
    assert L.decide(None)["state"] == "INDETERMINATE" and L.decide(None)["adverse_inference"]
    assert L.decide(L.Evidence(exists=True, usable=None, score_conditioned=False, tier=1))["state"] == "INDETERMINATE"
    assert L.decide(L.Evidence(exists=True, usable=True, score_conditioned=False, tier=3))["state"] == "INDETERMINATE"
    assert L.decide(L.Evidence(exists=True, usable=True, score_conditioned=None, tier=1))["state"] == "INDETERMINATE"
    # hard failures (8.2): absent, conditioned on the contested score, practically unusable
    for ev in (L.prov(exists=False), L.prov(score_conditioned=True), L.prov(usable=False)):
        d = L.decide(ev)
        assert d["state"] == "ABSENT" and d["hard_failure"]
    assert L.decide(L.prov(shortfalls=("omits the decision stage",)))["state"] == "PARTIAL" and "omits the decision stage" in L.decide(L.prov(shortfalls=("omits the decision stage",)))["reason"]
    s = L.decide(L.prov())
    assert s["state"] == "SECURED" and "affirmative Tier 1" in s["reason"]
    na = L.decide(None, (False, "no irreversible harm is possible"))
    assert na["state"] == "INAPPLICABLE" and "challengeable ground" in na["reason"] and "no irreversible harm" in na["reason"]


def test_the_findings_do_not_compensate_for_one_another():
    inst = L.baseline_institution()
    ev = L.evidence_for(inst, 3)
    base = L.audit(inst, 3, evidence=ev)
    st = {f["id"]: f["state"] for f in base["findings"]} | {s["id"]: s["state"] for s in base["sub_findings"]}
    rng = random.Random(1)
    for _ in range(30):
        target = rng.choice(L.FINDING_IDS)
        for repl in (L.prov(exists=False), L.prov(), None):
            ev2 = dict(ev)
            ev2[target] = repl
            a = L.audit(inst, 3, evidence=ev2)
            st2 = {f["id"]: f["state"] for f in a["findings"]} | {s["id"]: s["state"] for s in a["sub_findings"]}
            assert all(st2[g] == st[g] for g in L.FINDING_IDS if g != target)  # a secured notice does not mend an absent appeal, and an absent one does not break a secured notice
    assert all(k not in base for k in ("total", "score", "average", "rank", "weighted")) and "no aggregate" in base["no_total"]


def test_g12_and_g15_are_reported_through_their_sub_findings_and_the_parent_is_the_worst_of_them():
    a = L.audit(L.baseline_institution(), 3)
    g12 = next(f for f in a["findings"] if f["id"] == "G12")
    assert [s["id"] for s in g12["sub_findings"]] == ["G12A", "G12B"] and g12["state"] == L.worst([s["state"] for s in g12["sub_findings"]])
    assert [s["id"] for s in next(f for f in a["findings"] if f["id"] == "G15")["sub_findings"]] == ["G15A", "G15B", "G15C", "G15D"]
    assert L.worst(["SECURED", "PARTIAL"]) == "PARTIAL" and L.worst(["SECURED", "INDETERMINATE", "PARTIAL"]) == "INDETERMINATE" and L.worst(["SECURED", "ABSENT"]) == "ABSENT" and L.worst(["INAPPLICABLE", "INAPPLICABLE"]) == "INAPPLICABLE"


def test_a_formal_appeal_that_cannot_alter_the_decision_is_a_hard_failure_not_a_partial_compliance():
    base = L.baseline_institution()
    a = L.audit(base, 3)
    g11 = next(f for f in a["findings"] if f["id"] == "G11")
    assert base.appeal and g11["state"] == "ABSENT" and g11["hard_failure"] and "practically unusable" in g11["reason"]
    fixed = L.audit(base.with_(review_authority=True, review_independent=True, review_capacity=0.3), 3)
    assert next(f for f in fixed["findings"] if f["id"] == "G11")["state"] == "SECURED"
    # a correction that does not reach the downstream recipient is a hard failure (8.2) although the source data are corrected
    assert next(f for f in a["findings"] if f["id"] == "G10")["state"] == "ABSENT"


def test_the_low_score_subject_finding_is_separate_and_detects_score_conditioned_review():
    b = L.baseline_institution().with_(review_authority=True, review_independent=True, review_capacity=0.3)
    deg = [L.audit(b.with_(score_degrades_review=True), s)["U"]["state"] for s in range(12)]
    ctl = [L.audit(b, s)["U"]["state"] for s in range(12)]
    assert deg.count("ABSENT") >= 11 and ctl.count("ABSENT") <= 1
    a = L.audit(b.with_(score_degrades_review=True), 0)
    assert "U" not in {f["id"] for f in a["findings"]} and a["U"]["failed_in"] == ["G2"] and "Score-Based Procedural Degradation" in a["U"]["reason"]
    assert any(f["id"] == "G2" and f["state"] == "ABSENT" and f["hard_failure"] for f in a["findings"])


def test_an_unobserved_finding_is_indeterminate_and_the_recommendation_is_advisory():
    inst = L.repaired_institution()
    obs = {f for f in L.FINDING_IDS if f not in ("G3", "G9", "G13")}
    a = L.audit(inst, 3, observed=obs)
    st = {s["id"]: s["state"] for s in a["sub_findings"]} | {f["id"]: f["state"] for f in a["findings"]}
    assert st["G3"] == "INDETERMINATE" and st["G9"] == "INDETERMINATE" and st["G13"] == "INDETERMINATE" and st["G11"] == "SECURED" and "not observed is not absent" in next(f for f in a["findings"] if f["id"] == "G3")["reason"]
    r = L.audit(inst, 3, min_cases=0)["recommendation"]
    assert r["advisory_only"] and "human decision maker" in r["decided_by"] and r["candidate"] == "continue with monitored compliance"
    # with the minimum-case rule (the default) a well-repaired institution has too few wrongful denials for the score-degradation test to have been performed: U is Indeterminate, not passed
    d = L.audit(inst, 3)
    assert d["U"]["state"] == "INDETERMINATE" and d["recommendation"]["candidate"] == "continue subject to time-limited corrective conditions"
    assert L.audit(L.baseline_institution(), 3)["recommendation"]["candidate"] == "withdraw and redesign"  # a constitutive failure (G1, G2, U): the source's taxonomy, the candidate is only advice
    ev = {k: L.prov(exists=False) if k == "G13" else v for k, v in L.evidence_for(L.repaired_institution(), 3, min_cases=0).items()}
    assert L.audit(L.repaired_institution(), 3, evidence=ev)["recommendation"]["candidate"] == "suspend the relevant use"


def test_inapplicable_needs_its_reason_and_is_checked_against_the_configuration():
    a = L.audit(L.baseline_institution().with_(harm_irreversible=False), 3)
    g13 = next(f for f in a["findings"] if f["id"] == "G13")
    assert g13["state"] == "INAPPLICABLE" and "challengeable ground" in g13["reason"] and g13["applicable"] is False
    assert next(f for f in L.audit(L.baseline_institution(), 3)["findings"] if f["id"] == "G13")["state"] != "INAPPLICABLE"


def test_the_translation_register_gives_g6_and_g7_their_evidence_and_the_chain_keeps_its_layers():
    a = L.audit(L.baseline_institution(), 3)
    g6, g7 = (next(f for f in a["findings"] if f["id"] == k) for k in ("G6", "G7"))
    assert g6["state"] == "PARTIAL" and "inherited_record_gate" in g6["reason"] and g7["state"] == "PARTIAL" and "translation loss" in g7["reason"]
    assert next(f for f in L.audit(L.baseline_institution().with_(proxy_gate=False), 3)["findings"] if f["id"] == "G6")["state"] == "SECURED"
    ok, bad = L.assess_chain(L.example_chain(True)), L.assess_chain(L.example_chain(False))
    assert ok["valid_legal_decision"] and [s["stage"] for s in ok["stages"]] == list(L.STAGES) and {s["layer"] for s in ok["stages"]} == {"technical", "asserted", "legal", "authorised decision", "review", "remedy"}
    assert not bad["valid_legal_decision"] and bad["first_invalid_stage"] == "legal_fact" and any("no legal basis" in w for s in bad["stages"] for w in s["why_not"]) and any("not a legal decision" in w for s in bad["stages"] for w in s["why_not"])
    nojur = L.example_chain(True)
    nojur[3] = {**nojur[3], "jurisdiction": None}
    assert L.assess_chain(nojur)["unresolved_legal_questions"] == ["legal_classification"]


def test_the_inheritance_test_gives_one_of_the_five_required_findings():
    b = L.baseline_institution()
    assert L.ontological_inheritance_finding(b, 3)["finding"] == "identified without safeguards"
    assert L.ontological_inheritance_finding(b.with_(score_expiry=4), 3)["finding"] == "identified with partial safeguards"
    assert L.ontological_inheritance_finding(b.with_(score_expiry=4, propagate_correction=True, collective_challenge=True), 3)["finding"] == "identified with effective safeguards"
    assert L.ontological_inheritance_finding(b.with_(lam=0.0, downstream_sharing=False, proxy_gate=False), 3)["finding"] == "no inheritance identified"
    assert L.ontological_inheritance_finding(b, 3, lineage_produced=False)["finding"] == "indeterminate"


def test_the_five_self_application_controls_hold_for_every_report():
    for inst in (L.baseline_institution(), L.repaired_institution()):
        a = L.audit(inst, 3)
        c = L.audit_integrity(a)
        assert c["no_person_scored"] and c["no_total"] and c["no_presumption_against_persons"] and c["evidence_limits_disclosed"] and "counter-audit" in c["challenge_route"] and c["framework_revision_trigger"] is False
    h = [L.audit(L.baseline_institution(), s) for s in (1, 2)]
    assert L.audit_integrity(h[0], h)["framework_revision_trigger"] is True  # recurring hard failures across audits trigger revision of the framework itself


def test_the_new_mechanisms_of_the_simulator_do_what_the_audit_assumes():
    b = L.baseline_institution().with_(review_authority=True, review_independent=True, review_capacity=0.3)
    r0, r6 = L.simulate(b, 5), L.simulate(b.with_(review_delay=6), 5)
    assert r6["time_to_restoration_mean"] > r0["time_to_restoration_mean"]
    deg = L.simulate(b.with_(score_degrades_review=True), 5)
    assert deg["review_rate_low_score"] < 0.7 * deg["review_rate_high_score"] and L.simulate(b, 5) == L.simulate(b, 5)
    assert L.simulate(b.with_(material_relief=True, review_delay=3), 5)["mean_resources_qualified"] > L.simulate(b.with_(review_delay=3), 5)["mean_resources_qualified"]
    assert L.simulate(L.baseline_institution(), 5)["endogenous_share_of_score"] > 0.15  # later data carry a material share of the score that the treatment produced


def test_the_legal_route_serves_the_source_based_bundle_locally_only(monkeypatch):
    import dataclasses

    from xzr.service import studies
    from xzr.service.limits import LIMITS

    r = client.get("/api/teoo/legal").json()
    assert r["synthetic"] and r["catalogue"]["verified_against_original"] is True and len(r["guarantees"]) == 15 and len(r["assessments"]) == 5 and all(len(v) == 15 for v in r["assessments"].values())
    assert r["guarantees"][1]["definition"] == L.GUARANTEES[1]["definition"] and "software" in r["software_limit"].lower() and "register" in r and "inheritance" in r
    assert all("U" in a and "recommendation" in a and "outcome_taxonomy" in a for a in r["audits"].values()) and client.get("/api/teoo/legal", params={"seed": -1}).status_code == 422
    monkeypatch.setattr(studies, "LIMITS", dataclasses.replace(LIMITS, public=True))
    assert client.get("/api/teoo/legal").status_code == 403


def test_the_saved_source_based_results_are_those_of_the_registered_protocols_and_keep_their_negative_results():
    from xzr.teoo import protocol as PR

    ev = TEOO.parents[2] / "docs" / "teoo_evidence" / "legal_source_v1"
    reg = PR.ProtocolRegistry(ev / "protocol_registry.jsonl")
    assert reg.verify() == []
    for k in ("LG2-EXP-01", "LG2-EXP-02", "LG2-EXP-03", "LG2-EXP-04", "LG2-EXP-05", "LG2-EXP-06", "LG2-EXP-07"):
        d = json.loads((ev / f"{k}.json").read_text())
        p = reg.get(d["protocol"]["experiment_id"], 1)
        assert PR.body_digest(p) == d["protocol_digest"] and d["units"] == 30 and all(d["results"][a["id"]]["registered_class"] == reg.analysis_class(p["experiment_id"], 1, a["id"]) for a in p["analyses"])
    e1 = json.loads((ev / "LG2-EXP-01.json").read_text())
    assert e1["results"]["L201e"]["criterion_met"] is False and e1["results"]["L201e"]["sensitivity"] < 0.5  # the score-degradation test was blind where reviews were few: kept as the negative result it is
    e7 = json.loads((ev / "LG2-EXP-07.json").read_text())
    assert e7["results"]["L207a"]["criterion_met"] is False and e7["results"]["L207b"]["criterion_met"] is False and e7["results"]["L207c"]["p_holm"] < 0.001
    assert json.loads((ev / "LG2-EXP-04.json").read_text())["results"]["L204c"]["p_holm"] > 0.05  # re-entry support was not shown to add re-entering persons
    old = json.loads((TEOO.parents[2] / "docs" / "teoo_evidence" / "legal" / "CMP-01.json").read_text())
    assert old["results"]["L11a"]["p"] > 0.05 and old["evidence_class"] == "Synthetic-world Result"  # the first implementation's results are untouched


def test_the_legal_figures_keep_concept_and_result_apart_and_cannot_lose_their_evidence():
    from xzr.teoo import export as EX

    d = TEOO.parents[2] / "docs" / "teoo_evidence" / "legal_figures"
    idx = json.loads((d / "legal_figures_index.json").read_text())
    assert len(idx["figures"]) == 8 and idx["concept_figures"] == ["legal_fig1", "legal_fig2", "legal_fig8"]
    for f in sorted(d.glob("legal_fig*.svg")):
        md = json.loads((d / f"{f.stem}.metadata.json").read_text())
        concept = f.stem.split("_")[0] + "_" + f.stem.split("_")[1] in ("legal_fig1", "legal_fig2", "legal_fig8")
        assert EX.verify_svg(f.read_text()) == [] and md["evidence"]["classes"] == (["CONCEPTUAL"] if concept else ["SYNTHETIC"]) and md["evidence"]["real_world_experiment_recorded"] is False
        assert (md["experiment"] is None) == (concept or f.stem.startswith("legal_fig7"))
        png = EX.inspect_png((d / f"{f.stem}.png").read_bytes())
        assert png["ok"] and png["metadata"] == md
