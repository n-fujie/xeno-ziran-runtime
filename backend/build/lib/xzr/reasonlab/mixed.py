"""Mixed-rule support structure: every cluster of items is evaluated with its own rule (two-level greatest or least
fixpoint, single level, backed only); requirements that cross clusters take the source cluster's resulting
eligible level as input; conflicts across clusters are resolved afterwards (the lower level loses, ties both).

The whole record (items, requirements, conflicts, retractions) is one ``SupportGraph``; per-cluster graphs are
rebuilt from it at each evaluation, so edits apply exactly as for a plain support graph.
"""

from __future__ import annotations

import copy

from ..practice.support import Evaluation, Item, Requirement, SupportGraph

RULES = {"greatest": ("two_level", "greatest"), "least": ("two_level", "least"), "single": ("single_level", "least"),
         "backed": ("backed_only", "least")}


class MixedSupport:
    def __init__(self, record: SupportGraph, cluster_of: dict[str, int], rules: dict[int, str]):
        self.record = record
        self.cluster_of = cluster_of
        self.rules = rules

    # the record is what edits, decay and inspection see
    @property
    def items(self) -> dict[str, Item]:
        return self.record.items

    def copy(self) -> MixedSupport:
        return copy.deepcopy(self)

    def _sub(self, c: int, ext: dict[str, float]) -> SupportGraph:
        mode, fx = RULES[self.rules[c]]
        g = SupportGraph(mode=mode, fixpoint=fx)
        mine = {i for i, k in self.cluster_of.items() if k == c}
        for i in mine:
            g.items[i] = self.record.items[i]
        for r in self.record.requirements:
            if r.target not in mine:
                continue
            srcs = []
            for s in r.sources:
                if s in mine:
                    srcs.append(s)
                else:  # a source in another cluster enters as a self-standing input at its eligible level
                    pid = f"@{s}"
                    if pid not in g.items:
                        g.items[pid] = Item(pid, (), [], ext.get(s, 0.0), True)
                    srcs.append(pid)
            g.requirements.append(Requirement(tuple(srcs), r.target, r.mode))
        g.conflicts = [(a, b) for a, b in self.record.conflicts if a in mine and b in mine]
        g.retracted = set(self.record.retracted) & mine
        g.blocked_tokens = set(self.record.blocked_tokens)
        return g

    def evaluate(self) -> Evaluation:
        clusters = sorted(set(self.cluster_of.values()))
        ext: dict[str, float] = {}
        level: dict[str, float] = {}
        eligible: dict[str, bool] = {}
        note: dict[str, str] = {}
        for _ in range(8):
            level, eligible, note = {}, {}, {}
            for c in clusters:
                ev = self._sub(c, ext).evaluate()
                for i, k in self.cluster_of.items():
                    if k == c:
                        level[i] = ev.level.get(i, 0.0)
                        eligible[i] = bool(ev.eligible.get(i, False))
                        if i in ev.note:
                            note[i] = ev.note[i]
            for a, b in self.record.conflicts:
                if self.cluster_of[a] != self.cluster_of[b] and eligible[a] and eligible[b]:
                    if level[a] >= level[b]:
                        eligible[b] = False
                        note[b] = f"cross-cluster conflict with {a}"
                    if level[b] >= level[a]:
                        eligible[a] = False
                        note[a] = f"cross-cluster conflict with {b}"
            nxt = {i: level[i] for i in level if eligible[i] and level[i] > 0}
            if nxt == ext:
                break
            ext = nxt
        return Evaluation({i: v for i, v in level.items() if v > 0}, eligible, note)

    def active_bindings(self) -> list[tuple[str, dict, float, str]]:
        ev = self.evaluate()
        out = []
        for i, it in self.record.items.items():
            lv = ev.level.get(i, 0.0) if ev.eligible[i] else 0.0
            for e in it.effects:
                out.append((i, e, lv, ev.note.get(i, "")))
        return out

    # edits act on the shared record
    def __getattr__(self, name: str):
        if name in ("block_token", "retract", "set_level", "drop_conflict", "drop_requirement", "add_requirement",
                    "blocked_tokens", "retracted", "requirements", "conflicts"):
            return getattr(self.record, name)
        raise AttributeError(name)
