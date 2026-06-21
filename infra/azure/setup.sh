#!/usr/bin/env bash
# setup.sh — Provision a fresh Ubuntu 24.04 Azure VM for Sentinel
#
# Run once on a new VM:
#   bash infra/azure/setup.sh
#
# What this installs:
#   - Docker + Docker Compose v2 (compose plugin)
#   - Python 3.12 (24.04 default) + uv (uv manages the project's pinned Python)
#   - Node.js 24 LTS + pnpm (via Corepack)
#   - cloudflared (Cloudflare Tunnel, via official apt repo)
#   - Langfuse v3 (self-hosted, Docker Compose)
#   - systemd services for eval-engine and atlassian-remote

set -euo pipefail

echo "=== Sentinel: Azure VM Setup ==="
. /etc/os-release
echo "OS: ${PRETTY_NAME}"
echo ""

# ── System packages ───────────────────────────────────────────────────────────
echo "→ Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    ca-certificates curl wget git build-essential gnupg \
    python3 python3-dev python3-venv python3-pip \
    nginx certbot python3-certbot-nginx \
    htop jq

# ── Docker ────────────────────────────────────────────────────────────────────
echo "→ Installing Docker..."
curl -fsSL https://get.docker.com | sudo bash
sudo usermod -aG docker "$USER"
sudo systemctl enable --now docker

# ── uv (Python package manager) ───────────────────────────────────────────────
echo "→ Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
# Modern uv installs to ~/.local/bin and writes its env file there.
source "$HOME/.local/bin/env"

# ── Node.js + pnpm ────────────────────────────────────────────────────────────
echo "→ Installing Node.js 24 LTS..."
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt-get install -y nodejs
# Corepack ships with Node and is the recommended way to manage pnpm.
sudo corepack enable
corepack prepare pnpm@latest --activate

# ── cloudflared (Cloudflare Tunnel) ───────────────────────────────────────────
echo "→ Installing cloudflared..."
# Use Cloudflare's apt repo so cloudflared receives security updates.
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
    | sudo tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" \
    | sudo tee /etc/apt/sources.list.d/cloudflared.list > /dev/null
sudo apt-get update -qq
sudo apt-get install -y cloudflared

# ── App directories ───────────────────────────────────────────────────────────
echo "→ Creating app directories..."
sudo mkdir -p /srv/sentinel/{eval-engine,atlassian-remote,langfuse,logs}
sudo chown -R "$USER":"$USER" /srv/sentinel

# ── Langfuse (self-hosted v3, Docker Compose) ─────────────────────────────────
echo "→ Setting up Langfuse..."
git clone https://github.com/langfuse/langfuse /srv/sentinel/langfuse 2>/dev/null || \
    git -C /srv/sentinel/langfuse pull
cd /srv/sentinel/langfuse

# Generate secrets. Langfuse v3 additionally requires ENCRYPTION_KEY (32-byte hex).
# These are picked up by the bundled docker-compose.yml via .env substitution.
NEXTAUTH_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
SALT=$(python3 -c "import secrets; print(secrets.token_hex(16))")
ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

cat > .env << EOF
# Langfuse v3 self-host secrets. The bundled docker-compose.yml runs
# Postgres + ClickHouse + Redis + MinIO automatically — only these need setting.
NEXTAUTH_URL=https://langfuse.YOURDOMAIN.com
NEXTAUTH_SECRET=${NEXTAUTH_SECRET}
SALT=${SALT}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
LANGFUSE_INIT_PROJECT_NAME=sentinel
EOF

echo ""
echo "  ⚠️  Edit /srv/sentinel/langfuse/.env and set NEXTAUTH_URL to your domain."
echo "  Then run: cd /srv/sentinel/langfuse && docker compose up -d"
echo ""

# ── systemd service: eval-engine ─────────────────────────────────────────────
echo "→ Creating systemd service: sentinel-eval..."
sudo tee /etc/systemd/system/sentinel-eval.service > /dev/null << EOF
[Unit]
Description=Sentinel Eval Engine (UC1)
After=network.target docker.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=/home/${USER}/AINS
EnvironmentFile=/srv/sentinel/.env
ExecStart=/home/${USER}/.local/bin/uv run uvicorn api:app --app-dir packages/eval-engine --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:/srv/sentinel/logs/eval-engine.log
StandardError=append:/srv/sentinel/logs/eval-engine.log

[Install]
WantedBy=multi-user.target
EOF

# ── systemd service: atlassian-remote ─────────────────────────────────────────
echo "→ Creating systemd service: sentinel-remote..."
sudo tee /etc/systemd/system/sentinel-remote.service > /dev/null << EOF
[Unit]
Description=Sentinel Atlassian Remote (UC3)
After=network.target docker.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=/home/${USER}/AINS
EnvironmentFile=/srv/sentinel/.env
ExecStart=/home/${USER}/.local/bin/uv run uvicorn api:app --app-dir packages/atlassian-remote --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5
StandardOutput=append:/srv/sentinel/logs/atlassian-remote.log
StandardError=append:/srv/sentinel/logs/atlassian-remote.log

[Install]
WantedBy=multi-user.target
EOF

# ── systemd service: flight-recorder ──────────────────────────────────────────
echo "→ Creating systemd service: sentinel-flight..."
sudo tee /etc/systemd/system/sentinel-flight.service > /dev/null << EOF
[Unit]
Description=Sentinel Flight Recorder (UC2)
After=network.target docker.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=/home/${USER}/AINS
EnvironmentFile=/srv/sentinel/.env
ExecStart=/home/${USER}/.local/bin/uv run uvicorn api:app --app-dir packages/flight-recorder --host 0.0.0.0 --port 8001
Restart=always
RestartSec=5
StandardOutput=append:/srv/sentinel/logs/flight-recorder.log
StandardError=append:/srv/sentinel/logs/flight-recorder.log

[Install]
WantedBy=multi-user.target
EOF

# ── systemd service: sentinel-dashboard ───────────────────────────────────────
# Next.js dashboard (UI). Build it first: `pnpm --filter dashboard build`. Server-
# side fetches use localhost so the UI shows live data without the public tunnel hop;
# clickable links (replay deep-link, Langfuse) stay on the public NEXT_PUBLIC_* URLs.
echo "→ Creating systemd service: sentinel-dashboard..."
sudo tee /etc/systemd/system/sentinel-dashboard.service > /dev/null << EOF
[Unit]
Description=Sentinel Dashboard (Next.js)
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=/srv/sentinel/dashboard
Environment=NODE_ENV=production
Environment=FLIGHT_RECORDER_INTERNAL_URL=http://localhost:8001
Environment=EVAL_ENGINE_INTERNAL_URL=http://localhost:8000
ExecStart=/usr/bin/node /srv/sentinel/dashboard/node_modules/next/dist/bin/next start -p 3001
Restart=always
RestartSec=5
StandardOutput=append:/srv/sentinel/logs/dashboard.log
StandardError=append:/srv/sentinel/logs/dashboard.log

[Install]
WantedBy=multi-user.target
EOF

# ── systemd service: cloudflared ──────────────────────────────────────────────
echo "→ Creating systemd service: cloudflared..."
sudo tee /etc/systemd/system/cloudflared.service > /dev/null << EOF
[Unit]
Description=Cloudflare Tunnel (Sentinel)
After=network.target

[Service]
Type=simple
User=${USER}
ExecStart=/usr/bin/cloudflared tunnel run sentinel
Restart=always
RestartSec=5
StandardOutput=append:/srv/sentinel/logs/cloudflared.log
StandardError=append:/srv/sentinel/logs/cloudflared.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable sentinel-eval sentinel-remote sentinel-flight sentinel-dashboard cloudflared

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Create Cloudflare Tunnel: cloudflared tunnel login && cloudflared tunnel create sentinel"
echo "  2. Edit /srv/sentinel/langfuse/.env with your domain"
echo "  3. Start Langfuse: cd /srv/sentinel/langfuse && docker compose up -d"
echo "  4. Clone the repo to /home/\${USER}/AINS (the Python services run from there via"
echo "     'uv run uvicorn ... --app-dir packages/<pkg>'); only the dashboard is built under"
echo "     /srv/sentinel/dashboard"
echo "  5. Copy .env to /srv/sentinel/.env"
echo "  6. Build the dashboard: cd /srv/sentinel/dashboard && pnpm install && pnpm build"
echo "  7. Add tunnel ingress hostnames in ~/.cloudflared/config.yml (one per service:"
echo "     langfuse:3000 eval:8000 remote:8080 flight:8001 dashboard:3001) and create the"
echo "     DNS routes, e.g.: cloudflared tunnel route dns sentinel dashboard.ahmedxsaad.me"
echo "  8. Start services: sudo systemctl start sentinel-eval sentinel-remote sentinel-flight sentinel-dashboard cloudflared"
echo ""
echo "  Note: log out and back in (or run 'newgrp docker') so your user picks up"
echo "        the docker group before running docker compose."
echo ""
