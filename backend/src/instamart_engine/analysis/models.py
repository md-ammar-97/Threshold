"""Analysis domain: analysis_run (versioned pipeline execution) and the
classification tables. datamodel.md §17, §25-27."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, Integer, Numeric, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from instamart_engine.core.database import Base, UUIDPrimaryKeyMixin


class AnalysisRunStatus(enum.StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


analysis_run_status_enum = Enum(
    AnalysisRunStatus, name="analysis_run_status", values_callable=lambda e: [m.value for m in e]
)


class AnalysisRun(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §17 — a versioned pipeline execution over a dataset
    snapshot. `embedding_configuration_id`, `theme_model_configuration_id`,
    `insight_model_configuration_id`, and `scoring_profile_id` are plain
    UUID columns (not FKs) since those tables don't exist until Phase 3/4."""

    __tablename__ = "analysis_run"
    __table_args__ = (
        CheckConstraint("records_selected >= 0", name="ck_analysis_run_selected_nonneg"),
        CheckConstraint("records_classified >= 0", name="ck_analysis_run_classified_nonneg"),
        CheckConstraint("records_embedded >= 0", name="ck_analysis_run_embedded_nonneg"),
        CheckConstraint("records_failed >= 0", name="ck_analysis_run_failed_nonneg"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_analysis_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[AnalysisRunStatus] = mapped_column(
        analysis_run_status_enum, nullable=False, server_default=AnalysisRunStatus.CREATED.value
    )
    dataset_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    taxonomy_version_id: Mapped[UUID] = mapped_column(nullable=False)
    embedding_configuration_id: Mapped[UUID | None] = mapped_column(nullable=True)
    classification_model_configuration_id: Mapped[UUID] = mapped_column(nullable=False)
    theme_model_configuration_id: Mapped[UUID | None] = mapped_column(nullable=True)
    insight_model_configuration_id: Mapped[UUID | None] = mapped_column(nullable=True)
    clustering_configuration: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    scoring_profile_id: Mapped[UUID | None] = mapped_column(nullable=True)
    records_selected: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    records_classified: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    records_embedded: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class FeedbackAnalysisStatus(enum.StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    LOW_CONFIDENCE = "low_confidence"
    INVALID_OUTPUT = "invalid_output"
    FAILED = "failed"
    HUMAN_CORRECTED = "human_corrected"


feedback_analysis_status_enum = Enum(
    FeedbackAnalysisStatus,
    name="feedback_analysis_status",
    values_callable=lambda e: [m.value for m in e],
)


class FeedbackAnalysis(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §25 — one complete structured analysis of one record."""

    __tablename__ = "feedback_analysis"
    __table_args__ = (
        CheckConstraint(
            "overall_confidence IS NULL OR overall_confidence BETWEEN 0 AND 1",
            name="ck_feedback_analysis_overall_confidence_range",
        ),
        CheckConstraint(
            "sentiment_score IS NULL OR sentiment_score BETWEEN -1 AND 1",
            name="ck_feedback_analysis_sentiment_range",
        ),
        CheckConstraint(
            "severity_value IS NULL OR severity_value BETWEEN 0 AND 5",
            name="ck_feedback_analysis_severity_range",
        ),
    )

    feedback_record_id: Mapped[UUID] = mapped_column(nullable=False)
    analysis_run_id: Mapped[UUID] = mapped_column(nullable=False)
    taxonomy_version_id: Mapped[UUID] = mapped_column(nullable=False)
    model_call_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[FeedbackAnalysisStatus] = mapped_column(
        feedback_analysis_status_enum,
        nullable=False,
        server_default=FeedbackAnalysisStatus.PENDING.value,
    )
    overall_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    sentiment_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    severity_value: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    severity_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_human_corrected: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    supersedes_feedback_analysis_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )


class LabelSource(enum.StrEnum):
    MODEL = "model"
    RULE = "rule"
    HUMAN = "human"
    IMPORTED = "imported"


label_source_enum = Enum(
    LabelSource, name="label_source", values_callable=lambda e: [m.value for m in e]
)


class ReviewStatus(enum.StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    NEEDS_SECOND_REVIEW = "needs_second_review"


review_status_enum = Enum(
    ReviewStatus, name="review_status", values_callable=lambda e: [m.value for m in e]
)


class AnalysisLabel(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §26 — one applied taxonomy label."""

    __tablename__ = "analysis_label"
    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_analysis_label_confidence_range"),
    )

    feedback_analysis_id: Mapped[UUID] = mapped_column(nullable=False)
    taxonomy_dimension_id: Mapped[UUID] = mapped_column(nullable=False)
    taxonomy_label_id: Mapped[UUID] = mapped_column(nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    source: Mapped[LabelSource] = mapped_column(label_source_enum, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        review_status_enum, nullable=False, server_default=ReviewStatus.UNREVIEWED.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )


class TextVariant(enum.StrEnum):
    ORIGINAL = "original"
    NORMALIZED = "normalized"
    REDACTED = "redacted"


text_variant_enum = Enum(
    TextVariant, name="text_variant", values_callable=lambda e: [m.value for m in e]
)


class AnalysisEvidenceSpan(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §27 — the exact excerpt supporting a label."""

    __tablename__ = "analysis_evidence_span"
    __table_args__ = (
        CheckConstraint("start_offset >= 0", name="ck_analysis_evidence_span_start_nonneg"),
        CheckConstraint(
            "end_offset > start_offset", name="ck_analysis_evidence_span_end_after_start"
        ),
        CheckConstraint(
            "support_strength IS NULL OR support_strength BETWEEN 0 AND 1",
            name="ck_analysis_evidence_span_support_range",
        ),
    )

    analysis_label_id: Mapped[UUID] = mapped_column(nullable=False)
    feedback_record_id: Mapped[UUID] = mapped_column(nullable=False)
    text_variant: Mapped[TextVariant] = mapped_column(text_variant_enum, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    excerpt_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    support_strength: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
