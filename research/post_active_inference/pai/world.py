"""Benchmark world: the existing runtime plus an observation/actuation interface (a Markov-blanket proxy).

Nothing here changes runtime semantics. The world is ``scenario.topologies.topology("modular", …)`` driven by
``runtime.engine.Engine``. The benchmark adds:

* a target region T (one module of the modular world), its two halves and four quarters (for latent split/merge
  measurements), and the neighbour module N (most connections to T);
* ``SensorArray``: K channels, each the mean ignition rate of a node set (initially disjoint samples of T) over a
  sensor window, with perturbable dropout, reassignment, delay, noise, scale/offset, fold, coarsening,
  duplication, asynchrony and window length. Sensor perturbations act on readings only; the world is untouched;
* ``Actuator``: maps an action id to runtime overlay items / actions on a node set U (initially U = T), with
  perturbable node set, leakage, delay, drop probability, per-decision node noise and action permutation;
* ground-truth probes: ``probe`` forks the engine (``Engine.fork``, exact continuation) and measures the effect of
  every action on T against noop, plus the per-node response footprint.

World perturbations are runtime overlay items placed in ``Engine.base_overlay``, or runtime actions. Controller
actions are the engine's ``overlay``; the two never overwrite each other.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_BACKEND = Path(__file__).resolve().parents[3] / "backend"
if str(_BACKEND) not in sys.path:  # source checkout: use the repository's runtime
    sys.path.insert(0, str(_BACKEND))

from xzr.runtime.engine import Engine  # noqa: E402
from xzr.runtime.intervention import Gate, Inject, ScaleThreshold  # noqa: E402
from xzr.runtime.state import Params  # noqa: E402
from xzr.scenario.topologies import topology  # noqa: E402

ACTIONS = ("noop", "damp", "excite", "shield", "pulse")
N_LEVELS = 5          # discrete levels of the target region's activity (latent state space of the comparator)
PREFERRED_LEVEL = 2   # default goal level (kept for reference); the benchmark uses the setpoint schedule below
SETPOINTS = (1, 3)    # goal alternates between these levels …
SETPOINT_PERIOD = 100 # … every this many steps (from the end of calibration), so that no world's resting level
                      # satisfies the goal by itself


def setpoint(t: int, calib_end: int) -> int:
    return SETPOINTS[((t - calib_end) // SETPOINT_PERIOD) % len(SETPOINTS)] if t >= calib_end else PREFERRED_LEVEL
RING = 64             # per-step ignition history kept (steps), ≥ the longest sensor window / decision interval


@dataclass
class WorldConfig:
    n: int = 1500
    gen_seed: int = 3
    topology: str = "modular"
    gain: float = 3.235               # cached calibration modular|1500 (experiments/results/resolution/calibration.json)
    target_module: int = 1
    sensor_channels: int = 6
    sensor_size: int = 8
    dt: int = 10                      # decision interval (steps)
    damp: float = 2.5                 # threshold factor of the damp action
    excite: float = 0.4               # threshold factor of the excite action
    shield: float = 0.2               # permeability of connections into U under the shield action
    pulse: float = 0.6                # difference injected into every node of U by the pulse action

    @classmethod
    def from_dict(cls, d: dict | None) -> WorldConfig:
        c = cls()
        for k, v in (d or {}).items():
            if not hasattr(c, k):
                raise ValueError(f"unknown world parameter {k}")
            setattr(c, k, type(getattr(c, k))(v))
        return c


# ------------------------------------------------------------------------------------------------ sensors
@dataclass
class SensorArray:
    channels: list[np.ndarray]
    window: int
    rng: np.random.Generator
    dropout: np.ndarray = field(default=None)       # bool[K]: reading forced to 0
    active: np.ndarray = field(default=None)        # bool[K]: False = channel missing (NaN)
    perm: np.ndarray = field(default=None)          # channel order
    duplicate_of: np.ndarray = field(default=None)  # int[K]: channel k reports channel duplicate_of[k]
    delay: int = 0                                  # decisions
    noise: float = 0.0                              # Gaussian sd in reading units
    scale: float = 1.0
    offset: float = 0.0
    fold: float | None = None                       # relabel: x → |x − fold| (non-monotone outcome map)
    coarsen: float = 0.0                            # grid step (merges outcome levels)
    async_p: float = 0.0                            # probability a channel keeps its previous reading
    _queue: list = field(default_factory=list)
    _last: np.ndarray | None = None

    def __post_init__(self) -> None:
        k = len(self.channels)
        self.dropout = np.zeros(k, bool) if self.dropout is None else self.dropout
        self.active = np.ones(k, bool) if self.active is None else self.active
        self.perm = np.arange(k) if self.perm is None else self.perm
        self.duplicate_of = np.arange(k) if self.duplicate_of is None else self.duplicate_of
        self.base_channels = [c.copy() for c in self.channels]

    def raw(self, ring: np.ndarray, filled: int, steps: int | None = None) -> np.ndarray:
        """Unperturbed channel readings: mean ignitions per node per step over the sensor window."""
        w = max(1, min(steps or self.window, filled, RING))
        recent = ring[:w].sum(0) / w
        return np.array([recent[c].mean() if len(c) else 0.0 for c in self.channels])

    def read(self, ring: np.ndarray, filled: int) -> np.ndarray:
        x = self.raw(ring, filled)
        x = x[self.duplicate_of]
        if self.async_p > 0 and self._last is not None:
            keep = self.rng.random(len(x)) < self.async_p
            x = np.where(keep, self._last, x)
        self._last = x.copy()
        x = x * self.scale + self.offset
        if self.noise > 0:
            x = x + self.rng.normal(0.0, self.noise, len(x))
        if self.fold is not None:
            x = np.abs(x - self.fold)
        if self.coarsen > 0:
            x = np.round(x / self.coarsen) * self.coarsen
        x = np.where(self.dropout, 0.0, x)
        x = np.where(self.active, x, np.nan)[self.perm]
        self._queue.append(x)
        if len(self._queue) > self.delay + 1:
            self._queue.pop(0)
        return self._queue[0] if len(self._queue) > self.delay else np.full(len(x), np.nan)


def aggregate(x: np.ndarray) -> float:
    """The controllers' scalar reading: mean of the available channels (NaN if none)."""
    v = x[np.isfinite(x)]
    return float(v.mean()) if len(v) else float("nan")


# ------------------------------------------------------------------------------------------------ actuator
@dataclass
class Actuator:
    U: np.ndarray
    cfg: WorldConfig
    rng: np.random.Generator
    leak_nodes: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int32))
    leak: float = 0.0              # fraction of the action's strength also applied to leak_nodes
    delay: int = 0                 # decisions
    drop_p: float = 0.0            # probability an action has no effect
    node_noise: float = 0.0        # fraction of U replaced by random outside nodes each decision
    perm: np.ndarray = field(default_factory=lambda: np.arange(len(ACTIONS)))
    outside: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int32))
    _queue: list = field(default_factory=list)

    def effective(self, a: int) -> int:
        self._queue.append(a)
        if len(self._queue) > self.delay + 1:
            self._queue.pop(0)
        a = self._queue[0] if len(self._queue) > self.delay else 0
        if self.drop_p > 0 and self.rng.random() < self.drop_p:
            return 0
        return int(self.perm[a])

    def nodes(self) -> np.ndarray:
        u = self.U
        if self.node_noise > 0 and len(self.outside):
            k = int(round(self.node_noise * len(u)))
            if k:
                keep = self.rng.permutation(len(u))[k:]
                u = np.concatenate([u[keep], self.rng.choice(self.outside, k, replace=False)])
        return np.unique(u).astype(np.int32)

    def compile(self, a: int, state, u: np.ndarray | None = None) -> tuple[list, list]:
        """(overlay items, one-shot actions) for action ``a`` (already effective) on node set ``u``."""
        u = self.nodes() if u is None else u
        c = self.cfg
        items: list = []
        acts: list = []
        name = ACTIONS[a]

        def scaled(nodes, f, strength=1.0):
            if len(nodes):
                items.append(ScaleThreshold(tuple(int(i) for i in nodes), 1.0 + (f - 1.0) * strength))

        if name == "damp":
            scaled(u, c.damp)
            scaled(self.leak_nodes, c.damp, self.leak)
        elif name == "excite":
            scaled(u, c.excite)
            scaled(self.leak_nodes, c.excite, self.leak)
        elif name == "shield":
            for nodes, strength in ((u, 1.0), (self.leak_nodes, self.leak)):
                if len(nodes) and strength > 0:
                    inside = np.zeros(state.n, bool)
                    inside[nodes] = True
                    e = np.flatnonzero(state.alive & inside[state.dst] & ~inside[state.src])
                    if len(e):
                        items.append(Gate(tuple(int(i) for i in e), 1.0 + (c.shield - 1.0) * strength))
        elif name == "pulse":
            if len(u):
                acts.append(Inject(tuple(int(i) for i in u), c.pulse))
            if len(self.leak_nodes) and self.leak > 0:
                acts.append(Inject(tuple(int(i) for i in self.leak_nodes), c.pulse * self.leak))
        return items, acts


# ------------------------------------------------------------------------------------------------ world
class BenchWorld:
    """One run's world. ``gen_seed`` fixes the graph and local state; ``seed`` is the engine random stream."""

    def __init__(self, cfg: WorldConfig, seed: int, boundary: bool = True):
        self.cfg = cfg
        self.seed = seed
        asm = topology(cfg.topology, cfg.n, cfg.gen_seed, Params(gain=cfg.gain))
        st = asm.state
        self.engine = Engine(st, seed, checkpoint_every=0)
        self.modules = {int(k[3:]): v for k, v in asm.sets.items() if k.startswith("mod")}
        self.module_of = np.zeros(cfg.n, np.int32)
        for k, v in self.modules.items():
            self.module_of[v] = k
        wrng = np.random.default_rng(cfg.gen_seed * 7919 + 17)   # world-structure randomness (fixed per world)
        self.T = np.sort(self.modules[cfg.target_module]).astype(np.int32)
        sh = wrng.permutation(self.T)
        self.halves = [np.sort(sh[: len(sh) // 2]), np.sort(sh[len(sh) // 2:])]
        self.quarters = [np.sort(q) for q in np.array_split(sh, 4)]
        m = st.alive
        inT = np.isin(st.src[m], self.T) ^ np.isin(st.dst[m], self.T)
        other = np.where(np.isin(st.src[m], self.T), st.dst[m], st.src[m])[inT]
        cnt = np.bincount(self.module_of[other], minlength=len(self.modules))
        cnt[cfg.target_module] = -1
        self.N = np.sort(self.modules[int(np.argmax(cnt))]).astype(np.int32)
        self.neighbour_module = int(np.argmax(cnt))
        self.outside = np.setdiff1d(np.arange(cfg.n), self.T).astype(np.int32)
        self.adj0 = (st.src[m].copy(), st.dst[m].copy())                 # initial undirected structure (hop distances)
        # interface (seeded per engine seed so sensor noise etc. is paired across controllers)
        irng = np.random.default_rng(seed * 104729 + 3)
        if boundary:
            pool = wrng.permutation(self.T)
            chans = [np.sort(pool[i * cfg.sensor_size:(i + 1) * cfg.sensor_size]) for i in range(cfg.sensor_channels)]
            U = self.T.copy()
        else:  # boundary ablation: no sensory/active partition — channels and actuator sample the whole field
            pool = wrng.permutation(cfg.n)
            chans = [np.sort(pool[i * cfg.sensor_size:(i + 1) * cfg.sensor_size]) for i in range(cfg.sensor_channels)]
            U = np.sort(wrng.choice(cfg.n, len(self.T), replace=False)).astype(np.int32)
        self.sensors = SensorArray(chans, cfg.dt, irng)
        self.actuator = Actuator(U, cfg, np.random.default_rng(seed * 15485863 + 5), outside=self.outside)
        self.ring = np.zeros((RING, cfg.n), np.uint8)
        self.filled = 0
        self.dt = cfg.dt
        self.listeners: list = []

    @property
    def state(self):
        return self.engine.state

    @property
    def t(self) -> int:
        return self.engine.state.t

    def step(self) -> None:
        d = self.engine.step()
        self.ring = np.roll(self.ring, 1, axis=0)
        self.ring[0] = 0
        self.ring[0, d.ignitions] = 1
        self.filled = min(self.filled + 1, RING)
        for f in self.listeners:
            f(d, self.engine.state)

    def act(self, a: int) -> int:
        """Apply controller action ``a`` for the next decision interval. Returns the effective action."""
        ea = self.actuator.effective(a)
        items, acts = self.actuator.compile(ea, self.state)
        self.engine.set_overlay(items)
        if acts:
            self.engine.apply(acts)
        return ea

    def activity(self, nodes: np.ndarray, steps: int | None = None) -> float:
        w = max(1, min(steps or self.dt, self.filled))
        return float(self.ring[:w, nodes].sum() / (w * max(len(nodes), 1)))

    def node_activity(self, steps: int) -> np.ndarray:
        w = max(1, min(steps, self.filled))
        return self.ring[:w].sum(0) / w

    def true_level(self, steps: int | None = None) -> float:
        return self.activity(self.T, steps)


def level_of(x: float, edges: np.ndarray) -> int | None:
    if not np.isfinite(x):
        return None
    return int(np.searchsorted(edges, x, side="right"))


# ------------------------------------------------------------------------------------------------ probes
def probe(world: BenchWorld, steps: int = 20) -> dict:
    """Ground-truth action→effect map and response footprint, by exact forks of the current engine.

    effect[a] = mean ignition rate of T over ``steps`` with action a held, minus the same under noop. The actions
    go through the *current* actuator mapping (its node set, leak and permutation; no delay/drop randomness). The
    footprint is the set of |T| nodes with the largest per-node |rate(damp) − rate(noop)| + |rate(excite) − rate(noop)|;
    response_share_T is the share of that response mass inside T."""
    eng = world.engine
    act = world.actuator
    rates = []
    for a in range(len(ACTIONS)):
        f = eng.fork()
        items, acts = act.compile(int(act.perm[a]), f.state, u=act.U)
        f.set_overlay(items)
        if acts:
            f.apply(acts)
        cnt = np.zeros(world.cfg.n)
        for _ in range(steps):
            d = f.step()
            np.add.at(cnt, d.ignitions, 1.0)
        rates.append(cnt / steps)
    rates = np.array(rates)
    means = rates[:, world.T].mean(1)
    eff = means - means[0]
    resp = np.abs(rates[1] - rates[0]) + np.abs(rates[2] - rates[0])   # damp and excite responses
    k = len(world.T)
    foot = np.sort(np.argsort(-resp, kind="stable")[:k]) if resp.max() > 0 else np.zeros(0, np.int64)
    share = float(resp[world.T].sum() / resp.sum()) if resp.sum() > 0 else None
    return {"effect": eff.tolist(), "footprint": foot.astype(np.int32).tolist(), "response_share_T": share}
