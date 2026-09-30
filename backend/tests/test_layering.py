"""Strict one-directional layering, checked on import statements."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "xzr"
ALLOWED = {
    "runtime": {"runtime"},
    "shapes": {"runtime", "lod", "shapes"},
    "lod": {"runtime", "lod"},
    "interpret": {"interpret"},
    "practice": {"practice", "runtime"},  # compiles into runtime intervention records only
    "compare": {"runtime", "lod", "shapes", "compare"},
    "scenario": {"scenario", "runtime", "lod"},
    "reasonlab": {"reasonlab", "practice", "runtime", "scenario"},  # never interpret, shapes or service
}


def _internal_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level > 0 and node.module:
            parts = node.module.split(".")
            out.add(parts[0] if node.level == 2 else path.parent.name)
        elif isinstance(node, ast.ImportFrom) and node.level == 1 and not node.module:
            out.add(path.parent.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("xzr."):
            out.add(node.module.split(".")[1])
    return out


def test_layers_import_only_what_they_may():
    bad = []
    for layer, allowed in ALLOWED.items():
        for p in (ROOT / layer).glob("*.py"):
            extra = _internal_imports(p) - allowed
            if extra:
                bad.append(f"{layer}/{p.name} imports {sorted(extra)}")
    assert bad == [], bad


def test_practice_reaches_runtime_only_through_intervention_records():
    for p in (ROOT / "practice").glob("*.py"):
        src = p.read_text()
        for forbidden in ("runtime.engine", "runtime.ops", "runtime.state"):
            assert forbidden not in src, f"{p.name} uses {forbidden}"
