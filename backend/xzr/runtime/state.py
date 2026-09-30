"""Compact structure-of-arrays representation of local configurations and their connections.

The runtime knows only numbers: differences, thresholds, retention, memory, connections, gates.
It carries no human-readable category of what a configuration "is".
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, fields
from typing import Any

import numpy as np

NO_INDEX = -1


@dataclass
class Params:
    """Global operational parameters. All are dimensionless."""

    emit_frac: float = 0.55  # fraction of difference emitted on ignition
    discharge: float = 0.25  # fraction of the non-emitted residue an ignited configuration keeps
    gain: float = 2.8  # transmission gain: difference is not conserved, it can amplify or attenuate
    fatigue: float = 1.0  # loaded connections conduct less: flow / (1 + fatigue·load/capacity)
    theta_floor: float = 0.4  # memory can lower an effective threshold to at most this fraction
    refractory_steps: int = 4
    n_forms: int = 4  # number of opaque difference forms
    transform_min_share: float = 0.5  # dominant incoming share needed to rewrite form
    decay_eps: float = 0.02  # below this a difference counts as vanished
    load_decay: float = 0.7  # per-step decay of connection load
    w_min: float = 0.03  # weaker connections dissolve (disconnect)
    w_max: float = 3.0
    strengthen: float = 0.03  # penetrating connections strengthen
    weaken: float = 0.02  # carrying-but-not-penetrating connections weaken
    relax: float = 0.0005  # drift of weight back towards its base value
    connect_per_step: int = 6  # max new connections per step (triadic closure)
    connect_mem_min: float = 0.6
    connect_weight: float = 0.4
    reconfigure_per_step: int = 2
    overload_steps: int = 4  # consecutive saturated steps before reconfiguration
    input_rate: float = 0.004  # fraction of configurations receiving external difference per step
    input_amp: float = 0.9
    quant_max: float = 10.0  # upper bound for quantized transport of differences

    def to_dict(self) -> dict[str, float | int]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, d: dict | None) -> Params:
        p = cls()
        for k, v in (d or {}).items():
            if not hasattr(p, k):
                raise ValueError(f"unknown parameter: {k}")
            setattr(p, k, type(getattr(p, k))(v))
        return p


NODE_FLOAT = ("diff", "theta", "theta_mod", "retention", "memory", "mem_decay", "mem_coupling", "cap",
              "base_mem_decay", "base_mem_coupling")
NODE_INT = ("form", "refractory", "wave_origin", "wave_depth", "cause_edge", "pending_origin", "pending_depth",
            "overload", "last_ignite", "ignite_count")
EDGE_ARRAYS = ("src", "dst", "weight", "base_weight", "alive", "transform", "gate", "base_gate",
               "gate_mod", "load", "capacity")


@dataclass
class State:
    """All runtime arrays. Node count is fixed per run; connections live in a fixed-capacity pool."""

    # --- configurations (N) ---
    diff: np.ndarray
    form: np.ndarray
    theta: np.ndarray
    theta_mod: np.ndarray  # intervention multiplier on theta (1 = unmodified)
    retention: np.ndarray
    memory: np.ndarray
    mem_decay: np.ndarray
    mem_coupling: np.ndarray
    base_mem_decay: np.ndarray
    base_mem_coupling: np.ndarray
    cap: np.ndarray
    frozen: np.ndarray
    refractory: np.ndarray
    wave_origin: np.ndarray
    wave_depth: np.ndarray
    cause_edge: np.ndarray  # dominant incoming connection of the last propagation (-1 if none)
    pending_origin: np.ndarray  # wave origin carried by the cause connection
    pending_depth: np.ndarray
    overload: np.ndarray
    last_ignite: np.ndarray
    ignite_count: np.ndarray
    geo: np.ndarray  # (N, 2) lon/lat, NaN when absent. Projection data only; never read by dynamics.
    mutation: np.ndarray  # per-configuration connection mutation rate (overlay-controlled; 0 = none)
    xbuf: np.ndarray  # relational-difference variant only: self-held part of each configuration's difference
    # --- connections (capacity E) ---
    src: np.ndarray
    dst: np.ndarray
    weight: np.ndarray
    base_weight: np.ndarray
    alive: np.ndarray
    transform: np.ndarray
    gate: np.ndarray
    base_gate: np.ndarray
    gate_mod: np.ndarray
    load: np.ndarray
    capacity: np.ndarray
    ebuf: np.ndarray  # relational-difference variant only: difference held on each connection
    t: int = 0
    params: Params = field(default_factory=Params)

    @property
    def n(self) -> int:
        return int(self.diff.shape[0])

    @property
    def e_cap(self) -> int:
        return int(self.src.shape[0])

    def n_alive_edges(self) -> int:
        return int(self.alive.sum())

    def theta_eff(self) -> np.ndarray:
        base = self.theta * self.theta_mod
        return np.maximum(base - self.mem_coupling * self.memory, self.params.theta_floor * base)

    def reachable_mask(self) -> np.ndarray:
        """Connections currently usable as transitions."""
        m = self.alive & (self.gate > 0.0)
        m[m] &= ~self.frozen[self.dst[m]]
        return m

    def copy(self) -> State:
        kw: dict[str, Any] = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, np.ndarray):
                kw[f.name] = v.copy()
            elif isinstance(v, Params):
                kw[f.name] = Params.from_dict(v.to_dict())
            else:
                kw[f.name] = v
        return State(**kw)

    def arrays(self) -> dict[str, np.ndarray]:
        return {f.name: getattr(self, f.name) for f in fields(self) if isinstance(getattr(self, f.name), np.ndarray)}


def allocate(n: int, e_cap: int, params: Params | None = None) -> State:
    f = lambda v: np.full(n, v, dtype=np.float64)  # noqa: E731
    i = lambda v, dt=np.int32: np.full(n, v, dtype=dt)  # noqa: E731
    return State(
        diff=f(0.0), form=i(0, np.int8), theta=f(1.0), theta_mod=f(1.0), retention=f(0.85), memory=f(0.0),
        mem_decay=f(0.9), mem_coupling=f(0.2), base_mem_decay=f(0.9), base_mem_coupling=f(0.2), cap=f(6.0),
        frozen=np.zeros(n, dtype=bool), refractory=i(0, np.int16), wave_origin=i(NO_INDEX), wave_depth=i(0),
        cause_edge=i(NO_INDEX), pending_origin=i(NO_INDEX), pending_depth=i(0), overload=i(0, np.int16), last_ignite=i(-(10**6)),
        ignite_count=i(0), geo=np.full((n, 2), np.nan), mutation=f(0.0), xbuf=f(0.0),
        src=np.zeros(e_cap, dtype=np.int32), dst=np.zeros(e_cap, dtype=np.int32),
        weight=np.zeros(e_cap), base_weight=np.zeros(e_cap), alive=np.zeros(e_cap, dtype=bool),
        transform=np.zeros(e_cap, dtype=np.int8), gate=np.ones(e_cap), base_gate=np.ones(e_cap),
        gate_mod=np.ones(e_cap), load=np.zeros(e_cap), capacity=np.full(e_cap, 8.0), ebuf=np.zeros(e_cap),
        params=params or Params(),
    )


def fingerprint(state: State, rng: np.random.Generator | None = None) -> str:
    """SHA-256 over every runtime array (+ RNG state). Equal fingerprints = bit-identical runs."""
    h = hashlib.sha256()
    h.update(str(state.t).encode())
    for name, arr in sorted(state.arrays().items()):
        h.update(name.encode())
        h.update(np.ascontiguousarray(arr).tobytes())
    if rng is not None:
        h.update(repr(rng.bit_generator.state).encode())
    return h.hexdigest()
