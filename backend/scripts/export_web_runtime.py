"""Add the in-browser simulator to the static site: the app at /app/ and its runtime files at /runtime/.

    python backend/scripts/export_web_runtime.py [site_dir]        # default: site/ (run export_static.py first)

What is published (everything is a static file; no server code):
  /app/                    the interactive app, built with VITE_WEBRT=1 (frontend `npm run build:web`)
  /runtime/pyodide/        Pyodide core (pyodide.mjs, .asm.wasm/.mjs, python_stdlib.zip) from the npm package `pyodide`
                           (version pinned in frontend/package.json and package-lock.json) and the six wheels the engine
                           needs (numpy, pydantic, pydantic-core, annotated-types, typing-extensions, typing-inspection)
  /runtime/engine-<h>.zip  the engine source (the same files the iOS app embeds, see ios/scripts/stage_engine.py) + scenarios
  /runtime/manifest.json   versions, file hashes, the size limits of the browser build

Integrity: the wheels are downloaded once from the Pyodide release CDN, each checked against the sha256 in the package's own
pyodide-lock.json (which comes from the npm package, whose hash is pinned by package-lock.json), cached under
.cache/web-runtime/ and re-checked on every export. The published lock file lists only these six packages, so Pyodide
itself verifies each wheel's hash again in the visitor's browser. Nothing is loaded from any other origin at run time.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ios" / "scripts"))
import stage_engine  # noqa: E402  (the iOS app's engine staging: one definition of "the engine")

FRONTEND = ROOT / "frontend"
PYODIDE_DIR = FRONTEND / "node_modules" / "pyodide"
CACHE = ROOT / ".cache" / "web-runtime"
NEEDED = ["numpy", "pydantic"]  # direct requirements; their dependencies are resolved from the lock
CORE_FILES = ["pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip"]
# Browser limits (see docs/WEB_RUNTIME.md), from measurements: the engine runs ~4x slower here than on the desktop, and a graph
# without a precomputed hierarchy needs a dense eigensolve that is cubic in n (1.5k nodes ~10 s, 2k ~23 s, 4k > 130 s).
# The bundled scenarios with exported hierarchies (600, 1,500, 3,000 and the two 10,000-node benchmarks) skip that solve.
LIMITS = {
    "XZR_MAX_NODES": "10000", "XZR_MAX_EDGES": "100000", "XZR_MAX_NODES_COMPUTED_HIERARCHY": "1500",
    "XZR_MAX_WARMUP": "3000", "XZR_MAX_SESSIONS": "2",
    "XZR_MAX_STEP_BATCH": "5000", "XZR_MAX_CHECKPOINTS": "12", "XZR_MAX_COMPARE_HORIZON": "300",
    "XZR_MAX_ACTIVE_JOBS_PER_SESSION": "1", "XZR_MAX_QUEUED_JOBS": "2", "XZR_MAX_COMPARES_PER_SESSION": "10",
    "XZR_MAX_JOBS": "40", "XZR_MAX_EXPORT_BYTES": "25000000", "XZR_MAX_BODY": "8000000",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def closure(lock: dict, names: list[str]) -> list[str]:
    pk = lock["packages"]
    seen: list[str] = []

    def visit(n: str) -> None:
        key = n if n in pk else next(k for k in pk if k.lower().replace("_", "-") == n.lower().replace("_", "-"))
        if key in seen:
            return
        seen.append(key)
        for d in pk[key].get("depends", []):
            visit(d)

    for n in names:
        visit(n)
    return seen


def wheel(lock: dict, version: str, key: str) -> bytes:
    meta = lock["packages"][key]
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / meta["file_name"]
    if cached.exists() and sha256(cached.read_bytes()) == meta["sha256"]:
        return cached.read_bytes()
    url = f"https://cdn.jsdelivr.net/pyodide/v{version}/full/{meta['file_name']}"
    with urllib.request.urlopen(url, timeout=180) as r:  # noqa: S310 (fixed https URL)
        data = r.read()
    if sha256(data) != meta["sha256"]:
        raise SystemExit(f"{meta['file_name']}: sha256 differs from the Pyodide lock file; refusing to publish it")
    cached.write_bytes(data)
    return data


def engine_zip(out_dir: Path) -> tuple[str, str, int]:
    stage = CACHE / "engine-stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    files = stage_engine.stage(ROOT / "backend", stage)
    members = sorted(p for p in stage.rglob("*") if p.is_file())
    tmp = CACHE / "engine.zip"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in members:
            zi = zipfile.ZipInfo(str(p.relative_to(stage)), date_time=(2026, 1, 1, 0, 0, 0))  # deterministic bytes
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, p.read_bytes())
    data = tmp.read_bytes()
    name = f"engine-{sha256(data)[:12]}.zip"
    (out_dir / name).write_bytes(data)
    return name, sha256(data), len(files)


def main() -> None:
    site = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "site"
    if not site.is_dir():
        raise SystemExit(f"{site} does not exist; run backend/scripts/export_static.py first")
    if not PYODIDE_DIR.is_dir():
        raise SystemExit("frontend/node_modules/pyodide is missing: run `npm ci` in frontend/")
    pyodide_pkg = json.loads((PYODIDE_DIR / "package.json").read_text())
    version = pyodide_pkg["version"]
    lock = json.loads((PYODIDE_DIR / "pyodide-lock.json").read_text())

    # 1. the app
    build = ROOT / "web-app-build"
    subprocess.run(["npm", "run", "build:web"], cwd=FRONTEND, check=True)
    app = site / "app"
    if app.exists():
        shutil.rmtree(app)
    shutil.copytree(build, app)
    shutil.rmtree(build)

    # 2. the runtime
    rt = site / "runtime"
    if rt.exists():
        shutil.rmtree(rt)
    py = rt / "pyodide"
    py.mkdir(parents=True)
    for f in CORE_FILES:
        shutil.copy2(PYODIDE_DIR / f, py / f)
    keys = closure(lock, NEEDED)
    files = {}
    for k in keys:
        data = wheel(lock, version, k)
        fn = lock["packages"][k]["file_name"]
        (py / fn).write_bytes(data)
        files[fn] = sha256(data)
    trimmed = {"info": lock["info"], "packages": {k: lock["packages"][k] for k in keys}}
    (py / "pyodide-lock.json").write_text(json.dumps(trimmed, separators=(",", ":")))
    for f in CORE_FILES:
        files[f] = sha256((py / f).read_bytes())
    engine, engine_hash, nfiles = engine_zip(rt)
    total = sum(p.stat().st_size for p in rt.rglob("*") if p.is_file())
    manifest = {
        "format": "xzr-web-runtime/1", "engine": engine, "engineSha256": engine_hash, "engineFiles": nfiles,
        "pyodide": version, "python": lock["info"]["python"], "numpy": lock["packages"]["numpy"]["version"],
        "packages": {k: lock["packages"][k]["version"] for k in keys}, "files": files,
        "limits": LIMITS, "sizeBytes": total,
    }
    (rt / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"web runtime written to {site}: app/, runtime/ ({total / 1e6:.1f} MB; engine {engine}, Pyodide {version})")


if __name__ == "__main__":
    main()
