"""Body configuration: a plain JSON-able dict, its defaults, validation and the interventions that edit it.

The body is *declared*, not hard-wired: a list of links and joints (any number, any nominal values), a list of operation lines
(each with its own time scale, ignition condition, resource dependence and the observation kinds that can in principle see it),
an environment, and a task. Two nominal presets ship with it (a human-like and a machine-like planar body); both are limited
models with nominal numbers, not measured anatomy. Non-human or robotic bodies are further presets of the same schema.

Configuration values are the single source of truth for a run: ``engine.py`` reads only this dict (plus the seed).
"""

from __future__ import annotations

import copy
from typing import Any

# ------------------------------------------------------------------------------------------------ operation lines

LINE_KINDS = ("mechanical", "sensory", "neural", "internal", "environment")
OBSERVATION_KINDS = ("eeg", "emg", "imu", "contact", "respiration", "posture", "latency", "threshold")


def line(lid: str, label: str, kind: str, timescale_s: float, signal: str, threshold: float, hold_s: float,
         cost_per_s: float, observable_by: list[str], enabled: bool = True, note: str = "") -> dict[str, Any]:
    """One operation line. ``timescale_s`` is used by the engine as the line's characteristic delay / period / time constant
    (see docs/XBTRO.md for the meaning per line); ``ignition`` is the condition on the line's own sensed signal; ``resource``
    is what the line costs while active; ``observable_by`` lists the observation kinds that can in principle see it."""
    return {"id": lid, "label": label, "kind": kind, "enabled": enabled, "timescale_s": timescale_s,
            "ignition": {"signal": signal, "threshold": threshold, "hold_s": hold_s},
            "resource": {"pool": "energy", "cost_per_s": cost_per_s}, "observable_by": observable_by, "note": note}


def human_lines() -> list[dict[str, Any]]:
    return [
        line("mech.passive", "viscoelastic joints (passive)", "mechanical", 0.0, "always", 0.0, 0.0, 0.0, ["posture", "imu"],
             note="always on; stiffness and damping per joint"),
        line("sens.proprio", "proprioceptive sensing", "sensory", 0.03, "joint-velocity", 0.05, 0.05, 0.0, ["posture", "emg"],
             note="timescale = sensory delay (s); ignites when a joint velocity exceeds the threshold (rad/s)"),
        line("sens.vestibular", "vestibular / head-motion sensing", "sensory", 0.02, "trunk-tilt-rate", 0.03, 0.05, 0.0,
             ["imu", "eeg"], note="timescale = delay; ignites on trunk tilt rate (rad/s)"),
        line("sens.visual", "visual feedback", "sensory", 0.10, "com-offset", 0.004, 0.10, 0.0, ["posture", "eeg"],
             note="timescale = delay; ignites on a visible COM offset (m); can be blocked"),
        line("sens.tactile", "tactile / contact-pressure sensing", "sensory", 0.04, "cop-shift", 0.004, 0.05, 0.0,
             ["contact", "eeg"], note="timescale = delay; ignites on a centre-of-pressure shift (m)"),
        line("sens.cue", "cue perception", "sensory", 0.12, "cue", 0.5, 0.05, 0.0, ["eeg", "latency"],
             note="timescale = delay; the movement / direction-change cues are sensed through it"),
        line("neural.reflex", "local joint reflex", "neural", 0.04, "joint-velocity", 0.12, 0.08, 0.002,
             ["emg", "latency", "eeg"], note="timescale = loop latency; ignites on a fast sensed joint motion"),
        line("neural.central.ankle", "central balance command (ankle)", "neural", 0.10, "com-offset", 0.003, 0.20, 0.004,
             ["emg", "eeg", "latency"], note="timescale = latency; ignites on a sensed COM offset from the reference"),
        line("neural.central.hip", "central balance command (hip)", "neural", 0.10, "com-offset", 0.020, 0.25, 0.008,
             ["emg", "eeg", "latency"], note="timescale = latency; ignites on a large COM offset"),
        line("neural.central.cue", "central movement command (feed-forward)", "neural", 0.10, "cue", 0.5, 0.30, 0.004,
             ["emg", "eeg", "latency"], note="timescale = latency; ignites on a sensed cue"),
        line("core.tonic", "tonic co-contraction (core)", "internal", 0.0, "always", 0.0, 0.0, 0.003, ["emg"],
             note="baseline co-contraction level; costs energy while on"),
        line("breath.cycle", "breathing cycle", "internal", 4.0, "always", 0.0, 0.0, 0.001, ["respiration", "imu", "emg"],
             note="timescale = period (s); modulates trunk drive and chest motion"),
        line("metabolic.supply", "energy supply / fatigue", "internal", 30.0, "always", 0.0, 0.0, 0.0, [],
             note="timescale = fatigue time constant (s); internal, no observation model sees it directly"),
        line("adapt.gain", "gain adaptation", "internal", 20.0, "always", 0.0, 0.0, 0.0, [],
             note="timescale = adaptation time constant (s); slow retained state"),
    ]


# ------------------------------------------------------------------------------------------------ presets

def human_like() -> dict[str, Any]:
    """A nominal human-like planar body (sagittal plane): shank, thigh, trunk with arms, head. Nominal values."""
    return {
        "name": "human-like-planar", "family": "human-like", "model": "xb-tro/1.0",
        "links": [
            {"id": "shank", "label": "shank + foot", "region": "shank", "length": 0.45, "mass": 6.6, "com_frac": 0.45},
            {"id": "thigh", "label": "thigh", "region": "thigh", "length": 0.45, "mass": 14.0, "com_frac": 0.45},
            {"id": "trunk", "label": "trunk + arms", "region": "trunk", "length": 0.55, "mass": 38.0, "com_frac": 0.50},
            {"id": "head", "label": "head + neck", "region": "head", "length": 0.30, "mass": 4.8, "com_frac": 0.50},
        ],
        "joints": [
            {"id": "ankle", "label": "ankle", "tau_max": 120.0, "k_passive": 720.0, "c_passive": 45.0, "q_range": 0.6,
             "act_rise": 0.04, "act_fall": 0.08},
            {"id": "knee", "label": "knee", "tau_max": 150.0, "k_passive": 700.0, "c_passive": 40.0, "q_range": 0.6,
             "act_rise": 0.04, "act_fall": 0.08},
            {"id": "hip", "label": "hip", "tau_max": 180.0, "k_passive": 420.0, "c_passive": 35.0, "q_range": 0.8,
             "act_rise": 0.04, "act_fall": 0.08},
            {"id": "neck", "label": "neck", "tau_max": 25.0, "k_passive": 45.0, "c_passive": 4.0, "q_range": 0.8,
             "act_rise": 0.03, "act_fall": 0.06},
        ],
        "foot": {"toe": 0.17, "heel": 0.07},
        "environment": {"gravity": 9.81, "friction_mu": 0.8, "compliance": 0.0, "pushes": [], "ledge": None, "handrail": None},
        "sensors": {
            "proprio": {"noise": 0.002, "gain": 1.0},
            "vestibular": {"noise": 0.004, "gain": 1.0},
            "visual": {"noise": 0.004, "gain": 1.0, "blocked_windows": []},
            "tactile": {"noise": 0.003, "gain": 1.0},
            "cue": {"noise": 0.15},
        },
        "neural": {
            "gain_ankle_p": 3.0, "gain_ankle_d": 3.5, "gain_cop": 0.0, "gravity_comp": 0.5, "gravity_ff": -0.4, "gain_hip_p": 1.2, "gain_hip_d": 0.8,
            "gain_reflex_p": 0.6, "gain_reflex_d": 0.05, "gain_cue_ff": 1.0, "motor_noise": 0.01,
            "strategy": "endpoint", "windup_s": 0.25, "windup_frac": 0.35, "visual_weight": 1.0,
            "vestibular_weight": 1.0, "proprio_weight": 2.0, "tactile_weight": 0.6, "cocontraction_base": 0.06,
            "cocontraction_gain": 2.0,
        },
        "internal": {
            "breath_period": 4.0, "breath_amp": 0.015, "breath_variability": 0.05, "energy0": 1.0, "basal_cost": 0.0004,
            "activation_cost": 0.004, "fatigue_rate": 0.020, "fatigue_recovery": 0.012, "capacity_floor": 0.45,
            "energy_floor": 0.30, "resources_enabled": True,
        },
        "adaptation": {"enabled": True, "eta": 0.2, "error_target": 0.003, "gain_min": 0.9, "gain_max": 1.15,
                       "cost": 0.0},
        "task": {"horizon": 8.0, "dt": 0.01, "substeps": 2, "integrator": "rk4", "t_cue": 1.0, "x_target": 0.035, "ramp_s": 0.35, "t_turn": 4.2,
                 "x_turn": -0.020, "initial_lean": 0.0},
        "lines": human_lines(),
        "xeno14": [],
        "slow_state0": None,
    }


def machine_like() -> dict[str, Any]:
    """A nominal machine-like planar body: lighter links, fast stiff actuators, short loop latencies, encoders, a battery in
    place of fatigue, no breathing and no vision. Nominal values, not a model of any particular robot."""
    cfg = human_like()
    cfg.update({"name": "machine-like-planar", "family": "machine-like"})
    cfg["task"]["dt"] = 0.005  # loop latencies of 4-15 ms and stiff joints need a step below the human-like 0.01 s
    cfg["links"] = [
        {"id": "shank", "label": "lower leg + foot plate", "region": "shank", "length": 0.40, "mass": 8.0, "com_frac": 0.40},
        {"id": "thigh", "label": "upper leg", "region": "thigh", "length": 0.40, "mass": 10.0, "com_frac": 0.45},
        {"id": "trunk", "label": "torso + battery", "region": "trunk", "length": 0.50, "mass": 30.0, "com_frac": 0.45},
        {"id": "head", "label": "sensor head", "region": "head", "length": 0.20, "mass": 3.0, "com_frac": 0.50},
    ]
    cfg["joints"] = [
        {"id": "ankle", "label": "ankle actuator", "tau_max": 160.0, "k_passive": 60.0, "c_passive": 6.0, "q_range": 0.6,
         "act_rise": 0.008, "act_fall": 0.010},
        {"id": "knee", "label": "knee actuator", "tau_max": 200.0, "k_passive": 900.0, "c_passive": 10.0, "q_range": 0.6,
         "act_rise": 0.008, "act_fall": 0.010},
        {"id": "hip", "label": "hip actuator", "tau_max": 220.0, "k_passive": 720.0, "c_passive": 12.0, "q_range": 0.8,
         "act_rise": 0.008, "act_fall": 0.010},
        {"id": "neck", "label": "neck actuator", "tau_max": 20.0, "k_passive": 20.0, "c_passive": 1.0, "q_range": 0.8,
         "act_rise": 0.008, "act_fall": 0.010},
    ]
    cfg["foot"] = {"toe": 0.14, "heel": 0.08}
    cfg["sensors"] = {"proprio": {"noise": 0.0006, "gain": 1.0}, "vestibular": {"noise": 0.0015, "gain": 1.0},
                      "visual": {"noise": 0.004, "gain": 0.0, "blocked_windows": []},
                      "tactile": {"noise": 0.001, "gain": 1.0}, "cue": {"noise": 0.05}}
    cfg["neural"].update({"gain_ankle_p": 1.5, "gain_ankle_d": 1.5, "gravity_comp": 1.0, "gravity_ff": 0.0, "gain_hip_p": 1.6, "gain_hip_d": 0.5, "motor_noise": 0.002,
                          "visual_weight": 0.0, "vestibular_weight": 0.2, "tactile_weight": 0.8, "cocontraction_base": 0.02, "strategy": "whole-body",
                          "windup_s": 0.0, "windup_frac": 0.0})
    cfg["internal"].update({"breath_amp": 0.0, "fatigue_rate": 0.0, "fatigue_recovery": 0.0, "basal_cost": 0.0002,
                            "activation_cost": 0.003, "capacity_floor": 1.0})
    cfg["adaptation"].update({"eta": 0.2})
    by = {ln["id"]: ln for ln in cfg["lines"]}
    for lid, ts in (("sens.proprio", 0.004), ("sens.vestibular", 0.003), ("sens.tactile", 0.006), ("sens.cue", 0.02),
                    ("neural.reflex", 0.006), ("neural.central.ankle", 0.015), ("neural.central.hip", 0.015),
                    ("neural.central.cue", 0.015)):
        by[lid]["timescale_s"] = ts
    by["sens.visual"]["enabled"] = False
    by["breath.cycle"]["enabled"] = False
    by["metabolic.supply"]["note"] = "timescale = thermal / battery time constant (s)"
    return cfg


PRESETS = {"human-like-planar": human_like, "machine-like-planar": machine_like}

# ------------------------------------------------------------------------------------------------ validation

# dotted path -> (min, max); lists of dicts use the path of their element schema (links.*.mass).
RANGES: dict[str, tuple[float, float]] = {
    "links.*.length": (0.05, 3.0), "links.*.mass": (0.1, 500.0), "links.*.com_frac": (0.05, 0.95),
    "joints.*.tau_max": (0.0, 2000.0), "joints.*.k_passive": (0.0, 20000.0), "joints.*.c_passive": (0.0, 2000.0),
    "joints.*.q_range": (0.05, 3.0), "joints.*.act_rise": (0.002, 1.0), "joints.*.act_fall": (0.002, 1.0),
    "foot.toe": (0.02, 0.6), "foot.heel": (0.02, 0.6),
    "environment.gravity": (0.5, 30.0), "environment.friction_mu": (0.05, 2.0), "environment.compliance": (0.0, 1.0),
    "sensors.*.noise": (0.0, 0.5), "sensors.*.gain": (0.0, 2.0),
    "neural.*": (-50.0, 50.0), "neural.motor_noise": (0.0, 0.5), "neural.windup_s": (0.0, 2.0), "neural.windup_frac": (0.0, 1.0),
    "internal.breath_period": (1.0, 12.0), "internal.breath_amp": (0.0, 0.2), "internal.breath_variability": (0.0, 0.5),
    "internal.energy0": (0.05, 5.0), "internal.basal_cost": (0.0, 0.1), "internal.activation_cost": (0.0, 0.5),
    "internal.fatigue_rate": (0.0, 1.0), "internal.fatigue_recovery": (0.0, 1.0), "internal.capacity_floor": (0.0, 1.0),
    "internal.energy_floor": (0.0, 1.0),
    "adaptation.eta": (0.0, 5.0), "adaptation.error_target": (0.0, 0.2), "adaptation.gain_min": (0.1, 1.0),
    "adaptation.gain_max": (1.0, 5.0), "adaptation.cost": (0.0, 1.0),
    "task.horizon": (1.0, 60.0), "task.dt": (0.002, 0.02), "task.substeps": (1, 8), "task.t_cue": (0.0, 30.0), "task.x_target": (-0.15, 0.15),
    "task.ramp_s": (0.05, 3.0), "task.t_turn": (0.0, 60.0), "task.x_turn": (-0.15, 0.15), "task.initial_lean": (-0.3, 0.3),
    "lines.*.timescale_s": (0.0, 600.0), "lines.*.ignition.threshold": (0.0, 10.0), "lines.*.ignition.hold_s": (0.0, 5.0),
    "lines.*.resource.cost_per_s": (0.0, 1.0),
}
STRING_CHOICES = {"neural.strategy": ("endpoint", "whole-body"), "task.integrator": ("rk4", "semi-implicit-euler", "explicit-euler"), "family": None, "name": None, "model": None}


class ConfigError(ValueError):
    """An invalid or unknown setting; the message names the dotted path."""


def deep_merge(base: Any, over: Any) -> Any:
    if isinstance(base, dict) and isinstance(over, dict):
        out = copy.deepcopy(base)
        for k, v in over.items():
            out[k] = deep_merge(base[k], v) if k in base else copy.deepcopy(v)
        return out
    return copy.deepcopy(over)


def _range_for(path: str) -> tuple[float, float] | None:
    parts = path.split(".")
    if path in RANGES:
        return RANGES[path]
    for i in range(len(parts)):
        gen = ".".join(parts[:i] + ["*"] + parts[i + 1:])
        if gen in RANGES:
            return RANGES[gen]
    if len(parts) >= 3:  # links.N.mass -> links.*.mass ; lines.N.ignition.threshold -> lines.*.ignition.threshold
        gen = ".".join([parts[0], "*", *parts[2:]])
        if gen in RANGES:
            return RANGES[gen]
    return None


def _check(base: Any, cfg: Any, path: str, strict_keys: bool) -> None:
    if isinstance(base, dict):
        if not isinstance(cfg, dict):
            raise ConfigError(f"{path or 'config'} must be an object")
        for k in cfg:
            if k not in base and strict_keys and path not in ("sensors.cue",):
                raise ConfigError(f"unknown setting {path + '.' if path else ''}{k}")
        for k, v in cfg.items():
            if k in base:
                _check(base[k], v, f"{path}.{k}" if path else k, strict_keys)
    elif isinstance(base, list) or base is None and isinstance(cfg, (list, dict)):
        if path in ("lines", "links", "joints"):
            if not isinstance(cfg, list) or not cfg:
                raise ConfigError(f"{path} must be a non-empty list")
            for i, item in enumerate(cfg):
                _check(base[0] if base else item, item, f"{path}.{i}", False)
        # other lists (pushes, blocked_windows, xeno14) are validated by their own checks below
    elif isinstance(base, bool):
        if not isinstance(cfg, bool):
            raise ConfigError(f"{path} must be true or false")
    elif isinstance(base, (int, float)):
        if isinstance(cfg, bool) or not isinstance(cfg, (int, float)) or cfg != cfg:
            raise ConfigError(f"{path} must be a number")
        rng = _range_for(path)
        if rng and not rng[0] <= cfg <= rng[1]:
            raise ConfigError(f"{path} = {cfg} is outside the allowed range {rng[0]}..{rng[1]}")
    elif isinstance(base, str):
        if not isinstance(cfg, str):
            raise ConfigError(f"{path} must be text")
        choices = STRING_CHOICES.get(path)
        if choices and cfg not in choices:
            raise ConfigError(f"{path} must be one of {choices}")


def validate(cfg: dict[str, Any], reference: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a normalised copy of ``cfg`` or raise ConfigError. Unknown keys and out-of-range values are refused, never
    silently clipped. ``reference`` is the schema (a preset); the human-like preset by default."""
    ref = reference or human_like()
    if not isinstance(cfg, dict):
        raise ConfigError("config must be an object")
    _check(ref, cfg, "", True)
    out = copy.deepcopy(cfg)
    n = len(out["links"])
    if len(out["joints"]) != n or n < 2 or n > 8:
        raise ConfigError("a body needs between 2 and 8 links and exactly one joint per link")
    ids = [ln["id"] for ln in out["lines"]]
    if len(set(ids)) != len(ids):
        raise ConfigError("operation line ids must be unique")
    for ln in out["lines"]:
        if ln["kind"] not in LINE_KINDS:
            raise ConfigError(f"line {ln['id']}: kind must be one of {LINE_KINDS}")
        for k in ln.get("observable_by", []):
            if k not in OBSERVATION_KINDS:
                raise ConfigError(f"line {ln['id']}: unknown observation kind {k}")
    env = out["environment"]
    for i, p in enumerate(env.get("pushes", [])):
        for key, lo, hi in (("t", 0.0, 60.0), ("dur", 0.01, 2.0), ("force", -600.0, 600.0), ("link", 0, n - 1),
                            ("point_frac", 0.0, 1.0)):
            if key not in p or not lo <= p[key] <= hi:
                raise ConfigError(f"environment.pushes.{i}.{key} must be within {lo}..{hi}")
    for w in out["sensors"]["visual"].get("blocked_windows", []):
        if not (isinstance(w, (list, tuple)) and len(w) == 2 and 0.0 <= w[0] <= w[1]):
            raise ConfigError("sensors.visual.blocked_windows must be [start, end] pairs of seconds")
    if env.get("ledge") is not None:
        led = env["ledge"]
        if not all(k in led for k in ("t0", "t1", "toe_scale")) or not 0.1 <= led["toe_scale"] <= 1.0:
            raise ConfigError("environment.ledge needs t0, t1 and toe_scale in 0.1..1")
    hr = env.get("handrail")
    if hr is not None and not all(k in hr for k in ("x", "k", "c", "t0", "t1", "height_frac")):
        raise ConfigError("environment.handrail needs x, k, c, t0, t1 and height_frac")
    t = out["task"]
    if t["t_cue"] + t["ramp_s"] > t["horizon"]:
        raise ConfigError("the cue ramp must end before the horizon")
    return out


def get_preset(name: str) -> dict[str, Any]:
    if name not in PRESETS:
        raise ConfigError(f"unknown body preset {name!r}; known: {sorted(PRESETS)}")
    return PRESETS[name]()


def build(preset: str = "human-like-planar", overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """A validated configuration: the preset with ``overrides`` deep-merged (lists such as ``lines`` are replaced whole)."""
    base = get_preset(preset)
    cfg = deep_merge(base, overrides or {})
    return validate(cfg, base)


def line_by_id(cfg: dict[str, Any], lid: str) -> dict[str, Any]:
    for ln in cfg["lines"]:
        if ln["id"] == lid:
            return ln
    raise ConfigError(f"no operation line {lid!r}")


# ------------------------------------------------------------------------------------------------ interventions

INTERVENTIONS: dict[str, dict[str, Any]] = {
    "sensory_delay": {"label": "sensory feedback delay", "unit": "s added", "default": 0.05, "range": (0.0, 0.6),
                      "edits": "adds delay to the proprioceptive, vestibular and tactile lines (the visual line is separate)"},
    "visual_block": {"label": "visual feedback block", "unit": "end time of block (s); 0 = whole trial", "default": 0.0,
                     "range": (0.0, 60.0), "edits": "blocks the visual line from the start (or reconnects it at the given time)"},
    "contact_change": {"label": "contact condition", "unit": "0 = firm … 1 = slippery and soft", "default": 0.4,
                       "range": (0.0, 1.0), "edits": "lowers friction and base-of-support quality, raises floor compliance"},
    "posture_change": {"label": "posture condition", "unit": "initial forward lean (rad)", "default": 0.04,
                       "range": (-0.2, 0.2), "edits": "initial lean of all links (a posture the body must recover from)"},
    "neural_delay": {"label": "neural response delay", "unit": "s added", "default": 0.03, "range": (0.0, 0.5),
                     "edits": "adds latency to the reflex and central command lines"},
    "perturbation": {"label": "external disturbance", "unit": "push force (N)", "default": 50.0, "range": (-300.0, 300.0),
                     "edits": "a push on the trunk 1.3 s after the cue has taken effect (inside the cue-settling window)"},
    "resource_constraint": {"label": "bodily resource constraint", "unit": "0 = none … 1 = severe", "default": 0.4,
                            "range": (0.0, 1.0), "edits": "less energy, lower capacity floor, faster fatigue"},
}


def apply_intervention(cfg: dict[str, Any], iid: str, magnitude: float | None = None) -> dict[str, Any]:
    """A copy of ``cfg`` with one intervention applied. Interventions edit configuration values only; they never touch
    the random stream, so a control and an intervened run share their noise (common random numbers)."""
    if iid not in INTERVENTIONS:
        raise ConfigError(f"unknown intervention {iid!r}; known: {sorted(INTERVENTIONS)}")
    spec = INTERVENTIONS[iid]
    m = spec["default"] if magnitude is None else float(magnitude)
    lo, hi = spec["range"]
    if not lo <= m <= hi:
        raise ConfigError(f"{iid}: magnitude {m} outside {lo}..{hi}")
    out = copy.deepcopy(cfg)
    by = {ln["id"]: ln for ln in out["lines"]}
    if iid == "sensory_delay":
        for lid in ("sens.proprio", "sens.vestibular", "sens.tactile"):
            by[lid]["timescale_s"] += m
    elif iid == "visual_block":
        end = m if m > 0 else out["task"]["horizon"]
        out["sensors"]["visual"]["blocked_windows"] = [*out["sensors"]["visual"].get("blocked_windows", []), [0.0, end]]
    elif iid == "contact_change":
        out["environment"]["friction_mu"] = max(0.05, out["environment"]["friction_mu"] * (1 - 0.85 * m))
        out["environment"]["compliance"] = min(1.0, out["environment"]["compliance"] + m)
    elif iid == "posture_change":
        out["task"]["initial_lean"] = out["task"]["initial_lean"] + m
    elif iid == "neural_delay":
        for lid in ("neural.reflex", "neural.central.ankle", "neural.central.hip", "neural.central.cue"):
            by[lid]["timescale_s"] += m
    elif iid == "perturbation":
        t = out["task"]
        # a disturbance inside the cue-settling window of the protocol (tagged as an intervention: it does not cut the protocol's windows)
        t_push = t["t_cue"] + t["ramp_s"] + 1.3
        out["environment"]["pushes"] = [*out["environment"]["pushes"],
                                        {"t": round(t_push, 3), "dur": 0.12, "force": m, "link": 2, "point_frac": 0.8, "role": "intervention"}]
    elif iid == "resource_constraint":
        i = out["internal"]
        i["energy0"] = max(0.05, i["energy0"] * (1 - 0.9 * m))
        i["capacity_floor"] = max(0.0, i["capacity_floor"] * (1 - 0.5 * m))
        i["fatigue_rate"] = i["fatigue_rate"] * (1 + 4 * m)
    return out


def apply_interventions(cfg: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    out = cfg
    for it in items:
        out = apply_intervention(out, it["id"], it.get("magnitude"))
    return out
