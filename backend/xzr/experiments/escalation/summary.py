"""Aggregate the resolution-escalation result files into one summary (the source of the docs tables and of the
research views): per-structure configuration map, factor dependence, resolution floor, noise control,
scale penetration chains, and the studies (clusters, disconnection, topology triggers, adaptivity, compression).

    python -m xzr.experiments.escalation.summary     # writes results/resolution/summary.json
"""

from __future__ import annotations

import json

import numpy as np

from ...reasonlab.structures import VARIANT_NAMES
from .harness import RESULTS
from .stats import ALPHA, ALPHA_PER_RESOLUTION, FACTOR_LABEL, PRACTICAL, RESOLUTIONS, SESOI, factor_dependence

COARSE = ("macro", "global")
DESCRIPTIONS = {
    "A": "no reasoning layer (vs reasoning with the reference structure)",
    "B": "vocabulary-bearing representation of the same structure",
    "D": "one-status support graph",
    "E": "eligibility tracking disabled (backed only)",
    "F": "least instead of greatest fixpoint",
    "G": "conflict defeats persist across evaluations",
    "H": "no dependency records",
    "I": "local-only records (cross-cluster requirements dropped)",
    "J": "records persistent (immune to decay, fragmentation, loss)",
    "K": "mixed rules per cluster",
    "C~": "noise control: the reference under another random stream",
}


def _load(name: str) -> dict | None:
    p = RESULTS / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


REQUIRED = ("experiment", "code", "condition", "topology", "n", "horizon", "engine_seeds", "structure", "comparison",
            "memory", "coupling", "mutation", "address", "status")
# the matrix was launched before per-condition provenance was recorded; its code state is recorded here (runs
# started 2026-09-30 11:25 from HEAD 2634e69 plus the uncommitted phase code; later edits were verified
# behaviour-neutral with fixed guard fingerprints before any further condition ran)
MATRIX_CODE = {"git_head": "2634e697e9f743536a2efffb13a4a2938b94b0c4", "dirty": True,
               "note": "launched 2026-09-30 11:25; subsequent edits verified behaviour-neutral (guard fingerprints)"}


def _row(cid: str, cond: dict, key: str, v: dict, experiment: str = "matrix", prov: dict | None = None) -> dict:
    cl = v["classification"]
    res = v["resolutions"]
    from .runner import SEED0
    seeds = (prov or {}).get("engine_seeds") or list(range(SEED0, SEED0 + int(v["seeds"])))
    largest = None
    for r in reversed(RESOLUTIONS):  # coarsest detected resolution first
        if res[r]["detected"] and res[r].get("largest"):
            largest = {"resolution": r, **res[r]["largest"]}
            break
    return {
        "experiment": experiment, "code": prov or MATRIX_CODE, "engine_seeds": seeds,
        "memory": cond.get("memory"), "mutation": cond.get("mutation"), "address": cond.get("address"),
        "return": cond.get("return"), "variant_name": VARIANT_NAMES.get(key, key),
        "mde": {r: res[r].get("median_mde_rel") for r in RESOLUTIONS},
        "effect_median_abs": {r: res[r].get("effect_median_abs_rel") for r in RESOLUTIONS},
        "global_effects": res["global"].get("global_effects"),
        "condition": cid, "factor": cond.get("factor", "reference"), "level": cond.get("level", cid),
        "n": cond["n"], "horizon": cond["horizon"], "seeds": v["seeds"], "topology": cond["topology"],
        "structure": cond["structure"], "size": cond["size"], "coupling": cond["coupling"],
        "primary": cl["primary"], "labels": cl["labels"], "status": cl["status"],
        "visible_from": cl.get("visible_from"), "visible_up_to": cl.get("visible_up_to"),
        "hidden_kind": cl.get("hidden_kind"),
        "exact_identical_share": v["exact_identical_share"],
        "intervention_checks_differing": v["intervention_checks_differing"],
        "ci_half": {r: res[r]["median_ci_half_rel"] for r in RESOLUTIONS},
        "pattern": {r: res[r]["pattern"] for r in RESOLUTIONS},
        "onset_segment": {r: res[r]["onset_segment"] for r in RESOLUTIONS},
        "segments_detected": {r: res[r]["segments_detected"] for r in RESOLUTIONS},
        "p": {r: [res[r]["p_segment"], res[r]["p_aggregate"]] for r in RESOLUTIONS},
        "largest": largest,
        "divergence_end": {r: v["divergence"][r]["ratio"][-1] for r in RESOLUTIONS},
        "chain": {"level": None if key == "A" else v.get("first_level_difference_median"),  # A has no levels
                  "intervention": v.get("first_intervention_difference_median"),
                  "world": v.get("first_step_median"), "target": v.get("first_step_target_median"),
                  "macro_exact": v.get("macro_onset_median")},
        "collapsed_share": v.get("collapsed_share"), "reasoning_share": v.get("reasoning_share"),
    }


def matrix_rows(doc: dict, experiment: str = "matrix") -> list[dict]:
    rows = []
    for cid, a in doc["conditions"].items():
        cond = a["condition"]
        for key, v in a["comparisons"].items():
            rows.append({"comparison": key, **_row(cid, cond, key, v, experiment, a.get("provenance"))})
    return rows


def validate(rows: list[dict], expected_seeds: dict[str, int] | None = None) -> tuple[list[dict], list[dict]]:
    """Rows with complete provenance and a complete seed set; the rest are quarantined (with the reason)."""
    ok, bad = [], []
    seen = set()
    for r in rows:
        missing = [k for k in REQUIRED if r.get(k) in (None, "", [])]
        key = (r["experiment"], r["condition"], r["comparison"])
        if key in seen:
            missing.append("duplicate")
        seen.add(key)
        if len(r["engine_seeds"]) != r["seeds"]:
            missing.append("incomplete seed set")
        if missing:
            bad.append({"experiment": r.get("experiment"), "condition": r.get("condition"),
                        "comparison": r.get("comparison"), "reason": missing})
        else:
            ok.append(r)
    return ok, bad


def _visible(r: dict) -> bool:
    return r["primary"] == "NON-REDUNDANT"


def _ref_values() -> dict:
    from .harness import REFERENCE
    return {"topology": REFERENCE["topology"], "memory": REFERENCE["memory"], "coupling": REFERENCE["coupling"],
            "mutation": REFERENCE["mutation"], "address": REFERENCE["address"], "structure": REFERENCE["structure"],
            "size": REFERENCE["size"], "horizon": REFERENCE["horizon"], "n": REFERENCE["n"]}


REF_VALUE = _ref_values()


def reversibility(rows: list[dict]) -> list[dict]:
    """Variants reverted to the reference rule at mid-run (X@rev): is a systematic difference still present in the
    segments after the revert (irreversible divergence), compared with the unreverted variant?"""
    out = []
    for r in rows:
        if not r["comparison"].endswith("@rev"):
            continue
        base = r["comparison"][:-4]
        orig = next((x for x in rows if x["condition"] == r["condition"] and x["comparison"] == base), None)
        after = {res: any(r["segments_detected"][res][4:]) for res in r["segments_detected"]}
        if any(after.values()):
            verdict = "irreversible: systematic difference persists after the revert"
        elif r["primary"] == "REDUNDANT":
            verdict = "no divergence (bit-identical)"
        elif r["primary"] == "HIDDEN AT COARSE RESOLUTION":
            verdict = "exact divergence persists (never re-converges); no systematic difference after the revert"
        else:
            verdict = "not established: exact divergence persists; coarse equivalence after the revert not resolved"
        out.append({"condition": r["condition"], "variant": base, "reverted_primary": r["primary"],
                    "unreverted_primary": orig["primary"] if orig else None,
                    "systematic_after_revert": after, "irreversible": verdict,
                    "exact_identical_after_revert": r["exact_identical_share"]})
    return out


def structure_map(rows: list[dict]) -> dict:
    out = {}
    for key in sorted({r["comparison"] for r in rows if not r["comparison"].endswith("@rev")}):
        rs = [r for r in rows if r["comparison"] == key]
        vis = [r for r in rs if _visible(r)]
        coarse_vis = [r for r in vis if any(r["status"][x] == "DETECTED" for x in COARSE)]
        local_only = [r for r in rs if not any(r["status"][x] == "DETECTED" for x in COARSE)
                      and any(r["status"][x] == "DETECTED" for x in ("node", "local", "meso"))]
        hidden = [r for r in rs if "HIDDEN AT COARSE RESOLUTION" in r["labels"]]
        red = [r for r in rs if r["primary"] == "REDUNDANT"]
        unres = [r for r in rs if r["primary"] == "UNRESOLVED"]
        deps = {}
        for factor in sorted({r["factor"] for r in rs} - {"reference"}):
            levels = {str(r["level"]): {"labels": r["labels"]} for r in rs if r["factor"] == factor}
            ref = [r for r in rs if r["factor"] == "reference"]
            if ref and factor in REF_VALUE:  # the reference condition is this factor's reference level
                levels[f"{REF_VALUE[factor]} (reference)"] = {"labels": ref[0]["labels"]}
            deps[factor] = factor_dependence(levels)
        labels = set()
        if rs and len(red) == len(rs):
            labels.add("REDUNDANT")
        if vis:
            labels.add("NON-REDUNDANT")
        if hidden:
            labels.add("HIDDEN AT COARSE RESOLUTION")
        if vis and all(r["pattern"].get(x) in ("transient", "none") for r in vis for x in COARSE):
            labels.add("TRANSIENT")
        for f, d in deps.items():
            if d["dependent"]:
                base = f.split("×")[-1]
                labels.add(FACTOR_LABEL.get(base, "REGIME-DEPENDENT"))
        late = [r for r in vis if r["horizon"] >= 4000 and min(
            [s for x, s in r["onset_segment"].items() if x in ("meso", *COARSE) and s is not None], default=0) >= 2]
        if late:
            labels.add("TIME-WINDOW-DEPENDENT")
        if unres and not vis and not hidden and not (rs and len(red) == len(rs)):
            labels.add("UNRESOLVED")
        out[key] = {
            "name": VARIANT_NAMES.get(key, "noise control" if key == "C~" else key),
            "description": DESCRIPTIONS.get(key, key),
            "conditions": len(rs), "visible": [r["condition"] for r in vis],
            "visible_coarse": [r["condition"] for r in coarse_vis],
            "locally_only": [r["condition"] for r in local_only], "hidden": [r["condition"] for r in hidden],
            "redundant": [r["condition"] for r in red], "unresolved": [r["condition"] for r in unres],
            "labels": sorted(labels), "factor_dependence": deps,
            "globally_non_redundant": bool(coarse_vis), "locally_non_redundant_only": bool(local_only) and not coarse_vis,
            "exact_identical_everywhere": bool(rs) and all(r["exact_identical_share"] >= 1 for r in rs),
            "effects": [{"condition": r["condition"], **(r["largest"] or {})} for r in vis][:40],
        }
    return out


def resolution_floor(rows: list[dict]) -> dict:
    """The noise floor: median 90 % CI half-width (relative) of time-aggregated summaries, for the noise-control
    comparison, per resolution and per (n, horizon, seeds)."""
    out: dict = {}
    for r in rows:
        if r["comparison"] != "C~":
            continue
        k = f"n={r['n']} horizon={r['horizon']} seeds={r['seeds']}"
        out.setdefault(k, {x: [] for x in RESOLUTIONS})
        for x in RESOLUTIONS:
            out[k][x].append(r["ci_half"][x])
    return {k: {x: round(float(np.median(v[x])), 4) for x in RESOLUTIONS} | {"conditions": len(v["global"])}
            for k, v in out.items()}


def noise_control(rows: list[dict]) -> dict:
    nc = [r for r in rows if r["comparison"] == "C~"]
    fp = [r["condition"] for r in nc if any(r["status"][x] == "DETECTED" for x in RESOLUTIONS)]
    return {"comparisons": len(nc), "false_positive_conditions": fp, "false_positive_rate": round(len(fp) / max(len(nc), 1), 4),
            "nominal_family_alpha": ALPHA}


def penetration(rows: list[dict], doc: dict) -> dict:
    """Scale penetration per visible comparison: the chain from reasoning-level difference to world divergence,
    the resolutions crossed, attenuation / amplification (end-of-run divergence ratio, coarser ÷ finer) and
    whether the difference returns into local conditions (local divergence rising after the macro onset)."""
    out = []
    for r in rows:
        if r["comparison"] in ("C~",) or r["comparison"].endswith("@rev") or r["exact_identical_share"] >= 1:
            continue
        a = doc["conditions"][r["condition"]]["comparisons"][r["comparison"]]
        div = a["divergence"]
        det = [x for x in RESOLUTIONS if r["status"][x] == "DETECTED"]
        seg_len = r["horizon"] / 8
        onsets = {x: (None if r["onset_segment"][x] is None else int(r["onset_segment"][x] * seg_len)) for x in RESOLUTIONS}
        ratio_end = {x: div[x]["ratio"][-1] for x in RESOLUTIONS}
        amp = {f"{b}/{a_}": round(ratio_end[b] / (ratio_end[a_] + 1e-12), 3)
               for a_, b in zip(RESOLUTIONS[:-1], RESOLUTIONS[1:], strict=True)}
        loc = np.asarray(div["local"]["ratio"], dtype=float)
        mac_onset = r["chain"]["macro_exact"]
        w = len(loc)
        k = int(min(w - 1, (mac_onset or 0) / r["horizon"] * w)) if mac_onset else 0
        ret = float(loc[-max(1, w // 4):].mean() - loc[k]) if w else 0.0
        out.append({"comparison": r["comparison"], "condition": r["condition"], "chain_steps": r["chain"],
                    "detected_resolutions": det, "depth": det[-1] if det else "exact",
                    "scales_crossed": len(det), "systematic_onset_step": onsets,
                    "divergence_ratio_end": ratio_end, "amplification": amp,
                    "divergence_series": {x: div[x]["ratio"] for x in RESOLUTIONS},
                    "return_into_local": round(ret, 4), "persistent": all(r["pattern"][x] == "persistent" for x in det)
                    if det else False})
    return {"rows": out}


def structure_descriptors() -> dict:
    from ...reasonlab.structures import STRUCTURES, descriptors, generate
    return {k: {str(z): descriptors(generate(k, z, 3), edits=10) for z in (9, 32, 128)} for k in STRUCTURES}


def _detected_somewhere(r: dict) -> bool:
    return any(r["status"][x] == "DETECTED" for x in RESOLUTIONS)


def _equivalent(r: dict) -> bool:
    """No systematic difference anywhere and macro + global equivalent (or bit-identical)."""
    return r["primary"] == "REDUNDANT" or (not _detected_somewhere(r) and r["status"]["macro"] == "EQUIVALENT"
                                           and r["status"]["global"] == "EQUIVALENT")


def disconnection_verdict(rows: list[dict]) -> dict:
    """Mechanical status of disconnection from the targeted study (downstream effects only).

    removal detectable    'off' shows a systematic downstream difference at some resolution in some structure
    REDUCIBLE             removal detectable, and some replacement is equivalent in every structure
    NON-REDUNDANT         removal detectable in every structure, no replacement equivalent everywhere
    REGIME-DEPENDENT      removal detectable in some structures (equivalent within the margin in others), no replacement
                          equivalent everywhere
    UNRESOLVED            removal not demonstrably detectable anywhere"""
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["comparison"], []).append(r)
    off = by.get("off", [])
    det = [r["condition"] for r in off if _detected_somewhere(r)]
    absent = [r["condition"] for r in off if _equivalent(r)]
    repl = {k: {"equivalent_everywhere": all(_equivalent(r) for r in v),
                "identical_everywhere": all(r["exact_identical_share"] >= 1 for r in v),
                "detected_in": [r["condition"] for r in v if _detected_somewhere(r)]}
            for k, v in by.items() if k not in ("off", "C~")}
    equiv = [k for k, v in repl.items() if v["equivalent_everywhere"]]
    if not det:
        status = "UNRESOLVED"
    elif equiv:
        status = "REDUCIBLE"
    elif len(det) == len(off):
        status = "NON-REDUNDANT"
    else:
        status = "REGIME-DEPENDENT"
    return {"status": status, "removal_detected_in": det, "removal_equivalent_in": absent,
            "removal_unresolved_in": [r["condition"] for r in off if r["condition"] not in det + absent],
            "replacements": repl, "equivalent_replacements": equiv}


def trigger_verdict(rows: list[dict]) -> dict:
    """Mechanical status of the cut / reconfiguration trigger distinction.

    descriptive only          a merged form (unified or merged) is bit-identical in every regime
    reducible                 a merged form is equivalent in every regime, and removing a trigger is detectable
    structurally necessary    both trigger removals detectable in every regime and no merged form equivalent in any
    conditionally necessary   otherwise, when a removal or a merged form is detectable in some regimes
    unresolved                nothing detectable and equivalence not established"""
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["comparison"], []).append(r)
    merged = {k: by.get(k, []) for k in ("unified", "merged")}
    removal = {k: by.get(k, []) for k in ("cut_only", "reconfigure_only")}
    ident = [k for k, v in merged.items() if v and all(r["exact_identical_share"] >= 1 for r in v)]
    equiv = [k for k, v in merged.items() if v and all(_equivalent(r) for r in v)]
    rem_det = {k: [r["condition"] for r in v if _detected_somewhere(r)] for k, v in removal.items()}
    merged_det = {k: [r["condition"] for r in v if _detected_somewhere(r)] for k, v in merged.items()}
    regimes = len(removal["cut_only"])
    if ident:
        status = "descriptive only"
    elif equiv and any(rem_det.values()):
        status = "reducible"
    elif all(len(v) == regimes for v in rem_det.values()) and all(
            not any(_equivalent(r) for r in v) for v in merged.values()):
        status = "structurally necessary"
    elif any(rem_det.values()) or any(merged_det.values()):
        status = "conditionally necessary"
    else:
        status = "unresolved"
    gen = by.get("generic_conditions", [])
    # A: is the underlying connection-mutation operation shared? (both triggers executed by one generic operation,
    #    conditions unchanged)
    if gen and all(r["exact_identical_share"] >= 1 for r in gen):
        op_shared = "shared (bit-identical in every regime)"
    elif gen and all(_equivalent(r) for r in gen):
        op_shared = "shared (equivalent in every regime; not bit-identical)"
    elif gen and any(_detected_somewhere(r) for r in gen):
        op_shared = "not shared: generic execution differs in " + ", ".join(
            r["condition"] for r in gen if _detected_somewhere(r))
    else:
        op_shared = "unresolved (no systematic difference; equivalence not established)"
    # B: are the trigger conditions operationally distinct? (merging them changes behaviour)
    if any(merged_det.values()):
        cond_distinct = "distinct: merging the conditions changes behaviour in " + "; ".join(
            f"{k}: {', '.join(v)}" for k, v in merged_det.items() if v)
    elif equiv:
        cond_distinct = "not distinct: a merged condition is equivalent in every regime (" + ", ".join(equiv) + ")"
    else:
        cond_distinct = "unresolved (merged forms show no systematic difference, equivalence not established)"
    return {"status": status, "operation_shared": op_shared, "conditions_distinct": cond_distinct,
            "removal_detected_in": rem_det, "merged_detected_in": merged_det,
            "merged_equivalent_everywhere": equiv, "merged_identical_everywhere": ident,
            "generic_conditions_identical_everywhere": bool(gen) and all(r["exact_identical_share"] >= 1 for r in gen)}


def adaptivity_verdict(ad: dict) -> dict:
    """Rules. Schedule variation across world seeds is split into: gating only (S: no triggers), scripted (R:
    replayed schedule — zero by construction) and world-responsive revision (C − S). Revision is *genuinely
    world-responsive* when C varies more across seeds than S and firings are followed by a return of the triggering
    metric more often than random checks. Precision / long-run effects are paired comparisons across seeds
    (|t| ≥ 3.11 ≈ two-sided 0.01 with 11 df); the multi-resolution world tests classify C against each control."""
    out = {}
    for cid, a in ad.items():
        ada = a["adaptivity"]
        resp = a["response"]
        world_part = round(ada["C"] - ada["S"], 4)
        responsive = world_part > 0.02 and resp.get("paired_t") is not None and resp["paired_t"] >= 3.11
        pp = a["in_band_paired"]
        prec = {k: ("better" if v["t"] >= 3.11 else "worse" if v["t"] <= -3.11 else "no significant difference")
                for k, v in pp.items()}
        comps = {k: r["primary"] for k, r in a["comparisons"].items()}
        out[cid] = {"gating_only_adaptivity": ada["S"], "scripted_adaptivity": ada["R"],
                    "closed_loop_adaptivity": ada["C"], "world_responsive_part": world_part,
                    "firings_followed_by_return": resp["responded"], "random_checks_followed_by_return": resp["control"],
                    "response_paired_t": resp.get("paired_t"),
                    "genuinely_world_responsive": bool(responsive), "control_precision_vs": prec,
                    "world_effect_vs": comps}
    return out


def compression_verdict(comp: dict) -> dict:
    """Rules per horizon and pair: a distinction is preserved when the systematic raw/compressed detections agree,
    the compressed pair÷noise distance ratio is within 25 % of the raw one, and the divergence onset is not lost;
    hidden local differences are retained when the local-difference correlation is ≥ 0.5."""
    out = {}
    for h, r in comp["horizons"].items():
        rows = {}
        for k, v in r["pairs"].items():
            rr, cr = v["raw_distance_ratio"]["mean"], v["compressed_distance_ratio"]["mean"]
            agree = v["systematic_raw"]["detected"] == v["systematic_compressed"]["detected"]
            close = rr is not None and cr is not None and abs(cr - rr) <= 0.25 * max(rr, 1e-9)
            rows[k] = {"distinction_preserved": bool(agree and close and v["onset_missing_compressed"] == 0),
                       "systematic_agree": agree, "distance_ratio_close": bool(close),
                       "onset_lost_seeds": v["onset_missing_compressed"],
                       "hidden_local_retained": bool((v["local_difference_correlation"]["mean"] or 0) >= 0.5)}
        out[h] = {"pairs": rows, "compression_ratio_C": r["per_variant"]["C"]["compression_ratio"]["mean"],
                  "replay_r2_C": r["per_variant"]["C"]["replay_r2"]["mean"]}
    return out


def case_lists(struct: dict, rows: list[dict]) -> dict:
    def with_label(label):
        return sorted(k for k, v in struct.items() if label in v["labels"])
    hidden = [{"comparison": r["comparison"], "condition": r["condition"], "kind": r.get("hidden_kind"),
               "finest_visible": r.get("visible_from")} for r in rows
              if "HIDDEN AT COARSE RESOLUTION" in r["labels"] and r["comparison"] != "C~"
              and not r["comparison"].endswith("@rev")]
    return {"hidden_cases": hidden, "topology_dependent": with_label("TOPOLOGY-DEPENDENT"),
            "time_window_dependent": with_label("TIME-WINDOW-DEPENDENT"),
            "memory_dependent": with_label("MEMORY-DEPENDENT"), "scale_dependent": with_label("SCALE-DEPENDENT"),
            "regime_dependent": with_label("REGIME-DEPENDENT"), "transient": with_label("TRANSIENT")}


def study(name: str) -> dict | None:
    doc = _load(name)
    if doc is None:
        return None
    rows, bad = validate(matrix_rows(doc, name))
    return {"rows": rows, "quarantined": bad, "noise_control": noise_control(rows), "meta": doc.get("meta", {})}


def build() -> dict:
    m = _load("matrix")
    summary: dict = {"rules": {"alpha_family": ALPHA, "alpha_per_resolution_family": ALPHA_PER_RESOLUTION,
                               "practical": PRACTICAL, "sesoi": SESOI, "resolutions": list(RESOLUTIONS)}}
    if m is not None:
        rows, bad = validate(matrix_rows(m))
        summary["quarantined"] = bad
        summary["matrix"] = {"rows": rows, "meta": m.get("meta", {}), "calibration": m.get("calibration", {}),
                             "references": {cid: a["reference"] | {"condition": {k: a["condition"].get(k) for k in (
                                 "factor", "level", "n", "horizon", "topology", "memory", "coupling", "mutation",
                                 "return", "address", "structure", "size", "seeds")}}
                                            for cid, a in m["conditions"].items()}}
        summary["structures"] = structure_map([r for r in rows if r["comparison"] != "C~"] +
                                              [r for r in rows if r["comparison"] == "C~"])
        summary["floor"] = resolution_floor(rows)
        summary["noise_control"] = noise_control(rows)
        summary["penetration"] = penetration(rows, m)
        summary["reversibility"] = reversibility(rows)
    for name in ("clusters", "disconnection", "topology_triggers"):
        s = study(name)
        if s is not None:
            summary[name] = s
    if "disconnection" in summary:
        summary["disconnection"]["verdict"] = disconnection_verdict(summary["disconnection"]["rows"])
    if "topology_triggers" in summary:
        summary["topology_triggers"]["verdict"] = trigger_verdict(summary["topology_triggers"]["rows"])
    if "clusters" in summary:
        summary["clusters"]["structures"] = structure_map([r for r in summary["clusters"]["rows"]
                                                           if r["comparison"] != "C~"])
    if "structures" in summary:
        summary["cases"] = case_lists(summary["structures"], summary["matrix"]["rows"])
    for name in ("adaptivity", "compression"):
        d = _load(name)
        if d is not None:
            summary[name] = d if name == "compression" else {
                cid: {k: a[k] for k in ("adaptivity", "in_band", "in_band_paired", "response", "fired_kinds")} |
                     {"comparisons": {key: {"comparison": key, **_row(cid, a["condition"], key, v, "adaptivity",
                                                                       a.get("provenance"))}
                                      for key, v in a["comparisons"].items()}}
                for cid, a in d["conditions"].items()}
    if "adaptivity" in summary:
        summary["adaptivity_verdict"] = adaptivity_verdict(summary["adaptivity"])
    if "compression" in summary:
        summary["compression_verdict"] = compression_verdict(summary["compression"])
    summary["descriptors"] = structure_descriptors()
    from .answers import answers
    summary["answers"] = answers(summary)
    return summary


def main() -> None:
    s = build()
    (RESULTS / "summary.json").write_text(json.dumps(s))
    print("wrote", RESULTS / "summary.json")


if __name__ == "__main__":
    main()
