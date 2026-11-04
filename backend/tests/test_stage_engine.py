"""What the iOS app embeds and the public browser runtime publishes at /runtime/ (ios/scripts/stage_engine.py): the engine, and not the research layers of the local app."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_ONLY_DIRS = ("teoo", "meos", "study", "totalobs", "hpo", "lab", "experiments", "reasonlab", "sbs", "truth_error", "gaisho")
LOCAL_ONLY_FILES = ("service/app.py", "service/meos.py", "service/studies.py", "service/teoo.py", "service/sbs.py", "service/truth_error.py", "lineage.py", "service/gaisho.py")


def _stage(dest: Path) -> list[str]:
    spec = importlib.util.spec_from_file_location("stage_engine", ROOT / "ios" / "scripts" / "stage_engine.py")
    m = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(m)  # type: ignore[union-attr]
    return m.stage(ROOT / "backend", dest)


def test_the_staged_engine_holds_no_research_layer_of_the_local_app(tmp_path):
    files = _stage(tmp_path)
    bad = [f for f in files if f.split("/")[0] in LOCAL_ONLY_DIRS or f in LOCAL_ONLY_FILES]
    assert not bad, f"local-only code would be embedded in the app and published in the browser runtime: {bad}"
    assert any(f.startswith("runtime/") for f in files) and "service/session.py" in files, "the engine itself is staged"


def test_every_staged_module_imports_without_the_excluded_ones(tmp_path):
    files = _stage(tmp_path)
    mods = sorted("xzr." + f[:-3].replace("/", ".").removesuffix(".__init__") for f in files if f.endswith(".py") and not f.endswith("__main__.py"))
    code = (
        "import importlib, sys\n"
        f"mods = {mods!r}\n"
        "failed = []\n"
        "for m in mods:\n"
        "    try:\n"
        "        importlib.import_module(m)\n"
        "    except ModuleNotFoundError as e:\n"
        "        failed.append((m, str(e)))\n"
        "print(failed)\n"
        "sys.exit(1 if failed else 0)\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env={"PYTHONPATH": str(tmp_path), "PATH": "/usr/bin:/bin"}, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-600:] + r.stderr[-400:]
