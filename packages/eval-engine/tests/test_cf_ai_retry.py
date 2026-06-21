"""CF Workers AI client retry tests — backoff on 429 / 5xx, sleep mocked.

The real ``asyncio.sleep`` is patched to a no-op recorder so the 30s / 5s backoffs
never actually block the test run (root CLAUDE.md §10: space real test calls >3s
apart; here every HTTP call is mocked via pytest-httpx).
"""

from __future__ import annotations

import httpx
import pytest
from eval_engine import cf_ai_client
from pytest_httpx import HTTPXMock


def _patch_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record retry backoff delays and skip the real ``asyncio.sleep`` wait."""
    sleeps: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("asyncio.sleep", _fake_sleep)
    return sleeps


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
    httpx_mock.add_response(status_code=500)
    httpx_mock.add_response(json={"result": {"data": [[0.1]]}})

    out = await cf_ai_client.cf_ai_embed(["x"])

    assert out == [[0.1]]
    assert sleeps == [5.0]


async def test_post_raises_after_5xx_budget_exhausted(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After the initial 5xx + 2 retries all 503, the error propagates."""
    sleeps = _patch_sleep(monkeypatch)
    for _ in range(3):
        httpx_mock.add_response(status_code=503)

    with pytest.raises(httpx.HTTPStatusError):
        await cf_ai_client.cf_ai_safety("some text to classify")

    assert sleeps == [5.0, 5.0]


async def test_post_does_not_retry_on_4xx(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-retryable 4xx (e.g. 401) raises immediately with no backoff."""
    sleeps = _patch_sleep(monkeypatch)
    httpx_mock.add_response(status_code=401)

    with pytest.raises(httpx.HTTPStatusError):
        await cf_ai_client.cf_ai_chat([{"role": "user", "content": "x"}])

    assert sleeps == []
    assert len(httpx_mock.get_requests()) == 1
