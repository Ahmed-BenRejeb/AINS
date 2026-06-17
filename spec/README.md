# spec/

Protocol gap proposals and design specifications.
This is our **open contribution** — a key differentiator for the hackathon bonus points.

---

## Why This Folder Exists

The hackathon spec awards bonus points for:
> *"The team identifies a specific, documented gap in tool protocols or evaluation architectures and implements a concrete solution, with clear documentation of the problem and the approach."*

This folder contains our proposals. They are real, verifiable protocol gaps — not invented for the hackathon. Each document defines the problem, proposes a solution, and links to the reference implementation in the relevant package.

---

## Documents

### `otel-genai-replay-extension.md`

**The gap:** The [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) define how to trace LLM calls (`gen_ai.*` spans) but have **no standard for attaching a deterministic replay manifest to a trace**. There is also no stable evaluation event schema. These conventions are still experimental.

**Our proposal:** Define `gen_ai.replay.*` span attributes and a `gen_ai.eval.*` event schema, with a reference implementation in `packages/flight-recorder`.

### `mcp-audit-trail-proposal.md`

**The gap:** The [MCP specification](https://spec.modelcontextprotocol.io/) defines how AI agents call tools via a standardized protocol, but has **no standardized audit trail** for what tools an agent called, with what arguments, at what time, across sessions. There is also no specified way to verify that an audit log has not been tampered with after the fact.

**Our proposal:** Define a hash-chained, HMAC-signed audit record format for MCP tool calls, with a reference implementation in `packages/flight-recorder/audit/`.

---

## Quality Standard

These documents must be written as if they were real RFC-style proposals — clear problem statement, proposed solution, examples, open questions. They will be read by judges. Do not treat them as afterthoughts.
