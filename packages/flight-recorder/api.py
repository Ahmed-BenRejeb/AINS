"""Flight Recorder HTTP API (UC2).

FastAPI service on port 8001 (exposed at ``flight.ahmedxsaad.me``). Lists recorded
runs and their traces from Cloudflare D1, and runs deterministic replay / bisect
over their cassettes.

Run locally::

    FLIGHT_MODE=replay uv run uvicorn api:app --port 8001
"""

from __future__ import annotations

import hmac
import os
import re
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from flight_recorder.config import RUN_MANIFESTS_TABLE
from flight_recorder.langfuse_client import init_langfuse
from flight_recorder.replay.bisect import BisectResult, bisect_runs
from flight_recorder.replay.engine import ReplayResult, replay_run
from flight_recorder.storage import d1_client
from pydantic import BaseModel, Field

app = FastAPI(title="Sentinel Flight Recorder", version="0.1.0")

# Initialise Langfuse observability at startup (no-op if LANGFUSE_* is unset).
init_langfuse()

# Expose Prometheus metrics when prometheus_fastapi_instrumentator is installed
# (optional — only present in the K8s/KEDA deployment; not installed on the VM).
try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app, include_in_schema=False)
except ImportError:
    pass

_RUN_ID_RE = re.compile(r"^[0-9a-fA-F]{32}$|^[0-9a-fA-F-]{36}$")


def require_secret(x_sentinel_secret: str | None = Header(default=None)) -> None:
    """Shared-secret gate (constant-time). Enforced only when ``FORGE_REMOTE_SECRET``
    is set (the VM); a no-op in local/test so the suite stays open. ``/health`` open."""
    expected = os.environ.get("FORGE_REMOTE_SECRET")
    if not expected:
        return
    if not x_sentinel_secret or not hmac.compare_digest(x_sentinel_secret, expected):
        raise HTTPException(status_code=401, detail="missing or invalid X-Sentinel-Secret")


def valid_run_id(run_id: str) -> str:
    """Reject non-uuid run ids before they become D1 params / replay keys."""
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="run_id must be a uuid")
    return run_id


_AUTH = [Depends(require_secret)]


class ReplayRequest(BaseModel):
    """Body for ``POST /replay``."""

    run_id: str = Field(description="UUID of the run to replay.")
    inject: dict[int, dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Divergence editing (UC2 §3.4): a {step_index: stored_response} map that "
            "overrides the recorded response at those steps during replay."
        ),
    )


class BisectRequest(BaseModel):
    """Body for ``POST /bisect``."""

    good_run_id: str = Field(description="UUID of the known-good run.")
    bad_run_id: str = Field(description="UUID of the known-bad run.")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/runs", dependencies=_AUTH)
def list_runs() -> list[dict[str, Any]]:
    """List all recorded run manifests, newest first."""
    return d1_client.query(
        f"SELECT * FROM {RUN_MANIFESTS_TABLE} ORDER BY started_at DESC",
    )


@app.get("/runs/{run_id}", dependencies=_AUTH)
def get_run(run_id: str) -> dict[str, Any]:
    """Return a run's manifest plus its ordered trace records.

    Args:
        run_id: UUID of the run.

    Returns:
        ``{"run_id", "manifest", "trace"}`` where ``trace`` is the ordered
        ``trace_records`` rows for the run.
    """
    valid_run_id(run_id)
    manifest = d1_client.query(
        f"SELECT * FROM {RUN_MANIFESTS_TABLE} WHERE run_id = ?",
        [run_id],
    )
    trace = d1_client.query(
        "SELECT * FROM trace_records WHERE run_id = ? ORDER BY sequence ASC",
        [run_id],
    )
    return {"run_id": run_id, "manifest": manifest[0] if manifest else None, "trace": trace}


@app.post("/replay", dependencies=_AUTH)
def post_replay(request: ReplayRequest) -> ReplayResult:
    """Replay a run from its cassette and return the divergence report.

    Re-drives the recorded CF calls from tape (zero live calls). When ``inject`` is
    given, the listed steps' responses are overridden mid-replay (divergence editing).
    """
    from flight_recorder.proxy import cassette
    from flight_recorder.replay.engine import build_tape_agent

    valid_run_id(request.run_id)
    records = cassette.load_cassette(request.run_id).get("records", [])
    agent = build_tape_agent(records) if records else None
    return replay_run(request.run_id, agent=agent, inject=request.inject)


@app.post("/bisect", dependencies=_AUTH)
def post_bisect(request: BisectRequest) -> BisectResult:
    """Bisect two runs and return the first diverging step."""
    return bisect_runs(valid_run_id(request.good_run_id), valid_run_id(request.bad_run_id))
