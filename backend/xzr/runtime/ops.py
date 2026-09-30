"""The operational primitives: ignite, propagate, penetrate, transform, retain, decay, return,
cut, connect, disconnect, reconfigure.

Each function reads/writes a :class:`State` in place and returns the events it produced.
They are vectorized over all configurations; the only per-item loops are the rate-limited structural
operations (connect, reconfigure), which touch at most a handful of items per step.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .delta import EMPTY_I, I32
from .state import NO_INDEX, State


@dataclass
class Ignition:
    fired: np.ndarray  # indices
    mask: np.ndarray  # bool (N)
    penetrations: np.ndarray  # (k, 3) edge, origin, depth
    returns: np.ndarray
    memory_dependent: int
    receivers: np.ndarray = field(default_factory=lambda: EMPTY_I)  # receiver of each penetration (row-aligned)


@dataclass
class Flow:
    emitted: np.ndarray  # (N)
    incoming: np.ndarray  # (N)
    edges: np.ndarray  # carrying connection ids
    flow: np.ndarray  # flow per carrying connection
    receivers: np.ndarray
    dominant_edge: np.ndarray
    dominant_flow: np.ndarray


def inject(state: State, rng: np.random.Generator) -> None:
    """External difference entering at seeded random configurations (explicit stochasticity)."""
    p = state.params
    k = int(rng.binomial(state.n, p.input_rate)) if p.input_rate > 0 else 0
    if k:
        idx = rng.integers(0, state.n, k)
        np.add.at(state.diff, idx, rng.exponential(p.input_amp, k))


def ignite(state: State, threshold: bool = True, wave: bool = True, return_events: bool = True) -> Ignition:
    """A configuration ignites when its difference reaches its effective threshold.

    Also resolves *penetration* (the ignition was caused by an incoming connection: the wave continues
    with depth + 1) and *return* (the wave that caused the ignition originated at this very configuration).

    Variants (reduction experiments): ``threshold=False`` — every configuration holding difference emits
    (continuous transition, no refractory period); ``wave=False`` — only the dominant incoming connection is
    reported, origin/depth are not tracked (-1 / 0) and no returns are detected.
    """
    p = state.params
    base = state.theta * state.theta_mod
    if threshold:
        mask = (state.diff >= state.theta_eff()) & (state.refractory == 0) & ~state.frozen
    else:
        mask = (state.diff > 0) & ~state.frozen
    fired = np.flatnonzero(mask).astype(I32)
    mem_dep = int(np.count_nonzero(state.diff[fired] < base[fired]))
    ce = state.cause_edge[fired]
    has = ce >= 0
    if wave:
        origin = state.pending_origin[fired]
        depth = state.pending_depth[fired]
        pen = np.stack([ce[has], origin[has], depth[has]], axis=1).astype(I32) if has.any() else np.zeros((0, 3), I32)
        returns = fired[has & (origin == fired)] if return_events else EMPTY_I
        state.wave_origin[fired] = np.where(has, origin, fired)
        state.wave_depth[fired] = np.where(has, depth, 0)
    else:
        k = int(has.sum())
        pen = np.stack([ce[has], np.full(k, NO_INDEX), np.zeros(k)], axis=1).astype(I32) if k else np.zeros((0, 3), I32)
        returns = EMPTY_I
    if threshold:
        state.refractory[fired] = p.refractory_steps + 1
    state.last_ignite[fired] = state.t
    state.ignite_count[fired] += 1
    return Ignition(fired, mask, pen, returns, mem_dep, fired[has])


def propagate(state: State, ign: Ignition, wave: bool = True, enabled: bool = True) -> Flow:
    """Ignited configurations emit part of their difference along their reachable transitions.

    Each receiver records its dominant incoming connection (its cause edge): if it ignites next step,
    that hop is a penetration carrying the wave onward.
    """
    p, n = state.params, state.n
    state.load *= p.load_decay
    state.cause_edge[:] = NO_INDEX
    e = np.flatnonzero(state.reachable_mask() & ign.mask[state.src]).astype(I32) if enabled else EMPTY_I
    emitted = np.zeros(n)
    if len(e) == 0:
        z = np.zeros(0)
        return Flow(emitted, np.zeros(n), EMPTY_I, z, EMPTY_I, EMPTY_I, z)
    s, d = state.src[e], state.dst[e]
    wg = state.weight[e] * state.gate[e]
    conduct = 1.0 / (1.0 + p.fatigue * state.load[e] / state.capacity[e])
    out_sum = np.bincount(s, wg, minlength=n)
    f = ign.fired
    emitted[f] = np.where(out_sum[f] > 0, state.diff[f] * p.emit_frac, 0.0)
    flow = p.gain * emitted[s] * wg / out_sum[s] * conduct
    incoming = np.bincount(d, flow, minlength=n)
    order = np.lexsort((flow, d))
    ds = d[order]
    last = np.r_[ds[1:] != ds[:-1], True]
    dom_e, dom_f, recv = e[order][last], flow[order][last], ds[last]
    state.cause_edge[recv] = dom_e
    if wave:
        src_dom = state.src[dom_e]
        state.pending_origin[recv] = state.wave_origin[src_dom]
        state.pending_depth[recv] = state.wave_depth[src_dom] + 1
    state.load[e] += flow
    return Flow(emitted, incoming, e, flow, recv, dom_e, dom_f)


def thresholded_transition(state: State, wave: bool = True, return_events: bool = True) -> tuple[Ignition, Flow]:
    """Reduction candidate: ignition is not a separate operation but the gate of a transition.

    One pass computes which configurations pass the threshold, what they emit along which reachable
    connections, and which incoming connection dominates each receiver. Arithmetic order is identical to
    ``ignite`` followed by ``propagate``.
    """
    p, n = state.params, state.n
    # gate
    base = state.theta * state.theta_mod
    gate_open = (state.diff >= state.theta_eff()) & (state.refractory == 0) & ~state.frozen
    fired = np.flatnonzero(gate_open).astype(I32)
    mem_dep = int(np.count_nonzero(state.diff[fired] < base[fired]))
    ce = state.cause_edge[fired]
    has = ce >= 0
    if wave:
        origin = state.pending_origin[fired]
        depth = state.pending_depth[fired]
        pen = np.stack([ce[has], origin[has], depth[has]], axis=1).astype(I32) if has.any() else np.zeros((0, 3), I32)
        returns = fired[has & (origin == fired)] if return_events else EMPTY_I
        state.wave_origin[fired] = np.where(has, origin, fired)
        state.wave_depth[fired] = np.where(has, depth, 0)
    else:
        k = int(has.sum())
        pen = np.stack([ce[has], np.full(k, NO_INDEX), np.zeros(k)], axis=1).astype(I32) if k else np.zeros((0, 3), I32)
        returns = EMPTY_I
    state.refractory[fired] = p.refractory_steps + 1
    state.last_ignite[fired] = state.t
    state.ignite_count[fired] += 1
    ign = Ignition(fired, gate_open, pen, returns, mem_dep, fired[has])
    # transition along reachable connections from open gates
    state.load *= p.load_decay
    state.cause_edge[:] = NO_INDEX
    e = np.flatnonzero(state.reachable_mask() & gate_open[state.src]).astype(I32)
    emitted = np.zeros(n)
    if len(e) == 0:
        z = np.zeros(0)
        return ign, Flow(emitted, np.zeros(n), EMPTY_I, z, EMPTY_I, EMPTY_I, z)
    s, d = state.src[e], state.dst[e]
    wg = state.weight[e] * state.gate[e]
    conduct = 1.0 / (1.0 + p.fatigue * state.load[e] / state.capacity[e])
    out_sum = np.bincount(s, wg, minlength=n)
    emitted[fired] = np.where(out_sum[fired] > 0, state.diff[fired] * p.emit_frac, 0.0)
    flow = p.gain * emitted[s] * wg / out_sum[s] * conduct
    incoming = np.bincount(d, flow, minlength=n)
    order = np.lexsort((flow, d))
    ds = d[order]
    last = np.r_[ds[1:] != ds[:-1], True]
    dom_e, dom_f, recv = e[order][last], flow[order][last], ds[last]
    state.cause_edge[recv] = dom_e
    if wave:
        src_dom = state.src[dom_e]
        state.pending_origin[recv] = state.wave_origin[src_dom]
        state.pending_depth[recv] = state.wave_depth[src_dom] + 1
    state.load[e] += flow
    return ign, Flow(emitted, incoming, e, flow, recv, dom_e, dom_f)


def transform(state: State, fl: Flow) -> np.ndarray:
    """A dominant flow through a form-rewriting connection changes what the receiving difference is like."""
    if len(fl.receivers) == 0:
        return np.zeros((0, 2), I32)
    p = state.params
    code = state.transform[fl.dominant_edge].astype(np.int32)
    m = (code != 0) & (fl.dominant_flow >= p.transform_min_share * fl.incoming[fl.receivers])
    nodes = fl.receivers[m]
    new = (state.form[state.src[fl.dominant_edge[m]]].astype(np.int32) + code[m]) % p.n_forms
    ch = new != state.form[nodes]
    nodes, new = nodes[ch], new[ch]
    state.form[nodes] = new.astype(np.int8)
    return np.stack([nodes, new], axis=1).astype(I32) if len(nodes) else np.zeros((0, 2), I32)


def retain_and_decay(state: State, fl: Flow, retention: bool = True) -> np.ndarray:
    """Retention keeps part of each difference; incoming flow adds; saturation is a local constraint.

    Returns configurations whose difference vanished (decay events).
    """
    p = state.params
    prev = state.diff
    keep = state.retention.copy() if retention else np.zeros(state.n)
    keep[fl.emitted > 0] *= p.discharge  # ignition consumes most of the difference it expresses
    new = (prev - fl.emitted) * keep + fl.incoming
    sat = new > state.cap
    np.minimum(new, state.cap, out=new)
    state.overload[:] = np.where(sat, state.overload + 1, 0)
    decays = np.flatnonzero((prev >= p.decay_eps) & (new < p.decay_eps)).astype(I32)
    state.diff = new
    np.maximum(state.refractory - 1, 0, out=state.refractory)
    return decays


def remember(state: State, ign: Ignition) -> None:
    state.memory *= state.mem_decay
    state.memory[ign.fired] += 1.0


def adapt_weights(state: State, penetrating_edges: np.ndarray, carried_prev: np.ndarray) -> None:
    """Connections that penetrated strengthen; those that carried flow without penetration weaken."""
    p = state.params
    w = state.weight
    if len(carried_prev):
        failed = np.setdiff1d(carried_prev, penetrating_edges, assume_unique=False)
        w[failed] -= p.weaken * w[failed]
    if len(penetrating_edges):
        pe = np.unique(penetrating_edges)
        w[pe] += p.strengthen * (p.w_max - w[pe])
    alive = state.alive
    w[alive] += p.relax * (state.base_weight[alive] - w[alive])


def successful_carriers(state: State, carried_prev: np.ndarray, fired_mask: np.ndarray) -> np.ndarray:
    """Variant input for adaptation: every connection that carried flow last step into a configuration that
    ignited now (multi-hop propagation without selecting a dominant connection)."""
    if len(carried_prev) == 0:
        return EMPTY_I
    live = carried_prev[state.alive[carried_prev]]
    return live[fired_mask[state.dst[live]]].astype(I32)


def cut(state: State) -> np.ndarray:
    """Overloaded connections break."""
    c = np.flatnonzero(state.alive & (state.load > state.capacity)).astype(I32)
    state.alive[c] = False
    state.load[c] = 0.0
    return c


def disconnect(state: State) -> np.ndarray:
    """Connections whose weight dissolved below w_min are removed."""
    r = np.flatnonzero(state.alive & (state.weight < state.params.w_min)).astype(I32)
    state.alive[r] = False
    return r


def sever(state: State, edges: np.ndarray) -> np.ndarray:
    """Cut specific connections (intervention form of cut)."""
    edges = np.asarray(edges, dtype=I32)
    c = edges[state.alive[edges]]
    state.alive[c] = False
    state.load[c] = 0.0
    return c


def _out_edges(state: State, a: int) -> np.ndarray:
    return np.flatnonzero(state.alive & (state.src == a))


def add_connection(state: State, a: int, b: int, w: float, transform_code: int = 0,
                   exclude: np.ndarray | None = None) -> int:
    """Place a new connection a→b in a free slot. Returns its id, or -1 if the pool is full or it exists."""
    if a == b:
        return -1
    out = _out_edges(state, a)
    if np.any(state.dst[out] == b):
        return -1
    free = ~state.alive
    if exclude is not None and len(exclude):
        free[exclude] = False
    slots = np.flatnonzero(free)
    if len(slots) == 0:
        return -1
    e = int(slots[0])
    state.src[e], state.dst[e] = a, b
    state.weight[e] = state.base_weight[e] = w
    state.alive[e] = True
    state.transform[e] = transform_code
    state.base_gate[e] = state.gate_mod[e] = state.gate[e] = 1.0
    state.load[e] = 0.0
    return e


def connect(state: State, rng: np.random.Generator, ign: Ignition, freed: np.ndarray) -> np.ndarray:
    """Triadic closure: an ignited, memory-bearing configuration connects to a second-order neighbour
    that also carries memory. Rate-limited and seeded."""
    p = state.params
    if p.connect_per_step <= 0 or len(ign.fired) == 0:
        return np.zeros((0, 3), I32)
    cand = ign.fired[state.memory[ign.fired] >= p.connect_mem_min]
    if len(cand) == 0:
        return np.zeros((0, 3), I32)
    picks = rng.choice(cand, size=min(p.connect_per_step, len(cand)), replace=False)
    out: list[tuple[int, int, int]] = []
    for a in np.sort(picks):
        oa = _out_edges(state, int(a))
        if len(oa) == 0:
            continue
        x = int(state.dst[oa[rng.integers(len(oa))]])
        ox = _out_edges(state, x)
        if len(ox) == 0:
            continue
        b = int(state.dst[ox[rng.integers(len(ox))]])
        if state.memory[b] < p.connect_mem_min * 0.5:
            continue
        e = add_connection(state, int(a), b, p.connect_weight, exclude=freed)
        if e >= 0:
            out.append((e, int(a), b))
    return np.array(out, dtype=I32).reshape(-1, 3)


def reconfigure(state: State, rng: np.random.Generator) -> np.ndarray:
    """An overloaded configuration redirects its strongest connection past its immediate neighbour."""
    p = state.params
    over = np.flatnonzero(state.overload >= p.overload_steps)
    if len(over) == 0 or p.reconfigure_per_step <= 0:
        return np.zeros((0, 3), I32)
    picks = rng.choice(over, size=min(p.reconfigure_per_step, len(over)), replace=False)
    out: list[tuple[int, int, int]] = []
    for a in np.sort(picks):
        a = int(a)
        oa = _out_edges(state, a)
        if len(oa) == 0:
            continue
        e = int(oa[np.argmax(state.weight[oa])])
        x = int(state.dst[e])
        ox = _out_edges(state, x)
        cand = np.setdiff1d(state.dst[ox], np.r_[state.dst[oa], a])
        if len(cand) == 0:
            continue
        b = int(cand[rng.integers(len(cand))])
        state.dst[e] = b
        state.load[e] = 0.0
        state.overload[a] = 0
        out.append((e, x, b))
    return np.array(out, dtype=I32).reshape(-1, 3)


def reconfigure_by_mutation(state: State, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Reduction candidate: reconfiguration expressed as connection mutation — remove the strongest outgoing
    connection and create a connection to a second-order neighbour carrying over its attributes.

    Selection and random draws are identical to :func:`reconfigure`. Returns (events, retired ids) where events
    are (new connection id, previous target, new target)."""
    p = state.params
    over = np.flatnonzero(state.overload >= p.overload_steps)
    if len(over) == 0 or p.reconfigure_per_step <= 0:
        return np.zeros((0, 3), I32), EMPTY_I
    picks = rng.choice(over, size=min(p.reconfigure_per_step, len(over)), replace=False)
    out: list[tuple[int, int, int]] = []
    retired: list[int] = []
    for a in np.sort(picks):
        a = int(a)
        oa = _out_edges(state, a)
        if len(oa) == 0:
            continue
        e = int(oa[np.argmax(state.weight[oa])])
        x = int(state.dst[e])
        ox = _out_edges(state, x)
        cand = np.setdiff1d(state.dst[ox], np.r_[state.dst[oa], a])
        if len(cand) == 0:
            continue
        b = int(cand[rng.integers(len(cand))])
        attrs = (state.weight[e], state.base_weight[e], state.transform[e], state.capacity[e], state.base_gate[e],
                 state.gate_mod[e], state.gate[e])
        state.alive[e] = False  # remove
        # create — never in a slot retired during this step (events must stay unambiguous)
        e2 = add_connection(state, a, b, float(attrs[0]), int(attrs[2]), exclude=np.array([*retired, e], dtype=np.int64))
        if e2 < 0:  # pool full: restore
            state.alive[e] = True
            continue
        (state.base_weight[e2], state.capacity[e2], state.base_gate[e2], state.gate_mod[e2],
         state.gate[e2]) = attrs[1], attrs[3], attrs[4], attrs[5], attrs[6]
        state.overload[a] = 0
        retired.append(e)
        out.append((e2, x, b))
    return np.array(out, dtype=I32).reshape(-1, 3), np.array(retired, dtype=I32)


def mutate(state: State, rng: np.random.Generator, max_per_step: int = 256) -> np.ndarray:
    """Connection mutation at a per-configuration rate (``state.mutation``): a mutated outgoing connection is
    redirected to a uniformly random configuration. Consumes random numbers only when some rate is > 0,
    so runs without mutation are unaffected. Returns (connection, previous target, new target)."""
    if not state.mutation.any():
        return np.zeros((0, 3), I32)
    live = np.flatnonzero(state.alive)
    r = state.mutation[state.src[live]]
    live, r = live[r > 0], r[r > 0]
    pick = live[rng.random(len(live)) < r][:max_per_step]
    if len(pick) == 0:
        return np.zeros((0, 3), I32)
    new = rng.integers(0, state.n, len(pick)).astype(I32)
    ok = new != state.src[pick]
    pick, new = pick[ok], new[ok]
    old = state.dst[pick].copy()
    state.dst[pick] = new
    state.load[pick] = 0.0
    return np.stack([pick, old, new], axis=1).astype(I32) if len(pick) else np.zeros((0, 3), I32)
