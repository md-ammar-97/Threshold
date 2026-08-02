"""Reporting domain: curated research reports, their ordered sections,
evidence links, and export jobs. datamodel.md Part IX (§53-56); design.md
§33 (Report Builder), §42 (Empty report state)."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from instamart_engine.core.database import Base, UUIDPrimaryKeyMixin


class ReportStatus(enum.StrEnum):
    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


report_status_enum = Enum(
    ReportStatus, name="report_status", values_callable=lambda e: [m.value for m in e]
)


class Report(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §53 — a curated research report draft."""

    __tablename__ = "report"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    subtitle: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    analysis_run_id: Mapped[UUID] = mapped_column(nullable=False)
    theme_set_id: Mapped[UUID] = mapped_column(nullable=False)
    insight_set_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[ReportStatus] = mapped_column(
        report_status_enum, nullable=False, server_default=ReportStatus.DRAFT.value
    )
    report_configuration: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReportSectionType(enum.StrEnum):
    EXECUTIVE_SUMMARY = "executive_summary"
    RESEARCH_SCOPE = "research_scope"
    COVERAGE = "coverage"
    KEY_THEME = "key_theme"
    KEY_INSIGHT = "key_insight"
    OPPORTUNITY = "opportunity"
    CONTRADICTION = "contradiction"
    LIMITATION = "limitation"
    VALIDATION_PLAN = "validation_plan"
    METHODOLOGY = "methodology"
    APPENDIX = "appendix"


report_section_type_enum = Enum(
    ReportSectionType,
    name="report_section_type",
    values_callable=lambda e: [m.value for m in e],
)


class ReportSection(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §54 — ordered report content. `is_locked` (design.md
    §33.4 "lock manually edited sections") prevents a later regeneration
    pass from silently overwriting a human edit."""

    __tablename__ = "report_section"
    __table_args__ = (
        UniqueConstraint("report_id", "position", name="uq_report_section_report_position"),
        CheckConstraint("position > 0", name="ck_report_section_position_positive"),
    )

    report_id: Mapped[UUID] = mapped_column(nullable=False)
    section_type: Mapped[ReportSectionType] = mapped_column(
        report_section_type_enum, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    narrative_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_locked: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )


class ReportEvidenceType(enum.StrEnum):
    """Mirrors `research.models.CitationObjectType`'s vocabulary plus
    `generated_answer` — a report section can cite a whole answer, not just
    the record/theme/insight/metric granularity a citation does."""

    FEEDBACK_RECORD = "feedback_record"
    THEME = "theme"
    THEME_METRIC = "theme_metric"
    INSIGHT = "insight"
    GENERATED_ANSWER = "generated_answer"


report_evidence_type_enum = Enum(
    ReportEvidenceType,
    name="report_evidence_type",
    values_callable=lambda e: [m.value for m in e],
)


class ReportEvidenceLink(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §55 — links a report section to an immutable snapshot of
    a research artifact. `snapshot` is captured at link time so a later edit
    to the draft theme/insight doesn't silently change a published export
    (datamodel.md §66 report lineage)."""

    __tablename__ = "report_evidence_link"
    __table_args__ = (
        UniqueConstraint(
            "report_section_id",
            "object_type",
            "object_id",
            name="uq_report_evidence_link_section_object",
        ),
        CheckConstraint("display_order > 0", name="ck_report_evidence_link_display_order_positive"),
    )

    report_section_id: Mapped[UUID] = mapped_column(nullable=False)
    object_type: Mapped[ReportEvidenceType] = mapped_column(
        report_evidence_type_enum, nullable=False
    )
    object_id: Mapped[UUID] = mapped_column(nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class ReportExportFormat(enum.StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"
    PDF = "pdf"


report_export_format_enum = Enum(
    ReportExportFormat,
    name="report_export_format",
    values_callable=lambda e: [m.value for m in e],
)


class ReportExportStatus(enum.StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


report_export_status_enum = Enum(
    ReportExportStatus,
    name="report_export_status",
    values_callable=lambda e: [m.value for m in e],
)


class ReportExport(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §56 — an export job and its generated artifact. Only
    `markdown`/`json` are actually renderable today (see `reports/export.py`)
    — `pdf` is a documented, deferred `ReportExportFormat` member, not
    silently unsupported: datamodel.md itself says "support only Markdown
    and JSON report export initially, with PDF added later"."""

    __tablename__ = "report_export"

    report_id: Mapped[UUID] = mapped_column(nullable=False)
    export_format: Mapped[ReportExportFormat] = mapped_column(
        report_export_format_enum, nullable=False
    )
    status: Mapped[ReportExportStatus] = mapped_column(
        report_export_status_enum,
        nullable=False,
        server_default=ReportExportStatus.CREATED.value,
    )
    storage_backend: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    export_configuration: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    failure_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
