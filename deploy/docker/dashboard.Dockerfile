# Sentinel dashboard (Next.js) image.
# The dashboard is self-contained (its types mirror trace-core; it imports no other
# workspace package), so it builds standalone with --ignore-workspace.
#
# Build from the REPO ROOT:
#   docker build -f deploy/docker/dashboard.Dockerfile -t sentinel-dashboard:dev .
#
# Runtime service URLs (server-side fetches) come from the Deployment env:
#   FLIGHT_RECORDER_INTERNAL_URL=http://flight-recorder:8001
#   EVAL_ENGINE_INTERNAL_URL=http://eval-engine:8000
#
# ── Builder ───────────────────────────────────────────────────────────────────
FROM node:20-slim AS builder
RUN corepack enable
WORKDIR /app

# Deps first (layer cache). The dashboard has no workspace-internal deps.
COPY packages/dashboard/package.json ./
RUN pnpm install --ignore-workspace --no-frozen-lockfile

# Source + production build (.next).
COPY packages/dashboard/ ./
RUN pnpm build

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM node:20-slim AS runtime
RUN corepack enable
ENV NODE_ENV=production
WORKDIR /app
RUN useradd --create-home --uid 10001 sentinel

# Carry the built app (.next + node_modules + source) from the builder.
COPY --from=builder --chown=sentinel:sentinel /app /app
USER sentinel

EXPOSE 3001
CMD ["pnpm", "start"]
