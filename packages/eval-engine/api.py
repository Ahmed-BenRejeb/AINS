"""Eval Engine HTTP API (UC1).

FastAPI service on port 8000 (exposed at ``eval.ahmedxsaad.me``). Evaluates a
single run trial or a ``pass^k`` batch, returning :class:`trace_core.EvalVerdict`
objects with failure attribution and self-evaluation.

Run locally::

    uv run uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

from eval_engine.metrics.pass_at_k import consistency_rate, pass_at_k
from eval_engine.trace_loader import load_trace
from eval_engine.verdicts.reporter import evaluate_run
from fastapi import FastAPI
from pydantic import BaseModel, Field
from trace_core import PASS_AT_K_TRIALS, EvalVerdict, TraceRecord

app = FastAPI(title="Sentinel Eval Engine", version="0.1.0")


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


async def _resolve_records(request: EvaluateRequest) -> list[TraceRecord]:
    """Use submitted records, else load the trace from the flight recorder."""
    if request.records is not None:
        return request.records
    return await load_trace(request.run_id)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/evaluate")
async def evaluate(request: EvaluateRequest) -> EvalVerdict:
    """Evaluate one trial of a run and return its verdict."""
    records = await _resolve_records(request)
    return await evaluate_run(request.run_id, request.trial_number, records)


@app.post("/evaluate/batch")
async def evaluate_batch(request: BatchRequest) -> BatchResult:
    """Evaluate every run in a batch and aggregate the pass^k reliability metric."""
    verdicts: list[EvalVerdict] = []
    for trial_number, run_id in enumerate(request.run_ids):
        records = await load_trace(run_id)
        verdicts.append(await evaluate_run(run_id, trial_number, records))
    results: list[bool] = [v.verdict == "pass" for v in verdicts]
    return BatchResult(
        verdicts=verdicts,
        pass_hat_k=pass_at_k(results, request.k),
        consistency_rate=consistency_rate(results),
    )
