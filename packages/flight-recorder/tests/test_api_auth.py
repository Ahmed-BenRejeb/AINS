"""The flight-recorder API enforces the shared secret when it is configured."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

_API_PATH = Path(__file__).resolve().parents[1] / "api.py"


def _load_api() -> ModuleType:
    """Import the root api.py under a unique name (avoid cross-package collision)."""
    spec = importlib.util.spec_from_file_location("flight_recorder_api", _API_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _client() -> TestClient:
    return TestClient(_load_api().app)


def test_health_is_open() -> None:
    """/health is never gated (tunnel liveness)."""
    assert _client().get("/health").status_code == 200


def test_runs_401_without_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """With FORGE_REMOTE_SECRET set, /runs requires a matching X-Sentinel-Secret."""
    monkeypatch.setenv("FORGE_REMOTE_SECRET", "s3cret")
    assert _client().get("/runs").status_code == 401
    assert _client().get("/runs", headers={"X-Sentinel-Secret": "wrong"}).status_code == 401


def test_replay_rejects_non_uuid_run_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-uuid run_id is rejected with 400 before any lookup (path-traversal guard)."""
    monkeypatch.delenv("FORGE_REMOTE_SECRET", raising=False)
    assert _client().post("/replay", json={"run_id": "../etc/passwd"}).status_code == 400
