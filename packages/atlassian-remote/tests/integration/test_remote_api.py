"""FastAPI route tests — auth enforcement plus happy paths with mocked deps.

``api.py`` lives at the package root (run as ``uvicorn api:app``), so it is loaded
by path under a unique module name to avoid colliding with the other packages'
``api.py`` modules in a shared pytest session.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest
from atlassian_remote import analyzer, cf_ai_client, vector_search
from atlassian_remote.models import AnalyzeResult, DuplicateResult
from fastapi import FastAPI
from fastapi.testclient import TestClient
from trace_core import Attribution, DuplicateVerdict, RcaDraft, SearchResult

_API_PATH = Path(__file__).resolve().parents[2] / "api.py"
_AUTH = {"X-Sentinel-Secret": "remote-secret", "X-Account-Id": "acc-1"}


def _load_api() -> ModuleType:
    """Import the root api.py under a unique module name.

    The module is registered in ``sys.modules`` before execution so Pydantic can
    resolve the forward references in the response models (``list[SearchResult]``)
    against the module's globals.
    """
    spec = importlib.util.spec_from_file_location("atlassian_remote_api", _API_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _app() -> FastAPI:
    app: FastAPI = _load_api().app
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_app())


def _draft() -> RcaDraft:
    return RcaDraft(
        root_cause_hypothesis="pool exhausted",
        evidence=["INC-1"],
        severity_rationale="impact",
        proposed_severity="high",
        proposed_assignee_team="platform",
        duplicate_check=[],
        knowledge_gaps=["redis failover"],
        confidence_score=0.82,
    )


def _hit() -> SearchResult:
    return SearchResult(
        id="INC-1",
        text="db pool",
        score=0.9,
        attribution=Attribution(dims={}, terms={}, confidence_margin=0.1),
    )


def _verdict() -> DuplicateVerdict:
    return DuplicateVerdict(
        is_duplicate=True,
        duplicate_of="INC-1",
        confidence=0.91,
        rationale="same pool exhaustion",
        explanation="This looks like a duplicate of INC-1.",
        candidates=[],
    )


def test_health_is_open(client: TestClient) -> None:
    """/health needs no secret and reports ok."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_requires_secret(client: TestClient) -> None:
    """/analyze rejects a request with no X-Sentinel-Secret header."""
    response = client.post("/analyze", json={"incident_key": "AO-1", "requested_by": "acc"})

    assert response.status_code == 401


def test_search_rejects_wrong_secret(client: TestClient) -> None:
    """/search rejects a request with the wrong shared secret."""
    response = client.post(
        "/search",
        json={"query": "db", "index": "incidents"},
        headers={"X-Sentinel-Secret": "wrong"},
    )

    assert response.status_code == 401


def test_analyze_happy_path(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """/analyze returns a serialised AnalyzeResult with the integration envelope."""
    result = AnalyzeResult(
        run_id="run-abc",
        rca_draft=_draft(),
        similar=[_hit()],
        runbooks=[],
        flag_for_human=False,
        eval_verdict=None,
        replay_link="https://flight.ahmedxsaad.me/runs/run-abc",
    )

    async def fake_analyze(incident_key: str, requested_by: str) -> AnalyzeResult:
        return result

    monkeypatch.setattr(analyzer, "analyze_incident", fake_analyze)

    response = client.post(
        "/analyze", json={"incident_key": "AO-1", "requested_by": "acc"}, headers=_AUTH
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "run-abc"
    assert body["rca_draft"]["proposed_severity"] == "high"
    assert body["rca_draft"]["confidence_score"] == 0.82
    assert body["similar"][0]["id"] == "INC-1"
    assert body["flag_for_human"] is False
    assert body["replay_link"] == "https://flight.ahmedxsaad.me/runs/run-abc"


def test_duplicates_requires_secret(client: TestClient) -> None:
    """/duplicates rejects a request with no X-Sentinel-Secret header."""
    response = client.post("/duplicates", json={"incident_key": "AO-1", "requested_by": "acc"})

    assert response.status_code == 401


def test_duplicates_happy_path(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """/duplicates returns a serialised DuplicateResult containing the verdict."""
    result = DuplicateResult(verdict=_verdict(), similar=[_hit()], flag_for_human=False)

    async def fake_resolve(incident_key: str, requested_by: str) -> DuplicateResult:
        return result

    monkeypatch.setattr(analyzer, "resolve_incident_duplicate", fake_resolve)

    response = client.post(
        "/duplicates", json={"incident_key": "AO-1", "requested_by": "acc"}, headers=_AUTH
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"]["is_duplicate"] is True
    assert body["verdict"]["duplicate_of"] == "INC-1"
    assert body["similar"][0]["id"] == "INC-1"
    assert body["flag_for_human"] is False


def test_search_happy_path(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """/search returns hits with their attribution payload."""

    async def fake_search(query: str, index: str, k: int = 5) -> list[SearchResult]:
        return [_hit()]

    monkeypatch.setattr(vector_search, "search_similar", fake_search)

    response = client.post(
        "/search", json={"query": "db", "index": "incidents", "k": 3}, headers=_AUTH
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["id"] == "INC-1"
    assert "attribution" in results[0]


def test_embed_happy_path(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """/embed returns one vector per input text."""

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]

    monkeypatch.setattr(cf_ai_client, "cf_ai_embed", fake_embed)

    response = client.post("/embed", json={"texts": ["a", "b"]}, headers=_AUTH)

    assert response.status_code == 200
    assert response.json()["embeddings"] == [[0.1, 0.2], [0.1, 0.2]]


def test_search_maps_upstream_cf_429_to_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CF Workers AI 429 (quota exhausted) surfaces as a clean 503, not a 500.

    Regression for the live /search failure: the embeddings call returned a 429,
    which propagated as an unhandled 500. An upstream dependency being unavailable
    is a 503 (retry later), and the body carries a descriptive message.
    """

    async def upstream_429(query: str, index: str, k: int = 5) -> list[SearchResult]:
        request = httpx.Request(
            "POST", "https://api.cloudflare.com/client/v4/accounts/x/ai/run/@cf/baai/bge"
        )
        response = httpx.Response(
            429,
            request=request,
            json={"errors": [{"code": 4006, "message": "daily free allocation of neurons"}]},
        )
        raise httpx.HTTPStatusError("429", request=request, response=response)

    monkeypatch.setattr(vector_search, "search_similar", upstream_429)

    response = client.post("/search", json={"query": "db", "index": "incidents"}, headers=_AUTH)

    assert response.status_code == 503
    assert "retry later" in response.json()["detail"]
