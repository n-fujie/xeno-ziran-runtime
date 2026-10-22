"""Reachability of a configuration: which operations can observe what they need, before and after a change.

A reconfiguration (reconfig.apply) changes the instruments, so it changes which later operations are possible at all.
This module records that effect. For every live operation and every channel its kinds need it evaluates the *static*
part of the observation predicate of ``Instruments.observe`` (the same order of tests, the same reasons):

    unmeasurable · instrument_mismatch · scale_mismatch · time_window_mismatch

The dynamic reasons (``boundary_invisible``: depends on the veils present; ``unmeasured``: depends on the resource
pool) are not evaluated here and are not claimed. An operation is *runnable* when none of its essential channels is
blocked statically. A reachability record is a statement about the configuration, not about the world: it says what
can be seen, never what was found.
"""

from __future__ import annotations

from .observe import MAX_FLOW_LEVEL, InstrumentSpec
from .operations import ESSENTIAL


def _static_reason(ch: str, spec: InstrumentSpec, catalog: tuple[str, ...], needs: tuple[int, int],
                   n_levels: int) -> str:
    min_level, max_window = needs
    level = min(spec.level, n_levels - 1)
    if spec.oracle:
        return ""
    if ch not in catalog or ch == "interior":
        return "unmeasurable"
    if ch not in spec.channels:
        return "instrument_mismatch"
    if level < min_level or (ch == "boundary_flow" and level > MAX_FLOW_LEVEL):
        return "scale_mismatch"
    if spec.window > max_window or spec.period > max_window:
        return "time_window_mismatch"
    return ""


def reachability(f) -> dict[str, dict]:
    """Per live operation: ``{"runnable": bool, "blocked": {channel: reason}, "essential_blocked": [...]}``.

    ``f`` is a running ``Field``; nothing in it is changed.
    """
    n_levels = len(f.world.h.labels)
    out: dict[str, dict] = {}
    for o in f.live():
        blocked = {ch: r for ch, nd in o.needs().items()
                   if (r := _static_reason(ch, o.instrument, f.instruments.catalog, nd, n_levels))}
        ess = sorted({ch for k in o.kinds for ch in ESSENTIAL[k] if ch in blocked})
        out[o.oid] = {"kinds": list(o.kinds), "runnable": not ess, "blocked": dict(sorted(blocked.items())),
                      "essential_blocked": ess}
    return out


def delta(before: dict[str, dict], after: dict[str, dict]) -> dict:
    """What a change opened and closed. Operations present on one side only are listed, not compared."""
    opened, closed, channels_opened, channels_closed = [], [], [], []
    for oid in sorted(set(before) & set(after)):
        b, a = before[oid], after[oid]
        if not b["runnable"] and a["runnable"]:
            opened.append(oid)
        elif b["runnable"] and not a["runnable"]:
            closed.append(oid)
        for ch in sorted(set(b["blocked"]) - set(a["blocked"])):
            channels_opened.append({"oid": oid, "channel": ch, "was": b["blocked"][ch]})
        for ch in sorted(set(a["blocked"]) - set(b["blocked"])):
            channels_closed.append({"oid": oid, "channel": ch, "now": a["blocked"][ch]})
    return {"runnable_opened": opened, "runnable_closed": closed, "channels_opened": channels_opened,
            "channels_closed": channels_closed, "only_before": sorted(set(before) - set(after)),
            "only_after": sorted(set(after) - set(before)),
            "runnable_before": sum(v["runnable"] for v in before.values()),
            "runnable_after": sum(v["runnable"] for v in after.values())}
