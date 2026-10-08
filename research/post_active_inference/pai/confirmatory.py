"""Confirmatory analysis of the research stage, implementing PREREGISTRATION.md §§ 2–4 exactly.

    python run_benchmark.py analyse configs/research.json      # secondary, development-style analysis (summary.json)
    python -m pai.confirmatory results/research                # this protocol → confirmatory.json + confirmatory_tables.md

D, D_post and K come from the frozen development labels in results/research/preregistration.json (or, for testing on
the development stage itself, from that stage's summary.json). Research statistics use only the given stage directory.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import fisher_exact, spearmanr

import regime_classifier as RC

from .analysis import _get, load
from .perturbations import REGISTRY
from .stats import cohen_dz, describe, holm, paired, threshold

LABS = RC.LABELS
COMPAT, TRANS, POST = LABS
D_POST_DEV = ("sensor.delay", "sensor.dropout", "sensor.reassignment", "temporal.asynchronous", "variable.deletion",
              "boundary.reassignment", "temporal.interface_drift")
WORLD_FAMILIES = ("topology", "coupling", "memory", "structural")


def _sets(dev_labels: dict) -> tuple[list, list, list]:
    by: dict[str, list] = defaultdict(list)
    for cell, v in dev_labels.items():
        k, _, _ = cell.partition("@")
        by[k].append(v["label"])
    D = sorted(k for k, ls in by.items() if any(x != COMPAT for x in ls))
    K = sorted(k for k, ls in by.items() if all(x == COMPAT for x in ls))
    Dp = sorted(k for k in D if any(x == POST for x in by[k]))
    return D, Dp, K


def _sequence(labels: list[str]) -> str:
    if POST in labels:
        first_p = labels.index(POST)
        before = labels[:first_p]
        mono = all(_rank(labels[i]) <= _rank(labels[i + 1]) for i in range(len(labels) - 1))
        if not mono:
            return "non-monotone"
        return "C→T→P" if TRANS in before else "C→P"
    if TRANS in labels:
        mono = all(_rank(labels[i]) <= _rank(labels[i + 1]) for i in range(len(labels) - 1))
        return "C→T" if mono else "non-monotone"
    return "C only"


def _rank(lab: str | None) -> int:
    return {COMPAT: 0, TRANS: 1, POST: 2}.get(lab, -1)


def analyse(stage_dir: str, dev_labels: dict | None = None, out_dir: str | None = None) -> dict:
    od = Path(stage_dir)
    outp = Path(out_dir) if out_dir else od
    if dev_labels is None:
        dev_labels = json.loads((od / "preregistration.json").read_text())["development_reference_labels"]
    D, Dp, K = _sets(dev_labels)
    controls, cells = load(od)
    tol = RC.tolerance(controls)
    # --- per cell × seed scores (+ derived continuous scores, § 2)
    rows = []
    for c in cells:
        ref = controls.get(c["seed"])
        if ref is None:
            continue
        s = RC.scores(c["runs"], ref["control"], ref["noise"], tol)
        sm = [x for x in (s["S_model"], s["S_variable"]) if x is not None]
        s["structural_instability"] = 1 - min(sm) if sm else None
        pc = _get(c["runs"].get("none"), "persistence_pert")
        pr = [x for x in (_get(ref["control"].get("none"), "persistence_pert"), _get(ref["noise"].get("none"), "persistence_pert"))
              if x is not None]
        s["operational_persistence"] = float(np.clip(pc / np.mean(pr), 0, 1)) if pc is not None and pr and np.mean(pr) > 0 else None
        for ctl in ("none", "aif_fixed", "aif_adaptive", "ost"):
            s[f"success_pert_{ctl}"] = _get(c["runs"].get(ctl), "success_pert")
            s[f"success_rec_{ctl}"] = _get(c["runs"].get(ctl), "success_rec")
            s[f"acc_pert_{ctl}"] = _get(c["runs"].get(ctl), "one_step_acc_pert")
        s["control_success_rec_aif_adaptive"] = _get(ref["control"].get("aif_adaptive"), "success_rec")
        rows.append({"key": c["key"], "family": c["key"].split(".")[0], "side": REGISTRY[c["key"]].side,
                     "severity": c["severity"], "seed": c["seed"], **s})
    by_cell = defaultdict(list)
    for r in rows:
        by_cell[(r["key"], r["severity"])].append(r)
    cell = {k: RC.cell_label(v) for k, v in by_cell.items()}
    # --- Q1 null (leave-one-seed-out tolerance)
    null = {seed: RC.null_scores(v["control"], v["noise"], RC.tolerance(controls, exclude=seed)) for seed, v in controls.items()}
    nl = Counter(n["label"] for n in null.values())
    nmeans = {k: float(np.mean([n[k] for n in null.values() if n.get(k) is not None]))
              for k in ("S_sensor", "S_model", "S_variable") if any(n.get(k) is not None for n in null.values())}
    null_cell = RC.label(min(nmeans.values())) if nmeans else None
    q1 = {"per_seed": dict(nl), "n": len(null), "cell_level": {"scores": nmeans, "label": null_cell},
          "confirmed": bool(null_cell == COMPAT and nl.get(COMPAT, 0) >= 0.9 * len(null))}
    null_c = {seed: n["C_AIF"] for seed, n in null.items()}
    null_mean = float(np.mean([v for v in null_c.values() if v is not None])) if null_c else 1.0
    # --- per perturbation: severity sweep, thresholds, sequence, kind, per-severity statistics (Q2–Q5)
    per = {}
    for k in sorted({k for k, _ in by_cell}):
        sevs = sorted(s for kk, s in by_cell if kk == k)
        seeds = sorted({r["seed"] for s in sevs for r in by_cell[(k, s)]})
        M = np.full((len(seeds), len(sevs) + 1), np.nan)
        M[:, 0] = null_mean
        sev_stats = []
        for j, s in enumerate(sevs):
            rs = by_cell[(k, s)]
            cs = []
            dz_d = []
            for r in rs:
                if r["C_AIF"] is not None:
                    M[seeds.index(r["seed"]), j + 1] = r["C_AIF"]
                    cs.append(r["C_AIF"])
                    if null_c.get(r["seed"]) is not None:
                        dz_d.append(r["C_AIF"] - null_c[r["seed"]])
            d = describe(cs)
            sev_stats.append({
                "severity": s, "n_seeds": len(rs), "C_AIF": {kk: d[kk] for kk in ("mean", "median", "sd", "ci95")},
                "effect_size_dz_vs_null": cohen_dz(dz_d), "direction_consistency": (float(np.mean([x < 0 for x in dz_d])) if dz_d else None),
                "seed_labels": dict(Counter(r["label"] for r in rs)), "cell_label": cell[(k, s)]["label"],
                "cell_scores": cell[(k, s)]["scores"],
                "structural_instability": describe([r["structural_instability"] for r in rs])["mean"],
                "operational_persistence": describe([r["operational_persistence"] for r in rs])["mean"],
                "task_success": {ctl: describe([r[f"success_pert_{ctl}"] for r in rs])["mean"] for ctl in ("none", "aif_fixed", "aif_adaptive", "ost")},
                "predictive_acc": {ctl: describe([r[f"acc_pert_{ctl}"] for r in rs])["mean"] for ctl in ("aif_fixed", "aif_adaptive", "ost")},
                "primitives": {p: describe([r[p] for r in rs])["mean"] for p in RC.SCORES}})
        levels = [0.0] + sevs
        thr = {str(t): threshold(levels, M, t) for t in (RC.HI, RC.LO)}
        seq_labels = [cell[(k, s)]["label"] for s in sevs]
        means = [x["C_AIF"]["mean"] for x in sev_stats]
        halfw = [((x["C_AIF"]["ci95"][1] - x["C_AIF"]["ci95"][0]) / 2) if x["C_AIF"]["ci95"] else 0.0 for x in sev_stats]
        inconsistent = any(means[i + 1] is not None and means[i] is not None and means[i + 1] - means[i] > max(halfw[i], halfw[i + 1])
                           for i in range(len(means) - 1))
        seq = _sequence(seq_labels)
        if inconsistent:
            kind = "inconsistent"
        elif TRANS in seq_labels:
            kind = "gradual"
        elif POST in seq_labels:
            kind = "abrupt"
        else:
            kind = "compatible_throughout"
        per[k] = {"side": REGISTRY[k].side, "severities": sevs, "cell_labels": seq_labels, "sequence": seq, "kind": kind,
                  "thresholds": thr, "by_severity": sev_stats}
    # --- Q2 replication
    q2 = {}
    for k in D:
        p = per.get(k)
        if p is None:
            q2[k] = {"replicated": None, "reason": "not run"}
            continue
        t8 = p["thresholds"]["0.8"]
        rep = (any(x != COMPAT for x in p["cell_labels"]) and t8.get("boot_never_share", 1) < 0.05
               and (t8.get("seeds_crossing_share") or 0) >= 0.5)
        dev_lab = {c: v["label"] for c, v in dev_labels.items() if c.startswith(k + "@")}
        q2[k] = {"replicated": bool(rep), "research_crossing_0.8": t8.get("estimate"), "ci95": t8.get("ci95"),
                 "seeds_crossing_share": t8.get("seeds_crossing_share"), "boot_never_share": t8.get("boot_never_share"),
                 "research_crossing_0.5": p["thresholds"]["0.5"].get("estimate"), "development_labels": dev_lab}
    reverse = {k: per[k]["cell_labels"] for k in K if k in per and any(x != COMPAT for x in per[k]["cell_labels"])}
    # --- Q3 sequence for D_post
    q3 = {k: {"sequence": per[k]["sequence"], "labels": per[k]["cell_labels"], "severities": per[k]["severities"],
              "replicated": bool(POST in per[k]["cell_labels"] and per[k]["sequence"] in ("C→T→P", "C→P"))}
          for k in Dp if k in per}
    # --- Q4 stability of principal crossings
    q4 = {}
    for k in D:
        if k not in per:
            continue
        for t in ("0.8", "0.5"):
            th = per[k]["thresholds"][t]
            ci = th.get("ci95")
            q4[f"{k}|{t}"] = {"estimate": th.get("estimate"), "ci95": ci, "ci_width": (ci[1] - ci[0]) if ci else None,
                              "seeds_crossing_share": th.get("seeds_crossing_share"), "per_seed_iqr": th.get("per_seed_iqr"),
                              "boot_never_share": th.get("boot_never_share"),
                              "stable": bool(ci is not None and ci[1] - ci[0] <= 0.25 and (th.get("seeds_crossing_share") or 0) >= 0.8)}
    # --- Q5 kinds + task-level persistence after reversal
    q5 = {k: per[k]["kind"] for k in D if k in per}
    hyst = []
    for k in D:
        P = REGISTRY[k]
        if P.revert is None or P.permanent or k not in per:
            continue
        for s in per[k]["severities"]:
            d = [r["success_rec_aif_adaptive"] - r["control_success_rec_aif_adaptive"] for r in by_cell[(k, s)]
                 if r["success_rec_aif_adaptive"] is not None and r["control_success_rec_aif_adaptive"] is not None]
            if len(d) >= 3:
                hyst.append({"perturbation": k, "severity": s, **paired(d, 0.05)})
    for h, p in zip(hyst, holm([h["p"] for h in hyst]) if hyst else [], strict=True):
        h["p_holm"] = p
        h["persists_after_reversal"] = bool(p < 0.05 and h["mean"] < 0)
    # --- Q6 side share of POST
    side_cells = defaultdict(Counter)
    side_seed = defaultdict(Counter)
    for (k, _s), v in cell.items():
        side_cells[REGISTRY[k].side][v["label"]] += 1
    for r in rows:
        side_seed[r["side"]][r["label"]] += 1
    oi = [side_seed["observation"][POST] + side_seed["interface"][POST],
          sum(side_seed["observation"].values()) + sum(side_seed["interface"].values())]
    wd = [side_seed["world"][POST], sum(side_seed["world"].values())]
    table = [[oi[0], oi[1] - oi[0]], [wd[0], wd[1] - wd[0]]]
    odds, pf = fisher_exact(table) if oi[1] and wd[1] else (None, None)
    q6 = {"cells_by_side": {k: dict(v) for k, v in side_cells.items()}, "cell_seeds_by_side": {k: dict(v) for k, v in side_seed.items()},
          "post_share_observation_interface": oi[0] / oi[1] if oi[1] else None, "post_share_world": wd[0] / wd[1] if wd[1] else None,
          "fisher_odds_ratio": odds, "fisher_p": pf}
    # --- Q7 world-side families
    q7 = {}
    for fam in WORLD_FAMILIES:
        labs = [v["label"] for (k, s), v in cell.items() if k.startswith(fam + ".")]
        q7[fam] = {"max_cell_label": max(labs, key=_rank) if labs else None, "cell_labels": dict(Counter(labs)),
                   "seed_post": sum(1 for r in rows if r["family"] == fam and r["label"] == POST)}
    q7["confirmed"] = all(q7[f]["max_cell_label"] != POST for f in WORLD_FAMILIES if q7[f]["max_cell_label"])
    # --- Q8 dissociation
    post_cells = [k for k, v in cell.items() if v["label"] == POST]
    a = {}
    for scope, sel in (("cell_level_post", [r for r in rows if (r["key"], r["severity"]) in post_cells]),
                       ("seed_level_post", [r for r in rows if r["label"] == POST])):
        tests = []
        for ctl in ("aif_fixed", "aif_adaptive"):
            d = [r[f"success_pert_{ctl}"] - r["success_pert_none"] for r in sel
                 if r[f"success_pert_{ctl}"] is not None and r["success_pert_none"] is not None]
            tests.append({"contrast": f"{ctl} - none", **paired(d, 0.05)} if len(d) >= 3 else {"contrast": f"{ctl} - none", "n": len(d)})
        ps = [t.get("p", 1.0) for t in tests]
        for t, p in zip(tests, holm(ps), strict=True):
            t["p_holm"] = p
        a[scope] = {"n_cell_seeds": len(sel), "tests": tests}
    adv, accs, cs = [], [], []
    for (k, s), v in cell.items():
        rs = by_cell[(k, s)]
        x = [r["success_pert_aif_adaptive"] - r["success_pert_none"] for r in rs if r["success_pert_aif_adaptive"] is not None and r["success_pert_none"] is not None]
        y = [r["acc_pert_aif_adaptive"] for r in rs if r["acc_pert_aif_adaptive"] is not None]
        if v["C_AIF"] is not None and x and y:
            cs.append(v["C_AIF"])
            adv.append(float(np.mean(x)))
            accs.append(float(np.mean(y)))

    def sp(u, w):
        if len(u) < 5:
            return None
        rho = float(spearmanr(u, w).statistic)
        rng = np.random.default_rng(0)
        b = []
        u, w = np.asarray(u), np.asarray(w)
        for _ in range(2000):
            i = rng.integers(0, len(u), len(u))
            if np.std(u[i]) > 0 and np.std(w[i]) > 0:
                b.append(spearmanr(u[i], w[i]).statistic)
        return {"rho": rho, "ci95": [float(np.quantile(b, 0.025)), float(np.quantile(b, 0.975))] if b else None, "n_cells": len(u)}
    q8 = {"a": a, "b_spearman_C_vs_task_advantage": sp(cs, adv), "c_spearman_C_vs_predictive_acc": sp(cs, accs),
          "dissociation_supported": bool(any(t.get("p_holm", 1) < 0.05 and (t.get("mean") or 0) > 0 for t in a["cell_level_post"]["tests"]))}
    # --- secondary: tolerance sensitivity with the frozen development tolerance
    from .preregister import DEV_TOLERANCE
    sens = Counter()
    for (k, s), rs0 in by_cell.items():
        rs2 = []
        for r in rs0:
            c = next(c for c in cells if c["key"] == k and c["severity"] == s and c["seed"] == r["seed"])
            ref = controls[r["seed"]]
            rs2.append(RC.scores(c["runs"], ref["control"], ref["noise"], DEV_TOLERANCE))
        sens[RC.cell_label(rs2)["label"]] += 1
    out = {"sets": {"D": D, "D_post": Dp, "K": K}, "noise_tolerance": tol, "Q1": q1, "Q2": q2,
           "Q2_replicated_count": f"{sum(1 for v in q2.values() if v.get('replicated'))}/{len(D)}", "Q2_reverse_check": reverse,
           "Q3": q3, "Q4": q4, "Q4_stable_count": f"{sum(1 for v in q4.values() if v['stable'])}/{len(q4)}", "Q5": q5,
           "Q5_task_persistence_after_reversal": hyst, "Q6": q6, "Q7": q7, "Q8": q8,
           "cell_level_regimes": dict(Counter(v["label"] for v in cell.values())),
           "secondary_dev_tolerance_cell_regimes": dict(sens), "per_perturbation": per}
    outp.mkdir(parents=True, exist_ok=True)
    (outp / "confirmatory.json").write_text(json.dumps(out, indent=1, default=_j))
    (outp / "confirmatory_tables.md").write_text(tables(out))
    return out


def _j(x):
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x) if np.isfinite(x) else None
    if isinstance(x, np.bool_):
        return bool(x)
    return str(x)


def _f(x, d=2):
    return "—" if x is None else (f"{x:.{d}f}" if isinstance(x, float) else str(x))


def tables(o: dict) -> str:
    L = ["# Confirmatory tables (PREREGISTRATION.md protocol)", "",
         f"Q1 null: per-seed {o['Q1']['per_seed']} (n={o['Q1']['n']}); cell-level {o['Q1']['cell_level']['label']} → "
         f"**{'confirmed' if o['Q1']['confirmed'] else 'not confirmed'}**", "",
         f"Noise tolerance: {json.dumps({k: round(v, 3) for k, v in o['noise_tolerance'].items()})}", "",
         f"Cell-level regimes: {o['cell_level_regimes']}; with the development tolerance (secondary): {o['secondary_dev_tolerance_cell_regimes']}", "",
         f"## Q2 replication of development crossings: {o['Q2_replicated_count']}", "",
         "| perturbation | replicated | crossing 0.8 [CI] | seeds crossing | crossing 0.5 | development labels |", "|---|---|---|---|---|---|"]
    for k, v in o["Q2"].items():
        ci = v.get("ci95")
        L.append(f"| {k} | {v.get('replicated')} | {_f(v.get('research_crossing_0.8'))} {[round(x, 2) for x in ci] if ci else ''} | "
                 f"{_f(v.get('seeds_crossing_share'))} | {_f(v.get('research_crossing_0.5'))} | "
                 f"{', '.join(f'{c.split(chr(64))[1]}:{lab[:5]}' for c, lab in sorted(v.get('development_labels', {}).items()))} |")
    L += ["", f"Reverse check (compatible in development, non-compatible in research): {o['Q2_reverse_check'] or 'none'}", "",
          "## Q3 sequences (D_post)", "", "| perturbation | sequence | replicated | labels by severity |", "|---|---|---|---|"]
    for k, v in o["Q3"].items():
        L.append(f"| {k} | {v['sequence']} | {v['replicated']} | " + ", ".join(f"{s:g}:{(lab or '—')[:5]}" for s, lab in zip(v["severities"], v["labels"], strict=True)) + " |")
    L += ["", f"## Q4 principal crossings: stable {o['Q4_stable_count']}", "",
          "| crossing | estimate | CI | width | seeds crossing | per-seed IQR | stable |", "|---|---|---|---|---|---|---|"]
    for k, v in o["Q4"].items():
        L.append(f"| {k} | {_f(v['estimate'])} | {v['ci95'] and [round(x, 2) for x in v['ci95']]} | {_f(v['ci_width'])} | "
                 f"{_f(v['seeds_crossing_share'])} | {v['per_seed_iqr'] and [round(x, 2) for x in v['per_seed_iqr']]} | {v['stable']} |")
    L += ["", "## Per-severity statistics for D", ""]
    for k in o["sets"]["D"]:
        p = o["per_perturbation"].get(k)
        if not p:
            continue
        L += [f"### {k} ({p['side']}; {p['kind']}; {p['sequence']})", "",
              "| sev | n | C mean | median | CI | dz vs null | direction | seed labels | cell | struct. instab. | op. persist. | success none / fixed / adaptive / ost | primitives (sensor, model, variable, boundary, policy) |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for x in p["by_severity"]:
            c = x["C_AIF"]
            sl = ", ".join(f"{n} {lab[:5]}" for lab, n in sorted(x["seed_labels"].items(), key=lambda t: _rank(t[0])))
            ts = " / ".join(_f(x["task_success"][ctl]) for ctl in ("none", "aif_fixed", "aif_adaptive", "ost"))
            pr = ", ".join(_f(x["primitives"][q]) for q in RC.SCORES)
            L.append(f"| {x['severity']:g} | {x['n_seeds']} | {_f(c['mean'])} | {_f(c['median'])} | {c['ci95'] and [round(v, 2) for v in c['ci95']]} | "
                     f"{_f(x['effect_size_dz_vs_null'])} | {_f(x['direction_consistency'])} | {sl} | {(x['cell_label'] or '—')[:5]} | "
                     f"{_f(x['structural_instability'])} | {_f(x['operational_persistence'])} | {ts} | {pr} |")
        L.append("")
    L += ["## Q5 kinds", "", json.dumps(dict(Counter(o["Q5"].values()))), "", "Task-level persistence after reversal (Holm):", ""]
    for h in o["Q5_task_persistence_after_reversal"]:
        if h.get("persists_after_reversal"):
            L.append(f"* {h['perturbation']} @ {h['severity']:g}: {_f(h['mean'])} (Holm p {_f(h['p_holm'], 4)})")
    L += ["", "## Q6 POST by side", "", "```", json.dumps(o["Q6"], indent=1, default=_j), "```", "",
          "## Q7 world-side families", "", "```", json.dumps(o["Q7"], indent=1, default=_j), "```", "",
          "## Q8 task performance vs representational validity", "", "```", json.dumps(o["Q8"], indent=1, default=_j), "```", ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    stage = sys.argv[1]
    dev = None
    if len(sys.argv) > 2:  # testing on a stage without preregistration.json: pass that stage's own summary.json
        dev = json.loads(Path(sys.argv[2]).read_text())["cell_classification"]
    o = analyse(stage, dev, sys.argv[3] if len(sys.argv) > 3 else None)
    print(json.dumps({k: o[k] for k in ("Q2_replicated_count", "Q4_stable_count", "cell_level_regimes")}, default=_j),
          "Q1", o["Q1"]["confirmed"], "Q7", o["Q7"]["confirmed"], "Q8", o["Q8"]["dissociation_supported"])
