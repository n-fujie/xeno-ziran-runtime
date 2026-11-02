"""Configuration and Ignition Engine + HPO Interaction Engine.

``Settings`` is the configuration an HPO run holds for its operations: which kinds run, their instruments, the
channel catalog, boundary, time (sampling, act delay), resources, institutional constraints, external memory, history
reinsertion, feedback, reachability horizon, the interaction switches, the evaluation order, scheduled configuration
changes and stopping conditions. It is plain JSON with a fixed set of keys (``validate``), which is also the sandbox
HPO-003 reconfigures (reconfig.py).

``Field`` runs the operations in one world. Per world step:

    1. the world advances one step (exogenous input from its own stream)
    2. scheduled configuration changes at this step
    3. every operation due to sample (its instrument period) observes, evaluates its ignition conditions, changes
       status (ignite / re-ignite / cease) and, if it fired, issues requests; requests are filtered (institution,
       closure filter), paid for (resources) and compiled into runtime intervention records
    4. interaction rules triggered by this step's acts transform other operations (ignition parameters, rules,
       instruments, budgets); standing threshold factors in conflict are resolved (competition)
    5. coupling / splitting, reclassification, history reinsertion (each on its own cadence)

Interaction switches (``Settings["interaction"]``), all off = independent operations:

    share_info           operations fill unobserved values from other operations' recent observations
    share_resources      one resource pool drawn in evaluation order (else a fixed equal share per operation)
    share_history        the external memory is readable by every operation (else each reads only its own entries)
    transform            the interaction rules (RULES) change other operations' parameters
    observation_change   veils hide regions from others; a revision propagates to overlapping instruments
    competition_adapt    conflicting threshold factors attenuate the weaker operation's rule, amplify the stronger's
    partition            coupling into composite kinds, decoupling, adoption of domains, composite splitting
    reclassify           operations whose executed actions match another kind's prototype are reclassified
    action_filter        an active closure filters other operations' acts on its region (irritation)

Everything that changes is written to the causal history with before/after state (causal.py).
"""

from __future__ import annotations

import copy
from collections import deque
from typing import Any

import numpy as np

from ..runtime.intervention import Action, Connect, Gate, Inject, ScaleThreshold, Sever
from .causal import CausalHistory
from .observe import DEFAULT_CATALOG, DERIVED, MAX_FLOW_LEVEL, Instruments, InstrumentSpec, Observation, Veil
from .operations import (
    DEFAULT_IGN,
    DEFAULT_INSTRUMENT,
    DEFAULT_RULE,
    FIRED,
    NOT_FIRED,
    REQUEST_TYPES,
    UNOBSERVABLE,
    Operation,
    Request,
    make,
)
from .registry import KINDS
from .world import World

INTERACTION_KEYS = ("share_info", "share_resources", "share_history", "transform", "observation_change",
                    "competition_adapt", "partition", "reclassify", "action_filter")
ALL_ON = dict.fromkeys(INTERACTION_KEYS, True)
ALL_OFF = dict.fromkeys(INTERACTION_KEYS, False)

DEFAULTS: dict[str, Any] = {
    "kinds": list(KINDS),
    "warmup": 40,
    "horizon": 240,
    "catalog": list(DEFAULT_CATALOG),
    "instruments": {},  # kind → instrument overrides
    "ign": {},  # kind → ignition parameter overrides
    "rule": {},  # kind → rule parameter overrides
    "boundary": {"veil_scale": 1.0, "gate_scale": 1.0},
    "time": {"act_delay": 0},
    "resources": {"pool_per_step": 2.4, "act_cost_per_node": 0.002, "connection_cost": 0.05},
    "institution": {"max_nodes_per_act": 400, "forbidden": [], "max_ops": 16, "max_new_connections_per_step": 8},
    "external_memory": {"enabled": True, "capacity": 64},
    "history": {"reinsert": False, "lag": 60, "every": 40, "data": True, "params": True, "veils": True},
    "feedback": True,
    "reach_hops": 3,
    "interaction": dict(ALL_OFF),
    "order": list(KINDS),
    "schedule": [],  # [{"at": step, "type": remove_channel|restore_channel|relocate|set_catalog, ...}]
    "stop": {"all_ceased": False},
    "allocation": {},  # kind → resource factor of operations carrying it
    "variables": [],  # adopted derived variables (observe.DERIVED); e.g. activity_trend
    "symbol_layer": False,
    "picturing_requires_symbol_channel": False,
    "placement": "shared",  # shared: overlapping regions in the two largest macro clusters; separate: one each
}

# --------------------------------------------------------------------------------------------- interaction rules
# (source kind, trigger, relation, target kind or "*", effect). Effects: ("ign", param, factor), ("primary", factor),
# ("rule", param, factor), ("instrument_level", +k), ("budget", factor). Relations: overlap = shared configurations,
# near = same macro cluster (public addresses). These rules ARE the HPO hypothesis about cross-operational
# transformation; they are explicit so that each can be inspected and ablated (Settings.interaction.transform).
RULES: list[tuple[str, str, str, str, tuple]] = [
    ("withdrawal", "act", "near", "assemblage", ("primary", 0.85)),   # a withdrawn object makes flows around it salient
    ("withdrawal", "act", "overlap", "closure", ("ign", "threshold", 0.9)),  # withdrawal raises internal recursion share
    ("transduction", "act", "overlap", "closure", ("primary", 0.9)),  # individuated structure supplies recursion
    ("transduction", "act", "overlap", "picturing", ("ign", "tolerance", 0.9)),  # structuring surprises the picture
    ("concrescence", "deposit", "overlap", "*", ("primary", 0.92)),  # data of past occasions lower later entry
    ("picturing", "act", "overlap", "transduction", ("rule", "factor", "toward1:0.25")),  # damping resists structuring
    ("closure", "act", "near", "withdrawal", ("ign", "threshold", 1.15)),  # closure reduces contact around it
    ("closure", "act", "overlap", "assemblage", ("rule", "links", 0.75)),  # closure resists new couplings
    ("assemblage", "act", "overlap", "*", ("budget", 1.1)),  # plugging in amplifies the partner's resources
]
PRIMARY = {"withdrawal": "threshold", "transduction": "threshold", "concrescence": "threshold",
           "picturing": "tolerance", "assemblage": "threshold", "closure": "threshold"}
BOUND = (0.25, 4.0)  # parameters stay within [0.25×, 4×] of their default
COUPLABLE = {frozenset(p) for p in (("assemblage", k) for k in KINDS if k != "assemblage")} | {
    frozenset(("transduction", "closure")), frozenset(("concrescence", "picturing"))}
PROTOTYPES: dict[str, dict[str, float]] = {
    "withdrawal": {"gate_boundary": 1, "veil": 1, "archive": 1, "connect": 0.3},
    "transduction": {"scale_threshold_down": 1, "split": 0.2},
    "concrescence": {"archive": 1, "deposit_memory": 1},
    "picturing": {"scale_threshold_up": 1, "revise": 0.3},
    "assemblage": {"connect": 1, "sever": 0.4, "gate_internal": 1},
    "closure": {"gate_boundary": 1, "veil": 1, "inject": 0.5, "scale_threshold_down": 0.3},
}
COUPLE_EVERY = 10
RECOUPLE_COOLDOWN = 40  # steps before the same kinds may couple again after decoupling
RECLASSIFY_EVERY = 20
DECOUPLE_AFTER = 8  # samples without ignition of a component kind


class SettingsError(ValueError):
    pass


def validate(s: dict) -> dict:
    """Full settings (defaults + overrides) or SettingsError naming the offending key."""
    unknown = set(s) - set(DEFAULTS)
    if unknown:
        raise SettingsError(f"unknown setting(s): {', '.join(sorted(unknown))}")
    out = copy.deepcopy(DEFAULTS)
    for k, v in s.items():
        if isinstance(DEFAULTS[k], dict) and k not in ("instruments", "ign", "rule"):
            if not isinstance(v, dict) or set(v) - set(DEFAULTS[k]):
                raise SettingsError(f"{k}: unknown key(s) {sorted(set(v) - set(DEFAULTS[k])) if isinstance(v, dict) else v}")
            out[k] = {**DEFAULTS[k], **v}
        else:
            out[k] = copy.deepcopy(v)
    if set(out["kinds"]) - set(KINDS) or set(out["order"]) - set(KINDS):
        raise SettingsError("kinds/order must name registry kinds")
    for sect in ("instruments", "ign", "rule"):
        if set(out[sect]) - set(KINDS):
            raise SettingsError(f"{sect}: unknown kind(s)")
    for k, d in out["ign"].items():
        if set(d) - set(DEFAULT_IGN[k]):
            raise SettingsError(f"ign.{k}: unknown parameter(s) {sorted(set(d) - set(DEFAULT_IGN[k]))}")
    for k, d in out["rule"].items():
        if set(d) - set(DEFAULT_RULE[k]):
            raise SettingsError(f"rule.{k}: unknown parameter(s) {sorted(set(d) - set(DEFAULT_RULE[k]))}")
    for k, d in out["instruments"].items():
        InstrumentSpec.from_dict({**DEFAULT_INSTRUMENT[k].to_dict(), **d})
    if not (out["warmup"] >= 0 and 10 <= out["horizon"] <= 20000):
        raise SettingsError("warmup ≥ 0 and 10 ≤ horizon ≤ 20000")
    if set(out["allocation"]) - set(KINDS) or any(not 0.25 <= float(v) <= 4.0 for v in out["allocation"].values()):
        raise SettingsError("allocation: kind → factor in [0.25, 4]")
    if set(out["variables"]) - set(DERIVED):
        raise SettingsError(f"variables ⊆ {DERIVED}")
    if out["placement"] not in ("shared", "separate"):
        raise SettingsError("placement must be shared or separate")
    for ev in out["schedule"]:
        if ev.get("type") not in ("remove_channel", "restore_channel", "relocate", "set_catalog"):
            raise SettingsError(f"schedule: unknown event type {ev.get('type')!r}")
    return out


# --------------------------------------------------------------------------------------------- placement
def macro_order(world: World) -> list[int]:
    lab = world.h.labels[0]
    size = np.bincount(lab)
    return [int(c) for c in np.argsort(-size, kind="stable")]


def children(world: World, level: int, nodes: np.ndarray) -> list[np.ndarray]:
    lab = world.h.labels[level][nodes]
    return [nodes[lab == c] for c in np.unique(lab)]


def place(world: World, kinds: list[str], placement: str, t: int, settings: dict, slot: int = 0) -> list[Operation]:
    """Deterministic regions from the public address hierarchy. ``slot`` shifts to other macro clusters (relocation)."""
    lab0 = world.h.labels[0]
    order = macro_order(world)
    m1 = np.flatnonzero(lab0 == order[(0 + 2 * slot) % len(order)]).astype(np.int32)
    m2 = np.flatnonzero(lab0 == order[(1 + 2 * slot) % len(order)]).astype(np.int32)
    ch1 = children(world, 1, m1)
    ch2 = children(world, 1, m2)
    pick = lambda xs, i: xs[i % len(xs)]  # noqa: E731
    ops = []
    for i, k in enumerate(kinds):
        if placement == "separate":
            mk = np.flatnonzero(lab0 == order[(i + 2 * slot) % len(order)]).astype(np.int32)
            cm = children(world, 1, mk)
            region = {"withdrawal": cm[0], "closure": cm[0], "concrescence": mk, "picturing": mk,
                      "assemblage": np.concatenate([cm[0], cm[-1]]) if len(cm) > 1 else mk}.get(k)
            milieu = mk if k == "transduction" else None
            if k == "transduction":
                region = children(world, 2, cm[0])[0]
        else:
            region = {"withdrawal": pick(ch1, 0), "closure": pick(ch1, 1), "concrescence": m1,
                      "picturing": np.concatenate([m1, m2]),
                      "assemblage": np.concatenate([pick(ch1, 3), pick(ch2, 0)])}.get(k)
            milieu = m1 if k == "transduction" else None
            if k == "transduction":
                region = children(world, 2, pick(ch1, 2))[0]
        assert region is not None
        inst = DEFAULT_INSTRUMENT[k].to_dict() | settings["instruments"].get(k, {})
        op = make(f"{k[:2].upper()}{slot or ''}", k, np.sort(region).astype(np.int32), t,
                  InstrumentSpec.from_dict(inst), milieu, settings["ign"].get(k), settings["rule"].get(k))
        if k == "picturing" and settings["picturing_requires_symbol_channel"]:
            op.mem["_needs_symbol"] = True
        ops.append(op)
    return ops


# --------------------------------------------------------------------------------------------- the field
class Field:
    def __init__(self, world: World, settings: dict, seed: int, keep_states: bool = True):
        self.world = world
        self.s = validate(settings)
        self.seed = seed
        self.ix = self.s["interaction"]
        catalog = tuple(self.s["catalog"]) + (("symbol",) if self.s["symbol_layer"] else ()) + tuple(self.s["variables"])
        self.instruments = Instruments(world, catalog)
        self.instruments.apply_veils = self.ix["observation_change"]
        self.history = CausalHistory(keep_states)
        self.ops: dict[str, Operation] = {}
        self.couplable = set(COUPLABLE)
        self.archive: list[dict] = []
        self.board: dict[tuple[int, str], tuple[int, np.ndarray]] = {}  # shared observations: (level, channel)
        self.pool = 0.0
        self.counter = 0
        self.t0 = world.t
        self.rng = np.random.default_rng([seed, 0x48504F])  # instrument noise (operation side)
        self.stats: dict[str, Any] = {
            "evaluations": {FIRED: 0, NOT_FIRED: 0, UNOBSERVABLE: 0}, "unobservable": {}, "unobservable_by_kind": {},
            "applied": {"gate_edges": 0, "threshold_nodes": 0, "connections": 0, "severed": 0, "injections": 0,
                        "memory_deposits": 0}, "requests": dict.fromkeys(REQUEST_TYPES, 0), "suppressed": 0,
            "filtered": 0, "shared_fills": 0, "correction_latency": [], "retransform_latency": [],
            "first_ignition": {}, "ignite_times": {}, "cease_times": {}, "reignite_times": {},
            "reignite_latency": [], "states_visited": set(), "series": {"active": [], "ceased": [], "ops": []},
            "param_drift": {}, "reinsertions": 0, "veil_steps": 0}
        self._pending: deque = deque()  # (due step, op id, requests, cause event) for act_delay
        self._step_acts: list[tuple[Operation, int, list[Request]]] = []
        for op in place(world, self.s["kinds"], self.s["placement"], world.t, self.s):
            self._add(op, [], "config")
        self._param_hist: deque = deque(maxlen=64)
        self.stopped_at: int | None = None

    # ------------------------------------------------------------------------- bookkeeping
    def _add(self, op: Operation, causes: list[int], source: str) -> Operation:
        alloc = self.s["allocation"]
        op.budget = float(np.mean([float(alloc.get(k, 1.0)) for k in op.kinds]))
        op.mem["_variables"] = list(self.s["variables"])
        if "picturing" in op.kinds and "activity_trend" in self.s["variables"]:
            op.instrument = op.instrument.with_(channels=tuple(sorted(set(op.instrument.channels) | {"activity_trend"})))
        op.mem.setdefault("_inbox", [])
        op.mem.setdefault("_fired_hist", deque(maxlen=4))
        op.mem.setdefault("_kind_last_fire", {k: self.world.t for k in op.kinds})
        op.mem.setdefault("_init", {"ign": copy.deepcopy(op.ign), "rule": copy.deepcopy(op.rule)})
        self.ops[op.oid] = op
        self.history.add(self.world.t, "config", source, op.oid, causes, None, op.snapshot(),
                         {"created": op.label, "lineage": op.lineage})
        return op

    def _new_id(self, base: str) -> str:
        self.counter += 1
        return f"{base}-{self.counter}"

    def live(self) -> list[Operation]:
        order = {k: i for i, k in enumerate(self.s["order"])}
        ops = [o for o in self.ops.values() if o.status != "subsumed"]
        return sorted(ops, key=lambda o: (min(order.get(k, 99) for k in o.kinds), o.oid))

    def _ev(self, type_: str, source: str, target: str, causes: list[int] | None = None, before=None, after=None,
            detail: dict | None = None) -> int:
        return self.history.add(self.world.t, type_, source, target, causes, before, after, detail)

    def _notify(self, op: Operation, eid: int) -> None:
        op.mem["_inbox"].append(eid)
        op.mem["_transformed_at"] = self.world.t

    # ------------------------------------------------------------------------- the step
    def step(self) -> None:
        w = self.world
        w.step()
        t = w.t
        self._schedule(t)
        per = self.s["resources"]["pool_per_step"]
        self.pool = min(4 * per, self.pool + per) if self.ix["share_resources"] else per
        self._step_acts = []
        live = self.live()
        for op in live:
            if op.status == "subsumed" or op.oid not in self.ops:
                continue
            if self._due(op, t):
                fair = per * max(1, op.instrument.period) / max(1, len(live))
                self._sample(op, t, fair)
        while self._pending and self._pending[0][0] <= t:
            _, oid, reqs, cause = self._pending.popleft()
            if oid in self.ops and self.ops[oid].status == "active":
                self._execute(self.ops[oid], reqs, cause)
        if self.ix["transform"]:
            self._apply_rules()
        self._competition()
        if self.ix["partition"] and (t - self.t0) % COUPLE_EVERY == 0:
            self._couple()
            self._decouple()
        if self.ix["reclassify"] and (t - self.t0) % RECLASSIFY_EVERY == 0:
            self._reclassify()
        h = self.s["history"]
        if h["reinsert"] and t - self.t0 >= h["lag"] and (t - self.t0) % h["every"] == 0:
            self._reinsert(t)
        self._expire_history_veils(t)
        self._record_series()
        if self.s["stop"]["all_ceased"] and all(o.status == "ceased" for o in self.live()):
            self.stopped_at = t

    def run(self, steps: int | None = None) -> None:
        for _ in range(steps if steps is not None else self.s["horizon"]):
            self.step()
            if self.stopped_at is not None:
                break

    def _due(self, op: Operation, t: int) -> bool:
        return (t - op.created_at) % max(1, op.instrument.period) == 0

    # ------------------------------------------------------------------------- sampling, ignition, status
    def _sample(self, op: Operation, t: int, fair: float) -> None:
        """Observe → evaluate → status change → act. Resources: a fixed fair share per sample (scaled by the operation's
        budget factor), or — with share_resources — up to twice that, drawn from one pool in evaluation order."""
        budget = min(self.pool, 2 * fair * op.budget) if self.ix["share_resources"] else fair * op.budget
        rng = self.rng if op.instrument.noise else None
        obs, cost = self.instruments.observe(op.instrument, op.needs(), op.region, budget, rng, viewer=op.oid)
        self.stats["measure_cost"] = self.stats.get("measure_cost", 0.0) + cost  # resources spent on measurement
        self.stats["measure_budget"] = self.stats.get("measure_budget", 0.0) + budget
        if self.ix["share_resources"]:
            self.pool -= cost
        op.mem["_budget_left"] = budget - cost
        if self.ix["share_info"]:
            self._fill_from_board(op, obs)
        for ch, v in obs.values.items():
            if ch != "boundary_flow":
                self.board[(obs.level, ch)] = (t, v)
        counts = obs.unobserved_counts()
        for reason, c in counts.items():
            self.stats["unobservable"][reason] = self.stats["unobservable"].get(reason, 0) + c
            per = self.stats["unobservable_by_kind"].setdefault(op.label, {})
            per[reason] = per.get(reason, 0) + c
        causes = list(op.mem["_inbox"]) + sorted(obs.veil_events)
        op.mem["_inbox"] = []
        igns = op.evaluate(obs)
        self._feedback(op, igns, causes)
        fired = []
        for g in igns:
            self.stats["evaluations"][g.outcome] += 1
            if g.outcome == FIRED:
                fired.append(g.kind)
                op.mem["_kind_last_fire"][g.kind] = t
                self.stats["first_ignition"].setdefault(g.kind, t - self.t0)
        op.mem["_last_ign"] = {g.kind: (g.outcome, g.reason, g.value) for g in igns}
        blind = all(g.outcome == UNOBSERVABLE for g in igns)
        votes = all(g.cease_vote or g.outcome == UNOBSERVABLE for g in igns)
        self.stats["states_visited"].add((op.label, op.status, blind))
        if fired:
            op.mem["_fired_hist"].append(t)
            op.mem["cease_streak"] = 0
            if op.status != "active":
                kind_ = "reignite" if op.status == "ceased" else "ignite"
                before = op.snapshot()
                op.status = "active"
                eid = self._ev(kind_, op.oid, op.oid, causes, before, op.snapshot(),
                               {"kinds": fired, "values": {g.kind: g.value for g in igns}})
                self.stats["ignite_times"].setdefault(op.oid, []).append(t)
                if kind_ == "reignite":
                    ceased = self.stats["cease_times"].get(op.oid, [t])[-1]
                    self.stats["reignite_times"].setdefault(op.oid, []).append(t)
                    self.stats["reignite_latency"].append(t - ceased)
                op.mem["_activation"] = eid
            if op.mem.get("_transformed_at") is not None:
                self.stats["retransform_latency"].append(t - op.mem.pop("_transformed_at"))
            reqs = op.act(obs, fired, self._visible_archive(op))
            for r in reqs:
                op.mem.setdefault("_fb_value", {})[r.kind] = op.mem["_last_ign"].get(r.kind, (None, None, None))[2]
            ae = self._ev("act", op.oid, "world", [op.mem.get("_activation", -1), *causes], None, None,
                          {"kinds": fired, "requests": [r.type for r in reqs]})
            if self.s["time"]["act_delay"]:
                self._pending.append((t + self.s["time"]["act_delay"], op.oid, reqs, ae))
            else:
                self._execute(op, reqs, ae)
        else:
            if blind and causes:  # recorded only when an earlier event (a veil, a transformation) made it blind
                self._ev("unobservable", op.oid, op.oid, causes, None, None, {"reasons": {g.kind: g.reason for g in igns}})
            if op.status == "active" and votes:
                op.mem["cease_streak"] = op.mem.get("cease_streak", 0) + 1
                limit = min(op.ign[k]["cease_after"] for k in op.kinds)
                if op.mem["cease_streak"] >= limit:
                    self._cease(op, causes, "blind" if blind else "condition")
            elif not votes:
                op.mem["cease_streak"] = 0

    def _cease(self, op: Operation, causes: list[int], why: str) -> None:
        before = op.snapshot()
        op.status = "ceased"
        op.mem["cease_streak"] = 0
        # structuring already done by transduction persists; every other standing effect is withdrawn
        keep = [k for k in op.kinds if k == "transduction"]
        self._set_standing(op, {k: v for k, v in op.mem.get("_standing", {}).items() if k in keep})
        self._drop_veils(op.oid)
        self.stats["cease_times"].setdefault(op.oid, []).append(self.world.t)
        self._ev("cease", op.oid, op.oid, causes, before, op.snapshot(), {"why": why})

    def _fill_from_board(self, op: Operation, obs: Observation) -> None:
        for ch, reasons in obs.reasons.items():
            if ch == "boundary_flow":
                continue
            entry = self.board.get((obs.level, ch))
            if entry is None or self.world.t - entry[0] > 4:
                continue
            fill = (reasons == "boundary_invisible") | (reasons == "instrument_mismatch") | (reasons == "unmeasured")
            src = entry[1]
            ok = fill & ~np.isnan(src)
            if ok.any():
                obs.values[ch] = obs.values[ch].copy()
                obs.values[ch][ok] = src[ok]
                obs.reasons[ch] = reasons.copy()
                obs.reasons[ch][ok] = ""
                self.stats["shared_fills"] += int(ok.sum())

    def _visible_archive(self, op: Operation) -> list[dict]:
        if not self.s["external_memory"]["enabled"]:
            return []
        if self.ix["share_history"]:
            return self.archive
        return [a for a in self.archive if a["owner"] == op.oid]

    def _feedback(self, op: Operation, igns: list, causes: list[int]) -> None:
        """Return of an operation's own result into its ignition condition: when its last act did not move the observed
        quantity in the direction its rule aims at, its ignition parameter rises by 3 % (habituation)."""
        if not self.s["feedback"] or not op.mem.get("_fb_value"):
            return
        aims = {"withdrawal": -1, "transduction": -1, "picturing": -1, "assemblage": 1, "closure": 1}
        prev_vals = op.mem.pop("_fb_value")
        now_vals = {g.kind: g.value for g in igns}
        for k, before in prev_vals.items():
            now = now_vals.get(k)
            if k not in aims or before is None or now is None:
                continue
            if (now - before) * aims[k] <= 0:
                param = PRIMARY[k]
                b = copy.deepcopy(op.ign)
                op.ign[k][param] = self._bounded(k, "ign", param, op.ign[k][param] * 1.03)
                if op.ign != b:
                    self._ev("feedback", op.oid, op.oid, causes, {"ign": b}, {"ign": copy.deepcopy(op.ign)},
                             {"kind": k, "before_value": before, "now": now})

    # ------------------------------------------------------------------------- requests → runtime records
    def _execute(self, op: Operation, reqs: list[Request], cause: int) -> None:
        inst = self.s["institution"]
        res = self.s["resources"]
        left = op.mem.get("_budget_left", 0.0) if not self.ix["share_resources"] else self.pool
        st = self.world.state
        standing: dict[str, list] = {k: list(v) for k, v in op.mem.get("_standing", {}).items()}
        touched_standing: set[str] = set()
        actions: list[Action] = []
        new_conn = 0
        for r in reqs:
            if r.type in inst["forbidden"]:
                self._ev("suppress", "field", op.oid, [cause], None, None, {"request": r.type, "why": "forbidden"})
                continue
            if len(r.nodes) > inst["max_nodes_per_act"]:
                r.nodes = r.nodes[:inst["max_nodes_per_act"]]
            if self.ix["action_filter"]:
                kept = self._filter(op, r, cause)
                if kept is None:
                    continue
                r = kept
            cost = res["act_cost_per_node"] * len(r.nodes) + (res["connection_cost"] * r.count if r.type == "connect" else 0)
            if cost > left + 1e-12:
                self.stats["suppressed"] += 1
                self._ev("suppress", "field", op.oid, [cause], None, None, {"request": r.type, "why": "resources",
                                                                          "cost": cost, "left": left})
                continue
            left -= cost
            if self.ix["share_resources"]:
                self.pool -= cost
            op.signature[r.type] = op.signature.get(r.type, 0) + 1
            self.stats["requests"][r.type] += 1
            if r.type in ("gate_boundary", "gate_internal"):
                edges = self._edges(r.nodes, internal=r.type == "gate_internal",
                                    direction=r.detail.get("direction", "both"), exempt=r.to_nodes)
                f = r.value if r.type == "gate_internal" else 1.0 - (1.0 - r.value) * self.s["boundary"]["gate_scale"]
                if r.standing:
                    if r.kind not in touched_standing:
                        standing[r.kind] = []
                        touched_standing.add(r.kind)
                    standing[r.kind].append(Gate(tuple(edges.tolist()), float(f)))
                self.stats["applied"]["gate_edges"] += len(edges)
            elif r.type in ("scale_threshold_down", "scale_threshold_up"):
                if r.kind not in touched_standing:
                    standing[r.kind] = []
                    touched_standing.add(r.kind)
                standing[r.kind].append(ScaleThreshold(tuple(r.nodes.tolist()), float(r.value)))
                self.stats["applied"]["threshold_nodes"] += len(r.nodes)
            elif r.type == "veil":
                self._drop_veils(op.oid, kind=r.kind)
                self.instruments.veils.append(Veil(op.oid, r.nodes.copy(),
                                                   float(r.value) * self.s["boundary"]["veil_scale"], cause, r.kind))
            elif r.type == "connect":
                pairs = self._pairs(r.nodes, r.to_nodes, r.count)
                pairs = pairs[:max(0, inst["max_new_connections_per_step"] - new_conn)]
                for a, b in pairs:
                    actions.append(Connect(int(a), int(b), float(r.value)))
                new_conn += len(pairs)
                self.stats["applied"]["connections"] += len(pairs)
                if r.detail.get("extends_region") and len(pairs):
                    op.region = np.union1d(op.region, np.array([b for _, b in pairs], np.int32)).astype(np.int32)
            elif r.type == "sever":
                e = self._edges(r.nodes, internal=True)
                if len(e):
                    e = e[np.argsort(-st.load[e], kind="stable")[:r.count]]
                    actions.append(Sever(tuple(int(x) for x in e)))
                    self.stats["applied"]["severed"] += len(e)
            elif r.type == "inject":
                actions.append(Inject(tuple(r.nodes.tolist()), float(r.value) * 0.25))
                self.stats["applied"]["injections"] += len(r.nodes)
            elif r.type == "deposit_memory":
                self.world.deposit_memory(r.nodes, float(r.value))
                self.stats["applied"]["memory_deposits"] += len(r.nodes)
            elif r.type == "archive":
                if self.s["external_memory"]["enabled"]:
                    self.archive.append({"t": self.world.t, "owner": op.oid, "kind": r.kind, "nodes": r.nodes.copy(),
                                         **r.detail, "event": cause})
                    if len(self.archive) > self.s["external_memory"]["capacity"]:
                        del self.archive[0]
            elif r.type == "revise":
                self._revise(op, r, cause)
            elif r.type == "split":
                self._split(op, cause, "domain size")
                return
        self.world.apply(actions)
        if touched_standing:
            self._set_standing(op, standing)
        self._step_acts.append((op, cause, reqs))
        self._read_archive(op)

    def _read_archive(self, op: Operation) -> None:
        """Operations that prehend archived data (picturing: prior; transduction: re-seed when its milieu is spent)."""
        arch = [a for a in self._visible_archive(op) if a.get("what") == "datum" and a["owner"] != op.oid]
        if not arch:
            return
        a = arch[-1]
        if "picturing" in op.kinds:
            m = op.mem.setdefault("picturing", {})
            pic = m.get("picture")
            lab = self.world.h.labels[a["level"]] if a.get("level") is not None else None
            own = np.unique(lab[op.region]) if lab is not None else np.zeros(0, np.int32)
            # only a picture over exactly the current categories and region can take the datum as its prior
            if pic is not None and a.get("level") == m.get("picture_level") and len(own) == len(pic):
                prior = pic.copy()
                for c, v in zip(a["clusters"], a["datum"], strict=False):
                    hit = np.flatnonzero(own == c)
                    if len(hit):
                        prior[hit[0]] = v
                m["prior"] = prior
        if "transduction" in op.kinds and op.milieu is not None and not np.setdiff1d(op.milieu, op.region).size:
            seed = a["nodes"]
            if len(seed):
                before = op.snapshot()
                op.milieu = np.union1d(op.milieu, seed).astype(np.int32)
                self._ev("reinsert", "field", op.oid, [a["event"]] if a.get("event", -1) >= 0 else [], before,
                         op.snapshot(), {"what": "archived datum re-seeds the milieu"})

    def _edges(self, nodes: np.ndarray, internal: bool, direction: str = "both",
               exempt: np.ndarray | None = None) -> np.ndarray:
        st = self.world.state
        inside = np.zeros(st.n, bool)
        inside[nodes] = True
        a = st.alive
        si, di = inside[st.src], inside[st.dst]
        if internal:
            m = a & si & di
        elif direction == "in":
            m = a & ~si & di
        else:
            m = a & (si != di)
        if exempt is not None and len(exempt):
            ex = np.zeros(st.n, bool)
            ex[exempt] = True
            m &= ~ex[st.src]
        return np.flatnonzero(m).astype(np.int32)

    def _pairs(self, a: np.ndarray, b: np.ndarray, count: int) -> list[tuple[int, int]]:
        st = self.world.state
        if not len(a) or not len(b) or count <= 0:
            return []
        ta = a[np.argsort(-st.ignite_count[a], kind="stable")][:count]
        tb = b[np.argsort(-st.ignite_count[b], kind="stable")][:count]
        return [(int(x), int(y)) for x, y in zip(ta, tb, strict=False) if x != y]

    def _set_standing(self, op: Operation, standing: dict[str, list]) -> None:
        op.mem["_standing"] = standing
        self.world.set_owner_overlay(op.oid, [it for k in sorted(standing) for it in standing[k]])

    def _drop_veils(self, owner: str, kind: str | None = None) -> None:
        self.instruments.veils = [v for v in self.instruments.veils
                                  if not (v.owner == owner and (kind is None or v.kind == kind))]

    # ------------------------------------------------------------------------- closure filter
    def _filter(self, op: Operation, r: Request, cause: int) -> Request | None:
        if r.type not in ("scale_threshold_down", "scale_threshold_up", "inject", "connect", "deposit_memory",
                          "gate_internal", "gate_boundary"):
            return r
        for sys_ in self.live():
            if sys_.oid == op.oid or sys_.status != "active" or "closure" not in sys_.kinds:
                continue
            inside = np.isin(r.nodes, sys_.region)
            tgt_inside = np.isin(r.to_nodes, sys_.region) if r.type == "connect" else np.zeros(0, bool)
            if not inside.any() and not tgt_inside.any():
                continue
            before = {"type": r.type, "nodes": int(len(r.nodes)), "value": r.value}
            cm = sys_.mem.setdefault("closure", {})
            if r.type == "connect":
                coupling = cm.get("coupling_nodes", np.zeros(0, np.int32))
                if tgt_inside.any() and not np.isin(r.nodes, coupling).any():
                    r.to_nodes = r.to_nodes[~tgt_inside]
                if inside.any():
                    r.nodes = r.nodes[~inside]
            elif r.type in ("inject", "deposit_memory"):
                r.value *= sys_.rule["closure"]["closure"]
            else:
                r.nodes = r.nodes[~inside]
            cm["irritation"] = cm.get("irritation", 0.0) + 1.0
            self.stats["filtered"] += 1
            eid = self._ev("filter", sys_.oid, op.oid, [cause], before,
                           {"type": r.type, "nodes": int(len(r.nodes)), "value": r.value},
                           {"system": sys_.oid, "irritation": cm["irritation"]})
            self._notify(sys_, eid)
            if (r.type == "connect" and (not len(r.nodes) or not len(r.to_nodes))) or (
                    r.type not in ("inject", "deposit_memory", "connect") and not len(r.nodes)):
                return None
        return r

    # ------------------------------------------------------------------------- interaction rules
    def _relation(self, a: Operation, b: Operation, rel: str) -> bool:
        if rel == "overlap":
            return bool(np.intersect1d(a.region, b.region, assume_unique=False).size)
        lab = self.world.h.labels[0]
        return bool(np.intersect1d(np.unique(lab[a.region]), np.unique(lab[b.region])).size)

    def _bounded(self, kind: str, sect: str, param: str, value: float) -> float:
        base = (DEFAULT_IGN if sect == "ign" else DEFAULT_RULE)[kind][param]
        lo, hi = sorted((base * BOUND[0], base * BOUND[1]))
        return float(min(max(value, lo), hi))

    def _apply_rules(self) -> None:
        for src, cause, reqs in self._step_acts:
            triggers = {"act"} | ({"deposit"} if any(r.type == "deposit_memory" for r in reqs) else set())
            for sk, trig, rel, tk, eff in RULES:
                if sk not in src.kinds or trig not in triggers:
                    continue
                for tgt in self.live():
                    if tgt.oid == src.oid or tgt.status == "subsumed" or (tk != "*" and tk not in tgt.kinds):
                        continue
                    if not self._relation(src, tgt, rel):
                        continue
                    self._transform(src, tgt, tk, eff, cause, f"{sk}:{trig}:{rel}")

    def _transform(self, src: Operation, tgt: Operation, tk: str, eff: tuple, cause: int, rule: str) -> None:
        before = tgt.snapshot()
        kinds = tgt.kinds if tk == "*" else (tk,)
        for k in kinds:
            if eff[0] == "primary":
                p = PRIMARY[k]
                tgt.ign[k][p] = self._bounded(k, "ign", p, tgt.ign[k][p] * eff[1])
            elif eff[0] == "ign" and eff[1] in tgt.ign.get(k, {}):
                tgt.ign[k][eff[1]] = self._bounded(k, "ign", eff[1], tgt.ign[k][eff[1]] * eff[2])
            elif eff[0] == "rule" and eff[1] in tgt.rule.get(k, {}):
                v = tgt.rule[k][eff[1]]
                if isinstance(eff[2], str) and eff[2].startswith("toward1:"):
                    v = v + float(eff[2].split(":")[1]) * (1.0 - v)
                else:
                    v = v * eff[2]
                tgt.rule[k][eff[1]] = self._bounded(k, "rule", eff[1], v)
            elif eff[0] == "budget":
                tgt.budget = float(min(max(tgt.budget * eff[1], 0.25), 4.0))
        after = tgt.snapshot()
        if after != before:
            eid = self._ev("transform", src.oid, tgt.oid, [cause], before, after, {"rule": rule, "effect": list(eff)})
            self._notify(tgt, eid)

    def _revise(self, op: Operation, r: Request, cause: int) -> None:
        before = op.snapshot()
        lvl = int(r.detail["level"])
        op.instrument = op.instrument.with_(level=lvl)
        self.stats["correction_latency"].append(self.world.t - int(r.detail.get("error_onset", self.world.t)))
        eid = self._ev("revise", op.oid, op.oid, [cause], before, op.snapshot(), {"level": lvl})
        if self.ix["observation_change"]:
            # shared observation conditions: overlapping instruments are refined too — as far as a resolution at which
            # every channel they carry still exists (an instrument cannot follow a revision past its own channels)
            for tgt in self.live():
                cap = MAX_FLOW_LEVEL if "boundary_flow" in tgt.instrument.channels else lvl
                new = min(lvl, max(cap, tgt.instrument.level))
                if tgt.oid != op.oid and self._relation(op, tgt, "overlap") and tgt.instrument.level < new:
                    b = tgt.snapshot()
                    tgt.instrument = tgt.instrument.with_(level=new)
                    e2 = self._ev("transform", op.oid, tgt.oid, [eid], b, tgt.snapshot(),
                                  {"rule": "picturing:revise:overlap", "effect": ["instrument_level", new]})
                    self._notify(tgt, e2)

    # ------------------------------------------------------------------------- competition
    def _competition(self) -> None:
        """Opposite standing threshold factors on the same configurations: a conflict. With competition_adapt, the
        operation with the lower salience (ignition value ÷ its threshold) is attenuated (its factor moves 20 % towards
        1) and the other amplified (5 % away from 1)."""
        st = self.world.state
        down = np.zeros(st.n, bool)
        up = np.zeros(st.n, bool)
        owners_down: list[tuple[Operation, str, np.ndarray]] = []
        owners_up: list[tuple[Operation, str, np.ndarray]] = []
        for op in self.live():
            for k, items in op.mem.get("_standing", {}).items():
                for it in items:
                    if isinstance(it, ScaleThreshold) and it.nodes:
                        idx = np.asarray(it.nodes)
                        (down if it.factor < 1 else up)[idx] = True
                        (owners_down if it.factor < 1 else owners_up).append((op, k, idx))
        both = down & up
        if not both.any():
            return
        for od, kd, idd in owners_down:
            for ou, ku, idu in owners_up:
                if od.oid == ou.oid or not both[np.intersect1d(idd, idu)].any():
                    continue
                key = (od.oid, ou.oid)
                last = self.stats.setdefault("_conflict_last", {})
                if self.world.t - last.get(key, -10**9) < 10:
                    continue
                last[key] = self.world.t
                sal = {o.oid: self._salience(o, k) for o, k in ((od, kd), (ou, ku))}
                ce = self._ev("conflict", "field", f"{od.oid}|{ou.oid}", [], None, None,
                              {"down": od.oid, "up": ou.oid, "salience": sal,
                               "configurations": int(both[np.intersect1d(idd, idu)].sum())})
                if not self.ix["competition_adapt"]:
                    continue
                loser, lk, winner, wk = (od, kd, ou, ku) if sal[od.oid] < sal[ou.oid] else (ou, ku, od, kd)
                for o, k, attenuate in ((loser, lk, True), (winner, wk, False)):
                    param = {"transduction": "factor", "picturing": "damp", "closure": "adapt"}.get(k)
                    if param is None or param not in o.rule.get(k, {}):
                        continue
                    b = o.snapshot()
                    v = o.rule[k][param]
                    v = v + 0.2 * (1.0 - v) if attenuate else v + 0.05 * (v - 1.0)
                    o.rule[k][param] = self._bounded(k, "rule", param, v)
                    if o.snapshot() != b:
                        e = self._ev("transform", winner.oid if o is loser else loser.oid, o.oid, [ce], b, o.snapshot(),
                                     {"rule": "competition", "effect": ["attenuate" if attenuate else "amplify", param]})
                        self._notify(o, e)

    def _salience(self, op: Operation, kind: str) -> float:
        last = op.mem.get("_last_ign", {}).get(kind)
        v = last[2] if last and last[2] is not None else 0.0
        return float(v) / max(1e-9, op.ign[kind][PRIMARY[kind]])

    # ------------------------------------------------------------------------- partition: couple / split / adopt
    def _couple(self) -> None:
        live = [o for o in self.live() if o.status == "active"]
        t = self.world.t
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                if a.oid not in self.ops or b.oid not in self.ops or "subsumed" in (a.status, b.status):
                    continue
                if len(self.live()) >= self.s["institution"]["max_ops"]:
                    return
                ka, kb = set(a.kinds), set(b.kinds)
                if ka & kb or len(ka | kb) > 3:
                    continue
                if not any(frozenset((x, y)) in self.couplable for x in ka for y in kb):
                    continue
                co = sum(1 for x in a.mem["_fired_hist"] if t - x <= 8) >= 2 and \
                    sum(1 for x in b.mem["_fired_hist"] if t - x <= 8) >= 2
                if not co or not self._relation(a, b, "overlap"):
                    continue
                key = "∘".join(sorted(ka | kb))
                if t - self.stats.setdefault("_decoupled", {}).get(key, -10**9) < RECOUPLE_COOLDOWN:
                    continue
                self._make_composite(a, b)

    def _make_composite(self, a: Operation, b: Operation) -> Operation:
        kinds = tuple(k for k in self.s["order"] if k in set(a.kinds) | set(b.kinds))
        ia, ib = a.instrument, b.instrument
        inst = InstrumentSpec(tuple(sorted(set(ia.channels) | set(ib.channels))), max(ia.level, ib.level),
                              min(ia.window, ib.window), min(ia.period, ib.period), max(ia.noise, ib.noise),
                              max(ia.penetration, ib.penetration))
        mem = {**{k: v for k, v in b.mem.items() if not k.startswith("_")},
               **{k: v for k, v in a.mem.items() if not k.startswith("_")}}
        z = Operation(self._new_id("∘".join(x[:2].upper() for x in kinds)), kinds,
                      np.union1d(a.region, b.region).astype(np.int32), inst, {**b.ign, **a.ign}, {**b.rule, **a.rule},
                      lineage=[a.oid, b.oid], mem=mem, milieu=a.milieu if a.milieu is not None else b.milieu,
                      created_at=self.world.t)
        before = [a.snapshot(), b.snapshot()]
        for o in (a, b):
            o.status = "subsumed"
            self._drop_veils(o.oid)
        standing = {**b.mem.get("_standing", {}), **a.mem.get("_standing", {})}
        for o in (a, b):
            self.world.set_owner_overlay(o.oid, [])
        z.status = "active"
        self._add(z, [], "field")
        z.budget = min(4.0, a.budget + b.budget)
        z.mem["_fired_hist"] = deque(sorted(set(a.mem["_fired_hist"]) | set(b.mem["_fired_hist"]))[-4:], maxlen=4)
        z.mem["_init"] = {"ign": copy.deepcopy(z.ign), "rule": copy.deepcopy(z.rule)}
        self._set_standing(z, standing)
        causes = [e for e in (a.mem.get("_last_act"), b.mem.get("_last_act")) if e is not None]
        self._ev("couple", "field", z.oid, causes, before, z.snapshot(), {"kinds": list(kinds), "new_kind": z.label})
        return z

    def _decouple(self) -> None:
        t = self.world.t
        for z in [o for o in self.live() if len(o.kinds) > 1 and o.status == "active"]:
            stale = [k for k in z.kinds if t - z.mem["_kind_last_fire"].get(k, z.created_at) >
                     DECOUPLE_AFTER * max(1, z.instrument.period)]
            if not stale or len(stale) == len(z.kinds):
                continue
            self._split_kinds(z, stale)

    def _split_kinds(self, z: Operation, stale: list[str]) -> None:
        groups = [tuple(k for k in z.kinds if k not in stale), tuple(stale)]
        self.stats.setdefault("_decoupled", {})["∘".join(sorted(z.kinds))] = self.world.t
        before = z.snapshot()
        z.status = "subsumed"
        self.world.set_owner_overlay(z.oid, [])
        self._drop_veils(z.oid)
        new = []
        for g in groups:  # each part keeps the composite's region, instrument and drifted parameters
            o = Operation(self._new_id("".join(x[:2].upper() for x in g)), g, z.region.copy(), z.instrument,
                          {k: dict(z.ign[k]) for k in g}, {k: dict(z.rule[k]) for k in g}, status="active",
                          lineage=[z.oid], mem={k: z.mem.get(k, {}) for k in g}, milieu=z.milieu,
                          created_at=self.world.t)
            self._add(o, [], "field")
            o.mem["_init"] = {"ign": {k: z.mem["_init"]["ign"].get(k, dict(DEFAULT_IGN[k])) for k in g},
                              "rule": {k: z.mem["_init"]["rule"].get(k, dict(DEFAULT_RULE[k])) for k in g}}
            self._set_standing(o, {k: v for k, v in z.mem.get("_standing", {}).items() if k in g})
            new.append(o)
        self._ev("split", "field", z.oid, [], before, [o.snapshot() for o in new],
                 {"why": "co-activation stopped", "parts": [o.label for o in new]})

    def _split(self, op: Operation, cause: int, why: str) -> None:
        if len(self.live()) + 1 > self.s["institution"]["max_ops"]:
            self._ev("suppress", "field", op.oid, [cause], None, None, {"request": "split", "why": "max_ops"})
            return
        lab = self.world.h.labels[2]
        order = np.argsort(lab[op.region], kind="stable")
        halves = [op.region[order[: len(order) // 2]], op.region[order[len(order) // 2:]]]
        before = op.snapshot()
        op.status = "subsumed"
        self.world.set_owner_overlay(op.oid, [])
        self._drop_veils(op.oid)
        parts = []
        for i, reg in enumerate(halves):
            o = Operation(self._new_id(op.oid.split("-")[0]), op.kinds, np.sort(reg).astype(np.int32), op.instrument,
                          copy.deepcopy(op.ign), copy.deepcopy(op.rule), status="active", lineage=[op.oid],
                          mem={k: copy.deepcopy(v) for k, v in op.mem.items() if not k.startswith("_")},
                          milieu=op.milieu, created_at=self.world.t)
            if "transduction" in o.kinds:
                o.rule["transduction"]["factor"] = self._bounded("transduction", "rule", "factor",
                                                                 o.rule["transduction"]["factor"] * (0.97 if i == 0 else 1.03))
            self._add(o, [cause], "field")
            o.mem["_init"] = copy.deepcopy(op.mem.get("_init"))
            self._set_standing(o, {"transduction": [ScaleThreshold(tuple(o.region.tolist()),
                                                                   o.rule["transduction"]["factor"])]}
                               if "transduction" in o.kinds else {})
            parts.append(o)
        self._ev("split", "field", op.oid, [cause], before, [o.snapshot() for o in parts], {"why": why})

    # ------------------------------------------------------------------------- reclassification
    def _reclassify(self) -> None:
        keys = list(REQUEST_TYPES)
        protos = {k: np.array([PROTOTYPES[k].get(x, 0.0) for x in keys]) for k in KINDS}
        for op in self.live():
            if len(op.kinds) != 1 or op.status != "active":
                continue
            sig = np.array([op.signature.get(x, 0) for x in keys], float)
            if sig.sum() < 10:
                continue
            sig = sig / np.linalg.norm(sig)
            cos = {k: float(sig @ (p / np.linalg.norm(p))) for k, p in protos.items()}
            own = op.kinds[0]
            best = max(cos, key=lambda k: cos[k])
            if best != own and cos[best] > cos[own] + 0.1:
                op.mem["_reclass_votes"] = op.mem.get("_reclass_votes", 0) + 1
                if op.mem["_reclass_votes"] >= 2:
                    before = op.snapshot()
                    op.kinds = (best,)
                    op.ign = {best: {**DEFAULT_IGN[best], **self.s["ign"].get(best, {})}}
                    op.rule = {best: {**DEFAULT_RULE[best], **self.s["rule"].get(best, {})}}
                    op.mem["_reclass_votes"] = 0
                    self._ev("reclassify", "field", op.oid, [], before, op.snapshot(),
                             {"from": own, "to": best, "similarity": cos})
            else:
                op.mem["_reclass_votes"] = 0

    # ------------------------------------------------------------------------- history reinsertion
    def _reinsert(self, t: int) -> None:
        h = self.s["history"]
        old = [a for a in self.archive if t - a["t"] >= h["lag"]]
        if h["data"]:
            for a in old[-3:]:
                if a.get("what") == "datum" and len(a["nodes"]):
                    self.world.deposit_memory(a["nodes"], 0.3)
                    self.stats["reinsertions"] += 1
                    eid = self._ev("reinsert", "field", "world", [a["event"]] if a.get("event", -1) >= 0 else [],
                                   None, None, {"what": "archived datum", "from_t": a["t"], "nodes": int(len(a["nodes"]))})
                    for op in self.live():
                        if np.intersect1d(op.region, a["nodes"]).size:
                            self._notify(op, eid)
        if h["veils"]:
            for a in old[-2:]:
                if a.get("what") == "veil" and len(a["nodes"]):
                    eid = self._ev("reinsert", "field", "world", [a["event"]] if a.get("event", -1) >= 0 else [], None,
                                   None, {"what": "archived veil", "from_t": a["t"]})
                    self.instruments.veils.append(Veil("history", a["nodes"].copy(), float(a["opacity"]), eid,
                                                       "history", until=t + 10))
                    self.stats["reinsertions"] += 1
        if h["params"]:
            past = [p for p in self._param_hist if t - p[0] >= h["lag"]]
            if past:
                snap = past[-1][1]
                for op in self.live():
                    if op.oid in snap and snap[op.oid] != op.ign and set(snap[op.oid]) == set(op.ign):
                        before = op.snapshot()
                        op.ign = copy.deepcopy(snap[op.oid])
                        self.stats["reinsertions"] += 1
                        eid = self._ev("reinsert", "field", op.oid, [], before, op.snapshot(),
                                       {"what": "ignition parameters of an earlier configuration", "from_t": past[-1][0]})
                        self._notify(op, eid)

    def _expire_history_veils(self, t: int) -> None:
        if any(v.until is not None for v in self.instruments.veils):
            self.instruments.veils = [v for v in self.instruments.veils if v.until is None or v.until > t]

    # ------------------------------------------------------------------------- scheduled configuration changes
    def _schedule(self, t: int) -> None:
        for ev in self.s["schedule"]:
            if ev["at"] + self.t0 != t:
                continue
            targets = [o for o in self.live() if ev.get("kind") in o.kinds or ev.get("oid") == o.oid]
            for op in targets:
                before = op.snapshot()
                if ev["type"] == "remove_channel":
                    op.instrument = op.instrument.with_(channels=tuple(c for c in op.instrument.channels
                                                                       if c != ev["channel"]))
                elif ev["type"] == "restore_channel":
                    chans = tuple(sorted(set(op.instrument.channels) | {ev["channel"]}))
                    op.instrument = op.instrument.with_(channels=chans, **ev.get("instrument", {}))
                elif ev["type"] == "relocate":
                    moved = place(self.world, [k for k in op.kinds], self.s["placement"], t, self.s,
                                  slot=int(ev.get("slot", 1)))[0]
                    op.region, op.milieu = moved.region, moved.milieu
                    self._set_standing(op, {})
                    self._drop_veils(op.oid)
                eid = self._ev("config", "config", op.oid, [], before, op.snapshot(), dict(ev))
                self._notify(op, eid)
            if ev["type"] == "set_catalog":
                self.instruments.catalog = tuple(ev["catalog"])
                self._ev("config", "config", "field", [], None, None, dict(ev))

    # ------------------------------------------------------------------------- records
    def _record_series(self) -> None:
        live = self.live()
        ser = self.stats["series"]
        ser["active"].append(sum(o.status == "active" for o in live))
        ser["ceased"].append(sum(o.status == "ceased" for o in live))
        ser["ops"].append(len(live))
        self.stats["veil_steps"] += len(self.instruments.veils)
        self._param_hist.append((self.world.t, {o.oid: copy.deepcopy(o.ign) for o in live}))
        for op, cause, _ in self._step_acts:
            op.mem["_last_act"] = cause

    def drift(self) -> dict[str, float]:
        """Relative L1 change of each live operation's ignition + rule parameters from their initial values."""
        out = {}
        for op in self.live():
            init = op.mem.get("_init")
            if not init:
                continue
            tot, n = 0.0, 0
            for sect in ("ign", "rule"):
                for k, d in getattr(op, sect).items():
                    for p, v in d.items():
                        v0 = init[sect].get(k, {}).get(p)
                        if v0:
                            tot += abs(v - v0) / abs(v0)
                            n += 1
            out[op.oid] = tot / max(1, n)
        return out
