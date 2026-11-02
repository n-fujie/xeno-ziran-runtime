"""Access boundary, abuse controls and operational metrics of the service.

Ownership is an anonymous capability: the first session a browser creates sets an `xzr_owner` cookie holding a random
256-bit token (HttpOnly, SameSite=Strict). The server keeps only its SHA-256, binds every session to it, and answers
any session route (REST and WebSocket) of a session the caller does not own exactly as for a session that does not
exist. Session ids are 128-bit random and are not credentials; the token never appears in a URL or a log line.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import re

try:
    import resource
except ImportError:  # WebAssembly (Pyodide) has no `resource`; the browser tab bounds memory instead
    resource = None  # type: ignore[assignment]
import secrets
import sys
import threading
import time
from collections import defaultdict
from typing import Any

from ..scenario.model import Scenario
from .limits import LIMITS, LimitError

OWNER_COOKIE = "xzr_owner"
log = logging.getLogger("xzr.service")
_ID_IN_PATH = re.compile(r"/([0-9a-f]{8})[0-9a-f]{24}(?=/|\?|$| )")


class _RedactIds(logging.Filter):
    """Shortens 128-bit session / job ids in access-log request lines to an 8-character prefix (they are not
    credentials, but full ids are not needed to operate the service)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(_ID_IN_PATH.sub(r"/\1…", a) if isinstance(a, str) else a for a in record.args)
        return True


logging.getLogger("uvicorn.access").addFilter(_RedactIds())

if not log.handlers:  # one JSON object per line on stderr, independent of the server's own logging setup
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)


def new_session_id() -> str:
    return secrets.token_hex(16)  # 128 bits


def new_owner_token(now: float | None = None) -> str:
    """`<issue time, hex>.<256 random bits>`. The issue time gives the capability an explicit lifetime that survives
    restarts without server state; editing it only changes the token's hash, i.e. yields a new, empty identity."""
    return f"{int(time.time() if now is None else now):x}.{secrets.token_urlsafe(32)}"


def token_issued(token: str | None) -> float | None:
    if not token or len(token) > 128 or "." not in token:
        return None
    try:
        return float(int(token.split(".", 1)[0], 16))
    except ValueError:
        return None


def owner_of(token: str | None, now: float | None = None) -> str | None:
    """The stored identity for an owner token (its hash); None for a malformed or expired token."""
    issued = token_issued(token)
    if issued is None or token is None:
        return None
    now = time.time() if now is None else now
    if not issued - 300 <= now <= issued + LIMITS.owner_max_age_s:  # small allowance for clock skew
        return None
    return hashlib.sha256(token.encode()).hexdigest()


def _addr(token: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """One address from a forwarding header entry: strips quotes, ports and IPv6 brackets; None if not an address
    (e.g. "unknown" or an obfuscated identifier)."""
    t = token.strip().strip('"')
    if t.startswith("["):
        t = t[1:t.find("]")] if "]" in t else t
    elif t.count(":") == 1:  # IPv4 with a port
        t = t.split(":")[0]
    try:
        return ipaddress.ip_address(t)
    except ValueError:
        return None


def _chain(headers: dict[str, str], header: str) -> list[str]:
    """Hop addresses in the order the proxies wrote them (oldest first)."""
    v = headers.get(header, "")
    if header == "forwarded":  # RFC 7239: comma-separated elements, each with optional for=
        out = []
        for element in v.split(","):
            for pair in element.split(";"):
                k, _, val = pair.partition("=")
                if k.strip().lower() == "for":
                    out.append(val)
        return out
    if header == "x-real-ip":
        return [v] if v.strip() else []
    return [x for x in v.split(",") if x.strip()]


def client_ip(headers: dict[str, str], peer: str | None) -> str:
    """The client address under an explicit trust chain.

    A forwarding header is considered only when the connecting peer is a configured trusted proxy
    (XZR_TRUSTED_PROXIES), and only the configured header (XZR_FORWARDED_HEADER). Its hops are read from the right
    (the entry the nearest proxy wrote) past further trusted proxies; the first untrusted hop is the client. Entries
    left of it are client-supplied and ignored. Anything malformed falls back to the peer. Without trusted proxies
    every forwarding header is ignored, so a client cannot choose its apparent address by sending one.
    """
    if not peer:
        return "unknown"
    peer_ip = _addr(peer)
    trusted = LIMITS.trusted_proxies
    if peer_ip is None or not trusted or not any(peer_ip in n for n in trusted):
        return peer
    for hop in reversed(_chain(headers, LIMITS.forwarded_header)):
        ip = _addr(hop)
        if ip is None:
            return peer
        if not any(ip in n for n in trusted):
            return str(ip)
    return peer


def short(value: str) -> str:
    """A non-reversible tag for logs (never the value itself)."""
    return hashlib.sha256(value.encode()).hexdigest()[:10]


# ------------------------------------------------------------------------------------------------ rate limiting
class RateLimiter:
    """Token buckets per (kind, key): `rate` tokens per second, burst `burst`."""

    def __init__(self) -> None:
        self._b: dict[tuple[str, str], tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, kind: str, key: str, rate: float, burst: float) -> tuple[bool, float]:
        if rate <= 0:
            return True, 0.0
        now = time.monotonic()
        with self._lock:
            tokens, last = self._b.get((kind, key), (burst, now))
            tokens = min(burst, tokens + (now - last) * rate)
            if tokens >= 1:
                self._b[(kind, key)] = (tokens - 1, now)
                return True, 0.0
            self._b[(kind, key)] = (tokens, now)
            return False, (1 - tokens) / rate

    def prune(self, older_than_s: float = 600) -> None:
        now = time.monotonic()
        with self._lock:
            for k in [k for k, (_, last) in self._b.items() if now - last > older_than_s]:
                del self._b[k]


RATES = RateLimiter()


def check_rate(kind: str, key: str) -> None:
    per = {"api": (LIMITS.rate_api_per_s, LIMITS.rate_api_per_s * 4),
           "sessions": (LIMITS.rate_sessions_per_min / 60, max(1.0, LIMITS.rate_sessions_per_min / 2)),
           "jobs": (LIMITS.rate_jobs_per_min / 60, max(1.0, LIMITS.rate_jobs_per_min / 2)),
           "ws": (LIMITS.rate_ws_per_min / 60, max(1.0, LIMITS.rate_ws_per_min / 2))}[kind]
    ok, retry = RATES.allow(kind, key, *per)
    if not ok:
        raise LimitError(f"rate_{kind}", f"too many requests ({kind}); retry in {retry:.0f} s")


# ------------------------------------------------------------------------------------------------ ingestion
def json_depth(v: Any, limit: int) -> int:
    """Nesting depth of a parsed JSON value, stopping early once it exceeds `limit`."""
    stack = [(v, 1)]
    deepest = 0
    while stack:
        x, d = stack.pop()
        deepest = max(deepest, d)
        if deepest > limit:
            return deepest
        if isinstance(x, dict):
            stack += [(y, d + 1) for y in x.values()]
        elif isinstance(x, list):
            stack += [(y, d + 1) for y in x]
    return deepest


def check_payload(raw: Any) -> None:
    """Bounds on an incoming scenario / saved-session payload before it is validated or built."""
    if json_depth(raw, LIMITS.max_depth) > LIMITS.max_depth:
        raise LimitError("max_depth", f"payload nested deeper than {LIMITS.max_depth} levels", 413)
    stack = [raw]
    while stack:
        x = stack.pop()
        if isinstance(x, str) and len(x) > LIMITS.max_string:
            raise LimitError("max_string", f"a string exceeds {LIMITS.max_string} characters", 413)
        if isinstance(x, dict):
            if len(x) > LIMITS.max_list:
                raise LimitError("max_list", f"an object has more than {LIMITS.max_list} entries", 413)
            stack += list(x.keys()) + list(x.values())
        elif isinstance(x, list):
            stack += x


def check_scenario(sc: Scenario) -> None:
    """Size of the world a scenario would build, checked before anything is allocated."""
    if sc.generator is not None:
        n = sc.generator.n
        edges = int(n * sc.generator.mean_degree)
    elif sc.explicit is not None:
        n = len(sc.explicit.nodes)
        edges = len(sc.explicit.edges)
    else:
        n = edges = 0
    if n > LIMITS.max_nodes:
        raise LimitError("max_nodes", f"scenario has {n:,} configurations; this runtime allows {LIMITS.max_nodes:,}", 413)
    if edges > LIMITS.max_edges:
        raise LimitError("max_edges", f"scenario has ~{edges:,} connections; this runtime allows {LIMITS.max_edges:,}", 413)
    if sc.warmup > LIMITS.max_warmup:
        raise LimitError("max_warmup", f"warmup of {sc.warmup:,} steps exceeds {LIMITS.max_warmup:,}", 413)
    for name, seq in (("sets", sc.sets), ("boundaries", sc.boundaries), ("frozen", sc.frozen),
                      ("drivers", sc.drivers), ("interpretation_rules", sc.interpretation_rules or [])):
        if len(seq) > LIMITS.max_list:
            raise LimitError("max_list", f"scenario {name} has more than {LIMITS.max_list} entries", 413)


# ------------------------------------------------------------------------------------------------ metrics
class Metrics:
    """Counters for operating the service. Holds counts only — no payloads, ids, addresses or tokens."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = defaultdict(int)
        self.rejected: dict[str, int] = defaultdict(int)
        self.started = time.time()
        self._lock = threading.Lock()

    def inc(self, name: str, by: int = 1) -> None:
        with self._lock:
            self.counters[name] += by

    def reject(self, limit: str) -> None:
        with self._lock:
            self.rejected[limit] += 1
        event("rejected", limit=limit)


METRICS = Metrics()


def rss_bytes() -> int:
    """Current resident memory (Linux /proc); elsewhere the peak, as getrusage reports it (0 where neither exists)."""
    if resource is None:
        return 0
    try:
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * resource.getpagesize()
    except OSError:
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak if sys.platform == "darwin" else peak * 1024


def event(name: str, **fields: Any) -> None:
    """One structured log line. Callers pass counts, limit names and short tags only."""
    log.info(json.dumps({"event": name, "t": round(time.time(), 3), **fields}, default=str))
