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
    changes = [
        ("entities.A2.x", [4, 7, 9]),
        ("entities.A2.y", [3, 9]),
        ("entities.A2.sensor_radius", [0, 1, 3]),
        ("entities.A1.sensor_radius", [0, 1, 3]),
        ("entities.A2.window", [2, 20]),
        ("entities.A1.window", [2, 20]),
        ("entities.A2.persist", [1, 6]),
        ("entities.A2.speed", [0.5, 2.0]),
    ]
    rows = []
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


def observe(rec: dict, obs: dict | None = None) -> dict:
    """What an observation array with a configured sampling interval, spatial resolution and region would conclude about the same run.

    The observer sees only the events at sampled ticks (tick % interval == 0) inside its region; a cycle is observed only if all four of its events
    are observed. The observed status is computed with the same criteria as the true status, from the observed cycles only. It can differ from the
    true status: observation is a parameter of what is found, not a neutral window."""
    obs = {"sampling_interval": 1, "spatial_resolution": 1, "region": None, **(obs or {})}
    k = max(1, int(obs["sampling_interval"]))
    ev = {e["id"]: e for e in rec["events"]}
    region = obs["region"]

    def seen(e: dict | None) -> bool:
        if e is None or e["tick"] % k != 0:
            return False
        if region and e.get("cell"):
            x, y = e["cell"]
            return region[0] <= x <= region[2] and region[1] <= y <= region[3]
        return True

    cycles = []
    for e in rec["events"]:
        if e["kind"] != "cycle":
            continue
        parts = [ev.get(e["a1_act"]), ev.get(e["a2_fire"]), ev.get(e["reconfigure"]), ev.get(e["a1_fire"])]
        if all(seen(p) for p in parts):
            cycles.append(e["tick"])
    win, k_active, stale = 48, 2, 24
    trajectory = []
    for t in range(len(rec["frames"])):
        c = [x for x in cycles if x <= t and t - x < win]
        last = max((x for x in cycles if x <= t), default=None)
        if len(c) >= k_active and last is not None and t - last <= stale:
            lab = "ACTIVE"
        elif c or t < win:
            lab = "DEGRADED"
        else:
            lab = "COLLAPSED"
        trajectory.append(lab)
    true_final = rec["final_status"]["label"]
    return {
        "observation": obs,
        "observed_cycles": len(cycles),
        "true_cycles": len(rec["cycles"]),
        "observed_status": trajectory[-1],
        "true_status": true_final,
        "agrees": trajectory[-1] == true_final,
        "observed_trajectory": trajectory,
    }
