"""Operational-shape tracker: model-light, vocabulary-free description of a running field.

It reads only the runtime's own step records (``StepDelta``) and the current graph. It assumes no agent, no fixed
boundary, no latent-state vocabulary, no generative model and no policy identity. Configurations are opaque
indices; clusters are re-derived from the current activity every window.

Per window of W steps it records:

    local_diff          mean |a_i(w) − a_i(w−1)| (a = per-configuration ignition rate)
    transition_diff     connection events (cut, new, removed, retired, reconfigured) + gate changes
    coupling_change     Σ|Δweight| over connections alive in both windows / alive
    persistence         Jaccard of active sets of consecutive windows
    retention           mean memory
    recurrence          max cosine similarity of a(w) with any a(w−k), k ≥ 5
    components          active components (active nodes, currently reachable connections; size ≥ 5)
    splits / merges     component matching between windows (Jaccard ≥ 0.2): one→many = split, many→one = merge
    reachable           share of configurations reachable from the probe set within 2 hops (shapes.metrics)
    reignitions         ignitions after ≥ QUIET_GAP quiet steps (shapes.detector definition)

``finalize`` turns the series into change detection (z > Z_DETECT against pre-onset windows), localisation
(per-configuration change score, ROC-AUC against a ground-truth footprint), propagation depth (hop distance from
the footprint to the farthest strongly changed configuration), reconfiguration magnitude and pattern recurrence.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.sparse import csgraph
from xzr.shapes.detector import QUIET_GAP
from xzr.shapes.metrics import horizon_reach, transition_graph

Z_DETECT = 4.0
SERIES = ("local_diff", "transition_diff", "coupling_change", "persistence", "retention", "recurrence", "components",
          "splits", "merges", "reachable", "reignitions", "reignitions_T")
DETECT_FEATURES = ("local_diff", "transition_diff", "coupling_change", "persistence", "reachable", "components")


def auc(scores: np.ndarray, positive: np.ndarray) -> float | None:
    """ROC-AUC with ties counted 1/2 (Mann–Whitney)."""
    pos = scores[positive]
    neg = scores[~positive]
    if len(pos) == 0 or len(neg) == 0:
        return None
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order))
    allv = np.concatenate([pos, neg])[order]
    i = 0
    r = np.arange(1, len(order) + 1, dtype=float)
    while i < len(allv):  # average ranks for ties
        j = i
        while j + 1 < len(allv) and allv[j + 1] == allv[i]:
            j += 1
        r[i:j + 1] = (i + j + 2) / 2
        i = j + 1
    ranks[order] = r
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


class OperationalTracker:
    def __init__(self, world, window: int = 20, probe_nodes: np.ndarray | None = None):
        self.w = world
        self.W = window
        n = world.cfg.n
        self.n = n
        self.probe = world.T if probe_nodes is None else probe_nodes
        self.ign = np.zeros(n)
        self.ev = 0
        self.re = 0
        self.re_T = 0
        self.last = np.full(n, -(10**6))
        self.ever = np.zeros(n, bool)
        self.inT = np.zeros(n, bool)
        self.inT[world.T] = True
        self.prev_a: np.ndarray | None = None
        self.prev_w: np.ndarray | None = None
        self.prev_alive: np.ndarray | None = None
        self.prev_comps: list[np.ndarray] = []
        self.A: list[np.ndarray] = []      # per-window activity vectors (float32)
        self.t: list[int] = []
        self.s: dict[str, list[float]] = {k: [] for k in SERIES}
        self.edges_at: dict[int, set] = {}
        world.listeners.append(self.observe)

    def mark_edges(self, label: int) -> None:
        st = self.w.state
        m = st.alive
        self.edges_at[label] = set(zip(st.src[m].tolist(), st.dst[m].tolist(), strict=True))

    def observe(self, d, st) -> None:
        f = d.ignitions
        np.add.at(self.ign, f, 1.0)
        gap = d.t - self.last[f]
        re = self.ever[f] & (gap > QUIET_GAP)
        self.re += int(re.sum())
        self.re_T += int((re & self.inT[f]).sum())
        self.last[f] = d.t
        self.ever[f] = True
        self.ev += len(d.cuts) + len(d.new_connections) + len(d.removed_connections) + len(d.retired) \
            + len(d.reconfigurations) + len(d.gate_edge)
        if d.t % self.W == 0:
            self._window(st)

    def _window(self, st) -> None:
        a = (self.ign / self.W).astype(np.float32)
        s = self.s
        act = a > 0
        if self.prev_a is not None:
            s["local_diff"].append(float(np.abs(a - self.prev_a).mean()))
            pa = self.prev_a > 0
            u = (act | pa).sum()
            s["persistence"].append(float((act & pa).sum() / u) if u else 1.0)
        else:
            s["local_diff"].append(0.0)
            s["persistence"].append(1.0)
        s["transition_diff"].append(float(self.ev))
        both = st.alive & (self.prev_alive if self.prev_alive is not None else st.alive)
        s["coupling_change"].append(float(np.abs(st.weight[both] - self.prev_w[both]).sum() / max(both.sum(), 1))
                                    if self.prev_w is not None else 0.0)
        s["retention"].append(float(st.memory.mean()))
        rec = 0.0
        if len(self.A) >= 5:
            H = np.stack(self.A[:-4])
            na = np.linalg.norm(a) + 1e-12
            rec = float((H @ a / (np.linalg.norm(H, axis=1) * na + 1e-12)).max())
        s["recurrence"].append(rec)
        comps = self._components(st, act)
        sp_, mg = self._match(self.prev_comps, comps)
        s["components"].append(float(len(comps)))
        s["splits"].append(float(sp_))
        s["merges"].append(float(mg))
        g = transition_graph(st)
        s["reachable"].append(float(horizon_reach(g, self.probe, 2).mean()))
        s["reignitions"].append(float(self.re))
        s["reignitions_T"].append(float(self.re_T))
        self.A.append(a)
        self.t.append(int(st.t))
        self.prev_a, self.prev_w, self.prev_alive, self.prev_comps = a, st.weight.copy(), st.alive.copy(), comps
        self.ign[:] = 0
        self.ev = self.re = self.re_T = 0

    def _components(self, st, act) -> list[np.ndarray]:
        m = st.reachable_mask()
        m &= act[st.src] & act[st.dst]
        idx = np.flatnonzero(act)
        if len(idx) == 0:
            return []
        g = sp.csr_matrix((np.ones(int(m.sum())), (st.src[m], st.dst[m])), shape=(self.n, self.n))
        k, lab = csgraph.connected_components(g, directed=False)
        lab = lab[idx]
        sizes = np.bincount(lab)
        return [idx[lab == c] for c in np.flatnonzero(sizes >= 5)]

    @staticmethod
    def _match(prev: list[np.ndarray], cur: list[np.ndarray]) -> tuple[int, int]:
        if not prev or not cur:
            return 0, 0
        links = np.zeros((len(prev), len(cur)), bool)
        for i, p in enumerate(prev):
            for j, c in enumerate(cur):
                inter = len(np.intersect1d(p, c, assume_unique=True))
                if inter and inter / (len(p) + len(c) - inter) >= 0.2:
                    links[i, j] = True
        return int((links.sum(1) >= 2).sum()), int((links.sum(0) >= 2).sum())

    # ------------------------------------------------------------------ summary
    def finalize(self, t_p: int, t_r: int, footprint: list[int], pre_from: int = 200) -> dict:
        t = np.asarray(self.t)
        S = {k: np.asarray(v) for k, v in self.s.items()}
        A = np.stack(self.A) if self.A else np.zeros((0, self.n))
        pre = (t > pre_from) & (t <= t_p)
        pert = (t > t_p) & (t <= t_r)
        rec = t > t_r
        out: dict = {}
        # change detection
        F = np.stack([S[k] for k in DETECT_FEATURES], 1)
        mu = F[pre].mean(0)
        sd = F[pre].std(0, ddof=1) + 1e-9 + 0.05 * np.abs(mu)
        z = np.abs((F - mu) / sd).max(1)
        out["z_max_pre"] = float(z[pre].max()) if pre.any() else None
        out["detect_onset"] = _first(t, z, t_p, t_p + 100)
        out["detect_revert"] = _first(t, z, t_r, t_r + 100)
        out["world_change_score"] = float(np.mean(z[pert][:5])) if pert.any() else None
        out["false_alarms_pre"] = int((z[pre] > Z_DETECT).sum())
        # localisation and propagation (score = change of each configuration's rate vs its pre-onset distribution)
        if pre.sum() >= 3 and pert.sum() >= 1:
            mu_i, sd_i = A[pre].mean(0), A[pre].std(0, ddof=1)
            score = np.abs(A[pert][:5].mean(0) - mu_i) / (sd_i + 0.05)
            fp = np.zeros(self.n, bool)
            if len(footprint):
                fp[np.asarray(footprint, int)] = True
            out["localisation_auc"] = auc(score, fp) if 0 < fp.sum() < self.n else None
            out["propagation_depth"] = self._depth(fp, score > 3.0) if fp.any() and fp.sum() < self.n else None
            out["affected_share"] = float((score > 3.0).mean())
        # operational counts per phase
        for name, m in (("pre", pre), ("pert", pert), ("rec", rec)):
            for k in ("splits", "merges", "reignitions", "reignitions_T", "components", "persistence", "reachable",
                      "recurrence", "local_diff", "transition_diff", "coupling_change", "retention"):
                out[f"{k}_{name}"] = float(S[k][m].mean()) if m.any() else None
        out["reachable_change"] = (out["reachable_pert"] - out["reachable_pre"]) if out.get("reachable_pre") is not None else None
        if t_p in self.edges_at and t_r in self.edges_at:
            a, b = self.edges_at[t_p], self.edges_at[t_r]
            out["reconfiguration_magnitude"] = 1 - len(a & b) / max(len(a | b), 1)
        out["_A"] = A
        out["_t"] = t
        return out

    def _depth(self, src_mask: np.ndarray, affected: np.ndarray) -> int:
        s, d = self.w.adj0
        g = sp.csr_matrix((np.ones(len(s)), (s, d)), shape=(self.n, self.n))
        g = ((g + g.T) > 0).astype(float)
        dist = csgraph.shortest_path(g, unweighted=True, indices=np.flatnonzero(src_mask)[:64], directed=False).min(0) \
            if src_mask.sum() <= 64 else _multi_source(g, src_mask)
        far = dist[affected & np.isfinite(dist)]
        return int(far.max()) if len(far) else 0


def _multi_source(g, mask) -> np.ndarray:
    n = g.shape[0]
    aug = sp.vstack([sp.hstack([g, sp.csr_matrix((n, 1))]),
                     sp.hstack([sp.csr_matrix((np.ones(int(mask.sum())), (np.zeros(int(mask.sum()), int), np.flatnonzero(mask))),
                                              shape=(1, n)), sp.csr_matrix((1, 1))])]).tocsr()
    aug = ((aug + aug.T) > 0).astype(float)
    d = csgraph.shortest_path(aug, unweighted=True, indices=[n], directed=False)[0, :n] - 1
    return d


def _first(t: np.ndarray, z: np.ndarray, start: int, end: int) -> dict:
    m = (t > start) & (t <= end)
    hit = np.flatnonzero(m & (z > Z_DETECT))
    return {"hit": bool(len(hit)), "delay": int(t[hit[0]] - start) if len(hit) else None}


def sensor_only_detection(rows: list[dict], t_p: int, t_r: int, pre_from: int = 200) -> dict:
    """The same change detection, restricted to the comparator's channels (the aggregate reading and the
    per-channel reading change). Separates descriptive form from information access."""
    t = np.array([r["t"] for r in rows])
    X = np.array([r["x"] for r in rows], float)
    X = np.where(np.isfinite(X), X, 0.0)
    agg = X.mean(1)
    dx = np.r_[0.0, np.abs(np.diff(X, axis=0)).mean(1)]
    F = np.stack([agg, dx], 1)
    pre = (t > pre_from) & (t <= t_p)
    pert = (t > t_p) & (t <= t_r)
    mu, sd = F[pre].mean(0), F[pre].std(0, ddof=1) + 1e-9 + 0.05 * np.abs(F[pre].mean(0))
    z = np.abs((F - mu) / sd).max(1)
    return {"detect_onset": _first(t, z, t_p, t_p + 100), "detect_revert": _first(t, z, t_r, t_r + 100),
            "world_change_score": float(np.mean(z[pert][:10])) if pert.any() else None,
            "false_alarms_pre": int((z[pre] > Z_DETECT).sum())}
