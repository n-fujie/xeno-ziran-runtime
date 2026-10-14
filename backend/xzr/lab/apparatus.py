"""Apparatus state as a pure function of the runtime state.

A *chamber* is bound to one cluster of the world's intrinsic address hierarchy (level 1: 32 clusters) and placed in
3D space by its address (macro cluster → bay on a ring, sub-cluster → position in the bay, stacked in height), so
placement depends on public addresses only, never on runtime dynamics.

Per step, for every chamber, read from the runtime state (nothing else):

    shutter    permeability of the chamber's incoming boundary: mean current gate of live connections entering it
               (1 = open; < 1 = containment partly closed by a runtime gate)
    activity   share of the chamber's configurations that ignited this step
    memory     mean retained history (memory) of the chamber's configurations

Per pair of chambers: ``conduit`` = number of live connections between them (the apparatus topology).

Apparatus *events* are discrete changes of these values beyond fixed thresholds (containment closing / opening,
conduit established / severed). Each event carries the runtime step and the runtime cause that produced it (see
record.py). Thresholds are display-independent constants declared here.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

import numpy as np

SHUTTER_EVENT = 0.15  # change of shutter permeability that counts as containment closing / opening
LEVEL = 1


@dataclass(frozen=True)
class Chamber:
    cid: str  # hierarchy address, e.g. "3.2"
    nodes: np.ndarray
    position: tuple[float, float, float]


def chambers(h) -> list[Chamber]:
    out = []
    labels = h.labels[LEVEL]
    n_macro = h.n_clusters(0)
    for k in range(h.n_clusters(LEVEL)):
        addr = h.address(LEVEL, k)
        macro, sub = (int(x) for x in addr.split("."))
        ang = 2 * math.pi * macro / n_macro
        bay = (math.cos(ang) * 14.0, math.sin(ang) * 14.0)
        dx, dz = (sub % 2) * 3.4 - 1.7, (sub // 2) * 3.4 - 1.7
        y = 1.6 + 3.2 * (sub // 2)
        out.append(Chamber(addr, np.flatnonzero(labels == k).astype(np.int32),
                           (round(bay[0] + dx, 3), round(y, 3), round(bay[1] + dz, 3))))
    return out


def state(st, cs: list[Chamber], ignitions: np.ndarray) -> dict:
    """The apparatus state of one step, derived from the runtime state only."""
    n = st.n
    owner = np.full(n, -1, np.int32)
    for i, c in enumerate(cs):
        owner[c.nodes] = i
    alive = st.alive
    s_own, d_own = owner[st.src], owner[st.dst]
    entering = alive & (s_own != d_own)
    gate_sum = np.bincount(d_own[entering], weights=st.gate[entering], minlength=len(cs))
    gate_cnt = np.bincount(d_own[entering], minlength=len(cs))
    shutter = np.where(gate_cnt > 0, gate_sum / np.maximum(gate_cnt, 1), 1.0)
    size = np.array([len(c.nodes) for c in cs], float)
    act = np.bincount(owner[ignitions], minlength=len(cs)) / np.maximum(size, 1) if len(ignitions) else np.zeros(len(cs))
    mem = np.bincount(owner, weights=st.memory, minlength=len(cs)) / np.maximum(size, 1)
    a, b = np.minimum(s_own[entering], d_own[entering]), np.maximum(s_own[entering], d_own[entering])
    key = a.astype(np.int64) * len(cs) + b
    uniq, cnt = np.unique(key, return_counts=True)
    conduits = {f"{cs[int(u) // len(cs)].cid}|{cs[int(u) % len(cs)].cid}": int(c) for u, c in zip(uniq, cnt, strict=True)}
    return {"shutter": [round(float(x), 4) for x in shutter], "activity": [round(float(x), 4) for x in act],
            "memory": [round(float(x), 4) for x in mem], "conduits": conduits}


def digest(s: dict) -> str:
    return hashlib.sha256(json.dumps(s, sort_keys=True).encode()).hexdigest()[:16]


def events(prev: dict | None, cur: dict, cs: list[Chamber], t: int) -> list[dict]:
    """Discrete apparatus changes between two consecutive apparatus states."""
    if prev is None:
        return []
    out = []
    for i, c in enumerate(cs):
        d = cur["shutter"][i] - prev["shutter"][i]
        if abs(d) >= SHUTTER_EVENT:
            out.append({"t": t, "type": "containment_close" if d < 0 else "containment_open", "chamber": c.cid,
                        "before": prev["shutter"][i], "after": cur["shutter"][i]})
    for k in sorted(set(prev["conduits"]) | set(cur["conduits"])):
        a, b = prev["conduits"].get(k, 0), cur["conduits"].get(k, 0)
        if a == 0 and b > 0:
            out.append({"t": t, "type": "conduit_established", "pair": k, "before": 0, "after": b})
        elif a > 0 and b == 0:
            out.append({"t": t, "type": "conduit_severed", "pair": k, "before": a, "after": 0})
    return out
