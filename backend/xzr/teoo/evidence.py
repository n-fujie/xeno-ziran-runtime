"""Evidence Classification: what a record may be called, from its provenance class and kind (never from its values).

Mapped on the claim-status vocabulary of ziran-xeno-simulator (docs/claims.md) only as hints: TEOO's SYNTHETIC records are functional-test data, not a 'synthetic-world
result' (there is no world model behind them), and no record is an 'empirical observation' on its own: a MEASURED observation is a *recorded observation*, and becomes
evidence for a claim only through a protocol (study.protocol, evidence_class confirmatory / exploratory), which is outside this module.
"""

from __future__ import annotations

from .provenance import Kind, Provenance

LABELS = {
    (Provenance.MEASURED, Kind.OBSERVATION): ("recorded observation", "real-world data declared by its source; evidence only through a protocol", "empirical observation (candidate)"),
    (Provenance.SYNTHETIC, Kind.OBSERVATION): ("functional-test data (not evidence)", "generated for testing; no physiological or physical validity is claimed", "implementation property"),
    (Provenance.SYNTHETIC, Kind.REFERENCE_STATE): ("synthetic reference state (not evidence)", "the state of a generator, not of a body", "implementation property"),
    (Provenance.SYNTHETIC, Kind.ESTIMATE): ("estimate from synthetic data (not evidence)", "", "implementation property"),
    (Provenance.SYNTHETIC, Kind.RECONSTRUCTION): ("reconstruction from synthetic data (not evidence)", "", "implementation property"),
    (Provenance.RECONSTRUCTED_ESTIMATE, Kind.ESTIMATE): ("model estimate (not an observation)", "computed from inputs by a method; not observed", "unresolved"),
    (Provenance.RECONSTRUCTED_ESTIMATE, Kind.RECONSTRUCTION): ("reconstruction (not an observation)", "computed from inputs by a method; not observed", "unresolved"),
    (Provenance.MEASURED, Kind.INTERVENTION): ("recorded intervention", "an action that its source declares was carried out; what followed is a separate observation, and the difference is not by itself a cause", "empirical observation (candidate)"),
    (Provenance.SYNTHETIC, Kind.INTERVENTION): ("simulated intervention (not evidence)", "an intervention in generated data", "implementation property"),
    (Provenance.CONCEPTUAL, Kind.INTERVENTION): ("planned intervention (not done)", "a plan; nothing was carried out", "implementation property"),
    (Provenance.SYNTHETIC, Kind.COUNTERFACTUAL_MODEL): ("counterfactual from a model on synthetic data (not an observation)", "what a declared model says would have happened; not what happened", "implementation property"),
    (Provenance.RECONSTRUCTED_ESTIMATE, Kind.COUNTERFACTUAL_MODEL): ("counterfactual from a declared model (not an observation)", "what a declared model says would have happened; not what happened; valid only under its stated assumptions and scope", "unresolved"),
    (Provenance.CONCEPTUAL, Kind.REFERENCE_STATE): ("conceptual illustration (not data)", "a drawing of an idea; not a photograph, not a measurement", "implementation property"),
}


def classify(rec: dict) -> dict:
    p, k = Provenance(rec["provenance"]), Kind(rec["kind"])
    label, note, hint = LABELS[(p, k)]
    tainted = sorted(set(rec["lineage_classes"]) - {p.value})
    return {"record_id": rec["record_id"], "provenance": p.value, "kind": k.value, "label": label, "note": note, "claim_status_hint": hint, "upstream_classes": tainted,
            "is_evidence": False, "why_not": "a record is not evidence; a protocol-registered analysis of MEASURED observations can be"}


def aggregate_guard(records: list[dict], *, mixing_declared: bool = False) -> dict:
    """Aggregating records of different provenance classes needs an explicit declaration (as ziran-xeno-simulator's summarize() requires)."""
    classes = sorted({r["provenance"] for r in records})
    if len(classes) > 1 and not mixing_declared:
        return {"allowed": False, "classes": classes, "reason": "records of different provenance classes are not combined unless the mixing is declared"}
    return {"allowed": True, "classes": classes, "reason": ""}
