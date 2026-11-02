"""Export a static, read-only mirror of the research results (frontend built with VITE_STATIC=1 + result files).

    python backend/scripts/export_static.py [out_dir]     # default: site/

The API paths used by the research views are mapped to exported files by vercel.json, so the views read exactly the
same machine-readable results as with the local server. No simulation runs in the mirror.

Large result files are additionally published as sections (data/parts/): a manifest plus content-addressed section
files, a lossless split at the top level (one level deeper for large sections), so that a view fetches only the
sections it renders. The original file is still served unchanged at /api/experiments/<name> (the download).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

RES = ROOT / "backend" / "experiments" / "results"
# the Ziran / Xeno Simulator project page, as built by that repository's site/build.ts (read, never modified)
ZIRAN_SITE = ROOT.parent / "ziran-xeno-simulator" / "site" / "dist"
FILES = {  # API name -> result file
    "reduction": RES / "reduction.json",
    "reason": RES / "reason.json",
    "final_results": RES / "final_results.json",
    "resolution-summary": RES / "resolution" / "summary.json",
    # Heterogeneous Philosophical Operations (published when generated; see docs/HPO.md)
    **{f"hpo-{p.stem}": p for p in sorted((RES / "hpo").glob("*.json"))},
    **{f"lab-{p.stem}": p for p in sorted((RES / "lab").glob("*.json"))},  # laboratory records (xzr.labrun/1)
}
SPLIT_MIN = 512_000  # files larger than this are also published as sections
SECTION_SPLIT = 256_000  # a top-level object section larger than this is split one level further
INLINE_MAX = 16_000  # sections up to this size share one file (the small-sections file)


def _dumps(v: object) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def split_sections(obj: dict) -> list[tuple[list[str], object]]:
    """Ordered (path, value) sections that cover `obj` exactly once, in its key order."""
    out: list[tuple[list[str], object]] = []
    for k, v in obj.items():
        if isinstance(v, dict) and v and len(_dumps(v)) > SECTION_SPLIT:
            out += [([k, k2], v2) for k2, v2 in v.items()]
        else:
            out.append(([k], v))
    return out


def assemble(sections: list[tuple[list[str], object]]) -> dict:
    """Inverse of split_sections (also for any subset of the sections, keeping the original key order)."""
    obj: dict = {}
    for path, v in sections:
        if len(path) == 1:
            obj[path[0]] = v
        else:
            obj.setdefault(path[0], {})[path[1]] = v
    return obj


def _csize(data: bytes) -> int:
    """Deterministic compressed-size estimate (zlib level 9) used by the loader's whole-vs-sections rule."""
    return len(zlib.compress(data, 9))


def plan_sections(name: str, raw: bytes) -> tuple[dict[str, bytes], dict, dict]:
    """Lossless sections of one result file: (files to publish, loader index entry, provenance manifest).

    Each large section is its own content-addressed file; all small sections share one content-addressed file (a
    list of [path, value] in file order), so a view's data arrives in a single round of parallel requests. The index
    entry (embedded in the build) lists every section in file order with its file and compressed size.
    """
    files: dict[str, bytes] = {}

    def publish(text: bytes) -> str:
        url = f"/data/parts/{name}/{hashlib.sha256(text).hexdigest()[:16]}.json"  # content-addressed: immutable
        files[url] = text
        return url

    sections = split_sections(json.loads(raw))
    small = [[path, value] for path, value in sections if len(_dumps(value).encode()) <= INLINE_MAX]
    small_text = _dumps(small).encode()
    small_url = publish(small_text) if small else None
    index_sections: list[list] = []
    manifest_sections: list[dict] = []
    for path, value in sections:
        text = _dumps(value).encode()
        if len(text) <= INLINE_MAX:
            index_sections.append([path, None, 0])
            manifest_sections.append({"path": path, "bytes": len(text), "in": small_url})
        else:
            url = publish(text)
            index_sections.append([path, url, _csize(text)])
            manifest_sections.append({"path": path, "bytes": len(text), "file": url,
                                      "sha256": hashlib.sha256(text).hexdigest()})
    entry = {"full": _csize(raw), "small": [small_url, _csize(small_text)] if small_url else None,
             "sections": index_sections}
    manifest = {"source": f"{name}.json", "source_url": f"/api/experiments/{name}", "source_bytes": len(raw),
                "source_sha256": hashlib.sha256(raw).hexdigest(), "small_sections": small_url,
                "sections": manifest_sections}
    return files, entry, manifest


def write_sections(name: str, files: dict[str, bytes], manifest: dict, out: Path) -> str:
    """Write the section files and the provenance manifest data/parts/<name>.json; returns the manifest URL."""
    for url, text in files.items():
        f = out / url.lstrip("/")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(text)
    (out / "data" / "parts" / f"{name}.json").write_text(_dumps(manifest))
    return f"/data/parts/{name}.json"


# The browser simulator loads nothing from other origins; WebAssembly compilation needs 'wasm-unsafe-eval'.
# (Same policy as the page's meta tag in frontend/vite.config.ts; sent as a header so the worker is bound too.)
WEB_CSP = ("default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; "
           "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:; "
           "object-src 'none'; base-uri 'self'; form-action 'none'; frame-src 'none'")


def vercel_config(views: list[str]) -> dict:
    """Route-aware hosting for the mirror (no SPA catch-all).

    Views are addressed as /?view=<id>. The views of this build are served the app; any other `view` value and any
    unknown path get a real 404 with 404.html, the app shell, which renders the app's Not Found state for that URL.
    """
    known = "^(" + "|".join(views) + ")$"
    return {
        "cleanUrls": False,
        "routes": [
            # the earlier project page served its screenshots from the root
            {"src": "/screenshots/(.*)", "status": 308, "headers": {"Location": "/overview/screenshots/$1"}},
            {"src": "/overview", "status": 308, "headers": {"Location": "/"}},  # the overview is the entry view
            {"src": "/(index\\.html)?", "has": [{"type": "query", "key": "view", "value": known}],
             "dest": "/index.html"},
            {"src": "/(index\\.html)?", "has": [{"type": "query", "key": "view"}], "status": 404,
             "dest": "/404.html"},
            {"src": "/data/parts/[^/]+/[0-9a-f]{16}\\.json",
             "headers": {"Cache-Control": "public, max-age=31536000, immutable"}, "continue": True},
            {"src": "/data/(.*)", "headers": {"Content-Type": "application/json"}, "continue": True},
            # the in-browser simulator (export_web_runtime.py): /app/ is the app, /runtime/ its Pyodide runtime files
            {"src": "/app", "status": 308, "headers": {"Location": "/app/"}},
            {"src": "/runtime/engine-[0-9a-f]{12}\\.zip",
             "headers": {"Cache-Control": "public, max-age=31536000, immutable"}, "continue": True},
            {"src": "/app/(.*)", "headers": {"Content-Security-Policy": WEB_CSP, "X-Content-Type-Options": "nosniff",
                                             "Referrer-Policy": "no-referrer"}, "continue": True},
            {"src": "/api/experiments", "dest": "/data/experiments.json"},
            {"src": "/api/experiments/primitives", "dest": "/data/primitives.json"},
            {"src": "/api/experiments/([^/]+)", "dest": "/data/$1.json"},
            {"handle": "filesystem"},
            {"src": "/(.*)", "status": 404, "dest": "/404.html"},
        ],
    }


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
    # the Vercel project link survives the rebuild, so a redeploy always goes to the same project
    link = out / ".vercel" / "project.json"
    kept_link = link.read_bytes() if link.exists() else None
    if out.exists():
        shutil.rmtree(out)
    # Sections are planned before the build: the build embeds their index, so a view fetches exactly the files it
    # needs in one round of parallel requests (no manifest round trip), or the whole file (see api/results.ts).
    planned = {name: plan_sections(name, src.read_bytes()) for name, src in FILES.items()
               if src.stat().st_size > SPLIT_MIN}
    index = {name: entry for name, (_, entry, _) in planned.items()}
    env = {**os.environ, "VITE_STATIC": "1", "VITE_SECTIONS": _dumps(index)}
    subprocess.run(["npx", "vite", "build", "--outDir", str(out), "--emptyOutDir"], cwd=ROOT / "frontend", env=env,
                   check=True)
    data = out / "data"
    data.mkdir()
    listing = []
    for name, src in FILES.items():
        shutil.copyfile(src, data / f"{name}.json")  # the original, byte for byte
        raw = src.read_bytes()
        entry = {"name": name, "bytes": len(raw), "modified": src.stat().st_mtime,
                 "sha256": hashlib.sha256(raw).hexdigest()}
        if name in planned:
            files, _, manifest = planned[name]
            entry["sections"] = write_sections(name, files, manifest, out)
        listing.append(entry)
    (data / "experiments.json").write_text(json.dumps(listing))
    assert sorted(e["name"] for e in listing if "sections" in e) == sorted(index)  # what the build was told
    ov = out / "overview"
    ov.mkdir()
    shutil.copyfile(ZIRAN_SITE / "index.html", ov / "index.html")
    if (ZIRAN_SITE / "screenshots").exists():
        shutil.copytree(ZIRAN_SITE / "screenshots", ov / "screenshots")
    # the iOS app's privacy policy (App Store Connect points to /privacy/)
    policy = ROOT / "ios" / "AppStore" / "privacy-policy.html"
    if policy.exists():
        (out / "privacy").mkdir()
        shutil.copyfile(policy, out / "privacy" / "index.html")
    from xzr.experiments.catalog import primitives
    (data / "primitives.json").write_text(json.dumps(primitives()))
    views = json.loads((ROOT / "frontend" / "src" / "static-views.json").read_text())
    vercel = vercel_config(views)
    (out / "vercel.json").write_text(json.dumps(vercel, indent=1))
    # Views are addressed by the query (/?view=<id>), so there is no SPA path fallback: an unknown path gets the
    # host's real 404 status, and 404.html is the app shell, which shows its own Not Found state for that path.
    shell = (out / "index.html").read_text()
    (out / "404.html").write_text(shell.replace("<head>", '<head>\n    <meta name="robots" content="noindex" />', 1))
    if kept_link is not None:
        link.parent.mkdir(exist_ok=True)
        link.write_bytes(kept_link)
    print("static mirror written to", out, sorted(p.name for p in data.iterdir()))


if __name__ == "__main__":
    main()
