"""Experiments over MEOS-0: ablation, minimal operational configuration (the MFS relation), XenoBody operational boundaries, history re-entry,
SSS and Address Domain perturbation, and observation-dependent status. Every function runs the real engine; nothing here is an estimate.

MFS is not redefined. MFS is the minimal relational operational configuration relative to a specified operation, physical conditions, scale and
admissible reductions. Here the operation is "MEOS-0's recursive cycle is sustained (status ACTIVE at the end of the run)", the physical conditions
and scale are the run's configuration, and the admissible reductions are the removals in ``engine.COMPONENTS``. MEOS is the ecosystem-level
application: several operational sequences (A1's, A2's) recursively modify one another's subsequent conditions. Minimality is therefore relational
and operational — the smallest set of retained components that still sustains the operation — and never a number of graphical objects.
"""

from __future__ import annotations

import copy
import itertools
from typing import Any

from . import engine as E

# The operational components a boundary can contain; environmental conditions (gradient, persistence) belong to the environment, not to a body.
BODY_COMPONENTS = ("A2", "sensor_resource", "sensor_alteration", "interaction_channel", "feedback", "resource_renewal", "history")
# The components each leg of the recursion needs: a leg lies inside a body only if all its components do.
LEGS: dict[str, tuple[str, ...]] = {
    "A1 senses the resource and fires": ("A1", "sensor_resource"),
    "A1 acts and alters the environment": ("A1",),
    "the alteration reaches the other configuration": ("interaction_channel",),
    "A2 detects the alteration and fires": ("A2", "sensor_alteration"),
    "A2 reconfigures the environment": ("A2", "feedback", "resource_renewal"),
    "history re-enters the next firing": ("history",),
}
# Named partitions of the same physical arrangement into operational bodies (XenoBody boundary specifications).
PARTITIONS: dict[str, dict[str, Any]] = {
    "B1": {"label": "A1 as one operational body", "components": ["A1", "sensor_resource"]},
    "B2": {
        "label": "A1 + the environmental sensor network",
        "components": ["A1", "sensor_resource", "sensor_alteration", "interaction_channel"],
    },
    "B3": {
        "label": "A1 + A2 + the resource-transfer loop",
        "components": [
            "A1",
            "A2",
            "sensor_resource",
            "sensor_alteration",
            "interaction_channel",
            "feedback",
            "resource_renewal",
            "history",
        ],
    },
}


def summarize(rec: dict) -> dict:
    """What one run says, without the frames: the end state, the cycles, when it collapsed and why, and the digests that identify it."""
    st = rec["final_status"]
    log = rec["status_log"]
    collapse = next((s["tick"] for s in log if s["label"] == "COLLAPSED"), None)
    return {
        "status": st["label"],
        "reason": st["reason"],
        "persists": st["label"] == "ACTIVE",
        "cycles": len(rec["cycles"]),
        "history_reentry_cycles": sum(1 for c in rec["cycles"] if c["history_reentry"]),
        "first_collapse_tick": collapse,
        "failed_dependency": st["dependency"],
        "status_log": [(s["tick"], s["label"]) for s in log],
        "result_digest": rec["result_digest"],
        "final_power": rec["frames"][-1]["power"],
    }


def experiment(config: dict, interventions: list[dict] | None = None, label: str = "") -> dict:
    rec = E.run_record(config, interventions or [])
    return {"label": label, "interventions": interventions or [], **summarize(rec)}


def removal(components: tuple[str, ...] | list[str], tick: int = 0) -> list[dict]:
    return [{"tick": tick, "op": "REMOVE", "target": c} for c in components]


def ablation_table(config: dict, subsets: list[list[str]] | None = None, seeds: tuple[int, ...] | None = None) -> dict:
    """Every single-component removal (or the given subsets) against the unperturbed run, over one or several seeds."""
    seeds = seeds or (config["seed"],)
    subsets = subsets if subsets is not None else [[c] for c in E.COMPONENTS]
    rows = []
    for sub in [[], *subsets]:
        per = []
        for sd in seeds:
            cfg = copy.deepcopy(config)
            cfg["seed"] = sd
            per.append(experiment(cfg, removal(sub), "+".join(sub) or "baseline"))
        rows.append(
            {
                "removed": sub,
                "outcomes": [
                    {
                        "seed": sd,
                        **{
                            k: p[k]
                            for k in ("status", "persists", "cycles", "first_collapse_tick", "failed_dependency", "result_digest")
                        },
                    }
                    for sd, p in zip(seeds, per, strict=True)
                ],
                "persists_in_all_seeds": all(p["persists"] for p in per),
            }
        )
    return {"seeds": list(seeds), "rows": rows}


def minimal_configuration(config: dict, exhaustive: bool = False, horizon: int | None = None) -> dict:
    """The smallest set of retained components that still sustains the operation, relative to the removals in ``E.COMPONENTS``.

    Default: backward elimination in a fixed order, then a leave-one-out check of the result (the retained set is 1-minimal: no single further removal
    keeps the operation). ``exhaustive`` evaluates every subset and reports every minimal retained set. Both are measurements of this model."""
    cfg = copy.deepcopy(config)
    if horizon:
        cfg["horizon"] = horizon
    comps = list(E.COMPONENTS)

    def persists(removed: list[str]) -> bool:
        return summarize(E.run_record(cfg, removal(removed)))["persists"]

    base = persists([])
    out: dict[str, Any] = {
        "operation": "MEOS-0 recursive cycle sustained: status ACTIVE at the end of the run",
        "relative_to": {"horizon": cfg["horizon"], "seed": cfg["seed"], "scale": cfg["sss"], "admissible_reductions": comps},
        "baseline_persists": base,
    }
    if not base:
        return {
            **out,
            "retained": comps,
            "removed": [],
            "note": "the unperturbed configuration does not sustain the operation: no reduction is meaningful",
        }
    singles = {c: persists([c]) for c in comps}
    removed: list[str] = []
    for c in (
        comps
    ):  # backward elimination: remove a component if the operation survives its removal on top of what is already removed
        if persists([*removed, c]):
            removed.append(c)
    retained = [c for c in comps if c not in removed]
    loo = {c: persists([*removed, c]) for c in retained}  # leave-one-out: removing any retained component ends the operation
    out.update(
        {
            "single_removal_persists": singles,
            "removed": removed,
            "retained": retained,
            "retained_is_one_minimal": not any(loo.values()),
            "leave_one_out_persists": loo,
            "retained_sustains_operation": persists(removed),
        }
    )
    if exhaustive:
        survivors = []
        for r in range(len(comps) + 1):
            for sub in itertools.combinations(comps, r):  # sub = the removed set
                if persists(list(sub)):
                    survivors.append(sorted(set(comps) - set(sub)))
        minimal = [s for s in survivors if not any(set(t) < set(s) for t in survivors)]
        out["exhaustive"] = {
            "subsets_evaluated": 2 ** len(comps),
            "sets_that_sustain": len(survivors),
            "minimal_retained_sets": minimal,
        }
    return out


def legs_inside(body: list[str]) -> dict[str, bool]:
    return {name: all(c in body for c in needs) for name, needs in LEGS.items()}


def boundary_analysis(config: dict, partitions: dict[str, dict] | None = None) -> dict:
    """The same arrangement partitioned into different operational bodies. For each partition: which legs of the recursion lie wholly inside the body
    (closure), and whether the operation persists when only the body's operational components are retained (the others are removed)."""
    parts = partitions or PARTITIONS
    base = E.run_record(config, [])
    rows = []
    for key, p in parts.items():
        body = list(p["components"])
        inside = legs_inside(body)
        outside = [c for c in BODY_COMPONENTS if c not in body]
        retained_run = summarize(E.run_record(config, removal(outside)))
        rows.append(
            {
                "id": key,
                "label": p.get("label", key),
                "components": body,
                "legs_inside": inside,
                "closure": round(sum(inside.values()) / len(inside), 4),
                "persists_when_only_the_body_is_retained": retained_run["persists"],
                "status_when_only_the_body_is_retained": retained_run["status"],
                "failed_dependency": retained_run["failed_dependency"],
                "cycles": retained_run["cycles"],
            }
        )
    return {
        "note": "the same physical arrangement; only the specification of what belongs to the operational body differs",
        "unperturbed": summarize(base),
        "partitions": rows,
    }


def history_comparison(config: dict) -> dict:
    """H+ (history re-enters) against H- (history removed) and H- (recorded but prevented from affecting later operation)."""
    runs = {
        "H+": E.run_record(config, []),
        "H- removed": E.run_record(config, [{"tick": 0, "op": "DISABLE_HISTORY", "mode": "removed"}]),
        "H- prevented": E.run_record(config, [{"tick": 0, "op": "DISABLE_HISTORY", "mode": "prevented"}]),
    }
    plus = runs["H+"]
    out = {}
    for k, rec in runs.items():
        fires_a = [(e["tick"], e["actor"]) for e in plus["events"] if e["kind"] == "fire"]
        fires_b = [(e["tick"], e["actor"]) for e in rec["events"] if e["kind"] == "fire"]
        diverge = next((i for i, (a, b) in enumerate(zip(fires_a, fires_b, strict=False)) if a != b), None)
        div_tick = None if diverge is None else min(fires_a[diverge][0], fires_b[diverge][0])
        if diverge is None and len(fires_a) != len(fires_b):
            div_tick = (fires_a if len(fires_a) > len(fires_b) else fires_b)[min(len(fires_a), len(fires_b))][0]
        reentry = [e["history_reentry"] for e in rec["events"] if e["kind"] == "fire"]
        out[k] = {
            **summarize(rec),
            "first_divergence_from_H+": div_tick,
            "mean_threshold_reduction": round(sum(reentry) / max(1, len(reentry)), 5),
        }
    return out


def sss_sweep(config: dict, values: dict[str, list[float]] | None = None) -> dict:
    """One-at-a-time SSS perturbation from tick 0. Scale changes sensing reach and diffusion length, size changes footprint and rates, speed changes
    movement and the process clock: the conditions of operation change, not the camera."""
    values = values or {"scale": [0.5, 1.0, 1.5, 2.0], "size": [0.5, 1.0, 2.0, 3.0], "speed": [0.5, 1.0, 2.0, 3.0]}
    rows = []
    for axis, vals in values.items():
        for v in vals:
            s = experiment(config, [{"tick": 0, "op": "ALTER_SSS", axis: v}], f"{axis}={v}")
            rows.append(
                {
                    "axis": axis,
                    "value": v,
                    **{
                        k: s[k]
                        for k in ("status", "persists", "cycles", "first_collapse_tick", "failed_dependency", "result_digest")
                    },
                }
            )
    return {"rows": rows}


def address_sweep(config: dict) -> dict:
    """One-at-a-time Address Domain perturbation of A1 and A2 (position, sensing boundary, temporal window, speed) from tick 0."""
    changes: list[tuple[str, list[float]]] = [
        ("entities.A2.x", [4, 7, 9]),
        ("entities.A2.y", [3, 9]),
        ("entities.A2.sensor_radius", [0, 1, 3]),
        ("entities.A1.sensor_radius", [0, 1, 3]),
        ("entities.A2.window", [2, 20]),
        ("entities.A1.window", [2, 20]),
        ("entities.A2.persist", [1, 6]),
        ("entities.A2.speed", [0.5, 2.0]),
    ]
    rows: list[dict[str, Any]] = []
    for path, vals in changes:
        for v in vals:
            s = experiment(config, [{"tick": 0, "op": "RECONFIGURE", "path": path, "value": v}], f"{path}={v}")
            rows.append(
                {
                    "path": path,
                    "value": v,
                    **{
                        k: s[k]
                        for k in ("status", "persists", "cycles", "first_collapse_tick", "failed_dependency", "result_digest")
                    },
                }
            )
    return {"rows": rows}


OBSERVABILITY = {
    "sampling_interval": "INSUFFICIENT_TEMPORAL_RESOLUTION",
    "spatial_stride": "INSUFFICIENT_SPATIAL_RESOLUTION",
    "region": "REGION_EXCLUDES_ACTIVITY",
    "aggregation": "AGGREGATION_SCALE_MISMATCH",
    "window": "OBSERVATION_WINDOW_MISMATCH",
}
# The fourth stage's vocabulary (the primary one in the interface and the run logs). The first-stage names above stay in ``observability_status`` of every result, so that
# records and tests that read them are unchanged; ``observability`` carries the new name beside it.
OBSERVABILITY_V4 = {
    "sampling_interval": "INSUFFICIENT_TEMPORAL_RESOLUTION",
    "aggregation": "INSUFFICIENT_TEMPORAL_RESOLUTION",
    "spatial_stride": "INSUFFICIENT_SPATIAL_RESOLUTION",
    "region": "OUTSIDE_OBSERVATION_REGION",
    "occluder": "BOUNDARY_OCCLUDED",
    "address_resolution": "ADDRESS_UNRESOLVED",
    "window": "WINDOW_TOO_SHORT",
    "threshold": "SIGNAL_BELOW_THRESHOLD",
}
OBSERVABILITY_STATUSES = (
    "SUFFICIENT",
    "INSUFFICIENT_TEMPORAL_RESOLUTION",
    "INSUFFICIENT_SPATIAL_RESOLUTION",
    "OUTSIDE_OBSERVATION_REGION",
    "BOUNDARY_OCCLUDED",
    "ADDRESS_UNRESOLVED",
    "WINDOW_TOO_SHORT",
    "SIGNAL_BELOW_THRESHOLD",
    "COMBINED_LIMITS",
    "OBSERVATION_OVERESTIMATES",
)
FULL_OBSERVATION = {
    "sampling_interval": 1,
    "spatial_stride": 1,
    "spatial_offset": [0, 0],
    "region": None,
    "aggregation": 1,
    "window": 48,
}
# Opt-in observation limits of the fourth stage; absent (None) they do nothing, so an observation that does not name them is the first-stage observation.
OPTIONAL_LIMITS: dict[str, Any] = {"threshold": None, "occluder": None, "address_resolution": None}
_RELAX = (
    ("sampling_interval", 1),
    ("spatial_stride", 1),
    ("region", None),
    ("aggregation", 1),
    ("window", 48),
    ("threshold", None),
    ("occluder", None),
    ("address_resolution", None),
)


def _signal(e: dict) -> float:
    """The amplitude an observer with a detection threshold compares: a fire's differentiated stimulus, an action's larger flow, a reconfiguration's signal."""
    if "differentiated" in e:
        return float(e["differentiated"])
    return max((float(e[k]) for k in ("consumed", "deposited", "amount", "signal") if k in e), default=1.0)


def _observed_cycle_ticks(rec: dict, obs: dict) -> list[int]:
    """The cycles an observation resolves. It sees an event only at a sampled tick, on its sampling lattice (every ``spatial_stride``-th cell from ``spatial_offset``),
    inside its region and outside its occluder, above its detection threshold and while the Address Domain still lets it attribute the event to an actor; a cycle is
    observed if all four of its events are seen; with an aggregation scale a, cycles inside one block of a ticks are one observed cycle."""
    k, s, a = max(1, int(obs["sampling_interval"])), max(1, int(obs["spatial_stride"])), max(1, int(obs["aggregation"]))
    ox, oy = obs["spatial_offset"]
    region, occluder = obs["region"], obs.get("occluder")
    thr, res = obs.get("threshold"), obs.get("address_resolution")
    ev = {e["id"]: e for e in rec["events"]}
    integ: dict[str, list[float]] = {
        n: t for n in ("A1", "A2") if (t := (rec.get("traces") or {}).get(f"address_integrity_{n.lower()}")) is not None
    }

    def seen(e: dict | None) -> bool:
        if e is None or e["tick"] % k != 0:
            return False
        if thr is not None and _signal(e) < float(thr):
            return False
        if res is not None and e.get("actor") in integ and float(integ[e["actor"]][e["tick"]]) < float(res):
            return False
        cell = e.get("cell")
        if cell is None:
            return True
        x, y = cell
        if (x - ox) % s or (y - oy) % s:
            return False
        if occluder and occluder[0] <= x <= occluder[2] and occluder[1] <= y <= occluder[3]:
            return False
        return not region or (region[0] <= x <= region[2] and region[1] <= y <= region[3])

    ticks = [
        e["tick"]
        for e in rec["events"]
        if e["kind"] == "cycle" and all(seen(ev.get(e[key])) for key in ("a1_act", "a2_fire", "reconfigure", "a1_fire"))
    ]
    return sorted({(t // a) * a + (a - 1) for t in ticks}) if a > 1 else ticks


def _label_trajectory(cycles: list[int], n: int, win: int) -> list[str]:
    k_active, stale = 2, min(24, win)
    out = []
    for t in range(n):
        c = [x for x in cycles if x <= t and t - x < win]
        last = max((x for x in cycles if x <= t), default=None)
        if len(c) >= k_active and last is not None and t - last <= stale:
            out.append("ACTIVE")
        elif c or t < win:
            out.append("DEGRADED")
        else:
            out.append("COLLAPSED")
    return out


def _v4_status(obs: dict, causes: list[str], agrees: bool, observed: str, true_final: str) -> str:
    if agrees:
        return "SUFFICIENT"
    if observed == "ACTIVE" and true_final != "ACTIVE":
        return "OBSERVATION_OVERESTIMATES"
    if len(causes) == 1:
        c = causes[0]
        return "WINDOW_MISMATCH" if c == "window" and int(obs["window"]) >= 48 else OBSERVABILITY_V4[c]
    return "COMBINED_LIMITS"


def observe(rec: dict, obs: dict | None = None) -> dict:
    """What an observation array with the configured temporal sampling interval, spatial resolution (sampling lattice), region, aggregation scale and observation window
    would conclude about the same run, kept apart from what the run did.

    ``operational_state`` is the status of the run itself; ``observed_state`` is the status computed with the same criteria from the observed cycles only;
    ``observability_status`` says why they differ — found by relaxing each observation parameter in turn to full resolution and seeing which restores agreement. An
    observation that cannot resolve the operation does not show that the operation is gone: it shows a limit of the observation.

    The fourth stage adds three opt-in limits (``threshold``, ``occluder``, ``address_resolution``), the ``observability`` block with the new status vocabulary and the per-tick
    ``timeline`` (operational, observed and observability state at every tick)."""
    obs = {**FULL_OBSERVATION, **OPTIONAL_LIMITS, **(obs or {})}
    n = len(rec["frames"])
    true_final = rec["final_status"]["label"]

    def state(o: dict) -> tuple[str, list[str], list[int]]:
        cyc = _observed_cycle_ticks(rec, o)
        traj = _label_trajectory(cyc, n, int(o["window"]))
        return traj[-1], traj, cyc

    observed, traj, cycles = state(obs)
    agrees = observed == true_final
    causes: list[str] = []
    relaxed_traj: dict[str, list[str]] = {}
    for key, full in _RELAX:
        if obs[key] != full:
            r = state({**obs, key: full})
            relaxed_traj[key] = r[1]
            if not agrees and r[0] == true_final:
                causes.append(key)
    if agrees:
        status = "OBSERVABLE"
    else:
        legacy = {**OBSERVABILITY, **{k: v for k, v in OBSERVABILITY_V4.items() if k not in OBSERVABILITY}}
        if observed == "ACTIVE" and true_final != "ACTIVE":
            status = "OBSERVATION_OVERESTIMATES"
        elif len(causes) == 1:
            status = legacy[causes[0]]
        elif causes:
            status = "MULTIPLE_LIMITS: " + ", ".join(legacy[c] for c in causes)
        else:
            status = "COMBINED_LIMITS: no single parameter restores agreement"
    v4 = _v4_status(obs, causes, agrees, observed, true_final)
    frames = rec["frames"]
    timeline = []
    for t in range(n):
        op = frames[t]["status"]
        ob = traj[t]
        if ob == op:
            tl_status, tl_causes = "SUFFICIENT", []
        else:
            tl_causes = [k for k, tr in relaxed_traj.items() if tr[t] == op]
            if ob == "ACTIVE" and op != "ACTIVE":
                tl_status = "OBSERVATION_OVERESTIMATES"
            elif len(tl_causes) == 1:
                tl_status = (
                    "WINDOW_MISMATCH" if tl_causes[0] == "window" and int(obs["window"]) >= 48 else OBSERVABILITY_V4[tl_causes[0]]
                )
            else:
                tl_status = "COMBINED_LIMITS"
        timeline.append({"t": t, "operational": op, "observed": ob, "observability": tl_status, "limiting": tl_causes})
    return {
        "observation": obs,
        "operational_state": true_final,
        "observed_state": observed,
        "observability_status": status,
        "observability": {
            "status": v4,
            "limiting_parameters": causes,
            "legacy_status": status,
            # an observed COLLAPSED against an operational non-collapse is a limit of the observation, not a collapse of the run
            "observed_collapse_is_operational": observed == "COLLAPSED" and true_final == "COLLAPSED",
            "observed_collapse_is_artifact": observed == "COLLAPSED" and true_final != "COLLAPSED",
        },
        "limiting_parameters": causes,
        "observed_cycles": len(cycles),
        "true_cycles": len(rec["cycles"]),
        "observed_trajectory": traj,
        "timeline": timeline,
        # kept for the interface and earlier records
        "observed_status": observed,
        "true_status": true_final,
        "agrees": agrees,
    }
