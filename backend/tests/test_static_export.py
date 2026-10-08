"""Routing of the static mirror: known views are served, everything else is a real 404 (no SPA catch-all)."""

import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("export_static", ROOT / "backend" / "scripts" / "export_static.py")
assert _spec and _spec.loader
export_static = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export_static)
VIEWS = json.loads((ROOT / "frontend" / "src" / "static-views.json").read_text())


def _routes():
    return export_static.vercel_config(VIEWS)["routes"]


def test_known_view_values_and_nothing_else_are_served_the_app():
    served = next(r for r in _routes() if r.get("dest") == "/index.html")
    pattern = served["has"][0]["value"]
    # Vercel matches `has` values case-insensitively; the app reads view ids the same way
    for v in [*VIEWS, "OVERVIEW", "Res_Matrix"]:
        assert re.fullmatch(pattern, v, re.I)
    for v in ["", "nonexistent", "network", "practice", "res_matrix_x", "xres_matrix"]:
        assert not re.fullmatch(pattern, v, re.I)


def test_other_view_values_are_404_with_the_app_shell():
    rejected = next(r for r in _routes() if r.get("dest") == "/404.html" and "has" in r)
    assert rejected["status"] == 404 and "value" not in rejected["has"][0]
    assert _routes().index(rejected) > _routes().index(next(r for r in _routes() if r.get("dest") == "/index.html"))


def test_no_catch_all_serves_the_app_and_filesystem_misses_are_404():
    routes = _routes()
    for r in routes:
        if r.get("dest") == "/index.html":
            assert "has" in r  # only a known view value is rewritten to the app
    assert routes[-2] == {"handle": "filesystem"}
    assert routes[-1]["status"] == 404 and routes[-1]["dest"] == "/404.html"


def test_static_view_list_is_unique_and_starts_with_the_entry_view():
    assert VIEWS[0] == "overview" and len(set(VIEWS)) == len(VIEWS)
    assert all(re.fullmatch(r"[a-z_]+", v) for v in VIEWS)


def _reassemble(files: dict, entry: dict) -> dict:
    """What the browser loader does with all sections: big files plus the small-sections file, in index order."""
    small = {tuple(p): v for p, v in json.loads(files[entry["small"][0]])} if entry["small"] else {}
    return export_static.assemble([(path, json.loads(files[url]) if url else small[tuple(path)])
                                   for path, url, _ in entry["sections"]])


def test_sections_reassemble_every_large_result_losslessly_in_key_order(tmp_path):
    for name, src in export_static.FILES.items():
        raw = src.read_bytes()
        original = json.loads(raw)
        sections = export_static.split_sections(original)
        assert export_static.assemble(sections) == original
        assert export_static._dumps(export_static.assemble(sections)) == export_static._dumps(original)  # key order
        if len(raw) > export_static.SPLIT_MIN:
            files, entry, manifest = export_static.plan_sections(name, raw)
            rebuilt = _reassemble(files, entry)
            assert rebuilt == original and export_static._dumps(rebuilt) == export_static._dumps(original)
            assert manifest["source_bytes"] == len(raw)
            assert manifest["source_sha256"] == hashlib.sha256(raw).hexdigest()
            for e in manifest["sections"]:  # every big section file is addressed by its own hash
                if "file" in e:
                    assert hashlib.sha256(files[e["file"]]).hexdigest() == e["sha256"]
                    assert e["file"].endswith(f"/{e['sha256'][:16]}.json")
            url = export_static.write_sections(name, files, manifest, tmp_path)
            assert url == f"/data/parts/{name}.json" and (tmp_path / url.lstrip("/")).is_file()
            assert all((tmp_path / u.lstrip("/")).read_bytes() == t for u, t in files.items())


def test_index_sizes_drive_a_deterministic_rule():
    raw = export_static.FILES["reduction"].read_bytes()
    _, entry, _ = export_static.plan_sections("reduction", raw)
    assert entry["full"] == export_static._csize(raw) > 0
    assert all(c > 0 for _, url, c in entry["sections"] if url) and all(c == 0 for _, url, c in entry["sections"] if not url)


def test_a_subset_of_sections_keeps_the_original_order_of_what_it_contains():
    obj = {"a": 1, "big": {f"k{i}": "x" * 30_000 for i in range(10)}, "c": [1, 2]}
    sections = export_static.split_sections(obj)
    assert [p for p, _ in sections][:3] == [["a"], ["big", "k0"], ["big", "k1"]]
    subset = export_static.assemble([s for s in sections if s[0] != ["big", "k3"]])
    assert list(subset) == ["a", "big", "c"] and "k3" not in subset["big"]


def test_content_addressed_sections_are_cached_as_immutable():
    rule = next(r for r in _routes() if "parts" in r.get("src", ""))
    assert rule["headers"]["Cache-Control"] == "public, max-age=31536000, immutable" and rule["continue"]
    assert re.fullmatch(rule["src"], "/data/parts/reduction/0123456789abcdef.json")
    assert not re.fullmatch(rule["src"], "/data/parts/reduction.json")  # the manifest is revalidated
