"""Exceptions raised by the flight recorder.

Kept in their own module so any layer (proxy, replay, interceptor) can raise or
catch them without importing the heavier transport/storage modules.
"""

from __future__ import annotations


class FlightRecorderError(Exception):
    """Base class for all flight-recorder errors."""


class CassetteMissError(FlightRecorderError):
    """Raised in ``replay`` mode when a request has no recorded response.

    A miss means the agent issued a request that was never recorded — i.e. its
    behaviour diverged from the recorded run, or the cassette is incomplete.
    Replay must never fall back to a live call, so this is surfaced instead.
    """

    def __init__(self, step_key: str) -> None:
        self.step_key = step_key
        super().__init__(f"no recorded response for step_key {step_key!r}")
