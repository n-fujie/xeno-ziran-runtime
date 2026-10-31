"""TEOO Phase 3: the total-observation relation layer and Open Revision. A configuration says what could be observed of declared targets; its history can be replayed at any time; a revision records what it lost and gained."""

from __future__ import annotations

import copy

import pytest

from xzr.teoo import observation as OB
from xzr.teoo import revision as RV
from xzr.teoo import session as SE


def sens(sid="s", channels=("angle",), **kw):
    base = dict(resolution=1.0, sampling_period_s=0.02, window_s=20.0, detection_limit=0.1, penetration=0.5)
    base.update(kw)
    return OB.sensor(sid, list(channels), **base)


def tgt(tid="t", **kw):
    base = dict(scale=2.0, phenomenon_period_s=2.0, amplitude=10.0, opacity=0.0)
    base.update(kw)
    return OB.target_spec(tid, "angle", **base)


def cfg(sensors, **kw):
    return OB.new_configuration(sensors, **kw)


def test_every_observation_limit_is_found_from_the_declared_conditions():
    c = cfg([sens()])
    assert OB.assess_target(c, tgt(), 0)["status"] == "MEASURED_VALID"
    assert OB.assess_target(c, tgt(scale=0.5), 0)["status"] == "SCALE_MISMATCH"
    assert OB.assess_target(c, tgt(phenomenon_period_s=0.02), 0)["status"] == "TIME_WINDOW_MISMATCH"
    assert OB.assess_target(c, tgt(opacity=0.9), 0)["status"] == "BOUNDARY_INVISIBLE"
    assert OB.assess_target(c, tgt(amplitude=0.01), 0)["status"] == "SIGNAL_BELOW_THRESHOLD"
    assert OB.assess_target(c, OB.target_spec("e", "emg", scale=1, phenomenon_period_s=1, amplitude=1, opacity=0), 0)["status"] == "UNMEASURABLE"
    several = OB.assess_target(c, tgt(scale=0.5, phenomenon_period_s=0.02, opacity=0.9), 0)
    assert set(several["causes"]) == {"SCALE_MISMATCH", "TIME_WINDOW_MISMATCH", "BOUNDARY_INVISIBLE"} and several["status"] == "BOUNDARY_INVISIBLE"


def test_a_sensor_failure_a_spent_budget_an_overwritten_sample_and_a_dead_link_have_their_own_reasons():
    assert OB.assess_target(cfg([sens(health=0.0)]), tgt(), 0)["detail"] == ["sensor s has failed"]
    worn = OB.assess_target(cfg([sens(health=0.25)]), tgt(amplitude=0.3), 0)  # the detection limit rises as the sensor wears: 0.1 / 0.25 = 0.4 > 0.3
    assert worn["status"] == "SIGNAL_BELOW_THRESHOLD" and any("detection limit is raised" in d for d in worn["detail"])
    spent = cfg([sens(cost_per_s=1.0)], resources={"energy_budget": 5.0})
    assert OB.assess_target(spent, tgt(), 2)["status"] == "MEASURED_VALID" and OB.energy_remaining(spent, 2) == 3.0
    late = OB.assess_target(spent, tgt(), 9)
    assert late["status"] == "UNMEASURED" and "budget is spent" in late["detail"][-1]  # could be measured; is not
    overwritten = OB.assess_target(cfg([sens()], memory={"buffer_s": 1.0, "retrieval_delay_s": 5.0}), tgt(), 0)
    assert overwritten["status"] == "MISSING" and overwritten["cause_known"] and "overwritten" in overwritten["detail"][-1]
    down = OB.assess_target(cfg([sens()], couplings={"s:t": {"gain": 1.0, "delay_s": 0.0, "link": False}}), tgt(), 0)
    assert down["status"] == "BOUNDARY_INVISIBLE" and "link is down" in down["detail"][0]
    weak = OB.assess_target(cfg([sens()], couplings={"s:t": {"gain": 0.001, "delay_s": 0.0, "link": True}}), tgt(amplitude=10.0), 0)
    assert weak["status"] == "SIGNAL_BELOW_THRESHOLD"  # a weak coupling lowers what arrives below the limit


def test_a_sensor_that_does_not_reach_a_target_is_not_a_candidate_unless_none_does():
    c = cfg([sens("a", reach=["t1"]), sens("b", reach=["t2"], sampling_period_s=1.0)])
    assert OB.assess_target(c, tgt("t1"), 0)["sensor"] == "a" and OB.assess_target(c, tgt("t2", phenomenon_period_s=0.2), 0)["status"] == "TIME_WINDOW_MISMATCH"  # t2 is judged by b only
    out = OB.assess_target(c, tgt("t3"), 0)
    assert out["status"] == "BOUNDARY_INVISIBLE" and "outside" in " ".join(out["detail"])  # outside every reach


def test_missing_metadata_gives_an_unknown_cause_not_a_guess():
    c = cfg([OB.sensor("s", ["angle"])])
    r = OB.assess_target(c, tgt(), 0)
    assert r["status"] == "UNKNOWN_CAUSE" and r["causes"] == [] and not r["cause_known"] and {"scale", "time_window"} <= set(r["undetermined"])


def test_the_state_of_observation_at_any_time_is_replayed_from_the_history():
    s = SE.build_session()
    hist, specs = s["observation"]["history"], s["observation"]["specs"]
    assert [c["version"] for c in hist] == [1, 2, 3, 4] and [c["at"] for c in hist] == [0.0, 6.0, 10.0, 14.0]
    for t, ver in ((0.0, 1), (5.99, 1), (6.0, 2), (9.0, 2), (10.0, 3), (13.5, 3), (14.0, 4), (1e6, 4)):
        assert OB.state_at(hist, specs, t)["version"] == ver
    a, b = OB.state_at(hist, specs, 0.0), OB.state_at(hist, specs, 20.0)
    assert a["targets"]["tgt.thigh_l"]["status"] == "UNMEASURABLE" and b["targets"]["tgt.thigh_l"]["status"] == "MEASURED_VALID"
    assert OB.state_at(hist, specs, 0.0) == a  # the replay is deterministic
    assert [x["summary"] for x in OB.replay(hist, specs, [0.0, 20.0])] == [a["summary"], b["summary"]]
    ch = OB.observability_changes(hist, specs, "tgt.ankle_l")
    assert [(c["version"], c["status"]) for c in ch] == [(1, "TIME_WINDOW_MISMATCH"), (3, "MEASURED_VALID")]  # where the observability of the ankle changed and which change did it
    assert ch[1]["change"]["op"] == "time_window_change"


def test_the_completeness_reported_is_relative_to_the_declared_targets_and_never_to_the_world():
    st = OB.state_at(SE.build_session()["observation"]["history"], SE.build_session()["observation"]["specs"], 0.0)
    assert st["declared_targets"] == 7 and st["observed"] == 3 and "not the world" in st["note"] and "not an acquisition of the world" in st["claim_note"]
    assert "completeness" not in st and "coverage_of_world" not in st


def test_the_relation_field_keeps_exclusions_and_stays_open_while_a_judgment_changing_relation_is_unobserved():
    f = OB.relation_field("task", [{"id": "a", "dimension": "spatial", "observed": True, "accessible": True, "judgment_changing": True},
                                   {"id": "b", "dimension": "material", "observed": False, "accessible": True, "judgment_changing": None},
                                   {"id": "c", "dimension": "temporal", "observed": False, "accessible": False, "judgment_changing": False},
                                   {"id": "d", "dimension": "causal", "observed": False, "accessible": None, "judgment_changing": True}])
    assert f["observed"] == ["a"] and f["accessible_but_unobserved"] == ["b"] and f["inaccessible"] == ["c"] and f["access_unknown"] == ["d"]
    assert f["judgment_open"] == ["b", "d"] and f["epistemically_open"] and not f["generalisation_allowed"] and f["completeness_claim"] is None  # unknown counts as possible
    closed = OB.relation_field("task", [{"id": "a", "dimension": "spatial", "observed": True}, {"id": "c", "dimension": "temporal", "observed": False, "accessible": False, "judgment_changing": False}])
    assert closed["generalisation_allowed"] and "conditional cross-section" in closed["reading"]
    with pytest.raises(ValueError):
        OB.relation_field("task", [{"id": "x", "dimension": "vibes", "observed": True}])


# ---------------------------------------------------------------------------------------------------- Open Revision
def base_history():
    h = [cfg([sens("a", reach=["t1"]), sens("slow", sampling_period_s=1.0, reach=["t2"])], variables=["v1"], body_version=1)]
    return h, [tgt("t1"), tgt("t2", phenomenon_period_s=0.2), OB.target_spec("t3", "emg", scale=1, phenomenon_period_s=1, amplitude=1, opacity=0)]


CASES = {
    "sensor_change": {"op": "add", "sensor": sens("emg", ("emg",), reach=["t3"])},
    "scale_change": {"sensor": "a", "resolution": 0.2},
    "time_window_change": {"sensor": "slow", "sampling_period_s": 0.05},
    "boundary_change": {"sensor": "a", "reach": ["t1", "t2"], "penetration": 0.9},
    "body_structure_change": {"body_version": 2},
    "coupling_change": {"key": "a:t1", "coupling": {"gain": 0.5}},
    "variable_added": {"variable": "v2"},
    "variable_removed": {"variable": "v1"},
}


@pytest.mark.parametrize("rtype", RV.TYPES)
def test_each_type_of_revision_is_recorded_with_its_reason_versions_and_what_was_lost_and_gained(rtype):
    h, specs = base_history()
    log: list = []
    new, ev = RV.revise(h, specs, rtype, CASES[rtype], reason="a stated reason", at=5.0, log=log)
    assert len(new) == 2 and new[-1]["version"] == 2 and new[-1]["parent"] == 1 and new[-1]["change"]["op"] == rtype and new[-1]["change"]["reason"] == "a stated reason"
    assert ev["status"] == "recorded" and ev["before_version"] == 1 and ev["after_version"] == 2 and ev["reason"] and log == [ev]
    assert set(ev) >= {"lost", "gained", "changed", "unchanged_count", "body_version_before", "body_version_after", "initiated_by", "autonomous_revision_demonstrated"}
    assert h[0]["version"] == 1 and len(h) == 1  # the earlier history is untouched


def test_what_a_revision_gained_and_lost_is_computed_not_asserted():
    h, specs = base_history()
    _, add = RV.revise(h, specs, "sensor_change", CASES["sensor_change"], reason="r", at=5.0)
    assert [g["target"] for g in add["gained"]] == ["t3"] and add["gained"][0]["from"] == "UNMEASURABLE" and add["lost"] == []
    _, win = RV.revise(h, specs, "time_window_change", CASES["time_window_change"], reason="r", at=5.0)
    assert [g["target"] for g in win["gained"]] == ["t2"]
    _, worse = RV.revise(h, specs, "scale_change", {"sensor": "a", "resolution": 5.0}, reason="coarser, cheaper sensor", at=5.0)
    assert [x["target"] for x in worse["lost"]] == ["t1"] and worse["lost"][0]["to"] == "SCALE_MISMATCH"  # information was lost, and it is said
    _, same = RV.revise(h, specs, "variable_added", CASES["variable_added"], reason="r", at=5.0)
    assert same["gained"] == [] and same["lost"] == [] and same["unchanged_count"] == 3  # a variable listed does not by itself change what can be observed


def test_a_proposal_creates_no_version_and_a_validated_status_cannot_be_set_here():
    h, specs = base_history()
    log: list = []
    same, ev = RV.revise(h, specs, "sensor_change", CASES["sensor_change"], reason="proposal", at=5.0, status="proposed", log=log)
    assert len(same) == 1 and ev["after_version"] is None and ev["gained"] and "not a physically executed modification" in ev["note"]
    for kw in ({"status": "validated"}, {"initiated_by": "autonomous-agent"}, {"reason": ""}):
        with pytest.raises(ValueError):
            RV.revise(h, specs, "sensor_change", CASES["sensor_change"], **{"reason": "r", "at": 5.0, **kw})
    with pytest.raises(ValueError):
        RV.revise(h, specs, "not_a_type", {}, reason="r", at=5.0)
    assert "validated" in RV.STATUSES


def test_no_event_claims_that_the_apparatus_revised_itself():
    h, specs = base_history()
    log: list = []
    for rtype in RV.TYPES:
        _, ev = RV.revise(h, specs, rtype, CASES[rtype], reason="r", at=5.0, log=log, initiated_by="researcher")
        assert ev["autonomous_revision_demonstrated"] is False
    _, ev = RV.revise(h, specs, "sensor_change", CASES["sensor_change"], reason="r", at=5.0, initiated_by="system")
    assert ev["initiated_by"] == "system" and ev["autonomous_revision_demonstrated"] is False  # a system that initiated a change did not thereby demonstrate autonomous revision


def test_the_revision_log_and_the_versions_agree_on_replay_and_a_broken_log_is_noticed():
    s = SE.build_session()
    hist, specs, log = s["observation"]["history"], s["observation"]["specs"], s["observation"]["revisions"]
    rep = RV.replay_revisions(hist, log, specs)
    assert len(rep) == 3 and all(r["version_ok"] for r in rep) and [e["status"] for e in log] == ["recorded", "recorded", "recorded", "proposed"]
    assert rep[0]["after"] != rep[0]["before"]
    broken = copy.deepcopy(hist)
    broken[1]["change"]["op"] = "scale_change"
    assert not RV.replay_revisions(broken, log, specs)[0]["version_ok"]
