"""Intake and comparison of the primary sources of the AI legal governance work. Run: python scripts/teoo_legal_source_intake.py V3.docx 100POINT.docx R2.docx [OUT.json]

It reads the files that exist (it never invents the ones that do not), records for each its SHA-256, size, paragraph and heading counts and chapter outline, compares the two editions of *The Minimum Guarantees of Human Legal
Subjecthood* (outline, paragraph-level additions and removals, sentences that carry the fifteen guarantees), and matches the titles of the PROVISIONAL catalogue (xzr/teoo/legal_guarantees.json) against each text. It decides nothing about
which edition is authoritative and changes no catalogue: it produces the evidence for that comparison. Missing files are reported as missing."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
CHAPTER = re.compile(r"^(Chapter\s+\d+|Appendix\s+[A-Z]|Part\s+[IVX]+)\b[:.\s—-]*(.*)$", re.I)


def paragraphs(path: Path) -> list[dict]:
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for p in root.iter(f"{W}p"):
        text = "".join(t.text or "" for t in p.iter(f"{W}t")).strip()
        if not text:
            continue
        st = p.find(f"{W}pPr/{W}pStyle")
        out.append({"text": text, "style": st.get(f"{W}val") if st is not None else ""})
    return out


def outline(paras: list[dict]) -> list[str]:
    return [p["text"][:140] for p in paras if CHAPTER.match(p["text"]) or p["style"].lower().startswith(("heading", "title"))]


def norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def describe(path: Path) -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False}
    paras = paragraphs(path)
    return {"path": str(path), "exists": True, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size, "paragraphs": len(paras), "characters": sum(len(p["text"]) for p in paras),
            "outline": outline(paras), "_paras": paras}


def match_catalogue(paras: list[dict], cat: dict) -> list[dict]:
    texts = [norm(p["text"]) for p in paras]
    rows = []
    for g in cat["guarantees"]:
        t = norm(g["title"])
        exact = [i for i, x in enumerate(texts) if t in x]
        best = max((difflib.SequenceMatcher(None, t, x[: len(t) + 40]).ratio() for x in texts), default=0.0) if not exact else 1.0
        rows.append({"number": g["number"], "provisional_title": g["title"], "exact_occurrences": len(exact), "first_paragraph": exact[0] if exact else None, "best_fuzzy_ratio": round(best, 3)})
    return rows


def compare(a: list[dict], b: list[dict]) -> dict:
    ta, tb = [p["text"] for p in a], [p["text"] for p in b]
    sa, sb = set(map(norm, ta)), set(map(norm, tb))
    only_a = [t[:200] for t in ta if norm(t) not in sb]
    only_b = [t[:200] for t in tb if norm(t) not in sa]
    sm = difflib.SequenceMatcher(None, [norm(t) for t in ta], [norm(t) for t in tb], autojunk=False)
    return {"paragraphs_only_in_first": len(only_a), "paragraphs_only_in_second": len(only_b), "paragraph_similarity_ratio": round(sm.ratio(), 4), "only_in_first_sample": only_a[:40], "only_in_second_sample": only_b[:40],
            "outline_only_in_first": [o for o in outline(a) if norm(o) not in {norm(x) for x in outline(b)}], "outline_only_in_second": [o for o in outline(b) if norm(o) not in {norm(x) for x in outline(a)}]}


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    names = ("V3_0", "V3_0_100_POINT_EDITION", "ai_law_osr_r2")
    docs = {n: describe(Path(p).expanduser()) for n, p in zip(names, sys.argv[1:4], strict=True)}
    cat = json.loads((Path(__file__).resolve().parents[1] / "xzr" / "teoo" / "legal_guarantees.json").read_text())
    report: dict = {"sources": {n: {k: v for k, v in d.items() if k != "_paras"} for n, d in docs.items()}, "catalogue_checked": {"source": cat["source"], "verified_against_original": cat["verified_against_original"]}, "missing": [n for n, d in docs.items() if not d["exists"]]}
    if docs[names[0]]["exists"] and docs[names[1]]["exists"]:
        report["editions_compared"] = compare(docs[names[0]]["_paras"], docs[names[1]]["_paras"])
    report["catalogue_match"] = {n: match_catalogue(d["_paras"], cat) for n, d in docs.items() if d["exists"]}
    report["not_decided_here"] = ["which edition is authoritative", "whether the provisional catalogue is correct", "the definitions, independence and non-substitutability of the fifteen guarantees (read them in the sources)"]
    if len(sys.argv) > 4:
        Path(sys.argv[4]).write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps({"missing": report["missing"], "sources": {n: {k: d.get(k) for k in ("exists", "sha256", "paragraphs")} for n, d in report["sources"].items()}}, indent=1))


if __name__ == "__main__":
    main()
