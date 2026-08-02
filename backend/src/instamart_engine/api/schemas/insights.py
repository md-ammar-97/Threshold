"""Response DTOs for the (minimal, read-only) insights surface — mirrors
`api/schemas/themes.py`'s exact shape: list + detail, nothing more.
Phase 4's insights service/repository existed with no API surface at all
until now (audit-2026-07-31.md F-13/R-7)."""

from uuid import UUID

from pydantic import BaseModel


class InsightSummaryResponse(BaseModel):
    id: UUID
    insight_type: str
    title: str
    finding: str
    confidence_level: str
    confidence_score: float | None
    opportunity_score: float | None


class InsightEvidencePreviewResponse(BaseModel):
    id: UUID
    excerpt: str
    evidence_role: str
    source_connector_key: str
    published_at: str | None


class InsightThemeLinkResponse(BaseModel):
    theme_id: UUID
    theme_name: str
    relationship_type: str


class InsightDetailResponse(InsightSummaryResponse):
    interpretation: str
    affected_context: str | None
    product_implication: str | None
    validation_recommendation: str | None
    insight_set_id: UUID
    themes: list[InsightThemeLinkResponse]
    evidence: list[InsightEvidencePreviewResponse]


class InsightListResponse(BaseModel):
    insight_set_id: UUID | None
    insight_set_status: str | None
    theme_set_id: UUID | None
    analysis_run_id: UUID | None
    insights: list[InsightSummaryResponse]
