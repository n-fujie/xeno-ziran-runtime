"""B2, the OPEN-LOOP replay: the signal a body sensed is fed to the existing XenoSNN neuron, and the body's records and the neuron's records are kept as separate records.

R37 X (fourth family) asks for sensor, body, memory and resource conditions to be compared "without inferring a thinking subject from a classifier"; R37 III says Sensor-Body and XenoSNN proposals need "separately specified acquisition conditions" for firing records, body configurations, reports and attribution hypotheses.
So the records are kept apart: the sensor input (and its times), the spikes (and their times), the internal state (the membrane), the weights and the plasticity (NONE: XenoSNN has none), the body's own output (does it fall, when), the environment's return (the disturbance), and the coupling (OPEN: nothing the neuron does reaches the body;
XenoSNN keeps no state between calls and so cannot sit in a closed loop). A spike is the crossing of a threshold by a membrane variable: it carries no Gaisho meaning, is never an input of the attribution, and the encoding below is a DECLARED stipulation, not a finding.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from . import snnlink
from .domains import BodyDomain
from .model import digest

# The encoding is stipulated before any result is seen: the vestibular tilt estimate that the body's controller received (a delayed, noisy copy of the trunk tilt, in radians) becomes the unsigned input current of the neuron, one value per body step.
ENCODING = {
    "signal": "the body's sensed vestibular trunk-tilt estimate (the controller's own delayed, noisy copy; XB-TRO sensed channel 2n, n = 4 links)",
    "transform": "input current = GAIN * |tilt estimate|",
    "gain": 1.0,
    "status": "STIPULATED. No value of the gain was tuned to any result; another encoding is another experiment",
}
SENSED_TILT_CHANNEL = 8  # 2 * n links


def replay_cell(dom: BodyDomain, cond: str, i: int, j: int, seeds: list[int]) -> dict[str, Any]:
    """Run the body at cell (i, j) for ``seeds`` and send each seed's sensed tilt through the neuron."""
    if not (0 <= i < len(dom.x_values) and 0 <= j < len(dom.y_values)) or cond not in dom.conditions:
        raise ValueError("cell or condition outside the domain")
    delay, push = float(dom.x_values[i]), float(dom.y_values[j])
    run = dom.run_cell(cond, delay, push, list(seeds))
    dt = float(run.dt)
    sensed = np.asarray(run.arrays["sensed"])[:, :, SENSED_TILT_CHANNEL]
    force = np.asarray(run.arrays["push_force"])
    per_seed = []
    for k, seed in enumerate(seeds):
        current = (ENCODING["gain"] * np.abs(sensed[k])).tolist()
        tr = snnlink.replay(current, f"gaisho-body-snn-{cond[:24]}-{i}-{j}-{seed}")
        steps = tr["timesteps"]
        spikes = [s["t"] for s in steps if s["spike"] == 1]
        per_seed.append({
            "seed": seed,
            "sensor_input": {"times_s": [round(t * dt, 6) for t in range(len(current))], "current": current},
            "spikes": {"steps": spikes, "times_s": [round(t * dt, 6) for t in spikes], "count": len(spikes)},
            "internal_state": {"membrane": [s["membrane"] for s in steps], "max": max(s["membrane"] for s in steps)},
            "bodily_output": {"fell": bool(run.fell[k]), "fall_time_s": None if not bool(run.fell[k]) else float(run.fall_time[k])},
            "environment_return": {"push_force_peak_N": float(np.max(np.abs(force[k])))},
            "runtime": tr["runtime"],
        })
    fell = [p["spikes"]["count"] for p in per_seed if p["bodily_output"]["fell"]]
    stayed = [p["spikes"]["count"] for p in per_seed if not p["bodily_output"]["fell"]]
    rec: dict[str, Any] = {
        "kind": "B2_OPEN_LOOP_REPLAY", "figure_kind": "EXECUTED_COMPUTATIONAL_EXPERIMENT", "condition": cond, "cell": [i, j],
        "interventions": {"sensory feedback delay added, s": delay, "external disturbance, push force N": push}, "seeds": list(seeds), "body": dom.provenance(), "encoding": ENCODING,
        "records": per_seed,
        "weights": "NONE: XenoSNN is one LIF neuron with fixed beta and threshold, set in its code",
        "plasticity": "NONE: nothing changes between calls",
        "memory": "NONE in the neuron; the body's slow gain adaptation is part of the body's own run and is not recorded here",
        "coupling": "OPEN LOOP: the body ran first; the neuron's spikes are not an input of the body (XenoSNN keeps no state between calls and cannot be closed-loop with a body)",
        "operational_summary": {"spike_counts_of_seeds_that_fell": fell, "spike_counts_of_seeds_that_stayed_up": stayed,
                                "reading": "a listing of two groups, not a test and not a measure of anything but this encoding; a difference between the groups would be an operational difference of a stipulated signal, not a Gaisho"},
        "attribution": "UNRESOLVED", "applicability_gate": "NOT_PASSED: a spike train of a one-neuron model is not an episode of a bearer; spikes, firing counts and the body's fall are not inputs of any attribution (R37: Det_D, not Occ_G)",
    }
    rec["digest"] = digest({k: v for k, v in rec.items() if k != "digest"})
    return rec
