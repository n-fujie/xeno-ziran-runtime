"""The Operational Difference Engine and Total Relational Observation of the laboratory.

A DOMAIN supplies conditions (candidate operations), two intervention axes and the executed computational experiment (``simulate``): for one condition and one seed it runs the operation and answers interventions on a grid.
An OBSERVATION CONDITION (the ten axes of the brief) decides what of the executed operation is recorded, at which scale, window and speed, through which instrument, within which boundary, with which coupling and memory,
and whether the observer itself perturbs the operation. The same executed operation can therefore be seen through different conditions, and what differs between the records is attributed either to the operation (a different
realized run) or to the observation (the same realized run, a different record). A relation that a condition cannot identify is not dropped: it carries one of the six UNOBSERVED classes.
Every number is one run of the model per seed; the unit of replication is the seed, and differences between conditions are paired over the same seeds (common random numbers).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

import numpy as np

from . import MODEL_VERSION
from .model import digest

SEEDS = tuple(range(1, 21))


@dataclass(frozen=True)
class Observation:
    """The ten axes. The defaults are the fullest observation the laboratory offers; each field names what it changes."""

    sensor_noise: float = 0.0  # instrument: the probability that a recorded trial outcome is flipped
    sensor_channels: tuple[str, ...] = ("x", "y", "memory")  # sensor: which of the domain's variables have a channel (x, y of the intervention plane, the agent's memory)
    scale: int = 1  # scale: the recorded grid keeps every ``scale``-th point of each axis
    temporal_window: int = 40  # temporal window: the trials per recorded cell and per window of a series
    speed: int = 1  # speed: one snapshot of the operation's state in every ``speed`` snapshots
    coupling: str = "intervened"  # "intervened" (both axes are set by the observer) or "passive" (the operation is only watched along its natural coupling)
    resources: int = 10_000  # resources: the most cells the observer can record
    memory: bool = True  # memory: whether the agent's internal state is recorded
    environment: str = "default"  # environment: a named condition of the world the operation runs in (a REAL change of the operation)
    probe: float = 0.0  # intervention: how strongly the observer perturbs the operation it records (a REAL change of the operation)
    boundary: tuple[str, ...] = ()  # boundary: the variables outside the boundary of the observation

    def asdict(self) -> dict:
        return dataclasses.asdict(self)

    def operation_part(self) -> dict:
        """What of the observation changes the realized operation itself (the rest only changes the record)."""
        return {"temporal_window": self.temporal_window, "environment": self.environment, "probe": self.probe}


FULL = Observation()


class Domain:
    """Interface of a research domain (see knowledge.py, domains.py)."""

    id = ""
    title = ""
    conditions: dict[str, dict] = {}
    x_name = "x"
    y_name = "y"
    x_values: np.ndarray = np.linspace(-3, 3, 13)
    y_values: np.ndarray = np.linspace(-1.5, 1.5, 7)
    snapshots: tuple[str, ...] = ("end",)
    relation_names: tuple[str, ...] = ()
    fine_scale = 1
    seed_count = 20
    max_seeds = 20  # the most seeds one request may run (the cost of one run differs by domain)

    def simulate(self, cond: str, seed: int, obs: Observation) -> dict:  # pragma: no cover - interface
        raise NotImplementedError


# ------------------------------------------------------------------------------------------------ the recorded surface and the relations read from it
def _grid_index(n: int, step: int) -> list[int]:
    return list(range(0, n, max(1, step)))


def record_surface(dom: Domain, raw: np.ndarray, obs: Observation, rng: np.random.Generator) -> dict:
    """What the observation records of one executed surface ``raw`` (shape ny x nx, the share of the n trials of a cell with the outcome 1): the sensor flips outcomes, the scale keeps some points, the resources cap the cells,
    a passive coupling records only the natural manifold, a boundary hides an axis. A cell that is not recorded carries the class of the reason."""
    ny, nx = raw.shape
    n = max(1, obs.temporal_window)
    ix, iy = _grid_index(nx, obs.scale), _grid_index(ny, obs.scale)
    cells = []
    budget = obs.resources
    x_hidden, y_hidden = "x" in obs.boundary or "x" not in obs.sensor_channels, "y" in obs.boundary or "y" not in obs.sensor_channels
    for j in range(ny):
        for i in range(nx):
            status, value = "RECORDED", None
            if i not in ix or j not in iy:
                status = "SCALE_MISFIT"
            elif y_hidden and j != ny // 2:
                status = "BOUNDARY_INVISIBLE" if "y" in obs.boundary else "UNMEASURED"
            elif x_hidden and i != nx // 2:
                status = "BOUNDARY_INVISIBLE" if "x" in obs.boundary else "UNMEASURED"
            elif obs.coupling == "passive" and abs(j - (ny - 1) * (i / max(1, nx - 1))) > 0.9:
                status = "UNMEASURED"  # off the natural manifold: the operation was not made to go there
            elif budget <= 0:
                status = "UNMEASURED"
            if status == "RECORDED":
                budget -= 1
                k = int(round(raw[j, i] * n))
                if obs.sensor_noise > 0:
                    flips = rng.binomial(k, obs.sensor_noise) - rng.binomial(n - k, obs.sensor_noise)
                    k = int(min(n, max(0, k - flips)))
                value = k / n
            cells.append({"i": i, "j": j, "x": float(dom.x_values[i]), "y": float(dom.y_values[j]), "status": status, "p": value, "n": n if value is not None else 0})
    return {"cells": cells, "nx": nx, "ny": ny}


def _col(rec: dict, i: int) -> list[float]:
    return [c["p"] for c in rec["cells"] if c["i"] == i and c["p"] is not None]


def _row(rec: dict, j: int) -> list[float]:
    return [c["p"] for c in rec["cells"] if c["j"] == j and c["p"] is not None]


def surface_effects(rec: dict, nx_hi: int, nx_lo: int, ny_hi: int, ny_lo: int) -> dict:
    """The effect of each axis on the outcome, read from the RECORDED cells only: the mean over the other axis of the difference between the high and the low end of this one. None where the cells needed were not recorded."""
    by = {(c["i"], c["j"]): c["p"] for c in rec["cells"] if c["p"] is not None}
    ny, nx = rec["ny"], rec["nx"]

    def axis_effect(hi: int, lo: int, along_x: bool) -> float | None:
        hs: list[float] = []
        for k in range(ny if along_x else nx):
            a = by.get((hi, k)) if along_x else by.get((k, hi))
            b = by.get((lo, k)) if along_x else by.get((k, lo))
            if a is not None and b is not None:
                hs.append(a - b)
        return float(np.mean(hs)) if hs else None

    return {"effect_x": axis_effect(nx_hi, nx_lo, True), "effect_y": axis_effect(ny_hi, ny_lo, False)}


def classify_unobserved(relation: str, needs: dict, obs: Observation, detectable: bool, feature_width: float | None, step: float) -> str | None:
    """The reason a relation is not identified under this observation, or None if it is. ``needs``: the axes and kinds of record the relation needs (see each domain)."""
    for axis in needs.get("axes", ()):
        if axis in obs.boundary:
            return "BOUNDARY_INVISIBLE"
        if axis not in obs.sensor_channels:
            return "UNMEASURED"
    if needs.get("snapshots") and not obs.memory:
        return "UNMEASURED"
    if needs.get("separate_axes") and obs.coupling == "passive":
        return "IDENTIFICATION_UNRESOLVED"
    if needs.get("snapshots") and obs.speed > 1 and obs.speed >= needs.get("time_constant_snapshots", 2):
        return "TEMPORAL_MISFIT"
    if obs.temporal_window < needs.get("min_window", 20):
        return "TEMPORAL_MISFIT"
    if feature_width is not None and step >= feature_width:
        return "SCALE_MISFIT"
    if obs.sensor_noise >= 0.25 and not detectable:
        return "INSTRUMENT_MISFIT"
    return None


# ------------------------------------------------------------------------------------------------ running a domain
def run_domain(dom: Domain, obs: Observation = FULL, seeds: tuple[int, ...] = SEEDS, conditions: list[str] | None = None) -> dict:
    """Execute the domain's conditions for every seed through the observation and aggregate (the mean over seeds, with the standard deviation across seeds and the standard error; one run is one unit)."""
    names = conditions or list(dom.conditions)
    out: dict[str, Any] = {}
    for cond in names:
        runs = [dom.simulate(cond, s, obs) for s in seeds]
        out[cond] = aggregate(dom, cond, runs, obs)
    res: dict[str, Any] = {"model_version": MODEL_VERSION, "domain": dom.id, "title": dom.title, "observation": obs.asdict(), "seeds": list(seeds), "conditions": out}
    res["digest"] = digest({k: v for k, v in res.items() if k != "digest"})
    return res


def aggregate(dom: Domain, cond: str, runs: list[dict], obs: Observation) -> dict:
    n = len(runs)
    snaps: dict[str, dict] = {}
    for name in dom.snapshots:
        recs = [r["snapshots"].get(name) for r in runs]
        if any(x is None for x in recs):
            snaps[name] = {"recorded": False, "reason": "UNMEASURED" if not obs.memory else "TEMPORAL_MISFIT"}
            continue
        cells: list[dict] = []
        for c0 in recs[0]["surface"]["cells"]:
            vals = [next(c for c in rc["surface"]["cells"] if c["i"] == c0["i"] and c["j"] == c0["j"])["p"] for rc in recs]
            have = [v for v in vals if v is not None]
            cells.append({**{k: c0[k] for k in ("i", "j", "x", "y", "status", "n")}, "p": float(np.mean(have)) if have else None, "sd": float(np.std(have, ddof=1)) if len(have) > 1 else 0.0 if have else None})
        snaps[name] = {"recorded": True, "nx": recs[0]["surface"]["nx"], "ny": recs[0]["surface"]["ny"], "cells": cells, "weights": _mean_weights(recs)}
    rels = {}
    for rn in dom.relation_names:
        vals = [r["relations"][rn]["value"] for r in runs if r["relations"][rn]["value"] is not None]
        status = runs[0]["relations"][rn]["status"]
        if status != "IDENTIFIED" or len(vals) < max(2, n // 2):
            rels[rn] = {"status": status if status != "IDENTIFIED" else "TEMPORAL_MISFIT", "value": None, "n": len(vals)}
            continue
        m, sd = float(np.mean(vals)), float(np.std(vals, ddof=1))
        se = sd / np.sqrt(len(vals))
        rels[rn] = {"status": "IDENTIFIED", "value": m, "sd": sd, "se": se, "ci95": [m - 2.093 * se, m + 2.093 * se], "n": len(vals), "per_seed": [float(v) for v in vals]}
    return {"accuracy": _stat([r["accuracy"] for r in runs]), "accuracy_pre_shift": _stat([r.get("accuracy_pre_shift") for r in runs]), "relations": rels, "snapshots": snaps, "seeds": n, "operation_digest": digest([r["operation_digest"] for r in runs])}


def _mean_weights(recs: list[dict]) -> dict | None:
    w = [r["weights"] for r in recs if r.get("weights")]
    return {k: float(np.mean([x[k] for x in w])) for k in w[0]} if w else None


def _stat(x: list[float | None]) -> dict:
    v = np.array([e for e in x if e is not None], dtype=float)
    if v.size == 0:
        return {"mean": None, "sd": None, "se": None, "n": 0}
    sd = float(v.std(ddof=1)) if v.size > 1 else 0.0
    return {"mean": float(v.mean()), "sd": sd, "se": sd / float(np.sqrt(v.size)), "n": int(v.size)}


def paired(a: list[float | None], b: list[float | None]) -> dict:
    d = np.array([x - y for x, y in zip(a, b, strict=True) if x is not None and y is not None], dtype=float)
    if d.size < 2:
        return {"n": int(d.size), "mean": float(d.mean()) if d.size else None, "sd": None, "se": None, "ci95": None, "detected": None}
    sd = float(d.std(ddof=1))
    se = sd / float(np.sqrt(d.size))
    m = float(d.mean())
    lo, hi = m - 2.093 * se, m + 2.093 * se
    return {"n": int(d.size), "mean": m, "sd": sd, "se": se, "ci95": [lo, hi], "detected": bool(lo > 0 or hi < 0)}
