"""Serve an exported static site locally with the response headers its vercel.json sets (for testing, not for production).

    python backend/scripts/serve_site.py [site_dir] [port]      # default: site/ on 4173

Applies every route of vercel.json that only adds headers (``continue: true``) to the matching request path, the 308
redirects, and the plain rewrites (``src`` -> ``dest``, e.g. /api/experiments/<name> -> /data/<name>.json), so the browser
build's Content-Security-Policy (which restricts the Web Worker and Pyodide to this origin) and the static result views are
exercised as on the host. It is not a re-implementation of the host's routing: query-conditional routes are not applied
and unknown paths are 404.
"""

from __future__ import annotations

import json
import re
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, rules, routes=(), **kw):
        self.rules = rules
        self.routes = routes
        super().__init__(*a, **kw)

    def _rules(self):
        path = self.path.split("?", 1)[0]
        return [r for r in self.rules if re.fullmatch(r["src"], path)]

    def _rewrite(self):
        path, _, query = self.path.partition("?")
        for r in self.routes:
            if "dest" in r and "has" not in r and "status" not in r and re.fullmatch(r["src"], path):
                path = re.sub(r["src"], r["dest"].replace("$1", r"\1"), path)
                break
        self.path = path + ("?" + query if query else "")

    def do_GET(self):
        for r in self._rules():
            if r.get("status") == 308:
                self.send_response(308)
                self.send_header("Location", r["headers"]["Location"])
                self.end_headers()
                return
        self._rewrite()
        super().do_GET()

    def end_headers(self):
        for r in self._rules():
            if r.get("continue"):
                for k, v in r.get("headers", {}).items():
                    self.send_header(k, v)
        super().end_headers()

    def log_message(self, fmt, *args):  # quiet
        pass


def main() -> None:
    site = Path(sys.argv[1] if len(sys.argv) > 1 else "site").resolve()
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 4173
    cfg = json.loads((site / "vercel.json").read_text())
    rules = [r for r in cfg["routes"] if "src" in r and ("headers" in r) and "has" not in r]
    handler = partial(Handler, directory=str(site), rules=rules, routes=[r for r in cfg["routes"] if "src" in r])
    ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


if __name__ == "__main__":
    main()
