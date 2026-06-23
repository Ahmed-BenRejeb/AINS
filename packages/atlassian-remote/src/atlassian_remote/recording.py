"""Flight-recorder (UC2) integration for the analyze pipeline.

Wraps the flight recorder so the analyzer stays readable: a :class:`RunRecorder`
context routes every CF Workers AI call made inside it through the recorder's
:class:`~flight_recorder.AsyncRecordingTransport` (taping each call into the run's
MinIO cassette + the D1 audit chain), and :func:`persist_manifest` writes the
one-per-run summary row to D1 once the analysis completes.

Recording is best-effort infrastructure: a recorder/D1 hiccup must never fail the
incident analysis itself, so manifest persistence swallows and logs errors.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from types import TracebackType

from flight_recorder import AsyncRecordingTransport, write_run_manifest
from flight_recorder.config import resolve_mode
from trace_core import RunManifest, RunStatus

from . import cf_ai_client

logger = logging.getLogger("atlassian_remote.recording")

AGENT_ID = "atlassian-remote"
"""``agent_id`` recorded on every run manifest this backend produces."""


def new_run_id() -> str:
    """Generate a fresh run id (uuid4 hex). Seam so tests can pin it."""
    return uuid.uuid4().hex


class RunRecorder:
    """Scope a run's CF Workers AI calls onto a flight-recorder cassette.

    Entering binds the recorder's :class:`~flight_recorder.AsyncRecordingTransport`
    as :mod:`cf_ai_client`'s active transport (via a contextvar), so embedding and
    RCA calls issued inside the ``with`` block are recorded under ``run_id``.
    Exiting clears the binding. After the block, :attr:`step_count` reports how many
    CF calls were taped.
    """

    def __init__(self, run_id: str) -> None:
        """Bind a recorder to ``run_id`` using the env-resolved ``FLIGHT_MODE``."""
        self.run_id = run_id
        self.started_at = datetime.now(UTC)
        self.transport = AsyncRecordingTransport(run_id, mode=resolve_mode())
        self._binding = cf_ai_client.using_transport(self.transport)

    def __enter__(self) -> RunRecorder:
        """Activate the recording transport for this thread/task."""
        self._binding.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Deactivate the recording transport."""
        self._binding.__exit__(exc_type, exc, tb)

    @property
    def step_count(self) -> int:
        """Number of CF Workers AI calls recorded during the run so far."""
        return self.transport.step_count

    def record_tool_call(
        self,
        *,
        tool_name: str,
        arguments: dict[str, object],
        output: dict[str, object],
        input_preview: str,
        output_preview: str,
        extra_metadata: dict[str, object] | None = None,
    ) -> None:
        """Tape a logical tool call (e.g. an xqdrant search) into the run's trace.

        Enriches the trace with the agent's non-LLM workflow steps so it reads as
        embed -> search -> search -> reason, not just raw model calls. Best-effort:
        a recorder hiccup must never fail the analysis. The xqdrant searches reuse
        the already-taped query embedding, so no extra LLM call is made.

        Args:
            extra_metadata: Optional display-only fields merged into ``metadata_json``
                (e.g. retrieval ``attributions`` for the dashboard timeline).
        """
        metadata: dict[str, object] = {"tool_name": tool_name, "operation": "retrieval"}
        if extra_metadata:
            metadata.update(extra_metadata)
        try:
            self.transport.record_event(
                kind="tool_call",
                input_data={"tool_name": tool_name, "arguments": arguments},
                output_data=output,
                metadata=metadata,
                input_preview=input_preview,
                output_preview=output_preview,
            )
        except Exception as exc:  # recording must never break the incident analysis
            logger.warning("failed to record tool call %s: %s", tool_name, exc)


def persist_manifest(
    run_id: str,
    *,
    step_count: int,
    task_id: str,
    started_at: datetime,
    completed_at: datetime | None = None,
    status: RunStatus = "completed",
) -> None:
    """Write the run's summary manifest to the flight recorder's D1 (best-effort).

    Args:
        run_id: UUID of the recorded run.
        step_count: Number of recorded steps (CF Workers AI calls).
        task_id: The incident key the run analysed.
        started_at: When the run started.
        completed_at: When the run finished (defaults to now).
        status: Run lifecycle status (default ``"completed"``).
    """
    try:
        manifest = RunManifest(
            run_id=run_id,
            agent_id=AGENT_ID,
            task_id=task_id,
            flight_mode=resolve_mode(),
            cassette_id=f"{run_id}.json",
            step_count=step_count,
            status=status,
            started_at=started_at,
            completed_at=completed_at or datetime.now(UTC),
        )
        write_run_manifest(manifest)
    except Exception as exc:  # recording must never break the incident analysis
        logger.warning("failed to persist run manifest run_id=%s: %s", run_id, exc)
