"""An ordinary optimal-feedback rival for the XB-TRO body (R20, section 18D: "matched rivals").

Why this module exists. Operational Nihilism (R20) 18D asks that a bodily claim be compared with a *substantive* conventional rival that is built BEFORE the preferred result is examined, that is "not a weaker mechanical straw man", that is
allowed to learn and correct under the same available signals, and that is not given a smaller observation stream or a larger rehearsal budget unnoticed. The named conventional rival is the optimal-feedback account of task-relevant
correction (Todorov and Jordan 2002). Dictionary D5 of the Gaisho laboratory asks the same for domain 004 and records that no such rival was built. This is that rival, for this simulated planar body only.

What the rival is. A linear-quadratic regulator with the standard predictor for a known input/measurement delay (Artstein reduction), on the plant linearised NUMERICALLY from the engine's own equations of motion (so it is a correctly specified
ordinary model, not a caricature), acting on the ankle and the hip through the SAME operation lines as the preset's own law (same command latency, same ignition and hold, same energy and fatigue ledger through the muscle activation, same
motor noise, same torque limits and base of support, same slow gain adaptation ``kc`` with the same adaptation cost).

Information matched. It receives exactly the estimates the preset's law receives: the delayed, noisy proprioceptive joint angles and rates, corrected toward the SAME fused centre-of-mass estimate (proprio, vestibular and visual, with the preset's
own weights), and the SAME perceived reference (``xref_ctrl``, which already contains the preset's own cue delay and strategy). It reads nothing from the true state, the cue times of the true task, the push, or the record.

Not tuned. The cost weights follow Bryson's rule (one over the square of the largest acceptable deviation) and are NOT adjusted to any outcome; ``R_SCALE`` variants (x0.3, x1, x3) are reported together as a sensitivity, not selected. The
gains are computed from the configuration, once per run, by a fixed procedure.

What it is granted, stated so that it can be argued about: the true loop delay of the cell (known delay; a variant assumes the preset's NOMINAL delay instead), the nominal passive stiffness, and the plant's mass matrix. What it is NOT: free of cost. Its
activation passes through the preset's activation cost, so the ledger is the same ledger. Its computation is not priced (the ledger cannot price compute): that is a limit, not a claim.

Not a statement about any human, a Gaisho, or XenoBody as practised. It is a controller for a simulated planar body."""

from __future__ import annotations

from typing import Any

import numpy as np

# Bryson's rule: one over the square of the largest acceptable deviation. Fixed here, before any comparison is run.
THETA_MAX = 0.10  # rad, a link angle
OMEGA_MAX = 0.50  # rad/s
U_MAX = 1.0  # normalised drive
R_SCALES = (0.3, 1.0, 3.0)  # reported together, never selected


def expm(m: np.ndarray) -> np.ndarray:
    """Matrix exponential by scaling and squaring of a Taylor series (no SciPy: this must run wherever the engine runs)."""
    norm = float(np.linalg.norm(m, 1))
    k = max(0, int(np.ceil(np.log2(max(norm, 1e-12)))) + 2)
    a = m / (2**k)
    out = np.eye(m.shape[0])
    term = np.eye(m.shape[0])
    for j in range(1, 24):
        term = term @ a / j
        out = out + term
    for _ in range(k):
        out = out @ out
    return out


def dare(a: np.ndarray, b: np.ndarray, q: np.ndarray, r: np.ndarray, iters: int = 20000, tol: float = 1e-11) -> tuple[np.ndarray, np.ndarray]:
    """Discrete algebraic Riccati equation by fixed-point iteration; returns (P, K) with u = -K z."""
    p = q.copy()
    for _ in range(iters):
        bt = b.T @ p
        k = np.linalg.solve(r + bt @ b, bt @ a)
        p_new = q + a.T @ p @ (a - b @ k)
        p_new = 0.5 * (p_new + p_new.T)
        if np.max(np.abs(p_new - p)) < tol * max(1.0, float(np.max(np.abs(p_new)))):
            p = p_new
            break
        p = p_new
    k = np.linalg.solve(r + b.T @ p @ b, b.T @ p @ a)
    return p, k


def linearise(sim: Any) -> dict[str, Any]:
    """The plant of the engine about the upright posture, by finite differences of its own acceleration function. Inputs: the normalised drive of joint 0 (ankle) and of the hip joint."""
    p = sim.p
    cfg = sim.cfg
    n = p.n
    hi = min(2, n - 1)
    gcc = cfg["neural"]["cocontraction_gain"]
    cc = np.zeros(n)
    if any(ln["id"] == "core.tonic" and ln.get("enabled", True) for ln in cfg["lines"]):
        cc = cfg["neural"]["cocontraction_base"] * np.array([0.5, 1.0, 1.0, 0.3] + [0.5] * max(0, n - 4))[:n]
    del gcc
    toe = np.array([cfg["foot"]["toe"]])
    heel = np.array([cfg["foot"]["heel"]])
    fn = p.mtot * p.g
    zero = np.zeros((1, n))

    def acc(theta: np.ndarray, omega: np.ndarray, u: np.ndarray) -> np.ndarray:
        tau = np.zeros((1, n))
        tau[0, 0] = p.tau_max[0] * u[0]
        tau[0, hi] += p.tau_max[hi] * u[1]
        a, _ = sim._accel(theta[None], omega[None], tau, cc[None], zero, toe, heel, fn)
        return a[0]

    eps = 1e-6
    th0, om0, u0 = np.zeros(n), np.zeros(n), np.zeros(2)
    a_th = np.zeros((n, n))
    a_om = np.zeros((n, n))
    b_u = np.zeros((n, 2))
    for j in range(n):
        d = np.zeros(n)
        d[j] = eps
        a_th[:, j] = (acc(th0 + d, om0, u0) - acc(th0 - d, om0, u0)) / (2 * eps)
        a_om[:, j] = (acc(th0, om0 + d, u0) - acc(th0, om0 - d, u0)) / (2 * eps)
    for j in range(2):
        d = np.zeros(2)
        d[j] = eps
        b_u[:, j] = (acc(th0, om0, u0 + d) - acc(th0, om0, u0 - d)) / (2 * eps)
    ac = np.block([[np.zeros((n, n)), np.eye(n)], [a_th, a_om]])
    bc = np.vstack([np.zeros((n, 2)), b_u])
    dt = p.dt
    big = np.zeros((2 * n + 2, 2 * n + 2))
    big[: 2 * n, : 2 * n] = ac * dt
    big[: 2 * n, 2 * n :] = bc * dt
    e = expm(big)
    return {"A": e[: 2 * n, : 2 * n], "B": e[: 2 * n, 2 * n :], "a_th": a_th, "b_u": b_u, "hi": hi, "n": n}


class OrdinaryFeedback:
    """The rival. ``r_scale`` scales the control cost (a reported sensitivity); ``assumed_delay_steps`` is the loop delay the controller believes (None = the true one of the cell)."""

    def __init__(self, r_scale: float = 1.0, assumed_delay_steps: tuple[int, int] | None = None, use_hip: bool = True, inject: bool = True, model_actuator: bool = True):
        self.inject = inject
        self.model_actuator = model_actuator
        self.r_scale = float(r_scale)
        self.assumed = assumed_delay_steps
        self.use_hip = use_hip
        self._ready = False

    # -- one-time construction from the configuration the engine is running (never from outcomes)
    def _build(self, sim: Any) -> None:
        p = sim.p
        lin = linearise(sim)
        n = lin["n"]
        self.n, self.hi = n, lin["hi"]
        A, B = lin["A"], lin["B"]
        q = np.diag([1.0 / THETA_MAX**2] * n + [1.0 / OMEGA_MAX**2] * n)
        # Bryson's rule for the control: the largest acceptable drive is the largest FEASIBLE one. The ankle can only transmit torque inside the base of support, so its feasible share of the ankle
        # actuator is fn * min(toe, heel) / tau_max (an ordinary model of the plant includes this limit); the hip is limited by its actuator (1).
        fn = p.mtot * p.g
        u_ankle_max = min(U_MAX, fn * min(sim.cfg["foot"]["toe"], sim.cfg["foot"]["heel"]) / float(p.tau_max[0]))
        r = np.diag([1.0 / u_ankle_max**2, 1.0 / U_MAX**2]) * self.r_scale
        if not self.use_hip:
            r = np.diag([1.0 / u_ankle_max**2, 1e6])
        _, self.K = dare(A, B, q, r)
        self.A, self.B = A, B
        self.hc = float(p.Sg.sum() / p.mtot)  # height factor of a rigid lean: COM = hc * lean
        # Reference posture and its static drive. A rigid lean is not an equilibrium of a four-link body with two actuated joints, so the reference posture is the equilibrium (per metre of COM reference) that is closest to
        # a rigid lean: solve  a_th theta + b_u u = 0,  c_x . theta = 1  with minimal distance from (1/hc, 0) (a KKT / pseudo-inverse solution). theta_ref = xref * Gt, u_ref = xref * Gu.
        cx = (p.Sg / p.mtot)[None, :]
        cmat = np.block([[lin["a_th"], lin["b_u"]], [cx, np.zeros((1, 2))]])
        y0 = np.concatenate([np.ones(n) / self.hc, np.zeros(2)])
        e = np.zeros(n + 1)
        e[-1] = 1.0
        y = y0 + np.linalg.pinv(cmat) @ (e - cmat @ y0)
        self.Gt, self.G = y[:n], y[n:]
        ids = [ln["id"] for ln in sim.cfg["lines"]]
        self.ja = ids.index("neural.central.ankle")
        self.jh = ids.index("neural.central.hip")
        d_m = p.delay_steps("sens.proprio")
        d_in = p.delay_steps("neural.central.ankle") + int(round(float((sim.cfg.get("apparatus") or {}).get("delay_add", 0.0)) / p.dt))
        if self.assumed is not None:
            d_m, d_in = self.assumed
        if self.model_actuator:  # the muscle activation is a first-order lag; an ordinary model of it is approximated by that much extra input delay
            d_in += int(round(float(np.mean([p.act_rise[0], p.act_rise[self.hi]])) / p.dt))
        self.d = int(d_m + d_in)
        self.Apow = [np.eye(2 * n)]
        for _ in range(self.d):
            self.Apow.append(self.Apow[-1] @ A)
        self.prev_xref: np.ndarray | None = None
        self.dt = p.dt
        self.w = (float(sim.cfg["neural"]["proprio_weight"]) if p.enabled("sens.proprio") else 0.0, float(sim.cfg["neural"]["vestibular_weight"]) if p.enabled("sens.vestibular") else 0.0, float(sim.cfg["neural"]["visual_weight"]))
        self.dch = (p.delay_steps("sens.vestibular"), p.delay_steps("sens.visual"))
        self.xp_hist: list[np.ndarray] = []
        self.bias = [np.zeros(sim.S), np.zeros(sim.S)]
        self._ready = True

    def __call__(self, sim: Any, i: int, sig: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        if not self._ready:
            self._build(sim)
        d = self.d
        hc = self.hc
        xref = sig["xref"]
        # measured joint state. The slower channels (vestibular, visual) enter as a complementary filter: each channel's innovation is taken against the proprioceptive COM of the SAME instant (its own delay), low-passed (0.5 s), and
        # blended with the preset's own channel weights. This uses the same information as the preset's fusion without treating a 0.1 s old visual sample as current.
        self.xp_hist.append(sig["x_p"].copy())
        alpha = self.dt / 0.5
        wp, wv, wvis = self.w
        for c, (x_c, ok) in enumerate(((sig["x_v"], wv > 0.0), (sig["x_vis"], bool(np.all(sig["vis_ok"])) and wvis > 0.0))):
            if not (self.inject and ok):
                continue
            j = len(self.xp_hist) - 1 - self.dch[c]
            ref = self.xp_hist[max(0, j)]
            self.bias[c] = self.bias[c] + alpha * ((x_c - ref) - self.bias[c])
        wsum = max(wp + (wv if self.inject else 0.0) + (wvis if self.inject else 0.0), 1e-9)
        corr = (wv * self.bias[0] + wvis * self.bias[1]) / wsum if self.inject else np.zeros_like(xref)
        th = sig["th_hat"] + (corr / hc)[:, None]
        om = sig["w_hat"]
        z = np.concatenate([th, om], axis=1)
        # reference lean and its rate (the perceived reference only)
        vref = np.zeros_like(xref) if self.prev_xref is None else (xref - self.prev_xref) / self.dt
        self.prev_xref = xref.copy()
        z_ref = np.concatenate([np.outer(xref, self.Gt), np.outer(vref, self.Gt)], axis=1)
        # predictor over the d commands that have not yet shown in the measurement (the commands this controller issued, as gated by the lines)
        zp = z @ self.Apow[d].T
        U = sim.U
        for k in range(d):
            t = i - d + k
            if t < 0:
                continue
            u = np.stack([U[:, t, self.ja, 0], U[:, t, self.jh, self.hi]], axis=1)
            zp = zp + (u @ self.B.T) @ self.Apow[d - 1 - k].T
        zr = z_ref  # the reference is held over the prediction window (the perceived reference moves slowly against it)
        u_fb = -(zp - zr) @ self.K.T
        u_ff = np.outer(xref, self.G)
        kc = sig["kc"]
        u = u_ff + u_fb * kc[:, None]
        return u[:, 0], (u[:, 1] if self.use_hip else np.zeros_like(u[:, 1]))
