"""The built-in evaluator-quality gold set is well-formed."""

from __future__ import annotations

from eval_engine.gold_demo import demo_gold_set


def test_demo_gold_set_shape() -> None:
    """4 cases (2 expected-pass, 2 expected-fail), each with records."""
    cases = demo_gold_set()
    assert len(cases) == 4
    assert sorted(c.expected for c in cases) == ["fail", "fail", "pass", "pass"]
    assert all(len(c.records) >= 1 for c in cases)
    # Run ids are unique so a κ join never collapses cases.
    assert len({c.run_id for c in cases}) == 4
