"""Relational-difference variant (reduction experiment for *Difference*).

Difference is held on connections (``ebuf``: what arrived through each connection and is still retained) plus one
self-held term per configuration (``xbuf``: externally injected difference). A configuration's difference is
*recomputed* each step as ``xbuf + Σ ebuf(incoming)``. Retention, discharge and saturation scale all buffers of a
configuration by the same factor, so the aggregate follows the node-held dynamics up to floating-point rounding.
"""

from __future__ import annotations

import numpy as np

from .ops import Flow
from .state import State


def aggregate(state: State) -> np.ndarray:
    return state.xbuf + np.bincount(state.dst, state.ebuf, minlength=state.n)


def adopt(state: State) -> None:
    """Start relational bookkeeping: all existing difference is self-held."""
    state.xbuf[:] = state.diff
    state.ebuf[:] = 0.0


def fold_dead(state: State) -> None:
    """Difference held on a connection that no longer exists stays with its target configuration."""
    m = (~state.alive) & (state.ebuf != 0)
    if m.any():
        np.add.at(state.xbuf, state.dst[m], state.ebuf[m])
        state.ebuf[m] = 0.0


def fold_redirected(state: State, events: np.ndarray) -> None:
    """Before/after a connection changed its target, its buffer belongs to the previous target."""
    for e, old, _new in events:
        state.xbuf[old] += state.ebuf[e]
        state.ebuf[e] = 0.0


def absorb_external(state: State, before: np.ndarray) -> None:
    """Difference that entered from outside since ``before`` (inputs, drivers) is self-held."""
    state.xbuf += state.diff - before


def retain_and_decay(state: State, fl: Flow, retention: bool = True) -> np.ndarray:
    p = state.params
    prev = state.diff
    keep = state.retention.copy() if retention else np.zeros(state.n)
    keep[fl.emitted > 0] *= p.discharge
    with np.errstate(invalid="ignore", divide="ignore"):
        factor = np.where(prev > 0, (prev - fl.emitted) * keep / prev, 0.0)
    state.xbuf *= factor
    state.ebuf *= factor[state.dst]
    if len(fl.edges):
        np.add.at(state.ebuf, fl.edges, fl.flow)
    total = aggregate(state)
    sat = total > state.cap
    if sat.any():
        scale = np.where(sat, state.cap / np.where(total > 0, total, 1.0), 1.0)
        state.xbuf *= scale
        state.ebuf *= scale[state.dst]
        total = aggregate(state)
    state.overload[:] = np.where(sat, state.overload + 1, 0)
    decays = np.flatnonzero((prev >= p.decay_eps) & (total < p.decay_eps)).astype(np.int32)
    state.diff = total
    np.maximum(state.refractory - 1, 0, out=state.refractory)
    return decays
