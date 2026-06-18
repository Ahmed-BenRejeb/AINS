"""Tests for the OTel GenAI span helpers.

Uses an in-memory span exporter so the helpers can be exercised without any
external collector. Verifies the gen_ai.* (and gen_ai.replay.*) attributes are
emitted with the conventional span names.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Tracer
from trace_core import (
    emit_agent_run_span,
    emit_llm_call_span,
    emit_tool_call_span,
)


@pytest.fixture()
def exporter_and_tracer() -> Iterator[tuple[InMemorySpanExporter, Tracer]]:
    """Provide a fresh in-memory exporter and a tracer wired to it."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    yield exporter, tracer
    provider.shutdown()


def test_emit_llm_call_span_sets_gen_ai_attributes(
    exporter_and_tracer: tuple[InMemorySpanExporter, Tracer],
) -> None:
    exporter, tracer = exporter_and_tracer
    with emit_llm_call_span(
        "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        system="cf.workers_ai",
        request_params={"temperature": 0.0, "max_tokens": 1000},
        input_tokens=12,
        output_tokens=34,
        tracer=tracer,
    ):
        pass
    (span,) = exporter.get_finished_spans()
    assert span.name == "chat @cf/meta/llama-3.3-70b-instruct-fp8-fast"
    attrs = dict(span.attributes or {})
    assert attrs["gen_ai.operation.name"] == "chat"
    assert attrs["gen_ai.system"] == "cf.workers_ai"
    assert attrs["gen_ai.request.model"] == "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    assert attrs["gen_ai.request.temperature"] == 0.0
    assert attrs["gen_ai.request.max_tokens"] == 1000
    assert attrs["gen_ai.usage.input_tokens"] == 12
    assert attrs["gen_ai.usage.output_tokens"] == 34


def test_emit_tool_call_span_sets_tool_attributes(
    exporter_and_tracer: tuple[InMemorySpanExporter, Tracer],
) -> None:
    exporter, tracer = exporter_and_tracer
    with emit_tool_call_span("create_jira_issue", tool_call_id="call-1", tracer=tracer):
        pass
    (span,) = exporter.get_finished_spans()
    assert span.name == "execute_tool create_jira_issue"
    attrs = dict(span.attributes or {})
    assert attrs["gen_ai.operation.name"] == "execute_tool"
    assert attrs["gen_ai.tool.name"] == "create_jira_issue"
    assert attrs["gen_ai.tool.call.id"] == "call-1"


def test_emit_agent_run_span_sets_replay_attributes(
    exporter_and_tracer: tuple[InMemorySpanExporter, Tracer],
) -> None:
    exporter, tracer = exporter_and_tracer
    with emit_agent_run_span(
        "incident-rca-agent",
        agent_id="agent-1",
        run_id="run-1",
        cassette_id="sentinel-cassettes/run-1",
        flight_mode="record",
        tracer=tracer,
    ):
        pass
    (span,) = exporter.get_finished_spans()
    assert span.name == "invoke_agent incident-rca-agent"
    attrs = dict(span.attributes or {})
    assert attrs["gen_ai.operation.name"] == "invoke_agent"
    assert attrs["gen_ai.agent.name"] == "incident-rca-agent"
    assert attrs["gen_ai.agent.id"] == "agent-1"
    assert attrs["gen_ai.replay.run_id"] == "run-1"
    assert attrs["gen_ai.replay.cassette_id"] == "sentinel-cassettes/run-1"
    assert attrs["gen_ai.replay.mode"] == "record"


def test_omitted_optional_attributes_are_not_set(
    exporter_and_tracer: tuple[InMemorySpanExporter, Tracer],
) -> None:
    """None-valued optional fields must not appear as span attributes."""
    exporter, tracer = exporter_and_tracer
    with emit_tool_call_span("noop", tracer=tracer):
        pass
    (span,) = exporter.get_finished_spans()
    attrs = dict(span.attributes or {})
    assert "gen_ai.tool.call.id" not in attrs
