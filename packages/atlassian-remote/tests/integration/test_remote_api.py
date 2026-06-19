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

import pytest
from atlassian_remote import analyzer, cf_ai_client, vector_search
from atlassian_remote.models import AnalyzeResult
from fastapi import FastAPI
from fastapi.testclient import TestClient
from trace_core import Attribution, RcaDraft, SearchResult

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
    """/analyze returns a serialised AnalyzeResult containing a valid RcaDraft."""
    result = AnalyzeResult(rca_draft=_draft(), similar=[_hit()], runbooks=[], flag_for_human=False)

    async def fake_analyze(incident_key: str, requested_by: str) -> AnalyzeResult:
        return result

    monkeypatch.setattr(analyzer, "analyze_incident", fake_analyze)

    response = client.post(
        "/analyze", json={"incident_key": "AO-1", "requested_by": "acc"}, headers=_AUTH
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rca_draft"]["proposed_severity"] == "high"
    assert body["rca_draft"]["confidence_score"] == 0.82
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
