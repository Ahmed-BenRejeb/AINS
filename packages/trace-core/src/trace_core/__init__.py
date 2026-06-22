"""Sentinel trace-core: the shared contract for the whole platform.

Import everything you need from this top-level package::

    from trace_core import TraceRecord, EvalVerdict, PASS_AT_K_TRIALS

This package holds only types, schemas, constants, and pure helpers — no
business logic and no imports from any other local Sentinel package.
"""

from __future__ import annotations

from .constants import (
    AUDIT_HMAC_ALGORITHM,
    CASSETTE_VERSION,
    CONFIDENCE_THRESHOLD,
    DUPLICATE_CONFIDENCE_THRESHOLD,
    HASH_ALGORITHM,
    HASH_PREFIX,
    LOG_LEVEL,
    MAX_RETRIEVAL_RESULTS,
    PASS_AT_K_TRIALS,
    VECTOR_SIMILARITY_THRESHOLD,
    VOLATILE_REQUEST_FIELDS,
)
from .hash_utils import (
    canonical_json,
    hash_step_key,
    normalize_request,
    sha256_hex,
)
from .otel import (
    emit_agent_run_span,
    emit_llm_call_span,
    emit_tool_call_span,
)
from .schema import (
    Attribution,
    AuditBlock,
    DimensionScore,
    DriftReport,
    DuplicateVerdict,
    EvaluatorQuality,
    EvalVerdict,
    FailureAttribution,
    FlightMode,
    RcaDraft,
    RunManifest,
    RunStatus,
    SearchResult,
    SelfEvaluation,
    SeverityLevel,
    StepKind,
    StepMetadata,
    TraceRecord,
    VerdictLabel,
)

__all__ = [
    # constants
    "AUDIT_HMAC_ALGORITHM",
    "CASSETTE_VERSION",
    "CONFIDENCE_THRESHOLD",
    "DUPLICATE_CONFIDENCE_THRESHOLD",
    "HASH_ALGORITHM",
    "HASH_PREFIX",
    "LOG_LEVEL",
    "MAX_RETRIEVAL_RESULTS",
    "PASS_AT_K_TRIALS",
    "VECTOR_SIMILARITY_THRESHOLD",
    "VOLATILE_REQUEST_FIELDS",
    # hash utils
    "canonical_json",
    "hash_step_key",
    "normalize_request",
    "sha256_hex",
    # otel helpers
    "emit_agent_run_span",
    "emit_llm_call_span",
    "emit_tool_call_span",
    # schema — literal type aliases
    "FlightMode",
    "RunStatus",
    "SeverityLevel",
    "StepKind",
    "VerdictLabel",
    # schema — models
    "Attribution",
    "AuditBlock",
    "DimensionScore",
    "DriftReport",
    "DuplicateVerdict",
    "EvalVerdict",
    "EvaluatorQuality",
    "FailureAttribution",
    "RcaDraft",
    "RunManifest",
    "SearchResult",
    "SelfEvaluation",
    "StepMetadata",
    "TraceRecord",
]
