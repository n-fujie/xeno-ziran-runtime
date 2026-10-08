"""Resource and abuse limits of the service, from the environment.

`XZR_PUBLIC=1` selects the defaults for an anonymous public demo; without it the defaults keep the local runtime's
behaviour (one trusted user). Every value can be overridden by its own variable. A limit is enforced server-side and
an exceeded limit is rejected with a message naming it — research inputs are never silently truncated.

The public defaults are sized for one instance with 2 vCPU / 2 GiB from measurements
(docs/PUBLIC_RUNTIME_DEPLOYMENT.md): a 10,000-configuration session holds ~70-100 MiB; in a 2-CPU container three
capped sessions used 72% CPU with API p95 52 ms at 30 steps/s, but p95 849 ms at 60 steps/s (one Python process:
the simulation threads compete with request handling). At capacity — 4 sessions plus a running comparison — two
10,000-configuration worlds with a 1,000-step comparison gave API p95 2.3 s; worlds of at most 3,000 with a 300-step
comparison gave p50 17 ms / p95 103 ms at 93% CPU. A larger instance can raise these through the environment.
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, fields


def _num(name: str, public: bool, local_default: float, public_default: float) -> float:
    v = os.environ.get(name)
    return float(v) if v not in (None, "") else (public_default if public else local_default)


@dataclass(frozen=True)
class Limits:
    public: bool
    # sessions
    max_sessions: int  # XZR_MAX_SESSIONS: live sessions per process
    max_sessions_per_client: int  # XZR_MAX_SESSIONS_PER_CLIENT: per owner cookie (its own oldest is replaced)
    max_sessions_per_ip: int  # XZR_MAX_SESSIONS_PER_IP
    session_idle_s: float  # XZR_SESSION_IDLE_TTL: closed after this long without API or WebSocket activity
    session_max_age_s: float  # XZR_SESSION_MAX_AGE: absolute lifetime
    # scenario ingestion
    max_nodes: int  # XZR_MAX_NODES
    max_edges: int  # XZR_MAX_EDGES (generated: n × mean_degree; explicit: listed edges)
    max_warmup: int  # XZR_MAX_WARMUP: steps run while a session is created
    max_body_bytes: int  # XZR_MAX_BODY: request body (scenario upload / load)
    max_string: int  # XZR_MAX_STRING: any string in a scenario
    max_list: int  # XZR_MAX_LIST: list lengths in a scenario other than explicit nodes / edges
    max_depth: int  # XZR_MAX_DEPTH: JSON nesting depth of a request body
    # runtime
    max_step_batch: int  # XZR_MAX_STEP_BATCH: steps per step request
    max_speed: float  # XZR_MAX_SPEED: steps per second (0 = unlimited)
    max_checkpoints: int  # XZR_MAX_CHECKPOINTS: rewind points kept per session
    max_export_bytes: int  # XZR_MAX_EXPORT_BYTES
    # comparison jobs (each job compares two branches: baseline and intervention)
    max_compare_horizon: int  # XZR_MAX_COMPARE_HORIZON
    max_active_jobs_per_session: int  # XZR_MAX_ACTIVE_JOBS_PER_SESSION
    max_queued_jobs: int  # XZR_MAX_QUEUED_JOBS: queued + running, per process
    max_compares_per_session: int  # XZR_MAX_COMPARES_PER_SESSION: finished comparisons kept (branch pairs)
    job_ttl_s: float  # XZR_JOB_TTL: finished / failed jobs are pruned after this
    max_jobs: int  # XZR_MAX_JOBS: job records kept at most
    # websockets
    max_ws: int  # XZR_MAX_WS: concurrent sockets per process
    max_ws_per_session: int  # XZR_MAX_WS_PER_SESSION
    max_ws_per_ip: int  # XZR_MAX_WS_PER_IP
    ws_idle_s: float  # XZR_WS_IDLE: closed after this long without a client message (the UI pings every 30 s)
    ws_max_message: int  # XZR_WS_MAX_MESSAGE: bytes per client message
    ws_message_rate: float  # XZR_WS_MESSAGE_RATE: client messages per second
    ws_queue: int  # XZR_WS_QUEUE: outbound frames queued per socket before it is resynchronised
    # request rates per client IP (0 = off): per second for the API, per minute for the rest
    rate_api_per_s: float  # XZR_RATE_API
    rate_sessions_per_min: float  # XZR_RATE_SESSIONS
    rate_jobs_per_min: float  # XZR_RATE_JOBS (comparisons and practice commands)
    rate_ws_per_min: float  # XZR_RATE_WS
    # deployment
    # XZR_TRUSTED_PROXIES: addresses / CIDRs of the reverse proxies in front of the service. Forwarding headers are read
    # only from a peer in this set, and only the header named by XZR_FORWARDED_HEADER, whose semantics must be
    # verified for the actual platform. Empty (default): every forwarding header is ignored; the peer is the client.
    trusted_proxies: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
    forwarded_header: str  # XZR_FORWARDED_HEADER: x-forwarded-for | forwarded | x-real-ip
    # XZR_ALLOWED_ORIGINS: exact browser origins (scheme://host[:port]) allowed to open sockets. Behind a reverse proxy
    # set it: proxies may rewrite Host (e.g. drop the port), so comparing Origin with Host is not reliable there.
    # Empty: the Origin must match the request's Host (direct, same-origin serving). CORS stays closed either way.
    allowed_origins: tuple[str, ...]
    cookie_secure: bool  # XZR_COOKIE_SECURE: owner cookie only over HTTPS
    owner_max_age_s: float  # XZR_OWNER_MAX_AGE: lifetime of an anonymous owner capability
    ops_token: str  # XZR_OPS_TOKEN: required for /api/ops/metrics in public mode (endpoint disabled if empty)

    def describe(self) -> dict:
        out = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "ops_token"}
        out["trusted_proxies"] = [str(n) for n in self.trusted_proxies]
        return out


FORWARDED_HEADERS = ("x-forwarded-for", "forwarded", "x-real-ip")


def _proxies(spec: str) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    return tuple(ipaddress.ip_network(p.strip(), strict=False) for p in spec.split(",") if p.strip())


def load_limits() -> Limits:
    pub = os.environ.get("XZR_PUBLIC", "") == "1"
    if os.environ.get("XZR_TRUST_PROXY"):
        # the former switch trusted forwarding headers from any peer; refuse to start rather than guess
        raise RuntimeError("XZR_TRUST_PROXY was removed: list the reverse proxies in XZR_TRUSTED_PROXIES "
                           "and name the verified header in XZR_FORWARDED_HEADER")
    header = os.environ.get("XZR_FORWARDED_HEADER", "x-forwarded-for").lower()
    if header not in FORWARDED_HEADERS:
        raise RuntimeError(f"XZR_FORWARDED_HEADER must be one of {FORWARDED_HEADERS}")

    def i(name: str, local: float, public: float) -> int:
        return int(_num(name, pub, local, public))

    def f(name: str, local: float, public: float) -> float:
        return _num(name, pub, local, public)

    return Limits(
        public=pub,
        max_sessions=i("XZR_MAX_SESSIONS", 4, 4),
        max_sessions_per_client=i("XZR_MAX_SESSIONS_PER_CLIENT", 4, 2),
        max_sessions_per_ip=i("XZR_MAX_SESSIONS_PER_IP", 4, 3),
        session_idle_s=f("XZR_SESSION_IDLE_TTL", 24 * 3600, 900),
        session_max_age_s=f("XZR_SESSION_MAX_AGE", 7 * 24 * 3600, 7200),
        max_nodes=i("XZR_MAX_NODES", 500_000, 3_000),
        max_edges=i("XZR_MAX_EDGES", 32_000_000, 40_000),
        max_warmup=i("XZR_MAX_WARMUP", 1_000_000, 500),
        max_body_bytes=i("XZR_MAX_BODY", 256_000_000, 2_000_000),
        max_string=i("XZR_MAX_STRING", 1_000_000, 4_000),
        max_list=i("XZR_MAX_LIST", 10_000_000, 5_000),
        max_depth=i("XZR_MAX_DEPTH", 64, 32),
        max_step_batch=i("XZR_MAX_STEP_BATCH", 100_000, 2_000),
        max_speed=f("XZR_MAX_SPEED", 0, 30),
        max_checkpoints=i("XZR_MAX_CHECKPOINTS", 24, 24),
        max_export_bytes=i("XZR_MAX_EXPORT_BYTES", 2_000_000_000, 25_000_000),
        max_compare_horizon=i("XZR_MAX_COMPARE_HORIZON", 5000, 300),
        max_active_jobs_per_session=i("XZR_MAX_ACTIVE_JOBS_PER_SESSION", 8, 1),
        max_queued_jobs=i("XZR_MAX_QUEUED_JOBS", 64, 6),
        max_compares_per_session=i("XZR_MAX_COMPARES_PER_SESSION", 50, 10),
        job_ttl_s=f("XZR_JOB_TTL", 6 * 3600, 900),
        max_jobs=i("XZR_MAX_JOBS", 1000, 200),
        max_ws=i("XZR_MAX_WS", 256, 32),
        max_ws_per_session=i("XZR_MAX_WS_PER_SESSION", 16, 3),
        max_ws_per_ip=i("XZR_MAX_WS_PER_IP", 64, 6),
        ws_idle_s=f("XZR_WS_IDLE", 24 * 3600, 180),
        ws_max_message=i("XZR_WS_MAX_MESSAGE", 1_000_000, 8_192),
        ws_message_rate=f("XZR_WS_MESSAGE_RATE", 0, 20),
        ws_queue=i("XZR_WS_QUEUE", 256, 64),
        rate_api_per_s=f("XZR_RATE_API", 0, 60),
        rate_sessions_per_min=f("XZR_RATE_SESSIONS", 0, 6),
        rate_jobs_per_min=f("XZR_RATE_JOBS", 0, 20),
        rate_ws_per_min=f("XZR_RATE_WS", 0, 20),
        trusted_proxies=_proxies(os.environ.get("XZR_TRUSTED_PROXIES", "")),
        forwarded_header=header,
        allowed_origins=tuple(o.strip().rstrip("/").lower() for o in os.environ.get("XZR_ALLOWED_ORIGINS", "").split(",")
                              if o.strip()),
        cookie_secure=os.environ.get("XZR_COOKIE_SECURE", "1" if pub else "") == "1",
        owner_max_age_s=f("XZR_OWNER_MAX_AGE", 30 * 24 * 3600, 24 * 3600),
        ops_token=os.environ.get("XZR_OPS_TOKEN", ""),
    )


LIMITS = load_limits()


class LimitError(Exception):
    """A request exceeded a configured limit: answered with `status` and a message naming the limit."""

    def __init__(self, limit: str, message: str, status: int = 429):
        super().__init__(message)
        self.limit = limit
        self.message = message
        self.status = status

    def body(self) -> dict:
        return {"error": self.message, "limit": self.limit}
