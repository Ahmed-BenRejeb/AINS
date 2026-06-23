"""Tests for dimension → concept label resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from atlassian_remote import dimension_label_map
from trace_core import Attribution


@pytest.fixture
def label_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the label map at a tiny fixture file."""
    path = tmp_path / "dimension_labels.json"
    path.write_text(
        json.dumps(
            {
                "Database connection pool exhaustion": [350, 94],
                "Security incident": [421],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DIMENSION_LABELS_PATH", str(path))
    dimension_label_map.clear_dimension_label_cache()
    yield path
    dimension_label_map.clear_dimension_label_cache()


def test_resolve_terms_maps_known_dims(label_fixture: Path) -> None:
    """Known dimensions aggregate into concept labels."""
    terms, unmapped = dimension_label_map.resolve_terms({"350": 0.2, "421": 0.1})

    assert unmapped == []
    assert terms["Database connection pool exhaustion"] == pytest.approx(0.2)
    assert terms["Security incident"] == pytest.approx(0.1)


def test_resolve_terms_reports_unmapped(label_fixture: Path) -> None:
    """Unknown dimensions are returned as unmapped."""
    terms, unmapped = dimension_label_map.resolve_terms({"350": 0.2, "999": 0.15})

    assert terms["Database connection pool exhaustion"] == pytest.approx(0.2)
    assert unmapped == ["999"]


def test_enrich_attribution_fills_terms(label_fixture: Path) -> None:
    """Search attribution gets ``terms`` populated from ``dims``."""
    raw = Attribution(dims={"421": 0.145}, terms={}, confidence_margin=0.05)
    enriched = dimension_label_map.enrich_attribution(raw)

    assert enriched.terms == {"Security incident": pytest.approx(0.145)}
    assert enriched.dims == {"421": 0.145}
