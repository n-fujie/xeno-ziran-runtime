"""MEOS-0, fifth stage: world-responsive reconfiguration — a controller that senses what a run is doing and moves between known MFS.

Nothing here is a script of cases. A controller reads the run's own traces (never the schedule of the stress), derives a sensed environment (which of history, coupling, resource, renewal
and address look normal), matches it against the *conditions* of the MFS library of experiment F, and — if the matched conditions have known retaining sets — moves to the one that costs
least to reach from what is currently enabled. The move is a set of ordinary interventions (``ROUTE`` and ``RECONNECT``) injected into the run, so the recorded schedule replays the same run
without the controller. What was sensed, which candidates existed, what was chosen, what it cost and whether it worked are recorded; a switch that did not help is recorded as a failure.

Controllers: ``none`` (control), ``fixed`` (always the same fallback, whatever was sensed), ``adaptive`` (the library rule above: it can only enable what a route needs), ``adaptive_shed`` (the same,
and it also removes what the destination MFS does not retain: an MFS is a statement about a set that is retained *and nothing else*, the dynamics are not monotone, so reaching it can mean shedding), ``delayed``
(adaptive, acting after a delay), ``noisy`` (adaptive, on a sensed environment that is wrong at random, so that false switches occur). None of them is tuned to win.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from . import engine as E

WINDOW = 12
REFERENCE = (20, 60)  # the ticks over which a reference level of each sensed quantity is taken (before any stress in the experiments)
FEATURES = ("history", "coupling", "resource", "renewal", "address")
NORMAL = {"history": "ok", "coupling": "normal", "resource": "normal", "renewal": "normal", "address": "ok"}


def enabled_components(run: E.Run, universe: tuple[str, ...]) -> set[str]:
    """The components of the universe that are currently in place, read from the run's configuration."""
    cfg = run.cfg
    on: set[str] = set()
    for c in universe:
        if c == "A2":
            ok = run.ent["A2"]["present"]
        elif c == "resource_gradient":
            ok = bool(cfg["environment"]["gradient"])
        elif c == "history":
            ok = bool(cfg["history"]["enabled"])
        elif c == "interaction_channel":
            ok = bool(cfg["channels"]["interaction"])
        elif c == "sensor_resource":
            ok = bool(cfg["channels"]["sensor_resource"])
        elif c == "sensor_alteration":
            ok = bool(cfg["channels"]["sensor_alteration"])
        elif c == "environmental_persistence":
            ok = cfg["environment"]["persistence"] != 1.0
        elif c == "feedback":
            ok = bool(cfg["channels"]["feedback"])
        elif c == "resource_renewal":
            ok = cfg["environment"]["regrow"] > 0 and cfg["power"]["charge"] > 0
        elif c == "m2_tap":
            ok = (cfg.get("m2") or {}).get("sense", "none") != "none"
        else:
            ok = True
        if ok:
            on.add(c)
    return on


def _tail(run: E.Run, key: str, n: int = WINDOW) -> list[float]:
    v = run.traces.get(key, [])
    return [float(x) for x in v[-n:]]


def _ref(run: E.Run, key: str) -> float | None:
    v = run.traces.get(key, [])
    seg = [float(x) for x in v[REFERENCE[0] : REFERENCE[1]]]
    return float(np.mean(seg)) if len(seg) >= 10 else None


def sense(run: E.Run) -> dict[str, str]:
    """The sensed environment at this tick, from the run's own traces: which of the five features look normal. Nothing is read from the configuration of a stress."""
    f = dict(NORMAL)
    if len(run.traces.get("t", [])) < REFERENCE[1] + WINDOW:
        return f
    contrib = _tail(run, "history_contribution_a1") + _tail(run, "history_contribution_a2")
    trace = _tail(run, "history_trace_a1") + _tail(run, "history_trace_a2")
    if max(trace, default=0.0) > 0.5 and sum(contrib) < 1e-9:
        f["history"] = "lost"  # a history trace exists and lowers no threshold
    ref = _ref(run, "interaction_strength")
    if ref and ref > 1e-6 and float(np.mean(_tail(run, "interaction_strength"))) < 0.7 * ref:
        f["coupling"] = "weak"
    ref = _ref(run, "resource_flow")
    if ref and ref > 1e-6 and float(np.mean(_tail(run, "resource_flow"))) < 0.6 * ref:
        f["resource"] = "reduced"
    ref = _ref(run, "renewal_events")
    if ref and ref > 1e-6 and sum(_tail(run, "renewal_events")) == 0:
        f["renewal"] = "reduced"
    if min(_tail(run, "address_integrity_a1") + _tail(run, "address_integrity_a2"), default=1.0) < 0.9:
        f["address"] = "degraded"
    return f


def _distance(a: dict, b: dict) -> int:
    return sum(1 for k in FEATURES if a.get(k, NORMAL[k]) != b.get(k, NORMAL[k]))


class Controller:
    """One controller. ``library`` is the list of MFS of experiment F (each with its condition features); ``arrangement`` names the tap the run has available and the universe."""

    def __init__(self, kind: str, library: list[dict], arrangement: dict, *, delay: int = 15, noise: float = 0.0, seed: int = 0, start: int = 60, cooldown: int = 30, max_switches: int = 3, debounce: int = 3, fixed_route: str = "m2_tap"):
        self.kind, self.lib, self.arr = kind, library, arrangement
        self.delay = delay if kind == "delayed" else 0
        self.shed = kind in ("adaptive_shed", "adaptive_mid")  # adaptive_mid: a library of actions that survive a stress in mid-run (midrun.py), which mostly remove components
        self.noise = noise if kind == "noisy" else 0.0
        self.rng = np.random.default_rng(seed + 777)
        self.start, self.cooldown, self.max_switches = start, cooldown, max_switches
        self.debounce = 1 if kind == "noisy" else debounce
        self.fixed_route = fixed_route
        self.streak: dict[str, int] = {}
        self.pending: dict[str, Any] | None = None
        self.last_switch = -10_000
        self.switches = 0
        self.broken: set[str] = set()
        self.log: list[dict] = []
        self.current_mfs = None

    # -- the sensed environment, possibly wrong
    def _sensed(self, run: E.Run) -> dict[str, str]:
        f = sense(run)
        if self.noise > 0:
            for k in FEATURES:
                if self.rng.random() < self.noise:
                    f[k] = "ok" if f[k] != NORMAL[k] else ("lost" if k == "history" else "degraded" if k == "address" else "weak" if k == "coupling" else "reduced")
        return f

    def _match(self, sensed: dict, universe: tuple[str, ...], cur: set[str]) -> dict[str, Any]:
        """The library entries whose condition is nearest to the sensed environment and that need no component the controller has found broken; the cheapest to reach first."""
        feats = {**sensed, "tap": self.arr["tap_feature"]}
        scored = []
        for m in self.lib:
            d = _distance(m["features"], sensed) + (0 if m["features"].get("tap") == feats["tap"] else 1)
            scored.append((d, m))
        if not scored:
            return {"candidates": [], "distance": None}
        best = min(d for d, _ in scored)
        if self.kind == "adaptive_mid" and best > 0:
            return {"candidates": [], "distance": best}  # an action of the mid-run library is valid only for the signature it was found for, not for the nearest other one
        cands = []
        for d, m in scored:
            if d != best:
                continue
            need = set(m["retained"])
            if need & self.broken:
                continue
            to_enable = [c for c in m["retained"] if c not in cur]
            to_shed = [c for c in sorted(cur) if c not in m["retained"]] if self.shed else []
            cands.append({"mfs": m["id"], "condition": m["condition_id"], "retained": m["retained"], "cost": len(to_enable) + len(to_shed), "enable": to_enable, "shed": to_shed, "cardinality": m["cardinality"]})
        cands.sort(key=lambda c: (c["cost"], c["cardinality"], c["mfs"]))
        return {"candidates": cands, "distance": best}

    def _current_mfs(self, cur: set[str], sensed: dict) -> str:
        """The smallest library MFS (of the conditions nearest the environment) wholly contained in what is enabled now, or 'none'."""
        inside = [m for m in self.lib if set(m["retained"]) <= cur and _distance(m["features"], sensed) <= 1]
        return min(inside, key=lambda m: (m["cardinality"], m["id"]))["id"] if inside else "none"

    def _ops(self, enable: list[str], shed: list[str] | None = None) -> list[dict]:
        ops: list[dict] = []
        for c in shed or []:
            if c == "m2_tap":
                ops.append({"op": "ROUTE", "m2": {"sense": "none"}})
            elif c == "history":
                ops.append({"op": "ROUTE", "history": "off"})
            else:
                ops.append({"op": "REMOVE", "target": c})
        for c in enable:
            if c == "m2_tap":
                ops.append({"op": "ROUTE", "m2": dict(self.arr["tap"])})
            elif c == "history":
                ops.append({"op": "ROUTE", "history": "on"})
            else:
                ops.append({"op": "RECONNECT", "target": c})
        return ops

    def step(self, run: E.Run) -> None:
        """Called before each tick: sense, decide, and inject the intervention(s) for the next tick."""
        t = run.t
        if self.kind == "none" or t < self.start:
            return
        universe = self.arr["universe"]
        cur = enabled_components(run, universe)
        sensed = self._sensed(run)
        for k in FEATURES:
            self.streak[k] = self.streak.get(k, 0) + 1 if sensed[k] != NORMAL[k] else 0
        if self.pending is not None and t >= self.pending["act_at"]:
            self._act(run, self.pending, cur)
            self.pending = None
            return
        if self.pending is not None:
            return
        firm = [k for k in FEATURES if self.streak[k] >= self.debounce]
        if not firm or self.switches >= self.max_switches or t - self.last_switch < self.cooldown:
            return
        if "history" in firm:
            self.broken.add("history")  # a history that lowers nothing is treated as unavailable
        if self.kind == "fixed":
            to_enable = [self.fixed_route] if self.fixed_route not in cur else []
            decision: dict[str, Any] = {"candidates": [{"mfs": "fixed fallback", "condition": "-", "retained": [self.fixed_route], "cost": len(to_enable), "enable": to_enable, "shed": [], "cardinality": 1}], "distance": None}
        else:
            decision = self._match(sensed, universe, cur)
        ev = {"tick": t, "kind": "decide", "sensed": sensed, "trigger": firm, "controller": self.kind, "current_mfs": self._current_mfs(cur, sensed), "matched_distance": decision["distance"], "candidates": [{k: c[k] for k in ("mfs", "condition", "cost")} for c in decision["candidates"]]}
        if not decision["candidates"]:
            ev.update(outcome="no known route: the matched conditions have no retaining set (or all need a broken component)")
            self.log.append(ev)
            self.last_switch = t  # do not decide again at once
            return
        chosen = decision["candidates"][0]
        if chosen["cost"] == 0:
            ev.update(outcome="no switch: the chosen MFS is already wholly enabled", chosen=chosen["mfs"])
            self.log.append(ev)
            self.last_switch = t
            return
        ev.update(chosen=chosen["mfs"], cost=chosen["cost"], enable=chosen["enable"], shed=chosen.get("shed", []))
        self.log.append(ev)
        self.pending = {"act_at": t + self.delay, "chosen": chosen, "trigger": firm, "decided": t, "from": ev["current_mfs"]}
        if self.delay == 0:
            self._act(run, self.pending, cur)
            self.pending = None

    def _act(self, run: E.Run, p: dict, cur: set[str]) -> None:
        chosen = p["chosen"]
        enable = [c for c in chosen["enable"] if c not in cur]
        shed = [c for c in chosen.get("shed", []) if c in cur]
        for op in self._ops(enable, shed):
            run.inject({**op, "why": f"sensed {','.join(p['trigger'])}", "from": p["from"], "to": chosen["mfs"], "cost": chosen["cost"], "trigger": ",".join(p["trigger"])})
        self.switches += 1
        self.last_switch = run.t
        self.log.append({"tick": run.t, "kind": "switch", "from": p["from"], "to": chosen["mfs"], "enabled": enable, "shed": shed, "cost": chosen["cost"], "trigger": p["trigger"], "decided_at": p["decided"]})


def run_controlled(cfg: dict, interventions: list[dict], controller: Controller | None) -> dict:
    """Step a run with a controller acting before each tick. Returns the record (whose ``interventions`` include the injected ones: replaying it without the controller is the same run)."""
    run = E.Run(copy.deepcopy(cfg), copy.deepcopy(interventions))
    while True:
        if controller is not None:
            controller.step(run)
        if not run.step():
            break
    rec = E.finalize(run.record(), cfg, run.interventions)  # the digests cover the schedule that was actually run, the injected interventions included
    rec["controller"] = {"kind": controller.kind if controller else "none", "log": controller.log if controller else [], "switches": controller.switches if controller else 0}
    return rec


def library_from(results_f: dict[str, dict], condition_ids: list[str] | None = None) -> list[dict]:
    """The MFS of experiment F as a library for the controller: id, condition, the features of the condition, the retained components."""
    lib = []
    for cid, r in results_f.items():
        if condition_ids and cid not in condition_ids:
            continue
        for m in r["mfs"]:
            lib.append({"id": m["id"], "condition_id": cid, "features": m["environment_condition"]["features"], "retained": m["retained_components"], "cardinality": m["cardinality"]})
    return lib


# ---------------------------------------------------------------------------------------------------- what a run's switches did
def switch_outcomes(rec: dict, stress_tick: int | None) -> list[dict]:
    """For each switch of a controlled run: when it happened, what it moved between, the cost, the operation lost between the switch and the end (ticks not ACTIVE), the recovery latency
    (ticks from the switch to the next ACTIVE, if the run was not ACTIVE at the switch) and whether the operation is preserved at the end."""
    ctl: dict[str, Any] = rec["controller"]
    sw = [e for e in ctl["log"] if e["kind"] == "switch"]
    frames = rec["frames"]
    out = []
    for e in sw:
        t = e["tick"]
        status_at = frames[min(t, len(frames) - 1)]["status"]
        after = [f["status"] for f in frames[t:]]
        lat = None
        if status_at != "ACTIVE":
            lat = next((i for i, s in enumerate(after) if s == "ACTIVE"), None)
        out.append({
            "tick": t, "from": e["from"], "to": e["to"], "trigger": e["trigger"], "cost": e["cost"], "enabled": e["enabled"], "state_at_switch": status_at,
            "operation_lost_ticks_after": sum(1 for s in after if s != "ACTIVE"), "recovery_latency": lat, "preserved_at_end": frames[-1]["status"] == "ACTIVE",
            "stress_tick": stress_tick, "changes_of_state_after": sum(1 for a, b in zip(after, after[1:], strict=False) if a != b),
        })
    return out
