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
