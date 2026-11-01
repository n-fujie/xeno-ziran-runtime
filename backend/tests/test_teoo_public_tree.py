"""The public tree carries no unpublished manuscript, and nothing public depends on one.

The wording of the sources (The Minimum Guarantees of Human Legal Subjecthood V3.0 / 100_POINT_EDITION, ai_law_osr_r2 and revisions of it) is held in a private store outside the repository.
These tests check the tracked tree (and the preview output when it exists), that the public code runs without the store, and that attaching it changes display text only.
"""

from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from xzr.teoo import legal as L
from xzr.teoo import legal_source as LS
from xzr.teoo import manuscript_guard as MG

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
BINARY = (".png", ".jpg", ".jpeg", ".docx", ".pdf", ".npz", ".woff", ".woff2", ".ico", ".xlsx", ".zip", ".pyc")
ALLOWED_DOCX = {"docs/publication/XENO-ZIRAN-3D-research-record.docx"}
FORBIDDEN_NAMES = ("ai_law_osr", "minimum_guarantees", "legal_source_text")
PRIVATE = os.environ.get(LS.ENV)


def _public_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True, check=True).stdout
        return [ROOT / f for f in out.decode().split("\0") if f and (ROOT / f).is_file()]
    except (OSError, subprocess.CalledProcessError):
        skip = {".git", "node_modules", ".venv", "dist", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
        return [Path(d) / f for d, ds, fs in os.walk(ROOT) if not (ds.__setitem__(slice(None), [x for x in ds if x not in skip])) for f in fs]


def _text(p: Path) -> str | None:
    if p.suffix.lower() in BINARY:
        return None
    try:
        raw = p.read_bytes()
        return (gzip.decompress(raw) if p.suffix == ".gz" else raw).decode("utf8")
    except (OSError, ValueError, EOFError):
        return None


def test_no_passage_of_the_unpublished_sources_is_in_the_public_tree():
    assert len(MG.fingerprint()) > 1000
    bad = {}
    for p in _public_files():
        t = _text(p)
        if t and p.name != MG.FILE.name and (hit := MG.find_passages(t)):
            bad[str(p.relative_to(ROOT))] = hit[:2]
    assert not bad, f"passages of the unpublished sources (word positions only): {bad}"


def test_no_manuscript_file_is_in_the_public_tree():
    rel = {str(p.relative_to(ROOT)) for p in _public_files()}
    assert not [r for r in rel if any(k in Path(r).name.lower() for k in FORBIDDEN_NAMES)], "a manuscript or private-store file name is in the tree"
    assert {r for r in rel if r.lower().endswith(".docx")} <= ALLOWED_DOCX, "an unlisted .docx is in the tree (manuscripts are kept in the private store)"


def test_the_guard_detects_a_copied_passage_and_ignores_titles_and_short_phrases():
    if not PRIVATE:
        pytest.skip("needs the private store to take a real passage")
    full = json.loads(Path(PRIVATE).expanduser().read_text())
    passage = full["guarantees"][2]["definition"] + " " + full["guarantees"][9]["definition"]
    assert MG.find_passages(passage) and MG.find_passages(full["non_aggregation"][0])
    assert not MG.find_passages(" ".join(g["title"] for g in full["guarantees"])) and not MG.find_passages("Source: The Minimum Guarantees of Human Legal Subjecthood, Publication Final V3.0, Chapter 6.2")


def test_the_guard_only_holds_hashes():
    data = json.loads(MG.FILE.read_text())
    assert set(data) == {"note", "n", "sample", "sources_sha256", "digests"} and all(len(d) == 10 and int(d, 16) % MG.SAMPLE == 0 for d in data["digests"])


def test_the_public_code_runs_without_the_private_store():
    env = {k: v for k, v in os.environ.items() if k != LS.ENV}
    code = ("import json; from xzr.teoo import legal as L; b = L.legal_bundle(7); "
            "print(json.dumps({'avail': b['text_available'], 'n': len(b['guarantees']), 'defs': [g['definition'] for g in b['guarantees']], 'states': {k: [x['state'] for x in v] for k, v in b['assessments'].items()}}))")
    out = json.loads(subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env={**env, "PYTHONPATH": str(BACKEND)}, capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
    assert out["avail"] is False and out["n"] == 15 and set(out["defs"]) == {None}
    assert all(len(v) == 15 for v in out["states"].values())
    live = L.legal_bundle(7)
    assert out["states"] == {k: [x["state"] for x in v] for k, v in live["assessments"].items()}


@pytest.mark.skipif(not PRIVATE, reason="no private store attached (XZR_TEOO_PRIVATE_SOURCE)")
def test_attaching_the_private_store_changes_display_text_only():
    code = "import json; from xzr.teoo import legal as L; b = L.legal_bundle(7); print(json.dumps({'avail': b['text_available'], 'assessments': b['assessments'], 'audits': b['audits']}, sort_keys=True))"
    out = json.loads(subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env={**os.environ, "PYTHONPATH": str(BACKEND)}, capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
    assert out["avail"] is True

    def strip(a):  # noqa: ANN001, ANN202
        return {k: [{kk: vv for kk, vv in x.items() if kk not in ("definition", "audit_questions")} for x in v] for k, v in a.items()}

    live = L.legal_bundle(7)
    assert strip(out["assessments"]) == json.loads(json.dumps(strip(live["assessments"]), sort_keys=True))
    assert out["audits"] == json.loads(json.dumps(live["audits"], sort_keys=True))


def test_the_fifteen_findings_are_individual_and_never_totalled():
    b = L.legal_bundle(7)
    for a in b["assessments"].values():
        assert [x["number"] for x in a] == list(range(1, 16)) and all(x["state"] in L.STATES for x in a)
    assert not any(k in b for k in ("total", "score", "rank", "average"))
    assert b["synthetic"] is True and "SYNTHETIC" in json.dumps(b["scope"]).upper() or "synthetic" in b["scope"]


def test_a_preview_build_carries_neither_a_manuscript_nor_a_passage():
    out = ROOT / "site-teoo-preview"
    if not out.exists():
        pytest.skip("no preview output built")
    files = [p for p in out.rglob("*") if p.is_file()]
    assert not [p for p in files if p.suffix.lower() in (".docx", ".pdf") or any(k in p.name.lower() for k in FORBIDDEN_NAMES)]
    assert not {str(p.relative_to(out)): MG.find_passages(t) for p in files if (t := _text(p)) and MG.find_passages(t)}
    legal = json.loads((out / "teoo-preview" / "legal.json").read_text())
    assert legal["text_available"] is False and all(g["definition"] is None for g in legal["guarantees"]) and legal["synthetic"] is True
