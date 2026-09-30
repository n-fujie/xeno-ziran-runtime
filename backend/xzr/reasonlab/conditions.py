"""Operational world probes and configurable enabling conditions for reasoning.

Nothing here names what would make reasoning possible. Candidate enabling conditions are *measured operational
properties* of the world, each configurable:

    memory      mean memory in a set of configurations          (persistent external memory / shared records)
    activity    mean ignition rate in a set                     (repeated interaction)
    stability   fraction of a set's connections unchanged since the previous check   (stable addressability)
    mutation    connection changes per step, whole field        (low mutation rate)
    flow        mean load on a set of connections               (traceable dependency across a boundary)
    reach       fraction of a set reachable from another set within 3 hops (traceable dependency structure)
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from ..runtime.delta import StepDelta
from ..scenario.build import World

METRICS = ("memory", "activity", "stability", "mutation", "flow", "reach")
OPS = {"<": np.less, "<=": np.less_equal, ">": np.greater, ">=": np.greater_equal}


class WorldProbe:
    def __init__(self, world: World):
        self.world = world
        n = world.state.n
        self.ign = np.zeros(n)
        self.topo = 0.0
        self._prev_edges: dict[str, np.ndarray] = {}
        self._cache: dict[tuple, float] = {}

    def begin_check(self) -> None:
        """Values are cached within one check (stability compares with the previous check)."""
        self._cache = {}

    def update(self, d: StepDelta) -> None:
        self.ign *= 0.95
        self.ign[d.ignitions] += 0.05
        change = len(d.cuts) + len(d.new_connections) + len(d.removed_connections) + len(d.reconfigurations)
        self.topo = 0.9 * self.topo + 0.1 * change

    def _incident(self, target: str) -> np.ndarray:
        s = self.world.state
        m = np.zeros(s.n, bool)
        m[self.world.resolve(target, "nodes")] = True
        a = s.alive & (m[s.src] | m[s.dst])
        return np.sort(s.src[a].astype(np.int64) * s.n + s.dst[a])

    def value(self, metric: str, target: str = "", source: str = "") -> float:
        key = (metric, target, source)
        if key not in self._cache:
            self._cache[key] = self._value(metric, target, source)
        return self._cache[key]

    def _value(self, metric: str, target: str, source: str) -> float:
        s = self.world.state
        if metric == "memory":
            return float(s.memory[self.world.resolve(target, "nodes")].mean())
        if metric == "activity":
            return float(self.ign[self.world.resolve(target, "nodes")].mean())
        if metric == "mutation":
            return float(self.topo)
        if metric == "flow":
            e = self.world.resolve(target, "edges")
            return float(s.load[e].mean()) if len(e) else 0.0
        if metric == "stability":
            now = self._incident(target)
            prev = self._prev_edges.get(target)
            self._prev_edges[target] = now
            if prev is None:
                return 1.0
            u = len(np.union1d(prev, now))
            return 1.0 if u == 0 else len(np.intersect1d(prev, now)) / u
        if metric == "reach":
            m = s.reachable_mask()
            g = sp.csr_matrix((np.ones(int(m.sum())), (s.src[m], s.dst[m])), shape=(s.n, s.n))
            frontier = np.zeros(s.n, bool)
            frontier[self.world.resolve(source, "nodes")] = True
            seen = frontier.copy()
            gt = g.T.tocsr()
            for _ in range(3):
                frontier = ((gt @ frontier.astype(float)) > 0) & ~seen
                seen |= frontier
            tgt = self.world.resolve(target, "nodes")
            return float(seen[tgt].mean())
        raise ValueError(f"unknown metric {metric}")


def holds(probe: WorldProbe, cond: dict) -> tuple[bool, float]:
    v = probe.value(cond["metric"], cond.get("target", ""), cond.get("source", ""))
    return bool(OPS[cond["op"]](v, cond["value"])), v
