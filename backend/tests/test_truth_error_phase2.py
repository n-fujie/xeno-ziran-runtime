"""TRUTH-ERROR phase 2: the correction process, the release of a constraint, the recoverability of a lost opportunity and the appeal, in the synthetic institution.
These check the model's own properties (the phase-1 digests unchanged, the event times, the independence of correction time and release time, the conditions of non-identity, the recoverability accounting, the appeal, the
reproduction of the saved results); none of it is evidence about a real institution or person."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import numpy as np
import pytest

from xzr.service.truth_error import config_from
from xzr.truth_error import experiments2 as X2
from xzr.truth_error import institution as I  # noqa: E741
from xzr.truth_error.process import EVENTS, METRICS, recoverability

DOCS = Path(__file__).resolve().parents[2] / "docs" / "truth_error"
SAVED1, SAVED2 = DOCS / "experiments.json", DOCS / "experiments2.json"


def cfg(**kw):
    return I.Config(**{"n": 120, "periods": 40, "lock_after": 4, "release_after": 3, **kw})


def times(r, ev):
    return np.array([-1 if t is None else t for t in r["process"]["events"][ev]["times"]])


# ------------------------------------------------------------------------------------------------ phase 1 is untouched
def test_every_saved_phase_1_arm_still_reproduces_its_digest():
    saved = json.loads(SAVED1.read_text())["experiments"]
    n = 0
    for eid, e in saved.items():
        by_arm = {a["arm"]: a["result_digest_seed1"] for a in e["arms"]}
        for name, conf in e["arm_configs"].items():
            c = config_from({"config": {**conf, "seed": 1}})
            assert I.run(c)["result_digest"] == by_arm[name], (eid, name)
            n += 1
    assert n >= 40  # every arm of the 11 saved experiments


def test_the_defaults_have_no_process_and_the_phase_2_record_stays_outside_the_digested_result():
    r = I.run(cfg(seed=3))
    ev = r["process"]["events"]
    assert all(ev[k]["n"] == 0 for k in ("detected", "requested", "approved", "score_updated")) and r["process"]["appeal"]["exists"] is False
    # the process record is not part of result_digest (so the saved digests hold) but has its own digest
    assert r["result_digest"] == I.digest({k: r[k] for k in ("series", "summary")}) and r["process_digest"] == I.digest(r["process"])


# ------------------------------------------------------------------------------------------------ the nine times and their independence
PROC = dict(audit_every=2, request_delay=1, approval_delay=2, release_mode="after_approval", release_delay=0, beta=0.0)


def test_the_times_of_the_process_follow_their_declared_delays_exactly():
    r = I.run(cfg(seed=2, **{**PROC, "request_delay": 2, "approval_delay": 3, "score_delay": 1, "release_delay": 4}))
    d, q, a, s, rel = (times(r, k) for k in ("detected", "requested", "approved", "score_updated", "released"))
    both = (d >= 0) & (q >= 0)
    assert both.any() and np.all(q[both] - d[both] == 2)
    both = (q >= 0) & (a >= 0)
    assert both.any() and np.all(a[both] - q[both] == 3)
    both = (a >= 0) & (s >= 0)
    assert both.any() and np.all(s[both] - a[both] == 1)
    both = (a >= 0) & (rel >= 0)
    assert both.any() and np.all(rel[both] - a[both] == 4)  # a release after approval comes exactly release_delay after it
    assert set(r["process"]["events"]) == set(EVENTS)


def test_a_misclassification_is_never_adopted_before_it_occurs():
    r = I.run(cfg(seed=4, **PROC))
    m, ad = times(r, "misclassified"), times(r, "adopted")
    ok = (m >= 0) & (ad >= 0)
    assert ok.any() and np.all(m[ok] <= ad[ok])
    assert np.all(ad[ad >= 0] >= m[ad >= 0])  # nothing is adopted that was not first misclassified


def test_correction_time_and_release_time_are_independent_variables():
    a = I.run(cfg(seed=5, **{**PROC, "release_delay": 0}))
    b = I.run(cfg(seed=5, **{**PROC, "release_delay": 6}))
    assert np.array_equal(times(a, "approved"), times(b, "approved"))  # the correction does not move when only the release does
    assert not np.array_equal(times(a, "released"), times(b, "released"))
    c = I.run(cfg(seed=5, **{**PROC, "approval_delay": 6}))
    assert not np.array_equal(times(a, "approved"), times(c, "approved"))
    both = (times(a, "released") >= 0) & (times(c, "released") >= 0) & (times(a, "approved") >= 0) & (times(c, "approved") >= 0)
    assert both.any()


def test_process_settings_leave_the_subjects_real_states_alone_when_resources_do_not_feed_back():
    base = I.run(cfg(seed=6, **{**PROC, "audit_every": None}))
    for kw in ({"approval_delay": 9}, {"release_delay": 5}, {"audit_every": 1}, {"release_mode": "never"}):
        assert I.run(cfg(seed=6, **{**PROC, **kw}))["target_state_digest"] == base["target_state_digest"]


# ------------------------------------------------------------------------------------------------ the conditions of non-identity
def test_where_no_constraint_exists_correction_and_release_are_not_distinct():
    a = I.run(cfg(seed=7, lock_after=None, **{**PROC, "release_mode": "never"}))
    b = I.run(cfg(seed=7, lock_after=None, **PROC))
    assert a["result_digest"] == b["result_digest"]


def test_where_a_constraint_exists_withholding_the_release_leaves_it_in_force_after_the_correction():
    rel = [I.run(cfg(seed=s, **PROC)) for s in range(1, 9)]
    nev = [I.run(cfg(seed=s, **{**PROC, "release_mode": "never"})) for s in range(1, 9)]
    lock = lambda rs: np.mean([r["process"]["metrics"]["persistent_constraint"] for r in rs])  # noqa: E731
    assert lock(nev) > lock(rel)
    assert all(times(r, "released").max() == -1 for r in nev)  # no release happened at all
    assert any(times(r, "approved").max() >= 0 for r in nev)  # yet corrections were approved


def test_a_release_without_a_score_update_is_taken_back_where_the_score_binds_and_is_not_where_it_cannot():
    kw = {**PROC, "approval_delay": 0, "request_delay": 0}
    for seed in (1, 2, 3):
        upd = I.run(cfg(seed=seed, **kw))
        no_upd = I.run(cfg(seed=seed, **{**kw, "score_delay": 99}))
        assert no_upd["process"]["metrics"]["denial_rate_late_fav"] >= upd["process"]["metrics"]["denial_rate_late_fav"]
        # the score never binds: updating it changes nothing
        a = I.run(cfg(seed=seed, tau_a=-5.0, **kw))
        b = I.run(cfg(seed=seed, tau_a=-5.0, **{**kw, "score_delay": 99}))
        assert a["result_digest"] == b["result_digest"]
    assert np.mean([I.run(cfg(seed=s, **{**kw, "score_delay": 99}))["process"]["reimposed_after_release"] for s in (1, 2, 3)]) > 0


# ------------------------------------------------------------------------------------------------ recoverability
def acc(rows):
    return np.array(rows, dtype=bool).T  # rows given per subject -> (periods, subjects)


def test_recoverability_classes_by_hand_built_access_histories():
    h = acc([[0, 0, 0, 1, 1, 1, 1, 1]])  # denied for 3 periods, then access returns
    assert recoverability(h, 0)["episodes"]["unrecoverable"] == 1 and recoverability(h, 0)["periods"]["recoverable"] == 0
    p2 = recoverability(h, 2)
    assert p2["periods"] == {"recoverable": 2, "expired": 1, "unresolved": 0} and p2["episodes"]["partially_recoverable"] == 1
    assert recoverability(h, 3)["episodes"]["recoverable"] == 1 and recoverability(h, 3)["periods"]["recoverable"] == 3
    never = acc([[1, 1, 0, 0, 0, 0]])  # denied to the end of the observed periods
    n2 = recoverability(never, 2)
    assert n2["episodes"]["unresolved"] == 1 and n2["periods"]["unresolved"] > 0 and n2["periods"]["recoverable"] == 0
    assert recoverability(acc([[1, 1, 1]]), 5) == {"window": 5, "periods": {"recoverable": 0, "expired": 0, "unresolved": 0}, "episodes": {"recoverable": 0, "partially_recoverable": 0, "unrecoverable": 0, "unresolved": 0}}


def test_the_irreversible_reading_is_a_setting_not_a_result():
    r = I.run(cfg(seed=3, opportunity_window=None, **PROC))
    h = np.array(r["process"]["access_history_favourable"], dtype=bool)
    z = recoverability(h, 0)
    assert z["periods"]["recoverable"] == 0
    wide = recoverability(h, 12)
    assert wide["periods"]["recoverable"] > 0  # access does return for some: whether lost opportunities return is read from the window, never assumed


# ------------------------------------------------------------------------------------------------ the appeal
def test_an_appeal_runs_its_stages_in_order_with_the_declared_review_time():
    r = I.run(cfg(seed=3, appeal=True, review_delay=3, request_delay=0, approval_delay=1, release_mode="after_approval"))
    s = r["process"]["appeal"]["stage_times"]
    f, e, ac, rj = (np.array([-1 if t is None else t for t in s[k]]) for k in ("appeal_filed", "evidence_submitted", "appeal_accepted", "rejudged"))
    assert (f >= 0).sum() > 0 and (e >= 0).sum() <= (f >= 0).sum() and (ac >= 0).sum() <= (e >= 0).sum() and (rj >= 0).sum() == (ac >= 0).sum()
    ok = rj >= 0
    assert np.all(rj[ok] - ac[ok] == 3) and np.all(ac[ok] >= e[ok]) and np.all(e[ok] >= f[ok])


def test_an_appeal_that_exists_is_not_relief_and_a_score_gated_appeal_blocks_the_score_denied():
    base = dict(appeal=True, request_delay=0, approval_delay=1, release_mode="after_approval")
    o = I.run(cfg(seed=3, **base))["process"]["appeal"]
    assert o["stages"]["appeal_filed"] > 0 and o["relief_effective"] < o["stages"]["appeal_filed"]  # filing is not relief
    g = I.run(cfg(seed=3, appeal_access="score_gated", appeal_min_score=5.0, **base))["process"]["appeal"]
    assert g["stages"]["appeal_filed"] == 0 and g["blocked_subjects"] > 0 and g["relief_effective"] == 0  # nobody can reach the appeal
    n = I.run(cfg(seed=3))["process"]["appeal"]
    assert n["exists"] is False and n["stages"]["appeal_filed"] == 0


def test_an_appeal_changes_nothing_when_it_is_not_used():
    a = I.run(cfg(seed=3))
    b = I.run(cfg(seed=3, appeal=False, appeal_filing_prob=1.0, appeal_acceptance_prob=1.0))
    assert a["result_digest"] == b["result_digest"]


# ------------------------------------------------------------------------------------------------ the metrics and the saved phase-2 results
def test_every_primary_metric_states_its_denominator_period_unit_and_population():
    assert set(X2.PRIMARY2) <= set(METRICS)
    for k in X2.PRIMARY2:
        assert {"denominator", "period", "unit"} <= set(METRICS[k]) and all(METRICS[k].values()), k
    assert "favourable at the start" in " ".join(m["denominator"] for m in METRICS.values())


def test_the_ranges_of_the_sensitivity_are_fixed_before_the_runs_and_cover_the_base():
    for k, vals in X2.PARAMETER_RANGES.items():
        assert len(vals) == 3 and len(set(vals)) >= 2, k


@pytest.fixture(scope="module")
def saved2():
    return json.loads(SAVED2.read_text())


def test_the_saved_phase_2_results_have_replication_definitions_and_kept_negatives(saved2):
    assert saved2["engine"] == "truth_error/2" and set(saved2["experiments"]) == set(X2.REGISTRY2)
    for k, e in saved2["experiments"].items():
        assert e["invalid_if_any_failure_condition"] is False, (k, e["failure_conditions"])
        assert e["replication"]["seeds"] == list(X2.SEEDS2) and e["seeds"] == list(X2.SEEDS if hasattr(X2, "SEEDS") else range(1, 21))
        assert set(e["metric_definitions"]) <= set(METRICS) and e["limits"] and e["protocol_digest"]
        assert e["replication"]["counts"]["not detected"] + e["replication"]["counts"]["replicated"] > 0
    assert any(e["negative_results"] for e in saved2["experiments"].values())  # not-detected effects are kept


def _contrast(e, label_part, outcome):
    return next(c for c in e["contrasts"] if label_part in c["label"] and c["outcome"] == outcome)


def test_the_non_identity_holds_where_a_mechanism_exists_and_not_where_it_does_not(saved2):
    e = saved2["experiments"]["EXP-TE07-release"]
    for lock in (2, 4):  # a constraint that binds: withholding the release leaves it in force
        c = _contrast(e, f"N1 lock_after={lock}:", "persistent_constraint")
        assert c["class"] == "replicated" and c["paired"]["mean"] > 0.03, lock
    c0 = _contrast(e, "N1 lock_after=None:", "persistent_constraint")
    assert c0["paired"]["mean"] == 0.0 and c0["class"] == "not detected"  # no constraint: identity
    c8 = _contrast(e, "N1 lock_after=8:", "persistent_constraint")
    assert c8["class"] == "not detected"  # a constraint that rarely forms: not demonstrated either way
    e2 = saved2["experiments"]["EXP-TE07-correction"]
    for tau in ("-0.2", "+0.0"):
        c = _contrast(e2, f"N2 tau_a={tau}:", "denial_rate_late_fav")
        assert c["class"] == "replicated" and c["paired"]["mean"] > 0.03, tau
    assert _contrast(e2, "N2 tau_a=-5.0:", "denial_rate_late_fav")["paired"]["mean"] == 0.0


def test_the_saved_timing_experiment_shows_correction_time_and_release_time_separately(saved2):
    e = saved2["experiments"]["EXP-TE08"]
    ca = _contrast(e, "correction time alone", "persistent_constraint")
    cr = _contrast(e, "release time alone", "persistent_constraint")
    assert ca["class"] == "replicated" and ca["paired"]["mean"] > 5 * abs(cr["paired"]["mean"])  # a late correction matters far more than a late release here
    rt = _contrast(e, "release time alone", "recovery_time")
    assert rt["class"] == "replicated" and rt["paired"]["mean"] > 0  # but the release time sets the time to recovery


def test_the_saved_appeal_experiment_separates_existing_from_relief(saved2):
    e = saved2["experiments"]["EXP-TE12"]
    open_arm = next(a for a in e["arms"] if a["arm"] == "appeal open to every denied subject")
    filed, relief = open_arm["mean"]["appeal_appeal_filed_share"]["mean"], open_arm["mean"]["appeal_relief_effective_share"]["mean"]
    assert filed > 0.4 and relief < filed / 5
    c = _contrast(e, "an open appeal minus no appeal", "denial_rate_late_fav")
    assert abs(c["paired"]["mean"]) < 0.01 and c["class"] == "not detected"  # the open appeal does not move the denial rate measurably, on either list of seeds
    assoc = _contrast(e, "an open appeal minus no appeal", "appeal_relief_effective_share")
    assert assoc["class"] == "replicated" and assoc["paired"]["mean"] > 0.03  # yet subjects end with access after a favourable re-judgement: an association that is not an effect
    gated = next(a for a in e["arms"] if a["arm"].startswith("appeal gated"))
    assert gated["mean"]["appeal_blocked_share"]["mean"] > 0.3


def test_the_saved_results_for_recoverability_and_the_timing_are_the_ones_the_code_produces(saved2):
    for name in ("EXP-TE11", "EXP-TE07-correction"):
        again = X2.REGISTRY2[name]()
        old = saved2["experiments"][name]
        assert again["protocol_digest"] == old["protocol_digest"]
        assert [a["result_digest_seed1"] for a in again["arms"]] == [a["result_digest_seed1"] for a in old["arms"]]
        for a, b in zip(again["arms"], old["arms"], strict=True):
            for k in old["primary_outcomes"]:
                assert a["mean"][k] == b["mean"][k], (name, a["arm"], k)
        assert [c["paired"]["mean"] for c in again.get("contrasts", [])] == [c["paired"]["mean"] for c in old.get("contrasts", [])]


# ------------------------------------------------------------------------------------------------ the API
def test_the_api_exposes_the_process_settings_with_checks_and_the_saved_phase_2_results():
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod

    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    spec = c.get("/api/truth-error/spec").json()
    assert spec["engine"] == "truth_error/2" and set(spec["phase2"]["primary_metrics"]) == set(X2.PRIMARY2)
    body = {"config": {"seed": 3, "lock_after": 4, "audit_every": 2, "appeal": True, "release_mode": "after_approval"}}
    r = c.post("/api/truth-error/run", json=body).json()
    assert r["process"]["events"]["approved"]["n"] > 0 and r["process"]["appeal"]["exists"] is True
    assert r["result_digest"] == I.run(config_from(body))["result_digest"]
    json.dumps(r, allow_nan=False)  # strict JSON, no NaN
    for bad in ({"release_mode": "forever"}, {"appeal_access": "vip"}, {"audit_every": 0}, {"approval_delay": -1}, {"appeal_filing_prob": 2}, {"opportunity_window": -1}, {"appeal": "yes"}):
        assert c.post("/api/truth-error/run", json={"config": bad}).status_code == 422, bad
    assert c.get("/api/truth-error/experiments2").json()["engine"] == "truth_error/2"
    assert c.get("/api/truth-error/experiments2", headers={"origin": "http://evil.example"}).status_code in (403, 404)


def test_phase_2_is_synthetic_and_names_no_real_person_or_credit_decision():
    text = (Path(X2.__file__).read_text() + (Path(X2.__file__).parent / "process.py").read_text()).lower()
    assert "synthetic" in text
    for banned in ("face_recognition", "mediapipe", "credit_score_of", "ssn", "passport"):
        assert banned not in text
    assert dataclasses.is_dataclass(I.Config())


def test_an_observation_only_change_holds_the_real_state_only_when_the_resources_do_not_feed_back(saved2):
    e = saved2["experiments"]["EXP-TE10"]
    arms = {a["arm"]: a for a in e["arms"]}
    assert arms["Q4 only the observation changes (view angle 40, occlusion 0.25)"]["target_state_identical_to_control_in_every_seed"] is False  # beta 0.06: access moves the state
    held = cfg(seed=2, audit_every=None, release_mode="by_score", beta=0.0, transfer_at=12)
    seen = I.run(dataclasses.replace(held, signal_sensor=dataclasses.replace(held.signal_sensor, view_angle=40.0, occlusion_prob=0.25)))
    assert seen["target_state_digest"] == I.run(held)["target_state_digest"]  # beta 0: only the observation differs, the subjects' states are the same
    assert seen["result_digest"] != I.run(held)["result_digest"]
    c = _contrast(e, "Q4 observation-only change with the real state held", "lost_opportunities_per_fav")
    assert c["class"] == "replicated" and c["paired"]["mean"] > 0


# ------------------------------------------------------------------------------------------------ final verification: what is guaranteed by construction, what the appeal is connected to, the separation
def test_every_experiment_records_what_was_changed_what_was_held_and_the_observation(saved2):
    for k, e in saved2["experiments"].items():
        recs = {r["arm"]: r for r in e["intervention_records"]}
        assert set(recs) == {a["arm"] for a in e["arms"]} - {e["control"]}, k
        for r in recs.values():
            assert r["variables_changed"] and "seed" not in r["variables_held"] and not set(r["variables_changed"]) & set(r["variables_held"])
            assert r["observation"]["periods"] == 40 and r["observation"]["late_window_periods"] == 10 and r["observation"]["seeds"] == e["seeds"]
            assert "shared with the control" in r["random_draws"]


def test_the_guarantees_of_the_transition_rules_hold_by_construction():
    """these differences are built in: an experiment can only show their size, never their existence"""
    kw = dict(seed=5, **PROC)
    assert I.run(cfg(**{**kw, "release_mode": "never"}))["process"]["events"]["released"]["n"] == 0
    assert I.run(cfg(**{**kw, "confidence_floor": 2.0}))["process"]["metrics"]["denial_rate_late_fav"] == 0.0  # nothing adopted: the score stays at its start and nobody is denied
    for k, v in (("request_delay", 3), ("approval_delay", 4), ("score_delay", 2)):
        a, b = I.run(cfg(**kw)), I.run(cfg(**{**kw, k: v}))
        assert not np.array_equal(times(a, "approved"), times(b, "approved")) or k == "score_delay"
    assert set(X2.BY_CONSTRUCTION) >= {"release_mode never", "lock_after none", "approval_delay / request_delay / score_delay / release_delay", "appeal off"}


def test_the_appeal_is_connected_to_evidence_rejudgement_correction_and_the_score_update_but_not_to_the_release_by_the_score():
    t = X2.appeal_trace()["counts"]
    assert t["evidence"] <= t["filed"] and t["accepted"] <= t["evidence"] and t["rejudged"] == t["accepted"]   # each stage follows the last
    assert t["corrected_by_rejudgement"] + t["upheld"] == t["rejudged"]
    # every re-judgement that follows the evidence becomes a request, an approval after the declared delay, and a score update at the approval
    assert t["correction_requested_at_rejudgement"] == t["approved_after_request_delay"] == t["score_updated_at_approval"] == t["corrected_by_rejudgement"] > 0
    assert t["released_at_or_after_approval"] < t["corrected_by_rejudgement"] / 5   # the release is by the score in this configuration: the appeal does not reach it
    # why the outcomes do not move: almost no favourable subject's access differs with the appeal, and of those still denied at the end every one filed
    assert t["favourable_with_any_access_difference"] <= t["favourable_subjects"] * 0.01
    assert t["needing_relief_never_filed"] == 0 and t["needing_relief_upheld"] > t["needing_relief_still_denied_at_end"] / 2


def test_the_saved_appeal_trace_is_the_one_the_code_produces():
    saved = json.loads((DOCS / "appeal_trace.json").read_text())
    assert saved["counts"] == X2.appeal_trace()["counts"] and saved["seeds"] == list(X2.SEEDS)


def test_the_appeal_stays_null_when_it_is_the_only_route_to_the_release_and_when_it_is_fully_resourced(saved2):
    e = saved2["experiments"]["EXP-TE12-release"]
    m = _contrast(e, "MATCHED", "denial_rate_late_fav")
    assert m["class"] == "not detected" and abs(m["paired"]["mean"]) < 0.005
    assert _contrast(e, "fully resourced", "denial_rate_late_fav")["class"] == "not detected"
    c = _contrast(e, "CONFOUNDED", "denial_rate_late_fav")
    assert c["class"] == "replicated" and c["paired"]["mean"] > 0.05   # the rule switch itself (loss of the release by the score) is what moves the outcome
    assert e["protocol"]["status"].startswith("exploratory")
    resourced = next(a for a in e["arms"] if a["arm"].startswith("appeal open, evidence always"))
    assert resourced["mean"]["share_approved"]["mean"] > 0.1 and resourced["mean"]["time_released"]["mean"] is None   # approvals are made, and none of them meets a constraint in force


def test_the_correction_the_score_update_and_the_release_are_separated_by_the_saved_2x2x2(saved2):
    e = saved2["experiments"]["EXP-TE15"]
    c = lambda lab, out: _contrast(e, lab, out)  # noqa: E731
    assert c("main effect of the release", "denial_rate_late_fav")["class"] == "not detected"   # delaying the release alone leaves the late denial rate
    assert c("main effect of the release", "time_restored")["class"] == "replicated" and c("main effect of the release", "time_restored")["paired"]["mean"] > 3   # but it delays the restoration
    for lab in ("main effect of the time of the correction", "main effect of the score update"):
        x = c(lab, "denial_rate_late_fav")
        assert x["class"] == "replicated" and x["paired"]["mean"] > 0.01
    arms = {a["arm"]: a for a in e["arms"]}
    # the times are the declared delays: the approval at 8 comes later than at 0 and the score update lags it by its own delay
    ta0, ta8 = (arms[f"approval {a} / score update +0 / release +0"]["mean"]["time_approved"]["mean"] for a in (0, 8))
    assert ta8 > ta0 + 3
    s8 = arms["approval 0 / score update +8 / release +0"]["mean"]
    assert s8["time_score_updated"]["mean"] > s8["time_approved"]["mean"] + 3


# ------------------------------------------------------------------------------------------------ correspondence checks (docs/TRUTH_ERROR.md section 12)
def test_extinguishing_the_score_does_not_extinguish_a_binding_constraint():
    """the doc said this was tested; it was not: it is now. At every expiry period a subject under a constraint is still denied although the score has been reset"""
    base = cfg(seed=1, beta=0.06)
    held = 0
    for seed in range(1, 6):
        r = I.run(dataclasses.replace(base, seed=seed, score_expiry=10))
        assert r["series"]["score_extinguished"][-1] == 3.0  # the score is reset at 10, 20 and 30
        for rec in r["records"]:
            for t in (10, 20, 30):
                if rec[t]["locked"]:
                    held += 1
                    assert rec[t]["access"] is False
    assert held > 20
    a = np.mean([I.run(dataclasses.replace(base, seed=s, score_expiry=10))["summary"]["locked_fraction"] for s in range(1, 11)])
    b = np.mean([I.run(dataclasses.replace(base, seed=s))["summary"]["locked_fraction"] for s in range(1, 11)])
    assert abs(a - b) < 0.05  # the constraint at the end is about as common with the expiry as without it


def test_a_correct_classification_still_lowers_the_real_state_of_the_subjects_it_correctly_denies():
    """predictive correctness is not institutional direction: with an accurate classifier the subjects who are unfavourable at the start end lower with the score than with a lottery (through the resource feedback)"""
    acc = cfg(beta=0.06, signal_sensor=dataclasses.replace(I.Config().signal_sensor, noise_sigma=0.05))
    d_fav, d_unfav = [], []
    for seed in range(1, 11):
        s = I.run(dataclasses.replace(acc, seed=seed))
        lot = I.run(dataclasses.replace(acc, seed=seed, use_score=False))
        assert s["summary"]["classification_correct"] > 0.97   # the classification is accurate
        for rs, rl in zip(s["records"], lot["records"], strict=True):
            delta = (rs[-1]["reference_z"] - rs[0]["reference_z"]) - (rl[-1]["reference_z"] - rl[0]["reference_z"])
            (d_fav if rs[0]["reference_z"] > 0 else d_unfav).append(delta)
    assert np.mean(d_unfav) < -0.5 and np.mean(d_fav) > 0.5   # the score widens the gap between the two groups although it classifies them correctly


# ------------------------------------------------------------------------------------------------ the complementary metrics (docs/TRUTH_ERROR.md section 12.6)
def test_the_complementary_metrics_are_computed_over_every_subject_with_stated_denominators():
    from xzr.truth_error.process import COMPLEMENT_METRICS

    r = I.run(I.Config(seed=2, n=12, periods=40, lock_after=4, beta=0.06))   # n = 12: every subject is a sample subject with a full record
    c = r["process"]["complement"]
    assert set(c) == set(COMPLEMENT_METRICS) and all({"denominator", "period", "unit"} <= set(v) for v in COMPLEMENT_METRICS.values())
    z0 = np.array([rs[0]["reference_z"] for rs in r["records"]])
    dz = np.array([rs[-1]["reference_z"] - rs[0]["reference_z"] for rs in r["records"]])
    un = z0 <= 0
    # the metric is z after the last update minus z0; the record of the last period holds z before that update, so the two differ by one period's change (at most beta/2 plus noise)
    assert c["state_change_unfav"] == pytest.approx(dz[un].mean(), abs=0.06) and c["state_change_fav"] == pytest.approx(dz[~un].mean(), abs=0.06)
    assert c["state_gap_change"] == pytest.approx(c["state_change_fav"] - c["state_change_unfav"])
    acc = np.array([[x["access"] for x in rs] for rs in r["records"]])
    assert c["denial_rate_late_unfav"] == pytest.approx(1.0 - acc[un][:, -10:].mean())
    # the primary metrics are untouched: the same keys, and the complement is a separate record
    assert set(r["process"]["metrics"]) == set(X2.PRIMARY2) | {"recovery_censored_share"}


def test_the_change_of_the_real_state_moves_only_through_the_resource_feedback(saved2):
    e = saved2["experiments"]["EXP-TE16"]
    arms = {a["arm"]: a["mean"] for a in e["arms"]}
    m = lambda arm, k: arms[arm][k]["mean"]  # noqa: E731
    acc = "score, accurate sensor (noise 0.05)"
    b0, b3, b12 = (next(a for a in arms if a.startswith(f"score, accurate sensor, {t}")) for t in ("no feedback", "beta 0.03", "beta 0.12"))
    assert abs(m(b0, "state_change_unfav")) < 0.02 and abs(m(b0, "state_gap_change")) < 0.1   # beta 0: the score changes who is denied, not the states
    assert m(b3, "state_change_unfav") / m(acc, "state_change_unfav") == pytest.approx(0.5, abs=0.1) and m(b12, "state_change_unfav") / m(acc, "state_change_unfav") == pytest.approx(2.0, abs=0.2)   # proportional to beta
    # the correctly denied are not worse off than the randomly denied: the harm per denied subject is the same, the score concentrates it
    c = _contrast(e, "accurate score minus lottery", "state_change_unfav_denied")
    assert c["class"] == "not detected" and abs(c["paired"]["mean"]) < 0.05
    for out, sign in (("state_change_unfav", -1), ("state_change_fav", 1), ("state_gap_change", 1)):
        x = _contrast(e, "accurate score minus lottery", out)
        assert x["class"] == "replicated" and x["paired"]["mean"] * sign > 0.5, out
    assert _contrast(e, "accurate score minus full access", "state_change_unfav")["paired"]["mean"] < -2.0


def test_the_saved_complement_experiment_is_the_one_the_code_produces(saved2):
    again, old = X2.REGISTRY2["EXP-TE16"](), saved2["experiments"]["EXP-TE16"]
    assert again["protocol_digest"] == old["protocol_digest"]
    for a, b in zip(again["arms"], old["arms"], strict=True):
        assert a["result_digest_seed1"] == b["result_digest_seed1"]
        for k in old["primary_outcomes"]:
            assert a["mean"][k] == b["mean"][k], (a["arm"], k)


# ------------------------------------------------------------------------------------------------ phase 4: guarantees, support, P1-P3, the statistics of EXP-TE16
DEFAULTS4 = dict(resource_floor=0.0, denial_cap=None, interim_access=False, release_support=0.0, support_rule="none", support_amount=0.1, support_capacity=None, resources_start=0.5, z_shift=0.0)


def test_the_phase_4_settings_at_their_defaults_change_nothing_and_every_saved_phase_2_arm_still_reproduces(saved2):
    a, b = I.run(cfg(seed=4)), I.run(cfg(seed=4, **DEFAULTS4))
    assert a["result_digest"] == b["result_digest"] and a["target_state_digest"] == b["target_state_digest"]
    n = 0
    for eid, e in saved2["experiments"].items():
        if eid in ("EXP-TE17", "EXP-TE18"):
            continue   # these are the experiments that add the settings; their arms are checked by the reproduction test below
        by = {r["arm"]: r["result_digest_seed1"] for r in e["arms"]}
        for name, conf in e["arm_configs"].items():
            assert I.run(config_from({"config": {**conf, "seed": 1}}))["result_digest"] == by[name], (eid, name)
            n += 1
    assert n > 100


def test_the_guarantee_and_support_mechanisms_do_what_they_declare():
    r = I.run(cfg(seed=2, resource_floor=0.3))
    assert min(x["resources"] for rs in r["records"] for x in rs) >= 0.3 - 1e-9   # resources never fall below the floor
    r = I.run(cfg(seed=2, denial_cap=3))
    for rs in r["records"]:
        run_len = 0
        for x in rs:
            run_len = 0 if x["access"] else run_len + 1
            assert run_len <= 3   # no subject is denied for more than the cap in a row
    assert any(x["guarantee_access"] for rs in r["records"] for x in rs)
    p = I.run(cfg(seed=2, support_rule="low_score", support_amount=0.12, support_capacity=0.1))["process"]["guarantee"]
    assert p["support_units_per_subject"] <= 0.12 * 0.1 * 40 + 1e-9 and p["capacity_binding_periods"] > 0   # a capacity of 10 % bounds the cost and is reached
    none = I.run(cfg(seed=2))["process"]["guarantee"]
    assert none["support_units_per_subject"] == 0.0 and none["support_share_to_unfav"] is None
    # access kept pending a correction: with the audit on, subjects between a finding and its approval are not denied
    kw = dict(seed=2, **{**PROC, "approval_delay": 6, "request_delay": 1})
    a, b = I.run(cfg(**kw)), I.run(cfg(**kw, interim_access=True))
    assert b["process"]["guarantee"]["guarantee_access_periods_per_subject"] > 0 and b["process"]["metrics"]["denial_rate_late_fav"] <= a["process"]["metrics"]["denial_rate_late_fav"]


def test_with_no_feedback_the_real_state_depends_on_no_institutional_setting():
    """an intervention on the observation, the classifier, the threshold or a guarantee cannot change the subjects' states unless resources feed back: the causal structure of the model, checked by the target-state digest"""
    base = cfg(seed=3, beta=0.0)
    ref = I.run(base)["target_state_digest"]
    for kw in ({"classifier": "pose_rule"}, {"tau_a": 0.4}, {"signal_sensor": dataclasses.replace(base.signal_sensor, view_angle=40.0)}, {"resource_floor": 0.3}, {"support_rule": "denied"}, {"denial_cap": 3}, {"use_score": False}, {"lock_after": None}):
        assert I.run(dataclasses.replace(base, **kw))["target_state_digest"] == ref, kw
    assert I.run(dataclasses.replace(base, beta=0.06))["target_state_digest"] != ref   # with feedback the institution's access changes the state


def test_the_change_of_state_of_a_subject_denied_or_granted_throughout_is_fixed_by_the_constants(saved2):
    """by construction: beta x the sum of (resources - 0.5). The saved lottery arm (denied half of the time, always the same half) and full access reproduce it; an experiment only finds WHO is denied"""
    c = X2.NO_PROCESS
    den, gra = X2.resource_path_change(c, True), X2.resource_path_change(c, False)
    assert den == pytest.approx(-1.152, abs=1e-6) and gra == pytest.approx(1.152, abs=1e-6)
    e = saved2["experiments"]["EXP-TE16"]
    arms = {a["arm"]: a["mean"] for a in e["arms"]}
    lot, full = arms["lottery: no score, access for half at random"], arms["full access: no score, access for everyone"]
    assert lot["state_change_unfav_denied"]["mean"] == pytest.approx(den, abs=0.03) and full["state_change_unfav"]["mean"] == pytest.approx(gra, abs=0.03)
    # beta, floor and gain/loss enter only through this path: the saved arms at beta 0.03 and 0.12 are the same path scaled
    for beta, arm in ((0.03, "score, accurate sensor, beta 0.03"), (0.12, "score, accurate sensor, beta 0.12")):
        scaled = X2.resource_path_change(dataclasses.replace(c, beta=beta), True)
        assert arms[arm]["state_change_unfav_denied"]["mean"] == pytest.approx(scaled, abs=0.05 * abs(scaled) + 0.02), arm


def test_the_statistics_of_exp_te16_are_one_run_per_seed_with_the_interval_stated(saved2):
    e = saved2["experiments"]["EXP-TE16"]
    vals = {r["arm"]: r["values"] for r in e["arms"]}
    acc, lot, full = "score, accurate sensor (noise 0.05)", "lottery: no score, access for half at random", "full access: no score, access for everyone"
    s = X2.paired_summary(vals[acc]["state_change_unfav"], vals[lot]["state_change_unfav"])
    assert s["n"] == 20 and s["mean"] == pytest.approx(-1.134, abs=0.002) and s["se"] == pytest.approx(0.031, abs=0.002)   # 20 seeds, one run per seed: not 1200 subjects
    assert s["sd"] == pytest.approx(s["se"] * 20 ** 0.5) and s["ci95"][0] < s["mean"] < s["ci95"][1] and (s["ci95"][1] - s["ci95"][0]) / 2 == pytest.approx(2.093 * s["se"], rel=0.01)
    c2 = _contrast(e, "accurate score minus lottery", "state_change_unfav")
    assert c2["paired_seeds_21_40"]["mean"] == pytest.approx(-1.104, abs=0.002) and c2["paired_seeds_21_40"]["se"] == pytest.approx(0.028, abs=0.002)
    d = X2.paired_summary(vals[acc]["state_change_unfav_denied"], vals[lot]["state_change_unfav_denied"])
    assert d["mean"] == pytest.approx(-0.008, abs=0.002) and d["se"] == pytest.approx(0.004, abs=0.001) and d["ci95"][0] < 0 < d["ci95"][1] + 0.02
    f = X2.paired_summary(vals[acc]["state_change_unfav"], vals[full]["state_change_unfav"])
    g = X2.paired_summary(vals[acc]["state_gap_change"], vals[lot]["state_gap_change"])
    assert f["mean"] == pytest.approx(-2.29, abs=0.005) and g["mean"] == pytest.approx(2.305, abs=0.005)
    b0 = X2.paired_summary(vals["score, accurate sensor, no feedback of resources to the state (beta 0)"]["state_change_unfav"], vals[lot]["state_change_unfav"])
    assert abs(b0["mean"]) < 2 * b0["se"]   # beta 0: no difference
    arms = {r["arm"]: r["mean"]["state_change_unfav"]["mean"] for r in e["arms"]}
    assert [round(arms[f"score, accurate sensor, beta {b}"], 2) for b in (0.03, 0.12)] == [-0.57, -2.27] and round(arms[acc], 2) == -1.14


def test_p1_p2_p3_as_measured_by_the_saved_decomposition(saved2):
    e = saved2["experiments"]["EXP-TE17"]
    # P1: an accurate classification (correct in every period but a few thousandths) still has large consequences, and the consequence is set by other settings, not by the accuracy
    acc_cc = next(a for a in e["arms"] if a["arm"] == "classifier noise 0.05")["mean"]["classification_correct"]["mean"]
    assert acc_cc > 0.995
    sc = {a["arm"]: a["mean"]["state_change_unfav"]["mean"] for a in e["arms"]}
    assert sc["accurate, beta 0.0"] == pytest.approx(0.0, abs=0.02) and sc["accurate, beta 0.12"] < 2 * sc["classifier noise 0.05"] * 0.95 and sc["classifier noise 0.05"] < -1.0   # accuracy is the same, the consequence runs from 0 to -2.3 with beta
    # P2: a disadvantage without classification error: denial and lost resources need no feedback, the change of state needs it
    c = _contrast(e, "P2: accurate, no feedback minus lottery", "denial_rate_late_unfav")
    assert c["class"] == "replicated" and c["paired"]["mean"] > 0.3
    assert _contrast(e, "P2: accurate, no feedback minus lottery", "state_change_unfav")["class"] == "not detected"
    # P3: improving the accuracy moves denial from the favourable to the not favourable and widens the gap; the interaction with the feedback is the whole effect
    for out, sign in (("denial_rate_late_fav", -1), ("denial_rate_late_unfav", 1), ("state_change_unfav", -1), ("state_gap_change", 1)):
        x = _contrast(e, "P3: improving the accuracy", out)
        assert x["class"] == "replicated" and x["paired"]["mean"] * sign > 0, out
    i1 = _contrast(e, "interaction: accuracy x feedback", "state_change_unfav")
    p3 = _contrast(e, "P3: improving the accuracy", "state_change_unfav")
    assert i1["paired"]["mean"] == pytest.approx(p3["paired"]["mean"], abs=0.02)   # at beta 0 accuracy changes no state: the effect exists only through the feedback


def test_the_manufactured_accuracy_the_institution_produces_in_what_it_classifies(saved2):
    """with the feedback the subjects are pushed away from the boundary, so the same classifier is measured as more accurate; protecting the states lowers the measured accuracy again"""
    e = saved2["experiments"]["EXP-TE17"]
    cc = {a["arm"]: a["mean"]["classification_correct"]["mean"] for a in e["arms"]}
    assert cc["classifier noise 1.6"] < cc["noisy, beta 0.0"] + 0.1 and cc["noisy classifier (noise 0.8), the base"] > cc["noisy, beta 0.0"] + 0.05
    g = saved2["experiments"]["EXP-TE18"]
    gc = {a["arm"]: a["mean"]["classification_correct"]["mean"] for a in g["arms"]}
    assert gc["noisy: support to the denied 0.12"] < gc["noisy: no guarantee"] - 0.02   # the guarantee improves the states and the measured accuracy falls


def test_the_guarantees_improve_some_things_not_others_and_cost_resources_as_saved(saved2):
    e = saved2["experiments"]["EXP-TE18"]
    arms = {a["arm"]: a["mean"] for a in e["arms"]}
    m = lambda arm, k: arms[arm][k]["mean"]  # noqa: E731
    # a resource floor improves the state of the not favourable group and, for an accurate classifier, does not change who is denied
    assert _contrast(e, "accurate: resource floor 0.3 minus no guarantee", "state_change_unfav")["paired"]["mean"] > 0.5
    assert _contrast(e, "accurate: resource floor 0.3 minus no guarantee", "denial_rate_late_unfav")["paired"]["mean"] == pytest.approx(0.0, abs=0.01)
    # support is bounded by its capacity: the cost falls and so does the improvement
    full_c, cap_c = m("accurate: support to the low score 0.12", "support_units_per_subject"), m("accurate: support to the low score 0.12, capacity 10%", "support_units_per_subject")
    assert cap_c < full_c / 3 and _contrast(e, "accurate: support to the low score 0.12, capacity 10% minus no guarantee", "state_change_unfav")["paired"]["mean"] < 0.2
    # the accurate classifier identifies the recipients better (precision) and yet the not favourable group does better with the noisy one under the same support
    assert m("accurate: support to the low score 0.12", "support_share_to_unfav") > m("noisy: support to the low score 0.12", "support_share_to_unfav")
    assert _contrast(e, "accurate classification as the identifier", "state_change_unfav")["paired"]["mean"] < 0
    # conditions that did not improve, kept: a recovery measure after a release leaves the gap unchanged for the noisy classifier; a long cap of 6 changes very little
    assert _contrast(e, "noisy: process + recovery support after the release 0.3 minus the process alone", "state_gap_change")["class"] == "not detected"
    assert _contrast(e, "accurate: denial cap 6 minus no guarantee", "state_change_unfav")["paired"]["mean"] < 0.05
    # interaction of the two process guarantees: they substitute for each other (the combined effect is smaller than the sum)
    assert _contrast(e, "noisy: interaction of access-kept and recovery support", "state_change_unfav")["paired"]["mean"] < 0


def test_the_api_validates_the_hypothetical_guarantee_settings():
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod

    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    ok = c.post("/api/truth-error/run", json={"config": {"seed": 2, "resource_floor": 0.3, "support_rule": "low_score", "support_capacity": 0.1, "denial_cap": 3, "interim_access": True}})
    assert ok.status_code == 200 and ok.json()["process"]["guarantee"]["support_units_per_subject"] > 0
    for bad in ({"support_rule": "everyone"}, {"resource_floor": 1.5}, {"denial_cap": 0}, {"support_capacity": -0.1}, {"interim_access": "yes"}, {"z_shift": 9}, {"resources_start": 2}):
        assert c.post("/api/truth-error/run", json={"config": bad}).status_code == 422, bad
    assert c.get("/api/truth-error/spec").json()["support_rules"] == ["none", "denied", "low_score"]
