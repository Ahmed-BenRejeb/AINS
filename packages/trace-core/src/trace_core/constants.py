"""Shared named constants for the Sentinel platform.

Every constant in this module carries a comment explaining its origin — the
paper, specification, or business decision it comes from. This is the single
place these magic numbers are allowed to be written down; everywhere else they
must be imported from here (see the root ``CLAUDE.md`` coding standards).

This module has no runtime dependencies and no business logic.
"""

from __future__ import annotations

from typing import Final

# ─── Evaluation (UC1 — eval-engine) ────────────────────────────────────────────

PASS_AT_K_TRIALS: Final[int] = 8
"""Number of independent trials for the ``pass^k`` reliability metric.

Origin: τ-bench (Yao et al., arXiv:2406.12045). ``pass^k`` requires ALL k
independent trials to succeed and exposes catastrophic inconsistency that
``pass@1`` hides (GPT-4o: ~61% pass@1 collapses to ~25% pass^8). k=8 is the
τ-bench standard and the headline metric in ``docs/eval_report.md``.
"""

CONFIDENCE_THRESHOLD: Final[float] = 0.70
"""Minimum judge confidence below which a verdict is flagged for human review.

Origin: ``.env`` key ``EVAL_CONFIDENCE_THRESHOLD`` and the UC3 workflow in
``docs/BATTLE_PLAN.md`` §6 — ``if verdict.confidence < CONFIDENCE_THRESHOLD:
return needs_human_review``. A low-confidence verdict auto-files a "Human Review
Required" Jira issue (self-evaluation bonus point).
"""

VECTOR_SIMILARITY_THRESHOLD: Final[float] = 0.75
"""Minimum cosine similarity for a vector-search hit to count as relevant.

Origin: ``.env`` key ``VECTOR_SIMILARITY_THRESHOLD``. Applied to xqdrant /
Vectorize cosine scores (768-dim BGE-Base-EN embeddings) when retrieving
similar incidents and runbooks. Below this, the agent treats a result as "no
relevant match" (drives knowledge-gap detection in UC3).
"""

MAX_RETRIEVAL_RESULTS: Final[int] = 5
"""Default top-k cap for vector retrieval of similar incidents/runbooks.

Origin: ``docs/BATTLE_PLAN.md`` §6 multi-agent workflow — ``vector_search(...,
k=5)`` for similar incidents. Bounds retrieval cost and keeps the RCA prompt
focused on the most relevant evidence.
"""

# ─── Flight Recorder (UC2 — cassettes & replay) ────────────────────────────────

CASSETTE_VERSION: Final[int] = 1
"""Schema version of the flight-recorder cassette format.

Origin: ``spec/otel-genai-replay-extension.md`` attribute
``gen_ai.replay.cassette_version``. The cassette stores recorded boundary events
keyed by :func:`trace_core.hash_utils.hash_step_key`. Any change to the
hashing/normalization logic or the recorded payload shape MUST bump this number,
because it invalidates every previously recorded cassette.
"""

# ─── Audit Trail (UC2 — tamper-evident hash chain) ─────────────────────────────

AUDIT_HMAC_ALGORITHM: Final[str] = "sha256"
"""Hash algorithm used for the HMAC that signs each audit record.

Origin: ``spec/mcp-audit-trail-proposal.md`` — records are HMAC-SHA256 signed
with the server-side ``AUDIT_HMAC_KEY`` (see ``.env``). Passed to
``hmac.new(key, msg, digestmod=AUDIT_HMAC_ALGORITHM)``. Changing this breaks
verification of every existing audit chain.
"""

HASH_ALGORITHM: Final[str] = "sha256"
"""Hash algorithm used for canonical payload hashing and cassette step keys.

Origin: ``docs/BATTLE_PLAN.md`` §4 hash-chained audit trail — ``payload_hash``
and ``prev_hash`` are ``sha256:`` digests of canonical JSON. Kept separate from
:data:`AUDIT_HMAC_ALGORITHM` so the content hash and the signature algorithm can
evolve independently if ever needed.
"""

HASH_PREFIX: Final[str] = "sha256:"
"""Prefix on hash strings (e.g. ``sha256:abc123...``).

Origin: the audit record shape in ``docs/BATTLE_PLAN.md`` §4 and
``spec/mcp-audit-trail-proposal.md`` (``"prev_hash": "sha256:..."``). Makes the
digest algorithm self-describing inside stored records and trace attributes.
"""

VOLATILE_REQUEST_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "timestamp",
        "request_id",
        "x-request-id",
        "idempotency_key",
        "nonce",
        "trace_id",
        "span_id",
    }
)
"""Request keys stripped before hashing so replay lookups stay deterministic.

Origin: AgentRR (arXiv:2505.17716) determinism insight and ``docs/BATTLE_PLAN.md``
§4 — "normalize + hash (strips timestamps/UUIDs)". These fields change on every
otherwise-identical request and would defeat cassette lookup if hashed. Edits to
this set change every cassette key and therefore require a :data:`CASSETTE_VERSION`
bump.
"""

# ─── Observability ─────────────────────────────────────────────────────────────

LOG_LEVEL: Final[str] = "INFO"
"""Default level for the project's structured logger.

Origin: project coding standard (root ``CLAUDE.md`` §6 — "no ``console.log`` /
``print`` in production code, use a structured logger"). A standard ``logging``
level name; overridable per service via environment configuration.
"""
