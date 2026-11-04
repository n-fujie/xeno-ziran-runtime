"""What the experiments of the knowledge domain SUPPORT (inside the synthetic model), what they show to be LIMITED or NEGATIVE, and what stays a philosophical hypothesis that the laboratory does not test.

A claim has a status and, for a supported or negative one, the relation or result of the saved experiments it rests on (``docs/gaisho/experiments.json``); a test (tests/test_gaisho.py) re-reads those results and fails if a claim
no longer holds. A hypothesis is listed so that it is not mistaken for a result. The manuscript GAISHO R37 was not available when this registry was written: whether the operational criterion matches the definition of the
non-accidental core in R37 is UNVERIFIED, and every statement here is about the laboratory's own operational construct.
"""

from __future__ import annotations

SUPPORTED_IN_MODEL = "SUPPORTED_IN_MODEL"  # holds in the executed synthetic experiments, for the declared model and constants
LIMITED_OR_NEGATIVE = "LIMITED_OR_NEGATIVE"  # the experiments show a limit, a null or a negative result
UNTESTED_HYPOTHESIS = "UNTESTED_PHILOSOPHICAL_HYPOTHESIS"  # not tested by any computation here

CLAIMS: tuple[dict, ...] = (
    {"id": "K1", "status": SUPPORTED_IN_MODEL, "claim": "Judging agents with the same accuracy before an environmental shift (base-rate guess, coincidental cue, ground-responsive) differ in how their judgement responds to interventions on the evidence and on the cue.",
     "rests_on": "effect_E, effect_S (do(E), do(S)) and accuracy_pre_shift of the three conditions, 20 seeds, 95 % intervals not overlapping between the cue-driven and the evidence-driven conditions"},
    {"id": "K2", "status": SUPPORTED_IN_MODEL, "claim": "The cue-driven agent loses accuracy when the cue decouples from the state; the ground-responsive agent does not.",
     "rests_on": "shift_drop and stability_do_W (a balanced world with the cue decoupled)"},
    {"id": "K3", "status": SUPPORTED_IN_MODEL, "claim": "With feedback on the true state the agent reconfigures its dependence (from the cue to the evidence); without feedback the dependence is kept.",
     "rests_on": "revision_E, revision_S of 'correction and reconfiguration' against 'no correction'"},
    {"id": "K4", "status": SUPPORTED_IN_MODEL, "claim": "An observation condition can change the record of a relation without changing the realized operation (scale, instrument noise, passive coupling, boundary, memory), and can change the operation itself (probe, environment, window).",
     "rests_on": "compare_observations: the operation digest is identical for the first group and differs for the second"},
    {"id": "K5", "status": SUPPORTED_IN_MODEL, "claim": "A shape of this domain carries the three weights of the agent's decision rule at the moment of the snapshot (plus sampling noise); before and after a moment at which the weights did not change, the shapes differ only by sampling noise.",
     "rests_on": "construction.explain_shape: the fitted weights reproduce the recorded weights; construction.reading_of_difference"},
    {"id": "N1", "status": LIMITED_OR_NEGATIVE, "claim": "The pre-set operational criterion of the 'non-accidental core' (large effect of the evidence, small effect of the cue, stable correctness under do(W)) does not separate the miscalibrated misjudgement from the ground-responsive judgement.",
     "rests_on": "attribution_tests: both NOT_NEGATED; the criterion tests responsiveness, not the correctness of the reading"},
    {"id": "N2", "status": LIMITED_OR_NEGATIVE, "claim": "The 'core-only' construction (response to the evidence alone) adds nothing over a static causal model of the same information on held-out interventions: REDUNDANT or HARMFUL in every condition.",
     "rests_on": "compare_models, verdicts against M1"},
    {"id": "N3", "status": LIMITED_OR_NEGATIVE, "claim": "No cut and no structural feature beyond a smooth ridge appears in the shapes of this domain: they are logistic surfaces of three weights, so the domain cannot show a richer 'operational shape' than the weights define.",
     "rests_on": "explain_shape: cuts = 0 for the default conditions; the fit residual is at the sampling-noise level"},
    {"id": "N4", "status": LIMITED_OR_NEGATIVE, "claim": "Relations that were not detected (95 % interval includes 0) are not shown to be zero; relations an observation cannot identify are unresolved, not zero.", "rests_on": "negative_results kinds NOT_DETECTED and UNOBSERVED"},
    {"id": "H1", "status": UNTESTED_HYPOTHESIS, "claim": "Non-accidentality is the characteristic core of a knowledge Gaisho (or of any Gaisho).", "rests_on": "nothing: the laboratory reads candidate relations and does not assume a core; whether a core exists is not decided"},
    {"id": "H2", "status": UNTESTED_HYPOTHESIS, "claim": "The ground-responsive agent has a knowledge Gaisho; the cue-driven agent has an accidental one.", "rests_on": "nothing: a synthetic operation has no bearer and no historical interval, and the attribution needs independent evidence"},
    {"id": "H3", "status": UNTESTED_HYPOTHESIS, "claim": "The operational criterion corresponds to what the manuscript GAISHO R37 means by the non-accidental core.", "rests_on": "R37 was not available: UNVERIFIED"},
    {"id": "H4", "status": UNTESTED_HYPOTHESIS, "claim": "Ignition, maintenance, transformation, expiry and re-ignition of a Gaisho have the operational counterparts used here (feedback reconfiguration, shift, revision).", "rests_on": "nothing: they are the laboratory's operationalisations, not R37's definitions"},
)


def claims_by_status() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {SUPPORTED_IN_MODEL: [], LIMITED_OR_NEGATIVE: [], UNTESTED_HYPOTHESIS: []}
    for c in CLAIMS:
        out[c["status"]].append(c)
    return out
