"""Perturbation registry: deterministic, severity-parameterised perturbations with explicit phases.

Every perturbation has a family, a subtype name, a ``side``:

* ``world`` — the runtime's dynamics or structure change;
* ``interface`` — the actuator mapping changes; the world changes only through actions;
* ``observation`` — the sensor readings change; the world is untouched.

Each also has a severity in [0, 1] (0 = no perturbation; severity 0 is the shared paired control) and hooks:

    onset(w, sev, ctx)              at step t_p
    per_step(w, sev, ctx)           every step of the perturbation phase (optional)
    per_decision(w, sev, ctx, t)    at every decision of the perturbation phase (optional)
    revert(w, sev, ctx)             at step t_r (optional; permanent perturbations leave a reconfigured world)

``ctx`` carries the perturbation's own seeded RNG (seeded from subtype and engine seed), calibration statistics
and whatever the onset saved. ``footprint`` lists the nodes the perturbation touches directly; it is the ground
truth for localisation, and is empty for observation-side perturbations.

Aliases (``ALIASES``) name the same operation under a second family. They are run once and reported under both
names, never counted twice.
"""
from __future__ import annotations

import zlib
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from xzr.runtime.intervention import Connect, Gate, MemoryCondition, Mutation, Sever  # noqa: E402

from .world import ACTIONS, BenchWorld


@dataclass(frozen=True)
class Perturbation:
    family: str
    name: str
    side: str
    onset: Callable
    revert: Callable | None = None
    per_step: Callable | None = None
    per_decision: Callable | None = None
    permanent: bool = False
    note: str = ""

    @property
    def key(self) -> str:
        return f"{self.family}.{self.name}"


def ctx_for(key: str, seed: int, calib: dict) -> dict:
    return {"rng": np.random.default_rng(zlib.crc32(key.encode()) * 1000003 + seed), "calib": calib, "footprint": []}


# ------------------------------------------------------------------------------------------------ helpers
def _edges(st, src_in: np.ndarray | None = None, dst_in: np.ndarray | None = None, cross: bool = False):
    m = st.alive.copy()
    if src_in is not None:
        m &= np.isin(st.src, src_in)
    if dst_in is not None:
        m &= np.isin(st.dst, dst_in)
    return np.flatnonzero(m)


def _incident(st, nodes):
    return np.flatnonzero(st.alive & (np.isin(st.src, nodes) | np.isin(st.dst, nodes)))


def _pick(rng, arr, frac):
    k = int(round(frac * len(arr)))
    return np.sort(rng.choice(arr, k, replace=False)) if k else np.zeros(0, arr.dtype if len(arr) else np.int64)


def _sever(w: BenchWorld, edges, ctx, save=False):
    st = w.state
    edges = np.asarray(edges, np.int64)
    if save:
        ctx.setdefault("severed", []).extend(zip(st.src[edges].tolist(), st.dst[edges].tolist(),
                                                 st.weight[edges].tolist(), strict=True))
    if len(edges):
        w.engine.apply([Sever(tuple(int(e) for e in edges))])
    ctx["footprint"] = np.unique(np.concatenate([ctx["footprint"], st.src[edges], st.dst[edges]])).astype(int).tolist()


def _make_room(w: BenchWorld, k: int, ctx) -> None:
    """The runtime's connection pool is fixed-capacity and saturated in the steady state (t ≳ 1000). An addition
    then needs free slots: the k weakest connections with both ends outside T ∪ N are severed first (relocation).
    Their configurations are part of the perturbation's footprint; the count is recorded."""
    st = w.state
    free = int((~st.alive).sum())
    if free >= k:
        return
    far = np.ones(st.n, bool)
    far[w.T] = far[w.N] = False
    cand = np.flatnonzero(st.alive & far[st.src] & far[st.dst])
    weakest = cand[np.argsort(st.weight[cand], kind="stable")[: k - free]]
    ctx["relocated"] = ctx.get("relocated", 0) + len(weakest)
    _sever(w, weakest, ctx)


def _connect(w: BenchWorld, pairs, ctx, weight=0.4, save=False):
    acts = [Connect(int(a), int(b), float(weight if wt is None else wt)) for a, b, wt in pairs]
    if acts:
        _make_room(w, len(acts), ctx)
        before = w.state.alive.copy()
        w.engine.apply(acts)
        new = np.flatnonzero(w.state.alive & ~before)
        if save:
            ctx.setdefault("added", []).extend(new.tolist())
        nodes = np.array([p[0] for p in pairs] + [p[1] for p in pairs])
        ctx["footprint"] = np.unique(np.concatenate([ctx["footprint"], nodes])).astype(int).tolist()
        ctx["connect_failed"] = ctx.get("connect_failed", 0) + len(acts) - len(new)


def _add_base(w: BenchWorld, item, ctx):
    eng = w.engine
    eng.base_overlay = [*eng.base_overlay, item]
    ctx.setdefault("base_items", []).append(item)
    eng.set_overlay(list(eng.overlay))


def _remove_base(w: BenchWorld, ctx):
    eng = w.engine
    ids = {id(i) for i in ctx.get("base_items", [])}
    eng.base_overlay = [i for i in eng.base_overlay if id(i) not in ids]
    eng.set_overlay(list(eng.overlay))


def _fp(ctx, nodes):
    ctx["footprint"] = np.unique(np.concatenate([ctx["footprint"], np.asarray(nodes)])).astype(int).tolist()


def drift_period(sev: float) -> int:
    """Change period for drift perturbations: 300 steps at severity 0 → 10 steps (one decision) at severity 1."""
    return max(1, int(round(300 * (10 / 300) ** sev)))


# ------------------------------------------------------------------------------------------------ boundary (actuator)
def _set_act(attr, value_fn):
    def on(w, sev, ctx):
        ctx["saved_" + attr] = getattr(w.actuator, attr)
        setattr(w.actuator, attr, value_fn(w, sev, ctx))

    def rev(w, sev, ctx):
        setattr(w.actuator, attr, ctx["saved_" + attr])
        if attr == "delay":
            w.actuator._queue = w.actuator._queue[-1:]
    return on, rev


def _reassign_U(w, sev, ctx):
    T, N = w.T, w.N
    k = int(round(sev * len(T)))
    out = ctx["rng"].choice(len(T), k, replace=False)
    U = np.delete(T, out)
    return np.sort(np.concatenate([U, ctx["rng"].choice(N, min(k, len(N)), replace=False)])).astype(np.int32)


def _fragment_U(w, sev, ctx):
    keep = max(1, int(round((1 - 0.9 * sev) * len(w.T))))
    return np.sort(ctx["rng"].choice(w.T, keep, replace=False)).astype(np.int32)


def _merge_U(w, sev, ctx):
    return np.sort(np.concatenate([w.T, _pick(ctx["rng"], w.N, sev)])).astype(np.int32)


def _leak_on(w, sev, ctx):
    ctx["saved_leak"] = (w.actuator.leak_nodes, w.actuator.leak)
    w.actuator.leak_nodes, w.actuator.leak = w.N.copy(), float(sev)


def _leak_rev(w, sev, ctx):
    w.actuator.leak_nodes, w.actuator.leak = ctx["saved_leak"]


# ------------------------------------------------------------------------------------------------ topology
def _edge_deletion(w, sev, ctx):
    _sever(w, _pick(ctx["rng"], _incident(w.state, w.T), 0.7 * sev), ctx)
    _fp(ctx, w.T)


def _edge_addition(w, sev, ctx):
    r = ctx["rng"]
    k = int(round(300 * sev))
    a, b = r.choice(w.T, k), r.choice(w.outside, k)
    flip = r.random(k) < 0.5
    pairs = [(y, x, None) if f else (x, y, None) for x, y, f in zip(a, b, flip, strict=True)]
    _connect(w, pairs, ctx)
    _fp(ctx, w.T)


def _cluster_split(w, sev, ctx):
    h0, h1 = w.halves
    st = w.state
    e = np.flatnonzero(st.alive & ((np.isin(st.src, h0) & np.isin(st.dst, h1)) | (np.isin(st.src, h1) & np.isin(st.dst, h0))))
    _sever(w, _pick(ctx["rng"], e, sev), ctx)
    _fp(ctx, w.T)


def _cluster_merge(w, sev, ctx):
    r = ctx["rng"]
    k = int(round(400 * sev))
    a, b = r.choice(w.T, k), r.choice(w.N, k)
    pairs = [(x, y, None) if i % 2 else (y, x, None) for i, (x, y) in enumerate(zip(a, b, strict=True))]
    _connect(w, pairs, ctx)
    _fp(ctx, np.concatenate([w.T, w.N]))


def _hub_removal(w, sev, ctx):
    st = w.state
    k = int(np.ceil(10 * sev))
    deg = np.bincount(st.src[st.alive], minlength=st.n) + np.bincount(st.dst[st.alive], minlength=st.n)
    hubs = w.T[np.argsort(-deg[w.T], kind="stable")[:k]]
    ctx["hubs"] = hubs.tolist()
    _sever(w, _incident(st, hubs), ctx)


def _rerouting(w, sev, ctx):
    st, r = w.state, ctx["rng"]
    e = _pick(r, np.flatnonzero(st.alive & np.isin(st.dst, w.T) & ~np.isin(st.src, w.T)), 0.6 * sev)
    srcs, wts = st.src[e].copy(), st.weight[e].copy()
    _sever(w, e, ctx)
    _connect(w, [(s, int(r.choice(w.outside)), float(x)) for s, x in zip(srcs, wts, strict=True)], ctx)
    _fp(ctx, w.T)


def _mutation_on(w, sev, ctx):
    _add_base(w, Mutation(tuple(int(i) for i in w.T), 0.02 * sev), ctx)
    _fp(ctx, w.T)


# ------------------------------------------------------------------------------------------------ sensors / variables
def _sens(attr, fn):
    def on(w, sev, ctx):
        ctx["saved_" + attr] = getattr(w.sensors, attr)
        setattr(w.sensors, attr, fn(w, sev, ctx))

    def rev(w, sev, ctx):
        setattr(w.sensors, attr, ctx["saved_" + attr])
        if attr == "delay":
            w.sensors._queue = w.sensors._queue[-1:]
    return on, rev


def _frac_mask(w, sev, ctx, keep_one=False):
    k = len(w.sensors.channels)
    m = int(round(sev * (k - 1 if keep_one else k)))
    mask = np.zeros(k, bool)
    mask[ctx["rng"].choice(k, m, replace=False)] = True
    return mask


def _reassign_on(w, sev, ctx):
    s = w.sensors
    ctx["saved_channels"] = [c.copy() for c in s.channels]
    for i in np.flatnonzero(_frac_mask(w, sev, ctx)):
        s.channels[i] = np.sort(ctx["rng"].choice(w.N, len(s.channels[i]), replace=False))


def _reassign_rev(w, sev, ctx):
    w.sensors.channels = ctx["saved_channels"]


def _dup(w, sev, ctx):
    d = np.arange(len(w.sensors.channels))
    m = _frac_mask(w, sev, ctx, keep_one=True)
    m[0] = False
    d[m] = 0
    return d


def _deletion_dec(w, sev, ctx, t):
    w.sensors.active = np.zeros(len(w.sensors.channels), bool) if ctx["rng"].random() < sev else ctx["saved_active"]


def _deletion_on(w, sev, ctx):
    ctx["saved_active"] = w.sensors.active.copy()


def _deletion_rev(w, sev, ctx):
    w.sensors.active = ctx["saved_active"]


# ------------------------------------------------------------------------------------------------ memory
def _mem_sel(w, sev, ctx):
    if "mem_sel" not in ctx:
        ctx["mem_sel"] = _pick(ctx["rng"], w.T, sev)
        _fp(ctx, ctx["mem_sel"])
    return ctx["mem_sel"]


def _mem_delete_step(w, sev, ctx):
    w.state.memory[_mem_sel(w, sev, ctx)] = 0.0


def _mem_truncate_step(w, sev, ctx):
    sel = w.T
    if "cap" not in ctx:
        ctx["cap"] = float(np.quantile(w.state.memory[sel], 0.95)) * (1 - sev) if len(sel) else 0.0
        _fp(ctx, sel)
    w.state.memory[sel] = np.minimum(w.state.memory[sel], ctx["cap"])


def _mem_access_on(w, sev, ctx):
    st = w.state
    sel = w.T
    # MemoryCondition sets one coupling value for the node set; scale the mean |coupling| by (1 − sev), keeping signs
    # node by node is not representable through the overlay, so coupling is set per sign group
    for sign in (-1.0, 1.0):
        nodes = sel[np.sign(st.base_mem_coupling[sel]) == sign]
        if len(nodes):
            _add_base(w, MemoryCondition(tuple(int(i) for i in nodes), None,
                                         float(np.mean(st.base_mem_coupling[nodes]) * (1 - sev))), ctx)
    _fp(ctx, sel)


def _hist_remove(w, sev, ctx):
    sel = _mem_sel(w, sev, ctx)
    ctx["saved_memory"] = w.state.memory[sel].copy()
    w.state.memory[sel] = 0.0


def _hist_reactivate(w, sev, ctx):
    # experiments/history.py semantics: the saved record is added back on top of what regrew since removal
    w.state.memory[ctx["mem_sel"]] += ctx["saved_memory"]


def _migrate(w, sev, ctx):
    sel = _mem_sel(w, sev, ctx)
    dest = np.sort(ctx["rng"].choice(w.N, min(len(sel), len(w.N)), replace=False))
    ctx["dest"] = dest.tolist()
    w.state.memory[dest] += w.state.memory[sel][: len(dest)]
    w.state.memory[sel] = 0.0
    _fp(ctx, dest)


# ------------------------------------------------------------------------------------------------ coupling
def _gain(f_of_sev):
    def on(w, sev, ctx):
        ctx["saved_gain"] = w.state.params.gain
        w.state.params.gain = ctx["saved_gain"] * f_of_sev(sev)
        _fp(ctx, np.arange(w.state.n))

    def rev(w, sev, ctx):
        w.state.params.gain = ctx["saved_gain"]
    return on, rev


def _asym_on(w, sev, ctx):
    st = w.state
    e = np.flatnonzero(st.alive & np.isin(st.src, w.T) & ~np.isin(st.dst, w.T))
    _add_base(w, Gate(tuple(int(i) for i in e), 1 - 0.95 * sev), ctx)
    _fp(ctx, w.T)


def _decouple_on(w, sev, ctx):
    st = w.state
    e = np.flatnonzero(st.alive & np.isin(st.dst, w.T) & ~np.isin(st.src, w.T))
    _add_base(w, Gate(tuple(int(i) for i in e), 1 - 0.95 * sev), ctx)
    _fp(ctx, w.T)


def _far_module(w):
    st = w.state
    m = st.alive
    inT = np.isin(st.src[m], w.T) ^ np.isin(st.dst[m], w.T)
    other = np.where(np.isin(st.src[m], w.T), st.dst[m], st.src[m])[inT]
    cnt = np.bincount(w.module_of[other], minlength=len(w.modules)).astype(float)
    cnt[w.cfg.target_module] = np.inf
    return w.modules[int(np.argmin(cnt))]


def _cross_on(w, sev, ctx):
    r = ctx["rng"]
    far = _far_module(w)
    k = int(round(300 * sev))
    a, b = r.choice(w.T, k), r.choice(far, k)
    _connect(w, [(x, y, None) if i % 2 else (y, x, None) for i, (x, y) in enumerate(zip(a, b, strict=True))], ctx,
             save=True)


def _cross_rev(w, sev, ctx):
    added = [e for e in ctx.get("added", []) if w.state.alive[e]]
    if added:
        w.engine.apply([Sever(tuple(int(e) for e in added))])


def _reversal(w, sev, ctx):
    st, r = w.state, ctx["rng"]
    e = _pick(r, np.flatnonzero(st.alive & np.isin(st.dst, w.T) & ~np.isin(st.src, w.T)), sev)
    trip = list(zip(st.dst[e].tolist(), st.src[e].tolist(), st.weight[e].tolist(), strict=True))
    _sever(w, e, ctx)
    _connect(w, trip, ctx)


# ------------------------------------------------------------------------------------------------ temporal
def _dt_on(f_of_sev):
    def on(w, sev, ctx):
        ctx["saved_dt"] = (w.dt, w.sensors.window)
        w.dt = int(max(2, min(30, round(w.cfg.dt * f_of_sev(sev)))))
        w.sensors.window = w.dt

    def rev(w, sev, ctx):
        w.dt, w.sensors.window = ctx["saved_dt"]
    return on, rev


PERMS = (np.array([0, 2, 1, 3, 4]), np.array([0, 1, 2, 4, 3]), np.array([0, 2, 1, 4, 3]), np.arange(len(ACTIONS)))


def _iface_drift_on(w, sev, ctx):
    ctx["period"] = drift_period(sev)
    ctx["next"] = w.t
    ctx["k"] = 0


def _iface_drift_step(w, sev, ctx):
    if w.t >= ctx["next"]:
        w.actuator.perm = PERMS[ctx["k"] % len(PERMS)].copy()
        ctx["k"] += 1
        ctx["next"] = w.t + ctx["period"]
        ctx.setdefault("changes", []).append(w.t)


def _iface_drift_rev(w, sev, ctx):
    w.actuator.perm = np.arange(len(ACTIONS))


def _world_drift_on(w, sev, ctx):
    st = w.state
    ctx["edges"] = tuple(int(i) for i in np.flatnonzero(
        st.alive & ((np.isin(st.src, w.N) & np.isin(st.dst, w.T)) | (np.isin(st.src, w.T) & np.isin(st.dst, w.N)))))
    ctx["period"] = drift_period(sev)
    ctx["next"] = w.t
    ctx["closed"] = False
    _fp(ctx, np.concatenate([w.T, w.N]))


def _world_drift_step(w, sev, ctx):
    if w.t >= ctx["next"]:
        _remove_base(w, ctx)
        ctx["base_items"] = []
        ctx["closed"] = not ctx["closed"]
        if ctx["closed"]:
            _add_base(w, Gate(ctx["edges"], 0.05), ctx)
        ctx["next"] = w.t + ctx["period"]
        ctx.setdefault("changes", []).append(w.t)


# ------------------------------------------------------------------------------------------------ structural
def _cut_on(w, sev, ctx):
    st = w.state
    e = np.flatnonzero(st.alive & np.isin(st.dst, w.T) & ~np.isin(st.src, w.T))
    _sever(w, _pick(ctx["rng"], e, sev), ctx, save=True)


def _reconnect(w, sev, ctx):
    _connect(w, [(a, b, x) for a, b, x in ctx.get("severed", [])], ctx)


def _disconnect(w, sev, ctx):
    st = w.state
    e = np.flatnonzero(st.alive & (np.isin(st.src, w.T) ^ np.isin(st.dst, w.T)))
    _sever(w, _pick(ctx["rng"], e, sev), ctx)
    _fp(ctx, w.T)


def _reorganize(w, sev, ctx):
    st, r = w.state, ctx["rng"]
    e = np.flatnonzero(st.alive & (w.module_of[st.src] != w.module_of[st.dst]))
    e = _pick(r, e, 0.5 * sev)
    srcs, wts = st.src[e].copy(), st.weight[e].copy()
    _sever(w, e, ctx)
    _connect(w, [(s, int(r.integers(st.n)), float(x)) for s, x in zip(srcs, wts, strict=True)], ctx)


# ------------------------------------------------------------------------------------------------ registry
def _build() -> dict[str, Perturbation]:
    P = Perturbation
    on_noise, rev_noise = _set_act("node_noise", lambda w, s, c: 0.5 * s)
    on_delay, rev_delay = _set_act("delay", lambda w, s, c: int(round(1 + 4 * s)))
    on_reass, rev_reass = _set_act("U", _reassign_U)
    on_frag, rev_frag = _set_act("U", _fragment_U)
    on_mergeU, rev_mergeU = _set_act("U", _merge_U)
    on_drop, rev_drop = _set_act("drop_p", lambda w, s, c: float(s))
    s_drop = _sens("dropout", lambda w, s, c: _frac_mask(w, s, c))
    s_perm = _sens("perm", lambda w, s, c: c["rng"].permutation(len(w.sensors.channels)) if s > 0 else np.arange(len(w.sensors.channels)))
    s_delay = _sens("delay", lambda w, s, c: int(round(1 + 5 * s)))
    s_noise = _sens("noise", lambda w, s, c: 2.0 * s * c["calib"]["reading_sd"])
    s_part = _sens("active", lambda w, s, c: ~_frac_mask(w, s, c, keep_one=True))
    s_scale = _sens("scale", lambda w, s, c: 1.0 + 2.0 * s)
    s_win = _sens("window", lambda w, s, c: max(1, int(round(w.cfg.dt * (1 - 0.9 * s)))))
    v_remap = _sens("offset", lambda w, s, c: s * c["calib"]["reading_range"])
    v_dup = _sens("duplicate_of", _dup)
    v_fold = _sens("fold", lambda w, s, c: float(np.quantile(c["calib"]["readings"], 0.5 * s)))
    v_coarse = _sens("coarsen", lambda w, s, c: 1.5 * s * c["calib"]["reading_iqr"])
    s_async = _sens("async_p", lambda w, s, c: float(s))
    g_weak = _gain(lambda s: 1 - 0.25 * s)
    g_strong = _gain(lambda s: 1 + 0.25 * s)
    t_comp = _dt_on(lambda s: 1 - 0.7 * s)
    t_exp = _dt_on(lambda s: 1 + 2.0 * s)
    items = [
        P("boundary", "noise", "interface", on_noise, rev_noise),
        P("boundary", "leakage", "interface", _leak_on, _leak_rev),
        P("boundary", "delayed_update", "interface", on_delay, rev_delay),
        P("boundary", "reassignment", "interface", on_reass, rev_reass),
        P("boundary", "fragmentation", "interface", on_frag, rev_frag),
        P("boundary", "merge", "interface", on_mergeU, rev_mergeU),
        P("boundary", "disappearance", "interface", on_drop, rev_drop),
        P("topology", "edge_deletion", "world", _edge_deletion, permanent=True),
        P("topology", "edge_addition", "world", _edge_addition, permanent=True),
        P("topology", "cluster_split", "world", _cluster_split, permanent=True),
        P("topology", "cluster_merge", "world", _cluster_merge, permanent=True),
        P("topology", "hub_removal", "world", _hub_removal, permanent=True),
        P("topology", "rerouting", "world", _rerouting, permanent=True),
        P("topology", "dynamic_mutation", "world", _mutation_on, lambda w, s, c: _remove_base(w, c)),
        P("sensor", "dropout", "observation", *s_drop),
        P("sensor", "reassignment", "observation", _reassign_on, _reassign_rev),
        P("sensor", "permutation", "observation", *s_perm),
        P("sensor", "delay", "observation", *s_delay),
        P("sensor", "noise", "observation", *s_noise),
        P("sensor", "partial_observability", "observation", *s_part),
        P("sensor", "scale_mismatch", "observation", *s_scale),
        P("sensor", "window_mismatch", "observation", *s_win),
        P("variable", "remap", "observation", *v_remap),
        P("variable", "deletion", "observation", _deletion_on, _deletion_rev, per_decision=_deletion_dec),
        P("variable", "duplication", "observation", *v_dup),
        P("variable", "relabel", "observation", *v_fold, note="non-monotone outcome map x → |x − c|"),
        P("variable", "outcome_merge", "observation", *v_coarse, note="coarsened readings merge outcome levels"),
        P("memory", "deletion", "world", lambda w, s, c: _mem_sel(w, s, c), per_step=_mem_delete_step),
        P("memory", "truncation", "world", lambda w, s, c: None, per_step=_mem_truncate_step),
        P("memory", "access_block", "world", _mem_access_on, lambda w, s, c: _remove_base(w, c),
          note="delayed memory availability: memory coupling of T scaled by (1 − severity) during the phase"),
        P("memory", "history_removal", "world", _hist_remove, permanent=True),
        P("memory", "history_reactivation", "world", _hist_remove, _hist_reactivate),
        P("memory", "migration", "world", _migrate, permanent=True),
        P("coupling", "weakening", "world", *g_weak),
        P("coupling", "strengthening", "world", *g_strong),
        P("coupling", "asymmetric", "world", _asym_on, lambda w, s, c: _remove_base(w, c)),
        P("coupling", "cross_cluster", "world", _cross_on, _cross_rev),
        P("coupling", "reversal", "world", _reversal, permanent=True),
        P("coupling", "temporary_decoupling", "world", _decouple_on, lambda w, s, c: _remove_base(w, c)),
        P("temporal", "horizon_compression", "interface", *t_comp),
        P("temporal", "horizon_expansion", "interface", *t_exp),
        P("temporal", "asynchronous", "observation", *s_async),
        P("temporal", "interface_drift", "interface", _iface_drift_on, _iface_drift_rev, per_step=_iface_drift_step,
          note="action→actuation permutation changes every drift_period(severity) steps"),
        P("temporal", "world_drift", "world", _world_drift_on, lambda w, s, c: _remove_base(w, c),
          per_step=_world_drift_step, note="T↔N connections close/open every drift_period(severity) steps"),
        P("structural", "cut_reconnect", "world", _cut_on, _reconnect),
        P("structural", "disconnection", "world", _disconnect, permanent=True),
        P("structural", "multi_cluster_reorganization", "world", _reorganize, permanent=True),
    ]
    return {p.key: p for p in items}


REGISTRY: dict[str, Perturbation] = _build()
ALIASES: dict[str, str] = {
    "variable.latent_split": "topology.cluster_split",
    "variable.latent_merge": "topology.cluster_merge",
    "variable.feature_remap": "sensor.scale_mismatch",
    "temporal.delayed_feedback": "sensor.delay",
    "temporal.adaptation_delay": "boundary.delayed_update",
    "structural.reconfiguration": "topology.rerouting",
    "structural.expansion": "topology.cluster_merge",
    "structural.configuration_crossing_recurrence": "memory.migration",
    "memory.memory_migration": "memory.migration",
}
NOT_IMPLEMENTED = {
    "structural.compression": "fixed-N engine: no operation removes configurations while keeping the run comparable",
    "memory.history_fork": "Engine.fork is an exact continuation (bit-identical, tested), so it is not a perturbation",
    "sensor.temporal_window_mismatch": "covered by sensor.window_mismatch",
}
