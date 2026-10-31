"""AI legal governance, as a SYNTHETIC institution that can be observed, intervened on and assessed (a research module on top of TEOO; it imports nothing else from ``xzr``).

What is here, and what it is not
* ``GUARANTEES``: the fifteen guarantees of the catalogue in ``legal_guarantees.json``. **That catalogue is provisional**: it was copied from an earlier implementation (plato-audit-suite) because the originals (the Minimum
  Guarantees of Human Legal Subjecthood V3.0 / 100_POINT_EDITION, MHEG, the fifteen principles) were not found; it has not been compared with them, so names, definitions and independence are unverified. The twelve MHEG
  guarantees, the fifteen guarantees of legal subjecthood and the fifteen principles of governance are three different lists and are not conflated here: only the first fifteen-item list below is present.
* ``simulate``: a small synthetic institution (people with a latent qualification, an inherited record, resources that feed back into the score; a capacity-limited decision on a score or, when the score is deleted, on a
  proxy; a downstream institution that inherits data; appeals with a reviewer). It is a model for *comparing configurations*, not a model of any real institution or law.
* ``assess_guarantees``: one state per guarantee (SECURED / PARTIAL / ABSENT / INDETERMINATE / INAPPLICABLE), from what the institution provides (formal provision) and what the simulation shows it does (effectiveness).
  The fifteen are never combined into one score; INAPPLICABLE needs a reason that is checked against the configuration; a guarantee whose evidence is not observed is INDETERMINATE, never ABSENT.
  The mapping from a guarantee to its indicators is this implementation's operationalisation, not the paper's.
* ``LegalTranslation``: the path technical event -> data representation -> legal fact -> legal classification -> norm selection -> exception handling -> attribution -> burden of proof -> legal decision -> remedy; a stage
  without a legal basis is not a legally valid stage, and an AI output is never the final authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

_CAT = json.loads((Path(__file__).with_name("legal_guarantees.json")).read_text())
CATALOGUE_STATUS = {"source": _CAT["source"], "verified_against_original": _CAT["verified_against_original"], "note": _CAT["note"]}
GUARANTEES: tuple[dict, ...] = tuple(_CAT["guarantees"])
STATES = ("SECURED", "PARTIAL", "ABSENT", "INDETERMINATE", "INAPPLICABLE")

# the provisions an institution may make (formal provision); each guarantee is assessed from one of them
PROVISIONS = ("person_not_score", "procedures_independent_of_score", "ai_use_notice", "score_access", "history_access", "legal_source_access", "variable_access", "fact_inference_separation", "individual_reasons",
              "correction", "contestation", "human_review", "suspension", "expiry_reassessment", "reentry_support")
GUARANTEE_PROVISION = dict(zip(range(1, 16), PROVISIONS, strict=True))


@dataclass
class Institution:
    """The configuration of a synthetic institution (everything an intervention can change)."""

    n: int = 300
    periods: int = 24
    capacity: float = 0.4  # the share of people that can be served in a period
    tau_score: bool = True  # decisions use the score
    proxy_gate: bool = True  # the inherited record is used as a gate / as the fallback ranking
    lam: float = 0.8  # weight of the inherited record in the score (score inheritance)
    fairness_opt: bool = False  # per-group thresholds equalise the true-positive rate of the score
    downstream_sharing: bool = True  # a second institution inherits the first one's records
    propagate_correction: bool = False  # a correction at the first institution reaches the second
    appeal: bool = True  # appeals exist formally
    review_capacity: float = 0.15  # share of the denied-qualified that a reviewer can reach per period
    review_independent: bool = False
    review_authority: bool = False  # the reviewer can reverse the outcome
    appeal_burden: float = 0.6  # the effort asked of the subject (0 = none, 1 = prohibitive)
    score_expiry: int | None = None  # periods after which the inherited part of the score is dropped
    reentry_support: bool = False  # a support route back for people who were excluded
    suspension: bool = False  # adverse treatment can be suspended while review is pending
    provisions: dict[str, bool | None] = field(default_factory=lambda: {p: True for p in PROVISIONS})
    harm_irreversible: bool = True  # whether exclusion here can cause harm that cannot be undone (the applicability of suspension)

    def with_(self, **kw: Any) -> Institution:
        d = {**self.__dict__, "provisions": dict(self.provisions)}
        d.update(kw)
        return Institution(**d)


def simulate(inst: Institution, seed: int, correct_at: int | None = None) -> dict[str, Any]:
    """Run the institution for ``inst.periods`` periods. Returns outcome series and probes. ``correct_at``: a period at which all wrongful denials are corrected (used by the restoration experiment)."""
    rng = np.random.default_rng(seed)
    n, T = inst.n, inst.periods
    m = rng.normal(size=n)  # latent qualification (the truth the institution tries to serve)
    g = (rng.uniform(size=n) < 0.4).astype(float)  # the disadvantaged group
    r = g * 1.0 + rng.normal(0, 0.5, n)  # the inherited record (family / region / class)
    R = 0.5 * m - 0.5 * g + rng.normal(0, 0.3, n)  # resources
    qual = m >= 0.0
    denied_prev = np.zeros(n, bool)
    access_hist, qual_denied_hist, tpr_gap_hist, gate_ex = [], [], [], []
    ex_g0, ex_g1, deny_hi, deny_lo, corr_sr, mism = [], [], [], [], [], []
    appeals_filed = overturned = wrongful_total = 0
    down_ok_hist = []
    restored: list[float] = []
    since_denied = np.zeros(n)
    last_den = np.full(n, -99)
    corrected = np.zeros(n, bool)
    low_cap = high_cap = 0.0
    low_n = high_n = 0
    reentered = 0
    excluded0 = None
    for t in range(T):
        lam_t = inst.lam if (inst.score_expiry is None or (t % max(1, inst.score_expiry)) != 0 or t == 0) else 0.0
        score = 1.0 * m + 0.8 * R - lam_t * r + rng.normal(0, 0.4, n)
        if inst.tau_score:
            key = score
        elif inst.proxy_gate:
            key = -r + rng.normal(0, 0.05, n)  # the score is deleted: the proxy takes its place
        else:
            key = rng.normal(size=n)  # neither: a lottery
        if inst.proxy_gate and inst.tau_score:
            key = np.where(r > 1.2, -np.inf, key)  # a gate: a high inherited record is refused before ranking
        if inst.fairness_opt and inst.tau_score:  # per-group thresholds that equalise the true-positive rate: rank within group
            for gv in (0.0, 1.0):
                idx = g == gv
                ranks = key[idx].argsort().argsort() / max(1, int(int(idx.sum())) - 1)
                key = key.copy()
                key[idx] = np.where(np.isinf(key[idx]), -np.inf, ranks + (1.0 if gv else 0.0) * 0.0)
        k = int(inst.capacity * n)
        order = np.argsort(-key)
        access = np.zeros(n, bool)
        access[order[:k]] = True
        access &= ~np.isneginf(key) | (not inst.proxy_gate)
        # appeals: wrongful denials (qualified and denied) may be reviewed
        denied_q = qual & ~access
        if inst.appeal:
            file_p = 1.0 - inst.appeal_burden
            filed = denied_q & (rng.uniform(size=n) < file_p)
            reach = inst.review_capacity * (1.0 if (m >= 0).all() else 1.0)
            reviewed = filed & (rng.uniform(size=n) < reach * (2.0 if inst.review_independent else 1.0))
            win = reviewed & (rng.uniform(size=n) < (0.9 if (inst.review_authority and inst.review_independent) else 0.5 if inst.review_authority else 0.0))
            appeals_filed += int(filed.sum())
            overturned += int(win.sum())
            wrongful_total += int(denied_q.sum())
            access = access | win
            corrected = corrected | win
            # procedures independent of score: the reach for low-score subjects is lower unless the provision holds
            if not inst.provisions.get("procedures_independent_of_score"):
                access = access & ~(win & (score < np.quantile(score, 0.3)) & (rng.uniform(size=n) < 0.6))
        if correct_at is not None and t == correct_at:
            fix = qual & ~access
            access = access | fix
            corrected = corrected | fix
        # the downstream institution: it holds the records of the first; a correction reaches it only if corrections propagate
        if inst.downstream_sharing:
            stale = access & (last_den >= 0) & ((t - last_den) <= 3) if not inst.propagate_correction else np.zeros(n, bool)  # the second institution still holds the old denial for three periods
            down_ok = access & ~stale
        else:
            down_ok = access
        down_ok_hist.append(float((down_ok & qual).sum() / max(1, int(qual.sum()))))
        q0, q1 = qual & (g == 0), qual & (g == 1)
        ex_g0.append(float((q0 & ~access).sum() / max(1, int(q0.sum()))))
        ex_g1.append(float((q1 & ~access).sum() / max(1, int(q1.sum()))))
        hi, lo_r = qual & (r > 1.0), qual & (r <= 1.0)
        deny_hi.append(float((hi & ~access).sum() / max(1, int(hi.sum()))))
        deny_lo.append(float((lo_r & ~access).sum() / max(1, int(lo_r.sum()))))
        corr_sr.append(float(np.corrcoef(score, r)[0, 1]))
        mism.append(float((access & qual & ~down_ok).sum() / max(1, int((access & qual).sum()))))
        # resources feed back into next period's score
        benefit = down_ok.astype(float)
        R = 0.8 * R + 0.6 * benefit - 0.2 * (1 - benefit) + rng.normal(0, 0.05, n)
        if inst.reentry_support:
            R = R + 0.25 * (~access & qual)  # a support route restores part of what exclusion took
        if inst.suspension:
            R = R + 0.1 * (denied_q & denied_prev)  # harm is limited while a review is pending
        newly = access & denied_prev
        reentered += int((newly & qual).sum())
        denied_prev = ~access
        access_hist.append(float(access.mean()))
        qual_denied_hist.append(float(denied_q.sum() / max(1, int(qual.sum()))))
        a0, a1 = access[qual & (g == 0)].mean() if (qual & (g == 0)).any() else 0.0, access[qual & (g == 1)].mean() if (qual & (g == 1)).any() else 0.0
        tpr_gap_hist.append(float(abs(a0 - a1)))
        gate_ex.append(float(((r > 1.2) & qual & ~access).sum() / max(1, int(qual.sum()))))
        if t == 0:
            excluded0 = qual & ~access
        lo = score < np.quantile(score, 0.3)
        low_cap += float((filed & lo).sum()) if inst.appeal else 0.0
        low_n += int((denied_q & lo).sum())
        high_cap += float((filed & ~lo).sum()) if inst.appeal else 0.0
        high_n += int((denied_q & ~lo).sum())
        since_denied = np.where(access, 0, since_denied + 1)
        last_den = np.where(~access, t, last_den)
        _ = restored
    w = slice(-4, None)
    still = float(np.mean([(qual_denied_hist[i]) for i in range(T)][w]))
    persist = float((excluded0 & denied_prev).sum() / max(1, int(excluded0.sum()))) if excluded0 is not None else 0.0
    inherited_gap = float(np.mean(access_hist[w]))
    probes = {"excl_g0": float(np.mean(ex_g0[w])), "excl_g1": float(np.mean(ex_g1[w])), "deny_highr": float(np.mean(deny_hi[w])), "deny_lowr": float(np.mean(deny_lo[w])), "corr_score_r": float(np.mean(corr_sr[w])),
              "downstream_mismatch": float(np.mean(mism[w]))}
    probes["group_exclusion_gap"] = probes["excl_g1"] - probes["excl_g0"]
    return {**probes, "exclusion_qualified": still, "exclusion_persistence": persist, "tpr_gap": float(np.mean(tpr_gap_hist[w])), "access_rate": inherited_gap, "gate_exclusion": float(np.mean(gate_ex[w])),
            "downstream_access_qualified": float(np.mean(down_ok_hist[w])), "series_exclusion": [round(x, 4) for x in qual_denied_hist], "appeals_filed": appeals_filed, "overturned": overturned, "wrongful_denials": wrongful_total,
            "overturn_rate_of_wrongful": overturned / max(1, wrongful_total), "formal_appeal_rate": appeals_filed / max(1, wrongful_total),
            "low_score_filing_share": (low_cap / low_n) if low_n else None, "high_score_filing_share": (high_cap / high_n) if high_n else None,
            "reentered_qualified": reentered, "burden_subject": float(inst.appeal_burden * (appeals_filed + 1) / max(1, n)),
            "burden_institution": float(inst.review_capacity * (2 if inst.review_independent else 1) * (1 if inst.review_authority else 0.5))}


# ------------------------------------------------------------------------------------------------ the fifteen guarantees: one state each, never one score
def assess_guarantees(inst: Institution, seed: int = 0, observed: set[str] | None = None) -> list[dict]:
    """The state of each guarantee. ``observed``: the provisions this assessment can see (None = all); an unobserved provision gives INDETERMINATE, not ABSENT."""
    base = simulate(inst, seed)
    # the effectiveness of what is provided, measured from the simulation
    eff = {
        "person_not_score": 1.0 - base["gate_exclusion"] / max(1e-9, 0.25) if inst.proxy_gate else 1.0,
        "procedures_independent_of_score": 1.0 if (base["low_score_filing_share"] is None or base["high_score_filing_share"] is None) else min(1.0, (base["low_score_filing_share"] + 1e-9) / (base["high_score_filing_share"] + 1e-9)),
        "correction": 1.0 if inst.propagate_correction else 0.0,
        "contestation": base["overturn_rate_of_wrongful"] / 0.2,
        "human_review": 1.0 if (inst.review_independent and inst.review_authority) else 0.5 if inst.review_authority else 0.0,
        "suspension": 1.0 if inst.suspension else 0.0,
        "expiry_reassessment": 1.0 if inst.score_expiry else 0.0,
        "reentry_support": 1.0 if inst.reentry_support else 0.0,
    }
    out = []
    for gnum, prov in GUARANTEE_PROVISION.items():
        meta = _CAT["guarantees"][gnum - 1]
        have = inst.provisions.get(prov)
        e = eff.get(prov)
        reason, applicable, remedy = "", True, ""
        if prov == "suspension" and not inst.harm_irreversible:
            state, applicable = "INAPPLICABLE", False
            reason = "exclusion here cannot cause irreversible harm (harm_irreversible is false), so suspension pending review is not needed; this condition is checked against the configuration"
        elif observed is not None and prov not in observed:
            state, reason = "INDETERMINATE", f"the provision '{prov}' is not observed by this assessment: not observed is not absent"
        elif have is None:
            state, reason = "INDETERMINATE", f"the institution's provision '{prov}' is unknown"
        elif not have:
            state, reason = "ABSENT", f"the institution makes no provision '{prov}'"
            remedy = f"establish '{prov}'"
        elif e is None:
            state, reason = "SECURED", f"the provision '{prov}' exists; no effectiveness indicator applies, so existence is all that can be shown"
        elif e >= 0.8:
            state, reason = "SECURED", f"provided and effective: indicator {e:.2f} >= 0.80 in the simulation"
        elif e > 0.0:
            state, reason = "PARTIAL", f"provided but only partly effective: indicator {e:.2f}"
            remedy = f"make '{prov}' effective (independence, authority, capacity, propagation)"
        else:
            state, reason = "PARTIAL", f"provided in form, no effect shown: indicator {e:.2f}"
            remedy = f"make '{prov}' effective (independence, authority, capacity, propagation)"
        out.append({"number": gnum, "title": meta["title"], "provision": prov, "applicable": applicable, "required_evidence": f"provision '{prov}' and, where it applies, its measured effectiveness", "institutional_function": meta["description"],
                    "state": state, "reason": reason, "remedy_path": remedy, "effectiveness_indicator": None if e is None else round(float(e), 3), "catalogue_verified": _CAT["verified_against_original"]})
    return out


# ------------------------------------------------------------------------------------------------ legal translation chain
STAGES = ("technical_event", "data_representation", "legal_fact", "legal_classification", "norm_selection", "exception_handling", "attribution", "burden_of_proof", "legal_decision", "remedy")


def stage(name: str, *, legal_basis: str | None, scope: str, responsible: str, evidence: str, uncertainty: str, authority: str | None, contest_path: str | None, by_ai: bool = False) -> dict:
    if name not in STAGES:
        raise ValueError(f"stage must be one of {STAGES}")
    return {"stage": name, "legal_basis": legal_basis, "scope": scope, "responsible": responsible, "evidence": evidence, "uncertainty": uncertainty, "authority": authority, "contest_path": contest_path, "by_ai": by_ai}


def assess_chain(chain: list[dict]) -> dict:
    """Which stages are legally valid. A stage with no legal basis is not a valid legal step (it may be a technical one); a legal decision made by AI, or by no one with authority, is not a legal decision; a chain
    that cannot be contested at its decision is not an effective one. The order must be the order of STAGES."""
    names = [s["stage"] for s in chain]
    issues = []
    if names != [s for s in STAGES if s in names]:
        issues.append("the stages are not in the order of the translation path")
    rows = []
    for s in chain:
        why = []
        technical = s["stage"] in ("technical_event", "data_representation")
        if not technical and not s["legal_basis"]:
            why.append("no legal basis is stated: not a legally valid step")
        if s["stage"] in ("legal_decision", "remedy"):
            if s["by_ai"] and not s["authority"]:
                why.append("an AI output is not a legal decision: no authorised human decides")
            if not s["authority"]:
                why.append("no decision authority is named")
            if not s["contest_path"]:
                why.append("no route to contest or review is named")
        rows.append({"stage": s["stage"], "valid": not why, "why_not": why, "uncertainty": s["uncertainty"], "responsible": s["responsible"]})
    first_bad = next((r["stage"] for r in rows if not r["valid"]), None)
    return {"stages": rows, "valid_legal_decision": first_bad is None and "legal_decision" in names and not issues, "first_invalid_stage": first_bad, "issues": issues,
            "reading": "a decision whose chain has an invalid legal stage is not treated as a legally valid decision; the technical stages are valid as technical facts only"}


def example_chain(valid: bool = True) -> list[dict]:
    ai = not valid
    return [stage("technical_event", legal_basis=None, scope="a score is computed", responsible="system operator", evidence="model run log", uncertainty="model error", authority=None, contest_path=None),
            stage("data_representation", legal_basis=None, scope="applicant record", responsible="data controller", evidence="record digest", uncertainty="input errors", authority=None, contest_path=None),
            stage("legal_fact", legal_basis="administrative procedure act (placeholder)" if valid else None, scope="eligibility facts", responsible="case officer", evidence="documents", uncertainty="facts disputed", authority="case officer", contest_path="notice and reply"),
            stage("legal_classification", legal_basis="eligibility rule (placeholder)", scope="class of the applicant", responsible="case officer", evidence="rule and facts", uncertainty="borderline", authority="case officer", contest_path="review"),
            stage("norm_selection", legal_basis="eligibility rule (placeholder)", scope="norm", responsible="case officer", evidence="statute text", uncertainty="interpretation", authority="case officer", contest_path="review"),
            stage("exception_handling", legal_basis="hardship clause (placeholder)", scope="exceptions", responsible="case officer", evidence="hardship claim", uncertainty="discretion", authority="case officer", contest_path="review"),
            stage("attribution", legal_basis="responsibility rule (placeholder)", scope="who answers", responsible="institution", evidence="process record", uncertainty="shared", authority="institution", contest_path="review"),
            stage("burden_of_proof", legal_basis="burden rule (placeholder)", scope="who proves", responsible="institution", evidence="rule", uncertainty="none", authority="institution", contest_path="review"),
            stage("legal_decision", legal_basis="eligibility rule (placeholder)", scope="grant or refuse", responsible="authorised official" if valid else "scoring system", evidence="reasons", uncertainty="error rate", authority="authorised official" if valid else None,
                  contest_path="independent review" if valid else None, by_ai=ai),
            stage("remedy", legal_basis="remedy rule (placeholder)", scope="correction and re-entry", responsible="institution", evidence="corrected record", uncertainty="propagation", authority="reviewer", contest_path="appeal")]


# ------------------------------------------------------------------------------------------------ the bundle that the legal-governance view reads (live small simulations; nothing stored)
def legal_bundle(seed: int = 3) -> dict:
    base = Institution(capacity=0.4, lam=0.8, review_capacity=0.15)
    repaired = base.with_(review_independent=True, review_authority=True, review_capacity=0.3, appeal_burden=0.2, propagate_correction=True, proxy_gate=False, lam=0.0, score_expiry=4, reentry_support=True, suspension=True)
    arms = {"baseline": base, "fairness optimisation only": base.with_(fairness_opt=True), "gate removed": base.with_(proxy_gate=False), "score deleted": base.with_(tau_score=False), "score deleted and gate removed": base.with_(tau_score=False, proxy_gate=False),
            "independent review with authority and propagation": base.with_(review_independent=True, review_authority=True, review_capacity=0.3, appeal_burden=0.2, propagate_correction=True), "all repairs": repaired}
    runs = {k: simulate(v, seed) for k, v in arms.items()}
    seen = {p for i, p in enumerate(PROVISIONS) if i % 4 != 3}  # a partial assessment: every fourth provision is not observed
    return {"synthetic": True, "catalogue": CATALOGUE_STATUS, "states": list(STATES), "guarantees": list(GUARANTEES),
            "assessments": {"baseline institution (formal appeal that can reverse nothing)": assess_guarantees(base, seed), "after the repairs": assess_guarantees(repaired, seed),
                            "baseline, with some provisions not observed": assess_guarantees(base, seed, observed=seen),
                            "an institution for which irreversible harm is impossible": assess_guarantees(base.with_(harm_irreversible=False), seed)},
            "chains": {"valid": {"chain": example_chain(True), "assessment": assess_chain(example_chain(True))}, "decided by the scoring system": {"chain": example_chain(False), "assessment": assess_chain(example_chain(False))}},
            "interventions": {k: {m: v[m] for m in ("exclusion_qualified", "exclusion_persistence", "tpr_gap", "group_exclusion_gap", "downstream_access_qualified", "overturn_rate_of_wrongful", "formal_appeal_rate", "burden_subject", "burden_institution")} | {"series_exclusion": v["series_exclusion"]}
                              for k, v in runs.items()},
            "observation": {"observed_provisions": sorted(seen), "not_observed_provisions": sorted(set(PROVISIONS) - seen), "note": "a provision that is not observed is INDETERMINATE: not observed is not absent"},
            "scope": "a synthetic institution; the guarantee catalogue is provisional (not verified against the originals); the mapping from guarantee to indicator is this implementation's; no real institution, law or person is described",
            "seed": seed}
