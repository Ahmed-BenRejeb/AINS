# Sentinel — Security Audit & Hardening

> Deep security review of the deployed stack and the hardening applied. Date:
> 2026-06-23. Scope: the three public FastAPI services (eval-engine :8000,
> flight-recorder :8001, atlassian-remote :8080), the dashboard (:3001), the data
> stores (D1, MinIO, xqdrant), secrets handling, and the Atlassian/Forge surface.

---

## 1. Method

Reviewed every internet-reachable entry point (services are exposed via the
Cloudflare tunnel), the trust boundaries between them, input handling on each
route, secrets storage, and the data stores. Severities are CVSS-style qualitative
(Critical/High/Medium/Low/Info).

---

## 2. Findings & status

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | **High** | **eval-engine (:8000) and flight-recorder (:8001) had no authentication** — exposed via tunnel. `GET /runs`, `/runs/{id}`, `/verdicts` leaked recorded traces (prompts/incident text); `/replay`, `/bisect`, `/evaluate`, `/drift`, `/evaluator-quality` were freely triggerable; `/evaluate` burns CF neurons and can file Jira issues. | **Fixed** — shared-secret `X-Sentinel-Secret` gate (constant-time) on every route except `/health`, matching atlassian-remote. |
| 2 | **Medium** | `/evaluate` abuse: arbitrary `records` run the LLM judge (neuron burn) and could file an AO Jira Incident, unauthenticated. | **Fixed** — now behind auth; `/evaluate/batch` capped at 64 run_ids; `/verdicts?limit` clamped to ≤500. |
| 3 | **Medium** | **`run_id` used unvalidated** as a MinIO object key (`{run_id}.json`), D1 query param, and URL path → path-traversal / injection sink. | **Fixed** — `valid_run_id()` rejects anything that is not a uuid (hex or dashed) with 400, on `/runs/{id}`, `/replay`, `/bisect`, `/evaluate`, `/verdicts/{id}`. |
| 4 | **Low** | `d1_client.insert` interpolated table/column **identifiers** into SQL (values were always parameterised). Safe today (callers pass constants) but a latent injection sink. | **Fixed** — identifier allowlist `^[A-Za-z_][A-Za-z0-9_]*$` enforced before interpolation. |
| 5 | **Low** | Quota/abuse: no per-route size caps. | **Partly fixed** — batch + verdict-limit caps added (see #2). Network-level rate limiting still recommended (see §4). |
| 6 | **Info** | No CORS middleware is configured — dashboard fetches are **server-side**, so no browser CORS is needed and none is opened (good: no permissive `*` origin). | OK by design |
| 7 | **Info** | Secrets are **not** in the repo (`.env` is gitignored; lives at `/srv/sentinel/.env`, chmod 600). The dashboard reads the secret from its systemd `Environment`, never the browser. | OK |

---

## 3. What was already sound (verified, no change)

- **MinIO (:9090) and xqdrant (:6333) are internal-only** — never exposed via the
  tunnel; only the VM-local services reach them.
- **Tamper-evident audit trail** — every recorded step is hash-chained and
  HMAC-SHA256 signed (`AUDIT_HMAC_KEY`); `verify_chain` detects any edit. Previews/
  metadata are display-only and excluded from the hash, so enriching them never
  weakens the chain.
- **Constant-time secret comparison** (`hmac.compare_digest`) everywhere a secret is
  checked (atlassian-remote already; now eval/flight too).
- **Fail-safe error handling** — upstream LLM errors map to 503 (not 500 with a
  stack trace); D1/MinIO/Jira writes are best-effort and never crash a request;
  the LLM judge never trusts free text (Pydantic-validated structured outputs).
- **Atlassian writes are least-surprise** — issue creation is constrained to the AO
  project + the Incident type id; auto-linking duplicates only above a strict
  confidence (0.85), else it flags for a human.

---

## 4. Residual risks & recommendations (before a production deployment)

| Priority | Recommendation |
|---|---|
| High | **Rate-limit at the edge.** The shared secret stops anonymous abuse, but add a Cloudflare rate-limit rule (or WAF) on the `*.ahmedxsaad.me` hostnames to cap request volume / neuron burn even from a holder of the secret. |
| Medium | **Per-service distinct secrets + rotation.** Today all services share `FORGE_REMOTE_SECRET`. For real multi-tenant use, issue per-service secrets and rotate on a schedule; consider mTLS or a signed-JWT between services. |
| Medium | **Structured audit logging.** `LOG_LEVEL` exists but no request/audit logger is wired; add per-request logging (account id, route, run_id, status) for incident response. |
| Low | **Default `file_issue=False` on the public `/evaluate`.** Auth already closes the abuse vector, but defaulting issue-filing off on the raw route (and having the analyzer opt in) is defense in depth. |
| Low | **Forge deploy** the Rovo agent so UC3 runs inside Atlassian's own auth/permission model rather than only the Forge Remote backend. |

---

## 5. Verification (live, 2026-06-23)

```
unauthenticated:  flight /runs → 401 · eval /verdicts → 401 · eval /evaluate → 401
authenticated:    flight /runs → 200 · eval /verdicts → 200   (X-Sentinel-Secret)
run_id guard:     POST /replay {"run_id":"../etc/passwd"} → 400
health (open):    /health → 200
dashboard:        home LIVE (server-side secret), /runs page 200
end-to-end:       /analyze AO-133 → eval_verdict populated (remote→eval auth OK)
```

165 Python tests pass (incl. 5 new auth/validation regression tests); per-package
ruff + `mypy --strict` clean on eval-engine / flight-recorder / atlassian-remote;
`check-docs` clean.
