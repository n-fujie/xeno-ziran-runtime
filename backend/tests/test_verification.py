"""Tests of the Brassier Machine verification layer (xzr.verification)."""

from __future__ import annotations

import copy
import inspect
import json

import numpy as np

from xzr.sbs.engine import Config, Sim
from xzr.verification import demo
from xzr.verification.brassier import (
    AUTHORITY,
    VERDICTS,
    Claim,
    Evidence,
    identify,
    standard_comparison,
    verdict_for,
    verify_record,
    with_brassier,
)


def test_equivalence_is_recorded_and_identified_by_an_intervention_otherwise_open():
    r = identify(demo.PAIRS["clamp_vs_free"], demo.BASE, [demo.LONG, demo.SENSOR2, demo.CLAMP])
    assert r["result"] == "IDENTIFIED" and r["identified_by"] == "clamp intervention" and r["equivalent_pairs_under_base"] == ["M1|M2"]
    assert [t["separates_all_equivalent_pairs"] for t in r["protocols_tried"]] == [False, False, True]
    o = identify(demo.PAIRS["hidden_label"], demo.BASE, [demo.LONG, demo.SENSOR2, demo.CLAMP])
    assert o["result"] == "OPEN" and o["identified_by"] is None and "not a statement that they are the same" in o["note"]  # condition 2
    d = identify(demo.PAIRS["gain_vs_offset"], demo.BASE, [demo.LONG])
    assert d["result"] == "DISTINGUISHABLE_UNDER_BASE" and d["equivalent_pairs_under_base"] == []


def test_the_verifier_is_given_no_generating_mechanism_and_labels_do_not_change_the_result():
    params = list(inspect.signature(identify).parameters)
    assert params == ["mechanisms", "base", "discriminating", "tol"]  # functions from a protocol to observations; no truth label
    swapped = {"M1": demo.clamped, "M2": demo.free}
    a = identify(demo.PAIRS["clamp_vs_free"], demo.BASE, [demo.CLAMP])
    b = identify(swapped, demo.BASE, [demo.CLAMP])
    assert (a["result"], a["identified_by"]) == (b["result"], b["identified_by"])


def test_the_existing_results_are_not_changed_and_disabling_the_machine_empties_only_the_ledger():
    sim = Sim(Config(n=16, eps=1.5), 1)
    sim.step(50)
    results = {"x": sim.x.copy(), "t": sim.t}
    before = copy.deepcopy(results)
    claims = [Claim("c", "t", evidence=[Evidence("e", "supports", "observation")])]
    on = with_brassier(results, claims)
    off = with_brassier(results, claims, enabled=False)
    assert on["results"] is results and off["results"] is results  # the same object, not a copy
    assert np.array_equal(results["x"], before["x"]) and results["t"] == before["t"]
    assert off["brassier"]["ledger"] == [] and len(on["brassier"]["ledger"]) == 1
    assert on["brassier"]["enabled"] is True and off["brassier"]["enabled"] is False  # removal, disabling and reintroduction are one argument


def test_verdicts_are_support_withhold_or_withdraw_and_never_a_determination_of_what_is_real():
    led = demo.demo_ledger()["brassier"]
    verdicts = {e["claim"]: e["verdict"] for e in led["ledger"]}
    assert verdicts == {"claim-clamp": "SUPPORTED", "claim-hidden": "WITHHELD", "claim-gain": "WITHDRAWN"}
    assert set(verdicts.values()) <= set(VERDICTS)
    text = json.dumps(led).lower()
    assert all(e["authority"] == AUTHORITY for e in led["ledger"]) and led["authority"] == AUTHORITY
    assert '"verdict": "true"' not in text and '"verdict": "real"' not in text and "exists" not in {e["verdict"].lower() for e in led["ledger"]}


def test_a_claim_with_only_its_own_models_output_is_not_supported_and_unresolved_equivalence_withholds_it():
    c = Claim("c", "t", evidence=[Evidence("e", "supports", "model_output")])
    e = verdict_for(c)
    assert e["verdict"] == "WITHHELD" and e["checks"]["independence"]["result"] == "MODEL_ONLY"
    c2 = Claim("c2", "t", evidence=[Evidence("e", "supports", "observation")])
    assert verdict_for(c2)["verdict"] == "SUPPORTED"
    assert verdict_for(c2, {"result": "OPEN"})["verdict"] == "WITHHELD"  # an unresolved equivalence blocks support


def test_negative_results_seeds_interventions_and_provenance_are_kept_in_a_sealed_record():
    a, b = demo.demo_ledger(), demo.demo_ledger()
    assert a["brassier"]["digest"] == b["brassier"]["digest"]  # deterministic
    gain = next(e for e in a["brassier"]["ledger"] if e["claim"] == "claim-gain")
    assert gain["checks"]["world_warrant"]["negative_results_kept"] == ["e-obs-a"]
    assert all(x["seeds"] == [0] and x["provenance"] and x["protocol"]["name"] for x in gain["evidence"])
    clamp = next(e for e in a["brassier"]["ledger"] if e["claim"] == "claim-clamp")
    assert clamp["evidence"][1]["protocol"]["interventions"] == ["clamp"] and clamp["digest"]
    assert verify_record(a["brassier"]) is True
    tampered = copy.deepcopy(a["brassier"])
    tampered["ledger"][2]["verdict"] = "SUPPORTED"  # a withdrawn claim quietly restored
    assert verify_record(tampered) is False
    dropped = copy.deepcopy(a["brassier"])
    dropped["ledger"][2]["evidence"] = [x for x in dropped["ledger"][2]["evidence"] if x["outcome"] != "contradicts"]  # a negative result removed
    assert verify_record(dropped) is False


def test_the_standard_comparison_is_reported_beside_the_ledger_and_ties_where_the_ledger_records_the_equivalence():
    out = demo.demo_ledger()
    std = out["standard_comparison_clamp_vs_free_passive"]
    assert abs(std["models"]["M1"]["rss"] - std["models"]["M2"]["rss"]) < 1e-9  # identical predictions under passive observation
    assert std["models"]["M1"]["BIC"] < std["models"]["M2"]["BIC"]  # the criteria separate them only by the parameter count, not by the data
    s = standard_comparison(np.arange(10.0), {"a": np.arange(10.0), "b": np.arange(10.0) + 1}, {"a": 1, "b": 1})
    assert s["preferred_by_AIC"] == "a"


def test_the_verification_route_serves_the_demo_ledger_with_an_intact_seal_and_refuses_a_public_runtime(monkeypatch):
    import dataclasses

    from fastapi.testclient import TestClient

    from xzr.service import studies
    from xzr.service.app import app

    c = TestClient(app)
    r = c.get("/api/verification/brassier/demo")
    assert r.status_code == 200
    body = r.json()
    assert body["seal_intact"] is True and {e["verdict"] for e in body["brassier"]["ledger"]} == {"SUPPORTED", "WITHHELD", "WITHDRAWN"}
    monkeypatch.setattr(studies, "LIMITS", dataclasses.replace(studies.LIMITS, public=True))
    assert c.get("/api/verification/brassier/demo").status_code == 403


def test_the_verification_layer_is_excluded_from_the_ios_and_browser_bundles():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "ios" / "scripts" / "stage_engine.py").read_text()
    assert '"verification"' in src and 'Path("service") / "verification.py"' in src
