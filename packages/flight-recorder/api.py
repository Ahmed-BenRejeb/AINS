"""Flight Recorder HTTP API (UC2).

FastAPI service on port 8001 (exposed at ``flight.ahmedxsaad.me``). Lists recorded
runs and their traces from Cloudflare D1, and runs deterministic replay / bisect
over their cassettes.

Run locally::

    FLIGHT_MODE=replay uv run uvicorn api:app --port 8001
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from flight_recorder.config import RUN_MANIFESTS_TABLE
from flight_recorder.replay.bisect import BisectResult, bisect_runs
from flight_recorder.replay.engine import ReplayResult, replay_run
from flight_recorder.storage import d1_client
from pydantic import BaseModel, Field

app = FastAPI(title="Sentinel Flight Recorder", version="0.1.0")


class ReplayRequest(BaseModel):
    """Body for ``POST /replay``."""

    run_id: str = Field(description="UUID of the run to replay.")


class BisectRequest(BaseModel):
    """Body for ``POST /bisect``."""

    good_run_id: str = Field(description="UUID of the known-good run.")
    bad_run_id: str = Field(description="UUID of the known-bad run.")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/runs")
def list_runs() -> list[dict[str, Any]]:
    """List all recorded run manifests, newest first."""
    return d1_client.query(
        f"SELECT * FROM {RUN_MANIFESTS_TABLE} ORDER BY started_at DESC",
    )


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    """Return a run's manifest plus its ordered trace records.

    Args:
        run_id: UUID of the run.

    Returns:
        ``{"run_id", "manifest", "trace"}`` where ``trace`` is the ordered
        ``trace_records`` rows for the run.
    """
    manifest = d1_client.query(
        f"SELECT * FROM {RUN_MANIFESTS_TABLE} WHERE run_id = ?",
        [run_id],
    )
    trace = d1_client.query(
        "SELECT * FROM trace_records WHERE run_id = ? ORDER BY sequence ASC",
        [run_id],
    )
    return {"run_id": run_id, "manifest": manifest[0] if manifest else None, "trace": trace}


@app.post("/replay")
def post_replay(request: ReplayRequest) -> ReplayResult:
    """Replay a run from its cassette and return the divergence report."""
    return replay_run(request.run_id)


@app.post("/bisect")
def post_bisect(request: BisectRequest) -> BisectResult:
    """Bisect two runs and return the first diverging step."""
    return bisect_runs(request.good_run_id, request.bad_run_id)
