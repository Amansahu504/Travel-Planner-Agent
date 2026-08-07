# Single image for every service — docker-compose selects the module to run.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# uv for fast, lockfile-faithful installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies first so code edits don't invalidate this layer. uv
# creates /app/.venv; putting it on PATH makes `python` resolve to it. Prefer
# the frozen lockfile; fall back to a fresh resolve if the lock is out of date.
COPY pyproject.toml uv.lock* README.md ./
RUN uv sync --frozen --no-dev || uv sync --no-dev
ENV PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV="/app/.venv"

# Application code (data/, .env, .venv are excluded via .dockerignore; data is
# supplied at runtime through the ./data volume mount).
COPY common/ ./common/
COPY mcp_server_1/ ./mcp_server_1/
COPY mcp_server_2/ ./mcp_server_2/
COPY mcp_server_3/ ./mcp_server_3/
COPY remote_agent_1/ ./remote_agent_1/
COPY remote_agent_2/ ./remote_agent_2/
COPY host_agent/ ./host_agent/
COPY ingest/ ./ingest/
COPY scripts/ ./scripts/
COPY tests/ ./tests/
COPY run_all.py ./

# Bind on all interfaces inside a container; peers are reached via the
# *_URL environment variables that docker-compose sets to service names.
ENV HOST=0.0.0.0

# Overridden per service in docker-compose.yml.
CMD ["python", "-m", "mcp_server_1.main"]
