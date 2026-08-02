"""Theme domain: versioned theme sets, themes, memberships, metrics, and
scoring profiles. datamodel.md §30-34; architecture.md §15."""

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


class ThemeSetStatus(enum.StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY_FOR_REVIEW = "ready_for_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


theme_set_status_enum = Enum(
    ThemeSetStatus, name="theme_set_status", values_callable=lambda e: [m.value for m in e]
)


class ThemeSet(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §30 — a versioned set of themes from one analysis run
    and clustering configuration."""

    __tablename__ = "theme_set"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", "version_number", name="uq_theme_set_run_version"),
        CheckConstraint("version_number > 0", name="ck_theme_set_version_positive"),
        CheckConstraint("eligible_record_count >= 0", name="ck_theme_set_eligible_nonneg"),
        CheckConstraint("clustered_record_count >= 0", name="ck_theme_set_clustered_nonneg"),
        CheckConstraint("outlier_record_count >= 0", name="ck_theme_set_outlier_nonneg"),
        CheckConstraint("theme_count >= 0", name="ck_theme_set_theme_count_nonneg"),
    )

    analysis_run_id: Mapped[UUID] = mapped_column(nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ThemeSetStatus] = mapped_column(
        theme_set_status_enum, nullable=False, server_default=ThemeSetStatus.DRAFT.value
    )
    clustering_algorithm: Mapped[str] = mapped_column(Text, nullable=False)
    clustering_configuration: Mapped[dict] = mapped_column(JSONB, nullable=False)
    eligible_record_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    clustered_record_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    outlier_record_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    theme_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    coverage_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    stability_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class ThemeType(enum.StrEnum):
    REPEAT_CATEGORY_DRIVER = "repeat_category_driver"
    EXPLORATION_BARRIER = "exploration_barrier"
    DISCOVERY_MECHANISM = "discovery_mechanism"
    HABIT_SIGNAL = "habit_signal"
    INFORMATION_NEED = "information_need"
    FRUSTRATION = "frustration"
    EXPERIMENTATION_SIGNAL = "experimentation_signal"
    UNMET_NEED = "unmet_need"
    SERVICE_QUALITY = "service_quality"
    OTHER = "other"


theme_type_enum = Enum(ThemeType, name="theme_type", values_callable=lambda e: [m.value for m in e])


class ThemeStatus(enum.StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    MERGED = "merged"
    SPLIT = "split"
    SUPERSEDED = "superseded"


theme_status_enum = Enum(
    ThemeStatus, name="theme_status", values_callable=lambda e: [m.value for m in e]
)


class Theme(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §31. `opportunity_score`/`score_components` are a
    denormalized cache kept in sync with `theme_metric` (see datamodel.md
    fix applied during the docs-review pass — the index that sorts by this
    column requires the column to actually exist)."""

    __tablename__ = "theme"
    __table_args__ = (
        UniqueConstraint("theme_set_id", "theme_key", name="uq_theme_set_key"),
        CheckConstraint(
            "confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1",
            name="ck_theme_confidence_range",
        ),
        CheckConstraint(
            "coherence_score IS NULL OR coherence_score BETWEEN 0 AND 1",
            name="ck_theme_coherence_range",
        ),
        CheckConstraint(
            "opportunity_score IS NULL OR opportunity_score >= 0",
            name="ck_theme_opportunity_score_nonneg",
        ),
    )

    theme_set_id: Mapped[UUID] = mapped_column(nullable=False)
    theme_key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    short_summary: Mapped[str] = mapped_column(Text, nullable=False)
    long_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    theme_type: Mapped[ThemeType] = mapped_column(theme_type_enum, nullable=False)
    status: Mapped[ThemeStatus] = mapped_column(
        theme_status_enum, nullable=False, server_default=ThemeStatus.UNREVIEWED.value
    )
    model_call_id: Mapped[UUID | None] = mapped_column(nullable=True)
    representative_record_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    coherence_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    discovery_relevance_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    actionability_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    opportunity_score: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    score_components: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
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
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ThemeMembership(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §32."""

    __tablename__ = "theme_membership"
    __table_args__ = (
        UniqueConstraint("theme_id", "feedback_record_id", name="uq_theme_membership_theme_record"),
        CheckConstraint(
            "membership_score BETWEEN 0 AND 1", name="ck_theme_membership_score_range"
        ),
        CheckConstraint(
            "rank_within_theme IS NULL OR rank_within_theme > 0",
            name="ck_theme_membership_rank_positive",
        ),
        CheckConstraint(
            "NOT (is_representative AND is_counterexample)",
            name="ck_theme_membership_not_both_rep_and_counter",
        ),
    )

    theme_id: Mapped[UUID] = mapped_column(nullable=False)
    feedback_record_id: Mapped[UUID] = mapped_column(nullable=False)
    membership_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    assignment_method: Mapped[str] = mapped_column(Text, nullable=False)
    is_representative: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    is_counterexample: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    rank_within_theme: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_status: Mapped[ReviewStatus] = mapped_column(
        review_status_enum,
        nullable=False,
        server_default=ReviewStatus.UNREVIEWED.value,
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


class ThemeMetric(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §33 — deterministic theme metrics, keyed and versioned."""

    __tablename__ = "theme_metric"
    __table_args__ = (
        UniqueConstraint(
            "theme_id",
            "metric_key",
            "segment_key",
            "calculation_version",
            name="uq_theme_metric_key_segment_version",
        ),
        CheckConstraint(
            "num_nonnulls(numeric_value, text_value, json_value) = 1",
            name="ck_theme_metric_exactly_one_value",
        ),
    )

    theme_id: Mapped[UUID] = mapped_column(nullable=False)
    metric_key: Mapped[str] = mapped_column(Text, nullable=False)
    segment_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    numeric_value: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    json_value: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    calculation_version: Mapped[str] = mapped_column(Text, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class ScoringProfileStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


scoring_profile_status_enum = Enum(
    ScoringProfileStatus,
    name="scoring_profile_status",
    values_callable=lambda e: [m.value for m in e],
)


class ScoringProfile(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §34 — versioned opportunity-score weights."""

    __tablename__ = "scoring_profile"
    __table_args__ = (UniqueConstraint("version_key", name="uq_scoring_profile_version_key"),)

    version_key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False)
    normalization_rules: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    formula_expression: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ScoringProfileStatus] = mapped_column(
        scoring_profile_status_enum, nullable=False, server_default=ScoringProfileStatus.DRAFT.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
