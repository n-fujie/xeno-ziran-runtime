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

import numpy as np

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


# ------------------------------------------------------------------------------------------------------ levels of reachability
# Seven things that are easily conflated, kept apart. A configuration change can raise the first without raising the next:
#   available    the operation's instrument carries what its essential channels need (static; ``reachability``)
#   executable   its last evaluation was not blocked at run time (a veil, no resources): dynamic, known only after the next evaluation
#   success      it acted (a request reached the world) during the epoch that followed
#   reachable    the configurations its action can reach in the runtime graph within ``reach_hops`` (a finite, computed set)
#   observable   the (channel, cluster) cells its instrument actually returns a value for (veils and resources remove cells)
#   identified   the kinds whose ignition rule fired in the last evaluation (the detector's output)
#   used         its acts that were a cause of a later recorded event (they entered later research)
# A record that an operation was enabled is not a finding that the research possibilities grew.
def _reach_mask(world, nodes: np.ndarray, hops: int) -> np.ndarray:
    st = world.state
    m = st.reachable_mask()
    src, dst = st.src[m], st.dst[m]
    seen = np.zeros(st.n, bool)
    seen[nodes] = True
    frontier = seen.copy()
    for _ in range(hops):
        nxt = np.zeros(st.n, bool)
        nxt[dst[frontier[src]]] = True
        frontier = nxt & ~seen
        if not frontier.any():
            break
        seen |= frontier
    return seen


def levels(f) -> dict:
    """The static and dynamic state sets of a running field (nothing in it is changed)."""
    from .operations import UNOBSERVABLE

    live = f.live()
    av = reachability(f)
    available = sorted(oid for oid, v in av.items() if v["runnable"])
    executable, unevaluated, identified = [], [], []
    for o in live:
        last = o.mem.get("_last_ign")
        if not last:
            unevaluated.append(o.oid)
            continue
        if o.oid in available and not all(out == UNOBSERVABLE for out, _, _ in last.values()):
            executable.append(o.oid)
        identified += [f"{o.oid}:{k}" for k, (out, _, _) in last.items() if out == "FIRED"]
    regions = np.unique(np.concatenate([o.region for o in live])) if live else np.zeros(0, np.int32)
    seen = _reach_mask(f.world, regions, int(f.s["reach_hops"])) if len(regions) else np.zeros(f.world.state.n, bool)
    lab1 = f.world.h.labels[1]
    clusters = sorted(int(c) for c in np.unique(lab1[seen]))
    cells: set[str] = set()
    for o in live:
        obs, _ = f.instruments.observe(o.instrument, o.needs(), o.region, float("inf"), None, viewer=o.oid)
        for ch, v in obs.values.items():
            arr = np.asarray(v, float)
            seen_cells = np.flatnonzero(~np.isnan(arr)) if arr.ndim == 1 else np.flatnonzero(~np.isnan(arr).all(axis=1))
            cells |= {f"{o.oid}:{ch}:L{obs.level}:{int(c)}" for c in seen_cells}
    return {"t": int(f.world.t - f.t0), "available": available, "executable": sorted(executable), "unevaluated": sorted(unevaluated),
            "identified": sorted(identified), "reachable_configurations": int(seen.sum()), "reachable_clusters": clusters,
            "observable_cells": sorted(cells), "n_observable_cells": len(cells)}


def _delta_set(a: list, b: list) -> dict:
    sa, sb = set(a), set(b)
    return {"gained": sorted(sb - sa), "lost": sorted(sa - sb), "before": len(sa), "after": len(sb)}


SET_KEYS = ("available", "executable", "identified", "reachable_clusters", "observable_cells")


def compare_levels(before: dict, after: dict) -> dict:
    """Per level: what was gained and lost, and one verdict on the whole change: ``expanded`` (something gained, nothing lost), ``contracted``
    (something lost, nothing gained), ``mixed`` (both), ``equivalent`` (no level differs). The reachable-configuration count enters as a number."""
    d = {k: _delta_set(before[k], after[k]) for k in SET_KEYS}
    d["reachable_configurations"] = {"before": before["reachable_configurations"], "after": after["reachable_configurations"],
                                     "delta": after["reachable_configurations"] - before["reachable_configurations"]}
    gained = any(d[k]["gained"] for k in SET_KEYS) or d["reachable_configurations"]["delta"] > 0
    lost = any(d[k]["lost"] for k in SET_KEYS) or d["reachable_configurations"]["delta"] < 0
    d["effect"] = "mixed" if gained and lost else "expanded" if gained else "contracted" if lost else "equivalent"
    return d


def realised(f, evs: list[dict], epoch: int, epoch_len: int) -> dict:
    """What the operations did in an epoch: ``success`` (acts per operation) and ``used`` (acts that were a cause of a later event)."""
    caused = {c for e in evs for c in e["causes"]}
    acts: dict[str, int] = {}
    used: dict[str, int] = {}
    for e in evs:
        if e["type"] == "act":
            acts[e["source"]] = acts.get(e["source"], 0) + 1
            if e["id"] in caused:
                used[e["source"]] = used.get(e["source"], 0) + 1
    return {"epoch": epoch, "success": acts, "used": used}
