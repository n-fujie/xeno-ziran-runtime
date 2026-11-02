"""Causal execution history: every state change of an HPO run as a node of a directed acyclic graph.

An event records *what* changed (type, source, target), the target's state *before* and *after* the change, and the
earlier events that *caused* it. Causes are recorded by the code path that produced the change (an act is caused by
the ignition that triggered it; a transformation by the act that triggered the interaction rule; an ignition by
the transformations and veils that changed the operation's conditions since its last evaluation). This is a record
of the run's own execution — not an inference of causation from correlations.
"""

from __future__ import annotations

from typing import Any

EVENT_TYPES = ("ignite", "reignite", "cease", "act", "transform", "filter", "conflict", "couple", "split",
               "reclassify", "revise", "reinsert", "feedback", "suppress", "config", "unobservable", "veil")


class CausalHistory:
    def __init__(self, keep_states: bool = True):
        self.events: list[dict[str, Any]] = []
        self.keep_states = keep_states
        self._depth: list[int] = []
        self._ops_on_path: list[int] = []

    def add(self, t: int, type_: str, source: str, target: str, causes: list[int] | None = None,
            before: Any = None, after: Any = None, detail: dict | None = None) -> int:
        assert type_ in EVENT_TYPES, type_
        causes = sorted({c for c in (causes or []) if 0 <= c < len(self.events)})
        eid = len(self.events)
        ev: dict[str, Any] = {"id": eid, "t": t, "type": type_, "source": source, "target": target, "causes": causes}
        if self.keep_states:
            if before is not None:
                ev["before"] = before
            if after is not None:
                ev["after"] = after
        if detail:
            ev["detail"] = detail
        self.events.append(ev)
        d = 1 + max((self._depth[c] for c in causes), default=0)
        cross = max((self._ops_on_path[c] + (self.events[c]["source"] != source) for c in causes), default=1)
        self._depth.append(d)
        self._ops_on_path.append(cross)
        return eid

    def summary(self) -> dict:
        by_type: dict[str, int] = {}
        cross_links = 0
        pairs: dict[str, int] = {}
        for ev in self.events:
            by_type[ev["type"]] = by_type.get(ev["type"], 0) + 1
            for c in ev["causes"]:
                a, b = self.events[c]["source"], ev["source"]
                if a != b and not a.startswith(("world", "config", "field")) and not b.startswith(("world", "config")):
                    cross_links += 1
                    key = f"{self.events[c]['type']}→{ev['type']}"
                    pairs[key] = pairs.get(key, 0) + 1
        return {"events": len(self.events), "by_type": by_type, "cross_operation_links": cross_links,
                "cross_link_types": dict(sorted(pairs.items(), key=lambda kv: -kv[1])[:20]),
                "max_depth": max(self._depth, default=0),
                "max_sources_on_a_path": max(self._ops_on_path, default=0)}

    def chain(self, eid: int, limit: int = 12) -> list[dict]:
        """One longest causal chain ending at ``eid`` (oldest first), for display."""
        out: list[dict] = []
        cur: int | None = eid
        while cur is not None and len(out) < limit:
            ev = self.events[cur]
            out.append({k: ev[k] for k in ("id", "t", "type", "source", "target")})
            cur = max(ev["causes"], key=lambda c: self._depth[c]) if ev["causes"] else None
        return out[::-1]

    def deepest(self) -> int | None:
        return max(range(len(self.events)), key=lambda i: (self._ops_on_path[i], self._depth[i])) if self.events else None
