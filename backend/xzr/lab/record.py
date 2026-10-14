"""Run a laboratory experiment headless and record it (schema ``xzr.labrun/1``).

The run is an HPO field (operations acting on the runtime world) observed through the apparatus layer. Per step the
record keeps: the runtime fingerprint (SHA-256 over every state array and the RNG), the apparatus state, its digest,
and apparatus events. Every apparatus event carries its runtime provenance:

    containment_close/open   the overlay changes of that step (which operation's standing gates changed) and the
                             causal-history act events of those operations; or "connection turnover" when only the
                             set of entering connections changed (no gate was set that step)
    conduit_established/...  the engine's connection events of that step between the two chambers (created / cut /
                             disconnected / reconfigured / severed by an operation)

Nothing here alters the run: the wrappers only read what the runtime and the field do.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np

from ..hpo.field import Field
from ..hpo.world import build_world
from . import apparatus

SCHEMA = "xzr.labrun/1"  # runs without scientific systems (M2, M3)
SCHEMA_V2 = "xzr.labrun/2"  # runs with scientific systems (M4–M7): adds science state per step and science events
SCHEMA_V3 = "xzr.labrun/3"  # M9: resource partition, causal-pathway switches, harness interventions, physics params
DEFAULT_CONFIG: dict[str, Any] = {"n": 800, "gen_seed": 9100, "seed": 91000, "regime": "intermittent", "warmup": 40,
                                  "horizon": 240, "settings": {"interaction": "all", "history": {"reinsert": True}},
                                  "physics": False, "resources": 3.0}
# keys that only v2 (scientific systems) configurations carry; absent = v1 behaviour, unchanged
V2_KEYS = ("systems", "config_change")
V3_KEYS = ("partition", "harness", "physics_params")  # any of these (or a system with comm / inert) makes a v3 run
V3_SYSTEM_KEYS = ("comm", "inert", "sensor_range", "relocation")


def is_v3(cfg: dict) -> bool:
    return any(cfg.get(k) for k in V3_KEYS) or any(k in s for s in cfg.get("systems") or [] for k in V3_SYSTEM_KEYS)


def _settings(cfg: dict) -> dict:
    from ..hpo.field import ALL_OFF, ALL_ON
    s = json.loads(json.dumps(cfg["settings"]))
    ix = s.get("interaction", "all")
    if isinstance(ix, str):
        s["interaction"] = dict(ALL_ON) if ix == "all" else dict(ALL_OFF)
    s.setdefault("warmup", cfg["warmup"])
    s.setdefault("horizon", cfg["horizon"])
    return s


class _Tap:
    """Read-only taps on one world: the engine delta of each step, overlay owners changed, operation actions."""

    def __init__(self, world, lab=None, chamber_of=None):
        self.delta = None
        self.overlay_owners: list[str] = []
        self.actions: list[str] = []
        self.lab, self.chamber_of, self.field = lab, chamber_of, None
        self.requests: list[dict] = []
        eng = world.engine
        step, set_owner, apply_ = eng.step, world.set_owner_overlay, world.apply

        def step_tap():
            self.delta = step()
            return self.delta

        def overlay_tap(owner, items):
            self.overlay_owners.append(owner)
            return set_owner(owner, items)

        def apply_tap(actions):
            self.actions += [type(a).__name__ for a in actions]
            if self.lab is None:
                return apply_(actions)
            # physical laboratory: a connection an operation requests exists only after a material transfer
            from ..runtime.intervention import Connect
            rest = [a for a in actions if not isinstance(a, Connect)]
            last = self.field.history.events[-1] if self.field and self.field.history.events else None
            by = {"operation": last["source"], "causal_event": last["id"]} if last and last["type"] == "act" else {}
            for a in actions:
                if isinstance(a, Connect):
                    ev = self.lab.request(a, self.chamber_of, world.t - (self.field.t0 if self.field else 0))
                    self.requests.append({**ev, **by})
            return apply_(rest)

        eng.step = step_tap
        world.set_owner_overlay = overlay_tap
        world.apply = apply_tap

    def take(self) -> tuple[Any, list[str], list[str]]:
        d, o, a = self.delta, self.overlay_owners, self.actions
        self.overlay_owners, self.actions = [], []
        return d, o, a

    def take_requests(self) -> list[dict]:
        r, self.requests = self.requests, []
        return r


def _conduit_causes(delta, st, owner: np.ndarray, pair: tuple[int, int], actions: list[str],
                    physical: list[tuple[int, int, str]] | None = None) -> list[str]:
    out = [f"physical_transfer:bay {bay}" for a, b, bay in (physical or []) if tuple(sorted((a, b))) == pair]
    for name, arr in (("created", delta.new_connections[:, 0] if len(delta.new_connections) else []),
                      ("cut", delta.cuts), ("disconnected", delta.removed_connections), ("retired", delta.retired)):
        for e in np.asarray(arr, dtype=np.int64):
            a, b = sorted((int(owner[st.src[e]]), int(owner[st.dst[e]])))
            if (a, b) == pair:
                out.append(f"runtime:{name}")
                break
    # a reconfiguration redirects a connection: it leaves the pair (source, old target) and joins (source, new target)
    for e, old, new in (np.asarray(delta.reconfigurations, dtype=np.int64) if len(delta.reconfigurations) else []):
        s = int(owner[st.src[e]])
        if tuple(sorted((s, int(owner[old])))) == pair or tuple(sorted((s, int(owner[new])))) == pair:
            out.append("runtime:reconfigured")
            break
    if not out and actions:
        out.append("operation:" + ",".join(sorted(set(actions))))
    return out or ["runtime:unattributed"]


class LabRun:
    """One laboratory run, advanced step by step (recording, replay and live streaming share this path).

    Without ``systems`` in the configuration the step order is exactly the v1 order (M2/M3 records replay unchanged).
    With systems: HPO field step (if any) → harness configuration change → systems decide (requests go to the physical
    laboratory) → physics → physical events to the systems → completed transfers released into the runtime →
    outcome observations → apparatus state.
    """

    def __init__(self, cfg: dict | None = None):
        cfg = {**DEFAULT_CONFIG, **(cfg or {})}
        self.cfg = cfg
        self.t_start = time.time()
        w = build_world(cfg["n"], cfg["gen_seed"], cfg["seed"], regime=cfg["regime"])
        for _ in range(cfg["warmup"]):
            w.step()
        self.w = w
        self.cs = cs = apparatus.chambers(w.h)
        self.owner = owner = np.full(w.state.n, -1, np.int32)
        for i, c in enumerate(cs):
            owner[c.nodes] = i
        self.idx = {c.cid: i for i, c in enumerate(cs)}
        self.ch_records = [{"cid": c.cid, "position": list(c.position), "size": int(len(c.nodes))} for c in cs]
        self.lab = None
        if cfg["physics"] or cfg.get("systems"):
            from .physics import PhysicalLab
            self.lab = (PhysicalLab(self.ch_records, resources=float(cfg["resources"]), partition=cfg.get("partition"),
                                    params=cfg.get("physics_params")) if is_v3(cfg)
                        else PhysicalLab(self.ch_records, resources=float(cfg["resources"])))
        self.tap = _Tap(w, self.lab, lambda node: cs[int(owner[node])].cid if owner[node] >= 0 else None)
        self.t0 = w.t
        self.f = Field(w, _settings(cfg), cfg["seed"], keep_states=False) if cfg["settings"] is not None else None
        self.tap.field = self.f
        self.science = None
        if cfg.get("systems"):
            from .science import Science, SystemSpec
            self.science = Science(w, cs, self.lab, [SystemSpec(**s) for s in cfg["systems"]], cfg["seed"], self.t0,
                                   cfg.get("config_change"))
        self.prev = apparatus.state(w.state, cs, np.zeros(0, np.int32))
        self.steps: list[dict] = []
        self.events: list[dict] = []
        self.physical: list[dict] = []
        self.applied_phys: list[tuple[int, int, str]] = []
        self.science_seen = 0
        self.harness = sorted(cfg.get("harness") or [], key=lambda h: h["at"])

    @property
    def t(self) -> int:
        return self.w.t - self.t0

    @property
    def done(self) -> bool:
        return self.t >= self.cfg["horizon"]

    def step(self) -> dict:
        """Advance one runtime step; returns the recorded step plus the events it produced."""
        w, cs, owner, lab, f, sci = self.w, self.cs, self.owner, self.lab, self.f, self.science
        n_ev = len(f.history.events) if f else 0
        if f is not None:
            f.step()
        else:
            w.step()
        delta, owners, actions = self.tap.take()
        st = w.state
        t = self.t
        pending_phys: list[tuple[int, int, str]] = []
        new_phys: list[dict] = []
        if lab is not None:
            if sci is not None:
                sci.apply_config_change(t)
                for h in self.harness:
                    if h["at"] == t:
                        new_phys += self._harness(h, t)
                sci.decide(t)
            new_phys += self.tap.take_requests()
            pev, done = lab.step(t)
            new_phys += pev
            if sci is not None:
                sci.on_physical(pev, t)
            if done:  # completed transfers: the requested connections now exist in the runtime (next step's record)
                acts = [x for a, _ in done for x in (sci.release(a, t) if sci is not None else [a])]
                if acts:
                    w.engine.apply(acts)
            pending_phys = [(int(owner[a.src]), int(owner[a.dst]), bay) for a, bay in done]
            if sci is not None:
                sci.observe_outcomes(t)
        self.physical += new_phys
        cur = apparatus.state(st, cs, delta.ignitions)
        acts_ev = {e["source"]: e["id"] for e in f.history.events[n_ev:] if e["type"] == "act"} if f else {}
        new_events = []
        for ev in apparatus.events(self.prev, cur, cs, t):
            if ev["type"].startswith("containment"):
                ops = sorted(set(owners))
                ev["cause"] = ([f"operation:{o}" for o in ops] + [f"causal_event:{acts_ev[o]}" for o in ops if o in acts_ev]
                               if ops else ["runtime:connection_turnover"])
            else:
                a, b = (self.idx[x] for x in ev["pair"].split("|"))
                ev["cause"] = _conduit_causes(delta, st, owner, (min(a, b), max(a, b)), actions, self.applied_phys)
            new_events.append(ev)
        self.events += new_events
        rec_step = {"t": t, "fingerprint": w.engine.fingerprint(), "digest": apparatus.digest(cur), **cur}
        if lab is not None:
            rec_step["physics"] = {"fingerprint": lab.fingerprint(), **lab.state()}
            self.applied_phys = pending_phys
        new_sci: list[dict] = []
        if sci is not None:
            rec_step["science"] = sci.state()
            new_sci = sci.events[self.science_seen:]
            self.science_seen = len(sci.events)
        self.steps.append(rec_step)
        self.prev = cur
        return {"step": rec_step, "events": new_events, "physical_events": new_phys, "science_events": new_sci}

    def _harness(self, h: dict, t: int) -> list[dict]:
        """A declared harness intervention (M9): physical (gantry failure, resources) or runtime (containment, severed
        connections). It is part of the configuration, applied at its step before the systems decide, and recorded."""
        from ..runtime.intervention import Gate, Sever
        lab, w, sci = self.lab, self.w, self.science
        assert lab is not None and sci is not None
        ev: list[dict] = []
        do = h["do"]
        if do == "fail_gantry":
            lab.force_failure(h["gantry"], t, ev)
        elif do == "set_resources":
            lab.set_resources(h["gantry"], h["value"], t, ev)
        elif do in ("close", "open"):
            st = w.state
            for c in h["chambers"]:
                n = self.cs[self.idx[c]].nodes
                inside = np.zeros(st.n, bool)
                inside[n] = True
                e = np.flatnonzero(st.alive & inside[st.dst] & ~inside[st.src])
                w.set_owner_overlay(f"harness:close:{c}",
                                    [Gate(tuple(int(x) for x in e), float(h.get("factor", 0.2)))] if do == "close" else [])
        elif do == "sever":  # cut every live connection between the listed chambers and any other chamber
            st = w.state
            sel = np.zeros(st.n, bool)
            for c in h["chambers"]:
                sel[self.cs[self.idx[c]].nodes] = True
            own = self.owner
            e = np.flatnonzero(st.alive & (sel[st.src] | sel[st.dst]) & (own[st.src] != own[st.dst]))
            if len(e):
                w.engine.apply([Sever(tuple(int(x) for x in e))])
            h = {**h, "severed": int(len(e))}
        else:
            raise ValueError(f"unknown harness intervention {do!r}")
        sci.invalidate()
        sci.events.append({"t": t, "type": "harness", **{k: v for k, v in h.items() if k != "at"}})
        return ev

    def record(self) -> dict:
        cfg, lab, f, sci = self.cfg, self.lab, self.f, self.science
        schema = SCHEMA_V3 if is_v3(cfg) else SCHEMA_V2 if sci is not None else SCHEMA
        rec = {"schema": schema, "config": cfg, "chambers": self.ch_records,
               "layout": lab.layout() if lab is not None else None,
               "steps": self.steps, "events": self.events, "physical_events": self.physical,
               "operations": sorted({o.label for o in f.ops.values()}) if f else [],
               "elapsed_s": round(time.time() - self.t_start, 2),
               "note": "Apparatus states are derived from the runtime state (xzr/lab/apparatus.py); the renderer draws "
                       "these values only. Simulation-internal; no physical apparatus exists."}
        if sci is not None:
            rec["science_events"] = sci.events
            rec["summary"] = _plain(sci.summary())
        return rec


def _plain(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): _plain(v) for k, v in x.items()}
    if isinstance(x, list | tuple | set):
        return [_plain(v) for v in (sorted(x, key=str) if isinstance(x, set) else x)]
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def run(cfg: dict | None = None, out: Path | None = None) -> dict:
    r = LabRun(cfg)
    while not r.done:
        r.step()
    rec = r.record()
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            raise FileExistsError(f"{out} exists; records are never overwritten")
        out.write_text(json.dumps(rec, separators=(",", ":")))
    return rec
