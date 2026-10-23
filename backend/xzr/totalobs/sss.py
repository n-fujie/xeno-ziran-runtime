"""Scale / Size / Speed: three independently changeable axes, their interactions, and metrics whose own definitions may change.

SSS is not a triple of parameters. Each axis is a *set of declared parameters* of the world and the observing net; it is the conditions under which observing,
identifying, forming objects, intervening, communicating and recording succeed that these parameters change, and the metrics that describe the outcome have
a definition, a unit, a method, a version, a history, a comparability rule and expiry conditions that can themselves change.

    Scale   the scale at which observation and identification take place: sensor block size, identification connectivity (and the intervention footprint)
    Size    the extent of the system: rows x cols of regions, interaction span, number of sources, resource pool per sensor stays fixed per sensor count
    Speed   the relative speeds: propagation ``c``, the world's own event period, the sensors' observation period, communication latency per hop,
            the research decision interval (steps per generation)

``vary`` changes one axis and leaves the parameters of the others untouched (checked by ``independent``). ``factorial`` runs 2 (or 3) axes at two levels and
returns main effects and interaction contrasts from the cell means. A metric measured under a changed definition is not compared with the old one:
``comparable`` says why not, and ``segments`` cuts a series at every break; nothing is imputed.
"""

from __future__ import annotations

import copy
import itertools
from collections.abc import Callable

import numpy as np

AXES = ("scale", "size", "speed")
# axis -> level -> dotted parameters set in the environment
LEVELS: dict[str, dict[str, dict[str, float | int]]] = {
    "scale": {"low": {"net.scale": 1}, "high": {"net.scale": 2}},
    "size": {"low": {"world.rows": 6, "world.cols": 8}, "high": {"world.rows": 10, "world.cols": 16}},
    "speed": {
        "low": {"world.c": 0.5, "net.period": 6, "world.source_period": 36},
        "high": {"world.c": 2.0, "net.period": 3, "world.source_period": 20},
    },
}
AXIS_PARAMS = {a: sorted({k for lv in LEVELS[a].values() for k in lv}) for a in AXES}


def _get(env: dict, dotted: str):
    node = env
    for p in dotted.split("."):
        node = node.get(p, {}) if isinstance(node, dict) else None
    return node


def _set(env: dict, dotted: str, value) -> None:
    node = env
    parts = dotted.split(".")
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    node[parts[-1]] = value


def vary(env: dict, axis: str, level: str | dict) -> dict:
    """A copy of ``env`` with only ``axis`` set to ``level`` ('low' / 'high' or an explicit {param: value} dict over that axis's parameters)."""
    if axis not in AXES:
        raise ValueError(f"axis must be one of {AXES}")
    values = LEVELS[axis][level] if isinstance(level, str) else level
    bad = [k for k in values if k not in AXIS_PARAMS[axis]]
    if bad:
        raise ValueError(f"parameters {bad} do not belong to the {axis} axis")
    out = copy.deepcopy(env)
    for k, v in values.items():
        _set(out, k, v)
    return out


def independent(env_a: dict, env_b: dict, axis: str) -> dict:
    """Which declared parameters differ between two environments, per axis: an axis change is independent when only its own parameters differ."""
    allp = {a: AXIS_PARAMS[a] for a in AXES}
    diff = {a: [k for k in ps if _get(env_a, k) != _get(env_b, k)] for a, ps in allp.items()}
    return {"changed": {a: v for a, v in diff.items() if v}, "independent": all(not v for a, v in diff.items() if a != axis)}


# ---------------------------------------------------------------------------------------------------- interactions
def effects(axes: tuple[str, ...], cells: dict[tuple, float | None], levels: tuple[str, str] = ("low", "high")) -> dict:
    """Main effects (high - low, averaged over the other axes) and interaction contrasts of order 2 and 3 from the cell values of a full 2^k design.
    A cell whose value is undefined (``None``) makes every effect that uses it undefined (``None``); it is not replaced by 0."""

    def contrast(sub: tuple[int, ...]) -> float | None:
        tot = 0.0
        for combo, v in cells.items():
            if v is None:
                return None
            sign = 1
            for i in sub:
                sign *= 1 if combo[i] == levels[1] else -1
            tot += sign * v
        return round(tot / (len(cells) / 2), 6)

    out = {
        "axes": list(axes),
        "levels": list(levels),
        "cells": {"/".join(c): v for c, v in cells.items()},
        "main": {},
        "interaction": {},
    }
    for i, a in enumerate(axes):
        out["main"][a] = contrast((i,))
    for order in range(2, len(axes) + 1):
        for sub in itertools.combinations(range(len(axes)), order):
            out["interaction"]["x".join(axes[i] for i in sub)] = contrast(sub)
    return out


def factorial(
    env: dict, axes: tuple[str, ...], run: Callable[[dict], float | None], levels: tuple[str, str] = ("low", "high")
) -> dict:
    """Run a full two-level design over ``axes`` (``run(env) -> value`` per cell, already averaged over seeds by the caller) and return ``effects``."""
    cells: dict[tuple, float | None] = {}
    for combo in itertools.product(levels, repeat=len(axes)):
        e = env
        for a, lv in zip(axes, combo, strict=True):
            e = vary(e, a, lv)
        cells[combo] = run(e)
    return effects(axes, cells, levels)


# ---------------------------------------------------------------------------------------------------- metrics with definitions
METRICS: dict[str, dict] = {
    "recall_region": {
        "definition": "fraction of true objects (connected sets of regions above the verifier's truth threshold) that overlap at least one identified object; undefined (null) when no true object exists",
        "unit": "fraction",
        "range": [0.0, 1.0],
        "method": "verifier overlap on region cells at checkpoints (verifier.score)",
        "version": 1,
        "basis_keys": [],
        "expires_when": ["the truth threshold or connectivity of the verifier changes"],
        "history": [{"version": 1, "change": "initial definition"}],
    },
    "identified_count": {
        "definition": "number of objects the observing configuration identifies",
        "unit": "objects",
        "range": [0, None],
        "method": "agent-side identify() on the hub's records",
        "version": 1,
        "basis_keys": ["rows", "cols", "theta", "connect", "scale_profile", "variable", "integrate"],
        "expires_when": ["any basis key changes (the objects counted are not the same kind of thing)"],
        "history": [{"version": 1, "change": "initial definition"}],
    },
    "eval_success": {
        "definition": "whether the evaluation rule in force (E0: coverage and an identified object; E1: and persistence; E2: and a supported hypothesis) holds",
        "unit": "boolean",
        "range": [0, 1],
        "method": "agent-side rule on findings",
        "version": 1,
        "basis_keys": ["eval_rule"],
        "expires_when": ["the evaluation rule changes"],
        "history": [{"version": 1, "change": "initial definition"}],
    },
    "info_age": {
        "definition": "mean age (steps) of the records the hub holds at the checkpoints: observation time to checkpoint time",
        "unit": "steps",
        "range": [0, None],
        "method": "hub store at checkpoints",
        "version": 1,
        "basis_keys": ["staleness"],
        "expires_when": ["staleness window changes"],
        "history": [{"version": 1, "change": "initial definition"}],
    },
}


# rules v2 (see loop.py): the hub's freshness window counts from ARRIVAL, so the same metric names are measured on a different set of records than under v1. The
# freshness rule becomes part of the basis of the metrics that depend on what the hub holds: a v1 and a v2 measurement are not comparable, and say why.
METRICS_V2 = copy.deepcopy(METRICS)
for _m in ("recall_region", "identified_count", "info_age"):
    METRICS_V2[_m]["basis_keys"] = [*METRICS_V2[_m]["basis_keys"], "freshness"]
METRICS_V2["recall_region"]["definition"] += (
    "; computed from the records the hub's freshness rule lets the agent use (rules v2: the window counts from arrival). This is a measure of what the research "
    "system observed, not of the software's reproducibility"
)


def comparable(a: dict, b: dict) -> dict:
    """Two measurements ``{metric, version, basis: {...}}``: comparable only if the metric is the same, at the same version, and every basis key the
    metric declares is equal. Returns ``{"comparable": bool, "reasons": [...]}``; there is no partial comparability and nothing is converted."""
    reasons: list[str] = []
    if a["metric"] != b["metric"]:
        return {"comparable": False, "reasons": [f"different metrics: {a['metric']} / {b['metric']}"]}
    spec = METRICS.get(a["metric"])
    if spec is None:
        return {"comparable": False, "reasons": [f"metric {a['metric']!r} has no registered definition"]}
    if a.get("version") != b.get("version"):
        reasons.append(f"definition version differs ({a.get('version')} vs {b.get('version')})")
    for k in spec["basis_keys"]:
        if a.get("basis", {}).get(k) != b.get("basis", {}).get(k):
            reasons.append(f"basis {k!r} differs ({a.get('basis', {}).get(k)!r} vs {b.get('basis', {}).get(k)!r})")
    return {"comparable": not reasons, "reasons": reasons}


class MetricLog:
    """Measurements with the definition under which they were made. A *revision* of a metric (a new definition) bumps its version and keeps the
    history; ``segments`` and ``compare`` then refuse to treat numbers across a break as one series."""

    def __init__(self, rules_version: str = "v1") -> None:
        self.registry = copy.deepcopy(METRICS_V2 if rules_version == "v2" else METRICS)
        self.rows: list[dict] = []

    def measure(self, metric: str, value, basis: dict, t: int) -> dict:
        spec = self.registry[metric]
        row = {
            "metric": metric,
            "version": spec["version"],
            "basis": {k: basis.get(k) for k in spec["basis_keys"]},
            "value": value,
            "t": t,
            "unit": spec["unit"],
        }
        self.rows.append(row)
        return row

    def revise(self, metric: str, change: str, t: int) -> dict:
        spec = self.registry[metric]
        spec["version"] += 1
        spec["history"].append({"version": spec["version"], "change": change, "t": t})
        return {"metric": metric, "version": spec["version"], "change": change, "t": t}

    def segments(self, metric: str) -> list[list[dict]]:
        segs: list[list[dict]] = []
        for r in (r for r in self.rows if r["metric"] == metric):
            if segs and comparable(segs[-1][-1], r)["comparable"]:
                segs[-1].append(r)
            else:
                segs.append([r])
        return segs

    def compare(self, metric: str, first: int, second: int) -> dict:
        """Compare the means of two segments of a series; if the segments' definitions are incomparable, say so and return no number."""
        segs = self.segments(metric)
        if not (0 <= first < len(segs) and 0 <= second < len(segs)):
            return {"comparable": False, "reasons": ["no such segment"], "delta": None}
        a, b = segs[first][0], segs[second][0]
        c = comparable(a, b)
        if not c["comparable"]:
            return {**c, "delta": None}
        va = [r["value"] for r in segs[first] if r["value"] is not None]
        vb = [r["value"] for r in segs[second] if r["value"] is not None]
        if not va or not vb:
            return {"comparable": True, "reasons": ["a segment has no defined value"], "delta": None}
        return {"comparable": True, "reasons": [], "delta": round(float(np.mean(vb) - np.mean(va)), 6)}

    def report(self) -> dict:
        return {
            "registry": self.registry,
            "segments": {
                m: [{"n": len(s), "version": s[0]["version"], "basis": s[0]["basis"]} for s in self.segments(m)]
                for m in sorted({r["metric"] for r in self.rows})
            },
        }
