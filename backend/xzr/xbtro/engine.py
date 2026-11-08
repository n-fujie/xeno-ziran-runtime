"""The body simulator: a batched, deterministic, planar N-link body with separate operation lines.

* Mechanics: an N-link planar chain (Lagrangian equations, exact mass matrix), RK4 with the muscle drive held constant over a
  step; joint torque = muscle drive + passive viscoelasticity; the ankle torque is limited by the base of support (centre of
  pressure must stay inside the foot); Coulomb friction is checked; pushes, a ledge (narrower support) and a handrail are
  part of the environment.
* Sensing: proprioceptive, vestibular, visual, tactile and cue channels, each a *delayed, noisy copy* of the true quantity
  (delay and noise from the line / sensor settings). The controller only ever sees these copies.
* Operation lines: ``ignite`` when their own sensed condition holds, stay active for a hold time, and cost energy; their
  commands reach the muscles after the line's own latency. Lines are separate contributions to the joint drive, so conflicts
  and couplings between them can be read from the record.
* Internal coordination: breathing phase, energy, fatigue, slow gain adaptation, all optional.

All seeds of a batch advance together (arrays of shape (S, ...)); noise is drawn up front from ``seed`` so two runs that differ
only in configuration share their noise (common random numbers), and observation noise comes from a different stream so that
changing an observation never changes the body. Nothing here is measured physiology: values are nominal and limited.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from . import xeno14 as _x14

LINE_IDS_SENS = ("sens.proprio", "sens.vestibular", "sens.visual", "sens.tactile", "sens.cue")
CUE_PULSE_S = 0.2
FALL_ANGLE = 0.9
# run-time divergence criteria (a trajectory that satisfies any of these is a numerical failure, not a fall)
DIVERGE_OMEGA = 60.0  # rad/s, far beyond any physical joint rate of this model
DIVERGE_TORQUE = 40.0  # total joint torque in units of the largest joint's tau_max
CC_MAX = 0.9  # co-contraction is clipped here (see _step), so the static check covers cc in [0, CC_MAX]


def smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


@dataclass
class Params:
    """Numbers derived from a configuration dict (once per run)."""

    cfg: dict[str, Any]
    n: int = 0
    dt: float = 0.01
    length: np.ndarray = field(default_factory=lambda: np.zeros(0))
    mass: np.ndarray = field(default_factory=lambda: np.zeros(0))
    d: np.ndarray = field(default_factory=lambda: np.zeros(0))
    inertia: np.ndarray = field(default_factory=lambda: np.zeros(0))

    def __post_init__(self) -> None:
        c = self.cfg
        self.n = len(c["links"])
        self.dt = float(c["task"]["dt"])
        self.substeps = int(c["task"].get("substeps", 1))
        self.integrator = str(c["task"].get("integrator", "rk4"))
        self.length = np.array([ln["length"] for ln in c["links"]], dtype=float)
        self.mass = np.array([ln["mass"] for ln in c["links"]], dtype=float)
        self.d = np.array([ln["com_frac"] * ln["length"] for ln in c["links"]], dtype=float)
        self.inertia = self.mass * self.length**2 / 12.0
        n = self.n
        coef = np.zeros((n, n))
        for k in range(n):
            for i in range(n):
                coef[k, i] = self.length[i] if i < k else (self.d[k] if i == k else 0.0)
        self.coef = coef
        self.H = coef.T @ np.diag(self.mass) @ coef
        self.Sg = coef.T @ self.mass
        self.mtot = float(self.mass.sum())
        self.tau_max = np.array([j["tau_max"] for j in c["joints"]])
        self.k_pass = np.array([j["k_passive"] for j in c["joints"]])
        self.c_pass = np.array([j["c_passive"] for j in c["joints"]])
        self.q_range = np.array([j["q_range"] for j in c["joints"]])
        self.act_rise = np.array([j["act_rise"] for j in c["joints"]])
        self.act_fall = np.array([j["act_fall"] for j in c["joints"]])
        self.lines = {ln["id"]: ln for ln in c["lines"]}
        self.line_ids = [ln["id"] for ln in c["lines"]]
        self.g = float(c["environment"]["gravity"])
        self.trunk = min(2, n - 1)
        self.head = n - 1
        # nominal COM height with the body upright (used by the controller's crude estimators)
        up = np.cumsum(self.length)
        self.h_com = float((self.mass * (np.concatenate([[0.0], up[:-1]]) + self.d)).sum() / self.mtot)

    @property
    def h(self) -> float:
        return self.dt / self.substeps

    def numeric_stability(self, cc: float = CC_MAX, integrator: str | None = None) -> dict[str, Any]:
        """A-priori stability of one plant sub-step for the passive joint dynamics at the upright pose.

        The passive plant is linear there: x' = A x with A = [[0, I], [-M^-1 K, -M^-1 C]] in absolute segment angles (joint
        angles are relative: q = T theta, K = T' k T, C = T' c T; co-contraction ``cc`` scales both; gravity is left out, it only
        moves slow eigenvalues). One sub-step of length h maps x to Phi x, with
        * RK4:                 Phi = I + Ah + (Ah)^2/2 + (Ah)^3/6 + (Ah)^4/24   (the muscle drive is a constant input, so it does not enter Phi)
        * explicit Euler:      Phi = I + Ah
        * semi-implicit Euler: w+ = w - h M^-1 (K th + C w);  th+ = th + h w+
        The step is numerically stable for the passive dynamics iff the spectral radius of Phi is <= 1 (``margin``; for RK4 this
        is the classical |R(lambda h)| <= 1 for every eigenvalue lambda of A, R(z) = 1 + z + z^2/2 + z^3/6 + z^4/24, i.e. about
        lambda h in [-2.78, 0] on the real axis). Not covered: the feedback loop (gains, delays, held muscle drive across the
        step) and contact switching (base-of-support clipping, friction, joint limits); those are checked by the run-time
        divergence criteria and by the time-step convergence study."""
        n = self.n
        integrator = integrator or self.integrator
        T = np.eye(n) - np.eye(n, k=-1)
        gcc = float(self.cfg["neural"]["cocontraction_gain"])
        M = self.H + np.diag(self.inertia)
        Minv = np.linalg.inv(M)
        K = T.T @ np.diag(self.k_pass * (1.0 + gcc * cc)) @ T
        C = T.T @ np.diag(self.c_pass * (1.0 + 0.5 * gcc * cc)) @ T
        A = np.block([[np.zeros((n, n)), np.eye(n)], [-Minv @ K, -Minv @ C]])
        h = self.h
        Ah = A * h
        I2 = np.eye(2 * n)
        if integrator == "rk4":
            Phi = I2 + Ah + Ah @ Ah / 2 + Ah @ Ah @ Ah / 6 + Ah @ Ah @ Ah @ Ah / 24
        elif integrator == "explicit-euler":
            Phi = I2 + Ah
        else:
            E = np.eye(n)
            Phi = np.block([[E - h * h * Minv @ K, h * (E - h * Minv @ C)], [-h * Minv @ K, E - h * Minv @ C]])
        rho = float(np.max(np.abs(np.linalg.eigvals(Phi))))
        lam = np.linalg.eigvals(A)
        eig_m = np.linalg.eigvalsh(M)
        return {
            "margin": rho,
            "stable": bool(rho <= 1.0 + 1e-9),
            "integrator": integrator,
            "cc": cc,
            "dt": self.dt,
            "substeps": self.substeps,
            "max_abs_lambda_h": float(np.abs(lam).max() * h),
            "fastest_mode_hz": float(np.abs(lam.imag).max() / (2 * math.pi)),
            "mass_matrix_min_eig": float(eig_m[0]),
            "mass_matrix_condition": float(eig_m[-1] / eig_m[0]),
            "scope": f"passive joint dynamics at the upright pose, {integrator}, co-contraction within [0, {cc:.1f}]. A spectral radius of at most 1 "
            "guarantees that the integration of the passive plant does not blow up anywhere in that range (a sufficient condition). It is not "
            "necessary: a refused configuration may still run stably at the co-contraction it actually uses, which is why the run-time divergence "
            "criteria also exist. It does not cover feedback delays, gains or contact switching: a passed configuration can still have an unstable closed loop",
        }

    def enabled(self, lid: str) -> bool:
        ln = self.lines.get(lid)
        return bool(ln and ln["enabled"])

    def delay_steps(self, lid: str) -> int:
        ln = self.lines.get(lid)
        return max(0, int(round(ln["timescale_s"] / self.dt))) if ln else 0


@dataclass
class Run:
    """The reference record of a batched run: full-rate, internal to the simulation (not an observation)."""

    cfg: dict[str, Any]
    seeds: list[int]
    t: np.ndarray
    dt: float
    arrays: dict[str, np.ndarray]
    line_ids: list[str]
    fell: np.ndarray  # physical fall (segment angle or COM beyond the recoverable range)
    fall_time: np.ndarray
    diverged: np.ndarray  # numerical divergence (non-finite, rate or torque beyond the criteria) — never a fall
    diverge_time: np.ndarray
    slow_end: dict[str, np.ndarray]
    events: dict[str, Any]

    def __getitem__(self, k: str) -> np.ndarray:
        return self.arrays[k]


class Sim:
    """A batch of S bodies advancing together. ``advance(k)`` takes k steps; the record accumulates in ``self.rec``."""

    def __init__(
        self,
        cfg: dict[str, Any],
        seeds: list[int],
        horizon_steps: int | None = None,
        slow_state: dict[str, Any] | None = None,
        record: bool = True,
        noise_stream: int = 0,
        enforce_stability: bool = True,
    ):
        self.record = record
        self.enforce_stability = (
            enforce_stability  # False only for the study that checks the a-priori criterion against real runs
        )
        self.set_config(cfg)
        p = self.p
        self.seeds = list(seeds)
        s = self.S = len(self.seeds)
        n = p.n
        self.T = horizon_steps if horizon_steps is not None else int(round(cfg["task"]["horizon"] / p.dt))
        T = self.T
        # noise: one stream per seed, drawn up front; body noise stream 0, never touched by observation
        self.noise_sens = np.empty((s, T, 2 * n + 9))
        self.noise_motor = np.empty((s, T, n))
        self.noise_breath = np.empty((s, T))
        for i, sd in enumerate(self.seeds):
            rng = np.random.default_rng([int(sd), noise_stream])
            self.noise_sens[i] = rng.standard_normal((T, 2 * n + 9))
            self.noise_motor[i] = rng.standard_normal((T, n))
            self.noise_breath[i] = rng.standard_normal(T)
        # state
        lean = float(cfg["task"]["initial_lean"])
        self.theta = np.full((s, n), lean)
        self.omega = np.zeros((s, n))
        self.act = np.zeros((s, n, 2))
        self.energy = np.full(s, float(cfg["internal"]["energy0"]))
        self.fatigue = np.zeros(s)
        self.kc = np.ones(s)
        self.phi = np.zeros(s)
        self.core = np.full(s, 0.2)
        self.hand = np.zeros(s)
        self.sediment = np.zeros(s)
        self.err_f = np.zeros(s)
        self.prev_xref = np.zeros(s)
        self.alive = np.ones(s, dtype=bool)
        self.fall_t = np.full(s, np.inf)
        self.diverged = np.zeros(s, dtype=bool)
        self.div_t = np.full(s, np.inf)
        self.slip_timer = np.zeros(s)
        self.cop = np.zeros(s)
        self.t_det = {1: np.full(s, np.inf), 2: np.full(s, np.inf)}
        self.hold = np.zeros((s, len(p.line_ids)))
        if slow_state:
            self._load_slow(slow_state)
        self.step_i = 0
        L = len(p.line_ids)
        K = 2 * n + 9
        self.K = K
        self.hist_len = T + 2
        self.Y = np.zeros((s, self.hist_len, K))  # true quantities, the delay buffer for sensing
        self.U = np.zeros((s, self.hist_len, L, n))  # command contributions per line, the delay buffer for motor latency
        self.rec: dict[str, np.ndarray] = {}
        if record:
            self._alloc()

    # ---------------------------------------------------------------------------------------- configuration
    def set_config(self, cfg: dict[str, Any]) -> None:
        """(Re)derive parameters. Live edits (interventions in a running session) go through here; array shapes (links,
        joints, lines) must not change."""
        self.cfg = cfg
        self.p = Params(cfg)
        ns = self.p.numeric_stability()
        if not ns["stable"] and getattr(self, "enforce_stability", True):
            from .config import ConfigError

            raise ConfigError(
                f"the explicit RK4 step is numerically unstable for the passive joint dynamics (plant step {self.p.h:g} s, "
                f"largest step amplification {ns['margin']:.2f} > 1, fastest mode {ns['fastest_mode_hz']:.1f} Hz, "
                f"checked with co-contraction up to {ns['cc']:g}); lower c_passive / k_passive or the time step. "
                "Such a run would diverge numerically and must not be read as a falling body."
            )
        self.x14 = _x14.effects(cfg)

    def _load_slow(self, st: dict[str, Any]) -> None:
        for key, arr in (
            ("fatigue", self.fatigue),
            ("energy", self.energy),
            ("kc", self.kc),
            ("sediment", self.sediment),
            ("core", self.core),
            ("hand", self.hand),
        ):
            if key in st and st[key] is not None:
                v = np.asarray(st[key], dtype=float)
                arr[:] = v if v.shape == arr.shape else np.resize(v, arr.shape)

    def slow_state(self) -> dict[str, np.ndarray]:
        return {
            "fatigue": self.fatigue.copy(),
            "energy": self.energy.copy(),
            "kc": self.kc.copy(),
            "sediment": self.sediment.copy(),
            "core": self.core.copy(),
            "hand": self.hand.copy(),
        }

    def _alloc(self) -> None:
        s, T, n, L = self.S, self.T, self.p.n, len(self.p.line_ids)
        r = self.rec
        for k in ("theta", "omega", "q", "tau"):
            r[k] = np.zeros((s, T, n))
        r["act"] = np.zeros((s, T, n, 2))
        for k in (
            "com",
            "vcom",
            "cop",
            "fn",
            "energy",
            "fatigue",
            "cap",
            "phi",
            "xref_true",
            "xref_ctrl",
            "xhat",
            "vhat",
            "kc",
            "sediment",
            "core",
        ):
            r[k] = np.zeros((s, T))
        r["slip"] = np.zeros((s, T), dtype=bool)
        r["alive"] = np.zeros((s, T), dtype=bool)
        r["line_active"] = np.zeros((s, T, L), dtype=bool)
        r["line_u"] = np.zeros((s, T, L, n))
        r["sensed"] = np.zeros((s, T, self.K))
        r["push_force"] = np.zeros((s, T))
        r["cc"] = np.zeros((s, T, n))

    # ---------------------------------------------------------------------------------------- mechanics
    def _accel(
        self,
        theta: np.ndarray,
        omega: np.ndarray,
        tau_act: np.ndarray,
        cc: np.ndarray,
        qgen: np.ndarray,
        toe: np.ndarray,
        heel: np.ndarray,
        fn: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        p = self.p
        n = p.n
        cosd = np.cos(theta[:, :, None] - theta[:, None, :])
        sind = np.sin(theta[:, :, None] - theta[:, None, :])
        M = p.H[None] * cosd
        idx = np.arange(n)
        M[:, idx, idx] += p.inertia[None]
        cor = (p.H[None] * sind * (omega**2)[:, None, :]).sum(axis=2)
        grav = p.g * p.Sg[None] * np.sin(theta)
        q = np.concatenate([theta[:, :1], np.diff(theta, axis=1)], axis=1)
        qd = np.concatenate([omega[:, :1], np.diff(omega, axis=1)], axis=1)
        gcc = self.cfg["neural"]["cocontraction_gain"]
        stiff = 1.0 + gcc * cc
        tau_pass = -p.k_pass[None] * stiff * q - p.c_pass[None] * (1.0 + 0.5 * gcc * cc) * qd
        over = np.abs(q) - p.q_range[None]
        tau_pass += np.where(over > 0, -2500.0 * np.sign(q) * over, 0.0)
        tau = tau_act + tau_pass
        tau[:, 0] = np.clip(tau[:, 0], -fn * toe, fn * heel)  # the foot can only transmit torque within the base of support
        gen = tau - np.concatenate([tau[:, 1:], np.zeros((theta.shape[0], 1))], axis=1) + qgen
        acc = np.linalg.solve(M, (gen - cor + grav)[:, :, None])[:, :, 0]
        return acc, tau

    def _com(self, theta: np.ndarray, omega: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        p = self.p
        xk = np.sin(theta) @ p.coef.T
        vk = (np.cos(theta) * omega) @ p.coef.T
        return (xk @ p.mass) / p.mtot, (vk @ p.mass) / p.mtot

    def _generalised(self, force: np.ndarray, link: int, frac: float, theta: np.ndarray) -> np.ndarray:
        """Generalised forces of a horizontal force acting on ``link`` at ``frac`` of its length."""
        p = self.p
        coef = np.zeros(p.n)
        coef[:link] = p.length[:link]
        coef[link] = frac * p.length[link]
        return force[:, None] * coef[None] * np.cos(theta)

    # ---------------------------------------------------------------------------------------- one step
    def _step(self) -> None:
        p, cfg = self.p, self.cfg
        i = self.step_i
        dt, n, s = p.dt, p.n, self.S
        t = i * dt
        neural, internal, env, task = cfg["neural"], cfg["internal"], cfg["environment"], cfg["task"]
        x14 = self.x14
        alive = self.alive
        # ---- true quantities (the delay buffer) and the sensory channels
        q = np.concatenate([self.theta[:, :1], np.diff(self.theta, axis=1)], axis=1)
        qd = np.concatenate([self.omega[:, :1], np.diff(self.omega, axis=1)], axis=1)
        xcom, vcom = self._com(self.theta, self.omega)
        cue1 = 1.0 if task["t_cue"] <= t < task["t_cue"] + CUE_PULSE_S else 0.0
        cue2 = 1.0 if task["t_turn"] <= t < task["t_turn"] + CUE_PULSE_S else 0.0
        fn = p.mtot * p.g
        y = np.concatenate(
            [
                q,
                qd,
                self.theta[:, p.trunk : p.trunk + 1],
                self.omega[:, p.head : p.head + 1],
                xcom[:, None],
                vcom[:, None],
                self.cop[:, None],
                np.full((s, 1), fn),
                np.full((s, 1), cue1),
                np.full((s, 1), cue2),
            ],
            axis=1,
        )
        # K = 2n + 8 used; one spare column keeps the width at 2n + 9 (noise has one more column than channels)
        self.Y[:, i, : y.shape[1]] = y
        sens = cfg["sensors"]
        nz = self.noise_sens[:, i]

        def read(lid: str, cols: slice, noise_sd: np.ndarray | float, noise_cols: slice, gain: float = 1.0) -> np.ndarray:
            if not p.enabled(lid):
                return np.zeros((s, cols.stop - cols.start))
            j = max(0, i - p.delay_steps(lid))
            return gain * self.Y[:, j, cols] + nz[:, noise_cols] * noise_sd

        apparatus = cfg.get("apparatus") or {}
        nadd = float(apparatus.get("noise_add", 0.0))
        pr = sens["proprio"]
        q_hat = read("sens.proprio", slice(0, n), pr["noise"] + nadd, slice(0, n), pr["gain"])
        qd_hat = read("sens.proprio", slice(n, 2 * n), 6 * (pr["noise"] + nadd), slice(n, 2 * n), pr["gain"])
        ve = sens["vestibular"]
        tilt_hat = read("sens.vestibular", slice(2 * n, 2 * n + 1), ve["noise"] + nadd, slice(2 * n, 2 * n + 1), ve["gain"])
        head_rate_hat = read(
            "sens.vestibular", slice(2 * n + 1, 2 * n + 2), 5 * (ve["noise"] + nadd), slice(2 * n + 1, 2 * n + 2), ve["gain"]
        )
        vi = sens["visual"]
        blocked = any(a <= t <= b for a, b in vi.get("blocked_windows", []))
        vis_ok = p.enabled("sens.visual") and not blocked and vi["gain"] > 0
        x_vis = (
            read("sens.visual", slice(2 * n + 2, 2 * n + 3), vi["noise"] + nadd, slice(2 * n + 2, 2 * n + 3), vi["gain"])
            if vis_ok
            else np.zeros((s, 1))
        )
        ta = sens["tactile"]
        cop_hat = read(
            "sens.tactile",
            slice(2 * n + 4, 2 * n + 5),
            ta["noise"] * (1.0 + env["compliance"]) + nadd,
            slice(2 * n + 4, 2 * n + 5),
            ta["gain"],
        )
        cue_sd = sens["cue"]["noise"]
        cue1_hat = read("sens.cue", slice(2 * n + 6, 2 * n + 7), cue_sd, slice(2 * n + 6, 2 * n + 7))[:, 0]
        cue2_hat = read("sens.cue", slice(2 * n + 7, 2 * n + 8), cue_sd, slice(2 * n + 7, 2 * n + 8))[:, 0]
        for k, ch, t_on in ((1, cue1_hat, task["t_cue"]), (2, cue2_hat, task["t_turn"])):
            hit = np.isinf(self.t_det[k]) & (ch > 0.5) & (t >= t_on)
            self.t_det[k] = np.where(hit, t, self.t_det[k])
        # ---- estimates the controller works with (fusion of whatever channels exist)
        th_hat = np.cumsum(q_hat, axis=1)
        w_hat = np.cumsum(qd_hat, axis=1)
        x_p = ((np.sin(th_hat) @ p.coef.T) @ p.mass) / p.mtot
        v_p = (((np.cos(th_hat) * w_hat) @ p.coef.T) @ p.mass) / p.mtot
        x_v = p.h_com * np.sin(tilt_hat[:, 0]) * 0.55
        v_v = p.h_com * head_rate_hat[:, 0] * 0.55
        wp = neural["proprio_weight"] if p.enabled("sens.proprio") else 0.0
        wv = neural["vestibular_weight"] if p.enabled("sens.vestibular") else 0.0
        wvis = neural["visual_weight"] if vis_ok else 0.0
        wsum = max(wp + wv + wvis, 1e-9)
        xhat = (wp * x_p + wv * x_v + wvis * x_vis[:, 0]) / wsum
        vw = max(wp + wv, 1e-9)
        vhat = (wp * v_p + wv * v_v) / vw
        # ---- reference the controller works towards (after it has perceived the cues)
        x_true = self._xref(t, np.full(s, task["t_cue"]), np.full(s, task["t_turn"]), endpoint=False)
        strategy_endpoint = neural["strategy"] == "endpoint" and not x14["whole_body"]
        wind = neural["windup_s"] * (0.0 if x14["whole_body"] else 1.0)
        ramp_scale = x14["ramp_scale"]
        xref_ctrl = self._xref(t, self.t_det[1], self.t_det[2], endpoint=strategy_endpoint, windup=wind, ramp_scale=ramp_scale)
        err = xhat - xref_ctrl
        # ---- operation lines: ignition, hold, resource (prev_xref is read by the feed-forward line below)
        lid = p.line_ids
        L = len(lid)
        energy_ok = self.energy > 0.02
        cond = np.zeros((s, L), dtype=bool)

        def li(name: str) -> int:
            return lid.index(name) if name in lid else -1

        def ign(name: str, value: np.ndarray) -> None:
            j = li(name)
            if j >= 0 and p.lines[name]["enabled"]:
                cond[:, j] = np.abs(value) > p.lines[name]["ignition"]["threshold"]

        ign("sens.proprio", np.max(np.abs(qd_hat), axis=1))
        ign("sens.vestibular", head_rate_hat[:, 0])
        ign("sens.visual", (x_vis[:, 0] if vis_ok else np.zeros(s)))
        cop_prev = self.Y[:, max(0, i - 10), 2 * n + 4]
        ign("sens.tactile", cop_hat[:, 0] - cop_prev)
        ign("sens.cue", np.maximum(cue1_hat, cue2_hat))
        ign("neural.reflex", np.max(np.abs(qd_hat), axis=1))
        cue_active = (t >= self.t_det[1]) & (t < self.t_det[2] + task["ramp_s"] + 1.0)
        j = li("neural.central.ankle")
        if j >= 0 and p.lines["neural.central.ankle"]["enabled"]:
            thr = p.lines["neural.central.ankle"]["ignition"]["threshold"]
            cond[:, j] = (np.abs(err) > thr) | cue_active | (np.abs(vhat) > 0.02)
        ign("neural.central.hip", err)
        j = li("neural.central.cue")
        if j >= 0 and p.lines["neural.central.cue"]["enabled"]:
            cond[:, j] = np.isfinite(self.t_det[1]) & (t >= self.t_det[1]) & (t < self.t_det[1] + 2.0)
        for name in ("mech.passive", "core.tonic", "breath.cycle", "metabolic.supply", "adapt.gain"):
            j = li(name)
            if j >= 0 and p.lines[name]["enabled"]:
                cond[:, j] = True
        # resource: lines with a cost cannot ignite without energy
        cost = np.array([p.lines[x]["resource"]["cost_per_s"] for x in lid])
        costly = cost > 0
        blocked_by_energy = cond & costly[None] & (~energy_ok)[:, None]
        cond &= ~blocked_by_energy
        self.hold = np.where(cond, np.array([p.lines[x]["ignition"]["hold_s"] for x in lid])[None], self.hold - dt)
        active = (cond | (self.hold > 0)) & np.array([p.lines[x]["enabled"] for x in lid])[None]
        active &= alive[:, None]
        # ---- commands (net drive per joint, normalised to [-1, 1]) per line
        kc = self.kc
        contrib = np.zeros((s, L, n))
        a_idx = 0
        u_ankle = -(neural["gain_ankle_p"] * err + neural["gain_ankle_d"] * vhat) * kc
        u_ankle += -neural["gain_cop"] * (cop_hat[:, 0] - x_p) * kc
        # static gravity compensation: the ankle torque that holds the estimated COM offset (a controller without it would
        # settle with a steady-state lean); it uses the same sensed estimate, so it is subject to the same delays
        u_ankle += -neural["gravity_comp"] * p.mtot * p.g * xhat / max(p.tau_max[0], 1e-9)
        # feed-forward of the static torque that holds the reference position (what the sensed-position term above cannot supply)
        u_ankle += -neural.get("gravity_ff", 0.0) * p.mtot * p.g * xref_ctrl / max(p.tau_max[0], 1e-9)
        j = li("neural.central.ankle")
        if j >= 0:
            contrib[:, j, a_idx] = np.where(active[:, j], u_ankle, 0.0)
        hi = min(2, n - 1)
        u_hip = -(neural["gain_hip_p"] * err + neural["gain_hip_d"] * vhat) * kc
        j = li("neural.central.hip")
        if j >= 0:
            contrib[:, j, hi] = np.where(active[:, j], u_hip, 0.0)
        j = li("neural.reflex")
        if j >= 0:
            contrib[:, j, :] = np.where(
                active[:, j][:, None], -(neural["gain_reflex_p"] * q_hat + neural["gain_reflex_d"] * qd_hat), 0.0
            )
            contrib[:, j, 0] = 0.0  # the ankle is governed by the central line; the reflex stiffens the other joints
        j = li("neural.central.cue")
        if j >= 0:
            vref = (xref_ctrl - self.prev_xref) / dt
            ff = neural["gain_cue_ff"] * neural["gain_ankle_d"] * vref * kc
            contrib[:, j, 0] = np.where(active[:, j], ff, 0.0)
        # ---- optional Xeno-14 rule lines (experimental conditions; see xeno14.py)
        extra = _x14.drive(
            self,
            x14,
            t,
            i,
            dict(
                xhat=xhat,
                vhat=vhat,
                tilt=tilt_hat[:, 0],
                q_hat=q_hat,
                qd_hat=qd_hat,
                cop_hat=cop_hat[:, 0],
                err=err,
                xref=xref_ctrl,
                head_rate=head_rate_hat[:, 0],
            ),
        )
        for name, (xu, xon) in extra["lines"].items():
            j = li(name)
            if j >= 0:
                on = (
                    xon & alive & (energy_ok | ~costly[j]) & bool(p.lines[name]["enabled"])
                )  # a switched-off line contributes nothing
                contrib[:, j, :] = np.where(on[:, None], xu, 0.0)
                active[:, j] = on
        # breath: slow modulation of trunk / neck drive, and a small COM sway
        j = li("breath.cycle")
        period = max(1.0, float(internal["breath_period"]) * 1.0)
        if j >= 0 and p.lines["breath.cycle"]["enabled"]:
            period = max(1.0, p.lines["breath.cycle"]["timescale_s"])
            br = internal["breath_amp"] * np.sin(self.phi)
            contrib[:, j, hi] = br
            if n > 3:
                contrib[:, j, n - 1] = 0.5 * br
        # ---- apply each line's latency (command buffer), sum, add motor noise
        self.U[:, i] = contrib
        applied = np.zeros((s, L, n))
        for jj, name in enumerate(lid):
            d = 0 if name in ("breath.cycle",) else p.delay_steps(name) if name.startswith("neural") else 0
            d += int(round(float(apparatus.get("delay_add", 0.0)) / dt)) if name.startswith("neural.central") else 0
            if d == 0:
                applied[:, jj] = contrib[:, jj]
            else:
                applied[:, jj] = self.U[:, max(0, i - d), jj] if i - d >= 0 else 0.0
        net = applied.sum(axis=1)
        net += self.noise_motor[:, i] * (neural["motor_noise"] * x14["motor_noise_scale"])
        # ---- resources: capacity from fatigue and energy; split when limited
        cap_f = 1.0 - (1.0 - internal["capacity_floor"]) * self.fatigue if internal["resources_enabled"] else np.ones(s)
        e_ratio = np.clip(self.energy / max(internal["energy_floor"], 1e-6), 0.0, 1.0)
        cap = cap_f * (0.3 + 0.7 * e_ratio) if internal["resources_enabled"] else np.ones(s)
        net = np.clip(net, -1.0, 1.0)
        # ---- co-contraction (tonic line, core tension, tensegrity, breathing) and muscle activation
        cc = np.zeros((s, n))
        j = li("core.tonic")
        if j >= 0 and active[:, j].any():
            cc += neural["cocontraction_base"] * np.array([0.5, 1.0, 1.0, 0.3] + [0.5] * max(0, n - 4))[:n][None]
        cc += x14["core_cc"] * self.core[:, None] * np.array([0.3, 1.0, 1.0, 0.2] + [0.3] * max(0, n - 4))[:n][None]
        cc += extra["cc"]
        if x14["tensegrity"] > 0:
            cc = cc + x14["tensegrity"] * (cc.mean(axis=1, keepdims=True) - cc)
        cc = np.clip(cc, 0.0, 0.9)
        a_e_cmd = np.clip(cc + np.maximum(net, 0.0), 0.0, 1.0)
        a_f_cmd = np.clip(cc + np.maximum(-net, 0.0), 0.0, 1.0)
        cmd = np.stack([a_e_cmd, a_f_cmd], axis=2)
        rise = np.where(cmd > self.act, p.act_rise[None, :, None], p.act_fall[None, :, None])
        self.act = self.act + dt * (cmd - self.act) / rise
        tau_act = p.tau_max[None] * cap[:, None] * (self.act[:, :, 0] - self.act[:, :, 1])
        # ---- environment: support, friction, pushes, handrail
        toe0, heel0 = cfg["foot"]["toe"], cfg["foot"]["heel"]
        comp = env["compliance"]
        scale = (1.0 - 0.35 * comp) * x14["support_scale"]
        led = env.get("ledge")
        toe_scale = led["toe_scale"] if led and led["t0"] <= t <= led["t1"] else 1.0
        toe = np.full(s, toe0 * scale * toe_scale)
        heel = np.full(s, heel0 * scale)
        slipping = self.slip_timer > 0
        toe = np.where(slipping, toe * 0.5, toe)
        heel = np.where(slipping, heel * 0.5, heel)
        force = np.zeros(s)
        qgen = np.zeros((s, n))
        for push in env.get("pushes", []):
            if push["t"] <= t < push["t"] + push["dur"]:
                force = force + push["force"]
                qgen = qgen + self._generalised(
                    np.full(s, float(push["force"])), min(int(push["link"]), n - 1), float(push["point_frac"]), self.theta
                )
        hr = env.get("handrail")
        if hr and hr["t0"] <= t <= hr["t1"]:
            ptx = self._attach_x(self.theta, hr["height_frac"])
            ptv = self._attach_v(self.theta, self.omega, hr["height_frac"])
            fr = -hr["k"] * np.maximum(ptx - hr["x"], 0.0) - np.where(ptx > hr["x"], hr["c"] * ptv, 0.0)
            qgen = qgen + self._generalised(fr, self.trunk_idx(), hr["height_frac"], self.theta)
        # ---- RK4 with the muscle drive and the push held over the control step; the plant may be integrated in ``substeps``
        # sub-steps of dt / substeps (the controller still acts once per dt), which only refines the integration
        th, om = self.theta, self.omega
        h = dt / p.substeps
        th_s, om_s = th, om
        for sub in range(p.substeps):
            acc1, tau_s = self._accel(th_s, om_s, tau_act, cc, qgen, toe, heel, fn)
            if sub == 0:
                tau1, acc_first = tau_s, acc1
            if p.integrator == "rk4":
                acc2, _ = self._accel(th_s + 0.5 * h * om_s, om_s + 0.5 * h * acc1, tau_act, cc, qgen, toe, heel, fn)
                acc3, _ = self._accel(
                    th_s + 0.5 * h * (om_s + 0.5 * h * acc1), om_s + 0.5 * h * acc2, tau_act, cc, qgen, toe, heel, fn
                )
                acc4, _ = self._accel(th_s + h * (om_s + 0.5 * h * acc2), om_s + h * acc3, tau_act, cc, qgen, toe, heel, fn)
                th_s = th_s + h * (om_s + h * (acc1 + acc2 + acc3) / 6.0)
                om_s = om_s + h * (acc1 + 2 * acc2 + 2 * acc3 + acc4) / 6.0
            elif p.integrator == "semi-implicit-euler":
                om_s = om_s + h * acc1
                th_s = th_s + h * om_s
            else:  # explicit Euler
                th_s, om_s = th_s + h * om_s, om_s + h * acc1
        th_new, om_new = th_s, om_s
        # friction: the horizontal ground force needed vs the available friction
        fx = p.mtot * self._com_acc(th, om, acc_first)
        slip = (np.abs(fx) > env["friction_mu"] * fn) & alive
        self.slip_timer = np.where(slip, 0.25, np.maximum(self.slip_timer - dt, 0.0))
        # ---- record (state at the start of the step), then update
        if self.record:
            r = self.rec
            r["theta"][:, i] = self.theta
            r["omega"][:, i] = self.omega
            r["q"][:, i] = q
            r["tau"][:, i] = tau1
            r["act"][:, i] = self.act
            r["com"][:, i] = xcom
            r["vcom"][:, i] = vcom
            r["cop"][:, i] = self.cop
            r["fn"][:, i] = fn
            r["energy"][:, i] = self.energy
            r["fatigue"][:, i] = self.fatigue
            r["cap"][:, i] = cap
            r["phi"][:, i] = self.phi
            r["xref_true"][:, i] = x_true
            r["xref_ctrl"][:, i] = xref_ctrl
            r["xhat"][:, i] = xhat
            r["vhat"][:, i] = vhat
            r["kc"][:, i] = self.kc
            r["sediment"][:, i] = self.sediment
            r["core"][:, i] = self.core
            r["slip"][:, i] = slip
            r["alive"][:, i] = alive
            r["line_active"][:, i] = active
            r["line_u"][:, i] = applied
            r["push_force"][:, i] = force
            r["cc"][:, i] = cc
            r["sensed"][:, i, :n] = q_hat
            r["sensed"][:, i, n : 2 * n] = qd_hat
            r["sensed"][:, i, 2 * n] = tilt_hat[:, 0]
            r["sensed"][:, i, 2 * n + 1] = head_rate_hat[:, 0]
            r["sensed"][:, i, 2 * n + 2] = x_vis[:, 0]
            r["sensed"][:, i, 2 * n + 4] = cop_hat[:, 0]
            r["sensed"][:, i, 2 * n + 6] = cue1_hat
            r["sensed"][:, i, 2 * n + 7] = cue2_hat
        self.prev_xref = xref_ctrl.copy()
        self.cop = np.where(alive, -tau1[:, 0] / fn, self.cop)
        bad = (
            ~np.isfinite(th_new).all(axis=1)
            | ~np.isfinite(om_new).all(axis=1)
            | (np.abs(om_new) > DIVERGE_OMEGA).any(axis=1)
            | ((np.abs(tau1) / float(p.tau_max.max())) > DIVERGE_TORQUE).any(axis=1)
        ) & alive
        self.div_t = np.where(bad, (i + 1) * dt, self.div_t)
        self.diverged = self.diverged | bad
        alive = alive & ~bad
        good = alive[:, None]
        self.theta = np.where(good, th_new, self.theta)
        self.omega = np.where(good, om_new, self.omega)
        # internal state
        w = p.tau_max / max(p.tau_max.sum(), 1e-9)
        level = ((self.act**2).sum(axis=2) * w[None]).sum(axis=1) / 2.0
        act_cost = internal["activation_cost"] * level * 4.0
        line_cost = (active * cost[None]).sum(axis=1)
        if internal["resources_enabled"]:
            self.energy = np.maximum(
                self.energy - dt * (internal["basal_cost"] + act_cost + line_cost) * (1.0 + 0.2 * np.sin(self.phi)), 0.0
            )
            fr = internal["fatigue_rate"] * x14["fatigue_scale"]
            self.fatigue = np.clip(
                self.fatigue + dt * (fr * level * (1 - self.fatigue) - internal["fatigue_recovery"] * self.fatigue * (1 - level)),
                0.0,
                1.0,
            )
        self.phi = self.phi + dt * 2 * math.pi / period * (1.0 + internal["breath_variability"] * self.noise_breath[:, i])
        # slow gain adaptation: error filtered over ~1 s; gain rises when the error stays above target
        ad = cfg["adaptation"]
        if ad["enabled"] and p.enabled("adapt.gain"):
            tau_a = max(p.lines["adapt.gain"]["timescale_s"], 1e-3)
            self.err_f = self.err_f + dt * (np.abs(err) - self.err_f) / 1.0
            drive = np.clip(self.err_f / max(ad["error_target"], 1e-6) - 1.0, -1.0, 2.0)
            self.kc = np.clip(self.kc + dt * ad["eta"] / tau_a * drive * 4.0, ad["gain_min"], ad["gain_max"])
            self.energy = np.maximum(self.energy - dt * ad["cost"] * np.abs(drive), 0.0)
        _x14.slow(self, x14, dt, extra)
        # falls
        xc, _ = self._com(self.theta, self.omega)
        fell = (np.abs(self.theta).max(axis=1) > FALL_ANGLE) | (np.abs(xc) > 2.4 * toe0)
        newly = alive & fell
        self.fall_t = np.where(newly, (i + 1) * dt, self.fall_t)
        self.alive = alive & ~fell
        self.step_i += 1

    # ---------------------------------------------------------------------------------------- helpers
    def trunk_idx(self) -> int:
        return self.p.trunk

    def _attach_x(self, theta: np.ndarray, frac: float) -> np.ndarray:
        p = self.p
        k = self.trunk_idx()
        base = (p.length[:k] * np.sin(theta[:, :k])).sum(axis=1)
        return base + frac * p.length[k] * np.sin(theta[:, k])

    def _attach_v(self, theta: np.ndarray, omega: np.ndarray, frac: float) -> np.ndarray:
        p = self.p
        k = self.trunk_idx()
        base = (p.length[:k] * np.cos(theta[:, :k]) * omega[:, :k]).sum(axis=1)
        return base + frac * p.length[k] * np.cos(theta[:, k]) * omega[:, k]

    def _com_acc(self, theta: np.ndarray, omega: np.ndarray, acc: np.ndarray) -> np.ndarray:
        p = self.p
        ak = (np.cos(theta) * acc - np.sin(theta) * omega**2) @ p.coef.T
        return (ak @ p.mass) / p.mtot

    def _xref(
        self, t: float, t1: np.ndarray, t2: np.ndarray, endpoint: bool, windup: float = 0.0, ramp_scale: float = 1.0
    ) -> np.ndarray:
        """The COM reference as a function of (perceived) cue times: wind-up (endpoint strategy), ramp to the target, ramp to
        the turn position."""
        task = self.cfg["task"]
        ramp = task["ramp_s"] * ramp_scale
        xt, xr = task["x_target"], task["x_turn"]
        base1 = t1 + (windup if endpoint else 0.0)
        s1 = smoothstep((t - base1) / ramp)
        out = xt * s1
        if endpoint and windup > 0:
            u = (t - t1) / windup
            ant = np.where((u >= 0) & (u < 1), -self.cfg["neural"]["windup_frac"] * xt * np.sin(np.pi * np.clip(u, 0, 1)), 0.0)
            out = out + ant
        s2 = smoothstep((t - t2) / ramp)
        out = out + (xr - xt) * s2 * (s1 > 0.99)
        return np.where(np.isfinite(t1), out, 0.0)

    # ---------------------------------------------------------------------------------------- driving
    def advance(self, k: int) -> int:
        """Take up to k steps (fewer at the horizon). Returns the number taken."""
        taken = 0
        while taken < k and self.step_i < self.T:
            self._step()
            taken += 1
        return taken

    def finish(self) -> Run:
        t = np.arange(self.step_i) * self.p.dt
        arrays = {k: v[:, : self.step_i] for k, v in self.rec.items()}
        events = {"cue_detect": {str(k): self.t_det[k].copy() for k in (1, 2)}}
        return Run(
            self.cfg,
            self.seeds,
            t,
            self.p.dt,
            arrays,
            list(self.p.line_ids),
            np.isfinite(self.fall_t),
            self.fall_t.copy(),
            self.diverged.copy(),
            self.div_t.copy(),
            self.slow_state(),
            events,
        )


def simulate(
    cfg: dict[str, Any],
    seeds: list[int],
    slow_state: dict[str, Any] | None = None,
    chunk: int = 0,
    enforce_stability: bool = True,
):
    """Run a batch to the horizon. With ``chunk`` > 0 this is a generator that yields after every ``chunk`` steps (for hosts
    without threads, which advance such generators in time slices); the return value of the generator is the Run."""
    sim = Sim(cfg, seeds, slow_state=slow_state, enforce_stability=enforce_stability)
    if chunk <= 0:
        sim.advance(sim.T)
        return sim.finish()
    return _sliced(sim, chunk)


def _sliced(sim: Sim, chunk: int):
    while sim.step_i < sim.T:
        sim.advance(chunk)
        yield sim.step_i / sim.T
    return sim.finish()


def run_to_end(gen_or_run):
    """Drive a sliced simulation to completion (the desktop path) and return the Run."""
    if isinstance(gen_or_run, Run):
        return gen_or_run
    while True:
        try:
            next(gen_or_run)
        except StopIteration as stop:
            return stop.value
