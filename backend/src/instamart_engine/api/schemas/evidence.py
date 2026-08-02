"""Response DTOs for the (minimal, read-only) evidence surface.
architecture.md §20.5 describes a fuller evidence API; only list + detail
are implemented here."""

from uuid import UUID

from pydantic import BaseModel


class EvidenceRowResponse(BaseModel):
    id: UUID
    excerpt: str
    source_connector_key: str
    record_type: str
    published_at: str | None
    rating_normalized: float | None
    relevance_status: str
    quality_status: str


class EvidenceListResponse(BaseModel):
    total_matching: int
    limit: int
    offset: int
    records: list[EvidenceRowResponse]


class EvidenceDetailResponse(EvidenceRowResponse):
    original_text: str
    redacted_text: str
    language_code: str | None
    source_url: str | None


class EvidenceSourceOption(BaseModel):
    key: str
    display_name: str


class EvidenceSourcesResponse(BaseModel):
    sources: list[EvidenceSourceOption]
