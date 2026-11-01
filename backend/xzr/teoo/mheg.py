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


DUTIES: tuple[dict[str, Any], ...] = tuple(
    {"id": i, "name": n, "label_ja": ja, "function": fn, "crosswalk_as_reported": cw, "findings": list(expand(cw)), "mapping_kind": _kind(len(expand(cw))), "evaluation_target": tgt, "required_evidence": ev, "cannot_verify": cv,
     "definition_status": "FUNCTIONAL_SUMMARY", "source": SOURCE_NOTE, "identity_with_guarantees": "functional correspondence only; not an identity of definition"}
    for i, n, ja, fn, cw, tgt, ev, cv in _D)
DUTY_IDS = tuple(d["id"] for d in DUTIES)

GOVERNANCE_PRINCIPLES: dict[str, Any] = {
    "status": "UNVERIFIED", "reported_count": 15, "reported_source": "The End of Human Philosophy, Chapter 12, 12.3 (as reported by the research owner); the manuscript was not available",
    "items": [], "crosswalk_to_guarantees": None, "crosswalk_to_duties": None,
    "rule": "these principles are a separate set: the names of the guarantees are not reused for them, they are not mapped here, and nothing about them is displayed as established until the source is read",
    "to_check_when_available": ["correspondence with the fifteen guarantees", "correspondence with the twelve duties", "function in institutional operation", "implementation conditions", "independence", "disagreements", "conditions not implemented"],
}

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
        projections[name] = {"findings": fs, "duties": project(fs)}
    for name, inst in insts.items():
        ev = L.evidence_for(inst, seed)  # the same default as the audits in the legal bundle (the score-degradation test needs a minimum number of cases)
        chains[name] = assess_transformation(inst, L.audit(inst, seed, evidence=ev), ev)
    return {"duties": list(DUTIES), "crosswalk": crosswalk_matrix(), "projections": projections, "chains": chains, "chain_definition": [{"id": c[0], "label": c[1], "findings": list(c[4])} for c in CHAIN], "fidelity": FIDELITY,
            "governance_principles": GOVERNANCE_PRINCIPLES, "states": list(DSTATES), "components": {k: list(v) for k, v in L.COMPONENTS.items()},
            "unverified": ["the initial MHEG source (the duties are functional summaries, not definitions)", "R16, the later correspondence table (the crosswalk is as reported)", "the fifteen governance principles (source not available; not mapped)", "the independence of the three sets",
                           "every normative condition listed under 'cannot verify' for each duty and under 'normative_unverifiable' for each finding", "validity of any of this for a real institution, law or person"],
            "limits": "a projection of the audit of a SYNTHETIC institution; not an evaluation of any duty's definition, and no total, rank or average is formed", "seed": seed}
