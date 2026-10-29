"""MEOS-0, fifth stage, experiment L: configurations that survive a stress arriving in mid-run, and a controller that uses them.

Why. Experiment F finds the sets that suffice when everything else is removed at tick 0. The diagnosis of experiment I (docs/ecosystem/experiments_stage5_adaptive_diagnosis.json) showed that such sets are already wholly enabled in the full arrangement, so a controller built on them has nothing to do while a
stress that arrives in mid-run collapses the run. This experiment asks the question the diagnosis left open, in three parts:

  L1  existence     for each stress of experiment I (arriving at tick 100): of every set R of components a controller could leave enabled at tick 113 (the tick of the first decision of the adaptive controller), which keep the
                    operation? Every subset is run (search seeds 1-5; a set *persists* only if it persists on all five) and the candidates are validated on seeds 6-10, never mixed with the search seeds.
  L2  library       the cheapest validated action for each sensed signature (what the controller senses at its first decision), chosen on the search seeds only.
  L3  controller    ``adaptive_mid`` (the adaptive controller with that library and the ability to shed) against none, the fixed M2 fallback and the original adaptive controller on fresh seeds 11-30.

Limit, stated where it matters: the stresses of L3 are the stresses of L1/L2 (the library is built for them, on other seeds), so L3 tests whether an action exists and a controller can find it by sensing; it does not test generalisation to a stress the library has never seen.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from . import engine as E
from . import experiments as X
from . import mfs5 as M
from . import reconf as RC
from . import stage5_experiments as X5
from . import stats5 as ST

T_ACT = 113  # the first decision of the adaptive controller (stress at 100 + sensing + debounce), in every scenario where it decided
HORIZON = 300  # the horizon of experiment I
SEARCH_SEEDS = (1, 2, 3, 4, 5)
VALIDATION_SEEDS = (6, 7, 8, 9, 10)
EVAL_SEEDS = tuple(range(11, 31))
UNIVERSE = M.COMPONENTS5
UNAVAILABLE = {"history lost": ("history",), "renewal disabled": ("feedback",)}  # components the stress itself removes: no action can restore them
STRESSES = tuple(k for k in X5.SCENARIOS if not k.startswith("no stress"))
ARRANGEMENT = {"tap": M.M2_BASE, "tap_feature": "direct", "universe": M.COMPONENTS5}


def free_components(scen: str) -> list[str]:
    return [c for c in UNIVERSE if c not in UNAVAILABLE.get(scen, ())]


def enabled_before(scen: str) -> set[str]:
    """What is enabled when the controller acts: everything except the dormant M2 tap and what the stress removed."""
    return set(free_components(scen)) - {"m2_tap"}


def base_interventions(scen: str) -> list[dict]:
    return [{"tick": 0, "op": "ROUTE", "m2": {"sense": "none"}}, *copy.deepcopy(X5.SCENARIOS[scen][0])]


def action_interventions(scen: str, retained: set | frozenset, t: int = T_ACT) -> list[dict]:
    """Leave exactly ``retained`` enabled at tick ``t``: remove what is enabled and not retained, switch the M2 tap on if it is retained."""
    cur = enabled_before(scen)
    ivs: list[dict] = [{"tick": t, "op": "REMOVE", "target": c} for c in sorted(cur - set(retained))]
    if "m2_tap" in retained:
        ivs.append({"tick": t, "op": "ROUTE", "m2": dict(M.M2_BASE)})
    return ivs


def cost_of(scen: str, retained: set | frozenset) -> int:
    return len(enabled_before(scen) - set(retained)) + (1 if "m2_tap" in retained else 0)


def run(scen: str, retained: set | frozenset | None, seed: int) -> dict:
    cfg = X.cfg_with(E.default_config(), seed=seed, horizon=HORIZON)
    ivs = base_interventions(scen) + ([] if retained is None else action_interventions(scen, retained))
    return E.run_record(cfg, ivs)


def persists(scen: str, retained: set | frozenset | None, seeds: tuple[int, ...]) -> tuple[bool, ...]:
    return tuple(run(scen, retained, sd)["final_status"]["label"] == "ACTIVE" for sd in seeds)


def _job(a: tuple) -> tuple[str, int, tuple[bool, ...]]:
    scen, mask, seeds = a
    free = free_components(scen)
    return scen, mask, persists(scen, frozenset(c for i, c in enumerate(free) if mask >> i & 1), seeds)


def enumerate_actions(scen: str, seeds: tuple[int, ...] = SEARCH_SEEDS, processes: int | None = None) -> dict[int, tuple[bool, ...]]:
    """Persistence of every set R of free components left enabled at T_ACT (bit i of the mask = free_components(scen)[i])."""
    jobs = [(scen, m, seeds) for m in range(1 << len(free_components(scen)))]
    return {m: p for _, m, p in X5.pmap(_job, jobs, processes, chunksize=8)}


def _set(scen: str, mask: int) -> frozenset:
    return frozenset(c for i, c in enumerate(free_components(scen)) if mask >> i & 1)


def l1_existence(scen: str, processes: int | None = None) -> dict:
    table = enumerate_actions(scen, SEARCH_SEEDS, processes)
    ok = {m: all(p) for m, p in table.items()}
    persisting = [m for m, v in ok.items() if v]
    minimal = M.minimal_masks(ok)
    order = sorted(persisting, key=lambda m: (cost_of(scen, _set(scen, m)), -bin(m).count("1"), m))
    cheapest = order[:5]
    full = sum(1 << i for i, c in enumerate(free_components(scen)) if c != "m2_tap")  # no action: the enabled set stays as it is
    rows = []
    for m in cheapest:
        r = _set(scen, m)
        v = persists(scen, r, VALIDATION_SEEDS)
        rows.append({"retained": sorted(r), "cost": cost_of(scen, r), "search_persists": f"{sum(table[m])}/{len(SEARCH_SEEDS)}", "validation_persists": f"{sum(v)}/{len(VALIDATION_SEEDS)}", "validated": all(v)})
    return {"scenario": scen, "free_components": free_components(scen), "sets_tested": len(table), "persisting_on_all_search_seeds": len(persisting), "inclusion_minimal_persisting": len(minimal),
            "no_action_persists_on_search_seeds": all(table[full]),
            "sets_by_search_seeds_persisted": {str(k): sum(1 for p in table.values() if sum(p) == k) for k in range(len(SEARCH_SEEDS) + 1)}, "best_search_seeds_persisted": max(sum(p) for p in table.values()), "cheapest_persisting_sets": rows, "any_validated": any(r["validated"] for r in rows),
            "_ok": ok}


def first_signature(scen: str, seeds: tuple[int, ...] = SEARCH_SEEDS) -> dict[str, str]:
    """What the controller senses at its first decision in this scenario (the modal signature over the seeds), from the adaptive controller's own log."""
    sig: Counter[tuple[tuple[str, str], ...]] = Counter()
    library = M_LIBRARY_STUB
    for sd in seeds:
        cfg = X.cfg_with(E.default_config(), seed=sd, horizon=HORIZON)
        rec = RC.run_controlled(cfg, base_interventions(scen), RC.Controller("adaptive", library, ARRANGEMENT, seed=sd))
        d = [e for e in rec["controller"]["log"] if e["kind"] == "decide"]
        if d:
            sig[tuple(sorted(d[0]["sensed"].items()))] += 1
    return dict(sig.most_common(1)[0][0]) if sig else {}


M_LIBRARY_STUB: list[dict] = []  # an empty library: the adaptive controller then only senses and logs; it never acts (nothing to match)


def l2_library(l1: dict[str, dict]) -> tuple[list[dict], dict]:
    """One entry per sensed signature: among the sets that persist on all search seeds in **every** scenario that shares the signature, the cheapest (the sets are chosen on the search seeds; validation is reported
    afterwards, never used to choose)."""
    sigs = {s: first_signature(s) for s in STRESSES}
    groups: dict[tuple, list[str]] = {}
    for s, g in sigs.items():
        groups.setdefault(tuple(sorted(g.items())), []).append(s)
    lib, report = [], {}
    for key, scens in groups.items():
        sets = None
        for s in scens:
            t = {m for m, v in l1[s]["_ok"].items() if v}
            names = {_set(s, m) for m in t}
            sets = names if sets is None else sets & names
        shared = sorted(sets or [], key=lambda r: (max(cost_of(s, r) for s in scens), -len(r), sorted(r)))
        entry = {"signature": dict(key), "scenarios": scens, "shared_persisting_sets": len(shared)}
        if shared:
            r = shared[0]
            entry.update(retained=sorted(r), cost=max(cost_of(s, r) for s in scens), validation={s: f"{sum(persists(s, r, VALIDATION_SEEDS))}/{len(VALIDATION_SEEDS)}" for s in scens})
            lib.append({"id": "MID-" + "+".join(s.split(" ")[0] for s in scens), "condition_id": "mid-run", "condition": "; ".join(scens), "features": {**dict(key), "tap": "direct"}, "retained": sorted(r), "removed": [], "cardinality": len(r),
                        "route_kind": "action that survives a stress in mid-run", "retained_paths": [], "lost_paths": [], "digest": ""})
        else:
            entry.update(retained=None, note="no set persists in every scenario that shares this signature: the sensed signature cannot tell these stresses apart and no single action serves them")
        report["+".join(scens)] = entry
    return lib, report


def l3_controller(library_mid: list[dict], library_f: list[dict], processes: int | None = None) -> dict:
    kinds = ("none", "fixed", "adaptive", "adaptive_mid")
    jobs = [(scen, kind, seed, library_mid if kind == "adaptive_mid" else library_f, ARRANGEMENT) for scen in ("no stress (control for false switches)", *STRESSES) for kind in kinds for seed in EVAL_SEEDS]
    res = X5.pmap(X5._i_job, jobs, processes, chunksize=4)
    by: dict[tuple[str, str], list[dict]] = {}
    for r in res:
        by.setdefault((r["scenario"], r["controller"]), []).append(r)
    rows = []
    for (scen, kind), rs in by.items():
        n, k = len(rs), sum(1 for r in rs if r["active_at_end"])
        rows.append({"scenario": scen, "controller": kind, "n": n, "persisted": ST.proportion(k, n), "mean_switches": round(sum(r["switch_count"] for r in rs) / n, 2), "mean_switching_cost": round(sum(r["switching_cost"] for r in rs) / n, 2),
                     "false_switches": sum(r["false_switches"] for r in rs), "mean_energy": round(sum(r["energy"] for r in rs) / n, 2)})
    return {"rows": rows}


def verdicts(l3: dict) -> list[dict]:
    """Fixed before the run: a controller is *effective* in a scenario if its persistence exceeds that of no reconfiguration by at least 30 percentage points AND Fisher exact p < 0.05 AND mean switching cost <= 3; *harmful* if it is lower by
    that margin with p < 0.05; otherwise *no effect*. Holm adjustment over all comparisons is reported next to the unadjusted p."""
    idx = {(r["scenario"], r["controller"]): r for r in l3["rows"]}
    out = []
    for scen in STRESSES:
        ctl = idx[(scen, "none")]
        for kind in ("fixed", "adaptive", "adaptive_mid"):
            r = idx[(scen, kind)]
            c = ST.compare_proportions(r["persisted"]["k"], r["persisted"]["n"], ctl["persisted"]["k"], ctl["persisted"]["n"])
            d = r["persisted"]["p"] - ctl["persisted"]["p"]
            out.append({"scenario": scen, "controller": kind, "persisted": f"{r['persisted']['k']}/{r['persisted']['n']}", "none": f"{ctl['persisted']['k']}/{ctl['persisted']['n']}", "difference": round(d, 3), "cohens_h": c["cohens_h"], "fisher_p": c["fisher_exact_p"],
                        "mean_switching_cost": r["mean_switching_cost"], "false_switches": r["false_switches"], "_d": d})
    from .stage5_final import holm
    adj = holm([o["fisher_p"] for o in out])
    for o, a in zip(out, adj, strict=True):
        o["holm_p"] = a
        d = o.pop("_d")
        o["verdict"] = "effective" if d >= 0.30 and o["fisher_p"] < 0.05 and o["mean_switching_cost"] <= 3 else "harmful" if d <= -0.30 and o["fisher_p"] < 0.05 else "no effect"
        o["survives_holm"] = a < 0.05
    return out


SAVED = Path(__file__).resolve().parents[3] / "docs" / "ecosystem" / "experiments_stage5.json"


def run_all(processes: int | None = None) -> dict[str, Any]:
    l1 = {s: l1_existence(s, processes) for s in STRESSES}
    lib_mid, lib_report = l2_library(l1)
    for s in STRESSES:
        l1[s].pop("_ok")  # the full per-set tables were needed to build the library; the saved rows keep the counts
    lib_f = RC.library_from(json.loads(SAVED.read_text())["experiments"]["F"]["by_condition"])
    l3 = l3_controller(lib_mid, lib_f, processes)
    return {"L1_existence": l1, "L2_library": lib_report, "library_entries": lib_mid, "L3_controller": l3, "L3_verdicts": verdicts(l3)}
