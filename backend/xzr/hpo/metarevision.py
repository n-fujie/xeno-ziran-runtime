"""Revision of revision rules: the controller's own rule parameters are revised from what its earlier changes did.

The HPO-003 controller (reconfig.Controller) reconfigures the instruments from the *reasons* operations were blind.
Its rules have parameters (how far to raise penetration, how much to raise an allocation, how much to lengthen a
reinsertion lag). This module adds one more level: after a rule has been applied, the next epoch shows whether the
blindness it targeted (same kind, same reason) is still there. A rule whose change did not remove it twice in a row
is *revised* (a bounded parameter step) and, when the parameter is already at its bound or has no parameter, marked
*exhausted* (the controller stops applying it and says so). Every revision is a record with its evidence.

Sandbox, as for the settings: only the parameters in ``BOUNDS`` can change, only inside their bounds, and the change
list is closed; no code is generated or loaded. Nothing here reads the world: the evidence is the controller's own
record of unobservable events.

A revised rule is a *proposal about the controller*, not a validated improvement: whether revised rules do better than
fixed ones is a separate paired comparison on held-out seeds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULTS: dict[str, float] = {
    "penetration": 0.7,  # boundary_invisible → raise the instrument's penetration to this
    "alloc_step": 1.5,  # unmeasured → multiply the kind's allocation by this
    "lag_step": 20.0,  # reinsertions without downstream event → lengthen the lag by this
}
BOUNDS: dict[str, tuple[float, float]] = {"penetration": (0.0, 1.0), "alloc_step": (1.0, 3.0),
                                          "lag_step": (0.0, 200.0)}
STEPS: dict[str, float] = {"penetration": 0.15, "alloc_step": 0.5, "lag_step": 20.0}
# the blindness reason whose rule each parameter belongs to (None: no blindness evidence for that parameter)
PARAM_OF_REASON: dict[str, str] = {"boundary_invisible": "penetration", "unmeasured": "alloc_step"}
PATIENCE = 2  # consecutive epochs in which a rule's change did not remove its blindness before it is revised


class MetaSandboxError(ValueError):
    pass


@dataclass(frozen=True)
class RuleSpec:
    """Which rule parameters exist, their defaults, bounds and signed revision steps, and which blindness reason each belongs to.
    The default spec is the HPO-003 controller's; another controller (the shared ARDS-HPO environment's) brings its own."""

    defaults: dict[str, float]
    bounds: dict[str, tuple[float, float]]
    steps: dict[str, float]
    param_of_reason: dict[str, str]


HPO_SPEC = RuleSpec(DEFAULTS, BOUNDS, STEPS, PARAM_OF_REASON)


@dataclass
class RuleTable:
    """The revisable parameters of the controller's rules, and which rules are exhausted."""

    spec: RuleSpec = HPO_SPEC
    params: dict[str, float] = field(default_factory=dict)
    exhausted: set[str] = field(default_factory=set)  # blindness reasons whose rule is no longer applied

    def __post_init__(self) -> None:
        if not self.params:
            self.params = dict(self.spec.defaults)

    def set(self, name: str, value: float) -> None:
        if name not in self.spec.bounds:
            raise MetaSandboxError(f"rule parameter {name!r} is outside the sandbox")
        lo, hi = self.spec.bounds[name]
        if not lo <= value <= hi:
            raise MetaSandboxError(f"{name}={value} outside [{lo}, {hi}]")
        self.params[name] = float(value)

    def snapshot(self) -> dict:
        return {"params": dict(self.params), "exhausted": sorted(self.exhausted)}


@dataclass
class MetaReviser:
    """Judges earlier changes by the next epoch's blindness and revises the rule table."""

    rules: RuleTable = field(default_factory=RuleTable)
    patience: int = PATIENCE
    trace: list[dict] = field(default_factory=list)
    _pending: list[dict] = field(default_factory=list)  # changes awaiting their outcome: {kind, reason, event, epoch}
    _fails: dict[str, int] = field(default_factory=dict)  # reason → consecutive failures

    def register(self, kind: str, reason: str, event: int, epoch: int, cause_ids: list[int]) -> None:
        """A blindness-targeted change was applied (event = its causal-history event)."""
        self._pending.append({"kind": kind, "reason": reason, "event": event, "epoch": epoch, "causes": cause_ids})

    def judge(self, blind: dict[str, dict[str, list[int]]], epoch: int) -> list[dict]:
        """``blind``: kind → reason → ids of unobservable events in the epoch just ended. Returns the revisions made."""
        made: list[dict] = []
        outcomes: dict[str, list[bool]] = {}
        for p in self._pending:
            persisted = p["reason"] in blind.get(p["kind"], {})
            outcomes.setdefault(p["reason"], []).append(persisted)
        self._pending = []
        for reason, results in outcomes.items():
            if reason in self.rules.exhausted:
                continue
            if any(results):
                self._fails[reason] = self._fails.get(reason, 0) + 1
            else:
                self._fails[reason] = 0
                continue
            if self._fails[reason] < self.patience:
                continue
            self._fails[reason] = 0
            spec = self.rules.spec
            param = spec.param_of_reason.get(reason)
            before = self.rules.snapshot()
            lo, hi = spec.bounds[param] if param is not None else (0.0, 0.0)
            nxt = self.rules.params[param] + spec.steps[param] if param is not None else 0.0
            if param is not None and lo - 1e-9 <= nxt <= hi + 1e-9:
                new = round(min(hi, max(lo, nxt)), 6)
                self.rules.set(param, new)
                rec = {"epoch": epoch, "revision": "parameter", "reason": reason, "param": param,
                       "from": before["params"][param], "to": new}
            else:
                self.rules.exhausted.add(reason)
                rec = {"epoch": epoch, "revision": "exhausted", "reason": reason, "param": param,
                       "note": "the rule's change did not remove the blindness it targeted and its parameter "
                               "cannot be revised further; the rule is no longer applied"}
            rec["after"] = self.rules.snapshot()
            rec["evidence_epochs"] = self.patience
            self.trace.append(rec)
            made.append(rec)
        return made
