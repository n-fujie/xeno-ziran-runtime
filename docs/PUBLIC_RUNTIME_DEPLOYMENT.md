# Public runtime: security boundary and deployment plan

> **Update.** The server container described below is still not deployed. A different public form now exists that needs no
> host for compute: the simulator running in the visitor's browser tab at `/app/` of the static site
> ([WEB_RUNTIME.md](WEB_RUNTIME.md)). Its trust boundary is different (no server-side execution, no sessions, no
> authentication); the capability-session model below applies only to the server container.

Status (2026-10-05, re-checked): **NO-GO — staging host unavailable. The runtime stays private.** Searched: hosting
CLIs (Fly, Railway, Render, gcloud, AWS, Azure, doctl, Heroku, kubectl, helm, Koyeb, Hetzner, Scaleway, Vultr, OCI,
Linode, Northflank, wrangler), their credential directories and environment variables, Docker registry logins (none),
CI/CD (only `ci.yml` / `security-audit.yml` in other repositories, no deploy targets; the only repository secret is a
Discord webhook), git remotes (none for this repository), SSH hosts (github.com only). The authenticated GitHub CLI
cannot push images (no `write:packages` scope) and GitHub does not host long-running containers; Vercel (configured for
the static site) cannot run a long-lived WebSocket container. The security boundary below is
implemented and tested (`backend/tests/test_security.py`) and the final immutable candidate image was verified
locally, including behind a real nginx TLS reverse proxy — but no external container host or credentials are
configured for this project, so nothing has been verified on real staging (public Web PKI, the platform's forwarding
semantics, its instance model, its logs). A local rehearsal is not staging.

The public site (https://ziran-xeno-simulator.vercel.app) remains the static, read-only research-result layer of
XENO ZIRAN SIMULATOR. The interactive runtime — sessions, run / step / rewind, graph projections, branch comparison,
practice console, save / load, CSV / JSON export — runs on the local server and, once deployed, in the container
described here.

### Final candidate image

| | |
|---|---|
| tag | `xeno-ziran-runtime:candidate-d44087a037fb` (local only; not pushed anywhere) |
| image id / digest | `sha256:a6d96dfa7912782e8ed42b44adc60fc74c1f4fd09860ae53096be52031852e31` |
| size | 122 MB |
| built | 2026-10-05 (label `org.opencontainers.image.created`) |
| source | HEAD `2634e697` + uncommitted working tree (label `org.opencontainers.image.revision=…-dirty`) |
| build-input hash | `d44087a037fb…` (label `xzr.source-tree-sha256`): sorted per-file SHA-256 of Dockerfile, .dockerignore, backend/pyproject.toml, backend/xzr, backend/scenarios, frontend sources, package.json, package-lock.json |
| lockfiles | `6f266d128fd1…` (label `xzr.lockfiles-sha256`) = package-lock.json + pyproject.toml. The backend has no Python lockfile: pip resolves at build time; the image's resolved set (23 packages) has `pip freeze` SHA-256 `06ec1552b55ac3b1…` |
| check | the image's `xzr` package hashes identically to the working tree; verification used no bind mounts or overlays |

Supersedes `candidate-7e88ebeb01e8` (sha256:32e77caa…), which lacked the session-loss fixes below.

Staging must run this exact image (pushed by digest to a registry the host can pull). A host that rebuilds from source
produces a different artifact, which must be verified separately.

## 1. Access model: anonymous capability sessions

* The first session a browser creates sets the `xzr_owner` cookie: a random 256-bit token, `HttpOnly`,
  `SameSite=Strict`, `Secure` in public mode. The server stores only its SHA-256 and binds each session to it.
* One middleware (`service/app.py::guard`) checks ownership for every `/api/sessions/{sid}/…` route (info, control,
  rewind, LOD tiles, snapshot, inspection, practice, compare, save, export, delete) and for `/api/jobs/{jid}` (the
  job's session must be the caller's). The WebSocket `/ws/{sid}` performs the same check before accepting, plus a
  same-origin check. A session or job the caller does not own is answered exactly like a missing one (404 / close
  4404), so existence is not revealed.
* Session ids are 128-bit random (`secrets.token_hex(16)`) and are not credentials; job ids are 128-bit UUIDs.
  `GET /api/sessions` lists only the caller's own sessions.
* The token never appears in a URL, a response body or a log line. Structured events carry an 8-character session
  prefix and a hashed client address only.

**Authentication decision: anonymous capability sessions are sufficient for the public demo.** Sessions hold no
personal data, are ephemeral (idle TTL, absolute lifetime), persist nothing server-side, and are bounded by the
limits below; an account system would add credential handling without protecting anything the capability does not
already isolate. Accounts become necessary only if server-side persistence, larger quotas per person, or uploads
beyond the anonymous caps are offered.

## 2. Limits (environment, `service/limits.py`)

`XZR_PUBLIC=1` selects the public defaults; without it the local defaults keep the single-user behaviour. Every value
has its own variable. An exceeded limit is rejected with HTTP 4xx/5xx and `{"error": …, "limit": <name>}`; the UI
shows the message with the limit name. Research inputs are never silently truncated.

| limit | variable | public | local |
|---|---|---|---|
| live sessions per process | `XZR_MAX_SESSIONS` | 4 | 4 |
| sessions per owner (own oldest is replaced) | `XZR_MAX_SESSIONS_PER_CLIENT` | 2 | 4 |
| sessions per client address | `XZR_MAX_SESSIONS_PER_IP` | 3 | 4 |
| idle timeout | `XZR_SESSION_IDLE_TTL` | 900 s | 24 h |
| absolute session lifetime | `XZR_SESSION_MAX_AGE` | 2 h | 7 d |
| configurations (nodes) | `XZR_MAX_NODES` | 3,000 | 500,000 |
| connections (edges) | `XZR_MAX_EDGES` | 40,000 | 32,000,000 |
| warmup steps at creation | `XZR_MAX_WARMUP` | 500 | 1,000,000 |
| request body | `XZR_MAX_BODY` | 2 MB | 256 MB |
| string length / list length / JSON depth | `XZR_MAX_STRING` / `_LIST` / `_DEPTH` | 4,000 / 5,000 / 32 | 1M / 10M / 64 |
| steps per step request | `XZR_MAX_STEP_BATCH` | 2,000 | 100,000 |
| simulation speed (steps/s; "max" is capped) | `XZR_MAX_SPEED` | 30 | unlimited |
| rewind checkpoints per session | `XZR_MAX_CHECKPOINTS` | 24 | 24 |
| export size | `XZR_MAX_EXPORT_BYTES` | 25 MB | 2 GB |
| comparison horizon | `XZR_MAX_COMPARE_HORIZON` | 300 | 5,000 |
| running comparisons per session | `XZR_MAX_ACTIVE_JOBS_PER_SESSION` | 1 | 8 |
| queued + running comparisons per process | `XZR_MAX_QUEUED_JOBS` | 6 | 64 |
| finished comparisons kept per session (branch pairs) | `XZR_MAX_COMPARES_PER_SESSION` | 10 | 50 |
| finished / failed job TTL, job records kept | `XZR_JOB_TTL`, `XZR_MAX_JOBS` | 900 s, 200 | 6 h, 1,000 |
| sockets per process / session / address | `XZR_MAX_WS`, `_PER_SESSION`, `_PER_IP` | 32 / 3 / 6 | 256 / 16 / 64 |
| socket idle timeout (the UI pings every 30 s) | `XZR_WS_IDLE` | 180 s | 24 h |
| client message size / rate | `XZR_WS_MAX_MESSAGE`, `XZR_WS_MESSAGE_RATE` | 8 KB, 20/s | 1 MB, off |
| outbound frames queued per socket | `XZR_WS_QUEUE` | 64 | 256 |
| API requests per address | `XZR_RATE_API` | 60/s (burst 240) | off |
| session creations / comparisons / sockets per address | `XZR_RATE_SESSIONS` / `_JOBS` / `_WS` | 6 / 20 / 20 per min | off |

Uvicorn (Dockerfile) also bounds WebSocket frames (`--ws-max-size`, 1 MB) and connections (`--limit-concurrency`).

## 3. Lifecycles

* **Sessions.** A reaper (every 15 s) closes sessions idle beyond the TTL (no API call and no socket message; an
  open UI pings) and sessions past the absolute lifetime, and drops their LOD grid caches. A full process answers
  503; a visitor never evicts another visitor's session. A visitor at its own limit replaces its own least recently
  used session, and the UI closes a session it replaces (scenario switch, load). In public mode a page reload
  re-attaches to the visitor's latest own session instead of creating another.
* **Comparison jobs.** Two worker threads (bounded concurrency); jobs are `queued → running → done | error |
  cancelled`. Finished and failed records are pruned after the TTL and beyond the count limit; queued jobs can be
  cancelled (`POST /api/jobs/{jid}/cancel`) and are cancelled when their session closes; a running comparison
  completes within its horizon cap. Finished comparison results per session are bounded.
* **State.** Ephemeral by design: live sessions exist only in the process; persistence is the client's explicit
  save (JSON download) and load (upload). No server-side storage is needed or implied.

## 4. WebSocket safeguards

Ownership and same-origin checks before accept; per-process / session / address socket limits (an over-limit socket
receives `{"type": "error", "limit": …}` and close 1013); idle timeout; client message size and rate limits (close
1009 / 1008). Outbound frames go through a bounded per-socket queue drained by a writer task, so a slow client never
stalls the broadcaster or other clients. When a queue overflows, that client's pending delta frames are dropped and it
is resynchronised with a full snapshot (no state is lost) and told so with a `notice` message shown in the UI;
update fidelity is otherwise unchanged.

## 5. Experiment execution boundary

The service exposes no route that runs experiment suites, spawns processes, or takes filesystem paths: the only
mutating routes are session creation / deletion, control, rewind, practice commands and comparisons (bounded as
above), and job cancellation (`test_no_route_runs_experiments_or_touches_the_filesystem` pins this list).
`/api/experiments/*` serves existing result files read-only (names restricted to `[a-z0-9_-]`). Batch research
(`backend/experiments/run_*.py`) stays an offline, local command-line activity; the public research results come
from the static export.

## 6. Observability

`GET /api/ops/metrics` (public mode: requires `X-Ops-Token` = `XZR_OPS_TOKEN`; disabled when unset) reports active
sessions and sockets, job counts, counters (sessions created / closed by reason, denied session / job / socket
accesses, HTTP responses by class, socket frames and resyncs, jobs started / done / failed / pruned / cancelled),
rejections by limit, resident memory, process CPU time, mean step latency, total steps per second and the
effective limits. It contains no ids, addresses, tokens or research payloads. Structured JSON events (stderr):
`start`, `session_created`, `session_closed`, `rejected` (limit name), `reaper_error`. Uvicorn's access log
records request paths, which contain session ids (not credentials).

## 7. Measurements (this machine)

* Per session (`resbench`): 600-configuration world ~10–20 MiB, 10,000 ~70–100 MiB including checkpoints; a
  150-step comparison 0.6 s (600) to 4.6 s (10,000). Uncapped speed uses more than one core per session.
* Public-mode process, 3 visitors at the speed cap with one socket each, 30 s: ~39 frames/s per socket, 0 resyncs,
  API p50 4.5 ms / p95 58 ms, 89 % of one core, RSS 252 MiB.
* Container (2 CPU, 2 GiB), 3 sessions with sockets: at 60 steps/s API p95 849 ms (simulation threads compete with
  request handling in one Python process); at 30 steps/s p50 8.9 ms / p95 51.7 ms, 72 % CPU, RSS 273 MiB → public
  default 30 steps/s.
* Container at capacity (4 sessions with sockets plus a running comparison, 40 s): two 10,000-configuration worlds and
  a 1,000-step comparison gave API p50 621 ms / p95 2.3 s, 8 frames/s (at 142 % CPU: the bottleneck is contention in
  the one Python process, not CPU); worlds of at most 3,000 with a 1,000-step comparison p50 35 ms / p95 1.2 s; with
  a 300-step comparison p50 17 ms / p95 103 ms, 38.5 frames/s per socket, every session at its 30 steps/s cap,
  93 % CPU, RSS 282 MiB → public defaults 3,000 configurations, 300-step comparisons. Larger worlds are refused with
  a message (the scenario list marks them) — never truncated; a larger instance can raise the limits.

## 8. Topology (when the gate opens)

One container (the existing Dockerfile: UI + API + WebSocket on one origin, so no CORS and no frontend URL change)
behind the platform's HTTPS/WSS termination, `XZR_PUBLIC=1`; `XZR_TRUSTED_PROXIES` = only the platform proxy's
addresses / CIDR and `XZR_FORWARDED_HEADER` = the one header whose semantics were verified on that platform (the
former `XZR_TRUST_PROXY` switch refuses to start); `XZR_ALLOWED_ORIGINS` = the public origin (a proxy may rewrite
Host); `XZR_OPS_TOKEN` from the platform's secret store. One instance (sessions are in
memory; more instances need sticky routing). 2 vCPU / 2 GiB, no GPU (no source path uses one). Health check
`/api/health`. Rollback by immutable image tag. The static site stays independent.

## 9. Proxy trust, origins, capability lifecycle, readiness

* **Client address.** Forwarding headers are read only when the TCP peer is in `XZR_TRUSTED_PROXIES`, and only the
  header named by `XZR_FORWARDED_HEADER` (`x-forwarded-for` | `forwarded` | `x-real-ip`). Hops are read from the
  right past further trusted proxies; the first untrusted hop is the client; client-written entries to its left and
  malformed entries are ignored (fallback: the peer). Without trusted proxies every forwarding header is ignored.
* **Socket origins.** `XZR_ALLOWED_ORIGINS` (exact origins). Unset: Origin must equal the request Host. In the nginx
  rehearsal `proxy_set_header Host $host` dropped the port and the Host comparison rejected every socket — set the
  allowlist behind any proxy. CORS stays closed (no CORS middleware; a foreign-origin preflight gets 405 without
  `Access-Control-Allow-Origin`).
* **Owner capability.** `<issue time>.<256 random bits>`, cookie `HttpOnly`, `Secure` (public), `SameSite=Strict`,
  `Max-Age` = `XZR_OWNER_MAX_AGE` (public 24 h). Rotated at session creation past half its lifetime (the owner's live
  sessions move to the new capability; the old one stops working). Sessions are reaped when their owner capability
  expires. `POST /api/owner/reset` closes the caller's sessions and clears the cookie.
* **Readiness / liveness.** `/api/ready`: 200 while the cleanup task runs, the process is not stopping and memory is
  below `XZR_READY_MEMORY_FRACTION` (0.9) of the container limit; 503 otherwise. Being full is *not* unready (a single
  instance taken out of rotation would cut off its sessions) and is reported as `accepting_new_sessions`.
  `/api/health`: liveness. Neither contains secrets.
* **Unknown `/api/*` paths** answer 404 JSON (they previously fell through to the app's `index.html` with 200).
* **Access log.** Uvicorn access lines show session / job ids shortened to 8 characters. A platform proxy's own access
  log is outside the service's control and will contain full request paths (session ids are not credentials).

## 10. Exact-image verification (local, 2026-10-05) — not staging

Topology: the candidate image (no mounts) on a private Docker network, unpublished, behind nginx 1.27 with a
self-signed certificate (TLS termination, `X-Forwarded-For` appended via `$proxy_add_x_forwarded_for`, WebSocket
upgrade, `proxy_read_timeout 60s`), `XZR_TRUSTED_PROXIES=<nginx>/32`, colima VM with 2 CPUs; runtime limited to
2 CPU / 2 GiB.

| check | result |
|---|---|
| HTTP → HTTPS, TLS chain (rehearsal CA) | 301; verifies with the CA, fails without (not public Web PKI) |
| derived client address with forged XFF / Forwarded / X-Real-IP | always the proxy-observed peer; per-address session limit still refused a 4th identity |
| owner cookie | HttpOnly, Secure, SameSite=Strict, Max-Age=86400; not readable from JavaScript (browser, HTTP run) |
| A vs B (read, control, rewind, export, compare, save, delete, B's job, B's socket) | all 404 / 403; listings only own |
| reload / reconnect | same state (t=25) on two reconnects, no duplicate session |
| rotation / reset / owner expiry / idle cleanup | rotated cookie keeps the session, pre-rotation cookie 404; reset closes and clears; expired owner → 404 and reaped; idle → reaped |
| restart | readiness 502 (proxy) → 200; old session 404, old socket 403, old cookie 404 on another visitor's new session, clean new session |
| limits | nodes, edges, warmup → 413; malformed → 422; body > 2 MB → 413; horizon, steps → 422; second compare, 4th socket, session rate → 429; export over cap → 413; API burst 124–231 req/s → 75–208 × 429 |
| experiment boundary | no execution route (POST → 405, unknown → 404); route inventory test |
| metrics | 404 without token, 200 with |
| slow client | a fast client kept 38 frames/s while another read nothing; the stalled socket was disconnected by the WebSocket keepalive. Queue-overflow resync did not fire (proxy and socket buffers absorbed the backlog) — only non-stalling and disconnection were verified |
| idle | 30 s pings kept a socket alive 130 s through the proxy; a silent socket closed at 181 s (code 1001, runtime idle limit) |
| logs | no tokens, cookies, auth headers, metrics token or scenario payloads; runtime access lines show 8-char ids; the rehearsal proxy log shows full ids |
| load, 4 sessions (two 3,000-node), sockets, 300-step compare, 300 s | three runs of the same code: API p95 215 ms / 560 ms / 1.6 s, frames 34 / 32 / 19 per socket, CPU 82–96 % of 2, RSS ≤ 348 MiB, 0 errors, 0 resyncs; the 1.6 s run had cgroup throttling while the host load average was ~8. Local numbers are not a capacity sign-off |

Session loss (fixed in `candidate-d44087a037fb`; `frontend/src/api/sessionGone.ts`, tests in
`api/sessionGone.test.ts` and `store/sessionLoss.test.ts`):

* A session is *gone* only on a 404 "no such session" for one of its routes; network errors and 5xx (a proxy waiting
  for a restarting runtime) are transient. After an unexpected socket close the client probes the session with
  backoff (1, 2, 4, 5 s …): 200 → the stream reconnects; transient → "Connection to the runtime lost — reconnecting…";
  404 → the session is gone.
* Once gone, every request bound to that session (REST and LOD tiles) is refused locally without a network request,
  the stream is closed, and the message offers "Start a new session".
* Browser check on the exact image (runtime stopped 10 s under an open map view, then started): transient notice
  1 s after the disconnect, definitive message after the restarted runtime answered (≈ 10–15 s after it was ready,
  within the backoff and the browser's connection retries), then 0 requests to the dead session over 13 s including
  map zooming; the console held the outage's connection errors and exactly one 404 (previously 800+).

## 11. Required staging host

Docker/OCI container support (pull by digest); exactly one pinned instance (no autoscaling, no multi-instance fan-out
— sessions are in memory); HTTPS and WSS with public Web PKI; configurable health checks (`/api/ready`, liveness
`/api/health`); fixed CPU / memory (2 vCPU / 2 GiB measured); environment variables and secrets
(`XZR_OPS_TOKEN`); documented, testable forwarded-header semantics and proxy addresses; WebSocket idle timeout above
the 30 s UI ping; a reachable staging URL; deployment rollback by image digest; access to platform proxy logs.

## 12. Remaining prerequisites (why NO-GO)

1. A container host for this project (none is configured) with WebSocket support and HTTPS.
2. A staging deployment on it, then: real WebSocket and multi-session isolation tests, a load test at the configured
   limits, and a check of logs and metrics on that host — the protocol forbids skipping staging for the stateful
   backend.
3. Confirmation of the capacity defaults on the target host (measured here in a local 2-CPU container; the 10,000-
   configuration benchmark scenarios are outside the anonymous limits on that size).
