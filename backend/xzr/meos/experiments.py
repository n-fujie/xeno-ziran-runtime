"""MEOS-0 experiments, second stage. Every function runs the real engine (seeded, deterministic); nothing is estimated, and no outcome is adjusted toward an expectation.

What is measured is persistence of one specified operation — the recursive cycle (status ACTIVE: at least 2 complete cycles in the last 48 ticks, the latest no older than
24) — in a formal model. A null result, a reversed effect, a conditional necessity or a non-monotone response is recorded as such. The outcomes are properties of this
model's operational relations and say nothing about any physical or biological ecosystem.

Operational state and observed state are kept apart throughout: ``operational_state`` is the status of the run itself; ``observed_state`` is what a configured
observation would conclude; ``observability_status`` says why they differ (see ``analysis.observe``).
"""

from __future__ import annotations

import copy
import itertools
import statistics
from typing import Any

import numpy as np

from . import analysis as A
from . import engine as E

POWER_FINITE = {"infinite": False}
POWER_UNLIMITED = {"infinite": True}
INTERRUPTION = [
    {"tick": 100, "op": "ISOLATE", "target": "interaction_channel"},
    {"tick": 150, "op": "RECONNECT", "target": "interaction_channel"},
]


def cfg_with(base: dict, **over: Any) -> dict:
    c = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(c.get(k), dict):
            c[k].update(v)
        else:
            c[k] = v
    return c


def pulse(tick: int, amount: float, x: int = 3, y: int = 6) -> dict:
    return {"tick": tick, "op": "ALTER_RESOURCE", "inject": {"x": x, "y": y, "amount": amount}}


def trace_metrics(rec: dict) -> dict:
    """The intermediate quantities of one run, reduced: throughput, energy use, renewal count, activity, the share of ticks the target held."""
    T = rec["traces"]
    margin = T["target_margin"]
    log = rec["status_log"]
    collapse = next((s["tick"] for s in log if s["label"] == "COLLAPSED"), None)
    cyc_before = None if collapse is None else sum(1 for c in rec["cycles"] if c["tick"] <= collapse)
    return {
        "resource_throughput": round(sum(T["resource_flow"]), 4),
        "resource_consumed": round(sum(T["resource_consumed"]), 4),
        "resource_renewed": round(sum(T["resource_renewed"]), 4),
        "cumulative_energy_use": round(sum(T["power_draw"]), 4),
        "renewal_count": int(sum(T["renewal_events"])),
        "a1_activity": int(sum(T["a1_fired"])),
        "a2_activity": int(sum(T["a2_fired"])),
        "target_held_share": round(sum(1 for m in margin if m >= 0) / len(margin), 4),
        "final_target_margin": margin[-1],
        "final_power": T["power_reserve"][-1],
        "collapse_tick": collapse,
        "cycles_before_collapse": cyc_before,
        "cycles": len(rec["cycles"]),
        "history_reentry_cycles": sum(1 for c in rec["cycles"] if c["history_reentry"]),
    }


def run_summary(cfg: dict, ivs: list[dict], observation: dict | None = None) -> dict:
    rec = E.run_record(cfg, ivs)
    out = {
        "operational_state": rec["final_status"]["label"],
        "persists": rec["final_status"]["label"] == "ACTIVE",
        **trace_metrics(rec),
        "failed_dependency": (rec["final_status"]["dependency"] or {}).get("detail"),
        "result_digest": rec["result_digest"],
        "trace_digest": rec["trace_digest"],
    }
    if observation is not None:
        o = A.observe(rec, observation)
        out.update(observed_state=o["observed_state"], observability_status=o["observability_status"])
    return out


def _agg(values: list[float]) -> dict:
    v = [x for x in values if x is not None]
    if not v:
        return {"mean": None, "std": None, "min": None, "max": None, "n": 0}
    return {
        "mean": round(statistics.fmean(v), 4),
        "std": round(statistics.pstdev(v), 4) if len(v) > 1 else 0.0,
        "min": round(min(v), 4),
        "max": round(max(v), 4),
        "n": len(v),
    }


# ---------------------------------------------------------------------------------------------------- causal path of an intervention
QUANTITIES = (
    "interaction_strength",
    "a2_activity",
    "resource_renewed",
    "resource_flow",
    "reconfiguration_signal",
    "a1_differentiated",
    "a1_activity",
    "history_contribution_a1",
    "history_contribution_a2",
    "power_balance",
    "address_integrity_a1",
    "address_integrity_a2",
    "cycles_in_window",
    "target_margin",
)


def causal_path(cfg: dict, interventions: list[dict], horizon: int | None = None) -> dict:
    """intervention -> change of the intermediate quantities -> failure of the persistence condition -> COLLAPSED, from two runs of the same seed (with and without the
    intervention): each quantity is compared tick by tick with its counterfactual, and the ticks at which they first depart (for two consecutive ticks, beyond 5 % of the
    counterfactual's range) are ordered. The status is never read from this path: it is the cycle criteria that decide it."""
    c = cfg_with(cfg, **({"horizon": horizon} if horizon else {}))
    base, run = E.run_record(c, []), E.run_record(c, interventions)
    t0 = min((iv["tick"] for iv in interventions), default=0)
    steps = []
    for q in QUANTITIES:
        b, r = np.array(base["traces"][q], float), np.array(run["traces"][q], float)
        tol = max(0.05 * float(np.ptp(b)), 1e-4)
        dev = np.abs(r - b) > tol
        first = next((i for i in range(t0, len(dev) - 1) if dev[i] and dev[i + 1]), None)
        if first is not None:
            steps.append(
                {
                    "quantity": q,
                    "first_departure_tick": first,
                    "counterfactual": round(float(b[first]), 5),
                    "observed": round(float(r[first]), 5),
                }
            )
    steps.sort(key=lambda s: (s["first_departure_tick"], QUANTITIES.index(s["quantity"])))
    margin = run["traces"]["target_margin"]
    fail = next((t for t in range(t0, len(margin)) if margin[t] < 0), None)
    collapse = next((s["tick"] for s in run["status_log"] if s["label"] == "COLLAPSED" and s["tick"] >= t0), None)
    recovery = next(
        (s["tick"] for s in run["status_log"] if s["label"] == "ACTIVE" and collapse is not None and s["tick"] > collapse), None
    )
    chain = [
        f"intervention at tick {t0}: "
        + ", ".join(
            f"{iv['op']} {iv.get('target') or iv.get('path') or iv.get('address_mode') or iv.get('mode') or ''}".strip()
            for iv in interventions
        )
    ]
    chain += [
        f"tick {s['first_departure_tick']}: {s['quantity']} departs from its counterfactual ({s['counterfactual']} -> {s['observed']})"
        for s in steps
    ]
    if fail is not None:
        chain.append(f"tick {fail}: the persistence condition (target margin >= 0) no longer holds")
    if collapse is not None:
        chain.append(f"tick {collapse}: no complete cycle in the last 48 ticks: COLLAPSED (decided by the cycle criteria)")
    if recovery is not None:
        chain.append(f"tick {recovery}: ACTIVE again: the recovery trigger is the intervention (or event) that precedes it")
    return {
        "intervention_ticks": [iv["tick"] for iv in interventions],
        "intermediate_changes": steps,
        "persistence_failure_tick": fail,
        "collapse_tick": collapse,
        "recovery_tick": recovery,
        "collapse_trigger": steps[0] if steps and collapse is not None else None,
        "chain": chain,
        "final_operational_state": run["final_status"]["label"],
        "judgement": "the status is derived from counted cycles; the dependency label is an explanation, never an input",
    }


# ---------------------------------------------------------------------------------------------------- history x gradient x power
def _conditions() -> list[dict]:
    out = []
    for power in ("finite", "unlimited"):
        for gradient in (True, False):
            for history in (True, False):
                out.append({"history": history, "gradient": gradient, "power": power})
    return out


def condition_ivs(c: dict) -> list[dict]:
    ivs = []
    if not c["history"]:
        ivs.append({"tick": 0, "op": "REMOVE", "target": "history"})
    if not c["gradient"]:
        ivs.append({"tick": 0, "op": "REMOVE", "target": "resource_gradient"})
    return ivs


def factorial_history_gradient_power(cfg: dict, seeds: tuple[int, ...] = tuple(range(1, 11))) -> dict:
    """The eight conditions of history (on/off) x resource gradient (on/off) x power (finite/unlimited): same initial conditions, the same seed set, the same 240-tick
    evaluation. Recovery possibility = the interaction channel cut at 100 and restored at 150 with a resource pulse of 2.0 at 151 (horizon 360): is the operation back?"""
    rows = []
    for c in _conditions():
        base = cfg_with(cfg, power=POWER_UNLIMITED if c["power"] == "unlimited" else POWER_FINITE, horizon=240)
        long = cfg_with(base, horizon=360)
        per = []
        for sd in seeds:
            r = run_summary(cfg_with(base, seed=sd), condition_ivs(c))
            rec = run_summary(cfg_with(long, seed=sd), [*condition_ivs(c), *INTERRUPTION, pulse(151, 2.0)])
            per.append({**r, "recovers_after_interruption": rec["persists"]})
        keys = (
            "resource_throughput",
            "cumulative_energy_use",
            "renewal_count",
            "a1_activity",
            "a2_activity",
            "target_held_share",
            "cycles",
            "collapse_tick",
            "cycles_before_collapse",
        )
        rows.append(
            {
                "condition": c,
                "persists_seeds": sum(1 for p in per if p["persists"]),
                "seeds": len(seeds),
                "operational_state": "ACTIVE"
                if all(p["persists"] for p in per)
                else "COLLAPSED"
                if not any(p["persists"] for p in per)
                else "MIXED",
                "recovery_possible_seeds": sum(1 for p in per if p["recovers_after_interruption"]),
                **{k: _agg([p[k] for p in per]) for k in keys},
                "result_digests": [p["result_digest"] for p in per],
            }
        )
    lookup = {(r["condition"]["history"], r["condition"]["gradient"], r["condition"]["power"]): r for r in rows}
    effects = []
    for g in (True, False):
        for pw in ("finite", "unlimited"):
            on, off = lookup[(True, g, pw)], lookup[(False, g, pw)]
            effects.append(
                {
                    "gradient": g,
                    "power": pw,
                    "history_on": on["operational_state"],
                    "history_off": off["operational_state"],
                    "history_is_necessary": on["operational_state"] == "ACTIVE" and off["operational_state"] == "COLLAPSED",
                    "history_is_reversed": on["operational_state"] == "COLLAPSED" and off["operational_state"] == "ACTIVE",
                    "difference_in_cycles": round(on["cycles"]["mean"] - off["cycles"]["mean"], 3),
                }
            )
    return {
        "question": "under which environment, resource and power conditions is history necessary for the specified operation to persist?",
        "operation": "recursive cycle sustained: status ACTIVE at tick 239",
        "seeds": list(seeds),
        "rows": rows,
        "history_effect_by_condition": effects,
    }


def history_necessity_map(
    cfg: dict,
    charges: tuple[float, ...] = (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0, 1.5, 2.0),
    capacities: tuple[float, ...] = (12.0, 24.0, 48.0),
    seeds: tuple[int, ...] = (1, 2, 3),
) -> dict:
    """Where in the (power recharge rate x reserve capacity) plane the operation persists with history, without it, with both or with neither."""
    cells = []
    for cap in capacities:
        for ch in charges:
            outcome = {}
            for hist in (True, False):
                ok = []
                for sd in seeds:
                    c = cfg_with(cfg, seed=sd, power={"capacity": cap, "reserve": cap, "charge": ch}, horizon=240)
                    ok.append(
                        E.run_record(c, [] if hist else [{"tick": 0, "op": "REMOVE", "target": "history"}])["final_status"][
                            "label"
                        ]
                        == "ACTIVE"
                    )
                outcome[hist] = all(ok) if all(ok) or not any(ok) else None
            cls = (
                "history necessary"
                if outcome[True] and outcome[False] is False
                else "persists without history"
                if outcome[True] and outcome[False]
                else "history reversed (persists only without)"
                if outcome[True] is False and outcome[False]
                else "collapses either way"
                if outcome[True] is False and outcome[False] is False
                else "seed-dependent"
            )
            cells.append(
                {"charge": ch, "capacity": cap, "with_history": outcome[True], "without_history": outcome[False], "class": cls}
            )
    return {"axes": {"charge": list(charges), "capacity": list(capacities)}, "seeds": list(seeds), "cells": cells}


# ---------------------------------------------------------------------------------------------------- the minimal operational configuration, restated
def _identity(rec: dict, base_rec: dict) -> dict:
    """Does a configuration that persists preserve the SAME operation? The chain of every cycle must be the full four-link chain; the cycle rate and the use of history
    are reported against the unreduced run, so that a persistence that is a different regime is visible."""

    def period(r: dict) -> float | None:
        t = [c["tick"] for c in r["cycles"]]
        return round(float(statistics.median(np.diff(t).tolist())), 3) if len(t) > 2 else None

    ids = {e["id"] for e in rec["events"]}
    full = all(
        all(c[k] in ids for k in ("a1_act", "a2_fire", "reconfigure", "a1_fire")) for c in rec["events"] if c["kind"] == "cycle"
    )
    return {
        "every_cycle_has_the_full_four_link_chain": full,
        "cycle_period_median": period(rec),
        "cycle_period_median_unreduced": period(base_rec),
        "history_reentry_share": round(sum(1 for c in rec["cycles"] if c["history_reentry"]) / max(1, len(rec["cycles"])), 3),
        "history_reentry_share_unreduced": round(
            sum(1 for c in base_rec["cycles"] if c["history_reentry"]) / max(1, len(base_rec["cycles"])), 3
        ),
        "power_draw_per_cycle": round(sum(rec["traces"]["power_draw"]) / max(1, len(rec["cycles"])), 4),
        "power_draw_per_cycle_unreduced": round(sum(base_rec["traces"]["power_draw"]) / max(1, len(base_rec["cycles"])), 4),
    }


def minimal_configurations(
    cfg: dict,
    seeds: tuple[int, ...] = (1,),
    horizon: int = 160,
    observation: dict | None = None,
    components: tuple[str, ...] | None = None,
) -> dict:
    """The minimal relational operational configurations relative to the specified operation, physical conditions, scale, observation condition and admissible reductions.

    EVERY subset of the admissible components is run (2^n runs per seed); a retained set preserves the operation if the run is ACTIVE for every seed. A preserving set is
    inclusion-minimal if no proper subset of it preserves the operation (checked against all the evaluated subsets, not assumed from monotonicity); all minimal sets are
    reported, whatever their number, with their cardinalities, and the identity of the preserved operation is checked for each."""
    comps = list(components or E.COMPONENTS)
    cfg = cfg_with(cfg, horizon=horizon)
    results: dict[frozenset, dict] = {}
    base_rec = E.run_record(cfg_with(cfg, seed=seeds[0]), [])
    for r in range(len(comps) + 1):
        for removed in itertools.combinations(comps, r):
            retained = frozenset(comps) - set(removed)
            ok, obs_ok, last = [], [], None
            for sd in seeds:
                rec = E.run_record(cfg_with(cfg, seed=sd), [{"tick": 0, "op": "REMOVE", "target": c} for c in removed])
                ok.append(rec["final_status"]["label"] == "ACTIVE")
                if observation is not None:
                    obs_ok.append(A.observe(rec, observation)["observed_state"] == "ACTIVE")
                last = rec
            results[retained] = {
                "retained": sorted(retained),
                "removed": sorted(removed),
                "persists": all(ok),
                "observed_persists": all(obs_ok) if observation is not None else None,
                "_rec": last,
            }
    survivors = [k for k, v in results.items() if v["persists"]]
    minimal = [k for k in survivors if not any(t < k for t in survivors)]
    obs_survivors = [k for k, v in results.items() if v["observed_persists"]] if observation is not None else []
    obs_minimal = [k for k in obs_survivors if not any(t < k for t in obs_survivors)]
    candidates = []
    for k in sorted(minimal, key=lambda s: (len(s), sorted(s))):
        subs = [{"removed_additionally": c, "persists": results[k - {c}]["persists"]} for c in sorted(k)]
        candidates.append(
            {
                "retained": sorted(k),
                "cardinality": len(k),
                "every_proper_subset_fails": not any(t < k for t in survivors),
                "single_removals": subs,
                "operation_identity": _identity(results[k]["_rec"], base_rec),
            }
        )
    return {
        "preserved_operation": "recursive cycle sustained (status ACTIVE at the end of the run)",
        "environment_condition": {
            "power": cfg["power"],
            "gradient": cfg["environment"]["gradient"],
            "persistence": cfg["environment"]["persistence"],
            "renew_efficiency": cfg["environment"].get("renew_efficiency", 1.0),
        },
        "observation_condition": observation or "none (operational state)",
        "scale": cfg["sss"],
        "temporal_window": {"status_window_ticks": 48, "horizon": cfg["horizon"], "seeds": list(seeds)},
        "allowed_reduction_operations": comps,
        "subsets_evaluated": len(results),
        "sets_that_preserve": len(survivors),
        "minimal_sets": candidates,
        "minimal_set_count": len(minimal),
        "minimum_cardinality": min((len(k) for k in minimal), default=None),
        "observed_minimal_sets": [sorted(k) for k in obs_minimal] if observation is not None else None,
        "non_monotone_examples": [
            {
                "removed_alone_persists": results[frozenset(comps) - {c}]["persists"],
                "component": c,
                "removed_together_with": sorted(set(comps) - set(k) - {c}),
            }
            for k in survivors
            for c in comps
            if c not in k and not results[frozenset(comps) - {c}]["persists"]
        ][:12],
        "all_subsets": [{kk: vv for kk, vv in v.items() if kk != "_rec"} for v in results.values()],
    }


# ---------------------------------------------------------------------------------------------------- XenoBody boundaries
def history_access_run(cfg: dict, access: dict[str, bool], seed: int | None = None) -> dict:
    c = cfg_with(cfg, history={"access": access}, **({"seed": seed} if seed else {}))
    return run_summary(c, [])


def boundary_experiments(cfg: dict, seeds: tuple[int, ...] = (1, 2, 3)) -> dict:
    """Five different things a boundary change can be, kept apart: (1) the observation boundary (what is seen), (2) the operational coupling (what is connected),
    (3) the resource-exchange boundary, (4) the history-access boundary, (5) the Address Domain boundary. For each, what changed in operation, coupling, resource exchange,
    history accessibility, observation and recovery."""
    obs_all = {"sampling_interval": 1}
    kinds: list[dict] = [
        {"kind": "none (unperturbed)", "ivs": [], "config": {}, "observation": obs_all},
        {
            "kind": "observation boundary: the observer's region excludes A2's habitat",
            "ivs": [],
            "config": {},
            "observation": {"sampling_interval": 1, "region": [0, 0, 2, 13]},
        },
        {
            "kind": "operational coupling cut (interaction channel)",
            "ivs": [{"tick": 0, "op": "REMOVE", "target": "interaction_channel"}],
            "config": {},
            "observation": obs_all,
        },
        {
            "kind": "resource-exchange boundary (renewal feedback)",
            "ivs": [{"tick": 0, "op": "REMOVE", "target": "feedback"}],
            "config": {},
            "observation": obs_all,
        },
        {
            "kind": "resource-exchange boundary (power recharge and source renewal)",
            "ivs": [{"tick": 0, "op": "REMOVE", "target": "resource_renewal"}],
            "config": {},
            "observation": obs_all,
        },
        {
            "kind": "history-access boundary: A1 only",
            "ivs": [],
            "config": {"history": {"access": {"A1": True, "A2": False}}},
            "observation": obs_all,
        },
        {
            "kind": "history-access boundary: A2 only",
            "ivs": [],
            "config": {"history": {"access": {"A1": False, "A2": True}}},
            "observation": obs_all,
        },
        {
            "kind": "history-access boundary: neither",
            "ivs": [],
            "config": {"history": {"access": {"A1": False, "A2": False}}},
            "observation": obs_all,
        },
        {
            "kind": "Address Domain boundary: arena radius 2",
            "ivs": [{"tick": 0, "op": "CHANGE_BOUNDARY", "arena_radius": 2}],
            "config": {},
            "observation": obs_all,
        },
        {
            "kind": "Address Domain boundary: A2 reassigned to (9, 6)",
            "ivs": [{"tick": 0, "op": "ADDRESS", "target": "A2", "mode": "reassign", "x": 9, "y": 6}],
            "config": {},
            "observation": obs_all,
        },
    ]
    rows = []
    for k in kinds:
        per = []
        for sd in seeds:
            c = cfg_with(cfg, seed=sd, **k["config"])
            rec = E.run_record(c, k["ivs"])
            tm = trace_metrics(rec)
            o = A.observe(rec, k["observation"])
            long = E.run_record(cfg_with(c, horizon=360), [*k["ivs"], *INTERRUPTION, pulse(151, 2.0)])
            T = rec["traces"]
            per.append(
                {
                    "operation": rec["final_status"]["label"],
                    "coupling_mean_interaction_strength": round(float(np.mean(T["interaction_strength"])), 5),
                    "resource_exchange_renewed": tm["resource_renewed"],
                    "history_accessibility_mean_threshold_reduction": round(
                        float(np.mean(np.array(T["history_contribution_a1"]) + np.array(T["history_contribution_a2"]))), 5
                    ),
                    "observed_state": o["observed_state"],
                    "observability_status": o["observability_status"],
                    "recovery_after_interruption": long["final_status"]["label"],
                }
            )
        rows.append(
            {
                "boundary_change": k["kind"],
                "seeds": len(seeds),
                "per_seed": per,
                "operation_persists_in_all_seeds": all(p["operation"] == "ACTIVE" for p in per),
            }
        )
    return {
        "dimensions": ["operation", "coupling", "resource exchange", "history accessibility", "observation", "recovery"],
        "rows": rows,
    }


def body_closure(cfg: dict) -> dict:
    """Which relation closes for the first time in B3. Every set between B1 and B3 (B1 plus any subset of what B3 adds) is run with only those operational components
    retained; the minimal persisting ones are reported with the relation each contributes."""
    parts = A.PARTITIONS
    b1, b3 = set(parts["B1"]["components"]), set(parts["B3"]["components"])
    extra = sorted(b3 - b1)
    result = []
    for r in range(len(extra) + 1):
        for add in itertools.combinations(extra, r):
            body = sorted(b1 | set(add))
            outside = [c for c in A.BODY_COMPONENTS if c not in body]
            s = run_summary(cfg, [{"tick": 0, "op": "REMOVE", "target": c} for c in outside])
            result.append(
                {
                    "body": body,
                    "added_to_B1": list(add),
                    "persists": s["persists"],
                    "state": s["operational_state"],
                    "legs_closed": sum(A.legs_inside(body).values()),
                }
            )
    persisting = [x for x in result if x["persists"]]
    minimal = [x for x in persisting if not any(set(y["added_to_B1"]) < set(x["added_to_B1"]) for y in persisting)]
    return {
        "b1": sorted(b1),
        "b3": sorted(b3),
        "added_by_b3": extra,
        "sets_evaluated": len(result),
        "minimal_persisting_bodies": minimal,
        "closing_relation": "the relations that every minimal persisting body adds to B1: "
        + ", ".join(sorted(set.intersection(*[set(m["added_to_B1"]) for m in minimal])))
        if minimal
        else "no body between B1 and B3 persists",
        "all": result,
    }


# ---------------------------------------------------------------------------------------------------- recovery
def _recovery_metrics(rec: dict, t_event: int, base_rec: dict) -> dict:
    T = rec["traces"]
    log = rec["status_log"]
    rec_tick = next((s["tick"] for s in log if s["label"] == "ACTIVE" and s["tick"] > t_event), None)
    final = rec["final_status"]["label"]
    out: dict[str, Any] = {"final_state": final, "recovered": rec_tick is not None, "recovery_tick": rec_tick}
    if rec_tick is None:
        return {**out, "region": "no recovery", "latency": None, "sustained_ticks": 0, "recollapsed": False}
    nxt = next((s["tick"] for s in log if s["tick"] > rec_tick and s["label"] != "ACTIVE"), None)
    sustained = (nxt if nxt is not None else len(T["t"])) - rec_tick
    cyc = [c["tick"] for c in rec["cycles"] if c["tick"] >= rec_tick]
    iv = np.diff(cyc[:12]) if len(cyc) > 3 else np.array([])
    fires1 = [t for t in range(len(T["t"])) if T["a1_fired"][t] and t >= rec_tick][:8]
    fires2 = [t for t in range(len(T["t"])) if T["a2_fired"][t] and t >= rec_tick][:8]
    lag = [min((b - a for b in fires2 if b >= a), default=None) for a in fires1]
    lag = [x for x in lag if x is not None]
    pre = [t for t in range(60, t_event) if base_rec["traces"]["history_trace_a1"][t] is not None]
    return {
        **out,
        "region": "overshoot / re-collapse" if final != "ACTIVE" else "recovery",
        "latency": rec_tick - t_event,
        "sustained_ticks": sustained,
        "recollapsed": nxt is not None and final != "ACTIVE",
        "post_recovery_cycle_period_cv": round(float(iv.std() / iv.mean()), 4) if len(iv) > 2 and iv.mean() > 0 else None,
        "history_trace_after_vs_unperturbed": [
            round(float(np.mean(T["history_trace_a1"][rec_tick : rec_tick + 40])), 4),
            round(float(np.mean(base_rec["traces"]["history_trace_a1"][60:100])), 4),
        ]
        if pre
        else None,
        "energy_reserve_at_recovery": [round(T["power_reserve"][rec_tick], 3), round(T["a1_energy"][rec_tick], 3)],
        "a1_a2_lag_after_recovery": round(float(np.mean(lag)), 3) if lag else None,
        "a1_a2_lag_unperturbed": None,
    }


def recovery_phase(
    cfg: dict,
    amounts: tuple[float, ...] | None = None,
    seeds: tuple[int, ...] = (1, 2, 3),
    scenario: str = "interaction cut 100-150",
) -> dict:
    """The response to a resource pulse after an interruption, swept finely: no-recovery, recovery and overshoot / re-collapse regions, over several seeds, with what
    recovery consists of (latency, how long it is sustained, stability, history reconstruction, energy, A1/A2 resynchronisation)."""
    amounts = amounts or tuple(round(0.25 * i, 2) for i in range(0, 25))
    interruption = (
        INTERRUPTION
        if scenario.startswith("interaction")
        else [{"tick": 100, "op": "REMOVE", "target": "A2"}, {"tick": 150, "op": "RECONNECT", "target": "A2"}]
    )
    base_by_seed = {sd: E.run_record(cfg_with(cfg, seed=sd, horizon=360), []) for sd in seeds}
    rows = []
    for a in amounts:
        per = []
        for sd in seeds:
            ivs = [*interruption, *([pulse(151, a)] if a > 0 else [])]
            rec = E.run_record(cfg_with(cfg, seed=sd, horizon=360), ivs)
            per.append({"seed": sd, **_recovery_metrics(rec, 150, base_by_seed[sd])})
        regions = [p["region"] for p in per]
        majority = max(set(regions), key=regions.count)
        rows.append(
            {
                "amount": a,
                "region": majority
                if regions.count(majority) == len(regions)
                else "seed-dependent: " + "/".join(sorted(set(regions))),
                "per_seed": per,
            }
        )
    recovering = [r["amount"] for r in rows if r["region"] in ("recovery", "overshoot / re-collapse")]
    lo, hi = (min(recovering), max(recovering)) if recovering else (None, None)
    for r in rows:  # a failure to recover is of two kinds: too little inserted, or too much
        if r["region"] == "no recovery" and lo is not None:
            r["region"] = (
                "no recovery (below the band)"
                if r["amount"] < lo
                else "no recovery (above the band: excess pulse)"
                if r["amount"] > hi
                else "no recovery"
            )
    order = [r["region"] for r in rows]
    names = ["no recovery (below the band)", "recovery", "overshoot / re-collapse", "no recovery (above the band: excess pulse)"]
    return {
        "scenario": scenario,
        "pulse": "resource inserted at A1's cell (3, 6) one tick after the interruption ends",
        "seeds": list(seeds),
        "rows": rows,
        "regions": {k: [r["amount"] for r in rows if r["region"] == k] for k in sorted(set(order))},
        "recovery_band": [lo, hi],
        "response_is_monotone": all(
            names.index(order[i]) <= names.index(order[i + 1])
            for i in range(len(order) - 1)
            if order[i] in names and order[i + 1] in names
        )
        and "no recovery (above the band: excess pulse)" not in order,
    }


# ---------------------------------------------------------------------------------------------------- SSS regions
def sss_phase(
    cfg: dict,
    scales=(0.5, 1.0, 1.5),
    sizes=(0.5, 1.0, 1.5, 2.0),
    speeds=(0.5, 0.75, 1.0, 1.5, 2.0),
    seeds: tuple[int, ...] = (1, 2),
) -> dict:
    """The (scale, size, speed) space split into: ACTIVE, metastable (ACTIVE at tick 239 but not at 479, or seeds disagree), COLLAPSED, recovery-capable (a collapsed
    configuration that a resource pulse restores), observation-sensitive (ACTIVE, yet an observation at interval 2 concludes COLLAPSED)."""
    points = []
    for sc in scales:
        for sz in sizes:
            for sp in speeds:
                per = []
                for sd in seeds:
                    c = cfg_with(cfg, seed=sd, horizon=480, sss={"scale": sc, "size": sz, "speed": sp})
                    rec = E.run_record(c, [])
                    s239, s479 = rec["frames"][239]["status"], rec["frames"][-1]["status"]
                    obs = A.observe(rec, {"sampling_interval": 2})["observed_state"]
                    rec_cap = None
                    if s239 != "ACTIVE":
                        r2 = E.run_record(c, [pulse(300, 2.0)])
                        rec_cap = r2["final_status"]["label"] == "ACTIVE" and rec["final_status"]["label"] != "ACTIVE"
                    per.append({"at_239": s239, "at_479": s479, "observed_interval_2": obs, "recovery_capable": rec_cap})
                if all(p["at_239"] == "ACTIVE" and p["at_479"] == "ACTIVE" for p in per):
                    cls = "ACTIVE"
                elif all(p["at_239"] != "ACTIVE" for p in per):
                    cls = "COLLAPSED"
                else:
                    cls = "metastable"
                points.append(
                    {
                        "scale": sc,
                        "size": sz,
                        "speed": sp,
                        "class": cls,
                        "recovery_capable": any(p["recovery_capable"] for p in per) if cls != "ACTIVE" else None,
                        "observation_sensitive": cls == "ACTIVE" and all(p["observed_interval_2"] != "ACTIVE" for p in per),
                        "per_seed": per,
                    }
                )
    counts: dict[str, int] = {}
    for p in points:
        counts[p["class"]] = counts.get(p["class"], 0) + 1
    return {
        "axes": {"scale": list(scales), "size": list(sizes), "speed": list(speeds)},
        "seeds": list(seeds),
        "points": points,
        "counts": counts,
        "recovery_capable_points": sum(1 for p in points if p["recovery_capable"]),
        "observation_sensitive_points": sum(1 for p in points if p["observation_sensitive"]),
    }


# ---------------------------------------------------------------------------------------------------- Address Domain
def address_experiments(cfg: dict, seeds: tuple[int, ...] = (1, 2, 3)) -> dict:
    """Address loss, reassignment, fragmentation, collision and partial addressability, each applied at tick 100 for 30 ticks and then restored (reassignment: moved
    away, then back), with and without a resource pulse after the restoration: does the operation survive, collapse, recover?"""
    cases: list[tuple[str, list[dict], list[dict]]] = []
    for tgt in ("A1", "A2", "both"):
        cases.append(
            (
                f"address loss of {tgt}",
                [{"tick": 100, "op": "ADDRESS", "target": tgt, "mode": "loss"}],
                [{"tick": 130, "op": "ADDRESS", "target": tgt, "mode": "restore"}],
            )
        )
        cases.append(
            (
                f"collision ({tgt} given the other's address)",
                [{"tick": 100, "op": "ADDRESS", "target": tgt if tgt != "both" else "A2", "mode": "collision"}],
                [
                    {
                        "tick": 130,
                        "op": "ADDRESS",
                        "target": tgt if tgt != "both" else "A2",
                        "mode": "reassign",
                        "x": 5 if tgt != "A1" else 3,
                        "y": 6,
                    }
                ],
            )
        )
    for f in (0.25, 0.5, 0.75):
        cases.append(
            (
                f"fragmentation of A2's addressable window to {int(f * 100)} %",
                [{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "fragment", "fraction": f}],
                [{"tick": 130, "op": "ADDRESS", "target": "A2", "mode": "restore"}],
            )
        )
        cases.append(
            (
                f"partial addressability of A2 ({int(f * 100)} % of steps)",
                [{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "partial", "fraction": f}],
                [{"tick": 130, "op": "ADDRESS", "target": "A2", "mode": "restore"}],
            )
        )
        cases.append(
            (
                f"partial addressability of A1 ({int(f * 100)} % of steps)",
                [{"tick": 100, "op": "ADDRESS", "target": "A1", "mode": "partial", "fraction": f}],
                [{"tick": 130, "op": "ADDRESS", "target": "A1", "mode": "restore"}],
            )
        )
    cases.append(
        (
            "A2 reassigned to (9, 6), never restored",
            [{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "reassign", "x": 9, "y": 6}],
            [],
        )
    )
    cases.append(
        (
            "A2 reassigned to (9, 6), then back to (5, 6)",
            [{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "reassign", "x": 9, "y": 6}],
            [{"tick": 130, "op": "ADDRESS", "target": "A2", "mode": "reassign", "x": 5, "y": 6}],
        )
    )
    rows = []
    for name, fault, restore in cases:
        per = []
        for sd in seeds:
            c = cfg_with(cfg, seed=sd, horizon=360)
            during = E.run_record(c, fault)
            restored = E.run_record(c, [*fault, *restore])
            pulsed = E.run_record(c, [*fault, *restore, pulse(131, 2.0)])
            per.append(
                {
                    "fault_only": during["final_status"]["label"],
                    "restored": restored["final_status"]["label"],
                    "restored_and_pulse": pulsed["final_status"]["label"],
                    "cycles_restored": len(restored["cycles"]),
                }
            )
        rows.append({"case": name, "seeds": len(seeds), "per_seed": per})
    return {"modes": list(E.ADDRESS_MODES), "rows": rows}


# ---------------------------------------------------------------------------------------------------- M2
def m2_experiment(cfg: dict, seeds: tuple[int, ...] = (1, 2, 3)) -> dict:
    """Does connecting A2's alteration M2 to A1's sensing make any difference? Four conditions (none, direct, delayed, noisy) at three weights, over scenarios that test
    persistence and reconstitution. A difference is reported only if the outcome or the measured quantities differ from ``none``; otherwise it is "no difference"."""
    scenarios = {
        "unperturbed": ([], {}),
        "interaction cut 100-150 + pulse 2.0": ([*INTERRUPTION, pulse(151, 2.0)], {"horizon": 360}),
        "interaction cut 100-150, no pulse": (INTERRUPTION, {"horizon": 360}),
        "scale 1.5": ([{"tick": 0, "op": "ALTER_SSS", "scale": 1.5}], {}),
        "renewal efficiency 0.7 at 100": (
            [{"tick": 100, "op": "RECONFIGURE", "path": "environment.renew_efficiency", "value": 0.7}],
            {"horizon": 300},
        ),
        "unlimited power": ([], {"power": POWER_UNLIMITED}),
        "A2 partially addressable (50 %) from 100": (
            [{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "partial", "fraction": 0.5}],
            {},
        ),
    }
    conds = [("none", 0.0, {"sense": "none"})]
    for w in (0.25, 0.5, 1.0, 2.0, 4.0):
        conds += [
            (f"direct w={w}", w, {"sense": "direct", "weight": w}),
            (f"delayed(3) w={w}", w, {"sense": "delayed", "weight": w, "delay": 3}),
            (f"noisy(0.05) w={w}", w, {"sense": "noisy", "weight": w, "noise": 0.05}),
        ]
    rows = []
    for sname, (ivs, over) in scenarios.items():
        ref = None
        for cname, _w, m2 in conds:
            per = [run_summary(cfg_with(cfg, seed=sd, m2=m2, **over), ivs) for sd in seeds]
            agg = {
                "persists_seeds": sum(1 for p in per if p["persists"]),
                "cycles": _agg([p["cycles"] for p in per]),
                "resource_throughput": _agg([p["resource_throughput"] for p in per]),
                "cumulative_energy_use": _agg([p["cumulative_energy_use"] for p in per]),
                "a1_activity": _agg([p["a1_activity"] for p in per]),
                "digests": [p["result_digest"] for p in per],
            }
            if cname == "none":
                ref = agg
            same = ref is not None and agg["digests"] == ref["digests"]
            differs = ref is not None and (
                agg["persists_seeds"] != ref["persists_seeds"] or agg["cycles"]["mean"] != ref["cycles"]["mean"]
            )
            rows.append(
                {
                    "scenario": sname,
                    "m2": cname,
                    **agg,
                    "difference_vs_none": "identical run"
                    if same
                    else "different outcome"
                    if differs
                    else "no difference in outcome (the run differs in detail)",
                }
            )
    return {"conditions": [c[0] for c in conds], "seeds": list(seeds), "rows": rows}


# ---------------------------------------------------------------------------------------------------- Philosophical operations, first stage
def _shift(kind: str) -> tuple[list[dict], int]:
    def setv(t: int, v: float) -> dict:
        return {"tick": t, "op": "RECONFIGURE", "path": "environment.renew_efficiency", "value": round(v, 4)}

    if kind == "stable":
        return [], 240
    if kind.startswith("step"):
        return [setv(100, float(kind[4:]))], 300
    if kind.startswith("drift"):
        b = float(kind[5:])
        return [setv(80 + i * 5, 1 + (b - 1) * (i + 1) / 12) for i in range(12)], 360
    if kind.startswith("shift-restore-shift"):
        b = float(kind.split(":")[1])
        down = [setv(80 + i * 5, 1 + (b - 1) * (i + 1) / 12) for i in range(12)]
        up = [setv(200 + i * 5, b + (1 - b) * (i + 1) / 12) for i in range(12)]
        down2 = [setv(320 + i * 5, 1 + (b - 1) * (i + 1) / 12) for i in range(12)]
        return down + up + down2, 480
    raise ValueError(kind)


def phil_paths(rec: dict) -> list[dict]:
    """The complete closed paths in a record: environmental event -> body detection -> expression -> response -> score -> subsequent operational change."""
    ev = {e["id"]: e for e in rec["events"]}
    out = []
    ivs = [e for e in rec["events"] if e["kind"] == "intervention" and (e.get("path") or "").startswith("environment.")]
    for expr in (e for e in rec["events"] if e["kind"] == "expression"):
        resp = next((e for e in rec["events"] if e["kind"] == "response" and e.get("expression") == expr["id"]), None)
        score = next((e for e in rec["events"] if e["kind"] == "score" and resp and e.get("response") == resp["id"]), None)
        change = next(
            (
                e
                for e in rec["events"]
                if e["kind"] in ("revision", "correction", "withhold")
                and score
                and e.get("score", e.get("inference")) in (score["id"],)
            ),
            None,
        ) or next(
            (
                e
                for e in rec["events"]
                if e["kind"] == "revision" and resp and ev.get(e.get("inference", -1), {}).get("response") == resp["id"]
            ),
            None,
        )
        prior = [i for i in ivs if i["tick"] <= expr["tick"]]
        if resp and score and change:
            out.append(
                {
                    "environmental_event_tick": prior[-1]["tick"] if prior else None,
                    "detection_and_expression_tick": expr["tick"],
                    "response_tick": resp["tick"],
                    "answer": resp["answer"],
                    "score_tick": score["tick"],
                    "operational_change": change["kind"],
                    "change_tick": change["tick"],
                }
            )
    return out


def phil_experiment(cfg: dict, seeds: tuple[int, ...] = (1, 2, 3)) -> dict:
    """no philosophical operation / expression only / expression + scorekeeping / expression + scorekeeping + norm-sensitive revision, over environments in which the
    renewal efficiency is stable, steps, drifts, or shifts, is restored and shifts again; with finite and unlimited power and with a clean, noisy or slow channel."""
    envs = ["stable", "step0.85", "step0.7", "drift0.7", "drift0.5", "shift-restore-shift:0.6"]
    modes = ("none", "expression", "scorekeeping", "revision")
    channels = {"clean": {}, "noisy": {"noise": 0.6}, "slow": {"delay": 15}}
    rows = []
    for power_name, power in (("finite power", POWER_FINITE), ("unlimited power", POWER_UNLIMITED)):
        for env in envs:
            ivs, horizon = _shift(env)
            for chname, ch in channels.items():
                if chname != "clean" and env not in ("drift0.7", "shift-restore-shift:0.6"):
                    continue
                for mode in modes:
                    if chname != "clean" and mode in ("none",):
                        continue
                    per = []
                    for sd in seeds:
                        c = cfg_with(
                            cfg,
                            seed=sd,
                            horizon=horizon,
                            power=power,
                            phil={"mode": mode, "margin": 0.1, "window": 3, "verify_margin": 0.02, **ch},
                        )
                        rec = E.run_record(c, ivs)
                        cnt = {
                            k: sum(1 for e in rec["events"] if e["kind"] == k)
                            for k in ("expression", "response", "score", "inference", "revision", "correction", "withhold")
                        }
                        win = (
                            {
                                "before_shift": sum(1 for e in rec["events"] if e["kind"] == "expression" and e["tick"] < 80),
                                "during_first_shift": sum(
                                    1 for e in rec["events"] if e["kind"] == "expression" and 80 <= e["tick"] < 200
                                ),
                                "after_restore_quiet": sum(
                                    1 for e in rec["events"] if e["kind"] == "expression" and 260 <= e["tick"] < 320
                                ),
                                "during_second_shift": sum(
                                    1 for e in rec["events"] if e["kind"] == "expression" and e["tick"] >= 320
                                ),
                            }
                            if env.startswith("shift-restore")
                            else None
                        )
                        per.append(
                            {
                                "state": rec["final_status"]["label"],
                                "cycles": len(rec["cycles"]),
                                "counts": cnt,
                                "power_spent_on_the_operation": round(sum(rec["traces"].get("phil_power_spent", [0.0])[-1:]), 4),
                                "closed_paths": len(phil_paths(rec)),
                                "windows": win,
                                "final_boost": rec["traces"].get("phil_boost", [1.0])[-1],
                            }
                        )
                    rows.append(
                        {
                            "power": power_name,
                            "environment": env,
                            "channel": chname,
                            "mode": mode,
                            "persists_seeds": sum(1 for p in per if p["state"] == "ACTIVE"),
                            "seeds": len(seeds),
                            "per_seed": per,
                        }
                    )
    return {
        "modes": list(modes),
        "environments": envs,
        "channels": list(channels),
        "seeds": list(seeds),
        "rows": rows,
        "note": "the operation is not designed to help: it costs power, a noisy or slow channel makes it wrong or late",
    }
