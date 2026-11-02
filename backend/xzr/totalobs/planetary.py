"""Planetary scale, stated as conditions. The number of regions or agents does not make a synthetic world planetary.

``conditions(env)`` evaluates, from the environment's declared parameters, the structural conditions under which this model has the *form* of a planetary-scale
observation problem, each with its declared threshold and value:

    spatial extent              extent in regions across the longer axis (and the declared synthetic length)
    inter-regional interaction  interaction span reaches beyond the next region (>= 2) and regions beyond the span are coupled only through chains
    propagation time            time for a signal to cross the extent, in sensor periods (>= 3: the world changes during one pass of observation)
    observation period          steps between a sensor's observations
    communication delay         worst-case hub delay in periods (>= 1: information is older than one observation when it arrives)
    observation density         share of regions inside some footprint (< 1: partial coverage)
    resource allocation         blocks one full-resolution pass would need per step relative to the pool (> 1: competition)
    local / global time gap     propagation time across the extent over the local response time (one period)
    scaling law                 reported by ``scaling_law`` from a Size sweep, not asserted
    applicability limits        listed, always

All of this describes the structure of a synthetic model. It says nothing about the Earth: ``earth_claim`` is always false. A claim about a real planetary
system would need measured data and an existing earth-system model to compare with (``requires`` below), neither of which exists here.
"""

from __future__ import annotations

import math

import numpy as np

THRESHOLDS = {
    "span_min": 2,
    "propagation_periods_min": 3.0,
    "comm_delay_periods_min": 1.0,
    "coverage_max": 0.999,
    "contention_min": 1.0,
}
LIMITS = [
    "regions form a regular grid (periodic in longitude only); there is no sphere, no topography, no heterogeneity of the medium",
    "one scalar activity with a single decay and a single coupling law; no energy conservation",
    "sources are pulsed emitters; no feedback from the activity on the sources",
    "propagation delay is an integer number of steps per grid distance; sub-step timing is not modelled",
    "the synthetic length (km_per_region) is a declared unit, not a calibration",
]
REQUIRES = [
    "measured observational data of a real system",
    "an existing earth-system model for the same variables",
    "an agreed mapping from regions to a real geometry",
]


def conditions(env: dict) -> dict:
    w = env.get("world", {})
    n = env.get("net", {})
    rows, cols = int(w.get("rows", 8)), int(w.get("cols", 12))
    c = float(w.get("c", 1.0))
    span = int(w.get("span", 2))
    period = int(n.get("period", 4))
    latency = int(n.get("latency", 1))
    n_sensors = int(n.get("n_sensors", 2))
    radius = int(n.get("radius", 3))
    scale = int(n.get("scale", 1))
    pool = float(n.get("pool", 30))
    N = rows * cols
    extent = max(rows, cols)
    t_cross = extent / max(c, 1e-9)
    foot = min(N, 2 * radius * (radius + 1) + 1)  # regions in a footprint on an unbounded grid (an upper bound)
    covered = min(1.0, n_sensors * foot / N)
    need = (
        n_sensors * math.ceil(foot / (scale * scale)) / max(1, int(round(period)))
    )  # blocks per step if all sensors observe each period
    worst_hops = rows - 1 + cols // 2
    rows_ = [
        {
            "condition": "spatial extent",
            "value": extent,
            "unit": "regions",
            "synthetic_km": round(extent * float(w.get("km_per_region", 500.0)), 1),
            "met": extent >= 2 * span + 1,
            "threshold": f">= {2 * span + 1} (more than one interaction neighbourhood)",
        },
        {
            "condition": "inter-regional interaction",
            "value": span,
            "unit": "grid steps",
            "met": span >= THRESHOLDS["span_min"],
            "threshold": f">= {THRESHOLDS['span_min']}",
        },
        {
            "condition": "propagation time",
            "value": round(t_cross / period, 3),
            "unit": "observation periods",
            "met": t_cross / period >= THRESHOLDS["propagation_periods_min"],
            "threshold": f">= {THRESHOLDS['propagation_periods_min']}",
        },
        {"condition": "observation period", "value": period, "unit": "steps", "met": True, "threshold": "reported"},
        {
            "condition": "communication delay",
            "value": round(worst_hops * latency / period, 3),
            "unit": "observation periods",
            "met": worst_hops * latency / period >= THRESHOLDS["comm_delay_periods_min"],
            "threshold": f">= {THRESHOLDS['comm_delay_periods_min']}",
        },
        {
            "condition": "observation density",
            "value": round(covered, 3),
            "unit": "share of regions in a footprint (upper bound)",
            "met": covered < THRESHOLDS["coverage_max"],
            "threshold": f"< {THRESHOLDS['coverage_max']}",
        },
        {
            "condition": "resource allocation",
            "value": round(need / max(pool, 1e-9), 3),
            "unit": "demand / pool",
            "met": need / max(pool, 1e-9) > THRESHOLDS["contention_min"],
            "threshold": f"> {THRESHOLDS['contention_min']}",
        },
        {
            "condition": "local / global time gap",
            "value": round(t_cross / max(period, 1), 3),
            "unit": "global pass / local period",
            "met": t_cross / period >= 2.0,
            "threshold": ">= 2",
        },
    ]
    return {
        "synthetic": True,
        "earth_claim": False,
        "conditions": rows_,
        "n_met": sum(r["met"] for r in rows_),
        "n": len(rows_),
        "all_met": all(r["met"] for r in rows_),
        "note": "the count of regions or sensors alone does not satisfy these conditions; they describe the structure of a synthetic model",
        "limits": LIMITS,
        "requires_for_real_world_claims": REQUIRES,
    }


def scaling_law(points: list[tuple[float, float]]) -> dict:
    """Power-law fit y ~ a x^b over (x, y) points with y > 0 (x: extent, y: e.g. mean information age). Reports the exponent with a bootstrap interval
    when at least 4 points exist; fewer points give no exponent (null), not a guess."""
    pts = [(x, y) for x, y in points if x > 0 and y is not None and y > 0]
    if len(pts) < 3:
        return {"exponent": None, "n": len(pts), "note": "fewer than 3 usable points: no fit"}
    lx, ly = np.log([p[0] for p in pts]), np.log([p[1] for p in pts])
    b, a = np.polyfit(lx, ly, 1)
    out = {"exponent": round(float(b), 4), "prefactor": round(float(np.exp(a)), 4), "n": len(pts), "interval": None}
    if len(pts) >= 4:
        rng = np.random.default_rng(1)
        bs = []
        for _ in range(200):
            idx = rng.integers(0, len(pts), len(pts))
            if len(set(idx.tolist())) < 3:
                continue
            bs.append(np.polyfit(lx[idx], ly[idx], 1)[0])
        if bs:
            out["interval"] = [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]
    out["note"] = "an empirical fit of this synthetic model over the sweep; no law is asserted"
    return out
