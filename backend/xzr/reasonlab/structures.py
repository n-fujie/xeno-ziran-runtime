"""Qualitatively distinct reasoning structures (neutral support specifications) and the structural variants
compared in the resolution-escalation experiments.

A structure is a neutral specification: items (tokens, effects, base level, self-standing flag, cluster),
requirements (sources → target, carry | enable), conflicts. Effects bind items to world regions (set names) with
magnitudes fixed by the coupling level. Nothing here depends on how the items are named or read.

Variants (letters as in docs/RESOLUTION_ESCALATION.md):
    A  none                       no reasoning layer
    B  vocabulary                 the reference structure expressed in the vocabulary-bearing representation
                                  (practice/graph.py), for the vocabulary control only
    C  two_status                 reference: two-level support graph, greatest fixpoint
    D  one_status                 single level (conflicts resolved before propagation)
    E  no_eligibility             backed only (no eligibility tracking)
    F  least_fixpoint             two-level, least fixpoint
    G  sticky_conflicts           reference + defeats persist across evaluations while the defeater is usable
    H  no_records                 no dependency records: requirements dropped, every item stands on its own level
    I  local_records              only requirements inside a cluster are kept
    J  persistent_records         reference, but records are immune to decay, fragmentation and loss
    K  mixed_rules                each cluster evaluated with its own rule
"""

from __future__ import annotations

import copy
import random
from collections import defaultdict
from typing import Any

import numpy as np

from ..practice.support import SupportGraph
from .mixed import MixedSupport

STRUCTURES = ("shallow_acyclic", "deep_chain", "strongly_cyclic", "multi_cycles", "sparse_conflicts",
              "dense_conflicts", "unsupported_addressable", "competing_clusters", "local_external_memory",
              "distributed_external_memory", "record_fragmentation", "record_loss_reconstruction",
              "mixed_fixpoint_regions", "multiple_clusters", "partially_incompatible_rules")
SIZES = (9, 32, 128, 512, 2048)
VARIANTS = ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K")
VARIANT_NAMES = {"A": "none", "B": "vocabulary", "C": "two_status", "D": "one_status", "E": "no_eligibility",
                 "F": "least_fixpoint", "G": "sticky_conflicts", "H": "no_records", "I": "local_records",
                 "J": "persistent_records", "K": "mixed_rules"}

# operational magnitude of one binding at full level, per coupling
COUPLING: dict[str, dict[str, Any]] = {
    "weak": {"threshold": 0.05, "gate": 0.9, "memory": (0.92, 0.05), "freeze_scale": "L", "mutation": 0.0002},
    "medium": {"threshold": 0.2, "gate": 0.6, "memory": (0.96, 0.15), "freeze_scale": "Q", "mutation": 0.001},
    "strong": {"threshold": 0.5, "gate": 0.2, "memory": (0.99, 0.35), "freeze_scale": "Z", "mutation": 0.005},
}
OPS = ("scale_threshold", "gate", "memory_condition", "freeze", "mutation")
OP_P = (0.4, 0.25, 0.15, 0.1, 0.1)


def _effect(rng: random.Random, region: int, coupling: str, n_sub: dict[str, int]) -> dict:
    c = COUPLING[coupling]
    op = rng.choices(OPS, OP_P)[0]
    z = f"Z{region}"
    if op == "scale_threshold":
        return {"op": op, "target": z, "factor": round(1 + c["threshold"] * rng.choice((-1, 1)), 4)}
    if op == "gate":
        return {"op": op, "target": f"BZ{region}", "factor": c["gate"]}
    if op == "memory_condition":
        return {"op": op, "target": z, "decay": c["memory"][0], "coupling": c["memory"][1]}
    if op == "freeze":  # eligibility: a sub-region whose size grows with coupling
        s = c["freeze_scale"]
        if s == "Z":
            return {"op": op, "target": z}
        k = n_sub[s]
        return {"op": op, "target": f"{s}{region * k + rng.randrange(k)}"}
    return {"op": op, "target": z, "factor": c["mutation"]}


def generate(kind: str, size: int, seed: int, coupling: str = "medium", regions: int = 32,
             clusters: int | None = None) -> dict:
    """Neutral specification of one structure. ``regions`` meso regions Z0..Z{regions-1} exist in the world;
    cluster c binds to regions r with r % n_clusters == c."""
    rng = random.Random(seed * 7919 + size * 31 + STRUCTURES.index(kind))
    multi = kind in ("competing_clusters", "mixed_fixpoint_regions", "multiple_clusters", "partially_incompatible_rules")
    nc = clusters or (min(4, max(2, size // 8)) if multi else 1)
    n_sub = {"L": 16, "Q": 4}  # sub-regions per meso region (512 = 32·16, 128 = 32·4)
    ids = [f"i{k}" for k in range(size)]
    cl = {i: (k * nc // size) for k, i in enumerate(ids)}
    regs = defaultdict(list)
    for r in range(regions):
        regs[r % nc].append(r)
    tokens = [f"t{k}" for k in range(8)]
    items = {}
    for i in ids:
        eff = [_effect(rng, rng.choice(regs[cl[i]]), coupling, n_sub)] if rng.random() < 0.75 else []
        items[i] = {"id": i, "tokens": rng.sample(tokens, rng.randint(0, 2)), "effects": eff, "base_level": 0.0,
                    "self_standing": False, "cluster": cl[i]}
    reqs: list[dict] = []
    conflicts: list[list[str]] = []

    def root(i: str, lo: float = 0.5) -> None:
        items[i]["self_standing"] = True
        items[i]["base_level"] = round(rng.uniform(lo, 1.0), 3)

    def req(target: str, sources: list[str], mode: str = "carry") -> None:
        if target not in sources:
            reqs.append({"sources": sources, "target": target, "mode": mode})

    def dag(members: list[str], root_share: float, max_par: int = 2) -> None:
        for k, i in enumerate(members):
            if k < max(1, int(len(members) * root_share)) or k == 0:
                root(i)
            else:
                par = rng.sample(members[:k], min(k, rng.randint(1, max_par)))
                req(i, par, "carry" if rng.random() < 0.85 else "enable")

    def conflict(a: str, b: str) -> None:
        if a != b and [a, b] not in conflicts and [b, a] not in conflicts:
            conflicts.append([a, b])

    def rand_conflicts(members: list[str], count: int) -> None:
        for _ in range(count):
            conflict(*rng.sample(members, 2))

    by_cluster = defaultdict(list)
    for i in ids:
        by_cluster[cl[i]].append(i)
    if kind in ("shallow_acyclic", "local_external_memory", "distributed_external_memory", "record_fragmentation",
                "record_loss_reconstruction", "multiple_clusters"):
        for mem in by_cluster.values():
            roots = mem[: max(1, int(len(mem) * 0.4))]
            for i in roots:
                root(i)
            for i in mem[len(roots):]:
                req(i, rng.sample(roots, min(len(roots), rng.randint(1, 2))))
            rand_conflicts(mem, max(1, len(mem) // 20))
    elif kind == "deep_chain":
        half = max(2, size // 2)
        for chain in (ids[:half], ids[half:]):
            if not chain:
                continue
            root(chain[0], 0.8)
            for a, b in zip(chain[:-1], chain[1:], strict=True):
                req(b, [a])
            rival = chain[len(chain) // 2]
            conflict(rival, chain[0])
    elif kind in ("strongly_cyclic", "multi_cycles"):
        if kind == "strongly_cyclic":
            rings = [ids]
        else:
            rings, k = [], 0
            while k < size:
                L = rng.randint(4, 8)
                rings.append(ids[k:k + L])
                k += max(2, L - 2)  # overlapping rings share members
        for ring in rings:
            for a, b in zip(ring, ring[1:] + ring[:1], strict=True):
                req(b, [a], "carry" if rng.random() < 0.8 else "enable")
        for i in rng.sample(ids, max(1, size // 10)):
            items[i]["base_level"] = round(rng.uniform(0.3, 1.0), 3)  # backed, not self-standing
        for i in rng.sample(ids, max(1, size // 12)):
            root(i)
        rand_conflicts(ids, max(1, size // 16))
    elif kind in ("sparse_conflicts", "dense_conflicts"):
        dag(ids, 0.25)
        rand_conflicts(ids, max(1, int(size * (0.1 if kind == "sparse_conflicts" else 1.5))))
    elif kind == "unsupported_addressable":
        k1, k2 = int(size * 0.3), int(size * 0.8)
        for i in ids[:max(1, k1)]:
            root(i)
        for i in ids[max(1, k1):k2]:  # backed but without any requirement: addressable, not supported
            items[i]["base_level"] = round(rng.uniform(0.3, 1.0), 3)
        for i in ids[k2:]:
            req(i, rng.sample(ids[:max(1, k1)], 1))
        rand_conflicts(ids, max(1, size // 10))
    elif kind in ("competing_clusters", "partially_incompatible_rules"):
        conclusions = []
        for mem in by_cluster.values():
            dag(mem, 0.3)
            conclusions.append(mem[-1])
            rand_conflicts(mem, max(1, len(mem) // 20))
        for ka in range(len(conclusions)):
            for kb in range(ka + 1, len(conclusions)):
                conflict(conclusions[ka], conclusions[kb])
        if kind == "partially_incompatible_rules":
            mems = list(by_cluster.values())
            for _ in range(max(1, size // 8)):
                ka, kb = rng.sample(range(len(mems)), 2)
                conflict(rng.choice(mems[ka]), rng.choice(mems[kb]))
            for _ in range(max(1, size // 16)):  # some cross-cluster records
                ka, kb = rng.sample(range(len(mems)), 2)
                req(rng.choice(mems[ka]), [rng.choice(mems[kb])])
    elif kind == "mixed_fixpoint_regions":
        for c, mem in by_cluster.items():
            if c % 2 == 0:  # cyclic region
                for a, b in zip(mem, mem[1:] + mem[:1], strict=True):
                    req(b, [a])
                for i in rng.sample(mem, max(1, len(mem) // 4)):
                    items[i]["base_level"] = round(rng.uniform(0.3, 1.0), 3)
                root(mem[0])
            else:
                dag(mem, 0.35)
            rand_conflicts(mem, max(1, len(mem) // 16))
    else:
        raise ValueError(kind)
    spec = {"kind": kind, "size": size, "coupling": coupling, "clusters": nc, "tokens": tokens,
            "items": list(items.values()), "requirements": reqs, "conflicts": conflicts, "retracted": [],
            "blocked_tokens": [], "mode": "two_level", "fixpoint": "greatest"}
    spec["dynamic"] = {"record_fragmentation": kind == "record_fragmentation",
                       "record_loss": kind == "record_loss_reconstruction",
                       "memory_grounding": "local" if kind == "local_external_memory" else
                       "distributed" if kind == "distributed_external_memory" else None}
    return spec


# ------------------------------------------------------------------------------------------------ variants
def _graph(spec: dict, **over) -> SupportGraph:
    s = {**spec, **over}
    return SupportGraph.from_spec(s)


def build_variant(letter: str, spec: dict):
    """Reasoning representation for a variant letter (None for A)."""
    if letter == "A":
        return None
    if letter == "B":
        from ..practice.graph import Practice
        from .representations import untranslate
        return Practice.from_json(untranslate(spec))
    if letter in ("C", "J"):
        g = _graph(spec, mode="two_level", fixpoint="greatest")
        if letter == "J":
            g.persistent = True  # type: ignore[attr-defined]
        return g
    if letter == "D":
        return _graph(spec, mode="single_level")
    if letter == "E":
        return _graph(spec, mode="backed_only")
    if letter == "F":
        return _graph(spec, mode="two_level", fixpoint="least")
    if letter == "G":
        g = _graph(spec, mode="two_level", fixpoint="greatest")
        g.sticky = True
        return g
    if letter == "H":
        s = copy.deepcopy(spec)
        s["requirements"] = []
        for it in s["items"]:
            it["self_standing"] = True
        return _graph(s, mode="two_level", fixpoint="greatest")
    if letter == "I":
        cl = {it["id"]: it["cluster"] for it in spec["items"]}
        s = copy.deepcopy(spec)
        s["requirements"] = [r for r in s["requirements"] if all(cl[x] == cl[r["target"]] for x in r["sources"])]
        return _graph(s, mode="two_level", fixpoint="greatest")
    if letter == "K":
        cl = {it["id"]: it["cluster"] for it in spec["items"]}
        order = ("greatest", "single", "least", "backed")
        rules = {c: order[c % 4] for c in set(cl.values())}
        return MixedSupport(_graph(spec, mode="two_level", fixpoint="greatest"), cl, rules)
    raise ValueError(letter)


def revert_to_reference(rep) -> None:
    """Remove the structural difference of a variant in place (used by the reversibility test): after this the
    representation evaluates with the reference rule on its current record."""
    if isinstance(rep, MixedSupport):
        for c in rep.rules:
            rep.rules[c] = "greatest"
    elif isinstance(rep, SupportGraph):
        rep.mode, rep.fixpoint, rep.sticky = "two_level", "greatest", False
        rep.defeats = {}


# ------------------------------------------------------------------------------------------------ descriptors
def _sccs(nodes: list[str], edges: dict[str, set[str]]) -> list[list[str]]:
    index, low, stack, on, out, counter = {}, {}, [], set(), [], [0]

    def strong(v: str) -> None:
        work = [(v, iter(sorted(edges.get(v, ()))))]
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        while work:
            u, it = work[-1]
            nxt = next(it, None)
            if nxt is not None:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter[0]
                    counter[0] += 1
                    stack.append(nxt)
                    on.add(nxt)
                    work.append((nxt, iter(sorted(edges.get(nxt, ())))))
                elif nxt in on:
                    low[u] = min(low[u], index[nxt])
            else:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[u])
                if low[u] == index[u]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on.discard(w)
                        comp.append(w)
                        if w == u:
                            break
                    out.append(comp)

    for v in nodes:
        if v not in index:
            strong(v)
    return out


def descriptors(spec: dict, edits: int = 20, seed: int = 0) -> dict:
    ids = [it["id"] for it in spec["items"]]
    n = len(ids)
    cl = {it["id"]: it["cluster"] for it in spec["items"]}
    edges: dict[str, set[str]] = defaultdict(set)
    indeg: dict[str, int] = defaultdict(int)
    outdeg: dict[str, int] = defaultdict(int)
    alt: dict[str, int] = defaultdict(int)
    for r in spec["requirements"]:
        alt[r["target"]] += 1
        for s in r["sources"]:
            edges[s].add(r["target"])
            outdeg[s] += 1
            indeg[r["target"]] += 1
    comps = _sccs(ids, edges)
    cyclic = [c for c in comps if len(c) > 1]
    # longest path over the condensation
    comp_of = {v: k for k, c in enumerate(comps) for v in c}
    cedges: dict[int, set[int]] = defaultdict(set)
    for u, vs in edges.items():
        for v in vs:
            if comp_of[u] != comp_of[v]:
                cedges[comp_of[u]].add(comp_of[v])
    depth: dict[int, int] = {}
    for k in range(len(comps)):  # Tarjan emits components in reverse topological order
        depth[k] = 1 + max((depth[j] for j in cedges.get(k, ()) if j in depth), default=0)
    deg = np.array([indeg[i] + outdeg[i] for i in ids], dtype=float)
    reqs = spec["requirements"]
    cross = sum(1 for r in reqs if any(cl[s] != cl[r["target"]] for s in r["sources"]))
    cross_c = sum(1 for a, b in spec["conflicts"] if cl[a] != cl[b])
    derived = [i for i in ids if alt[i] > 0]
    # fixpoint sensitivity: share of items whose eligibility differs between least and greatest fixpoint,
    # on the structure and after random retractions / level changes
    rng = random.Random(seed)
    diffs, total = 0, 0
    s0 = copy.deepcopy(spec)
    for k in range(edits + 1):
        if k:
            i = rng.choice(ids)
            if rng.random() < 0.5:
                s0["retracted"] = sorted(set(s0["retracted"]) | {i})
            else:
                next(it for it in s0["items"] if it["id"] == i)["base_level"] = round(rng.random(), 3)
        eg = SupportGraph.from_spec({**s0, "fixpoint": "greatest"}).evaluate().eligible
        el = SupportGraph.from_spec({**s0, "fixpoint": "least"}).evaluate().eligible
        diffs += sum(eg[i] != el[i] for i in ids)
        total += n
    return {
        "items": n, "requirements": len(reqs), "conflicts": len(spec["conflicts"]),
        "dependency_depth": int(max(depth.values(), default=0)),
        "cycle_count": len(cyclic), "items_in_cycles": sum(len(c) for c in cyclic),
        "support_branching": round(float(np.mean([outdeg[i] for i in ids if outdeg[i] > 0])) if outdeg else 0.0, 3),
        "incompatibility_density": round(len(spec["conflicts"]) / max(n * (n - 1) / 2, 1), 5),
        "dependency_centralization": round(float(deg.max() / deg.sum()) if deg.sum() else 0.0, 4),
        "record_locality": round(1 - cross / len(reqs), 4) if reqs else 1.0,
        "support_redundancy": round(float(np.mean([alt[i] for i in derived])) if derived else 0.0, 3),
        "fixpoint_sensitivity": round(diffs / max(total, 1), 5),
        "cluster_count": int(spec.get("clusters", 1)),
        "inter_cluster_coupling": round((cross + cross_c) / max(len(reqs) + len(spec["conflicts"]), 1), 4),
        "unsupported_backed": sum(1 for it in spec["items"] if it["base_level"] > 0 and not it["self_standing"]
                                  and alt[it["id"]] == 0),
        # effect-bearing items acting under the reference rule (two-level, greatest fixpoint) before any revision;
        # 0 means the structure defeats itself (e.g. equal-level conflicts on a support ring remove its roots)
        "active_bindings_reference": sum(1 for _i, _e, s, _w in _graph(spec, mode="two_level", fixpoint="greatest")
                                         .active_bindings() if s > 0),
        "bindings": sum(len(it["effects"]) for it in spec["items"]),
    }
