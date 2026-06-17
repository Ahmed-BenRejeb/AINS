-- d1-schema.sql
-- Sentinel D1 database schema (Cloudflare SQLite)
-- Apply with: wrangler d1 migrations apply sentinel-traces

-- ── Trace Records (flight recorder output) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS trace_records (
    id            TEXT PRIMARY KEY,          -- step_id UUID
    run_id        TEXT NOT NULL,
    sequence      INTEGER NOT NULL,
    kind          TEXT NOT NULL,             -- llm_call | tool_call | decision | state_snapshot
    timestamp_utc TEXT NOT NULL,             -- ISO-8601
    payload_hash  TEXT NOT NULL,             -- SHA-256 of canonical JSON
    prev_hash     TEXT,                      -- hash chain link
    hmac          TEXT NOT NULL,             -- HMAC-SHA256 tamper evidence
    blob_key      TEXT,                      -- R2 key for full input/output blob (if large)
    input_preview TEXT,                      -- first 500 chars of input (for listing)
    output_preview TEXT,                     -- first 500 chars of output (for listing)
    metadata_json TEXT,                      -- model_id, tool_name, latency_ms, etc.
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_trace_records_run_id ON trace_records(run_id);
CREATE INDEX IF NOT EXISTS idx_trace_records_kind   ON trace_records(kind);

-- ── Run Manifests (one per agent run) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS run_manifests (
    run_id        TEXT PRIMARY KEY,
    agent_id      TEXT NOT NULL,
    task_id       TEXT,
    flight_mode   TEXT NOT NULL,             -- record | replay | passthrough
    cassette_id   TEXT,                      -- R2 key for the full cassette
    step_count    INTEGER DEFAULT 0,
    status        TEXT DEFAULT 'active',     -- active | complete | failed
    started_at    TEXT NOT NULL,
    completed_at  TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_run_manifests_agent_id ON run_manifests(agent_id);
CREATE INDEX IF NOT EXISTS idx_run_manifests_status   ON run_manifests(status);

-- ── Eval Verdicts (eval engine output) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS eval_verdicts (
    id               TEXT PRIMARY KEY,       -- verdict UUID
    run_id           TEXT NOT NULL,
    trial_number     INTEGER NOT NULL,
    verdict          TEXT NOT NULL,          -- pass | fail | uncertain
    overall_score    REAL,
    confidence       REAL,
    flag_for_human   INTEGER DEFAULT 0,      -- SQLite boolean (0/1)
    attribution_step INTEGER,
    attribution_component TEXT,
    dimensions_json  TEXT,                   -- per-dimension scores as JSON
    self_critique    TEXT,
    replay_link      TEXT,
    recommended_action TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES run_manifests(run_id)
);

CREATE INDEX IF NOT EXISTS idx_eval_verdicts_run_id  ON eval_verdicts(run_id);
CREATE INDEX IF NOT EXISTS idx_eval_verdicts_verdict ON eval_verdicts(verdict);
CREATE INDEX IF NOT EXISTS idx_eval_verdicts_flag    ON eval_verdicts(flag_for_human);
