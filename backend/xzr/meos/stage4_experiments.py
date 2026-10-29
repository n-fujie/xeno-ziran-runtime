"""MEOS-0, fourth stage: Experiments A–E. Every function runs the real engine (seeded, deterministic); nothing is estimated and no outcome is adjusted toward an expectation.

Each experiment returns the same frame: ``seeds``, ``fixed_conditions``, ``manipulated_variable``, ``measured_variables``, ``rows`` (the results), ``null_results`` (comparisons
in which the manipulation made no measured difference), ``failures`` (runs the engine refused) and ``interpretation_limit``. A difference is reported only if a measured quantity
differs from the control; otherwise the row says so. The outcomes are properties of this formal model's operational relations and say nothing about any physical or biological
ecosystem.

  A  observation resolution sweep — the same runs watched with sampling interval, spatial stride, region, occluder, detection threshold and window varied
  B  XenoBody boundary perturbation — five boundary kinds, four durations
  C  Address Domain loss / reassignment / fragmentation / collision / partial / delayed / stale
  D  SSS boundary sweep — regions of the (scale, size, speed) space and the transition points along each axis
  E  M2 sensing ablation — none / direct / delayed / noisy / thresholded
"""

from __future__ import annotations

import statistics
from typing import Any

from . import analysis as A
from . import engine as E
from . import experiments as X
from . import stage4 as S

SEEDS = (1, 2, 3, 4, 5)
HONESTY = (
    "A formal model: the numbers describe how this engine's specified operations (a recursive cycle of two configurations, status ACTIVE / DEGRADED / COLLAPSED) respond to the "
    "manipulation. They are not evidence about any physical, biological or ecological system, and a visual representation of a run is never evidence of the run."
)


def _frame(name: str, seeds: tuple[int, ...], fixed: dict, manipulated: dict, measured: list[str], limit: str) -> dict:
    return {
        "experiment": name,
        "seeds": list(seeds),
        "fixed_conditions": fixed,
        "manipulated_variable": manipulated,
        "measured_variables": measured,
        "rows": [],
        "null_results": [],
        "failures": [],
        "interpretation_limit": f"{limit} {HONESTY}",
    }


def _try(out: dict, label: str, fn: Any, *a: Any, **kw: Any) -> Any:
    try:
        return fn(*a, **kw)
    except E.MeosError as exc:  # a refused run is recorded, not hidden
        out["failures"].append({"run": label, "error": str(exc)})
        return None


def _mean(v: list[float]) -> float | None:
    v = [x for x in v if x is not None]
    return round(statistics.fmean(v), 4) if v else None


# ====================================================================================================== A
def experiment_a(cfg: dict, seeds: tuple[int, ...] = SEEDS) -> dict:
    """The same runs, watched differently. Three scenarios (the unperturbed operation, an interaction cut that collapses it, the same cut followed by a resource pulse that
    restores it); the operational state is computed once per run and is identical under every observation, so what varies is only ``observed_state`` and the
    observability status. For each observation limit the transition value is the first one at which the observer's conclusion first differs from the run's."""
    scenarios = {
        "unperturbed (ACTIVE)": [],
        "interaction cut 100-150 (collapses)": X.INTERRUPTION,
        "cut 100-150 + pulse 2.0 at 151 (recovers)": [*X.INTERRUPTION, X.pulse(151, 2.0)],
    }
    sweeps: dict[str, list[dict]] = {
        "sampling_interval": [{"sampling_interval": v} for v in (1, 2, 3, 4, 5, 6, 8, 12)],
        "spatial_stride": [{"spatial_stride": v} for v in (1, 2, 3, 4, 6)],
        "region": [
            {"region": r}
            for r in (
                [0, 0, 13, 13],
                [0, 0, 9, 9],
                [0, 0, 6, 9],
                [2, 4, 6, 8],
                [3, 5, 5, 7],
                [4, 6, 5, 7],
                [8, 8, 12, 12],
                [0, 0, 2, 13],
            )
        ],
        "occluder": [{"occluder": r} for r in ([8, 8, 12, 12], [0, 0, 2, 13], [5, 6, 5, 6], [3, 6, 3, 6], [3, 5, 5, 7])],
        "threshold": [{"threshold": v} for v in (0.0, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.9)],
        "window": [{"window": v} for v in (6, 12, 24, 36, 48, 72)],
        "address_resolution": [{"address_resolution": v} for v in (0.25, 0.5, 0.75, 1.0)],
    }
    out = _frame(
        "A: observation resolution sweep",
        seeds,
        {"configuration": "MEOS-0 default", "horizon": 360, "scenarios": list(scenarios)},
        {"observation parameter": list(sweeps), "values": {k: [list(v.values())[0] for v in vs] for k, vs in sweeps.items()}},
        [
            "operational_state (final)",
            "observed_state (final)",
            "observability status",
            "observed cycles / true cycles",
            "operational digest",
        ],
        "The observation is a function applied to a finished record: it can only lose information, and the 'transition value' is a property of this record's event timing.",
    )
    recs = {(sn, sd): E.run_record(X.cfg_with(cfg, seed=sd, horizon=360), ivs) for sn, ivs in scenarios.items() for sd in seeds}
    for sn in scenarios:
        digests = {recs[(sn, sd)]["result_digest"] for sd in seeds}
        for param, vs in sweeps.items():
            for v in vs:
                per = []
                for sd in seeds:
                    rec = recs[(sn, sd)]
                    o = _try(out, f"{sn}/{param}={v}/seed{sd}", A.observe, rec, v)
                    if o is None:
                        continue
                    per.append(
                        {
                            "seed": sd,
                            "operational": o["operational_state"],
                            "observed": o["observed_state"],
                            "observability": o["observability"]["status"],
                            "observed_cycles": o["observed_cycles"],
                            "true_cycles": o["true_cycles"],
                            "observed_collapse_is_artifact": o["observability"]["observed_collapse_is_artifact"],
                            "operational_first_collapsed_tick": next(
                                (f["t"] for f in rec["frames"] if f["status"] == "COLLAPSED"), None
                            ),
                            "observed_first_collapsed_tick": next(
                                (t for t, x in enumerate(o["observed_trajectory"]) if x == "COLLAPSED"), None
                            ),
                        }
                    )
                agree = sum(1 for p in per if p["operational"] == p["observed"])
                out["rows"].append(
                    {
                        "scenario": sn,
                        "parameter": param,
                        "value": list(v.values())[0],
                        "seeds_where_observed_equals_operational": agree,
                        "seeds": len(per),
                        "statuses": sorted({p["observability"] for p in per}),
                        "mean_observed_cycle_share": _mean(
                            [p["observed_cycles"] / p["true_cycles"] for p in per if p["true_cycles"]]
                        ),
                        "observed_collapse_artifacts": sum(1 for p in per if p["observed_collapse_is_artifact"]),
                        "mean_observation_latency_ticks": _mean(
                            [
                                p["observed_first_collapsed_tick"] - p["operational_first_collapsed_tick"]
                                for p in per
                                if p["observed_first_collapsed_tick"] is not None
                                and p["operational_first_collapsed_tick"] is not None
                            ]
                        ),
                        "per_seed": per,
                    }
                )
        out.setdefault("operational_digests", {})[sn] = sorted(digests)
    # transition value per (scenario, parameter): the first value, in the sweep order, at which any seed's observation disagrees with the run
    trans = []
    for sn in scenarios:
        for param in sweeps:
            rows = [r for r in out["rows"] if r["scenario"] == sn and r["parameter"] == param]
            first = next((r["value"] for r in rows if r["seeds_where_observed_equals_operational"] < r["seeds"]), None)
            trans.append({"scenario": sn, "parameter": param, "first_disagreeing_value": first})
            if first is None:
                out["null_results"].append(f"{sn}: no value of {param} in the sweep made the observer disagree with the run")
    out["transition_values"] = trans
    # the run itself does not depend on the observation: the same record is observed 50+ ways above, and replaying it gives the same digest
    out["replay_identical_after_all_observations"] = all(E.replay(rec)["identical"] for rec in recs.values())
    return out


# ====================================================================================================== B
def experiment_b(cfg: dict, seeds: tuple[int, ...] = SEEDS) -> dict:
    out = _frame(
        "B: XenoBody boundary perturbation",
        seeds,
        {
            "configuration": "MEOS-0 default",
            "perturbation tick": 100,
            "restoration": "after the stated duration",
            "pulse": "2.0 at the cell (3, 6), one tick after the restoration",
        },
        {"boundary": list(S.BOUNDARY_KINDS), "duration (ticks)": [10, 20, 40, 80]},
        [
            "state before / at end of perturbation / final",
            "collapse tick",
            "recovery without a pulse",
            "recovery with a pulse",
            "paths cut and paths changed",
            "observability status",
            "B1/B2/B3 legs broken",
        ],
        "A perturbation is a removal and restoration of one relation at a fixed tick; the duration sweep shows how long the relation may be absent, not how long a real boundary may be.",
    )
    for kind in S.BOUNDARY_KINDS:
        for dur in (10, 20, 40, 80):
            r = _try(out, f"{kind}/{dur}", S.boundary_perturbation, cfg, kind, 100, dur, seeds)
            if r is None:
                continue
            rows = r["rows"]
            row = {
                "boundary": kind,
                "label": r["label"],
                "duration": dur,
                "collapsed_seeds": sum(1 for x in rows if x["collapsed"]),
                "recovered_without_pulse_seeds": sum(1 for x in rows if x["recovers_without_pulse"]),
                "recovered_with_pulse_seeds": sum(1 for x in rows if x["recovers_with_pulse"]),
                "pulse_alone_final_states": sorted({x["state_final_unperturbed_and_pulse"] for x in rows}),
                "operation_changed_seeds": sum(1 for x in rows if x["operation_changed"]),
                "mean_collapse_tick": _mean([x["collapse_tick"] for x in rows]),
                "paths_cut_directly": r["paths_cut_directly"],
                "paths_changed": r["affected_paths"],
                "observability": sorted({x["observability"]["status"] for x in rows}),
                "observed_states": sorted({x["observability"]["observed_state"] for x in rows}),
                "affected_components": r["affected_components"],
                "bodies": {
                    k: {"legs_broken": v["legs_broken_by_perturbation"], "affected_inside": v["affected_inside"]}
                    for k, v in r["bodies"].items()
                },
                "seeds": len(rows),
            }
            out["rows"].append(row)
            if row["operation_changed_seeds"] == 0:
                out["null_results"].append(
                    f"{kind} for {dur} ticks: the operation was bit for bit the unperturbed one in every seed (only the observation changed)"
                )
            elif row["collapsed_seeds"] == 0:
                out["null_results"].append(
                    f"{kind} for {dur} ticks: the operation changed in detail but did not collapse in any seed"
                )
    # the relation each boundary kind belongs to, from the body partitions (B3-only persistence is the existing boundary analysis; recomputed here with five seeds)
    out["body_persistence"] = _body_persistence(cfg, seeds)
    return out


def _body_persistence(cfg: dict, seeds: tuple[int, ...]) -> dict:
    """B3-only persistence: the operation persists with only the operational components of B1, B2, B3 retained (the rest removed), per seed."""
    res = {}
    for key, part in A.PARTITIONS.items():
        body = list(part["components"])
        outside = [c for c in A.BODY_COMPONENTS if c not in body]
        per = [
            X.run_summary(X.cfg_with(cfg, seed=sd), [{"tick": 0, "op": "REMOVE", "target": c} for c in outside])["persists"]
            for sd in seeds
        ]
        res[key] = {"label": part["label"], "components_retained": body, "persists_seeds": sum(per), "seeds": len(per)}
    return res


# ====================================================================================================== C
def experiment_c(cfg: dict, seeds: tuple[int, ...] = SEEDS) -> dict:
    out = _frame(
        "C: Address Domain interventions",
        seeds,
        {
            "configuration": "MEOS-0 default",
            "intervention tick": 100,
            "restoration": "after the stated duration (for reassign: the configuration is not moved back)",
            "pulse": "2.0 one tick after the restoration",
        },
        {"mode": [m for m in E.ADDRESS_MODES if m != "restore"], "target": ["A1", "A2", "both"], "duration": [10, 40]},
        [
            "operational state at the end",
            "collapse tick",
            "recovery status without / with a pulse",
            "address integrity during the fault",
            "observed state under address_resolution 0.9",
        ],
        "An Address Domain fault here is a fault of the attribution of a configuration to a cell; it is not a model of any network or naming system.",
    )
    for mode in (m for m in E.ADDRESS_MODES if m != "restore"):
        for target in ("A1", "A2", "both"):
            for dur in (10, 40):
                per = []
                for sd in seeds:
                    r = _try(
                        out,
                        f"{mode}/{target}/{dur}/seed{sd}",
                        S.address_intervention,
                        cfg,
                        mode,
                        target,
                        100,
                        dur,
                        sd,
                        {},
                        {"address_resolution": 0.9},
                    )
                    if r is None:
                        continue
                    e0 = r["effects"][0]
                    rec = r["record"]
                    integ = min(
                        (
                            f["address"][n]["integrity"]
                            for f in rec["frames"]
                            if f.get("address")
                            for n in (["A1", "A2"] if target == "both" else [target])
                        ),
                        default=1.0,
                    )
                    per.append(
                        {
                            "seed": sd,
                            "final": r["operational_state"],
                            "unperturbed": r["unperturbed_state"],
                            "final_with_pulse": r["restored_and_pulse_state"],
                            "collapse_tick": e0["operational_effect"]["collapse_tick"],
                            "min_integrity": integ,
                            "observed": e0["observed_effect"]["observed_state_final"],
                            "observability": e0["observed_effect"]["observability"],
                            "dynamics_changed": r["dynamics_changed"],  # the frames differ (the result digest would differ for any intervention: it covers the intervention log)
                        }
                    )
                if not per:
                    continue
                row = {
                    "mode": mode,
                    "target": target,
                    "duration": dur,
                    "seeds": len(per),
                    "collapsed_seeds": sum(1 for p in per if p["collapse_tick"] is not None),
                    "final_active_seeds": sum(1 for p in per if p["final"] == "ACTIVE"),
                    "final_active_with_pulse_seeds": sum(1 for p in per if p["final_with_pulse"] == "ACTIVE"),
                    "mean_collapse_tick": _mean([p["collapse_tick"] for p in per]),
                    "min_integrity": min(p["min_integrity"] for p in per),
                    "dynamics_changed_seeds": sum(1 for p in per if p["dynamics_changed"]),
                    "per_seed": per,
                }
                out["rows"].append(row)
                if row["dynamics_changed_seeds"] == 0:
                    out["null_results"].append(
                        f"{mode} on {target} for {dur} ticks: the dynamics (every frame) were bit for bit the unperturbed run's in every seed"
                    )
                elif row["collapsed_seeds"] == 0:
                    out["null_results"].append(
                        f"{mode} on {target} for {dur} ticks: the dynamics changed in {row['dynamics_changed_seeds']} of {row['seeds']} seeds, no seed collapsed"
                    )
    return out


# ====================================================================================================== D
def experiment_d(cfg: dict, seeds: tuple[int, ...] = (1, 2)) -> dict:
    scales = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
    sizes = (0.5, 1.0, 1.5, 2.0)
    speeds = (0.5, 1.0, 1.5, 2.0)
    out = _frame(
        "D: SSS boundary sweep",
        seeds,
        {
            "configuration": "MEOS-0 default",
            "horizon": 480,
            "region definitions": "ACTIVE at ticks 239 and 479 in every seed; COLLAPSED at 239 in every seed; otherwise METASTABLE; RECOVERY-CAPABLE = COLLAPSED but ACTIVE after a pulse of 2.0 at 300; OBSERVATION-SENSITIVE = ACTIVE but an observation at interval 2 concludes otherwise",
        },
        {"scale": list(scales), "size": list(sizes), "speed": list(speeds)},
        ["region of every grid point", "counts per region", "transition points along each axis (others at 1.0)"],
        "Scale, size and speed are model parameters of sensing reach, footprint and process clock; the regions are regions of this parameter space, not of any physical scale.",
    )
    ph = X.sss_phase(cfg, scales, sizes, speeds, seeds)
    pts = []
    for p in ph["points"]:
        pts.append(
            {k: p[k] for k in ("scale", "size", "speed", "class", "recovery_capable", "observation_sensitive")}
            | {"region": S.sss_region(p)}
        )
    out["rows"] = pts
    counts: dict[str, int] = {}
    for p in pts:
        counts[p["region"]] = counts.get(p["region"], 0) + 1
    out["counts"] = counts
    # transition points: bisect each axis (the others at 1.0) between the ACTIVE default and the nearest non-ACTIVE grid value
    out["transition_points"] = []
    for axis, grid in (("scale", scales), ("size", sizes), ("speed", speeds)):

        def cls_at(v: float, axis: str = axis) -> str:
            kw = {"scale": 1.0, "size": 1.0, "speed": 1.0} | {axis: v}
            return S.sss_classify(cfg, kw["scale"], kw["size"], kw["speed"], seeds)["class"]

        for side, candidates in (("above", [v for v in grid if v > 1.0]), ("below", [v for v in reversed(grid) if v < 1.0])):
            hit = next((v for v in candidates if cls_at(v) != "ACTIVE"), None)
            if hit is None:
                out["null_results"].append(
                    f"{axis} {side} 1.0: every grid value up to {candidates[-1] if candidates else 1.0} stays ACTIVE"
                )
                out["transition_points"].append(
                    {"axis": axis, "side": side, "last_active": candidates[-1] if candidates else 1.0, "first_not_active": None}
                )
                continue
            lo, hi = (candidates[candidates.index(hit) - 1] if candidates.index(hit) > 0 else 1.0), hit
            for _ in range(6):
                mid = round((lo + hi) / 2, 4)
                if cls_at(mid) == "ACTIVE":
                    lo = mid
                else:
                    hi = mid
            out["transition_points"].append(
                {
                    "axis": axis,
                    "side": side,
                    "last_active": lo,
                    "first_not_active": hi,
                    "class_there": cls_at(hi),
                    "resolution": round(abs(hi - lo), 4),
                }
            )
    return out


# ====================================================================================================== E
M2_CONDITIONS: list[tuple[str, dict]] = [
    ("none", {"sense": "none"}),
    ("direct w=1", {"sense": "direct", "weight": 1.0}),
    ("direct w=4", {"sense": "direct", "weight": 4.0}),
    ("delayed(3) w=1", {"sense": "delayed", "weight": 1.0, "delay": 3}),
    ("delayed(3) w=4", {"sense": "delayed", "weight": 4.0, "delay": 3}),
    ("noisy(0.05) w=1", {"sense": "noisy", "weight": 1.0, "noise": 0.05}),
    ("noisy(0.05) w=4", {"sense": "noisy", "weight": 4.0, "noise": 0.05}),
    ("threshold 0.05 w=4", {"sense": "threshold", "weight": 4.0, "threshold": 0.05}),
    ("threshold 0.2 w=4", {"sense": "threshold", "weight": 4.0, "threshold": 0.2}),
]


def _lag(rec: dict) -> float | None:
    """Mean ticks from A1's alteration to A2's firing over the counted cycles (read from the cycle events, which name the four events of each cycle)."""
    ev = {e["id"]: e for e in rec["events"]}
    cyc = [e for e in rec["events"] if e["kind"] == "cycle"]
    lags = [ev[c["a2_fire"]]["tick"] - ev[c["a1_act"]]["tick"] for c in cyc if c["a2_fire"] in ev and c["a1_act"] in ev]
    return round(statistics.fmean(lags), 4) if lags else None


def experiment_e(cfg: dict, seeds: tuple[int, ...] = SEEDS) -> dict:
    scenarios: dict[str, tuple[list[dict], dict]] = {
        "unperturbed": ([], {"horizon": 240}),
        "cut 100-150 + pulse 2.0": ([*X.INTERRUPTION, X.pulse(151, 2.0)], {"horizon": 360}),
        "cut 100-150, no pulse": (X.INTERRUPTION, {"horizon": 360}),
        "scale 1.5": ([{"tick": 0, "op": "ALTER_SSS", "scale": 1.5}], {"horizon": 240}),
        "renewal efficiency 0.7 at 100": (
            [{"tick": 100, "op": "RECONFIGURE", "path": "environment.renew_efficiency", "value": 0.7}],
            {"horizon": 300},
        ),
        "A2 partially addressable (50 %) from 100": (
            [{"tick": 100, "op": "ADDRESS", "target": "A2", "mode": "partial", "fraction": 0.5}],
            {"horizon": 240},
        ),
    }
    out = _frame(
        "E: M2 sensing ablation",
        seeds,
        {
            "configuration": "MEOS-0 default",
            "downstream path": "M2 (A2's alteration of the environment) is added to A1's resource-sensor signal, so it enters A1's differentiated stimulus and its firing condition",
            "observation for the observability column": {"sampling_interval": 2},
        },
        {"m2 sensing": [c[0] for c in M2_CONDITIONS], "scenario": list(scenarios)},
        [
            "collapse frequency (any COLLAPSED tick)",
            "recovery rate (collapsed, then ACTIVE at the end)",
            "cumulative energy use",
            "A1 to A2 coordination (cycles, mean A1-act to A2-fire lag)",
            "history dependence (ACTIVE with history removed)",
            "observability effect (observed interval 2 disagrees with the run)",
        ],
        "M2 sensing is one added term in A1's sensor signal; 'no difference' means no difference in these measured quantities for these seeds and scenarios.",
    )
    for sname, (ivs, over) in scenarios.items():
        ref: dict | None = None
        for cname, m2 in M2_CONDITIONS:
            per = []
            for sd in seeds:
                c = X.cfg_with(cfg, seed=sd, m2=m2, **over)
                rec = _try(out, f"{sname}/{cname}/seed{sd}", E.run_record, c, ivs)
                nohist = _try(
                    out,
                    f"{sname}/{cname}/seed{sd}/history removed",
                    E.run_record,
                    c,
                    [{"tick": 0, "op": "DISABLE_HISTORY", "mode": "removed"}, *ivs],
                )
                if rec is None or nohist is None:
                    continue
                tm = X.trace_metrics(rec)
                collapsed = any(s["label"] == "COLLAPSED" for s in rec["status_log"])
                o = A.observe(rec, {"sampling_interval": 2})
                per.append(
                    {
                        "persists": rec["final_status"]["label"] == "ACTIVE",
                        "collapsed": collapsed,
                        "recovered": collapsed and rec["final_status"]["label"] == "ACTIVE",
                        "energy": tm["cumulative_energy_use"],
                        "cycles": tm["cycles"],
                        "lag": _lag(rec),
                        "active_without_history": nohist["final_status"]["label"] == "ACTIVE",
                        "observation_disagrees": o["observed_state"] != o["operational_state"],
                        "digest": rec["result_digest"],
                    }
                )
            if not per:
                continue
            agg = {
                "scenario": sname,
                "m2": cname,
                "seeds": len(per),
                "collapse_frequency": round(sum(p["collapsed"] for p in per) / len(per), 4),
                "recovery_rate": round(sum(p["recovered"] for p in per) / max(1, sum(p["collapsed"] for p in per)), 4)
                if any(p["collapsed"] for p in per)
                else None,
                "persist_frequency": round(sum(p["persists"] for p in per) / len(per), 4),
                "mean_energy": _mean([p["energy"] for p in per]),
                "mean_cycles": _mean([p["cycles"] for p in per]),
                "mean_a1_a2_lag": _mean([p["lag"] for p in per]),
                "active_without_history_frequency": round(sum(p["active_without_history"] for p in per) / len(per), 4),
                "observation_disagrees_frequency": round(sum(p["observation_disagrees"] for p in per) / len(per), 4),
                "digests": [p["digest"] for p in per],
            }
            if cname == "none":
                ref = agg
            elif ref is not None:
                keys = (
                    "collapse_frequency",
                    "recovery_rate",
                    "persist_frequency",
                    "mean_energy",
                    "mean_cycles",
                    "mean_a1_a2_lag",
                    "active_without_history_frequency",
                    "observation_disagrees_frequency",
                )
                diff = [k for k in keys if agg[k] != ref[k]]
                agg["identical_runs_to_none"] = agg["digests"] == ref["digests"]
                agg["measured_differences_vs_none"] = diff
                if not diff:
                    out["null_results"].append(
                        f"{sname} / {cname}: no difference from M2 sensing 'none' in any measured quantity"
                        + (
                            " (the runs are bit for bit identical)"
                            if agg["identical_runs_to_none"]
                            else " (the runs differ in detail)"
                        )
                    )
            out["rows"].append(agg)
    return out
