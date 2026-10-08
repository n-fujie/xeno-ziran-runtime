"""World-responsive revision triggers.

A trigger watches an operational metric of one region, calibrated against that region's own baseline (mean and
spread over the checks before reasoning is allowed), and emits reasoning edits when the metric deviates
persistently. Edits act only on items whose effects are bound to that region. Triggers never touch world state;
their edits reach the world only through recompilation and the intervention gate.

Kinds (metric → edit):
    memory_level          memory low → raise a memory-bound item; high → retract it
    reachability          reach from the record region to the region low → retract items gating the region
    mismatch              |activity − running prediction| persistently high → halve the level of the region's items
    topology_change       connection churn high → retract mutation items bound to the region
    failed_intervention   an active threshold item whose intended direction is contradicted by the activity
                          deviation → retract it
    support_path_loss     reach from the record region low → drop one requirement of a derived item on the region
    new_incompatibility   two regions both persistently over-active → add a conflict between their items
    delayed_consequence   an item raised by a trigger that produced no activity change after a delay → retract
    repeated_instability  activity variance high, repeatedly → raise a threshold-raising item of the region
    unexpected_closure    closure rate high → raise a gate item of the region
    overwrite             a region persistently over-active → retract an active item bound to a region of another
                          reasoning cluster (clusters overwriting each other's records)
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

import numpy as np

from .representations import Edit, effective

KINDS = ("memory_level", "reachability", "mismatch", "topology_change", "failed_intervention", "support_path_loss",
         "new_incompatibility", "delayed_consequence", "repeated_instability", "unexpected_closure")
EXTRA_KINDS = ("overwrite",)
METRIC = {"memory_level": "memory", "reachability": "reach", "mismatch": "activity", "topology_change": "churn",
          "failed_intervention": "activity", "support_path_loss": "reach", "new_incompatibility": "activity",
          "delayed_consequence": "activity", "repeated_instability": "activity", "unexpected_closure": "closure",
          "overwrite": "activity"}


@dataclass
class TriggerSet:
    kinds: tuple[str, ...]
    regions: tuple[str, ...]  # region set names (e.g. "Z3")
    items_by_region: dict[str, list[tuple[str, dict]]]  # region -> [(item id, effect)]
    requirements_of: dict[str, list[tuple[str, ...]]]  # item -> requirement source tuples
    record_region: str = "R"
    z: float = 2.0
    window: int = 2
    refractory: int = 5
    delay: int = 5
    baseline: dict[tuple[str, str], list[float]] = field(default_factory=lambda: defaultdict(list))
    stats: dict[tuple[str, str], tuple[float, float]] = field(default_factory=dict)
    streak: dict[tuple[str, str, int], int] = field(default_factory=lambda: defaultdict(int))
    last_fire: dict[tuple[str, str], int] = field(default_factory=dict)
    history: dict[str, deque] = field(default_factory=lambda: defaultdict(lambda: deque(maxlen=6)))
    pending: list[tuple[int, str, str, float]] = field(default_factory=list)  # (due check, region, item, z0)
    unstable: dict[str, deque] = field(default_factory=lambda: defaultdict(lambda: deque(maxlen=20)))
    fired: list[tuple[int, str, str, str]] = field(default_factory=list)  # (t, kind, region, edit op)
    check: int = 0
    # external-memory dependence: region -> [(item, base level)]; items lose level while the region's memory is
    # persistently below its baseline and regain it when it recovers
    memory_groundings: dict[str, list[tuple[str, float]]] = field(default_factory=dict)
    lowered: set[str] = field(default_factory=set)
    region_cluster: dict[str, int] = field(default_factory=dict)  # for "overwrite"
    trace: list | None = None  # when a list: per check (check, t, {region: activity z}) after calibration

    # ------------------------------------------------------------------ metric access
    def _value(self, loop, kind: str, region: str) -> float:
        m = METRIC[kind]
        if m == "reach":
            return loop.probe.value("reach", region, self.record_region)
        if kind == "mismatch":
            h = self.history[region]
            v = loop.probe.value("activity", region)
            pred = float(np.mean(h)) if h else v
            return abs(v - pred)
        if kind == "repeated_instability":
            hist = list(self.history[region])
            return float(np.std(hist)) if len(hist) >= 3 else 0.0
        return loop.probe.value(m, region)

    def observe(self, loop, calibrating: bool) -> None:
        """Called at every check. While calibrating, collect baselines; the first call after calibration freezes
        them (mean, sd)."""
        values = {(k, r): self._value(loop, k, r) for k in self.kinds for r in self.regions}
        for r in self.memory_groundings:
            values[("grounding", r)] = loop.probe.value("memory", r)
        if calibrating:
            for key, v in values.items():
                self.baseline[key].append(v)
        elif not self.stats:
            for key, vs in self.baseline.items():
                a = np.asarray(vs, dtype=float)
                self.stats[key] = (float(a.mean()), float(a.std() + 1e-9 + 0.05 * abs(a.mean())))
        for r in self.regions:
            self.history[r].append(loop.probe.value("activity", r))
        self._values = values
        if self.trace is not None and self.stats:
            # activity z-score per region (baseline of the failed_intervention metric = raw activity)
            zkind = "failed_intervention" if "failed_intervention" in self.kinds else None
            self.trace.append((self.check, loop.world.state.t,
                               {r: round(self._zval(zkind, r), 4) if zkind else round(loop.probe.value("activity", r), 6)
                                for r in self.regions}))

    def _zval(self, kind: str, region: str) -> float:
        mu, sd = self.stats.get((kind, region), (0.0, 1.0))
        return (self._values[(kind, region)] - mu) / sd

    def _persist(self, kind: str, region: str, cond: bool, tag: int = 0) -> bool:
        key = (kind, region, tag)
        self.streak[key] = self.streak[key] + 1 if cond else 0
        if self.streak[key] < self.window:
            return False
        return self.check - self.last_fire.get((kind, region), -10**9) >= self.refractory

    def _items(self, region: str, ops: tuple[str, ...] | None = None, pred=None) -> list[tuple[str, dict]]:
        out = [(i, e) for i, e in self.items_by_region.get(region, []) if ops is None or e["op"] in ops]
        return [x for x in out if pred is None or pred(x)]

    # ------------------------------------------------------------------ firing
    def fire(self, loop) -> list[Edit]:
        """Edits to apply now (reasoning active)."""
        self.check += 1
        if not self.stats:
            return []
        eff = effective(loop.rep)
        edits: list[Edit] = []

        def emit(kind: str, region: str, e: Edit) -> None:
            edits.append(e)
            self.last_fire[(kind, region)] = self.check
            self.fired.append((loop.world.state.t, kind, region, e.op))

        for r, group in self.memory_groundings.items():
            z = self._zval("grounding", r)
            if r not in self.lowered and self._persist("grounding", r, z < -1.0, 0):
                self.lowered.add(r)
                for i, b in group:
                    emit("grounding", r, Edit("set_level", a=i, value=round(0.3 * b, 6)))
            elif r in self.lowered and self._persist("grounding", r, z > -0.5, 1):
                self.lowered.discard(r)
                for i, b in group:
                    emit("grounding", r, Edit("set_level", a=i, value=b))
        for kind in self.kinds:
            for r in self.regions:
                z = self._zval(kind, r)
                if kind == "memory_level":
                    items = self._items(r, ("memory_condition",))
                    if items and self._persist(kind, r, z < -self.z, 0):
                        emit(kind, r, Edit("set_level", a=items[0][0], value=1.0))
                    elif items and self._persist(kind, r, z > self.z, 1):
                        emit(kind, r, Edit("retract", a=items[0][0]))
                elif kind == "reachability":
                    items = self._items(r, ("gate",), lambda x: eff.get(x[0], 0) > 0)
                    if items and self._persist(kind, r, z < -self.z):
                        emit(kind, r, Edit("retract", a=items[0][0]))
                elif kind == "mismatch":
                    items = self._items(r, None, lambda x: eff.get(x[0], 0) > 0)
                    if items and self._persist(kind, r, z > self.z):
                        i = items[0][0]
                        emit(kind, r, Edit("set_level", a=i, value=round(eff[i] * 0.5, 6)))
                elif kind == "topology_change":
                    items = self._items(r, ("mutation",), lambda x: eff.get(x[0], 0) > 0)
                    if items and self._persist(kind, r, z > self.z):
                        emit(kind, r, Edit("retract", a=items[0][0]))
                elif kind == "failed_intervention":
                    act = self._zval("failed_intervention", r)
                    for k, (i, e) in enumerate(self._items(r, ("scale_threshold",), lambda x: eff.get(x[0], 0) > 0)):
                        wrong = (e["factor"] > 1 and act > 1.0) or (e["factor"] < 1 and act < -1.0)
                        if self._persist(kind, r, wrong, k):
                            emit(kind, r, Edit("retract", a=i))
                            break
                elif kind == "support_path_loss":
                    derived = [(i, e) for i, e in self._items(r) if self.requirements_of.get(i)]
                    if derived and self._persist(kind, r, z < -self.z):
                        i = derived[0][0]
                        emit(kind, r, Edit("drop_requirement", a=i, b=self.requirements_of[i][0][0]))
                elif kind == "repeated_instability":
                    hit = z > self.z
                    self.unstable[r].append(1 if hit else 0)
                    items = self._items(r, ("scale_threshold",), lambda x: x[1]["factor"] > 1)
                    if items and sum(self.unstable[r]) >= 2 and self._persist(kind, r, hit, 0):
                        emit(kind, r, Edit("set_level", a=items[0][0], value=1.0))
                        self.pending.append((self.check + self.delay, r, items[0][0], z))
                elif kind == "overwrite":
                    own = self.region_cluster.get(r)
                    if own is not None and self._persist(kind, r, z > self.z):
                        other = [(i, e) for rr, lst in self.items_by_region.items()
                                 if self.region_cluster.get(rr, own) != own for i, e in lst if eff.get(i, 0) > 0]
                        if other:
                            emit(kind, r, Edit("retract", a=other[0][0]))
                elif kind == "unexpected_closure":
                    items = self._items(r, ("gate",))
                    if items and self._persist(kind, r, z > self.z):
                        emit(kind, r, Edit("set_level", a=items[0][0], value=1.0))
                        self.pending.append((self.check + self.delay, r, items[0][0],
                                             self._zval("mismatch", r) if "mismatch" in self.kinds else 0.0))
            if kind == "new_incompatibility":
                hot = [r for r in self.regions if self._persist(kind, r, self._zval(kind, r) > self.z)]
                if len(hot) >= 2:
                    ia = self._items(hot[0], None, lambda x: eff.get(x[0], 0) > 0)
                    ib = self._items(hot[1], None, lambda x: eff.get(x[0], 0) > 0)
                    if ia and ib and ia[0][0] != ib[0][0]:
                        emit(kind, hot[0], Edit("add_conflict", a=ia[0][0], b=ib[0][0]))
            if kind == "delayed_consequence":
                due = [p for p in self.pending if p[0] <= self.check]
                self.pending = [p for p in self.pending if p[0] > self.check]
                for _, r, i, z0 in due:
                    if abs(self._zval("delayed_consequence", r) - z0) < 0.5:
                        emit(kind, r, Edit("retract", a=i))
        return edits


def trigger_set(kinds: tuple[str, ...], spec: dict, regions: tuple[str, ...] | None = None,
                record_region: str = "R", **kw) -> TriggerSet:
    """Build a trigger set for a structure: regions default to every region an item is bound to."""
    by_region: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for it in spec["items"]:
        for e in it["effects"]:
            reg = e["target"][1:] if e["target"].startswith("BZ") else e["target"]
            if reg.startswith(("L", "Q")):
                continue
            by_region[reg].append((it["id"], e))
    reqs: dict[str, list[tuple[str, ...]]] = defaultdict(list)
    for r in spec["requirements"]:
        reqs[r["target"]].append(tuple(r["sources"]))
    regs = regions or tuple(sorted(by_region, key=lambda x: int(x[1:]) if x[1:].isdigit() else 0))
    ts = TriggerSet(tuple(kinds), tuple(regs), dict(by_region), dict(reqs), record_region=record_region, **kw)
    nc = int(spec.get("clusters", 1))
    if nc > 1:
        ts.region_cluster = {r: int(r[1:]) % nc for r in regs if r[1:].isdigit()}
    mode = spec.get("dynamic", {}).get("memory_grounding")
    if mode:
        roots = [(it["id"], it["base_level"]) for it in spec["items"] if it["self_standing"] and it["base_level"] > 0]
        if mode == "local":
            ts.memory_groundings = {record_region: roots}
        else:
            k = 8
            ts.memory_groundings = {f"Z{j}": roots[j::k] for j in range(k) if roots[j::k]}
    return ts
