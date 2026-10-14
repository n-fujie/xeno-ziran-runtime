"""Copy the simulator engine into an app bundle folder (used by the Xcode build phase and by desktop checks).

    python3 stage_engine.py <backend dir> <dest dir>

Writes <dest>/xzr (the engine package) and <dest>/scenarios (the bundled scenarios). Excluded, because the app does
not run them: the HTTP service module (service/app.py: FastAPI), the experiment harnesses (experiments/, reasonlab/, hpo/, lab/:
desktop research runs whose results are published on the research-results site) and bytecode caches. The copy is
exact otherwise: the app runs the same engine source as the desktop runtime.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

EXCLUDE_DIRS = {"__pycache__", "experiments", "reasonlab", "hpo", "lab"}
EXCLUDE_FILES = {Path("service") / "app.py"}


def stage(backend: Path, dest: Path) -> list[str]:
    src = backend / "xzr"
    out = dest / "xzr"
    if out.exists():
        shutil.rmtree(out)
    copied = []
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if any(part in EXCLUDE_DIRS for part in rel.parts) or rel in EXCLUDE_FILES or p.is_dir():
            continue
        if p.suffix not in (".py", ".npz"):
            continue
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        copied.append(str(rel))
    sc = dest / "scenarios"
    sc.mkdir(parents=True, exist_ok=True)
    for p in sorted((backend / "scenarios").glob("*.json")):
        shutil.copy2(p, sc / p.name)
    return copied


if __name__ == "__main__":
    files = stage(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
    print(f"staged {len(files)} engine files")
