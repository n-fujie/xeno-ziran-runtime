"""AI legal governance on a SYNTHETIC institution, built on the source text of the fifteen guarantees (The Minimum Guarantees of Human Legal Subjecthood, V3.0; identical in the 100_POINT_EDITION and in R2 section 4).

What is source and what is this implementation (the two are kept apart, in the data and in every output)
* **Source:** the public specification ``legal_guarantees.json`` carries the fifteen titles, their positions in the source, the number of audit questions, the sub-finding labels, the outcome categories, the evidence tiers and
  the SHA-256 of the three source files (``legal_source.py``). The wording of the source (definitions, audit questions, rules, descriptions) is held in a private store outside this repository; an optional adapter merges it in
  for display when ``XZR_TEOO_PRIVATE_SOURCE`` names a store that matches the public specification. No state, rule, experiment or statistic reads that text. The Low-Score Subject Guarantee Principle (6.1) is a transversal
  rule reported as the separate finding U.
* **Implementation:** the *operational definitions* below — how a synthetic institution's configuration and simulated behaviour are turned into evidence for a finding, and the rules that turn evidence into a state — are this
  implementation's, in the spirit of the source (R2 section 16: SECURED requires affirmative evidence of a usable pathway, not a policy statement; ABSENT is the lack of an operative safeguard; INDETERMINATE preserves missing or
  conflicting evidence; INAPPLICABLE needs a contestable, case-specific reason) and of V3.0 8.2 (a hard failure is a function that is absent, conditioned on the contested score, or practically unusable: an appeal that cannot alter
  the decision, a reviewer without authority, a correction that does not reach downstream recipients). Every finding carries the operational definition; the source definition is shown only where the private store is attached.
* **Limits (V3.0 24.10, 100_POINT_EDITION):** a digital tool may organise evidence, map guarantees and track versions; it must not decide legal legitimacy, rank persons or produce a certification score. Nothing here computes a total.
  The deployment recommendation is advice to the competent human decision maker, from a rule that is this implementation's proposal.

``legal_v1.py`` is the first implementation (a provisional catalogue and a simpler state rule); the experiments EXP-01..10 and CMP-01 were run with it and stay reproducible there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from . import legal_source as LS

CANON: dict = LS.load()
CATALOGUE_STATUS = {"source": CANON["normative_reference"], "verified_against_original": CANON["verified_against_original"], "sha256": {k: v["sha256"] for k, v in CANON["sources"].items()},
                    "editions_identical_for_guarantees": CANON["editions_identical_for_guarantees"], "note": CANON["vocabulary_note"]}
GUARANTEES: tuple[dict, ...] = tuple(CANON["guarantees"])  # definition is None and audit_questions is empty unless the private store is attached
STATES = ("SECURED", "PARTIAL", "ABSENT", "INDETERMINATE", "INAPPLICABLE")
FINDING_IDS = tuple([f"G{i}" for i in range(1, 12)] + ["G12A", "G12B", "G13", "G14", "G15A", "G15B", "G15C", "G15D"])
PARENT = {"G12": ("G12A", "G12B"), "G15": ("G15A", "G15B", "G15C", "G15D")}
RANK = {"SECURED": 0, "PARTIAL": 1, "INDETERMINATE": 2, "ABSENT": 3}  # for a parent finding only: the worst sub-finding, never an average


# ------------------------------------------------------------------------------------------------ evidence and the state rule
@dataclass
class Evidence:
    """What the audit has about one finding. ``exists``: the function is present; ``usable``: it is practically usable by a low-score subject (not a policy statement); ``score_conditioned``: access to it depends on the contested
    score or a derivative (the score-degradation test of Appendix A); ``tier``: the best evidence tier available (1 logs / records, 2 design documents, 3 statements); ``shortfalls``: specific, named shortfalls of an otherwise usable function."""

    exists: bool | None = None
    usable: bool | None = None
    score_conditioned: bool | None = None
    tier: int | None = None
    shortfalls: tuple[str, ...] = ()
    basis: str = ""
    institution_controls_evidence: bool = True


def prov(exists: bool | None = True, usable: bool | None = True, score_conditioned: bool | None = False, tier: int | None = 1, shortfalls: tuple[str, ...] = (), basis: str = "") -> Evidence:
    return Evidence(exists, usable, score_conditioned, tier, shortfalls, basis)


def decide(ev: Evidence | None, applicable: tuple[bool, str] = (True, "")) -> dict:
    """The state of one finding from its evidence, and why. The order of the rules matters and is the order of the source: INAPPLICABLE needs its reason; missing evidence is INDETERMINATE and is never compliance (B.10);
    a function that is absent, conditioned on the score or unusable is ABSENT and a hard failure (8.2); SECURED needs affirmative Tier 1 or 2 evidence that a usable pathway exists and is not score-conditioned (R2 16, B.4)."""
    if not applicable[0]:
        return {"state": "INAPPLICABLE", "hard_failure": False, "reason": applicable[1] + " (the condition is checked against the configuration; a challengeable ground, not a neutral value)", "adverse_inference": False, "evidence_missing": []}
    miss = []
    if ev is None or ev.exists is None:
        miss.append("whether the function exists")
    if ev is not None and ev.exists and ev.usable is None:
        miss.append("whether it is practically usable by a low-score subject (policy alone cannot establish implementation, A.8)")
    if ev is not None and ev.exists and ev.score_conditioned is None:
        miss.append("the score-degradation test")
    if ev is not None and ev.tier is None:
        miss.append("evidence of any tier")
    if ev is not None and ev.tier == 3 and ev.exists:
        miss.append("Tier 1 or 2 evidence (Tier 3 cannot alone establish compliance, B.2)")
    if miss and not (ev is not None and ev.exists is False and ev.tier is not None):
        return {"state": "INDETERMINATE", "hard_failure": False, "reason": "the available evidence does not permit a conclusion; Indeterminate is not compliance (B.10): missing " + "; ".join(miss), "evidence_missing": miss,
                "adverse_inference": bool(ev is None or ev.institution_controls_evidence)}
    assert ev is not None
    if ev.exists is False:
        return {"state": "ABSENT", "hard_failure": True, "reason": "the institution has no operative safeguard of this kind" + (f" ({ev.basis})" if ev.basis else ""), "evidence_missing": [], "adverse_inference": False}
    if ev.score_conditioned:
        return {"state": "ABSENT", "hard_failure": True, "reason": "hard failure: the function is conditioned on the contested score or a derivative (Score-Based Procedural Degradation)" + (f" ({ev.basis})" if ev.basis else ""), "evidence_missing": [], "adverse_inference": False}
    if ev.usable is False:
        return {"state": "ABSENT", "hard_failure": True, "reason": "hard failure: the function exists in form but is practically unusable for what the guarantee requires" + (f" ({ev.basis})" if ev.basis else ""), "evidence_missing": [], "adverse_inference": False}
    if ev.shortfalls:
        return {"state": "PARTIAL", "hard_failure": False, "reason": "usable, with a specific shortfall: " + "; ".join(ev.shortfalls), "evidence_missing": [], "adverse_inference": False}
    return {"state": "SECURED", "hard_failure": False, "reason": "affirmative Tier " + str(ev.tier) + " evidence of a usable pathway that is not score-conditioned" + (f" ({ev.basis})" if ev.basis else ""), "evidence_missing": [], "adverse_inference": False}


def worst(states: list[str]) -> str:
    """A parent finding (G12, G15) from its sub-findings: the most severe; the sub-findings cannot compensate for one another (V3.0 7.6). INAPPLICABLE only if every sub-finding is."""
    live = [s for s in states if s != "INAPPLICABLE"]
    return "INAPPLICABLE" if not live else max(live, key=lambda s: RANK[s])


# ------------------------------------------------------------------------------------------------ legal translation (R2 section 15 and 24; V3.0 4, 13, 18.3)
STAGES = ("technical_event", "data_representation", "legal_fact", "legal_classification", "norm_selection", "exception_handling", "attribution", "burden_of_proof", "legal_decision", "review", "remedy")
LAYER_OF = {"technical_event": "technical", "data_representation": "technical", "legal_fact": "asserted", "legal_classification": "legal", "norm_selection": "legal", "exception_handling": "legal", "attribution": "legal", "burden_of_proof": "legal",
            "legal_decision": "authorised decision", "review": "review", "remedy": "remedy"}


def stage(name: str, *, legal_basis: str | None, jurisdiction: str | None, rule_version: str | None, scope: str, responsible: str, evidence: str, uncertainty: str, authority: str | None, contest_path: str | None,
          transformation_rule: str = "", timestamp: str = "", by_ai: bool = False) -> dict:
    if name not in STAGES:
        raise ValueError(f"stage must be one of {STAGES}")
    return {"stage": name, "layer": LAYER_OF[name], "legal_basis": legal_basis, "jurisdiction": jurisdiction, "rule_version": rule_version, "scope": scope, "responsible": responsible, "evidence": evidence, "uncertainty": uncertainty,
            "authority": authority, "contest_path": contest_path, "transformation_rule": transformation_rule, "timestamp": timestamp, "by_ai": by_ai}


def assess_chain(chain: list[dict]) -> dict:
    """R2 section 15: a machine prediction is neither a legal fact nor an authorised decision; every edge keeps jurisdiction, source authority, rule version, actor, timestamp, evidence provenance, transformation rule, uncertainty and
    objection channel. A legal stage without a legal basis, jurisdiction and rule version is not a valid legal step; an authorised decision needs a human authority and a route to contest; where the applicable law is unclear the answer is an
    unresolved legal question for a competent reviewer, not a silent assumption that the guarantees are enacted law. The layers are never merged: a chain can be inferentially consistent but unauthorised, authorised but unreviewable, corrected but leaving harm downstream."""
    names = [s["stage"] for s in chain]
    issues = [] if names == [s for s in STAGES if s in names] else ["the stages are not in the order of the translation path"]
    rows = []
    for s in chain:
        why, technical = [], s["layer"] == "technical"
        if not technical:
            if not s["legal_basis"]:
                why.append("no legal basis is stated: not a legally valid step")
            if s["legal_basis"] and not (s["jurisdiction"] and s["rule_version"]):
                why.append("the legal basis has no jurisdiction or rule version: an unresolved legal question for a competent reviewer")
        if s["stage"] in ("legal_decision", "review", "remedy"):
            if s["by_ai"] and not s["authority"]:
                why.append("an AI output is not a legal decision: no authorised human decides")
            if not s["authority"]:
                why.append("no decision authority is named")
            if not s["contest_path"]:
                why.append("no route to contest or review is named")
        rows.append({"stage": s["stage"], "layer": s["layer"], "valid": not why, "why_not": why, "uncertainty": s["uncertainty"], "responsible": s["responsible"]})
    first_bad = next((r["stage"] for r in rows if not r["valid"]), None)
    return {"stages": rows, "valid_legal_decision": first_bad is None and "legal_decision" in names and not issues, "first_invalid_stage": first_bad, "issues": issues,
            "unresolved_legal_questions": [r["stage"] for r in rows if any("unresolved" in w for w in r["why_not"])],
            "reading": "a decision whose chain is invalid at a legal stage is not treated as a legally valid decision; the technical stages stand as technical facts; the engine recommends and records, it does not authorise"}


def example_chain(valid: bool = True) -> list[dict]:
    j, v = "synthetic jurisdiction", "rule v1"
    ai = not valid
    return [stage("technical_event", legal_basis=None, jurisdiction=None, rule_version=None, scope="a score is computed", responsible="system operator", evidence="model run log", uncertainty="model error", authority=None, contest_path=None, transformation_rule="score = f(record)"),
            stage("data_representation", legal_basis=None, jurisdiction=None, rule_version=None, scope="applicant record", responsible="data controller", evidence="record digest", uncertainty="input errors", authority=None, contest_path=None, transformation_rule="record -> features"),
            stage("legal_fact", legal_basis="procedure act (placeholder)" if valid else None, jurisdiction=j if valid else None, rule_version=v if valid else None, scope="eligibility facts", responsible="case officer", evidence="documents", uncertainty="facts disputed",
                  authority="case officer", contest_path="notice and reply", transformation_rule="features -> asserted fact"),
            stage("legal_classification", legal_basis="eligibility rule (placeholder)", jurisdiction=j, rule_version=v, scope="class of the applicant", responsible="case officer", evidence="rule and facts", uncertainty="borderline", authority="case officer", contest_path="review"),
            stage("norm_selection", legal_basis="eligibility rule (placeholder)", jurisdiction=j, rule_version=v, scope="norm", responsible="case officer", evidence="statute text", uncertainty="interpretation", authority="case officer", contest_path="review"),
            stage("exception_handling", legal_basis="hardship clause (placeholder)", jurisdiction=j, rule_version=v, scope="exceptions", responsible="case officer", evidence="hardship claim", uncertainty="discretion", authority="case officer", contest_path="review"),
            stage("attribution", legal_basis="responsibility rule (placeholder)", jurisdiction=j, rule_version=v, scope="who answers", responsible="institution", evidence="process record", uncertainty="shared", authority="institution", contest_path="review"),
            stage("burden_of_proof", legal_basis="burden rule (placeholder)", jurisdiction=j, rule_version=v, scope="who proves", responsible="institution", evidence="rule", uncertainty="none", authority="institution", contest_path="review"),
            stage("legal_decision", legal_basis="eligibility rule (placeholder)", jurisdiction=j, rule_version=v, scope="grant or refuse", responsible="authorised official" if valid else "scoring system", evidence="reasons", uncertainty="error rate",
                  authority="authorised official" if valid else None, contest_path="independent review" if valid else None, by_ai=ai),
            stage("review", legal_basis="review rule (placeholder)", jurisdiction=j, rule_version=v, scope="reconsideration", responsible="independent reviewer", evidence="complete record", uncertainty="competence", authority="independent reviewer", contest_path="appeal"),
            stage("remedy", legal_basis="remedy rule (placeholder)", jurisdiction=j, rule_version=v, scope="correction and re-entry", responsible="institution", evidence="corrected record", uncertainty="propagation", authority="reviewer", contest_path="appeal")]


# ------------------------------------------------------------------------------------------------ Translation Register (V3.0 B.7, 13, 18.3): the legal source -> purpose -> variable -> proxy -> threshold -> recipient record
@dataclass
class RegisterEntry:
    variable: str
    legal_source: str | None  # None: no identified authority (discretionary, contractual, organisational convenience)
    purpose: str
    proxy_for: str | None
    threshold: float | None
    translation_loss_disclosed: bool
    recipients: tuple[str, ...] = ()
    version: str = "v1"
    responsible: str = "operator"


def default_register(proxy_gate: bool) -> list[RegisterEntry]:
    reg = [RegisterEntry("score", "eligibility rule (placeholder)", "rank applicants by qualification and resources", None, None, True, ("second institution",))]
    if proxy_gate:
        reg.append(RegisterEntry("inherited_record_gate", None, "refuse applicants with a high inherited record before ranking", "creditworthiness (family / region record)", 1.2, False, ("second institution",)))
    return reg


# ------------------------------------------------------------------------------------------------ the synthetic institution
@dataclass
class Institution:
    """The configuration of a synthetic institution: what the institution does and provides (everything an intervention can change). Fields marked (new) are not in ``legal_v1``."""

    n: int = 300
    periods: int = 24
    capacity: float = 0.4
    tau_score: bool = True
    proxy_gate: bool = True
    lam: float = 0.8
    fairness_opt: bool = False
    downstream_sharing: bool = True
    propagate_correction: bool = False
    appeal: bool = True
    review_capacity: float = 0.15
    review_independent: bool = False
    review_authority: bool = False
    appeal_burden: float = 0.6
    score_expiry: int | None = None
    reentry_support: bool = False
    suspension: bool = False
    harm_irreversible: bool = True
    score_degrades_review: bool = False  # (new) low-score subjects are given a lower chance of being reviewed
    review_delay: int = 0  # (new) periods between a denial being appealed and the decision on the appeal
    record_retention: int = 3  # (new) periods for which the second institution holds a denial that was reversed, unless corrections propagate
    material_relief: bool = False  # (new) a reversed wrongful denial is accompanied by restoration of lost resources
    resources_support: bool = False  # (new) time, language, fee relief, representation: lowers the effort demanded of the subject
    collective_challenge: bool = False  # (new) a collective / systemic challenge route that can change the proxy and the weight of the inherited record
    provisions: dict[str, Evidence] = field(default_factory=dict)  # (new) evidence for the findings that the simulation does not measure (G3-G9)
    registry: list[RegisterEntry] | None = None  # (new) the Translation Register; None: the default for this configuration
    components: dict[str, dict[str, bool | None]] | None = None  # (new, mheg) itemised components of G3, G5, G9 and G15A (True present, False missing, None not observed); None: the single provision as before

    def with_(self, **kw: Any) -> Institution:
        d = {**self.__dict__, "provisions": dict(self.provisions)}
        d.update(kw)
        return Institution(**d)


def simulate(inst: Institution, seed: int, correct_at: int | None = None) -> dict[str, Any]:
    """The synthetic institution over ``periods`` periods (the same world as ``legal_v1.simulate`` plus the (new) mechanisms above). Paired comparisons use the same seed: the same people, the same exogenous noise."""
    rng = np.random.default_rng(seed)
    n, T = inst.n, inst.periods
    m = rng.normal(size=n)
    g = (rng.uniform(size=n) < 0.4).astype(float)
    r = g * 1.0 + rng.normal(0, 0.5, n)
    R = 0.5 * m - 0.5 * g + rng.normal(0, 0.3, n)
    qual = m >= 0.0
    denied_prev = np.zeros(n, bool)
    last_den = np.full(n, -99)
    pending: list[tuple[int, np.ndarray]] = []  # (period when the decision on the appeals falls due, who wins)
    corrected = np.zeros(n, bool)
    den_t = np.full(n, -1)  # first period of the current spell of denial
    qual_denied_hist, tpr_hist, down_hist, ex_g0, ex_g1, access_hist, endo, res_hist = [], [], [], [], [], [], [], []
    appeals_filed = overturned = wrongful_total = reentered = 0
    low_den = low_rev = high_den = high_rev = 0
    ttr: list[int] = []
    excluded0 = None
    lam_now = inst.lam
    for t in range(T):
        lam_t = lam_now if (inst.score_expiry is None or (t % max(1, inst.score_expiry)) != 0 or t == 0) else 0.0
        score = 1.0 * m + 0.8 * R - lam_t * r + rng.normal(0, 0.4, n)
        endo.append(float(np.var(0.8 * R) / max(1e-9, np.var(score))))
        if inst.tau_score:
            key = score
        elif inst.proxy_gate:
            key = -r + rng.normal(0, 0.05, n)
        else:
            key = rng.normal(size=n)
        if inst.proxy_gate and inst.tau_score:
            key = np.where(r > 1.2, -np.inf, key)
        if inst.fairness_opt and inst.tau_score:
            for gv in (0.0, 1.0):
                idx = g == gv
                ranks = key[idx].argsort().argsort() / max(1, int(idx.sum()) - 1)
                key = key.copy()
                key[idx] = np.where(np.isinf(key[idx]), -np.inf, ranks)
        k = int(inst.capacity * n)
        order = np.argsort(-key)
        access = np.zeros(n, bool)
        access[order[:k]] = True
        access &= ~np.isneginf(key) | (not inst.proxy_gate)
        denied_q = qual & ~access
        lo = score < np.quantile(score, 0.3)
        if inst.appeal:
            file_p = 1.0 - inst.appeal_burden * (0.5 if inst.resources_support else 1.0)
            filed = denied_q & (rng.uniform(size=n) < file_p)
            reach = inst.review_capacity * (2.0 if inst.review_independent else 1.0)
            reach_i = np.where(lo & inst.score_degrades_review, reach * 0.4, reach)
            reviewed = filed & (rng.uniform(size=n) < reach_i)
            win = reviewed & (rng.uniform(size=n) < (0.9 if (inst.review_authority and inst.review_independent) else 0.5 if inst.review_authority else 0.0))
            appeals_filed += int(filed.sum())
            wrongful_total += int(denied_q.sum())
            low_den += int((denied_q & lo).sum())
            low_rev += int((reviewed & lo).sum())
            high_den += int((denied_q & ~lo).sum())
            high_rev += int((reviewed & ~lo).sum())
            if inst.review_delay <= 0:
                access = access | win
                corrected |= win
                overturned += int(win.sum())
                ttr += [int(t - den_t[i]) for i in np.where(win & (den_t >= 0))[0]]
            else:
                pending.append((t + inst.review_delay, win))
        due = [p for p in pending if p[0] <= t]
        for _, w in due:
            access = access | w
            corrected |= w
            overturned += int(w.sum())
            ttr += [int(t - den_t[i]) for i in np.where(w & (den_t >= 0))[0]]
            if inst.material_relief:
                R = R + 0.6 * w
        pending = [p for p in pending if p[0] > t]
        if correct_at is not None and t == correct_at:
            fix = qual & ~access
            access = access | fix
            corrected |= fix
        if inst.collective_challenge and t == T // 2:  # a systemic challenge can reach the proxy and the inherited part of the score
            lam_now = lam_now * 0.4
            inst = inst.with_(proxy_gate=False) if inst.proxy_gate else inst
        if inst.downstream_sharing:
            stale = access & (last_den >= 0) & ((t - last_den) <= inst.record_retention) if not inst.propagate_correction else np.zeros(n, bool)
            down_ok = access & ~stale
        else:
            down_ok = access
        down_hist.append(float((down_ok & qual).sum() / max(1, int(qual.sum()))))
        q0, q1 = qual & (g == 0), qual & (g == 1)
        ex_g0.append(float((q0 & ~access).sum() / max(1, int(q0.sum()))))
        ex_g1.append(float((q1 & ~access).sum() / max(1, int(q1.sum()))))
        benefit = down_ok.astype(float)
        R = 0.8 * R + 0.6 * benefit - 0.2 * (1 - benefit) + rng.normal(0, 0.05, n)
        if inst.reentry_support:
            R = R + 0.25 * (~access & qual)
        if inst.suspension:
            R = R + 0.1 * (denied_q & denied_prev)
        reentered += int(((access & denied_prev) & qual).sum())
        den_t = np.where(~access & (den_t < 0), t, np.where(access, -1, den_t))
        denied_prev = ~access
        last_den = np.where(~access, t, last_den)
        access_hist.append(float(access.mean()))
        res_hist.append(float(R[qual].mean()))
        qual_denied_hist.append(float(denied_q.sum() / max(1, int(qual.sum()))))
        a0 = access[q0].mean() if q0.any() else 0.0
        a1 = access[q1].mean() if q1.any() else 0.0
        tpr_hist.append(float(abs(a0 - a1)))
        if t == 0:
            excluded0 = qual & ~access
    last = slice(-4, None)
    return {"exclusion_qualified": float(np.mean(qual_denied_hist[last])), "exclusion_persistence": float((excluded0 & denied_prev).sum() / max(1, int(excluded0.sum()))) if excluded0 is not None else 0.0,
            "tpr_gap": float(np.mean(tpr_hist[last])), "group_exclusion_gap": float(np.mean(ex_g1[last]) - np.mean(ex_g0[last])), "downstream_access_qualified": float(np.mean(down_hist[last])), "access_rate": float(np.mean(access_hist[last])),
            "overturn_rate_of_wrongful": overturned / max(1, wrongful_total), "formal_appeal_rate": appeals_filed / max(1, wrongful_total), "reentered_qualified": reentered,
            "review_rate_low_score": low_rev / max(1, low_den), "review_rate_high_score": high_rev / max(1, high_den), "review_counts": [low_rev, low_den, high_rev, high_den], "time_to_restoration_mean": float(np.mean(ttr)) if ttr else None, "restorations": len(ttr),
            "endogenous_share_of_score": float(np.mean(endo[last])), "mean_resources_qualified": float(np.mean(res_hist[last])), "burden_subject": float(inst.appeal_burden * (0.5 if inst.resources_support else 1.0) * (appeals_filed + 1) / max(1, n)),
            "burden_institution": float(inst.review_capacity * (2 if inst.review_independent else 1) * (1 if inst.review_authority else 0.5)), "series_exclusion": [round(x, 4) for x in qual_denied_hist]}


# ------------------------------------------------------------------------------------------------ the evidence an audit gets from the synthetic institution (Tier 1: the simulation's own logs and its configuration)
OPERATIONAL = {  # the implementation's operational definition of each finding in the synthetic institution (not the source's)
    "G1": "decisions can be altered by individual context (a reviewer with authority) and are not taken on the inherited-record proxy alone",
    "G2": "the review rate of low-score subjects is not lower than that of high-score subjects among wrongfully denied qualified people (measured)",
    "G3": "the configuration provides notice (a provision; usable, not score-conditioned)", "G4": "the configuration provides score access", "G5": "the configuration provides history, expiry, scope and recipient visibility",
    "G6": "every variable of the Translation Register names an identified legal authority", "G7": "every variable of the Translation Register has its proxy, threshold and translation loss disclosed",
    "G8": "the configuration separates fact, inference, score and judgment in records", "G9": "the configuration provides individual reasons and the inferential chain",
    "G10": "a correction reaches the downstream recipient (corrections propagate, or there is no downstream recipient)", "G11": "an appeal exists and, measured, it overturns wrongful denials (>= 0.20 of them: SECURED; > 0: PARTIAL; none: hard failure)",
    "G12A": "the effort demanded of the subject is proportionate (burden <= 0.30 SECURED; <= 0.60 PARTIAL; above: hard failure)", "G12B": "the reviewer has authority and independence (both: SECURED; authority only: PARTIAL; no authority: hard failure)",
    "G13": "adverse treatment can be suspended pending review (applicable only where exclusion can cause irreversible harm)", "G14": "scores expire or are reassessed; the inherited part does not keep the group gap open (measured)",
    "G15A": "minimum resources: time, language, fee relief, representation (resources_support)", "G15B": "cessation, correction, downstream remediation and material relief (propagation and material relief)",
    "G15C": "effective re-entry (re-entry support; measured: people regain access)", "G15D": "mutual audit: a collective / systemic challenge route (collective_challenge)"}


COMPONENTS: dict[str, tuple[str, ...]] = {  # the components of a finding that the specification of this implementation itemises (own wording of what each guarantee asks to be provided); a single yes/no provision can hide a missing one
    "G3": ("responsible_body", "role_of_the_system", "influence_on_the_decision", "expected_consequence", "route_to_contest"),
    "G5": ("creation_and_change_time", "reason_for_change", "model_used", "purpose_of_use", "validity_period", "recipients", "future_use"),
    "G9": ("evidence_used", "variable_transformation", "score_and_threshold", "institutional_rule", "main_inferences", "uncertainty", "rejected_counter_evidence"),
    "G15A": ("time", "comprehensible_information", "language_support", "disability_accommodation", "technical_access", "representation", "fee_relief", "evidence_gathering"),
}


def itemised(fid: str, present: dict[str, bool | None], base: Evidence) -> Evidence:
    """The evidence of a finding from its itemised components. All missing: the function does not exist (ABSENT); some missing: usable with named shortfalls (PARTIAL); a component not observed and none known missing: the
    usability is unknown (INDETERMINATE, never SECURED); all present: the single-provision evidence stands. Itemising can only lower a finding relative to the single provision, never raise it."""
    names = COMPONENTS[fid]
    missing = [n for n in names if present.get(n) is False]
    unknown = [n for n in names if present.get(n) is None]
    if len(missing) == len(names):
        return prov(exists=False, usable=False, basis=f"none of the {len(names)} components of {fid} is provided")
    if missing:
        return prov(exists=base.exists, usable=base.usable, shortfalls=base.shortfalls + tuple(f"component '{n}' is missing" for n in missing), basis=f"{len(names) - len(missing)} of {len(names)} components provided")
    if unknown:
        return Evidence(exists=base.exists, usable=None, score_conditioned=base.score_conditioned, tier=base.tier, shortfalls=base.shortfalls, basis=f"{len(unknown)} of {len(names)} components not observed")
    return base


def evidence_for(inst: Institution, seed: int, run: dict | None = None, min_cases: int = 30) -> dict[str, Evidence | None]:
    """``min_cases``: the smallest number of wrongfully denied qualified people on each side (and of reviews in all) with which the score-degradation test is regarded as having been performed; with fewer, the test is *not performed* (None: INDETERMINATE), never passed. 0 reproduces the first version of this evaluator (LG2-EXP-01..06)."""
    run = run or simulate(inst, seed)
    reg = inst.registry if inst.registry is not None else default_register(inst.proxy_gate)
    P = inst.provisions
    ev: dict[str, Evidence | None] = {}
    # G1 and G2
    short1 = ("the inherited-record proxy gate treats the record as the person before any individual consideration",) if inst.proxy_gate else ()
    ev["G1"] = prov(exists=True, usable=inst.review_authority, score_conditioned=False, shortfalls=short1, basis="a reviewer with authority can alter treatment on contextual evidence" if inst.review_authority else "no one with authority can alter a treatment on individual context")
    lo, hi = run["review_rate_low_score"], run["review_rate_high_score"]
    lr, ld, hr, hd = run["review_counts"]
    pooled = (lr + hr) / max(1, ld + hd)
    se = (pooled * (1 - pooled) * (1 / max(1, ld) + 1 / max(1, hd))) ** 0.5
    degraded: bool | None = bool(hi > 0 and lo < 0.8 * hi and se > 0 and (hi - lo) / se > 1.96)  # a lower review rate that is also larger than chance (two-proportion z > 1.96), not a difference of a few cases
    if min_cases and (ld < min_cases or hd < min_cases or lr + hr < 20) and not degraded:
        degraded = None  # too few cases to have performed the test: an unperformed test is not a passed test
    ev["G2"] = prov(exists=True, usable=True, score_conditioned=degraded, basis=f"review rate of low-score {lo:.3f} against {hi:.3f} for others among wrongfully denied qualified people ({ld} and {hd} cases)")
    for k in ("G3", "G4", "G5", "G8", "G9"):
        ev[k] = P.get(k, prov())
    # G6 and G7 from the Translation Register
    unsourced = [e.variable for e in reg if not e.legal_source]
    ev["G6"] = P.get("G6", prov(exists=True, usable=not unsourced or len(unsourced) < len(reg), shortfalls=tuple(f"variable '{v}' has no identified legal or institutional authority" for v in unsourced) if len(unsourced) < len(reg) else (),
                                basis="Translation Register"))
    undisclosed = [e.variable for e in reg if not e.translation_loss_disclosed]
    ev["G7"] = P.get("G7", prov(exists=True, usable=True, shortfalls=tuple(f"the translation loss of '{v}' (a proxy and threshold) is not disclosed" for v in undisclosed), basis="Translation Register"))
    # G10 correction
    down = inst.downstream_sharing
    ev["G10"] = prov(exists=True, usable=(inst.propagate_correction or not down), basis="downstream recipient " + ("is corrected" if inst.propagate_correction else "still holds the old denial" if down else "does not exist"))
    # G11 contestation
    ov = run["overturn_rate_of_wrongful"]
    ev["G11"] = prov(exists=inst.appeal, usable=ov > 0.0, shortfalls=("few wrongful denials are overturned",) if 0 < ov < 0.2 else (), basis=f"appeals file at {run['formal_appeal_rate']:.2f} of wrongful denials and {ov:.3f} are overturned")
    # G12A / G12B
    eff_burden = inst.appeal_burden * (0.5 if inst.resources_support else 1.0)
    ev["G12A"] = prov(exists=True, usable=eff_burden <= 0.6, shortfalls=("the effort demanded of the subject is substantial",) if 0.3 < eff_burden <= 0.6 else (), basis=f"effort demanded of the subject {eff_burden:.2f}")
    ev["G12B"] = prov(exists=inst.appeal, usable=inst.review_authority, shortfalls=("the reviewer has authority but is not independent of the system",) if inst.review_authority and not inst.review_independent else (), basis="reviewer authority and independence")
    # G13 suspension
    ev["G13"] = prov(exists=inst.suspension, usable=inst.suspension, basis="suspension pending review")
    # G14 temporal
    gap = run["group_exclusion_gap"]
    ev["G14"] = prov(exists=inst.score_expiry is not None, usable=True, shortfalls=("the inherited part of the score keeps the group gap open despite expiry",) if inst.score_expiry is not None and gap > 0.3 else (), basis="expiry / reassessment")
    ev["G15A"] = prov(exists=inst.resources_support, usable=inst.resources_support, basis="resources to use the procedure")
    ev["G15B"] = prov(exists=True, usable=inst.propagate_correction or not down, shortfalls=() if inst.material_relief else ("no restoration of lost resources accompanies a reversed denial",), basis="downstream correction and material relief")
    ev["G15C"] = prov(exists=inst.reentry_support, usable=inst.reentry_support and run["reentered_qualified"] > 0, basis="re-entry support")
    ev["G15D"] = prov(exists=inst.collective_challenge, usable=inst.collective_challenge, basis="collective / systemic challenge")
    for fid, comps in (inst.components or {}).items():
        if fid in COMPONENTS and ev.get(fid) is not None:
            ev[fid] = itemised(fid, comps, ev[fid])  # type: ignore[arg-type]
    return ev


def applicability(inst: Institution) -> dict[str, tuple[bool, str]]:
    app = {k: (True, "") for k in FINDING_IDS}
    if not inst.harm_irreversible:
        app["G13"] = (False, "exclusion in this institution cannot cause irreversible or disproportionate harm, so suspension pending review is not required")
    return app


def audit(inst: Institution, seed: int = 0, observed: set[str] | None = None, evidence: dict[str, Evidence | None] | None = None, min_cases: int = 30) -> dict:
    """The audit of a synthetic institution: one finding for each of G1-G15 (G12 and G15 from their sub-findings, which are also reported), the separate finding U (the Low-Score Subject Guarantee Principle), the outcome
    taxonomy, and an advisory deployment recommendation. ``observed``: the findings that this audit has evidence for (None = all); an unobserved finding is INDETERMINATE, not ABSENT. No total is computed."""
    run = simulate(inst, seed)
    ev = evidence if evidence is not None else evidence_for(inst, seed, run, min_cases)
    app = applicability(inst)
    sub: dict[str, dict] = {}
    for fid in FINDING_IDS:
        e = None if (observed is not None and fid not in observed) else ev.get(fid)
        d = decide(e, app[fid])
        if observed is not None and fid not in observed and app[fid][0]:
            d["reason"] = "the finding is not observed by this audit: not observed is not absent; " + d["reason"]
        sub[fid] = {**d, "id": fid, "evidence_tier": None if e is None else e.tier, "evidence_basis": None if e is None else e.basis, "formal_exists": None if e is None else e.exists, "operational_definition": OPERATIONAL[fid]}
    gnum = {g["number"]: g for g in GUARANTEES}
    findings = []
    for i in range(1, 16):
        key = f"G{i}"
        subs = [sub[s] for s in PARENT[key]] if key in PARENT else [sub[key]]
        state = worst([s["state"] for s in subs]) if key in PARENT else sub[key]["state"]
        hard = any(s["hard_failure"] for s in subs)
        why = "; ".join(f"{s['id']}: {s['reason']}" for s in subs) if key in PARENT else sub[key]["reason"]
        remedy = "" if state in ("SECURED", "INAPPLICABLE") else ("; ".join(f"{s['id']}: " + _remedy(s) for s in subs if s["state"] not in ("SECURED", "INAPPLICABLE")) if key in PARENT else _remedy(sub[key]))
        findings.append({"number": i, "id": key, "title": gnum[i]["title"], "definition": gnum[i]["definition"], "source_position": gnum[i]["source_position"], "audit_questions": gnum[i]["audit_questions"], "audit_question_count": gnum[i]["audit_question_count"],
                         "operational_definition": " | ".join(f"{s['id']}: {s['operational_definition']}" for s in subs), "state": state, "hard_failure": hard, "reason": why, "remedy_path": remedy,
                         "formal_exists": any(bool(s["formal_exists"]) for s in subs), "sub_findings": [{k: s[k] for k in ("id", "state", "hard_failure", "reason", "operational_definition", "evidence_tier", "evidence_basis", "formal_exists")} for s in subs] if key in PARENT else [],
                         "evidence_missing": sorted({m for s in subs for m in s["evidence_missing"]}), "adverse_inference_available": any(s["adverse_inference"] for s in subs), "applicable": all(s["state"] != "INAPPLICABLE" for s in subs),
                         "catalogue_verified": CATALOGUE_STATUS["verified_against_original"]})
    u = _finding_u(ev, sub)
    return {"findings": findings, "sub_findings": [sub[s] for s in FINDING_IDS if s in ("G12A", "G12B", "G15A", "G15B", "G15C", "G15D")], "U": u, "outcome_taxonomy": outcome_taxonomy(findings, sub, u), "run": {k: v for k, v in run.items() if k != "series_exclusion"},
            "recommendation": recommend(findings, sub, u), "no_total": "no aggregate, average, weighted score, rank or pass percentage is computed (A.3, 8.4); a failed guarantee is not offset by another"}


def _remedy(s: dict) -> str:
    if s["state"] == "INDETERMINATE":
        return "produce the missing evidence (the institution controls it; absent a good reason the burden stays with it, B.10)"
    return {"G1": "let a person with authority alter treatment on context; drop the proxy gate", "G2": "remove every score-conditioned difference in procedure", "G10": "propagate corrections to every recipient",
            "G11": "give the appeal route the power to alter the decision", "G12A": "move the evidential burden to the institution and reduce the demands on the subject", "G12B": "give an independent reviewer authority to depart from the system", "G13": "establish timely suspension pending review",
            "G14": "establish expiry and reassessment; audit the feedback loop", "G15A": "provide time, language, fee relief and representation", "G15B": "propagate correction and restore what was lost", "G15C": "establish effective re-entry", "G15D": "establish collective and systemic challenge"}.get(s["id"], f"establish an operative, usable, score-independent {s['id']}")


def _finding_u(ev: dict[str, Evidence | None], sub: dict[str, dict]) -> dict:
    """U: the Low-Score Subject Guarantee Principle as a separate finding (A.9): is any guarantee conditioned on a score or a derivative? A failure of any test is Score-Based Procedural Degradation."""
    tested = {k: e.score_conditioned for k, e in ev.items() if e is not None and e.exists}
    failed = [k for k, v in tested.items() if v]
    untested = [k for k in FINDING_IDS if sub[k]["state"] != "INAPPLICABLE" and (ev.get(k) is None or ev[k].score_conditioned is None)]  # type: ignore[union-attr]
    if failed:
        return {"state": "ABSENT", "hard_failure": True, "reason": "Score-Based Procedural Degradation: access to " + ", ".join(failed) + " depends on the contested score or a derivative", "failed_in": failed, "untested": untested}
    if untested:
        return {"state": "INDETERMINATE", "hard_failure": False, "reason": "the score-degradation test was not performed for " + ", ".join(untested), "failed_in": [], "untested": untested}
    return {"state": "SECURED", "hard_failure": False, "reason": "no tested guarantee is conditioned on a score or a derivative", "failed_in": [], "untested": []}


def outcome_taxonomy(findings: list[dict], sub: dict[str, dict], u: dict) -> dict:
    """The non-aggregative legal outcome taxonomy of V3.0 8.6, as the categories whose defining finding is present (the assignment of guarantees to categories is this implementation's reading of the five definitions)."""
    st = {f["id"]: f["state"] for f in findings} | {k: v["state"] for k, v in sub.items()}
    bad = lambda ids: [i for i in ids if st.get(i) == "ABSENT"]  # noqa: E731
    cats = {"constitutive_failure": bad(["G1", "G2", "G6"]) + (["U"] if u["state"] == "ABSENT" else []),
            "procedural_failure": bad(["G3", "G4", "G5", "G7", "G8", "G9", "G11", "G12A", "G12B", "G13"]), "remedial_failure": bad(["G10", "G15B", "G15C"]),
            "systemic_failure": bad(["G15D", "G14"]) + [i for i in ("G7",) if st.get(i) == "PARTIAL"], "indeterminate_findings": [i for i, s in st.items() if s == "INDETERMINATE"]}
    return {k: v for k, v in cats.items()} | {"definitions": {k: CANON["outcome_text"].get(k) for k in CANON["outcome_taxonomy"]}}


def recommend(findings: list[dict], sub: dict[str, dict], u: dict) -> dict:
    """An ADVISORY recommendation for the competent human decision maker, one of four options (continue with monitoring; continue under time-limited corrective conditions; suspend the use; withdraw and redesign).
    The rule is this implementation's own proposal, loosely following the order of severity of V3.0 8.4 and 8.6: the software does not decide legal legitimacy."""
    st = {f["id"]: f for f in findings}
    tax = outcome_taxonomy(findings, sub, u)
    hard_suspend = [i for i in ("G3", "G6", "G11", "G12B", "G15B", "G15C") if (sub[i]["state"] == "ABSENT" if i in sub else False)]
    if tax["constitutive_failure"]:
        rec = "withdraw and redesign"
    elif hard_suspend or tax["procedural_failure"] or tax["remedial_failure"]:
        rec = "suspend the relevant use"
    elif any(f["state"] in ("PARTIAL", "INDETERMINATE") for f in st.values()):
        rec = "continue subject to time-limited corrective conditions"
    else:
        rec = "continue with monitored compliance"
    return {"candidate": rec, "advisory_only": True, "decided_by": "the competent human decision maker (court, regulator, procurement body or institution)", "rule_source": "implementation proposal grounded in V3.0 8.4 and 8.6", "hard_failures": [f["id"] for f in st.values() if f["hard_failure"]] + (["U"] if u["hard_failure"] else [])}


def audit_integrity(report: dict, history: list[dict] | None = None) -> dict:
    """The five self-application controls of V3.0 24.7, as this implementation checks them: (1) no person is scored for the ability to exercise the guarantees; (2) a failed or incomplete audit is not turned into
    a presumption against affected persons; (3) the evidence limits are disclosed; (4) the finding can be challenged; (5) formal compliance that coexists with recurring practical failure triggers revision of the framework itself."""
    forbidden = ("score", "total", "rank", "average", "weighted", "percentage")
    keys = {k.lower() for f in report["findings"] for k in f} | {k.lower() for k in report}
    # (5) recurring practical failure of functions that exist in form: in at least two audits, some finding whose function is formally present is a hard failure
    hist = history or []
    revise = len(hist) >= 2 and sum(any(f["formal_exists"] and f["state"] == "ABSENT" and f["hard_failure"] for f in h["findings"]) for h in hist) >= 2
    return {"no_person_scored": not any(k in ("person_score", "credibility", "cooperativeness") for k in keys), "no_total": not any(k in ("total", "rank", "average", "weighted", "percentage", "legitimacy_score", "compliance_score") for k in keys) and "no_total" in report,
            "no_presumption_against_persons": all(f["state"] != "INDETERMINATE" or not f.get("presumption_against_person", False) for f in report["findings"]),
            "evidence_limits_disclosed": all("evidence_missing" in f for f in report["findings"]), "challenge_route": "counter-audit by the affected person, a representative organisation, a regulator or a court (B.13)",
            "framework_revision_trigger": revise, "forbidden_words_checked": list(forbidden)}


def ontological_inheritance_finding(inst: Institution, seed: int = 0, lineage_produced: bool = True) -> dict:
    """A.6.1 (100_POINT_EDITION): required finding — no inheritance identified; identified with effective / partial / no safeguards; or indeterminate because the institution has not produced the lineage and treatment records. Inheritance is
    identified when the inherited record enters the score (lambda > 0) or later data produced under the treatment carry a material share of the score (endogenous share), and the data cross to a second institution. Safeguards: expiry of the
    inherited part, propagation of corrections, and a collective challenge route (Endogeneity Presumption, 24.3)."""
    if not lineage_produced:
        return {"finding": "indeterminate", "reason": "the institution has not produced the lineage and treatment records; the evidential burden stays with it and adverse treatment should be suspended (A.7 / B.10)"}
    run = simulate(inst, seed)
    present = (inst.lam > 0 and inst.tau_score) or run["endogenous_share_of_score"] > 0.15
    if not (present and (inst.downstream_sharing or inst.proxy_gate)):
        return {"finding": "no inheritance identified", "endogenous_share": run["endogenous_share_of_score"]}
    safeguards = [inst.score_expiry is not None, inst.propagate_correction or not inst.downstream_sharing, inst.collective_challenge]
    kind = "identified with effective safeguards" if all(safeguards) else "identified with partial safeguards" if any(safeguards) else "identified without safeguards"
    return {"finding": kind, "safeguards": {"expiry": safeguards[0], "propagation": safeguards[1], "collective_challenge": safeguards[2]}, "endogenous_share": run["endogenous_share_of_score"], "group_exclusion_gap": run["group_exclusion_gap"]}


# ------------------------------------------------------------------------------------------------ the bundle that View I reads
def baseline_institution() -> Institution:
    return Institution(capacity=0.4, lam=0.8, review_capacity=0.15)


def repaired_institution() -> Institution:
    return baseline_institution().with_(review_independent=True, review_authority=True, review_capacity=0.3, appeal_burden=0.2, propagate_correction=True, proxy_gate=False, lam=0.0, score_expiry=4, reentry_support=True, suspension=True,
                                        resources_support=True, material_relief=True, collective_challenge=True, registry=default_register(False))


def legal_bundle(seed: int = 3) -> dict:
    base, fixed = baseline_institution(), repaired_institution()
    degraded = base.with_(score_degrades_review=True, review_authority=True, review_independent=True, review_capacity=0.3)
    arms = {"baseline": base, "fairness optimisation only": base.with_(fairness_opt=True), "gate removed": base.with_(proxy_gate=False), "score deleted": base.with_(tau_score=False), "score deleted and gate removed": base.with_(tau_score=False, proxy_gate=False),
            "independent review with authority and propagation": base.with_(review_independent=True, review_authority=True, review_capacity=0.3, appeal_burden=0.2, propagate_correction=True), "all repairs": fixed}
    runs = {k: simulate(v, seed) for k, v in arms.items()}
    observed = {f for i, f in enumerate(FINDING_IDS) if i % 4 != 3}
    audits = {"baseline institution (a formal appeal that can reverse nothing, a proxy gate, no downstream correction)": audit(base, seed), "after the repairs": audit(fixed, seed),
              "low-score subjects are reviewed less often (a reviewer with authority exists)": audit(degraded, seed), "baseline, with some findings not observed": audit(base, seed, observed=observed),
              "an institution for which irreversible harm is impossible": audit(base.with_(harm_irreversible=False), seed)}
    return {"synthetic": True, "catalogue": CATALOGUE_STATUS, "states": list(STATES), "guarantees": [{k: g[k] for k in ("number", "title", "definition", "source_position", "audit_questions", "audit_question_count")} for g in GUARANTEES],
            "sub_finding_definitions": {k: CANON["sub_finding_text"].get(k, lab) for k, lab in CANON["sub_findings"].items()}, "assessments": {k: v["findings"] for k, v in audits.items()}, "audits": {k: {kk: vv for kk, vv in v.items() if kk != "findings"} for k, v in audits.items()},
            "chains": {"valid": {"chain": example_chain(True), "assessment": assess_chain(example_chain(True))}, "decided by the scoring system": {"chain": example_chain(False), "assessment": assess_chain(example_chain(False))}},
            "register": {"baseline": [e.__dict__ for e in default_register(True)], "after the repairs": [e.__dict__ for e in default_register(False)]},
            "interventions": {k: {m: v[m] for m in ("exclusion_qualified", "exclusion_persistence", "tpr_gap", "group_exclusion_gap", "downstream_access_qualified", "overturn_rate_of_wrongful", "formal_appeal_rate", "burden_subject", "burden_institution", "series_exclusion")}
                              for k, v in runs.items()},
            "inheritance": {"baseline": ontological_inheritance_finding(base, seed), "after the repairs": ontological_inheritance_finding(fixed, seed), "lineage not produced": ontological_inheritance_finding(base, seed, lineage_produced=False)},
            "observed_by_assessment": {k: (sorted(observed) if "not observed" in k else None) for k in audits}, "observation": {"observed_findings": sorted(observed), "not_observed_findings": sorted(set(FINDING_IDS) - observed), "note": "a finding that is not observed is INDETERMINATE: not observed is not absent"},
            "software_limit": CANON["software_limit"],
            "text_available": CANON["text_available"], "scope": "a synthetic institution; the guarantees' titles are the source titles (V3.0 6.2, identical in the 100_POINT_EDITION and R2) and their wording is held privately; the operational definitions, the evidence rules and the recommendation rule are this implementation's; "
                     "no real institution, law or person is described; the software does not decide legal legitimacy", "seed": seed}
