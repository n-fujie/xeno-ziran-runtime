"""Seeded topology families, memory regimes, return/delay structures and targeted structures for the resolution
escalation experiments.

Every generator returns an :class:`Assembled` world skeleton: a runtime ``State`` plus named node sets (modules,
regions) that the experiment harness turns into scenario sets. Node parameters are drawn exactly as in
``runtime.generator.latent_geometric`` (same distributions), so topology is the only thing that changes between
families. Nothing here names what a configuration is.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..runtime.generator import latent_geometric
from ..runtime.state import Params, State, allocate

TOPOLOGIES = ("sparse_random", "dense_random", "modular", "hierarchical", "small_world", "highly_clustered",
              "weakly_connected", "bottlenecked", "multi_region", "nested_multiscale")
MEMORY_REGIMES = ("near_zero", "short", "medium", "long", "external_persistent", "fragmented", "delayed_return")
RETURN_STRUCTURES = ("immediate", "delayed", "multi_step_delayed", "none", "competing")
DISCONNECTION_STRUCTURES = ("single_bridge", "bottleneck", "sparse_tree", "fragile_loop", "one_way_path",
                            "delayed_return_route", "high_path_dependence", "isolated_regions_bridge")


@dataclass
class Assembled:
    state: State
    sets: dict[str, np.ndarray] = field(default_factory=dict)  # name -> node indices
    world_items: list[dict] = field(default_factory=list)  # permanent world-side overlay specs
    info: dict = field(default_factory=dict)


# ------------------------------------------------------------------------------------------------ helpers
def _dedupe(src: np.ndarray, dst: np.ndarray, n: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    keep = src != dst
    key = np.unique(src[keep].astype(np.int64) * n + dst[keep])
    key = key[rng.permutation(len(key))]
    return (key // n).astype(np.int32), (key % n).astype(np.int32)


def _reciprocate(src: np.ndarray, dst: np.ndarray, rng: np.random.Generator, p: float) -> tuple[np.ndarray, np.ndarray]:
    back = rng.random(len(src)) < p
    return np.concatenate([src, dst[back]]), np.concatenate([dst, src[back]])


def _blocks(n: int, k: int, rng: np.random.Generator) -> np.ndarray:
    """Module label per node: k modules of (almost) equal size, randomly placed in index space."""
    lab = np.arange(n) * k // n
    return lab[rng.permutation(n)]


def _sbm(labels: np.ndarray, deg: float, p_in: float, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Directed block model with expected out-degree ``deg`` and share ``p_in`` of connections inside modules."""
    n = len(labels)
    m = int(round(n * deg))
    src = rng.integers(0, n, m)
    inside = rng.random(m) < p_in
    members = [np.flatnonzero(labels == k) for k in range(int(labels.max()) + 1)]
    dst = rng.integers(0, n, m)
    for k, mem in enumerate(members):
        sel = inside & (labels[src] == k)
        dst[sel] = mem[rng.integers(0, len(mem), int(sel.sum()))]
    return src, dst


def assemble(n: int, src: np.ndarray, dst: np.ndarray, rng: np.random.Generator, params: Params | None = None,
             field_: np.ndarray | None = None, heterogeneity: float = 0.35, capacity: float = 3.0,
             cap_ratio: float = 1.8, transform_fraction: float = 0.08, spare: float = 0.34) -> State:
    """Allocate a state for a given connection list with node/connection parameters drawn as in the default
    generator (``field_`` is the smooth excitability field; iid if omitted)."""
    params = params or Params()
    src, dst = _dedupe(np.asarray(src), np.asarray(dst), n, rng)
    e = len(src)
    st = allocate(n, e + max(2048, int(e * spare)), params)
    f = rng.normal(0, 1, n) if field_ is None else (field_ - field_.mean()) / (field_.std() + 1e-9)
    st.theta[:] = np.clip(rng.normal(1.0, 0.15, n) * np.exp(heterogeneity * f), 0.3, 4.0)
    st.cap[:] = np.exp(rng.normal(np.log(cap_ratio), 0.25, n)) * st.theta
    st.retention[:] = np.clip(rng.beta(9, 1.8, n), 0.4, 0.98)
    st.base_mem_decay[:] = st.mem_decay[:] = rng.uniform(0.8, 0.95, n)
    st.base_mem_coupling[:] = st.mem_coupling[:] = rng.choice([-0.25, -0.1, 0.0, 0.1, 0.25], n,
                                                              p=[0.25, 0.2, 0.2, 0.2, 0.15])
    st.form[:] = rng.integers(0, params.n_forms, n)
    st.diff[:] = rng.exponential(0.3, n)
    st.src[:e], st.dst[:e] = src, dst
    w = np.clip(np.exp(rng.normal(np.log(0.5), 0.5, e)), 0.08, 2.5)
    st.weight[:e] = st.base_weight[:e] = w
    st.alive[:e] = True
    tr = rng.random(e) < transform_fraction
    st.transform[:e] = np.where(tr, rng.integers(1, params.n_forms, e), 0)
    st.capacity[:e] = np.exp(rng.normal(np.log(capacity), 0.4, e))
    return st


def _module_field(labels: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Excitability field that is smooth over modules (module offset + small node noise)."""
    off = rng.normal(0, 1, int(labels.max()) + 1)
    return off[labels] + 0.3 * rng.normal(0, 1, len(labels))


def _module_sets(labels: np.ndarray, prefix: str = "mod") -> dict[str, np.ndarray]:
    return {f"{prefix}{k}": np.flatnonzero(labels == k).astype(np.int32) for k in range(int(labels.max()) + 1)}


# ------------------------------------------------------------------------------------------------ topology families
def topology(kind: str, n: int, seed: int, params: Params | None = None, mean_degree: float = 6.0,
             p_in: float | None = None) -> Assembled:
    rng = np.random.default_rng(seed)
    params = params or Params()
    if kind == "multi_region":  # the default generator: latent multi-region field
        g = latent_geometric(n, seed, mean_degree=mean_degree, geo_fraction=0.0, params=params)
        lab = np.clip((g.latent[:, 0] * 4).astype(int), 0, 3) * 4 + np.clip((g.latent[:, 1] * 4).astype(int), 0, 3)
        return Assembled(g.state, _module_sets(lab), info={"family": kind})
    if kind in ("sparse_random", "dense_random"):
        deg = 2.5 if kind == "sparse_random" else 14.0
        m = int(n * deg / 1.35)
        src, dst = rng.integers(0, n, m), rng.integers(0, n, m)
        src, dst = _reciprocate(src, dst, rng, 0.35)
        lab = _blocks(n, 16, rng)
        st = assemble(n, src, dst, rng, params)
        return Assembled(st, _module_sets(lab), info={"family": kind, "mean_degree": deg})
    if kind in ("modular", "weakly_connected"):
        lab = _blocks(n, 16, rng)
        p_in = p_in if p_in is not None else (0.85 if kind == "modular" else 0.995)
        src, dst = _sbm(lab, mean_degree / 1.35, p_in, rng)
        src, dst = _reciprocate(src, dst, rng, 0.35)
        st = assemble(n, src, dst, rng, params, field_=_module_field(lab, rng))
        return Assembled(st, _module_sets(lab), info={"family": kind, "p_in": p_in})
    if kind == "bottlenecked":
        lab = _blocks(n, 16, rng)
        half = lab // 8  # modules 0–7 | 8–15
        src, dst = _sbm(lab, mean_degree / 1.35, 0.85, rng)
        cross = half[src] != half[dst]
        src, dst = src[~cross], dst[~cross]
        a, b = np.flatnonzero(half == 0), np.flatnonzero(half == 1)
        k = 4  # bridge connections each way
        bs = np.concatenate([rng.choice(a, k), rng.choice(b, k)])
        bd = np.concatenate([rng.choice(b, k), rng.choice(a, k)])
        src, dst = _reciprocate(src, dst, rng, 0.35)
        src, dst = np.concatenate([src, bs]), np.concatenate([dst, bd])
        st = assemble(n, src, dst, rng, params, field_=_module_field(lab, rng))
        sets = _module_sets(lab) | {"side0": a.astype(np.int32), "side1": b.astype(np.int32)}
        return Assembled(st, sets, info={"family": kind, "bridges_each_way": k})
    if kind == "small_world" or kind == "highly_clustered":
        # ring lattice (k neighbours each side); small world rewires a fraction of connections uniformly
        k = 3 if kind == "small_world" else 4
        base = np.arange(n)
        offs = np.concatenate([np.arange(1, k + 1), -np.arange(1, k + 1)])
        src = np.repeat(base, len(offs))
        dst = (src + np.tile(offs, n)) % n
        keep = rng.random(len(src)) < (mean_degree / (2 * k) if kind == "small_world" else 1.0)
        src, dst = src[keep], dst[keep]
        if kind == "small_world":
            rw = rng.random(len(src)) < 0.05
            dst[rw] = rng.integers(0, n, int(rw.sum()))
        perm = rng.permutation(n)  # hide the lattice order from index space
        src, dst = perm[src], perm[dst]
        lab = np.empty(n, dtype=int)
        lab[perm] = np.arange(n) * 16 // n  # modules = contiguous lattice arcs
        pos = np.empty(n)
        pos[perm] = np.arange(n) / n
        field_ = np.sin(2 * np.pi * 3 * pos) + 0.5 * np.sin(2 * np.pi * 7 * pos + 1.0)
        st = assemble(n, src, dst, rng, params, field_=field_)
        return Assembled(st, _module_sets(lab), info={"family": kind, "lattice_k": k})
    if kind in ("hierarchical", "nested_multiscale"):
        # 3 nested levels of 4 → 64 leaf modules
        leaf = _blocks(n, 64, rng)
        lv1, lv2 = leaf // 4, leaf // 16
        if kind == "nested_multiscale":
            # every level connects, with density decreasing by level: leaf 70%, sibling 18%, cousin 8%, far 4%
            m = int(n * mean_degree / 1.35)
            src = rng.integers(0, n, m)
            u = rng.random(m)
            lvl = np.select([u < 0.70, u < 0.88, u < 0.96], [0, 1, 2], 3)
            groups = (leaf, lv1, lv2, np.zeros(n, int))
            dst = rng.integers(0, n, m)
            for lv in range(3):
                grp = groups[lv]
                for k in np.unique(grp):
                    mem = np.flatnonzero(grp == k)
                    sel = (lvl == lv) & (grp[src] == k)
                    dst[sel] = mem[rng.integers(0, len(mem), int(sel.sum()))]
            src, dst = _reciprocate(src, dst, rng, 0.35)
        else:
            # hub hierarchy: dense leaf modules; each module has 3 hubs; hubs connect only to hubs of sibling
            # modules at the next level, level hubs to level hubs above (tree-structured routing)
            src, dst = _sbm(leaf, mean_degree / 1.35, 1.0, rng)
            src, dst = _reciprocate(src, dst, rng, 0.35)
            hubs = {k: rng.choice(np.flatnonzero(leaf == k), 3, replace=False) for k in range(64)}
            es, ed = [], []
            for k in range(64):
                sibs = [j for j in range(64) if j // 4 == k // 4 and j != k]
                for j in sibs:
                    es.append(rng.choice(hubs[k], 2))
                    ed.append(rng.choice(hubs[j], 2))
                if k % 4 == 0:  # module 0 of each group routes to other groups of its level-2 parent
                    for j in range(0, 64, 4):
                        if j != k and j // 16 == k // 16:
                            es.append(hubs[k][:1])
                            ed.append(hubs[j][:1])
                if k % 16 == 0:  # top-level routing between level-2 groups
                    for j in range(0, 64, 16):
                        if j != k:
                            es.append(hubs[k][:2])
                            ed.append(hubs[j][:2])
            src = np.concatenate([src, *es])
            dst = np.concatenate([dst, *ed])
        field_ = _module_field(lv2, rng) + 0.5 * _module_field(leaf, rng)
        st = assemble(n, src, dst, rng, params, field_=field_)
        return Assembled(st, _module_sets(lv1), info={"family": kind, "levels": 3, "leaf_modules": 64})
    raise ValueError(f"unknown topology {kind}")


# ------------------------------------------------------------------------------------------------ modifiers
def _add_chain(st: State, nodes: np.ndarray, frm: np.ndarray, to: np.ndarray, rng: np.random.Generator,
               w: float = 1.2) -> None:
    """A relay path frm → nodes[0] → … → nodes[-1] → to (strong connections, placed in free slots)."""
    from ..runtime.ops import add_connection
    seq = [int(rng.choice(frm)), *map(int, nodes), int(rng.choice(to))]
    for a, b in zip(seq[:-1], seq[1:], strict=True):
        e = add_connection(st, a, b, w)
        if e >= 0:
            st.capacity[e] = 6.0


def _remove_between(st: State, a: np.ndarray, b: np.ndarray) -> int:
    ma, mb = np.zeros(st.n, bool), np.zeros(st.n, bool)
    ma[a], mb[b] = True, True
    e = st.alive & ma[st.src] & mb[st.dst]
    st.alive[e] = False
    return int(e.sum())


def apply_return_structure(asm: Assembled, kind: str, seed: int) -> Assembled:
    """Return / delay structure between two regions A (module 0) and B (module 1) of a modular world."""
    rng = np.random.default_rng(seed + 7)
    st = asm.state
    a, b = asm.sets["mod0"], asm.sets["mod1"]
    asm.sets["A"], asm.sets["B"] = a, b
    other = np.setdiff1d(np.arange(st.n), np.concatenate([a, b]))
    if kind == "immediate":
        alive = np.flatnonzero(st.alive)
        from ..runtime.ops import add_connection
        for e in alive[rng.random(len(alive)) < 0.6]:
            add_connection(st, int(st.dst[e]), int(st.src[e]), float(st.base_weight[e]))
    elif kind in ("delayed", "multi_step_delayed", "competing"):
        _remove_between(st, b, a)
        lengths = {"delayed": [5], "multi_step_delayed": [25], "competing": [5, 17]}[kind]
        used: list[int] = []
        for L in lengths:
            relay = rng.choice(np.setdiff1d(other, used), L, replace=False)
            used += relay.tolist()
            _add_chain(st, relay, b, a, rng)
            asm.sets[f"relay{L}"] = relay.astype(np.int32)
    elif kind == "none":
        # no return path anywhere: keep only connections that go forward in a fixed node order (a DAG)
        order = np.empty(st.n, dtype=np.int64)
        lab = np.zeros(st.n, dtype=np.int64)
        for k in range(16):
            lab[asm.sets[f"mod{k}"]] = k
        order[np.lexsort((rng.random(st.n), lab))] = np.arange(st.n)
        back = st.alive & (order[st.src] >= order[st.dst])
        st.alive[back] = False
    else:
        raise ValueError(kind)
    asm.info["return_structure"] = kind
    return asm


def apply_memory_regime(asm: Assembled, kind: str, seed: int, region: np.ndarray, local_labels: np.ndarray,
                        target: np.ndarray | None = None) -> Assembled:
    """Memory regime. ``region`` is the record region R; ``local_labels`` are fine clusters (for fragmentation);
    ``target`` is the region the delayed memory return feeds back into."""
    rng = np.random.default_rng(seed + 11)
    st = asm.state
    decay = {"near_zero": 0.3, "short": 0.7, "long": 0.99}
    if kind in decay:
        st.base_mem_decay[:] = st.mem_decay[:] = decay[kind]
    elif kind == "medium":
        pass
    elif kind == "external_persistent":
        asm.world_items.append({"kind": "memory_condition", "nodes": region, "decay": 0.995, "coupling": 0.3})
    elif kind == "fragmented":
        k = int(local_labels.max()) + 1
        per = np.where(rng.random(k) < 0.5, 0.3, 0.99)
        st.base_mem_decay[:] = st.mem_decay[:] = per[local_labels]
    elif kind == "delayed_return":
        # the record region keeps memory, but reaches the rest only through a 15-step relay path
        asm.world_items.append({"kind": "memory_condition", "nodes": region, "decay": 0.995, "coupling": 0.3})
        rest = np.setdiff1d(np.arange(st.n), region)
        _remove_between(st, region, rest)
        relay = rng.choice(np.setdiff1d(rest, target if target is not None else []), 15, replace=False)
        _add_chain(st, relay, region, target if target is not None else rest, rng)
        asm.sets["memory_relay"] = relay.astype(np.int32)
    else:
        raise ValueError(kind)
    asm.info["memory_regime"] = kind
    return asm


# ------------------------------------------------------------------------------------------------ disconnection
def disconnection_structure(kind: str, n: int, seed: int, params: Params | None = None) -> Assembled:
    """Structures in which disconnection should matter if it is operationally non-redundant: the connections that
    carry flow between parts are weak (base weight just above w_min), so they dissolve when they carry flow
    without penetrating."""
    rng = np.random.default_rng(seed)
    params = params or Params()
    weak = params.w_min * 1.6
    lab = _blocks(n, 8, rng)
    src, dst = _sbm(lab, 6.0 / 1.35, 1.0, rng)  # 8 closed modules
    src, dst = _reciprocate(src, dst, rng, 0.35)
    mods = [np.flatnonzero(lab == k) for k in range(8)]
    bridges: list[tuple[int, int]] = []

    def link(a: np.ndarray, b: np.ndarray, k: int = 1) -> None:
        for _ in range(k):
            bridges.append((int(rng.choice(a)), int(rng.choice(b))))

    if kind == "single_bridge":
        for i in range(1, 8):  # modules 1–7 joined richly; module 0 attached by one connection each way
            for j in range(1, 8):
                if i != j:
                    link(mods[i], mods[j], 3)
        link(mods[1], mods[0])
        link(mods[0], mods[1])
    elif kind == "bottleneck":
        for i in range(8):
            for j in range(8):
                if i != j and (i < 4) == (j < 4):
                    link(mods[i], mods[j], 3)
        link(mods[0], mods[4], 2)
        link(mods[4], mods[0], 2)
    elif kind == "sparse_tree":
        for i in range(1, 8):
            p = (i - 1) // 2
            link(mods[p], mods[i])
            link(mods[i], mods[p])
    elif kind == "fragile_loop":
        for i in range(8):
            link(mods[i], mods[(i + 1) % 8])
    elif kind == "one_way_path":
        for i in range(7):
            link(mods[i], mods[i + 1])
    elif kind == "delayed_return_route":
        for i in range(7):
            link(mods[i], mods[i + 1], 2)
        link(mods[7], mods[0])  # the only way back
    elif kind == "high_path_dependence":
        # two competing routes from module 0 to module 5; whichever strengthens first carries
        for a, b in ((0, 1), (1, 2), (2, 5), (0, 3), (3, 4), (4, 5), (5, 0)):
            link(mods[a], mods[b])
    elif kind == "isolated_regions_bridge":
        for i in range(4):
            for j in range(4):
                if i != j:
                    link(mods[i], mods[j], 2)
                    link(mods[i + 4], mods[j + 4], 2)
        link(mods[3], mods[4])  # the only bridge between two otherwise isolated regions
        link(mods[4], mods[3])
    else:
        raise ValueError(kind)
    bs = np.array([b[0] for b in bridges]) if bridges else np.zeros(0, int)
    bd = np.array([b[1] for b in bridges]) if bridges else np.zeros(0, int)
    st = assemble(n, np.concatenate([src, bs]), np.concatenate([dst, bd]), rng, params,
                  field_=_module_field(lab, rng))
    is_bridge = st.alive & (lab[st.src] != lab[st.dst])
    st.weight[is_bridge] = st.base_weight[is_bridge] = weak
    st.capacity[is_bridge] = 1.5
    sets = _module_sets(lab)
    return Assembled(st, sets, info={"family": kind, "bridge_connections": int(is_bridge.sum()),
                                     "bridge_base_weight": weak})


# ------------------------------------------------------------------------------------------------ regime calibration
TARGET_ACTIVITY = 0.04  # ignitions per configuration per step in the sustained regime


def activity(build, gain: float, steps: int = 500, seed: int = 1) -> float:
    """Mean ignitions per configuration per step (after a 150-step transient) of a freshly built world."""
    from ..runtime.engine import Engine
    asm = build(Params(gain=gain))
    e = Engine(asm.state, seed, checkpoint_every=0)
    n = asm.state.n
    tot = 0
    for t in range(steps):
        d = e.step()
        if t >= 150:
            tot += len(d.ignitions)
    return tot / ((steps - 150) * n)


def calibrate_gain(build, target: float = TARGET_ACTIVITY, lo: float = 1.2, hi: float = 9.0, iters: int = 9,
                   steps: int = 500) -> dict:
    """Bisection on the transmission gain for the lowest gain at which a topology sustains at least ``target``
    activity. Topologies with a discontinuous transition end above the target (reported); topologies that never
    reach it return the upper bound with ``reached=False``. ``build(params)`` must return an :class:`Assembled`."""
    a_lo, a_hi = activity(build, lo, steps), activity(build, hi, steps)
    if a_lo >= target:
        return {"gain": lo, "activity": round(a_lo, 5), "reached": True}
    if a_hi < target:
        return {"gain": hi, "activity": round(a_hi, 5), "reached": False}
    for _ in range(iters):
        mid = float(np.sqrt(lo * hi))
        a = activity(build, mid, steps)
        if a < target:
            lo = mid
        else:
            hi, a_hi = mid, a
    return {"gain": round(hi, 4), "activity": round(a_hi, 5), "reached": True}
