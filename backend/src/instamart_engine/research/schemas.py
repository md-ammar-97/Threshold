"""Query-planning and answer-generation output schemas.
datamodel.md §41, §43-45; architecture.md §17.2, §17.5."""

from typing import Literal

from pydantic import BaseModel, Field

from instamart_engine.insights.models import ConfidenceLevel, InsightType
from instamart_engine.research.models import QueryIntent

QUERY_INTENT_VALUES = tuple(member.value for member in QueryIntent)
INSIGHT_TYPE_VALUES = tuple(member.value for member in InsightType)
CONFIDENCE_LEVEL_VALUES = tuple(member.value for member in ConfidenceLevel)


class QueryStructuredFilters(BaseModel):
    """The fixed set of filter keys `research.query_filters.ALLOWED_FILTER_KEYS`
    accepts. A free-form `dict[str, str]` can't be expressed as a strict
    JSON schema (Groq's structured-output mode requires `additionalProperties:
    false` on every object), so the filter keys are enumerated as optional
    fields instead."""

    source_connector_key: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    taxonomy_dimension_key: str | None = None
    taxonomy_label_key: str | None = None


class QueryPlanOutput(BaseModel):
    research_dimensions: list[str] = Field(
        description="Short topical dimensions this question is about, e.g. "
        "['exploration_barrier', 'delivery_experience']."
    )
    query_intent: Literal[QUERY_INTENT_VALUES]  # type: ignore[valid-type]
    structured_filters: QueryStructuredFilters = Field(
        default_factory=QueryStructuredFilters,
        description="Only set fields you are confident about "
        "(date_from/date_to are ISO dates). Never include a demographic "
        "attribute as a filter.",
    )
    ambiguity_warnings: list[str] = Field(default_factory=list)
    requires_deterministic_aggregation: bool = Field(
        description="True when the question asks for an exact count or percentage."
    )


class AnswerFindingOutput(BaseModel):
    statement: str = Field(description="One atomic, citable claim.")
    finding_type: Literal[INSIGHT_TYPE_VALUES]  # type: ignore[valid-type]
    confidence_level: Literal[CONFIDENCE_LEVEL_VALUES]  # type: ignore[valid-type]
    confidence_score: float = Field(ge=0, le=1)
    citation_labels: list[str] = Field(
        description="Stable evidence labels this statement relies on, e.g. "
        "['E3', 'T1']. Only use labels given to you in the evidence package."
    )


class GeneratedAnswerOutput(BaseModel):
    answer_text: str = Field(description="A grounded narrative synthesizing the findings below.")
    findings: list[AnswerFindingOutput] = Field(default_factory=list)
    limitations: list[str] = Field(
        default_factory=list,
        description="Source, sample-size, date-coverage, or inference limitations.",
    )
    suggested_validations: list[str] = Field(default_factory=list)
