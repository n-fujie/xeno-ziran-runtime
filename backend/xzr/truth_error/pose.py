"""Synthetic head pose and a sensor model for it. Nothing here comes from a real face, camera or landmark model; ``SensorConfig`` declares this implementation's assumptions about how a viewing angle,
occlusion, noise, calibration and a failure change a measurement. (MediaPipe Face Landmarker would be one possible real source of such measurements; it is not used, see docs/TRUTH_ERROR.md.)"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

AXES = ("yaw", "pitch", "roll")
AMPLITUDE = np.array([35.0, 20.0, 12.0])  # degrees: the range the synthetic poses move in
MISSING = ("none", "occlusion", "tracking_lost")  # a failed sensor is NOT in this list: it does not announce itself


def reference_pose(rng: np.random.Generator, n: int, periods: int) -> np.ndarray:
    """Smooth synthetic reference poses (degrees), shape (n, periods, 3): a few sinusoids with seeded phases. It is the 'real state' a sensor measures and is independent of everything an institution cares about."""
    t = np.arange(periods)[None, :, None]
    f = rng.uniform(0.08, 0.35, size=(n, 1, 3))
    ph = rng.uniform(0, 2 * np.pi, size=(n, 1, 3))
    a = AMPLITUDE * rng.uniform(0.4, 1.0, size=(n, 1, 3))
    return a * np.sin(2 * np.pi * f * t / 8.0 + ph) + 0.25 * a * np.sin(2 * np.pi * 2.3 * f * t / 8.0 + 1.7 * ph)


@dataclass(frozen=True)
class SensorConfig:
    """The conditions of one observation: the viewing angle of the sensor (0 = facing the subject), noise, a calibration error per axis, occlusion, tracking failure and an injected failure."""

    view_angle: float = 0.0  # degrees off the subject's frontal axis: oblique views raise noise and lower confidence
    noise_sigma: float = 1.5  # degrees (at a frontal view)
    bias: tuple[float, float, float] = (0.0, 0.0, 0.0)  # calibration offset per axis, degrees
    scale_error: tuple[float, float, float] = (0.0, 0.0, 0.0)  # calibration gain error per axis (0.05 = 5 % too large)
    occlusion_prob: float = 0.0  # per period: the chance that an occlusion starts
    occlusion_length: int = 2
    dropout_prob: float = 0.0  # per period: the chance that tracking is lost
    dropout_length: int = 3
    fail_at: int | None = None  # an injected sensor failure from this period on
    fail_mode: str = "stuck"  # stuck (holds the last value), zero (reads 0), drift (a growing offset)

    def asdict(self) -> dict:
        return asdict(self)


def effective_sigma(cfg: SensorConfig) -> float:
    """Noise grows as the view turns away from frontal (declared assumption: sigma / max(cos(angle), 0.2))."""
    return cfg.noise_sigma / max(float(np.cos(np.radians(cfg.view_angle))), 0.2)


def base_confidence(cfg: SensorConfig) -> float:
    """The sensor's own account of itself (declared): lower for an oblique view and for more noise. It is not a verified probability of being right: a miscalibrated sensor can be confident and wrong."""
    return float(np.clip(np.cos(np.radians(cfg.view_angle)), 0.0, 1.0) * np.exp(-cfg.noise_sigma / 12.0))


class SensorState:
    """The running state of one sensor over n subjects: the remaining length of an occlusion or a tracking loss, and the last good value (for a stuck failure)."""

    def __init__(self, n: int, k: int):
        self.occ = np.zeros(n, dtype=int)
        self.drop = np.zeros(n, dtype=int)
        self.last = np.zeros((n, k))


def measure_period(
    ref_t: np.ndarray,
    cfg: SensorConfig,
    t: int,
    eps: np.ndarray,
    u_occ: np.ndarray,
    u_drop: np.ndarray,
    st: SensorState,
    mult: np.ndarray | float = 1.0,
) -> dict:
    """One period of measurement for every subject at once. ``ref_t`` (n, k) is the reference, ``eps`` (n, k) standard normal draws, ``u_occ`` / ``u_drop`` (n,) uniform draws, ``mult`` (n,) scales the noise and the
    chance of losing the subject (the institution's effect on how a subject is observed, TE06). Returns values (NaN where nothing was obtained), the reason code (0 none, 1 occlusion, 2 tracking lost), the confidence
    and the effective noise. A failed sensor does not mark its periods missing: it reports a value that is wrong."""
    k = ref_t.shape[1]
    scale = 1.0 + np.array(cfg.scale_error[:k])
    sigma = effective_sigma(cfg) * np.asarray(mult)
    val = ref_t * scale + np.array(cfg.bias[:k]) + eps * np.reshape(sigma, (-1, 1))
    m = np.asarray(mult)
    start_occ = (st.occ == 0) & (u_occ < np.clip(cfg.occlusion_prob * m, 0, 1))
    st.occ = np.where(start_occ, cfg.occlusion_length, np.maximum(st.occ - 1, 0) + (start_occ * 0))
    start_drop = (st.drop == 0) & (u_drop < np.clip(cfg.dropout_prob * m, 0, 1))
    st.drop = np.where(start_drop, cfg.dropout_length, np.maximum(st.drop - 1, 0))
    reason = np.where(st.drop > 0, 2, np.where(st.occ > 0, 1, 0))
    if cfg.fail_at is not None and t >= cfg.fail_at:
        if cfg.fail_mode == "zero":
            val = np.zeros_like(val)
        elif cfg.fail_mode == "drift":
            val = val + (t - cfg.fail_at + 1) * 1.5
        else:
            val = st.last if t > cfg.fail_at else val
    else:
        st.last = np.where((reason == 0)[:, None], val, st.last)
    missing = reason > 0
    out = np.where(missing[:, None], np.nan, val)
    conf = np.where(missing, 0.0, base_confidence(cfg))
    return {"values": out, "reason": reason, "confidence": conf, "sigma": sigma}


def measure_series(ref: np.ndarray, cfg: SensorConfig, seed: int) -> dict:
    """Measure the reference pose of ONE subject over time (ref: (periods, 3)): the standalone form used by the 3D pose viewer and the sensor experiments. It is the same per-period function the institution uses."""
    periods = ref.shape[0]
    rng = np.random.default_rng(seed)
    eps, u_occ, u_drop = rng.normal(size=(periods, 1, 3)), rng.uniform(size=(periods, 1)), rng.uniform(size=(periods, 1))
    st = SensorState(1, 3)
    vals, reasons, confs = [], [], []
    for t in range(periods):
        r = measure_period(ref[t : t + 1], cfg, t, eps[t], u_occ[t], u_drop[t], st)
        vals.append(r["values"][0])
        reasons.append(int(r["reason"][0]))
        confs.append(float(r["confidence"][0]))
    return {"values": np.array(vals), "reason": np.array(reasons), "confidence": np.array(confs), "sigma": effective_sigma(cfg)}


def tolerance(axis: int, base: float = 5.0) -> float:
    """The error (degrees) within which a measurement is called correct: 5 degrees on yaw, scaled on the other axes by their range, plus a floor of 3 (a declared convention)."""
    return float(base * AMPLITUDE[axis] / AMPLITUDE[0] + 3.0)
