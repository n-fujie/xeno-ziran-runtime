"""TEOO reconstruction and evidence: reference state, observation, estimate and reconstruction are separate; an estimate is never an observation; labels follow class and kind."""

from __future__ import annotations

import pytest

from xzr.teoo import evidence as EV
from xzr.teoo import provenance as P
from xzr.teoo import reconstruction as RC
from xzr.teoo import synthetic as SY
from xzr.teoo.timebase import Interpolation

CREATOR = {"name": "tester"}


def test_observation_estimate_and_reference_state_are_kept_apart():
    obs = P.seal({"x": 1}, provenance="SYNTHETIC", kind="OBSERVATION", creator=CREATOR, source={"kind": "generator", "description": "g", "declared_by": "t"})
    ref = P.seal({"x": 1}, provenance="SYNTHETIC", kind="REFERENCE_STATE", creator=CREATOR, source={"kind": "generator", "description": "g", "declared_by": "t"})
    est = RC.make_reconstruction([obs], method="kalman-smoother", creator=CREATOR, reconstruction_time_s=1.0, time_uncertainty_s=0.01, value={"knee_deg": 31.0}, uncertainty={"sd": 1.2})
    assert (obs["kind"], ref["kind"], est["kind"]) == ("OBSERVATION", "REFERENCE_STATE", "RECONSTRUCTION")
    assert len({obs["record_id"], ref["record_id"], est["record_id"]}) == 3
    assert est["provenance"] == "RECONSTRUCTED_ESTIMATE" and est["provenance"] != "MEASURED" and obs["provenance"] != "MEASURED"  # an observation of a synthetic world is not a measurement
    assert EV.classify(est)["label"].startswith("reconstruction (not an observation)") and EV.classify(obs)["label"].startswith("functional-test data")


def test_a_reconstruction_records_inputs_method_time_uncertainty_and_interpolation():
    m = P.seal({"x": 1}, provenance="MEASURED", kind="OBSERVATION", creator=CREATOR, source={"kind": "device", "description": "imu", "declared_by": "t"})
    interp = [Interpolation("linear", 0.40, 0.46, (20, 21), "a dropout of 60 ms between samples 20 and 21")]
    est = RC.make_reconstruction([m], method="linear-interpolation + model", creator=CREATOR, reconstruction_time_s=0.43, time_uncertainty_s=None, synchronised_inputs=False, value={"knee_deg": 12.0}, interpolation=interp,
                                 assumptions=["rigid segments"])
    rec = est["payload"]["reconstruction"]
    assert est["derived_from"] == [{"record_id": m["record_id"], "record_digest": m["record_digest"]}] and est["payload"]["inputs"][0]["provenance"] == "MEASURED"
    assert rec["method"] and rec["assumptions"] == ["rigid segments"] and rec["interpolation"][0]["method"] == "linear" and rec["interpolation"][0]["sample_indices"] == [20, 21]
    assert rec["time"]["kind"] == "RECONSTRUCTION" and rec["time"]["uncertainty_s"] is None and rec["time"]["inputs_synchronised"] is False  # unknown, not zero
    assert est["lineage_classes"] == ["MEASURED", "RECONSTRUCTED_ESTIMATE"] and est["transformations"][0]["interpolated"] is True
    with pytest.raises(ValueError):
        RC.make_reconstruction([m], method="", creator=CREATOR, reconstruction_time_s=0.0, time_uncertainty_s=0.0, value={})


def test_a_reconstruction_cannot_be_registered_as_measured():
    m = P.seal({"x": 1}, provenance="MEASURED", kind="OBSERVATION", creator=CREATOR, source={"kind": "device", "description": "imu", "declared_by": "t"})
    with pytest.raises(P.ProvenanceError):
        P.derive([m], payload={"y": 1}, provenance="MEASURED", kind="RECONSTRUCTION", creator=CREATOR, source={"kind": "device", "description": "x", "declared_by": "t"}, transformations=[{"method": "filtering", "preserves_provenance": True}])


def test_labels_follow_class_and_kind_and_no_record_is_evidence_by_itself():
    d = SY.make_demo()["records"][0]
    c = EV.classify(d)
    assert c["is_evidence"] is False and c["claim_status_hint"] == "implementation property" and "not evidence" in c["label"]
    m = P.seal({"x": 1}, provenance="MEASURED", kind="OBSERVATION", creator=CREATOR, source={"kind": "device", "description": "imu", "declared_by": "t"})
    cm = EV.classify(m)
    assert cm["label"] == "recorded observation" and cm["is_evidence"] is False and cm["claim_status_hint"] == "empirical observation (candidate)"
    concept = P.seal({"drawing": True}, provenance="CONCEPTUAL", kind="REFERENCE_STATE", creator=CREATOR, source={"kind": "researcher", "description": "a sketch"})
    assert "not a photograph" in EV.classify(concept)["note"]


def test_records_of_different_classes_are_not_aggregated_without_a_declaration():
    a = P.seal({"x": 1}, provenance="MEASURED", kind="OBSERVATION", creator=CREATOR, source={"kind": "device", "description": "imu", "declared_by": "t"})
    b = P.seal({"x": 1}, provenance="SYNTHETIC", kind="OBSERVATION", creator=CREATOR, source={"kind": "generator", "description": "g", "declared_by": "t"})
    assert EV.aggregate_guard([a, b])["allowed"] is False and EV.aggregate_guard([a, b], mixing_declared=True)["allowed"] is True and EV.aggregate_guard([a, a])["allowed"] is True
