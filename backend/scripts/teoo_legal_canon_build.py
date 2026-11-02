"""Build the canonical catalogue from the primary sources, verbatim, and split it: python scripts/teoo_legal_canon_build.py V3.docx 100POINT.docx R2.docx PRIVATE_STORE.json

PRIVATE_STORE.json (outside the repository) receives the full text; xzr/teoo/legal_guarantees.json receives only the public specification derived from it (xzr.teoo.legal_source.public_spec).

Nothing is typed in by hand: the titles and definitions of the fifteen guarantees (Chapter 6.2), the audit questions (Appendix A.4), the sub-findings of G12 and G15 (7.6), the finding scale (A.3), the outcome taxonomy and deployment
recommendations (8.4, 8.6), the evidence tiers and burden rules (Appendix B) are copied from V3.0 with their position in the extracted body and the SHA-256 of the file; where the 100_POINT_EDITION or R2 states the same
text, that is recorded. The file is data: a corrected source changes this file, not the code."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("intake", HERE / "teoo_legal_source_intake.py")
intake = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(intake)  # type: ignore[union-attr]


def section(paras: list[dict], head: str, until_style: str = "heading") -> list[tuple[int, dict]]:
    """The entries after the heading whose text starts with `head`, up to the next heading of the same or higher level."""
    out, on, lvl = [], False, None
    for i, p in enumerate(paras):
        st = p["style"].lower()
        if st.startswith("heading"):
            if on and int(st[-1]) <= lvl:
                break
            if not on and p["text"].startswith(head):
                on, lvl = True, int(st[-1])
                continue
        elif on:
            out.append((i, p))
    return out


def main() -> None:
    v3p, v100p, r2p = (Path(x).expanduser() for x in sys.argv[1:4])
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    docs = {n: intake.paragraphs(p) for n, p in (("v3", v3p), ("v100", v100p), ("r2", r2p))}
    v3 = docs["v3"]
    gs = intake.extract_guarantees(v3)
    gs100 = intake.extract_guarantees(docs["v100"])
    gsr2 = intake.extract_guarantees(docs["r2"])
    assert sorted(gs) == list(range(1, 16)), "the fifteen guarantees were not all found"
    # Appendix A.4 questions: Heading3 'G<n> ...' followed by bullet paragraphs
    qs: dict[int, list[str]] = {}
    cur = None
    for p in v3:
        m = re.match(r"^G(\d+)\s", p["text"]) if p["style"].lower() == "heading3" else None
        if m:
            cur = int(m.group(1))
            qs[cur] = []
        elif cur and p["style"].lower().startswith("heading"):
            cur = None
        elif cur and p["text"].startswith("•"):
            qs[cur].append(p["text"].lstrip("• ").strip())
    # 7.6 sub-findings
    s76 = [p["text"] for _, p in section(v3, "7.6 ")]
    sub = {}
    for key, pat in (("G12A", r"G12A[^.]*\."), ("G12B", r"G12B[^.]*\."), ("G15A", r"G15A[^.]*\."), ("G15B", r"G15B[^.]*\."), ("G15C", r"G15C[^.]*\."), ("G15D", r"G15D[^.]*\.")):
        for t in s76:
            m = re.search(pat, t)
            if m:
                sub[key] = m.group(0).strip()
                break
    assert set(sub) == {"G12A", "G12B", "G15A", "G15B", "G15C", "G15D"}, sub
    txt = lambda head: [p["text"] for _, p in section(v3, head)]  # noqa: E731
    outcome = {}
    for p in txt("8.6 "):
        m = re.match(r"^([A-Za-z ]+?):\s", p)
        if m and m.group(1).strip() in ("Constitutive failure", "Procedural failure", "Remedial failure", "Systemic failure", "Indeterminate finding", "Deployment decision"):
            outcome[m.group(1).strip()] = p
    tiers = {f"Tier {n}": next(t for t in txt("B.2 ") if t.startswith(f"Tier {n}")) for n in (1, 2, 3)}
    canon = {
        "schema": "teoo.legal-canon/1",
        "sources": {n: {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for n, p in (("v3_0", v3p), ("v3_0_100_point_edition", v100p), ("ai_law_osr_r2", r2p))},
        "verified_against_original": True,
        "normative_reference": "The Minimum Guarantees of Human Legal Subjecthood, Publication Final V3.0, Chapter 6.2 (identical in the 100_POINT_EDITION and in R2 section 4: all fifteen titles and definitions compared character for character)",
        "editions_identical_for_guarantees": all((gs[k]["title"], gs[k]["definition"]) == (gs100[k]["title"], gs100[k]["definition"]) == (gsr2[k]["title"], gsr2[k]["definition"]) for k in gs) if all(k in gsr2 and k in gs100 for k in gs) else None,
        "guarantees": [{"number": k, "title": gs[k]["title"], "definition": gs[k]["definition"], "source_position": gs[k]["position"], "audit_questions": qs.get(k, []), "audit_questions_source": "V3.0 Appendix A.4"} for k in sorted(gs)],
        "sub_findings": sub,
        "sub_findings_source": "V3.0 section 7.6 (G12A, G12B, G15A-G15D); Appendix A records G1-G15; the report records the sub-findings separately",
        "low_score_subject_guarantee_principle": next(p["text"] for p in v3 if p["text"].startswith("Low-Score Subject Guarantee Principle:")),
        "principle_status": "a transversal rule governing all fifteen, not a sixteenth guarantee (V3.0 7.3); reported as a separate finding U (Appendix A.9)",
        "finding_scale_table_vocabulary": "Secured / Partial / Absent / Indeterminate / Inapplicable (Appendix A table; R2 section 16)",
        "finding_scale_text_vocabulary": next(p for p in txt("A.3 ")),
        "vocabulary_note": "V3.0 uses two vocabularies for the same five findings (Appendix A table: Secured/Partial/Absent/Indeterminate/Inapplicable; A.3 and 8.4 text: Satisfied/Partially Satisfied/Failed/Indeterminate/Not Applicable). R2 section 16 and this implementation use the table's.",
        "non_aggregation": [t for t in txt("8.1 ")] + [t for t in txt("8.4 ")][:1],
        "hard_failure_and_partial_compliance": txt("8.2 "),
        "outcome_taxonomy": outcome,
        "deployment_decision": next((t for t in txt("8.6 ") if t.startswith("Deployment decision:")), None),
        "evidence_tiers": tiers,
        "burden_of_production": txt("B.3 "),
        "burden_of_persuasion": txt("B.4 "),
        "indeterminacy_rule": txt("B.10 "),
        "evidential_conclusion_format": txt("B.14 "),
        "required_evidence": txt("A.8 "),
        "preliminary_low_score_test": txt("A.2 "),
        "ontological_inheritance_tests_100_point_edition": [p["text"] for _, p in section(docs["v100"], "A.6.1 ")] + [p["text"] for _, p in section(docs["v100"], "A.6.2 ")] + [p["text"] for _, p in section(docs["v100"], "A.6.3 ")] + [p["text"] for _, p in section(docs["v100"], "A.6.4 ")],
        "software_limit": next(p["text"] for p in docs["v100"] if p["text"].startswith("This self-limitation is especially important when MHEG is implemented through software.")),
    }
    if len(sys.argv) < 5:
        raise SystemExit("a fifth argument is required: the path of the private store, outside the repository")
    store = Path(sys.argv[4]).expanduser().resolve()
    if store.is_relative_to(Path(__file__).resolve().parents[2]):
        raise SystemExit("refusing to write the full source text inside the repository")
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(canon, indent=1, ensure_ascii=False))
    store.chmod(0o600)
    from xzr.teoo.legal_source import public_spec

    out = Path(__file__).resolve().parents[1] / "xzr" / "teoo" / "legal_guarantees.json"
    out.write_text(json.dumps(public_spec(canon), indent=1, ensure_ascii=False) + "\n")
    print("wrote", out, "(public) and", store, "(private);", "guarantees", len(canon["guarantees"]), "questions", sum(len(g["audit_questions"]) for g in canon["guarantees"]), "outcomes", list(outcome))


if __name__ == "__main__":
    main()
