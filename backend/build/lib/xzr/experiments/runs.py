"""Shared experiment machinery: test configurations (dynamic regimes), paired runs, floors.

A *configuration* is a dynamic regime of the generated field. Every run of a configuration starts from the
same initial graph and local state (generator seed), and uses an engine random stream (engine seed) and an
optional intervention battery applied at a fixed step. Paired comparisons share all of these; only the runtime
variant differs.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

import numpy as np

from ..compare.trajectory import Recording
from ..lod.hierarchy import Hierarchy, build_hierarchy, symmetric_adjacency
from ..runtime.engine import Engine
from ..runtime.flags import Flags
from ..runtime.generator import latent_geometric
from ..runtime.intervention import Freeze, Gate, ScaleThreshold
from ..runtime.state import Params, State
from ..shapes.detector import ShapeDetector

N = 1500
HORIZON = 360
INTERVENE_AT = 120
SNAPSHOT_EVERY = 30


@dataclass(frozen=True)
class Config:
    name: str
    description: str
    params: dict = field(default_factory=dict)
    gen: dict = field(default_factory=dict)
    mem_coupling_scale: float = 1.0
    mem_decay: float | None = None


CONFIGS: tuple[Config, ...] = (
    Config("intermittent", "default parameters: sustained, intermittent cascades"),
    Config("sparse", "lower transmission gain: sparse activity near the sub-critical edge", params={"gain": 2.45}),
    Config("memory_heavy", "memory couplings doubled, slower memory decay", mem_coupling_scale=2.0, mem_decay=0.95),
    Config("churn", "fragile connections, frequent closure and reconfiguration",
           params={"connect_per_step": 12, "reconfigure_per_step": 6, "overload_steps": 2}, gen={"capacity": 2.0}),
)


@dataclass(frozen=True)
class Variant:
    """A runtime variant: flags plus optional parameter overrides (used for compensation searches)."""

    name: str
    flags: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    mem_coupling_scale: float = 1.0
    retention_add: float = 0.0


FULL = Variant("full")


def build_state(cfg: Config, gen_seed: int, variant: Variant = FULL) -> tuple[State, Hierarchy]:
    params = Params.from_dict({**cfg.params, **variant.params})
    g = latent_geometric(N, gen_seed, params=params, **cfg.gen)
    st = g.state
    scale = cfg.mem_coupling_scale * variant.mem_coupling_scale
    if scale != 1.0:
        st.base_mem_coupling *= scale
        st.mem_coupling[:] = st.base_mem_coupling
    if cfg.mem_decay is not None:
        st.base_mem_decay[:] = cfg.mem_decay
        st.mem_decay[:] = cfg.mem_decay
    if variant.retention_add:
        st.retention[:] = np.clip(st.retention + variant.retention_add, 0.0, 0.99)
    m = st.alive
    h = build_hierarchy(symmetric_adjacency(st.src[m], st.dst[m], st.n))
    return st, h


def intervention_battery(st: State, h) -> list:
    """Standard intervention set (runtime-level, opaque): freeze one macro region, close the boundary of
    another to 20% permeability, raise thresholds of a third by 30%."""
    a, b, c = h.resolve("1"), h.resolve("4"), h.resolve("6")
    inside = np.zeros(st.n, bool)
    inside[b] = True
    boundary = np.flatnonzero(st.alive & (inside[st.src] != inside[st.dst]))
    return [Freeze(tuple(a.tolist())), Gate(tuple(boundary.tolist()), 0.2), ScaleThreshold(tuple(c.tolist()), 1.3)]


def array_hashes(st: State) -> dict[str, str]:
    return {k: hashlib.sha1(np.ascontiguousarray(v).tobytes()).hexdigest()[:16] for k, v in st.arrays().items()}


def run(cfg: Config, variant: Variant, gen_seed: int, engine_seed: int, intervene: bool = False,
        eps: float = 0.0, horizon: int = HORIZON) -> Recording:
    st, h = build_state(cfg, gen_seed, variant)
    if eps:
        st.diff[0] += eps
    flags = Flags.from_dict(variant.flags)
    eng = Engine(st, engine_seed, checkpoint_every=0, flags=flags)
    det = ShapeDetector(h, graph_every=10)
    rec = Recording(n=st.n, snapshot_every=SNAPSHOT_EVERY)
    battery = intervention_battery(st, h) if intervene else []
    engine_time = 0.0
    for _ in range(horizon):
        if intervene and eng.state.t == INTERVENE_AT:
            eng.set_overlay(battery)
        t0 = time.perf_counter()
        d = eng.step()
        engine_time += time.perf_counter() - t0
        r = det.observe(d, eng.state)
        rec.record(d, eng.state)
        if "graph" in r:
            rec.signatures.append(list(det.signatures))
    rec.attach_detector(det)
    rec.ms_per_step = 1000 * engine_time / horizon
    rec.state_bytes = int(sum(v.nbytes for v in eng.state.arrays().values()))
    rec.hashes = array_hashes(eng.state)
    return rec
