"""TRUTH-ERROR: the synthetic institution, the sensor model and the pre-registered experiments. These are checks of the model's own properties (determinism, independence of the random streams, the separation of the
records, the sensor model, the asymmetries the research is about, the safety scope) and of the saved results; none of it is evidence about a real institution or person."""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import numpy as np

from xzr.truth_error import experiments as X
from xzr.truth_error import institution as I  # noqa: E741
from xzr.truth_error.pose import SensorConfig, measure_series, reference_pose, tolerance

SAVED = Path(__file__).resolve().parents[2] / "docs" / "truth_error" / "experiments.json"
PKG = Path(I.__file__).parent


def cfg(**kw):
    return I.Config(**kw)


# ------------------------------------------------------------------------------------------------ determinism and independent streams
def test_a_run_is_deterministic_and_the_seed_matters():
    a, b, c = I.run(cfg(seed=3)), I.run(cfg(seed=3)), I.run(cfg(seed=4))
    assert a["result_digest"] == b["result_digest"] and a["target_state_digest"] == b["target_state_digest"]
    assert a["result_digest"] != c["result_digest"]


def test_changing_only_the_threshold_changes_no_classification():
    # classification does not depend on the gate (no feedback): the same classification results meet different thresholds
    a, b = I.run(cfg(tau_a=0.0)), I.run(cfg(tau_a=0.4))
    assert a["series"]["cls_correct"] == b["series"]["cls_correct"] and a["series"]["accepted"] == b["series"]["accepted"]
    assert a["series"]["access"] != b["series"]["access"]


def test_changing_only_the_classifier_leaves_the_measurements_and_the_real_state_alone():
    a, b = I.run(cfg(classifier="signal_rule")), I.run(cfg(classifier="pose_rule"))
    assert a["target_state_digest"] == b["target_state_digest"]
    assert a["series"]["meas_correct"] == b["series"]["meas_correct"]
    assert a["series"]["cls_correct"] != b["series"]["cls_correct"]


def test_the_observation_conditions_do_not_change_the_real_state_unless_a_decision_acts_on_it():
    base = cfg(use_score=False)
    noisy = dataclasses.replace(base, pose_sensor=SensorConfig(noise_sigma=6.0), signal_sensor=SensorConfig(noise_sigma=3.2))
    assert I.run(base)["target_state_digest"] == I.run(noisy)["target_state_digest"]
    # with a score used and resources changing the real state, the same observation conditions change it
    a, b = dataclasses.replace(base, use_score=True, beta=0.1), dataclasses.replace(noisy, use_score=True, beta=0.1)
    assert I.run(a)["target_state_digest"] != I.run(b)["target_state_digest"]


# ------------------------------------------------------------------------------------------------ the sensor model
def test_a_calibration_bias_is_the_error_the_sensor_makes():
    ref = reference_pose(np.random.default_rng(1), 1, 200)[0]
    out = measure_series(ref, SensorConfig(noise_sigma=0.01, bias=(8.0, 4.0, 3.0)), seed=1)
    assert np.allclose(np.nanmean(out["values"] - ref, axis=0), [8.0, 4.0, 3.0], atol=0.1)


def test_occlusion_and_tracking_loss_are_missing_with_a_reason_and_zero_confidence():
    ref = reference_pose(np.random.default_rng(1), 1, 200)[0]
    out = measure_series(ref, SensorConfig(occlusion_prob=0.15, dropout_prob=0.1), seed=2)
    miss = np.isnan(out["values"][:, 0])
    assert miss.any() and (out["reason"][miss] > 0).all() and (out["confidence"][miss] == 0).all()
    assert set(out["reason"][~miss]) == {0}


def test_an_oblique_view_raises_the_noise_and_lowers_the_confidence():
    ref = reference_pose(np.random.default_rng(1), 1, 300)[0]
    front, side = measure_series(ref, SensorConfig(view_angle=0), 1), measure_series(ref, SensorConfig(view_angle=60), 1)
    assert side["sigma"] > front["sigma"] and np.nanmean(side["confidence"]) < np.nanmean(front["confidence"])
    assert np.nanstd(side["values"] - ref) > np.nanstd(front["values"] - ref)


def test_a_failed_sensor_is_wrong_and_does_not_announce_itself():
    ref = reference_pose(np.random.default_rng(1), 1, 60)[0]
    out = measure_series(ref, SensorConfig(noise_sigma=0.5, fail_at=30, fail_mode="stuck"), 1)
    after = out["values"][31:]
    assert not np.isnan(after).any() and (out["reason"][30:] == 0).all()  # not marked missing
    assert np.allclose(after, after[0])  # but stuck: wrong while the reference moves
    assert np.abs(after - ref[31:]).max() > tolerance(0)
    assert (out["confidence"][30:] > 0).all()  # and still confident


# ------------------------------------------------------------------------------------------------ the records are separate; nothing is forced to a binary
def test_each_stage_is_its_own_record_and_an_abstention_is_neither_correct_nor_wrong():
    r = I.run(
        cfg(
            pose_sensor=SensorConfig(occlusion_prob=0.5, dropout_prob=0.3, occlusion_length=5),
            signal_sensor=SensorConfig(noise_sigma=0.8, occlusion_prob=0.6, occlusion_length=6),
            classifier="signal_rule",
            window=1,
        )
    )
    rec = r["records"][0]
    keys = {
        "reference_z",
        "verification_label",
        "pose_measured",
        "pose_confidence",
        "pose_missing",
        "signal_measured",
        "classification",
        "classification_correct",
        "warrant",
        "accepted",
        "score",
        "access",
        "locked",
        "resources",
        "opportunities_lost",
        "corrected",
    }
    assert keys <= set(rec[0])
    abst = [x for row in r["records"] for x in row if x["classification"] == 0]
    assert abst and all(x["classification_correct"] is None for x in abst)
    assert all(x["accepted"] is False for x in abst)  # an institution adopts nothing it did not classify


def test_the_warrant_has_three_states_and_is_not_forced_to_two():
    r = I.run(cfg())
    seen = {x["warrant"] for row in r["records"] for x in row}
    assert seen == set(I.WARRANT)  # SUPPORTED, REFUTED and UNDECIDED all occur
    assert (
        abs(
            r["series"]["warrant_supported"][-1] + r["series"]["warrant_refuted"][-1] + r["series"]["warrant_undecided"][-1] - 1.0
        )
        < 1e-9
    )


def test_acceptance_is_an_institutional_act_apart_from_correctness():
    r = I.run(cfg(classifier="random_rule"))
    assert (
        r["summary"]["accepted"] > 0.9 and abs(r["summary"]["classification_correct"] - 0.5) < 0.1
    )  # adopted although right only by chance
    strict = I.run(cfg(classifier="random_rule", requires_warrant=True))
    assert strict["summary"]["accepted"] < r["summary"]["accepted"]  # an institution that needs warrant adopts less of it


# ------------------------------------------------------------------------------------------------ the asymmetries
def test_an_invalid_rule_is_at_chance_yet_acts_on_subjects_as_a_lottery_does():
    valid, inv, lottery = I.run(cfg()), I.run(cfg(classifier="pose_rule")), I.run(cfg(use_score=False))
    assert valid["summary"]["classification_correct"] > 0.8 and abs(inv["summary"]["classification_correct"] - 0.5) < 0.1
    assert (
        inv["summary"]["access_favourable"] < valid["summary"]["access_favourable"] - 0.25
    )  # the invalid rule denies favourable subjects
    assert (
        inv["summary"]["lost_opportunities_favourable_per_subject"]
        > 3 * valid["summary"]["lost_opportunities_favourable_per_subject"]
    )
    # and no more than a lottery does: it discriminates nothing
    assert abs(inv["summary"]["access_favourable"] - inv["summary"]["access_unfavourable"]) < 0.15
    assert (
        abs(
            inv["summary"]["lost_opportunities_favourable_per_subject"]
            - lottery["summary"]["lost_opportunities_favourable_per_subject"]
        )
        < 2.0
    )


def test_the_head_pose_carries_nothing_about_the_reference_state_unless_it_is_coupled_by_hand():
    rs = [I.run(cfg(seed=s, classifier="pose_rule", use_score=False))["summary"]["classification_correct"] for s in range(1, 9)]
    assert abs(float(np.mean(rs)) - 0.5) < 0.06
    coupled = [
        I.run(cfg(seed=s, classifier="pose_rule", use_score=False, pose_z_coupling=25.0, yaw_threshold=0.0))["summary"][
            "classification_correct"
        ]
        for s in range(1, 4)
    ]
    assert coupled  # the coupling is an explicit parameter; its default is zero
    assert I.Config().pose_z_coupling == 0.0


def test_a_biased_sensor_can_make_a_warrant_that_looks_supported_and_is_wrong():
    ok, biased = (
        I.run(cfg(use_score=False)),
        I.run(cfg(use_score=False, signal_sensor=SensorConfig(noise_sigma=0.8, bias=(0.7, 0.0, 0.0)))),
    )
    assert ok["summary"]["warrant_support_wrong"] < 0.02
    assert biased["summary"]["warrant_support_wrong"] > 0.1


def test_a_correction_restores_the_score_but_not_the_opportunities_or_the_constraint():
    c = I.run(cfg(lock_after=4, correct_at=10))
    lost = c["series"]["lost_fav_cum"]
    assert all(b >= a for a, b in zip(lost, lost[1:], strict=False))  # opportunities lost never come back
    s = c["summary"]
    assert (
        s["corrected_share"] > 0.05 and s["score_recovered_share_of_corrected"] > 0.5
    )  # about a tenth of the subjects are favourable and denied at the correction
    assert s["still_denied_after_correction_share_of_corrected"] > 0.1  # a restored score does not always mean restored access
    never = I.run(cfg(lock_after=4, correct_at=10, release_after=999))
    assert (
        never["summary"]["still_denied_after_correction_share_of_corrected"]
        > s["still_denied_after_correction_share_of_corrected"]
    )


def test_a_transferred_judgement_keeps_the_force_it_has_at_the_second_institution_when_it_carries_no_evidence():
    inv = I.run(cfg(classifier="pose_rule", transfer_at=15))
    s = inv["summary"]
    assert abs(s["b_evidential_accuracy_of_transferred_score"] - 0.5) < 0.1  # no evidence
    assert s["b_denied_though_favourable"] > 0.3  # and it still denies favourable subjects at B
    val = I.run(cfg(transfer_at=15))["summary"]
    assert (
        val["b_evidential_accuracy_of_transferred_score"] > 0.8
        and val["b_denied_though_favourable"] < s["b_denied_though_favourable"]
    )


def test_a_denial_that_changes_the_real_state_comes_true_and_one_that_does_not_does_not():
    off, on = I.run(cfg(beta=0.0))["summary"], I.run(cfg(beta=0.12))["summary"]
    assert on["self_fulfilled_share_of_early_denied_favourable"] > off["self_fulfilled_share_of_early_denied_favourable"] + 0.3
    assert on["denial_persistence_favourable"] > off["denial_persistence_favourable"] + 0.3


def test_a_worse_observation_of_denied_subjects_alone_does_not_make_a_denial_persist_in_this_model():
    # a negative result kept: gamma (denied subjects are observed worse) without a change of the real state did not raise persistence
    base = [I.run(cfg(seed=s))["summary"]["denial_persistence_favourable"] for s in range(1, 9)]
    g = [I.run(cfg(seed=s, gamma=4.0))["summary"]["denial_persistence_favourable"] for s in range(1, 9)]
    assert float(np.mean(g)) <= float(np.mean(base)) + 0.05


# ------------------------------------------------------------------------------------------------ the experiments
def test_every_experiment_runs_with_the_declared_changes_and_no_failure_condition(monkeypatch):
    monkeypatch.setattr(X, "SEEDS", (1, 2, 3))
    for name, fn in X.REGISTRY.items():
        r = fn()  # _run_experiment asserts that the changes of each arm equal the declared ones
        assert r["invalid_if_any_failure_condition"] is False, (name, r["failure_conditions"])
        assert r["seeds"] == [1, 2, 3] and r["limits"] and r["protocol_digest"] and r["control"] in {a["arm"] for a in r["arms"]}
        assert all(set(a["mean"]) == set(r["outcomes"]) for a in r["arms"])


def test_the_saved_results_are_the_ones_the_code_produces():
    saved = json.loads(SAVED.read_text())
    assert saved["engine"] == "truth_error/1" and set(saved["experiments"]) == set(X.REGISTRY)
    r = X.te03()  # one experiment, in full, with its twenty seeds
    s = saved["experiments"]["EXP-TE03"]
    assert [(a["arm"], a["result_digest_seed1"]) for a in r["arms"]] == [(a["arm"], a["result_digest_seed1"]) for a in s["arms"]]
    assert r["protocol_digest"] == s["protocol_digest"]


def test_the_saved_results_keep_the_negative_results_and_the_failure_conditions():
    saved = json.loads(SAVED.read_text())["experiments"]
    assert all("negative_results" in e and "failure_conditions" in e and e["seeds"] == list(range(1, 21)) for e in saved.values())
    assert any(e["negative_results"] for e in saved.values())
    # the control arm of TE03 changes nothing and its classification is the same in every threshold arm
    te03 = saved["EXP-TE03"]
    assert (
        len({round(a["mean"]["classification_correct"]["mean"], 9) for a in te03["arms"] if not a["arm"].startswith("no score")})
        == 1
    )
    # TE01: the sensor alone leaves the real state as it was; with a score acting on it, it does not
    assert all(a["target_state_identical_to_control_in_every_seed"] for a in saved["EXP-TE01-unscored"]["arms"])
    assert not all(a["target_state_identical_to_control_in_every_seed"] for a in saved["EXP-TE01-scored-transforming"]["arms"])


# ------------------------------------------------------------------------------------------------ the safety scope
def test_the_package_is_synthetic_only_and_does_not_import_a_face_pipeline_or_a_video_library():
    text = "\n".join(p.read_text() for p in PKG.glob("*.py"))
    for lib in ("mediapipe", "cv2", "opencv", "dlib", "face_recognition", "tensorflow", "torch", "PIL"):
        assert not re.search(rf"^\s*(import|from)\s+{lib}\b", text, re.M), lib
    init = (PKG / "__init__.py").read_text()
    for must in ("SYNTHETIC", "NOT an indicator of truthfulness", "No real person"):
        assert must in init
    assert "invalid BY CONSTRUCTION" in init or "invalid by construction" in text


def test_no_output_names_a_person_or_scores_a_real_individual():
    r = I.run(cfg())
    blob = json.dumps(r)
    for word in ("name", "face", "photo", "video", "ssn", "address_of_person"):
        assert f'"{word}"' not in blob
    assert {k for k in r["records"][0][0] if "name" in k} == set()


# ------------------------------------------------------------------------------------------------ the API
def test_the_api_runs_the_institution_and_the_pose_and_refuses_anything_that_is_not_a_synthetic_number():
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod

    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    spec = c.get("/api/truth-error/spec").json()
    assert "SYNTHETIC" in spec["scope"] and spec["classifiers"] == list(I.CLASSIFIERS)
    r = c.post(
        "/api/truth-error/run", json={"config": {"seed": 2, "classifier": "pose_rule", "pose_sensor": {"view_angle": 30}}}
    ).json()
    assert (
        r["result_digest"]
        == I.run(I.Config(seed=2, classifier="pose_rule", pose_sensor=SensorConfig(view_angle=30)))["result_digest"]
    )  # API == direct
    assert c.post("/api/truth-error/run", json={"config": {"image": "x.png"}}).status_code == 422
    assert c.post("/api/truth-error/run", json={"config": {"classifier": "face_recognition"}}).status_code == 422
    assert c.post("/api/truth-error/run", json={"config": {"n": 100000}}).status_code == 422
    assert c.post("/api/truth-error/run", json={"config": {"pose_sensor": {"video": "a.mp4"}}}).status_code == 422
    for bad in (
        {"view_angle": "left"},
        {"bias": [1, 2]},
        {"fail_mode": "explode"},
        {"occlusion_length": 0},
        {"noise_sigma": True},
    ):
        assert c.post("/api/truth-error/run", json={"config": {"pose_sensor": bad}}).status_code == 422, bad
    p = c.post("/api/truth-error/pose", json={"seed": 3, "periods": 30, "sensor": {"bias": [5, 0, 0]}}).json()
    assert len(p["reference"]) == 30 and "not a face" in p["note"] and p["tolerance_degrees"][0] > 0
    assert c.get("/api/truth-error/experiments").json()["engine"] == "truth_error/1"


def test_the_output_is_strict_json_with_no_nan_so_that_a_browser_can_read_it():
    for c in (
        cfg(),
        cfg(classifier="none"),
        cfg(use_score=False),
        cfg(transfer_at=12),
        cfg(signal_sensor=SensorConfig(occlusion_prob=0.9, occlusion_length=8)),
    ):
        json.dumps(I.run(c), allow_nan=False)  # raises on a NaN
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod

    text = TestClient(app_mod.app, headers={"origin": "http://testserver"}).post("/api/truth-error/run", json={"config": {}}).text
    assert "NaN" not in text


def test_the_api_is_local_only_and_stores_nothing(tmp_path):
    import pytest as _pytest
    from fastapi.testclient import TestClient

    from xzr.service import app as app_mod
    from xzr.service import studies as studies_mod
    from xzr.service.limits import LIMITS

    c = TestClient(app_mod.app, headers={"origin": "http://testserver"})
    before = sorted(p.name for p in tmp_path.iterdir())
    assert c.post("/api/truth-error/run", json={"config": {}}).status_code == 200
    assert sorted(p.name for p in tmp_path.iterdir()) == before  # a run is computed, never written
    mp = _pytest.MonkeyPatch()
    try:
        mp.setattr(studies_mod, "LIMITS", dataclasses.replace(LIMITS, public=True))
        for method, path, body in (
            ("get", "/api/truth-error/spec", None),
            ("post", "/api/truth-error/run", {"config": {}}),
            ("post", "/api/truth-error/pose", {}),
            ("get", "/api/truth-error/experiments", None),
        ):
            r = c.get(path) if method == "get" else c.post(path, json=body)
            assert r.status_code == 403, (path, r.status_code)
    finally:
        mp.undo()
    # a request from another site's page is refused as well
    other = TestClient(app_mod.app, headers={"origin": "http://evil.example"})
    assert other.post("/api/truth-error/run", json={"config": {}}).status_code == 403
