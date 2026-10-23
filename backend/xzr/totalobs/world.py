"""A synthetic regional world with finite propagation speed: the common minimal dynamics of the total-observation research line.

What it is. ``rows x cols`` regions (rows: latitude bands, cols: longitude, periodic) carry an activity ``u`` and a persistent *mark* ``m`` (the
material consequence of an intervention). Activity spreads between regions within ``span`` grid steps with a delay ``ceil(d / c)`` (``c``:
propagation speed in regions per step), decays, is fed by a few pulsed sources, and is lowered in decay where a mark sits. Observers
(``observers.py``) read it and disturb it; interventions (``perturb``) change it. Nothing here knows about observers' records: the world
advances whether or not anything is recorded, and a mark outlives every record of the intervention that made it.

What it is not. It is not a model of the Earth. ``km_per_region`` is a declared unit for scaling statements, not a calibration: the model
makes no claim about any real planetary system (``planetary.py`` states the conditions under which it is *planetary in structure* and nothing more).
The state of this world is not "reality as a whole": it is the part of a synthetic world that the verifier may read (``verifier.py``); the research agent
never reads it (``ontology.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# the world generator and the engine stream are seeded separately (as everywhere in this repository): ``gen`` fixes the sources,
# ``seed`` the process noise and the observers' noise
SEED_STRIDE = 7919


@dataclass
class WorldConfig:
    rows: int = 8
    cols: int = 12
    c: float = 1.0  # propagation speed: regions per step
    span: int = 2  # interaction range: grid distance within which regions couple
    coupling: float = 0.30
    decay: float = 0.08
    mark_gain: float = 0.5  # a mark lowers the local decay by this fraction of its value (floor at 10 % of decay)
    mark_decay: float = 0.002  # marks are long-lived
    n_sources: int = 3
    source_period: int = 28  # speed of the world's own events: steps between pulses of one source
    pulse_len: int = 8
    source_amp: float = 0.9
    noise: float = 0.004
    km_per_region: float = 500.0  # declared unit (synthetic); no calibration against any real system

    @property
    def n(self) -> int:
        return self.rows * self.cols


def dist(cfg: WorldConfig, a: int, b: int) -> int:
    ra, ca = divmod(a, cfg.cols)
    rb, cb = divmod(b, cfg.cols)
    dc = abs(ca - cb)
    return abs(ra - rb) + min(dc, cfg.cols - dc)


def dist_matrix(cfg: WorldConfig) -> np.ndarray:
    n = cfg.n
    r, c = np.divmod(np.arange(n), cfg.cols)
    dr = np.abs(r[:, None] - r[None, :])
    dc = np.abs(c[:, None] - c[None, :])
    return dr + np.minimum(dc, cfg.cols - dc)


class World:
    def __init__(self, cfg: WorldConfig, gen: int, seed: int):
        self.cfg = cfg
        n = cfg.n
        self.t = 0
        self.rng = np.random.default_rng(seed * SEED_STRIDE + 1)
        g = np.random.default_rng(gen * SEED_STRIDE + 3)
        self.u = np.zeros(n)
        self.m = np.zeros(n)
        d = dist_matrix(cfg)
        self.d = d
        # interaction pairs within span, with weights and integer delays
        ii, jj = np.nonzero((d > 0) & (d <= cfg.span))
        self._ii, self._jj = ii, jj
        self._w = 1.0 / d[ii, jj]
        self._tau = np.maximum(1, np.ceil(d[ii, jj] / max(cfg.c, 1e-9)).astype(int))
        self._wsum = np.bincount(ii, weights=self._w, minlength=n)
        self._L = int(self._tau.max(initial=1)) + 1
        self._H = np.zeros((self._L, n))
        # sources: region, phase; the generator seed fixes them (the same world for every arm)
        self.src_region = g.choice(n, size=min(cfg.n_sources, n), replace=False)
        self.src_phase = g.integers(0, cfg.source_period, size=len(self.src_region))
        self.src_amp = cfg.source_amp * (0.8 + 0.4 * g.random(len(self.src_region)))
        self.events: list[dict] = []  # harness changes of the world itself (a source moved / added): these are world-side facts

    # ------------------------------------------------------------------------------------------------- world-side harness changes
    def move_source(self, k: int, region: int) -> None:
        self.src_region[k] = region
        self.events.append({"t": self.t, "do": "move_source", "source": int(k), "region": int(region)})

    def add_source(self, region: int, amp: float | None = None, phase: int | None = None) -> int:
        self.src_region = np.append(self.src_region, region)
        self.src_phase = np.append(self.src_phase, self.t % self.cfg.source_period if phase is None else phase)
        self.src_amp = np.append(self.src_amp, amp if amp is not None else float(np.mean(self.src_amp)))
        self.events.append({"t": self.t, "do": "add_source", "region": int(region)})
        return len(self.src_region) - 1

    # ------------------------------------------------------------------------------------------------- interventions
    def perturb(self, region: int, amount: float, radius: int = 0) -> int:
        """Inject activity and leave a mark in the regions within ``radius`` of ``region`` (a permitted intervention). Returns the regions changed."""
        reg = np.flatnonzero(self.d[region] <= radius)
        self.u[reg] += amount
        self.m[reg] += abs(amount)
        return int(len(reg))

    def absorb(self, regions: np.ndarray, fraction: float) -> None:
        self.u[regions] *= 1.0 - fraction

    # ------------------------------------------------------------------------------------------------- dynamics
    def sources_now(self) -> np.ndarray:
        s = np.zeros(self.cfg.n)
        for r, ph, a in zip(self.src_region, self.src_phase, self.src_amp, strict=True):
            if (self.t + ph) % self.cfg.source_period < self.cfg.pulse_len:
                s[r] += a
        return s

    def step(self) -> None:
        cfg = self.cfg
        # delayed neighbour values: u_j(t - tau_ij)
        past = self._H[(self.t - self._tau) % self._L, self._jj]
        flow = np.bincount(self._ii, weights=self._w * (past - self.u[self._ii]), minlength=cfg.n) / np.maximum(self._wsum, 1e-9)
        dec = np.maximum(cfg.decay * 0.1, cfg.decay - cfg.mark_gain * cfg.decay * self.m / (1.0 + self.m))
        nu = self.u + cfg.coupling * flow - dec * self.u + self.sources_now() + cfg.noise * self.rng.standard_normal(cfg.n)
        self._H[self.t % self._L] = self.u  # u(t) is what neighbours see at t + tau
        self.u = np.maximum(nu, 0.0)
        self.m *= 1.0 - cfg.mark_decay
        self.t += 1

    def snapshot(self) -> dict:
        return {"t": self.t, "u": self.u.copy(), "m": self.m.copy()}
