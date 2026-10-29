"""MEOS-0, sixth stage: repair controllers. A controller that, while a run is stepping, senses a stress from the run's own traces, enumerates the repair actions it has, selects one, applies it, watches the result and, if the run has not recovered, moves to the next.

The loop is the same for every kind; only what differs between the kinds differs:

  none         never acts.
  fixed        one action chosen before any run was looked at (a pulse of 2.0 at A1's cell, the recovery action of the earlier stages), applied once whenever a stress is detected. It does not try anything else.
  rule_based   maps each sensed damaged feature to the action that undoes it (coupling -> restore the gain, resource -> restore regrow and charge, renewal -> restore the efficiency, then reconnect the feedback, Address -> restore, history -> the M2 tap), in the
               order the features are listed. It knows nothing about what worked.
  cost_aware   takes the plans of a library (validated on seeds the controller is not evaluated on) whose sensed signature matches, drops those with no expected recovery, and tries the one with the highest expected recovery first, the cheapest among equals.
  delayed      cost_aware, acting ``delay`` ticks after the decision.
  noisy        cost_aware on a detection that flips each sensed feature with probability ``noise`` (and without the debounce).

Nothing is written for a case: the stress is never read from the schedule; the controller sees the five sensed features of ``reconf.sense`` and the run's own status. Every decision is logged: what was detected, which plans were available, which were rejected and why, the one selected, its estimated cost and
expected recovery, and (filled in afterwards) what actually happened. The recorded schedule (the injected interventions included) replays the same run without the controller.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from . import engine as E
from . import reconf as RC
from . import repair6 as R

KINDS = ("none", "fixed", "rule_based", "cost_aware", "delayed", "noisy")
FIXED_PLAN = {"id": "fixed: pulse 2.0", "actions": [{"action": "resource.pulse", "magnitude": 2.0, "duration": 0}], "klass": "B"}
RULES: dict[str, list[dict]] = {  # sensed damaged feature -> the actions that undo it, in the order they are tried
    "coupling": [{"id": "rule: restore coupling gain", "actions": [{"action": "coupling.restore", "magnitude": 1.0, "duration": 0}], "klass": "B"}],
    "resource": [{"id": "rule: restore regrow and charge", "actions": [{"action": "resource.inflow", "magnitude": 0.02, "duration": 120}], "klass": "B"}],
    "renewal": [{"id": "rule: restore renewal efficiency", "actions": [{"action": "renewal.restore", "magnitude": 1.0, "duration": 0}], "klass": "B"},
                {"id": "rule: reconnect feedback", "actions": [{"action": "renewal.restart", "magnitude": 0.0, "duration": 0}], "klass": "B"}],
    "address": [{"id": "rule: restore Address", "actions": [{"action": "address.restore", "magnitude": 0.0, "duration": 0}], "klass": "B"}],
    "history": [{"id": "rule: M2 tap", "actions": [{"action": "internal.m2_tap", "magnitude": 0.0, "duration": 0}], "klass": "A"}],
}


def _get(cfg: dict, path: str, default: float) -> float:
    cur: Any = cfg
    for p in path.split("."):
        cur = cur.get(p) if isinstance(cur, dict) else None
        if cur is None:
            return default
    return float(cur)


def current_stress(run: E.Run) -> R.Stress:
    """A Stress object whose ``stressed`` values are what the world has *now* (read from the running configuration): what a temporary bridge returns to, where a gradual restoration starts."""
    cur = {k: _get(run.cfg, k, v) for k, v in R.BASE.items()}
    return R.Stress("sensed", "sensed", "the world as it is now", lambda t: [], cur)


class RepairController:
    def __init__(self, kind: str, library: list[dict] | None = None, *, seed: int = 0, start: int = 60, debounce: int = 3, delay: int = 15, noise: float = 0.1, max_attempts: int = 3, wait: int = 25):
        if kind not in KINDS:
            raise ValueError(f"unknown repair controller {kind!r}")
        self.kind, self.lib = kind, library or []
        self.rng = np.random.default_rng(seed + 4242)
        self.start, self.debounce, self.delay, self.noise, self.max_attempts, self.wait = start, 1 if kind == "noisy" else debounce, delay if kind == "delayed" else 0, noise if kind == "noisy" else 0.0, max_attempts, wait
        self.streak: dict[str, int] = {}
        self.queue: list[dict] = []  # interventions with a future tick (the later steps of a gradual restoration, the return of a bridge)
        self.attempts: list[dict] = []
        self.tried: set[str] = set()
        self.plan_queue: list[dict] = []
        self.pending: dict | None = None  # a decision waiting for its (delayed) action tick
        self.active: dict | None = None  # the attempt being watched
        self.done = False
        self.log: list[dict] = []
        self._first: dict = {}

    # -- sensing
    def _sensed(self, run: E.Run) -> dict[str, str]:
        f = RC.sense(run)
        if self.noise > 0:
            for k in RC.FEATURES:
                if self.rng.random() < self.noise:
                    f[k] = RC.NORMAL[k] if f[k] != RC.NORMAL[k] else ("lost" if k == "history" else "degraded" if k == "address" else "weak" if k == "coupling" else "reduced")
        return f

    # -- candidate plans
    def _candidates(self, sensed: dict, firm: list[str]) -> tuple[list[dict], list[dict]]:
        """(available plans in the order they will be tried, rejected plans with the reason)."""
        rejected: list[dict] = []
        if self.kind == "fixed":
            return [FIXED_PLAN], rejected
        if self.kind == "rule_based":
            plans = [p for f in firm for p in RULES.get(f, [])]
            return plans, rejected
        sig = {**sensed}
        avail = []
        for p in self.lib:
            if not any(all(s.get(k) == sig.get(k) for k in RC.FEATURES) for s in p["signatures"]):
                rejected.append({"plan": p["id"], "reason": "its signature does not match what is sensed"})
            elif p["expected"] <= 0:
                rejected.append({"plan": p["id"], "reason": "no expected recovery"})
            else:
                avail.append(p)
        avail.sort(key=lambda p: (-p["expected"], p["cost"], p["id"]))
        return avail, rejected

    # -- acting
    def _apply(self, run: E.Run, plan: dict) -> None:
        st = current_stress(run)
        t = run.t + 1
        for a in plan["actions"]:
            for iv in R.build_action(a["action"], st, a["magnitude"], t, a["duration"]):
                if iv["tick"] <= t:
                    run.inject({k: v for k, v in iv.items() if k != "tick"})
                else:
                    self.queue.append(iv)

    def step(self, run: E.Run) -> None:
        t = run.t
        due = [iv for iv in self.queue if iv["tick"] <= t + 1]
        for iv in due:
            run.inject({k: v for k, v in iv.items() if k != "tick"})
            self.queue.remove(iv)
        if self.kind == "none" or t < self.start or self.done:
            return
        status = run.frames[-1]["status"] if run.frames else "DEGRADED"
        if self.active is not None:  # watching an attempt: after ``wait`` ticks, did the run recover?
            if t >= self.active["decided"] + self.wait:
                recent = [f["status"] for f in run.frames[-10:]]
                ok = all(s == "ACTIVE" for s in recent)
                self.active["entry"]["actual"] = {"tick": t, "recovered_so_far": ok, "status_now": status}
                self.active = None
                if ok:
                    self.done = True
                    return
            else:
                return
        if self.pending is not None:
            if t >= self.pending["act_at"]:
                self._apply(run, self.pending["plan"])
                self.active = {"decided": t, "entry": self.pending["entry"]}
                self.pending = None
            return
        sensed = self._sensed(run)
        for k in RC.FEATURES:
            self.streak[k] = self.streak.get(k, 0) + 1 if sensed[k] != RC.NORMAL[k] else 0
        firm = [k for k in RC.FEATURES if self.streak[k] >= self.debounce]
        if not firm and not self.attempts:
            return
        if len(self.attempts) >= self.max_attempts:
            self.done = True
            return
        if not firm and status == "ACTIVE":
            self.done = True
            return
        if not self.plan_queue and not self.attempts:
            avail, rejected = self._candidates(sensed, firm)
            self.plan_queue = [p for p in avail if p["id"] not in self.tried]
            self._first = {"sensed": sensed, "firm": firm, "available": [p["id"] for p in avail], "rejected": rejected}
        elif not self.plan_queue:
            self.done = True  # nothing left to try
            return
        plan = self.plan_queue.pop(0)
        self.tried.add(plan["id"])
        base = self._first or {"sensed": sensed, "firm": firm, "available": [], "rejected": []}
        entry = {"tick": t, "kind": "decide", "attempt": len(self.attempts) + 1, "detected": base["firm"], "sensed": base["sensed"], "available": base["available"], "rejected": base["rejected"],
                 "remaining_after": [p["id"] for p in self.plan_queue], "selected": plan["id"], "actions": copy.deepcopy(plan["actions"]), "class": plan.get("klass"), "estimated_cost": plan.get("cost"), "expected_recovery": plan.get("expected"), "actual": None}
        self.log.append(entry)
        self.attempts.append(entry)
        if self.delay > 0:
            self.pending = {"act_at": t + self.delay, "plan": plan, "entry": entry}
        else:
            self._apply(run, plan)
            self.active = {"decided": t, "entry": entry}


def run_repaired(cfg: dict, interventions: list[dict], controller: RepairController | None) -> dict:
    """Step a run with a repair controller acting before each tick. The record's schedule includes the injected interventions."""
    run = E.Run(copy.deepcopy(cfg), copy.deepcopy(interventions))
    while True:
        if controller is not None:
            controller.step(run)
        if not run.step():
            break
    rec = E.finalize(run.record(), cfg, run.interventions)
    if controller is not None:
        for e in controller.log:
            if e["actual"] is None:
                e["actual"] = {"tick": len(rec["frames"]) - 1, "recovered_so_far": rec["final_status"]["label"] == "ACTIVE", "status_now": rec["final_status"]["label"]}
        rec["controller"] = {"kind": controller.kind, "log": controller.log, "attempts": len(controller.attempts)}
    else:
        rec["controller"] = {"kind": "none", "log": [], "attempts": 0}
    return rec
