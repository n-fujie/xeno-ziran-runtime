"""Instruments: what an operation can know about the world, and why it cannot know the rest.

An operation receives an :class:`Observation`, never the world. An observation is a set of per-cluster values at the
instrument's resolution (a level of the intrinsic hierarchy), aggregated over the instrument's time window. Every
value that is not observed is NaN *and* carries a reason; a missing value is never turned into zero:

    unmeasurable          no instrument in this configuration can measure the channel (it is not in the
                          configuration's channel catalog; ``interior`` is never in it)
    instrument_mismatch   the channel exists in the configuration, but this instrument does not carry it
    scale_mismatch        the operation needs a finer resolution than the instrument has, or the channel does not
                          exist at the instrument's resolution
    time_window_mismatch  the instrument's window (or sampling period) is longer than the operation's phenomenon
    boundary_invisible    the cluster is behind a veil the instrument cannot penetrate
    unmeasured            the channel could be measured but was not (the operation could not pay for the
                          measurement)

Channels (all per cluster c at level L, window w):

    activity        ignitions in c per configuration per step
    tension         share of configurations of c with difference in [0.5, 1) × effective threshold (metastability)
    memory          mean retained history (memory) of c
    recursion       share of ignitions in c caused by a connection from inside c
    structure       live connections inside c per configuration
    boundary_flow   matrix of penetrations from cluster a into cluster b (a ≠ b), per step (levels ≤ 2 only)
    symbol          exists only when the configuration includes a symbolic layer (never in the default catalog)
    interior        never measurable (kept to show the distinction between 'cannot' and 'did not')
    activity_trend  derived: activity in the later half of the window minus the earlier half (only when adopted)
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from .world import RING, World

CHANNELS = ("activity", "tension", "memory", "recursion", "structure", "boundary_flow", "symbol", "interior",
            "activity_trend")
DERIVED = ("activity_trend",)  # derived variables a configuration can adopt (HPO-003 proposals with an implementation)
DEFAULT_CATALOG = ("activity", "tension", "memory", "recursion", "structure", "boundary_flow")
REASONS = ("unmeasurable", "instrument_mismatch", "scale_mismatch", "time_window_mismatch", "boundary_invisible",
           "unmeasured")
MAX_FLOW_LEVEL = 2
COST_PER_CLUSTER = 0.002  # resource cost of measuring one channel in one cluster


@dataclass(frozen=True)
class InstrumentSpec:
    channels: tuple[str, ...] = DEFAULT_CATALOG
    level: int = 1  # 0 macro (8 clusters) … 3 configuration-scale (512)
    window: int = 4
    period: int = 2
    noise: float = 0.0  # relative multiplicative noise (sd)
    penetration: float = 0.0  # veils with opacity ≤ penetration are seen through
    oracle: bool = False  # truth access (HPO-001 leak control only): every channel, no veil, no cost, no noise

    def with_(self, **kw) -> InstrumentSpec:
        return replace(self, **kw)

    def to_dict(self) -> dict:
        return {"channels": list(self.channels), "level": self.level, "window": self.window, "period": self.period,
                "noise": self.noise, "penetration": self.penetration, "oracle": self.oracle}

    @classmethod
    def from_dict(cls, d: dict) -> InstrumentSpec:
        d = dict(d)
        if "channels" in d:
            d["channels"] = tuple(d["channels"])
        return cls(**d)


@dataclass
class Veil:
    owner: str  # operation id (or "history" for a re-inserted veil)
    nodes: np.ndarray
    opacity: float
    event: int = -1  # causal-history event that created it
    kind: str = ""  # the kind whose rule made it
    until: int | None = None  # re-inserted veils expire


@dataclass
class Observation:
    t: int
    level: int
    n_clusters: int
    values: dict[str, np.ndarray] = field(default_factory=dict)  # per cluster (boundary_flow: K×K)
    reasons: dict[str, np.ndarray] = field(default_factory=dict)  # per cluster, '' = observed
    own_clusters: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int32))  # clusters of the op's region
    labels: np.ndarray | None = None  # cluster of each configuration at this level (addresses are public)
    sizes: np.ndarray | None = None
    veil_events: set[int] = field(default_factory=set)  # causal events of the veils that hid clusters

    def get(self, channel: str, clusters: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        """(values, observed mask) for the clusters (default: all)."""
        v = self.values.get(channel)
        if v is None:
            k = self.n_clusters if clusters is None else len(clusters)
            return np.full(k, np.nan), np.zeros(k, bool)
        if clusters is not None:
            v = v[clusters]
        return v, ~np.isnan(v)

    def reason(self, channel: str, clusters: np.ndarray | None = None) -> str:
        """Dominant reason why the channel is not observed for these clusters ('' if all observed)."""
        r = self.reasons.get(channel)
        if r is None:
            return "unmeasurable"
        if clusters is not None:
            r = r[clusters]
        missing = r[r != ""]
        if not len(missing):
            return ""
        vals, counts = np.unique(missing, return_counts=True)
        return str(vals[np.argmax(counts)])

    def unobserved_counts(self) -> dict[str, int]:
        """Per reason: number of channels of this observation with at least one cluster unobserved for it."""
        out: dict[str, int] = {}
        for r in self.reasons.values():
            for x in set(r[r != ""].tolist()):
                out[str(x)] = out.get(str(x), 0) + 1
        return out


class Instruments:
    """Computes observations from the world for every operation; caches per-step aggregates per (level, window)."""

    def __init__(self, world: World, catalog: tuple[str, ...] = DEFAULT_CATALOG):
        self.world = world
        self.catalog = tuple(catalog)
        self.veils: list[Veil] = []
        self.apply_veils = True  # off: veils are recorded but change no one's observation (ablation)
        self._cache: dict = {}
        self._cache_t = -1

    def _labels(self, level: int) -> np.ndarray:
        return self.world.h.labels[level]

    def _agg(self, level: int, window: int) -> dict:
        t = self.world.t
        if t != self._cache_t:
            self._cache, self._cache_t = {}, t
        key = (level, window)
        if key in self._cache:
            return self._cache[key]
        w = self.world
        st = w.state
        lab = self._labels(level)
        k = int(lab.max()) + 1
        size = np.bincount(lab, minlength=k).astype(float)
        recs = w.records[-window:] if window <= RING else w.records
        nw = max(1, len(recs))
        ign = np.concatenate([r.ignitions for r in recs]) if recs else np.zeros(0, np.int32)
        ps = np.concatenate([r.pen_src for r in recs]) if recs else np.zeros(0, np.int32)
        pd = np.concatenate([r.pen_dst for r in recs]) if recs else np.zeros(0, np.int32)
        activity = np.bincount(lab[ign], minlength=k) / (np.maximum(size, 1) * nw)
        theta = st.theta_eff()
        ratio = st.diff / np.maximum(theta, 1e-9)
        tension = np.bincount(lab, weights=((ratio >= 0.5) & (ratio < 1.0)).astype(float), minlength=k) / np.maximum(size, 1)
        memory = np.bincount(lab, weights=st.memory, minlength=k) / np.maximum(size, 1)
        ls, ld = lab[ps], lab[pd]
        caused = np.bincount(ld, minlength=k).astype(float)
        internal = np.bincount(ld[ls == ld], minlength=k).astype(float)
        with np.errstate(invalid="ignore", divide="ignore"):
            recursion = np.where(caused > 0, internal / np.maximum(caused, 1), np.nan)
        alive = st.alive
        es, ed = lab[st.src[alive]], lab[st.dst[alive]]
        structure = np.bincount(es[es == ed], minlength=k) / np.maximum(size, 1)
        out = {"activity": activity, "tension": tension, "memory": memory, "recursion": recursion,
               "structure": structure, "_k": k, "_size": size}
        if "activity_trend" in self.catalog and len(recs) >= 2:
            half = len(recs) // 2
            early = np.concatenate([r.ignitions for r in recs[:half]]) if half else np.zeros(0, np.int32)
            late = np.concatenate([r.ignitions for r in recs[half:]])
            out["activity_trend"] = (np.bincount(lab[late], minlength=k) / max(1, len(recs) - half)
                                     - np.bincount(lab[early], minlength=k) / max(1, half)) / np.maximum(size, 1)
        if level <= MAX_FLOW_LEVEL:
            cross = ls != ld
            flow = np.bincount(ls[cross] * k + ld[cross], minlength=k * k).reshape(k, k) / nw
            out["boundary_flow"] = flow
        self._cache[key] = out
        return out

    def veiled_mask(self, level: int, spec: InstrumentSpec, viewer: str) -> tuple[np.ndarray, set[int]]:
        """Clusters at this level hidden from an instrument, and the events of the veils that hid them.

        A veil hides a region from every instrument except its owner's (a withdrawn region is withdrawn from every
        relation, including operations whose own region contains it); ``penetration`` sees through thin veils.
        """
        lab = self._labels(level)
        k = int(lab.max()) + 1
        hidden = np.zeros(k, bool)
        events: set[int] = set()
        if spec.oracle or not self.apply_veils:
            return hidden, events
        size = np.bincount(lab, minlength=k)
        for v in self.veils:
            if v.owner == viewer or v.opacity <= spec.penetration or not len(v.nodes):
                continue
            cl = np.unique(lab[v.nodes])
            frac = np.bincount(lab[v.nodes], minlength=k)[cl] / size[cl]  # hidden when most of the cluster is veiled
            hit = cl[frac >= 0.5]
            if len(hit):
                hidden[hit] = True
                events.add(v.event)
        return hidden, events

    def observe(self, spec: InstrumentSpec, needs: dict[str, tuple[int, int]], own_nodes: np.ndarray,
                budget: float, rng: np.random.Generator | None, viewer: str = "") -> tuple[Observation, float]:
        """Observation for one operation; returns it and the resource cost spent.

        ``needs``: channel → (minimum level, maximum window) the operation's phenomenon requires.
        """
        level = min(spec.level, len(self.world.h.labels) - 1)
        agg = self._agg(level, spec.window)
        k = agg["_k"]
        lab = self._labels(level)
        obs = Observation(self.world.t, level, k, own_clusters=np.unique(lab[own_nodes]).astype(np.int32)
                          if len(own_nodes) else np.zeros(0, np.int32), labels=lab, sizes=agg["_size"])
        hidden, obs.veil_events = self.veiled_mask(level, spec, viewer)
        cost = 0.0
        for ch, (min_level, max_window) in needs.items():
            reason = ""
            if spec.oracle:
                reason = "unmeasurable" if ch in ("interior", "symbol") and ch not in self.catalog else ""
            elif ch not in self.catalog or ch == "interior":
                reason = "unmeasurable"
            elif ch not in spec.channels:
                reason = "instrument_mismatch"
            elif level < min_level or (ch == "boundary_flow" and level > MAX_FLOW_LEVEL):
                reason = "scale_mismatch"
            elif spec.window > max_window or spec.period > max_window:
                reason = "time_window_mismatch"
            elif ch not in agg:
                reason = "unmeasurable"
            if not reason and not spec.oracle:
                c = COST_PER_CLUSTER * k
                if cost + c > budget:
                    reason = "unmeasured"
                else:
                    cost += c
            if reason:
                shape = (k, k) if ch == "boundary_flow" else (k,)
                obs.values[ch] = np.full(shape, np.nan)
                obs.reasons[ch] = np.full(k, reason, dtype=object)
                continue
            v = np.array(agg[ch], dtype=float, copy=True)
            if spec.noise and rng is not None and not spec.oracle:
                v = v * (1.0 + spec.noise * rng.standard_normal(v.shape))
            r = np.full(k, "", dtype=object)
            if hidden.any():
                if ch == "boundary_flow":
                    v[hidden, :] = np.nan
                    v[:, hidden] = np.nan
                else:
                    v[hidden] = np.nan
                r[hidden] = "boundary_invisible"
            obs.values[ch] = v
            obs.reasons[ch] = r
        return obs, cost
