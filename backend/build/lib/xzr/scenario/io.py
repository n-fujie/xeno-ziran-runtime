"""Scenario files and exports (JSON / CSV)."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path

import numpy as np

from ..runtime.state import State
from .model import Scenario

SCENARIO_DIR = Path(os.environ.get("XZR_SCENARIOS", Path(__file__).resolve().parents[2] / "scenarios"))


def list_samples() -> list[dict]:
    out = []
    for p in sorted(SCENARIO_DIR.glob("*.json")):
        d = json.loads(p.read_text())
        size = d.get("generator", {}).get("n") if d.get("generator") else len(d.get("explicit", {}).get("nodes", []))
        out.append({"id": p.stem, "name": d.get("name", p.stem), "description": d.get("description", ""),
                    "configurations": size})
    return out


def load_sample(sample_id: str) -> Scenario:
    if "/" in sample_id or "\\" in sample_id or sample_id.startswith("."):
        raise KeyError(sample_id)
    p = SCENARIO_DIR / f"{sample_id}.json"
    if not p.is_file():
        raise KeyError(sample_id)
    return Scenario.model_validate_json(p.read_text())


def nodes_csv(state: State, addresses: list[str]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "address", "difference", "form", "theta", "theta_eff", "retention", "memory", "mem_coupling",
                "cap", "frozen", "ignite_count", "lon", "lat"])
    te = state.theta_eff()
    for i in range(state.n):
        lon, lat = state.geo[i]
        w.writerow([i, addresses[i], f"{state.diff[i]:.6g}", int(state.form[i]), f"{state.theta[i]:.6g}",
                    f"{te[i]:.6g}", f"{state.retention[i]:.6g}", f"{state.memory[i]:.6g}",
                    f"{state.mem_coupling[i]:.6g}", f"{state.cap[i]:.6g}", int(state.frozen[i]),
                    int(state.ignite_count[i]), "" if np.isnan(lon) else f"{lon:.5f}",
                    "" if np.isnan(lat) else f"{lat:.5f}"])
    return buf.getvalue()


def edges_csv(state: State) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "src", "dst", "weight", "gate", "load", "capacity", "transform"])
    for e in np.flatnonzero(state.alive):
        w.writerow([int(e), int(state.src[e]), int(state.dst[e]), f"{state.weight[e]:.6g}", f"{state.gate[e]:.6g}",
                    f"{state.load[e]:.6g}", f"{state.capacity[e]:.6g}", int(state.transform[e])])
    return buf.getvalue()


def events_csv(deltas: list) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["t", "kind", "a", "b", "c"])
    for d in deltas:
        for i in d.ignitions:
            w.writerow([d.t, "ignition", int(i), "", ""])
        for e, o, dep in d.penetrations:
            w.writerow([d.t, "penetration", int(e), int(o), int(dep)])
        for i, f in d.transformations:
            w.writerow([d.t, "transformation", int(i), int(f), ""])
        for i in d.returns:
            w.writerow([d.t, "return", int(i), "", ""])
        for i in d.decays:
            w.writerow([d.t, "decay", int(i), "", ""])
        for e in d.cuts:
            w.writerow([d.t, "cut", int(e), "", ""])
        for e, a, b in d.new_connections:
            w.writerow([d.t, "new_connection", int(e), int(a), int(b)])
        for e in d.removed_connections:
            w.writerow([d.t, "removed_connection", int(e), "", ""])
        for e, a, b in d.reconfigurations:
            w.writerow([d.t, "reconfiguration", int(e), int(a), int(b)])
    return buf.getvalue()


def metrics_csv(t: list[int], series: dict[str, list]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    keys = list(series)
    w.writerow(["t", *keys])
    for i, ti in enumerate(t):
        w.writerow([ti, *[series[k][i] for k in keys]])
    return buf.getvalue()
