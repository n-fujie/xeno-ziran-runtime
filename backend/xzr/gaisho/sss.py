"""Scale, Size and Speed of the OBSERVATION, varied one axis at a time over several values each (Dictionary entries 035-038: the three are separate, non-monotonic, never one score; each is to be varied separately before any interpretation; dictionary.D6).

The laboratory's stand-ins, and what each is NOT:
* Scale (036: granularity and range of the description) <- ``Observation.scale``: the recorded grid keeps every k-th point of each axis. Not the agent's size and not a rate.
* Size (037: material extent, capacity, count) <- ``Observation.resources``: the most cells the observer can record (the capacity of the apparatus). The material size of the TARGET (the agent has three weights) is not a variable of this domain, so it is not varied.
* Speed (038: rates and delays of target change, sensing, correction) <- ``Observation.speed``: one snapshot of the operation's state in every k-th. Target dynamics, sensing rate, computing latency and intervention deadline are not separated here (only the snapshot rate is).

The temporal window (the trials per recorded cell) is varied as a fourth, separate sweep because it is the horizon of a sample, which entry 038 distinguishes from the rate: it is not one of the three.

Each axis is listed from the fullest value to the most degraded one, so that a relation that is lost and then identified again along the list is a non-monotonic dependence (an identification that merely appears as the values grow would not be). For every value the relations the observation can identify, the classes of those it cannot, and the interval over the 20 seeds are kept. Whether a relation survives is read per relation, never summed into a score. Dictionary 035 asks for a causal pathway before any epistemic interpretation: none is proposed here, so none is drawn."""

from __future__ import annotations

from typing import Any

from . import MODEL_VERSION
from .knowledge import KnowledgeDomain
from .lab import FULL, SEEDS, Observation, run_domain
from .model import digest

SWEEPS: dict[str, tuple[str, tuple[int, ...]]] = {
    "Scale": ("scale", (1, 2, 3, 4, 6)),
    "Size (recording capacity, cells)": ("resources", (91, 60, 30, 15, 6)),
    "Speed (snapshot rate)": ("speed", (1, 2, 3)),
    "Temporal window (not SSS)": ("temporal_window", (100, 40, 20, 10, 5)),
}


def _obs(field: str, value: int) -> Observation:
    return Observation(**{**FULL.asdict(), field: value, "sensor_channels": FULL.sensor_channels, "boundary": FULL.boundary})


def _overlap(a: list[float] | None, b: list[float] | None) -> bool | None:
    return None if a is None or b is None else bool(a[0] <= b[1] and b[0] <= a[1])


def run_sss(seeds: list[int] | None = None) -> dict[str, Any]:
    seeds = list(seeds or SEEDS)
    dom = KnowledgeDomain()
    sweeps: dict[str, Any] = {}
    for name, (field, values) in SWEEPS.items():
        rows = []
        for v in values:
            res = run_domain(dom, _obs(field, v), tuple(seeds))
            rows.append({"value": v, "result_digest": res["digest"], "conditions": {c: {n: ({"status": r["status"], "value": r["value"], "ci95": r["ci95"]} if r["status"] == "IDENTIFIED" else {"status": r["status"]}) for n, r in cv["relations"].items()} for c, cv in res["conditions"].items()}})
        base = rows[0]
        read: dict[str, Any] = {}
        for c in dom.conditions:
            for n in dom.relation_names:
                series = [r["conditions"][c][n] for r in rows]
                ident = [s["status"] == "IDENTIFIED" for s in series]
                moved = [(_overlap(s.get("ci95"), base["conditions"][c][n].get("ci95")) is False) if ident[k] and ident[0] else None for k, s in enumerate(series)]
                lost_then_back = any(not ident[k] and any(ident[k + 1:]) for k in range(len(ident)))
                read[f"{c} / {n}"] = {"identified_at": [rows[k]["value"] for k in range(len(rows)) if ident[k]], "interval_differs_from_first_value": moved, "identified_lost_and_regained_along_the_axis": bool(lost_then_back)}
        sweeps[name] = {"field": field, "values": list(values), "rows": rows, "reading": read, "relations_regained_after_loss": sorted(k for k, r in read.items() if r["identified_lost_and_regained_along_the_axis"])}
    body = {"model_version": MODEL_VERSION, "domain": dom.id, "seeds": seeds, "sweeps": sweeps,
            "meaning": "what the observation identifies at each value of ONE axis, the other axes at the full observation. No composite score, no causal pathway to an epistemic claim (035), no Gaisho; attribution UNRESOLVED."}
    return {**body, "digest": digest(body)}
