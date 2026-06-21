"""Atlassian Remote HTTP API (UC3 heavy-compute backend).

FastAPI service on port 8080 (exposed at ``remote.ahmedxsaad.me``). Called only by
the ``atlassian-agent`` Forge app over Forge Remote. Every functional request is
authenticated with the shared ``X-Sentinel-Secret`` header (root atlassian-remote
CLAUDE.md security section); ``/health`` is an unauthenticated liveness probe so
the Cloudflare Tunnel can monitor it.

Run locally::

    uv run uvicorn api:app --reload --port 8080
"""

from __future__ import annotations

import hmac
import logging

from atlassian_remote import analyzer, cf_ai_client, vector_search
from atlassian_remote.config import forge_remote_secret
from atlassian_remote.langfuse_client import init_langfuse
from atlassian_remote.models import AnalyzeResult, DuplicateResult
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from trace_core import MAX_RETRIEVAL_RESULTS, SearchResult

logger = logging.getLogger("atlassian_remote.api")

app = FastAPI(title="Sentinel Atlassian Remote", version="0.1.0")

# Initialise Langfuse observability at startup (no-op if LANGFUSE_* is unset).
init_langfuse()


async def verify_request(request: Request) -> str:
    """Authenticate a Forge Remote request and return the caller's account id.

    Compares the ``X-Sentinel-Secret`` header against ``FORGE_REMOTE_SECRET`` in
    constant time. The ``X-Account-Id`` header is logged for audit context.

    Args:
        request: The incoming request.

    Returns:
        The caller's Atlassian account id (``"unknown"`` if the header is absent).

    Raises:
        HTTPException: 401 if the secret is missing or does not match.
    """
    provided = request.headers.get("X-Sentinel-Secret") or ""
    if not hmac.compare_digest(provided, forge_remote_secret()):
        raise HTTPException(status_code=401, detail="invalid or missing X-Sentinel-Secret")
    account_id = request.headers.get("X-Account-Id", "unknown")
    logger.info("remote request authenticated accountId=%s path=%s", account_id, request.url.path)
    return account_id


class AnalyzeRequest(BaseModel):
    """Body for ``POST /analyze``."""

    incident_key: str = Field(description="Jira issue key to analyse (e.g. 'AO-123').")
    requested_by: str = Field(description="Atlassian account id of the requester.")


class DuplicateRequest(BaseModel):
    """Body for ``POST /duplicates``."""

    incident_key: str = Field(description="Jira issue key to check for duplicates (e.g. 'AO-123').")
    requested_by: str = Field(description="Atlassian account id of the requester.")


class SearchRequest(BaseModel):
    """Body for ``POST /search``."""

    query: str = Field(description="Free text to embed and search with.")
    index: str = Field(description="xqdrant collection name ('incidents' or 'runbooks').")
    k: int = Field(
        default=MAX_RETRIEVAL_RESULTS, ge=1, description="Top-k cap before threshold filtering."
    )


class SearchResponse(BaseModel):
    """Response for ``POST /search``."""

    results: list[SearchResult] = Field(description="Relevant hits, each with attribution.")


class EmbedRequest(BaseModel):
    """Body for ``POST /embed``."""

    texts: list[str] = Field(description="Strings to embed (BGE, 768-dim).")


class EmbedResponse(BaseModel):
    """Response for ``POST /embed``."""

    embeddings: list[list[float]] = Field(description="One vector per input text, in order.")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe (unauthenticated)."""
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(
    request: AnalyzeRequest, account_id: str = Depends(verify_request)
) -> AnalyzeResult:
    """Analyse an incident end-to-end (the Phase 4 loop).

    Retrieves evidence and drafts a structured RCA while the flight recorder tapes
    every LLM call, then has the eval engine judge the recorded run. Returns the
    draft, supporting hits, the eval verdict, and a replay deep link.
    """
    return await analyzer.analyze_incident(request.incident_key, request.requested_by)


@app.post("/duplicates")
async def duplicates(
    request: DuplicateRequest, account_id: str = Depends(verify_request)
) -> DuplicateResult:
    """Judge whether an incident is a semantic duplicate of a past one."""
    return await analyzer.resolve_incident_duplicate(request.incident_key, request.requested_by)


@app.post("/search")
async def search(
    request: SearchRequest, account_id: str = Depends(verify_request)
) -> SearchResponse:
    """Vector-search a collection and return relevant hits with attribution."""
    results = await vector_search.search_similar(request.query, request.index, k=request.k)
    return SearchResponse(results=results)


@app.post("/embed")
async def embed(request: EmbedRequest, account_id: str = Depends(verify_request)) -> EmbedResponse:
    """Embed a batch of texts with the BGE model via CF Workers AI."""
    return EmbedResponse(embeddings=await cf_ai_client.cf_ai_embed(request.texts))
