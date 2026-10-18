"""Xeno-14 as experimental conditions on the body configuration.

The fourteen principle names and their operational definitions come from the existing specification in the sibling
repository ``ziran-xeno-simulator`` (``src/domains/body.ts``, ``XENO14`` and ``bundle()``; ``embodied/xeno14/principles.py``
records the same names). They are *starting hypotheses*: each may ignite or fail to ignite, split, merge, conflict, become
redundant, depend on the embodiment, or have no effect. Here every principle is a condition that edits the body
configuration and, where its definition has a rule, adds one operation line (``xeno.<principle>``) with its own ignition
condition and resource cost. Nothing about the sign of any effect is assumed; ``acts_on`` only names the organizations a
principle's definition touches, so an analysis can look there first. Several principles can be active at once.

Not implemented: the principles as fixed body parts or as a universal control law. The operationalization of each principle in
this planar body is stated in ``operationalization`` and is a *translation*, not the original rule.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

SOURCE = "ziran-xeno-simulator: src/domains/body.ts (XENO14, bundle()); embodied/xeno14/principles.py"
JOINT_W = np.array([0.5, 1.0, 1.0, 0.3])

PRINCIPLES: list[dict[str, Any]] = [
    {
        "id": "lower-abdominal-continuity",
        "alias": "lower-center persistence",
        "definition": "maintains a lower-abdominal tension of at least 0.6, coupled to the tension of every segment; tonic, slow, costs energy",
        "operationalization": "a core-tension state kept at or above 0.6 on a slow clock; it adds co-contraction to knee, hip, neck and ankle",
        "ignition": "core tension < 0.6 on the slow clock",
        "acts_on": ["posture_stability", "fatigue_cost", "turn_speed"],
        "cost_per_s": 0.04,
    },
    {
        "id": "whole-skin-sensing",
        "alias": "whole-surface sensing",
        "definition": "senses lean over the whole surface with fine resolution and corrects locally when a segment's signal exceeds a threshold",
        "operationalization": "per-joint local correction from the sensed joint angle when it exceeds 0.03 rad (uses the tactile channel's noise)",
        "ignition": "|sensed joint angle| > 0.03 rad",
        "acts_on": ["posture_stability", "correction_quality", "fatigue_cost"],
        "cost_per_s": 0.03,
    },
    {
        "id": "axis-maintenance",
        "alias": "axial maintenance",
        "definition": "ignites when the body axis deviates by more than 0.02; adds a lean correction proportional to the axis to every segment; costs energy",
        "operationalization": "ankle and hip drive proportional to the sensed trunk tilt when it exceeds 0.02 rad",
        "ignition": "|sensed trunk tilt| > 0.02 rad",
        "acts_on": ["posture_stability", "correction_quality"],
        "cost_per_s": 0.04,
    },
    {
        "id": "endpoint-removal",
        "alias": "terminal-point removal",
        "definition": "disables the endpoint-driven wind-up of a step and replaces it by a whole-body movement",
        "operationalization": "the movement strategy becomes whole-body (no anticipatory counter-lean before the cue response)",
        "ignition": "a cue is perceived",
        "acts_on": ["turn_speed", "precision", "posture_stability"],
        "cost_per_s": 0.0,
    },
    {
        "id": "low-noise-movement",
        "alias": "low-noise movement",
        "definition": "ignites when an external push is registered; damps the push and reduces lean",
        "operationalization": "halves the motor noise and adds joint damping drive while the sensed head rate exceeds 0.05 rad/s",
        "ignition": "|sensed head rate| > 0.05 rad/s",
        "acts_on": ["posture_stability", "correction_quality"],
        "cost_per_s": 0.02,
    },
    {
        "id": "minimal-approach-distance",
        "alias": "upward abdominal organization / minimum-distance action (alias mapping uncertain)",
        "definition": "shortens the approach: reduces the movement velocity above a limit",
        "operationalization": "braking drive on the ankle when the sensed COM velocity towards the target exceeds 0.05 m/s",
        "ignition": "sensed COM velocity > 0.05 m/s towards the target",
        "acts_on": ["precision", "turn_speed"],
        "cost_per_s": 0.02,
    },
    {
        "id": "zero-run-up-transition",
        "alias": "minimum-distance / zero-run-up action",
        "definition": "starts the transition without any run-up when the cue arrives",
        "operationalization": "whole-body strategy with a 20 % faster reference ramp",
        "ignition": "a cue is perceived",
        "acts_on": ["turn_speed", "precision", "posture_stability"],
        "cost_per_s": 0.0,
    },
    {
        "id": "tensegrity",
        "alias": "tensegrity-like distributed organization",
        "definition": "tension is distributed over the segments: each segment's tension relaxes towards the mean",
        "operationalization": "co-contraction across joints is partly equalised (50 % towards the mean)",
        "ignition": "always on",
        "acts_on": ["posture_stability", "fatigue_cost"],
        "cost_per_s": 0.01,
    },
    {
        "id": "slow-movement",
        "alias": "slow-control / locomotor coordination",
        "definition": "reduces the movement velocity above 0.6",
        "operationalization": "the reference ramp is 1.8 times slower",
        "ignition": "a cue is perceived",
        "acts_on": ["turn_speed", "precision", "posture_stability"],
        "cost_per_s": 0.0,
    },
    {
        "id": "narrow-step-balance",
        "alias": "narrow-step balance",
        "definition": "the base of support is narrower (0.7 of its usual width)",
        "operationalization": "the base of support (toe and heel lengths) is 0.7 of nominal",
        "ignition": "always on",
        "acts_on": ["posture_stability", "recovery_time", "fall_rate"],
        "cost_per_s": 0.0,
    },
    {
        "id": "fingertip-tension",
        "alias": "distal / fingertip tension",
        "definition": "holds a fingertip tension of at least 0.4 and couples it to the lower-abdominal tension",
        "operationalization": "a distal-tension state kept at or above 0.4 that adds co-contraction",
        "ignition": "distal tension < 0.4 on the slow clock",
        "acts_on": ["fatigue_cost", "posture_stability"],
        "cost_per_s": 0.05,
    },
    {
        "id": "breathing-synchronization",
        "alias": "respiration-action synchronization",
        "definition": "a breath cycle modulates segment tension; on the exhale phase a lean beyond 0.04 is released",
        "operationalization": "breath-phase modulation of co-contraction; trunk release drive during exhalation when |tilt| > 0.04 rad",
        "ignition": "exhale phase and |sensed trunk tilt| > 0.04 rad",
        "acts_on": ["posture_stability", "correction_quality"],
        "cost_per_s": 0.01,
    },
    {
        "id": "anti-collapse-posture",
        "alias": "anti-slouch / postural organization",
        "definition": "when a lean exceeds 0.55 of the base, catches it with a strong correction that costs energy",
        "operationalization": "strong ankle drive when the sensed COM offset exceeds 55 % of the toe-side base of support",
        "ignition": "|sensed COM offset| > 0.55 * toe length",
        "acts_on": ["fall_rate", "recovery_time", "fatigue_cost"],
        "cost_per_s": 0.30,
    },
    {
        "id": "long-duration-sedimentation",
        "alias": "long-horizon bodily deposition",
        "definition": "a slow clock deposits a retained increment that raises coupling gain and tension",
        "operationalization": "a sediment state grows on an accelerated slow clock (one unit per 2 s, for demonstration) and adds co-contraction",
        "ignition": "always on (slow clock)",
        "acts_on": ["posture_stability", "fatigue_cost"],
        "cost_per_s": 0.0,
    },
]
BY_ID = {p["id"]: p for p in PRINCIPLES}

# How each principle relates to the source rule in body.ts ("source_rule" is the rule as written there: its ignition test and its
# action). Fidelity classes:
#   translated   the planar body has the quantities the rule acts on; ignition and action are translated one-to-one in kind
#                (thresholds are rescaled from the abstract lean/tension units of the source to radians / metres)
#   partial      the rule acts on something the planar body only has in part
#   proxy-only   the planar body has no counterpart of what the rule acts on; the implemented condition is a stand-in and is NOT
#                the principle (do not read its effects as evidence about the principle)
FIDELITY: dict[str, dict[str, str]] = {
    "lower-abdominal-continuity": {
        "fidelity": "translated",
        "source_rule": "clock slow: if lower-abdominal tension < 0.6 then +0.1 and consume energy; couples to every segment tension (gain 0.5, delay 0.2)",
        "gap": "the myofascial coupling delay (0.2) is not modelled; tension acts as co-contraction on a slow clock",
    },
    "whole-skin-sensing": {
        "fidelity": "partial",
        "source_rule": "five distributed skin channels (resolution 0.02); if any |lean| > 0.03 then lean -= 0.35 x reading, consume energy",
        "gap": "the planar body has joint sensors, not a skin; the tactile channel's noise stands in for the skin's resolution",
    },
    "axis-maintenance": {
        "fidelity": "translated",
        "source_rule": "if |axis| > 0.02 then every segment lean -= 0.3 x axis, consume energy 0.04",
        "gap": "the axis is the sensed trunk tilt",
    },
    "endpoint-removal": {
        "fidelity": "translated",
        "source_rule": "disable the endpoint run-up and go-command; whole-body step instead",
        "gap": "the endpoint run-up is the pre-movement counter-lean (windup); whole-body means no windup",
    },
    "low-noise-movement": {
        "fidelity": "partial",
        "source_rule": "if a push is registered then the push is damped and lean reduced by 0.1",
        "gap": "a push is registered through the sensed head rate (> 0.05 rad/s); damping is joint damping drive plus halved motor noise; the source does not mention motor noise",
    },
    "minimal-approach-distance": {
        "fidelity": "proxy-only",
        "source_rule": "if movement velocity > 1.0 then velocity -= 0.3 x excess",
        "gap": "the source's 'movement velocity' is an abstract state; here a braking ankle drive above 0.05 m/s COM velocity. The alias mapping is flagged uncertain in the source.",
    },
    "zero-run-up-transition": {
        "fidelity": "translated",
        "source_rule": "on a cue with velocity < 0.2 and no run-up: velocity += 1.4 (and a forward lean if tension is low)",
        "gap": "whole-body strategy with a 20 % faster reference ramp; the low-tension lean is not modelled",
    },
    "tensegrity": {
        "fidelity": "translated",
        "source_rule": "slow clock: each segment tension moves 50 % towards the mean (-0.05 t + 0.02); lean couples to neighbouring tensions (gain 0.4, delay 0.3)",
        "gap": "the neighbour couplings with delay are not modelled; only the equalisation of co-contraction",
    },
    "slow-movement": {
        "fidelity": "translated",
        "source_rule": "if velocity > 0.6 then velocity -= 0.4 x excess",
        "gap": "implemented as a 1.8 x slower reference ramp (a velocity cap on the abstract state has no direct counterpart)",
    },
    "narrow-step-balance": {
        "fidelity": "translated",
        "source_rule": "base of support = 0.7",
        "gap": "toe and heel lengths x 0.7",
    },
    "fingertip-tension": {
        "fidelity": "proxy-only",
        "source_rule": "slow clock: if fingertip tension < 0.4 then +0.1 and consume energy; couples to lower-abdominal tension (gain 0.4, delay 0.5)",
        "gap": "the planar body has no hand or fingertip; a distal co-contraction state stands in. It is NOT a fingertip.",
    },
    "breathing-synchronization": {
        "fidelity": "partial",
        "source_rule": "breath clock (period 4) alternates phase and shifts every tension +-0.05; on exhale with |axis| > 0.04 lean -= 0.15 x lean",
        "gap": "phase modulation of co-contraction and a trunk release drive on exhale; breath period from the internal breathing line",
    },
    "anti-collapse-posture": {
        "fidelity": "translated",
        "source_rule": "if any |lean| > 0.55 x base then lean -= 0.6 x lean and consume energy 0.8",
        "gap": "strong ankle drive when the sensed COM offset exceeds 55 % of the toe-side support; ignites only in large excursions",
    },
    "long-duration-sedimentation": {
        "fidelity": "proxy-only",
        "source_rule": "sediment clock (period 25): sediment += 1, raises the lower-abdominal couplings' gain and tension",
        "gap": "a sediment state on an accelerated clock (one unit per 2 s) adding co-contraction. Real long-horizon deposition is not simulated in a 7 s trial.",
    },
}
for _p in PRINCIPLES:
    _p.update(FIDELITY[_p["id"]])

ORGANIZATIONS = (
    "posture_stability",
    "correction_quality",
    "turn_speed",
    "precision",
    "fatigue_cost",
    "recovery_time",
    "fall_rate",
)


def catalog() -> list[dict[str, Any]]:
    return [
        {
            **p,
            "status": {
                "translated": "translated to the planar body",
                "partial": "partly translated",
                "proxy-only": "proxy only: the planar body has no counterpart",
            }[p["fidelity"]],
            "source": SOURCE,
        }
        for p in PRINCIPLES
    ]


def apply(cfg: dict[str, Any], ids: list[str]) -> dict[str, Any]:
    """A copy of ``cfg`` with the given principles active: ``cfg['xeno14']`` and one operation line per rule-bearing principle."""
    for i in ids:
        if i not in BY_ID:
            raise ValueError(f"unknown Xeno-14 principle {i!r}")
    out = copy.deepcopy(cfg)
    out["xeno14"] = sorted(set(ids))
    out["lines"] = [ln for ln in out["lines"] if not ln["id"].startswith("xeno.")]
    for i in out["xeno14"]:
        p = BY_ID[i]
        if p["cost_per_s"] > 0 or i in ("endpoint-removal", "zero-run-up-transition", "slow-movement", "narrow-step-balance"):
            out["lines"].append(
                {
                    "id": f"xeno.{i}",
                    "label": f"Xeno-14: {i}",
                    "kind": "neural"
                    if i not in ("lower-abdominal-continuity", "tensegrity", "fingertip-tension", "long-duration-sedimentation")
                    else "internal",
                    "enabled": True,
                    "timescale_s": 0.0,
                    "ignition": {"signal": p["ignition"], "threshold": 0.0, "hold_s": 0.1},
                    "resource": {"pool": "energy", "cost_per_s": p["cost_per_s"]},
                    "observable_by": ["emg", "imu", "posture"],
                    "note": p["operationalization"],
                }
            )
    return out


def effects(cfg: dict[str, Any]) -> dict[str, Any]:
    ids = set(cfg.get("xeno14") or [])
    n = len(cfg["links"])
    return {
        "ids": ids,
        "whole_body": "endpoint-removal" in ids or "zero-run-up-transition" in ids,
        "ramp_scale": (0.8 if "zero-run-up-transition" in ids else 1.0) * (1.8 if "slow-movement" in ids else 1.0),
        "motor_noise_scale": 0.5 if "low-noise-movement" in ids else 1.0,
        "support_scale": 0.7 if "narrow-step-balance" in ids else 1.0,
        "fatigue_scale": 1.0,
        "core_cc": 0.8 if "lower-abdominal-continuity" in ids else 0.0,
        "tensegrity": 0.5 if "tensegrity" in ids else 0.0,
        "w": np.array(([*JOINT_W] + [0.3] * max(0, n - 4))[:n]),
    }


def drive(sim: Any, x14: dict[str, Any], t: float, i: int, sig: dict[str, Any]) -> dict[str, Any]:
    """The contributions of the active rule-bearing principles: per-line drive, extra co-contraction, extra cost."""
    p = sim.p
    s, n = sim.S, p.n
    ids = x14["ids"]
    lines: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    cc = np.zeros((s, n))
    cost = np.zeros(s)
    w = x14["w"]
    toe = sim.cfg["foot"]["toe"]
    hi = min(2, n - 1)

    def add(pid: str, u: np.ndarray, active: np.ndarray) -> None:
        lines[f"xeno.{pid}"] = (np.where(active[:, None], u, 0.0), active)

    if not ids:
        return {"u": np.zeros((s, n)), "cc": cc, "cost": cost, "lines": lines}
    tilt, q_hat, qd_hat = sig["tilt"], sig["q_hat"], sig["qd_hat"]
    if "whole-skin-sensing" in ids:
        act = np.max(np.abs(q_hat), axis=1) > 0.03
        add("whole-skin-sensing", np.where(np.abs(q_hat) > 0.03, -0.35 * q_hat * 3.0, 0.0), act)
    if "axis-maintenance" in ids:
        act = np.abs(tilt) > 0.02
        u = np.zeros((s, n))
        u[:, 0] = -8.0 * tilt
        u[:, hi] = -5.0 * tilt
        add("axis-maintenance", u, act)
    if "low-noise-movement" in ids:
        act = np.abs(sig["head_rate"]) > 0.05
        add("low-noise-movement", -0.15 * qd_hat, act)
    if "minimal-approach-distance" in ids:
        direction = np.sign(sim.cfg["task"]["x_target"]) or 1.0
        over = np.maximum(direction * sig["vhat"] - 0.05, 0.0)
        act = over > 0
        u = np.zeros((s, n))
        u[:, 0] = -1.2 * direction * over
        add("minimal-approach-distance", u, act)
    if "breathing-synchronization" in ids:
        exhale = np.sin(sim.phi) < 0
        act = exhale & (np.abs(tilt) > 0.04)
        u = np.zeros((s, n))
        u[:, hi] = -3.0 * tilt
        add("breathing-synchronization", u, act)
        cc += 0.05 * np.sin(sim.phi)[:, None] * w[None]
    if "anti-collapse-posture" in ids:
        act = np.abs(sig["xhat"]) > 0.55 * toe
        u = np.zeros((s, n))
        u[:, 0] = -0.6 * sig["xhat"] / toe * 3.0
        add("anti-collapse-posture", u, act)
    if "fingertip-tension" in ids:
        cc += 0.25 * sim.hand[:, None] * w[None]
    if "long-duration-sedimentation" in ids:
        cc += 0.04 * sim.sediment[:, None] * w[None]
    # lines without a drive of their own are active whenever their condition is (for the record)
    for pid in ids:
        key = f"xeno.{pid}"
        if key in sim.p.lines and key not in lines:
            on = np.ones(s, dtype=bool)
            if pid in ("endpoint-removal", "zero-run-up-transition", "slow-movement"):
                on = np.isfinite(sim.t_det[1]) & (t >= sim.t_det[1])
            lines[key] = (np.zeros((s, n)), on)
    for pid in ids:
        key = f"xeno.{pid}"
        if key in lines:
            cost += lines[key][1] * BY_ID[pid]["cost_per_s"]
    return {"u": np.zeros((s, n)), "cc": cc, "cost": cost, "lines": lines}


def slow(sim: Any, x14: dict[str, Any], dt: float, extra: dict[str, Any]) -> None:
    """Slow states of the principles that have one (core tension, fingertip tension, sediment)."""
    ids = x14["ids"]
    tick = int(round(0.5 / dt))
    if "lower-abdominal-continuity" in ids and sim.step_i % tick == 0:
        sim.core = np.where(sim.core < 0.6, sim.core + 0.1, sim.core)
    if "fingertip-tension" in ids and sim.step_i % tick == 0:
        sim.hand = np.where(sim.hand < 0.4, sim.hand + 0.1, sim.hand)
    if "long-duration-sedimentation" in ids and sim.step_i % int(round(2.0 / dt)) == 0 and sim.step_i > 0:
        sim.sediment = sim.sediment + 1.0
