"""The optional link to the EXISTING XenoSNN reference server (pa-simulation-environment/python/ziran_pytorch_server.py): the second reviewed exception to the laboratory's no-network rule, next to bodylink.py for files.

What XenoSNN is (read in its source): ONE snnTorch Leaky Integrate-and-Fire neuron (beta 0.9, threshold 1.0, constants in its code) driven by a whole numeric input sequence; ``POST /run`` with ``metadata.experimentType = "snn-minimal"`` returns, per
timestep, ``t``, ``input``, ``membrane`` and ``spike``. It keeps no state between requests, has no weights, no plasticity and no memory, and needs torch and snnTorch (no substitute computation exists, by its own rule).

Only a LOOPBACK address from the environment variable ``XZR_XENOSNN_URL`` is ever contacted (never an address from a request): http, host 127.0.0.1 / localhost / [::1], an explicit port, no path. Redirects are refused. One fixed endpoint (``/run``, and ``/health``),
a fixed payload shape, a timeout, a bounded response, and a strict check of what comes back. Nothing is written and no process is started here.
"""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

ENV = "XZR_XENOSNN_URL"
MAX_INPUT = 4000
MAX_RESPONSE_BYTES = 4_000_000
LOOPBACK = ("127.0.0.1", "localhost", "::1")


class SnnLinkError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        raise SnnLinkError("the XenoSNN server answered with a redirect: refused")


_OPENER = urllib.request.build_opener(_NoRedirect)


def base_url() -> str | None:
    raw = os.environ.get(ENV, "").strip()
    if not raw:
        return None
    u = urlparse(raw)
    if u.scheme != "http" or u.hostname not in LOOPBACK or u.port is None or u.path not in ("", "/") or u.query or u.fragment or u.username or u.password:
        return None
    return f"http://{'[::1]' if u.hostname == '::1' else u.hostname}:{u.port}"


def _call(path: str, body: dict | None, timeout: float) -> dict[str, Any]:
    root = base_url()
    if root is None:
        raise SnnLinkError("XZR_XENOSNN_URL is not set to a loopback http address with a port")
    req = urllib.request.Request(root + path, data=None if body is None else json.dumps(body).encode(), headers={"content-type": "application/json"}, method="GET" if body is None else "POST")
    try:
        with _OPENER.open(req, timeout=timeout) as r:  # noqa: S310 (the URL is built from a validated loopback root and a fixed path)
            raw = r.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SnnLinkError(f"the XenoSNN server could not be reached: {exc}") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise SnnLinkError("the XenoSNN response is too large")
    try:
        out = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SnnLinkError("the XenoSNN response is not JSON") from exc
    if not isinstance(out, dict):
        raise SnnLinkError("the XenoSNN response is not an object")
    return out


def health(timeout: float = 5.0) -> dict[str, Any] | None:
    """The server's own report, or None if it is not reachable or does not have snnTorch."""
    try:
        h = _call("/health", None, timeout)
    except SnnLinkError:
        return None
    return h if h.get("status") == "ok" and (h.get("snnRuntime") or {}).get("available") is True else None


def replay(inputs: list[float], experiment_id: str, timeout: float = 60.0) -> dict[str, Any]:
    """One input sequence through the neuron. Returns the server's own trace and runtime description; raises SnnLinkError on anything that is not a well-formed, successful snn-minimal answer."""
    if not inputs or len(inputs) > MAX_INPUT or not all(isinstance(x, int | float) and not isinstance(x, bool) and math.isfinite(x) for x in inputs):
        raise SnnLinkError(f"the input must be 1..{MAX_INPUT} finite numbers")
    r = _call("/run", {"experimentId": experiment_id, "input": [float(x) for x in inputs], "metadata": {"experimentType": "snn-minimal"}}, timeout)
    if r.get("status") != "ok" or r.get("experimentId") != experiment_id:
        raise SnnLinkError(f"the XenoSNN server did not run the experiment: {r.get('status')} {r.get('error') or (r.get('metadata') or {}).get('executionFailure')}")
    steps = (r.get("output") or {}).get("timesteps")
    if not isinstance(steps, list) or len(steps) != len(inputs):
        raise SnnLinkError("the XenoSNN trace does not have one entry per input")
    for i, s in enumerate(steps):
        if not (isinstance(s, dict) and s.get("t") == i and s.get("spike") in (0, 1) and isinstance(s.get("membrane"), int | float) and math.isfinite(s["membrane"]) and s.get("input") == float(inputs[i])):
            raise SnnLinkError("the XenoSNN trace is malformed")
    return {"timesteps": steps, "runtime": (r.get("metadata") or {}).get("snnRuntime"), "provenance": r.get("provenance")}
