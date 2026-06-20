"""Run-manifest persistence — one summary row per recorded agent run.

The audit chain (``trace_records``) captures every step; a :class:`trace_core.RunManifest`
captures the run as a whole (agent, task, mode, cassette pointer, step count,
status, timing). It is written to Cloudflare D1 once the run completes so that the
flight-recorder API's ``GET /runs`` / ``GET /runs/{run_id}`` can list and locate it,
and the eval engine can find the matching cassette for replay.

The D1 column set mirrors ``infra/cloudflare/d1-schema.sql`` (``run_manifests``);
``created_at`` is left to the table default.
"""

from __future__ import annotations

from typing import Any

from trace_core import RunManifest

from .config import RUN_MANIFESTS_TABLE
from .storage import d1_client


def _manifest_row(manifest: RunManifest) -> dict[str, Any]:
    """Project a :class:`~trace_core.RunManifest` onto its D1 ``run_manifests`` row.

    Datetimes are serialized to ISO-8601 strings (D1 stores them as ``TEXT``).
    ``created_at`` is omitted so the table's ``datetime('now')`` default applies.

    Args:
        manifest: The completed run's manifest.

    Returns:
        A column→value mapping ready for :func:`flight_recorder.storage.d1_client.insert`.
    """
    return {
        "run_id": manifest.run_id,
        "agent_id": manifest.agent_id,
        "task_id": manifest.task_id,
        "flight_mode": manifest.flight_mode,
        "cassette_id": manifest.cassette_id,
        "step_count": manifest.step_count,
        "status": manifest.status,
        "started_at": manifest.started_at.isoformat(),
        "completed_at": manifest.completed_at.isoformat() if manifest.completed_at else None,
    }


def write_run_manifest(manifest: RunManifest) -> None:
    """Write a run's summary manifest row to Cloudflare D1 (``run_manifests``).

    Args:
        manifest: The completed run's :class:`~trace_core.RunManifest`.
    """
    d1_client.insert(RUN_MANIFESTS_TABLE, _manifest_row(manifest))
