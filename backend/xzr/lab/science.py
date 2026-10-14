"""Heterogeneous scientific systems in the physical laboratory (M4–M7).

A scientific system observes chambers through its own sensors, selects experiments, has material moved physically
(xzr/lab/physics.py) and learns from what it can observe of the outcome. Everything it does acts on the runtime: a
completed transfer creates a connection and releases the material's load into the target chamber; isolation closes a
chamber's containment (a runtime gate). The runtime stays the only source of scientific state transitions.

Material semantics (declared design): when a sample is grasped from its source chamber for an experiment it takes up a
*load* q = min(LOAD_FRACTION · Σ difference of the chamber, LOAD_MAX), removed from the chamber's configurations;
when it is released in the target chamber the load is injected there and the connection is made. A runtime
pilot on development seeds (gen 8000–8003) showed such deliveries change the target's ignitions far beyond trajectory
noise (sd 4.3 vs 0.8), while a bare connection does not (sd 0.8 vs 0.8).

Ground truth (privileged, harness only): at every release the harness forks the runtime world (with / without the
release, same streams) and counts the target chamber's ignitions over TRUE_WINDOW steps. Systems never read it: they
learn from their own observation of the target after the release, which may be impossible (unobservable target).

Systems (provisional experimental implementations, not categories of science):

    local        sensor head at one chamber, sees chambers within SENSOR_RANGE of it; transfers within its bay only
    distributed  sensors at several chambers in different bays; a reading reaches its hub only along live runtime
                 connections between chambers (≤ comm_hops hops), delayed by the hop count; transfers anywhere (relay);
                 may isolate chambers (close containment) whose observed activity exceeds isolate_above
    history      sees its own bay; keeps an external memory of outcomes in a store chamber (readable only while that
                 chamber's containment is open); transfers within its bay and the adjacent bays

Memory modes (M6): none · ordinary (pair → outcomes) · contextual (outcomes used only under a matching context) ·
shuffled (outcomes permuted across entries at every read) · write_only (written, never read) — and policy "random"
(same action space, budget and timing, seeded choice).

Observation revision (M5-A): a local system may move its sensor head and change its window; variable generation
(M5-B): candidate variables (products, temporal trends, relational conduit counts) are adopted only if they lower the
leave-one-out prediction error of the system's own observed outcomes by ≥ ADOPT_GAIN and more than a capacity-matched
control (the same candidate with its values permuted).

Causal pathway switches (M9, opt-in; defaults reproduce M4–M7 exactly):

    comm      how a distributed system's readings reach its hub: "conduit" (live runtime connections, the M4–M7
              behaviour), "frozen" (the connection graph as it was when the systems started: the same structure and
              delays, but nothing that happens later, including another system's connections, changes it) or "free"
              (no dependence on connections, = comm_free)
    inert     the system decides and does all its physical work (gantries, material, queues, wear), but its transfers
              change nothing in the runtime: no extraction, no connection, no load, no isolation. It removes the
              system's runtime (environmental and communication) pathways and keeps its physical one.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..runtime.intervention import Connect, Gate, Inject
from . import apparatus

LOAD_FRACTION = 0.3
LOAD_MAX = 6.0
TRUE_WINDOW = 20
SENSOR_RANGE = 3.6
ADOPT_GAIN = 0.05
ISOLATE_FACTOR = 0.2
BASE_FEATURES = ("act_a", "load_a", "mem_a", "act_b", "tens_b", "mem_b")


@dataclass
class SystemSpec:
    sid: str
    kind: str  # local | distributed | history
    home: str  # local: initial sensor chamber; distributed: hub chamber; history: a chamber of its bay
    sensors: tuple[str, ...] = ()  # distributed: sensor chambers
    budget: float = 24.0
    cost_transfer: float = 1.0
    cost_relocate: float = 0.5
    cost_isolate: float = 0.5
    window: int = 8
    period: int = 4
    comm_hops: int = 3
    memory: str = "none"  # none | ordinary | contextual | shuffled | write_only
    store: str | None = None  # memory store chamber (history)
    policy: str = "model"  # model | random
    revise_observation: bool = False
    generate_variables: bool = False
    adapt_parameters: bool = False
    isolate_above: float | None = None  # distributed: isolate chambers whose observed activity exceeds this
    isolate_steps: int = 40
    reach: str | None = None  # override: bay | adjacent | any
    see_all: bool = False  # equalization control: observe every chamber (no range / comm limit)
    comm_free: bool = False  # control: distributed readings reach the hub without runtime connections
    comm: str = "conduit"  # conduit | frozen | free (M9; comm_free=True is "free")
    inert: bool = False  # M9: physical work without any runtime effect
    shared_memory_from: str | None = None  # read another system's memory store (M7 test 6)
    explore: float = 1.5
    ridge: float = 1.0

    def comm_mode(self) -> str:
        return "free" if self.comm_free else self.comm

    def reach_rule(self) -> str:
        return self.reach or {"local": "bay", "distributed": "any", "history": "adjacent"}[self.kind]


@dataclass
class SystemState:
    spec: SystemSpec
    sensor: str  # current sensor head chamber (local) / hub (distributed)
    window: int
    budget: float
    explore: float
    ridge: float
    features: list[str] = field(default_factory=lambda: list(BASE_FEATURES))
    data: list[tuple[dict, float]] = field(default_factory=list)  # (feature values, observed outcome)
    memory: list[dict] = field(default_factory=list)
    pending: dict | None = None
    awaiting: list[dict] = field(default_factory=list)  # outcome observations scheduled
    tries: dict[str, int] = field(default_factory=dict)  # per target chamber
    isolated: dict[str, int] = field(default_factory=dict)  # chamber → step to reopen
    seen_contents: dict[str, int] = field(default_factory=dict)  # material last seen in each chamber (own observation)
    obs_error: list[float] = field(default_factory=list)  # |prediction − own observed outcome| (no privileged truth)
    stats: dict[str, Any] = field(default_factory=lambda: {
        "requests": 0, "completed": 0, "failed": 0, "denied": 0, "true_gain": 0.0, "true_gain_post": 0.0,
        "observed_outcomes": 0, "unobserved_outcomes": 0, "relocations": 0, "window_changes": 0, "isolations": 0,
        "memory_reads": 0, "memory_unavailable": 0, "abs_pred_error": [], "coverage": [], "paths": [],
        "first_request": None, "pairs": set(), "variables_adopted": [], "variables_rejected": 0, "spent": 0.0})


def ridge_fit(X: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    k = X.shape[1]
    return np.linalg.solve(X.T @ X + lam * np.eye(k), X.T @ y)


def loo_error(X: np.ndarray, y: np.ndarray, lam: float) -> float:
    """Exact leave-one-out mean absolute error of ridge regression."""
    k = X.shape[1]
    A = np.linalg.inv(X.T @ X + lam * np.eye(k))
    H = X @ A @ X.T
    beta = A @ X.T @ y
    resid = (y - X @ beta) / np.maximum(1 - np.diag(H), 1e-6)
    return float(np.mean(np.abs(resid)))


class Science:
    """Systems acting in one laboratory (world + physical lab). Driven by the recorder, step by step."""

    def __init__(self, world, chambers: list[apparatus.Chamber], lab, specs: list[SystemSpec], seed: int, t0: int,
                 config_change: dict | None = None):
        self.w, self.cs, self.lab, self.seed, self.t0 = world, chambers, lab, seed, t0
        self.idx = {c.cid: i for i, c in enumerate(chambers)}
        self.bay = {c.cid: c.cid.split(".")[0] for c in chambers}
        self.ring = lab.ring
        self.systems = {s.sid: SystemState(s, s.home, s.window, s.budget, s.explore, s.ridge) for s in specs}
        # deterministic per-system generators (str hashes are salted per process: use a stable key)
        self.rng = {s.sid: np.random.default_rng([seed, sum(ord(ch) * (i + 1) for i, ch in enumerate(s.sid))])
                    for s in specs}
        self.transfers: dict[int, dict] = {}  # physical transfer id → experiment
        self.by_action: dict[int, dict] = {}
        self.events: list[dict] = []
        self.config_change = config_change
        self.owner = np.full(world.state.n, -1, np.int32)
        for i, c in enumerate(chambers):
            self.owner[c.nodes] = i
        self._cache: dict = {}
        self._cache_t = -1
        # the connection graph when the systems start (comm="frozen"); computed only if a system uses it
        self._graph0 = self._conduit_graph_raw() if any(s.comm == "frozen" for s in specs) else None

    def _cached(self, key, fn):
        """Per-step cache of runtime-derived quantities (they cannot change within a step)."""
        if self.w.t != self._cache_t or self.w.state.alive.sum() != self._cache.get("_alive"):
            self._cache, self._cache_t = {"_alive": self.w.state.alive.sum(), "_gate": None}, self.w.t
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def invalidate(self) -> None:
        self._cache_t = -1

    # ------------------------------------------------------------------ runtime-derived quantities
    def _act(self, cid: str, window: int, delay: int = 0) -> float:
        return self._cached(("act", cid, window, delay), lambda: self._act_raw(cid, window, delay))

    def _act_raw(self, cid: str, window: int, delay: int = 0) -> float:
        recs = self.w.records[-(window + delay):len(self.w.records) - delay or None]
        nodes = self.cs[self.idx[cid]].nodes
        if not recs:
            return 0.0
        return float(np.mean([np.isin(r.ignitions, nodes).sum() for r in recs]) / len(nodes))

    def _chan(self, cid: str, window: int, delay: int = 0) -> dict[str, float]:
        return self._cached(("chan", cid, window, delay), lambda: self._chan_raw(cid, window, delay))

    def _chan_raw(self, cid: str, window: int, delay: int = 0) -> dict[str, float]:
        st = self.w.state
        n = self.cs[self.idx[cid]].nodes
        ratio = st.diff[n] / np.maximum(st.theta_eff()[n], 1e-9)
        return {"act": self._act(cid, window, delay), "load": float(min(LOAD_FRACTION * st.diff[n].sum(), LOAD_MAX)),
                "mem": float(st.memory[n].mean()), "tens": float(((ratio >= 0.5) & (ratio < 1)).mean())}

    def shutter(self, cid: str) -> float:
        return self._cached(("shutter", cid), lambda: self._shutter_raw(cid))

    def _shutter_raw(self, cid: str) -> float:
        st = self.w.state
        n = self.cs[self.idx[cid]].nodes
        inside = np.zeros(st.n, bool)
        inside[n] = True
        e = st.alive & inside[st.dst] & ~inside[st.src]
        return float(st.gate[e].mean()) if e.any() else 1.0

    def conduit_graph(self) -> dict[str, set[str]]:
        return self._cached(("conduits",), self._conduit_graph_raw)

    def _conduit_graph_raw(self) -> dict[str, set[str]]:
        st = self.w.state
        a = st.alive
        s, d = self.owner[st.src[a]], self.owner[st.dst[a]]
        g: dict[str, set[str]] = {c.cid: set() for c in self.cs}
        for x, y in set(zip(s[s != d].tolist(), d[s != d].tolist(), strict=True)):
            g[self.cs[x].cid].add(self.cs[y].cid)
            g[self.cs[y].cid].add(self.cs[x].cid)
        return g

    # ------------------------------------------------------------------ what a system can observe
    def coverage(self, sys_: SystemState) -> dict[str, int]:
        """Observable chambers → reading delay (steps). Closed containment hides a chamber from every sensor."""
        sp = sys_.spec
        out: dict[str, int] = {}
        if sp.see_all:
            out = {c.cid: 0 for c in self.cs}
        elif sp.kind == "local":
            p = np.array(self.lab.pos[sys_.sensor])
            out = {c.cid: 0 for c in self.cs if np.linalg.norm(np.array(self.lab.pos[c.cid]) - p) <= SENSOR_RANGE}
        elif sp.kind == "history":
            out = {c.cid: 0 for c in self.cs if self.bay[c.cid] == self.bay[sp.home]}
        elif sp.comm_mode() == "free":
            out = {s: 0 for s in (sys_.sensor, *sp.sensors)}
        else:
            g = self._graph0 if sp.comm_mode() == "frozen" and self._graph0 is not None else self.conduit_graph()
            dist = {sys_.sensor: 0}
            frontier = [sys_.sensor]
            while frontier:
                nxt = []
                for x in frontier:
                    for y in g[x]:
                        if y not in dist and dist[x] + 1 <= sp.comm_hops:
                            dist[y] = dist[x] + 1
                            nxt.append(y)
                frontier = nxt
            out = {s: dist[s] for s in (sys_.sensor, *sp.sensors) if s in dist}
        return {c: d for c, d in out.items() if self.shutter(c) >= 0.5}

    def _material(self, c: str, sid: str) -> list:
        """Material in a chamber that the system can use (the shared laboratory: all of it)."""
        lab = self.lab
        return lab.material(c, sid) if getattr(lab, "part", None) is not None else lab.contents.get(c, [])

    def _reach_ok(self, sp: SystemSpec, a: str, b: str) -> bool:
        r = sp.reach_rule()
        if r == "any":
            return True
        ba, bb = self.ring.index(self.bay[a]), self.ring.index(self.bay[b])
        hops = min((ba - bb) % len(self.ring), (bb - ba) % len(self.ring))
        return hops == 0 if r == "bay" else hops <= 1

    def candidates(self, sys_: SystemState, cov: dict[str, int]) -> list[tuple[str, str]]:
        """Executable experiments as the system knows them: material in an observed source, a target it can observe
        (an experiment whose outcome cannot be observed is not selected), reachable, both containments open."""
        sp = sys_.spec
        src = [c for c in sorted(cov) if self._material(c, sp.sid)]
        return [(a, b) for a in src for b in sorted(cov)
                if b != a and self._reach_ok(sp, a, b) and self.shutter(b) >= 0.5 and b not in sys_.isolated]

    def features(self, sys_: SystemState, a: str, b: str, cov: dict[str, int]) -> dict[str, float]:
        w = sys_.window
        fa = self._chan(a, w, cov.get(a, 0)) if a in cov else None
        fb = self._chan(b, w, cov.get(b, 0)) if b in cov else None
        f = {"act_a": fa["act"] if fa else 0.0, "load_a": fa["load"] if fa else 0.0, "mem_a": fa["mem"] if fa else 0.0,
             "act_b": fb["act"] if fb else 0.0, "tens_b": fb["tens"] if fb else 0.0, "mem_b": fb["mem"] if fb else 0.0,
             "seen_b": 1.0 if fb else 0.0}
        for v in sys_.features:  # generated variables
            if v in f:
                continue
            if v.startswith("prod:"):
                x, y = v[5:].split("*")
                f[v] = f.get(x, 0.0) * f.get(y, 0.0)
            elif v.startswith("trend:"):
                c = a if v.endswith("_a") else b
                f[v] = (self._act(c, w // 2, cov.get(c, 0)) - self._act(c, w, cov.get(c, 0) + w // 2)) if c in cov else 0.0
            elif v == "rel:conduit_ab":
                f[v] = float(b in self.conduit_graph()[a]) if (a in cov and b in cov) else 0.0
        return f

    # ------------------------------------------------------------------ prediction and memory
    def _X(self, sys_: SystemState, rows: list[dict]) -> np.ndarray:
        return np.array([[1.0, *[r.get(v, 0.0) for v in sys_.features]] for r in rows])

    def predict(self, sys_: SystemState, f: dict) -> float:
        if len(sys_.data) < 4:
            return 0.0
        X = self._X(sys_, [d[0] for d in sys_.data])
        y = np.array([d[1] for d in sys_.data])
        beta = ridge_fit(X, y, sys_.ridge)
        return float(self._X(sys_, [f])[0] @ beta)

    def context(self, b: str, f: dict) -> tuple:
        return (round(self.shutter(b), 1), int(f["load_a"] > 2.0))

    def memory_value(self, sys_: SystemState, a: str, b: str, f: dict, t: int) -> float | None:
        sp = sys_.spec
        store_sys = self.systems.get(sp.shared_memory_from) if sp.shared_memory_from else sys_
        mode = sp.memory if not sp.shared_memory_from else store_sys.spec.memory if store_sys else "none"
        if mode in ("none", "write_only") or store_sys is None:
            return None
        store = store_sys.spec.store
        if store is not None and self.shutter(store) < 0.5:
            sys_.stats["memory_unavailable"] += 1
            return None
        entries = store_sys.memory
        sys_.stats["memory_reads"] += 1
        if mode == "shuffled" and entries:
            perm = np.random.default_rng([self.seed, t, len(entries)]).permutation(len(entries))
            outs = [entries[i]["outcome"] for i in perm]
            entries = [{**e, "outcome": o} for e, o in zip(entries, outs, strict=True)]
        rel = [e for e in entries if e["pair"] == (a, b)]
        if mode == "contextual":
            ctx = self.context(b, f)
            rel = [e for e in rel if e["ctx"] == ctx]
        return float(np.mean([e["outcome"] for e in rel])) if rel else None

    # ------------------------------------------------------------------ decisions
    def decide(self, t: int) -> None:
        self.invalidate()
        for sys_ in self.systems.values():
            sp = sys_.spec
            if t % sp.period:
                continue
            self._reopen(sys_, t)
            cov = self.coverage(sys_)
            sys_.stats["coverage"].append(len(cov) / len(self.cs))
            for c in cov:
                sys_.seen_contents[c] = len(self._material(c, sp.sid))
            if sp.isolate_above is not None and sys_.budget >= sp.cost_isolate:
                self._isolate(sys_, cov, t)
            if sp.revise_observation and t % (4 * sp.period) == 0:
                self._revise(sys_, cov, t)
            if sp.adapt_parameters and t % (4 * sp.period) == 0:
                self._adapt(sys_)
            if sp.generate_variables and t % (10 * sp.period) == 0:
                self._generate(sys_, t)
            cands = self.candidates(sys_, cov)
            sys_.stats["paths"].append(len(cands))
            if sys_.pending is not None or sys_.budget < sp.cost_transfer or not cands:
                continue
            choice, pred, basis = self._choose(sys_, cands, cov, t)
            if choice is None:
                continue
            self._request(sys_, choice, pred, basis, cov, t)

    def _choose(self, sys_: SystemState, cands: list[tuple[str, str]], cov: dict[str, int], t: int):
        sp = sys_.spec
        if sp.policy == "random":
            a, b = cands[int(self.rng[sp.sid].integers(len(cands)))]
            return (a, b), 0.0, "random"
        best, best_score, best_pred, basis = None, -math.inf, 0.0, "model"
        for a, b in cands:
            f = self.features(sys_, a, b, cov)
            pred = self.predict(sys_, f)
            mem = self.memory_value(sys_, a, b, f, t) if sp.memory != "none" or sp.shared_memory_from else None
            src = "model"
            if mem is not None:
                pred, src = 0.5 * pred + 0.5 * mem if len(sys_.data) >= 4 else mem, "memory"
            score = pred + sys_.explore / math.sqrt(1 + sys_.tries.get(b, 0))
            if score > best_score:
                best, best_score, best_pred, basis = (a, b), score, pred, src
        return best, best_pred, basis

    def _request(self, sys_: SystemState, pair: tuple[str, str], pred: float, basis: str, cov: dict[str, int], t: int):
        sp = sys_.spec
        a, b = pair
        na, nb = self.cs[self.idx[a]].nodes, self.cs[self.idx[b]].nodes
        st = self.w.state
        src = int(na[np.argmax(st.ignite_count[na])])
        dst = int(nb[np.argmin(st.theta_eff()[nb])])
        act = Connect(src, dst, 0.5)
        if getattr(self.lab, "part", None) is not None:
            ev = self.lab.request(act, lambda n: self.cs[int(self.owner[n])].cid, t, owner=sp.sid)
        else:
            ev = self.lab.request(act, lambda n: self.cs[int(self.owner[n])].cid, t)
        sys_.budget -= sp.cost_transfer
        sys_.stats["spent"] += sp.cost_transfer
        sys_.stats["requests"] += 1
        sys_.stats["first_request"] = sys_.stats["first_request"] if sys_.stats["first_request"] is not None else t
        f = self.features(sys_, a, b, cov)
        exp = {"system": sp.sid, "src": a, "dst": b, "pred": pred, "basis": basis, "features": f, "t": t,
               "transfer": ev.get("transfer"), "load": 0.0}
        self.events.append({"t": t, "type": "experiment_selected", "system": sp.sid, "src": a, "dst": b,
                            "pred": round(pred, 3), "basis": basis, "physical": ev["type"]})
        if ev["type"] != "transfer_queued":
            sys_.stats["denied"] += 1
            return
        sys_.pending = exp
        sys_.tries[b] = sys_.tries.get(b, 0) + 1
        self.transfers[ev["transfer"]] = exp
        self.by_action[id(act)] = exp

    def _isolate(self, sys_: SystemState, cov: dict[str, int], t: int) -> None:
        sp = sys_.spec
        for c in sorted(cov):
            if c == sys_.sensor or c in sys_.isolated:
                continue
            a = self._act(c, sys_.window, cov[c])
            limit = sp.isolate_above if sp.isolate_above is not None else math.inf  # 0.0 is a valid threshold
            if a > limit and sys_.budget >= sp.cost_isolate:
                n = self.cs[self.idx[c]].nodes
                stt = self.w.state
                inside = np.zeros(stt.n, bool)
                inside[n] = True
                e = np.flatnonzero(stt.alive & inside[stt.dst] & ~inside[stt.src])
                if not sp.inert:
                    self.w.set_owner_overlay(f"{sp.sid}:isolate:{c}", [Gate(tuple(int(x) for x in e), ISOLATE_FACTOR)])
                    self.invalidate()
                sys_.isolated[c] = t + sp.isolate_steps
                sys_.budget -= sp.cost_isolate
                sys_.stats["spent"] += sp.cost_isolate
                sys_.stats["isolations"] += 1
                self.events.append({"t": t, "type": "isolation", "system": sp.sid, "chamber": c,
                                    "observed_activity": round(a, 4), "until": t + sp.isolate_steps})

    def _reopen(self, sys_: SystemState, t: int) -> None:
        for c, until in list(sys_.isolated.items()):
            if t >= until:
                if not sys_.spec.inert:
                    self.w.set_owner_overlay(f"{sys_.spec.sid}:isolate:{c}", [])
                    self.invalidate()
                del sys_.isolated[c]
                self.events.append({"t": t, "type": "reopened", "system": sys_.spec.sid, "chamber": c})

    def _revise(self, sys_: SystemState, cov: dict[str, int], t: int) -> None:
        """Observation revision: move the sensor head to the chamber of the bay whose neighbourhood holds the most
        material and the fewest tried targets; widen the window when observed outcomes are noisy."""
        sp = sys_.spec
        if sp.kind == "local" and sys_.budget >= sp.cost_relocate:
            bay = [c.cid for c in self.cs if self.bay[c.cid] == self.bay[sys_.sensor]]

            def value(s: str) -> float:
                p = np.array(self.lab.pos[s])
                near = [c for c in bay if np.linalg.norm(np.array(self.lab.pos[c]) - p) <= SENSOR_RANGE]
                # what the system itself has seen (unseen chambers count as unknown, valued 1), never the true contents
                return sum(sys_.seen_contents.get(c, 1) for c in near) - 0.5 * sum(sys_.tries.get(c, 0) for c in near)
            best = max(bay, key=lambda s: (value(s), -bay.index(s)))
            if best != sys_.sensor and value(best) > value(sys_.sensor):
                self.events.append({"t": t, "type": "sensor_relocated", "system": sp.sid, "from": sys_.sensor,
                                    "to": best})
                sys_.sensor = best
                sys_.budget -= sp.cost_relocate
                sys_.stats["spent"] += sp.cost_relocate
                sys_.stats["relocations"] += 1
        errs = sys_.obs_error[-4:]
        if len(errs) == 4:
            new = 12 if np.mean(errs) > 3 else 6
            if new != sys_.window:
                self.events.append({"t": t, "type": "window_changed", "system": sp.sid, "from": sys_.window, "to": new})
                sys_.window = new
                sys_.stats["window_changes"] += 1

    def _adapt(self, sys_: SystemState) -> None:
        errs = sys_.obs_error[-4:]
        if len(errs) == 4:
            sys_.explore = float(np.clip(sys_.explore * (1.2 if np.mean(errs) > 3 else 0.85), 0.2, 4.0))
            sys_.ridge = float(np.clip(sys_.ridge * (1.5 if np.mean(errs) > 3 else 0.8), 0.1, 10.0))

    def _generate(self, sys_: SystemState, t: int) -> None:
        """Candidate variables from observed relations; adopted only on held-out (leave-one-out) evidence against a
        capacity-matched permuted control."""
        if len(sys_.data) < 8:
            return
        cands = [f"prod:{x}*{y}" for i, x in enumerate(BASE_FEATURES) for y in BASE_FEATURES[i + 1:]]
        cands += ["trend:act_a", "trend:act_b", "rel:conduit_ab"]
        cands = [c for c in cands if c not in sys_.features]
        rows = [d[0] for d in sys_.data]
        y = np.array([d[1] for d in sys_.data])
        X0 = self._X(sys_, rows)
        base = loo_error(X0, y, sys_.ridge)
        best, best_gain = None, 0.0
        for c in cands:
            col = np.array([r.get(c, self._derive(c, r)) for r in rows])
            if np.allclose(col, col[0]):
                continue
            e1 = loo_error(np.c_[X0, col], y, sys_.ridge)
            perm = np.random.default_rng([self.seed, t, len(rows)]).permutation(len(col))
            ec = loo_error(np.c_[X0, col[perm]], y, sys_.ridge)
            gain = (base - e1) / max(base, 1e-9)
            ok = gain >= ADOPT_GAIN and e1 < ec
            self.events.append({"t": t, "type": "variable_candidate", "system": sys_.spec.sid, "variable": c,
                                "loo_base": round(base, 4), "loo_with": round(e1, 4), "loo_control": round(ec, 4),
                                "adopted": False})
            if ok and gain > best_gain:
                best, best_gain = c, gain
            elif not ok:
                sys_.stats["variables_rejected"] += 1
        if best is not None:
            sys_.features.append(best)
            sys_.stats["variables_adopted"].append(best)
            for e in reversed(self.events):
                if e["type"] == "variable_candidate" and e["variable"] == best and e["t"] == t:
                    e["adopted"] = True
                    break

    @staticmethod
    def _derive(v: str, r: dict) -> float:
        if v.startswith("prod:"):
            x, y = v[5:].split("*")
            return r.get(x, 0.0) * r.get(y, 0.0)
        return r.get(v, 0.0)

    # ------------------------------------------------------------------ physical events → runtime
    def on_physical(self, events: list[dict], t: int) -> None:
        for e in events:
            exp = self.transfers.get(e.get("transfer", -1))
            if exp is None:
                continue
            sys_ = self.systems[exp["system"]]
            if e["type"] == "sample_grasped" and e.get("at") == exp["src"]:
                n = self.cs[self.idx[exp["src"]]].nodes
                st = self.w.state
                total = float(st.diff[n].sum())
                q = min(LOAD_FRACTION * total, LOAD_MAX)
                if total > 0 and not sys_.spec.inert:
                    st.diff[n] *= (1 - q / total)
                    self.invalidate()
                exp["load"] = q
                ev = {"t": t, "type": "material_extracted", "system": exp["system"], "chamber": exp["src"],
                      "load": round(q, 4)}
                if sys_.spec.inert:
                    ev["inert"] = True  # moved physically, nothing removed from the runtime
                self.events.append(ev)
            elif e["type"] == "transfer_failed":
                sys_.stats["failed"] += 1
                sys_.pending = None
                self.events.append({"t": t, "type": "experiment_failed", "system": exp["system"], "src": exp["src"],
                                    "dst": exp["dst"], "reason": e.get("reason")})

    def release(self, action: Connect, t: int) -> list:
        """A completed transfer: returns the runtime actions to apply (connection + load), or none if the target's
        containment is closed now (delivery blocked at the boundary)."""
        exp = self.by_action.get(id(action))
        if exp is None:
            return [action]
        sys_ = self.systems[exp["system"]]
        sys_.pending = None
        b = exp["dst"]
        if self.shutter(b) < 0.5:
            sys_.stats["failed"] += 1
            self.events.append({"t": t, "type": "delivery_blocked", "system": exp["system"], "dst": b})
            return []
        nb = self.cs[self.idx[b]].nodes
        acts = [action, Inject(tuple(int(x) for x in nb), exp["load"] / len(nb))]
        if sys_.spec.inert:  # physical work done; the runtime is not touched (true effect 0 by construction)
            acts, true = [], 0.0
        else:
            true = self._true_effect(acts, nb)
        sys_.stats["completed"] += 1
        sys_.stats["true_gain"] += true
        if self.config_change and t >= self.config_change["at"]:
            sys_.stats["true_gain_post"] += true
        sys_.stats["pairs"].add((exp["src"], b))
        sys_.stats["abs_pred_error"].append(abs(exp["pred"] - true))
        before = self._act(b, sys_.window)
        sys_.awaiting.append({**exp, "due": t + sys_.window, "before": before, "true": true})
        self.events.append({"t": t, "type": "material_delivered", "system": exp["system"], "src": exp["src"], "dst": b,
                            "load": round(exp["load"], 4), "true_effect": true, "pred": round(exp["pred"], 3)})
        return acts

    def _true_effect(self, acts: list, nodes: np.ndarray) -> float:
        f1, f0 = self.w.fork(), self.w.fork()
        f1.engine.apply(acts)
        i1 = i0 = 0
        for _ in range(TRUE_WINDOW):
            i1 += int(np.isin(f1.step().ignitions, nodes).sum())
            i0 += int(np.isin(f0.step().ignitions, nodes).sum())
        return float(i1 - i0)

    def observe_outcomes(self, t: int) -> None:
        self.invalidate()  # releases of this step changed connections and differences
        for sys_ in self.systems.values():
            keep = []
            for a in sys_.awaiting:
                if t < a["due"]:
                    keep.append(a)
                    continue
                cov = self.coverage(sys_)
                if a["dst"] in cov:
                    nb = self.cs[self.idx[a["dst"]]].nodes
                    obs = (self._act(a["dst"], sys_.window, cov[a["dst"]]) - a["before"]) * len(nb) * sys_.window
                    sys_.data.append((a["features"], obs))
                    sys_.obs_error.append(abs(a["pred"] - obs))
                    sys_.stats["observed_outcomes"] += 1
                    if sys_.spec.memory != "none":
                        sys_.memory.append({"pair": (a["src"], a["dst"]), "outcome": obs, "t": t,
                                            "ctx": self.context(a["dst"], a["features"])})
                    self.events.append({"t": t, "type": "outcome_observed", "system": sys_.spec.sid, "dst": a["dst"],
                                        "observed": round(obs, 3)})
                else:
                    sys_.stats["unobserved_outcomes"] += 1
                    self.events.append({"t": t, "type": "outcome_unobservable", "system": sys_.spec.sid,
                                        "dst": a["dst"], "reason": "target outside the system's observation"})
            sys_.awaiting = keep

    def apply_config_change(self, t: int) -> None:
        """Harness-side configuration change (M6): close the containment of the listed chambers."""
        cc = self.config_change
        if not cc or t != cc["at"]:
            return
        st = self.w.state
        for c in cc["close"]:
            n = self.cs[self.idx[c]].nodes
            inside = np.zeros(st.n, bool)
            inside[n] = True
            e = np.flatnonzero(st.alive & inside[st.dst] & ~inside[st.src])
            self.w.set_owner_overlay(f"config:close:{c}", [Gate(tuple(int(x) for x in e), cc.get("factor", 0.6))])
            self.invalidate()
        self.events.append({"t": t, "type": "configuration_changed", "closed": list(cc["close"]),
                            "factor": cc.get("factor", 0.6)})

    # ------------------------------------------------------------------ record
    def state(self) -> dict:
        return {sid: {"sensor": s.sensor, "window": s.window, "budget": round(s.budget, 3),
                      "coverage": sorted(self.coverage(s)), "features": list(s.features[len(BASE_FEATURES):]),
                      "pending": [s.pending["src"], s.pending["dst"]] if s.pending else None,
                      "isolated": sorted(s.isolated), "memory": len(s.memory)} for sid, s in self.systems.items()}

    def summary(self) -> dict:
        out = {}
        for sid, s in self.systems.items():
            st = copy.copy(s.stats)
            st["pairs"] = len(s.stats["pairs"])
            st["coverage"] = float(np.mean(s.stats["coverage"])) if s.stats["coverage"] else 0.0
            st["paths"] = float(np.mean(s.stats["paths"])) if s.stats["paths"] else 0.0
            st["abs_pred_error"] = float(np.mean(s.stats["abs_pred_error"])) if s.stats["abs_pred_error"] else math.nan
            st["budget_left"] = s.budget
            out[sid] = st
        return out
