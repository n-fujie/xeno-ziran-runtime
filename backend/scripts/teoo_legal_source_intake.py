"""Intake and comparison of the primary sources of the AI legal governance work. Run: python scripts/teoo_legal_source_intake.py V3.docx 100POINT.docx R2.docx [PUBLIC_OUT.json [PRIVATE_FULL.json]]

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


def _text(el) -> str:  # noqa: ANN001
    parts = []
    for x in el.iter():
        if x.tag == W + "t":
            parts.append(x.text or "")
        elif x.tag == W + "tab":
            parts.append("\t")
        elif x.tag in (W + "br", W + "cr"):
            parts.append("\n")
    return "".join(parts)


def paragraphs(path: Path) -> list[dict]:
    """The body in document order: paragraphs (with their style), and the rows of tables (one entry per row, style 'table-row', cells joined by ' | '); then the text of headers, footers, footnotes and endnotes if the file has them."""
    import xml.etree.ElementTree as ET

    out: list[dict] = []
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        body = root.find(f"{W}body")
        for ch in list(body) if body is not None else []:
            if ch.tag == W + "p":
                text = _text(ch).strip()
                if text:
                    st = ch.find(f"{W}pPr/{W}pStyle")
                    out.append({"text": text, "style": st.get(f"{W}val") if st is not None else ""})
            elif ch.tag == W + "tbl":
                for row in ch.iter(W + "tr"):
                    cells = [" / ".join(t for t in (_text(p).strip() for p in c.iter(W + "p")) if t) for c in row.findall(W + "tc")]
                    if any(cells):
                        out.append({"text": " | ".join(cells), "style": "table-row"})
        for name in sorted(n for n in z.namelist() if re.fullmatch(r"word/(header|footer|footnotes|endnotes)\d*\.xml", n)):
            for p in ET.fromstring(z.read(name)).iter(W + "p"):
                text = _text(p).strip()
                if text:
                    out.append({"text": text, "style": name.split("/")[-1].removesuffix(".xml")})
    return out


def coverage_check(path: Path, paras: list[dict]) -> dict:
    """Two independent checks that nothing was dropped, neither of which is a count of paragraphs or characters of the output alone: (1) the non-whitespace characters of all text runs of the document part equal those of all of its
    paragraphs (tables included) as extracted element by element; (2) every non-empty paragraph that occurs anywhere in the document part (table cells included) is present in the extracted body, as an entry or inside a table row."""
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    raw = "".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", xml.decode("utf-8")))
    all_p = [t for t in (_text(p).strip() for p in ET.fromstring(xml).iter(W + "p")) if t]
    ch_runs = len(re.sub(r"\s", "", raw))
    ch_paras = sum(len(re.sub(r"\s", "", t)) for t in all_p)
    body = [p["text"] for p in paras if not p["style"].startswith(("header", "footer", "footnotes", "endnotes"))]
    flat = "\n".join(body)
    missing = [t[:80] for t in all_p if t not in flat]
    return {"characters_in_text_runs": ch_runs, "characters_in_paragraphs": ch_paras, "paragraphs_in_xml": len(all_p), "paragraphs_missing_from_extraction": len(missing), "missing_sample": missing[:5], "complete": ch_runs == ch_paras and not missing}


def outline(paras: list[dict]) -> list[str]:
    return [p["text"][:140] for p in paras if CHAPTER.match(p["text"]) or p["style"].lower().startswith(("heading", "title"))]


def norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def describe(path: Path) -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False}
    paras = paragraphs(path)
    with zipfile.ZipFile(path) as z:
        core = z.read("docProps/core.xml").decode("utf-8", "replace") if "docProps/core.xml" in z.namelist() else ""
    meta = {k: (re.search(rf"<(?:\w+:)?{k}[^>]*>([^<]*)<", core).group(1) if re.search(rf"<(?:\w+:)?{k}[^>]*>([^<]*)<", core) else None) for k in ("title", "subject", "creator", "created", "modified")}
    return {"path": str(path), "exists": True, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size, "paragraphs": len(paras), "characters": sum(len(p["text"]) for p in paras),
            "core_properties": meta, "coverage": coverage_check(path, paras), "outline": outline(paras), "_paras": paras}


GUARANTEE_HEAD = re.compile(r"^Guarantee\s+(\d+)\.\s+(.*)$")


def extract_guarantees(paras: list[dict]) -> dict[int, dict]:
    """The fifteen guarantees of Chapter 6.2 as the document states them: the heading 'Guarantee N. Title' and the paragraph(s) up to the next heading, with the index of the heading in the extracted body (the position in the source)."""
    out: dict[int, dict] = {}
    cur = None
    for i, p in enumerate(paras):
        m = GUARANTEE_HEAD.match(p["text"]) if p["style"].lower().startswith("heading") else None
        if m and int(m.group(1)) not in out:
            cur = int(m.group(1))
            out[cur] = {"number": cur, "title": m.group(2).strip(), "position": i, "definition": []}
        elif cur is not None and p["style"].lower().startswith("heading"):
            cur = None
        elif cur is not None:
            out[cur]["definition"].append(p["text"])
    return {k: {**v, "definition": " ".join(v["definition"])} for k, v in out.items()}


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


def public_report(report: dict) -> dict:
    """The report without any text of the sources: outlines (tables of contents) and paragraph samples are dropped, file paths shortened to names; hashes, counts, coverage and identity flags stay."""
    drop = ("outline", "only_in_first_sample", "only_in_second_sample", "outline_only_in_first", "outline_only_in_second", "missing_sample")

    def clean(x):  # noqa: ANN001, ANN202
        if isinstance(x, dict):
            return {k: ({"file": Path(v).name} if k == "path" and isinstance(v, str) else clean(v)) for k, v in x.items() if k not in drop and k != "core_properties"}
        return [clean(i) for i in x] if isinstance(x, list) else x

    out = clean(report)
    out["withheld"] = "outlines, paragraph samples and document properties of the sources are withheld from the public report; the full report is kept privately"
    return out


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    names = ("V3_0", "V3_0_100_POINT_EDITION", "ai_law_osr_r2")
    docs = {n: describe(Path(p).expanduser()) for n, p in zip(names, sys.argv[1:4], strict=True)}
    cat = json.loads((Path(__file__).resolve().parents[1] / "xzr" / "teoo" / "legal_guarantees_provisional.json").read_text())
    report: dict = {"sources": {n: {k: v for k, v in d.items() if k != "_paras"} for n, d in docs.items()}, "catalogue_checked": {"source": cat["source"], "verified_against_original": cat["verified_against_original"]}, "missing": [n for n, d in docs.items() if not d["exists"]]}
    if docs[names[0]]["exists"] and docs[names[1]]["exists"]:
        report["editions_compared"] = compare(docs[names[0]]["_paras"], docs[names[1]]["_paras"])
    report["catalogue_match"] = {n: match_catalogue(d["_paras"], cat) for n, d in docs.items() if d["exists"]}
    gs = {n: extract_guarantees(d["_paras"]) for n, d in docs.items() if d["exists"]}
    report["guarantees_extracted"] = {n: {k: {"title": v["title"], "position": v["position"], "definition_characters": len(v["definition"])} for k, v in g.items()} for n, g in gs.items()}
    if names[0] in gs and names[1] in gs:
        report["guarantees_between_editions"] = {k: {"title_identical": gs[names[0]][k]["title"] == gs[names[1]][k]["title"], "definition_identical": gs[names[0]][k]["definition"] == gs[names[1]][k]["definition"]} for k in sorted(gs[names[0]]) if k in gs[names[1]]}
    if names[2] in gs and names[0] in gs:
        report["guarantees_r2_vs_v3"] = {k: {"title_identical": gs[names[2]][k]["title"] == gs[names[0]][k]["title"], "definition_identical": gs[names[2]][k]["definition"] == gs[names[0]][k]["definition"]} for k in sorted(gs[names[0]]) if k in gs[names[2]]}
    prov = Path(__file__).resolve().parents[1] / "xzr" / "teoo" / "legal_guarantees_provisional.json"
    if prov.exists() and names[0] in gs:
        pc = json.loads(prov.read_text())
        report["provisional_catalogue_vs_v3"] = [{"number": g["number"], "provisional_title": g["title"], "canonical_title": gs[names[0]][g["number"]]["title"], "title_identical": norm(g["title"]) == norm(gs[names[0]][g["number"]]["title"]),
                                                  "title_similarity": round(difflib.SequenceMatcher(None, norm(g["title"]), norm(gs[names[0]][g["number"]]["title"])).ratio(), 3),
                                                  "definition_similarity": round(difflib.SequenceMatcher(None, norm(g["description"]), norm(gs[names[0]][g["number"]]["definition"])).ratio(), 3)} for g in pc["guarantees"] if g["number"] in gs[names[0]]]
    report["not_decided_here"] = ["which edition is authoritative", "whether the provisional catalogue is correct", "the definitions, independence and non-substitutability of the fifteen guarantees (read them in the sources)"]
    if len(sys.argv) > 4:
        Path(sys.argv[4]).write_text(json.dumps(public_report(report), indent=1, ensure_ascii=False))
    if len(sys.argv) > 5:  # the full report (outlines and samples of the source) goes to a private path only
        Path(sys.argv[5]).write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps({"missing": report["missing"], "sources": {n: {k: d.get(k) for k in ("exists", "sha256", "paragraphs")} for n, d in report["sources"].items()}}, indent=1))


if __name__ == "__main__":
    main()
