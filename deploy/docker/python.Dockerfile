# One image for all three Sentinel FastAPI services (they share a uv workspace).
# Each Deployment overrides the command to pick its service + port:
#   eval-engine     : uvicorn api:app --app-dir packages/eval-engine     --port 8000
#   flight-recorder : uvicorn api:app --app-dir packages/flight-recorder --port 8001
#   atlassian-remote: uvicorn api:app --app-dir packages/atlassian-remote --port 8080
#
# Build from the REPO ROOT (the build context must be the workspace root):
#   docker build -f deploy/docker/python.Dockerfile -t sentinel-python:dev .
#
# ── Builder: resolve the uv workspace into a self-contained .venv ──────────────
FROM python:3.11-slim AS builder

# uv: the project's package manager (pinned to the repo's version).
RUN pip install --no-cache-dir uv==0.11.23

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app

# Copy the workspace manifests first so dependency resolution is cached across
# source-only changes. (The lockfile is the single source of truth.)
COPY pyproject.toml uv.lock ./
COPY packages/trace-core/pyproject.toml      packages/trace-core/pyproject.toml
COPY packages/flight-recorder/pyproject.toml packages/flight-recorder/pyproject.toml
COPY packages/eval-engine/pyproject.toml     packages/eval-engine/pyproject.toml
COPY packages/atlassian-remote/pyproject.toml packages/atlassian-remote/pyproject.toml

# Then the full source for the workspace members (api.py lives at each package root;
# the importable code is under packages/<pkg>/src/<pkg>). .dockerignore keeps
# node_modules / caches / .env out of the context.
COPY packages/ packages/

# Reproducible, prod-only install (no dev tools) into /app/.venv.
RUN uv sync --all-packages --no-dev --frozen

# ── Runtime: slim image with just the venv + source ───────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app

# Run as a non-root user (defense in depth; the services need no root).
RUN useradd --create-home --uid 10001 sentinel
COPY --from=builder --chown=sentinel:sentinel /app /app
USER sentinel

# Documentation only; the actual port comes from each Deployment's command.
EXPOSE 8000 8001 8080

# Default to the eval engine; Deployments override `command`/`args` per service.
CMD ["uvicorn", "api:app", "--app-dir", "packages/eval-engine", "--host", "0.0.0.0", "--port", "8000"]
