"""Insight domain: insight sets, insights, and their theme/evidence links.
datamodel.md §35-38; architecture.md §16."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from instamart_engine.analysis.models import ReviewStatus, review_status_enum
from instamart_engine.core.database import Base, UUIDPrimaryKeyMixin


class InsightSetStatus(enum.StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY_FOR_REVIEW = "ready_for_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


insight_set_status_enum = Enum(
    InsightSetStatus, name="insight_set_status", values_callable=lambda e: [m.value for m in e]
)


class InsightSet(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §35 — groups insights produced from a specific theme set."""

    __tablename__ = "insight_set"
    __table_args__ = (
        UniqueConstraint(
            "theme_set_id", "version_number", name="uq_insight_set_theme_set_version"
        ),
        CheckConstraint("version_number > 0", name="ck_insight_set_version_positive"),
        CheckConstraint("insight_count >= 0", name="ck_insight_set_count_nonneg"),
    )

    theme_set_id: Mapped[UUID] = mapped_column(nullable=False)
    analysis_run_id: Mapped[UUID] = mapped_column(nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    status: Mapped[InsightSetStatus] = mapped_column(
        insight_set_status_enum, nullable=False, server_default=InsightSetStatus.DRAFT.value
    )
    model_configuration_id: Mapped[UUID] = mapped_column(nullable=False)
    prompt_version_id: Mapped[UUID] = mapped_column(nullable=False)
    insight_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class InsightType(enum.StrEnum):
    OBSERVED_EVIDENCE = "observed_evidence"
    SYNTHESIZED_INSIGHT = "synthesized_insight"
    PRODUCT_HYPOTHESIS = "product_hypothesis"


insight_type_enum = Enum(
    InsightType, name="insight_type", values_callable=lambda e: [m.value for m in e]
)


class ConfidenceLevel(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


confidence_level_enum = Enum(
    ConfidenceLevel, name="confidence_level", values_callable=lambda e: [m.value for m in e]
)


class Insight(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §36 — an evidence-backed research insight.

    Publishability (datamodel.md §64) is enforced at the service layer, not
    the DB layer: at least one `insight_evidence` or `insight_theme` row,
    and a `validation_recommendation` when `insight_type` is
    `product_hypothesis` (INS-010).
    """

    __tablename__ = "insight"
    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1",
            name="ck_insight_confidence_score_range",
        ),
        CheckConstraint(
            "opportunity_score IS NULL OR opportunity_score >= 0",
            name="ck_insight_opportunity_score_nonneg",
        ),
    )

    insight_set_id: Mapped[UUID] = mapped_column(nullable=False)
    insight_type: Mapped[InsightType] = mapped_column(insight_type_enum, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    finding: Mapped[str] = mapped_column(Text, nullable=False)
    interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    affected_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_implication: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_level: Mapped[ConfidenceLevel] = mapped_column(confidence_level_enum, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    opportunity_score: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    score_components: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    model_call_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[ReviewStatus] = mapped_column(
        review_status_enum, nullable=False, server_default=ReviewStatus.UNREVIEWED.value
    )
    supersedes_insight_id: Mapped[UUID | None] = mapped_column(nullable=True)
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


class InsightThemeRelationship(enum.StrEnum):
    PRIMARY = "primary"
    SUPPORTING = "supporting"
    CONTRADICTORY = "contradictory"
    CONTEXTUAL = "contextual"


insight_theme_relationship_enum = Enum(
    InsightThemeRelationship,
    name="insight_theme_relationship",
    values_callable=lambda e: [m.value for m in e],
)


class InsightTheme(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §37."""

    __tablename__ = "insight_theme"
    __table_args__ = (
        UniqueConstraint(
            "insight_id", "theme_id", "relationship_type", name="uq_insight_theme_relationship"
        ),
        CheckConstraint(
            "relevance_score IS NULL OR relevance_score BETWEEN 0 AND 1",
            name="ck_insight_theme_relevance_range",
        ),
    )

    insight_id: Mapped[UUID] = mapped_column(nullable=False)
    theme_id: Mapped[UUID] = mapped_column(nullable=False)
    relationship_type: Mapped[InsightThemeRelationship] = mapped_column(
        insight_theme_relationship_enum, nullable=False
    )
    relevance_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class EvidenceRole(enum.StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTORY = "contradictory"
    ILLUSTRATIVE = "illustrative"
    QUANTITATIVE_CONTEXT = "quantitative_context"


evidence_role_enum = Enum(
    EvidenceRole, name="evidence_role", values_callable=lambda e: [m.value for m in e]
)


class InsightEvidence(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §38 — links insights directly to evidence records."""

    __tablename__ = "insight_evidence"
    __table_args__ = (
        UniqueConstraint(
            "insight_id", "feedback_record_id", "evidence_role", name="uq_insight_evidence_role"
        ),
        CheckConstraint(
            "relevance_score BETWEEN 0 AND 1", name="ck_insight_evidence_relevance_range"
        ),
        CheckConstraint(
            "(start_offset IS NULL AND end_offset IS NULL) OR "
            "(start_offset >= 0 AND end_offset > start_offset)",
            name="ck_insight_evidence_offsets_valid",
        ),
    )

    insight_id: Mapped[UUID] = mapped_column(nullable=False)
    feedback_record_id: Mapped[UUID] = mapped_column(nullable=False)
    evidence_role: Mapped[EvidenceRole] = mapped_column(evidence_role_enum, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    excerpt_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
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
