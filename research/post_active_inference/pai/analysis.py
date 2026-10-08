"""Analysis of a benchmark stage: per-cell regime scores, main results, thresholds, regime summaries, the too-slow
correction and history re-entry analyses, the failure taxonomy and the non-redundancy tests."""
from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import nonredundancy as NR
import regime_classifier as RC

from .perturbations import ALIASES, NOT_IMPLEMENTED, REGISTRY
from .stats import describe, holm, paired, sign_flip_p, threshold

CONTROL = "control"
CTRL_METRICS = ("success_pre", "success_pert", "success_rec", "abs_error_pert", "abs_error_rec", "one_step_acc_pre",
                "one_step_acc_pert", "one_step_acc_rec", "multi_step_acc_pert", "pred_mae_pert", "inferred_state_acc_pert",
                "log_loss_pert", "calibration_gap_pert", "support_coverage_pert", "adaptation_time", "recovery_time",
                "recovered", "model_validity_duration", "rebuilds_pert", "invalidations", "policy_switch_rate_pert",
                "policy_entropy_pert", "F_pert", "G_pert", "surprise_pert", "time_to_effect_pert", "reach_rate_pert",
                "level_sd_rec", "N_activity_pert", "failed_inference", "numerical", "missing_observations",
                "adaptation_lag_steps", "dt_pert")
TRACKER_METRICS = ("detect_onset.hit", "detect_onset.delay", "detect_revert.hit", "localisation_auc", "propagation_depth",
                   "affected_share", "world_change_score", "splits_pert", "merges_pert", "reignitions_pert",
                   "reignitions_T_pert", "reachable_change", "reconfiguration_magnitude", "recurrence_pert",
                   "persistence_pert", "false_alarms_pre")
MAIN_CONTROLLERS = ("none", "aif_fixed", "aif_adaptive", "ost")


# ------------------------------------------------------------------------------------------------ loading
def load(od: Path) -> tuple[dict, list[dict]]:
    controls: dict[int, dict] = {}
    cells: list[dict] = []
    for p in sorted((od / "jobs").glob("*/*.json")):
        c = json.loads(p.read_text())
        if c["key"] == CONTROL:
            runs = {k: v for k, v in c["runs"].items() if not k.endswith("@noise")}
            noise = {k[:-6]: v for k, v in c["runs"].items() if k.endswith("@noise")}
            controls[c["seed"]] = {"control": runs, "noise": noise}
        else:
            cells.append(c)
    return controls, cells


def _get(rec, key):
    if rec is None or rec.get("status") != "ok":
        return None
    src = rec["metrics"]
    if key in ("detect_onset.hit", "detect_onset.delay", "detect_revert.hit") or key in TRACKER_METRICS:
        src = rec.get("tracker", {})
    v = src
    for part in key.split("."):
        v = v.get(part) if isinstance(v, dict) else None
    if isinstance(v, bool):
        return float(v)
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return None
    return float(v)


def _family(key: str) -> str:
    return key.split(".")[0]


# ------------------------------------------------------------------------------------------------ main analysis
def analyse(cfg: dict, od: Path, publish_to: Path | None = None, manifest_fn=None) -> dict:
    controls, cells = load(od)
    if not controls:
        raise SystemExit(f"no control cells in {od}")
    # 1. per cell × seed scores (noise tolerance from all seeds; the null check leaves its own seed out)
    tol = RC.tolerance(controls)
    scored = []
    for c in cells:
        ref = controls.get(c["seed"])
        if ref is None:
            continue
        s = RC.scores(c["runs"], ref["control"], ref["noise"], tol)
        scored.append({"key": c["key"], "family": _family(c["key"]), "side": REGISTRY[c["key"]].side,
                       "severity": c["severity"], "seed": c["seed"], **s})
    nulls = [RC.null_scores(v["control"], v["noise"], RC.tolerance(controls, exclude=seed)) for seed, v in controls.items()]
    # cell-level regime (primary): scores averaged over seeds, then the minimum
    regime_of: dict[tuple, str | None] = {}
    cell_cls: dict[tuple, dict] = {}
    by_cell = defaultdict(list)
    for r in scored:
        by_cell[(r["key"], r["severity"])].append(r)
    for k, rs in by_cell.items():
        cell_cls[k] = RC.cell_label(rs)
        regime_of[k] = cell_cls[k]["label"]

    main_rows = _main_results(cells, controls)
    thr_rows, thr = _thresholds(by_cell, nulls)
    summary = {
        "stage": cfg["stage"], "seeds": cfg["seeds"], "severities": cfg["severities"],
        "perturbations_run": len({c["key"] for c in cells}), "aliases": ALIASES, "not_implemented": NOT_IMPLEMENTED,
        "noise_tolerance": tol,
        "cell_classification": {f"{k}@{sv:g}": v for (k, sv), v in sorted(cell_cls.items())},
        "decision_rule": {"compatible": f"C_AIF >= {RC.HI}", "transition": f"{RC.LO} <= C_AIF < {RC.HI}",
                          "post": f"C_AIF < {RC.LO}", "scores": RC.SCORES, "C_AIF": "min of available scores"},
        "null_classification": _null_summary(nulls),
        "regimes": _regime_summary(scored, regime_of),
        "first_unstable": _first_unstable(scored),
        "transition_region": _transition_region(by_cell, regime_of),
        "performance_by_regime": _performance(cells, regime_of, controls),
        "tracking_by_regime": _tracking(scored),
        "tracker_informative_while_comparator_invalid": _q7(scored),
        "structure_learning_overlap": _overlap(scored),
        "too_slow_correction": _too_slow(cells, controls),
        "history_reentry": _history(cells),
        "thresholds": thr,
    }
    # non-redundancy
    abl_cells = []
    for seed, v in controls.items():
        abl_cells.append({"key": CONTROL, "severity": 0.0, "seed": seed, "regime": "REFERENCE (unperturbed)",
                          "runs": v["control"]})
    for c in cells:
        if any(k.startswith("aif_adaptive-") for k in c["runs"]):
            abl_cells.append({"key": c["key"], "severity": c["severity"], "seed": c["seed"],
                              "regime": regime_of.get((c["key"], c["severity"])), "runs": c["runs"]})
    nr = NR.analyse(abl_cells)
    nr["summary"] = NR.summary_status(nr["table"])
    summary["nonredundancy"] = nr["summary"]
    failures = _failures(cells, controls, scored)
    summary["failures"] = {k: len(v) for k, v in failures["categories"].items()}
    od.mkdir(parents=True, exist_ok=True)
    for dest in [od] + ([publish_to] if publish_to else []):
        dest.mkdir(parents=True, exist_ok=True)
        _csv(dest / "main_results.csv", main_rows)
        _csv(dest / "thresholds.csv", thr_rows)
        _csv(dest / "cell_scores.csv", [{k: v for k, v in r.items() if not isinstance(v, dict)} for r in scored])
        _csv(dest / "nonredundancy.csv", nr["tests"])
        (dest / "summary.json").write_text(json.dumps(summary, indent=1, default=_j))
        (dest / "failures.json").write_text(json.dumps(failures, indent=1, default=_j))
        (dest / "nonredundancy.json").write_text(json.dumps(nr, indent=1, default=_j))
        if manifest_fn is not None:
            n_runs = sum(len(c["runs"]) for c in cells) + sum(len(v["control"]) + len(v["noise"]) for v in controls.values())
            (dest / "run_manifest.json").write_text(json.dumps(manifest_fn(cfg, {
                "analysed_cells": len(cells) + len(controls), "analysed_runs": n_runs,
                "results_dir": str(od.relative_to(od.parents[1]))}), indent=1, default=_j))
    print(json.dumps({"cells": len(cells), "regimes": summary["regimes"]["overall"], "failures": summary["failures"],
                      "null_mislabelled_share": summary["null_classification"]["mislabelled_share"]}, default=_j))
    return summary


def _j(x):
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x) if np.isfinite(x) else None
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, set):
        return sorted(x)
    return str(x)


def _csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v, default=_j) if isinstance(v, (list, dict, tuple)) else v) for k, v in r.items()})


# ------------------------------------------------------------------------------------------------ main results
def _main_results(cells, controls) -> list[dict]:
    rows = []
    groups = defaultdict(list)
    for c in cells:
        groups[(c["key"], c["severity"])].append(c)
    for seed, v in controls.items():
        groups[(CONTROL, 0.0)].append({"key": CONTROL, "severity": 0.0, "seed": seed, "runs": v["control"]})
    for (key, sev), cs in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        ctrls = sorted({k for c in cs for k in c["runs"]})
        for ctl in ctrls:
            metrics = CTRL_METRICS + (TRACKER_METRICS if ctl == "none" else ())
            for m in metrics:
                vals, diffs = [], []
                for c in cs:
                    v = _get(c["runs"].get(ctl), m)
                    if v is None:
                        continue
                    vals.append(v)
                    base = controls.get(c["seed"], {}).get("control", {}).get(ctl)
                    b = _get(base, m)
                    if b is not None and key != CONTROL:
                        diffs.append(v - b)
                if not vals:
                    continue
                d = describe(vals)
                row = {"perturbation": key, "family": _family(key) if key != CONTROL else CONTROL,
                       "side": REGISTRY[key].side if key in REGISTRY else None, "severity": sev, "controller": ctl,
                       "metric": m, "n": d["n"], "mean": d["mean"], "median": d["median"], "sd": d["sd"],
                       "ci95_lo": d["ci95"][0] if d["ci95"] else None, "ci95_hi": d["ci95"][1] if d["ci95"] else None}
                if len(diffs) >= 2:
                    pr = paired(diffs, 0.05)
                    row.update(vs_control_mean=pr["mean"], vs_control_ci95=pr["ci95"], vs_control_p=pr["p"],
                               vs_control_dz=pr["dz"])
                rows.append(row)
    # collateral change (activity of the neighbour module) relative to the uncontrolled run of the same cell
    for (key, sev), cs in groups.items():  # noqa: B007 - key/sev used in the rows below
        for ctl in MAIN_CONTROLLERS[1:]:
            d = [(_get(c["runs"].get(ctl), "N_activity_pert") or np.nan) - (_get(c["runs"].get("none"), "N_activity_pert") or np.nan)
                 for c in cs]
            d = [x for x in d if np.isfinite(x)]
            if len(d) >= 2:
                ds = describe(d)
                rows.append({"perturbation": key, "family": _family(key) if key != CONTROL else CONTROL,
                             "side": REGISTRY[key].side if key in REGISTRY else None, "severity": sev,
                             "controller": ctl, "metric": "collateral_N_activity_vs_none", "n": ds["n"],
                             "mean": ds["mean"], "median": ds["median"], "sd": ds["sd"],
                             "ci95_lo": ds["ci95"][0] if ds["ci95"] else None, "ci95_hi": ds["ci95"][1] if ds["ci95"] else None})
    return rows


# ------------------------------------------------------------------------------------------------ thresholds
def _thresholds(by_cell, nulls) -> tuple[list[dict], dict]:
    rows, out = [], {}
    null_c = [n["C_AIF"] for n in nulls if n["C_AIF"] is not None]
    keys = sorted({k for k, _ in by_cell})
    for key in keys:
        sevs = sorted(s for k, s in by_cell if k == key)
        seeds = sorted({r["seed"] for s in sevs for r in by_cell[(key, s)]})
        levels = [0.0] + sevs
        for metric in ("C_AIF",) + RC.SCORES:
            M = np.full((len(seeds), len(levels)), np.nan)
            for j, s in enumerate(sevs):
                for r in by_cell[(key, s)]:
                    v = r.get(metric)
                    if v is not None:
                        M[seeds.index(r["seed"]), j + 1] = v
            M[:, 0] = np.mean(null_c) if (metric == "C_AIF" and null_c) else 1.0
            if np.isnan(M[:, 1:]).all():
                continue
            for thr_ in (RC.HI, RC.LO):
                t = threshold(levels, M, thr_)
                row = {"perturbation": key, "family": _family(key), "side": REGISTRY[key].side, "score": metric,
                       "threshold": thr_, "crossing_severity": t["estimate"], "ci95": t.get("ci95"),
                       "seeds_crossing_share": t.get("seeds_crossing_share"), "per_seed_iqr": t.get("per_seed_iqr"),
                       "boot_never_share": t.get("boot_never_share"), "levels": levels, "mean_curve": t.get("curve")}
                rows.append(row)
                if metric == "C_AIF":
                    out.setdefault(key, {})[str(thr_)] = {k: row[k] for k in ("crossing_severity", "ci95",
                                                                             "seeds_crossing_share", "per_seed_iqr")}
        labs = {f"{s:g}": dict(Counter(r["label"] for r in by_cell[(key, s)])) for s in sevs}
        out.setdefault(key, {})["labels_by_severity"] = labs
    return rows, out


# ------------------------------------------------------------------------------------------------ summaries
def _null_summary(nulls) -> dict:
    labs = [n["label"] for n in nulls if n["label"]]
    c = Counter(labs)
    means = {k: float(np.mean([n[k] for n in nulls if n.get(k) is not None]))
             for k in ("S_sensor", "S_model", "S_variable") if any(n.get(k) is not None for n in nulls)}
    cell_c = min(means.values()) if means else None
    return {"n": len(labs), "labels": dict(c), "cell_level": {"scores": means, "C_AIF": cell_c, "label": RC.label(cell_c)},
            "mislabelled_share": (1 - c.get(RC.LABELS[0], 0) / len(labs)) if labs else None,
            "C_AIF": describe([n["C_AIF"] for n in nulls])}


def _regime_summary(scored, regime_of) -> dict:
    overall = Counter(r["label"] for r in scored)
    fam = defaultdict(Counter)
    side = defaultdict(Counter)
    sev = defaultdict(Counter)
    for r in scored:
        fam[r["family"]][r["label"]] += 1
        side[r["side"]][r["label"]] += 1
        sev[f"{r['severity']:g}"][r["label"]] += 1
    sens = {k: Counter(r["label_sensitivity"][k] for r in scored) for k in (f"{h}/{lo}" for h, lo in RC.SENSITIVITY)}
    cells = Counter(regime_of.values())
    return {"overall": dict(overall), "by_family": {k: dict(v) for k, v in fam.items()},
            "by_side": {k: dict(v) for k, v in side.items()}, "by_severity": {k: dict(v) for k, v in sev.items()},
            "cells_majority": dict(cells), "threshold_sensitivity": {k: dict(v) for k, v in sens.items()}}


def _first_unstable(scored) -> dict:
    """Which primitive is lowest when a cell first leaves the compatible regime (mode over seeds, per perturbation)."""
    out = {}
    for key in sorted({r["key"] for r in scored}):
        rs = sorted([r for r in scored if r["key"] == key], key=lambda r: r["severity"])
        firsts = Counter()
        lowest = None
        for s in sorted({r["severity"] for r in rs}):
            sub = [r for r in rs if r["severity"] == s and r["first_unstable"]]
            if sub and lowest is None and len(sub) >= max(1, len([r for r in rs if r["severity"] == s]) // 2):
                lowest = s
                firsts.update(r["first_unstable"] for r in sub)
        out[key] = {"lowest_severity_majority_unstable": lowest, "first_unstable_counts": dict(firsts),
                    "first_unstable": firsts.most_common(1)[0][0] if firsts else None}
    by_prim = defaultdict(list)
    for k, v in out.items():
        if v["first_unstable"]:
            by_prim[v["first_unstable"]].append(k)
    return {"per_perturbation": out, "by_primitive": dict(by_prim)}


def _transition_region(by_cell, regime_of) -> dict:
    """Per perturbation: the cell-level label sequence over severity. 'graded' = passes through TRANSITION;
    'abrupt' = compatible → post-AIF between two grid points; 'post_from_lowest_severity' = already post at the
    lowest tested severity (the grid is too coarse to locate the onset). Seed disagreement is listed separately."""
    out = {}
    for key in sorted({k for k, _ in by_cell}):
        sevs = sorted(s for k, s in by_cell if k == key)
        seq = [regime_of[(key, s)] for s in sevs]
        mixed = [s for s in sevs if len({r["label"] for r in by_cell[(key, s)]}) > 1]
        cs = [float(np.nanmean([r["C_AIF"] for r in by_cell[(key, s)] if r["C_AIF"] is not None] or [np.nan])) for s in sevs]
        if all(x == RC.LABELS[0] for x in seq):
            kind = "compatible_throughout"
        elif RC.LABELS[1] in seq:
            kind = "graded"          # the cell-level label passes through TRANSITION
        elif RC.LABELS[2] in seq and seq[0] == RC.LABELS[0]:
            kind = "abrupt"          # compatible → post with no transition cell on this severity grid
        else:
            kind = "post_from_lowest_severity"
        out[key] = {"severities": sevs, "majority": seq, "mean_C_AIF": cs, "mixed_severities": mixed, "kind": kind}
    return {"per_perturbation": out, "counts": dict(Counter(v["kind"] for v in out.values()))}


def _performance(cells, regime_of, controls) -> dict:
    """Success in the perturbation phase per controller, by the cell-level regime; paired contrasts with Holm."""
    by_reg = defaultdict(lambda: defaultdict(list))
    pairs = defaultdict(lambda: defaultdict(list))
    rows = [(c["key"], c["severity"], c["runs"], regime_of.get((c["key"], c["severity"]))) for c in cells]
    rows += [(CONTROL, 0.0, v["control"], "REFERENCE (unperturbed)") for v in controls.values()]
    contrasts = (("aif_adaptive", "ost"), ("aif_fixed", "ost"), ("aif_adaptive", "aif_fixed"), ("aif_adaptive", "none"),
                 ("aif_fixed", "none"), ("ost", "none"))
    for metric in ("success_pert", "success_rec", "one_step_acc_pert"):
        for _key, _sev, runs, reg in rows:
            if reg is None:
                continue
            for ctl in MAIN_CONTROLLERS:
                v = _get(runs.get(ctl), metric)
                if v is not None:
                    by_reg[(metric, reg)][ctl].append(v)
            for a, b in contrasts:
                va, vb = _get(runs.get(a), metric), _get(runs.get(b), metric)
                if va is not None and vb is not None:
                    pairs[(metric, reg)][f"{a} - {b}"].append(va - vb)
    tests = []
    for (metric, reg), d in pairs.items():
        for name, xs in d.items():
            tests.append({"metric": metric, "regime": reg, "contrast": name, **paired(xs, 0.05)})
    adj = holm([t["p"] for t in tests]) if tests else []
    for t, p in zip(tests, adj, strict=True):
        t["p_holm"] = p
    return {"means": {f"{m}|{r}": {c: describe(v) for c, v in d.items()} for (m, r), d in by_reg.items()},
            "contrasts": tests, "note": "cell-seed level; contrasts paired within cell and seed; Holm over all contrasts"}


def _tracking(scored) -> dict:
    out = {}
    for lab in RC.LABELS:
        rs = [r for r in scored if r["label"] == lab]
        def share(key, side=None, rs=rs):
            v = [r[key] for r in rs if r.get(key) is not None and (side is None or r["side"] == side)]
            return {"share_true": float(np.mean(v)) if v else None, "n": len(v)}
        out[lab] = {"tracking_preserved_world": share("tracking_preserved", "world"),
                    "tracking_preserved_observation": share("tracking_preserved", "observation"),
                    "comparator_detection_world": share("comparator_detection", "world"),
                    "sensor_only_tracker_world": share("tracking_sensor_only", "world"),
                    "localisation_auc_tracker": describe([r.get("localisation_auc") for r in rs]),
                    "localisation_auc_comparator_channels": describe([r.get("channel_localisation_auc") for r in rs])}
    return out


def _q7(scored) -> dict:
    inv = [r for r in scored if (r["S_model"] is not None and r["S_model"] < RC.LO) or
           (r["C_AIF"] is not None and r["C_AIF"] < RC.LO)]
    both = [r for r in inv if r.get("tracking_preserved") is True]
    per = Counter(r["key"] for r in both)
    return {"comparator_structurally_invalid_cell_seeds": len(inv),
            "of_which_tracking_preserved": len(both),
            "of_which_tracking_failed": sum(1 for r in inv if r.get("tracking_preserved") is False),
            "of_which_tracking_not_applicable": sum(1 for r in inv if r.get("tracking_preserved") is None),
            "where": dict(per.most_common()),
            "note": "tracking_preserved uses the full-stream tracker (information advantage); the sensor-only "
                    "tracker's detection is reported in tracking_by_regime"}


def _overlap(scored) -> dict:
    ov = [r for r in scored if r.get("overlap_structure_learning")]
    return {"cell_seeds": len(ov), "where": dict(Counter(f"{r['key']}@{r['severity']:g}" for r in ov).most_common()),
            "definition": "fixed-model validity < 0.5 while the adaptive (structure-learning-lite) model keeps ≥ 0.8"}


def _too_slow(cells, controls) -> dict:
    out = {}
    for key in ("temporal.interface_drift", "temporal.world_drift"):
        cs = [c for c in cells if c["key"] == key]
        if not cs:
            continue
        rows = []
        for sev in sorted({c["severity"] for c in cs}):
            sub = [c for c in cs if c["severity"] == sev]
            period = next((c["runs"]["none"]["perturbation_info"].get("period") for c in sub
                           if c["runs"].get("none", {}).get("status") == "ok"), None)
            row = {"severity": sev, "change_period_steps": period}
            for ctl in MAIN_CONTROLLERS:
                row[f"success_{ctl}"] = describe([_get(c["runs"].get(ctl), "success_pert") for c in sub])["mean"]
                row[f"adaptation_time_{ctl}"] = describe([_get(c["runs"].get(ctl), "adaptation_time") for c in sub])["mean"]
                row[f"model_validity_{ctl}"] = describe([_get(c["runs"].get(ctl), "model_validity_duration") for c in sub])["mean"]
                row[f"acc_{ctl}"] = describe([_get(c["runs"].get(ctl), "one_step_acc_pert") for c in sub])["mean"]
            for ctl in ("aif_fixed", "aif_adaptive", "ost"):
                d = [(_get(c["runs"].get(ctl), "success_pert") or np.nan) - (_get(c["runs"].get("none"), "success_pert") or np.nan) for c in sub]
                d = [x for x in d if np.isfinite(x)]
                pr = paired(d, 0.05) if len(d) >= 2 else None
                row[f"{ctl}_minus_none"] = pr["mean"] if pr else None
                row[f"{ctl}_minus_none_p"] = pr["p"] if pr else None
            rows.append(row)
        # adaptation lag of the adaptive comparator at the slowest change (lowest severity), in steps
        lag = describe([_get(c["runs"].get("aif_adaptive"), "adaptation_lag_steps") for c in cs
                        if c["severity"] == min(c2["severity"] for c2 in cs)])
        stale = None
        for r in sorted(rows, key=lambda r: -(r["change_period_steps"] or 0)):
            if r["aif_adaptive_minus_none"] is not None and (r["aif_adaptive_minus_none"] <= 0 or
                                                             (r["aif_adaptive_minus_none_p"] or 1) > 0.05):
                stale = r["change_period_steps"]
                break
        out[key] = {"by_severity": rows, "staleness_period_steps": stale, "adaptive_lag_steps_slowest": lag,
                    "rule": "staleness = longest change period at which the adaptive comparator's success is no "
                            "longer better than no control (mean ≤ 0 or paired p > 0.05)"}
    return out


def _history(cells) -> dict:
    by = defaultdict(dict)
    for c in cells:
        if c["key"] in ("memory.history_removal", "memory.history_reactivation", "memory.migration"):
            by[(c["seed"], c["severity"])][c["key"]] = c
    rows = []
    for sev in sorted({s for _, s in by}):
        pr = [v for (seed, s), v in by.items() if s == sev and "memory.history_removal" in v and "memory.history_reactivation" in v]
        row = {"severity": sev, "n": len(pr)}
        for ctl in ("aif_fixed", "aif_adaptive", "ost", "none"):
            d = [(_get(v["memory.history_reactivation"]["runs"].get(ctl), "success_rec") or np.nan)
                 - (_get(v["memory.history_removal"]["runs"].get(ctl), "success_rec") or np.nan) for v in pr]
            d = [x for x in d if np.isfinite(x)]
            row[f"success_rec_reactivate_minus_remove_{ctl}"] = paired(d, 0.05) if len(d) >= 2 else None
        rec = []
        for v in pr:
            a = v["memory.history_reactivation"]["runs"].get("none", {}).get("profiles", {}).get("T_pre_vs_rec")
            b = v["memory.history_removal"]["runs"].get("none", {}).get("profiles", {}).get("T_pre_vs_rec")
            if a is not None and b is not None:
                rec.append(a - b)
        row["pattern_recurrence_reactivate_minus_remove"] = paired(rec, 0.05) if len(rec) >= 2 else None
        mig = [v["memory.migration"]["runs"].get("none", {}).get("profiles", {}) for (seed, s), v in by.items()
               if s == sev and "memory.migration" in v]
        dm = [m["migration_dest_corr"] - m["migration_dest_corr_pre"] for m in mig
              if m.get("migration_dest_corr") is not None and m.get("migration_dest_corr_pre") is not None]
        row["migration_destination_recurrence_gain"] = paired(dm, 0.05) if len(dm) >= 2 else None
        rows.append(row)
    return {"by_severity": rows,
            "note": "reactivate vs remove are paired within seed and severity (identical until t_r). Pattern "
                    "recurrence = corr(T's per-configuration profile before onset, after t_r). Migration gain = "
                    "corr(source profile before, destination profile after) − the same before migration."}


# ------------------------------------------------------------------------------------------------ failures
def _failures(cells, controls, scored) -> dict:
    cats: dict[str, list] = {k: [] for k in ("simulator_failure", "numerical_failure", "benchmark_failure",
                                             "comparator_failure", "model_structure_failure", "controller_failure",
                                             "genuine_regime_transition")}
    allc = list(cells) + [{"key": CONTROL, "severity": 0.0, "seed": s, "runs": {**v["control"], **{k + "@noise": x for k, x in v["noise"].items()}}}
                          for s, v in controls.items()]
    run_failed = set()
    for c in allc:
        for name, r in c["runs"].items():
            where = {"perturbation": c["key"], "severity": c["severity"], "seed": c["seed"], "controller": name}
            if r["status"] != "ok":
                cat = r["failure"]["category"]
                cats.setdefault(cat, []).append({**where, "error": r["failure"].get("error")})
                run_failed.add((c["key"], c["severity"], c["seed"]))
                continue
            s = r.get("controller_summary", {})
            if s.get("comparator_errors") or s.get("numerical") or s.get("failed_inference"):
                cats["comparator_failure"].append({**where, **{k: s.get(k) for k in ("comparator_errors", "numerical", "failed_inference")}})
            if name in ("aif_fixed", "aif_adaptive", "ost") and c["key"] != CONTROL:
                v, b = _get(r, "success_pert"), _get(c["runs"].get("none"), "success_pert")
                if v is not None and b is not None and v < b - 0.2:
                    cats["controller_failure"].append({**where, "success_pert": v, "none_success_pert": b})
    for r in scored:
        where = {"perturbation": r["key"], "severity": r["severity"], "seed": r["seed"]}
        if r["S_model"] is not None and r["S_model"] < RC.LO:
            cats["model_structure_failure"].append({**where, "S_model": r["S_model"], "S_model_adaptive": r["S_model_adaptive"]})
        if r["label"] in RC.LABELS[1:] and (r["key"], r["severity"], r["seed"]) not in run_failed:
            cats["genuine_regime_transition"].append({**where, "label": r["label"], "C_AIF": r["C_AIF"],
                                                      "first_unstable": r["first_unstable"]})
    return {"taxonomy": {
        "simulator_failure": "exception or non-finite state inside the runtime (run aborted)",
        "numerical_failure": "non-finite runtime state detected by the benchmark (run aborted)",
        "benchmark_failure": "exception in benchmark code outside the runtime (run aborted)",
        "comparator_failure": "comparator exception, non-finite belief/free energy, or zero-evidence inference (run continued)",
        "model_structure_failure": "fixed generative model's predictive validity < 0.5 of the unperturbed reference",
        "controller_failure": "controller success in the perturbation phase > 0.2 below no control (same cell, seed)",
        "genuine_regime_transition": "cell-seed labelled TRANSITION or POST_ACTIVE_INFERENCE with no aborted run"},
        "categories": cats, "counts": {k: len(v) for k, v in cats.items()},
        "note": "no run is discarded; aborted runs are excluded from metrics that need them and listed here"}


# ------------------------------------------------------------------------------------------------ adaptive refinement
def refine(cfg: dict, od: Path) -> Path:
    controls, cells = load(od)
    by_cell = defaultdict(list)
    for c in cells:
        ref = controls.get(c["seed"])
        if ref:
            by_cell[(c["key"], c["severity"])].append(RC.scores(c["runs"], ref["control"], ref["noise"], RC.tolerance(controls)))
    extra: dict[str, list[float]] = {k: list(v) for k, v in cfg.get("extra_severities", {}).items()}
    for key in sorted({k for k, _ in by_cell}):
        sevs = sorted(s for k, s in by_cell if k == key)
        levels = [0.0] + sevs
        curve = [1.0] + [float(np.nanmean([r["C_AIF"] for r in by_cell[(key, s)] if r["C_AIF"] is not None] or [np.nan])) for s in sevs]
        for thr_ in (RC.HI, RC.LO):
            for i in range(1, len(levels)):
                a, b = curve[i - 1], curve[i]
                if np.isfinite(a) and np.isfinite(b) and a >= thr_ > b:
                    lo, hi = levels[i - 1], levels[i]
                    for f in (1 / 3, 2 / 3):
                        v = round(lo + f * (hi - lo), 3)
                        if v > 0 and v not in sevs and v not in extra.get(key, []):
                            extra.setdefault(key, []).append(v)
                    break
    new = {k: v for k, v in cfg.items() if not k.startswith("_")}
    new["extra_severities"] = {k: sorted(v) for k, v in extra.items()}
    p = Path(cfg["_path"]).with_name(Path(cfg["_path"]).stem + "_refined.json")
    p.write_text(json.dumps(new, indent=1))
    return p


__all__ = ["analyse", "refine", "sign_flip_p"]
