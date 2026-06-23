#!/usr/bin/env python3
"""make_bisect_pair.py — build a good/bad run pair that diverges at the RCA step.

Demo aid for UC2 bisect. Records two runs of the SAME incident whose embedding and
retrieval steps are byte-identical, but whose final RCA *response* differs — the
non-determinism the brief is about (same prompt, different conclusion). Bisect then
reports the RCA step as the first divergence with a readable good-vs-bad output diff,
instead of the trivial "different incident diverges at step 0".

Both runs are written as real cassettes (MinIO) + audit chain + run manifests (D1),
so they appear on the dashboard ``/runs`` and bisect works live. Run ids are
deterministic, and existing rows for them are cleared first, so it is re-runnable.

Usage::

    set -a; source /srv/sentinel/.env; set +a
    uv run python scripts/make_bisect_pair.py

Reads: ``CLOUDFLARE_ACCOUNT_ID`` / ``CLOUDFLARE_API_TOKEN`` / ``CF_D1_DATABASE_ID``
(D1), ``BLOB_STORAGE_*`` (MinIO), ``AUDIT_HMAC_KEY``, ``CF_AI_MODEL_*``.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import UTC, datetime

import httpx
from flight_recorder.audit.hash_chain import sign, write_audit_record
from flight_recorder.config import GENESIS_PREV_HASH
from flight_recorder.manifest import write_run_manifest
from flight_recorder.proxy import cassette
from flight_recorder.storage import d1_client
from trace_core import RunManifest

_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
GOOD_RUN = uuid.uuid5(_NS, "sentinel-demo-bisect-good").hex
BAD_RUN = uuid.uuid5(_NS, "sentinel-demo-bisect-bad").hex

EMBED_MODEL = os.environ.get("CF_AI_MODEL_EMBED", "@cf/baai/bge-base-en-v1.5")
MAIN_MODEL = os.environ.get("CF_AI_MODEL_MAIN", "@cf/meta/llama-3.1-8b-instruct-fp8-fast")
_BASE = (
    f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CLOUDFLARE_ACCOUNT_ID']}/ai/run"
)

INCIDENT = (
    "DB connection pool exhausted on prod\n\n"
    "All database connections consumed; app servers queuing requests; DB CPU at 95%."
)
RCA_PROMPT = [
    {"role": "system", "content": "You are Sentinel, an incident RCA assistant. Output JSON."},
    {"role": "user", "content": f"INCIDENT:\n{INCIDENT}\n\nDraft a root-cause analysis as JSON."},
]
# Same incident + same prompt -> identical request key; only the RESPONSE differs.
GOOD_RCA = json.dumps(
    {
        "root_cause_hypothesis": "Database connection pool exhaustion: pool size too small for "
        "peak concurrency, connections not released, cascading to all services.",
        "proposed_severity": "critical",
        "proposed_assignee_team": "Database Platform",
        "confidence_score": 0.91,
    }
)
BAD_RCA = json.dumps(
    {
        "root_cause_hypothesis": "Transient network blip; likely self-resolved, no action needed.",
        "proposed_severity": "low",
        "proposed_assignee_team": "Unassigned",
        "confidence_score": 0.38,
    }
)


def _req(model: str, body: dict[str, object]) -> httpx.Request:
    return httpx.Request("POST", f"{_BASE}/{model}", json=body)


def _key(req: httpx.Request) -> str:
    return cassette.hash_step_key(cassette.normalize_request(req))


def _stored(body: dict[str, object]) -> dict[str, object]:
    return {
        "status_code": 200,
        "headers": {"content-type": "application/json"},
        "is_json": True,
        "body": body,
    }


class _Recorder:
    """Minimal re-implementation of the recording transport's persist, for fixtures."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.prev = GENESIS_PREV_HASH
        self.seq = 0

    def _audit(
        self, step_id: str, kind: str, inp: dict, out: dict, meta: dict, ip: str, op: str
    ) -> None:
        self.prev = write_audit_record(
            run_id=self.run_id,
            step_id=step_id,
            kind=kind,
            input_data=inp,
            output_data=out,
            prev_hash=self.prev,
            sequence=self.seq,
            input_preview=ip,
            output_preview=op,
            metadata=meta,
        )

    def _record(self, step_id: str, kind: str, inp: dict, out: dict, meta: dict, prev: str) -> dict:
        return {
            "run_id": self.run_id,
            "step_id": step_id,
            "sequence": self.seq,
            "timestamp": datetime.now(UTC).isoformat(),
            "kind": kind,
            "input": inp,
            "output": out,
            "metadata": meta,
            "audit": {"prev_hash": prev, "payload_hash": self.prev, "hmac": sign(self.prev)},
        }

    def http(
        self, req: httpx.Request, stored: dict, op: str, model: str, ip: str, opv: str
    ) -> None:
        """Record a replayable HTTP step (embed / chat) into steps + records."""
        prev, step_id = self.prev, uuid.uuid4().hex
        key = _key(req)
        inp = {"step_key": key, "path": req.url.path, "body": json.loads(req.content)}
        meta = {"model_id": model, "operation": op}
        self._audit(step_id, "llm_call", inp, stored, meta, ip, opv)
        cassette.save_to_cassette(
            self.run_id,
            key,
            stored,
            record=self._record(step_id, "llm_call", inp, stored, meta, prev),
        )
        self.seq += 1

    def tool(self, tool: str, args: dict, out: dict, ip: str, opv: str) -> None:
        """Record a records-only tool step (xqdrant search) — not replayable, enriches the trace."""
        prev, step_id = self.prev, uuid.uuid4().hex
        inp = {"tool_name": tool, "arguments": args}
        meta = {"tool_name": tool, "operation": "retrieval"}
        self._audit(step_id, "tool_call", inp, out, meta, ip, opv)
        cassette.append_record(
            self.run_id, self._record(step_id, "tool_call", inp, out, meta, prev)
        )
        self.seq += 1


def _clear(run_id: str) -> None:
    for table in ("trace_records", "eval_verdicts", "run_manifests"):
        try:
            d1_client.query(f"DELETE FROM {table} WHERE run_id = ?", [run_id])
        except Exception as exc:  # best-effort cleanup so the script is re-runnable
            print(f"  (clear {table} skip: {exc})")


def build(run_id: str, task_id: str, rca_response: str) -> None:
    """Build one run: embed -> search incidents -> search runbooks -> RCA."""
    _clear(run_id)
    started = datetime.now(UTC)
    r = _Recorder(run_id)
    r.http(
        _req(EMBED_MODEL, {"text": [INCIDENT[:2000]]}),
        _stored({"result": {"data": [[0.01] * 768]}, "success": True}),
        "embedding",
        EMBED_MODEL,
        "embed 1 text(s): DB connection pool exhausted on prod",
        "1 embedding vector(s), 768-dim",
    )
    r.tool(
        "xqdrant.query_points",
        {"collection": "incidents", "k": 5},
        {"count": 3, "top_score": 0.86},
        "search incidents (k=5)",
        "3 hits, top 0.86",
    )
    r.tool(
        "xqdrant.query_points",
        {"collection": "runbooks", "k": 5},
        {"count": 2, "top_score": 0.72},
        "search runbooks (k=5)",
        "2 hits, top 0.72",
    )
    r.http(
        _req(MAIN_MODEL, {"messages": RCA_PROMPT, "max_tokens": 1024}),
        _stored({"result": {"response": rca_response}}),
        "chat",
        MAIN_MODEL,
        "chat: INCIDENT: DB connection pool exhausted on prod ...",
        rca_response[:180],
    )
    write_run_manifest(
        RunManifest(
            run_id=run_id,
            agent_id="atlassian-remote",
            task_id=task_id,
            flight_mode="record",
            cassette_id=f"{run_id}.json",
            step_count=r.seq,
            status="completed",
            started_at=started,
            completed_at=datetime.now(UTC),
        )
    )


def main() -> int:
    """Build the good/bad pair and print a ready-to-run bisect command."""
    print("→ Building good/bad bisect demo pair (same incident, divergent RCA)...")
    build(GOOD_RUN, "DEMO-bisect (good RCA)", GOOD_RCA)
    build(BAD_RUN, "DEMO-bisect (bad RCA)", BAD_RCA)
    print(f"✓ good run: {GOOD_RUN}")
    print(f"✓ bad  run: {BAD_RUN}")
    print("\nBisect them (diverges at the RCA step — same request, different conclusion):")
    print(
        f'  curl -s -X POST localhost:8001/bisect -H "Content-Type: application/json" '
        f'-d \'{{"good_run_id":"{GOOD_RUN}","bad_run_id":"{BAD_RUN}"}}\' | jq'
    )
    print(f"\nOr on the dashboard: open /replay/{GOOD_RUN} and paste the bad id into Bisect.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
