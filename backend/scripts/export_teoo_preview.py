"""Write the fixed SYNTHETIC fixtures of the read-only TEOO preview next to a built preview page.

    PYTHONPATH=. python scripts/export_teoo_preview.py ../site-teoo-preview     # after `npm run build:teoo-preview` in frontend/

The fixtures are the responses of the local API (called in-process), so the preview shows exactly what the local app shows. Before anything is written the script checks that **no record is MEASURED**, that every
record is SYNTHETIC, a reconstruction or a concept, and that every figure verifies; a failure writes nothing. The output also gets a `vercel.json` (headers: no indexing, no framing, strict CSP, no caching of
HTML) and a manifest with the digest of every fixture. There is no API in the output and no route to one.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from xzr.service import app as app_mod
from xzr.teoo import body as B
from xzr.teoo import export as EX
from xzr.teoo import manuscript_guard as MG

ALLOWED = {"SYNTHETIC", "RECONSTRUCTED_ESTIMATE", "CONCEPTUAL"}
GENERATED_AT = "2026-01-01T00:00:00.000000Z"


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "../site-teoo-preview").resolve()
    if not (out / "teoo-preview.html").exists():
        raise SystemExit(f"{out}/teoo-preview.html not found: build the preview page first (npm run build:teoo-preview)")
    c = TestClient(app_mod.app)
    files: dict[str, object] = {}
    demo = c.get("/api/teoo/demo").json()
    files["demo.json"] = demo
    files["session.json"] = c.get("/api/teoo/session").json()
    files["safety.json"] = c.get("/api/teoo/safety").json()
    files["legal.json"] = c.get("/api/teoo/legal").json()
    for name in sorted(B.PRESETS):
        files[f"body-{name}.json"] = c.get(f"/api/teoo/body/{name}").json()
        files[f"coverage-{name}.json"] = c.post("/api/teoo/coverage", json={"records": demo["records"], "body_preset": name}).json()
    for kind in ("timeseries", "body", "limits", "evidence"):
        files[f"figure-{kind}.json"] = c.post("/api/teoo/figure", json={"kind": kind, "generated_at": GENERATED_AT}).json()
    # --- checks before anything is written
    records = files["session.json"]["records"] + demo["records"]  # type: ignore[index]
    bad = [r["record_id"] for r in records if r["provenance"] not in ALLOWED]
    if bad:
        raise SystemExit(f"refusing to write: records that are not SYNTHETIC / estimate / concept: {bad}")
    if any(r["provenance"] == "MEASURED" or "MEASURED" in r["lineage_classes"] for r in records):
        raise SystemExit("refusing to write: a MEASURED record or ancestor is present")
    for kind in ("timeseries", "body", "limits", "evidence"):
        f = files[f"figure-{kind}.json"]
        if f["issues"] or EX.verify_svg(f["svg"]):  # type: ignore[index]
            raise SystemExit(f"refusing to write: figure {kind} does not verify")
    if not files["legal.json"]["synthetic"] or len(files["legal.json"]["guarantees"]) != 15 or not files["legal.json"]["catalogue"]["sha256"]:
        raise SystemExit("refusing to write: the legal bundle is not a synthetic bundle on a checksummed source catalogue")
    if files["legal.json"].get("text_available") or any(MG.find_passages(json.dumps(doc, ensure_ascii=False)) for doc in files.values()):
        raise SystemExit("refusing to write: the preview would carry the wording of an unpublished source (unset XZR_TEOO_PRIVATE_SOURCE; the preview is built from the public specification only)")
    if files["safety.json"]["production_ready"] or files["safety.json"]["human_measurement_ingestion_allowed"]:  # type: ignore[index]
        raise SystemExit("refusing to write: the production gate is open")
    d = out / "teoo-preview"
    d.mkdir(exist_ok=True)
    manifest = {}
    for name, doc in files.items():
        text = json.dumps(doc, ensure_ascii=True, separators=(",", ":"))
        (d / name).write_text(text)
        manifest[name] = {"sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text)}
    (d / "manifest.json").write_text(json.dumps({"note": "fixed SYNTHETIC fixtures written by backend/scripts/export_teoo_preview.py from the local API; no MEASURED record; production gate closed", "records_checked": len(records), "files": manifest}, indent=1))
    (out / "index.html").write_text((out / "teoo-preview.html").read_text())
    csp = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-src 'none'; frame-ancestors 'none'"
    sec = [{"key": "X-Robots-Tag", "value": "noindex, nofollow"}, {"key": "X-Frame-Options", "value": "DENY"}, {"key": "Content-Security-Policy", "value": csp}, {"key": "Referrer-Policy", "value": "no-referrer"},
           {"key": "X-Content-Type-Options", "value": "nosniff"}, {"key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()"}]
    (out / "vercel.json").write_text(json.dumps({"cleanUrls": True, "headers": [{"source": "/(.*)", "headers": sec}, {"source": "/(index.html)?", "headers": [{"key": "Cache-Control", "value": "no-cache"}]}]}, indent=1))
    print(f"wrote {len(files)} fixtures to {d}; {len(records)} records checked, none MEASURED")


if __name__ == "__main__":
    main()
