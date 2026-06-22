"""Tests for the D1 ``eval_verdicts`` persistence (best-effort, no live network)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from eval_engine import verdict_store
from trace_core import (
    DimensionScore,
    EvalVerdict,
    FailureAttribution,
    SelfEvaluation,
)


def _verdict() -> EvalVerdict:
    """A representative failed verdict with attribution + dimensions."""
    return EvalVerdict(
        run_id="run-123",
        trial_number=0,
        verdict="fail",
        dimensions={
            "correctness": DimensionScore(score=0.4, reason="wrong", confidence=0.9),
            "safety": DimensionScore(score=1.0, reason="safe", confidence=1.0),
        },
        failure_attribution=FailureAttribution(
            step=2, component="retrieval", description="irrelevant context", confidence=0.8
        ),
        self_evaluation=SelfEvaluation(
            judge_confidence=0.55, self_critique="low evidence", flag_for_human=True
        ),
        replay_link="https://flight.example/runs/run-123",
        recommended_action="bisect step 2",
    )


def test_row_flattens_verdict_to_schema_columns() -> None:
    """``_row`` maps an EvalVerdict onto the eval_verdicts columns."""
    row = verdict_store._row(_verdict())
    assert row["run_id"] == "run-123"
    assert row["verdict"] == "fail"
    assert row["flag_for_human"] == 1  # SQLite boolean
    assert row["attribution_step"] == 2
    assert row["attribution_component"] == "retrieval"
    assert row["overall_score"] == pytest.approx(0.7)  # mean of 0.4 and 1.0
    assert row["confidence"] == pytest.approx(0.55)
    assert set(json.loads(row["dimensions_json"])) == {"correctness", "safety"}


def test_persist_noops_when_d1_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """With D1 env unset, persist is a no-op (returns False, makes no request)."""
    monkeypatch.delenv("CF_D1_DATABASE_ID", raising=False)

    def boom(*_a: Any, **_k: Any) -> None:
        raise AssertionError("must not touch the network when D1 is unconfigured")

    monkeypatch.setattr(httpx, "Client", boom)
    assert verdict_store.persist_verdict(_verdict()) is False


def test_persist_inserts_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """With D1 configured, persist POSTs an INSERT and returns True."""
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setenv("CF_D1_DATABASE_ID", "db")
    verdict_store._query_url.cache_clear()
    captured: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_a: Any) -> None:
            return None

        def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any]) -> FakeResponse:
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    assert verdict_store.persist_verdict(_verdict()) is True
    assert "INSERT INTO eval_verdicts" in captured["json"]["sql"]
    assert "run-123" in captured["json"]["params"]
    verdict_store._query_url.cache_clear()


def test_row_to_verdict_roundtrips_a_persisted_row() -> None:
    """A persisted row reconstructs into a faithful EvalVerdict for the dashboard."""
    row = verdict_store._row(_verdict())
    rebuilt = verdict_store._row_to_verdict(row)
    assert rebuilt.run_id == "run-123"
    assert rebuilt.verdict == "fail"
    assert set(rebuilt.dimensions) == {"correctness", "safety"}
    assert rebuilt.dimensions["correctness"].score == pytest.approx(0.4)
    assert rebuilt.self_evaluation.flag_for_human is True
    assert rebuilt.self_evaluation.judge_confidence == pytest.approx(0.55)
    assert rebuilt.failure_attribution is not None
    assert rebuilt.failure_attribution.step == 2
    assert rebuilt.failure_attribution.component == "retrieval"


def test_get_verdict_returns_none_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """With D1 unset, the read is a no-op (None) and makes no request."""
    monkeypatch.delenv("CF_D1_DATABASE_ID", raising=False)

    def boom(*_a: Any, **_k: Any) -> None:
        raise AssertionError("must not touch the network when D1 is unconfigured")

    monkeypatch.setattr(httpx, "Client", boom)
    assert verdict_store.get_verdict("run-123") is None
    assert verdict_store.list_verdicts() == []


def test_persist_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """A D1 failure is logged and swallowed (returns False), never raised."""
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setenv("CF_D1_DATABASE_ID", "db")
    verdict_store._query_url.cache_clear()

    class FakeClient:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_a: Any) -> None:
            return None

        def post(self, *_a: Any, **_k: Any) -> None:
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "Client", FakeClient)
    assert verdict_store.persist_verdict(_verdict()) is False
    verdict_store._query_url.cache_clear()
