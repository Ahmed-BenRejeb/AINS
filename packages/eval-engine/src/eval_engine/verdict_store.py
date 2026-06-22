"""Persist an ``EvalVerdict`` to the Cloudflare D1 ``eval_verdicts`` table.

The verdict is the eval engine's primary product. It is returned inline on
``/evaluate`` (and surfaced on ``/analyze``) and, on fail/flag, filed as a Jira
Incident — but it is *also* the durable record the dashboard's verdict screens
read. This module is the D1 write side for that record, mirroring the flight
recorder's ``storage.d1_client`` (which owns ``trace_records`` / ``run_manifests``)
the same way :mod:`eval_engine.cassette_store` mirrors its MinIO write side, so
eval-engine takes no cross-package dependency.

The write is **best-effort**: a D1 outage or missing config must never fail
evaluation. Tests monkeypatch :func:`persist_verdict`, so no live D1 (or network)
is touched.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from functools import lru_cache
from typing import Any

import httpx
from trace_core import EvalVerdict

logger = logging.getLogger("eval_engine.verdict_store")

_D1_TIMEOUT_SECONDS = 30.0
_REQUIRED_ENV = ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "CF_D1_DATABASE_ID")


@lru_cache(maxsize=1)
def _query_url() -> str:
    """Build the D1 ``query`` endpoint URL from the environment (cached)."""
    account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    database_id = os.environ["CF_D1_DATABASE_ID"]
    return (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/d1/database/{database_id}/query"
    )


def _overall_score(verdict: EvalVerdict) -> float | None:
    """Mean of the per-dimension scores (the headline numeric for a verdict)."""
    if not verdict.dimensions:
        return None
    return sum(d.score for d in verdict.dimensions.values()) / len(verdict.dimensions)


def _row(verdict: EvalVerdict) -> dict[str, Any]:
    """Flatten an ``EvalVerdict`` into one ``eval_verdicts`` row (schema columns)."""
    attribution = verdict.failure_attribution
    dimensions_json = {name: score.model_dump() for name, score in verdict.dimensions.items()}
    return {
        "id": str(uuid.uuid4()),
        "run_id": verdict.run_id,
        "trial_number": verdict.trial_number,
        "verdict": verdict.verdict,
        "overall_score": _overall_score(verdict),
        "confidence": verdict.self_evaluation.judge_confidence,
        "flag_for_human": int(verdict.self_evaluation.flag_for_human),
        "attribution_step": attribution.step if attribution else None,
        "attribution_component": attribution.component if attribution else None,
        "dimensions_json": json.dumps(dimensions_json),
        "self_critique": verdict.self_evaluation.self_critique,
        "replay_link": verdict.replay_link,
        "recommended_action": verdict.recommended_action,
    }


def persist_verdict(verdict: EvalVerdict) -> bool:
    """Insert ``verdict`` into the D1 ``eval_verdicts`` table (best-effort).

    Args:
        verdict: The assembled verdict to persist.

    Returns:
        ``True`` if the row was written, ``False`` if D1 is unconfigured or the
        write failed (in which case the error is logged, not raised).
    """
    if not all(os.environ.get(key) for key in _REQUIRED_ENV):
        logger.debug("D1 not configured; skipping eval_verdicts persist")
        return False
    record = _row(verdict)
    columns = list(record.keys())
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO eval_verdicts ({', '.join(columns)}) VALUES ({placeholders})"
    try:
        with httpx.Client(timeout=_D1_TIMEOUT_SECONDS) as client:
            response = client.post(
                _query_url(),
                headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}"},
                json={"sql": sql, "params": [record[column] for column in columns]},
            )
            response.raise_for_status()
    except Exception as exc:  # best-effort: a D1 failure must not fail evaluation
        logger.warning("failed to persist eval_verdict for run %s: %s", verdict.run_id, exc)
        return False
    return True
