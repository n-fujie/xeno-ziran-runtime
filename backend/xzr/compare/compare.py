"""Baseline vs intervention.

Both branches are forked from the same engine state *and* RNG state (common random numbers), so any
difference is attributable to the intervention and to how the dynamics amplify it. A third branch —
the baseline under a different random stream — gives a **noise floor**: a difference is reported as
exceeding it only if |intervention − baseline| > 2·|baseline′ − baseline|. This is a heuristic guard
against over-reading, not a statistical test.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from ..lod.hierarchy import Hierarchy
from ..runtime.engine import Engine
from ..runtime.intervention import Action, OverlayItem
from ..shapes.detector import GRAPH_SERIES, STEP_SERIES, ShapeDetector

NODE_CLASSES = {0: "unchanged", 1: "newly reached", 2: "no longer reached", 3: "loop gained", 4: "loop lost",
                5: "ignites more", 6: "ignites less"}
EDGE_CLASSES = {1: "cut only in baseline", 2: "cut only in intervention", 3: "new only in intervention",
                4: "new only in baseline", 5: "reconfigured only in intervention", 6: "reconfigured only in baseline",
                7: "gate changed by intervention"}


@dataclass
class Branch:
    ign: np.ndarray
    reached: np.ndarray
    in_loop: np.ndarray
    cuts: set
    new: set
    reconf: set
    removed: set
    series: dict
    graph: dict
    first_divergence_sets: list  # ignition sets for the first steps (divergence detection)
    gate: np.ndarray
    fingerprint: str


def _drive(gen):
    """Run a stepping generator to completion and return its result (the desktop path: no slicing)."""
    while True:
        try:
            next(gen)
        except StopIteration as stop:
            return stop.value


def _run_steps(engine: Engine, overlay: list[OverlayItem], actions: list[Action], horizon: int, h: Hierarchy,
               graph_every: int, rng_seed: int | None = None):
    """One branch. A generator that yields after every simulation step so a host without threads can interleave other
    work (the browser build); its return value is (Branch, ShapeDetector). Same steps in the same order as always."""
    if rng_seed is not None:
        engine.rng = np.random.default_rng(rng_seed)
    engine.set_overlay(overlay)
    engine.apply(actions)
    s = engine.state
    n = s.n
    det = ShapeDetector(h, graph_every=graph_every)
    ign = np.zeros(n, dtype=np.int32)
    cuts, new, reconf, removed = set(), set(), set(), set()
    early = []
    for i in range(horizon):
        d = engine.step()
        det.observe(d, s)
        ign[d.ignitions] += 1
        for e in d.cuts:
            cuts.add((int(s.src[e]), int(s.dst[e])))
        for e in d.removed_connections:
            removed.add((int(s.src[e]), int(s.dst[e])))
        for _, a, b in d.new_connections:
            new.add((int(a), int(b)))
        for e, old, nw in d.reconfigurations:
            reconf.add((int(s.src[e]), int(old), int(nw)))
        if i < 400:
            early.append(d.ignitions)
        yield i
    if not det.last_graph:
        det.graph_pass(s, s.t)
    return Branch(ign, ign > 0, det.in_loop.copy(), cuts, new, reconf, removed,
                  {k: float(np.mean(v)) if v else 0.0 for k, v in det.series.items()},
                  {k: float(np.mean(v)) if v else 0.0 for k, v in det.graph_series.items()},
                  early, s.gate.copy(), engine.fingerprint()), det


def compare(engine: Engine, base_overlay: list[OverlayItem], base_actions: list[Action],
            int_overlay: list[OverlayItem], int_actions: list[Action], h: Hierarchy, horizon: int = 150,
            graph_every: int = 10, noise_floor: bool = True) -> dict:
    return _drive(compare_steps(engine, base_overlay, base_actions, int_overlay, int_actions, h, horizon, graph_every,
                                noise_floor))


def compare_steps(engine: Engine, base_overlay: list[OverlayItem], base_actions: list[Action],
                  int_overlay: list[OverlayItem], int_actions: list[Action], h: Hierarchy, horizon: int = 150,
                  graph_every: int = 10, noise_floor: bool = True):
    """compare() as a generator (yields once per simulation step of any branch; returns the result dict)."""
    t0 = time.perf_counter()
    start_t = engine.state.t
    a, det_a = yield from _run_steps(engine.fork(), base_overlay, base_actions, horizon, h, graph_every)
    b, det_b = yield from _run_steps(engine.fork(), int_overlay, int_actions, horizon, h, graph_every)
    a2 = None
    if noise_floor:
        a2, _ = yield from _run_steps(engine.fork(), base_overlay, base_actions, horizon, h, graph_every,
                                      rng_seed=engine.seed * 7919 + start_t + 1)

    n = len(a.ign)
    cls = np.zeros(n, dtype=np.uint8)
    ratio = np.log2((b.ign + 1) / (a.ign + 1))
    cls[(ratio >= 1) & (np.maximum(a.ign, b.ign) >= 3)] = 5
    cls[(ratio <= -1) & (np.maximum(a.ign, b.ign) >= 3)] = 6
    cls[b.in_loop & ~a.in_loop] = 3
    cls[a.in_loop & ~b.in_loop] = 4
    cls[b.reached & ~a.reached] = 1
    cls[a.reached & ~b.reached] = 2

    edges: list[list[int]] = []
    for (x, y) in a.cuts - b.cuts:
        edges.append([x, y, 1])
    for (x, y) in b.cuts - a.cuts:
        edges.append([x, y, 2])
    for (x, y) in b.new - a.new:
        edges.append([x, y, 3])
    for (x, y) in a.new - b.new:
        edges.append([x, y, 4])
    for (x, _, y) in b.reconf - a.reconf:
        edges.append([x, y, 5])
    for (x, _, y) in a.reconf - b.reconf:
        edges.append([x, y, 6])
    gchg = np.flatnonzero(np.abs(a.gate - b.gate) > 1e-9)
    s = engine.state
    for e in gchg[:4000]:
        edges.append([int(s.src[e]), int(s.dst[e]), 7])

    divergence = None
    for i, (x, y) in enumerate(zip(a.first_divergence_sets, b.first_divergence_sets, strict=False)):
        if len(x) != len(y) or not np.array_equal(x, y):
            divergence = start_t + i + 1
            break

    def table(key: str, src: str) -> dict:
        va = getattr(a, src)[key]
        vb = getattr(b, src)[key]
        row = {"baseline": round(va, 5), "intervention": round(vb, 5), "delta": round(vb - va, 5)}
        if a2 is not None:
            noise = abs(getattr(a2, src)[key] - va)
            row["noise_floor"] = round(noise, 5)
            row["exceeds_noise"] = bool(abs(vb - va) > 2 * noise + 1e-9)
        return row

    metrics = {k: table(k, "series") for k in STEP_SERIES}
    metrics.update({k: table(k, "graph") for k in GRAPH_SERIES})

    def setdiff(x: set, y: set) -> int:
        return len(x - y)

    summary = {
        "reachable": {"baseline": int(a.reached.sum()), "intervention": int(b.reached.sum()),
                      "newly_reached": int((cls == 1).sum()), "no_longer_reached": int((cls == 2).sum()),
                      "noise_floor_flips": int((a.reached != a2.reached).sum()) if a2 else None,
                      "exceeds_noise": (bool(int((cls == 1).sum() + (cls == 2).sum()) > 2 * int((a.reached != a2.reached).sum()))
                                        if a2 else None)},
        "ignition_pattern": {"ignites_more": int((cls == 5).sum()), "ignites_less": int((cls == 6).sum()),
                             "total_baseline": int(a.ign.sum()), "total_intervention": int(b.ign.sum())},
        "cuts": {"only_baseline": setdiff(a.cuts, b.cuts), "only_intervention": setdiff(b.cuts, a.cuts),
                 "shared": len(a.cuts & b.cuts)},
        "loops": {"gained": int((b.in_loop & ~a.in_loop).sum()), "lost": int((a.in_loop & ~b.in_loop).sum()),
                  "baseline_fraction": round(float(a.in_loop.mean()), 4),
                  "intervention_fraction": round(float(b.in_loop.mean()), 4)},
        "reconfiguration": {"baseline": len(a.reconf), "intervention": len(b.reconf),
                            "only_intervention": setdiff(b.reconf, a.reconf)},
        "new_connections": {"baseline": len(a.new), "intervention": len(b.new)},
        "gates_changed": int(len(gchg)),
        "first_divergence_step": divergence,
    }
    return {
        "start_t": start_t, "horizon": horizon, "elapsed_s": round(time.perf_counter() - t0, 3),
        "summary": summary, "metrics": metrics,
        "series": {"t": det_a.t, "baseline": det_a.series["ignitions"], "intervention": det_b.series["ignitions"]},
        "node_classes": cls.tolist(), "node_class_names": NODE_CLASSES,
        "cluster_changes": [
            np.round(np.bincount(h.labels[lv], (cls != 0).astype(float), minlength=h.n_clusters(lv))
                     / np.maximum(np.bincount(h.labels[lv], minlength=h.n_clusters(lv)), 1), 4).tolist()
            for lv in range(len(h.labels))],
        "edges": edges[:8000], "edge_class_names": EDGE_CLASSES,
        "fingerprints": {"baseline": a.fingerprint, "intervention": b.fingerprint},
    }
