"""Structured evidence for the phase's seventeen questions, derived mechanically from the summary. Each answer lists
evidence rows with experiment ID, effect size, noise comparison, topology, configuration count, horizon, seed count,
uncertainty and classification. No number here is typed by hand; the prose in the docs interprets these records."""

from __future__ import annotations

STRUCTURAL = ("D", "E", "F", "G", "H", "I", "J", "K")
COARSE = ("macro", "global")


def _noise(rows: list[dict]) -> dict[str, dict]:
    return {r["condition"]: r for r in rows if r["comparison"] == "C~"}


def ev(r: dict, noise: dict[str, dict], experiment: str = "matrix") -> dict:
    n = noise.get(r["condition"])
    lg = r.get("largest")
    eff = ({"resolution": lg["resolution"], "feature": lg["feature"], "relative": lg["relative"]} if lg else
           {"median_abs_relative_global": (r.get("effect_median_abs") or {}).get("global"),
            "divergence_ratio_global": r["divergence_end"]["global"]})
    return {"experiment_id": f"{experiment}:{r['condition']}", "comparison": r["comparison"], "effect": eff,
            "noise_comparison": {"noise_ci_half": n["ci_half"] if n else None,
                                 "noise_detected": [x for x in ("node", "local", "meso", "macro", "global")
                                                    if n and n["status"][x] == "DETECTED"] if n else None},
            "topology": r["topology"], "configurations": r["n"], "horizon": r["horizon"], "seeds": r["seeds"],
            "uncertainty": {"ci_half": r["ci_half"], "mde": r.get("mde"), "p_segment_aggregate": r.get("p")},
            "classification": r["labels"], "status": r["status"],
            "exact_identical_share": r["exact_identical_share"], "structure": r["structure"], "size": r["size"],
            "memory": r.get("memory"), "coupling": r["coupling"], "mutation": r.get("mutation"),
            "address": r.get("address")}


def answers(s: dict) -> dict:
    out: dict = {}
    if "matrix" not in s:
        return out
    rows = s["matrix"]["rows"]
    noise = _noise(rows)
    st = s["structures"]

    def rows_of(keys, pred):
        return [ev(r, noise) for r in rows if r["comparison"] in keys and pred(r)]

    def coarse(r):
        return any(r["status"][x] == "DETECTED" for x in COARSE)

    glob = [k for k in STRUCTURAL + ("A",) if k in st and st[k]["globally_non_redundant"]]
    out["1"] = {"question": "Which reasoning structures are globally non-redundant?", "structures": glob,
                "evidence": rows_of(glob, coarse)}
    loc = [k for k in STRUCTURAL + ("A",) if k in st and st[k]["locally_non_redundant_only"]]
    out["2"] = {"question": "Which are only locally non-redundant?", "structures": loc,
                "evidence": rows_of(loc, lambda r: any(r["status"][x] == "DETECTED" for x in ("node", "local", "meso")))}
    hid = sorted({h["comparison"] for h in s["cases"]["hidden_cases"]})
    out["3"] = {"question": "Which are hidden at coarse resolution?", "structures": hid,
                "evidence": rows_of(hid, lambda r: "HIDDEN AT COARSE RESOLUTION" in r["labels"])}
    for q, key, factor in (("4", "topology_dependent", ("topology", "strong×topology")),
                           ("5", "time_window_dependent", ("horizon",)), ("6", "memory_dependent", ("memory",))):
        ks = [k for k in s["cases"][key] if k != "C~"]
        out[q] = {"question": {"4": "Which are topology-dependent?", "5": "Which are time-window-dependent?",
                               "6": "Which are memory-dependent?"}[q], "structures": ks,
                  "factor_dependence": {k: {f: st[k]["factor_dependence"].get(f) for f in factor} for k in ks},
                  "evidence": rows_of(ks, lambda r, factor=factor: r["factor"] in factor or r["factor"] == "reference")}
    red = [k for k in ("B", *STRUCTURAL) if k in st and st[k]["exact_identical_everywhere"]]
    out["7"] = {"question": "Which remain redundant across all tested configurations?", "structures": red,
                "evidence": rows_of(red, lambda r: True)}
    unres = [k for k in STRUCTURAL if k in st and not st[k]["visible"] and st[k]["unresolved"]]
    out["8"] = {"question": "Which remain unresolved?", "structures": unres,
                "counts": {k: {"unresolved": len(st[k]["unresolved"]), "hidden": len(st[k]["hidden"]),
                               "conditions": st[k]["conditions"]} for k in STRUCTURAL if k in st},
                "evidence": rows_of(unres, lambda r: r["primary"] == "UNRESOLVED")}
    out["9"] = {"question": "Under what exact configuration does reasoning become operationally non-redundant?",
                "reasoning_vs_none": rows_of(("A",), lambda r: r["primary"] == "NON-REDUNDANT"),
                "structure_differences": rows_of(STRUCTURAL, lambda r: r["primary"] == "NON-REDUNDANT")}
    refs = s["matrix"]["references"]

    def shares(v: dict) -> dict:
        c = v["condition"]
        checks = max(int(c["horizon"]) // 10, 1)
        pre = max(int(c.get("reasoning_from", 200)) // 10 - 1, 0) / checks
        rs, cs = v["reasoning_share"], v["collapsed_share"]
        return {"reasoning_share": rs, "collapsed_share": cs,
                "never_enabled_share": round(max(0.0, 1 - rs - cs - pre), 4)}
    coll = sorted(((cid, shares(v)) for cid, v in refs.items()), key=lambda x: x[1]["reasoning_share"])
    out["10"] = {"question": "Under what exact configuration does reasoning collapse?",
                 "rule": "reasoning inactive for most of the run: collapsed (enabled, then failed) or never enabled",
                 "collapsed_share_by_condition": [{"experiment_id": f"matrix:{cid}", **sh, **refs[cid]["condition"]}
                                                  for cid, sh in coll if sh["reasoning_share"] < 0.5]}
    if "adaptivity_verdict" in s:
        out["11"] = {"question": "Does world-responsive revision create genuine adaptivity?",
                     "verdict": s["adaptivity_verdict"],
                     "evidence": {cid: {k: ev(r, {}, "adaptivity") for k, r in a["comparisons"].items()}
                                  for cid, a in s["adaptivity"].items()}}
    brows = [r for r in rows if r["comparison"] == "B"]
    out["12"] = {"question": "Does the vocabulary-bearing representation (variant B) remain purely interpretive?",
                 "bit_identical_in_all_conditions": bool(brows) and all(r["exact_identical_share"] >= 1 for r in brows),
                 "conditions": len(brows), "evidence": [ev(r, noise) for r in brows]}
    if "disconnection" in s:
        d = s["disconnection"]
        dn = _noise(d["rows"])
        out["13"] = {"question": "Is disconnection reducible?", "verdict": d["verdict"],
                     "evidence": [ev(r, dn, "disconnection") for r in d["rows"] if r["comparison"] != "C~"]}
    if "topology_triggers" in s:
        tt = s["topology_triggers"]
        tn = _noise(tt["rows"])
        out["14"] = {"question": "Can cut and reconfiguration triggers be merged?", "verdict": tt["verdict"],
                     "evidence": [ev(r, tn, "topology_triggers") for r in tt["rows"] if r["comparison"] != "C~"]}
    if "compression_verdict" in s:
        out["15"] = {"question": "Does long-run compression preserve intervention-relevant distinctions?",
                     "verdict": s["compression_verdict"]}
    vis = [r for r in rows if r["comparison"] in STRUCTURAL and r["primary"] == "NON-REDUNDANT"]
    out["16"] = {"question": "What is the smallest world / scale / time window where reasoning structure changes "
                             "world behavior?",
                 "smallest_n": min((r["n"] for r in vis), default=None),
                 "smallest_horizon": min((r["horizon"] for r in vis), default=None),
                 "smallest_structure_size": min((r["size"] for r in vis), default=None),
                 "evidence": [ev(r, noise) for r in sorted(vis, key=lambda r: (r["n"], r["horizon"], r["size"]))][:20]}
    diff = [r for r in rows if r["comparison"] in STRUCTURAL and r["exact_identical_share"] < 1]
    first: dict[str, int] = {}
    up: dict[str, int] = {}
    for r in diff:
        first[r.get("visible_from") or "exact"] = first.get(r.get("visible_from") or "exact", 0) + 1
        up[r.get("visible_up_to") or "exact"] = up.get(r.get("visible_up_to") or "exact", 0) + 1
    out["17"] = {"question": "At what observation scale do hidden differences first become visible?",
                 "comparisons_with_trajectory_difference": len(diff),
                 "finest_systematic_resolution": first, "coarsest_systematic_resolution": up,
                 "exact_divergence_share": round(sum(1 for r in diff if r["exact_identical_share"] == 0) /
                                                 max(len(diff), 1), 4)}
    return out
