# infra/

Infrastructure configuration and provisioning scripts.
This folder contains **no application code** — only config files and setup scripts.

---

## What Goes Here

- Cloudflare resource configuration (D1, R2, Vectorize, Queues, Workers, Tunnel)
- Azure VM provisioning scripts and systemd service definitions
- Any other infrastructure-as-code

## What Does NOT Go Here

- Application code (goes in `packages/`)
- One-off data scripts (go in `scripts/`)
- Documentation (goes in `docs/`)

## The Split: Cloudflare vs Azure

| Platform | Responsibility |
|---|---|
| **Cloudflare** | Serverless resources: trace metadata (D1), trace blobs (R2), embeddings (Vectorize), async eval jobs (Queues), LLM inference (Workers AI), public HTTPS endpoint (Tunnel) |
| **Azure** | Persistent services: Langfuse + Postgres, eval-engine API, atlassian-remote API, Cloudflare Tunnel daemon |

Cloudflare handles everything stateless and globally distributed. Azure handles everything that needs to run persistently as a service.

## Sub-folders

- `cloudflare/` — `wrangler.toml` and migration files for all Cloudflare resources
- `azure/` — VM setup script, systemd service files, Nginx config
