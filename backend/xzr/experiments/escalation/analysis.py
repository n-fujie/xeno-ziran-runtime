"""Across-seed analysis of one condition: per comparison (variant vs reference C), per resolution.

For every resolution the per-seed paired differences of segment means (segments × features × units) are tested
with the family-wise sign-flip max-T test (stats.maxt_test). The noise replicate C~ (same structure, other random
stream) is analysed identically and serves as the false-positive control. Divergence ratios compare the window
distance of a pair with the distance between C and its noise replicate (0 = identical, ~1 = as different as an
independent replicate).
"""

from __future__ import annotations

import numpy as np

from ...shapes.multiscale import FEATURES, GLOBAL_KEYS
from .stats import RESOLUTIONS, SESOI, classify_condition, maxt_test, time_pattern

# own-output exclusions: summaries that a comparison changes by definition (none for reasoning variants; the
# disconnection / topology-trigger studies pass their own)
OWN_GLOBAL: dict[str, set[str]] = {}


def _stack(jobs: list[dict], key: str, res: str) -> np.ndarray:
    if res == "global":
        return np.stack([j["runs"][key]["gseg"] for j in jobs])  # (S, K, G)
    return np.stack([j["runs"][key]["seg"][res] for j in jobs])  # (S, K, F, U)


def _family(d: np.ndarray, base: np.ndarray, shape: tuple) -> dict:
    valid = base > 1e-9
    r = maxt_test(d[:, valid], base[valid])
    m = int(np.prod(shape))

    def full(v, fill):
        out = np.full(m, fill, dtype=float)
        out[np.flatnonzero(valid)] = v
        return out.reshape(shape)

    return {"r": r, "det": full(r["detected"], 0).astype(bool), "rel": full(r["rel"], 0.0),
            "mde": full(r["mde"], np.inf), "half": full(r["ci_half"], np.inf),
            "determ": full(r["deterministic"], 0).astype(bool), "n_tests": int(valid.sum())}


def _test(jobs: list[dict], key: str, res: str, exclude: frozenset[str] | set[str] = frozenset(),
          first_seg: int = 0) -> dict:
    x, c = _stack(jobs, key, res), _stack(jobs, "C", res)
    allnames = list(GLOBAL_KEYS) if res == "global" else list(FEATURES)
    keep = [i for i, k in enumerate(allnames) if k not in exclude]  # own outputs of the comparison are excluded
    x, c = x[:, :, keep], c[:, :, keep]
    names = [allnames[i] for i in keep]
    s = x.shape[0]
    # family 1: time segments (K × F × U)
    seg = _family((x - c).reshape(s, -1), np.abs(c).mean(0).reshape(-1), x.shape[1:])
    # family 2: time average over the segments after reasoning is allowed (F × U)
    xa, ca = x[:, first_seg:].mean(1), c[:, first_seg:].mean(1)
    agg = _family((xa - ca).reshape(s, -1), np.abs(ca).mean(0).reshape(-1), xa.shape[1:])
    det = seg["det"]
    k = det.shape[0]
    seg_det = [bool(det[i].any()) for i in range(k)]
    agg_det = bool(agg["det"].any())
    half = agg["half"][np.isfinite(agg["half"])]
    med_half = float(np.median(half)) if half.size else float("inf")
    mde = agg["mde"][np.isfinite(agg["mde"])]
    detected = bool(det.any()) or agg_det
    pattern = time_pattern(seg_det)
    if pattern == "none" and agg_det:
        pattern = "aggregate-only"
    out = {"detected": detected, "segment_detected": bool(det.any()), "aggregate_detected": agg_det,
           "p_segment": seg["r"]["p"], "p_aggregate": agg["r"]["p"], "crit_segment": round(seg["r"]["crit"], 3),
           "crit_aggregate": round(agg["r"]["crit"], 3),
           "segments_detected": seg_det, "pattern": pattern,
           "onset_segment": seg_det.index(True) if any(seg_det) else None,
           "n_detected": int(det.sum()) + int(agg["det"].sum()),
           "n_deterministic": int(seg["determ"].sum()) + int(agg["determ"].sum()),
           "n_tests": seg["n_tests"] + agg["n_tests"],
           "median_ci_half_rel": round(med_half, 4), "median_mde_rel": round(float(np.median(mde)), 4) if mde.size else None,
           "equivalent": (not detected) and med_half <= SESOI,
           "min_p_attainable": seg["r"]["min_p_attainable"]}
    # effect sizes for every result, null or not (time-aggregated family, relative to the unit's baseline)
    arel = np.abs(agg["rel"][np.isfinite(agg["half"])])
    out["effect_median_abs_rel"] = round(float(np.median(arel)), 5) if arel.size else None
    out["effect_max_abs_rel"] = round(float(arel.max()), 5) if arel.size else None
    if res == "global":
        rel, hf = agg["rel"].reshape(len(names), -1)[:, 0], agg["half"].reshape(len(names), -1)[:, 0]
        out["global_effects"] = {names[f]: {"relative": round(float(rel[f]), 5), "ci_half": round(float(hf[f]), 5)}
                                 for f in range(len(names)) if np.isfinite(hf[f])}
    # the largest detected effect (aggregate family first)
    for fam, arr in (("aggregate", agg), ("segment", seg)):
        if arr["det"].any():
            rel = np.where(arr["det"], np.abs(arr["rel"]), 0)
            idx = np.unravel_index(int(np.argmax(rel)), rel.shape)
            f_axis = 0 if fam == "aggregate" else 1
            item = {"family": fam, "feature": names[idx[f_axis]], "relative": round(float(arr["rel"][idx]), 4)}
            if fam == "segment":
                item["segment"] = int(idx[0])
            if res != "global":
                item["unit"] = int(idx[-1])
            out["largest"] = item
            dets = arr["det"] if fam == "aggregate" else arr["det"].any(0)
            out["detected_units_by_feature"] = {names[f]: int(dets[f].sum()) for f in range(dets.shape[0])}
            if res != "global":
                out["detected_units"] = sorted(set(np.flatnonzero(dets.any(0)).tolist()))[:512]
            break
    return out


def _ratio(jobs: list[dict], key: str) -> dict:
    """Median over seeds of dist(pair) / dist(C, C~) per window, per resolution (activity feature / global
    activity), plus the pair's raw window distance."""
    out = {}
    for r in RESOLUTIONS:
        a = np.stack([j["runs"][key]["cmp"]["dist"][r] for j in jobs])  # (S, W, F)
        n = np.stack([j["runs"]["C~"]["cmp"]["dist"][r] for j in jobs])
        fa = a[:, :, 0]
        fn = n[:, :, 0]
        out[r] = {"distance": np.round(np.median(fa, 0), 4).tolist(),
                  "ratio": np.round(np.median(fa / (fn + 1e-12), 0), 4).tolist()}
    return out


def analyse(cond: dict, jobs: list[dict], exclude: frozenset[str] | set[str] = frozenset()) -> dict:
    keys = [k for k in jobs[0]["runs"] if k != "C"]
    comps = {}
    for key in keys:
        cm = [j["runs"][key]["cmp"] for j in jobs]
        first = 0 if cond.get("flag_variants") else int(np.ceil(cond["reasoning_from"] / (cond["horizon"] / 8)))
        res = {r: _test(jobs, key, r, exclude, first) for r in RESOLUTIONS}
        ident = float(np.mean([x["identical"] for x in cm]))
        row = {
            "exact_identical_share": ident,
            "first_step_median": _med([x["first_step"] for x in cm]),
            "first_step_target_median": _med([x["first_step_target"] for x in cm]),
            "macro_onset_median": _med([min([o for o in x["macro_onsets"] if o is not None], default=None) for x in cm]),
            "intervention_checks_differing": round(float(np.mean([x["intervention_checks_differing"] for x in cm])), 4),
            "first_intervention_difference_median": _med([x["first_intervention_difference"] for x in cm]),
            "first_level_difference_median": _med([x["first_level_difference"] for x in cm]),
            "resolutions": res,
            "divergence": _ratio(jobs, key),
            "revisions_mean": round(float(np.mean([j["runs"][key]["revisions"] for j in jobs])), 2),
            "reasoning_share": round(float(np.mean([j["runs"][key]["phases"].count("reasoning") /
                                                    max(len(j["runs"][key]["phases"]), 1) for j in jobs])), 4),
            "collapsed_share": round(float(np.mean([j["runs"][key]["phases"].count("collapsed") /
                                                    max(len(j["runs"][key]["phases"]), 1) for j in jobs])), 4),
            "coupling": _mean_dicts([j["runs"][key]["coupling"] for j in jobs]),
            "seeds": len(jobs), "horizon": cond["horizon"], "segments": len(res["global"]["segments_detected"]),
        }
        row["classification"] = classify_condition(row)
        comps[key] = row
    ref = {"reasoning_share": round(float(np.mean([j["runs"]["C"]["phases"].count("reasoning") /
                                                   max(len(j["runs"]["C"]["phases"]), 1) for j in jobs])), 4),
           "collapsed_share": round(float(np.mean([j["runs"]["C"]["phases"].count("collapsed") /
                                                   max(len(j["runs"]["C"]["phases"]), 1) for j in jobs])), 4),
           "revisions_mean": round(float(np.mean([j["runs"]["C"]["revisions"] for j in jobs])), 2),
           "fired": _mean_dicts([j["runs"]["C"]["fired_kinds"] for j in jobs]),
           "coupling": _mean_dicts([j["runs"]["C"]["coupling"] for j in jobs]),
           "ms_per_step": round(float(np.mean([j["runs"]["C"]["ms_per_step"] for j in jobs])), 3),
           "loop_ms_per_step": round(float(np.mean([j["runs"]["C"]["loop_ms_per_step"] for j in jobs])), 3),
           "info": jobs[0]["runs"]["C"]["info"],
           "schedule_adaptivity": _adaptivity([j["runs"]["C"]["effects"] for j in jobs])}
    return {"condition": _cond_json(cond), "reference": ref, "comparisons": comps}


def _adaptivity(schedules: list[list[str]]) -> float:
    vals = []
    for i in range(len(schedules)):
        for j in range(i + 1, len(schedules)):
            a, b = schedules[i], schedules[j]
            n = min(len(a), len(b))
            vals.append(np.mean([a[k] != b[k] for k in range(n)]) if n else 0.0)
    return round(float(np.mean(vals)), 4) if vals else 0.0


def _med(xs: list) -> float | None:
    v = [x for x in xs if x is not None]
    return float(np.median(v)) if v else None


def _mean_dicts(ds: list[dict]) -> dict:
    keys = sorted({k for d in ds for k in d})
    return {k: round(float(np.mean([d.get(k, 0.0) for d in ds])), 5) for k in keys}


def _cond_json(c: dict) -> dict:
    out = {}
    for k, v in c.items():
        out[k] = list(v) if isinstance(v, tuple) else v
    return out
