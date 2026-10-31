"""Temporal Reference: four kinds of time, clock synchronisation with its uncertainty, alignment that pairs only what can be paired, and interpolation records.

* Device Time        the time of the instrument's own clock (what the file says)
* Acquisition Time   when the acquisition happened, in a reference clock (needs a synchronisation record)
* Ingestion Time     when TEOO received the data
* Reconstruction Time the time a reconstructed state is *about* (not when it was computed)

Samples of two instruments are paired as one body state only if both clocks are related to a reference clock with a *known* uncertainty and the pairing fits the
tolerance; otherwise they stay unpaired and the reason is kept. A change shorter than the sampling period is not 'absent': :func:`resolvable` says it is not resolvable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class TimeKind(StrEnum):
    DEVICE = "DEVICE"
    ACQUISITION = "ACQUISITION"
    INGESTION = "INGESTION"
    RECONSTRUCTION = "RECONSTRUCTION"


@dataclass(frozen=True)
class ClockSync:
    clock_id: str
    reference_id: str | None  # None: not related to any reference clock
    method: str = "none"  # none | shared-trigger | network-time | manual-offset | post-hoc-alignment
    offset_s: float | None = None  # reference = device + offset
    uncertainty_s: float | None = None  # None: unknown (not zero)
    drift_ppm: float | None = None

    def known(self) -> bool:
        return self.reference_id is not None and self.offset_s is not None and self.uncertainty_s is not None

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def to_reference(t_device: float, sync: ClockSync | None) -> tuple[float | None, float | None]:
    """(time in the reference clock, its uncertainty); (None, None) when the clock is not related to a reference with a known uncertainty."""
    if sync is None or not sync.known():
        return None, None
    return t_device + sync.offset_s, sync.uncertainty_s  # type: ignore[operator]


def resolvable(sampling_period_s: float | None, change_duration_s: float) -> dict:
    """Can a change of the given duration be seen at this sampling period (Nyquist: at least two samples within it)? 'Not resolvable' means *not seen*, not *did not happen*."""
    if sampling_period_s is None:
        return {"resolvable": None, "status": "UNKNOWN_CAUSE", "note": "the sampling period is not declared"}
    ok = sampling_period_s <= change_duration_s / 2
    return {"resolvable": ok, "status": "MEASURED_VALID" if ok else "TIME_WINDOW_MISMATCH", "note": "" if ok else "a change this short can have happened between samples; it is not absent"}


@dataclass(frozen=True)
class Interpolation:
    method: str
    from_t: float
    to_t: float
    sample_indices: tuple[int, ...]
    note: str = ""

    def to_dict(self) -> dict:
        return {"method": self.method, "from_t": self.from_t, "to_t": self.to_t, "sample_indices": list(self.sample_indices), "note": self.note}


def align(times_a: list[float], sync_a: ClockSync | None, times_b: list[float], sync_b: ClockSync | None, tolerance_s: float) -> dict:
    """Pair samples of two series by reference time. Only pairs whose gap plus combined clock uncertainty fits ``tolerance_s`` are paired (and then only as 'near in time',
    with the uncertainty); the rest is unpaired. If either clock is not related to a reference clock with a known uncertainty nothing is paired."""
    ra = [to_reference(t, sync_a) for t in times_a]
    rb = [to_reference(t, sync_b) for t in times_b]
    if not (sync_a and sync_a.known() and sync_b and sync_b.known()):
        why = []
        for name, s in (("a", sync_a), ("b", sync_b)):
            if s is None:
                why.append(f"series {name} has no synchronisation record")
            elif not s.known():
                why.append(f"series {name}'s clock is not related to a reference clock with a known uncertainty")
        return {"synchronised": False, "reason": "; ".join(why), "pairs": [], "unpaired_a": list(range(len(times_a))), "unpaired_b": list(range(len(times_b))), "simultaneity_claim": False}
    if sync_a.reference_id != sync_b.reference_id:
        return {"synchronised": False, "reason": "the two clocks are related to different reference clocks", "pairs": [], "unpaired_a": list(range(len(times_a))), "unpaired_b": list(range(len(times_b))), "simultaneity_claim": False}
    ua, ub = sync_a.uncertainty_s, sync_b.uncertainty_s
    u = math.sqrt(ua**2 + ub**2)  # type: ignore[operator]
    pairs, used_b = [], set()
    for i, (ta, _) in enumerate(ra):
        best = None
        for j, (tb, _) in enumerate(rb):
            if j in used_b:
                continue
            gap = abs(ta - tb)  # type: ignore[operator]
            if best is None or gap < best[1]:
                best = (j, gap)
        if best is not None and best[1] + u <= tolerance_s:
            used_b.add(best[0])
            pairs.append({"a": i, "b": best[0], "gap_s": best[1], "uncertainty_s": u})
    paired_a = {p["a"] for p in pairs}
    return {"synchronised": True, "reason": "", "pairs": pairs, "unpaired_a": [i for i in range(len(times_a)) if i not in paired_a], "unpaired_b": [j for j in range(len(times_b)) if j not in used_b],
            "simultaneity_claim": False, "note": "pairs are 'near in time within the stated uncertainty', not the same instant"}
