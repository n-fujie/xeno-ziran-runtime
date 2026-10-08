"""Stage 2 of the reduction study (systematic effects) and the classification rules.

Stage 1 (``reduction.run_all`` / ``analyse``) asks: is the paired trajectory distance larger than seed-to-seed
variability? That test is blind to small but *consistent* effects, and to slow structural effects. Stage 2 runs
longer (``SYSTEMATIC_HORIZON`` steps) over more seeds and tests signed, paired differences of scalar summaries
(second-half means of every descriptor series and event rate, final connection count, final mean difference):

    systematic effect  ⇔  |t| > T_THRESHOLD over paired seeds  and  |mean difference| > PRACTICAL · |full mean|

Classification definitions (applied mechanically; see ``classify``):

    removal divergent (config)  stage-1 verdict 'divergent' OR a stage-2 systematic effect in that configuration
    effect demonstrated         removal divergent in ≥ 1 configuration
    DESCRIPTIVE ONLY            removal bit-identical in every configuration (apart from the operation's own
                                state/events): nothing else reads it
    DERIVED                     output reconstructed exactly by an observer, or recomputed equivalently from other
                                state (aggregate): it need not be primitive state
    REDUCIBLE                   effect demonstrated AND a reduced implementation from other primitives is
                                equivalent everywhere with no systematic effect
    NON-REDUNDANT               effect demonstrated AND no tested reduction or compensation is equivalent everywhere
    UNRESOLVED                  effect not demonstrated but not bit-identical (it changes trajectories, not
                                detectably at the tested resolution), or its trigger (almost) never fired
"""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from .reduction import NOISE_SEED_OFFSET, VARIANTS
from .runs import CONFIGS, FULL, run

SYSTEMATIC_VARIANTS = ("cut_off", "disconnect_off", "connect_off", "reconfigure_off", "reconfigure_as_mutation",
                       "adapt_off", "adapt_all_carriers", "memory_off", "difference_relational", "transform_off",
                       "retention_off", "minimal")
# a removal's own outputs are not evidence of a downstream effect: its own event rate, and the topology-change
# series, which sums the structural events themselves
OWN_SUMMARIES = {
    "cut_off": {"rate:cuts", "s:topology_change"},
    "disconnect_off": {"rate:removed_connections", "s:topology_change"},
    "connect_off": {"rate:new_connections", "s:topology_change"},
    "reconfigure_off": {"rate:reconfigurations", "s:topology_change"},
    "memory_off": {"s:memory_dependence"},  # defined through memory; identically zero without it
}
SYSTEMATIC_SEEDS = tuple(range(21, 29))
SYSTEMATIC_HORIZON = 1200
T_THRESHOLD = 4.0
PRACTICAL = 0.02


def _summaries(rec) -> dict[str, float]:
    half = len(rec.series.get("s:ignitions", [])) // 2
    out = {}
    for k, v in rec.series.items():
        x = np.asarray(v, dtype=float)
        out[k] = float(x[len(x) // 2:].mean()) if len(x) else 0.0
    for k, v in rec.counts.items():
        if k in ("transformations", "returns"):
            continue  # descriptive event kinds; their absence is the ablation itself
        out[f"rate:{k}"] = float(np.mean(v[half:])) if v else 0.0
    out["edges:final"] = float(len(rec.snap_edges[-1])) if rec.snap_edges else 0.0
    out["difference:mean_final"] = float(rec.snap_diff[-1].mean()) if rec.snap_diff else 0.0
    return out


def _job(args: tuple) -> tuple:
    key, cfg, variant, seed, engine_seed = args
    return key, _summaries(run(cfg, variant, seed, engine_seed, horizon=SYSTEMATIC_HORIZON))


def systematic(configs=CONFIGS, seeds=SYSTEMATIC_SEEDS, procs: int = 7) -> dict:
    by_name = {v.name: v for v in VARIANTS}
    jobs = []
    for cfg in configs:
        for s in seeds:
            jobs.append(((cfg.name, s, "full"), cfg, FULL, s, s))
            jobs.append(((cfg.name, s, "noise"), cfg, FULL, s, s + NOISE_SEED_OFFSET))
            for vn in SYSTEMATIC_VARIANTS:
                jobs.append(((cfg.name, s, vn), cfg, by_name[vn], s, s))
    with ProcessPoolExecutor(procs) as ex:
        res = dict(ex.map(_job, jobs, chunksize=2))
    out: dict = {"horizon": SYSTEMATIC_HORIZON, "seeds": list(seeds), "t_threshold": T_THRESHOLD,
                 "practical": PRACTICAL, "own_summaries_excluded": {k: sorted(v) for k, v in OWN_SUMMARIES.items()},
                 "variants": {}, "raw": {f"{c}|{s}|{v}": x for (c, s, v), x in res.items()}}
    for vn in (*SYSTEMATIC_VARIANTS, "noise"):
        per_cfg = {}
        for cfg in configs:
            full = [res[(cfg.name, s, "full")] for s in seeds]
            var = [res[(cfg.name, s, vn)] for s in seeds]
            effects: dict[str, dict] = {}
            all_eff: dict[str, dict] = {}
            own = OWN_SUMMARIES.get(vn, set())
            for k in full[0]:
                if k.endswith("transformations") or k.endswith("returns") or k == "s:recurrence":
                    continue
                d = np.array([v[k] - f[k] for v, f in zip(var, full, strict=True)])
                base = np.mean([abs(f[k]) for f in full]) + 1e-12
                sd = d.std(ddof=1)
                if sd == 0:
                    t = 0.0 if d.mean() == 0 else float("inf")
                else:
                    t = float(d.mean() / (sd / np.sqrt(len(d))))
                rel = float(d.mean() / base)
                tt = round(t, 2) if np.isfinite(t) else "inf"
                all_eff[k] = {"t": tt, "relative": round(rel, 4)}
                if abs(t) > T_THRESHOLD and abs(rel) > PRACTICAL:
                    (effects.setdefault("__own__", {}) if k in own else effects)[k] = {"t": tt, "relative": round(rel, 4)}
            own_hits = effects.pop("__own__", {})
            per_cfg[cfg.name] = {"systematic_effects": effects, "own_output_effects": own_hits,
                                 "detected": bool(effects), "all": all_eff}
        out["variants"][vn] = per_cfg
    return out


def classify(an: dict, audits: dict, sysres: dict) -> list[dict]:
    V = an["variants"]
    S = sysres["variants"]
    configs = list(an["floors"])

    def divergent_cfgs(name: str) -> list[str]:
        return [c for c in configs if V[name]["configs"][c]["verdict"] == "divergent"
                or (name in S and S[name][c]["detected"])]

    def equivalent_everywhere(name: str) -> bool:
        return V[name]["overall"] in ("bit-identical", "equivalent") and not (
            name in S and any(S[name][c]["detected"] for c in configs))

    def ev(*names: str) -> list[str]:
        out = []
        for n in names:
            per = []
            for c, x in V[n]["configs"].items():
                sy = S.get(n, {}).get(c, {}).get("systematic_effects", {})
                own = S.get(n, {}).get(c, {}).get("own_output_effects", {})
                sy_s = ("; systematic: " + ", ".join(f"{k} t={v['t']} {v['relative']:+.1%}" for k, v in list(sy.items())[:4])
                        if sy else ("; stage 2: no downstream effect" if n in S else ""))
                if own:
                    sy_s += "; own outputs: " + ", ".join(f"{k} {v['relative']:+.0%} (t={v['t']})" for k, v in own.items())
                ex = x["exceeded"]
                per.append(f"{c}: {x['verdict']}" + (f" ({', '.join(e.replace('criterion:', '') for e in ex[:5])})" if ex else "")
                           + sy_s)
            out.append(f"{n} — " + " | ".join(per))
        return out

    totals = {c: f["full_event_totals"] for c, f in an["floors"].items()}

    def idle(kind: str) -> list[str]:
        return [c for c, t in totals.items() if t.get(kind, 0) < 10]

    obs, wr, infl = audits["observer"], audits["writes"], audits["influence"]
    obs_ok = all(o["penetrations_agree"] and o["returns_agree"] for o in obs.values())

    def status_for(removal: str, reductions: tuple[str, ...]) -> tuple[str, list[str]]:
        dv = divergent_cfgs(removal)
        if V[removal]["overall"] == "bit-identical" and not dv:
            return "DESCRIPTIVE ONLY", dv
        if not dv:
            return "UNRESOLVED", dv
        if any(equivalent_everywhere(r) for r in reductions):
            return "REDUCIBLE", dv
        return "NON-REDUNDANT", dv

    rows: list[dict] = []
    rows.append({"primitive": "Ignition (as a separate operation)", "question": "Is ignition distinct from a thresholded "
                 "transition?", "status": "REDUCIBLE" if V["fused_transition"]["overall"] == "bit-identical" else "UNRESOLVED",
                 "rule": "REDUCIBLE: a single fused thresholded-transition operation is bit-identical everywhere",
                 "reduced_to": "thresholded transition", "evidence": ev("fused_transition")})
    thr = ("threshold_off", "threshold_off_gain0.3", "threshold_off_gain0.6", "threshold_off_gain1.0")
    st, dv = status_for("threshold_off", thr[1:])
    rows.append({"primitive": "Threshold gating (ignition condition)", "question": "Can continuous transition, "
                 "gain-compensated, reproduce the shapes?", "status": st, "diverges_in": dv,
                 "rule": "NON-REDUNDANT unless some compensation is equivalent everywhere", "evidence": ev(*thr)})
    for prim, removal, comps, q in (
            ("Retention", "retention_off", ("retention_off_memory_x2", "retention_off_memory_x4"),
             "Does retention produce transition differences that memory alone cannot reproduce?"),
            ("Memory", "memory_off", ("memory_off_retention+0.05", "memory_off_retention+0.10"),
             "Does memory produce transition differences that retention alone cannot reproduce?")):
        st, dv = status_for(removal, comps)
        rows.append({"primitive": prim, "question": q, "status": st, "diverges_in": dv,
                     "rule": "NON-REDUNDANT if removal diverges somewhere and no compensation by the other primitive is "
                             "equivalent everywhere", "evidence": ev(removal, *comps)})
    st, _ = status_for("transform_off", ())
    rows.append({"primitive": "Transformation", "question": "Is transformation a separate primitive?", "status": st,
                 "rule": "DESCRIPTIVE ONLY if removal is bit-identical everywhere apart from its own state/events",
                 "evidence": ev("transform_off") + [f"influence(form) → {infl['form'] or 'no other array'}",
                                                    f"transform writes {wr.get('transform')}"]})
    derived = V["wave_state_off"]["overall"] == "bit-identical" and obs_ok
    rows.append({"primitive": "Penetration", "status": "DERIVED" if derived else "UNRESOLVED",
                 "question": "Is penetration non-redundant, or multi-hop propagation observed across boundaries?",
                 "rule": "DERIVED if removing wave state is bit-identical and an observer reconstructs origin, depth and "
                         "returns exactly from transition records",
                 "reduced_to": "dominant incoming connection of a configuration that passed its threshold + observer",
                 "evidence": ev("wave_state_off", "adapt_all_carriers") +
                 [f"observer reconstruction: {json.dumps(obs)}",
                  f"influence(wave_origin) → {infl['wave_origin'] or 'no other array'}; influence(pending_origin) → "
                  f"{infl['pending_origin']}"]})
    st, _ = status_for("return_events_off", ())
    rows.append({"primitive": "Return", "question": "Does return alter future transition conditions?",
                 "status": st if obs_ok else "UNRESOLVED",
                 "rule": "DESCRIPTIVE ONLY if disabling it is bit-identical everywhere and it is observer-reconstructible",
                 "evidence": ev("return_events_off") + [f"returns vs detected loops: {json.dumps(audits['returns_vs_loops'])}"]})
    st, dv = status_for("reconfigure_off", ("reconfigure_as_mutation",))
    rows.append({"primitive": "Reconfiguration", "status": st, "diverges_in": dv,
                 "question": "Does reconfiguration add anything beyond connection creation/deletion?",
                 "rule": "REDUCIBLE only if removing it demonstrably matters AND remove+create is equivalent everywhere",
                 "reduced_to": "connection mutation (remove + create)",
                 "evidence": ev("reconfigure_off", "reconfigure_as_mutation")})
    rows.append({"primitive": "Difference", "question": "Is Difference required as explicit per-configuration state?",
                 "status": "DERIVED" if equivalent_everywhere("difference_relational") else "UNRESOLVED",
                 "rule": "DERIVED if difference held on connections (+ a self-held input term), with the per-configuration "
                         "value recomputed as a sum, is equivalent everywhere without systematic effect",
                 "reduced_to": "sum of relational state", "evidence": ev("difference_relational")})
    reach_written = [op for op, fs in wr.items() if any("reach" in f for f in fs)]
    rows.append({"primitive": "Reachability", "question": "Is reachability a primitive or a derived metric?",
                 "status": "DERIVED" if not reach_written else "UNRESOLVED",
                 "rule": "DERIVED if no operation writes reachability state",
                 "evidence": [f"arrays written per operation: {json.dumps(wr)}",
                              "reachable = alive ∧ gate>0 ∧ ¬frozen[target]; computed on demand, never stored"]})
    for prim, removal, reds, kind in (("Transition", "transition_off", (), "penetrations"),
                                      ("Cut", "cut_off", (), "cuts"),
                                      ("Disconnection", "disconnect_off", (), "removed_connections"),
                                      ("Connection (closure)", "connect_off", (), "new_connections"),
                                      ("Weight adaptation", "adapt_off", ("adapt_all_carriers",), "penetrations")):
        st, dv = status_for(removal, reds)
        not_run = idle(kind)
        why = None
        if st == "UNRESOLVED":
            fires = [c for c in configs if removal in S and S[removal][c].get("own_output_effects")]
            if fires:
                why = (f"the operation fires (its own outputs change detectably in: {', '.join(fires)}), but no "
                       "downstream effect is detected in any regime; absence of a detected effect is not evidence of "
                       "redundancy")
            elif not_run:
                why = f"trigger fired < 10 times in stage 1 in: {', '.join(not_run)}; no downstream effect in stage 2"
            else:
                why = "changes trajectories, but no effect beyond the noise floor or systematic effect in any regime"
        rows.append({"primitive": prim, "question": f"Does removing {prim.lower()} demonstrably change behaviour?",
                     "status": st, "diverges_in": dv, "why_unresolved": why,
                     "rule": "NON-REDUNDANT if removal diverges somewhere and no reduction is equivalent everywhere",
                     "evidence": ev(removal, *reds)})
    rows.append({"primitive": "Decay", "question": "Is decay an operation?", "status": "DESCRIPTIVE ONLY",
                 "rule": "DESCRIPTIVE ONLY if it writes no state",
                 "evidence": [f"retain_and_decay writes {wr.get('retain_and_decay')}; decay events are a threshold "
                              "crossing of retention's output and are never read by any operation"]})
    return rows


def minimal_verification(an: dict, sysres: dict) -> dict:
    """Full vs MINIMAL in every regime, with the same stage-1 and stage-2 criteria used for single reductions."""
    v1 = an["variants"]["minimal"]
    v2 = sysres["variants"].get("minimal", {})
    per = {c: {"stage1_verdict": x["verdict"], "stage1_exceeded": x["exceeded"],
               "stage2_downstream_effects": v2.get(c, {}).get("systematic_effects", {}),
               "criteria_distance_over_tolerance": {k.replace("criterion:", ""): round(x["distance"][k] / x["tolerance"][k], 3)
                                                    for k in x["distance"] if k in x["tolerance"]}}
           for c, x in v1["configs"].items()}
    ok = all(p["stage1_verdict"] in ("bit-identical", "equivalent") and not p["stage2_downstream_effects"]
             for p in per.values())
    return {"verdict": "EQUIVALENT in every regime" if ok else "NOT EQUIVALENT", "equivalent": ok, "per_regime": per}


def reclassify(path: str, procs: int = 7, rerun_systematic: bool = False) -> dict:
    result = json.loads(Path(path).read_text())
    an = {"floors": result["floors"], "variants": result["variants"]}
    if rerun_systematic or "systematic" not in result:
        result["systematic"] = systematic(procs=procs)
    result["classification"] = classify(an, result["audits"], result["systematic"])
    if "minimal" in result["variants"]:
        result["minimal_verification"] = minimal_verification(an, result["systematic"])
    Path(path).write_text(json.dumps(result, indent=1, default=str))
    return result
