"""The correspondence of the laboratory with the manuscript GAISHO R37 (Fujie, 3 November 2026), written after reading it (2026-11-05).

What was read, and what was not (stated so that nothing here is taken for a full-text verification of 784k characters): READ IN FULL OR NEARLY SO: the Abstract and Preface; Part II sections 4-5 and its passages on individuation, the two evidential tracks, the G-C-N comparison, the four-way test, the
six-register crosswalk, the equivalence-and-reduction challenge, the pair of action-identical episodes, intervention order, the proxy counterexample, failure to individuate, the causal mediator, the limited discrimination proposition and the levels of claim; all of Part III; Part X's opening, seven-arm programme,
failure registries, counterexamples and withdrawal rules; most of Part XII; Appendix A (A.1, A.2, A.3 with the randomized-questioning and report-indeterminacy results, A.3e, A.5, A.6 opening); Appendix B.2b; the Appendix C cross-index (entries 001-044). READ IN PART: Part I (the two inferential prohibitions), Part V (the Scale-Size-Speed
passage), Part VIII (the four sites of credit classification, the Score-Subject Agent, reversible renaming against executed classification). HEADINGS ONLY, NOT READ: the rest of Part II, Parts IV, VI, VII, IX and XI, the rest of Part V and Part VIII, the rest of Appendix B (B.2c-B.5: the inherited R13-R18 studies), the rest of Appendix C.
The P/A Dictionary v40 itself (181 pages) was not provided: only R37's cross-index of its headwords is available, so no entry's own definition (entry 022 included) has been checked.

What R37 says that this module takes as constraints (section numbers are R37's):
* II 4: Gaisho is a *candidate* mode of thought-related operation, an EPISODE of orientation of a bearer b over an interval t toward a directed relation w; occurrence Occ_G(b,t,w), detectability Det_D(K,t) and attribution
  A_G(b,t,w;e,K) in {supported, defeated-for-K, unresolved} have different codomains; absent rival explanations, provenance, admissible interventions and an individuation rule "the verdict is unresolved rather than negative".
* II 5 and the G-C-N / four-way / six-register passages: A_G, C (conceptual operational shape), P (prereflective orientation), E (expressive act), N (normative standing) and I (institutional execution) are separate registers with
  separate evidence; there is no right to infer one from another. "A failed applicability check must precede, rather than be coded as, a defeated-for-K judgment."
* II (evidential failures): unmeasured, instrument-incompatible, scale-incompatible, window-incompatible, boundary-induced invisibility: diagnoses of access, not proofs of occurrence.
* II (comparative protocol; equivalence and reduction): (a) a local philosophical correction, (b) an observationally supported episode attribution, (c) an identified non-redundant implementation or mechanism are different
  claims; Q-equivalence needs a frozen inquiry Q; only a difference that survives an equal-information, equal-cost adversarial comparator supports a non-redundant mechanism, and "a non-collapsible difference is a possible
  outcome of the comparison, never the selection rule".
* III: ignition is "a transition from a specified prior configuration to an episode that meets the stated attribution criteria"; persistence, expiry, re-ignition and re-entry are different operations; re-ignition needs a justified
  relation to the prior episode, not a repeated label; an ignition rate is an index of a frozen detector with its denominator, never "a count of Gaisho in the real".
* X: the fourth study family tests "whether sensor morphology, memory, available world intervention and resource conditions actually determine different future continuation classes, without inferring a thinking subject from
  a classifier"; the seven arms A-G; five non-exchangeable failure registries; separate estimands (no common scalar); withdrawal is domain-relative.
* XII: A_G=supported does not entail truth, freedom, a valid proof, a fair win, a correct procedure or a just allocation, and none of these entails A_G=supported.
* R37's own H1-H3 are three FORMATION HISTORIES of an orientation under a question (retrieved by the question, constituted by it, a partial disposition transformed by it). They are not the laboratory's claim identifiers.
"""

from __future__ import annotations

from typing import Any

R37_REF = "GAISHO R37 (Fujie, 3 November 2026), as read on 2026-11-05 (parts read: see the module docstring)"

# The laboratory's five levels against R37's vocabulary. One of them (the Gaisho operational shape) is a term of the development brief that R37 does not use.
LEVEL_TERMS: dict[str, dict[str, Any]] = {
    "real_operation": {"r37_term": "Real Operation (a P/A term, R37 I and Appendix C 002)", "in_r37": True},
    "operational_shape": {"r37_term": "Operational Shape (a P/A term, R37 Appendix C 003)", "in_r37": True},
    "conceptual_operational_shape": {"r37_term": "C: a warranted conceptual-operational-shape judgment under reidentification and revision conditions (R37 II 5, G-C-N)", "in_r37": True},
    "gaisho_operational_shape": {"r37_term": "NO R37 TERM. R37 has Occ_G(b,t,w) (occurrence), Det_D(K,t) (detectability) and M_G (a candidate causal mediator); the brief's 'Gaisho operational shape' is the laboratory's own level", "in_r37": False},
    "gaisho_attribution": {"r37_term": "A_G(b,t,w;e,K) in {supported, defeated-for-K, unresolved} (R37 II 4); the laboratory also records ASSERTED_BY_RESEARCHER, which R37 does not have", "in_r37": True},
}

# Why the laboratory's synthetic operation is not even a candidate target of A_G (R37: a failed applicability check precedes, and is not coded as, defeated-for-K).
APPLICABILITY_GATE: dict[str, Any] = {
    "passed": False,
    "reason": "no eligible bearer b, no bounded episode interval, no directed relation w and no independent evidential route is specified: a synthetic operation is not a target of an episode attribution, so the gate fails before any A_G value can be assigned",
    "consequence": "the attribution is recorded as UNRESOLVED (R37: unresolved, not defeated-for-K and not a metaphysical zero); it is not an assertion that no thought-related episode occurs, and an operational difference is not evidence of one",
}

# The six registers of R37 (II) plus the target operation S and the occurrence Occ_G, as the laboratory can and cannot record them.
def registers(domain: str) -> dict[str, dict[str, Any]]:
    base: dict[str, dict[str, Any]] = {
        "S": {"r37": "occurrence of the target operation", "lab": "EXECUTED_IN_MODEL", "note": "what the laboratory runs (a decision rule, a declared rule set, the TRUTH-ERROR institution, a planar body)"},
        "Occ_G": {"r37": "occurrence of a Gaisho episode: true or false independently of examination", "lab": "NOT_ASSESSED", "note": "the laboratory has no episode, bearer or interval; it cannot assess occurrence"},
        "Det_D": {"r37": "what a frozen detector registers under K", "lab": "RECORDED_PER_OBSERVATION", "note": "the observation condition and what it could and could not identify (the unobserved classes); a detector output is not an occurrence"},
        "A_G": {"r37": "attribution of a situated thought-related episode: supported / defeated-for-K / unresolved", "lab": "UNRESOLVED", "applicability_gate": "NOT_PASSED", "note": APPLICABILITY_GATE["reason"]},
        "C": {"r37": "conceptual operational shape: reidentification, comparison, transformation, reuse", "lab": "NOT_MODELLED", "note": "no concept formation, reidentification or reuse is modelled"},
        "P": {"r37": "prereflective bodily or practical orientation", "lab": "NOT_MODELLED", "note": "no body in this domain"},
        "E": {"r37": "expressive act or stance", "lab": "NOT_MODELLED", "note": "no expressive acts"},
        "N": {"r37": "normative standing: commitment, entitlement, challenge, justification", "lab": "NOT_MODELLED", "note": "no normative practice is modelled; no entitlement is computed"},
        "I": {"r37": "institutional execution", "lab": "NOT_MODELLED", "note": "no institution"},
    }
    if domain == "005-credit":
        base["I"] = {"r37": "institutional execution", "lab": "EXECUTED_IN_MODEL", "note": "the TRUTH-ERROR institution's score-conditioned access decision (an I_exec analogue of a synthetic institution; it is not an individual's episode and confers no standing)"}
    if domain == "004-body":
        base["P"] = {"r37": "prereflective bodily or practical orientation", "lab": "EXECUTED_IN_MODEL", "note": "the planar body's sensorimotor operation (delayed, noisy sensing; operation lines; feedback); it is a bodily operation, and is not a thinker or an episode"}
    if domain == "001-knowledge":
        base["N"] = {"r37": "normative standing", "lab": "NOT_MODELLED", "note": "R37 keeps epistemic entitlement apart from Gaisho (P/A Dictionary entries 013-024: constitution, detection, attribution, entitlement, defeater, non-accidental success, continuity, withdrawal); the laboratory computes none of the entitlement entries"}
    return base


# Which of the five failure registries of R37 X each kind of the laboratory's negative or unresolved results belongs to. They are non-exchangeable.
FAILURE_REGISTRIES = {
    "F1": "absence of a predicted empirical contrast within a calibrated sensor, scale and horizon",
    "F2": "a fully competent rival's explanatory equivalence",
    "F3": "a blocked or unauthorized intervention",
    "F4": "unresolved bearer- or episode-attribution",
    "F5": "normative disagreement under shared material facts",
}
NEGATIVE_KIND_TO_REGISTRY = {
    "NOT_DETECTED": ("F1", "no difference was detected (95 % interval includes 0): within this sensor, scale, window and horizon; not shown to be zero"),
    "UNOBSERVED": ("F4-access", "an access failure of the observation (a typed unobserved class): unresolved, not zero; it is a diagnosis of access, not of occurrence"),
    "REDUNDANT": ("F2", "a competing explanation holds the same contrast (a Q-redundancy of the compared construction, not a finding about a Gaisho)"),
    "HARMFUL": ("F2", "the compared construction predicts the held-out interventions worse than the competitor"),
    "CRITERION_NEGATIVE": ("F1", "the pre-set operational criterion was negated (an operational test, not an attribution)"),
    "UNRESOLVED": ("F4", "unresolved"),
    "NOT_DONE": ("NOT_RUN", "comparisons and arms that were not run: missing cells, not filled by numbers"),
}

# The seven arms of R37 X for a prospective Gaisho-focused experiment, and what the laboratory has executed of each (missing cells are marked, not filled).
ARMS = {
    "A": {"r37": "an established non-Gaisho model of attention, appraisal, recall or control", "lab": "PARTIAL", "note": "only the static causal, reliability-only and single-factor comparators of the knowledge domain, on a synthetic decision rule; no model of attention, appraisal, recall or control"},
    "B": {"r37": "A plus an explicit episodic-orientation state, no special synchronization", "lab": "NOT_EXECUTED", "note": "the laboratory has no episodic-orientation state"},
    "C": {"r37": "a candidate state-dependent coupling with controlled latencies", "lab": "NOT_EXECUTED", "note": ""},
    "D": {"r37": "a phase-coupling manipulation on independently verified periodic components", "lab": "NOT_EXECUTED", "note": ""},
    "E": {"r37": "a perturbation of the purported Gaisho channel with all other task information preserved", "lab": "NOT_EXECUTED", "note": "no Gaisho channel is specified"},
    "F": {"r37": "a change of reporting and social attribution without a change of the candidate mediator", "lab": "NOT_EXECUTED", "note": ""},
    "G": {"r37": "a change of the institutional gate with the subject episode fixed or unresolved", "lab": "PARTIAL", "note": "domain 005 intervenes on the synthetic institution's score threshold and resource feedback; the subject episode is not modelled (so it is neither fixed nor assessed)"},
}

# The constraints of R37 against what the laboratory implements. IMPLEMENTED = a record or a refusal in the code; PARTIAL; NOT_IMPLEMENTED. Each names the place in R37.
CONSTRAINTS: tuple[dict[str, str], ...] = (
    {"id": "R1", "where": "II 4", "constraint": "Occ_G, Det_D and A_G have different codomains; attribution is {supported, defeated-for-K, unresolved}", "status": "PARTIAL", "how": "registers() records Occ_G NOT_ASSESSED, Det per observation, A_G UNRESOLVED; the laboratory never returns supported or defeated-for-K"},
    {"id": "R2", "where": "II (type error in mixed institutional countermodels)", "constraint": "a failed applicability check precedes, and is not coded as, defeated-for-K", "status": "IMPLEMENTED", "how": "the attribution record carries an applicability gate (NOT_PASSED) next to UNRESOLVED"},
    {"id": "R3", "where": "II G-C-N, four-way test, six-register crosswalk", "constraint": "A_G, C, P, E, N, I are separate registers; no inference among them", "status": "PARTIAL", "how": "registers() keeps them apart; C, E, N are NOT_MODELLED; P is executed only in the body domain, I only in the credit domain (a synthetic institution)"},
    {"id": "R4", "where": "II (evidential failures)", "constraint": "unmeasured, instrument-, scale-, window-incompatible and boundary invisibility are diagnoses of access, not proofs of occurrence", "status": "IMPLEMENTED", "how": "the unobserved classes UNMEASURED, INSTRUMENT_MISFIT, SCALE_MISFIT, TEMPORAL_MISFIT, BOUNDARY_INVISIBLE (the laboratory adds IDENTIFICATION_UNRESOLVED, which R37 does not name)"},
    {"id": "R5", "where": "II 4, X", "constraint": "absent evidence the verdict is unresolved rather than negative", "status": "IMPLEMENTED", "how": "UNRESOLVED / UNOBSERVED are kept and never turned into zero or into a negative"},
    {"id": "R6", "where": "II (comparative protocol)", "constraint": "(a) local philosophical correction, (b) observationally supported episode attribution, (c) identified non-redundant mechanism are different claims", "status": "NOT_IMPLEMENTED", "how": "the laboratory makes none of the three claims for a Gaisho: its comparisons concern constructions of a synthetic decision rule"},
    {"id": "R7", "where": "II (equivalence and reduction)", "constraint": "Q-equivalence needs a frozen inquiry Q; only a difference surviving an equal-information, equal-cost adversarial comparator supports a non-redundant mechanism", "status": "PARTIAL", "how": "the comparators declare information, history, parameters and held-out interventions and a Q block; cost accounting and the adversarial family are not complete"},
    {"id": "R8", "where": "III", "constraint": "ignition is a transition to an episode meeting attribution criteria; persistence, expiry, re-ignition and re-entry are different operations; re-ignition needs a justified relation to the prior episode", "status": "NOT_IMPLEMENTED", "how": "there is no episode: the 'ignition / maintenance / expiry / re-ignition' fields of a research object are OPERATIONAL ANALOGUES (effects, revisions, shift loss) and are labelled so"},
    {"id": "R9", "where": "III", "constraint": "an ignition rate is an index of a frozen detector with its denominator and unresolved cases, not a count of Gaisho", "status": "PARTIAL", "how": "no ignition rate is computed; relations carry their n and intervals, and their unobserved classes"},
    {"id": "R10", "where": "X (fourth family)", "constraint": "test whether sensor morphology, memory, world intervention and resource conditions determine different continuation classes, without inferring a thinking subject from a classifier", "status": "PARTIAL", "how": "domain 004-body (planar body: sensing delay and disturbance interventions, fall as a continuation class) when the XB-TRO path is configured, with morphology (two presets), sensor (visual block), memory (slow adaptation off) and resource conditions as separate named conditions; they are not crossed with one another"},
    {"id": "R21", "where": "V (Scale-Size-Speed), I", "constraint": "scale, size and speed are three separate comparison variables; a change of observational scale or of a record's resolution is not a physical reordering, while a change of the operative size or speed (a queue's capacity, a sanction's speed, a sensor's availability) is causal", "status": "PARTIAL", "how": "records and operations are kept apart (compare_observations: RECORD_DIFFERENCE / OPERATION_DIFFERENCE); the observation has a scale and a speed (descriptive) but no 'size' axis; operative size and speed appear only in the credit and body domains"},
    {"id": "R22", "where": "VIII (Score-Subject Agent; four sites of credit classification)", "constraint": "inclusion in a score regime, a live score-to-allocation pathway, a realized score-conditioned effect and evidence competent for the investigator's attribution are four different types; the institution's schema is not a subject's orientation", "status": "PARTIAL", "how": "domain 005 runs a live gate of a synthetic institution and records the realized access; the four SSA types, the five sites and the retained institutional memory are not recorded as such"},
    {"id": "R23", "where": "III (Sensor-Body and XenoSNN proposals), X (fourth family)", "constraint": "firing records, body configurations, reports and attribution hypotheses need separately specified acquisition conditions; no thinking subject is inferred from a classifier", "status": "PARTIAL", "how": "B2 (bodysnn.py): the body's sensed signal is replayed OPEN-LOOP through the real XenoSNN neuron and the sensor input, spikes, membrane, weights (none), plasticity (none), memory (none), bodily output and environment return are separate records, with the attribution UNRESOLVED; no closed loop exists and no spiking body model with weights or plasticity"},
    {"id": "R11", "where": "X (seven arms)", "constraint": "arms A-G, with missing cells marked, not filled", "status": "PARTIAL", "how": "ARMS records A and G as partial and B-F as NOT_EXECUTED"},
    {"id": "R12", "where": "X (failure registries)", "constraint": "five non-exchangeable failure registries", "status": "IMPLEMENTED", "how": "FAILURE_REGISTRIES and NEGATIVE_KIND_TO_REGISTRY classify the kept negative results; no result is moved from one registry to another"},
    {"id": "R13", "where": "X (estimands)", "constraint": "separate estimands; no common scalar score", "status": "IMPLEMENTED", "how": "no score anywhere; verdicts, relations and registers are kept apart"},
    {"id": "R14", "where": "XII", "constraint": "A_G=supported entails no truth, freedom, validity, fairness, correctness or justice, and none of these entails A_G=supported", "status": "IMPLEMENTED", "how": "model.refuse refuses the eight inferences; the attribution takes no operational input"},
    {"id": "R15", "where": "II (H1-H3: formation histories); Appendix A.3", "constraint": "the formation of an orientation under a question: retrieved, constituted or transformed; identical avowals do not fix the history", "status": "PARTIAL", "how": "countermodels.py enumerates R37's finite models of retrieval and formation exactly (same recorded joint, different E0; the question's effect identified, P(E0=1) not) and checks that no report-only rule decides the property; the third history (a partial disposition transformed by the question) has no finite model in the passages read and is not modelled; no human, neural or machine data"},
    {"id": "R17", "where": "Appendix A.5", "constraint": "A_G is printed as supported, defeated-for-K or unresolved, never coded 1/0/? unless a separate, reversibly mapped serialization is named; a marker with a causal effect leaves the attribution unresolved", "status": "IMPLEMENTED", "how": "the attribution states are the strings of the record; no numeric code exists; where an effect is identified the A_G register reads 'marker has a causal effect; Gaisho attribution unresolved'"},
    {"id": "R18", "where": "Appendix B.2b (R12) and A.3 Results 2-4", "constraint": "equal records can hide unequal intervention effects; a marker's effect does not establish A_G; output identity is not operational identity", "status": "IMPLEMENTED", "how": "the R12 structural study is re-executed (128 seeds, 524,288 matched worlds; the intervals agree with the reported ones); the knowledge domain shows equal accuracy with unequal intervention profiles; neither supports an attribution"},
    {"id": "R19", "where": "Appendix A.5 and VIII (renaming vs executed classification)", "constraint": "a reversible renaming and an executed classification update are different interventions", "status": "IMPLEMENTED", "how": "label_control: renaming changes nothing by construction; an executed update changes the outcome only where the gate reads the label"},
    {"id": "R20", "where": "II (levels of claim: B1 / B2)", "constraint": "B1 (non-exclusivity of description in a worked case) and B2 (operational equivalence for a frozen Q, family, intervention set, horizon and tolerance) are different outcomes; B2 requires evidence or proof within those exact constraints", "status": "NOT_IMPLEMENTED", "how": "no Gaisho-added model exists to be replaced by a rival, so neither B1 nor B2 is established for a Gaisho; the laboratory's Q-redundancy verdicts concern a construction of a synthetic decision rule"},
    {"id": "R16", "where": "Appendix C 013-024 (epistemic family)", "constraint": "five separate results for knowledge: successful target, constituted epistemic state, detection of evidence, third-party attribution, operative withdrawal; non-accidental success is one distinction among them and does not let a Gaisho replace epistemic justification", "status": "PARTIAL", "how": "domain 001 measures a successful target (accuracy), a non-accidental-success operationalisation (do(E), do(S), do(W)) and a reconfiguration under feedback; entitlement, detection and third-party attribution are not computed"},
)


def record_block(domain: str) -> dict[str, Any]:
    return {"reference": R37_REF, "registers": registers(domain), "applicability_gate": APPLICABILITY_GATE, "level_terms": LEVEL_TERMS, "arms": ARMS, "failure_registries": FAILURE_REGISTRIES}
