"""Trajectory recording and trajectory distances between two runs.

A :class:`Recording` keeps, per step, event counts and ignition sets; periodically, snapshots of connection
structure and state distributions; and the shape detector's step and graph descriptor series and regional
signatures. Distances compare *temporal and topological structure*, not only final aggregates:

* event-sequence distance      windowed event-count series per kind; per-step ignition-set Jaccard distance
* graph-edit distance (approx.) symmetric difference of connection sets at aligned snapshots
* state-distribution distance  Wasserstein-1 between difference / memory distributions at aligned snapshots
* shape-signature distance     fraction of regional clusters whose signature differs, per graph pass
* criterion distances          windowed trajectory distance of the descriptor series behind each equivalence
                               criterion (reachability, branching, closure, loops, fragmentation, concentration,
                               persistence, amplification regime, path dependence)
* intervention-response distance  how differently two runtimes respond to the same intervention battery

All distances are in [0, 1] (0 = identical) except where noted, so they can be compared against noise floors.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import wasserstein_distance

from ..runtime.delta import EVENT_KINDS, StepDelta
from ..runtime.state import State

WINDOWS = 8

# equivalence criteria → descriptor series (step series 's:', graph series 'g:')
CRITERIA: dict[str, tuple[str, ...]] = {
    "reachable_structure": ("g:reach_dynamic", "g:reach_horizon", "g:reach_closure"),
    "branching": ("s:branching", "s:branch_points"),
    "closure": ("g:loop_fraction",),
    "recurrent_loops": ("g:loops", "g:largest_loop", "s:recurrence"),
    "fragmentation": ("g:fragmentation", "g:components"),
    "concentration": ("s:concentration", "g:difference_concentration"),
    "persistence": ("s:persistence",),
    "amplification_regime": ("s:ignitions", "s:amplification"),
    "path_dependence": ("g:path_dependency",),
}


@dataclass
class Recording:
    n: int
    snapshot_every: int
    counts: dict[str, list[int]] = field(default_factory=lambda: {k: [] for k in EVENT_KINDS})
    ignitions: list[np.ndarray] = field(default_factory=list)
    reached: np.ndarray | None = None
    snap_t: list[int] = field(default_factory=list)
    snap_edges: list[np.ndarray] = field(default_factory=list)
    snap_diff: list[np.ndarray] = field(default_factory=list)
    snap_memory: list[np.ndarray] = field(default_factory=list)
    series: dict[str, list[float]] = field(default_factory=dict)
    signatures: list[list[str]] = field(default_factory=list)
    ms_per_step: float = 0.0
    state_bytes: int = 0
    hashes: dict[str, str] = field(default_factory=dict)

    def record(self, d: StepDelta, state: State) -> None:
        for k, v in d.counts().items():
            self.counts[k].append(v)
        self.ignitions.append(d.ignitions.copy())
        if self.reached is None:
            self.reached = np.zeros(self.n, dtype=bool)
        self.reached[d.ignitions] = True
        if d.t % self.snapshot_every == 0:
            self.snap_t.append(d.t)
            a = state.alive
            self.snap_edges.append(np.sort(state.src[a].astype(np.int64) * self.n + state.dst[a]))
            self.snap_diff.append(state.diff.astype(np.float32).copy())
            self.snap_memory.append(state.memory.astype(np.float32).copy())

    def attach_detector(self, det) -> None:
        self.series = {**{f"s:{k}": list(map(float, v)) for k, v in det.series.items()},
                       **{f"g:{k}": list(map(float, v)) for k, v in det.graph_series.items()}}


def _windows(x: Sequence[float] | np.ndarray, w: int = WINDOWS) -> np.ndarray:
    a = np.asarray(x, dtype=np.float64)
    if len(a) == 0:
        return np.zeros(w)
    return np.array([c.mean() if len(c) else 0.0 for c in np.array_split(a, w)])


def series_distance(a: Sequence[float], b: Sequence[float]) -> float:
    """Windowed relative distance of two time series (temporal structure, scale-free)."""
    wa, wb = _windows(a), _windows(b)
    den = np.abs(wa).mean() + np.abs(wb).mean()
    if den <= 1e-12:
        return 0.0
    return float(min(1.0, np.abs(wa - wb).mean() / den))


def event_sequence_distance(a: Recording, b: Recording) -> dict:
    per_kind = {k: series_distance(a.counts[k], b.counts[k]) for k in EVENT_KINDS}
    active = [v for k, v in per_kind.items() if sum(a.counts[k]) + sum(b.counts[k]) > 0]
    jac = []
    first = None
    for i, (x, y) in enumerate(zip(a.ignitions, b.ignitions, strict=False)):
        if first is None and (len(x) != len(y) or not np.array_equal(x, y)):
            first = i + 1
        u = len(np.union1d(x, y))
        jac.append(0.0 if u == 0 else 1.0 - len(np.intersect1d(x, y, assume_unique=True)) / u)
    return {"counts": float(np.mean(active)) if active else 0.0, "per_kind": per_kind,
            "ignition_sets": float(np.mean(jac)) if jac else 0.0, "first_divergence": first}


def graph_edit_distance(a: Recording, b: Recording) -> float:
    """Approximate graph edit distance: |E_A Δ E_B| / |E_A ∪ E_B| at aligned snapshots (configurations aligned)."""
    d = []
    for x, y in zip(a.snap_edges, b.snap_edges, strict=False):
        u = len(np.union1d(x, y))
        d.append(0.0 if u == 0 else len(np.setxor1d(x, y)) / u)
    return float(np.mean(d)) if d else 0.0


def state_distribution_distance(a: Recording, b: Recording) -> dict:
    def w1(xs: list[np.ndarray], ys: list[np.ndarray]) -> float:
        out = []
        for x, y in zip(xs, ys, strict=False):
            scale = max(float(np.mean(np.abs(x)) + np.mean(np.abs(y))), 1e-9)
            out.append(min(1.0, wasserstein_distance(x, y) / scale))
        return float(np.mean(out)) if out else 0.0

    def aligned(xs: list[np.ndarray], ys: list[np.ndarray]) -> float:
        out = []
        for x, y in zip(xs, ys, strict=False):
            den = float(np.abs(x).sum() + np.abs(y).sum())
            out.append(0.0 if den == 0 else float(np.abs(x - y).sum() / den))
        return float(np.mean(out)) if out else 0.0

    return {"difference_w1": w1(a.snap_diff, b.snap_diff), "memory_w1": w1(a.snap_memory, b.snap_memory),
            "difference_aligned": aligned(a.snap_diff, b.snap_diff),
            "memory_aligned": aligned(a.snap_memory, b.snap_memory)}


def signature_distance(a: Recording, b: Recording) -> float:
    """Distribution distance between regional signature multisets per graph pass (total variation)."""
    d = []
    for x, y in zip(a.signatures, b.signatures, strict=False):
        keys = set(x) | set(y)
        cx = {k: x.count(k) / max(len(x), 1) for k in keys}
        cy = {k: y.count(k) / max(len(y), 1) for k in keys}
        d.append(0.5 * sum(abs(cx[k] - cy[k]) for k in keys))
    return float(np.mean(d)) if d else 0.0


def criterion_distances(a: Recording, b: Recording) -> dict[str, float]:
    out = {}
    for crit, keys in CRITERIA.items():
        vals = [series_distance(a.series.get(k, []), b.series.get(k, [])) for k in keys]
        out[crit] = float(np.mean(vals))
    ra = a.reached if a.reached is not None else np.zeros(a.n, bool)
    rb = b.reached if b.reached is not None else np.zeros(b.n, bool)
    u = (ra | rb).sum()
    out["reachable_structure"] = float(np.mean([out["reachable_structure"],
                                                0.0 if u == 0 else (ra ^ rb).sum() / u]))
    return out


def response_vector(base: Recording, intervened: Recording) -> np.ndarray:
    """What an intervention changed: windowed descriptor differences (intervened − base) for every criterion."""
    parts = []
    for keys in CRITERIA.values():
        for k in keys:
            wa, wb = _windows(base.series.get(k, [])), _windows(intervened.series.get(k, []))
            scale = max(np.abs(wa).mean(), np.abs(wb).mean(), 1e-9)
            parts.append((wb - wa) / scale)
    return np.concatenate(parts) if parts else np.zeros(0)


def response_distance(ra: np.ndarray, rb: np.ndarray) -> float:
    den = np.abs(ra).sum() + np.abs(rb).sum()
    return 0.0 if den <= 1e-12 else float(min(1.0, np.abs(ra - rb).sum() / den))


def compare_recordings(a: Recording, b: Recording) -> dict:
    ev = event_sequence_distance(a, b)
    return {
        "event_sequence": ev["counts"], "event_per_kind": ev["per_kind"], "ignition_sets": ev["ignition_sets"],
        "first_divergence": ev["first_divergence"], "graph_edit": graph_edit_distance(a, b),
        **state_distribution_distance(a, b), "signature": signature_distance(a, b),
        "criteria": criterion_distances(a, b),
    }
