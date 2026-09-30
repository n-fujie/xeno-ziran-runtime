"""Continuous shape detection over the delta stream.

Cheap descriptors are updated every step from the StepDelta; graph descriptors every ``graph_every``
steps. The detector owns its own RNG (for sampling) and never writes runtime arrays.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from ..lod.hierarchy import Hierarchy
from ..runtime.delta import StepDelta
from ..runtime.state import State
from . import metrics as M

STEP_SERIES = ("ignitions", "penetrations", "amplification", "branching", "branch_points", "reignitions", "returns",
               "decays", "transformations", "topology_change", "memory_dependence", "persistence", "concentration",
               "recurrence")
GRAPH_SERIES = ("reach_dynamic", "reach_horizon", "reach_closure", "loops", "loop_fraction", "largest_loop", "fragmentation",
                "components", "bottleneck_concentration", "asymmetry", "one_way_share", "difference_concentration",
                "path_dependency", "connections")
SIGNATURE_AXES = (("I", "ignition rate"), ("L", "loop membership"), ("R", "return rate"), ("M", "memory"),
                  ("K", "retention"), ("B", "bottleneck share"))
FEATURES = ("ignition_rate", "memory", "retention", "theta_eff", "in_degree", "out_degree", "in_loop", "return_rate",
            "transform_rate", "bottleneck", "difference")
QUIET_GAP = 20  # re-ignition = ignition after at least this many quiet steps
MAX_POINTS = 20000


class ShapeDetector:
    def __init__(self, h: Hierarchy, graph_every: int = 10, window: int = 50, horizon_hops: int = 2):
        self.h = h
        n = h.n
        self.graph_every = graph_every
        self.window = window
        self.hops = horizon_hops
        self.local = h.labels[3]
        self.k_local = h.n_clusters(3)
        self.regional = h.labels[2]
        self.k_regional = h.n_clusters(2)
        self.local_to_regional = h.parents[3]
        self.prev_ignite = np.full(n, -(10**6), dtype=np.int64)
        self.ever = np.zeros(n, dtype=bool)
        self.streak = np.zeros(n, dtype=np.int32)
        self.ign_rate = np.zeros(n)
        self.ret_rate = np.zeros(n)
        self.tr_rate = np.zeros(n)
        self.ring = np.zeros((2 * window, self.k_local), dtype=np.float32)
        self.ring_pos = 0
        self.prev_ign = 0
        self.prev_total: float | None = None
        self.topo_mean, self.topo_var = 0.0, 1.0
        self.patterns: deque[tuple[int, np.ndarray]] = deque(maxlen=400)
        self.rec_ema = 0.0
        self.t: list[int] = []
        self.series: dict[str, list[float]] = {k: [] for k in STEP_SERIES}
        self.t_graph: list[int] = []
        self.graph_series: dict[str, list[float]] = {k: [] for k in GRAPH_SERIES}
        self.events: deque[dict] = deque(maxlen=2000)
        self.last_graph: dict = {}
        self.in_loop = np.zeros(n, dtype=bool)
        self.visits = np.zeros(n)
        self.signatures: list[str] = []
        self.signature_history: dict[str, dict] = {}
        self.embedding: np.ndarray | None = None
        self.embedding_version = 0

    # ------------------------------------------------------------------ per step
    def observe(self, d: StepDelta, state: State) -> dict:
        t = d.t
        fired = d.ignitions.astype(np.int64)
        ign = len(fired)
        pen = len(d.penetrations)
        amplification = d.total_diff / self.prev_total if self.prev_total else 1.0
        self.prev_total = d.total_diff if d.total_diff > 0 else None
        branching = pen / self.prev_ign if self.prev_ign else 0.0
        if pen:
            srcs = state.src[d.penetrations[:, 0]]
            branch_points = int((np.bincount(srcs) >= 2).sum())
        else:
            branch_points = 0
        gap = t - self.prev_ignite[fired]
        reign = int(np.count_nonzero(self.ever[fired] & (gap > QUIET_GAP)))
        self.prev_ignite[fired] = t
        self.ever[fired] = True
        topo = len(d.cuts) + len(d.new_connections) + len(d.removed_connections) + len(d.reconfigurations)
        z = (topo - self.topo_mean) / np.sqrt(self.topo_var + 1e-9)
        if t > 30 and z > 4 and topo >= 4:
            self.events.append({"t": t, "kind": "sudden_topology_change", "size": topo, "z": round(float(z), 1)})
        self.topo_mean = 0.97 * self.topo_mean + 0.03 * topo
        self.topo_var = 0.97 * self.topo_var + 0.03 * (topo - self.topo_mean) ** 2
        active = (t - self.prev_ignite) <= (state.params.refractory_steps + 3)
        self.streak = np.where(active, self.streak + 1, 0)
        persistence = float(np.mean(self.streak >= 30))
        self.ign_rate *= 0.95
        self.ign_rate[fired] += 0.05
        self.ret_rate *= 0.98
        self.ret_rate[d.returns] += 0.02
        self.tr_rate *= 0.98
        if len(d.transformations):
            self.tr_rate[d.transformations[:, 0]] += 0.02
        row = np.bincount(self.local[fired], minlength=self.k_local).astype(np.float32)
        self.ring[self.ring_pos % len(self.ring)] = row
        self.ring_pos += 1
        recent = self._window_sum(self.window)
        concentration = M.gini(recent)
        recurrence = self._recurrence(t)
        if ign > 4 * max(self.prev_ign, 1) and ign > 50:
            self.events.append({"t": t, "kind": "amplification_burst", "from": self.prev_ign, "to": ign})
        if self.prev_ign > 50 and ign < 0.2 * self.prev_ign:
            self.events.append({"t": t, "kind": "sudden_decay", "from": self.prev_ign, "to": ign})
        self.prev_ign = ign
        rec: dict[str, Any] = {
            "ignitions": ign, "penetrations": pen, "amplification": round(float(amplification), 4),
            "branching": round(float(branching), 4), "branch_points": branch_points, "reignitions": reign,
            "returns": len(d.returns), "decays": len(d.decays), "transformations": len(d.transformations),
            "topology_change": topo, "memory_dependence": round(d.memory_dependent_ignitions / ign, 4) if ign else 0.0,
            "persistence": round(persistence, 4), "concentration": round(concentration, 4),
            "recurrence": round(self.rec_ema, 4),
        }
        if recurrence is not None:
            self.events.append({"t": t, "kind": "recurrence", "gap": recurrence})
        self.t.append(t)
        for k in STEP_SERIES:
            self.series[k].append(rec[k])
        if len(self.t) > MAX_POINTS:
            self.t = self.t[-MAX_POINTS:]
            for k in STEP_SERIES:
                self.series[k] = self.series[k][-MAX_POINTS:]
        if self.graph_every and t % self.graph_every == 0:
            rec["graph"] = self.graph_pass(state, t)
        return rec

    def _window_sum(self, w: int) -> np.ndarray:
        k = min(w, self.ring_pos, len(self.ring))
        idx = [(self.ring_pos - 1 - i) % len(self.ring) for i in range(k)]
        return self.ring[idx].sum(0) if k else np.zeros(self.k_local, dtype=np.float32)

    def _recurrence(self, t: int) -> int | None:
        """Attractor-like recurrence: the coarse regional activity pattern of the last 5 steps
        matches (Jaccard ≥ 0.85) a pattern seen at least 25 steps earlier."""
        act = np.bincount(self.local_to_regional, weights=self._window_sum(5), minlength=self.k_regional)
        if act.sum() <= 0:
            self.rec_ema *= 0.98
            return None
        bits = act > np.median(act[act > 0]) if (act > 0).sum() > 4 else act > 0
        gap = None
        best = 0.0
        for t0, b0 in self.patterns:
            if t - t0 < 25:
                continue
            inter = np.count_nonzero(bits & b0)
            uni = np.count_nonzero(bits | b0)
            j = inter / uni if uni else 0.0
            if j > best:
                best, gap = j, t - t0
        hit = best >= 0.85
        self.rec_ema = 0.98 * self.rec_ema + 0.02 * float(hit)
        if t % 5 == 0:
            self.patterns.append((t, bits))
        return gap if hit and t % 25 == 0 else None

    # ------------------------------------------------------------------ periodic graph pass
    def graph_pass(self, state: State, t: int) -> dict:
        rng = np.random.default_rng(t)
        g = M.transition_graph(state)
        active = np.flatnonzero((t - self.prev_ignite) <= 2).astype(np.int64)
        hr = M.horizon_reach(g, active, self.hops)
        cr = M.closure_reach(g, active)
        lp = M.loops(state)
        prev_loop = self.in_loop
        self.in_loop = lp["in_loop"]
        gained = int(np.count_nonzero(self.in_loop & ~prev_loop))
        lost = int(np.count_nonzero(~self.in_loop & prev_loop))
        fr = M.fragmentation(state)
        srcs = rng.choice(active, size=min(8, len(active)), replace=False) if len(active) else active
        self.visits = 0.7 * self.visits + M.bottlenecks(g, srcs, rng)
        asym = M.asymmetry(state)
        a, b = self._window_sum(self.window), self._pair_window()
        pdep = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0
        out = {
            "reach_dynamic": round(float(np.mean((t - self.prev_ignite) <= self.window)), 4),
            "reach_horizon": round(float(hr.mean()), 4), "reach_closure": round(float(cr.mean()), 4),
            "loops": lp["n_loops"], "loop_fraction": round(lp["loop_fraction"], 4), "largest_loop": lp["largest_loop"],
            "fragmentation": round(fr["fragmentation"], 4), "components": fr["components"],
            "bottleneck_concentration": round(M.top_share(self.visits, 0.01), 4),
            "asymmetry": round(asym["asymmetry"], 4), "one_way_share": round(asym["one_way_share"], 4),
            "difference_concentration": round(M.gini(state.diff), 4), "path_dependency": round(pdep, 4),
            "connections": int(state.alive.sum()),
        }
        if self.last_graph:
            big = max(20, int(0.03 * state.n))
            if gained >= big:
                self.events.append({"t": t, "kind": "loop_formation", "configurations": gained})
            if lost >= big:
                self.events.append({"t": t, "kind": "loop_dissolution", "configurations": lost})
            if fr["components"] - self.last_graph.get("components", fr["components"]) >= 3:
                self.events.append({"t": t, "kind": "fragmentation", "components": fr["components"]})
        self.last_graph = out
        self.t_graph.append(t)
        for k in GRAPH_SERIES:
            self.graph_series[k].append(out[k])
        self._signatures(state, t)
        self._embed(state)
        return out

    def _pair_window(self) -> np.ndarray:
        """Cluster activity in the window preceding the current one (lag = window)."""
        w = self.window
        k = min(w, max(0, self.ring_pos - w))
        idx = [(self.ring_pos - 1 - w - i) % len(self.ring) for i in range(k)]
        return self.ring[idx].sum(0) if k else np.zeros(self.k_local, dtype=np.float32)

    # ------------------------------------------------------------------ features, signatures, embedding
    def features(self, state: State) -> np.ndarray:
        n = state.n
        m = state.alive
        indeg = np.bincount(state.dst[m], minlength=n)
        outdeg = np.bincount(state.src[m], minlength=n)
        vis = self.visits / (self.visits.max() + 1e-9)
        return np.stack([self.ign_rate, state.memory, state.retention, state.theta_eff(), indeg, outdeg,
                         self.in_loop.astype(float), self.ret_rate, self.tr_rate, vis, state.diff], 1)

    def _signatures(self, state: State, t: int) -> None:
        lab, k = self.regional, self.k_regional
        cnt = np.maximum(np.bincount(lab, minlength=k), 1)

        def mean(x: np.ndarray) -> np.ndarray:
            return np.bincount(lab, x, minlength=k) / cnt

        axes = np.stack([mean(self.ign_rate), mean(self.in_loop.astype(float)), mean(self.ret_rate),
                         mean(state.memory), mean(state.retention),
                         np.bincount(lab, self.visits, minlength=k) / (self.visits.sum() + 1e-9)], 1)
        lo, hi = np.quantile(axes, [1 / 3, 2 / 3], axis=0)
        levels = (axes > lo).astype(int) + (axes > hi).astype(int)
        self.signatures = [" ".join(f"{a}{v}" for (a, _), v in zip(SIGNATURE_AXES, row, strict=True)) for row in levels]
        now = Counter(self.signatures)
        for sig, c in now.items():
            rec = self.signature_history.setdefault(sig, {"first_seen": t, "passes": 0, "max_clusters": 0})
            rec["passes"] += 1
            rec["last_seen"] = t
            rec["clusters_now"] = c
            rec["max_clusters"] = max(rec["max_clusters"], c)
        for sig, rec in self.signature_history.items():
            if sig not in now:
                rec["clusters_now"] = 0

    def recurrent_shapes(self, limit: int = 16) -> list[dict]:
        """Signatures that recur across clusters (≥2 at once) or across time (≥3 passes)."""
        out = []
        for sig, rec in self.signature_history.items():
            if rec["max_clusters"] >= 2 or rec["passes"] >= 3:
                clusters = [self.h.address(2, i) for i, s in enumerate(self.signatures) if s == sig]
                out.append({"signature": sig, **rec, "clusters": clusters[:32],
                            "axes": {a: int(sig.split()[i][1]) for i, (a, _) in enumerate(SIGNATURE_AXES)}})
        out.sort(key=lambda r: (-r["clusters_now"], -r["passes"]))
        return out[:limit]

    def _embed(self, state: State) -> None:
        """Abstract Shape Space: PCA of standardized per-configuration descriptor vectors."""
        x = self.features(state)
        x = (x - x.mean(0)) / (x.std(0) + 1e-9)
        c = np.cov(x, rowvar=False)
        vals, vecs = np.linalg.eigh(c)
        comp = x @ vecs[:, ::-1][:, :2]
        if self.embedding is not None:
            for j in range(2):
                if np.dot(comp[:, j], self.embedding[:, j]) < 0:
                    comp[:, j] = -comp[:, j]
        # robust scaling so outliers do not collapse the view
        lo, hi = np.percentile(comp, [1, 99], axis=0)
        comp = np.clip(comp, lo - (hi - lo) * 0.1, hi + (hi - lo) * 0.1)
        self.embedding = comp
        self.embedding_version += 1
        self.embedding_loadings = {FEATURES[i]: [round(float(vecs[i, -1]), 3), round(float(vecs[i, -2]), 3)]
                                   for i in range(len(FEATURES))}

    def summary(self) -> dict:
        last = {k: (v[-1] if v else None) for k, v in self.series.items()}
        return {"t": self.t[-1] if self.t else 0, "step": last, "graph": self.last_graph,
                "events": list(self.events)[-50:], "recurrent_shapes": self.recurrent_shapes(),
                "axes": [{"key": a, "descriptor": d} for a, d in SIGNATURE_AXES],
                "embedding_loadings": getattr(self, "embedding_loadings", {})}

    def truncate(self, t: int) -> None:
        """After a rewind: drop series beyond t (descriptors re-accumulate from there)."""
        keep = [i for i, x in enumerate(self.t) if x <= t]
        self.t = [self.t[i] for i in keep]
        for k in STEP_SERIES:
            self.series[k] = [self.series[k][i] for i in keep]
        keep = [i for i, x in enumerate(self.t_graph) if x <= t]
        self.t_graph = [self.t_graph[i] for i in keep]
        for k in GRAPH_SERIES:
            self.graph_series[k] = [self.graph_series[k][i] for i in keep]
        self.events = deque([e for e in self.events if e["t"] <= t], maxlen=2000)
        self.prev_ignite = np.minimum(self.prev_ignite, t)
