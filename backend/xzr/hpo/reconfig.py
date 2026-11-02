"""HPO-003: Recursive reconfiguration of the Ziran System's own experiment settings.

Between epochs of a run, a controller reads what the HPO run produced in the last epoch (the field's records and its
causal history — not the world's true state) and changes the experiment's own settings: observation channels, the
evaluation order of operations, time scales (sampling periods), resource allocation, the coupling structure, history
reinsertion conditions and stopping conditions — and it can *propose* new observation variables.

Sandbox. A change is a record ``{"path": ..., "value": ..., "op": "set" | "add" | "remove"}`` whose path is in
``SANDBOX`` and whose value passes that path's check. Nothing else can be changed: no code is loaded, generated or
modified; nothing outside the run (files, network, other processes) is touched; the world is not addressed directly —
only the settings through which the HPO layer observes and acts. A rejected change raises ``SandboxError`` and is
recorded; it is never applied.

Proposal ≠ validation. ``propose`` records a variable with its rationale and the events that motivated it
(status ``proposed``). A proposed variable is *adopted* only if the configuration has an implementation for it
(observe.DERIVED); its effectiveness is a separate paired test on held-out seeds (experiments.py, HPO-003 validation),
and only that test can mark it ``validated``. A proposal without an implementation stays ``proposed (no
implementation; untestable here)``.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from .field import Field
from .metarevision import MetaReviser, RuleTable
from .observe import CHANNELS, DERIVED, InstrumentSpec
from .operations import NEEDS
from .reachability import compare_levels, delta, levels, reachability, realised
from .registry import KINDS

EPOCH = 60
_BLIND_REASONS = ("instrument_mismatch", "scale_mismatch", "time_window_mismatch", "boundary_invisible", "unmeasured",
                  "unmeasurable")


class SandboxError(ValueError):
    pass


def _kind_of(path: str) -> str:
    k = path.split(".")[1]
    if k not in KINDS:
        raise SandboxError(f"{path}: unknown kind {k!r}")
    return k


SANDBOX: dict[str, Any] = {
    "catalog": lambda v: v in CHANNELS and v != "interior",
    "instruments.*.level": lambda v: isinstance(v, int) and 0 <= v <= 3,
    "instruments.*.window": lambda v: isinstance(v, int) and 1 <= v <= 16,
    "instruments.*.period": lambda v: isinstance(v, int) and 1 <= v <= 8,
    "instruments.*.penetration": lambda v: isinstance(v, int | float) and 0.0 <= v <= 1.0,
    "instruments.*.channels": lambda v: v in CHANNELS and v != "interior",
    "order": lambda v: isinstance(v, list) and sorted(v) == sorted(KINDS),
    "allocation.*": lambda v: isinstance(v, int | float) and 0.25 <= v <= 4.0,
    "resources.pool_per_step": lambda v: isinstance(v, int | float) and 0.5 <= v <= 8.0,
    "couplable": lambda v: isinstance(v, list) and len(v) == 2 and set(v) <= set(KINDS),
    "history.lag": lambda v: isinstance(v, int) and 10 <= v <= 400,
    "history.every": lambda v: isinstance(v, int) and 10 <= v <= 400,
    "history.reinsert": lambda v: isinstance(v, bool),
    "stop.all_ceased": lambda v: isinstance(v, bool),
    "variables": lambda v: v in DERIVED,
}


def _pattern(path: str) -> str:
    parts = path.split(".")
    if parts[0] in ("instruments", "allocation") and len(parts) >= 2:
        _kind_of(path)
        parts[1] = "*"
    return ".".join(parts)


def check(change: dict) -> None:
    if set(change) - {"path", "value", "op", "why"}:
        raise SandboxError(f"unknown change fields {sorted(set(change) - {'path', 'value', 'op', 'why'})}")
    pat = _pattern(change.get("path", ""))
    if pat not in SANDBOX:
        raise SandboxError(f"path {change.get('path')!r} is outside the sandbox")
    if change.get("op", "set") not in ("set", "add", "remove"):
        raise SandboxError("op must be set, add or remove")
    if not SANDBOX[pat](change.get("value")):
        raise SandboxError(f"{change['path']}: value {change.get('value')!r} rejected")


def apply(f: Field, change: dict, causes: list[int]) -> int:
    """Apply one checked change to a running field; returns its causal-history event."""
    check(change)
    path, v, op = change["path"], change["value"], change.get("op", "set")
    before = copy.deepcopy({k: f.s[k] for k in ("catalog", "instruments", "order", "allocation", "resources",
                                                 "history", "stop", "variables")})
    parts = path.split(".")
    touched = []
    if parts[0] == "catalog":
        cat = set(f.instruments.catalog)
        cat = cat | {v} if op != "remove" else cat - {v}
        f.instruments.catalog = tuple(c for c in CHANNELS if c in cat)
        f.s["catalog"] = list(f.instruments.catalog)
    elif parts[0] == "instruments":
        kind, attr = parts[1], parts[2]
        inst = f.s["instruments"].setdefault(kind, {})
        for o in f.live():
            if kind not in o.kinds:
                continue
            if attr == "channels":
                ch = set(o.instrument.channels)
                ch = ch | {v} if op != "remove" else ch - {v}
                o.instrument = o.instrument.with_(channels=tuple(c for c in CHANNELS if c in ch))
                inst["channels"] = list(o.instrument.channels)
            else:
                o.instrument = o.instrument.with_(**{attr: v})
                inst[attr] = v
            touched.append(o)
        InstrumentSpec.from_dict({**InstrumentSpec().to_dict(), **{k: x for k, x in inst.items()}})
    elif parts[0] == "order":
        f.s["order"] = list(v)
    elif parts[0] == "allocation":
        kind = parts[1]
        f.s["allocation"][kind] = float(v)
        for o in f.live():
            if kind in o.kinds:
                o.budget = float(np.mean([float(f.s["allocation"].get(k, 1.0)) for k in o.kinds]))
                touched.append(o)
    elif parts[0] == "resources":
        f.s["resources"][parts[1]] = float(v)
    elif parts[0] == "couplable":
        pair = frozenset(v)
        f.couplable = f.couplable | {pair} if op == "add" else f.couplable - {pair}
    elif parts[0] in ("history", "stop"):
        f.s[parts[0]][parts[1]] = v
    elif parts[0] == "variables":
        if v not in f.s["variables"]:
            f.s["variables"].append(v)
            f.instruments.catalog = tuple(dict.fromkeys((*f.instruments.catalog, v)))
            for o in f.live():
                o.mem["_variables"] = list(f.s["variables"])
                if "picturing" in o.kinds:
                    o.instrument = o.instrument.with_(channels=tuple(sorted(set(o.instrument.channels) | {v})))
    after = copy.deepcopy({k: f.s[k] for k in before})
    eid = f.history.add(f.world.t, "config", "ziran", path, causes, before if f.history.keep_states else None,
                        after if f.history.keep_states else None, {"change": change})
    for o in touched:
        f._notify(o, eid)
    return eid


class Controller:
    """Rule-based, deterministic reconfiguration from one epoch's records (``mode='recursive'``), or the same number
    of uniformly random valid changes (``mode='random'``, the control: any change vs result-driven change)."""

    def __init__(self, mode: str = "recursive", seed: int = 0, budget: list[int] | None = None,
                 trace_reachability: bool = False, meta: MetaReviser | None = None,
                 authority: list[str] | None = None, max_changes_per_epoch: int | None = None):
        assert mode in ("recursive", "random", "static")
        self.mode = mode
        self.trace_reachability = trace_reachability  # opt-in: record what each change opened or closed
        self.meta = meta  # opt-in: revise this controller's own rule parameters (metarevision.py)
        # revision authority: the sandbox path patterns this controller may change (None = all of the sandbox) and the
        # most changes it may make per epoch (None = unlimited); a change outside either is rejected and recorded
        self.authority = None if authority is None else set(authority)
        self.max_changes_per_epoch = max_changes_per_epoch
        self.rules = meta.rules if meta is not None else RuleTable()
        self.rng = np.random.default_rng([seed, 0x5A4952])
        self.trace: list[dict] = []
        self.proposals: list[dict] = []
        self.rejected: list[dict] = []
        self.budget = list(budget or [])  # random mode: number of changes per epoch
        self._mark = (0, None)
        self.counts: list[int] = []
        self._pending: list[dict] = []  # applied changes awaiting their next epoch (levels, realised)

    def start(self, f: Field) -> None:
        self._mark = (len(f.history.events), copy.deepcopy(f.stats["evaluations"]))

    def _settle(self, f: Field, evs: list[dict], epoch: int) -> None:
        """The epoch after earlier changes has run: record what the operations did and the levels now (dynamic part)."""
        if not self._pending:
            return
        nxt = levels(f)
        real = realised(f, evs, epoch, EPOCH)
        for rec in self._pending:
            lv = rec["levels"]
            lv["next"] = nxt
            lv["dynamic"] = compare_levels(lv["before"], nxt)
            rec["realised"] = real
        self._pending = []

    def finalize(self, f: Field, epoch: int) -> None:
        """Call after the last epoch: settles the changes made at the end of the epoch before it."""
        self._settle(f, f.history.events[self._mark[0]:], epoch)

    def end_epoch(self, f: Field, epoch: int) -> list[dict]:
        if self.mode == "static":
            self.counts.append(0)
            return []
        evs = f.history.events[self._mark[0]:]
        self._settle(f, evs, epoch)
        if self.meta is not None and self.mode == "recursive":
            self.meta.judge(self._blindness(f, evs), epoch)
        changes = self._decide(f, evs) if self.mode == "recursive" else self._random(f, epoch)
        applied = []
        lv_before = levels(f) if self.trace_reachability and changes else None
        for ch, causes in changes:
            try:
                if self.authority is not None and _pattern(ch["path"]) not in self.authority:
                    raise SandboxError(f"{ch['path']}: outside this controller's revision authority")
                if self.max_changes_per_epoch is not None and len(applied) >= self.max_changes_per_epoch:
                    raise SandboxError(f"{ch['path']}: over the change budget of {self.max_changes_per_epoch} per epoch")
                before = reachability(f) if self.trace_reachability else None
                eid = apply(f, ch, causes)
                rec = {**ch, "event": eid, "t": f.world.t, "epoch": epoch}
                if self.meta is not None:  # the rule parameters in force when this change was decided (did a revision reach it?)
                    rec["rules_in_force"] = dict(self.rules.params)
                if before is not None:
                    rec["reachability"] = delta(before, reachability(f))
                    lv_after = levels(f)
                    rec["levels"] = {"before": lv_before, "after": lv_after, "static": compare_levels(lv_before, lv_after)}
                    lv_before = lv_after  # the next change of this epoch starts from the state this one left
                    self._pending.append(rec)
                applied.append(rec)
                if self.meta is not None and ch.get("why") in _BLIND_REASONS and "." in ch["path"]:
                    self.meta.register(ch["path"].split(".")[1], ch["why"], eid, epoch, causes)
            except SandboxError as e:
                self.rejected.append({**ch, "error": str(e), "t": f.world.t})
        self.trace += applied
        self.counts.append(len(applied))
        self.start(f)
        return applied

    # ------------------------------------------------------------------ result-driven policy
    def _blindness(self, f: Field, evs: list[dict]) -> dict[str, dict[str, list[int]]]:
        """kind → reason → ids of the unobservable events (the reasons operations were blind in these events)."""
        live = {o.oid: o for o in f.live()}
        blind: dict[str, dict[str, list[int]]] = {}
        for e in evs:
            if e["type"] == "unobservable" and e["source"] in live:
                for kind, reason in e["detail"]["reasons"].items():
                    blind.setdefault(kind, {}).setdefault(reason, []).append(e["id"])
        for o in live.values():
            for kind, (outcome, reason, _) in o.mem.get("_last_ign", {}).items():
                if outcome == "UNOBSERVABLE":
                    blind.setdefault(kind, {}).setdefault(reason, [])
        return blind

    def _decide(self, f: Field, evs: list[dict]) -> list[tuple[dict, list[int]]]:
        out: list[tuple[dict, list[int]]] = []
        seen_paths: set[str] = set()

        def add(ch: dict, causes: list[int]) -> None:
            if ch["path"] not in seen_paths:
                seen_paths.add(ch["path"])
                out.append((ch, causes[-8:]))

        live = {o.oid: o for o in f.live()}
        # 1. observation channels / time windows / penetration, from why operations were blind
        blind = self._blindness(f, evs)
        for kind, reasons in blind.items():
            reason = max(reasons, key=lambda r: len(reasons[r]))
            if reason in self.rules.exhausted:
                continue
            ids = reasons[reason]
            need = NEEDS[kind]
            if reason == "instrument_mismatch":
                for ch in need:
                    add({"path": f"instruments.{kind}.channels", "value": ch, "op": "add", "why": reason}, ids)
                    break
            elif reason == "scale_mismatch":
                lvl = 2 if "boundary_flow" in need else max(lv for lv, _ in need.values())
                add({"path": f"instruments.{kind}.level", "value": int(lvl), "why": reason}, ids)
            elif reason == "time_window_mismatch":
                add({"path": f"instruments.{kind}.window", "value": int(min(w for _, w in need.values())),
                     "why": reason}, ids)
                add({"path": f"instruments.{kind}.period", "value": 2, "why": reason}, ids)
            elif reason == "boundary_invisible":
                add({"path": f"instruments.{kind}.penetration", "value": self.rules.params["penetration"],
                     "why": reason}, ids)
            elif reason == "unmeasured":
                cur = float(f.s["allocation"].get(kind, 1.0))
                add({"path": f"allocation.{kind}", "value": min(4.0, cur * self.rules.params["alloc_step"]),
                     "why": reason}, ids)
            elif reason == "unmeasurable":
                for ch in need:
                    if ch not in f.instruments.catalog:
                        add({"path": "catalog", "value": ch, "op": "add", "why": reason}, ids)
        # 2. resources: kinds whose requests were suppressed for lack of resources
        starved: dict[str, list[int]] = {}
        for e in evs:
            if e["type"] == "suppress" and e.get("detail", {}).get("why") == "resources" and e["target"] in live:
                for k in live[e["target"]].kinds:
                    starved.setdefault(k, []).append(e["id"])
        for k, ids in starved.items():
            if len(ids) >= 2:
                cur = float(f.s["allocation"].get(k, 1.0))
                add({"path": f"allocation.{k}", "value": min(4.0, cur * 1.25), "why": "suppressed"}, ids)
        # 3. evaluation order: an operation that transforms another more often than the reverse goes first
        flows: dict[tuple[str, str], list[int]] = {}
        for e in evs:
            if e["type"] in ("transform", "filter") and e["source"] in live and e["target"] in live:
                a, b = live[e["source"]].kinds[0], live[e["target"]].kinds[0]
                if a != b:
                    flows.setdefault((a, b), []).append(e["id"])
        order = list(f.s["order"])
        moved_ids: list[int] = []
        for (a, b), ids in sorted(flows.items(), key=lambda kv: -len(kv[1])):
            if len(ids) >= 3 and len(ids) > len(flows.get((b, a), [])) and order.index(a) > order.index(b):
                order.remove(a)
                order.insert(order.index(b), a)
                moved_ids += ids
        if order != f.s["order"]:
            add({"path": "order", "value": order, "why": "transformation flow"}, moved_ids)
        # 4. time scale: kinds that ignited and ceased within one epoch are sampled twice as often
        fast: dict[str, list[int]] = {}
        for e in evs:
            if e["type"] == "cease" and e["source"] in live:
                fast.setdefault(live[e["source"]].kinds[0], []).append(e["id"])
        for k, ids in fast.items():
            per = int(f.s["instruments"].get(k, {}).get("period", 2))
            if per > 1:
                add({"path": f"instruments.{k}.period", "value": max(1, per // 2), "why": "ceased within epoch"}, ids)
        # 5. coupling structure: pairs that decoupled within the epoch are no longer coupled
        for e in evs:
            if e["type"] == "split" and e.get("detail", {}).get("why") == "co-activation stopped":
                parts = [p for lab in e["detail"].get("parts", []) for p in lab.split("∘")]
                if len(set(parts)) >= 2:
                    pair = sorted(set(parts))[:2]
                    if frozenset(pair) in f.couplable:
                        add({"path": "couplable", "value": pair, "op": "remove", "why": "decoupled"}, [e["id"]])
        # 6. history reinsertion: reinsertions that caused nothing later → longer lag
        rein = [e["id"] for e in evs if e["type"] == "reinsert"]
        if rein and f.s["history"]["reinsert"]:
            caused = {c for e in evs for c in e["causes"]}
            if not caused & set(rein):
                lag = int(f.s["history"]["lag"] + self.rules.params["lag_step"])
                add({"path": "history.lag", "value": min(400, lag), "why": "reinsertions without downstream event"}, rein)
        # 7. stopping: every operation ceased throughout the epoch
        ser = f.stats["series"]
        if ser["ops"] and all(c == o for c, o in zip(ser["ceased"][-EPOCH:], ser["ops"][-EPOCH:], strict=False)):
            add({"path": "stop.all_ceased", "value": True, "why": "all ceased for an epoch"}, [])
        # 8. new variables (proposals)
        self._propose(f, evs)
        for p in self.proposals:
            if p["status"] == "proposed" and p["name"] in DERIVED and p["name"] not in f.s["variables"]:
                add({"path": "variables", "value": p["name"], "op": "add", "why": "adopt proposal"}, p["evidence"])
                p["status"] = "adopted (validation pending)"
        return out

    def _propose(self, f: Field, evs: list[dict]) -> None:
        names = {p["name"] for p in self.proposals}
        pic = [o.mem.get("picturing", {}) for o in f.live() if "picturing" in o.kinds]
        tol = min((o.ign["picturing"]["tolerance"] for o in f.live() if "picturing" in o.kinds), default=None)
        errs = [p.get("error", 0.0) for p in pic]
        revs = [e["id"] for e in evs if e["type"] == "revise"]
        if tol is not None and errs and max(errs) > tol and revs and "activity_trend" not in names:
            self.proposals.append({"name": "activity_trend", "status": "proposed", "t": f.world.t, "evidence": revs,
                                   "rationale": "picturing error stays above tolerance after revising categories: "
                                                "the error may come from change over time that a level picture "
                                                "cannot carry"})
        veiled = [e["id"] for e in evs if e["type"] == "unobservable"
                  and "boundary_invisible" in e["detail"]["reasons"].values()]
        if len(veiled) >= 5 and "veil_coverage" not in names:
            self.proposals.append({"name": "veil_coverage", "status": "proposed (no implementation; untestable here)",
                                   "t": f.world.t, "evidence": veiled[:8],
                                   "rationale": "operations repeatedly blinded by veils: a variable for how much of "
                                                "the field is veiled could anticipate blindness"})
        conflicts = [e["id"] for e in evs if e["type"] == "conflict"]
        if len(conflicts) >= 5 and "conflict_density" not in names:
            self.proposals.append({"name": "conflict_density", "status": "proposed (no implementation; untestable "
                                   "here)", "t": f.world.t, "evidence": conflicts[:8],
                                   "rationale": "frequent opposite threshold factors on shared configurations"})

    # ------------------------------------------------------------------ control: random valid changes
    def _random(self, f: Field, epoch: int) -> list[tuple[dict, list[int]]]:
        k = self.budget[epoch] if epoch < len(self.budget) else 0
        out: list[tuple[dict, list[int]]] = []
        for _ in range(k):
            kind = str(self.rng.choice(KINDS))
            choice = int(self.rng.integers(7))
            if choice == 0:
                ch = {"path": f"instruments.{kind}.level", "value": int(self.rng.integers(0, 4))}
            elif choice == 1:
                ch = {"path": f"instruments.{kind}.period", "value": int(self.rng.integers(1, 5))}
            elif choice == 2:
                ch = {"path": f"instruments.{kind}.penetration", "value": float(self.rng.choice([0.0, 0.7]))}
            elif choice == 3:
                ch = {"path": f"allocation.{kind}", "value": float(self.rng.choice([0.5, 1.0, 1.5, 2.0]))}
            elif choice == 4:
                order = list(KINDS)
                self.rng.shuffle(order)
                ch = {"path": "order", "value": [str(x) for x in order]}
            elif choice == 5:
                ch = {"path": "history.lag", "value": int(self.rng.integers(20, 120))}
            else:
                ch = {"path": f"instruments.{kind}.window", "value": int(self.rng.integers(1, 9))}
            ch["why"] = "random control"
            out.append((ch, []))
        return out
