"""Stage 5, experiment L: actions that survive a stress in mid-run."""

from __future__ import annotations

from xzr.meos import midrun as ML
from xzr.meos import reconf as RC


def test_the_stress_removes_a_component_no_action_can_restore():
    assert "history" not in ML.free_components("history lost") and "feedback" not in ML.free_components("renewal disabled")
    assert "history" in ML.free_components("resource reduced")
    assert "m2_tap" not in ML.enabled_before("resource reduced") and "m2_tap" in ML.free_components("resource reduced")  # installed, dormant


def test_an_action_leaves_exactly_the_retained_set_enabled_at_the_action_tick():
    scen = "resource reduced"
    keep = ML.enabled_before(scen)
    assert ML.action_interventions(scen, keep) == []  # no action: nothing changes
    ivs = ML.action_interventions(scen, keep - {"history"} | {"m2_tap"})
    assert {"tick": ML.T_ACT, "op": "REMOVE", "target": "history"} in ivs
    assert any(i["op"] == "ROUTE" and i["m2"]["sense"] == "direct" and i["tick"] == ML.T_ACT for i in ivs)
    assert ML.cost_of(scen, keep) == 0 and ML.cost_of(scen, keep - {"history"} | {"m2_tap"}) == 2


def test_no_action_collapses_and_switching_the_m2_tap_on_persists_when_history_is_lost():
    scen = "history lost"
    assert ML.persists(scen, None, (1, 2)) == (False, False)
    assert ML.persists(scen, ML.enabled_before(scen) | {"m2_tap"}, (1, 2)) == (True, True)  # the one action found by the exhaustive search


def test_the_mid_run_controller_can_shed_and_enable_to_reach_its_action():
    entry = {"id": "MID-x", "condition_id": "mid-run", "features": {"history": "ok", "coupling": "weak", "resource": "reduced", "renewal": "normal", "address": "ok", "tap": "direct"}, "retained": ["A2", "m2_tap"], "cardinality": 2}
    ctl = RC.Controller("adaptive_mid", [entry], ML.ARRANGEMENT)
    sensed = {"history": "ok", "coupling": "weak", "resource": "reduced", "renewal": "normal", "address": "ok"}
    cands = ctl._match(sensed, ML.UNIVERSE, ML.enabled_before("resource reduced"))["candidates"]
    assert cands[0]["enable"] == ["m2_tap"] and set(cands[0]["shed"]) == ML.enabled_before("resource reduced") - {"A2"}
    assert RC.Controller("adaptive", [entry], ML.ARRANGEMENT)._match(sensed, ML.UNIVERSE, ML.enabled_before("resource reduced"))["candidates"][0]["shed"] == []  # the original adaptive controller never sheds


def _saved() -> dict:
    import json
    from pathlib import Path

    return json.loads((Path(__file__).resolve().parents[2] / "docs/ecosystem/experiments_stage5_midrun.json").read_text())


def test_saved_existence_result_one_stress_has_an_action_and_five_have_none():
    d = _saved()
    r = d["L1_existence"]
    assert r["history lost"]["persisting_on_all_search_seeds"] == 1 and r["history lost"]["any_validated"] and r["history lost"]["no_action_persists_on_search_seeds"] is False
    assert r["history lost"]["cheapest_persisting_sets"][0]["validation_persists"] == "5/5" and "m2_tap" in r["history lost"]["cheapest_persisting_sets"][0]["retained"]
    for scen in ML.STRESSES:
        if scen != "history lost":
            assert r[scen]["best_search_seeds_persisted"] == 0 and r[scen]["persisting_on_all_search_seeds"] == 0  # not one set of component states keeps the operation on even one seed
            assert sum(r[scen]["sets_by_search_seeds_persisted"].values()) == r[scen]["sets_tested"]


def test_saved_controller_result_only_the_one_scenario_with_an_action_is_helped_and_nothing_misfires():
    d = _saved()
    eff = {(v["scenario"], v["controller"]) for v in d["L3_verdicts"] if v["verdict"] == "effective"}
    assert eff == {("history lost", "fixed"), ("history lost", "adaptive_mid")}
    assert all(v["survives_holm"] for v in d["L3_verdicts"] if v["verdict"] == "effective")
    assert not any(v["verdict"] == "harmful" for v in d["L3_verdicts"])
    for r in d["L3_controller"]["rows"]:
        if r["scenario"].startswith("no stress"):
            assert r["mean_switches"] == 0 and r["persisted"]["k"] == r["persisted"]["n"]  # no false switch and no harm without a stress
    assert d["seeds"]["search"] == [1, 2, 3, 4, 5] and d["seeds"]["validation"] == [6, 7, 8, 9, 10]  # the three seed sets are kept apart
