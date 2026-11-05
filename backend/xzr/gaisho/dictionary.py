"""The correspondence of the laboratory with the P/A Dictionary file ``PA_Dictionary_V40_Integrated.docx``, written after reading it (2026-11-05).

Served by ``/api/gaisho/spec`` only. It is NOT part of an experiment record: the records and their digests (``docs/gaisho/experiments*.json``) were made before this file was read and are not changed by it.

WHICH EDITION THIS IS. The file's cover says "Critical research edition V40, October 2026"; it holds 71 entries (001-071); its embedded document title says V37. R37 (Appendix C.23, and its bibliography) cites "English cumulative research
edition v40, 3 November 2026" with 112 entries (181 pages) and relies on entries 072-077 (Gaisho, Philosophical Operational Shape, Gaisho Ignition / Maintenance / Re-Ignition, Nuance and Coupling, Minimum Constitution, Sensory-Body-XenoSNN
Integration) and 096-097. The 71 headwords of the file are identical to R37's cross-index for 001-071 (checked mechanically, 71 of 71). The word "Gaisho" does not occur in the file. So the file is NOT the edition R37 cites: the entries on which
R37's formation / attribution comparison and its body-XenoSNN statements rest (072-112) were not available, and nothing here is a check against them.

WHAT WAS READ. In full: 001, 003, 004, 013-024 (the epistemic family), 035-038 (SSS), 043-047, 056-061, 064-066, 069. In part: 002. HEADINGS ONLY: 005-012, 025-034, 039-042, 048-055, 062-063, 067-068, 070-071, and the alphabetical locator and index.
The file says of itself that it is "a critical lexicon ... not seventy-one claims of independent discovery" and that inherited simulation numbers are not certified by it: a Dictionary entry is not evidence for a result of this laboratory.

Each constraint below is a paraphrase of what the entries ask of an operational study, with the laboratory's status (IMPLEMENTED / PARTIAL / NOT_IMPLEMENTED) and where. A status is a statement about this code, not about the Dictionary."""

from __future__ import annotations

from typing import Any

DICTIONARY_REF: dict[str, Any] = {
    "title": "P/A - The Dictionary of Operational Philosophy",
    "author": "Naoto Fujie",
    "file": "PA_Dictionary_V40_Integrated.docx",
    "sha256": "a93a48a7069fba503d0d444397e36256b7f6452d948f855aacf33b12711d8e03",
    "cover_edition": "Critical research edition V40, October 2026",
    "embedded_document_title": "P/A - The Dictionary of Operational Philosophy, V37",
    "entries_in_file": 71,
    "edition_cited_by_r37": "English cumulative research edition v40, 3 November 2026 (112 entries, 181 pages)",
    "headwords_001_071_match_r37_index": True,
    "gaisho_in_file": False,
}

EDITION_STATUS = (
    "The file provided is the 71-entry October 2026 edition, not the 112-entry cumulative edition of 3 November 2026 that R37 cites. Entries 001-071 carry the same headwords as R37's cross-index; entries 072-112 "
    "(072 Gaisho, 074 Gaisho Ignition / Maintenance / Re-Ignition, 077 Sensory-Body-XenoSNN Integration, 096-097 and the rest) are not in it, and the word Gaisho does not occur in it. Nothing about Gaisho is checked against the Dictionary."
)

READ_IN_FULL = (1, 3, 4, *range(13, 25), *range(35, 39), *range(43, 48), *range(56, 62), 64, 65, 66, 69)
HEADINGS_ONLY = (*range(5, 13), *range(25, 35), *range(39, 43), *range(48, 56), 62, 63, 67, 68, 70, 71)

# the headwords of the entries cited below, as they are in the file (and in R37's cross-index)
HEADWORDS: dict[int, str] = {
    3: "Operational Shape",
    4: "Operational-Shape Realism",
    13: "Knowledge",
    17: "Knowledge Constitution",
    18: "Knowledge Detection",
    19: "Knowledge Attribution",
    21: "Effective Defeater",
    22: "Non-Accidental Success",
    35: "SSS — Scale, Size, Speed",
    36: "Scale",
    37: "Size",
    38: "Speed",
    43: "Operational Equivalence",
    44: "Operational Reduction",
    58: "XenoSNN",
    60: "XenoBody",
    61: "Active Inference",
    65: "Consciousness",
    66: "Freedom",
}

CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"id": "D1", "entries": (13, 17, 18, 19, 21), "status": "PARTIAL",
     "constraint": "knowledge needs a bearer, a truth-evaluable content, success creditable to a competence and an assessment of defeaters; constitution, detection and attribution are separate; the defeat of a knowledge and the defeat of an assessor's grounds are separate",
     "how": "the knowledge domain is an operational report on a synthetic judgement; it computes no constitution, no detection and no attribution (the attribution stays UNRESOLVED), and keeps its relations apart. The locations of defeat (a defect in the original process, the loss of an auditor's record, a later change of the target) are NOT modelled"},
    {"id": "D2", "entries": (22,), "status": "PARTIAL",
     "constraint": "a non-accidental success needs the class of nearby errors to be specified, not robustness under arbitrary shocks; the choice of the neighbourhood can manufacture either safety or fragility",
     "how": "the laboratory's criterion names its perturbations: do(E), do(S) and the cue decoupled from the state (do(W)). It is one specified set. The sensitivity of the verdict to the choice of the set (other neighbourhoods, other decouplings) was NOT run"},
    {"id": "D3", "entries": (13, 17, 35), "status": "IMPLEMENTED",
     "constraint": "no sufficient condition for knowledge is inferred from a successful discrimination, an attributed content and a measured response; the variables are not collapsed into one knowledge score",
     "how": "no knowledge score exists in the laboratory; every relation is reported with its own interval, and accuracy_improved -> knowledge_established is a refused inference"},
    {"id": "D4", "entries": (43,), "status": "PARTIAL",
     "constraint": "an equivalence is indexed to a target, observation vocabulary, intervention family, resources, tolerance and horizon; a finite suite supports bounded non-equivalence only; operational non-equivalence does not establish unequal knowledge, consciousness, moral standing or metaphysical kind",
     "how": "every record carries its specification (domain, observation, seeds, conditions) and is restored by re-running it; OPERATION_CHANGED is a judgement inside the experiment model. The experiments are exploratory: the intervention families and successor predicates were not preregistered (no frozen protocol)"},
    {"id": "D5", "entries": (3, 4, 44, 61), "status": "PARTIAL",
     "constraint": "a P/A-specific explanatory claim is withdrawn where a matched, equally resourced rival (revision-capable, not a frozen caricature) reproduces the contrast; negative reduction results are published",
     "how": "comparators M0, M1, M4 and the candidate are run, REDUNDANT / HARMFUL / UNRESOLVED verdicts are kept as negative results, and no advantage of the shape vocabulary is claimed. For the body no rival model (a POMDP or adaptive controller with the same privileges) was built: NOT done"},
    {"id": "D6", "entries": (35, 36, 37, 38), "status": "PARTIAL",
     "constraint": "Scale, Size and Speed are separate, non-monotonic and never one score; an SSS-based epistemic conclusion needs a causal pathway",
     "how": "scale, temporal window and speed are separate fields of the Observation and no composite is computed; the laboratory draws no epistemic conclusion from them. Size is not an axis of its own, and a systematic one-axis-at-a-time sweep of the three was not run"},
    {"id": "D7", "entries": (58, 65), "status": "NOT_IMPLEMENTED",
     "constraint": "the name XenoSNN is justified only if an independent intervention signature persists after controls (training seeds, latency and spike timing, parameter and energy budgets, out-of-distribution windows, competitive recurrent and non-spiking baselines); consciousness is not inferred from XenoSNN timing sensitivity",
     "how": "B2 is an open-loop replay of a body's signal through ONE Leaky Integrate-and-Fire neuron with a stipulated encoding. It has none of those controls and no baseline, so it is not a XenoSNN signature study and its spike counts are not evidence of one. No consciousness, knowledge or Gaisho is inferred (attribution UNRESOLVED)"},
    {"id": "D8", "entries": (60,), "status": "PARTIAL",
     "constraint": "XenoBody comparisons need matched morphology, control and environment, failures included; no single task score establishes consciousness",
     "how": "the two bodies of B1 are two XB-TRO PRESETS, not two morphologies: 33 of their 73 configuration entries differ (control, sensors, internal model, integration step 0.01 against 0.005 s, links and joints). A single-block matched comparison was run (bodymatched.py, experiments_body_matched.json: one block taken from the other preset at a time, both directions, 6 seeds, the plain presets reproducing the earlier record). In the coherent cases the delay and disturbance pattern of the human-like preset follows its STRUCTURE block (the machine-like control on the human-like structure gives the same 0.60 / 0.40) and no detected change comes from swapping its control, sensors or internal model; the human-like control on the machine-like structure falls at every cell (a combination that does not hold, not a result about control); the integration step alone moves the machine-like preset (delay effect 0.27 to 0.40, disturbance effect 0.57 to 0.27) and not detectably the human-like one. NOT run: combinations of swaps, a re-tuned control on another structure, other time steps. A difference between the presets is therefore not attributed to morphology. Failures (falls) are the outcome and are kept"},
    {"id": "D9", "entries": (66,), "status": "PARTIAL",
     "constraint": "the size of a reachable set or the number of nominal options is not freedom; the empirical map of reachability does not settle which freedoms ought to be protected; capability approaches are the strong rival",
     "how": "domain 003 reports the reach under declared coupling rules and says nothing about freedom as such (the description of the domains module says so); no normative conclusion is drawn. A capability-approach comparator was NOT run"},
)


def spec_block() -> dict[str, Any]:
    return {"reference": DICTIONARY_REF, "edition_status": EDITION_STATUS, "read_in_full": list(READ_IN_FULL), "headings_only": list(HEADINGS_ONLY), "headwords": {str(k): v for k, v in HEADWORDS.items()}, "constraints": [dict(c, entries=list(c["entries"])) for c in CONSTRAINTS]}
