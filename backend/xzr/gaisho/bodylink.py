"""The ONE place where the laboratory reaches outside its own package: the optional link to the XB-TRO planar body.

XB-TRO (branch ``feat/xb-tro`` of this repository, not part of this branch) is a leaf package: it imports numpy and the standard library only and nothing else of ``xzr``. It is NOT merged here. The operator may point the
laboratory at a checkout of it with the environment variable ``XZR_XBTRO_PATH`` (the directory ``.../backend/xzr/xbtro``). The path is never taken from a request. Without it, or if the directory is not that package, the body
domain is NOT EXECUTED and nothing is substituted.

What is done here, and nothing else: read the package's ``.py`` files once to hash them (the hash and the package's own model version are written into every record, so that a record names the body it ran on), and import the
package from that directory under the name ``xbtro`` without touching ``sys.path``. No file is written, no network or process is used, no code is evaluated from a request. This module is excluded from the general file-access
scan of the engine and has a scan of its own (tests/test_gaisho_body.py).
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

ENV = "XZR_XBTRO_PATH"


@dataclass(frozen=True)
class BodyLink:
    config: ModuleType
    engine: ModuleType
    model_version: str
    source_sha256: str
    n_files: int


_CACHE: dict[str, BodyLink | None] = {}


def load() -> BodyLink | None:
    raw = os.environ.get(ENV, "").strip()
    if not raw:
        return None
    if raw in _CACHE:
        return _CACHE[raw]
    _CACHE[raw] = _load(Path(raw))
    return _CACHE[raw]


def _load(pkg: Path) -> BodyLink | None:
    init = pkg / "__init__.py"
    if not pkg.is_dir() or not init.is_file() or not (pkg / "engine.py").is_file() or not (pkg / "config.py").is_file():
        return None
    files = sorted(pkg.glob("*.py"))
    h = hashlib.sha256()
    for f in files:
        h.update(f.name.encode())
        h.update(f.read_bytes())
    mod = sys.modules.get("xbtro")
    if mod is None or Path(getattr(mod, "__file__", "") or "").parent != pkg:
        spec = importlib.util.spec_from_file_location("xbtro", init, submodule_search_locations=[str(pkg)])
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["xbtro"] = mod
        try:
            spec.loader.exec_module(mod)
        except (ImportError, SyntaxError, AttributeError, TypeError, ValueError, OSError):
            sys.modules.pop("xbtro", None)
            return None
    try:
        from importlib import import_module

        return BodyLink(import_module("xbtro.config"), import_module("xbtro.engine"), str(getattr(mod, "MODEL_VERSION", "unknown")), h.hexdigest(), len(files))
    except (ImportError, AttributeError):
        return None
