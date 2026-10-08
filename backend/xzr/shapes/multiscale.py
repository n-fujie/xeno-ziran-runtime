"""Multi-resolution observation of a running field (read-only).

Resolutions:
    exact    per-step state signature (difference sum, ignitions, alive connections) and per-window fingerprints
    node     per-configuration features
    local    finest hierarchy clusters (512 by address depth 9)
    meso     32 hierarchy clusters (address depth 2)
    macro    8 hierarchy clusters (address depth 1)
    global   whole-field aggregates

Features per configuration, averaged over a window: activity (ignitions per step), memory, difference, out-degree
(alive connections). Cluster values are means over member configurations. The observer never writes runtime
arrays.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np

from ..lod.hierarchy import Hierarchy
from ..runtime.delta import StepDelta
from ..runtime.state import State

SCALES = ("node", "local", "meso", "macro", "global")
FEATURES = ("activity", "memory", "difference", "degree")
GLOBAL_KEYS = ("activity", "memory", "difference", "degree", "new_connections", "cuts", "removed", "reconfigurations",
               "memory_dependent_share", "penetrations", "reachable_share", "alive_connections")
LEVEL_OF = {"local": 3, "meso": 1, "macro": 0}  # index into hierarchy.labels (depths 9, 5, 3 bits)


def labels_for(h: Hierarchy) -> dict[str, np.ndarray]:
    return {s: h.labels[lv] for s, lv in LEVEL_OF.items()}


def aggregate(node_values: np.ndarray, labels: np.ndarray, k: int) -> np.ndarray:
    """Mean of node values (…, n) per cluster → (…, k)."""
    cnt = np.bincount(labels, minlength=k).astype(float)
    cnt[cnt == 0] = 1.0
    if node_values.ndim == 1:
        return np.bincount(labels, node_values, minlength=k) / cnt
    out = np.empty((*node_values.shape[:-1], k))
    flat = node_values.reshape(-1, node_values.shape[-1])
    of = out.reshape(-1, k)
    for i in range(flat.shape[0]):
        of[i] = np.bincount(labels, flat[i], minlength=k) / cnt
    return out


def _fp(state: State) -> str:
    h = hashlib.sha1()
    a = state.alive
    for arr in (state.diff, state.memory, state.theta_mod, state.src[a], state.dst[a], state.weight[a]):
        h.update(np.ascontiguousarray(arr).tobytes())
    return h.hexdigest()[:16]


@dataclass
class Frame:
    """One observation window: node features (F, n) and global aggregates."""

    t: int
    node: np.ndarray
    glob: dict[str, float]
    fingerprint: str


@dataclass
class MultiScaleObserver:
    n: int
    window: int
    sample_every: int = 5
    target: np.ndarray | None = None  # optional node set traced per step (e.g. where interventions land)
    frames: list[Frame] = field(default_factory=list)
    exact: list[tuple[float, int, int]] = field(default_factory=list)  # per step signature
    exact_macro: list[np.ndarray] = field(default_factory=list)  # per step difference sum per macro cluster
    exact_target: list[float] = field(default_factory=list)
    keep_frames: bool = True
    macro_labels: np.ndarray | None = None

    def __post_init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self._ign = np.zeros(self.n)
        self._mem = np.zeros(self.n)
        self._diff = np.zeros(self.n)
        self._deg = np.zeros(self.n)
        self._samples = 0
        self._steps = 0
        self._g = {k: 0.0 for k in ("new_connections", "cuts", "removed", "reconfigurations", "penetrations",
                                    "memory_dependent", "ignitions")}

    def observe(self, d: StepDelta, s: State) -> Frame | None:
        self._steps += 1
        np.add.at(self._ign, d.ignitions, 1.0)
        g = self._g
        g["new_connections"] += len(d.new_connections)
        g["cuts"] += len(d.cuts)
        g["removed"] += len(d.removed_connections) + len(d.retired)
        g["reconfigurations"] += len(d.reconfigurations)
        g["penetrations"] += len(d.penetrations)
        g["memory_dependent"] += int(d.memory_dependent_ignitions)
        g["ignitions"] += len(d.ignitions)
        self.exact.append((float(s.diff.sum()), int(len(d.ignitions)), int(s.alive.sum())))
        if self.macro_labels is not None:
            self.exact_macro.append(np.bincount(self.macro_labels, s.diff, minlength=8).astype(np.float64))
        if self.target is not None:
            self.exact_target.append(float(s.diff[self.target].sum()))
        if d.t % self.sample_every == 0:
            self._mem += s.memory
            self._diff += s.diff
            a = s.alive
            self._deg += np.bincount(s.src[a], minlength=self.n)
            self._samples += 1
        if d.t % self.window:
            return None
        k = max(self._samples, 1)
        node = np.stack([self._ign / self._steps, self._mem / k, self._diff / k, self._deg / k]).astype(np.float32)
        steps = self._steps
        glob = {"activity": float(node[0].mean()), "memory": float(node[1].mean()), "difference": float(node[2].mean()),
                "degree": float(node[3].mean()),
                **{k2: g[k2] / steps for k2 in ("new_connections", "cuts", "removed", "reconfigurations", "penetrations")},
                "memory_dependent_share": g["memory_dependent"] / max(g["ignitions"], 1.0),
                "reachable_share": float(s.reachable_mask().sum() / max(s.alive.sum(), 1)),
                "alive_connections": float(s.alive.sum())}
        fr = Frame(d.t, node, glob, _fp(s))
        if self.keep_frames:
            self.frames.append(fr)
        self._reset()
        return fr


def scale_values(frame_node: np.ndarray, labels: dict[str, np.ndarray], scale: str) -> np.ndarray:
    """(F, units) feature matrix of one window at a resolution."""
    if scale == "node":
        return frame_node
    if scale == "global":
        return frame_node.mean(axis=1, keepdims=True)
    lab = labels[scale]
    return aggregate(frame_node, lab, int(lab.max()) + 1)


def window_distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Per-feature normalized L1 distance between two (F, units) matrices: Σ|a−b| / Σ(|a|+|b|)/2 (0 = identical,
    ~1 = unrelated)."""
    num = np.abs(a - b).sum(axis=1)
    den = (np.abs(a) + np.abs(b)).sum(axis=1) / 2 + 1e-12
    return num / den
