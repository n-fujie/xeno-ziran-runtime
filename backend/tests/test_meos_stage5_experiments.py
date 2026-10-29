"""MEOS-0, fifth stage: the building blocks of experiments G–K, and the integrity of their saved results.

The blocks are run on single cases whose answers the earlier stages or the first runs established; the saved file is checked for completeness (every experiment carries its seeds, conditions,
manipulated and measured variables, nulls, failures, unexpected outcomes and limit) and for internal consistency. Null results and counter-examples are required to be *kept*."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xzr.meos import analysis as A
from xzr.meos import engine as E
from xzr.meos import mfs5 as M
from xzr.meos import routes5 as R
from xzr.meos import stage5_experiments as X5

SAVED = Path(__file__).resolve().parents[2] / "docs" / "ecosystem" / "experiments_stage5.json"
FRAME = {"experiment", "seeds", "fixed_conditions", "manipulated_variable", "measured_variables", "rows", "null_results", "failures", "unexpected", "interpretation_limit"}


# ---------------------------------------------------------------------------------------------------- M2 substitution (G)
def test_history_off_collapses_alone_and_direct_m2_replaces_it_at_the_default_cell_but_not_at_scale_1_15():
    off_none = X5._g1_job(("OFF", "none", 1.0, 1.0, "normal", 1.0, 1))
    off_direct = X5._g1_job(("OFF", "direct", 1.0, 1.0, "normal", 1.0, 1))
    on_none = X5._g1_job(("ON", "none", 1.0, 1.0, "normal", 1.0, 1))
    assert (on_none[7], off_none[7], off_direct[7]) == (True, False, True)
    assert X5._g1_job(("OFF", "direct", 1.15, 1.0, "normal", 1.0, 1))[7] is False  # the substitution is conditional on the cell


def test_the_restoring_and_the_compensating_rescues_are_told_apart():
    r = [
        {"failing_cell": {}, "change": {"history": ["OFF", "ON"]}, "after": 5, "n": 5},
        {"failing_cell": {}, "change": {"resource": ["normal", "oversupplied"]}, "after": 5, "n": 5},
        {"failing_cell": {}, "change": {"m2": ["none", "direct"]}, "after": 5, "n": 5},
        {"failing_cell": {}, "change": {"renewal": ["reduced", "normal"]}, "after": 5, "n": 5},
    ]
    c = X5.compensations(r)
    assert c["restoring"] == 2 and c["compensating"] == 2 and set(c["compensating_by_factor_and_change"]) == {"resource", "m2"}


# ---------------------------------------------------------------------------------------------------- dynamic Address (H)
def test_collision_and_stale_stay_strict_nulls_in_the_default_arrangement_and_loss_still_collapses():
    arr = {"id": "x", "a2x": 5, "a2y": 6, "speed": 1.0, "a2r": 2, "a1r": 2}
    for fault in ("collision", "stale (30 ticks)"):
        assert not X5._h_job((arr, fault, "A2", 100, 1))["dynamics_changed"]
    loss = X5._h_job((arr, "loss", "A2", 100, 1))
    assert loss["collapsed"] and loss["dynamics_changed"] and loss["control_active"]


def test_an_arrangement_screen_measures_separation_and_motion_on_the_control():
    near = X5._h_screen_job((5, 6, 1.0, 2, 2, 1))
    assert near["active"] and near["separation_after_60"] == 0.0  # A2 walks to A1's cell
    far = X5._h_screen_job((9, 6, 1.0, 2, 2, 1))
    assert not far["active"] and far["separation_after_60"] > 0  # apart, and the operation does not persist


def test_crossing_two_configurations_that_share_a_cell_changes_nothing():
    arr = {"id": "x", "a2x": 5, "a2y": 6, "speed": 1.0, "a2r": 2, "a1r": 2}
    r = X5._h_swap_job((arr, 100, 1))
    assert r["positions_differ"] is False and not r["dynamics_changed"]


# ---------------------------------------------------------------------------------------------------- SSS mapping (J)
def test_the_sss_region_of_an_mfs_is_computed_with_the_definitions_of_the_earlier_stage():
    cond = M.conditions_f()[0]
    base = R.sss_point(cond, frozenset(["A2", "interaction_channel", "sensor_resource", "sensor_alteration", "environmental_persistence", "feedback", "resource_renewal"]), 1.0, 1.0, 1.0)
    assert base["region"] in ("ACTIVE", "OBSERVATION-SENSITIVE") and base["class"] == "ACTIVE"
    far = R.sss_point(cond, frozenset(["A2", "interaction_channel", "sensor_resource", "sensor_alteration", "environmental_persistence", "feedback", "resource_renewal"]), 2.0, 1.0, 1.0)
    assert far["class"] == "COLLAPSED" and far["region"] in ("COLLAPSED", "RECOVERY-CAPABLE")


# ---------------------------------------------------------------------------------------------------- observation robustness (K)
def test_an_mfs_that_keeps_the_operation_can_still_be_unobservable_and_the_scores_are_separate():
    cond = M.conditions_f()[0]
    ret = frozenset(["A2", "interaction_channel", "sensor_resource", "sensor_alteration", "environmental_persistence", "feedback", "resource_renewal"])
    p = R.profile(cond, ret)
    assert p["preserved_operation"] == 1.0 and 0.0 <= p["observational_robustness"] < 1.0  # operation kept; the observer disagrees under some of the settings
    rec = E.run_record(M._config(cond, 6, 240), M.retained_interventions(cond, ret))
    o = A.observe(rec, {"sampling_interval": 3})
    assert o["operational_state"] == "ACTIVE" and o["observed_state"] != "ACTIVE" and o["observability"]["observed_collapse_is_artifact"]  # unobservable, not collapsed
    assert {"perturbation_sensitivity", "observational_robustness", "address_dependence", "recovery"} <= set(p)  # operational, observational, address and recovery measures are separate entries


# ---------------------------------------------------------------------------------------------------- the saved results
@pytest.fixture(scope="module")
def saved():
    if not SAVED.exists():
        pytest.skip("the fifth-stage experiments have not been run")
    return json.loads(SAVED.read_text())


def test_every_experiment_is_saved_with_its_frame_and_keeps_its_nulls(saved):
    ex = saved["experiments"]
    assert set(ex) >= set("FGHIJK") and saved["baseline_result_digest"] == "b4cf1e522e8bee460eab30ee2a3f86ffd703a3f7969dc21271cf0240aa09adc5"
    for k, e in ex.items():
        assert set(e) >= FRAME, k
        assert e["seeds"] and e["rows"] and e["interpretation_limit"] and isinstance(e["null_results"], list) and isinstance(e["failures"], list)
    assert ex["F"]["null_results"] and ex["H"]["null_results"] and ex["I"]["null_results"]  # nulls were found and were kept


def test_multiple_mfs_are_reported_with_their_counter_evidence(saved):
    f = saved["experiments"]["F"]
    counts = [r["minimal_sets"] for r in f["rows"]]
    assert max(counts) >= 1 and f["conditions_with_more_than_one_mfs"] == [r["condition"] for r in f["rows"] if r["minimal_sets"] > 1]
    assert any(c == 1 for c in counts), "the conditions with one dominant MFS are in the file"
    assert any(r["persisting_subsets"] == 0 for r in f["rows"]) and any("no retaining set" in n for n in f["null_results"])  # a condition without any MFS is kept as a null
    for e in f["route_equivalence"]:
        assert e["verdict"].startswith(("operationally equivalent", "not equivalent")) and 0 <= e["equivalent_through_level"] <= 4


def test_the_stage_four_strict_nulls_are_kept_in_experiment_h(saved):
    h = saved["experiments"]["H"]
    assert h["stage4_strict_nulls_reproduced"] and all(x["class"].startswith("null") for x in h["stage4_strict_nulls_reproduced"])
    assert h["summary_by_class"]["null"] > 0 and h["arrangements_screened"]


def test_every_reconfiguration_cell_has_its_no_reconfiguration_control_and_replays(saved):
    i = saved["experiments"]["I"]
    scen = {r["scenario"] for r in i["rows"]}
    for s in scen:
        assert any(r["scenario"] == s and r["controller"] == "none" for r in i["rows"]), s
    assert i["all_replays_identical"] is True and i["runs"] == len(scen) * len(X5.CONTROLLERS) * len(i["seeds"])
    assert {"persisted", "collapsed", "mean_switching_cost", "false_switches", "unnecessary_switches"} <= set(i["rows"][0])


def test_each_mfs_has_an_sss_island_and_four_separate_robustness_scores(saved):
    ids = {m["id"] for r in saved["experiments"]["F"]["by_condition"].values() for m in r["mfs"]}
    j, k = saved["experiments"]["J"], saved["experiments"]["K"]
    assert {r["mfs"] for r in j["rows"]} == ids and {r["mfs"] for r in k["rows"]} == ids
    for r in k["rows"]:
        assert {"operational_robustness", "observational_robustness", "addressability", "recoverability"} <= set(r)


def test_the_substitution_classes_follow_the_stated_rule(saved):
    g = saved["experiments"]["G"]
    n = 10
    for row in g["rows"]:
        for m in ("direct", "delayed(3)", "noisy(0.05)", "threshold(0.05)"):
            cls = row[f"class_{m}"]
            if row["ON_none"] >= 0.8 * n and row["OFF_none"] <= 0.2 * n:
                assert cls.startswith("history needed"), (row, m)
                assert (row[f"OFF_{m}"] >= 0.8 * n) == cls.endswith("M2 substitutes")
            if row["OFF_none"] >= 0.8 * n:
                assert cls == "history not needed here"
