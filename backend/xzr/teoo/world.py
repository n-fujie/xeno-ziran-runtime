"""A SYNTHETIC world with a known truth, for experiments on what an observation condition can and cannot tell apart.

Everything here is artificial and says nothing about any body. The world is a set of components joined by directed couplings; each component has a declared *operational shape* (what it does over time): a
periodic oscillation (amplitude, frequency), optional intermittent bursts, and a feed-forward influence from the components that are coupled into it. The truth (the parameters, the noise-free signals) is known
because it is the definition of the world, and is kept apart from what an observer gets. Nothing is physically simulated: when a graph edge is cut here, the simulated signal changes because the generator says
so; that is a property of this synthetic world, not a statement about any physical body.

The observer is a sensor with the parameters TEOO already declares (spatial resolution, sampling period, window, detection limit, penetration), and each parameter acts through a mechanism, so that the TEOO
status of a target (SCALE_MISMATCH, TIME_WINDOW_MISMATCH, SIGNAL_BELOW_THRESHOLD, BOUNDARY_INVISIBLE) is a *prediction* that the detectors below can be compared with:

* resolution coarser than the structure's scale: the reading mixes the component with the mean of the others (weight scale / resolution on the component);
* sampling period: the continuous signal is sampled without an anti-aliasing filter (frequencies above the Nyquist frequency alias); the window limits how long the trace is;
* detection limit: samples below it carry no value (status SIGNAL_BELOW_THRESHOLD; never reported as 0);
* penetration below the boundary's opacity: the reading is attenuated by exp(-8 (opacity - penetration)).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from . import observation as OB

DT = 0.005  # the fine grid of the latent signal (s); the sensor samples from it
NOISE_SD = 0.3  # sensor noise


@dataclass
class Component:
    id: str
    f: float  # Hz
    amp: float
    scale: float  # the spatial scale of the structure (the unit of the sensor's resolution)
    opacity: float  # boundary opacity between the component and the sensor
    burst_rate: float = 0.0  # bursts per second
    burst_amp: float = 0.0


@dataclass
class World:
    comps: list[Component]
    edges: dict[tuple[int, int], float] = field(default_factory=dict)  # (source, target) -> coupling strength
    lag_s: float = 0.15

    def copy(self) -> World:
        return World([Component(**c.__dict__) for c in self.comps], dict(self.edges), self.lag_s)

    def n(self) -> int:
        return len(self.comps)


def make_world(seed: int, n: int = 10, extra_edges: int = 4) -> World:
    """A deterministic random world: n components, a spanning chain of couplings plus a few extra ones."""
    rng = np.random.default_rng(10_000 + seed)
    comps = [Component(f"c{i}", f=float(rng.uniform(0.3, 3.0)), amp=float(rng.uniform(0.8, 2.0)), scale=float(rng.uniform(1.0, 3.0)), opacity=float(rng.choice([0.0, 0.1, 0.3, 0.5, 0.8]))) for i in range(n)]
    edges: dict[tuple[int, int], float] = {}
    for i in range(1, n):
        edges[(int(rng.integers(0, i)), i)] = float(rng.uniform(0.4, 0.8))  # a tree of couplings keeps the graph connected
    tries = 0
    while len(edges) < n - 1 + extra_edges and tries < 200:
        tries += 1
        a, b = sorted(int(v) for v in rng.integers(0, n, size=2))  # couplings run from a lower to a higher index: the world is acyclic, so influence propagates along paths
        if a != b and (a, b) not in edges:
            edges[(a, b)] = float(rng.uniform(0.3, 0.7))
    return World(comps, edges)


def _shift(x: np.ndarray, k: int) -> np.ndarray:
    return np.concatenate([np.zeros(k), x[:-k]]) if k > 0 else x


def latent(w: World, t: np.ndarray, rng: np.random.Generator, only: int | None = None) -> np.ndarray:
    """The noise-free signals of all components over times t (shape n x len(t)); the phases and the bursts are redrawn per trial. A component's signal is its own oscillation (and bursts) plus the lagged signals of the
    components coupled into it, so influence propagates along paths (the couplings run from lower to higher index). ``only``: keep the own signal of that component alone (used to define how much of a component's
    signal comes from a source: its operability)."""
    n = w.n()
    phi = rng.uniform(0, 2 * math.pi, n)
    own = np.stack([c.amp * np.sin(2 * math.pi * c.f * t + phi[i]) for i, c in enumerate(w.comps)])
    for i, c in enumerate(w.comps):
        if c.burst_rate > 0:
            for t0 in np.sort(rng.uniform(t[0], t[-1], rng.poisson(c.burst_rate * (t[-1] - t[0])))):
                own[i] += c.burst_amp * np.exp(-(((t - t0) / 0.4) ** 2)) * np.sin(2 * math.pi * 3 * c.f * (t - t0))
    if only is not None:
        keep = own[only].copy()
        own[:] = 0.0
        own[only] = keep
    k_lag = max(1, int(round(w.lag_s / DT)))
    x = own.copy()
    for b in range(n):  # indices increase along every coupling, so a component's sources are final when it is reached
        for (a, bb), k in w.edges.items():
            if bb == b:
                x[b] += k * _shift(x[a], k_lag)
    return x


def spec_of(w: World, i: int) -> dict:
    c = w.comps[i]
    return OB.target_spec(c.id, "angle", scale=c.scale, phenomenon_period_s=1.0 / c.f, amplitude=c.amp, opacity=c.opacity)


def sensor_of(r: float, ts: float, win: float, lim: float, pen: float, sid: str = "s", cost_per_s: float = 0.0) -> dict:
    return OB.sensor(sid, ["angle"], resolution=r, sampling_period_s=ts, window_s=win, detection_limit=lim, penetration=pen, cost_per_s=cost_per_s)


def observe(w: World, x: np.ndarray, t: np.ndarray, sens: dict, rng: np.random.Generator, comps: list[int] | None = None, gaps: float = 0.0, sync_jitter_s: float = 0.0
            ) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """What the sensor returns for each component: (times, values) with NaN where the sample carries no value (below the detection limit, in a gap). ``comps``: the components within the sensor's reach."""
    n = w.n()
    r, ts, win, lim, pen = sens["resolution"], sens["sampling_period_s"], sens["window_s"], sens["detection_limit"], sens["penetration"]
    idx = np.arange(0, min(len(t), int(round(win / DT))), max(1, int(round(ts / DT))))
    if sync_jitter_s:
        idx = np.clip(idx + np.round(rng.normal(0, sync_jitter_s / DT, len(idx))).astype(int), 0, len(t) - 1)
    mean_all = x.sum(axis=0)
    out: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for i in (range(n) if comps is None else comps):
        c = w.comps[i]
        wgt = min(1.0, c.scale / r)
        y = wgt * x[i] + (1 - wgt) * ((mean_all - x[i]) / max(1, n - 1))
        tau = 1.0 if c.opacity <= pen else math.exp(-8.0 * (c.opacity - pen))
        v = (tau * y)[idx] + rng.normal(0, NOISE_SD, len(idx))
        v = np.where(np.abs(v) < lim, np.nan, v)  # below the detection limit: no value (never 0)
        if gaps > 0:
            v = np.where(rng.uniform(size=len(v)) < gaps, np.nan, v)
        out[i] = (t[idx], v)
    return out


# ------------------------------------------------------------------------------------------------ detectors: a p-value for "does this feature differ between the two conditions?"
MIN_VALID = 12


def _valid(v: np.ndarray) -> np.ndarray:
    return v[~np.isnan(v)]


def feature(kind: str, tv: tuple[np.ndarray, np.ndarray], other: tuple[np.ndarray, np.ndarray] | None = None) -> float | None:
    """One number per trace; None when too few samples carry a value (the answer is then undetermined, not 0)."""
    t, v = tv
    ok = ~np.isnan(v)
    if ok.sum() < MIN_VALID:
        return None
    if kind == "amplitude":
        return float(np.std(v[ok]))
    if kind == "frequency":
        vv = np.where(ok, v, 0.0) - np.nanmean(v)
        vv = np.where(ok, vv, 0.0)
        dt = float(t[1] - t[0])
        spec = np.abs(np.fft.rfft(vv * np.hanning(len(vv)), n=max(4096, len(vv) * 8)))
        fr = np.fft.rfftfreq(max(4096, len(vv) * 8), dt)
        spec[fr < 0.05] = 0
        return float(fr[int(np.argmax(spec))])
    if kind == "burst":
        vv = np.where(ok, v, 0.0)
        k = max(3, len(vv) // 25)
        env = np.sqrt(np.convolve(vv**2, np.ones(k) / k, mode="valid"))
        return float(env.max() / (np.median(env) + 1e-9))
    if kind == "coupling":
        if other is None:
            return None
        a, b = tv[1], other[1]
        m = ~np.isnan(a) & ~np.isnan(b)
        if m.sum() < MIN_VALID:
            return None
        a, b = a[m] - a[m].mean(), b[m] - b[m].mean()
        best = 0.0
        for lag in range(0, 6):
            aa, bb = (a[: len(a) - lag], b[lag:]) if lag else (a, b)
            den = math.sqrt(float((aa**2).sum() * (bb**2).sum()))
            if den > 0:
                best = max(best, abs(float((aa * bb).sum()) / den))
        return best
    raise ValueError(kind)


def perm_p(a: list[float], b: list[float], rng: np.random.Generator, n_perm: int = 1000) -> float:
    """Two-sided randomisation test of a difference of means (labels shuffled), vectorised."""
    y = np.asarray(a + b, float)
    na = len(a)
    obs = abs(y[na:].mean() - y[:na].mean())
    idx = rng.permuted(np.tile(np.arange(len(y)), (n_perm, 1)), axis=1)
    yy = y[idx]
    d = np.abs(yy[:, na:].mean(axis=1) - yy[:, :na].mean(axis=1))
    return float((np.sum(d >= obs - 1e-12) + 1) / (n_perm + 1))


def detect(kind: str, traces0: list[Any], traces1: list[Any], rng: np.random.Generator, alpha: float = 0.01, n_perm: int = 1000) -> dict[str, Any]:
    """Compare the feature between the two conditions. ``traces``: per trial a (times, values) or, for the coupling feature, a pair of such. Returns identified / not / undetermined with the p-value."""
    if kind == "coupling":
        f0 = [feature(kind, a, b) for a, b in traces0]
        f1 = [feature(kind, a, b) for a, b in traces1]
    else:
        f0, f1 = [feature(kind, tr) for tr in traces0], [feature(kind, tr) for tr in traces1]
    g0, g1 = [x for x in f0 if x is not None], [x for x in f1 if x is not None]
    if len(g0) < 4 or len(g1) < 4:
        return {"result": "undetermined", "p": None, "n0": len(g0), "n1": len(g1)}
    p = perm_p(g0, g1, rng, n_perm)
    return {"result": "identified" if p < alpha else "not_identified", "p": p, "n0": len(g0), "n1": len(g1), "effect": float(np.mean(g1) - np.mean(g0))}
