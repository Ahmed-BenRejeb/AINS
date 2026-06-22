"""Shared fixtures for eval-engine tests.

No test makes a real network call: the CF Workers AI client functions are
monkeypatched in the tests that need them, and Atlassian credentials are left
unset so issue filing no-ops. A helper loads the JSON trace fixtures into
``TraceRecord`` objects.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from eval_engine import langfuse_client
from trace_core import TraceRecord

_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def disable_langfuse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable Langfuse in tests so instrumentation no-ops (no client, no network)."""
    monkeypatch.setattr(langfuse_client, "get_langfuse", lambda: None)


def load_fixture(name: str) -> list[TraceRecord]:
    """Load a trace fixture (a JSON array of steps) into TraceRecord objects."""
    data = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    return [TraceRecord.model_validate(step) for step in data]


@pytest.fixture
def trace_pass() -> list[TraceRecord]:
    """A run that passes every grader."""
    return load_fixture("trace_pass.json")


@pytest.fixture
def trace_fail_step2() -> list[TraceRecord]:
    """A run that fails at step 2 (retrieval timeout)."""
    return load_fixture("trace_fail_step2.json")


@pytest.fixture(autouse=True)
def cf_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set dummy CF credentials so config getters never KeyError if reached."""
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct-test")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token-test")
    # Atlassian intentionally left unconfigured → create_eval_issue() no-ops.
    for key in ("ATLASSIAN_SITE", "ATLASSIAN_EMAIL", "ATLASSIAN_API_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    # D1 intentionally left unconfigured → persist_verdict() no-ops (no network).
    monkeypatch.delenv("CF_D1_DATABASE_ID", raising=False)
