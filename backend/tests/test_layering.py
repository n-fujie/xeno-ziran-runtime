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
    # HPO: an experiment layer over the runtime (world regimes and provenance from experiments); never service,
    # practice, interpret or reasonlab
    "hpo": {"hpo", "runtime", "lod", "experiments"},
    # laboratory layer: apparatus states derived from the runtime, observing an HPO field; never service or practice
    "lab": {"lab", "hpo", "runtime", "lod", "experiments"},
    # study layer: protocols, seeded batch execution, analysis and paper outputs over hpo / lab (and the shape detector);
    # never service, practice, interpret or reasonlab. Only the service imports it.
    "study": {"study", "hpo", "lab", "runtime", "lod", "experiments", "shapes", "totalobs"},
    # total-observation layer: a synthetic world, observers and a research loop re-using hpo's rule revision and reachability
    # comparison; imports nothing of study, lab, service, practice, interpret or reasonlab (study imports it, never the reverse)
    "totalobs": {"totalobs", "hpo"},
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


# ``_compat`` stands in for third-party libraries missing on iOS (scipy, pydantic); like them it may be used by any
# layer, and it is a leaf: it imports nothing from xzr (checked below).
FOUNDATION = {"_compat"}


def test_compat_is_a_leaf():
    for p in (ROOT / "_compat").glob("*.py"):
        assert _internal_imports(p) <= {"_compat"}, p.name


def test_layers_import_only_what_they_may():
    bad = []
    for layer, allowed in ALLOWED.items():
        for p in (ROOT / layer).glob("*.py"):
            extra = _internal_imports(p) - allowed - FOUNDATION
            if extra:
                bad.append(f"{layer}/{p.name} imports {sorted(extra)}")
    assert bad == [], bad


def test_experiment_layer_is_not_imported_by_the_product_layers():
    """Resolution-escalation machinery (experiments/escalation) is imported by nothing in runtime, shapes, lod,
    compare, scenario, practice or reasonlab; the multi-scale observer never imports reasoning."""
    for layer in ("runtime", "shapes", "lod", "compare", "scenario", "practice", "reasonlab"):
        for p in (ROOT / layer).glob("*.py"):
            assert "experiments" not in _internal_imports(p), p
            assert "hpo" not in _internal_imports(p), p
            assert "lab" not in _internal_imports(p), p
            assert "study" not in _internal_imports(p), p
    assert _internal_imports(ROOT / "shapes" / "multiscale.py") <= {"runtime", "lod", "shapes"}


def test_practice_reaches_runtime_only_through_intervention_records():
    for p in (ROOT / "practice").glob("*.py"):
        src = p.read_text()
        for forbidden in ("runtime.engine", "runtime.ops", "runtime.state"):
            assert forbidden not in src, f"{p.name} uses {forbidden}"
