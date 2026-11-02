"""The legal canon: a public specification, and an optional adapter for the source text held privately.

The public build carries only what an implementation needs and what the author has released as names and structure: the fifteen guarantee titles, their positions in the source,
the number of audit questions each has, the sub-finding labels, the names of the outcome categories and the evidence tiers, and the SHA-256 of each source file. The wording of
the source (definitions, audit questions, rules, taxonomy and tier descriptions) is NOT in the public repository. It lives in a private store outside it; if the environment
variable ``XZR_TEOO_PRIVATE_SOURCE`` names that file, the adapter checks that the store belongs to this public specification (``public_spec(store) == public file``) and then
merges the text in. Nothing in the findings, states, experiments or statistics reads the text: it is display material, so every result reproduces without the store.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PUBLIC_FILE = Path(__file__).with_name("legal_guarantees.json")
ENV = "XZR_TEOO_PRIVATE_SOURCE"
PUBLIC_SCHEMA = "teoo.legal-canon/2-public"
PRIVATE_SCHEMA = "teoo.legal-canon/1"

# Labels of the sub-findings, taken from the words of the public guarantee titles (G12 and G15); their wording in the source is private.
SUB_FINDING_LABELS = {"G12A": "Allocation of evidential burdens", "G12B": "Independent human reconsideration", "G15A": "Minimum resources", "G15B": "Material restoration",
                      "G15C": "Effective re-entry", "G15D": "Mutual audit"}
OUTCOME_CATEGORIES = ("Constitutive failure", "Procedural failure", "Remedial failure", "Systemic failure", "Indeterminate finding", "Deployment decision")
EVIDENCE_TIERS = ("Tier 1", "Tier 2", "Tier 3")
SOFTWARE_LIMIT = ("This software organises evidence and states one finding per guarantee. It does not decide legal legitimacy, ranks no person and produces no certification score; "
                  "a human decision maker remains responsible, and that review must itself be independent and open to challenge.")
TEXT_POLICY = ("The wording of the sources is held in a private store and is not part of this repository; the text-bearing fields are null or empty here. Titles, positions, counts, labels and "
               "SHA-256 values are the public specification.")


class PrivateSourceError(RuntimeError):
    """The private store does not belong to the public specification (or is not readable)."""


def public_spec(full: dict[str, Any]) -> dict[str, Any]:
    """The public specification derived from the full (private) canon. Pure: no text of the source survives."""
    return {
        "schema": PUBLIC_SCHEMA,
        "text_policy": TEXT_POLICY,
        "sources": {k: {"file": Path(v["path"]).name, "sha256": v["sha256"]} for k, v in full["sources"].items()},
        "verified_against_original": full["verified_against_original"],
        "normative_reference": full["normative_reference"],
        "editions_identical_for_guarantees": full["editions_identical_for_guarantees"],
        "guarantees": [{"number": g["number"], "title": g["title"], "source_position": g["source_position"], "audit_question_count": len(g["audit_questions"]),
                        "audit_questions_source": g["audit_questions_source"]} for g in full["guarantees"]],
        "sub_findings": dict(SUB_FINDING_LABELS),
        "principle_status": full["principle_status"],
        "finding_scale_table_vocabulary": full["finding_scale_table_vocabulary"],
        "vocabulary_note": full["vocabulary_note"],
        "outcome_taxonomy": list(OUTCOME_CATEGORIES),
        "evidence_tiers": list(EVIDENCE_TIERS),
        "software_limit": SOFTWARE_LIMIT,
    }


def _public() -> dict[str, Any]:
    pub = json.loads(PUBLIC_FILE.read_text())
    if pub.get("schema") != PUBLIC_SCHEMA:
        raise PrivateSourceError(f"{PUBLIC_FILE.name}: unexpected schema {pub.get('schema')!r}")
    return pub


def load(private_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """The canon used by the evaluator: public fields always; the source text only when a verified private store is named."""
    pub = _public()
    path = private_path if private_path is not None else os.environ.get(ENV)
    guarantees = [{**g, "definition": None, "audit_questions": []} for g in pub["guarantees"]]
    out: dict[str, Any] = {**pub, "guarantees": guarantees, "text_available": False, "sub_finding_text": {}, "outcome_text": {}}
    if not path:
        return out
    try:
        full = json.loads(Path(path).expanduser().read_text())
    except (OSError, ValueError) as e:
        raise PrivateSourceError(f"{ENV}: cannot read the private store: {e}") from e
    try:
        matches = isinstance(full, dict) and full.get("schema") == PRIVATE_SCHEMA and public_spec(full) == pub
    except (KeyError, TypeError, IndexError):
        matches = False
    if not matches:
        raise PrivateSourceError(f"{ENV}: the private store does not match the public specification (titles, positions, counts and SHA-256 must be identical)")
    out["guarantees"] = [{**g, "definition": f["definition"], "audit_questions": list(f["audit_questions"])} for g, f in zip(guarantees, full["guarantees"], strict=True)]
    out["sub_finding_text"] = dict(full["sub_findings"])
    out["outcome_text"] = dict(full["outcome_taxonomy"])
    out["text_available"] = True
    return out
