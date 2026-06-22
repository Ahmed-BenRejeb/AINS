"""End-to-end Phase 4 loop: POST /analyze records, evaluates, and returns it all.

Every boundary is mocked — Atlassian (``get_issue``), xqdrant (``search_similar``),
CF Workers AI (``httpx_mock``), MinIO + D1 (the flight recorder's storage modules),
and the eval engine (``httpx_mock``) — so the real analyzer → recording transport →
cassette → manifest → eval-engine wiring runs without touching the network.

Asserts the integration contract: the RCA-generation LLM call is taped into a MinIO
cassette, the eval engine is called for the run, and the response carries the
``run_id``, the eval verdict, and the replay deep link.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
from atlassian_remote import vector_search
from atlassian_remote.atlassian_client import AtlassianClient
from atlassian_remote.config import cf_ai_url, eval_engine_url, model_embed, model_main
from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from flight_recorder.storage import d1_client, minio_client
from pytest_httpx import HTTPXMock
from trace_core import (
    Attribution,
    EvalVerdict,
    RcaDraft,
    SearchResult,
    SelfEvaluation,
)

_API_PATH = Path(__file__).resolve().parents[2] / "api.py"
_AUTH = {"X-Sentinel-Secret": "remote-secret", "X-Account-Id": "acc-1"}

_ISSUE: dict[str, Any] = {
    "key": "AO-7",
    "fields": {
        "summary": "Checkout latency spike",
        "description": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "p99 latency tripled after deploy"}],
                }
            ],
        },
    },
}


def _load_app() -> FastAPI:
    """Import the root api.py under a unique module name and return its app."""
    spec = importlib.util.spec_from_file_location("atlassian_remote_api_fullloop", _API_PATH)
    assert spec is not None and spec.loader is not None
    module: ModuleType = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    app: FastAPI = module.app
    return app


def _rca_draft() -> RcaDraft:
    return RcaDraft(
        root_cause_hypothesis="connection pool exhausted after deploy",
        evidence=["INC-1"],
        severity_rationale="customer-facing latency",
        proposed_severity="high",
        proposed_assignee_team="platform",
        duplicate_check=[],
        knowledge_gaps=["redis failover"],
        confidence_score=0.4,  # below threshold → flag_for_human True
    )


def _eval_verdict(run_id: str) -> EvalVerdict:
    return EvalVerdict(
        run_id=run_id,
        trial_number=0,
        verdict="fail",
        dimensions={},
        self_evaluation=SelfEvaluation(
            judge_confidence=0.55, self_critique="thin evidence", flag_for_human=True
        ),
        replay_link=f"https://flight.ahmedxsaad.me/runs/{run_id}",
        recommended_action="Open the replay and bisect the retrieval step.",
    )


def _hit() -> SearchResult:
    return SearchResult(
        id="INC-1",
        text="db pool",
        score=0.9,
        attribution=Attribution(dims={}, terms={}, confidence_margin=0.1),
    )


@pytest.fixture
def fake_blobs(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    """Replace the flight recorder's MinIO with an in-memory ``key -> bytes`` store."""
    store: dict[str, bytes] = {}

    def _store(key: str, data: bytes) -> None:
        store[key] = data

    def _load(key: str) -> bytes:
        if key not in store:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return store[key]

    monkeypatch.setattr(minio_client, "store_blob", _store)
    monkeypatch.setattr(minio_client, "load_blob", _load)
    return store


@pytest.fixture
def captured_d1(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Capture every flight-recorder D1 insert (audit rows + the run manifest)."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def _insert(table: str, record: dict[str, Any]) -> None:
        calls.append((table, record))

    monkeypatch.setattr(d1_client, "insert", _insert)
    return calls


async def test_full_loop_records_evaluates_and_returns(
    monkeypatch: pytest.MonkeyPatch,
    httpx_mock: HTTPXMock,
    fake_blobs: dict[str, bytes],
    captured_d1: list[tuple[str, dict[str, Any]]],
) -> None:
    """POST /analyze: cassette stored in MinIO, eval engine called, verdict + link returned."""

    # ── Atlassian + xqdrant boundaries (no network) ──
    async def fake_get_issue(_self: AtlassianClient, _key: str) -> dict[str, Any]:
        return _ISSUE

    async def fake_search(
        _query: str, collection: str, k: int = 5, embedding: list[float] | None = None
    ) -> list[SearchResult]:
        return [_hit()] if collection == "incidents" else []

    monkeypatch.setattr(AtlassianClient, "get_issue", fake_get_issue)
    monkeypatch.setattr(vector_search, "search_similar", fake_search)

    # ── CF Workers AI: the embed + RCA calls flow through the recording transport ──
    httpx_mock.add_response(
        url=f"{cf_ai_url()}/{model_embed()}",
        json={"result": {"data": [[0.1, 0.2, 0.3]]}, "success": True},
    )
    httpx_mock.add_response(
        url=f"{cf_ai_url()}/{model_main()}",
        json={"result": {"response": _rca_draft().model_dump_json()}, "success": True},
    )
    # ── eval engine: called internally over localhost with the run_id ──
    eval_run_id_box: dict[str, str] = {}

    def eval_callback(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        eval_run_id_box["run_id"] = payload["run_id"]
        return httpx.Response(200, json=_eval_verdict(payload["run_id"]).model_dump(mode="json"))

    httpx_mock.add_callback(eval_callback, url=f"{eval_engine_url()}/evaluate")

    with TestClient(_load_app()) as client:
        response = client.post(
            "/analyze",
            json={"incident_key": "AO-7", "requested_by": "acc-1"},
            headers=_AUTH,
        )

    assert response.status_code == 200
    body = response.json()
    run_id = body["run_id"]

    # The eval engine was called for exactly this run.
    assert eval_run_id_box["run_id"] == run_id

    # The eval verdict (and any auto-filed issue side effect) came back on the envelope.
    assert body["eval_verdict"] is not None
    assert body["eval_verdict"]["verdict"] == "fail"

    # The replay deep link points at this run on the dashboard (human page, not JSON API).
    assert body["replay_link"] == f"https://dashboard.ahmedxsaad.me/replay/{run_id}"

    # The trace was taped into a MinIO cassette as the full workflow:
    # embed (llm_call) -> search incidents (tool_call) -> search runbooks (tool_call)
    # -> RCA (llm_call). Only the 2 HTTP calls (embed + chat) are replayable steps.
    assert f"{run_id}.json" in fake_blobs
    cassette = json.loads(fake_blobs[f"{run_id}.json"])
    kinds = [record["kind"] for record in cassette["records"]]
    assert kinds == ["llm_call", "tool_call", "tool_call", "llm_call"]
    assert len(cassette["steps"]) == 2  # embed + chat (tool_calls add no replay step)
    tool_calls = [r for r in cassette["records"] if r["kind"] == "tool_call"]
    assert all(r["metadata"]["tool_name"] == "xqdrant.query_points" for r in tool_calls)

    # The run manifest + audit row were written to D1.
    tables = [table for table, _ in captured_d1]
    assert "run_manifests" in tables
    assert "trace_records" in tables
    manifest_row = next(record for table, record in captured_d1 if table == "run_manifests")
    assert manifest_row["run_id"] == run_id
    assert manifest_row["task_id"] == "AO-7"
