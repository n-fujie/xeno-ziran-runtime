"""What the experiments of the knowledge domain SUPPORT (inside the synthetic model), what they show to be LIMITED or NEGATIVE, and what stays a philosophical hypothesis that the laboratory does not test.

A claim has a status and, for a supported or negative one, the relation or result of the saved experiments it rests on (``docs/gaisho/experiments.json``); a test (tests/test_gaisho.py) re-reads those results and fails if a claim
no longer holds. A hypothesis is listed so that it is not mistaken for a result. The manuscript GAISHO R37 was read on 2026-11-05 (parts read are listed in r37.py): the laboratory's claims are not R37 propositions, no claim here is registered as proved by R37, and the identifiers U1-U4 avoid R37's own H1-H3
(formation histories). Whether the operational criterion matches Non-Accidental Success (Dictionary entry 022) is UNVERIFIED.
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
    {"id": "U1", "status": UNTESTED_HYPOTHESIS, "claim": "Non-accidental success is the characteristic core of a knowledge Gaisho, or of any Gaisho.",
     "rests_on": "nothing. R37 (as read) has no 'knowledge Gaisho': it keeps knowledge (P/A Dictionary 013-024: constitution, detection, attribution, entitlement, defeater, non-accidental success, continuity, withdrawal) apart from Gaisho, and says these distinctions prevent a Gaisho episode from replacing epistemic justification"},
    {"id": "U2", "status": UNTESTED_HYPOTHESIS, "claim": "The ground-responsive agent has a knowledge Gaisho; the cue-driven agent has an accidental one.",
     "rests_on": "nothing: a synthetic operation has no eligible bearer, interval or directed relation, so it fails R37's applicability gate; the attribution is recorded as unresolved"},
    {"id": "U3", "status": UNTESTED_HYPOTHESIS, "claim": "The laboratory's operational criterion of non-accidental success (large effect of the evidence, small effect of the cue, stable correctness under do(W)) corresponds to what R37 or the P/A Dictionary (entry 022) means by Non-Accidental Success, and that success is a necessary and sufficient constitutive core of knowledge or of a Gaisho.",
     "rests_on": "UNVERIFIED. The researcher states that R37 does not prove Non-Accidental Success to be a necessary and sufficient constitutive core of a knowledge Gaisho; in the parts of R37 read, entry 022 appears only in the Appendix C cross-index, as one of the five separate results of the epistemic family, 'research-dependent rather than a settled account of knowledge'. The definition of entry 022 in the Dictionary itself (v40) was not available. Not to be read as an R37-proved proposition"},
    {"id": "U4", "status": UNTESTED_HYPOTHESIS, "claim": "Ignition, maintenance, transformation, expiry and re-ignition of a Gaisho have the operational counterparts used here (feedback reconfiguration, shift loss, revision).",
     "rests_on": "nothing: R37 III defines Gaisho ignition as a transition to an episode meeting attribution criteria and re-ignition as needing a justified relation to the prior episode; the laboratory's fields of these names are labelled operational analogues"},
    {"id": "R37-H1..H3", "status": UNTESTED_HYPOTHESIS, "claim": "R37's own H1, H2 and H3: three formation histories of an orientation under a question (retrieved by the question, constituted by it, a partial disposition transformed by it), observationally equivalent under identical avowals.",
     "rests_on": "not modelled by the laboratory. These are R37's identifiers and are unrelated to the laboratory's claims U1-U4 (renamed from H1-H4 to avoid the collision)"},
)


def claims_by_status() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {SUPPORTED_IN_MODEL: [], LIMITED_OR_NEGATIVE: [], UNTESTED_HYPOTHESIS: []}
    for c in CLAIMS:
        out[c["status"]].append(c)
    return out
