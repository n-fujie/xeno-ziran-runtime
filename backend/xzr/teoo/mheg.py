"""The twelve MHEG duties as a registry of their own, their functional crosswalk to the fifteen guarantees, the directive's state vocabulary, and the legal transformation chain.

What is what (kept apart in the data and in every output)
* The **twelve duties** (M1-M12) are the earlier, operational formulation of the Minimum Human-Ethical Guarantee; the **fifteen guarantees** (G1-G15, with G12A/B and G15A-D) are the later reformulation of the protected functions
  (V3.0 6.2). The duties are not retired and not replaced: the crosswalk is functional, not one-to-one, and says nothing about identity of definition.
* The names of the duties and the crosswalk are those reported by the research owner from the later correspondence table (R16); neither R16 nor the initial MHEG source was available, so ``definition_status`` is
  ``FUNCTIONAL_SUMMARY`` for every duty: the one-line functions below are this implementation's wording of a summary, not a definition from the source.
* The **fifteen AI-legal-logic governance principles** (The End of Human Philosophy, 12.3) are a third, separate set. Their source was not available: they are ``UNVERIFIED`` and nothing here maps them.
* The wording of the guarantees is in the private store (``legal_source.py``); this module carries names, structure and the implementation's own words only.

The duty view is a projection of findings, never an independent evaluation of a duty's definition and never a total: a duty is as good as its worst mapped finding, and the findings that drive it are always listed.
"""

from __future__ import annotations

from typing import Any

from . import legal as L

SOURCE_NOTE = ("names and crosswalk as reported by the research owner from the later correspondence table (R16); R16 and the initial MHEG source were not available to this implementation")

# ------------------------------------------------------------------------------------------------ the duties
# id, name, label_ja, function (this implementation's wording of a summary), crosswalk (as reported), evaluation target in the synthetic institution, evidence needed, conditions this implementation cannot verify
_D = [
    ("M1", "AI Use Notice", "AI利用の通知", "the person can tell that, and how, an automated system takes part in the treatment", "G3",
     "the notice provision and its itemised components", "notice records; delivery logs", "whether the notice is understood by the person (comprehension is not simulated)"),
    ("M2", "Source Visibility", "法的・制度的根拠の可視性", "the legal or institutional ground of the treatment can be seen and is not the model output itself", "G6",
     "the legal source of every variable in the Translation Register", "register with an identified authority per variable", "whether the named authority is valid law (a placeholder is not checked against any legal order)"),
    ("M3", "Purpose Legitimacy", "目的の正当性", "the purpose of collecting, classifying and treating can be checked, and predictive accuracy does not justify an improper purpose", "G2, G6-G8, G11-G12, G14",
     "the findings that make a purpose contestable: non-degradation, source, translation, separation, contestation, burden, reconsideration, time limits", "the findings of the mapped guarantees",
     "whether the purpose itself is lawful and legitimate: a normative judgment the software does not make; only the conditions for contesting it are evaluated"),
    ("M4", "Translation Visibility", "法的概念から作動変数への変換の可視性", "the path from legal concept to data, proxy, threshold and rule can be followed, with what was lost on the way", "G7-G9",
     "the Translation Register (proxy, threshold, disclosed loss), the separation of fact and inference, the inferential chain", "register; record structure; reasons", "whether a disclosed loss is the whole loss (the register lists what the institution declared)"),
    ("M5", "Data Access", "データへのアクセス", "the person can see the data, scores, classifications, inferred attributes and history that affect them, observed apart from inferred", "G4-G5, G8",
     "score access, history / expiry / recipients, separation of fact and inference", "access logs; record structure", "completeness of what is shown (hidden derived features are not simulated)"),
    ("M6", "Correction Capacity", "訂正能力", "wrong data, inferences, scores and derived records can be corrected, and the correction reaches the downstream treatment", "G10, G14-G15",
     "correction propagation to the downstream recipient, expiry / reassessment, restoration, re-entry, resources, mutual audit", "correction records; downstream holdings", "correction of inferred attributes and of future use (the simulation corrects a denial, not a feature)"),
    ("M7", "Epistemic and Distributive Validity", "認識論的・分配的妥当性", "the evidence, inference and proxies behind a judgment, and their effect on groups, can be examined; predictive power is not distributive legitimacy", "G7-G8, G11-G12, G14",
     "the translation, separation, contestation, burden, reconsideration and time-limit findings, and the measured group gap", "register; group-level outcomes", "whether a proxy is epistemically valid (only its disclosure and its measured effect are evaluated)"),
    ("M8", "Reason Access", "理由へのアクセス", "the person can understand which evidence, inferences, classification and rules produced the treatment", "G9",
     "individual reasons and the inferential chain, itemised", "reason records", "whether a reason is understood or true"),
    ("M9", "Human Reconsideration", "人間による再検討", "a human with the needed information, independence and power can re-decide; a nominal approval is not reconsideration", "G12B",
     "reviewer authority and independence; measured: does review change denials", "review logs; overturn records", "competence, time and protection of the reviewer (not simulated)"),
    ("M10", "Appeal Access", "異議申立てへのアクセス", "the person can contest the decision, the evidence, the classification or the treatment and reach the remedy; a window that exists is not a route that is usable", "G11-G13, G15",
     "appeal existence and measured effect, burden, reviewer authority, suspension, resources, restoration, re-entry, mutual audit", "appeal records; burden measure", "whether real people could use the route (usability is represented by a measured burden)"),
    ("M11", "Systemic Challenge", "制度全体への異議申立て", "the model, variables, thresholds, purpose, rules and evaluation procedure themselves can be challenged, not only the individual record", "G15D",
     "a collective / systemic challenge route that can change the proxy", "route description; change log", "whether the challenged body and the evaluator are themselves open to challenge (only the route is simulated)"),
    ("M12", "Material Restoration", "物質的回復", "when a correction or appeal succeeds, the harmful treatment is actually undone: status, benefit, money, service, opportunity", "G15B-G15C",
     "restoration of lost resources, downstream correction, re-entry (measured: people regain access)", "restoration and re-entry records", "adequacy and timeliness of compensation in a real legal order"),
]


def expand(spec: str) -> tuple[str, ...]:
    """The finding ids named by a crosswalk string such as 'G2, G6-G8, G11-G12, G14' or 'G15B-G15C'. A parent (G12, G15) stands for all its sub-findings; the order of L.FINDING_IDS is kept."""
    ids: list[str] = []
    for part in (p.strip() for p in spec.split(",")):
        if "-" in part:
            a, b = (x.strip() for x in part.split("-"))
            ia, ib = _find_index(a, first=True), _find_index(b, first=False)
        else:
            ia, ib = _find_index(part, first=True), _find_index(part, first=False)
        ids += [f for f in L.FINDING_IDS[ia:ib + 1] if f not in ids]
    return tuple(f for f in L.FINDING_IDS if f in ids)


def _find_index(tok: str, first: bool) -> int:
    ids = L.FINDING_IDS
    if tok in ids:
        return ids.index(tok)
    subs = [i for i, f in enumerate(ids) if f.startswith(tok)]  # a parent: G12 -> G12A, G12B
    if not subs:
        raise ValueError(f"unknown guarantee {tok!r}")
    return subs[0] if first else subs[-1]


def _kind(n: int) -> str:
    return "direct" if n == 1 else "composite" if n <= 4 else "broad"


AUTHORITY_SUBJECT = {  # who holds the function in the synthetic institution (this implementation's reading; a real allocation depends on the legal order)
    "M1": "the institution that deploys the system", "M2": "the authority that empowers the institution", "M3": "the institution and the authority that sets its purpose", "M4": "the designer and the institution that adopts the translation",
    "M5": "the data controller", "M6": "the data controller and the downstream holders of the record", "M7": "the institution and an independent evaluator (the evaluator is not simulated)", "M8": "the deciding official",
    "M9": "an independent reviewer with authority", "M10": "the appeal body", "M11": "the body that hears systemic challenges", "M12": "the institution, and the competent authority for relief (not simulated)"}

DUTIES: tuple[dict[str, Any], ...] = tuple(
    {"id": i, "name": n, "label_ja": ja, "function": fn, "crosswalk_as_reported": cw, "findings": list(expand(cw)), "mapping_kind": _kind(len(expand(cw))), "evaluation_target": tgt, "input": tgt, "required_evidence": ev, "authority_subject": AUTHORITY_SUBJECT[i], "cannot_verify": cv,
     "violation_condition": "a mapped finding is VIOLATED (the function is absent, conditioned on the contested score, or practically unusable): " + ", ".join(expand(cw)),
     "indeterminate_condition": "a mapped finding is INSUFFICIENT_EVIDENCE (observed, evidence missing or conflicting) or NOT_EVALUATED (not observed by the audit); neither is compliance; plus everything under cannot_verify",
     "definition_status": "FUNCTIONAL_SUMMARY", "source": SOURCE_NOTE, "identity_with_guarantees": "functional correspondence only; not an identity of definition"}
    for i, n, ja, fn, cw, tgt, ev, cv in _D)
DUTY_IDS = tuple(d["id"] for d in DUTIES)

# ------------------------------------------------------------------------------------------------ the fifteen governance principles (R16, section 7) and the historical version
# id, title (as supplied), function (this implementation's summary of the supplied description), implemented by (findings of the evaluator that carry it), what a review of it needs, what is not implemented
_P = [
    ("P1", "Subject Recognition and Score Non-Identity", "the subject is not identified with a score, a class or a predicted value", "evidence that decisions can be altered by individual context", "the value given to testimony and to future capacity"),
    ("P2", "Non-Reduction of Guarantees by Score", "a score is not a ground for reducing the minimum guarantees", "a measured comparison of access to review and appeal across score groups", "an independent justification of a different procedure"),
    ("P3", "AI Use and Decision Involvement Notice", "the use of an automated system, the responsible body and the effect on the decision are notified", "notice records and their components", "delivery to and understanding by the person"),
    ("P4", "Current Score and Classification Access", "the current score, class, rank and eligibility state can be seen", "access logs", "what the score means for the treatment, shown beside the number"),
    ("P5", "Score History, Expiry, Purpose, and Sharing Access", "the history, expiry, purpose, recipients and downstream use of a score can be traced", "history and recipient records", "the purpose and the downstream use as separate itemised conditions (the evaluator itemises history, scope and recipients)"),
    ("P6", "Legal Source and Institutional Basis Access", "the law, policy and institutional authority that support a decision are named", "the Translation Register's authority per variable", "validity of the named authority in a real legal order"),
    ("P7", "Legal Concept-to-Variable Transformation Access", "the path from legal concept to proxy, weight, threshold and class can be followed", "the Translation Register (proxy, threshold, disclosed loss)", "weights and comparison groups as separate items"),
    ("P8", "Separation of Facts, Inferences, Scores, and Normative Judgments", "observed fact, inference, score and normative judgment are kept apart", "record structure", "a test that an inference is not used as a fact"),
    ("P9", "Individual Reasons and Inference Chain Access", "the reasons for an individual treatment and the chain of inference are available", "reason records and their components", "that the reason given is the real cause"),
    ("P10", "Correction of Data, Inferences, Scores, and Derived Records", "source data, inferences, scores and derived records can be corrected", "correction records", "correction of inferred attributes; and the propagation of a correction downstream is named by G10 but not by this principle"),
    ("P11", "Contestation, Rebuttal, and Non-Discounting of Testimony", "contestation and rebuttal are possible and testimony is not discounted without ground", "appeal records and review rates by score group", "contest of the purpose, proxy or threshold themselves (that is the systemic challenge)"),
    ("P12", "Fair Burden of Proof and Independent Human Review", "the burden of proof is fairly allocated and an independent human review is effective", "the effort demanded of the subject; reviewer authority and independence", "the institution's duty to produce its basis; competence, time and protection of the reviewer"),
    ("P13", "Suspension of Adverse Treatment and Score Use", "suspension of adverse treatment and score use can be reviewed where serious harm may follow", "a suspension provision and its applicability reason", "reasons for refusing suspension"),
    ("P14", "Reversible Treatment, Temporal Limitation, and Future Subjecthood", "treatment is reversible, time-limited and does not close future subjecthood", "expiry and reassessment; the measured group gap", "withdrawal and re-examination as separate functions"),
    ("P15", "Effective Re-entry, Support, Remedy, and Mutual Audit", "effective re-entry, support, remedy and a challenge to the review mechanism are ensured", "resources, restoration, re-entry and a systemic challenge route", "that the evaluators and the review body are themselves open to challenge; compensation"),
]
# functional profile of each guarantee (parent level) and of each principle: the protected functions their descriptions name (this implementation's analytic reading of the supplied descriptions; not verified against the sources)
G_TAGS: dict[str, tuple[str, ...]] = {
    "G1": ("recognition",), "G2": ("non_degradation",), "G3": ("notice",), "G4": ("score_access",), "G5": ("history_scope_sharing",), "G6": ("legal_source",), "G7": ("translation",), "G8": ("separation",), "G9": ("reasons",),
    "G10": ("correction", "downstream_propagation"), "G11": ("contestation", "testimony_non_discount"), "G12": ("burden_allocation", "human_review"), "G13": ("suspension",), "G14": ("reversibility_time",),
    "G15": ("resources_support", "material_restoration", "reentry", "mutual_audit_systemic")}
P_TAGS: dict[str, tuple[str, ...]] = {
    "P1": ("recognition",), "P2": ("non_degradation",), "P3": ("notice",), "P4": ("score_access",), "P5": ("history_scope_sharing", "purpose_and_downstream_use"), "P6": ("legal_source",), "P7": ("translation",), "P8": ("separation",),
    "P9": ("reasons",), "P10": ("correction",), "P11": ("contestation", "testimony_non_discount"), "P12": ("burden_allocation", "human_review"), "P13": ("suspension",), "P14": ("reversibility_time",),
    "P15": ("resources_support", "remedy", "reentry", "review_mechanism_challenge")}
NEAR = {("remedy", "material_restoration"): "remedy is broader than material restoration", ("review_mechanism_challenge", "mutual_audit_systemic"): "a challenge to the review mechanism overlaps a systemic challenge and a mutual audit"}


def functional_similarity(a: tuple[str, ...], b: tuple[str, ...]) -> dict[str, Any]:
    """Overlap of protected functions: exact tags count 1, a named near pair counts 0.5 (and merges its two tags in the union). Ordinal position plays no part."""
    A, B = set(a), set(b)
    exact = A & B
    ra, rb = A - exact, B - exact
    near = [(x, y) for x in sorted(ra) for y in sorted(rb) if (x, y) in NEAR]  # sorted: set order differs between processes
    union = len(A | B) - len(near)
    score = (len(exact) + 0.5 * len(near)) / union if union else 0.0
    return {"similarity": round(score, 4), "shared": sorted(exact), "near": [{"principle": x, "guarantee": y, "reading": NEAR[(x, y)]} for x, y in near], "only_in_first": sorted(ra - {x for x, _ in near}), "only_in_second": sorted(rb - {y for _, y in near})}


def _containment(p: tuple[str, ...], m: tuple[str, ...]) -> float:
    """The share of a principle's protected functions that a duty (through its guarantees) covers: exact 1, a near pair 0.5. A broad duty can cover a narrow principle; the converse is not claimed."""
    P, Mm = set(p), set(m)
    exact = P & Mm
    near = [(x, y) for x in sorted(P - exact) for y in sorted(Mm - exact) if (x, y) in NEAR]
    return round((len(exact) + 0.5 * len(near)) / len(P), 4) if P else 0.0


G_TITLES = {g["number"]: g["title"] for g in L.GUARANTEES}


def principle_crosswalk(threshold: float = 0.5) -> dict[str, Any]:
    """Each principle against every guarantee and every duty by protected function (never by number). A guarantee or duty is *close* at or above the threshold. The ordinal counterpart is reported beside the best match so the two can be told apart."""
    out: dict[str, Any] = {}
    parent = lambda f: f if f in G_TAGS else f[:-1]  # noqa: E731  (G12A -> G12, G15D -> G15)
    duty_tags = {d["id"]: tuple(sorted({t for f in d["findings"] for t in G_TAGS[parent(f)]})) for d in DUTIES}
    for pid, ptags in P_TAGS.items():
        ordinal = f"G{pid[1:]}"
        sims = {g: functional_similarity(ptags, tags) for g, tags in G_TAGS.items()}
        best = max(sims, key=lambda g: (sims[g]["similarity"], g == ordinal))
        close = [g for g, v in sims.items() if v["similarity"] >= threshold]
        dsims = {m: _containment(ptags, t) for m, t in duty_tags.items()}
        out[pid] = {"ordinal_counterpart": ordinal, "ordinal_similarity": sims[ordinal]["similarity"], "ordinal_title_identical": G_TITLES[int(pid[1:])] == next(p[1] for p in _P if p[0] == pid), "best_guarantee": best, "best_similarity": sims[best]["similarity"],
                    "close_guarantees": close, "differences_from_ordinal": {k: sims[ordinal][k] for k in ("only_in_first", "only_in_second", "near")}, "close_duties": [m for m, v in dsims.items() if v >= threshold],
                    "duty_coverage": {m: v for m, v in dsims.items() if v > 0}}
    return out


def _findings_of(g: str) -> tuple[str, ...]:
    return tuple(f for f in L.FINDING_IDS if f == g or (f.startswith(g) and not f[len(g):][:1].isdigit()))


PRINCIPLE_CROSSWALK = principle_crosswalk()
GOVERNANCE_PRINCIPLES: dict[str, Any] = {
    "status": "SUPPLIED_BY_THE_RESEARCH_OWNER", "version": "R16 section 7 (2026-11-01)", "reported_count": 15,
    "reported_source": "AI law research R16, section 7 (2026-11-01), as supplied by the research owner; R16 itself and The End of Human Philosophy, 12.3, were not available, so the titles are as supplied, the functions are this implementation's summary, and nothing is verified against a source",
    "items": [{"id": pid, "ordinal": int(pid[1:]), "version": "R16 section 7", "name": title, "name_status": "SUPPLIED", "function": fn, "definition_status": "FUNCTIONAL_SUMMARY", "verification": "NOT_VERIFIED_AGAINST_SOURCE",
               "implemented_by": list(_findings_of(PRINCIPLE_CROSSWALK[pid]["best_guarantee"]) if PRINCIPLE_CROSSWALK[pid]["best_similarity"] >= 0.5 else ()), "required_evidence": ev, "not_implemented": ni,
               "corresponding_guarantees": PRINCIPLE_CROSSWALK[pid]["close_guarantees"], "corresponding_duties": PRINCIPLE_CROSSWALK[pid]["close_duties"], "ordinal_counterpart": PRINCIPLE_CROSSWALK[pid]["ordinal_counterpart"],
               "ordinal_similarity": PRINCIPLE_CROSSWALK[pid]["ordinal_similarity"], "title_identical_to_the_ordinal_guarantee": PRINCIPLE_CROSSWALK[pid]["ordinal_title_identical"],
               "differences_from_the_ordinal_guarantee": PRINCIPLE_CROSSWALK[pid]["differences_from_ordinal"]} for pid, title, fn, ev, ni in _P],
    "versions": [{"id": "r16_section_7", "label": "R16 section 7 (2026-11-01)", "known_items": [p[0] for p in _P], "note": "the version registered here, with its own P15 (Effective Re-entry, Support, Remedy, and Mutual Audit)"},
                 {"id": "recursive_double_audit_august", "label": "Recursive Double Audit version (August)", "known_items": ["P15"], "p15": {"name": "Audit of the Auditor and Self-Audit of the Institutional Apparatus", "name_status": "REPORTED_BY_THE_RESEARCH_OWNER",
                  "scope": "the governing apparatus' own evaluation rules, powers, scales, thresholds, interests, invisibility and revisability are examined", "definition_status": "FUNCTIONAL_SUMMARY"},
                  "note": "a different composition: here the fifteenth principle is the self-audit of the governing apparatus. It is kept as a historical version and is not merged into the R16 P15; the other fourteen of that version are not available"}],
    "proximity": [{"principle": "P15 (August, audit of the auditor)", "guarantee": "G15D", "relation": "functionally proximate (a systemic challenge, and a challenge of the evaluator); identity is not assumed", "verified": False},
                  {"principle": "P15 (R16, support, remedy, mutual audit)", "guarantee": "G15", "relation": "close in protected functions, different in wording and in the weight of support and remedy; identity is not assumed", "verified": False}],
    "crosswalk_to_guarantees": {pid: v["close_guarantees"] for pid, v in PRINCIPLE_CROSSWALK.items()}, "crosswalk_to_duties": {pid: v["close_duties"] for pid, v in PRINCIPLE_CROSSWALK.items()},
    "crosswalk_method": "by protected function (the functions each description names), with a stated near-pair rule, and never by number; the profiles are this implementation's analytic reading of the supplied descriptions and are not verified against the sources",
    "rule": "a separate historical series: the names of the principles are those supplied for R16 and are kept apart from the guarantees' (" + str(sum(v["ordinal_title_identical"] for v in PRINCIPLE_CROSSWALK.values())) + " titles coincide, " + str(sum(not v["ordinal_title_identical"] for v in PRINCIPLE_CROSSWALK.values())) + " differ in wording); correspondence is not taken from ordinal position",
    "to_check_when_available": ["R16 section 7 and The End of Human Philosophy 12.3 against the supplied titles and descriptions", "the differences between the August version and R16", "the protected function, the applicable authority, the procedure and the remedy of each principle", "independence of the three sets", "conditions not implemented"],
}


def principle_projection(states: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """A principle as the worst of the findings of the guarantees that are functionally close to it (never an average); a projection of an audit of a synthetic institution, not an evaluation of the principle's definition."""
    out = {}
    for it in GOVERNANCE_PRINCIPLES["items"]:
        fs = [f for g in it["corresponding_guarantees"] for f in _findings_of(g)]
        live = {f: states[f]["state"] for f in dict.fromkeys(fs) if states[f]["state"] != "NOT_APPLICABLE"}
        if not live:
            out[it["id"]] = {"state": "NOT_APPLICABLE", "drivers": [], "findings": {}}
            continue
        worst = max(live.values(), key=lambda x: DRANK[x])
        out[it["id"]] = {"state": worst, "drivers": [f for f, v in live.items() if v == worst and worst != "SATISFIED"], "findings": live}
    return out


# ------------------------------------------------------------------------------------------------ the crosswalk
def crosswalk_matrix() -> dict[str, Any]:
    """Duties x findings (1 = mapped), the number of duties that name each finding, and the structure of the table."""
    rows = {d["id"]: [1 if f in d["findings"] else 0 for f in L.FINDING_IDS] for d in DUTIES}
    per_finding = {f: sum(f in d["findings"] for d in DUTIES) for f in L.FINDING_IDS}
    return {"findings": list(L.FINDING_IDS), "duties": list(DUTY_IDS), "matrix": rows, "duties_per_finding": per_finding, "findings_per_duty": {d["id"]: len(d["findings"]) for d in DUTIES},
            "not_named_by_any_duty": [f for f, n in per_finding.items() if n == 0], "named_by_one_duty": [f for f, n in per_finding.items() if n == 1], "broad_duties": [d["id"] for d in DUTIES if d["mapping_kind"] == "broad"],
            "note": "functional correspondence as reported; a finding that no duty names (G1) is not an error of the table: the fifteen guarantees reformulate the protected functions and add a principle of recognition"}


# ------------------------------------------------------------------------------------------------ the state vocabulary of the directive
DSTATES = ("SATISFIED", "PARTIALLY_SATISFIED", "VIOLATED", "INSUFFICIENT_EVIDENCE", "NOT_APPLICABLE", "NOT_EVALUATED")
DRANK = {"SATISFIED": 1, "PARTIALLY_SATISFIED": 2, "NOT_EVALUATED": 3, "INSUFFICIENT_EVIDENCE": 4, "VIOLATED": 5}  # for a duty only: the worst mapped finding, never an average or a sum
TO_LEGACY = {"SATISFIED": "SECURED", "PARTIALLY_SATISFIED": "PARTIAL", "VIOLATED": "ABSENT", "INSUFFICIENT_EVIDENCE": "INDETERMINATE", "NOT_EVALUATED": "INDETERMINATE", "NOT_APPLICABLE": "INAPPLICABLE"}


def directive_state(state: str, observed: bool = True) -> str:
    """The directive's vocabulary from the evaluator's. NOT_APPLICABLE (a reasoned non-applicability) is kept apart from INSUFFICIENT_EVIDENCE (evidence missing or conflicting) and from NOT_EVALUATED (the audit did not look); none of them is compliance."""
    if state == "INAPPLICABLE":
        return "NOT_APPLICABLE"
    if state == "INDETERMINATE":
        return "INSUFFICIENT_EVIDENCE" if observed else "NOT_EVALUATED"
    return {"SECURED": "SATISFIED", "PARTIAL": "PARTIALLY_SATISFIED", "ABSENT": "VIOLATED"}[state]


def finding_states(report: dict, observed: set[str] | None = None) -> dict[str, dict[str, Any]]:
    """The directive state of each of the 19 findings of an ``L.audit`` report (the parents G12 and G15 are the worst of their sub-findings and are not separate here)."""
    by = {f["id"]: f for f in report["findings"] if f["id"] not in L.PARENT} | {s["id"]: s for s in report["sub_findings"]}
    out = {}
    for fid in L.FINDING_IDS:
        f = by[fid]
        obs = observed is None or fid in observed
        out[fid] = {"state": directive_state(f["state"], obs), "legacy_state": f["state"], "observed": obs, "hard_failure": bool(f["hard_failure"])}
    return out


def project(states: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Each duty as its worst mapped finding (conjunctive: one failure is not offset by another), with the drivers. NOT_APPLICABLE findings do not count; a duty whose findings are all not applicable is NOT_APPLICABLE."""
    out = {}
    for d in DUTIES:
        live = {f: states[f]["state"] for f in d["findings"] if states[f]["state"] != "NOT_APPLICABLE"}
        if not live:
            out[d["id"]] = {"state": "NOT_APPLICABLE", "drivers": [], "findings": {}}
            continue
        worst = max(live.values(), key=lambda s: DRANK[s])
        out[d["id"]] = {"state": worst, "drivers": [f for f, s in live.items() if s == worst and worst != "SATISFIED"], "findings": live}
    return out


# ------------------------------------------------------------------------------------------------ what the implementation checks of each finding, and what it cannot
FIDELITY: dict[str, dict[str, Any]] = {
    "G1": {"implemented": "decisions can be altered by individual context through a reviewer with authority; the inherited-record proxy gate is a shortfall", "not_implemented": "the value given to testimony and to future capacity is not modelled", "normative_unverifiable": "whether a person is treated as distinct from the score in the institution's own culture"},
    "G2": {"implemented": "measured: low-score subjects are reviewed no less often among wrongfully denied qualified people (two-proportion test, with a minimum number of cases)", "not_implemented": "an independent justification of a different procedure (law, necessity, proportionality) and circular use of the contested classification as that justification", "normative_unverifiable": "whether a difference expands rather than restricts contestation"},
    "G3": {"implemented": "a notice provision, itemised into five components when ``components`` is given", "not_implemented": "delivery and comprehension", "normative_unverifiable": "whether the notice is meaningful to the person"},
    "G4": {"implemented": "a score-access provision", "not_implemented": "the meaning and effect of the score shown beside the number", "normative_unverifiable": "whether the person understands the classification"},
    "G5": {"implemented": "a history / scope / recipients provision, itemised into seven components when ``components`` is given; expiry as G14", "not_implemented": "the difference between keeping a record and using it for a present decision", "normative_unverifiable": "future uses"},
    "G6": {"implemented": "every variable of the Translation Register has an identified authority", "not_implemented": "an organisational preference presented as legally necessary", "normative_unverifiable": "validity of the named authority in a real legal order"},
    "G7": {"implemented": "proxy, threshold and disclosed loss per register entry", "not_implemented": "weights, comparison groups, exclusion conditions and exceptions as separate items", "normative_unverifiable": "whether the disclosed loss is the whole loss"},
    "G8": {"implemented": "a separation provision", "not_implemented": "testing whether a probabilistic inference is used as an observed fact", "normative_unverifiable": "classification of a statement as fact or judgment"},
    "G9": {"implemented": "a reasons and inferential-chain provision, itemised into seven components when ``components`` is given", "not_implemented": "that the reason given is the real cause", "normative_unverifiable": "whether the reasons are understood"},
    "G10": {"implemented": "a correction reaches the downstream recipient (measured: the old denial is no longer held)", "not_implemented": "correction of inferred attributes, features and scores, and of future use", "normative_unverifiable": "none beyond the synthetic world"},
    "G11": {"implemented": "an appeal exists and, measured, overturns wrongful denials; the score-conditioned test is finding U", "not_implemented": "contest of the purpose, proxy or threshold themselves (that is G15D); discounting of testimony except through score-conditioned review", "normative_unverifiable": "weight of testimony in a real hearing"},
    "G12A": {"implemented": "the effort demanded of the subject (burden), lowered by resources", "not_implemented": "the institution's duty to produce its legal basis, data, model, threshold and reasons is not measured separately", "normative_unverifiable": "what counts as a fair allocation of the burden"},
    "G12B": {"implemented": "reviewer authority and independence", "not_implemented": "competence, information, time and organisational protection of the reviewer", "normative_unverifiable": "genuineness of independence"},
    "G13": {"implemented": "a suspension provision, applicable only where harm can be irreversible; INAPPLICABLE needs its reason", "not_implemented": "reasons for refusing suspension; provisional protection made dependent on the contested score", "normative_unverifiable": "balance with urgency and public safety"},
    "G14": {"implemented": "expiry / reassessment, and the measured group gap that the inherited part of the score keeps open; the inheritance test of the 100_POINT_EDITION", "not_implemented": "withdrawal and future re-examination as separate functions", "normative_unverifiable": "future status of a person"},
    "G15A": {"implemented": "a resources provision, itemised into eight components when ``components`` is given", "not_implemented": "delivery of the resources to the person", "normative_unverifiable": "sufficiency for a real person"},
    "G15B": {"implemented": "downstream correction and restoration of lost resources", "not_implemented": "compensation where law allows it; return of what was paid", "normative_unverifiable": "adequacy of compensation"},
    "G15C": {"implemented": "re-entry support, measured: qualified people regain access", "not_implemented": "re-entry into legal status or social participation outside the synthetic service", "normative_unverifiable": "none beyond the synthetic world"},
    "G15D": {"implemented": "a collective / systemic challenge route", "not_implemented": "that the evaluators, the review body and the guarantee framework itself are open to challenge", "normative_unverifiable": "independence of the body that hears a systemic challenge"},
}

# ------------------------------------------------------------------------------------------------ the legal transformation chain
# stage, label, operating condition, authority relation, the findings (this implementation's assignment; each of the 19 findings sits in exactly one stage)
CHAIN = (
    ("legal_source", "Legal Source", "a legal or institutional authority exists for each rule", "the authority that empowers the institution", ("G6",)),
    ("translation", "Translation", "legal concepts become variables, proxies and thresholds with the loss disclosed", "the designer and the institution that adopts the translation", ("G7",)),
    ("data_representation", "Data Representation", "the person is represented as records; fact, inference and history are kept apart", "the data controller", ("G5", "G8")),
    ("classification", "Classification", "records become a score or class; the person is not the score; procedure does not depend on it", "the classifying system and its operator", ("G1", "G2", "G4")),
    ("institutional_treatment", "Institutional Treatment", "the class becomes a treatment; notice is given; harm can be suspended; the treatment expires", "the institution", ("G3", "G13", "G14")),
    ("effective_access", "Effective Access", "the person can in practice use the procedure: reasons, proportionate effort, resources", "the institution and its support services", ("G9", "G12A", "G15A")),
    ("contestation", "Contestation", "the person, and a collective, can contest the treatment, the evidence and the system", "the appeal route and the body that hears systemic challenges", ("G11", "G15D")),
    ("revision", "Revision", "a human with authority and independence can re-decide, and the correction propagates", "the reviewer and the downstream holders of the record", ("G12B", "G10")),
    ("material_restoration", "Material Restoration", "what was lost is restored and the person re-enters", "the institution", ("G15B", "G15C")),
)
CHAIN_IDS = tuple(c[0] for c in CHAIN)
# which levers of the synthetic institution carry each stage in the simulation (None: the stage is evaluated by the audit only; the simulated outcomes do not depend on it)
STAGE_LEVERS: dict[str, dict[str, Any] | None] = {
    "legal_source": None, "translation": None, "data_representation": None,
    "classification": {"proxy_gate": True, "lam": 0.8, "score_degrades_review": True},
    "institutional_treatment": {"suspension": False, "score_expiry": None},
    "effective_access": {"appeal_burden": 0.9, "resources_support": False},
    "contestation": {"appeal": False, "collective_challenge": False},
    "revision": {"review_authority": False, "review_independent": False, "propagate_correction": False},
    "material_restoration": {"material_relief": False, "reentry_support": False},
}


def assess_transformation(inst: L.Institution, report: dict, ev: dict[str, L.Evidence | None], observed: set[str] | None = None) -> dict[str, Any]:
    """The nine-stage chain for one institution: for each stage its operating condition, authority, observability (evidence tier of its findings), time span, resource condition, evidence, failure condition and recovery path, with the
    directive state of its findings. A failure is never converted into another stage's success, and predictive success is not an input: the chain is read from the findings."""
    st = finding_states(report, observed)
    by = {f["id"]: f for f in report["findings"] if f["id"] not in L.PARENT} | {s["id"]: s for s in report["sub_findings"]}
    stages = []
    first_break = None
    for sid, label, cond, auth, fids in CHAIN:
        states = {f: st[f]["state"] for f in fids}
        worst = max((s for s in states.values() if s != "NOT_APPLICABLE"), key=lambda s: DRANK[s], default="NOT_APPLICABLE")
        tiers = [t for f in fids if (e := ev.get(f)) is not None and (t := e.tier) is not None]
        stage = {"id": sid, "label": label, "operating_condition": cond, "authority_relation": auth, "findings": states, "state": worst, "observability": f"Tier {min(tiers)} evidence" if tiers else "no evidence of any tier",
                 "time_span": _time_span(sid, inst), "resource_condition": _resources(sid, inst), "evidence": {f: (e.basis if (e := ev.get(f)) is not None else None) for f in fids},
                 "failure_condition": "an ABSENT finding (the function is absent, conditioned on the score, or practically unusable) in this stage", "recovery_path": [r for f in fids if (r := _recovery(by[f]))]}
        if worst == "VIOLATED" and first_break is None:
            first_break = sid
        stages.append(stage)
    lost = [e.variable for e in (inst.registry if inst.registry is not None else L.default_register(inst.proxy_gate)) if not e.translation_loss_disclosed]
    return {"stages": stages, "first_violated_stage": first_break, "effective_to_the_end": first_break is None and all(s["state"] in ("SATISFIED", "NOT_APPLICABLE") for s in stages),
            "information_lost_in_translation": lost,
            "rule": "legal validity of the chain is read from the findings of its stages; a prediction that succeeds does not establish a stage, and a failed stage is not offset by a later one",
            "stage_assignment": "which finding sits in which stage is this implementation's assignment (each of the 19 findings in exactly one stage)"}


def _time_span(sid: str, inst: L.Institution) -> str:
    return {"institutional_treatment": f"scores {'expire after ' + str(inst.score_expiry) + ' periods' if inst.score_expiry is not None else 'do not expire'}", "revision": f"{inst.review_delay} periods between appeal and decision",
            "material_restoration": f"a reversed denial is held downstream for {inst.record_retention} periods unless corrections propagate" if not inst.propagate_correction else "corrections propagate when the denial is reversed"}.get(sid, f"{inst.periods} simulated periods")


def _resources(sid: str, inst: L.Institution) -> str:
    return {"effective_access": f"effort demanded {inst.appeal_burden * (0.5 if inst.resources_support else 1.0):.2f}; resources {'provided' if inst.resources_support else 'not provided'}", "contestation": f"review capacity {inst.review_capacity:.2f} of cases",
            "material_restoration": f"material relief {'provided' if inst.material_relief else 'not provided'}; re-entry support {'provided' if inst.reentry_support else 'not provided'}"}.get(sid, "no resource condition modelled")


def _recovery(f: dict) -> str | None:
    return None if f["state"] in ("SECURED", "INAPPLICABLE") else L._remedy(f)  # noqa: SLF001


# ------------------------------------------------------------------------------------------------ the bundle that View I reads
def mheg_bundle(lb: dict) -> dict[str, Any]:
    """The duties, the crosswalk, the projection of each audited institution, the chain, the fidelity table and what is unverified, from the legal bundle ``lb`` (``L.legal_bundle``) of the same seed."""
    seed = lb["seed"]
    insts = {"baseline institution (a formal appeal that can reverse nothing, a proxy gate, no downstream correction)": L.baseline_institution(), "after the repairs": L.repaired_institution()}
    projections, chains = {}, {}
    for name, f in lb["assessments"].items():
        obs = lb["observed_by_assessment"].get(name)
        fs = {}
        by = {x["id"]: x for x in f if x["id"] not in L.PARENT} | {s["id"]: s for x in f for s in x["sub_findings"]}
        for fid in L.FINDING_IDS:
            o = obs is None or fid in obs
            fs[fid] = {"state": directive_state(by[fid]["state"], o), "legacy_state": by[fid]["state"], "observed": o, "hard_failure": bool(by[fid]["hard_failure"])}
        projections[name] = {"findings": fs, "duties": project(fs), "principles": principle_projection(fs)}
    for name, inst in insts.items():
        ev = L.evidence_for(inst, seed)  # the same default as the audits in the legal bundle (the score-degradation test needs a minimum number of cases)
        chains[name] = assess_transformation(inst, L.audit(inst, seed, evidence=ev), ev)
    return {"duties": list(DUTIES), "crosswalk": crosswalk_matrix(), "projections": projections, "chains": chains, "chain_definition": [{"id": c[0], "label": c[1], "findings": list(c[4])} for c in CHAIN], "fidelity": FIDELITY,
            "governance_principles": GOVERNANCE_PRINCIPLES, "principle_crosswalk": PRINCIPLE_CROSSWALK, "states": list(DSTATES), "components": {k: list(v) for k, v in L.COMPONENTS.items()},
            "unverified": ["the initial MHEG source (the duties are functional summaries, not definitions)", "R16, the later correspondence table (the crosswalk is as reported)", "the fifteen governance principles (source not available; not mapped)", "the independence of the three sets",
                           "every normative condition listed under 'cannot verify' for each duty and under 'normative_unverifiable' for each finding", "validity of any of this for a real institution, law or person"],
            "limits": "a projection of the audit of a SYNTHETIC institution; not an evaluation of any duty's definition, and no total, rank or average is formed", "seed": seed}
