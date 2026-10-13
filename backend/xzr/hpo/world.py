"""The simulated world an HPO run acts in: the runtime engine plus what only the harness may read.

Two random streams are kept apart:

    exogenous   the external difference entering the world (the engine's own input is switched off and the same
                amount is drawn here from a dedicated generator, with a fixed number of draws per step that does not
                depend on the world's state). Every paired branch of one seed receives exactly the same exogenous
                input, whatever the operations do.
    endogenous  the engine's generator (connection creation, reconfiguration): it is consumed state-dependently, so
                two branches that diverge also consume it differently. A *noise* branch uses another endogenous seed
                with the same exogenous input.

The true state (``World.engine.state`` and the per-step records here) is read by instruments (observe.py) and by the
harness's metrics; operations never receive a World.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..experiments.runs import CONFIGS
from ..lod.hierarchy import Hierarchy, build_hierarchy, symmetric_adjacency
from ..runtime.engine import Engine
from ..runtime.generator import latent_geometric
from ..runtime.intervention import Action, OverlayItem
from ..runtime.state import Params

RING = 16  # steps of per-step records kept for instruments (max instrument window)
EXO_STREAM = 0x45584F  # salt of the exogenous generator
NOISE_OFFSET = 7919  # endogenous seed offset of the noise branch


@dataclass
class StepRecord:
    t: int
    ignitions: np.ndarray  # configurations that ignited
    pen_src: np.ndarray  # penetrations: source and destination configuration of the causing connection
    pen_dst: np.ndarray


@dataclass
class World:
    engine: Engine
    h: Hierarchy
    exo: np.random.Generator
    input_rate: float
    input_amp: float
    records: list[StepRecord] = field(default_factory=list)
    overlays: dict[str, list[OverlayItem]] = field(default_factory=dict)
    memory_writes: float = 0.0  # total |memory| written directly (history deposits / reinsertion)
    total_ignitions: int = 0
    rng_trace: list[int] | None = None  # endogenous stream position per step (when tracked)

    @property
    def state(self):
        return self.engine.state

    @property
    def t(self) -> int:
        return int(self.engine.state.t)

    def step(self) -> StepRecord:
        s = self.engine.state
        n = s.n
        k = int(self.exo.binomial(n, self.input_rate))
        idx = self.exo.integers(0, n, k)
        amt = self.exo.exponential(self.input_amp, k)
        np.add.at(s.diff, idx, amt)
        d = self.engine.step()
        s = self.engine.state
        e = d.penetrations[:, 0] if len(d.penetrations) else np.zeros(0, np.int64)
        rec = StepRecord(int(d.t), d.ignitions.astype(np.int32), s.src[e].astype(np.int32), s.dst[e].astype(np.int32))
        self.records.append(rec)
        if len(self.records) > RING:
            del self.records[0]
        self.total_ignitions += int(d.ignitions.size)
        if self.rng_trace is not None:
            self.rng_trace.append(int(self.engine.rng.bit_generator.state["state"]["state"]))
        return rec

    # ---------------------------------------------------------------- acting (only the field calls these)
    def set_owner_overlay(self, owner: str, items: list[OverlayItem]) -> None:
        if not items and owner not in self.overlays:
            return
        if items:
            self.overlays[owner] = list(items)
        else:
            self.overlays.pop(owner, None)
        self.engine.set_overlay([it for k in sorted(self.overlays) for it in self.overlays[k]])

    def apply(self, actions: list[Action]) -> None:
        if actions:
            self.engine.apply(actions)

    def deposit_memory(self, nodes: np.ndarray, amount: float) -> None:
        if len(nodes) and amount:
            self.engine.state.memory[nodes] += amount
            self.memory_writes += abs(amount) * len(nodes)

    def fork(self, endogenous_seed: int | None = None) -> World:
        """An exact continuation (same state, same streams); with ``endogenous_seed`` the engine stream is replaced."""
        e = self.engine.fork()
        if endogenous_seed is not None:
            e.rng = np.random.default_rng(endogenous_seed)
        exo = np.random.default_rng()
        exo.bit_generator.state = self.exo.bit_generator.state
        return World(e, self.h, exo, self.input_rate, self.input_amp, list(self.records),
                     {k: list(v) for k, v in self.overlays.items()}, self.memory_writes)

    def track_rng(self) -> World:
        self.rng_trace = []
        return self


def build_world(n: int, gen_seed: int, seed: int, regime: str = "intermittent", input_rate: float = 0.004,
                input_amp: float = 0.9, endogenous_offset: int = 0) -> World:
    """A seeded world. ``gen_seed`` fixes the initial structure, ``seed`` the exogenous and endogenous streams."""
    cfg = next((c for c in CONFIGS if c.name == regime), None)
    if cfg is None:
        raise ValueError(f"unknown regime {regime!r}; one of {', '.join(c.name for c in CONFIGS)}")
    params = Params.from_dict({**cfg.params, "input_rate": 0.0})
    st = latent_geometric(n, gen_seed, params=params, **cfg.gen).state
    if cfg.mem_coupling_scale != 1.0:
        st.base_mem_coupling *= cfg.mem_coupling_scale
        st.mem_coupling[:] = st.base_mem_coupling
    if cfg.mem_decay is not None:
        st.base_mem_decay[:] = cfg.mem_decay
        st.mem_decay[:] = cfg.mem_decay
    m = st.alive
    h = build_hierarchy(symmetric_adjacency(st.src[m], st.dst[m], st.n))
    eng = Engine(st, seed + endogenous_offset, checkpoint_every=0)
    exo = np.random.default_rng([seed, EXO_STREAM])
    return World(eng, h, exo, input_rate, input_amp)
