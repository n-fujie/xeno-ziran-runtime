"""Local observation models ("cuts") and what they reveal.

An observation model is a signal model applied to the *reference record* of a simulation. It has a range (which body regions it
reaches), a time resolution (sampling rate), a spatial resolution, noise, delay, dropouts and blind windows. Its output is stored
separately from the reference and is all an observer is allowed to use. The names (EEG-like, EMG-like, IMU-like, ...) describe
the *kind of signal*; none is a model of the physiology of that technique, and nothing here is calibrated to real devices.

Observation can also change the body: a sensor has mass, a device has a burden, a feedback display feeds the controller
(``effects``). Those are explicit, user-set, assumed parameters, applied to the body configuration (``apply_apparatus``), so the
difference between "with" and "without" the apparatus can be measured on the reference.
"""

from __future__ import annotations

import copy
import zlib
from typing import Any

import numpy as np

from . import metrics
from .engine import Run

REGIONS = ("shank", "thigh", "trunk", "head", "ground", "neural", "internal")

# kind -> description, defaults, family (what aspect of the body it belongs to), signals it can carry
KINDS: dict[str, dict[str, Any]] = {
    "posture": {"label": "posture observation (marker / camera-like)", "family": "kinematic",
                "defaults": {"sample_hz": 50.0, "noise": 1.0, "delay_s": 0.02, "dropout": 0.0, "spatial": "joint", "joints": "all"},
                "spatial_choices": ["joint", "segment", "pooled"], "noise_unit": "0.012 rad",
                "signals": ["joint angles (or segment angles, or one pooled lean)"],
                "effects": {}},
    "imu": {"label": "IMU-like motion observation", "family": "kinematic",
            "defaults": {"sample_hz": 100.0, "noise": 1.0, "delay_s": 0.0, "dropout": 0.0, "spatial": "segment", "segments": [2]},
            "spatial_choices": ["segment", "pooled"], "noise_unit": "0.01 rad tilt, 0.03 rad/s rate",
            "signals": ["segment tilt and angular rate"], "effects": {"mass_kg": 0.4}},
    "emg": {"label": "EMG-like muscle-activity observation", "family": "muscular",
            "defaults": {"sample_hz": 100.0, "noise": 1.0, "delay_s": 0.0, "dropout": 0.0, "spatial": "joint", "joints": "all"},
            "spatial_choices": ["joint-pair", "joint", "pooled"], "noise_unit": "20 % multiplicative + 0.01 additive",
            "signals": ["activation envelope per joint (total), or extensor and flexor separately, or pooled"],
            "effects": {"mass_kg": 0.05}},
    "contact": {"label": "contact force / plantar pressure observation", "family": "contact",
                "defaults": {"sample_hz": 100.0, "noise": 1.0, "delay_s": 0.0, "dropout": 0.0, "spatial": "detailed"},
                "spatial_choices": ["detailed", "pooled"], "noise_unit": "0.004 m centre of pressure, 6 N force",
                "signals": ["centre of pressure, vertical force, heel and toe pressure (detailed) or force only (pooled)"],
                "effects": {"tactile_gain_scale": 0.95}},
    "respiration": {"label": "respiration observation (chest-motion-like)", "family": "respiratory",
                    "defaults": {"sample_hz": 20.0, "noise": 1.0, "delay_s": 0.05, "dropout": 0.0, "spatial": "chest"},
                    "spatial_choices": ["chest"], "noise_unit": "1.5 mm", "signals": ["chest displacement"],
                    "effects": {"breath_amp_scale": 0.95}},
    "eeg": {"label": "EEG-like neural-activity observation (proxy of the neural lines)", "family": "neural",
            "defaults": {"sample_hz": 100.0, "noise": 1.0, "delay_s": 0.0, "dropout": 0.0, "spatial": "pooled"},
            "spatial_choices": ["pooled", "regional"], "noise_unit": "0.2 of the activity scale",
            "signals": ["command activity of the central and reflex lines (pooled, or motor and sensory regions)"],
            "effects": {"noise_add": 0.0002, "delay_add_s": 0.003}},
    "latency": {"label": "movement-correction latency estimator", "family": "derived",
                "defaults": {"sample_hz": 100.0, "noise": 1.0, "delay_s": 0.0, "dropout": 0.0, "spatial": "derived"},
                "spatial_choices": ["derived"], "noise_unit": "inherits from the streams it uses",
                "signals": ["an estimate of the correction latency from the other streams"], "effects": {}},
    "threshold": {"label": "sensory detection threshold protocol", "family": "derived",
                  "defaults": {"sample_hz": 100.0, "noise": 1.0, "delay_s": 0.0, "dropout": 0.0, "spatial": "derived",
                               "trials": 6, "levels": 10, "report_error": 0.05},
                  "spatial_choices": ["derived"], "noise_unit": "report error probability",
                  "signals": ["push force detected 50 % of the time (report = a response of the central lines)"], "effects": {}},
}

PRESET_CONFIGS = {
    "motion-only": ["posture"],
    "motion+emg+contact": ["posture", "emg", "contact"],
    "full": ["posture", "imu", "emg", "contact", "respiration", "eeg", "latency", "threshold"],
}


class ObservationError(ValueError):
    pass


def model(kind: str, mid: str | None = None, **over: Any) -> dict[str, Any]:
    if kind not in KINDS:
        raise ObservationError(f"unknown observation kind {kind!r}; known: {sorted(KINDS)}")
    spec = KINDS[kind]
    m = {"id": mid or kind, "kind": kind, **copy.deepcopy(spec["defaults"]), "blind_windows": [], "blind_regions": [],
         "effects": copy.deepcopy(spec["effects"]), "effects_on": True}
    m.update(over)
    return m


def config(name: str = "motion-only", kinds: list[str] | None = None, models: list[dict[str, Any]] | None = None,
           window: list[float] | None = None) -> dict[str, Any]:
    ms = models if models is not None else [model(k) for k in (kinds if kinds is not None else PRESET_CONFIGS[name])]
    return {"name": name, "models": ms, "window": window}


def validate(obs: dict[str, Any], n_links: int = 4) -> dict[str, Any]:
    if not isinstance(obs, dict) or not isinstance(obs.get("models"), list):
        raise ObservationError("an observation configuration needs a list of models")
    out = copy.deepcopy(obs)
    ids = set()
    for m in out["models"]:
        kind = m.get("kind")
        if kind not in KINDS:
            raise ObservationError(f"unknown observation kind {kind!r}")
        base = model(kind)
        for k in list(m):
            if k not in base:
                raise ObservationError(f"model {m.get('id', kind)}: unknown setting {k!r}")
        m.update({k: m.get(k, v) for k, v in base.items()})
        if m["id"] in ids:
            raise ObservationError(f"duplicate model id {m['id']!r}")
        ids.add(m["id"])
        if not 0.5 <= float(m["sample_hz"]) <= 1000.0:
            raise ObservationError(f"model {m['id']}: sample_hz must be within 0.5..1000")
        if not 0.0 <= float(m["noise"]) <= 20.0:
            raise ObservationError(f"model {m['id']}: noise must be within 0..20")
        if not 0.0 <= float(m["delay_s"]) <= 2.0:
            raise ObservationError(f"model {m['id']}: delay_s must be within 0..2")
        if not 0.0 <= float(m["dropout"]) <= 0.9:
            raise ObservationError(f"model {m['id']}: dropout must be within 0..0.9")
        if m["spatial"] not in KINDS[kind]["spatial_choices"]:
            raise ObservationError(f"model {m['id']}: spatial must be one of {KINDS[kind]['spatial_choices']}")
        for w in m["blind_windows"]:
            if not (isinstance(w, (list, tuple)) and len(w) == 2 and 0 <= w[0] <= w[1]):
                raise ObservationError(f"model {m['id']}: blind_windows are [start, end] pairs")
        for r in m["blind_regions"]:
            if r not in REGIONS:
                raise ObservationError(f"model {m['id']}: unknown region {r!r}")
        for key in ("segments",):
            if key in m and (not isinstance(m[key], list) or any((not isinstance(i, int)) or not 0 <= i < n_links for i in m[key])):
                raise ObservationError(f"model {m['id']}: {key} must be link indices 0..{n_links - 1}")
        if "joints" in m and m["joints"] != "all" and (not isinstance(m["joints"], list) or any((not isinstance(i, int)) or not 0 <= i < n_links for i in m["joints"])):
            raise ObservationError(f"model {m['id']}: joints must be 'all' or joint indices 0..{n_links - 1}")
    if out.get("window") is not None:
        w = out["window"]
        if not (isinstance(w, (list, tuple)) and len(w) == 2 and 0 <= w[0] < w[1]):
            raise ObservationError("window must be [start, end] seconds")
    return out


# ------------------------------------------------------------------------------------------------ induced change

def apparatus_effects(obs: dict[str, Any]) -> dict[str, Any]:
    """The explicit effects the observation apparatus has on the body (assumed, user-settable parameters)."""
    eff = {"mass_add": {}, "tactile_gain_scale": 1.0, "noise_add": 0.0, "delay_add_s": 0.0, "breath_amp_scale": 1.0,
           "feedback_gain": 0.0}
    for m in obs["models"]:
        if not m.get("effects_on", True):
            continue
        e = m.get("effects", {})
        if e.get("mass_kg"):
            segs = m.get("segments") or ([0] if m["kind"] != "emg" else [0, 1, 2])
            for sgm in segs:
                eff["mass_add"][sgm] = eff["mass_add"].get(sgm, 0.0) + float(e["mass_kg"])
        eff["tactile_gain_scale"] *= float(e.get("tactile_gain_scale", 1.0))
        eff["noise_add"] += float(e.get("noise_add", 0.0))
        eff["delay_add_s"] += float(e.get("delay_add_s", 0.0))
        eff["breath_amp_scale"] *= float(e.get("breath_amp_scale", 1.0))
        eff["feedback_gain"] += float(e.get("feedback_gain", 0.0))
    return eff


def apply_apparatus(cfg: dict[str, Any], obs: dict[str, Any]) -> dict[str, Any]:
    """A copy of the body configuration with the observation apparatus fitted (mass, burden, feedback)."""
    eff = apparatus_effects(obs)
    out = copy.deepcopy(cfg)
    for i, kg in eff["mass_add"].items():
        if 0 <= int(i) < len(out["links"]):
            out["links"][int(i)]["mass"] += kg
    out["sensors"]["tactile"]["gain"] *= eff["tactile_gain_scale"]
    out["internal"]["breath_amp"] *= eff["breath_amp_scale"]
    out["neural"]["gain_cop"] += eff["feedback_gain"]
    out["apparatus"] = {"noise_add": eff["noise_add"], "delay_add": eff["delay_add_s"],
                        "models": [m["id"] for m in obs["models"] if m.get("effects_on", True)]}
    return out


# ------------------------------------------------------------------------------------------------ coverage

def model_regions(m: dict[str, Any], n_links: int, regions: list[str]) -> set[str]:
    """Body regions a model reaches (minus its blind regions)."""
    kind = m["kind"]
    out: set[str] = set()
    if kind == "posture":
        js = range(n_links) if m.get("joints", "all") == "all" else m["joints"]
        for j in js:
            out.add(regions[j])
            if j >= 1:
                out.add(regions[j - 1])
            else:
                out.add("ground")
    elif kind == "imu":
        out |= {regions[i] for i in (m.get("segments") or range(n_links))}
    elif kind == "emg":
        js = range(n_links) if m.get("joints", "all") == "all" else m["joints"]
        for j in js:
            out.add(regions[j])
    elif kind == "contact":
        out |= {"ground"}
    elif kind == "respiration":
        out |= {"trunk", "internal"}
    elif kind == "eeg":
        out |= {"neural"}
    elif kind in ("latency", "threshold"):
        out |= {"neural"} if kind == "threshold" else set()
    return out - set(m.get("blind_regions", []))


def coverage(cfg: dict[str, Any], obs: dict[str, Any]) -> dict[str, Any]:
    """Which regions and which operation lines each model can reach, and what no model reaches."""
    regions = [ln["region"] for ln in cfg["links"]]
    n = len(regions)
    per_model = {m["id"]: sorted(model_regions(m, n, regions)) for m in obs["models"]}
    covered: dict[str, list[str]] = {}
    for mid, rs in per_model.items():
        for r in rs:
            covered.setdefault(r, []).append(mid)
    lines: dict[str, list[str]] = {}
    kinds_present = {m["kind"]: m for m in obs["models"]}
    for ln in cfg["lines"]:
        seen = [m["id"] for m in obs["models"] if m["kind"] in ln.get("observable_by", [])]
        lines[ln["id"]] = seen
    all_regions = [*dict.fromkeys(regions), "ground", "neural", "internal"]
    return {"models": per_model, "regions": {r: covered.get(r, []) for r in all_regions},
            "unobserved_regions": [r for r in all_regions if not covered.get(r)],
            "lines": lines, "unobserved_lines": [lid for lid, ms in lines.items() if not ms], "kinds": sorted(kinds_present)}


# ------------------------------------------------------------------------------------------------ signals

def _rng(seed: int, m: dict[str, Any]) -> np.random.Generator:
    return np.random.default_rng([int(seed), 1, zlib.crc32(m["id"].encode()) & 0x7FFFFFFF])


def _sample_index(T: int, dt: float, m: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    step = max(1, int(round(1.0 / (float(m["sample_hz"]) * dt))))
    si = np.arange(0, T, step)
    sd = np.maximum(si - int(round(float(m["delay_s"]) / dt)), 0)
    return si, sd


def _moving_avg(x: np.ndarray, w: int) -> np.ndarray:
    if w <= 1:
        return x
    c = np.cumsum(np.pad(x, [(0, 0), (w, 0)] + [(0, 0)] * (x.ndim - 2)), axis=1)
    return (c[:, w:] - c[:, :-w]) / w


def observe(run: Run, obs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Apply every observation model to the run's reference record. Returns, per model id,
    ``{"t": sample times (Ns,), "x": values (S, Ns, C) with NaN where a sample is missing or blind, "channels": [...]}``.
    The result depends only on the reference record, the model settings and the seeds; it never feeds back into the body."""
    dt = run.dt
    T = run["com"].shape[1]
    S = run["com"].shape[0]
    cfg = run.cfg
    n = run["theta"].shape[2]
    trunk = min(2, n - 1)
    out: dict[str, dict[str, Any]] = {}
    window = obs.get("window")
    for m in obs["models"]:
        kind = m["kind"]
        if kind in ("latency", "threshold"):
            continue
        si, sd = _sample_index(T, dt, m)
        t = si * dt
        nz = float(m["noise"])
        rngs = [_rng(sd_, m) for sd_ in run.seeds]
        blind = np.zeros(len(si), dtype=bool)
        for a, b in m.get("blind_windows", []):
            blind |= (t >= a) & (t <= b)
        if window is not None:
            blind |= (t < window[0]) | (t > window[1])
        if kind == "posture":
            joints = list(range(n)) if m.get("joints", "all") == "all" else list(m["joints"])
            if m["spatial"] == "joint":
                x = run["q"][:, :, joints]
                ch = [f"q:{cfg['joints'][j]['id']}" for j in joints]
            elif m["spatial"] == "segment":
                x = run["theta"][:, :, joints]
                ch = [f"theta:{cfg['links'][j]['id']}" for j in joints]
            else:
                x = np.abs(run["theta"][:, :, trunk])[:, :, None]
                ch = ["lean:pooled"]
            x = x[:, sd]
            sd_noise = 0.012 * nz
        elif kind == "imu":
            segs = list(m.get("segments") or [trunk])
            if m["spatial"] == "pooled":
                tilt = run["theta"][:, :, segs].mean(axis=2, keepdims=True)
                rate = run["omega"][:, :, segs].mean(axis=2, keepdims=True)
                ch = ["tilt:pooled", "rate:pooled"]
            else:
                tilt, rate = run["theta"][:, :, segs], run["omega"][:, :, segs]
                ch = [f"{k}:{cfg['links'][j]['id']}" for j in segs for k in ("tilt", "rate")]
            x = np.concatenate([tilt, rate], axis=2) if m["spatial"] == "pooled" else \
                np.stack([v for pair in zip(np.moveaxis(tilt, 2, 0), np.moveaxis(rate, 2, 0), strict=True) for v in pair], axis=2)
            x = x[:, sd]
            sd_noise = np.tile([0.01, 0.03], x.shape[2] // 2)[None, None, :] * nz
        elif kind == "emg":
            joints = list(range(n)) if m.get("joints", "all") == "all" else list(m["joints"])
            act = _moving_avg(run["act"], 5)
            if act.shape[1] < T:
                act = np.concatenate([act, np.repeat(act[:, -1:], T - act.shape[1], axis=1)], axis=1)
            if m["spatial"] == "joint-pair":
                x = np.concatenate([act[:, :, joints, 0], act[:, :, joints, 1]], axis=2)
                ch = [f"emg-ext:{cfg['joints'][j]['id']}" for j in joints] + [f"emg-flex:{cfg['joints'][j]['id']}" for j in joints]
            elif m["spatial"] == "joint":
                tot = act.sum(axis=3)
                x = tot[:, :, joints] + 0.15 * (np.roll(tot, 1, axis=2) + np.roll(tot, -1, axis=2))[:, :, joints]
                ch = [f"emg:{cfg['joints'][j]['id']}" for j in joints]
            else:
                x = act.sum(axis=(2, 3))[:, :, None]
                ch = ["emg:pooled"]
            x = x[:, sd]
            sd_noise = 0.01 * nz
        elif kind == "contact":
            cop, fn = run["cop"], run["fn"]
            toe, heel = cfg["foot"]["toe"], cfg["foot"]["heel"]
            w_toe = np.clip((cop + heel) / (toe + heel), 0, 1)
            if m["spatial"] == "pooled":
                x = fn[:, :, None]
                ch = ["fn"]
                sd_noise = 6.0 * nz
            else:
                x = np.stack([cop, fn, fn * (1 - w_toe), fn * w_toe], axis=2)
                ch = ["cop", "fn", "p-heel", "p-toe"]
                sd_noise = np.array([0.004, 6.0, 6.0, 6.0])[None, None, :] * nz
            x = x[:, sd]
        elif kind == "respiration":
            chest = 0.01 * np.sin(run["phi"]) * (1.0 if cfg["lines"][[ln["id"] for ln in cfg["lines"]].index("breath.cycle")]["enabled"] else 0.0) \
                + 0.12 * run["theta"][:, :, trunk]
            x = chest[:, :, None][:, sd]
            ch = ["chest"]
            sd_noise = 0.0015 * nz
        else:  # eeg
            ids = run.line_ids

            def mag(name: str) -> np.ndarray:
                return np.abs(run["line_u"][:, :, ids.index(name)]).sum(axis=2) if name in ids else np.zeros((S, T))

            motor = mag("neural.central.ankle") + mag("neural.central.hip") + mag("neural.central.cue") + 0.5 * mag("neural.reflex")
            sensory = sum((run["line_active"][:, :, ids.index(nm)].astype(float) for nm in ids if nm.startswith("sens.")), np.zeros((S, T)))
            w = 8
            motor = _moving_avg(motor, w)
            sensory = _moving_avg(sensory, w) / 4.0
            if motor.shape[1] < T:
                motor = np.concatenate([motor, np.repeat(motor[:, -1:], T - motor.shape[1], axis=1)], axis=1)
                sensory = np.concatenate([sensory, np.repeat(sensory[:, -1:], T - sensory.shape[1], axis=1)], axis=1)
            if m["spatial"] == "regional":
                x = np.stack([motor, sensory], axis=2)
                ch = ["neural:motor", "neural:sensory"]
            else:
                x = (motor + sensory)[:, :, None]
                ch = ["neural:pooled"]
            x = x[:, sd]
            sd_noise = 0.2 * nz
        noise = np.empty_like(x)
        for i in range(S):
            noise[i] = rngs[i].standard_normal(x.shape[1:])
            if kind == "emg":
                noise[i] = noise[i]
        xn = x + noise * sd_noise
        if kind == "emg":
            mult = np.empty_like(x)
            for i in range(S):
                mult[i] = rngs[i].standard_normal(x.shape[1:])
            xn = np.abs(x * (1.0 + 0.2 * nz * mult) + noise * sd_noise)
        if kind == "eeg":  # temporally coloured noise
            col = xn.copy()
            for k in range(1, xn.shape[1]):
                col[:, k] = x[:, k] + (col[:, k - 1] - x[:, k - 1]) * 0.8 + noise[:, k] * sd_noise * 0.6
            xn = col
        drop = np.zeros((S, len(si)), dtype=bool)
        if float(m["dropout"]) > 0:
            for i in range(S):
                drop[i] = rngs[i].random(len(si)) < float(m["dropout"])
        xn = np.where((drop | blind[None])[:, :, None], np.nan, xn)
        out[m["id"]] = {"t": t, "x": xn, "channels": ch, "kind": kind, "sample_hz": float(m["sample_hz"]),
                        "delay_s": float(m["delay_s"]), "spatial": m["spatial"], "model": m}
    return out


# ------------------------------------------------------------------------------------------------ features

def _first_dev(t: np.ndarray, x: np.ndarray, t0: float, thr_sd: float = 4.0, base: float = 0.4, t1: float | None = None,
               direction: int = 0, min_thr: float = 0.0) -> np.ndarray:
    """From a sampled signal (S, Ns): seconds from t0 until it deviates from its pre-t0 mean by more than ``thr_sd`` baseline
    standard deviations (or ``min_thr``) for two consecutive samples. NaN if no deviation or too few baseline samples."""
    S = x.shape[0]
    out = np.full(S, np.nan)
    pre = (t >= t0 - base) & (t < t0)
    post = (t >= t0) & ((t <= t1) if t1 is not None else True)
    if pre.sum() < 4 or post.sum() < 2:
        return out
    for i in range(S):
        b = x[i, pre]
        b = b[np.isfinite(b)]
        if len(b) < 4:
            continue
        thr = max(thr_sd * b.std(ddof=1), min_thr)
        dev = x[i, post] - b.mean()
        hit = (np.abs(dev) > thr) if direction == 0 else (direction * dev > thr)
        hit = np.where(np.isfinite(dev), hit, False)
        for k in range(len(hit) - 1):
            if hit[k] and hit[k + 1]:
                out[i] = t[post][k] - t0
                break
    return out


def _forward_com(q: np.ndarray, cfg: dict[str, Any]) -> np.ndarray:
    """COM offset estimated from observed joint angles (S, Ns, n) with the nominal body."""
    length = np.array([ln["length"] for ln in cfg["links"]])
    mass = np.array([ln["mass"] for ln in cfg["links"]])
    d = np.array([ln["com_frac"] * ln["length"] for ln in cfg["links"]])
    n = len(length)
    coef = np.zeros((n, n))
    for k in range(n):
        for i in range(n):
            coef[k, i] = length[i] if i < k else (d[k] if i == k else 0.0)
    th = np.cumsum(q, axis=2)
    return ((np.sin(th) @ coef.T) @ mass) / mass.sum()


def features(run: Run, obs_out: dict[str, dict[str, Any]], obs: dict[str, Any]) -> dict[str, np.ndarray]:
    """Per-seed features computed ONLY from observation streams. A feature is absent when no stream can provide it."""
    cfg = run.cfg
    ev = metrics.events(cfg)
    S = run["com"].shape[0]
    n = run["theta"].shape[2]
    trunk = min(2, n - 1)
    feats: dict[str, np.ndarray] = {}
    q0, q1 = 0.3, max(ev["cue"] - 0.1, 0.4)

    def win(t: np.ndarray, x: np.ndarray, a: float, b: float) -> np.ndarray:
        return x[:, (t >= a) & (t <= b)]

    for mid, o in obs_out.items():
        t, x, ch, kind = o["t"], o["x"], o["channels"], o["kind"]
        if kind == "posture":
            sp = o["spatial"]
            tr = None
            if sp == "joint" and x.shape[2] >= trunk + 1 and all(f"q:{cfg['joints'][j]['id']}" in ch for j in range(trunk + 1)):
                idxs = [ch.index(f"q:{cfg['joints'][j]['id']}") for j in range(trunk + 1)]
                tr = x[:, :, idxs].sum(axis=2)
            elif sp == "segment" and f"theta:{cfg['links'][trunk]['id']}" in ch:
                tr = x[:, :, ch.index(f"theta:{cfg['links'][trunk]['id']}")]
            elif sp == "pooled":
                tr = x[:, :, 0]
            if tr is not None:
                w_ = win(t, tr, q0, q1)
                feats["posture_sway_rms"] = np.array([np.sqrt(np.nanmean((r - np.nanmean(r)) ** 2)) if np.isfinite(r).sum() > 3 else np.nan for r in w_])
                if sp != "pooled":
                    feats["posture_peak_lean"] = np.nanmax(np.abs(tr), axis=1)
            if sp == "joint" and x.shape[2] == n:
                com = _forward_com(np.nan_to_num(x, nan=0.0), cfg)
                com = np.where(np.isfinite(x).all(axis=2), com, np.nan)
                feats["com_excursion_obs"] = np.nanmax(np.abs(com - np.nanmean(win(t, com, 0.3, ev["cue"] - 0.1), axis=1, keepdims=True)), axis=1)
                tgt = cfg["task"]["x_turn"]
                post = (t >= ev["turn"] + cfg["task"]["ramp_s"]) & (t <= ev["turn"] + cfg["task"]["ramp_s"] + 1.2)
                feats["turn_error_obs"] = np.array([np.nanmean(np.abs(c[post] - tgt)) if np.isfinite(c[post]).any() else np.nan for c in com])
                if ev["pushes"]:
                    t_push = ev["pushes"][0]
                    feats["com_onset_push"] = _first_dev(t, com, t_push, thr_sd=4.0, min_thr=0.002)
                    pw = (t >= t_push) & (t <= t_push + 1.5)
                    base = np.nanmean(com[:, (t >= t_push - 0.2) & (t < t_push)], axis=1)
                    feats["peak_dev_obs"] = np.nanmax(np.abs(com[:, pw] - base[:, None]), axis=1)
        elif kind == "imu":
            for j, nm in enumerate(ch):
                if nm.startswith("tilt:") and (nm.endswith(cfg["links"][trunk]["id"]) or nm == "tilt:pooled"):
                    w_ = win(t, x[:, :, j], q0, q1)
                    feats["sway_rms_imu"] = np.array([np.sqrt(np.nanmean((r - np.nanmean(r)) ** 2)) if np.isfinite(r).sum() > 3 else np.nan for r in w_])
                if nm.startswith("rate:") and (nm.endswith(cfg["links"][trunk]["id"]) or nm == "rate:pooled") and ev["pushes"]:
                    feats["imu_onset_push"] = _first_dev(t, x[:, :, j], ev["pushes"][0], thr_sd=4.0, min_thr=0.02)
                    pw = (t >= ev["pushes"][0]) & (t <= ev["pushes"][0] + 1.5)
                    feats["imu_rate_peak"] = np.nanmax(np.abs(x[:, pw, j]), axis=1)
        elif kind == "emg":
            if o["spatial"] == "pooled":
                feats["emg_mean"] = np.nanmean(x[:, :, 0], axis=1)
            elif o["spatial"] == "joint":
                feats["emg_mean"] = np.nanmean(x, axis=(1, 2))
            else:
                k = x.shape[2] // 2
                ext, flex = x[:, :, :k], x[:, :, k:]
                feats["emg_mean"] = np.nanmean(x, axis=(1, 2))
                feats["emg_cc"] = np.nanmean(2 * np.minimum(ext, flex), axis=(1, 2))
            ankle = None
            if o["spatial"] == "joint-pair":
                ia = ch.index(f"emg-ext:{cfg['joints'][0]['id']}") if f"emg-ext:{cfg['joints'][0]['id']}" in ch else None
                ib = ch.index(f"emg-flex:{cfg['joints'][0]['id']}") if f"emg-flex:{cfg['joints'][0]['id']}" in ch else None
                if ia is not None and ib is not None:
                    ankle = x[:, :, ia] - x[:, :, ib]
            elif o["spatial"] == "joint" and f"emg:{cfg['joints'][0]['id']}" in ch:
                ankle = x[:, :, ch.index(f"emg:{cfg['joints'][0]['id']}")]
            if ankle is not None:
                feats["emg_onset_cue"] = _first_dev(t, ankle, ev["cue"], thr_sd=4.0, t1=ev["turn"] - 0.1)
                if ev["pushes"]:
                    feats["emg_onset_push"] = _first_dev(t, ankle, ev["pushes"][0], thr_sd=4.0)
            ext_end = np.nanmean(x[:, (t >= cfg["task"]["horizon"] - 1.0)], axis=(1, 2))
            ext_beg = np.nanmean(x[:, (t >= 0.2) & (t <= 1.0)], axis=(1, 2))
            feats["emg_drift"] = ext_end - ext_beg
        elif kind == "contact":
            if "cop" in ch:
                c = x[:, :, ch.index("cop")]
                feats["cop_rms_obs"] = np.sqrt(np.nanmean(c ** 2, axis=1))
                feats["cop_range_obs"] = np.nanmax(c, axis=1) - np.nanmin(c, axis=1)
                if ev["pushes"]:
                    feats["cop_onset_push"] = _first_dev(t, c, ev["pushes"][0], thr_sd=4.0, min_thr=0.006)
            if "fn" in ch:
                feats["load_mean"] = np.nanmean(x[:, :, ch.index("fn")], axis=1)
        elif kind == "respiration":
            c = x[:, :, 0]
            pp = np.array([np.nanmax(r[(t >= 0.5)]) - np.nanmin(r[(t >= 0.5)]) if np.isfinite(r).sum() > 4 else np.nan for r in c])
            feats["breath_amp_obs"] = pp
        elif kind == "eeg":
            a = x[:, :, 0] if o["spatial"] == "pooled" else x[:, :, 0]
            feats["neural_mean"] = np.nanmean(a, axis=1)
            feats["neural_onset_cue"] = _first_dev(t, a, ev["cue"] + 0.0, thr_sd=4.0, t1=ev["turn"] - 0.1)
            if ev["pushes"]:
                feats["neural_onset_push"] = _first_dev(t, a, ev["pushes"][0], thr_sd=4.0)
    # latency estimator: the best correction-latency estimate the present streams allow
    if any(m["kind"] == "latency" for m in obs["models"]):
        for key in ("emg_onset_push", "cop_onset_push", "imu_onset_push", "com_onset_push"):
            if key in feats:
                feats["corr_latency_est"] = feats[key]
                break
    return feats
