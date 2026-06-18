"""Sentinel flight recorder (UC2).

Transparently records every LLM call (Cloudflare Workers AI) and tool call an
agent makes, stores them in a cassette (MinIO) with a tamper-evident audit chain
(Cloudflare D1), and replays them deterministically with zero live API calls.

The single switch is ``FLIGHT_MODE`` (``record`` | ``replay`` | ``passthrough``).
Shared schemas and the cassette hash helpers come from ``trace_core`` and are
never redefined here.
"""

from __future__ import annotations

from .config import resolve_mode
from .exceptions import CassetteMissError, FlightRecorderError
from .proxy.llm_proxy import RecordingTransport
from .proxy.mcp_interceptor import record_tool
from .replay.bisect import BisectResult, bisect_runs
from .replay.engine import Divergence, ReplayResult, replay_run

__all__ = [
    "BisectResult",
    "CassetteMissError",
    "Divergence",
    "FlightRecorderError",
    "RecordingTransport",
    "ReplayResult",
    "bisect_runs",
    "record_tool",
    "replay_run",
    "resolve_mode",
]
