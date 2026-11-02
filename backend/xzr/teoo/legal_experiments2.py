"""Experiments LG2-EXP-01 .. 06 on the synthetic institution of ``legal.py`` (the source-based evaluator). New experiment ids: the results of EXP-01..10 and CMP-01 (run with ``legal_v1``) are not touched. Each ``run_*`` runs one
independent world (a seed). Results are about a SYNTHETIC institution and about this implementation."""

from __future__ import annotations

import itertools
from typing import Any

import numpy as np

from . import legal as L

LEVERS = ("review_authority", "review_independent", "propagate_correction", "low_burden", "resources_support", "material_relief", "reentry_support", "suspension", "expiry", "collective_challenge", "score_degrades_review")


def world(seed: int) -> L.Institution:
    rng = np.random.default_rng(60_000 + seed)
    return L.Institution(capacity=float(rng.uniform(0.3, 0.5)), lam=float(rng.uniform(0.6, 1.0)), review_capacity=float(rng.uniform(0.12, 0.25)))


def configure(base: L.Institution, lv: dict[str, bool]) -> L.Institution:
    return base.with_(review_authority=lv["review_authority"], review_independent=lv["review_independent"], propagate_correction=lv["propagate_correction"], appeal_burden=0.2 if lv["low_burden"] else 0.7,
                      resources_support=lv["resources_support"], material_relief=lv["material_relief"], reentry_support=lv["reentry_support"], suspension=lv["suspension"], score_expiry=4 if lv["expiry"] else None,
                      collective_challenge=lv["collective_challenge"], score_degrades_review=lv["score_degrades_review"], review_capacity=max(base.review_capacity, 0.25) if lv["review_authority"] else base.review_capacity)


def expected(lv: dict[str, bool], inst: L.Institution) -> dict[str, str]:
    """What an independent reader of the *configuration* (not of the simulation) expects of the findings that the levers determine without ambiguity. Findings that depend on measured rates near a threshold are not in it."""
    e = {"G10": "SECURED" if lv["propagate_correction"] else "ABSENT", "G12B": "ABSENT" if not lv["review_authority"] else "SECURED" if lv["review_independent"] else "PARTIAL",
         "G13": "SECURED" if lv["suspension"] else "ABSENT", "G15A": "SECURED" if lv["resources_support"] else "ABSENT", "G15C": "SECURED" if lv["reentry_support"] else "ABSENT", "G15D": "SECURED" if lv["collective_challenge"] else "ABSENT",
         "G14": "ABSENT" if not lv["expiry"] else None, "G12A": "SECURED" if lv["low_burden"] else "ABSENT" if not lv["resources_support"] else "PARTIAL"}
    return {k: v for k, v in e.items() if v is not None}


def checklist(inst: L.Institution, lv: dict[str, bool]) -> dict[str, str]:
    """A rule-based checker of formal provisions only (the existence of a function), the comparator: it cannot see that a route exists but cannot alter anything."""
    f = {"G10": True, "G11": inst.appeal, "G12A": True, "G12B": inst.appeal, "G13": inst.suspension, "G14": inst.score_expiry is not None, "G15A": inst.resources_support, "G15B": True, "G15C": inst.reentry_support, "G15D": inst.collective_challenge, "G2": True, "G1": True}
    return {k: "SECURED" if v else "ABSENT" for k, v in f.items()}


def run_01(seed: int) -> dict:
    """The evaluator against configurations of known construction: agreement with the lever reading, hard failures found vs a formal checklist, unobserved findings, non-compensation."""
    rng = np.random.default_rng(61_000 + seed)
    base = world(seed)
    rows = []
    for k in range(8):
        lv = {n: bool(rng.integers(0, 2)) for n in LEVERS}
        inst = configure(base, lv)
        a = L.audit(inst, seed * 10 + k, min_cases=0)
        st = {f["id"]: f["state"] for f in a["findings"]} | {s["id"]: s["state"] for s in a["sub_findings"]}
        exp = expected(lv, inst)
        chk = checklist(inst, lv)
        # hard failures that exist by construction: an appeal route that cannot alter anything; a correction that does not propagate; low-score subjects reviewed less (U)
        hard_truth = [("G11", not lv["review_authority"]), ("G12B", not lv["review_authority"]), ("G10", not lv["propagate_correction"])]
        found = sum(st[g] == "ABSENT" for g, t in hard_truth if t)
        found_chk = sum(chk[g] == "ABSENT" for g, t in hard_truth if t)
        n_truth = sum(t for _, t in hard_truth)
        obs = {f for f in L.FINDING_IDS if rng.uniform() < 0.7}
        part = L.audit(inst, seed * 10 + k, observed=obs, min_cases=0)
        pst = {f["id"]: f["state"] for f in part["findings"]} | {s["id"]: s["state"] for s in part["sub_findings"]}
        unobs_bad = [f for f in L.FINDING_IDS if f not in obs and inst.harm_irreversible and pst[f] not in ("INDETERMINATE",)]
        # non-compensation: change the evidence of one finding to a hard failure, nothing else may change
        ev = L.evidence_for(inst, seed * 10 + k, min_cases=0)
        target = L.FINDING_IDS[int(rng.integers(0, len(L.FINDING_IDS)))]
        ev2 = dict(ev)
        ev2[target] = L.prov(exists=False)
        a2 = L.audit(inst, seed * 10 + k, evidence=ev2, min_cases=0)
        st2 = {f["id"]: f["state"] for f in a2["findings"]} | {s["id"]: s["state"] for s in a2["sub_findings"]}
        changed = [g for g in L.FINDING_IDS if st2[g] != st[g] and g != target]
        rows.append({"agree": [st[g] == v for g, v in exp.items()], "n_expected": len(exp), "hard_truth": n_truth, "hard_found": found, "hard_found_checklist": found_chk, "unobserved_misreported": len(unobs_bad),
                     "non_compensation_violations": len(changed), "no_total": "no_total" in a and not any(k2 in a for k2 in ("total", "score", "average", "rank")), "advisory": a["recommendation"]["advisory_only"],
                     "u_state": a["U"]["state"], "u_truth_degraded": lv["score_degrades_review"]})
    return {"seed": seed, "rows": rows}


def run_02(seed: int) -> dict:
    """The Low-Score Subject Guarantee: score-conditioned review against a control; the finding U against a conventional group-fairness measure."""
    base = world(seed).with_(review_authority=True, review_independent=True, review_capacity=0.3, appeal_burden=0.3)
    arms = {"control": base, "degraded": base.with_(score_degrades_review=True), "degraded_then_removed": base.with_(score_degrades_review=False)}
    out = {}
    for name, inst in arms.items():
        r = L.simulate(inst, seed)
        a = L.audit(inst, seed, min_cases=0)
        out[name] = {"U": a["U"]["state"], "review_rate_low": r["review_rate_low_score"], "review_rate_high": r["review_rate_high_score"], "review_gap": r["review_rate_high_score"] - r["review_rate_low_score"], "tpr_gap": r["tpr_gap"],
                     "overturn_rate_of_wrongful": r["overturn_rate_of_wrongful"], "exclusion_qualified": r["exclusion_qualified"], "G2": next(f["state"] for f in a["findings"] if f["id"] == "G2")}
    return {"seed": seed, "arms": out}


def run_03(seed: int) -> dict:
    """Contestability architecture: authority, independence, capacity and burden, each on and off; the formal route against the effective one."""
    base = world(seed).with_(review_capacity=0.1)
    arms = {}
    for auth, ind, cap, low in itertools.product((False, True), repeat=4):
        inst = base.with_(review_authority=auth, review_independent=ind, review_capacity=0.3 if cap else 0.1, appeal_burden=0.2 if low else 0.7)
        r = L.simulate(inst, seed)
        a = L.audit(inst, seed, min_cases=0)
        st = {f["id"]: f["state"] for f in a["findings"]} | {s["id"]: s["state"] for s in a["sub_findings"]}
        arms[f"auth{int(auth)}_ind{int(ind)}_cap{int(cap)}_low{int(low)}"] = {"overturn_rate_of_wrongful": r["overturn_rate_of_wrongful"], "formal_appeal_rate": r["formal_appeal_rate"], "exclusion_qualified": r["exclusion_qualified"],
                                                                              "G11": st["G11"], "G12A": st["G12A"], "G12B": st["G12B"], "authority": auth, "independent": ind, "capacity": cap, "low_burden": low}
    return {"seed": seed, "arms": arms}


def run_04(seed: int) -> dict:
    """Material restoration: data correction, rights restoration, downstream propagation, material relief and re-entry support, added one by one."""
    base = world(seed).with_(review_authority=True, review_independent=True, review_capacity=0.25, appeal_burden=0.3)
    arms = {"appeal_only": base, "plus_propagation": base.with_(propagate_correction=True), "plus_material_relief": base.with_(propagate_correction=True, material_relief=True, review_delay=3),
            "plus_reentry_support": base.with_(propagate_correction=True, material_relief=True, review_delay=3, reentry_support=True), "plus_resources_support": base.with_(propagate_correction=True, material_relief=True, review_delay=3, reentry_support=True, resources_support=True)}
    arms["plus_material_relief_without_relief"] = base.with_(propagate_correction=True, review_delay=3)
    out = {}
    for name, inst in arms.items():
        r = L.simulate(inst, seed)
        a = L.audit(inst, seed, min_cases=0)
        sub = {s["id"]: s["state"] for s in a["sub_findings"]} | {f["id"]: f["state"] for f in a["findings"]}
        out[name] = {"downstream_access_qualified": r["downstream_access_qualified"], "mean_resources_qualified": r["mean_resources_qualified"], "reentered_qualified": r["reentered_qualified"], "exclusion_qualified": r["exclusion_qualified"],
                     "time_to_restoration_mean": r["time_to_restoration_mean"] if r["time_to_restoration_mean"] is not None else float("nan"), "G10": sub["G10"], "G15B": sub["G15B"], "G15C": sub["G15C"], "G15A": sub["G15A"]}
    return {"seed": seed, "arms": out}


def run_05(seed: int) -> dict:
    """Institutional time: the delay of review, the retention of a reversed denial downstream, and the expiry of scores."""
    base = world(seed).with_(review_authority=True, review_independent=True, review_capacity=0.25, appeal_burden=0.3, propagate_correction=False)
    arms = {}
    for delay, ret, exp in itertools.product((0, 3, 6), (3, 8), (None, 4)):
        inst = base.with_(review_delay=delay, record_retention=ret, score_expiry=exp)
        r = L.simulate(inst, seed)
        arms[f"delay{delay}_retention{ret}_expiry{exp}"] = {"time_to_restoration_mean": r["time_to_restoration_mean"] if r["time_to_restoration_mean"] is not None else float("nan"), "exclusion_qualified": r["exclusion_qualified"], "exclusion_persistence": r["exclusion_persistence"],
                                                             "downstream_access_qualified": r["downstream_access_qualified"], "group_exclusion_gap": r["group_exclusion_gap"], "overturn_rate_of_wrongful": r["overturn_rate_of_wrongful"]}
    return {"seed": seed, "arms": arms}


def run_06(seed: int) -> dict:
    """The Ontological Score Inheritance finding (A.6.1 of the 100_POINT_EDITION): the five required findings against what the configuration was built to be; and whether the treatment-produced share of the score is there."""
    base = world(seed)
    cases = {"no_inheritance": (base.with_(lam=0.0, downstream_sharing=False, proxy_gate=False), "no inheritance identified"),
             "without_safeguards": (base, "identified without safeguards"),
             "partial_safeguards": (base.with_(score_expiry=4), "identified with partial safeguards"),
             "effective_safeguards": (base.with_(score_expiry=4, propagate_correction=True, collective_challenge=True), "identified with effective safeguards")}
    out = {}
    for name, (inst, truth) in cases.items():
        f = L.ontological_inheritance_finding(inst, seed)
        out[name] = {"finding": f["finding"], "truth": truth, "match": f["finding"] == truth, "endogenous_share": f.get("endogenous_share")}
    f = L.ontological_inheritance_finding(base, seed, lineage_produced=False)
    out["lineage_not_produced"] = {"finding": f["finding"], "truth": "indeterminate", "match": f["finding"] == "indeterminate", "endogenous_share": None}
    return {"seed": seed, "arms": out}


def run_07(seed: int) -> dict:
    """The score-degradation test with and without a rule that an unperformed test is not a passed test: random configurations of known construction, the first version of the evaluator against the version with a minimum number of cases."""
    rng = np.random.default_rng(62_000 + seed)
    base = world(seed)
    rows = []
    for k in range(8):
        lv = {n: bool(rng.integers(0, 2)) for n in LEVERS}
        inst = configure(base, lv)
        row: dict[str, Any] = {"truth_degraded": lv["score_degrades_review"]}
        for name, mc in (("first_version", 0), ("min_cases_10", 10), ("min_cases_30", 30), ("min_cases_60", 60)):
            a = L.audit(inst, seed * 10 + k, min_cases=mc)
            row[name] = a["U"]["state"]
        rows.append(row)
    return {"seed": seed, "rows": rows}


RUN: dict[str, Any] = {"LG2-EXP-07": run_07, "LG2-EXP-01": run_01, "LG2-EXP-02": run_02, "LG2-EXP-03": run_03, "LG2-EXP-04": run_04, "LG2-EXP-05": run_05, "LG2-EXP-06": run_06}
