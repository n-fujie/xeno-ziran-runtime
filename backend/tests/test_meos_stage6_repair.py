"""Stage 6: world-state repair. Every test runs the real engine; none adjusts an outcome toward an expectation."""

from __future__ import annotations

import pytest

from xzr.meos import engine as E
from xzr.meos import repair6 as R
from xzr.meos import repair_ctl as RCTL
from xzr.meos import repair_events as RE
from xzr.meos import stage6_experiments as S6

COUPLING, RESOURCE, RENEW_EFF, RENEW_STOP, ADDRESS, HISTORY = (R.STRESSES[k] for k in R.STRESSES)


def outcome(stress: R.Stress, parts: list[tuple[str, float, int]], t: int, seed: int = 1) -> dict:
    reps: list[dict] = []
    for a, m, d in parts:
        reps += R.build_action(a, stress, m, t, d)
    return R.run_eval(stress, sorted(reps, key=lambda i: i["tick"]), seed, t)["horizons"]


def ok(h: dict, t: int = R.T_ACT) -> bool:
    """Effective: success at every horizon applicable to the action tick (the short horizon is not applicable after tick 120)."""
    app = R.horizons_applicable(t)
    return all(v["success"] for k, v in h.items() if app[k])


def test_the_action_space_names_what_the_main_experiments_could_not_do_and_never_runs_it():
    for aid in ("coupling.bypass", "resource.rerouting", "address.temporary_local"):
        assert R.ACTIONS[aid].status == "not implemented" and R.ACTIONS[aid].note and aid not in R.RUNNABLE  # the frozen Stage 6 registry: the main experiments could not build them
        assert R.FOLLOWUP[aid].status == "implemented" and R.build_action(aid, COUPLING, 1.0, 113, 30)  # the follow-up (engine meos-0.5) builds them in its own registry
    with pytest.raises(ValueError):
        R.build_action("observation.sampling", COUPLING, 1.0, 113)  # an observation repair is never an action of a run
    assert R.ACTIONS["resource.redistribute"].status == "proxy" and "proxy" in R.ACTIONS["resource.redistribute"].note
    assert {R.ACTIONS[a].klass for a in R.ACTIONS} == {"A", "B", "C"}  # internal reconfiguration, world-state repair and observation repair are three different things


def test_no_repair_collapses_every_stress():
    for st in R.STRESSES.values():
        h = R.run_eval(st, [], 1)["horizons"]
        assert not any(v["success"] for v in h.values()), st.id


def test_coupling_restoration_alone_works_only_early_and_a_pulse_works_later():
    assert ok(outcome(COUPLING, [("coupling.restore", 1.0, 0)], 104), 104)
    assert not ok(outcome(COUPLING, [("coupling.restore", 1.0, 0)], 113))  # restoring the original parameter alone does not restore the system once the damage has set in
    assert ok(outcome(COUPLING, [("resource.pulse", 1.0, 0)], 113))  # the repair site is not the damage site


def test_minimum_effective_coupling_restoration_is_a_partial_one():
    assert ok(outcome(COUPLING, [("coupling.restore", 0.7, 0)], 104))
    assert not ok(outcome(COUPLING, [("coupling.restore", 0.6, 0)], 104))


def test_resource_pulse_is_not_monotone_in_its_size():
    h2, h4 = outcome(COUPLING, [("resource.pulse", 2.0, 0)], 113), outcome(COUPLING, [("resource.pulse", 4.0, 0)], 113)
    assert ok(h2) and h2["long"]["outcome"] == "prevented"
    assert h4["long"]["outcome"] == "secondary collapse" and h4["long"]["secondary_collapse"]  # more is worse: overshoot
    assert not outcome(COUPLING, [("resource.pulse", 0.1, 0)], 113)["long"]["success"]  # too little


def test_renewal_efficiency_is_repaired_only_by_a_prompt_full_restoration():
    assert ok(outcome(RENEW_EFF, [("renewal.restore", 1.0, 0)], 104))
    assert not ok(outcome(RENEW_EFF, [("renewal.restore", 1.0, 0)], 113))
    assert not ok(outcome(RENEW_EFF, [("renewal.restore", 0.7, 0)], 104))  # a partial restoration is not enough here


def test_stopped_renewal_is_not_repaired_by_a_restart_or_a_pulse_alone_but_by_both_at_tick_130():
    assert not ok(outcome(RENEW_STOP, [("renewal.restart", 0.0, 0)], 130))
    assert not ok(outcome(RENEW_STOP, [("resource.pulse", 0.5, 0)], 130))
    assert ok(outcome(RENEW_STOP, [("renewal.restart", 0.0, 0), ("resource.pulse", 0.5, 0)], 130))  # a combined recovery: neither part works alone, so it is not attributed to either


def test_address_repair_alone_is_null_and_its_combination_is_a_near_miss_that_does_not_validate_strictly():
    assert not ok(outcome(ADDRESS, [("address.restore", 0.0, 0)], 113))
    assert not ok(outcome(ADDRESS, [("address.reassign", 0.0, 0)], 113))
    rows = [S6._cjob(("Address partial 0.5", (("address.restore", 0.0, 0), ("resource.pulse", 1.0, 0)), 113, sd)) for sd in (1, 6)]
    assert S6.effective([rows[0]]) and not S6.effective([rows[1]])  # seed 1 recovers, seed 6 collapses secondarily: a candidate that failed strict validation is kept, not dropped


def test_the_m2_tap_repairs_history_lost_at_113_and_not_later_a_timing_window():
    assert ok(outcome(HISTORY, [("internal.m2_tap", 0.0, 0)], 113))
    assert not ok(outcome(HISTORY, [("internal.m2_tap", 0.0, 0)], 130))
    assert ok(outcome(HISTORY, [("internal.m2_tap", 0.0, 0), ("resource.pulse", 1.0, 0)], 120))  # the pair extends the window (neither part alone works at 120)
    assert not ok(outcome(HISTORY, [("internal.m2_tap", 0.0, 0)], 120)) and not ok(outcome(HISTORY, [("resource.pulse", 1.0, 0)], 120))


def test_the_stage_5_history_lost_result_holds_under_the_stage_5_criterion():
    rec = R.run(HISTORY, R.build_action("internal.m2_tap", HISTORY, 0.0, 113), 1, 300)
    assert rec["final_status"]["label"] == "ACTIVE"  # stage 5 experiment L: the M2 tap at tick 113, horizon 300, ACTIVE at the end


def test_recovery_is_not_a_flash_of_active():
    st = ["DEGRADED"] * 100 + ["ACTIVE"] * 10 + ["COLLAPSED"] * 30 + ["ACTIVE"] * 40 + ["DEGRADED"] * 20
    o = R.outcome_at(st, len(st), 100)
    assert not o["success"]  # ACTIVE at 100-110 is shorter than W: it is not a stretch; the end is DEGRADED
    st2 = ["DEGRADED"] * 100 + ["ACTIVE"] * 40 + ["COLLAPSED"] * 30 + ["ACTIVE"] * 60
    o2 = R.outcome_at(st2, len(st2), 100)
    assert o2["secondary_collapse"] and not o2["success"]  # a collapse after a sustained stretch is a secondary collapse even if the run is ACTIVE again at the end
    assert R.outcome_at(["DEGRADED"] * 100 + ["COLLAPSED"] * 20 + ["ACTIVE"] * 80, 200, 100)["outcome"] == "recovered"
    assert R.outcome_at(["DEGRADED"] * 100 + ["ACTIVE"] * 100, 200, 100)["outcome"] == "prevented"


def test_costs_are_raw_normalised_and_unweighted():
    o = R.run_eval(COUPLING, R.build_action("resource.pulse", COUPLING, 1.0, 113), 1)
    assert set(o["costs"]["raw"]) == {"energy_use", "resource_mass", "switching", "persistence_energy_rate", "collateral"} and o["costs"]["raw"]["switching"] == 1
    assert set(o["costs"]["normalised"]) == {"energy_use", "resource_mass", "persistence_energy_rate"} and "weighted" not in str(o["costs"])


def test_a_repair_that_has_no_effect_on_the_engine_digest_when_absent():
    cfg = R.config(1, 100)
    assert E.run_record(cfg, R.schedule(None, []))["result_digest"] == E.run_record(cfg, [{"tick": 0, "op": "ROUTE", "m2": {"sense": "none"}}])["result_digest"]
    assert E.run_record(E.default_config(), [])["result_digest"] == "b4cf1e522e8bee460eab30ee2a3f86ffd703a3f7969dc21271cf0240aa09adc5"


def test_a_controller_that_senses_nothing_does_nothing_in_a_run_with_no_stress():
    for kind in ("fixed", "rule_based", "cost_aware", "delayed", "noisy"):
        if kind == "noisy":
            continue  # a noisy detector is allowed to see a stress that is not there: tested separately
        rec = RCTL.run_repaired(R.config(1, 300), R.schedule(None, []), RCTL.RepairController(kind, [], seed=1))
        assert rec["controller"]["attempts"] == 0 and rec["final_status"]["label"] == "ACTIVE", kind


def test_a_controller_acts_on_what_it_senses_logs_why_and_replays_without_itself():
    ctl = RCTL.RepairController("rule_based", [], seed=1)
    base = R.schedule(HISTORY, [])
    rec = RCTL.run_repaired(R.config(1, 300), base, ctl)
    log = rec["controller"]["log"]
    assert log and {"detected", "available", "rejected", "selected", "estimated_cost", "expected_recovery", "actual"} <= set(log[0])
    assert log[0]["selected"] == "rule: M2 tap" and log[0]["class"] == "A"  # a rule: history lost -> the M2 tap, an internal reconfiguration, labelled as one
    assert rec["final_status"]["label"] == "ACTIVE"
    replay = E.run_record(R.config(1, 300), rec["interventions"])
    assert replay["result_digest"] == rec["result_digest"]  # the recorded schedule, the injected interventions included, replays the same run


def test_a_detected_stress_with_no_available_action_is_logged_not_hidden():
    rec = RCTL.run_repaired(R.config(1, 300), R.schedule(ADDRESS, []), RCTL.RepairController("cost_aware", [], seed=1))
    log = rec["controller"]["log"]
    assert log and log[0]["selected"] is None and log[0]["note"] and rec["controller"]["attempts"] == 0


def test_repair_events_come_from_the_run():
    h = R.build_action("resource.pulse", COUPLING, 4.0, 113)
    rec = R.run(COUPLING, h, 1)
    ev = RE.build(COUPLING, 100, [{"action": "resource.pulse", "magnitude": 4.0, "duration": 0, "t": 113}], rec, R.evaluate(rec, R.reference(1), h, 113), None, 120)
    kinds = [e["kind"] for e in ev["events"]]
    assert {"stress-onset", "repair-action", "overshoot", "secondary-collapse", "irreversible"} <= set(kinds)
    assert all(e["source"] for e in ev["events"]) and ev["evaluation"]["horizons"]["long"]["secondary_collapse"]


def test_classification_of_repairability():
    assert S6.classify_repairability(True, False, False, False) == "internally reconfigurable"
    assert S6.classify_repairability(False, True, False, False) == "externally repairable"
    assert S6.classify_repairability(True, False, True, False) == "both"
    assert S6.classify_repairability(False, False, False, True) == "inconclusive"
    assert S6.classify_repairability(False, False, False, False).startswith("neither")
