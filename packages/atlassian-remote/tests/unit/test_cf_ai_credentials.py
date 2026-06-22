"""Workers AI credentials prefer CF_AI_* overrides, falling back to CLOUDFLARE_*."""

from __future__ import annotations

import pytest
from atlassian_remote import config


def test_cf_account_prefers_ai_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """CF_AI_ACCOUNT_ID / CF_AI_API_TOKEN win when set (teammate-account route)."""
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "primary-acct")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "primary-tok")
    monkeypatch.setenv("CF_AI_ACCOUNT_ID", "teammate-acct")
    monkeypatch.setenv("CF_AI_API_TOKEN", "teammate-tok")
    assert config.cf_account_id() == "teammate-acct"
    assert config.cf_api_token() == "teammate-tok"
    assert "teammate-acct" in config.cf_ai_url()


def test_cf_account_falls_back_to_cloudflare(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no CF_AI_* override, the primary CLOUDFLARE_* creds are used."""
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "primary-acct")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "primary-tok")
    monkeypatch.delenv("CF_AI_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CF_AI_API_TOKEN", raising=False)
    assert config.cf_account_id() == "primary-acct"
    assert config.cf_api_token() == "primary-tok"
