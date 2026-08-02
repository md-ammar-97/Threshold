"""Classification output schema, built dynamically from the active
taxonomy version so the model can only ever return label keys that
actually exist in that version (TAX-001/TAX-007) — Pydantic (and, where the
provider enforces it server-side, the API itself) rejects anything else
before it ever reaches application code.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, create_model

from instamart_engine.taxonomy.repository import TaxonomyDimensionInfo, TaxonomyLabelInfo

SENTIMENT_LABELS = ("positive", "neutral", "negative", "mixed")


class LabelWithEvidence(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)
    evidence_excerpt: str = Field(
        description="A short verbatim excerpt from the feedback text supporting this label."
    )


def build_label_model(dimension_key: str, label_keys: list[str]) -> type[LabelWithEvidence]:
    label_literal = Literal[tuple(label_keys)]  # type: ignore[valid-type]
    return create_model(
        f"{dimension_key}_Label",
        __base__=LabelWithEvidence,
        label=(label_literal, ...),
    )


def build_classification_output_model(
    dimensions: list[TaxonomyDimensionInfo],
) -> type[BaseModel]:
    """Every dimension becomes an optional (possibly empty) list field named
    after `dimension.key` — CLS-004: an empty list is always valid; no
    dimension may force a label."""
    dimension_fields: dict[str, tuple[type, object]] = {}
    for dimension in dimensions:
        if not dimension.labels:
            continue
        label_model = build_label_model(dimension.key, [label.key for label in dimension.labels])
        dimension_fields[dimension.key] = (list[label_model], Field(default_factory=list))  # type: ignore[valid-type]

    return create_model(  # type: ignore[call-overload,no-any-return]
        "ClassificationOutput",
        sentiment_label=(Literal[SENTIMENT_LABELS], ...),
        sentiment_score=(float, Field(ge=-1, le=1)),
        sentiment_confidence=(float, Field(ge=0, le=1)),
        severity_value=(int, Field(ge=0, le=5)),
        severity_confidence=(float, Field(ge=0, le=1)),
        summary=(str, ...),
        overall_confidence=(float, Field(ge=0, le=1)),
        **dimension_fields,
    )


def build_topic_output_model(dimensions: list[TaxonomyDimensionInfo]) -> type[BaseModel]:
    """Leaner than `build_classification_output_model`: only the
    per-dimension label fields, no sentiment/severity/summary (those already
    come from the primary classification call) — keeps the topic_main/
    topic_sub call's schema/prompt size isolated from the primary call."""
    dimension_fields: dict[str, tuple[type, object]] = {}
    for dimension in dimensions:
        if not dimension.labels:
            continue
        label_model = build_label_model(dimension.key, [label.key for label in dimension.labels])
        dimension_fields[dimension.key] = (list[label_model], Field(default_factory=list))  # type: ignore[valid-type]

    return create_model(  # type: ignore[call-overload,no-any-return]
        "TopicClassificationOutput",
        **dimension_fields,
    )


def render_taxonomy_reference(dimensions: list[TaxonomyDimensionInfo]) -> str:
    """A dimension whose labels are all children of labels in another
    dimension in this same list (e.g. topic_sub under topic_main) is folded
    and indented under its parent instead of getting its own top-level
    section — gives the model real hierarchical context even though
    `build_classification_output_model` still selects from each dimension
    independently (no structural nesting in the actual output schema).
    Dimensions with no parent-linked labels (all of v1's) render exactly as
    before this function grew a hierarchy branch."""
    label_by_id: dict[UUID, TaxonomyLabelInfo] = {
        label.id: label for dimension in dimensions for label in dimension.labels
    }
    children_by_parent_id: dict[UUID, list[TaxonomyLabelInfo]] = {}
    for dimension in dimensions:
        for label in dimension.labels:
            if label.parent_label_id is not None:
                children_by_parent_id.setdefault(label.parent_label_id, []).append(label)

    child_dimension_keys = {
        dimension.key
        for dimension in dimensions
        if dimension.labels
        and all(
            label.parent_label_id is not None and label.parent_label_id in label_by_id
            for label in dimension.labels
        )
    }

    lines = []
    for dimension in dimensions:
        if dimension.key in child_dimension_keys:
            continue
        lines.append(f"- {dimension.key} ({dimension.display_name}):")
        for label in dimension.labels:
            lines.append(f"    - {label.key}: {label.definition}")
            for child in children_by_parent_id.get(label.id, []):
                lines.append(f"        - {child.key}: {child.definition}")
    return "\n".join(lines)
