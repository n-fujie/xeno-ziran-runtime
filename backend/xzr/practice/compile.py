"""Compile the practice layer + direct interventions into runtime interventions.

This is the only bridge from commitments to the runtime, and it is one-way: it produces index-addressed
:mod:`xzr.runtime.intervention` records plus a provenance list explaining where each record came from.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..runtime.intervention import (
    Action,
    Connect,
    Freeze,
    Gate,
    Inject,
    MemoryCondition,
    Mutation,
    OverlayItem,
    ScaleThreshold,
    SetThreshold,
    Sever,
)
from .graph import Score

# resolver(target, want) -> indices; want in {"nodes", "edges"}
Resolver = Callable[[str, str], np.ndarray]


@dataclass
class InterventionConfig:
    """Everything that shapes a run beyond its scenario: commitments, boundaries, direct operations."""

    practice: Any  # Practice, or any representation exposing active_bindings() (see practice/support.py)
    boundaries: dict[str, float]  # scenario boundary set name -> permeability factor
    removed_boundaries: set[str] = field(default_factory=set)
    boundary_override: dict[str, float] = field(default_factory=dict)
    direct: list[dict] = field(default_factory=list)  # {"kind": ..., "target"/..., "text": ...}
    actions: list[dict] = field(default_factory=list)  # one-shot, applied when the config is applied
    log: list[str] = field(default_factory=list)

    def copy(self) -> InterventionConfig:
        return copy.deepcopy(self)

    def to_json(self) -> dict:
        return {"practice": self.practice.to_json(), "boundaries": self.boundaries,
                "removed_boundaries": sorted(self.removed_boundaries), "boundary_override": self.boundary_override,
                "direct": self.direct, "actions": self.actions, "log": self.log}


def _interp(factor: float, strength: float) -> float:
    return 1.0 + (factor - 1.0) * strength


def compile_config(cfg: InterventionConfig, resolve: Resolver) -> tuple[list[OverlayItem], list[Action], list[dict],
                                                                          Score | None]:
    overlay: list[OverlayItem] = []
    prov: list[dict] = []
    # scenario boundaries
    for name, factor in cfg.boundaries.items():
        if name in cfg.removed_boundaries:
            prov.append({"source": f"boundary {name}", "effect": "removed", "targets": 0})
            continue
        f = cfg.boundary_override.get(name, factor)
        edges = resolve(name, "edges")
        overlay.append(Gate(tuple(edges.tolist()), f))
        prov.append({"source": f"boundary {name}", "effect": f"gate × {f:g}", "targets": int(len(edges))})
    # reasoning-layer bindings (any representation exposing active_bindings())
    score = cfg.practice.score() if hasattr(cfg.practice, "score") else None
    for cid, b, s, why in cfg.practice.active_bindings():
        tgt, op = b["target"], b["op"]
        if s <= 0:
            prov.append({"source": f"claim {cid}", "effect": f"{op} on {tgt} inactive", "targets": 0, "why": why})
            continue
        if tgt in cfg.removed_boundaries:
            prov.append({"source": f"claim {cid}", "effect": f"{op} on removed boundary {tgt} suppressed",
                         "targets": 0})
            continue
        if op == "scale_threshold":
            nodes = resolve(tgt, "nodes")
            f = _interp(float(b.get("factor", 1.0)), s)
            overlay.append(ScaleThreshold(tuple(nodes.tolist()), f))
            prov.append({"source": f"claim {cid}", "effect": f"threshold × {f:.3g} on {tgt}", "targets": len(nodes)})
        elif op == "gate":
            edges = resolve(tgt, "edges")
            f = _interp(float(b.get("factor", 1.0)), s)
            overlay.append(Gate(tuple(edges.tolist()), f))
            prov.append({"source": f"claim {cid}", "effect": f"gate × {f:.3g} on {tgt}", "targets": len(edges)})
        elif op == "memory_condition" and s >= 0.5:
            nodes = resolve(tgt, "nodes")
            overlay.append(MemoryCondition(tuple(nodes.tolist()), b.get("decay"), b.get("coupling")))
            prov.append({"source": f"claim {cid}", "effect": f"memory condition on {tgt}", "targets": len(nodes)})
        elif op == "freeze" and s >= 0.5:
            nodes = resolve(tgt, "nodes")
            overlay.append(Freeze(tuple(nodes.tolist())))
            prov.append({"source": f"claim {cid}", "effect": f"freeze {tgt}", "targets": len(nodes)})
        elif op == "mutation":
            nodes = resolve(tgt, "nodes")
            rate = float(b.get("factor", 0.0)) * s
            overlay.append(Mutation(tuple(nodes.tolist()), rate))
            prov.append({"source": f"claim {cid}", "effect": f"mutation {rate:.3g} on {tgt}", "targets": len(nodes)})
    # direct overlay items
    for d in cfg.direct:
        k = d["kind"]
        if k == "scale_threshold":
            nodes = resolve(d["target"], "nodes")
            overlay.append(ScaleThreshold(tuple(nodes.tolist()), d["factor"]))
        elif k == "memory_condition":
            nodes = resolve(d["target"], "nodes")
            overlay.append(MemoryCondition(tuple(nodes.tolist()), d.get("decay"), d.get("coupling")))
        elif k == "freeze":
            nodes = resolve(d["target"], "nodes")
            overlay.append(Freeze(tuple(nodes.tolist())))
        else:
            raise ValueError(f"unknown direct overlay kind {k}")
        prov.append({"source": "direct", "effect": d.get("text", k), "targets": len(nodes)})
    actions: list[Action] = []
    for a in cfg.actions:
        k = a["kind"]
        if k == "sever":
            actions.append(Sever(tuple(a["edges"])))
        elif k == "connect":
            actions.append(Connect(a["src"], a["dst"], a.get("weight", 0.5)))
        elif k == "set_threshold":
            actions.append(SetThreshold(tuple(resolve(a["target"], "nodes").tolist()), a["value"]))
        elif k == "inject":
            actions.append(Inject(tuple(resolve(a["target"], "nodes").tolist()), a["amount"]))
        prov.append({"source": "direct action", "effect": a.get("text", k)})
    return overlay, actions, prov, score
