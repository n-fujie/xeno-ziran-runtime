"""Build a runnable world from a scenario: state, engine, hierarchy, projections and target resolver."""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from ..lod.hierarchy import Hierarchy, build_hierarchy, symmetric_adjacency
from ..lod.layouts import address_layout, geo_layout, network_layout, normalize
from ..runtime.engine import Driver, Engine
from ..runtime.generator import latent_geometric
from ..runtime.intervention import Freeze
from ..runtime.state import Params, State, allocate
from .model import Scenario, SetSpec

_NODE_REF = re.compile(r"^(?:c|#|configuration\s*)(\d+)$", re.IGNORECASE)
_ADDR = re.compile(r"^@?(\d(?:\.\d)*)$")


@dataclass
class World:
    scenario: Scenario
    engine: Engine
    hierarchy: Hierarchy
    positions: dict[str, np.ndarray]

    @property
    def state(self) -> State:
        return self.engine.state

    # ------------------------------------------------------------------ opaque target resolution
    def resolve(self, target: str, want: str = "nodes") -> np.ndarray:
        """Resolve a target name to configuration indices (``want='nodes'``) or connection ids (``'edges'``)."""
        target = target.strip()
        s = self.state
        m = _NODE_REF.match(target)
        if m:
            i = int(m.group(1))
            if not 0 <= i < s.n:
                raise KeyError(f"no configuration {i}")
            nodes = np.array([i], dtype=np.int32)
            return nodes if want == "nodes" else self._boundary_edges(nodes)
        if target in self.scenario.sets:
            return self._resolve_set(target, want)
        am = _ADDR.match(target)
        if am:
            nodes = self.hierarchy.resolve(am.group(1))
            return nodes if want == "nodes" else self._boundary_edges(nodes)
        raise KeyError(f"unknown target {target!r} (use c<index>, @<address>, or a set name: "
                       f"{', '.join(sorted(self.scenario.sets)) or 'none defined'})")

    def _boundary_edges(self, nodes: np.ndarray) -> np.ndarray:
        s = self.state
        inset = np.zeros(s.n, dtype=bool)
        inset[nodes] = True
        return np.flatnonzero(s.alive & (inset[s.src] != inset[s.dst])).astype(np.int32)

    def _resolve_set(self, name: str, want: str) -> np.ndarray:
        spec: SetSpec = self.scenario.sets[name]
        s = self.state
        if spec.edges is not None:
            e = np.asarray(spec.edges, dtype=np.int32)
            return e if want == "edges" else np.unique(np.concatenate([s.src[e], s.dst[e]])).astype(np.int32)
        if spec.boundary_of is not None:
            e = self._boundary_edges(self._resolve_set(spec.boundary_of, "nodes"))
            return e if want == "edges" else np.unique(np.concatenate([s.src[e], s.dst[e]])).astype(np.int32)
        if spec.between is not None:
            a = np.zeros(s.n, dtype=bool)
            b = np.zeros(s.n, dtype=bool)
            a[self._resolve_set(spec.between[0], "nodes")] = True
            b[self._resolve_set(spec.between[1], "nodes")] = True
            e = np.flatnonzero(s.alive & ((a[s.src] & b[s.dst]) | (b[s.src] & a[s.dst]))).astype(np.int32)
            return e if want == "edges" else np.unique(np.concatenate([s.src[e], s.dst[e]])).astype(np.int32)
        parts = []
        if spec.nodes is not None:
            parts.append(np.asarray(spec.nodes, dtype=np.int32))
        if spec.address is not None:
            parts.append(self.hierarchy.resolve(spec.address))
        for addr in spec.addresses or []:
            parts.append(self.hierarchy.resolve(addr))
        if spec.random is not None:
            rng = np.random.default_rng(int(spec.random.get("seed", 0)))
            k = max(1, int(s.n * float(spec.random.get("fraction", 0.01))))
            parts.append(np.sort(rng.choice(s.n, size=k, replace=False)).astype(np.int32))
        nodes = np.unique(np.concatenate(parts)).astype(np.int32) if parts else np.zeros(0, np.int32)
        return nodes if want == "nodes" else self._boundary_edges(nodes)

    def relation_edges(self, a: str, b: str) -> np.ndarray:
        """Alive connections from target a to target b."""
        s = self.state
        ma = np.zeros(s.n, dtype=bool)
        mb = np.zeros(s.n, dtype=bool)
        ma[self.resolve(a, "nodes")] = True
        mb[self.resolve(b, "nodes")] = True
        return np.flatnonzero(s.alive & ma[s.src] & mb[s.dst]).astype(np.int32)


def _explicit_state(sc: Scenario, params: Params) -> tuple[State, np.ndarray | None]:
    ex = sc.explicit
    assert ex is not None
    n, e = len(ex.nodes), len(ex.edges)
    st = allocate(n, e + max(256, e // 3), params)
    for i, nd in enumerate(ex.nodes):
        st.theta[i] = nd.theta
        st.retention[i] = nd.retention
        st.mem_decay[i] = st.base_mem_decay[i] = nd.mem_decay
        st.mem_coupling[i] = st.base_mem_coupling[i] = nd.mem_coupling
        st.cap[i] = nd.cap if nd.cap is not None else 1.8 * nd.theta
        st.form[i] = nd.form % params.n_forms
        st.diff[i] = nd.diff
        if nd.geo is not None:
            st.geo[i] = nd.geo
    for j, ed in enumerate(ex.edges):
        st.src[j], st.dst[j] = ed.src, ed.dst
        st.weight[j] = st.base_weight[j] = ed.weight
        st.alive[j] = True
        st.transform[j] = ed.transform % params.n_forms
        st.capacity[j] = ed.capacity
    latent = np.asarray(ex.latent, dtype=np.float64) if ex.latent is not None else None
    return st, latent


def build_world(sc: Scenario, flags=None) -> World:
    params = Params.from_dict(sc.params)
    latent_opt: np.ndarray | None
    if sc.generator is not None:
        g = sc.generator
        gen = latent_geometric(g.n, sc.seed, mean_degree=g.mean_degree, long_range=g.long_range,
                               reciprocity=g.reciprocity, groups=g.groups, geo_fraction=g.geo_fraction,
                               transform_fraction=g.transform_fraction, capacity=g.capacity,
                               heterogeneity=g.heterogeneity, cap_ratio=g.cap_ratio, params=params)
        state, latent_opt = gen.state, gen.latent
    else:
        state, latent_opt = _explicit_state(sc, params)
    m = state.alive
    h = build_hierarchy(symmetric_adjacency(state.src[m], state.dst[m], state.n))
    positions = {
        "network": network_layout(h, latent_opt, sc.seed),
        "address": address_layout(h),
        "shape": normalize(np.stack([h.path.astype(np.float64), np.zeros(state.n)], 1)),  # replaced once running
        "geo": geo_layout(state.geo),
    }
    engine = Engine(state, sc.seed, checkpoint_every=sc.checkpoint_every, flags=flags)
    world = World(sc, engine, h, positions)
    engine.drivers = [Driver(world.resolve(d.set, "nodes"), d.period, d.amount, d.phase) for d in sc.drivers]
    engine.base_overlay = [Freeze(tuple(world.resolve(f, "nodes").tolist())) for f in sc.frozen]
    engine.set_overlay([])
    engine.log.clear()
    # the initial checkpoint must reflect base constraints
    engine.checkpoints.clear()
    engine._save_checkpoint()
    return world
