import uuid

import pytest
from pydantic import ValidationError

from instamart_engine.analysis.schemas import (
    build_classification_output_model,
    render_taxonomy_reference,
)
from instamart_engine.taxonomy.repository import TaxonomyDimensionInfo, TaxonomyLabelInfo


def _dimensions() -> list[TaxonomyDimensionInfo]:
    return [
        TaxonomyDimensionInfo(
            id=uuid.uuid4(),
            key="exploration_barrier",
            display_name="Exploration Barrier",
            labels=[
                TaxonomyLabelInfo(id=uuid.uuid4(), key="out_of_stock", definition="..."),
                TaxonomyLabelInfo(id=uuid.uuid4(), key="price_uncertainty", definition="..."),
            ],
        )
    ]


def test_valid_payload_parses() -> None:
    model = build_classification_output_model(_dimensions())
    instance = model.model_validate(
        {
            "sentiment_label": "negative",
            "sentiment_score": -0.5,
            "sentiment_confidence": 0.8,
            "severity_value": 2,
            "severity_confidence": 0.7,
            "summary": "User could not find the item they wanted.",
            "overall_confidence": 0.75,
            "exploration_barrier": [
                {"label": "out_of_stock", "confidence": 0.9, "evidence_excerpt": "out of stock"}
            ],
        }
    )
    assert instance.exploration_barrier[0].label == "out_of_stock"  # type: ignore[attr-defined]


def test_empty_dimension_list_is_valid() -> None:
    """CLS-004 — no dimension may force a label."""
    model = build_classification_output_model(_dimensions())
    instance = model.model_validate(
        {
            "sentiment_label": "neutral",
            "sentiment_score": 0.0,
            "sentiment_confidence": 0.6,
            "severity_value": 0,
            "severity_confidence": 0.6,
            "summary": "Nothing notable.",
            "overall_confidence": 0.5,
        }
    )
    assert instance.exploration_barrier == []  # type: ignore[attr-defined]


def test_unknown_label_is_rejected() -> None:
    """TAX-007 — an unknown label key must fail schema validation."""
    model = build_classification_output_model(_dimensions())
    with pytest.raises(ValidationError):
        model.model_validate(
            {
                "sentiment_label": "negative",
                "sentiment_score": -0.5,
                "sentiment_confidence": 0.8,
                "severity_value": 2,
                "severity_confidence": 0.7,
                "summary": "x",
                "overall_confidence": 0.75,
                "exploration_barrier": [
                    {
                        "label": "not_a_real_label",
                        "confidence": 0.9,
                        "evidence_excerpt": "x",
                    }
                ],
            }
        )


def test_severity_out_of_range_is_rejected() -> None:
    model = build_classification_output_model(_dimensions())
    with pytest.raises(ValidationError):
        model.model_validate(
            {
                "sentiment_label": "negative",
                "sentiment_score": -0.5,
                "sentiment_confidence": 0.8,
                "severity_value": 9,
                "severity_confidence": 0.7,
                "summary": "x",
                "overall_confidence": 0.75,
            }
        )


def test_render_taxonomy_reference_includes_all_labels() -> None:
    text = render_taxonomy_reference(_dimensions())
    assert "out_of_stock" in text
    assert "price_uncertainty" in text
    assert "exploration_barrier" in text
