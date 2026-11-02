"""MEOS-0, fifth stage, final reading: the classes of conditions, the status of candidate sets, the roles of components, the equivalence classes, the reconfiguration verdicts and the Holm
correction are tested on small hand-made inputs, and the saved ``final`` block is checked against the raw results it was derived from."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xzr.meos import stage5_final as FN

SAVED = Path(__file__).resolve().parents[2] / "docs" / "ecosystem" / "experiments_stage5.json"


def ca(validated=0, rejected=0, near=0):
    return {"validated": validated, "rejected": [{}] * rejected, "near_misses": [{}] * near, "candidates": []}


def test_condition_classes_follow_the_stated_rule():
    assert FN.condition_class(ca()) == "NO_MFS"
    assert FN.condition_class(ca(rejected=1)) == "UNSTABLE_CANDIDATE"
    assert FN.condition_class(ca(validated=1)) == "SINGLE_MFS"
    assert FN.condition_class(ca(validated=1, rejected=1)) == "SINGLE_MFS"  # a rejected candidate does not make a second MFS
    assert FN.condition_class(ca(validated=2)) == "MULTIPLE_MFS"
    assert FN.condition_class(ca(validated=1, near=1)) == "INCONCLUSIVE"


def test_holm_correction():
    assert FN.holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]
    assert FN.holm([0.5]) == [0.5] and all(a >= p for a, p in zip(FN.holm([0.001, 0.2, 0.04]), [0.001, 0.2, 0.04], strict=True))


def row(scenario, controller, k, n=10, cost=1.0, p=1.0):
    return {"scenario": scenario, "controller": controller, "n": n, "persisted": {"k": k, "n": n}, "mean_switches": 1.0, "mean_switching_cost": cost, "false_switches": 0, "unnecessary_switches": 0,
            "vs_none_persistence": {"fisher_exact_p": p, "cohens_h": 1.0}, "vs_none_energy_paired": {"median_difference": 0.0}}


def test_a_switch_is_not_a_success_and_the_verdict_needs_a_better_outcome_than_the_control():
    i = {"rows": [row("s1", "none", 0), row("s1", "fixed", 5, p=0.03), row("s1", "adaptive", 0, p=1.0), row("s2", "none", 6), row("s2", "adaptive", 1, p=0.02), row("s2", "fixed", 6, p=1.0)]}
    out = {(v["scenario"], v["controller"]): v for v in FN.reconfiguration_verdicts(i)["verdicts"]}
    assert out[("s1", "fixed")]["verdict"] == "effective" and out[("s1", "adaptive")]["verdict"] == "no effect" and out[("s1", "adaptive")]["route_switch_occurred_in_runs"]  # switched, no effect
    assert out[("s2", "adaptive")]["verdict"] == "harmful" and out[("s2", "fixed")]["verdict"] == "no effect"
    assert out[("s1", "fixed")]["holm_p_over_all_comparisons"] > out[("s1", "fixed")]["fisher_p_unadjusted"] and out[("s1", "fixed")]["survives_correction"] is False  # a result that does not survive the correction says so
    costly = {"rows": [row("s1", "none", 0), row("s1", "fixed", 8, cost=5.0, p=0.001)]}
    assert FN.reconfiguration_verdicts(costly)["verdicts"][0]["verdict"] == "no effect"  # cost not acceptable


def test_equivalence_classes_never_rest_on_active_alone():
    ok = {"recovery": {"testable": True}}
    assert FN.equivalence_class({"equivalent_through_level": 4}, ok, ok) == "equivalent at tested preservation level"
    assert FN.equivalence_class({"equivalent_through_level": 3}, ok, ok) == "partially equivalent"
    assert FN.equivalence_class({"equivalent_through_level": 1}, ok, ok) == "non-equivalent"
    assert FN.equivalence_class({"equivalent_through_level": 4}, ok, {"recovery": {"testable": False}}) == "insufficient evidence"


def test_the_roles_prefer_compensatory_over_necessary_where_the_component_is_redundant_under_the_condition_degraded():
    res = {"universe": ["history"], "classification": {"components": {"history": {"labels": ["necessary"]}}}}
    across = {"history": {"compensatory": [{"needed_under": "F8", "redundant_under": "F3"}]}}
    assert FN.role("F8", "history", res, across) == "compensatory" and FN.role("F12", "history", res, across) == "necessary"
    assert FN.role("F7", "m2_tap", res, across).startswith("not available")


@pytest.fixture(scope="module")
def final():
    if not SAVED.exists() or "final" not in json.loads(SAVED.read_text()):
        pytest.skip("experiments are not finalised")
    return json.loads(SAVED.read_text())


def test_the_final_table_lists_every_condition_with_search_and_validation_kept_apart(final):
    t = final["final"]["F_table"]
    assert [r["condition_id"] for r in t] == [f"F{n}" for n in range(1, 17)]
    for r in t:
        assert r["search_seeds"] == [1, 2, 3, 4, 5] and r["validation_seeds"] == [6, 7, 8, 9, 10] and not set(r["search_seeds"]) & set(r["validation_seeds"])
        assert r["classification"] in ("NO_MFS", "SINGLE_MFS", "MULTIPLE_MFS", "UNSTABLE_CANDIDATE", "INCONCLUSIVE")
        assert {"history_role", "m2_role", "address_role", "coupling_role", "resource_role", "renewal_role", "sss_region_default_setting", "observational_robustness"} <= set(r)
    for c in final["final"]["candidates"].values():
        for x in c["candidates"]:
            assert set(x["search_seeds"]).isdisjoint(x["validation_seeds"]) and x["status"] in ("validated", "failed the search criterion", "failed validation", "near miss")


def test_the_stated_headline_results_hold_in_the_saved_file(final):
    f = final["final"]
    cls = {r["condition_id"]: r["classification"] for r in f["F_table"]}
    assert cls["F9"] == "NO_MFS" and cls["F14"] == "MULTIPLE_MFS" and cls["F8"] == "SINGLE_MFS"  # F8's second candidate is not counted as an MFS
    assert [c["condition_id"] for c in f["F_table"] if c["classification"] == "MULTIPLE_MFS"] == ["F14"]
    roles = {r["condition"]: r["role"] for r in f["history_role"]}
    assert roles["F8"] == roles["F10"] == roles["F16"] == "compensatory" and roles["F12"] == "necessary"
    f8 = f["F8_candidate_rejection"]["candidates_and_status"]
    assert any(c["status"] == "failed the search criterion" and "resource_gradient" in c["retained"] for c in f8) and any(c["status"] == "validated" for c in f8)
    assert "no validated inclusion-minimal retaining set" in f["F9_no_mfs"]["statement"] and f["F9_no_mfs"]["persisting_subsets_in_search"] == 0
    assert "did not sustain a long-lived spatially separated configuration" in f["address"]["statement"] and "not a finding that Address is unnecessary" in f["address"]["not_concluded"]
    assert f["sss_x_mfs"]["active_only_points"] == 0 and "all ACTIVE points were also observation-sensitive" in f["sss_x_mfs"]["statement"]


def test_adaptive_and_fixed_are_reported_apart_and_the_failure_stands(final):
    r = final["final"]["reconfiguration"]
    by = r["by_controller"]
    assert by["adaptive"]["effective"] == 0 and by["adaptive_shed"]["effective"] == 0 and by["fixed"]["effective"] == 1
    fx = [v for v in r["verdicts"] if v["controller"] == "fixed" and v["verdict"] == "effective"]
    assert len(fx) == 1 and fx[0]["scenario"] == "history lost" and fx[0]["survives_correction"] is False
    c = final["final"]["fixed_fallback_confirmation"]
    assert c["persisted"]["adaptive"]["k"] == 0 and c["persisted"]["adaptive_shed"]["k"] == 0 and c["persisted"]["fixed"]["k"] > c["persisted"]["none"]["k"]  # the fixed fallback's benefit is on fresh seeds; the adaptive one's absence too
    assert set(c["seeds"]).isdisjoint(set(range(1, 11)))


def test_f14_claims_route_non_equivalence_only_when_both_sets_persist_in_every_validation_seed(final):
    c = final["final"]["F14_comparison"]
    assert c["same_cardinality"] and all(s["persists"] == 5 for s in c["stability"].values())
    assert c["claim"].startswith("route non-equivalence") and c["equivalence"]["equivalent_through_level"] < 4
    assert any(r["differs"] for r in c["rows"])


def test_the_adaptive_controller_did_not_act_because_the_matched_mfs_was_already_enabled():
    """The saved diagnosis of the adaptive controller's own log: outside 'renewal disabled' its first decision was always 'already wholly enabled' and it never switched."""
    d = json.loads((Path(__file__).resolve().parents[2] / "docs/ecosystem/experiments_stage5_adaptive_diagnosis.json").read_text())
    rows = {r["scenario"]: r for r in d["rows"]}
    assert len(rows) == 6
    for scen, r in rows.items():
        if scen == "renewal disabled":
            assert r["first_decision"] == {"switch": 10} and r["switches"] == 10
        else:
            assert r["first_decision"] == {"already wholly enabled (cost 0, no action)": 10} and r["switches"] == 0
    assert "not a finding that reconfiguration cannot help" in d["limit"]
