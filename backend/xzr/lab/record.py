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
import time
from pathlib import Path
from typing import Any

import numpy as np

from ..hpo.field import Field
from ..hpo.world import build_world
from . import apparatus

SCHEMA = "xzr.labrun/1"
DEFAULT_CONFIG: dict[str, Any] = {"n": 800, "gen_seed": 9100, "seed": 91000, "regime": "intermittent", "warmup": 40,
                                  "horizon": 240, "settings": {"interaction": "all", "history": {"reinsert": True}},
                                  "physics": False, "resources": 3.0}


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


def run(cfg: dict | None = None, out: Path | None = None) -> dict:
    cfg = {**DEFAULT_CONFIG, **(cfg or {})}
    t0 = time.time()
    w = build_world(cfg["n"], cfg["gen_seed"], cfg["seed"], regime=cfg["regime"])
    for _ in range(cfg["warmup"]):
        w.step()
    cs = apparatus.chambers(w.h)
    owner = np.full(w.state.n, -1, np.int32)
    for i, c in enumerate(cs):
        owner[c.nodes] = i
    idx = {c.cid: i for i, c in enumerate(cs)}
    ch_records = [{"cid": c.cid, "position": list(c.position), "size": int(len(c.nodes))} for c in cs]
    lab = None
    if cfg["physics"]:
        from .physics import PhysicalLab
        lab = PhysicalLab(ch_records, resources=float(cfg["resources"]))
    tap = _Tap(w, lab, lambda node: cs[int(owner[node])].cid if owner[node] >= 0 else None)
    f = Field(w, _settings(cfg), cfg["seed"], keep_states=False)
    tap.field = f
    prev = apparatus.state(w.state, cs, np.zeros(0, np.int32))
    steps, events, physical = [], [], []
    applied_phys: list[tuple[int, int, str]] = []
    for _ in range(cfg["horizon"]):
        n_ev = len(f.history.events)
        f.step()
        delta, owners, actions = tap.take()
        st = w.state
        t = w.t - f.t0
        if lab is not None:
            physical += tap.take_requests()
            pev, done = lab.step(t)
            physical += pev
            if done:  # completed transfers: the requested connections now exist in the runtime (next step's record)
                w.engine.apply([a for a, _ in done])
            pending_phys = [(int(owner[a.src]), int(owner[a.dst]), bay) for a, bay in done]
        cur = apparatus.state(st, cs, delta.ignitions)
        acts = {e["source"]: e["id"] for e in f.history.events[n_ev:] if e["type"] == "act"}
        for ev in apparatus.events(prev, cur, cs, t):
            if ev["type"].startswith("containment"):
                ops = sorted(set(owners))
                ev["cause"] = ([f"operation:{o}" for o in ops] + [f"causal_event:{acts[o]}" for o in ops if o in acts]
                               if ops else ["runtime:connection_turnover"])
            else:
                a, b = (idx[x] for x in ev["pair"].split("|"))
                ev["cause"] = _conduit_causes(delta, st, owner, (min(a, b), max(a, b)), actions, applied_phys)
            events.append(ev)
        rec_step = {"t": t, "fingerprint": w.engine.fingerprint(), "digest": apparatus.digest(cur), **cur}
        if lab is not None:
            rec_step["physics"] = {"fingerprint": lab.fingerprint(), **lab.state()}
            applied_phys = pending_phys
        steps.append(rec_step)
        prev = cur
    rec = {"schema": SCHEMA, "config": cfg, "chambers": ch_records, "layout": lab.layout() if lab is not None else None,
           "steps": steps, "events": events, "physical_events": physical,
           "operations": sorted({o.label for o in f.ops.values()}),
           "elapsed_s": round(time.time() - t0, 2),
           "note": "Apparatus states are derived from the runtime state (xzr/lab/apparatus.py); the renderer draws "
                   "these values only. Simulation-internal; no physical apparatus exists."}
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            raise FileExistsError(f"{out} exists; records are never overwritten")
        out.write_text(json.dumps(rec, separators=(",", ":")))
    return rec
