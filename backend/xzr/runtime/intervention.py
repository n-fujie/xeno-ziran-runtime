"""Runtime-level interventions. Addressed only by opaque indices.

Two families:

* **Overlay** items are idempotent modifiers recomputed from base values whenever the overlay changes
  (threshold scaling, gating, memory conditions, freezing). Removing an overlay item fully restores
  the base semantics.
* **Actions** are one-shot structural operations (sever, connect, set threshold, inject difference).

Higher layers compile their own state into these records; the runtime never learns what produced them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np


def _arr(x) -> np.ndarray:
    return np.asarray(sorted(set(int(i) for i in x)), dtype=np.int32)


@dataclass(frozen=True)
class ScaleThreshold:
    nodes: tuple[int, ...]
    factor: float
    kind: str = "scale_threshold"


@dataclass(frozen=True)
class Gate:
    """Multiply the permeability of connections (a boundary). factor 0 closes, 1 leaves unchanged."""

    edges: tuple[int, ...]
    factor: float
    kind: str = "gate"


@dataclass(frozen=True)
class MemoryCondition:
    nodes: tuple[int, ...]
    decay: float | None = None
    coupling: float | None = None
    kind: str = "memory_condition"


@dataclass(frozen=True)
class Freeze:
    nodes: tuple[int, ...]
    kind: str = "freeze"


@dataclass(frozen=True)
class Sever:
    edges: tuple[int, ...]
    kind: str = "sever"


@dataclass(frozen=True)
class Connect:
    src: int
    dst: int
    weight: float = 0.5
    kind: str = "connect"


@dataclass(frozen=True)
class SetThreshold:
    nodes: tuple[int, ...]
    value: float
    kind: str = "set_threshold"


@dataclass(frozen=True)
class Inject:
    nodes: tuple[int, ...]
    amount: float
    kind: str = "inject"


@dataclass(frozen=True)
class Mutation:
    """Connection-mutation rate for outgoing connections of configurations (addressability change)."""

    nodes: tuple[int, ...]
    rate: float
    kind: str = "mutation"


OverlayItem = ScaleThreshold | Gate | MemoryCondition | Freeze | Mutation
Action = Sever | Connect | SetThreshold | Inject
Intervention = OverlayItem | Action

_KINDS = {"scale_threshold": ScaleThreshold, "gate": Gate, "memory_condition": MemoryCondition, "freeze": Freeze,
          "mutation": Mutation, "sever": Sever, "connect": Connect, "set_threshold": SetThreshold, "inject": Inject}


def is_overlay(x: Intervention) -> bool:
    return isinstance(x, ScaleThreshold | Gate | MemoryCondition | Freeze | Mutation)


def to_dict(x: Intervention) -> dict:
    d = asdict(x)
    for k, v in d.items():
        if isinstance(v, tuple):
            d[k] = list(v)
    return d


def from_dict(d: dict) -> Intervention:
    d = dict(d)
    cls = _KINDS[d.pop("kind")]
    for k in ("nodes", "edges"):
        if k in d:
            d[k] = tuple(int(i) for i in d[k])
    return cls(**d)


@dataclass
class OverlayResult:
    gate_changed: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int32))


def apply_overlay(state, base_items: list[OverlayItem], items: list[OverlayItem]) -> np.ndarray:
    """Recompute every overlay-controlled array from base values. Returns connections whose gate changed."""
    old_gate = state.gate.copy()
    state.theta_mod[:] = 1.0
    state.gate_mod[:] = 1.0
    state.mem_decay[:] = state.base_mem_decay
    state.mem_coupling[:] = state.base_mem_coupling
    state.frozen[:] = False
    state.mutation[:] = 0.0
    for it in [*base_items, *items]:
        if isinstance(it, ScaleThreshold):
            state.theta_mod[_arr(it.nodes)] *= it.factor
        elif isinstance(it, Gate):
            state.gate_mod[_arr(it.edges)] *= it.factor
        elif isinstance(it, MemoryCondition):
            idx = _arr(it.nodes)
            if it.decay is not None:
                state.mem_decay[idx] = it.decay
            if it.coupling is not None:
                state.mem_coupling[idx] = it.coupling
        elif isinstance(it, Freeze):
            state.frozen[_arr(it.nodes)] = True
        elif isinstance(it, Mutation):
            idx = _arr(it.nodes)
            state.mutation[idx] = np.maximum(state.mutation[idx], it.rate)
    np.multiply(state.base_gate, state.gate_mod, out=state.gate)
    return np.flatnonzero(state.gate != old_gate).astype(np.int32)
