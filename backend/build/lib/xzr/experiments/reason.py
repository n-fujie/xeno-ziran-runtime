"""Reasoning-layer non-redundancy experiments (suite ``philosophical_nonredundancy``).

Question: in which configurations does the reasoning / scorekeeping layer produce an operational difference that
the base runtime cannot reproduce at the same descriptive resolution, and does the commitment/entitlement
vocabulary add anything beyond a representation that does not use it?

Representations compared in every scenario (same world, seed, edits, run length):
  none                        base operational runtime (no reasoning layer)
  scorekeeping                commitment + entitlement scorekeeping
  scorekeeping_no_entitlement reduced reasoning: every commitment counts as entitled
  support_single              alternate representation with one status
  support                     alternate representation, two levels, least fixpoint
  support_greatest            alternate representation, two levels, greatest fixpoint
plus ``replay`` (the base runtime replaying scorekeeping's recorded intervention schedule) and a noise replicate
(scorekeeping under a different engine random stream).

Criteria (Part C) are computed separately and each is marked as *operational* (about world transitions) or
*bookkeeping* (about the reasoning records themselves, true by construction for any representation that keeps
dependency records).
"""

from __future__ import annotations

import copy
import json
import os
import random
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from ..compare.trajectory import Recording, compare_recordings
from ..reasonlab.loop import LoopConfig, ReasonLoop, _overlay_key
from ..reasonlab.representations import REPRESENTATIONS, Edit, apply_edit, build, effective
from ..runtime.intervention import to_dict
from ..scenario.build import World, build_world
from ..scenario.io import load_sample
from ..shapes.detector import ShapeDetector

SCENARIO = "reason-lab"
HORIZON = 400
EDIT_AT = 150
PROBE_AT = 250
SEED = 5
NOISE_SEED = 1005
ABS_TOL = 0.02

ENABLING = [
    # calibrated to the world's own record level: undriven memory in R settles at ~0.9–1.1 (reasoning's own memory
    # condition raises it to ~6, so a threshold above the undriven level would make enabling depend on reasoning)
    {"name": "persistent external memory", "metric": "memory", "target": "R", "op": ">=", "value": 0.7},
    {"name": "stable addressability", "metric": "stability", "target": "R", "op": ">=", "value": 0.95},
    {"name": "low mutation rate", "metric": "mutation", "target": "", "op": "<=", "value": 8.0},
]
GROUNDINGS = [
    {"claim": "K9", "when": {"metric": "activity", "target": "B", "op": "<", "value": 0.041}, "window": 2, "effect": "assert",
     "level": 1.0},
    {"claim": "K9", "when": {"metric": "activity", "target": "B", "op": ">", "value": 0.050}, "window": 2, "effect": "retract"},
    {"claim": "K1", "when": {"metric": "flow", "target": "BA", "op": ">", "value": 0.026}, "window": 3, "effect": "retract"},
    {"claim": "K1", "when": {"metric": "flow", "target": "BA", "op": "<", "value": 0.010}, "window": 3, "effect": "assert",
     "level": 1.0},
]
COMPARED = ("none", "scorekeeping", "scorekeeping_no_entitlement", "support_single", "support", "support_greatest")
CRITS = ("reachable_structure", "branching", "closure", "recurrent_loops", "fragmentation", "concentration",
         "persistence", "amplification_regime", "path_dependence")


def lab() -> tuple:
    sc = load_sample(SCENARIO)
    return sc, sc.practice


def new_world(engine_seed: int = SEED) -> World:
    sc, _ = lab()
    w = build_world(sc)
    w.engine.rng = np.random.default_rng(engine_seed)
    return w


def make_loop(representation: str, engine_seed: int = SEED, practice: dict | None = None, **kw) -> ReasonLoop:
    sc, pj = lab()
    w = new_world(engine_seed)
    cfg = LoopConfig(representation=representation, enabling=kw.pop("enabling", ENABLING),
                     groundings=kw.pop("groundings", GROUNDINGS), **kw)
    return ReasonLoop(w, copy.deepcopy(practice or pj), cfg)


def record(loop: ReasonLoop, steps: int) -> Recording:
    det = ShapeDetector(loop.world.hierarchy, graph_every=10)
    rec = Recording(n=loop.world.state.n, snapshot_every=30)
    for _ in range(steps):
        d = loop.step()
        r = det.observe(d, loop.world.state)
        rec.record(d, loop.world.state)
        if "graph" in r:
            rec.signatures.append(list(det.signatures))
    rec.attach_detector(det)
    from .runs import array_hashes
    rec.hashes = array_hashes(loop.world.state)
    return rec


def _schedule_json(loop: ReasonLoop) -> list:
    return [(t, [to_dict(i) for i in items]) for t, items in loop.overlay_changes]


# ------------------------------------------------------------------------------------------------ scenarios (Part F)
def _p2_practice() -> dict:
    """Scenario 10: same claims and compiled operational effects, different scorekeeping structure:
    the derived claims are asserted directly (no inferential dependencies) at their derived strengths."""
    _, pj = lab()
    p = copy.deepcopy(pj)
    for c in p["claims"]:
        if c["id"] in ("K3", "K6", "K8"):
            c["commitment"] = {"K3": 1.0, "K6": 0.9, "K8": 0.9}[c["id"]]
            c["default_entitled"] = True
    p["dependencies"] = []
    return p


SCENARIOS: dict[str, dict] = {
    "1_remove_concept_human": {"edits": [(EDIT_AT, Edit("remove_token", a="human"))]},
    "2_remove_concept_responsibility": {"edits": [(EDIT_AT, Edit("remove_token", a="responsibility"))]},
    "3_withdraw_K2": {"edits": [(EDIT_AT, Edit("retract", a="K2"))]},
    "4_remove_incompatibility": {"edits": [(EDIT_AT, Edit("drop_conflict", a="K4", b="K9"))]},
    # the reduction applies to both vocabularies: scorekeeping → no entitlement; support graph → no eligibility check
    "5_remove_entitlement_tracking": {"edits": [], "representation_override": {
        "scorekeeping": "scorekeeping_no_entitlement", "support": "support_backed_only",
        "support_greatest": "support_backed_only"}},
    "6_remove_external_memory": {"world_events": [{"t": EDIT_AT, "items": [
        {"kind": "memory_condition", "target": "R", "decay": 0.3}]}]},
    "7_high_mutation": {"world_events": [{"t": EDIT_AT, "items": [{"kind": "mutation", "target": "R", "rate": 0.01}]}]},
    "8_remove_address_persistence": {"world_events": [{"t": EDIT_AT, "items": [
        {"kind": "mutation", "target": "A", "rate": 0.01}, {"kind": "mutation", "target": "B", "rate": 0.01},
        {"kind": "mutation", "target": "R", "rate": 0.004}]}]},
    "9_change_dependency_graph": {"edits": [(EDIT_AT, Edit("drop_requirement", a="K3", b="K2")),
                                            (EDIT_AT, Edit("add_requirement", a="K3", sources=("K1",))),
                                            (PROBE_AT, Edit("remove_token", a="human"))],
                                  "reference_edits": [(PROBE_AT, Edit("remove_token", a="human"))]},
    "10_alter_scorekeeping_structure": {"practice": "p2", "edits": []},
}


def _scenario_job(args: tuple) -> tuple:
    name, rep, seed, variant = args
    spec = SCENARIOS[name]
    edits = spec.get("edits", []) if variant == "edit" else spec.get("reference_edits", [])
    kind = rep
    if variant == "edit" and spec.get("representation_override"):
        kind = spec["representation_override"].get(rep, rep)
    practice = _p2_practice() if (spec.get("practice") == "p2" and variant == "edit") else None
    world_events = spec.get("world_events", []) if variant == "edit" else []
    loop = make_loop(kind, seed, practice=practice, edits=list(edits), world_events=list(world_events))
    rec = record(loop, HORIZON)
    phases = [r["phase"] for r in loop.timeline]
    return args, {"rec": rec, "schedule": _schedule_json(loop), "revisions": loop.revisions,
                  "overlay_changes": len(loop.overlay_changes), "phases": phases,
                  "collapsed_share": phases.count("collapsed") / max(len(phases), 1),
                  "fingerprint": loop.world.engine.fingerprint()}


def _replay_job(args: tuple) -> tuple:
    name, seed, schedule = args
    from ..runtime.intervention import from_dict
    loop = make_loop("replay", seed, replay=[(t, [from_dict(x) for x in items]) for t, items in schedule])
    rec = record(loop, HORIZON)
    return args[:2], {"rec": rec, "fingerprint": loop.world.engine.fingerprint()}


def _dist(a: Recording, b: Recording) -> dict:
    c = compare_recordings(a, b)
    return {"event_sequence": c["event_sequence"], "graph_edit": c["graph_edit"], "difference_w1": c["difference_w1"],
            "signature": c["signature"], "first_divergence": c["first_divergence"],
            **{f"criterion:{k}": c["criteria"][k] for k in CRITS}}


def _exceeds(d: dict, noise: dict) -> list[str]:
    return [k for k, v in d.items() if k != "first_divergence" and v > 2 * noise[k] + ABS_TOL]


def scenario_suite(procs: int = 7) -> dict:
    jobs = []
    for name in SCENARIOS:
        for rep in COMPARED:
            jobs.append((name, rep, SEED, "edit"))
        jobs.append((name, "scorekeeping", SEED, "reference"))
        jobs.append((name, "scorekeeping", NOISE_SEED, "edit"))
    with ProcessPoolExecutor(procs) as ex:
        res = dict(ex.map(_scenario_job, jobs))
    replays = [(name, SEED, res[(name, "scorekeeping", SEED, "edit")]["schedule"]) for name in SCENARIOS]
    with ProcessPoolExecutor(procs) as ex:
        rep_res = dict(ex.map(_replay_job, replays))
    out = {}
    for name in SCENARIOS:
        sk = res[(name, "scorekeeping", SEED, "edit")]
        noise = _dist(sk["rec"], res[(name, "scorekeeping", NOISE_SEED, "edit")]["rec"])
        rows = {}
        for rep in COMPARED:
            r = res[(name, rep, SEED, "edit")]
            identical = r["fingerprint"] == sk["fingerprint"] and r["schedule"] == sk["schedule"]
            d = _dist(sk["rec"], r["rec"]) if rep != "scorekeeping" else {k: 0.0 for k in noise}
            rows[rep] = {"identical_to_scorekeeping": identical, "exceeds": [] if identical else _exceeds(d, noise),
                         "distance": d, "overlay_changes": r["overlay_changes"], "revisions": r["revisions"],
                         "collapsed_share": round(r["collapsed_share"], 3)}
        ref = res[(name, "scorekeeping", SEED, "reference")]
        edit_d = _dist(ref["rec"], sk["rec"])
        replay_identical = rep_res[(name, SEED)]["fingerprint"] == sk["fingerprint"]
        vocab_identical = rows["support_greatest"]["identical_to_scorekeeping"]
        out[name] = {
            "representations": rows, "noise": noise,
            "edit_effect": {"distance": edit_d, "exceeds": _exceeds(edit_d, noise),
                            "identical": ref["fingerprint"] == sk["fingerprint"]},
            "replay_reproduces_scorekeeping_exactly": replay_identical,
            "vocabulary_nonredundant": not vocab_identical,
            "two_status_nonredundant": not rows["support_single"]["identical_to_scorekeeping"],
            "entitlement_nonredundant": not rows["scorekeeping_no_entitlement"]["identical_to_scorekeeping"],
            "fixpoint_choice_matters": not rows["support"]["identical_to_scorekeeping"],
            "reasoning_vs_base_exceeds": rows["none"]["exceeds"],
            "statement": _statement(name, vocab_identical, rows, replay_identical, edit_d, noise, ref, sk),
        }
    return out


def _statement(name, vocab_identical, rows, replay_identical, edit_d, noise, ref, sk) -> str:
    parts = []
    parts.append("The commitment/entitlement vocabulary produced NO non-redundant operational difference: the "
                 "terminology-free support graph (greatest fixpoint) gave a bit-identical world trajectory and "
                 "intervention schedule." if vocab_identical else
                 "The commitment/entitlement vocabulary differed from the terminology-free support graph "
                 "(greatest fixpoint) — see distances.")
    parts.append("The two-status structure (commitment vs entitlement) mattered here (single-status alternative "
                 "diverged)." if not rows["support_single"]["identical_to_scorekeeping"] else
                 "The two-status structure made no operational difference here (single-status alternative identical).")
    parts.append("The reasoning-enabled trajectory is exactly reproducible by the base runtime replaying the "
                 "recorded operational intervention schedule." if replay_identical else "Replay did NOT reproduce it.")
    eff = _exceeds(edit_d, noise)
    parts.append(("The edit changed the world beyond the noise floor on: " + ", ".join(eff) + ".") if eff else
                 ("The edit changed nothing (bit-identical trajectory)." if ref["fingerprint"] == sk["fingerprint"]
                  else "The edit's effect on the world stayed within the noise floor."))
    return " ".join(parts)


# ------------------------------------------------------------------------------------------------ representation equivalence
def _rand_graph(rng: random.Random) -> dict:
    n = rng.randint(3, 9)
    ids = [f"C{i}" for i in range(n)]
    toks = ["t0", "t1", "t2", "t3"]
    claims = [{"id": c, "text": "", "uses": rng.sample(toks, rng.randint(0, 2)),
               "bindings": [{"op": "scale_threshold", "target": "X", "factor": 1.2}],
               "default_entitled": rng.random() < 0.6, "commitment": rng.choice([0, 0, 0.4, 0.7, 1.0])} for c in ids]
    deps = []
    for _ in range(rng.randint(0, n)):
        concl = rng.choice(ids)
        prem = rng.sample([i for i in ids if i != concl], rng.randint(1, min(2, n - 1)))
        deps.append({"premises": prem, "conclusion": concl, "kind": "committive" if rng.random() < 0.8 else "permissive"})
    return {"concepts": toks, "claims": claims, "dependencies": deps,
            "incompatibilities": [rng.sample(ids, 2) for _ in range(rng.randint(0, 2))]}


def _rand_edit(rng: random.Random, pj: dict) -> Edit:
    ids = [c["id"] for c in pj["claims"]]
    op = rng.choice(["remove_token", "retract", "set_level", "drop_conflict"])
    if op == "remove_token":
        return Edit(op, a=rng.choice(pj["concepts"]))
    if op == "set_level":
        return Edit(op, a=rng.choice(ids), value=rng.choice([0.3, 0.6, 1.0]))
    if op == "drop_conflict" and pj["incompatibilities"]:
        a, b = rng.choice(pj["incompatibilities"])
        return Edit(op, a=a, b=b)
    return Edit("retract", a=rng.choice(ids))


def _cyclic(pj: dict, rep) -> set[str]:
    """Claims on a dependency cycle."""
    succ: dict[str, set[str]] = {}
    for d in pj["dependencies"]:
        for p in d["premises"]:
            succ.setdefault(p, set()).add(d["conclusion"])
    out = set()
    for start in succ:
        stack, seen = list(succ.get(start, ())), set()
        while stack:
            x = stack.pop()
            if x == start:
                out.add(start)
                break
            if x in seen:
                continue
            seen.add(x)
            stack.extend(succ.get(x, ()))
    return out


def _downstream(pj: dict, roots: set[str]) -> set[str]:
    """Claims reachable from ``roots`` along dependency edges (premise → conclusion), including the roots."""
    succ: dict[str, set[str]] = {}
    for d in pj["dependencies"]:
        for p in d["premises"]:
            succ.setdefault(p, set()).add(d["conclusion"])
    out, stack = set(roots), list(roots)
    while stack:
        for y in succ.get(stack.pop(), ()):
            if y not in out:
                out.add(y)
                stack.append(y)
    return out


CAUSES = {
    "cycle": "claim on or downstream of a dependency cycle (least vs greatest fixpoint)",
    "unentitled_support": "claim downstream of a committed-but-not-entitled claim (support through commitment vs through "
                          "eligibility)",
    "conflict_scope": "claim in, or downstream of, an incompatibility whose other member is committed but not finally "
                      "entitled (which items conflicts are resolved among, and whether a defeat is undone when the "
                      "defeating claim later loses entitlement)",

    "support": "fixpoint choice: every differing claim is on or downstream of a dependency cycle (least vs greatest "
               "fixpoint of eligibility)",
    "support_single": "two-status structure: every differing claim is downstream of a committed-but-not-entitled claim "
                      "(support flows through commitment in two-status scorekeeping, only through eligibility in the "
                      "single-status graph), or on/downstream of a cycle",
    "scorekeeping_no_entitlement": "entitlement tracking: every differing claim is a committed-but-not-entitled claim or "
                                   "downstream of one",
    "support_backed_only": "entitlement/eligibility checking: same as above",
}


def representation_equivalence(graphs: int = 3000, edits: int = 4, seed: int = 1) -> dict:
    """Random claim graphs × random edit sequences; every representation vs scorekeeping (and the backed-only support
    graph vs scorekeeping without entitlement). Each disagreement is tested against its structural cause."""
    rng = random.Random(seed)
    pairs = {k: "scorekeeping" for k in REPRESENTATIONS if k not in ("scorekeeping", "support_backed_only")}
    pairs["support_backed_only"] = "scorekeeping_no_entitlement"
    stats: dict[str, dict[str, Any]] = {k: {"reference": ref, "disagreements": 0, "explained": 0,
                 "by_cause": {"cycle": 0, "unentitled_support": 0, "conflict_scope": 0}} for k, ref in pairs.items()}
    residual: dict[str, list] = {k: [] for k in stats}
    total = 0
    for _ in range(graphs):
        pj = _rand_graph(rng)
        reps = {k: build(k, pj) for k in REPRESENTATIONS}
        for _step in range(edits):
            total += 1
            cur = reps["scorekeeping"].to_json()
            sc = reps["scorekeeping"].score()
            unent = {i for i in sc.commitment if sc.commitment[i] > 0 and not sc.entitled[i]}
            cyc = _downstream(cur, _cyclic(cur, None))
            unsup = _downstream(cur, unent)
            conflict_roots = {b for a, b in cur["incompatibilities"] if a in unent} | \
                {a for a, b in cur["incompatibilities"] if b in unent}
            cscope = _downstream(cur, conflict_roots)
            cause_sets = {"cycle": cyc, "unentitled_support": unsup, "conflict_scope": cscope}
            for k, ref_name in pairs.items():
                e, ref = effective(reps[k]), effective(reps[ref_name])
                if e == ref:
                    continue
                stats[k]["disagreements"] += 1
                diff = {i for i in ref if ref[i] != e.get(i)}
                hit = [c for c, members in cause_sets.items() if diff & members]
                why = diff <= set().union(*cause_sets.values())
                for c in hit:
                    stats[k]["by_cause"][c] += 1
                stats[k]["explained"] += int(why)
                if not why and len(residual[k]) < 3:
                    residual[k].append({"state": cur, "differing": sorted(diff)})
            ed = _rand_edit(rng, pj)
            for r in reps.values():
                apply_edit(r, ed)
    return {"states": total, "vs_scorekeeping": stats, "causes": CAUSES, "residual_examples": residual}


# ------------------------------------------------------------------------------------------------ Part C criteria
def _loop_features(loop: ReasonLoop) -> tuple[list[float], list[float]]:
    p = loop.probe
    ops = [p.value("activity", "A"), p.value("activity", "B"), p.value("activity", "R"), p.value("flow", "BA"),
           p.value("flow", "BB"), p.value("memory", "R"), float(len(loop.overlay)),
           float(np.mean(loop.world.state.theta_mod)), float(np.mean(loop.world.state.gate))]
    eff = effective(loop.rep) if loop.rep is not None else {}
    reason = [eff.get(k, 0.0) for k in sorted(eff)] + [float(s) for s in loop._g_streak]
    return ops, reason


def _prediction_job(seed: int) -> list:
    loop = make_loop("scorekeeping", seed)
    rows = []
    for _ in range(HORIZON // loop.cfg.check_every):
        before_key = loop.key
        for _ in range(loop.cfg.check_every):
            loop.step()
        loop.probe.begin_check()
        ops, reason = _loop_features(loop)
        rows.append((loop.world.state.t, ops, reason, loop.key != before_key))
    return rows


def transition_prediction(procs: int = 7, seeds: tuple = tuple(range(20, 32))) -> dict:
    """Predict whether the operational intervention set changes during the next check window, and the next
    window's activity in A and B, from (i) current operational state, (ii) operational state + its history,
    (iii) operational state + the reasoning state. Ridge regression; train on 8 seeds, test on 4."""
    with ProcessPoolExecutor(procs) as ex:
        runs = list(ex.map(_prediction_job, seeds))

    def dataset(which: str, idx: list[int]):
        X, yc, ya = [], [], []
        for i in idx:
            r = runs[i]
            for k in range(3, len(r) - 1):
                ops = r[k][1]
                hist = r[k - 1][1] + r[k - 2][1]
                feats = {"ops": ops, "ops+history": ops + hist, "ops+reasoning": ops + r[k][2],
                         "ops+history+reasoning": ops + hist + r[k][2]}[which]
                X.append(feats)
                yc.append(float(r[k + 1][3]))
                ya.append(r[k + 1][1][0] + r[k + 1][1][1])
        return np.array(X), np.array(yc), np.array(ya)

    train, test = list(range(8)), list(range(8, len(seeds)))
    out = {}
    for which in ("ops", "ops+history", "ops+reasoning", "ops+history+reasoning"):
        Xtr, yctr, yatr = dataset(which, train)
        Xte, ycte, yate = dataset(which, test)
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
        A = np.c_[np.ones(len(Xtr)), (Xtr - mu) / sd]
        B = np.c_[np.ones(len(Xte)), (Xte - mu) / sd]
        lam = 1.0 * np.eye(A.shape[1])
        lam[0, 0] = 0
        res = {}
        for tag, ytr, yte in (("overlay_change", yctr, ycte), ("activity_AB", yatr, yate)):
            w = np.linalg.solve(A.T @ A + lam, A.T @ ytr)
            pred = B @ w
            if tag == "overlay_change":
                res[tag] = {"accuracy": float(np.mean((pred > 0.5) == (yte > 0.5))),
                            "brier": float(np.mean((np.clip(pred, 0, 1) - yte) ** 2)),
                            "base_rate": float(np.mean(yte))}
            else:
                res[tag] = {"r2": float(1 - np.sum((pred - yte) ** 2) / max(np.sum((yte - yte.mean()) ** 2), 1e-12))}
        out[which] = res
    return out


def intervention_precision() -> dict:
    """For each compiled operational modifier, the smallest side effect with which a single reasoning-level edit can
    remove exactly it, versus a direct operational edit (always zero side effects)."""
    _, pj = lab()
    loop = make_loop("scorekeeping", SEED)
    base = {_overlay_key([i]): i for i in loop._compiled(loop.rep)}
    edits = [Edit("remove_token", a=c) for c in pj["concepts"]] + [Edit("retract", a=c["id"]) for c in pj["claims"]]
    per_item: dict[str, int | None] = {}
    for key, item in base.items():
        best: int | None = None
        for e in edits:
            rep = build("scorekeeping", pj)
            apply_edit(rep, e)
            after = {_overlay_key([i]) for i in loop._compiled(rep)}
            if key in after:
                continue
            side = len(set(base) - after - {key}) + len(after - set(base))
            best = side if best is None else min(best, side)
        per_item[f"{len(per_item)}:{item.kind}:{len(getattr(item, 'nodes', getattr(item, 'edges', ())))}"] = best
    achievable = [v for v in per_item.values() if v is not None]
    return {"modifiers": len(base), "min_side_effects_per_modifier": per_item,
            "reasoning_edit_mean_side_effects": float(np.mean(achievable)) if achievable else None,
            "unreachable_by_single_reasoning_edit": sum(v is None for v in per_item.values()),
            "direct_operational_edit_side_effects": 0}


def dependency_tracing() -> dict:
    """Predict which operational modifiers change when a concept is removed or a claim retracted.
    Representations with dependency records predict from their own records; the operational-only representation
    (the list of modifiers) has no dependency information and can only predict 'nothing changes'."""
    _, pj = lab()
    loop = make_loop("scorekeeping", SEED)
    edits = [Edit("remove_token", a=c) for c in pj["concepts"]] + [Edit("retract", a=c["id"]) for c in pj["claims"]]
    base = {_overlay_key([i]) for i in loop._compiled(build("scorekeeping", pj))}
    scores: dict[str, dict[str, Any]] = {k: {"tp": 0, "fp": 0, "fn": 0}
                                         for k in ("scorekeeping", "support_greatest", "operational_only")}
    for e in edits:
        truth_rep = build("scorekeeping", pj)
        apply_edit(truth_rep, e)
        actual = base ^ {_overlay_key([i]) for i in loop._compiled(truth_rep)}
        for k in scores:
            if k == "operational_only":
                pred: set = set()
            else:
                r = build(k, pj)
                apply_edit(r, e)  # the representation's own dependency records answer the question
                pred = base ^ {_overlay_key([i]) for i in loop._compiled(r)}
            scores[k]["tp"] += len(pred & actual)
            scores[k]["fp"] += len(pred - actual)
            scores[k]["fn"] += len(actual - pred)
    for s in scores.values():
        s["recall"] = s["tp"] / max(s["tp"] + s["fn"], 1)
        s["precision"] = s["tp"] / max(s["tp"] + s["fp"], 1) if s["tp"] + s["fp"] else None
    return {"edits": len(edits), "scores": scores, "note": "by construction for any representation with dependency records"}


class _OneBinding:
    def __init__(self, cid: str, b: dict):
        self.items = [(cid, b, 1.0, "")]

    def active_bindings(self) -> list:
        return self.items


def _factor_items(items: list) -> list[int]:
    return [k for k, it in enumerate(items) if hasattr(it, "factor")]


def _operational_check(items: list) -> bool:
    """What an operational-only record can check: duplicated identical modifiers, factors out of range, or two
    modifiers of one kind on the same target that cancel each other."""
    seen = set()
    for it in items:
        key = (type(it).__name__, getattr(it, "nodes", getattr(it, "edges", ())), getattr(it, "factor", None))
        if key in seen or not (0.0 <= getattr(it, "factor", 1.0) <= 5.0):
            return True
        seen.add(key)
    by_target: dict = {}
    for it in items:
        if hasattr(it, "factor"):
            by_target.setdefault((type(it).__name__, getattr(it, "nodes", getattr(it, "edges", ()))), []).append(it.factor)
    return any(len(v) > 1 and abs(float(np.prod(v)) - 1.0) < 1e-6 for v in by_target.values())


def error_detection(trials: int = 400, seed: int = 3) -> dict:
    """Corrupt the applied intervention set and try to detect it.

    Corruptions: *orphan* (a modifier of a claim that is not effective in the current state), *lost* (a justified
    modifier removed), *tampered* (a factor changed); plus *clean* control trials (no corruption) to measure false
    alarms. States: the lab graph, with concept "human" removed, and with K9 asserted (K4 defeated) — so that inactive
    claims with modifiers exist. Detection with dependency records = recompile and compare (by construction for any
    representation with dependency records); operational-only = internal consistency checks."""
    rng = random.Random(seed)
    _, pj = lab()
    loop = make_loop("scorekeeping", SEED)
    states = []
    for edit in (None, Edit("remove_token", a="human"), Edit("set_level", a="K9", value=1.0)):
        rep = build("scorekeeping", pj)
        if edit:
            apply_edit(rep, edit)
        good = loop._compiled(rep)
        inactive = [(cid, b) for cid, b, st, _ in rep.active_bindings() if st <= 0]
        states.append((good, inactive))
    kinds = ("orphan", "lost", "tampered", "clean")
    counts = dict.fromkeys(kinds, 0)
    det = {k: dict.fromkeys(kinds, 0) for k in ("dependency_records", "operational_only")}
    for _ in range(trials):
        good, inactive = rng.choice(states)
        kind = rng.choice(kinds)
        if kind == "orphan" and not inactive:
            kind = "clean"
        items = list(good)
        if kind == "orphan":
            cid, b = rng.choice(inactive)
            items = items + loop._compiled(_OneBinding(cid, b))
        elif kind == "lost":
            items.pop(rng.randrange(len(items)))
        elif kind == "tampered":
            k = rng.choice(_factor_items(items))
            it = items[k]
            items[k] = type(it)(getattr(it, "nodes", None) or it.edges, it.factor * rng.choice([0.5, 1.5]))
        counts[kind] += 1
        det["dependency_records"][kind] += int(_overlay_key(items) != _overlay_key(good))
        det["operational_only"][kind] += int(_operational_check(items))
    rates = {d: {k: (round(v[k] / counts[k], 3) if counts[k] else None) for k in kinds} for d, v in det.items()}
    return {"trials": counts, "detected": det, "rates": rates,
            "note": "clean = false-alarm rate. Detection by recompiling needs dependency records (any representation "
                    "that has them), not a particular vocabulary"}


def compression(runs: dict) -> dict:
    """Description length of the intervention trajectory measured on *semantic* intervention changes (operation,
    target set, factor) per check, vs the reasoning layer's own revisions and scheduled edits, plus the one-off size
    of the reasoning specification."""
    _, pj = lab()
    static = len(pj["claims"]) + len(pj["dependencies"]) + len(pj["incompatibilities"]) + \
        sum(len(c.get("bindings", [])) for c in pj["claims"]) + len(GROUNDINGS)
    out = {}
    for name, r in runs.items():
        prev: set = set()
        tokens = 0
        for eff in r["effects"]:
            cur = set(eff)
            tokens += len(cur ^ prev)
            prev = cur
        dyn = r["revisions"] + r["edits"]
        out[name] = {"operational_tokens": tokens, "reasoning_tokens_dynamic": dyn, "reasoning_tokens_static": static,
                     "reasoning_total": dyn + static, "compresses": dyn + static < tokens}
    return out


def _control_job(args: tuple) -> tuple:
    rep, seed, schedule = args
    from ..runtime.intervention import from_dict
    kw: dict[str, Any] = {"replay": [(t, [from_dict(x) for x in items]) for t, items in schedule]} if rep == "replay" else {}
    loop = make_loop(rep, seed, **kw)
    vals = []
    for _ in range(HORIZON):
        loop.step()
        if loop.world.state.t % 10 == 0 and loop.world.state.t >= 50:
            loop.probe.begin_check()
            vals.append((loop.probe.value("flow", "BA"), loop.probe.value("activity", "B")))
    return args[:2], vals


def reconfiguration_control(procs: int = 7, seeds: tuple = (40, 41, 42, 43)) -> dict:
    """Does the closed loop keep the world inside the bands its groundings react to (flow across BA below 0.026,
    activity in B above 0.041) better than: no reasoning, a memoryless reactive policy, or replaying a schedule
    recorded on a different seed?"""
    src = make_loop("scorekeeping", 39)
    for _ in range(HORIZON):
        src.step()
    sched = _schedule_json(src)
    jobs = [(rep, s, sched if rep == "replay" else None) for rep in ("scorekeeping", "memoryless", "none", "replay")
            for s in seeds]
    with ProcessPoolExecutor(procs) as ex:
        res = dict(ex.map(_control_job, jobs))
    out = {}
    for rep in ("scorekeeping", "memoryless", "none", "replay"):
        inband = [np.mean([(f <= 0.026) and (a >= 0.041) for f, a in res[(rep, s)]]) for s in seeds]
        out[rep] = {"in_band_mean": float(np.mean(inband)), "in_band_by_seed": [round(float(x), 3) for x in inband]}
    return out


# ------------------------------------------------------------------------------------------------ Part D phases
def _phase_job(args: tuple) -> tuple:
    rep, seed, probe_at = args
    loop = make_loop(rep, seed, reasoning_from=150, world_events=[{"t": 450, "items": [
        {"kind": "memory_condition", "target": "R", "decay": 0.3}]}])
    if probe_at is None:
        rec = record(loop, 700)
        return args, {"timeline": loop.timeline, "rec": rec}
    loop.run(probe_at)
    probe = copy.deepcopy(loop)
    noise = copy.deepcopy(loop)
    noise.world.engine.rng = np.random.default_rng(seed + 7777)
    apply_edit(probe.rep, Edit("remove_token", a="responsibility")) if probe.rep is not None else None
    probe._apply()
    a, b, c = record(loop, 100), record(probe, 100), record(noise, 100)
    return args, {"edit": _dist(a, b), "noise": _dist(a, c)}


def phases(procs: int = 7) -> dict:
    jobs: list[tuple[str, int, int | None]] = [("scorekeeping", SEED, None), ("none", SEED, None)]
    jobs += [("scorekeeping", SEED, t) for t in (100, 300, 600)]
    with ProcessPoolExecutor(procs) as ex:
        res = dict(ex.map(_phase_job, jobs))
    tl = res[("scorekeeping", SEED, None)]["timeline"]
    by_phase: dict[str, dict] = {}
    for r in tl:
        ph = by_phase.setdefault(r["phase"], {"checks": 0, "commitment_distinction": 0, "entitlement_distinction": 0,
                                                "overlay_changes": 0})
        ph["checks"] += 1
        ph["commitment_distinction"] += int(r.get("commitment_distinction", False))
        ph["entitlement_distinction"] += int(r.get("entitlement_distinction", False))
        ph["overlay_changes"] += int(r["overlay_changed"])

    def first(key):
        return next((r["t"] for r in tl if r.get(key)), None)

    sens = {}
    for t in (100, 300, 600):
        r = res[("scorekeeping", SEED, t)]
        ex_ = _exceeds(r["edit"], r["noise"])
        sens[str(t)] = {"phase": next((x["phase"] for x in tl if x["t"] >= t), None), "exceeds_noise_on": ex_,
                        "edit_event_distance": r["edit"]["event_sequence"],
                        "noise_event_distance": r["noise"]["event_sequence"],
                        "edit_first_divergence": r["edit"]["first_divergence"]}
    world_d = _dist(res[("none", SEED, None)]["rec"], res[("scorekeeping", SEED, None)]["rec"])
    return {"schedule": {"reasoning_from": 150, "degrade_at": 450, "degradation": "memory condition on R (decay 0.3)",
                         "end": 700},
            "timeline": [{k: v for k, v in r.items() if k != "effective"} | {"effective": r.get("effective", {})}
                         for r in tl],
            "by_phase": by_phase, "first_commitment_distinction": first("commitment_distinction"),
            "first_entitlement_distinction": first("entitlement_distinction"),
            "enabled_at": next((r["t"] for r in tl if r["enabled"] and r["phase"] == "reasoning"), None),
            "collapsed_at": next((r["t"] for r in tl if r["phase"] == "collapsed"), None),
            "sensitivity_to_reasoning_edit": sens, "reasoning_vs_none_world_distance": world_d}


def _mutation_job(rate: float) -> tuple:
    loop = make_loop("scorekeeping", SEED, world_events=[{"t": EDIT_AT, "items": [
        {"kind": "mutation", "target": "R", "rate": rate}]}] if rate > 0 else [])
    loop.run(HORIZON)
    tl = loop.timeline
    after = [r for r in tl if r["t"] > EDIT_AT]
    return rate, {"collapsed_share_after": sum(r["phase"] == "collapsed" for r in after) / max(len(after), 1),
                  "first_collapse": next((r["t"] for r in after if r["phase"] == "collapsed"), None),
                  "stability_R_after_mean": float(np.mean([r["conditions"][1] for r in after])) if after else None,
                  "revisions": loop.revisions}


def mutation_sweep(procs: int = 7, rates: tuple = (0.0, 0.0005, 0.001, 0.002, 0.004, 0.008, 0.016)) -> dict:
    with ProcessPoolExecutor(procs) as ex:
        res = dict(ex.map(_mutation_job, rates))
    return {str(k): v for k, v in res.items()}


# ------------------------------------------------------------------------------------------------ multi-seed world effects
WORLD_SEEDS = tuple(range(60, 68))
WORLD_HORIZON = 400


def _spec_job(args: tuple) -> tuple:
    key, spec, seed = args
    spec = dict(spec)
    practice = _p2_practice() if spec.pop("practice", None) == "p2" else None
    rep = spec.pop("representation")
    loop = make_loop(rep, seed, practice=practice, **spec)
    rec = record(loop, WORLD_HORIZON)
    from .reduction_rules import _summaries
    return key, {"summ": _summaries(rec), "effects": [tuple(r["effects"]) for r in loop.timeline],
                 "fp": loop.world.engine.fingerprint(), "phases": [r["phase"] for r in loop.timeline]}


def _paired(a: list[dict], b: list[dict]) -> dict:
    """Paired test over seeds on scalar summaries (same thresholds as reduction stage 2); plus exact indicators."""
    from .reduction_rules import PRACTICAL, T_THRESHOLD
    effects = {}
    for k in a[0]["summ"]:
        if k.endswith("transformations") or k.endswith("returns") or k == "s:recurrence":
            continue
        d = np.array([y["summ"][k] - x["summ"][k] for x, y in zip(a, b, strict=True)])
        base = np.mean([abs(x["summ"][k]) for x in a]) + 1e-12
        sd = d.std(ddof=1)
        t = (0.0 if d.mean() == 0 else float("inf")) if sd == 0 else float(d.mean() / (sd / np.sqrt(len(d))))
        rel = float(d.mean() / base)
        if abs(t) > T_THRESHOLD and abs(rel) > PRACTICAL:
            effects[k] = {"t": round(t, 2) if np.isfinite(t) else "inf", "relative": round(rel, 4)}
    sched = [float(np.mean([u != v for u, v in zip(x["effects"], y["effects"], strict=False)]))
             for x, y in zip(a, b, strict=True)]
    return {"world_effects": effects, "world_effect_detected": bool(effects),
            "identical_runs": sum(x["fp"] == y["fp"] for x, y in zip(a, b, strict=True)), "seeds": len(a),
            "intervention_checks_differing": round(float(np.mean(sched)), 3)}


def _adaptivity(runs: list[dict]) -> float:
    """How much the intervention schedule depends on the world: mean fraction of checks at which two runs of the
    same representation on different world seeds apply different interventions (0 = schedule world-independent)."""
    vals = []
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            vals.append(np.mean([u != v for u, v in zip(runs[i]["effects"], runs[j]["effects"], strict=False)]))
    return round(float(np.mean(vals)), 3) if vals else 0.0


WORLD_SPECS: dict[str, dict] = {
    "none": {"representation": "none"},
    "scorekeeping": {"representation": "scorekeeping"},
    "support_greatest": {"representation": "support_greatest"},
    "support": {"representation": "support"},
    "support_single": {"representation": "support_single"},
    "scorekeeping_no_entitlement": {"representation": "scorekeeping_no_entitlement"},
    "memoryless": {"representation": "memoryless"},
    "edit_human": {"representation": "scorekeeping", "edits": [(EDIT_AT, Edit("remove_token", a="human"))]},
    "edit_responsibility": {"representation": "scorekeeping",
                            "edits": [(EDIT_AT, Edit("remove_token", a="responsibility"))]},
    "p2_edit_human": {"representation": "scorekeeping", "practice": "p2",
                      "edits": [(EDIT_AT, Edit("remove_token", a="human"))]},
    "support_greatest_edit_human": {"representation": "support_greatest",
                                    "edits": [(EDIT_AT, Edit("remove_token", a="human"))]},
}
WORLD_PAIRS = {
    "reasoning layer vs none": ("none", "scorekeeping"),
    "vocabulary: scorekeeping vs terminology-free support graph (greatest fixpoint)": ("scorekeeping", "support_greatest"),
    "vocabulary under an edit: same, after removing concept human": ("edit_human", "support_greatest_edit_human"),
    "fixpoint choice: greatest vs least": ("scorekeeping", "support"),
    "two-status vs single-status": ("scorekeeping", "support_single"),
    "entitlement tracking on vs off": ("scorekeeping", "scorekeeping_no_entitlement"),
    "persistent reasoning state vs memoryless reactive policy": ("scorekeeping", "memoryless"),
    "edit: remove concept human": ("scorekeeping", "edit_human"),
    "edit: remove concept responsibility": ("scorekeeping", "edit_responsibility"),
    "counterfactual discrimination: same interventions, different dependency structure, same edit":
        ("edit_human", "p2_edit_human"),
}


def world_effects(procs: int = 7) -> dict:
    jobs = [(name, spec, s) for name, spec in WORLD_SPECS.items() for s in WORLD_SEEDS]
    with ProcessPoolExecutor(procs) as ex:
        out = list(ex.map(_spec_job, [((k, s), sp, s) for k, sp, s in jobs]))
    res = dict(out)
    runs = {k: [res[(k, s)] for s in WORLD_SEEDS] for k in WORLD_SPECS}
    pairs = {name: _paired(runs[a], runs[b]) | {"a": a, "b": b} for name, (a, b) in WORLD_PAIRS.items()}
    return {"seeds": list(WORLD_SEEDS), "horizon": WORLD_HORIZON, "edit_at": EDIT_AT, "pairs": pairs,
            "adaptivity": {k: _adaptivity(runs[k]) for k in ("scorekeeping", "memoryless", "none")},
            "reasoning_active_share": {k: round(float(np.mean([r["phases"].count("reasoning") / max(len(r["phases"]), 1)
                                                               for r in runs[k]])), 3) for k in WORLD_SPECS}}


# ------------------------------------------------------------------------------------------------ Part D enabling conditions
EXTRA_GATES = {
    "repeated interaction": {"metric": "activity", "target": "R", "op": ">=", "value": 0.10},
    "traceable dependency structure": {"metric": "reach", "target": "A", "source": "R", "op": ">=", "value": 0.20},
}
CONDITIONS: dict[str, dict] = {
    "none degraded (reference)": {},
    "external memory": {"world": [{"kind": "memory_condition", "target": "R", "decay": 0.3}]},
    "stable addressability": {"world": [{"kind": "mutation", "target": "R", "rate": 0.008}]},
    "repeated interaction": {"world": [{"kind": "scale_threshold", "target": "R", "factor": 3.0}],
                             "gate": "repeated interaction"},
    "traceable dependency structure": {"world": [{"kind": "gate", "target": "BR", "factor": 0.0}],
                                       "gate": "traceable dependency structure"},
    "incompatibility tracking": {"edits": [Edit("drop_conflict", a="K4", b="K9"), Edit("drop_conflict", a="K2", b="K7")]},
    "inferential interface stability": {"loop": {"interface_churn": {"from": EDIT_AT, "every": 2, "seed": 3}}},
    "low mutation rate": {"world": [{"kind": "mutation", "target": "A", "rate": 0.004},
                                    {"kind": "mutation", "target": "B", "rate": 0.004},
                                    {"kind": "mutation", "target": "R", "rate": 0.004}]},
    "shared record persistence": {"loop": {"record_decay": {"from": EDIT_AT, "factor": 0.85}}},
}
GATED_BY = {"external memory", "stable addressability", "low mutation rate", "repeated interaction",
            "traceable dependency structure"}
MATRIX_SEEDS = tuple(range(80, 86))
PROBE = Edit("remove_token", a="human")


def _cond_spec(name: str, gated: bool, representation: str, practice: str | None = None, probe: bool = False) -> dict:
    c = CONDITIONS[name]
    spec: dict = {"representation": representation,
                  "world_events": [{"t": EDIT_AT, "items": c["world"]}] if c.get("world") else [],
                  "edits": [(EDIT_AT, e) for e in c.get("edits", [])] + ([(PROBE_AT, PROBE)] if probe else []),
                  **c.get("loop", {})}
    spec["enabling"] = (ENABLING + ([EXTRA_GATES[c["gate"]]] if c.get("gate") else [])) if gated else []
    if practice:
        spec["practice"] = practice
    return spec


MATRIX_SPECS = {
    "gated": lambda n: _cond_spec(n, True, "scorekeeping"),
    "none": lambda n: _cond_spec(n, False, "none"),
    "sk": lambda n: _cond_spec(n, False, "scorekeeping"),
    "memoryless": lambda n: _cond_spec(n, False, "memoryless"),
    "p1_probe": lambda n: _cond_spec(n, False, "scorekeeping", probe=True),
    "p2_probe": lambda n: _cond_spec(n, False, "scorekeeping", practice="p2", probe=True),
}


def enabling_matrix(procs: int = 7) -> dict:
    """For each candidate enabling condition, degraded at EDIT_AT:

    gated    scorekeeping with the enabling gates: share of checks collapsed after degradation. For conditions
             measured by a gate this is true *by construction* (implementation choice); for the others it tests
             whether the degradation reaches a gate indirectly.
    ungated  reasoning forced on in the degraded world (6 world seeds, paired): does it still change the world
             (vs none), does its persistent state matter (vs memoryless), does its dependency structure discriminate
             a counterfactual edit (P1 vs P2 with the same probe), and is its schedule world-dependent (adaptivity)?"""
    jobs = [((name, kind, s), MATRIX_SPECS[kind](name), s) for name in CONDITIONS for kind in MATRIX_SPECS
            for s in MATRIX_SEEDS]
    with ProcessPoolExecutor(procs) as ex:
        res = dict(ex.map(_spec_job, jobs))
    out = {}
    for name in CONDITIONS:
        runs = {k: [res[(name, k, s)] for s in MATRIX_SEEDS] for k in MATRIX_SPECS}
        after = [ph for r in runs["gated"] for ph in r["phases"][EDIT_AT // 10 + 2:]]
        crit = {"world_effect_vs_none": _paired(runs["none"], runs["sk"]),
                "persistence_vs_memoryless": _paired(runs["memoryless"], runs["sk"]),
                "counterfactual_discrimination": _paired(runs["p1_probe"], runs["p2_probe"])}
        out[name] = {
            "gated_collapsed_share": round(after.count("collapsed") / max(len(after), 1), 3),
            "measured_by_gate": name in GATED_BY,
            "ungated": {k: {x: v[x] for x in ("world_effect_detected", "intervention_checks_differing", "identical_runs")}
                        | {"effects": dict(list(v["world_effects"].items())[:4])} for k, v in crit.items()},
            "adaptivity": _adaptivity(runs["sk"]),
            "valuable_on": [k for k, v in crit.items() if v["world_effect_detected"]],
        }
    return {"conditions": out, "seeds": list(MATRIX_SEEDS), "probe_edit": f"remove concept human at t={PROBE_AT}",
            "degradation_at": EDIT_AT,
            "note": "gated collapse is by construction for conditions measured by a gate; the ungated columns are the "
                    "empirical test of whether reasoning adds operational value in the degraded world"}


# ------------------------------------------------------------------------------------------------ Part G closed loop
def closed_loop_trace() -> dict:
    """One closed-loop run with the full event chain recorded."""
    loop = make_loop("scorekeeping", SEED, reasoning_from=50, world_events=[{"t": 300, "items": [
        {"kind": "memory_condition", "target": "R", "decay": 0.3}]}, {"t": 450, "items": []}])
    loop.run(500)
    chain = []
    prev = None
    for r in loop.timeline:
        if prev is not None:
            if r["enabled"] != prev["enabled"]:
                chain.append({"t": r["t"], "event": "enabling conditions " + ("met" if r["enabled"] else "failed"),
                              "conditions": r["conditions"]})
            if r["revisions"] != prev["revisions"]:
                chain.append({"t": r["t"], "event": "world → reasoning: grounded revision",
                              "effective": r.get("effective")})
            if r["effects"] != prev["effects"]:  # semantic change (operation, target set, factor), not index churn
                added = sorted(set(r["effects"]) - set(prev["effects"]))
                removed = sorted(set(prev["effects"]) - set(r["effects"]))
                ext = [x for x in added + removed if x.startswith("world ")]
                own_add = [x for x in added if not x.startswith("world ")]
                own_rem = [x for x in removed if not x.startswith("world ")]
                if ext:
                    chain.append({"t": r["t"], "event": "external world intervention (degradation)", "items": ext})
                if own_add or own_rem:
                    chain.append({"t": r["t"], "event": "reasoning → world: operational interventions changed",
                                  "added": own_add, "removed": own_rem})
            if r["phase"] != prev["phase"]:
                chain.append({"t": r["t"], "event": f"phase: {prev['phase']} → {r['phase']}"})
        prev = r
    semantic = sum(1 for a, b in zip(loop.timeline, loop.timeline[1:], strict=False) if a["effects"] != b["effects"])
    return {"chain": chain[:200], "revisions": loop.revisions, "overlay_changes": len(loop.overlay_changes),
            "semantic_intervention_changes": semantic, "gate_calls": loop.gate.applied,
            "phases": [r["phase"] for r in loop.timeline]}


# ------------------------------------------------------------------------------------------------ main
def main(out: str | None = None, procs: int = 7) -> dict:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    t0 = time.perf_counter()
    scen = scenario_suite(procs)
    result: dict[str, Any] = {
        "suite": "philosophical_nonredundancy", "scenario": SCENARIO, "horizon": HORIZON, "edit_at": EDIT_AT,
        "enabling_conditions": ENABLING, "groundings": GROUNDINGS,
        "scenarios": scen,
        "representation_equivalence": representation_equivalence(),
        "criteria": {
            "transition_prediction": transition_prediction(procs),
            "intervention_precision": intervention_precision(),
            "dependency_tracing": dependency_tracing(),
            "error_detection": error_detection(),
            "reconfiguration_control": reconfiguration_control(procs),
        },
        "world_effects": world_effects(procs),
        "phases": phases(procs),
        "enabling_matrix": enabling_matrix(procs),
        "mutation_sweep": mutation_sweep(procs),
        "closed_loop": closed_loop_trace(),
        "elapsed_s": 0.0,
    }
    result["criteria"]["compression"] = _compression_from_suite(procs)
    result["elapsed_s"] = round(time.perf_counter() - t0, 1)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(result, indent=1, default=str))
    return result


def _compression_job(name: str) -> tuple:
    spec = SCENARIOS[name]
    loop = make_loop(spec.get("representation_override", {}).get("scorekeeping", "scorekeeping"), SEED,
                     practice=_p2_practice() if spec.get("practice") == "p2" else None,
                     edits=list(spec.get("edits", [])), world_events=list(spec.get("world_events", [])))
    loop.run(HORIZON)
    return name, {"effects": [r["effects"] for r in loop.timeline], "revisions": loop.revisions,
                  "edits": len(spec.get("edits", []))}


def _compression_from_suite(procs: int) -> dict:
    with ProcessPoolExecutor(procs) as ex:
        runs = dict(ex.map(_compression_job, list(SCENARIOS)))
    return compression(runs)


if __name__ == "__main__":
    import sys
    r = main(sys.argv[1] if len(sys.argv) > 1 else None)
    for n, s in r["scenarios"].items():
        print(n, "| vocab non-redundant:", s["vocabulary_nonredundant"], "| two-status:", s["two_status_nonredundant"],
              "| entitlement:", s["entitlement_nonredundant"], "| replay exact:", s["replay_reproduces_scorekeeping_exactly"])
