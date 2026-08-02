"""Insight generation output schema. datamodel.md §35-38; architecture.md §16."""

from typing import Literal

from pydantic import BaseModel, Field

from instamart_engine.insights.models import ConfidenceLevel, EvidenceRole, InsightType

INSIGHT_TYPE_VALUES = tuple(member.value for member in InsightType)
CONFIDENCE_LEVEL_VALUES = tuple(member.value for member in ConfidenceLevel)
EVIDENCE_ROLE_VALUES = tuple(member.value for member in EvidenceRole)


class InsightEvidenceCitation(BaseModel):
    excerpt_number: int = Field(
        description="The bracketed number of the cited excerpt, e.g. 2 for [2]. "
        "Use 0 to cite the [0 / counterexample] excerpt."
    )
    role: Literal[EVIDENCE_ROLE_VALUES]  # type: ignore[valid-type]
    relevance_score: float = Field(ge=0, le=1)


class InsightGenerationOutput(BaseModel):
    insight_type: Literal[INSIGHT_TYPE_VALUES]  # type: ignore[valid-type]
    title: str = Field(description="A concise, specific, non-causal insight title.")
    finding: str = Field(
        description="What the evidence shows, grounded only in the excerpts and counts given."
    )
    interpretation: str = Field(
        description="Why the finding matters, without inventing facts or causality."
    )
    affected_context: str | None = Field(
        default=None,
        description="The affected surface, flow, or context — never a demographic segment.",
    )
    product_implication: str | None = Field(
        default=None,
        description="A framed opportunity or question, not a prescriptive roadmap command.",
    )
    validation_recommendation: str | None = Field(
        default=None,
        description="Required when insight_type is product_hypothesis: the next "
        "validation method (e.g. survey, controlled experiment, usability test).",
    )
    confidence_level: Literal[CONFIDENCE_LEVEL_VALUES]  # type: ignore[valid-type]
    confidence_score: float = Field(ge=0, le=1)
    evidence: list[InsightEvidenceCitation] = Field(default_factory=list)
