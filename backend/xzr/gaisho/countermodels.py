"""The finite countermodels of R37 (Appendix A and B.2b), made executable: exact enumeration where R37 gives a finite construction, and an independent re-execution where R37 reports an executed study.

None of them simulates Gaisho, thought, a human subject or an institution. Each is a LOGICAL or METHODOLOGICAL obstruction stated by R37 ("a finite type-safe counterexample ... without asserting new human data"), and each result below
is bounded the way R37 bounds it: no part of it supports A_G=supported, makes a subject exist, or establishes a philosophical right. R37 place of each: ``where``.

* questioning_models: R37 A.3 "Randomized questioning and a finite non-identification countermodel" (and its common-endpoint extension). H_R (retrieval) and H_F (formation through questioning) induce the same joint
  distribution of the recorded (X_ask, R) although the pre-question orientation E0 differs; with a common endpoint Y the interventional effect of the question is identified (1/2) and P(E0=1) is not (1/2 against 0).
  These are two of R37's three formation histories (H1 and H2); R37 gives no finite model of the third (a partial disposition transformed by the question) in the passages read, and none is invented here.
* report_indeterminacy: R37 A.3 "Conditional report-indeterminacy result": no rule based solely on the final report decides the property P(h) 'the orientation was operative before elicitation' on all histories.
* z_equivalence: R37 A.3: histories are Z-equivalent when Y(H1,z)=Y(H2,z) for every z in a frozen intervention set Z; a prospective pre-question probe, if independently justified, would break the equivalence (its validity is not assumed here).
* scm_equal_records: R37 B.2b (the R12 study): two structural models with identical observational (M,Y) records and different effects of do(M); re-executed here (R37 states that its edition did not rerun it) and compared with the values R37 reports.
* label_control: R37 A.5 and the R13 control: a reversible renaming of a label decoded before every consequence is invariant by construction, whereas an executed classification update that reaches the gate is not.
"""

from __future__ import annotations

import itertools
from fractions import Fraction
from typing import Any

import numpy as np

from .model import digest

BOT = "BOT"  # the report is inapplicable when no question is asked

# What R37 B.2b reports for the study it ran (128 seeds from 20261029, 4,096 units each, 524,288 worlds). Its random generator and script are not available here; the re-execution is compared with these numbers, not forced to them.
R37_REPORTED = {
    "where": "R37 Appendix B.2b (R12 study, GAISHO_R12_study.py)",
    "seeds": 128, "first_seed": 20261029, "units_per_seed": 4096, "p_noise": 0.1, "mcar_mask": 0.2,
    "association_mean": 0.800495, "association_interval": [0.798913, 0.802078],
    "effect_A_mean": 0.800510, "effect_A_interval": [0.798927, 0.802094],
    "effect_B": 0.0, "theory_effect_A": 0.8,
}


def _joint(model: str, with_y: bool) -> dict[tuple, Fraction]:
    """Exact joint distribution of the recorded pair by complete enumeration of (U, X_ask) in {0,1}^2, each with weight 1/4."""
    out: dict[tuple, Fraction] = {}
    for u, x in itertools.product((0, 1), repeat=2):
        e1 = u if model == "H_R" else x * u
        r = BOT if (x == 0 and not with_y) else e1  # R: inapplicable without a question; Y: a common t2 readout equal to E1 in both arms
        out[(x, r)] = out.get((x, r), Fraction(0)) + Fraction(1, 4)
    return out


def questioning_models() -> dict[str, Any]:
    pair = {}
    for name, (a, b), with_y in (("report", ("H_R", "H_F"), False), ("common_endpoint", ("H_R*", "H_F*"), True)):
        ja, jb = _joint(a, with_y), _joint(b, with_y)
        e0 = {m: sum(Fraction(1, 4) for u, x in itertools.product((0, 1), repeat=2) if (u if m in ("H_R", "H_R*") else 0) == 1) for m in (a, b)}
        entry: dict[str, Any] = {"models": [a, b], "same_recorded_joint": ja == jb, "joint": {f"({k[0]},{k[1]})": str(v) for k, v in sorted(ja.items(), key=str)}, "P_E0_equals_1": {m: str(v) for m, v in e0.items()}, "P_E0_identified_by_the_record": e0[a] == e0[b]}
        if with_y:  # the interventional effect of the question on Y: E[Y | do(X_ask=1)] - E[Y | do(X_ask=0)]; Y = X_ask * U in both arms
            eff = {m: sum(Fraction(1, 2) * (1 * u) for u in (0, 1)) - sum(Fraction(1, 2) * (0 * u) for u in (0, 1)) for m in (a, b)}
            entry["effect_of_the_question_on_Y"] = {m: str(v) for m, v in eff.items()}
            entry["effect_identified"] = eff[a] == eff[b] == Fraction(1, 2)
        pair[name] = entry
    return {"where": "R37 Appendix A.3 (randomized questioning; common-endpoint extension)", "models": pair,
            "reading": "randomized questioning and full knowledge of the recorded distribution identify what the question changes by t2 and do not identify whether the orientation preceded it; the binary state is stipulated, not a verified episode",
            "limits": "two of R37's three formation histories (retrieval, formation); the third (a partial disposition transformed by the question) is not modelled; no human, neural or machine data; A_G stays unresolved"}


def report_indeterminacy() -> dict[str, Any]:
    """No report-only rule g decides P on all histories: enumerated over every function from the report values to {0,1}."""
    hist = [(m, u, x) for m in ("H_R", "H_F") for u, x in itertools.product((0, 1), repeat=2)]

    def P(h):  # the orientation was operative before elicitation (E0 = 1)
        return int((h[1] if h[0] == "H_R" else 0) == 1)

    def r(h):  # the recorded pair (X_ask, R)
        m, u, x = h
        e1 = u if m == "H_R" else x * u
        return (x, BOT if x == 0 else e1)
    values = sorted({r(h) for h in hist}, key=str)
    deciding = [g for g in itertools.product((0, 1), repeat=len(values)) if all(dict(zip(values, g, strict=True))[r(h)] == P(h) for h in hist)]
    witness = [(h1, h2) for h1, h2 in itertools.combinations(hist, 2) if r(h1) == r(h2) and P(h1) != P(h2)]
    return {"where": "R37 Appendix A.3 (conditional report-indeterminacy result)", "histories": len(hist), "report_values": [list(map(str, v)) for v in values], "report_only_rules_checked": 2 ** len(values), "rules_that_decide_P_on_every_history": len(deciding),
            "witness_pair": [list(map(str, w)) for w in witness[:1]], "reading": "the antecedent (two admissible histories with equal reports and different P) holds, so no report-only rule identifies P; the result is conditional on this admissible pair and is not a general impossibility of memory research"}


def z_equivalence() -> dict[str, Any]:
    def Y(model: str, u: int, z: str) -> int:  # the common outcome map under an intervention z
        x = {"do(X_ask=0)": 0, "do(X_ask=1)": 1}.get(z)
        if z == "pre-question probe (E0)":
            return u if model == "H_R*" else 0
        assert x is not None
        return x * u
    Z0 = ("do(X_ask=0)", "do(X_ask=1)")
    Z1 = (*Z0, "pre-question probe (E0)")
    eq = lambda Z: all(Y("H_R*", u, z) == Y("H_F*", u, z) for u in (0, 1) for z in Z)  # noqa: E731
    return {"where": "R37 Appendix A.3 (intervention-relative distinction)", "frozen_Z": list(Z0), "Z_equivalent_on_Z": eq(Z0), "with_probe": list(Z1), "Z_equivalent_with_probe": eq(Z1),
            "reading": "on the question alone the two histories are Z-equivalent; a pre-question probe independently justified as sensitive to E0 would break the equivalence. The probe's validity is stipulated here: R37 requires it to be established without assuming the Gaisho attribution; changing Z changes the test and cannot be used to reverse a conclusion silently"}


def scm_equal_records(seeds: int = 128, units: int = 4096, first_seed: int = 20261029, p_noise: float = 0.1, mcar: float = 0.2) -> dict[str, Any]:
    """R37 B.2b: U binary with P=1/2, E binary noise with P(E=1)=0.1, M recorded, Y downstream. Model A: M:=U, Y:=M xor E. Model B: M:=U, Y:=U xor E. The interventions set M to 1 or 0 on the same exogenous tape."""
    assoc, eff_a, eff_b, same, same_masked, sham = [], [], [], True, True, True
    for k in range(seeds):
        rg = np.random.default_rng(first_seed + k)
        u = rg.integers(0, 2, units)
        e = (rg.uniform(size=units) < p_noise).astype(int)
        visible = rg.uniform(size=units) >= mcar
        m = u.copy()
        ya, yb = m ^ e, u ^ e  # observational outcomes of the two models on the same tape
        same = same and bool(np.array_equal(ya, yb))
        same_masked = same_masked and bool(np.array_equal(ya[visible], yb[visible]))
        assoc.append(float(ya[m == 1].mean() - ya[m == 0].mean()))
        eff_a.append(float(((1 ^ e) - (0 ^ e)).mean()))  # A: Y(do(M=m)) = m xor E
        eff_b.append(float(((u ^ e) - (u ^ e)).mean()))  # B: Y does not depend on M
        # the R13 control: a reversible observer-side relabel L' = 1 - M, decoded before the consequence-generating equation
        l_obs = 1 - m
        sham = sham and bool(np.array_equal((1 - l_obs) ^ e, ya))  # decode, then apply the equation of A: nothing changes
    def ci(x):
        a = np.asarray(x)
        se = float(a.std(ddof=1) / np.sqrt(len(a))) if len(a) > 1 else 0.0
        return {"mean": float(a.mean()), "interval95": [float(a.mean() - 1.96 * se), float(a.mean() + 1.96 * se)], "seeds": len(a)}
    res: dict[str, Any] = {"where": R37_REPORTED["where"], "seeds": seeds, "units_per_seed": units, "worlds": seeds * units, "first_seed": first_seed, "p_noise": p_noise, "mcar_mask": mcar,
                           "observational_records_identical_in_every_seed": same, "masked_records_identical_in_every_seed": same_masked,
                           "association": ci(assoc), "effect_of_do_M_in_A": ci(eff_a), "effect_of_do_M_in_B": ci(eff_b), "executed_sham_relabel_effect_is_zero": sham,
                           "theory": {"effect_A": 1 - 2 * p_noise, "effect_B": 0.0}}
    if seeds == R37_REPORTED["seeds"] and units == R37_REPORTED["units_per_seed"] and first_seed == R37_REPORTED["first_seed"]:
        rep = R37_REPORTED
        overlap = lambda a, b: a[0] <= b[1] and b[0] <= a[1]  # noqa: E731
        res["compared_with_r37"] = {"reported": {k: rep[k] for k in ("association_mean", "association_interval", "effect_A_mean", "effect_A_interval", "effect_B")},
                                    "association_interval_overlaps": overlap(res["association"]["interval95"], rep["association_interval"]), "effect_A_interval_overlaps": overlap(res["effect_of_do_M_in_A"]["interval95"], rep["effect_A_interval"]),
                                    "effect_B_equal": res["effect_of_do_M_in_B"]["mean"] == rep["effect_B"] == 0.0,
                                    "note": "R37 states its random generator is not given here; agreement is of the intervals (both estimate 1 - 2 P(E=1) = 0.8), not of the seed-level numbers"}
    res["reading"] = "observational equivalence, even across the matched worlds, does not settle mediation; the intervention separates A (do(M) matters) from B (it does not); the effect of a marker, where present, does not establish a Gaisho attribution ('marker has a causal effect; Gaisho attribution unresolved')"
    return res


def label_control(units: int = 4096, seed: int = 7) -> dict[str, Any]:
    """R37 A.5: descriptive renaming (decoded before every consequence) against an executed classification update that reaches the gate."""
    rg = np.random.default_rng(seed)
    u = rg.integers(0, 2, units)
    e = (rg.uniform(size=units) < 0.1).astype(int)
    out = {}
    for name, f in (("A (the gate reads the marker)", lambda m, uu: m ^ e), ("B (the gate does not read the marker)", lambda m, uu: uu ^ e)):
        base = f(u, u)
        renamed = f(1 - (1 - u), u)  # rho then its inverse before the gate: F(rho^-1(rho(L))) = F(L)
        updated = f(1 - u, u)  # an executed update kappa(L) = 1 - L consumed by the gate
        out[name] = {"renaming_changes_outcomes": int((renamed != base).sum()), "executed_update_changes_outcomes": int((updated != base).sum()), "units": units}
    return {"where": "R37 Appendix A.5 and VIII (reversible renaming and executed classification as distinct interventions)", "gates": out,
            "reading": "renaming changes nothing by construction; an executed update changes the outcome only if the gate reads the label (A) and not otherwise (B): the negative result for renaming proves nothing about an executed update, and neither says anything about the justice of the gate or about a Gaisho"}


def run_all(seeds: int = 128, units: int = 4096) -> dict[str, Any]:
    out: dict[str, Any] = {"questioning": questioning_models(), "report_indeterminacy": report_indeterminacy(), "z_equivalence": z_equivalence(), "scm": scm_equal_records(seeds, units), "label_control": label_control(units),
                           "supports_a_gaisho_attribution": False, "attribution": "UNRESOLVED",
                           "scope": "finite logical and methodological constructions stipulated by R37; they do not simulate Gaisho, thought, a human subject or an institution, and none of their results supports A_G=supported"}
    out["digest"] = digest({k: v for k, v in out.items() if k != "digest"})
    return out
