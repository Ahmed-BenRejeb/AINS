"""Eval Engine HTTP API (UC1).

FastAPI service on port 8000 (exposed at ``eval.ahmedxsaad.me``). Evaluates a
single run trial or a ``pass^k`` batch, returning :class:`trace_core.EvalVerdict`
objects with failure attribution and self-evaluation.

Run locally::

    uv run uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

import hmac
import logging
import os
import re

import httpx
from eval_engine.drift.detector import detect_drift
from eval_engine.langfuse_client import init_langfuse
from eval_engine.metrics.pass_at_k import consistency_rate, pass_at_k
from eval_engine.models import GoldCase
from eval_engine.trace_loader import load_trace
from eval_engine.verdict_store import get_verdict, list_verdicts
from eval_engine.verdicts.reporter import evaluate_gold_set, evaluate_run
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from trace_core import (
    PASS_AT_K_TRIALS,
    DriftReport,
    EvaluatorQuality,
    EvalVerdict,
    TraceRecord,
)

logger = logging.getLogger("eval_engine.api")

app = FastAPI(title="Sentinel Eval Engine", version="0.1.0")

# Initialise Langfuse observability at startup (no-op if LANGFUSE_* is unset).
init_langfuse()

# Expose Prometheus metrics at GET /metrics (request count/latency/in-progress per
# endpoint) for the in-cluster kube-prometheus-stack to scrape. Left unauthenticated
# like /health so the ServiceMonitor can reach it; the service is internal-only.
Instrumentator().instrument(app).expose(app, include_in_schema=False)


@app.exception_handler(httpx.HTTPStatusError)
async def cf_upstream_error_handler(request: Request, exc: httpx.HTTPStatusError) -> JSONResponse:
    """Map an upstream CF Workers AI error to a clean 503 instead of a bare 500.

    The graders (safety filter, LLM judge) call CF Workers AI. When that returns a
    429 (rate limit / daily neuron allocation exhausted) or a 5xx, it is an
    *upstream* dependency failure, not a bug here — so the correct status is 503
    Service Unavailable (retry later), with a descriptive message, not a 500.
    """
    status = exc.response.status_code
    if status == 429:
        detail = "CF Workers AI rate limit or daily neuron allocation exhausted; retry later"
    else:
        detail = f"upstream CF Workers AI error (status {status}); retry later"
    logger.warning("upstream CF Workers AI %s on %s: %s", status, request.url.path, detail)
    return JSONResponse(status_code=503, content={"detail": detail})


def require_secret(x_sentinel_secret: str | None = Header(default=None)) -> None:
    """Shared-secret gate for the public API (constant-time compare).

    Enforced only when ``FORGE_REMOTE_SECRET`` is configured (it is on the VM); in
    local/test environments without the secret the check is a no-op so the test
    suite and dev servers stay open. ``/health`` is intentionally left unprotected
    for tunnel liveness probes.
    """
    expected = os.environ.get("FORGE_REMOTE_SECRET")
    if not expected:
        return
    if not x_sentinel_secret or not hmac.compare_digest(x_sentinel_secret, expected):
        raise HTTPException(status_code=401, detail="missing or invalid X-Sentinel-Secret")


_RUN_ID_RE = re.compile(r"^[0-9a-fA-F]{32}$|^[0-9a-fA-F-]{36}$")


def valid_run_id(run_id: str) -> str:
    """Validate ``run_id`` is a uuid4 hex (or dashed uuid) before use as a key/path.

    Run ids become MinIO object keys (``{run_id}.json``) and D1 query params, so
    rejecting anything that is not a uuid removes a path-traversal / injection sink.
    """
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="run_id must be a uuid")
    return run_id


_AUTH = [Depends(require_secret)]


class EvaluateRequest(BaseModel):
    """Body for ``POST /evaluate``."""

    run_id: str = Field(description="UUID of the run to evaluate.")
    trial_number: int = Field(default=0, ge=0, description="0-based trial index.")
    records: list[TraceRecord] | None = Field(
        default=None,
        description="Optional trace to evaluate directly; loaded from the recorder if omitted.",
    )


class BatchRequest(BaseModel):
    """Body for ``POST /evaluate/batch``."""

    run_ids: list[str] = Field(description="Run UUIDs forming one pass^k batch.")
    k: int = Field(default=PASS_AT_K_TRIALS, ge=1, description="Trials that must all pass.")


class BatchResult(BaseModel):
    """Response for ``POST /evaluate/batch``: verdicts plus the pass^k metric."""

    verdicts: list[EvalVerdict] = Field(description="One verdict per run, in input order.")
    pass_hat_k: float = Field(description="1.0 only if all k trials passed, else 0.0.")
    consistency_rate: float = Field(description="Average passing rate across trials.")


class DriftRequest(BaseModel):
    """Body for ``POST /drift``: a baseline window vs a current window of verdicts."""

    baseline: list[EvalVerdict] = Field(description="Verdicts from the reference window.")
    current: list[EvalVerdict] = Field(description="Verdicts from the window under test.")
    baseline_outputs: list[str] | None = Field(
        default=None,
        description="Optional agent output texts for the baseline window (enables semantic drift).",
    )
    current_outputs: list[str] | None = Field(
        default=None,
        description="Optional agent output texts for the current window (enables semantic drift).",
    )


class EvaluatorQualityRequest(BaseModel):
    """Body for ``POST /evaluator-quality``: a human-labelled gold set."""

    cases: list[GoldCase] = Field(description="Gold-labelled runs (records + expected verdict).")


async def _resolve_records(request: EvaluateRequest) -> list[TraceRecord]:
    """Use submitted records, else load the trace from the flight recorder."""
    if request.records is not None:
        return request.records
    return await load_trace(request.run_id)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/verdicts", dependencies=_AUTH)
def get_verdicts(limit: int = 50) -> list[EvalVerdict]:
    """List the most recent persisted verdicts (newest first) from D1.

    Powers the dashboard overview + verdict list. Returns ``[]`` when D1 is
    unconfigured or empty, so the UI degrades cleanly rather than erroring.
    """
    return list_verdicts(min(max(limit, 1), 500))


@app.get("/verdicts/{run_id}", dependencies=_AUTH)
def get_verdict_by_run(run_id: str) -> EvalVerdict:
    """Return the most recent persisted verdict for ``run_id`` (404 if none)."""
    verdict = get_verdict(valid_run_id(run_id))
    if verdict is None:
        raise HTTPException(status_code=404, detail=f"no verdict persisted for run {run_id}")
    return verdict


@app.post("/evaluate", dependencies=_AUTH)
async def evaluate(request: EvaluateRequest) -> EvalVerdict:
    """Evaluate one trial of a run and return its verdict."""
    valid_run_id(request.run_id)
    records = await _resolve_records(request)
    return await evaluate_run(request.run_id, request.trial_number, records)


@app.post("/evaluate/batch", dependencies=_AUTH)
async def evaluate_batch(request: BatchRequest) -> BatchResult:
    """Evaluate every run in a batch and aggregate the pass^k reliability metric."""
    if len(request.run_ids) > 64:
        raise HTTPException(status_code=400, detail="batch too large (max 64 run_ids)")
    verdicts: list[EvalVerdict] = []
    for trial_number, run_id in enumerate(request.run_ids):
        records = await load_trace(valid_run_id(run_id))
        verdicts.append(await evaluate_run(run_id, trial_number, records))
    results: list[bool] = [v.verdict == "pass" for v in verdicts]
    return BatchResult(
        verdicts=verdicts,
        pass_hat_k=pass_at_k(results, request.k),
        consistency_rate=consistency_rate(results),
    )


@app.post("/drift", dependencies=_AUTH)
async def drift(request: DriftRequest) -> DriftReport:
    """Detect behavioural drift between a baseline and a current window of runs."""
    return await detect_drift(
        request.baseline,
        request.current,
        baseline_outputs=request.baseline_outputs,
        current_outputs=request.current_outputs,
    )


@app.post("/evaluator-quality", dependencies=_AUTH)
async def evaluator_quality(request: EvaluatorQualityRequest) -> EvaluatorQuality:
    """Score the evaluator against a human-labelled gold set (judge-vs-human κ)."""
    return await evaluate_gold_set(request.cases)


@app.get("/evaluator-quality/demo", dependencies=_AUTH)
async def evaluator_quality_demo() -> EvaluatorQuality:
    """Run the evaluator over the built-in demo gold set and report Cohen's κ.

    Powers the dashboard "Evaluator quality" screen: a small, self-contained gold
    set (2 expected-pass + 2 expected-fail synthetic runs) scored judge-vs-human, so
    the metric is demonstrable without a stored ground-truth label set.
    """
    from eval_engine.gold_demo import demo_gold_set

    return await evaluate_gold_set(demo_gold_set())
