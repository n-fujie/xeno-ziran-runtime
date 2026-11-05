"""What the experiments of the knowledge domain SUPPORT (inside the synthetic model), what they show to be LIMITED or NEGATIVE, and what stays a philosophical hypothesis that the laboratory does not test.

A claim has a status and, for a supported or negative one, the relation or result of the saved experiments it rests on (``docs/gaisho/experiments.json``); a test (tests/test_gaisho.py) re-reads those results and fails if a claim
no longer holds. A hypothesis is listed so that it is not mistaken for a result. The manuscript GAISHO R37 was read on 2026-11-05 (parts read are listed in r37.py): the laboratory's claims are not R37 propositions, no claim here is registered as proved by R37, and the identifiers U1-U4 avoid R37's own H1-H3
(formation histories). The Dictionary file provided on 2026-11-05 (71 entries, October 2026; not the 112-entry edition R37 cites) was read for entries 001-071: it defines Non-Accidental Success (entry 022) without any operational criterion and does not make it a necessary and sufficient core of knowledge (U3); it has no Gaisho entry.
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
     "rests_on": "PARTLY CHECKED against the 71-entry October 2026 Dictionary (dictionary.py), UNVERIFIED against the 112-entry edition R37 cites. (1) Correspondence: entry 022 defines Non-Accidental Success as a correct performance attributable to a relevant capacity and not dependent on a lucky coincidence in the comparison situations that matter, and asks that the perturbation set be specified; the laboratory's criterion is one such specification (do(E), do(S), the cue decoupled), not shown to be what 022 means. Its sensitivity to the choice of the set WAS run (perturbation.py, eight declared worlds, experiments_perturbation.json): the set of agents it calls stable differs between worlds, so the verdict depends on the neighbourhood; which neighbourhood is right is not decided. (2) Necessary and sufficient core: not supported; entry 013 calls its analysis defeasible and 'not a new necessary-and-sufficient theorem', requires a bearer, content, truth, competence and defeaters, and entry 017 warns against inferring a sufficient condition for knowledge from a successful discrimination. The file has no Gaisho entry, so the claim for a Gaisho is unchecked. R37 (as read) lists 022 only in its cross-index, as one of five separate results of the epistemic family, 'research-dependent rather than a settled account of knowledge'. Not to be read as an R37-proved or Dictionary-proved proposition"},
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
