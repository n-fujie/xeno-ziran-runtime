"""The intake tool for the legal-governance primary sources: it reports missing files as missing, digests the files it has, and compares two editions without deciding which is authoritative. (The documents used here are tiny
files made by the test to exercise the tool; they are not the sources and say nothing about them.)"""

from __future__ import annotations

import hashlib
import importlib.util
import zipfile
from pathlib import Path

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def docx(path: Path, paras: list[tuple[str, str]]) -> Path:
    body = "".join(f'<w:p><w:pPr><w:pStyle w:val="{st}"/></w:pPr><w:r><w:t>{t}</w:t></w:r></w:p>' for st, t in paras)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document xmlns:w="{W_NS}"><w:body>{body}</w:body></w:document>')
    return path


def tool():
    spec = importlib.util.spec_from_file_location("intake", Path(__file__).resolve().parents[1] / "scripts" / "teoo_legal_source_intake.py")
    m = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(m)  # type: ignore[union-attr]
    return m


def test_a_missing_file_is_reported_missing_and_nothing_is_made_up(tmp_path):
    t = tool()
    d = t.describe(tmp_path / "absent.docx")
    assert d == {"path": str(tmp_path / "absent.docx"), "exists": False}


def test_a_present_file_is_digested_and_outlined(tmp_path):
    t = tool()
    p = docx(tmp_path / "a.docx", [("Heading1", "Chapter 6: Low-Score Subject Guarantee Principle"), ("Normal", "Subject Recognition and Score Non-Identity is guarantee one."), ("Heading1", "Appendix A: MHEG Instrument")])
    d = t.describe(p)
    assert d["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest() and d["paragraphs"] == 3 and d["outline"] == ["Chapter 6: Low-Score Subject Guarantee Principle", "Appendix A: MHEG Instrument"]


def test_two_editions_are_compared_by_paragraph_and_outline_without_choosing_one(tmp_path):
    t = tool()
    a = t.paragraphs(docx(tmp_path / "a.docx", [("Heading1", "Chapter 7: Coverage"), ("Normal", "Shared paragraph."), ("Normal", "Only in the first edition.")]))
    b = t.paragraphs(docx(tmp_path / "b.docx", [("Heading1", "Chapter 7: Coverage"), ("Normal", "Shared paragraph."), ("Normal", "Only in the second edition."), ("Heading1", "Chapter 8: Conjunction")]))
    c = t.compare(a, b)
    assert c["paragraphs_only_in_first"] == 1 and c["paragraphs_only_in_second"] == 2 and c["outline_only_in_second"] == ["Chapter 8: Conjunction"] and "authoritative" not in str(c)


def test_the_provisional_catalogue_is_matched_against_a_text_and_stays_unverified(tmp_path):
    t = tool()
    import json

    cat = json.loads((Path(__file__).resolve().parents[1] / "xzr" / "teoo" / "legal_guarantees_provisional.json").read_text())
    rows = t.match_catalogue(t.paragraphs(docx(tmp_path / "a.docx", [("Normal", "The first is Subject Recognition and Score Non-Identity."), ("Normal", "Something else entirely.")])), cat)
    assert rows[0]["exact_occurrences"] == 1 and rows[1]["exact_occurrences"] == 0 and len(rows) == 15 and cat["verified_against_original"] is False
