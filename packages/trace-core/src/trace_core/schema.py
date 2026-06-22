"""Pydantic v2 models that cross package boundaries in Sentinel.

This is the single source of truth for every data structure shared between
packages (flight-recorder, eval-engine, atlassian-remote, dashboard). If a type
is used by more than one package, it lives here and is never redefined.

Mirrored in ``schema.ts`` for the TypeScript side (dashboard + Forge). When a
field changes here, it must change there in the same commit.

This module contains schemas only — no business logic, no I/O.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ─── Shared literal types ──────────────────────────────────────────────────────

StepKind = Literal["llm_call", "tool_call", "decision", "state_snapshot"]
"""The kind of boundary event a :class:`TraceRecord` captures."""

FlightMode = Literal["record", "replay", "passthrough"]
"""Flight-recorder operating mode (``.env`` key ``FLIGHT_MODE``)."""

RunStatus = Literal["running", "completed", "failed", "aborted"]
"""Lifecycle status of a recorded agent run."""

VerdictLabel = Literal["pass", "fail", "uncertain"]
"""Outcome of an evaluation. ``uncertain`` is emitted when judge calibration
detects a position-bias flip (AgentRewardBench, arXiv:2504.08942)."""

SeverityLevel = Literal["critical", "high", "medium", "low"]
"""Proposed incident severity for a UC3 RCA draft."""


# ─── Flight Recorder — trace & audit (UC2) ─────────────────────────────────────


class StepMetadata(BaseModel):
    """Provenance and timing for a single recorded step.

    Fields are optional because not every step kind populates every field: an
    ``llm_call`` sets ``model_id`` and ``sampling_params`` while a ``tool_call``
    sets ``tool_name`` and ``tool_version`` instead.
    """

    model_id: str | None = Field(
        default=None,
        description="LLM model identifier for llm_call steps (e.g. a CF Workers AI model).",
    )
    tool_name: str | None = Field(
        default=None,
        description="Tool/function name for tool_call steps (e.g. 'create_jira_issue').",
    )
    tool_version: str | None = Field(
        default=None,
        description="Version string of the tool/MCP server that handled the call.",
    )
    latency_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Wall-clock latency of the step in milliseconds.",
    )
    sampling_params: dict[str, Any] | None = Field(
        default=None,
        description="LLM sampling parameters (temperature, top_p, max_tokens, ...).",
    )


class AuditBlock(BaseModel):
    """One link in the tamper-evident, hash-chained audit trail.

    See ``spec/mcp-audit-trail-proposal.md``. Records are written before
    execution (write-ahead). Each block's ``prev_hash`` equals the previous
    block's ``payload_hash``, forming a chain; the ``hmac`` makes each block
    individually tamper-evident. Verification recomputes ``payload_hash`` and
    checks the chain is unbroken.
    """

    prev_hash: str = Field(
        description="payload_hash of the previous record (chain link); genesis is all-zero.",
    )
    payload_hash: str = Field(
        description="SHA-256 of this record's canonical JSON, e.g. 'sha256:...'.",
    )
    hmac: str = Field(
        description="HMAC-SHA256 of payload_hash signed with AUDIT_HMAC_KEY.",
    )


class TraceRecord(BaseModel):
    """A single recorded boundary event in an agent run.

    The atomic unit of the flight recorder. A run is an ordered sequence of
    these (by ``sequence``), each carrying its raw input/output, provenance
    metadata, and an audit-chain link. Modelled on the OTel GenAI ``gen_ai.*``
    span shape so it round-trips cleanly to/from traces.
    """

    run_id: str = Field(description="UUID of the run this step belongs to.")
    step_id: str = Field(description="UUID uniquely identifying this step.")
    sequence: int = Field(ge=0, description="0-based position of this step within the run.")
    timestamp: datetime = Field(description="UTC timestamp when the step was recorded.")
    kind: StepKind = Field(description="The kind of boundary event captured.")
    input: dict[str, Any] = Field(description="Raw input payload sent at this step.")
    output: dict[str, Any] = Field(description="Raw output payload received at this step.")
    metadata: StepMetadata = Field(description="Provenance and timing for this step.")
    audit: AuditBlock = Field(description="Hash-chained, HMAC-signed audit link for this step.")


class RunManifest(BaseModel):
    """Summary record describing one complete agent run.

    Stored as trace metadata (Cloudflare D1) and used to locate the matching
    cassette for replay. Surfaces the ``gen_ai.replay.*`` attributes defined in
    ``spec/otel-genai-replay-extension.md``.
    """

    run_id: str = Field(description="UUID of this run.")
    agent_id: str = Field(description="Identifier of the agent that produced the run.")
    task_id: str = Field(description="Identifier of the task/scenario the agent was given.")
    flight_mode: FlightMode = Field(description="Recorder mode the run executed under.")
    cassette_id: str | None = Field(
        default=None,
        description="Reference to the cassette blob in storage (None until recorded).",
    )
    step_count: int = Field(ge=0, description="Number of recorded steps in the run.")
    status: RunStatus = Field(description="Lifecycle status of the run.")
    started_at: datetime = Field(description="UTC timestamp when the run started.")
    completed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the run finished (None while running).",
    )


# ─── Eval Engine — verdicts & attribution (UC1) ────────────────────────────────


class DimensionScore(BaseModel):
    """Score for one rubric dimension (correctness, efficiency, safety, ...)."""

    score: float = Field(ge=0.0, le=1.0, description="Normalized dimension score in [0, 1].")
    reason: str = Field(description="Human-readable justification for the score.")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Judge confidence in this dimension score, in [0, 1]."
    )


class FailureAttribution(BaseModel):
    """Per-step credit assignment for a failure (VeriLA pattern).

    Not just "the run failed" but "component X at step N caused it, with
    confidence C" — see ``docs/BATTLE_PLAN.md`` §5.
    """

    step: int = Field(ge=0, description="0-based index of the step blamed for the failure.")
    component: str = Field(
        description="Component attributed (e.g. 'retrieval', 'planning', 'execution').",
    )
    description: str = Field(description="Explanation of how this step caused the failure.")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in this attribution, in [0, 1]."
    )


class SelfEvaluation(BaseModel):
    """The judge's evaluation of its own verdict (self-evaluation bonus point).

    See ``docs/BATTLE_PLAN.md`` §10. A low ``judge_confidence`` sets
    ``flag_for_human`` and auto-files a "Human Review Required" Jira issue.
    """

    judge_confidence: float = Field(
        ge=0.0, le=1.0, description="Overall confidence the judge has in its verdict, in [0, 1]."
    )
    self_critique: str = Field(description="The judge's critique of its own reasoning.")
    flag_for_human: bool = Field(description="True if this verdict needs human review.")


class EvalVerdict(BaseModel):
    """The structured result of evaluating one agent run trial.

    Produced by the three-grader pipeline (safety → code → LLM judge). One
    verdict is emitted per trial; ``pass^k`` aggregates ``PASS_AT_K_TRIALS`` of
    them. Designed so a non-AI engineer can read and act on every field.
    """

    run_id: str = Field(description="UUID of the run that was evaluated.")
    trial_number: int = Field(
        ge=0, description="0-based trial index within a pass^k evaluation batch."
    )
    verdict: VerdictLabel = Field(description="Overall pass/fail/uncertain outcome.")
    dimensions: dict[str, DimensionScore] = Field(
        description="Per-dimension rubric scores keyed by dimension name.",
    )
    failure_attribution: FailureAttribution | None = Field(
        default=None,
        description="Which step/component caused the failure (None when verdict is pass).",
    )
    self_evaluation: SelfEvaluation = Field(
        description="The judge's confidence and self-critique for this verdict.",
    )
    replay_link: str = Field(description="Deep link to the deterministic replay of this run.")
    recommended_action: str = Field(
        description="Concrete next step for a human (e.g. 'open replay and bisect step 3').",
    )


class DriftReport(BaseModel):
    """Behavioural-drift comparison between a baseline and a current set of runs.

    Implements the UC1 drift-detection capability (official brief §2.3): compare
    evaluation results across runs over time and detect meaningful shifts in agent
    behaviour, tool usage, or output characteristics. Two complementary signals are
    combined — verdict/score drift (from :class:`EvalVerdict` aggregates) and
    semantic drift of the agents' output text (BGE-embedding centroid distance) —
    so a regression is caught whether or not the pass/fail outcome moved (brief
    Scenario B: "longer, less structured summaries after a model update"). Every
    field is human-readable so a non-AI engineer can act on the ``summary``.
    """

    baseline_run_count: int = Field(ge=0, description="Number of runs in the baseline window.")
    current_run_count: int = Field(ge=0, description="Number of runs in the current window.")
    pass_rate_baseline: float = Field(
        ge=0.0, le=1.0, description="Fraction of baseline runs whose verdict was 'pass'."
    )
    pass_rate_current: float = Field(
        ge=0.0, le=1.0, description="Fraction of current runs whose verdict was 'pass'."
    )
    pass_rate_delta: float = Field(
        description="pass_rate_current - pass_rate_baseline (negative = regression)."
    )
    mean_score_baseline: float = Field(
        ge=0.0, le=1.0, description="Mean rubric-dimension score across the baseline runs."
    )
    mean_score_current: float = Field(
        ge=0.0, le=1.0, description="Mean rubric-dimension score across the current runs."
    )
    dimension_deltas: dict[str, float] = Field(
        description="Per-dimension mean-score change (current - baseline), keyed by dimension.",
    )
    most_shifted_dimension: str | None = Field(
        default=None,
        description="Dimension with the largest absolute score change (None if no dimensions).",
    )
    semantic_drift: float | None = Field(
        default=None,
        description="Cosine distance between baseline/current output-embedding centroids "
        "(0 = identical, higher = more drift); None when no output text was supplied.",
    )
    drift_detected: bool = Field(
        description="True when any signal crosses its drift threshold.",
    )
    drift_score: float = Field(
        ge=0.0, le=1.0, description="Overall drift magnitude in [0, 1] (max of the signals)."
    )
    summary: str = Field(
        description="Human-readable explanation of what shifted and by how much.",
    )


class EvaluatorQuality(BaseModel):
    """Quality of the evaluator itself, measured against a human-labelled gold set.

    Implements the UC1 "evaluation of the evaluator" criterion (official brief §2.4
    "Should"): the team defines and reports at least one metric assessing the
    quality of the evaluation system. The evaluator is run over a gold set of runs
    with known human verdicts; agreement is reported as raw accuracy **and** Cohen's
    κ (chance-corrected, so a judge that always says "pass" on a mostly-passing set
    is not credited). ``per_label_recall`` and ``agreement_band`` make it explainable.
    """

    n_cases: int = Field(ge=0, description="Number of gold-labelled cases scored.")
    n_agreements: int = Field(
        ge=0, description="Cases where the evaluator's verdict matched the human label."
    )
    accuracy: float = Field(
        ge=0.0, le=1.0, description="Raw agreement: n_agreements / n_cases (0.0 when empty)."
    )
    cohen_kappa: float = Field(
        ge=-1.0,
        le=1.0,
        description="Chance-corrected agreement (Cohen's κ): 1 perfect, 0 chance, <0 worse.",
    )
    per_label_recall: dict[str, float] = Field(
        description="Per gold-label fraction the evaluator matched (sensitivity), keyed by label.",
    )
    agreement_band: str = Field(
        description="Qualitative κ band (Landis & Koch): e.g. 'substantial', 'moderate'.",
    )
    summary: str = Field(
        description="Human-readable one-line assessment of evaluator quality.",
    )


# ─── Retrieval & explainability (xqdrant) ──────────────────────────────────────


class Attribution(BaseModel):
    """Explainability payload for a vector-search hit (xqdrant extension).

    xqdrant's differentiator over plain Qdrant: it reports *why* a result
    matched. ``dims`` and ``terms`` break the score down by contribution, and
    ``confidence_margin`` is the gap to the runner-up — a small margin signals
    an ambiguous match.
    """

    dims: dict[str, float] = Field(
        description="Per-embedding-dimension contribution to the similarity score.",
    )
    terms: dict[str, float] = Field(
        description="Per-term contribution to the match (lexical explainability).",
    )
    confidence_margin: float = Field(
        description="Score gap between this hit and the next-best hit; smaller is more ambiguous.",
    )


class SearchResult(BaseModel):
    """A single ranked hit from a vector search over incidents or runbooks."""

    id: str = Field(description="Identifier of the matched document (incident or runbook).")
    text: str = Field(description="The matched document's text content.")
    score: float = Field(description="Similarity score (cosine) for this hit.")
    attribution: Attribution = Field(description="Explainability breakdown for this hit.")


# ─── UC3 Atlassian agent output ────────────────────────────────────────────────


class RcaDraft(BaseModel):
    """Structured root-cause-analysis draft produced by the UC3 incident agent.

    Always a Pydantic structured output — never parsed from free text — so the
    flight recorder can replay tool dispatch deterministically (AgentRR,
    arXiv:2505.17716). Matches the Rovo agent prompt contract in
    ``docs/BATTLE_PLAN.md`` §6.
    """

    root_cause_hypothesis: str = Field(description="The proposed root cause of the incident.")
    evidence: list[str] = Field(
        description="Specific evidence (similar incidents, runbook excerpts) for the hypothesis.",
    )
    severity_rationale: str = Field(description="Why the proposed severity was chosen.")
    proposed_severity: SeverityLevel = Field(description="Proposed incident severity level.")
    proposed_assignee_team: str = Field(
        description="Team the incident should be assigned to, based on similar past patterns.",
    )
    duplicate_check: list[str] = Field(
        description="IDs of suspected semantic-duplicate incidents (empty if none found).",
    )
    knowledge_gaps: list[str] = Field(
        description="Topics with no matching runbook (drive Confluence stub creation).",
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0, description="Agent's confidence in this draft, in [0, 1]."
    )


class DuplicateVerdict(BaseModel):
    """LLM judgment on whether an incoming incident is a semantic duplicate.

    Produced by the UC3 semantic duplicate resolver after vector-searching the
    incidents collection. Always a Pydantic structured output — never parsed from
    free text — so the Forge action can act on it deterministically. ``flag_for_human``
    is deliberately NOT a field here: it is derived from this verdict and surfaced on
    the response envelope (``atlassian_remote.models.DuplicateResult``), keeping this
    schema a pure model contract (mirrors how ``RcaDraft`` omits it).
    """

    is_duplicate: bool = Field(
        description="True when the incident is judged a true semantic duplicate of a past one.",
    )
    duplicate_of: str | None = Field(
        default=None,
        description="Incident id of the matched duplicate (None when is_duplicate is False).",
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Judge confidence in the duplicate verdict, in [0, 1]."
    )
    rationale: str = Field(
        description="Why the incident is or is not a duplicate (semantic, not lexical, reasoning).",
    )
    explanation: str = Field(
        description="Polite reporter-facing message to post as a Jira comment when confident.",
    )
    candidates: list[str] = Field(
        description="Ids of near-miss incidents to surface for human review (empty if none).",
    )
