"""Alternate reasoning representation: a support graph.

Vocabulary: *items* (carry tokens and effects), *levels* (0..1), *requirements* (an item is carried by a set of
items: "carry"; or only enabled by them: "enable"), *conflicts*, *self-standing* items, *eligibility*,
*retraction*, *revision*. It is built from a neutral specification (see ``reasonlab/translate.py``) and shares no
code with ``practice/graph.py``. Its algorithms differ on purpose:

* levels: widest-path (bottleneck) propagation over requirement hyper-edges with a priority queue;
* eligibility, two-level mode: grown from the eligible base (least fixpoint) — or shrunk from all backed items
  (greatest fixpoint) when ``fixpoint="greatest"`` — then conflicts remove the lower-level item (ties: both);
* single-level mode: conflicts are resolved *before* propagation and levels only flow out of eligible items, so
  there is one status (eligible with a level) instead of two (backed, and separately eligible).

Only ``active_bindings()`` reaches the runtime, through the same compiler as every other representation.
"""

from __future__ import annotations

import copy
import heapq
from dataclasses import dataclass, field


@dataclass
class Item:
    id: str
    tokens: tuple[str, ...]
    effects: list[dict]
    base_level: float = 0.0
    self_standing: bool = True


@dataclass
class Requirement:
    sources: tuple[str, ...]
    target: str
    mode: str = "carry"  # carry: sources pass their level; enable: sources only make the target eligible


@dataclass
class Evaluation:
    level: dict[str, float]
    eligible: dict[str, bool]
    note: dict[str, str]


@dataclass
class SupportGraph:
    items: dict[str, Item] = field(default_factory=dict)
    requirements: list[Requirement] = field(default_factory=list)
    conflicts: list[tuple[str, str]] = field(default_factory=list)
    retracted: set[str] = field(default_factory=set)
    blocked_tokens: set[str] = field(default_factory=set)
    mode: str = "two_level"  # "two_level" | "single_level" | "backed_only" (no eligibility check)
    fixpoint: str = "least"  # "least" | "greatest" (two_level only)

    @classmethod
    def from_spec(cls, spec: dict) -> SupportGraph:
        g = cls(mode=spec.get("mode", "two_level"), fixpoint=spec.get("fixpoint", "least"))
        for it in spec["items"]:
            g.items[it["id"]] = Item(it["id"], tuple(it["tokens"]), list(it["effects"]), float(it["base_level"]),
                                     bool(it["self_standing"]))
        g.requirements = [Requirement(tuple(r["sources"]), r["target"], r["mode"]) for r in spec.get("requirements", [])]
        g.conflicts = [tuple(c) for c in spec.get("conflicts", [])]
        g.retracted = set(spec.get("retracted", []))
        g.blocked_tokens = set(spec.get("blocked_tokens", []))
        return g

    def copy(self) -> SupportGraph:
        return copy.deepcopy(self)

    # ------------------------------------------------------------------ evaluation
    def _usable(self, i: str) -> bool:
        return i not in self.retracted and not (set(self.items[i].tokens) & self.blocked_tokens)

    def _propagate(self, seeds: dict[str, float], allowed: set[str]) -> dict[str, float]:
        """Bottleneck propagation: level(target) = max over carry requirements of min(level(sources))."""
        level = dict(seeds)
        heap = [(-v, k) for k, v in level.items()]
        heapq.heapify(heap)
        by_source: dict[str, list[Requirement]] = {}
        for r in self.requirements:
            if r.mode == "carry":
                for s in r.sources:
                    by_source.setdefault(s, []).append(r)
        done: set[str] = set()
        while heap:
            _, k = heapq.heappop(heap)
            if k in done:
                continue
            done.add(k)
            for r in by_source.get(k, []):
                if r.target not in allowed or not all(s in level for s in r.sources):
                    continue
                v = min(level[s] for s in r.sources)
                if v > level.get(r.target, 0.0) + 1e-12:
                    level[r.target] = v
                    done.discard(r.target)
                    heapq.heappush(heap, (-v, r.target))
        return level

    def _resolve_conflicts(self, candidates: set[str], level: dict[str, float]) -> tuple[set[str], dict[str, str]]:
        out, note = set(candidates), {}
        for a, b in self.conflicts:
            if a in out and b in out:
                if level[a] > level[b]:
                    out.discard(b)
                    note[b] = f"conflicts with higher-level {a}"
                elif level[b] > level[a]:
                    out.discard(a)
                    note[a] = f"conflicts with higher-level {b}"
                else:
                    out -= {a, b}
                    note[a] = note[b] = "equal-level conflict"
        return out, note

    def _justified(self, i: str, pool: set[str]) -> bool:
        if self.items[i].self_standing:
            return True
        return any(r.target == i and all(s in pool for s in r.sources) for r in self.requirements)

    def evaluate(self) -> Evaluation:
        usable = {i for i in self.items if self._usable(i)}
        base = {i: self.items[i].base_level for i in usable if self.items[i].base_level > 0}
        note: dict[str, str] = {i: "retracted or blocked" for i in self.items if i not in usable}
        if self.mode == "backed_only":
            level = self._propagate(base, usable)
            return Evaluation({i: round(v, 6) for i, v in level.items()}, {i: i in level for i in self.items}, note)
        if self.mode == "single_level":
            defeated: set[str] = set()
            for _ in range(len(self.items) + 1):
                level = self._propagate({i: v for i, v in base.items() if i not in defeated}, usable - defeated)
                _, cnote = self._resolve_conflicts(set(level), level)
                if set(cnote) <= defeated:
                    break
                defeated |= set(cnote)
                note.update(cnote)
            eligible: set[str] = set()
            for _ in range(len(self.items) + 1):  # grow from the self-standing items
                nxt = {i for i in level if self._justified(i, eligible)}
                if nxt == eligible:
                    break
                eligible = nxt
        else:
            level = self._propagate(base, usable)
            backed = set(level)
            if self.fixpoint == "greatest":
                pool = set(backed)
                for _ in range(len(self.items) + 1):
                    nxt = {i for i in pool if self._justified(i, pool)}
                    nxt, cnote = self._resolve_conflicts(nxt, level)
                    if nxt == pool:
                        break
                    pool = nxt
                eligible = pool
                note.update({i: "not justified or in conflict" for i in backed - eligible})
            else:
                eligible = set()
                for _ in range(len(self.items) + 1):
                    grown = {i for i in backed if self._justified(i, eligible)}
                    grown, cnote = self._resolve_conflicts(grown, level)
                    if grown == eligible:
                        break
                    eligible = grown
                note.update({i: "not justified or in conflict" for i in backed - eligible})
        return Evaluation({i: round(v, 6) for i, v in level.items()}, {i: i in eligible for i in self.items}, note)

    def active_bindings(self) -> list[tuple[str, dict, float, str]]:
        ev = self.evaluate()
        out = []
        for i, it in self.items.items():
            lv = ev.level.get(i, 0.0) if ev.eligible[i] else 0.0
            for e in it.effects:
                out.append((i, e, lv, ev.note.get(i, "")))
        return out

    # ------------------------------------------------------------------ edits
    def block_token(self, t: str) -> None:
        self.blocked_tokens.add(t)

    def retract(self, i: str) -> None:
        self.retracted.add(i)

    def set_level(self, i: str, v: float) -> None:
        self.retracted.discard(i)
        self.items[i].base_level = max(0.0, min(1.0, v))

    def drop_conflict(self, a: str, b: str) -> None:
        self.conflicts = [c for c in self.conflicts if set(c) != {a, b}]

    def drop_requirement(self, target: str, source: str) -> None:
        self.requirements = [r for r in self.requirements if not (r.target == target and source in r.sources)]

    def add_requirement(self, target: str, sources: tuple[str, ...]) -> None:
        self.requirements.append(Requirement(tuple(sources), target, "carry"))
