"""Tests for bisecting two runs to the first diverging step."""

from __future__ import annotations

from flight_recorder.proxy import cassette
from flight_recorder.replay.bisect import bisect_runs


def test_identical_runs_report_no_divergence(fake_blobs: dict[str, bytes]) -> None:
    """Two byte-identical cassettes bisect to 'identical'."""
    for run in ("good", "bad"):
        cassette.save_to_cassette(run, "sha256:k0", {"body": 1})
        cassette.save_to_cassette(run, "sha256:k1", {"body": 2})

    result = bisect_runs("good", "bad")
    assert result.identical is True
    assert result.first_diverging_step is None


def test_diverging_response_is_located(fake_blobs: dict[str, bytes]) -> None:
    """Same request, different recorded output diverges at that step."""
    cassette.save_to_cassette("good", "sha256:k0", {"body": 1})
    cassette.save_to_cassette("good", "sha256:k1", {"body": 2})
    cassette.save_to_cassette("bad", "sha256:k0", {"body": 1})
    cassette.save_to_cassette("bad", "sha256:k1", {"body": 999})

    result = bisect_runs("good", "bad")
    assert result.identical is False
    assert result.first_diverging_step == 1
    assert result.reason == "response diverged (same request, different output)"


def test_diverging_request_is_located(fake_blobs: dict[str, bytes]) -> None:
    """A different request key at a step diverges there."""
    cassette.save_to_cassette("good", "sha256:k0", {"body": 1})
    cassette.save_to_cassette("good", "sha256:k1", {"body": 2})
    cassette.save_to_cassette("bad", "sha256:k0", {"body": 1})
    cassette.save_to_cassette("bad", "sha256:DIFFERENT", {"body": 2})

    result = bisect_runs("good", "bad")
    assert result.first_diverging_step == 1
    assert result.reason == "request diverged (different step_key)"


def test_length_mismatch_diverges_at_shorter_end(fake_blobs: dict[str, bytes]) -> None:
    """A run with extra steps diverges where the shorter one ends."""
    cassette.save_to_cassette("good", "sha256:k0", {"body": 1})
    cassette.save_to_cassette("bad", "sha256:k0", {"body": 1})
    cassette.save_to_cassette("bad", "sha256:k1", {"body": 2})

    result = bisect_runs("good", "bad")
    assert result.first_diverging_step == 1
    assert result.reason == "run length diverged (one run has more steps)"
