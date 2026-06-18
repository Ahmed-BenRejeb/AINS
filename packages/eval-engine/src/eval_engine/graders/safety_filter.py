"""Safety pre-filter using Llama Guard 3 (via Cloudflare Workers AI).

Runs first in the pipeline. If a transcript is unsafe, the reporter short-circuits
to a ``fail`` verdict without spending an LLM-judge call on it.
"""

from __future__ import annotations

from .. import cf_ai_client
from ..models import SafetyResult


async def check_safety(text: str) -> SafetyResult:
    """Classify a transcript with the Llama Guard safety model.

    Args:
        text: The transcript (or any content) to classify.

    Returns:
        A :class:`~eval_engine.models.SafetyResult`; ``safe is False`` means the
        caller should short-circuit to a ``fail`` verdict.
    """
    return await cf_ai_client.cf_ai_safety(text)
