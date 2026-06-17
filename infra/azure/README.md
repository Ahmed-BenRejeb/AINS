# infra/azure/

Azure VM provisioning for Sentinel's persistent services.

## What Runs on the VM

| Service | Port | Description |
|---|---|---|
| Langfuse v3 | 3000 | Self-hosted trace + eval UI (Docker) |
| Postgres + ClickHouse + Redis + MinIO | — | Langfuse v3's backing stores (Docker, bundled compose) |
| eval-engine API | 8000 | FastAPI — evaluation pipeline |
| atlassian-remote API | 8080 | FastAPI — Forge Remote backend |
| cloudflared | — | Cloudflare Tunnel daemon (exposes services) |

> Langfuse v3 runs a multi-container stack (Postgres, ClickHouse, Redis, MinIO). The
> bundled `docker-compose.yml` provisions all of them — Standard_B2s (4 GB RAM) is the
> practical minimum; bump to Standard_B2ms (8 GB) if the stack gets OOM-killed.

## VM Spec (Azure for Students — $100 credit)

- **Type:** Standard_B2s (2 vCPU, 4 GB RAM)
- **OS:** Ubuntu 24.04 LTS
- **Open ports:** 22 (SSH only — all other traffic via Cloudflare Tunnel)

## Setup

```bash
# Run once on a fresh VM
bash infra/azure/setup.sh
```

The `setup.sh` script installs Docker (with Compose v2), Python 3.12 + `uv`, Node.js 24 LTS + `pnpm` (via Corepack), `cloudflared` (from Cloudflare's apt repo), pulls Langfuse v3, and configures systemd services for the eval-engine and atlassian-remote APIs.

## Important

All external traffic goes through Cloudflare Tunnel — never expose the VM's raw IP. The only open port should be 22 (SSH). Everything else is routed via `cloudflared`.
