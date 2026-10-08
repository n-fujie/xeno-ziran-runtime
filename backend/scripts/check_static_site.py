"""Check the HTTP routing of the static mirror against a running host (the deployment, or a local emulation).

    python backend/scripts/check_static_site.py https://ziran-xeno-simulator.vercel.app

Every view of the build must answer 200 when requested directly (a deep link or a refresh), and anything that
addresses no view must answer a real 404 that serves the app shell (so the app renders its Not Found state rather
than the overview). Exits non-zero on any failure.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIEWS = json.loads((ROOT / "frontend" / "src" / "static-views.json").read_text())
RUNTIME_ONLY = ["network", "shape", "address", "map", "globe", "timeline", "compare", "practice"]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # type: ignore[no-untyped-def]
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def get(url: str) -> tuple[int, str, bytes, str]:
    try:
        r = OPENER.open(url, timeout=30)
        return r.status, r.headers.get("Content-Type", ""), r.read(), r.headers.get("Location", "")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read(), e.headers.get("Location", "")


def main() -> None:
    base = sys.argv[1].rstrip("/")
    fails: list[str] = []

    def expect(path: str, status: int, ctype: str = "", shell: bool = False, location: str = "") -> None:
        code, ct, body, loc = get(base + path)
        ok = code == status and ctype in ct and (not shell or b'<div id="root">' in body) and location in loc
        print(f"{'ok  ' if ok else 'FAIL'} {code} {ct.split(';')[0]:<17} {path}" + (f" -> {loc}" if loc else ""))
        if not ok:
            fails.append(path)

    expect("/", 200, "text/html", shell=True)
    for v in VIEWS:  # direct request = deep link / refresh
        expect(f"/?view={v}", 200, "text/html", shell=True)
    expect("/?view=res_matrix&lang=ja", 200, "text/html", shell=True)
    expect("/index.html?view=reason", 200, "text/html", shell=True)
    expect("/?view=RES_Matrix", 200, "text/html", shell=True)  # ids are case-insensitive (Vercel `has` matching)
    for v in ["nonexistent", "", "res_matrix_x", "xres_matrix", *RUNTIME_ONLY]:
        expect(f"/?view={v}", 404, "text/html", shell=True)
    for p in ["/nope", "/res_matrix", "/a/b/c", "/api", "/api/sessions", "/.vercel/project.json"]:
        expect(p, 404, "text/html", shell=True)
    expect("/api/experiments", 200, "application/json")
    try:
        listing = json.loads(get(base + "/api/experiments")[2])
    except ValueError:
        listing = []
        fails.append("/api/experiments (not JSON)")
    for e in listing:
        expect(f"/api/experiments/{e['name']}", 200, "application/json")
    expect("/api/experiments/primitives", 200, "application/json")
    expect("/api/experiments/nonexistent", 404)
    expect("/overview/index.html", 200, "text/html")
    expect("/overview", 308, location="/")
    expect("/screenshots/x.png", 308, location="/overview/screenshots/x.png")
    print(f"\n{len(fails)} failure(s)" + (": " + ", ".join(fails) if fails else ""))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
