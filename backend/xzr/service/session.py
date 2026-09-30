"""A live session: one world, one dedicated simulation thread, comparison jobs in a worker pool.

Request handlers never step the simulation themselves; they enqueue work (run / step / compare) and
read state under the session lock.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from ..compare.compare import compare
from ..interpret.labels import interpret, rules_from_json
from ..lod.hierarchy import SCALES
from ..lod.layouts import LAYOUTS, normalize
from ..practice.compile import InterventionConfig, compile_config
from ..practice.graph import Claim, Practice
from ..practice.parser import ParseError, help_text, parse
from ..runtime.delta import StepDelta
from ..runtime.engine import MEM_QMAX
from ..scenario.build import World, build_world
from ..scenario.model import Scenario
from ..shapes.detector import ShapeDetector
from ..shapes.waves import WaveObserver

OUTBOX_MAX = 600  # hard bound: beyond this, clients are resynced with a snapshot (event log keeps everything)
BACKPRESSURE = 45  # while clients are connected, the simulation waits once this many steps are unsent
RING = 1500  # steps of full event history kept in memory for the event log / inspection

_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="xzr-job")
JOBS: dict[str, dict] = {}


class CommandError(ValueError):
    def __init__(self, msg: str, suggestions: list[str] | None = None):
        super().__init__(msg)
        self.suggestions = suggestions or []


def config_from_json(d: dict, boundaries: dict[str, float]) -> InterventionConfig:
    cfg = InterventionConfig(Practice.from_json(d.get("practice")), dict(d.get("boundaries", boundaries)))
    cfg.removed_boundaries = set(d.get("removed_boundaries", []))
    cfg.boundary_override = dict(d.get("boundary_override", {}))
    cfg.direct = list(d.get("direct", []))
    cfg.log = list(d.get("log", []))
    return cfg


class Session:
    def __init__(self, scenario: Scenario, applied: dict | None = None, graph_every: int = 10, flags=None):
        self.flags = flags
        self.id = uuid.uuid4().hex[:10]
        self.created = time.time()
        self.touched = time.time()
        self.scenario = scenario
        self.graph_every = graph_every
        self.lock = threading.RLock()
        self.cv = threading.Condition(self.lock)
        self.running = False
        self.pending_steps = 0
        self.speed = 20.0  # steps per second; 0 = as fast as possible
        self.closed = False
        self.streaming = False  # set by the transport while websocket clients are attached
        self.listeners: list[Callable[[dict], None]] = []  # notified (from worker threads) about jobs etc.
        self.compares: dict[str, dict] = {}
        self._build(applied)
        self.thread = threading.Thread(target=self._loop, name=f"xzr-sim-{self.id}", daemon=True)
        self.thread.start()

    def _build(self, applied: dict | None = None) -> None:
        sc = self.scenario
        self.world: World = build_world(sc, self.flags)
        # a runtime variant without wave state: penetration annotations and returns are reconstructed here,
        # so every streamed event keeps its full content
        self.wave_observer = (WaveObserver(self.world.state)
                              if self.world.engine.flags.wave_state == "off" else None)
        self.h = self.world.hierarchy
        self.detector = ShapeDetector(self.h, graph_every=self.graph_every)
        self.rules = rules_from_json(sc.interpretation_rules)
        boundaries = {k: b.permeability for k, b in sc.boundaries.items()}
        base = InterventionConfig(Practice.from_json(sc.practice), boundaries)
        self.applied = config_from_json(applied, boundaries) if applied else base
        self.draft = self.applied.copy()
        overlay, _, self.applied_prov, _ = compile_config(self.applied, self.world.resolve)
        self.engine.set_overlay(overlay)
        self.engine.log.clear()
        self.engine.checkpoints.clear()
        self.engine._save_checkpoint()
        self.outbox: list[StepDelta] = []
        self.ring: deque[StepDelta] = deque(maxlen=RING)
        self.resync = True
        self.latest: dict = {}
        self.graph_latest: dict | None = None
        self.layout_version = 0
        self.step_times: deque[float] = deque(maxlen=120)
        warm = sc.warmup
        for _ in range(warm):
            self._step_locked()

    @property
    def engine(self):
        return self.world.engine

    # ------------------------------------------------------------------ simulation thread
    def _step_locked(self) -> None:
        d = self.engine.step()
        if self.wave_observer is not None:
            d.penetrations, d.returns = self.wave_observer.observe(d, self.engine.state)
        rec = self.detector.observe(d, self.engine.state)
        self.ring.append(d)
        self.outbox.append(d)
        if len(self.outbox) > OUTBOX_MAX:
            self.outbox.clear()
            self.resync = True
        self.latest = rec
        if "graph" in rec:
            self.graph_latest = rec["graph"]
            if self.detector.embedding is not None:
                self.world.positions["shape"] = normalize(self.detector.embedding)
                self.layout_version += 1
        self.step_times.append(time.perf_counter())

    def _loop(self) -> None:
        while True:
            with self.cv:
                while not self.closed and (not (self.running or self.pending_steps > 0)
                                           or (self.streaming and len(self.outbox) >= BACKPRESSURE)):
                    self.cv.wait(0.05 if self.streaming else 0.5)
                if self.closed:
                    return
                t0 = time.perf_counter()
                self._step_locked()
                if self.pending_steps > 0:
                    self.pending_steps -= 1
                speed = self.speed if self.pending_steps == 0 else 0
            if speed > 0:
                time.sleep(max(0.0, 1.0 / speed - (time.perf_counter() - t0)))
            else:
                # yield: Python locks are not fair, and the transport must be able to drain the outbox
                time.sleep(0.001 if self.streaming else 0)

    def steps_per_second(self) -> float:
        ts = self.step_times
        if len(ts) < 2 or time.perf_counter() - ts[-1] > 1.0:
            return 0.0
        return (len(ts) - 1) / (ts[-1] - ts[0])

    def take_outbox(self) -> tuple[list[StepDelta], bool]:
        with self.lock:
            out, self.outbox = self.outbox, []
            rs, self.resync = self.resync, False
            self.cv.notify_all()
            return out, rs

    # ------------------------------------------------------------------ control
    def control(self, action: str, steps: int = 1, speed: float | None = None) -> dict:
        with self.cv:
            if speed is not None:
                self.speed = max(0.0, float(speed))
            if action == "run":
                self.running = True
            elif action in ("pause", "stop"):
                self.running = False
                self.pending_steps = 0
            elif action == "step":
                self.running = False
                self.pending_steps += max(1, min(int(steps), 100_000))
            elif action == "reset":
                self.running = False
                self.pending_steps = 0
                self._build()
            elif action != "speed":
                raise CommandError(f"unknown control action {action}")
            self.cv.notify_all()
            return self.status()

    def rewind(self, t: int) -> dict:
        with self.cv:
            self.running = False
            self.pending_steps = 0
            reached = self.engine.rewind(t)
            self.detector.truncate(reached)
            self.ring = deque([d for d in self.ring if d.t <= reached], maxlen=RING)
            self.outbox.clear()
            self.resync = True
            return self.status()

    def status(self) -> dict:
        s = self.engine.state
        return {"t": s.t, "running": self.running, "speed": self.speed, "pending_steps": self.pending_steps,
                "steps_per_second": round(self.steps_per_second(), 1), "connections": int(s.alive.sum()),
                "checkpoints": sorted(self.engine.checkpoints), "layout_version": self.layout_version,
                "draft_differs": self.draft.to_json() != self.applied.to_json()}

    def info(self) -> dict:
        s = self.engine.state
        with self.lock:
            return {
                "id": self.id, "scenario": {"name": self.scenario.name, "description": self.scenario.description},
                "n": s.n, "e_cap": s.e_cap, "params": s.params.to_dict(), "quant_max": s.params.quant_max,
                "mem_qmax": MEM_QMAX, "n_forms": s.params.n_forms, "scales": list(SCALES), "layouts": list(LAYOUTS),
                "clusters_per_level": [self.h.n_clusters(lv) for lv in range(4)],
                "geo_count": int(np.isfinite(s.geo).all(1).sum()), "sets": sorted(self.scenario.sets),
                "boundaries": {k: b.permeability for k, b in self.scenario.boundaries.items()},
                "runtime_flags": self.engine.flags.to_dict(), "runtime_is_full": self.engine.flags.is_full(),
                **self.status(),
            }

    # ------------------------------------------------------------------ inspection
    def node(self, i: int, recent: int = 200) -> dict:
        with self.lock:
            s = self.engine.state
            if not 0 <= i < s.n:
                raise KeyError(i)
            out_e = np.flatnonzero(s.alive & (s.src == i))
            in_e = np.flatnonzero(s.alive & (s.dst == i))
            reach = s.reachable_mask()
            te = s.theta_eff()
            ev: list[dict] = []
            for d in list(self.ring)[-recent:]:
                if np.any(d.ignitions == i):
                    ev.append({"t": d.t, "kind": "ignition"})
                for e, o, dep in d.penetrations:
                    if s.dst[e] == i:
                        ev.append({"t": d.t, "kind": "penetrated from", "other": int(s.src[e]), "depth": int(dep),
                                   "origin": int(o)})
                    elif s.src[e] == i:
                        ev.append({"t": d.t, "kind": "penetrated into", "other": int(s.dst[e]), "depth": int(dep)})
                for x, f in d.transformations:
                    if x == i:
                        ev.append({"t": d.t, "kind": "transformation", "form": int(f)})
                if np.any(d.returns == i):
                    ev.append({"t": d.t, "kind": "return"})
                if np.any(d.decays == i):
                    ev.append({"t": d.t, "kind": "decay"})
                for e in d.cuts:
                    if s.src[e] == i or s.dst[e] == i:
                        ev.append({"t": d.t, "kind": "cut", "edge": int(e)})
                for _e, a, b in d.new_connections:
                    if a == i or b == i:
                        ev.append({"t": d.t, "kind": "new connection", "other": int(b if a == i else a)})
                for e, old, nw in d.reconfigurations:
                    if s.src[e] == i:
                        ev.append({"t": d.t, "kind": "reconfiguration", "from": int(old), "to": int(nw)})
            reg = int(self.h.labels[2][i])
            sig = self.detector.signatures[reg] if self.detector.signatures else None
            return {
                "id": i, "address": self.h.node_address(i),
                "cluster_path": [self.h.address(lv, int(self.h.labels[lv][i])) for lv in range(4)],
                "difference": float(s.diff[i]), "form": int(s.form[i]), "theta": float(s.theta[i]),
                "theta_mod": float(s.theta_mod[i]), "theta_eff": float(te[i]), "retention": float(s.retention[i]),
                "memory": float(s.memory[i]), "mem_decay": float(s.mem_decay[i]),
                "mem_coupling": float(s.mem_coupling[i]), "cap": float(s.cap[i]), "frozen": bool(s.frozen[i]),
                "refractory": int(s.refractory[i]), "overload": int(s.overload[i]),
                "wave_origin": int(s.wave_origin[i]), "wave_depth": int(s.wave_depth[i]),
                "ignite_count": int(s.ignite_count[i]), "last_ignite": int(s.last_ignite[i]),
                "geo": None if not np.isfinite(s.geo[i]).all() else [float(s.geo[i, 0]), float(s.geo[i, 1])],
                "in_loop": bool(self.detector.in_loop[i]), "regional_signature": sig,
                "reachable_transitions": [
                    {"edge": int(e), "to": int(s.dst[e]), "weight": round(float(s.weight[e]), 4),
                     "gate": round(float(s.gate[e]), 4), "load": round(float(s.load[e]), 4),
                     "transform": int(s.transform[e]), "reachable": bool(reach[e])} for e in out_e[:64]],
                "incoming": [{"edge": int(e), "from": int(s.src[e]), "weight": round(float(s.weight[e]), 4),
                              "gate": round(float(s.gate[e]), 4)} for e in in_e[:64]],
                "out_degree": int(len(out_e)), "in_degree": int(len(in_e)),
                "recent_transitions": ev[-80:],
            }

    def events(self, since: int = 0, until: int | None = None, limit: int = 200) -> list[dict]:
        with self.lock:
            ds = [d for d in self.ring if d.t >= since and (until is None or d.t <= until)]
            return [d.to_json() for d in ds[-limit:]]

    def shapes(self) -> dict:
        with self.lock:
            summ = self.detector.summary()
            summ["interpretation"] = interpret(summ["recurrent_shapes"], self.rules)
            return summ

    def metrics(self, since: int = 0) -> dict:
        with self.lock:
            det = self.detector
            i0 = next((k for k, t in enumerate(det.t) if t >= since), len(det.t))
            j0 = next((k for k, t in enumerate(det.t_graph) if t >= since), len(det.t_graph))
            return {"t": det.t[i0:], "series": {k: v[i0:] for k, v in det.series.items()},
                    "t_graph": det.t_graph[j0:], "graph_series": {k: v[j0:] for k, v in det.graph_series.items()},
                    "events": [e for e in det.events if e["t"] >= since]}

    # ------------------------------------------------------------------ practice console
    def practice_view(self) -> dict:
        with self.lock:
            sa = self.applied.practice.score()
            sd = self.draft.practice.score()
            _, _, prov_d, _ = compile_config(self.draft, self.world.resolve)
            return {"applied": {**self.applied.to_json(), "score": sa.to_json(), "provenance": self.applied_prov},
                    "draft": {**self.draft.to_json(), "score": sd.to_json(), "provenance": prov_d},
                    "grammar": help_text(), "sets": sorted(self.scenario.sets),
                    "boundaries": {k: b.permeability for k, b in self.scenario.boundaries.items()}}

    def command(self, text: str, auto_compare: bool = True, horizon: int = 150) -> dict:
        try:
            cmd = parse(text)
        except ParseError as e:
            raise CommandError(str(e), e.suggestions) from e
        with self.lock:
            before = self.draft.copy()
            d = self.draft.copy()
            p = d.practice
            a = cmd.args
            report: dict = {"command": cmd.to_json()}
            mutates = True
            try:
                if cmd.op == "remove_concept":
                    report["dependencies"] = p.dependencies_of(a["name"])
                    p.remove_concept(a["name"])
                elif cmd.op == "restore_concept":
                    p.restore_concept(a["name"])
                    report["dependencies"] = p.dependencies_of(a["name"])
                elif cmd.op in ("weaken", "strengthen", "withdraw", "assert", "revise"):
                    report["dependencies"] = p.dependencies_of(a["claim"] if "claim" in a else a["name"])
                    if cmd.op == "weaken":
                        p.weaken(a["claim"], a["factor"])
                    elif cmd.op == "strengthen":
                        p.strengthen(a["claim"], a["amount"])
                    elif cmd.op == "withdraw":
                        p.withdraw(a["name"])
                    elif cmd.op == "assert":
                        p.assert_claim(a["claim"], a["strength"])
                    else:
                        p.revise(a["claim"], a["strength"])
                elif cmd.op == "introduce_claim":
                    bind = [a["binding"]] if a["binding"] else []
                    for b in bind:
                        self.world.resolve(b["target"], "nodes")
                    p.introduce(Claim(a["claim"], cmd.text, tuple(a["uses"]), bind, default_entitled=not a["premises"]),
                                1.0 if not a["premises"] else 0.0, tuple(a["premises"]))
                    report["dependencies"] = p.dependencies_of(a["claim"])
                elif cmd.op == "reconnect":
                    p.reconnect(a["claim"], tuple(a["premises"]))
                    report["dependencies"] = p.dependencies_of(a["claim"])
                elif cmd.op == "disconnect_claim":
                    if p.disconnect(a["claim"], a["premise"]) == 0:
                        raise CommandError(f"no dependency of {a['claim']} on {a['premise']}")
                    report["dependencies"] = p.dependencies_of(a["claim"])
                elif cmd.op in ("remove_boundary", "restore_boundary", "set_boundary"):
                    name = a["name"]
                    bound_by = [c.id for c in p.claims.values() if any(b["target"] == name for b in c.bindings)]
                    if name not in d.boundaries and not bound_by:
                        raise CommandError(f"unknown boundary {name}; known: "
                                           f"{', '.join(sorted(set(d.boundaries) | self._bound_targets(p))) or 'none'}")
                    report["dependencies"] = {"token": name, "direct": bound_by, "consequences": [],
                                              "dependencies": [], "incompatibilities": []}
                    if cmd.op == "remove_boundary":
                        d.removed_boundaries.add(name)
                    elif cmd.op == "restore_boundary":
                        d.removed_boundaries.discard(name)
                        d.boundary_override.pop(name, None)
                    else:
                        if name not in d.boundaries:
                            raise CommandError(f"{name} is bound by claims, not a scenario boundary")
                        d.boundary_override[name] = a["permeability"]
                elif cmd.op == "set_threshold":
                    self.world.resolve(a["target"], "nodes")
                    d.actions.append({"kind": "set_threshold", "target": a["target"], "value": a["value"],
                                      "text": cmd.text})
                elif cmd.op == "scale_threshold":
                    self.world.resolve(a["target"], "nodes")
                    d.direct.append({"kind": "scale_threshold", "target": a["target"], "factor": a["factor"],
                                     "text": cmd.text})
                elif cmd.op == "memory_condition":
                    self.world.resolve(a["target"], "nodes")
                    d.direct.append({"kind": "memory_condition", "target": a["target"], "decay": a["decay"],
                                     "coupling": a["coupling"], "text": cmd.text})
                elif cmd.op == "freeze":
                    self.world.resolve(a["name"], "nodes")
                    d.direct.append({"kind": "freeze", "target": a["name"], "text": cmd.text})
                elif cmd.op == "inject":
                    self.world.resolve(a["target"], "nodes")
                    d.actions.append({"kind": "inject", "target": a["target"], "amount": a["amount"], "text": cmd.text})
                elif cmd.op == "sever":
                    edges = self.world.relation_edges(a["a"], a["b"])
                    if len(edges) == 0:
                        raise CommandError(f"no live connection from {a['a']} to {a['b']}")
                    d.actions.append({"kind": "sever", "edges": edges.tolist(), "text": cmd.text})
                    report["severed_connections"] = int(len(edges))
                elif cmd.op == "connect":
                    sa, sb = self.world.resolve(a["a"], "nodes"), self.world.resolve(a["b"], "nodes")
                    if len(sa) != 1 or len(sb) != 1:
                        raise CommandError("connect needs two single configurations (c<index>)")
                    d.actions.append({"kind": "connect", "src": int(sa[0]), "dst": int(sb[0]), "weight": a["weight"],
                                      "text": cmd.text})
                else:
                    mutates = False
            except KeyError as e:
                raise CommandError(str(e).strip("'\"")) from e
            except ValueError as e:
                raise CommandError(str(e)) from e

            if cmd.op == "compare":
                report["job"] = self.start_compare(a["horizon"])
                return report
            if cmd.op == "apply":
                report["applied"] = self.apply_draft()
                return report
            if cmd.op == "discard":
                self.draft = self.applied.copy()
                report["discarded"] = True
                return report
            if cmd.op == "show":
                report["dependencies"] = p.dependencies_of(a["name"])
                report["score"] = p.score().to_json()
                return report
            if cmd.op == "help":
                report["grammar"] = help_text()
                return report
            if not mutates:
                return report
            d.log.append(cmd.text)
            self.draft = d
            report["commitment_changes"] = self._score_diff(before.practice, d.practice)
            _, _, prov_before, _ = compile_config(before, self.world.resolve)
            _, _, prov_after, _ = compile_config(d, self.world.resolve)
            report["operational_changes"] = {"before": prov_before, "after": prov_after}
            if auto_compare:
                report["job"] = self.start_compare(horizon)
            return report

    @staticmethod
    def _bound_targets(p: Practice) -> set[str]:
        return {b["target"] for c in p.claims.values() for b in c.bindings if b["op"] == "gate"}

    @staticmethod
    def _score_diff(a: Practice, b: Practice) -> list[dict]:
        sa, sb = a.score(), b.score()
        out = []
        for cid, cl in b.claims.items():
            ra = {"commitment": sa.commitment.get(cid, 0.0), "entitled": sa.entitled.get(cid, False),
                  "status": sa.status.get(cid, "")}
            rb = {"commitment": sb.commitment.get(cid, 0.0), "entitled": sb.entitled.get(cid, False),
                  "status": sb.status.get(cid, "")}
            if ra != rb:
                out.append({"claim": cid, "text": cl.text, "before": ra, "after": rb})
        return out

    def apply_draft(self) -> dict:
        with self.lock:
            overlay, actions, prov, _ = compile_config(self.draft, self.world.resolve)
            self.engine.set_overlay(overlay)
            self.engine.apply(actions)
            self.draft.actions = []
            self.applied = self.draft.copy()
            self.applied_prov = prov
            return {"t": self.engine.state.t, "overlay_items": len(overlay), "actions": len(actions)}

    # ------------------------------------------------------------------ comparison jobs
    def start_compare(self, horizon: int = 150) -> str:
        horizon = max(10, min(int(horizon), 5000))
        with self.lock:
            fork = self.engine.fork()
            ov_a, act_a, prov_a, _ = compile_config(self.applied, self.world.resolve)
            ov_b, act_b, prov_b, _ = compile_config(self.draft, self.world.resolve)
            changes = self._score_diff(self.applied.practice, self.draft.practice)
            draft_log = list(self.draft.log)
        jid = uuid.uuid4().hex[:10]
        job = {"id": jid, "kind": "compare", "session": self.id, "status": "running", "created": time.time(),
               "horizon": horizon}
        JOBS[jid] = job

        def work() -> None:
            try:
                res = compare(fork, ov_a, act_a, ov_b, act_b, self.h, horizon=horizon, graph_every=self.graph_every)
                res["id"] = jid
                res["commitment_changes"] = changes
                res["operational_changes"] = {"baseline": prov_a, "intervention": prov_b}
                res["intervention_log"] = draft_log
                self.compares[jid] = res
                job["status"] = "done"
                job["summary"] = res["summary"]
            except Exception as e:  # noqa: BLE001 — reported to the client
                job["status"] = "error"
                job["error"] = f"{type(e).__name__}: {e}"
            for fn in list(self.listeners):
                fn({"type": "job", **{k: v for k, v in job.items() if k != "created"}})

        _POOL.submit(work)
        return jid

    # ------------------------------------------------------------------ persistence
    def save(self) -> dict:
        with self.lock:
            return {"format": "xzr-session/1", "scenario": self.scenario.model_dump(mode="json", exclude_none=True),
                    "applied": self.applied.to_json(), "t": self.engine.state.t,
                    "fingerprint": self.engine.fingerprint()}

    def close(self) -> None:
        with self.cv:
            self.closed = True
            self.cv.notify_all()
