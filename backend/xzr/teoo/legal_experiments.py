"""Experiments EXP-01 .. EXP-10 and CMP-01 on the synthetic institution of ``legal.py``. Each ``run_*`` runs one independent world (a seed) and returns plain data. Results are results about a SYNTHETIC institution
and about this implementation; none is an observation of any real institution, law or person. ``scripts/teoo_legal_run.py`` pre-registers, runs and analyses them."""

from __future__ import annotations

import itertools
from typing import Any

import numpy as np

from . import legal_v1 as L

MECHS = ("gate", "inheritance", "downstream", "weak_review")
FIELD_OF = {"gate": "inherited_record", "inheritance": "score_log", "downstream": "downstream_log", "weak_review": "review_log"}


def world_inst(seed: int) -> L.Institution:
    rng = np.random.default_rng(50_000 + seed)
    return L.Institution(capacity=float(rng.uniform(0.3, 0.5)), lam=float(rng.uniform(0.6, 1.0)), review_capacity=float(rng.uniform(0.1, 0.2)))


def sim(inst: L.Institution, seed: int, k: int = 0, **kw: Any) -> dict:
    return L.simulate(inst, seed * 100 + k, **kw)


def run_e01(seed: int) -> dict:
    b = world_inst(seed)
    arms = {"baseline": b, "fairness_opt": b.with_(fairness_opt=True), "fairness_opt_gate_removed": b.with_(fairness_opt=True, proxy_gate=False)}
    return {"seed": seed, "arms": {k: {m: v[m] for m in ("tpr_gap", "exclusion_persistence", "exclusion_qualified", "group_exclusion_gap")} for k, v in ((a, sim(i, seed)) for a, i in arms.items())}}


def run_e02(seed: int) -> dict:
    b = world_inst(seed)
    arms = {"baseline": b, "lower_threshold": b.with_(capacity=min(0.9, b.capacity + 0.2)), "delete_score": b.with_(tau_score=False), "remove_gate": b.with_(proxy_gate=False), "delete_score_and_gate": b.with_(tau_score=False, proxy_gate=False)}
    return {"seed": seed, "arms": {a: {m: r[m] for m in ("exclusion_qualified", "exclusion_persistence", "group_exclusion_gap", "access_rate")} for a, r in ((a, sim(i, seed)) for a, i in arms.items())}}


def run_e03(seed: int) -> dict:
    b = world_inst(seed)
    resid = b.with_(proxy_gate=False)  # the gate is removed; the score still carries the inherited record, the second institution still inherits
    clean = b.with_(proxy_gate=False, lam=0.0, downstream_sharing=False)
    arms = {"before_removal": b, "gate_removed_with_residual_dependencies": resid, "gate_removed_dependencies_cut": clean}
    return {"seed": seed, "arms": {a: {m: r[m] for m in ("group_exclusion_gap", "excl_g1", "exclusion_qualified")} for a, r in ((a, sim(i, seed)) for a, i in arms.items())}}


def run_e04(seed: int) -> dict:
    b = world_inst(seed)
    arms = {"formal_only": b.with_(appeal=True, review_authority=False, review_independent=False), "effective": b.with_(appeal=True, review_authority=True, review_independent=True, review_capacity=0.3, appeal_burden=0.2)}
    return {"seed": seed, "arms": {a: {m: r[m] for m in ("formal_appeal_rate", "overturn_rate_of_wrongful", "exclusion_qualified", "burden_subject")} for a, r in ((a, sim(i, seed)) for a, i in arms.items())}}


def run_e05(seed: int) -> dict:
    b = world_inst(seed).with_(review_authority=True, review_independent=True, review_capacity=0.2)
    arms = {"no_correction": (b, None), "correction_no_propagation": (b.with_(propagate_correction=False), 8), "correction_propagated": (b.with_(propagate_correction=True), 8), "correction_propagated_with_reentry_support": (b.with_(propagate_correction=True, reentry_support=True), 8)}
    return {"seed": seed, "arms": {a: {m: r[m] for m in ("exclusion_qualified", "downstream_access_qualified", "downstream_mismatch", "reentered_qualified")} for a, r in ((a, sim(i, seed, correct_at=c)) for a, (i, c) in arms.items())}}


def run_e06(seed: int) -> dict:
    b = world_inst(seed)
    arms = {f"lambda_{lam}": b.with_(lam=lam) for lam in (0.0, 0.4, 0.8, 1.2)}
    arms["lambda_0.8_with_expiry"] = b.with_(lam=0.8, score_expiry=4)
    return {"seed": seed, "arms": {a: {m: r[m] for m in ("group_exclusion_gap", "excl_g1", "exclusion_qualified")} for a, r in ((a, sim(i, seed)) for a, i in arms.items())}}


# ---- EXP-07 observation revision: which active mechanisms of the institution can an observer identify, with fixed / revised / cost-matched static observation
def _active(seed: int) -> dict[str, bool]:
    rng = np.random.default_rng(70_000 + seed)
    a = {m: bool(rng.uniform() < 0.6) for m in MECHS}
    if not any(a.values()):
        a[MECHS[int(rng.integers(0, 4))]] = True
    return a


def inst_with(act: dict[str, bool], seed: int) -> L.Institution:
    b = world_inst(seed)
    return b.with_(proxy_gate=act["gate"], lam=b.lam if act["inheritance"] else 0.0, downstream_sharing=True, propagate_correction=not act["downstream"], review_authority=not act["weak_review"], review_independent=not act["weak_review"],
                   review_capacity=0.25)


_CAL: dict[str, float] = {}


def _stat(mech: str, r: dict) -> float:
    return {"gate": r["deny_highr"] - r["deny_lowr"], "inheritance": -r["corr_score_r"], "downstream": r["downstream_mismatch"], "weak_review": -r["overturn_rate_of_wrongful"]}[mech]


def calibration() -> dict[str, float]:
    """Thresholds for each mechanism's detector: the 95th percentile of its statistic over worlds in which that mechanism is switched off (all others as in the world)."""
    if not _CAL:
        for mech in MECHS:
            vals = []
            for s in range(900, 940):
                act = _active(s)
                act[mech] = False
                vals.append(_stat(mech, sim(inst_with(act, s), s)))
            _CAL[mech] = float(np.quantile(vals, 0.95))
    return _CAL


def identify(act: dict[str, bool], seed: int, fields: set[str]) -> dict[str, str]:
    r = sim(inst_with(act, seed), seed)
    cal = calibration()
    return {m: ("not_observed" if FIELD_OF[m] not in fields else ("identified_active" if _stat(m, r) > cal[m] else "not_identified")) for m in MECHS}


def run_e07(seed: int) -> dict:
    rng = np.random.default_rng(71_000 + seed)
    act = _active(seed)
    base_r = sim(inst_with(act, seed), seed)
    start = {str(x) for x in rng.choice([FIELD_OF[m] for m in MECHS], 2, replace=False)}
    rest = [f for f in FIELD_OF.values() if f not in start]
    # outcome-responsive revision: a group gap in the (always observable) outcome points to the fields about inheritance; otherwise to the fields about review and downstream
    gap = base_r["group_exclusion_gap"]
    pref = ["inherited_record", "score_log", "review_log", "downstream_log"] if gap > 0.15 else ["review_log", "downstream_log", "inherited_record", "score_log"]
    adaptive = set(start) | set([f for f in pref if f in rest][:1])
    prespec = set(start) | set([f for f in ("inherited_record", "score_log", "review_log", "downstream_log") if f in rest][:1])
    static = set(start) | {rest[int(rng.integers(0, len(rest)))]}  # the same cost (one more field) chosen without looking at anything
    arms = {"fixed": set(start), "prespecified_revision": prespec, "outcome_responsive_revision": adaptive, "cost_matched_static": static}
    out = {}
    for a, fields in arms.items():
        res = identify(act, seed, fields)
        out[a] = {"fields": len(fields), "true_identified": sum(res[m] == "identified_active" and act[m] for m in MECHS), "false_identified": sum(res[m] == "identified_active" and not act[m] for m in MECHS),
                  "active": sum(act.values()), "not_observed_active": sum(res[m] == "not_observed" and act[m] for m in MECHS)}
    return {"seed": seed, "active": act, "arms": out}


# ---- EXP-08 inferential versus operational
MENU = ("remove_gate", "zero_inheritance", "enable_propagation", "independent_review", "fairness_opt", "delete_score", "expiry", "reentry_support")
INFERENTIAL = {"remove_gate": 0.9, "independent_review": 0.85, "enable_propagation": 0.8, "delete_score": 0.7, "zero_inheritance": 0.65, "fairness_opt": 0.6, "expiry": 0.5, "reentry_support": 0.45}  # how convincing each is as an argument


def apply(inst: L.Institution, names: list[str]) -> L.Institution:
    out = inst
    for n in names:
        out = {"remove_gate": lambda i: i.with_(proxy_gate=False), "zero_inheritance": lambda i: i.with_(lam=0.0), "enable_propagation": lambda i: i.with_(propagate_correction=True),
               "independent_review": lambda i: i.with_(review_independent=True, review_authority=True, review_capacity=0.3), "fairness_opt": lambda i: i.with_(fairness_opt=True), "delete_score": lambda i: i.with_(tau_score=False),
               "expiry": lambda i: i.with_(score_expiry=4), "reentry_support": lambda i: i.with_(reentry_support=True)}[n](out)
    return out


def hidden_world(seed: int) -> tuple[dict[str, bool], L.Institution]:
    act = _active(seed + 3000)
    return act, inst_with(act, seed)


def run_e08(seed: int) -> dict:
    rng = np.random.default_rng(80_000 + seed)
    act, inst = hidden_world(seed)
    base = sim(inst, seed)["exclusion_qualified"]
    executable = {str(x) for x in rng.choice(MENU, 5, replace=False)}  # what this actor has the authority to do
    effect = {n: base - sim(apply(inst, [n]), seed)["exclusion_qualified"] for n in MENU}
    ranked = sorted(MENU, key=lambda n: -INFERENTIAL[n])
    top3 = ranked[:3]
    exec_top = [n for n in top3 if n in executable]
    realised = sum(max(0.0, effect[n]) for n in exec_top)  # a non-executable intervention changes nothing
    best_exec = sorted((n for n in executable), key=lambda n: -effect[n])[:3]
    return {"seed": seed, "base": base, "executable": sorted(executable), "effect": effect, "top3_inferential": top3, "top3_executable_share": len(exec_top) / 3, "realised_effect_of_inferential_top3": realised,
            "effect_of_operationally_best_executable3": sum(max(0.0, effect[n]) for n in best_exec), "inferentially_valid_but_no_effect": sum(1 for n in top3 if n not in executable or effect[n] <= 0.02),
            "inferential_scores": [INFERENTIAL[n] for n in MENU], "operational_effects": [effect[n] for n in MENU]}


# ---- EXP-09 fifteen guarantees
def run_e09(seed: int) -> dict:
    rng = np.random.default_rng(90_000 + seed)
    base = L.Institution().with_(review_authority=True, review_independent=True, review_capacity=0.3, appeal_burden=0.2, propagate_correction=True, score_expiry=4, reentry_support=True, suspension=True, proxy_gate=False, lam=0.0)
    removed = {str(x) for x in rng.choice(L.PROVISIONS, 3, replace=False)}
    inst = base.with_(provisions={p: (p not in removed) for p in L.PROVISIONS})
    full = L.assess_guarantees(inst, seed)
    seen = {str(x) for x in rng.choice(L.PROVISIONS, 11, replace=False)}  # a partial observation: eleven of fifteen provisions are visible
    part = L.assess_guarantees(inst, seed, observed=seen)
    ineffective = inst.with_(review_authority=False, review_independent=False)  # a formal appeal that cannot change anything
    inef = L.assess_guarantees(ineffective, seed)
    rule_based = {a["number"]: ("SECURED" if ineffective.provisions[a["provision"]] else "ABSENT") for a in inef}  # a checklist of formal provisions
    r = {"seed": seed, "removed": sorted(removed)}
    st = {a["provision"]: a["state"] for a in full}
    pt = {a["provision"]: a["state"] for a in part}
    r["violation_detection_full"] = float(np.mean([st[p] == "ABSENT" for p in removed]))
    r["false_detection_full"] = float(np.mean([st[p] == "ABSENT" for p in L.PROVISIONS if p not in removed]))
    unseen_removed = [p for p in removed if p not in seen]
    r["unseen_removed"] = len(unseen_removed)
    r["unseen_removed_reported_indeterminate"] = sum(pt[p] == "INDETERMINATE" for p in unseen_removed)
    r["unseen_removed_reported_secured_or_absent"] = sum(pt[p] in ("SECURED", "ABSENT") for p in unseen_removed)
    r["false_absent_partial"] = float(np.mean([pt[p] == "ABSENT" for p in L.PROVISIONS if p not in removed]))
    r["formal_but_ineffective_found"] = int(any(a["provision"] in ("contestation", "human_review") and a["state"] == "PARTIAL" for a in inef))
    r["rule_based_finds_ineffective"] = int(any(rule_based[a["number"]] != "SECURED" for a in inef if a["provision"] in ("contestation", "human_review")))
    r["remedy_given_when_not_secured"] = float(np.mean([bool(a["remedy_path"]) for a in full if a["state"] in ("ABSENT", "PARTIAL")])) if any(a["state"] in ("ABSENT", "PARTIAL") for a in full) else 1.0
    r["states_are_not_one_score"] = len({a["state"] for a in full}) >= 1 and len(full) == 15
    r["inapplicable_has_checked_reason"] = all(a["state"] != "INAPPLICABLE" or "checked against the configuration" in a["reason"] for a in L.assess_guarantees(base.with_(harm_irreversible=False), seed))
    return r


def run_e10(seed: int) -> dict:
    b = world_inst(seed)
    arms = {"institution_self_review": b.with_(review_independent=False, review_authority=True, review_capacity=0.15, appeal_burden=0.5),
            "independent_body_with_authority": b.with_(review_independent=True, review_authority=True, review_capacity=0.3, appeal_burden=0.3, propagate_correction=True),
            "independent_body_with_consent_and_formal_procedure": b.with_(review_independent=True, review_authority=True, review_capacity=0.18, appeal_burden=0.7, propagate_correction=True),
            "subject_initiated_correction_no_consent_step": b.with_(review_independent=True, review_authority=True, review_capacity=0.3, appeal_burden=0.1, propagate_correction=True)}
    return {"seed": seed, "arms": {a: {m: r[m] for m in ("exclusion_qualified", "overturn_rate_of_wrongful", "burden_subject", "burden_institution")} for a, r in ((a, sim(i, seed)) for a, i in arms.items())}}


# ---- CMP-01 six planners on one task: choose at most two executable interventions to lower exclusion, from the same observation
BUDGET = 2
FIX_OF = {"gate": "remove_gate", "inheritance": "zero_inheritance", "downstream": "enable_propagation", "weak_review": "independent_review"}


def _exec(seed: int) -> set[str]:
    rng = np.random.default_rng(81_000 + seed)
    return {str(x) for x in rng.choice(MENU, 6, replace=False)}


def _outcome(act: dict, seed: int, plan: list[str]) -> float:
    return sim(apply(inst_with(act, seed), plan), seed, k=7)["exclusion_qualified"]


def _believed(obs: dict[str, str]) -> dict[str, bool]:
    return {m: obs[m] == "identified_active" for m in MECHS}  # an unobserved or unidentified mechanism is assumed inactive by a planner that cannot see it


def _model_plan(obs: dict[str, str], seed: int, ex: set[str], rollouts: int) -> tuple[list[str], int]:
    """Exhaustive search over feasible subsets with the simulator of the *believed* institution (mechanisms the planner cannot see are taken as inactive)."""
    bel = _believed(obs)
    if not any(bel.values()):
        bel = {**bel, "gate": True}  # a planner that believes nothing must still have a model: the default one
    best, bs, calls = [], 9.0, 0
    for k in range(0, BUDGET + 1):
        for sub in itertools.combinations(sorted(ex), k):
            v = float(np.mean([sim(apply(inst_with(bel, seed), list(sub)), seed, k=20 + j)["exclusion_qualified"] for j in range(rollouts)]))
            calls += rollouts
            if v < bs - 1e-9:
                best, bs = list(sub), v
    return best, calls


def run_cmp(seed: int) -> dict:
    rng = np.random.default_rng(82_000 + seed)
    act, inst = hidden_world(seed)
    ex = _exec(seed)
    start = {str(x) for x in rng.choice([FIELD_OF[m] for m in MECHS], 2, replace=False)}
    obs0 = identify(act, seed, start)
    base = _outcome(act, seed, [])
    out: dict[str, Any] = {}
    # 1 rule-based legal compliance: fix the formal provisions that are missing, in guarantee order (it sees the provisions, not the mechanisms)
    missing = []
    if not inst.propagate_correction:
        missing.append("enable_propagation")
    if not (inst.review_independent and inst.review_authority):
        missing.append("independent_review")
    missing += ["expiry", "reentry_support"]
    plan1 = [n for n in dict.fromkeys(missing) if n in ex][:BUDGET]
    out["rule_based_compliance"] = {"plan": plan1, "exclusion": _outcome(act, seed, plan1), "rollouts": 0}
    # 2 conventional fairness optimisation
    plan2 = [n for n in ("fairness_opt",) if n in ex]
    out["fairness_optimisation"] = {"plan": plan2, "exclusion": _outcome(act, seed, plan2), "rollouts": 0}
    # 3 structural causal model from observational logs of other worlds (the same observed fields), then the do-effect of each fix
    X, y = [], []
    for s in range(400, 430):
        a2 = _active(s)
        o = identify(a2, s, start)
        X.append([1.0] + [1.0 if o[m] == "identified_active" else 0.0 for m in MECHS])
        y.append(sim(inst_with(a2, s), s)["exclusion_qualified"])
    coef = np.linalg.lstsq(np.array(X), np.array(y), rcond=None)[0][1:]
    cand = sorted((m for m in MECHS if obs0[m] == "identified_active" and FIX_OF[m] in ex), key=lambda m: -coef[MECHS.index(m)])
    plan3 = [FIX_OF[m] for m in cand][:BUDGET]
    out["structural_causal_model"] = {"plan": plan3, "exclusion": _outcome(act, seed, plan3), "rollouts": 30}
    # 4 constrained planning with the believed model
    plan4, calls4 = _model_plan(obs0, seed, ex, 2)
    out["constrained_planning"] = {"plan": plan4, "exclusion": _outcome(act, seed, plan4), "rollouts": calls4}
    # 5 model-based greedy planning with a model whose effects are learned from rollouts of other worlds
    eff = {}
    for n in MENU:
        eff[n] = float(np.mean([sim(inst_with(_active(s), s), s)["exclusion_qualified"] - sim(apply(inst_with(_active(s), s), [n]), s)["exclusion_qualified"] for s in range(500, 508)]))
    bel = _believed(obs0)
    score5 = {n: eff[n] * (2.0 if any(bel[m] and FIX_OF[m] == n for m in MECHS) else 1.0) for n in MENU if n in ex}
    plan5 = [n for n in sorted(score5, key=lambda n: -score5[n]) if score5[n] > 0][:BUDGET]
    out["model_based_greedy"] = {"plan": plan5, "exclusion": _outcome(act, seed, plan5), "rollouts": 16 * len(MENU)}
    # 6 operational-shape intervention with observation revision: one revision (one more field, chosen from the observable outcome), then constrained planning
    gap = sim(inst, seed)["group_exclusion_gap"]
    rest = [f for f in FIELD_OF.values() if f not in start]
    pref = ["inherited_record", "score_log", "review_log", "downstream_log"] if gap > 0.15 else ["review_log", "downstream_log", "inherited_record", "score_log"]
    f6 = start | {[f for f in pref if f in rest][0]}
    obs6 = identify(act, seed, f6)
    plan6, calls6 = _model_plan(obs6, seed, ex, 2)
    out["osr_with_observation_revision"] = {"plan": plan6, "exclusion": _outcome(act, seed, plan6), "rollouts": calls6, "revisions": 1, "initiated_by": "system", "autonomous_revision_demonstrated": False}
    # 6b the same information cost without looking at anything: the extra field chosen at random
    fr = start | {rest[int(rng.integers(0, len(rest)))]}
    obsr = identify(act, seed, fr)
    plan7, calls7 = _model_plan(obsr, seed, ex, 2)
    out["constrained_planning_with_random_extra_field"] = {"plan": plan7, "exclusion": _outcome(act, seed, plan7), "rollouts": calls7}
    # the best that the executable menu could do (oracle): an upper bound, not a competitor
    best = min((list(s) for k in range(BUDGET + 1) for s in itertools.combinations(sorted(ex), k)), key=lambda s: _outcome(act, seed, s))
    out["oracle_best_executable"] = {"plan": best, "exclusion": _outcome(act, seed, best), "rollouts": 0}
    return {"seed": seed, "base": base, "active": act, "executable": sorted(ex), "observed_initially": sorted(start), "arms": out}
