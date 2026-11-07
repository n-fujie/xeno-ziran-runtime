"""The substrate of the Simondonian Body Simulation (SBS): N identical particles in a periodic 2-D box, overdamped Langevin dynamics, a tunable pair attraction.

This is an ordinary condensation model (a Weeks-Chandler-Andersen core with an attractive tail of well depth ``eps``) and nothing in it is a body: the particles are not grouped, labelled or given a boundary. The control parameters are the ones a physicist would use: the thermal energy ``kT`` (the noise of the milieu), the well depth ``eps`` (the coupling) and an optional uniform drift force. A group of particles that stays together is a PHENOMENON of these dynamics, to be detected by an observer (``organisation.py``) and compared with ordinary descriptions (``comparison.py``); this module never decides that one exists.

Units: particle diameter 1, friction 1, so the diffusion coefficient is kT. Everything is a pure function of the configuration and the seeds: a run is reproduced exactly by the same seeds and parameters (common random numbers: a branch that shares the noise seed of another receives the same noise at every step, so that an intervention is compared with its control on the same noise).

Not claimed: that this is a model of any real material, organism or body; the numbers (box size, thresholds) are declared conventions of this synthetic model, not measurements."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy.spatial import cKDTree

SIGMA = 1.0  # particle diameter
RM = 2 ** (1 / 6) * SIGMA  # minimum of the WCA core
WC = 1.0  # width of the attractive tail (cos^2 switch from RM to RM + WC)
R_CUT = RM + WC


@dataclass(frozen=True)
class Config:
    n: int = 60
    density: float = 0.25  # particles per unit area
    kT: float = 0.3  # thermal energy of the milieu
    eps: float = 1.0  # well depth of the attraction (coupling)
    dt: float = 0.002
    drift: float = 0.0  # uniform force along +x on every particle

    def box(self) -> float:
        return float(np.sqrt(self.n / self.density))

    def asdict(self) -> dict:
        return asdict(self)


def _pair_forces(x: np.ndarray, box: float, eps: float) -> np.ndarray:
    """Forces on every particle (minimum image, neighbour pairs within the cut-off from a periodic k-d tree); the repulsive core has strength 1 and the tail strength ``eps``."""
    out = np.zeros_like(x)
    pairs = cKDTree(x, boxsize=box).query_pairs(R_CUT, output_type="ndarray")
    if pairs.size == 0:
        return out
    i, j = pairs[:, 0], pairs[:, 1]
    d = x[i] - x[j]
    d -= box * np.round(d / box)
    r2 = (d**2).sum(-1)
    r = np.sqrt(r2)
    f = np.empty_like(r)
    core = r < RM
    inv6 = (SIGMA**2 / r2) ** 3
    f[core] = 24.0 * (2.0 * inv6[core] ** 2 - inv6[core]) / r[core]  # -dU/dr of the WCA core: repulsive, along +r
    arg = np.pi * (r[~core] - RM) / (2.0 * WC)
    f[~core] = -eps * (np.pi / (2.0 * WC)) * np.sin(2.0 * arg)  # U = -eps cos^2(arg): the tail attracts
    fv = (f / r)[:, None] * d
    n = len(x)
    for k in range(2):  # bincount is several times faster than np.add.at for these sizes
        out[:, k] = np.bincount(i, fv[:, k], minlength=n) - np.bincount(j, fv[:, k], minlength=n)
    return out


class Sim:
    """One trajectory. ``noise_seed`` fixes the noise sequence (shared by branches that must see the same noise); ``seed`` fixes the initial gas."""

    def __init__(self, cfg: Config, seed: int, noise_seed: int | None = None):
        self.cfg = cfg
        self.box = cfg.box()
        rng = np.random.default_rng(seed)
        side = int(np.ceil(np.sqrt(cfg.n)))
        grid = np.array([(i % side, i // side) for i in range(cfg.n)], dtype=float) * (self.box / side)
        self.x = (grid + 0.15 * rng.normal(size=grid.shape)) % self.box  # a jittered lattice, then equilibrated as a gas by the caller
        self.noise = np.random.default_rng(seed + 10_000_019 if noise_seed is None else noise_seed)
        self.t = 0.0
        self.unwrapped = self.x.copy()

    def clone(self, noise_seed: int) -> Sim:
        new = object.__new__(Sim)
        new.cfg, new.box = self.cfg, self.box
        new.x, new.unwrapped, new.t = self.x.copy(), self.unwrapped.copy(), self.t
        new.noise = np.random.default_rng(noise_seed)
        return new

    def step(self, n: int, kT: float | None = None, eps: float | None = None, drift: float | None = None, pull: np.ndarray | None = None) -> None:
        """Advance ``n`` steps; ``kT``, ``eps`` and ``drift`` override the configuration for these steps (an intervention); ``pull`` is a per-particle force vector."""
        c = self.cfg
        kt = c.kT if kT is None else kT
        e = c.eps if eps is None else eps
        g = c.drift if drift is None else drift
        amp = np.sqrt(2.0 * kt * c.dt)
        for _ in range(n):
            f = _pair_forces(self.x, self.box, e)
            f[:, 0] += g
            if pull is not None:
                f += pull
            dx = f * c.dt + amp * self.noise.normal(size=self.x.shape)
            dx = np.clip(dx, -0.2, 0.2)  # a numerical guard against a single violent overlap; counted by the caller via ``guard_hits`` if needed
            self.x = (self.x + dx) % self.box
            self.unwrapped += dx
        self.t += n * c.dt

    def snapshot(self) -> dict:
        return {"t": self.t, "x": self.x.copy(), "unwrapped": self.unwrapped.copy()}
