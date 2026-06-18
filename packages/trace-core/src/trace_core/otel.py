"""OpenTelemetry GenAI span helpers.

Thin wrappers that create spans following the OTel GenAI semantic conventions
(``gen_ai.*``). These conventions are experimental and require opt-in via
``OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`` (set in the
``Makefile`` and ``.env``).

The agent-run helper also emits the ``gen_ai.replay.*`` attributes proposed in
``spec/otel-genai-replay-extension.md`` so a downstream tool can discover that a
trace has a replayable cassette.

Attribute names are written as string constants here (rather than imported from
the incubating semconv module, whose import path is unstable across releases) so
this helper does not break on an opentelemetry upgrade. Each constant cites its
semantic-convention name.

These helpers create spans only — they contain no business logic.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span, Tracer

# Instrumentation scope reported on every span this module creates.
_INSTRUMENTATION_NAME = "trace_core"
_INSTRUMENTATION_VERSION = "0.1.0"

# ─── gen_ai.* semantic convention attribute names ──────────────────────────────
# Source: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"  # "chat" | "execute_tool" | "invoke_agent"
GEN_AI_SYSTEM = "gen_ai.system"  # provider, e.g. "cf.workers_ai", "anthropic"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"  # requested model id
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"  # model id that actually served
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_TOOL_NAME = "gen_ai.tool.name"
GEN_AI_TOOL_CALL_ID = "gen_ai.tool.call.id"
GEN_AI_AGENT_NAME = "gen_ai.agent.name"
GEN_AI_AGENT_ID = "gen_ai.agent.id"

# ─── gen_ai.replay.* (Sentinel proposal — spec/otel-genai-replay-extension.md) ──
GEN_AI_REPLAY_RUN_ID = "gen_ai.replay.run_id"
GEN_AI_REPLAY_CASSETTE_ID = "gen_ai.replay.cassette_id"
GEN_AI_REPLAY_MODE = "gen_ai.replay.mode"  # "record" | "replay" | "passthrough"

# Maps a sampling-parameter key to its gen_ai.request.* attribute name.
# Source: gen_ai.request.* in the GenAI spans convention.
_SAMPLING_PARAM_ATTRS: dict[str, str] = {
    "temperature": "gen_ai.request.temperature",
    "top_p": "gen_ai.request.top_p",
    "top_k": "gen_ai.request.top_k",
    "max_tokens": "gen_ai.request.max_tokens",
    "presence_penalty": "gen_ai.request.presence_penalty",
    "frequency_penalty": "gen_ai.request.frequency_penalty",
    "stop_sequences": "gen_ai.request.stop_sequences",
}


def _get_tracer(tracer: Tracer | None) -> Tracer:
    """Return the supplied tracer, or this module's default tracer."""
    if tracer is not None:
        return tracer
    return trace.get_tracer(_INSTRUMENTATION_NAME, _INSTRUMENTATION_VERSION)


def _set(span: Span, key: str, value: Any) -> None:
    """Set a span attribute, skipping ``None`` so absent fields stay unset."""
    if value is not None:
        span.set_attribute(key, value)


@contextmanager
def emit_llm_call_span(
    model: str,
    *,
    operation: str = "chat",
    system: str | None = None,
    request_params: Mapping[str, Any] | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    response_model: str | None = None,
    tracer: Tracer | None = None,
) -> Iterator[Span]:
    """Open a span for an LLM call following the gen_ai chat convention.

    The span is named ``"{operation} {model}"`` (e.g. ``"chat llama-3.3-70b"``)
    per the convention. Token-usage and response-model attributes are usually set
    by the caller after the response returns; they are accepted here too for
    convenience.

    Args:
        model: Requested model identifier (``gen_ai.request.model``).
        operation: GenAI operation name (default ``"chat"``).
        system: Provider/system, e.g. ``"cf.workers_ai"`` (``gen_ai.system``).
        request_params: Sampling parameters; recognized keys are mapped to their
            ``gen_ai.request.*`` attributes (see ``_SAMPLING_PARAM_ATTRS``).
        input_tokens: Prompt token count (``gen_ai.usage.input_tokens``).
        output_tokens: Completion token count (``gen_ai.usage.output_tokens``).
        response_model: Model that served the response (``gen_ai.response.model``).
        tracer: Optional tracer; defaults to this module's tracer.

    Yields:
        The active :class:`~opentelemetry.trace.Span`, so the caller can attach
        additional attributes or events.
    """
    with _get_tracer(tracer).start_as_current_span(f"{operation} {model}") as span:
        _set(span, GEN_AI_OPERATION_NAME, operation)
        _set(span, GEN_AI_SYSTEM, system)
        _set(span, GEN_AI_REQUEST_MODEL, model)
        _set(span, GEN_AI_RESPONSE_MODEL, response_model)
        _set(span, GEN_AI_USAGE_INPUT_TOKENS, input_tokens)
        _set(span, GEN_AI_USAGE_OUTPUT_TOKENS, output_tokens)
        for key, value in (request_params or {}).items():
            attr = _SAMPLING_PARAM_ATTRS.get(key)
            if attr is not None:
                _set(span, attr, value)
        yield span


@contextmanager
def emit_tool_call_span(
    tool_name: str,
    *,
    tool_call_id: str | None = None,
    operation: str = "execute_tool",
    tracer: Tracer | None = None,
) -> Iterator[Span]:
    """Open a span for a tool/MCP call following the gen_ai execute_tool convention.

    The span is named ``"{operation} {tool_name}"`` (e.g.
    ``"execute_tool create_jira_issue"``) per the convention.

    Args:
        tool_name: Name of the tool/function invoked (``gen_ai.tool.name``).
        tool_call_id: Correlation id for this tool call (``gen_ai.tool.call.id``).
        operation: GenAI operation name (default ``"execute_tool"``).
        tracer: Optional tracer; defaults to this module's tracer.

    Yields:
        The active :class:`~opentelemetry.trace.Span`.
    """
    with _get_tracer(tracer).start_as_current_span(f"{operation} {tool_name}") as span:
        _set(span, GEN_AI_OPERATION_NAME, operation)
        _set(span, GEN_AI_TOOL_NAME, tool_name)
        _set(span, GEN_AI_TOOL_CALL_ID, tool_call_id)
        yield span


@contextmanager
def emit_agent_run_span(
    agent_name: str,
    *,
    agent_id: str | None = None,
    run_id: str | None = None,
    cassette_id: str | None = None,
    flight_mode: str | None = None,
    operation: str = "invoke_agent",
    tracer: Tracer | None = None,
) -> Iterator[Span]:
    """Open the root span for an agent run (gen_ai invoke_agent convention).

    Also emits the ``gen_ai.replay.*`` attributes from
    ``spec/otel-genai-replay-extension.md`` so downstream tooling can locate the
    cassette and know which mode the run executed under. The span is named
    ``"{operation} {agent_name}"``.

    Args:
        agent_name: Human-readable agent name (``gen_ai.agent.name``).
        agent_id: Stable agent identifier (``gen_ai.agent.id``).
        run_id: UUID of this run (``gen_ai.replay.run_id``).
        cassette_id: Cassette blob reference (``gen_ai.replay.cassette_id``).
        flight_mode: ``"record"`` | ``"replay"`` | ``"passthrough"``
            (``gen_ai.replay.mode``).
        operation: GenAI operation name (default ``"invoke_agent"``).
        tracer: Optional tracer; defaults to this module's tracer.

    Yields:
        The active root :class:`~opentelemetry.trace.Span`.
    """
    with _get_tracer(tracer).start_as_current_span(f"{operation} {agent_name}") as span:
        _set(span, GEN_AI_OPERATION_NAME, operation)
        _set(span, GEN_AI_AGENT_NAME, agent_name)
        _set(span, GEN_AI_AGENT_ID, agent_id)
        _set(span, GEN_AI_REPLAY_RUN_ID, run_id)
        _set(span, GEN_AI_REPLAY_CASSETTE_ID, cassette_id)
        _set(span, GEN_AI_REPLAY_MODE, flight_mode)
        yield span
