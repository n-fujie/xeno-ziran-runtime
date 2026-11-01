"""Experiments on the integration of the twelve MHEG duties and the fifteen guarantees (MH-EXP-01 .. 04). New experiment ids: the results of EXP-01..10, CMP-01 and LG2-EXP-01..07 are not touched.

Each ``run_NN(seed)`` is a deterministic function of its seed and returns one unit of results. Evidence classes: MH-EXP-01 and 03 are Implementation Properties (about the specification and the code), 02 an Implementation Property
with a paired Synthetic-world contrast, 04 a Synthetic-world Result. Everything concerns a SYNTHETIC institution; none of it observes a real institution, law or person.
"""

from __future__ import annotations

import dataclasses
import itertools
from typing import Any

import numpy as np

from . import legal as L
from . import legal_experiments2 as X
from . import mheg as M

RANK = {"SECURED": 0, "PARTIAL": 1, "INDETERMINATE": 2, "ABSENT": 3}


def full(seed: int, **kw: Any) -> L.Institution:
    """A synthetic institution that provides everything (every lever on, no proxy gate, an honest register): the base from which one failure at a time is introduced."""
    lv = {n: True for n in X.LEVERS}
    lv["score_degrades_review"] = False
    return X.configure(X.world(seed), lv).with_(proxy_gate=False, lam=0.0, registry=L.default_register(False), **kw)


def _dstates(report: dict, observed: set[str] | None = None) -> dict[str, dict[str, Any]]:
    return M.finding_states(report, observed)


# ------------------------------------------------------------------------------------------------ MH-EXP-01: the crosswalk as a projection (structural)
def run_01(seed: int) -> dict:
    """Remove one finding, or two, from a fully provisioned institution (its evidence is set to 'the function does not exist') and read the twelve duties. 19 single and 171 pair removals; no simulation is involved: this is the
    specification (the crosswalk) and the projection code."""
    app = L.applicability(L.Institution())
    ids = list(L.FINDING_IDS)

    def duties_for(removed: tuple[str, ...]) -> tuple[dict[str, str], dict[str, str]]:
        st = {f: {"state": M.directive_state(L.decide(L.prov(exists=False) if f in removed else L.prov(), app[f])["state"])} for f in ids}
        proj = M.project(st)
        return {f: st[f]["state"] for f in ids}, {d: proj[d]["state"] for d in M.DUTY_IDS}

    fs0, ds0 = duties_for(())
    single: dict[str, list[str]] = {}
    pair: dict[str, list[str]] = {}
    noncomp = 0
    for r in [(f,) for f in ids] + list(itertools.combinations(ids, 2)):
        fs, ds = duties_for(r)
        sig = tuple(d for d in M.DUTY_IDS if ds[d] == "VIOLATED")
        (single if len(r) == 1 else pair)["+".join(r)] = list(sig)
        for d in M.DUTIES:  # a duty cannot be SATISFIED while a finding it maps is VIOLATED
            if ds[d["id"]] == "SATISFIED" and any(fs[f] == "VIOLATED" for f in d["findings"]):
                noncomp += 1
    return {"seed": seed, "baseline_all_satisfied": all(v == "SATISFIED" for v in ds0.values()) and all(v == "SATISFIED" for v in fs0.values()), "single": single, "pair": pair, "noncompensation_violations": noncomp}


# ------------------------------------------------------------------------------------------------ MH-EXP-02: itemising the provisions
def run_02(seed: int) -> dict:
    """For fully provisioned worlds in which each itemised component (G3, G5, G9, G15A) is present with probability 0.85, compare the evaluation that takes the single yes/no provision with the itemised one."""
    rng = np.random.default_rng(71_000 + seed)
    rows = []
    for k in range(8):
        comps = {fid: {c: bool(rng.uniform() < 0.85) for c in cs} for fid, cs in L.COMPONENTS.items()}
        base = full(seed)
        item = base.with_(components=comps)
        ev_b, ev_i = L.evidence_for(base, seed * 10 + k, min_cases=0), L.evidence_for(item, seed * 10 + k, min_cases=0)
        ab, ai = L.audit(base, seed * 10 + k, evidence=ev_b, min_cases=0), L.audit(item, seed * 10 + k, evidence=ev_i, min_cases=0)
        sb = {s["id"]: s["state"] for s in ab["findings"]} | {s["id"]: s["state"] for s in ab["sub_findings"]}
        si = {s["id"]: s["state"] for s in ai["findings"]} | {s["id"]: s["state"] for s in ai["sub_findings"]}
        ids = ("G3", "G5", "G9", "G15A")
        db, di = M.project(M.finding_states(ab)), M.project(M.finding_states(ai))
        n_missing = {f: sum(not v for v in comps[f].values()) for f in ids}
        rows.append({"flag": {f: sb[f] for f in ids}, "item": {f: si[f] for f in ids}, "missing": n_missing, "base_secured": all(sb[f] == "SECURED" for f in ids), "raised": sum(RANK[si[f]] < RANK[sb[f]] for f in ids),
                     "rec_flag": ab["recommendation"]["candidate"], "rec_item": ai["recommendation"]["candidate"],
                     "duties_unmet_flag": sum(v["state"] not in ("SATISFIED", "NOT_APPLICABLE") for v in db.values()), "duties_unmet_item": sum(v["state"] not in ("SATISFIED", "NOT_APPLICABLE") for v in di.values())})
    return {"seed": seed, "rows": rows}


# ------------------------------------------------------------------------------------------------ MH-EXP-03: the state vocabulary and the duty projection under partial audits
def run_03(seed: int) -> dict:
    """Random configurations, random partial audits (each finding observed with probability 0.7), some evidence deliberately unknown, some institutions without irreversible harm: check the invariants of the directive's vocabulary."""
    rng = np.random.default_rng(72_000 + seed)
    bad = {"unobserved_not_not_evaluated": 0, "observed_indeterminate_not_insufficient": 0, "violated_iff_absent": 0, "duty_satisfied_with_unmet_finding": 0, "duty_violated_without_violated_finding": 0, "all_na_duty_not_na": 0,
           "not_applicable_only_if_inapplicable": 0, "total_in_projection": 0}
    n: dict[str, Any] = {"findings": 0, "duties": 0, "audits": 0, "states_seen": set()}
    for k in range(8):
        lv = {c: bool(rng.integers(0, 2)) for c in X.LEVERS}
        inst = X.configure(X.world(seed), lv).with_(harm_irreversible=bool(rng.integers(0, 2)))
        ev = L.evidence_for(inst, seed * 10 + k, min_cases=0)
        for f in L.FINDING_IDS:
            if rng.uniform() < 0.12:
                ev[f] = L.Evidence()  # nothing known about this finding
        obs = {f for f in L.FINDING_IDS if rng.uniform() < 0.7}
        rep = L.audit(inst, seed * 10 + k, observed=obs, evidence=ev, min_cases=0)
        fs = M.finding_states(rep, obs)
        proj = M.project(fs)
        app = L.applicability(inst)
        n["audits"] += 1
        for f, v in fs.items():
            n["findings"] += 1
            n["states_seen"].add(v["state"])
            if f not in obs and app[f][0] and v["state"] != "NOT_EVALUATED":
                bad["unobserved_not_not_evaluated"] += 1
            if f in obs and v["legacy_state"] == "INDETERMINATE" and v["state"] != "INSUFFICIENT_EVIDENCE":
                bad["observed_indeterminate_not_insufficient"] += 1
            if f in obs and ((v["legacy_state"] == "ABSENT") != (v["state"] == "VIOLATED")):
                bad["violated_iff_absent"] += 1
            if v["state"] == "NOT_APPLICABLE" and app[f][0]:
                bad["not_applicable_only_if_inapplicable"] += 1
        for d in M.DUTIES:
            n["duties"] += 1
            s = proj[d["id"]]["state"]
            mapped = [fs[f]["state"] for f in d["findings"]]
            if s == "SATISFIED" and any(m not in ("SATISFIED", "NOT_APPLICABLE") for m in mapped):
                bad["duty_satisfied_with_unmet_finding"] += 1
            if s == "VIOLATED" and "VIOLATED" not in mapped:
                bad["duty_violated_without_violated_finding"] += 1
            if all(m == "NOT_APPLICABLE" for m in mapped) and s != "NOT_APPLICABLE":
                bad["all_na_duty_not_na"] += 1
        if any(k2 in str(proj).lower() for k2 in ("total_score", "'rank'", "average")):
            bad["total_in_projection"] += 1
    n["states_seen"] = sorted(n["states_seen"])
    return {"seed": seed, "violations": bad, "n": n}


# ------------------------------------------------------------------------------------------------ MH-EXP-04: one stage of the transformation chain broken at a time
def _break(inst: L.Institution, stage: str) -> L.Institution:
    reg = list(inst.registry or L.default_register(False))
    if stage == "legal_source":
        return inst.with_(registry=[dataclasses.replace(e, legal_source=None) for e in reg])
    if stage == "translation":
        return inst.with_(registry=[dataclasses.replace(e, translation_loss_disclosed=False, proxy_for=e.proxy_for or "an undisclosed proxy", threshold=e.threshold if e.threshold is not None else 1.0) for e in reg])
    prov_off = {"data_representation": ("G5", "G8"), "classification": ("G4",), "institutional_treatment": ("G3",), "effective_access": ("G9",)}.get(stage, ())
    P = dict(inst.provisions)
    for f in prov_off:
        P[f] = L.prov(exists=False)
    lev = M.STAGE_LEVERS[stage] or {}
    return inst.with_(provisions=P, **lev)


OUTCOMES = ("overturn_rate_of_wrongful", "downstream_access_qualified", "exclusion_persistence", "exclusion_qualified", "burden_subject", "formal_appeal_rate", "reentered_qualified", "mean_resources_qualified")


def run_04(seed: int) -> dict:
    """A fully provisioned institution, then each of the nine stages of the legal transformation chain broken in turn (the levers that carry the stage in the simulation, and the provisions the audit reads). The outcomes of the
    simulation and the audit of the stage's findings are recorded for the intact institution and for each broken one."""
    base = full(seed)
    arms = {}
    for name in ("intact",) + M.CHAIN_IDS:
        inst = base if name == "intact" else _break(base, name)
        ev = L.evidence_for(inst, seed, min_cases=0)
        rep = L.audit(inst, seed, evidence=ev, min_cases=0)
        fs = M.finding_states(rep)
        run = L.simulate(inst, seed)
        stage_f = dict((c[0], c[4]) for c in M.CHAIN)
        own = [f for f in stage_f.get(name, ())]
        violated = [f for f, v in fs.items() if v["state"] == "VIOLATED"]
        ch = M.assess_transformation(inst, rep, ev)
        arms[name] = {"outcomes": {o: float(run[o]) for o in OUTCOMES}, "violated": violated, "own_findings_violated": [f for f in own if fs[f]["state"] == "VIOLATED"], "own_findings_not_satisfied": [f for f in own if fs[f]["state"] != "SATISFIED"],
                      "spillover": [f for f in violated if f not in own], "first_violated_stage": ch["first_violated_stage"], "duties_violated": [d for d, v in M.project(fs).items() if v["state"] == "VIOLATED"]}
    return {"seed": seed, "arms": arms}


RUN: dict[str, Any] = {"MH-EXP-01": run_01, "MH-EXP-02": run_02, "MH-EXP-03": run_03, "MH-EXP-04": run_04}
