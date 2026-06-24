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
# Node 22 + a PINNED pnpm: `corepack enable` alone pulls the latest pnpm (11.x),
# which needs Node 22.13+ (node:sqlite) and breaks on older bases. Pinning to the
# repo's pnpm (10.33.4) keeps the build reproducible.
FROM node:22-slim AS builder
RUN corepack enable && corepack prepare pnpm@10.33.4 --activate
WORKDIR /app

# Deps first (layer cache). The dashboard has no workspace-internal deps.
COPY packages/dashboard/package.json ./
RUN pnpm install --ignore-workspace --no-frozen-lockfile

# Source + production build (.next).
COPY packages/dashboard/ ./
RUN pnpm build

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM node:22-slim AS runtime
ENV NODE_ENV=production
WORKDIR /app
RUN useradd --create-home --uid 10001 sentinel

# Carry the built app (.next + node_modules + source) from the builder.
COPY --from=builder --chown=sentinel:sentinel /app /app
USER sentinel

EXPOSE 3001
# Run Next directly (no pnpm/corepack needed at runtime); matches the VM's systemd unit.
CMD ["node", "node_modules/next/dist/bin/next", "start", "-p", "3001"]
