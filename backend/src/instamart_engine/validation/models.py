"""Validation domain: evaluation datasets, annotations, evaluation runs and
metrics, and generic human review decisions. datamodel.md §47-52;
architecture.md §18."""

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


class EvaluationType(enum.StrEnum):
    CLASSIFICATION = "classification"
    RETRIEVAL = "retrieval"
    THEME = "theme"
    GROUNDING = "grounding"


evaluation_type_enum = Enum(
    EvaluationType, name="evaluation_type", values_callable=lambda e: [m.value for m in e]
)


class EvaluationDatasetStatus(enum.StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    LOCKED = "locked"
    DEPRECATED = "deprecated"


evaluation_dataset_status_enum = Enum(
    EvaluationDatasetStatus,
    name="evaluation_dataset_status",
    values_callable=lambda e: [m.value for m in e],
)


class EvaluationDataset(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §47 — a versioned evaluation or gold dataset.

    Dataset *partition* (development/validation/blind_test, ai_evals.md §6.1)
    and evaluation *subtype* (e.g. `grounding/citations`, ai_evals.md §5) are
    deliberately not separate enum columns — per ai_evals.md §82 "store
    evaluation subtype in metadata rather than proliferating enums
    prematurely" — they live in `selection_method`.
    """

    __tablename__ = "evaluation_dataset"
    __table_args__ = (
        UniqueConstraint("version_key", name="uq_evaluation_dataset_version_key"),
        CheckConstraint("item_count >= 0", name="ck_evaluation_dataset_item_count_nonneg"),
    )

    version_key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    evaluation_type: Mapped[EvaluationType] = mapped_column(evaluation_type_enum, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    taxonomy_version_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[EvaluationDatasetStatus] = mapped_column(
        evaluation_dataset_status_enum,
        nullable=False,
        server_default=EvaluationDatasetStatus.DRAFT.value,
    )
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    selection_method: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvaluationObjectType(enum.StrEnum):
    FEEDBACK_RECORD = "feedback_record"
    RESEARCH_QUESTION = "research_question"
    THEME = "theme"
    GENERATED_ANSWER = "generated_answer"


evaluation_object_type_enum = Enum(
    EvaluationObjectType,
    name="evaluation_object_type",
    values_callable=lambda e: [m.value for m in e],
)


class EvaluationDatasetItem(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §48 — links an evaluation dataset to one evaluated
    object and its immutable test input."""

    __tablename__ = "evaluation_dataset_item"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_dataset_id",
            "object_type",
            "object_id",
            name="uq_evaluation_dataset_item_object",
        ),
    )

    evaluation_dataset_id: Mapped[UUID] = mapped_column(nullable=False)
    object_type: Mapped[EvaluationObjectType] = mapped_column(
        evaluation_object_type_enum, nullable=False
    )
    object_id: Mapped[UUID] = mapped_column(nullable=False)
    input_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    gold_output: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    item_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class Annotation(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §49 — one human annotation of an evaluated item."""

    __tablename__ = "annotation"
    __table_args__ = (
        CheckConstraint("annotation_round > 0", name="ck_annotation_round_positive"),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_annotation_confidence_range",
        ),
    )

    evaluation_dataset_item_id: Mapped[UUID] = mapped_column(nullable=False)
    annotator_actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    annotation_round: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    annotation_output: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    is_adjudicated: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )


class EvaluationRunStatus(enum.StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"


evaluation_run_status_enum = Enum(
    EvaluationRunStatus,
    name="evaluation_run_status",
    values_callable=lambda e: [m.value for m in e],
)


class EvaluationRun(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §50 — one evaluation execution."""

    __tablename__ = "evaluation_run"
    __table_args__ = (
        CheckConstraint("items_evaluated >= 0", name="ck_evaluation_run_items_evaluated_nonneg"),
        CheckConstraint("items_failed >= 0", name="ck_evaluation_run_items_failed_nonneg"),
    )

    evaluation_dataset_id: Mapped[UUID] = mapped_column(nullable=False)
    analysis_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    model_configuration_id: Mapped[UUID | None] = mapped_column(nullable=True)
    prompt_version_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[EvaluationRunStatus] = mapped_column(
        evaluation_run_status_enum,
        nullable=False,
        server_default=EvaluationRunStatus.CREATED.value,
    )
    configuration_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    items_evaluated: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    items_failed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class EvaluationMetric(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §51 — one calculated evaluation metric."""

    __tablename__ = "evaluation_metric"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_run_id",
            "metric_key",
            "dimension_key",
            name="uq_evaluation_metric_run_key_dimension",
        ),
        CheckConstraint("sample_count >= 0", name="ck_evaluation_metric_sample_count_nonneg"),
        CheckConstraint(
            "num_nonnulls(numeric_value, json_value) = 1",
            name="ck_evaluation_metric_exactly_one_value",
        ),
    )

    evaluation_run_id: Mapped[UUID] = mapped_column(nullable=False)
    metric_key: Mapped[str] = mapped_column(Text, nullable=False)
    dimension_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    numeric_value: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    json_value: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    calculation_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class ReviewObjectType(enum.StrEnum):
    FEEDBACK_RELEVANCE = "feedback_relevance"
    FEEDBACK_ANALYSIS = "feedback_analysis"
    ANALYSIS_LABEL = "analysis_label"
    THEME = "theme"
    THEME_MEMBERSHIP = "theme_membership"
    INSIGHT = "insight"
    INSIGHT_EVIDENCE = "insight_evidence"
    ANSWER_FINDING = "answer_finding"
    ANSWER_CITATION = "answer_citation"


review_object_type_enum = Enum(
    ReviewObjectType, name="review_object_type", values_callable=lambda e: [m.value for m in e]
)


class ReviewDecision(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §52 — a generic human-review record for selected entity
    types. `previous_snapshot` is always captured before any mutation so a
    human edit creates a new reviewed version rather than destroying the
    original model output (architecture.md §18.3; edgecases.md REV-006)."""

    __tablename__ = "review_decision"

    object_type: Mapped[ReviewObjectType] = mapped_column(review_object_type_enum, nullable=False)
    object_id: Mapped[UUID] = mapped_column(nullable=False)
    reviewer_actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    decision: Mapped[ReviewStatus] = mapped_column(review_status_enum, nullable=False)
    previous_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    edited_snapshot: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
