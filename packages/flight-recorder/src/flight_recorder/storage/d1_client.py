"""Thin wrapper around the Cloudflare D1 REST API.

D1 is the trace-metadata store: the hash-chained audit records (``trace_records``)
and the per-run summaries (``run_manifests``) live here. Queries go through the
HTTP ``query`` endpoint:

    POST https://api.cloudflare.com/client/v4/accounts/{id}/d1/database/{db}/query

Tests monkeypatch the module-level :func:`insert` / :func:`query` functions, so no
live D1 (or network) is touched.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Any

import httpx

_D1_TIMEOUT_SECONDS = 30.0
# SQL identifiers (table/column names) are interpolated into the statement, so they
# must match a strict allowlist — values are always parameterised with `?`.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _check_identifier(name: str) -> str:
    """Reject any table/column name that is not a plain SQL identifier."""
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"unsafe SQL identifier: {name!r}")
    return name


class D1Client:
    """Minimal Cloudflare D1 HTTP client (insert + parameterised query)."""

    def __init__(self, account_id: str, api_token: str, database_id: str) -> None:
        """Create a client bound to one D1 database.

        Args:
            account_id: Cloudflare account id.
            api_token: Cloudflare API token (Bearer auth).
            database_id: Target D1 database id.
        """
        self._account_id = account_id
        self._api_token = api_token
        self._database_id = database_id

    @property
    def _query_url(self) -> str:
        return (
            f"https://api.cloudflare.com/client/v4/accounts/{self._account_id}"
            f"/d1/database/{self._database_id}/query"
        )

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        """Run a SQL statement and return the result rows.

        Args:
            sql: SQL with ``?`` placeholders.
            params: Positional bind values for the placeholders.

        Returns:
            The first result set's rows as a list of column dicts.
        """
        with httpx.Client(timeout=_D1_TIMEOUT_SECONDS) as client:
            response = client.post(
                self._query_url,
                headers={"Authorization": f"Bearer {self._api_token}"},
                json={"sql": sql, "params": params or []},
            )
            response.raise_for_status()
            body = response.json()
        results = body.get("result", [])
        if not results:
            return []
        rows: list[dict[str, Any]] = results[0].get("results", [])
        return rows

    def insert(self, table: str, record: dict[str, Any]) -> None:
        """Insert one row into ``table`` from a column→value mapping.

        Args:
            table: Target table name.
            record: Column→value mapping; keys become the column list.
        """
        columns = [_check_identifier(name) for name in record]
        placeholders = ", ".join("?" for _ in columns)
        column_list = ", ".join(columns)
        sql = f"INSERT INTO {_check_identifier(table)} ({column_list}) VALUES ({placeholders})"
        self.query(sql, [record[column] for column in columns])


@lru_cache(maxsize=1)
def _default_client() -> D1Client:
    """Build the default client from environment variables (cached)."""
    return D1Client(
        account_id=os.environ["CLOUDFLARE_ACCOUNT_ID"],
        api_token=os.environ["CLOUDFLARE_API_TOKEN"],
        database_id=os.environ["CF_D1_DATABASE_ID"],
    )


def insert(table: str, record: dict[str, Any]) -> None:
    """Insert ``record`` into ``table`` using the env-configured default client."""
    _default_client().insert(table, record)


def query(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    """Run ``sql`` with ``params`` using the env-configured default client."""
    return _default_client().query(sql, params)
