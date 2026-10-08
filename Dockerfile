# XENO ZIRAN SIMULATOR runtime — single-service container (API + simulation workers + static UI).
# Public demo: run with XZR_PUBLIC=1 (limits in backend/xzr/service/limits.py, plan in docs/PUBLIC_RUNTIME_DEPLOYMENT.md).
# Cloud Run compatible: listens on $PORT (default 8080).

# ---- frontend build ---------------------------------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- runtime -------------------------------------------------------------------------------------------
FROM python:3.12-slim AS app
ENV PIP_DEFAULT_TIMEOUT=300 PIP_RETRIES=10
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 XZR_STATIC=/app/static XZR_SCENARIOS=/app/backend/scenarios
WORKDIR /app
COPY backend/pyproject.toml ./backend/
COPY backend/xzr ./backend/xzr
RUN pip install --no-cache-dir ./backend
COPY backend/scenarios ./backend/scenarios
COPY --from=web /web/dist ./static
RUN useradd --system --uid 10001 xzr && chown -R xzr /app
USER xzr
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health')"
# one worker process: sessions live in memory (see docs/LIMITATIONS.md); simulation runs in threads inside it
# frame size and connection count are also bounded at the server, before the application sees a message
CMD ["sh", "-c", "exec uvicorn xzr.service.app:app --host 0.0.0.0 --port ${PORT} --app-dir /app/backend --ws-max-size ${XZR_WS_MAX_SIZE:-1048576} --limit-concurrency ${XZR_LIMIT_CONCURRENCY:-256} --timeout-keep-alive 15"]
