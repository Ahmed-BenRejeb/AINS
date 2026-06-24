# infra/

Infrastructure configuration and provisioning scripts.
This folder contains **no application code** — only config files and setup scripts.

---

## What Goes Here

- Cloudflare resource configuration (D1, Vectorize, Workers AI, Tunnel)
- Azure VM provisioning scripts and systemd service definitions
- Any other infrastructure-as-code

> Blob storage uses **MinIO** (on the Azure VM at port 9090, inside the Langfuse Docker stack), not Cloudflare R2; **Queues** were skipped (sync eval calls). See root `CLAUDE.md` §9.

## What Does NOT Go Here

- Application code (goes in `packages/`)
- One-off data scripts (go in `scripts/`)
- Documentation (goes in `docs/`)

## The Split: Cloudflare vs Azure

| Platform | Responsibility |
|---|---|
| **Cloudflare** | Serverless resources: trace metadata (D1), embeddings (Vectorize), LLM inference (Workers AI), public HTTPS endpoint (Tunnel). Trace blobs/cassettes use MinIO on Azure (not R2) |
| **Azure** | Persistent services: Langfuse + Postgres, eval-engine API, atlassian-remote API, Cloudflare Tunnel daemon |

Cloudflare handles everything stateless and globally distributed. Azure handles everything that needs to run persistently as a service.

## Sub-folders

- `cloudflare/` — `wrangler.toml` and migration files for all Cloudflare resources
- `azure/` — VM provisioning script and systemd service unit files (no Nginx — public HTTPS is via the Cloudflare Tunnel daemon `cloudflared`)

> For Kubernetes/Helm/KEDA production deployment see `deploy/` at the repo root.
