"""Observation Status: why a value is, or is not, there.

Three things are kept in separate fields of every sample: ``status`` (what happened to the observation), ``causes`` (the observation limits that apply; several can
apply at once) and the value's validity (a value is present only for MEASURED_VALID; a value that is not there is ``None``, never 0). A cause is never guessed:
when the metadata needed to decide is missing the answer is UNKNOWN_CAUSE and the list of what could not be decided is kept. *Not observed* is not *absent*: no
status here says that something does not exist.

``FROM_HPO`` and ``FROM_MEOS`` record how the vocabularies of the two existing observation layers (hpo/observe.py REASONS; meos/analysis.py OBSERVABILITY_STATUSES)
map onto this one; they are plain data so this package imports neither (tests read both modules and check the tables are complete).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .schema import Issue


class ObsStatus(StrEnum):
    MEASURED_VALID = "MEASURED_VALID"
    UNMEASURED = "UNMEASURED"  # could have been measured, was not
    UNMEASURABLE = "UNMEASURABLE"  # no instrument of the configuration can measure it
    INSTRUMENT_MISMATCH = "INSTRUMENT_MISMATCH"
    SCALE_MISMATCH = "SCALE_MISMATCH"
    TIME_WINDOW_MISMATCH = "TIME_WINDOW_MISMATCH"
    BOUNDARY_INVISIBLE = "BOUNDARY_INVISIBLE"
    SIGNAL_BELOW_THRESHOLD = "SIGNAL_BELOW_THRESHOLD"  # measured, below the detection limit: a bound, not an absence
    MISSING = "MISSING"  # an expected sample is absent (its reason may be unknown)
    INVALID = "INVALID"  # a value arrived and failed validation (the raw text is kept in the detail)
    UNKNOWN_CAUSE = "UNKNOWN_CAUSE"  # not available, and which limit applies could not be decided from the metadata


LIMIT_CAUSES = (ObsStatus.INSTRUMENT_MISMATCH, ObsStatus.SCALE_MISMATCH, ObsStatus.TIME_WINDOW_MISMATCH, ObsStatus.BOUNDARY_INVISIBLE, ObsStatus.SIGNAL_BELOW_THRESHOLD)
PRECEDENCE = (ObsStatus.UNMEASURABLE, ObsStatus.INSTRUMENT_MISMATCH, ObsStatus.BOUNDARY_INVISIBLE, ObsStatus.SCALE_MISMATCH, ObsStatus.TIME_WINDOW_MISMATCH, ObsStatus.SIGNAL_BELOW_THRESHOLD)
STATUS_IDS = tuple(s.value for s in ObsStatus)
CAUSE_IDS = tuple(s.value for s in (ObsStatus.UNMEASURABLE, *LIMIT_CAUSES))

FROM_HPO: dict[str, tuple[str | None, str]] = {
    "unmeasurable": ("UNMEASURABLE", "no instrument of the configuration can measure the channel"),
    "instrument_mismatch": ("INSTRUMENT_MISMATCH", "the channel exists in the configuration but this instrument does not carry it"),
    "scale_mismatch": ("SCALE_MISMATCH", "the needed resolution is finer than the instrument's"),
    "time_window_mismatch": ("TIME_WINDOW_MISMATCH", "the instrument's window or period is longer than the phenomenon"),
    "boundary_invisible": ("BOUNDARY_INVISIBLE", "behind a veil the instrument cannot penetrate"),
    "unmeasured": ("UNMEASURED", "could be measured but was not"),
}
FROM_MEOS: dict[str, tuple[str | None, str]] = {
    "SUFFICIENT": ("MEASURED_VALID", "the observation agrees with the run's own state"),
    "INSUFFICIENT_TEMPORAL_RESOLUTION": ("TIME_WINDOW_MISMATCH", "sampling or aggregation too coarse for the phenomenon"),
    "INSUFFICIENT_SPATIAL_RESOLUTION": ("SCALE_MISMATCH", "spatial stride too coarse"),
    "OUTSIDE_OBSERVATION_REGION": ("BOUNDARY_INVISIBLE", "the activity is outside the observed region (an observation boundary)"),
    "BOUNDARY_OCCLUDED": ("BOUNDARY_INVISIBLE", "an occluder hides the target"),
    "ADDRESS_UNRESOLVED": ("SCALE_MISMATCH", "the addressing resolution cannot separate the target"),
    "WINDOW_TOO_SHORT": ("TIME_WINDOW_MISMATCH", "the observation window is shorter than the phenomenon"),
    "SIGNAL_BELOW_THRESHOLD": ("SIGNAL_BELOW_THRESHOLD", "measured but under the detection threshold"),
    "COMBINED_LIMITS": (None, "several limits at once: the status is the highest-precedence cause and the causes list carries all of them; they must be read from the record, not from this string"),
    "OBSERVATION_OVERESTIMATES": (None, "an observation exists and is larger than the state: not an availability status (the value is MEASURED_VALID with a bias note)"),
    "REGION_EXCLUDES_ACTIVITY": ("BOUNDARY_INVISIBLE", "first-stage name of OUTSIDE_OBSERVATION_REGION"),
    "AGGREGATION_SCALE_MISMATCH": ("TIME_WINDOW_MISMATCH", "first-stage name (aggregation)"),
    "OBSERVATION_WINDOW_MISMATCH": ("TIME_WINDOW_MISMATCH", "first-stage name of WINDOW_TOO_SHORT"),
    "WINDOW_MISMATCH": ("TIME_WINDOW_MISMATCH", "legacy window label"),
}


def combine(causes: list[ObsStatus]) -> tuple[ObsStatus, list[str]]:
    """Several limits at once: the status is the highest-precedence one, the causes are all of them (no cause is dropped)."""
    cs = [c for c in causes if c in PRECEDENCE]
    if not cs:
        raise ValueError("no cause to combine")
    first = next(p for p in PRECEDENCE if p in cs)
    return first, [c.value for c in PRECEDENCE if c in cs]


def sample(value: Any, status: ObsStatus | str, *, causes: list[str] | None = None, cause_known: bool = True, detection_limit: float | None = None, detail: Any = None) -> dict:
    """One sample of a series. A value is kept only for MEASURED_VALID."""
    st = ObsStatus(status)
    return {"value": value, "status": st.value, "causes": list(causes or []), "cause_known": cause_known, "detection_limit": detection_limit, "detail": detail}


def validate_sample(s: dict, where: str = "sample") -> list[Issue]:
    out: list[Issue] = []
    try:
        st = ObsStatus(str(s.get("status")))
    except ValueError:
        return [Issue(where, "STATUS_UNKNOWN", f"status must be one of {STATUS_IDS}")]
    v, causes = s.get("value"), s.get("causes", [])
    if st is ObsStatus.MEASURED_VALID:
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            out.append(Issue(where, "VALID_WITHOUT_VALUE", "MEASURED_VALID carries a finite value"))
        if causes:
            out.append(Issue(where, "VALID_WITH_CAUSES", "a valid measurement lists no observation-limit cause"))
    else:
        if v is not None:
            out.append(Issue(where, "VALUE_WITHOUT_VALIDITY", f"status {st.value} carries no value; a missing or limited value is None, never a number (not 0)"))
        for c in causes:
            if c not in CAUSE_IDS:
                out.append(Issue(where, "CAUSE_UNKNOWN", f"cause {c!r} is not one of {CAUSE_IDS}"))
        if st in LIMIT_CAUSES and st.value not in causes:
            out.append(Issue(where, "CAUSE_MISSING", f"status {st.value} appears among its own causes"))
        if st is ObsStatus.UNKNOWN_CAUSE and (causes or s.get("cause_known", True)):
            out.append(Issue(where, "CAUSE_ASSERTED", "UNKNOWN_CAUSE names no cause: a reason is never attached to an unexplained gap"))
        if st is ObsStatus.SIGNAL_BELOW_THRESHOLD and s.get("detection_limit") is None:
            out.append(Issue(where, "LIMIT_MISSING", "SIGNAL_BELOW_THRESHOLD states the detection limit (the value is 'below it', not absent)"))
        if not s.get("cause_known", True) and causes:
            out.append(Issue(where, "CAUSE_CONTRADICTION", "cause_known is false but causes are listed"))
    return out


@dataclass(frozen=True)
class Instrument:
    id: str
    channels: tuple[str, ...]
    resolution: float | None = None  # the smallest scale it separates (the unit of the target's scale)
    sampling_period_s: float | None = None
    window_s: float | None = None
    detection_limit: float | None = None
    penetration: float | None = None  # boundaries with opacity <= penetration are seen through


@dataclass(frozen=True)
class Target:
    channel: str
    scale: float | None = None
    phenomenon_period_s: float | None = None
    amplitude: float | None = None
    boundary_opacity: float | None = None


def assess(configuration_channels: tuple[str, ...] | None, instrument: Instrument | None, target: Target, *, measured: bool) -> dict:
    """What can be said of one target under one observation condition. Several causes can apply at once; a check whose metadata is missing is *undetermined*, not passed:
    with no determined cause and some undetermined check the answer is UNKNOWN_CAUSE."""
    causes: list[ObsStatus] = []
    undetermined: list[str] = []
    if configuration_channels is None:
        undetermined.append("configuration_channels")
    elif target.channel not in configuration_channels:
        causes.append(ObsStatus.UNMEASURABLE)
    if ObsStatus.UNMEASURABLE not in causes:
        if instrument is None:
            causes.append(ObsStatus.INSTRUMENT_MISMATCH)
        else:
            if target.channel not in instrument.channels:
                causes.append(ObsStatus.INSTRUMENT_MISMATCH)
            if instrument.resolution is None or target.scale is None:
                undetermined.append("scale")
            elif instrument.resolution > target.scale:
                causes.append(ObsStatus.SCALE_MISMATCH)
            if instrument.sampling_period_s is None or instrument.window_s is None or target.phenomenon_period_s is None:
                undetermined.append("time_window")
            elif instrument.sampling_period_s > target.phenomenon_period_s / 2 or instrument.window_s < target.phenomenon_period_s:
                causes.append(ObsStatus.TIME_WINDOW_MISMATCH)
            if target.boundary_opacity is not None and instrument.penetration is not None and target.boundary_opacity > instrument.penetration:
                causes.append(ObsStatus.BOUNDARY_INVISIBLE)
            elif target.boundary_opacity is not None and instrument.penetration is None:
                undetermined.append("boundary")
    if causes:
        st, all_c = combine(causes)
        return {"status": st.value, "causes": all_c, "cause_known": True, "undetermined": undetermined}
    if undetermined:
        return {"status": ObsStatus.UNKNOWN_CAUSE.value, "causes": [], "cause_known": False, "undetermined": undetermined}
    if not measured:
        return {"status": ObsStatus.UNMEASURED.value, "causes": [], "cause_known": True, "undetermined": []}
    assert instrument is not None
    if instrument.detection_limit is None or target.amplitude is None:
        return {"status": ObsStatus.UNKNOWN_CAUSE.value, "causes": [], "cause_known": False, "undetermined": ["detection_limit"]}
    if target.amplitude < instrument.detection_limit:
        return {"status": ObsStatus.SIGNAL_BELOW_THRESHOLD.value, "causes": [ObsStatus.SIGNAL_BELOW_THRESHOLD.value], "cause_known": True, "undetermined": []}
    return {"status": ObsStatus.MEASURED_VALID.value, "causes": [], "cause_known": True, "undetermined": []}
