# OTel GenAI Replay Extension — Specification Proposal

**Status:** Draft · **Authors:** Selecao team · **Hackathon:** AINS 2026

---

## Problem Statement

The [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) define a standard set of `gen_ai.*` span attributes for tracing LLM calls. As of mid-2026, these conventions are still **experimental** (`OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`).

Two specific gaps exist:

1. **No replay manifest standard.** There is no standard way to attach a deterministic replay cassette reference to a trace — i.e., no way for a downstream tool to know that this trace has a corresponding cassette of recorded boundary events that can be used to re-execute it deterministically.

2. **No stable evaluation event schema.** The evaluation layer in the OTel GenAI conventions is nascent. There is no agreed schema for `gen_ai.eval.*` events covering verdict, score, grader type, or judge confidence.

---

## Proposed Attributes

### `gen_ai.replay.*` — Replay Manifest Attributes

Added as attributes on the root `invoke_agent` span:

| Attribute | Type | Required | Description |
|---|---|---|---|
| `gen_ai.replay.run_id` | string | Yes | UUID of this recorded run |
| `gen_ai.replay.cassette_id` | string | Yes | Reference to the cassette blob in storage |
| `gen_ai.replay.cassette_version` | int | Yes | Schema version of the cassette format |
| `gen_ai.replay.mode` | string | Yes | `record` \| `replay` \| `passthrough` |
| `gen_ai.replay.step_count` | int | No | Number of recorded steps in this run |
| `gen_ai.replay.diverged` | boolean | No | Whether this replay diverged from the original |
| `gen_ai.replay.diverged_at_step` | int | No | Step index where divergence first occurred |

### `gen_ai.eval.*` — Evaluation Event Attributes

Added as span events on the root `invoke_agent` span after evaluation completes:

| Attribute | Type | Required | Description |
|---|---|---|---|
| `gen_ai.eval.verdict` | string | Yes | `pass` \| `fail` \| `uncertain` |
| `gen_ai.eval.score` | double | Yes | Aggregate score 0.0–1.0 |
| `gen_ai.eval.grader` | string | Yes | `code` \| `llm` \| `human` \| `composite` |
| `gen_ai.eval.dimension` | string | No | Dimension being scored (correctness, efficiency, etc.) |
| `gen_ai.eval.confidence` | double | No | Judge confidence 0.0–1.0 |
| `gen_ai.eval.flag_for_human` | boolean | No | Whether this verdict needs human review |
| `gen_ai.eval.attribution_step` | int | No | Step index attributed as failure cause |
| `gen_ai.eval.attribution_component` | string | No | Component attributed (retrieval, planning, execution) |

---

## Reference Implementation

The reference implementation of both attribute sets is in `packages/flight-recorder/`:

- `packages/flight-recorder/audit/hash_chain.py` — emits `gen_ai.replay.*` attributes on run start
- `packages/eval-engine/verdicts/reporter.py` — emits `gen_ai.eval.*` events on verdict production

---

## Open Questions

1. Should `gen_ai.replay.cassette_id` be a URI (e.g., `r2://sentinel-cassettes/run-abc123`) or an opaque string?
2. Should `gen_ai.eval.*` be span attributes or span events? Events allow multiple evaluations per run (e.g., one per component).
3. How should multi-trial (`pass^k`) evaluation results be represented — one event per trial, or aggregate only?
