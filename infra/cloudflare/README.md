# infra/cloudflare/

Cloudflare resource definitions for Sentinel.

## Resources

| Resource | Name | Used By | Purpose |
|---|---|---|---|
| D1 (SQLite) | `sentinel-traces` | flight-recorder, eval-engine | Trace metadata, step index, verdicts |
| Vectorize | `sentinel-embeddings` | atlassian-remote, eval-engine | Incident + runbook embeddings (768-dim, cosine) |
| Workers AI | (shared) | atlassian-remote, eval-engine | Llama 3.3 70B, Llama Guard 3, BGE-Base-EN embeddings |
| Tunnel | `sentinel` | infra | Expose Azure VM services via stable HTTPS URL |

### Tunnel ingress (`~/.cloudflared/config.yml` on the VM)

Each public hostname is an ingress rule routing to a local port; add the matching
proxied DNS CNAME with `cloudflared tunnel route dns sentinel <hostname>`.

| Hostname | → local service |
|---|---|
| `langfuse.ahmedxsaad.me` | `http://localhost:3000` |
| `eval.ahmedxsaad.me` | `http://localhost:8000` |
| `remote.ahmedxsaad.me` | `http://localhost:8080` |
| `flight.ahmedxsaad.me` | `http://localhost:8001` |
| `dashboard.ahmedxsaad.me` | `http://localhost:3001` |

> The zone enforces a Cloudflare **managed/bot challenge**: browsers pass (sometimes
> after a one-time interstitial), but `curl`/bots get `403 cf-mitigated: challenge`.
> A shell 403 against these hostnames is expected, not an outage.

> **Skipped (see root `CLAUDE.md` §9 decisions log):**
> - **R2** (`sentinel-cassettes`) — requires a credit card; replaced by **MinIO** (S3-compatible)
>   running in the Langfuse Docker stack on the Azure VM (`localhost:9090`).
> - **Queues** (`sentinel-eval-queue`) — auth issues + not critical; the eval engine uses
>   synchronous calls instead.

## Setup

```bash
npm install -g wrangler
wrangler login

wrangler d1 create sentinel-traces
wrangler vectorize create sentinel-embeddings --dimensions=768 --metric=cosine
```

Add the IDs returned by these commands to your `.env` file.
Blob storage (cassettes/trace blobs) is MinIO, not R2 — see the `BLOB_STORAGE_*` env vars.
