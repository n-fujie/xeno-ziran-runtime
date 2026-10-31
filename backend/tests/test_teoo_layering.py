"""TEOO layering and non-interference: TEOO imports nothing else from xzr (it runs without MEOS), only the service imports it, and the Stage 4-6 results and the MEOS baseline are untouched."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XZR = ROOT / "xzr"
REPO = ROOT.parent


def _xzr_imports(path: Path) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom):
            if node.level >= 2:
                out.add((node.module or "").split(".")[0])
            elif node.level == 0 and node.module and node.module.split(".")[0] == "xzr":
                out.add(node.module.split(".")[1] if "." in node.module else "")
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] == "xzr":
                    out.add(a.name.split(".")[1] if "." in a.name else "")
    return out - {""}


def test_teoo_imports_nothing_else_from_xzr():
    bad = {p.name: sorted(_xzr_imports(p) - {"teoo"}) for p in (XZR / "teoo").glob("*.py") if _xzr_imports(p) - {"teoo"}}
    assert bad == {}, bad
    for p in (XZR / "teoo").glob("*.py"):  # not even indirectly through a relative import of a sibling package
        for node in ast.walk(ast.parse(p.read_text())):
            assert not (isinstance(node, ast.ImportFrom) and node.level >= 2), p.name


def test_teoo_runs_in_a_fresh_interpreter_without_importing_meos_or_any_other_layer():
    code = ("import sys; import xzr.teoo.synthetic as s, xzr.teoo.ingest, xzr.teoo.xbtro_adapter, xzr.teoo.reconstruction, xzr.teoo.evidence; d = s.make_demo();"
            "bad = sorted(m for m in sys.modules if m.startswith('xzr.') and not m.startswith('xzr.teoo') and m != 'xzr._compat' and not m.startswith('xzr._compat.')); print(len(d['records']), bad)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"})
    assert out.returncode == 0, out.stderr[-400:]
    assert out.stdout.strip() == "1 []", out.stdout  # no other xzr module was loaded (no meos, hpo, totalobs, study, xbtro)


def test_only_the_service_imports_teoo():
    users = {}
    for p in XZR.rglob("*.py"):
        layer = p.relative_to(XZR).parts[0]
        if layer in ("teoo", "__pycache__"):
            continue
        if "teoo" in _xzr_imports(p) or "teoo" in {n.module.split(".")[-1] for n in ast.walk(ast.parse(p.read_text())) if isinstance(n, ast.ImportFrom) and n.module and n.level == 2 and n.module.startswith("teoo")}:
            users[str(p.relative_to(XZR))] = layer
    assert set(users.values()) <= {"service"}, users


def test_the_meos_baseline_digest_is_unchanged_by_the_presence_of_teoo():
    from xzr.meos import engine as E

    rec = E.run_record(E.default_config(), [])
    assert rec["result_digest"] == "b4cf1e522e8bee460eab30ee2a3f86ffd703a3f7969dc21271cf0240aa09adc5" and E.ENGINE_VERSION == "meos-0.5"


def test_stage_4_to_6_results_are_still_what_they_were():
    eco = REPO / "docs" / "ecosystem"
    final = json.loads((eco / "experiments_stage6_final.json").read_text())
    assert [r["irreversible_tick"] for r in final["stress_table"]] == [389, 110, 112, 384, 384, 121]
    for name in ("experiments_stage6.json", "experiments_stage6_refine.json", "experiments_stage6_followup.json", "experiments_stage6_open_windows.json", "experiments_stage5.json", "experiments_stage4.json"):
        assert (eco / name).exists(), name
    assert (REPO / "docs" / "ECOSYSTEM_MEOS_STAGE6.md").read_text().count("INCONCLUSIVE") >= 1  # the performance verdict is still stated as it was


def test_no_teoo_module_writes_into_the_stage_results_or_the_meos_package():
    for p in (XZR / "teoo").glob("*.py"):
        src = p.read_text()
        assert "docs/ecosystem" not in src and "xzr/meos" not in src and "experiments_stage" not in src, p.name
