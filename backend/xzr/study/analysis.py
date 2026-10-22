"""Statistical analysis of a study: descriptives, paired and independent comparisons, effect sizes, intervals, multiplicity,
sensitivity, failure and outlier accounting, criteria evaluation and the Ziran-specific records (reachability checks,
meta-revision, history re-entry, observation changes).

Rules kept here:
  * every declared contrast and every requested metric is reported, whatever it shows (negative and null results stay);
  * a comparison is confirmatory only if the protocol was confirmatory, registered, and the contrast was declared in the
    registered protocol; anything else is exploratory, and a functional study is never evidence;
  * a significance test is one number among several: the verdict of a criterion is about the declared effect size and
    interval, and says nothing about any theory;
  * a metric that is undefined for a run (NaN) is counted as undefined, never as zero.
"""

from __future__ import annotations

import hashlib
import json
import math
import warnings
from typing import Any

import numpy as np
from scipy import stats as sps

from ..hpo.experiments import clean
from ..hpo.stats import ALPHA, EQUIV, PRACTICAL, bootstrap_ci, holm, paired
from . import protocol as P
from .runner import Study


def _rng(study: Study, tag: str) -> np.random.Generator:
    h = hashlib.sha256((study.manifest()["protocol_digest"] + tag).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "big"))


def _bh(ps: dict[str, float]) -> dict[str, float]:
    items = sorted(ps.items(), key=lambda kv: kv[1])
    m = len(items)
    out, nxt = {}, 1.0
    for i in range(m - 1, -1, -1):
        k, p = items[i]
        nxt = min(nxt, p * m / (i + 1))
        out[k] = nxt
    return out


def describe(x: np.ndarray, rng: np.random.Generator) -> dict:
    ok = x[~np.isnan(x)]
    out: dict[str, Any] = {"n": int(ok.size), "undefined": int(x.size - ok.size)}
    if ok.size == 0:
        return out
    q1, med, q3 = (float(v) for v in np.quantile(ok, [0.25, 0.5, 0.75]))
    lo, hi = bootstrap_ci(ok, rng) if ok.size > 1 else (math.nan, math.nan)
    out.update(
        mean=float(ok.mean()),
        median=med,
        sd=float(ok.std(ddof=1)) if ok.size > 1 else None,  # one value has no spread: undefined, not 0
        var=float(ok.var(ddof=1)) if ok.size > 1 else None,
        min=float(ok.min()),
        max=float(ok.max()),
        q1=q1,
        q3=q3,
        ci95_mean=[lo, hi],
    )
    return out


def outliers(x: np.ndarray) -> list[dict]:
    """Values outside Tukey's fences (1.5 IQR) or with a robust z above 3.5; recorded, never removed."""
    ok = ~np.isnan(x)
    v = x[ok]
    if v.size < 4:
        return []
    q1, q3 = np.quantile(v, [0.25, 0.75])
    iqr = q3 - q1
    med = np.median(v)
    mad = np.median(np.abs(v - med))
    out = []
    for i in np.flatnonzero(ok):
        z = 0.6745 * (x[i] - med) / mad if mad > 0 else 0.0
        if (iqr > 0 and (x[i] < q1 - 1.5 * iqr or x[i] > q3 + 1.5 * iqr)) or abs(z) > 3.5:
            out.append({"index": int(i), "value": float(x[i]), "robust_z": float(z)})
    return out


def hedges_g(a: np.ndarray, b: np.ndarray) -> float | None:
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if a.size < 2 or b.size < 2:
        return None
    sp = math.sqrt(((a.size - 1) * a.var(ddof=1) + (b.size - 1) * b.var(ddof=1)) / (a.size + b.size - 2))
    if sp == 0:
        return 0.0 if a.mean() == b.mean() else None
    d = (a.mean() - b.mean()) / sp
    return float(d * (1 - 3 / (4 * (a.size + b.size) - 9)))


def sensitivity(x: np.ndarray, y: np.ndarray) -> dict:
    ok = ~(np.isnan(x) | np.isnan(y))
    d = (x - y)[ok]
    if d.size < 3:
        return {"n": int(d.size), "note": "fewer than 3 pairs: no sensitivity analysis"}
    loo = [float(np.delete(d, i).mean()) for i in range(d.size)]
    out: dict[str, Any] = {
        "n": int(d.size),
        "leave_one_out_mean_range": [min(loo), max(loo)],
        "sign_agreement": float(max((d > 0).mean(), (d < 0).mean())),
        "mean_without_outliers": None,
    }
    q1, q3 = np.quantile(d, [0.25, 0.75])
    iqr = q3 - q1
    keep = d[(d >= q1 - 1.5 * iqr) & (d <= q3 + 1.5 * iqr)] if iqr > 0 else d
    out["mean_without_outliers"] = float(keep.mean()) if keep.size else None
    out["n_without_outliers"] = int(keep.size)
    if np.any(d != 0):
        try:
            out["wilcoxon_p"] = float(sps.wilcoxon(d).pvalue)
        except ValueError:
            out["wilcoxon_p"] = None
    return out


def independent(x: np.ndarray, y: np.ndarray) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # scipy warns when samples are nearly identical; the result is reported as is
        return _independent(x, y)


def _independent(x: np.ndarray, y: np.ndarray) -> dict:
    a, b = x[~np.isnan(x)], y[~np.isnan(y)]
    if a.size < 2 or b.size < 2:
        return {"n_a": int(a.size), "n_b": int(b.size), "note": "too few trials"}
    out = {"n_a": int(a.size), "n_b": int(b.size), "hedges_g": hedges_g(a, b)}
    t = sps.ttest_ind(a, b, equal_var=False)
    out["welch_p"] = float(t.pvalue) if np.isfinite(t.pvalue) else None
    try:
        out["mann_whitney_p"] = float(sps.mannwhitneyu(a, b).pvalue)
    except ValueError:
        out["mann_whitney_p"] = None
    return out


def paired_safe(x: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> dict:
    """The paired comparison, with what cannot be estimated said so. Fewer than two complete pairs: no spread, interval, effect size or test exists,
    and none is invented (a zero would read as "no effect"; infinity as "perfect separation"). Missing data and a zero effect stay different things."""
    ok = ~(np.isnan(x) | np.isnan(y))
    n = int(ok.sum())
    if n >= 2:
        r = paired(x, y, None, rng)
        r["insufficient"] = None
        return r
    r = {
        "n": n,
        "undefined_pairs": int(x.size - n),
        "insufficient": f"{n} complete pair(s): spread, interval, effect size and test are not estimable",
        "sd": None,
        "dz": None,
        "ci95": [None, None],
        "p": None,
        "identical": False,
        "noise_floor": 0.0,
        "relative": None,
    }
    if n == 1:
        xv, yv = float(x[ok][0]), float(y[ok][0])
        r.update(mean_x=xv, mean_y=yv, mean=xv - yv, scale=max(abs(xv), abs(yv), 1e-12))
    return r


def status_of(r: dict) -> str:
    """DETECTED / EQUIVALENT / UNRESOLVED / IDENTICAL / NOT MEASURED — the HPO classification, kept for continuity."""
    if r.get("n", 0) == 0:
        return "NOT MEASURED"
    if r.get("insufficient"):
        return "INSUFFICIENT DATA"
    if r["identical"]:
        return "IDENTICAL"
    if r["p_holm"] < ALPHA and abs(r["mean"]) >= PRACTICAL * r["scale"] and abs(r["mean"]) > r["noise_floor"]:
        return "DETECTED"
    lo, hi = r["ci95"]
    if math.isfinite(lo) and -EQUIV * r["scale"] <= lo and hi <= EQUIV * r["scale"]:
        return "EQUIVALENT"
    return "UNRESOLVED"


def evidence_class(doc: dict, registered: dict, amendments: list[dict], contrast_id: str) -> str:
    if doc["mode"] == "functional":
        return "functional check (not evidence)"
    if doc["mode"] == "exploratory":
        return "exploratory"
    declared = any(c["id"] == contrast_id for c in registered.get("contrasts", []))
    late = any(a["runs_started"] for a in amendments)
    if declared and registered.get("freeze") and not late:
        return "confirmatory"
    return "exploratory (declared after the first run or not registered)" if late else "exploratory (contrast not registered)"


def _criterion(c: dict, res: dict | None) -> dict:
    if res is None or res.get("n", 0) == 0 or res.get("insufficient") or res.get("ci95", [None, None])[0] is None:
        return {
            **c,
            "result": "not evaluable",
            "why": "metric undefined, too few complete pairs for an interval, or contrast missing",
        }
    mean, scale = res["mean"], max(res["scale"], 1e-12)
    rel = mean / scale
    lo, hi = res["ci95"]
    need = float(c.get("min_relative_effect", 0.0))
    d = c["direction"]
    if d == "greater":
        eff = rel >= need
        ci = lo > 0 if c.get("ci_excludes_zero", True) else True
    elif d == "less":
        eff = rel <= -need
        ci = hi < 0 if c.get("ci_excludes_zero", True) else True
    elif d == "different":
        eff = abs(rel) >= need
        ci = (lo > 0 or hi < 0) if c.get("ci_excludes_zero", True) else True
    else:  # equivalent
        eff = math.isfinite(lo) and lo >= -EQUIV * scale and hi <= EQUIV * scale
        ci = True
    met = bool(eff and ci)
    return {
        **c,
        "result": "met" if met else "not met",
        "observed_relative_effect": rel,
        "ci95": [lo, hi],
        "effect_ok": bool(eff),
        "interval_ok": bool(ci),
        "n_pairs": res["n"],
    }


def analyse(study: Study, write: bool = True) -> dict:
    doc = study.protocol()
    reg = study.registered()
    amends = study.amendments()
    runs = study.runs()
    arms = [a["name"] for a in doc["arms"]]
    seeds = P.seed_list(doc)
    by = {(r["arm"], r["index"]): r for r in runs}
    # run accounting
    acc = {}
    for a in arms:
        rs = [by.get((a, k)) for k in range(len(seeds))]
        st = [r["status"] if r else "not run" for r in rs]
        acc[a] = {
            "planned": len(seeds),
            "ok": st.count("ok"),
            "failed": st.count("failed"),
            "timeout": st.count("timeout"),
            "not_run": st.count("not run"),
            "failure_rate": (st.count("failed") + st.count("timeout")) / max(1, len(seeds) - st.count("not run")),
            "errors": sorted({r.get("error", "") for r in rs if r and r["status"] != "ok"})[:5],
        }
    metrics = list(dict.fromkeys(doc["metrics"]["primary"] + doc["metrics"].get("secondary", [])))

    def vec(arm: str, m: str) -> np.ndarray:
        out = []
        for k in range(len(seeds)):
            r = by.get((arm, k))
            v = r["metrics"].get(m) if r and r["status"] == "ok" and r.get("metrics") else None
            out.append(math.nan if v is None else float(v))
        return np.array(out, float)

    rng = _rng(study, "describe")
    desc = {a: {m: describe(vec(a, m), rng) for m in metrics} for a in arms}
    outs = {a: {m: o for m in metrics if (o := outliers(vec(a, m)))} for a in arms}
    # contrasts
    contrasts = []
    family: dict[str, float] = {}
    for c in doc.get("contrasts", []):
        rows: dict[str, Any] = {}
        rng_c = _rng(study, "contrast" + c["id"])
        for m in metrics:
            x, y = vec(c["a"], m), vec(c["b"], m)
            r = paired_safe(x, y, rng_c)
            r["independent"] = independent(x, y)
            r["sensitivity"] = sensitivity(x, y)
            rows[m] = r
            if r.get("n", 0) >= 2 and r.get("p") is not None:
                family[f"{c['id']}|{m}"] = r["p"]
        contrasts.append(
            {
                "id": c["id"],
                "a": c["a"],
                "b": c["b"],
                "role": c.get("role", "secondary"),
                "varies": c.get("varies", []),
                "evidence": evidence_class(doc, reg, amends, c["id"]),
                "metrics": rows,
            }
        )
    hol, bh = holm(family), _bh(family)
    for c in contrasts:
        for m, r in c["metrics"].items():
            k = f"{c['id']}|{m}"
            if k in hol:
                r["p_holm"], r["p_bh"] = hol[k], bh[k]
            else:
                r["p_holm"] = r["p_bh"] = None  # no test was possible: neither "significant" nor p = 1
            r["status"] = status_of(r)
    cres = {c["id"]: c for c in contrasts}
    crit = doc.get("criteria", {})
    succ = [_criterion(x, (cres.get(x["contrast"]) or {}).get("metrics", {}).get(x["metric"])) for x in crit.get("success", [])]
    fail = [_criterion(x, (cres.get(x["contrast"]) or {}).get("metrics", {}).get(x["metric"])) for x in crit.get("failure", [])]
    if any(x["result"] == "not evaluable" for x in succ + fail):
        verdict = "not evaluable: a criterion's metric or contrast is undefined"
    elif any(x["result"] == "met" for x in fail):
        verdict = "failure criterion met"
    elif succ and all(x["result"] == "met" for x in succ):
        verdict = "success criteria met"
    elif succ:
        verdict = "success criteria not met"
    else:
        verdict = "no criteria declared"
    low_n = [x for x in succ + fail if x.get("n_pairs", 99) < 8]
    if low_n:
        verdict += " (fewer than 8 pairs: the interval rests on very few seeds and is unreliable)"
    out = {
        "schema": "xzr.studyanalysis/1",
        "experiment_id": study.id,
        "protocol_digest": study.manifest()["protocol_digest"],
        "mode": doc["mode"],
        "label": "FUNCTIONAL CHECK — not evidence" if doc["mode"] == "functional" else doc["mode"],
        "n_seeds": len(seeds),
        "arms": arms,
        "metrics": metrics,
        "accounting": acc,
        "descriptives": desc,
        "outliers": outs,
        "contrasts": contrasts,
        "multiplicity": {
            "family_size": len(family),
            "methods": ["Holm (family-wise)", "Benjamini-Hochberg (FDR)"],
            "family": "all contrasts x metrics reported here",
        },
        "criteria": {
            "success": succ,
            "failure": fail,
            "verdict": verdict,
            "scope": "The verdict concerns this protocol's declared criteria only; it is not a statement about any theory.",
        },
        "fairness": P.fairness(doc),
        "amendments": amends,
        "ziran": ziran_records(doc, runs, arms),
        "meta_followup": meta_followup(doc, runs, by, len(seeds)),
        "censoring": censoring(doc, runs, arms),
        "negative_results_note": "Every declared contrast and metric is listed above, including null and reversed effects.",
        "seeds": seeds,
    }
    out = clean(out)
    if write:
        (study.path / "analysis.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, allow_nan=False))
        study.log("analysed", verdict=verdict)
    return out


def meta_followup(doc: dict, runs: list[dict], by: dict, n: int) -> list[dict]:
    """For every declared contrast that differs only in meta-revision: what the revisions were, whether later changes used the revised rules, and what
    happened to the outcome and the resources, seed by seed against the control without revision. Improvement and worsening are both reported;
    neither is assumed. (Runs of a protocol that imposes scarcity are artificial conditions: the protocol's own provenance field says so.)"""
    out = []
    for c in doc.get("contrasts", []):
        if c.get("varies") != ["meta_revision"]:
            continue
        rows = []
        for k in range(n):
            ra, rb = by.get((c["a"], k)), by.get((c["b"], k))
            if not (
                ra and rb and ra["status"] == "ok" and rb["status"] == "ok" and ra.get("controller") and rb.get("controller")
            ):
                continue
            mt = ra["controller"].get("meta_trace") or []
            first = min((m["epoch"] for m in mt if m["revision"] == "parameter"), default=None)
            after = [
                ch
                for ch in (ra.get("controller_changes") or [])
                if first is not None and ch.get("epoch", -1) > first and "rules_in_force" in ch
            ]
            default = (ra["controller"].get("rules") or {}).get("params") and {
                k2: v for k2, v in (ra["controller"]["rules"]["params"]).items()
            }
            reflected = [
                ch
                for ch in after
                if default is not None and ch["rules_in_force"] != next(iter(ra["controller_changes"]))["rules_in_force"]
            ]
            fa, fb = ra["metrics"].get("fired_samples"), rb["metrics"].get("fired_samples")
            d = None if fa is None or fb is None else fa - fb
            tol = 0.02 * max(abs(fb or 0), 1e-12)
            rows.append(
                {
                    "seed": k,
                    "revisions": sum(1 for m in mt if m["revision"] == "parameter"),
                    "exhausted": sum(1 for m in mt if m["revision"] == "exhausted"),
                    "changes_after_first_revision": len(after),
                    "changes_using_revised_rules": len(reflected),
                    "evidence_recorded": all(m.get("evidence") is not None and m.get("before") is not None for m in mt),
                    "delta_fired": d,
                    "verdict": None if d is None else "improved" if d > tol else "worsened" if d < -tol else "unchanged",
                    "delta_measure_cost": (ra["metrics"].get("measure_cost") or 0) - (rb["metrics"].get("measure_cost") or 0),
                    "delta_controller_changes": (ra["metrics"].get("controller_changes") or 0)
                    - (rb["metrics"].get("controller_changes") or 0),
                }
            )
        v = [r["verdict"] for r in rows if r["verdict"]]
        out.append(
            {
                "contrast": c["id"],
                "meta_arm": c["a"],
                "control_arm": c["b"],
                "pairs": len(rows),
                "runs_with_a_revision": sum(1 for r in rows if r["revisions"]),
                "improved": v.count("improved"),
                "worsened": v.count("worsened"),
                "unchanged": v.count("unchanged"),
                "rows": rows,
                "note": "revision success, failure and exhaustion are separate counts; 'improved' / 'worsened' compare fired samples with the control on the same seed "
                "(tolerance 2%); no direction is assumed, and a revision is not evidence of improvement.",
            }
        )
    return out


def censoring(doc: dict, runs: list[dict], arms: list[str]) -> dict:
    """first_ignition_mean is censored at the horizon for kinds that never ignite; never_ignited counts those kinds."""
    out = {}
    for a in arms:
        ms = [r["metrics"] for r in runs if r["arm"] == a and r["status"] == "ok" and r.get("metrics")]
        out[a] = {
            "runs_with_censored_first_ignition": sum(1 for m in ms if (m.get("never_ignited") or 0) > 0),
            "censoring_point": int(doc["environment"].get("horizon", 0)),
            "runs_stopped_early": sum(1 for r in runs if r["arm"] == a and r.get("stopped_at") is not None),
        }
    return out


def ziran_records(doc: dict, runs: list[dict], arms: list[str]) -> dict:
    out: dict[str, Any] = {}
    for a in arms:
        rs = [r for r in runs if r["arm"] == a and r["status"] == "ok"]
        e: dict[str, Any] = {"runs": len(rs)}
        chk = [r["reachability_check"] for r in rs if r.get("reachability_check")]
        if chk:
            on = sum(c["opened"]["n"] for c in chk)
            cn = sum(c["closed"]["n"] for c in chk)
            e["reachability"] = {
                "opened_predictions": on,
                "opened_then_acted": sum(c["opened"]["acted"] for c in chk),
                "opened_not_used": on - sum(c["opened"]["acted"] for c in chk),
                "opened_success_rate": (sum(c["opened"]["acted"] for c in chk) / on) if on else None,
                "closed_predictions": cn,
                "closed_consistent": sum(c["closed"]["silent"] for c in chk),
                "closed_consistency_rate": (sum(c["closed"]["silent"] for c in chk) / cn) if cn else None,
                "note": chk[0].get("note")
                or "opened = the operation could observe what it needs; success = it acted in the next epoch. Opening is "
                "not success; the gap between the two is the estimation error of the reachability record.",
            }
        chs = [c for r in rs for c in (r.get("controller_changes") or []) + (r.get("protocol_changes") or [])]
        gained = sum(len(c["reachability"]["channels_opened"]) for c in chs if c.get("reachability"))
        lost = sum(len(c["reachability"]["channels_closed"]) for c in chs if c.get("reachability"))
        e["observation_changes"] = {
            "controller": sum(len(r.get("controller_changes") or []) for r in rs),
            "protocol": sum(len(r.get("protocol_changes") or []) for r in rs),
            "rejected_by_authority_or_budget": sum(len((r.get("controller") or {}).get("rejected") or []) for r in rs),
            "channels_gained": gained,
            "channels_lost": lost,
        }
        lv_changes = [c for c in chs if c.get("levels")]
        if lv_changes:
            eff = {"static": {}, "dynamic": {}}
            for c in lv_changes:
                eff["static"][c["levels"]["static"]["effect"]] = eff["static"].get(c["levels"]["static"]["effect"], 0) + 1
                if "dynamic" in c["levels"]:
                    eff["dynamic"][c["levels"]["dynamic"]["effect"]] = eff["dynamic"].get(c["levels"]["dynamic"]["effect"], 0) + 1
            opened = [(c, o) for c in lv_changes for o in c["levels"]["static"]["available"]["gained"]]
            settled = [(c, o) for c, o in opened if c.get("realised")]
            e["levels"] = {
                "changes": len(lv_changes),
                "effect_counts": eff,
                "available_gained": len(opened),
                "of_which_succeeded_next_epoch": sum(1 for c, o in settled if c["realised"]["success"].get(o, 0) > 0),
                "of_which_used": sum(1 for c, o in settled if c["realised"]["used"].get(o, 0) > 0),
                "settled": len(settled),
                "observable_cells_gained": sum(len(c["levels"]["static"]["observable_cells"]["gained"]) for c in lv_changes),
                "observable_cells_lost": sum(len(c["levels"]["static"]["observable_cells"]["lost"]) for c in lv_changes),
                "reachable_configurations_delta": sum(
                    c["levels"]["static"]["reachable_configurations"]["delta"] for c in lv_changes
                ),
                "note": "static = immediately after the change; dynamic = after the next epoch against the state before it (includes the world's own "
                "change, so the controlled comparison is across arms). Gained availability, success and use are counted separately.",
            }
        meta = [
            r["controller"]["meta_trace"]
            for r in rs
            if r.get("controller")
            and r["controller"].get("meta_trace") is not None
            and (r["controller"].get("rules") is not None)
        ]
        if meta:
            flat = [m for t in meta for m in t]
            e["meta_revision"] = {
                "runs_with_meta": len(meta),
                "runs_with_a_revision": sum(1 for t in meta if t),
                "revisions": len(flat),
                "exhausted_rules": sum(1 for m in flat if m["revision"] == "exhausted"),
                "parameter_revisions": sum(1 for m in flat if m["revision"] == "parameter"),
                "final_rules": [r["controller"]["rules"] for r in rs if r["controller"].get("rules")][:3],
                "note": "A revision is a change of the controller's rule parameters; whether later changes "
                "were better is a separate comparison (see the contrasts), not assumed.",
            }
        he = [r["history_reentry"] for r in rs if r.get("history_reentry")]
        if he:
            n = sum(h["reinsertions"] for h in he)
            e["history_reentry"] = {
                "enabled_runs": sum(1 for h in he if h["enabled"]),
                "reinsertions": n,
                "with_downstream_event": sum(h["with_downstream_event"] for h in he),
                "downstream_share": (sum(h["with_downstream_event"] for h in he) / n) if n else None,
            }
        sd = [r["shape_detection"] for r in rs if r.get("shape_detection")]
        if sd:
            e["shape_detection"] = {
                "runs": len(sd),
                "interpretation": None,
                "detector_limits": sd[0]["detector_limits"],
                "separation": "transition record (engine deltas) / detector output / interpretation (none produced)",
            }
        e["proposals"] = sorted(
            {p["name"] + " [" + p["status"] + "]" for r in rs for p in ((r.get("controller") or {}).get("proposals") or [])}
        )
        out[a] = e
    return out
