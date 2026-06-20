"""CF Workers AI client tests — response normalization for the judge."""

from __future__ import annotations

import json

from eval_engine import cf_ai_client


def test_response_text_passes_through_string() -> None:
    """A plain string response is returned unchanged."""
    assert cf_ai_client._response_text({"response": "hello"}) == "hello"


def test_response_text_serializes_json_mode_dict() -> None:
    """CF auto-parses JSON output: a dict `response` becomes a JSON string.

    Reproduces the live Llama 3.3 70B behaviour that would break the judge's
    `JudgeVerdict.model_validate_json` (which needs a string, not a dict).
    """
    parsed = {"verdict": "pass", "confidence": 0.9}
    out = cf_ai_client._response_text({"response": parsed})

    assert isinstance(out, str)
    assert json.loads(out) == parsed


def test_response_text_missing_key_is_empty_string() -> None:
    """A result without a 'response' key yields an empty string."""
    assert cf_ai_client._response_text({}) == ""
