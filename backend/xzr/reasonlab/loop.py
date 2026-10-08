"""World ↔ reason closed loop.

    world transition → probes → (if enabled) grounded revisions of the reasoning state → compile →
    operational interventions (threshold / permeability / memory / eligibility / mutation) → world transition …

The reasoning layer never writes world state: every effect passes through ``compile_config`` into overlay records
that the engine applies (``InterventionGate`` checks the record types). When the enabling conditions fail, the
reasoning layer collapses according to a configurable policy.

Representations: any of ``representations.REPRESENTATIONS``, plus
  ``memoryless`` — each check rebuilds the reasoning state from the initial specification and applies only the
                   groundings whose condition holds *now* (no persistent revision state),
  ``none``       — no reasoning layer (world interventions only),
  ``replay``     — no reasoning layer; a recorded overlay schedule is applied open-loop at the recorded steps.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import Any

from ..practice.compile import InterventionConfig, compile_config
from ..practice.graph import Practice
from ..runtime.intervention import Freeze, Gate, MemoryCondition, Mutation, ScaleThreshold, is_overlay, to_dict
from ..scenario.build import World
from .conditions import WorldProbe, holds
from .representations import Edit, apply_edit, build, effective


class _Empty:
    def active_bindings(self) -> list:
        return []


class InterventionGate:
    """The only path from the reasoning layer to the world: validates records before the engine applies them."""

    ALLOWED = (ScaleThreshold, Gate, MemoryCondition, Freeze, Mutation)

    def __init__(self, engine):
        self.engine = engine
        self.applied = 0

    def set_overlay(self, items: list) -> None:
        for it in items:
            if not (is_overlay(it) and isinstance(it, self.ALLOWED)):
                raise TypeError(f"reasoning may only emit operational interventions, got {it!r}")
        self.engine.set_overlay(items)
        self.applied += 1


@dataclass
class LoopConfig:
    representation: str = "scorekeeping"
    check_every: int = 10
    enabling: list[dict] = field(default_factory=list)
    enable_streak: int = 2
    groundings: list[dict] = field(default_factory=list)
    collapse: str = "decay"  # decay | drop | freeze
    decay_factor: float = 0.6
    reasoning_from: int = 0
    world_events: list[dict] = field(default_factory=list)  # {"t", "items": [{"kind", "target", ...}]}
    edits: list[tuple[int, Edit]] = field(default_factory=list)
    replay: list[tuple[int, list]] = field(default_factory=list)
    track_distinctions: bool = True
    # degradations of the reasoning interface itself (enabling-condition experiments)
    interface_churn: dict | None = None  # {"from": t, "every": checks, "seed": s}: random dependency edits
    record_decay: dict | None = None  # {"from": t, "factor": f}: records fade every check, even while active
    triggers: Any = None  # reasonlab.triggers.TriggerSet: world-responsive revisions (optional)
    light: bool = False  # compact timeline (long runs): no per-check effective levels


def hash_effects(effects: tuple) -> str:
    return hashlib.sha1("|".join(effects).encode()).hexdigest()[:12]


def _overlay_key(items: list) -> str:
    return hashlib.sha1(json.dumps([to_dict(i) for i in items], sort_keys=True).encode()).hexdigest()[:12]


class ReasonLoop:
    def __init__(self, world: World, practice_json: dict, cfg: LoopConfig, rep: Any = None):
        self.world = world
        self.cfg = cfg
        self.base_json = copy.deepcopy(practice_json)
        kind = cfg.representation
        if rep is not None:  # a prebuilt representation (structures.build_variant); kind is then only a label
            self.rep: Any = rep
        else:
            self.rep = build(kind, practice_json) if kind not in ("memoryless", "none", "replay") else None
        if kind == "memoryless":
            self.rep = build("scorekeeping", practice_json)
        self.gate = InterventionGate(world.engine)
        self.probe = WorldProbe(world)
        self.enabled = False
        self.ever_enabled = False
        self._streak = 0
        self._g_streak = [0] * len(cfg.groundings)
        self.world_items: list = []
        self.overlay: list = []
        self.key = ""
        self.timeline: list[dict] = []
        self.overlay_changes: list[tuple[int, list]] = []
        self.revisions = 0
        self._frozen_overlay: list | None = None
        self._frozen_effects: tuple = ()
        self.effects: tuple = ()
        self.effect_changes: list[tuple[int, tuple]] = []
        self._calib: dict[int, list[float]] = {}
        self._churn_rng = random.Random(cfg.interface_churn["seed"]) if cfg.interface_churn else None
        self._apply(initial=True)
        if cfg.representation == "replay":
            for at, items in cfg.replay:
                if at == world.state.t:
                    self._replay_apply(items)

    # ------------------------------------------------------------------ helpers
    def _world_item(self, spec: dict):
        if spec["kind"] == "gate":
            return Gate(tuple(self.world.resolve(spec["target"], "edges").tolist()), float(spec["factor"]))
        nodes = tuple(self.world.resolve(spec["target"], "nodes").tolist())
        if spec["kind"] == "memory_condition":
            return MemoryCondition(nodes, spec.get("decay"), spec.get("coupling"))
        if spec["kind"] == "mutation":
            return Mutation(nodes, float(spec["rate"]))
        if spec["kind"] == "freeze":
            return Freeze(nodes)
        if spec["kind"] == "scale_threshold":
            return ScaleThreshold(nodes, float(spec["factor"]))
        raise ValueError(spec["kind"])

    def _compiled(self, rep) -> list:
        return self._compile(rep)[0]

    def _compile(self, rep) -> tuple[list, tuple]:
        """Compiled operational interventions, and their semantic key: the set of (operation, target set, factor)
        in force — independent of which connection indices a target set resolves to at this moment."""
        boundaries = {k: b.permeability for k, b in self.world.scenario.boundaries.items()}
        cfg = InterventionConfig(rep if rep is not None else _Empty(), boundaries)
        cache: dict[tuple[str, str], Any] = {}

        def resolve(target: str, want: str = "nodes"):
            k = (target, want)
            if k not in cache:
                cache[k] = self.world.resolve(target, want)
            return cache[k]

        items, _, prov, _ = compile_config(cfg, resolve)
        effects = tuple(sorted(p["effect"] for p in prov if p.get("targets") and "inactive" not in p["effect"]))
        return items, effects

    def _apply(self, initial: bool = False) -> None:
        kind = self.cfg.representation
        active = self.enabled and self.world.state.t >= self.cfg.reasoning_from
        if kind in ("none", "replay"):
            rep = None
        elif active:
            rep = self.rep
        elif self.cfg.collapse == "freeze" and self._frozen_overlay is not None:
            rep = "frozen"
        else:
            rep = None
        if rep == "frozen":
            reasoning_items, effects = list(self._frozen_overlay or []), self._frozen_effects
        else:
            reasoning_items, effects = self._compile(rep)
        if active:
            self._frozen_overlay, self._frozen_effects = reasoning_items, effects
        new_effects = (*tuple(effects), *sorted(f"world {type(i).__name__}" for i in self.world_items))
        if new_effects != self.effects or initial:
            self.effect_changes.append((self.world.state.t, new_effects))
        self.effects = new_effects
        items = [*reasoning_items, *self.world_items]
        key = _overlay_key(items)
        if key != self.key or initial:
            self.gate.set_overlay(items)
            self.key = key
            self.overlay = items
            if not self.cfg.light:
                self.overlay_changes.append((self.world.state.t, list(items)))
            else:
                self.world.engine.log.clear()  # long runs: the rewind log is not needed

    def _replay_apply(self, items: list) -> None:
        self.gate.set_overlay(items)
        self.overlay = list(items)
        self.key = _overlay_key(items)
        self.overlay_changes.append((self.world.state.t, list(items)))

    # ------------------------------------------------------------------ step
    def step(self):
        t_next = self.world.state.t
        for ev in self.cfg.world_events:
            if ev["t"] == t_next:
                self.world_items = [*self.world_items, *[self._world_item(x) for x in ev["items"]]]
                self._apply()
        for at, e in self.cfg.edits:
            if at == t_next and self.rep is not None:
                if e.op in ("lose_records", "restore_records") and self._persistent():
                    continue
                if self.cfg.representation == "memoryless":
                    p = build("scorekeeping", self.base_json)
                    apply_edit(p, e)
                    self.base_json = p.to_json()
                    self.rep = build("scorekeeping", self.base_json)
                else:
                    apply_edit(self.rep, e)
                self._apply()
        d = self.world.engine.step()
        if self.cfg.representation == "replay":  # same timing as the recorded loop: end of the step
            for at, items in self.cfg.replay:
                if at == self.world.state.t:
                    self._replay_apply(items)
        self.probe.update(d)
        if self.world.state.t % self.cfg.check_every == 0:
            self._check()
        return d

    def run(self, steps: int) -> None:
        for _ in range(steps):
            self.step()

    def _persistent(self) -> bool:
        return bool(getattr(self.rep, "persistent", False))

    def _holds(self, k: int, c: dict, calibrating: bool) -> tuple[bool, float]:
        """Enabling condition; with ``rel`` the threshold is rel × the metric's mean over the calibration checks
        (the checks before reasoning is allowed)."""
        if "rel" not in c:
            return holds(self.probe, c)
        v = self.probe.value(c["metric"], c.get("target", ""), c.get("source", ""))
        if calibrating:
            self._calib.setdefault(k, []).append(v)
            return True, v
        base = float(sum(self._calib.get(k, [v])) / max(len(self._calib.get(k, [v])), 1))
        return holds(self.probe, {**c, "value": c["rel"] * base})

    def _check(self) -> None:
        t = self.world.state.t
        self.probe.begin_check()
        calibrating = t < self.cfg.reasoning_from
        conds = [self._holds(k, c, calibrating) for k, c in enumerate(self.cfg.enabling)]
        ok = all(c[0] for c in conds)
        allowed = t >= self.cfg.reasoning_from
        if ok != self.enabled:
            self._streak += 1
            if self._streak >= self.cfg.enable_streak:
                self.enabled = ok
                self._streak = 0
        else:
            self._streak = 0
        self.ever_enabled |= self.enabled and allowed
        if (not self.enabled and self.ever_enabled and self.rep is not None and self.cfg.collapse == "decay"
                and self.cfg.representation != "memoryless" and not self._persistent()):
            self._decay()
        trig = self.cfg.triggers
        if trig is not None and self.rep is not None:
            trig.observe(self, calibrating)
            if self.enabled and allowed:
                before_eff = effective(self.rep)
                for e in trig.fire(self):
                    apply_edit(self.rep, e)
                if effective(self.rep) != before_eff:
                    self.revisions += 1
        gvals = []
        if self.enabled and allowed and self.rep is not None:
            if self.cfg.representation == "memoryless":
                self.rep = build("scorekeeping", self.base_json)
                for g in self.cfg.groundings:
                    h, v = holds(self.probe, g["when"])
                    gvals.append(v)
                    if h:
                        self._ground(g)
            else:
                for k, g in enumerate(self.cfg.groundings):
                    h, v = holds(self.probe, g["when"])
                    gvals.append(v)
                    self._g_streak[k] = self._g_streak[k] + 1 if h else 0
                    if self._g_streak[k] >= g.get("window", 1):
                        self._ground(g)
        self._interface_degradation(t)
        before = self.key
        if self.cfg.representation != "replay":
            self._apply()
        phase = ("no_reasoning_layer" if self.cfg.representation in ("none", "replay") else
                 "pre" if not allowed else "reasoning" if self.enabled else
                 "collapsed" if self.ever_enabled else "not_enabled")
        if self.cfg.light:
            lv = "" if self.rep is None else hash_effects(tuple(f"{k}={v}" for k, v in sorted(effective(self.rep).items())))
            self.timeline.append({"t": t, "phase": phase, "effects": hash_effects(self.effects), "levels": lv,
                                  "revisions": self.revisions, "conditions": [round(c[1], 5) for c in conds]})
            return
        rec = {"t": t, "phase": phase, "enabled": self.enabled, "conditions": [round(c[1], 5) for c in conds],
               "groundings": [round(v, 5) for v in gvals], "overlay_items": len(self.overlay),
               "overlay_changed": self.key != before, "revisions": self.revisions, "effects": list(self.effects)}
        if self.rep is not None:
            rec["effective"] = effective(self.rep)
            if self.cfg.track_distinctions and isinstance(self.rep, Practice):
                d = self._distinctions()
                # operative only while reasoning is active; otherwise the distinction is latent
                rec["commitment_distinction"] = d["commitment_distinction"] and phase == "reasoning"
                rec["entitlement_distinction"] = d["entitlement_distinction"] and phase == "reasoning"
                rec["commitment_distinction_latent"] = d["commitment_distinction"]
                rec["entitlement_distinction_latent"] = d["entitlement_distinction"]
        self.timeline.append(rec)

    def _interface_degradation(self, t: int) -> None:
        if self.rep is None or self._persistent():
            return
        rd = self.cfg.record_decay
        if rd and t >= rd["from"] and self.enabled:
            self._decay_by(rd["factor"])
        ch = self.cfg.interface_churn
        if ch and t >= ch["from"] and (t // self.cfg.check_every) % ch["every"] == 0:
            rng = self._churn_rng
            assert rng is not None
            ids = sorted(effective(self.rep))
            target, source = rng.choice(ids), rng.choice(ids)
            if target != source:
                op = rng.choice(["drop_requirement", "add_requirement"])
                apply_edit(self.rep, Edit(op, a=target, b=source, sources=(source,)))

    def _decay_by(self, f: float) -> None:
        if self.rep is None:
            return
        if isinstance(self.rep, Practice):
            for cid in list(self.rep.asserted):
                self.rep.asserted[cid] *= f
        else:
            for it in self.rep.items.values():
                it.base_level *= f

    def _ground(self, g: dict) -> None:
        before = effective(self.rep)
        eff = g["effect"]
        if eff == "retract":
            apply_edit(self.rep, Edit("retract", a=g["claim"]))
        elif eff == "assert":
            apply_edit(self.rep, Edit("set_level", a=g["claim"], value=g.get("level", 1.0)))
        else:
            raise ValueError(eff)
        if effective(self.rep) != before:
            self.revisions += 1

    def _decay(self) -> None:
        self._decay_by(self.cfg.decay_factor)

    def _distinctions(self) -> dict:
        """Would collapsing commitment/entitlement into one status, or dropping entitlement tracking, change the
        compiled operational interventions *in the current reasoning state*?"""
        assert isinstance(self.rep, Practice)
        pj = self.rep.to_json()
        mine = self._compiled(self.rep)
        single = self._compiled(build("support_single", pj))
        no_ent = self._compiled(build("scorekeeping_no_entitlement", pj))
        return {"commitment_distinction": _overlay_key(single) != _overlay_key(mine),
                "entitlement_distinction": _overlay_key(no_ent) != _overlay_key(mine)}
