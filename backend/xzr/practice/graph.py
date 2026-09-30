"""Commitment / entitlement scorekeeping.

Inspired by inferential scorekeeping, but deliberately minimal and non-authoritative: this is one
explicit, inspectable way of keeping score, not a theory of meaning. Everything here is a data
structure plus a deterministic fixpoint.

* A **claim** uses concepts (opaque tokens) and may carry operational **bindings**.
* A **commitment** is a strength in [0, 1] attached to a claim; asserted explicitly or inherited as a
  **consequence** through committive dependencies (strength = weakest premise).
* **Entitlement** requires commitment plus either default entitlement or a dependency whose premises are
  all entitled; of two incompatible entitled commitments the weaker loses entitlement (ties: both).
* **Withdrawal** and **concept removal** make a claim unavailable; **revision** changes its strength.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field


@dataclass
class Claim:
    id: str
    text: str
    uses: tuple[str, ...] = ()
    bindings: list[dict] = field(default_factory=list)
    default_entitled: bool = True


@dataclass
class Dependency:
    premises: tuple[str, ...]
    conclusion: str
    kind: str = "committive"  # committive | permissive


@dataclass
class Score:
    commitment: dict[str, float]
    entitled: dict[str, bool]
    status: dict[str, str]

    def effective(self, cid: str) -> float:
        return self.commitment.get(cid, 0.0) if self.entitled.get(cid) else 0.0

    def to_json(self) -> dict:
        return {"commitment": self.commitment, "entitled": self.entitled, "status": self.status}


@dataclass
class Practice:
    concepts: list[str] = field(default_factory=list)
    claims: dict[str, Claim] = field(default_factory=dict)
    dependencies: list[Dependency] = field(default_factory=list)
    incompatibilities: list[tuple[str, str]] = field(default_factory=list)
    asserted: dict[str, float] = field(default_factory=dict)
    withdrawn: set[str] = field(default_factory=set)
    removed_concepts: set[str] = field(default_factory=set)
    # "two_status": commitment and entitlement are tracked separately (default).
    # "no_entitlement": reduced reasoning — every commitment counts as entitled (no support / incompatibility check).
    score_mode: str = "two_status"

    # ------------------------------------------------------------------ construction
    @classmethod
    def from_json(cls, d: dict | None) -> Practice:
        if not d:
            return cls()
        p = cls(concepts=list(d.get("concepts", [])))
        for c in d.get("claims", []):
            p.claims[c["id"]] = Claim(c["id"], c.get("text", ""), tuple(c.get("uses", [])), list(c.get("bindings", [])),
                                      bool(c.get("default_entitled", True)))
            if c.get("commitment", 0) > 0:
                p.asserted[c["id"]] = float(c["commitment"])
        for dep in d.get("dependencies", []):
            p.dependencies.append(Dependency(tuple(dep["premises"]), dep["conclusion"], dep.get("kind", "committive")))
        p.incompatibilities = [tuple(x) for x in d.get("incompatibilities", [])]
        p.withdrawn = set(d.get("withdrawn", []))
        p.removed_concepts = set(d.get("removed_concepts", []))
        for c in p.claims.values():
            for u in c.uses:
                if u not in p.concepts:
                    p.concepts.append(u)
        p.validate()
        return p

    def to_json(self) -> dict:
        return {
            "concepts": self.concepts,
            "claims": [{"id": c.id, "text": c.text, "uses": list(c.uses), "bindings": c.bindings,
                        "default_entitled": c.default_entitled, "commitment": self.asserted.get(c.id, 0.0)}
                       for c in self.claims.values()],
            "dependencies": [{"premises": list(d.premises), "conclusion": d.conclusion, "kind": d.kind}
                             for d in self.dependencies],
            "incompatibilities": [list(x) for x in self.incompatibilities],
            "withdrawn": sorted(self.withdrawn), "removed_concepts": sorted(self.removed_concepts),
        }

    def validate(self) -> None:
        for d in self.dependencies:
            for x in (*d.premises, d.conclusion):
                if x not in self.claims:
                    raise ValueError(f"dependency refers to unknown claim {x}")
            if d.kind not in ("committive", "permissive"):
                raise ValueError(f"unknown dependency kind {d.kind}")
        for a, b in self.incompatibilities:
            if a not in self.claims or b not in self.claims:
                raise ValueError(f"incompatibility refers to unknown claim {a}/{b}")

    def copy(self) -> Practice:
        return copy.deepcopy(self)

    # ------------------------------------------------------------------ scorekeeping
    def available(self, cid: str) -> tuple[bool, str]:
        if cid in self.withdrawn:
            return False, "withdrawn"
        gone = [u for u in self.claims[cid].uses if u in self.removed_concepts]
        if gone:
            return False, f"uses removed concept: {', '.join(gone)}"
        return True, ""

    def score(self) -> Score:
        status: dict[str, str] = {}
        avail = {}
        for cid in self.claims:
            ok, why = self.available(cid)
            avail[cid] = ok
            if not ok:
                status[cid] = why
        commit = {c: s for c, s in self.asserted.items() if avail.get(c) and s > 0}
        source = {c: "asserted" for c in commit}
        changed = True
        while changed:
            changed = False
            for d in self.dependencies:
                if d.kind != "committive" or not avail[d.conclusion]:
                    continue
                if all(p in commit for p in d.premises):
                    s = min(commit[p] for p in d.premises)
                    if s > commit.get(d.conclusion, 0.0) + 1e-12:
                        commit[d.conclusion] = s
                        source[d.conclusion] = "consequence of " + ", ".join(d.premises)
                        changed = True
        ent = set(commit)
        lost: dict[str, str] = {}
        for _ in range(64 if self.score_mode == "two_status" else 0):
            nxt = set()
            for c in commit:
                if c not in ent:
                    continue
                cl = self.claims[c]
                supports = [d for d in self.dependencies if d.conclusion == c]
                if cl.default_entitled or any(all(p in ent for p in d.premises) for d in supports):
                    nxt.add(c)
                else:
                    lost[c] = "no entitled support"
            for a, b in self.incompatibilities:
                if a in nxt and b in nxt:
                    if commit[a] > commit[b]:
                        nxt.discard(b)
                        lost[b] = f"incompatible with stronger {a}"
                    elif commit[b] > commit[a]:
                        nxt.discard(a)
                        lost[a] = f"incompatible with stronger {b}"
                    else:
                        nxt.discard(a)
                        nxt.discard(b)
                        lost[a] = lost[b] = "incompatible commitments of equal strength"
            if nxt == ent:
                break
            ent = nxt
        entitled = {c: (c in ent) for c in self.claims}
        for c in self.claims:
            if c in status:
                continue
            if c not in commit:
                status[c] = "not committed"
            elif c in ent:
                status[c] = f"committed ({source[c]}), entitled"
            else:
                status[c] = f"committed ({source[c]}), not entitled: {lost.get(c, 'unsupported')}"
        return Score({c: round(s, 6) for c, s in commit.items()}, entitled, status)

    def active_bindings(self) -> list[tuple[str, dict, float, str]]:
        """(claim id, binding, effective strength, status) for every binding — the only thing compiled to the runtime."""
        sc = self.score()
        return [(cid, b, sc.effective(cid), sc.status.get(cid, "")) for cid, cl in self.claims.items() for b in cl.bindings]

    # ------------------------------------------------------------------ dependency queries
    def consequences(self, claims: set[str]) -> set[str]:
        """Transitive downstream claims (via any dependency) of a set of claims."""
        out: set[str] = set()
        frontier = set(claims)
        while frontier:
            nxt = set()
            for d in self.dependencies:
                if frontier & set(d.premises) and d.conclusion not in out and d.conclusion not in claims:
                    nxt.add(d.conclusion)
            out |= nxt
            frontier = nxt
        return out

    def dependencies_of(self, token: str) -> dict:
        """What depends on a concept or claim: direct users, inferential consequences, incompatibilities."""
        if token in self.claims:
            direct = {token}
        else:
            direct = {c.id for c in self.claims.values() if token in c.uses}
        cons = self.consequences(direct)
        deps = [d for d in self.dependencies if set(d.premises) & (direct | cons) or d.conclusion in direct | cons]
        inc = [list(x) for x in self.incompatibilities if set(x) & (direct | cons)]
        return {"token": token, "direct": sorted(direct), "consequences": sorted(cons),
                "dependencies": [{"premises": list(d.premises), "conclusion": d.conclusion, "kind": d.kind} for d in deps],
                "incompatibilities": inc}

    # ------------------------------------------------------------------ revisions
    def _need(self, cid: str) -> None:
        if cid not in self.claims:
            raise KeyError(f"unknown claim: {cid}")

    def remove_concept(self, c: str) -> None:
        if c not in self.concepts:
            raise KeyError(f"unknown concept: {c}")
        self.removed_concepts.add(c)

    def restore_concept(self, c: str) -> None:
        self.removed_concepts.discard(c)

    def withdraw(self, cid: str) -> None:
        self._need(cid)
        self.withdrawn.add(cid)

    def assert_claim(self, cid: str, strength: float = 1.0) -> None:
        self._need(cid)
        self.withdrawn.discard(cid)
        self.asserted[cid] = max(0.0, min(1.0, strength))

    def revise(self, cid: str, strength: float) -> None:
        self._need(cid)
        self.asserted[cid] = max(0.0, min(1.0, strength))

    def current_strength(self, cid: str) -> float:
        self._need(cid)
        return self.asserted.get(cid) or self.score().commitment.get(cid, 0.0)

    def weaken(self, cid: str, factor: float = 0.5) -> None:
        self.revise(cid, self.current_strength(cid) * factor)

    def strengthen(self, cid: str, amount: float = 0.5) -> None:
        self.revise(cid, self.current_strength(cid) + amount)

    def introduce(self, claim: Claim, strength: float, premises: tuple[str, ...] = ()) -> None:
        if claim.id in self.claims:
            raise ValueError(f"claim exists: {claim.id}")
        self.claims[claim.id] = claim
        for u in claim.uses:
            if u not in self.concepts:
                self.concepts.append(u)
        if strength > 0:
            self.asserted[claim.id] = strength
        if premises:
            self.reconnect(claim.id, premises)

    def reconnect(self, cid: str, premises: tuple[str, ...], kind: str = "committive") -> None:
        self._need(cid)
        for p in premises:
            self._need(p)
        self.dependencies.append(Dependency(tuple(premises), cid, kind))

    def disconnect(self, cid: str, premise: str) -> int:
        self._need(cid)
        before = len(self.dependencies)
        self.dependencies = [d for d in self.dependencies if not (d.conclusion == cid and premise in d.premises)]
        return before - len(self.dependencies)
