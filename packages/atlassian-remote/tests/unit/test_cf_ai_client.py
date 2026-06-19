"""CF Workers AI client tests — every HTTP call mocked via pytest-httpx."""

from __future__ import annotations

from atlassian_remote import cf_ai_client
from pytest_httpx import HTTPXMock


async def test_cf_ai_chat_returns_response_text(httpx_mock: HTTPXMock) -> None:
    """chat() unwraps result.response and sends the bearer token + main model."""
    httpx_mock.add_response(json={"result": {"response": "root cause: db pool"}})

    out = await cf_ai_client.cf_ai_chat([{"role": "user", "content": "analyse"}])

    assert out == "root cause: db pool"
    request = httpx_mock.get_requests()[0]
    assert request.headers["Authorization"] == "Bearer token-test"
    assert "@cf/meta/llama-3.3-70b-instruct-fp8-fast" in str(request.url)


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
