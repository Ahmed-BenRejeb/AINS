"""FastAPI route tests for the eval engine.

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
from eval_engine import cf_ai_client
from fastapi import FastAPI
from fastapi.testclient import TestClient
from trace_core import TraceRecord

_API_PATH = Path(__file__).resolve().parents[1] / "api.py"


def _load_api() -> ModuleType:
    """Import the root api.py under a unique module name."""
    spec = importlib.util.spec_from_file_location("eval_engine_api", _API_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_verdicts_401_without_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """With FORGE_REMOTE_SECRET set, /verdicts requires a matching X-Sentinel-Secret."""
    monkeypatch.setenv("FORGE_REMOTE_SECRET", "s3cret")
    client = TestClient(_load_api().app)
    assert client.get("/verdicts").status_code == 401
    assert client.get("/health").status_code == 200  # health stays open


def test_evaluate_rejects_non_uuid_run_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-uuid run_id is rejected with 400 before any work (injection guard)."""
    monkeypatch.delenv("FORGE_REMOTE_SECRET", raising=False)
    client = TestClient(_load_api().app)
    assert client.post("/evaluate", json={"run_id": "../x", "records": []}).status_code == 400


def test_evaluate_maps_upstream_cf_429_to_503(
    monkeypatch: pytest.MonkeyPatch, trace_pass: list[TraceRecord]
) -> None:
    """A CF Workers AI 429 (quota exhausted) surfaces as a clean 503, not a 500.

    Regression for the live ``make eval`` failure: the safety filter's CF call
    returned a 429, which propagated as an unhandled 500. An upstream dependency
    being unavailable is a 503 (retry later).
    """

    async def upstream_429(text: str) -> object:
        request = httpx.Request(
            "POST", "https://api.cloudflare.com/client/v4/accounts/x/ai/run/@cf/meta/llama-guard"
        )
        response = httpx.Response(
            429,
            request=request,
            json={"errors": [{"code": 4006, "message": "daily free allocation of neurons"}]},
        )
        raise httpx.HTTPStatusError("429", request=request, response=response)

    monkeypatch.setattr(cf_ai_client, "cf_ai_safety", upstream_429)

    app: FastAPI = _load_api().app
    client = TestClient(app)
    body = {
        "run_id": "00000000000000000000000000000abc",
        "records": [record.model_dump(mode="json") for record in trace_pass],
    }

    response = client.post("/evaluate", json=body)

    assert response.status_code == 503
    assert "retry later" in response.json()["detail"]
