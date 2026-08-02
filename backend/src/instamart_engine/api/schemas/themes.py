"""Response DTOs for the (minimal, read-only) themes surface.
architecture.md §20.4 defines the full theme/insight CRUD surface; this is
just the read path the Phase 7 frontend needs — list + detail."""

from uuid import UUID

from pydantic import BaseModel


class ThemeTagResponse(BaseModel):
    dimension_key: str
    dimension_display_name: str
    label_key: str
    label_display_name: str
    record_count: int


class ThemeSummaryResponse(BaseModel):
    id: UUID
    theme_key: str
    name: str
    theme_type: str
    short_summary: str
    representative_record_count: int
    confidence_score: float | None
    opportunity_score: float | None
    tags: list[ThemeTagResponse]


class EvidencePreviewResponse(BaseModel):
    id: UUID
    excerpt: str
    source_connector_key: str
    published_at: str | None


class ThemeDetailResponse(ThemeSummaryResponse):
    long_summary: str | None
    theme_set_id: UUID
    representative_evidence: list[EvidencePreviewResponse]
    counterexample: EvidencePreviewResponse | None


class ThemeListResponse(BaseModel):
    theme_set_id: UUID | None
    theme_set_status: str | None
    analysis_run_id: UUID | None
    themes: list[ThemeSummaryResponse]
