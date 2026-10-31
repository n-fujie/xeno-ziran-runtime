"""TEOO observation status and temporal reference: missing is not zero, unmeasured is not absent, several limits at once, unsynchronised data stay unpaired."""

from __future__ import annotations

import pytest

from xzr.teoo import status as ST
from xzr.teoo import timebase as TB
from xzr.teoo.status import Instrument, ObsStatus, Target


def test_a_missing_value_is_none_and_never_zero():
    s = ST.sample(None, ObsStatus.MISSING, cause_known=False)
    assert s["value"] is None and ST.validate_sample(s) == []
    zero = ST.sample(0.0, ObsStatus.MISSING, cause_known=False)
    assert {i.code for i in ST.validate_sample(zero)} == {"VALUE_WITHOUT_VALIDITY"}
    assert {i.code for i in ST.validate_sample(ST.sample(None, ObsStatus.MEASURED_VALID))} == {"VALID_WITHOUT_VALUE"}
    assert ST.validate_sample(ST.sample(0.0, ObsStatus.MEASURED_VALID)) == []  # a measured zero is a value; only a measurement can say 0


def test_unmeasured_and_absent_are_not_the_same_state():
    assert not any("ABSENT" in s or "NOT_EXIST" in s or "NONEXIST" in s for s in ST.STATUS_IDS)  # no status says that something does not exist
    inst = Instrument("imu", ("angle",), resolution=1.0, sampling_period_s=0.02, window_s=10.0, detection_limit=0.1, penetration=0.5)
    tgt = Target("angle", scale=5.0, phenomenon_period_s=2.0, amplitude=30.0, boundary_opacity=0.0)
    unmeasured = ST.assess(("angle",), inst, tgt, measured=False)
    assert unmeasured["status"] == "UNMEASURED" and unmeasured["causes"] == []  # could have been measured, was not
    measured = ST.assess(("angle",), inst, tgt, measured=True)
    assert measured["status"] == "MEASURED_VALID"
    below = ST.assess(("angle",), inst, Target("angle", scale=5.0, phenomenon_period_s=2.0, amplitude=0.01, boundary_opacity=0.0), measured=True)
    assert below["status"] == "SIGNAL_BELOW_THRESHOLD" and below["status"] != "UNMEASURED"  # measured and under the limit: a bound, not an absence
    s = ST.sample(None, ObsStatus.SIGNAL_BELOW_THRESHOLD, causes=["SIGNAL_BELOW_THRESHOLD"])
    assert "LIMIT_MISSING" in {i.code for i in ST.validate_sample(s)}  # it must state the detection limit it is below


def test_several_observation_limits_can_apply_at_once_and_none_is_dropped():
    inst = Instrument("slow-coarse", ("angle",), resolution=10.0, sampling_period_s=5.0, window_s=60.0, detection_limit=0.1, penetration=0.0)
    tgt = Target("angle", scale=1.0, phenomenon_period_s=2.0, amplitude=30.0, boundary_opacity=0.9)
    r = ST.assess(("angle",), inst, tgt, measured=True)
    assert set(r["causes"]) == {"BOUNDARY_INVISIBLE", "SCALE_MISMATCH", "TIME_WINDOW_MISMATCH"} and r["status"] == "BOUNDARY_INVISIBLE" and r["cause_known"]
    wrong = ST.assess(("angle", "emg"), Instrument("emg-only", ("emg",), 1, 0.001, 10, 0.1, 0.0), tgt, measured=True)
    assert wrong["status"] == "INSTRUMENT_MISMATCH"
    assert ST.assess(("emg",), inst, tgt, measured=True)["status"] == "UNMEASURABLE"  # no instrument of the configuration carries the channel
    st, causes = ST.combine([ObsStatus.TIME_WINDOW_MISMATCH, ObsStatus.SCALE_MISMATCH])
    assert st is ObsStatus.SCALE_MISMATCH and causes == ["SCALE_MISMATCH", "TIME_WINDOW_MISMATCH"]
    multi = ST.sample(None, ObsStatus.BOUNDARY_INVISIBLE, causes=r["causes"])
    assert ST.validate_sample(multi) == []


def test_an_unknown_cause_is_kept_unknown_and_no_reason_is_guessed():
    inst = Instrument("imu", ("angle",))  # no resolution, period, window, limit declared
    r = ST.assess(("angle",), inst, Target("angle"), measured=True)
    assert r["status"] == "UNKNOWN_CAUSE" and r["causes"] == [] and r["cause_known"] is False and {"scale", "time_window"} <= set(r["undetermined"])
    assert ST.assess(None, inst, Target("angle"), measured=False)["status"] == "UNKNOWN_CAUSE"  # even the configuration's channels are unknown
    asserted = ST.sample(None, ObsStatus.UNKNOWN_CAUSE, causes=["SCALE_MISMATCH"], cause_known=False)
    assert "CAUSE_ASSERTED" in {i.code for i in ST.validate_sample(asserted)}
    gap = ST.sample(None, ObsStatus.MISSING, causes=["SCALE_MISMATCH"], cause_known=False)
    assert "CAUSE_CONTRADICTION" in {i.code for i in ST.validate_sample(gap)}


def test_every_status_of_the_two_existing_observation_layers_is_mapped():
    from xzr.hpo.observe import REASONS
    from xzr.meos import analysis as A

    assert set(ST.FROM_HPO) == set(REASONS)
    meos_names = set(A.OBSERVABILITY_STATUSES) | set(A.OBSERVABILITY.values()) | set(A.OBSERVABILITY_V4.values())
    assert meos_names <= set(ST.FROM_MEOS), sorted(meos_names - set(ST.FROM_MEOS))
    for table in (ST.FROM_HPO, ST.FROM_MEOS):
        for name, (mapped, why) in table.items():
            assert (mapped is None or mapped in ST.STATUS_IDS) and why, name


def test_clock_synchronisation_uncertainty_is_kept_and_unsynchronised_data_are_not_paired():
    a = TB.ClockSync("imu", "lab", "shared-trigger", offset_s=0.010, uncertainty_s=0.002)
    b = TB.ClockSync("emg", "lab", "shared-trigger", offset_s=-0.004, uncertainty_s=0.003)
    res = TB.align([0.0, 0.1, 0.2], a, [0.0, 0.1, 0.2], b, tolerance_s=0.030)
    assert res["synchronised"] and len(res["pairs"]) == 3 and res["simultaneity_claim"] is False
    assert all(abs(p["uncertainty_s"] - (0.002**2 + 0.003**2) ** 0.5) < 1e-12 for p in res["pairs"])
    none = TB.align([0.0, 0.1], a, [0.0, 0.1], None, tolerance_s=0.030)
    assert not none["synchronised"] and none["pairs"] == [] and none["unpaired_b"] == [0, 1] and "no synchronisation record" in none["reason"]
    unknown = TB.ClockSync("emg", "lab", "none", offset_s=0.0, uncertainty_s=None)  # an offset without a known uncertainty is not a synchronisation
    assert not TB.align([0.0], a, [0.0], unknown, tolerance_s=1.0)["synchronised"] and TB.to_reference(1.0, unknown) == (None, None)
    other = TB.ClockSync("emg", "other-ref", "shared-trigger", offset_s=0.0, uncertainty_s=0.001)
    assert not TB.align([0.0], a, [0.0], other, tolerance_s=1.0)["synchronised"]
    tight = TB.align([0.0], a, [0.0], b, tolerance_s=0.001)  # tolerance below the combined uncertainty: not paired
    assert tight["pairs"] == [] and tight["unpaired_a"] == [0]
    assert TB.to_reference(1.0, a) == (1.010, 0.002)


def test_a_change_shorter_than_the_sampling_period_is_not_resolvable_and_not_absent():
    slow = TB.resolvable(1.0, 0.5)
    assert slow["resolvable"] is False and slow["status"] == "TIME_WINDOW_MISMATCH" and "not absent" in slow["note"]
    assert TB.resolvable(0.01, 0.5)["resolvable"] is True
    assert TB.resolvable(None, 0.5)["status"] == "UNKNOWN_CAUSE"
    it = TB.Interpolation("linear", 1.0, 2.0, (3, 4), "between samples 3 and 4").to_dict()
    assert it["method"] == "linear" and it["sample_indices"] == [3, 4]


def test_time_kinds_are_four_distinct_kinds():
    assert [k.value for k in TB.TimeKind] == ["DEVICE", "ACQUISITION", "INGESTION", "RECONSTRUCTION"]


@pytest.mark.parametrize("bad", ["", "X", "Measured_Valid"])
def test_an_unknown_status_is_refused(bad):
    assert {i.code for i in ST.validate_sample({"status": bad, "value": None})} == {"STATUS_UNKNOWN"}
