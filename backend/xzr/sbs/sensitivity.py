"""Dependence of the SBS findings on the declared conventions of the model (number of particles, density, contact cut-off, durations, integration step).

Each VARIANT changes ONE convention of the frozen protocol, runs the same worlds and reads whether the qualitative findings of ``docs/SBS.md`` still hold. The frozen protocol itself (``protocol.PROTOCOL``, its digest) is not edited: a variant is applied to a deep copy inside a context manager and restored afterwards. The model comparison (SBS-05) is NOT repeated per variant (it needs dozens of worlds each); what is checked is formation, dissolution by severity, the outcome distribution and finite-time hysteresis.

The qualitative findings checked (each a boolean with the numbers behind it, none of them a threshold tuned after seeing results):
  F1 condensation: the coupled run holds a larger largest-group share than the never-coupled control at the end of formation
  F2 graded dissolution: mean largest-group share at the end of the intervention falls monotonically with the severity of decoupling and of heating
  F3 outcomes are not guaranteed and depend on severity: persistence is less frequent after the harshest heating than in the untouched control
  F4 finite-time hysteresis: the area between the down and the up sweep is positive"""

from __future__ import annotations

import copy
from contextlib import contextmanager
from typing import Any

import numpy as np

from . import organisation as org
from . import protocol as P

# name -> (kind, change). kind 'world' runs formation + dissolution + reconfiguration (+ hysteresis); 'hold' runs hysteresis only.
VARIANTS: dict[str, tuple[str, dict[str, Any]]] = {
    "baseline": ("world", {}),
    "n40": ("world", {"model.n": 40}),
    "n100": ("world", {"model.n": 100}),
    "density015": ("world", {"model.density": 0.15}),
    "density035": ("world", {"model.density": 0.35}),
    "r_bond1.2": ("world", {"r_bond": 1.2}),
    "r_bond1.5": ("world", {"r_bond": 1.5}),
    "recovery1500": ("world", {"recovery_steps": 1500}),
    "recovery6000": ("world", {"recovery_steps": 6000}),
    "dt0.001_same_physical_time": ("world", {"model.dt": 0.001, "scale_steps": 2}),
    "hold750": ("hold", {"metastability.hold_steps": 750, "metastability.measure_last_steps": 250}),
    "hold3000": ("hold", {"metastability.hold_steps": 3000, "metastability.measure_last_steps": 1000}),
}
STEP_KEYS = ("gas_equilibration.steps", "formation_steps", "hold_steps", "recovery_steps", "interventions.decoupling.duration_steps", "interventions.heating.duration_steps", "sample_every", "metastability.hold_steps", "metastability.measure_last_steps")


def _get(d: dict, path: str):
    for k in path.split("."):
        d = d[k]
    return d


def _set(d: dict, path: str, v) -> None:
    ks = path.split(".")
    for k in ks[:-1]:
        d = d[k]
    d[ks[-1]] = v


@contextmanager
def applied(change: dict[str, Any]):
    """Apply a change to the protocol and the cut-off in place; restore both on exit."""
    saved, saved_r = copy.deepcopy(P.PROTOCOL), org.R_BOND
    try:
        c = dict(change)
        factor = c.pop("scale_steps", 1)
        if "r_bond" in c:
            org.R_BOND = c.pop("r_bond")
        for path, v in c.items():
            _set(P.PROTOCOL, path, v)
        if factor != 1:
            for path in STEP_KEYS:
                _set(P.PROTOCOL, path, int(_get(P.PROTOCOL, path) * factor))
        yield
    finally:
        P.PROTOCOL.clear()
        P.PROTOCOL.update(saved)
        org.R_BOND = saved_r


def run_one(variant: str, seed: int, with_hysteresis: bool) -> dict[str, Any]:
    kind, change = VARIANTS[variant]
    with applied(change):
        out: dict[str, Any] = {"variant": variant, "seed": seed}
        if kind == "world":
            w = P.run_world(seed)
            out["formation"] = {"coupled": w["formation"]["end_coupled"]["largest_share"], "control": w["formation"]["series"][-1]["uncoupled_control"]["largest_share"]}
            out["branches"] = {f"{b['kind']}:{b['level']}": {"share_end_intervention": b["dissolution"]["physical"]["largest_share"], "overlap_end_intervention": b["dissolution"]["organizational"]["best_overlap"], "outcome": b["reconfiguration"]["outcome"]} for b in w["branches"]}
        if with_hysteresis:
            m = P.run_metastability(seed)
            out["hysteresis_area"] = m["hysteresis_area"]
        return out


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Findings F1..F4 for one variant from its per-world rows."""
    worlds = [r for r in rows if "branches" in r]
    out: dict[str, Any] = {"n_worlds": len(worlds)}
    if worlds:
        coupled = float(np.mean([r["formation"]["coupled"] for r in worlds]))
        control = float(np.mean([r["formation"]["control"] for r in worlds]))
        out["F1_condensation"] = {"holds": coupled > control, "coupled_share": coupled, "uncoupled_control_share": control}
        def mean_share(key: str) -> float:
            return float(np.mean([r["branches"][key]["share_end_intervention"] for r in worlds]))
        dec = [mean_share(f"decoupling:{v}") for v in (1.0, 0.6, 0.3, 0.0)]
        heat = [mean_share(f"heating:{v}") for v in (0.5, 0.8, 1.2, 2.0)]
        out["F2_graded_dissolution"] = {"holds": all(a >= b for a, b in zip(dec, dec[1:])) and all(a >= b for a, b in zip(heat, heat[1:])), "mean_share_decoupling_1.0_to_0.0": dec, "mean_share_heating_0.5_to_2.0": heat}
        def count(key: str, outcome: str) -> int:
            return sum(r["branches"][key]["outcome"] == outcome for r in worlds)
        ctl, hot = count("control:None", "PERSISTENCE"), count("heating:2.0", "PERSISTENCE")
        out["F3_outcomes_depend_on_severity"] = {"holds": hot < ctl, "persistence_control": ctl, "persistence_heating_2.0": hot, "of": len(worlds)}
        out["outcomes"] = {key: {o: count(key, o) for o in sorted({r["branches"][key]["outcome"] for r in worlds})} for key in ("control:None", "decoupling:0.0", "heating:1.2", "heating:2.0")}
    areas = [r["hysteresis_area"] for r in rows if "hysteresis_area" in r]
    if areas:
        out["F4_finite_time_hysteresis"] = {"holds": float(np.mean(areas)) > 0, "area_mean": float(np.mean(areas)), "areas": areas}
    return out
