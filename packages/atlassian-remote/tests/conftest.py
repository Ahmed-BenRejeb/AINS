"""Shared fixtures for atlassian-remote tests.

No test makes a real network call: CF Workers AI and xqdrant clients are
monkeypatched in the tests that need them, and every Atlassian / Jira HTTP call is
intercepted by ``pytest-httpx``. The autouse fixture supplies dummy credentials so
the ``config`` getters never ``KeyError`` when a code path reaches them.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def remote_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set dummy env so config getters resolve without real infrastructure."""
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct-test")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token-test")
    monkeypatch.setenv("ATLASSIAN_SITE", "https://test.atlassian.net")
    monkeypatch.setenv("ATLASSIAN_EMAIL", "tester@example.com")
    monkeypatch.setenv("ATLASSIAN_API_TOKEN", "atl-token")
    monkeypatch.setenv("FORGE_REMOTE_SECRET", "remote-secret")
    monkeypatch.setenv("XQDRANT_URL", "http://localhost:6333")
    monkeypatch.setenv("XQDRANT_INCIDENTS_COLLECTION", "incidents")
    monkeypatch.setenv("XQDRANT_RUNBOOKS_COLLECTION", "runbooks")
