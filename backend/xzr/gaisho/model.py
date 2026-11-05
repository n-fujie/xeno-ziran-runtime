"""The research model of the laboratory: the distinctions that must never be merged into one state variable."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from .r37 import APPLICABILITY_GATE, LEVEL_TERMS

# the five levels, each its own record with its own evidence state
LEVELS = ("real_operation", "operational_shape", "conceptual_operational_shape", "gaisho_operational_shape", "gaisho_attribution")
LEVEL_LABELS = {
    "real_operation": "Real Operation",
    "operational_shape": "Operational Shape",
    "conceptual_operational_shape": "Conceptual Operational Shape",
    "gaisho_operational_shape": "Gaisho Operational Shape",
    "gaisho_attribution": "Gaisho Attribution",
}
LEVEL_STATES = (
    "EXECUTED_IN_MODEL",  # the operation was run in the model
    "RECONSTRUCTED",  # a relation was reconstructed from interventions and records
    "NOT_MODELLED",  # the model has no variable for it
    "NOT_ESTABLISHED",  # modelled or assessed, and not established
    "UNRESOLVED",  # the information, observation or intervention needed does not exist
    "CRITERION_NEGATIVE",  # a pre-set test with the power to support it did not
    "ASSERTED_BY_RESEARCHER",  # recorded as asserted by the researcher with independent evidence; the laboratory computes nothing here
)
# the five kinds of what a shape's point or line comes from (every element of a shape carries one):
#   REALIZED_OPERATION               what the model executed (the run, the weights); not an element of a shape: it is what the elements are records OF
#   RECORDED_OBSERVATION             a value recorded through the observation instrument (a CELL: the response of the operation under one intervention pair)
#   RECONSTRUCTED_RELATION           derived from recorded values by a rule of the laboratory (an EDGE or CUT: a neighbour difference and a threshold; a BRANCH POINT: an interpolation)
#   INTERVENTION_RELATIVE_DIFFERENCE a difference between interventions or conditions (the effects, revisions): relations, not elements of one surface
#   VISUALIZATION_PROJECTION         a choice made for drawing (positions, the surface between cells, colours, the marker of an unrecorded cell)
PROVENANCE = ("REALIZED_OPERATION", "RECORDED_OBSERVATION", "RECONSTRUCTED_RELATION", "INTERVENTION_RELATIVE_DIFFERENCE", "VISUALIZATION_PROJECTION")
# what an unobserved difference can be
UNOBSERVED = ("UNMEASURED", "INSTRUMENT_MISFIT", "SCALE_MISFIT", "TEMPORAL_MISFIT", "BOUNDARY_INVISIBLE", "IDENTIFICATION_UNRESOLVED")
# the verdicts of a comparison with a competing explanation (never added into one score)
VERDICTS = ("NON_REDUNDANT", "REDUNDANT", "HARMFUL", "UNRESOLVED", "CRITERION_NEGATIVE")
# what a figure is
FIGURE_KINDS = ("CONCEPTUAL_RECONSTRUCTION", "SYNTHETIC_SIMULATION", "EXECUTED_COMPUTATIONAL_EXPERIMENT", "PHYSICAL_MEASUREMENT", "PHILOSOPHICAL_INTERPRETATION")
OBSERVATION_AXES = ("sensor", "scale", "temporal_window", "speed", "coupling", "resources", "memory", "environment", "intervention", "boundary")

# premises -> conclusions that the research forbids; ``refuse`` answers with the reason
PROHIBITED_INFERENCES: tuple[tuple[str, str, str], ...] = (
    ("spike_fired", "gaisho_fired", "a spike firing is a firing of a neuron model; it is not the firing of a Gaisho"),
    ("concept_classification_succeeded", "gaisho_established", "a successful conceptual classification does not establish a Gaisho"),
    ("ai_internal_state_changed", "thought_established", "a change of the internal state of an AI does not establish thinking"),
    ("shape_3d_complex", "gaisho_exists", "the complexity of a drawn shape is not evidence of a Gaisho"),
    ("accuracy_improved", "knowledge_established", "an improved accuracy does not establish knowledge"),
    ("gaisho_attribution_succeeded", "judgement_about_object_true", "the success of an attribution does not make the judgement about the object true"),
    ("institution_evaluation_changed", "individual_gaisho_changed", "a change of an institution's evaluation is not a change of an individual's Gaisho"),
    ("operational_difference_found", "gaisho_attributed", "an operational difference is not an attribution: the attribution needs independent evidence"),
)
LIMITS = (
    "Synthetic computational experiments with declared constants. A shape drawn from them is a projection of identified relations, not the complete acquisition of any real operation; "
    "nothing here shows anything about human neural activity, the formation of a real Gaisho, or a universal philosophical law."
)


def refuse(premise: str, conclusion: str) -> str | None:
    """The reason a requested inference is refused, or None if it is not one of the forbidden ones."""
    for p, c, why in PROHIBITED_INFERENCES:
        if p == premise and c == conclusion:
            return why
    return None


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


@dataclass
class LevelRecord:
    level: str
    state: str
    evidence: list[str] = field(default_factory=list)
    note: str = ""
    r37_term: str = ""  # the term of the manuscript GAISHO R37 this level corresponds to (or that it has none): see r37.LEVEL_TERMS
    applicability_gate: str = ""  # only for the attribution: R37 requires a failed applicability check to precede, and not to be coded as, a defeated-for-K judgment

    def __post_init__(self) -> None:
        assert self.level in LEVELS and self.state in LEVEL_STATES


def attribute(operational: dict[str, str], bearer: str | None = None, historical_interval: str | None = None, independent_evidence: list[str] | None = None) -> dict:
    """The five levels of one candidate as SEPARATE records. ``operational`` gives the states of the first three levels (what the laboratory executed or reconstructed).

    The Gaisho operational shape needs a bearer and a historical interval; the attribution needs independent evidence supplied by the researcher. **No operational result is ever turned into an attribution here:** without the
    independent evidence the attribution is UNRESOLVED, and with it the laboratory only records that the researcher asserted it (ASSERTED_BY_RESEARCHER): it computes nothing and does not check it.
    """
    ind = list(independent_evidence or [])
    rec = {lv: LevelRecord(lv, operational.get(lv, "NOT_MODELLED")) for lv in LEVELS[:3]}
    if bearer and historical_interval:
        rec["gaisho_operational_shape"] = LevelRecord("gaisho_operational_shape", "NOT_ESTABLISHED", [f"bearer: {bearer}", f"historical interval: {historical_interval}"], "a candidate that can be attributed to a bearer and an interval; it needs thought-related orientation the model does not contain")
    else:
        rec["gaisho_operational_shape"] = LevelRecord("gaisho_operational_shape", "NOT_ESTABLISHED", [], "no bearer and no historical interval: a synthetic operation has neither, so it is not a candidate")
    if ind and bearer and historical_interval:
        rec["gaisho_attribution"] = LevelRecord("gaisho_attribution", "ASSERTED_BY_RESEARCHER", ind, "independent evidence supplied by the researcher; not computed and not checked by the laboratory")
    else:
        rec["gaisho_attribution"] = LevelRecord("gaisho_attribution", "UNRESOLVED", [], "no independent evidence (operational differences are not evidence of a Gaisho)")
    for lv, r in rec.items():
        r.r37_term = str(LEVEL_TERMS[lv]["r37_term"])
    # R37 II: an ineligible or ill-formed target fails a prior applicability gate and is not assigned a metaphysical zero. A bearer, an interval AND independent evidence are what a researcher would have to supply for the gate to be passed
    # (and then the laboratory still computes nothing: it records the assertion).
    rec["gaisho_attribution"].applicability_gate = "PASSED_BY_RESEARCHER_ASSERTION" if (ind and bearer and historical_interval) else "NOT_PASSED: " + str(APPLICABILITY_GATE["reason"])
    return {lv: asdict(r) for lv, r in rec.items()}


@dataclass
class ResearchObject:
    """The twelve questions about a Gaisho candidate. A value is what the experiments identified or the string NOT_IDENTIFIED: no question is assumed answerable, and no feature is assumed to be a necessary condition."""

    id: str
    candidate: str
    relation_to_object: str = "NOT_IDENTIFIED"
    characteristic_configuration: list = field(default_factory=list)
    candidate_core: list = field(default_factory=list)
    ignition_conditions: list = field(default_factory=list)
    maintenance_conditions: list = field(default_factory=list)
    transformation_expiry_conditions: list = field(default_factory=list)
    history_and_reignition: list = field(default_factory=list)
    structural_similarity: list = field(default_factory=list)
    competing_explanations: list = field(default_factory=list)
    intervention_differences: list = field(default_factory=list)
    unresolved_attribution: str = "UNRESOLVED"
