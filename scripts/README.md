# scripts/

One-off scripts for data seeding, evaluation runs, and migrations.
These are not importable modules — they are run directly from the command line via `make` targets.

---

## What Goes Here

- Data seeding scripts (create synthetic Atlassian incidents, Confluence runbooks)
- Evaluation runner scripts (run the eval suite, generate reports)
- Index population scripts (embed and upload data to Cloudflare Vectorize)
- Any other one-time or periodic operational scripts

## What Does NOT Go Here

- Application code (goes in `packages/`)
- Infrastructure config (goes in `infra/`)
- Test fixtures — those live in each package's `tests/fixtures/` directory

## Scripts

| Script | Command | What It Does |
|---|---|---|
| `seed_atlassian.py` | `make seed` | Creates 100 synthetic JSM incidents + 10 Confluence runbooks (one per root-cause category) on the dev site |
| `seed_xqdrant.py` | `make seed-xqdrant` | Embeds the seeded incidents + runbooks with BGE-768 and loads them into xqdrant for retrieval |
| `seed_custom_incidents.py` | `make seed-custom CSV=<path>` | Seeds a company's own incidents from a CSV into Jira AO + xqdrant for a tailored demo |
| `run_synthetic_eval.py` | `make eval` | Runs the eval suite on synthetic traces, outputs `pass^k` report to `docs/eval_report.md` |
| `make_bisect_pair.py` | `make bisect-demo` | Builds a good/bad run pair that diverges at the RCA step (for the bisect demo) |
| `check_docs.py` | `make check-docs` | Verifies `.env.example` + docs haven't drifted from the code (run before every commit) |

## Run Order (First-Time Setup)

```bash
# 1. Seed Atlassian with synthetic data
make seed

# 2. Embed those incidents + runbooks into xqdrant (required for retrieval to return results)
make seed-xqdrant

# 3. Run the eval suite on the resulting traces
make eval
```

## Adding a New Script

1. Create the script in `scripts/`
2. Add a `make` target in `Makefile` so teammates don't need to remember the command
3. Document it in this README's "Scripts" table
