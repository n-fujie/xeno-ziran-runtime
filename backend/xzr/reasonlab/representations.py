"""Interchangeable reasoning representations and one edit vocabulary applied to all of them.

* ``scorekeeping``            practice/graph.py, commitment + entitlement tracked separately
* ``scorekeeping_no_entitlement``  same, but every commitment counts as entitled (reduced reasoning)
* ``support``                 practice/support.py, two-level (backed / eligible), least fixpoint
* ``support_greatest``        same, greatest fixpoint (matches scorekeeping's fixpoint choice)
* ``support_single``          practice/support.py, single status (eligible with a level)

``translate`` maps the scorekeeping JSON (which uses commitment/entitlement keys) to the neutral support
specification, so support.py itself never sees that vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..practice.graph import Practice
from ..practice.support import SupportGraph

REPRESENTATIONS = ("scorekeeping", "scorekeeping_no_entitlement", "support", "support_greatest", "support_single",
                   "support_backed_only")


def translate(practice_json: dict, mode: str = "two_level", fixpoint: str = "least") -> dict:
    items = [{"id": c["id"], "tokens": list(c.get("uses", [])), "effects": list(c.get("bindings", [])),
              "base_level": float(c.get("commitment", 0.0)), "self_standing": bool(c.get("default_entitled", True))}
             for c in practice_json.get("claims", [])]
    reqs = [{"sources": list(d["premises"]), "target": d["conclusion"],
             "mode": "carry" if d.get("kind", "committive") == "committive" else "enable"}
            for d in practice_json.get("dependencies", [])]
    return {"items": items, "requirements": reqs, "conflicts": [list(x) for x in practice_json.get("incompatibilities", [])],
            "retracted": list(practice_json.get("withdrawn", [])),
            "blocked_tokens": list(practice_json.get("removed_concepts", [])),
            "mode": mode, "fixpoint": fixpoint}


def build(kind: str, practice_json: dict):
    if kind == "scorekeeping":
        return Practice.from_json(practice_json)
    if kind == "scorekeeping_no_entitlement":
        p = Practice.from_json(practice_json)
        p.score_mode = "no_entitlement"
        return p
    if kind == "support":
        return SupportGraph.from_spec(translate(practice_json))
    if kind == "support_greatest":
        return SupportGraph.from_spec(translate(practice_json, fixpoint="greatest"))
    if kind == "support_single":
        return SupportGraph.from_spec(translate(practice_json, mode="single_level"))
    if kind == "support_backed_only":  # terminology-free counterpart of scorekeeping without entitlement tracking
        return SupportGraph.from_spec(translate(practice_json, mode="backed_only"))
    raise ValueError(f"unknown representation {kind}")


@dataclass(frozen=True)
class Edit:
    """One reasoning edit, expressible in every representation."""

    op: str  # remove_token | restore_token | retract | set_level | drop_conflict | drop_requirement | add_requirement
    a: str = ""
    b: str = ""
    value: float = 0.0
    sources: tuple[str, ...] = ()


def apply_edit(rep, e: Edit) -> None:
    if isinstance(rep, Practice):
        if e.op == "remove_token":
            rep.remove_concept(e.a)
        elif e.op == "restore_token":
            rep.restore_concept(e.a)
        elif e.op == "retract":
            rep.withdraw(e.a)
        elif e.op == "set_level":
            rep.assert_claim(e.a, e.value)
        elif e.op == "drop_conflict":
            rep.incompatibilities = [x for x in rep.incompatibilities if set(x) != {e.a, e.b}]
        elif e.op == "drop_requirement":
            rep.disconnect(e.a, e.b)
        elif e.op == "add_requirement":
            rep.reconnect(e.a, e.sources)
        else:
            raise ValueError(e.op)
    elif isinstance(rep, SupportGraph):
        if e.op == "remove_token":
            rep.block_token(e.a)
        elif e.op == "restore_token":
            rep.blocked_tokens.discard(e.a)
        elif e.op == "retract":
            rep.retract(e.a)
        elif e.op == "set_level":
            rep.set_level(e.a, e.value)
        elif e.op == "drop_conflict":
            rep.drop_conflict(e.a, e.b)
        elif e.op == "drop_requirement":
            rep.drop_requirement(e.a, e.b)
        elif e.op == "add_requirement":
            rep.add_requirement(e.a, e.sources)
        else:
            raise ValueError(e.op)
    else:
        raise TypeError(type(rep))


def effective(rep) -> dict[str, float]:
    """Effective strength per item/claim (what the compiler uses), comparable across representations."""
    out: dict[str, float] = {}
    for cid, _b, s, _why in rep.active_bindings():
        out[cid] = round(s, 9)
    if isinstance(rep, Practice):
        sc = rep.score()
        for cid in rep.claims:
            out[cid] = round(sc.effective(cid), 9)
    else:
        ev = rep.evaluate()
        for i in rep.items:
            out[i] = round(ev.level.get(i, 0.0) if ev.eligible[i] else 0.0, 9)
    return out
