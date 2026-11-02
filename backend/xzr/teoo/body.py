"""Open Body Graph: a body is a *declared* graph, versioned, not a fixed skeleton.

    Body                 id, name, family (human / artificial / non-human / distributed / unknown), a list of ConfigurationVersions
    Component            a part: a segment, a node, a sensor, an operation line, a tool ... (kind is free text)
    Relation             between two components: a joint, a coupling, a signal, a dependency, a contact, a support ... with its *basis* (declared / observed /
                         estimated / hypothesized) and its *claim* (structural / association / causal)
    Constraint           a rule that applies to some components or relations
    Boundary             a set of components that an observer or a declaration treats as the body's limit (it may depend on who observes)
    ObservationTarget    what an observation variable is about: a component or a relation
    ConfigurationVersion one state of the structure; every change (add, remove, sever, rejoin, reconfigure, change of boundary) makes a new version that names its
                         parent and the change, with a digest chained to the parent's. Nothing is overwritten.

A correlation never becomes a causal edge by itself: a relation with claim 'causal' must name supporting records and a design that can support it (an intervention
comparison, a randomised N-of-1, a natural experiment); :func:`promote_to_causal` is the only route and it makes a new version. The human simplified skeleton is one
*preset* (its coordinates are for drawing a concept, not anatomical measurements); the other presets are not human. What is *represented* here is not what has been
*validated*: nothing in this module simulates a body.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from .provenance import digest_of, now_iso
from .schema import Issue

FAMILIES = ("human", "artificial", "non-human", "distributed", "unknown")
BASES = ("declared", "observed", "estimated", "hypothesized")
CLAIMS = ("structural", "association", "causal")
CAUSAL_DESIGNS = ("intervention-comparison", "randomized-n-of-1", "natural-experiment")
STATES = ("active", "severed")
SECTIONS = ("components", "relations", "constraints", "boundaries", "targets")


def component(cid: str, kind: str, label: str = "", **attrs: Any) -> dict:
    return {"id": cid, "kind": kind, "label": label or cid, "attrs": attrs}


def relation(rid: str, source: str, target: str, kind: str, *, directed: bool = False, basis: str = "declared", claim: str = "structural", support: list[str] | None = None,
             design: str | None = None, state: str = "active", **attrs: Any) -> dict:
    return {"id": rid, "source": source, "target": target, "kind": kind, "directed": directed, "basis": basis, "claim": claim, "support": list(support or []), "design": design, "state": state, "attrs": attrs}


def constraint(cid: str, applies_to: list[str], kind: str, description: str = "", **params: Any) -> dict:
    return {"id": cid, "applies_to": list(applies_to), "kind": kind, "description": description, "params": params}


def boundary(bid: str, members: list[str], description: str = "", defined_by: str = "declared", observer: str | None = None) -> dict:
    return {"id": bid, "members": list(members), "description": description, "defined_by": defined_by, "observer": observer}


def target(tid: str, ref: str, variables: list[str], anatomical_ref: str | None = None, **meta: Any) -> dict:
    return {"id": tid, "ref": ref, "variables": list(variables), "anatomical_ref": anatomical_ref, "meta": meta}


def _version(n: int, parent: dict | None, change: dict, content: dict, at: str | None) -> dict:
    body = {"version": n, "parent": None if parent is None else parent["version"], "change": change, **{k: content[k] for k in SECTIONS}}
    return {**body, "at": at or now_iso(), "digest": digest_of({"parent_digest": None if parent is None else parent["digest"], **body})}


class Body:
    def __init__(self, body_id: str, name: str, family: str, versions: list[dict], meta: dict | None = None):
        self.id, self.name, self.family, self.versions, self.meta = body_id, name, family, versions, meta or {}

    @property
    def current(self) -> dict:
        return self.versions[-1]

    def at(self, n: int) -> dict:
        return next(v for v in self.versions if v["version"] == n)

    def to_dict(self) -> dict:
        return {"schema": "teoo.body/1", "id": self.id, "name": self.name, "family": self.family, "meta": self.meta, "versions": copy.deepcopy(self.versions)}

    @classmethod
    def from_dict(cls, d: dict) -> Body:
        return cls(d["id"], d["name"], d["family"], copy.deepcopy(d["versions"]), d.get("meta"))

    def _next(self, change: dict, mutate: Any, at: str | None = None) -> Body:
        content = {k: copy.deepcopy(self.current[k]) for k in SECTIONS}
        mutate(content)
        v = _version(self.current["version"] + 1, self.current, change, content, at)
        return Body(self.id, self.name, self.family, [*self.versions, v], self.meta)


def new_body(body_id: str, name: str, family: str, *, components: list[dict] | None = None, relations: list[dict] | None = None, constraints: list[dict] | None = None,
             boundaries: list[dict] | None = None, targets: list[dict] | None = None, meta: dict | None = None, at: str | None = None) -> Body:
    content = {"components": components or [], "relations": relations or [], "constraints": constraints or [], "boundaries": boundaries or [], "targets": targets or []}
    return Body(body_id, name, family, [_version(1, None, {"op": "declare"}, content, at)], meta)


def validate_body(b: Body | dict) -> list[Issue]:
    d = b.to_dict() if isinstance(b, Body) else b
    out: list[Issue] = []
    if d.get("family") not in FAMILIES:
        out.append(Issue("family", "BAD_FAMILY", f"family must be one of {FAMILIES}"))
    prev = None
    for v in d["versions"]:
        w = f"version[{v['version']}]"
        ids: dict[str, set] = {s: set() for s in SECTIONS}
        for s in SECTIONS:
            for it in v[s]:
                if it["id"] in ids[s]:
                    out.append(Issue(f"{w}.{s}", "DUPLICATE_ID", f"duplicate id {it['id']!r}"))
                ids[s].add(it["id"])
        comps, rels = ids["components"], ids["relations"]
        for r in v["relations"]:
            if r["source"] not in comps or r["target"] not in comps:
                out.append(Issue(f"{w}.relations[{r['id']}]", "DANGLING", "a relation joins components that are not in this version"))
            if r["basis"] not in BASES or r["claim"] not in CLAIMS or r["state"] not in STATES:
                out.append(Issue(f"{w}.relations[{r['id']}]", "BAD_RELATION_FIELD", f"basis in {BASES}, claim in {CLAIMS}, state in {STATES}"))
            if r["claim"] == "causal" and (not r["support"] or r["design"] not in CAUSAL_DESIGNS):
                out.append(Issue(f"{w}.relations[{r['id']}]", "CAUSAL_WITHOUT_SUPPORT", f"a causal relation names supporting records and a design in {CAUSAL_DESIGNS}; a correlation is an association, never an assumed cause"))
            if r["claim"] == "structural" and r["basis"] not in ("declared",):
                out.append(Issue(f"{w}.relations[{r['id']}]", "STRUCTURAL_NOT_DECLARED", "a structural relation is declared; an observed or inferred relation is an association or a causal claim"))
        for c in v["constraints"]:
            if not set(c["applies_to"]) <= comps | rels:
                out.append(Issue(f"{w}.constraints[{c['id']}]", "DANGLING", "a constraint applies to something not in this version"))
        for bd in v["boundaries"]:
            if not set(bd["members"]) <= comps:
                out.append(Issue(f"{w}.boundaries[{bd['id']}]", "DANGLING", "a boundary names components not in this version"))
        for t in v["targets"]:
            if t["ref"] not in comps | rels:
                out.append(Issue(f"{w}.targets[{t['id']}]", "DANGLING", "an observation target refers to something not in this version"))
        body = {"version": v["version"], "parent": v["parent"], "change": v["change"], **{k: v[k] for k in SECTIONS}}
        want = digest_of({"parent_digest": None if prev is None else prev["digest"], **body})
        if v["digest"] != want:
            out.append(Issue(w, "VERSION_DIGEST_MISMATCH", "the version does not match its digest (or its parent's): the history was changed"))
        prev = v
    return out


# ------------------------------------------------------------------------------------------------ changes: every one is a new version with the change recorded
def add_component(b: Body, comp: dict, at: str | None = None) -> Body:
    return b._next({"op": "add_component", "id": comp["id"]}, lambda c: c["components"].append(comp), at)


def remove_component(b: Body, cid: str, at: str | None = None) -> Body:
    """Removing a component also removes the relations, targets, constraint references and boundary memberships that name it; which relations went is recorded in the change."""
    gone = [r["id"] for r in b.current["relations"] if cid in (r["source"], r["target"])]
    removed = {cid, *gone}

    def f(c: dict) -> None:
        c["components"] = [x for x in c["components"] if x["id"] != cid]
        c["relations"] = [r for r in c["relations"] if cid not in (r["source"], r["target"])]
        c["targets"] = [t for t in c["targets"] if t["ref"] not in removed]
        for cs in c["constraints"]:
            cs["applies_to"] = [a for a in cs["applies_to"] if a not in removed]
        c["constraints"] = [cs for cs in c["constraints"] if cs["applies_to"]]
        for bd in c["boundaries"]:
            bd["members"] = [m for m in bd["members"] if m != cid]

    return b._next({"op": "remove_component", "id": cid, "removed_relations": gone}, f, at)


def sever(b: Body, rid: str, at: str | None = None, note: str = "") -> Body:
    def f(c: dict) -> None:
        for r in c["relations"]:
            if r["id"] == rid:
                r["state"] = "severed"
    return b._next({"op": "sever", "id": rid, "note": note}, f, at)


def rejoin(b: Body, rid: str, at: str | None = None, note: str = "") -> Body:
    def f(c: dict) -> None:
        for r in c["relations"]:
            if r["id"] == rid:
                r["state"] = "active"
    return b._next({"op": "rejoin", "id": rid, "note": note}, f, at)


def connect(b: Body, rel: dict, at: str | None = None) -> Body:
    return b._next({"op": "connect", "id": rel["id"]}, lambda c: c["relations"].append(rel), at)


def change_boundary(b: Body, bid: str, members: list[str], at: str | None = None, note: str = "") -> Body:
    def f(c: dict) -> None:
        for bd in c["boundaries"]:
            if bd["id"] == bid:
                bd["members"] = list(members)
    return b._next({"op": "change_boundary", "id": bid, "members": list(members), "note": note}, f, at)


def reconfigure(b: Body, note: str, mutate: Any, at: str | None = None) -> Body:
    """An arbitrary change of the structure, as one new version with a note (the mutation gets a copy of the content)."""
    return b._next({"op": "reconfigure", "note": note}, mutate, at)


def promote_to_causal(b: Body, rid: str, support: list[str], design: str, at: str | None = None) -> Body:
    """The only route from an association to a causal claim: it needs supporting records and a design that can support one. It makes a new version; the association stays in the history."""
    if not support or design not in CAUSAL_DESIGNS:
        raise ValueError(f"a causal claim needs supporting record ids and a design in {CAUSAL_DESIGNS}")

    def f(c: dict) -> None:
        for r in c["relations"]:
            if r["id"] == rid:
                r["claim"], r["support"], r["design"] = "causal", list(support), design
    return b._next({"op": "promote_to_causal", "id": rid, "design": design, "support": list(support)}, f, at)


def configuration_changes(b: Body) -> list[dict]:
    return [{"version": v["version"], "change": v["change"], "at": v["at"]} for v in b.versions]


# ------------------------------------------------------------------------------------------------ presets
_HUMAN_LAYOUT = {  # concept drawing coordinates (0-100 x 0-200): a picture of a simplified skeleton, not an anatomical measurement
    "head": (50, 18), "trunk": (50, 62), "upper_arm_l": (32, 48), "forearm_l": (24, 74), "hand_l": (20, 96), "upper_arm_r": (68, 48), "forearm_r": (76, 74), "hand_r": (80, 96),
    "thigh_l": (42, 110), "shank_l": (40, 148), "foot_l": (38, 184), "thigh_r": (58, 110), "shank_r": (60, 148), "foot_r": (62, 184),
}
_HUMAN_JOINTS = (("neck", "head", "trunk"), ("shoulder_l", "trunk", "upper_arm_l"), ("elbow_l", "upper_arm_l", "forearm_l"), ("wrist_l", "forearm_l", "hand_l"),
                 ("shoulder_r", "trunk", "upper_arm_r"), ("elbow_r", "upper_arm_r", "forearm_r"), ("wrist_r", "forearm_r", "hand_r"), ("hip_l", "trunk", "thigh_l"),
                 ("knee_l", "thigh_l", "shank_l"), ("ankle_l", "shank_l", "foot_l"), ("hip_r", "trunk", "thigh_r"), ("knee_r", "thigh_r", "shank_r"), ("ankle_r", "shank_r", "foot_r"))
_JOINT_VARIABLES = {"knee_l": "joint.angle.knee_l", "hip_l": "joint.angle.hip_l", "elbow_r": "joint.angle.elbow_r", "ankle_l": "joint.angle.ankle_l"}
_REGION_VARIABLES = {"head": ["temp.skin.forehead", "cog.attention.score"], "trunk": ["hr.beat", "resp.rate", "resp.chest_motion", "posture.trunk.lean"], "thigh_l": ["emg.rms.quadriceps_l"],
                     "foot_l": ["contact.force.foot_l", "balance.cop.x"], "upper_arm_l": ["bp.systolic"]}


def human_simplified_skeleton(at: str | None = None) -> Body:
    comps = [component(c, "segment", c.replace("_", " "), concept_layout={"x": x, "y": y}, concept_only=True) for c, (x, y) in _HUMAN_LAYOUT.items()]
    rels = [relation(j, a, b, "joint", directed=False) for j, a, b in _HUMAN_JOINTS]
    targets = [target(f"tgt.{j}", j, [v], anatomical_ref=j) for j, v in _JOINT_VARIABLES.items()] + [target(f"tgt.{c}", c, vs, anatomical_ref=c) for c, vs in _REGION_VARIABLES.items()]
    return new_body("body.human-simplified-skeleton", "Human, simplified skeleton (a preset)", "human", components=comps, relations=rels, targets=targets, at=at,
                    boundaries=[boundary("bd.skin", [c["id"] for c in comps], "the body as one declared boundary (the skin)", "declared")],
                    meta={"preset": "human-simplified-skeleton/1", "concept_only": True, "note": "one preset among others; the layout is a drawing, not a measurement; no anatomical claim is made"})


def distributed_array(n: int = 6, at: str | None = None) -> Body:
    comps = [component(f"node_{i}", "node", f"node {i}") for i in range(n)]
    rels = [relation(f"link_{i}_{j}", f"node_{i}", f"node_{j}", "coupling") for i in range(n) for j in range(i + 1, n) if (j - i) in (1, n - 1)]
    return new_body("body.distributed-array", f"Distributed array of {n} nodes (a preset)", "distributed", components=comps, relations=rels, at=at,
                    boundaries=[boundary("bd.observer", [c["id"] for c in comps[: n // 2]], "what one observer's reach covers (observer-dependent)", "observer", "observer-A")],
                    meta={"preset": "distributed-array/1", "note": "no skeleton, no fixed joints; relations are couplings"})


def articulated_artificial(at: str | None = None) -> Body:
    comps = [component("base", "link"), component("link_1", "link"), component("link_2", "link"), component("link_3", "link"), component("gripper", "tool"), component("encoder_1", "sensor")]
    rels = [relation("j1", "base", "link_1", "joint", directed=True), relation("j2", "link_1", "link_2", "joint", directed=True), relation("j3", "link_2", "link_3", "joint", directed=True),
            relation("tool", "link_3", "gripper", "mount", directed=True), relation("enc", "encoder_1", "link_1", "signal", directed=True)]
    return new_body("body.articulated-artificial", "Articulated artificial arm (a preset)", "artificial", components=comps, relations=rels, at=at, meta={"preset": "articulated-artificial/1"})


def radial_non_human(arms: int = 5, at: str | None = None) -> Body:
    comps = [component("hub", "core")] + [component(f"arm_{i}", "limb", f"limb {i}") for i in range(arms)]
    rels = [relation(f"attach_{i}", "hub", f"arm_{i}", "attachment") for i in range(arms)]
    return new_body("body.radial-non-human", f"Radial body with {arms} limbs (a preset)", "non-human", components=comps, relations=rels, at=at,
                    boundaries=[boundary("bd.body", [c["id"] for c in comps], "declared boundary")], meta={"preset": "radial-non-human/1", "note": "no bilateral symmetry, no spine, no fixed number of limbs"})


PRESETS: dict[str, Callable[..., Body]] = {"human-simplified-skeleton": human_simplified_skeleton, "distributed-array": distributed_array, "articulated-artificial": articulated_artificial, "radial-non-human": radial_non_human}
