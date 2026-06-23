"""Deterministic replay orchestrator.

:func:`replay_run` re-executes a recorded run with a :class:`RecordingTransport`
in ``replay`` mode, so every LLM call is served from the cassette and **zero
live API calls** are made. If the agent issues a request that was never recorded
(a cassette miss), that is reported as a divergence rather than escaping to the
network.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from pydantic import BaseModel, Field

from ..exceptions import CassetteMissError
from ..proxy import cassette
from ..proxy.llm_proxy import RecordingTransport

ReplayAgent = Callable[[httpx.Client], object]
"""An agent under replay: given a replay-bound client, it does its work.

The client's transport serves all CF Workers AI calls from the cassette, so the
agent runs exactly as recorded without touching live APIs.
"""


class Divergence(BaseModel):
    """A point where replay departed from the recorded run."""

    step_key: str = Field(description="Cassette key of the request that diverged.")
    reason: str = Field(description="Human-readable description of the divergence.")


class ReplayResult(BaseModel):
    """Outcome of replaying one recorded run."""

    run_id: str = Field(description="UUID of the replayed run.")
    recorded_steps: int = Field(ge=0, description="Number of steps in the cassette.")
    live_call_count: int = Field(
        ge=0, description="Live API calls made during replay; must be 0 for a clean replay."
    )
    diverged: bool = Field(description="True if replay differed from the recording.")
    divergences: list[Divergence] = Field(
        default_factory=list, description="Every detected divergence (empty when clean)."
    )
    injected_steps: list[int] = Field(
        default_factory=list,
        description="Indices of steps whose recorded response was overridden (divergence editing).",
    )

    @property
    def is_clean(self) -> bool:
        """A clean replay made no live calls and found no divergences."""
        return self.live_call_count == 0 and not self.diverged


def replay_run(
    run_id: str,
    agent: ReplayAgent | None = None,
    inject: dict[int, dict[str, object]] | None = None,
) -> ReplayResult:
    """Replay a recorded run from its cassette and report any divergence.

    Args:
        run_id: UUID of the run to replay.
        agent: Optional callable that re-drives the agent against a replay-bound
            ``httpx.Client``. When omitted, the cassette is loaded and validated
            without re-execution (a no-op replay that still proves 0 live calls).
        inject: Optional **divergence editing** (UC2 §3.4): a ``{step_index:
            stored_response}`` map overriding the recorded response at those steps,
            by position in the cassette's ``order``. The re-driven agent then sees
            the injected value and may take a new path (an unrecorded request shows
            up as a divergence). Requires ``agent``.

    Returns:
        A :class:`ReplayResult`. ``live_call_count`` is asserted to be 0 for the
        replay to be considered clean.
    """
    loaded = cassette.load_cassette(run_id)
    recorded_steps = len(loaded["steps"])
    order: list[str] = loaded["order"]
    injections: dict[str, dict[str, object]] = {}
    applied: list[int] = []
    for index, override in (inject or {}).items():
        if 0 <= index < len(order):
            injections[order[index]] = override
            applied.append(index)
    transport = RecordingTransport(run_id, mode="replay", injections=injections)
    divergences: list[Divergence] = []

    if agent is not None:
        client = httpx.Client(transport=transport)
        try:
            agent(client)
        except CassetteMissError as miss:
            divergences.append(
                Divergence(step_key=miss.step_key, reason="request not present in cassette")
            )
        finally:
            client.close()

    if transport.live_call_count != 0:
        divergences.append(
            Divergence(
                step_key="",
                reason=f"{transport.live_call_count} live API call(s) escaped during replay",
            )
        )

    return ReplayResult(
        run_id=run_id,
        recorded_steps=recorded_steps,
        live_call_count=transport.live_call_count,
        diverged=bool(divergences),
        divergences=divergences,
        injected_steps=sorted(applied),
    )
