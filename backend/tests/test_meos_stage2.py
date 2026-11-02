"""MEOS-0, second stage: intermediate traces, the factorial and necessity experiments, the restated minimal configurations, operational versus observed state,
boundary experiments, recovery phases, SSS regions, Address Domain interventions, M2 connection and the first Philosophical-AI operations.

Every outcome below is measured by running the engine; none is chosen. Where the model gives a null result, a reversed effect or a conditional one, the test pins
that (and would fail if the engine started to say otherwise). Software checks on a formal model, not evidence about any ecosystem."""

from __future__ import annotations

import itertools

import numpy as np
import pytest
from fastapi.testclient import TestClient

from xzr.meos import analysis as A
from xzr.meos import engine as E
from xzr.meos import experiments as X
from xzr.service import app as app_mod

BASELINE_RESULT_DIGEST = (
    "b4cf1e522e8bee460eab30ee2a3f86ffd703a3f7969dc21271cf0240aa09adc5"  # the unperturbed MEOS-0 run of stage one (meos-0.1)
)


def run(ivs=None, **cfg):
    return E.run_record(E.default_config(**cfg), ivs or [])


@pytest.fixture(scope="module")
def base():
    return run()


# ---------------------------------------------------------------------------------------------------- the baseline was not changed
def test_stage_two_did_not_change_the_baseline_or_its_digest(base):
    assert base["result_digest"] == BASELINE_RESULT_DIGEST  # the same frames, events, cycles, status log, fields as stage one
    assert base["final_status"]["label"] == "ACTIVE" and len(base["cycles"]) == 47
    d = E.default_config()
    for key in ("m2", "phil", "address"):
        assert (
            key not in d
        )  # new features are absent by default, so the input digest of a baseline configuration is unchanged too
    assert "access" not in d["history"] and "renew_efficiency" not in d["environment"]
    assert d["environment"]["gradient"] and d["power"] == {"reserve": 24.0, "capacity": 24.0, "charge": 0.4, "infinite": False}
    assert all("address" not in f for f in base["frames"])  # frames only gain a key when an Address Domain fault is active


def test_the_trace_block_is_separate_and_replays(base):
    assert "traces" in base and base["trace_digest"] and base["full_digest"] and base["trace_digest"] != base["result_digest"]
    again = run()
    assert again["trace_digest"] == base["trace_digest"] and again["full_digest"] == base["full_digest"]
    assert E.replay(base)["identical"] is True
    other = run(seed=2)
    assert other["trace_digest"] != base["trace_digest"]


# ---------------------------------------------------------------------------------------------------- 1. intermediate quantities and the operational basis of the verdict
def test_every_required_intermediate_quantity_is_a_per_tick_series(base):
    T = base["traces"]
    n = len(base["frames"])
    for k in (
        "resource_flow",
        "resource_consumed",
        "resource_renewed",
        "power_reserve",
        "power_balance",
        "power_draw",
        "renewal_events",
        "a1_activity",
        "a2_activity",
        "interaction_strength",
        "history_contribution_a1",
        "history_contribution_a2",
        "sensor_radius_a1",
        "speed_a2",
        "address_integrity_a1",
        "target_margin",
    ):
        assert len(T[k]) == n, k
    assert T["t"] == list(range(n))
    assert np.allclose(
        np.array(T["resource_flow"]), np.array(T["resource_consumed"]) + np.array(T["resource_renewed"]), atol=1e-4
    )
    assert sum(T["renewal_events"]) > 0 and sum(T["resource_renewed"]) > 0


def test_the_power_balance_accounts_for_the_reserve(base):
    T = base["traces"]
    res = np.array(T["power_reserve"])
    step = np.diff(res)
    bal = np.array(T["power_balance"])[1:]
    free = res[1:] < 24.0 - 1e-6  # not clipped at the capacity
    assert np.allclose(
        step[free], bal[free], atol=2e-3
    )  # reserve(t) - reserve(t-1) = recharge - draw, wherever the reserve was not at its ceiling


def test_the_target_margin_is_non_negative_exactly_when_the_operation_is_active(base):
    for rec in (
        base,
        run([{"tick": 100, "op": "REMOVE", "target": "A2"}]),
        run([{"tick": 0, "op": "REMOVE", "target": "history"}]),
    ):
        T = rec["traces"]
        for t, f in enumerate(rec["frames"]):
            assert (T["target_margin"][t] >= 0) == (f["status"] == "ACTIVE"), (t, f["status"], T["target_margin"][t])


def test_the_verdict_never_reads_the_dependency_label(monkeypatch):
    ivs = [{"tick": 100, "op": "REMOVE", "target": "A2"}]
    ref = run(ivs)
    monkeypatch.setattr(E.Run, "_diagnose", lambda self: None)  # the explanation removed altogether
    blind = run(ivs)
    assert [f["status"] for f in blind["frames"]] == [f["status"] for f in ref["frames"]]
    assert blind["cycles"] == ref["cycles"] and blind["traces"] == ref["traces"]
    assert all(s["dependency"] is None for s in blind["status_log"]) and any(s["dependency"] for s in ref["status_log"])


def test_a_collapse_has_a_traceable_path_from_the_intervention_to_the_verdict():
    p = X.causal_path(E.default_config(), [{"tick": 100, "op": "REMOVE", "target": "A2"}])
    assert p["final_operational_state"] == "COLLAPSED"
    steps = p["intermediate_changes"]
    assert steps and all(s["first_departure_tick"] >= 100 for s in steps)
    q = {s["quantity"]: s["first_departure_tick"] for s in steps}
    assert (
        q["a2_activity"] == 100 and q["resource_renewed"] < p["persistence_failure_tick"] < p["collapse_tick"]
    )  # intermediate change, then failure, then the verdict
    assert p["collapse_trigger"]["first_departure_tick"] <= q["resource_renewed"]
    assert (
        p["chain"][0].startswith("intervention at tick 100")
        and "COLLAPSED" in p["chain"][-1]
        and "decided by the cycle criteria" in p["chain"][-1]
    )
    ok = X.causal_path(
        E.default_config(), [{"tick": 100, "op": "RECONFIGURE", "path": "power.charge", "value": 0.4}]
    )  # a no-op: nothing departs
    assert ok["intermediate_changes"] == [] and ok["collapse_tick"] is None


# ---------------------------------------------------------------------------------------------------- 2. history x gradient x power
def test_the_eight_condition_factorial_localises_where_history_is_necessary():
    f = X.factorial_history_gradient_power(E.default_config(), seeds=(1, 2))
    assert len(f["rows"]) == 8 and {
        (r["condition"]["history"], r["condition"]["gradient"], r["condition"]["power"]) for r in f["rows"]
    } == set(itertools.product((True, False), (True, False), ("finite", "unlimited")))
    by = {(r["condition"]["history"], r["condition"]["gradient"], r["condition"]["power"]): r for r in f["rows"]}
    for key, r in by.items():
        expect = "COLLAPSED" if key == (False, True, "finite") else "ACTIVE"
        assert r["operational_state"] == expect, key
        for m in (
            "resource_throughput",
            "cumulative_energy_use",
            "renewal_count",
            "a1_activity",
            "a2_activity",
            "target_held_share",
            "collapse_tick",
            "cycles_before_collapse",
        ):
            assert m in r and "std" in r[m]
    nec = {(e["gradient"], e["power"]): e["history_is_necessary"] for e in f["history_effect_by_condition"]}
    assert nec == {
        (True, "finite"): True,
        (True, "unlimited"): False,
        (False, "finite"): False,
        (False, "unlimited"): False,
    }  # conditional, not a general necessity
    assert not any(e["history_is_reversed"] for e in f["history_effect_by_condition"])
    assert (
        by[(False, True, "finite")]["recovery_possible_seeds"] == 0 and by[(True, True, "finite")]["recovery_possible_seeds"] == 2
    )


def test_the_necessity_map_classifies_each_cell_of_recharge_rate_and_capacity():
    m = X.history_necessity_map(E.default_config(), charges=(0.05, 0.4, 1.0), capacities=(24.0,), seeds=(1,))
    by = {c["charge"]: c["class"] for c in m["cells"]}
    assert by[0.05] == "collapses either way"
    assert by[0.4] == "history necessary"
    assert by[1.0] == "persists without history"  # the dependence on history belongs to the power regime
    assert set(by.values()) <= {
        "history necessary",
        "persists without history",
        "history reversed (persists only without)",
        "collapses either way",
        "seed-dependent",
    }


# ---------------------------------------------------------------------------------------------------- 3. the minimal operational configurations
def test_all_minimal_configurations_are_found_by_brute_force_and_checked_for_inclusion_minimality():
    comps = ("A2", "history", "resource_gradient", "feedback", "interaction_channel")
    m = X.minimal_configurations(E.default_config(), seeds=(1,), horizon=160, components=comps)
    assert m["subsets_evaluated"] == 32 and m["allowed_reduction_operations"] == list(comps)
    pres = [frozenset(s["retained"]) for s in m["all_subsets"] if s["persists"]]
    brute = [s for s in pres if not any(t < s for t in pres)]
    assert sorted(map(sorted, brute)) == sorted(c["retained"] for c in m["minimal_sets"]) and m["minimal_set_count"] == len(brute)
    for c in m["minimal_sets"]:
        assert c["every_proper_subset_fails"] and c["cardinality"] == len(c["retained"])
        assert c["operation_identity"]["every_cycle_has_the_full_four_link_chain"]
    for k in (
        "preserved_operation",
        "environment_condition",
        "observation_condition",
        "scale",
        "temporal_window",
        "allowed_reduction_operations",
    ):
        assert k in m  # what a minimal configuration is relative to
    assert {"A2", "feedback", "interaction_channel"} <= set(m["minimal_sets"][0]["retained"])
    ex = m["non_monotone_examples"]
    assert (
        ex
        and ex[0]["component"] == "history"
        and ex[0]["removed_alone_persists"] is False
        and ex[0]["removed_together_with"] == ["resource_gradient"]
    )


def test_a_persisting_reduced_configuration_is_checked_for_whether_it_is_the_same_operation():
    m = X.minimal_configurations(E.default_config(), seeds=(1,), horizon=160, components=("A2", "history", "resource_gradient"))
    ident = m["minimal_sets"][0]["operation_identity"]
    assert ident["every_cycle_has_the_full_four_link_chain"]
    assert ident["cycle_period_median"] == ident["cycle_period_median_unreduced"]  # the same rhythm ...
    assert (
        ident["history_reentry_share"] == 0.0 and ident["history_reentry_share_unreduced"] == 1.0
    )  # ... but without history re-entry: the difference is recorded, not hidden


# ---------------------------------------------------------------------------------------------------- 4. operational state is not observed state
def test_an_observation_cannot_change_what_it_observes_and_agreeing_observation_is_observable(base):
    o = A.observe(base, {})
    assert o["operational_state"] == o["observed_state"] == "ACTIVE" and o["observability_status"] == "OBSERVABLE" and o["agrees"]
    assert run()["result_digest"] == base["result_digest"]  # observing is a computation over the record; the run is untouched


@pytest.mark.parametrize(
    ("obs", "status", "cause"),
    [
        ({"sampling_interval": 2}, "INSUFFICIENT_TEMPORAL_RESOLUTION", "sampling_interval"),
        ({"spatial_stride": 2}, "INSUFFICIENT_SPATIAL_RESOLUTION", "spatial_stride"),
        ({"region": [0, 0, 1, 1]}, "REGION_EXCLUDES_ACTIVITY", "region"),
        ({"window": 6}, "OBSERVATION_WINDOW_MISMATCH", "window"),
    ],
)
def test_a_limit_of_the_observation_is_not_an_operational_collapse(base, obs, status, cause):
    o = A.observe(base, obs)
    assert o["operational_state"] == "ACTIVE" and o["observed_state"] != "ACTIVE" and not o["agrees"]
    assert o["observability_status"] == status and o["limiting_parameters"] == [cause]
    full = A.observe(base, {k: v for k, v in A.FULL_OBSERVATION.items() if k == cause})
    assert full["agrees"]  # relaxing exactly that parameter restores agreement


def test_aggregation_and_combined_limits_are_distinguished(base):
    assert (
        A.observe(base, {"aggregation": 6})["agrees"]
        and A.observe(base, {"aggregation": 24})["observed_cycles"] < A.observe(base, {"aggregation": 6})["observed_cycles"]
    )
    both = A.observe(base, {"sampling_interval": 2, "spatial_stride": 2})
    assert both["observability_status"].startswith("COMBINED_LIMITS") and both["limiting_parameters"] == []
    dead = run([{"tick": 0, "op": "REMOVE", "target": "A2"}])
    o = A.observe(dead, {"sampling_interval": 2})
    assert o["operational_state"] == "COLLAPSED" and o["agrees"]  # a real collapse is observed as one, whatever the resolution


# ---------------------------------------------------------------------------------------------------- 5. boundaries
def test_five_kinds_of_boundary_change_are_kept_apart():
    b = X.boundary_experiments(E.default_config(), seeds=(1,))
    assert b["dimensions"] == ["operation", "coupling", "resource exchange", "history accessibility", "observation", "recovery"]
    by = {
        r["boundary_change"].split(":")[0] if "observation boundary" in r["boundary_change"] else r["boundary_change"]: r[
            "per_seed"
        ][0]
        for r in b["rows"]
    }
    obs = by["observation boundary"]
    assert (
        obs["operation"] == "ACTIVE"
        and obs["observed_state"] == "COLLAPSED"
        and obs["observability_status"] == "REGION_EXCLUDES_ACTIVITY"
    )  # seen differently, operating the same
    cut = by["operational coupling cut (interaction channel)"]
    assert (
        cut["operation"] == "COLLAPSED"
        and cut["observed_state"] == "COLLAPSED"
        and cut["coupling_mean_interaction_strength"] < by["none (unperturbed)"]["coupling_mean_interaction_strength"]
    )
    for k in (r["boundary_change"] for r in b["rows"] if r["boundary_change"].startswith("resource-exchange")):
        assert by[k]["operation"] == "COLLAPSED"
    assert by["history-access boundary: A1 only"]["operation"] == "ACTIVE"  # A1's access to history is enough ...
    assert by["history-access boundary: A2 only"]["operation"] == "COLLAPSED"  # ... A2's alone is not
    assert (
        by["history-access boundary: A1 only"]["history_accessibility_mean_threshold_reduction"]
        < by["none (unperturbed)"]["history_accessibility_mean_threshold_reduction"]
    )
    assert by["Address Domain boundary: A2 reassigned to (9, 6)"]["operation"] == "COLLAPSED"


def test_the_relations_that_close_for_the_first_time_in_b3_are_identified():
    c = X.body_closure(E.default_config())
    assert c["sets_evaluated"] == 2 ** len(c["added_by_b3"]) and len(c["minimal_persisting_bodies"]) == 1
    assert set(c["minimal_persisting_bodies"][0]["added_to_B1"]) == {
        "A2",
        "feedback",
        "history",
        "interaction_channel",
        "resource_renewal",
        "sensor_alteration",
    }
    assert all(
        not x["persists"] for x in c["all"] if set(x["added_to_B1"]) < set(c["added_by_b3"])
    )  # no proper part of what B3 adds closes it
    assert "closing" in c["closing_relation"] or "relations" in c["closing_relation"]


def test_history_access_can_be_given_to_one_configuration_only():
    r = E.run_record(E.default_config(history={"access": {"A1": True, "A2": False}}), [])
    a2 = r["traces"]["history_contribution_a2"]
    assert (
        max(a2) == 0.0 and max(r["traces"]["history_contribution_a1"]) > 0 and max(r["traces"]["history_trace_a2"]) > 0
    )  # recorded, not accessible


# ---------------------------------------------------------------------------------------------------- 6. recovery
def test_the_recovery_response_to_a_resource_pulse_has_a_band_and_a_failure_above_it():
    r = X.recovery_phase(E.default_config(), amounts=(0, 0.5, 1, 2, 3, 4, 5), seeds=(1, 2))
    reg = {row["amount"]: row["region"] for row in r["rows"]}
    assert reg[0] == "no recovery (below the band)" and reg[0.5] == "no recovery (below the band)"
    assert reg[1] == reg[2] == reg[3] == "recovery"
    assert reg[4] == reg[5] == "no recovery (above the band: excess pulse)"
    assert r["recovery_band"] == [1, 3] and r["response_is_monotone"] is False  # more is not better
    good = next(row for row in r["rows"] if row["amount"] == 2)["per_seed"][0]
    for k in (
        "latency",
        "sustained_ticks",
        "post_recovery_cycle_period_cv",
        "history_trace_after_vs_unperturbed",
        "energy_reserve_at_recovery",
        "a1_a2_lag_after_recovery",
    ):
        assert k in good
    assert good["latency"] == 11 and good["sustained_ticks"] > 150 and good["final_state"] == "ACTIVE"


def test_after_an_a2_interruption_an_overshooting_pulse_recovers_and_collapses_again():
    r = X.recovery_phase(E.default_config(), amounts=(0, 2, 5), seeds=(1,), scenario="A2 removed 100-150")
    reg = {row["amount"]: row["region"] for row in r["rows"]}
    assert reg[2] == "recovery" and reg[5] == "overshoot / re-collapse"
    over = next(row for row in r["rows"] if row["amount"] == 5)["per_seed"][0]
    assert over["recovered"] and over["recollapsed"] and over["sustained_ticks"] < 60 and over["final_state"] != "ACTIVE"


# ---------------------------------------------------------------------------------------------------- 7. SSS and Address Domain
def test_the_sss_space_is_split_into_regions_and_the_active_region_is_observation_sensitive():
    p = X.sss_phase(E.default_config(), scales=(0.5, 1.0), sizes=(1.0, 2.0), speeds=(1.0, 2.0), seeds=(1,))
    by = {(q["scale"], q["size"], q["speed"]): q for q in p["points"]}
    assert (
        by[(1.0, 1.0, 1.0)]["class"] == "ACTIVE"
        and by[(1.0, 2.0, 1.0)]["class"] == "COLLAPSED"
        and by[(1.0, 1.0, 2.0)]["class"] == "COLLAPSED"
    )
    assert by[(1.0, 1.0, 1.0)]["observation_sensitive"] is True  # active, yet an interval-2 observation says collapsed
    assert by[(1.0, 2.0, 1.0)]["recovery_capable"] is False and set(p["counts"]) <= {"ACTIVE", "COLLAPSED", "metastable"}


def test_address_interventions_are_applied_and_leave_the_baseline_alone():
    loss = run([{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "loss"}])
    assert (
        loss["frames"][100]["address"]["A2"] == {"mode": "loss", "integrity": 0.0}
        and loss["frames"][100]["address"]["A1"]["mode"] is None
    )
    assert any(
        e["kind"] == "act" and e["actor"] == "A2" and e["action"].startswith("blocked") for e in loss["events"]
    )  # it fires, its actions reach nothing
    assert loss["traces"]["address_integrity_a2"][101] == 0.0 and loss["final_status"]["label"] == "COLLAPSED"
    restored = run(
        [
            {"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "loss"},
            {"tick": 130, "op": "ADDRESS", "target": "A2", "mode": "restore"},
        ],
        horizon=360,
    )
    pulsed = run(
        [
            {"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "loss"},
            {"tick": 130, "op": "ADDRESS", "target": "A2", "mode": "restore"},
            X.pulse(131, 2.0),
        ],
        horizon=360,
    )
    assert (
        restored["final_status"]["label"] == "COLLAPSED" and pulsed["final_status"]["label"] == "ACTIVE"
    )  # recovery after restoration needs the pulse
    assert (
        run([{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "restore"}])["result_digest"] != ""
        and run([{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "restore"}])["final_status"]["label"] == "ACTIVE"
    )


def test_the_address_experiments_cover_loss_reassignment_fragmentation_collision_and_partial_addressability():
    r = X.address_experiments(E.default_config(), seeds=(1,))
    names = " | ".join(x["case"] for x in r["rows"])
    for w in ("address loss", "collision", "fragmentation", "partial addressability", "reassigned"):
        assert w in names
    by = {x["case"]: x["per_seed"][0] for x in r["rows"]}
    assert by["address loss of A2"]["fault_only"] == "COLLAPSED" and by["address loss of A2"]["restored_and_pulse"] == "ACTIVE"
    assert (
        by["partial addressability of A2 (75 % of steps)"]["restored_and_pulse"] == "COLLAPSED"
    )  # even a mild, temporary loss is not recovered from by a pulse
    assert (
        by["fragmentation of A2's addressable window to 25 %"]["fault_only"] == "ACTIVE"
    )  # a null result: A2's peak detector survives a fragmented window
    assert by["A2 reassigned to (9, 6), never restored"]["fault_only"] == "COLLAPSED"


def test_address_interventions_are_validated():
    for iv in (
        {"tick": 5, "op": "ADDRESS", "target": "A2", "mode": "teleport"},
        {"tick": 5, "op": "ADDRESS", "target": "C", "mode": "loss"},
        {"tick": 5, "op": "ADDRESS", "target": "A2", "mode": "reassign"},
        {"tick": 5, "op": "ADDRESS", "target": "A2", "mode": "partial", "fraction": 2},
    ):
        with pytest.raises(E.MeosError):
            E.Run(E.default_config(), [iv])


# ---------------------------------------------------------------------------------------------------- 8. M2
def test_m2_is_off_by_default_and_an_explicit_connection_is_compared_not_assumed(base):
    assert run(m2={"sense": "none"})["result_digest"] == base["result_digest"]
    direct = run(m2={"sense": "direct", "weight": 0.5})
    assert direct["final_status"]["label"] == "ACTIVE" and len(direct["cycles"]) == len(
        base["cycles"]
    )  # connected, and no difference in outcome
    delayed = run(m2={"sense": "delayed", "weight": 1.0, "delay": 3})
    assert delayed["final_status"]["label"] == "ACTIVE"
    noisy_a, noisy_b = (
        run(m2={"sense": "noisy", "weight": 1.0, "noise": 0.05}),
        run(m2={"sense": "noisy", "weight": 1.0, "noise": 0.05}),
    )
    assert noisy_a["result_digest"] == noisy_b["result_digest"]  # the noise has its own seeded stream: deterministic


def test_the_m2_experiment_reports_no_difference_where_there_is_none():
    r = X.m2_experiment(E.default_config(), seeds=(1,))
    none = [x for x in r["rows"] if x["m2"] == "none"]
    assert len(none) == 7 and all(x["difference_vs_none"] == "identical run" for x in none)
    unperturbed = {x["m2"]: x for x in r["rows"] if x["scenario"] == "unperturbed"}
    assert unperturbed["direct w=0.5"]["difference_vs_none"].startswith("no difference")
    assert any(
        x["difference_vs_none"] == "different outcome" for x in r["rows"]
    )  # and a difference where there is one, not hidden
    fatal = {x["m2"]: x["persists_seeds"] for x in r["rows"] if x["scenario"] == "renewal efficiency 0.7 at 100"}
    assert all(
        v == 0 for k, v in fatal.items() if "w=0.25" in k or "w=0.5" in k or k.startswith(("direct", "delayed"))
    )  # a plain connection, direct or delayed, rescues nothing
    assert (
        fatal["noisy(0.05) w=2.0"] == 1 and fatal["noisy(0.05) w=4.0"] == 1
    )  # a noisy, strongly weighted M2 does: noise keeps re-triggering A1 (a conditional effect, not a design goal)
    harm = {x["m2"]: x["cycles"]["mean"] for x in r["rows"] if x["scenario"] == "unperturbed"}
    assert (
        harm["noisy(0.05) w=4.0"] < harm["none"]
    )  # and where nothing needs rescuing the same connection reduces the cycles: a cost


# ---------------------------------------------------------------------------------------------------- 9. Philosophical operations
def phil(mode, ivs, horizon=360, **kw):
    ph = {"mode": mode, "margin": 0.1, "window": 3, "verify_margin": 0.02, **{k: v for k, v in kw.items() if k not in ("power",)}}
    return E.run_record(E.default_config(horizon=horizon, phil=ph, power=kw.get("power", {})), ivs)


def kinds(rec):
    out: dict[str, int] = {}
    for e in rec["events"]:
        out[e["kind"]] = out.get(e["kind"], 0) + 1
    return out


def test_mode_none_is_the_baseline_and_each_mode_adds_only_its_own_operations(base):
    assert E.run_record(E.default_config(phil={"mode": "none"}), [])["result_digest"] == base["result_digest"]
    ivs, h = X._shift("drift0.7")
    unl = {"infinite": True}
    ex, sc, rv = (
        phil("expression", ivs, h, power=unl),
        phil("scorekeeping", ivs, h, power=unl),
        phil("revision", ivs, h, power=unl),
    )
    assert kinds(ex).get("expression", 0) > 0 and not {"response", "score", "inference", "revision", "correction"} & set(
        kinds(ex)
    )
    assert (
        kinds(sc).get("response", 0) > 0
        and kinds(sc).get("score", 0) > 0
        and not {"inference", "revision", "correction"} & set(kinds(sc))
    )
    assert {"expression", "response", "score", "inference", "revision"} <= set(kinds(rv))


def test_a_closed_path_from_environmental_event_to_operational_change_is_recorded():
    ivs, h = X._shift("drift0.7")
    rec = phil("revision", ivs, h, power={"infinite": True})
    paths = X.phil_paths(rec)
    assert len(paths) >= 5
    false_alarms = [
        q for q in paths if q["environmental_event_tick"] is None
    ]  # a claim with no environmental event before it is a false alarm: recorded as such
    assert false_alarms and len(false_alarms) < len(paths)
    p = next(q for q in paths if q["environmental_event_tick"] is not None)
    assert (
        p["environmental_event_tick"] >= 80
        and p["environmental_event_tick"] <= p["detection_and_expression_tick"] < p["response_tick"] <= p["score_tick"]
        and p["operational_change"] in ("revision", "correction", "withhold")
    )
    assert any(q["operational_change"] == "revision" for q in paths)
    boost = rec["traces"]["phil_boost"]
    assert (
        boost[0] == 1.0 and boost[-1] > 1.3 and rec["traces"]["phil_power_spent"][-1] > 0
    )  # the revision is a real change of A2's action, and the operation is paid for


def test_philosophical_operations_are_conditionally_necessary_not_always_helpful():
    ivs, h = X._shift("drift0.7")
    modes = ("none", "expression", "scorekeeping", "revision")
    unlimited = {m: phil(m, ivs, h, power={"infinite": True})["final_status"]["label"] for m in modes}
    finite = {m: phil(m, ivs, h)["final_status"]["label"] for m in modes}
    assert unlimited == {
        "none": "COLLAPSED",
        "expression": "COLLAPSED",
        "scorekeeping": "COLLAPSED",
        "revision": "ACTIVE",
    }  # needed, and only revision supplies it
    assert set(finite.values()) == {
        "COLLAPSED"
    }  # under the finite reserve nothing helps: the operation is paid for from the same reserve
    stable = {m: phil(m, [], 240)["final_status"]["label"] for m in modes}
    assert set(stable.values()) == {"ACTIVE"}  # in a stable environment it is not needed, and (here) not harmful
    mild = X._shift("step0.85")
    assert (
        phil("none", *mild, power={"infinite": True})["final_status"]["label"] == "ACTIVE"
    )  # a mild shift needs no philosophical operation at all


def test_the_operation_fires_becomes_unnecessary_and_fires_again():
    ivs, h = X._shift("shift-restore-shift:0.6")
    rec = phil("revision", ivs, h, power={"infinite": True})
    ex = [e["tick"] for e in rec["events"] if e["kind"] == "expression"]
    first, quiet, second = [t for t in ex if 80 <= t < 200], [t for t in ex if 260 <= t < 320], [t for t in ex if t >= 320]
    assert (
        len(first) >= 3 and quiet == [] and len(second) >= 3
    )  # fires when the environment shifts, is silent once it is restored, fires again on the next shift
    assert (
        rec["final_status"]["label"] == "ACTIVE"
        and phil("none", ivs, h, power={"infinite": True})["final_status"]["label"] == "COLLAPSED"
    )


def test_a_slow_or_noisy_channel_is_a_reason_the_operation_can_fail():
    ivs, h = X._shift("drift0.7")
    clean = phil("revision", ivs, h, power={"infinite": True})
    noisy, slow = (
        phil("revision", ivs, h, power={"infinite": True}, noise=0.6),
        phil("revision", ivs, h, power={"infinite": True}, delay=15),
    )
    assert clean["final_status"]["label"] == "ACTIVE"
    assert (
        noisy["traces"]["phil_boost"][-1] != clean["traces"]["phil_boost"][-1]
        and slow["traces"]["phil_boost"][-1] != clean["traces"]["phil_boost"][-1]
    )  # what was inferred differs
    assert kinds(noisy).get("expression", 0) > 0 and kinds(slow).get("expression", 0) > 0


def test_the_norm_withholds_an_unreliable_kind_of_claim_and_a_mismatch_is_corrected():
    rec = phil("revision", [], 240, power={"infinite": True})  # a stable environment: any claim is a false alarm
    k = kinds(rec)
    assert k.get("correction", 0) > 0 and k.get("withhold", 0) > 0 and rec["final_status"]["label"] == "ACTIVE"
    w = next(e for e in rec["events"] if e["kind"] == "withhold")
    sc = next(e for e in rec["events"] if e["kind"] == "score" and e["id"] == w["score"])
    assert sc["reliability"] < 0.4  # the norm: an unreliable kind is not asserted
    assert phil("revision", [], 240, power={"infinite": True})["result_digest"] == rec["result_digest"]  # deterministic


def test_the_philosophical_module_has_no_language_model_and_is_part_of_the_bodies():
    from pathlib import Path

    src = Path(E.__file__).with_name("phil.py").read_text().lower()
    for w in ("openai", "anthropic", "transformers", "llm(", "completion"):
        assert w not in src
    assert (
        "run.ent" in src and "run.power" in src and "run._event" in src
    )  # it reads and changes the same bodies, power and event record as everything else


# ---------------------------------------------------------------------------------------------------- API
@pytest.fixture
def client():
    return TestClient(app_mod.app, headers={"origin": "http://testserver"})


def test_the_stage_two_api_serves_causal_observe_factorial_recovery_and_address(client):
    c = client.post("/api/meos/causal", json={"interventions": [{"tick": 100, "op": "REMOVE", "target": "A2"}]}).json()
    assert c["collapse_tick"] and c["chain"]
    o = client.post("/api/meos/observe", json={"observation": {"sampling_interval": 2}}).json()
    assert (
        o["operational_state"] == "ACTIVE"
        and o["observed_state"] == "COLLAPSED"
        and o["observability_status"] == "INSUFFICIENT_TEMPORAL_RESOLUTION"
    )
    f = client.post("/api/meos/factorial", json={"seeds": [1]}).json()
    assert len(f["rows"]) == 8
    r = client.post("/api/meos/recovery", json={"amounts": [0, 2, 5], "seeds": [1]}).json()
    assert [row["region"] for row in r["rows"]][1] == "recovery"
    a = client.post(
        "/api/meos/run", json={"interventions": [{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "loss"}]}
    ).json()
    assert (
        a["record"]["frames"][100]["address"]["A2"]["mode"] == "loss" and "traces" in a["record"] and a["record"]["trace_digest"]
    )


def test_the_stage_two_api_bounds_its_work(client):
    assert client.post("/api/meos/causal", json={}).status_code == 422
    assert client.post("/api/meos/factorial", json={"seeds": list(range(20))}).status_code == 422
    assert client.post("/api/meos/minimal-configurations", json={"horizon": 9999}).status_code == 422
    assert client.post("/api/meos/recovery", json={"amounts": list(range(40))}).status_code == 422
    assert client.post("/api/meos/recovery", json={"scenario": "nope"}).status_code == 422
    assert (
        client.post("/api/meos/sss-phase", json={"scales": [1.0] * 5, "sizes": [1.0] * 5, "speeds": [1.0] * 5}).status_code == 422
    )
    assert client.post("/api/meos/observe", json={"observation": "x"}).status_code == 422
