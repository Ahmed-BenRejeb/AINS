# infra/cloudflare/

Cloudflare resource definitions for Sentinel.

## Resources

| Resource | Name | Used By | Purpose |
|---|---|---|---|
| D1 (SQLite) | `sentinel-traces` | flight-recorder, eval-engine | Trace metadata, step index, verdicts |
| R2 (Object storage) | `sentinel-cassettes` | flight-recorder | Full trace blobs, prompt contents, cassettes |
| Vectorize | `sentinel-embeddings` | atlassian-remote, eval-engine | Incident + runbook embeddings for search and drift |
| Queues | `sentinel-eval-queue` | eval-engine | Async evaluation job queue |
| Workers AI | (shared) | atlassian-remote, eval-engine | Llama Guard 3, BGE-Base-EN embeddings |
| Tunnel | `sentinel` | infra | Expose Azure VM services via stable HTTPS URL |

## Setup

```bash
npm install -g wrangler
wrangler login

wrangler d1 create sentinel-traces
wrangler r2 bucket create sentinel-cassettes
wrangler vectorize create sentinel-embeddings --dimensions=768 --metric=cosine
wrangler queues create sentinel-eval-queue
```

Add the IDs returned by these commands to your `.env` file.
