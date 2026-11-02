"""Phase 4: pre-register, run and analyse experiments A-E on the SYNTHETIC world (xzr.teoo.experiments). Run: PYTHONPATH=. python scripts/teoo_phase4_run.py OUT_DIR [--workers N]

Order, which is the point: (1) the five protocols are built and *frozen* in a hash-chained registry (``protocol_registry.jsonl``); (2) only then the first datum exists (``note_first_data``) and the units are run; (3) the analyses
named in the protocols are computed exactly as registered, and each result is labelled confirmatory or exploratory by the registry, not by this script; (4) everything, including the results that do not support the
expectation, is written. A re-run with the same code gives identical files (every unit is seeded, no process-dependent hashing); ``--check`` re-runs one unit per experiment and compares digests.
Results are results about a synthetic world and about this implementation; none is an empirical observation of a body."""

from __future__ import annotations

import gzip
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import numpy as np

from xzr.teoo import experiments as X
from xzr.teoo import protocol as PR
from xzr.teoo import stats as S
from xzr.teoo.provenance import digest_of

SEEDS = list(range(1, 31))  # the seeds of protocol version 1 (the pilot); the confirmatory run uses version 2 with fresh seeds
SEEDS_D = list(range(101, 131))
FINAL_SEEDS = list(range(1001, 1031))
FINAL_SEEDS_D = list(range(1101, 1131))
AMEND_REASON = ("the pilot (version 1, seeds {s}) has been seen; version 2 repeats the same hypotheses, analyses, margins and criteria on fresh seeds so that the confirmatory run uses no seed whose outcome was known"
                "{extra}")
CLASS = "Synthetic-world Result"
BASE = {"ts": 0.02, "r": 0.5, "lim": 0.05, "win": 20.0}


def protocols() -> dict[str, dict]:
    def p(eid: str, hyps: list, targets: list, conds: list, control: str, seeds: list, trials: int, outcomes: dict, analyses: list, mult: str, fail: list, inst: dict, repro: list) -> dict:
        return PR.new_protocol(experiment_id=eid, hypotheses=hyps, targets=targets, instrument_conditions=inst, control_condition=control, conditions=conds, seeds=seeds, trials_per_condition=trials,
                               stopping_rule={"type": "fixed-n", "units": len(seeds), "no interim analysis": True}, outcomes=outcomes, analyses=analyses, multiplicity=mult, failure_conditions=fail,
                               reproduction={"generator": "xzr.teoo.experiments", "steps": repro, "world": "xzr.teoo.world (SYNTHETIC)"})
    an = lambda i, h, o, m, c=True, **kw: {"id": i, "hypothesis": h, "outcome": o, "method": m, "confirmatory": c, **kw}  # noqa: E731
    out = {}
    out["EXP-A"] = p("TEOO4-EXP-A", [{"id": "HA1", "statement": "Finer sampling raises the share of true frequency differences that are identified"},
                                     {"id": "HA2", "statement": "Finer sampling raises the share of true burst differences that are identified"},
                                     {"id": "HA3", "statement": "Sampling period does not change the share of true amplitude differences identified (equivalence within 0.10)"},
                                     {"id": "HA4", "statement": "A target whose TEOO status is MEASURED_VALID has a higher identification rate than one whose status is not"},
                                     {"id": "HA5", "statement": "Null cases are identified at a rate below 0.05 under every configuration (the simulation is calibrated)"}],
                     ["frequency, burst, amplitude, coupling features of one component"], ["fixed-fine", "variants"], "fixed-fine", SEEDS, 8,
                     {"primary": ["identification rate of true differences by feature type", "false identification rate of null cases"], "secondary": ["undetermined share", "effect of resolution, detection limit and window"]},
                     [an("A1", "HA1", "sensitivity_frequency", "paired-sign-flip", contrast="ts 0.02 minus ts 1.0", others=BASE), an("A2", "HA2", "sensitivity_burst", "paired-sign-flip", contrast="ts 0.02 minus ts 1.0", others=BASE),
                      an("A3", "HA3", "sensitivity_amplitude", "equivalence", margin=0.10, contrast="ts 0.02 minus ts 1.0", others=BASE), an("A4", "HA4", "rate_valid_minus_invalid", "paired-sign-flip", contrast="status valid minus not valid, true cases"),
                      an("A5", "HA5", "false_identification_rate", "exact-upper-bound", threshold=0.05, per="configuration"),
                      an("A6", "HA4", "accuracy_status_minus_limit_rule", "paired-sign-flip", c=False, contrast="status predictor minus the one-parameter rule amplitude >= detection limit")],
                     "holm", ["a null false-identification rate above 0.05 in any configuration invalidates the simulation", "fewer than 30 worlds"],
                     {"grid": X.GRID, "penetration": X.PEN, "alpha": 0.01}, ["run_a(seed) for each seed", "analyse"])
    out["EXP-B"] = p("TEOO4-EXP-B", [{"id": "HB1", "statement": "Cutting couplings lowers the share of the cut pairs that are read as coupled"}, {"id": "HB2", "statement": "Restoring them restores that share"},
                                     {"id": "HB3", "statement": "Reading with TEOO status (leaving a pair undecided when an endpoint is not MEASURED_VALID) has a higher precision than reading every pair"}],
                     ["coupling structure"], ["connected", "disconnected", "reconnected", "reconfigured"], "connected", SEEDS, 8,
                     {"primary": ["share of cut pairs read as coupled", "precision of the read structure"], "secondary": ["recall, F1, undecided pairs, invisible true couplings, components"]},
                     [an("B1", "HB1", "cut_pairs_read_coupled", "paired-sign-flip", contrast="connected minus disconnected, fine sensor"), an("B2", "HB2", "cut_pairs_read_coupled", "paired-sign-flip", contrast="reconnected minus disconnected, fine sensor"),
                      an("B3", "HB3", "precision", "paired-sign-flip", contrast="status-aware minus naive, medium sensor, connected condition")],
                     "holm", ["fewer than 10 worlds where both precisions are defined for B3"], {"sensors": ["fine", "medium", "limited"]}, ["run_graph(seed)", "analyse"])
    out["EXP-C"] = p("TEOO4-EXP-C", [{"id": "HC1", "statement": "Outcome-adaptive revision identifies more true differences than a fixed sensor"}, {"id": "HC2", "statement": "... more than a pre-specified revision schedule of equal cost"},
                                     {"id": "HC3", "statement": "... more than the best static sensor of equal cost (non-redundancy of revision)"}],
                     ["amplitude difference of each of 12 components"], ["fixed", "prespecified", "random", "adaptive", "static_costmatched"], "fixed", SEEDS, 8,
                     {"primary": ["number of true differences identified (of 12)"], "secondary": ["cost used", "revisions", "capabilities lost", "valid statuses"]},
                     [an("C1", "HC1", "identified", "paired-sign-flip", contrast="adaptive minus fixed"), an("C2", "HC2", "identified", "paired-sign-flip", contrast="adaptive minus prespecified"),
                      an("C3", "HC3", "identified", "paired-sign-flip", contrast="adaptive minus static_costmatched"), an("C4", "HC3", "identified", "equivalence", c=False, margin=0.5, contrast="adaptive minus static_costmatched"),
                      an("C5", "HC2", "identified", "paired-sign-flip", c=False, contrast="adaptive minus random")],
                     "holm", ["an arm exceeding the budget"], {"initial": X.INITIAL, "budget": X.BUDGET}, ["run_c(seed)", "analyse"])
    out["EXP-D"] = p("TEOO4-EXP-D", [{"id": "HD1", "statement": "Observed dependency between a source and a sink falls when their connection is cut"}, {"id": "HD2", "statement": "... and returns when it is restored"},
                                     {"id": "HD3", "statement": "Observed dependency tracks the simulated operability across conditions"}],
                     ["source-sink dependency"], ["connected", "disconnected", "reconnected", "reconfigured"], "connected", SEEDS_D, 8,
                     {"primary": ["observed dependency (best-lag correlation)", "simulated operability"], "secondary": ["agreement of sign of change for the reconfigured condition"]},
                     [an("D1", "HD1", "dependency_observed", "paired-sign-flip", contrast="connected minus disconnected, fine sensor"), an("D2", "HD2", "dependency_observed", "paired-sign-flip", contrast="reconnected minus disconnected, fine sensor"),
                      an("D3", "HD3", "spearman_dependency_operability", "paired-sign-flip", contrast="Spearman rho over all world x condition points, bootstrap over worlds")],
                     "holm", ["operability of the connected condition equal to 0 in more than half of the worlds"], {"sensors": ["fine"]}, ["run_graph(seed)", "analyse"])
    out["EXP-E"] = p("TEOO4-EXP-E", [{"id": "HE1", "statement": "Interpolation reconstructs a component with temporal gaps better than the zero predictor"}, {"id": "HE2", "statement": "Using the known couplings reconstructs unobserved components better than the zero predictor"},
                                     {"id": "HE3", "statement": "The 90% intervals of the interpolation are calibrated (coverage within 0.05 of 0.90) under temporal gaps"}],
                     ["latent signal of each component"], ["reference", "partial", "gaps", "coarse", "hidden", "noisy", "desync"], "reference", SEEDS, 1,
                     {"primary": ["normalised RMSE over identifiable cells", "coverage of 90% intervals", "share of cells declared unidentifiable"], "secondary": ["all conditions and methods"]},
                     [an("E1", "HE1", "nrmse_zero_minus_interp", "paired-sign-flip", contrast="gaps condition"), an("E2", "HE2", "nrmse_zero_minus_graph", "paired-sign-flip", contrast="partial condition, components the graph method can identify"),
                      an("E3", "HE3", "coverage_minus_0.9", "equivalence", margin=0.05, contrast="interp, gaps condition")],
                     "holm", ["fewer than 20 worlds with an identifiable cell in the partial condition"], {"degradations": list(X.DEGRADATIONS)}, ["run_e(seed)", "analyse"])
    return out


def _map(fn: Any, seeds: list[int], workers: int) -> list[dict]:
    with Pool(workers) as pool:
        return pool.map(fn, seeds)


# ------------------------------------------------------------------------------------------------ analyses
def an_a(units: list[dict]) -> dict:
    res: dict[str, Any] = {}

    def sens_of(u: dict, kind: str, ts: float) -> float | None:
        rows = [r for r in u["rows"] if r["kind"] == kind and r["truth"] and r["ts"] == ts and all(r[k] == BASE[k] for k in ("r", "lim", "win"))]
        return float(np.mean([r["result"] == "identified" for r in rows])) if rows else None

    for aid, kind in (("A1", "frequency"), ("A2", "burst"), ("A3", "amplitude")):
        d = [a - b for u in units if (a := sens_of(u, kind, 0.02)) is not None and (b := sens_of(u, kind, 1.0)) is not None]
        res[aid] = {**(S.paired_sign_flip(d, seed=1) if aid != "A3" else S.equivalence(d, 0.10, seed=1)), "feature": kind, "mean_fine": float(np.mean([sens_of(u, kind, 0.02) for u in units])), "mean_coarse": float(np.mean([sens_of(u, kind, 1.0) for u in units]))}
    diffs = []
    for u in units:
        v, inv = [r for r in u["rows"] if r["truth"] and r["status_valid"]], [r for r in u["rows"] if r["truth"] and not r["status_valid"]]
        if v and inv:
            diffs.append(float(np.mean([r["result"] == "identified" for r in v]) - np.mean([r["result"] == "identified" for r in inv])))
    allr = [r for u in units for r in u["rows"] if r["truth"]]
    res["A4"] = {**S.paired_sign_flip(diffs, seed=2), "rate_status_valid": float(np.mean([r["result"] == "identified" for r in allr if r["status_valid"]])), "rate_status_not_valid": float(np.mean([r["result"] == "identified" for r in allr if not r["status_valid"]])),
                 "n_true_rows": len(allr)}
    fp = {}
    for ts in X.GRID["ts"]:
        for r_ in X.GRID["r"]:
            for lim in X.GRID["lim"]:
                for win in X.GRID["win"]:
                    nulls = [r for u in units for r in u["rows"] if not r["truth"] and (r["ts"], r["r"], r["lim"], r["win"]) == (ts, r_, lim, win)]
                    k = sum(r["result"] == "identified" for r in nulls)
                    fp[f"ts{ts}_r{r_}_lim{lim}_win{win}"] = {"false_identifications": k, "null_cases": len(nulls), "rate": k / len(nulls), "upper95": S.upper_bound(k, len(nulls))}
    worst = max(fp.values(), key=lambda v: v["upper95"] or 0)
    res["A5"] = {"per_configuration": fp, "worst_upper95": worst["upper95"], "criterion_met": all((v["upper95"] or 1) <= 0.05 for v in fp.values()), "max_rate": max(v["rate"] for v in fp.values())}
    # exploratory: does the whole status model beat the one-parameter rule?
    acc_s, acc_r = [], []
    for u in units:
        rr = [r for r in u["rows"] if r["truth"]]
        acc_s.append(float(np.mean([(r["status_valid"]) == (r["result"] == "identified") for r in rr])))
        acc_r.append(float(np.mean([(r["amp"] >= r["lim"]) == (r["result"] == "identified") for r in rr])))
    res["A6"] = {**S.paired_sign_flip([a - b for a, b in zip(acc_s, acc_r, strict=True)], seed=3), "accuracy_status": float(np.mean(acc_s)), "accuracy_rule": float(np.mean(acc_r))}
    # exploratory: of the frequency differences that were identified, how many were identified *as the true difference* (estimated difference within 50% of the true one)?
    rec: dict[str, Any] = {}
    for ts in X.GRID["ts"]:
        ident = [r for u in units for r in u["rows"] if r["kind"] == "frequency" and r["truth"] and r["ts"] == ts and r["result"] == "identified"]
        ok = [r for r in ident if r["effect"] is not None and abs(r["effect"] - r["true_effect"]) <= 0.5 * abs(r["true_effect"])]
        rec[str(ts)] = {"identified": len(ident), "identified_as_the_true_difference": len(ok), "share": (len(ok) / len(ident)) if ident else None}
    res["A7"] = {"method": "descriptive", "frequency_differences_identified_as_the_true_difference_by_sampling_period": rec, "evidence_class": CLASS,
                 "registered_class": "exploratory (not declared in this version)", "note": "added after the pilot showed that a difference can survive aliasing without its value surviving; not part of any registered analysis"}
    # secondary tables
    sec: dict[str, Any] = {}
    for factor in ("ts", "r", "lim", "win"):
        sec[factor] = {str(v): {k: float(np.mean([x["result"] == "identified" for u in units for x in u["rows"] if x["truth"] and x["kind"] == k and x[factor] == v])) for k in X.TYPES} for v in X.GRID[factor]}
    und = float(np.mean([x["result"] == "undetermined" for u in units for x in u["rows"]]))
    res["secondary"] = {"identification_rate_by_factor_and_feature": sec, "undetermined_share": und,
                        "status_valid_fraction_of_true_rows": float(np.mean([r["status_valid"] for r in allr]))}
    return res


def _cut_pairs_read(u: dict, cond: str, sensor: str) -> float:
    cut = {tuple(e) for e in u["cut"]}
    rec = {tuple(e) for e in u["conditions"][cond]["sensors"][sensor]["recovered"]}
    return len(cut & rec) / len(cut) if cut else float("nan")


def an_b(units: list[dict]) -> dict:
    res: dict[str, Any] = {}
    for aid, c1, c0 in (("B1", "connected", "disconnected"), ("B2", "reconnected", "disconnected")):
        d = [_cut_pairs_read(u, c1, "fine") - _cut_pairs_read(u, c0, "fine") for u in units]
        res[aid] = {**S.paired_sign_flip(d, seed=4), "share_cut_pairs_read": {c: float(np.mean([_cut_pairs_read(u, c, "fine") for u in units])) for c in ("connected", "disconnected", "reconnected", "reconfigured")}}
    d3 = []
    for u in units:
        s = u["conditions"]["connected"]["sensors"]["medium"]
        if s["naive"]["precision"] is not None and s["aware"]["precision"] is not None:
            d3.append(s["aware"]["precision"] - s["naive"]["precision"])
    res["B3"] = {**S.paired_sign_flip(d3, seed=5), "worlds_with_both_defined": len(d3), "mean_undecided_pairs": float(np.mean([u["conditions"]["connected"]["sensors"]["medium"]["aware_undecided_pairs"] for u in units]))}
    desc: dict[str, Any] = {}
    for c in ("connected", "disconnected", "reconnected", "reconfigured"):
        desc[c] = {"components_mean": float(np.mean([u["conditions"][c]["components"] for u in units])), "edges_mean": float(np.mean([u["conditions"][c]["edges"] for u in units]))}
        for sn in ("fine", "medium", "limited"):
            f1 = [u["conditions"][c]["sensors"][sn]["naive"]["f1"] for u in units if u["conditions"][c]["sensors"][sn]["naive"]["f1"] is not None]
            rec = [u["conditions"][c]["sensors"][sn]["naive"]["recall"] for u in units if u["conditions"][c]["sensors"][sn]["naive"]["recall"] is not None]
            pre = [u["conditions"][c]["sensors"][sn]["naive"]["precision"] for u in units if u["conditions"][c]["sensors"][sn]["naive"]["precision"] is not None]
            desc[c][sn] = {"f1_mean": float(np.mean(f1)) if f1 else None, "recall_mean": float(np.mean(rec)) if rec else None, "precision_mean": float(np.mean(pre)) if pre else None,
                           "invisible_true_edges_mean": float(np.mean([len(u["conditions"][c]["sensors"][sn]["invisible_true_edges"]) for u in units])), "worlds_with_no_pair_decided": int(len(units) - len(f1))}
    res["descriptive"] = desc
    # newly reachable in the reconfigured condition: pairs that are true edges there and were not in the connected world
    newly = []
    for u in units:
        new = {tuple(e) for e in u["conditions"]["reconfigured"]["truth_edges"]} - {tuple(e) for e in u["conditions"]["connected"]["truth_edges"]}
        rec = {tuple(e) for e in u["conditions"]["reconfigured"]["sensors"]["fine"]["recovered"]}
        if new:
            newly.append(len(new & rec) / len(new))
    res["reconfigured_new_couplings_recovered_share"] = float(np.mean(newly)) if newly else None
    return res


def an_d(units: list[dict]) -> dict:
    dep = {c: [u["conditions"][c]["sensors"]["fine"]["dependency_observed"] for u in units] for c in ("connected", "disconnected", "reconnected", "reconfigured")}
    op = {c: [u["conditions"][c]["operability"] for u in units] for c in dep}
    res: dict[str, Any] = {}
    for aid, c1, c0 in (("D1", "connected", "disconnected"), ("D2", "reconnected", "disconnected")):
        d = [a - b for a, b in zip(dep[c1], dep[c0], strict=True) if a is not None and b is not None]
        res[aid] = {**S.paired_sign_flip(d, seed=6), "mean_dependency": {c: float(np.mean([x for x in v if x is not None])) for c, v in dep.items()}, "mean_operability": {c: float(np.mean(v)) for c, v in op.items()}}
    from scipy.stats import spearmanr

    xs = [(dep[c][i], op[c][i]) for c in dep for i in range(len(units)) if dep[c][i] is not None]
    rho = float(spearmanr([a for a, _ in xs], [b for _, b in xs])[0])
    rng = np.random.default_rng(7)
    boots = []
    for _ in range(2000):
        idx = rng.integers(0, len(units), len(units))
        pts = [(dep[c][i], op[c][i]) for c in dep for i in idx if dep[c][i] is not None]
        boots.append(float(spearmanr([a for a, _ in pts], [b for _, b in pts])[0]))
    p = (sum(b <= 0 for b in boots) + 1) / (len(boots) + 1)
    res["D3"] = {"method": "spearman, bootstrap over worlds", "rho": rho, "ci95": [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))], "p": p, "n_points": len(xs), "inferential": True}
    agree = [np.sign((dep["reconfigured"][i] or 0) - (dep["connected"][i] or 0)) == np.sign(op["reconfigured"][i] - op["connected"][i]) for i in range(len(units)) if dep["reconfigured"][i] is not None and dep["connected"][i] is not None]
    res["reconfigured_sign_agreement"] = {"share": float(np.mean(agree)), "n": len(agree), "chance": 0.5}
    res["operability_connected_zero_worlds"] = int(sum(v < 1e-9 for v in op["connected"]))
    return res


def an_c(units: list[dict]) -> dict:
    ident = {a: [u["arms"][a]["identified"] for u in units] for a in units[0]["arms"]}
    res: dict[str, Any] = {}
    for aid, a, b, kind in (("C1", "adaptive", "fixed", "sf"), ("C2", "adaptive", "prespecified", "sf"), ("C3", "adaptive", "static_costmatched", "sf"), ("C4", "adaptive", "static_costmatched", "eq"), ("C5", "adaptive", "random", "sf")):
        d = [x - y for x, y in zip(ident[a], ident[b], strict=True)]
        res[aid] = {**(S.paired_sign_flip(d, seed=8) if kind == "sf" else S.equivalence(d, 0.5, seed=8)), "contrast": f"{a} minus {b}"}
    res["arms"] = {a: {"identified_mean": float(np.mean(ident[a])), "identified_sd": float(np.std(ident[a], ddof=1)), "cost_over_initial_mean": float(np.mean([u["arms"][a]["cost_over_initial"] for u in units])),
                       "revisions_mean": float(np.mean([u["arms"][a]["revisions"] for u in units])), "capabilities_lost_total": int(sum(u["arms"][a]["capabilities_lost"] for u in units)),
                       "valid_statuses_mean": float(np.mean([u["arms"][a]["valid_statuses"] for u in units]))} for a in ident}
    res["budget_respected"] = all(u["arms"][a]["cost_over_initial"] <= u["budget"] + 1e-9 for u in units for a in u["arms"])
    res["adaptive_vs_static_cost"] = float(np.mean([u["arms"]["adaptive"]["cost_over_initial"] - u["arms"]["static_costmatched"]["cost_over_initial"] for u in units]))
    res["adaptive_decider"] = units[0]["arms"]["adaptive"]["decider"]
    res["autonomous_revision_demonstrated"] = any(e["autonomous_revision_demonstrated"] for u in units for a in u["arms"].values() for e in a["events"])
    return res


def an_e(units: list[dict]) -> dict:
    def per_world(cond: str, method: str, key: str) -> list[float | None]:
        out = []
        for u in units:
            cs = [c for c in u["conditions"][cond]["methods"][method] if c["identifiable"]]
            out.append(float(np.mean([c[key] for c in cs])) if cs else None)
        return out
    res: dict[str, Any] = {}
    z, i_ = per_world("gaps", "zero", "nrmse"), per_world("gaps", "interp", "nrmse")
    res["E1"] = {**S.paired_sign_flip([a - b for a, b in zip(z, i_, strict=True) if a is not None and b is not None], seed=9), "nrmse_zero": float(np.mean([x for x in z if x is not None])), "nrmse_interp": float(np.mean([x for x in i_ if x is not None]))}
    d2 = []
    for u in units:
        cs = u["conditions"]["partial"]["methods"]
        g = {c["c"]: c for c in cs["graph"] if c["identifiable"]}
        own = {c["c"] for c in cs["interp"] if c["identifiable"]}  # components with samples of their own are reconstructed from them; E2 is about the others
        zz = {c["c"]: c for c in cs["zero"] if c["identifiable"]}
        cells = [c for c in g if c not in own]
        if cells:
            d2.append(float(np.mean([zz[c]["nrmse"] - g[c]["nrmse"] for c in cells])))
    res["E2"] = {**S.paired_sign_flip(d2, seed=10), "worlds_with_identifiable_cells": len(d2)}
    cov = [c - 0.9 for c in per_world("gaps", "interp", "cover") if c is not None]
    res["E3"] = {**S.equivalence(cov, 0.05, seed=11), "mean_coverage": float(np.mean(cov) + 0.9)}
    table: dict[str, Any] = {}
    for cond in X.DEGRADATIONS:
        table[cond] = {}
        for m in ("zero", "interp", "graph"):
            cells = [c for u in units for c in u["conditions"][cond]["methods"][m]]
            ok = [c for c in cells if c["identifiable"]]
            table[cond][m] = {"unidentifiable_share": 1 - len(ok) / len(cells), "nrmse": float(np.mean([c["nrmse"] for c in ok])) if ok else None, "coverage90": float(np.mean([c["cover"] for c in ok])) if ok else None}
    res["table"] = table
    return res


ANALYSE = {"EXP-A": an_a, "EXP-B": an_b, "EXP-C": an_c, "EXP-D": an_d, "EXP-E": an_e}
RUN = {"EXP-A": X.run_a, "EXP-B": X.run_graph, "EXP-C": X.run_c, "EXP-D": X.run_graph, "EXP-E": X.run_e}


def total_observation_records(out: Path, seed: int) -> dict:
    """The record of one unit (the first of the graph experiments) such that its state can be rebuilt at any time: the body versions (cut, rejoin, rewire as new versions of a declared graph), the intervention records with the
    body and observation-configuration versions before and after, the observation configuration history and its replayed states, and the revision events of one revision experiment unit. Everything is SYNTHETIC and sealed."""
    from xzr.teoo import body as B
    from xzr.teoo import causal as CA
    from xzr.teoo import observation as OB
    from xzr.teoo import world as W
    from xzr.teoo.provenance import Ledger, Provenance, verify_record

    at = "2026-01-01T00:00:00.000000Z"
    rng = np.random.default_rng(seed)
    w = W.make_world(seed)
    cut = sorted(X._cuts(w, rng))
    rid = {e: f"r{e[0]}_{e[1]}" for e in w.edges}
    body = B.new_body(f"synthetic-world-{seed}", f"synthetic world {seed}", "artificial", components=[B.component(c.id, "segment", c.id, concept_only=True) for c in w.comps],
                      relations=[B.relation(rid[e], w.comps[e[0]].id, w.comps[e[1]].id, "coupling", directed=True, basis="declared") for e in w.edges], meta={"concept_only": True, "note": "SYNTHETIC world"}, at=at)
    v_conn = body.current["version"]
    for e in cut:
        body = B.sever(body, rid[e], at=at, note="phase 4 disconnection")
    v_cut = body.current["version"]
    for e in cut:
        body = B.rejoin(body, rid[e], at=at, note="phase 4 reconnection")
    v_rej = body.current["version"]
    src = dict(name="teoo.phase4/1", role="generator")
    srcd = {"kind": "generator", "description": "phase 4 synthetic world generator", "declared_by": "teoo.phase4"}
    cfgs = [X.cfg_of(X.sens(0.02, 0.5, 0.05, 20.0, 0.9), at=0.0), X.cfg_of(X.sens(0.2, 4.0, 0.8, 20.0, 0.4), at=10.0)]
    cfgs[1] = {**cfgs[1], "version": 2, "parent": 1, "change": {"op": "scale_change", "reason": "a coarser, cheaper sensor from t = 10 s"}}
    specs = [W.spec_of(w, i) for i in range(w.n())]
    ivs = []
    for name, before, after, kind in (("cut the couplings that join three components to the rest", v_conn, v_cut, "disconnect"), ("restore them", v_cut, v_rej, "reconnect")):
        ivs.append(CA.intervention_record(description=name, kind_of_action=kind, target="coupling set " + ",".join(rid[e] for e in cut), applied_at_s=0.0, assignment="researcher-chosen", body_version_before=before,
                                          body_version_after=after, config_version_before=1, config_version_after=1, provenance=Provenance.SYNTHETIC, creator=src, source=srcd, created_at=at))
    ledger = Ledger()
    for r in ivs:
        ledger.append(r)
    times = [0.0, 5.0, 9.9, 10.0, 15.0]
    states = OB.replay(cfgs, specs, times)
    again = OB.replay(cfgs, specs, times)
    c_unit = X.run_c(seed)
    doc = {"unit_seed": seed, "body": {"id": body.id, "versions": [{"version": v["version"], "change": v["change"], "digest": v["digest"]} for v in body.versions], "version_connected": v_conn, "version_disconnected": v_cut, "version_reconnected": v_rej},
           "cut_couplings": [rid[e] for e in cut], "interventions": [{"record_id": r["record_id"], "kind": r["kind"], "provenance": r["provenance"], "record_digest": r["record_digest"], "issues": verify_record(r)} for r in ivs],
           "ledger_issues": [i.to_dict() for i in ledger.verify()], "observation_configurations": [{"version": c["version"], "at": c["at"], "digest": OB.digest(c), "change": c["change"]} for c in cfgs],
           "replayed_states": [{"t": s_["t"], "config_version": s_["version"], "observed_of_declared": f"{s_['observed']}/{s_['declared_targets']}", "summary": s_["summary"], "digest": digest_of(s_)} for s_ in states],
           "replay_is_identical": states == again, "revision_events_unit": {"seed": seed, "arms": {a: {"sequence": v["sequence"], "decider": v["decider"], "events": v["events"]} for a, v in c_unit["arms"].items()}},
           "scope": "SYNTHETIC; the unobserved are not recorded as 0; autonomous revision is not demonstrated (every event names who initiated it)"}
    (out / "total_observation_records.json").write_text(json.dumps(doc, indent=1, default=str))
    return doc


def amendments(protos: dict[str, dict]) -> dict[str, tuple[dict, str]]:
    out = {}
    for key, p in protos.items():
        seeds = FINAL_SEEDS_D if key == "EXP-D" else FINAL_SEEDS
        changes: dict[str, Any] = {"seeds": seeds, "stopping_rule": {**p["stopping_rule"], "units": len(seeds)}}
        extra = ""
        if key == "EXP-E":
            changes["analyses"] = [{**a, "outcome": "nrmse_zero_minus_graph_on_components_without_own_samples"} if a["id"] == "E2" else a for a in p["analyses"]]
            changes["hypotheses"] = [{**h, "statement": "Using the known couplings reconstructs components that have no samples of their own better than the zero predictor"} if h["id"] == "HE2" else h for h in p["hypotheses"]]
            extra = ("; also, the pilot showed that the graph method of version 1 ignored a component's own samples when parents were available, which is a defect of the method definition (not of the hypothesis): "
                     "version 2 reconstructs from own samples when there are any and from the parents only otherwise, and E2 is restricted to components without own samples")
        out[key] = (changes, AMEND_REASON.format(s="1-30, and 101-130 for D", extra=extra))
    return out


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 6
    check = "--check" in sys.argv
    pilot_registry = Path(__file__).resolve().parents[2] / "docs" / "teoo_evidence" / "phase4" / "pilot_seeds_1_30" / "protocol_registry.jsonl"
    reg_path = out / "protocol_registry.jsonl"
    if not check:
        reg_path.write_bytes(pilot_registry.read_bytes())  # the registry continues from the pilot's: version 1 was frozen before the pilot data
    reg = PR.ProtocolRegistry(reg_path)
    assert not reg.verify(), reg.verify()
    protos1 = protocols()
    protos: dict[str, dict] = {}
    if not check:
        for key, (changes, reason) in amendments(protos1).items():
            p2 = reg.amend(protos1[key]["experiment_id"], 1, changes, reason)
            reg.freeze(p2["experiment_id"], 2, time.time())
            protos[key] = p2
        for p in protos.values():
            reg.note_first_data(p["experiment_id"], 2, time.time() + 1.0)  # the first datum of version 2 is produced only after every version 2 is frozen
    else:
        for key, p in protos1.items():
            protos[key] = reg.get(p["experiment_id"], 2)
    summary: dict[str, Any] = {}
    for key, p in protos.items():
        t0 = time.time()
        seeds = p["seeds"]
        if check:
            u = RUN[key](seeds[0])
            saved = json.loads((out / f"{key}_unit_first.json").read_text())
            summary[key] = {"replay_identical": digest_of(json.loads(json.dumps(u, default=str))) == saved["digest"]}
            continue
        units = _map(RUN[key], seeds, workers)
        res = ANALYSE[key](units)
        fam = {a["id"]: res[a["id"]]["p"] for a in p["analyses"] if a.get("confirmatory") and res.get(a["id"], {}).get("p") is not None and a["method"] in ("paired-sign-flip", "randomization-test")}
        holm = S.holm(fam)
        for aid, h in holm.items():
            res[aid]["p_holm"] = h["p_holm"]
        for a in p["analyses"]:
            res[a["id"]]["registered_class"] = reg.analysis_class(p["experiment_id"], 2, a["id"])
            res[a["id"]]["evidence_class"] = CLASS
        doc = {"experiment_id": p["experiment_id"], "protocol_version": 2, "protocol_digest": PR.body_digest(p), "protocol": p, "units": len(units), "seeds": seeds, "evidence_class": CLASS, "seconds": round(time.time() - t0, 1),
               "results": res, "note": "results about a SYNTHETIC world and this implementation; not an observation of any body"}
        (out / f"{key}.json").write_text(json.dumps(doc, indent=1, default=str))
        (out / f"{key}_unit_first.json").write_text(json.dumps({"seed": seeds[0], "digest": digest_of(json.loads(json.dumps(units[0], default=str)))}))
        with gzip.open(out / f"{key}_units.json.gz", "wt") as f:
            json.dump(units, f, default=str, separators=(",", ":"))
        summary[key] = {a["id"]: {k: res[a["id"]].get(k) for k in ("mean_diff", "p", "p_holm", "supported", "ci95", "ci90", "rho")} for a in p["analyses"]}
        print(key, round(time.time() - t0, 1), "s", json.dumps(summary[key], default=str)[:500], flush=True)
    if check:
        print(json.dumps(summary))
    else:
        rec = total_observation_records(out, FINAL_SEEDS[0])
        print("registry verify:", reg.verify(), "| total-observation record: replay identical", rec["replay_is_identical"], "ledger issues", rec["ledger_issues"])


if __name__ == "__main__":
    main()
