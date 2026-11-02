"""MEOS-0, fifth stage: every inclusion-minimal retaining set (MFS) of a specified operation under a stated condition, and what the sets say about the components.

The question of the earlier stages was "what is the minimal configuration". The question here is "which different minimal configurations are there, under which conditions, and
how do the components relate (necessary, sufficient, substitutable, redundant, ...)". Nothing is assumed: the enumeration is exhaustive over the retained subsets of a universe of
components, so every inclusion-minimal set is found and the minimality of each is a statement about *all* its proper subsets, each of which was run.

Specified operation: the recursive cycle persists, status ACTIVE at the horizon in every search seed (the same operation as in the earlier stages). A component is *removed* by the
intervention that removes it at tick 0 (``REMOVE``); the optional M2 tap (``m2_tap``) is removed by switching M2 sensing off (``ROUTE``). A set of components is *retained* when it is
the complement of the removed ones within the universe of the condition. Components the condition declares unavailable are never retained.

Everything runs the real engine; nothing here changes a run, and every outcome is recorded whether or not it was expected.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import multiprocessing as mp
from typing import Any

from . import analysis as A
from . import engine as E
from . import experiments as X
from . import stage4 as S4

COMPONENTS5: tuple[str, ...] = (*E.COMPONENTS, "m2_tap")
HORIZON = 160  # the horizon of the earlier stages' minimal-configuration search
SEARCH_SEEDS = (1, 2, 3, 4, 5)  # a set persists only if it persists in every one of these
CONFIRM_SEEDS = (6, 7, 8, 9, 10)  # independent seeds: every MFS found is run again on seeds the search never saw

# the operational paths of the earlier stage, plus the two that exist from this stage on: the M2 path (the tap) and the address path (both configurations present and addressed)
PATH_COMPONENTS: dict[str, tuple[str, ...]] = {
    **{k: tuple(v["components"]) for k, v in S4.PATHS.items()},
    "m2": ("m2_tap",),
    "address": ("A1", "A2"),
}

M2_BASE = {"sense": "direct", "weight": 4.0}


def condition(cid: str, label: str, config: dict | None = None, *, unavailable: tuple[str, ...] = (), tap: dict | None = None, features: dict | None = None, degrades: str | None = None, pre: list[dict] | None = None, only: tuple[str, ...] | None = None) -> dict:
    """A condition under which the specified operation is to be retained: configuration overrides, components that cannot be retained, an optional M2 tap, the features the controller
    of ``reconf`` matches a sensed environment against, and (for a degraded condition) the condition it degrades."""
    cfg = copy.deepcopy(config or {})
    if tap is not None:
        cfg["m2"] = copy.deepcopy(tap)
    universe = tuple(c for c in (COMPONENTS5 if tap is not None else E.COMPONENTS) if c not in unavailable)
    if only is not None:  # a smaller universe (the other components stay in place, never removed): used to keep tests and focused searches small
        universe = tuple(c for c in universe if c in only)
    return {"id": cid, "label": label, "config": cfg, "universe": universe, "unavailable": list(unavailable), "features": features or {}, "degrades": degrades, "pre": pre or []}


def base_features(**over: Any) -> dict:
    f = {"history": "ok", "coupling": "normal", "resource": "normal", "power": "finite", "tap": "none", "address": "ok", "renewal": "normal"}
    f.update(over)
    return f


# The conditions of experiment F. ``tap`` conditions add the optional M2 tap to the universe; conditions that degrade another declare it.
def conditions_f() -> list[dict]:
    return [
        condition("F1", "finite power, no M2 tap", features=base_features()),
        condition("F2", "unlimited power, no M2 tap", {"power": {"infinite": True}}, features=base_features(power="unlimited")),
        condition("F3", "finite power, direct M2 tap (weight 4)", tap=M2_BASE, features=base_features(tap="direct")),
        condition("F4", "unlimited power, direct M2 tap", {"power": {"infinite": True}}, tap=M2_BASE, features=base_features(power="unlimited", tap="direct")),
        condition("F5", "finite power, noisy M2 tap (0.05, weight 4)", tap={"sense": "noisy", "weight": 4.0, "noise": 0.05}, features=base_features(tap="noisy")),
        condition("F6", "finite power, delayed M2 tap (3 ticks, weight 4)", tap={"sense": "delayed", "weight": 4.0, "delay": 3}, features=base_features(tap="delayed")),
        condition("F7", "direct tap, history unavailable", tap=M2_BASE, unavailable=("history",), features=base_features(history="lost", tap="direct"), degrades="F3"),
        condition("F8", "direct tap, coupling weakened (gain 0.6)", {"coupling": {"gain": 0.6}}, tap=M2_BASE, features=base_features(coupling="weak", tap="direct"), degrades="F3"),
        condition("F9", "direct tap, resource reduced (regrow 0.01, charge 0.2)", {"environment": {"regrow": 0.01}, "power": {"charge": 0.2}}, tap=M2_BASE, features=base_features(resource="reduced", tap="direct"), degrades="F3"),
        condition("F10", "direct tap, renewal efficiency 0.7", {"environment": {"renew_efficiency": 0.7}}, tap=M2_BASE, features=base_features(renewal="reduced", tap="direct"), degrades="F3"),
        condition("F11", "direct tap, history delayed (lag 8)", {"history": {"lag": 8}}, tap=M2_BASE, features=base_features(history="delayed", tap="direct"), degrades="F3"),
        # the conditions in which the earlier stage (experiment E) saw M2 sensing rescue a run that collapses without it: SSS scale 1.5. They are added because that result was seen, not to produce a
        # second set: whether an M2-mediated MFS exists there is what the search decides.
        condition("F12", "SSS scale 1.5, no M2 tap", {"sss": {"scale": 1.5}}, features=base_features()),
        condition("F13", "SSS scale 1.5, direct M2 tap", {"sss": {"scale": 1.5}}, tap=M2_BASE, features=base_features(tap="direct")),
        condition("F14", "SSS scale 1.5, delayed M2 tap (3 ticks)", {"sss": {"scale": 1.5}}, tap={"sense": "delayed", "weight": 4.0, "delay": 3}, features=base_features(tap="delayed")),
        condition("F15", "SSS scale 1.5, noisy M2 tap (0.05)", {"sss": {"scale": 1.5}}, tap={"sense": "noisy", "weight": 4.0, "noise": 0.05}, features=base_features(tap="noisy")),
        condition("F16", "renewal efficiency 0.7, noisy M2 tap", {"environment": {"renew_efficiency": 0.7}}, tap={"sense": "noisy", "weight": 4.0, "noise": 0.05}, features=base_features(renewal="reduced", tap="noisy"), degrades="F5"),
    ]


# ---------------------------------------------------------------------------------------------------- running a retained set
def _config(cond: dict, seed: int, horizon: int) -> dict:
    return X.cfg_with(E.default_config(), seed=seed, horizon=horizon, **copy.deepcopy(cond["config"]))


def retained_interventions(cond: dict, retained: frozenset | set | tuple) -> list[dict]:
    """The interventions that leave exactly ``retained`` (within the universe of the condition) in place: every other component of the universe is removed at tick 0."""
    ivs: list[dict] = []
    for c in cond["universe"]:
        if c in retained:
            continue
        ivs.append({"tick": 0, "op": "ROUTE", "m2": {"sense": "none"}} if c == "m2_tap" else {"tick": 0, "op": "REMOVE", "target": c})
    for c in cond["unavailable"]:  # an unavailable component is absent in every run of the condition
        ivs.append({"tick": 0, "op": "ROUTE", "m2": {"sense": "none"}} if c == "m2_tap" else {"tick": 0, "op": "REMOVE", "target": c})
    return [*ivs, *copy.deepcopy(cond["pre"])]


def persists(cond: dict, retained: frozenset | set | tuple, seeds: tuple[int, ...] = SEARCH_SEEDS, horizon: int = HORIZON) -> tuple[bool, ...]:
    ivs = retained_interventions(cond, retained)
    return tuple(E.run_record(_config(cond, sd, horizon), ivs)["final_status"]["label"] == "ACTIVE" for sd in seeds)


def _eval_mask(args: tuple) -> tuple[int, tuple[bool, ...]]:
    cond, mask, seeds, horizon = args
    uni = cond["universe"]
    retained = frozenset(c for i, c in enumerate(uni) if mask >> i & 1)
    return mask, persists(cond, retained, seeds, horizon)


def enumerate_persistence(cond: dict, seeds: tuple[int, ...] = SEARCH_SEEDS, horizon: int = HORIZON, processes: int | None = None) -> dict[int, tuple[bool, ...]]:
    """Run every subset of the universe as the retained set; ``result[mask]`` is the per-seed persistence (bit i of the mask = universe[i] retained)."""
    n = len(cond["universe"])
    jobs = [(cond, m, seeds, horizon) for m in range(1 << n)]
    if processes == 1:
        return dict(map(_eval_mask, jobs))
    with mp.get_context("fork").Pool(processes or max(1, (mp.cpu_count() or 2) - 2)) as pool:
        return dict(pool.imap_unordered(_eval_mask, jobs, chunksize=8))


def _submasks(m: int):
    s = (m - 1) & m
    while True:
        yield s
        if s == 0:
            return
        s = (s - 1) & m


def minimal_masks(persist: dict[int, bool]) -> list[int]:
    """The inclusion-minimal persisting masks: persisting, with no persisting proper subset (every proper subset is checked)."""
    out = []
    for m, ok in persist.items():
        if ok and not any(persist[s] for s in _submasks(m) if s != m):
            out.append(m)
    return sorted(out, key=lambda m: (bin(m).count("1"), m))


# ---------------------------------------------------------------------------------------------------- the record of one MFS
def paths_of(retained: set | frozenset, universe: tuple[str, ...]) -> tuple[list[str], list[str]]:
    """The paths whose every component is retained, and the paths that are lost (a component not retained). Paths whose components are outside the universe are not counted."""
    kept: list[str] = []
    lost: list[str] = []
    for p, comps in PATH_COMPONENTS.items():
        if not all(c in universe for c in comps):
            continue
        (kept if all(c in retained for c in comps) else lost).append(p)
    return kept, lost


def route_kind(retained: set | frozenset, universe: tuple[str, ...]) -> str:
    """A name for the route the set realises, from what it retains that is not common to every set: history-mediated, M2-mediated, mixed, or neither; plus the resource and renewal parts."""
    parts = []
    h, m = "history" in retained, "m2_tap" in retained
    if h and m:
        parts.append("history+M2 (mixed)")
    elif h:
        parts.append("history-mediated")
    elif m:
        parts.append("M2-mediated")
    elif "history" in universe:
        parts.append("history-free")
    if {"resource_gradient", "resource_renewal"} <= set(retained):
        parts.append("resource-mediated")
    if {"feedback", "resource_renewal"} <= set(retained):
        parts.append("renewal-mediated")
    if "interaction_channel" in retained:
        parts.append("coupling-mediated")
    return ", ".join(parts) or "unclassified"


def recovery_probe(cond: dict, retained: frozenset, seeds: tuple[int, ...] = CONFIRM_SEEDS) -> dict:
    """Recovery capability of a retained set: the coupling is interrupted from tick 100 to 150 (when the set retains it) and, in a second run, a resource pulse follows at 151."""
    if "interaction_channel" not in retained:
        return {"testable": False, "reason": "the set does not retain the interaction channel, so the interruption has nothing to cut"}
    base = retained_interventions(cond, retained)
    cut = [{"tick": 100, "op": "ISOLATE", "target": "interaction_channel"}, {"tick": 150, "op": "RECONNECT", "target": "interaction_channel"}]
    out: dict[str, Any] = {"testable": True, "without_pulse": 0, "with_pulse": 0, "latency_with_pulse": []}
    for sd in seeds:
        cfg = _config(cond, sd, 360)
        r0 = E.run_record(cfg, [*base, *cut])
        r1 = E.run_record(cfg, [*base, *cut, X.pulse(151, 2.0)])
        out["without_pulse"] += r0["final_status"]["label"] == "ACTIVE"
        ok = r1["final_status"]["label"] == "ACTIVE"
        out["with_pulse"] += ok
        if ok:
            t = next((s["tick"] for s in r1["status_log"] if s["label"] == "ACTIVE" and s["tick"] > 150), None)
            out["latency_with_pulse"].append(None if t is None else t - 150)
    out["seeds"] = len(seeds)
    return out


def mfs_record(cond: dict, mask: int, persist: dict[int, tuple[bool, ...]], index: int, confirm_seeds: tuple[int, ...] = CONFIRM_SEEDS) -> dict:
    uni = cond["universe"]
    retained = frozenset(c for i, c in enumerate(uni) if mask >> i & 1)
    removed = [c for c in uni if c not in retained]
    kept, lost = paths_of(retained, uni)
    sub = [s for s in _submasks(mask) if s != mask]
    # the proof of inclusion-minimality: every proper subset was run and none persists; the maximal proper subsets (one component fewer) are run again with the confirmation seeds
    maximal: list[dict[str, Any]] = []
    for i, c in enumerate(uni):
        if mask >> i & 1:
            m2 = mask & ~(1 << i)
            sp = persists(cond, frozenset(x for j, x in enumerate(uni) if m2 >> j & 1), confirm_seeds)
            maximal.append({"without": c, "persists_seeds": sum(sp), "seeds": len(confirm_seeds)})
    seeds_ok = persists(cond, retained, confirm_seeds)
    rec = {
        "id": f"MFS-{cond['id']}-{index}",
        "condition_id": cond["id"],
        "route_kind": route_kind(retained, uni),
        "preserved_operation": "the recursive cycle persists: status ACTIVE at the horizon (at least 2 complete cycles in the last 48 ticks, the latest no older than 24)",
        "environment_condition": {"label": cond["label"], "config": cond["config"], "unavailable": cond["unavailable"], "features": cond["features"]},
        "observation_condition": "operational state read from the run itself (full observation); observability is evaluated separately (observability field)",
        "temporal_window": {"status_window_ticks": 48, "horizon": HORIZON, "recovery_probe_horizon": 360},
        "scale": E.default_config()["sss"] | (cond["config"].get("sss") or {}),
        "allowed_reductions": list(uni),
        "retained_components": [c for c in uni if c in retained],
        "removed_components": removed,
        "retained_paths": kept,
        "lost_paths": lost,
        "cardinality": len(retained),
        "recovery_capability": recovery_probe(cond, retained),
        "inclusion_minimality_proof": {
            "all_proper_subsets_evaluated": len(sub),
            "persisting_proper_subsets": sum(1 for s in sub if persist[s] and all(persist[s])),
            "maximal_proper_subsets": maximal,
            "statement": "every proper subset of the retained set was run in every search seed; none persists in all of them",
        },
        "search_seeds": list(SEARCH_SEEDS),
        "confirmation_seeds": list(confirm_seeds),
        "persists_in_confirmation_seeds": sum(seeds_ok),
    }
    rec["digest"] = E.digest({k: rec[k] for k in ("condition_id", "retained_components", "removed_components", "environment_condition", "allowed_reductions")})
    run = E.run_record(_config(cond, CONFIRM_SEEDS[0], HORIZON), retained_interventions(cond, retained))
    rec["run_result_digest"] = run["result_digest"]
    obs = A.observe(run, {"sampling_interval": 2})
    rec["observability"] = {"operational_state": obs["operational_state"], "observed_state_at_interval_2": obs["observed_state"], "status": obs["observability"]["status"]}
    return rec


def search(cond: dict, processes: int | None = None, confirm_seeds: tuple[int, ...] = CONFIRM_SEEDS) -> dict:
    """The exhaustive search of one condition: every subset run, every inclusion-minimal set recorded, the classification of the components computed from the whole table."""
    uni = cond["universe"]
    raw = enumerate_persistence(cond, processes=processes)
    persist = {m: all(v) for m, v in raw.items()}
    mins = minimal_masks(persist)
    records = [mfs_record(cond, m, raw, i + 1, confirm_seeds) for i, m in enumerate(mins)]
    return {
        "condition": {k: cond[k] for k in ("id", "label", "config", "unavailable", "features", "degrades")},
        "universe": list(uni),
        "subsets_evaluated": len(raw),
        "persisting_subsets": sum(persist.values()),
        "seed_disagreeing_subsets": sum(1 for v in raw.values() if any(v) and not all(v)),
        "minimal_count": len(mins),
        "mfs": records,
        "classification": classify(uni, persist),
        "table": {str(m): sum(v) for m, v in raw.items()},  # per subset, the number of search seeds in which it persists
    }


# ---------------------------------------------------------------------------------------------------- necessary, sufficient, substitutable, ...
def classify(universe: tuple[str, ...], persist: dict[int, bool]) -> dict:
    """The relations of each component to the operation under one condition, from the whole table of subsets (definitions in the document, section 5).

    necessary: in every persisting set. sufficient: it completes the necessary core (the core and it persist) without being necessary itself. substitutable by X: a context S exists in
    which S+c and S+X persist and S does not. null: it never matters (S persists iff S+c does, for every S). redundant: in no minimal set while the full set minus it still persists.
    destabilizing: adding it to some persisting set makes that set stop persisting. jointly necessary (a pair): neither alone is necessary but every persisting set holds at least one.
    jointly sufficient (a pair): the core plus both persists, the core plus either alone does not."""
    n = len(universe)
    full = (1 << n) - 1
    P = [m for m, ok in persist.items() if ok]
    mins = minimal_masks(persist)
    idx = {c: i for i, c in enumerate(universe)}
    core = full if P else 0
    for m in P:
        core &= m
    out: dict[str, Any] = {"persisting_sets": len(P), "minimal_sets": len(mins), "necessary_core": [c for c in universe if core >> idx[c] & 1], "components": {}, "pairs": {"jointly_necessary": [], "jointly_sufficient": []}}
    for c in universe:
        b = 1 << idx[c]
        labels: list[str] = []
        detail: dict[str, Any] = {}
        if P and core & b:
            labels.append("necessary")
        if P and not core & b and not persist.get(core, False) and persist.get(core | b, False):
            labels.append("sufficient (completes the necessary core)")
        affects = any(persist[m] != persist[m | b] for m in persist if not m & b)
        if not affects:
            labels.append("null")
        in_minimal = any(m & b for m in mins)
        if not in_minimal and persist.get(full & ~b, False) and persist.get(full, False):
            labels.append("redundant")
        if any(persist[m] and not persist[m | b] for m in persist if not m & b):
            labels.append("destabilizing")
            detail["destabilizing_example_without"] = [x for x in universe if next(m for m in persist if not m & b and persist[m] and not persist[m | b]) >> idx[x] & 1]
        subs: list[tuple[tuple[str, ...], int]] = []
        for k in (1, 2):
            for X_ in itertools.combinations([x for x in universe if x != c], k):
                xb = sum(1 << idx[x] for x in X_)
                if any(subs_has(X_, s) for s in subs):
                    continue
                ctx = [m for m in persist if not m & (b | xb) and persist[m | b] and persist[m | xb] and not persist[m]]
                if ctx:
                    subs.append((X_, min(ctx, key=lambda m: bin(m).count("1"))))
        if subs:
            labels.append("substitutable")
            detail["substitutable_by"] = [{"by": list(x), "context_retained": [u for u in universe if m >> idx[u] & 1]} for x, m in subs[:6]]
        out["components"][c] = {"labels": labels or ["contributes in some contexts only"], **detail}
    for a, b2 in itertools.combinations(universe, 2):
        ab, bb = 1 << idx[a], 1 << idx[b2]
        if P and not core & ab and not core & bb and all(m & (ab | bb) for m in P):
            out["pairs"]["jointly_necessary"].append([a, b2])
        if P and persist.get(core | ab | bb, False) and not persist.get(core | ab, False) and not persist.get(core | bb, False):
            out["pairs"]["jointly_sufficient"].append([a, b2])
    return out


def subs_has(small: tuple, existing: tuple) -> bool:
    """Whether an earlier substitute is wholly contained in this one (a larger substitute is then not minimal)."""
    return set(existing[0]) <= set(small)


def classify_across(results: dict[str, dict]) -> dict:
    """Relations that only exist between conditions: conditionally redundant (in no minimal set under one condition, in one under another) and compensatory (conditionally redundant, and
    needed under a condition that degrades the first)."""
    out: dict[str, Any] = {}
    comps = sorted({c for r in results.values() for c in r["universe"]})
    for c in comps:
        row: dict[str, Any] = {"in_a_minimal_set_under": [], "in_no_minimal_set_under": [], "necessary_under": []}
        for cid, r in results.items():
            if c not in r["universe"]:
                continue
            mins = r["mfs"]
            (row["in_a_minimal_set_under"] if any(c in m["retained_components"] for m in mins) else row["in_no_minimal_set_under"]).append(cid)
            if c in r["classification"]["necessary_core"]:
                row["necessary_under"].append(cid)
        row["conditionally_redundant"] = bool(row["in_a_minimal_set_under"] and row["in_no_minimal_set_under"])
        comp = []
        for cid, r in results.items():
            base = r["condition"]["degrades"]
            if base and base in results and c in r["universe"] and base in row["in_no_minimal_set_under"] and cid in row["in_a_minimal_set_under"]:
                comp.append({"component": c, "redundant_under": base, "needed_under": cid})
        row["compensatory"] = comp
        out[c] = row
    return out


def digest_of(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
