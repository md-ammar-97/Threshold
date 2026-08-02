"""Request/response DTOs for the Report Builder surface. design.md §33."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ReportEvidenceLinkResponse(BaseModel):
    id: UUID
    object_type: str
    object_id: UUID
    display_order: int
    snapshot: dict[str, Any]


class ReportSectionResponse(BaseModel):
    id: UUID
    section_type: str
    position: int
    title: str
    content: dict[str, Any]
    narrative_text: str | None
    is_locked: bool
    evidence: list[ReportEvidenceLinkResponse]


class ReportSummaryResponse(BaseModel):
    id: UUID
    title: str
    subtitle: str | None
    status: str
    analysis_run_id: UUID
    theme_set_id: UUID
    insight_set_id: UUID | None
    created_at: str
    updated_at: str
    published_at: str | None


class ReportDetailResponse(ReportSummaryResponse):
    sections: list[ReportSectionResponse]


class ReportListResponse(BaseModel):
    reports: list[ReportSummaryResponse]


class CreateReportRequest(BaseModel):
    title: str
    subtitle: str | None = None
    analysis_run_id: UUID | None = None
    theme_set_id: UUID | None = None
    insight_set_id: UUID | None = None


class UpdateReportRequest(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    status: str | None = None


class EvidenceRefRequest(BaseModel):
    object_type: str
    object_id: UUID


class CreateSectionRequest(BaseModel):
    section_type: str
    title: str
    content: dict[str, Any] = {}
    narrative_text: str | None = None
    position: int | None = None
    evidence: list[EvidenceRefRequest] = []


class UpdateSectionRequest(BaseModel):
    title: str | None = None
    content: dict[str, Any] | None = None
    narrative_text: str | None = None
    is_locked: bool | None = None


class ReorderSectionsRequest(BaseModel):
    section_ids: list[UUID]


class CreateExportRequest(BaseModel):
    export_format: str


class ReportExportResponse(BaseModel):
    id: UUID
    report_id: UUID
    export_format: str
    status: str
    sha256: str | None
    byte_size: int | None
    failure_code: str | None
    failure_message: str | None
    created_at: str
    completed_at: str | None
    content: str | dict[str, Any] | None


class EmailExportRequest(BaseModel):
    recipient_email: str


class EmailExportResponse(BaseModel):
    message_id: str
    recipient_email: str
