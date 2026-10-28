"""MEOS-0, fourth stage, observation: operational state, observed state and observability status are three separate things, with the fourth stage's vocabulary,
three opt-in limits (threshold, occluder, address resolution) and a per-tick timeline. An observation that cannot resolve the operation is never a collapse of the run."""

from __future__ import annotations

import pytest

from xzr.meos import analysis as A
from xzr.meos import engine as E


@pytest.fixture(scope="module")
def base():
    return E.run_record(E.default_config(), [])


@pytest.mark.parametrize(
    ("obs", "status"),
    [
        ({"sampling_interval": 3}, "INSUFFICIENT_TEMPORAL_RESOLUTION"),
        ({"spatial_stride": 4}, "INSUFFICIENT_SPATIAL_RESOLUTION"),
        ({"region": [8, 8, 12, 12]}, "OUTSIDE_OBSERVATION_REGION"),
        ({"occluder": [3, 6, 3, 6]}, "BOUNDARY_OCCLUDED"),
        ({"threshold": 0.9}, "SIGNAL_BELOW_THRESHOLD"),
        ({"window": 8}, "WINDOW_TOO_SHORT"),
    ],
)
def test_each_observation_limit_has_its_own_status_and_leaves_the_run_unchanged(base, obs, status):
    x = A.observe(base, obs)
    assert x["operational_state"] == "ACTIVE"  # what the run did does not depend on how it is watched
    assert x["observed_state"] != "ACTIVE" and x["observability"]["status"] == status
    assert x["observability"]["limiting_parameters"] == list(obs.keys())
    assert x["observability"]["observed_collapse_is_artifact"] == (
        x["observed_state"] == "COLLAPSED"
    )  # an unobservable run is not a collapsed run


def test_full_observation_is_sufficient_and_the_first_stage_fields_are_kept(base):
    x = A.observe(base)
    assert x["observability"]["status"] == "SUFFICIENT" and x["observability_status"] == "OBSERVABLE" and x["agrees"]
    assert {"observed_status", "true_status", "observed_trajectory"} <= set(x)
    assert (
        A.observe(base, {"sampling_interval": 3})["observability_status"] == "INSUFFICIENT_TEMPORAL_RESOLUTION"
    )  # the legacy name is kept beside the new one


def test_address_resolution_hides_events_of_a_configuration_whose_address_is_lost():
    rec = E.run_record(E.default_config(), [{"tick": 30, "op": "ADDRESS", "target": "A1", "mode": "loss"}])
    full, strict = A.observe(rec, {}), A.observe(rec, {"address_resolution": 0.9})
    assert strict["observed_cycles"] <= full["observed_cycles"]
    # the loss is an operational fault; an observer that cannot resolve addresses sees fewer events, it does not change what the run did
    assert strict["operational_state"] == full["operational_state"]


def test_the_timeline_has_one_row_per_tick_and_the_three_states_apart(base):
    x = A.observe(base, {"sampling_interval": 3})
    assert len(x["timeline"]) == len(base["frames"])
    row = x["timeline"][200]
    assert (
        row["operational"] == "ACTIVE"
        and row["observed"] != "ACTIVE"
        and row["observability"] == "INSUFFICIENT_TEMPORAL_RESOLUTION"
    )
    assert row["limiting"] == ["sampling_interval"]
    assert all(r["observability"] == "SUFFICIENT" for r in A.observe(base)["timeline"])


def test_observation_does_not_enter_the_engine_digest(base):
    A.observe(base, {"sampling_interval": 5, "threshold": 0.3})
    assert (
        E.replay(base)["identical"]
        and base["result_digest"] == "b4cf1e522e8bee460eab30ee2a3f86ffd703a3f7969dc21271cf0240aa09adc5"
    )
