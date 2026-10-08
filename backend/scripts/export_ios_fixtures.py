"""Write the iOS app's cross-runtime fixtures (ios/XenoZiranTests/Fixtures) from the desktop runtime.

* conformance_reference.json — the golden behavioural snapshot (copied from tests/fixtures)
* desktop_save.json — a Save file produced by the desktop HTTP service (reason-lab with an applied intervention)
* desktop_save_expect.json — sha256 of the binary state snapshot after loading that file and stepping 20 steps,
  as the desktop service serves it; the app must produce the identical bytes

Run from backend/: python scripts/export_ios_fixtures.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path

from fastapi.testclient import TestClient

from xzr.service import app as app_mod

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "ios" / "XenoZiranTests" / "Fixtures"
STEPS = 20


def _wait(http: TestClient, sid: str, t: int) -> None:
    for _ in range(4000):
        st = http.get(f"/api/sessions/{sid}").json()
        if st["t"] >= t:
            return
        time.sleep(0.005)
    raise TimeoutError


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "tests" / "fixtures" / "conformance_reference.json", OUT / "conformance_reference.json")
    http = TestClient(app_mod.app)
    sid = http.post("/api/sessions", json={"sample": "reason-lab"}).json()["id"]
    r = http.post(f"/api/sessions/{sid}/practice/command", json={"text": "remove concept human", "auto_compare": False})
    r.raise_for_status()
    applied = http.post(f"/api/sessions/{sid}/practice/command", json={"text": "apply", "auto_compare": False})
    applied.raise_for_status()
    saved = http.get(f"/api/sessions/{sid}/save").json()
    (OUT / "desktop_save.json").write_text(json.dumps(saved, indent=1))
    lid = http.post("/api/sessions", json={"scenario": saved["scenario"], "applied": saved["applied"]}).json()["id"]
    t0 = http.get(f"/api/sessions/{lid}").json()["t"]
    http.post(f"/api/sessions/{lid}/control", json={"action": "step", "steps": STEPS})
    _wait(http, lid, t0 + STEPS)
    time.sleep(0.3)
    snap = http.get(f"/api/sessions/{lid}/snapshot").content
    expect = {"steps": STEPS, "t": t0 + STEPS, "snapshot_sha256": hashlib.sha256(snap).hexdigest(),
              "snapshot_bytes": len(snap)}
    (OUT / "desktop_save_expect.json").write_text(json.dumps(expect, indent=1))
    print(expect)


if __name__ == "__main__":
    main()
