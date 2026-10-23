"""Identification: what the hub can make of the records it holds. Objects are constructs of a configuration, not facts of the world.

An *identified object* is a connected set of regions whose value, under the current observing configuration (scale, boundary, integration rule, variable,
threshold, connectivity), exceeds the detection threshold. Change any of these and the identified objects change although the world did not: that is what
``identify`` is for. Whether an identified object corresponds to anything the world does is not decided here (that is the verifier's work, ``verifier.py``);
this module reads records only.

Integration rules (how reports from several sensors become one field):
    separate   each sensor identifies on its own; objects of different sensors that share a region are one object (union)
    mean       the region's value is the mean of every report covering it (can dilute a fine sensor's high value with a coarse sensor's mean)
    finest     the region's value comes from the finest-scale report covering it
Variables: ``level`` (the reading), ``change`` (reading minus the same block's previous reading), ``contrast`` (reading minus the mean of the
sensor's blocks in the same report).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .observers import Record
from .world import WorldConfig, dist_matrix

INTEGRATIONS = ("separate", "mean", "finest")
VARIABLES = ("level", "change", "contrast")


@dataclass(frozen=True)
class IdentParams:
    theta: float = 0.18  # detection threshold (the classification scheme)
    connect: int = 1  # regions within this grid distance are connected
    integrate: str = "separate"
    variable: str = "level"
    min_cells: int = 1

    def to_dict(self) -> dict:
        return {
            "theta": round(self.theta, 6),
            "connect": self.connect,
            "integrate": self.integrate,
            "variable": self.variable,
            "min_cells": self.min_cells,
        }


def _latest_by_sensor(records: list[Record]) -> dict[str, list[Record]]:
    out: dict[str, list[Record]] = {}
    for r in sorted(records, key=lambda r: (r.t_obs, r.sid)):
        out.setdefault(r.sid, []).append(r)
    return out


def _sensor_field(recs: list[Record], variable: str) -> dict[int, tuple[float, int, int]]:
    """region -> (value, scale, t_obs) from the latest report of one sensor, under ``variable``."""
    last = recs[-1]
    prev = recs[-2] if len(recs) > 1 else None
    vals = {b: v for b, (v, _) in last.blocks.items()}
    if variable == "change":
        vals = {b: (v - prev.blocks[b][0]) if prev is not None and b in prev.blocks else 0.0 for b, v in vals.items()}
    elif variable == "contrast":
        m = float(np.mean(list(vals.values()))) if vals else 0.0
        vals = {b: v - m for b, v in vals.items()}
    out: dict[int, tuple[float, int, int]] = {}
    for b, (_, idx) in last.blocks.items():
        for i in idx:
            out[i] = (vals[b], last.scale, last.t_obs)
    return out


def _components(cells: set[int], d: np.ndarray, connect: int) -> list[set[int]]:
    left, comps = set(cells), []
    while left:
        seed = left.pop()
        comp, stack = {seed}, [seed]
        while stack:
            a = stack.pop()
            near = [b for b in list(left) if d[a, b] <= connect]
            for b in near:
                left.discard(b)
                comp.add(b)
                stack.append(b)
        comps.append(comp)
    return comps


def key_of(cfg: WorldConfig, cells: set[int]) -> str:
    rs, cs = zip(*(divmod(i, cfg.cols) for i in cells), strict=True)
    return f"{int(np.mean(rs)) // 2}:{int(np.mean(cs)) // 3}"


def identify(cfg: WorldConfig, records: list[Record], p: IdentParams, d: np.ndarray | None = None) -> list[dict]:
    """Objects identified from ``records`` under ``p``: ``[{key, cells, peak, mean}]``, sorted by key."""
    if not records:
        return []
    d = dist_matrix(cfg) if d is None else d
    per = {sid: _sensor_field(rs, p.variable) for sid, rs in _latest_by_sensor(records).items()}
    groups: list[set[int]] = []
    vals_of: dict[int, float] = {}
    if p.integrate == "separate":
        for sid in sorted(per):
            f = per[sid]
            over = {i for i, (v, _, _) in f.items() if v > p.theta}
            for comp in _components(over, d, p.connect):
                groups.append(comp)
                for i in comp:
                    vals_of[i] = max(vals_of.get(i, 0.0), f[i][0])
    else:
        contrib: dict[int, list[tuple[float, int, int]]] = {}
        for sid in sorted(per):
            for i, t in per[sid].items():
                contrib.setdefault(i, []).append(t)
        field: dict[int, float] = {}
        for i, cs in contrib.items():
            if p.integrate == "mean":
                field[i] = float(np.mean([v for v, _, _ in cs]))
            else:  # finest: smallest scale, then the latest report
                field[i] = sorted(cs, key=lambda x: (x[1], -x[2]))[0][0]
        over = {i for i, v in field.items() if v > p.theta}
        vals_of = field
        groups = _components(over, d, p.connect)
    # union groups that share a region (separate: objects of different sensors on the same regions are one object)
    merged: list[set[int]] = []
    for g in groups:
        hit = [m for m in merged if m & g]
        for m in hit:
            merged.remove(m)
            g = g | m
        merged.append(g)
    out = []
    for g in merged:
        if len(g) < p.min_cells:
            continue
        v = [vals_of[i] for i in g if i in vals_of]
        out.append({"key": key_of(cfg, g), "cells": sorted(g), "peak": round(max(v), 6), "mean": round(float(np.mean(v)), 6)})
    out.sort(key=lambda o: (o["key"], o["cells"][0]))
    # equal keys (two objects in one bin) are kept apart by a suffix, so that identified sets can be compared as sets
    seen: dict[str, int] = {}
    for o in out:
        k = o["key"]
        seen[k] = seen.get(k, 0) + 1
        if seen[k] > 1:
            o["key"] = f"{k}#{seen[k]}"
    return out


def coverage_cells(records: list[Record]) -> set[int]:
    return {
        i
        for r in _latest_by_sensor(records).values()
        for i in r[-1].blocks and {j for _, (_, idx) in r[-1].blocks.items() for j in idx}
    }
