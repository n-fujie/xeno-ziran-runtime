"""Experiment records, their JSON / CSV export, re-running, and the history store (historical re-entry).

A record holds everything needed to repeat an experiment and to read it back: id, model version, seeds, the initial body
configuration, the observation configurations, the interventions, the time step and numerical method, the results (tables and
series that the interface plots), the negative results, the unobserved differences and the history links. ``rerun`` repeats an
experiment from its stored settings and compares result digests: within one platform a repeat is bit-identical; across platforms
(desktop vs the browser's WebAssembly) values agree to rounding, so the digest is taken over values rounded to 6 significant
digits and ``compare`` reports the numeric difference.

The history store keeps records in order. *Re-entry* means three things here, all explicit: ``reanalyse`` re-observes a stored
simulated trajectory (same body, same seeds) under a later observation configuration; ``carry_over`` hands the retained slow
state of a stored run (fatigue, energy, adaptation gain, tension, sediment) to a later experiment as its starting state;
``registry`` accumulates unobserved differences across records so later reconfigurations can target them. Re-observing a
simulation is not a re-measurement of a real body.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import platform
import sys
from typing import Any

import numpy as np

from . import MODEL_VERSION

SCHEMA = "xbtro.record/1"
NUMERICAL_METHOD = ("RK4 on the N-link planar Lagrangian equations with the muscle drive held over each step; "
                    "batched seeds with common random numbers; first-order activation dynamics; digests over 6 significant digits")


def _round(x: Any, sig: int = 6) -> Any:
    if isinstance(x, (np.floating, float)):
        v = float(x)
        if not math.isfinite(v):
            return None
        if v == 0:
            return 0.0
        return float(f"{v:.{sig - 1}e}")
    if isinstance(x, (np.integer, int)) and not isinstance(x, bool):
        return int(x)
    if isinstance(x, np.ndarray):
        return [_round(v, sig) for v in x.tolist()]
    if isinstance(x, dict):
        return {str(k): _round(v, sig) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_round(v, sig) for v in x]
    return x


def clean(x: Any) -> Any:
    """JSON-safe copy: numpy types converted, non-finite numbers become null."""
    return _round(x, 12)


def digest(results: Any) -> str:
    """Hash of the results rounded to 6 significant digits (stable across platforms up to rounding)."""
    blob = json.dumps(_round(results, 6), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def provenance() -> dict[str, Any]:
    return {"python": sys.version.split()[0], "numpy": np.__version__, "platform": sys.platform, "machine": platform.machine()}


def make_record(experiment: str, params: dict[str, Any], seeds: list[int], body: dict[str, Any], observations: list[dict[str, Any]],
                interventions: list[dict[str, Any]], results: dict[str, Any], negative: list[dict[str, Any]],
                unobserved: list[dict[str, Any]], history: dict[str, Any], dt: float) -> dict[str, Any]:
    results = clean(results)
    d = digest(results)
    rec = {
        "schema": SCHEMA, "id": f"xb-{experiment.lower()}-{d[:12]}", "experiment": experiment, "model_version": MODEL_VERSION,
        "seeds": list(seeds), "initial_configuration": clean(body), "observation_configurations": clean(observations),
        "interventions": clean(interventions), "time_step_s": dt, "numerical_method": NUMERICAL_METHOD,
        "parameters": clean(params), "results": results, "negative_results": clean(negative),
        "unobserved_differences": clean(unobserved), "history": clean(history),
        "rerun": {"experiment": experiment, "parameters": clean(params)}, "digest": d, "provenance": provenance(),
        "labels": {"reference": "model reference state (simulator-internal; not an observation of a real body)",
                   "observation": "output of a simulated observation model applied to the reference (separate from it)",
                   "estimate": "model-based estimate computed from observation outputs only"},
    }
    return rec


# ------------------------------------------------------------------------------------------------ export

def to_json(record: dict[str, Any]) -> str:
    return json.dumps(record, indent=1, sort_keys=True)


def to_csv(record: dict[str, Any]) -> str:
    """Every table of the record, one after another, each preceded by '# table: <name>' and a header row. Metadata first."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["# record", record["id"]])
    for k in ("experiment", "model_version", "digest", "time_step_s", "numerical_method"):
        w.writerow([f"# {k}", record[k]])
    w.writerow(["# seeds", " ".join(str(s) for s in record["seeds"])])
    w.writerow(["# labels", "reference = model reference state (not an observation of a real body); observation = simulated model output"])
    for t in record["results"].get("tables", []):
        w.writerow([])
        w.writerow([f"# table: {t['name']}", t.get("title", "")])
        w.writerow(t["columns"])
        for row in t["rows"]:
            w.writerow(["" if v is None else v for v in row])
    if record.get("negative_results"):
        w.writerow([])
        w.writerow(["# table: negative_results"])
        w.writerow(["statement", "evidence"])
        for n in record["negative_results"]:
            w.writerow([n.get("statement", ""), json.dumps(n.get("evidence", ""), sort_keys=True)])
    if record.get("unobserved_differences"):
        w.writerow([])
        w.writerow(["# table: unobserved_differences"])
        w.writerow(["difference", "status", "reason", "observation_configuration"])
        for u in record["unobserved_differences"]:
            w.writerow([u.get("id"), u.get("status"), u.get("reason"), u.get("configuration")])
    return out.getvalue()


def compare(a: dict[str, Any], b: dict[str, Any], rtol: float = 1e-6) -> dict[str, Any]:
    """Compare the results of two records numerically (for runs on different platforms): max relative difference of all numbers."""
    worst = 0.0
    count = 0
    mismatches: list[str] = []

    def walk(x: Any, y: Any, path: str) -> None:
        nonlocal worst, count
        if isinstance(x, dict) and isinstance(y, dict):
            for k in x:
                if k in y:
                    walk(x[k], y[k], f"{path}.{k}")
                else:
                    mismatches.append(f"{path}.{k} missing")
        elif isinstance(x, list) and isinstance(y, list):
            if len(x) != len(y):
                mismatches.append(f"{path} length {len(x)} vs {len(y)}")
                return
            for i, (u, v) in enumerate(zip(x, y, strict=True)):
                walk(u, v, f"{path}[{i}]")
        elif isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
            count += 1
            denom = max(abs(x), abs(y), 1e-12)
            rel = abs(x - y) / denom
            worst = max(worst, rel)
        elif x != y:
            mismatches.append(f"{path}: {x!r} != {y!r}")

    walk(a["results"], b["results"], "results")
    return {"numbers_compared": count, "max_relative_difference": worst, "structural_mismatches": mismatches[:20],
            "equal_digest": a["digest"] == b["digest"], "within_tolerance": worst <= rtol and not mismatches}


# ------------------------------------------------------------------------------------------------ history

class HistoryStore:
    """An ordered, exportable store of records with an accumulating registry of unobserved differences."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        self.order: list[str] = []
        self.slow: dict[str, dict[str, list[float]]] = {}   # record id -> retained slow state per seed
        self.log: list[dict[str, Any]] = []

    def add(self, record: dict[str, Any], slow_state: dict[str, Any] | None = None, parent: str | None = None) -> dict[str, Any]:
        rid = record["id"]
        if rid in self.records:
            rid2 = f"{rid}-{len(self.order) + 1}"
            record = {**record, "id": rid2}
            rid = rid2
        record["history"] = {**record.get("history", {}), "sequence": len(self.order) + 1, "parent": parent}
        self.records[rid] = record
        self.order.append(rid)
        if slow_state is not None:
            self.slow[rid] = {k: [float(x) for x in np.asarray(v).ravel()] for k, v in slow_state.items()}
        self.log.append({"event": "added", "id": rid, "parent": parent})
        return record

    def get(self, rid: str) -> dict[str, Any]:
        if rid not in self.records:
            raise KeyError(rid)
        return self.records[rid]

    def listing(self) -> list[dict[str, Any]]:
        return [{"id": rid, "experiment": self.records[rid]["experiment"], "digest": self.records[rid]["digest"][:12],
                 "sequence": self.records[rid]["history"].get("sequence"), "parent": self.records[rid]["history"].get("parent"),
                 "negative_results": len(self.records[rid].get("negative_results", [])),
                 "unobserved": len(self.records[rid].get("unobserved_differences", [])), "seeds": len(self.records[rid]["seeds"])}
                for rid in self.order]

    def registry(self) -> list[dict[str, Any]]:
        """Unobserved differences accumulated over all records, with whether a later record identified them."""
        reg: dict[str, dict[str, Any]] = {}
        for rid in self.order:
            for u in self.records[rid].get("unobserved_differences", []):
                e = reg.setdefault(u["id"], {"id": u["id"], "first_record": rid, "history": [], "identified_later": False})
                e["history"].append({"record": rid, "status": u.get("status"), "reason": u.get("reason"), "configuration": u.get("configuration")})
                if u.get("status", "").startswith("identified"):
                    e["identified_later"] = True
                    e["identified_in"] = rid
        return sorted(reg.values(), key=lambda e: e["id"])

    def carry_over(self, rid: str) -> dict[str, list[float]] | None:
        return self.slow.get(rid)

    def export(self) -> dict[str, Any]:
        return {"schema": "xbtro.history/1", "records": [self.records[r] for r in self.order], "slow_state": self.slow, "log": self.log}

    def load(self, data: dict[str, Any]) -> int:
        if data.get("schema") != "xbtro.history/1":
            raise ValueError("not an XB-TRO history export")
        n = 0
        for rec in data["records"]:
            if rec.get("schema") != SCHEMA:
                raise ValueError("a record has an unknown schema")
            if digest(rec["results"]) != rec["digest"]:
                raise ValueError(f"record {rec.get('id')}: results do not match their digest")
            if rec["id"] not in self.records:
                self.records[rec["id"]] = rec
                self.order.append(rec["id"])
                n += 1
        for k, v in data.get("slow_state", {}).items():
            self.slow.setdefault(k, v)
        return n

    def import_record(self, rec: dict[str, Any]) -> dict[str, Any]:
        if rec.get("schema") != SCHEMA:
            raise ValueError("not an XB-TRO record")
        if digest(rec["results"]) != rec["digest"]:
            raise ValueError("the record's results do not match its digest (edited or damaged)")
        return self.add(rec, parent=rec.get("history", {}).get("parent"))
