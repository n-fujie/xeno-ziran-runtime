"""Intervention and causal inference: three things that are never merged.

``OBSERVATION``           what was seen (before and after).
``INTERVENTION``          what was done (an action on a body or an apparatus, with the body and observation-configuration versions before and after).
``COUNTERFACTUAL_MODEL``  what a *declared model* says would have happened. It is never an observation and never MEASURED; its record names the model's assumptions, the identification conditions and the scope.

A difference between before and after an intervention is reported as an *observed difference*; ``identify`` says what status the data may have as a causal statement, and the answer is 'association' unless the design
supports more (a randomised assignment within a frozen, pre-registered protocol), and even then it is 'supported under the stated assumptions', never 'established'."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .provenance import Kind, Provenance, seal

ASSIGNMENTS = ("randomized", "researcher-chosen", "natural", "unknown")


def intervention_record(*, description: str, kind_of_action: str, target: str, applied_at_s: float, assignment: str, body_version_before: int | None, body_version_after: int | None, config_version_before: int | None,
                        config_version_after: int | None, provenance: Provenance | str, creator: dict, source: dict, protocol_ref: dict | None = None, created_at: str | None = None) -> dict:
    if assignment not in ASSIGNMENTS:
        raise ValueError(f"assignment must be one of {ASSIGNMENTS}")
    payload = {"intervention": {"description": description, "action": kind_of_action, "target": target, "applied_at_s": applied_at_s, "assignment": assignment, "protocol_ref": protocol_ref,
                                "body_version": {"before": body_version_before, "after": body_version_after}, "observation_config_version": {"before": config_version_before, "after": config_version_after}},
               "note": "a record of what was done, not of what followed"}
    return seal(payload, provenance=provenance, kind=Kind.INTERVENTION, creator=creator, source=source, created_at=created_at)


def _valid(rec: dict, variable: str) -> list[float]:
    ch = next(c for c in rec["payload"]["channels"] if c["variable"] == variable)
    return [s["value"] for s in ch["samples"] if s["status"] == "MEASURED_VALID" and s["value"] is not None]


def _counts(rec: dict, variable: str) -> dict[str, int]:
    return next(c for c in rec["payload"]["channels"] if c["variable"] == variable)["counts"]


def compare_pre_post(pre: dict, post: dict, variable: str, intervention: dict | None = None) -> dict:
    """The observed difference of a variable between two observation records: valid samples only, the missing ones counted and named. It is not a causal effect and says so."""
    a, b = _valid(pre, variable), _valid(post, variable)
    d = None if not a or not b else float(np.mean(b) - np.mean(a))
    cfg_changed = bool(intervention and intervention["payload"]["intervention"]["observation_config_version"]["before"] != intervention["payload"]["intervention"]["observation_config_version"]["after"])
    return {"variable": variable, "pre_record": pre["record_id"], "post_record": post["record_id"], "intervention_record": intervention["record_id"] if intervention else None, "mean_pre": float(np.mean(a)) if a else None,
            "mean_post": float(np.mean(b)) if b else None, "observed_difference": d, "n_pre": len(a), "n_post": len(b), "pre_counts": _counts(pre, variable), "post_counts": _counts(post, variable),
            "observation_configuration_changed": cfg_changed, "classes": sorted({pre["provenance"], post["provenance"]}), "causal_claim": None,
            "reading": "an observed difference between two records" + ("; the observation configuration also changed, so the two are not even the same observation" if cfg_changed else "") + "; not a causal effect"}


def identify(design: dict) -> dict:
    """What the design allows to be said causally. ``design``: {"assignment", "protocol_analysis_class", "confounders_unaddressed": [...], "n"}."""
    why = []
    if design.get("assignment") != "randomized":
        why.append(f"the assignment was {design.get('assignment')!r}, not randomised")
    if design.get("protocol_analysis_class") != "confirmatory":
        why.append(f"the analysis is {design.get('protocol_analysis_class')!r}, not a pre-registered confirmatory one")
    if design.get("confounders_unaddressed"):
        why.append(f"unaddressed confounders: {design['confounders_unaddressed']}")
    if (design.get("n") or 0) < 2:
        why.append("too few observations")
    if why:
        return {"status": "association", "why_not_causal": why, "assumptions": ["none made: no causal claim"], "statement": "an association; no causal effect is identified by this design"}
    return {"status": "causal effect supported under the stated assumptions", "why_not_causal": [], "assumptions": ["randomisation was carried out as registered", "no interference between trials", "the outcome was measured as registered"],
            "statement": "supported under these assumptions, in this design and scope; not established, not general"}


class StructuralModel:
    """A linear structural causal model with a declared scope. Equations: {var: {"parents": {p: coef}, "intercept": c, "noise_sd": s}}. The model must name its assumptions, its identification conditions and its scope."""

    def __init__(self, equations: dict[str, dict], *, assumptions: list[str], identification: list[str], scope: str):
        if not assumptions or not identification or not scope:
            raise ValueError("a causal model names its assumptions, its identification conditions and its scope")
        self.eq, self.assumptions, self.identification, self.scope = equations, assumptions, identification, scope
        self.order = self._topo()

    def _topo(self) -> list[str]:
        order: list[str] = []
        left = dict(self.eq)
        while left:
            ready = [v for v, e in left.items() if all(p in order or p not in self.eq for p in e["parents"])]
            if not ready:
                raise ValueError("the model has a cycle")
            for v in sorted(ready):
                order.append(v)
                del left[v]
        return order

    def simulate(self, seed: int, n: int, do: dict[str, float] | None = None) -> dict[str, list[float]]:
        rng, do = np.random.default_rng(seed), do or {}
        out: dict[str, np.ndarray] = {}
        for v in self.order:
            e = self.eq[v]
            val = e.get("intercept", 0.0) + sum(c * out[p] for p, c in e["parents"].items() if p in out) + rng.normal(0, e.get("noise_sd", 0.0), n)
            out[v] = np.full(n, float(do[v])) if v in do else val
        return {k: [float(x) for x in v] for k, v in out.items()}

    def counterfactual(self, observed: dict[str, float], do: dict[str, float]) -> dict[str, float]:
        """Abduction (the unit's noise terms from its observed values), action (do), prediction. Needs every variable observed for the unit."""
        if set(observed) != set(self.eq):
            raise ValueError("every variable of the model must be observed for the unit")
        u = {v: observed[v] - (self.eq[v].get("intercept", 0.0) + sum(c * observed[p] for p, c in self.eq[v]["parents"].items() if p in observed)) for v in self.eq}
        out: dict[str, float] = {}
        for v in self.order:
            out[v] = float(do[v]) if v in do else self.eq[v].get("intercept", 0.0) + sum(c * out[p] for p, c in self.eq[v]["parents"].items() if p in out) + u[v]
        return out


def counterfactual_record(model: StructuralModel, observed: dict[str, float], do: dict[str, float], *, parents: list[dict], creator: dict, created_at: str | None = None) -> dict:
    """The model's counterfactual as a sealed record: COUNTERFACTUAL_MODEL, never MEASURED (RECONSTRUCTED_ESTIMATE when it is built from real observations; SYNTHETIC when every input is SYNTHETIC)."""
    pred = model.counterfactual(observed, do)
    prov = Provenance.SYNTHETIC if parents and all(p["provenance"] == "SYNTHETIC" for p in parents) else Provenance.RECONSTRUCTED_ESTIMATE
    payload = {"counterfactual": {"do": do, "observed_unit": observed, "predicted": pred, "assumptions": model.assumptions, "identification": model.identification, "scope": model.scope,
                                  "equations": {v: {"parents": e["parents"], "intercept": e.get("intercept", 0.0)} for v, e in model.eq.items()}},
               "reading": "what the declared model says would have happened for this unit, under its assumptions and within its scope; not an observation and not a result"}
    from .provenance import derive
    if parents:
        return derive(parents, payload=payload, provenance=prov, kind=Kind.COUNTERFACTUAL_MODEL, creator=creator, source={"kind": "computation", "description": "structural causal model (abduction, action, prediction)"},
                      transformations=[{"method": "counterfactual-model", "preserves_provenance": False}], created_at=created_at)
    return seal(payload, provenance=Provenance.SYNTHETIC, kind=Kind.COUNTERFACTUAL_MODEL, creator=creator, source={"kind": "generator", "description": "structural causal model on declared synthetic inputs", "declared_by": "teoo"}, created_at=created_at)


def is_finite_effect(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)
