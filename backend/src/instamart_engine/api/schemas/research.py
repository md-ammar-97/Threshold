"""Request/response DTOs for the research workspace API. architecture.md §20.6."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CreateResearchSessionRequest(BaseModel):
    title: str
    analysis_run_id: UUID
    theme_set_id: UUID
    insight_set_id: UUID | None = None
    default_filters: dict[str, Any] = Field(default_factory=dict)


class ResearchSessionResponse(BaseModel):
    id: UUID
    title: str
    analysis_run_id: UUID
    theme_set_id: UUID
    insight_set_id: UUID | None
    status: str
    created_at: datetime


class CreateQuestionRequest(BaseModel):
    question_text: str = Field(min_length=1, max_length=2000)
    requested_filters: dict[str, str] = Field(default_factory=dict)


class QueryPlanResponse(BaseModel):
    research_dimensions: list[str]
    query_intent: str
    structured_filters: dict[str, Any]
    ambiguity_warnings: dict[str, Any]
    requires_deterministic_aggregation: bool


class AnswerCitationResponse(BaseModel):
    citation_label: str
    object_type: str
    object_id: UUID
    evidence_role: str
    excerpt_snapshot: str | None
    supports_claim: bool | None


class AnswerFindingResponse(BaseModel):
    position: int
    finding_type: str
    statement: str
    confidence_level: str
    confidence_score: float | None
    support_status: str
    citations: list[AnswerCitationResponse]


class AnswerWarningResponse(BaseModel):
    warning_type: str
    severity: str
    message: str
    details: dict[str, Any]


class GeneratedAnswerResponse(BaseModel):
    id: UUID
    answer_text: str
    grounding_status: str
    grounding_score: float | None
    citation_count: int
    warning_count: int
    observed_evidence_count: int
    synthesized_insight_count: int
    product_hypothesis_count: int
    limitations: list[str]
    suggested_validations: list[str]
    findings: list[AnswerFindingResponse]
    warnings: list[AnswerWarningResponse]


class ResearchQuestionResponse(BaseModel):
    id: UUID
    research_session_id: UUID
    question_text: str
    status: str
    requested_filters: dict[str, Any]
    effective_filters: dict[str, Any]
    answer_mode: str | None
    failure_code: str | None
    failure_message: str | None
    query_plan: QueryPlanResponse | None
    answer: GeneratedAnswerResponse | None
