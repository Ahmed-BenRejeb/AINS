"""Decorator that records and replays tool/function calls.

The LLM proxy handles model calls; this handles the *other* side effect an agent
has — calling tools (MCP servers, Python functions). Wrap any function with
:func:`record_tool` and its calls are taped into the same cassette keyed by a
hash of ``(tool name, args, kwargs)``:

* ``record``      — call the real function, store its result, write an audit record.
* ``replay``      — return the stored result; the real function is never called.
* ``passthrough`` — call the real function; record nothing.

Results should be JSON-serializable (Pydantic structured outputs are handled) so
the replay is deterministic — see ``docs/BATTLE_PLAN.md`` §4 (AgentRR).
"""

from __future__ import annotations

import functools
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypeVar, cast

from pydantic import BaseModel
from trace_core import FlightMode, hash_step_key, normalize_request

from ..audit.hash_chain import sign, write_audit_record
from ..config import GENESIS_PREV_HASH, resolve_mode
from ..exceptions import CassetteMissError
from . import cassette

F = TypeVar("F", bound=Callable[..., Any])

# Per-run audit-chain heads so tool records chain together across calls.
_PREV_HASH: dict[str, str] = {}
_SEQUENCE: dict[str, int] = {}


def _jsonable(value: Any) -> Any:
    """Coerce a value into something JSON-serializable for hashing/storage.

    Pydantic models are dumped to JSON-mode dicts; other values are returned as
    is when natively serializable, else stringified as a last resort.
    """
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def _call_step_key(tool_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Deterministic cassette key for one tool invocation."""
    normalized = normalize_request(
        {
            "tool": tool_name,
            "args": [_jsonable(a) for a in args],
            "kwargs": {k: _jsonable(v) for k, v in kwargs.items()},
        }
    )
    return hash_step_key(normalized)


def record_tool(run_id: str, mode: FlightMode | None = None) -> Callable[[F], F]:
    """Decorate a function so its calls are recorded into / replayed from a run.

    Args:
        run_id: UUID of the run the tool calls belong to.
        mode: Override for ``FLIGHT_MODE``; resolved from the env when ``None``.

    Returns:
        A decorator that wraps the target function.
    """
    resolved_mode = resolve_mode(mode)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tool_name = func.__name__
            step_key = _call_step_key(tool_name, args, kwargs)

            if resolved_mode == "replay":
                steps = cassette.load_cassette(run_id)["steps"]
                if step_key not in steps:
                    raise CassetteMissError(step_key)
                return steps[step_key]["result"]

            if resolved_mode == "passthrough":
                return func(*args, **kwargs)

            # record
            result = func(*args, **kwargs)
            stored = {"tool": tool_name, "result": _jsonable(result)}
            prev_hash = _PREV_HASH.get(run_id, GENESIS_PREV_HASH)
            sequence = _SEQUENCE.get(run_id, 0)
            step_id = uuid.uuid4().hex
            input_data = {
                "tool": tool_name,
                "args": [_jsonable(a) for a in args],
                "kwargs": {k: _jsonable(v) for k, v in kwargs.items()},
            }
            payload_hash = write_audit_record(
                run_id=run_id,
                step_id=step_id,
                kind="tool_call",
                input_data=input_data,
                output_data=stored,
                prev_hash=prev_hash,
                sequence=sequence,
            )
            record = {
                "run_id": run_id,
                "step_id": step_id,
                "sequence": sequence,
                "timestamp": datetime.now(UTC).isoformat(),
                "kind": "tool_call",
                "input": input_data,
                "output": stored,
                "metadata": {"tool_name": tool_name},
                "audit": {
                    "prev_hash": prev_hash,
                    "payload_hash": payload_hash,
                    "hmac": sign(payload_hash),
                },
            }
            cassette.save_to_cassette(run_id, step_key, stored, record=record)
            _PREV_HASH[run_id] = payload_hash
            _SEQUENCE[run_id] = sequence + 1
            return result

        return cast(F, wrapper)

    return decorator
