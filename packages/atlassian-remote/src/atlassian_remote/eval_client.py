"""Call the eval engine (UC1) to judge a freshly recorded run.

After the analyzer records an RCA-generation run, it asks the eval engine to grade
it: ``POST {EVAL_ENGINE_URL}/evaluate {"run_id": ...}``. The eval engine loads the
run's trace from the flight recorder, runs the safety → code → judge pipeline, and
(on a failing/flagged verdict) files a Jira Incident itself — so the verdict is
returned for display, while the *side effect* of filing is owned by UC1.

The call is internal VM-to-VM (localhost:8000), never the public tunnel. It is
best-effort: an eval outage must not fail the incident analysis, so failures log
and return ``None`` (the analyze response carries a null verdict).
"""

from __future__ import annotations

import logging

import httpx
from trace_core import EvalVerdict

from .config import EVAL_TIMEOUT_SECONDS, eval_engine_url, forge_remote_secret

logger = logging.getLogger("atlassian_remote.eval_client")


def _auth_headers() -> dict[str, str]:
    """Shared-secret header for the eval engine's protected API (empty if unset)."""
    try:
        return {"X-Sentinel-Secret": forge_remote_secret()}
    except KeyError:
        return {}


async def request_evaluation(run_id: str) -> EvalVerdict | None:
    """Ask the eval engine to evaluate ``run_id`` and return its verdict.

    Args:
        run_id: UUID of the run the flight recorder just captured.

    Returns:
        The :class:`~trace_core.EvalVerdict`, or ``None`` if the eval engine is
        unreachable or returns an unparseable body (logged, non-fatal).
    """
    try:
        async with httpx.AsyncClient(timeout=EVAL_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{eval_engine_url()}/evaluate",
                json={"run_id": run_id},
                headers=_auth_headers(),
            )
            response.raise_for_status()
            return EvalVerdict.model_validate(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("eval-engine evaluation failed for run_id=%s: %s", run_id, exc)
        return None
