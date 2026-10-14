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
                                  "horizon": 240, "settings": {"interaction": "all", "history": {"reinsert": True}}}


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

    def __init__(self, world):
        self.delta = None
        self.overlay_owners: list[str] = []
        self.actions: list[str] = []
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
            return apply_(actions)

        eng.step = step_tap
        world.set_owner_overlay = overlay_tap
        world.apply = apply_tap

    def take(self) -> tuple[Any, list[str], list[str]]:
        d, o, a = self.delta, self.overlay_owners, self.actions
        self.overlay_owners, self.actions = [], []
        return d, o, a


def _conduit_causes(delta, st, owner: np.ndarray, pair: tuple[int, int], actions: list[str]) -> list[str]:
    out = []
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
    tap = _Tap(w)
    f = Field(w, _settings(cfg), cfg["seed"], keep_states=False)
    cs = apparatus.chambers(w.h)
    owner = np.full(w.state.n, -1, np.int32)
    for i, c in enumerate(cs):
        owner[c.nodes] = i
    idx = {c.cid: i for i, c in enumerate(cs)}
    prev = apparatus.state(w.state, cs, np.zeros(0, np.int32))
    steps, events = [], []
    for _ in range(cfg["horizon"]):
        n_ev = len(f.history.events)
        f.step()
        delta, owners, actions = tap.take()
        st = w.state
        cur = apparatus.state(st, cs, delta.ignitions)
        t = w.t - f.t0
        acts = {e["source"]: e["id"] for e in f.history.events[n_ev:] if e["type"] == "act"}
        for ev in apparatus.events(prev, cur, cs, t):
            if ev["type"].startswith("containment"):
                ops = sorted(set(owners))
                ev["cause"] = ([f"operation:{o}" for o in ops] + [f"causal_event:{acts[o]}" for o in ops if o in acts]
                               if ops else ["runtime:connection_turnover"])
            else:
                a, b = (idx[x] for x in ev["pair"].split("|"))
                ev["cause"] = _conduit_causes(delta, st, owner, (min(a, b), max(a, b)), actions)
            events.append(ev)
        steps.append({"t": t, "fingerprint": w.engine.fingerprint(), "digest": apparatus.digest(cur), **cur})
        prev = cur
    rec = {"schema": SCHEMA, "config": cfg, "chambers": [{"cid": c.cid, "position": list(c.position),
                                                          "size": int(len(c.nodes))} for c in cs],
           "steps": steps, "events": events, "operations": sorted({o.label for o in f.ops.values()}),
           "elapsed_s": round(time.time() - t0, 2),
           "note": "Apparatus states are derived from the runtime state (xzr/lab/apparatus.py); the renderer draws "
                   "these values only. Simulation-internal; no physical apparatus exists."}
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            raise FileExistsError(f"{out} exists; records are never overwritten")
        out.write_text(json.dumps(rec, separators=(",", ":")))
    return rec
