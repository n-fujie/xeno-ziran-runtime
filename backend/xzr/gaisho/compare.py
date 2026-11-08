"""Comparison of observation conditions on the same operation, and of the Gaisho-candidate profile with competing explanations."""

from __future__ import annotations

import numpy as np

from .lab import FULL, Domain, Observation, paired, run_domain
from .model import digest


def compare_observations(dom: Domain, cond: str, a: Observation, b: Observation, seeds: tuple[int, ...]) -> dict:
    """The same condition through two observation conditions. A relation is classified as: SAME; RECORD_DIFFERENCE (the realized operation is identical, the record differs: the observation changed what was recorded);
    OPERATION_DIFFERENCE (the realized operation itself differs: the observation changed the operation, through a probe, an environment or a window that is part of the run); or UNOBSERVED_IN_ONE (one record cannot identify it)."""
    ra, rb = run_domain(dom, a, seeds, [cond]), run_domain(dom, b, seeds, [cond])
    ca, cb = ra["conditions"][cond], rb["conditions"][cond]
    same_op = ca["operation_digest"] == cb["operation_digest"]
    rows = []
    for name in dom.relation_names:
        x, y = ca["relations"][name], cb["relations"][name]
        if x["status"] != "IDENTIFIED" or y["status"] != "IDENTIFIED":
            kind = "UNOBSERVED_IN_ONE" if (x["status"] == "IDENTIFIED") != (y["status"] == "IDENTIFIED") else "UNOBSERVED_IN_BOTH"
            rows.append({"relation": name, "first": x["status"] if x["status"] != "IDENTIFIED" else x["value"], "second": y["status"] if y["status"] != "IDENTIFIED" else y["value"], "kind": kind})
            continue
        d = paired(x["per_seed"], y["per_seed"])
        differs = bool(d["detected"]) and abs(d["mean"]) > 0.05
        rows.append({"relation": name, "first": x["value"], "second": y["value"], "paired_difference": d, "kind": "SAME" if not differs else ("RECORD_DIFFERENCE" if same_op else "OPERATION_DIFFERENCE")})
    perturbs = (not same_op) and (a.probe != b.probe or a.environment != b.environment or a.temporal_window != b.temporal_window)
    return {"condition": cond, "same_realized_operation": same_op, "observation_changed_the_operation": perturbs, "operation_part_first": a.operation_part(), "operation_part_second": b.operation_part(), "relations": rows, "digests": [ra["digest"], rb["digest"]]}


def _logit(p):
    p = np.clip(p, 0.02, 0.98)
    return np.log(p / (1 - p))


def _fit(cells: list[tuple[float, float, float]]) -> np.ndarray:
    X = np.array([[x, y, 1.0] for x, y, _ in cells])
    t = _logit(np.array([p for _, _, p in cells]))
    return np.linalg.lstsq(X, t, rcond=None)[0]


def _predict(w: np.ndarray, x: float, y: float) -> float:
    return float(1 / (1 + np.exp(-(w[0] * x + w[1] * y + w[2]))))


# What each model of the comparison is given and what it may fit. All of them see the SAME recorded cells of the 'end' snapshot (the training cells), none sees the history (the other snapshots or the weights),
# none sees the held-out cells, and the interventions of the test are the same. M0..M4 differ only in the structure they may fit; the number of parameters is stated, because a nested model cannot beat the model it is nested in
# when that model contains the generating process (the knowledge domain's cells ARE a three-weight logistic response: M1 is the true model class, CAND is M1 with the cue weight fixed to zero, M4 is M1 with the evidence weight fixed to zero).
COMPARATORS = {
    "M0": {"label": "reliability only", "fits": "the marginal rate of the training cells (what an accuracy statistic holds)", "parameters": 1, "information": "end-snapshot training cells", "history": False, "nested_in": None},
    "M1": {"label": "static causal model", "fits": "logistic response to the evidence E and the cue S, with an offset", "parameters": 3, "information": "end-snapshot training cells", "history": False, "nested_in": None},
    "CAND": {"label": "the candidate construction (response to the evidence alone)", "fits": "logistic response to E and an offset; the cue is no part of the 'core'", "parameters": 2, "information": "end-snapshot training cells", "history": False, "nested_in": "M1 (cue weight 0)"},
    "M4": {"label": "single-factor cue account", "fits": "logistic response to S and an offset; the evidence is no part of the account", "parameters": 2, "information": "end-snapshot training cells", "history": False, "nested_in": "M1 (evidence weight 0)"},
}
# R37 (II, equivalence and reduction): two descriptions are Q-equivalent only under a FROZEN inquiry specification Q. The Q of this comparison, as far as the laboratory fixes it (cost accounting is the coarse parameter count only).
Q_SPEC = {
    "target_discrimination": "whether the response of a synthetic judging agent to interventions on the evidence and on a coincidental cue is predicted at held-out intervention cells by a response to the evidence alone, as well as by the competitors (a question about a construction of a decision rule, not about a Gaisho)",
    "boundaries": "the agent's decision rule at the end of the run; the world, the cue and the feedback are outside the compared models",
    "observation_channels": "the recorded surface of the 'end' snapshot under the stated observation condition",
    "time_horizon": "one moment (the end of 400 trials); no history",
    "admissible_interventions": "do(E) and do(S) on a 13 x 7 grid; training on the natural manifold and the neutral-cue row, test on the other cells",
    "history": "none is given to any model",
    "resources": "the same recorded cells for every model; 1 to 3 fitted parameters (the parameter count is the whole of the cost accounting)",
    "endpoints": "root-mean-square error on the held-out cells, paired over seeds; verdicts by a margin of 0.03",
}
# R37 II distinguishes three results of a comparison; the laboratory's verdicts correspond only to the first two kinds of statement and never to the third.
R37_OUTCOME_CLASSES = {
    "i": "an attributed episode with no additional model distinction under Q: not applicable (there is no episode)",
    "ii": "a difference in self-avowal or interpretation that matters to another question: not applicable (no avowal)",
    "iii": "a distinct, independently validated difference that survives an equal-information, equal-cost adversarial comparator (support for a non-redundant mechanism in the declared experiment): NOT ASSESSED; no verdict here is evidence for or against it",
}
NOT_RUN = ("attention", "memory / history-informed prediction", "predictive processing", "sensorimotor", "cognitive appraisal", "concept learning", "SNN", "dynamical systems", "the existing operational-shape analysis")


def compare_models(dom: Domain, seeds: tuple[int, ...], obs: Observation = FULL, margin: float = 0.03, extended: bool = False) -> dict:
    """The Gaisho-candidate profile against competing explanations, with the SAME information (the recorded response on the training cells), the same computation (a three-parameter fit each) and the same held-out interventions.
    Train: the cells on the natural manifold (evidence and cue move together, as they do without intervention) and the neutral-cue row (do(E)). Test: every other cell (evidence and cue set independently).
    M0 reliability only: predicts the marginal rate (what an accuracy statistic knows). M1 static causal model: logistic response to E and S fitted to the training cells. CAND the candidate construction: the
    'non-accidental core' read as a response to the evidence alone (the coincidental cue is no part of the core). A competitor that holds the same differences makes the added construction REDUNDANT;
    the verdicts are kept apart and are not added into a score."""
    cond_names = [c for c in dom.conditions]
    ny, nx = len(dom.y_values), len(dom.x_values)
    train = lambda i, j: abs(j - (ny - 1) * (i / max(1, nx - 1))) <= 0.9 or j == ny // 2  # noqa: E731
    per: dict[str, dict[str, list[float]]] = {c: {"M0": [], "M1": [], "CAND": [], **({"M4": []} if extended else {})} for c in cond_names}
    for cond in cond_names:
        for s in seeds:
            r = dom.simulate(cond, s, obs)
            end = r["snapshots"].get("end")
            if not end:
                continue
            cells = [c for c in end["surface"]["cells"] if c["p"] is not None]
            tr = [(c["x"], c["y"], c["p"]) for c in cells if train(c["i"], c["j"])]
            te = [(c["x"], c["y"], c["p"]) for c in cells if not train(c["i"], c["j"])]
            if len(tr) < 6 or not te:
                continue
            w = _fit(tr)
            m0 = float(np.mean([p for _, _, p in tr]))
            # the candidate construction: the 'non-accidental core' is the response to the evidence alone, with the coincidental cue treated as no part of it: a logistic response to E and an offset (two numbers; the causal model has three)
            Xc = np.array([[x, 1.0] for x, _, _ in tr])
            wc = np.linalg.lstsq(Xc, _logit(np.array([p for _, _, p in tr])), rcond=None)[0]
            cand = np.array([wc[0], 0.0, wc[1]])
            per[cond]["M0"].append(float(np.sqrt(np.mean([(m0 - p) ** 2 for _, _, p in te]))))
            per[cond]["M1"].append(float(np.sqrt(np.mean([(_predict(w, x, y) - p) ** 2 for x, y, p in te]))))
            if extended:
                Xs = np.array([[y, 1.0] for _, y, _ in tr])
                ws = np.linalg.lstsq(Xs, _logit(np.array([p for _, _, p in tr])), rcond=None)[0]
                m4 = np.array([0.0, ws[0], ws[1]])
                per[cond]["M4"].append(float(np.sqrt(np.mean([(_predict(m4, x, y) - p) ** 2 for x, y, p in te]))))
            per[cond]["CAND"].append(float(np.sqrt(np.mean([(_predict(cand, x, y) - p) ** 2 for x, y, p in te]))))
    rows = []
    for cond in cond_names:
        d = per[cond]
        if min(len(v) for v in d.values()) < 2:
            rows.append({"condition": cond, "verdicts": [{"competitor": "all", "verdict": "UNRESOLVED", "why": "the held-out interventions were not recorded under this observation (no off-manifold cells): the explanations cannot be told apart"}]})
            continue
        verdicts = []
        for comp, label in (("M0", "reliability only"), ("M1", "static causal model"), *((("M4", "single-factor cue account"),) if extended else ())):
            diff = paired(list(d[comp]), list(d["CAND"]))  # competitor error minus candidate error: positive = the candidate predicts the held-out interventions better
            if diff["ci95"] is None:
                v = "UNRESOLVED"
            elif diff["ci95"][0] > margin:
                v = "NON_REDUNDANT"
            elif diff["ci95"][1] < -margin:
                v = "HARMFUL"
            elif diff["ci95"][0] > -margin and diff["ci95"][1] < margin:
                v = "REDUNDANT"
            else:
                v = "UNRESOLVED"
            verdicts.append({"competitor": f"{comp} ({label})", "verdict": v, "error_difference": diff, "margin": margin, "errors": {k: float(np.mean(x)) for k, x in d.items()}})
        rows.append({"condition": cond, "verdicts": verdicts})
    out_extra = {"comparators": {k: v for k, v in COMPARATORS.items() if extended or k != "M4"}, "Q": Q_SPEC, "r37_outcome_classes": R37_OUTCOME_CLASSES, "not_run": list(NOT_RUN), "held_out": "every cell off the natural manifold (the evidence and the cue set independently) except the neutral-cue row",
                 "reading": "the verdicts compare the construction 'response to the evidence alone' with the explanations above, on the same cells; they say nothing about whether a Gaisho or non-accidentality exists, and a nested model cannot beat the model that contains the generating process"} if extended else {}
    return {**out_extra, "rule": "NON_REDUNDANT if the candidate's held-out error is lower than the competitor's by more than the margin (95% CI); REDUNDANT if the CI lies inside +/- margin; HARMFUL if the candidate is worse by more than the margin; otherwise UNRESOLVED", "unit": "one run per seed; paired over seeds", "seeds": list(seeds), "rows": rows, "digest": digest(rows)}


def attribution_tests(result: dict, stability_level: float = 0.7) -> list[dict]:
    """Pre-set operational tests of the hypothesis that a condition shows the candidate 'non-accidental core' (the effect of the evidence large, the effect of the coincidental cue small, the correctness stable under do(W)).
    The test has the power to fail: a condition is CRITERION_NEGATIVE if its 95 % interval excludes the criterion. A condition that passes the operational test is NOT attributed anything: the test is operational, the attribution
    needs independent evidence and stays UNRESOLVED."""
    out = []
    for cond, v in result["conditions"].items():
        r = v["relations"]
        if any(r[n]["status"] != "IDENTIFIED" for n in ("effect_E", "effect_S", "stability_do_W")):
            out.append({"condition": cond, "operational_test": "UNRESOLVED", "attribution": "UNRESOLVED", "why": "a relation needed by the test is unobserved under this observation"})
            continue
        e, s, st = r["effect_E"], r["effect_S"], r["stability_do_W"]
        fails = []
        if e["ci95"][1] < 0.5:
            fails.append("the effect of the evidence is below 0.5")
        if s["ci95"][0] > 0.2:
            fails.append("the effect of the coincidental cue is above 0.2")
        if st["ci95"][1] < stability_level:
            fails.append(f"the correctness under do(W) is below {stability_level}")
        out.append({"condition": cond, "operational_test": "CRITERION_NEGATIVE" if fails else "NOT_NEGATED", "attribution": "UNRESOLVED", "why": "; ".join(fails) if fails else "the operational criterion was not negated; this is not an attribution", "criterion": {"effect_E_min": 0.5, "effect_S_max": 0.2, "stability_min": stability_level}})
    return out
