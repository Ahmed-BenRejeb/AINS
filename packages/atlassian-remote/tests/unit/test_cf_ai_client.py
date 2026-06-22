"""CF Workers AI client tests — every HTTP call mocked via pytest-httpx."""

from __future__ import annotations

import json

import httpx
import pytest
from atlassian_remote import cf_ai_client
from pytest_httpx import HTTPXMock


def _patch_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record retry backoff delays and skip the real ``asyncio.sleep`` wait."""
    sleeps: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("asyncio.sleep", _fake_sleep)
    return sleeps


async def test_cf_ai_chat_returns_response_text(httpx_mock: HTTPXMock) -> None:
    """chat() unwraps result.response and sends the bearer token + main model."""
    httpx_mock.add_response(json={"result": {"response": "root cause: db pool"}})

    out = await cf_ai_client.cf_ai_chat([{"role": "user", "content": "analyse"}])

    assert out == "root cause: db pool"
    request = httpx_mock.get_requests()[0]
    assert request.headers["Authorization"] == "Bearer token-test"
    assert "@cf/meta/llama-3.1-8b-instruct-fp8-fast" in str(request.url)


async def test_cf_ai_embed_returns_vectors(httpx_mock: HTTPXMock) -> None:
    """embed() unwraps result.data and targets the BGE embedding model."""
    httpx_mock.add_response(json={"result": {"data": [[0.1, 0.2], [0.3, 0.4]]}})

    out = await cf_ai_client.cf_ai_embed(["a", "b"])

    assert out == [[0.1, 0.2], [0.3, 0.4]]
    assert "bge-base-en-v1.5" in str(httpx_mock.get_requests()[0].url)


async def test_cf_ai_chat_defaults_to_empty_string(httpx_mock: HTTPXMock) -> None:
    """A response envelope without a 'response' key yields an empty string."""
    httpx_mock.add_response(json={"result": {}})

    assert await cf_ai_client.cf_ai_chat([{"role": "user", "content": "x"}]) == ""


async def test_cf_ai_chat_serializes_json_mode_dict_response(httpx_mock: HTTPXMock) -> None:
    """CF auto-parses JSON output: a dict `response` is re-serialized to a JSON string.

    Reproduces the live Llama 3.3 70B behaviour that broke RCA generation — the
    model's JSON object comes back as a dict, not a string.
    """
    httpx_mock.add_response(
        json={"result": {"response": {"root_cause_hypothesis": "x", "confidence_score": 0.5}}}
    )

    out = await cf_ai_client.cf_ai_chat([{"role": "user", "content": "analyse"}])

    assert isinstance(out, str)
    assert json.loads(out) == {"root_cause_hypothesis": "x", "confidence_score": 0.5}


async def test_post_retries_on_429_then_succeeds(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 429 backs off 30s (mocked) and retries, then returns the next 200."""
    sleeps = _patch_sleep(monkeypatch)
    httpx_mock.add_response(status_code=429)
    httpx_mock.add_response(json={"result": {"response": "ok"}})

    out = await cf_ai_client.cf_ai_chat([{"role": "user", "content": "x"}])

    assert out == "ok"
    assert sleeps == [30.0]
    assert len(httpx_mock.get_requests()) == 2


async def test_post_retries_on_5xx_then_succeeds(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A transient 5xx backs off 5s (mocked) and retries, then succeeds."""
    sleeps = _patch_sleep(monkeypatch)
    httpx_mock.add_response(status_code=503)
    httpx_mock.add_response(json={"result": {"data": [[0.1, 0.2]]}})

    out = await cf_ai_client.cf_ai_embed(["x"])

    assert out == [[0.1, 0.2]]
    assert sleeps == [5.0]


async def test_post_raises_after_429_budget_exhausted(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After the initial 429 + 3 retries all 429, the error propagates."""
    sleeps = _patch_sleep(monkeypatch)
    for _ in range(4):
        httpx_mock.add_response(status_code=429)

    with pytest.raises(httpx.HTTPStatusError):
        await cf_ai_client.cf_ai_chat([{"role": "user", "content": "x"}])

    assert sleeps == [30.0, 30.0, 30.0]


async def test_post_fails_fast_on_daily_quota_429(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 429 carrying CF code 4006 (daily neurons spent) fails fast — no retry/backoff.

    Reproduces the live cause of the /search 500: the embeddings endpoint returns a
    non-transient 429. Retrying it 3×30s pointlessly burns 90s and still fails (and
    blows the Forge 25s timeout), so the quota error must raise immediately.
    """
    sleeps = _patch_sleep(monkeypatch)
    httpx_mock.add_response(
        status_code=429,
        json={
            "success": False,
            "errors": [
                {
                    "code": 4006,
                    "message": (
                        "AiError: you have used up your daily free allocation of "
                        "10,000 neurons, please upgrade to Cloudflare's Workers Paid plan"
                    ),
                }
            ],
        },
    )

    with pytest.raises(httpx.HTTPStatusError):
        await cf_ai_client.cf_ai_embed(["database connection pool exhausted"])

    assert sleeps == []  # no backoff
    assert len(httpx_mock.get_requests()) == 1  # no retry — failed fast
