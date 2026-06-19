"""Atlassian REST client tests — focus on exponential backoff and the AO rules."""

from __future__ import annotations

import json

import httpx
import pytest
from atlassian_remote import atlassian_client
from atlassian_remote.atlassian_client import AtlassianClient, adf, build_incident_fields
from atlassian_remote.config import BACKOFF_MAX_RETRIES
from pytest_httpx import HTTPXMock


@pytest.fixture(autouse=True)
def instant_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the backoff sleep to a no-op so retry tests run instantly."""

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(atlassian_client, "_backoff_sleep", _no_sleep)


async def test_get_issue_uses_basic_auth(httpx_mock: HTTPXMock) -> None:
    """get_issue() hits the v3 issue endpoint with HTTP Basic auth."""
    httpx_mock.add_response(json={"key": "AO-1", "fields": {"summary": "S"}})

    issue = await AtlassianClient().get_issue("AO-1")

    assert issue["key"] == "AO-1"
    request = httpx_mock.get_requests()[0]
    assert request.url.path == "/rest/api/3/issue/AO-1"
    assert request.headers["Authorization"].startswith("Basic ")


async def test_429_then_success_retries_with_backoff(httpx_mock: HTTPXMock) -> None:
    """A 429 is retried; the second (200) response is returned."""
    httpx_mock.add_response(status_code=429, headers={"Retry-After": "0"})
    httpx_mock.add_response(json={"key": "AO-2", "fields": {}})

    issue = await AtlassianClient().get_issue("AO-2")

    assert issue["key"] == "AO-2"
    assert len(httpx_mock.get_requests()) == 2  # original + one retry


async def test_429_exhausts_retries_then_raises(httpx_mock: HTTPXMock) -> None:
    """Persistent 429s raise after the original call plus BACKOFF_MAX_RETRIES."""
    total = BACKOFF_MAX_RETRIES + 1
    for _ in range(total):
        httpx_mock.add_response(status_code=429)

    with pytest.raises(httpx.HTTPStatusError):
        await AtlassianClient().get_issue("AO-3")

    assert len(httpx_mock.get_requests()) == total


def test_build_incident_fields_obeys_ao_rules() -> None:
    """AO incidents use issue-type id 10013 and never carry priority/labels."""
    fields = build_incident_fields("Outage", "DB pool exhausted")

    assert fields["issuetype"] == {"id": "10013"}
    assert "priority" not in fields
    assert "labels" not in fields
    assert fields["project"]["key"] == "AO"
    assert fields["description"]["type"] == "doc"  # plain text wrapped as ADF


async def test_create_issue_posts_fields_verbatim(httpx_mock: HTTPXMock) -> None:
    """create_issue() wraps fields under 'fields' and returns the created key."""
    httpx_mock.add_response(json={"key": "AO-9", "id": "10001"})

    out = await AtlassianClient().create_issue(build_incident_fields("S", "d"))

    assert out["key"] == "AO-9"
    request = httpx_mock.get_requests()[0]
    assert request.url.path == "/rest/api/3/issue"
    body = json.loads(request.content)
    assert body["fields"]["issuetype"]["id"] == "10013"
    assert "priority" not in body["fields"]


async def test_add_comment_targets_comment_endpoint(httpx_mock: HTTPXMock) -> None:
    """add_comment() posts an ADF body to the issue's comment endpoint."""
    httpx_mock.add_response(json={"id": "1"})

    await AtlassianClient().add_comment("AO-1", adf("looking into it"))

    request = httpx_mock.get_requests()[0]
    assert request.url.path == "/rest/api/3/issue/AO-1/comment"
    assert json.loads(request.content)["body"]["type"] == "doc"


async def test_create_confluence_page_uses_storage_format(httpx_mock: HTTPXMock) -> None:
    """create_confluence_page() posts storage-format content to a space by key."""
    httpx_mock.add_response(json={"id": "page-1"})

    await AtlassianClient().create_confluence_page("SENT", "PIR", "<p>postmortem</p>")

    request = httpx_mock.get_requests()[0]
    assert request.url.path == "/wiki/rest/api/content"
    body = json.loads(request.content)
    assert body["space"]["key"] == "SENT"
    assert body["body"]["storage"]["representation"] == "storage"


async def test_search_jql_posts_query(httpx_mock: HTTPXMock) -> None:
    """search_jql() posts the JQL to the bulk search endpoint."""
    httpx_mock.add_response(json={"issues": []})

    await AtlassianClient().search_jql("project = AO ORDER BY created DESC")

    request = httpx_mock.get_requests()[0]
    assert request.url.path == "/rest/api/3/search/jql"
    assert json.loads(request.content)["jql"].startswith("project = AO")
